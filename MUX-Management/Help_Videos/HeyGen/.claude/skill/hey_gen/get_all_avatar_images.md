# Skill: Get All Avatar Images (HeyGen)

**Purpose:** Find HeyGen avatars and download all of their look (outfit) preview
images locally, so a specific avatar + look can be chosen for video generation.

**Location:** `HeyGen/.claude/skill/hey_gen/`
**Companion script:** `get_all_avatar_images.py` (in this same folder)

---

## When to use this

Use this skill whenever the goal is to **browse, identify, or pick a HeyGen
avatar** — e.g. "find me a female avatar," "show me Pamela's outfits," "get the
avatar_id for X," or "download all the looks for avatar Y."

It does NOT generate videos. It only discovers avatars and saves their preview
images so a human can look and choose. The chosen `avatar_id` is then used later
by the (separate) avatar video-generation step.

---

## The mental model (important — this tripped us up before)

HeyGen avatars are a **two-level hierarchy**:

1. **Group** ("character", e.g. *Pamela*, *Annie*) — has a `group_id`,
   a `name`, a `gender`, and a `looks_count`.
2. **Looks** (outfits/poses within a group) — each look has its own `id`.
   **That look `id` is the `avatar_id`** you pass to video generation.

So picking an avatar really means: pick a **group**, then pick a **look** inside it.

### Hard-won gotchas

- A dashboard URL like `app.heygen.com/avatar/my-avatars/<ID>` contains the
  **group_id** — but that ID only resolves through
  `GET /v3/avatars/looks?group_id=<ID>`. It does **not** work with
  `/v2/avatar/<id>/details`, `/v2/talking_photos`, or digital-twin endpoints.
- **Do not use `/v2/avatars`** — it is deprecated and tends to hang. Always use
  the **v3** endpoints with `limit<=50` and follow `next_token` pagination.
- Auth header is **`x-api-key`** (lowercase), value = `HEYGEN_API_KEY`.
- `source .env.local` does **not** export the key to child processes (no
  `export` in the file). The script reads `.env.local` directly to avoid this.
- Many public avatars name every look identically (e.g. all 32 of Pamela's looks
  are just named "Pamela"). Names can't be used to tell looks apart — you must
  **look at the preview images** and identify by the `id` in the filename.
- `looks_count` on the group can be larger than the number the looks endpoint
  returns (Pamela showed 352 but 32 looks came back). Use what's returned.

---

## How to run it

All commands run from the **HeyGen project root** (where `.env.local` lives).
The script finds the key automatically. Optionally export it first:

```bash
export HEYGEN_API_KEY=$(grep '^HEYGEN_API_KEY=' .env.local | cut -d= -f2)
```

### 1. List avatar groups (optionally filter by gender)

```bash
python3 .claude/skill/hey_gen/get_all_avatar_images.py list --gender female
```

Prints one line per group: `group_id | name | gender | looks:N`.
(There are ~1,400 public avatars, so this returns a long list.)

### 2. Find one avatar group by name

```bash
python3 .claude/skill/hey_gen/get_all_avatar_images.py find "Pamela"
```

Searches public **and** private avatars, prints the `group_id` if found.

### 3. Download ALL look previews for an avatar

Accepts a **name** or a **group_id**:

```bash
python3 .claude/skill/hey_gen/get_all_avatar_images.py looks "Pamela"
# or
python3 .claude/skill/hey_gen/get_all_avatar_images.py looks 0484e7d80416443388aa1763f684f019
```

This writes to `./avatar_previews/<name>/`:
- `<name>__<look_id>.webp` — one preview image per look
- `_looks.json` — full look data
- `_looks.txt` — `id <tab> name <tab> preview_url` per line

Then open the folder to choose:

```bash
open avatar_previews/Pamela
```

**The string after `__` in a filename is the `avatar_id`.**

---

## Picking and recording a choice

1. Run the `looks` command for the avatar.
2. Open the folder, eyeball the previews, pick one.
3. Read the `avatar_id` from that file's name (after `__`, before `.webp`).
4. Record it wherever the project keeps avatar config (e.g. the per-video config
   JSON, or `session-memory.md`).

---

## Endpoints reference (v3, current)

| Purpose | Endpoint | Notes |
|---|---|---|
| List groups | `GET /v3/avatars` | `ownership=public\|private`, `limit` 1–50, `token` cursor, `has_more` |
| List looks | `GET /v3/avatars/looks` | `group_id=<id>`, same pagination |
| Look detail fields | (in looks response) | `id` (=avatar_id), `name`, `preview_image_url`, `preview_video_url`, `supported_api_engines` |

`supported_api_engines` may be `[]`; that does not necessarily block use, but
verify at generation time which engine the look accepts.

---

## Known-good example (verified)

- **Pamela** — group_id `0484e7d80416443388aa1763f684f019`, public, 32 looks
  returned, all named "Pamela", previews downloaded successfully.
- **Annie** — group_id `e0e84faea390465896db75a83be45085`, public, looks named
  by outfit (e.g. "Annie in Blue Suit" → `Annie_expressive_public`).
