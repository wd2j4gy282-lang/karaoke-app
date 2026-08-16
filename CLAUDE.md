# CLAUDE.md — ground rules, architecture, lessons learned

## Required reading before any task

1. `docs/README.md` — documentation index and authority order
2. `docs/ai-workflow.md` — planning/implementation surface operating model
3. The relevant feature spec under `docs/features/` (if implementing a feature)
4. Linked architecture and decision documents for that feature

## How we work across surfaces

Four surfaces, one job each:
- **Planning chat** — brainstorm, research, pressure-test, lock decisions. Nothing is real until it's written into a canonical doc.
- **Canonical docs** (`docs/` tree, this file, PROGRESS.md) — the actual source of truth. Win on any conflict.
- **Claude Code** — implementation. Reads canonical docs before any task. Holds commits locally and reports back before pushing. Never pushes without explicit go-ahead.

The loop: decision locked in chat → scoped handover pasted to Code → Code builds/holds → reviewed → explicit go-ahead → push → confirm live → PROGRESS.md updated.

**Never mix a doc-only handover with a build handover.** Doc changes are always safe to apply immediately; build handovers need review discipline first.

---

## Stack

| Layer | Technology |
|---|---|
| Web server | Flask (Python), Jinja2 templates |
| Frontend | Vanilla JS + CSS (no SPA framework); `localStorage`/`sessionStorage` for cross-page state |
| Audio download | yt-dlp |
| Vocal separation | Demucs (`htdemucs` model) |
| Transcription / alignment | WhisperX (word-level timestamps) |
| Pitch extraction | librosa (pYIN) |
| Video rendering | PIL/Pillow + numpy, piped to FFmpeg (libx264/aac) |
| Lyrics search | Musixmatch API + LRCLIB fallback |
| File system | `output/<song-id>/` per song; `meta.json` as song state |

---

## Architecture invariants

- **`pipeline.py` is pure logic** — no Flask imports, no global HTTP state. All side effects go through the `output_dir` parameter.
- **`app.py` is thin** — it owns routing, job tracking (in-memory dict + thread), and nothing else. All real work is delegated to `pipeline`.
- **Processing is idempotent by step** — `process_song` checks `meta["steps"][step] == "done"` before re-running each stage. Resuming a failed job is safe.
- **Always align WhisperX against `vocals.wav`, not the full mix.** The full mix's instrumentation throws off forced alignment, causing lyric sync drift.
- **yt-dlp 403 fix** — if YouTube downloads fail with 403/SABR errors, add `--extractor-args youtube:player_client=default,mweb` to the yt-dlp call.

---

## Video rendering invariants

- `_render_frame` is stateless — takes `(bg_img, lines, t, ...)` and returns a PIL Image. Safe to call from both preview and export paths.
- `_scroll_pos(lines, t)` returns a continuous float P where `int(P)` = base line index, `P - int(P)` = scroll fraction. Do **not** clamp `scroll_frac` to 1.0 indefinitely — that was the bug that left the active line one slot above center for the entire time it was being sung.
- `_split_long_lines` must be called **after** the font is resolved (font size affects word widths). Word-wrap threshold is `w * 0.88`.
- `_draw_word_fill` uses a small RGBA crop + numpy alpha slicing to clip the fill at the word boundary — avoids full-frame allocation.

---

## Lessons learned

1. **Investigate before fixing.** Read the real logic/data before deciding what's wrong. Especially for rendering bugs — trace the math through specific time values rather than guessing from symptoms.
2. **Scroll fraction clamping is a classic off-by-one.** `min(elapsed/window, 1.0)` permanently returns 1.0 after the window, which looks like "lines moved up and froze." The fix is an explicit `if elapsed < window` guard before computing the fraction.
3. **Self-audit is never sufficient for visual bugs.** A render that "looks right in code" needs an actual exported video checked by the user before the fix is confirmed.
4. **Verify the right audio path for WhisperX.** After Demucs separation exists, always use `vocals.wav` — the meta `audio_path` still points to the original download.
