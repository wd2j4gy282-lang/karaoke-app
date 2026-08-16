# 005 — Save dialog fires before render starts

**Status:** Accepted

## Context

Video export is a long-running operation (minutes). There was a choice: let the user start the render and then pick a save location when it's done, or ask for the save location first.

## Decision

`window.showSaveFilePicker` is called as the very first action in the export button handler. The backend render only starts if the user confirms a save path. If the user cancels (`AbortError`), no render job is submitted.

## Alternatives considered

- Save dialog after render — user waits minutes then picks a location. If they cancel, the render was wasted.
- Auto-save to a default folder — less control; user may not want the file there.

## Consequences

- Chrome only: `window.showSaveFilePicker` is not available in Safari or Firefox
- Default folder handle is persisted in IndexedDB (`karaoke-fs` db) across sessions
- The "Set default folder…" button in the export modal pre-selects the IndexedDB handle for future exports

## Related

- [docs/features/video-export.md](../features/video-export.md)
