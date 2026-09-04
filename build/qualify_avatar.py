#!/usr/bin/env python3
"""
Pre-qualify a video's frames BEFORE anything is built from them.

    python3 build/qualify_avatar.py "<video folder>"
    python3 build/qualify_avatar.py "<video folder>" --quiet    # only failures

WHAT IT IS FOR
    A build reads two tracks and lays one over the other. It assumes, without
    ever checking, that for every frame of footage there is a matching frame of
    Sarah, and that the Sarah frame has Sarah in it.

    Both assumptions have now failed in production, silently:

      * A joined scene's narration was TRANSPARENT for its first 285 frames,
        because the half being joined in had no HeyGen render and the join
        filled the gap to hold the timing. The build composited 11.4 seconds of
        nothing and reported success.

      * The frame counts of the two tracks drift apart as scenes are edited,
        and the build papers over it by holding whichever is short. That is
        right for a small difference and wrong for a large one, and nothing
        said which had happened.

    So this runs first and refuses. A build that cannot stage a matched pair
    for every position has no business starting.

THE THREE SHAPES SARAH IS EVER IN
    Measured across ski-demo's 2753 avatar frames, her height as a share of the
    canvas falls into three bands with nothing in between:

        25-29%   2570 frames    CORNER      the head shot she spends the video in
        30-84%     18 frames    TRANSITION  the sizing morph, in and out
        85-89%    163 frames    SEATED      full frame, the opening and closing

    That is the whole vocabulary. A frame outside those bands, or with no Sarah
    at all, is not a fourth style — it is a fault, and this says so.

    A short help clip that is corner-only for its whole length is normal and
    passes: the bands are about what a frame IS, not about the order they come
    in. Only EMPTY is always wrong.

EXIT CODE
    0  every scene staged and every frame qualified
    1  something is missing, mismatched, or empty

    Made to gate a build:  python3 build/qualify_avatar.py "$V" && python3 build/assemble_video.py "$V"
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "shared"))
import paths as PTH  # noqa: E402

try:
    from PIL import Image
except ImportError:
    sys.exit("  qualify_avatar needs Pillow:  pip3 install Pillow")

# Her height as a share of the canvas. The gaps between these bands are wide —
# the measured data has nothing between 30% and 84% except the morph itself —
# so a frame that lands outside them is a real anomaly and not a rounding case.
CORNER = (18, 34)
TRANSITION = (34, 80)
SEATED = (80, 96)

# The morph is about 30 frames. Anything much longer is not a morph; it is a
# clip that was cut in the middle of one, or two clips joined at the wrong place.
TRANSITION_MAX = 60

PROBE = 144          # alpha is measured at this size; the bands are percentages


def decoded_frames(path, alpha):
    dec = ["-c:v", "libvpx-vp9"] if alpha else []
    r = subprocess.run(["ffprobe", "-v", "error"] + dec + ["-select_streams", "v",
                        "-count_frames", "-show_entries", "stream=nb_read_frames",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    out = r.stdout.strip()
    return int(out) if out.isdigit() else None


def heights(path):
    """Her height, per frame, as a percentage of the canvas. 0 means empty."""
    tmp = tempfile.mkdtemp(prefix="qualify_")
    try:
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", path,
             "-vf", f"alphaextract,scale={PROBE}:{PROBE}",
             "-fps_mode", "passthrough", "-start_number", "1",
             os.path.join(tmp, "a_%05d.png")], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(r.stderr[-300:])
        out = []
        for f in sorted(glob.glob(os.path.join(tmp, "a_*.png"))):
            im = Image.open(f).convert("L")
            px, w, h = im.load(), *im.size
            ys = [y for y in range(h) if any(px[x, y] > 32 for x in range(0, w, 2))]
            out.append(0 if not ys else round((ys[-1] - ys[0]) / h * 100))
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def band(pct):
    if pct == 0:
        return "EMPTY"
    if CORNER[0] <= pct < CORNER[1]:
        return "corner"
    if TRANSITION[0] <= pct < TRANSITION[1]:
        return "transition"
    if SEATED[0] <= pct <= SEATED[1]:
        return "seated"
    return "OUTSIDE"


def runs(bands):
    """['seated','seated','corner'] -> [('seated',2), ('corner',1)] — the SHAPE
    of a scene, which is what a person reads to see whether it is the one they
    meant to build."""
    out = []
    for b in bands:
        if out and out[-1][0] == b:
            out[-1][1] += 1
        else:
            out.append([b, 1])
    return [(b, n) for b, n in out]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", help="a video folder, e.g. .../videos/01-first-time-ordering")
    ap.add_argument("--quiet", action="store_true", help="only print what fails")
    ap.add_argument("--log", action="store_true", help="write the report beside the video")
    a = ap.parse_args()

    F = os.path.abspath(a.folder)
    scenes = PTH.scenes_from_script(F)
    if not scenes:
        sys.exit(f"  no scenes in {PTH.script(F)}")

    lines = []

    def say(t="", always=False):
        lines.append(t)
        if always or not a.quiet:
            print(t)

    say(f"\n  Qualify — {os.path.basename(F)}   {time.strftime('%Y-%m-%d %H:%M:%S')}")
    say(f"  {len(scenes)} scene(s) in the script\n")

    faults = []

    # ── 1. STAGE THE PAIRS. Nothing is measured until every scene has both. ──
    say("  Staging — one segment and one overlay per scene")
    staged = []
    for n, label in scenes:
        sb = PTH.sandbox_only(F, n, label)
        seg, ov = sb["segment"], sb["avatar"]
        miss = [w for w, p in (("segment", seg), ("overlay", ov)) if not p]
        if miss:
            faults.append(f"scene {n} {label}: no {' and no '.join(miss)} in sandbox/")
            say(f"    ✗ {n:>2} {label:<28} MISSING {', '.join(miss)}", always=True)
            continue
        # The narration is READ but no longer gates anything. The build
        # composites avatar.webm now — the file the editor shows and the one
        # that gets approved — so that is what has to be right.
        #
        # It is still measured and reported, because it is the raw render the
        # avatar was made from and a difference between them is worth seeing.
        # It just cannot stop a build any more: failing over a file nothing
        # reads is the mirror of the bug this tool was written for.
        nar = sb["narration"]
        ns, no = decoded_frames(seg, False), decoded_frames(ov, True)
        if ns is None or no is None:
            faults.append(f"scene {n} {label}: a track could not be counted")
            say(f"    ✗ {n:>2} {label:<28} unreadable", always=True)
            continue
        if ns != no:
            # Not fatal on its own — the build holds the shorter track, and a
            # few frames is normal. It is reported every time because a LARGE
            # gap is how a wrong file gets composited without anyone noticing.
            say(f"    ⚠ {n:>2} {label:<28} {ns:>5} SG  {no:>5} OL   differ by {ns-no:+d}",
                always=abs(ns - no) > 30)
            if abs(ns - no) > 30:
                faults.append(f"scene {n} {label}: tracks differ by {ns-no:+d} frames")
        else:
            say(f"    ✓ {n:>2} {label:<28} {ns:>5} SG  {no:>5} OL")
        staged.append((n, label, seg, ov, nar, ns, no))

    if faults:
        say("\n  Refused before measuring anything — the pairs are not staged.", always=True)
        for f in faults:
            say(f"    {f}", always=True)
        return 1

    # ── 2. QUALIFY EVERY OVERLAY FRAME ──────────────────────────────────────
    say("\n  Qualifying — every overlay frame, against the three known shapes")
    say("    OL  is what the BUILD composites, and what can fail this.")
    say("    NAR is the raw render behind it — reported, never a gate.")
    say(f"    corner {CORNER[0]}-{CORNER[1]}%   transition {TRANSITION[0]}-{TRANSITION[1]}%   "
        f"seated {SEATED[0]}-{SEATED[1]}%\n")
    tot = {"corner": 0, "transition": 0, "seated": 0, "EMPTY": 0, "OUTSIDE": 0}
    for n, label, seg, ov, nar, ns, no in staged:
        # BOTH clips, and the narration is the one that matters most: it is what
        # the build composites. `OL` is the editor's preview; `NAR` is the master.
        for what, clip, gates in (("OL ", ov, True), ("NAR", nar, False)):
            if clip is None:
                say(f"    - {n:>2} {label:<28} {what}  none — nothing to qualify")
                continue
            try:
                hs = heights(clip)
            except RuntimeError as e:
                faults.append(f"scene {n}: could not read the {what.strip()} — {e}")
                say(f"    ✗ {n:>2} {label:<28} {what}  unreadable", always=True)
                continue
            bs = [band(h) for h in hs]
            for b in bs:
                tot[b] = tot.get(b, 0) + 1
            shape = "  ".join(f"{b} {c}" for b, c in runs(bs))
            bad = [(i, hs[i]) for i in range(len(bs)) if bs[i] in ("EMPTY", "OUTSIDE")]
            long_t = [(b, c) for b, c in runs(bs) if b == "transition" and c > TRANSITION_MAX]
            mark = "✗" if bad or long_t else "✓"
            say(f"    {mark} {n:>2} {label:<28} {what}  {shape}",
                always=bool(bad or long_t))
            if bad:
                first = bad[0]
                msg = (f"scene {n} {label}: {what.strip()} has {len(bad)} frame(s) with "
                       f"no usable Sarah, first at frame {first[0]+1} ({first[1]}% tall)")
                if gates:
                    faults.append(msg + ". This is the clip the BUILD composites, so "
                                        "those frames would ship empty.")
                else:
                    say(f"      note: {msg}. Nothing builds from this — it is the raw "
                        f"render behind the avatar.", always=True)
            for _b, c in long_t:
                msg = (f"scene {n} {label}: {what.strip()} has a {c}-frame transition — "
                       f"a morph is about 30; this looks like a clip cut mid-morph")
                if gates:
                    faults.append(msg)
                else:
                    say(f"      note: {msg}", always=True)

    say(f"\n  {sum(tot.values())} overlay frames:  "
        + "  ".join(f"{k} {v}" for k, v in tot.items() if v))

    if a.log:
        d = os.path.join(F, "work")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, f"qualify_{time.strftime('%Y%m%d-%H%M%S')}.log")
        open(p, "w").write("\n".join(lines) + "\n")
        print(f"\n  written to {p}")

    if faults:
        print("\n  ✗ NOT QUALIFIED — do not build from this:", flush=True)
        for f in faults:
            print(f"      {f}")
        return 1
    print("\n  ✓ qualified — every pair staged, every frame a known shape")
    return 0


if __name__ == "__main__":
    sys.exit(main())
