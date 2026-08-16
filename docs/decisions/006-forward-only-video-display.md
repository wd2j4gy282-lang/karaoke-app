# 006 — No already-sung lines in video export

**Status:** Accepted

## Context

The video renders a sliding window of lyric lines. The question was whether to show lines that have already been sung (scrolling up and out of frame) or only the current and upcoming lines.

## Decision

Visible range is `range(0, VIDEO_VISIBLE_LINES)` — slot 0 is the active line, slots 1+ are upcoming. No negative slots (already-sung lines) are rendered.

## Alternatives considered

- Show 2 already-sung lines above active — briefly implemented with `range(-2, VIDEO_VISIBLE_LINES)`. User explicitly rejected it; preferred the clean forward-only look.

## Consequences

- Cleaner, less cluttered video frame
- Singer focuses on current and upcoming lines only
- Already-sung lines disappear as they scroll out; no visual confirmation of what was sung

## Related

- [docs/features/video-export.md](../features/video-export.md)
- CLAUDE.md (video rendering invariants)
