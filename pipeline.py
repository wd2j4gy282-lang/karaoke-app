"""
Karaoke prep pipeline: download audio (YouTube or local file), separate
vocals/instrumental with Demucs, generate word-level lyric timestamps with
WhisperX, and extract a reference pitch curve with librosa.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import librosa
import numpy as np
import torch

OUTPUT_DIR = Path(__file__).parent / "output"

# Ensure Homebrew binaries (ffmpeg, ffprobe) are findable even if the app is
# launched in a context that didn't source the shell profile.
for _brew_bin in ("/opt/homebrew/bin", "/usr/local/bin"):
    if os.path.isdir(_brew_bin) and _brew_bin not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = _brew_bin + os.pathsep + os.environ.get("PATH", "")

# YouTube increasingly forces SABR streaming on the default web client, which
# causes HTTP 403s. Requesting these player clients restores direct downloads.
YT_PLAYER_CLIENTS = "youtube:player_client=android,ios,web_music"


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\- ]", "", text).strip().lower()
    return re.sub(r"[\s_]+", "-", text)


def search_youtube(query: str, limit: int = 8) -> list[dict]:
    """Search YouTube via yt-dlp and return a list of candidate videos."""
    result = subprocess.run(
        [
            sys.executable, "-m", "yt_dlp",
            f"ytsearch{limit}:{query}",
            "--flat-playlist",
            "-J",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    entries = data.get("entries", [])
    videos = []
    for e in entries:
        videos.append({
            "id": e.get("id"),
            "title": e.get("title"),
            "channel": e.get("channel") or e.get("uploader"),
            "duration": e.get("duration"),
            "thumbnail": (e.get("thumbnails") or [{}])[-1].get("url"),
            "url": f"https://www.youtube.com/watch?v={e.get('id')}",
        })
    return videos


def download_youtube_audio(url: str, output_dir: Path) -> tuple[Path, dict]:
    """Download audio from a YouTube URL using yt-dlp. Returns (file_path, info)."""
    print(f"[yt-dlp] downloading audio from {url}...")
    output_dir.mkdir(parents=True, exist_ok=True)

    info_result = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "-J", "--extractor-args", YT_PLAYER_CLIENTS, url],
        check=True, capture_output=True, text=True,
    )
    info = json.loads(info_result.stdout)

    out_template = str(output_dir / "%(id)s.%(ext)s")
    subprocess.run(
        [
            sys.executable, "-m", "yt_dlp",
            "-x", "--audio-format", "mp3",
            "--extractor-args", YT_PLAYER_CLIENTS,
            "-o", out_template,
            url,
        ],
        check=True,
    )

    candidates = list(output_dir.glob(f"{info['id']}.mp3"))
    if not candidates:
        raise FileNotFoundError("yt-dlp did not produce an mp3 file")
    return candidates[0], info


def run_demucs(input_path: Path, output_dir: Path) -> tuple[Path, Path]:
    """Run Demucs two-stem separation and return (instrumental, vocals) paths."""
    print(f"[demucs] separating {input_path.name}...")
    subprocess.run(
        [
            sys.executable, "-m", "demucs",
            "--two-stems", "vocals",
            "-o", str(output_dir),
            str(input_path),
        ],
        check=True,
    )

    stem_dir = next(output_dir.glob(f"*/{input_path.stem}"))
    instrumental = stem_dir / "no_vocals.wav"
    vocals = stem_dir / "vocals.wav"
    if not instrumental.exists():
        raise FileNotFoundError(f"Expected instrumental track at {instrumental}")
    return instrumental, vocals


def run_whisperx(audio_path: Path, model_name: str, device: str) -> dict:
    """Run WhisperX transcription + word-level alignment on the given audio."""
    import whisperx

    print(f"[whisperx] transcribing {audio_path.name} on {device}...")
    compute_type = "float16" if device == "cuda" else "float32"

    model = whisperx.load_model(model_name, device, compute_type=compute_type)
    audio = whisperx.load_audio(str(audio_path))
    result = model.transcribe(audio, batch_size=8)

    print("[whisperx] aligning words...")
    align_model, metadata = whisperx.load_align_model(
        language_code=result["language"], device=device
    )
    result = whisperx.align(
        result["segments"], align_model, metadata, audio, device,
        return_char_alignments=False,
    )

    return result


def extract_pitch_curve(vocals_path: Path) -> dict:
    """Extract a frame-by-frame pitch (f0) curve from the vocals track using librosa.pyin."""
    print(f"[librosa] extracting pitch curve from {vocals_path.name}...")
    y, sr = librosa.load(str(vocals_path), sr=None, mono=True)

    f0, voiced_flag, voiced_prob = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C7"),
        sr=sr,
    )

    hop_length = 512  # librosa.pyin default
    times = librosa.times_like(f0, sr=sr, hop_length=hop_length)

    return {
        "times": times.tolist(),
        "f0": [None if np.isnan(v) else float(v) for v in f0],
        "voiced": [bool(v) for v in voiced_flag],
    }


def process_song(
    source: str,
    title: Optional[str] = None,
    model: str = "medium",
    output_dir: Path = OUTPUT_DIR,
    progress_cb=None,
) -> Path:
    """
    Run the full pipeline on a YouTube URL or local file path.

    progress_cb(stage: str) is called before each stage starts.
    Returns the path to the song's output directory.
    """
    def progress(stage):
        print(f"[pipeline] {stage}")
        if progress_cb:
            progress_cb(stage)

    output_dir = Path(output_dir)
    source_url = None

    if source.startswith("http://") or source.startswith("https://"):
        progress("downloading")
        downloads_dir = output_dir / "_downloads"
        input_path, info = download_youtube_audio(source, downloads_dir)
        title = title or info.get("title")
        source_url = source
    else:
        input_path = Path(source).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        title = title or input_path.stem

    song_id = slugify(title)
    song_output_dir = output_dir / song_id
    song_output_dir.mkdir(parents=True, exist_ok=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"

    # 1. Separate vocals from instrumental
    progress("separating vocals (demucs)")
    demucs_tmp = output_dir / f"_demucs_tmp_{song_id}"
    instrumental_src, vocals_src = run_demucs(input_path, demucs_tmp)

    instrumental_dest = song_output_dir / "instrumental.wav"
    vocals_dest = song_output_dir / "vocals.wav"
    shutil.copy(instrumental_src, instrumental_dest)
    shutil.copy(vocals_src, vocals_dest)
    shutil.rmtree(demucs_tmp, ignore_errors=True)

    # 2. Transcribe + align word timestamps (run on original audio for best accuracy)
    progress("transcribing lyrics (whisperx)")
    result = run_whisperx(input_path, model, device)
    with open(song_output_dir / "timestamps.json", "w") as f:
        json.dump(result, f, indent=2)

    # 3. Extract reference pitch curve from the isolated vocals (for scoring)
    progress("extracting pitch curve (librosa)")
    pitch_data = extract_pitch_curve(vocals_dest)
    with open(song_output_dir / "pitch.json", "w") as f:
        json.dump(pitch_data, f)

    # 4. Save metadata for the library
    meta = {
        "id": song_id,
        "title": title,
        "source_url": source_url,
    }
    with open(song_output_dir / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    progress("done")
    return song_output_dir


def list_library(output_dir: Path = OUTPUT_DIR) -> list[dict]:
    """Scan the output directory for processed songs and return their metadata."""
    output_dir = Path(output_dir)
    if not output_dir.exists():
        return []

    songs = []
    for entry in sorted(output_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        meta_path = entry / "meta.json"
        if not meta_path.exists():
            continue
        with open(meta_path) as f:
            meta = json.load(f)
        songs.append(meta)
    return songs
