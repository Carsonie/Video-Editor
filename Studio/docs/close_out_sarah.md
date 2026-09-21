# Sarah's bookends — the Closing Scene, and everything needed to finish it

**Status: BUILT and shipped, 2026-08-21.** This file was written as a design so
the plan would survive the session; it is kept because the reasoning still
explains the code. What actually shipped differs from the plan below in three
ways, all of them simplifications:

1. **No `build_sarah_closing.py` was needed.** The closing lives inside
   `assemble_video.py`'s existing closing block, which already appended to the
   front and rear track lists. It activates when a `*-transition-to-centre.webm`
   exists in the store's avatar folder, and falls back to the old corner hold
   otherwise — so the three stores without one are untouched.
2. **The morph is `morph_avatar_corner.py --reverse`** — the same interpolation
   with its endpoints swapped, so the opening and closing cannot drift apart.
   Reversed, it also measures from the START of the clip, because a closing move
   begins in the corner rather than ending there.
3. **The closing carries its own short line.** Sarah landed full-screen and then
   sat mute, which read badly, so a separate render says *"See you at the
   store."* ($0.05). Deliberately generic: the bookend is identical for every
   store, so no other store needs its own.

Delivered: `video/ski-demo_first-time-ordering_v18.mp4`, 112.3s. Both bookends
are also exported standalone to `sarah_clips/OPENING.mp4` and
`sarah_clips/CLOSING.mp4` by `export_bookends.py`.

⚠ The folder was renamed `sarah_intro_tools/` → **`sarah_clips/`** on the same
day, named for the avatar rather than the job, so a second presenter gets
`<name>_clips/`. The code accepts either name.

Written to the repo root because `/root` does not exist on this machine.

---

## The goal

Every help video should open and close the same way, whatever the store:

- **Opening Scene** — Sarah centred on a dark screen, then the first segment
  fades in as she morphs down into the lower-right corner. **Already built.**
- **Closing Scene** — the reverse. She morphs back out of the corner to centre
  while the background goes dark, and **finishes in the same pose she started
  in**. **Not built.**

Only the words change per store. Both halves are store-independent machinery.

---

## What already exists (the Opening)

Built by `build/build_sarah_opening.py` in the Video-Editor repo (moved there
2026-08-28).

Two HeyGen lines drive it:

| line | purpose |
|---|---|
| `intro` | spoken centred, on the dark screen |
| `bridge` | gives the morph footage that exists **after** the intro's last word |

That second line is not decoration. The background must stay dark until the
intro finishes, so the morph needs footage after it. One clip cannot do it —
you would either freeze her or move her mid-sentence.

Files, in `Customers/<Business>/<store>/help-videos/final/sarah_clips/`:

| file | what it is |
|---|---|
| `sarah-intro-alpha.webm` | raw HeyGen output, 1920×1080, alpha |
| `sarah-intro-1152-alpha.webm` | **6.34s** — intro centred on a 1152 canvas, with 1.52s of real idle footage prepended |
| `sarah-bridge-alpha.webm` | the bridge line |
| `sarah-bridge-transition-to-corner.webm` | the morph, 1.2s, eased |
| `sarah-bridge-corner-320-alpha.webm` | the corner element it lands on |
| `TRACK_front_sarah.webm` | Sarah only, transparent, carries the audio |
| `TRACK_rear_background.mp4` | dark, then scene 1 fading in over 0.6s, silent |

Output: `final/scenes/OPENING.mp4` (8.655s).

### The morph is Python, not an ffmpeg filter

`morph_avatar_corner.py` composites frame by frame because three things change
together — crop box, output size, position — and ffmpeg cannot do that:
`crop` fixes w/h at filter init, and per-frame `scale` feeding `overlay`
produces a varying-size input that overlay handles badly.

1.2s is ~30 frames at 25fps. Compositing them directly is exact and keeps alpha.

**This is why the closing is cheap: run the same interpolation backwards.**

Defaults: `--canvas 1080 --corner 300 --inset 0 --duration 1.2 --fps 25`.
ski-demo's build uses canvas **1152** and corner **320** (`assemble_video.py`
line 53: `CANVAS, CORNER = 1152, 320`); the corner sits flush at
`x = y = CANVAS - CORNER` (line 392).

---

## The Closing Scene — the spec

```
 t=0.0   segment 14 (the logged-out sign-in page) on screen,
         Sarah in the lower-right corner, starts the closing line
 t≈2.5   morph corner -> centre, 1.2s, the opening's interpolation reversed
         background crossfades to the pad colour over 0.6s
 t≈3.7   Sarah centred on dark, finishes the line
 t≈5.5   holds on REST_POSE — the same pose the opening began on
```

The user's words: *"the logout wallpaper for about 1-2 sec … then after another
1-2 sec, have Sarah transition back full screen and the background go dark, just
like the opening scene … so Sarah finishes in the same pose she started with."*

The closing line for ski-demo is already written in `script.json` scene 14:

> "Thank you for renting with Ski Demo. We hope you have a great time on the slopes!"

17 words ≈ **4.9s** at 3.44 wps.

### One line or two?

The opening needs two because the background must stay dark until the intro
ends. The closing does **not** have that constraint — the morph can happen
mid-sentence, like a camera move, and the tail after her last word is filled
with the existing idle clip. **One line is enough.** One render, ~$0.40.

---

## Implementation plan

### 1. `build_sarah_closing.py` — new, beside `build_sarah_opening.py`

- Reverse the interpolation in `morph_avatar_corner.py` (corner → centre).
  Add a `--reverse` flag there rather than duplicating the maths.
- Front track: corner hold (speaking) ++ reverse morph ++ centred hold ++ rest pose.
- Rear track: last segment, then `fade=t=out` to the pad colour over 0.6s,
  then flat pad colour. Mirrors `build_sarah_opening.py` line 332's fade-in.
- Output `final/scenes/CLOSING.mp4`, matching `OPENING.mp4`.

⚠ The pad colour is **not** hardcoded `#212121`. `assemble_video.py` line 399
samples it from the segment's own edge pixel:
`PAD = "0x%02X%02X%02X" % im.getpixel((5, im.size[1] // 2))`. Do the same, or
the closing's dark will not match the opening's.

### 2. `assemble_video.py` — the closing hold must change

Today it ends on `REST_POSE` **in the corner** (`END_HOLD = 1.0`, line 54, and
the block at line ~533). The bookend requires it to end **centred and
full-screen**. That block is what gets replaced.

`REST_POSE` = `Help_Videos/HeyGen/Sarah/sarah-rest-pose-full-alpha.png` — a
canonical still, deliberately not scene 11's last frame, which ends on a softer
"Uncertainty" expression. Framing matches within 2px across renders.

### 3. Then wire it to real footage

See "Order of work" below. Sarah's half does not depend on the recording.

---

## Facts found this session that must not be lost

### Segment 14 is the logged-out sign-in page, NOT desktop wallpaper

It was 4 frames of desktop wallpaper. The user trimmed it in `video_editor` at
10:53 and 10:55 on 2026-08-21 down to the **one frame showing the empty
"Email verification / Your email / Send Code" page** — the logged-out state.

So *"we start with login and end with login"* was literal, not a typo for
logout. It rhymes with scene 1, which is the same page being filled in. Holding
it out is honest: the page is genuinely static, nothing is loading.

### The archived head scrap cannot be reused as background

`segments/z_History/20260821-103343/Num_1-v2-segment.mp4` is 3s of the same
desktop wallpaper and was considered as filler. **It has a photo of Sarah
sitting on the desktop** plus a split-screen edge. A still portrait of Sarah
next to the animated Sarah reads as a mistake. Do not use it.

---

## Current state of `script.json`

`Customers/Rentify Demos Corp/ski-demo/help-videos/final/video/script.json`

- **14 scenes**, matching the 14-piece v2 cut (`segments/Num_1..14-v2-segment.mp4`).
- All lines reviewed and updated by the user on 2026-08-21.
- `silent: true` was **cleared** from scenes 13 and 14 — the user gave both
  lines, and leaving the flag would have made `render_narration.py` skip them
  and silently discard the copy.
- `actual-word-time` was **removed** everywhere: those were measured against the
  old words. They come back when the new lines are rendered.
- Each scene now carries `estimated-word-time`, `segment-length` (measured on
  disk), `target-length`, and `target-shortfall`.

### `target-length` — the rule

```
target = estimated speech + 2.3s, floored at 3.0s

2.3s = 0.4 lead-in + 0.8 tail + 0.8 render fluctuation + 0.3 seam
```

The 0.8s fluctuation allowance comes from the 11 previously rendered lines:
estimate-vs-actual ranged −0.5s to **+0.6s**, roughly constant rather than
proportional to length.

`segment-length` is kept as the MEASURED value on purpose. The gap between the
two — `target-shortfall` — is the number that drives everything downstream.

### The shortfall table (2026-08-21)

```
 n scene                    words  speech  target    have  short by
 1 login-and-code              23    6.7s    9.0s   5.72s     +3.3s
 2 dashboard-new-order          8    2.3s    4.6s   2.96s     +1.6s
 3 add-a-person                 9    2.6s    4.9s   4.36s     +0.5s
 4 add-myself                   9    2.6s    4.9s   5.40s        ok
 5 catalogue-search            30    8.7s   11.0s   5.88s     +5.1s
 6 dates                       42   12.2s   14.5s   7.20s     +7.3s
 7 review-and-continue         17    4.9s    7.2s   2.20s     +5.0s
 8 requirements                46   13.4s   15.7s  14.80s     +0.9s
 9 checkout-pay-with-stripe    20    5.8s    8.1s   2.88s     +5.2s
10 payment-card                10    2.9s    5.2s   4.40s     +0.8s
11 order-complete              21    6.1s    8.4s   2.12s     +6.3s
12 order-history               24    7.0s    9.3s   1.96s     +7.3s
13 logout-menu                 13    3.8s    6.1s   3.00s     +3.1s
14 tail-scrap                  17    4.9s    7.2s   0.04s     +7.2s
   TOTAL                                   116.1s  62.92s    +53.2s
```

**The current recording is roughly half the length the narration needs.**
Holding frames would mean 53s of frozen picture across 14 scenes. That is why
the pauses below matter.

---

## The Puppeteer pause plan (agreed, not built)

Make the E2E flow hold on each step so OBS records segments already at their
`target-length`. Real footage beats a repeated frame every time.

It also fixes an older bug for free: the notes warn a cut must land on a
**settled** page, and a loading spinner once shipped inside a scene. A
deliberate pause guarantees settling.

**Three things to get right:**

1. **Gate it.** These same flows are what `testing-runner-manager` runs for real
   E2E testing. Unconditional pauses make **every test ~53s slower** for no
   benefit. It must be opt-in — an env var the recorder sets, off by default.
   This is the one that will bite.
2. **Pause after the page settles, not before the click.** The extra time must
   sit on the finished picture, because that is what the narration describes.
3. **Watch the order clock.** The order page shows "expires in 9:57 minutes".
   This run goes 63s → 116s, fine. Test 4 is 4 people × 2 items and much
   longer — check it before adding pauses there.

---

## The capture fix (the task being done first)

Not a Sarah change, but the re-record depends on it, so it is recorded here.

**The finding.** The monitor is **3840×2160 physical**, presented as 1920×1080.
The browser is captured at its true **2304×1926 pixels**, then scaled by
**0.5** onto a 1152×963 canvas. Half of every captured pixel is discarded
before encoding. Retina text downsampled to 1x is the softness.

From the OBS scene file: `crop left 768, right 768, top 234, bottom 0` →
2304×1926, then `scale x 0.5, y 0.5`.

**Editing OBS by hand will not stick.** `Master_Flows/Recorder/lib/obs.ts:199`
calls `SetVideoSettings` on every run and overrides the profile. The 0.5 is
computed at `lib/obs.ts:184`. The fix belongs in that file.

**Ruled out as causes, with measurements:**

- The cut step. Segment vs raw scores **SSIM 0.9994**. Re-encoding at CRF 18,
  15 and 12 barely moved the picture.
- The editor preview. 750px JPEG q3 — slightly softer, not the cause.

**Other findings in the OBS profile:**

- `recordEncoder.json` is `{}` — no explicit quality setting at all, running on
  the 6000 kbps default (measured 5,955 kbps).
- Canvas height **963 is odd**, so the encoder emits 962 and crops a row.
- OBS installed is **32.2.2**; the `obs` skill documents **32.1.2**. Defaults
  shift between minors — confirm before trusting one.

**Caveat.** The finished video is 1152×1152, so capturing at 2304 and shrinking
back buys one good downscale instead of OBS's bicubic one. Real, but modest.
The large win needs the final canvas raised too, and that upscales Sarah, who
comes out of HeyGen at 1080.

---

## Traps that will cost an hour

- **`-c:v libvpx-vp9` on EVERY decode of an alpha WebM**, including `-f concat`.
  It has bitten three separate ways and the file always still reports
  `yuva420p`. Verify transparency by overlaying on magenta and reading a corner
  pixel — never by trusting metadata.
- **Match Sarah on the HEAD, not the alpha bbox.** The bbox bottom tracks her
  hands, which move constantly.
- **Measure difference in the region the viewer looks at.** Closed mouth →
  speaking is 1.94% across the whole frame but **8.52% across the face**. The
  full-frame number said "safe to fade" and was wrong.
- **A HeyGen clip STARTS mid-word with eyes shut** — it is trimmed to the first
  audio sample. It ENDS on the settled rest pose. So clip ends are safe to hold,
  clip starts are not. This is why the opening has 1.52s of idle prepended.
- **A negative gap is the defect that ships silently** — the picture freezes
  while she keeps talking. Run `vtt.py` until nothing is flagged. It is free.
- **Never drop `RECIPE=<name>`** from a generated flow-runner command.

---

## Order of work

1. **Capture fix** — `Master_Flows/Recorder/lib/obs.ts`. Full pixels, no 0.5
   downscale, bitrate raised to match, even canvas height. *(in progress)*
2. **Puppeteer pauses** — gated behind an env var, driven from the shortfall
   table above.
3. **Re-record ski-demo once.** One recording gets both full-resolution pixels
   and correct-length segments. Re-recording twice is wasted.
4. **Re-cut** in `video_editor`, renumber, refresh `segment-length` from disk.
5. **`build_sarah_closing.py`** — can be built any time from step 1 onward; it
   does not depend on the recording.
6. **`vtt.py`** until nothing is flagged. Free, and where the video is won.
7. **`render_narration.py`** — the only step that costs money.
8. **`assemble_video.py`** — and verify the untested silent-scene path
   (committed in `8d1539e`, never exercised).

---

## Cost

| item | cost |
|---|---|
| closing line render | ~$0.40 |
| scenes 13 + 14 now voiced | ~$0.80 |
| re-rendering the 12 changed lines | ~$4.80 |
| everything else (ffmpeg, cutting, assembling) | free |

Wallet was **$22.45** on 2026-08-20. `GET /v3/users/me` for the live figure —
that number goes stale, never quote it.

---

## Still open, unrelated to Sarah

- **Delivery is blocked.** `Rentify_v10` has no way to serve a help video at
  all. `ToDo_Rentify_v10.md` **V3**. Videos can be built but not shipped.
- The other three stores (bike-demo, canoe-demo, alpine-sports) are still
  **30fps output** and never had the v14/v15 treatment. Expect the same defects.
