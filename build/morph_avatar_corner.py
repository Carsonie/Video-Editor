#!/usr/bin/env python3
"""
Build the centre -> corner avatar morph, and the corner element it lands on.

Sarah starts full-figure and centred on a square canvas, then over ~1.2s scales
down, reframes to head-and-shoulders, and travels to the lower-right corner.
Written 2026-08-15 after doing it by hand; see
`.claude/agents/6_end-customer-help-video-creations.md` -> "Sarah Opening" for
the reasoning behind every choice here.

WHY THIS IS PYTHON AND NOT AN FFMPEG FILTER GRAPH
-------------------------------------------------
Three things change together: the crop box, the output size, and the position.
ffmpeg cannot do that:
  * `crop` fixes w/h at filter init - it cannot change output size per frame,
    and the framing change is half the effect.
  * per-frame `scale` (eval=frame) feeding `overlay` produces a varying-size
    input that overlay handles badly.
A 1.2s transition is ~36 frames; compositing them directly is exact, keeps
alpha, and runs in seconds.

USAGE
-----
    python3 morph_avatar_corner.py --src sarah-intro-alpha.webm --outdir .

    # tune the landing spot / timing
    python3 morph_avatar_corner.py --src in.webm --outdir . \\
        --corner 300 --inset 30 --duration 1.5

Writes, into --outdir:
    <stem>-corner-<N>-alpha.webm      the static corner element
    <stem>-transition-to-corner.webm  the morph, canvas-sized, alpha

Both are VP9 with a real alpha channel. Remember that any later ffmpeg step
reading them MUST pass `-c:v libvpx-vp9` on decode or the transparency is
silently dropped (ffprobe will even report yuv420p).
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is required:  .claude/agent-tools/venv/bin/pip install pillow")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"command failed:\n  {' '.join(cmd)}\n{r.stderr[-800:]}")
    return r


def measure(src, at):
    """
    Find the subject in the source frame: full bounding box, and the shoulder
    line where the silhouette widens.

    Both matter. The subject is NOT centred in HeyGen's output - measured 31px
    off on the first build - so centring the *video* leaves her lopsided. And a
    corner avatar has to be cropped to head-and-shoulders BEFORE scaling, or it
    is just a tiny distant person in a mostly-empty box.
    """
    tmp = tempfile.mkdtemp()
    mask = os.path.join(tmp, "mask.png")
    run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-ss", str(at), "-i", src,
         "-vf", "alphaextract", "-frames:v", "1", "-update", "1", "-y", mask])
    im = Image.open(mask).convert("L")
    w, h = im.size
    px = im.load()

    rows = {}
    for y in range(0, h, 2):
        cols = [x for x in range(0, w, 3) if px[x, y] > 32]
        if cols:
            rows[y] = (min(cols), max(cols))
    if not rows:
        shutil.rmtree(tmp, ignore_errors=True)
        sys.exit("no subject found - is the alpha channel actually present? "
                 "(decode with -c:v libvpx-vp9 to check)")

    ys = sorted(rows)
    top, bottom = ys[0], ys[-1]
    left = min(v[0] for v in rows.values())
    right = max(v[1] for v in rows.values())

    # Shoulder line: first row below the head whose width exceeds 1.4x the
    # head's typical width. The head runs ~290-410px wide and the shoulders
    # jump past 600 - the step is unambiguous, so this beats eyeballing it.
    head_rows = [y for y in ys if y < top + (bottom - top) * 0.35]
    head_w = sorted(rows[y][1] - rows[y][0] for y in head_rows)[len(head_rows) // 2]
    shoulder = next((y for y in ys if y > top + 100 and
                     (rows[y][1] - rows[y][0]) > head_w * 1.4), top + (bottom - top) // 3)
    head_cx = (rows[ys[len(head_rows) // 2]][0] + rows[ys[len(head_rows) // 2]][1]) // 2

    shutil.rmtree(tmp, ignore_errors=True)
    return dict(w=w, h=h, top=top, bottom=bottom, left=left, right=right,
                shoulder=shoulder, head_cx=head_cx,
                subject_cx=(left + right) // 2)


def clamp_box(cx, cy, side, w, h):
    """A square crop centred on (cx, cy), nudged to stay inside the frame."""
    x = max(0, min(w - side, cx - side // 2))
    y = max(0, min(h - side, cy - side // 2))
    return (x, y, x + side, y + side)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="alpha WebM from HeyGen (type:avatar, output_format:webm)")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--canvas", type=int, default=1080)
    ap.add_argument("--corner", type=int, default=300, help="corner element size, px")
    ap.add_argument("--inset", type=int, default=0, help="margin from the corner (0 = flush)")
    ap.add_argument("--duration", type=float, default=1.2)
    # ⚠ 25, matching HeyGen's avatar output and the rest of the pipeline. This
    # default was 30 and was missed in the 2026-08-20 sweep because it is a
    # CLI default, not a literal in a filter string — the morph came out at
    # 30fps inside an otherwise-25fps opening.
    ap.add_argument("--fps", type=int, default=25)
    ap.add_argument("--measure-at", type=float, default=2.0, help="seconds into src to measure the pose")
    ap.add_argument("--reverse", action="store_true",
                    help="CORNER -> CENTRE instead of centre -> corner. The closing bookend: "
                         "Sarah grows back out of the corner as the background goes dark, "
                         "landing on the pose the opening began from. Same interpolation, "
                         "endpoints swapped — so the two moves are exact mirrors and cannot "
                         "drift apart.")
    ap.add_argument("--start-at", type=float, default=None,
                    help="seconds into src the morph begins (default: last <duration> of the clip)")
    a = ap.parse_args()

    m = measure(a.src, a.measure_at)
    print(f"  subject   x={m['left']}..{m['right']}  y={m['top']}..{m['bottom']}")
    print(f"  head cx={m['head_cx']}  (frame centre {m['w']//2}) | shoulder line y={m['shoulder']}")

    # Head + upper shoulders: from a little above the head down past the
    # shoulder line, squared off and centred on the HEAD's x, not the frame's.
    pad_above = int((m["shoulder"] - m["top"]) * 0.08)
    side = int((m["shoulder"] - m["top"] + pad_above) * 1.35)
    e_crop = clamp_box(m["head_cx"], m["top"] - pad_above + side // 2, side, m["w"], m["h"])
    print(f"  head+shoulders crop: {e_crop[2]-e_crop[0]}x{e_crop[3]-e_crop[1]} at ({e_crop[0]},{e_crop[1]})")

    # Start: the whole frame, fitted to canvas height, with the SUBJECT centred.
    s_crop = (0, 0, m["w"], m["h"])
    s_h = a.canvas
    s_w = round(s_h * m["w"] / m["h"])
    s_pos = (round(a.canvas / 2 - m["subject_cx"] * (s_w / m["w"])), 0)
    e_pos = (a.canvas - a.corner - a.inset, a.canvas - a.corner - a.inset)
    print(f"  start {s_w}x{s_h} at {s_pos}   ->   end {a.corner}x{a.corner} at {e_pos}")

    stem = os.path.splitext(os.path.basename(a.src))[0].replace("-alpha", "")
    outdir = a.outdir
    os.makedirs(outdir, exist_ok=True)

    # ---- the static corner element -------------------------------------
    corner_out = os.path.join(outdir, f"{stem}-corner-{a.corner}-alpha.webm")
    cw = e_crop[2] - e_crop[0]
    run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", a.src,
         "-filter_complex",
         f"[0:v]crop={cw}:{cw}:{e_crop[0]}:{e_crop[1]},scale={a.corner}:{a.corner},format=yuva420p",
         "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "1M", "-c:a", "libopus",
         "-y", corner_out])
    print(f"  wrote {corner_out}")

    # ---- the morph -------------------------------------------------------
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", a.src], capture_output=True, text=True).stdout.strip()
    # Forward: the morph runs at the END of the clip (she has finished the intro
    # and is about to move). Reversed: it runs at the START, because the closing
    # line begins in the corner and she travels out while still speaking.
    if a.start_at is not None:
        start = a.start_at
    elif a.reverse:
        start = 0.0
    else:
        start = max(0.0, float(dur) - a.duration)

    tmp = tempfile.mkdtemp()
    run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-ss", str(start), "-t", str(a.duration),
         "-i", a.src, "-vf", f"fps={a.fps}", "-pix_fmt", "rgba",
         os.path.join(tmp, "src_%04d.png")])
    frames = sorted(glob.glob(os.path.join(tmp, "src_*.png")))
    outd = os.path.join(tmp, "out")
    os.makedirs(outd, exist_ok=True)

    lerp = lambda p, q, t: p + (q - p) * t
    # The closing is the opening played backwards through the SAME maths, not a
    # second implementation — swap the endpoints and every frame mirrors exactly.
    if a.reverse:
        s_crop, e_crop = e_crop, s_crop
        s_pos, e_pos = e_pos, s_pos
        s_h, end_h = a.corner, s_h
    else:
        end_h = a.corner
    for i, f in enumerate(frames):
        u = i / max(1, len(frames) - 1)
        p = 3 * u * u - 2 * u * u * u          # smoothstep; linear reads mechanical
        box = tuple(round(lerp(s_crop[k], e_crop[k], p)) for k in range(4))
        h = round(lerp(s_h, end_h, p))
        bw, bh = box[2] - box[0], box[3] - box[1]
        # Width comes from the CROP's aspect. Lerping w and h independently
        # squashes her mid-move, because the crop aspect is changing too.
        w = max(2, round(h * bw / bh))
        pos = (round(lerp(s_pos[0], e_pos[0], p)), round(lerp(s_pos[1], e_pos[1], p)))
        img = Image.open(f).convert("RGBA").crop(box).resize((w, h), Image.LANCZOS)
        canvas = Image.new("RGBA", (a.canvas, a.canvas), (0, 0, 0, 0))
        canvas.alpha_composite(img, pos)
        canvas.save(os.path.join(outd, f"f_{i:04d}.png"))

    morph_out = os.path.join(outdir,
        f"{stem}-transition-to-{'centre' if a.reverse else 'corner'}.webm")
    run(["ffmpeg", "-v", "error", "-framerate", str(a.fps), "-i", os.path.join(outd, "f_%04d.png"),
         "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "2M", "-y", morph_out])
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"  wrote {morph_out}  ({len(frames)} frames, {a.duration}s)")

    print("\n  compose over a demo scene (PAD sampled from the clip's own edge):")
    print(f"""    ffmpeg -i scene.mp4 -c:v libvpx-vp9 -i {os.path.basename(morph_out)} \\
      -itsoffset {a.duration} -c:v libvpx-vp9 -i {os.path.basename(corner_out)} \\
      -filter_complex "[0:v]scale={a.canvas}:-2,pad={a.canvas}:{a.canvas}:0:({a.canvas}-ih)/2:color=$PAD,setsar=1[bg];\\
    [bg][1:v]overlay=x=0:y=0:enable='lt(t,{a.duration})'[x];\\
    [x][2:v]overlay=x={e_pos[0]}:y={e_pos[1]}:enable='gte(t,{a.duration})',format=yuv420p" out.mp4""")


if __name__ == "__main__":
    main()
