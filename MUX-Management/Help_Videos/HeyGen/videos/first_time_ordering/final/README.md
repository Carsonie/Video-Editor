# final/ — Finished Deliverable

## What this folder is
This folder holds the **approved, export-ready** *First Time Ordering* help video
— the end product of the two-track pipeline (screen-recording segments from
`../source/` + Sarah avatar narration, assembled in `../temp/`, polished in
HeyGen AI Studio).

## Current version
- **`First_Time_Ordering_6.mp4`** — the latest and current video (v6).

This is the one to ship and the baseline for any future improvements. The earlier
drafts (v1–v5) were **intentionally not kept** in this backup; v6 supersedes them.

## Quick-play launcher
- **`Play Latest Video.command`** — double-click in Finder to open the
  highest-numbered `First_Time_Ordering_#.mp4` in this folder with your default
  macOS player (QuickTime). It always tracks the latest version, so no need to edit
  it when you add `_7`, `_8`, etc. First run only: if macOS Gatekeeper blocks it,
  right-click → **Open** once to approve, then double-click works normally.

## Versioning rule (important)
Per the project's hard rules, **we never overwrite a finished video** — there is
no undo. Every new cut becomes a **new incremented file**:

```
First_Time_Ordering_6.mp4  →  First_Time_Ordering_7.mp4  →  …
```

When you improve v6, re-cut from `../temp/` (or `../source/` if a segment needs
re-recording), render to the **next number**, and leave v6 in place until the new
version is approved.

## Spec of the finished file
- Canvas: 1152×1080, 60fps, yuv420p, AAC
- Intro on `#E8F4F8` brand background; app body is dark-themed
- Sarah narration overlay in bottom-right corner (288px wide, 30px margin)

## How to make improvements to v6
1. Open the relevant building blocks in `../temp/` (segments, intro, corner).
2. If a screen recording itself needs to change, re-cut from `../source/`.
3. Reassemble with ffmpeg following the rules in `../temp/README.md`
   (`libvpx-vp9` on webms, `normalize=0` on amix, `fps=60,format=yuv420p` on
   non-60fps bases, etc.).
4. Render to `First_Time_Ordering_7.mp4` (next increment).
5. Hand to HeyGen AI Studio for captions/polish/export.

## Narration / avatar reminder
Use **Video Generation (verbatim script)** for narration clips — never Video
Agent, which rewrites scripts. Sarah's locked IDs and framing are documented in
`../temp/README.md`.
