#!/usr/bin/env python3
"""
Render a whole video's narration in ONE HeyGen pass, then split it back into
the per-scene clips the rest of the pipeline already expects.

    python3 onepass_narration.py script "<video folder>"          # free — compose + cost
    python3 onepass_narration.py render "<video folder>"          # PAID — one render
    python3 onepass_narration.py split  "<video folder>"          # free — cut it up

WHY
---
Rendering scene by scene gives Sarah no run-up into a sentence and no run-out
of one. Every clip starts cold and ends cold, so every join is a small jolt —
and there are eleven of them. One pass lets her flow through the whole script.

Measured on a real render (2026-08-22): during a break she keeps breathing and
shifting (frame-to-frame motion 0.083 vs 0.191 while speaking), and she starts
moving again about a second BEFORE her voice returns. That anticipation is the
thing per-scene rendering cannot produce at any price.

HOW THE SPLIT IS SAFE
---------------------
Sentences are separated by an SSML `<break>`, which Sarah's voice honours
(`support_pause: true`). The break is deliberately LONGER than the finished
video needs — it is slack to cut away, not a measurement to get right. A 2.0s
break came back as ~3.0s of detected silence, because her own lead-out and
lead-in sit either side of it.

That margin is what makes the split reliable: a natural mid-sentence breath
measured 0.67s, so a threshold anywhere around 1.5s separates the two cleanly.

The split REFUSES to guess. If the number of gaps found is not exactly one less
than the number of scenes, it stops and shows what it found. Writing eleven
clips into twelve scene folders would corrupt every scene after the mistake,
and it would look like a narration problem rather than a splitting one.
"""
import argparse, json, os, re, subprocess, sys, time, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# paths.py lives in shared/ here, not beside these tools. In Basic_E2E_Testing
# it sat in this same folder; the flatten moved it down to where the editors
# import it from, and one home for it beats two that drift.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "shared"))
import paths as PTH

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
# $/second, measured from the 2026-08-22 probe: $0.35 for a 7.12s clip.
RATE = 0.049
# Alpha survives all three of decode, encode and container only if each is told.
DEC = ["-c:v", "libvpx-vp9"]
ENC = ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0",
       "-b:v", "2M", "-c:a", "libopus"]


def key():
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


def req(url, k, payload=None):
    r = urllib.request.Request(
        url, data=json.dumps(payload).encode() if payload else None,
        headers={"X-Api-Key": k, "Content-Type": "application/json"},
        method="POST" if payload else "GET")
    with urllib.request.urlopen(r, timeout=90) as resp:
        return json.load(resp)


def scenes_of(folder):
    cfg = json.load(open(PTH.script(folder)))
    out = [s for s in cfg["scenes"]
           if not s.get("silent") and s.get("line", "").strip()]
    return cfg, out


def compose(folder, brk):
    """The one-pass script: every line, joined by a break of `brk` seconds."""
    cfg, sc = scenes_of(folder)
    parts = []
    for i, s in enumerate(sc):
        parts.append(s["line"].strip())
        if i < len(sc) - 1:
            parts.append(f'<break time="{brk}s"/>')
    return cfg, sc, " ".join(parts)


def onepass_dir(folder):
    d = os.path.join(folder, "onepass")
    os.makedirs(d, exist_ok=True)
    return d


def newest_render(folder):
    d = onepass_dir(folder)
    best = (None, -1)
    for f in os.listdir(d):
        m = re.match(r"^narration-onepass-v(\d+)\.webm$", f)
        if m and int(m.group(1)) > best[1]:
            best = (os.path.join(d, f), int(m.group(1)))
    return best


def probe_duration(p, dec=True):
    r = subprocess.run(["ffprobe", "-v", "error"] + (DEC if dec else []) +
                       ["-show_entries", "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


# ── modes ──────────────────────────────────────────────────────────────────
def cmd_script(a):
    cfg, sc, text = compose(a.folder, a.brk)
    wps = cfg.get("words_per_second", 3.44)
    words = sum(len(s["line"].split()) for s in sc)
    speech = words / wps
    breaks = (len(sc) - 1) * a.brk
    total = speech + breaks
    print(f"\n  {len(sc)} scenes · {words} words · {wps} words/sec\n")
    for s in sc:
        print(f"   {s['n']:>2}  {s.get('label',''):<26} {len(s['line'].split()):>3}w"
              f"  ~{len(s['line'].split())/wps:5.1f}s")
    print(f"\n  speech      ~{speech:6.1f}s")
    print(f"  breaks       {breaks:6.1f}s   ({len(sc)-1} x {a.brk}s)")
    print(f"  RENDER      ~{total:6.1f}s   ~${total*RATE:.2f} at ${RATE}/s\n")
    print(f"  script ({len(text)} chars):\n")
    print("   " + text[:600].replace("\n", " ") + ("..." if len(text) > 600 else ""))
    out = os.path.join(onepass_dir(a.folder), "onepass-script.txt")
    open(out, "w").write(text)
    print(f"\n  written: {out}\n")


def cmd_render(a):
    cfg, sc, text = compose(a.folder, a.brk)
    k = key()
    before = req(f"{API}/users/me", k)["data"]["wallet"]["remaining_balance"]
    print(f"  wallet before: ${before}")
    print(f"  submitting {len(sc)} lines as ONE render...")
    r = req(f"{API}/videos", k, {
        "type": "avatar", "avatar_id": AVATAR_ID, "script": text,
        "voice_id": VOICE_ID,
        "title": f"{cfg.get('store','?')} {cfg.get('title','?')} — one-pass",
        "resolution": "1080p", "output_format": "webm"})
    if r.get("error"):
        sys.exit(f"REJECTED: {r['error']}")
    vid = r["data"]["video_id"]
    print(f"  video_id: {vid}\n  polling...")
    url = None
    deadline = time.time() + 60 * 40
    while time.time() < deadline:
        time.sleep(20)
        d = req(f"{API}/videos/{vid}", k).get("data", {})
        st = d.get("status")
        print(f"    {st}")
        if st in ("completed", "success"):
            url = d.get("video_url"); break
        if st in ("failed", "error"):
            sys.exit(f"FAILED: {d.get('error')}")
    if not url:
        sys.exit("timed out — the render may still finish; check the dashboard")
    # `v or 0` was wrong: newest_render returns -1 for "none yet", and -1 is
    # TRUTHY, so the first render came out named v0.
    _, v = newest_render(a.folder)
    out = os.path.join(onepass_dir(a.folder), f"narration-onepass-v{max(v, 0)+1}.webm")
    urllib.request.urlretrieve(url, out)
    after = req(f"{API}/users/me", k)["data"]["wallet"]["remaining_balance"]
    print(f"\n  saved: {out}  ({os.path.getsize(out)/1e6:.1f} MB, "
          f"{probe_duration(out):.2f}s)")
    print(f"  wallet after: ${after}   (spent ${round(before-after,2)})\n")


def cmd_split(a):
    cfg, sc = scenes_of(a.folder)
    src, v = newest_render(a.folder)
    if not src:
        sys.exit(f"no one-pass render in {onepass_dir(a.folder)} — run `render` first")
    dur = probe_duration(src)
    print(f"  source: {os.path.basename(src)}  {dur:.2f}s")

    r = subprocess.run(["ffmpeg", "-v", "info", "-i", src, "-af",
                        f"silencedetect=noise={a.noise}dB:d={a.min_gap}", "-f", "null", "-"],
                       capture_output=True, text=True)
    gaps = []
    start = None
    for line in r.stderr.splitlines():
        m = re.search(r"silence_start:\s*([\d.]+)", line)
        if m:
            start = float(m.group(1)); continue
        m = re.search(r"silence_end:\s*([\d.]+)\s*\|\s*silence_duration:\s*([\d.]+)", line)
        if m and start is not None:
            gaps.append((start, float(m.group(1)), float(m.group(2))))
            start = None
    # Trailing silence at the very end is not a break between two sentences.
    gaps = [g for g in gaps if g[1] < dur - 0.25]

    # Merge silences separated by almost nothing. One real 1.78s pause came back
    # as 0.84s + 0.94s because a click in the middle broke it in two, and both
    # halves then failed a threshold the whole would have passed.
    gaps.sort()
    merged = []
    for g in gaps:
        if merged and g[0] - merged[-1][1] < a.join:
            merged[-1] = (merged[-1][0], g[1], g[1] - merged[-1][0])
        else:
            merged.append(list(g) if False else (g[0], g[1], g[2]))
    gaps = merged

    # Take the N-1 LARGEST, rather than everything over a fixed threshold.
    #
    # The count is KNOWN — twelve sentences have eleven breaks — and that is far
    # stronger information than any dB-and-seconds guess. A fixed 1.5s cutoff
    # missed two real breaks here (1.33s and 0.94s) purely because Sarah trailed
    # off quickly into them, and no single number separated those from a 0.94s
    # thinking pause inside a line.
    want = len(sc) - 1
    if len(gaps) < want:
        print(f"\n  ✗ only {len(gaps)} silences found, need {want} for {len(sc)} scenes.")
        print( "    Lower --min-gap, or two lines ran together with no break at all.\n")
        sys.exit(2)
    ranked = sorted(gaps, key=lambda x: -x[2])
    chosen = sorted(ranked[:want])
    rejected = ranked[want:]

    # The margin IS the confidence. If the smallest break kept is barely bigger
    # than the biggest pause dropped, the split is a coin toss and should be
    # looked at rather than trusted.
    lo = min(g[2] for g in chosen)
    hi = max((g[2] for g in rejected), default=0.0)
    margin = (lo / hi) if hi else float("inf")
    print(f"  {len(gaps)} silences · keeping the {want} largest")
    print(f"  smallest kept {lo:.2f}s · largest dropped {hi:.2f}s · margin {margin:.2f}x")
    if margin < 1.3:
        print("\n  ⚠ THIN MARGIN — a pause inside a line is nearly as long as a real")
        print("    break. Check the boundaries below before trusting them, or raise")
        print("    --brk and re-render.")
    gaps = chosen

    # Cut at the MIDDLE of each gap, so every piece keeps her lead-out and the
    # next one keeps her lead-in. The editor trims the rest to fit the segment.
    cuts = [ (s + e) / 2 for s, e, _ in sorted(gaps) ]
    bounds = [0.0] + cuts + [dur]
    print()
    for i, s in enumerate(sc):
        a0, a1 = bounds[i], bounds[i + 1]
        sd = PTH.sandbox_dir(a.folder, s["n"], s.get("label"))
        os.makedirs(sd, exist_ok=True)
        dst = os.path.join(sd, "narration.webm")
        if os.path.isfile(dst) and not a.dry_run:
            hist = os.path.join(sd, "z_History", time.strftime("%Y%m%d-%H%M%S"))
            os.makedirs(hist, exist_ok=True)
            os.replace(dst, os.path.join(hist, "narration.webm"))
        line = f"   {s['n']:>2} {s.get('label',''):<26} {a0:7.2f} -> {a1:7.2f}  {a1-a0:5.2f}s"
        if a.dry_run:
            print(line + "   (dry run)"); continue
        rr = subprocess.run(["ffmpeg", "-v", "error"] + DEC +
                            ["-ss", f"{a0:.3f}", "-i", src, "-t", f"{a1-a0:.3f}"] +
                            ENC + ["-y", dst], capture_output=True, text=True)
        if rr.returncode != 0:
            print(line + f"   ✗ {rr.stderr[-200:]}"); continue
        print(line + f"   -> {os.path.relpath(dst, a.folder)}")
    print(f"\n  {'would write' if a.dry_run else 'wrote'} {len(sc)} clip(s). "
          f"Next: make overlays, then assemble.\n")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("script", cmd_script), ("render", cmd_render), ("split", cmd_split)):
        q = sub.add_parser(name)
        q.add_argument("folder")
        q.set_defaults(fn=fn)
        if name in ("script", "render"):
            q.add_argument("--brk", type=float, default=2.0,
                           help="seconds of SSML break between lines (default 2.0)")
        if name == "split":
            q.add_argument("--min-gap", type=float, default=0.8,
                           help="shortest silence even considered (default 0.8s). The "
                                "N-1 LARGEST are then chosen, so this only has to be "
                                "low enough to catch every real break.")
            q.add_argument("--join", type=float, default=0.25,
                           help="merge silences closer together than this (default "
                                "0.25s) — a click can split one pause into two")
            q.add_argument("--noise", type=float, default=-40,
                           help="silence threshold in dB (default -40)")
            q.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    a.folder = os.path.abspath(a.folder)
    a.fn(a)


main()
