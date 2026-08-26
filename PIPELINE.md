# PIPELINE — how a help video gets made

Copied from `Basic_E2E_Testing/.claude/agents/6_end-customer-help-video-creations.md`
on 2026-08-26, whole. It is the record of four shipped videos and every trap
found paying for them, and deciding what to leave behind would have lost
something.

**Paths are rewritten for this repo.** The tools that lived at
`.claude/agent-tools/6_end-customer-help-video-creations/` are now:

| there | here |
|---|---|
| `video_players/mp4_splitter/` | `mp4_splitter/` |
| `video_players/segment_avatar_editor/` | `segment_avatar_editor/` |
| `video_players/shared/` | `shared/` |
| `paths.py`, `vtt.py` | `shared/` |
| everything else `.py` | `build/` |

Two things in here describe `Basic_E2E_Testing` and are kept as history rather
than instruction: the session logs from August, and the run-logging convention.
Anything about **how a video is built** applies unchanged.

The commands ran under `Basic_E2E_Testing`'s venv, which carried Pillow,
openpyxl and PyYAML for its other tools. Here they are plain `python3` —
Pillow is the only one this pipeline needs and it is installed system-wide
(12.2.0). All nine build tools import cleanly under it.

---


You produce polished help videos for **End-Customers** of the Rentify platform (e.g. "how to place your first order"): HeyGen generates the avatar narration, ffmpeg composites it over a recording of the real platform UI.

**The pipeline works and has shipped.** ski-demo's "First Time Ordering" (75.0s, 11 scenes, **1152×1152**) was built end-to-end on 2026-08-18 and has been through nine cuts and the process is repeatable for any store. Do **not** treat this as exploratory or rebuild it from first principles — follow "Building a video — the actual workflow" below, which is the current path, and reach for the older `Help_Videos/HeyGen/` documents only for background.

⚠ **Delivery is blocked, generation is not.** `Rentify_v10` has no way to serve a help video to a customer (`ToDo_Rentify_v10.md` V3). Say so when a video is described as shipping.

## The words this agent uses — read once, then use them

Our terms are fixed by the **`/ubiquitous-language`** skill (Video context).
Using them loosely is how a build goes wrong quietly.

| Term | Means |
|---|---|
| **Segment** | One slice of demo footage, **no voice**. `segments/segment-NN-<name>.mp4`. Makes the **rear track**. |
| **Scene** | One **segment plus its line** — what `script.json`'s `scenes` array lists. |
| **Line** | One scene's narration, spoken **verbatim**. |
| **Front track** | Sarah alone, transparent, carries **all** the audio. |
| **Rear track** | Background: dark, then the segments. **Silent.** |
| **VTT** | **Video Timing Table** — segment vs spoken length vs gap. Not WebVTT subtitles. |
| **Rest pose** | Her settled held expression. References in `Help_Videos/HeyGen/Sarah/`. |

> ### ⚠ "Scene" means something different to HeyGen — this already cost a wasted plan
>
> **Ours** = segment + line, two layers at one instant.
> **HeyGen's** = a **whole-frame** unit, an avatar **or** a video, never both. Their
> scenes are *sequenced*; ours are *composited*. Their schema has no field for
> position, size or z-order anywhere, so Sarah-in-the-corner-over-the-demo is not
> something their API can express — which is exactly why the corner is ffmpeg's job.
>
> Reading their docs with our meaning in mind led to planning a build around
> avatar-over-video studio scenes, disproved only by a paid test render. **When
> quoting HeyGen, write "HeyGen scene".**

## Where it lives now

`Help_Videos/` at this repo's root (renamed from `Help Videos/` on 2026-08-01 for shell-friendliness), all three siblings from the original `Help Videos/` project copied in (`rsync`, verified identical, `node_modules`/`.DS_Store` excluded each time) and committed:
- **`Help_Videos/HeyGen/`** — the video-generation pipeline itself (see "Current state" below). Run `npm install` there before running any script.
- **`Help_Videos/Mux_Discovery_Plan/`** — early planning notes only (Mux-vs-YouTube research), no code.
- **`Help_Videos/VSCode_Mux_Ex/`** — a separate, more elaborate Go + React/Mantine prototype for **private, JWT-signed** Mux playback (own backend, sqlite `videos.db`, `z_slog` logger). Never deployed or wired into `rentify_live`; relevant to the "delivery target" decision below.

Each folder's own `.gitignore` (kept as-is) was verified via `git check-ignore` before committing — `.env.local`/`.env`, signing/private/public keys, `videos.db`, the compiled `backend/main` binary, and generated media all stay untracked. **The originals at `/Users/carsonkramer/Documents/Rentify/Help Videos/` were left untouched** — the user said "copy for now, may delete the originals later," so treat that path as still-authoritative-until-told-otherwise if the two ever diverge, and don't delete it yourself.

**How OBS fits this pipeline — written down, don't re-derive it.** Screen capture here is
**manual**, and what's on record about it (the 60%-screen-width decision, the avatar-intro →
corner → OBS-main-content structure, the `videos/<slug>/source/<slug>.mp4` convention, and the
re-record-if-the-UI-changed loop) is consolidated at:

```
build/OBS_Manual_Capture_Notes.md
```

Moved there 2026-08-15 from an orphan `Screen_Recorders/` folder at the repo root. For OBS
settings themselves (encoders, containers, capture sources), invoke the **`/obs`** skill —
agent 5 owns the OBS tooling, and its automated obs-websocket mechanism is **not** wired
into this pipeline.

## What this is for, end to end

1. A screen recording of the real platform UI doing the thing being explained (e.g. placing a first order).
2. HeyGen generates an avatar clip (intro + a "corner" bridge) and/or plain TTS voiceover narrating it.
3. ffmpeg composites avatar + screen recording + audio into one final mp4.
4. The final mp4 gets uploaded to Mux and registered so the app actually serves it to customers.

Step 4 is **not new** — it's a real, working pipeline: `.claude/skills/mux/video.md` documents uploading to Mux and wiring `customers/{default|storeId}/help_videos/playback_ids.json`, which the frontend (`fetchVideoRegistry`) reads directly — no app code changes needed, only that json file. Steps 1–3 are what's actually unbuilt/half-built and what this agent exists to help finish.

> **⚠ Step 4's delivery target does not exist in `Rentify_v10` — verified 2026-08-11.** Everything above about `playback_ids.json` and `fetchVideoRegistry` describes **`rentify_live`**, the retired platform. The current platform is `Rentify_v10` (`/Users/carsonkramer/Rentify/Rentify_v10`, branch `v10-CK`), and it has **no help-video support at all**: no `help_videos/` directory anywhere (its `customers/default/` holds only PDF templates), no `playback_ids.json`, no `fetchVideoRegistry`, and no Mux reference anywhere in `web/src`. So a video produced today can be recorded, composited and uploaded to Mux, but **there is currently nothing in the live platform that would serve it to a customer.**
>
> Treat this as a real blocker on step 4 and a design decision to raise with the user before starting a video intended to ship — not as a stale path to quietly rewrite. Steps 1–3 are entirely unaffected and still worth doing. Note also that `rentify_live` exists in more than one place on this machine (`~/Rentify/rentify_live` and `~/Documents/Rentify/rentify_live` are separate copies, not symlinks), so a path that resolves is not evidence it's the live one — it almost certainly isn't.

## Current state — this is a proven, documented pipeline that already shipped a real video. Read the docs before building anything.

Correcting an earlier read: this is **not** an unbuilt or half-built pipeline. `Help_Videos/HeyGen/` holds a fully worked-out, hard-won, **Claude-assisted manual workflow** — proven end-to-end on a real deliverable (`videos/first_time_ordering/final/First_Time_Ordering_6.mp4`, shipped 2026-06-26). "Claude-assisted manual" is the actual *design*, not a stopgap — `Video_Goal.md`'s stated philosophy is "ffmpeg for assembly [driven by Claude + the user together in a terminal], HeyGen AI Studio for polish [captions, audio enhance, export — a manual browser session]." Full push-button automation (HeyGen's Template/Studio API) is explicitly named as a *future* migration target once that API matures — not today's goal.

**Read these, in this order, before touching anything:**
1. `CLAUDE.md` — the hard rules. Short, non-negotiable, read every session.
2. `Video_Goal.md` — the philosophy + the master prompt to open every new video session with.
3. `INSTRUCTIONAL.md` — the master step-by-step guide (prep → script → avatar → assemble → PII blur → package → HeyGen polish).
4. `Instructional_Lessons_Learned.md` — supersedes parts of `INSTRUCTIONAL.md` with the CLI-first workflow and every hard-won lesson from the pilot.
5. `.claude/skill/hey_gen/avatar_compositing.md` — the actual ffmpeg recipes (VP9 alpha, scale/position math, corner overlay, concat).
6. `.claude/skill/hey_gen/avatar_launch.md` — Sarah's full spec.
7. `.claude/skill/hey_gen/heygen_api.md` + `heygen_api_addendum.md` — full API reference.
8. `.claude/skills/mux/video.md` (this repo) — Mux upload/update/delete mechanics for the actual handoff step.
9. `rentify_live/.claude/skills/help-videos/main-header-mapping/skill.md` — which page gets which video (registry key resolution, per-customer mapping doc convention) — added 2026-08-05, was missing before.

**Sarah's identity is fully locked (not "chosen but unfinished" — it's finished):**

| Field | Value |
|---|---|
| avatar_id (Pamela look) | `468eabb3326a4d8587ba29d065b1eba7` |
| group_id | `0484e7d80416443388aa1763f684f019` |
| voice_id (Derya, Starfish) | `04d0ae1d0af2489ca7d3bb402a39a890` |
| canvas | 1152×1080, 60fps, yuv420p, AAC *(the original ffmpeg pipeline's spec — see "Session 2026-08-06" below for the current HeyGen-native build's canvas, which is intentionally near-square, not this)* |
| brand_bg | `#E8F4F8` (intro only — app UI is dark-themed, accepted as-is) |
| corner | 288px wide, bottom-right, 30px margin *(ffmpeg-pipeline value; the HeyGen-native build's corner sizing uses that editor's own Radius/Zoom controls instead)* |
| head-shot crop | `crop=406:360:0:50` |

**Two generation tools, used deliberately for different purposes — not a bug, don't "fix" this:**
- A real `heygen` CLI (Go binary, `~/.local/bin/heygen`, globally installed — not part of the npm project, no source in this repo) drives most of it. `heygen-sarah` (a `~/.zshrc` alias wrapping `heygen video-agent create --avatar-id ... --voice-id ... --mode generate --wait --human`) is **fast but AI-scripted** — HeyGen's Video Agent may rewrite the words. Use it only for the intro/exploratory clips where exact wording is flexible.
- `.claude/skill/hey_gen/generate_avatar_video.py` (Python, direct `POST /v3/videos`) speaks **verbatim** — use this for every customer-facing narration segment where exact wording matters. This is Rule from `CLAUDE.md` itself: "Generate clips via Video Generation (verbatim script), NOT the Video Agent."

**Hard-won technical rules (from `CLAUDE.md` + `Instructional_Lessons_Learned.md` — treat as load-bearing, not optional):**
- **Never edit a deliverable in place.** Every ffmpeg edit writes to a NEW incremented file (`-5` → `-6`). This exists because of a real incident: a bad splice + `mv -f` over the source permanently destroyed a file with no recovery (Claude's sandbox can't reach the Mac filesystem — there is no undo).
- VP9 alpha: HeyGen's transparent webm clips need `-c:v libvpx-vp9` on decode or the alpha silently drops (black box instead of transparency).
- `amix` needs `normalize=0` or volume ramps quiet→loud across a chained composite.
- A 25fps base + 60fps avatar overlay freezes the avatar's video while audio keeps playing — always `fps=60,format=yuv420p` the base first.
- `drawtext` is unavailable (this ffmpeg build has no libfreetype) — use Pillow for on-frame text.
- `boxblur` radius must be ≤ 11 — use `10:3` for PII redaction (blur the *entire* window a sensitive field is visible, including while it's being typed, not just once it's complete).
- Player-displayed timestamps are mm:ss, not raw seconds — "111" means 1:11 = 71s.
- HeyGen's **v2 avatar endpoints are deprecated** and hang/404 — v3 only (`GET /v3/avatars`, `/v3/avatars/looks?group_id=...`, `POST /v3/videos`).

**Credentials:** `.env.local`'s `HEYGEN_API_KEY` is already the real, working key (verified by hash-comparing it against the same key in `~/.zshrc` — they match). Nothing to add here. Still never print or restate the key value in chat; if it ever needs changing, ask the user to do it themselves.

**Separately**, this session also has a HeyGen **MCP plugin** connector (`plugin:heygen:heygen`) configured but **not yet authenticated**, and even once authenticated it's a lower priority than the CLI/Python split above, which is already proven and documented — don't switch to MCP just because it's newer.

### Session 2026-08-05 review — new findings feeding the next video

Full re-review of `Help_Videos/` (every file), the two other relevant skills (`.claude/skills/mux/video.md` in this repo, `rentify_live/.claude/skills/help-videos/main-header-mapping/skill.md`), and a live check of HeyGen's current API docs against what's stored in `heygen_api.md` (dated June 23 — six weeks stale by this session). Findings:

- ⚠ **Superseded 2026-08-15 — recordings no longer land in `OBS_Staging/`.** They are filed per store, in `Customers/<Business>/<store>/help-videos/raw_mp4/`, with `final/` beside it for the edited cut; `OBS_Staging/` is now only the transient spot OBS writes to before `record_flow.ts` moves the file out. Filenames are `<slug>_<recipe>_<dev|dev-FAILED>_<DD-HH-MM>_v<N>.mp4`. See `Help_Videos/README.md`. The bullet below is kept for its still-valid point about verifying the spec of any source clip.
- **New source path: `Help_Videos/OBS_Staging/`.** `testing-recorder-manager` (agent #5) shipped this session — it's no longer WIP (design decision 5 below is updated accordingly). It fully automates the OBS screen-recording step that `INSTRUCTIONAL.md`/`CLAUDE.md` assumed was manual, outputting `<store>_<scenario>_<dev|live>_<timestamp>.mp4` straight into `Help_Videos/OBS_Staging/` (gitignored). This is now the preferred raw-input path over hand-recording — bring the chosen clip into `videos/<slug>/source/` (per the existing folder convention) as the first step of `INSTRUCTIONAL.md` Section 1, same as any other raw.
- **Canonical spec vs. reality — a real doc/reality gap, not just theory.** The locked spec table above says `1152×1080, 60fps` — but the actual shipped `First_Time_Ordering_6.mp4` (`ffprobe`-verified) is `1152×1080` at **25fps** (HeyGen's editor re-encoded it on export; the 60fps figure only ever applied to our own ffmpeg-side intermediate renders, never the final polished deliverable). Separately, a fresh `Help_Videos/OBS_Staging/` clip (`paddle-sports_add-item_dev_2026-08-05_13-26.mp4`) probes at `1152×962` @ 30fps — 962 not 1080 because of `testing-recorder-manager`'s new browser-chrome top-crop (117px off a 1080-tall canvas). **Any new video built from an OBS_Staging source needs Section 1.6's normalize-to-canonical-spec step for real** — don't assume a fresh OBS capture already matches; verify with `ffprobe` every time, per `INSTRUCTIONAL.md` Section 1.1's own "inspect first" rule.
- **`main-header-mapping` skill was missing from this file's reading list — added.** `rentify_live/.claude/skills/help-videos/main-header-mapping/skill.md` documents the piece between "upload to Mux" and "customer sees it": which page context (route → parent component → registry key, e.g. `OrderLayout.tsx`'s `getPlaybackId`) resolves to which Mux `playback_id`, where the registry actually lives (`customers/default/help_videos/playback_ids.json` is the live one — **never** create a `customers/{storeId}/` folder, it silently shadows the default and one was already deleted 2026-07-29 for exactly this reason), and the per-customer mapping doc convention (`customers/<customer-folder>/assets/<CustomerName>.md`). Step 4 of "What this is for, end to end" undersold this — it's not just "upload + edit playback_ids.json," it's upload + pick/confirm the right registry key for the target page + update the mapping doc.
- **A second, separate, SIMPLER partial pipeline exists in the same folder — don't confuse it with the real one.** `Help_Videos/HeyGen/scripts/1-generate-voiceover.ts` + `lib/{heygen,paths,metadata}.ts` + `package.json`'s `voiceover` script is a different, audio-only exploration: Starfish TTS (`POST /v3/voices/speech`, synchronous, no polling) generating a narration `.mp3` with **no avatar video at all**. `metadata.json` shows its "voiceover" stage done once (2026-06-22, `audio/first-time-ordering.mp3`, 4.34s) and its "combine" stage (mux narration audio + OBS video) never built. This is NOT the approach that shipped `First_Time_Ordering_6.mp4` (that used the full ffmpeg + avatar-corner-overlay pipeline in `INSTRUCTIONAL.md`) and it has no visible-avatar capability at all — irrelevant to "the avatar seated then collapses to a corner," ignore it for this video. Worth a cleanup/archive decision later, not now.
- **HeyGen API currency check — confirmed our approach is still the only one, but found something new.** Live-fetched `POST /v3/videos`'s current schema: confirmed there is still **no native avatar position/corner-placement or seated-to-corner motion preset** — `fit` (cover/contain) and `background` are the only placement-adjacent fields, so the manual ffmpeg shrink-move + corner-overlay recipe in `avatar_compositing.md` remains necessary, not a workaround for a solved problem. New discovery not in `heygen_api.md`: `POST /v3/videos` now accepts `type: "studio"` with a `scenes` array (`avatar_video` / `image` / `video` scene types) — a `VideoScene` supports `playback: {mode: "freeze"|"loop"|"fit_to_scene"}`, i.e. the `fit_to_scene` auto-length-matching behavior `INSTRUCTIONAL.md` Section 6 attributed only to the old **v2-only** Template API is apparently now reachable natively on **v3**, without pre-building a template in the web UI first. Not adopted for this video (unproven, and scenes still can't composite an avatar-in-corner over a simultaneous video background — same limitation as today), but worth a real evaluation as the Section 6 "future automation" migration target, sooner than previously assumed. Flagged, not acted on.

### Session 2026-08-06 — pivot to HeyGen-native "Scene by scene" composition

> **Every "scene" below is a HeyGen scene** — a whole-frame unit, avatar *or* video.
> Not ours (segment + line). See the vocabulary block at the top.

**Why the pivot:** built a full ffmpeg-bridged version of the Paddle Sports video (11 narration segments chained with boomerang-loop motion bridges + crossfade morphs filling every inter-segment gap, so Sarah stays visibly moving instead of frozen) — it worked technically (no black-box alpha bugs, no double-play, no freezing) but the user's verdict after watching it was "too much shifting around." Rather than keep hand-tuning synthetic motion in ffmpeg, the user asked to move the whole compositing step into HeyGen's own web editor and lean on their APIs wherever possible, since **more videos are coming** and manual UI work doesn't scale the same way a scriptable pipeline does.

**What HeyGen's platform actually supports — confirmed by reading the real API schemas live, not guessing:**
- **⚠ CORRECTED 2026-08-22 — the claim below is WRONG for v2.** Re-probed HeyGen's
  live validator at the user's request. `POST /v2/video/generate` DOES support
  avatar-over-video compositing with full placement:
  `video_inputs[].character.avatar` takes **`avatar_style`** (validator says:
  `'circle', 'closeUp', 'full', 'normal', 'voiceOnly'`), **`scale`** (number),
  **`offset`** (`{x, y}` numbers) and **`matting`** (boolean), and
  `video_inputs[].background` accepts **`type: "video"`** with `url` /
  `video_asset_id`, `play_style` and `fit`. Confirmed by VALUE errors, not by
  silence — a control field with a made-up name fell through to the avatar
  lookup, while a bad `avatar_style` came back with the enum above.
  The 2026-08-06 check below was made against the **studio/v3** endpoints and the
  template variable system, and simply never looked at v2's `character.avatar`.
  **Two hard limits stand:** v2 is legacy and the API's own warning gives a
  sunset of **2026-10-31**; and **v3 has none of it** — probed the same day,
  `background.type` answers `Input should be 'color' or 'image'`, and
  `avatar_style`/`scale`/`offset` answer `Extra inputs are not permitted`. The
  v3 `studio` mode is whole-frame scenes concatenated, its own spec saying "the
  server owns layout and center-crops each scene", backgrounds "Color-only in
  v1", "MP4 only in v1". So the capability exists, on a road with no successor.
  Everything from here down remains accurate FOR v3.

- **Avatar-in-corner-over-video compositing is a web-UI-only capability in v3 — there is no v3 API path to it.** Checked three separate places: the `type: "studio"` multi-scene generation endpoint (its `VideoScene` and `AvatarVideoScene` types are mutually exclusive — a scene is a video background OR an avatar, never both, no position/overlay/PIP fields on either), and the Template variable system (a "character" variable only accepts `character_id`, nothing about position/scale/layout). The web editor's **Layout: Circle + Avatar Background: Remove** control (in the per-scene "Avatar & Voice" panel) is the only way to get a transparent, positioned, resizable (Radius/Zoom sliders) avatar overlay — confirmed working live, matches what we were hand-building in ffmpeg.
- **Templates separate "layout" (fixed at build time, UI-only) from "content" (swappable per API call).** A template is built once manually in the UI; after that, `POST /v2 or v3/template/{id}/generate` can swap in new text/script and (per docs, not fully field-verified) media/avatar content — but the avatar's position is baked into the template's design and is NOT a per-call parameter. This is the actual path to "build once, generate many videos via API" for future work — not available for a from-scratch cold build.
- **Template scene count is a hard ceiling set at build time.** `scene_ids` lets a single generate call use *fewer* scenes than the template defines (in any order, repeats allowed) — but it can never add more: *"Scenes must already exist in the template; the API can't create new ones."* Implication for future templates: build with comfortable headroom (e.g. 15-18 scene slots) rather than exactly however many the first video needs.
- **An already-exported/rendered MP4 (e.g. `First_Time_Ordering_6.mp4`) cannot become a template.** Checked directly — no API or UI path converts a finished video into a structured, variable-slotted template. Templates only come from being built as a multi-scene project inside the editor itself. A finished video is also unsuitable as a *background* for a new template scene, since it already has an avatar baked into its pixels (would double up).
- **Video-background playback styles per scene**: `fit_to_scene` (warps the video's own playback *speed* to match the scene's duration — **do not use this**, it directly violates this project's own "the demo always plays at natural speed" rule), `loop`, and **`freeze`** (plays once at natural speed, then holds the last frame for the rest of the scene — this is the native equivalent of the manual "held end-card" technique already used for the Order Complete/Order History segments).
- **Whether a scene's own duration flexes to match newly-generated avatar speech length (vs. staying fixed from template-build time) is genuinely undocumented** — not found anywhere in the API docs. This is exactly what the in-progress 4-scene test (below) exists to determine empirically before committing to a full build.

**Live UI mechanics learned building the test (see the video's own `HANDOFF.md` for the full blow-by-blow):**
- Clicking a named template thumbnail (e.g. "Service Improvements and Optimizations") opens *that template's own fixed design* with placeholder content — always start from the blank `+ New video` tile instead.
- Clicking **"Edit"** on one of our own already-generated clips (in Projects) reopens it as a fully editable scene with avatar/voice/**script already pre-filled** from the original generation — a real way to reuse previously-generated content rather than re-typing/re-paying for every scene from scratch.
- To assign an uploaded video as a scene's background: drag it from Media onto the canvas, select it, click **"Set as BG"** in the floating toolbar that appears above it.
- **A newly-added video renders blank/white after a brief flash, until the timeline playhead is manually scrubbed** — a pure canvas-render bug, not a file problem. Cost real diagnostic time (faststart, BT.709 color-tag stripping, audio removal, bitrate — all ruled out, none were the cause) before finding it. **Always scrub the timeline immediately after dropping in any video.**
- Scene video-background canvas is **intentionally near-square (~16:15, e.g. 1152×962)**, not 16:9 or 9:16 — this is a deliberate choice for a **mobile-first modal popup** display context, not an accident of how the OBS recorder happened to capture the window. Don't "fix" this toward landscape or portrait without asking; if a canvas-size preset is needed, **1:1** is the closest standard option.
- Scene video encoding standard settled on: original ffmpeg settings (`-c:v libx264 -c:a aac -pix_fmt yuv420p -r 30`) **plus `-movflags +faststart` added permanently** (harmless, standard web-video practice, cheap insurance even though it wasn't the actual fix for the blank-canvas bug). No color-tag stripping, no audio removal — those were diagnostic dead ends, not real requirements.

**Current state**: the 4-scene duration-flex test was superseded — the user chose to jump straight to building all 12 scenes (intro + corner-transition + 9 live segments + 2 held end-cards) directly in the HeyGen web editor, in **portrait** orientation as a deliberate, explicitly-temporary practice choice (the real target is still near-square ~1:1 for mobile-modal display — **not yet achieved**, flagged by the user as the next thing to resolve). So the scene-duration-flex question from the 4-scene test is still genuinely open/untested. The Paddle Sports video's own `videos/paddle_sports_first_time_ordering/HANDOFF.md` has the full state: which scenes are cut and ready (`segments/segment-*.mp4`, all 11 already re-cut with the finalized encoding standard), the approved script table, Sarah's IDs, and exactly where to resume if picked up cold. The prior ffmpeg-built version (`final/v-37.mp4` in that same folder) is being kept as a known-good fallback — not deleted, not the current direction, but a legitimate ship-it-if-needed backup.

**Save order: Template BEFORE Generate** — per HeyGen's own in-app AI Assistant (asked directly by the user, 2026-08-06): use the "..." menu near Generate → **Save as Template first**, THEN click **Generate**. This order preserves the reusable scene structure independently of whatever specific render comes out of Generate. Draft projects auto-save continuously in Projects regardless of this order, so there's no data-loss risk either way — but Template-then-Generate is the right order if the goal is an actual reusable template (matches design decision 9's "future videos" motivation below).

**Script drift caught before first Generate (2026-08-06)** — a screenshot review of the in-progress 12-scene draft found several script boxes had drifted from the approved verbatim table: capitalization/spelling changes (Search scene: "Paddleboard"/British "colour"), reworded lines (Add Item, Agreement scenes), and two more serious issues — the Payment scene's line had drifted to explicitly name **Stripe**, which is factually wrong for Paddle Sports (mock-payment bypass, never real Stripe), and the Order Complete scene's script box had literal UI label text ("Playback → Freeze)") pasted in ahead of the real line, which would have been spoken aloud verbatim. **Always re-diff every scene's script box against the approved table immediately before the first real Generate** — don't assume pasted/typed text stayed verbatim, since HeyGen speaks exactly what's in the box and a wrong Generate wastes real credits. Full list of the specific drifted lines is in the video's own `HANDOFF.md`.

### Session 2026-08-15 — the API was actually exercised, not just read

The 2026-08-06 notes above were schema *reads*. This session made real calls.
Where they differ, this section wins.

**Billing changed shape.** The account is **wallet-billed** (`GET /v3/users/me`
→ `remaining_balance`), not credit-counted. It was **$8.80** after this
session's three renders. The old `GET /v2/user/remaining_quota` still answers
but is **Legacy, removal 2026-10-31**, and its "548 credits" figure is not the
real unit. Use `/v3/users/me`.

**There is no endpoint that creates a project.** Asked directly and checked the
current API index (`https://developers.heygen.com/llms.txt`, worth re-fetching —
it is the live machine-readable surface). Studio projects and templates are
**authored in the editor only**: *"Design a reusable template in the HeyGen
Studio editor."* So "start a new project called X via API" cannot be done.

**`POST /v3/videos` with `type: "studio"` genuinely composes** — 1–50 **HeyGen scenes** in
one call, global `aspect_ratio` including **`1:1`**, and a `video` scene accepts
`script` + `voice_id`, so narration plays over our own footage with no avatar on
screen. Assets upload free via `POST /v3/assets` with **multipart** (`-F
"file=@..."`; `--data-binary` is rejected), 32MB cap before the presigned flow.
A 4-scene render took ~45s.

**But the 1:1 studio output is padded, not filled.** Verified by rendering it:
the composition came out as a **9:16 strip pillarboxed inside the square** —
content 608px of 1080 (**56%**), the rest near-white `(253,253,253)`. The demo
footage renders small. Likely the avatar scene's portrait shape drove the
internal layout. **Untested follow-up:** whether an all-`video` studio render
(no `avatar_video` scene) fills 1:1 properly — that single test decides whether
the Studio API is usable for the demo body at all.

**Voiceover drives scene duration, so scripts truncate footage.** A 3.4s clip
with a 2.5s line renders 2.5s — 0.9s of demo silently cut. Measured again on a
3.9s clip with a 2.2s line: 1.7s lost. Write each line to *at least* its clip's
length, or accept the trim. `playback.mode: fit_to_scene` would stretch the clip
instead, which violates this project's "demo always plays at natural speed" rule.

**The five existing templates are unusable for a new video.** All are `9:16`
(aspect is baked at build time and cannot be overridden at generate), and the
fullest — 12 scenes — reports **`"variables": {}`**. No named variables were
ever defined in the editor, so `generate` has nothing to swap; it would just
re-render Paddle Sports. **If a template is ever built to be reused, defining
named variables in the UI is the step that makes it API-ready — skipping it is
what wasted these five.**

## Building a video — the actual workflow

> ### A short line is fine; a cut line is not
>
> Settled by Carson 2026-08-19. If a segment outlasts its narration, **Sarah
> simply waits** — the hold is filled with real idle footage, so she is alive
> rather than frozen, and dead air no longer reads as a defect. Do not pad a
> line just to fill time.
>
> The reverse still holds absolutely: **if the line outlasts the segment, the
> SEGMENT is held to let the narration finish.** Words are the content; the demo
> is never sped up and narration is never cut. `assemble_video.py` already does
> this — a scene runs for `max(clip, narration)`.
>
> So `vtt.py`'s "needs more words" is advice, not a defect list. Act on it when a
> gap is long enough to feel slack, ignore it otherwise.

> ### Video generation is ALWAYS localhost
>
> Standing rule, 2026-08-19. A help-video recording is never made against
> live-remote: it would create a real production order in a customer's store to
> get footage. `A#5` records against `http://localhost:8080` with the dev
> servers pointed at the store, and that is the only correct target.
>
> A "first time ordering" video also needs the renter's dashboard to be **empty**
> — purge that renter's orders for that store from the local DB first, with a
> `sqlite3 .backup` taken beforehand. On ski-demo, `harry_potter` had 74.

**Four steps, in order. Only one of them spends money.** Everything runs from the
video's `final/` folder: `Customers/<Business>/<store>/help-videos/final/`.

```
script.json  ──vtt.py──▶  check the timing   (free)
             ──render_narration.py──▶  Sarah clips   ($ ~0.21 per scene)
             ──assemble_video.py──▶  FINAL_video.mp4 (free)
```

### The layout of a video's `final/` folder

Restructured 2026-08-20. Its root now holds only `HANDOFF.md`, `.gitkeep` and
`.render_jobs.json`; everything else lives in a folder named for what it is.

```
final/
  sarah_clips/   the opening: two PAID raw clips, the centred intro,
                       the morph, the corner element, both TRACK_* outputs
    z_History/<ts>/    what the previous build wrote, moved aside automatically
  scenes/              OPENING.mp4 + the sarah-scene-NN-alpha.webm clips
  segments/            the cut demo footage
  video/               finished videos, script.json, script_v<N>.json snapshots
```

**Every tool resolves these through a helper, each with a fallback to `final/`**
— `opening_dir()`, `scene_clips_dir()`, `script_path()`. bike-demo, canoe-demo
and alpine-sports are NOT migrated and keep working unchanged; migrate a store
by moving the files, not by editing code.

⚠ **`build_sarah_opening.py` archives before it overwrites.** Existing assets
move to `sarah_clips/z_History/<timestamp>/` first. This exists because the
old behaviour destroyed paid renders: on 2026-08-20 a re-run overwrote
`sarah-intro-alpha.webm` and `sarah-bridge-alpha.webm` with no backup, and the
only surviving trace of that opening was the finished video built from it.
`--skip-generate` deliberately does **not** archive those two, because in that
mode they are the input rather than something being replaced.

⚠ **`sarah-scene-NN-alpha.webm` are Sarah's voiced clips, not scenes.** A scene
is a segment plus its line and exists only as a row in `script.json` — no file
is a scene. The folder is named for what a reader expects to find; the code says
what it actually holds.

### 0. `script.json` is the copy — never retype a line anywhere else

**It lives at `<final>/video/script.json`**, beside the videos it produced —
moved there 2026-08-20 so the copy and the cut it made sit together. All four
tools resolve it through `script_path()`, which still accepts the old
`<final>/script.json` with a warning, so an un-migrated store keeps working.

**`script_v<N>.json` beside it is a RECORD, not an input.** When a build is
copied to `..._v13.mp4`, the script that produced it is snapshotted as
`script_v13.json`. That pairs every shipped video with the exact copy behind it,
which matters because lines get rewritten and re-rendered: ski-demo's v13 script
differs from its v10 script in four lines. The working file stays unversioned
because at edit time the next version number is not known yet.

It holds every line, the segment each one belongs to, and the measured
`words_per_second`. **Edit lines here and nowhere else.** A line quoted into a doc
or into chat is a copy that will drift from what was actually rendered.

### 1. Cut the recording into segments — `cut_segments.py`

```bash
python3 \
  build/cut_segments.py analyse \
  "Customers/<Business>/<store>/help-videos/final" \
  --raw     "<the raw_mp4 recording>" \
  --log     "<store>/testing/log_reports/<recipe>_INV-*.log" \
  --rec-log "Master_Flows/Recorder/_logs/<store>/<NN>-record-<recipe>.log"
```

Then **look at `work/boundaries.png`**, and only then `cut_segments.py cut <folder>`.

**It needs BOTH logs.** The flow log stamps each step with an absolute time
(`▶ [16:39:29.189] Login …`); the recorder log stamps when OBS began writing
(`RECORDING_STARTED_AT 16:39:27.305`). Subtracting gives each step's exact
offset into the video.

⚠ **Never go back to summing the `(NNNNms)` durations.** It fails in a way that
looks like success — on one take the totals matched to 0.88s while individual
boundaries were out by a whole scene, because the time *between* steps is logged
nowhere and varied 3.6–6.0s within that single run.

⚠ **A recording made before 2026-08-19 has no stamps and cannot be sliced.**
The tool refuses rather than guessing. Re-record.

**A page can carry more than one scene.** The slicer's unit is the page load —
that is what it can detect. ski-demo's requirements form and checkout summary are
the same page, so nothing navigates between them and no detector can find that
boundary; it has to be given one with `--override`.

When a page's segment is split, name the parts `segment-<NN>_<k>-<name>.mp4`:

```
segment-07_1-requirements.mp4     same page, first part
segment-07_2-checkout.mp4         same page, second part
```

The hyphen sequence stays reserved for genuinely distinct pages; the underscore
says "slice of one page", so the name itself records why the boundary exists —
which is what a later re-cut needs to know. Split a page when it is long enough
to want two narrations, or long enough that one line leaves a large gap.

**Supported in code** since 2026-08-19 — the stem regex is
`^segment-\d+(?:_\d+)?-|\.mp4$`, so `segment-07_1-requirements.mp4` resolves. A
split page still needs its own `DEFAULT_MAP` entry to anchor on.

**Expect to force one or two boundaries.** The tool got 9 of 11 on ski-demo. The
two it missed — checkout and payment — are steps whose visible result lands far
from their stamp: clicking "Save and Continue" leaves you on the requirements
page for 2.7s before checkout paints. Five different snap rules were tried and
each fixed one case while breaking another, because login's result appears
**early** and checkout's appears **late**. Read the right time off the contact
sheet and pass `--override 8=51.16 --override 9=54.04`.

**The scene→action mapping lives in `DEFAULT_MAP`.** A store whose flow differs
needs its own entries. Note some lines are logged outside `step()` and carry no
`▶` stamp, so they cannot be anchors — "Order completed" is one, which is why
`complete` anchors on "Wait for order completion" instead.

### 1b. Make the segment fit the line — frame holds

A segment shorter than its narration is the single most common defect, and the
build hides it: the clip simply **freezes its last frame** and Sarah talks over
whatever happened to be there. On ski-demo v13 that frame was the **dashboard**,
during "your order is complete" — and scene 11 then opened on the same dashboard.
Nothing errored. It only shows up in the VTT as a negative gap.

**Fix it by duplicating frames inside the segment, never by slowing footage.** A
UI at 0.55x reads as broken instantly; a still page does not, because the page
genuinely is still at that moment.

```bash
python3 \
  build/cut_segments.py cut <folder> \
  --hold 4=0.52:0.6 --hold 4=2.32:1.0 --length 2=4.0
```

`--hold N=AT:SECS` freezes scene N's segment at `AT` seconds in, for `SECS`.
`--length N=SECS` caps a segment that outlives its scene.

**Finding `AT` — the procedure, not a guess:**

1. Build a per-frame change profile of the segment (mean % and moved-pixel count,
   at 576px — the same two signals `diff_profile` uses).
2. List the **still runs**: stretches where nothing changes. Each is one state a
   viewer can read.
3. `AT` is the **LAST frame of the state**, not the first. At the first the page
   may still be drawing. Same rule as a cut landing on the settled page.
4. **Look at the frame before spending time on it.** Pull it out and view it.
5. After cutting, pull a frame from **inside** the new hold and confirm it is the
   state you meant. This has caught a mistake more than once.

⚠ **Copies are made at the SOURCE rate.** `cut_with_holds` reads `r_frame_rate`
off the input for exactly this reason — a hardcoded 30 injects 30fps stills into
25fps footage and forces a resample at the concat.

⚠ **Do not re-run a whole `cut` just to add a hold.** The previous run's
`--override` / `--length` / `--hold` flags are not stored anywhere, so a bare
re-cut silently discards every earlier adjustment. To adjust one segment, import
`cut_with_holds` and pass the **existing segment** as the raw with `start=0`:
that reuses the tested code path and the locked encode standard, costs one extra
encode generation, and touches nothing else.

**Archive before overwriting.** Copy the segment to
`segments/z_History/<timestamp>/` first. Every asset replaced this way is
recoverable; a segment re-cut from a recording that has since been deleted is not.

**What this looked like on ski-demo v14** — five scenes were over their footage
and none are now:

| # | scene | was | now | what was held |
|---|---|---|---|---|
| 2 | neworder | 6.2s | **4.0s** | *trimmed* — the line had been cut to 8 words |
| 4 | search | 6.5s | **9.4s** | opening, highlighted dropdown, dropdown open, Check availability |
| 6 | additem | 2.2s | **5.2s** | the order review page — on screen 0.28s under a 5.2s line |
| 7 | requirements | 12.0s | **14.1s** | opening form, completed form |
| 8 | checkout | 5.8s | **6.4s** | opening |
| 10 | complete | 3.0s | **7.0s** | "Your order is completed" |

Scene 6 is the one to remember: the state the line was *about* existed for
**0.28s**. Segment length alone would never have revealed that — only the state
profile did.

### 1c. Do it by eye instead — the video players

`cut_segments.py --hold` needs you to already know the timestamp to freeze at.
When you don't — which is most of the time, because the state you want is the
one that was on screen for 0.28s — open the clip in the **video editor** and
look at it frame by frame.

```bash
python3 shared/serve.py --port 8842
```

Plain `python3`, not the venv the other tools here use — this one is stdlib only
(it shells out to `ffmpeg`/`ffprobe` and serves the pages itself). It is also
the `video-editor` entry in `.claude/launch.json`.

Then open `http://localhost:8842/browse.html` and pick a recording. It extracts
every frame as a JPEG once and serves a page where the slider jumps to any frame
instantly. **Every position shown is a real decoded frame**, not a player's seek
— this pipeline has already lost time to more than one bug (the stray "R", frame
0 vs frame 1) caused by trusting `-ss` instead of extracting the frame and
looking at it. That is the whole reason this tool exists.

There are two players. The **MP4 Splitter** opens one clip and cuts it into
numbered segments; the **Segment and Avatar Editor** puts a scene's footage
under its alpha avatar, either one scene at a time or several on a timeline.
Both are served by `shared/serve.py` on the same port, and both name
themselves and their version at the foot of the page.

Two modes share the same six step buttons (1, 10, 100, each direction):

| Mode | The step buttons | Writes |
|---|---|---|
| **Mark** | move the playhead | nothing |
| **Frame Editor** | **Add** duplicates the current frame on that side; **Subtract** deletes frames on that side | nothing — the preview cache only |

Arrow keys always navigate, in **both** modes, on purpose: muscle memory
reaching for ← should never delete a frame.

**Two different writes, and the difference matters.**

- **Cut into N segments** slices the *source* at every break point into
  `Num_1-vN-segment.mp4`, `Num_2-vN-segment.mp4`, … in the store's
  `help-videos/final/segments/`. `N` is one higher than anything already there,
  so re-cutting never destroys an earlier attempt. The source file is untouched.
- **Save edited segment** has no break points at all. It rebuilds the whole
  edited clip and **overwrites the file you opened** (archiving the previous
  version to `z_History/` first). This is how a Frame Editor length change gets
  committed — it is the one button here that changes a file you already had.

Both rebuild from the original with ffmpeg via `frame_map`, so a duplicated
frame becomes a genuinely held frame in the output. Neither is ever a screenshot
of the preview, and the green mark overlay is CSS — it cannot reach an `.mp4`.

**The durations drawn over the slider are the real ones.** Each band spans the
frames one segment covers and shows its length, so you read what Cut is about to
write before pressing it. `computeSegments()` in `build.py` deliberately mirrors
`/api/cut`'s own `[1] + marks + [nb_frames+1]` rule in `serve.py`, empty segments
skipped. **If you change one, change the other** — drift there turns these
labels into lies.

⚠ **`serve.py` imports `build.py` once, at startup.** Edit the page template and
the running server keeps serving the old one — and worse, *Clear all edits*
rewrites the page from its stale copy, so a fix appears to un-apply itself.
Restart the server after any edit to `build.py`.

The cache under `video_players/cache/` is gitignored, shared by every player and fully regenerable;
*Reset Editor* deletes one video's whole cache and never touches the source.

> Renamed from `frame_viewer` on 2026-08-21 when the control layout was rebuilt
> (the "Toolbelt" layout), then split from one `video_editor/` into
> `video_players/` on 2026-08-24 — a folder per player over a shared core.
> **Committing a player change has its own rules** (one player per commit, bump
> its `VERSION`, `<Player Name> v<N> ADDED: …`): see CLAUDE.md, "The video
> players". A `pre-commit` hook prints a reminder.

### 2. Check the timing — `vtt.py`

```bash
python3 \
  shared/vtt.py \
  "Customers/<Business>/<store>/help-videos/final"
```

It prints, per scene: segment length, predicted spoken length, and the **gap**
between them. The estimate is trustworthy — across 11 real clips it was accurate
to a mean **+0.09s**, and predicted total dead air of 10.4s against an actual 10.5s.

**Read the gaps and fix the lines before rendering.** A gap over ~2s is Sarah
holding silently with nothing to say; a **negative** gap means the line outruns its
footage. This is the whole reason a video lands close to what the user wanted on the
first build instead of the third — and it costs nothing.

**Regenerating a VTT means recalculating the gaps and re-rendering the whole table**,
not editing a number by hand.

⚠ **`vtt.py` counts SPOKEN words.** A token with no letter or digit — a spaced em
dash is the one that occurs — is punctuation, not a word. `line.split()` counted
it and added 0.29s to every line written with one. Fixed 2026-08-20; if you write
your own word count anywhere, match this rule.

#### The four time fields in `script.json` — and the thing they catch

Each scene carries:

| field | where it comes from |
|---|---|
| `estimated-word-time` | predicted — word count ÷ `words_per_second` |
| `actual-word-time` | **measured** off the rendered clip in `scenes/` |
| `segment-length` | measured off the segment file |
| `segment-frames` | measured off the segment file |

The pair that matters is the first two. **A clip whose measured length is far from
its estimate was rendered from DIFFERENT WORDS.** Nothing else reports this: the
file exists, the build succeeds, and the video ships speaking a line nobody wrote
any more.

On 2026-08-20 that comparison found **five** stale clips at once:

| # | estimated | on disk | verdict |
|---|---|---|---|
| 5 | 12.2s | 5.5s | stale by 6.7s |
| 2 | 2.3s | 6.2s | stale by 3.9s |
| 6 | 4.9s | 1.4s | stale by 3.5s |
| 3, 7, 8, 9, 10, 11 | — | within 0.5s | current |

**A gap over ~0.5s means re-render that scene.** The estimate is good enough to
be used as a test: across today's five fresh renders it was accurate to **0.6s or
better** on every one.

⚠ **These fields are a snapshot.** Hold more frames in a segment and
`segment-length` / `segment-frames` go stale immediately. Refresh them from disk
in the same step that changes a segment — never later, never by hand.

### 3. Render the narration — the only step that costs money

> #### ⚠ ASK BEFORE SPENDING — one line, exactly this
>
> ```
> I need to pay HeyGen for this.  The COST should be around: $X.XX  Yes (Y) or No (N)
> ```
>
> One line. One question. Then STOP and wait for `Y` or `N`.
>
> The number comes from `--dry-run`, never an estimate. Ask per run — a yes for
> one render is not a yes for the next. `--force` re-renders clips that already
> exist and therefore pays again, so name the exact scenes and the reason before
> asking.
>
> A spend request buried in a paragraph of explanation is one that gets skimmed.
> One line cannot be.

```bash
python3 \
  build/render_narration.py \
  "Customers/<Business>/<store>/help-videos/final" [--only 4 7] [--dry-run]
```

`--dry-run` first, always. It **adopts** renders already submitted for that store,
so a re-run after a crash never pays twice.

**Price the run, do not assume one.** The tool quotes a flat **$0.40** a clip, but
what the wallet actually loses has ranged **$0.21–$0.34** per clip across real runs
(11 clips for $2.30 on 2026-08-18; 5 clips for $1.70 on 2026-08-20). Treat the quote
as a ceiling and read the `wallet before` / `wallet after` lines for the truth. Never
quote a per-clip figure from memory — this doc has already carried a stale one.

> ### ⚠⚠ A changed line does NOT re-render itself — this fails silently
>
> The renderer skips any scene whose clip already exists on disk. Edit a line in
> `script.json`, re-run, and you get `skip (exists)` and a clean-looking rebuild
> **carrying the old audio**. Nothing errors.
>
> **Rule: after editing scene N's line, render it with `--only N --force`.** Then
> confirm the new wording is actually in the clip before assembling.

### 4. Assemble

```bash
python3 \
  build/assemble_video.py \
  "Customers/<Business>/<store>/help-videos/final" --out FINAL_video.mp4
```

Builds both tracks and composites them. Free — re-run it as often as needed.

⚠ **`--out` is resolved RELATIVE TO THE FOLDER**, not the working directory.
Passing a full path produces a doubled path and ffmpeg fails on the very last
step, after every track is built. Pass `--out video/<store>_<title>_v<N>.mp4`.

⚠ **`command failed:` on the last step DOES exit 1 — a pipe can hide that.**
`run()` calls `sys.exit("command failed:\n  ...")`, and `sys.exit(str)` is exit
code 1, verified directly. What actually produced an apparent "exit 0" on
2026-08-20 was piping the build through `| tail -N` — the shell reports the
LAST command in a pipe's exit status, so `tail`'s 0 masked python's 1. **This
was a false alarm** I logged as a real defect (`ToDo.md` P1 2b, corrected). The
underlying advice still stands for a different reason: confirm the output file
exists and probe it, because that is evidence, not because the exit code lies.

> ### ⚠⚠ A `-paused-` clip WINS over the plain one, forever
>
> The assembler picks `sarah-scene-NN-paused-alpha.webm` if it exists, and only
> falls back to `sarah-scene-NN-alpha.webm`. That file is written when a scene
> has `pauses` — but **removing `pauses` from `script.json` does not remove the
> file.** It stays on disk and keeps winning.
>
> Caught on ski-demo v14: scene 7's pauses were deleted, yet the stale paused
> clip (15.08s vs the real 13.00s) was still selected. It would have put scene 7
> back over its 14.1s segment — silently undoing the fix that build existed for.
>
> **Rule: delete a scene's `pauses` → move its `-paused-` clip to `z_History`
> in the same breath.** Before any build, list `scenes/*.webm` and account for
> every file you see.

**Then copy it to `final/video/` with a version bump** (`v1`, `v2`, …) so earlier
cuts stay reviewable. `FINAL_video.mp4` is the working file; `video/` is the record.

### 5. The closing fade — already wired in, nothing to run

`assemble_video.py` calls `fade_frames.py` itself at the one seam that reliably
needs it: the last scene's final frame meeting the canonical rest pose, which is
a **different render**. It prints what it did:

```
  closing fade: 3 frames (0.100s), seam was 4.43% different
```

If the seam ever measures above `FADE_CAP` (9%, corner space) it prints the reason and leaves
the cut alone — that is correct behaviour, not a failure. The fade is wrapped in
a `try`, so a problem there degrades to the old hard cut rather than losing the
build.

⚠ **The rear track absorbs the fade too** (`END_HOLD + fade_dur`). Both tracks
must grow by the same amount or every frame after the seam is offset — the same
desync trap as the `-ss` output-option bug.

### 6. Idle footage in every hold — already wired in, nothing to run

A scene whose line is shorter than its segment leaves Sarah holding. Across
ski-demo that was **~10.2s of the 74.8s** frozen. `assemble_video.py` now fills
those holds with real idle footage instead:

```
  idle footage: 500 frames available at 25fps
    scene 2: idle 27f (0.90s) from idle frames 90-111  (seam 8.44%, 5-frame fade)
```

**A different slice per hold**, allocated sequentially and never reused, so the
same motion never appears twice. ski-demo v14's six holds need 127 frames and 500 exist. Over
`IDLE_CAP` the hold falls back to freezing, and the whole thing is inside a
`try` — a failure degrades to the old behaviour rather than losing the build.

⚠ **The source is `Help_Videos/HeyGen/Sarah/idle/sarah-idle-10s-alpha.webm`,
made from SILENT AUDIO — not scraped from speech.** Send `audio_asset_id`
pointing at a WAV of room tone, with no `script` and no `voice_id`; clip length
follows the audio. Full method, measurements and cost in that folder's README.

⚠ **Mining speech clips for closed-mouth frames is a dead end.** It was tried
exhaustively and every metric passed footage where she is visibly talking. All
13 ski-demo clips together hold **17** non-speaking frames. Render idle footage;
do not hunt for it.

Two bugs this wiring produced, both worth recognising elsewhere:

- **`-shortest` dropped a frame on some holds only.** Audio of `total/30`
  rounded to 4dp lands *below* the video's true length for some frame counts
  (34/30 → 1.1333 vs 1.13333). The audio is now deliberately one frame longer.
- **Measuring the seam consumed footage.** The seam must be known before the
  fade length, but the fade length changes how much idle the hold needs — so
  allocating in order to measure burnt ~2× the footage and wrapped the cursor,
  reintroducing the repetition the design exists to prevent. There is a peek
  that does not consume.

### Inspecting other seams by hand

```bash
python3 \
  build/fade_frames.py \
  report "Customers/<Business>/<store>/help-videos/final"
```

`report` prints every scene boundary with its difference and a verdict. Then
`tail` builds the fade for the one case that reliably needs it — the closing,
where scene 11's last frame meets the canonical rest pose from a **different
render**:

```bash
… fade_frames.py tail sarah-scene-11-alpha.webm \
    --to Help_Videos/HeyGen/Sarah/sarah-rest-pose-full-alpha.png \
    --out closing-fade-alpha.webm
```

Frame count is derived, not chosen: `ceil(difference% / --per-step)`.

**Three things about this were measured and all three are counter-intuitive.
Do not re-derive them:**

| Finding | Number |
|---|---|
| Real differences sit in a narrow band, so a 10%-per-frame rule gives **zero** frames | 2–14%, mean 7.3% |
| Aligning the frames first makes it **worse** — the alpha bbox centre tracks her **hands**, not her head, so translating misaligns hair and shoulders | helped 2 of 10, hurt 8 |
| Above the cap a blend is a **double exposure**, not a fade — at scene 07→08 her hands are down in one frame and raised in the next | refuses above `--cap` |
| **The metric is framing-dependent.** The same two frames measure 4.4% full-frame and 8.5% corner-cropped, because the corner isolates her face and the torso stops diluting it | so `FADE_CAP` is **9.0** in `assemble_video.py` (corner space) and 5.0 in the tool's own default |
| **A scalar cannot tell "expression changed" from "limbs moved."** 8.5% of expression dissolves fine; 13.8% of hand movement does not | the cap is a guard, not a proof — look at the midpoint frame before overriding |

⚠ **It is a dissolve, not a morph.** The midpoint frame ghosts slightly at the
mouth. A true morph needs optical flow (OpenCV, not installed) and would break
on exactly the hard cases — teeth and fingers have nothing to flow from. The cap
is what keeps the dissolve inside the range where it reads as smooth.

⚠ **A scene boundary is a hard cut BY DESIGN.** Clips end on the rest pose and
start mid-word; that is lesson 16c, not a defect. Do not fade the big ones.

### Known rough edge

Scene 7's mid-line pauses are spliced by hand into
`sarah-scene-07-paused-alpha.webm`. `script.json` describes them under `pauses`, but
`assemble_video.py` does not yet perform the splice. If that scene is re-rendered,
the pauses must be re-cut by hand — or the splicing moved into the assembler first.

## Sarah Opening — the standard opening for every help video

**Built and proven 2026-08-15 (ski-demo).** Every help video opens the same
way: Sarah cut out and centred on a dark 1152×1152 screen for the intro, then
the first scene fades in as she morphs down into the lower-right corner and
holds. **Only the words change per video.** The overlay, the geometry, the
timing and the two-track structure are fixed.

> ### ⚠ The canvas is 1152, and it is not arbitrary
>
> **It matches the OBS capture width exactly**, so the demo is never rescaled.
> At 1080 the rear track was scaled by 15/16 — a non-integer downscale that
> resampled every glyph and cost **21%** of the text's edge sharpness (24.70 →
> 19.51 on the checkout line item; 1152 measures 24.97, i.e. native).
>
> Sarah is unaffected either way: she is downscaled ~0.5× from 608 wide, and a
> large downscale looks crisp. It was the *small* downscale that hurt.
>
> `CORNER` is **320**, holding the same 27.8% of the canvas that 300/1080 did.
>
> **If the OBS capture width ever changes, `CANVAS` changes with it** — see
> `A#5`'s "Record at 25fps" section, which records the same coupling from the
> other end.

### Building one — the whole opening, one command

```bash
python3 \
  build/build_sarah_opening.py \
  --intro  "Hi, I'm Sarah. Let me show you how to place your first order with <Store>." \
  --bridge "Let's get started. Here are the steps to complete your first <thing> rental." \
  --scene1 segments/segment-01-login.mp4 \
  --outdir "Customers/<Business>/<store>/help-videos/final"
```

It generates both avatar clips, measures her pose in each, builds the morph and
corner element, assembles the front and rear tracks, and composites
**`OPENING.mp4`**. Then it prints the timings it used.

| flag | default | |
|---|---|---|
| `--corner` / `--inset` | 300 / 0 | corner size; inset 30 for the older margin |
| `--morph` / `--fade` | 1.2 / 0.6 | morph length; background fade-in |
| `--canvas` | 1080 | square canvas |
| `--skip-generate` | — | re-assemble from clips already on disk, **no spend** |

⚠ **Each run generates two clips and costs real money** against the wallet
(`GET /v3/users/me` → `remaining_balance`). Proofread both lines first — a typo
costs another render. Use `--skip-generate` for any re-assembly.

⚠ **Only the two script lines should change between videos.** If a new video
seems to need different geometry or timing, raise it rather than passing
different flags — the whole point is that every opening looks identical.

Everything below is *why it works that way*, and is only needed when the
opening itself has to change. The first build's assets are in
`Customers/Rentify Demos Corp/ski-demo/help-videos/final/`.

### Step 1 — generate her with a transparent background

`type: "avatar"` takes a **flat** schema. Nesting the script inside an `input`
object (as the `studio` scene type does) fails with *"An audio source is
required"* — an easy and confusing mistake to make when switching between the
two endpoints.

```json
{
  "type": "avatar",
  "avatar_id": "468eabb3326a4d8587ba29d065b1eba7",
  "script": "<the line>",
  "voice_id": "04d0ae1d0af2489ca7d3bb402a39a890",
  "resolution": "1080p",
  "output_format": "webm"
}
```

- **`output_format: "webm"` is the whole switch.** It returns alpha, applies
  matting for you, and **rejects** any `background` value in the same request.
  MP4 can never carry alpha.
- **`aspect_ratio` is IGNORED here.** Asking for `1:1` still returns
  **1080×1920** portrait. The square is made locally in step 3 — don't wait for
  the API to honour it.
- Poll `GET /v3/videos/{id}`; ~90s for a 5s clip.

### Step 2 — the VP9 alpha trap, which lies to you

Plain `ffprobe` reports `pix_fmt=yuv420p` on a perfectly good alpha file, and
any ffmpeg step that decodes it without the right decoder **silently drops the
alpha** — you get an opaque black box, not an error.

```bash
ffprobe -v error -c:v libvpx-vp9 -show_entries stream=pix_fmt ...   # → yuva420p
```

Force `-c:v libvpx-vp9` **on every decode of the file**, including the input to
the composite. Verify transparency by overlaying on a garish colour and reading
a corner pixel back — a magenta corner means the alpha is live.

### Step 3 — centre HER, not the frame

Her subject is not centred in HeyGen's output. Measured on the first build:
she spans `x=140..1052`, so her centre is **x=596** against a frame centre of
540. Centring the video would leave her 31px off. Measure the alpha mask each
time — a different script or pose moves her:

```bash
ffmpeg -c:v libvpx-vp9 -ss 2 -i in.webm -vf alphaextract -frames:v 1 mask.png
# then bbox the non-zero pixels; offset = 540 - (subject_centre * scale)
```

Composite, preserving alpha (1080×1920 → 607×1080, full height, no crop):

```bash
ffmpeg -c:v libvpx-vp9 -i sarah-intro-alpha.webm \
  -filter_complex "color=c=black@0.0:s=1152x1152:r=30,format=yuva420p[bg];\
[0:v]scale=607:1080,format=yuva420p[s];[bg][s]overlay=x=205:y=0:shortest=1,format=yuva420p" \
  -c:v libvpx-vp9 -pix_fmt yuva420p -b:v 2M -c:a libopus out.webm
```

`x=205` is the *measured* offset from this build, not a constant — recompute it.

⚠ A seated figure in a square occupies roughly the middle 56%, with transparent
space either side. That is inherent to the source framing, not a bug. Crop
tighter to a head-and-shoulders medium shot if a fuller frame is wanted — ask
first, it changes the look.

### Step 4 — Sarah in the corner, over the demo (the look the API cannot make)

**Proven 2026-08-15.** This is the corner-avatar overlay HeyGen's API has no
path to — `studio` scenes are whole-frame, avatar *or* video, never layered.
ffmpeg does it in one pass, from the same alpha WebM as the full-screen intro.

**Do not just shrink the whole figure.** Scaling a 1080×1920 seated portrait
into 300×300 gives a tiny distant person in a mostly-empty box. Crop to head
and shoulders first. Find the shoulder line by profiling the alpha mask's width
per row — the head is narrow and the shoulders jump:

```
y=300..700  width 291→414   ← head
y=800       width 630       ← shoulders begin
y=1000+     width 750+      ← torso
```

For this build that gave `crop=820:820:145:170` — a square around head + upper
shoulders, centred on the head's own x (~555, **not** the frame centre).
**Re-measure per clip**; a different script or pose moves her.

**The reusable element** — build the corner once, overlay it anywhere:

```bash
ffmpeg -c:v libvpx-vp9 -i sarah-intro-alpha.webm \
  -filter_complex "[0:v]crop=820:820:145:170,scale=300:300,format=yuva420p" \
  -c:v libvpx-vp9 -pix_fmt yuva420p -b:v 1M -c:a libopus sarah-corner-300-alpha.webm
```

**Demo footage into a 1:1 frame — pad, don't crop.** Our captures are 1152×962.
Centre-cropping to square would cut ~95px off each side and clip the app's
cards. Fit to width and pad top/bottom instead, so nothing is lost:

⚠ **Sample the pad colour from the clip's own edge — do not guess it.** The app
edge is `#212121`; padding with the plausible-looking `#2A2A2A` left a visible
horizontal band across every scene. Nine RGB values was enough to see.

```bash
# read the real edge colour first, then use it
PAD=$(python3 -c "from PIL import Image; im=Image.open('frame.png').convert('RGB'); \
r,g,b=im.getpixel((5,480)); print('0x%02X%02X%02X'%(r,g,b))")

ffmpeg -i segments/segment-NN.mp4 -c:v libvpx-vp9 -i sarah-corner-300-alpha.webm \
  -filter_complex "[0:v]scale=1080:-2,pad=1080:1080:0:(1080-ih)/2:color=$PAD,setsar=1[bg];\
[bg][1:v]overlay=x=780:y=780:shortest=0,format=yuv420p" \
  -c:v libx264 -c:a aac -movflags +faststart out.mp4
```

**Placement**: `x=780:y=780` puts a 300×300 element flush in the lower-right of
1152×1152 (`1152-320`). For the project's older 30px inset, subtract it again —
that is the only number that changes. Bottom-right is the standing default
(design decision 8); a flush corner crops her lower shoulders at the frame edge,
which reads as a normal webcam-style PIP.

`shortest=0` matters: the avatar clip is shorter than most demo scenes, so
without it the scene would be truncated to the avatar's length.

### Step 5 — the centre→corner morph

**Built 2026-08-15.** Sarah scales down, reframes from full figure to head-and-
shoulders, and travels to the corner over ~1.2s, then holds. This is the
`[0-3s] intro → [3-6s] corner, screen fading in` beat from the original video
structure, done for real.

**HeyGen has nothing for this — checked, don't go looking again.** The Studio
spec has **no** transition, keyframe, position or animation field of any kind;
scenes are concatenated whole-frame. `motion_prompt` animates gestures *within*
the avatar's own performance, and `cinematic_avatar` directs a camera *within*
an avatar shot — neither moves an avatar across a background it isn't part of.
The editor's scene transitions are cuts/fades between whole scenes, not motion.

**Two ffmpeg approaches that do NOT work, so don't burn time on them:**

- **Animated `crop`.** `w`/`h` are fixed at filter init — a crop cannot change
  its output size per frame, and the framing change is half the effect.
- **Per-frame `scale` (`eval=frame`) into `overlay`.** Produces a
  varying-size input that overlay handles badly.

**What works: composite the frames directly** — and that is now a tool, so
don't hand-roll it again:

```bash
python3 \
  build/morph_avatar_corner.py \
  --src sarah-intro-alpha.webm --outdir <store>/help-videos/final
```

It writes **both** the static corner element and the morph, and prints the
compose command for you. Flags: `--corner 300`, `--inset 0` (30 for the older
margin), `--duration 1.2`, `--canvas 1080`.

**It measures the pose itself** rather than taking hardcoded numbers — it finds
the subject's bounding box, the head's own x, and the shoulder line (the first
row where the silhouette exceeds 1.4× the head's width). Run against the first
build it independently derived shoulder y=784 and crop 835² against the 800/820²
found by hand, and the identical `x=205` centring offset. That auto-measurement
is the point: **a different script or pose moves her**, so hardcoding the crop
across videos would slowly go wrong.

What it does per frame, for when it needs changing:

```
p     = smoothstep(i/(n-1))          # 3u²−2u³; linear reads mechanical
box   = lerp each of the 4 crop edges     (full frame → head+shoulders)
h     = lerp(canvas, corner, p)
w     = h * (box_w / box_h)          ← from the CROP's aspect, NOT a second lerp
pos   = lerp each of x, y                 (centred → corner)
crop → resize(LANCZOS) → alpha_composite onto a transparent canvas
```

⚠ **Derive the width from the crop's own aspect ratio.** Lerping width and
height independently makes her subtly squash and stretch mid-move, because the
crop is going from 0.5625 to 1.0 aspect while the output box is going from
607×1080 to 300×300. Deriving `w` keeps every intermediate frame correct.

Encode the sequence with alpha, then compose against the demo — the transition
ends at *exactly* the corner element's size and position, so the handoff is
seamless by construction:

```bash
ffmpeg -framerate 30 -i out/f_%04d.png -c:v libvpx-vp9 -pix_fmt yuva420p -b:v 2M morph.webm

ffmpeg -i scene.mp4 -c:v libvpx-vp9 -i morph.webm \
  -itsoffset 1.2 -c:v libvpx-vp9 -i sarah-corner-300-alpha.webm \
  -filter_complex "[0:v]scale=1080:-2,pad=1080:1080:0:(1080-ih)/2:color=$PAD,setsar=1[bg];\
[bg][1:v]overlay=x=0:y=0:enable='lt(t,1.2)'[a];\
[a][2:v]overlay=x=780:y=780:enable='gte(t,1.2)',format=yuv420p" out.mp4
```

The morph clip is already canvas-sized, so it overlays at `x=0:y=0`; the corner
element is 300×300 and needs its own offset. `-itsoffset` delays the corner
input so it starts where the morph lands.

**Keep it to one deliberate move.** The 2026-08-06 feedback that killed the
ffmpeg pipeline was "too much shifting around" — that was *synthetic gap-filling
motion* invented to keep her alive between segments. A single scripted
centre→corner move at the start is the opposite: it is motivated, it happens
once, and it stops.

### Step 6 — the two-track model (this is the composition architecture)

**Adopted 2026-08-15, at the user's direction.** Sarah and the background are
**two independent files**, joined by a single overlay at the end. Neither
timeline depends on the other, which is the whole point — the relationship
between them becomes something you set, not something baked in.

```
FRONT  TRACK_front_sarah.webm        1152×1152, yuva420p, carries the audio
       intro (centred) ++ morph (1.2s) ++ corner hold        — one continuous clip
REAR   TRACK_rear_background.mp4     1152×1152, opaque, silent
       dark #212121 for the intro ++ scenes, fading in

FINAL  overlay front over rear at x=0:y=0 — nothing else
```

```bash
ffmpeg -i TRACK_rear_background.mp4 -c:v libvpx-vp9 -i TRACK_front_sarah.webm \
  -filter_complex "[0:v][1:v]overlay=x=0:y=0:shortest=1,format=yuv420p[v]" \
  -map "[v]" -map 1:a -c:v libx264 -c:a aac -movflags +faststart out.mp4
```

Because the front track is canvas-sized and transparent everywhere she isn't,
it overlays at `0:0` — no positioning at composite time. All of Sarah's motion
is already inside her own track.

**The bridge clip is not optional.** The background is supposed to stay dark
*until the intro finishes*, and only then reveal scene 1 as she moves. That
needs Sarah footage **after** the intro's audio ends — otherwise you either
freeze her (dead) or morph her mid-sentence. So generate a second short avatar
clip for the corner-transition line, exactly as the original video structure
specified:

> "Let's get started. Here are the steps to complete your first ski rental."

The morph is then built from the **first** 1.2s of that bridge clip
(`--start-at 0`), and the corner hold is its remainder. Her audio runs
continuously across both.

**Fade the background in, don't cut it.** A 0.6s
`fade=t=in:st=0:d=0.6:color=<PAD>` on the first scene matches the original
"screen fading in" beat and stops the reveal being abrupt.

⚠⚠ **The reveal holds scene 1's FIRST FRAME for the whole bridge, so that frame
must be a settled page.** A scene's opening frames are very often mid-render.
On ski-demo, scene 1's first **0.17s** was a loading spinner — three dots — and
holding frame 0 froze those dots for the entire 4.16s bridge. It was the most
visible defect in the finished video, and it survived a full build plus a
contact-sheet review because the sheet sampled every 6s and simply missed it.

**Fix the CUT, not the hold.** Re-cut the scene to begin on the settled view,
then hold its (new) first frame — that way the reveal and the scene's own
playback start from the same picture, so there is no jump when it begins. On
ski-demo the cut moved from source `3.30s` to `3.47s`, landing on the login form
with an empty box showing its "Your email" placeholder, *before* typing starts.
Never trim only the hold and leave the clip starting earlier; the dots would
simply reappear when the scene played.

**How to check it, since this is invisible in the code:** extract a frame at the
moment the morph lands (intro + morph duration, ~6.05s on this build) and LOOK
at it. The demo page should be fully up behind her. Sampling every few seconds
will not catch a sub-second loading state.

**Both openings must be built the same way.** `build_sarah_opening.py` used to
*play* scene 1 under the bridge while `assemble_video.py` *held* its first frame
— two tools, two different openings from the same assets. They are aligned on
the hold now. If one is changed, change both, or `OPENING.mp4` stops matching
the opening of the finished video.

⚠ **Two separate avatar renders never match exactly at the join.** The intro
ends with her centred at `x=205`; the bridge's own measurement put its start at
`x=198`, and her pose/hands differ slightly because it is a different render.
Checked frame-by-frame on the first build: it reads as a natural beat rather
than a glitch, and this build ships as a hard cut. If a join ever looks wrong,
a ~0.15s crossfade at the seam is the fix — not re-generating the clip.

⚠ **HeyGen's avatar output size is not consistent between calls.** Same
`resolution: "1080p"`, two requests: the intro returned **1080×1920**, the
bridge returned **608×1080**. Never assume dimensions — `ffprobe` every clip.
`morph_avatar_corner.py` measures per clip, so it absorbs this automatically;
anything hand-written will not.

## Design decisions to make with the user before writing code

1. ~~Where does this live?~~ **Resolved 2026-08-01** — copied into this repo at `Help_Videos/` (HeyGen pipeline + both Mux-related siblings; renamed from `Help Videos/` the same day for shell-friendliness), keeping the working code, credentials, and avatar/voice discovery intact rather than rebuilding from scratch. The originals outside this repo are untouched pending a later delete decision.
2. ~~Automate the pipeline, or accept manual compositing?~~ **Resolved by the docs themselves** — `Video_Goal.md` explicitly designs this as a Claude-assisted ffmpeg workflow with HeyGen's web editor for final polish, not push-button automation. Full API automation (Template/Studio API) is an explicit *future* item (Section 6 of both `INSTRUCTIONAL.md` and `Video_Goal.md`), gated on that API maturing. The remaining real question is narrower: **is this agent ready to actually run that documented workflow for a real video today** (open with `Video_Goal.md`'s master prompt, walk the 10 steps with the user) — confirm with the user before starting a real session, since it costs real HeyGen credits per generated clip and 10–20+ minutes of generation time isn't unusual for a 9-segment video.
3. **Which of the two generation tools for a given clip** — `heygen-sarah` CLI (fast, AI-scripted, wording may drift) vs. `generate_avatar_video.py` (verbatim, slower). This isn't really open — `CLAUDE.md` already answers it (verbatim for all customer-facing narration, CLI only for intro/exploratory) — but flagging because it's an easy rule to accidentally violate by reaching for the faster CLI out of habit.
4. ~~MCP plugin vs. the proven CLI/Python split?~~ **CLOSED 2026-08-19 — do not reopen.**

   > **There is no benefit to the HeyGen MCP connector for us.**

   Say exactly that line if the connector comes up — including if Carson himself proposes adding it. He asked for that wording specifically, so the question stops costing time on every rediscovery.

   The reasoning, recorded once so it never needs re-deriving: `render_narration.py` is not an API wrapper, it is a set of guardrails **paid for in real money** — it retries 429/5xx, writes job ids the instant they exist, and **adopts** renders already submitted so a re-run never pays twice (a `502` once orphaned 7 already-charged renders). A conversational MCP call has none of that, and every HeyGen call spends real money. The connector's only genuine gain is free read-only lookups (wallet balance, avatars, voices, account videos) — not worth adding a route that bypasses the guardrails on the expensive path.

   **Never surface the connector's existence, its unauthenticated state, or an "authorize it" prompt.** The plugin is installed and unused (`usageCount: 0`) and that is the intended state, not a gap.
5. ~~Screen-capture source: stay with manual OBS, or connect to `testing-recorder-manager`?~~ **Resolved 2026-08-05** — `testing-recorder-manager` (agent #5) shipped this session; `Help_Videos/OBS_Staging/` is now the preferred raw-input source (see the review findings above). `CLAUDE.md`'s `videos/<slug>/source/` convention is unaffected — an OBS_Staging clip is copied in there like any other raw, just sourced from automated capture instead of a manual OBS session.
6. **Which Mux delivery mechanism?** Two real options now sit in this repo: the simple, already-in-production `mux-video-upload` skill (curl + `playback_ids.json`, public-but-unlisted Mux asset — this is what `rentify_live` actually serves today) vs. `Help_Videos/VSCode_Mux_Ex/`'s prototype (own Go backend, JWT-signed **private** playback, sqlite-backed) — built but never deployed or connected to `rentify_live`. Adopting the latter means standing up and hosting a whole second service; the former is a shell script and a json edit. Ask whether genuinely private (token-gated, not just unlisted) playback is a real requirement before taking on that scope — if unlisted-public has been fine so far, that's the strong default to keep using.
7. **Delivery target** — which store(s) is the first video for? `customers/default/help_videos/` (all stores) vs. a specific `customers/{storeId}/help_videos/` override, per the existing Mux skill's convention. Affects nothing about generation, only where the final upload lands — and is moot until decision 6 is made.
8. ~~Corner position: locked bottom-right vs. a per-video override?~~ **Resolved 2026-08-05** — after being asked directly, the user confirmed bottom-right stays the standing default; the earlier lower-left request for this specific video was reconsidered and dropped, not adopted. No compositing recipes needed to change.
9. ~~Compositing approach: ffmpeg-assembled + HeyGen-editor-polished, or build directly in HeyGen's own editor?~~ **Resolved 2026-08-06** — pivoted to building directly in HeyGen's "Scene by scene" editor, per explicit user feedback that the ffmpeg-bridged version had "too much shifting" in the avatar's gap-filling motion. See "Session 2026-08-06" above for the full reasoning and what HeyGen's platform actually supports. The original ffmpeg + HeyGen-editor-polish pipeline (`INSTRUCTIONAL.md`, `Instructional_Lessons_Learned.md`, `avatar_compositing.md`) remains fully documented and is what shipped `First_Time_Ordering_6.mp4` — still a legitimate fallback path if the HeyGen-native build stalls, not something to delete or treat as wrong.

## Logging your progress (session summary)

> ⚠ **Does not run here.** `agent_log.py` is a `Basic_E2E_Testing` tool and did
> not come across. Kept because the SHAPE of the log — one step per real stage,
> a warn on anything that needed attention even when it succeeded, stop on a
> genuine error — is the convention this repo's own logs already follow. See
> `tests/log_reports/` and the editor session log in `logs/`.

Log each real video-production session — not every ffmpeg invocation, since a single video runs many small commands and most are just iteration. Use `.claude/agent-tools/logger/agent_log.py` (see `.claude/agent-tools/README.md` for the full command reference), keyed to the video's slug (e.g. `first_time_ordering`), one `step`/`expected` pair per phase of the documented workflow (prep → script → avatar → assemble → PII blur → package → HeyGen polish):

```bash
LOGPATH=$(python3 .claude/agent-tools/logger/agent_log.py start "6_end-customer-help-video-creations" "<video-slug>" | tail -1)

python3 .claude/agent-tools/logger/agent_log.py step "$LOGPATH" 1 "Prep: source recording + script ready"
python3 .claude/agent-tools/logger/agent_log.py expected "$LOGPATH" 1

# HeyGen generation costs real credits — flag with warn even on success if anything about the run needed attention
python3 .claude/agent-tools/logger/agent_log.py step "$LOGPATH" 3 "Avatar clips generated via generate_avatar_video.py (verbatim)"
python3 .claude/agent-tools/logger/agent_log.py expected "$LOGPATH" 3
python3 .claude/agent-tools/logger/agent_log.py warn "$LOGPATH" 3 "re-generated once — first pass had a script typo, cost 1 extra credit"

# a genuine failure — log the error, then STOP; do not continue to the next step
python3 .claude/agent-tools/logger/agent_log.py error "$LOGPATH" 5 "boxblur radius 15 rejected by ffmpeg — must be <= 11"

# once, at the end — writes the Run Summary and closes the file (skip if `error` already ran)
python3 .claude/agent-tools/logger/agent_log.py footer "$LOGPATH"
```

Logs land in `build/logs/<video-slug>_<timestamp>.log` — gitignored, local only, never deleted except by the human. To review one in color, run `python3 .claude/agent-tools/logger/activate_theme.py 6_end-customer-help-video-creations` and reload the VS Code window (only one agent's theme can be active at a time).

## Guardrails

- Never read, print, or copy the contents of any `.env.local` (in `Help_Videos/HeyGen/` or elsewhere) — credentials stay where they are; ask the user directly if a key is needed here.
- Don't target HeyGen's v2 avatar endpoints — confirmed dead end (hangs/404s). v3 only.
- Don't assume the HeyGen MCP plugin is usable — it's unauthenticated; if a tool call to it fails for that reason, tell the user it needs authorization rather than working around it.
- Don't re-derive the avatar/voice/endpoint decisions already made in `Help_Videos/HeyGen/`'s handoff docs — read them first; only revisit a locked decision if the user asks to.
- Don't upload anything to Mux or write to `rentify_live/customers/**/playback_ids.json` until there's an actual finished, verified mp4 — that's the existing `mux-video-upload` skill's job once step 3 (compositing) produces real output, not something to wire early against placeholder files.
- Don't create git commits in either repo.
- This agent's surface is help-video production (avatar/voiceover generation, compositing, and handing off to the existing Mux upload step) — not BCP/customer catalog data, not the rental-flow E2E tests themselves (that's `testing-runner-manager`/`testing-recorder-manager`).

## When something goes wrong — categorize before reporting

Before reporting a failure, classify why, and say the category explicitly as part of the report:

- **Process/Agent gap** — this file's own instructions, or the documented pipeline (`CLAUDE.md`/`INSTRUCTIONAL.md`/`Instructional_Lessons_Learned.md`) were wrong, missing a case, or ambiguous. The fix belongs in THIS FILE (or the referenced doc it points to) — once resolved, add a dated entry to "Lessons Learned" below.
- **Content/input quality issue** — the raw material was bad, not the process: a source screen recording has a UI bug or bad framing making it unusable, a narration script has a typo that wasn't caught before generating (costs a real HeyGen credit to fix), a config value (avatar_id, voice_id) was mistyped. Not this agent's fault if it followed the documented steps — name exactly what's wrong and where.
- **External/environmental** — HeyGen's API/CLI behaves differently than `heygen_api.md`/`heygen_api_addendum.md` describe (a real possibility — those were captured at a point in time), an ffmpeg build quirk, a credit/quota issue. Note it plainly; only add a Lessons Learned entry if a durable workaround is now known.

Don't guess if it's genuinely unclear — say so and let the user decide. Getting the category right matters more than getting it fast: filing a content problem as a process fix (or vice versa) sends whoever fixes it to the wrong file.

## Lessons Learned

**2026-08-15 — First session to actually call the HeyGen API rather than read its schemas. Four things cost real time or would have.**

1. **The same API uses two different request shapes for an avatar, and mixing them fails opaquely.** A `studio` scene nests the script inside `input: {type: "avatar", script, voice_id}`; a standalone `type: "avatar"` video puts `avatar_id`/`script`/`voice_id` **flat at the top level**. Sending the nested form to the flat endpoint returns *"An audio source is required: provide (script + voice_id)…"* — which reads like the script is missing when it is actually present, just one level too deep.
2. **`aspect_ratio` is honoured by `studio` and ignored by `avatar`.** A `1:1` avatar request returns 1080×1920 portrait with no warning. Don't build a pipeline that assumes the API will frame anything for you — square framing is a local ffmpeg step.
3. **A rendered 1:1 studio video is not necessarily a filled 1:1 frame.** Ours came back with the composition pillarboxed into a 9:16 strip, 44% of the canvas near-white. The container dimensions were exactly right, which is precisely why this needed a rendered test and not a schema read — `ffprobe` said `1080x1080` and the picture was still wrong. Same lesson as agent 5's black-bar bug: **extract a frame and look at it.**
4. **Centre the subject, not the video.** HeyGen's avatar output does not centre her in her own frame — measured 31px off. Extract the alpha with `alphaextract`, bbox the non-zero pixels, and offset by that. Assuming `(canvas - width) / 2` gives a visibly lopsided intro.

Also confirmed the hard way that the repo's own long-standing warning is real: **`ffprobe` reports `yuv420p` on an alpha WebM** and any decode without `-c:v libvpx-vp9` throws the transparency away silently. The existing note said so; this session proves it still applies to files HeyGen generates today.

15. **A held reveal frame must be a settled page — and a contact sheet will not catch it.** Scene 1's first 0.17s was a loading spinner; holding frame 0 froze three dots for the whole 4.16s bridge. It shipped through a full assembly and a frame-by-frame review because the review sheet sampled every 6 seconds. Sub-second loading states hide between samples. When a single frame is going to be held for seconds, extract *that* frame and look at it — the general rule "extract a frame and look" has to be pointed at the specific frame the build freezes, not at the video in general. The fix belongs in the CUT (start the **segment** on the settled view) so the reveal and the segment's own playback share one picture.

16. **Where a held frame comes from decides whether it looks alive — and "the last frame" is nearly but not quite right.** Three separate defects came out of holding the wrong frame, and each needed a different answer:

    a. **Padding with transparent frames made her VANISH** the instant a line ended (`tpad=stop_mode=add`), on ten of eleven scenes. `stop_mode=clone` holds her instead.

    b. **A held frame mid-clip catches a blink or a half-formed word.** This render blinks and glances down constantly — four of eight frames sampled across one 13s clip had her eyes shut, and scene 7 is continuous speech with almost no closed-mouth frame anywhere in it. The two 1s pauses spliced into that scene were cloning whatever frame sat at the split, which is a coin flip. They now hold the clip's **final** frame.

    c. **Which works because every HeyGen clip ENDS on the settled rest pose** — eyes open, mouth closed, level head — verified across all eleven scene clips. Clip **starts** are the opposite: mid-word with eyes shut. So `clone` is correct for a mid-video hold by construction, not by luck. **But scene 11's final frame is an exception** (a softer, asymmetric look, now kept as the "Uncertainty" standard), so the video's *closing* frame must come from the canonical reference file, never from "whatever the last clip ended on". `assemble_video.py` closes with a 1s hold on `Help_Videos/HeyGen/Sarah/sarah-rest-pose-full-alpha.png` and warns if it is missing.

    Framing is consistent enough across renders to drop the reference in — measured `head_cx` 321 vs 319 with identical `top` — but measure before relying on it rather than assuming.

    **The standards live in `Help_Videos/HeyGen/Sarah/`** with a README. Check a hold against them rather than inventing a metric: scoring frames on eye contrast minus mouth contrast still ranked mid-speech frames top, and looking at a contact sheet found the right frame in seconds.


**2026-08-16 — Rendered all 11 narration clips and assembled the first complete video. Three failures worth knowing, one of them expensive.**

12. **`-c:v libvpx-vp9` is needed on EVERY decode of an alpha WebM — including the concat demuxer.** The first full assembly came out with a completely black background. The rear track was fine; the FRONT track had been flattened to opaque during `-f concat`, because the decoder flag was passed when building each clip but not when joining them. The joined file still reported `pix_fmt=yuva420p`, so nothing looked wrong until the composite. This is the third distinct place this trap has bitten (probe, filter input, now concat) — the rule is the flag goes before **every** `-i` that reads one of these files, and the only trustworthy check is overlaying on a garish colour and reading a corner pixel back.
13. **A transient API error mid-batch can orphan work you have already paid for.** A `502 Bad Gateway` while submitting clip 8 of 11 killed the script *after* clips 1–7 were submitted and charged. Those renders completed on HeyGen with nothing locally tracking their ids. Recovered by listing the account's videos and matching on title. `render_narration.py` now retries 429/5xx with backoff, writes job ids to disk the moment they exist, and **adopts** any render already submitted for that store before spending again — a re-run must never pay twice.
14. **The demo must not start under the bridge line.** Scene 1's footage was originally playing during the corner-transition, which left only 1.9s of it for its own narration — so "Enter your email…" would have played over the code screen. Fixed by holding scene 1's FIRST FRAME under the bridge and starting the clip when its narration does. The opening looks identical; the login page simply waits a beat before typing begins. Worth knowing that the opening and the first scene compete for the same footage, and the opening wins.

Also confirmed at real scale: the VTT's measured 3.44 words/sec predicted the 11 rendered clips to a mean error of **+0.09s**, and predicted total dead air of 10.4s against an actual 10.5s. Estimating narration length from a measured rate is reliable enough to plan a whole video against. Actual cost was ~$2.30 for 11 clips (~$0.21 each) on that run. ⚠ **Do not carry that figure forward** — 2026-08-20's 5-clip run cost $1.70 (~$0.34 each). Per-clip cost varies; the $0.40 quote is a ceiling, and the wallet lines are the truth.

**2026-08-19 — Built the fade generator. Every intuition about it measured wrong.**

20. **Three plausible design assumptions, all falsified by measuring.** (a) A percentage-per-frame rule sounds scale-free, but real Sarah-to-Sarah differences occupy a **2–14%** band, so the natural-sounding "one frame per 10%" produces **zero** frames for almost everything. Pick the constant from the measured range, never from the shape of the rule. (b) **Aligning the two frames before blending makes the result worse** — it helped 2 of ski-demo's 10 boundaries and hurt 8, because the alpha bounding box tracks her *hands*, which move constantly, not her head, which does not. The "25px shift" that looked like a framing offset was an arm rising. (c) **Crossfading a large difference is worse than the cut it replaces**: at 13.8% her hands are down in one frame and raised in the next, and a blend is two faces and four hands. So the tool **refuses** above 5% rather than obeying. A generator that will not run on the worst input is doing its job.

    (d) **A threshold is only meaningful in the space it was calibrated in.** The 5% cap was derived from full-frame measurements, then applied to corner-scaled frames — where the same seam reads 8.5% instead of 4.4%, because the corner crop isolates her face and the static torso is no longer diluting the difference. The cap silently refused the one seam the feature was wired for. `assemble_video.py` uses 9.0 for that reason, and the tool keeps 5.0 for full-frame work. Any threshold carried between two representations of the same thing needs re-deriving, not reusing.

    Also worth keeping: `ffprobe` reported `pix_fmt=yuv420p` on the correctly-encoded alpha output, exactly as the standing warning says. The only check that meant anything was overlaying on magenta and reading a corner pixel — **with a control that decodes without `-c:v libvpx-vp9` and is expected to fail.** A passing test proves nothing until its failing twin fails.

**2026-08-20 — Four help videos built end to end. The lessons that cost the most.**

21. **Verify in the space the thing ships in, at the size it ships at.** Four separate defects came from checking at the wrong resolution, and it is the single most expensive pattern in this project. A contact-sheet thumbnail was too small to show a stray "R" in the login field, and that build was reported as good. A MEAN frame-difference cannot see a typed character at all — it is 0.014% of the frame and, being a ratio, stays 0.018% at triple the resolution. A changed-PIXEL count does see it (70 pixels) but counts scale with area, so thresholds measured at 576px became noise at 192px. And `fade_frames`' cap was calibrated on full frames at 5%, then applied to corner crops where the same seam measures 8.5%. The corner is what the viewer sees, so the corner is where you calibrate.

22. **The failures that look like success are the expensive ones.** `--force` re-rendered three rewritten lines for **$0.00** and returned the originals; only the clip durations gave it away. The OBS Profile said `FPSCommon=25` while every recording came out at 30, found only because a real test recording was asked for. And a flow log summing to 71.12s against a 72.00s video looked like a clean 0.88s offset while individual segment boundaries were out by a whole scene. In each case the wrong answer was reported cheerfully. Check the number that would have to change if it worked.

23. **A cache is right for one reason and wrong for another — and knowing that does not stop you.** Three instances inside `render_narration.py` alone: `skip (exists)` is correct for crash recovery and wrong after a text change; `--force` fixed the file check but not adoption; and the render title was identical for every version of a scene, so adoption could never tell a rewritten line from its predecessor. Lesson 17 documented the first one. That did not prevent the other two.

24. **When the third variation of an approach fails, the approach is wrong.** Five snap rules were tried for segment boundaries — nearest transition, last, last-bounded-by-next-step, first-then-settle — each fixing one case and breaking another. The fix was not a sixth rule; it was making the flow log stamp absolute times so boundaries became arithmetic. Same shape with frozen holds: five metrics for finding closed-mouth frames inside speech all passed footage where she is visibly talking, and the answer was to stop mining and RENDER idle footage for $0.50. Fix upstream.

25. **Measure the segments, then write the script.** ski-demo's was written blind and needed four lines rewritten and re-rendered; it landed at 6% dead air only after that rework. bike-demo, canoe and alpine were written against measured segment lengths — 11%, 3% and 3%, with no rework at all. The VTT exists to be read before anything is paid for.

26. **A pipeline is only proven by its SECOND use.** Everything ski-demo needed had been hand-done once, which hid three gaps in `build_sarah_opening.py` until bike-demo: stale 1080/300 defaults, `--scene1` resolved against the caller's cwd rather than `--outdir`, and the centred intro file that `assemble_video.py` reads but nothing ever wrote. All three surfaced only when a store went through for real, and two of them wasted paid renders. Canoe and alpine then needed none.

27. **Stores differ in SHAPE, not just wording.** canoe-demo and alpine-sports have no question set, so there is no requirements form and no separate checkout page — ten scenes, not eleven. Canoe cost a full slice to discover, its scene 7 arriving at 0.48s. Alpine's was visible in the flow log in seconds: a sub-second gap between two steps means that screen barely existed. `cut_segments.py` now warns on it. **Check the shape before writing a word of script.**

Still open after four videos: the closing fade refuses on three of four stores (26%, 25.7%, and skipped), which makes ski-demo the exception rather than those three — treat it as a cut decision, not a threshold to widen. And two override classes recur on every store: a spinner on the add-person page, and Stripe's spinner standing in for the completed order. Both are one thing — a step whose visible result arrives well after its stamp — and that is the next thing worth solving properly.

**2026-08-20 (later) — ski-demo v14. Holds, and four defects that each reported success.**

28. **"The segment is too short" is invisible; only a NEGATIVE GAP names it.** The build never fails when a line outruns its footage — it freezes the last frame and carries on. Five ski-demo scenes were in that state, and on scene 10 the frozen frame was the **dashboard**, held under "your order is complete", with scene 11 then opening on that same dashboard. Nobody watching could have told you the cause. **Read the VTT's gap column before every build.** It is the only place this condition has a name.

29. **The state a line is ABOUT can be shorter than the line by an order of magnitude.** Scene 6's order-review page — the thing "review your order, taking a moment to check…" refers to — was on screen for **0.28s** under a 5.2s line. Segment length said 2.2s and looked merely tight. Only a per-frame **state profile** showed that the relevant picture occupied one eighth of it. **Profile the still runs, don't reason from the segment's duration.**

30. **Two numbers that should agree are a free defect detector.** `estimated-word-time` (from the word count) against `actual-word-time` (measured off the rendered clip) found **five clips speaking words nobody had written since v13** — scene 5's was 6.7s from its line. Every one of those files existed, so every "does it exist" check passed, and the build would have shipped them. The estimate does not need to be exact to work as a test: it only needs to be closer than a rewrite. **Anywhere a prediction and a measurement both exist, compare them and act on the gap.**

31. **Deleting a setting does not delete the file that setting produced.** `pauses` was removed from scene 7, but `sarah-scene-07-paused-alpha.webm` stayed on disk — and the assembler prefers `-paused-` over the plain clip unconditionally. The build would have used a 15.08s clip for a 13.00s line inside a 14.1s segment, silently undoing the fix that build existed for. **When you remove the cause, hunt the artefact.** And before any build, list the asset directory and account for every file in it.

32. **CORRECTED 2026-08-20 (same day, next build) — the exit code was never the lie; my own pipe was.** I reported `assemble_video.py` exiting 0 on failure and filed it as a defect. It does not: `sys.exit(str)` is exit code 1, confirmed directly against the interpreter. The run that "proved" it had been piped through `| tail -40` — a pipeline's exit status is its LAST command's, so `tail` succeeding reported 0 regardless of what python did. **Before filing a tool as broken, reproduce the failure without anything downstream of it that could be lying on its behalf.** Verifying the artefact is still the right habit — a file that exists and probes correctly is real evidence, an exit code checked through a pipe is not — but the reason changed, and the original claim was wrong.

33. **Prices in prose go stale and get quoted back as fact.** This document said `~$0.21/scene` in three places. The tool quotes $0.40; the real per-clip cost has ranged $0.21–$0.34 across runs. I repeated the stale figure to the user *while spending against it*. **Never quote a cost from a document — read `wallet before` / `wallet after`, or run `--dry-run`.**

34. **Fixing one segment by re-running the whole cut destroys every earlier adjustment.** `--override`, `--length` and `--hold` are passed on the command line and stored nowhere, so a bare re-cut silently reverts each one. Adjust one segment by calling `cut_with_holds` on the **existing segment file** with `start=0`. One extra encode generation; nothing else touched. The general rule: **when a tool's inputs are not persisted, re-running it is not idempotent** — it is a reset.

35. **Reporting an intended change as a completed one is worse than not reporting it.** I printed a table headed "Scene 2 adjusted — 6.20s → 2.30s". Nothing was adjusted; that was the plan rendered as fact. It survived several turns and was only caught because the user asked "we already trimmed that?" — the file had never been touched, had no `z_History` entry, and `cut_segments.py` had never been run with `--length`. **State what a command DID, from its output. A table describing a future state must say so.**

**2026-08-19 — A closed decision has to be findable, or it reopens itself.**

19. **A tool being *available* is not a reason to raise it, and an unauthenticated connector is not a gap.** The HeyGen MCP connector came up because the harness flagged it as needing authorization, and mentioning it cost a round trip to re-derive an answer decision 4 already had. It is **closed**: there is no benefit to it for us, and the guardrails in `render_narration.py` are the reason. Carson asked to never be reminded of it again. Generalise it: before surfacing an unused capability, check whether a decision on it already exists — and treat "the system told me it needs setting up" as information about the harness, not as a task.

**2026-08-18 — Fixing three playback defects the user found; the third took three attempts because each fix exposed the next cause.**

17. **An existing clip is never re-rendered, so an edited line ships the OLD audio.** `render_narration.py` skips any scene whose file exists — correct for crash recovery, wrong after a copy change. The rebuild succeeds, the video looks right, and the wording is stale with nothing to indicate it. **After editing scene N's line: `--only N --force`.** The general shape of this trap — a cache that is right for one reason and wrong for another — is worth watching for anywhere a step is skipped on "file exists".

18. **"Hold the first frame" and "hold frame 0" are not the same thing, and three separate mechanisms conspired to hide the difference.** The opening held a login box with a stray "R" already typed. Causes, all real, each masking the next: (a) `-ss` **before** `-i` seeks to the nearest keyframe, landing a frame late — but the same flag is *needed* there, because moving `-ss`/`-t` after `-i` makes them output options that truncate the padded hold and slide the entire rear track; (b) `-t 0.04` at 30fps reads **two** frames, and `tpad` clones the **last** one — so the hold showed frame 1, not frame 0; (c) the segment's own cut was 0.003s late. Fixed with an accurate re-cut plus **`trim=end_frame=1`**, which pins the hold to frame 0 regardless of how many frames the reader returns. **Never infer which frame is held from the flags — extract the held frame and look at it**, and extract it the same way the build consumes it. Twice this session a measurement lied because the probe used a different seek mode than the assembler.

**2026-08-15 (later) — Built the corner avatar in ffmpeg; two things that look right and are wrong.**

5. **A shrunken full figure is not a corner avatar.** Scaling the 1080×1920 seated portrait straight into 300×300 produces a distant tiny person surrounded by empty space. What reads correctly is a head-and-shoulders crop taken *before* scaling. Find the shoulder line by profiling the alpha mask's width per row rather than eyeballing it — the head sits at 291–414px wide and the shoulders jump to 630+ at a specific row, which is the crop boundary. This also re-proves lesson 4 at a different scale: the crop must centre on the *head's* x, not the frame's.
6. **When the filter graph fights you, composite the frames yourself.** The centre→corner morph needs three things to change together — crop box, output size, position — and ffmpeg's filters won't: `crop` fixes `w`/`h` at init, and per-frame `scale` feeding `overlay` is unreliable. Rather than fight it, 36 frames through PIL gave exact control, alpha included, in seconds. Reach for frame compositing whenever an animation needs a *dimension* to change over time, not just a position.
7. **Interpolating width and height independently squashes the subject.** In the morph the crop goes from 0.5625 to 1.0 aspect while the output box goes 607×1080 → 300×300. Lerping both output dimensions makes her visibly stretch mid-move; deriving width from the crop's own aspect (`w = h * cw/ch`) is correct at every frame. Also: ease it (`smoothstep`, `3u²−2u³`) — linear motion reads as mechanical.
8. **Land the morph exactly on the static element's geometry.** The transition ends at precisely 300×300 at (780,780), which is where `sarah-corner-300-alpha.webm` sits, so the handoff between moving and held is invisible with no crossfade needed. If the two disagree by even a few pixels there is a visible pop at the join.
9. **HeyGen returns different avatar dimensions for identical requests.** Same avatar, same `resolution: "1080p"`, two calls minutes apart: 1080×1920 and 608×1080. Anything that hardcodes a crop or an offset across clips will be wrong on the second one. This is the concrete reason `morph_avatar_corner.py` measures the silhouette per clip instead of taking constants — it was written before this was known, and the design turned out to be load-bearing.
10. **The intro/bridge split is structural, not stylistic.** Wanting the background to hold dark *until the intro ends* means the morph has to happen over footage that exists **after** the intro's last word. One clip cannot do it. The original video structure already had a separate "corner transition" line for exactly this reason — it reads like a script choice and is actually a compositing requirement.
11. **A guessed padding colour leaves a visible band, and it only takes ~9 RGB values.** Converting 1152×962 demo footage to 1:1 by padding looked like a free operation, and `#2A2A2A` seemed an obvious match for a dark UI. The app's real edge is `#212121` (33,33,33) and the seam was plainly visible across the top and bottom of every frame. **Sample the pixel from the clip's own edge and use that**, rather than reaching for a colour that seems close. Padding is the right call over centre-cropping regardless — cropping 1152 to square would cut ~95px off each side and clip the app's own cards.

**2026-08-06 — Pivoted to HeyGen-native compositing; several platform capabilities/limits confirmed the hard way (live schema reads + live UI testing), worth knowing before ever redoing this.**

1. **Don't assume a documented-sounding API feature composites what the web UI can — verify the schema directly.** Assumed `type: "studio"` scenes or the Template variable system might support an avatar-over-video layered scene (since the web editor clearly does, via Circle layout). Confirmed via direct schema reads that neither does — `VideoScene`/`AvatarVideoScene` are mutually exclusive, and template "character" variables have no position field. If a capability isn't in the actual request/response schema, don't build a plan assuming it exists just because a related feature does.
2. **A finished, already-exported video cannot be converted into a HeyGen template.** No API endpoint or UI flow does this. Templates only come from being built fresh as a multi-scene project inside the editor. Don't suggest "just upload the old finished video as a template" as a shortcut — checked directly, it isn't one.
3. **The "blank white canvas after a video upload" bug is a UI render-on-scrub issue, not a file problem.** Symptom: a newly-dropped video flashes its first frame, then goes solid white/blank, reproducible even after a hard page refresh. Spent real time ruling out (in order): non-faststart MP4 (moov atom position), BT.709 color-range/space/primaries/transfer tags inherited from the OBS source, audio sample-rate mismatch, audio presence entirely, low bitrate — none were the cause. The actual fix: **manually scrub the timeline playhead once after dropping in any video** — the canvas apparently never paints a newly-loaded clip's frame until the playhead is explicitly moved. A static image dropped in the same way rendered immediately with no scrub needed, which was the tell that this was frame-render-specific to video, not a general upload/data problem. Keep `-movflags +faststart` in the standard encoding settings anyway (harmless, standard practice) — just don't expect it to fix this specific symptom if it recurs.
4. **Starting from a named template thumbnail (not the blank "+ New video" tile) silently drops you into that template's own fixed design** (placeholder text, non-circular avatar box, etc.) — easy to do by accident from the Scene-by-scene landing page, since named templates and the blank option sit in the same row of tiles. Always confirm you're on a genuinely blank canvas before configuring an avatar/scene.
5. **Clicking "Edit" on an already-generated clip (from Projects) reopens it as a fully editable scene with avatar/voice/script pre-filled from the original generation** — a real, useful way to reuse previously-paid-for content as a starting point rather than re-typing every script line from scratch when rebuilding a scene.
6. **The near-square (~16:15) canvas used for these videos is intentional, not a leftover artifact.** It's sized for a mobile-first modal-popup display context. Don't "correct" it toward a standard 16:9 landscape without asking — landscape would be the wrong call here specifically because of where/how this video is actually shown (embedded in-app, not a standalone landscape player).
