# HANDOFF

> **Run every command in this file from `Video-Editors/`.** The repo root
> was split on 2026-09-04 into `Customers/` and `Video-Editors/`.


Newest work first. One file so there is one place to check for open work.

---

## 2026-09-05 — two-folder root, dev/ as a mirror, a release is a folder

Branch **`customers-videos`**, pushed, and `main` fast-forwarded to match.
`next_gen_editors` and `All-Four-Editors-Working` are deliberately LEFT at
`101de08` — they still hold the pre-restructure tree, so checking either one
out means the editors will not start until you return to `main`.

**The root is now two visible folders**, `Customers/` beside
`Video-Editors/`. `.git`, `.gitignore`, `.claude/` and `CLAUDE.md` stay at
the root and must — a skill only registers at the PROJECT root, and moving
`.claude/` down makes every skill vanish silently.

**Run every command in this repo from `Video-Editors/`.** `Customers/` did
not move, so from there it is `../Customers`.

**`dev/` is now Carson's safety mirror of `sandbox/`**, not a build stage.
Nothing reads from it, and nothing may: it is archived to the root
`z_History/` and replaced wholesale on each refresh. The six suites used to
read their footage from `dev/01-login-and-code/` and the first refresh would
have killed all of them; the clips are at `tests/_fixture_source/` now,
gitignored, with a committed README. ⛔ **Do not touch that folder.**

**A release is a folder.** `release_video.py` writes
`help-videos/<NN-slug>/` holding the mp4, its `script_v<N>.json` (required)
and `vtt.html` if one exists. ski-demo v33 is released — the first one.

**Two skills to know about:**

- `/final-video-clean-up` — run after a release. Its step 0 is to ask
  whether what is parked in the root `z_History/` is obsolete yet.
- `vtt` — "Show me the VTT" builds an HTML table and opens a Chrome tab.
  ⚠ `python3 shared/vtt.py` is a NO-OP (a shim with no CLI; it prints
  nothing and exits 0). Use `python3 -m editor_base.vtt`.

**Open / not done:**

- `887 MB` parked in the root `z_History/` awaiting a decision:
  `cache-dead-20260904` (835 MB) and `dev-20260905-112452` (52 MB).
- ~1.1 GB sitting in the Trash, not yet emptied — Carson's call.
- `build/assemble_video.py` still carries someone else's uncommitted
  crossfade work. **Do not stage it.**
- SEVEN of ski-demo's eleven avatars are SHORTER than their own
  `narration.webm`; `vtt.html` flags them. Scene 2's is deliberate (the pose
  edit). The other six have not been listened to, so nobody knows whether
  words were lost.
- `next-editor-version/web/node_modules` was cleared. That editor needs
  `npm install` before it will start again.

All six suites pass: 696 checks.

## 2026-09-04 — the cleanup plan is FINISHED, Phases 3–7

Branch **`plan-implementation`** — ⚠ **that branch no longer exists.** It
was merged and deleted 2026-09-05 with zero unique commits; all of this work
is on `main` and `customers-videos`. Every step of `README-CODE-CLEANUP-PLAN.md` is now `✅ done`,
one commit each.

**The suites, after:**

| | start of plan | now |
|---|---|---|
| old combined server | 167 | 167 |
| Avatar Editor | 210 | **165** |
| Segment and Avatar Editor | 90 | **117** |
| MP4 Splitter | 82 | **101** |
| Frame Blender | 49 | **71** |
| `editor_base` | — | **57** (new) |
| **total** | | **678** |

**What landed, briefly:**

- **11a — `editor_base/`.** Carson chose Option A. `frames.py`, `paths.py`
  and `vtt.py` existed three times over and differed by **two lines of
  real code**; both are configuration now (`use_cache()`, `use_player()`).
  3,850 duplicated lines gone. `shared/` keeps ~25-line re-export shims so
  the nine `build/` scripts import unchanged — one of them,
  `assemble_video.py`, must not be edited.
- **12, 13 — the pages are static files.** `mp4_splitter/player.py` 1,568
  -> 66 lines; `segment_avatar_editor/player.py` 3,966 -> 134. Pages ship
  empty and the clip arrives over `/api/clip` and `/api/view`.
- **14, 15, 16 — the front end.** `gap-builder.js`'s 21 globals became
  three `const` state objects, then the file split into five; Frame
  Blender's `app.js` split into five.
- **17 — Avatar Editor's own cache.** Not the free change the plan
  assumed; see below.
- **18 — `ruff`**, rules `F` + `E9` only, never a formatter.

**The four things worth carrying forward:**

1. **A GREEN SUITE IS NOT A WORKING PAGE.** Three separate bugs shipped in
   one day with every suite green: a script truncated by 40 lines, a route
   serving the wrong page, and a load-order forward reference that threw on
   every page load. All three were found in the browser. Two now have
   permanent guards; the first probably cannot have one. **Open the tool
   after any change to a page.**
2. **`shared/serve.py` is more load-bearing than it looks.** Avatar Editor
   calls its helpers rather than copying them, and two of those read its
   module-level `CACHE`. Giving Avatar Editor its own cache therefore also
   needed `main_serve.CACHE = CACHE`, and both assignments must come after
   `import serve as main_serve`, which sets the cache at its own import
   time.
3. **Load order in the static pages is a behaviour contract.** Nine files
   in Avatar Editor, five in Frame Blender, one flat scope, no IIFEs.
   Moving a `<script>` tag is a behaviour change.
4. **`_splitter_player.py` is the last Python-string page**, and
   de-duplicating it was **deferred, not skipped** — the reasons are under
   Step 11a.8 in the plan. Revisit it as its own decision.

**Still open:** `ruff` flags 9 cosmetic things in `build/`, left alone and
written up in `ToDo.md` P3. `Sarah/sarah-scene-12-CORNER-preview-alpha.webm`
still sits unsorted at the library root — nobody has said what "scene 12"
is.

---

## 2026-09-03 (later) — the cleanup plan, Phases 0–2 implemented

Branch **`plan-implementation`**, off `next_gen_editors`. Nothing pushed.
Steps 0–9 of `README-CODE-CLEANUP-PLAN.md` are done and each is its own
commit; that file now marks them `✅ done`.

**The suites, after:**

| | before | after |
|---|---|---|
| Avatar Editor | 210 | **141** (79 source-text greps -> 9) |
| Frame Blender | 49 | 50 |
| MP4 Splitter | 82 | 83 |
| Segment and Avatar Editor | 90 | 91 |
| the old combined `test_editor.py` | — | 167, untouched |

All five green. The +1s are the new dead-handler guard.

**What landed:**

- **Step 0 — the plan had four errors; fixed before implementing.** The
  worst: its dead-handler guard was specified as a call-site diff, which
  under-reports, because dead code calling dead code looks alive. The
  real figure was 15 handlers / 930 lines / 36% of mp4_splitter's
  serve.py, not 13 / 759 / 29%. Following the original plan would have
  deleted 13, reported clean, and left 171 dead lines behind.
- **Steps 1–2 — `fixture.dead_handlers()`**, transitive reachability
  from `do_GET`/`do_POST`, wired into all four suites. Committed
  deliberately RED so the guard's find was on the record before the fix.
- **Steps 3–4 — 1,387 unreachable lines deleted.** mp4_splitter
  2,556 -> 1,383 (15 handlers + 5 orphaned module-level helpers);
  segment_avatar_editor 2,587 -> 2,373 (4 handlers + a stale
  `session_log()` branch still formatting a line for `/api/open`).
- **Steps 5–6 — the two missing READMEs written**, every factual claim
  verified rather than recalled.
- **Steps 7–8 — Avatar Editor's suite made honest.** 71 presence-greps
  removed, 8 absence assertions kept, plus the element-id contracts, the
  cross-panel isolation invariant (broken twice historically) and the
  no-silent-control scan. Mean checks per step ~10 -> 5.2.
- **Step 9 — every stated count corrected** in `CLAUDE.md` and
  `tests/README.md`, from a fresh run. `tests/README.md` gained a
  "What a check is allowed to assert" section so the grep habit does not
  return.

### Where it stops, and why

**Step 10 is a DECISION and needs Carson.** It is the duplication
strategy, and nothing past it can start without an answer:

- `paths.py` is byte-identical in three places.
- `_splitter_player.py` differs from `mp4_splitter/player.py` by 16
  lines out of ~1,570.
- `mp4_splitter/serve.py` and `segment_avatar_editor/serve.py` were 88%
  identical before this cleanup.
- Meanwhile Avatar Editor and Frame Blender each import 13 symbols from
  the legacy `shared/serve.py` and cannot run without it.

Option A is a shared `editor_base/`; Option B is full duplication made
honest with a drift report. Both are written out in the plan (11a/11b).
The review recommends A because the copies have not diverged, but it
overrides a rule Carson set, so it is his call. Record the answer in the
plan under `## Decision (Step 10)`.

**Phases 4–6 remain**: moving MP4 Splitter and SAE off Python-string
pages (Steps 12–13, the big ones — note Step 12's stale-cached-viewer
hazard, added in Step 0), gathering `gap-builder.js`'s 21 globals before
splitting it (14 then 15, in that order), Frame Blender's `app.js`
(16), Avatar Editor's own cache dir (17), a narrow linter (18), and the
final doc sync (19).

### Still standing, unchanged

- **`build/assemble_video.py` is modified and NOT ours** — someone
  else's uncommitted crossfade work-in-progress. Never touch it, never
  stage it, never commit over it.

---

## 2026-09-03 — Sarah's clips got a real home, and the Avatar Editor now has two library panels

Branch **`next_gen_editors`**. Everything below is **committed AND
pushed** — `git log` matches `origin/next_gen_editors` exactly, working
tree clean except `build/assemble_video.py` (not ours, never touch —
see the standing note further down) and this file. Avatar Editor is at
**`VERSION` 9**.

### Quick point-form refresher, for picking this back up cold

- Avatar Editor now has TWO side-by-side library panels: **`Sarah`**
  (her common library, `Sarah/` at the repo root) on the left,
  **`<store name>` / `<video name>`** (that store's own leftover files
  in `sarah_clips/`) on the right. Checking a clip in EITHER feeds the
  SAME Frame Selector / Clip-Gap Builder / Audio Menu below.
- **Read `.claude/skills/sarah-library/SKILL.md` before touching any of
  this again.** It is now the one place that explains what Sarah's
  clips are, where they live, and how the Avatar Editor and the build
  scripts each use them — CLAUDE.md points here for a reason.
- ski-demo's own `sarah_clips/libs/` — the old per-store organized
  library — is **archived**, not deleted: it's at
  `sarah_clips/z_history/20260903-112319/libs/`. The Avatar Editor's
  store panel deliberately never looks inside `z_history/`.
- `Sarah/sarah-scene-12-CORNER-preview-alpha.webm` still sits unsorted
  at `Sarah/`'s own root — **still unresolved**. Nobody has said what
  "scene 12" is (this video only has scenes 1–11). Don't guess a folder
  for it; ask Carson.
- Test suites now write their own log + report per editor, under
  `tests/<editor>/` — see "Testing output split apart per editor,
  too" below before running any of the four.
- A full **code review of all 4 editors** was done and handed to Carson
  as a downloadable `.txt` (scorecard + suggestions, not yet acted on).
  The one finding worth knowing before touching MP4 Splitter or Segment
  and Avatar Editor: both still build their whole page as one giant
  Python string (`player.py`, 1,568 and 3,966 lines) — the exact pattern
  Avatar Editor and Frame Blender already moved off of on 2026-08-30.
  Neither has a README either. See "Code review of all 4 editors" below
  for the full scorecard and ranked suggestions — nothing here has been
  started.

### Sarah's common library — built out, and wired into the Avatar Editor

Started from a plain question: where does `sarah_clips/libs` loading
actually come from, and does it match the top-level `Sarah/` folder?
Answer: they were two unrelated things — every store kept its own
private copy, and `Sarah/` was a hand-kept reference stash nothing read.
Carson's direction, arrived at over several turns: **`Sarah/` becomes
the real, common, shared library; a store's own `sarah_clips/` keeps
only what was developed specifically for that video.**

What that turned into, in order:

1. **The 7-folder taxonomy** — `openings`, `gap-fillers`, `idle`,
   `stills`, `transitions`, `sound_bits`, `closings` — added to
   `avatar_editor/serve.py`'s `LIBS_GROUP_ORDER`, and to `Sarah/` itself
   as real folders (`openings/` was the one that didn't exist yet,
   confirming Carson's original "7 nested folders" count).
2. **The 6 loose PNGs at `Sarah/`'s own root** (rest-pose, uncertainty)
   moved into `stills/`, where they belonged.
3. **Every real Sarah clip found under ski-demo's `01-first-time-
   ordering`** (the one finished video — all others are still in
   progress) that `Sarah/` didn't already have was copied in — never
   moved, so nothing a build script depends on broke. Files that fit no
   folder went to `Sarah/`'s own root, Carson's own rule for anything
   ambiguous. One exception, at his explicit instruction: the old
   `TRACK_rear_background.mp4` was genuinely MOVED and renamed to
   `Sarah/login_segment.mp4` — its original really is gone from
   ski-demo's `sarah_clips/`.
4. **A second library panel** added to the Avatar Editor — `Sarah`
   (common) beside the existing per-store one. Backend: `libs_list()`,
   `lib_frames()` and `lib_media()` all gained a `source` param
   (`store`|`common`), each clip now carries which library it came
   from, and a second, separately-scoped path guard (`safe_join_sarah`)
   keeps `Sarah/` and `Customers/` from ever being confused — tested
   with a deliberate path-escape attempt, refused correctly. Checking a
   clip in either panel feeds the SAME toolset (Carson's own call, so a
   build can mix a common clip with a store-specific one).
5. **ski-demo's own `sarah_clips/libs/` archived** to
   `sarah_clips/z_history/<timestamp>/libs/` — worked off the common
   library from here on. Confirmed the dependency was actually broken
   (the store panel answers cleanly empty for that pair, not an error),
   and confirmed no BUILD SCRIPT depends on that per-store `libs/`
   path — only the Avatar Editor's own browsing UI did.
6. **The store panel reworked** to browse a store's own `sarah_clips/`
   ITSELF (not `sarah_clips/libs/`, which is usually empty/archived
   now) — shows whatever loose files are actually still there, one
   plain group, `z_history/` deliberately excluded from the browse.
   Its header now reads the STORE name then the VIDEO name, not the
   folder path.
7. **A one-off orphan found and removed**: `sarah_clips/scene_overlays/
   v1/manifest.json` — leftover metadata from a since-superseded
   per-scene review tool (`make_scene_overlays.py`); the `.webm` files
   it described were migrated into today's `sandbox/` layout back on
   2026-08-26 and the manifest never went with them. Confirmed nothing
   else in the repo reads it before deleting.
8. **Two small polish items**: the common panel's title is now just
   `SARAH` (was `Sarah/ (common)`); both panels show a real spinning
   loading indicator while their own fetch is in flight, each hidden in
   a `finally` block so it can never get stuck spinning.

`tests/test_avatar_editor.py` grew from 60 checks (its state at the
last handoff) to **210**, entirely from this arc — including two checks
that specifically try to escape either library's root and confirm
they're refused.

### Sarah's documentation consolidated into one skill

Everything about what Sarah's clips ARE, why the standards exist
(rest pose, "uncertainty", why idle footage is rendered rather than
mined), and how the Avatar Editor works with either library was
scattered across `Sarah/README.md`, `Sarah/closings/README.md`,
`avatar_editor/README.md`, and a stale line in `editor-launchers/
SKILL.md` — some of it already wrong after the split above. Moved into
one file: **`.claude/skills/sarah-library/SKILL.md`**. `CLAUDE.md` now
says to read it first, every time, before touching `avatar_editor/`,
`Sarah/`, or any store's `sarah_clips/` — same pattern as the existing
`vtt`/`editor-launchers` rules.

The older docs were trimmed to point at the skill rather than staying
duplicated — `Sarah/README.md` is now a short landing note,
`avatar_editor/README.md` kept only its own code-architecture content,
`frame_blender/README.md` had a flatly wrong row deleted (described a
file — `gap-builder.js` — that tool hasn't had since the 2026-09-02
split). A real staleness bug was fixed along the way:
`Sarah/closings/README.md`'s own `mv` commands still said
`Sarah/closing` (singular) — the folder was renamed to `closings/` this
session and the doc never caught up.

Deliberately left alone: `docs/avatar_launch.md`, `heygen_api.md`,
`HEYGEN_RULES.md`, `avatar_compositing.md` — Sarah's locked HeyGen
identity and how a brand-new clip of her gets rendered is a different
concern from working with clips that already exist; the skill points to
them rather than absorbing them.

### Testing output split apart per editor, too

Before today, none of the four newer per-editor suites
(`test_avatar_editor.py`, `test_frame_blender.py`,
`test_mp4_splitter.py`, `test_segment_avatar_editor.py`) wrote a log
file at all — only the old combined `test_editor.py` did. Each of the
four now writes into its own folder:

```
tests/avatar_editor/avatar_editor_<HH>_<MM>_<SS>.log   the full transcript
tests/avatar_editor/avatar_editor_<HH>_<MM>_<SS>.txt   the pass/fail report
tests/frame_blender/frame_blender_<HH>_<MM>_<SS>.{log,txt}
tests/mp4_splitter/mp4_splitter_<HH>_<MM>_<SS>.{log,txt}
tests/segment_avatar_editor/segment_avatar_editor_<HH>_<MM>_<SS>.{log,txt}
```

The `.txt` report: total run, total passed, every step's own PASS/FAIL,
and — only when something failed — a `Failures:` section naming exactly
which check and what it found. One shared function,
`fixture.write_report()`, writes both for all four, so the shape can't
drift between them. Verified the failure-description path with a
synthetic failing result before trusting it for real. Before writing
this, confirmed the four editors' actual CODE is genuinely
independent — no editor imports another's Python, no editor's page
loads another's JS/CSS.

**One asterisk, flagged, not fixed:** Avatar Editor and Frame Blender
still share one `cache/` directory at the repo root — a leftover from
before they split apart. Data-directory sharing, not code sharing.

### Code review of all 4 editors

Full scorecard (1–10, five axes each — architecture, best practices,
separation of concerns, cross-editor use, readability) delivered to
Carson as a downloadable `.txt`. Nothing from it has been acted on yet.
Short version, ranked by what would help most:

1. Give MP4 Splitter and Segment and Avatar Editor a README each —
   Avatar Editor's and Frame Blender's are right there as a template.
2. Move both off the Python-string page-building style, the way Avatar
   Editor and Frame Blender already did (2026-08-30) — this is the
   single biggest structural fix available.
3. Split `segment_avatar_editor/player.py` (3,966 lines, the biggest
   file in the whole codebase) into its two page types.
4. Decide on `_splitter_player.py` — a documented, deliberate duplicate
   of MP4 Splitter's own player, copied rather than imported.
5. Smaller: split `gap-builder.js` (1,155 lines, 8 different jobs in
   one file) and Frame Blender's `app.js` (765 lines, no split at all)
   a bit further.

### Still standing, unchanged

- **`build/assemble_video.py` is modified and NOT ours** — someone
  else's uncommitted crossfade work-in-progress. Never touch it, never
  stage it, never commit over it.

---

## 2026-09-02 — the four editors split apart, logging split apart, two of them got their first tests

Branch **`next_gen_editors`**. 5 commits made today sit **ahead of `origin/
next_gen_editors`, not yet pushed** (oldest first):
`d58e1ba` Frame Blender v14, `4bfced5` Avatar Editor v3, `3abace8` MP4
Splitter v11, `6099590` Segment and Avatar Editor v60, `38337cf` the
CLAUDE.md Tests-section doc update. Push only if Carson says to.

**On top of those, working-tree changes not yet committed** (in
`avatar_editor/web/app.js`, `web/gap-builder.js`, `web/index.html`):
the Frame Selector's and Clip-Gap Builder's own Play buttons were
corrected to each play whichever clip THEIR OWN panel is currently
showing (an earlier version of this session played a "checked Sound
Bit" instead — Carson corrected that), and the Audio Menu's "Play" text
now turns green (`.ready` class, same language `gmCopySelected`/
`gmLibViewToggle` already use) once a Sound Bit is actually loaded.
Tested live both ways, 60/60 automated checks pass. **Not committed —
wait for Carson to say so**, then bump `avatar_editor/VERSION` to `4`
and commit as its own `Avatar Editor vN ADDED:` commit, per this repo's
own player-commit rule.

**`build/assemble_video.py` is modified and NOT ours** — someone else's
uncommitted crossfade work-in-progress, sitting there the whole
session as it has for weeks. Never touch it, never stage it, never
commit over it.

### What we succeeded on

1. **The 4 editors' purpose split settled, and code now matches it.**
   Frame Blender watches the two tracks (base + overlay) frame by frame
   and drives the combine/build — Overlay/Base panels, Speed dropdown,
   Build, Save MP4. Avatar Editor keeps only the Gap Builder — Sarah's
   own overlay library (`sarah_clips/libs`), the Frame Selector, and the
   Clip-Gap Builder that assembles gap-filler sequences from it. Avatar
   Editor started the session as a WHOLE duplicate of Frame Blender
   (including the combine/build UI); that half was removed outright
   (Overlay/Base panels, Build, Save MP4, and their backend routes)
   once the split was made explicit. Frame Blender's own Gap Builder
   (it had one too, from before the split) was removed the same way,
   moving the other direction.
2. **MP4 Splitter and the Segment and Avatar Editor's landing/viewer
   pages cleaned up**: no more `Browse Customers —` prefix, the tab
   title stays on the clean tool name even with a clip/scene open
   (was drifting to the source filename before). SAE's landing page
   was reworked from a raw `Customers/` file browser into the same
   store → video → sandbox-scenes-only picker the in-editor Load
   button already used — no more hand-pairing raw, uncut footage.
3. **Session logging split apart per editor** — was one shared
   `logs/editor_<date>.log` for all four standalone tools (plus the old
   combined server), with Frame Blender's and Avatar Editor's own
   actions mislabeled `"FB: Load video"` even when it was Avatar Editor
   that acted. Now each of the four writes to its own dedicated file
   (`frame_blender_<date>.log`, `avatar_editor_<date>.log`,
   `mp4_splitter_<date>.log`, `segment_avatar_editor_<date>.log`),
   correctly labeled, verified live by triggering a real action on each
   running server and reading the right line out of the right file.
   MP4 Splitter's and SAE's own `ACTIONS` label tables were also
   trimmed to just the routes each process actually serves — both
   still carried entries for routes that belong to OTHER tools,
   inherited from the shared table they were copied out of.
4. **MP4 Splitter and Segment and Avatar Editor each got their first
   real automated test suite** — `tests/test_mp4_splitter.py` (82
   checks) and `tests/test_segment_avatar_editor.py` (90 checks).
   Neither existed before today; both tools had been standalone
   processes since 2026-09-01/02 but were only ever checked by hand.
   Every kept route gets a real check, every route the split dropped is
   confirmed truly gone (404, not just untested), each tool's own cache
   directory and session log are verified directly, and every page's
   generated JavaScript is checked with `node --check` — SAE's suite
   checks all THREE of its pages, including `_splitter_player.py`'s own
   private duplicate of MP4 Splitter's viewer.
5. **Avatar Editor UI work**: `sarah_clips/libs` moved to the top-left
   of the page (was centered below Timeline Scenes); the Frame Selector
   and Clip-Gap Builder previewers now stay open all the time, including
   on first load, instead of staying hidden until something is picked.
6. **New standing rule, added to this repo's own `CLAUDE.md`**: code
   changes for one editor stay inside that editor's own files. The
   other three don't get touched in the same pass, even for an
   identical, obviously-correct fix, unless Carson explicitly widens
   scope in chat. (Also saved to Claude's cross-session memory, outside
   this repo.)
7. **Confirmed by direct ffprobe, not assumed**: `sarah_clips/libs/
   sound_bits/*.webm` carry a REAL video track (VP9, 1152×1152, Sarah's
   own avatar footage) plus the Opus audio — not audio-only files. So
   checking one in the Frame Selector should show her picture moving,
   not a blank/black viewer.

### What's still open

1. **The 3 uncommitted Avatar Editor files above** — waiting on
   Carson's go-ahead to commit (see the top of this section for exactly
   what's in them).
2. **The 5 commits above are unpushed.** Push only on explicit
   instruction.
3. **Frame Blender's and Avatar Editor's own tab titles still drift**
   once a scene is open (`Frame Blender — 01-intro-and-login`, same for
   Avatar Editor) — the exact thing that was fixed for MP4 Splitter and
   SAE earlier this session (item 2 above), just never asked for on
   these two. Spotted, not fixed — flag it if Carson wants it matched.
4. Carson reported the Frame Selector/Gap Builder Play buttons "not
   working" more than once this session; every attempt to reproduce it
   with real clicks succeeded. The audio-source correction and the
   green-ready fix (both in the uncommitted work above) may be what he
   was actually asking for each time — worth confirming on his return
   rather than assuming closed.
5. Everything under "What's still open" in the 2026-08-30 sections
   below is unchanged and still real: **scene 1's frozen tail (frames
   442–482) is still frozen**, the transition tools are still
   command-line only, and only one gap-filler size exists in the
   library.

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
