# 004 — Continuous float scroll position model

**Status:** Accepted

## Context

The video export needs to smoothly scroll lyrics lines upward as the song progresses. An earlier implementation used `_scroll_state()` which returned a base line index and a scroll fraction separately. The fraction was clamped with `min(elapsed/window, 1.0)`, which permanently returned 1.0 after the 0.6s transition window — keeping the active line one slot above center for its entire sung duration.

## Decision

Replace `_scroll_state` with `_scroll_pos(lines, t) -> float` that returns a single continuous float P:

- `int(P)` = base line index (the line at the active slot)
- `P - int(P)` = scroll fraction (0.0 = settled, 0→1 = mid-transition)
- Returns an exact integer (as float) once a line is settled — scroll_frac is exactly 0
- Uses smoothstep easing over `VIDEO_SCROLL_TRANSITION` (0.6s)

## Alternatives considered

- Event-driven snapping — jump immediately to the next line on lyric boundary. Visually jarring.
- Fixing the clamp bug in `_scroll_state` — possible, but the unified float model is cleaner and easier to reason about.

## Consequences

- Scroll animation is smooth and mathematically correct
- `_render_frame` is simpler: one float drives the entire layout calculation
- The model is easy to test with specific time values without needing to render a frame

## Lessons learned

The clamping bug (lesson 2 in CLAUDE.md): `min(elapsed/window, 1.0)` looks safe but is wrong here. After the window ends, the fraction stays 1.0, which looks like "lines moved up and froze." The fix is `if elapsed < window: compute fraction, else: fraction = 0 (settled)`.

## Related

- CLAUDE.md (video rendering invariants)
- [docs/features/video-export.md](../features/video-export.md)
