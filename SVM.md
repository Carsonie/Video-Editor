# SVM — Standalone Video Migration

This repo becomes the **help-video creation repo**. All video development
happens here. `Basic_E2E_Testing` keeps the E2E testing, the BCP work and the
customer folders — and receives finished videos.

**The plan changed twice on 2026-08-26, and the second change is the bigger one.**

First the scope widened from the two editors to the whole pipeline: the editors
cut and assemble a video's parts, they do not build the finished mp4, and half
a pipeline in each repo is the shape that causes drift. So the eight build
tools came too, and the store came whole rather than trimmed.

Then the *direction* changed. This was going to be "develop here, import the
functionality back". It is not. **The pipeline stays here.** The only thing
that travels back is the finished video.

---

## The end state

```
   Basic_E2E_Testing                          Video-Editor  (this repo)
   ─────────────────                          ────────────────────────
   A#5 records an E2E run
   → help-videos/raw_mp4/  ────── import ──→  the raw recording

                                              cut · hand off · edit
                                              join · split · narrate
                                              assemble

   Customers/<Business>/<store>/  ←─ return ─  the finished video, and
   help-videos/                                nothing else
```

**Coming this way:** raw `.mp4` recordings, and every customer's
`help-videos/` working files. They live here while a video is being made.

**Going back:** the finished video product, into that customer's folder in
`Basic_E2E_Testing`. Not the working files, not the archives, not the cuts —
the product.

### Why the split is clean

Nothing in `Basic_E2E_Testing` imports this pipeline. Checked 2026-08-26:
three TypeScript files under `Master_Flows/UI/` *mention* `cut_segments.py`,
but only in comments explaining a convention they share. No code depends on
`paths.py`, `vtt.py` or any build tool.

So **trap 1 dissolves.** There is no import-back to plan for and no second copy
of `paths.py` to drift — this repo owns it now.

The one live seam is **A#5, the recorder**. It writes into
`Basic/Customers/<Business>/<store>/help-videos/raw_mp4/`, and it stays there,
because it wraps an E2E test run. That is the file this repo imports.

Source of everything below:
`~/Rentify/Basic_E2E_Testing/.claude/agent-tools/6_end-customer-help-video-creations/`

---

## 0. The tree, as built

```
Video-Editor/
├── SVM.md  setup_demo.py  .gitignore  layers.sh
├── mp4_splitter/          player.py  VERSION  __init__.py
├── segment_avatar_editor/ player.py  VERSION  __init__.py
├── shared/                serve.py  frames.py  paths.py  vtt.py  __init__.py
├── tests/                 test_editor.py  fixture.py  README.md
├── build/                 the 8 tools that make the finished video
└── Customers/             gitignored — the whole ski-demo store
```

Flatter than the source by one level: there is no `video_players/` here,
because there is nothing beside it to be distinguished from. `paths.py` and
`vtt.py` moved DOWN into `shared/`, which is what let the level go — they were
the only reason `serve.py` had to climb out of the tree.

**Proven 2026-08-26:** server starts, the splitter opens the raw recording, the
editor opens a scene layered and three on a timeline, the VTT reads 11 scenes,
and `tests/test_editor.py` passes 106/106.

---

## 1. The code — 13 files, all of it

Everything the two editors run on. No file here is optional.

### The players

| File | What it is |
|---|---|
| `video_players/mp4_splitter/player.py` | **MP4 Splitter v8** — the whole page: HTML, CSS and JS in one Python template |
| `video_players/mp4_splitter/VERSION` | `8` — rendered at the foot of the page, so the version on screen is the version in git |
| `video_players/mp4_splitter/__init__.py` | makes it importable |
| `video_players/segment_avatar_editor/player.py` | **Segment and Avatar Editor v29** — holds TWO templates: `PAIR_TEMPLATE` (one scene, layered) and `SEQ_TEMPLATE` (several, on a timeline) |
| `video_players/segment_avatar_editor/VERSION` | `29` |
| `video_players/segment_avatar_editor/__init__.py` | makes it importable |

### Shared

| File | What it is |
|---|---|
| `video_players/shared/serve.py` | **The one server, and every endpoint.** 28 of them. Also holds `BROWSE_HTML` inline — there is no separate browse page to copy |
| `video_players/shared/frames.py` | Frame extraction, the frame map, the edit maths, audio extraction |
| `video_players/shared/__init__.py` | makes it importable |

### The layer above — needed, and easy to miss

`serve.py` reaches **up out of** `video_players/` for two modules. Copy them or
nothing runs:

| File | Why |
|---|---|
| `paths.py` | Resolves every scene file (sandbox → dev → flat), and owns `archive_contents()` — the generation archives both editors write |
| `vtt.py` | `serve.py` imports it for `words()` alone, but imports the **whole module**, so it must be present and importable |

### Tests

| File | What it is |
|---|---|
| `video_players/tests/test_editor.py` | 30 steps, 106 checks — every endpoint plus a `node --check` on all three generated pages |
| `video_players/tests/fixture.py` | Builds a disposable store from real ski-demo footage |
| `video_players/tests/README.md` | What is covered and what cannot be |

⚠ `fixture.py` **hard-codes a path into ski-demo's `dev/`** for its source clips,
and a `REPO` walk of five `..` levels to find `Customers/`. Both need rewriting
for this repo's shape — see §4.

### Not code, but copy them

| File | Why |
|---|---|
| `video_players/layers.sh` | helper script that lives with the players |
| `.gitignore` — **already written** | ignores `Customers/`, `cache/`, the logs and every `z_History/` |
| `setup_demo.py` — **already written** | copies the demo data in |

### `build/` — the finished video

| File | What it does |
|---|---|
| `assemble_video.py` | builds the finished mp4 and archives the older ones |
| `render_narration.py` | the HeyGen renders — **the only step that costs money** |
| `onepass_narration.py` | one-pass narration |
| `make_scene_overlays.py` | Sarah over each scene |
| `morph_avatar_corner.py` | the 1.2s move to the corner |
| `build_sarah_opening.py` | intro → morph → corner |
| `export_bookends.py` | the opening and closing |
| `fade_frames.py`, `cut_segments.py` | frame maths and slicing |

They import each other AND `paths`. `paths.py` is in `shared/` here, so four of
them — `assemble_video`, `export_bookends`, `make_scene_overlays`,
`onepass_narration` — carry one extra `sys.path` line pointing at `../shared`.
One home for `paths.py` beats two that drift.

`assemble_video.py` needs **Pillow** (installed: 12.2.0).

### The HeyGen key

Looked for in this order:

1. `HEYGEN_API_KEY` in the environment
2. `<repo>/.env.local`
3. `<repo>/Help_Videos/HeyGen/.env.local`

Environment first, because it is the one place a secret can live that no repo
can accidentally swallow. `.env.local` is gitignored — the rule was written
before the file was created, not after.

It used to be a single hardcoded path three levels above the tool, which
resolved to the **home directory** once these moved here. The key was simply
not found, and nothing said why.

⚠ **`render_narration.py` is the only step that spends money.** Every clip is a
real charge, and HeyGen speaks the line exactly as written — a typo costs
another render. Proofread with `vtt.py` first; it is free.

---

## 2. The demo data — ski-demo

The editors resolve everything under a `Customers/` root. The demo needs one
store, one video folder, in this exact shape:

```
Customers/Rentify Demos Corp/ski-demo/help-videos/
├── raw_mp4/<one recording>.mp4          ← the MP4 Splitter's input
└── videos/01-first-time-ordering/
    ├── dev/<NN>-<label>/                ← segment-v6.mp4, avatar-v1.webm,
    │                                       narration-v1.webm, scene.json
    ├── sandbox/<NN>-<label>/            ← segment.mp4, avatar.webm, narration.webm
    └── video/script.json                ← the scene list and the lines
```

| What | Size | Needed because |
|---|---|---|
| `dev/` — 12 scenes, 48 files | **48 MB** | where a cut lands; the editor's fallback source |
| `sandbox/` — 14 folders, 49 files | **58 MB** | the Segment and Avatar Editor's whole scope. Includes the two bookends `00-opening` and `99-closing`, which are NOT script scenes |
| `video/script.json` | **9 KB** | the scene list, the lines, and `words_per_second` — the VTT is nothing without it |
| One raw recording | **48 MB** | the splitter needs something to cut. Take the SMALLEST: `ski-demo_owner-one-item_dev_19-17-45_v5.mp4` |

**Demo total: about 155 MB.**

### Do NOT copy

| | Size | Why not |
|---|---|---|
| the other 9 raw recordings | 1.5 GB | one is enough to demonstrate cutting |
| `video/*_vNN.mp4` — 14 finished builds | 74 MB | outputs, not inputs |
| `video/z_History/` | 96 MB | archives of those outputs |
| every `sandbox/*/z_History/` | ~20 MB | per-file archives; the editor recreates them |
| `onepass/` | 27 MB | narration renders, nothing the editors read |
| `video_players/cache/` | — | regenerated from the source video on first open |

Full ski-demo is **2.2 GB**. The demo is **155 MB** — about 7%.

### The video is NOT in git — decided 2026-08-26

`setup_demo.py` copies it in; `Customers/` is gitignored.

Not a size decision. `dev/` and `sandbox/` are the folders the editors WRITE
to, so running the tools changes 106 MB of files. Git keeps every version of
every file forever and cannot pack video down, so each commit of a working
state would add its full size again — permanently, since removing it later
means rewriting history.

```bash
python3 setup_demo.py          # copy what is missing
python3 setup_demo.py --force  # throw it away and copy it again
python3 setup_demo.py --check  # say what is there, copy nothing
```

**Updated 2026-08-26: the WHOLE store is here, not the 150 MB subset.**
2.2 GB, 801 files, cloned in **0.16 seconds** and using **no extra disk** — the
volume is APFS, so a copy on it shares blocks until something changes. The
trimmed subset existed to keep a git repo small; nothing is committed, so there
was nothing to keep small.

`setup_demo.py` still copies the 150 MB subset, which is all the editors and
the tests need. To bring the whole store instead:

```bash
cp -Rc "~/Rentify/Basic_E2E_Testing/Customers/Rentify Demos Corp/ski-demo" \
       "Customers/Rentify Demos Corp/ski-demo"
```

The tracked repo stays **under 400 KB**.

LFS was the alternative and was not taken: it needs installing before anyone
can clone, GitHub's free allowance is 1 GB stored and 1 GB a month
transferred, and it solves a problem this repo does not have.

The cost, stated plainly: **this repo is not self-contained.** On a machine
that has never had `Basic_E2E_Testing`, point the script at a copy of that
store with `--from`, or bring the data by hand.

`.gitkeep` files are deliberately not copied — they exist so git tracks those
folders in the other repo, and `Customers/` is ignored here.

---

## 3. What "working" means — the demo checklist

The migration is done when all of these pass **in this repo**:

- [ ] `python3 video_players/shared/serve.py --port 8842` starts and prints its
      browse root and session-log path
- [ ] the browse page lists the ski-demo store
- [ ] **MP4 Splitter**: opens the raw recording, plays with sound, marks,
      ＋/− Frame, ＋/− Zone, Undo, Loop Zone, the segment list matches the
      slider bands, Cut writes to `dev/_cuts/`
- [ ] **Hand off** deposits into `dev/`, archiving what was there to
      `dev/z_History/<date>-v_N/`
- [ ] **Segment and Avatar Editor**: opens a scene layered, and 2+ scenes as a
      timeline; frame and zone edits; Save writes the exact frame count; Cut;
      Join; Split; the save-as-a-set lock; the VTT reads and its lines save
- [ ] `python3 video_players/tests/test_editor.py` → **30 steps, 106 checks, PASS**

---

## 4. Known traps

Each of these has already cost time once.

1. ~~**The two reach-ups.**~~ **Settled 2026-08-26.** `paths.py` and `vtt.py`
   now live in `shared/`, beside `serve.py`, and the `video_players/` level is
   gone — the players sit at the repo root. Both `sys.path` climbs are deleted.

   ~~The cost, for import-back~~ — **no longer applies.** There is no
   import-back: the pipeline stays here. Nothing in `Basic_E2E_Testing` imports
   it, so there is no second copy to drift.

2. **`fixture.py` still hard-codes ski-demo's `dev/`** for its source clips.
   The five-`..` walk to `Customers/` is fixed — it is one level here — but the
   clip path remains a hard-coded reach into the demo store.

3. **`safe_join()` pins everything under `Customers/`.** Anything outside it is
   unreachable by every endpoint. `find_repo_root()` walks up looking for a
   `Customers/` folder, so it lands on this repo root by itself — but the demo
   data still has to sit under that name. Making the root configurable is the
   better fix and belongs in this repo.

4. **The pages are Python `.format()` templates.** Every CSS and JS brace is
   doubled `{{ }}`, and a stray apostrophe in a single-quoted JS string kills
   the whole page silently. That shipped once. `test_editor.py`'s step 30 is
   the guard — do not drop it.

5. **Alpha WebM lies to ffprobe.** An avatar track reports `yuv420p` unless the
   decoder is forced with `-c:v libvpx-vp9`. Any new frame-counting code must
   force it.

6. **The cache is keyed on the source path.** Moving the demo data invalidates
   every cached extraction — expected, but the first open is then slow.

---

## 5. Order of work

Open items are tracked in `ToDo.md`, ranked. This is the sequence.


1. ~~Decide whether the demo video is in git or LFS~~ — **done**: neither,
   `setup_demo.py` copies it and `Customers/` is gitignored
2. ~~Decide the tree shape~~ — **done**: flat, `paths.py`/`vtt.py` in `shared/`
3. ~~Copy the 13 code files~~ — **done**, keeping the `paths.py` / `vtt.py` relationship intact
4. ~~Copy the demo data~~ — **done**, `python3 setup_demo.py`
5. ~~Fix `fixture.py`'s repo-root walk~~ — **done**; its ski-demo clip path
   is still hard-coded
6. Walk the checklist in §3 by hand in a browser — the endpoints pass, the
   controls have not been clicked here yet
7. Cut the last cords, in this order:
   - a `CLAUDE.md` here, so a session in this repo starts informed
   - the `A#6` pipeline knowledge, which lives in `Basic`'s agent doc today
   - make `Customers/` a configurable root rather than a fixed name
   - a script that imports a raw recording FROM `Basic`
   - a script that returns a finished video TO the right customer folder
8. Bring the other customers' `help-videos/` over as they are worked on
