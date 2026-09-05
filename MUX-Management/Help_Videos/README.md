# Help videos — where they live

Two layers, and they don't overlap.

## Per store — the workflow folders

```
Customers/<Business>/<store>/help-videos/
    raw_mp4/     unedited captures, straight out of the recorder
    final/       the finished, shareable cut
```

Added 2026-08-15 for the four stores under active work — `ski-demo`,
`canoe-demo`, `bike-demo`, `alpine-sports`. Organized by **customer → store →
stage**, so a video's owner and how far along it is are both readable from its
path, instead of every store's raw and finished work landing in one shared pile.

`raw_mp4/` is the input to editing; `final/` is the output. A file in `final/`
is one someone could be shown.

⚠ **The folders are tracked, the videos are not.** Each folder holds a
`.gitkeep`, so the structure appears on every checkout, and `.gitignore` drops
`*.mp4`/`*.mov`/`*.mkv` underneath. One recorded run is ~50MB, and a binary
committed once is in git history permanently — removing it later means a
history rewrite. To share a finished video, publish it rather than commit it.

## Repo-level — the other folders here

| | |
|---|---|
| `OBS_Staging/` | the `Rentify-E2E` OBS profile's own `RecFilePath` — where OBS writes, before `record_flow.ts` moves the finished file into the store's `raw_mp4/`. Gitignored. As of 2026-08-15 it is a real staging area, matching its name; until then it was the final destination. |
| `HeyGen/`, `MUX/`, `Mux_Discovery_Plan/`, `VSCode_Mux_Ex/` | avatar narration and Mux delivery work — agent `6_end-customer-help-video-creations`. `MUX/` is gitignored: it holds real signing keys. |

⚠ v10 has **no help-video support yet** — the `playback_ids.json` /
`fetchVideoRegistry` delivery mechanism existed only in the retired
`rentify_live`. Don't plan a delivery path around it without checking first.

## Recording a run

`Master_Flows/Recorder` (agent `5_testing-recorder-manager`) records an E2E
flow and files it in the right store's `raw_mp4/` automatically — OBS writes to
`OBS_Staging/`, then `record_flow.ts` moves it, resolving the business folder
from the store slug. Nothing to file by hand.

If the store folder can't be resolved, the video is left in `OBS_Staging/` with
a warning rather than the run failing: by then the recording already exists,
and losing a good capture to a path lookup is the worse outcome.
