#!/usr/bin/env python3
"""
Render every scene's narration as a transparent avatar clip.

Reads a video's `script.json` and generates one alpha WebM per scene, named
`sarah-scene-NN-alpha.webm` beside it. Submits them all first, then polls —
sequential submit-and-wait would take 15 minutes for eleven clips.

    python3 render_narration.py "<store>/help-videos/final"           # render all
    python3 render_narration.py "<folder>" --only 3 7                 # just these
    python3 render_narration.py "<folder>" --dry-run                  # cost only

Existing clips are SKIPPED unless --force. Re-rendering costs money, and the
common case after a script tweak is that only one or two lines changed.

⚠ Each clip is a real charge against the HeyGen wallet. Proofread first — the
  words are spoken exactly as written, so a typo costs another render.

⚠ AGENTS: ask before running this, with one line and nothing else:

      I need to pay HeyGen for this.  The COST should be around: $X.XX  Yes (Y) or No (N)

  Then stop and wait for Y or N. The number comes from --dry-run, never an
  estimate. Ask per run. --force pays again for clips that already exist.
"""
import hashlib
import argparse, json, os, re, sys, time, urllib.request

API = "https://api.heygen.com/v3"
AVATAR_ID = "468eabb3326a4d8587ba29d065b1eba7"
VOICE_ID  = "04d0ae1d0af2489ca7d3bb402a39a890"
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
# Where the HeyGen key is looked for, in order. It was ONE hardcoded path three
# levels up from this file — which resolved to the home directory once these
# tools moved, so the key was simply not found and the reason was invisible.
#
# The environment variable comes first because it is the one place a secret can
# live that no repo can accidentally swallow.
ENV_CANDIDATES = [
    os.path.join(REPO, ".env.local"),
    os.path.join(REPO, "Help_Videos", "HeyGen", ".env.local"),
]
ENV = ENV_CANDIDATES[0]          # what an error message names


def api_key():
    """The HeyGen key, from the environment or the first .env.local that has it.

    Every render is a real charge, so a key that is quietly missing has to fail
    loudly and say exactly where it looked."""
    from_env = os.environ.get("HEYGEN_API_KEY", "").strip()
    if from_env:
        return from_env
    for path in ENV_CANDIDATES:
        try:
            for line in open(path):
                m = re.match(r'\s*(?:export\s+)?HEYGEN_API_KEY\s*=\s*["\']?([^"\'\s]+)', line)
                if m:
                    return m.group(1)
        except OSError:
            continue
    sys.exit("HEYGEN_API_KEY not set. Put it in the environment, or in one of:\n  "
             + "\n  ".join(ENV_CANDIDATES))


def req(url, key, payload=None, tries=4):
    """
    Retries transient failures. A 502 mid-batch once killed the script AFTER
    seven clips were already submitted and charged for — the renders survived
    on HeyGen but the local process died holding their ids. Never let a
    transient error strand paid work.
    """
    last = None
    for i in range(tries):
        try:
            r = urllib.request.Request(
                url, data=json.dumps(payload).encode() if payload else None,
                headers={"X-Api-Key": key, "Content-Type": "application/json"},
                method="POST" if payload else "GET")
            with urllib.request.urlopen(r, timeout=60) as resp:
                return json.load(resp)
        except Exception as e:
            last = e
            code = getattr(e, "code", None)
            if code and code not in (429, 500, 502, 503, 504):
                raise
            time.sleep(3 * (i + 1))
    raise last


def wallet(key):
    try:
        return req(f"{API}/users/me", key).get("data", {}).get("wallet", {}).get("remaining_balance")
    except Exception:
        return None


def title_for(cfg, scene):
    """
    `<store> scene NN <hash>` — the hash is of the LINE.

    ⚠ The hash is load-bearing, not decoration. Adoption matches renders by
    title, and a title of just `<store> scene NN` is identical for every render
    of that scene ever made — so a changed line adopts the OLD render and the
    build ships stale audio while reporting success. That happened on
    2026-08-19: three rewritten lines "downloaded" for $0.00 and came back at
    their original durations.
    """
    h = hashlib.sha1(scene["line"].encode("utf-8")).hexdigest()[:8]
    return f"{cfg['store']} scene {scene['n']:02d} {h}"


def script_path(folder):
    """
    Locate a video's script.

    Moved to `<final>/sandbox/script.json` 2026-08-29 -- Carson's own call,
    to keep the script beside the scene folders it describes rather than a
    level up. `<final>/video/script.json` (2026-08-20 through 2026-08-29)
    and the bare `<final>/script.json` before that are both still accepted,
    so an un-migrated store keeps working rather than failing obscurely.

    Versioned snapshots (`script_v13.json`) are RECORDS written when a build is
    copied to a version, not inputs. At edit time the next version number is not
    known yet, so the working file stays unversioned.
    """
    import os
    new = os.path.join(folder, "sandbox", "script.json")
    mid = os.path.join(folder, "video", "script.json")
    old = os.path.join(folder, "script.json")
    if os.path.exists(new):
        return new
    if os.path.exists(mid):
        print(f"  ⚠ using {mid} — move it to sandbox/script.json")
        return mid
    if os.path.exists(old):
        print(f"  ⚠ using {old} — move it to sandbox/script.json")
        return old
    raise SystemExit(f"no script.json in {os.path.join(folder,'sandbox')}, "
                     f"{os.path.join(folder,'video')}, or {folder}")


def scene_clips_dir(folder):
    """
    Where the `sarah-scene-*-alpha.webm` narration clips live.

    Prefers `<final>/scenes/`, moved there 2026-08-20 so the per-scene clips sit
    together instead of loose in `final/`. Falls back to `<final>/` so a store
    that has not been migrated keeps working.

    ⚠ These are Sarah's voiced clips, NOT scenes. A scene is a segment plus its
    line and exists only as a row in script.json — no file is a scene. The
    folder is named for what a reader expects to find, and this note exists
    because a `scenes/` folder holding the wrong thing was renamed to
    `segments/` once already (glossary Decision 6).
    """
    import os, glob as _g
    d = os.path.join(folder, "scenes")
    if os.path.isdir(d) and _g.glob(os.path.join(d, "sarah-scene-*-alpha.webm")):
        return d
    return folder


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--only", nargs="*", type=int, help="scene numbers")
    ap.add_argument("--force", action="store_true", help="re-render even if the file exists")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cfg = json.load(open(script_path(a.folder)))
    scenes = [s for s in cfg["scenes"] if not a.only or s["n"] in a.only]

    todo = []
    for s in scenes:
        # A SILENT scene is deliberate — the segment plays with Sarah waiting in
        # the corner and nothing spoken. It must never be submitted: HeyGen is
        # billed per render, and an empty script would be paid for and useless.
        # assemble_video.py builds these from idle footage instead.
        if bool(s.get("silent")) or not s.get("line", "").strip():
            print(f"  skip  scene {s['n']:>2}  (silent — no narration by design)")
            continue
        out = os.path.join(scene_clips_dir(a.folder), f"sarah-scene-{s['n']:02d}-alpha.webm")
        if os.path.exists(out) and not a.force:
            print(f"  skip  scene {s['n']:>2}  (exists)")
            continue
        todo.append((s, out))

    if not todo:
        print("\nnothing to render.")
        return
    print(f"\n  {len(todo)} clip(s) to render, ~$0.40 each  =>  ~${0.40*len(todo):.2f}")
    for s, _ in todo:
        print(f"    {s['n']:>2}  {len(s['line'].split()):>3}w  {s['line'][:72]}...")
    if a.dry_run:
        print("\n  --dry-run, nothing submitted.")
        return

    key = api_key()
    before = wallet(key)
    print(f"\n  wallet before: ${before}")

    # Adopt anything already submitted for this store — a crashed or re-run
    # batch must never pay for the same clip twice.
    remote = {}
    if a.force:
        print("    --force: not adopting any existing render")
    try:
        d = req(f"{API}/videos?limit=50", key).get("data")
        vids = d if isinstance(d, list) else (d or {}).get("videos") or (d or {}).get("list") or []
        for v in vids:
            t = (v.get("title") or "").strip()
            if v.get("status") not in ("processing", "pending", "waiting", "completed"):
                continue
            # Only adopt a render whose title carries THIS line's hash.
            for sc in cfg["scenes"]:
                if t == title_for(cfg, sc):
                    remote.setdefault(sc["n"], v.get("id") or v.get("video_id"))
    except Exception as e:
        print(f"    (could not list existing renders: {e})")

    jobs = []
    for s, out in todo:
        if s["n"] in remote and not a.force:
            jobs.append({"n": s["n"], "id": remote[s["n"]], "out": out, "done": False})
            print(f"    adopted  scene {s['n']:>2}  {remote[s['n']]}  (already submitted)")
            continue
        r = req(f"{API}/videos", key, {
            "type": "avatar", "avatar_id": AVATAR_ID, "script": s["line"],
            "voice_id": VOICE_ID, "title": title_for(cfg, s),
            "resolution": "1080p", "output_format": "webm"})
        if r.get("error"):
            sys.exit(f"scene {s['n']} rejected: {r['error']}")
        jobs.append({"n": s["n"], "id": r["data"]["video_id"], "out": out, "done": False})
        print(f"    submitted scene {s['n']:>2}  {r['data']['video_id']}")
        # written after every submit, not at the end — the point is to survive a crash
        json.dump([{k: j[k] for k in ("n", "id", "out")} for j in jobs],
                  open(os.path.join(a.folder, ".render_jobs.json"), "w"), indent=2)

    print("\n  polling...")
    deadline = time.time() + 60 * 25
    while any(not j["done"] for j in jobs) and time.time() < deadline:
        time.sleep(15)
        for j in jobs:
            if j["done"]:
                continue
            d = req(f"{API}/videos/{j['id']}", key).get("data", {})
            st = d.get("status")
            if st == "completed":
                urllib.request.urlretrieve(d["video_url"], j["out"])
                j["done"] = True
                print(f"    scene {j['n']:>2}  downloaded  ({os.path.getsize(j['out'])/1e6:.1f} MB)")
            elif st == "failed":
                j["done"] = True
                print(f"    scene {j['n']:>2}  FAILED: {d}")

    missing = [j["n"] for j in jobs if not os.path.exists(j["out"])]
    after = wallet(key)
    print(f"\n  wallet after: ${after}" + (f"   (spent ~${before-after:.2f})" if before and after else ""))
    if missing:
        sys.exit(f"  incomplete: scenes {missing}")
    print(f"  all {len(jobs)} clip(s) rendered into {a.folder}")


if __name__ == "__main__":
    main()
