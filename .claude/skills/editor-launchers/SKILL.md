---
name: editor-launchers
description: Launch any of the Video-Editor tools (Segment and Avatar Editor, MP4 Splitter, Frame Blender, Avatar Editor, the next-gen web editor) in the browser, individually or all together. Use whenever Carson asks to open, launch, start, or run an editor by name, or asks to "run the editors"/"run all 4 editors."
user_invocable: true
---

# Launching the editors

**"Run the editors" / "run all 4 editors" means these four**, Carson's own
standing directive (2026-09-02) — always these four unless he names a
different set:

| Editor | What it is | Launch.json name(s) | Port(s) |
|---|---|---|---|
| **Segment and Avatar Editor** | `shared/serve.py` | `video-editor` | 8842 |
| **MP4 Splitter** | Shares the SAME server/port as the SAE above — one process, two tools on one page (`browse.html`). Starting `video-editor` starts both; there is no separate launch for this one. | `video-editor` | 8842 |
| **Frame Blender** | Standalone frame-by-frame overlay/base combiner, `frame_blender/` | `frame-blender` | 8843 |
| **Avatar Editor** | Frame Blender's own sibling — duplicated from it whole (2026-09-02) as a separate, independent starting point for different work, `avatar_editor/` | `avatar-editor` | 8844 |

**Each of these four is fully independent** — none of them need each other,
or the main SAE server, running to work. Frame Blender and Avatar Editor
used to proxy Load/Save/Undo/Build to the SAE's own server; that dependency
was removed (2026-09-02) — see `frame_blender/serve.py`'s own module
docstring, and `avatar_editor/serve.py`'s identical copy of it, for exactly
what was duplicated and why. Starting any ONE of the four needs nothing
else up first.

**The next-gen web editor is a FIFTH, separate tool** — not part of "the
four," not started by "run the editors." Launch it only when Carson names
it specifically.

## Launching one, by name

Use the Browser-pane preview tool with the exact `name` from the table:

- **Segment and Avatar Editor / MP4 Splitter**: `preview_start({name: "video-editor"})` — one call starts the one server both live on.
- **Frame Blender**: `preview_start({name: "frame-blender"})` — standalone, nothing else needs to be running first.
- **Avatar Editor**: `preview_start({name: "avatar-editor"})` — standalone, same as Frame Blender.
- **Next-gen web editor**: it is TWO processes — a Go API with nothing to look
  at on its own, and the actual UI. Start the API first, THEN the UI:
  1. `preview_start({name: "video-editor-web-backend"})` — opens a tab at
     `:8870` too, but that tab is just raw JSON; ignore or close it.
  2. `preview_start({name: "video-editor-web"})` — this is the actual editor,
     at `:5180`.

  Skipping step 1 does not fail loudly — the UI loads fine, but every API call
  (Browse, Save, anything that touches a file) 502s. Confirmed by testing:
  starting `video-editor-web` alone leaves `:8870` closed and every
  `/api/*` request bad-gateways; starting the backend first fixes it
  immediately, no restart of the frontend needed — Vite's dev proxy checks the
  backend per request, not once at boot.

`preview_start` reuses an already-running server on that port instead of
double-starting it — safe to call again if unsure whether one is up.

## "Run the editors" — all four, in Chrome

Carson's directive (2026-09-02): all four run **in his actual Chrome
browser**, not the embedded Browser pane — each its own tab, each fully
independent of the others. Order doesn't matter now (nothing here depends
on anything else being up first), but starting the SERVER before opening
the Chrome tab still does:

1. Start all four servers (order doesn't matter, none depend on each other):
   - `preview_start({name: "video-editor"})` — 8842 (serves both SAE and Splitter)
   - `preview_start({name: "frame-blender"})` — 8843
   - `preview_start({name: "avatar-editor"})` — 8844
2. Open each in a real Chrome tab (`open -a "Google Chrome" <url>` via Bash —
   `preview_start` itself only opens the embedded pane, not real Chrome):
   - `http://localhost:8842` — SAE / MP4 Splitter
   - `http://localhost:8843` — Frame Blender
   - `http://localhost:8844` — Avatar Editor

That's three servers for four editor NAMES, because MP4 Splitter and the SAE
still share one page — opening `:8842` once gives Carson both.

## If a server was started outside `preview_start`

`preview_start` refuses to attach to a process already holding one of these
ports if that process wasn't started BY `preview_start` itself — it reports
the port as "in use by ... (not a preview server)" instead of reusing it. If
that happens: find and stop the stray process (`lsof -i :<port>`, then
`kill`), and start it again through `preview_start` so it's tracked properly
(logs, clean stop) — happened once with Frame Blender when it had been started
by plain `Bash` earlier in a session; killing that process and re-running
`preview_start({name: "frame-blender"})` picked it up cleanly on the next try.

## Raw commands, for reference or a manual fallback

```bash
# Segment and Avatar Editor + MP4 Splitter (one server, both tools)
python3 shared/serve.py --port 8842

# Frame Blender
python3 frame_blender/serve.py --port 8843

# Avatar Editor
python3 avatar_editor/serve.py --port 8844

# Next-gen web editor — backend, from next-editor-version/server/
go run ./cmd/editord --port 8870

# Next-gen web editor — UI, from next-editor-version/web/
npm run dev                      # http://localhost:5180
```
