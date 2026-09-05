#!/usr/bin/env python3
"""get_all_avatar_images.py — find HeyGen avatars and download their look previews.

Proven workflow (uses the CURRENT v3 endpoints, not deprecated v1/v2):
  1. GET /v3/avatars            -> list avatar GROUPS (characters), paginated
  2. GET /v3/avatars/looks      -> list LOOKS (outfits) inside one group
  3. download each look's preview_image_url locally so you can see them

Key facts learned the hard way:
  - The id in a dashboard URL (/avatar/my-avatars/<ID>) IS the group_id, but it
    only resolves via /v3/avatars/looks?group_id=<ID> — NOT /v2/avatar/<id>/details.
  - /v2/avatars is deprecated and tends to hang. Always use /v3 with limit<=50.
  - `source .env.local` does NOT export to child processes; this script reads
    .env.local directly so the key is always found.
  - A look's `id` is the value you pass as `avatar_id` to video generation.

USAGE:
  # List female avatar groups (name + group_id):
  python3 get_all_avatar_images.py list --gender female

  # Find a specific avatar group by name (searches public + private):
  python3 get_all_avatar_images.py find "Pamela"

  # Download ALL look previews for a group (by name OR group_id) into a folder:
  python3 get_all_avatar_images.py looks "Pamela"
  python3 get_all_avatar_images.py looks 0484e7d80416443388aa1763f684f019

Output for `looks` goes to ./avatar_previews/<name>/ with each file named
<name>__<look_id>.webp  — the part after "__" is the avatar_id to use.
"""
import json, subprocess, os, sys, urllib.request

API = "https://api.heygen.com"


def load_key():
    k = os.environ.get("HEYGEN_API_KEY")
    if k:
        return k
    # walk up from cwd looking for .env.local (project root may be a few levels up)
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


def api_get(path):
    """GET a v3 endpoint, return parsed JSON (or None on failure)."""
    out = subprocess.run(
        ["curl", "-s", "--max-time", "30", "-H", f"x-api-key: {KEY}", API + path],
        capture_output=True, text=True,
    ).stdout
    try:
        return json.loads(out)
    except Exception:
        print("  bad response:", out[:200])
        return None


def list_groups(ownership=None, gender=None, max_pages=60):
    """Page through avatar groups. Returns list of group dicts.
    gender filter accepts female/male and matches both 'female'/'woman' etc."""
    groups, token = [], ""
    for _ in range(max_pages):
        q = "limit=50"
        if ownership:
            q += f"&ownership={ownership}"
        if token:
            q += f"&token={token}"
        d = api_get(f"/v3/avatars?{q}")
        if not d:
            break
        for g in d.get("data", []):
            if gender:
                gv = (g.get("gender") or "").lower()
                if gender.lower() == "female" and gv not in ("female", "woman"):
                    continue
                if gender.lower() == "male" and gv not in ("male", "man"):
                    continue
            groups.append(g)
        if not d.get("has_more"):
            break
        token = d.get("next_token", "")
    return groups


def get_looks(group_id, max_pages=60):
    """Page through all looks for a group_id."""
    looks, token = [], ""
    for _ in range(max_pages):
        q = f"group_id={group_id}&limit=50"
        if token:
            q += f"&token={token}"
        d = api_get(f"/v3/avatars/looks?{q}")
        if not d:
            break
        looks.extend(d.get("data", []))
        if not d.get("has_more"):
            break
        token = d.get("next_token", "")
    return looks


def resolve_group_id(name_or_id):
    """If given a hex id, use it. Otherwise search groups by name."""
    s = name_or_id.strip()
    if len(s) >= 24 and all(c in "0123456789abcdef" for c in s.lower()):
        return s, s  # looks like an id
    target = s.lower()
    for ownership in ("public", "private"):
        for g in list_groups(ownership=ownership):
            if (g.get("name") or "").strip().lower() == target:
                return g.get("id"), g.get("name")
    return None, None


def cmd_list(args):
    gender = None
    if "--gender" in args:
        gender = args[args.index("--gender") + 1]
    groups = list_groups(gender=gender)
    print(f"{len(groups)} avatar group(s)" + (f" (gender={gender})" if gender else "") + ":")
    for g in groups:
        print(f"  {g.get('id')} | {g.get('name')} | {g.get('gender')} | looks:{g.get('looks_count')}")


def cmd_find(args):
    if not args:
        sys.exit("usage: find <name>")
    gid, name = resolve_group_id(args[0])
    if gid:
        print(f"FOUND '{name}'  group_id={gid}")
    else:
        print(f"'{args[0]}' not found in public or private avatars.")


def cmd_looks(args):
    if not args:
        sys.exit("usage: looks <name|group_id>")
    gid, name = resolve_group_id(args[0])
    if not gid:
        sys.exit(f"Could not resolve '{args[0]}' to a group.")
    name = name or args[0]
    looks = get_looks(gid)
    print(f"{name}: fetched {len(looks)} looks (group_id={gid})")

    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(name))[:40]
    outdir = os.path.join("avatar_previews", safe_name)
    os.makedirs(outdir, exist_ok=True)

    json.dump(looks, open(os.path.join(outdir, "_looks.json"), "w"), indent=2)
    with open(os.path.join(outdir, "_looks.txt"), "w") as f:
        for L in looks:
            f.write(f"{L.get('id')}\t{L.get('name')}\t{L.get('preview_image_url','')}\n")

    ok = 0
    for L in looks:
        img = L.get("preview_image_url")
        lid = L.get("id", "")
        if not img:
            continue
        dest = os.path.join(outdir, f"{safe_name}__{lid}.webp")
        try:
            urllib.request.urlretrieve(img, dest)
            ok += 1
        except Exception as e:
            print("  image failed:", lid, e)
    print(f"Saved {ok} preview images + catalog to ./{outdir}/")
    print(f"Each file: {safe_name}__<avatar_id>.webp  (string after __ is the avatar_id)")
    print(f"Open it:  open '{outdir}'")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd, rest = sys.argv[1], sys.argv[2:]
    if cmd == "list":
        cmd_list(rest)
    elif cmd == "find":
        cmd_find(rest)
    elif cmd == "looks":
        cmd_looks(rest)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
