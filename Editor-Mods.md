# Editor-Mods.md — changes made to the editor's own code, for review/revert

Each entry: what changed, why, exactly where, and how to put it back.

---

## 2026-08-29 — "Save All" now writes every scene unconditionally

**Requested by Carson.** He deleted `sandbox/` for ski-demo's
`01-first-time-ordering` (see below) and wanted "Save All" changed so that
reloading it from the editor writes down every scene exactly as configured
on the timeline right now — not just scenes the page's internal dirty
tracker happens to have flagged as edited.

**Why the old behavior could bite:** "Save All" only ever wrote scenes with
`pendingOf(i)` — a dirty flag tracked in the page's own JS memory. That
tracker is reset by a page reload (see the existing comment on `HIST` in
`player.py`, just above `pendingOf`), so a scene that's actually different
from what's on disk can still report "no unsaved edits" if the tracker
never saw it happen in *this* page load. "Save All" then does nothing for
that scene, which reads as "nothing to save" rather than "the tracker
doesn't know."

### What changed

**File:** `segment_avatar_editor/player.py`

1. `saveAllScenes()` now takes a `force` argument.
   - `force=false` (**Save Scenes**, the `cutBtn`): unchanged — only scenes
     with tracked pending edits, exactly as before.
   - `force=true` (**Save All**, the `saveBtn`): every scene on the
     timeline, every layer that exists (`base`/`overlay`) and isn't locked
     — regardless of the dirty tracker's state.
2. A **locked track is still respected** even in force mode. The lock tick
   is a deliberate "do not touch this one," and force does not override it
   — it only overrides the *dirty* check, not an explicit lock.
3. Updated the confirm-dialog text and the `saveBtn` tooltip to say plainly
   that Save All now writes everything as configured, whether or not it was
   marked edited.
4. Restarted the running editor server (`shared/serve.py --port 8842`) so
   it serves the new code — a running server otherwise keeps answering
   with the page it started with.

### Verified

- `python3 -c "import ast; ast.parse(...)"` — Python still parses.
- `python3 tests/test_editor.py` — **142/142 checks pass**, including the
  step that actually runs `node --check` on the generated JavaScript
  (`Segment and Avatar Editor (timeline): its JavaScript parses`). This is
  the project's own stated hard rule for any change here — checked, not
  assumed.

### To revert

Change `saveAllScenes(force)` back to `saveAllScenes()` with no parameter,
restore `withWork` to the single `pendingOf`-only computation, restore the
original confirm text and `saveBtn` tooltip, and change both button wiring
lines back to `$('cutBtn').onclick = saveAllScenes;` /
`$('saveBtn').onclick = saveAllScenes;`. Restart the server afterward.

---

## 2026-08-29 — Save All: removed the lock skip, force-saves the script too

**Requested by Carson**, right after the first fix above. He still hit
`No scene has unsaved edits` on Save All. Cause: force mode still skipped
any track that was locked (`!isLocked(...)`), and everything on his
timeline was locked — so the write set came out empty and it fell through
to the same dead-end message the whole fix was meant to remove. His
instruction: *"Remove this so it becomes a forced save of all scenes and
narrative script."*

### What changed

**File:** `segment_avatar_editor/player.py`

1. **Locks no longer stop Save All.** The `!isLocked(s.n, w)` filter is
   gone from the force branch — every base/overlay layer that exists gets
   written, locked or not. Save Scenes (`cutBtn`, force=false) is
   untouched — it still only writes tracked pending edits and still
   respects the unticked-track message.
2. **The "nothing to save" dead-end can no longer fire in force mode** as
   long as anything is on the timeline. It now only fires if `SEQ` itself
   is empty. (Save Scenes keeps its old messages — "unticked track" /
   "no unsaved edits" / renumber-note hint — those still apply to it.)
3. **Save All now also force-writes every scene's narrative line** to
   `script.json` via `/api/line`, in the same click, using whatever text
   is currently sitting in that scene's EVTT box (`vLine[n]`) — not gated
   by `vDirty`, which is the same "only what a tracker happened to see"
   gate that caused the video-layer bug in the first place.
4. Confirm-dialog text and the `saveBtn` tooltip updated: now say plainly
   that locked tracks are included and that script lines are written too.
5. Status message after a run now also reports `Lines saved for N of M
   scene(s)`, plus any line-save failures separately from video-save
   failures.
6. Restarted the running editor server (PID 26445 → 27090) so it serves
   this code.

### Verified

- `python3 -c "import ast; ast.parse(...)"` — parses.
- `python3 tests/test_editor.py` — **142/142 checks pass**, including
  `Segment and Avatar Editor (timeline): its JavaScript parses`.

### To revert

Put the `&& !isLocked(s.n, w)` condition back into the force branch's
layer filter, restore the single "nothing to write" early-return (checked
for both force and non-force, as it was in the first fix above), and
delete the `scriptTargets` block and the `/api/line` loop that runs after
the video-save loop. Restore the tooltip/confirm text from the prior
entry. Restart the server afterward.

---

## 2026-08-29 — Save All archives the old sandbox into `1000_archive/` first

**Requested by Carson.** He created `sandbox/1000_archive/` himself and
asked: on every Save All click, snapshot whatever is currently in
`sandbox/` into a new dated/numbered folder inside `1000_archive/` FIRST,
then land the current editor state (video + narrative) into sandbox —
so `1000_archive/` keeps one full copy of every generation Save All ever
replaced.

**One technical adjustment, flagged here because it changes what was
literally asked for:** Carson asked for the old sandbox to be *moved*
out, then the new data written in. That can't work as stated — `/api/save`
rebuilds each scene by reading the exact file sitting in `sandbox/`
(`meta.json`'s `"source"` — see `build_frames()` in `shared/frames.py`)
and refuses if that file is gone. Moving it away first would make every
save in the same click fail with `source no longer exists`. Copying
instead gets the identical end state Carson asked for — `1000_archive/`
ends up holding exactly the old generation, `sandbox/` ends up holding
exactly the new one — without breaking the mechanism the new data has to
come from.

### What changed

**Files:** `shared/paths.py`, `shared/serve.py`, `segment_avatar_editor/player.py`

1. **`shared/paths.py`** — `archive_name`, `archive_name_v`, and
   `archive_contents` all take a new optional `archive_dir=` parameter
   (defaults to the existing `z_History`, so the three existing callers —
   Backup Scenes, the MP4 Splitter handoff, `assemble_video.py`'s own
   build archiving — are byte-for-byte unchanged). `archive_contents`
   also now always skips BOTH `z_History` and whatever `archive_dir` was
   passed, so an archive folder can never sweep itself or the other
   scheme up into its own snapshot.
2. **`shared/serve.py`** — new endpoint `POST /api/save-archive`
   (`api_save_archive`, right after `api_archive`). Payload: `{root}` —
   same video-folder-relative path every other endpoint here uses.
   Copies (never moves) everything currently in that video's `sandbox/`
   into `sandbox/1000_archive/<Add-V name>/` — Add-V naming
   (`26-8-29_v1`, `_v2`, ... resetting each day; same scheme
   `Backup Scenes`'s `naming: "add-v"` already uses, just counted inside
   `1000_archive/` instead of `z_History/`). Returns `{archived_to}`, or
   `{empty: true}` if the sandbox had nothing in it to archive.
3. **`segment_avatar_editor/player.py`**, `saveAllScenes(force)` — when
   `force===true` (Save All only; Save Scenes is unaffected): right after
   the confirm dialog and before any video or line save, calls
   `/api/save-archive`. On error, Save All stops right there and reports
   the archive failure — none of the writes below run, so a failed
   archive can never look like a completed save. On success the run
   continues exactly as before. Confirm-dialog text, the `saveBtn`
   tooltip, and the final status line all updated to say the archive step
   happens and where it landed.

### Verified

- `python3 -c "import ast; ast.parse(...)"` on all three files — parses.
- `python3 tests/test_editor.py` — **142/142 checks still pass**,
  including Step 34 (`/api/archive`) — confirms the `archive_dir`
  parameter is fully backward compatible for every existing caller.
- Manual smoke test of the new endpoint against the live server (not yet
  covered by `test_editor.py`): `POST /api/save-archive` with ski-demo's
  `01-first-time-ordering` root. Result: `sandbox/` left untouched (still
  had all 11 scene folders + `script.json`), and
  `sandbox/1000_archive/26-8-29_v1/` came back holding an exact mirror of
  the same 11 folders + `script.json`. **This used up `v1` for today** —
  the next real Save All click produces `v2`, not `v1`.
- Restarted the running editor server (PID 27090 → 28368).

### To revert

Delete the `if (force) { ... /api/save-archive ... }` block from
`saveAllScenes(force)` (right after `stop();`), delete the
`archivedTo` line from the final status message, restore the
confirm-dialog text and `saveBtn` tooltip from the prior entry, remove
the `api_save_archive` method and its two dispatch/label lines from
`shared/serve.py`, and drop the `archive_dir` parameter from the three
functions in `shared/paths.py` (or just stop passing it — the default
preserves the old behavior exactly). Restart the server afterward.
`sandbox/1000_archive/` itself is just data — leave it; it's a real
backup, not something this revert needs to touch.

---

## 2026-08-29 — `/api/save` no longer crashes on a bad-pts source

**Found by Carson**, running the real Save All above: scene 4's `base`
(segment) came back `⚠ scene 4 base: TypeError: Failed to fetch` and the
scene was left out of the saved list.

**Not a bug in anything added today** — this was already possible in
`/api/save`, just never hit before because nothing had forced every scene
through it in one click until Save All did.

**What actually happened:** `/api/save` writes the new file to
`sandbox/…/segment.mp4` FIRST — that part succeeded (confirmed: the file
on disk is dated to the run, 248 frames, matches spec). It then
re-extracts frames into the live-preview cache, and THAT step called
ffmpeg on a source with one bad-timestamp frame
(`Invalid pts (186) <= last (186)`, non-monotonic dts). ffmpeg failed,
`build_frames()` raised, and nothing in `api_save` caught it — so the
request died mid-handler with no HTTP response at all. A dropped
connection is exactly what a browser reports as `TypeError: Failed to
fetch`, so a scene that had, in fact, already saved read as failed.

### What changed

**File:** `shared/serve.py`, `api_save()`

Wrapped the frame re-extraction step (`build_mod.build_frames(...)`
through the frame-count verification) in `try`/`except RuntimeError`. On
success, unchanged. On failure, the endpoint still returns 200 with the
file-save facts (`path`, `archived_to`, `duration_s`) and a `warning`
saying the live preview cache couldn't refresh and to reload that scene —
it does NOT report the save as failed, because it didn't fail. The
existing `saveAllScenes` client code already treats `d.warning` as
non-fatal (pushes to a warnings list, still marks the scene saved), so no
JS changes were needed for this half.

### Verified

- `python3 -c "import ast; ast.parse(...)"` — parses.
- `python3 tests/test_editor.py` — **142/142 still pass**.
- Confirmed on disk: scene 4's `segment.mp4` (dated to the run that hit
  this) is 248 frames — correct — so nothing here was ever actually lost.
- Restarted the server (PID 28368 → 29514).

### Not yet done

The ROOT ffmpeg issue — scene 4's source has one frame with a bad
timestamp — is still there; this fix stops it from crashing the request,
it doesn't clean the source. If scene 4 keeps throwing this warning on
every future save, that's worth a look on its own, separately.

### To revert

Un-indent the frame-re-extraction block back out of the `try`, delete the
`except RuntimeError` branch, and restore `wrote`/`warning`/`new_meta`
being computed unconditionally. Restart the server afterward.

---

## 2026-08-29 — `sandbox/` emptied for ski-demo's 01-first-time-ordering

**Requested by Carson**, as the first step before using the fixed Save All
to reload it fresh from the editor. Deleted:

```
Customers/Rentify Demos Corp/ski-demo/help-videos/videos/01-first-time-ordering/sandbox/*
```

All 11 scene folders, `z_History/`, `_builds/`, and `README.md` — the whole
folder's contents, not the folder itself. Nothing was backed up as part of
this specific delete (a full copy of the pre-delete state already existed
separately, in `sandbox_editor_bkup/`, made earlier the same session).

**To revert:** restore from `sandbox_editor_bkup/` (copy its scene folders
back into `sandbox/`), or from whatever the editor's next "Save All" writes
once reloaded — whichever is the state actually wanted.

**Reverted 2026-08-29, 10:xx.** Carson reloaded the editor before ever
clicking Save All, which wiped the in-memory timeline and re-loaded from
`sandbox/` — empty, since it hadn't been saved into yet. Restored: the 11
scene folders (`segment.mp4`/`narration.webm`/`avatar.webm`) plus
`script.json` copied from `sandbox_editor_bkup/` back into `sandbox/`.
`browser_vtt_snapshot_2026-08-29.json` was left in the backup folder only
— it's a snapshot artifact, not part of the sandbox's normal contents.

---

## 2026-08-29 — Row 4: five whole-session buttons, replacing Save Scenes/Save All

**Requested by Carson**, as a full revision of everything above. Instead of
two buttons doing an increasingly complicated job each, a new row (row 4,
between the frame-edit row and the report row) holds five buttons, each
doing exactly one thing:

| Button | Reach | Confirms |
|---|---|---|
| **Save Timeline** | Scenes with tracked video edits only | Yes |
| **Save all** | Those, plus scenes with a tracked narrative edit | Yes |
| **Backup Scenes** | Archives the whole sandbox generation, then force-writes every scene + every line, unconditionally; clears a renumber note if one is pending | Yes |
| **Clear All** | Empties this browser tab's session — no disk writes | Yes |
| **Load** | Opens a different video: pick a store, then which video, then loads fresh | Yes |

This retires today's earlier `force=true` Save All entirely — that job
(archive-then-write-everything) now belongs to Backup Scenes, per Carson's
own call when asked. `Backup Scenes` also absorbed its own former "copy
the sandbox to z_History" job the same way: one button, one full
description, not a name doing two things.

### What changed

**Files:** `shared/paths.py`, `shared/serve.py`, `segment_avatar_editor/player.py`

**`shared/paths.py`**
- `archive_name`, `archive_name_v`, `archive_contents` all take a new
  optional `archive_dir=` (default `z_History`, so the three existing
  callers — Backup Scenes' old job, the MP4 Splitter handoff,
  `assemble_video.py`'s own build archiving — are unchanged). `archive_contents`
  now skips both `z_History` and whatever `archive_dir` was passed, so an
  archive can never sweep itself up.

**`shared/serve.py`**
- `api_save_archive` (`/api/save-archive`, built earlier today) gained
  `dry` support, mirroring `api_archive`'s own dry-run shape — the button
  can now show the exact destination before asking to confirm.
- `api_save_archive` also now copies `video/script.json` into the archive
  alongside the scene folders. It didn't before — the sandbox sweep only
  reaches `sandbox/`'s own contents, and the narrative script lives at
  `video/script.json`, a SIBLING of sandbox/, not inside it. Carson asked
  for "the current scenes and the narration script" archived together;
  this was the gap between that ask and what the endpoint actually did.
  (The script's own per-edit history is untouched, still at
  `z_History/line-edits/` under the video folder root — this is an
  additional whole-generation copy, not a replacement.)
- New endpoint `GET /api/stores` (`api_stores`) for Load: walks
  `Customers/<Business>/<store>/help-videos/videos/*/`, and for every video
  folder with a `video/script.json`, returns its scene numbers and whether
  `sandbox/` exists yet. Two levels under Customers/ is assumed to be
  Business/store, same assumption `/api/list`'s own store-detection makes.

**`segment_avatar_editor/player.py`** (timeline page only — the layered
pair-editor page's own `cutBtn`/`saveBtn`, an unrelated pair of buttons in
an unrelated page, were not touched)
- HTML: `backupBtn` moved out of the scene-list panel; `cutBtn`/`saveBtn`
  removed from row 3. New row 4 holds `saveTimelineBtn`, `saveAllBtn`,
  `backupBtn`, `clearAllBtn`, `loadBtn`. New `#loadModal` (a second overlay
  beside the existing name-input `#modal` — different enough in shape,
  a picked list rather than a form, to not be worth forcing into one).
- `saveAllScenes(force)` replaced by `saveScenes(includeNarrative)` — the
  force branch and its whole unconditional/lock-bypass/archive path are
  gone from this function entirely; it is dirty-only now, full stop.
- `backupScenes()` rewritten: dry-runs and calls `/api/save-archive`
  (was `/api/archive`), then runs what used to be `saveAllScenes(true)`'s
  force-write loop for video AND narrative, then keeps its old
  renumber-note-clearing job.
- New `clearAllScenes()`: resets `SEQ`, `starts`, `total`, `which`, `SOLO`,
  `vttCentred`, `MARKS`, `HIST`, `vLine`, `LOCKED`, `vDirty`, `ON`,
  `RENUMBERED`, `VTT`, and repaints the scene list/viewer/VTT panel/report
  row directly rather than through `paint()`/`show()`/`renderScenes()` —
  those all assume at least one scene exists, and auditing every one of
  them for a zero-scene case was a bigger job than this button needed.
  Touches nothing on disk.
- New `openLoadModal()` + `renderStoreList()`/`renderVideoList()`/
  `confirmLoad()`: fetches `/api/stores` fresh on every open (not cached —
  a stale list missing a just-built video is the failure worth avoiding),
  two-step picker, same `Escape`/click-outside/Cancel pattern the existing
  name-input modal already uses.

### A real bug found and fixed along the way

Ski-demo scene 4's `segment.mp4` had one frame (the boundary at frame 186)
with a corrupted, non-monotonic timestamp — not something this session
introduced, but something Save All's unconditional reach was the first
thing to actually touch every scene and surface. It broke TWO different
things: `/api/save`'s post-write cache refresh (fixed earlier today, see
the entry above), and — worse — `/api/open-seq-go` itself, which extracts
every scene's frames before the editor can even open, so this one bad
frame blocked the WHOLE timeline from loading at all once it landed.

Fixed by re-encoding just that file: decoded every frame in file order
(`-fflags +genpts -vsync 0`), re-stamped clean, evenly-spaced timestamps
(`setpts=N/(25*TB)`), re-encoded with this project's own `ENCODE` settings
(`libx264 -crf 18 -c:a aac -pix_fmt yuv420p`). Verified before swapping in:
same 248 frames (none dropped — a naive `-vsync cfr` conform tried first
DID drop 60 frames and was discarded), same 9.92s/25fps as every prior
record of this scene, audio duration unchanged, and SSIM ≈0.9997 frame-for-
frame against the original — same picture, only the timestamps fixed. The
old file is archived at `sandbox/04-catalogue-search/z_History/<timestamp>/segment.mp4`,
same convention as every other overwrite here.

Also removed a stray `sandbox/script.json` from earlier today's backup
restore — the editor never reads that path (`video/script.json` is the
real one, confirmed by reading `api_line`/`api_vtt`), so it was inert
clutter, not data.

### Verified

- `python3 -c "import ast; ast.parse(...)"` on all three files — parses.
- `python3 tests/test_editor.py` — **142/142 checks pass**, including both
  players' JavaScript-parses steps. `/api/save-archive` and `/api/stores`
  are new and not yet covered by this suite — exercised by hand instead
  (below), since covering them properly would mean extending the test
  script itself, which wasn't asked for here.
- Live in the browser, against the running server: opened the real
  timeline (ski-demo, all 11 scenes — this is what proved the scene 4 fix
  actually cleared the block). Confirmed by screenshot/DOM inspection:
  - Row 4 renders with all five buttons, correctly positioned.
  - **Load**: store list showed all 4 real stores; picked ski-demo, saw
    its one video with 11 scenes; Back returned to the store list; picked
    canoe-demo instead and it genuinely navigated there — different
    avatar, different scene count (10), confirmed via screenshot and the
    tab's own title. canoe-demo's `sandbox/` was confirmed untouched
    afterward.
  - **Clear All**: with `confirm` forced to `true` (this browser pane
    suppresses real dialogs), the scene list, viewer, VTT panel and report
    row all emptied and `rebuildBtn` correctly read "Tick at least one
    scene" — read directly off the DOM after the click, not assumed.
  - **Save Timeline** / **Save all**: with nothing dirty, both correctly
    reported "No scene has unsaved edits." and made no request.
  - **Backup Scenes**: confirm dialog text read correctly off the
    suppressed-dialog console log — right scene count, right destination
    path (`.../canoe-demo/.../sandbox/1000_archive/...`) — and declining it
    left canoe-demo's `sandbox/` with no `1000_archive/` folder at all,
    confirming nothing writes before the confirm is accepted.
- Server restarted (PID 29514 → 31008) partway through, before the browser
  testing above, so everything screenshotted above is the code as it now
  stands.

### To revert

This is a large, multi-part change — reverting it cleanly means putting
back the two-button version from the entries above (`cutBtn`/`saveBtn` in
row 3, `backupBtn` in the scene-list panel, `saveAllScenes(force)`), not
patching row 4 down to fewer buttons. If only part of this is unwanted,
say which button and it can come out on its own — the five are independent
of each other now, nothing here depends on another one of the five
existing.

The scene 4 timestamp fix and the stray `sandbox/script.json` removal are
independent of the button work and don't need reverting alongside it.

---

## 2026-08-29 — `/api/save-archive` and `/api/stores` added to `tests/test_editor.py`

**Requested by Carson**, after asking directly whether the row-4 work above
had test coverage. It didn't — those two endpoints were only exercised by
hand (screenshots and `javascript_exec`, logged in the entry above). The
suite's own endpoint-count check (`endpoint_counts()`, `tests/test_editor.py:74`)
was quietly reporting 29/31 the whole time; nobody was watching that number.

**What "click events" can and can't mean here**, since that's the exact
word Carson used: `test_editor.py` drives HTTP against the server — it has
never simulated an actual button click for ANY control, old or new. What
IS new-per-button covered now is the ENDPOINT each button calls, same as
every other button in this suite. A true click-driven UI test would need
browser automation this project doesn't have; said so at the time rather
than silently answering a narrower question than the one asked.

### What changed

**File:** `tests/test_editor.py`

- **`s_save_archive()`** (new, Step 35): dry run reports `would_archive`
  including `"script.json (video/)"` and a destination under
  `1000_archive/`; a real call confirms sandbox is COPIED not moved, the
  snapshot holds the same scene folders PLUS `script.json` copied in
  alongside them, a same-day second call is `_v2` not a clash, and a path
  outside `Customers/` is refused. Modeled directly on the existing
  `s_archive()` above it — same shape, different endpoint.
- **`s_stores()`** (new, Step 36): confirms the endpoint's list shape, and
  specifically that the test fixture (`Customers/_Editor_Test`, which sits
  ONE level under `Customers/` with no `Business/store/help-videos/videos`
  nesting) is correctly excluded — not just incidentally absent, actually
  checked. Runs against the REAL `Customers/` tree rather than a built
  fixture, because that tree IS what this endpoint reads; structural
  checks (business/store/videos/scenes/root/has_sandbox all present and
  correctly typed) are asserted against whatever real store comes back
  first, so the test doesn't depend on which stores happen to exist.
- Both registered in `FUNCTIONS`, right after `s_archive` — same
  neighborhood as the endpoint they're closest to in behavior.

### A test bug caught and fixed before this landed

First run failed: `s_archive()` (the existing step, run just before)
leaves a `sandbox/z_History/` folder behind from ITS OWN archive test, and
my new step's "sandbox still has its scene folders" check didn't exclude
that folder name — so the check compared the real sandbox listing
(scene folders + a leftover `z_History/`) against the 1000_archive
snapshot (scene folders only, since `archive_contents` already correctly
skips both archive-scheme names) and failed on a folder that was never
actually part of either scheme's own promise. Fixed by excluding
`z_History` from that comparison too — the archived-generation snapshot
was never wrong; the test's idea of "what counts as a scene folder" was.

### Verified

- `python3 -c "import ast; ast.parse(...)"` — parses.
- `python3 tests/test_editor.py` — **161/161 checks pass, 31/31 endpoints
  now exercised** (was 29/31 before this). Both new steps' full output
  checked by eye, not just the pass/fail count — every value shown (dry-run
  destination path, snapshot contents, real business/store names picked up
  from disk) is what it should be.
- Log written to `tests/log_reports/` same as every other run, same
  naming (`editor_HH_MM_SS.log`) — nothing about the logging mechanism
  itself needed changing; the gap was coverage, not visibility.

### To revert

Remove `s_save_archive` and `s_stores` from `FUNCTIONS`, delete both
function definitions. The suite will report 29/31 endpoints again — which
is the honest number for whatever version of this file no longer tests
them.

---

## 2026-08-29 — `script.json` moved: `video/` → `sandbox/`

**Requested by Carson**: "I want to keep all the data together in one
folder... I want the editor to load and save the json file to the
sandbox folder." This is the second such move — `script.json` went from
a bare `<final>/script.json` to `<final>/video/script.json` on
2026-08-20; this moves it again, to `<final>/sandbox/script.json`,
following the exact same pattern the first move already established.

### What changed

**Files:** `shared/paths.py`, `shared/serve.py`, `shared/vtt.py`,
`build/assemble_video.py`, `build/cut_segments.py`,
`build/render_narration.py`, `build/make_scene_overlays.py`,
`build/preview_narration.py`, `build/migrate_to_dev.py`,
`tests/fixture.py`, `tests/test_editor.py`, plus the 4 real stores' data.

1. **`PTH.script(final)`** (`shared/paths.py`) — now a 3-tier resolver:
   `sandbox/script.json` (new) → `video/script.json` (2026-08-20 through
   today) → bare `script.json` (original). Whichever exists is returned;
   nothing is ever WRITTEN to an old tier — a store starts saving to
   sandbox/ the moment its file is physically there, same as the
   2026-08-20 move worked. This one function is what every server
   endpoint (`/api/line`, `/api/vtt`, `/api/join`, `/api/split`, etc.)
   and several build tools (`build_scenes.py`, `onepass_narration.py`,
   `qualify_avatar.py`, `preview_narration.py`) already read through, so
   fixing it here fixed all of them at once.
2. **Four standalone build tools had their OWN duplicate copy** of the
   same resolver, from before `paths.py` existed as the shared version:
   `shared/vtt.py`, `build/assemble_video.py`, `build/cut_segments.py`,
   `build/render_narration.py`. Each updated in lockstep — same 3-tier
   logic, same fallback warning message, so the whole pipeline agrees
   with itself again rather than three tools finding one location and a
   fourth finding another.
3. **`build/make_scene_overlays.py`** had a fifth, simpler hardcoded copy
   (`os.path.join(F, "video", "script.json")`, no fallback at all) —
   replaced with a call to `assemble_video.py`'s own `script_path()`,
   which it already imports.
4. **`api_save_archive`** (Backup Scenes' archive step, built earlier
   today): its special-case "copy script.json in separately, since it's
   a sandbox/ sibling" logic is now conditional — it only still does that
   extra copy for a store `PTH.script()` had to fall back for. For an
   already-migrated store the ordinary sandbox sweep carries script.json
   along with the scene folders on its own, so the special case would
   otherwise just duplicate it.
5. **`api_siblings`'s walk-up-to-root loop** (`/api/siblings`) had a real
   bug from this, caught by the test suite before it shipped: walking up
   from a scene file, it used to stop at the first directory whose
   `PTH.script()` resolved to something real — but climbing from
   `sandbox/<scene>/` passes THROUGH `sandbox/` itself, and now that
   script.json can live directly inside sandbox/, the old-flat fallback
   tier matched AT sandbox/, stopping the climb one level too early and
   building every downstream path from the wrong root. Fixed by never
   treating a directory literally named `sandbox` or `dev` as a
   candidate root.
6. **Data migration**: all 4 real stores' `video/script.json` moved to
   `sandbox/script.json` via `git mv` (alpine-sports, bike-demo,
   canoe-demo, ski-demo) — same command, so history follows the file
   rather than showing a delete and an unrelated add.
7. **`tests/fixture.py`** now builds its test store's script.json directly
   in `sandbox/` (no `video/` folder created at all — nothing else in the
   fixture used it). **`tests/test_editor.py`**'s 4 direct reads of the
   fixture's script.json updated to match, plus `s_save_archive`'s
   assertions reworked for the new reality (script.json is now an
   ordinary top-level sandbox entry, not a special extra) and two stale
   comments fixed.
8. User-facing error strings ("this store has no video/script.json", "no
   video/script.json above …") shortened to drop the now-sometimes-wrong
   "video/" — `shared/serve.py`, `build/preview_narration.py`. A note
   string WRITTEN INTO every scene's `dev/scene.json` by
   `build/migrate_to_dev.py` had the same wording baked into actual
   output files — fixed there too, not just in comments.

**Deliberately NOT touched:** `setup_demo.py`'s `video/script.json`
reference (line 54) — it copies FROM `~/Rentify/Basic_E2E_Testing`, a
different repo whose current data shape wasn't investigated as part of
this change. If that repo's own copy is still at the old location, this
line still works via the fallback the source side doesn't need to know
about; if `setup_demo.py` itself needs updating, that's a separate,
smaller follow-up.

### A bug found and fixed by the test suite before this shipped

First test run after this change failed with a crash, not a check
failure: `/api/siblings` threw `AttributeError: 'NoneType' object has no
attribute 'endswith'` — item 5 above. The walk-up-to-root logic had been
touched to route through `PTH.script()`'s new fallback chain, and that
introduced the sandbox/-stops-the-climb-early bug described there. Found
immediately because the suite runs, not just parses — exactly the class
of fault this project's own test philosophy exists to catch.

### Verified

- `python3 -c "import ast; ast.parse(...)"` on all 11 touched `.py`
  files — parses.
- `python3 tests/test_editor.py` — **161/161 checks pass**, 31/31
  endpoints exercised. Failed once first (the bug above), fixed, reran
  clean.
- Confirmed all 4 real stores' `sandbox/script.json` exists with correct
  content (ski-demo's scene 1 checked specifically — the long line
  Carson had just written into it survived the move intact).
- `/api/vtt` and the live EVTT panel (browser, ski-demo's real timeline)
  both confirmed reading the new location correctly.
- `/api/save-archive`'s dry-run confirmed script.json now appears as a
  plain, unmarked entry in `would_archive` (no more `"(video/)"` suffix)
  — the ordinary sweep, not the special case, is what is finding it now.
- Server restarted (PID 31008 → 34048).

### To revert

Change `PTH.script()` back to the single `os.path.join(final, "video",
"script.json")` line, revert the 4 standalone tools' `script_path()`
functions to their 2-tier form, revert `make_scene_overlays.py`,
`api_save_archive`, and the `api_siblings` walk-up loop, restore
`tests/fixture.py`'s `video/` folder and script location, revert the 4
`test_editor.py` path references, and `git mv` each real store's
`sandbox/script.json` back to `video/script.json`. Restart the server
afterward.

---
