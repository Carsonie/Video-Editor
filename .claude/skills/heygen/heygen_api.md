# HeyGen API Reference — Complete Guide
# Source: https://developers.heygen.com / https://docs.heygen.com/reference
# Last reviewed: June 23, 2026
# Base URL: https://api.heygen.com
# Auth header: X-Api-Key: <your-key>
# Active platform: v3 (v1/v2 supported through Oct 31 2026; all new features on v3 only)

---

## COMMON CONVENTIONS (read first)

**Authentication:** Every request needs `X-Api-Key: <your-key>` in the header.
Get your key from Settings → API in the HeyGen dashboard. Store in `.env.local`.

**Async pattern:** Video jobs are long-running. POST to create → you get a video_id →
poll GET until status is `completed` or `failed`. Or pass `callback_url` for a webhook.
Status moves: `pending` → `processing` → `completed` or `failed`.
On failure, inspect `failure_code` and `failure_message`.

**Idempotency:** Mutation endpoints accept optional `Idempotency-Key` header. A retry
within 24 hours reusing the same key replays the original response — safe retries, no
duplicate jobs.

**Billing pools (IMPORTANT):**
- MCP usage → deducted from your **web plan premium credits**
- CLI + Direct API usage → deducted from your **API wallet** ($5 minimum top-up)
These are completely independent pools.

**Version note:** v3 is the active platform. All new features are v3 only. v1/v2 continue
to work until October 31, 2026. Exception: Studio/Template API is v2 only, not yet on v3.

---

## 1. VIDEO GENERATION

### 1.1 Create Avatar Video (v3) — OUR PRIMARY ENDPOINT
- **Endpoint:** `POST /v3/videos`
- **Ref:** https://developers.heygen.com/reference/create-video

**Official description (HeyGen):**
"Creates a video from a HeyGen avatar or an arbitrary image. Supports scripts or
pre-recorded audio for lip-sync. Supports Avatar IV and Avatar V engines; set the
'engine' field to select. Output container: 'webm' returns a video with a transparent
background (alpha channel); 'mp4' (default) returns a standard video. 'webm' requires
an avatar that supports matting. When 'webm' is selected, any 'background' value is
rejected and background removal is applied automatically. Text script for the avatar
to speak. Pair with voice_id, or omit voice_id when using avatar_id to use the
avatar's default voice."

**How we use it / what to expect:**
This is the endpoint that powers every narration clip in the Rentify pipeline. We call
it via generate_avatar_video.py with Sarah's locked avatar_id and voice_id.

Key parameters we use:
- type: "avatar" — always for Sarah
- avatar_id: "468eabb3326a4d8587ba29d065b1eba7" — Sarah/Pamela locked identity
- voice_id: "04d0ae1d0af2489ca7d3bb402a39a890" — Derya/Starfish voice
- script: "..." — VERBATIM text; HeyGen speaks exactly what you write
- output_format: "webm" — gives transparent background (alpha channel)
- Omit background entirely when using webm (it is rejected automatically)

What you get back: a video_id. Poll GET /v3/videos/{video_id} until status is
"completed", then download the video_url. Typical render time: 30s–2min.

CRITICAL for Rentify: We use Video Generation (NOT Video Agent) because Video Agent
rewrites your script. This endpoint speaks it verbatim. Never switch to Video Agent
for narration clips.

### v2 CAN composite an avatar over video; v3 cannot (probed 2026-08-22, free)

Probed the live validator with deliberately bad VALUES, so a real field answers
with its own error and an unknown field falls through. A control field with a
made-up name fell through — so these are genuine, not ignored:

| `POST /v2/video/generate` — `video_inputs[]` | |
|---|---|
| `character.avatar.avatar_style` | `'circle'`, `'closeUp'`, `'full'`, `'normal'`, `'voiceOnly'` |
| `character.avatar.scale` | number |
| `character.avatar.offset` | `{x, y}` numbers |
| `character.avatar.matting` | boolean |
| `background.type` | includes `"video"` (needs `url`/`video_asset_id` + `play_style`, `fit`) |

That is Sarah-in-a-circle over our own segment, placed and scaled — the thing we
had written down as impossible.

**v3 has none of it.** Same day, same method:
`background.type` -> `Input should be 'color' or 'image'`;
`avatar_style` -> `Extra inputs are not permitted`.
And per the official OpenAPI spec, v3 `studio` mode is whole-frame scenes
concatenated — "the server owns layout and center-crops each scene", backgrounds
"Color-only in v1", "MP4 only in v1 — the output container is fixed and
``output_format`` is not exposed". So no transparent multi-scene either.

**v2's sunset is 2026-10-31**, stated in the API's own response warning. There is
no v3 successor for any of the above. Treat v2 compositing as a capability that
exists and is going away, not as somewhere to build.

### SSML `<break>` — measured, not assumed (2026-08-22, one paid test)

Sarah's voice (`04d0ae1d0af2489ca7d3bb402a39a890`, "Derya - Lifelike -
Broadcaster") reports **`support_pause: True`** from `GET /v3/voices`, and a real
render confirms the tag is honoured in the `script` field of `POST /v3/videos`:

    First sentence here. <break time="2.5s"/> Second sentence here.

  - **Gap measured:** 3.49s of silence (the 2.5s break plus her natural lead-out
    and lead-in). Cost $0.35 for a 7.12s clip — $0.049/s.
  - **Alpha survives it:** `yuva420p` when decoded with `-c:v libvpx-vp9`. The
    default decode reports `yuv420p` on the same file, which is the whole trap.
  - **She does not freeze in the gap.** Frame-to-frame motion averaged 0.083 vs
    0.191 while speaking — breathing and small shifts, not a still. She starts
    moving again ~1s BEFORE her voice returns.
  - **A natural mid-sentence breath also reads as silence** — 0.67s in this
    clip. Anything splitting on silence needs a minimum-duration threshold;
    1.5s separated the real break from the breath cleanly here.

Why this matters: it makes a ONE-PASS render of a whole script viable — Sarah
flows through the video instead of cold-starting each sentence — with the breaks
as findable split points. Note the per-second cost above is BETTER than the
per-scene renders ($0.21-0.34 each for 3-6s clips = $0.07-0.12/s), which points
at a per-render floor. One data point, not a cost model.

The webm/alpha workflow:
1. Generate with --webm flag → get a .webm file with alpha channel
2. Always decode with -c:v libvpx-vp9 in ffmpeg (native decoder drops alpha = black box)
3. Crop to head-and-shoulders: crop=406:360:0:50
4. Re-encode crops: -pix_fmt yuva420p -auto-alt-ref 0 to keep alpha

---

### 1.2 Create Avatar Video (v2) — Legacy
- **Endpoint:** `POST /v2/video/generate`
- **Ref:** https://docs.heygen.com/reference/create-an-avatar-video-v2

**Official description (HeyGen):**
"Generate an avatar video using scripts or pre-recorded audio. Supports customizable
backgrounds, captions, dimensions, and voice settings. Supported until October 31, 2026."

**How we use it / what to expect:**
Functionally similar to v3 but different request shape. The background param in v2
needs BOTH type AND value: {"type":"color","value":"#E8F4F8"} — omitting either
causes a silent failure. Do not use for new work; migrate to v3 (1.1).

---

### 1.3 Create Avatar IV Video
- **Endpoint:** `POST /v2/video/av4/generate`
- **Ref:** https://docs.heygen.com/reference/create-avatar-iv-video

**Official description (HeyGen):**
"Enables programmatic generation of AI-powered avatar videos using advanced
photorealistic Avatar IV technology, including support for Talking Photos with
improved motion quality and more expressive facial animation."

**How we use it / what to expect:**
Avatar IV is HeyGen's previous-generation engine (superseded by Avatar V). Our Sarah
clips use this via the default path in v3. Not recommended to call directly — use
1.1 with the engine field instead.

---

### 1.4 Get Video Status (v1 legacy)
- **Endpoint:** `GET /v1/video_status.get?video_id={video_id}`
- **Ref:** https://docs.heygen.com/reference/video-status

**Official description (HeyGen):**
"Retrieves the current rendering status of a video job. Returns status, video_url when
complete, and failure details when failed."

**How we use it / what to expect:**
Our generate_avatar_video.py script polls this. Prefer the v3 equivalent
(GET /v3/videos/{video_id}) for new integrations. Status: pending, processing,
completed, failed.

---

### 1.5 Get Video (v3)
- **Endpoint:** `GET /v3/videos/{video_id}`
- **Ref:** https://developers.heygen.com/reference/get-video

**Official description (HeyGen):**
"Retrieve the full record for a video — status, video_url, thumbnail_url, duration,
failure_code, and failure_message."

**How we use it / what to expect:**
Primary polling endpoint for v3. Call every 10 seconds after creating a video. When
status === "completed", video_url contains a direct download link. When
status === "failed", read failure_code and failure_message. Response also includes
duration (seconds) and thumbnail_url.

---

### 1.6 List Videos
- **Endpoint:** `GET /v3/videos?limit=20&offset=0`
- **Ref:** https://developers.heygen.com/reference/list-videos

**Official description (HeyGen):**
"Retrieve all videos in your account with pagination."

**How we use it / what to expect:**
Auditing, finding a video_id you didn't save, or building a dashboard. Not part of
the primary pipeline but helpful for housekeeping.

---

### 1.7 Delete Video
- **Endpoint:** `DELETE /v3/videos/{video_id}`
- **Ref:** https://developers.heygen.com/reference/delete-video

**Official description (HeyGen):**
"Permanently remove a video from your HeyGen account. This action cannot be undone."

**How we use it / what to expect:**
Always download the webm/mp4 locally before deleting. Once deleted, the video_url
is gone from HeyGen's servers. Use for cleaning up test renders.

---

## 2. VIDEO AGENT

### 2.1 Create Video Agent Session (v3)
- **Endpoint:** `POST /v3/video-agents`
- **Ref:** https://developers.heygen.com/reference/create-video-agent-session

**Official description (HeyGen):**
"Send a text prompt describing the video you want. The agent handles scripting, avatar
selection, scene composition, and rendering. Runs in two modes: 'generate' (one-shot,
fire-and-forget) and 'chat' (multi-turn, pauses for decisions). Accepts up to 20 file
attachments. Takes optional avatar_id, voice_id, style_id, and brand_kit_id.
Auto-detects orientation from content."

**How we use it / what to expect:**
DO NOT USE FOR RENTIFY NARRATION CLIPS. The Video Agent rewrites your script.
We use Video Generation (1.1) which speaks verbatim. The Agent is useful for
exploratory one-off videos where you want AI to write the script from a concept.
Good for: "make a 30-second product overview." Bad for: "say exactly this line."
Pricing: 2 credits/min (recently reduced from 6).

---

### 2.2 Get Video Agent Session (v3)
- **Endpoint:** `GET /v3/video-agents/{session_id}`
- **Ref:** https://developers.heygen.com/reference/get-video-agent-session

**Official description (HeyGen):**
"Poll the session for a video_id, then use the video_id to poll for video_url."

**How we use it / what to expect:**
Two-step polling: first poll session for video_id, then poll video for video_url.
Only needed if you use the Video Agent (2.1). For our pipeline, use
GET /v3/videos/{video_id} directly.

---

### 2.3 Video Agent Generate (v1 — Legacy)
- **Endpoint:** `POST /v1/video_agent/generate`
- **Ref:** https://docs.heygen.com/reference/video-agent

**Official description (HeyGen):**
"A powerful one-shot tool that creates high-quality avatar videos from simple natural
language prompts. The Video Agent handles scripting, avatar selection, scene composition,
and rendering automatically."

**How we use it / what to expect:**
Older v1 version, superseded by v3 (POST /v3/video-agents). Deprecated. Same caution
— it rewrites scripts, never use for verbatim narration.

---

## 3. TEMPLATE API

> **Rewritten 2026-08-22** from HeyGen's own OpenAPI spec
> (`https://developers.heygen.com/openapi/external-api.json`) and live calls.
> The previous version of this section had the paths wrong — it listed
> `GET /v3/template/{id}` (singular) and `POST /v2/template/{id}/generate`.
> Neither exists. It is `templates`, plural, and generate is a **v3 POST to the
> same path as the GET**.

**Why this section matters more than it looks.** Everywhere else in the API,
avatar-over-video compositing is impossible (see 1.1). A TEMPLATE is the
exception, and the reason is that its *layout* is built by hand in the web
editor — where **Layout: Circle + Avatar Background: Remove** does exist. The
API cannot create that arrangement, but it can FILL one that already exists.
This is the only v3 path to Sarah-in-the-corner-over-our-footage.

### 3.1 List Templates
- **Endpoint:** `GET /v3/templates`  ·  params: `limit`, `token` (pagination)

"Returns a paginated list of API-ready templates in the workspace. Templates are
created and edited in the HeyGen web editor; only templates with variables
defined are listed."

Returns `TemplateListItemV3`: `id`, `name`, `thumbnail_url`, `aspect_ratio`,
`created_at`, `updated_at`.

### 3.2 Get Template
- **Endpoint:** `GET /v3/templates/{template_id}`

"Returns template details including its variable schema (with current default
values) and scenes. Variable defaults are returned in the same shape the generate
request accepts, so a response can be edited and posted back. **Only draft
version 4 templates (the current editor format) are supported.**"

Returns `TemplateDetailV3`: the list fields plus `variables` (an object keyed by
variable name), `scene_ids` (in template order) and `scenes`
(`TemplateSceneV3` = `scene_id`, `script` with placeholders unreplaced, and the
`variables` that scene uses).

### 3.3 Generate Video from Template
- **Endpoint:** `POST /v3/templates/{template_id}`

"Generates a video from the template by replacing its variables (text, image,
video, audio, character, voice). Use `scene_ids` to select, reorder, or repeat
scenes — **scenes must already exist in the template; the API cannot create new
ones.** Returns the created video object; poll `GET /v3/videos/{video_id}` or use
webhooks. Idempotent replays return the original creation-time snapshot."

`GenerateFromTemplateV3Request`:

| field | notes |
|---|---|
| `variables` * | replacements keyed by the template's own variable names |
| `scene_ids` | subset, reordered, repeats allowed — never MORE than the template has |
| `dimension` | `{width, height}`, even, 128–4096, **must keep the template's aspect ratio** |
| `fps` | **25, 30 or 60** — 25 is ours |
| `title`, `folder_id`, `caption`, `subtitles`, `callback_url`, `callback_id` | |
| `brand_glossary_id` | pronunciation of custom terms (`brand_voice_id` is the legacy alias) |
| `reorder_music`, `keep_text_vertically_centered`, `include_gif`, `enable_sharing` | |

### 3.4 The six variable types

Each is a discriminated union on `type`.

| type | fields |
|---|---|
| `text` | `content` |
| `video` | `asset`, `fit`, `play_style`, `volume` |
| `image` | `asset`, `fit` |
| `audio` | `asset` |
| `character` | `character_id`, `character_type` (`avatar` \| `talking_photo`) |
| `voice` | `voice_id`, `locale` |

`asset` is a union discriminated on its own `type`: **`url`**, **`asset_id`** or
**`base64`**.

`fit`: `cover` \| `contain` \| `crop` \| `none`  (default `contain`)

`play_style`: `fit_to_scene` \| `freeze` \| `loop` \| `once` \| `full_video`
(default `loop`) — "Playback behavior when the video is shorter than the scene."

⚠ **Never use `fit_to_scene` for a demo recording.** It warps the clip's playback
SPEED to match the scene, which breaks this project's rule that the demo always
plays at natural speed. `once` and `freeze` are the safe ones — `freeze` is the
native equivalent of the held end-card we build by hand. `full_video` is the one
to test if the goal is the SCENE bending to the footage rather than the reverse.

### 3.5 State of this workspace (checked 2026-08-22)

Five templates exist, all left over from the abandoned 2026-08-06 pivot:

```
d757699e0a1341adb1bdf92384175244  First Time Rental V1-3          9:16
73692a9356074ff7bd9fbe62e725c879  First Time Rental Template -2   9:16
b583cbea622c47ac8abb1f03e5995e42  First Time Rental Template      9:16
c4ac9134f96e4ad498743a4982f2a172  First Time Rental V1-1          9:16
de7351893d0e459180b46a94e05b00df  First Time Rental V1            9:16
```

`V1-3` has **12 scenes with the Paddle Sports scripts already written in**, and
**zero variables**. That second fact is the blocker: with no variables there is
nothing for `POST /v3/templates/{id}` to replace, so the template can only ever
render exactly what is baked into it. Variables are defined in the web editor,
not over the API.

Two other things to know before reusing them:

- **They are 9:16.** Our videos are 1152x1152 (1:1). `dimension` must keep the
  template's aspect ratio, so this cannot be overridden per call — it is a
  rebuild in the editor.
- One scene's script contains the stray text `Playback → Freeze)` — an editor
  note typed into the script box. It would be SPOKEN.

Worth noting the scripts already use `<break time='5s'/>`, which matches the
SSML finding in 1.1 — the tag works, and it was in use here first.

## 4. AVATARS

### 4.1 List Avatars (v2)
- **Endpoint:** `GET /v2/avatars`
- **Ref:** https://docs.heygen.com/reference/list-avatars-v2

**Official description (HeyGen):**
"Returns all available avatars including public studio avatars, private digital twins,
and talking photos. Each record includes the avatar_id, group_id, preview image URL,
and supported engines."

**How we use it / what to expect:**
Our get_all_avatar_images.py skill uses this. Run list to see all avatars, find "Pamela"
to locate Sarah. The id field in each record is the avatar_id you pass to video creation.
Public avatars shown to all users; private Digital Twins filtered by ownership.

---

### 4.2 List Avatar Groups
- **Endpoint:** `GET /v2/avatar_group.list`
- **Ref:** https://docs.heygen.com/reference/list-avatar-groups

**Official description (HeyGen):**
"Returns all avatar groups. Each group contains multiple looks (poses, outfits) for
the same avatar. The group_id is used to browse all looks for a specific avatar."

**How we use it / what to expect:**
Sarah's group_id: 0484e7d80416443388aa1763f684f019. Groups organize an avatar's
different looks. To see all of Pamela's looks/outfits, use the group_id with 4.3.

---

### 4.3 List Avatars in Group
- **Endpoint:** `GET /v2/avatar_group/{group_id}/avatars`
- **Ref:** https://docs.heygen.com/reference/list-avatars-in-group

**Official description (HeyGen):**
"Returns all avatar looks within a specific group. The look ID (id field) is what
you pass as avatar_id when creating a video."

**How we use it / what to expect:**
Use with Sarah's group_id to see all available Pamela looks. The avatar_id we locked
(468eabb3326a4d8587ba29d065b1eba7) is one look from this group — the one that
supports matting (transparent webm output).

---

### 4.4 Get Avatar Look
- **Endpoint:** `GET /v3/avatars/looks/{look_id}`
- **Ref:** https://developers.heygen.com/reference/get-avatar-look

**Official description (HeyGen):**
"Returns details for a specific avatar look including the supported_api_engines array.
Check this before requesting Avatar V — if 'avatar_v' is not listed, the request
will be rejected."

**How we use it / what to expect:**
Verify whether Sarah's look supports Avatar V before attempting to upgrade engine
quality. Currently we use Avatar IV (default). To test Avatar V (more expressive
facial animation), check this endpoint first to avoid a rejected request.

---

## 5. TALKING PHOTO (Photo Avatar)

### 5.1 Upload Talking Photo
- **Endpoint:** `POST /v1/talking_photo`
- **Ref:** https://docs.heygen.com/reference/upload-talking-photo

**Official description (HeyGen):**
"Upload a still image to create a Talking Photo avatar. HeyGen animates the face,
syncs lip movements to your script, and produces a realistic talking-head video from
one photo. Returns a talking_photo_id."

**How we use it / what to expect:**
Alternative to Digital Twin — use a single photo instead of a video-trained model.
Good for a quick presenter from a headshot without recording video. Not currently used
in Rentify (we use Sarah/Pamela), but useful if you want a different presenter for a
specific video without a full Digital Twin setup.

---

### 5.2 List Talking Photos
- **Endpoint:** `GET /v1/talking_photo.list`
- **Ref:** https://docs.heygen.com/reference/list-talking-photos

**Official description (HeyGen):**
"Returns all Talking Photo avatars in your account with their IDs and preview URLs."

**How we use it / what to expect:**
Discovery endpoint for your photo avatars. Not used in current pipeline.

---

### 5.3 Delete Talking Photo
- **Endpoint:** `DELETE /v1/talking_photo/{talking_photo_id}`
- **Ref:** https://docs.heygen.com/reference/delete-talking-photo

**Official description (HeyGen):**
"Permanently deletes a Talking Photo avatar from your account."

**How we use it / what to expect:**
Housekeeping only. Irreversible. Confirm the photo avatar is no longer needed
before calling this.

---

## 6. VOICES

### 6.1 List Voices (v2)
- **Endpoint:** `GET /v2/voices`
- **Ref:** https://docs.heygen.com/reference/list-voices-v2

**Official description (HeyGen):**
"Returns all available voices including HeyGen built-in library, ElevenLabs voices,
and custom cloned voices. Each record includes voice_id, name, language, gender,
and a preview_audio_url."

**How we use it / what to expect:**
Our get_all_voices.py skill wraps this. Run list to browse, find "Derya" to confirm
Sarah's voice. Sarah's locked voice_id: 04d0ae1d0af2489ca7d3bb402a39a890 (Derya,
Starfish engine). Play the preview_audio_url to audition a voice before committing —
saves credits.

---

### 6.2 List Voices — Starfish/Audio (v1)
- **Endpoint:** `GET /v1/audio/voices`
- **Ref:** https://docs.heygen.com/reference/list-voices-audio

**Official description (HeyGen):**
"Returns voices compatible with HeyGen's Starfish TTS engine. Use to find voice_ids
for the Text to Speech endpoint (7.1)."

**How we use it / what to expect:**
Specifically for the audio/TTS pipeline. Use when calling the TTS endpoint directly
(7.1) to get audio-only output without generating a full video.

---

## 7. TEXT TO SPEECH (Starfish TTS)

### 7.1 Generate Speech
- **Endpoint:** `POST /v1/audio/text_to_speech`
- **Ref:** https://docs.heygen.com/reference/text-to-speech

**Official description (HeyGen):**
"Generate natural-sounding speech audio from text using HeyGen's Starfish TTS engine.
Previously available only in AI Studio on the web, now accessible directly via API.
Returns an audio_url (MP3), duration, and request_id."

**How we use it / what to expect:**
Audio-only output — no video, no avatar. Payload: {"text":"...","voice_id":"..."}.
Response: {"audio_url":"...","duration":2.1,"request_id":"..."}.

Cost: $0.000667/sec — far cheaper than full avatar video generation. Useful for
generating narration audio to mix with video yourself via ffmpeg, when you don't need
the visual corner-avatar presenter. For Rentify help videos that show Sarah in the
corner, keep using full video generation (1.1). If a future video format is audio-only
narration (no face), this is the efficient path.

Powerful combo: generate audio here → Lipsync (9.1) → apply to existing avatar clip.
This lets you correct a mis-spoken line without regenerating the full video.

---

## 8. VIDEO TRANSLATION

### 8.1 Translate Video
- **Endpoint:** `POST /v3/video-translations`
- **Ref:** https://docs.heygen.com/reference/video-translate

**Official description (HeyGen):**
"You supply a source video and target languages; the engine handles transcription,
translation, voice cloning, lip-sync, and optional burned-in captions. This is not
new-video generation. The performance, framing, and brand assets in the original are
preserved — translation rides on top of what's already there. Supports 175+ languages.
Two modes: Fast (3 credits/min, default) and Precision/Quality (6 credits/min,
context-aware natural lip-sync). Supports: translate_audio_only, speaker_num for
speaker separation, start_time/end_time for partial translation, background music
removal, brand_glossary_id for custom terms."

**How we use it / what to expect:**
Most powerful future feature for Rentify's international expansion. Once help videos
are finalized in English, run them through this endpoint to localize into French,
Spanish, etc. — same Pamela face, same screen recording, different language audio +
lip-sync. The original video is preserved; translation rides on top.

Key decisions:
- Mode: Always Precision for help videos (clear speech, one speaker, face visible).
  Precision = better lip-sync, worth the 2x cost for professional output.
- speaker_num: Always set to 1 — wrong speaker count is the #1 quality killer,
  causing voices to bleed across speakers.
- brand_glossary_id: Add brand terms like "Rentify" so they don't get translated
  literally. "Rentify" should stay "Rentify" in every language.

Returns one video_translation_id per language. Batch multiple languages in one call.

---

### 8.2 Get Translation Status
- **Endpoint:** `GET /v3/video-translations/{video_translate_id}`
- **Ref:** https://docs.heygen.com/reference/get-video-translation

**Official description (HeyGen):**
"Returns the current status of a video translation job, the output video_url when
complete, and caption_url for generated caption files."

**How we use it / what to expect:**
Poll after starting a translation (8.1). Translation jobs take several minutes.
Response includes caption_url for an SRT/VTT file usable as a sidecar subtitle file.

---

### 8.3 List Supported Languages
- **Endpoint:** `GET /v2/video_translate/target_languages`
- **Ref:** https://docs.heygen.com/reference/list-target-languages

**Official description (HeyGen):**
"Returns all supported target languages for video translation, with language codes,
names, and supported modes (fast, precision)."

**How we use it / what to expect:**
Run before starting a translation to confirm your target language is supported and
which modes are available. 175+ languages supported; not all support Precision mode.

---

## 9. LIPSYNC

### 9.1 Create Lipsync Job
- **Endpoint:** `POST /v3/lipsyncs`
- **Ref:** https://developers.heygen.com/lipsync-precision

**Official description (HeyGen):**
"Dub or replace audio on a video using a provided audio file. HeyGen re-syncs the
speaker's lip movements to match the new audio. Two modes: Precision ($0.0667/sec,
highest quality lip-sync) and Speed ($0.0333/sec, faster turnaround). Returns a
lipsync_id to poll for status."

**How we use it / what to expect:**
Distinct from Translation — Lipsync takes an existing video + a NEW audio file and
re-syncs the lips to match the new audio. Use when: you recorded better narration,
you want a different voice, or you need to swap one line without re-generating the
full video. For Rentify: if Sarah's voice needs to change but the visual is fine,
use Lipsync to swap the audio and re-sync lips.

Powerful combo: TTS (7.1) to generate new audio → Lipsync (9.1) to apply it to
the existing avatar clip. This lets you correct a mis-spoken narration line cheaply
without regenerating the full video clip.

---

### 9.2 Get Lipsync Job Status
- **Endpoint:** `GET /v3/lipsyncs/{lipsync_id}`
- **Ref:** https://docs.heygen.com/reference/get-lipsync

**Official description (HeyGen):**
"Returns the status of a lipsync job, output video_url when complete, and caption_url."

**How we use it / what to expect:**
Standard async polling. Lipsync jobs are typically faster than full video generation.
Response includes caption_url if captions were generated.

---

## 10. PROOFREAD API (Enterprise only)

### 10.1 Proofread Translation
- **Endpoint:** `POST /v3/video-translations/proofreads`
- **Ref:** https://docs.heygen.com/reference/proofread

**Official description (HeyGen):**
"For high-stakes translated content: after translation, retrieve an editable SRT
subtitle file, make corrections (brand terms, register, names), upload the edited SRT,
then trigger a final render with the corrected subtitles. This workflow gives you
editorial control before committing to the final lip-synced render. Recommended for
long videos (>3 min), corporate/branded content, and languages the viewer reads natively."

**How we use it / what to expect:**
Enterprise-only. Workflow: translate → fetch SRT → edit (fix brand names like
"Rentify," fix tone/register) → upload corrected SRT → generate final → deliver.
Worth requesting enterprise access if Rentify expands to multilingual help content
where accuracy of terminology matters.

---

## 11. ASSETS

### 11.1 Upload Asset
- **Endpoint:** `POST /v3/assets`
- **Ref:** https://docs.heygen.com/reference/upload-asset

**Official description (HeyGen):**
"Upload a file (image, video, audio, PDF) to HeyGen's asset storage. Returns an
asset_id you can reference in video creation, templates, and lipsync requests instead
of passing public URLs. Supported MIME types include image/jpeg, image/png, video/mp4,
video/webm, audio/mp3, audio/wav, application/pdf."

**How we use it / what to expect:**
Essential for the Template API future pipeline. Instead of requiring your screen
recording to be at a public URL, upload it here to get an asset_id, then reference
that in the template variable. This keeps content private and avoids URL expiry issues.
For the current ffmpeg pipeline, assets aren't needed (we work locally). Once we move
to API-based assembly, assets become the bridge for your screen recordings.

---

### 11.2 List Assets
- **Endpoint:** `GET /v1/asset/list`
- **Ref:** https://docs.heygen.com/reference/list-assets

**Official description (HeyGen):**
"Returns a paginated list of assets with filters for file_type and folder_id."

**How we use it / what to expect:**
Housekeeping — find asset_ids for assets you want to reuse. Filter by file_type
(e.g. video/mp4) to find screen recording assets quickly.

---

### 11.3 Delete Asset
- **Endpoint:** `DELETE /v1/asset/{asset_id}/delete`
- **Ref:** https://docs.heygen.com/reference/delete-asset

**Official description (HeyGen):**
"Permanently deletes an uploaded asset from HeyGen's storage."

**How we use it / what to expect:**
Cleanup. Irreversible. Confirm the asset isn't referenced by any active template or
pending video job before deleting.

---

## 12. STREAMING / INTERACTIVE AVATAR

### 12.1 New Streaming Session
- **Endpoint:** `POST /v1/streaming.new`
- **Ref:** https://docs.heygen.com/reference/new-session

**Official description (HeyGen):**
"Create a new real-time interactive avatar streaming session. The avatar responds in
real-time to text or audio input, enabling live conversational experiences. Returns
a session_id and WebRTC connection credentials. Guide: https://docs.heygen.com/docs/streaming-api"

**How we use it / what to expect:**
Completely different paradigm — creates a LIVE, real-time avatar stream (think a
chatbot with a face). Not relevant to current Rentify help-video pipeline (we make
pre-rendered videos). Future use case: a live interactive help assistant on the Rentify
website where customers can ask Sarah questions in real time. Requires WebRTC
integration on the frontend.

---

### 12.2 Start Streaming Session
- **Endpoint:** `POST /v1/streaming.start`
- **Ref:** https://docs.heygen.com/reference/start-session

**Official description (HeyGen):**
"Activate a created streaming session and begin the avatar stream."

**How we use it / what to expect:**
Called after 12.1 to actually start the avatar stream. Session lifecycle:
new → start → task (send text/audio) → stop. Part of the streaming integration flow.

---

### 12.3 Submit Streaming Task
- **Endpoint:** `POST /v1/streaming.task`
- **Ref:** https://docs.heygen.com/reference/submit-task

**Official description (HeyGen):**
"Send a text or audio task to an active streaming session. The avatar speaks the
provided text in real time with synced lip movement. Low latency — designed for
conversational use."

**How we use it / what to expect:**
How you make the live avatar say something. The real-time equivalent of our script
param in video generation. For a live help assistant, each user question triggers a
new task to make Sarah respond.

---

### 12.4 Stop Streaming Session
- **Endpoint:** `POST /v1/streaming.stop`
- **Ref:** https://docs.heygen.com/reference/stop-session

**Official description (HeyGen):**
"End an active streaming session and release resources."

**How we use it / what to expect:**
Always call this when done. Sessions left open consume resources and may incur charges.
Implement cleanup logic (try/finally) in any streaming integration.

---

### 12.5 List Streaming Sessions
- **Endpoint:** `GET /v1/streaming.list`
- **Ref:** https://docs.heygen.com/reference/list-sessions

**Official description (HeyGen):**
"Returns all active and recent streaming sessions in your account."

**How we use it / what to expect:**
Debugging — see if you have orphaned sessions open consuming resources. Check this
list and stop any sessions you didn't intentionally leave open.

---

### 12.6 Interrupt Streaming Task
- **Endpoint:** `POST /v1/streaming.interrupt`
- **Ref:** https://docs.heygen.com/reference/interrupt-task

**Official description (HeyGen):**
"Interrupt the avatar's current speech mid-sentence, allowing a new task to begin
immediately."

**How we use it / what to expect:**
Makes live avatar conversations feel responsive. If the user asks something while
Sarah is still talking, interrupt and respond to the new input immediately. Essential
for a good UX in any live-streaming integration.

---

## 13. WEBHOOKS

### 13.1 Add Webhook Endpoint
- **Endpoint:** `POST /v3/webhooks/endpoints`
- **Ref:** https://docs.heygen.com/reference/add-a-webhook-endpoint

**Official description (HeyGen):**
"Webhook events are how HeyGen notifies your endpoints when a variety of interactions
or events happen, including when avatar video processing succeeds or fails. Webhook
events are sent by HeyGen as POST requests to your webhook endpoint. Register a URL
to receive POST notifications when video events occur, including avatar_video.success
and avatar_video.fail. HeyGen sends the event payload with the video_id, status,
video_url (on success), and your callback_id."

**How we use it / what to expect:**
Instead of polling every 10 seconds for video status, register a webhook and HeyGen
pushes to it when your video is done. Much more efficient at scale. For Rentify: when
we automate generation for many clips at once, webhooks eliminate the polling loop.
Set a callback_id when creating the video (any string) — it's echoed back in the
webhook so you can match which video finished. Requires a publicly accessible HTTPS
endpoint on your server.

---

### 13.2 List Webhook Endpoints
- **Endpoint:** `GET /v3/webhooks/endpoints`
- **Ref:** https://docs.heygen.com/reference/list-webhook-endpoints

**Official description (HeyGen):**
"Retrieves a list of all webhook endpoints that are registered under your account."

**How we use it / what to expect:**
Auditing — see what's registered, verify event types subscribed. Useful if unsure
whether a webhook is still active.

---

### 13.3 Delete Webhook Endpoint
- **Endpoint:** `DELETE /v3/webhooks/endpoints/{endpoint_id}`
- **Ref:** https://docs.heygen.com/reference/delete-webhook-endpoint

**Official description (HeyGen):**
"Permanently removes a registered webhook endpoint."

**How we use it / what to expect:**
Cleanup — remove webhooks pointing at decommissioned servers or test endpoints.
Important note: PATCH on webhooks performs a FULL REPLACEMENT of the event types
array (not a merge) — include all desired events in a single PATCH call.

---

## 14. USER / ACCOUNT

### 14.1 Get Remaining Quota
- **Endpoint:** `GET /v1/user/remaining_quota`
- **Ref:** https://docs.heygen.com/reference/get-remaining-quota

**Official description (HeyGen):**
"Returns your current remaining API credit balance."

**How we use it / what to expect:**
Check before starting a batch generation to ensure sufficient credits. Returns the
API wallet balance — NOT your web plan premium credits (those are separate and
tracked differently). Add a pre-flight check in automation scripts: if balance is
below a threshold, alert before the batch starts.

---

### 14.2 Get User Info
- **Endpoint:** `GET /v3/users/me`
- **Ref:** https://docs.heygen.com/reference/get-user-info

**Official description (HeyGen):**
"Returns information about the authenticated API user, including account ID, email,
plan type, and account limits."

**How we use it / what to expect:**
Verify API key validity and confirm which plan/features are accessible. If you get
unexpected 403 errors on certain endpoints (like Proofread or Digital Twin Creation),
check this to confirm your plan type includes those features.

---

## 15. INTEGRATION PATHS (non-REST)

### 15.1 MCP (Model Context Protocol)
- **URL:** https://developers.heygen.com/mcp/overview
- **Auth:** OAuth (no API key needed — users authorize via consent screen)
- **Billing:** Deducts from web plan premium credits (separate from API wallet)

**Official description (HeyGen):**
"Connect HeyGen to any AI agent with a single endpoint. No API keys or setup needed.
Just OAuth and your agent starts creating videos instantly. HeyGen offers three
integration paths: MCP for connecting to AI assistants like Claude without managing
APIs, Skills for extending AI coding agents like Claude Code and Cursor, and Direct
API for full programmatic control. Supported MCP tools include: create video from
avatar, create video from image, list/get/delete videos, lipsync, video translation,
design_voice (find voices from natural-language description), and asset management."

**How we use it / what to expect:**
MCP is how Claude (this assistant) can directly call HeyGen on your behalf in a chat
interface without you running terminal commands. The tradeoff: MCP uses your web plan
credits; terminal scripts use your API wallet. For the Rentify pipeline we mostly use
terminal scripts. MCP is convenient for one-off tasks and exploration inside Claude
conversations — e.g. asking Claude to generate a test clip without leaving the chat.

---

### 15.2 CLI
- **Install:** `curl -fsSL https://static.heygen.ai/cli/install.sh | bash`
- **Ref:** https://developers.heygen.com/cli
- **Auth:** API key stored at ~/.heygen/credentials or HEYGEN_API_KEY env var
- **Billing:** API wallet (same pool as Direct API)

**Official description (HeyGen):**
"Build and ship videos without leaving your terminal. The HeyGen CLI gives developers
and AI agents command-line access to HeyGen's video platform. It wraps the v3 API,
outputs structured JSON by default, and works out of the box in scripts, CI pipelines,
and agent workflows. Covers all v3 endpoints including Video Agent, Lipsync, Video
Translation (with Proofreads), Webhooks, and Assets. Supports --wait flag for
blocking until async operations complete, --request-schema to inspect API schemas
without auth, and --force for non-interactive destructive operations in CI."

**How we use it / what to expect:**
Alternative to our Python scripts — wraps the same v3 API, produces JSON pipeable
to jq. Good for quick one-off operations or CI integration. Key commands:
  heygen video create -d '{"type":"avatar",...}' --wait     (create and wait)
  heygen video get <video_id>                                (check status)
  heygen video download <video_id>                           (download MP4)
  heygen voice speech create --text "..." --voice-id <id>   (TTS audio only)
  heygen video-translate create --output-languages es --mode precision --wait
  heygen webhook endpoints create --url <url> --events "avatar_video.success"

Currently our pipeline uses generate_avatar_video.py for more control. The CLI
supplements for exploration and debugging.

---

## QUICK REFERENCE — RENTIFY PIPELINE ENDPOINTS

| Step | Endpoint | Notes |
|------|----------|-------|
| Generate narration clip | POST /v3/videos | output_format: webm, Sarah's IDs |
| Poll for clip ready | GET /v3/videos/{video_id} | Poll every 10s |
| List available avatars | GET /v2/avatars | get_all_avatar_images.py |
| Browse avatar looks | GET /v2/avatar_group/{id}/avatars | Find Sarah's looks |
| List voices | GET /v2/voices | get_all_voices.py |
| Future: upload screen rec | POST /v3/assets | For template-based pipeline |
| Future: generate from template | POST /v2/template/{id}/generate | v2 only |
| Future: translate to French | POST /v3/video-translations | Precision, speaker_num:1 |
| Future: swap narration audio | POST /v3/lipsyncs | Replace voice, re-sync lips |
| Future: live help assistant | POST /v1/streaming.new | Real-time avatar |
| Check credits | GET /v1/user/remaining_quota | API wallet balance |

## SARAH — LOCKED IDENTITY (use on every Rentify video)
- avatar_id:  468eabb3326a4d8587ba29d065b1eba7
- group_id:   0484e7d80416443388aa1763f684f019
- voice_id:   04d0ae1d0af2489ca7d3bb402a39a890 (Derya, Starfish engine)
- engine:     Avatar IV (default) — upgrade to Avatar V: {"engine":{"type":"avatar_v"}}
- output:     always output_format: "webm" for transparent corner clips
- brand_bg:   #E8F4F8 (intro only; app UI is dark-themed)
