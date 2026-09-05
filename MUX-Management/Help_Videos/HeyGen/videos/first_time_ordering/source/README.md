# source/ — Raw Screen Recordings

## What this folder is
This folder holds the **original, unedited screen recordings** of the Rentify
equipment-rental app walking through the *First Time Ordering* flow. These are
the raw capture files — the very first track in our two-track video approach
(screen recording + Sarah avatar narration). Everything else in the project is
derived from these files, so they are the single source of truth. If a segment
needs to be re-cut, re-cropped, or re-timed, you come back here.

## Why it exists
Per the project's hard rules, **we never overwrite a file** and there is **no
undo** — numbered fallbacks are the only recovery mechanism. Keeping the pristine
raws separate from working/intermediate files means we can always regenerate any
segment from scratch without re-recording the app. Deleting or editing these in
place would make the rest of the pipeline unreproducible.

## What's in here
Five full-length raw captures, in chronological/version order:

- `first-time-ordering.mp4` — first raw capture (~89 MB, the largest/most complete)
- `first-time-ordering-1.mp4`
- `first-time-ordering-2.mp4`
- `first-time-ordering-3.mp4`
- `first-time-ordering-4.mp4` — most recent raw capture

Higher numbers are later re-recordings of the flow (cleaner runs, UI changes, or
fixed mistakes). When starting fresh work, prefer the **highest-numbered** raw
unless you specifically need an older UI state.

## How these are used
1. A raw is loaded into ffmpeg and **cut into per-screen segments** (search,
   dashboard, dates, person, questionnaire, email, name, payment, code,
   collections, checkout, receipt, continue). Those segments live in `../temp/`.
2. Each segment also gets a **-tight** crop variant for the corner/zoom framing.
3. Segments become the background track; Sarah's narration overlays on top.

## Guidance for future videos
- **Record at the project canvas where possible:** 1152×1080, 60fps, yuv420p, AAC.
- The Rentify app UI is **dark-themed**; the brand background `#E8F4F8` is used
  for the **intro only**, never over the app.
- **Player timestamps are mm:ss, not raw seconds** — convert before using in
  ffmpeg cut points (e.g. "111" = 1:11 = 71 seconds).
- If a base recording isn't 60fps, add `fps=60,format=yuv420p` before overlaying
  the avatar, or the avatar track will freeze while audio plays.
- Keep raws here untouched. Do all cutting/processing into `../temp/`.
