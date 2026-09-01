---
name: editor-launchers
description: Launch any of the three Video-Editor tools (Segment and Avatar Editor, the next-gen web editor, Frame Blender) in the browser, individually or all together. Use whenever Carson asks to open, launch, start, or run an editor by name.
user_invocable: true
---

# Launching the editors

There are **three** separate browser tools in this repo, each its own process.
Each runs independently — starting one never requires the others, except where
noted below.

| Editor | What it is | Launch.json name(s) | Port(s) |
|---|---|---|---|
| **Segment and Avatar Editor** (+ MP4 Splitter) | The original editor pair — `shared/serve.py` | `video-editor` | 8842 |
| **Next-gen web editor** | The React/Vite replacement, backed by a separate Go API | `video-editor-web-backend` (Go API), then `video-editor-web` (the UI) | 8870 (API), 5180 (UI) |
| **Frame Blender** | Standalone frame-by-frame overlay/base combiner, `frame_blender/` | `frame-blender` | 8843 |

**All four configs live in `Basic_E2E_Testing/.claude/launch.json`** — not
here. This repo has no `launch.json` of its own; the browser-preview tooling
reads the one in whichever repo the session was started from, and that has
always been `Basic_E2E_Testing` for this work. If a session is ever rooted
here instead, these named configs need copying over before they'll resolve.

## Launching one, by name

Use the Browser-pane preview tool with the exact `name` from the table:

- **Segment and Avatar Editor**: `preview_start({name: "video-editor"})`
- **Frame Blender**: needs the Segment and Avatar Editor's server (8842) up
  first for Load/Save/Undo/Build — those routes proxy straight to it. Start
  `video-editor` first if it isn't already running, then
  `preview_start({name: "frame-blender"})`.
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

## Launching all three together

Start, in this order (each is independent once up, but the ORDER below avoids
the 502s and proxy failures above):

1. `preview_start({name: "video-editor"})` — 8842
2. `preview_start({name: "video-editor-web-backend"})` — 8870
3. `preview_start({name: "video-editor-web"})` — 5180
4. `preview_start({name: "frame-blender"})` — 8843 (after step 1, since it
   depends on it)

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
# Segment and Avatar Editor
python3 shared/serve.py --port 8842

# Next-gen web editor — backend, from next-editor-version/server/
go run ./cmd/editord --port 8870

# Next-gen web editor — UI, from next-editor-version/web/
npm run dev                      # http://localhost:5180

# Frame Blender
python3 frame_blender/serve.py --port 8843
```
