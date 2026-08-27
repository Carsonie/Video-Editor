# next-editor-version

The two editors, rebuilt on the standard stack: **Go** on the back, and
**TypeScript + Vite + React + Mantine** on the front.

It runs BESIDE the working editors, on its own port and its own frame cache.
Nothing here replaces anything yet, and `shared/serve.py` keeps working
untouched the whole time.

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
| `--cache` | `<repo>/cache-go` | its own, deliberately — see below |
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

## Phase 3 — the Segment and Avatar Editor in React
