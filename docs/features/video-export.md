# Video Export

**Status:** Implemented
**System area:** Library page export modal, backend pipeline
**Primary user:** Single local user
**Last updated:** 2026-08-16
**Related documents:**
- [decisions/004-continuous-scroll-pos.md](../decisions/004-continuous-scroll-pos.md)
- [decisions/005-save-dialog-before-render.md](../decisions/005-save-dialog-before-render.md)
- [decisions/006-forward-only-video-display.md](../decisions/006-forward-only-video-display.md)
- [decisions/007-uniform-font-size.md](../decisions/007-uniform-font-size.md)

---

## 1. Purpose

Export a processed song as a karaoke MP4 video with smooth lyric scroll, syllable-level word fill highlight, and optional intro video prepended.

## 2. Scope

- Export modal on the library page (triggered from a song card)
- Save location selected before rendering (`window.showSaveFilePicker`)
- Async render job (PIL/Pillow + numpy piped to FFmpeg)
- Resolution: 720p (1280×720) or 1080p (1920×1080)
- Lyric display: current line + next 2–3 lines, smooth upward scroll, uniform font size
- Syllable fill: left-to-right highlight on the active word
- Background: thumbnail (default) or user-uploaded image
- Intro video: optional MP4/MOV prepended via FFmpeg concat (no re-encode of karaoke portion)
- Custom background image upload

## 3. Out of scope

- Exporting audio only
- Batch export of multiple songs
- Subtitle/SRT output
- Uploading directly to YouTube

## 4. User journey

1. User clicks "Export Video" on a song card in the library
2. Export modal opens: preview frame thumbnail, font/background/resolution controls, intro video selector
3. User optionally selects resolution (720p default) and an intro video from the dropdown (populated from `Video Exports/` folder)
4. User clicks "Export" → save dialog opens immediately (`window.showSaveFilePicker`)
5. User picks a save location → render job starts on the backend
6. Progress indicator polls `/api/jobs/<job_id>`
7. Backend renders frame-by-frame and pipes to FFmpeg
8. If an intro video is selected, it is re-encoded to match specs and concatenated before the karaoke video via FFmpeg concat demuxer
9. Output file is written to the user-chosen path
10. Modal shows "Done" on completion

## 5. Functional requirements

### Rendering
- **FR-01** `_render_frame(bg_img, lines, t, ...)` is stateless — given the same inputs it always returns the same PIL Image
- **FR-02** `_scroll_pos(lines, t)` returns a continuous float P; `int(P)` = base line index; `P - int(P)` = scroll fraction using smoothstep easing over 0.6s
- **FR-03** Visible range is `range(0, VIDEO_VISIBLE_LINES)` — no already-sung lines
- **FR-04** All visible lines render at the same font size (Helvetica Neue Bold, index 1 in the TTC)
- **FR-05** Long lines are word-wrapped by `_split_long_lines` at 88% of frame width; called after font is resolved
- **FR-06** `_draw_word_fill` clips the fill colour at the word boundary using RGBA crop + numpy alpha slicing
- **FR-07** Countdown dots (ellipsis) for gaps between lyrics appear above the next lyric line, not in place of it
- **FR-08** Background defaults to the song's thumbnail; user may upload a custom image

### Export pipeline
- **FR-09** Save dialog fires before the backend job starts; `AbortError` cancels with no render
- **FR-10** Default save folder persisted in IndexedDB (`karaoke-fs`) across sessions
- **FR-11** Resolution: 720p → 1280×720; 1080p → 1920×1080
- **FR-12** Export job runs in a background thread; progress polled via `/api/jobs/<job_id>`

### Intro stitching
- **FR-13** Intro videos in `Video Exports/` folder are listed by `/api/intro-videos` and shown in a dropdown
- **FR-14** User may also upload an intro video via file picker (saved to TEMP_DIR)
- **FR-15** `stitch_intro_video` re-encodes the intro to match karaoke specs (resolution, fps, yuv420p, aac), then concatenates via FFmpeg concat demuxer — karaoke portion is not re-encoded
- **FR-16** Intro files in `Video Exports/` are never deleted after stitching; temp uploads are cleaned up

## 6. Data requirements

- Reads `meta.json` timestamps for lyric line timing
- Reads `vocals.wav` path (derived from `output_dir`, not `audio_path`)
- Background image: `video_background.*` in `output_dir` if uploaded, else `thumbnail.jpg`
- Intro video: path from `Video Exports/` or TEMP_DIR

## 7. Error states

- Render failure — job status shows error message; user can retry
- Intro stitch failure — job status shows "intro video failed"; karaoke portion is not affected if stitch fails after export
- `AbortError` on save dialog — modal stays open, no job submitted

## 8. Acceptance criteria

- **AC-01** Lyrics scroll smoothly upward with no freeze or snap during export
- **AC-02** The active line stays centred in the frame while being sung (not one slot above)
- **AC-03** All visible lines render at identical font size during scroll transitions
- **AC-04** No already-sung lines appear above the active slot
- **AC-05** Syllable fill advances left-to-right within the active word proportional to elapsed word fraction
- **AC-06** Countdown dots appear above the next lyric line during gaps, not replacing it
- **AC-07** 720p export produces a 1280×720 MP4; 1080p produces 1920×1080
- **AC-08** Selecting an intro from the dropdown and exporting produces a video that starts with the intro and continues with the karaoke
- **AC-09** The `Video Exports/OG Karaoke Intro.mp4` file is not deleted after stitching
- **AC-10** Cancelling the save dialog produces no render job and no backend side effects
