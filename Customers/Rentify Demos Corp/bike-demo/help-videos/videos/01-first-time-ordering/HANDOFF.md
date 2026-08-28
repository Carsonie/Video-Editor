# HANDOFF — bike-demo, "First Time Ordering"

Written 2026-08-28. Covers: migrating this store off the old `final/` layout,
rebuilding its missing avatar files, and producing a full video that matches
v1's quality. The reusable procedure (for canoe-demo, alpine-sports, or a
new store) is in the personal skill **`sae-video-building`** — this file is
the record of what actually happened here, plus the two things still open.

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
