# Frame Blender

Step through a scene's two tracks — the demo footage (`segment.mp4`) and the
avatar overlay (`avatar.webm`) — one frame at a time, combine them, and build
a real mp4 from what you see.

```bash
python3 frame_blender/serve.py          # http://localhost:8843
```

The main editor (`shared/serve.py`, port 8842) must also be running for Load,
Save Scene and Undo — those are proxied to it rather than reimplemented here,
so there is exactly one save path no matter which tool you use.

## What's in here

| | |
|---|---|
| `serve.py` | the server. Stateless: every request that acts on a scene names that scene. |
| `web/index.html` | the page, with no scene in it |
| `web/app.css` | its styling |
| `web/app.js` | its behaviour |
| `VERSION` | bumped on every commit that touches this tool |

## The one idea worth knowing

**The page starts empty and the scene arrives over the API.** `SCENE` in
`app.js` is the single thing that says what is loaded; `null` means nothing
is, and that is a normal state rather than an error.

It used to be the other way round — the server rendered the page *around*
one scene and remembered that scene in a module global. Three separate bugs
came out of that shape before the cause was understood, on 2026-08-30:

- **Clear could not clear.** The scene was baked into the HTML as literal
  values, so blanking the screen left every tool still acting on it.
- **Load could not load.** It listed a store's scenes and showed their
  dirty/clean state, but clicking one did nothing — the page could not
  change scene without a hand-edited URL.
- **Two tabs fought.** One remembered scene per process, shared by every
  browser tab pointed at it.

All three are gone by construction now, not by patching: Clear is one
`SCENE = null`, Load opens a scene because the page can change scene, and
two tabs are independent because the server remembers nothing.
