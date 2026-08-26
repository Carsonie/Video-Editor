# Skill: Avatar Launch Spec — "Sarah" (HeyGen)

**Purpose:** The single, reusable definition of how the Rentify help-video presenter
("Sarah") is generated and how she should look and perform. Applies to **all** help
videos — intro clips, corner clips, and any future avatar segments — so every video is
visually and tonally consistent.

**Location:** `HeyGen/.claude/skill/hey_gen/`
**Companion generator:** `generate_avatar_video.py` (same folder)

---

## 1. Identity

| Field | Value | Notes |
|---|---|---|
| On-screen character | **Sarah** | The persona viewers see/hear. Not the underlying asset names. |
| Avatar (visual) | **Pamela** look | group `0484e7d80416443388aa1763f684f019` |
| **avatar_id** (the look) | `468eabb3326a4d8587ba29d065b1eba7` | This exact look = "Sarah". Do not swap looks between videos. |
| Voice | **Derya - Lifelike - Broadcaster** | `04d0ae1d0af2489ca7d3bb402a39a890` (English, female, Starfish) |
| Brand background | **`#E8F4F8`** light blue | Solid, mobile-friendly. Used for full-screen avatar segments. |

> Consistency rule: every video uses the **same avatar_id + same voice_id**. Changing
> either breaks the "same presenter" feel that makes the help library cohesive.

---

## 2. Generation method (LOCKED): Video Generation, NOT Video Agent

Always use **Video Generation** (`POST /v3/videos`, `type: "avatar"`) so the avatar speaks
the **script verbatim**. Never use the **Video Agent** (`/v3/video-agents`) for these — it
writes/improvises its own script, which is not wanted for scripted help content.

- Verbatim script  → Video Generation  ✅ (this spec)
- AI writes script → Video Agent        ❌ (do not use here)

The avatar speaks exactly what is in the `script` field. No AI embellishment.

---

## 3. Proven request shapes

### Full-screen segment (e.g. intro) — solid brand background, mp4
```json
{
  "type": "avatar",
  "avatar_id": "468eabb3326a4d8587ba29d065b1eba7",
  "voice_id": "04d0ae1d0af2489ca7d3bb402a39a890",
  "script": "<verbatim line>",
  "aspect_ratio": "16:9",
  "output_format": "mp4",
  "background": { "type": "color", "value": "#E8F4F8" }
}
```
> `background` REQUIRES both `type` and `value`. Omitting `type` → 400 `background.type required`.

### Corner / overlay segment — transparent webm
```json
{
  "type": "avatar",
  "avatar_id": "468eabb3326a4d8587ba29d065b1eba7",
  "voice_id": "04d0ae1d0af2489ca7d3bb402a39a890",
  "script": "<verbatim line>",
  "aspect_ratio": "16:9",
  "output_format": "webm"
}
```
> `webm` returns transparent (alpha) and REJECTS any `background` field. Requires an avatar
> that supports **matting**. If Pamela does not support matting, fall back to generating on
> green `#008000` and chroma-keying in ffmpeg. (Matting support: TBD — verify on first webm run.)

---

## 4. How to generate (the working command)

```bash
export HEYGEN_API_KEY=$(grep '^HEYGEN_API_KEY=' .env.local | cut -d= -f2)
mkdir -p videos/<slug>/temp

# Full-screen (intro):
python3 .claude/skill/hey_gen/generate_avatar_video.py \
  --avatar 468eabb3326a4d8587ba29d065b1eba7 \
  --voice 04d0ae1d0af2489ca7d3bb402a39a890 \
  --script "Hi, I'm Sarah. Learn how to place your first equipment rental order." \
  --bg "#E8F4F8" \
  --out videos/<slug>/temp/<slug>-intro.mp4

# Corner (transparent overlay):
python3 .claude/skill/hey_gen/generate_avatar_video.py \
  --avatar 468eabb3326a4d8587ba29d065b1eba7 \
  --voice 04d0ae1d0af2489ca7d3bb402a39a890 \
  --script "Let me show you how. Here are the steps to complete your first rental." \
  --webm \
  --out videos/<slug>/temp/<slug>-corner.webm
```
Add `--dry-run` to inspect the request body without spending a credit.
Verified: intro generation completed in ~40s and downloaded successfully.

---

## 5. Look & mannerisms (performance direction)

This is the intended on-screen feel of "Sarah" across all videos. Where HeyGen exposes a
control for it, set it; where it doesn't, keep it in mind when choosing scripts/looks.

**Visual look**
- Same Pamela look every time (avatar_id above) — same outfit/framing = brand recognition.
- Framing: head-and-shoulders, centered for full-screen intro; same crop for corner (scaled down).
- Background: solid `#E8F4F8` for full-screen; transparent for corner overlays.
- Orientation: 16:9 generation, then scaled/cropped in compositing to the demo frame.

**Tone of delivery**
- Warm, calm, professional — a helpful guide, not a hype presenter.
- Clear and unhurried; this is instructional content, so pacing favors comprehension.
- Friendly but neutral; avoid overly excited or salesy energy.

**Mannerisms / motion**
- Natural, restrained gestures — subtle head movement and expression, no big theatrical motion.
- Steady eye-line to camera (talking to the viewer).
- Let the voice carry the message; the avatar supports, never distracts from, the screen content.
- If a motion control is available (`motion_prompt` / expressiveness on some engines), keep it
  **low-to-moderate** — calm and credible over animated.

**Speech / script style** (so delivery matches the look)
- Intro: ~15–20 words, introduces topic + "I'm Sarah".
- Corner: ~12–15 words, a short bridge that hands off to the on-screen steps.
- First person, present tense, plain language, no jargon.
- Standard set lines (reused for brand consistency):
  - Intro: "Hi, I'm Sarah. Learn how to place your first equipment rental order."
    (swap the task per video, keep the "Hi, I'm Sarah" opener)
  - Corner: "Let me show you how. Here are the steps to complete your first rental."

**Do / Don't**
- ✅ Same avatar_id + voice_id every video.
- ✅ Verbatim scripts via Video Generation.
- ✅ Calm, professional, helpful delivery.
- ❌ No Video Agent (it rewrites scripts).
- ❌ No swapping looks/voices between videos.
- ❌ No high-energy/sales tone; no busy gestures.

---

## 6. Engine note

The intro generated successfully without specifying an engine (HeyGen defaulted, Avatar IV
is the documented default). `--engine avatar_v` is available for Avatar V on eligible looks
if higher consistency across angles is wanted later. Legacy v1/v2 endpoints are deprecated
(supported only until 2026-10-31) — always generate via **v3 `/v3/videos`**.

---

## 7. Open item

- [ ] **Matting / transparency for Pamela:** confirm the corner `webm` returns clean
      transparency. If it fails, switch the corner clip to green `#008000` + ffmpeg chromakey,
      and record that decision here.
