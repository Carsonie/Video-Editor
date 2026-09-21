# Studio — what every video shares

Carson, 2026-09-21: *"fold `MUX-Management/` into `Studio/`."*

**`MUX-Management/` no longer exists.** This is it, reorganised: the things that
serve EVERY video live here, once. Anything belonging to ONE video lives in that
video's own folder — see `Video-Editor/CLAUDE.md`, section
**"A VIDEO'S FOLDER SHAPE"**.

```
Studio/
├── avatars/   12 MB   Sarah/, annie/, dt/, pamela/, find_avatar.py,
│                      talking_photos.json, v3_groups.json
├── beds/     7.3 MB   silence-10s-pure · silence-10s-roomtone · silence-20s-roomtone
├── heygen/   408 KB   the tooling: .claude/skill/hey_gen/, scripts/, config/,
│                      metadata.json, and four instruction docs
├── mux/       22 MB   tokens, the two signing keys, and vscode_example/
└── docs/      80 KB   Mux Overview · Mux · Mux Session Rules · YouTube ·
                       YouTube Setup · VIDEO_CREATION · close_out_sarah
```

**778.7 MB moved. Nothing deleted.**

---

## WHERE EACH THING CAME FROM

| now | was |
|---|---|
| `avatars/Sarah/` | `MUX-Management/Help_Videos/HeyGen/Sarah/` |
| `avatars/{annie,dt,pamela}/` + 3 files | `…/HeyGen/avatars/` |
| `beds/silence-*.wav` | `…/HeyGen/audio/` |
| `heygen/` (everything else) | `…/HeyGen/` root |
| `mux/` | `…/MUX/` |
| `mux/vscode_example/` | `…/VSCode_Mux_Ex/` |
| `docs/` | `…/Mux_Discovery_Plan/` + `MUX-Management/`'s three loose files + two READMEs |
| `z_History/MUX-Management_pre-Studio/HeyGen_videos/` | `…/HeyGen/videos/` — **679 MB** |
| `z_History/MUX-Management_pre-Studio/HeyGen_archive/` | `…/HeyGen/_archive/` — 23 MB |

### Why `videos/` went to history

679 MB — **93% of the old folder** — and it held exactly two entries:
`first_time_ordering` and `paddle_sports_first_time_ordering`. Both are
superseded HeyGen renders of one video, and one of them is for **paddle-sports,
which has no store row in the v10 database at all** (0 of 5 tests runnable, and
it cannot be re-recorded). Nothing is deleted; it is in `z_History/`.

---

## THE RULES

⚠ **SHARED HERE, PER-VIDEO THERE.** Sarah, the talking-photo groups and the
silence beds are one set for every video. A video's own HeyGen requests, clips
and audio go in that video's `4_avatar/`. Getting this backwards is how a
store's video work ended up in two unconnected places in the first place.

⚠ **`heygen/audio/first-time-ordering.mp3` IS THE ONE EXCEPTION, AND IT IS IN
THE WRONG PLACE.** It is 139 KB of voiceover for ONE video, sitting beside
shared tooling. Under the new shape it belongs in that video's `4_avatar/audio/`.
It has not been moved because **four stores each have a
`development_videos/01-first-time-ordering/`** and nothing in the file says
which one it was made for — `HANDOFF.md` points at ski-demo, `metadata.json`
does not say. Ask Carson before guessing.

⚠ **THE SECRETS ARE STILL IN THE REPO, AND ONE IS NO LONGER DUPLICATED.**
`mux/` holds two `.env` token files and two `.pem` signing keys, and
`heygen/.env.local` is a third secret. They are gitignored.
`mux-signing-key-2bCop….pem` used to exist **twice** — once in `MUX/` and again
in `VSCode_Mux_Ex/`. The fold did not merge them; `vscode_example/` still has
its own copy, because that example's `Makefile` reads it by path.

The proposal is **one copy outside the repo**, in `~/.rentify/mux/`, read from an
environment variable. Carson has not ruled on it. Until then: gitignored is not
the same as safe, and two copies of a signing key is one too many.

⚠ **NO CODE NAMED THE OLD PATHS.** Checked before moving: the only four hits in
the whole repo were **comments** in `Video-Editors/build/assemble_video.py`
(lines 117, 131, 715) and `build/fade_frames.py` (line 86) — and two of those
already said *"Basic_E2E_Testing's OLD layout"*, so they were stale before this.
They now name `Studio/avatars/Sarah/`.

⚠ **`heygen/metadata.json` IS THE OLD STAGE RECORD, AND IT IS THIN.** One entry,
`first-time-ordering`, with `stages.voiceover.status: "done"` and
`stages.combine.status: "pending"`. It holds no asset id, no playback id and no
upload date. That is what a per-video `6_mux/mux_state.json` is for; do not
extend this file to cover new videos.
