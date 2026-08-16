# 003 — WhisperX aligned against vocals.wav, not the full mix

**Status:** Accepted

## Context

WhisperX forced alignment requires an audio file. The pipeline has both the original `audio.m4a` and the Demucs-separated `vocals.wav`.

## Decision

Always run WhisperX transcription and forced alignment against `vocals.wav`, not `audio.m4a`.

## Alternatives considered

- Full mix (`audio.m4a`) — available earlier in the pipeline, no Demucs dependency, but causes alignment drift

## Consequences

- Forced alignment quality is significantly better: instrumentation in the full mix confuses the aligner, causing lyric sync drift
- Demucs separation (`separate` step) must complete before any transcription/alignment step
- `meta["audio_path"]` still points to `audio.m4a`; code must explicitly resolve `vocals.wav` from `output_dir`, not from `audio_path`

## Lessons learned

This was discovered during debugging when alignment on the full mix produced visibly drifted lyrics. See lesson 4 in CLAUDE.md.

## Related

- CLAUDE.md (architecture invariants)
- [docs/features/youtube-search-and-processing.md](../features/youtube-search-and-processing.md)
