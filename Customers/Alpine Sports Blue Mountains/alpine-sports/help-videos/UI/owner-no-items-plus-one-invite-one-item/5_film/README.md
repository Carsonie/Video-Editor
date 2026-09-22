# 5_film — the cuts that ship

**PARTLY BUILT.** Created 2026-09-21 as the agreed home for step 8.

## What goes here

```
5_film/
├── <capture>-avatar_v<N>.mp4      THE SHIPPABLE CUT — Sarah's voice
└── script_v<N>.json               the words that made v<N>
```

⚠ **THE MAC-VOICE FILM IS NOT IN HERE, ON PURPOSE.**
`../<capture>-narrated.mp4` stays at the recipe root. Carson's call,
2026-09-21, asked outright: *"This way we move on without breaking anything."*

Moving it would touch 4 code spots in 2 repos — `sae_vtt_sync.py:190` and
`vtt_editor/serve.py:442, 932, 978` — and 26 files across 25 folders, for no
gain. The split is real, not a fudge:

| | |
|---|---|
| `../<capture>-narrated.mp4` | the **review** cut. Mac voice. Rebuilt on every sync. |
| `5_film/<capture>-avatar_v<N>.mp4` | the **deliverable**. Sarah's voice. Versioned. |

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
