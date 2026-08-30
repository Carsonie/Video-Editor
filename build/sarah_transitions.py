#!/usr/bin/env python3
"""
Gap-fillers and the 5-frame transitions either side of them, for the
sarah_clips/libs/ library (see that folder's own README for the plan).

    python3 sarah_transitions.py gap-filler <idle.webm> <seconds> <out.webm>
    python3 sarah_transitions.py opening <scene-avatar.webm> <frame-n> <gap-filler.webm> <out.webm>
    python3 sarah_transitions.py closing <gap-filler.webm> <still.png> <out.webm>

THE ONE THING THAT MAKES THIS TRICKIER THAN IT LOOKS
    sarah_clips/libs/idle/*.webm is the RAW HeyGen render — 608x1080,
    full-figure, the same shape narration.webm always is. A scene's own
    avatar.webm is a DIFFERENT shape: 1152x1152, corner-cropped, composited
    onto a transparent canvas. Blending a raw idle frame straight against a
    canvas frame would fade between two different pictures at two different
    scales — not a transition, a jump cut with extra steps.

    assemble_video.py already solves exactly this for its own hold-fills —
    _idle_canvas() corner-crops an idle clip by ITS OWN geometry and
    composites it onto the same 1152x1152 transparent canvas a scene's
    avatar.webm uses. gap-filler() below calls that function directly
    rather than re-cropping by a second recipe that could drift from it.
    Verified for real before this was written: the composited canvas is
    genuinely transparent outside her corner (checked pixel-by-pixel) and
    her silhouette lands exactly at the requested (x, y) — not assumed from
    reading the code.

THE FIVE-FRAME TRANSITIONS
    fade_frames.build_fade() picks its OWN frame count from how different
    the two endpoints are — the right call for a real hold, where a
    smaller jump deserves fewer frames. Here the count is a fixed
    requirement (5, both directions), so this calls the same blending
    primitives (_smoothstep, _premultiplied_blend) directly rather than
    build_fade()'s frame-count logic — reusing the part that makes a frame
    look right, not the part that decides how many to make.
"""
import argparse
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, os.pardir, "shared"))
import assemble_video as AV               # noqa: E402  _idle_canvas, corner_crop, CANVAS, FPS, run
import build_scenes as BS                 # noqa: E402  probe() — (frames, duration, w, h, start)
import fade_frames as FF                  # noqa: E402  frame_at, _smoothstep, _premultiplied_blend
from PIL import Image                     # noqa: E402


def gap_filler(idle_clip, seconds, out, x=832, y=832):
    """
    A fixed-length slice of `idle_clip`, corner-composited onto the same
    1152x1152 canvas a scene's avatar.webm uses, with silent audio (matching
    assemble_video.py's own hold-fills — a pause is silence, not room tone).

    Returns the frame count actually written.
    """
    # Fresh cache every call: _idle_canvas() memoises per-process in a
    # module-global dict, keyed by nothing but "has this run before" — safe
    # inside assemble_video.py's own one-clip-per-run world, wrong here
    # where a second call might mean a DIFFERENT idle source.
    AV._IDLE.update({"canvas": None, "frames": 0, "used": [], "thumbs": None})
    old_clip = AV.IDLE_CLIP
    AV.IDLE_CLIP = idle_clip
    tmp = tempfile.mkdtemp(prefix="gapfiller_")
    try:
        canvas = AV._idle_canvas(tmp, x, y)
        total = AV._IDLE["frames"]
    finally:
        AV.IDLE_CLIP = old_clip

    n = max(1, round(seconds * AV.FPS))
    if n > total:
        raise ValueError(f"asked for {n} frames ({seconds}s) — the idle canvas "
                          f"only has {total} ({total / AV.FPS:.1f}s)")

    AV.run(["ffmpeg", "-v", "error",
            "-c:v", "libvpx-vp9", "-i", canvas,
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-map", "0:v", "-map", "1:a",
            "-frames:v", str(n), "-shortest",
            "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "2M",
            "-c:a", "libopus", "-y", out])
    return n


def _fixed_fade(a_img, b_img, n):
    """Exactly `n` blended RGBA frames strictly between a and b — same
    premultiplied-alpha blend + ease as build_fade(), just a fixed count
    instead of one chosen from how different the two images are."""
    a = a_img.convert("RGBA")
    b = b_img.convert("RGBA")
    if a.size != b.size:
        b = b.resize(a.size, Image.LANCZOS)
    return [FF._premultiplied_blend(a, b, FF._smoothstep((i + 1) / (n + 1)))
            for i in range(n)]


def opening_transition(scene_avatar, last_frame_n, filler_clip, out, n=5):
    """
    5 frames from a scene's LAST REAL NARRATED frame (1-based frame number,
    matching how Frame Blender numbers frames) into the first frame of a
    gap-filler. Both sources are already 1152x1152 canvas-corner clips, so
    no recompositing is needed here — only the blend.
    """
    tmp = tempfile.mkdtemp(prefix="opening_")
    a_png = FF.frame_at(scene_avatar, os.path.join(tmp, "a.png"), index=last_frame_n - 1)
    b_png = FF.frame_at(filler_clip, os.path.join(tmp, "b.png"), index=0)
    frames = _fixed_fade(Image.open(a_png), Image.open(b_png), n)
    FF.frames_to_webm(frames, out, fps=AV.FPS)
    return len(frames)


def _place_in_corner(still_img, x=832, y=832, corner=None, canvas=None):
    """
    A CORNER-cropped still (e.g. libs/stills/sarah-rest-pose-corner-300-
    alpha.png — roughly square, already head-and-shoulders framed) resized
    to the standard corner box and pasted at (x, y) on a transparent canvas
    the same size a scene's avatar.webm uses.

    Rejects the "-full-" stills outright rather than silently warping them:
    the first version of this function resized whatever it was given
    straight to the full canvas, and a 608x1080 portrait stretched to
    1152x1152 covered nearly the whole frame instead of sitting in the
    corner — five real frames, visibly wrong. A still this far from square
    is a give-away it's the full-figure version, not the corner crop.
    """
    corner = corner or AV.CORNER
    canvas = canvas or AV.CANVAS
    still_img = still_img.convert("RGBA")
    w, h = still_img.size
    if not (0.85 <= w / h <= 1.15):
        raise ValueError(f"still is {w}x{h} — not roughly square, so this looks "
                          f"like the FULL still, not a corner crop. Use the "
                          f"'-corner-<N>-alpha.png' sibling instead.")
    resized = still_img.resize((corner, corner), Image.LANCZOS)
    out = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    out.alpha_composite(resized, (x, y))
    return out


def closing_transition(filler_clip, still_png, out, n=5, x=832, y=832):
    """
    5 frames from a gap-filler's LAST frame into a still reference image —
    pass the CORNER-cropped variant (e.g.
    libs/stills/sarah-rest-pose-corner-300-alpha.png), not the "-full-" one;
    see _place_in_corner()'s docstring for why.
    """
    tmp = tempfile.mkdtemp(prefix="closing_")
    a_png = FF.frame_at(filler_clip, os.path.join(tmp, "a.png"), last=True)
    b_composited = _place_in_corner(Image.open(still_png), x, y)
    frames = _fixed_fade(Image.open(a_png), b_composited, n)
    FF.frames_to_webm(frames, out, fps=AV.FPS)
    return len(frames)


def _add_silence(video_only_webm, out):
    """Give a video-only webm (frames_to_webm()'s output has no audio track
    at all) the same silent stereo track the gap-filler carries, so every
    piece being concatenated has the same streams — concat demuxer refuses
    to join a silent part to a voiced one otherwise, it just drops the track."""
    AV.run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", video_only_webm,
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-map", "0:v", "-map", "1:a", "-shortest",
            "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "2M",
            "-c:a", "libopus", "-y", out])
    return out


def replace_frozen_tail(avatar_path, real_frames_n, idle_clip, still_png, out,
                         opening_n=5, closing_n=5, x=832, y=832):
    """
    Rebuild `avatar_path` with everything AFTER `real_frames_n` replaced:
    her last real narrated frame, then a 5-frame Opening into a gap-filler
    sized to make the total land back on the SAME frame count the file
    already has, then a 5-frame Closing into the standard rest pose.

    Nothing here writes to `avatar_path` itself — `out` is a new file,
    checked before anything decides to swap it in.
    """
    total = int(BS.probe(avatar_path, alpha=True)[0])
    filler_n = total - real_frames_n - opening_n - closing_n
    if filler_n < 1:
        raise ValueError(f"{total} total frames, {real_frames_n} real, "
                          f"{opening_n}+{closing_n} for transitions — leaves "
                          f"{filler_n} for the gap-filler, which is not enough")

    tmp = tempfile.mkdtemp(prefix="replace_tail_")
    real = os.path.join(tmp, "real.webm")
    AV.run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", avatar_path,
            "-frames:v", str(real_frames_n),
            "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "2M",
            "-c:a", "libopus", "-y", real])

    filler = os.path.join(tmp, "filler.webm")
    gap_filler(idle_clip, filler_n / AV.FPS, filler, x, y)

    opening_raw = os.path.join(tmp, "opening_raw.webm")
    opening_transition(avatar_path, real_frames_n, filler, opening_raw, opening_n)
    opening = os.path.join(tmp, "opening.webm")
    _add_silence(opening_raw, opening)

    closing_raw = os.path.join(tmp, "closing_raw.webm")
    closing_transition(filler, still_png, closing_raw, closing_n, x, y)
    closing = os.path.join(tmp, "closing.webm")
    _add_silence(closing_raw, closing)

    concat_list = os.path.join(tmp, "concat.txt")
    with open(concat_list, "w") as fh:
        for p in (real, opening, filler, closing):
            fh.write(f"file '{os.path.abspath(p)}'\n")
    concatenated = os.path.join(tmp, "concatenated.webm")
    AV.run(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0",
            "-c:v", "libvpx-vp9", "-i", concat_list,
            "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "2M",
            "-c:a", "libopus", "-y", concatenated])

    # THE FOUR-RULE TRAP, RULE 4: the concat demuxer lays audio and video
    # end-to-end SEPARATELY. `real`'s own audio (whatever narration.webm
    # naturally ran to for 441 frames) doesn't necessarily end exactly on a
    # frame boundary, and that slop survives the concat untouched — measured
    # here at +1.6s over the video's true length. atrim first (a no-op if
    # already short enough) then apad (a no-op if already exact) forces the
    # audio to the video's real, frame-counted length either direction,
    # rather than assuming concat already got it right.
    exact_dur = total / AV.FPS
    AV.run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", concatenated,
            "-af", f"atrim=0:{exact_dur:.6f},apad=whole_dur={exact_dur:.6f}",
            "-frames:v", str(total),
            "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "2M",
            "-c:a", "libopus", "-y", out])

    got = int(BS.probe(out, alpha=True)[0])
    if got != total:
        raise ValueError(f"assembled {got} frames, expected {total} — "
                          f"NOT swapping this in, {out} is left for inspection")
    return {"total": got, "real": real_frames_n, "opening": opening_n,
            "filler": filler_n, "closing": closing_n}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("gap-filler")
    p.add_argument("idle_clip")
    p.add_argument("seconds", type=float)
    p.add_argument("out")

    p = sub.add_parser("opening")
    p.add_argument("scene_avatar")
    p.add_argument("last_frame_n", type=int)
    p.add_argument("filler_clip")
    p.add_argument("out")

    p = sub.add_parser("closing")
    p.add_argument("filler_clip")
    p.add_argument("still_png")
    p.add_argument("out")

    p = sub.add_parser("replace-tail")
    p.add_argument("avatar_path")
    p.add_argument("real_frames_n", type=int)
    p.add_argument("idle_clip")
    p.add_argument("still_png")
    p.add_argument("out")

    a = ap.parse_args()
    if a.cmd == "gap-filler":
        n = gap_filler(a.idle_clip, a.seconds, a.out)
        print(f"  wrote {a.out} ({n} frames, {n / AV.FPS:.2f}s)")
    elif a.cmd == "opening":
        n = opening_transition(a.scene_avatar, a.last_frame_n, a.filler_clip, a.out)
        print(f"  wrote {a.out} ({n} frames)")
    elif a.cmd == "closing":
        n = closing_transition(a.filler_clip, a.still_png, a.out)
        print(f"  wrote {a.out} ({n} frames)")
    elif a.cmd == "replace-tail":
        r = replace_frozen_tail(a.avatar_path, a.real_frames_n, a.idle_clip, a.still_png, a.out)
        print(f"  wrote {a.out}: {r['total']} frames total "
              f"({r['real']} real + {r['opening']} opening + "
              f"{r['filler']} filler + {r['closing']} closing)")


if __name__ == "__main__":
    main()
