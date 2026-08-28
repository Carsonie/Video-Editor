# ToDo

Open work in this repo. Ranked `P1`–`P4`, most severe first, same convention as
`Basic_E2E_Testing`'s own list.

`SVM.md` is the plan and the end state. This is what is left to get there.

---

## P1 — the playbook has holes in it

### P1.2 The demo checklist has never been walked by hand here

`SVM.md` §3 lists what "working" means. The endpoints all pass (106 checks) and
both pages load, but **no one has clicked the controls in this repo**: mark,
cut, hand off, join, split, save, edit a line. A dead page answers every
endpoint perfectly — that already happened once.

---

## P2 — the transfers, which is what makes this repo independent

### P2.1 `Customers/` is a hardcoded root

`safe_join()` pins every path under a folder literally named `Customers/`, and
`find_repo_root()` walks up looking for one. It works, but it means this repo's
data folder has to carry `Basic_E2E_Testing`'s name for it. Make the root
configurable — an argument or an env var — with `Customers/` the default.

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

### P3.3 `layers.sh` — used, or an orphan?

It came across with the players and nothing imports it. Either it earns its
place or it goes.

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

- ~~Decide git vs LFS for the video~~ — neither; `setup_demo.py` copies it and
  `Customers/` is gitignored
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
