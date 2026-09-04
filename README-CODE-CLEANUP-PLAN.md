# Code Cleanup Plan — the four editors

Written 2026-09-03, from the third-pass code review of `avatar_editor/`,
`frame_blender/`, `mp4_splitter/` and `segment_avatar_editor/`. This is
the step-by-step to make the code compliant with that review and to fix
the testing deficiencies it found. It is ordered by dependency: each
step assumes the ones before it are done.

Every finding from the review is mapped to a step in the **Compliance
checklist** at the end, so nothing is left to memory.

---

## Decision (Step 10) — Option A, 2026-09-03

**Carson chose Option A: a supported base library.**

The shared, genuinely-pure code moves into one package all the editors
import from. `shared/serve.py` stops being "the old server that cannot
be removed" and becomes an ordinary consumer of the same base.

The mitigations that made Option A acceptable are not optional — they
are what keeps this from re-creating the coupling the 2026-09-02 split
removed:

- The base library holds **pure functions only**. No routes, no
  request state, no page rendering. If it needs `self`, it does not
  belong there.
- It has **its own test suite** (`tests/test_editor_base.py`) and its
  own report folder, like every editor.
- **A change to the base runs all five suites**, not just one.
- `CLAUDE.md`'s "editor changes stay inside the one editor" rule gains
  exactly one named exception, and no more (Step 11a.9).

Implemented in Steps 11a.1–11a.9 below.

---

## Rules that apply to every step

These come from `CLAUDE.md` and the standing instructions. They are not
optional and they are restated here so a cold reader does not have to
go looking.

- **One editor per task.** Code changes go in that editor's own files
  only. Touching a second editor in the same pass needs Carson's
  explicit go-ahead, in the chat, that same conversation. Several steps
  below are therefore written *per editor* and must be run as separate
  tasks, one editor at a time.
- **A cleanup is a restructure, not an `ADDED:`.** `CLAUDE.md`: *"A
  restructure is not an `ADDED:` — commit that plainly and leave
  `VERSION` alone."* Deleting dead code, splitting a file, and moving a
  page off a string template do not change what the player *does*. Do
  not bump `VERSION` for them. The commit hook will nag; it says itself
  it is not blocking.
- **Never touch `build/assemble_video.py`.** Someone else's uncommitted
  work. Not staged, not committed, not edited.
- **Do not commit or push until Carson says so.** Each step ends with
  "ready to commit," not "committed."
- **Run the affected editor's suite after every step, and read its
  report.** The suites now write to `tests/<editor>/<editor>_<HH>_<MM>_<SS>.txt`.
  A step is not done until that report says `PASS`.
- **The four suites share one fixture store.** Run them one after
  another, never in parallel.

---

## Phase 0 — Guardrails first

*Purpose: put a test in place that will catch the thing being cleaned
up, BEFORE cleaning it up. Then the fix is proven by a test that stays.*

### Step 1. Add a dead-handler guard to `tests/fixture.py`  ✅ done 2026-09-03

**Why:** the review found unreachable handler bodies in MP4 Splitter and
Segment and Avatar Editor. Every suite asserts the *routes* 404. None
can see that the *handler bodies* are still there. This guard closes
that gap, permanently.

**⚠ REACHABILITY, NOT "IS IT CALLED".** The first draft of this plan
specified "collect every `self.<name>(` call site and diff." That is
wrong, and it under-reports: **dead code calling dead code looks alive.**
In `mp4_splitter/serve.py`, `api_open_pair` and `api_open_seq` *are*
called — but only from `api_open_pair_go` and `api_open_seq_go`, which
are themselves dead. A call-site diff marks them live and leaves 171
lines hidden, then reports "clean" after Step 3.

The guard must compute **transitive reachability from the dispatchers**
(`do_GET`, `do_POST`) and treat everything not reached as dead.

**What:** add one function to `tests/fixture.py`, shared by all four
suites (same reasoning as `write_report()` — one place, no drift):

```python
def dead_handlers(serve_py_path):
    """Handler methods that no dispatcher can reach, transitively.

    A route can be deleted from do_GET/do_POST while its body stays
    behind — the suite's own 404 checks pass either way, so this is
    the only thing that can see it. Walks OUT from do_GET/do_POST
    following self.<name>() calls; whatever is never arrived at is
    dead, including a chain of dead handlers calling each other.

    Returns a sorted list of names. AST only — never imports or runs
    the server.
    """
```

Method: parse with `ast`, take the `Handler` class, build a
name → {called names} map, then walk out from `do_GET`/`do_POST`
until the reachable set stops growing. Dead = candidate methods minus
reachable.

**Candidate set — one rule, all four editors.** No prefix lists and no
hand-maintained name sets (the first draft needed those and they were
the reason it was hand-wavy for the two plain-named editors). Exclude
only framework/base plumbing by prefix:

```
do_    _    send_    end_    translate_    log_    address_
```

Everything else on `Handler` is a candidate. Verified below that this
one rule gives the right answer for all four.

**Verify:** call it from a scratch Python one-liner against all four
`serve.py` files. Expected right now:

```
avatar_editor:            0 unreachable,    0 lines
frame_blender:            0 unreachable,    0 lines
mp4_splitter:            15 unreachable,  930 lines  (36% of serve.py)
segment_avatar_editor:    4 unreachable,  207 lines  (8%)
```

If it does not report exactly **15** and **4**, the guard is wrong —
fix the guard before going further. (13 means it is doing a call-site
diff, not reachability. That is the bug this box is about.)

### Step 2. Wire the guard into all four suites — and watch two of them FAIL  ✅ done 2026-09-03

**What:** add one step to each `tests/test_<editor>.py`:

```
step("no handler is defined that the dispatcher cannot reach")
eq("unreachable handlers", fixture.dead_handlers(<SERVE_PATH>), [])
```

Place it right after the existing "routes this split deliberately
dropped — confirmed gone" step in `test_mp4_splitter.py` and
`test_segment_avatar_editor.py`; anywhere sensible in the other two.

**Verify:** run all four.
- `test_mp4_splitter.py` — **must FAIL**, listing the 15 names.
- `test_segment_avatar_editor.py` — **must FAIL**, listing the 4.
- `test_avatar_editor.py`, `test_frame_blender.py` — must pass.

A failing test here is the correct outcome. It proves the guard works.
Do not "fix" the test; fix the code in Phase 1.

**This is one commit across four test files.** It is test
infrastructure, not player code — the one-editor rule is about the
editors' own files, and `tests/` is shared. Subject: plain, e.g.
`Guard against dead handlers in every editor's suite`. No VERSION bump.

---

## Phase 1 — Free wins (no behaviour changes)

### Step 3. Delete the 15 unreachable handlers in `mp4_splitter/serve.py`  ✅ done 2026-09-03 (15 handlers + 5 orphaned helpers, 1,173 lines)

**Task scope:** MP4 Splitter only.

**What to delete** — these method bodies, in full, including their
docstrings:

```
api_join            api_line            api_open_pair
api_open_pair_go    api_open_seq        api_open_seq_go
api_paste           api_renumber_clear  api_renumber_state
api_save_archive    api_siblings        api_span
api_split           api_stores          api_vtt
```

`api_open_pair` and `api_open_seq` are on this list for the reason in
Step 1's warning box: they are reachable ONLY from `api_open_pair_go`
and `api_open_seq_go`, which are themselves dead. Delete all four
together — deleting the two `_go` wrappers alone would leave the other
two orphaned and the guard would then (correctly) fail again.

**Before deleting each one, confirm it really is unreachable:** `grep
-n "self.api_join(" mp4_splitter/serve.py` must return nothing (the
`def` line does not count). The guard from Step 1 already did this; the
grep is the belt to its braces.

**Also delete** any now-unused imports or module-level helpers that
only those handlers used — run `python3 -c "import ast; ..."` or simply
`python3 mp4_splitter/serve.py --help` to confirm the module still
imports cleanly.

**Update the module docstring.** Its "Routes:" block already omits
these, so it is probably already correct — but re-read it. The line
*"SAE-only routes … are gone from the dispatch tables below"* should
now read *"… are gone entirely"*, because they finally are.

**Verify:**
- `python3 tests/test_mp4_splitter.py` → **PASS**, and the Step 2 guard
  now reports `[]`.
- The pre-existing "routes this split deliberately dropped — confirmed
  gone" step still passes (the routes still 404 — nothing changed
  there).
- File shrinks by roughly 930 lines — about 36% of it. `wc -l` before and after.

Ready to commit. Plain subject. No VERSION bump.

### Step 4. Delete the 4 dead handlers in `segment_avatar_editor/serve.py`  ✅ done 2026-09-03 (4 handlers + a stale log branch, 214 lines)

**Task scope:** Segment and Avatar Editor only. A separate task from
Step 3.

**What to delete:**

```
api_clear_edits     api_handoff         api_open
api_reset_editor
```

Same procedure as Step 3: confirm each with grep, delete the body,
prune now-unused imports, fix the docstring, verify with
`python3 tests/test_segment_avatar_editor.py` → **PASS**, guard reports
`[]`. Roughly 207 lines gone.

Ready to commit. Plain subject. No VERSION bump.

### Step 5. Write `mp4_splitter/README.md`  ✅ done 2026-09-03

**Task scope:** MP4 Splitter only.

It is one of two editors with no README. Use `frame_blender/README.md`
as the template — same headings, same length, same tone. It must cover:

- one-line purpose (from `serve.py`'s own docstring)
- how to start it and its port (8845)
- **What's in here** — a table of every file: `serve.py`, `player.py`,
  `frames.py`, `paths.py`, `VERSION`, and what each owns
- that `frames.py`/`paths.py` are **copies** of `shared/`'s, not
  imports, and why (link to the decision in Step 9 once made)
- that the page is built from a Python string in `player.py` (and, once
  Step 12 is done, that it no longer is)
- the commit rule (one player per commit, bump `VERSION` for real
  changes, plain commit for restructures)

**Verify:** every file named in the table exists (`ls`). No claim in
the README that `grep` can prove false.

Ready to commit. Docs only, no VERSION bump.

### Step 6. Write `segment_avatar_editor/README.md`  ✅ done 2026-09-03

**Task scope:** Segment and Avatar Editor only. Separate task from Step 5.

Same template. Additionally it must explain:

- `player.py` builds **two** pages, `PAIR_TEMPLATE` (layered) and
  `SEQ_TEMPLATE` (timeline), and why they are one file
- `_splitter_player.py` is a **99%-identical copy** of
  `mp4_splitter/player.py`, kept so the SAE's "open this scene on its
  own" link works without importing another editor — and that this is a
  known duplication (Step 10 decides its future)
- `vtt.py` is its own copy too

Ready to commit. Docs only.

---

## Phase 2 — Fix the testing deficiencies

*Purpose: make a green run mean what it looks like it means. This phase
is deliberately BEFORE the big structural work in Phases 3–4, because
that work needs a suite that tests behaviour, not spelling.*

### Step 7. Reclassify every source-text check in `tests/test_avatar_editor.py`  ✅ done 2026-09-03 (211 -> 141 checks; greps 79 -> 9)

**Task scope:** Avatar Editor's suite only.

**The finding:** ~78 of its 173 checks assert that a literal string
appears in the served JS/HTML/CSS — e.g. `"P.resync(STACK)" in fp`.
Those pass when the feature is broken and fail when a variable is
renamed. Frame Blender's suite (40 checks, ~1 such) is the model.

**How to find them:** they all read a served file into a variable and
test membership. Grep for these patterns and list every hit:

```
" in js    " in gb    " in fp    " in wc    " in tt    " in html
" in css   " in src   " in serve_src   " in fs_block   " in gb_block
" not in <any of the above>
```

**Classify each one into exactly one bucket, and write the bucket down
in a comment above it before changing anything:**

| Bucket | Meaning | Action |
|---|---|---|
| **A — behavioural twin exists** | the thing being asserted can be observed through an HTTP call or a served page's *effect* | rewrite as a behavioural check; delete the grep |
| **B — pure spelling** | only asserts an identifier or phrase is present; no observable behaviour behind it | delete |
| **C — genuinely structural** | asserts load order, an element id exists in the HTML, a file parses, a security-relevant string is absent | keep, but move into a step titled `structure — …` so it is counted honestly |

Worked examples from the current file:

- `"P.resync(STACK)" in fp` → **B**. Delete. The behaviour ("ticking
  mid-run extends the run") cannot be driven over HTTP; it is
  browser-only, and pretending a grep covers it is the problem.
- `'id="libGroupsCommon"' in html` → **C**. Keep, under a `structure`
  step. An element id is a real contract between HTML and JS.
- `"gmSaveTarget.onchange" in gb` → **B**. Delete.
- `"function storeVideoFromPath(rel)" in gb` → **B**. Delete.
- `"parts.indexOf('sandbox')" in gb` → **B**. Delete.
- the `safe_join_sarah` path-escape checks that call `/api/lib_frames`
  with `../Customers/...` → these are already **behavioural** (they hit
  the server and assert 400). Not in scope; leave them.
- `"<h3>Sarah</h3>" in html` → **C** (HTML contract). Keep.
- `"const DELAY = 3000;" in tt` → **B**. Delete. (A 3-second tooltip
  cannot be tested over HTTP; the check only proves a constant is
  spelled that way.)

**Expected outcome:** the count drops from ~173 to somewhere near
95–110, most of the drop being bucket B. That is the honest number.
**Fewer checks, better checks.**

**Verify:** suite passes; every remaining check either drives HTTP or
sits under a step whose title starts with `structure —`.

Ready to commit. Test-only. No VERSION bump.

### Step 8. Break Avatar Editor's 10-check steps toward one-step-per-concern  ✅ done 2026-09-03 (fell out of Step 7: mean ~10 -> 5.2)

**Task scope:** Avatar Editor's suite only. Can be the same task as
Step 7 if convenient.

**The finding:** Avatar Editor packs ~10 checks per step; SAE runs ~3
per step, one step per endpoint. When a 10-check step fails, the report
says which *step*, and the reader has to dig for which *check*.

**What:** split the largest steps (`s_working_clips`, `s_original_audio_
stack`, `s_common_library_wiring`, `s_tooltips`) so that each `step(…)`
covers one concern. A step should rarely exceed ~5 checks. The `.txt`
report will then show PASS/FAIL per concern, which is the whole point
of the report.

**Verify:** `tests/avatar_editor/<latest>.txt` lists more, smaller
steps; all PASS.

### Step 9. Correct every stated check count  ✅ done 2026-09-03

**Task scope:** docs. Can be one commit.

After Steps 7–8 the real numbers change. Update:

- `CLAUDE.md` → Tests section, the `# … — N checks` comments on all
  five lines. Take the number from a fresh run, never from memory.
- `tests/README.md` → any count it states.
- `HANDOFF.md` → the "grew from 60 to 210" line should note the
  reclassification and the new honest count.

**Verify:** `grep -n "checks" CLAUDE.md tests/README.md` — every number
matches the newest `.txt` report for that editor.

---

## Phase 3 — Decide the duplication strategy, then act on it

*Purpose: the two editor pairs made opposite trade-offs. The modern
pair (Avatar Editor, Frame Blender) imports 13 symbols from the legacy
`shared/serve.py` and stays small. The legacy pair (MP4 Splitter, SAE)
copied everything and got fat. Neither is clean. One decision fixes
both.*

### Step 10. DECISION — Carson's call, made explicitly, written down  ✅ done 2026-09-03 (Option A)

**This step is a question, not a change.** Do not proceed past it
without an answer in the chat.

The facts the decision rests on (all measured in the review):

| Compared | Differs by |
|---|---|
| `paths.py` — `shared/` vs `mp4_splitter/` vs `segment_avatar_editor/` | 0 lines, byte-identical, three copies |
| `frames.py` — mp4 vs sae | 36 lines, nearly all comments *about being a copy* |
| `serve.py` — mp4 vs sae | 305 of ~2,570 (88% identical) |
| `_splitter_player.py` vs `mp4_splitter/player.py` | 16 of ~1,570 (99% identical) |
| `serve.py` — avatar_editor vs frame_blender | 658 lines — genuinely diverged |
| symbols Avatar Editor / Frame Blender import from `shared/serve.py` | 13 each: `frame_count`, `cache_state`, `save_marks`, `load_marks`, `resolve_outdir`, `build_segment`, `is_alpha`, `dec_for`, `session_log`, `SESSION_LOG`, `SESSION_OFF`, `SESSION_DIR`, `ACTIONS` |

**Option A — a supported base library.** Promote the genuinely shared,
genuinely pure code into one package all four import from. Candidate
name: `editor_base/` (or keep `shared/` but strip it down to *only* the
pure helpers and rename its role). Contents: `paths.py`, `frames.py`,
and the 13 helpers above pulled out of `shared/serve.py`. The old
combined server on port 8842 keeps working by importing the same base.

- Cost: this is the one thing the 2026-09-02 split said it would never
  do. It reintroduces a place where one change reaches four tools.
- Mitigation: the base library is *pure functions only* — no routes, no
  state, no page. Its own test suite. A change to it runs all five
  suites.
- Benefit: ~3,500 duplicated lines gone; `_splitter_player.py` becomes
  a real import; the "cannot be removed" legacy server becomes an
  ordinary consumer.

**Option B — full duplication, made honest.** Keep the rule. Then apply
it evenly: Avatar Editor and Frame Blender each copy the 13 helpers in
(the same move MP4 Splitter/SAE already made), so *all four* are
genuinely standalone and `shared/serve.py` can finally be deleted.

- Cost: four copies of `paths.py`/`frames.py`, and ~1,000 more
  duplicated lines in the modern pair.
- Mitigation — **mandatory under this option:** a **drift test** in
  `tests/fixture.py` that diffs each copy against a named reference and
  *reports* the divergence in every run's `.txt` report (not fails —
  divergence is allowed; *silent* divergence is not). Then a bug fixed
  in one copy is at least visible as missing from the others.
- Benefit: the rule stays simple and absolute; no editor can break
  another, ever.

**Recommendation in the review: Option A**, because the measured
divergence in the copies is essentially zero — the duplication has so
far bought nothing — and because the modern pair *already* depends on
shared code and always has. But it overrides a rule Carson set, so it
is his call.

Record the answer at the top of this file under a heading
`## Decision (Step 10)` with the date.

### Step 11a. If Option A — build the base library  ✅ done 2026-09-04

Order of operations (each a separate task, one editor at a time after
the library exists):

1. Create `editor_base/` with `__init__.py`, `paths.py`, `frames.py`,
   `helpers.py` (the 13 functions/constants, lifted verbatim from
   `shared/serve.py`). No routes, no `Handler`, no page.
2. Give it `tests/test_editor_base.py` — pure-function tests for every
   helper. Own folder `tests/editor_base/` for its reports, same
   `write_report()` as the others.
3. `shared/serve.py` → import from `editor_base` instead of defining
   the helpers. Run `tests/test_editor.py`. Green.
4. **Avatar Editor task:** replace `import serve as main_serve` and
   `from serve import …` with `editor_base` imports. Run its suite.
5. **Frame Blender task:** same.
6. **MP4 Splitter task:** delete its `frames.py`/`paths.py`; import
   from `editor_base`. Run its suite, *including* the "its own cache"
   step — the cache dir is config, not code, and must stay separate.
7. **SAE task:** same, plus `vtt.py` if it is also a copy (check with
   `diff shared/vtt.py segment_avatar_editor/vtt.py` first).
8. **SAE task:** `_splitter_player.py` — fold the 16 differing lines
   into parameters on `mp4_splitter/player.py` *or* into `editor_base`,
   and import. Delete the copy.
9. Update `CLAUDE.md`'s "Editor changes stay inside the one editor"
   section to add the one exception: `editor_base/` is shared by
   design, and a change to it runs all five suites.

### Step 11b. If Option B — make the duplication honest

1. `tests/fixture.py` → add `drift_report(reference, copies)` that
   diffs and returns line counts; `write_report()` appends a `Drift:`
   section to every `.txt` when any copy differs from its reference.
2. **Avatar Editor task:** copy the 13 helpers into
   `avatar_editor/helpers.py`; drop the `shared/` imports. Suite green.
3. **Frame Blender task:** same.
4. Once nothing imports it: delete `shared/serve.py` and
   `tests/test_editor.py`, and remove the port-8842 entry from
   `.claude/skills/editor-launchers/SKILL.md` and `CLAUDE.md`.
5. `_splitter_player.py` stays; the drift report now shows its 16-line
   divergence in every SAE run, so it can never drift further unseen.

---

## Phase 4 — Move the legacy pair off Python-string pages

*Purpose: the single largest structural fix. The pattern to copy
already exists in this repo — Avatar Editor and Frame Blender did
exactly this on 2026-08-30. Copy their shape, do not invent a new one.*

**Prerequisite — corrected.** The first draft said "Phases 1–2 done for
the editor in question." That is wrong: **Phase 2 is entirely about
Avatar Editor's suite** and does nothing for these two, so as written
the prerequisite was vacuous. What MP4 Splitter and SAE actually need
before their page is rebuilt:

1. **Phase 1 done for that editor** (Steps 3/4 — its dead code gone, so
   the rewrite is not carrying corpses across).
2. **Its `node --check` page guard confirmed green and understood** —
   MP4 Splitter's Step 20, SAE's Step 32. That guard is the only thing
   standing between a broken page and a silent ship, and sub-step 7
   below repoints it. Know what it covers before you move it.
3. **Its README written** (Steps 5/6), because the rewrite changes what
   the README would have to say anyway.

### Step 12. MP4 Splitter — extract the page

**Task scope:** MP4 Splitter only.

**The pattern to copy** (from `avatar_editor/`):

- `web/index.html` — the page, with **no scene in it**
- `web/app.js`, `web/app.css` — plain files, no escaping, no `{{ }}`
- `serve.py` serves `/web/*` via a `send_web()` method (copy Avatar
  Editor's, lines ~283–310)
- **The page ships empty and the clip arrives over the API.** Today
  `player.py` bakes ~24 values into the HTML at render time (`disp_w`,
  `disp_h`, `fps`, `nb_frames`, `has_audio`, `edited_flag`, `slug`,
  `source`, …). Each of those becomes a field the page fetches on load
  from a small JSON endpoint — `/api/clip?slug=…` — exactly the way
  Avatar Editor's `SCENE` arrives from `/api/open_pair`.

**Sub-steps:**

1. Enumerate every `{placeholder}` in `mp4_splitter/player.py`'s
   `TEMPLATE` precisely (`grep -oE "\{[a-z_]+\}" | sort -u`). Those are
   the fields the new `/api/clip` endpoint must return. Do this first;
   the review counted ~24 but the exact list is the contract.
2. Add `/api/clip?slug=` to `serve.py` returning that JSON. Test it
   (behavioural: real slug → 200 + every field present; bad slug → 400).
3. Create `web/index.html` from the template's HTML with every `{{`
   `}}` un-doubled and every `{placeholder}` removed.
4. Create `web/app.js` from the `<script>` block, un-doubled, with a
   `CLIP = null` / `fetch('/api/clip?…')` bootstrap at the bottom (copy
   Avatar Editor's bootstrap shape).
5. Create `web/app.css` from the `<style>` block, un-doubled.
6. `player.py` → `write(outdir, meta)` no longer renders a template. It
   either writes a one-line `viewer.html` that redirects to
   `/?slug=<slug>`, or `serve.py` handles `/<slug>/viewer.html` by
   serving `web/index.html` directly. Pick the one that keeps every
   existing URL working — the suite's "open one clip" step is the test.

   **⚠ STALE CACHED PAGES — the migration hazard.** `player.write()`
   writes a *physical `viewer.html` into every clip's own cache folder*
   (`<cache>/<slug>/viewer.html`). So every clip ever opened already has
   a fully-rendered copy of the OLD page sitting on disk, and those keep
   being served after the rewrite. A fresh test store will not show
   this — the fixture builds clean caches — so the suite can pass while
   Carson's real, months-old caches still serve the old page.

   Handle it explicitly, one of:
   - have `serve.py` route `/<slug>/viewer.html` to the new static page
     and ignore any file on disk (simplest, and makes every old cache
     correct for free); or
   - bump the cache format so existing slugs re-extract; or
   - delete the stale `viewer.html` files as a one-off migration.

   **Verify against a clip cached BEFORE the change** — not just a
   fresh one. Open something already in `cache_mp4_splitter/` from
   earlier work and confirm it serves the new page.
7. **Keep the `node --check` guard, but point it at the static files.**
   Today `s_…does the JavaScript actually run?` checks the *generated*
   page. Change it to fetch `/web/app.js` and `node --check` it — the
   exact step Avatar Editor's `s_app_js_parses` already does.
8. Delete `TEMPLATE` from `player.py`. The file should shrink from
   1,568 lines to well under 200.

**Verify:** `python3 tests/test_mp4_splitter.py` → PASS. Open the tool
in Chrome, open a real clip, click through ＋/− Frame, Mark, Cut. Same
behaviour as before. `wc -l mp4_splitter/player.py` before/after.

Ready to commit. This is a restructure (behaviour unchanged) — plain
subject, no VERSION bump. If Carson prefers to treat "the page is now
static files" as a visible change, bump and use `ADDED:` — his call.

### Step 13. Segment and Avatar Editor — extract both pages

**Task scope:** SAE only. **The biggest step in this plan.** Do it after
Step 12 so the pattern is proven on the smaller tool first.

Same sub-steps as Step 12, with these differences:

- There are **two** templates, `PAIR_TEMPLATE` (layered) and
  `SEQ_TEMPLATE` (timeline). Extract them as two pages — `web/pair.html`
  + `web/pair.js`, `web/seq.html` + `web/seq.js` — sharing one
  `web/app.css` and, only if genuinely identical, a `web/common.js`.
  Do not force them into one page; they were two templates for a
  reason.
- The placeholder count is roughly double MP4 Splitter's (~50). Two
  endpoints: `/api/pair?slug=` and `/api/seq?slug=`.
- `_splitter_player.py` (the 99% copy of MP4 Splitter's player) is
  resolved by Step 11a/11b, *not* here. If Step 11 has not happened
  yet, leave it alone in this step.
- `player.py` should shrink from 3,966 lines to well under 300.
- The `node --check` guard already checks **three** pages here (Step
  32 in its suite); repoint all three at the new static files.

**Verify:** suite PASS; every one of the 32 steps still green; a real
layered view and a real timeline open in Chrome and behave identically.

---

## Phase 5 — Front-end structure in the modern pair

### Step 14. `gap-builder.js` — gather the 21 globals into one state object FIRST

**Task scope:** Avatar Editor only.

**The finding:** 21 top-level `let` variables, mutated from 25
functions and many inline handlers. This is the *cause* of "8 jobs in
one file" — the file cannot be split while every part of it reaches
into the same loose state.

**Order matters.** Do this step *before* Step 15. Splitting first would
spread the same shared state across more files and make it worse.

**The 21, by the concern they belong to:**

| Concern | Globals |
|---|---|
| the library / Frame Selector's collection | `PICKED`, `LIB_FRAMES`, `LIB_ORDER`, `libCurClip`, `restPosePath`, `restPoseSource`, `restPoseFrame` |
| the Frame Selector's selection state machine | `LIB_SELECTED`, `libRangeStart`, `libPhase`, `libArmed`, `libShowSelectedOnly`, `libStepping` |
| the Clip-Gap Builder's collection | `BUILDER_FRAMES`, `builderCurClip`, `builderStepping` |
| the Clip-Gap Builder's selection state machine | `SELECTED`, `builderRangeStart`, `builderPhase`, `builderArmed` |
| shared between the two rows | `CLIPBOARD` |

**What:** replace them with a small number of state objects, one per
concern row above — e.g. `const LIB = {picked: [], frames: [], order:
[], …}` and `const BUILDER = {…}` — or, better, follow the shape
`frame-player.js` and `working-clips.js` already use: an IIFE that owns
its state and exposes a small object. The second is the established
house pattern in this same editor.

**The trap:** `app.js` reaches into several of these by name
(`PICKED`, `BUILDER_FRAMES`, `CLIPBOARD`, `SELECTED` in `showEmpty()`).
Grep `app.js` for every one of the 21 names first and update each
reference. The flat scope means nothing will warn you.

**Verify:** the suite's `s_app_js_parses` still passes (both files
together, in load order); the live editor — tick a clip, select frames,
copy, paste, save to Working Clips, Replace Selected, Clear — all
behave identically. Zero top-level `let` left in `gap-builder.js`
(`grep -cE "^let " → 0`).

Ready to commit. Restructure, no VERSION bump.

### Step 15. `gap-builder.js` — now split it

**Task scope:** Avatar Editor only. After Step 14.

Its own section banners already say where the seams are:

```
// ── sarah_clips/libs ──             → web/library.js
// ── Clip-Gap Builder ──            → web/clip-gap-builder.js
// ── Gap Builder Menu ──            → web/gap-menu.js
// ── the three Play buttons ──      → stays with gap-menu.js
// ── Working Clips: saving out … ── → already mostly in working-clips.js; move the rest
// ── hand the player what it needs ─→ a 10-line web/wire.js, loaded last
```

Update `index.html`'s `<script>` order and the load-order comment
above it. Update `avatar_editor/README.md`'s file table. Update the
suite's `s_app_js_parses` to fetch and parse every new file, alone and
concatenated in load order.

**Verify:** suite PASS; no file over ~400 lines; live editor identical.

### Step 16. `frame_blender/web/app.js` — split by its section banners

**Task scope:** Frame Blender only. Separate task.

Same approach as Step 15, smaller: 765 lines, 0 globals, already
well-sectioned. Likely three files: the combine/build engine, Timeline
Scenes + the Load popup, persistence. Update its README's table and its
suite's parse step.

---

## Phase 6 — Tooling and hygiene

### Step 17. Give Avatar Editor its own cache directory

**Task scope:** Avatar Editor only.

**The finding:** Avatar Editor and Frame Blender share one `cache/` at
the repo root. MP4 Splitter and SAE each got their own
(`cache_mp4_splitter/`, `cache_segment_avatar_editor/`) at the
2026-09-02 split; this pair was missed.

**What:** in `avatar_editor/serve.py`, `CACHE = os.path.join(ROOT,
"cache_avatar_editor")`. Add the folder to `.gitignore` beside the other
two. Add a step to its suite modelled exactly on MP4 Splitter's *"its
own cache — cache_mp4_splitter/, not the shared cache/"* step.

**Note:** Frame Blender then keeps `cache/` to itself. That is fine —
or give it `cache_frame_blender/` in its own separate task for
symmetry. Update `.claude/skills/editor-launchers/SKILL.md`'s cache
column either way; it currently documents the sharing.

### Step 18. Add a linter — narrow, non-reformatting

**Task scope:** repo-wide config, one commit.

**The finding:** no linter or formatter config anywhere. Consistency is
held by hand.

**What:** `ruff` for Python with a deliberately small rule set — unused
imports, unused variables, undefined names, syntax — and **no
auto-formatting**, so it never rewrites the hand-styled files. A
`pyproject.toml` with `[tool.ruff]` `select = ["F", "E9"]` is enough to
start. For JS, `node --check` in the suites already covers syntax; a
full ESLint setup is not worth the churn on a single-purpose tool page.

Run it once across all four editors and `shared/`/`build/`/`tests/`.
Fix only what it flags in the editors (the dead-code deletions in Phase
1 will already have removed most unused imports). Do not touch
`build/assemble_video.py` even if it flags — note the findings in
`ToDo.md` instead.

**Verify:** `ruff check .` is clean for the four editors and `tests/`.

---

## Phase 7 — Sync every document that describes the four editors

### Step 19. Update the docs the cleanup made stale

One pass, one commit, after everything above:

- `CLAUDE.md` — Tests section counts (again, if Phase 4 changed
  them); the "old combined server … cannot be removed" note (changed or
  gone depending on Step 10); the "pages are Python `.format()`
  templates" section — **delete it** once Steps 12–13 are done, it will
  no longer be true of anything.
- `tests/README.md` — currently describes only `test_editor.py`.
  Rewrite its top to describe all five (or four, under Option B).
- `.claude/skills/editor-launchers/SKILL.md` — the cache column; the
  port-8842 entry.
- `avatar_editor/README.md`, `frame_blender/README.md` — file tables
  after Steps 15–16.
- `HANDOFF.md` — a dated entry summarising what this plan closed.
- **This file** — mark each step `✅ done <date>` as it lands, so the
  next reader knows where the plan stands.

---

## Compliance checklist — finding → step

Every finding from the third-pass review, and the step that closes it.

| # | Finding | Severity | Closed by |
|---|---|---|---|
| 1 | 15 unreachable handlers, 930 lines (36%), in `mp4_splitter/serve.py` | High | Step 3 |
| 2 | 4 unreachable handlers, 207 lines, in `segment_avatar_editor/serve.py` | High | Step 4 |
| 3 | No test can see unreachable handler bodies — suites only assert routes 404; and a call-site diff is not enough, dead code calling dead code looks alive | High | Steps 1–2 |
| 4 | ~78 of Avatar Editor's 173 checks are source-text greps (45%); "210 checks" is inflated | High | Steps 7, 9 |
| 5 | Avatar Editor packs ~10 checks/step; failures hard to locate | Medium | Step 8 |
| 6 | MP4 Splitter has no README | Medium | Step 5 |
| 7 | SAE has no README | Medium | Step 6 |
| 8 | `paths.py` byte-identical ×3; `frames.py` near-identical; `serve.py` mp4/sae 88% identical | High | Step 10 → 11a/11b |
| 9 | `_splitter_player.py` is 99% identical to `mp4_splitter/player.py` | High | Step 10 → 11a/11b |
| 10 | Avatar Editor and Frame Blender each import 13 symbols from the legacy `shared/serve.py`; the two pairs made opposite trade-offs | Medium | Step 10 → 11a/11b |
| 11 | `mp4_splitter/player.py` builds the page as a 1,568-line Python string | High | Step 12 |
| 12 | `segment_avatar_editor/player.py` builds two pages as a 3,966-line Python string | High | Step 13 |
| 13 | `gap-builder.js` — 21 mutable globals written from 25 functions | Medium | Step 14 |
| 14 | `gap-builder.js` — 8 jobs in one 1,155-line file | Medium | Step 15 (after 14) |
| 15 | `frame_blender/web/app.js` — 765 lines, no split | Low | Step 16 |
| 16 | Avatar Editor and Frame Blender share one `cache/` directory | Low | Step 17 |
| 17 | No linter or formatter config in the repo | Low | Step 18 |
| 18 | Every count/claim in `CLAUDE.md`, `tests/README.md`, the skills | Low | Steps 9, 19 |

**What the review found that is NOT in this plan, on purpose:**

- Comment density (25–40%, "why" not "what") — a strength. Keep it.
- Zero `TODO`/`FIXME` inline — a strength. Keep it; open work stays in
  `ToDo.md`/`HANDOFF.md`.
- The `safe_join` / `safe_join_sarah` path guards and the checks that
  try to break them — correct as they are.
- `build/assemble_video.py`'s stale `REST_POSE` path — real, known, and
  off-limits by standing instruction. Tracked in the `sarah-library`
  skill, not here.

---

## Suggested sequencing for a session

If picking this up cold, this is the order that gives the most safety
per hour:

1. **Session 1** — Steps 1–2 (guard, watch it fail), 3, 4. Three
   commits. Everything after this is safer.
2. **Session 2** — Steps 5, 6, 7, 8, 9. The suite becomes honest;
   the numbers in the docs match reality.
3. **Session 3** — Step 10, the decision, then whichever of 11a/11b.
   Several tasks, one editor each.
4. **Session 4** — Step 12 (MP4 Splitter's page). Prove the pattern.
5. **Session 5** — Step 13 (SAE's two pages). The big one.
6. **Session 6** — Steps 14, 15, 16, 17, 18, 19.

Nothing in Sessions 1–2 changes what any editor does. Nothing after
Session 2 should be started without Sessions 1–2 done.
