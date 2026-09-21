# Skill: Get All Voices (HeyGen)

**Purpose:** List and search HeyGen voices for standalone text-to-speech (TTS),
so a `voice_id` can be chosen for the voiceover pipeline (Stage 1).

**Location:** `HeyGen/.claude/skill/hey_gen/`
**Companion script:** `get_all_voices.py` (in this same folder)

---

## When to use this

Use whenever the goal is to **find or pick a voice** — e.g. "list female English
voices," "find a broadcaster voice," "what voices can I use for TTS," or "get me a
voice_id." It only lists/searches voices; it does not generate audio. The chosen
`voice_id` goes into `config/<slug>.json` under `voice.voice_id`.

To actually hear a voice, put its id in a config and run `npm run voiceover <slug>`
(that's the existing Stage 1 TTS path).

---

## The one rule that matters: Starfish engine

Standalone TTS (`POST /v3/voices/speech`) **only works with voices on the
"starfish" engine.** If a non-Starfish voice_id is used, generation fails.

So this skill **defaults to `engine=starfish`** in every command. Only pass
`--engine any` if the goal is to browse the full voice library for reasons other
than picking a TTS voice (rare).

---

## Hard-won gotchas

- Endpoint is **`GET /v3/voices`** with optional `engine`, `language`, `gender`
  query params. (Not `/v2/...`.)
- Auth header is **`x-api-key`** (lowercase), value = `HEYGEN_API_KEY`.
- The response nests voices under **`data.voices`** (sometimes just `data[]`) —
  the script handles both shapes.
- `source .env.local` does **not** export the key to child processes; the script
  reads `.env.local` directly.
- `support_pause: true` means the voice supports SSML `<break>` tags (shown as
  `ssml` in output) — useful if pacing/pauses are needed in narration.

---

## How to run it

From the **HeyGen project root** (where `.env.local` lives). Key is auto-found;
optionally export first:

```bash
export HEYGEN_API_KEY=$(grep '^HEYGEN_API_KEY=' .env.local | cut -d= -f2)
```

### 1. List TTS voices (filtered)

```bash
python3 .claude/skill/hey_gen/get_all_voices.py list --language English --gender female
```

Prints one line per voice: `voice_id | name | language | gender | ssml`.
(Equivalent to the existing `npm run voices English female`, but standalone.)

### 2. List ALL Starfish voices (no filter)

```bash
python3 .claude/skill/hey_gen/get_all_voices.py list
```

### 3. Find a voice by name term

```bash
python3 .claude/skill/hey_gen/get_all_voices.py find broadcaster
python3 .claude/skill/hey_gen/get_all_voices.py find Derya --language English
```

### 4. Dump the full catalog to files

```bash
python3 .claude/skill/hey_gen/get_all_voices.py dump --language English
```

Writes `voices_catalog.json` (full data) and `voices_catalog.txt`
(`voice_id <tab> name <tab> language <tab> gender`).

---

## Picking and recording a choice

1. Run a `list` or `find` command.
2. Copy the `voice_id` of the voice you want.
3. Put it in `config/<slug>.json` → `voice.voice_id`.
4. Audition by running `npm run voiceover <slug>` and playing
   `audio/<slug>.mp3`. Swap and re-run to A/B different voices.

---

## Endpoints reference (v3, current)

| Purpose | Endpoint | Notes |
|---|---|---|
| List/browse voices | `GET /v3/voices` | optional `engine`, `language`, `gender` |
| Generate TTS | `POST /v3/voices/speech` | synchronous; returns `audio_url`; Starfish voices only |

Voice fields of interest: `voice_id`, `name`, `language`, `gender`,
`support_pause` (SSML break support).

---

## Known-good example (verified)

- **Derya - Lifelike - Broadcaster** —
  voice_id `04d0ae1d0af2489ca7d3bb402a39a890`, English, female, Starfish.
  Confirmed working through Stage 1 TTS (generated `audio/first-time-ordering.mp3`).
  This is the currently-selected voice for the "First Time Ordering" pilot.
