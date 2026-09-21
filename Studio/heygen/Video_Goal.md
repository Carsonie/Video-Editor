# Original request for this prompt:

---

We need to work towards the Template API programmatically goal for new amd updated future videos. You and I can progress much quicker by using the ffmpeg method, but the final polishing will always need to be done with the heygen editor.
So the goal is for us (you and I) to break up the raw video in the logical segments, attach the avatar to that segment, add the narrative to that segment and pass/load all of this into the Heygen editor for final review and polish.
Therefore our final video needs to readable by HeyGen into its editor for a quick turnaround for us.
Create a prompt that I can use for our next new video generation, so when I supply you a raw mp4 screen role you can help me to achieve our goal.
Maybe add a file call Video_Goal.md and put this there for me.

---

# Video_Goal.md

# Rentify Help Videos — Goal, Philosophy & Master Prompt

# Date: June 24, 2026

# Use this file to onboard Claude at the start of every new help video session.

---

## THE GOAL

Transform a raw MP4 screen recording of a Rentify user workflow into a
HeyGen AI Studio-ready multi-scene package — where each scene contains a
screen recording segment as the background and Sarah's avatar narration
as the overlay — for final review and polish in the HeyGen editor.

**You + Claude:** break the raw video into logical segments, write the script,
generate Sarah's narration clips, composite with ffmpeg, package for HeyGen.

**HeyGen AI Studio:** final caption styling, audio polish, music, transitions,
export. This is the handoff point. Claude and ffmpeg do the heavy lifting;
HeyGen does the finishing.

---

## PHILOSOPHY

1. **ffmpeg for assembly, HeyGen for polish.** We can move faster in ffmpeg
   than in any GUI. But the final product always goes through the HeyGen
   AI Studio editor for captions, audio enhancement, and export.

2. **Two tracks per scene.** Every scene has:
   - Track 1 (background): a segment of the screen recording
   - Track 2 (avatar): Sarah narrating what's happening in that segment
     The tracks are length-matched — Sarah talks for exactly as long as the
     screen segment runs.

3. **Narration is verbatim.** We control every word Sarah says. Use
   `generate_avatar_video.py` (not the Video Agent) for all narration clips
   so the script is spoken exactly as written.

4. **The demo never freezes.** Sarah narrates OVER the playing demo. If her
   line outlasts the screen it describes, she finishes over the next screen.
   Never pause the demo to fit narration.

5. **One file per step, never overwrite.** Every ffmpeg edit writes to a new
   incremented file. The previous file is always the fallback.

---

## MASTER PROMPT

## (Use this to start every new help video session with Claude)

---

Hi Claude. We are building a new Rentify help video. I am supplying you with
a raw MP4 screen recording of a user workflow. Our goal is to produce a
HeyGen AI Studio-ready package for final polish and export.

Here is our working directory:
`/Users/carsonkramer/Documents/Rentify/Help Videos/HeyGen/`

Here are the reference files you should read before we start:

- `CLAUDE.md` — hard project rules (never overwrite, normalize=0, etc.)
- `INSTRUCTIONAL.md` — the full pipeline reference
- `Instructional_Lessons_Learned.md` — updated pipeline with CLI and lessons
- `Video_Goal.md` — this file, our goal and philosophy
- `.claude/skill/hey_gen/heygen_api.md` — HeyGen API reference
- `.claude/skill/hey_gen/avatar_compositing.md` — ffmpeg compositing recipes

Sarah's locked identity (use on every video, never change):

- avatar_id: 468eabb3326a4d8587ba29d065b1eba7
- voice_id: 04d0ae1d0af2489ca7d3bb402a39a890 (Derya, Starfish)
- canvas: 1152×1080, 60fps, yuv420p, AAC
- brand_bg: #E8F4F8

The raw MP4 is at: [USER SUPPLIES PATH]
The video topic is: [USER SUPPLIES TOPIC e.g. "First Time Ordering"]

Please follow these steps with me:

STEP 1 — INSPECT THE RAW MP4
Read the file. Report back:

- Total duration
- Video codec, resolution, fps
- Audio track present? (yes/no)
- Opening frame description (grab and show me frame at 0.3s)
- Any obvious issues (wrong resolution, very long dead sections at start/end)

STEP 2 — PREP THE RAW MP4
Guide me through:
a) Trimming the head (show me the opening frame, I decide how much to cut)
b) Trimming the tail (show me the last frame, I decide where to end)
c) Removing any dead wait time in the middle (find sections with no UI change)
d) Normalizing to canonical spec: 1152x1080, 60fps, yuv420p, AAC
Save the cleaned demo as: videos/source/demo-[TOPIC]-clean.mp4

STEP 3 — SEGMENT THE DEMO INTO SCENES
Watch the demo with me. Break it into logical scenes where each scene
corresponds to one user action or screen. For each scene report:

- Scene number
- Start time (seconds)
- End time (seconds)
- Duration (seconds)
- What's happening on screen (1 sentence)
- Suggested narration line (what Sarah should say)

Target: 5–12 scenes. Each scene 3–15 seconds. No scene shorter than 3s
(Sarah can't narrate faster than that) and no scene longer than 20s
(viewer attention).

STEP 4 — REVIEW AND APPROVE SCRIPT
Present me the full script table:

| Scene | Start | End  | Dur | Screen                    | Sarah says                   |
| ----- | ----- | ---- | --- | ------------------------- | ---------------------------- |
| 1     | 0.0   | 7.5  | 7.5 | Email verification screen | "When we have your email..." |
| 2     | 7.5   | 12.0 | 4.5 | Code entry                | "Enter the 4-digit code..."  |

...

I will approve, edit, or reject each line. Do not generate any clips until
I have approved the full script. Every word costs a credit if wrong.

STEP 5 — GENERATE SARAH'S NARRATION CLIPS
For each approved scene, generate Sarah's narration clip (verbatim):

```bash
export HEYGEN_API_KEY=$(grep '^HEYGEN_API_KEY=' .env.local | cut -d= -f2)
python3 .claude/skill/hey_gen/generate_avatar_video.py \
  --avatar 468eabb3326a4d8587ba29d065b1eba7 \
  --voice 04d0ae1d0af2489ca7d3bb402a39a890 \
  --script "Approved narration line." \
  --webm --out videos/temp/seg-[SCENE_NAME].webm
```

After each clip: get its exact duration and update the timing table.
Check for timing collisions (clip N must end before clip N+1 starts).
If a clip is longer than its scene, note it — we either extend the scene
or accept that Sarah finishes over the next screen.

Then crop each clip to head-and-shoulders corner framing:

```bash
ffmpeg -y -c:v libvpx-vp9 -i videos/temp/seg-[NAME].webm \
  -vf "crop=406:360:0:50,format=yuva420p" \
  -c:v libvpx-vp9 -pix_fmt yuva420p -auto-alt-ref 0 \
  videos/temp/seg-[NAME]-tight.webm
```

STEP 6 — GENERATE INTRO CLIP
Generate the intro (full-screen Sarah on brand background):

```bash
python3 .claude/skill/hey_gen/generate_avatar_video.py \
  --avatar 468eabb3326a4d8587ba29d065b1eba7 \
  --voice 04d0ae1d0af2489ca7d3bb402a39a890 \
  --script "Hi. I'm Sarah. [Topic-specific intro line.]" \
  --webm --out videos/temp/intro.webm
```

Composite over brand background with 0.5s fade-in:

```bash
ffmpeg -f lavfi -i "color=c=#E8F4F8:s=1152x1080:d=<DUR>:r=60" \
  -c:v libvpx-vp9 -i videos/temp/intro.webm \
  -filter_complex "\
[1:v]scale=1130:2005[p];\
[0:v][p]overlay=(W-w)/2:-180:shortest=1,fade=in:st=0:d=0.5[v];\
[1:a]afade=in:st=0:d=0.5[a]" \
  -map "[v]" -map "[a]" \
  -c:v libx264 -c:a aac -pix_fmt yuv420p -r 60 \
  videos/temp/intro_solid.mp4
```

STEP 7 — ASSEMBLE: INTRO + CORNER SHRINK-MOVE + LIVE OVERLAYS
Build the base video (intro → corner shrink-move → demo):
Then stack all narration overlays at their scene start times.
Always write to new incremented files. Always normalize=0 on amix.
Always verify duration matches before and after each overlay.

Output: videos/final/[TOPIC]-[N].mp4

STEP 8 — BLUR PII (if applicable)
Scan the demo for any sensitive data visible on screen:

- Payment card numbers, CVV, expiry
- Personal email addresses
- Government IDs or sensitive personal info

If found: identify the screen time window and pixel coordinates,
apply boxblur=10:3 to those regions only for that time window.

STEP 9 — PACKAGE FOR HEYGEN AI STUDIO
Produce a HeyGen-ready package. This means:

a) SCENE MANIFEST (scenes.json) — tells HeyGen exactly how to reassemble:

```json
{
  "video_topic": "[TOPIC]",
  "canvas": "1152x1080",
  "fps": 60,
  "scenes": [
    {
      "scene": 1,
      "name": "intro",
      "background": "videos/temp/intro_solid.mp4",
      "avatar_clip": null,
      "duration": 3.72,
      "narration": "Hi. I'm Sarah..."
    },
    {
      "scene": 2,
      "name": "email-verification",
      "background": "videos/source/scene-02-email.mp4",
      "avatar_clip": "videos/temp/seg-email-tight.webm",
      "start_in_demo": 0.0,
      "end_in_demo": 7.5,
      "duration": 7.5,
      "narration": "When we have your email..."
    }
  ]
}
```

b) SCENE SEGMENT FILES — extract each scene segment from the clean demo:

```bash
ffmpeg -y -ss <START> -t <DUR> -i videos/source/demo-[TOPIC]-clean.mp4 \
  -c:v libx264 -c:a aac -pix_fmt yuv420p -r 60 \
  videos/scenes/scene-[NN]-[NAME].mp4
```

c) AVATAR CLIPS — already generated in Step 5 as seg-\*-tight.webm

d) ASSEMBLED PREVIEW — the ffmpeg composite (from Step 7) as a preview:
videos/final/[TOPIC]-preview.mp4

The HeyGen AI Studio import workflow:

1. Upload each scene-[NN]-[NAME].mp4 as a background asset
2. For each scene: set background → your scene clip, avatar → Sarah's clip
3. HeyGen auto-matches lengths with fit_to_scene
4. Polish: captions, audio enhance, music, transitions
5. Export final

STEP 10 — FINAL CHECKS BEFORE HANDOFF
Before handing to HeyGen editor:

- [ ] All narration clips verified (non-zero duration, yuva420p, audio present)
- [ ] No timing collisions (each scene ends before next begins)
- [ ] PII blurred if applicable
- [ ] scenes.json written and accurate
- [ ] All scene segment files extracted and named consistently
- [ ] Preview composite plays cleanly start to finish
- [ ] Volume is even throughout (normalize=0 was used on all overlays)

---

## TECHNICAL RULES (always in effect)

These apply to every video. Claude reads CLAUDE.md at session start.

1. Never overwrite a file. Always increment: v-1 → v-2 → v-3.
2. Verify pieces before splicing. A broken piece silently truncates output.
3. Use -y on scripted ffmpeg, only when writing to NEW filenames.
4. No undo. Numbered fallbacks are the only recovery.
5. Demo never freezes. Narration overlays are always live.
6. Always -c:v libvpx-vp9 on every webm input (VP9 alpha).
7. Always normalize=0 on amix (prevents volume ramp).
8. Always fps=60,format=yuv420p on non-60fps base videos before overlaying.
9. boxblur radius ≤ 11 (chroma_param limit). Use 10:3.
10. Player timestamps are mm:ss. Convert to seconds before using in ffmpeg.

---

## HEYGEN AI STUDIO HANDOFF CHECKLIST

When handing to the HeyGen editor, supply:

- [ ] scenes.json (scene manifest with timing, narration text, file paths)
- [ ] videos/scenes/ folder (one MP4 per scene, named scene-NN-name.mp4)
- [ ] videos/temp/seg-\*-tight.webm (Sarah's narration clips, one per scene)
- [ ] videos/final/[TOPIC]-preview.mp4 (the assembled ffmpeg preview)
- [ ] Note any PII blur regions (time + coordinates) so editor knows not to
      expose those frames during review

In the HeyGen AI Studio:

- Background per scene = scene-NN-name.mp4 (uploaded as asset)
- Avatar per scene = seg-\*-tight.webm (uploaded as asset)
- play_style = fit_to_scene (auto length-match)
- Caption position = above bottom-right corner (don't crowd Sarah)
- Audio enhance = on
- Export = 1152x1080, 60fps (or let HeyGen upscale to 4K)

---

## FOLDER STRUCTURE FOR EACH NEW VIDEO

```
Help Videos/HeyGen/
├── videos/
│   ├── source/
│   │   ├── RAW-[TOPIC]-1.mp4          (original recording)
│   │   └── demo-[TOPIC]-clean.mp4     (prepped, canonical spec)
│   ├── scenes/
│   │   ├── scene-01-intro.mp4
│   │   ├── scene-02-[name].mp4
│   │   └── ...
│   ├── temp/
│   │   ├── intro.webm                 (raw HeyGen intro clip)
│   │   ├── intro_solid.mp4            (intro composited on brand bg)
│   │   ├── corner_tight.webm          (corner intro clip, cropped)
│   │   ├── seg-[name].webm            (raw narration clips)
│   │   ├── seg-[name]-tight.webm      (cropped narration clips)
│   │   └── check/                     (frame verification thumbnails)
│   └── final/
│       ├── [TOPIC]-1.mp4              (numbered working chain)
│       ├── [TOPIC]-2.mp4
│       └── [TOPIC]-preview.mp4        (final ffmpeg assembled preview)
├── scenes.json                         (scene manifest for HeyGen)
├── CLAUDE.md                           (hard rules — auto-loaded)
├── INSTRUCTIONAL.md                    (pipeline reference)
├── Instructional_Lessons_Learned.md    (updated pipeline + lessons)
└── Video_Goal.md                       (this file)
```

---

## WHAT HEYGEN AI STUDIO DOES THAT WE DON'T

These are the reasons we always finish in HeyGen, not ffmpeg:

- Auto-captions synced to speech (we can't do this without libfreetype/drawtext)
- Word-level caption timing and styling
- Background music library (royalty-free, auto-ducked under narration)
- Scene transitions (cross-fades, wipes — ffmpeg can do these but HeyGen is faster)
- Audio enhancement (noise reduction, level smoothing, voice enhancement)
- Upscale to 4K (Topaz Starlight Precise — recovers quality from re-encode passes)
- One-click export in multiple formats/sizes
- Brand kit application (colors, fonts, logos consistently applied)

---

## FUTURE: FULL TEMPLATE API AUTOMATION

When the HeyGen Template/Studio API matures enough to support this workflow
programmatically, the handoff step (Step 9) becomes an API call instead of
a manual import. The scene manifest (scenes.json) is already structured for
this — it maps directly to the template variables format:

```
POST /v2/template/{template_id}/generate
{
  "variables": {
    "scene_1_background": {"type":"media","value":"<asset_id_scene_1>"},
    "scene_1_narration": {"type":"text","value":"When we have your email..."},
    "scene_2_background": {"type":"media","value":"<asset_id_scene_2>"},
    "scene_2_narration": {"type":"text","value":"Enter the 4-digit code..."}
  }
}
```

With fit_to_scene backgrounds, HeyGen auto-matches each scene's length to its
narration clip. No timestamp math, no overlap detection, no ffmpeg compositing.
This is the end goal. The scenes.json file we write today is already the
blueprint for that future API call.

Watch for: Template API v3 support, asset upload improvements, and the ability
to set avatar position/size per scene (currently only controllable in the web UI).
