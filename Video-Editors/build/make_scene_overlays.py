#!/usr/bin/env python3
"""
Build ONE corner-composited avatar clip PER SCENE, versioned, so the editor can
lay each scene's own narration over its own footage.

    python3 make_scene_overlays.py "<store>/help-videos/final"

WHY THIS EXISTS
---------------
The layered viewer takes a single overlay file, so reviewing a cut meant laying
ONE narration clip over every scene: scene 5's footage with scene 12's voice.
The picture changed as you clicked through and the audio never did, which makes
the one thing worth checking — does this mouth match these words — impossible.

WHY THEY ARE VERSIONED
----------------------
`scenes/sarah-scene-NN-alpha.webm` is overwritten by name on every render and
carries no record of which script it came from. Three things have to agree
frame for frame — the segment, the avatar overlay and its audio — and only the
segments were versioned. A set built here is stamped, and each set records the
SHA of every line it was built from, so a later mismatch is detectable instead
of merely possible.

    sarah_clips/scene_overlays/v1/sarah-scene-01-corner-alpha.webm
    sarah_clips/scene_overlays/v1/manifest.json

WHAT "CORNER" MEANS
-------------------
A raw HeyGen clip is full-frame 1920x1080. In the finished video the avatar is
cropped head-and-shoulders and sits flush in the lower-right at CORNER px on a
CANVAS square. These are that composite — the same one assemble_video.py builds
in its temp dir — so the preview is the real arrangement rather than a guess.
"""
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# paths.py lives in shared/ here, not beside these tools. In Basic_E2E_Testing
# it sat in this same folder; the flatten moved it down to where the editors
# import it from, and one home for it beats two that drift.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "shared"))
import assemble_video as av
import paths as PTH


def main():
    if len(sys.argv) < 2:
        sys.exit('usage: make_scene_overlays.py "<store>/help-videos/final"')
    F = os.path.abspath(sys.argv[1])
    cfg_path = av.script_path(F)
    cfg = json.load(open(cfg_path))
    root = os.path.join(av.sarah_dir(F), "scene_overlays")
    os.makedirs(root, exist_ok=True)

    # Next version, one higher than anything already there — same convention the
    # segment cuts use, so an earlier set is never destroyed by a rebuild.
    have = [int(m.group(1)) for d in os.listdir(root)
            for m in [re.match(r"^v(\d+)$", d)] if m]
    ver = (max(have) + 1) if have else 1
    outdir = os.path.join(root, f"v{ver}")
    os.makedirs(outdir, exist_ok=True)
    print(f"  building scene overlays v{ver} -> {os.path.relpath(outdir, F)}")

    x = y = av.CANVAS - av.CORNER
    entries, missing = [], []
    for s in cfg["scenes"]:
        n = s["n"]
        # RESOLVED, never a hardcoded folder. This read `<final>/scenes/` by
        # name until 2026-08-22, which meant it could not see a narration clip
        # in a scene's own sandbox folder — and a missing folder does not error,
        # it reads as "no files", so every scene came back missing and the store
        # looked empty. paths.narration() checks sandbox, then dev, then flat.
        src = PTH.narration(F, n, s.get("label"))
        if not src or not os.path.isfile(src):
            missing.append(n)
            continue
        box = av.corner_crop(src)
        cw = box[2] - box[0]
        dst = os.path.join(outdir, f"sarah-scene-{n:02d}-corner-alpha.webm")
        av.run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", src, "-filter_complex",
                f"color=c=black@0.0:s={av.CANVAS}x{av.CANVAS}:r={av.FPS},format=yuva420p[bg];"
                f"[0:v]crop={cw}:{cw}:{box[0]}:{box[1]},scale={av.CORNER}:{av.CORNER},"
                f"fps={av.FPS},format=yuva420p[c];"
                f"[bg][c]overlay=x={x}:y={y}:shortest=1,format=yuva420p[v]",
                "-map", "[v]", "-map", "0:a", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
                "-b:v", "2M", "-c:a", "libopus", "-y", dst])
        dur = float(av.dur(dst, True))
        entries.append({
            "n": n, "label": s.get("label", ""),
            "file": os.path.basename(dst), "duration": round(dur, 3),
            # The LINE's hash, not the file's: it is what identifies the render.
            # A changed line with an unchanged filename is the exact failure this
            # is here to make visible.
            "line_sha1": hashlib.sha1(s["line"].encode("utf-8")).hexdigest()[:12],
            "words": len(s["line"].split()),
            # WHICH layer this clip came from. A sandbox override silently
            # entering a build is the one failure this layout can introduce, and
            # it is invisible in the picture.
            "source": PTH.source_of(F, src),
            "source_file": os.path.relpath(src, F)})
        print(f"    {n:>2} {s.get('label',''):<26} {dur:>6.2f}s   "
              f"[{PTH.source_of(F, src)}]")

    manifest = {
        "version": ver,
        "built": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
        "canvas": av.CANVAS, "corner": av.CORNER, "fps": av.FPS,
        # Per scene now, because they no longer have to share one folder.
        "source_layers": sorted({e["source"] for e in entries}),
        "_note": ("One corner-composited avatar clip per scene, with its audio, so a "
                  "scene's footage can be reviewed against its OWN narration. `line_sha1` "
                  "is the SHA of the line each clip was rendered from — compare it with "
                  "script.json to tell whether a set is still current, which a filename "
                  "cannot say because renders overwrite by name."),
        "scenes": entries}
    with open(os.path.join(outdir, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)

    print(f"\n  {len(entries)} overlay(s) written, manifest alongside them")
    if missing:
        print(f"  ⚠ no narration clip for scene(s) {missing} — they will have no overlay")


main()
