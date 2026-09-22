---
name: heygen
description: The HeyGen API as this project actually uses it — the voice ("Sarah" is the AVATAR; the voice is Derya, 04d0ae1d0af2489ca7d3bb402a39a890), standalone Starfish TTS for voice-only narration, how a <break> tag must be written, why a fixed pause drifts against the picture and the two-pass fix, what a call costs in credits, and WHICH KNOB EXISTS ON WHICH ENDPOINT — the TTS call has speed only, the VIDEO call adds pitch/volume via voice_settings, Starfish voices have no engine settings at all, and NOTHING anywhere sets a voice mood (heygen.com's Original/Excited/Broadcaster/Angry page is about the AVATAR's performance, not the voice). Also Design Voices, auditioning, the avatar-video endpoints, avatar compositing, and the voice/avatar listings. Use whenever HeyGen is mentioned, when swapping the Mac voice for a real one, when picking or auditioning a voice, when a narration lands early or late against its screens, or before spending a single credit.
user_invocable: true
---

# HeyGen — the voice, the pauses, and what a call costs

⚠ **THIS SKILL DID NOT REGISTER FOR SEVEN WEEKS.** It sat at
`Studio/heygen/.claude/skill/hey_gen/` — folder named `skill`, singular, four
levels down inside `Studio/`, and **with no `SKILL.md` in it at all**. Three
reasons, each enough on its own. Moved here 2026-09-21 at Carson's word. Its
41 KB of API notes were invisible the whole time, and a whole session's worth
of findings had to be rediscovered by calling the API.

A skill registers **only** at `.claude/skills/<name>/SKILL.md`, relative to the
project root. Not `skill/`. Not nested deeper. Not without this file.

---

## ⛔ MONEY: ONE LINE, THEN WAIT

Every render costs real credits from a real wallet. Carson's standing rule:
**one exact line showing the cost, then wait for Y or N. Never buried in a
paragraph.**

```bash
# the wallet and the credits — both free to read
curl -s -H "X-Api-Key: $HEYGEN_API_KEY" https://api.heygen.com/v3/users/me
curl -s -H "X-Api-Key: $HEYGEN_API_KEY" https://api.heygen.com/v2/user/remaining_quota
```

⚠ **A REFUSED CALL IS FREE.** Measured 2026-09-21: a bad `<break>` tag, a
`speed` of 99, an empty Design-Voices body — all returned 400 and the quota did
not move. So **probe with a deliberately invalid field** to learn what an
endpoint accepts without paying for it.

⚠ **MEASURED COST, standalone TTS, 2026-09-21:**

| words | credits |
|---|---|
| 19 (one short line) | **1** |
| 76 (one long scene, 8 pauses) | **5** |

So roughly **1 credit per 15–19 words**. A 602-word video is ~35–40 credits one
pass, ~70–80 with the two-pass timing below.

⚠ **THE TWO NUMBERS ARE NOT LINKED ANYWHERE.** `/v3/users/me` reports dollars
(`wallet.remaining_balance`), `/v2/user/remaining_quota` reports credits. Making
a call moved the credits and left the dollars unchanged. **Do not quote a
dollar figure for a render** — the rate is only on dashboard.heygen.com, behind
a login. Quote credits, and say the wallet balance separately.

⚠ **PLAN CREDITS CANNOT PAY FOR THIS.** An **API key** bills the wallet; **OAuth
(MCP)** bills subscription credits. HeyGen's own words: an API key *"bills to
API plans"*, OAuth is *"sized for trial rather than scale"*. So `plan_credit` in
the quota response is not a pot we can reach — and Carson has permanently
declined the HeyGen MCP connector anyway, so do not raise it.

---

## THE VOICE — "Sarah" IS THE AVATAR, NOT THE VOICE

```
Sarah    468eabb3326a4d8587ba29d065b1eba7   the AVATAR, the face on screen
Derya    04d0ae1d0af2489ca7d3bb402a39a890   the VOICE she speaks with
```

HeyGen's own listing calls it **"Derya - Lifelike - Broadcaster 🎙️"**, female,
English, Starfish, `support_pause: true`. The script it reads opens *"Hi, I'm
Sarah"*, which is where the mix-up came from.

⚠ **THIS REPO'S OWN DOCS DISAGREE WITH EACH OTHER.** `Studio/heygen/CLAUDE.md`
says *"Voice: Sarah"*; `Video_Goal.md` says *"Derya"*. Same id. `heygen_api.md`
§6.1 calls it **Sarah's locked voice_id**, which is the settled reading: the
character is Sarah, the voice is Derya, and it does not change without Carson.

⚠ **NOTHING RECORDS WHICH VOICE A FINISHED RENDER USED.** `.render_jobs.json`
holds only `{n, id, out}`, and `GET /v1/video_status.get` returns no voice
field. To find out what an existing video sounds like, **extract its audio and
listen** — e.g. `sandbox/<scene>/narration.webm`.

---

## VOICE-ONLY NARRATION — Starfish TTS

Carson, 2026-09-21: *"We do not need to see Sarah in the video, just have her
narrate it."* That is **not** an avatar render. It is a plain TTS call:
synchronous, no polling, no queue, and far cheaper.

```bash
curl -X POST "https://api.heygen.com/v3/voices/speech" \
  -H "X-Api-Key: $HEYGEN_API_KEY" -H "Content-Type: application/json" \
  -d '{"text":"Hello. <break time=\"1.5s\"/> And welcome.",
       "voice_id":"04d0ae1d0af2489ca7d3bb402a39a890",
       "speed":1.0,"input_type":"text"}'
```

Back comes `audio_url` (an mp3, 44.1 kHz mono), `duration`, and
**`word_timestamps`** — start and end for every word. Those timings are exact,
and far better than the VTT's 3.44-words-a-second estimate.

**The complete field list is five:** `text` (1–5,000 chars), `voice_id`,
`speed` (0.5–2.0), `language`, `locale`, `input_type`. That is all.

### ⚠ `<break>` TAKES SECONDS. MILLISECONDS ARE REFUSED.

```
<break time="2s"/>      ✅        <break time="0.5s"/>   ✅
<break time="2000ms"/>  ❌ 400 — "Millisecond break values are not supported"
```

`<break>` is **the only markup allowed**. HeyGen: *"wrapping the script in other
tags such as `<speak>` can add spoken artifacts."* So do NOT switch
`input_type` to `ssml`, and do not add `<prosody>`.

⚠ **AND CONVERT CARSON'S `{n}` MARKERS.** He writes `{2}` and `{.5}` in
`script.json`. Sending those raw makes the voice say them. `pause_marks.py`
owns the format; the conversion is `{2}` → `<break time="2s"/>`.

### ⚠ THE VOICE ADDS ITS OWN PAUSES ON TOP OF YOURS

Measured on a scene with 8 beats: six came back within 0.10s of what was asked,
but a `{.5}` after a full stop came back at **1.00s** — double — and the voice
also inserted an **0.85s gap at a comma nobody asked for**. A 2s beat swallows
the extra; a 0.5s one does not. An ordinary word gap is 0.07s, so anything over
about 0.3s is a real pause.

---

## ⚠⚠ A FIXED PAUSE DRIFTS. THE FIX IS TWO PASSES.

This is the most expensive thing in this skill to rediscover.

The Mac voice (Samantha, 155 wpm) and Derya at speed 1.0 say the same words in
different times. The `{n}` beats are **fixed**, the speech between them is not,
so every beat lands earlier than the last. Carson: *"The voice is way ahead of
the segment."*

Measured on one 36.64s scene: beat 1 was 1.30s early, and by beat 8 it was
**6.35s early**. The totals hid it completely — both voices finished within 0.6s
of each other, so a simple "does it fit" check said fine.

**THE FIX — the break is the only lever:**

```
break_k  =  (when screen k changes)  −  (when the previous sentence ends)
```

1. **Pass 1** — render the scene with the asked-for beats. Read
   `word_timestamps` to learn how long this voice takes over each chunk of words.
2. Take the **targets** from the Mac cut: the END of each silence in
   `voice/<NN>-<label>.m4a` is when that sentence should start. The frames were
   tuned to that cut, so it is the truth.
3. Compute each break, then **subtract the voice's own added pause** for that
   beat (pass 1's `got − asked`).
4. **Pass 2** — render again with the computed breaks.

Result on the same scene: worst sentence-start error **0.95s, down from 6.35s**,
and the last beat landed at **+0.10s**. Breaks sent were 1.62 / 2.16 / 2.43 /
1.95 / 2.02 / 0.62 / 2.43 / **0.30** — never more than 0.43s from what Carson
wrote, but each one placed.

⚠ **IT IS TWO CALLS PER SCENE**, so budget double. Pass 1's segment durations can
be cached per scene, since the words rarely change.

---

## MOOD AND TUNING — WHICH KNOB EXISTS ON WHICH ENDPOINT

⚠ **THE ANSWER IS DIFFERENT FOR THE TWO ENDPOINTS, AND THAT IS THE WHOLE
TRAP.** An earlier version of this section said flatly that no pitch knob
exists anywhere. That is wrong, and Carson caught it by sending HeyGen's own
marketing page. Read the table before repeating either claim.

| knob | `POST /v3/voices/speech` (TTS) | `POST /v3/videos` (avatar video) |
|---|---|---|
| `speed` | ✅ 0.5 – 2.0 | ✅ 0.5 – 1.5 (note: different ceiling) |
| `pitch` | ❌ not a field | ✅ **−50 to +50 semitones** |
| `volume` | ❌ | ✅ 0 – 1 |
| `locale` | ✅ | ✅ |
| emotion / mood / style | ❌ | ❌ |
| `expressiveness` | ❌ | ⚠ yes, but it moves the AVATAR, not the voice |

### The TTS endpoint has five fields and no tuning object

`text`, `voice_id`, `speed`, `language`, `locale`, `input_type`. That is all.

⚠ **UNKNOWN FIELDS ARE SILENTLY IGNORED, NOT REFUSED.** Probes of `emotion`,
`style`, `mood`, `pitch`, `emotion_scale` and `voice_settings` all came back as
if fine — the API only ever complained about the one value made invalid on
purpose. **Silently ignored is worse than refused**: it looks like it worked
and changes nothing, so a "fix" can ship without anyone noticing it did nothing.

### The VIDEO endpoint has `voice_settings`, and Starfish cannot use the good part

```json
"voice_settings": { "speed": 1.0, "pitch": 0, "volume": 1.0, "locale": "en-US",
                    "engine_settings": { "engine_type": "starfish" } }
```

`pitch` is real there — a couple of semitones up genuinely lifts a voice. But
`engine_settings` is per engine, and HeyGen's own schema says:

> **Starfish has no user-tunable settings today.**

ElevenLabs and Fish voices get their own tuning blocks; Starfish gets none.
Derya is Starfish.

⚠ **AND THE VIDEO ENDPOINT IS THE EXPENSIVE ONE.** Going through it just to
reach `pitch` and then discarding the picture means paying avatar-render prices
for audio, and it is ASYNCHRONOUS — a `video_id` to poll, not an instant
`audio_url`. Only worth it if picking a different voice has already failed.

### "Expressive AI avatars" — Original / Excited / Broadcaster / Angry

That is heygen.com's own marketing page, and it is about the **avatar's
performance**, not the voice. Its own subtitle says so: *"Your AI avatar
doesn't just mirror gestures and speech."* In the API it is:

```
expressiveness:  high | medium | low     ← "PHOTO AVATARS ONLY", defaults low
motion_prompt:   "walk towards the camera slowly"
```

**Face and body.** With no avatar on screen it does nothing at all. Do not let
that page send you looking for a voice mood setting — there isn't one.

### `emotion_support` on the voice list is a dead end too

`GET /v2/voices` carries an `emotion_support` field the v3 list hides. Of 2,956
voices, **55** have it — all tagged "Multilingual", **0 English**, and 50 of
them have `allowed_engines: []`, so they cannot run on Starfish at all. Their
names give them away: *"Gail in car"*, *"Lea outside walking"*.

### So: the mood is baked into the voice you pick

The style label in the name is the real handle. Among 1,099 English female
Starfish voices:

```
118  Bright & Energetic      46  Firm & Measured
113  Upbeat & Lively         35  Calm & Gentle
 30  Excited 🤩              15  Lifelike   ← Derya is here
```

⚠ **DERYA'S FULL NAME IS "Derya - Lifelike - Broadcaster 🎙️", AND THAT IS THE
WHOLE EXPLANATION FOR WHY SHE READS FLAT.** A broadcaster is built to be even.
Carson, 2026-09-21: *"This voice is not very energetic."* `speed` will not fix
it — a broadcaster at 1.1 is a fast broadcaster.

### AUDITIONING — previews are free, but patchy

`heygen_api.md` §6.1's advice stands: *"Play the preview_audio_url to audition a
voice before committing — saves credits."*

⚠ **BUT ONLY 2,040 OF 2,956 VOICES HAVE ONE, AND THE ENERGETIC GROUPS HAVE
NONE.** All 113 "Upbeat & Lively" English female voices came back with **zero**
previews — checked on the v3 list, the v2 list, and both single-voice
endpoints. To hear one you must render, at 1 credit for a short line.

**Design Voices** is the free-preview route: `POST /v3/voices` with a
plain-English `prompt` (max 1,000 chars) describing the mood, optional `gender`,
and `seed` (0 = best matches, increment for the next batch). It returns
candidate voices **with** preview urls. Confirmed live on this account — an
empty body came back `Field required: prompt`, which means enabled, not missing.

```bash
curl -X POST "https://api.heygen.com/v3/voices" \
  -H "X-Api-Key: $HEYGEN_API_KEY" -H "Content-Type: application/json" \
  -d '{"prompt":"A bright, upbeat female voice with warm energy. Friendly and
       encouraging, like a product demo host. Not shouty.","gender":"female"}'
```

⚠ **ITS COST IS UNMEASURED.** Nothing in the docs says. Measure it the usual
way — quota before, quota after — and record the number here.

### SO WHEN CARSON SAYS "MAKE IT PEPPIER", THE ORDER IS

1. **Design Voices** — describe the mood in his own words. Free to look at the
   candidates, because they come back with previews.
2. **Pick from the tagged groups** — 1 credit to hear one on a real line of his
   script. Generic marketing previews do not tell you how a voice reads HIS
   words, so audition on scene 1's line, not on the preview.
3. **The video endpoint, for `pitch` only** — last resort. Avatar-render prices
   for audio, asynchronous, and Starfish has no engine settings anyway.

⚠ **A VOICE SWAP DOES NOT THROW AWAY THE PAUSE WORK.** The two-pass timing is
computed per voice from its own `word_timestamps`, so changing voice just means
running the two passes again for that voice. Say so — Carson asked.

---

## THE REST OF THE API

The detail lives beside this file, moved with it:

| file | what |
|---|---|
| `heygen_api.md` | 41 KB — every endpoint this project uses, with HeyGen's own wording and ours |
| `heygen_api_addendum.md` | video agents, styles, later additions |
| `avatar_compositing.md` | putting an avatar in a corner over the demo |
| `avatar_launch.md` | starting an avatar render |
| `get_all_voices.md` / `.py` | the voice listing, wrapped |
| `get_all_avatar_images.md` / `.py` | the avatar listing, wrapped |
| `generate_avatar_video.py` | one avatar clip, full-screen or transparent corner |

⚠ **`heygen_api.md` STILL POINTS AT `docs.heygen.com`.** The live API now
returns a deprecation warning on every legacy call naming
`developers.heygen.com` and `https://developers.heygen.com/llms.txt` — an index
written for agents. Read that when an endpoint here looks wrong.

⚠ **`/v1/user/me` AND `/v2/user/remaining_quota` ARE BOTH RETIRED 2026-10-31.**
The replacement is `GET /v3/users/me`, which works today and carries the wallet.
The credits number has no v3 equivalent yet, so keep the v2 call until it dies.

---

## WHERE THE SHARED ASSETS LIVE

`MUX-Management/` is gone. Folded into `Studio/` on 2026-09-21:

```
Studio/avatars/   Sarah/, annie/, dt/, pamela/ — one set for every video
Studio/beds/      the silence beds
Studio/heygen/    the TypeScript tooling, config/, metadata.json, .env.local
Studio/mux/       tokens and the two signing keys
```

A video's **own** HeyGen work goes in that video's `4_avatar/` — see
`CLAUDE.md`'s "A VIDEO'S FOLDER SHAPE". Shared here, per-video there.

⚠ **`Studio/heygen/metadata.json` IS THE OLD STAGE RECORD AND IT IS THIN.** One
entry, `stages.combine.status: "pending"`, no asset id, no playback id. Do not
extend it for new videos — that is what `6_mux/mux_state.json` is for.
