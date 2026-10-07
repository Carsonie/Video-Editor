# ski-demo — "First Time Ordering" help video

Built with agent `6_end-customer-help-video-creations`, HeyGen-native
"Scene by scene" approach (the 2026-08-06 pivot away from ffmpeg compositing).

Started 2026-08-15. Everything for this video lives in this folder, per the
user's instruction — `segments/` (cut segments), `work/` (diagnostic contact
sheets), and the finished export alongside them.

## Source

`../raw_mp4/ski-demo_owner-one-item_dev_15-10-44_v2.mp4` — 67.8s, 1152×962,
30fps. ⚠ That rate is **historical** — OBS records at **25fps** since 2026-08-19,
to match HeyGen, which renders at 25 and cannot be changed. v14 and v15's segments
come from `..._19-17-45_v5.mp4` — 65.96s, 1152×962, confirmed **25fps** (1649
frames ÷ 25 = 65.96s exactly). ⚠ Don't read this off the doc — read
`final/work/boundaries.json`'s `raw` field, which is what `cut_segments.py`
actually cut. This line said `_v4.mp4` until 2026-08-20; that was wrong, caught
by cross-checking `boundaries.json`'s `recording_start_hms` (17:44:02) against
the candidate files' own recording times — 1 minute from `v5`'s, 64 minutes from
`v4`'s. A real recorded E2E run: ski-demo Test 1 `/owner-one-item`, renter
`harry_potter`, **INV-000617**, 2026-08-15.

Chosen over the part-built Paddle Sports video because that one's footage no
longer shows the product: paddle-sports has no store row in the v10 DB (0/5
runnable, cannot be re-recorded), and its payment scene shows a plain
"Pay Now (Simulated)" button, while the Stripe-look checkout — what every live
store actually presents — covers only bike-demo, ski-demo, canoe-demo and
alpine. Paddle Sports' `final/v-37.mp4` stays as a fallback and practice
artifact; it is not the thing to ship.

The source is already at the canonical scene spec, so no normalize step was
needed — verify with `ffprobe` anyway on any future source, per
`INSTRUCTIONAL.md` §1.1.

## How the segment boundaries are found — this is a TOOL now

Superseded 2026-08-19. This section used to describe a by-hand investigation and
ended "if this is ever re-cut from a new recording, redo this — do not reuse
these timestamps." That is no longer true: run
`.claude/agent-tools/6_end-customer-help-video-creations/cut_segments.py`.

Kept because the reasoning behind it still matters:

- **Summing the flow log's `(NNNNms)` durations does not work**, and it fails
  while looking correct. The totals agreed to 0.88s on one take while individual
  boundaries were out by a whole scene, because the time *between* steps is
  logged nowhere and varied 3.6s–6.0s within that single run. The old note here
  ("the true offset is 1.9s") was fitting a constant to something that is not one.
  The fix was to make the flow log stamp each step with an absolute time and the
  recorder log when OBS started; boundaries are now arithmetic.
- **Frame-difference detection alone gives far too many candidates** — 29 for 11
  segments — and misses transitions inside the same dark layout.
- **The cut must land on a SETTLED page**, not the load instant. And one quiet
  frame is not enough: a loading spinner is small enough to read as settled at
  analysis resolution, which is exactly how the three-dots defect got in.

**Boundaries below are for the take named above and are not portable.** Re-run
the tool for any new recording; it needs both logs and refuses without them.

## Segments — cut and verified

All cut with the locked standard:
`-c:v libx264 -c:a aac -pix_fmt yuv420p -r 30 -movflags +faststart`

| # | file | start | dur | what's on screen |
|---|---|---|---|---|
| 1 | `segment-01-login` | 3.3 | 6.1s | email entry → 4-digit code |
| 2 | `segment-02-neworder` | 9.4 | 3.4s | dashboard, New Order |
| 3 | `segment-03-addmyself` | 12.8 | 7.3s | Add a Person → Add Myself |
| 4 | `segment-04-search` | 20.1 | 8.4s | search, catalogue, pick the package |
| 5 | `segment-05-dates` | 28.5 | 3.9s | calendar, pickup + return |
| 6 | `segment-06-additem` | 32.4 | 3.2s | duration 6 days, Add Item |
| 7 | `segment-07-requirements` | 35.6 | 16.9s | sliders, skill, both T&C, Save and Continue |
| 8 | `segment-08-checkout` | 52.5 | 3.4s | order summary, **Pay with Stripe** |
| 9 | `segment-09-payment` | 55.9 | 4.4s | Stripe-look checkout, card fields |
| 10 | `segment-10-complete` | 60.3 | 2.4s | "Your order is completed" |
| 11 | `segment-11-history` | 62.7 | 4.1s | dashboard order history |

63.5s of demo footage. Logout was deliberately **not** cut — a help video
shouldn't end on signing out; scene 11 is the close.

## The script — approved and rendered

⚠ **The lines are no longer listed here.** `script.json` in this folder is the
source of truth for the copy, and the timing table is generated from it:

```bash
python3 .claude/agent-tools/6_end-customer-help-video-creations/vtt.py "<this folder>"
```

That prints the **VTT** (Video Timing Table) — clip length, spoken length and
the gap per scene. A table pasted into this file would drift from what was
actually rendered, which is exactly the failure the VTT exists to prevent.

Accuracy notes that shaped the copy: the checkout button really does read
**"Pay with Stripe"**, the Stripe-look page really does have card fields, and
the verification code is **4 digits** — so the narration can state all three
honestly here, unlike Paddle Sports.

## Open items before building

1. ~~Canvas aspect~~ **Resolved 2026-08-15 — `1:1` for this video**, per the
   user. This is now reachable both ways: the Studio API takes
   `aspect_ratio: "1:1"` as a global output setting, and the editor can be set
   to it. The five existing templates are all `9:16` and cannot be re-shaped —
   aspect is baked at template-build time.
2. **Whether a scene's duration flexes to the generated speech length is still
   untested** — the 4-scene experiment that would have answered it was skipped
   in favour of building the full Paddle Sports set. The script above is
   written shorter than each clip's runtime, which is the safer side.
3. **Delivery is blocked.** Re-verified 2026-08-15: `Rentify_v10` has no
   help-video support at all — no `help_videos/`, no `playback_ids.json`, no
   `fetchVideoRegistry`, no Mux reference in `web/src`. `customers/default/`
   holds only PDF templates. The whole delivery chain existed solely in the
   retired `rentify_live`. A finished video can be produced and uploaded to
   Mux, but **nothing in the platform would serve it to a customer.** That
   needs code inside `Rentify_v10`, so it is a **`V` item** for
   `ToDo_Rentify_v10.md`, not something fixable here.

## What's been produced so far (2026-08-15)

| file | what it is |
|---|---|
| `segments/segment-01..11-*.mp4` | the 11 cut demo segments, ready to use |
| `sarah-intro-alpha.webm` | raw HeyGen output — 1080×1920, alpha. The source both composites below are cut from; keep it. |
| `sarah-intro-1080-alpha.webm` | **Sarah, background removed, centred in 1080×1080, real alpha.** The full-screen intro master. |
| `sarah-intro-1080-preview.mp4` | the same over a dark background, just for viewing |
| `sarah-corner-300-alpha.webm` | **the corner element — 300×300, head-and-shoulders, alpha.** Overlay at `x=780:y=780` for a flush lower-right corner on 1080×1080. |
| `sarah-transition-centre-to-corner.webm` | **the morph — 1080×1080, alpha, 1.2s.** Sarah scales down, reframes to head-and-shoulders, travels to the corner, eased. Lands exactly on the corner element's geometry. |
| `DEMO_corner_avatar_1to1.mp4` | proof it works: the corner avatar over `segment-07-requirements`, full 1:1 |
| `DEMO_morph_to_corner.mp4` | the full beat: morph over real footage, then held in the corner |
| `sarah-bridge-alpha.webm` | the **corner-transition** clip — *"Let's get started. Here are the steps…"*, 4.16s. Required: the morph needs footage after the intro's audio ends. |
| **`TRACK_front_sarah.webm`** | **the front track** — Sarah only, transparent, 1080×1080, continuous: intro (centred) ++ morph ++ corner hold. Carries the audio. |
| **`TRACK_rear_background.mp4`** | **the rear track** — dark `#212121` through the intro, then scene 1 fading in over 0.6s. Silent. |
| `DEMO_two_track.mp4` | the two composited — a single `overlay=0:0` |
| `TEST_4scene_1to1.mp4` | the throwaway API feasibility render — see below |
| `work/` | contact sheets used to find the segment boundaries |

The Sarah opening **and** the corner overlay are reusable across every store's
video. Both recipes live once in
`.claude/agents/6_end-customer-help-video-creations.md` under **"Sarah
Opening"** — the flat `type: "avatar"` schema, `output_format: "webm"`, the VP9
alpha trap, measuring her real centre, the head-and-shoulders crop, and the
1:1 padding rule. Don't re-derive any of it here.

**This store's measured values** (re-measure for a different clip — a new
script moves her):

| | |
|---|---|
| subject bbox in the 1080×1920 source | `x=140..1052`, `y=212..1916` |
| her centre vs frame centre | x=596 vs 540 → full-screen offset `x=205`, not 236 |
| shoulder line (alpha width jumps 414→630) | y≈800 |
| head-and-shoulders crop | `crop=820:820:145:170` |
| corner placement on 1080×1080 | `x=780:y=780` flush (`x=750:y=750` for a 30px inset) |
| demo-footage pad colour, sampled from the clip edge | `#212121` |
| morph duration / easing | 1.2s, 30 frames @25fps, `smoothstep` (was 36 @30fps) |

**On the morph specifically:** HeyGen has no transition, keyframe or position
capability at all — this is pure ffmpeg/PIL. It is one deliberate move, not the
synthetic gap-filling motion that got the 2026-08-06 ffmpeg build rejected.

**For a NEW video, don't repeat any of this by hand** — the opening is one
command, and only the two script lines change:

```bash
.claude/agent-tools/venv/bin/python \
  .claude/agent-tools/6_end-customer-help-video-creations/build_sarah_opening.py \
  --intro "<intro line>" --bridge "<corner-transition line>" \
  --scene1 segments/segment-01-....mp4 --outdir .
```

It produces `OPENING.mp4` plus both tracks. Add `--skip-generate` to
re-assemble from existing clips without paying for new renders. This store's
opening was built and verified that way.

**The composition is two independent tracks** (agent 6, **Sarah Opening →
Step 6**): Sarah lives on a transparent front track that carries her whole
timeline and the audio; the background is a separate opaque track that stays
dark until her intro finishes, then reveals the scenes. They meet in one
`overlay=0:0`. Change either without touching the other — that is the point of
the split.

Timing on this build: intro ends at **4.85s**, at which the background fades in
over **0.6s** and the **1.2s** morph begins, landing her in the corner at
**6.05s**.

**Don't rebuild it by hand — it's a tool now.** Both the corner element and the
morph come from one command, which measures the pose itself and prints the
compose line:

```bash
.claude/agent-tools/venv/bin/python \
  .claude/agent-tools/6_end-customer-help-video-creations/morph_avatar_corner.py \
  --src sarah-intro-alpha.webm --outdir .
```

The values in the table above are what it measured for *this* clip. Run it
per video rather than copying them — a different script or pose moves her, and
the tool re-derives the crop from the actual silhouette. Reasoning, and the two
ffmpeg approaches that don't work, are in agent 6's **Sarah Opening → Step 5**.

## The Studio-API test, and what it ruled out

`TEST_4scene_1to1.mp4` was a real 4-scene render (Sarah intro + three narrated
demo scenes) to see whether the whole video could be built by API instead of by
hand in the editor. It worked mechanically — assets uploaded, rendered in ~45s,
1080×1080 out, Sarah's narration over our footage — but two results argue
against using it for this video:

1. **The square was 44% padding.** The composition came out as a 9:16 strip
   pillarboxed inside the 1:1 canvas (content 608 of 1080px), with the demo
   footage small. `ffprobe` reported a perfect `1080x1080`; only looking at a
   frame showed the problem.
2. **Narration length truncates the demo.** The voiceover drives scene
   duration, so a 2.5s line over a 3.4s clip silently cut 0.9s of footage.

Neither is fatal on its own, but combined with **no avatar-over-video
compositing in the API at all** (scenes are whole-frame — avatar *or* video),
the corner-avatar look this project wants is editor-only.

**Open, and worth one cheap test:** whether an all-`video` studio render, with
no `avatar_video` scene, fills 1:1 properly. If it does, the API could still
build the demo body with the Sarah opening prepended locally.

## Build steps (HeyGen editor)

Start from the blank **`+ New video`** tile — never a named template thumbnail,
which silently loads that template's own fixed design. Then per scene: upload
the segment (Media → Video), **scrub the timeline immediately** or the canvas
renders blank white, Set as BG, avatar → Pamela
(`468eabb3326a4d8587ba29d065b1eba7`), voice → Derya
(`04d0ae1d0af2489ca7d3bb402a39a890`), Layout → Circle (intro stays Original,
full-screen), Avatar Background → Remove, position, then paste the verbatim
line.

**Save as Template BEFORE Generate**, so the scene structure survives
independently of the render.

---

## FINISHED — 2026-08-16

The complete video is **`video/ski-demo_first-time-ordering.mp4`** — 74.0s,
1080×1080, h264 + aac. `FINAL_video.mp4` in this folder is the assembler's
output; the copy in `video/` is the deliverable, so re-running the assembler
never touches it.

Built with:

```bash
.claude/agent-tools/venv/bin/python \
  .claude/agent-tools/6_end-customer-help-video-creations/render_narration.py "<this folder>"
.claude/agent-tools/venv/bin/python \
  .claude/agent-tools/6_end-customer-help-video-creations/assemble_video.py  "<this folder>"
```

**On screen per scene** — every scene ran at its clip's natural length except
**scene 4**, whose narration came in 1.2s longer than predicted, so its clip
holds the last frame for 1.5s. Nothing else needed a hold.

**Two structural decisions baked into the build:**

- **The demo does not start under the bridge line.** Scene 1's first frame is
  held while Sarah says the corner-transition, then the clip plays with its own
  narration. Otherwise scene 1's footage was half-consumed before its line
  began, and "Enter your email…" landed over the code screen.
- **Scene 7 carried two 1s pauses** until v14, spliced locally at the
  inter-sentence silences (13.0s → 15.0s). HeyGen's script field has no SSML, so a
  pause can never be requested from the API — see agent 6. **Removed 2026-08-20**:
  they added silence without adding clarity, and the segment was held instead.
  ⚠ Removing `pauses` does NOT delete `sarah-scene-07-paused-alpha.webm`, and the
  assembler prefers a `-paused-` clip unconditionally — it is in
  `scenes/z_History/20260820-130713/` so the plain 13.00s clip wins.

**Cost:** 11 narration clips for ~$2.30 (~$0.21 each) on that build. v14
re-rendered 5 for **$1.70** (~$0.34 each). ⚠ Per-clip cost varies — the tool's
$0.40 quote is a ceiling, and the run's own `wallet before`/`wallet after` lines
are the only figure worth quoting.

**VTT accuracy at real scale:** the measured 3.44 words/sec predicted the eleven
rendered clips to a mean error of +0.09s, and total dead air of 10.4s against an
actual 10.5s.

⚠ **Still nowhere to deliver it.** `Rentify_v10` has no help-video support — no
`help_videos/`, no `playback_ids.json`, no Mux reference in `web/src`. That needs
code inside that repo, so it is a **`V` item** for `ToDo_Rentify_v10.md`, not
something fixable here.

---

## v14 — 2026-08-20. Every scene now fits its line.

`video/ski-demo_first-time-ordering_v14.mp4` — **88.8s, 25fps, 1152×1152, 5.4 MB.**
Words behind it: `video/script_v14.json`.

**The defect this build existed to fix.** Five scenes were *longer in speech than
in footage*. The build does not fail on that — it freezes the segment's last frame
and Sarah keeps talking. On scene 10 the frozen frame was the **dashboard**, held
under "your order is complete", and scene 11 then opened on that same dashboard.
Only the VTT's negative gap column named it.

**Fixed by holding frames inside the segments** — copied frames at the source
rate, never slowed footage:

| # | scene | was | now | held on |
|---|---|---|---|---|
| 2 | neworder | 6.2s | **4.0s** | *trimmed* — its line had been cut to 8 words |
| 4 | search | 6.5s | **9.4s** | opening, highlighted dropdown, dropdown open, Check availability |
| 6 | additem | 2.2s | **5.2s** | the order review page |
| 7 | requirements | 12.0s | **14.1s** | opening form, completed form |
| 8 | checkout | 5.8s | **6.4s** | opening |
| 10 | complete | 3.0s | **7.0s** | "Your order is completed" |

Scene 6 is the one worth remembering: the page its line is *about* was on screen
for **0.28s** under a 5.2s line. The segment read as 2.2s and merely tight; only a
per-frame state profile showed the real number.

**Five narration clips were stale** — still speaking v13's words. Found by
comparing `estimated-word-time` against `actual-word-time` in `script.json`;
scene 5's clip was 6.7s from its line. Re-rendered for **$1.70**. The estimate
held to 0.6s or better on all five.

**`script.json` now carries four fields per scene**: `estimated-word-time`,
`actual-word-time`, `segment-length`, `segment-frames`. The last two are a
snapshot — refresh them from disk whenever a segment changes.

**Still open:** scene 10's final 0.6s is the dashboard, arriving after Sarah has
finished and duplicating scene 11's opening picture. Trim it if it reads badly.

## v15 — 2026-08-20. The video no longer opens on Sarah mid-word.

`video/ski-demo_first-time-ordering_v15.mp4` — **90.3s, 25fps, 1152×1152, 5.4 MB.**

**The defect.** Every build up to v14 opened on the intro clip's frame 0, and that
frame is Sarah **mid-syllable** — mouth wide open, eyes closed. HeyGen trims the
render to the first audio sample, so there is no lead-in. Nothing was wrong with
the pipeline; there was simply nothing in front of her first word.

**The fix.** 1.52s of **real idle footage** prepended to
`sarah_clips/sarah-intro-1152-alpha.webm` (4.82s → **6.34s**). She sits,
blinks once, then speaks. Not a frozen frame — a freeze for a second and a half at
the very start is exactly the defect the idle clip exists to avoid.

### Matching the idle clip to the intro — the numbers, so this is repeatable

The two are **different HeyGen renders at different sizes**, so Sarah is not the
same size in each. Measured, not guessed:

| | intro | idle clip |
|---|---|---|
| source | `sarah-intro-alpha.webm`, 1920×1080 | `sarah-idle-20s-alpha.webm`, 608×1080 |
| her head width | 217px | 204px |
| head centre x | 540.5 | 316.0 |
| bbox top | 126 | 115 |

→ scale **1.064** (`scale=647:1149`), overlay at **x=204, y=4** on a 1152×1152
transparent canvas. After that the two agree exactly: head width 217, centre
540.5, bbox top 126 in both.

⚠ **Match on the HEAD, not the alpha bbox.** The bbox bottom tracks her hands,
which move constantly — the same reason `fade_frames --align` makes seams worse.

### Choosing which 1.52s

All 500 idle frames were measured against the intro's first frame; the span was
taken to **end** on the closest match, **frames 127–164**:

- join frame is **2.03%** from the intro's opening pose
- the span moves **0.03%/frame** (a talking clip runs 2–4%) — calm, not frozen
- she blinks once inside it, so it reads as alive

⚠ Those frames are also inside `assemble_video.py`'s idle pool, which allocates
from the same 500 frames for scene gaps. v15's allocations (13–29, 32–44, 90–111,
166–189, 198–221, 448–456) miss 127–164, so no motion repeats. **A different
store, or a changed gap, could collide** — check the build log's idle lines.

### The seam is a hard cut ON PURPOSE

Closed mouth → speaking measures **1.94%** across the whole frame but **8.52%
across the face** — above `fade_frames`' 5% cap, and correctly so: blending a
closed mouth into an open one is a double exposure, not a fade. The cut lands on
the exact frame the audio starts, so the eye reads it as *her beginning to
speak*. Audio verified silent to **1.50s**.

⚠ This is the framing-dependence trap again: the full-frame number said "safe to
fade" and the number that matters said the opposite. **Measure in the region the
viewer looks at.**

### Verified

Alpha survived (overlaid on magenta — `ffprobe` reports `yuv420p` on correct
alpha output and cannot be trusted); 2254 frames ÷ 25 = 90.2s; the output file
was confirmed to exist and probe, not assumed from the exit code.

Old clip: `sarah_clips/z_History/20260820-140512/`.

### Open on this store

- **`script.json`'s intro `duration` is stale** — it says `4.83`, the clip is
  **6.34s**. Only the VTT reads it, so the *video* is correct; the VTT's total
  reads 87.6s against a real 90.3s. Refresh it from the file.
- Scene 10's final 0.6s is the dashboard, arriving after Sarah has finished and
  duplicating scene 11's opening picture. Trim if it reads badly.

## Resume here

**This video is done.** Nothing is half-finished. If you are picking this up
cold, the useful next moves are all *other* work.

**To make the same video for another store** (canoe-demo, bike-demo,
alpine-sports) — every store already has 5/5 recorded runs in its `raw_mp4/`:

1. Pick that store's recording and run **`cut_segments.py`** — it aligns the flow
   log's `▶` stamps against `RECORDING_STARTED_AT` and finds the boundaries. The
   timestamps in this file are specific to this take and will be wrong for another.
   Then **`--hold`** each segment out to fit its line (see v14 above); a segment
   shorter than its narration fails silently, by freezing.
2. Copy this `script.json`, rewrite the lines for that store's catalogue, and
   run `vtt.py` until no scene is flagged. Free, and it is where the video is
   actually won or lost.
3. `build_sarah_opening.py` → `render_narration.py` → `assemble_video.py`.
   Budget ~$0.40 a scene and read the wallet lines for the real number.

**Four stores now have a video** — ski-demo, bike-demo, canoe-demo,
alpine-sports (all built 2026-08-20). ⚠ Only ski-demo has had the v14/v15
treatment; the other three are still **30fps output** and have not had their
segments held out to fit their lines. Expect the same defects there.

**Delivery is still blocked.** `ToDo_Rentify_v10.md` **V3** — v10 has no way to
serve a help video. These exist partly to make that ask concrete rather than
hypothetical.

**Two open defects found while building this**, both filed as `ToDo.md` **P4.17**
(a) and (b): `resolveRentalWindow` rejects `forDays < 1` so a same-day window
cannot be written in mock-user data, and the party flow ignores an invitee's
window entirely — which makes `tests:list`'s warning about it unreachable.

**Wallet:** **$22.45** as of 2026-08-20 (was $6.10 at the v13 build; topped up since). `GET /v3/users/me` for the live figure — never quote this line, it goes stale.

**The one trap that will cost you an hour:** `-c:v libvpx-vp9` on *every* decode
of an alpha WebM, including `-f concat`. It has bitten three separate ways and
the file always still reports `yuva420p`. Verify transparency by overlaying on
magenta and reading a corner pixel — never by trusting metadata.
