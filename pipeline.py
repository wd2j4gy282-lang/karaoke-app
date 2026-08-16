"""
Karaoke prep pipeline: download audio (YouTube or local file), separate
vocals/instrumental with Demucs, generate word-level lyric timestamps with
WhisperX, and extract a reference pitch curve with librosa.
"""

import colorsys
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
import requests
import torch
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

# PyTorch >=2.6 defaults torch.load to weights_only=True, which blocks
# the pyannote VAD checkpoint used by whisperx (pickled with omegaconf objects).
# Apply the monkeypatch at import time, before any lazy imports happen.
if not getattr(torch.load, "_karaoke_patched", False):
    _orig_torch_load = torch.load

    def _patched_torch_load(*args, **kwargs):
        kwargs["weights_only"] = False
        return _orig_torch_load(*args, **kwargs)

    _patched_torch_load._karaoke_patched = True
    torch.load = _patched_torch_load

OUTPUT_DIR = Path(__file__).parent / "output"

# Ensure Homebrew binaries (ffmpeg, ffprobe) are findable even if the app is
# launched in a context that didn't source the shell profile.
for _brew_bin in ("/opt/homebrew/bin", "/usr/local/bin"):
    if os.path.isdir(_brew_bin) and _brew_bin not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = _brew_bin + os.pathsep + os.environ.get("PATH", "")

# YouTube increasingly forces SABR streaming on the default web client, which
# causes HTTP 403s. Requesting these player clients restores direct downloads.
YT_PLAYER_CLIENTS = "youtube:player_client=android,ios,web_music"

# Ordered processing steps and their human-readable labels.
STEPS = ["download", "separate", "check_lyrics", "transcribe", "resync", "pitch"]
STEP_LABELS = {
    "download": "Downloading audio",
    "separate": "Separating vocals (Demucs)",
    "check_lyrics": "Checking lyrics database",
    "transcribe": "Transcribing lyrics (WhisperX)",
    "resync": "Syncing lyrics to audio",
    "pitch": "Extracting pitch curve",
}


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


def resync_lyrics(audio_path: Path, timestamps: dict, device: str, language_code: str = "en") -> dict:
    """
    Re-align existing lyrics text to the actual audio waveform using
    WhisperX's forced-alignment model. This doesn't re-transcribe -- it
    just takes the lyric lines we already have (e.g. from LrcLib's rough
    line-level timing) and snaps each word to where it's actually sung,
    using the audio's acoustic features.
    """
    import whisperx

    print(f"[whisperx] re-syncing lyrics to {audio_path.name} on {device}...")
    audio = whisperx.load_audio(str(audio_path))

    align_model, metadata = whisperx.load_align_model(
        language_code=language_code, device=device
    )

    # whisperx.align expects segments with "text", "start", "end".
    segments = [
        {"text": seg["text"], "start": seg["start"], "end": seg["end"]}
        for seg in timestamps.get("segments", [])
    ]

    result = whisperx.align(
        segments, align_model, metadata, audio, device,
        return_char_alignments=False,
    )

    return result


def search_lrclib(title: str, artist: str = "") -> list[dict]:
    """Search LrcLib for synced lyrics. Returns list of results with lrc text, or empty list."""
    try:
        url = "https://lrclib.net/api/search"
        params = {"q": title}
        if artist:
            params["q"] = f"{artist} {title}"
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code == 200:
            results = resp.json()
            # Filter to only results with syncedLyrics
            return [r for r in results if r.get("syncedLyrics")]
    except Exception as e:
        print(f"[lrclib] error searching for '{title}': {e}")
    return []


def query_lrclib(title: str, artist: str = "") -> Optional[str]:
    """Query LrcLib for synced lyrics. Returns LRC-format string or None if not found."""
    results = search_lrclib(title, artist)
    if results:
        # Return the first result's lyrics
        return results[0].get("syncedLyrics")
    return None


# ---------------------------------------------------------------------------
# Musixmatch (unofficial "web-desktop" API) -- the same backend Spotify-style
# synced lyrics ultimately come from. No official API key needed; instead a
# short-lived "user token" is fetched from the public token endpoint, the
# same flow used by the desktop/web Musixmatch clients.
# ---------------------------------------------------------------------------

MUSIXMATCH_BASE = "https://apic-desktop.musixmatch.com/ws/1.1"
MUSIXMATCH_APP_ID = "web-desktop-app-v1.0"
MUSIXMATCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
}

_musixmatch_token: Optional[str] = None


def _get_musixmatch_token() -> Optional[str]:
    """Fetch (and cache) an unofficial Musixmatch web token."""
    global _musixmatch_token
    if _musixmatch_token:
        return _musixmatch_token
    try:
        resp = requests.get(
            f"{MUSIXMATCH_BASE}/token.get",
            params={"app_id": MUSIXMATCH_APP_ID, "format": "json"},
            headers=MUSIXMATCH_HEADERS,
            timeout=5,
        )
        body = resp.json().get("message", {}).get("body", {})
        token = body.get("user_token")
        if token:
            _musixmatch_token = token
        return token
    except Exception as e:
        print(f"[musixmatch] error fetching token: {e}")
        return None


def _musixmatch_get(endpoint: str, params: dict) -> Optional[dict]:
    token = _get_musixmatch_token()
    if not token:
        return None
    full_params = {**params, "app_id": MUSIXMATCH_APP_ID, "format": "json", "usertoken": token}
    try:
        resp = requests.get(f"{MUSIXMATCH_BASE}/{endpoint}", params=full_params,
                             headers=MUSIXMATCH_HEADERS, timeout=5)
        data = resp.json()
        status = data.get("message", {}).get("header", {}).get("status_code")
        if status == 401:
            # Token expired/rejected -- refresh once and retry.
            global _musixmatch_token
            _musixmatch_token = None
            token = _get_musixmatch_token()
            if not token:
                return None
            full_params["usertoken"] = token
            resp = requests.get(f"{MUSIXMATCH_BASE}/{endpoint}", params=full_params,
                                 headers=MUSIXMATCH_HEADERS, timeout=5)
            data = resp.json()
        return data
    except Exception as e:
        print(f"[musixmatch] error calling {endpoint}: {e}")
        return None


def search_musixmatch(title: str, artist: str = "") -> list[dict]:
    """Search Musixmatch for a track. Returns a list of raw track dicts."""
    query = f"{artist} {title}".strip() if artist else title
    data = _musixmatch_get("track.search", {
        "q": query,
        "page_size": 15,
        "page": 1,
        "s_track_rating": "desc",
    })
    if not data:
        return []
    track_list = data.get("message", {}).get("body", {}).get("track_list", [])
    return [t["track"] for t in track_list if "track" in t]


def get_musixmatch_lyrics(track_id) -> Optional[dict]:
    """Fetch the best available synced lyrics for a Musixmatch track.

    Tries word-level RichSync first (the same data Spotify's word-by-word
    lyrics use), falling back to line-level LRC subtitles.
    Returns {"format": "richsync"|"lrc", "data": ...} or None.
    """
    data = _musixmatch_get("track.richsync.get", {"track_id": track_id})
    if data:
        body = data.get("message", {}).get("body") or {}
        richsync = (body.get("richsync") or {}).get("richsync_body")
        if richsync:
            return {"format": "richsync", "data": richsync}

    data = _musixmatch_get("track.subtitle.get", {"track_id": track_id, "subtitle_format": "lrc"})
    if data:
        body = data.get("message", {}).get("body") or {}
        subtitle = (body.get("subtitle") or {}).get("subtitle_body")
        if subtitle:
            return {"format": "lrc", "data": subtitle}

    return None


def richsync_to_timestamps(richsync_body: str) -> dict:
    """Convert Musixmatch RichSync JSON (word-level timing) into our
    timestamps.json structure. Already word-level, so no resync needed."""
    lines = json.loads(richsync_body)
    segments = []
    for line in lines:
        start = line.get("ts", 0.0)
        end = line.get("te", start)
        parts = line.get("l", [])
        words = []
        for i, part in enumerate(parts):
            text = part.get("c", "").strip()
            if not text:
                continue
            word_start = start + part.get("o", 0.0)
            word_end = (
                start + parts[i + 1].get("o", 0.0) if i + 1 < len(parts) else end
            )
            words.append({
                "word": text,
                "start": word_start,
                "end": max(word_end, word_start),
                "score": 1.0,
            })
        if words:
            segments.append({
                "start": start,
                "end": end,
                "text": line.get("x", "").strip(),
                "words": words,
            })
    return {"segments": segments, "word_segments": [w for s in segments for w in s["words"]]}


# ---------------------------------------------------------------------------
# Lyrics source dispatcher -- normalizes Musixmatch and LrcLib results so the
# UI can search/select from either database interchangeably.
# ---------------------------------------------------------------------------

def search_lyrics_candidates(title: str, artist: str = "", source: str = "musixmatch") -> list[dict]:
    """Search a lyrics database. Returns up to 15 normalized candidates:
    {track_name, artist_name, album_name, source, _ref}, where `_ref` holds
    whatever is needed later to fetch the full synced lyrics."""
    if source == "lrclib":
        results = search_lrclib(title, artist)
        return [
            {
                "track_name": r.get("trackName"),
                "artist_name": r.get("artistName"),
                "album_name": r.get("albumName"),
                "source": "lrclib",
                "_ref": {"synced_lyrics": r.get("syncedLyrics")},
            }
            for r in results[:15]
        ]

    results = search_musixmatch(title, artist)
    candidates = []
    for r in results[:15]:
        candidates.append({
            "track_name": r.get("track_name"),
            "artist_name": r.get("artist_name"),
            "album_name": r.get("album_name"),
            "source": "musixmatch",
            "_ref": {
                "track_id": r.get("track_id"),
                "has_richsync": bool(r.get("has_richsync")),
                "has_subtitles": bool(r.get("has_subtitles")),
            },
        })
    return candidates


def get_lyrics_for_candidate(candidate: dict) -> Optional[dict]:
    """Resolve a candidate from `search_lyrics_candidates` into a
    timestamps.json-compatible dict. Returns
    {"timestamps": {...}, "lyrics_source": "musixmatch-richsync"|"musixmatch-lrc"|"lrclib"}
    or None if the lyrics couldn't be fetched."""
    source = candidate.get("source")
    ref = candidate.get("_ref", {})

    if source == "lrclib":
        lrc_text = ref.get("synced_lyrics")
        if not lrc_text:
            return None
        return {"timestamps": parse_lrc_to_words(lrc_text), "lyrics_source": "lrclib"}

    if source == "musixmatch":
        track_id = ref.get("track_id")
        if not track_id:
            return None
        lyrics = get_musixmatch_lyrics(track_id)
        if not lyrics:
            return None
        if lyrics["format"] == "richsync":
            return {"timestamps": richsync_to_timestamps(lyrics["data"]), "lyrics_source": "musixmatch-richsync"}
        return {"timestamps": parse_lrc_to_words(lyrics["data"]), "lyrics_source": "musixmatch-lrc"}

    return None


def parse_lrc_to_words(lrc_text: str) -> dict:
    """
    Parse LRC format (synchronized lyrics with [mm:ss.xx] timestamps) into
    a timestamps.json-compatible structure with word-level timing.

    LRC format example:
        [00:12.34]This is a line of lyrics
        [00:16.78]Second line here

    LRC only gives us a start time for each line, not how long it's
    actually sung for -- the gap to the next timestamp may include a long
    instrumental break. So instead of stretching words across the whole
    gap, we estimate a realistic spoken/sung duration from the line's
    character count (~12 chars/sec), cap it to the available gap, and then
    distribute that duration across words proportional to each word's
    length.
    """
    CHARS_PER_SECOND = 12.0
    MIN_LINE_DURATION = 0.6
    DEFAULT_LINE_DURATION = 3.0

    lines = lrc_text.strip().split("\n")
    timed_lines = []  # (timestamp, text)

    for line in lines:
        match = re.match(r"\[(\d{2}):(\d{2}\.\d{2})\](.*)", line)
        if not match:
            continue
        mins, secs, text = match.groups()
        timestamp = int(mins) * 60 + float(secs)
        text = text.strip()
        if text:
            timed_lines.append((timestamp, text))

    segments = []
    for i, (timestamp, text) in enumerate(timed_lines):
        gap = (
            timed_lines[i + 1][0] - timestamp
            if i + 1 < len(timed_lines)
            else DEFAULT_LINE_DURATION
        )

        # Estimate how long this line actually takes to sing, capped to the
        # available gap so we never bleed into an instrumental break.
        estimated_duration = max(len(text) / CHARS_PER_SECOND, MIN_LINE_DURATION)
        duration = min(estimated_duration, gap) if gap > 0 else estimated_duration
        end_time = timestamp + duration

        words = text.split()
        if not words:
            continue

        # Distribute the line's duration across words proportional to
        # each word's length, so short words get less time than long ones.
        total_chars = sum(len(w) for w in words)
        word_segments = []
        cursor = timestamp
        for word in words:
            share = len(word) / total_chars if total_chars else 1 / len(words)
            word_duration = duration * share
            word_segments.append({
                "word": word,
                "start": cursor,
                "end": cursor + word_duration,
                "score": 1.0,
            })
            cursor += word_duration

        segments.append({
            "start": timestamp,
            "end": end_time,
            "text": text,
            "words": word_segments,
        })

    return {"segments": segments, "word_segments": [w for s in segments for w in s["words"]]}


# ---------------------------------------------------------------------------
# Manual fine-tuning: global offset shift + per-line "tap to sync" retiming.
# ---------------------------------------------------------------------------

def apply_sync_offset(timestamps: dict, offset: float) -> dict:
    """Shift every word/segment timestamp by `offset` seconds (can be negative).
    Used to bake in a manual correction after a user dials in a sync offset."""
    for segment in timestamps.get("segments", []):
        segment["start"] = max(0.0, segment.get("start", 0.0) + offset)
        segment["end"] = max(0.0, segment.get("end", 0.0) + offset)
        for word in segment.get("words", []):
            word["start"] = max(0.0, word.get("start", 0.0) + offset)
            word["end"] = max(0.0, word.get("end", 0.0) + offset)
    timestamps["word_segments"] = [w for s in timestamps.get("segments", []) for w in s.get("words", [])]
    return timestamps


def retime_segments(timestamps: dict, new_starts: list[float]) -> dict:
    """Re-time each line (segment) to a new tapped start time, redistributing
    that line's words proportional to character length (same heuristic as
    parse_lrc_to_words). `new_starts` must have one entry per segment, in
    order, and be non-decreasing."""
    CHARS_PER_SECOND = 12.0
    MIN_LINE_DURATION = 0.6
    DEFAULT_LINE_DURATION = 3.0

    segments = timestamps.get("segments", [])
    if len(new_starts) != len(segments):
        raise ValueError("new_starts length must match number of segments")

    new_segments = []
    for i, segment in enumerate(segments):
        start = new_starts[i]
        gap = (new_starts[i + 1] - start) if i + 1 < len(new_starts) else DEFAULT_LINE_DURATION

        text = segment.get("text", "")
        words_text = [w["word"] for w in segment.get("words", [])] or text.split()

        estimated = max(len(text) / CHARS_PER_SECOND, MIN_LINE_DURATION)
        duration = min(estimated, gap) if gap > 0 else estimated
        end = start + duration

        total_chars = sum(len(w) for w in words_text) or 1
        cursor = start
        words = []
        for w in words_text:
            share = len(w) / total_chars
            word_duration = duration * share
            words.append({"word": w, "start": cursor, "end": cursor + word_duration, "score": 1.0})
            cursor += word_duration

        new_segments.append({"start": start, "end": end, "text": text, "words": words})

    return {"segments": new_segments, "word_segments": [w for s in new_segments for w in s["words"]]}


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


def _meta_path(song_dir: Path) -> Path:
    return song_dir / "meta.json"


def load_meta(song_id: str, output_dir: Path = OUTPUT_DIR) -> Optional[dict]:
    """Load meta.json for a song, or None if it doesn't have one yet."""
    p = _meta_path(Path(output_dir) / song_id)
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)


def save_meta(song_id: str, meta: dict, output_dir: Path = OUTPUT_DIR) -> None:
    song_dir = Path(output_dir) / song_id
    song_dir.mkdir(parents=True, exist_ok=True)
    with open(_meta_path(song_dir), "w") as f:
        json.dump(meta, f, indent=2)


def start_job(source: str, title: str, output_dir: Path = OUTPUT_DIR) -> str:
    """
    Register a new (or existing) processing job for a song and return its song_id.
    Safe to call again for the same title -- won't overwrite existing progress.
    """
    output_dir = Path(output_dir)
    song_id = slugify(title)
    meta = load_meta(song_id, output_dir)
    if meta is None:
        meta = {
            "id": song_id,
            "title": title,
            "source": source,
            "status": "in_progress",
            "steps": {s: "pending" for s in STEPS},
        }
        save_meta(song_id, meta, output_dir)
    return song_id


def process_song(
    song_id: str,
    model: str = "medium",
    output_dir: Path = OUTPUT_DIR,
    progress_cb=None,
) -> Path:
    """
    Run (or resume) the pipeline for a song that was registered with start_job().

    Each step's completion is recorded in meta.json, so re-running this on a
    song that already has some steps done will skip those and continue from
    where it left off.

    progress_cb(stage: str) is called before each pending stage starts.
    Returns the path to the song's output directory.
    """
    def progress(stage):
        print(f"[pipeline] {stage}")
        if progress_cb:
            progress_cb(stage)

    output_dir = Path(output_dir)
    song_dir = output_dir / song_id

    meta = load_meta(song_id, output_dir)
    if meta is None:
        raise FileNotFoundError(f"No job registered for song_id={song_id!r}")

    meta.setdefault("steps", {s: "pending" for s in STEPS})
    meta["status"] = "in_progress"
    save_meta(song_id, meta, output_dir)

    source = meta["source"]
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # 1. Download (or locate local file)
    if meta["steps"].get("download") != "done":
        progress(STEP_LABELS["download"])
        if source.startswith("http://") or source.startswith("https://"):
            downloads_dir = output_dir / "_downloads"
            input_path, info = download_youtube_audio(source, downloads_dir)
            meta["audio_path"] = str(input_path.relative_to(output_dir))

            # Save the video thumbnail for use as a video-export background.
            thumb_url = info.get("thumbnail")
            if thumb_url:
                try:
                    resp = requests.get(thumb_url, timeout=10)
                    if resp.status_code == 200:
                        with open(song_dir / "thumbnail.jpg", "wb") as f:
                            f.write(resp.content)
                except Exception as e:
                    print(f"[pipeline] could not save thumbnail: {e}")
        else:
            input_path = Path(source).resolve()
            if not input_path.exists():
                raise FileNotFoundError(f"Input file not found: {input_path}")
            meta["audio_path"] = str(input_path)
        meta["steps"]["download"] = "done"
        save_meta(song_id, meta, output_dir)

    audio_path = Path(meta["audio_path"])
    if not audio_path.is_absolute():
        audio_path = output_dir / audio_path

    instrumental_dest = song_dir / "instrumental.wav"
    vocals_dest = song_dir / "vocals.wav"

    # 2. Separate vocals from instrumental
    if meta["steps"].get("separate") != "done":
        progress(STEP_LABELS["separate"])
        demucs_tmp = output_dir / f"_demucs_tmp_{song_id}"
        instrumental_src, vocals_src = run_demucs(audio_path, demucs_tmp)
        shutil.copy(instrumental_src, instrumental_dest)
        shutil.copy(vocals_src, vocals_dest)
        shutil.rmtree(demucs_tmp, ignore_errors=True)
        meta["steps"]["separate"] = "done"
        save_meta(song_id, meta, output_dir)

    # 3. Check for pre-synced lyrics: Musixmatch (word-level RichSync) first,
    # falling back to LrcLib if Musixmatch has no match.
    if meta["steps"].get("check_lyrics") != "done":
        progress(STEP_LABELS["check_lyrics"])
        candidates = search_lyrics_candidates(meta["title"], source="musixmatch")
        source_used = "musixmatch"
        if not candidates:
            candidates = search_lyrics_candidates(meta["title"], source="lrclib")
            source_used = "lrclib"
        if candidates:
            print(f"[pipeline] found {len(candidates)} lyrics candidates for '{meta['title']}' via {source_used}")
            meta["lyrics_candidates"] = [
                {
                    "id": i,
                    "track_name": c.get("track_name"),
                    "artist_name": c.get("artist_name"),
                    "album_name": c.get("album_name"),
                    "source": c.get("source"),
                }
                for i, c in enumerate(candidates)
            ]
            meta["lyrics_candidates_full"] = candidates
        else:
            print(f"[pipeline] no lyrics found for '{meta['title']}'")
            meta["lyrics_candidates"] = []
        meta["steps"]["check_lyrics"] = "done"
        # transcribe stays pending until user confirms a lyrics choice
        save_meta(song_id, meta, output_dir)

        # Pause here so the user can pick a lyrics candidate, run a manual
        # search, or explicitly choose to run WhisperX before we continue.
        if meta["steps"].get("transcribe") != "done":
            progress("awaiting lyrics selection")
            return song_dir

    # 4. Transcribe + align word timestamps (only if not already done by LrcLib)
    if meta["steps"].get("transcribe") != "done":
        progress(STEP_LABELS["transcribe"])
        try:
            # Transcribe + align against the ISOLATED VOCAL STEM, not the
            # original full mix. A clean vocal track dramatically improves
            # CTC forced-alignment accuracy — aligning against a dense full
            # mix (loud guitars/drums) makes word timings drift badly.
            result = run_whisperx(vocals_dest, model, device)
            with open(song_dir / "timestamps.json", "w") as f:
                json.dump(result, f, indent=2)
        except Exception:
            # WhisperX (via speechbrain/pyannote) can throw a harmless
            # exception during model teardown *after* transcription has
            # already completed and written its result. If the output file
            # exists, treat the step as successful instead of failing the
            # whole job.
            if not (song_dir / "timestamps.json").exists():
                raise
            print("[pipeline] ignoring post-transcription cleanup error (timestamps.json was written)")
        meta["steps"]["transcribe"] = "done"
        meta["lyrics_source"] = "whisperx"
        save_meta(song_id, meta, output_dir)

        # WhisperX leaves behind speechbrain/pyannote objects whose deferred
        # finalizers can raise the same harmless "k2_fsa" lazy-import error
        # at an unpredictable later point (e.g. during the next step). Force
        # garbage collection now, with that error suppressed, so it doesn't
        # surface mid-way through the pitch extraction step below.
        import gc
        try:
            gc.collect()
        except Exception:
            pass

    # 4b. Re-sync lyric word timings to the actual audio via forced alignment.
    # WhisperX-sourced lyrics are already aligned (whisperx.align ran as part
    # of transcription) and Musixmatch RichSync is already word-level, so only
    # line-level heuristic sources (LrcLib / Musixmatch LRC) need this step.
    # Forced alignment is deterministic, so a single pass suffices.
    if meta["steps"].get("resync") != "done":
        if meta.get("lyrics_source") in ("lrclib", "musixmatch-lrc"):
            progress(STEP_LABELS["resync"])
            try:
                with open(song_dir / "timestamps.json") as f:
                    timestamps = json.load(f)
                result = resync_lyrics(vocals_dest, timestamps, device)
                with open(song_dir / "timestamps.json", "w") as f:
                    json.dump(result, f, indent=2)
                meta["lyrics_source"] = meta["lyrics_source"] + "+resynced"
            except Exception:
                if not (song_dir / "timestamps.json").exists():
                    raise
                print("[pipeline] ignoring post-resync cleanup error (timestamps.json was written)")

            import gc
            try:
                gc.collect()
            except Exception:
                pass
        meta["steps"]["resync"] = "done"
        save_meta(song_id, meta, output_dir)

    # 5. Extract reference pitch curve from the isolated vocals (for scoring)
    if meta["steps"].get("pitch") != "done":
        progress(STEP_LABELS["pitch"])
        try:
            pitch_data = extract_pitch_curve(vocals_dest)
            with open(song_dir / "pitch.json", "w") as f:
                json.dump(pitch_data, f)
        except Exception:
            # Same harmless leftover WhisperX cleanup error can surface here.
            if not (song_dir / "pitch.json").exists():
                raise
            print("[pipeline] ignoring post-pitch-extraction cleanup error (pitch.json was written)")
        meta["steps"]["pitch"] = "done"
        save_meta(song_id, meta, output_dir)

    meta["status"] = "done"
    save_meta(song_id, meta, output_dir)
    progress("done")
    return song_dir


VIDEO_BACKGROUNDS = ("gradient", "solid", "blur", "photo")

VIDEO_FONTS = {
    "Helvetica Neue": ("/System/Library/Fonts/HelveticaNeue.ttc", 1),
    "Arial Black": "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "Arial": "/System/Library/Fonts/Supplemental/Arial.ttf",
    "Verdana": "/System/Library/Fonts/Supplemental/Verdana Bold.ttf",
    "Georgia": "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
    "Impact": "/System/Library/Fonts/Supplemental/Impact.ttf",
    "Futura": "/System/Library/Fonts/Supplemental/Futura.ttc",
    "Comic Sans": "/System/Library/Fonts/Supplemental/Comic Sans MS Bold.ttf",
    "Times New Roman": "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
}

VIDEO_FONT_NAMES = tuple(VIDEO_FONTS.keys())

VIDEO_GAP_THRESHOLD = 3.0
VIDEO_DOT_COUNT = 3
VIDEO_DOT_DURATION = 1.0

# Number of lines shown at once (current + upcoming) and how they're laid out.
VIDEO_VISIBLE_LINES = 3
VIDEO_LINE_HEIGHT_FRAC = 0.115
VIDEO_ACTIVE_Y_FRAC = 0.60
VIDEO_SCROLL_TRANSITION = 0.6

VIDEO_BACKGROUND_FILENAMES = ("video_background.jpg", "video_background.jpeg", "video_background.png")


def _video_font(font_name: str, size: int) -> "ImageFont.FreeTypeFont":
    entry = VIDEO_FONTS.get(font_name, VIDEO_FONTS["Arial Black"])
    path, index = entry if isinstance(entry, tuple) else (entry, 0)
    try:
        return ImageFont.truetype(path, size, index=index)
    except OSError:
        return ImageFont.truetype(VIDEO_FONTS["Arial Black"], size)


def _build_gradient_base(size: tuple[int, int], seed_hue: float = 0.6) -> np.ndarray:
    """A large, smooth diagonal gradient to slowly pan across between frames."""
    w, h = size
    gw, gh = int(w * 1.4), int(h * 1.4)
    xx, yy = np.meshgrid(np.linspace(0, 1, gw), np.linspace(0, 1, gh))
    diag = (xx + yy) / 2.0

    c1 = colorsys.hsv_to_rgb(seed_hue % 1.0, 0.55, 0.18)
    c2 = colorsys.hsv_to_rgb((seed_hue + 0.12) % 1.0, 0.6, 0.32)

    img = np.zeros((gh, gw, 3), dtype=np.uint8)
    for i in range(3):
        img[:, :, i] = (c1[i] * 255 * (1 - diag) + c2[i] * 255 * diag).astype(np.uint8)
    return img


def _gradient_frame(base: np.ndarray, size: tuple[int, int], t: float) -> Image.Image:
    """Crop a slowly-drifting window from the gradient base for a sense of motion."""
    w, h = size
    gh, gw = base.shape[:2]
    max_dx, max_dy = gw - w, gh - h
    dx = int((np.sin(t * 0.05) * 0.5 + 0.5) * max_dx)
    dy = int((np.cos(t * 0.037) * 0.5 + 0.5) * max_dy)
    return Image.fromarray(base[dy:dy + h, dx:dx + w], "RGB")


def _blur_background(song_dir: Path, size: tuple[int, int]) -> Optional[Image.Image]:
    thumb_path = song_dir / "thumbnail.jpg"
    if not thumb_path.exists():
        return None
    img = ImageOps.fit(Image.open(thumb_path).convert("RGB"), size, Image.LANCZOS)
    img = img.filter(ImageFilter.GaussianBlur(22))
    return Image.blend(img, Image.new("RGB", size, (0, 0, 0)), 0.6)


def _photo_background(song_dir: Path, size: tuple[int, int]) -> Optional[Image.Image]:
    for name in VIDEO_BACKGROUND_FILENAMES:
        path = song_dir / name
        if path.exists():
            return ImageOps.fit(Image.open(path).convert("RGB"), size, Image.LANCZOS)
    return None


def _build_video_lines(timestamps: dict) -> list[dict]:
    """Flatten segments into renderable lines: [{start, end, words: [{text, start, end}]}]."""
    lines = []
    for segment in timestamps.get("segments", []):
        words = [w for w in segment.get("words", []) if "start" in w and "end" in w]
        if not words:
            continue
        lines.append({
            "start": words[0]["start"],
            "end": max(segment.get("end", words[-1]["end"]), words[-1]["end"]),
            "words": [{"text": w["word"], "start": w["start"], "end": w["end"]} for w in words],
        })
    return lines


def _split_long_lines(lines: list[dict], font, max_width: float) -> list[dict]:
    """Break any line whose words would overflow max_width into shorter sub-lines,
    splitting at word boundaries while preserving per-word timing."""
    gap_w = font.getlength(" ")
    result = []
    for line in lines:
        words = line["words"]
        rows: list[list[dict]] = []
        current: list[dict] = []
        current_w = 0.0
        for word in words:
            ww = font.getlength(word["text"])
            needed = current_w + (gap_w if current else 0) + ww
            if current and needed > max_width:
                rows.append(current)
                current = [word]
                current_w = ww
            else:
                current.append(word)
                current_w = needed
        if current:
            rows.append(current)

        if len(rows) <= 1:
            result.append(line)
        else:
            for j, row_words in enumerate(rows):
                is_last = j == len(rows) - 1
                result.append({
                    "start": row_words[0]["start"],
                    # Last sub-line inherits the original segment end so scroll
                    # doesn't trigger prematurely.
                    "end": line["end"] if is_last else row_words[-1]["end"],
                    "words": row_words,
                })
    return result


_SUNG_COLOR = (74, 144, 217)
_ACTIVE_COLOR = (255, 255, 255)
_UPCOMING_COLOR = (130, 130, 130)


def _draw_word_fill(frame: "Image.Image", x: float, cy: float, text: str, font, fill_px: int) -> None:
    """Composite an active-colour overlay onto `frame`, clipped to `fill_px` pixels
    from the left edge of the word — producing a smooth left-to-right fill."""
    bbox = font.getbbox(text, anchor="lm")          # relative to (x, cy)
    x0 = max(0, int(x + bbox[0]) - 1)
    y0 = max(0, int(cy + bbox[1]) - 1)
    x1 = min(frame.width, int(x + bbox[2]) + 1)
    y1 = min(frame.height, int(cy + bbox[3]) + 1)
    if x1 <= x0 or y1 <= y0:
        return
    w_crop, h_crop = x1 - x0, y1 - y0
    # Draw the word in active colour on a small RGBA crop.
    temp = Image.new("RGBA", (w_crop, h_crop), (0, 0, 0, 0))
    ImageDraw.Draw(temp).text(
        (x - x0, cy - y0), text, font=font,
        fill=_ACTIVE_COLOR + (255,), anchor="lm",
    )
    # Zero out alpha to the right of the fill boundary.
    arr = np.array(temp)
    clip_col = int(x + fill_px) - x0
    if clip_col < w_crop:
        arr[:, max(0, clip_col):, 3] = 0
    frame.alpha_composite(Image.fromarray(arr, "RGBA"), dest=(x0, y0))


def _draw_lyric_line(
    draw: "ImageDraw.ImageDraw",
    frame: "Image.Image",
    words: list[dict],
    t: float,
    center: tuple[float, float],
    font,
) -> None:
    gap_w = draw.textlength(" ", font=font)
    widths = [draw.textlength(w["text"], font=font) for w in words]
    total_w = sum(widths) + gap_w * (len(words) - 1)

    cx, cy = center
    x = cx - total_w / 2
    for word, width in zip(words, widths):
        if t >= word["end"]:
            draw.text((x, cy), word["text"], font=font, fill=_SUNG_COLOR, anchor="lm")
        elif t >= word["start"]:
            # Draw the unfilled base in upcoming colour, then overlay the filled
            # portion in active colour clipped to the fraction already sung.
            frac = (t - word["start"]) / max(word["end"] - word["start"], 0.001)
            fill_px = int(width * min(frac, 1.0))
            draw.text((x, cy), word["text"], font=font, fill=_UPCOMING_COLOR, anchor="lm")
            if fill_px > 0:
                _draw_word_fill(frame, x, cy, word["text"], font, fill_px)
        else:
            draw.text((x, cy), word["text"], font=font, fill=_UPCOMING_COLOR, anchor="lm")
        x += width + gap_w


def _draw_countdown_dots(draw: "ImageDraw.ImageDraw", dots: list[tuple[float, float]], t: float, center: tuple[float, float], dot_size: int) -> None:
    cx, cy = center
    dot_r = dot_size // 2
    spacing = dot_size * 2.5
    total_w = spacing * (len(dots) - 1)
    x = cx - total_w / 2
    for ds, de in dots:
        color = _ACTIVE_COLOR if ds <= t < de or t >= de else _UPCOMING_COLOR
        draw.ellipse((x - dot_r, cy - dot_r, x + dot_r, cy + dot_r), fill=color)
        x += spacing


def _compute_gap_dots(lines: list[dict]) -> dict:
    """Precompute "..." countdown dots for gaps >= VIDEO_GAP_THRESHOLD before each line."""
    gap_dots = {}
    prev_end = 0.0
    for line in lines:
        if line["start"] - prev_end >= VIDEO_GAP_THRESHOLD:
            dots = []
            for i in range(VIDEO_DOT_COUNT, 0, -1):
                de = line["start"] - (i - 1) * VIDEO_DOT_DURATION
                dots.append((de - VIDEO_DOT_DURATION, de))
            gap_dots[id(line)] = dots
        prev_end = line["end"]
    return gap_dots


def _scroll_pos(lines: list[dict], t: float) -> float:
    """Return a continuous scroll position P where P == i means line i sits exactly
    at the active slot.  Fractional values animate the transition between two lines.

    The old implementation clamped the transition fraction to 1.0 indefinitely
    after the window closed, leaving every subsequent active line one slot too high.
    This version computes the correct settled value (a whole number) once the
    transition is done and never drifts from it."""
    for i, line in enumerate(lines):
        if t < line["end"]:
            # Singing (or about to sing) line i.
            if i > 0 and t >= lines[i - 1]["end"]:
                # Still within the transition that brought line i into the active slot.
                elapsed = t - lines[i - 1]["end"]
                linear = min(elapsed / VIDEO_SCROLL_TRANSITION, 1.0)
                frac = linear * linear * (3 - 2 * linear)
                return (i - 1) + frac
            return float(i)
        if t < line["end"] + VIDEO_SCROLL_TRANSITION:
            # Line i just ended – animate it scrolling away to reveal line i+1.
            elapsed = t - line["end"]
            linear = min(elapsed / VIDEO_SCROLL_TRANSITION, 1.0)
            frac = linear * linear * (3 - 2 * linear)
            return i + frac
    # Past all lines.
    return float(len(lines))


def _render_frame(
    bg_img: Image.Image,
    lines: list[dict],
    t: float,
    resolution: tuple[int, int],
    title_text: str,
    title_font,
    lyric_font,
    photo_mode: bool,
    gap_dots: dict,
) -> Image.Image:
    """Draw the title and the scrolling lyric block (current + upcoming lines)
    onto a copy of bg_img, returning the composed RGB frame."""
    w, h = resolution
    frame = bg_img.convert("RGBA")
    draw = ImageDraw.Draw(frame)
    draw.text((w / 2, h * 0.06), title_text, font=title_font, fill=(220, 220, 220, 255), anchor="mm")

    _P = _scroll_pos(lines, t)
    base_idx = int(_P)
    scroll_frac = _P - base_idx
    line_height = h * VIDEO_LINE_HEIGHT_FRAC
    active_y = h * VIDEO_ACTIVE_Y_FRAC

    visible = []
    for k in range(VIDEO_VISIBLE_LINES):
        idx = base_idx + k
        if idx < 0 or idx >= len(lines):
            continue
        y = active_y + line_height * (k - scroll_frac)
        if y < -line_height or y > h + line_height:
            continue
        visible.append((lines[idx], y, k))

    # Translucent "subtitle box" behind the lyric block for photo backgrounds.
    if photo_mode and visible:
        pad_x, pad_y = w * 0.04, line_height * 0.3
        top = min(y for _, y, _ in visible) - line_height / 2 - pad_y
        bottom = max(y for _, y, _ in visible) + line_height / 2 + pad_y
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(overlay).rectangle((pad_x, top, w - pad_x, bottom), fill=(0, 0, 0, 140))
        frame = Image.alpha_composite(frame, overlay)
        draw = ImageDraw.Draw(frame)

    for line, y, k in visible:
        _draw_lyric_line(draw, frame, line["words"], t, (w / 2, y), lyric_font)
        # Countdown dots appear ABOVE the upcoming line (not instead of it) so the
        # singer can see both the next lyric and the timing cue simultaneously.
        if k == 0:
            dots = gap_dots.get(id(line))
            if dots and t < line["start"] and t >= dots[0][0]:
                dot_y = y - line_height * 0.7
                _draw_countdown_dots(draw, dots, t, (w / 2, dot_y), int(h * 0.05))

    return frame.convert("RGB")


def _prepare_background(song_dir: Path, background: str, resolution: tuple[int, int]) -> tuple[str, Optional[Image.Image], Optional[np.ndarray]]:
    """Resolve the requested background mode to a static image / gradient base,
    falling back to "gradient" if the requested asset isn't available. Returns
    (resolved_mode, static_image_or_None, gradient_base_or_None)."""
    static_bg = None
    if background == "photo":
        static_bg = _photo_background(song_dir, resolution)
        if static_bg is None:
            background = "gradient"
    if background == "blur":
        static_bg = _blur_background(song_dir, resolution)
        if static_bg is None:
            background = "gradient"
    if background == "solid":
        static_bg = Image.new("RGB", resolution, (18, 18, 18))

    gradient_base = _build_gradient_base(resolution) if background == "gradient" else None
    return background, static_bg, gradient_base


def render_preview_frame(
    song_id: str,
    output_dir: Path = OUTPUT_DIR,
    background: str = "gradient",
    resolution: tuple[int, int] = (1280, 720),
    font_name: str = "Helvetica Neue",
    font_size: int = 48,
) -> Image.Image:
    """Render a single representative frame (showing the lyric scroll mid-song)
    for a live settings preview."""
    output_dir = Path(output_dir)
    song_dir = output_dir / song_id

    meta = load_meta(song_id, output_dir)
    if meta is None:
        raise FileNotFoundError(f"No song with id={song_id!r}")

    with open(song_dir / "timestamps.json") as f:
        timestamps = json.load(f)

    lines = _build_video_lines(timestamps)

    title_font = _video_font(font_name, int(font_size * 0.65))
    lyric_font = _video_font(font_name, font_size)

    w, h = resolution
    lines = _split_long_lines(lines, lyric_font, w * 0.88)
    gap_dots = _compute_gap_dots(lines)

    background, static_bg, gradient_base = _prepare_background(song_dir, background, resolution)
    photo_mode = background == "photo"

    if background == "gradient":
        bg_img = _gradient_frame(gradient_base, resolution, 0.0)
    else:
        bg_img = static_bg

    preview_idx = min(1, max(len(lines) - 1, 0))
    t = (lines[preview_idx]["start"] + lines[preview_idx]["end"]) / 2 if lines else 0.0

    return _render_frame(bg_img, lines, t, resolution, meta.get("title", ""), title_font, lyric_font, photo_mode, gap_dots)


def export_video(
    song_id: str,
    output_dir: Path = OUTPUT_DIR,
    background: str = "gradient",
    resolution: tuple[int, int] = (1280, 720),
    fps: int = 24,
    font_name: str = "Helvetica Neue",
    font_size: int = 48,
    progress_cb=None,
) -> Path:
    """Render a karaoke video with a scrolling lyric-highlight overlay over a
    chosen background, muxed with the instrumental track. Returns the output path."""
    output_dir = Path(output_dir)
    song_dir = output_dir / song_id

    meta = load_meta(song_id, output_dir)
    if meta is None:
        raise FileNotFoundError(f"No song with id={song_id!r}")

    with open(song_dir / "timestamps.json") as f:
        timestamps = json.load(f)

    audio_path = song_dir / "instrumental.wav"
    duration = librosa.get_duration(path=str(audio_path))
    num_frames = int(duration * fps)

    lines = _build_video_lines(timestamps)

    w, h = resolution
    title_font = _video_font(font_name, int(font_size * 0.65))
    lyric_font = _video_font(font_name, font_size)

    lines = _split_long_lines(lines, lyric_font, w * 0.88)
    gap_dots = _compute_gap_dots(lines)

    background, static_bg, gradient_base = _prepare_background(song_dir, background, resolution)
    photo_mode = background == "photo"

    title_text = meta.get("title", "")
    out_path = song_dir / "karaoke.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
        "-i", str(audio_path),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    try:
        for frame_idx in range(num_frames):
            t = frame_idx / fps

            if background == "gradient":
                bg_img = _gradient_frame(gradient_base, resolution, t)
            else:
                bg_img = static_bg

            frame_img = _render_frame(bg_img, lines, t, resolution, title_text, title_font, lyric_font, photo_mode, gap_dots)
            proc.stdin.write(np.asarray(frame_img, dtype=np.uint8).tobytes())

            if progress_cb and frame_idx % fps == 0:
                progress_cb(frame_idx / num_frames)
    finally:
        proc.stdin.close()
        proc.wait()

    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg exited with code {proc.returncode}")

    if progress_cb:
        progress_cb(1.0)

    return out_path


def stitch_intro_video(
    intro_path: Path,
    karaoke_path: Path,
    output_path: Path,
    resolution: tuple[int, int] = (1280, 720),
    fps: int = 24,
) -> None:
    """Prepend intro_path to karaoke_path and write the result to output_path.

    The intro is re-encoded to match the karaoke video specs (resolution, fps,
    yuv420p, aac audio). The karaoke video is copied without re-encoding.
    output_path may be the same file as karaoke_path — a temp file is used
    internally and then renamed."""
    w, h = resolution

    # Probe intro for audio stream.
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(intro_path)],
        capture_output=True, text=True,
    )
    streams = json.loads(probe.stdout).get("streams", []) if probe.returncode == 0 else []
    intro_has_audio = any(s.get("codec_type") == "audio" for s in streams)

    tmp_dir = output_path.parent
    tmp_intro = tmp_dir / f"_intro_norm_{intro_path.stem}.mp4"
    tmp_out = tmp_dir / f"_stitched_{output_path.name}"
    concat_list = tmp_dir / "_concat_list.txt"

    try:
        # Step 1: Re-encode intro to match karaoke specs exactly.
        norm_cmd = ["ffmpeg", "-y", "-i", str(intro_path)]
        if not intro_has_audio:
            norm_cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        vf = (
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,"
            f"fps={fps},format=yuv420p"
        )
        norm_cmd += [
            "-vf", vf,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(tmp_intro),
        ]
        subprocess.run(norm_cmd, check=True, capture_output=True)

        # Step 2: Concat using the demuxer (no re-encode of the main video).
        concat_list.write_text(
            f"file '{tmp_intro.resolve()}'\nfile '{karaoke_path.resolve()}'\n"
        )
        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c", "copy",
            str(tmp_out),
        ]
        subprocess.run(concat_cmd, check=True, capture_output=True)

        # Atomically replace the destination.
        tmp_out.replace(output_path)

    finally:
        for p in (tmp_intro, concat_list, tmp_out):
            try:
                p.unlink()
            except FileNotFoundError:
                pass


def list_library(output_dir: Path = OUTPUT_DIR) -> list[dict]:
    """Scan the output directory for songs (finished or in-progress) and return their metadata."""
    output_dir = Path(output_dir)
    if not output_dir.exists():
        return []

    songs = []
    for entry in sorted(output_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        meta_path = _meta_path(entry)
        if not meta_path.exists():
            continue
        with open(meta_path) as f:
            meta = json.load(f)
        songs.append(meta)
    return songs
