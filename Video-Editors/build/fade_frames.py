#!/usr/bin/env python3
"""
Generate morphed transition frames between two Sarah frames.

WHAT IT IS FOR
--------------
Smoothing a hard cut between two avatar frames — most usefully the video's
CLOSING (scene 11's last frame -> the canonical rest pose, a different render),
and the held frames spliced in for mid-line pauses.

THE RULE, AND WHY IT HAS A CEILING
----------------------------------
Frame count is derived from how different the two frames actually are:

    frames = ceil(difference% / --per-step)

Measured on ski-demo, real differences land in a 2%-14% band — NOT 0-100%. So
`--per-step 10` (the first instinct) yields ZERO frames for almost everything.
The default is 2.0, which gives 1-7 frames.

But above `--cap` (default 5%) a crossfade is WORSE than the cut, and the tool
refuses. This is not conservatism, it is measured: at ski-demo's scene 07->08
boundary (13.8% different) her hands are down and settled in one frame and
raised and clasped in the next. A blend there is two faces and four hands — a
double exposure, not a fade. Realigning does not help, because the hands are
genuinely elsewhere; there is no correspondence to interpolate. Fixing the CUT
is the answer at those boundaries, exactly as with the loading-spinner bug.

Pass `--no-cap` to override, and look at the result before believing it.

THE NUMBER IS FRAMING-DEPENDENT — CALIBRATE IN THE SPACE YOU USE IT
------------------------------------------------------------------
The same two frames measure 4.43% at 608x1080 and 8.50% cropped to the 300x300
corner. Nothing is wrong: the corner crop is head-and-shoulders, so it isolates
the face, and the static torso is no longer there to dilute the difference. The
corner figure is the honest one when the corner is what ships.

So `--cap` is not a universal constant. `assemble_video.py` uses 9.0 because it
measures corner-scaled frames; a full-frame comparison wants roughly half that.
Measure a real seam in the space it will be used before trusting a threshold.

A SCALAR CANNOT TELL "EXPRESSION CHANGED" FROM "LIMBS MOVED"
-----------------------------------------------------------
This is the metric's real limitation. 8.5% of expression change dissolves
acceptably; 13.8% of hand movement does not, and the number alone does not
distinguish them — it only correlates. The cap is therefore a guard, not a
proof. Above it, LOOK at the midpoint frame before overriding; below it, the
result has been acceptable every time so far. If a future seam passes the cap
and still ghosts, the fix is to look at what moved, not to tune the constant.

DO NOT ALIGN FIRST (measured, counter-intuitive)
------------------------------------------------
The obvious refinement — translate one frame onto the other so she lines up
before blending — makes the result WORSE. Measured across ski-demo's ten scene
boundaries it helped twice and hurt eight times, e.g. 01->02 went from 3.44%
to 6.96% after a 6px shift.

The reason: the alpha bbox centre is pulled around by her HANDS AND ARMS, which
move constantly, not by her head, which barely moves. HeyGen renders her in a
consistent frame position (`top` varies by ~4px across all eleven clips), so
there is no offset to correct — the apparent "25px shift" at scene 07->08 is her
arm rising, not the frame moving. Translating to match a gesture-driven centre
then misaligns her hair, shoulders and jacket, which are the large stable areas
that dominate the pixel count.

`--align` is available for a case where the two frames genuinely are offset
(different renders framed differently). Measure both ways before using it.

WHY NOT TRUE MORPHING
---------------------
A real morph (warping pixels along an optical-flow field) would need OpenCV,
which is not in `.claude/agent-tools/venv`. It would also break on precisely
the hard cases: teeth and fingers appearing where there was nothing to flow
from. Align-then-dissolve is honest about what it can do.

USAGE
-----
  # what IS the difference between two frames?
  fade_frames.py measure A.png B.png

  # emit the in-between frames
  fade_frames.py between A.png B.png --outdir frames/

  # the main case: fade a clip's last frame into a pose image, as alpha webm
  fade_frames.py tail sarah-scene-11-alpha.webm \
      --to Help_Videos/HeyGen/Sarah/sarah-rest-pose-full-alpha.png \
      --out closing-fade-alpha.webm

  # survey every scene boundary in a video folder (the diagnostic)
  fade_frames.py report "Customers/<Biz>/<store>/help-videos/final"

Importable:  from fade_frames import difference, build_fade
"""

import argparse
import glob
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

try:
    from PIL import Image, ImageChops, ImageMath
except ImportError:
    sys.exit("Pillow required:  .claude/agent-tools/venv/bin/python -m pip install pillow")

# ⚠ 25, NOT 30 — and this must match everywhere downstream.
#
# HeyGen renders avatars at 25fps and offers no way to change it, and OBS now
# records at 25 to match (RECORD_FPS in Master_Flows/Recorder/lib/obs.ts). Both
# sources are therefore 25. Compositing at 30 resampled BOTH of them, duplicating
# one frame in six in each — and before the OBS change it was worse in a
# different way: the demo was native 30 and only Sarah was resampled.
#
# Anything that converts seconds to frames must divide by THIS, not by a literal.
# `round(seconds * 30)` was scattered through the hold arithmetic and would make
# every hold 20% too long at 25.
FPS = 25
ALPHA_FLOOR = 20        # below this an alpha pixel is background, not subject
DIFF_NOISE = 8          # per-channel difference counted as "changed"


# --------------------------------------------------------------------------
# ffmpeg helpers.  ⚠ `-c:v libvpx-vp9` before EVERY -i that reads an alpha
# webm, or transparency is silently discarded while still reporting yuva420p.
# --------------------------------------------------------------------------

def _run(cmd, check=True):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"failed: {' '.join(cmd[:6])}…\n{r.stderr.strip()[-800:]}")
    return r


def duration(path):
    r = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
              "-of", "csv=p=0", path], check=False)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def frame_at(clip, out, index=0, last=False):
    """Extract one frame as RGBA png. `last=True` takes the final frame."""
    sel = "reverse,select=eq(n\\,0)" if last else f"select=eq(n\\,{index})"
    _run(["ffmpeg", "-y", "-v", "error", "-c:v", "libvpx-vp9", "-i", clip,
          "-vf", sel, "-frames:v", "1", "-c:v", "png", "-pix_fmt", "rgba", out])
    if not os.path.exists(out):
        sys.exit(f"could not extract a frame from {clip}")
    return out


def speech_end(clip):
    """When the audio last stops being silent, or None if it runs to the end."""
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", clip, "-af",
                        "silencedetect=n=-40dB:d=0.15", "-f", "null", "-"],
                       capture_output=True, text=True)
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)",
                                          r.stdout + r.stderr)]
    return starts[-1] if starts else None


# --------------------------------------------------------------------------
# measurement
# --------------------------------------------------------------------------

def _subject_mask(a, b):
    """Opaque in either frame — so appearing/disappearing pixels still count."""
    m = ImageChops.lighter(a.getchannel("A"), b.getchannel("A"))
    return m.point(lambda v: 255 if v > ALPHA_FLOOR else 0)


def _mask_area(mask):
    return sum(i * c for i, c in enumerate(mask.histogram())) / 255


def difference(a_img, b_img):
    """
    Return (mean_pct, changed_pct).

    mean_pct    mean absolute RGB difference over the subject, as % of 255.
                This is the number --per-step divides.
    changed_pct share of subject pixels differing by more than DIFF_NOISE.
                Reported because it is the more intuitive one to eyeball.
    """
    a = a_img.convert("RGBA")
    b = b_img.convert("RGBA")
    if a.size != b.size:
        b = b.resize(a.size, Image.LANCZOS)
    mask = _subject_mask(a, b)
    area = _mask_area(mask)
    if area == 0:
        return 0.0, 0.0
    d = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    total = sum(sum(i * c for i, c in enumerate(ImageChops.multiply(ch, mask).histogram()))
                for ch in d.split())
    ch = d.split()
    mx = ImageChops.multiply(ImageChops.lighter(ImageChops.lighter(ch[0], ch[1]), ch[2]), mask)
    changed = sum(c for i, c in enumerate(mx.histogram()) if i > DIFF_NOISE)
    return total / (3 * area) / 255 * 100, changed / area * 100


def silhouette(img):
    """(bbox, centre_x, top) of the subject, or None if the frame is empty."""
    a = img.convert("RGBA").getchannel("A").point(lambda v: 255 if v > ALPHA_FLOOR else 0)
    bb = a.getbbox()
    if not bb:
        return None, None, None
    return bb, (bb[0] + bb[2]) // 2, bb[1]


# --------------------------------------------------------------------------
# frame generation
# --------------------------------------------------------------------------

def _smoothstep(u):
    """Ease in and out. Linear reads mechanical — same finding as the morph."""
    return u * u * (3 - 2 * u)


def _unpremultiply(colour, alpha):
    """colour * 255 / alpha, clamped, with alpha==0 guarded to 0."""
    return ImageMath.lambda_eval(
        lambda k: k["convert"](
            k["min"](k["c"] * 255 / k["max"](k["a"], 1), 255), "L"),
        c=colour, a=alpha)


def _premultiplied_blend(a, b, t):
    """
    Blend in premultiplied alpha, then undo it.

    A straight `Image.blend` on RGBA mixes colour into fully transparent
    pixels, where RGB is undefined (usually black) — which shows up as a dark
    fringe around her edge. Premultiplying by alpha first, blending, then
    dividing back out keeps the edge clean.

    `ImageMath.lambda_eval` does the divide; PIL has no image-by-image
    division, and `ImageMath.eval` was removed in Pillow 12.
    """
    ar, ag, ab, aa = a.split()
    br, bg, bb, ba = b.split()

    out_a = Image.blend(aa, ba, t)
    out = []
    for ca, cb, na, nb in ((ar, br, aa, ba), (ag, bg, aa, ba), (ab, bb, aa, ba)):
        pre = Image.blend(ImageChops.multiply(ca, na), ImageChops.multiply(cb, nb), t)
        out.append(_unpremultiply(pre, out_a))

    return Image.merge("RGBA", (*out, out_a))


def _align(b, a):
    """Translate b so its subject centre sits where a's does."""
    _, acx, atop = silhouette(a)
    _, bcx, btop = silhouette(b)
    if None in (acx, bcx):
        return b, (0, 0)
    dx, dy = acx - bcx, atop - btop
    if dx == 0 and dy == 0:
        return b, (0, 0)
    shifted = Image.new("RGBA", b.size, (0, 0, 0, 0))
    shifted.paste(b, (dx, dy))
    return shifted, (dx, dy)


def build_fade(a_img, b_img, per_step=2.0, cap=5.0, align=False, no_cap=False):
    """
    Return (frames, info). `frames` is a list of PIL RGBA images strictly
    BETWEEN a and b — neither endpoint is included, so a caller can splice
    them in without duplicating either frame.
    """
    a = a_img.convert("RGBA")
    b = b_img.convert("RGBA")
    if a.size != b.size:
        b = b.resize(a.size, Image.LANCZOS)

    shift = (0, 0)
    if align:
        b, shift = _align(b, a)

    mean, changed = difference(a, b)
    info = {"mean_pct": mean, "changed_pct": changed, "shift": shift,
            "frames": 0, "refused": False, "reason": ""}

    if mean <= 0.05:
        info["reason"] = "frames are effectively identical — nothing to fade"
        return [], info

    if mean > cap and not no_cap:
        info["refused"] = True
        info["reason"] = (f"difference {mean:.1f}% exceeds the {cap:.1f}% cap — a "
                          f"crossfade here ghosts (see the module docstring). Fix "
                          f"the cut, or pass --no-cap and LOOK at the result.")
        return [], info

    n = max(1, math.ceil(mean / per_step))
    frames = [_premultiplied_blend(a, b, _smoothstep((i + 1) / (n + 1)))
              for i in range(n)]
    info["frames"] = n
    return frames, info


def frames_to_webm(frames, out, fps=FPS):
    """Encode RGBA frames to a VP9 alpha webm."""
    tmp = tempfile.mkdtemp(prefix="fade_")
    try:
        for i, f in enumerate(frames):
            f.save(os.path.join(tmp, f"f_{i:04d}.png"))
        _run(["ffmpeg", "-y", "-v", "error", "-framerate", str(fps),
              "-i", os.path.join(tmp, "f_%04d.png"),
              "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-lossless", "1",
              "-an", out])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _load(p):
    if not os.path.exists(p):
        sys.exit(f"missing: {p}")
    return Image.open(p).convert("RGBA")


def cmd_measure(a):
    x, y = _load(a.a), _load(a.b)
    mean, changed = difference(x, y)
    _, acx, atop = silhouette(x)
    _, bcx, btop = silhouette(y)
    n = max(1, math.ceil(mean / a.per_step)) if mean > 0.05 else 0
    print(f"  mean difference   {mean:6.2f}%")
    print(f"  pixels changed    {changed:6.1f}%")
    print(f"  subject offset    dx={acx - bcx if None not in (acx, bcx) else '?'}  "
          f"dy={atop - btop if None not in (atop, btop) else '?'}")
    print(f"  frames at {a.per_step}%/frame   {n}   ({n / FPS:.3f}s at {FPS}fps)")
    if mean > a.cap:
        print(f"  ⚠ ABOVE the {a.cap:.1f}% cap — fading here would ghost. Fix the cut.")


def cmd_between(a):
    frames, info = build_fade(_load(a.a), _load(a.b), a.per_step, a.cap,
                              align=a.align, no_cap=a.no_cap)
    _print_info(info)
    if not frames:
        sys.exit(1 if info["refused"] else 0)
    os.makedirs(a.outdir, exist_ok=True)
    for i, f in enumerate(frames):
        f.save(os.path.join(a.outdir, f"fade_{i:03d}.png"))
    print(f"  wrote {len(frames)} frames -> {a.outdir}/")


def cmd_tail(a):
    tmp = tempfile.mkdtemp(prefix="fade_tail_")
    try:
        last = frame_at(a.clip, os.path.join(tmp, "last.png"), last=True)
        frames, info = build_fade(_load(last), _load(a.to), a.per_step, a.cap,
                                  align=a.align, no_cap=a.no_cap)
        _print_info(info)
        if not frames:
            sys.exit(1 if info["refused"] else 0)
        frames_to_webm(frames, a.out)
        print(f"  wrote {len(frames)} frames ({len(frames)/FPS:.3f}s) -> {a.out}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _print_info(info):
    print(f"  mean difference   {info['mean_pct']:6.2f}%   "
          f"(pixels changed {info['changed_pct']:.1f}%)")
    if info["shift"] != (0, 0):
        print(f"  aligned by        dx={info['shift'][0]}  dy={info['shift'][1]}")
    if info["reason"]:
        mark = "⚠ REFUSED:" if info["refused"] else "  note:"
        print(f"  {mark} {info['reason']}")


def cmd_report(a):
    folder = a.folder.rstrip("/")
    clips = [f for f in sorted(glob.glob(os.path.join(scene_clips_dir(folder), "sarah-scene-*-alpha.webm")))
             if "paused" not in f]
    if not clips:
        sys.exit(f"no sarah-scene-*-alpha.webm in {folder}")
    tmp = tempfile.mkdtemp(prefix="fade_report_")
    try:
        print(f"  {'boundary':<26}{'mean Δ%':>9}{'px Δ':>8}{'frames':>8}   verdict")
        print("  " + "-" * 66)
        rows = []
        for i in range(len(clips) - 1):
            x = _load(frame_at(clips[i], os.path.join(tmp, f"{i}a.png"), last=True))
            y = _load(frame_at(clips[i + 1], os.path.join(tmp, f"{i}b.png"), index=0))
            frames, info = build_fade(x, y, a.per_step, a.cap, no_cap=False)
            m = info["mean_pct"]
            v = "FIX THE CUT" if info["refused"] else f"fade {len(frames)}f"
            n_a = os.path.basename(clips[i])[12:14]
            n_b = os.path.basename(clips[i + 1])[12:14]
            print(f"  scene {n_a} -> {n_b}{'':<14}{m:>8.2f}%{info['changed_pct']:>7.1f}%"
                  f"{len(frames):>8}   {v}")
            rows.append(m)
        print("  " + "-" * 66)
        print(f"  {'MEAN':<26}{sum(rows)/len(rows):>8.2f}%")
        print()
        print("  Reminder: a scene boundary is a hard cut by DESIGN — clips end on the")
        print("  rest pose and start mid-word. Fading a big one makes it worse. This")
        print("  table is for finding the small ones worth smoothing.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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
    ap = argparse.ArgumentParser(
        description="Generate morphed transition frames between two Sarah frames.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Frame count = ceil(difference-percent / --per-step), refused above --cap.")
    # Shared options live on the SUBPARSERS, so they can be typed after the
    # command (`measure a b --per-step 1`) where anyone would naturally put
    # them. On the top-level parser they would only work before it.
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--per-step", type=float, default=2.0,
                        help="one frame per this many percent of difference (default "
                             "2.0; 10 yields zero frames for real footage)")
    shared.add_argument("--cap", type=float, default=5.0,
                        help="refuse to fade above this percent difference (default 5.0)")
    shared.add_argument("--no-cap", action="store_true",
                        help="override the cap, then LOOK at the result")
    shared.add_argument("--align", action="store_true",
                        help="translate the second frame onto the first before blending. "
                             "OFF by default — measured to make things WORSE on 8 of 10 "
                             "ski-demo boundaries, because the bbox centre tracks her "
                             "HANDS, not her head (see the module docstring)")

    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("measure", parents=[shared],
                       help="print the difference between two frames")
    m.add_argument("a"); m.add_argument("b"); m.set_defaults(fn=cmd_measure)

    b = sub.add_parser("between", parents=[shared],
                       help="write the in-between frames as pngs")
    b.add_argument("a"); b.add_argument("b")
    b.add_argument("--outdir", required=True); b.set_defaults(fn=cmd_between)

    t = sub.add_parser("tail", parents=[shared],
                       help="fade a clip's LAST frame into a pose image")
    t.add_argument("clip"); t.add_argument("--to", required=True)
    t.add_argument("--out", required=True); t.set_defaults(fn=cmd_tail)

    r = sub.add_parser("report", parents=[shared],
                       help="survey every scene boundary in a final/ folder")
    r.add_argument("folder"); r.set_defaults(fn=cmd_report)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
