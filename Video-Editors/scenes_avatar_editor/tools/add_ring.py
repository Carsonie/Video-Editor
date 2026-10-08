#!/usr/bin/env python3
"""
Put a click ring around an element in a scene that was already recorded.

    python3 add_ring.py <scene-root> --scene 17 --frame 466 --at 700,1085 --preview
    python3 add_ring.py <scene-root> --scene 17 --frame 466 --box 224,1036,2079,1135
    python3 add_ring.py <scene-root> --scene 17 --reapply

<scene-root> is the recipe folder — the one holding script.json, segments/ and
sandbox/.

⚠ THE RECORDER CANNOT DO THIS, WHICH IS WHY THIS EXISTS.
`instrumentClicks` rings what it CLICKS, live, at record time, and the ring is
burnt into the pixels (see ring_check.py). An element the flow only talks about
— special-skis' Attributes box, whose own narration says "you can skip over
this" — is never clicked, so it never gets a ring. Re-recording to add one
throws away every edit made since. This draws the same ring afterwards instead.

⚠ IT WRITES THE CUT IN segments/, NOT THE CLIP IN sandbox/.
sae_vtt_sync rebuilds a sandbox clip from `cut + voice` whenever either moves,
so a ring painted on the clip is wiped by the next sync with nothing to say it
ever existed. The cut is upstream of that mux, so the ring survives. Run the
sync afterwards to carry it through to the clip and the film.

⚠ A RE-CUT STILL WIPES IT, AND THAT IS WHAT rings.json IS FOR.
stretch_scenes.py re-cuts a scene from the master whenever its src_in/src_out
pair moves, which throws the ring away. Every ring is therefore recorded in
`rings.json` beside script.json, and `--reapply` paints the lot back. A scene
born from a SPLIT has no src_in/src_out and cannot be re-cut, so its rings are
safe either way — but it is not worth remembering which is which.

THE RING IS THE RECORDER'S RING, NOT A NEW ONE
----------------------------------------------
Copied from Core/lib/clickPace.ts:152 so post-production matches record time:

    outline: 3px solid #FFD400        clickPace.ts:152
    outline-offset: 2px               clickPace.ts:153
    hold 750ms                        record_flow.ts:494  CLICK_HIGHLIGHT_MS
    no fill, ever                     record_flow.ts:506  CLICK_HIGHLIGHT_FILL=0

⚠ THOSE ARE CSS PIXELS AND THE CAPTURE IS NOT 1:1. The browser runs at 1152
wide and the capture is 2304, so every ring on screen is 6px, not 3px. The
scale is measured off the frame rather than assumed, because a capture at a
different width would silently get a hairline.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

from PIL import Image, ImageDraw

RING_RGB = (255, 212, 0)      # #FFD400 — clickPace.ts:152
STROKE_CSS = 3                # px, clickPace.ts:152
OFFSET_CSS = 2                # px, clickPace.ts:153
HOLD_MS = 750                 # record_flow.ts:494
RADIUS_CSS = 9                # the inputs' own corner, measured off a capture
BROWSER_W = 1152              # what the flows record at; see ring_check.py


def sh(cmd):
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def probe(path, entries, stream=True):
    cmd = ["ffprobe", "-v", "error"]
    if stream:
        cmd += ["-select_streams", "v:0"]
    cmd += ["-show_entries", ("stream=" if stream else "format=") + entries,
            "-of", "csv=p=0", path]
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


# ── WHERE THINGS LIVE, ASKED RATHER THAN ASSUMED ──────────────────────────
#
# ⚠⚠ THIS FILE USED TO HARDCODE `root/script.json`, `root/rings.json`,
# `root/segments` AND `root/sandbox`, AND ALL FOUR MOVED. The 2026-09-22
# refactor put a recipe on `0_master/ 1_cuts/ 2_scenes/ 3_voice/ …`, and
# 2026-09-23 made the voice folder the one source of truth for the script. So
# on picklist this tool had already been finding nothing, and on special-skis
# it broke the moment that folder was converted (2026-10-07).
#
# ⚠ IT FAILED BY FINDING NOTHING, NOT BY ERRORING. `--reapply` with no
# rings.json loads `{"rings": []}` and paints nothing, reporting success. That
# is the shape of bug this repo keeps paying for, so the resolution is shared
# rather than copied: editor_base.paths is THE answer when it can be imported,
# and the fallback below only exists for running this file somewhere that
# cannot see the Video-Editors package.
#
# ⚠ TWO WALKS, BECAUSE THIS FILE HAS LIVED IN TWO PLACES. It was
# `Customers/<biz>/<store>/help-videos/TOOLS/`, five levels under the repo root
# with `Video-Editors/` as a SIBLING; on 2026-10-08 it moved to
# `Video-Editors/scenes_avatar_editor/tools/`, where `editor_base` is a plain
# two levels up. The old range(3, 8) still happened to hit the new home — tools
# -> scenes_avatar_editor -> Video-Editors -> Video-Editor, then joining
# "Video-Editors" lands back inside — which is luck, not design, and luck that
# would evaporate the next time this folder moved one level.
_PATHS = None
_here = os.path.dirname(os.path.abspath(__file__))
_tries = []
for _up in range(0, 8):
    _base = os.path.abspath(os.path.join(_here, *[".."] * _up))
    _tries.append(_base)                       # editor_base sitting right here
    _tries.append(os.path.join(_base, "Video-Editors"))   # ...or beside us
for _cand in _tries:
    if os.path.isdir(os.path.join(_cand, "editor_base")):
        sys.path.insert(0, _cand)
        try:
            from editor_base import paths as _PATHS      # noqa: E402
        except Exception:
            _PATHS = None
        break


def _first(root, *rels):
    """The first of these that exists; otherwise the first one, to name in an error."""
    for r in rels:
        p = os.path.join(root, r)
        if os.path.exists(p):
            return p
    return os.path.join(root, rels[0])


def script_path(root):
    """script.json — the voice folder first, exactly as editor_base resolves it."""
    if _PATHS:
        return _PATHS.script(root)
    v = _first(root, "3_voice", "voice")
    for c in (os.path.join(v, "script.json"),
              os.path.join(root, "2_scenes", "sandbox", "script.json"),
              os.path.join(root, "sandbox", "script.json"),
              os.path.join(root, "script.json")):
        if os.path.isfile(c):
            return c
    return os.path.join(v, "script.json")


def rings_path(root):
    """rings.json — BESIDE script.json, which is the rule this tool documents."""
    return os.path.join(os.path.dirname(script_path(root)), "rings.json")


def segments_dir(root):
    """The cuts — 1_cuts/segments/ in the new shape, segments/ in the old."""
    return _first(root, os.path.join("1_cuts", "segments"), "segments")


def sandbox_dir(root):
    """The scene folders — 2_scenes/sandbox/ in the new shape, sandbox/ in the old."""
    if _PATHS:
        return _PATHS.sandbox_root(root)
    return _first(root, os.path.join("2_scenes", "sandbox"), "sandbox")


def scene_label(root, n):
    """The label as script.json spells it — the folder names are built from it."""
    with open(script_path(root)) as fh:
        for s in json.load(fh)["scenes"]:
            if s["n"] == n:
                return s["label"]
    return None


def find_cut(root, n, label):
    """
    The scene's cut in segments/, whatever naming it happens to carry.

    ⚠ MATCHED BY PREFIX, NOT BUILT FROM A TEMPLATE. A cut is named for how it
    was made — `<NN>-<label>-<factor>x<offset>-<fps>fps.mp4` off the master,
    `<NN>-<label>-split-<fps>fps.mp4` from a split — and guessing the wrong one
    silently finds nothing.

    ⚠ AND A SCENE CAN HAVE MORE THAN ONE, ONLY ONE OF WHICH IS LIVE. A split
    leaves the pre-split cut in place: special-skis scene 16 carries BOTH
    `16-item-details-f1.5555-154.33_177.86-25fps.mp4` (34.80s, dead since the
    2026-09-22 split) and `16-item-details-split-25fps.mp4` (15.16s, live).
    Sorting picks the dead one, because "f" sorts before "s" — a ring would
    have gone into a file nothing reads, and nothing would have said so.

    `sandbox/<NN>-<label>/.sync.json` names the cut the clip was actually built
    from. That is the answer; the prefix scan is only the fallback, and it
    prefers whichever cut is the same length as the clip.
    """
    segs = segments_dir(root)
    if not os.path.isdir(segs):
        return None
    sb = os.path.join(sandbox_dir(root), f"{n:02d}-{label}" if label else "")
    rec = os.path.join(sb, ".sync.json")
    if os.path.isfile(rec):
        try:
            named = json.load(open(rec)).get("cut")
            if named and os.path.isfile(os.path.join(segs, named)):
                return os.path.join(segs, named)
        except (ValueError, OSError):
            pass
    pre = f"{n:02d}-{label}-" if label else f"{n:02d}-"
    hits = sorted(f for f in os.listdir(segs)
                  if f.startswith(pre) and f.endswith(".mp4"))
    if not hits:
        return None
    clip = os.path.join(sb, "segment.mp4")
    if len(hits) > 1 and os.path.isfile(clip):
        want = probe(clip, "duration", stream=False)
        same = [f for f in hits
                if probe(os.path.join(segs, f), "duration", stream=False) == want]
        if len(same) == 1:
            return os.path.join(segs, same[0])
        sys.exit(f"{len(hits)} cuts match scene {n} and none is clearly the "
                 f"live one: {', '.join(hits)} — say which with --cut")
    return os.path.join(segs, hits[0])


def frame_png(video, n, dst):
    sh(["ffmpeg", "-v", "error", "-y", "-i", video,
        "-vf", rf"select=eq(n\,{n})", "-vsync", "0", "-frames:v", "1", dst])
    if not os.path.isfile(dst):
        sys.exit(f"frame {n} is past the end of {os.path.basename(video)}")
    return dst


def box_at(png, x, y, thresh=45):
    """
    The element under a point, found by its own border.

    ⚠ BY THE BORDER, NOT BY THE FILL. These forms draw an input as a 1-2px
    light outline on a ground barely lighter than the page, so a flood fill
    from the middle runs straight through the edge and swallows the form. The
    four nearest light runs out from the seed point ARE the box.
    """
    im = Image.open(png).convert("RGB")
    px, (W, H) = im.load(), im.size
    lit = lambda a, b: sum(px[a, b]) / 3 > thresh

    def walk(dx, dy):
        """
        ⚠ THROUGH the border run, not to its first pixel. A border is 2-4px
        thick here, and stopping on the near edge puts the ring inside the
        element's own outline instead of 2px outside it, where CSS draws one.
        """
        cx, cy = x, y
        while 0 <= cx + dx < W and 0 <= cy + dy < H:
            cx, cy = cx + dx, cy + dy
            if lit(cx, cy):
                while (0 <= cx + dx < W and 0 <= cy + dy < H
                       and lit(cx + dx, cy + dy)):
                    cx, cy = cx + dx, cy + dy
                return cx if dx else cy
        return None

    left, right = walk(-1, 0), walk(1, 0)
    top, bottom = walk(0, -1), walk(0, 1)
    if None in (left, right, top, bottom):
        sys.exit(f"no border found around {x},{y} — pass --box instead")
    return left, top, right, bottom


def ring_overlay(size, box, scale, dst):
    stroke = max(1, round(STROKE_CSS * scale))
    off = round(OFFSET_CSS * scale)
    x0, y0, x1, y1 = box
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle(
        [x0 - off, y0 - off, x1 + off, y1 + off],
        radius=round(RADIUS_CSS * scale) + off,
        outline=RING_RGB + (255,), width=stroke)
    im.save(dst)
    return stroke


def yellow_count(png, box, pad=12):
    im = Image.open(png).convert("RGB")
    px = im.load()
    x0, y0, x1, y1 = box
    n = 0
    for y in range(max(0, y0 - pad), min(im.size[1], y1 + pad)):
        for x in range(max(0, x0 - pad), min(im.size[0], x1 + pad)):
            r, g, b = px[x, y]
            if r > 200 and 170 < g < 235 and b < 80:
                n += 1
    return n


def load_rings(root):
    p = rings_path(root)
    return json.load(open(p)) if os.path.isfile(p) else {"rings": []}


def burn(root, n, label, cut, rings, work, quiet=False):
    """
    Paint every ring for this scene onto its cut, in one re-encode.

    ⚠ ONE PASS FOR ALL OF THEM. Each pass is a full h264 re-encode, so ringing
    four elements in four runs puts the scene through four generations of loss.
    They are composited together instead, and --reapply leans on the same thing.
    """
    W, H = (int(v) for v in probe(cut, "width,height").split(","))
    scale = W / BROWSER_W
    fps = eval(probe(cut, "r_frame_rate") or "25/1")  # "25/1" -> 25.0
    before = probe(cut, "nb_frames") or "?"

    chain, inputs = [], []
    for i, r in enumerate(rings):
        png = os.path.join(work, f"ring{i}.png")
        ring_overlay((W, H), tuple(r["box"]), scale, png)
        inputs += ["-i", png]
        last = "0:v" if i == 0 else f"v{i - 1}"
        hold = max(1, round(r.get("hold_ms", HOLD_MS) / 1000 * fps))
        a, b = r["frame"], r["frame"] + hold - 1
        chain.append(f"[{last}][{i + 1}:v]overlay=0:0:"
                     f"enable='between(n\\,{a}\\,{b})'[v{i}]")
    out = os.path.join(work, "ringed.mp4")
    sh(["ffmpeg", "-v", "error", "-y", "-i", cut, *inputs,
        "-filter_complex", ";".join(chain), "-map", f"[v{len(rings) - 1}]",
        "-c:v", "libx264", "-crf", "16", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-r", str(fps), out])

    after = probe(out, "nb_frames") or "?"
    if before != "?" and after != before:
        sys.exit(f"REFUSED: {before} frames in, {after} out — the cut would shift")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bk = os.path.join(root, "z_History", f"ring-{stamp}")
    os.makedirs(bk, exist_ok=True)
    shutil.copy2(cut, bk)
    shutil.move(out, cut)
    if not quiet:
        print(f"  cut        {os.path.basename(cut)} — {len(rings)} ring(s), "
              f"{before} frames unchanged")
        print(f"  backup     z_History/ring-{stamp}/")
    return fps, scale


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="the recipe folder holding script.json")
    ap.add_argument("--scene", type=int, required=True)
    ap.add_argument("--frame", type=int, help="scene-local frame the ring starts on")
    ap.add_argument("--at", help="X,Y on the element — its box is measured for you")
    ap.add_argument("--box", help="x0,y0,x1,y1 — skips the measuring")
    ap.add_argument("--hold-ms", type=int, default=HOLD_MS)
    ap.add_argument("--preview", action="store_true",
                    help="write a PNG and change no video")
    ap.add_argument("--reapply", action="store_true",
                    help="repaint every ring already in rings.json")
    a = ap.parse_args()

    keep = False
    root = os.path.abspath(a.root)
    if not os.path.isfile(script_path(root)):
        sys.exit(f"no script.json in {root} — that is not a recipe folder")
    label = scene_label(root, a.scene)
    cut = find_cut(root, a.scene, label)
    if not cut:
        sys.exit(f"no cut in segments/ for scene {a.scene} ({label})")

    # ⚠ NOT INSIDE THE RECIPE FOLDER. A scratch dir there is picked up by the
    # tools that walk help-videos/* looking for scenes, and a preview written
    # into it was deleted by this function's own cleanup a line later.
    work = tempfile.mkdtemp(prefix="ring_")
    store = load_rings(root)
    mine = [r for r in store["rings"] if r["scene"] == a.scene]

    try:
        if a.reapply:
            if not mine:
                sys.exit(f"nothing recorded for scene {a.scene} in rings.json")
            print(f"  scene {a.scene} {label} — reapplying {len(mine)} ring(s)")
            burn(root, a.scene, label, cut, mine, work)
            return

        if a.frame is None or not (a.at or a.box):
            sys.exit("need --frame and one of --at X,Y / --box x0,y0,x1,y1")

        png = frame_png(cut, a.frame, os.path.join(work, "frame.png"))
        if a.box:
            box = tuple(int(v) for v in a.box.split(","))
        else:
            x, y = (int(v) for v in a.at.split(","))
            box = box_at(png, x, y)
        print(f"  scene {a.scene} {label}  frame {a.frame}")
        print(f"  box        {box[0]},{box[1]} -> {box[2]},{box[3]}  "
              f"({box[2] - box[0]}x{box[3] - box[1]})")

        if a.preview:
            W, H = Image.open(png).size
            over = ring_overlay((W, H), box, W / BROWSER_W,
                                os.path.join(work, "ring.png"))
            base = Image.open(png).convert("RGBA")
            base.alpha_composite(Image.open(os.path.join(work, "ring.png")))
            out = os.path.join(work, f"preview-{a.scene}-{a.frame}.png")
            base.convert("RGB").save(out)
            print(f"  stroke     {over}px")
            print(f"  PREVIEW    {out}   (no video was changed)")
            keep = True          # the caller has to be able to open it
            return

        entry = {"scene": a.scene, "label": label, "frame": a.frame,
                 "box": list(box), "hold_ms": a.hold_ms,
                 "added": datetime.now().isoformat(timespec="seconds")}
        rings = mine + [entry]
        fps, _ = burn(root, a.scene, label, cut, rings, work)

        store["rings"] = [r for r in store["rings"] if r["scene"] != a.scene] + rings
        with open(rings_path(root), "w") as fh:
            json.dump(store, fh, indent=1)

        hold = max(1, round(a.hold_ms / 1000 * fps))
        last = a.frame + hold - 1
        print(f"  frames     {a.frame}-{last}  ({a.hold_ms}ms at {fps:g}fps)")
        for n, want in ((a.frame - 1, False), (a.frame, True),
                        (last, True), (last + 1, False)):
            if n < 0:
                continue
            try:
                p = frame_png(cut, n, os.path.join(work, f"v{n}.png"))
            except SystemExit:
                continue
            got = yellow_count(p, box) > 500
            mark = "ok" if got == want else "WRONG"
            print(f"  verify     frame {n}: "
                  f"{'ring' if got else 'clean':>5}  {mark}")
        print("  rings.json updated — run sae_vtt_sync --apply to carry it "
              "into the clip and the film")
    finally:
        if not keep:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
