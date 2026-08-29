---
name: vtt
description: Print a help video's Video Timing Table — per scene, how long the demo footage runs, how long Sarah's line takes to say, and the gap between them. Use when checking a store's video timing before or after a build, or when asked to "show the vtt" for a video.
user_invocable: true
---

# VTT — Video Timing Table

Not to be confused with WebVTT (`.vtt` subtitles). Different thing entirely.

The tool lives in this repo:

    shared/vtt.py

## What it does

For each scene: how long the demo clip runs, how long Sarah's line takes to
say, and the **gap** between them. The gap is the whole point — it is how
long she sits frozen in the corner with nothing to say, and it is invisible
until someone actually watches the finished video.

## Running it

```bash
cd ~/Rentify/Video-Editor
python3 shared/vtt.py "Customers/<Business>/<store>/help-videos/videos/<NN-slug>"
```

(For a store still on the old flat layout, point it at `help-videos/final`
instead.)

## Where the numbers come from

- **Clip lengths** are read straight from the files on disk — never
  hand-typed.
- **The lines** come from that video folder's `script.json`, which is the
  single source of truth for the copy. Edit the lines there and re-run —
  never retype a line into a doc or a chat message, which is how copy drifts
  from what actually got rendered.
- **Speech length** is estimated at the voice's MEASURED words-per-second
  (Derya: 3.44 wps), taken from clips already rendered. An earlier guess of
  2.70 understated every line by ~25% and hid a third of the dead air.
  Re-derive it whenever the voice or its speed setting changes.

## Reading the output

Each row shows: scene label, clip length, speech length, gap, and the exact
line Sarah says. A trailing summary gives the total clip time, total speech
time, total gap, and word count — plus a flag if any scene's gap exceeds the
2.5s threshold, and the dead-air percentage for the whole video.

A gap on its own is not a defect — the build holds the last frame while she
finishes talking. It only becomes worth fixing when a single scene's gap is
large enough to read as a stall (see the `sae-video-building` skill's "closing
hold" and "held frame" notes for what counts as normal versus worth a second
look).

## "Show me the vtt" means THIS table, by default

When asked to "show the vtt" for a video, show the **combined table**
below (timing + frame counts + a narrative row under every scene) — not
`vtt.py`'s plain CLI output. The CLI output is still what feeds it (see
"Running it" above), but it is a source, not the thing to display. Only
show the plain CLI table instead if asked for it specifically by name.

## Source: always `sandbox/`, never `dev/`, never anything else

The combined table's numbers come from `sandbox/<NN-label>/` — the same
folder the editor reads and writes. This is locked in, not a default that
quietly falls back elsewhere:

- The frame-count loop below points at `<video folder>/sandbox` explicitly.
- `vtt.py`'s clip length goes through `paths.py`, which resolves
  sandbox → dev → flat *per file* — so if a scene's `segment.mp4` is
  missing from `sandbox/` for some reason, it would silently read from
  `dev/` instead without saying so. If that ever happens, say so out loud
  rather than showing a number as if it came from sandbox: "scene N's
  segment isn't in sandbox — this reading is from dev/", not a silent
  substitution.

## The combined table — timing plus frame counts

`vtt.py` alone doesn't print frame counts, only timing. When checking a
store's sandbox in detail — confirming the editor and the sandbox agree,
or explaining why `assemble_video.py` printed `clip held` on a scene —
pull both together:

```bash
cd ~/Rentify/Video-Editor

python3 shared/vtt.py "<video folder>"

VF="<video folder>/sandbox"
for d in "$VF"/*/; do
  name=$(basename "$d")
  [ -f "$d/segment.mp4" ] || continue
  seg=$(ffprobe -v error -count_frames -select_streams v:0 \
        -show_entries stream=nb_read_frames -of csv=p=0 "$d/segment.mp4")
  av=$(ffprobe -v error -c:v libvpx-vp9 -count_frames -select_streams v:0 \
       -show_entries stream=nb_read_frames -of csv=p=0 "$d/avatar.webm")
  echo "$name: segment=$seg avatar=$av"
done
```

Merge the two outputs into one table by scene number. **Give every scene row
a second row underneath it holding just the narration line** — the numeric
row stays scannable, and the words she actually says sit on their own line
instead of stretching the row width.

**Name the store in the column header itself — never just "scene."** More
than one store's table can be in view across a conversation, and a bare
"scene" column gives no way to tell them apart at a glance. Use
`# <Store-Name> scenes`, with the store's actual name in place of
`<Store-Name>`:

| # | Canoe-Demo scenes | clip | speech | gap | segment frames | avatar frames |
|---|---|---|---|---|---|---|
| 1 | login-and-code | 7.9s | 6.7s | 1.3s | 198 | 214 |
| | *"Enter your email, and we'll send you a 4 digit verification code you can enter here to sign in and create your account."* |
| 2 | dashboard-new-order | 3.5s | 2.3s | 1.2s | 88 | 124 |
| | *"From your dashboard, tap New Order to begin."* |

The narration row is a single cell spanning the row (markdown tables can't
truly merge cells, so leave the other columns blank rather than repeating
dashes into every one) — italicized, quoted, exactly as it reads in
`script.json`. Never retype it from memory; copy it from the VTT output or
the file itself.

**Segment and avatar frame counts matching exactly (e.g. 482/482) is not
automatically a good sign.** It can mean the avatar was correctly built to
the footage's length — or it can mean the avatar was silently trimmed short
to fit, cutting off the end of Sarah's actual recorded line. Check the
avatar's own duration against its source `narration.webm` (both frame
counts should be close to the *narration's* length, not forced to match the
segment) before trusting a clean match as evidence nothing is wrong.

## The EVTT — the editor's own live VTT panel

**A third, separate thing from the two tables above.** The Segment and Avatar
Editor has its own built-in VTT view, right in the browser, alongside the
timeline. Call this one the **EVTT** to keep it unambiguous from `vtt.py`'s
report and the combined table — three different things that all show
similar numbers, easy to conflate by accident.

⚠ **Do not change the EVTT's behavior or appearance unless specifically
asked to.** This section documents what it already does, for reference —
it is not an invitation to "improve" it. It lives in
`segment_avatar_editor/player.py` (`renderVtt()`, `paintVttRow()`,
`paintVttSum()`), served as part of the editor at `shared/serve.py`'s
`/api/vtt` route.

### What it looks like

A header bar, then one row per scene (plus bookend rows for `00-opening` and
`99-closing`, greyed out with "not a script scene — no line" — shown anyway,
because a table that silently skips rows doesn't match what's actually
playing):

```
VTT                          110.1s clip · 92.7s said · 16% dead air · 1 over 2.5s
─────────────────────────────────────────────────────────────────────────────
1  Hi, I'm Sarah. Let me show you how to place your first order with...   19.3s clip · 16.0s said · 3.3s gap
2  From your dashboard, tap New Order to [begin.]                         3.5s clip · 2.3s said · 1.2s gap
3  We need to add a person to the order. You can add yourself, or...      6.4s clip · 5.2s said · 1.2s gap
```

### What makes it different from `vtt.py`

- **Clip length comes from the LIVE timeline, not the file on disk.** The
  backend (`/api/vtt`) sends only the lines and the word-count math; the page
  itself supplies the clip length from whatever is actually on the timeline
  right now — including edits that haven't been saved yet. `vtt.py` reads the
  committed file, which is right for a report and wrong for an editor: in an
  editor, a gap that doesn't move while you add frames is a lie with a
  decimal point.
- **The line is editable in place.** Click a row to turn it into a textarea;
  typing updates the gap live (`paintVttRow` repaints as you type, before
  anything is saved). Blur saves to `script.json` — the same file
  `render_narration.py` reads, so editing here is editing what HeyGen gets
  paid to say. Esc reverts to the last saved line. A previous version is
  copied to `z_History/line-edits/` first, every time.
- **Per-word spans.** Each word in the line is its own `<span>`, which is
  what lets the currently-spoken word highlight during playback (`begin.` in
  the screenshot above) — `vtt.py`'s plain-text report has no equivalent.
- **Clicking a row jumps the timeline** to that scene's start.

### Reading the gap color

Per row, the gap is color-coded, not just printed:

| color | meaning |
|---|---|
| green (`gapOk`) | normal — under the 2.5s threshold |
| orange (`gapBad`) | over 2.5s — long enough to be worth a look |
| red (`gapNeg`) | **negative** — the line is still being said when the footage has already moved on. This is the defect that ships silently; a positive gap just holds a frame, a negative one cuts her off. |

### The header summary

`{clip}s clip · {said}s said · {dead}% dead air`, plus `· N overrun` if any
scene has a negative gap, `· N over 2.5s` if any exceed the threshold, and
`· N unsaved` if there are live edits not yet written to `script.json`.
