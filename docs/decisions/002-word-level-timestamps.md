# 002 — Word-level timestamps as source of truth

**Status:** Accepted

## Context

WhisperX produces word-level timing data. An earlier consideration was whether to store and operate on line-level timing instead, which is simpler.

## Decision

All downstream features operate on `timestamps["segments"][*]["words"]` — word-level timestamps. Line-level timing is derived from word timing when needed, never stored as primary truth.

## Alternatives considered

- Line-level timestamps — simpler data model, but loses the ability to do per-syllable karaoke fill highlight and word-level sync adjustment

## Consequences

- Enables syllable-by-syllable fill highlight in both the player and video export
- Enables tap-to-seek at word granularity
- Pitch needle can be synced per word
- Slightly more complex data handling, but WhisperX gives it for free

## Related

- [docs/features/karaoke-player.md](../features/karaoke-player.md)
- [docs/features/video-export.md](../features/video-export.md)
