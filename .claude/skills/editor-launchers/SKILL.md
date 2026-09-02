---
name: editor-launchers
description: Launch any of the Video-Editor tools (Segment and Avatar Editor, MP4 Splitter, Frame Blender, Avatar Editor, the next-gen web editor) in the browser, individually or all together. Use whenever Carson asks to open, launch, start, or run an editor by name, or asks to "run the editors"/"run all 4 editors."
user_invocable: true
---

# Launching the editors

**"Run the editors" / "run all 4 editors" means these four**, Carson's own
standing directive (2026-09-02, updated same day when the fourth split
into two) — always these four unless he names a different set:

| Editor | What it is | Launch.json name | Port | Own cache |
|---|---|---|---|---|
| **MP4 Splitter** | Cuts a raw recording into numbered segments. `mp4_splitter/serve.py` | `mp4-splitter` | 8845 | `cache_mp4_splitter/` |
| **Segment and Avatar Editor** | Layers a segment + avatar overlay, timelines, Join/Split. `segment_avatar_editor/serve.py` | `segment-avatar-editor` | 8846 | `cache_segment_avatar_editor/` |
| **Frame Blender** | Standalone frame-by-frame overlay/base combiner, `frame_blender/` | `frame-blender` | 8843 | `cache/` (repo-root) |
| **Avatar Editor** | Frame Blender's own sibling — duplicated from it whole (2026-09-02) as a separate, independent starting point for different work, `avatar_editor/` | `avatar-editor` | 8844 | `cache/` — SAME folder as Frame Blender's, unlike the two below. That split (2026-08-xx) never asked for separate caches; this one (Splitter/SAE, 2026-09-02) explicitly did. Worth knowing if that ever needs fixing to match. |

**Every one of these four is now genuinely its own process, own port, own
cache, no shared code** — MP4 Splitter and the SAE used to share ONE
process (`shared/serve.py`, port 8842, `browse.html`); Carson asked for
them to split apart the same way Frame Blender/Avatar Editor did
(2026-09-02). Each new copy started as a literal copy of `shared/serve.py`,
trimmed to just the routes its own page actually calls — see
`mp4_splitter/serve.py`'s and `segment_avatar_editor/serve.py`'s own module
docstrings for exactly what was kept, dropped, and why. One deliberate
exception: the SAE's "open this scene on its own" link still works, via a
PRIVATE duplicate of MP4 Splitter's player baked into
`segment_avatar_editor/_splitter_player.py` — not an import of the real
`mp4_splitter` package.

**`shared/serve.py` still exists, unchanged, still on port 8842** — it has
to: Frame Blender and Avatar Editor both import plain functions out of it
directly (`resolve_outdir`, `build_segment`, `cache_state`, ...), so it
cannot be removed or gutted. Starting it (`video-editor` in launch.json)
still works and still serves both tools combined on one page — but it is
no longer part of "run the editors." Only mention/launch it if Carson
specifically asks for the old combined page.

**The next-gen web editor is a FIFTH, separate tool** — not part of "the
four," not started by "run the editors." Launch it only when Carson names
it specifically.

## Launching one, by name

Use the Browser-pane preview tool with the exact `name` from the table:

- **MP4 Splitter**: `preview_start({name: "mp4-splitter"})` — standalone.
- **Segment and Avatar Editor**: `preview_start({name: "segment-avatar-editor"})` — standalone.
- **Frame Blender**: `preview_start({name: "frame-blender"})` — standalone.
- **Avatar Editor**: `preview_start({name: "avatar-editor"})` — standalone.
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
independent of the others, none needing any of the others (or the old
combined 8842 server) running first.

1. Start all four servers (order doesn't matter, none depend on each other):
   - `preview_start({name: "mp4-splitter"})` — 8845
   - `preview_start({name: "segment-avatar-editor"})` — 8846
   - `preview_start({name: "frame-blender"})` — 8843
   - `preview_start({name: "avatar-editor"})` — 8844
2. Open each in a real Chrome tab (`open -a "Google Chrome" <url>` via Bash —
   `preview_start` itself only opens the embedded pane, not real Chrome):
   - `http://localhost:8845` — MP4 Splitter
   - `http://localhost:8846` — Segment and Avatar Editor
   - `http://localhost:8843` — Frame Blender
   - `http://localhost:8844` — Avatar Editor

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
# MP4 Splitter — standalone, own cache
python3 mp4_splitter/serve.py --port 8845

# Segment and Avatar Editor — standalone, own cache
python3 segment_avatar_editor/serve.py --port 8846

# Frame Blender
python3 frame_blender/serve.py --port 8843

# Avatar Editor
python3 avatar_editor/serve.py --port 8844

# The old combined server — still works, no longer part of "run the editors"
python3 shared/serve.py --port 8842

# Next-gen web editor — backend, from next-editor-version/server/
go run ./cmd/editord --port 8870

# Next-gen web editor — UI, from next-editor-version/web/
npm run dev                      # http://localhost:5180
```
