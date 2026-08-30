# sarah_clips/libs/ — the gap-filler library

Started 2026-08-30. Not read by `assemble_video.py` or anything else that
builds a real video — this is reference and raw material for Frame Blender,
where gap-fillers get puzzled together by hand. Safe by construction: the
real build only globs `*-transition-to-centre.webm` directly inside
`sarah_clips/`, never inside a subfolder, so nothing placed here can
accidentally reactivate itself in a release build.

## The plan this folder exists for

The pause between one narrated line and the next needs to look like Sarah is
actually there, not frozen and not obviously looping. The pieces:

1. **A standard gap-filler at each of four lengths** — 0.5s, 1s, 1.5s, 2s —
   built in Frame Blender from the idle footage below. These will land in
   `gap-fillers/` as they're made; empty for now.
2. **An Opening transition**: 5 frames carrying Sarah from her last real
   narrated frame into the first frame of whichever gap-filler is used.
3. **A Closing transition**: 5 frames carrying her from the gap-filler's
   last frame into the scene's own still frame.

## What's here now, copied in from elsewhere — nothing moved, nothing broken

| Folder | Contents | Source |
|---|---|---|
| `idle/` | `sarah-idle-20s-alpha.webm` (real material — use this one), `sarah-idle-10s-alpha.webm` (the first render, superseded, kept as fallback) | `Sarah/idle/` — the repo-wide reference copy `assemble_video.py`'s own hold-filling already reads |
| `stills/` | The rest pose (3 sizes) and the "Uncertainty" alternate (3 sizes) | `Sarah/` — see `Sarah/README.md` for the full story on each |
| `transitions/` | `sarah-idle-transition-to-centre.webm` — the corner→centre morph, generic (no words in it) | `Sarah/closing/` — this store's own closing was deliberately removed 2026-08-27; the morph itself is reusable and doesn't bring that decision back |
| `gap-fillers/` | Empty | Built here, not copied from anywhere |

**Not copied**: `sarah-closeout-alpha.webm` and its preview. Those are a
specific spoken line, not idle/still material — reusing them means reusing
her exact words, which is the one thing `Sarah/closing/README.md` warns
against doing without checking first.

## Why 5 and 10 seconds were remembered, but only 10 and 20 exist

The idle footage on file is two lengths — 10s (superseded) and 20s (the one
in use). No 5-second render exists anywhere in this repo; checked directly,
not assumed. If a 5s clip is wanted for finer gap-filler slicing, it needs a
fresh HeyGen render (`Sarah/README.md` has the exact recipe — silent audio,
no script) or slicing down from the 20s one, whichever is cheaper.
