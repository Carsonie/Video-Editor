# VTT Editor — v1

The **first edit** on a raw capture, in one place.

    python3 vtt_editor/serve.py            # http://localhost:8848

Or from `Basic_E2E_Testing/.claude/launch.json`, as `vtt-editor`.

---

## What it is for

Carson, 2026-09-15: *"This will be the first edit on the raw video and will do
the following things: Add the yellow rings to the click event triggers. Break
the raw into our segments. Into the scenes. Add some descriptive narrative. And
add the voice."*

Five jobs, one rail. Each row shows its own state, so the page answers *where am
I* without a click:

    RINGS       28 rings · 22 click, 6 typing · border-only
    SEGMENTS    21 of 21 scenes cut · 27 cached cuts
    SCENES      21 of 21 in sandbox/
    NARRATIVE   21 lines · 490 words · every screen fits
    VOICE       380.04s · 1 rushed          collection-list 185 wpm

The left edge of each row carries the verdict — green done, amber owed, grey
cannot run.

## What it does NOT do

**It does not re-implement anything.** Every job shells out to the tool that
already owns it, where the edge cases are written down:

| job | the tool behind it |
|---|---|
| rings | the recorder's own click log (`clickPace.ts`) |
| segments | `stretch_scenes.py` — cuts from CONFIRMED edges, caches in `segments/` |
| scenes | `editor_base/paths.py` — it owns the sandbox layout |
| narrative | `script.json` + `vtt_build.py`, which refuses on a mismatch |
| voice | `stretch_request.py` → `narrate_mac.py` |

A second copy of an ffmpeg recipe is a second copy to get wrong.

---

## The rules it is built around

⚠ **IT NEVER TOUCHES THE MASTER.** Every job writes NEW files beside it. The
master is what every later generation is cut from, and this repo has already
lost one.

⚠ **A JOB THAT CANNOT RUN SAYS WHY.** `/api/state` returns a `blocked` string
per job and the row shows it. Never hidden, never live-but-dead. The history
here is long enough to design against: a `confirm()` that returned false
silently in a sandbox, a Publish left enabled with no handler in a read-only
view, a Stretch offered against a stale table.

⚠ **THE SERVER READS EVERY NUMBER OFF DISK, ON EVERY REQUEST.** Nothing is
remembered between them — same rule as `avatar_editor` since the 2026-08-30
restructure, and the reason a stale table cannot offer a job that no longer
makes sense.

⚠ **A LINE SAVES ON A DEBOUNCE AS WELL AS ON BLUR.** Found by testing: `blur`
did not fire at all when the page was driven from a browser pane without window
focus, so an edit sat in the DOM unsaved with no error. And worse — a finished
job calls `refresh()`, which re-renders the table; anything half-typed went with
it. So typing saves itself after 900ms, and `render()` refuses to rebuild the
rows while a line has focus.

⚠ **A SCREEN IS "SHORT" ONLY BY MORE THAN 0.05s.** A raw `clip < need` flagged
add-collection's `item-saved` as short by `+0.0s` — true to two decimals and
meaningless. A row that says "too short by 0.0s" teaches you to ignore the
column that matters.

⚠ **THE RINGS ARE ALREADY IN EVERY CAPTURE.** Border-only, 750ms, drawn live by
the recorder — Carson, 2026-09-09: *"we will only use the rings from now on.
Looks better."* What did not exist until 2026-09-15 is any RECORD of them. A
capture from before that has no log, and the row says so rather than showing an
empty panel that reads as broken.

⚠ **A LOGGED RECT IS CSS PIXELS OF THE PAGE, NOT PIXELS OF THE VIDEO.** The
capture is a cropped window region on a scaled monitor. The log's header carries
the window region and the chrome crop; the transform happens in the page, where
the rendered frame's own size is also known. Multiplying by a guessed ratio is
how a ring lands near the right place and never on it.

---

## It replaced `serve_vtt.py`

Carson's call, 2026-09-15, when asked what happens to the three surfaces that
had grown to edit narration:

- **`Recorder/scripts/serve_vtt.py` — gone.** One writer too many: it and an
  artifact page could both hold `script.json` open, and on 2026-09-14 it was
  left running after being reported stopped. Its `vtt-live` launch entry (8847)
  went with it.
- **The artifact page — stays.** It is the one that opens anywhere.
- **The SAE's own EVTT panel — stays.** It covers a BUILT video's `sandbox/`,
  a different stage.

## Layout

    serve.py          the server and its job endpoints
    web/index.html    the rail, the frame, the scene strip, the table
    web/vtt.css       the look — dark ground, three colours, three meanings
    web/vtt.js        the behaviour
    VERSION           1

Cache: `Video-Editors/cache/vtt_editor/` — one folder per capture, frames by
time. Session log: `Video-Editors/logs/vtt_editor_<date>.log`.
