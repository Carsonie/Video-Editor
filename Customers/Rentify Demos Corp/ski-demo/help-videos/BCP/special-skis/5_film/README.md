# 5_film — the cuts that ship

**PARTLY BUILT.** Created 2026-09-21 as the agreed home for step 8.

## What goes here

```
5_film/
├── WIP-<Video Name>-v<N>.mp4      THE WORK IN PROGRESS — the newest cut
├── <capture>-avatar_v<N>.mp4      THE SHIPPABLE CUT — Sarah's voice
└── script_v<N>.json               the words that made v<N>
```

### `WIP-<Video Name>-v<N>.mp4` — added 2026-10-08

Carson: *"This is where I want to keep my most recent versions of our progress
before placing it onto the MUX service provider."*

**This folder is the staging post for MUX.** Whatever is the newest watchable
cut of a video lands here under a `WIP-` name, whichever voice is on it, and it
sits here until it is good enough to host. `6_mux/` is the step after.

    WIP-The Picklist-v1.mp4
    WIP-Special Skis-v12.mp4

⚠ **THE NAME IS THE VIDEO'S NAME, NOT THE CAPTURE'S.** A capture is named for
the run that made it — `ski-demo_special-skis_dev_10-19-12_v12` — which says
nothing to anyone reading the folder a year from now. A `WIP-` file is read by a
person deciding what to upload, so it carries the name the video is called.

⚠ **`v<N>` IS THE CUT, NOT THE CAPTURE'S VERSION.** They start out the same and
then diverge the first time a cut is rebuilt from the same master. Bump it on
every new cut placed here; keep the one being replaced in `z_History/` rather
than overwriting it, so "the last one I showed him" is always recoverable.

⚠ **IT IS NOT THE DELIVERABLE.** A `WIP-` file is what you would show someone
today. `<capture>-avatar_v<N>.mp4` is what ships, and it still needs its
`script_v<N>.json` beside it (see the rule below). A WIP has no such
requirement, because its whole point is to exist before the words are settled.

⚠ **THE MAC-VOICE REVIEW CUT CAN NOW BE THE WIP.** That is what changed on
2026-10-08: Carson moved special-skis' `..._v12-narrated.mp4` here from
`1_cuts/`. The paragraph below is the 2026-09-21 rule it supersedes, kept
because the code it names has NOT changed and still looks at the old path.

⚠ **THE MAC-VOICE FILM IS NOT IN HERE, ON PURPOSE.** *(2026-09-21 — SUPERSEDED
for the WIP copy, still true for the one the tools write.)*
`../1_cuts/<capture>-narrated.mp4` is what `sae_vtt_sync.py` REBUILDS on every
sync, and that path is still hardcoded in 4 spots across 2 repos —
`sae_vtt_sync.py:190` and `vtt_editor/serve.py:442, 932, 978`.

So a narrated cut in here is a COPY taken at a moment worth keeping, not a move.
⚠ **IF YOU MOVE THE ONE THE TOOLS WRITE, THE NEXT SYNC SILENTLY MAKES ANOTHER**
at the old path, and you end up with two films disagreeing about which is newest.

| | |
|---|---|
| `../1_cuts/<capture>-narrated.mp4` | the **review** cut. Mac voice. Rebuilt on every sync — never move it, copy it. |
| `5_film/WIP-<Video Name>-v<N>.mp4` | the **work in progress**. Whichever voice. The MUX staging post. |
| `5_film/<capture>-avatar_v<N>.mp4` | the **deliverable**. Sarah's voice. Versioned, and paired with its script. |

## The one rule that is already enforced

⚠ **A VIDEO AND THE WORDS THAT MADE IT MUST NOT BE SEPARABLE.**
`build/release_video.py` refuses a release with no `script_v<N>.json` beside the
mp4. That rule was learned on `01-first-time-ordering`, where
`video/script_v32.json` sits beside `ski-demo_first-time-ordering_v32.mp4`.
Keep the pairing here.

## What has to be built

The assemble step: the same stream-copy concat `sae_vtt_sync.py` already does
for the mac-voice film, with `../4_avatar/` audio in place of `../voice/`.

⚠ **`build/build_scenes.py --join` IS NOT IT.** It requires an `avatar.webm` in
**every** scene, so it refuses a BCP recipe outright — all 23 of special-skis'
scene folders have none. Measured 2026-09-21.
