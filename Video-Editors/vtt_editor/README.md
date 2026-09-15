# VTT Editor — v2

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
    SEGMENT FRAME DUPLICATOR   scene 3 · 18.00s · frame 78
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
| frame duplicator | nothing owned it — see below |

A second copy of an ffmpeg recipe is a second copy to get wrong.

---

## v2 — the Segment Frame Duplicator

Carson, 2026-09-15: *"add another panel like this one, called SEGMENT FRAME
DUPLICATOR and add 4 buttons to duplicate the trackers current image with the
05 x / 10 x / 20 x / 50 x buttons."*

Four buttons. Each freezes the frame under the playhead and adds that many
copies of it, so **one screen gets longer where you are looking**:

    05 x  +0.20s      20 x  +0.80s
    10 x  +0.40s      50 x  +2.00s        (at 25 fps)

**That is the difference from a Stretch.** `stretch_scenes.py` spreads
duplicated frames across every part of a segment on purpose, so the screen
slows rather than stalling. This parks on one frame deliberately — the
targeted version of the same fix, for when one state needs reading time.

⚠ **IT WRITES THE CACHED CUT IN `segments/`, IN PLACE.** Carson's call, asked
outright: that is the file the scene strip and the table already read, and
`sandbox/` was 0 of 44 on the folder he had open, so a panel aimed there would
have arrived greyed out. The filename is unchanged on purpose — the cache key
IS the name, so promote and build keep finding it.

⚠ **EVERY PRESS BACKS THE OLD CUT UP FIRST**, into
`segments/z_History/<stamp>/`, and the new file is only moved into place as the
last step — so a failure anywhere leaves the segment exactly as it was. That
backup is why these four have **no two-click arm**: an undoable button pressed
ten times in a row must not ask twice.

⚠ **FRAMES, NOT SECONDS — AND THAT IS NOT A DETAIL.** The first build cut a
head, wrote a still, looped it and concat-demuxed the three, copying
`cut_with_holds`. It was wrong: `-ss` placed BEFORE `-i` is a KEYFRAME seek, so
the still came from a keyframe rather than the frame on screen, and the tail
resumed somewhere else again. `select` + `loop` in one filter graph indexes
frames by NUMBER, so there is nothing to seek inexactly.

⚠ **AND A REAL UI SCREEN CANNOT SHOW YOU THAT FAULT.** Between two frames of a
sign-in page almost nothing changes, so every frame "matches" every other and
the bug hides. It was caught against a NUMBERED synthetic clip — `testsrc`,
40 frames, +5 at frame 12 — where the answer is checkable:

    0..11, 12,12,12,12,12,12, 13..39      frame 12 six times, 40 in, 45 out

⚠ **`loop=loop=N` YIELDS N+1 COPIES**, so the filter is built with
`copies - 1`. Measured on that same clip, not read off the docs: `loop=5` added
six frames.

⚠ **THE REPORT MOVES WITH THE FILE.** `job_state` reads each scene's length
from `stretch_report.json`, never from the segment — so a longer cut with an
unchanged report leaves the clip, gap and frames columns quietly showing the
old numbers, and the gap is the column this button exists to close. The new
length is MEASURED back off the file with ffprobe, so the two cannot drift. It
is written with `indent=1, ensure_ascii=False` — the exact shape
`stretch_scenes.py` and `stretch_request.py` use, because the report is TRACKED
and `indent=2` reformatted all 494 lines for one changed number.

⚠ **THE PLAYHEAD HAS TO BE INSIDE THE SELECTED SCENE.** The row shows the
scene, the time and the frame number *before* you click, and the four buttons
disable themselves when the scrub has been dragged out of the scene — freezing
scene 8's frame into scene 3 is a silent wrong answer rather than an error. On
a stretched scene the capture time is mapped through the factor
(add-collection's scene 2 is x1.0651: capture 10.00s → segment frame 50).

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
