import os
import threading
import uuid
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, render_template

import pipeline

app = Flask(__name__)

OUTPUT_DIR = pipeline.OUTPUT_DIR
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TEMP_DIR = OUTPUT_DIR / "_tmp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Folder where finished exports (and reusable intros) live alongside the app.
VIDEO_EXPORTS_DIR = Path(__file__).parent / "Video Exports"
VIDEO_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

# In-memory job tracker: job_id -> {"status": ..., "stage": ..., "song_id": ..., "error": ...}
jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()

# song_id -> job_id, only present while a job is actively running for that song
active_jobs: dict[str, str] = {}

# temp_id -> Path, for uploaded intro videos pending stitching
temp_uploads: dict[str, Path] = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/library")
def api_library():
    songs = pipeline.list_library(OUTPUT_DIR)
    with jobs_lock:
        for song in songs:
            song["active_job_id"] = active_jobs.get(song["id"])
            song["step_labels"] = pipeline.STEP_LABELS
            song["step_order"] = pipeline.STEPS
    return jsonify(songs)


@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "missing query"}), 400
    try:
        results = pipeline.search_youtube(query)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(results)


def _run_job(song_id: str):
    job_id = uuid.uuid4().hex
    with jobs_lock:
        jobs[job_id] = {"status": "queued", "stage": None, "song_id": song_id, "error": None}
        active_jobs[song_id] = job_id

    def on_progress(stage):
        with jobs_lock:
            jobs[job_id]["status"] = "running"
            jobs[job_id]["stage"] = stage

    def run():
        try:
            pipeline.process_song(
                song_id, output_dir=OUTPUT_DIR, progress_cb=on_progress
            )
            with jobs_lock:
                jobs[job_id]["status"] = "done"
        except Exception as e:
            with jobs_lock:
                jobs[job_id]["status"] = "error"
                jobs[job_id]["error"] = str(e)
        finally:
            with jobs_lock:
                active_jobs.pop(song_id, None)

    threading.Thread(target=run, daemon=True).start()
    return job_id


def _run_resync_job(song_id: str):
    job_id = uuid.uuid4().hex
    with jobs_lock:
        jobs[job_id] = {"status": "queued", "stage": "Re-syncing lyrics to audio", "song_id": song_id, "error": None}
        active_jobs[song_id] = job_id

    def run():
        try:
            with jobs_lock:
                jobs[job_id]["status"] = "running"

            meta = pipeline.load_meta(song_id, output_dir=OUTPUT_DIR)
            song_dir = OUTPUT_DIR / song_id
            # Align against the isolated vocal stem (clean), not the full mix —
            # the full mix's instrumentation throws off forced alignment.
            vocals_path = song_dir / "vocals.wav"
            if not vocals_path.exists():
                vocals_path = Path(meta["audio_path"])
                if not vocals_path.is_absolute():
                    vocals_path = OUTPUT_DIR / vocals_path

            with open(song_dir / "timestamps.json") as f:
                timestamps = pipeline.json.load(f)

            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            result = pipeline.resync_lyrics(vocals_path, timestamps, device)

            with open(song_dir / "timestamps.json", "w") as f:
                pipeline.json.dump(result, f, indent=2)

            meta["lyrics_source"] = meta.get("lyrics_source", "unknown") + "+resynced"
            pipeline.save_meta(song_id, meta, output_dir=OUTPUT_DIR)

            with jobs_lock:
                jobs[job_id]["status"] = "done"
        except Exception as e:
            with jobs_lock:
                jobs[job_id]["status"] = "error"
                jobs[job_id]["error"] = str(e)
        finally:
            with jobs_lock:
                active_jobs.pop(song_id, None)

    threading.Thread(target=run, daemon=True).start()
    return job_id


def _run_export_video_job(
    song_id: str, background: str, font_name: str, font_size: int,
    resolution: tuple[int, int] = (1280, 720),
    intro_path: Path = None,
):
    job_id = uuid.uuid4().hex
    with jobs_lock:
        jobs[job_id] = {"status": "queued", "stage": "Rendering video (0%)", "song_id": song_id, "error": None, "progress": 0}
        active_jobs[song_id] = job_id

    def run():
        try:
            with jobs_lock:
                jobs[job_id]["status"] = "running"

            def progress_cb(frac):
                with jobs_lock:
                    jobs[job_id]["progress"] = round(frac * 100)
                    jobs[job_id]["stage"] = f"Rendering video ({round(frac * 100)}%)"

            karaoke_path = pipeline.export_video(
                song_id, output_dir=OUTPUT_DIR, background=background,
                font_name=font_name, font_size=font_size, resolution=resolution,
                progress_cb=progress_cb,
            )

            if intro_path and intro_path.exists():
                with jobs_lock:
                    jobs[job_id]["stage"] = "Stitching intro video…"
                pipeline.stitch_intro_video(
                    intro_path, karaoke_path, karaoke_path, resolution=resolution
                )
                # Only delete if it's a temp upload (lives in TEMP_DIR), not a
                # permanent file the user pointed to from Video Exports.
                if TEMP_DIR in intro_path.parents:
                    try:
                        intro_path.unlink()
                    except OSError:
                        pass

            with jobs_lock:
                jobs[job_id]["status"] = "done"
        except Exception as e:
            with jobs_lock:
                jobs[job_id]["status"] = "error"
                jobs[job_id]["error"] = str(e)
        finally:
            with jobs_lock:
                active_jobs.pop(song_id, None)

    threading.Thread(target=run, daemon=True).start()
    return job_id


@app.route("/api/upload-video-background", methods=["POST"])
def api_upload_video_background():
    song_id = request.form.get("song_id")
    file = request.files.get("file")
    if not song_id or not file:
        return jsonify({"error": "missing song_id or file"}), 400

    meta = pipeline.load_meta(song_id, output_dir=OUTPUT_DIR)
    if meta is None:
        return jsonify({"error": "unknown song"}), 404

    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png"):
        return jsonify({"error": "file must be a .jpg, .jpeg, or .png image"}), 400

    song_dir = OUTPUT_DIR / song_id
    # Remove any previous background image (regardless of extension) before saving the new one.
    for name in pipeline.VIDEO_BACKGROUND_FILENAMES:
        existing = song_dir / name
        if existing.exists():
            existing.unlink()

    file.save(song_dir / f"video_background{ext}")
    return jsonify({"status": "ok"})


@app.route("/api/preview-video", methods=["POST"])
def api_preview_video():
    data = request.get_json(force=True) or {}
    song_id = data.get("song_id")
    background = data.get("background", "gradient")
    font_name = data.get("font", "Helvetica Neue")
    font_size = int(data.get("font_size", 48))

    if background not in pipeline.VIDEO_BACKGROUNDS:
        return jsonify({"error": f"invalid background, must be one of {pipeline.VIDEO_BACKGROUNDS}"}), 400
    if font_name not in pipeline.VIDEO_FONTS:
        return jsonify({"error": f"invalid font, must be one of {pipeline.VIDEO_FONT_NAMES}"}), 400

    meta = pipeline.load_meta(song_id, output_dir=OUTPUT_DIR)
    if meta is None:
        return jsonify({"error": "unknown song"}), 404

    img = pipeline.render_preview_frame(song_id, output_dir=OUTPUT_DIR, background=background, font_name=font_name, font_size=font_size)

    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return app.response_class(buf.read(), mimetype="image/png")


@app.route("/api/intro-videos")
def api_intro_videos():
    """List video files in the Video Exports folder that can be used as intros."""
    VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".avi"}
    files = []
    for p in sorted(VIDEO_EXPORTS_DIR.iterdir()):
        if p.suffix.lower() in VIDEO_EXTS and p.is_file():
            files.append({"name": p.name, "path": str(p)})
    return jsonify(files)


@app.route("/api/set-intro-by-path", methods=["POST"])
def api_set_intro_by_path():
    """Register a server-side video file as an intro without uploading it."""
    data = request.get_json(force=True) or {}
    path_str = data.get("path", "").strip()
    if not path_str:
        return jsonify({"error": "missing path"}), 400
    p = Path(path_str)
    if not p.exists() or not p.is_file():
        return jsonify({"error": "file not found on server"}), 404
    if p.suffix.lower() not in {".mp4", ".mov", ".m4v", ".mkv", ".avi"}:
        return jsonify({"error": "unsupported video format"}), 400
    temp_id = uuid.uuid4().hex
    temp_uploads[temp_id] = p  # point directly at the file — no copy needed
    return jsonify({"temp_id": temp_id, "filename": p.name})


@app.route("/api/upload-intro-video", methods=["POST"])
def api_upload_intro_video():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "missing file"}), 400
    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".mp4", ".mov", ".m4v", ".mkv", ".avi"):
        return jsonify({"error": "unsupported format — use mp4, mov, m4v, mkv, or avi"}), 400
    temp_id = uuid.uuid4().hex
    dest = TEMP_DIR / f"intro_{temp_id}{ext}"
    file.save(dest)
    temp_uploads[temp_id] = dest
    return jsonify({"temp_id": temp_id, "filename": file.filename})


@app.route("/api/export-video", methods=["POST"])
def api_export_video():
    data = request.get_json(force=True) or {}
    song_id = data.get("song_id")
    background = data.get("background", "gradient")
    font_name = data.get("font", "Helvetica Neue")
    font_size = int(data.get("font_size", 48))
    resolution_key = data.get("resolution", "720p")
    intro_video_id = data.get("intro_video_id")

    resolution = (1920, 1080) if resolution_key == "1080p" else (1280, 720)

    if background not in pipeline.VIDEO_BACKGROUNDS:
        return jsonify({"error": f"invalid background, must be one of {pipeline.VIDEO_BACKGROUNDS}"}), 400
    if font_name not in pipeline.VIDEO_FONTS:
        return jsonify({"error": f"invalid font, must be one of {pipeline.VIDEO_FONT_NAMES}"}), 400

    meta = pipeline.load_meta(song_id, output_dir=OUTPUT_DIR)
    if meta is None:
        return jsonify({"error": "unknown song"}), 404

    intro_path = temp_uploads.pop(intro_video_id, None) if intro_video_id else None

    with jobs_lock:
        if song_id in active_jobs:
            return jsonify({"job_id": active_jobs[song_id], "song_id": song_id})

    job_id = _run_export_video_job(
        song_id, background, font_name, font_size,
        resolution=resolution, intro_path=intro_path,
    )
    return jsonify({"job_id": job_id, "song_id": song_id})


@app.route("/api/process", methods=["POST"])
def api_process():
    data = request.get_json(force=True) or {}
    url = data.get("url")
    title = data.get("title")
    if not url or not title:
        return jsonify({"error": "missing url or title"}), 400

    song_id = pipeline.start_job(url, title, output_dir=OUTPUT_DIR)

    with jobs_lock:
        if song_id in active_jobs:
            return jsonify({"job_id": active_jobs[song_id], "song_id": song_id})

    job_id = _run_job(song_id)
    return jsonify({"job_id": job_id, "song_id": song_id})


@app.route("/api/resume", methods=["POST"])
def api_resume():
    data = request.get_json(force=True) or {}
    song_id = data.get("song_id")
    if not song_id:
        return jsonify({"error": "missing song_id"}), 400

    meta = pipeline.load_meta(song_id, output_dir=OUTPUT_DIR)
    if meta is None:
        return jsonify({"error": "unknown song_id"}), 404

    with jobs_lock:
        if song_id in active_jobs:
            return jsonify({"job_id": active_jobs[song_id], "song_id": song_id})

    job_id = _run_job(song_id)
    return jsonify({"job_id": job_id, "song_id": song_id})


@app.route("/api/transcribe", methods=["POST"])
def api_transcribe():
    data = request.get_json(force=True) or {}
    song_id = data.get("song_id")
    if not song_id:
        return jsonify({"error": "missing song_id"}), 400

    meta = pipeline.load_meta(song_id, output_dir=OUTPUT_DIR)
    if meta is None:
        return jsonify({"error": "unknown song_id"}), 404

    if meta["steps"].get("transcribe") == "done":
        return jsonify({"error": "transcription already done"}), 400

    with jobs_lock:
        if song_id in active_jobs:
            return jsonify({"job_id": active_jobs[song_id], "song_id": song_id})

    job_id = _run_job(song_id)
    return jsonify({"job_id": job_id, "song_id": song_id})


@app.route("/api/resync-lyrics", methods=["POST"])
def api_resync_lyrics():
    data = request.get_json(force=True) or {}
    song_id = data.get("song_id")
    if not song_id:
        return jsonify({"error": "missing song_id"}), 400

    meta = pipeline.load_meta(song_id, output_dir=OUTPUT_DIR)
    if meta is None:
        return jsonify({"error": "unknown song_id"}), 404

    song_dir = OUTPUT_DIR / song_id
    if not (song_dir / "timestamps.json").exists():
        return jsonify({"error": "no lyrics to resync"}), 400

    with jobs_lock:
        if song_id in active_jobs:
            return jsonify({"job_id": active_jobs[song_id], "song_id": song_id})

    job_id = _run_resync_job(song_id)
    return jsonify({"job_id": job_id, "song_id": song_id})


@app.route("/api/adjust-sync", methods=["POST"])
def api_adjust_sync():
    """Apply a global +/- offset (in seconds) to every lyric timestamp and
    persist it -- for manually correcting a song that's consistently early
    or late."""
    data = request.get_json(force=True) or {}
    song_id = data.get("song_id")
    offset = data.get("offset")
    if not song_id or offset is None:
        return jsonify({"error": "missing song_id or offset"}), 400

    try:
        offset = float(offset)
    except (TypeError, ValueError):
        return jsonify({"error": "offset must be a number"}), 400

    meta = pipeline.load_meta(song_id, output_dir=OUTPUT_DIR)
    if meta is None:
        return jsonify({"error": "unknown song_id"}), 404

    song_dir = OUTPUT_DIR / song_id
    timestamps_path = song_dir / "timestamps.json"
    if not timestamps_path.exists():
        return jsonify({"error": "no lyrics to adjust"}), 400

    with open(timestamps_path) as f:
        timestamps = pipeline.json.load(f)

    result = pipeline.apply_sync_offset(timestamps, offset)
    with open(timestamps_path, "w") as f:
        pipeline.json.dump(result, f, indent=2)

    return jsonify({"status": "ok"})


@app.route("/api/retime-lyrics", methods=["POST"])
def api_retime_lyrics():
    """Re-time each lyric line to a user-tapped start time (\"tap to sync\"),
    redistributing word timings within each line proportional to length."""
    data = request.get_json(force=True) or {}
    song_id = data.get("song_id")
    new_starts = data.get("starts")
    if not song_id or new_starts is None:
        return jsonify({"error": "missing song_id or starts"}), 400

    meta = pipeline.load_meta(song_id, output_dir=OUTPUT_DIR)
    if meta is None:
        return jsonify({"error": "unknown song_id"}), 404

    song_dir = OUTPUT_DIR / song_id
    timestamps_path = song_dir / "timestamps.json"
    if not timestamps_path.exists():
        return jsonify({"error": "no lyrics to retime"}), 400

    with open(timestamps_path) as f:
        timestamps = pipeline.json.load(f)

    try:
        result = pipeline.retime_segments(timestamps, [float(s) for s in new_starts])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with open(timestamps_path, "w") as f:
        pipeline.json.dump(result, f, indent=2)

    meta["lyrics_source"] = meta.get("lyrics_source", "unknown") + "+manual"
    pipeline.save_meta(song_id, meta, output_dir=OUTPUT_DIR)

    return jsonify({"status": "ok"})


@app.route("/api/jobs/<job_id>")
def api_job_status(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "unknown job"}), 404
    return jsonify(job)


@app.route("/api/search-lyrics", methods=["POST"])
def api_search_lyrics():
    data = request.get_json(force=True) or {}
    song_id = data.get("song_id")
    query = (data.get("query") or "").strip()
    source = data.get("source") or "musixmatch"
    if not song_id or not query:
        return jsonify({"error": "missing song_id or query"}), 400
    if source not in ("musixmatch", "lrclib"):
        return jsonify({"error": "invalid source"}), 400

    meta = pipeline.load_meta(song_id, output_dir=OUTPUT_DIR)
    if meta is None:
        return jsonify({"error": "unknown song_id"}), 404

    candidates = pipeline.search_lyrics_candidates(query, source=source)
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
    pipeline.save_meta(song_id, meta, output_dir=OUTPUT_DIR)

    return jsonify({"candidates": meta["lyrics_candidates"]})


@app.route("/api/select-lyrics", methods=["POST"])
def api_select_lyrics():
    data = request.get_json(force=True) or {}
    song_id = data.get("song_id")
    candidate_id = data.get("candidate_id")
    if not song_id or candidate_id is None:
        return jsonify({"error": "missing song_id or candidate_id"}), 400

    meta = pipeline.load_meta(song_id, output_dir=OUTPUT_DIR)
    if meta is None:
        return jsonify({"error": "unknown song_id"}), 404

    candidates_full = meta.get("lyrics_candidates_full", [])
    if candidate_id < 0 or candidate_id >= len(candidates_full):
        return jsonify({"error": "invalid candidate_id"}), 400

    candidate = candidates_full[candidate_id]
    resolved = pipeline.get_lyrics_for_candidate(candidate)
    if resolved is None:
        return jsonify({"error": "could not fetch lyrics for this candidate"}), 502

    song_dir = OUTPUT_DIR / song_id
    with open(song_dir / "timestamps.json", "w") as f:
        import json
        json.dump(resolved["timestamps"], f, indent=2)

    meta["steps"]["transcribe"] = "done"
    meta["lyrics_source"] = resolved["lyrics_source"]
    meta.pop("lyrics_candidates", None)
    meta.pop("lyrics_candidates_full", None)
    pipeline.save_meta(song_id, meta, output_dir=OUTPUT_DIR)

    with jobs_lock:
        if song_id in active_jobs:
            return jsonify({"status": "ok", "job_id": active_jobs[song_id], "song_id": song_id})

    job_id = _run_job(song_id)
    return jsonify({"status": "ok", "job_id": job_id, "song_id": song_id})


@app.route("/api/research-lyrics", methods=["POST"])
def api_research_lyrics():
    data = request.get_json(force=True) or {}
    song_id = data.get("song_id")
    if not song_id:
        return jsonify({"error": "missing song_id"}), 400

    meta = pipeline.load_meta(song_id, output_dir=OUTPUT_DIR)
    if meta is None:
        return jsonify({"error": "unknown song_id"}), 404

    with jobs_lock:
        if song_id in active_jobs:
            return jsonify({"job_id": active_jobs[song_id], "song_id": song_id})

    # Reset lyrics-related steps and rerun
    meta["steps"]["check_lyrics"] = "pending"
    meta["steps"]["transcribe"] = "pending"
    meta.pop("lyrics_candidates", None)
    meta.pop("lyrics_candidates_full", None)
    meta.pop("lyrics_source", None)
    pipeline.save_meta(song_id, meta, output_dir=OUTPUT_DIR)

    job_id = _run_job(song_id)
    return jsonify({"job_id": job_id, "song_id": song_id})


@app.route("/api/delete-song", methods=["POST"])
def api_delete_song():
    data = request.get_json(force=True) or {}
    song_id = data.get("song_id")
    if not song_id:
        return jsonify({"error": "missing song_id"}), 400

    song_dir = OUTPUT_DIR / song_id
    if not song_dir.is_dir():
        return jsonify({"error": "song not found"}), 404

    with jobs_lock:
        if song_id in active_jobs:
            return jsonify({"error": "cannot delete while processing"}), 400

    try:
        import shutil
        shutil.rmtree(song_dir)
        return jsonify({"status": "deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/rename-song", methods=["POST"])
def api_rename_song():
    data = request.get_json(force=True) or {}
    song_id = data.get("song_id")
    title = (data.get("title") or "").strip()
    if not song_id or not title:
        return jsonify({"error": "missing song_id or title"}), 400

    meta = pipeline.load_meta(song_id, output_dir=OUTPUT_DIR)
    if meta is None:
        return jsonify({"error": "song not found"}), 404

    meta["title"] = title
    pipeline.save_meta(song_id, meta, output_dir=OUTPUT_DIR)
    return jsonify({"status": "ok", "title": title})


@app.route("/player/<song_id>")
def player(song_id):
    song_dir = OUTPUT_DIR / song_id
    if not song_dir.is_dir():
        return jsonify({"error": "not found"}), 404
    meta = pipeline.load_meta(song_id, output_dir=OUTPUT_DIR)
    if meta is None or meta.get("status") != "done":
        return jsonify({"error": "song not ready"}), 404
    return render_template("player.html", song=meta)


@app.route("/library/<song_id>/<filename>")
def library_file(song_id, filename):
    song_dir = OUTPUT_DIR / song_id
    if not song_dir.is_dir():
        return jsonify({"error": "not found"}), 404
    return send_from_directory(song_dir, filename)


@app.route("/api/quit", methods=["POST"])
def api_quit():
    def shutdown():
        os._exit(0)

    threading.Timer(0.5, shutdown).start()
    return jsonify({"status": "shutting down"})


if __name__ == "__main__":
    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:5050")).start()
    # use_reloader=False: the reloader's module file-watcher crashes when it
    # encounters speechbrain's lazy-loaded k2_fsa module (ModuleNotFoundError: k2)
    app.run(host="0.0.0.0", port=5050, debug=True, use_reloader=False)
