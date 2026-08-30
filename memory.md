# memory.md — how this repo got here

A condensed history, not a task list — see `HANDOFF.md` for what's actually
open right now. This file exists so a later session (or Carson, six weeks
from now) can understand *why* things are shaped the way they are without
re-reading the whole conversation that produced them.

---

## The split that started it (2026-08-28)

`Video-Editor` didn't always exist as its own repo. Everything about
building a help video — both editors, the build tools, `PIPELINE.md`, every
store's working files — used to live inside `Basic_E2E_Testing` and had
drifted 26 versions out of sync with itself. Split into this repo the same
day: `Video-Editor` now holds all working material, `Basic_E2E_Testing`
holds only finished, released videos.

## bike-demo: proving the split works on a second store (2026-08-28)

ski-demo was the one store already built on the current pipeline. bike-demo
was still on the old flat `final/` layout with no per-scene avatar files at
all. Migrated it onto the same `dev/`/`sandbox/` shape ski-demo uses, built
its 11 missing avatar files locally (no HeyGen cost), and produced
`v2-full` — a rebuild matching the original `v1` release to within a
quarter of a second. Along the way, fixed a real bug in
`migrate_to_dev.py` (wrong `sys.path`, so it couldn't find `paths.py`) that
would have hit canoe-demo and alpine-sports too.

**Still open on this thread:** `v2-full` was never promoted to a proper
version number, and nothing's been released to `Basic_E2E_Testing` — v1 is
still what a customer sees. Full detail in `HANDOFF.md`.

## Frame Blender: from a diagnostic to a real tool (2026-08-29 → 2026-08-30)

Started as a narrow, single-purpose page: step through one scene's two
tracks (segment + avatar) frame by frame, built specifically to chase down
why ski-demo's scene 1 read as "out of sync" (turned out the background
track had a several-second blank stretch at its start). Its own module
docstring said, accurately at the time, "it has no buttons that write
anything."

That stopped being true over about a day of real use:

- The thumbnail grid and the new scrub slider were both capped at a fixed
  pixel width regardless of window size — fixed to use whatever's actually
  available.
- Added a real "Build" — a genuine one-pass ffmpeg build (picture + voice
  together, the same recipe `build_scenes.py` uses for a real release),
  reachable from a "Build (real speed)" option right in the frame-stepping
  speed dropdown, so stepping through frames and building the real thing
  live in the same control.
- Then it needed to **save** what it built, and to **know** whether a scene
  had already been changed by someone else — which meant it needed the same
  save path, and the same pristine/dirty signal, the Segment and Avatar
  Editor already has. Rather than duplicate either, `/api/save` grew a
  staleness check (refuses to overwrite a file that changed on disk since
  its cache was built, unless told `force`) and Frame Blender became a real
  second client of the SAME save/undo/dirty-state machinery, not a second
  implementation of it. A Timeline Scenes panel, and Clear/Load/Save MP4
  buttons, followed on top of that shared foundation.

**Two real bugs surfaced only because each piece was tested against a live
server, not just read as code** — full detail in `HANDOFF.md`'s 2026-08-30
section: an em-dash in any error message crashed the whole server outright
(`http.server`'s `send_error()` encodes as latin-1), and Save MP4's
versioning silently never incremented past `v1` because it asked a helper
for a bare filename to match against files that all had `.mp4` on them. A
third, smaller one — the Clear button only reset part of the page — was
found by Carson directly and fixed the same way: confirmed with a real
screenshot after a real click, not assumed from the diff.

Testing and logging grew alongside the feature, not after it: a new
`tests/test_frame_blender.py` (starts both servers for real) and 2 new
checks in the main suite; Frame Blender's own actions now write into the
same daily session log the main editor keeps, so there's one record of real
work regardless of which tool did it.

## The restructure, and why patching had to stop (2026-08-30, later)

Clear was reported broken a third time. Rather than patch it again, Carson
asked for the structure to be looked at — and the structure was the bug.

**The page WAS the scene.** The server rendered the whole page *around* one
pair, baking its label, frame counts and cache ids into the HTML as literal
values, and remembering that pair in module globals. Three complaints that
had been treated as separate bugs were all that one shape:

- Clear could not clear — the scene was baked into the page, so blanking
  the screen left every tool still acting on it.
- Load could not load — it listed a store's scenes and showed their
  dirty/clean state, but clicking one did nothing, because the page could
  not change scene without a hand-edited URL.
- Two browser tabs would have fought over the single remembered pair.

Now the page ships empty and the scene arrives over the API. `SCENE` in
`app.js` is the only thing that holds it, `null` is a normal state, and the
server remembers nothing — every request that acts on a scene names it.
Clear is one assignment. `/api/clear` was deleted outright: there is no
server-side copy left to clear.

The 755-line `player.py` — HTML, CSS and JavaScript inside a Python
`str.format()` template with every brace doubled — became real
`web/index.html`, `web/app.css`, `web/app.js`. `node --check` works on the
JS now, and found a **real syntax error shipping silently on the first
run**: nothing can lint code trapped inside a Python string. Browser
caching turned out to be part of the same round of confusion (a fix that
silently did not apply), so `app.js` is served `no-store`, asserted by a
test.

**Load then became what it always implied**: a two-step popup — pick a
store, pick one of its video folders — that loads every scene in that
video's `sandbox/` plus its `script.json`, and opens the first one.
`1000_archive` is excluded **by rule rather than by name** (a scene folder
is `<digits>-<label>`), so `z_History`, `_builds` and any future sibling
are skipped by the same rule with nothing to maintain. The loaded script is
visible on each scene row, so the file is doing something rather than just
being read.

217/217 checks passing after it, up from 192.

## The gap-filler library and the transition tools (2026-08-30)

The actual thing Frame Blender was for chasing kept surfacing: ski-demo
scene 1 freezes on a held frame from 442 to 482. The fix needs real idle
motion instead of a static hold, plus a clean way in and out of it — which
meant building a small reusable library rather than a one-off patch.

`sarah_clips/libs/` was created for ski-demo and populated by **copying**
(never moving) from the shared `Sarah/` reference folder: the idle footage,
her rest-pose and "Uncertainty" stills, and the generic corner↔centre
morph. Checked directly rather than assumed: no 5-second idle render exists
anywhere in the repo, only 10s and 20s.

`build/sarah_transitions.py` then built the actual mechanism: a
corner-composited gap-filler cut to any length, and fixed 5-frame Opening
and Closing transitions either side of one. The idle library's raw footage
is a different shape (608×1080, full figure) than a scene's own
`avatar.webm` (1152×1152, corner-cropped) — the gap-filler builder reuses
`assemble_video.py`'s own corner-compositing step rather than re-cropping by
a second recipe. **Caught for real**, not by inspection: the first attempt
at the Closing transition blended against the wrong still-image variant and
stretched Sarah across nearly the whole frame instead of her corner — found
by checking the actual pixels, fixed, and the function now refuses outright
if handed that wrong variant again.

## Scene 1's actual fix: measured, math confirmed, not finished

Measured directly (not assumed from memory) where scene 1's avatar.webm
really stops moving: frame 441, matching what Carson had already found by
eye. The replacement math checks out exactly: 441 real frames + 5 opening +
**31**-frame filler + 5 closing = 482, the file's own real length. A second
real bug turned up while assembling it — the concatenated result's audio
ran about 1.6 seconds longer than its video, the exact class of drift this
codebase's own build rules exist to catch — and a fix was written
(`atrim` then `apad` to the video's precise frame-counted length) but **not
re-verified** before the work was stopped for the day.

**Nothing was written to the real file.** Every attempt ran against a
throwaway `/tmp/avatar_candidate.webm`; `sandbox/01-opening-with-login/
avatar.webm` is exactly as it was before any of this started. Exact
next-session steps are in `HANDOFF.md`.

## What's sitting nearby, not ours

A crossfade feature has been mid-development in `build/assemble_video.py`
by someone else this whole time — visible in `git status` throughout, never
touched, never committed over.
