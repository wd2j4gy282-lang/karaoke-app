# YouTube Search and Processing Pipeline

**Status:** Implemented
**System area:** Library page, backend pipeline
**Primary user:** Single local user
**Last updated:** 2026-08-16
**Related documents:** [architecture/overview.md](../architecture/overview.md), [decisions/003-align-vocals-stem.md](../decisions/003-align-vocals-stem.md)

---

## 1. Purpose

Allow the user to find a song on YouTube, process it through the full audio pipeline, and add it to their local library.

## 2. Problem

Creating a karaoke track from a YouTube video requires downloading audio, isolating vocals, obtaining lyrics, and aligning them word-by-word. This feature automates that entire pipeline.

## 3. Scope

- YouTube search by query string
- Audio download via yt-dlp
- Vocal separation via Demucs
- Lyrics acquisition: Musixmatch richsync → LRCLIB LRC → WhisperX transcription fallback
- Word-level forced alignment via WhisperX on `vocals.wav`
- Pitch extraction via librosa pYIN
- Song stored in `output/<song-id>/` with `meta.json` tracking step completion

## 4. Out of scope

- Non-YouTube audio sources
- Batch processing of multiple songs simultaneously
- Automatic retry on network failure (user can resume manually)

## 5. User journey

1. User types a search query into the "Add a song" form on the library page
2. Results appear as YouTube video cards (title, thumbnail, channel, duration)
3. User clicks a result card
4. Processing starts: a progress indicator shows the current pipeline step
5. When complete, the song appears in the library

## 6. Functional requirements

- **FR-01** Search returns up to 10 YouTube video results matching the query
- **FR-02** Each result shows: title, thumbnail, channel name, duration
- **FR-03** Clicking a result starts the pipeline and adds the song to the library in a pending state
- **FR-04** Pipeline steps run in order: download → separate → check_lyrics → transcribe → resync → pitch
- **FR-05** Each step is idempotent: skipped if already marked done in `meta.json`
- **FR-06** A failed job can be resumed via "Resume" action on the song card
- **FR-07** WhisperX transcription and alignment run against `vocals.wav`, not `audio.m4a`
- **FR-08** yt-dlp uses `--extractor-args youtube:player_client=default,mweb` to avoid 403/SABR errors

## 7. Error states

- Download failure (403, network error) — song card shows error state; user can Resume
- Demucs failure — same error state + Resume
- WhisperX failure — same; lyrics may fall back to Musixmatch or LRCLIB if available

## 8. Data requirements

`meta.json` fields set by this pipeline:
- `id`, `title`, `source`, `audio_path`, `thumbnail`
- `steps`: one key per pipeline step, value `"done"` when complete
- `timestamps.segments`: word-level timing data
- `lyrics_source`: `"musixmatch"` | `"lrclib"` | `"whisperx"`

## 9. Acceptance criteria

- **AC-01** A search query returns results within 5 seconds
- **AC-02** A processed song appears in the library with all step badges marked done
- **AC-03** Restarting the server and resuming a mid-processing song continues from the last completed step, not from scratch
- **AC-04** `vocals.wav` exists in the song's output directory after the separate step
- **AC-05** `meta["timestamps"]["segments"][0]["words"]` contains at least one entry with `word`, `start`, `end` keys after the resync step
