# 008 — Light theme only, no dark-mode toggle

**Status:** Accepted

## Context

The app uses an "Apple store" aesthetic: white background, gradient badge, card hover lift, frosted Now Playing bar.

## Decision

Single light theme. No dark-mode toggle. No `prefers-color-scheme` media query support.

## Alternatives considered

- Dark/light toggle — adds toggle state, duplicated CSS variable definitions, and a `localStorage` preference. For a single-user local tool with an intentional white aesthetic, this is unnecessary complexity.

## Consequences

- CSS variable system is simpler: one set of values in `:root`
- Users who prefer dark mode cannot change it without editing CSS
- Acceptable for a personal local tool with a defined aesthetic intent

## Related

- [docs/architecture/overview.md](../architecture/overview.md)
