# MP4 Splitter

Open one raw recording, mark the break points, and cut it into numbered
segments — the first step of every help video, before anything is
layered or narrated.

```bash
python3 mp4_splitter/serve.py          # http://localhost:8845
```

Standalone — nothing else needs to be running. Its own process, its own
port, its own extracted-frame cache (`cache/mp4-splitter/`, not the
shared `cache/`), its own routes and its own pages. Split off
`shared/serve.py` on 2026-09-02 at Carson's request: MP4 Splitter and the
Segment and Avatar Editor used to share one process on port 8842, and he
asked for the two to be genuinely independent, code and all, so a change
to one can never break the other.

The one thing it does share is `editor_base/` — frame extraction, path
shapes and the VTT word count, imported rather than copied since
2026-09-03. Those three files had existed in triplicate and differed by
two lines of real code; both are now configuration this tool sets at
import time (`use_cache()`, `use_player()`). See `CLAUDE.md`, "The one
exception: editor_base/".

## What's in here

| | |
|---|---|
| `serve.py` | the server and every route. Stateless: each request names what it acts on |
| `web/index.html` | the clip page, shipped **empty** — no clip is baked into it |
| `web/app.css` | its styles. The clip's own size arrives as CSS custom properties |
| `web/app.js` | its behaviour, ~1,100 lines. Fetches `/api/clip` first, then runs |
| `player.py` | 66 lines: this player's name and version, and nothing else |
| `VERSION` | bumped on every commit that changes what this tool does — its own history, not another editor's |

Frame extraction, path shapes and the edit maths are in `editor_base/`,
imported — not copied here.

## The page is three static files, and it ships empty

`web/index.html`, `web/app.css`, `web/app.js` — plain files, served by
`serve.py`'s `send_web()` with `Cache-Control: no-store`.

**No clip is baked into any of them.** The fourteen values the page needs
arrive over `GET /api/clip?slug=…`, and `app.js` runs only once that has
answered. That endpoint IS the contract between the server and the page:
add a field in `serve.py`'s `api_clip()` and read it in `app.js`. There
is no third place to keep in step.

Two values could not simply become data:

- The clip's width and height drove four baked CSS numbers. Three are now
  custom properties (`--disp-w`, `--disp-h`, `--app-w`) set on the root
  element. The fourth is a **responsive breakpoint, and a `@media` query
  cannot read `var()`** — so `app.js`'s `applyLayout()` injects that one
  block itself with the real number.

### ⚠ Every clip's cache still holds a stale copy of the OLD page

Until 2026-09-04 `player.write()` rendered the whole page into
`<cache>/<slug>/viewer.html`, one baked copy per clip. Those files are
still on disk for every clip ever opened.

`serve.py` answers `/<slug>/viewer.html` from `web/index.html` and
**ignores whatever file is on disk**. That makes all of them correct at
once — no re-extraction, no migration pass. `player.write()` is now a
no-op that deliberately writes nothing, because anything it wrote would
be a stale copy nothing reads.

The suite pins this down (`s_stale_cached_pages`), because a fresh
fixture cannot show it: its caches are new, so the suite would pass while
months-old real caches served the old page.

### What this replaced, and why

`player.py` was 1,568 lines, almost all of it one `TEMPLATE` string
holding the HTML, the CSS and 1,018 lines of JavaScript, rendered with
`str.format()`. Every CSS and JS brace had to be doubled `{{ }}`, no
editor could lint or highlight it, and a stray apostrophe killed the page
at **render** time rather than at edit time. It is now 66 lines.

The extraction itself hit exactly that class of bug twice, which is the
best argument for having done it: slicing the template's *source text*
carried Python's own `\'` escape through into the JavaScript verbatim and
produced a syntax error, and reading line numbers off the source while
slicing the *evaluated* string silently truncated `app.js` by 40 lines —
taking the whole init block with it, while the suite stayed green.

**Keep the `node --check` guard.** It now fetches `/web/app.js` and parses
the real file, and asserts the page actually references it — a served file
nothing links to would otherwise pass.

Avatar Editor and Frame Blender moved off the Python-string pattern on
2026-08-30. The Segment and Avatar Editor has not yet; that is Step 13 of
`README-CODE-CLEANUP-PLAN.md`, and this tool is its worked example.

### One known rough edge

`HEAD /web/app.js` returns 404 while `GET` returns the file: `do_HEAD`
falls through to `SimpleHTTPRequestHandler`, which looks in the frame
cache and finds nothing. Nothing in this project issues a HEAD for these,
so it is recorded rather than fixed.

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
