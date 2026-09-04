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
the shared `cache/`), its own routes and its own pages. Split off
`shared/serve.py` on 2026-09-02 at Carson's request: this tool and MP4
Splitter used to share one process on port 8842, and he asked for the two
to be genuinely independent, code and all.

The one thing it does share is `editor_base/` — frame extraction, path
shapes and the VTT word count, imported rather than copied since
2026-09-03. Those three files had existed in triplicate. See `CLAUDE.md`,
"The one exception: editor_base/".

## What's in here

| | |
|---|---|
| `serve.py` | the server and every route. Stateless: each request names what it acts on |
| `web/pair.html` `.css` `.js` | the layered page, shipped **empty** — see below |
| `web/seq.html` `.css` `.js` | the timeline page, shipped **empty** |
| `player.py` | 134 lines: writes each view's `view.json`. No pages in it |
| `_splitter_player.py` | a private copy of MP4 Splitter's viewer — see below |
| `VERSION` | bumped on every commit that changes what this tool does |

Frame extraction, path shapes and the VTT word count are in
`editor_base/`, imported — not copied here.

### Two pages, and they ship empty

- **`web/pair.*`** — the layered view: one scene, mp4 underneath, alpha
  WebM on top, each track independently editable.
- **`web/seq.*`** — the timeline: several scenes joined, so the
  *boundaries* can be judged. A scene on its own cannot show the thing
  that most often goes wrong — how one scene joins the next.

Two pages rather than one, because they were two templates for a reason:
they share the tools but not the span. They share nothing but `serve.py`.

**No view is baked into either.** `player.py`'s `write_pair()` and
`write_seq()` write a small **`view.json`** into the cache folder, and
the page fetches it back over `GET /api/view?slug=…` before it draws
anything. One endpoint for both, because the page does not choose which
kind it is: `kind` in the answer says so, and `send_viewer()` has already
sent the matching page.

**Why a file and not a rebuild from `meta.json`.** Most of what a view
needs cannot be recovered afterwards. `base_rel` and `overlay_rel` are
handed in when a pair is opened; the timeline's `manifest`, mapping every
global frame to (scene, local frame), is built at open time and exists
nowhere else. A rebuild would have to guess them, so the open writes them
down.

### ⚠ Three pages live under one cache folder

A pair's cache holds **three** `viewer.html` paths, not one:

```
/<slug>/viewer.html            the layered page      (static, web/pair.*)
/<slug>/base/viewer.html       that scene on its own (_splitter_player.py)
/<slug>/overlay/viewer.html    the overlay on its own
```

`serve.py` routes **exactly two path segments** to the static page. The
first version of that route matched `path.endswith("/viewer.html")` and
swallowed all three, serving the layered page for every one — and **the
suite passed**, because its only check on those pages scraped `<script>`
out of the HTML, and the new static page has none, so it handed
`node --check` an empty string. `s_single_clip_page_still_works` now
pins this down; reintroducing the bug fails four checks.

### ⚠ A cache written before 2026-09-04 has no `view.json`

Those still hold a fully baked `viewer.html`, and nothing can rebuild a
view for them — the manifest and the relative paths only ever existed at
open time. `send_viewer()` falls through to the old page for those, so
they keep working. Re-open the pair or the timeline and the new page
takes over.

### What this replaced

`player.py` was **3,966 lines** — the largest file in this repo — almost
all of it two `str.format()` strings, `PAIR_TEMPLATE` (733 lines) and
`SEQ_TEMPLATE` (3,225), each holding a whole page. Every CSS and JS brace
had to be doubled `{{ }}`, no editor could lint or highlight any of it,
and a stray apostrophe killed the page at **render** time rather than at
edit time. It is now 134 lines.

**Keep the `node --check` guard, and note it is no longer uniform.** The
two static pages are parsed as real files (`/web/pair.js`, `/web/seq.js`);
the single-clip page is *still* a Python template, so that one is still
scraped out of the served HTML. Scraping the static pages would find
nothing and pass on an empty string.

### `_splitter_player.py` is a deliberate duplicate

The SAE's "open this scene on its own" link needs MP4 Splitter's single-
clip viewer. Rather than import another editor's package — which the
2026-09-02 split exists to prevent — a copy lives here.

It was 99% identical to `mp4_splitter/player.py` — 16 differing lines out
of ~1,570 — but that comparison is now out of date in a way that matters:
MP4 Splitter's `player.py` was migrated to static files on 2026-09-04 and
is 66 lines. **This file is the last Python-string page in the repo**, and
it no longer duplicates anything.

De-duplicating it was deliberately deferred rather than skipped; the
reasons are written up under Step 11a.8 in
`README-CODE-CLEANUP-PLAN.md`. In short: `editor_base/` may not hold page
rendering, and folding a player in would re-link two tools the 2026-09-02
split separated on purpose.

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
