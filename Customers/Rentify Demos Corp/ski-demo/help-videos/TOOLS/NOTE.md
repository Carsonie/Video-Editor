# TOOLS — overlay cards you can drop onto any scene

Carson made this folder on **2026-09-21**: *"Now I add a folder in BCP_raw called
TOOLS. Add this image overlay there and we will use it various locations. Add a
usage/implementation note.md file if you need it as reference for when I call on
you to add this."*

So this is the reference. When Carson says **"add the dashboard note to scene N"**,
this file is the whole procedure.

---

## WHERE THIS SITS IN THE PIPELINE

A card is laid on at step 4, THE FRAMES — after the words are settled and before
the voice, because a card changes pixels and not timing. The ten steps and the
folders they write are in this repo's `CLAUDE.md`, section **"A VIDEO'S FOLDER
SHAPE"**, settled 2026-09-21. The three new ones are:

    4_avatar/   HeyGen, per scene        (not built)
    5_film/     the deliverable cut      (not built)
    6_mux/      mux_state.json           (not built)

⚠ **A CARD GOES INTO `sandbox/`, NEVER INTO THOSE.** It is burnt into a scene's
own `segment.mp4`, so it is already in every later stage. `4_avatar/` gets
HeyGen's clips, and nothing else.

✅ **THIS FOLDER MOVED UP ON 2026-09-21.** It is `help-videos/TOOLS/` now, not
`help-videos/BCP/TOOLS/` — Carson's call, because the cards serve BCP
and UI recipes alike. **Every path below is written from a scene folder**, so
from `<recipe>/sandbox/<NN-label>/` the card is now four levels up:

    ../../../../TOOLS/back-to-dashboard.png      (it was ../../../TOOLS/…)

⚠ Nothing in code named the old path — the commands in this file were the only
place it was written down, and they are corrected here.

---

## WHAT IS IN HERE

| file | what it is |
|---|---|
| `back-to-dashboard.png` | the card, **full frame 2304×1926**, everything outside the card transparent |
| `make_overlay.py` | the builder — rebuilds that PNG, or a new card with different words |
| `intro-special-skis.png` | the INTRO frame — **opaque, full frame**, held as its own scene |
| `make_intro.py` | the intro builder. Same palette and fonts as `make_overlay.py` |

⚠ **THE TWO BUILDERS ARE OPPOSITES, AND SHARE ONE PALETTE.**
`make_overlay.py` writes a TRANSPARENT layer with a small card in the middle, to
lay over real footage. `make_intro.py` writes an OPAQUE full frame that IS the
picture, held as its own bookend scene (`sandbox/00-intro/`). If a colour or a
face changes in one, change it in the other — that is the only thing keeping the
intro and the in-video notes looking like one set.

The PNG is the asset. The script is there so the next card starts from a settled
design instead of a blank canvas.

### What the card says

```
        Back to the Dashboard
    ─────────────────────────────
       Mac:  Command + K
       Windows:  Control + K

        works from any page
```

### The design, and why each value is what it is

| thing | value | why |
|---|---|---|
| card | 1500 × 560, radius 30, centred | lands at x 402, y 683 in a 2304×1926 frame |
| card fill | `#18181A` at alpha 240 | matches the app's own dark panels; the page shows through faintly |
| card edge | `#1F6FB2`, 5px | the app's own Update-button blue, so the note looks built in |
| heading | Arial Bold **74pt**, white | Carson: *"reduce the font size by 2 pts"* — it was 76 |
| keys | Arial Bold 72pt, **`#6FCF97`** | Carson: *"the yellow is too bold, lets try green"*. It was `#FFC72C` |
| footnote | Arial 46pt, `#A8AAB0` | quiet, not part of the instruction |

⚠ **THE KEYS ARE SPELLED OUT, NOT SYMBOLS.** The first build used `⌘` (U+2318)
and it rendered as an **empty box** — no Arial on this Mac carries that glyph.
The word is also plainer for a viewer who has never met the symbol. Do not
"fix" this back to a symbol without looking at a rendered frame at full size.

---

## HOW TO PUT IT ON A SCENE — the five steps, in order

### 0. Check the scope first

Is that scene on the timeline Carson has open right now? Read his **live Chrome
tab**, never the newest `seq_` cache folder:

```bash
osascript -e 'tell application "Google Chrome" to get URL of every tab of every window'
# -> http://localhost:8846/seq_<slug>/viewer.html
python3 -c "import json;d=json.load(open('/Users/carsonkramer/Rentify/Video-Editor/Video-Editors/cache/segment-avatar-editor/seq_<slug>/view.json'));print([x['n'] for x in d['manifest']])"
```

Out of scope, or the words do not fit the target? **Stop and confirm.** Full rule
in `Basic_E2E_Testing/Carsons_Files/What is SAE -VTT-setup-and-launch.txt` §5.4b.

### 1. Back the clip up

```bash
cd "<...>/BCP/<recipe>/sandbox/<NN-label>"
STAMP=$(date +%Y%m%d-%H%M%S); mkdir -p "z_History/$STAMP"
cp segment.mp4 "z_History/$STAMP/segment.mp4"
```

⚠ **AND SAY THE STAMP OUT LOUD IN THE REPORT.** Every card so far has been
re-done at least once — the colour changed, then the font size. Each redo starts
by restoring this backup, because a second card drawn over the first leaves the
first showing faintly through alpha 240.

### 2. Check the clip's size

```bash
ffprobe -v error -select_streams v -show_entries stream=nb_frames,width,height \
        -of default=nw=1 segment.mp4
```

Every special-skis scene is **2304 × 1926**. A different size needs a rebuilt
card — `make_overlay.py --w <W> --h <H>` — or it sits in a corner at the wrong
scale.

### 3. Burn it in

⚠ **ffmpeg's `n` IS 0-BASED. THE SAE'S FRAME NUMBERS ARE 1-BASED.** So scene
frame **214** is `n=213`. Getting this wrong puts the card one frame off, which
nobody sees until playback.

```bash
ffmpeg -v error -i segment.mp4 -i "<store>/help-videos/TOOLS/back-to-dashboard.png" \
  -filter_complex "[0][1]overlay=0:0:enable='eq(n,213)'[v]" \
  -map "[v]" -map "0:a" \
  -c:v libx264 -crf 16 -preset medium -pix_fmt yuv420p \
  -c:a copy -fps_mode cfr out.mp4 -y
mv out.mp4 segment.mp4
```

- `overlay=0:0` — the card is full frame, so there is no x/y to get wrong
- `eq(n,213)` one frame · `between(n,213,287)` a range
- `-c:a copy` — never re-encode the voice
- `-fps_mode cfr` — a ragged clip is what makes the voice drift off its picture
- ⚠ **zsh eats an unquoted `0:a?`** ("no matches found"). Write `-map "0:a"`.

### 4. Prove it, by pixels and not by eye

```bash
python3 - <<'EOF'
from PIL import Image
import subprocess, glob, tempfile, os
d=tempfile.mkdtemp()
subprocess.run(['ffmpeg','-v','error','-i','segment.mp4','-vsync','0',f'{d}/%04d.png'],check=True)
BOX=(402,683,1903,1244)          # where the card sits
for p in sorted(glob.glob(f'{d}/*.png'))[-4:]:
    im=Image.open(p).convert('RGB').crop(BOX); px=im.load(); w,h=im.size
    green=sum(1 for y in range(0,h,3) for x in range(0,w,3)
              if px[x,y][1]>170 and px[x,y][1]-px[x,y][0]>40)
    print(os.path.basename(p), 'green px', green)
EOF
```

A frame with the card reads about **2,876** green pixels. A frame without reads
**0**. Check a frame either side of the range too, so an off-by-one shows up.

⚠ **NEVER MEASURE A THIN LINE ON A DOWNSCALED FRAME.** A 320px scan once
reported "no rings" on a video that plainly had them. Full resolution only.

### 5. Sync it, then rebuild the open timeline

```bash
cd ~/Rentify/Basic_E2E_Testing/Master_Flows/Recorder
python3 scripts/sae_vtt_sync.py "<the recipe folder>" --apply --scenes 20
curl -s "http://localhost:8846/api/open-seq-go?root=<biz>/<store>/help-videos/BCP/<recipe>&ns=19,20,21"
```

Then tell Carson to press **Cmd+R**.

---

## ONE FRAME IS 0.04 SECONDS — NOBODY CAN READ IT

This is the trap, and it caught the first build. Carson asked for the card on
*"the last frame image"*. That is **one frame**, 0.04s at 25fps, and scene 20
does not freeze at the end — the picture is still moving right into it.

A card only works if the frame is **held**. Two ways:

- **hold the last frame** — duplicate it, e.g. 75 frames for 3 seconds. The
  scene gets longer, so the voice bed is rebuilt behind it. Bonus when the
  scene's line is rushed: scene 20 speaks at 195 wpm and wants ~40 more frames,
  so a 75-frame hold fixes both at once.
- **lay it over footage already there** — `between(n,a,b)`. The length does not
  change and nothing re-syncs, but the page moves under the card.

**Duplicate through the SAE, not ffmpeg**, so the editor's own cache agrees:

```bash
curl -s -X POST http://localhost:8846/api/frames/dup -H 'Content-Type: application/json' \
  -d '{"slug":"<base_slug from view.json>","at":214,"count":75,"side":"right"}'
```

Then the green **Save Timeline** writes it down. To undo: `/api/frames/del-span`
with the exact `a`/`b`, then `/api/frames/restore` with a 1:1 `frame_map` to
clear the EDITED flag.

⚠ **ADDING FRAMES MAKES THE SCENE LONGER, SO THE VOICE IS DIRTY.** `--apply`
re-speaks it. A card on a scene whose line is already rushed is a good thing;
on one with dead air at the end it makes the dead air worse. Read the scene's
**gap** column in the VTT Editor before adding frames.

---

## MAKING A DIFFERENT CARD

```bash
cd "<store>/help-videos/TOOLS"
python3 make_overlay.py --head "Back to the Store" \
                        --keys "Mac:  Command + J" \
                        --keys "Windows:  Control + J" \
                        --foot "works from any page" \
                        --out back-to-store.png
```

Look before you burn — it composites onto a real frame for you:

```bash
python3 make_overlay.py --preview "../special-skis/sandbox/20-last-variant/segment.mp4" --frame 214
```

That writes `<name>_on_frame214.png` beside the card. **It is a look, not an
asset — delete it when you are done.**

---

## WHERE THIS CARD IS ALREADY USED

| recipe | scene | frames | ffmpeg `enable` | when |
|---|---|---|---|---|
| `special-skis` | 20 `last-variant` | **185-214** (timeline 551-580), 1.2s | `between(n,184,213)` | 2026-09-21 |
| `special-skis` | 21 `sign-out` | **1-30** (timeline 581-610), 1.2s | `between(n,0,29)` | 2026-09-21 |

Scene 20 is still **214 frames / 8.56s** — the card went over footage that was
already there, so nothing was added and nothing re-synced. Carson's call:
*"add the note to the last 30 frames in #20"*.

Keep this table current, because a card burnt into pixels leaves no other record.

⚠ **READ THE SCREEN BEFORE PLACING THE CARD.** Scene 21's first frames are the
Dashboard itself, and the app already prints *"For accessing menu hold Cmd + K"*
under its own title. So the card there tells a viewer how to reach the page they
are already on, and it covers the Questions and Logout tiles — which is what that
scene is about. Flagged to Carson on 2026-09-21; the placement is his call, and
`z_History/20260921-112717` is the clean clip if it comes off.
