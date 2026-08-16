# Architecture Overview

**Last updated:** 2026-08-16

---

## Stack

| Layer | Technology |
|---|---|
| Web server | Flask (Python), Jinja2 templates |
| Frontend | Vanilla JS + CSS (no SPA framework) |
| Cross-page state | `localStorage` / `sessionStorage` |
| Audio download | yt-dlp |
| Vocal separation | Demucs (`htdemucs` model) |
| Transcription / alignment | WhisperX (word-level timestamps) |
| Pitch extraction | librosa (pYIN) |
| Video rendering | PIL/Pillow + numpy, piped to FFmpeg (libx264/aac) |
| Lyrics search | Musixmatch API + LRCLIB fallback |
| File system | `output/<song-id>/` per song; `meta.json` as song state |

---

## File layout

```
karaoke-app/
├── app.py                  Flask server — routing + job tracking only
├── pipeline.py             All processing logic — no Flask imports
├── templates/
│   ├── index.html          Library page
│   └── player.html         Player page
├── static/
│   ├── style.css           Shared CSS variables + library page styles
│   ├── app.js              Library page JS
│   ├── player.css          Player page styles
│   └── player.js           Player page JS
├── output/                 Per-song data (gitignored)
│   └── <song-id>/
│       ├── meta.json
│       ├── audio.m4a
│       ├── vocals.wav
│       ├── accompaniment.wav
│       ├── thumbnail.jpg
│       └── video_background.*  (optional)
├── Video Exports/          Default export folder + persistent intro videos (gitignored)
├── docs/                   Project documentation (this directory)
├── requirements.txt
├── Start Karaoke.command   macOS double-click launcher
└── build_app.sh            macOS .app bundle builder
```

---

## Architecture invariants

- **`pipeline.py` is pure logic** — no Flask imports, no global HTTP state. All side effects go through the `output_dir` parameter.
- **`app.py` is thin** — owns routing, job tracking (in-memory dict + thread), nothing else. All real work delegates to `pipeline`.
- **Processing is idempotent by step** — `process_song` checks `meta["steps"][step] == "done"` before re-running each stage. Resuming a failed job is safe.
- **Always align WhisperX against `vocals.wav`, not the full mix.** See [../decisions/003-align-vocals-stem.md](../decisions/003-align-vocals-stem.md).

---

## Pipeline stages

Processing order for `process_song()`:

1. **download** — yt-dlp downloads audio + thumbnail from YouTube URL
2. **separate** — Demucs splits `audio.m4a` → `vocals.wav` + `accompaniment.wav`
3. **check_lyrics** — Musixmatch richsync → LRCLIB LRC → WhisperX fallback
4. **transcribe** — WhisperX transcription on `vocals.wav`
5. **resync** — WhisperX forced alignment of lyrics text against `vocals.wav`
6. **pitch** — librosa pYIN pitch extraction on `vocals.wav`

Each step is idempotent: skipped if `meta["steps"][step] == "done"`.

---

## API routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/library` | List all songs with step status + active job id |
| GET | `/api/search?q=` | YouTube search |
| POST | `/api/process` | Start full pipeline job for a YouTube URL |
| POST | `/api/resume` | Resume a stalled pipeline job |
| POST | `/api/transcribe` | Re-run WhisperX transcription only |
| POST | `/api/resync-lyrics` | Re-run WhisperX forced alignment on existing lyrics |
| POST | `/api/search-lyrics` | Search Musixmatch + LRCLIB for lyric candidates |
| POST | `/api/select-lyrics` | Apply a chosen lyrics candidate and run alignment |
| POST | `/api/research-lyrics` | Use YouTube title/description to find better lyrics |
| POST | `/api/adjust-sync` | Apply a manual time offset to all timestamps |
| POST | `/api/retime-lyrics` | Retime lyrics segments to new start times |
| POST | `/api/preview-video` | Render a single preview frame (PNG blob URL) |
| POST | `/api/export-video` | Start async video export job |
| POST | `/api/upload-video-background` | Upload a custom background image |
| POST | `/api/delete-song` | Delete a song and its output directory |
| POST | `/api/rename-song` | Rename a song (updates meta.json title) |
| GET | `/api/intro-videos` | List video files in Video Exports/ |
| POST | `/api/set-intro-by-path` | Register a server-side intro path (no upload) |
| POST | `/api/upload-intro-video` | Upload an intro video file to TEMP_DIR |
| GET | `/api/jobs/<job_id>` | Poll job status |
| GET | `/player/<song_id>` | Serve player page |
| GET | `/library/<song_id>/<filename>` | Serve song output files |
| POST | `/api/quit` | Shut down the Flask server |

---

## Key data structures

### `meta.json`
```json
{
  "id": "song-slug",
  "title": "Song Title",
  "source": "https://youtube.com/...",
  "audio_path": "output/song-slug/audio.m4a",
  "thumbnail": "output/song-slug/thumbnail.jpg",
  "steps": { "download": "done", "separate": "done", "..." : "..." },
  "timestamps": { "segments": [...] },
  "lyrics_source": "musixmatch|lrclib|whisperx"
}
```

### Word-level segment
```json
{
  "start": 1.23, "end": 3.45, "text": "Hello world",
  "words": [
    { "word": "Hello", "start": 1.23, "end": 2.1 },
    { "word": "world", "start": 2.2, "end": 3.45 }
  ]
}
```

### Video `lines` (built by `_build_video_lines`)
Pre-split by `_split_long_lines` at 88% frame width.
```json
[
  {
    "start": 1.23, "end": 3.45,
    "words": [{ "text": "Hello", "start": 1.23, "end": 2.1 }]
  }
]
```

---

## Video rendering model

- `_render_frame(bg_img, lines, t, ...)` — stateless; returns a PIL Image
- `_scroll_pos(lines, t)` — returns continuous float P:
  - `int(P)` = base line index at active slot
  - `P - int(P)` = scroll fraction (0 = settled, 0→1 = mid-transition)
  - Uses smoothstep easing over `VIDEO_SCROLL_TRANSITION` (0.6s)
  - See [../decisions/004-continuous-scroll-pos.md](../decisions/004-continuous-scroll-pos.md)
- `_draw_word_fill` — RGBA crop + numpy alpha slicing to clip fill at word boundary

---

## CSS variable system

All colours/radii defined as CSS variables in `style.css :root`, shared across both pages:

```
--bg / --surface / --surface-2   backgrounds
--border                          border colour
--text / --muted                  text colours
--accent / --accent-hover         blue CTA
--danger / --danger-hover         red destructive
--grad                            gradient (badge, now-playing icon)
--shadow / --shadow-hover         card elevation
--radius / --radius-sm            border radii
```
