---
name: mux
description: Mux Player chapters for Rentify help videos — how chapters reach the player (a JavaScript array, NOT the mp4), the exact addChapters API and its field names, how chapters relate to a script's scenes, and how to pick the grouping. Use whenever chapters, chapter markers, scrub-bar segments or "jump to" navigation come up on a help video, when wiring mux-player into a page, or when asked whether a version of Mux Player supports chapters. Also holds Mux asset upload, which is STALE — see the warning.
user_invocable: true
---

# Mux — chapters on a help video

Verified 2026-09-14 against Mux's own docs. Every claim here was checked, and the
ones that could not be are marked as unchecked rather than smoothed over.

## The single most important fact

**Mux Player does NOT read chapters out of the mp4.** You hand them to it as a
JavaScript array, in the page, after the media has loaded.

That matters because embedding chapters in an mp4 is easy and tempting —
`ffmpeg -f ffmetadata` with `[CHAPTER]` blocks and `-c copy`, instant, no
re-encode — and QuickTime and VLC both show them. **Mux Player will ignore all
of it.** Useful for the editor on their own machine; useless in the player.

Nothing in the player reference, the advanced-usage guide, or either
AI-chapters page describes ingesting chapters from an mp4 or a WebVTT track. The
JS array is the documented route.

## The API

```js
const p = document.querySelector('mux-player');

function addChapters() {
  p.addChapters([
    { startTime: 0,     value: 'Sign in' },
    { startTime: 14.0,  value: 'Find the store' },
    { startTime: 52.2,  value: 'Create the collection' },
  ]);
}

// ⚠ REQUIRED. Before the media has loaded there is nothing to attach them to.
if (p.readyState >= 1) addChapters();
else p.addEventListener('loadedmetadata', addChapters, { once: true });
```

| | |
|---|---|
| method | `addChapters(array)` |
| shape | `{ startTime: number, endTime?: number, value: string }` |
| units | **seconds** |
| read back | `p.chapters`, `p.activeChapter` (both read-only) |
| event | `chapterchange` |

⚠ **THE LABEL FIELD IS `value`, NOT `title`.** A web search summary said
`title`; Mux's own API reference says `value`. Getting it wrong gives
unlabelled chapters — which looks fine in code review and wrong on screen.

⚠ **`endTime` is optional and usually should be left out.** Omit it and a
chapter runs until the next one starts, with the last spanning to the end. Set
it only for a deliberate gap.

⚠ **Video-on-demand and audio only — NOT live.** Fine for help videos, which
are all VOD.

## Which versions have it

```
chapters API added   @mux/mux-player 2.7.0   (2024-05-28)
this repo is pinned  2.9.1                   ← already has it
latest seen          3.13.3                  (2026-09-09)
```

Pinned in `MUX-Management/Help_Videos/VSCode_Mux_Ex/frontend/package.json` as
`@mux/mux-player-react ^2.4.0`, resolving to **2.9.1** in the lockfile. The
caret means a fresh `npm install` could pull something newer — check the
lockfile, not the manifest, before claiming a version.

## Chapters are NOT scenes, and the counts SHOULD differ

This is the part that trips people up.

- A **scene** is a unit of narration: one screen, one line. `special-skis` has
  **21**.
- A **chapter** is a place a viewer wants to jump to. **Four to six** is right
  for a six-minute video.

21 chapters chops the scrub bar into confetti — every segment about 8 seconds —
and nobody navigates with that.

### The one rule

**A chapter's `startTime` must land on a scene boundary.** A chapter is a
COARSER GROUPING of the same timings, never a different set of them.

- On a boundary → the chapter opens on a clean screen, with a line starting.
- Anywhere else → it opens mid-sentence over a half-typed field.

So chapters are always a **subset of the scene start times**. That is what lets
one generator produce both from `script.json` and guarantees they cannot
disagree — the same reason the `.vtt`, `vtt.html` and `script.json` are built
from one source and never typed twice.

### The grouping that works, from special-skis

```
0:00   Sign in                    scenes 1-2
0:14   Find the store             scenes 3-7
0:52   Create the collection      scenes 8-12
1:58   Add the first item         scenes 13-17
3:14   The other variants         scene 18      ← the skippable one
5:51   Sign out                   scenes 19-21
```

One chapter per stage of the job. "Sign in" is short but earns its place: it is
the one thing a returning viewer always wants to skip.

### ⚠ The repeat-stretch chapter is the most valuable control on the player

The BCP admin recipes build one item and then CLONE it. Those clones are a
single **silent** scene, as long as the footage it covers:

| recipe | the silent stretch |
|---|---|
| `special-skis` | 156.2s |
| `special-boots` | 157.8s |
| `special-poles` | **382.3s** — over six minutes |

One chapter, one click, and the viewer skips the whole thing. On poles that is
more than half the video. Never bury this inside a larger chapter.

## Where the numbers come from

`script.json`, in each recipe's folder under
`Customers/<Business>/<store>/help-videos/raw_mp4/<recipe>/`. Every scene
carries its own footage length:

```json
{ "n": 11, "label": "collection-options", "raw-source": "27.7s on camera" }
```

Walk the scenes, accumulate `raw-source`, and every scene's start time falls
out. Those are the only legal chapter start times.

⚠ **`raw-source` is the FOOTAGE. `target-length` is the NARRATION, and it is
always shorter.** Chapters index the picture, so it is `raw-source` — always.
Summing `target-length` on a 376s capture gives 330s, and every chapter after
the first lands progressively early.

⚠ **THE GROUPING IS PER RECIPE, NOT SHARED.** `special-poles` has 18 items
against the others' 9, so its "other variants" chapter starts at a different
second. Never copy one recipe's times to another.

## Three outputs, one source

| where | what it needs |
|---|---|
| Mux Player | a `chapters.json` array — `startTime` + `value` |
| QuickTime, VLC | chapters inside the mp4 (`ffmetadata` + `-c copy`) |
| YouTube, Vimeo | plain timestamps in the description |

All three derive from the same walk of `script.json`, so build them together or
they drift.

## Mux's own AI chapter generation — UNCHECKED

Mux has a server-side job that generates chapters and returns
`chapters[].start_time` in **seconds**. Whether the player then picks those up
on its own, and whether you can store YOUR OWN chapters on an asset, is **not
stated** on either of Mux's chapters pages. Do not assume it works; check before
relying on it.

It is also the wrong tool here even if it does. AI chapters come from what the
video looks and sounds like; ours come from the flow's own labelled screens,
which are exact.

## ⚠ Nothing to show them in yet

`Rentify_v10` has **no help-video delivery at all** — no `help_videos/`, no
`playback_ids.json`, no Mux reference in `web/src`. That is
`Basic_E2E_Testing/ToDo_Rentify_v10.md` **V3**, still open as of 2026-09-14, and
it needs code in a repo that is read-only to us.

So chapters are for the editor and for whatever the videos are uploaded to —
not for a renter in the app. Build them anyway; they are cheap and the delivery
gap is someone else's commit.

## ⚠ `video.md` in this folder is STALE

`mux/video.md` covers uploading assets to Mux and wiring `playback_ids.json`. Two
problems:

1. **It never registered as a skill.** A skill only loads from
   `.claude/skills/<folder>/SKILL.md`; that file is `video.md`, so it has been
   invisible the whole time.
2. **It describes the retired `rentify_live` mechanism** —
   `deploy/app/etc/config.json`, `fetchVideoRegistry` in `web/src/api/index.ts`,
   `app/api.go:102`, `customers/*/help_videos/playback_ids.json`. None of that
   exists in v10. See V3 above.

Read it for the Mux account and dashboard details, not for how the frontend
resolves a video. It also holds **live Mux API credentials in plain text** —
worth moving out of a doc, and deliberately not copied into this file.
