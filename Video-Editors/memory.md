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

## Four editors, four processes, no shared code (2026-09-02)

By 2026-08-30 Frame Blender had grown real teeth — Save, Undo, Load, a
real Build — by reaching into the main editor's process (`shared/
serve.py`, port 8842) for its save/undo/dirty-state machinery, and MP4
Splitter and the Segment and Avatar Editor still lived together in that
SAME process, one combined page on one port. Carson's own call, stated
directly: he was about to develop different functionality in each tool
and did not want a small change in one to be able to break another —
code duplication was an accepted, explicit tradeoff for that isolation,
not an oversight to clean up later.

So, in order: Frame Blender was made to run standalone (own port, own
save/undo — genuinely reimplemented, not proxied through the other
process, though it still imports `shared/serve.py`'s PURE helper
functions as a plain Python module, since that's sharing code, not a
running process). Then Avatar Editor was created as a full duplicate of
Frame Blender, to split Carson's own upcoming work between the two
rather than have one tool do everything. Then MP4 Splitter and the
Segment and Avatar Editor split apart from each other the same way —
own port, own cache directory, own duplicated `frames.py`/`paths.py` —
with one deliberate exception: SAE's "open this scene on its own" link
still works, via a PRIVATE duplicate of MP4 Splitter's player
(`_splitter_player.py`), not an import of the real package. Four
standalone processes, one shared philosophy: **share components, never
the running process.**

## Splitting the work between Frame Blender and Avatar Editor (2026-09-02)

Avatar Editor started life as a byte-for-byte duplicate of Frame
Blender — same combine/build UI, same Gap Builder, everything. That
was a starting POSITION, not the end state: Carson was about to divide
real work between the two and needed them to already be independent
processes before the split of WHAT EACH ONE DOES could happen cleanly.

That division landed the same day: Frame Blender kept the two-track
combine/build job (Overlay/Base panels, Speed dropdown, Build, Save
MP4) and lost the Gap Builder entirely. Avatar Editor kept only the Gap
Builder — Sarah's own clip library, the Frame Selector, the Clip-Gap
Builder that assembles a gap-filler sequence from picked clips — and
lost the combine/build UI entirely, including its backend routes.
Neither tool duplicates the other's job anymore; each is a full
implementation of exactly one half of what "Avatar Editor" used to mean
as a single duplicate.

Two small corrections happened on top of that split, both from real use
rather than being planned up front: a "play the original audio to
compare against my edit" feature was first built around "whichever
Sound Bit is checked in the library," then corrected — Carson wanted
each panel's OWN Play button to play whichever clip THAT PANEL is
actually showing (the Frame Selector's own current frame, the Clip-Gap
Builder's own current frame), not a third, separately-tracked
selection. The simpler design was also the one that mirrored existing
code exactly — `libCurClip`/`showLibFrame` already tracked "what's on
screen right now" for the Frame Selector; `builderCurClip`/
`showBuilderFrame` is the same pattern applied to the Clip-Gap Builder,
not a new mechanism.

## Logging stopped being one shared file (2026-09-02)

Once four editors were genuinely separate processes, sharing ONE
session log (`logs/editor_<date>.log`) quietly undid part of that
independence — every tool's actions interleaved in one file, and Frame
Blender's and Avatar Editor's own entries were labelled `"FB: ..."`
regardless of which of the two actually did the thing, a leftover from
when both shared a single `ACTIONS` table built for the old combined
process. Each of the four now writes to its own dedicated file, with a
label table trimmed to just the routes that process actually serves —
the same "own process, own everything" principle the port/cache split
already established, applied to the one place it had been missed.

## Two editors had never been tested standalone (2026-09-02)

MP4 Splitter and the Segment and Avatar Editor had been running as
independent processes since 2026-09-01/02, verified by hand at the
time — curl and a real browser — but neither ever got a permanent,
automated suite of its own. `test_editor.py` still proved the
underlying code correct (both started as literal copies of it), but
nothing proved the STANDALONE server — its own trimmed dispatch table,
its own cache directory, its own session log — actually held together.
`tests/test_mp4_splitter.py` and `tests/test_segment_avatar_editor.py`
closed that gap: 82 and 90 checks, built the same way `test_frame_
blender.py`/`test_avatar_editor.py` already were, plus a check that
every route each split deliberately dropped is confirmed truly gone
rather than just never called.

## Sarah stopped being one folder per store, and became one shared library (2026-09-03)

`sarah_clips/libs` and the top-level `Sarah/` folder had always looked
related and never actually were: every store's own video kept a private
copy of stills/idle/transitions/sound-bits, and `Sarah/` sat beside all
of it as a hand-kept reference stash nothing in the code ever read. The
question of whether that was intentional had never actually been asked.
Carson's answer, once it was: no — `Sarah/` should be the real, common
library, the same across every store, and a store's own `sarah_clips/`
should hold only what was made specifically for that one video.

That answer reshaped more than the folder: the Avatar Editor gained a
whole second library panel (`Sarah`, beside the existing per-store one),
both feeding the same Frame Selector/Clip-Gap Builder/Audio Menu rather
than being two separate tools bolted together — checking a common clip
and a store-specific one in the same session had to just work, which
meant every clip now carries which library it came from (`source`), and
the server gained a second, separately-scoped path guard, because
`Sarah/` sits beside `Customers/`, not inside it. ski-demo's own
organized `sarah_clips/libs/` — now redundant — was archived rather
than deleted, following the project's own existing `z_History`
convention (spelled lowercase here, at Carson's own instruction, the
one deliberate deviation from that convention).

Two real bugs were caught DURING this work, both worth remembering as
patterns, not just fixes: files copied one folder deeper than a flat
listing walks are invisible, not an error (`sound_bits/HeyGen-
originals/` the first time); and a hardcoded path that quietly stops
resolving does not fail loudly, it just makes the build wrong
(`build/assemble_video.py`'s own `REST_POSE` constant had already done
this once, which is exactly why the risk was checked for explicitly
before the stills PNGs were moved this time, rather than after).

Every doc that had grown up around this — `Sarah/README.md`,
`Sarah/closings/README.md`, `avatar_editor/README.md`'s own Sarah
sections, a stale line in `editor-launchers/SKILL.md` — was written at
a different moment in that history and none of them agreed anymore.
Consolidated into one file, `.claude/skills/sarah-library/SKILL.md`,
with `CLAUDE.md` pointing there — the same shape the project had
already settled on for `vtt` and `editor-launchers`, just not yet
applied to the thing that had actually drifted the most.

## Test output followed the same "own everything" principle logging did (2026-09-03)

The 2026-09-02 entry above split each editor's session LOG apart, for
one process to never write into another's file. The same gap existed
one level over: none of the four newer test suites wrote a log file at
all — only the old combined `test_editor.py` did, because it was the
only one anyone had gone back and added that to. Rather than copy the
same log-plus-report logic into four files, it went into `fixture.py`
once, since all four already import it — a change to what the report
looks like only has to happen in one place now, and the four outputs
can't drift out of shape with each other the way the four editors'
own `ACTIONS` label tables once had.

## The root became two folders, and the docs had to follow (2026-09-05)

The root mixed Carson's customer video work with fourteen code folders and
seven loose files. Split so it holds exactly two visible things —
`Customers/` beside `Video-Editors/` — because he works in the first far more
than the second.

`.git`, `.gitignore`, `.claude/` and `CLAUDE.md` stayed at the root and had
to: a skill only registers at `.claude/skills/<folder>/SKILL.md` relative to
the PROJECT root, so moving `.claude/` down would have made every skill here
vanish with no error at all.

**The editors needed no changes.** `shared/serve.py`'s `find_repo_root()`
already walks UP until it finds a folder holding `Customers/`, so one level
deeper resolved the same. That function was written for exactly this and paid
for itself.

Three things broke, all outside the editors, and each one was invisible until
run:

- `Basic_E2E_Testing/.claude/launch.json` — 7 absolute paths into this repo.
  The launchers live in the OTHER repo, so a move here is invisible to them.
- `tests/fixture.py` COUNTED LEVELS to reach `Customers/`. Its own comment
  said a count "is wrong the moment the tree changes" — and it was: all six
  suites died at once looking for `Video-Editors/Customers/`. It walks up now.
- `fixture.REPO` had meant two things that were the same folder until that
  day: where the code is, and where `Customers/` is. Split into `REPO` and
  `CODE_ROOT`.

## `dev/` stopped being a build stage and became Carson's mirror (2026-09-05)

`<video folder>/dev/` is now his own safety copy of the working files, held
while the editors and the process are still being built. It mirrors
`sandbox/`'s scenes, `sandbox/script.json` and `video/vtt.html`, and is
archived wholesale to the root `z_History/` before each refresh.

That first refresh nearly killed the test suites. `tests/fixture.py` read its
source footage from `dev/01-login-and-code/` — a folder that was both moved
AND renamed (`01-intro-and-login`). The three clips now live at
`tests/_fixture_source/`, gitignored like every other video here, with a
README that IS committed so the rule travels even though the bytes do not.
**Nothing may point at `dev/` again**; it gets replaced wholesale.

## A release became a folder, not a file (2026-09-05)

`release_video.py` used to copy one mp4, flat, into the store's
`help-videos/`. It now creates `help-videos/<NN-slug>/` holding the build,
its `script_v<N>.json` and its `vtt.html`. The script is REQUIRED — `--join`
writes one every time, so a build without one did not come from a join, and
shipping a video whose words are unknown is the thing worth blocking.

ski-demo v33 was the first actual release. v32 could never have been: its
clock disagrees with its frame count by +0.121s and the gate refuses it —
which is very likely why it was built and never shipped.

## Two skills, both built out of what went wrong (2026-09-04 → 09-05)

**`/final-video-clean-up`** — run after a release. Its rules are all scar
tissue: `trim_history.py` ranks archives by a date parsed out of the FOLDER
NAME, so five archives written as `26-09-04_pose` matched no pattern and the
dry run proposed deleting that day's only safety copies while keeping backups
a week older. And proving which raw take a finished video came from is
DOCUMENTARY work only — three attempts to prove it from the footage gave
three different answers, because the takes are the same scripted flow on the
same screen minutes apart.

**`vtt`, extended** — "Show me the VTT" now builds an HTML table and opens a
Chrome tab. Writing it found that the documented `python3 shared/vtt.py` had
been a no-op since the `editor_base/` merge: a re-export shim with no CLI, so
it ran, printed nothing, and exited 0.

1.9 GB came off the repo in the same pass — nothing deleted, all of it moved
to the Trash or parked in the root `z_History/` for one cycle.
