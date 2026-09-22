# 4_avatar — HeyGen, per scene

**HALF BUILT.** This folder was the agreed shape, created 2026-09-21 so step 7
had a home before the work started. The VOICE half is built now, the same day
— **`clips/` (avatar video) is still not built.**

Carson: *"I am thinking to do the HeyGen and the MUX work inside the Video-Editor
project folder… So everything is linear from after the raw.mp4, to finished
product."* Then, once the voice was chosen: *"Do A"* — build the two-pass
HeyGen timing into the voice tool itself.

## What goes here

```
4_avatar/
├── requests/<NN>-<label>.json     what was SENT to HeyGen, per scene    ✅ built
├── audio/<NN>-<label>.mp3         HeyGen's own raw reply, unmixed       ✅ built
├── heygen_state.json              voice_id · credits spent · a note     ✅ built
└── clips/<NN>-<label>.webm        an AVATAR clip — alpha, 25 fps        ❌ not built
```

One file per scene, named exactly as `../sandbox/<NN-label>/` is. A scene with no
line is silent and gets nothing here — the same rule `../voice/` follows.

⚠ **THE VOICE, NOT THE SPOKEN AVATAR.** `clips/` (an avatar video, Sarah's face
on screen) is the still-unbuilt half of this folder. What is built is
voice-only narration — see "THE VOICE TOOL" below. Carson: *"We do not need to
see Sarah in the video, just have her narrate it."* — so `clips/` may never be
needed for this video at all.

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

## THE VOICE TOOL — `voice_scenes.py --engine heygen`

Lives in `Basic_E2E_Testing/Master_Flows/Recorder/scripts/`, beside the Mac
narration tool it extends. Same dirty/pristine marking, same `voice/`
output path — `sae_vtt_sync.py` reads `voice/<NN>-<label>.m4a` regardless of
which engine made it, so nothing downstream needed to change.

```bash
python3 scripts/voice_scenes.py "<recipe folder>" --engine heygen           # ESTIMATE, spends nothing
python3 scripts/voice_scenes.py "<recipe folder>" --engine heygen --yes     # actually speak
python3 scripts/voice_scenes.py "<recipe folder>" --scenes 13 --engine heygen --yes
```

⛔ **WITHOUT `--yes` IT ONLY ESTIMATES AND STOPS** — Carson's standing money
rule, built into the tool itself so it cannot be skipped by accident. It prints
which scenes are dirty, an estimated credit count, the real credit balance and
wallet (both free to read), then waits.

⚠ **A SCENE WITH A `{n}` BEAT COSTS TWO CALLS, NOT ONE.** Pass 1 learns how this
voice paces the words and how much pause it adds on its own; pass 2 re-sends
with the break RECOMPUTED so the next sentence lands on the same timing the
Mac take had — see `voice/.mac_backup/` below. A scene with no beats is one call.

⚠ **`voice/.mac_backup/<NN-label>.m4a` IS MADE ONCE, THE FIRST TIME A SCENE
SWITCHES TO HEYGEN**, and kept forever after — it is the ONLY record of the
original Mac timing the frames were tuned to, since `voice/<NN-label>.m4a`
itself gets overwritten by the HeyGen render. Losing it means every later
re-render of that scene falls back to sending Carson's beats unmodified
(still correct, just not timing-corrected).

Proved 2026-09-21 on real scenes, with real money: scene 1 (no beats, 1 credit)
and scene 13 (one `{2}` beat, 3 credits — two passes) both rendered correctly,
then were REVERTED back to the Mac voice with `--engine mac --force` (free),
because building the capability was the ask, not converting the actual video
yet. 4 credits spent proving it; 802 of 822 remain.

## What is still not built

The avatar-video half — `clips/`, a job id, polling `GET /v3/videos/{id}`. The
compositing already exists — `Video-Editors/build/make_scene_overlays.py` puts
an avatar in a corner. Given Carson does not want Sarah on screen for this
video, this may stay unbuilt for it.
