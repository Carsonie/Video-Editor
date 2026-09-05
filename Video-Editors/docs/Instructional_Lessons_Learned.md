# Instructional_Lessons_Learned.md
# Rentify Help Videos — Lessons Learned & Updated Pipeline
# Date: June 24, 2026
# Context: Captured after completing the "First Time Ordering" pilot video
# and installing the HeyGen CLI + Skills suite.
# Use this alongside INSTRUCTIONAL.md as the evolving development guide.

---

## OVERVIEW

This file captures everything learned during the First Time Ordering pilot that
should inform how we build the NEXT help video. It supersedes some approaches
in INSTRUCTIONAL.md where we have found better or faster methods. It also captures
honest tradeoffs so future development can make informed decisions.

---

## 1. THE NEW PIPELINE (CLI-FIRST)

The HeyGen CLI v0.1.5 is now installed and authenticated. This changes the
workflow significantly from the Python-script approach used in the pilot.

### What changed
- `generate_avatar_video.py` → `heygen-sarah` CLI alias (or kept for verbatim clips)
- Manual polling → `--wait` flag handles it automatically
- No captions before → CLI returns captioned URL + SRT + GIF automatically
- No defaults before → `heygen-sarah` alias bakes in Sarah's IDs

### Sarah's locked CLI alias
```bash
heygen-sarah --prompt "Your narration line here."
```
This expands to:
```bash
heygen video-agent create \
  --avatar-id 468eabb3326a4d8587ba29d065b1eba7 \
  --voice-id 04d0ae1d0af2489ca7d3bb402a39a890 \
  --mode generate \
  --wait \
  --human
```
Returns: Video URL, Captioned Video URL, Subtitle URL (SRT), GIF URL, Thumbnail URL.

> ⚠️ NOTE: Using heygen-sarah --prompt can be very time consuming. Each clip
> generation takes 30–120 seconds minimum on HeyGen's servers, plus the time
> to write a good prompt. For a video with 9+ narration segments, budget
> significant time for generation alone. Plan scripts in advance, generate
> clips in batches, and save all video_ids — you cannot re-download without
> the ID. Consider generating all clips in one session before compositing.

---

## 2. COMPLETE STEP-BY-STEP PIPELINE FOR NEXT VIDEO

### Step 1 — Prep the raw MP4 (ffmpeg only, no HeyGen)

```bash
# Inspect first — always look before cutting
ffmpeg -i videos/source/RAW.mp4 2>&1 | grep -e Duration -e Stream

# Grab opening frame to confirm the right starting screen
ffmpeg -y -ss 0.3 -i videos/source/RAW.mp4 -frames:v 1 -update 1 /tmp/open.png
ffmpeg -y -i /tmp/open.png -vf scale=300:-1 -update 1 videos/temp/check/open_sm.png

# Trim dead time from the head
ffmpeg -y -ss <N> -i videos/source/RAW.mp4 -c copy videos/source/RAW-2.mp4

# Trim the tail
ffmpeg -y -i videos/source/RAW-2.mp4 -t <T> -c copy videos/source/RAW-3.mp4

# Remove dead wait time in the MIDDLE (e.g. a 5s pause at 11-16s)
ffmpeg -y -i IN.mp4 -t 11 -c:v libx264 -c:a aac -pix_fmt yuv420p -r 60 /tmp/p1.mp4
ffmpeg -y -ss 16 -i IN.mp4 -c:v libx264 -c:a aac -pix_fmt yuv420p -r 60 /tmp/p2.mp4
printf "file '%s'\nfile '%s'\n" /tmp/p1.mp4 /tmp/p2.mp4 > /tmp/cut.txt
ffmpeg -y -f concat -safe 0 -i /tmp/cut.txt \
  -c:v libx264 -c:a aac -pix_fmt yuv420p -r 60 videos/source/demo-clean.mp4

# Normalize to canonical spec
ffmpeg -y -i videos/source/demo-clean.mp4 \
  -c:v libx264 -c:a aac -pix_fmt yuv420p -r 60 \
  videos/source/demo-final.mp4
```

**Lessons learned:**
- Player timestamps are mm:ss NOT raw seconds. "111" = 1:11 = 71s. Always convert.
- The Rentify app is dark-themed — there is no white screen to land on. Accept it.
- Grab frames at key timestamps BEFORE trimming to confirm you're cutting at the right spot.
- The 11–16s wait-time cut we made improved the video significantly — always scan
  for dead air in the demo recording before compositing.

---

### Step 2 — Write the narration script

**Before generating a single clip:**
1. Watch the full demo recording once through
2. Write one short narration line per screen/step
3. Fix ALL grammar/typos before generating (every typo costs a credit to fix)
4. Build a timing table:

| Segment | Screen appears (s) | Script | Est. duration | Ends (~s) | Next starts (s) | Collision? |
|---------|-------------------|--------|---------------|-----------|-----------------|------------|
| code | 7.7 | "When we have your email..." | ~6.7s | 14.4 | 18 | ✓ clear |
| name | 18 | "Since this is your first time..." | ~4.8s | 22.8 | 25 | ✓ clear |

**Key rules:**
- Scripts are verbatim — HeyGen speaks exactly what you write (when using
  generate_avatar_video.py or heygen video create; Video Agent may rewrite).
- Estimate ~2.5 words/second for rough duration planning.
- Leave ~0.5s buffer between segments. Two avatars talking at once = broken.
- Real duration only comes from generating the clip. Estimates are for planning only.
- If a line is longer than the screen it describes, she finishes over the next screen.
  That is fine — do NOT freeze the demo to fit narration.

---

### Step 3 — Generate the intro clip

```bash
heygen-sarah --prompt "Hi. I'm Sarah. Learn how to place your first equipment rental order."
```

Download the MP4:
```bash
heygen video download <video_id> --output videos/temp/intro.webm
```

Then composite over brand background with fade-in:
```bash
ffmpeg -f lavfi -i "color=c=#E8F4F8:s=1152x1080:d=<DUR>:r=60" \
  -c:v libvpx-vp9 -i videos/temp/intro.webm \
  -filter_complex "\
[1:v]scale=1130:2005[p];\
[0:v][p]overlay=(W-w)/2:-180:shortest=1,fade=in:st=0:d=0.5[v];\
[1:a]afade=in:st=0:d=0.5[a]" \
  -map "[v]" -map "[a]" -c:v libx264 -c:a aac -pix_fmt yuv420p -r 60 \
  videos/temp/intro_solid.mp4
```

**Lessons learned:**
- HeyGen's opening frame is uncontrollable — the avatar often starts mid-word.
- The 0.5s video + audio fade-in softens this significantly. Always add it.
- Leading the script with "Hi." as its own sentence (period, not comma) gives
  a calmer opening frame than "Hi, I'm Sarah."
- The intro uses a DIFFERENT crop/framing than the corner clips. Don't mix them up.

---

### Step 4 — Generate the corner intro clip (shrink-move transition)

This is the clip where Sarah shrinks from center to bottom-right as the demo begins.

```bash
heygen-sarah --prompt "Let me show you how. Here are the steps to complete your first rental."
```

Download, then crop to head-and-shoulders (406x360, 50px from top):
```bash
ffmpeg -y -c:v libvpx-vp9 -i videos/temp/corner.webm \
  -vf "crop=406:360:0:50,format=yuva420p" \
  -c:v libvpx-vp9 -pix_fmt yuva420p -auto-alt-ref 0 \
  videos/temp/corner_tight.webm
```

Verify framing + alpha:
```bash
ffmpeg -y -f lavfi -i color=white:s=406x360:d=1 -c:v libvpx-vp9 -i videos/temp/corner_tight.webm \
  -filter_complex "[0][1]overlay=shortest=1" -frames:v 1 -update 1 videos/temp/check/corner_sm.png
```

**Lessons learned:**
- The raw HeyGen webm is 406x720 (full seated shot). The crop=406:360:0:50 removes
  the lower body and hands to give a head-and-shoulders look.
- Always verify alpha with a white background composite. Black box = alpha was dropped.
  The fix: always -c:v libvpx-vp9 on webm inputs, NEVER the native decoder.
- Match the intro crop to the corner crop so the shrink-move transition reads as
  continuous motion rather than a jump between two different shot framings.

---

### Step 5 — Generate all narration clips in one batch

> ⚠️ TIME NOTE: Each clip takes 30–120 seconds to generate. For 9+ segments,
> that's 10–20 minutes of generation time minimum. Generate all clips FIRST,
> then composite. Do not interleave generation and compositing.

For each narration segment:
```bash
# Option A — CLI (Video Agent, may rewrite script slightly)
heygen-sarah --prompt "Your exact narration line."

# Option B — Python script (verbatim, transparent webm — use for precise scripts)
export HEYGEN_API_KEY=$(grep '^HEYGEN_API_KEY=' .env.local | cut -d= -f2)
python3 .claude/skill/hey_gen/generate_avatar_video.py \
  --avatar 468eabb3326a4d8587ba29d065b1eba7 \
  --voice 04d0ae1d0af2489ca7d3bb402a39a890 \
  --script "Your exact narration line." \
  --webm --out videos/temp/seg-NAME.webm
```

After each clip, crop to tight corner framing:
```bash
ffmpeg -y -c:v libvpx-vp9 -i videos/temp/seg-NAME.webm \
  -vf "crop=406:360:0:50,format=yuva420p" \
  -c:v libvpx-vp9 -pix_fmt yuva420p -auto-alt-ref 0 \
  videos/temp/seg-NAME-tight.webm
```

Get exact duration for timing table:
```bash
ffmpeg -c:v libvpx-vp9 -i videos/temp/seg-NAME-tight.webm 2>&1 | grep Duration
```

**The CLI vs Python script fork — which to use:**
- `heygen-sarah` (CLI/Video Agent): faster to call, returns captions + GIF automatically,
  but the Video Agent may rewrite your script for "quality." Use for general/exploratory clips.
- `generate_avatar_video.py` (Python/v3 direct): speaks VERBATIM, returns transparent webm,
  full control. Use for all narration clips where exact wording matters.
- NEVER use Video Agent for Rentify narration — it changes the words.

---

### Step 6 — Check timing table for collisions BEFORE compositing

With real durations from Step 5, fill in the timing table and check for overlaps:

```
Segment ends at: START + DURATION
Next segment must start AFTER the previous one ends (+ 0.5s buffer)

Example collision fix (from pilot):
  dates @45s (9.22s) → ends 54.2s
  continue was @52s → COLLISION (starts before dates ends)
  FIXED: continue @55s, questionnaire @58s
```

Fix collisions by adjusting start times BEFORE compositing. Fixing after = rebuilding
the whole chain from the collision point.

---

### Step 7 — Build the intro + demo composite

```bash
# 1. Build demo with corner shrink-move (Sarah animates from center to bottom-right)
ffmpeg -y -i videos/source/demo-final.mp4 \
  -c:v libvpx-vp9 -i videos/temp/corner_tight.webm \
  -filter_complex "\
[1:v]format=yuva420p,\
scale=w='if(lt(t,1.2), 1080-(1080-288)*(t/1.2), 288)':h=-1:eval=frame,\
fade=out:st=3.0:d=0.6:alpha=1[a];\
[0:v][a]overlay=\
x='if(lt(t,1.2), (W-w)/2+((W-w-30)-(W-w)/2)*(t/1.2), W-w-30)':\
y='if(lt(t,1.2), (H-h)/2+((H-h-30)-(H-h)/2)*(t/1.2), H-h-30)':\
eval=frame:enable='lte(t,3.6)'[v];\
[1:a]apad=whole_dur=<DEMO_DUR>[au]" \
  -map "[v]" -map "[au]" \
  -c:v libx264 -c:a aac -pix_fmt yuv420p -r 60 \
  videos/temp/demo_with_corner.mp4

# 2. Concat intro + demo
printf "file '%s'\nfile '%s'\n" \
  "$PWD/videos/temp/intro_solid.mp4" \
  "$PWD/videos/temp/demo_with_corner.mp4" > /tmp/concat.txt
ffmpeg -y -f concat -safe 0 -i /tmp/concat.txt \
  -c:v libx264 -c:a aac -pix_fmt yuv420p -r 60 \
  videos/final/v-1.mp4
```

---

### Step 8 — Stack narration overlays (live overlays, demo always plays)

```bash
overlay() {
  local IN=$1 OUT=$2 SEG=$3 START=$4
  local MS=$(echo "$START*1000" | bc)
  ffmpeg -y -i "$IN" -c:v libvpx-vp9 -i "videos/temp/$SEG.webm" \
    -filter_complex "\
[1:v]scale=288:-1,format=yuva420p,setpts=PTS-STARTPTS+${START}/TB[c];\
[0:v][c]overlay=W-w-30:H-h-30:enable='gte(t,${START})'[v];\
[1:a]adelay=${MS}|${MS}[ad];\
[0:a][ad]amix=inputs=2:duration=first:normalize=0[a]" \
    -map "[v]" -map "[a]" -c:v libx264 -c:a aac -pix_fmt yuv420p -r 60 "$OUT"
}

# Apply segments in time order — ALWAYS increment the output file
overlay videos/final/v-1.mp4 videos/final/v-2.mp4 seg-code-tight 7.7
overlay videos/final/v-2.mp4 videos/final/v-3.mp4 seg-name-tight 18.0
overlay videos/final/v-3.mp4 videos/final/v-4.mp4 seg-dashboard-tight 25.0
# ... continue for all segments
```

**Critical rules:**
- ALWAYS `normalize=0` on amix — stacking amix without it causes volume to ramp
  quiet→loud. We rebuilt the entire chain twice because of this. normalize=0 is
  non-negotiable.
- ALWAYS write to a NEW incremented file. Never overwrite the input. We lost a
  file permanently by doing mv -f over the source. The numbered file chain is
  the ONLY recovery mechanism.
- Output duration must match input duration. If it's shorter, something truncated.
  Stop and investigate before continuing.
- The demo NEVER freezes for narration. If a narration line outlasts its screen,
  she finishes over the next screen. That is correct behavior.
- VERIFY each overlay piece before splicing (Rule 2). A missing/broken intermediate
  piece silently truncates the output.

---

### Step 9 — Handle the end-card (closing narration)

If the final narration line needs to finish after the demo ends, extend the last frame:

```bash
# Grab the last frame
ffmpeg -y -sseof -0.1 -i IN.mp4 -frames:v 1 -update 1 /tmp/endcard.png

# Make a held clip (adjust duration to fit your closing narration)
ffmpeg -y -loop 1 -i /tmp/endcard.png \
  -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=48000 \
  -t 3.5 -c:v libx264 -c:a aac -pix_fmt yuv420p -r 60 -s 1152x1080 /tmp/endcard.mp4

# Concat demo + end-card
printf "file '%s'\nfile '%s'\n" "$PWD/IN.mp4" /tmp/endcard.mp4 > /tmp/ext.txt
ffmpeg -y -f concat -safe 0 -i /tmp/ext.txt \
  -c:v libx264 -c:a aac -pix_fmt yuv420p -r 60 /tmp/extended.mp4

# Then overlay the closing narration on the extended base
overlay /tmp/extended.mp4 videos/final/v-N.mp4 seg-receipt-tight 92.0
```

---

### Step 10 — Blur PII regions (if demo shows sensitive data)

```bash
# Stripe payment card fields example (coordinates from pilot)
ffmpeg -y -i IN.mp4 \
  -filter_complex "\
[0:v]fps=60,format=yuv420p[base];\
[base]crop=420:50:640:446,boxblur=10:3[card];\
[base]crop=160:44:640:496,boxblur=10:3[exp];\
[base]crop=130:44:840:496,boxblur=10:3[cvv];\
[base][card]overlay=640:446:enable='between(t,START,END)'[v1];\
[v1][exp]overlay=640:496:enable='between(t,START,END)'[v2];\
[v2][cvv]overlay=840:496:enable='between(t,START,END)'[v3]" \
  -map "[v3]" -map "0:a" \
  -c:v libx264 -c:a aac -pix_fmt yuv420p -r 60 OUT.mp4
```

**Lessons learned:**
- boxblur radius must be ≤ 11 (the chroma_param limit). Use 10:3 (radius 10, power 3).
- Blur the ENTIRE window when sensitive data is being typed, not just when it's complete.
  The typing-in animation is visible too (we missed the first 3 seconds in the pilot).
- Scan early frames of the Stripe section — card data appears as soon as typing starts.
- The blur is applied to ALL frames in the time window. If the Stripe screen appears
  at multiple points, you need multiple between() conditions.

---

### Step 11 — Polish in HeyGen AI Video Editor

Upload the final MP4 to app.heygen.com → Create → editor:

1. **Import** — editor auto-transcribes Pamela's narration audio
2. **Format** — keep 16:9 landscape, set brand color #E8F4F8
3. **Captions** — auto-generated from narration. Nudge position UP so captions
   don't crowd the bottom-right avatar corner
4. **Audio enhance** — smooth levels / reduce noise (safety net on top of normalize=0)
5. **Export** — watermark-free export needs paid plan/credits
6. **Optional: Upscale** (app.heygen.com/apps/upscale-video) — Precise engine
   (Topaz Starlight 2.5) recovers quality lost in multiple re-encode passes.
   Use LAST, after all editing is done.

---

## 3. CRITICAL TECHNICAL RULES (learned the hard way)

### VP9 Alpha — the #1 gotcha
HeyGen transparent webm clips use VP9 with alpha channel. ffmpeg's NATIVE decoder
drops the alpha (shows a black box instead of transparency). YOU MUST decode every
webm input with `-c:v libvpx-vp9`. Verify with `yuva420p` in the stream info.
When re-encoding crops: `-pix_fmt yuva420p -auto-alt-ref 0`.

### The amix volume trap
Plain `amix=inputs=2` halves the earlier audio on every stacked pass. After 8+
segments, the first narration clip is nearly inaudible. ALWAYS use:
`amix=inputs=2:duration=first:normalize=0`
If you hear a volume ramp (quiet start, loud end), rebuild the ENTIRE chain from
the silent base with normalize=0. There is no surgical fix.

### fps mismatch causes frozen avatar
If the base video is 25fps (e.g. exported from HeyGen editor as HEVC) and you
overlay a 60fps avatar clip, the avatar's video track can freeze while audio plays.
Fix: add `fps=60,format=yuv420p` conversion on the base video input BEFORE
the filter_complex overlay. Always output at -r 60.

### The in-place edit trap (file loss)
NEVER `mv -f /tmp/out.mp4` over the file you just read from. One bad splice
truncated our video to 15s and overwrote the good file permanently. The only
recovery was the previous numbered file. Every irreversible edit writes to a
NEW incremented file. This is Rule 1 and it has already saved us once.

### drawtext is NOT available
This ffmpeg build (Homebrew 8.1) was compiled without libfreetype. The drawtext
filter will fail with "No such filter." Use Pillow (Python) to draw text on frames.

### Timestamp format
When reading timestamps from a video player (e.g. macOS), they are mm:ss NOT
raw seconds. "111" from the player = 1 minute 11 seconds = 71 seconds.
"130" = 1:30 = 90 seconds. Always convert before using in ffmpeg commands.

---

## 4. HEYGEN CLI — NEW CAPABILITIES

### What the CLI gives us that the Python script didn't
- `--wait` flag: blocks until render complete, no manual polling loop
- `--human` flag: formatted table output instead of raw JSON
- Auto-returns: Video URL, Captioned Video URL, Subtitle SRT URL, GIF URL, Thumbnail
- `heygen video download <id>`: direct download without curl
- `heygen auth status`: check authentication state
- `heygen user`: check remaining credits before a batch run
- `heygen voice list`: browse voices (replaces get_all_voices.py)
- `heygen avatar list`: browse avatars (replaces get_all_avatar_images.py)

### CLI command reference (most useful for Rentify)
```bash
# Generate a clip with Sarah
heygen-sarah --prompt "Your narration line."

# Check remaining credits before a batch
heygen user --human

# List voices (filter to find a specific one)
heygen voice list --human | grep -i "derya"

# Download a previously generated video
heygen video download <video_id> --output videos/temp/seg-NAME.mp4

# Check status of a running job
heygen video get <video_id> --human

# List recent videos
heygen video list --human
```

### Known CLI limitations
- No `--output` flag on `video-agent create` — use `heygen video download` separately
- No `defaultAvatarId` / `defaultVoiceId` config keys — use the `heygen-sarah` alias
- Video Agent may rewrite scripts — use `generate_avatar_video.py` for verbatim clips
- `heygen config list` only shows `analytics` and `output` keys (v0.1.5)

---

## 5. THE VERBATIM SCRIPT FORK — WHICH TOOL TO USE

This is the most important workflow decision for the next video:

| Need | Use | Why |
|------|-----|-----|
| Exact wording, transparent webm, corner overlay | `generate_avatar_video.py` | v3 Video Generation, verbatim, webm output |
| Quick exploratory clip, don't care about exact words | `heygen-sarah` CLI | Video Agent, fast, auto-captions |
| Intro clip (full-screen, solid bg) | Either | Both work; CLI is faster |
| Translation to another language | `heygen video-translate` CLI | Built-in translation pipeline |
| Fix a single mis-spoken line | TTS + Lipsync | Cheaper than regenerating full clip |

**For the Rentify narration pipeline:** use `generate_avatar_video.py` for all
corner narration segments. Use `heygen-sarah` CLI for the intro, exploratory
testing, and any clip where exact wording is flexible.

---

## 6. FUTURE AUTOMATION (when HeyGen APIs mature)

### Template/Studio API — the native solution to timing overlaps
Build a multi-scene template ONCE in HeyGen AI Studio. Each scene has:
- A video background with `play_style: "fit_to_scene"` (your screen recording)
- An avatar with a script for that scene

HeyGen auto-matches the scene length to the narration. No manual timestamp math,
no overlap problems, no ffmpeg compositing. This is the goal.

```
POST /v2/template/{template_id}/generate
{
  "variables": {
    "screen_recording": {"type":"media","value":"<asset_id>"},
    "narration_1": {"type":"text","value":"Your script line."}
  }
}
```

Status: v2 only, template creation is manual (web UI). Watch for v3 availability.

### TTS + Lipsync — cheap narration correction
If a narration line needs changing after compositing:
1. `POST /v1/audio/text_to_speech` → generate new audio ($0.000667/sec)
2. `POST /v3/lipsyncs` → re-sync Sarah's lips to the new audio
No full video re-generation needed. Much cheaper than regenerating the clip.

### Translation pipeline (when Rentify goes multilingual)
```bash
heygen video-translate create \
  --source-video <video_id_or_url> \
  --output-languages fr,es \
  --mode precision \
  --speaker-num 1 \
  --wait --human
```
Always: Precision mode, speaker_num 1, add brand glossary for "Rentify."

---

## 7. FILE NAMING CONVENTION (new standard)

Going forward, use descriptive names instead of numbered chains for DELIVERABLES.
Keep numbered chains for WORKING files only.

```
videos/source/          → raw screen recordings (RAW-1, RAW-2 etc)
videos/temp/            → working clips (seg-*, corner_tight, intro_solid etc)
videos/temp/check/      → frame verification thumbnails (clear between sessions)
videos/final/           → numbered working chain (v-1, v-2 ... v-N)
videos/deliverable/     → NEW: final named deliverables
  └── First Time Ordering 1.mp4   (HeyGen editor polished)
  └── First Time Ordering 4.mp4   (PII blurred)
```

The `_archive/History/` folder holds superseded helper docs.

---

## 8. ENVIRONMENT SETUP CHECKLIST (for a new machine or new project)

```bash
# 1. HeyGen CLI
curl -fsSL https://static.heygen.ai/cli/install.sh | bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc

# 2. API key
echo 'export HEYGEN_API_KEY=<your-key>' >> ~/.zshrc
source ~/.zshrc
heygen auth login  # paste key when prompted

# 3. Sarah alias
echo 'alias heygen-sarah="heygen video-agent create --avatar-id 468eabb3326a4d8587ba29d065b1eba7 --voice-id 04d0ae1d0af2489ca7d3bb402a39a890 --mode generate --wait --human"' >> ~/.zshrc
source ~/.zshrc

# 4. HeyGen Skills (for Claude Code)
git clone --single-branch --depth 1 \
  https://github.com/heygen-com/skills.git \
  ~/.claude/skills/heygen-skills

# 5. Verify everything
heygen --version
heygen auth status
heygen user --human
heygen-sarah --prompt "Test clip." --timeout 3m
```

---

## 9. SARAH — LOCKED IDENTITY (never change without a project decision)

| Field | Value |
|-------|-------|
| avatar_id | `468eabb3326a4d8587ba29d065b1eba7` |
| group_id | `0484e7d80416443388aa1763f684f019` |
| voice_id | `04d0ae1d0af2489ca7d3bb402a39a890` (Derya, Starfish) |
| engine | Avatar IV (default) |
| canvas | 1152×1080, 60fps, yuv420p, AAC |
| brand_bg | `#E8F4F8` (intro only; app UI is dark-themed) |
| corner size | 288px wide, bottom-right, 30px margin |
| head-shot crop | `crop=406:360:0:50` |
| webm decode | always `-c:v libvpx-vp9` |
| amix | always `normalize=0` |
