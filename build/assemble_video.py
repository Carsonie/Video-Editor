#!/usr/bin/env python3
"""
Assemble the finished help video: opening + every narrated scene.

Builds the two tracks described in agent 6's "Sarah Opening -> Step 6" and
composites them:

  FRONT  transparent, carries all audio:  intro (centred) ++ morph ++ bridge
         hold ++ one corner segment per scene
  REAR   opaque, silent:  dark ++ scene 1's first frame held under the bridge
         ++ every scene clip

    python3 assemble_video.py "<store>/help-videos/final"

RULES THIS ENCODES
- A scene is on screen for max(clip, narration). Narration is never cut; if the
  line runs long the clip holds its last frame (see agent 6 - words are the
  content, and speeding the demo breaks the natural-speed rule).
- The demo does not start under the bridge. Scene 1's FIRST FRAME is held while
  Sarah says the corner-transition line, so no footage is consumed before its
  own narration begins.
- Every avatar clip is measured for its own crop. HeyGen returns different
  dimensions and poses per render; constants would be wrong by the second clip.
"""
import argparse, glob, json, os, re, shutil, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# paths.py lives in shared/ here, not beside these tools. In Basic_E2E_Testing
# it sat in this same folder; the flatten moved it down to where the editors
# import it from, and one home for it beats two that drift.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "shared"))
from morph_avatar_corner import measure, run, clamp_box  # noqa: E402
import fade_frames  # noqa: E402
import paths as PTH  # noqa: E402
from PIL import Image  # noqa: E402

# ⚠ CANVAS MATCHES THE SCREEN RECORDING'S WIDTH ON PURPOSE.
# OBS records the app at 1152x962. A 1080 canvas meant scaling the demo by
# 15/16 — a non-integer downscale that resampled every glyph and cost 21% of
# the text's edge sharpness (measured 24.70 -> 19.62 on the checkout line item).
# At 1152 the demo is used at its native width with no resampling at all.
# Sarah is unaffected either way: she is downscaled ~0.5x from 608 wide, and a
# large downscale looks crisp. It was the SMALL downscale that hurt.
# CORNER holds the same 27.8% of the canvas as 300/1080 did.
# ⚠ 25, NOT 30 — and this must match everywhere downstream.
#
# HeyGen renders avatars at 25fps and offers no way to change it, and OBS now
# records at 25 to match (RECORD_FPS in Master_Flows/Recorder/lib/obs.ts). Both
# sources are therefore 25. Compositing at 30 resampled BOTH of them, duplicating
# one frame in six in each — and before the OBS change it was worse in a
# different way: the demo was native 30 and only Sarah was resampled.
#
# Anything that converts seconds to frames must divide by THIS, not by a literal.
# `round(seconds * FPS)` was scattered through the hold arithmetic and would make
# every hold 20% too long at 25.
FPS = 25

CANVAS, CORNER = 1152, 320
END_HOLD = 1.0          # seconds to close on the standard rest pose
FADE_PER_STEP = 2.0     # one transition frame per this much % difference
# ⚠ CALIBRATED IN CORNER SPACE, which is NOT the same as full-frame space.
# The corner crop is head-and-shoulders, so it isolates her FACE — the static
# torso no longer dilutes the number. The closing seam measures 4.4% on the full
# 608x1080 frame and 8.5% on the 300x300 corner, for the same two frames. 8.5%
# is the honest figure, because the corner is what the viewer sees.
# 9.0 admits that seam (inspected frame-by-frame: mild ghosting at the midpoint
# nose/mouth, no limb duplication) while still refusing the 12-14% regime, where
# her hands are in a different place and a blend is a double exposure.
FADE_CAP = 9.0

# ---- idle footage: motion instead of a frozen frame during a hold ----------
# Sarah froze for ~10.2s of the 74.8s ski-demo build (tpad=stop_mode=clone at the
# end of every scene whose line is shorter than its segment).
#
# This is REAL idle footage, not frames scraped from speech. It was rendered by
# giving HeyGen SILENT AUDIO instead of a script: `audio_asset_id` pointing at a
# 10s WAV of room tone at -60dBFS, no `script`, no `voice_id`. HeyGen's clip
# length follows the audio, so ten seconds of nothing to say produced ten seconds
# of her sitting there. Measured on the 20s clip: 0 frozen frames out of 499,
# motion ~5x calmer than speech, and her mouth never opens (closed-score min 35,
# median 43, against a talking floor of 28). Cost $1.00 — about $0.05/second.
#
# 20s not 10s: seven holds need 288 frames and best-match picking scatters the
# windows, so a 10s clip fragmented and forced 8 frames of reuse. A 20s clip is
# ~2.1x headroom, which removes the reuse and gives the seam search more
# candidates. State it as a RATIO, not a frame count — the count changes with
# FPS (300 at 30fps, 250 at 25) while the ratio does not.
#
# ⚠ Scraping "closed-mouth" frames out of speech clips was tried first and is a
# dead end — HeyGen clips contain almost no non-speaking frames (17 across all 13
# clips, 0.68s total), and every candidate run that passed a metric turned out on
# inspection to have her mid-word. Render idle footage; do not mine for it.
#
# ⚠ 25fps native, like every HeyGen render.
# ⚠ STALE THE SAME WAY REST_POSE WAS, and this one fills every pause in the
# video. Three levels up at Basic_E2E_Testing's old `Help_Videos/HeyGen/Sarah/`,
# which does not exist here. One level up from build/ is where it lives.
IDLE_CLIP = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         os.pardir, "Sarah", "idle", "sarah-idle-20s-alpha.webm")
IDLE_MIN_SECS = 0.5     # below this a hold is too short for motion to read
IDLE_CAP = 9.0          # seam limit, same corner-space calibration as FADE_CAP

# The video must END on Sarah's standard rest pose. A clip's own final frame is
# NOT reliable for this: scene 11 ends on a softer, slightly asymmetric
# expression (kept as the "Uncertainty" standard), so the close is built from
# the canonical frame instead. Framing matches within 2px across renders
# (head_cx 321 vs 319), so it drops in with no visible jump.
#
# ⚠ THIS PATH WAS STALE and the failure was silent. It pointed three levels up
# at `Help_Videos/HeyGen/Sarah/`, which is Basic_E2E_Testing's old layout — a
# folder that does not exist in this repo. The reference resolved to nothing,
# and the build carried on and ENDED THE VIDEO ON SCENE 11'S OWN LAST FRAME
# instead, which is the softer asymmetric look kept as the "Uncertainty"
# standard. It said so in one warning line among forty and shipped anyway.
#
# The file has lived at <repo>/Sarah/ since the migration. One level up from
# build/, not three.
REST_POSE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         os.pardir, "Sarah", "sarah-rest-pose-full-alpha.png")


def dur(p, alpha=False):
    c = ["ffprobe", "-v", "error"] + (["-c:v", "libvpx-vp9"] if alpha else []) + \
        ["-show_entries", "format=duration", "-of", "csv=p=0", p]
    out = subprocess.run(c, capture_output=True, text=True).stdout.strip()
    # A still image has no duration and ffprobe answers with nothing. Zero is
    # the honest length of one frame's worth of picture, and it is what lets the
    # rest-pose PNG go through the same measuring path as every clip.
    return float(out) if out and out != "N/A" else 0.0


def _has_subject(src, at):
    """Is there anything opaque at `at`? One extracted alpha frame, nothing more."""
    tmp = tempfile.mkdtemp(prefix="sample_")
    try:
        m = os.path.join(tmp, "a.png")
        r = subprocess.run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9",
                            "-ss", f"{at:.3f}", "-i", src, "-vf", "alphaextract",
                            "-frames:v", "1", "-update", "1", "-y", m],
                           capture_output=True, text=True)
        if r.returncode != 0 or not os.path.isfile(m):
            return False
        from PIL import Image
        im = Image.open(m).convert("L")
        w, h = im.size
        px = im.load()
        for y in range(0, h, 4):
            if any(px[x, y] > 32 for x in range(0, w, 6)):
                return True
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def sample_time(src):
    """
    A moment in `src` where the subject is actually on screen.

    This used to be a flat `min(1.0, duration/2)`, which assumes she is there
    one second in. A JOINED scene breaks that assumption by design: when one
    half has no narration render and the other does, the join fills the gap
    with a TRANSPARENT silent clip so the later narration cannot slide forward
    on top of the earlier footage. ski-demo's opening is exactly that — scenes
    1 and 2 merged, the first with no render — so its narration is empty for
    the first eight seconds, and measuring at 1.0s found nothing and stopped
    the build with "no subject found - is the alpha channel actually present?".

    The alpha was present. She was not, yet.

    The old point is tried FIRST, so every clip that already worked is measured
    at exactly the same place and no existing build moves. Only a clip that is
    empty there pays for the search.
    """
    d = dur(src, True)
    first = min(1.0, d / 2)
    if _has_subject(src, first):
        return first
    for frac in (0.25, 0.4, 0.55, 0.7, 0.85, 0.95):
        t = d * frac
        if _has_subject(src, t):
            print(f"  {os.path.basename(src)}: nothing at {first:.2f}s "
                  f"(a filled gap) - measured at {t:.2f}s instead")
            return t
    return first          # nothing anywhere; let measure() say so


def corner_crop(src):
    """Head-and-shoulders square, centred on the head - never the frame."""
    m = measure(src, sample_time(src))
    pad = int((m["shoulder"] - m["top"]) * 0.08)
    side = int((m["shoulder"] - m["top"] + pad) * 1.35)
    return clamp_box(m["head_cx"], m["top"] - pad + side // 2, side, m["w"], m["h"])


_IDLE = {"canvas": None, "frames": 0, "used": [], "thumbs": None}


def _idle_canvas(tmp, x, y):
    """
    The whole idle clip, corner-cropped with ITS OWN geometry and composited on a
    transparent canvas at FPS. Built once; every hold takes a window from it.
    """
    if _IDLE["canvas"]:
        return _IDLE["canvas"]
    box = corner_crop(IDLE_CLIP)
    cw = box[2] - box[0]
    out = f"{tmp}/idle_canvas.webm"
    run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", IDLE_CLIP,
         "-filter_complex",
         f"color=c=black@0.0:s={CANVAS}x{CANVAS}:r={FPS},format=yuva420p[bg];"
         f"[0:v]crop={cw}:{cw}:{box[0]}:{box[1]},scale={CORNER}:{CORNER},fps={FPS},"
         f"format=yuva420p[c];[bg][c]overlay=x={x}:y={y}:shortest=1,format=yuva420p[v]",
         "-map", "[v]", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
         "-b:v", "2M", "-an", "-y", out])
    r = subprocess.run(["ffprobe", "-v", "error", "-c:v", "libvpx-vp9",
                        "-select_streams", "v", "-count_packets",
                        "-show_entries", "stream=nb_read_packets",
                        "-of", "csv=p=0", out], capture_output=True, text=True)
    _IDLE["canvas"], _IDLE["frames"] = out, int(r.stdout.strip())
    print(f"  idle footage: {_IDLE['frames']} frames available at {FPS}fps")
    return out


def _idle_thumbs(tmp, x, y):
    """
    Every idle frame as a small corner crop, held in memory.

    Scoring 300 candidate start frames per hold would mean 300 ffmpeg calls if
    done one at a time. One batch extraction plus PIL comparisons is seconds.
    Thumbnails only RANK candidates — the winner is re-measured at full canvas
    resolution before it is trusted against the cap.
    """
    if _IDLE["thumbs"] is not None:
        return _IDLE["thumbs"]
    canvas = _idle_canvas(tmp, x, y)
    d = f"{tmp}/idle_th"
    os.makedirs(d, exist_ok=True)
    run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", canvas,
         "-vf", f"crop={CORNER}:{CORNER}:{x}:{y},scale=150:150",
         "-c:v", "png", "-pix_fmt", "rgba", os.path.join(d, "t_%04d.png")])
    _IDLE["thumbs"] = [Image.open(f).convert("RGBA")
                       for f in sorted(glob.glob(os.path.join(d, "t_*.png")))]
    return _IDLE["thumbs"]


def _idle_overlap(s0, need):
    """How many frames of [s0, s0+need-1] have already been handed out."""
    e0 = s0 + need - 1
    return sum(max(0, min(e0, b) - max(s0, a) + 1) for a, b in _IDLE["used"])


def _idle_best_start(tmp, x, y, need, A):
    """
    Pick the unused window whose FIRST frame best matches the outgoing frame.

    Taking whatever sits at a moving cursor is what left scene 2 at a 9.93% seam
    when an 8.73% window existed elsewhere in the same clip. Ranking every free
    window costs nothing once the thumbnails exist.
    """
    thumbs = _idle_thumbs(tmp, x, y)
    total = _IDLE["frames"]
    Ac = A.crop((x, y, x + CORNER, y + CORNER)).resize((150, 150), Image.LANCZOS)

    # Prefer windows that reuse nothing. Best-match picking fragments the clip,
    # so a later hold can find no gap big enough — 288 frames are needed and 300
    # exist. When that happens, degrade to the LEAST-overlapping window rather
    # than clearing the history: wiping it silently let two holds take
    # overlapping ranges, which is the repetition this design exists to prevent.
    scored = [(_idle_overlap(s0, need), s0) for s0 in range(0, total - need + 1)]
    fewest = min(o for o, _ in scored)
    pool = [s0 for o, s0 in scored if o == fewest]
    best = min(pool, key=lambda s0: fade_frames.difference(Ac, thumbs[s0])[0])
    if fewest:
        print(f"      (idle exhausted — reusing {fewest} frames; "
              f"a longer idle render would remove this)")
    return best


def _idle_take(tmp, tag, start, nframes):
    """Cut [start, start+nframes-1] out of the idle canvas and mark it used."""
    a, b = start, start + nframes - 1
    _IDLE["used"].append((a, b))
    out = f"{tmp}/idle_{tag}.webm"
    run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", _IDLE["canvas"],
         "-vf", f"select=between(n\\,{a}\\,{b}),setpts=PTS-STARTPTS",
         "-vsync", "0", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
         "-b:v", "2M", "-an", "-y", out])
    return out, a, b


def breathing_segment(tmp, F, n, fv, seconds, x, y):
    """
    Replace a frozen hold with real idle footage.

    Returns a webm of EXACTLY `seconds` (video + silent audio), or None if the
    seam is too wide — in which case the caller must fall back to freezing,
    because the timeline may not come up short.
    """
    try:
        if not os.path.exists(IDLE_CLIP):
            print(f"    scene {n}: no idle clip at {IDLE_CLIP} — holding last frame")
            return None
        total = max(1, round(seconds * FPS))     # exact frames, no drift

        A = Image.open(fade_frames.frame_at(fv, f"{tmp}/is_{n}_a.png", last=True)).convert("RGBA")
        # Rank on thumbnails, then verify the winner at full resolution — the
        # thumbnail score is close but the cap decision must use the real metric.
        start = _idle_best_start(tmp, x, y, total, A)
        probe, _, _ = _idle_take(tmp, f"{n:02d}probe", start, 1)
        _IDLE["used"].pop()             # the probe is not an allocation
        B = Image.open(fade_frames.frame_at(probe, f"{tmp}/is_{n}_b.png", index=0)).convert("RGBA")
        seam = fade_frames.difference(A, B)[0]
        if seam > IDLE_CAP:
            print(f"    scene {n}: best idle seam {seam:.2f}% over {IDLE_CAP:.0f}%"
                  f" — holding last frame")
            return None

        # Fade INSIDE the hold's own duration; extra frames would desync the tracks.
        frames, _ = fade_frames.build_fade(A, B, per_step=FADE_PER_STEP, cap=IDLE_CAP)
        k = len(frames) if len(frames) < total else 0
        parts = []
        if k:
            fw = f"{tmp}/is_{n}_fade.webm"
            fade_frames.frames_to_webm(frames, fw)
            parts.append(fw)
        body, a, b = _idle_take(tmp, f"{n:02d}", start, total - k)
        parts.append(body)

        vcat = parts[0]
        if len(parts) > 1:
            lst = f"{tmp}/is_{n}.txt"
            open(lst, "w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
            vcat = f"{tmp}/is_{n}_v.webm"
            run(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0",
                 "-c:v", "libvpx-vp9", "-i", lst,
                 "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "2M",
                 "-an", "-y", vcat])

        out = f"{tmp}/f_{n:02d}_idle.webm"
        run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", vcat,
             # Audio is deliberately ONE FRAME LONGER than the video, so
             # `-shortest` is governed by the video. Rounding total/30 to 4dp
             # lands just under the true frame duration for some lengths (34/30
             # -> 1.1333 vs 1.13333) and silently drops the last video frame.
             "-f", "lavfi", "-t", f"{(total + 1) / FPS:.4f}",
             "-i", "anullsrc=r=48000:cl=stereo",
             "-map", "0:v", "-map", "1:a", "-shortest",
             "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "2M",
             "-c:a", "libopus", "-y", out])
        print(f"    scene {n}: idle {total}f ({total/30:.2f}s) from idle frames {a}-{b}"
              f"  (seam {seam:.2f}%, {k}-frame fade)")
        return out
    except Exception as e:
        print(f"    ⚠ scene {n}: idle failed ({type(e).__name__}: {e}) — holding last frame")
        return None


def silent_front(tmp, F, n, prev_fv, seconds, x, y):
    """
    The front track for a scene with NO narration: Sarah waits in the corner,
    in silence, for exactly `seconds`.

    Real idle footage first — seam-matched to whatever precedes it by the same
    breathing_segment() a long hold already uses, so a silent scene moves and
    breathes rather than freezing. If no window seams cleanly it clones the
    previous clip's last frame, the same fallback and for the same reason:
    nothing downstream may come up shorter than the plan.

    `prev_fv` is already canvas-sized and composited, so its last frame drops
    straight onto the timeline — no crop, no overlay. That is the whole reason
    this takes the PREVIOUS front clip rather than the full-frame rest pose.
    """
    seg = breathing_segment(tmp, F, n, prev_fv, seconds, x, y)
    if seg:
        return seg
    still = fade_frames.frame_at(prev_fv, f"{tmp}/sil_{n:02d}.png", last=True)
    out = f"{tmp}/f_{n:02d}_silent.webm"
    run(["ffmpeg", "-v", "error", "-loop", "1", "-t", f"{seconds:.3f}", "-i", still,
         "-f", "lavfi", "-t", f"{seconds:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
         "-filter_complex", f"[0:v]fps={FPS},format=yuva420p[v]",
         "-map", "[v]", "-map", "1:a", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
         "-b:v", "2M", "-c:a", "libopus", "-y", out])
    return out


def script_path(folder):
    """
    Locate a video's script.

    It lives in `<final>/video/script.json`, beside the videos it produced —
    moved there 2026-08-20 so the copy and the cuts it made sit together. The
    old `<final>/script.json` is still accepted so an un-migrated store keeps
    working rather than failing obscurely.

    Versioned snapshots (`script_v13.json`) are RECORDS written when a build is
    copied to a version, not inputs. At edit time the next version number is not
    known yet, so the working file stays unversioned.
    """
    import os
    new = os.path.join(folder, "video", "script.json")
    old = os.path.join(folder, "script.json")
    if os.path.exists(new):
        return new
    if os.path.exists(old):
        print(f"  ⚠ using {old} — move it to video/script.json")
        return old
    raise SystemExit(f"no script.json in {os.path.join(folder,'video')} or {folder}")


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


# The avatar's clips live in a folder named for the AVATAR, not for the job they
# do. `sarah_intro_tools` was accurate when the only thing in it was the opening;
# it now also holds the closing morph, the close-out line and the exported
# bookends, and a second presenter would need a folder of their own. Renamed
# 2026-08-21 to `sarah_clips` so the pattern extends: `<name>_clips`.
SARAH_DIR = "sarah_clips"
LEGACY_SARAH_DIRS = ("sarah_intro_tools",)


def sarah_dir(folder):
    """
    Where this store's avatar clips live. Prefers `<final>/sarah_clips/`, accepts
    the pre-rename `sarah_intro_tools/`, and falls back to `<final>/` itself so a
    store that never had the folder keeps working rather than failing obscurely.

    ⚠ Several of these are PAID HeyGen renders and the build scripts overwrite
    them by name with no backup. Losing them costs money to replace.
    """
    import os
    d = os.path.join(folder, SARAH_DIR)
    if os.path.isdir(d):
        return d
    for legacy in LEGACY_SARAH_DIRS:
        ld = os.path.join(folder, legacy)
        if os.path.isdir(ld):
            return ld
    return folder


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--out", default="FINAL_video.mp4")
    ap.add_argument("--scenes", default="",
                    help="build only these scene numbers, e.g. 1,2. For ITERATING "
                         "on the opening or a seam without paying for the whole "
                         "video — a full ski-demo build is four minutes and the "
                         "first two scenes are twenty seconds. The output is not "
                         "a deliverable; name it so nobody mistakes it for one.")
    ap.add_argument("--skip-qualify", action="store_true",
                    help="build anyway, without checking the frames first. "
                         "For when you KNOW a fault is there and want the "
                         "output regardless — it is never the normal path.")
    a = ap.parse_args()
    F = a.folder

    # ── THE GATE ────────────────────────────────────────────────────────────
    # Every frame is staged and qualified BEFORE a single one is composited.
    #
    # This build has twice produced a wrong video and reported success. A
    # joined scene's narration was transparent for its first 285 frames and
    # 11.4 seconds of nothing was composited over the footage; and the two
    # tracks drift apart as scenes are edited, which is papered over by holding
    # whichever is short — right for a few frames, wrong for a few hundred, and
    # silent either way.
    #
    # Neither was visible in the editor, because the editor shows avatar.webm
    # and this composites narration.webm. So the check has to live here, where
    # the decision is actually made.
    if not a.skip_qualify:
        gate = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "qualify_avatar.py")
        r = subprocess.run([sys.executable, gate, F, "--quiet", "--log"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.stderr.write(r.stdout + r.stderr)
            sys.exit("\n  Nothing was built. Fix the frames, or pass --skip-qualify "
                     "to build over the fault deliberately.")
        print("  frames qualified — every pair staged, every frame a known shape")
    cfg = json.load(open(script_path(F)))
    if a.scenes:
        want = {int(x) for x in a.scenes.split(",") if x.strip()}
        keep = [x for x in cfg["scenes"] if x["n"] in want]
        if not keep:
            sys.exit(f"  none of {sorted(want)} are in the script")
        cfg["scenes"] = keep
        print(f"  PARTIAL BUILD — scenes {sorted(x['n'] for x in keep)} only. "
              f"Not a deliverable.")
    tmp = tempfile.mkdtemp()
    P = lambda *x: os.path.join(F, *x)

    OD = sarah_dir(F)
    OP = lambda n: os.path.join(OD, n)
    intro_d = dur(OP(f"sarah-intro-{CANVAS}-alpha.webm"), True)
    morph_d = dur(OP("sarah-bridge-transition-to-corner.webm"), True)
    bridge_d = dur(OP("sarah-bridge-alpha.webm"), True)
    x = y = CANVAS - CORNER
    print(f"  opening: intro {intro_d:.2f}s + bridge {bridge_d:.2f}s (morph {morph_d:.2f}s)")

    # pad colour sampled from a real frame - guessing it leaves a visible band
    run(["ffmpeg", "-v", "error", "-ss", "1", "-i",
         PTH.segment(F, cfg["scenes"][0]["n"], cfg["scenes"][0].get("label"))
         or P("segments", cfg["scenes"][0]["segment"]),
         "-frames:v", "1", "-update", "1", "-y", f"{tmp}/edge.png"])
    im = Image.open(f"{tmp}/edge.png").convert("RGB")
    PAD = "0x%02X%02X%02X" % im.getpixel((5, im.size[1] // 2))
    print(f"  pad colour {PAD}")

    front, rear, plan = [], [], []
    # ---- opening -------------------------------------------------------
    front.append(OP(f"sarah-intro-{CANVAS}-alpha.webm"))
    # morph + bridge hold, as one piece with the bridge's audio
    seg = f"{tmp}/f_bridge.webm"
    run(["ffmpeg", "-v", "error",
         "-c:v", "libvpx-vp9", "-i", OP("sarah-bridge-transition-to-corner.webm"),
         "-c:v", "libvpx-vp9", "-i", OP(f"sarah-bridge-corner-{CORNER}-alpha.webm"),
         "-c:v", "libvpx-vp9", "-i", OP("sarah-bridge-alpha.webm"),
         "-filter_complex",
         f"color=c=black@0.0:s={CANVAS}x{CANVAS}:r={FPS},format=yuva420p[bg];"
         f"[1:v]trim=start={morph_d},setpts=PTS-STARTPTS[c];"
         f"[bg][c]overlay=x={x}:y={y}:shortest=1,format=yuva420p[hold];"
         f"[0:v]fps={FPS},format=yuva420p[m];[m][hold]concat=n=2:v=1:a=0,format=yuva420p[v]",
         "-map", "[v]", "-map", "2:a", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
         "-b:v", "2M", "-c:a", "libopus", "-y", seg])
    front.append(seg)

    # rear: dark for the intro, then scene 1's FIRST FRAME held under the bridge
    d1 = f"{tmp}/r_dark.mp4"
    run(["ffmpeg", "-v", "error", "-f", "lavfi", "-t", f"{intro_d:.3f}",
         "-i", f"color=c={PAD}:s={CANVAS}x{CANVAS}:r={FPS}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y", d1])
    rear.append(d1)
    # ⚠ This holds scene 1's FIRST frame for the whole bridge, so that frame
    # must be a settled page. It was a loading spinner ("three dots") until
    # scene 1 was re-cut to start 0.17s later — frozen for 4.16s it was the most
    # visible defect in the video. If a scene's opening frames are mid-render,
    # fix the CUT, not this.
    d2 = f"{tmp}/r_hold.mp4"
    # THE HELD FRAME IS FRAME 0, forced by `trim=end_frame=1`.
    # Two separate mistakes made this hold the wrong frame before:
    #   1. `-t 0.04` reads TWO frames at 30fps, and tpad clones the LAST one —
    #      so the hold showed frame 1, which on the login segment already has
    #      the first character typed ("R"). trim=end_frame=1 pins it to frame 0.
    #   2. Moving `-ss 0 -t 0.04` after `-i` makes them OUTPUT options, which
    #      truncates the padded result to 0.04s and silently slides the whole
    #      rear track so segment 1 plays under the bridge. They stay INPUT
    #      options.
    run(["ffmpeg", "-v", "error", "-ss", "0", "-t", "0.04", "-i",
         PTH.segment(F, cfg["scenes"][0]["n"], cfg["scenes"][0].get("label"))
         or P("segments", cfg["scenes"][0]["segment"]),
         "-vf", f"trim=end_frame=1,setpts=PTS-STARTPTS,scale={CANVAS}:-2:flags=lanczos,pad={CANVAS}:{CANVAS}:0:({CANVAS}-ih)/2:color={PAD},setsar=1,"
                f"fps={FPS},tpad=stop_mode=clone:stop_duration={bridge_d:.3f},fade=t=in:st=0:d=0.6:color={PAD}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", "-y", d2])
    rear.append(d2)

    # ---- announce any SANDBOX override before building anything --------
    # A sandbox file entering a finished video unannounced is the one failure
    # this layer could introduce, and it would be invisible in the output — the
    # video would simply differ from the one the folder names imply. So it is
    # said up front, per scene, per part.
    _sb = []
    for _s in cfg["scenes"]:
        for _what, _p in (("segment", PTH.segment(F, _s["n"], _s.get("label"))),
                          ("narration", PTH.narration(F, _s["n"], _s.get("label")))):
            if PTH.source_of(F, _p) == "sandbox":
                _sb.append(f"scene {_s['n']} {_s.get('label','')} — {_what}")
    if _sb:
        print("\n  ⚠ SANDBOX OVERRIDE — this build is NOT the committed material:")
        for _line in _sb:
            print(f"      {_line}")
        print(f"    {len(_sb)} override(s). Name the output accordingly.\n")

    # ---- one segment per scene -----------------------------------------
    for s in cfg["scenes"]:
        n = s["n"]
        clip = PTH.segment(F, n, s.get("label")) or P("segments", s["segment"])
        cd = dur(clip)

        # A SILENT scene has no narration and never went to HeyGen — the segment
        # plays while Sarah simply waits. Declared by `silent` in script.json;
        # an empty `line` counts too, because a scene with nothing to say cannot
        # have a narration clip, and looking for one only fails later and less
        # clearly. `box`/`cw` deliberately keep the last SPOKEN scene's geometry:
        # the closing hold's crop must come from a real render.
        if bool(s.get("silent")) or not s.get("line", "").strip():
            nd, on = 0.0, cd
            plan.append((n, cd, nd, on))
            if not front:
                sys.exit(f"  scene {n} is silent and comes first — there is nothing "
                         f"before it to hold. Give it a line, or move it later.")
            fv = silent_front(tmp, F, n, front[-1], cd, x, y)
            front.append(fv)
        else:
            # ── THE SCENE'S SARAH COMES FROM THE SANDBOX ────────────────
            # avatar.webm — the file the editor shows and the one you approve.
            #
            # This used to composite narration.webm instead: the raw 1920x1080
            # HeyGen render, cropped to her head here and scaled into the
            # corner. The reasoning was sound — the master is sharper, and the
            # crop is measured rather than inherited — and it was still wrong,
            # because it meant the picture that shipped was never the picture
            # anyone looked at.
            #
            # What that cost:
            #
            #   A joined scene's narration was TRANSPARENT for its first 285
            #   frames — the join filled the gap so the login line could not
            #   slide forward over the intro — while its avatar carried the
            #   opening's Sarah correctly. The editor was right and the video
            #   had an 11.4 second hole.
            #
            #   Frame counts were balanced against the AVATAR (482/482) and the
            #   build paired against the NARRATION (499), so it stretched eight
            #   of eleven scenes to lengths nobody chose. 0.68s of held frame in
            #   scene 1 alone.
            #
            # The avatar needs none of the old machinery: it is already
            # 1152x1152 with real alpha, already in the corner, and carries her
            # voice. So it is laid on as it is.
            #
            # The OPENING and CLOSING are untouched by this. They are built from
            # sarah_clips/ and never came from the sandbox.
            nar = PTH.avatar(F, n, s.get("label"))
            if nar is None:
                sys.exit(f"  no avatar for scene {n} ({s.get('label','')}) — "
                         f"the editor writes sandbox/<NN>-<label>/avatar.webm, "
                         f"and that is what a scene is built from.")
            if PTH.source_of(F, nar) != "sandbox":
                print(f"  ⚠ scene {n}: the avatar came from {PTH.source_of(F, nar)}/, "
                      f"not sandbox/ — this is not the clip the editor shows.")
            nd = dur(nar, True)
            on = max(nd, cd)
            plan.append((n, cd, nd, on))

            # A hold long enough to notice gets breathing footage instead of a
            # freeze. `breathing_segment` may still decline (no close enough loop),
            # so the fallback re-pads — the front track must never come up short.
            freeze = max(0.0, on - nd)
            if freeze >= IDLE_MIN_SECS and os.path.exists(IDLE_CLIP):
                pad_v, breath_secs = 0.0, freeze
            else:
                pad_v, breath_secs = freeze, 0.0

            # NO crop, NO scale, NO placing. The avatar is already the finished
            # canvas — 1152x1152, alpha, Sarah in the corner where the editor
            # put her. Every one of those steps was a chance to differ from
            # what was approved, and each of them has.
            #
            # It is still SCALED TO THE CANVAS, and only that: a defensive fit
            # for a clip that is not 1152 square, so an odd file lands whole
            # rather than half off the edge.
            fv = f"{tmp}/f_{n:02d}.webm"
            run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", nar, "-filter_complex",
                 f"color=c=black@0.0:s={CANVAS}x{CANVAS}:r={FPS},format=yuva420p[bg];"
                 f"[0:v]scale={CANVAS}:{CANVAS}:force_original_aspect_ratio=decrease,"
                 f"fps={FPS},format=yuva420p[c];"
                 f"[bg][c]overlay=x=(W-w)/2:y=(H-h)/2:shortest=1,"
                 # clone, NOT add. `add` pads with transparent frames, which made Sarah
                 # VANISH the instant her line ended. Cloning holds her last frame —
                 # and every HeyGen clip ENDS on the settled rest pose (eyes open,
                 # mouth closed), verified across all 11 scene clips, so the held
                 # frame is correct by construction. Clip STARTS are not: they are
                 # mid-word with eyes shut. See Help_Videos/HeyGen/Sarah/README.md.
                 f"tpad=stop_mode=clone:stop_duration={pad_v:.3f},format=yuva420p[v];"
                 f"[0:a]apad=pad_dur={pad_v:.3f}[a]",
                 "-map", "[v]", "-map", "[a]", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
                 "-b:v", "2M", "-c:a", "libopus", "-y", fv])
            front.append(fv)
            if breath_secs > 0:
                bseg = breathing_segment(tmp, F, n, fv, breath_secs, x, y)
                if bseg:
                    front.append(bseg)
                else:
                    # no usable loop — re-pad this clip the old way so the timeline
                    # still adds up. Nothing downstream may be shorter than `on`.
                    fv2 = f"{tmp}/f_{n:02d}_repad.webm"
                    run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", fv,
                         "-filter_complex",
                         f"[0:v]tpad=stop_mode=clone:stop_duration={breath_secs:.3f},format=yuva420p[v];"
                         f"[0:a]apad=pad_dur={breath_secs:.3f}[a]",
                         "-map", "[v]", "-map", "[a]", "-c:v", "libvpx-vp9",
                         "-pix_fmt", "yuva420p", "-b:v", "2M", "-c:a", "libopus", "-y", fv2])
                    front[-1] = fv2

        rv = f"{tmp}/r_{n:02d}.mp4"
        run(["ffmpeg", "-v", "error", "-i", clip, "-vf",
             f"scale={CANVAS}:-2:flags=lanczos,pad={CANVAS}:{CANVAS}:0:({CANVAS}-ih)/2:color={PAD},setsar=1,fps={FPS},"
             f"tpad=stop_mode=clone:stop_duration={max(0,on-cd):.3f}",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", "-y", rv])
        rear.append(rv)

    # ---- closing hold: end on the standard rest pose --------------------
    if os.path.exists(REST_POSE):
        fend = f"{tmp}/f_end.webm"
        # MEASURED AGAINST THE REST POSE ITSELF, not inherited from the last
        # scene. `box`/`cw` are still in scope from the loop above, and using
        # them here crops one image with another image's coordinates: the last
        # narration is 1920x1080 and this PNG is 608x1080, so the box started at
        # x=745 on a picture 608 wide — entirely off the right edge. What
        # survived was dropped in the corner at full size, cut off by the frame.
        #
        # It shipped because this branch had NEVER RUN: REST_POSE pointed at
        # Basic_E2E_Testing's old layout, the file was not there, and the build
        # took the other path every time. Fixing the path switched on dead code.
        rbox = corner_crop(REST_POSE)
        rcw = rbox[2] - rbox[0]
        run(["ffmpeg", "-v", "error", "-loop", "1", "-t", f"{END_HOLD:.3f}", "-i", REST_POSE,
             "-f", "lavfi", "-t", f"{END_HOLD:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
             "-filter_complex",
             f"color=c=black@0.0:s={CANVAS}x{CANVAS}:r={FPS},format=yuva420p[bg];"
             f"[0:v]crop={rcw}:{rcw}:{rbox[0]}:{rbox[1]},scale={CORNER}:{CORNER},fps={FPS},format=yuva420p[c];"
             f"[bg][c]overlay=x={x}:y={y}:shortest=1,format=yuva420p[v]",
             "-map", "[v]", "-map", "1:a", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
             "-b:v", "2M", "-c:a", "libopus", "-y", fend])
        # The rest pose is a DIFFERENT RENDER from scene 11, so this seam is a
        # real cut between two expressions (11 ends on the softer "Uncertainty"
        # look). Measured at 4.4% different — under fade_frames' 5% cap, so a
        # short dissolve smooths it. Above the cap it declines and says so,
        # which is correct: a big difference blends into a double exposure.
        fade_dur = 0.0
        try:
            a_png = fade_frames.frame_at(fv, f"{tmp}/seam_a.png", last=True)
            b_png = fade_frames.frame_at(fend, f"{tmp}/seam_b.png", index=0)
            frames, info = fade_frames.build_fade(
                Image.open(a_png).convert("RGBA"),
                Image.open(b_png).convert("RGBA"),
                per_step=FADE_PER_STEP, cap=FADE_CAP)
            if frames:
                ffade = f"{tmp}/f_fade.webm"
                fade_frames.frames_to_webm(frames, f"{tmp}/f_fade_silent.webm")
                fade_dur = len(frames) / FPS
                run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9",
                     "-i", f"{tmp}/f_fade_silent.webm",
                     "-f", "lavfi", "-t", f"{fade_dur:.3f}",
                     "-i", "anullsrc=r=48000:cl=stereo",
                     "-map", "0:v", "-map", "1:a",
                     "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "2M",
                     "-c:a", "libopus", "-y", ffade])
                front.append(ffade)
                print(f"  closing fade: {len(frames)} frames ({fade_dur:.3f}s), "
                      f"seam was {info['mean_pct']:.2f}% different")
            else:
                print(f"  closing fade: none — {info['reason']}")
        except Exception as e:
            print(f"  ⚠ closing fade skipped ({type(e).__name__}: {e}) — "
                  f"the cut is unchanged, not broken")

        # ---- the CLOSING BOOKEND -----------------------------------------
        # If a reverse morph exists, the video ends the way it began but
        # mirrored: Sarah grows back out of the corner to full screen while the
        # demo behind her fades to the pad colour, and lands on the same rest
        # pose the opening started from. Built by
        #   morph_avatar_corner.py --reverse
        # so it is the SAME interpolation as the opening with its endpoints
        # swapped, not a second implementation that could drift.
        #
        # Without that file the old behaviour stands: a short hold on the rest
        # pose, still in the corner. Every store that has not had a closing
        # built keeps working unchanged.
        morph_back = glob.glob(os.path.join(sarah_dir(F),
                                            "*-transition-to-centre.webm"))
        if morph_back:
            mb = morph_back[0]
            mb_d = dur(mb, True)
            front.append(mb)
            # A CLOSE-OUT LINE, if one was rendered: she lands from the morph and
            # speaks instead of sitting mute. Placed so her HEAD continues exactly
            # where the morph left it — matched on head height and head centre,
            # never on the alpha bbox, which tracks her hands and moves constantly.
            # The geometry is computed, not tuned by eye; the two HeyGen renders
            # differ slightly in framing every time and cannot be assumed equal.
            closeout = os.path.join(sarah_dir(F), "sarah-closeout-alpha.webm")
            tail_dur = END_HOLD
            if os.path.exists(closeout):
                # The morph is named for the clip it was cut from
                # (`sarah-scene-12-transition-to-centre.webm`), so its source is
                # derivable rather than assumed — the morph and this measurement
                # must be of the SAME render or her head will jump.
                stem = os.path.basename(mb).replace("-transition-to-centre.webm", "")
                nar_for_morph = next(
                    (c for c in (os.path.join(sarah_dir(F), f"{stem}-alpha.webm"),
                                 os.path.join(scene_clips_dir(F), f"{stem}-alpha.webm"),
                                 os.path.join(F, f"{stem}-alpha.webm"))
                     if os.path.exists(c)), None)
                if nar_for_morph is None:
                    raise SystemExit(
                        f"  the closing morph {os.path.basename(mb)} names a source "
                        f"`{stem}-alpha.webm` that is not beside it. The close-out has to be "
                        f"measured against the SAME render the morph was cut from, or her head "
                        f"jumps at the join — so this cannot be guessed.")
                src_m = measure(nar_for_morph, max(0.0, dur(nar_for_morph, True) - 1.0))
                co_m = measure(closeout, min(0.6, dur(closeout, True) / 2))
                k = CANVAS / src_m["h"]
                head_x = round(CANVAS / 2 - src_m["subject_cx"] * k) + src_m["head_cx"] * k
                head_y = src_m["top"] * k
                sc = k * ((src_m["shoulder"] - src_m["top"]) / (co_m["shoulder"] - co_m["top"]))
                cw2, ch2 = round(co_m["w"] * sc), round(co_m["h"] * sc)
                cx2 = round(head_x - co_m["head_cx"] * sc)
                cy2 = round(head_y - co_m["top"] * sc)
                fco = f"{tmp}/f_closeout.webm"
                run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", closeout,
                     "-filter_complex",
                     f"color=c=black@0.0:s={CANVAS}x{CANVAS}:r={FPS},format=yuva420p[bg];"
                     f"[0:v]scale={cw2}:{ch2},fps={FPS},format=yuva420p[c];"
                     f"[bg][c]overlay=x={cx2}:y={cy2}:shortest=1,format=yuva420p[v]",
                     "-map", "[v]", "-map", "0:a", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
                     "-b:v", "2M", "-c:a", "libopus", "-y", fco])
                # A HeyGen clip is trimmed to its first audio sample, so it OPENS
                # mid-word with the mouth already moving. Dropped straight after
                # the morph — which ends on her settled rest pose — that is a
                # visible snap: measured 17.4% against ~5% for every frame around
                # it. Two blended frames spread it, the same ease the opening
                # seam uses. Inserted as their own clip rather than overwriting
                # the first frames of the line, so not one sample of her speech
                # is lost.
                try:
                    a_png = fade_frames.frame_at(mb, f"{tmp}/co_a.png", last=True)
                    b_png = fade_frames.frame_at(fco, f"{tmp}/co_b.png", index=0)
                    A = Image.open(a_png).convert("RGBA")
                    B = Image.open(b_png).convert("RGBA")
                    steps = [Image.blend(A, B, k / 3.0) for k in (1, 2)]
                    bridge_silent = f"{tmp}/co_bridge_silent.webm"
                    fade_frames.frames_to_webm(steps, bridge_silent)
                    bridge = f"{tmp}/co_bridge.webm"
                    bd = len(steps) / FPS
                    run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", bridge_silent,
                         "-f", "lavfi", "-t", f"{bd:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
                         "-map", "0:v", "-map", "1:a", "-c:v", "libvpx-vp9",
                         "-pix_fmt", "yuva420p", "-b:v", "2M", "-c:a", "libopus",
                         "-y", bridge])
                    front.append(bridge)
                    tail_dur += bd
                    print(f"  close-out ease-in: {len(steps)} frames ({bd:.2f}s)")
                except Exception as e:
                    print(f"  ⚠ close-out ease-in skipped ({type(e).__name__}: {e}) — "
                          f"the cut is unchanged, not broken")
                front.append(fco)
                co_d = dur(fco, True)
                tail_dur += co_d
                print(f"  close-out line: {co_d:.2f}s, scaled {sc/k:.4f} to match her head "
                      f"(lands at x={cx2}, y={cy2})")
            # She is centred now, so the closing hold is the rest pose at FULL
            # SIZE — cropping it to the corner here would snap her back.
            fbig = f"{tmp}/f_end_big.webm"
            run(["ffmpeg", "-v", "error", "-loop", "1", "-t", f"{END_HOLD:.3f}", "-i", REST_POSE,
                 "-f", "lavfi", "-t", f"{END_HOLD:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
                 "-filter_complex",
                 f"color=c=black@0.0:s={CANVAS}x{CANVAS}:r={FPS},format=yuva420p[bg];"
                 f"[0:v]scale=-2:{CANVAS},fps={FPS},format=yuva420p[c];"
                 f"[bg][c]overlay=x=(W-w)/2:y=0:shortest=1,format=yuva420p[v]",
                 "-map", "[v]", "-map", "1:a", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
                 "-b:v", "2M", "-c:a", "libopus", "-y", fbig])
            front.append(fbig)
            # Rear: hold the last demo frame, fade it out to the pad colour over
            # the morph, then flat pad underneath the final hold. The fade has to
            # run for exactly the morph's length or the two tracks desync.
            rend = f"{tmp}/r_end.mp4"
            run(["ffmpeg", "-v", "error", "-i", rv, "-vf",
                 f"trim=start={max(0.0, dur(rv) - 0.05):.3f},setpts=PTS-STARTPTS,fps={FPS},"
                 f"tpad=stop_mode=clone:stop_duration={mb_d + tail_dur + fade_dur:.3f},"
                 f"fade=t=out:st={fade_dur:.3f}:d={mb_d:.3f}:color={PAD}",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", "-y", rend])
            rear.append(rend)
            print(f"  CLOSING BOOKEND: {mb_d:.2f}s morph corner->centre, background fading to "
                  f"{PAD}, then {END_HOLD:.1f}s centred on the rest pose")
        else:
            front.append(fend)
            # The rear track must absorb the fade too, or the two tracks desync and
            # every frame after the seam is offset.
            rend = f"{tmp}/r_end.mp4"
            run(["ffmpeg", "-v", "error", "-i", rv, "-vf",
                 f"trim=start={max(0.0, dur(rv) - 0.05):.3f},setpts=PTS-STARTPTS,fps={FPS},"
                 f"tpad=stop_mode=clone:stop_duration={END_HOLD + fade_dur:.3f}",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", "-y", rend])
            rear.append(rend)
            print(f"  closing hold: {END_HOLD:.1f}s on the standard rest pose (no bookend built)")
    else:
        print(f"  ⚠ rest-pose reference missing ({REST_POSE}) — video will end on "
              f"the last scene's own final frame, which is NOT the standard.")

    def concat(files, out, audio):
        lst = f"{tmp}/{os.path.basename(out)}.txt"
        open(lst, "w").write("".join(f"file '{os.path.abspath(f)}'\n" for f in files))
        # -c:v libvpx-vp9 BEFORE -i, or the concat demuxer decodes the alpha
        # WebMs with the default decoder and silently flattens them to opaque
        # black. The output still reports yuva420p, so it looks fine until the
        # composite shows a black background.
        cmd = ["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0"]
        if audio:
            cmd += ["-c:v", "libvpx-vp9"]
        cmd += ["-i", lst]
        if audio:
            cmd += ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "2M", "-c:a", "libopus"]
        else:
            cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"]
        run(cmd + ["-y", out])

    ftrack, rtrack = P("TRACK_front_full.webm"), P("TRACK_rear_full.mp4")
    concat(front, ftrack, True)
    concat(rear, rtrack, False)
    print(f"  front {dur(ftrack, True):.1f}s | rear {dur(rtrack):.1f}s")

    out = P(a.out)
    run(["ffmpeg", "-v", "error", "-i", rtrack, "-c:v", "libvpx-vp9", "-i", ftrack,
         "-filter_complex", "[0:v][1:v]overlay=x=0:y=0:shortest=1,format=yuv420p[v]",
         "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-crf", "20", "-c:a", "aac",
         "-movflags", "+faststart", "-y", out])
    print(f"\n  {out}  {dur(out):.1f}s")
    print(f"\n  {'#':>2}{'clip':>8}{'narr':>8}{'on screen':>11}")
    for n, cd, nd, on in plan:
        print(f"  {n:>2}{cd:>7.1f}s{nd:>7.1f}s{on:>10.1f}s" + ("   clip held" if on > cd else ""))

    # A version number in --out (e.g. "..._v15.mp4") gets its own script
    # snapshot next to script.json — the words behind THIS build, pinned. This
    # never ran automatically before 2026-08-20: script_v14.json existed only
    # because it was copied by hand, and v15 shipped with no snapshot at all
    # until that gap was noticed and backfilled. If --out carries no version
    # (e.g. FINAL_video.mp4), there is nothing to pin it to and this is skipped.
    m = re.search(r"_v(\d+)\.[^.]+$", os.path.basename(out))
    if m:
        snap = os.path.join(os.path.dirname(script_path(F)), f"script_v{m.group(1)}.json")
        shutil.copyfile(script_path(F), snap)
        print(f"  wrote {os.path.basename(snap)} — the script behind this build")

        # Every older build and its script snapshot move to video/z_History/.
        # ski-demo's video/ had fourteen finished mp4s and ten scripts sitting
        # beside each other, and picking the current one out of that list is a
        # job nobody should have to do carefully. What stays is this build, its
        # snapshot, script.json, and anything that is not a versioned build.
        vdir = os.path.dirname(script_path(F))
        keep = {os.path.basename(out), os.path.basename(snap), "script.json"}
        old_builds = [x for x in sorted(os.listdir(vdir))
                      if x not in keep
                      and re.search(r"_v\d+\.[^.]+$|^script_v\d+\.json$", x)]
        if old_builds:
            dest = PTH.archive_contents(vdir, only=old_builds)
            print(f"  archived {len(old_builds)} older build(s) and snapshot(s) to "
                  f"{os.path.relpath(dest, vdir)}/")
    else:
        print("  ⚠ --out has no _vN — no script snapshot written (pass e.g. --out video/store_title_v16.mp4)")


if __name__ == "__main__":
    main()
