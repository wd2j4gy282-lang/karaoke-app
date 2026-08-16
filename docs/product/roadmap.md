# Roadmap

**Last updated:** 2026-08-16

> Roadmap placement is an intention, not an implementation specification.
> Before implementation, create or update an approved feature spec under `docs/features/`.

---

## Now (shipped)

| Feature | Notes |
|---|---|
| YouTube search + audio download | yt-dlp, handles 403/SABR via `player_client=default,mweb` |
| Demucs vocal separation | `htdemucs` model → `vocals.wav` + `accompaniment.wav` |
| WhisperX word-level transcription + alignment | Aligned against `vocals.wav`, not full mix |
| Pitch extraction | librosa pYIN on `vocals.wav` |
| Lyrics search | Musixmatch richsync → LRCLIB LRC → WhisperX fallback |
| Library page | Song cards, step status checklist, search, add-song flow |
| Player page | Visualizer, seek bar, word-by-word lyrics, pitch meter, sync tools |
| Song rename | Rename in library and on player page title |
| Video export | Smooth scroll, uniform font, syllable fill, word-wrap, save dialog |
| Video export — resolution | 720p / 1080p selector |
| Video export — intro stitching | Select from Video Exports folder or upload; FFmpeg concat |

---

## Next (queued / agreed)

| Feature | Notes |
|---|---|
| Verify intro stitching end-to-end | Needs server restart + test export with OG Karaoke Intro.mp4 |
| Verify ellipsis + lyric coexist | Countdown dots should appear above the next lyric, not replace it |

---

## Backlog (no timeline)

| Feature | Notes |
|---|---|
| Custom thumbnail upload for song card | |
| Karaoke score display tuning | Current scoring is basic |
| Font / size / background controls in export UI | Currently hardcoded to Helvetica Neue Bold |
| Mobile-friendly player layout | Low priority — desktop only per vision |

---

## Decided against

| Item | Reason |
|---|---|
| Dark mode toggle | Adds CSS complexity; white background is the intended aesthetic |
| React / Vue / SPA framework | Build tooling overhead, no real benefit for a two-page app |
| Line-level timestamps | WhisperX gives word-level; downgrading loses karaoke fill |
| Scroll transition > 0.6s | Tested — feels sluggish; 0.6s + smoothstep is right |
| Showing already-sung lines | User explicitly preferred clean forward-only display |
