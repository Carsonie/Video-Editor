#!/usr/bin/env python3
"""Fetch all looks for Pamela (or any group_id) and save the catalog.

Usage:
    python3 fetch_pamela_looks.py
    python3 fetch_pamela_looks.py suit blazer professional   # download previews for matches

- Always writes the full catalog to pamela_looks.json (IDs, names, preview URLs).
- Always writes a readable index to pamela_looks.txt (one line per look).
- If keyword args are given, downloads preview images for matching looks
  into ./pamela_previews/ so you can eyeball them.
- Reads the API key from the environment or from .env.local directly.

Lives in avatars/pamela/. Outputs are written next to this script; the
API key is read from .env.local at the project root, so it runs correctly
from any working directory.
"""
import json, subprocess, os, sys, urllib.request

GROUP_ID = "0484e7d80416443388aa1763f684f019"  # Pamela

# Resolve locations relative to this file, not the current directory.
BASE = os.path.dirname(os.path.abspath(__file__))            # avatars/pamela/
ROOT = os.path.abspath(os.path.join(BASE, "..", ".."))       # project root (HeyGen/)


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

keywords = [a.lower() for a in sys.argv[1:]]

# --- page through all looks ---
all_looks = []
token = ""
for _ in range(60):  # 60 * 50 = 3000 cap, plenty for 352
    url = f"https://api.heygen.com/v3/avatars/looks?group_id={GROUP_ID}&limit=50"
    if token:
        url += "&token=" + token
    out = subprocess.run(
        ["curl", "-s", "--max-time", "30", "-H", f"x-api-key: {key}", url],
        capture_output=True, text=True,
    ).stdout
    try:
        d = json.loads(out)
    except Exception:
        print("Bad response:", out[:200])
        break
    all_looks.extend(d.get("data", []))
    if not d.get("has_more"):
        break
    token = d.get("next_token", "")

print(f"Fetched {len(all_looks)} looks for Pamela.")

# --- save full catalog ---
json.dump(all_looks, open(os.path.join(BASE, "pamela_looks.json"), "w"), indent=2)
with open(os.path.join(BASE, "pamela_looks.txt"), "w") as f:
    for L in all_looks:
        f.write(f"{L.get('id')}\t{L.get('name')}\t{L.get('preview_image_url','')}\n")
print("Saved -> pamela_looks.json  and  pamela_looks.txt")

# --- optional: download previews for keyword matches ---
if keywords:
    previews_dir = os.path.join(BASE, "pamela_previews")
    os.makedirs(previews_dir, exist_ok=True)
    matched = [
        L for L in all_looks
        if any(kw in (L.get("name") or "").lower() for kw in keywords)
    ]
    print(f"\n{len(matched)} looks match {keywords}:")
    for L in matched:
        name = L.get("name", "")
        lid = L.get("id", "")
        img = L.get("preview_image_url")
        print("  ", lid, "|", name)
        if img:
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:60]
            dest = os.path.join(previews_dir, f"{safe}__{lid}.webp")
            try:
                urllib.request.urlretrieve(img, dest)
            except Exception as e:
                print("      (image download failed:", e, ")")
    print(f"\nPreview images saved in ./pamela_previews/  (open that folder to view)")
else:
    print("\nNo keywords given, so no images downloaded.")
    print("Re-run with style words to grab previews, e.g.:")
    print("    python3 fetch_pamela_looks.py suit blazer professional")
