# Editor test

Runs every function the **Segment and Avatar Editor** offers against a
disposable store built from real footage, and asserts an exact frame count
after each one.

```bash
cd .claude/agent-tools/6_end-customer-help-video-creations/video_players
python3 tests/test_editor.py
```

141 checks in 35 steps — one per endpoint, plus the behaviour steps that
cross several: alpha survival, cache locking, the join's gap filler.
About 90 seconds cold, 30 warm. Exit code is non-zero if any fail.

Every run writes a log next to the test:

```
tests/log_reports/editor_<HH>_<MM>_<SS>.log
```

Same shape as the E2E run logs — a header, the steps with a tick per check, then
a recap and a `Result: PASS` / `FAIL` verdict. Gitignored, like those are.

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
```

Same base filename for both — only the extension differs. The `.log` is the
same text the terminal showed, step by step. The `.txt` report is the short
version: total run, total passed, every step's own PASS/FAIL, and — only
when something failed — a `Failures:` section naming exactly which check
and what it found. Both are written by `fixture.write_report()`, shared
across all four so the shape can't drift between them. Gitignored, like
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
| open one clip / layered / timeline | `/api/open`, `/api/open-pair`, `/api/open-seq` (+ both `-go` redirects) |
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
