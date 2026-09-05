# temp/ — Intermediate Working Assets

## What this folder is
This is the **workbench** for the *First Time Ordering* video. It holds every
intermediate piece produced between the raw recordings (`../source/`) and the
finished video (`../final/`): the cut screen segments, the intro, the avatar
corner clips, and the partially-assembled renders. These are the building blocks
that get spliced together with ffmpeg and handed to HeyGen AI Studio for final
captions/polish/export.

> Note: the name says "temp," but these are **not disposable**. They are the
> reusable pieces you need to make improvements to v6 without rebuilding from raw.
> (The throwaway verification screenshots — the old `check/`, `flash/`,
> `introcheck/` folders — were intentionally **not** copied into this backup.)

## What's in here

### Screen-recording segments (background track)
Each screen of the flow, cut from a source raw. Two crops per screen:
- `seg-<name>.webm` — full-frame segment
- `seg-<name>-tight.webm` — tighter crop for zoom/corner framing

Screens covered: `search`, `dashboard`, `dates`, `person`, `questionnaire`,
`email`, `name`, `payment`, `code`, `collections`, `checkout`, `receipt`,
`continue`.

### Intro assets
- `first-time-ordering-intro.webm` / `.mp4`, `intro2.webm`, `intro_fitted.mp4`,
  `intro_solid.mp4`, `intro_last.png` — variations of the branded intro
  (`#E8F4F8` background) used to open the video.

### Avatar corner clips (Sarah overlay)
- `corner_tight.webm`, `first-time-ordering-corner.webm`, `corner_first.png`,
  `corner_tight_preview.png` — Sarah in the bottom-right corner overlay.

### Assembled / preview renders
- `first-time-ordering-21.mp4` … `-24.mp4` — incremental assembled cuts
  (numbered fallbacks; higher = later).
- `demo_with_corner.mp4` — demo with the avatar corner composited in.

## Key technical rules (enforce on every ffmpeg pass)
- **webm decoding:** always use `-c:v libvpx-vp9` on every `.webm` input — the
  native decoder drops alpha (you'll get a black box). Confirm `yuva420p` in the
  stream info.
- **Audio mixing:** always `normalize=0` on `amix`, or earlier audio halves each
  pass (quiet start → loud end).
- **Frame rate:** add `fps=60,format=yuv420p` on any non-60fps base before
  overlaying the 60fps avatar, or the avatar freezes while audio plays.
- **Blur (PII):** `boxblur` radius must be ≤ 11; use `10:3` for PII blurring.
- **No drawtext:** this ffmpeg build has no libfreetype — render text with Pillow.
- **Demo never freezes:** narration always overlays the *live, playing* demo.
  Never pause the demo to fit narration.

## Workflow rules
- **Never overwrite.** Every irreversible edit writes a NEW incremented file
  (v-1 → v-2 → v-3). Use `-y` only when writing to a new filename.
- **Verify before splicing:** confirm each intermediate has non-zero duration and
  the expected streams before concatenating.
- Canvas spec for the finished piece: 1152×1080, 60fps, yuv420p, AAC.

## Sarah — locked identity (don't change without a project decision)
- avatar_id: `468eabb3326a4d8587ba29d065b1eba7`
- group_id:  `0484e7d80416443388aa1763f684f019`
- voice_id:  `04d0ae1d0af2489ca7d3bb402a39a890` (Derya, Starfish engine)
- corner: 288px wide, bottom-right, 30px margin
- crop: `crop=406:360:0:50` (head-and-shoulders framing)
- Narration generation: **always Video Generation (verbatim script)**, never
  Video Agent (it rewrites the script).
