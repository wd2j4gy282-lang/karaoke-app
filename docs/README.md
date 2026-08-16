# Documentation Index

**Authority order** (highest → lowest):
1. User's latest explicit instruction
2. Approved feature specification under `docs/features/`
3. Accepted decision under `docs/decisions/`
4. Architecture docs under `docs/architecture/`
5. Product docs under `docs/product/`
6. Existing implementation

When sources disagree, identify the conflict and recommend a resolution rather than silently picking one.

---

## Documents

### Product

| Document | Use for |
|---|---|
| [product/vision.md](product/vision.md) | What the app is, who it's for, guiding principles |
| [product/users.md](product/users.md) | User profile and context of use |
| [product/roadmap.md](product/roadmap.md) | Current priorities and backlog |

### Architecture

| Document | Use for |
|---|---|
| [architecture/overview.md](architecture/overview.md) | Stack, file layout, API routes, data structures |

### Decisions

| Document | Decision |
|---|---|
| [decisions/001-vanilla-js-no-framework.md](decisions/001-vanilla-js-no-framework.md) | Vanilla JS over a SPA framework |
| [decisions/002-word-level-timestamps.md](decisions/002-word-level-timestamps.md) | Word-level timing as source of truth |
| [decisions/003-align-vocals-stem.md](decisions/003-align-vocals-stem.md) | WhisperX aligned against vocals.wav, not full mix |
| [decisions/004-continuous-scroll-pos.md](decisions/004-continuous-scroll-pos.md) | Continuous float scroll model (not event-driven snapping) |
| [decisions/005-save-dialog-before-render.md](decisions/005-save-dialog-before-render.md) | Save dialog fires before render starts |
| [decisions/006-forward-only-video-display.md](decisions/006-forward-only-video-display.md) | No already-sung lines in video export |
| [decisions/007-uniform-font-size.md](decisions/007-uniform-font-size.md) | Uniform font size for all visible lines in video |
| [decisions/008-light-theme-only.md](decisions/008-light-theme-only.md) | Light theme, no dark-mode toggle |

### Features

| Document | Status |
|---|---|
| [features/youtube-search-and-processing.md](features/youtube-search-and-processing.md) | Implemented |
| [features/karaoke-player.md](features/karaoke-player.md) | Implemented |
| [features/video-export.md](features/video-export.md) | Implemented |

### Operations

| Document | Use for |
|---|---|
| [operations/local-dev.md](operations/local-dev.md) | Running the app locally on macOS |

### Templates

| Document | Use for |
|---|---|
| [templates/feature-template.md](templates/feature-template.md) | Starting a new feature specification |
| [templates/decision-template.md](templates/decision-template.md) | Recording an architectural or product decision |

### Workflow

| Document | Use for |
|---|---|
| [ai-workflow.md](ai-workflow.md) | Planning/implementation surface operating model |

---

## Implementation history

See [../PROGRESS.md](../PROGRESS.md) for a dated log of everything that shipped.
