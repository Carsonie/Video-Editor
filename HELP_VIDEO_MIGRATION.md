# Migrating a store's `help-videos/final/` to the dev layout

**Written 2026-08-22, after migrating ski-demo.** ski-demo is done; canoe-demo,
bike-demo and alpine-sports are not. This is the runbook for those three, and
for any store added later.

**Moved to this repo 2026-08-28** with the tooling it describes, and its paths
rewritten for this repo's flatter layout — `shared/paths.py`, `build/*.py`, and
players at the top level with no `video_players/` above them.

**Two changes are bundled here** and they are separable — do the video split
first, because it is cheaper before the folders move than after:

1. **A video dimension.** A store has SIX E2E tests and more than one deserves
   its own help video. `final/` assumed one.
2. **The per-scene `dev/` layout** inside each video.

Read this before touching another store. It records the traps that were only
found by hitting them, and every one of them fails **quietly**.

---

## Why

`final/` had grown eight sibling folders — `segments/`, `scenes/`,
`sarah_clips/`, `video/`, `work/`, `segments_old/`, plus loose files — and one
scene's parts were spread across three of them. Nine tools each hardcoded a
folder name, so renaming anything meant finding all nine, and **a missed one
does not error**: a folder that no longer exists reads as "no files", which
looks like an empty store rather than a broken path.

## The layout

```
help-videos/
  raw_mp4/                     SHARED — a recording is already named by scenario
  videos/01-first-time-ordering/
  videos/02-booking-for-your-party/
  z_History/                   store-level history
```

Only `raw_mp4/` is shared. The paid HeyGen renders are per video, because the
words differ — an intro saying "how to place your first order" is wrong for a
party video. The idle clip and rest pose are already global in
`Help_Videos/HeyGen/Sarah/`.

Inside one video folder:

```
<video>/
  dev/05-dates-and-review/     segment-v6.mp4        the footage
                               narration-v1.webm     the raw HeyGen render
                               avatar-v1.webm        corner composite (editor)
                               scene.json            this scene's script node
  sandbox/05-dates-and-review/ segment.mp4           YOUR edit, overrides dev
  sandbox/_builds/                                   videos built from edits
  video/                       finished videos, v#
  sarah_clips/                 opening + closing pieces (NOT per-scene)
  work/                        boundaries.json — the cut plan
  z_History/segments|scenes|sarah_clips|video/       history by ORIGINAL folder
```

⚠ `video/` holds BOTH `script.json` and the finished `v#` videos. That reads
oddly and was kept deliberately: `paths.script()` returns `<root>/video/script.json`
and renaming it buys nothing but churn.

**`paths.py` takes the ROOT as a parameter and never hardcodes a folder name.**
That is why adding the video dimension was a folder move plus one Makefile
variable rather than a rewrite — verified by pointing it at a directory called
`anything/` and watching it resolve. Every tool takes the root; they simply get
pointed one level deeper.

`paths.py` resolves **sandbox → dev → flat**, per FILE. Not per store: a scene
moved to `dev/` resolves there even if its neighbours have not. A migration
that must be finished in one go gets abandoned halfway with nothing working.

---

## The procedure

Per store, from the repo root. `<F>` is the VIDEO root —
`Customers/<Business>/<store>/help-videos/videos/<NN-slug>/` once split, or the
old `.../help-videos/final/` before.

### Step -1. Split the store's videos first

```bash
cd "Customers/<Business>/<store>/help-videos"
mkdir -p videos && git mv final "videos/01-<viewer-facing-slug>"
```

Name folders for the VIEWER, not the test: the test is `owner-one-item`, the
video is `first-time-ordering`. The recipe stays recorded in `script.json`.
Number them — `01-`, `02-` — so a listing sorts correctly.

**Six tests does not mean six videos.** Which videos exist is a product
decision. The working assumption:

| folder | tests |
|---|---|
| `01-first-time-ordering` | 1 (test 2 probably folds in) |
| `02-booking-for-your-party` | 3 + 4 |
| `03-booking-for-someone-else` | 5 |
| `04-one-day-rental` | 6 |

`make videos` lists what a store has. `VIDEO=.` reaches an unsplit store's
`help-videos/final/`, so the tools work either way.

### 0. Check where it starts

```bash
python3 -c "import sys,os;sys.path.insert(0,'shared');import paths as P;F=os.path.abspath('<F>');sc=P.scenes_from_script(F);print(P.layout(F), len(sc),'scenes, segments:',sum(1 for n,l in sc if P.segment(F,n,l)),'narration:',sum(1 for n,l in sc if P.narration(F,n,l)),'avatar:',sum(1 for n,l in sc if P.avatar(F,n,l)))"
```

Expect `flat`, and **segments and narration counts equal to the scene count**.
If segments resolve as 0, stop — see "Two naming schemes" below.

### 1. Clear the regenerable scratch

```bash
rm -rf "<F>/work/fr"
```

`work/fr/` is the frame dump `cut_segments.py analyse` writes — 1,400–3,300
PNGs, 50–90M, rebuilt on demand. **`work/boundaries.json` and `boundaries.png`
are NOT scratch** — `analyse` writes the plan and `cut` reads it back, and
`HANDOFF.md` cites it as the authority on which recording a cut came from.

`segments_old/`, if present, is the pre-`Num_` cut. Archive, do not delete —
it is the only copy.

### 2. Dry run the move

```bash
python3 build/migrate_to_dev.py "<F>"
```

Prints every move and nothing else. Read the warnings: `⚠ scene N has no
avatar` is expected for a store with no overlay set, and harmless.

### 3. Safety copy, then apply

```bash
cd "<F>" && tar -cf "z_History/$(date +%Y%m%d-%H%M%S)_pre-dev-migration.tar" segments scenes sarah_clips/scene_overlays 2>/dev/null; cd -
python3 build/migrate_to_dev.py "<F>" --apply
```

The tar is ~100M and holds paid HeyGen renders and hand-cut segments. Keep it
until step 5 passes.

### 4. Consolidate history

```bash
cd "<F>"
for d in segments scenes sarah_clips video; do
  [ -d "$d/z_History" ] && mkdir -p "z_History/$d" && mv "$d/z_History"/* "z_History/$d/" && rmdir "$d/z_History"
done
for d in segments scenes; do [ -d "$d" ] && [ -z "$(ls -A $d)" ] && rmdir "$d"; done
```

### 5. PROVE the move changed nothing

This is the step that makes the rest safe. **Build before and after and compare.**

```bash
# BEFORE the migration, build a reference:
python3 .../assemble_video.py "<F>" --out "video/<store>_pre-migration.mp4"
# AFTER, build again and compare duration + dimensions:
python3 .../assemble_video.py "<F>" --out "video/<store>_post-migration.mp4"
```

ski-demo: `112.208s / 1152x1152` both sides, 2.6KB apart on encoder noise.
Identical duration and dimensions means the restructure changed no output.
**Only then** delete the tar.

If a full assemble is too slow, `make vtt STORE="<Business>/<store>"` is a
cheaper partial check — it resolves every segment and reads its real duration.

### 6. Scaffold the sandbox

```bash
python3 -c "import sys,os;sys.path.insert(0,'shared');import paths as P;F=os.path.abspath('<F>');r=P.sandbox_root(F);os.makedirs(os.path.join(r,'_builds'),exist_ok=True);[os.makedirs(os.path.join(r,P.slugify(l or P.scene_label(F,n),n)),exist_ok=True) for n,l in P.scenes_from_script(F)];[open(os.path.join(r,d,'.gitkeep'),'w').close() for d in os.listdir(r) if os.path.isdir(os.path.join(r,d))]"
```

Copy `sandbox/README.md` from ski-demo.

---

## The editor writes ONLY to `sandbox/` (2026-08-22)

While the editor is still being built, it reads and writes `sandbox/` and
nothing else. `dev/` is the safe copy and the editor never touches it.

- `paths.sandbox_only()` is what the editor calls — no fallback to dev. A scene
  with no sandbox copy shows as **missing** rather than silently resolving from
  dev, because an edit that appears to work on a file the editor cannot write is
  worse than an obvious gap.
- Cuts land in `<video>/sandbox/_cuts/`, wherever the source was opened from —
  including a raw recording, which is still allowed since that is where segments
  come from.
- `make sandbox-sync` refills sandbox from dev. It OVERWRITES; that is the
  point, it is the undo. Verified: truncate a sandbox segment to 2.1s, sync,
  back to 18.42s, dev unchanged throughout.

**The bookends live in sandbox too**, as `00-opening/` and `99-closing/`, each a
`segment.mp4` + `avatar.webm` pair — a bookend already IS two tracks, Sarah's
alpha front over a background, so it reviews like any scene. Build them with:

```bash
python3 build/export_bookends.py "<F>"
```

The editor lists any NUMBERED sandbox folder that is not a script scene, so
00 and 99 appear at the ends of the list without touching script.json — which
is right, because a bookend is not a scene and never will be.

Every row in that list has a **checkbox**, and ticking several opens them on one
timeline (read-only — cutting stays per-scene). Nothing to set up per store: it
reads the same sandbox folders, and each scene reuses the extraction it already
has. It is how a join gets judged, and the two a newly migrated store has never
had checked are the bookend ones — 00 → first scene, and last scene → 99.

⚠ **A store need not keep 99 in its sandbox.** ski-demo's closing was taken
out on 2026-08-26 and now lives in `Sarah/closing/` in the Video-Editor repo,
because it is the same for every video and belongs to the library, not to one
of them. Its README says how to put it back. A missing 99 is a choice, not a
migration that stopped half way.

**Setting up a newly migrated store therefore has one more step:** copy
`dev/*/segment-v*.mp4` → `sandbox/*/segment.mp4` (and the same for narration and
avatar), which `make sandbox-sync` does.

⚠ That copy gives every file a new mtime, so the editor's frame cache is
invalidated and the first open of each clip re-extracts. Expect it to be slow
once, then normal.

**This is temporary.** Once the editor is trusted, the intention is to drop the
sandbox layer and edit `dev/` directly, with git as the safety net. Until then a
tool under active development is not the only thing between a bad edit and a
paid HeyGen render — it has already shipped one bug that showed stale frames
after a delete.

## Two naming schemes — the thing that will bite

ski-demo uses `Num_5-v6-segment.mp4`, written by the MP4 Splitter's cut. **The
other three still use the ORIGINAL `segment-04-search.mp4`** — unversioned,
and their `script.json` has **no `label` field at all**.

Both are handled, as of 2026-08-22:

- `paths.segment()` falls back to `script.json`'s own `segment` field. The
  script NAMES the file, so it is trusted over any pattern of ours.
- `paths.scene_label()` derives a folder name from the legacy stem —
  `segment-04-search.mp4` → `search` → `04-search/`. Numbers still do all the
  matching; the label is only readability.
- `migrate_to_dev.py` stamps a legacy segment **v1**. It is the first tracked
  version of that footage, and any other number would imply a history the
  files do not have.

Verified: canoe-demo 10/10, bike-demo 11/11, alpine-sports 10/10 resolve.

## Scene folders are matched by NUMBER, never by name

`scene_dir()` matches `^NN(-|$)`. The label is a convenience for reading a
directory listing. Matching on it would break the moment a scene is renamed in
`script.json` — which has happened twice already.

So renaming `05-dates-and-review/` to `05-anything` is safe. Renaming it to
`5-dates` is **not** — the zero padding is what keeps a listing in scene order.

## gitignore: git does not descend into an excluded directory

This trap cost real time twice.

`Customers/*/*/help-videos/**/work/` silently ignored every `!` re-include
inside it, which is why `boundaries.json` — a file the docs call authoritative
— was never tracked. The fix is to exclude the **contents**:

```
Customers/*/*/help-videos/**/work/*
!Customers/*/*/help-videos/**/work/boundaries.json
```

And for a skeleton that must survive a clone, re-include the **directories**
first or the file exceptions are dead:

```
Customers/*/*/help-videos/**/sandbox/**
!Customers/*/*/help-videos/**/sandbox/**/
!Customers/*/*/help-videos/**/sandbox/README.md
!Customers/*/*/help-videos/**/sandbox/**/.gitkeep
```

Always verify with `git check-ignore -v <path>`, never by reading the rules.

**The rule in THIS repo is different, and simpler** (2026-08-28). Here
`Customers/**` is excluded and only text under a store's `help-videos/` is
re-included — `.json`, `.md`, `.txt`, `.gitkeep`, plus `work/boundaries.png`:

```
Customers/**
!Customers/
!Customers/**/
!Customers/*/*/help-videos/**/*.json
```

Same trap, third time: the directory re-includes come first and are their own
lines. And it bit in the DANGEROUS direction while being written — `Customers/*`
with `!Customers/**/` staged **3.5 GB** of video before `git status` was read.
Check what a rule stages, not only what it ignores.

## Files that look like leftovers and are not

`TRACK_front_full.webm` and `TRACK_rear_full.mp4` sit loose in `final/` and
look abandoned. `assemble_video.py:728` **writes both on every build** and
consumes them immediately to make the final overlay. They are live
intermediates. I was one command away from deleting them.

Likewise `sarah_clips/` is not per-scene — the opening, the closing, the
morphs and the idle clip are store-level. `migrate_to_dev.py` leaves it alone.

## What still has no version, and why that matters

Narration clips (`sarah-scene-NN-alpha.webm`) were **overwritten by name** on
every render, recording nothing about which script they came from. Three things
must agree frame for frame — segment, avatar, script — and only segments were
versioned, so they could drift with nothing on screen to show it.

After migration they are `narration-vN.webm`. A re-render should write **v2**,
not overwrite v1. `make_scene_overlays.py` already versions its sets and stamps
the SHA of every LINE it was built from — not the file's hash, because a
changed line under an unchanged filename is the exact failure worth catching.

---

## Current state

| store | scenes | layout | segment naming | avatar set |
|---|---|---|---|---|
| ski-demo | 11 | **dev**, split into `videos/01-first-time-ordering/` | `Num_N-vV` → `segment-v6` | v1, and BUILT |
| canoe-demo | 10 | **dev**, split into `videos/01-first-time-ordering/` | legacy `segment-NN-name` → `segment-v1` | v1, and BUILT — RELEASED as v2 |
| bike-demo | 11 | **dev**, split into `videos/01-first-time-ordering/` | legacy `segment-NN-name` → `segment-v1` | in `sandbox/` only, and BUILT (v2, scenes only) |
| alpine-sports | 10 | **dev**, split into `videos/01-first-time-ordering/` | legacy `segment-NN-name` → `segment-v1` | v1, and BUILT — RELEASED as v2 |

ski-demo went from 12 scenes to 11 on 2026-08-26: `11-logout-menu` and
`12-signed-out` were always one action, and `99-closing` moved to `Sarah/closing/`
because it is the same in every video. **A store need not keep a 99.**

All four stores live in THIS repo as of 2026-08-28. The three flat ones came
across from `Basic_E2E_Testing` exactly as they were — the move did not migrate
them. **All four are now migrated onto the `dev` layout as of 2026-08-28** —
ski-demo first (2026-08-22), bike-demo, then canoe-demo and alpine-sports, both
the same day via `migrate_to_dev.py --apply` followed by the same manual steps
bike-demo got: `final/` renamed to `videos/01-first-time-ordering/`, the five
`sarah-*.webm` files moved into `sarah_clips/`, and `dev/` copied by hand into a
new `sandbox/`. No store remains flat.

`make overlays` reads its narration through `paths.narration()` as of
2026-08-22 — sandbox, then dev, then flat. Before that it read
`<final>/scenes/sarah-scene-NN-alpha.webm` by hardcoded name, so on a migrated
store it found nothing and reported every scene missing. A flat store still
resolves, which is why the bug hid: it only bit AFTER a migration.

**No store is left without per-scene avatar overlays as of 2026-08-28.**
bike-demo, canoe-demo and alpine-sports were all migrated without first
running `make overlays STORE="<Business>/<store>"`, so each one's `dev/`
folder started with no `avatar-v1.webm`. The fix used for all three: build
`avatar.webm` per scene with `morph_avatar_corner.py --src ... --outdir ...
--canvas 1152 --corner 320` (then composite it onto a full 1152×1152 canvas
— see the `sae-video-building` skill's step 6 for the exact command and the
shape-mismatch trap to avoid), and copy the result into
`dev/<label>/avatar-v1.webm` right after, so `sandbox/` isn't the only copy
of the work.

**canoe-demo and alpine-sports both went through this on 2026-08-28.** Each
got `avatar.webm` built in `sandbox/` for all 10 scenes, copied into
`dev/<label>/avatar-v1.webm` so both folders agree, and a full video
assembled with `assemble_video.py` and released as v2 — canoe-demo 70.15s
against v1's 70.0s, alpine-sports 69.88s against v1's 69.73s, both
1152×1152, matching quality. Each store's v1 was archived, not deleted,
by `release_video.py` itself.

**alpine-sports' `assemble_video.py` build needed `--skip-qualify`, and by a
wide margin.** Two scenes (payment, order-complete) have footage far shorter
than their narration — 3.9s of footage against a 5.5s line, and 2.6s against
5.3s. `qualify_avatar.py` refuses anything over a 30-frame (~1.2s) gap
between footage and the avatar overlay; these were 38 and 68 frames, more
than double canoe-demo's worst case (29 frames, which passed). Checked
against `dev/`'s original, untouched `segment-v1.mp4` before overriding —
the gap predates this migration and isn't something the rebuild introduced,
so it was safe to proceed. The build holds the last frame for the gap, same
mechanism as any smaller hold, just for longer (up to ~2.7s on the worst
scene) — worth a look in the finished video before calling a store done,
since a hold that long is a real judgment call about whether it still reads
as first-time-ordering quality, not just a mechanical pass/fail.

**bike-demo did not go through `make overlays`.** It was migrated first
(2026-08-28, via `migrate_to_dev.py` — also fixed a `sys.path` bug in that
script pointing at `build/` instead of `shared/`), then its avatar clips were
built by hand straight into `sandbox/*/avatar.webm`, bypassing both `make
overlays` and `migrate_to_dev.py`'s own avatar-file handling. Net effect:
`dev/` here has segment + narration + `scene.json` only, no `avatar-v1.webm`
— the avatar only exists in `sandbox/`, which is fine per `sandbox/README.md`
(sandbox overrides dev) but means **`dev/` alone cannot rebuild this store**;
losing `sandbox/` loses the avatar work. `build_scenes.py` passes all 11
scenes and `--join 2` was built (scenes only, no opening/bridge yet).

⚠ Their footage is also **30fps and un-held** — recorded before the 2026-08-19
switch to 25fps and before the per-step holds. Migrating the folders does not
fix that. A store that needs a good video needs a re-record first; migrating is
about tidiness, not quality.

---

## Keeping this file true

A `pre-commit` hook in `.githooks/` prints a reminder when a commit touches the
surface below without staging this file. It does not block — a hook that blocks
gets disabled, and then nothing reminds anyone.

⚠ **`core.hooksPath` is LOCAL git config and is NOT cloned.** A fresh clone gets
the hook file and never runs it. Enable it once per checkout:

```bash
git config core.hooksPath .githooks
```

**On every commit that touches any of the following, re-read this file and
update it in the same commit:**

- `shared/paths.py`
- `migrate_to_dev.py`, `make_scene_overlays.py`, `assemble_video.py`
- `shared/serve.py`'s `api_siblings`
- the `Makefile`'s `scenes` / `overlays` targets
- `.gitignore`'s `help-videos` rules
- any store's `final/` or `videos/<slug>/` folder structure

A runbook that lags the code is worse than none: it will be followed, and it
will be wrong. The **Current state** table above is the part most likely to go
stale — update it the moment a store migrates.
