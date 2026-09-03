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
| `web/gap-builder.js` | sarah_clips/libs, the Frame Selector, the Clip-Gap Builder, the menus — loaded SECOND |
| `web/working-clips.js` | the Working Clips panel: Carson's own saved clips — loaded THIRD |
| `web/tooltips.js` | the 3-second hover tooltip on every control |
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

`working-clips.js` keeps its own scope too, and hands out `WorkingClips`.
It is the panel right of Timeline Scenes: three sections (IDLE,
TRANSITIONS, SOUND_BITS) holding clips Carson built here, as opposed to
`sarah_clips/libs`, which holds what HeyGen and the transition tools
produced. Two controls read and write it — **Save to Working Clips** in
the Gap Builder Menu (the whole Clip-Gap Builder collection, in order,
under a typed name) and **Replace Selected** in the Frame Selector Menu
(the active saved clip goes in over the selection, with a Yes/No warning
when the frame counts differ). At most ONE entry is active at a time,
because Replace Selected needs one answer.

Saved clips live in the same `localStorage` record as the Clip-Gap
Builder's own collection, and are NOT tied to one scene. Frames are
stored compactly — a short list of source clips plus (clip index, frame
index) pairs — because written out in full a single 482-frame clip is
about 100KB of JSON against a ~5MB budget for the whole page. URLs are
rebuilt on the way out rather than stored.

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

## Tooltips

Every button, dropdown and icon control carries a `title` saying what it
does, and `tooltips.js` shows it as a styled box after a **3-second**
hover — Carson's own number: long enough that passing over a stack of
buttons never triggers it, short enough that stopping on one because you
are unsure gets you an answer. The browser's own tooltip is suppressed
while hovering and restored on the way out, so the two never show at once.

Two rules to keep:

- **`title` stays the source.** The text is read at hover time, never
  copied at load, because several titles are rewritten as the page works
  — each Play button's says how many clips it would play, and Save to:'s
  says how many frames it would save.
- **Checkboxes are excluded**, deliberately. A tick box says what it does
  by being ticked.

The listener is delegated on the document, so controls built at runtime
(the library's rows, Timeline Scenes' rows, Working Clips' rows) are
covered with nothing to wire up. A control can borrow another element's
description with `data-tip-from="<id>"` — the Save to: dropdown does,
because the row around it is the button.

The suite fails if any `<button>` or `<select>` in `index.html` has
neither a `title` nor a `data-tip-from`.
