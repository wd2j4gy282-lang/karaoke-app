# 001 — Vanilla JS, no SPA framework

**Status:** Accepted

## Context

The app has two pages: a library page and a player page. Cross-page state (Now Playing bar) is handled via `localStorage`/`sessionStorage`.

## Decision

Use vanilla JavaScript and CSS. No React, Vue, Svelte, or any SPA framework.

## Alternatives considered

- React — would require a build step, npm ecosystem, and component architecture for a two-page app
- Vue — same overhead concern

## Consequences

- No build tooling needed; the server just serves static files
- State bridging between pages is explicit (`localStorage`/`sessionStorage`) rather than a router
- Adding complex interactive UI in future would require either a migration or creative vanilla JS
- Acceptable at the current scale and for a single-user local tool

## Related

- [docs/architecture/overview.md](../architecture/overview.md)
