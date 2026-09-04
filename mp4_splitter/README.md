# MP4 Splitter

Open one raw recording, mark the break points, and cut it into numbered
segments — the first step of every help video, before anything is
layered or narrated.

```bash
python3 mp4_splitter/serve.py          # http://localhost:8845
```

Standalone — nothing else needs to be running. Its own process, its own
port, its own extracted-frame cache (`cache_mp4_splitter/`, not the
shared `cache/`), and its own copies of `frames.py` and `paths.py`.
Split off `shared/serve.py` on 2026-09-02 at Carson's request: MP4
Splitter and the Segment and Avatar Editor used to share one process on
port 8842, and he asked for the two to be genuinely independent, code
and all, so a change to one can never break the other.

## What's in here

| | |
|---|---|
| `serve.py` | the server and every route. Stateless: each request names what it acts on |
| `player.py` | the viewer page — see the warning below |
| `frames.py` | frame extraction, the frame map, the edit maths. **A copy** of `shared/frames.py`, not an import |
| `paths.py` | where a store's folders are. **A copy**, and currently byte-identical to `shared/`'s |
| `VERSION` | bumped on every commit that changes what this tool does — its own history, not another editor's |

There is no `web/` folder here, and that is the one thing worth knowing
before editing this tool. See below.

## ⚠ The page is a Python string, not files

`player.py` builds the entire viewer — HTML, CSS and JavaScript — as one
`TEMPLATE` string rendered with `str.format()`. That carries two traps
this project has already paid for, both documented in `CLAUDE.md`:

- **Every CSS and JS brace must be doubled** `{{ }}`, or `.format()`
  eats it.
- **A stray apostrophe in a single-quoted JS string kills the whole
  page silently** — every control dies, including Play. Use a backtick
  literal.

So: **always check the generated JavaScript, not just that the Python
parses.** The suite's last step does exactly that (`node --check` on the
rendered page) and is the only thing standing between a broken page and
a silent ship. Do not drop it.

Avatar Editor and Frame Blender moved off this pattern on 2026-08-30 to
plain `web/*.js` files. This tool has not yet — it is Step 12 of
`README-CODE-CLEANUP-PLAN.md`, and that plan describes the migration
using those two as the worked example.

## What it serves

`/browse.html` is the folder browser, rooted at `Customers/`. The rest:

```
/api/list          browse a folder          /api/mark, /api/marks,
/api/open          open a clip               /api/clear-marks   marking
/api/frames/map    read the frame map       /api/cut       cut at the marks
/api/frames/dup    ＋ Frame                  /api/save      overwrite the source
/api/frames/del    − Frame                  /api/clear-edits  discard edits
/api/frames/restore  Undo                   /api/reset-editor  unload it
/api/handoff       deposit into dev/        /api/archive   generation archive
```

`serve.py`'s own module docstring documents each one properly, including
the distinction between `/api/cut` (slices at marks into a new versioned
file, never touches the source) and `/api/save` (rebuilds the whole clip
and overwrites the source, archiving it first). Read that before
changing either.

Every `path` is relative to `Customers/` and is checked to stay inside
it — `..` cannot walk out. Every `slug` is checked the same way against
the frame cache.

## ⚠ Routes that were dropped are gone entirely — keep it that way

The 2026-09-02 split removed the SAE-only routes from the dispatch
tables but left their handler bodies behind. **15 unreachable methods,
930 lines, 36% of `serve.py`**, plus 5 module-level helpers only they
used. Every test passed the whole time, because a route with no dispatch
entry 404s exactly like a route whose handler was deleted.

Removed 2026-09-03. What stops it recurring is
`fixture.dead_handlers()`, which walks out from `do_GET`/`do_POST` and
fails the suite on anything it cannot reach — Step 21 of this tool's
suite. If you delete a route, delete its handler in the same commit.

## Tests

```bash
python3 tests/test_mp4_splitter.py
```

83 checks in 21 steps, against a disposable store built from real ski-demo
footage — real VP9-with-alpha files, because a synthetic clip would hide
the thing that actually bites (plain `ffprobe` reports alpha WebM as
`yuv420p` unless the decoder is forced). It builds the store, uses it,
and deletes it; it never touches a real one.

Each run writes both a full transcript and a pass/fail report:

```
tests/mp4_splitter/mp4_splitter_<HH>_<MM>_<SS>.log
tests/mp4_splitter/mp4_splitter_<HH>_<MM>_<SS>.txt
```

Every assertion is an exact decoded frame count. Every real bug this
family of tools has had was an off-by-a-frame that still produced a
playable file.

## Changing this tool — the commit rules

1. **One player per commit.** Never two. Shared code is its own commit.
2. **Bump `VERSION`** in the same commit — it renders at the foot of the
   page, so the version on screen is the version in git.
3. **Subject:** `MP4 Splitter v<N> ADDED: <what it does now>`

Write what the tool *does now*, not what you edited. `ADDED:` is the
form even when the change is a fix. **A restructure is not an `ADDED:`**
— commit that plainly and leave `VERSION` alone.
