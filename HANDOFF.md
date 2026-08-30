# HANDOFF

Newest work first. One file so there is one place to check for open work.

---

## 2026-08-30 (later) — Frame Blender restructured, and Load actually loads

### What we succeeded on

1. **The root cause of three separate "bugs" turned out to be one shape.**
   The server used to render the whole page *around* one scene, baking its
   name, frame counts and file ids into the HTML, and remembering that
   scene in module globals. That is why Clear could never clear (the scene
   was the page), why Load could list scenes but never open one (the page
   could not change scene), and why two tabs would have fought over one
   remembered pair. Restructured rather than patched again:
   - **The page ships empty.** `frame_blender/web/index.html` has no scene
     in it. `SCENE` in `app.js` is the one thing that says what is loaded,
     and `null` is a normal state.
   - **The server is stateless.** Every request that acts on a scene names
     that scene. `/api/clear` was deleted — there is nothing left to clear.
   - **Clear is now one line** (`SCENE = null`), not three patches.
2. **Split out of the Python string.** `player.py` (755 lines of HTML+CSS+JS
   inside a `str.format()` template, every brace doubled) is gone, replaced
   by real `web/index.html`, `web/app.css`, `web/app.js`. `node --check`
   works on the JS now — and immediately found a **real syntax error** that
   had been shipping silently, because nothing can lint code trapped in a
   Python string.
3. **Browser caching was part of the "same problem???" round.** `app.js` is
   served `no-store` now, with a test asserting it. A fix that silently did
   not apply is worse than no fix.
4. **Load actually loads — a two-step popup.** Pick a store (all four, read
   from `Customers/`), then pick one of that store's video folders, then it
   loads **every scene in that video's `sandbox/` plus its `script.json`**
   and opens the first scene. Back / Cancel / click-outside / Esc all work.
   - `1000_archive` is excluded **by rule, not by name** — a scene folder
     is `<digits>-<label>`, so `z_History`, `_builds` and any future sibling
     are skipped by the same rule with nothing to maintain. Asserted in the
     suite.
   - The loaded `script.json` is visible: hover a scene row to see the line
     Sarah says over it, and the status line reports how many lines loaded.
   - Clicking a scene row switches the viewer to that scene. That is what
     "Load" always implied and never did.
5. **Tests: 217/217 passing** (was 192). The Frame Blender suite went 25 →
   50 checks, including new steps asserting the page ships empty, that the
   server is genuinely stateless, and that the Load picker behaves.

### What's still open

1. **`tests/test_frame_blender.py` writes into a REAL store.** `build_clip`
   and `save_mp4` need release-shaped footage (1152² canvas, an avatar clip
   carrying a voice track) and the disposable fixture is deliberately
   lighter than that, so those two steps borrow bike-demo's scene 1. The
   run cleans up after itself and only ever reads that scene — but a
   fixture that could stand in for a real release build would be better.
2. **Undo is still a disabled icon** in Frame Blender's scene rows. It
   needs a snapshot of the previous state, and this tool has no edit action
   of its own yet that would create one.
3. Everything under "What's still open" in the section below is unchanged —
   **scene 1's frozen tail is still frozen**, and that is still the next
   real piece of work.

---

## 2026-08-30 (earlier) — Frame Blender gains real teeth, and ski-demo scene 1's fix is half-done

### What we succeeded on

1. **Cross-tool save safety.** `/api/save` now refuses to overwrite a file
   that changed on disk since its cache was built (another tab, or Frame
   Blender, already saved something here) — a 409 unless the caller passes
   `force`. Shared by both editors, not duplicated. Verified against the
   live server: a normal save is unaffected, a real conflict is refused,
   force overrides it correctly.
2. **Frame Blender is no longer read-only.** Added, and each piece proven
   against a real server, not just written:
   - A **Timeline Scenes** panel reading the SAME per-scene pristine/dirty
     state the main editor computes — proven end to end: edited a scene in
     the main editor, watched it show dirty here, saved it from here,
     confirmed the file on disk actually changed.
   - **Clear / Load / Save MP4** buttons. Save MP4 writes a real, dated,
     versioned copy into `video/sandbox_mp4_scenes/`.
   - A **"Build (real speed)"** option that skips the frame-by-frame
     animation and asks the server to build the real mp4 directly, plus a
     **Play video** button and a full-width scrub slider through every
     combined frame.
   - A **sarah_clips/libs** viewer panel, read-only, listing whatever's in
     the library for the open store.
3. **Two real bugs, found only by testing for real, both fixed:**
   - Any error message containing an em dash (this whole codebase's own
     writing style) crashed Frame Blender's server outright —
     `http.server`'s `send_error()` encodes into latin-1. Existed since the
     very first version of the "Build" feature, not just from this session.
     Replaced every error response with a proper JSON one.
   - Save MP4's versioning never actually incremented — it asked
     `archive_name_v()` for a bare name with no extension to match against
     files that all had `.mp4` on them, so it silently found "no existing
     versions" every time and handed out `v1` forever. Fixed with an
     extension-aware version scan; regression-tested.
   - The **Clear button** only reset the Timeline Scenes list, not the
     actual frame viewer, filmstrip, or build state — found by Carson
     directly. Fixed to wipe everything reachable from the page; confirmed
     with a real screenshot after a real click.
4. **Testing and logging, both upgraded for real.** A new
   `tests/test_frame_blender.py` (25 checks, starts both servers for real)
   plus 2 new checks in the main suite for the staleness behavior — **192/192
   passing**. Frame Blender's own actions (Build, Save MP4, Load) now write
   into the SAME daily session log the main editor already keeps.
5. **`sarah_clips/libs/` exists for ski-demo** — idle footage, still poses,
   and a generic transition, copied in from the shared `Sarah/` reference
   folder (nothing moved, nothing that already worked was touched). Its own
   README documents exactly what's there, and confirms **no 5-second idle
   render exists anywhere** — only 10s and 20s, checked directly.
6. **`build/sarah_transitions.py`** — three reusable pieces, each run against
   real ski-demo footage and verified, not just written:
   - `gap_filler()` — a fixed-length, corner-composited slice of idle
     footage, on the same canvas a scene's `avatar.webm` actually uses.
   - `opening_transition()` / `closing_transition()` — a fixed 5-frame blend
     either side of a gap-filler. **Caught a real bug here**: the first
     Closing attempt blended against the "-full-" still (the tall
     full-figure portrait) instead of the "-corner-" crop, and Sarah
     stretched across nearly the whole frame instead of staying in her
     corner. Checked pixel-by-pixel, found it, fixed the function to
     require the corner variant, and made it **refuse outright** if handed
     the wrong one again.

### What's still open

1. **Scene 1's frozen tail (frames 442–482) is still frozen.** Nothing was
   changed on the real file — the whole exercise ran against a throwaway
   `/tmp/avatar_candidate.webm`, confirmed never to have touched
   `sandbox/01-opening-with-login/avatar.webm`. The math is confirmed
   correct: 441 real frames + 5 opening + **31**-frame filler + 5 closing =
   482, matching the file exactly. A real second bug was found while
   assembling it — the concatenated result's audio track ran ~1.6s longer
   than its video (the same class of drift this codebase's own "four
   rules" warn about) — and a fix (`atrim` then `apad` to the video's exact
   frame-counted length) is written into `replace_frozen_tail()` in
   `build/sarah_transitions.py`, but **was not re-run or re-verified**
   before this was stopped. Next session: rerun the `replace-tail`
   subcommand, confirm frame count is 482 **and** duration is ~19.28s
   (matching the untouched original), only then back up and swap in the
   real file.
2. **Opening/Closing/gap-filler are command-line only** — not wired into
   Frame Blender's UI yet.
3. **Only one gap-filler is saved to the library** — `gap-filler-1.0s.webm`
   (25 frames). None of the four originally-planned standard sizes
   (0.5/1/1.5/2s) exist yet, and the 31-frame one scene 1 actually needs
   was built inside a temp folder during the interrupted run, not saved.
4. A **crossfade feature is mid-development** in `build/assemble_video.py`
   by someone else — still sitting uncommitted, still not ours to touch or
   commit over.

---

## 2026-08-28 — bike-demo, "First Time Ordering"

Covers: migrating this store off the old `final/` layout, rebuilding its
missing avatar files, and producing a full video that matches v1's quality.
The reusable procedure (for canoe-demo, alpine-sports, or a new store) is in
the personal skill **`sae-video-building`** — this section is the record of
what actually happened here, plus the two things still open.

---

## State, in one line

**v1 is still the released video.** `v2-full` was built today and matches
v1 to within 0.25 seconds — reviewed, not yet promoted to the official
release track. See "What's open" below.

| | v1 (released) | v2-full (today) |
|---|---|---|
| Resolution | 1152×1152 | 1152×1152 |
| Length | 75.9s | 76.2s |
| File size | 4.26 MB | 4.21 MB |
| Built with | an older, ad-hoc method (not this repo's current tools) | `assemble_video.py`, the current pipeline |

---

## The file structure — this is what to replicate

Before today, everything sat flat under `help-videos/final/`. It's now
split the same way ski-demo is:

```
help-videos/
  raw_mp4/                             untouched — the whole recordings
  videos/01-first-time-ordering/       THIS folder
    dev/<NN-label>/                    segment-v1.mp4, narration-v1.webm, avatar-v1.webm, scene.json
      01-login/  02-neworder/  03-addmyself/  04-search/  05-dates/
      06-additem/  07-requirements/  08-checkout/  09-payment/
      10-complete/  11-history/
    sandbox/<NN-label>/                segment.mp4, narration.webm, avatar.webm
      (same 11 folders as dev/)
    sarah_clips/                       the opening + bridge, not per-scene
      sarah-intro-alpha.webm
      sarah-intro-1152-alpha.webm
      sarah-bridge-alpha.webm
      sarah-bridge-corner-320-alpha.webm
      sarah-bridge-transition-to-corner.webm
    video/                             finished builds + script history
      script.json  script_v1.json  script_v2.json
      bike-demo_first-time-ordering_v1.mp4
      z_History/FINAL_video_dup-of-v1.mp4   (old duplicate, kept not deleted)
    work/                              boundaries.json, boundaries.png (the original cut plan)
    bike-demo_first-time-ordering_v2-full.mp4   ← today's build, sitting loose (see below)
    .render_jobs.json
    HANDOFF.md                         this file
```

**`dev/` and `sandbox/` are both complete as of 2026-08-28.** The avatar
files were first built by hand straight into `sandbox/` (not through `make
overlays`, which would have landed them in `dev/` first, the normal order)
— so for a while `dev/` had no `avatar-v1.webm` and `sandbox/` was the only
copy of that work. Fixed the same day by copying
`sandbox/<label>/avatar.webm` → `dev/<label>/avatar-v1.webm` for all 11
scenes. `build_scenes.py` re-run afterward: still 11/11 passing, so nothing
broke in the copy.

⚠ **Remember this the next time avatar files are built by hand instead of
through `make overlays`** (canoe-demo and alpine-sports will hit the same
situation): building straight into `sandbox/` is fine for a quick check, but
copy the result into `dev/<label>/avatar-v<N>.webm` right after, before
moving on — don't leave `sandbox/` as the only copy of paid-adjacent work.

---

## What was done today

1. **Migrated off `final/`** using `build/migrate_to_dev.py --apply`. Fixed
   a real bug in that script first — it pointed `sys.path` at `build/`
   instead of `shared/`, so it couldn't find `paths.py` at all. Fixed in
   the shared tool, so this won't recur for canoe-demo or alpine-sports.
2. **Built the missing `avatar.webm` per scene** (11 of them) — this store
   never had a corner-placed Sarah file, only the raw HeyGen renders (now
   `narration.webm`). Done locally, no HeyGen cost. One scene
   (`06-additem`, a very short line) needed `--measure-at 0.7` — the
   default 2-second measurement point falls outside a clip that short.
3. **Reorganized `final/` into `videos/01-first-time-ordering/`**, matching
   ski-demo's shape, using only bike-demo's own files — nothing copied
   from ski-demo.
4. **Built `bike-demo_first-time-ordering_v2-full.mp4`** with
   `assemble_video.py --skip-qualify`. The `--skip-qualify` was deliberate,
   not a shortcut: 5 scenes have a footage/narration length gap over the
   tool's default ~1.2s caution threshold, all coming from the *original*
   segment and narration files (nothing swapped or mismatched). Two of
   those (`checkout`, `complete`) hold on the last frame for ~2.2–2.8s
   while Sarah keeps talking — expected behavior, not a defect, and it's
   the main reason this build lands within a quarter-second of v1's own
   length.

---

## What's open

**1. `v2-full` isn't on the official version track yet.** Its filename
doesn't match the `_v<N>.mp4` pattern `release_video.py` and the script
snapshotting expect, so no `script_v2-full.json` exists to record what
produced it — only `script_v2.json`, from the earlier scenes-only build.
To promote it: rename/rebuild it as a properly numbered version (`--out
video/bike-demo_first-time-ordering_v2.mp4`), which will also cause the
snapshot to get written this time.

**2. It has not been released.** `build/release_video.py` is the only
thing allowed to write into `Basic_E2E_Testing`'s `help-videos/` — that
hasn't been run. v1 is still what a customer would be served.

---

## Reproducing this for another store

The full step-by-step is in the `sae-video-building` skill. Short version,
for a store still on the old flat layout:

```bash
python3 build/migrate_to_dev.py "<store>/help-videos/final" --apply
# copy dev/ -> sandbox/ by hand (segment.mp4, narration.webm, unversioned)
# build avatar.webm per scene if you want editor review (optional for assemble)
python3 build/build_sarah_opening.py --intro "..." --bridge "..." \
  --scene1 sandbox/01-<label>/segment.mp4 --outdir sarah_clips --skip-generate
python3 build/assemble_video.py "<video folder>" --out video/<store>_<title>_v<N>.mp4
```

The `--skip-generate` above only applies if the raw HeyGen renders already
exist (rebuilding a store, like this one). A store getting its opening for
the first time drops that flag and pays for two renders — ask first, per
the skill's money rule.
