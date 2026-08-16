# Local Development

**Last updated:** 2026-08-16

## Requirements

- macOS (tested on macOS 14+)
- Python 3.10+
- FFmpeg (must be on PATH)
- Chrome (required for `window.showSaveFilePicker` and Web Audio API)

## Setup

```bash
cd karaoke-app
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running

Double-click `Start Karaoke.command` in Finder, or from the terminal:

```bash
source venv/bin/activate
python app.py
```

The server starts on `http://localhost:5050`.

## Building a macOS app bundle

```bash
bash build_app.sh
```

This produces a `.app` bundle that can be double-clicked without a terminal.

## Key environment notes

- The server binds to `localhost:5050` only — not accessible from other machines
- `output/` is gitignored — song data lives here between runs; do not delete unless intentionally clearing the library
- `Video Exports/` is gitignored — persistent intro videos and default export folder live here
- `TEMP_DIR` (`output/_tmp/`) is used for uploaded intro videos; cleaned up after stitching

## yt-dlp 403 fix

If YouTube downloads fail with 403/SABR errors, the yt-dlp call must include:

```
--extractor-args youtube:player_client=default,mweb
```

This is already applied in `pipeline.py`. If it stops working, check for a newer yt-dlp version or a change in YouTube's client detection.
