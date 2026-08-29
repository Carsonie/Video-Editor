#!/usr/bin/env python3
"""
Render a video's VTT — Video Timing Table.

For each scene: how long the demo clip runs, how long Sarah's line takes to
say, and the GAP between them. The gap is the whole point — it is how long she
sits frozen in the corner with nothing to say, and it is invisible until
someone watches the finished video.

    python3 vtt.py "Customers/<Business>/<store>/help-videos/final"

Clip lengths are read from the files on disk; lines come from that folder's
`script.json`, which is the single source of truth for the copy. Edit the
lines there and re-run — never retype a line into a doc or a chat message,
which is how copy drifts from what actually got rendered.

Speech length is estimated at the voice's MEASURED words-per-second, taken
from clips already rendered (`words_per_second` in script.json). Derya came
out at 3.44 wps — an earlier guess of 2.70 understated every line by ~25% and
hid a third of the dead air. Re-derive it whenever the voice or its speed
setting changes.

⚠ Not to be confused with WebVTT (`.vtt` subtitles). Different thing entirely.
"""
import argparse
import re
import glob
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402


def words(line):
    """
    Count SPOKEN words. A token with no letter or digit in it is punctuation
    standing alone — an em dash between spaces is the one that occurs here — and
    the voice does not say it. `line.split()` counted it, which added a whole
    word (0.29s at 3.44 wps) to every line written with a spaced dash.
    """
    return len([w for w in line.split() if re.search(r"[A-Za-z0-9]", w)])


def dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        sys.exit(f"could not read duration of {path}")


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", help="a video's final/ folder (holds script.json and segments/)")
    ap.add_argument("--rewrite-over", type=float, default=2.5,
                    help="flag a scene whose gap exceeds this many seconds")
    a = ap.parse_args()

    sj = script_path(a.folder)
    if not os.path.exists(sj):
        sys.exit(f"no script.json in {a.folder}")
    cfg = json.load(open(sj))
    wps = cfg.get("words_per_second", 3.44)

    print(f"\n### VTT — {cfg.get('store','?')} · {cfg.get('title','')}   ({wps} words/sec)\n")
    print("| # | scene | clip | speech | gap | Sarah says |")
    print("|---|---|---|---|---|---|")

    for r in cfg.get("rendered", []):
        d = r["duration"]
        # A new store's opening is not rendered yet, so its duration is null.
        # Estimate from the word count instead of crashing — the whole point of
        # a VTT is to be readable BEFORE anything has been paid for.
        if d is None:
            est = words(r["line"]) / wps
            print(f'| — | {r["label"]} *(not yet rendered)* | — | ~{est:.1f}s | — | "{r["line"]}" |')
        else:
            print(f'| — | {r["label"]} *(rendered)* | {d:.1f}s | {d:.1f}s | — | "{r["line"]}" |')

    tc = ts = tg = 0.0
    flagged = []
    for s in cfg["scenes"]:
        # Resolved, not joined: a scene's footage lives in dev/<NN>-<label>/ after
        # the 2026-08-22 restructure and in segments/ before it, and both layouts
        # have to work while the other three stores are still flat.
        p = paths.segment(a.folder, s["n"], s.get("label"))
        if p is None:
            p = os.path.join(a.folder, "segments", s["segment"])
        if not os.path.exists(p):
            sys.exit(f"no footage for scene {s['n']} ({s.get('label','')}) — "
                     f"looked in dev/ and segments/")
        c = dur(p)
        nw = words(s["line"])
        # Pauses are inserted locally after rendering (HeyGen's script field is
        # plain text — no SSML, no <break>), but they occupy real time on
        # screen, so they count toward the scene's spoken length.
        pause = sum(x.get("seconds", 0) for x in s.get("pauses", []))
        sp = nw / wps + pause
        g = c - sp
        tc += c; ts += sp; tg += max(0.0, g)
        # A scene may name itself. The fallback derives a name from the file,
        # which worked while segments were called `segment-04-search.mp4` but
        # yields a bare "segment" for the MP4 Splitter's `Num_4-v2-segment.mp4` —
        # so every row in a 14-row table reads the same and the VTT stops
        # being scannable. `label` is optional; stores that don't set it keep
        # exactly the old behaviour.
        name = s.get("label") or s["segment"].split("-", 2)[-1].rsplit(".", 1)[0]
        if pause:
            name += f" +{pause:g}s pause"
        if g > a.rewrite_over:
            gs = f"**{g:.1f}s**"; flagged.append((s["n"], name, g, nw, round(c * wps)))
        elif g < 0:
            gs = f"**{g:.1f}s over**"
        else:
            gs = f"{g:.1f}s"
        print(f'| {s["n"]} | {name} | {c:.1f}s | {sp:.1f}s | {gs} | "{s["line"]}" |')

    # Estimate any opening that has not been rendered yet, same as the rows above.
    rd = sum(r["duration"] if r.get("duration") is not None
             else words(r["line"]) / wps
             for r in cfg.get("rendered", []))
    print(f"| | **total** | **{tc+rd:.1f}s** | **{ts+rd:.1f}s** | **{tg:.1f}s** | "
          f"{sum(words(s['line']) for s in cfg['scenes'])} words across {len(cfg['scenes'])} scenes |")

    if flagged:
        # Advice, not a defect list. Settled 2026-08-19: a segment outlasting its
        # line is fine — the hold plays real idle footage, so Sarah waits rather
        # than freezing. Only pad a line when the gap actually feels slack.
        print(f"\n**{len(flagged)} scene(s) could take more words** — at {wps} wps a clip "
              f"wants ~{wps:.1f} words/sec. A gap is not a defect: the hold is filled with "
              f"idle footage. Pad only what feels slack:\n")
        for n, name, g, have, want in flagged:
            print(f"- **{n} {name}** — {g:.1f}s of Sarah waiting. Has {have} words, "
                  f"room for ~{want}.")
    else:
        print(f"\nNo scene exceeds the {a.rewrite_over}s gap threshold.")
    print(f"\nDead air is {tg/(tc+rd)*100:.0f}% of the finished video.")


if __name__ == "__main__":
    main()
