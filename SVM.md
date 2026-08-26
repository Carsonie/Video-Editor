# SVM — Standalone Video Migration

Lifting the two video editors out of `Basic_E2E_Testing` into this repo, with
ski-demo as the worked example, so development happens here and the finished
functionality is imported back.

Source of everything below:
`~/Rentify/Basic_E2E_Testing/.claude/agent-tools/6_end-customer-help-video-creations/`

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

Measured: **88 files, 150 MB, 0.2 seconds** (same filesystem, so the copies are
cheap). The tracked repo stays **15 KB**.

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

1. **The two reach-ups.** `serve.py` does `sys.path.insert` twice to find
   `paths.py` and `vtt.py` one directory above `video_players/`. Flatten the
   layout here and those imports break — decide the shape first.

2. **`fixture.py` hard-codes ski-demo's `dev/`** for its source clips, and
   counts five `..` to reach `Customers/`. Both are wrong the moment the tree
   changes.

3. **`safe_join()` pins everything under `Customers/`.** Anything outside it is
   unreachable by every endpoint. The demo data must sit under a `Customers/`
   root even here, or the root has to be made configurable — which is the
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

1. ~~Decide whether the demo video is in git or LFS~~ — **done**: neither,
   `setup_demo.py` copies it and `Customers/` is gitignored
2. Decide the tree shape (see trap 1)
3. Copy the 13 code files, keeping the `paths.py` / `vtt.py` relationship intact
4. ~~Copy the demo data~~ — **done**, `python3 setup_demo.py`
5. Fix `fixture.py`'s two hard-coded paths
6. Run the checklist in §3
7. Import back into `Basic_E2E_Testing`
