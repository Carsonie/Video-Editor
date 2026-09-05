---
name: final-video-clean-up
description: Reclaim disk in the Video-Editor repo AFTER a store's video is finished and released. THE VOICE COMMAND "Final video clean up" (also "clean up the final video", "clean up <store>") means WORK THE NUMBERED PROCEDURE AT THE TOP: review what is parked in the root z_History and ASK whether it is obsolete yet, check dev/ against sandbox/, then build a list with sizes and WAIT — never delete on sight, and move to Trash rather than rm. Covers the one-raw-recording rule, how to prove which recording a finished video was cut from (and why comparing frames does not work), what regenerates for free, what only looks safe, the folders that must never be touched, and the archive-naming trap that makes trim_history.py delete the newest backups. Use whenever asked to clean up, trim, free space, or reduce the size of a video folder, a store's help-videos, raw recordings, the frame cache, or z_History.
user_invocable: true
---
# Final video clean up

Run **after** a build is released, never during editing. Editing is when the
history is worth most.

⚠ **Every size quoted in this file is ski-demo's FIRST pass, 2026-09-04 —
an example, not a target.** The shape holds; the numbers are already stale.
Measure, never assume.

## The rule that governs everything: LIST FIRST, DELETE NEVER

Two separate rules, and both are absolute.

1. **Produce a list with sizes and wait for confirmation.** No deletion is
   implied by "clean up". Carson set this the first time, 2026-09-04, and the
   run that followed found a tool that would have deleted that day's only
   safety copies.
2. **When confirmed, move to `~/.Trash` — do not `rm`.** Trash is reversible
   until he empties it; `rm` is not. Say the total freed and that emptying
   the Trash is his to do.

Report **what should be kept beyond the default**, not just what can go. The
useful sentence is "this one looks droppable and here is why I am not sure".

---

---

## THE PROCEDURE — do these in order

Everything after this section is the *why*. This is the *what*.

0. **Review what is already parked in the ROOT `z_History/`.** Each folder
   there was moved out of the way by a PREVIOUS clean-up, on the
   understanding that one cycle would pass before it went. That cycle is now.
   List each with its size, its date and what it was, and **ask Carson
   whether it is obsolete yet** — one line each, his call. What he confirms
   goes to `~/.Trash`; what he is unsure of stays another cycle.

   **Never clear `z_History/` on your own judgement.** It is the folder that
   exists precisely because a decision was deferred, so deferring it again is
   a valid answer and only he can give it.

1. **Check `dev/` against `sandbox/` and report it**, asked or not. STEP ZERO
   below. If it differs, say so and WAIT.

2. **Sizes first.** `du -sh` the repo, `Customers/` vs `Video-Editors/`, then
   the store's video folder and its `raw_mp4/` — so the list comes out
   ordered by what actually matters, not by what you looked at first.

3. **Group the raw recordings by scenario** and find the multi-take ones.
   `raw_mp4/` is one level ABOVE the video folder and is easy to miss.

4. **For each finished video, identify its source recording** from the
   documentary trail. Say what you found AND what you could not prove.

5. **Dry-run `trim_history.py`** and READ every DROP line. Rename any archive
   whose name it cannot parse BEFORE trimming.

6. **Present ONE list** — safe / needs-a-decision / keep-and-why — with sizes
   and a total.

7. **Wait for confirmation.** Then move to `~/.Trash`, never `rm`.

8. **Re-measure and report** what came off, re-run the six suites if anything
   structural moved, and remind him the Trash is his to empty.

---

## ⚠ STEP ZERO — is `dev/` still identical to `sandbox/`?

Carson keeps `<video folder>/dev/` as his **own safety mirror** of the
working files, held while the editors and the process are still being built.
Set 2026-09-05. It is not a build stage and nothing reads from it.

**Check it FIRST, before proposing anything else, and report the answer
whether or not it is asked for.** Three things must match:

| | sandbox side | dev side |
|---|---|---|
| the scenes | `sandbox/<NN-label>/{segment.mp4, avatar.webm, narration.webm}` | same names |
| the script | `sandbox/script.json` | `dev/script.json` |
| the timing table | `video/vtt.html` | `dev/vtt.html` |

Compare by **SHA-256, not size or mtime** — a re-encode can land on the same
size, and copying rewrites mtime.

```python
import os, hashlib
def h(p):
    x = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""): x.update(b)
    return x.hexdigest()
```

Compare the SET of scene folder names too, not just the files inside them —
a rename (`01-login-and-code` became `01-intro-and-login`) shows up nowhere
else.

**`z_History/` is NOT part of the mirror.** It is history, not a working
version; copying it would double the disk and defeat the point.

### If it differs: SAY SO AND WAIT

Report which files differ and which scenes exist on only one side. **Do not
refresh it unasked** — a stale `dev/` may be exactly the copy he wants back.
On his confirmation:

1. **Move the whole existing `dev/` to the ROOT `z_History/`**, stamped
   `z_History/dev-%Y%m%d-%H%M%S/`. Move, not delete — the old mirror is the
   thing being replaced, so it is the thing most worth keeping for a cycle.
2. Copy `sandbox/`'s scene working files, `sandbox/script.json` and
   `video/vtt.html` into a fresh `dev/`.
3. **Verify by hash** that every file now matches, and say so.

### The trap this walked into

`tests/fixture.py` used to read its source footage from
`dev/01-login-and-code/`. The first refresh moved `dev/` to `z_History` and
would have killed **all six suites** — that scene had been renamed, so no
path would have resolved.

Fixed 2026-09-05: the three clips now live at
`Video-Editors/tests/_fixture_source/` (3.9 MB, never change). **Nothing may
depend on `dev/` again** — it is a mirror that gets replaced wholesale, so
anything pointing at it is a breakage waiting for the next refresh. A new
reference to `dev/` is a bug, not a dependency.

---

## The raw recordings are the whole game

`<store>/help-videos/raw_mp4/` — **2.9 GB across four stores** before the
first clean-up, against 90 MB of everything else in the video folder put
together. Start here.

⚠ **They sit one level ABOVE the video folder.** Walking
`videos/<NN-slug>/` will not find them and the first pass here missed them
entirely. Always:

```bash
find Customers -type d -name raw_mp4 -print0 | while IFS= read -r -d '' d; do
  printf "  %-52s %6s\n" "$d" "$(du -sh "$d"|cut -f1)"; ls -1 "$d" | sed 's/^/      /'
done
```

`-print0`/`-d ''` is not optional — the business folders have spaces in them
and a plain `for d in $(find ...)` shatters every path.

### THE RULE: one recording per scenario, and it is the video's source

Carson's standard, 2026-09-04. Once a video is final, its scenario keeps
**exactly one** raw recording, and that one must be **the file the final
video was actually cut from**. Other scenarios keep their single recording
whether a video exists or not.

Group by scenario before proposing anything — the filename is
`<store>_<scenario>_dev_<HH-MM-SS>_v<N>.mp4`:

```python
m = re.match(r"(.+?)_(.+)_dev_(\d\d-\d\d-\d\d)_v(\d+)\.mp4$", filename)
```

On the first run exactly one scenario in **every** store had multiple takes
— always `owner-one-item`, the first one anybody records — and all 18 other
scenarios had exactly one. Expect that shape.

### PROVING which recording a finished video came from — and how it FAILS

The documentary trail is reliable; the footage is not.

**Look here, in this order:**

```bash
<video folder>/work/boundaries.json      # "raw": names the file outright
<video folder>/z_History/segments/       # e.g. 20260822-103421_v5-cut-of-recording-v7
```

Then corroborate on **duration**: `boundaries.json` records the source's
length, and `ffprobe` it against each candidate. On ski-demo, `132.72` matched
v7 exactly while v8 was `133.00`.

⚠ **DO NOT try to prove it by comparing pixels. It does not work, and it
lies.** Tried three ways on 2026-09-04, all useless:

- matching a shipped frame against each take: one scene picked v8, another
  picked v7
- using the cut plan's own `start_s` offsets: returned the *identical* number
  for all three takes, i.e. measuring nothing

**Why:** the takes are the same scripted flow on the same screen, minutes
apart. Most frames are genuinely identical; the only differences are mouse
paths and timing. There is not enough signal.

So: say what the paperwork says, say plainly that the footage could not
confirm it, and **do not claim proof you do not have**. When Carson cannot be
sure, the answer is to keep the ambiguous take — he kept both v7 and v8 for
exactly this reason.

⚠ **`boundaries.json` can be STALE.** ski-demo's was 2026-08-21 while its
sandbox was rebuilt 2026-08-29. Check its date against `sandbox/script.json`
and say so if it is older.

---

---

## Everything else, and what it is worth

Sizes are ski-demo's first pass — the shape holds, the numbers will not.

### Free, and genuinely free

| | | |
|---|---|---|
| `Video-Editors/cache/**` | **2.6 GB** | re-extracts from source on demand. The biggest single win in the repo. |
| loose `avatar_*`/`segment_*` slugs at `cache/`'s top level | ~250 MB | orphaned by the per-editor cache split; nothing points at them |
| `video/<scene>_v1.mp4` | 5.8 MB | `build_scenes.py` rewrites all 11 every run |
| `video/<store>_<title>.mp4` (no `_v<N>`) | 3.7 MB | unversioned, superseded by the release |
| `onepass/`, `preview/` | 35 MB | intermediate render stages |

### Keep — `Video-Editors/logs/` is NOT a clean-up target

Checked 2026-09-05 and deliberately left alone. Applying keep-3 to it would
delete 7 files and free **154 KB**; the whole folder is 826 KB. Three
reasons, and the first is the one that settles it:

- **All 23 are tracked in git.** Removing them from disk frees the 154 KB and
  keeps the content in history anyway. Nothing is actually reclaimed.
- **They are not repetitive.** One file is one day of one editor's session —
  what was opened, saved, cut. `editor_20260826.log` is the only record of
  that day, not a near-copy of anything.
- **Keep-3 was written for a different problem**: things that pile up in
  near-identical copies and cost hundreds of MB each — build attempts, cache
  extractions, raw takes. A day of log costs 15 KB.

The same reasoning covers `Video-Editors/tests/<suite>/` report files — 452
of them, 3.9 MB, git-tracked, each one the record of a distinct run.

**A rule that frees kilobytes and loses a record is the wrong rule.** Say so
rather than applying it because it is the default.

### Keep — these only look safe

- **`dev/`** — `tests/fixture.py` reads its source clips. Delete it and all
  six suites fail. Confirm with
  `grep -n "dev/" Video-Editors/tests/fixture.py` before proposing it.
- **`Video-Editors/tests/_fixture_source/`** — ⛔ NEVER TOUCH. Three clips,
  3.7 MB, that all six suites build their disposable store from. Not a
  working copy, not a version of anything, not covered by any keep-N rule.
  Gitignored on purpose, so a delete here is unrecoverable from git. It has
  its own README saying the same thing.
- **The released build and its `script_v<N>.json`** — the release refuses
  without the script.
- **Any build that is still `--version`-able.** ski-demo's v32 could never be
  released (its clock disagrees with its frame count by +0.121s) — worth
  saying, not worth keeping.

---

---

## ⚠ `trim_history.py` WILL DELETE THE NEWEST BACKUPS IF NAMES ARE WRONG

Always dry-run it, and **read the DROP lines before agreeing with them**:

```bash
cd ~/Rentify/Video-Editor/Video-Editors
python3 build/trim_history.py "../Customers/<Business>/<store>/help-videos/videos/<NN-slug>"
```

It keeps the 3 newest per folder — but "newest" is decided by `sort_key()` in
`build/trim_history.py`, which reads a date **out of the folder NAME** and
falls back to mtime only when no pattern matches. A name it does not
recognise is ranked BELOW every name it does.

On 2026-09-04 five same-day archives were named `26-09-04_pose`,
`26-09-04_push285`, `26-09-04_closepose_tail`, `26-09-04_inbound`. None
matches a pattern in `STAMPS`, so all of them ranked under August's — and the
dry run proposed deleting that day's only safety copies while keeping backups
a week older. Renaming them flipped it the right way round.

**The recognised shapes are in `STAMPS` at `build/trim_history.py:55`.**

### THE NAMING RULE: `%Y%m%d-%H%M%S`, the same stamp the EDITORS write

Not a convention to be polite about — it is what makes an archive findable
and trimmable.

```python
time.strftime("%Y%m%d-%H%M%S")      # 20260904-150122
```

That is literally what the editors use when they archive a file on save:

    avatar_editor/serve.py:946      hist_dir = .../z_History/<stamp>
    frame_blender/serve.py:581      same
    segment_avatar_editor/serve.py  script line-edits, sandbox snapshots

**Never invent a date format.** Add a label after the stamp if it helps —
`20260904-153414_push285` — the stamp leads, the words follow. To rename an
offender, take the folder's OWN mtime so the name matches when it was made:

```bash
stamp=$(stat -f '%Y%m%d-%H%M%S' "$d")   # macOS: stat -f '%Sm' -t '%Y%m%d-%H%M%S'
mv "$d" "$(dirname "$d")/${stamp}_${label}"
```

Rename BEFORE trimming. Renaming is free and reversible; deletion is not.

---

---

## Where a video's working edits live — DO NOT invent a new folder

Asked 2026-09-04: *"should we make a new folder in sandbox to hold these
while working?"* **No.** The home already exists, at two levels, and both are
written by the editors themselves:

| Level | Path | Answers |
|---|---|---|
| per scene | `sandbox/<NN-scene>/z_History/<stamp>/` | what did THIS clip look like before I saved it |
| whole sandbox | `sandbox/z_History/<date>-v_N/` | what did EVERYTHING look like before this batch |

The second is written by **Save All Scenes**, and
`segment_avatar_editor/serve.py:1623` explains the split in its own words:
one snapshot per batch is a record, one per click is a disk full of
near-identical copies.

A new folder would **split the history in two** — some written by the editors
into `z_History`, some by hand elsewhere — and `trim_history.py` would manage
one and not the other. Two copies of the same thing drifting apart is the
failure this repo has already paid for twice.

So when a working session ends, the checkpoint is **Save All Scenes**, not a
new directory. The fine-grained per-scene history sits underneath it.

---

---

## Related

- **`vtt`** — the timing table; `vtt.html` ships with a release
- **`sae-video-building`**, `PIPELINE.md` — how a video is made
- `build/release_video.py` — what a released folder must contain
- `build/trim_history.py` — the trimmer, and its naming trap
