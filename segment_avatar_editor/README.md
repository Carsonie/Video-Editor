# Segment and Avatar Editor

One scene's footage with its alpha avatar laid over it — or several
scenes on a timeline, to judge how they join. Frame and zone edits,
marks, Save, Cut, Join, Split, and the VTT panel where a scene's
narration line is edited in place.

```bash
python3 segment_avatar_editor/serve.py          # http://localhost:8846
```

Standalone — nothing else needs to be running. Its own process, its own
port, its own extracted-frame cache (`cache_segment_avatar_editor/`, not
the shared `cache/`), and its own copies of `frames.py`, `paths.py` and
`vtt.py`. Split off `shared/serve.py` on 2026-09-02 at Carson's request:
this tool and MP4 Splitter used to share one process on port 8842, and
he asked for the two to be genuinely independent, code and all.

## What's in here

| | |
|---|---|
| `serve.py` | the server and every route. Stateless: each request names what it acts on |
| `player.py` | **both** pages — see below |
| `_splitter_player.py` | a private copy of MP4 Splitter's viewer — see below |
| `frames.py` | frame extraction, the frame map, the edit maths. **A copy** of `shared/frames.py`, not an import |
| `paths.py` | where a store's folders are. **A copy**, currently byte-identical to `shared/`'s |
| `vtt.py` | the Video Timing Table — clip length vs. how long the line takes to say |
| `VERSION` | bumped on every commit that changes what this tool does |

### `player.py` builds two pages, not one

- **`PAIR_TEMPLATE`** — the layered view: one scene, mp4 underneath,
  alpha WebM on top, each track independently editable.
- **`SEQ_TEMPLATE`** — the timeline: several scenes joined, so the
  *boundaries* can be judged. A scene on its own cannot show the thing
  that most often goes wrong — how one scene joins the next.

They are one file because they edit the same two layers with the same
tools; only the span differs. At 3,966 lines it is the largest file in
this repo, and splitting it is Step 13 of
`README-CODE-CLEANUP-PLAN.md`.

### `_splitter_player.py` is a deliberate duplicate

The SAE's "open this scene on its own" link needs MP4 Splitter's single-
clip viewer. Rather than import another editor's package — which the
2026-09-02 split exists to prevent — a copy lives here.

**It is 99% identical to `mp4_splitter/player.py`: 16 differing lines
out of ~1,570.** That is a copy, not a divergence, and it is a known
open question rather than a settled design — Step 10 of the cleanup
plan is the decision about it. Until that is answered, a fix made in
one must be considered for the other by hand; nothing enforces it.

## ⚠ The pages are Python strings, not files

Both templates build HTML, CSS and JavaScript as `str.format()` strings.
Two traps, both already paid for and both in `CLAUDE.md`:

- **Every CSS and JS brace must be doubled** `{{ }}`.
- **A stray apostrophe in a single-quoted JS string kills the whole page
  silently.** Use a backtick literal.

**Always check the generated JavaScript, not just that the Python
parses.** The suite's Step 32 runs `node --check` on all three of this
tool's pages and is the only thing standing between a broken page and a
silent ship. Do not drop it.

Avatar Editor and Frame Blender moved off this pattern on 2026-08-30 to
plain `web/*.js` files; those two are the worked example for Step 13.

## ⚠ Routes that were dropped are gone entirely — keep it that way

The 2026-09-02 split removed the Splitter-only routes from the dispatch
tables but left their handler bodies behind: **4 unreachable methods,
211 lines**, plus a stale branch in `session_log()` formatting a line
for `/api/open`. Every test passed the whole time, because a route with
no dispatch entry 404s exactly like a route whose handler was deleted.

Removed 2026-09-03. What stops it recurring is
`fixture.dead_handlers()`, which walks out from `do_GET`/`do_POST` and
fails the suite on anything it cannot reach — Step 33 of this tool's
suite. If you delete a route, delete its handler in the same commit.

## Tests

```bash
python3 tests/test_segment_avatar_editor.py
```

91 checks in 33 steps — roughly one step per endpoint, which is why a
failure here points straight at the cause instead of needing a read.
Built against a disposable store made from real ski-demo footage (real
VP9-with-alpha, because a synthetic clip would hide the alpha-reporting
trap), used, then deleted. It never touches a real store.

Each run writes both a full transcript and a pass/fail report:

```
tests/segment_avatar_editor/segment_avatar_editor_<HH>_<MM>_<SS>.log
tests/segment_avatar_editor/segment_avatar_editor_<HH>_<MM>_<SS>.txt
```

Every assertion is an exact decoded frame count. The refusals are tested
as carefully as the successes — a split point past the shorter track, a
join of fewer than two scenes, two split halves with the same name — and
the split refusal also asserts that **no archive is left behind** for a
split that never ran.

## Changing this tool — the commit rules

1. **One player per commit.** Never two. Shared code is its own commit.
2. **Bump `VERSION`** in the same commit — it renders at the foot of the
   page, so the version on screen is the version in git.
3. **Subject:** `Segment and Avatar Editor v<N> ADDED: <what it does now>`

Write what the tool *does now*, not what you edited. `ADDED:` is the
form even when the change is a fix. **A restructure is not an `ADDED:`**
— commit that plainly and leave `VERSION` alone.
