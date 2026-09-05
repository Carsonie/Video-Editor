# INSTRUCTIONAL.md — Master Guide: Creating Rentify Help Videos with HeyGen

A complete, repeatable, step-by-step process for turning a raw screen-recording `.mp4` of
user interactions into a finished, narrated help video with a consistent avatar presenter.

This guide is the single source of truth for the workflow. The hard project rules also live
in `CLAUDE.md` (auto-loaded every session) and are summarized in Section 0 below.

> Environment note: Claude's sandbox CANNOT reach the Mac filesystem. All ffmpeg / python /
> curl commands are run by the user in their own terminal. Claude can VIEW files the user
> saves under `/Users/carsonkramer/Documents` via the filesystem connector (scale images to
> < 1MB / ~300–400px wide first). There is NO undo — see Rule 1.

---

## 0. PROJECT RULES (summary — full text in CLAUDE.md)

1. **Never edit a deliverable in place.** Every irreversible ffmpeg edit writes to a NEW
   incremented file (`-N` → `-N+1`). Never `mv -f` over a source. Never read & write the same
   filename in one ffmpeg command. The previous numbered file is the ONLY recovery path.
2. **Verify intermediate pieces before splicing** (non-zero duration, expected streams).
3. **Use `-y`** on scripted ffmpeg, but only when writing to NEW filenames.
4. **No undo.** The sandbox can't reach the Mac; numbered fallbacks are the only safety net.
5. **Narration overlays are LIVE.** The demo always plays at full speed; the avatar overlays
   as a live corner picture-in-picture. NEVER freeze the demo to fit narration (the one
   sanctioned exception: extending the final end-card so a closing line can finish — see 1.4).

Find the latest good file any time: `ls -lat videos/final/*.mp4 | head`

---

## 1. PREP THE RAW MP4 (screen recording)

Goal: a clean demo track at the canonical spec, landing on the right opening screen, with no
dead air, ready for avatar overlays.

**Canonical output spec (everything is normalized to this):**
`1152×1080, 60fps, yuv420p, AAC`. Brand background `#E8F4F8` (used for the intro only; the
app UI is dark-themed and accepted as-is).

### 1.1 Inspect first
Always look before cutting. Get duration and streams:
```bash
ffmpeg -i videos/source/RAW.mp4 2>&1 | grep -e Duration -e Stream
```
Grab frames to see what's on screen at key times (then VIEW them via the connector after
scaling small):
```bash
ffmpeg -y -ss 0.3 -i videos/source/RAW.mp4 -frames:v 1 -update 1 /tmp/f.png
ffmpeg -y -i /tmp/f.png -vf scale=300:-1 -update 1 videos/temp/check/f_sm.png
```
Tip: the player shows mm:ss. Remember "111" from a player = 1:11 = 71 seconds, NOT 111s.

### 1.2 Trim the head (remove intro dead time / land on the right first screen)
Cut N seconds off the front, write to a NEW numbered source:
```bash
ffmpeg -y -ss <N> -i videos/source/RAW.mp4 -c copy videos/source/RAW-2.mp4
```
Verify the new opening frame is the screen you want (re-grab frame at 0.3s). If the app is
dark-themed there may be no "white" landing screen — that's fine, dark UI is accepted.

### 1.3 Trim the tail
Keep up to time T:
```bash
ffmpeg -y -i videos/source/RAW-2.mp4 -t <T> -c copy videos/source/RAW-3.mp4
```

### 1.4 Remove an excess hold / dead wait in the MIDDLE
To delete the span A→B (e.g. a 5s wait), split and rejoin (re-encode so cuts land on frame
boundaries — stream-copy only cuts on keyframes and will glitch):
```bash
ffmpeg -y -i IN.mp4 -t <A> -c:v libx264 -c:a aac -pix_fmt yuv420p -r 60 /tmp/p1.mp4
ffmpeg -y -ss <B> -i IN.mp4 -c:v libx264 -c:a aac -pix_fmt yuv420p -r 60 /tmp/p2.mp4
printf "file '%s'\nfile '%s'\n" /tmp/p1.mp4 /tmp/p2.mp4 > /tmp/cut.txt
ffmpeg -y -f concat -safe 0 -i /tmp/cut.txt -c:v libx264 -c:a aac -pix_fmt yuv420p -r 60 OUT.mp4
```

### 1.5 ADD a hold at a specific point (only when truly needed)
Per Rule 5 we don't freeze the demo mid-play. The sanctioned use is **extending the final
end-card** so a closing narration line can finish. Pattern (freeze the last frame ~3.5s):
```bash
ffmpeg -y -sseof -0.1 -i IN.mp4 -frames:v 1 -update 1 /tmp/endcard.png
ffmpeg -y -loop 1 -i /tmp/endcard.png -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=48000 \
  -t 3.5 -c:v libx264 -c:a aac -pix_fmt yuv420p -r 60 -s 1152x1080 /tmp/endcard.mp4
printf "file '%s'\nfile '%s'\n" "$PWD/IN.mp4" /tmp/endcard.mp4 > /tmp/ext.txt
ffmpeg -y -f concat -safe 0 -i /tmp/ext.txt -c:v libx264 -c:a aac -pix_fmt yuv420p -r 60 OUT.mp4
```
> Caution: freezing mid-demo ALSO freezes any avatar talking at that moment, which pauses her
> voice mid-sentence and does NOT fix overlaps. Fix overlaps by respacing (Section 4), not
> freezing.

### 1.6 Normalize to canonical spec (if the raw isn't already)
```bash
ffmpeg -y -i IN.mp4 -c:v libx264 -c:a aac -pix_fmt yuv420p -r 60 -s 1152x1080 videos/source/demo-clean.mp4
```

---

## 2. SCRIPT DEVELOPMENT

Goal: one short narration line per screen/step, written the way you want it spoken, with a
KNOWN duration so you can place it without collisions.

### 2.1 Writing the lines
- One idea per screen. Keep lines tight; long lines overrun the next screen.
- The avatar speaks the script VERBATIM (we use Video Generation, not Video Agent which
  rewrites). So fix grammar/typos BEFORE generating ("sent"→"send", "latest name"→"last name").
- Lead a clip with "Hi." as its own sentence for a calmer opening frame when needed.

### 2.2 Getting a line's exact duration
There is no reliable way to know duration without generating. So generate the clip, then read
its duration — that number drives placement and overlap checks:
```bash
ffmpeg -c:v libvpx-vp9 -i videos/temp/seg-NAME.webm 2>&1 | grep Duration
```
Rough estimate for planning only (before generating): ~2.5 words/second.

### 2.3 Build a timing table
For each segment record: name, start time (seconds), duration, end time (= start+dur). Ensure
each segment's start ≥ previous segment's end (+~0.5s buffer). This prevents two avatars
talking at once. Convert any mm:ss timestamps to seconds first.

---

## 3. AVATAR & VOICE

### 3.1 Locked identity — "Sarah" (use on EVERY video for brand consistency)
- **Avatar (Pamela look):** `468eabb3326a4d8587ba29d065b1eba7`
  (group `0484e7d80416443388aa1763f684f019`, public). Supports matting (transparency).
- **Voice (Derya — Lifelike Broadcaster, Starfish):** `04d0ae1d0af2489ca7d3bb402a39a890`.
- Discover others with the skills: `get_all_avatar_images.py`, `get_all_voices.py`.

### 3.2 Generate a narration clip (transparent webm)
```bash
export HEYGEN_API_KEY=$(grep '^HEYGEN_API_KEY=' .env.local | cut -d= -f2)
python3 .claude/skill/hey_gen/generate_avatar_video.py \
  --avatar 468eabb3326a4d8587ba29d065b1eba7 \
  --voice 04d0ae1d0af2489ca7d3bb402a39a890 \
  --script "Your verbatim line here." \
  --webm --out videos/temp/seg-NAME.webm
```
Method is LOCKED to Video Generation (`POST /v3/videos`, type avatar). For transparent output
use `--webm` and OMIT background. For a solid bg the param needs BOTH type and value:
`{"type":"color","value":"#E8F4F8"}`.

### 3.3 VP9 ALPHA — the #1 gotcha
HeyGen transparent clips are VP9 webm with alpha. ffmpeg's native decoder DROPS the alpha
(black box). You MUST decode every webm input with `-c:v libvpx-vp9`. Confirm the stream reads
`yuva420p`. When re-encoding a crop, keep alpha with `-pix_fmt yuva420p -auto-alt-ref 0`.

### 3.4 Crop to head-and-shoulders (matches all segments)
HeyGen frames the avatar as a wide seated shot (406×720). Crop to a tight head-and-shoulders:
```bash
ffmpeg -y -c:v libvpx-vp9 -i videos/temp/seg-NAME.webm \
  -vf "crop=406:360:0:50,format=yuva420p" \
  -c:v libvpx-vp9 -pix_fmt yuva420p -auto-alt-ref 0 \
  videos/temp/seg-NAME-tight.webm
```
Verify framing + alpha by compositing over white and viewing:
```bash
ffmpeg -y -f lavfi -i color=white:s=406x360:d=1 -c:v libvpx-vp9 -i videos/temp/seg-NAME-tight.webm \
  -filter_complex "[0][1]overlay=shortest=1" -frames:v 1 -update 1 videos/temp/check/seg_sm.png
```

### 3.5 Corner placement (the in-demo look)
Scale to **288px wide**, bottom-right, **30px margin**. This is baked into the overlay command
in Section 4.

### 3.6 Intro + shrink-and-move transition (optional opener)
- Intro: Pamela full-screen on `#E8F4F8`, soft line. Framing `scale=1130:2005,
  overlay=(W-w)/2:-180`. Add `fade=in:st=0:d=0.5` (video) + `afade=in:st=0:d=0.5` (audio) to
  soften an open-mouth/loud start.
- Shrink-move: animate her from center → bottom-right over ~1.2s using a time-varying scale.
  The reliable trick is `scale=w='if(lt(t,1.2), 1080-(1080-288)*(t/1.2), 288)':h=-1:eval=frame`
  plus a matching `overlay` x/y interpolation with `eval=frame`. Match the intro crop to the
  corner crop first, or the move will visibly jump.
- `drawtext` is NOT available in this ffmpeg build (no libfreetype). Use Pillow for text-on-frame.

---

## 4. ASSEMBLE THE WORKING VIDEO (live corner overlays)

### 4.1 The core repeatable command — overlay one clip LIVE on the playing demo
ALWAYS `normalize=0` (see 4.3).
```bash
overlay() {            # overlay IN OUT SEG START
  local IN=$1 OUT=$2 SEG=$3 START=$4
  local MS=$(echo "$START*1000" | bc)
  ffmpeg -y -i "$IN" -c:v libvpx-vp9 -i "videos/temp/$SEG.webm" \
    -filter_complex "[1:v]scale=288:-1,format=yuva420p,setpts=PTS-STARTPTS+${START}/TB[c];[0:v][c]overlay=W-w-30:H-h-30:enable='gte(t,${START})'[v];[1:a]adelay=${MS}|${MS}[ad];[0:a][ad]amix=inputs=2:duration=first:normalize=0[a]" \
    -map "[v]" -map "[a]" -c:v libx264 -c:a aac -pix_fmt yuv420p -r 60 "$OUT"
}
# example:
# overlay videos/final/demo-clean.mp4 videos/final/v-1.mp4 seg-code-tight 7.7
```
The overlay adds NO length — the output duration must equal the input. That's your
no-truncation check.

### 4.2 Chain segments (each builds on the previous numbered file)
Apply segments in time order, incrementing the output each time:
```bash
overlay demo-clean.mp4 v-1.mp4  seg-A-tight  7.7
overlay v-1.mp4        v-2.mp4  seg-B-tight  18.0
overlay v-2.mp4        v-3.mp4  seg-C-tight  25.0
# ... etc, one per segment
```
Keep every intermediate `-N` as a fallback (Rule 1).

### 4.3 The amix volume trap (CRITICAL)
Plain `amix=inputs=2` HALVES earlier audio on every pass. Chaining many segments makes volume
ramp quiet→loud. ALWAYS use `amix=inputs=2:duration=first:normalize=0`. If you ever hear a
volume ramp, rebuild the whole chain from the silent base with `normalize=0`.

### 4.4 Respacing overlaps (the real fix, not freezing)
If two avatars talk at once, push the later one's start to ≥ the earlier one's end (+buffer),
then rebuild from a clean point before the overlap. Example fix we used:
dates@45 (9.22s→54.2), continue@52→**55**, questionnaire@55→**58**.

### 4.5 End-of-video closing lines
Closing lines (checkout/payment/receipt) often need the last screen held briefly so the line
can finish — use the end-card extension (1.5), then overlay the closing line so it finishes
over the held card.

### 4.6 Verify-before-splice (Rule 2)
Before any concat, print each piece's duration; a broken/zero piece silently truncates output.
Also beware ffmpeg's interactive "overwrite? [y/N]" prompt stalling pasted blocks — always `-y`,
always write NEW filenames.

---

## 5. FINISH / POLISH IN THE HEYGEN AI VIDEO EDITOR (manual, for now)

Our ffmpeg chain produces the correctly-composited cut. Do final polish in HeyGen's browser
editor (https://app.heygen.com → Create → editor). Claude cannot operate this UI; it's a
manual session, but Claude can troubleshoot what you see.

1. **Import** the final `.mp4`. The editor builds a transcript from Pamela's narration.
2. **Format & presets:** keep 16:9 landscape; set brand color `#E8F4F8` if offered.
3. **Edit / polish:**
   - **Captions** auto-generated from narration (big win for a help video). Nudge caption
     position UP/safe-area so it doesn't crowd the bottom-right avatar.
   - **Audio enhance:** reduce noise / smooth levels / emphasize speech (safety net on top of
     `normalize=0`).
   - Optional: titles/callouts on key screens, a transition or two.
   - DO NOT let "auto-tighten pacing" delete Pamela's deliberate pauses — review auto-cuts.
4. **Export** 16:9. (Watermark-free export likely needs a paid plan / credits.)
5. **Optional final pass — Upscale Video app** (app.heygen.com/apps/upscale-video): Precise
   engine (Topaz Starlight 2.5) reconstructs detail and **readable on-screen text**, and
   recovers quality lost to our many re-encodes. Do this LAST, after the editor. Credits apply.

---

## 6. FUTURE: AUTOMATE WITH HEYGEN APIs (build out over time)

Goal: replace the manual ffmpeg compositing + manual editor polish with HeyGen's native,
scriptable pipeline as features mature.

- **Template / Studio API (V3, "New AI Studio")** — the architecturally correct fit:
  - Build a multi-scene template ONCE in the HeyGen web UI (avatar-in-corner + screen-recording
    background per scene). Template creation is UI-only today.
  - A **video background** with `play_style: fit_to_scene` auto-matches the background length
    to each scene — HeyGen's NATIVE solution to our overlap/timing problem (no manual timestamp
    math). Other play styles: `freeze`, `loop`, `full_video`.
  - HeyGen enforces scene/script length alignment ("End of scene does not align with script"
    error if violated) — i.e. the avatar can't overrun its scene. This is the auto-sync we want.
  - Generate via `POST /v2/template/{template_id}/generate` with a `variables` map (text,
    image, video, audio, voice, character). Can restrict to `scene_ids`, override dimension/fps,
    burn subtitles. Retrieve mapping with `GET /v3/template/{template_id}` (returns `scenes`).
- **Generate Studio Video** endpoint — AI Studio backend with avatars/voices/dynamic
  backgrounds (Avatar III/IV).
- **Captions API / Auto Subtitle** — programmatic captions from the narration audio.
- **Upscale** — currently an app; watch for an API to add a final 4K pass programmatically.
- **Billing note:** API usage draws from the separate API wallet (top up from ~$5), independent
  of web-plan premium credits. MCP usage draws from web-plan credits.
- **Migration target:** when the Studio/Template API exposes enough timeline control, move the
  whole compositing step off ffmpeg onto templates for native sync + transitions + captions,
  keeping only light pre/post in ffmpeg if needed.

---

## 7. QUICK REFERENCE

| Thing | Value |
|---|---|
| Avatar (Sarah/Pamela) | `468eabb3326a4d8587ba29d065b1eba7` (group `0484e7d80416443388aa1763f684f019`) |
| Voice (Derya, Starfish) | `04d0ae1d0af2489ca7d3bb402a39a890` |
| Canvas | 1152×1080, 60fps, yuv420p, AAC |
| Brand bg | `#E8F4F8` (intro only; app UI is dark) |
| Corner avatar | 288px wide, bottom-right, 30px margin |
| Head-shot crop | `crop=406:360:0:50` |
| VP9 alpha decode | `-c:v libvpx-vp9` on every webm input |
| VP9 alpha re-encode | `-pix_fmt yuva420p -auto-alt-ref 0` |
| amix (no volume ramp) | `amix=inputs=2:duration=first:normalize=0` |
| API key | `.env.local` → `HEYGEN_API_KEY` |

### Key paths
- Project root: `/Users/carsonkramer/Documents/Rentify/Help Videos/HeyGen/`
- Skills: `.claude/skill/hey_gen/` (avatar/voice discovery, launch spec, compositing, generator)
- Sources: `videos/source/` · Working clips: `videos/temp/` · Outputs: `videos/final/`
- Frame checks: `videos/temp/check/`
