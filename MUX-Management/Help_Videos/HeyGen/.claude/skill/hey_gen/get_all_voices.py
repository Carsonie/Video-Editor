#!/usr/bin/env python3
"""get_all_voices.py — list HeyGen voices for standalone TTS (Stage 1).

Mirrors the avatar skill, for voices. Uses the CURRENT v3 voices endpoint.

Key facts (baked in so we don't re-review docs):
  - Endpoint: GET /v3/voices  (optional ?engine=&language=&gender=)
  - Standalone TTS (POST /v3/voices/speech) ONLY works with voices on the
    "starfish" engine. So for picking a voice_id for the pipeline, ALWAYS
    filter engine=starfish.
  - Auth header is `x-api-key` (lowercase), value = HEYGEN_API_KEY.
  - Response nests voices under data.voices (sometimes just data[]); handle both.
  - `source .env.local` does NOT export to child processes; this script reads
    .env.local directly so the key is always found.
  - A voice's `voice_id` is what you drop into config/<slug>.json -> voice.voice_id.

USAGE:
  # List all Starfish (TTS-capable) English female voices:
  python3 get_all_voices.py list --language English --gender female

  # List ALL Starfish voices (no filter):
  python3 get_all_voices.py list

  # List voices on ANY engine (not just TTS-capable) — rarely needed:
  python3 get_all_voices.py list --engine any --language English

  # Find voices whose name matches a term (e.g. a broadcaster):
  python3 get_all_voices.py find broadcaster

  # Dump the full voice catalog to voices_catalog.json + .txt:
  python3 get_all_voices.py dump

By default engine=starfish (the only engine that works for TTS).
Pass `--engine any` to drop that filter.
"""
import json, subprocess, os, sys

API = "https://api.heygen.com"


def load_key():
    k = os.environ.get("HEYGEN_API_KEY")
    if k:
        return k
    here = os.getcwd()
    for _ in range(6):
        p = os.path.join(here, ".env.local")
        if os.path.exists(p):
            for line in open(p):
                line = line.strip()
                if line.startswith("HEYGEN_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        here = os.path.dirname(here)
    return None


KEY = load_key()
if not KEY:
    sys.exit("HEYGEN_API_KEY not found in env or any parent .env.local")


def fetch_voices(engine="starfish", language=None, gender=None):
    """GET /v3/voices with optional filters. Returns list of voice dicts."""
    qs = []
    if engine and engine != "any":
        qs.append(f"engine={engine}")
    if language:
        qs.append(f"language={language}")
    if gender:
        qs.append(f"gender={gender}")
    path = "/v3/voices" + ("?" + "&".join(qs) if qs else "")
    out = subprocess.run(
        ["curl", "-s", "--max-time", "30", "-H", f"x-api-key: {KEY}", API + path],
        capture_output=True, text=True,
    ).stdout
    try:
        d = json.loads(out)
    except Exception:
        print("  bad response:", out[:200])
        return []
    data = d.get("data", d)
    if isinstance(data, dict):
        return data.get("voices", [])
    if isinstance(data, list):
        return data
    return []


def line_for(v):
    bits = [
        v.get("voice_id", ""),
        v.get("name") or "(unnamed)",
        v.get("language") or "",
        v.get("gender") or "",
        "ssml" if v.get("support_pause") else "",
    ]
    return "  |  ".join(b for b in bits if b)


def get_opt(args, flag, default=None):
    return args[args.index(flag) + 1] if flag in args else default


def cmd_list(args):
    engine = get_opt(args, "--engine", "starfish")
    language = get_opt(args, "--language")
    gender = get_opt(args, "--gender")
    voices = fetch_voices(engine=engine, language=language, gender=gender)
    label = f"engine={engine}"
    if language:
        label += f", language={language}"
    if gender:
        label += f", gender={gender}"
    print(f"{len(voices)} voice(s) ({label}):\n")
    for v in voices:
        print(line_for(v))


def cmd_find(args):
    if not args or args[0].startswith("--"):
        sys.exit("usage: find <term> [--engine any] [--language X] [--gender Y]")
    term = args[0].lower()
    engine = get_opt(args, "--engine", "starfish")
    language = get_opt(args, "--language")
    gender = get_opt(args, "--gender")
    voices = fetch_voices(engine=engine, language=language, gender=gender)
    matches = [v for v in voices if term in (v.get("name") or "").lower()]
    print(f"{len(matches)} voice(s) matching '{term}' (engine={engine}):\n")
    for v in matches:
        print(line_for(v))


def cmd_dump(args):
    engine = get_opt(args, "--engine", "starfish")
    language = get_opt(args, "--language")
    gender = get_opt(args, "--gender")
    voices = fetch_voices(engine=engine, language=language, gender=gender)
    json.dump(voices, open("voices_catalog.json", "w"), indent=2)
    with open("voices_catalog.txt", "w") as f:
        for v in voices:
            f.write(
                f"{v.get('voice_id')}\t{v.get('name')}\t{v.get('language')}\t{v.get('gender')}\n"
            )
    print(f"Dumped {len(voices)} voices (engine={engine}) -> voices_catalog.json + .txt")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd, rest = sys.argv[1], sys.argv[2:]
    if cmd == "list":
        cmd_list(rest)
    elif cmd == "find":
        cmd_find(rest)
    elif cmd == "dump":
        cmd_dump(rest)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
