---
name: editor-launchers
description: Launch any of the Video-Editor tools (Segment and Avatar Editor, MP4 Splitter, Frame Blender, Avatar Editor, the next-gen web editor) in the browser, individually or all together. Use whenever Carson asks to open, launch, start, run, or reload an editor by name, or asks to "run the editors"/"run all 4 editors"/"reload."
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
| **Frame Blender** | Monitors how the base and overlay tracks flow together, frame by frame, to form the current scene — and (planned) drives a visual frame-by-frame mp4 build, showing the build as it happens. `frame_blender/` | `frame-blender` | 8843 | `cache/` (repo-root) — it has that folder to itself since 2026-09-04. Renaming it `cache_frame_blender/` for symmetry is a separate task. |
| **Avatar Editor** | Edits Sarah's own overlay — her clip library (stills, idle loops, transitions, sound bits) via the Gap Builder, for building and adjusting her overlay scene by scene. `avatar_editor/` | `avatar-editor` | 8844 | `cache_avatar_editor/` — its own since 2026-09-04. It shared `cache/` with Frame Blender until then. |

**Frame Blender's purpose (2026-09-02):** it exists to watch the two
tracks — base and overlay — and how they line up, scene by scene, frame
by frame. The build step (`build_scenes.py`, `build/`) currently runs
blind, with nothing to look at while it works. Frame Blender is meant to
grow into the tool that shows that mp4 build happening, frame by frame,
as it runs — not just editing individual frames after the fact. That
build-visualizer piece is not built yet.

**Avatar Editor's purpose (2026-09-02, narrowed same day):** started as a
whole duplicate of Frame Blender, but Carson split the work between the
two — Frame Blender keeps the two-track combine/build job above; Avatar
Editor keeps only the Gap Builder, the tool for editing Sarah's overlay
itself — her common library (`Sarah/`) alongside a store's own
`sarah_clips/`, browsed side by side, plus the Frame Selector and
Clip-Gap Builder that assemble them (see `.claude/skills/sarah-library/
SKILL.md` for what Sarah's clips are and how the two libraries relate).
The
overlay+base combine view, Build, Play video and Save MP4 were removed
from `avatar_editor/` entirely — that job belongs to Frame Blender now,
not duplicated here.

**Every one of these four is now genuinely its own process, own port, own
cache, no shared code** — MP4 Splitter and the SAE used to share ONE
process (`shared/serve.py`, port 8842, `browse.html`); Carson asked for
them to split apart the same way Frame Blender/Avatar Editor did
(2026-09-02). Each new copy started as a literal copy of `shared/serve.py`,
trimmed to just the routes its own page actually calls — see
`mp4_splitter/serve.py`'s and `segment_avatar_editor/serve.py`'s own module
docstrings for exactly what was kept, dropped, and why. The SAE's "open this scene on its own" page is GONE (2026-09-04). It was
rendered by a private duplicate of MP4 Splitter's player
(`_splitter_player.py`), kept so the two tools stayed unlinked — but
nothing in any UI ever linked to the page itself, so it was deleted.
`/<slug>/base/viewer.html` now 404s, by design.

**`shared/serve.py` still exists, still on port 8842** — it has to: Frame
Blender and Avatar Editor both import plain functions out of it directly
(`resolve_outdir`, `build_segment`, `cache_state`, ...), so it cannot be
removed or gutted. Avatar Editor also *monkey-patches* its `CACHE` at
import time (2026-09-04), because two of those borrowed helpers read it.

What did change on 2026-09-03: `shared/frames.py`, `shared/paths.py` and
`shared/vtt.py` are now ~25-line **re-export shims** over `editor_base/`,
the one package every editor imports from. They keep the nine scripts in
`build/` working unchanged. The real code is in `editor_base/`.

Starting it (`video-editor` in launch.json) still works and still serves
both tools combined on one page — but it is no longer part of "run the
editors." Only mention/launch it if Carson specifically asks for the old
combined page.

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

⚠ **`preview_start` REUSES an already-running server on that port. It does
not restart it.** That is what you want when launching — call it again if
you are unsure whether one is up, and nothing is double-started.

It is exactly what you do NOT want when reloading. A Python server imports
its modules once, at startup, so a reused process keeps serving the code it
started with. Reusing it after a code change reports success and changes
nothing. See "Reload" below, which stops each server first.

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

## "Reload" — restart all four servers, then their real Chrome tabs

Carson's own standing phrase (2026-09-02, after a session's preview servers
had quietly all stopped, so a plain browser refresh on a dead server just
sat on a blank/error page): "reload" means restart the SERVERS, not just
refresh the tabs. A browser refresh alone proves nothing — it cannot tell
you whether the process behind it is even still running.

1. **STOP each running server, then START it.** `preview_start` alone is not
   a reload — it reuses the running process, which still holds the code it
   was launched with.
   - `preview_list()` — returns a `serverId` per running server
   - `preview_stop({serverId})` for each of the four
   - then `preview_start({name})` for each: `mp4-splitter` 8845,
     `segment-avatar-editor` 8846, `frame-blender` 8843, `avatar-editor` 8844
   - each result should say `"reused": false`. **If it says `true`, the stop
     did not take and you are about to test stale code.**
2. Reload each real Chrome tab whose URL contains one of those four ports,
   via `osascript`:
   ```applescript
   tell application "Google Chrome"
     repeat with w in windows
       repeat with t in tabs of w
         set u to URL of t
         if u contains "localhost:8843" or u contains "localhost:8844" or u contains "localhost:8845" or u contains "localhost:8846" then
           reload t
         end if
       end repeat
     end repeat
   end tell
   ```
3. Confirm it worked by reading back each tab's title (a dead server shows
   the tab titled plain `localhost`, not the editor's own name) — the same
   `osascript` shape as step 2, but returning `URL of t & " | " & title of t`
   instead of `reload`ing.
4. **If step 2 reloaded ZERO tabs, the tabs are gone, not broken.** Chrome
   was closed, or they were. Open them with `open -a "Google Chrome" <url>`
   as in "Run the editors" above, and say so — do not report a successful
   reload of nothing. This happened twice on 2026-09-04.

   Reopen each on the URL it was last on where you know it, rather than the
   landing page — except a URL whose cache you have just cleared or
   invalidated, which would only 404.

### Why this section is written this way (2026-09-04)

Until then step 1 said "`preview_start` all four, safe to call even if
they're already up". That is a reload that does not reload. It was hit for
real: `_splitter_player.py` had been commented out, the SAE was told to
reload, `preview_start` reused the old process, and the server went on
serving the deleted module — while the reply said all four had restarted.
A test of "is this page still used" was about to be run against code that
was still there.

The tell is `"reused": true` in the result. Watch for it.

Whichever tab was mid-session on a specific page (a viewer, a loaded pair)
reloads to THAT same URL, same as any browser refresh — this does not send
anyone back to the landing page unless the server restart itself lost that
state (it doesn't; only the in-page JS session state, kept in
`localStorage`, can survive a dead process, and frame/scene caches on disk
survive regardless).

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
