#!/usr/bin/env python3
"""
Export the OPENING and CLOSING as standalone mp4s, from exactly the parts
assemble_video.py composites — so what is exported is what ships.

They are the reusable half of a help video: identical for every store bar the
words. Having them as flat mp4s makes them reviewable on their own, and gives
the other three stores something to look at before paying for their own renders.
"""
import os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# paths.py lives in shared/ here, not beside these tools. In Basic_E2E_Testing
# it sat in this same folder; the flatten moved it down to where the editors
# import it from, and one home for it beats two that drift.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "shared"))
from morph_avatar_corner import measure
import assemble_video as av
import paths as PTH

if len(sys.argv) < 2:
    sys.exit("usage: export_bookends.py \"<store>/help-videos/final\"")
F = os.path.abspath(sys.argv[1])
OD = av.sarah_dir(F)
CANVAS, CORNER, FPS = av.CANVAS, av.CORNER, av.FPS
PAD = "0x232323"          # sampled from this store's own footage by assemble_video
tmp = tempfile.mkdtemp(prefix="bookends_")
run = av.run


def with_audio(path, tag):
    """
    Guarantee an audio stream. The morph clips are written video-only, and the
    concat demuxer will not join a silent part to a voiced one — it drops the
    track, and the flatten step then fails on `-map 1:a`. Give every part a
    track so the join is uniform.
    """
    has = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a",
                          "-show_entries", "stream=codec_type", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.strip()
    if has:
        return path
    out = f"{tmp}/{tag}_wa.webm"
    d = av.dur(path, True)
    run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", path,
         "-f", "lavfi", "-t", f"{d:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "libopus",
         "-y", out])
    return out


def to_sandbox(front_webm, rear_mp4, folder):
    """
    Put a bookend into the sandbox as a SCENE-SHAPED pair.

    The editor lays an alpha overlay over an mp4 base, which is exactly what a
    bookend already is — Sarah's front track over a background track. Dropping
    the two in as `avatar.webm` + `segment.mp4` makes the opening and closing
    reviewable with the same controls, audio and frame stepping as any scene,
    instead of only ever as a flattened mp4 that cannot be taken apart.
    """
    os.makedirs(folder, exist_ok=True)
    shutil.copy2(front_webm, os.path.join(folder, "avatar.webm"))
    shutil.copy2(rear_mp4, os.path.join(folder, "segment.mp4"))
    print(f"    -> {os.path.basename(folder)}/  segment.mp4 + avatar.webm")


def flatten(front_parts, rear, out, label, sandbox=None):
    """Composite an alpha front track over an opaque rear, exactly as the build does."""
    front_parts = [with_audio(p, f"{label}{i}") for i, p in enumerate(front_parts)]
    lst = f"{tmp}/{label}_front.txt"
    open(lst, "w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in front_parts))
    front = f"{tmp}/{label}_front.webm"
    run(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0", "-c:v", "libvpx-vp9",
         "-i", lst, "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "2M",
         "-c:a", "libopus", "-y", front])
    # ⚠ -c:v libvpx-vp9 BEFORE -i, or the alpha is silently flattened to black.
    run(["ffmpeg", "-v", "error", "-i", rear, "-c:v", "libvpx-vp9", "-i", front,
         "-filter_complex", "[0:v][1:v]overlay=0:0:shortest=1,format=yuv420p[v]",
         "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-crf", "18",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart",
         "-y", out])
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", out], capture_output=True, text=True).stdout.strip()
    print(f"  {os.path.basename(out)}  {float(d):.2f}s")
    if sandbox:
        to_sandbox(front, rear, sandbox)


# ---- OPENING: Sarah centred on dark, then the morph down into the corner ----
intro = f"{OD}/sarah-intro-1152-alpha.webm"
bridge_corner = f"{OD}/sarah-bridge-corner-{CORNER}-alpha.webm"
morph_in = f"{OD}/sarah-bridge-transition-to-corner.webm"
x = y = CANVAS - CORNER
bcorner = f"{tmp}/open_corner.webm"
run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", bridge_corner, "-filter_complex",
     f"color=c=black@0.0:s={CANVAS}x{CANVAS}:r={FPS},format=yuva420p[bg];"
     f"[0:v]scale={CORNER}:{CORNER},fps={FPS},format=yuva420p[c];"
     f"[bg][c]overlay=x={x}:y={y}:shortest=1,format=yuva420p[v]",
     "-map", "[v]", "-map", "0:a", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
     "-b:v", "2M", "-c:a", "libopus", "-y", bcorner])
front_open = [intro, morph_in, bcorner]
total_open = sum(av.dur(p, True) for p in front_open)
rear_open = f"{tmp}/open_rear.mp4"
run(["ffmpeg", "-v", "error", "-f", "lavfi", "-t", f"{total_open:.3f}",
     "-i", f"color=c={PAD}:s={CANVAS}x{CANVAS}:r={FPS}",
     "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", "-y", rear_open])
flatten(front_open, rear_open, f"{OD}/OPENING.mp4", "open",
        sandbox=os.path.join(F, "sandbox", "00-opening"))

# ---- CLOSING: corner -> centre, the close-out line, then the rest pose -------
# GLOB, do not name. The reverse morph was rebuilt from the idle clip on
# 2026-08-22 (its old source had Sarah still speaking, so her mouth moved in
# silence) and its filename changed with its source. assemble_video.py already
# globs for exactly this reason; this file hardcoded the dead name.
import glob as _g
_m = _g.glob(os.path.join(OD, "*-transition-to-centre.webm"))
if not _m:
    sys.exit(f"  no closing morph (*-transition-to-centre.webm) in {OD}")
morph_out = _m[0]
closeout = f"{OD}/sarah-closeout-alpha.webm"
# RESOLVED, not joined. `scenes/` stopped existing at the dev restructure and
# this line kept pointing at it — the exact hardcoded-folder failure paths.py
# was written to end, still lurking in a tool nobody had re-run since.
# The morph's source is the LAST scene's narration, whichever scene that is.
# The close-out must be matched against the SAME render the morph was cut from
# or her head jumps at the join. The morph is named for its source, so that is
# derivable rather than guessed.
_stem = os.path.basename(morph_out).replace("-transition-to-centre.webm", "")
_src = next((c for c in (os.path.join(OD, f"{_stem}-alpha.webm"),
                         os.path.join(F, "sarah_clips", f"{_stem}-alpha.webm"))
             if os.path.isfile(c)), None)
if not _src:
    sys.exit(f"  morph {os.path.basename(morph_out)} names a source {_stem}-alpha.webm "
             f"that is not beside it")
src_m = measure(_src, max(0.0, av.dur(_src, True) - 1.0))
co_m = measure(closeout, min(0.6, av.dur(closeout, True) / 2))
k = CANVAS / src_m["h"]
head_x = round(CANVAS / 2 - src_m["subject_cx"] * k) + src_m["head_cx"] * k
head_y = src_m["top"] * k
sc = k * ((src_m["shoulder"] - src_m["top"]) / (co_m["shoulder"] - co_m["top"]))
cw, ch = round(co_m["w"] * sc), round(co_m["h"] * sc)
cx, cy = round(head_x - co_m["head_cx"] * sc), round(head_y - co_m["top"] * sc)
fco = f"{tmp}/close_line.webm"
run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", closeout, "-filter_complex",
     f"color=c=black@0.0:s={CANVAS}x{CANVAS}:r={FPS},format=yuva420p[bg];"
     f"[0:v]scale={cw}:{ch},fps={FPS},format=yuva420p[c];"
     f"[bg][c]overlay=x={cx}:y={cy}:shortest=1,format=yuva420p[v]",
     "-map", "[v]", "-map", "0:a", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
     "-b:v", "2M", "-c:a", "libopus", "-y", fco])
frest = f"{tmp}/close_rest.webm"
run(["ffmpeg", "-v", "error", "-loop", "1", "-t", f"{av.END_HOLD:.3f}", "-i", av.REST_POSE,
     "-f", "lavfi", "-t", f"{av.END_HOLD:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
     "-filter_complex",
     f"color=c=black@0.0:s={CANVAS}x{CANVAS}:r={FPS},format=yuva420p[bg];"
     f"[0:v]scale=-2:{CANVAS},fps={FPS},format=yuva420p[c];"
     f"[bg][c]overlay=x=(W-w)/2:y=0:shortest=1,format=yuva420p[v]",
     "-map", "[v]", "-map", "1:a", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
     "-b:v", "2M", "-c:a", "libopus", "-y", frest])
front_close = [morph_out, fco, frest]
total_close = sum(av.dur(p, True) for p in front_close)
rear_close = f"{tmp}/close_rear.mp4"
run(["ffmpeg", "-v", "error", "-f", "lavfi", "-t", f"{total_close:.3f}",
     "-i", f"color=c={PAD}:s={CANVAS}x{CANVAS}:r={FPS}",
     "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", "-y", rear_close])
flatten(front_close, rear_close, f"{OD}/CLOSING.mp4", "close",
        sandbox=os.path.join(F, "sandbox", "99-closing"))

subprocess.run(["rm", "-rf", tmp])
