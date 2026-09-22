# 6_mux — hosting

**NOT BUILT YET.** Created 2026-09-21 as the agreed home for step 9.

## What goes here

```
6_mux/
└── mux_state.json     asset id · playback id · uploaded · duration
                       · playback policy · signed-URL notes
```

One file. It is the only place that says **where a finished video actually is**.

⚠ **NOTHING RECORDS THIS TODAY.** Checked 2026-09-21: no asset id, no playback
id and no upload date exists anywhere in either repo.
`Studio/heygen/metadata.json` holds one entry with
`stages.combine.status: "pending"` and that is all.

⚠ **THE OLD DELIVERY MECHANISM IS GONE.** `playback_ids.json` and
`fetchVideoRegistry` existed only in the retired `rentify_live`. **Rentify_v10
has no help-video support at all yet** — see `ToDo_Rentify_v10.md`. So a
playback id recorded here has nowhere to be served from until that lands. Record
it anyway; the id is the thing that cannot be recovered later.

⚠ **NO SECRETS IN THIS FOLDER, EVER.** The tokens and the two `.pem` signing
keys live in `Studio/mux/` — and one of them is still duplicated under
`Studio/mux/vscode_example/`, because that example's Makefile reads it by path. The proposal is one copy outside the repo,
read by path from an environment variable. `mux_state.json` holds ids, never
credentials.

## What has to be built

An upload tool and this state file. The tokens, the signing keys and the JWT
notes all exist in `Studio/mux/vscode_example/`; nothing joins
them to a video folder.

⚠ **AND `release_video.py` NEEDS THIS FILE.** It enforces mp4 + `script_v<N>.json`
today. Without `mux_state.json` carried into the release, a released video
cannot say where it is hosted.
