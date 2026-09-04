---
name: sarah-library
description: The single reference for Sarah — the on-screen HeyGen avatar every help video narrates over — as she is stored, standardized, and worked with in the Avatar Editor and the build pipeline. Covers Sarah/ (her common library, 7 folders), a store's own sarah_clips/ (what the build actually reads), the archived per-store library, the rest-pose/uncertainty/idle standards, and how the Avatar Editor's two panels work with all of it. Use whenever working in avatar_editor/, touching Sarah/ or any store's sarah_clips/, or asked about Sarah's clips, her standard poses, idle footage, or why a build used the wrong frame.
user_invocable: true
---

# Sarah — the library, the standards, and how the Avatar Editor uses them

Sarah is the on-screen HeyGen avatar every help video narrates over — one
locked look, one locked voice, reused across every store (her HeyGen
identity spec — avatar_id, voice_id, how a NEW clip of her is rendered —
lives in `docs/avatar_launch.md`; this skill is about the clips that
already exist and how they're stored, standardized, and edited, not about
generating new ones).

**Two separate places hold her clips, and they are not interchangeable:**

| | `Sarah/` (repo root) | a store's own `sarah_clips/` |
|---|---|---|
| What it is | her COMMON library — reference material the same across every store | that ONE store's own leftover pieces (openings, closings, bridge/intro clips, ...) |
| Who reads it | the Avatar Editor, interactively, for browsing/picking/assembling | the BUILD SCRIPTS (`assemble_video.py`, `sarah_transitions.py`, `build_sarah_opening.py`) — they glob a STORE's own folder by filename, never the common one |
| Scope | every store | one store, one video |

Carson's own call (2026-09-03): work off the common library for editing,
not a per-store copy. That changed what the Avatar Editor shows; it did
**not** change what the build scripts read — they still glob a store's
own `sarah_clips/` root directly, so a piece the Avatar Editor helps you
build still has to land there by hand before a build will pick it up
(see "Putting a piece back into a build" below).

## Why standards exist at all — the two defects that forced this

Before either library existed, a hold was built by cloning whatever frame
sat at a clip's boundary. That produced two real defects in the first
finished video:

1. **Eyes shut.** Sarah blinks and glances down constantly — four of eight
   frames sampled across one 13s clip had her eyes closed. A frame cloned
   from a boundary was a coin flip, and a hold on a blink reads as broken.
2. **Mouth mid-word.** Scanning continuous speech for a closed-mouth frame
   found almost none usable — a hold taken from mid-clip catches her
   talking, frozen.

Scoring frames by a metric didn't fix it either — eye-contrast-minus-mouth-
contrast still ranked mid-speech frames highly, and five later attempts to
detect a closed mouth algorithmically all passed footage where she is
visibly talking (frame-to-frame motion, motion-during-silence, closeness to
a reference pose, mouth-region difference, mouth darkness — every one
failed a different way). **A metric builds a shortlist; look at the frame
yourself.** And the deeper fix is upstream of any of that: **don't hunt for
a good frame — render one on purpose.** That is what the standards below
are.

## `Sarah/` — the common library, 7 folders

```
Sarah/
  openings/       her first appearance in a video — intro clips
  gap-fillers/    short filler clips for stitching frame sequences
  idle/           settled, gently-moving footage — fills a silent hold
  stills/         the reference POSES — rest pose, uncertainty (below)
  transitions/    corner-transition / bridge clips, moving between poses
  sound_bits/     spoken lines — HeyGen originals; per-store ones get
                  copied in from a finished video when useful elsewhere
  closings/       her sign-off — mirror of openings/
```

These 7 names are the fixed, deliberate taxonomy — `avatar_editor/serve.py`'s
`LIBS_GROUP_ORDER` enumerates them in this exact order (openings first,
closings last — the two bookend the other 5, the order they'd actually play
in a finished video), and every one of them shows in the Avatar Editor even
when empty (`(0)`), so the panel always shows the full shape of the library
at a glance rather than a folder only appearing once something's filed in
it. Loose files that don't fit any of the 7 sit at `Sarah/`'s own root —
Carson's own rule for anything ambiguous: don't guess a folder, drop a copy
at the root and sort it by hand later.

**Capturing a NEW still from a frame on screen** is a different job, and
it has its own traps — which of three near-identical source files to take
the frame from, and why two of them are wrong. That procedure is in the
**`video-development`** skill. This file stays the reference for what a
still IS; that one is how to get one.

### The rest pose — how she must look whenever she is NOT speaking

`stills/sarah-rest-pose-full-alpha.png` / `-corner-300-alpha.png` /
`-corner-300-preview.png` (over `#212121`, to look at).

**Eyes open, looking at camera, mouth closed, faint neutral smile, head
level.** Use it at the start of a scene (she should already be settled
before her line begins), the end of a scene (her line ends before the clip
does — she holds here), and any inserted pause (silence means her face must
be at rest).

Sourced from the ski-demo build: the **final frame of the corner-transition
(bridge) clip**, `sarah-bridge-alpha.webm` at `t=4.04`. Not a coincidence —
HeyGen clips open and close on a settled pose, so **the first and last
frames of any clip are where the rest pose lives**; mid-clip frames are
almost all mid-word.

### "Uncertainty" — the softer, asymmetric look

`stills/sarah-uncertainty-full-alpha.png` / `-corner-300-alpha.png` /
`-corner-300-preview.png`. Eyes open and mouth closed like the rest pose,
but the head sits very slightly turned and the expression reads softer —
hesitant rather than composed.

Sourced from `sarah-scene-11-alpha.webm` at `t=3.92` (its final frame) in
the ski-demo build — noticed because the finished video was ending on it
instead of the rest pose. **A clip's final frame is usually the rest pose,
but not always** — anything that needs the standard close must use the
rest-pose file itself, never "whatever the last clip ended on." Not used
deliberately anywhere yet; kept because it's a genuinely different register
that may suit a line asking a question or acknowledging a difficulty.

### Idle footage — how she looks when she has nothing to say

`idle/sarah-idle-20s-alpha.webm` — 608×1080, 25fps, RGBA alpha, 20.0s.
`idle/sarah-idle-10s-alpha.webm` — the first render, superseded, kept as a
fallback.

Settled, gently moving, saying nothing — what fills a silent hold.
`assemble_video.py` slices a different window per hold so the same motion
never repeats, instead of freezing a frame.

**How it's made: silent audio, no script** —
`{"type": "avatar", "avatar_id": "468eabb3326a4d8587ba29d065b1eba7",
"audio_asset_id": "<a 20s WAV of room tone>", "resolution": "1080p",
"output_format": "webm"}`. `audio_asset_id` replaces `script`+`voice_id`
entirely; HeyGen's clip length follows the audio, so N seconds of "nothing
to say" produces N seconds of idling. Measured against a real speech clip:
0 of 499 frames frozen, frame-to-frame motion ~4× calmer, mouth never
opens. Cost **$1.00** for the 20s render — budget ~$0.05/second.

Three traps already paid for, worth not re-learning:

- ⚠ **Render 20s, not 10.** A 300-frame clip *looks* like enough for seven
  30fps holds needing 288 frames combined, but the assembler picks each
  hold's window by best seam match, which scatters them — the clip
  fragmented and the last hold had no gap left, reusing 8 frames. ~600
  frames (2.1× the raw total needed) removed the reuse and improved three
  of seven seams, because the search had twice the candidates. Size an
  idle render against roughly **twice** the raw frame total, not the total
  itself.
- ⚠ **Use room tone, not digital zero.** The uploaded WAV needs to be
  audio at ~−60 dBFS (inaudible, unambiguously no speech) — pure silence
  as a control was never confirmed to be accepted.
- ⚠ **25fps, like every HeyGen render.** N frames is N/25 seconds; this
  pipeline runs at 30fps and resamples.

**Do not mine speech clips for idle frames — it was tried first, thoroughly,
and does not work.** HeyGen clips carry almost no non-speaking frames (17
frames total across 13 real clips, 0–6 per clip — nothing long enough to
use), and no frame-scoring metric reliably tells talking from not-talking
(see "Why standards exist" above). The scraped-frame loops built this way
were deleted after the rendered 20s clip replaced them — 54MB of PNGs down
to one 1.2MB clip that scores better on every measure. **Render idle
footage. Do not hunt for it.**

## A store's own `sarah_clips/` — what the build actually reads

Under `Customers/<Business>/<store>/help-videos/videos/<video>/sarah_clips/`.
Loose files at its own root are what `assemble_video.py` and friends glob
by filename — the opening piece, the closing piece
(`*-transition-to-centre.webm`, then `sarah-closeout-alpha.webm` beside
it — with neither present it falls back to a short hold on the standard
rest pose, in the corner; nothing errors), the bridge/corner-transition
clip, her intro. **This is genuinely separate from `Sarah/`** — copying
something into the common library does not put it where a build will find
it; that still needs a deliberate copy into this store's own folder.

A store's own **organized library** — the old `sarah_clips/libs/`
7-folder structure the Avatar Editor used to browse per-store, before the
common split — is retired. Where one still exists (archived, not
deleted), it sits at `sarah_clips/z_history/<timestamp>/libs/`, following
this repo's own `z_History` convention for "moved aside, kept, never
browsed live" (see `CLAUDE.md`'s own note on it) — the Avatar Editor's
store panel deliberately never looks inside `z_history/`; it isn't a
source, it's the archive.

### Putting a piece back into a build

The common library and a store's own build-input folder are not linked
automatically. To make the Avatar Editor's work actually show up in a
finished video, copy the finished piece into that store's own
`sarah_clips/` root by hand, under the filename the build script globs for
(e.g. `sarah-closeout-alpha.webm`, `*-transition-to-centre.webm`) — see
that store's own working files, or `build/assemble_video.py`'s own glob
patterns, for the exact name.

## The Avatar Editor's two panels

`avatar_editor/` (port 8844) shows the common library and a store's own
`sarah_clips/` side by side — left panel `Sarah` (the common library,
`/api/libs_list?source=common`), right panel headed with the STORE name
then the VIDEO name (that store's own `sarah_clips/`,
`/api/libs_list?base=&overlay=`). Both fetches run with their own loading
spinner, common first.

**Checking a clip in EITHER panel feeds the SAME Frame Selector, Clip-Gap
Builder and Audio Menu** — Carson's own call, so a build can mix a common
clip with a store-specific one in one session. Every clip carries which
library it came from (`source`: `'common'` or `'store'`), because the two
roots are siblings on disk, not one inside the other, so a bare path alone
can't say which — every later request (extracting frames, playing audio)
passes that `source` back so the server resolves it against the right
root. **A panel's Play button only ever moves its own panel's picture** —
this has been got wrong twice already (a frame stepper driven by one
button that moved a DIFFERENT panel's viewer; one shared `<video>` that
let one button's Play take over another's previewer), and the test suite
guards it.

The store panel's own header names the store and video, not the folder —
it's read from the open scene's own path, so it's right even when that
store's library is empty or fully archived. Its list of clips is now
just "whatever's actually left" (one plain group, no fixed taxonomy) since
its organized library moved to `z_history/`.

The rest pose is looked up in the common library FIRST when the Avatar
Editor needs it (Add Sarah Opening/Closing Still) — Sarah/ is the
canonical source for it now — falling back to a store's own copy only if
the common one hasn't been found yet.

### Audibility — measured, never assumed

Every `.webm` in either library carries an Opus audio stream, **including
the silent idle loops and gap-fillers** — so "has an audio stream" was
never the right question for which clips should actually play. Audibility
is measured server-side per file (`has_audible()` in `avatar_editor/serve.py`,
cached by path/mtime/size): a quick ffprobe stream check, then
`ffmpeg -vn -af volumedetect` for max volume (`-vn` matters — decoding the
VP9-alpha video track broke the measurement before it was added). Anything
above **−50.0 dB** counts as a real voice; measured gap between real
speech (max −4.8/−7.1 dB) and this library's silent tracks (idle: −60 dB,
gap-fillers: −91 dB, transitions/stills: no audio stream at all) is
enormous, so the threshold isn't near a real edge. The Audio Menu and
Frame Selector buttons only go green, and only play, clips that are
actually audible by this measure — the Clip-Gap Builder is the one
exception: it's a TIMELINE, not an audio picker, so it plays its whole
collection including silent clips, and goes green on FRAMES rather than
on a voice.

### Working Clips — what Carson builds here, saved

A third source, right of Timeline Scenes: `working-clips.js`'s own panel,
three sections (IDLE, TRANSITIONS, SOUND_BITS) holding clips assembled IN
the Clip-Gap Builder and saved under a typed name — as opposed to either
library above, which holds material HeyGen or the transition tools
produced. **Save to Working Clips** (in the Gap Builder Menu — picking a
section from its dropdown IS the save) files the whole Clip-Gap Builder
collection, in order. **Replace Selected** (in the Frame Selector Menu)
drops the one active saved clip in over a selection there, warning first
if the frame counts differ. Saved clips live in the same `localStorage`
record as the Clip-Gap Builder's own collection, not tied to one scene,
and are stored compactly (a short list of source clips plus per-frame
index pairs, URLs rebuilt on the way out) rather than as full frame
objects.

## Traps already paid for

- **A stale hardcoded path silently resolves to nothing, and the build
  carries on wrong rather than erroring.** `build/assemble_video.py`'s own
  `REST_POSE` constant has already gone stale once (pointing three levels
  up at a layout from the retired `rentify_live` repo) and produced a
  video that silently ended on the wrong frame — one warning line among
  forty, shipped anyway. `build/assemble_video.py` is off-limits to edit
  directly; if a `Sarah/` reorganization moves a file that constant
  depends on, that has to be flagged, not silently left broken.
- **A file nested one level deeper than a flat-folder walk expects is
  invisible, not an error.** `libs_list()`'s group walk only looks one
  level into each of the 7 folders — files copied into a further
  subfolder (`sound_bits/HeyGen-originals/`, once) showed a correct-
  looking `(0)` count and were simply never listed. Keep every library
  folder flat.
- **"Has an audio stream" is not "has a voice."** Every clip in this
  library carries an Opus track, silent ones included — always check
  `has_audible()`'s measurement, never the presence of a stream.

## Also relevant, not duplicated here

- `docs/avatar_launch.md`, `docs/heygen_api.md`, `docs/HEYGEN_RULES.md`,
  `docs/avatar_compositing.md` — Sarah's locked HeyGen identity (avatar_id,
  voice_id) and how a brand-new clip of her gets rendered. Upstream of
  everything in this skill; read those to generate new footage, this skill
  to work with what already exists.
- `PIPELINE.md` — where rendering and placing Sarah sits in the full
  video-build pipeline.
- `avatar_editor/README.md` — the Avatar Editor's own file-by-file
  architecture (which `.js` file owns what, the FramePlayer engine, load
  order). This skill covers what the tool is FOR; that file covers how
  it's built.
