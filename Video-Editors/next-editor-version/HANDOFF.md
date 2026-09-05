# HANDOFF — the next-generation editors

Where the rebuild stands, what it cannot do yet, and what to build next.

Measured on **2026-08-27**, on branch `next_gen_editors`.

---

## The state, in three numbers

| | Result |
|---|---|
| Current editors (Python) | **142/142 checks · 29/29 endpoints · PASS** |
| Rebuild (Go backend) | **149/149 checks · 30/30 endpoints · PASS** |
| Rebuild (React front end) | **36 of 47 controls built** |

The first two are `tests/test_editor.py`. The third is
`next-editor-version/parity.py`.

```bash
python3 tests/test_editor.py                  # the Python editors
python3 tests/test_editor.py --server go      # the rebuild's backend
python3 next-editor-version/parity.py --missing
```

---

## Read this before trusting a green run

**The test suite drives HTTP.** Every check in it ends in an endpoint, so it
proves the two BACKENDS agree and says **nothing** about whether a control
exists to reach them. Both servers answer perfectly today while the rebuild has
no button for a fifth of the tool.

That is not a flaw in the suite — it is what made a 3,400-line rewrite safe to
attempt at all. It is simply a different question, and `parity.py` asks the
other one:

> For each control the Python players put on screen, does the rebuild have one?

The Python side of that comparison is read from the players' **own markup**, so
it cannot go stale. The React side is matched by one short string per control,
written down in `parity.py`. A control leaves the report the moment its string
starts matching — nothing here is a hand-written list that can drift.

**A third question nobody has asked yet:** does it still work when a person uses
it for an hour? See P1.4.

---

## ToDo

Ranked `P1`–`P4`, most severe first — the same convention as this repo's
`ToDo.md`.

### P1 — the layered view does not exist

Six of the eleven gaps are one missing page. The Python build has a
`PAIR_TEMPLATE` for looking at ONE scene with its avatar on top, reached from
the browser by picking a background (`▩`) and an overlay (`◈`). None of that
was rebuilt.

**P1.1 — a dedicated layered page.** The rebuild treats a one-scene timeline as
the layered view. That was a deliberate simplification and it covers most of
the work, but it loses five controls that only exist on the pair page.

**P1.2 — solo a layer, and show/hide each layer.** Watching Sarah alone, or the
footage alone, is how a pose that pops gets found. The timeline always shows
both stacked.

**P1.3 — the segment version selector.** `dev/` keeps `segment-v6.mp4`,
`segment-v5.mp4` and so on. The Python pair page lets you load an older version
to compare. The rebuild reads only what `sandbox/` resolves to, with no way to
ask for a different version.

**P1.4 — the browser has no pair slots.** `▩ background` / `◈ overlay` is the
ONLY way into the layered view in the Python build. The rebuild's browser opens
a single clip in the splitter, or a whole video folder on the timeline, and has
no third option. Until P1.1 exists there is nowhere for the slots to go, so
these two land together.

**P1.5 — the sibling scene list.** On the pair page, a strip of every scene in
the store, so you can step to the next one carrying the same overlay across.
The timeline's scene list is the nearest thing and works differently.

**P1.6 — nobody has used the rebuild for a real hour of editing.** Both suites
are green and every control has been clicked once. That is not the same as
finishing a video with it, and the difference is where the last class of bug
lives — the one that only shows up on the fortieth edit. The Python editors
earned every note in their source that way.

### P2 — two controls that make a whole panel read-only

**P2.1 — the naming modal.** Join and Split ask for names with
`window.prompt()`. The Python build has a real modal that shows exactly which
scenes will be merged, validates the name as you type, and refuses before the
call rather than after. A typo currently costs a round trip and a refusal.

**P2.2 — per-row ＋ / － in the scene list.** In the Python timeline every scene
row carries its own add/subtract, acting on whichever layers THAT row has
ticked. The rebuild's row is read-only: to edit a scene you must first navigate
the playhead into it. On an eleven-scene video that is the difference between
one click and three.

**P2.3 — the balance report table.** Row 4 of the Python control block is a live
table of each ticked scene's two counts and the difference between them. The
rebuild reports a balance only AFTER it runs. Being able to see the imbalance
before deciding to fix it is the point.

### P3 — smaller, and each already understood

**P3.1 — ＋ / － Frame on the LEFT.** The API has always taken a `side`, and both
backends honour it. The rebuild's timeline only ever sends `right`, so there is
no way to insert or delete on the near side of the playhead. This is a button,
not a feature — the plumbing is done.

**P3.2 — frame preloading.** The Python players fetch the next ~40 frames ahead
of the playhead, so playback runs smoothly on a first pass. The rebuild fetches
each frame as it is shown, which stutters on a clip nobody has scrubbed yet.
Playback is for judging timing, so a stutter is not cosmetic.

### P4 — later, by design

**P4.1 — the pages are still the Python ones, for the OLD server.** The Go
backend renders `templates/*.gohtml`, which is 240 kB of the players' own
JavaScript lifted verbatim. Nothing uses them once the React front end is the
way in. They stay until the layered view lands, because they are the only
working layered view there is. Delete them then, and `SAELabel` with them.

**P4.2 — no build output is served.** `npm run dev` is the only way to run the
front end. Once it is used in earnest, `npm run build` and have the Go server
serve `web/dist`, so there is one process rather than two.

**P4.3 — the browser's `Browse…` entry points are thin.** No breadcrumbs, no
recent clips, no search. Nobody has complained.

---

## What is finished, so nobody rebuilds it

- **The whole backend.** All 30 endpoints, proven by the same suite that holds
  the Python server to account. Every ffmpeg rule came across with a comment
  saying which defect paid for it.
- **The MP4 Splitter**, apart from preloading. Mark, six step buttons, Frame
  Editor with Add/Subtract, ＋/－ Zone, Undo, Cut, the hand-off with its
  refusal, Save, Clear edits, Reset.
- **The timeline editor's operations.** Join and Split with their track
  pickers, Update Frame Imbalance, Save all, Cut, per-scene Save and Undo,
  copy/paste by POSITION, and the VTT with its lines edited in place.
- **The renumber lock**, read from `script.json` rather than remembered in the
  page.
- **The keyboard**, exactly as it was.

---

## The trap that will catch the next person

**Restart the Go server after changing it.** A backend running an older build
answers every endpoint perfectly and hands back nothing to draw — a blank page
and a stack trace three layers down. That happened during Phase 3. The front
end now says so outright, but only for the one field it can check.
