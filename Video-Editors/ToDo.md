# ToDo

Open work in this repo. Ranked `P1`–`P4`, most severe first, same convention as
`Basic_E2E_Testing`'s own list.

**This is the only open-work list in the repo.** `SVM.md` (the migration plan)
and `README-CODE-CLEANUP-PLAN.md` (the four editors' cleanup) were both
finished and deleted on 2026-09-04; whatever they still had that mattered is
below. Git history has them if a decision needs re-reading.

---

## P1 — the work itself, and holes in the playbook

### P1.3 The video queue — 20 of 24 not started, and one built-but-unreleased

**This is what the repo is FOR, and it was in no list until 2026-09-04.**

Four stores, six E2E scenarios each, so **24 help videos**. Counted from
the six recipes in `Basic_E2E_Testing/.claude/skills/`: `owner-one-item`,
`owner-three-items`, `owner-plus-one-invite-one-item-each`,
`owner-plus-three-invites-two-items-each`,
`owner-no-items-plus-one-invite-one-item`, `one-day-rental-owner-one-item`.

State on 2026-09-04, read off the folders rather than off any doc:

| Store | `01-first-time-ordering` | built here | released to `Basic` |
|---|---|---|---|
| ski-demo | 13 scenes | `_v32.mp4` | **NO — see below** |
| canoe-demo | 11 scenes | yes | `canoe-demo_first-time-ordering_v2.mp4` |
| bike-demo | 12 scenes | yes | `bike-demo_first-time-ordering_v1.mp4` |
| alpine-sports | 11 scenes | yes | `alpine-sports_first-time-ordering_v2.mp4` |

**Videos 02–06 do not exist for any store. That is 20 of the 24.**

**The odd one out: ski-demo has nothing released.** Its
`help-videos/` folder in `Basic_E2E_Testing` holds a README and nothing
else, while the other three each carry a finished mp4. Yet ski-demo is the
reference video — the one PIPELINE.md is written around, and the only one
with a `_v32`. Either the release was never run for it or it was undone.
`build/release_video.py` is the only thing that may write there.
**Check this first: it is one command, not a video's worth of work.**

`PIPELINE.md` opened with "One video is finished (ski-demo). Twenty-three
more are coming" — written before the other three shipped. Corrected the
same day.

Each remaining video is the full nine-step pipeline, and **step 5 spends
real money on HeyGen**. Nothing here should be batched without asking.

### P1.2 The demo checklist has never been walked by hand here

The suites all pass (678 checks) and every page loads, but **no one has
clicked these controls by hand in this repo**. A dead page answers every
endpoint perfectly — that has now happened three separate times, and only a
browser ever caught it.

The list, kept from `SVM.md` §3 (deleted 2026-09-04) and brought up to date —
the ports and the paths in the original were pre-split:

- [ ] each of the four editors starts and prints its browse root and session
      log (`.claude/skills/editor-launchers/SKILL.md` launches them)
- [ ] the browse page lists the ski-demo store
- [ ] **MP4 Splitter** (8845): opens a raw recording, plays with sound, marks,
      ＋/− Frame, ＋/− Zone, Undo, Loop Zone, the segment list matches the
      slider bands, Cut writes to `dev/_cuts/`
- [ ] **Hand off** deposits into `dev/`, archiving what was there to
      `dev/z_History/<date>-v_N/`
- [ ] **Segment and Avatar Editor** (8846): opens a scene layered, and 2+ as a
      timeline; frame and zone edits; Save writes the exact frame count; Cut;
      Join; Split; the save-as-a-set lock; the VTT reads and its lines save
- [ ] **Avatar Editor** (8844) and **Frame Blender** (8843): the same pass over
      their own controls — neither existed when this list was written

Partly done 2026-09-04: the Avatar Editor's library, Frame Selector, Copy
Selected, Paste and Clear were driven by hand, and MP4 Splitter's navigation,
Mark and Frame Editor. The rest of the list has not been.

---

## P2 — the transfers, which is what makes this repo independent

### P2.1 `Customers/` is a hardcoded root

`safe_join()` pins every path under a folder literally named `Customers/`, and
`find_repo_root()` walks up looking for one. It works, but it means this repo's
data folder has to carry `Basic_E2E_Testing`'s name for it. Make the root
configurable — an argument or an env var — with `Customers/` the default.

Kept from `SVM.md` (deleted 2026-09-04): `find_repo_root()` walks up looking
for a folder literally called `Customers/`, so it lands on this repo root by
itself — but the demo data still has to carry `Basic_E2E_Testing`'s name for
it. That is the whole of the problem; there is nothing subtler in it.

*(P2.2 and P2.3 were both done 2026-08-28 — see Done.)*

---

## P3 — smaller, and each already understood

### P3.1 `tests/fixture.py` hard-codes a path into ski-demo's `dev/`

`SRC` reaches into `Rentify Demos Corp/ski-demo/.../dev/01-login-and-code/` for
its source clips. The five-`..` repo walk is fixed; this is not. The tests fail
for a confusing reason on a machine whose demo data is a different store.

### P3.2 The sandbox snapshot is per BATCH, not per save — confirm that is right

`Save all scenes` snapshots the whole sandbox to `sandbox/z_History/`; a
single-scene save does not. ski-demo's sandbox is 80 MB, so per-click would
fill a disk with near-identical copies, and each scene already keeps its own
file history. **My call, not asked for** — worth confirming or changing.

### ~~P3.3 `layers.sh` — used, or an orphan?~~ — **an orphan. Deleted 2026-09-04.**

It was worse than unused: it pointed at
`Basic_E2E_Testing/.claude/agent-tools/6_end-customer-help-video-creations/video_players`,
a path that stopped existing when the tools moved here on 2026-08-28, and it
drove port 8842 — the old combined server, which is no longer part of "run the
editors". `.claude/skills/editor-launchers/SKILL.md` is what launches an editor
now.

### P3.4 bike-demo's `TRACK_*` files — moved aside, not read by any build

`Customers/Rentify Demos Corp/bike-demo/help-videos/final/` held three files
no script or doc references: `TRACK_front_full.webm`, `TRACK_front_sarah.webm`,
`TRACK_rear_full.mp4`. They look like an earlier, abandoned compositing
attempt — not the `sarah-*-alpha.webm` / `segments/` files the actual v1
build reads.

**Moved 2026-08-28** out of `final/` into
`z_History/2026-08-28_v1/`, so they stop cluttering the working folder
without deleting anything yet.

`Customers/` is gitignored, so there is no commit history to date them by.
**Last usage** below is each file's on-disk modified time from before the
move — the best signal available, and only a proxy for "last touched," not
"last built from."

| File | Last usage (mtime) |
|---|---|
| `TRACK_front_sarah.webm` | 2026-08-19 22:52 |
| `TRACK_front_full.webm` | 2026-08-19 23:02 |
| `TRACK_rear_full.mp4` | 2026-08-19 23:02 |

If no future bike-demo rebuild reads these, delete them from
`z_History/2026-08-28_v1/`. Don't delete on this entry alone — confirm first
that a rebuild of bike-demo (once it's migrated off the old `final/` layout
per P4.1) still doesn't touch them.

---

### ~~P3.x `ruff` flags nine things in `build/`~~ — **fixed 2026-09-04**

All nine gone, and `ruff check .` is now clean across the whole repo, not
just the editors.

The two `import paths` cases were checked by hand first, as this entry
warned to: in both `export_bookends.py` and `release_video.py` the only
other mentions of `paths` are comments, and the `sys.path.insert` that puts
`shared/` on the path is a separate line above, which stays. The imports
really were doing nothing.

`build/assemble_video.py` stays excluded in `pyproject.toml` while it is
uncommitted work-in-progress.

### P3.5 Nothing can seed this repo's demo data on a fresh machine

`setup_demo.py` used to copy ~150 MB of ski-demo out of `Basic_E2E_Testing`.
It was deleted on 2026-09-04 because **it can no longer do that**: the store's
`help-videos/` moved HERE on 2026-08-28, and the folder it copied FROM now
holds a single `README.md`.

So the gap it papered over is now open, and it is worth stating plainly rather
than discovering it on a new laptop:

- `Customers/` is gitignored, so a clone of this repo has **no video data at
  all** — no store, no scenes, no raw recordings.
- Every test suite builds its own fixture under `Customers/_Editor_Test/`, so
  **the 678 checks still pass on a bare clone**. It is the editors that have
  nothing to open.

Nobody has needed this yet, because there is one machine. Whoever needs it
second needs either a copy script pointed at wherever the data actually lives,
or a documented "bring the folder by hand" step. Not worth building on spec.

### P3.6 The extraction cache is keyed on the SOURCE PATH

Kept from `SVM.md` (deleted 2026-09-04) because it costs time once per person:
move or rename a store's folder and every cached extraction is invalidated —
the slug is a hash of the absolute source path. Nothing breaks; the first open
of each clip is just slow again while it re-extracts.

---

## P4 — later, by design

*(P4.1 was done 2026-08-28 — see Done.)*

### P4.2 `dev` → `sandbox` stays a MANUAL copy — decided, not outstanding

Recorded here so it is not "fixed" by accident. The Segment and Avatar Editor
reads `sandbox` only and never falls back to `dev`, which is what stops an edit
looking like it worked when it went somewhere else. Moving a fresh cut across
is a deliberate human step.

---

## Done

- ~~The four editors' code cleanup~~ — all 19 steps of
  `README-CODE-CLEANUP-PLAN.md`, done 2026-09-03/04 on branch
  `plan-implementation`, one commit per step. `editor_base/` replaced three
  copies of `frames`/`paths`/`vtt`; every page became static files fed by an
  API; `gap-builder.js`'s 21 globals became three state objects and the file
  split five ways; Frame Blender's `app.js` split five ways; Avatar Editor got
  its own cache; `ruff` was added. 538 -> 678 checks. **The plan file is
  deleted; `HANDOFF.md`'s 2026-09-04 entry is the summary, and the four things
  worth carrying forward are in it.**
- ~~P2.2 import a raw recording from `Basic`~~ — **not needed**: `record_flow.ts`
  over there now writes the capture straight into this repo's `raw_mp4/`, so
  there is no import step to build (2026-08-28)
- ~~P2.3 return a finished video to `Basic`~~ — `build/release_video.py`. Copies
  one blessed build, stands the previous release down into `z_History/`, refuses
  a build whose clock and frame count disagree (2026-08-28)
- ~~P4.1 bring the other stores over~~ — canoe-demo, bike-demo and alpine-sports
  moved 2026-08-28, on their old `final/` layout, unchanged. `Basic` now keeps
  released videos only
- ~~A garbage-collection strategy~~ — `build/trim_history.py`. Nested history
  deleted outright, 3 newest kept per bucket. Freed 974 MB first run (2026-08-28)
- ~~Reproducible builds~~ — `build/build_scenes.py`. The per-scene recipe that
  produced v27 existed only in a shell history until 2026-08-28

- ~~Decide git vs LFS for the video~~ — neither; `Customers/` is gitignored.
  (`setup_demo.py` copied it in from `Basic_E2E_Testing` until 2026-09-04 —
  see P3.5 for why that stopped being possible)
- ~~Decide the tree shape~~ — flat, `paths.py`/`vtt.py` in `shared/`
- ~~Copy the 13 code files~~ — plus the 9 build tools
- ~~Copy the demo data~~ — the whole ski-demo store, 2.2 GB
- ~~Fix `fixture.py`'s repo-root walk~~ — one level here, not five
- ~~The HeyGen key~~ — env var first, then `.env.local`, gitignored before it
  was created
- ~~`CLAUDE.md` here~~ — a session in this repo starts informed
- ~~The `A#6` pipeline knowledge~~ — `PIPELINE.md`, copied whole
- ~~P1.1 the five HeyGen docs~~ — 12 documents in `docs/`, plus `Sarah/` (her
  rest-pose standards AND the idle footage holds are filled with). 35
  references rewired; nothing in `PIPELINE.md` dangles
