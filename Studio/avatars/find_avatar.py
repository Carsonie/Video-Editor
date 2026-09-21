#!/usr/bin/env python3
"""Find an avatar by name across public AND private HeyGen avatar groups.

Usage:  python3 find_avatar.py Pamela

Lives in avatars/. The API key is read from .env.local at the project root,
and the matched group is saved to avatars/<name>/<name>_group.json — so it
runs correctly from any working directory and scales to new avatars.
"""
import json, subprocess, os, sys

# Resolve locations relative to this file, not the current directory.
BASE = os.path.dirname(os.path.abspath(__file__))       # avatars/
ROOT = os.path.abspath(os.path.join(BASE, ".."))        # project root (HeyGen/)


def load_key():
    k = os.environ.get("HEYGEN_API_KEY")
    if k:
        return k
    try:
        for line in open(os.path.join(ROOT, ".env.local")):
            line = line.strip()
            if line.startswith("HEYGEN_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return None


key = load_key()
if not key:
    sys.exit("HEYGEN_API_KEY not found in env or .env.local")

target = (sys.argv[1] if len(sys.argv) > 1 else "Pamela").lower()


def fetch(ownership):
    """Page through one ownership scope, return (all_names, match_or_None)."""
    token, names, match = "", [], None
    for _ in range(80):
        url = f"https://api.heygen.com/v3/avatars?ownership={ownership}&limit=50"
        if token:
            url += "&token=" + token
        out = subprocess.run(
            ["curl", "-s", "--max-time", "30", "-H", f"x-api-key: {key}", url],
            capture_output=True, text=True,
        ).stdout
        try:
            d = json.loads(out)
        except Exception:
            print(f"  [{ownership}] bad response:", out[:200])
            break
        for g in d.get("data", []):
            names.append(g.get("name"))
            if (g.get("name") or "").lower() == target:
                match = g
        if not d.get("has_more"):
            break
        token = d.get("next_token", "")
    return names, match


print(f"Searching for avatar: '{target}'\n")
found = None
for scope in ("public", "private"):
    names, match = fetch(scope)
    print(f"{scope.upper()} avatars ({len(names)}): {names}")
    if match and not found:
        found = match
        found["_scope"] = scope
    print()

if found:
    print("=== FOUND ===")
    print("  name    :", found.get("name"))
    print("  scope   :", found.get("_scope"))
    print("  group_id:", found.get("id"))
    print("  gender  :", found.get("gender"))
    print("  looks   :", found.get("looks_count"))
    print("  preview :", found.get("preview_image_url"))
    out_dir = os.path.join(BASE, target)
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"{target}_group.json")
    json.dump(found, open(out_file, "w"), indent=2)
    print(f"  saved -> avatars/{target}/{target}_group.json")
else:
    print(f"=== '{target}' NOT found in public or private avatars ===")
    print("If she's visible in the dashboard but not here, she isn't exposed")
    print("to the API your key can reach.")
