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
| `.gitignore` rules for `cache/`, `logs/`, `tests/log_reports/`, and the three `z_History/` folders | without them the repo fills with regenerable video |

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

⚠ **Git LFS or not in git at all.** 155 MB of video in a normal git repo will
be slow and GitHub warns above 50 MB per file. Decide this before the first
commit, not after.

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

1. Decide the tree shape and whether the demo video is in git or LFS
2. Copy the 13 code files, keeping the `paths.py` / `vtt.py` relationship intact
3. Copy the 155 MB of demo data
4. Fix `fixture.py`'s two hard-coded paths
5. Run the checklist in §3
6. Import back into `Basic_E2E_Testing`
