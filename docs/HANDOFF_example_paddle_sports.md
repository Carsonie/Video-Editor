# HANDOFF — Paddle Sports "First Time Ordering" video
# Date: 2026-08-05
# Read this first if picking this back up cold, or if something goes wrong
# mid-build and we need to recover to a known-good point.

---

## Where we are right now

We built a full ffmpeg-composited version of this video (raw OBS recording +
HeyGen avatar clips, manually overlaid/bridged/crossfaded) through several
iterations, landing at **`final/v-37.mp4`** — this is a real, working,
correct-alpha, no-freeze, no-double-play video. **It is being kept as a
fallback and is NOT to be deleted or overwritten.** If the HeyGen-native
rebuild below runs into trouble, `v-37.mp4` is the safe place to fall back to
and ship from.

**We are now pivoting away from the ffmpeg-bridging approach** (too much
synthetic shifting/sway in the gaps, per direct user feedback) **and rebuilding
the avatar-overlay + scene composition natively inside HeyGen's own "Scene by
scene" editor** (AI Studio), which we confirmed live in the browser has:

- **Native corner-avatar overlay**: on any scene's Avatar & Voice panel →
  `Avatar Background: Remove` (transparency) + `Layout: Circle` gives a
  draggable, resizable (Radius/Zoom sliders) transparent circular avatar
  overlay sitting on top of whatever's behind it — this is the *built-in*
  version of the corner-overlay compositing we were hand-rolling in ffmpeg.
- **Media → Video tab**: direct video upload (drag-and-drop or browse) for
  using our own screen recording as a scene's background.
- **"Add scene" builds a NEW empty scene** (its own avatar/script/media) — it
  does **not** import one of our 14 already-generated clips as a ready-made
  scene. Each scene needs to be configured fresh in this editor.
- Scenes **concatenate sequentially** (like a slide deck) — each scene is a
  discrete segment with its own background + avatar, not one continuous
  timeline. This is why we're about to cut the demo into 11 separate segment
  files (one per scene), matching our already-approved segmentation.

## Sarah's locked identity (use in every scene)

| Field | Value |
|---|---|
| avatar_id (Pamela look) | `468eabb3326a4d8587ba29d065b1eba7` |
| voice_id (Derya, Starfish) | `04d0ae1d0af2489ca7d3bb402a39a890` |

In the web editor, Scene 1 currently defaults to an unrelated old avatar
("Summer Santa" — leftover from a different, older project, not ours). Use
**"Change avatar"** and search for **Pamela** to switch to the correct one
before generating anything.

## The approved script (verbatim — already used to generate the 14 API clips)

| # | Segment | Screen window (demo-relative, in `source/RAW-2.mp4`) | Sarah says |
|---|---|---|---|
| — | Intro (full-screen) | — | "Hi. I'm Sarah. Let me show you how to place your first order with Paddle Sports." |
| — | Corner transition | — | "Let's get started. Here are the steps to complete your first paddleboard rental." |
| 1 | Login | 0.0–7.5s | "When we send you a verification code, enter it here to securely log in." |
| 2 | Start a New Order | 7.5–12.3s | "From your dashboard, just tap New Order to start renting your equipment." |
| 3 | Add Yourself | 12.3–18.5s | "Add yourself to the order so we know who's renting the equipment." *(wording fixed from "gear" 2026-08-05)* |
| 4 | Search & Select Equipment | 18.5–26.9s | "Search for your equipment, then pick the paddleboard and color you'd like to rent." |
| 5 | Choose Rental Dates | 26.9–30.8s | "Choose the dates you'll need your equipment." |
| 6 | Add the Item | 30.8–34.5s | "Add the item to your order to continue." |
| 7 | Review & Sign Agreement | 34.5–37.0s | "Review and agree to the rental terms." |
| 8 | Checkout | 37.0–40.0s | "Continue on to checkout when you're ready." |
| 9 | Payment | 40.0–46.1s | "Enter your payment details to complete your rental securely." |
| 10 | Order Complete (held end-card) | 46.1s, no natural duration — held ~4s | "Your order is complete — you'll get a confirmation right away." |
| 11 | Order History (held end-card, closing) | no natural duration — held ~4.5s | "You can always find your rental in your Order History. Happy paddling!" |

Segments 10 and 11 have almost no real screen time in the raw recording
(~50ms each — just page transitions) — we built short frozen-frame "held"
clips for these in the ffmpeg version (grab a still frame, hold for a few
seconds). Same treatment likely needed for their HeyGen scene backgrounds,
**unless** the web editor turns out to have its own per-scene
freeze/loop/hold option for video backgrounds — check for this before
manually building held clips again.

## What's already on disk

- `source/RAW-2.mp4` — the cleaned, head-trimmed, canonical-spec demo
  (1152×962, 30fps) — 49.27s, covers Login through the start of the Logout
  demonstration (which we exclude/don't use past ~46.2s).
- `temp/intro.mp4`, `temp/corner.webm`, `temp/seg-{login,neworder,addperson,
  search,dates,additem,agreement,checkout,payment,complete,history}.webm` —
  all 14 HeyGen-generated avatar clips (API-generated, verbatim script,
  verified alpha/duration), matching the table above. These also exist as
  individual assets in the HeyGen account's Projects (visible in the web UI),
  but per the finding above, the Scene-by-scene editor can't directly import
  them as ready-made scenes — they're only useful as audio-source reference
  or for the ffmpeg fallback path.
- `final/v-1.mp4` through `final/v-37.mp4` — the full ffmpeg build history.
  **`v-37.mp4` is the current best/safe fallback.**
- `.claude/agents/6_end-customer-help-video-creations.md` — has the full
  reviewed pipeline docs, Sarah's spec, and the 2026-08-05 review findings
  (OBS_Staging as source, spec mismatches, etc.) — read this for full context
  on the project's conventions if picking this up fresh.

## Next immediate steps (in order) — updated 2026-08-06

1. ~~Cut the 9 live segment clips + 2 held end-cards.~~ **Done** — all 11
   `scenes/scene-*.mp4` files exist, cut with the locked encoding standard
   below (faststart included). Nothing left to cut.
2. **In progress**: user is building out **all 11 scenes** in the HeyGen web
   editor directly (moved past the smaller 4-scene test — went straight to
   the full build once the blank-canvas-scrub bug was solved). For each
   scene: add scene, upload that segment's clip as background (Media →
   Video, then **immediately scrub the timeline** to force it to render —
   see the UI-quirks section below), Set as BG, set avatar to Pamela, Layout
   → Circle (except the intro, which should stay Layout → Original,
   full-screen), Avatar Background → Remove, position/resize, type in that
   scene's script verbatim (see the table above).
3. **Canvas aspect ratio is still unresolved — a real open item, not
   forgotten.** The original design intent (asked for explicitly by the
   user) is **near-square (~1:1)**, for a **mobile-first modal popup**
   display context — this is a genuine product requirement, not a cosmetic
   preference. In the editor: tried finding a direct 1:1 preset (not found
   yet), tried landscape (worked as a preset but is the wrong shape for the
   modal use case), and the user is now proceeding in **portrait** as a
   first pass specifically to build familiarity with the editor's mechanics
   — explicitly **not** the final target shape either. **Before this build
   is considered done, the canvas needs to actually be resolved to the
   correct near-square/1:1 shape** — don't let "portrait working" get
   mistaken for "aspect ratio solved." Revisit by deselecting all elements
   (click empty canvas / Escape) to find project-level canvas/resolution
   settings, distinct from any element's own Position & Size.
4. Let HeyGen's own scene transitions handle the between-segment motion —
   don't rebuild the boomerang-bridge system again.
5. Export/render the final video from HeyGen once all 11 scenes (+ intro)
   are built, reviewed, and the canvas shape is actually correct.
6. Once satisfied with the result, use **"Save as Template"** (see below)
   to make this reusable via the API for future videos.

## Scene video encoding standard (locked 2026-08-06)

All `scenes/scene-*.mp4` files are cut with:
```
ffmpeg -ss <START> -i source/RAW-2.mp4 -t <DUR> \
  -c:v libx264 -c:a aac -pix_fmt yuv420p -r 30 -movflags +faststart \
  scenes/scene-<NAME>.mp4
```
i.e. our original settings, **plus `-movflags +faststart` added permanently**.
Nothing else. We spent real effort diagnosing a HeyGen upload/preview bug
(see below) that turned out to be a pure UI rendering quirk, not a file
problem — so color-tag stripping, audio removal, and bitrate bumping were
all diagnostic dead ends, not real fixes, and are deliberately NOT part of
the standard. faststart is kept anyway since it's harmless, standard web-video
practice, and cheap insurance for other tools even though it wasn't the
actual cause here. The `scenes_web/` experimental folder (v1/v2/v3-noaudio
variants) was deleted once this was confirmed — don't recreate it.

## HeyGen Scene-by-scene editor — UI quirks discovered live (2026-08-06)

- **New video/media dropped onto the canvas renders blank/white until the
  timeline playhead is manually scrubbed.** Symptom: uploading a clip shows a
  split-second flash of the frame, then goes blank white — looks exactly like
  a broken/corrupt file. It is NOT a file problem. It's a canvas render bug:
  the preview never paints the first frame of a newly-added clip until you
  manually drag the little playhead triangle on the scene's timeline bar at
  the bottom. Once scrubbed even slightly, the frame renders and stays
  correct from then on. **Fix: after dropping in any video, immediately drag
  the timeline scrubber to force a repaint — don't assume the file is bad.**
  Confirmed via a real diagnostic chain (all ruled out, none were the actual
  cause, but good to know they're clean): faststart/moov position, BT.709
  color-range/space/primaries/transfer tags, audio sample rate, audio
  presence, bitrate, frame rate/timebase — none of these mattered. A totally
  independent synthetic test video (ffmpeg lavfi color bars) had the exact
  same blank-until-scrubbed behavior once we knew what to look for, and a
  plain static PNG image loaded fine immediately (no scrub needed) — which is
  what pointed us toward "this is frame-render-on-load specific to video,"
  not a data/encoding issue at all.
- Uploading a video from a **template's own thumbnail tile** (e.g. "Service
  Improvements and Optimizations") drops you into that template's own fixed
  design (placeholder lorem ipsum text, graphic elements, avatar embedded in
  a non-circular fixed box) — not a blank canvas. Always start from the
  literal blank **"+ New video"** tile (dashed border, plain `+` icon), never
  from a named/preview template thumbnail, when building from scratch.
- To set an uploaded video as a scene's background: drag it from Media onto
  the canvas, select it, and use the **"Set as BG"** button in the floating
  toolbar that appears above the selected element.
- Each scene's video-background element has its own **Playback** dropdown
  (Freeze / Loop / fit_to_scene-equivalent) and **Volume** slider — confirm
  Playback is NOT set to Freeze for scenes that should play live motion.

## Template scene-count flexibility — two different mechanisms, don't conflate them (2026-08-06)

Confirmed via HeyGen's own in-app AI Assistant (asked directly) and reconciled
against the API docs research (see agent #6's file, "Session 2026-08-06"):
there are **two separate ways** to work from a template, with different scene
count rules:

1. **Pure API generation** (`POST /template/{id}/generate`) — confirmed via
   docs: capped at the template's original scene count. `scene_ids` can
   select a *subset* per call, but can never add scenes beyond what the
   template defines. This is the fully-automated, zero-UI-touch path.
2. **"Start a new project from this template" in the UI** — per HeyGen's own
   AI Assistant: this creates an *editable copy* of the template's scenes as
   a real, fully-editable new project. Since it's a normal project at that
   point (not a locked API-generation target), you CAN add/duplicate/delete
   scenes on it freely — same as building any project from scratch.

**Practical implication**: a future video needing more scenes than this
template defines is achievable, but only via the UI path (duplicate the
template, then manually configure the extra scenes — same Circle/Remove/
position work as any new scene, no shortcut there). The pure-API path stays
hard-capped at the template's original scene count. Don't assume "we can
always just add scenes via the API later" — that's only true if a human is
doing it in the editor, not for automated generation.

## How to save a project as a template (2026-08-06, per HeyGen's own AI Assistant)

In the AI Studio editor's top bar: click the **"..." (More menu)** next to
the project title / Generate button → **"Save as Template."** This was an
open question in the original plan (we didn't know if Scene-by-scene
projects had a one-click template conversion) — now confirmed it exists.
Once the 4-scene test is validated, this is the mechanism to make it
reusable via the API going forward (see "Template scene-count flexibility"
above for what is/isn't then automatable from that saved template).

## Save order: Template BEFORE Generate (2026-08-06, per HeyGen's own AI Assistant)

Confirmed sensible sequencing, straight from HeyGen's in-app AI Assistant:

1. **Save as Template first** (`...` menu near Generate → "Save as Template")
   — preserves the layout/scene structure as a reusable asset.
   2. **Then click Generate** to render the actual output video.

Doing it in this order means the reusable template exists independently of
whichever specific render you generate from it. The draft project itself
auto-saves continuously in Projects regardless, so there's no risk of lost
work either way — but Template-then-Generate is still the right order to
actually end up with a reusable template, not just a rendered video.

## Script drift caught before first Generate attempt (2026-08-06)

Before generating the 12-scene draft, a screenshot review caught the
in-editor script text had drifted from the approved verbatim table in
several places — **do not generate until these are fixed**, since HeyGen
speaks exactly what's typed (per this project's own locked verbatim-script
rule):

- **Search scene**: "the **Paddleboard** and **colour**" — capitalized +
  British spelling; approved text is lowercase "paddleboard and color."
- **Add Item scene**: drifted to *"This adds the items to your order,
  allowing you to continue"* — approved text is *"Add the item to your
  order to continue."*
- **Agreement scene**: drifted to a much longer line mentioning "any
  questions we might have to properly prepare you rental equipment" (note:
  "you" should be "your" even in the drifted version) — approved text is
  the short *"Review and agree to the rental terms."*
- **Payment scene**: drifted to *"Enter your payment details into
  **Stripe** to complete your rental"* — **this is a factual error, not
  just wording drift.** Paddle Sports uses the mock-payment bypass, never
  real Stripe (confirmed in `testing-runner-manager`'s own rebuild-reference
  docs) — the avatar would be stating something untrue about this specific
  store's checkout if generated as-is.
- **Order Complete scene**: the script field literally starts with the
  text **"Playback → Freeze)"** — looks like UI label text accidentally
  pasted into the actual spoken-script input, which would have the avatar
  say that out loud before her real line.

Root cause suspected: the in-editor "Ask AI" assistant or an autocorrect/
autocapitalize pass touched the pasted script text along the way. Whatever
the cause, **re-check every scene's script box against the approved table
above before the first real Generate** — this was caught by chance via a
screenshot, not systematically, so don't assume only these 5 are affected.

## If something goes wrong

Fall back to `final/v-37.mp4` — it's a complete, correct, working video (no
black-box alpha bug, no double-play, no frozen-forever segments). It just has
more synthetic shifting/sway in the gaps than the user wants for a final
ship. It's a legitimate deliverable if the HeyGen-native rebuild stalls or
doesn't pan out.
