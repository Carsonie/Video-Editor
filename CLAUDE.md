# Project rules

This repo makes **help videos**: a HeyGen avatar narrating over a recording of
the real Rentify UI. It holds the editors, the build pipeline, and every
customer's `help-videos/` working files while a video is being made.

`Basic_E2E_Testing` keeps the E2E testing, the BCP work, and the customer
folders — and receives finished videos.

- **`SVM.md`** — the plan, the end state, and the traps
- **`ToDo.md`** — open work, ranked `P1`–`P4`
- **`PIPELINE.md`** — how a help video actually gets made. Read before building
- **`docs/`** — the HeyGen knowledge `PIPELINE.md` cites, and `Sarah/` her standards

---

## When Carson asks for a "vtt" / "VTT"

Read **`.claude/skills/vtt/SKILL.md`** first, every time. It is the source of
truth for what "show me the vtt" means (a combined table — timing, frame
counts, and the narration line under each row — not `vtt.py`'s plain output),
and it also defines the EVTT (the editor's own live panel) as a separate,
third thing. Don't rebuild this from memory of a past answer; the skill is
the one place this is written down, and it can change.

---

## Working with the Avatar Editor, or anything about Sarah

Read **`.claude/skills/sarah-library/SKILL.md`** first, every time —
before editing anything in `avatar_editor/`, before touching `Sarah/` or
any store's own `sarah_clips/`, and before answering a question about
Sarah's clips, her standard poses, or idle footage. It is the single
source of truth for what's common vs. per-store, what the Avatar Editor's
two panels each do, and the traps already paid for once (a stale path in
`build/assemble_video.py` that silently resolved to nothing; a folder one
level too deep that a flat listing never saw). Don't reconstruct any of
this from memory of a past answer — the skill is the one place it's
written down, and it changes as the library does.

---

## When Carson asks to open, launch, start, or run an editor

Read **`.claude/skills/editor-launchers/SKILL.md`** first, every time. Six
separate tools now — MP4 Splitter, Segment and Avatar Editor, Frame
Blender, Avatar Editor, the still-existing old combined server
(shared/serve.py, port 8842 — cannot be removed, Frame Blender/Avatar
Editor both import plain functions out of it), and the next-gen web
editor — each its own process, and the next-gen one is secretly two
processes — skip the skill and it's easy to start its UI without its API
and get a page full of 502s. "Run the editors"/"run all 4 editors" is
Carson's own standing phrase for four specific ones of these (not the old
combined server, not the next-gen editor) — the skill says which. The
launch.json they all run from lives in
`Basic_E2E_Testing`, not here.

---

## Editor changes stay inside the one editor in scope

When a task is about one editor, code changes go in that editor's own
files only. The other editors — of MP4 Splitter, Segment and Avatar
Editor, Frame Blender, Avatar Editor — do not get touched, even if the
same fix would technically apply to them too. Only Carson can widen the
scope, and only by saying so directly in the chat, in that same
conversation.

**Why:** the four editors were deliberately split apart into separate,
duplicated code (2026-09-02) so that a change in one could never break
another. Quietly "fixing it everywhere while I'm in here" defeats that —
it re-links tools that were split apart on purpose.

**How to apply:** before editing any file outside the editor named in the
current task, stop and ask Carson first, even if the change looks small,
obviously correct, or identical to one already approved for another
editor.

### The one exception: `editor_base/`

`editor_base/` is the single shared package every editor may import
from — `frames.py`, `paths.py`, `vtt.py`. It exists because those three
files were duplicated three times over (776 + 465 + 300 lines each) and
differed by **two lines of real code**: the cache folder name, and which
player module writes a clip's page. Both are now configuration
(`use_cache()`, `use_player()`), set by each editor at import time.

Carson chose this on 2026-09-03 (Option A) with four conditions, and they
are not optional:

1. **Pure functions and constants only.** No routes, no `Handler`, no
   `self`, nothing that knows about HTTP. `shared/serve.py` is the
   cautionary tale — it began as helpers and grew into a server four
   tools could not be untangled from.
2. **It has its own suite**, `tests/test_editor_base.py`, which enforces
   that purity mechanically.
3. **A change here runs all six suites, not one.** This is the trade the
   package makes: a change in `editor_base/` is not "one editor's
   change" — it can break four tools at once.
4. **It is the only exception.** Everything else still stays inside the
   one editor in scope.

`shared/paths.py`, `shared/frames.py` and `shared/vtt.py` still exist
under those names but are **thin re-export shims**, kept solely so the
nine scripts in `build/` keep importing them unchanged — one of which,
`build/assemble_video.py`, must not be edited at all. Nothing new should
import a shim.

---

## ⚠ Money: ask before every HeyGen render

`build/render_narration.py` is the **only** thing here that spends real money —
about $0.21–$0.34 a scene. Before running it, ask with **one line and nothing
else**:

```
I need to pay HeyGen for this.  The COST should be around: $X.XX  Yes (Y) or No (N)
```

Then stop and wait for `Y` or `N`.

- The number comes from `--dry-run`, never an estimate.
- Ask **per run**. A yes for one render is not a yes for the next.
- `--force` re-renders clips that already exist and therefore **pays again** —
  name the exact scenes and the reason before asking.
- HeyGen speaks each line exactly as written, so a typo costs another render.
  **Read the VTT first — it is free.**

A spend request buried in a paragraph gets skimmed. One line cannot be.

The key is in `.env.local` (gitignored) or `HEYGEN_API_KEY` in the environment.
Never print it, never commit it.

---

## The layout

```
mp4_splitter/            MP4 Splitter — cut a recording into segments
segment_avatar_editor/   Segment and Avatar Editor — finish them
editor_base/             frames.py  paths.py  vtt.py — the ONE shared package
shared/                  serve.py, plus re-export shims for build/
build/                   the tools that make the finished video
Sarah/                   her standards, and the clips every video reuses
tests/                   633 checks over six suites, one per server + editor_base
Customers/               the video data — GITIGNORED
```

Flatter than `Basic_E2E_Testing` by one level: no `video_players/`, because
nothing sits beside the players here. **Do not reintroduce a level above the
players.**

---

## ⚠ Build the SCENES first, and prove them, before joining

**Never build the whole video to find out whether it works.**

```bash
python3 build/build_scenes.py "<video folder>"            # every scene, checked
python3 build/build_scenes.py "<video folder>" --join 28  # only once they pass
```

Each scene is checked three ways — decoded frame count against its avatar's,
duration against that frame count, audio against the picture — and the tool
**refuses to join while any scene fails**. That refusal is the point of it.

Four whole-video builds shipped faults that one scene would have shown in
seconds: an 11.4-second hole (v23), a doubled opening (v25), a section cut 2.4s
short and a voice that never caught up (v26). Each cost a full rebuild and a
viewing to find. A joined video hides its faults inside 110 seconds; a scene
cannot.

**Whatever is in `sandbox/` after Carson's editing pass is the master version.**
Build that. Do not composite a different file because it looks more correct —
that mistake is exactly what produced v23 through v26.

---

## This repo owns ALL video work. `Basic_E2E_Testing` gets the release only.

Split 2026-08-28. Over there, a store's `help-videos/` holds finished videos and
a README, and nothing else — so "which file does a customer get?" is answered by
the folder. Before the split both repos held the same working files and
ski-demo's customer folder carried v10 through v22 beside 2.2 GB of raw
recordings.

```bash
python3 build/release_video.py "<video folder>" --version 28
```

**That is the only thing that may write there.** It refuses a build whose clock
and frame count disagree, and refuses to put different bytes under a version
number already released.

Raw captures now land here directly — `record_flow.ts` in that repo writes into
this one's `raw_mp4/` (override with `VIDEO_EDITOR_REPO`).

---

## Nothing under `Customers/` is in git

150 MB–2.2 GB of video, gitignored. `dev/` and `sandbox/` are the folders the
editors WRITE to, and git keeps every version of every file forever and cannot
pack video down — one commit of a working state would add its full size again,
permanently.

```bash
python3 setup_demo.py          # the 150 MB subset the editors and tests need
python3 setup_demo.py --check  # what is here, copies nothing
```

**`z_History` is therefore the only undo there is**, which is also why it grows
without limit. Trim it:

```bash
python3 build/trim_history.py "Customers"           # shows, deletes nothing
python3 build/trim_history.py "Customers" --apply   # keeps the 3 newest
```

It removes every `z_History` nested inside another one first — a backup does not
keep backups, and that alone was 514 MB of ski-demo's 1.3 GB.

The whole ski-demo store is already here (2.2 GB). Both repos are on one APFS
volume, so a copy shares blocks — it took 0.16 seconds and no disk.

---

## The pipeline

`PIPELINE.md` is the full playbook — every trap found paying for it, and the
nine steps in order. **Twenty-three more videos follow it.** Read it before
building anything; if a step there cannot be followed cold, fix it there.

The short version:

```
raw_mp4/  →  MP4 Splitter (or cut_segments.py)     →  dev/
          →  copy BY HAND                          →  sandbox/
          →  vtt.py + preview_narration.py    check the timing, FREE
          →  render_narration.py              THE ONLY PAID STEP
          →  morph_avatar_corner.py           →  avatar.webm
          →  the Segment and Avatar Editor    Carson adjusts
          →  build_scenes.py                  every scene, checked
          →  build_scenes.py --join <N>       →  video/<store>_<title>_v<N>.mp4
          →  release_video.py                 →  Basic_E2E_Testing
```

Everything after the narration render is local ffmpeg and free.

⚠ **`assemble_video.py` is not in that list.** It was the whole-video builder
until 2026-08-27 and it composited `narration.webm` — the raw 1920×1080 HeyGen
render — while the editor shows `avatar.webm`. So every frame balanced in the
editor was balancing a file the build never opened. It is kept for its opening
and closing handling; it is not how a video gets built.

### The folders, and what each is

- **`raw_mp4/`** — the recording, whole and uncut. `A#5` writes it here
  directly after an E2E run, from the other repo.
- **`dev/`** — where a video starts. The splitter deposits its named cut here.
  Files are versioned: `segment-v1.mp4`.
- **`sandbox/`** — the Segment and Avatar Editor's ground. Files carry no
  version: `segment.mp4`.
- **`_cuts/`** — the splitter's numbered output, inside `dev/`. Not yet scenes.
- **`z_History/`** — each of `dev/`, `sandbox/` and `video/` keeps its previous
  generation, as `<YYYY-MM-DD>-v_N`. **`dev` is MOVED, `sandbox` is COPIED** —
  a deposit replaces `dev` wholesale, while the sandbox is edited one scene at
  a time and moving it would take away the scenes a save is not touching.

⚠ **Nothing moves `dev` → `sandbox`.** That is a manual copy, on purpose.

---

## The two editors

```bash
python3 shared/serve.py --port 8842
```

One server, both players, 28 endpoints. It prints its browse root and its
session-log path on start.

- **MP4 Splitter** — mark, ＋/− Frame, ＋/− Zone, Undo, Loop Zone, the segment
  list, Cut, and the hand-off into `dev/`.
- **Segment and Avatar Editor** — one scene layered, or several on a timeline;
  frame and zone edits, marks, Save, Cut, Join, Split, and the VTT panel where
  a scene's line is edited in place.

### Changing a player — the commit rules

A player's history has to read as that player's changelog:

1. **One player per commit.** Never two. Shared code is its own commit.
2. **Bump that player's `VERSION`** in the same commit — it is rendered at the
   foot of the page, so the version on screen is the version in git.
3. **Subject:** `<Player Name> v<N> ADDED: <what it does now>`

Write what the player *does now*, not what you edited. `ADDED:` is the form
even when the change is a fix. A restructure is not an `ADDED:` — commit that
plainly and leave `VERSION` alone.

### The pages are Python `.format()` templates

Every CSS and JS brace is doubled `{{ }}`. Two traps that have both shipped:

- A stray **apostrophe** in a single-quoted JS string kills the whole page
  silently — every control dies, including Play. Use a backtick literal.
- `\n` in the source becomes a real newline. Inside a backtick literal that is
  legal; inside a single-quoted string it is a syntax error. Write `\\n`.

**Always check the generated JavaScript, not just that the Python parses.**
`tests/test_editor.py` step 30 does exactly this. Do not drop it.

---

## Tests

**Five suites now, one per server** — split 2026-09-02 alongside logging
(below), so each editor's own dispatch table, cache and log get checked
against the real standalone process people actually run, not only against
the code they started as a copy of.

```bash
python3 tests/test_editor.py                    # shared/serve.py, port 8842 (old combined) — 167 checks
python3 tests/test_mp4_splitter.py               # mp4_splitter/serve.py, port 8845          — 83 checks
python3 tests/test_segment_avatar_editor.py      # segment_avatar_editor/serve.py, port 8846  — 91 checks
python3 tests/test_frame_blender.py              # frame_blender/serve.py, port 8843          — 50 checks
python3 tests/test_avatar_editor.py              # avatar_editor/serve.py, port 8844           — 141 checks
```

`test_editor.py` is the deepest one — one step per disk function, plus a
`node --check` on every generated page, about 90 seconds cold. The four
per-editor suites don't re-derive that same depth (their target code
started as a literal copy of shared/serve.py's own, already proven there);
they exist to prove the STANDALONE process — its own trimmed routes, its
own cache directory, its own session log — actually works, and that a
route the split deliberately dropped is truly gone (404), not just
unreachable by accident. Each builds its own disposable store and deletes
it — none of the five ever touches real data.

Every assertion is an exact **decoded frame count**. Every real bug this
tool has had was an off-by-a-frame that still produced a playable file:
Save wrote 87 frames for an 89-frame edit for three weeks without
erroring.

A run writes `tests/log_reports/editor_<HH>_<MM>_<SS>.log`. Real editing
writes to a log **dedicated to whichever editor did it** (also split
2026-09-02, so one editor's actions are never interleaved with another's):
`logs/editor_<date>.log` for the old combined server, and `logs/
mp4_splitter_<date>.log` / `segment_avatar_editor_<date>.log` /
`frame_blender_<date>.log` / `avatar_editor_<date>.log` for the standalone
four. All gitignored.

### If a check fails

Read the **first** failure, not the list. The checks share state on purpose, so
one broken call cascades — a bad `side` value once failed five assertions that
each looked like a different bug.

---

## Two things ffprobe will lie to you about

1. **An alpha WebM reports `yuv420p`** unless the decoder is forced with
   `-c:v libvpx-vp9`. Any new frame-counting code must force it.
2. **VP9 has no frame count in its container.** Count decoded frames.

And in ffmpeg: use `-frames:v`, never `-t`. A duration cutoff drops the frame
that lands on the boundary — that is the 87-vs-89 bug.
