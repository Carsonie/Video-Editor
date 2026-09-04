# The test suites

Six of them. Five drive a real server over HTTP against a disposable store
built from real footage; the sixth has no server in it.

```bash
python3 tests/test_editor.py                 # shared/serve.py, port 8842 (old combined) — 166
python3 tests/test_avatar_editor.py          # avatar_editor/serve.py, port 8844          — 173
python3 tests/test_segment_avatar_editor.py  # segment_avatar_editor/serve.py, port 8846  — 107
python3 tests/test_mp4_splitter.py           # mp4_splitter/serve.py, port 8845           — 102
python3 tests/test_frame_blender.py          # frame_blender/serve.py, port 8843          —  71
python3 tests/test_editor_base.py            # editor_base/ — pure functions, no server   —  57
```

676 checks. Exit code is non-zero if any fail.

**A change inside `editor_base/` runs all six, not one.** That is the trade
the shared package makes: it is imported by every editor, so a change there
is not one editor's change.

`test_editor.py` is the deepest — one step per disk function, about 90
seconds cold, 30 warm. `test_editor_base.py` is the odd one out: it boots
nothing, because `editor_base/` has no server in it. Testing it through an
editor would only prove that one editor's use of it works.

Every run writes a log and a report into the suite's own folder — see
"The four standalone editors have their own folders" below.

## Three things only the BROWSER can see

Worth stating plainly, because all three shipped in one day while the
suites stayed green. Every check here drives HTTP, so a page can be
completely dead while the server answers perfectly.

1. **A truncated script.** An extraction bug cut `mp4_splitter/web/app.js`
   short by 40 lines, taking `show(1)` and the whole init block with it.
   101/101 passed; the page drew nothing.
2. **A route serving the wrong page.** The SAE's `send_viewer()` swallowed
   `/<slug>/base/viewer.html` and returned the layered page (itself since
   deleted). 91/91 passed,
   because the only check on that page scraped `<script>` out of the HTML
   and the new static page has none — an empty string parses fine.
3. **A load-order forward reference.** `timeline.js` assigned `pickStores`
   as an onclick at load time, and that function moved to a file loaded
   later. Function declarations hoist within a file, not across `<script>`
   tags. 65/65 passed; the page threw on every load.

Two of the three now have permanent guards (`s_single_clip_page_still_works`,
`s_load_order_forward_refs`). The first does not, and probably cannot.
**So: open the tool in a browser after any change to a page.** A green
suite is not the same as a working page.

## What a check is allowed to assert

A check must drive the server and assert a real result. It must not
assert that a line of source code is spelled a particular way.

That distinction was not always kept. Avatar Editor's suite reached 210
checks of which ~79 were source-text greps — asserting that a string
like `const DELAY = 3000;` appeared in the served JavaScript. Such a
check passes when the feature is broken and fails when a variable is
renamed, so it reports the opposite of what it looks like it reports.
Two of them asserted exact whitespace and indentation. They were removed
2026-09-03; the suite went 211 -> 141 checks (165 today,
after real behavioural steps were added back) and became worth its
number.

Three narrow exceptions are allowed, and they are all CONTRACTS rather
than spelling:

- **Element ids.** Every id the page's JavaScript looks up must exist in
  the served HTML. Break one and that panel dies silently.
- **Absence assertions.** "This removed control has not come back",
  "we did not go back to `window.prompt`", "Clear All does not touch
  PICKED". Nothing else can see these regressions.
- **`node --check` on the served pages.** Two editors still build their
  pages as Python strings, where a stray apostrophe kills the page at
  render time; this is the only guard against it.

Anything else that cannot be reached over HTTP — a tooltip appearing
after three seconds, a picture stepping with a voice — is browser
behaviour. This suite cannot test it. Say so in a comment and leave the
gap visible; do not paper over it with a grep.

Frame Blender's suite was the model at 50 checks, almost all behavioural;
it is 71 now, after its own page split added a load-order guard.

## The four standalone editors have their own folders, own logs, own reports

`test_avatar_editor.py`, `test_frame_blender.py`, `test_mp4_splitter.py` and
`test_segment_avatar_editor.py` are separate suites for the four genuinely
independent editor processes (each its own port, cache and code — see each
editor's own README for why). Since 2026-09-03 each writes its own run's
output into its own folder, never a shared one:

```
tests/avatar_editor/avatar_editor_<HH>_<MM>_<SS>.log            # the full transcript
tests/avatar_editor/avatar_editor_<HH>_<MM>_<SS>.txt            # the pass/fail report
tests/frame_blender/frame_blender_<HH>_<MM>_<SS>.{log,txt}
tests/mp4_splitter/mp4_splitter_<HH>_<MM>_<SS>.{log,txt}
tests/segment_avatar_editor/segment_avatar_editor_<HH>_<MM>_<SS>.{log,txt}
tests/editor_base/editor_base_<HH>_<MM>_<SS>.{log,txt}
```

Same base filename for both — only the extension differs. The `.log` is the
same text the terminal showed, step by step. The `.txt` report is the short
version: total run, total passed, every step's own PASS/FAIL, and — only
when something failed — a `Failures:` section naming exactly which check
and what it found. Both are written by `fixture.write_report()`, shared
across all five so the shape can't drift between them. Gitignored, like
`test_editor.py`'s own `tests/log_reports/`.

## The other log — real editing

The test's log is one run of a fixture. The editor keeps its own log of what you
actually do to your files, written by the server as you work:

```
video_players/logs/editor_<YYYYMMDD>.log
```

One file per day, appended, with a header each time the server starts. One line
per action that changes something — plus the clip you opened, which is what
makes the edits under it readable — and refusals too. The server prints the path
when it starts.

The test's server runs with `--no-session-log`, so a test run never appears in
it.

| flag | what it does |
|---|---|
| `--keep` | leaves the store and the server up, to click through the UI yourself |
| `--port N` | use another port (default 8850, so it never fights the editor on 8842) |

## It never touches a real store

`fixture.py` builds `Customers/_Editor_Test/` from scratch, and the test
deletes it at the end. That is not politeness — every function worth testing
**writes**: Save overwrites a segment, Cut replaces it, Join deletes the
folders it consumed, Split deletes the scene it cut in two. Pointed at
ski-demo those are real edits to a finished video, and the `z_History` archive
makes them recoverable, not harmless.

The store has to live under `Customers/` because `serve.py`'s `safe_join()`
resolves every path under `CUSTOMERS_ROOT` and returns `None` for anything
outside it. A fixture anywhere else is unreachable by the endpoints under test.
It is gitignored.

### The clips are real, short, and deliberately mismatched

Cut from ski-demo's scene 1, at 40/32/25 frames rather than the 200+ a real
scene runs — the test re-encodes them dozens of times.

Real footage, not `testsrc`, because of the trap the synthetic file would hide:
a real avatar track is **VP9 with alpha**, and plain `ffprobe` reports those as
`yuv420p` unless the decoder is forced with `-c:v libvpx-vp9`. A green test on
a synthetic clip would prove nothing about the files this tool is for.

The three tracks are different lengths on purpose. A segment longer than its
avatar is the normal state of a real scene, it is what "Update Frame Imbalance"
exists for, and a split point valid in one track but past the end of another is
what the split's pre-flight check has to refuse.

## Why every assertion is a frame count

Every real bug this tool has had was an off-by-a-frame that still produced a
**playable file**. Save wrote 87 frames for an 89-frame edit for three weeks
without erroring, because `-t` drops the frame that lands on the boundary.
Nothing crashed. The video was just wrong.

So no check here asserts "the file exists" or compares a duration. Each one
decodes the file and counts.

## One step per function

The log names all 26 disk functions as their own step. They were grouped into
10 before, and the log then showed "Frame edits" as a single green tick
covering five different functions — a report that cannot say WHICH function ran
is not a report.

## What is covered

| Editor control | Endpoint |
|---|---|
| browse to a clip | `/api/list`, `/api/siblings` |
| open one clip / timeline | `/api/open`, `/api/open-seq` (+ its `-go` redirect) |
| ＋ Frame, − Frame | `/api/frames/dup`, `/api/frames/del` (both sides) |
| ＋ Zone, − Zone | `/api/frames/dup-span`, `/api/frames/del-span` |
| Undo | `/api/frames/restore` |
| Mark / Unmark, Unmark all | `/api/mark`, `/api/marks`, `/api/clear-marks` |
| 💾 Save scene, per-row Save | `/api/save` |
| ✂ Cut scene | `/api/cut` |
| discard edits, reset | `/api/clear-edits`, `/api/reset-editor` |
| Join (all tracks) | `/api/join` |
| Split (all tracks) | `/api/split` |
| the save-as-a-set lock | `/api/renumber-state`, `/api/renumber-clear` |
| the VTT panel | `/api/vtt` |
| editing a line in the VTT | `/api/line` |

Plus the refusals, which matter as much as the successes: a path outside
`Customers/`, a slug containing a separator, a side that is neither left nor
right, a join of fewer than two scenes, a name that is not a slug, two split
halves with the same name, a split frame past the shorter track, and a line for
a scene that is not in the script. The split refusal also asserts that **no
archive is left behind** for a split that never ran.

**"Update Frame Imbalance"** is covered through `/api/frames/dup-span`, which is
what it calls to pad the shorter track.

## What it cannot cover

It drives HTTP, not the browser. The purely visual controls own no state on
disk and are out of scope by construction:

Play, the speed dropdown, Loop Zone, Solo, the layer toggle, the border
colours, the tooltips, and the VTT's follow-the-playhead highlight.

Use `--keep` and open the editor against `_Editor_Test` to check those by eye.

## If a check fails

Read the **first** failure, not the list. The checks share state on purpose —
they run in the order the work happens — so one broken call cascades.

The first version of this test learned that the hard way: it called `post()`
and ignored the answer, a `400` for a bad `side` value passed silently, and the
next five assertions each failed looking like a different bug. Every setup call
now goes through `must()`, which insists the call worked before anything is
asserted about its effect.
