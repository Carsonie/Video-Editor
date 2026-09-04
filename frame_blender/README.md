# Frame Blender

Step through a scene's two tracks — the demo footage (`segment.mp4`) and the
avatar overlay (`avatar.webm`) — one frame at a time, combine them, and build
a real mp4 from what you see.

```bash
python3 frame_blender/serve.py          # http://localhost:8843
```

Standalone — nothing else needs to be running. Load, Save Scene, Undo and the
store list all used to proxy to the main editor (`shared/serve.py`, port
8842); since 2026-09-02 they run here directly instead, reusing its own pure
helper functions (module-level, no live HTTP call) so the two tools' saves
and dirty-state tracking still can't drift apart — see `serve.py`'s own
module docstring and `save_scene()`'s docstring for the one real tradeoff
that came with the split (a cross-process lock gap).

## What's in here

| | |
|---|---|
| `serve.py` | the server. Stateless: every request that acts on a scene names that scene. |
| `web/index.html` | the page, with no scene in it |
| `web/app.css` | its styling |
| `web/state.js` | `SCENE`, `SCRIPT`, `pairQS()` — loaded **1st** |
| `web/persistence.js` | the browser's own storage, not the server — **2nd** |
| `web/load-picker.js` | `pickStores()` and the Load popup — **3rd** |
| `web/timeline.js` | Timeline Scenes — **4th** |
| `web/app.js` | loading and unloading a scene, and the bootstrap — **5th** |
| `VERSION` | bumped on every commit that touches this tool |

`app.js` was 765 lines covering four concerns; it was split on its own
section banners on 2026-09-04.

### ⚠ Load order is a behaviour contract, and it bit on day one

These files share one flat top-level scope on purpose — none is wrapped in
an IIFE, so each can call straight into the others' declarations, the way a
page has always shared scope across ordered `<script>` tags. No bundler, no
import/export.

That carries **two** risks, and only the first was known:

1. A `const` name declared in two files throws the moment they share a
   scope for real. `s_app_js_parses` checks every file alone **and all five
   concatenated in load order**, which is the only thing that sees it.

2. **A file that USES, at load time, a name declared in a later file.**
   `timeline.js` does

   ```js
   document.getElementById('tlLoadBtn').onclick = pickStores;
   ```

   at its top level, and `pickStores()` is in `load-picker.js`. Inside one
   file that worked — function declarations hoist. Across two `<script>`
   tags they do not, and the page threw `pickStores is not defined` on
   every load. **Nothing in the suite could see it**: every check drives
   HTTP, so the server answered perfectly, and `node --check` passes
   because the failure is at runtime, not in syntax. The browser found it.

   `s_load_order_forward_refs` now checks for exactly that, and
   `load-picker.js` must stay before `timeline.js`.

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
