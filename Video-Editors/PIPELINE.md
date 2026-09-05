# PIPELINE — how a help video gets made

> **Run everything below from `Video-Editors/`.** The root was split on
> 2026-09-04 into `Customers/` and `Video-Editors/`; every `python3 build/...`
> and `python3 shared/...` here is written from inside the latter. A path
> starting `Customers/` is the exception — that folder did not move, so from
> here it is `../Customers`. See the repo's `CLAUDE.md`.



**Four stores, six E2E scenarios each — 24 help videos.** Video 01,
*First Time Ordering*, is built for all four stores and released for three
of them; videos 02–06 have not been started for any. Every one of them
follows this file. `ToDo.md` P1.3 has the current state, store by store —
including the one that is built but not released.

If a step here cannot be followed cold, that is a defect in this file — fix
it here rather than working around it.

Rewritten 2026-08-28. The version before that had grown into a record of four
weeks of struggle: three dated session logs correcting each other, a `final/`
folder no store uses, an `assemble_video.py` build that was abandoned, and a
HeyGen-native pivot that was tried and dropped. It is at
`docs/z_History/PIPELINE_pre-2026-08-28.md`. **Nothing in it is instructions.**

---

## The words, used exactly

| Term | What it is |
|---|---|
| **segment** | a slice of demo footage. Silent. No avatar. |
| **scene** | one segment **plus its narration line**. The unit of work. |
| **avatar.webm** | Sarah as the editor shows her: 1152², VP9 alpha, corner-placed, carrying the audio. **This is what a build composites.** |
| **narration.webm** | the raw 1920×1080 HeyGen render. An input to the avatar, never to a build. |
| **e2e N** | one of the five rental-flow tests. Never "Test N". |
| **Add-V** | the `YY-M-D_v<N>` backup naming, sequence resetting daily. |

A scene has no file of its own. It is a row in `script.json` plus a folder in
`sandbox/`.

---

## ⚠ Money: ask before every HeyGen render

`build/render_narration.py` is the only thing here that spends real money —
about $0.21–$0.34 a scene. Before running it, ask with **one line and nothing
else**:

```
I need to pay HeyGen for this.  The COST should be around: $X.XX  Yes (Y) or No (N)
```

Then stop and wait for `Y` or `N`. The number comes from `--dry-run`, never an
estimate. Ask **per run** — a yes for one render is not a yes for the next.
`--force` re-renders clips that already exist and therefore **pays again**; name
the exact scenes and the reason before asking.

HeyGen speaks each line exactly as written, so a typo costs another render.
**Read the VTT first — it is free.** So is `build/preview_narration.py`, which
speaks the lines in the Mac's own voice over the real footage, and is the right
way to find a line that is four seconds too long.

The key is in `.env.local` (gitignored) or `HEYGEN_API_KEY`. Never print it,
never commit it.

---

## ⚠ THE DIRECTIVE: build the scenes first, and prove them, before joining

**Never build the whole video to find out whether it works.**

```bash
python3 build/build_scenes.py "<video folder>"            # every scene, checked
python3 build/build_scenes.py "<video folder>" --join 28  # only once they pass
```

`build_scenes.py` refuses to join while any scene fails. That refusal is the
point of the tool.

This is not tidiness. Four whole-video builds shipped faults that one scene
would have shown in seconds:

| Build | The fault | Where it actually was |
|---|---|---|
| v23 | an 11.4-second hole | one scene's narration was transparent for 285 frames |
| v25 | the opening played twice | scene 1 already contained the opening |
| v26 | a section cut short, then the voice fell behind | one segment 60 frames shorter than its avatar |
| v27 | — | first build with frames, clock and audio all correct |

Each cost a full rebuild and a viewing to find. **A joined video hides its
faults inside 110 seconds. A scene cannot.**

---

## Where things live: two repos, one job each

```
Video-Editor/          ALL video development. Every working file.
Basic_E2E_Testing/     released videos only — one file per store, plus a README
```

Split 2026-08-28. Before it, both repos held the same working files and the
customer folder accumulated every attempt: ski-demo's held v10 through v22 next
to 2.2 GB of raw recordings and sandbox scenes, and nothing said which file a
customer would be served. Now the answer is folder-shaped — **if it is in the
store's `help-videos/` over there, it shipped.**

`build/release_video.py` is the only thing that may write there.

```
Customers/<Business>/<store>/help-videos/
  raw_mp4/                     the recordings, whole and uncut
  videos/<NN-slug>/            ONE video. A store has several.
    dev/<NN-label>/            the splitter's named cut. Versioned: segment-v6.mp4
      _cuts/                   the splitter's numbered output. Not yet scenes.
    sandbox/<NN-label>/        the editor's ground. Unversioned: segment.mp4
      z_History/               Add-V snapshots of the whole sandbox
    video/                     finished builds, script.json, script_v<N>.json
    z_History/
```

⚠ **Nothing moves `dev` → `sandbox`.** That is a manual copy, on purpose. The
editor reads `sandbox` only and never falls back to `dev`, which is what stops
an edit looking like it worked when it went somewhere else.

⚠ **Never hardcode a folder name.** Ask `shared/paths.py`. A hardcoded folder
that no longer exists does not error — it reads as "no files", which looks like
an empty store.

**bike-demo, canoe-demo and alpine-sports are still on the old `final/`
layout.** They came across from `Basic_E2E_Testing` on 2026-08-28 exactly as
they were. Migrate one by moving files, never by editing code.

---

## The eight steps

Only step 5 spends money. Everything else is local ffmpeg and free.

```
 1  record            A#5, in Basic_E2E_Testing        → raw_mp4/
 2  split             MP4 Splitter                     → dev/
 3  copy              by hand                          → sandbox/
 4  write the lines   script.json  +  vtt.py           (free, do it twice)
 5  render Sarah      render_narration.py              ($, ASK FIRST)
 6  place Sarah       morph_avatar_corner.py           → avatar.webm
 7  adjust            Segment and Avatar Editor        (Carson's step)
 8  build             build_scenes.py, then --join     → video/
 9  release           release_video.py                 → Basic_E2E_Testing
```

### 1. Record — always localhost, never a live remote

A recording made against live-remote creates a **real production order in a
customer's store**. `A#5` records against `http://localhost:8080` with the dev
servers pointed at the store, and that is the only correct target.

```bash
node Local_Host/manage-servers.js store <slug>   # in Basic_E2E_Testing
node Local_Host/manage-servers.js start
```

Localhost serves **one store at a time**. A mock checkout there is correct, not
a misconfiguration.

A "first time ordering" video also needs the renter's dashboard **empty** —
purge that renter's orders for that store from the local DB first, with a
`sqlite3 .backup` taken beforehand. On ski-demo, `harry_potter` had 74.

The capture lands in **this repo's** `raw_mp4/` directly (`record_flow.ts`,
changed 2026-08-28).

### 2. Split the recording into segments

By eye, in the MP4 Splitter — mark, ＋/− Frame, ＋/− Zone, Loop Zone, Cut, then
the hand-off into `dev/`.

```bash
python3 shared/serve.py --port 8842
```

`build/cut_segments.py` can do it from flow-log stamps instead, but it must
**snap forward** from each stamp to the first settled frame. The 2026-08-21 cut
was made from raw ▶ stamps with no snap and every segment opened on the tail of
the previous screen — scene 1 opened on desktop wallpaper. Snap offsets on a
comparable run ranged +0.26s to +3.15s, so it is not a constant.

### 3. Copy `dev` → `sandbox`

By hand. See the warning above.

### 4. Write the lines — `script.json` is the copy

**It lives at `video/script.json`.** Every line, the segment it belongs to, and
the measured `words_per_second` (3.44 for Sarah). **Edit lines here and nowhere
else.** A line quoted into a doc or into chat is a copy that will drift from
what was actually rendered.

`script_v<N>.json` beside it is a **record, not an input** — the script that
produced `..._v<N>.mp4`, snapshotted by `build_scenes.py --join`.

Two free checks, both worth running before spending anything:

```bash
python3 build/preview_narration.py "<F>"   # hear it, over the real footage
python3 shared/vtt.py "<F>"                # measure it
```

**A short line is fine; a cut line is not.** If a segment outlasts its
narration, Sarah simply waits. If the line outlasts the segment, the **segment
is held** — `build_scenes.py` clones its last frame automatically. Words are
the content; the demo is never sped up and narration is never cut.

### 5. Render Sarah — the only paid step

```bash
python3 build/render_narration.py "<F>" --dry-run   # get the number
# ask the one line, wait for Y
python3 build/render_narration.py "<F>"
```

Writes `narration.webm` per scene: the raw 1920×1080 HeyGen render.

### 6. Place her in the corner

```bash
python3 build/morph_avatar_corner.py "<F>"
```

Writes `avatar.webm` — 1152², corner 320px bottom-right, alpha intact. **This
is the file everything downstream reads.**

Sarah is only ever in one of three shapes, and they are known in advance:
seated (full frame, the opening), the ~30-frame transition, and the corner.
`build/qualify_avatar.py` measures every frame against those and reports
anything else. It also confirms that a segment frame and its matching avatar
frame both exist before a build starts — the check that would have caught v23's
hole.

### 7. Adjust — Carson's step, in the editor

```bash
python3 shared/serve.py --port 8842
```

Frame and zone edits, marks, Join, Split, Solo, the VTT panel, **Save Scenes**
(this timeline → sandbox), **Save All** (every scene → sandbox), **Backup
Scenes** (an Add-V snapshot into `sandbox/z_History/`).

**Whatever is in the sandbox after this step is the master version.** Build
that. Do not second-guess it against `dev/`, and do not composite a different
file because it looks more correct — that mistake is what produced v23 through
v26.

### 8. Build — scenes first, then join

```bash
python3 build/build_scenes.py "<F>"                    # check every scene
python3 build/build_scenes.py "<F>" --scene 4 --rebuild  # fix one
python3 build/build_scenes.py "<F>" --join 28          # only once they pass
```

Each scene is written to `video/<label>_v1.mp4` and checked three ways: decoded
frame count against the avatar's, duration against the frame count, and audio
against the picture. See "the four rules" below for why each one is there.

### 9. Release

```bash
python3 build/release_video.py "<F>" --version 28
```

Copies that one build into the store's `help-videos/` in `Basic_E2E_Testing`
and stands the previous release down into `z_History/`. It refuses a build
whose clock and frame count disagree, and refuses to put different bytes under
a version number that is already released.

⚠ **Delivery is still blocked.** `Rentify_v10` has no way to serve a help video
(`ToDo_Rentify_v10.md` V3). Videos can be built and released; they cannot yet
reach a customer.

---

## The four rules ffmpeg cost real defects to learn

**1. `-frames:v N`, never `-t`.** A duration cutoff drops the frame that lands
on the boundary. Save wrote 87 frames for an 89-frame edit for three weeks
without erroring. `shortest=1` dropped one the same way.

**2. Force the VP9 decoder BEFORE the input, and only for a WebM.**

```bash
ffmpeg -c:v libvpx-vp9 -i avatar.webm ...
```

Without it an alpha WebM's transparency is silently dropped and ffprobe reports
`yuv420p`. **With it a still PNG cannot be opened at all** — so the decoder
follows the file, it is not a constant. VP9 also has no frame count in its
container; count decoded frames.

`format=yuva420p` belongs in the **filter chain**, not in `-pix_fmt`.

**3. A clock is stamped per piece, never on the join.** `-r N` *resamples* and
drops frames — a 274-frame rebuild came out at 166. `setpts=N/fps/TB` on a
concat is worse: `N` restarts on every segment, so the result ends on the last
piece's own clock. And on a segment with a real start offset it compressed 248
frames into 7.5s. **`setpts=PTS-STARTPTS`** is the right one: remove the offset,
keep the spacing.

**4. Pad each scene's audio to its own picture.** The concat demuxer lays audio
and video end-to-end *separately*, so a 15ms deficit per scene accumulates down
the whole video. It reached 13.8 seconds before this was understood.
`apad=whole_dur=<exact>` — not `-t`, which cuts on an AAC frame boundary.

---

## Housekeeping

None of `Customers/` is in git. Video cannot be packed, so one commit of a
working state would add its full size again, permanently. **`z_History` is the
only undo there is** — which is also why it grows without limit.

```bash
python3 build/trim_history.py "../Customers"           # shows, deletes nothing
python3 build/trim_history.py "../Customers" --apply   # keeps the 3 newest
```

It deletes every `z_History` nested inside another one first: a backup does not
keep backups, and that was 514 MB of ski-demo's 1.3 GB.

```bash
python3 tests/test_editor.py     # 38 steps, 168 checks, ~90s cold
```

Every assertion in the test suite is an exact **decoded frame count**. Every
real bug this tool has had was an off-by-a-frame that still produced a playable
file. If a check fails, read the **first** failure, not the list — the checks
share state on purpose and one broken call cascades.

---

## Reference

Sarah's standards and her source clips: `Sarah/` and `docs/avatar_launch.md`.
The compositing recipes: `docs/avatar_compositing.md`. The HeyGen API:
`docs/heygen_api.md` + `docs/heygen_api_addendum.md`. What each doc is for and
how far to trust it: `docs/README.md`.

| Field | Value |
|---|---|
| avatar_id (Pamela look) | `468eabb3326a4d8587ba29d065b1eba7` |
| group_id | `0484e7d80416443388aa1763f684f019` |
| voice_id (Derya, Starfish) | `04d0ae1d0af2489ca7d3bb402a39a890` |
| canvas | 1152 × 1152, 25 fps |
| corner | 320 px, bottom-right |
| words per second | 3.44, measured |

⚠ HeyGen's **v2 avatar endpoints are deprecated** and hang or 404. v3 only.
