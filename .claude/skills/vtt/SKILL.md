---
name: vtt
description: A help video's Video Timing Table — per scene, how long the demo footage runs, how long Sarah's line takes to say, and the gap between them, with every line editable. THE STANDING PHRASE "Open VTT" (also "Show me the VTT", "show the vtt", "vtt for <store>") means BUILD THE EDITABLE PAGE WITH Recorder/scripts/vtt_artifact.py, PUBLISH IT AS AN ARTIFACT, AND HAND BACK THE LINK — for any mp4 whose holding folder contains a script.json. Not a chat table, not the CLI output, and no longer a plain Chrome tab. Also covers Save Script, Publish and the soundtrack rebuild. Use whenever that phrase is said or typed, when checking a store's video timing before or after a build, or when asked about dead air, gaps, speech length or scene frame counts.
user_invocable: true
---

# VTT — Video Timing Table

Not to be confused with WebVTT (`.vtt` subtitles). Different thing entirely.

## ⚡ "OPEN VTT" — ANSWER WITH AN ARTIFACT LINK

Carson, 2026-09-14: *"if I ask to see open vtt, I should see a link to an
artifact to open this interface to edit any mp4 video, that contains the script
file inside the holding/current folder."*

**This REPLACES the "open it in a new Chrome tab" answer.** That rule stood from
2026-09-04 to 2026-09-14 and is now wrong — a Chrome tab shows a page you can
only read, and the table is where the words get CHANGED.

Both repos' `CLAUDE.md` were corrected at the same time, and each keeps a note
saying the old wording is reversed. If you ever find a copy that still reads
"a NEW CHROME TAB … not a published artifact" as the live instruction, that copy
is stale — fix it in place.

### The three steps, every time

```bash
# 1. build the editable page for the folder in scope
cd ~/Rentify/Basic_E2E_Testing/Master_Flows/Recorder
python3 scripts/vtt_artifact.py "<folder holding the mp4 + script.json>"
```

2. **Publish that file with the Artifact tool.** Same file path on every
   redeploy, so the link never changes — see "One artifact per video" below.
3. **Hand back the link**, plus one line of what the page shows: scene count,
   footage, and anything it flagged as too short.

### The gate: the folder must hold `script.json`

Carson's own wording — *"any mp4 video, that contains the script file inside the
holding/current folder."* The holding folder is the one the mp4 lives in, and
`script.json` beside it is the requirement.

**No `script.json`, no table.** The words are the INPUT to this page; there is
nothing to derive them from. `vtt_artifact.py` stops and says which folder was
empty rather than inventing lines.

Today every one of ski-demo's eight raw captures passes that gate. Checked
2026-09-14, all eight built:

| folder | scenes | footage | capture named in `script.json` |
|---|---|---|---|
| `add-collection` | 44 | 392.2s | `..._add-collection_dev_09-20-00_v4.mp4` |
| `add-item` | 13 | 127.7s | `..._add-item_dev_09-14-17_v15.mp4` |
| `add-question` | 12 | 125.6s | ⚠ names `v3`, and the folder holds `v4` |
| `add-requirement` | 13 | 131.6s | `..._add-requirement_dev_09-19-50_v3.mp4` |
| `login` | 3 | 15.5s | ⚠ **names none at all** |
| `special-boots` | 21 | 379.9s | `..._special-boots_dev_10-19-54_v1.mp4` |
| `special-poles` | 21 | 622.7s | `..._special-poles_dev_10-20-23_v1.mp4` |
| `special-skis` | 21 | 375.9s | `..._special-skis_dev_10-19-12_v12.mp4` |

⚠ **A MISSING CAPTURE IS NOT A BUILD FAILURE, AND THAT IS THE TRAP.** The page
still builds; the fps falls back to *assumed* 25, the title reads
`login/<no capture named>`, and **Publish has nothing to lay the voice over**.
The build output prints the capture name or `NOT NAMED` for exactly this reason
— read that line before promising a publish.

### One artifact per video, and the link is stable

The Artifact tool keys a page to its **file path**. `vtt_artifact.py` always
writes `<recipe>.vtt.artifact.html` into the video's own folder, so
republishing the same recipe redeploys to the SAME url and Carson's bookmark
keeps working. A different path claims a NEW url and orphans the old link.

⚠ **UPDATING ONE FROM A LATER SESSION NEEDS THE URL.** Pass the artifact's url
as `url` and `Read` the live version FIRST — a publish onto a page this
conversation has not read is refused, and rightly: someone may have typed into
it since. Merge their words onto yours, then publish.

⚠ **THE FILE IS GITIGNORED ON PURPOSE.** It is stale the second a line is
edited in the page, and a tracked copy would disagree with the live artifact.
Build it, publish it, leave it.

### Do not hand-assemble one again

The first editable page was put together by hand for special-skis. That does
not answer "any mp4", so the assembly moved into the script on 2026-09-14:

    Recorder/scripts/vtt_artifact.py    the builder
    Recorder/scripts/vtt_artifact.css   the page's look
    Recorder/scripts/vtt_artifact.js    the page's behaviour — the app

`vtt_artifact.py` reproduces that hand-built page exactly: same state keys, same
21 rows, same numbers, verified field by field. So edit the three files, never a
copy in a scratchpad.


## THE TABLE — its columns, and what each one is

Carson's definition, 2026-09-14. **Eleven columns, in this order**, and the
order is part of the definition — the eye reads left to right from "how long is
the picture" to "how long are the words" to "do they fit".

| # | column | unit | what it is |
|---|---|---|---|
| 1 | **SCENES** | *label* | the scene's own name — `sign-in`, `item-details`. Not a measurement |
| 2 | **CLIP** | seconds | how long the screen is ON CAMERA. Measured off the footage, never typed |
| 3 | **LEAD-IN** | seconds | Sarah on screen before she starts. 0.5s |
| 4 | **SPEECH** | seconds | the line itself, at the voice's measured words-per-second |
| 5 | **BEAT** | seconds | the `{0.3}` markers in the line, summed. Silence, never words |
| 6 | **EXIT** | seconds | after she stops — the join the next scene's crossfade eats into. 0.8s |
| 7 | **SCENE** | seconds | LEAD-IN + SPEECH + BEAT + EXIT. What the scene needs |
| 8 | **GAP** | seconds | CLIP − SCENE. **Negative is the defect**: the line is still running when the footage has moved on |
| 9 | **SEGMENT** | **frames** | the scene's `segment.mp4` frame count |
| 10 | **AVATAR** | **frames** | the scene's `avatar.webm` frame count |
| 11 | **WORDS** | **a count** | words in the line. A `{0.3}` marker is never one |

**COLUMNS 2 TO 8 ARE THE SEVEN IN SECONDS.** 1 is a label, 9 and 10 are frames,
11 is a plain count. Nothing else on the row is a time.

⚠ **A SILENT SCENE IS AS LONG AS ITS CLIP.** Cost it the ordinary way and
LEAD-IN + 0 + EXIT gives 1.3s against a picture that may run for minutes, and
GAP then reports the opposite of the truth. For a scene with no line, SCENE =
CLIP, GAP = 0, and LEAD-IN / SPEECH / BEAT / EXIT are all 0.

⚠ **SEGMENT AND AVATAR ONLY EXIST FOR A BUILT VIDEO.** They are frame counts
read off `sandbox/<NN-label>/`. A RAW CAPTURE has no clips yet, so those two
columns have nothing behind them — leave them out rather than print a zero that
reads like a measurement. Everything else applies to both.

⚠ **AND THE TWO GENERATORS ARE BOTH SHORT OF THIS TODAY** — checked 2026-09-14,
so a table that does not match is a tool to fix, not a definition to bend:

    vtt_artifact.py       ALL ELEVEN. The editable page, and the only generator
                          that is complete against the definition above — so it
                          is the one to copy from, not the one to fix.
    build/vtt_html.py     has SEGMENT + AVATAR, missing LEAD-IN, BEAT, EXIT, SCENE
                          (it also prints a NARRATION frames column, which is
                          not in the definition above)
    scene_sheet.py        has the timing breakdown, missing BEAT
                          (its SEGMENT/AVATAR are DERIVED — clip x measured fps,
                          and avatar 0 — which is honest for a raw capture)

## THE TABLE IS NOT TIED TO A VIDEO OR A VERSION

At this level the table is a **shape**, not a report about one film. Carson,
2026-09-14: *"table is not tied to a specific video, or version at the skill
level."*

So the columns above are the definition, and the SUBJECT is resolved at the
moment of asking:

1. the video in the **current working folder**, if that folder holds one; else
2. the video **currently in context and scope** — the one just built, edited,
   recorded or discussed.

State which one you resolved to, in one line, before anything opens. If two are
genuinely in play, or none is, ASK — see "Which video?" below.

### It builds two files, not one

For whichever video that turns out to be:

    <name>.vtt        the readable timeline — cues, lead-in and exit per scene
    <name>.vtt.html   the same table as a page, for looking at

Both come from that video's own `script.json`, so they cannot disagree. Naming
them after the video matters: eight of these open in eight tabs, and a file
called plainly `vtt.html` is indistinguishable the moment it is in one.

**One command builds both, and CHECKS that they agree:**

    RAW CAPTURE
      cd ~/Rentify/Basic_E2E_Testing/Master_Flows/Recorder
      python3 scripts/vtt_build.py "<.../raw_mp4/<recipe>>" [--open]

    BUILT VIDEO
      cd ~/Rentify/Video-Editor/Video-Editors
      python3 build/vtt_html.py "<video folder>" --open

⚠ **"THEY CANNOT DISAGREE" WAS A CLAIM WITH NO TOOL BEHIND IT UNTIL
2026-09-14.** `<recipe>.vtt` was only ever written from `recipes.json`, while
`<recipe>.vtt.html` is written from `script.json` — so the moment a line was
edited, the page moved and the timeline did not, with nothing saying so.
Measured on special-skis: three saves after scene 1 had been replaced, the .vtt
still read *"Enter the email address on your Rentify account."*

`vtt_build.py` takes script.json as the **input**, never rewrites it, emits both
files, and then compares every cue in the .vtt against script.json — and
**refuses** rather than shipping a mismatch. A silent scene is exempt: it has a
NOTE and no cue by design.

⚠ **script.json IS THE INPUT, NOT AN OUTPUT, ONCE A LINE HAS BEEN EDITED.**
Regenerating it from a recipe spec throws the edit away, along with the fields a
spec cannot carry — the silent flags, the chapter anchors, the per-scene notes.

## THE FIVE JOBS OF A FIRST EDIT — and vtt_editor drives them

Carson, 2026-09-15: *"This will be the first edit on the raw video and will do
the following things: Add the yellow rings to the click event triggers. Break
the raw into our segments. Into the scenes. Add some descriptive narrative. And
add the voice… I want to make this its own editor inside the Video-Editors
folder and call it `vtt_editor`."*

    cd ~/Rentify/Video-Editor/Video-Editors
    python3 vtt_editor/serve.py               # http://localhost:8848

Or from `Basic_E2E_Testing/.claude/launch.json` as **`vtt-editor`**. Five jobs,
one rail, each row showing its own state and its own blocker.

| job | reads | writes |
|---|---|---|
| **RINGS** | `<capture>.clicks.jsonl` | nothing — it shows them on the frame |
| **SEGMENTS** | `stretch_report.json`'s confirmed edges | `segments/` (cached cuts) |
| **SCENES** | `segments/` | `sandbox/<NN-label>/segment.mp4` |
| **NARRATIVE** | `script.json` | `script.json` + `.bak`, then `vtt_build.py` verifies |
| **VOICE** | the script and the edges | `-narrated.mp4` |

⚠ **NOTHING IN THE EDITOR RE-IMPLEMENTS A TOOL.** It shells out to
`stretch_scenes.py`, `stretch_request.py`, `narrate_mac.py` and `vtt_build.py`,
and resolves the scene layout through `editor_base/paths.py`. A second copy of
an ffmpeg recipe is a second copy to get wrong.

### ⚠ THE RINGS ARE ALREADY IN EVERY CAPTURE — border-only, 750ms

This is the part that reads like new work and is not. `instrumentClicks` is
patched onto every page in `Core/lib/browser.ts`, and the recorder sets:

    record_flow.ts:381   CLICK_HIGHLIGHT_MS   = 750    the ring holds 0.75s
    record_flow.ts:393   CLICK_HIGHLIGHT_FILL = 0      the fill is OFF

**Border only, no yellow wash** — Carson, 2026-09-09: *"we will only use the
rings from now on. Looks better."* Reaffirmed 2026-09-15 when he asked *"Are
they done with the yellow background fill or just the rings?"* and chose to keep
it. The fill exists in `highlightCss()` and defaults to 0.35 when nobody
overrides it; the recorder always overrides it. `set_collection_options.ts:129`
also passes `{fill: 0}` for the one screen where a wash was proven unreadable.

⚠ **AND A WARNING ABOUT MEASURING IT.** A scan that downscaled the video to
320px reported "no yellow anywhere" on a capture that plainly has rings — a 3px
outline at 2304px wide is 0.4px at 320. **Never measure a thin line on a
downscaled frame.** Pull a full-resolution frame at a moment a click happens and
look at it; a typing ring is held for seconds and is the easiest to catch.

### ⚠ THE CLICK LOG — new on 2026-09-15, and older captures have none

Rings were burnt into the pixels with no record of where or when, so nothing
downstream could move, extend or remove one. Now `holdFlash()` — the one choke
point every ring goes through — appends a line as it lights:

    {"t": 4.10, "kind": "click", "fill": 0, "held_ms": 750,
     "selector": "#go", "x": 300, "y": 120, "w": 160, "h": 44}

Written as **JSONL, appended synchronously**: a flow that crashes half way
through still leaves every ring it drew, which is exactly the run whose footage
you most want. Filed as `<capture>.clicks.jsonl` beside the capture.

⚠ **`t` IS SECONDS INTO THE CAPTURE, AND THE LEAD-IN TRIM MOVES IT.** OBS starts
before the flow does, so `record_flow.ts` passes the recording's start as
`CLICK_LOG_T0`. Then `trim_lead.py` cuts the dead opening off the FRONT of that
same file — so every `t` shifts. `record_flow.ts` reads the trim's own JSON
(`cut`) and rebases the log, recording the amount in the header. Caught before
shipping by reading what happens to a capture AFTER it is saved; left alone the
numbers stay plausible and land on the wrong frames.

⚠ **THE RECT IS CSS PIXELS OF THE PAGE, NOT PIXELS OF THE VIDEO.** The capture
is a cropped window region on a scaled monitor. The log's first line is a
GEOMETRY HEADER carrying the window region and the chrome crop, and the
transform happens in the page where the rendered frame's size is also known.

⚠ **ONE RING, ONE LINE.** `page.click` goes through `handle.click` and both are
patched, so a single click wrote TWO entries until an `inPageClick` depth guard
was added. Measured on a two-action harness that logged three rings.

⚠ **OFF UNLESS `CLICK_LOG_PATH` IS SET**, and read lazily rather than captured
at import — a module-level const meant the env had to be set before the file was
imported, which is true for the spawned flow and a trap for anything else.

### The three surfaces, corrected

    vtt_editor          localhost:8848. THE place to do a first edit.
    the artifact page   stays — the one that opens anywhere.
    the SAE's EVTT      stays — it covers a BUILT video's sandbox/.
    serve_vtt.py        GONE. Replaced, with its vtt-live entry (8847).

⚠ `serve_vtt.py` was one writer too many: it and an artifact page could both
hold `script.json` open, and on 2026-09-14 it was left running after being
reported stopped.

### ⚠ THE HELP-VIDEO FOLDER LAYOUT — ALL FOUR STORES SPLIT, 2026-09-15

Carson reorganised ski-demo on 2026-09-15: *"Review the ski-demo help-video
folder structure I just updated to keep me a bit better organized."* Then, the
same day: *"Refactor the bike demo help-videos folder to match with ski demo."*
Then *"Do canoe-demo next"*, then *"Do alpine-sports next."* All four now:

    <store>/help-videos/
      BCP_raw_mp4/        the admin recipes
      UI_raw_mp4/         the renter flows
      development_videos/ was videos/
      Completed_Videos/   was development/
      z_History/

⚠ **`raw_mp4` AND `videos` NO LONGER EXIST ANYWHERE UNDER `Customers/`.**
Not on one store, not as a fallback that something still finds. Any code that
names either is dead code as of 2026-09-15 — see "WHAT THIS BROKE" below,
because four files were still naming them and none of them said so.

**Raw captures split by SURFACE** — `BCP_raw_mp4` for the admin recipes,
`UI_raw_mp4` for the renter flows. `videos/` became `development_videos/`, and
`development/` was RENAMED to `Completed_Videos/` — it is not new and it is not
a deletion, which `git show --find-renames a1c11ff` shows outright.

⚠ **THE SPLITS CAME OUT NEARLY IDENTICAL**, because every store was recorded
from the same roster. `UI_raw_mp4` gets the same six renter recipes every time.
`BCP_raw_mp4` varies only in what was actually captured:

    bike-demo      4   catalogue expand-catalogue nav store   (all empty)
    canoe-demo     4   the same four                          (all empty)
    alpine-sports  5   + items, and it has 6 REAL captures
    ski-demo       7   add-collection add-item add-question
                       add-requirement special-{boots,poles,skis}

⚠ **`git mv` REFUSES A FOLDER GIT DOES NOT TRACK** — "fatal: source directory
is empty" — and it is ALL-OR-NOTHING, so the whole batch rolls back and you
have to look to see that nothing moved. alpine-sports' `items/` held one
gitignored mp4 and no `.gitkeep`, so it needed a plain `mv`. Check
`git ls-files <folder> | wc -l` per folder first.

⚠ **WHICH SURFACE A RECIPE BELONGS TO IS IN THE CODE, NOT IN YOUR HEAD.** The
BCP recipe names are the top-level keys of `BCP/Nav/scripts/bcp_runner.ts` —
`catalogue`, `expand-catalogue`, `nav`, `store`, `add-collection`, `add-item`,
`add-question`, `add-requirement`, the `special-*` set, and more. Everything
under `Master_Flows/UI/` is a renter flow. every store's admin
folders were sorted by running `surface_of()` over each folder name, not by
eye; none of their names match ski-demo's, so a pattern copied off ski-demo
would have put them all in the wrong place.

⚠ **NEVER HARDCODE A STAGE FOLDER. READ IT OFF DISK, EVERY TIME.** The
fallback to `raw_mp4` is kept in both tools below for a store that has not been
created yet — not because any store uses it. Two places do it right:

    record_flow.ts   rawSubdirFor(storeRoot, surface)  — picks BCP_/UI_ when the
                     store has them, else raw_mp4. Asks the DESTINATION repo,
                     not this one, because the split folders live over there.
    scene_script.py  looks for the recipe under BCP_raw_mp4, UI_raw_mp4, then
                     raw_mp4, and takes whichever already holds it.

⚠ **A STORE THAT SPLITS LATER NEEDS NO CODE CHANGE.** Both checks are on what
exists, not on the store's name. That is the point of doing it this way.

⚠ **vtt_editor NEEDED NOTHING.** Its breadcrumb walks `help-videos/*` rather
than assuming a name, so it showed the new folders the moment they appeared —
`BCP_raw_mp4 (4/4)`, `UI_raw_mp4 (5/11)`, `development_videos (1/1)`. That is
what a generic walk buys. Proven three times over: neither bike-demo's nor
canoe-demo's split needed a change to it.

### ⚠ WHAT THIS BROKE — READ THIS BEFORE SPLITTING ANOTHER STORE

**A folder rename breaks whatever NAMES the folder in a file, and not one of
these said so.** Reading the name off disk protects the tools that do it; it
protects nothing else. Everything below was found by grepping for the old names
AFTER the move, which is the step to repeat next time.

⚠ **THE `.gitignore` STOPPED TRACKING ALL TEN `*vtt.html` PAGES.** The two
un-ignore lines named `raw_mp4/` and `videos/`, so every page fell back to the
blanket `Customers/**` exclusion — **silently**, because an untracked file looks
exactly like a file with no changes. This is the SECOND time the same two lines
did this: on 2026-09-14 they missed the `<recipe>.vtt.html` rename. The pattern
now names no stage folder at all — un-ignore under `help-videos/**`, then put
back `dev/**` and `sandbox/**`, which the editors rewrite on every run. Verify
with `git check-ignore`, never by eye:

    find Customers -name '*vtt.html' ! -name '*.artifact.html' | while read -r f; do
      git check-ignore -q "$f" && echo "IGNORED $f" || echo "tracked $f"; done

Expected today: 9 tracked, and `dev/vtt.html` ignored.

⚠ **`work/boundaries.json` NAMES THE MASTER, AND EVERY STORE HAS ONE.**
`build/cut_segments.py` passes its `raw` field STRAIGHT TO ffmpeg as `-i`, and
`/final-video-clean-up` reads it to decide which file is the master. All four
were stale — three pointed into `Basic_E2E_Testing`, which has not held these
files since 2026-08-28, and at a flat `raw_mp4/` root rather than the recipe
folder; ski-demo's was relative, so it only ever resolved from one directory.
All four now hold an ABSOLUTE path to a file that exists. Check all four at
once:

    python3 - <<'EOF'
    import json, io, glob, os
    for p in sorted(glob.glob('/Users/carsonkramer/Rentify/Video-Editor/Customers/'
                              '*/*/help-videos/development_videos/*/work/boundaries.json')):
        print(os.path.isfile(json.load(io.open(p))['raw']), p)
    EOF

⚠ **THREE OTHER EDITORS NOW FIND NOTHING, ON ALL FOUR STORES. NOT FIXED —
editor scope lock, needs an explicit go-ahead.** Measured, not guessed:

    mp4_splitter/serve.py     355, 651, 660-661
    segment_avatar_editor/serve.py  490, 506-514, 907, 916-917, 959, 975
    avatar_editor/serve.py    396, 412
    Video-Editors/Makefile    19, 109, 118
    avatar_editor/web/library.js  30  (a comment only)

    "jump to raw captures" link   0/4 stores   (isdir help-videos/raw_mp4)
    Load picker, videos found     0/4 stores   (isdir help-videos/videos)

So the SAE's and avatar_editor's Load pickers are EMPTY for every store, and
the Makefile prints "no videos/ folder — this store is still flat" for all of
them. ski-demo has been in that state since its own reorg; the other three
joined it. **The fix is the same read-off-disk rule these two already use** —
see `rawSubdirFor` and `raw_folder` above.

⚠ **AND TWO THINGS DID NEED CHANGING IN THE TESTS, NEITHER OF WHICH ANNOUNCED
ITSELF.** Both name a path in a file, which no amount of reading-off-disk
protects:

    tests/test_{frame_blender,avatar_editor}.py   REAL_STORE_REL named
                     bike-demo's `videos/` outright, and test_avatar_editor's
                     SKI_STORE_REL named ski-demo's — that second one had been
                     dead since ski's own reorg and nobody noticed, because a
                     moved fixture folder reads as a FAILING ASSERTION, not as
                     a missing path. It looks like an editor bug. All three
                     constants now pick whichever of
                     development_videos/videos exists; all 9 fixture paths
                     resolve.
    (boundaries.json and the .gitignore are covered in their own
                     sections above — they are not test-only problems.)

⚠ **A NEW RECIPE IS FILED BY ITS SURFACE — FIXED 2026-09-15.**
`scene_script.py`'s fallback used to read `BCP_raw_mp4 if it exists else
raw_mp4`, so on a split store every brand-new recipe went to the ADMIN folder,
renter flows included. It only ever bit a recipe whose folder did not exist yet
— the loop above finds every existing one — but two stores are split now, so it
was wrong twice over.

    scene_script.py  bcp_recipes()  parses the top-level keys of
                     BCP/Nav/scripts/bcp_runner.ts's SEQUENCES object
                     surface_of()   those keys are 'bcp', everything else 'ui';
                     a `"surface"` in the recipe spec overrides both
                     raw_folder()   an existing folder wins; otherwise the
                     surface's own folder, else the flat raw_mp4 — the SAME
                     rule as record_flow.ts's rawSubdirFor()

⚠ **THE LIST IS PARSED, NEVER COPIED.** A list of recipe names pasted into
Python goes stale in silence: a recipe added to `bcp_runner.ts` later would
quietly file itself as a renter flow, and a wrong folder raises nothing. If the
runner cannot be read, `surface_of` STOPS with the file name and tells you to
put `"surface"` in the spec — it does not guess, because guessing is the bug.

⚠ **`login` IS A BCP RECIPE, AND ITS FOLDER STAYS UNDER `UI_raw_mp4` ANYWAY.**
Both halves are settled, so do not re-open either. It is BCP: there is no
`login` in `UI/Nav/lib/recipe.ts` at all, `bcp_runner.ts` calls it "sign in and
stop on the dashboard", and ski-demo's own `login/script.json` says the footage
exists "so it can be dropped over the front of every other BCP video". The
folder stays put by Carson's decision, 2026-09-15, asked outright. Nothing
breaks — an existing folder is found before the surface is consulted. **DO NOT
MOVE IT to make the two agree.**

⚠ **AND `scene_script.py` STILL WRITES `LEAD = 0.5` / `EXIT = 0.8`** (lines
48-49) while all nine ski-demo scripts carry `_lead_in_seconds: 0.75` and
`narrate_mac.py` defaults to `LEAD_DEFAULT = 0.75`. So a BRAND-NEW recipe opens
at 0.5 and disagrees with every existing script, and the voice tool honours
that 0.5 because it reads the script's own field. **Left alone on purpose** —
Carson's call, 2026-09-15: `--from-script` recomputes each `.vtt` from these
two constants, so changing them shifts every existing table on its next
rebuild. Raise it before the next new recipe is written, not during one.

⚠ **`mp4_splitter/serve.py` STILL HARDCODES `raw_mp4`** (lines 355, 660-661).
It is a different editor, the editor scope lock applies, and it has not been
touched. Its store rows will not jump to ski-demo's captures until someone with
a go-ahead fixes it.

## PUBLISH and STRETCH — the two actions on the table

Carson, 2026-09-14 and 2026-09-15. A VTT table is not only a report; it is
where the words get changed, and now where a screen too short for its line
gets fixed. **Two buttons**, and they do different things to different files.

| | what it does | cost |
|---|---|---|
| **Publish** | writes the edited lines into `script.json`, then rebuilds the narrated mp4 | a minute or two |
| **Stretch** | lengthens the screens with a NEGATIVE GAP, then re-narrates over the result | minutes; only the changed scenes after the first run |

### ⚠ SAVE SCRIPT IS GONE. Do not add it back.

There were three buttons until 2026-09-15. Carson asked *"Do we still need the
Save Script button since the Publish button will also update the script?"* and
the answer was no:

- Both called **one function**, `pushScript()`. Publish passed the extra flag.
  So **Publish was a strict superset** of Save Script, never a sibling.
- The words were never at risk without it. The **hot save** republishes the
  page on every changed line, with no button pressed — so an edit survives a
  closed tab whether or not anything was clicked.

What it uniquely offered was a *seconds*-fast write to disk with no encode.
Real, but thin, and not worth a third button in a row that must not wrap.

⚠ **THE ORDER IS WHAT MAKES DROPPING IT SAFE.** With no cheap save left, every
job writes `script/current` **before** its request row. If a row could land
without the words beside it, a job could encode from a stale `script.json`.
That guarantee is the write order, not a flag — do not reorder it.

⚠ **`#save` WAS LOAD-BEARING IN FOUR PLACES**, and deleting the tag alone
leaves four `null` dereferences on a page that currently works: `dirty()`
toggled its `disabled`, `doSave()` disabled and re-enabled it, `spinOn`/
`spinOff` did too, and the read-only branch stamped `dataset.readonly` on it.
All four are gone; the status text they wrote lives on the `#msg` span, which
kept its job. The `unsaved` FLAG stays — `doSave()` refuses when nothing is
pending and `beforeunload` uses it to get a last line out.

⚠ **AND THE ERROR TEXT CHANGED WITH IT.** A failed save used to say "press
Save to retry". There is no Save to press; it now says to edit a line again,
which is what actually retries.

### Where the buttons sit

**Publish on the LEFT of the pair, Stretch to its RIGHT, on ONE ROW** — from
Carson's original instruction, *"Add it on the right side of the page view, at
the same vertical height as the Save button."* That rule was written about
Save Script and Publish; it now governs Publish and Stretch.

⚠ **The row must not wrap.** The status messages beside the buttons are long
enough to push one onto a second line at a narrow viewport, which breaks the
one thing that was specified. Pin the row (`flex-wrap:nowrap`), never let the
BUTTONS shrink, and let the MESSAGES give way — truncated with an ellipsis,
since a status line is the cheapest thing on the row to lose.

⚠ **NEITHER IS STYLED AS THE DEFAULT BUTTON.** Both cost minutes. Both are
outlined rather than filled, and they take **different colours** — Publish the
warning colour, Stretch the accent — because two identical buttons side by side
is how the wrong one gets pressed.

⚠ **STRETCH IS HIDDEN WHEN NOTHING IS SHORT.** A button that cannot help should
not be on screen. `render()` owns it: it already counts the short screens for
the summary strip, so it also shows, hides and labels the button — *"Stretch 1
short screen"*. Edit a line long enough and the button leaves on its own;
shorten one and it comes back. Toggle `hidden`, never `style.display` — the
host's reset marks `[hidden]` important and a display value here would fight it.

### Both buttons: the words, and only the words

`script.json` holds far more than lines: the measured clip lengths, the pauses,
the chapter anchors, the notes. **Touch only `line`.** Everything else was
measured or decided elsewhere and a table has no business rewriting it.

⚠ **STRIP THE TABLE'S OWN DECORATION FIRST.** The generated page wraps every
line in `“ ”` for display. Read the cell back as-is and those quote marks are
written into `script.json` as real characters — which is exactly how two stray
quotes got into special-skis' words on 2026-09-14, and how one line then
measured 0.29s over its screen.

⚠ **AN EMPTIED LINE IS A REAL EDIT, AND IT MAKES THE SCENE SILENT.** Set
`silent: true` and drop its `pauses`, or every tool downstream costs it as words
it does not have. A guard of the shape `if (next && next !== old)` silently
refuses a cleared line — so a scene can be given words and never handed back to
silence. Both directions have to work.

⚠ **KEEP ONE BACKUP.** The words are the only thing in a video folder that
cannot be regenerated from something else. `script.json.bak` before each save
(the EVTT keeps its own copies in `z_History/line-edits/`).

⚠ **A SILENT ROW'S CELL HOLDS THE TABLE'S EXPLANATION, NOT A LINE.** The
generator renders "Silent, on purpose. These screens repeat the first item…"
into that cell so a reader knows the silence is meant. Seed an editor from it
and one save writes that prose in as the scene's line. Start the cell EMPTY with
the explanation as a placeholder.

### PUBLISH — what actually happens, end to end

⚠ **THE PAGE CANNOT DO ANY OF IT, AND IT DOES NOT PRETEND TO.** The artifact
runs in claude.ai's sandbox: no filesystem, and a network locked to a few CDNs.
So it cannot write `script.json`, cannot run `ffmpeg`, and cannot even reach a
localhost helper. What it CAN do is leave the words somewhere Claude reads.

**IN THE PAGE** — two documents in the artifact's own `db`:

    script/current      always. The whole patched script.json, plus the lines
                        as a flat list, the recipe, the capture and a timestamp.
    requests/publish    only on Publish. {state:'requested', note, requestedAt}

**ON THE MACHINE** — Claude watches that request row and does the four steps:

1. **MEASURE EVERY LINE WITH THE REAL VOICE FIRST**, and report which will be
   rushed. `words / wps` has no term for punctuation and `say` pauses at every
   comma: 21 words with four commas measured 8.18s where the formula said 7.9s.
   A line that will be sped up is worth knowing BEFORE the encode, not after.
2. Write `script.json`, keeping `script.json.bak`. Then `vtt_build.py`, which
   REFUSES if any cue disagrees with the script.
3. Speak the lines and lay them over the picture named in `_note`.
4. Report the new duration, and how many lines had to be rushed.

**BACK IN THE ROW** — Claude writes progress into `requests/publish` as it goes,
and the page's spinner follows it:

    state: 'running', step: 'rebuilding the soundtrack'
    state: 'done',    step: 'soundtrack rebuilt'
    state: 'failed',  step: '<what broke>', detail: '<why>'

⚠ **PUBLISH DOES NOT RUN ITSELF, AND CARSON HAS ASKED THIS TWICE.** The encode
happens because Claude is in the conversation and runs it. Say so plainly —
never let a spinner imply the machine is working on its own.

⚠ **PUBLISH NEEDS THE CAPTURE NAMED IN `script.json`'s `_note`** — "Cut from
&lt;file&gt;.mp4". Without it there is nothing to lay the voice over, and the
right move is to stop and say so rather than guess at the folder's mp4s. One
folder legitimately holds two (a master plus the shared login clip).

⚠ **NEVER WRITE OVER THE MASTER.** The narrated file is a NEW file beside it.
The master is what the delivered cut is made from, its screen edges live in
`stretch_report.json`, and this repo has already lost one.

### STRETCH — what actually happens, end to end

Carson, 2026-09-15: *"I want Sonnet to help me stretch the segment when the
narrative track has a negative gap. We need to add a button to trigger the
stretch event."*

**IN THE PAGE** — `script/current`, then `requests/stretch` carrying the scenes
it found short. **ON THE MACHINE** — one command, and the worker runs nothing
else:

    cd ~/Rentify/Basic_E2E_Testing/Master_Flows/Recorder
    python3 scripts/stretch_request.py "<folder>"        # --dry-run to look first

It backs up the edges, derives the bounds, stretches, re-narrates, and says what
came out. A worker must never be assembling ffmpeg arguments itself.

⚠ **THE EDGES COME FROM `stretch_report.json`, NEVER FROM DETECTION.** Every
report carries `src_in`/`src_out` per scene — edges a person already confirmed
against a contact sheet. **No report, no stretch**: the command stops and tells
you to run `stretch_scenes.py peaks` first. Auto-detection was tried twice and
is untrustworthy — "take the N-1 biggest frame changes" once made `sign-in`
25.84s and `item-details` 1.04s, because a dropdown opening is a bigger picture
change than a dark page replacing a dark page. And `script.json`'s `raw-source`
comes from a DIFFERENT run than the one recorded: on add-item v12 four of
thirteen were out by more than a second.

⚠ **ONLY THE CHANGED SCENES ARE RE-ENCODED.** Carson's own constraint. Every
per-scene mp4 is cached in `segments/`, keyed by scene, factor AND edges, so a
stale hit is impossible rather than unlikely. **Measured on special-skis
2026-09-15: first run 21 scenes in about 5 minutes; re-run 0 scenes in 24
seconds.** The first run of a capture has no cache and pays for all of them
once — say that, rather than promising the fast number.

⚠ **THE PICTURE SLOWS, IT DOES NOT FREEZE.** Frames are duplicated evenly
across the screen (`setpts=F*PTS` then `fps=25`), so the ring still lands and
the typing still runs, just slower. Holding the last frame parks the picture,
and a parked picture reads as a stall.

⚠ **IT ONLY EVER MAKES A SCREEN LONGER.** A screen with time to spare keeps it —
that spare is the editor's to trim.

⚠ **AND AFTERWARDS THE TABLE IS STALE UNTIL THE PAGE IS REBUILT.** `script.json`'s
`raw-source` is NOT rewritten by a stretch, and must not be — it is the record
of a measured run. So `vtt_artifact.py` reads the clip lengths from
`stretch_report.json`'s `built` whenever that file is there, since that is the
length each scene actually occupies in the cut the voice was laid over. Found
2026-09-15: the first real stretch fixed `enter-the-code` from 7.0s to 7.4s and
the rebuilt page still said *"1 screen too short"*.

### THE WORKER LOOP — who waits, and who works

⚠ **A SUBAGENT CANNOT HOLD AN ARTIFACT WATCH.** Only an interactive main-loop
session is notified when a page is republished — a subagent, background or print
session gets nothing. So Sonnet cannot be the monitor, however it is asked for.
Carson chose the split on 2026-09-15: **the main session waits, Sonnet works.**

On every `artifact-changed` event for a VTT page:

1. Read `requests/publish` AND `requests/stretch`.
2. `state` is not `'requested'` → **do nothing, say nothing.** That was a line
   edit; the hot save already handled it. This is the whole point of Carson's
   *"only publish when I do a Publish event using the button"* — the page saves
   itself constantly, and a save is not a request.
3. `state: 'requested'` → set it `'running'`, then spawn a **Sonnet 5** worker
   (`Agent`, `model: "sonnet"`) with the folder, the job, and the one command.
4. Write `done` or `failed` back with a real `step`. **A worker that dies
   silently leaves the spinner turning forever** — the page has no other way to
   learn the job ended.

⚠ **AND THE WORDS IN THE PAGE ARE USUALLY NEWER THAN THE WORDS ON DISK.** The
hot save keeps edits in the ARTIFACT; nothing reaches `script.json` until a
button is pressed. So before any rebuild or republish, **read the live page and
merge its lines onto disk first.** Measured 2026-09-15: Carson had rewritten
**12 of 21 lines** in the page while `script.json` still held the old ones — a
rebuild published without merging would have destroyed all twelve.

### The four bugs this page has already had — do not write them back

All four were live, all four were found by testing, all four are fixed in
`vtt_artifact.js`. Each one looked like nothing was wrong.

**1. `confirm()` returns `false` silently in a sandboxed frame.** No dialog, no
error, no message. The handler's first line was `if (!confirm(...)) return;`, so
Publish was a completely dead button — while Save Script, which has no confirm,
kept working. Diagnosed from the store: `script/current` had been written by a
later click and `requests/publish` was still empty.

    THE FIX: the guard is IN THE PAGE. First click arms, second commits, and it
    disarms itself after 6 seconds. Nothing depends on a dialog the host may
    refuse. NEVER put a confirm(), alert() or prompt() in an artifact.

**2. `get()` hands back a SNAPSHOT, and the body is behind `data()` — a
FUNCTION, not a property.**

    const snap = await DB.doc('requests/publish').get();
    snap.state          // ALWAYS undefined — this was the bug
    snap.data().state   // the real value

    type DocumentSnapshot = { id, exists, data(), metadata }

The poll read `r.state` off the snapshot, so it was undefined on every tick, so
it fell into the "not started yet" branch forever. **The spinner never stopped**,
even after `state: 'done'` was written. Both reads now go through one `readJob()`
helper, and a read that THROWS returns `undefined` rather than `null` — "could
not read" is not the same as "absent", and treating them alike restarts a job.

**3. Negative margins on the sticky title bar.** They pulled the bar up by the
PAGE's own padding, which only works if the page owns the body. The artifact
host wraps the content in its own body, so the bar was pushed off the top of the
scroll port and the title never appeared however far you scrolled. Two
screenshots arrived that way. Plain margins stick under either wrapper.

**4. Two listeners on one button.** An earlier pass added a SECOND click handler
to `#save` — the same element hot save already used — which would have run
`doSave` twice and raced the hand-over. Caught before publishing.

### And three more rules the code already encodes

⚠ **AN EMPTY LINE IS A REAL EDIT.** The old guard was `if (next && next !== old)`,
which silently refused a cleared line — so a scene could be given words and
never handed back to silence. Both directions have to work, and clearing a line
sets `silent: true` and drops its `pauses`.

⚠ **THE WHOLE `script.json` TRAVELS WITH THE PAGE**, in `S.script`. Save Script
patches the edited words into that copy and hands back a drop-in replacement, so
every measured clip length, pause, chapter anchor and note survives. Emitting
only the lines would quietly strip the fields nothing else can regenerate.

⚠ **THE SPINNER RUNS UNTIL THE JOB IS DONE, NOT UNTIL THE CLICK FINISHES.** The
click only hands the request over; the encode takes a minute or two. Stopping on
the click would say "finished" over a video still being written — the one thing
a progress indicator must never do. A page reloaded mid-job reads the row on
load and picks the spinner straight back up.


### Which surface — and the ARTIFACT is the default one now

⚠ **THREE SURFACES. ONLY ONE IS WHAT "OPEN VTT" MEANS.**

    A PUBLISHED ARTIFACT  ← THE ANSWER TO "OPEN VTT", from 2026-09-14
      Built by Recorder/scripts/vtt_artifact.py, published, link handed back.
      It CANNOT write script.json and CANNOT run the encode — sandboxed, no
      filesystem, network locked to a few CDNs, so not even a localhost
      helper is reachable. So it hands the whole script to its own `db` store
      and says on screen that Claude places the file. It never implies the
      page did the work. Full chain above under "PUBLISH — what actually
      happens".

    EVTT — the editor's own live panel, a BUILT video
      Lines editable in place, gap repaints as you type, and BLUR SAVES to
      script.json directly (copies in z_History/line-edits/). No Save button
      needed, and no Publish. It only covers a BUILT video's sandbox/.
      READ THAT SECTION BEFORE BUILDING ANYTHING NEW THAT EDITS NARRATION.

    A page served from localhost, a RAW capture
      Master_Flows/Recorder/scripts/serve_vtt.py. Both buttons write for real,
      because it runs on the machine the files are on.
      ⚠ DO NOT RUN IT ALONGSIDE AN ARTIFACT FOR THE SAME FOLDER. Two writers
      to one script.json. On 2026-09-14 it was left running (pid 9130) after
      being reported stopped, and it was a second writer the whole time.
      Prefer the artifact; start this only if Carson asks for localhost.


The tool lives in this repo:

    editor_base/vtt.py       (run it as `python3 -m editor_base.vtt`)

## What it does

For each scene: how long the demo clip runs, how long Sarah's line takes to
say, and the **gap** between them. The gap is the whole point — it is how
long she sits frozen in the corner with nothing to say, and it is invisible
until someone actually watches the finished video.

## Running it

```bash
cd ~/Rentify/Video-Editor/Video-Editors
python3 -m editor_base.vtt "<video folder>"
```

⚠ **Not `python3 shared/vtt.py`.** That path still exists but is a re-export
shim with no command line left in it — it runs, prints NOTHING, and exits 0,
which reads exactly like a video with no scenes. Corrected 2026-09-04 after
it silently did nothing. `-m` is required: run `editor_base/vtt.py` by path
and it cannot import its own package.

(For a store still on the old flat layout, point it at `help-videos/final`
instead.)

## Where the numbers come from

- **Clip lengths** are read straight from the files on disk — never
  hand-typed.
- **The lines** come from that video folder's `script.json`, which is the
  single source of truth for the copy. Edit the lines there and re-run —
  never retype a line into a doc or a chat message, which is how copy drifts
  from what actually got rendered.
- **Speech length** is estimated at the voice's MEASURED words-per-second
  (Derya: 3.44 wps), taken from clips already rendered. An earlier guess of
  2.70 understated every line by ~25% and hid a third of the dead air.
  Re-derive it whenever the voice or its speed setting changes.

## Reading the output

**The columns are defined once, at the top of this file** — "THE TABLE, its
columns, and what each one is". Nothing here restates them, and nothing should:
the fastest thing to drift in a document like this is a second, slightly
different list of the same eleven things.

`vtt.py`'s plain output is a SUBSET of that table — timing only, no frame
counts — and it puts the line Sarah says beside each row. A trailing summary
gives total clip, total speech, total gap and word count, plus the dead-air
percentage and a flag for any scene over the 2.5s gap threshold.

A gap on its own is not a defect — the build holds the last frame while she
finishes talking. It only becomes worth fixing when a single scene's gap is
large enough to read as a stall (see the `sae-video-building` skill's "closing
hold" and "held frame" notes for what counts as normal versus worth a second
look).

## 🔊 VOICE COMMAND — "Show me the VTT" / "Open VTT"

Carson's phrase, 2026-09-04. Said out loud or typed — "Open VTT", "Show me the
VTT", "show the vtt", "vtt for &lt;store&gt;" — it means **one thing, and the one
thing changed on 2026-09-14.**

⚠ **IT NO LONGER MEANS A CHROME TAB.** Build the editable page, publish it, and
hand back the artifact link. The full procedure is at the TOP of this file under
**"OPEN VTT — ANSWER WITH AN ARTIFACT LINK"**. Read that, not this.

**What this section is still for** is the two questions the phrase does not
answer on its own — *which* video, and *which* build — plus what the page shows
once it is open. Those are below and they still apply.

**The read-only pages are still real, and still useful.** They are just not what
the phrase means any more:

```bash
# a BUILT video, read-only, ffprobes sandbox/ for real frame counts
cd ~/Rentify/Video-Editor/Video-Editors
python3 build/vtt_html.py "<video folder>" --open

# a RAW capture, read-only
cd ~/Rentify/Basic_E2E_Testing/Master_Flows/Recorder
python3 scripts/vtt_build.py "<.../raw_mp4/<recipe>>" --open
```

Reach for those when the answer is *"what do the numbers say"* and nothing is
going to be edited. Reach for the artifact whenever a word might change.

**The markdown table further down** is still correct and still what to use when
the answer belongs *inside* a reply — a single scene, a quick comparison. The
plain CLI output is a source, not something to show.


### Which video? Infer it, then say which one you picked

Usually obvious from the conversation: the store and video just built,
edited, or discussed. State your choice in one line — *"ski-demo
01-first-time-ordering, v33"* — so a wrong guess is caught before a tab
opens.

**If two are genuinely in play, or none is, ASK.** Do not default to
ski-demo because it is the most worked-on. One short question beats a table
for the wrong store, which looks right and is not.

### Which build? `script_v<N>.json`, and it is a real choice

`--version 33` reads `video/script_v33.json`, the snapshot of the script
that produced `..._v33.mp4`. With no `--version` it takes the newest one,
and with no snapshots at all it falls back to `sandbox/script.json`.

The **lines** come from that file; the **numbers** always come from
`sandbox/` on disk. So a VTT for an old build shows that build's words
against today's footage. That is usually what is wanted right after a
build — say which script was read, and the page's footer says so too.

### The title matters — it is how eight of these are told apart

The page's `<title>` becomes the browser tab AND the artifact's name in the
gallery. Built as `<store> VTT <title>` — **`ski-demo VTT Adding a collection
with variants — Special Skis`**; the read-only builder uses `<store> VTT v<N>`.
Several of these get opened at once and a tab that just says "vtt" is no use.
The scripts do this; do not hand-edit it to something generic, and **keep it
stable across redeploys** — a changed name reads as a different page.

⚠ **AND THE PAGE'S OWN HEADING IS THE PATH, NOT THE PROSE NAME.** Carson,
2026-09-14: *"Replace this with the folder name and the file name, like this:
special-skis/ski-demo_special-skis_dev_10-19-12_v12.mp4"*. A prose title says
what the video is ABOUT; the path says WHICH FILE this table measures — and with
several recipes and several takes each, that is what you actually need to read
off a tab. Set in mono at 21.5px, sticky, so it stays put while 21 scenes
scroll. The prose name moves to the meta row under it.

### What the page shows

The table at the top of this file, with the line Sarah says on its own row
underneath each scene — plus a summary strip above it: clip, said, dead air %,
scenes over 2.5s, words, frames.

⚠ It does NOT yet carry every column in the definition — see the gap list
there. A table that falls short is a tool to fix, not a definition to bend.

It also raises the trap from "The combined table" below — any scene whose
avatar is **shorter than its own `narration.webm`** gets flagged, because
`segment = avatar` looks tidy and can mean the avatar was trimmed to fit,
cutting the end off her line.

## Source: always `sandbox/`, never `dev/`, never anything else

The combined table's numbers come from `sandbox/<NN-label>/` — the same
folder the editor reads and writes. This is locked in, not a default that
quietly falls back elsewhere:

- The frame-count loop below points at `<video folder>/sandbox` explicitly.
- `vtt.py`'s clip length goes through `paths.py`, which resolves
  sandbox → dev → flat *per file* — so if a scene's `segment.mp4` is
  missing from `sandbox/` for some reason, it would silently read from
  `dev/` instead without saying so. If that ever happens, say so out loud
  rather than showing a number as if it came from sandbox: "scene N's
  segment isn't in sandbox — this reading is from dev/", not a silent
  substitution.

## The combined table — timing plus frame counts

**This is the same table, pulled together by hand when no page is wanted** —
an answer that belongs INSIDE a reply: one scene, a quick comparison. The
columns are the ones defined at the top of this file; the example below shows a
SUBSET of them, because `vtt.py` prints no frame counts and the shell loop
supplies only two. Add the rest from the definition when they matter.

`vtt.py` alone doesn't print frame counts, only timing. When checking a
store's sandbox in detail — confirming the editor and the sandbox agree,
or explaining why `assemble_video.py` printed `clip held` on a scene —
pull both together:

```bash
cd ~/Rentify/Video-Editor/Video-Editors

python3 -m editor_base.vtt "<video folder>"

VF="<video folder>/sandbox"
for d in "$VF"/*/; do
  name=$(basename "$d")
  [ -f "$d/segment.mp4" ] || continue
  seg=$(ffprobe -v error -count_frames -select_streams v:0 \
        -show_entries stream=nb_read_frames -of csv=p=0 "$d/segment.mp4")
  av=$(ffprobe -v error -c:v libvpx-vp9 -count_frames -select_streams v:0 \
       -show_entries stream=nb_read_frames -of csv=p=0 "$d/avatar.webm")
  echo "$name: segment=$seg avatar=$av"
done
```

Merge the two outputs into one table by scene number. **Give every scene row
a second row underneath it holding just the narration line** — the numeric
row stays scannable, and the words she actually says sit on their own line
instead of stretching the row width.

**Name the store in the column header itself — never just "scene."** More
than one store's table can be in view across a conversation, and a bare
"scene" column gives no way to tell them apart at a glance. Use
`# <Store-Name> scenes`, with the store's actual name in place of
`<Store-Name>`:

| # | Canoe-Demo scenes | clip | speech | gap | segment frames | avatar frames |
|---|---|---|---|---|---|---|
| 1 | login-and-code | 7.9s | 6.7s | 1.3s | 198 | 214 |
| | *"Enter your email, and we'll send you a 4 digit verification code you can enter here to sign in and create your account."* |
| 2 | dashboard-new-order | 3.5s | 2.3s | 1.2s | 88 | 124 |
| | *"From your dashboard, tap New Order to begin."* |

The narration row is a single cell spanning the row (markdown tables can't
truly merge cells, so leave the other columns blank rather than repeating
dashes into every one) — italicized, quoted, exactly as it reads in
`script.json`. Never retype it from memory; copy it from the VTT output or
the file itself.

**Segment and avatar frame counts matching exactly (e.g. 482/482) is not
automatically a good sign.** It can mean the avatar was correctly built to
the footage's length — or it can mean the avatar was silently trimmed short
to fit, cutting off the end of Sarah's actual recorded line. Check the
avatar's own duration against its source `narration.webm` (both frame
counts should be close to the *narration's* length, not forced to match the
segment) before trusting a clean match as evidence nothing is wrong.

## The EVTT — the editor's own live VTT panel

**A third, separate thing from the two tables above.** The Segment and Avatar
Editor has its own built-in VTT view, right in the browser, alongside the
timeline. Call this one the **EVTT** to keep it unambiguous from `vtt.py`'s
report and the combined table — three different things that all show
similar numbers, easy to conflate by accident.

⚠ **Do not change the EVTT's behavior or appearance unless specifically
asked to.** This section documents what it already does, for reference —
it is not an invitation to "improve" it. It lives in
`segment_avatar_editor/player.py` (`renderVtt()`, `paintVttRow()`,
`paintVttSum()`), served as part of the editor at `shared/serve.py`'s
`/api/vtt` route.

### What it looks like

A header bar, then one row per scene (plus bookend rows for `00-opening` and
`99-closing`, greyed out with "not a script scene — no line" — shown anyway,
because a table that silently skips rows doesn't match what's actually
playing):

```
VTT                          110.1s clip · 92.7s said · 16% dead air · 1 over 2.5s
─────────────────────────────────────────────────────────────────────────────
1  Hi, I'm Sarah. Let me show you how to place your first order with...   19.3s clip · 16.0s said · 3.3s gap
2  From your dashboard, tap New Order to [begin.]                         3.5s clip · 2.3s said · 1.2s gap
3  We need to add a person to the order. You can add yourself, or...      6.4s clip · 5.2s said · 1.2s gap
```

### What makes it different from `vtt.py`

- **Clip length comes from the LIVE timeline, not the file on disk.** The
  backend (`/api/vtt`) sends only the lines and the word-count math; the page
  itself supplies the clip length from whatever is actually on the timeline
  right now — including edits that haven't been saved yet. `vtt.py` reads the
  committed file, which is right for a report and wrong for an editor: in an
  editor, a gap that doesn't move while you add frames is a lie with a
  decimal point.
- **The line is editable in place.** Click a row to turn it into a textarea;
  typing updates the gap live (`paintVttRow` repaints as you type, before
  anything is saved). Blur saves to `script.json` — the same file
  `render_narration.py` reads, so editing here is editing what HeyGen gets
  paid to say. Esc reverts to the last saved line. A previous version is
  copied to `z_History/line-edits/` first, every time.
- **Per-word spans.** Each word in the line is its own `<span>`, which is
  what lets the currently-spoken word highlight during playback (`begin.` in
  the screenshot above) — `vtt.py`'s plain-text report has no equivalent.
- **Clicking a row jumps the timeline** to that scene's start.

### Reading the gap color

Per row, the gap is color-coded, not just printed:

| color | meaning |
|---|---|
| green (`gapOk`) | normal — under the 2.5s threshold |
| orange (`gapBad`) | over 2.5s — long enough to be worth a look |
| red (`gapNeg`) | **negative** — the line is still being said when the footage has already moved on. This is the defect that ships silently; a positive gap just holds a frame, a negative one cuts her off. |

### The header summary

`{clip}s clip · {said}s said · {dead}% dead air`, plus `· N overrun` if any
scene has a negative gap, `· N over 2.5s` if any exceed the threshold, and
`· N unsaved` if there are live edits not yet written to `script.json`.
