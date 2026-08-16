# Product Vision

**Last updated:** 2026-08-16

## Purpose

A personal, local-first karaoke tool that turns any YouTube video into a singable karaoke track and a shareable karaoke video — automatically.

## Target user

A single user running the app on their own Mac. No accounts, no cloud, no multi-tenancy.

## Problem being solved

Creating a karaoke version of a song typically requires either paying for a service that may not have the song, or manually editing audio and lyrics. This app automates the full pipeline: download the audio, isolate the vocals, align lyrics word-by-word, and render a karaoke video — in one click.

## Value proposition

- **Any song on YouTube** → karaoke video, in one workflow
- **Word-level lyric sync** — syllable-by-syllable highlight, not just line-by-line
- **No internet dependency at playback time** — all output is local files
- **Exportable video** — rendered karaoke MP4 suitable for YouTube or personal use

## Product principles

1. **Local first.** No user accounts, no uploads to third-party services, no cloud dependency beyond YouTube itself.
2. **Single-user simplicity.** No multi-tenancy, no permissions system, no sharing features. Build for one person's workflow.
3. **Quality over speed.** The pipeline takes minutes; that is acceptable. The output (lyric timing, video smoothness) must be correct.
4. **Minimal UI surface.** Two pages: library and player. No SPA framework. Add UI only when a real need is established.

## Strategic goals

- Produce karaoke videos good enough to publish on YouTube
- Support recurring use: a growing personal song library
- Keep the tool runnable with a double-click on macOS

## Explicitly out of scope

- Multi-user or shared access
- Mobile app or responsive mobile layout (player layout is desktop-optimised)
- Cloud hosting or SaaS deployment
- Real-time online multiplayer karaoke
- Non-YouTube audio sources (Spotify, local files) — not currently planned
