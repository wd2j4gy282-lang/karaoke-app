# 007 — Uniform font size for all visible lines in video

**Status:** Accepted

## Context

An earlier implementation used `VIDEO_UPCOMING_FONT_SCALE = 0.78` to render upcoming (non-active) lines at 78% of the active line's font size. This caused a jarring visual jump: as a line transitioned from upcoming to active during scroll, it suddenly grew 28% larger.

## Decision

Remove `VIDEO_UPCOMING_FONT_SCALE` entirely. All visible lines render at the same `font_size`. The active line is distinguished by its lyric fill highlight colour, not by size.

## Alternatives considered

- Keeping the size difference but animating the scale transition — adds complexity; the uniform approach is simpler and cleaner
- Smaller upcoming lines — rejected because the transition looked unnatural

## Consequences

- Smooth, uniform layout during scroll
- Active line distinction relies entirely on the syllable fill colour (accent colour left-to-right progress)
- Slightly less visual hierarchy between active and upcoming lines — acceptable given the fill colour provides enough differentiation

## Related

- [docs/features/video-export.md](../features/video-export.md)
- CLAUDE.md (video rendering invariants)
