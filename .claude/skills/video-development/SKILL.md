---
name: video-development
description: The small hands-on tasks that come up while editing a help video in the browser. FOUR NAMED PHRASES trigger it directly, and they are printed in the Segment and Avatar Editor's own "ASK CLAUDE" box so Carson can read them off the screen: "Capture Still" (take the frame currently on screen, from the right source file, into Sarah's library), "Read Screen" (say which scene, frame, selection and unsaved state his own Chrome tab is showing), and "Which Source" (which of the frame cache, avatar.webm or narration.webm a job should read), and "Open Close Pose" (put Sarah's 3-frame rest pose at the end of a scene, the start of the next, or both, so the cut between them is invisible). Also use whenever asked to grab, capture or save a frame, still or pose, to add something to Sarah's library from what is on screen, to say where he is in an editor, or when a task needs a frame out of a scene at full quality. What a still IS and how it is named lives in the sarah-library skill; this one is how to get one.
user_invocable: true
---

# Video development — the occasional hands-on tasks

Small jobs done *while looking at an editor*, as opposed to running the
pipeline. Each one below has already cost time once.

**This skill is the HOW. The WHAT lives elsewhere — do not restate it here:**

- **`sarah-library`** — what a still is, the three-file set, the naming, the
  rest-pose / uncertainty / idle standards, when each is used.
- **`editor-launchers`** — starting and reloading the four editors.
- **`PIPELINE.md`** — the nine steps that make a video.

**THE PHRASES.** Carson says one of these and the matching section
below is followed rather than improvised. They are printed in the Segment
and Avatar Editor's own **ASK CLAUDE** box (bottom right of the timeline
page, under the status bar) so he can read them off the screen:

| Phrase | Section |
|---|---|
| **Capture Still** | the frame on screen → the right source → Sarah's library |
| **Read Screen** | which scene, frame, selection, what is unsaved |
| **Which Source** | cache vs `avatar.webm` vs `narration.webm` |
| **Open Close Pose** | Sarah's 3-frame rest pose at a scene boundary |

They are named in this file's `description:` too, so they match exactly
rather than by judgement. **Adding a phrase means three edits, always
together** — the box in `seq.html`, the `description:` above, and a section
here. A phrase in the box with no procedure behind it is a promise the
skill cannot keep.

Two copies of the same rule drift. If something here starts explaining what
a still *is*, it belongs in `sarah-library` instead.

---

## "Read Screen" — reading Carson's live tab

He works in his own Chrome, not the Browser pane. The pane's copy of a page
is a *different browser* — it loads fresh at frame 1 and knows nothing about
where he is.

Only two things are readable without setup: a tab's **URL** and its
**title**. The title carries more than it looks — the editor puts the scene
list in it:

```
Segment and Avatar Editor — timeline: scenes 1, 2
```

For anything inside the page, Chrome needs one setting, and only Carson can
turn it on:

> **View → Developer → Allow JavaScript from Apple Events**

It is in **Chrome's own menu bar**, NOT in DevTools Settings. He looked in
DevTools first, which is the obvious wrong place — say "menu bar" when
asking. It is a real permission: any AppleScript on the machine can then
run JS in his tabs. Reasonable to leave on while working and off after.

### The call that works

```bash
osascript <<'AS'
tell application "Google Chrome"
  repeat with w in windows
    repeat with t in tabs of w
      if URL of t contains "seq_" then
        return (execute t javascript "document.getElementById('pos').innerText")
      end if
    end repeat
  end repeat
end tell
AS
```

**Keep the JavaScript simple.** Passing it through AppleScript mangles
things:

- `JSON.stringify({...})` with several keys returned `missing value` — the
  braces do not survive. **Join the values into one string instead:**
  `[a, b, c].join(' ||| ')`.
- Regexes fail on the escaping (`\\s+` arrives broken). Use `innerText`,
  which is already collapsed, rather than a regex tidy-up.
- One `getElementById(...)` per value, no helper functions.

### The ids worth reading — timeline page

| id | what it says |
|---|---|
| `slider` | `.value` is the current global frame |
| `pos` | `timeline 441 / 570 · 17.60s of 22.80s` |
| `rep` | the status bar: SCENE, SEGMENT, SELECTION, OVERLAY, zones |
| `vttSum` | `22.8s clip · 18.9s said · 17% dead air · 1 over 2.5s` |
| `soloBtn` | `◉ Both`, or which track is soloed |
| `sceneList` | the rows; `input[type=checkbox]:checked` = ticked scenes |

Read the ids out of `segment_avatar_editor/web/seq.html` rather than
guessing them — several obvious guesses (`scStat`, `vttSummary`, `statbar`)
do not exist.

---

## "Capture Still" — from the frame on screen

The job: Carson is looking at a frame and wants it kept. Today's example was
Sarah's smile at frame 441 of `01-intro-and-login`.

### "Which Source" — which file to take it from, and it is the whole task

Three files hold "the same" frame and only ONE is right.

| source | size | frame-aligned? | use it? |
|---|---|---|---|
| `cache/<editor>/<slug>/frames/frame_NNNNN.png` | 750px canvas, she is ~191×198 | yes | **no** — too small, a 300px still would be upscaled |
| `sandbox/<scene>/avatar.webm` | 1152×1152, she is ~294×304 | **yes** | **YES** — near 1:1 for a 300px corner still |
| `sandbox/<scene>/narration.webm` | 1920×1080, full-body seated | **NO** | **no** — see below |

**`narration.webm` is a trap.** It is the raw HeyGen render, before
placement. Two things are wrong with it:

1. **Different shot.** Full-body seated, not the head-and-shoulders crop the
   corner uses. `morph_avatar_corner.py` does that crop.
2. **Different frame count.** On scene 1 it is **499 frames against
   avatar.webm's 482**. So its "frame 441" is a different moment — checked
   once, and she had her mouth open in it.

Verify alignment before trusting any source:

```bash
ffprobe -v error -c:v libvpx-vp9 -select_streams v -count_frames \
        -show_entries stream=nb_read_frames -of csv=p=0 <file>
```

`-c:v libvpx-vp9` is not optional. Without it ffprobe reports an alpha WebM
as `yuv420p` and the count is wrong.

### The extraction

`n` is zero-based, so frame 441 on screen is `n=440`:

```bash
ffmpeg -v error -c:v libvpx-vp9 -i "<scene>/avatar.webm" \
       -vf "select=eq(n\,440)" -vsync 0 -frames:v 1 -y out.png
```

If `select` yields nothing (it silently produced an empty output once), seek
instead — `-ss $(python3 -c 'print(440/25)')` before `-i`.

Ask the running page which file it is showing rather than working it out:

```javascript
document.getElementById('overImg').getAttribute('src')
// ../avatar_f3e067f5/frames/frame_00441.png?v=...
```

The slug is what you need; swap the cache path for the sandbox `avatar.webm`.

### Framing it to match

Measure an existing still rather than inventing geometry:

```python
Image.open("Sarah/stills/sarah-rest-pose-corner-300-alpha.png").getbbox()
# (0, 10, 277, 300)  -> flush left and bottom, ~10px headroom, 277 wide
```

Then scale her bbox to that width and paste flush bottom-left on a 300×300
transparent canvas. The preview is the same image over `#212121`.

### LOOK AT IT BEFORE AND AFTER

Non-negotiable, and the reason a button cannot do this job yet. Open the
extracted frame and the finished still as images.

- A mid-clip frame is **almost always mid-word** — `sarah-library` says the
  settled poses live at a clip's first and last frames.
- The frame Carson is on may not be the one he means.
- Alpha problems only show against a background, which is what the preview
  is for.

### `-full-alpha.png` — usually cannot be made this way

The other stills carry a third file at **608×1080**. It is a different crop
again, from the raw HeyGen render, and `avatar.webm` cannot produce it —
that would be a 2× upscale of an already-cropped image. Say so rather than
fabricating one. Making a real one means resolving the narration/avatar
frame offset first.

---

## Why these are a skill and not buttons

Every step above turns on **looking at the picture** — is that a smile or a
mid-word mouth, is the framing right, is this even the frame he meant. A
button would have silently taken the 750px cache frame and produced a soft
still that only shows up wrong in a finished video.

A button becomes the right answer once a procedure here is settled and being
run often. This file is what makes one safe to write.

---

## "Open Close Pose" — making a scene cut invisible

Carson's standard, defined 2026-09-04: a scene **ends** on Sarah's rest pose
and the next scene **begins** on the same one, so the join reads as one
continuous shot rather than two clips butted together. Same image both
sides, so there is nothing for the eye to catch.

**The asset already exists — do not rebuild it:**

```
Sarah/gap-fillers/sarah-open-closing-pose-3f-alpha.webm
  1152x1152 · yuva420p · 25fps · 3 frames · no audio
```

Built from `stills/sarah-rest-pose-corner-300-alpha.png`, scaled to 294x304
and placed at (836, 848) on a 1152x1152 transparent canvas — the geometry
measured off a real `avatar.webm` frame, not guessed. Verified against one
side by side: same size, same position, no jump.

### Why it is a CLIP and not painted frames — the trap

The obvious move is to composite the still onto the last three cache PNGs.
**It does not survive.** `/api/save` calls `build_segment()`, which rebuilds
the track **from the source file** using `frame_map`. Painted cache frames
look right in the editor and are silently discarded on Save — a lie that
only shows up in the finished video.

Anything that must persist has to be real source footage. That is why this
is a webm.

### Before placing it, check the tail

The pose fixes 3 frames. Look at what is actually wrong first:

```bash
python3 -c "import json;m=json.load(open('<cache>/<over_slug>/meta.json'));
print(m['speech_end'], m['nb_frames'])"
```

On ski-demo scene 1 she stops speaking at 17.565s (frame 439) but keeps
**mouthing to frame 480** — 43 bad frames, not 3. Three frames of rest pose
at the very end leaves 40 wrong ones in front of it. Say so rather than
placing it and calling the scene fixed.

### Where it goes

Carson names the position each time — end of a scene, start of the next, or
both. Do not assume: replacing the last frames and appending after them are
different edits with different lengths.
