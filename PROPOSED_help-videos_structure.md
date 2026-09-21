# PROPOSAL — one folder shape from raw.mp4 to MUX

> ## ✅ ACCEPTED — REDUCED SCOPE, 2026-09-21
>
> Carson: *"keep `sandbox/ segments/ voice/`, and add `4_avatar/ 5_film/ 6_mux/`.
> This way we move on without breaking anything. And try improving the folder
> structure on our next video."*
>
> **DONE:** the three stage folders exist in `special-skis` with a README each.
> **ZERO code changed. Zero files moved.**
>
> **DEFERRED TO THE NEXT VIDEO** — the two LARGE renames in section 4:
> `sandbox/` → `2_scenes/` (all 5 editors + `editor_base/paths.py` + `build/` +
> 3 test suites) and the raw master → `0_master/` (`capture_of()` used 5×, plus
> every recipe's `script.json` `_note`). A NEW video can be born in the clean
> shape for free; converting 25 existing ones cannot.
>
> **ALSO DEFERRED, and Carson has not ruled on these** — the rest of the free
> column: `TOOLS/` up one level, `MUX-Management/` → `Studio/`, and the
> duplicated `.pem` keys out of the repo.
>
> ⚠ **`5_film/` DOES NOT HOLD THE MAC-VOICE FILM.** `<capture>-narrated.mp4`
> stays at the recipe root. Moving it is 4 code spots in 2 repos
> (`sae_vtt_sync.py:190`, `vtt_editor/serve.py:442, 932, 978`) and 26 files
> across 25 folders, for no gain. The root file is the REVIEW cut; `5_film/`
> holds the DELIVERABLE.

**Written for Carson's review. The original proposal follows unchanged.** 2026-09-21.

Carson: *"I am thinking to do the HeyGen and the MUX work inside the
Video-Editor project folder… So everything is linear from after the raw.mp4, to
finished product. For each Customer/Store/help-videos folder, we need this to
hold all our work from raw.mp4 to MUX upload and hosting."*

---

## 1 — THE PIPELINE, AS IT REALLY RUNS

Steps 1-6 are **built and proven on special-skis**. Steps 7-10 are **not built**.

```
  ┌─ Basic_E2E_Testing ─┐  ┌──────────── Video-Editor (this repo) ────────────┐
  │                     │  │                                                  │
  1  RECORD ────────────────> 2 FIRST EDIT ──> 3 WORDS ──> 4 FRAMES ──> 5 VOICE
     OBS wraps an E2E run     first_edit.py    vtt_editor   SAE         voice_scenes
     raw .mp4, 25 fps         script.json      the words    the frames  per scene
                              segments/        is truth     sandbox/    voice/*.m4a
                                                  │            │           │
                                                  └────── sae_vtt_sync ────┘
                                                                │
                                                          6 FILM (mac voice)
                                                          <capture>-narrated.mp4
                                                                │
        ══════════════════ everything below is NOT BUILT ═══════▼═════════════
                                                                │
                                7 AVATAR ─────────────> 8 ASSEMBLE ──> 9 MUX
                                  HeyGen: Sarah           the shippable  upload
                                  replaces the mac        cut            asset id
                                  voice, per scene                       playback id
                                                                │
                                                        10 RELEASE
                                                        Completed_Videos/
```

---

## 2 — WHAT IS THERE TODAY, AND THE SIX PROBLEMS

### The same job has two different folder shapes

```
special-skis/                          01-first-time-ordering/
  (BCP, the settled shape, 1.1 GB)       (the original avatar work, 485 MB)

  master mp4        1,135 MB             FINAL_video.mp4
  script.json                            HANDOFF.md
  bounds.json                            TRACK_front_full.webm
  stretch_report.json                    TRACK_rear_full.mp4
  segments/            12 MB             dev/                  60 MB
  sandbox/             18 MB             onepass/              27 MB
  voice/              5.4 MB             preview/             7.6 MB
  chapters.{json,txt,ffmetadata}         sandbox/
  *.vtt  *.vtt.html                      sarah_clips/          50 MB
  <capture>-narrated.mp4  18 MB          video/                21 MB
                                         work/
                                         z_History/
```

| # | problem | the evidence |
|---|---|---|
| **P1** | **Two shapes, nothing says which is right.** | `special-skis` has 5 folders. `01-first-time-ordering` has 8 plus 4 loose files. A person opening either cannot tell which is the pattern. |
| **P2** | **Six places for intermediate renders.** | `dev/`, `onepass/`, `preview/`, `sarah_clips/`, `video/Master_Set_Of_Segments/`, `video/sandbox_mp4_scenes/`. 485 MB, most of it superseded. |
| **P3** | **The 1.1 GB master sits with the 30 KB working files.** | After today's archive, **95% of `special-skis/` is one read-only input file.** |
| **P4** | **HeyGen and MUX are outside `Customers/` entirely.** | `MUX-Management/Help_Videos/HeyGen/` — 722 MB, and it holds ONE video's work (`first-time-ordering`) mixed in with shared assets (`Sarah/`, `avatars/`, `audio/`). So a store's video work lives in two unconnected places. |
| **P5** | **No per-video record of the MUX side.** | `HeyGen/metadata.json` has one entry with `stages.voiceover.status: done`, `stages.combine.status: pending`. Nothing anywhere holds an asset id, a playback id, or an upload date. |
| **P6** | **Signing keys are duplicated in the tree.** | `MUX/mux-signing-key-2bCop….pem` **and** `VSCode_Mux_Ex/mux-signing-key-2bCop….pem` — the same key, twice. Plus 2 `.env` token files. |

### Lessons the original video already taught us

⚠ **Prose drifts from data, and the doc says so itself.** `HANDOFF.md` names the
source capture, then warns in its own text: *"Don't read this off the doc — read
`boundaries.json`'s `raw` field."* It had named the wrong file for 5 days.
→ **Rule: every stage writes a small JSON record. Prose never holds a fact.**

⚠ **A video and the words that made it must not be separable.**
`video/script_v32.json` + `ski-demo_first-time-ordering_v32.mp4`, paired. That
pairing is why `release_video.py` refuses a release with no `script_v<N>.json`.
→ **Rule: keep that, and extend it to the MUX record.**

⚠ **Six render folders is what "just put it here for now" becomes.**
→ **Rule: one folder per pipeline stage, numbered, and nothing else.**

---

## 3 — THE PROPOSAL

### Design rules

1. **One video, one folder.** Everything for it inside, nothing about it outside.
2. **The stage number IS the order.** `1_` … `6_` sorts into the pipeline.
3. **The raw master is an input, not work.** It moves out of the working folder.
4. **Shared assets live once**, at repo level — Sarah, avatars, silence beds, overlay cards.
5. **Secrets live once, outside the repo.**
6. **Each stage writes a `*_state.json`.** That is the record; docs only explain.

### The store folder — KEEP the outer names

```
Customers/<Business>/<store>/help-videos/
│
├── BCP_raw_mp4/            ◀ KEEP THE NAME. record_flow.ts's rawSubdirFor()
├── UI_raw_mp4/             ◀ and scene_script.py's raw_folder() read these off
│                             disk. Renaming broke 5 files on 2026-09-15.
├── TOOLS/                  ◀ MOVE UP one level (it is in BCP_raw_mp4/ today).
│   ├── back-to-dashboard.png   It serves BOTH surfaces, not just BCP.
│   ├── intro-special-skis.png
│   ├── make_overlay.py  make_intro.py  NOTE.md
│
├── development_videos/     ◀ KEEP. The avatar-path videos.
├── Completed_Videos/       ◀ KEEP. What release_video.py writes.
└── z_History/              ◀ KEEP.
```

### The working folder — the NEW part

```
<recipe or video>/
│
├── 0_master/                       ◀ NEW  the raw capture, READ ONLY
│   ├── <capture>.mp4                     1,135 MB — an input, never edited
│   └── .handoff.md                       the recording brief
│
├── script.json                     ◀ THE SINGLE SOURCE OF TRUTH for the words
├── bounds.json                           the cut plan
├── stretch_report.json                   the scene lengths
│
├── 1_cuts/                         ◀ was segments/
│   └── <NN-label>-f<factor>-<in>_<out>-<fps>fps.mp4
│
├── 2_scenes/                       ◀ was sandbox/   THE FRAME WORK
│   ├── 00-intro/segment.mp4              a bookend (00 first, 99 last)
│   ├── 01-sign-in/segment.mp4
│   │   └── z_History/<stamp>/            one-step undo per scene
│   └── …  22-signed-out/
│
├── 3_voice/                        ◀ was voice/     THE MAC VOICE
│   ├── <NN>-<label>.m4a                  exactly as long as its own picture
│   └── state.json                        rate, spoken, built, lead  ← LIVE FACTS
│
├── 4_avatar/                       ◀ NEW            HEYGEN
│   ├── requests/<NN>-<label>.json        what was sent, per scene
│   ├── clips/<NN>-<label>.webm           what came back (alpha)
│   ├── audio/<NN>-<label>.mp3            the HeyGen voiceover
│   └── heygen_state.json                 job id · status · cost · voice id
│
├── 5_film/                         ◀ NEW (partly)   THE ASSEMBLED CUTS
│   ├── <capture>-narrated.mp4            the MAC-VOICE cut, for review
│   ├── <capture>-avatar_v<N>.mp4         the SHIPPABLE cut
│   └── script_v<N>.json                  the words that made v<N>
│
├── 6_mux/                          ◀ NEW            HOSTING
│   └── mux_state.json                    asset id · playback id · uploaded
│                                         · duration · policy · signed-url notes
│
├── chapters.{json,txt,ffmetadata}         one per player: Mux · YouTube · QuickTime
├── <name>.vtt  <name>.vtt.html            the timing table
└── z_History/                              superseded work, never deleted
```

### Repo level — fold `MUX-Management` into a `Studio/`

```
Video-Editor/
│
├── Customers/                      the per-video work, above
│
├── Studio/                     ◀ NEW  was MUX-Management/Help_Videos/
│   ├── avatars/                      Sarah/, annie/, dt/, pamela/  (shared)
│   ├── beds/                         silence-10s-pure.wav, roomtone beds
│   ├── heygen/                       scripts/, config/, lessons learned
│   ├── mux/                          the CLI, the JWT notes, the Makefile
│   └── docs/                         Mux Overview · YouTube Setup · VIDEO_CREATION
│
├── Video-Editors/                  the 5 editors + editor_base + build/  (UNCHANGED)
└── z_History/
    └── MUX-Management_pre-Studio/    where the 679 MB HeyGen videos/ go
```

⚠ **The secrets leave the repo.** `MUX/*.pem` ×2, `*.env` ×2, and the duplicate
`.pem` under `VSCode_Mux_Ex/`. One copy, in `~/.rentify/mux/`, read by path from
an env var. They are gitignored today, which hides the duplication rather than
fixing it.

---

## 4 — WHAT EACH MOVE COSTS

Sorted by cost. **Nothing here is done yet.**

| move | breaks | cost |
|---|---|---|
| `TOOLS/` up one level | nothing — only `NOTE.md` names the path | **free** |
| add `4_avatar/ 5_film/ 6_mux/` | nothing — new folders | **free** |
| `MUX-Management/` → `Studio/` | no code; docs only | **free**, and it moves 679 MB of old HeyGen renders to `z_History/` |
| secrets out of the repo | the `VSCode_Mux_Ex` Makefile's key path | **small** |
| `segments/` → `1_cuts/` | `sae_vtt_sync.py` (`f.cut`), `stretch_scenes.py`, `stretch_request.py` | **medium** |
| `voice/` → `3_voice/` | `voice_scenes.py`, `sae_vtt_sync.py`, `vtt_editor/serve.py` | **medium** |
| `sandbox/` → `2_scenes/` | `editor_base/paths.py` + **all 5 editors** + `build/*` + 3 test suites | **LARGE** |
| raw master → `0_master/` | `capture_of()` at `vtt_editor/serve.py:164,179` (used 5×), `vtt_artifact.py:99`, `bounds.json`'s `raw`, `script.json`'s `_note` on every recipe | **LARGE** |

### My recommendation

**Do the free column now. Leave the renames.**

`sandbox/` is named in `editor_base/paths.py` and read by all five editors,
`build/`, and three test suites. `0_master/` needs every recipe's `script.json`
`_note` rewritten. Neither buys you anything the numbering does not — and the
2026-09-15 split already proved that a rename breaks whatever *names* a folder,
silently, in places nobody lists in advance.

So: **keep `sandbox/ segments/ voice/`, and add `4_avatar/ 5_film/ 6_mux/`.**
The pipeline reads left to right either way, and steps 7-10 get a home today.

---

## 5 — WHAT STILL HAS TO BE BUILT

| # | stage | what is missing |
|---|---|---|
| 7 | **AVATAR** | a per-scene HeyGen request/collect tool, and `heygen_state.json`. `build/make_scene_overlays.py` already composites an avatar into a corner — the gap is the ordering and the record, not the compositing. ⚠ Spend needs Carson's sign-off, one line with the $, every time. |
| 8 | **ASSEMBLE** | `sae_vtt_sync.py` builds the mac-voice film by stream copy today. The avatar cut needs the same thing with Sarah's audio in place of `3_voice/`. ⚠ `build/build_scenes.py --join` is NOT it — it requires an `avatar.webm` in **every** scene, so it refuses a BCP recipe outright (all 23 special-skis folders have none). |
| 9 | **MUX** | an upload tool and `mux_state.json`. The tokens, the signing keys and the JWT notes all exist in `VSCode_Mux_Ex/`; nothing joins them to a video folder. |
| 10 | **RELEASE** | `build/release_video.py` exists and enforces video + `script_v<N>.json`. It needs to carry `mux_state.json` too, or a released video cannot say where it is hosted. |

---

## 6 — THE ONE-LINE ANSWER TO "IS IT LINEAR?"

Today: **yes for steps 1-6, and they all live in the store's folder.**
Steps 7-10 live in `MUX-Management/`, keyed to one video by name only.

After this proposal: **yes for all ten**, in one folder per video, with a
`*_state.json` at every stage that has an outside service behind it.
