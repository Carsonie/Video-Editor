# Project rules

This repo makes **help videos**: a HeyGen avatar narrating over a recording of
the real Rentify UI. It holds the two editors, the build pipeline, and every
customer's `help-videos/` working files while a video is being made.

`Basic_E2E_Testing` keeps the E2E testing, the BCP work, and the customer
folders — and receives finished videos.

- **`SVM.md`** — the plan, the end state, and the traps
- **`ToDo.md`** — open work, ranked `P1`–`P4`
- **`PIPELINE.md`** — how a help video actually gets made. Read before building

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
shared/                  serve.py  frames.py  paths.py  vtt.py
build/                   the 9 tools that make the finished video
tests/                   106 checks over every endpoint
Customers/               the video data — GITIGNORED
```

Flatter than `Basic_E2E_Testing` by one level: no `video_players/`, because
nothing sits beside the players here. `paths.py` and `vtt.py` moved down into
`shared/`, which is what let that level go — they were the only reason
`serve.py` had to climb out of the tree. **Do not reintroduce a level above the
players.**

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

The whole ski-demo store is already here (2.2 GB). Both repos are on one APFS
volume, so a copy shares blocks — it took 0.16 seconds and no disk.

---

## The pipeline

`PIPELINE.md` is the full playbook — four shipped videos and every trap found
paying for them. Read it before building anything.

The short version:

```
raw_mp4/  →  cut_segments.py or the MP4 Splitter  →  dev/
          →  the Segment and Avatar Editor        →  sandbox/
          →  vtt.py            check the timing, FREE
          →  render_narration.py   THE ONLY PAID STEP
          →  assemble_video.py →  video/<store>_<title>_vNN.mp4
```

Everything after the narration render is local ffmpeg and free.

### The folders, and what each is

- **`raw_mp4/`** — the recording, whole and uncut. Imported from
  `Basic_E2E_Testing`, where `A#5` writes it after an E2E run.
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
python3 shared/serve.py --port 8860
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

```bash
python3 tests/test_editor.py
```

**30 steps, 106 checks**, about 90 seconds cold. One step per disk function,
plus a `node --check` on all three generated pages. It builds a disposable
store and deletes it — it never touches real data.

Every assertion is an exact **decoded frame count**. Every real bug this tool
has had was an off-by-a-frame that still produced a playable file: Save wrote
87 frames for an 89-frame edit for three weeks without erroring.

A run writes `tests/log_reports/editor_<HH>_<MM>_<SS>.log`. Real editing writes
`logs/editor_<YYYYMMDD>.log`. Both gitignored.

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
