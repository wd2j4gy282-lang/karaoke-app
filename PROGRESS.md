# PROGRESS.md — changelog of what actually shipped

## 2026-08-01

**Video export — uniform font size + no sung lines**
Removed `VIDEO_UPCOMING_FONT_SCALE` (was 0.78). All visible lines now render at the same font size. Visible range changed from `range(-2, VIDEO_VISIBLE_LINES)` to `range(0, VIDEO_VISIBLE_LINES)` — already-sung lines no longer appear above the active slot.

**Video export — smooth scroll fix (scroll_frac clamping bug)**
Replaced `_scroll_state` with `_scroll_pos`. The old function clamped `scroll_frac` to 1.0 indefinitely after the 0.6s transition window, leaving the active line one slot above center for its entire duration. `_scroll_pos` returns a precise continuous float (whole number once settled) so `scroll_frac` is exactly 0 during stable playback.

---

## Pre-2026-08-01 (initial build + earlier session)

**Initial commit**
YouTube search (yt-dlp), Demucs vocal separation, WhisperX word-level transcription + forced alignment, librosa pitch extraction, Flask + Jinja2 app, vanilla JS/CSS player page with visualizer, seek bar, pitch meter, sync offset controls, and in-memory job tracking.

**Light "Apple store" UI theme**
Full CSS variable overhaul: white background, gradient badge (mic SVG icon), card hover lift (`translateY(-2px)`), frosted Now Playing bar (`backdrop-filter: saturate(180%) blur(20px)`), modal blur overlay. Both `style.css` and `player.css` updated.

**Lyrics search improvements**
Enter key now submits search (factored into `runLyricsSearch()`). Results list scrollable up to 15 candidates (was 5). `search_musixmatch` and `search_lyrics_candidates` both updated to `page_size: 15` / `[:15]`.

**Video export — save dialog before rendering**
`window.showSaveFilePicker` called as the first action in the export button handler. User picks save location before the backend renders. `AbortError` cancels cleanly with no render. IndexedDB (`FS_DB_NAME = "karaoke-fs"`) persists the default export folder handle across sessions. Export modal has a "Set default folder…" button.

**Video export — word-wrap long lyric lines**
`_split_long_lines(lines, font, max_width)` added to `pipeline.py`. Greedy word-fit at `w * 0.88` frame width. Called in both `render_preview_frame` and `export_video` after font is resolved. Last sub-line of a wrapped segment inherits the original segment's end time.

**Video export — left-to-right syllable fill**
`_draw_word_fill(frame, x, cy, text, font, fill_px)` renders the active colour using a small RGBA crop + numpy alpha channel slicing to clip at the fill boundary. `_draw_lyric_line` updated to call it for the active word fraction. Replaces whole-word flash highlight.

**Video export — smooth scrolling (transition extended)**
`VIDEO_SCROLL_TRANSITION` raised from 0.4s to 0.6s. Smoothstep easing added in `_scroll_state` (since replaced by `_scroll_pos`).

**Video rendering — past-lines visibility (later reverted to forward-only)**
Briefly extended visible range to `range(-2, VIDEO_VISIBLE_LINES)` to show 2 sung lines above active. User preferred forward-only display; reverted to `range(0, VIDEO_VISIBLE_LINES)`.

**Helvetica Neue Bold for video**
`VIDEO_FONTS["Helvetica Neue"]` changed to tuple `("/System/Library/Fonts/HelveticaNeue.ttc", 1)` (index 1 = Bold). `_video_font()` updated to unpack tuple entries.
