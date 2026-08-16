# Karaoke Player

**Status:** Implemented
**System area:** Player page
**Primary user:** Single local user
**Last updated:** 2026-08-16
**Related documents:** [architecture/overview.md](../architecture/overview.md), [decisions/002-word-level-timestamps.md](../decisions/002-word-level-timestamps.md)

---

## 1. Purpose

Let the user sing along to a processed song with word-by-word lyric synchronisation, real-time pitch feedback, and sync adjustment tools.

## 2. Scope

- Audio playback via Web Audio API
- Word-by-word karaoke lyric display with syllable fill highlight
- Real-time pitch meter (via microphone)
- Seek bar (draggable)
- Waveform visualizer (FFT)
- Sync offset adjustment (slider + tap-sync)
- Karaoke score tracking
- Song title rename (in-place edit)

## 3. Out of scope

- Recording the user's voice
- Saving score history
- Multi-player / duet mode

## 4. User journey

1. User opens a song from the library (clicks "Open" or clicks the Now Playing bar)
2. Player page loads with audio, lyrics, visualizer ready
3. User presses Play
4. Lyrics scroll automatically; current word is highlighted with a left-to-right fill
5. Pitch meter shows whether they're in tune
6. If lyrics are off, user adjusts via the sync offset slider or tap-sync
7. User can rename the song title by clicking the pencil icon or double-clicking the title

## 5. Functional requirements

- **FR-01** Audio plays via `<audio>` element controlled by Web Audio API
- **FR-02** Lyrics display updates in real time based on audio `currentTime`
- **FR-03** Active word is highlighted with a left-to-right colour fill proportional to elapsed word duration
- **FR-04** Already-sung words are shown in accent colour; upcoming words are muted
- **FR-05** Clicking a word in the lyrics panel seeks to that word's start time
- **FR-06** Visualizer renders an FFT waveform on a `<canvas>` element using Web Audio API
- **FR-07** Seek bar updates continuously during playback; dragging it seeks the audio
- **FR-08** Pitch meter reads microphone input, detects fundamental frequency, and shows needle position relative to the target note (in-tune / flat / sharp / far)
- **FR-09** Sync offset slider shifts all lyric timestamps by ±N seconds; applied in real time
- **FR-10** Tap-sync: user taps a button on the beat; the offset is computed from the delta to the nearest expected lyric boundary
- **FR-11** Score increments when the user's pitch is within threshold of the target note during a word
- **FR-12** Song title is editable in-place: pencil button or double-click opens an input; Enter/blur saves; Escape cancels; save calls `POST /api/rename-song`
- **FR-13** Now Playing bar in the library page (persisted via `sessionStorage`) reflects the currently open song

## 6. Data requirements

- Reads `timestamps.segments[*].words` from `meta.json` (served via the player page template or `/api/library`)
- Pitch data (librosa output) served as part of the song data
- Sync offset stored in memory during session (not persisted to `meta.json`)

## 7. Error and empty states

- If `timestamps` is empty: lyrics panel shows a "No lyrics" message
- If microphone access is denied: pitch meter shows "Mic unavailable"

## 8. Acceptance criteria

- **AC-01** Active word fill advances smoothly left-to-right during playback
- **AC-02** Seeking via the seek bar or lyrics click updates both audio position and lyric highlight immediately
- **AC-03** Sync offset slider shifts lyric timing without reloading the page
- **AC-04** Renaming the title updates both the player page heading and the library card name
- **AC-05** Pitch needle responds within 100ms of the user singing a note
