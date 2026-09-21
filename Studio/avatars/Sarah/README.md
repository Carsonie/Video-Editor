# Sarah — standard clips and reference frames

Reference standards for how Sarah should look at fixed points in a help video.
Anything held on screen for more than a frame or two should match these.

## The rest pose — how she must look whenever she is NOT speaking

`sarah-rest-pose-full-alpha.png` — 608×1080, RGBA, real alpha
`sarah-rest-pose-corner-300-alpha.png` — the 300×300 corner crop the video uses
`sarah-rest-pose-corner-300-preview.png` — the same over the app's `#212121`, to look at

**Eyes open, looking at camera, mouth closed, faint neutral smile, head level.**

Use it at:

| moment | why |
|---|---|
| the start of a scene | she should already be settled before her line begins |
| the end of a scene | her line ends before the clip does — she holds here |
| any inserted pause | a pause is silence, so her face must be at rest |

Sourced from the ski-demo build: the **final frame of the corner-transition
(bridge) clip**, `sarah-bridge-alpha.webm` at `t=4.04`. That is not a
coincidence — HeyGen clips open and close on a settled pose, so **the first and
last frames of any clip are where the rest pose lives.** Mid-clip frames are
almost all mid-word.

## "Uncertainty" — the softer, asymmetric look

`sarah-uncertainty-full-alpha.png` — 608×1080, RGBA
`sarah-uncertainty-corner-300-alpha.png` — the 300×300 corner crop
`sarah-uncertainty-corner-300-preview.png` — over `#212121`, to look at

Eyes open and mouth closed like the rest pose, but the head sits very slightly
turned and the expression reads softer — hesitant rather than composed.

Sourced from `sarah-scene-11-alpha.webm` at `t=3.92` (its final frame) in the
ski-demo build. Noticed because the finished video was ending on it instead of
the rest pose — which is the point worth remembering: **a clip's final frame is
usually the rest pose, but not always.** Scene 11's is this instead. Anything
that needs the standard close must use the rest-pose file, not "whatever the
last clip ended on".

Not yet used deliberately anywhere. Kept because it is a genuinely different
register and may suit a line that asks a question or acknowledges a difficulty.

## Idle footage — how she looks when she has nothing to say

`idle/sarah-idle-20s-alpha.webm` — 608×1080, 25fps, RGBA, real alpha, 20.0s, 2.1 MB
`idle/sarah-idle-10s-alpha.webm` — the first render, superseded, kept as a fallback

Ten seconds of Sarah sitting there, settled and gently moving, saying nothing.
This is what fills a hold. `assemble_video.py` slices it — a different slice per
hold, so the same motion never appears twice — instead of freezing a frame.

**How it was made: silent audio, no script.**

```json
{ "type": "avatar", "avatar_id": "468eabb3326a4d8587ba29d065b1eba7",
  "audio_asset_id": "<a 20s WAV of room tone>",
  "resolution": "1080p", "output_format": "webm" }
```

`audio_asset_id` replaces `script` + `voice_id` entirely, and HeyGen's clip
length follows the audio — so ten seconds of nothing to say produces ten seconds
of idling. Measured on the result:

| | idle clip | a speech clip |
|---|---|---|
| frozen frames | **0 of 499** | — |
| frame-to-frame motion | median **0.039%** | median 0.24%, peaks 3.1% |
| mouth-closed score | min **35**, median 43 | dips to **28** |

Gentle motion in every frame, ~4× calmer than speech, mouth never opens, a
couple of natural blinks. Cost **$1.00** — budget ~$0.05/second.

⚠ **Render 20s, not 10.** Seven holds in the ski-demo build need 288 frames at
30fps, and a 300-frame clip looks like enough. It is not: the assembler picks
each hold's window by best seam match, which scatters them, and the clip
fragmented until the last hold had no gap left and had to reuse 8 frames.
~600 frames is 2.1x headroom — the reuse disappeared and three of seven seams
improved, because the search had twice as many candidates. Size the clip
against roughly **twice** the raw frame total, not the total itself.

⚠ **Use room tone, not digital zero.** The uploaded WAV is noise at **−60.8
dBFS** — inaudible, unambiguously no speech, but still valid audio. Pure silence
was uploaded as a control and never needed; it may or may not be accepted.

The WAV itself is **not committed** — it is 1.9 MB of silence and one command to
rebuild, so `Help_Videos/HeyGen/audio/*.wav` is gitignored:

```bash
ffmpeg -f lavfi -i "anoisesrc=color=brown:amplitude=0.0015:r=48000:d=20" \
  -ac 2 -c:a pcm_s16le Help_Videos/HeyGen/audio/silence-20s-roomtone.wav
```

Then `POST /v3/assets` with `-F "file=@..."` (multipart; `--data-binary` is
rejected) and use the returned `asset_id`.

⚠ **25fps, like every HeyGen render.** N frames is N/25 seconds. The pipeline
runs at 30 and resamples.

### Do not mine speech clips for idle frames — it does not work

This was tried first and thoroughly. **HeyGen clips contain almost no
non-speaking frames**: across all 13 ski-demo clips the settled frames after
speech ends total **17 frames — 0.68 seconds**, scattered 0–6 per clip. Nothing
long enough to use.

Five metrics were tried to find closed-mouth runs inside speech, and every one
of them passed footage where she is visibly talking:

| Attempt | Why it failed |
|---|---|
| low frame-to-frame motion | every 6th frame reads `0.00` from 25→30fps duplication |
| motion during audio silence | she speaks continuously; silences are a few frames |
| closeness to the rest pose | the mouth is too small a part of the frame to move the number |
| mouth-region frame difference | rejected everything — the two banked poses, both **closed**, differ by 12.9% there |
| mouth darkness vs a closed reference | separated open from closed only weakly, still ranked talking runs top |

**Render idle footage. Do not mine for it.** The scraped loops built this way
were deleted 2026-08-19 after v7 replaced them.

## Why this folder exists

Holding an arbitrary frame does not work, and produced two real defects in the
first finished video:

1. **Eyes shut.** This avatar blinks and glances down constantly — four of eight
   frames sampled across one 13s clip had her eyes closed. Cloning whatever
   frame sat at a boundary was a coin flip, and a 1s hold on a blink reads as a
   broken video.
2. **Mouth mid-word.** Scene 7 is continuous speech; scanning it for a
   closed-mouth frame found almost none. A hold taken from mid-clip catches her
   talking, frozen.

A metric alone did not solve it either — scoring frames on eye contrast minus
mouth contrast still ranked mid-speech frames highly, and five later attempts to
detect a closed mouth all passed footage where she is talking (see above).
**Look at the frame.** A metric builds a shortlist; your eyes decide.

And the deeper fix is upstream: **do not hunt for a good frame, render one.**

## Adding to this folder

Keep one file per standard, name it for the moment it covers, and record where
it came from — a clip + timestamp for a scraped frame, or the request that
generated it. PNGs here are small and **tracked**, as is `idle/`'s 1.2 MB webm,
unlike the video files under `Customers/*/*/help-videos/`, which are gitignored.

Size is the reason the scraped loops are gone: 54 MB of PNGs mined from speech,
replaced by one 1.2 MB clip that is better on every measure.
