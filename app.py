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

# In-memory job tracker: job_id -> {"status": ..., "stage": ..., "song_id": ..., "error": ...}
jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/library")
def api_library():
    return jsonify(pipeline.list_library(OUTPUT_DIR))


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


@app.route("/api/process", methods=["POST"])
def api_process():
    data = request.get_json(force=True) or {}
    url = data.get("url")
    title = data.get("title")
    if not url:
        return jsonify({"error": "missing url"}), 400

    job_id = uuid.uuid4().hex
    with jobs_lock:
        jobs[job_id] = {"status": "queued", "stage": None, "song_id": None, "error": None}

    def run():
        def on_progress(stage):
            with jobs_lock:
                jobs[job_id]["status"] = "running"
                jobs[job_id]["stage"] = stage

        try:
            song_dir = pipeline.process_song(
                url, title=title, output_dir=OUTPUT_DIR, progress_cb=on_progress
            )
            with jobs_lock:
                jobs[job_id]["status"] = "done"
                jobs[job_id]["song_id"] = song_dir.name
        except Exception as e:
            with jobs_lock:
                jobs[job_id]["status"] = "error"
                jobs[job_id]["error"] = str(e)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"job_id": job_id})


@app.route("/api/jobs/<job_id>")
def api_job_status(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "unknown job"}), 404
    return jsonify(job)


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
    # debug=True spawns a reloader subprocess, which would open the browser twice
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        threading.Timer(1.5, lambda: webbrowser.open("http://localhost:5050")).start()
    app.run(host="0.0.0.0", port=5050, debug=True)
