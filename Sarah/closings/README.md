# The closing — taken out of ski-demo's first video, kept for reuse

See `.claude/skills/sarah-library/SKILL.md` for how this folder fits into Sarah's common library, and how a piece from here has to be copied by hand into a store's own `sarah_clips/` before a build will pick it up.

Removed from `01-first-time-ordering` on **2026-08-27**, at the user's
direction. Nothing was deleted: every file that made the closing is here, and
putting it back is four `mv` commands.

## What is here, and which half it came from

| file | what it is |
|---|---|
| `sarah-idle-transition-to-centre.webm` | the reverse morph — Sarah grows back out of the corner to full screen |
| `sarah-closeout-alpha.webm` | her close-out line, alpha, from HeyGen |
| `PREVIEW-morph-then-closeout.mp4` | the two above joined, flat, to look at |
| `99-closing/` | the editor's reviewable copy — `segment.mp4` is a 7 kB placeholder, `avatar.webm` is the real picture |

## The two halves, because they are not the same thing

**`sarah_clips/` is what the video is BUILT from.** `assemble_video.py` globs
`*-transition-to-centre.webm` in that folder, and only if it finds one does it
append the morph and then look for `sarah-closeout-alpha.webm` beside it. With
neither present it falls back to a short hold on the standard rest pose, still
in the corner — which is what every store that never had a closing built
already does. Nothing errors.

**`sandbox/99-closing/` is what the EDITOR shows.** A bookend: a real folder
with no row in `script.json`, so it can sit on a timeline to be watched but
cannot be joined or split. Removing it changes the scene list and nothing else.

Deleting only the sandbox copy would have tidied the editor and left the
closing in the finished video, looking done. Both had to go.

## Putting it back

```bash
V="Customers/Rentify Demos Corp/ski-demo/help-videos/videos/01-first-time-ordering"
mv Sarah/closings/sarah-idle-transition-to-centre.webm "$V/sarah_clips/"
mv Sarah/closings/sarah-closeout-alpha.webm            "$V/sarah_clips/"
mv Sarah/closings/PREVIEW-morph-then-closeout.mp4      "$V/sarah_clips/"
mv Sarah/closings/99-closing                           "$V/sandbox/"
```

The build picks it up again on the next run — the glob is the only switch.

## Using it on another store

The morph is generic: it is Sarah moving, with no store in it. The close-out
line is a HeyGen render of specific words, so it carries whatever she says —
check that before reusing it somewhere the words do not fit.

⚠ `morph_avatar_corner.py --reverse` builds the morph FROM a scene's own render,
and `assemble_video.py` measures the close-out against that same render so her
head does not jump at the join. A morph moved to a store whose renders differ
will not line up. Rebuild it there rather than copying this one.
