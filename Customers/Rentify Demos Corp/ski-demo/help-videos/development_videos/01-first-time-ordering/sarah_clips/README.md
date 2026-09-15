# `sarah_clips/` — one avatar's clips for this store

Named for the **avatar**, not for the job. Renamed from `sarah_intro_tools`
2026-08-21: that name was accurate while the folder held only the opening, but
it now carries the closing morph, the close-out line and both exported
bookends. A second presenter gets their own folder on the same pattern —
`<name>_clips/`.

The code accepts either name (`sarah_dir()` in `assemble_video.py` and
`build_sarah_opening.py`), so a store that has not been renamed keeps working.

## The two bookends, as flat mp4s

| file | length | what it is |
|---|---|---|
| `OPENING.mp4` | 11.40s | Sarah centred on the pad colour for the intro, the 1.2s morph down into the corner, then the bridge line held in the corner |
| `CLOSING.mp4` | 3.38s | the 1.2s morph back out to centre, the close-out line, then 1.0s on the standard rest pose |

⚠ These are **previews of the avatar track**, not byte-identical slices of the
finished video. In the real build the store's first segment fades in underneath
the bridge, and the last segment fades out underneath the closing morph. Here
the background stays the flat pad colour throughout — which is what makes them
reusable, since nothing store-specific is baked in.

Rebuild them with `scratchpad/export_bookends.py`, which composites from the
same parts `assemble_video.py` uses, so what is exported is what ships.

## The parts they are built from

| file | paid? | role |
|---|---|---|
| `sarah-intro-alpha.webm` | **PAID** | raw HeyGen intro render |
| `sarah-bridge-alpha.webm` | **PAID** | raw HeyGen bridge render |
| `sarah-closeout-alpha.webm` | **PAID** | "See you at the store." |
| `sarah-intro-1152-alpha.webm` | derived | intro centred on the 1152 canvas, with 1.52s of real idle prepended and a 2-frame ease at the seam |
| `sarah-bridge-transition-to-corner.webm` | derived | the forward morph, centre → corner |
| `sarah-bridge-corner-320-alpha.webm` | derived | the corner element it lands on |
| `sarah-scene-12-transition-to-centre.webm` | derived | the reverse morph, corner → centre |
| `sarah-scene-12-corner-320-alpha.webm` | derived | by-product of building that morph; unused |
| `TRACK_front_sarah.webm`, `TRACK_rear_background.mp4` | derived | superseded; kept from the v15 two-track experiment |

⚠ The three PAID renders are overwritten **by name, with no backup**, by
`build_sarah_opening.py` unless `--skip-generate` is passed. Losing them costs
money to replace. `z_History/` holds prior versions.

## Two traps that have each cost an hour

- **`-c:v libvpx-vp9` before `-i` on every decode of an alpha WebM**, including
  `-f concat`. Omit it and the transparency is silently flattened to black while
  `ffprobe` still reports `yuva420p`.
- **The morph clips have no audio track.** The concat demuxer will not join a
  silent part to a voiced one — it drops the track entirely, and the failure
  surfaces later as `Stream map '' matches no streams`. Give every part a track
  before concatenating.
