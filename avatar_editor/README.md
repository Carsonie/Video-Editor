# Avatar Editor

Duplicated whole from Frame Blender on 2026-09-02, at Carson's own request —
he asked for the two tools to be split, code and all, so a small change to
one can never silently break the other. Everything below described Frame
Blender at the moment of the copy; this file describes THIS tool now, not
something to keep in sync with Frame Blender's own README as either one
grows differently.

Step through a scene's two tracks — the demo footage (`segment.mp4`) and the
avatar overlay (`avatar.webm`) — one frame at a time, combine them, and build
a real mp4 from what you see.

```bash
python3 avatar_editor/serve.py          # http://localhost:8844
```

Standalone — nothing else needs to be running. Load, Save Scene, Undo and the
store list all reuse the main editor's own pure helper functions directly
(module-level, no live HTTP call), so this tool's saves and dirty-state
tracking still can't drift from the main editor's — see `serve.py`'s own
module docstring and `save_scene()`'s docstring for the one real tradeoff
that comes with running standalone (a cross-process lock gap between this
tool, Frame Blender, and the main editor, if more than one is ever open on
the same scene at once).

## What's in here

| | |
|---|---|
| `serve.py` | the server. Stateless: every request that acts on a scene names that scene. |
| `web/index.html` | the page, with no scene in it |
| `web/app.css` | its styling |
| `web/frame-player.js` | the three Play buttons, one player each — loaded FIRST |
| `web/gap-builder.js` | sarah_clips/libs, the Frame Selector, the Clip-Gap Builder — loaded SECOND |
| `web/app.js` | everything else: the combine engine, persistence, Timeline Scenes, the Load popup |
| `VERSION` | bumped on every commit that touches this tool — starts at 1, its OWN history, not Frame Blender's |

`frame-player.js` is the one exception to the flat scope below: it wraps
itself in an IIFE and exposes `FramePlayer` — a FACTORY, one engine per
panel — plus three named scenarios built on it, and `Players`, the one
door the other two files come through. Each scenario logs
`Inside: <name>`, so a click traces button → `gap-builder.js` →
scenario → engine.

| Button | Plays | Picture |
|---|---|---|
| `OriginalAudio` — Audio Menu | the checked, audible Sound Bits, in library order | its own small player under the library |
| `FrameSelector` | that panel's own collection, audible clips only | that panel's own viewer, frames stepping with the voice |
| `GapBuilder` | that panel's WHOLE collection, silent clips included | that panel's own viewer, same way |

**A panel's button moves that panel and nothing else.** It has been got
wrong twice — a frame stepper driven by the Audio Menu that left the
Frame Selector parked on frame 327 of 482, and one shared `<video>` that
let the Frame Selector's Play take over the Audio Menu's previewer. The
ONE thing the engines say to each other is `stopOthers()`: starting one
pauses the rest, because two voices at once is never wanted. The test
suite guards all of this; read the file's own header before adding
anything that moves a panel.

The Clip-Gap Builder is a TIMELINE, not an audio picker — hence the
silent clips, and hence its button going green on FRAMES while the other
two go green only on a voice.

`gap-builder.js` and `app.js` share one flat scope on purpose — neither is
wrapped in an IIFE, so each can call straight into the other's top-level
declarations, the same way a page has always shared scope across ordered
`<script>` tags. No bundler, no import/export. The one real risk that comes
with that: a `let`/`const` name declared in both would throw the moment
they share a scope for real, which neither file's own syntax check alone
would catch.

## The one idea worth knowing

**The page starts empty and the scene arrives over the API.** `SCENE` in
`app.js` is the single thing that says what is loaded; `null` means nothing
is, and that is a normal state rather than an error.

## Why a duplicate, not a shared library

Carson's own call, made explicit when he asked for this split (2026-09-02):
he's developing different functionality in Frame Blender and Avatar Editor
going forward, and does not want a small change made for one to have any
chance of breaking the other. Duplicated code costs a second place to fix
the same bug if one ever turns up in code that's still identical between
the two; the alternative — a shared module both import — costs exactly the
coupling this split was meant to remove. Accept the first cost on purpose.
