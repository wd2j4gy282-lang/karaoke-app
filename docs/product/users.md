# Users

**Last updated:** 2026-08-16

## Primary user

**A single person** running the app locally on their Mac.

- Comfortable with macOS; does not need to be a developer
- Launches via `Start Karaoke.command` (double-click)
- Builds a personal song library over time
- Goal: sing along to songs they like, and optionally export a video for YouTube

## Context of use

- Desktop only (macOS)
- Chrome browser (required for `window.showSaveFilePicker` and Web Audio API features)
- Local network only — the Flask server binds to localhost
- No authentication or session management needed

## Workflow

1. Search for a song on YouTube
2. Process it (download → separate → transcribe → align → pitch)
3. Open the player: sing along, adjust sync if needed
4. Export a karaoke video (optionally with an intro clip)
5. Optionally: rename the song in the library

## What the user does not need

- Account creation or login
- Sharing with others from within the app
- Mobile or tablet access
- Offline YouTube access (downloading is part of the pipeline, not a workaround)
