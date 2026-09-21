# 4_avatar — HeyGen, per scene

**NOT BUILT YET.** This folder is the agreed shape, created 2026-09-21 so step 7
has a home before the work starts.

Carson: *"I am thinking to do the HeyGen and the MUX work inside the Video-Editor
project folder… So everything is linear from after the raw.mp4, to finished
product."*

## What goes here

```
4_avatar/
├── requests/<NN>-<label>.json     what was SENT to HeyGen, per scene
├── clips/<NN>-<label>.webm        what came BACK — alpha, 25 fps
├── audio/<NN>-<label>.mp3         the HeyGen voiceover for that scene
└── heygen_state.json              job id · status · cost · voice id · when
```

One file per scene, named exactly as `../sandbox/<NN-label>/` is. A scene with no
line is silent and gets nothing here — the same rule `../voice/` follows.

## The rules this folder inherits

⚠ **`heygen_state.json` IS THE RECORD. Prose never holds a fact.** The original
video's `HANDOFF.md` named its source capture, then warned in its own text
*"Don't read this off the doc — read `boundaries.json`'s `raw` field."* It had
named the wrong file for 5 days. Every stage with an outside service behind it
writes a `*_state.json`; a doc only explains.

⚠ **25 fps, NOT 30.** HeyGen renders at 25 and cannot be changed. OBS has
recorded at 25 since 2026-08-19 to match. A 30 fps capture is historical.

⚠ **SPEND NEEDS CARSON'S SIGN-OFF, EVERY TIME.** One line showing the dollar
amount, then wait for Y or N. Never buried in a paragraph.

⚠ **THE MAC VOICE IS THE REHEARSAL, NOT A DRAFT TO CONVERT.** `../voice/` proves
each line fits its screen at 155 wpm before a cent is spent. Carson's plan:
*"when I approve the mac voice, we will archive these files, remove the mac
voice, and go to HeyGen."* So a scene is not sent until its own row in the VTT
Editor is pristine and not rushed.

⚠ **SHARED AVATAR ASSETS DO NOT LIVE HERE.** Sarah, the talking-photo groups and
the silence beds are one set for every video, and they live in `Studio/` at the
repo root — `Studio/avatars/Sarah/`, `Studio/avatars/{annie,dt,pamela}/`,
`Studio/beds/`. Only this video's own requests, clips and audio belong here.

## What has to be built

A per-scene request/collect tool, and this state file. The compositing already
exists — `Video-Editors/build/make_scene_overlays.py` puts an avatar in a
corner. The gap is the ordering and the record, not the pixels.
