# Skill: Avatar Compositing — backgrounds, scaling, framing (ffmpeg)

**Purpose:** Reusable ffmpeg recipes for assembling avatar segments into help videos —
removing/replacing the avatar background, and scaling/cropping the avatar to frame her the
way we want. Captures everything proven during the First Time Ordering build so we never
re-derive it.

**Location:** `HeyGen/.claude/skill/hey_gen/`
**Related:** `avatar_launch.md` (the "Sarah" spec + IDs), `generate_avatar_video.py` (creates clips)

---

## 0. The single most important flag (VP9 alpha)

HeyGen transparent clips are **VP9 webm with an alpha channel**. ffmpeg's *native* VP9
decoder **silently drops the alpha** — you get an opaque black box instead of a cutout.

**ALWAYS force the libvpx-vp9 decoder on the webm INPUT:**

```bash
ffmpeg -c:v libvpx-vp9 -i clip.webm ...
```

- Without it: `alphaextract` errors "Requested planes not available"; overlays show a black box.
- With it: the pixel format reads `yuva420p` (the `a` = alpha) and the cutout is clean.

Verify a webm actually has alpha:
```bash
ffmpeg -c:v libvpx-vp9 -i clip.webm 2>&1 | grep Stream     # want yuva420p
ffmpeg -c:v libvpx-vp9 -i clip.webm -vf alphaextract -frames:v 1 -update 1 /tmp/mask.png
# /tmp/mask.png should be a WHITE silhouette on BLACK (white=opaque, black=transparent)
```

---

## 1. Remove / replace the avatar background

**You cannot reliably key a baked-in scene** (e.g. HeyGen's studio room) out of an mp4 —
there's no chroma key and edge-detection on a real scene leaves halos. **Don't try.**

Instead, **regenerate the clip as a transparent webm** (Pamela supports matting), then
composite over whatever background you want. Generate with `--webm`:

```bash
python3 .claude/skill/hey_gen/generate_avatar_video.py \
  --avatar 468eabb3326a4d8587ba29d065b1eba7 \
  --voice 04d0ae1d0af2489ca7d3bb402a39a890 \
  --script "<verbatim line>" \
  --webm \
  --out videos/<slug>/temp/<slug>-<segment>.webm
```

### Composite transparent avatar over a SOLID COLOUR
```bash
ffmpeg -f lavfi -i "color=c=#E8F4F8:s=1152x1080:d=<DUR>:r=60" \
  -c:v libvpx-vp9 -i <clip>.webm \
  -filter_complex "[1:v]scale=<W>:<H>[p];[0:v][p]overlay=(W-w)/2:<Y>:shortest=1[v]" \
  -map "[v]" -map "1:a" \
  -c:v libx264 -c:a aac -pix_fmt yuv420p -r 60 \
  <out>.mp4
```
- `color=c=#E8F4F8:s=1152x1080:d=<DUR>` — solid brand background at the demo's size/duration.
  Set `<DUR>` to the clip's duration (e.g. 3.68).
- `-c:v libvpx-vp9` on the webm — REQUIRED (see section 0).
- `-map "1:a"` — keep the avatar's voice from the webm.

### Composite transparent avatar over the DEMO (corner overlay) — see section 3.

---

## 2. Scale & position the avatar (framing)

The avatar is its own portrait clip (e.g. 406x720 for transparent output). To frame her in
a 1152x1080 canvas you SCALE her up, then POSITION with `overlay`.

```
[1:v]scale=<W>:<H>[p];[0:v][p]overlay=<X>:<Y>:shortest=1[v]
```

- **scale=W:H** — enlarge the avatar. Keep the source ratio (~203:360 for 406x720) to avoid
  distortion: multiply both by the same factor. Bigger numbers = bigger avatar.
- **overlay X** — horizontal position. `(W-w)/2` centers her.
- **overlay Y** — vertical position. This is the tricky one:
  - `<negative>` (e.g. `-180`) anchors from the TOP, letting the bottom run off-frame —
    good for a head-near-top "presenter" look.
  - `H-h+<n>` anchors from the BOTTOM — good for sitting her low.

### Dial-in cheat sheet (what we actually used)
For the First Time Ordering intro (406x720 webm → 1152x1080, head-near-top presenter):
```
scale=1130:2005   overlay=(W-w)/2:-180     # LOCKED look for the pilot intro
```
Adjustments:
- Head cut off at top → make Y less negative (`-180` → `-100`).
- Too much space above head → more negative (`-180` → `-280`).
- Too big / small → change the scale pair (keep ~203:360 ratio).

> Reality note: framing is trial-and-error. Render, view, nudge two numbers, repeat.
> macOS caches video thumbnails — if it "looks unchanged," close Preview fully and re-open,
> or check `ls -la` (file size/timestamp changes prove the render updated).

---

## 3. Corner overlay (avatar bottom-right on the demo)

Overlay the transparent corner clip onto the demo, sized ~1/4 width, fading out after she
speaks. (Numbers are starting points; dial in like section 2.)

```bash
ffmpeg -i videos/<slug>/source/<demo>.mp4 \
  -c:v libvpx-vp9 -i videos/<slug>/temp/<slug>-corner.webm \
  -filter_complex "\
    [1:v]scale=288:-1,format=yuva420p,fade=out:st=3.0:d=0.6:alpha=1[c];\
    [0:v][c]overlay=W-w-30:H-h-30:enable='lte(t,3.6)'[v]" \
  -map "[v]" -map "0:a" \
  -c:v libx264 -c:a aac -pix_fmt yuv420p -r 60 \
  videos/<slug>/temp/<slug>-demo-with-corner.mp4
```
- `scale=288:-1` — ~1/4 of 1152 width; `-1` keeps aspect.
- `fade=out:alpha=1` — fade the avatar (not the demo) via her alpha.
- `overlay=W-w-30:H-h-30` — bottom-right with 30px margin.
- `enable='lte(t,3.6)'` — only show her for the first 3.6s.
- `-map "0:a"` — keep the DEMO's audio track (the corner clip's voice may or may not be wanted;
  if her corner narration IS wanted, mix instead — TODO to decide per video).

---

## 4. Concatenate intro + demo into the final video

Both segments must share resolution/fps/pixel format (we standardize on 1152x1080, 60fps,
yuv420p). Then concat:

```bash
printf "file '%s'\nfile '%s'\n" \
  "$PWD/videos/<slug>/temp/intro_solid.mp4" \
  "$PWD/videos/<slug>/temp/<slug>-demo-with-corner.mp4" > /tmp/concat.txt

ffmpeg -f concat -safe 0 -i /tmp/concat.txt \
  -c:v libx264 -c:a aac -pix_fmt yuv420p -r 60 \
  videos/<slug>/final/<slug>.mp4
```
> If audio streams differ, concat can desync — re-encode (as above) rather than `-c copy`.
> For a soft intro→demo transition, use `xfade`/`acrossfade` instead of hard concat (optional).

---

## 5. Inspect / verify helpers

```bash
ffmpeg -i <file> 2>&1 | grep -e Duration -e "Stream.*Video"   # size, fps, duration
ffmpeg -c:v libvpx-vp9 -i <clip>.webm 2>&1 | grep Stream      # confirm yuva420p (alpha)
# Visual alpha check over magenta:
ffmpeg -f lavfi -i color=magenta:s=720x720:d=2 -c:v libvpx-vp9 -i <clip>.webm \
  -filter_complex "[0][1]overlay=(W-w)/2:(H-h)/2:shortest=1" -frames:v 1 -update 1 /tmp/a.png
```

---

## 6. Known-good values (First Time Ordering pilot)

| Thing | Value |
|---|---|
| Canvas (final) | 1152x1080 @ 60fps (matches demo; don't upscale the demo) |
| Brand bg colour | `#E8F4F8` |
| Intro webm | 406x720, ~3.68s |
| Intro framing | `scale=1130:2005`, `overlay=(W-w)/2:-180` |
| Corner webm | 406x720, ~3.6s |
| VP9 alpha decode | `-c:v libvpx-vp9` on EVERY webm input (mandatory) |

---

## TODO / wishlist

**Retired 2026-08-13.** The three items here (percentage-based crop/scale,
per-video narration mixing, an `xfade` intro→demo transition) all improved the
Claude-assisted **ffmpeg compositing pipeline**, which agent 6 pivoted away from
on 2026-08-06 — the user's feedback was that the ffmpeg-bridged avatar motion
looked wrong, and scenes are now built inside HeyGen's own "Scene by scene"
editor. Improving the retired pipeline would be work spent on a path we left.

This document is still worth reading for what it records about how the
compositing behaved; just don't treat the list above as a plan.

Open work lives in `ToDo.md` at the repo root. The live help-video items there
are `ToDo_Rentify_v10.md` **V3** (v10 has no help-video delivery mechanism at all — the whole
workstream is blocked on that) and **P4.20** (the canvas aspect ratio is still
unresolved; near-square ~1:1 is the real target, portrait is a familiarization
pass).
