# next-editor-version

The two editors, rebuilt on the standard stack: **Go** on the back, and
**TypeScript + Vite + React + Mantine** on the front.

It runs BESIDE the working editors, on its own port and its own frame cache.
Nothing here replaces anything yet, and `shared/serve.py` keeps working
untouched the whole time.

**`HANDOFF.md` is where the open work is** — what the rebuild cannot do yet,
ranked, with the measurements behind each item.

```
next-editor-version/
  server/          Phase 1 — the Go backend
  web/             Phase 2 & 3 — the React front end
```

---

## Why it is safe to rewrite this at all

Because the test suite is **HTTP-level**. `tests/test_editor.py` drives the
API and knows nothing about what answers it, so the same 141 checks that hold
the Python server to account hold this one:

```bash
python3 tests/test_editor.py --server go
```

That turns "rewrite 3,400 lines and hope" into a checklist with a green light
at the end. Without it this would not be worth attempting.

---

## Phase 1 — the Go backend

**Done. 141/141 checks, 29/29 endpoints.**

```bash
cd next-editor-version/server
go run ./cmd/editord --port 8870
```

| Flag | Default | |
|---|---|---|
| `--port` | `8870` | the Python server is on 8842, so both can run at once |
| `--cache` | `<repo>/cache/go` | its own, deliberately — see below |
| `--root` | found by walking up | the folder holding `Customers/` |
| `--no-session-log` | off | for a test run, so fixture traffic does not bury a day of editing |

### What it is a port of

| Go | Python | |
|---|---|---|
| `internal/editor/media.go` | `shared/frames.py` | the ffmpeg and ffprobe rules |
| `internal/editor/cache.go` | `shared/frames.py` | extraction, the frame map, every frame edit |
| `internal/editor/vpaths.go` | `shared/paths.py` | where a scene's parts live |
| `internal/editor/server.go` | `shared/serve.py` | routing, the `Customers/` boundary, the lock |
| `internal/editor/api_*.go` | `shared/serve.py` | the 29 handlers |
| `internal/editor/templates/` | the players' `TEMPLATE`s | the three pages, lifted verbatim |

### The pages are LIFTED, not rewritten

`templates/*.gohtml` is 240 kB of the players' own JavaScript and CSS, moved
across character for character. Only the placeholders changed.

That was deliberate: Phase 1 is about the BACKEND. A page that is also being
rewritten cannot tell you whether the backend is right. Phases 2 and 3 replace
these; until then the pages you get are the pages you already know.

Two of Python's shorthands had to be honoured in the move, and the first one
was missed on the first attempt:

- `{base_ext!r}` — **repr, which QUOTES the value.** Dropped, it wrote
  `ext: .jpg` into the JavaScript. The page died on load with every control
  dead, and `node --check` in step 35 is the only thing that caught it.
- `{fps:g}` — `25`, not `25.000000`. It lands inside an ffmpeg filter string.

The delimiters are `⟦ ⟧` rather than Go's own `{{ }}`, because these files
contain every ASCII delimiter pair already.

### Why a separate cache

The two servers each derive an extraction's mtime their own way, so one shared
folder would have each of them decide the other's work was stale and re-extract
it. Point them at one folder deliberately with `--cache`, never by accident.

---

## Phase 2 — the MP4 Splitter in React

**Done.** Everything the old splitter does, driven and checked in a browser:
mark, step, zone, Frame Editor, Undo, Cut, and the hand-off.

```bash
cd next-editor-version/web
npm install
npm run dev            # http://localhost:5180
```

It needs the Go server up on 8870. The front-end server proxies two kinds of
path across to it — `/api/*`, and `/<slug>/frames/*` for the extracted frames
and each clip's audio. The second cannot be matched by prefix, because a cache
slug is an arbitrary name, so it is matched by SHAPE.

Point it somewhere else with `EDITOR_API=http://host:port npm run dev`.

### The layout is the argument

The frame takes the whole main column. ONE toolbar under it, in three rows with
one job each — **where you are**, **how you move**, **what you change**.
Anything touched once a session lives in the drawer on the right, behind a tab,
where it cannot be hit by accident.

That is not decoration. The frame counter used to sit in the same row as the
delete buttons, and Reset Editor — the most destructive control in the tool —
used to sit at the bottom of a scroll with the same weight as Browse.

### What was kept, deliberately

- **The native range input.** It is the one control that already does keyboard,
  drag, click-to-position and accessibility correctly, and this timeline needs
  all four. It is restyled, not replaced.
- **Every tooltip.** Several are a paragraph, because several controls need one.
- **The keyboard.** `←/→` one frame, `Shift` ten, `Alt` the next break point,
  `[`/`]` the same, `space` play, `m` mark. Alt is checked FIRST — without that,
  `Alt+←` steps a frame as well and lands one frame off the mark, which is the
  exact error being checked for.
- **The green.** Break points are green on an mp4 and purple on a WebM. In this
  view there is no layer toggle to read, so the marks are the only thing that
  can say which kind of file is open.

### The one endpoint the rebuild adds

`/api/clip`. The Python players baked the clip's facts into the generated page
— `const N = 40; const FPS = 25.0;` were written into the JavaScript at
extraction time, so the page never had to ask. A React bundle is static and is
handed a slug, so it does. No new behaviour, and nothing on disk that was not
already inside `meta.json`.

`tests/test_editor.py --server go` covers it: **30/30 endpoints, 149 checks.**
The Python run stays at 29/29 and the step says why it skipped, rather than
showing a green tick that means "not applicable".

## Phase 3 — the Segment and Avatar Editor in React

**Done.** Several scenes on one timeline, the avatar laid over the footage,
with every operation driven and checked in a browser: mark, ＋/－ Frame, ＋/－
Zone, copy and paste, per-scene undo, Update Frame Imbalance, Cut, Save, Save
all, Join, Split, and the VTT with its lines edited in place.

```
/timeline?root=<video folder>&ns=1,2,3
```

`ns=all` is resolved from the store's own script. Bookends are not in the
script and so are not included — they are ticked on from the scene list,
deliberately, because a bookend can sit on a timeline but cannot be joined or
split.

### One component, not two

The Python build had a `PAIR_TEMPLATE` for one scene and a `SEQ_TEMPLATE` for
several, and they drifted. Here a **one-scene timeline IS the layered view** —
same controls, same code, nothing to keep in step.

### The rules that had to survive the port

Each of these was paid for with a real defect, and each is a comment in the
source where it lives:

- **Check every ticked track BEFORE writing any.** The tracks are routinely
  different lengths — 480 segment against 442 avatar is normal — so the frame
  on screen can exist in one and be past the end of the other. Skipping past a
  refusal changed the tracks that worked and left the rest: a half-done edit
  that reads as an error. It shipped four times, on paste.
- **One zone, decided before anything is written.** Editing the first layer
  shifts its marks, so recomputing the zone for the second read the
  already-moved marks: a 35-frame zone grew the segment by 35 and the overlay
  by 70.
- **Resync before aiming an edit at a frame number.** The page's idea of a
  length can drift below the cache's real one, and the edit is then aimed at
  the wrong frame.
- **The VTT's clip length comes from the TIMELINE, not the file.** Reading the
  file is right for a report and wrong for an editor: a gap that does not move
  while you add frames is just a lie with a decimal point.
- **A join that would drop a track refuses**, and offers to fill the gap. The
  opening has no narration render, so dropping it silently would make scene 2's
  narration start at frame 1 — Sarah saying the login line over the intro.
- **The renumber lock is read from `script.json`, not remembered in the page.**
  A join RELOADS the timeline, so a flag held in JavaScript dies at exactly the
  moment it starts mattering.

### What the two additive fields are for

`/api/open-seq` and `/api/open-pair` now also return the manifest — the same
data the generated page carried inside its own JavaScript. Every field the old
answers had is unchanged, and the test asserts on those.

### Fixed while driving it

- The undo history is keyed by POSITION, so it cannot outlive the set of scenes
  it came from. After a join, index 0 is a different clip.
- The footage sets the stage height. A hardcoded aspect put the stage at the
  wrong shape for any clip that was not 750×422, and the avatar hung off the
  bottom.
- A backend too old to send the manifest now says so. It answered everything
  else perfectly and handed back nothing to draw — a blank page and a stack
  trace three layers down. The cause was a server still running the previous
  build.
