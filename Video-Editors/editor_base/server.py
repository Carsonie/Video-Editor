"""
The plumbing every editor server needs, once.

⚠ THIS CODE EXISTED TWICE, VERBATIM, AND TWO MORE EDITORS IMPORTED ONE OF THE
COPIES. `shared/serve.py` was an 82% duplicate of the Segment and Avatar
Editor's own server (2711 lines against 2487), Frame Blender and Avatar Editor
did `import serve as main_serve` and then CONFIGURED it by writing into its
globals (`main_serve.CACHE = ...`), and nine of these ten helpers were
byte-identical in both files. A fix in one was a fix in one.

So they live here, lifted out of the SAE unchanged, and every editor imports
them. What stays with each editor is what differs: its port, its routes, its
page, its own cache folder, its own log name.

    from editor_base import server as ebserver
    ebserver.safe_join(rel)              # under Customers/, or None
    ebserver.resolve_outdir(slug)        # a cache folder, never a path escape

⚠ THE CACHE IS THE CALLER'S. `resolve_outdir` reads `editor_base.frames.CACHE`,
which each editor sets once at start-up with `frames.use_cache(...)`. That is
why two editors can hold different extractions of the same clip without
touching each other's, and why this module never picks a cache of its own.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

from editor_base import frames as build_mod


HERE = os.path.dirname(os.path.abspath(__file__))


def _repo_root(start):
    """
    The folder that HAS a Customers/ — found by walking up, not by counting
    `..` levels, so moving an editor does not silently point it somewhere else.
    """
    d = start
    for _ in range(8):
        if os.path.isdir(os.path.join(d, "Customers")):
            return d
        up = os.path.dirname(d)
        if up == d:
            break
        d = up
    return start


REPO_ROOT = _repo_root(HERE)
CUSTOMERS_ROOT = os.path.join(REPO_ROOT, "Customers")


ENCODE = ["-c:v", "libx264", "-crf", "18", "-c:a", "aac", "-pix_fmt", "yuv420p",
          "-movflags", "+faststart"]

# H.264 CANNOT carry an alpha channel. Cutting an avatar WebM through ENCODE
# produced Sarah on a black rectangle — and produced it SILENTLY, with a zero
# exit code and a playable file, because the alpha was already gone at the
# decode step. Anything transparent goes through this instead.
#
#   -auto-alt-ref 0   alt-ref frames are what drop alpha in libvpx-vp9
#   -b:v 2M           matches make_scene_overlays.py, so a cut clip and a
#                     composited one are the same picture
ENCODE_ALPHA = ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0",
                "-b:v", "2M", "-c:a", "libopus"]


def is_alpha(path):
    """A `.webm` here always means a transparent avatar render — that is the
    only kind this pipeline produces or consumes."""
    return str(path).lower().endswith(".webm")


def dec_for(path):
    """The decoder to force, BEFORE `-i`.

    Without this ffmpeg picks a decoder that drops the alpha channel and still
    reports success. Verified 2026-08-22 on a real HeyGen render: the default
    decode reports `yuv420p`, the forced one reports `yuva420p`, same file.
    """
    return ["-c:v", "libvpx-vp9"] if is_alpha(path) else []


def safe_join(rel):
    """Resolve `rel` under CUSTOMERS_ROOT; return None if it would escape."""
    rel = (rel or "").strip("/")
    target = os.path.normpath(os.path.join(CUSTOMERS_ROOT, rel))
    if target != CUSTOMERS_ROOT and not target.startswith(CUSTOMERS_ROOT + os.sep):
        return None
    return target


def resolve_outdir(slug, which=None):
    """
    A `slug` is a literal cache subfolder name, never a path — reject anything
    with a separator so this can't be used to escape CACHE.

    `which` selects one half of a PAIR (`base` or `overlay`). A pair keeps two
    complete extractions side by side, each with its own frames, meta and break
    points, so either can be edited without disturbing the other. Every editing
    endpoint takes it, which is what lets one set of controls drive whichever
    layer is active.
    """
    if not slug or "/" in slug or "\\" in slug or slug in (".", ".."):
        return None
    outdir = os.path.join(build_mod.CACHE, slug)
    if which:
        if which not in ("base", "overlay"):
            return None
        outdir = os.path.join(outdir, which)
    if not os.path.isdir(outdir) or not os.path.isfile(os.path.join(outdir, "meta.json")):
        return None
    return outdir


def frame_count(path):
    """
    How many frames the editor will actually work with, and whether that
    number is known or estimated.

    ffprobe's container `nb_frames` and the extractor DISAGREE: on
    sandbox/01-login-and-code/segment.mp4 the container says 198 and the
    extraction produces 199 real JPEGs. Every other number in this tool --
    the slider, the frame map, what Cut and Save write -- is the extracted
    one, so showing the container's would put a number on screen that
    contradicts the editor by one.

    So: if the clip has been extracted, report meta.json's count and call it
    exact. Otherwise fall back to the container and mark it an estimate, which
    the page renders with a leading ~. Never silently mix the two.
    """
    outdir = os.path.join(build_mod.CACHE, build_mod.slug_for(path))
    meta_p = os.path.join(outdir, "meta.json")
    if os.path.isfile(meta_p):
        try:
            return int(json.load(open(meta_p))["nb_frames"]), True
        except (ValueError, KeyError, OSError, json.JSONDecodeError):
            pass
    try:
        return int(build_mod.probe(path, "nb_frames", stream=True)), False
    except (ValueError, RuntimeError):
        pass
    # VP9 carries no frame count in the container -- `nb_frames` is N/A on every
    # avatar clip, with or without the libvpx-vp9 decoder forced. Counting
    # packets does work and agrees with the extraction (155 on
    # 01-login-and-code/avatar.webm, which extracts to 155 JPEGs), but it reads
    # the whole file, so it is the LAST resort and only for a clip nobody has
    # opened yet. Anything already extracted never reaches this.
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v", "-count_packets",
             "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=60)
        if r.returncode == 0 and r.stdout.strip().isdigit():
            return int(r.stdout.strip()), False
    except (subprocess.SubprocessError, OSError):
        pass
    return None, False


def marks_path(outdir):
    return os.path.join(outdir, "breakpoints.json")


def load_marks(outdir):
    p = marks_path(outdir)
    if not os.path.exists(p):
        return []
    return sorted(set(json.load(open(p)).get("marks", [])))


def save_marks(outdir, marks):
    json.dump({"marks": sorted(set(marks))}, open(marks_path(outdir), "w"), indent=2)


def cache_state(path, log=None):
    """
    (slug, edited) for a file, via ITS OWN cache — the same one /api/save
    writes against, and the same `edited` flag api_open_seq reads for the
    Timeline Scenes dirty icon. Used by api_siblings so a second tool
    (Frame Blender) can show the SAME pristine/dirty state and save through
    the SAME slug, rather than tracking either one separately.

    Building the cache here (if it doesn't exist yet) costs what open_seq
    already costs to show a store's scene list — not a new expense, just
    the same one paid from a second call site. Guarded because a listing
    should degrade to "can't tell" on one bad file, not fail entirely.
    """
    if not path or not os.path.isfile(path):
        return None, False
    try:
        outdir = build_mod.build_frames(path, box=750, alpha_png=is_alpha(path),
                                         log=log or (lambda m: None))
        meta = json.load(open(os.path.join(outdir, "meta.json")))
        return os.path.basename(outdir), bool(meta.get("edited"))
    except Exception:
        return None, False


def build_segment(src, fps, runs, dst, tmp_dir):
    """
    Build one segment from build_mod.group_frame_runs()'s pieces.

    A single ("cut", start, end) — the common case, nothing in this segment
    was ever touched by Frame Editor — goes straight to one ffmpeg call,
    exactly how every segment was cut before Frame Editor existed.

    Multiple runs mean an edit landed inside this segment: each piece is
    built separately and concatenated, mirroring cut_segments.py's own
    cut_with_holds — a "hold" is one still frame extracted from the source
    and looped at the source's OWN fps for the held duration, never slowed
    footage. Verified directly before this was wired in: concatenating a
    still-derived (video-only) piece between two video+audio cuts produces a
    valid file at the right duration, reproducing the source frame for frame.

    LENGTH IS COUNTED IN FRAMES, NOT SECONDS. Every piece used to end with
    `-t duration`, and a duration cutoff drops the last frame whenever that
    frame's own span ends exactly on the boundary: asking for 30 frames
    (1.200s at 25fps) returned 29, and 58 returned 57. Each piece rounded on
    its own, so an edited clip lost one frame PER CUT -- a 89-frame preview
    wrote 87. `-frames:v N` asks for the thing actually wanted and returns
    exactly N.

    The `-ss` seek stays: it was never the problem. Verified by md5 -- the
    frame it lands on is byte-identical to the same frame pulled with an exact
    `select=eq(n,...)`.

    Returns the last subprocess.CompletedProcess, so the caller can check
    .returncode/.stderr exactly as it already does for the single-cut path.
    """
    # Transparency has to survive all three of decode, encode and container. Miss
    # any one and the failure is a black box, not an error.
    dec = dec_for(src)
    enc = ENCODE_ALPHA if is_alpha(src) else ENCODE
    ext = ".webm" if is_alpha(src) else ".mp4"

    if len(runs) == 1 and runs[0][0] == "cut":
        _, s, e = runs[0]
        # Stamped here as well. This is the path an UNEDITED clip takes, and a
        # clip that arrived with a broken clock has to leave with a right one —
        # otherwise a re-save silently preserves the fault it was meant to fix.
        return subprocess.run(
            ["ffmpeg", "-v", "error"] + dec + ["-ss", f"{(s - 1) / fps:.6f}", "-i", src,
             "-frames:v", str(e - s + 1),
             "-vf", f"setpts=N/{fps:g}/TB", "-fps_mode", "passthrough"]
            + enc + ["-y", dst],
            capture_output=True, text=True)

    parts = []
    for i, piece in enumerate(runs):
        if piece[0] == "cut":
            _, s, e = piece
            part = os.path.join(tmp_dir, f"p{i}_cut{ext}")
            r = subprocess.run(
                ["ffmpeg", "-v", "error"] + dec + ["-ss", f"{(s - 1) / fps:.6f}", "-i", src,
                 "-frames:v", str(e - s + 1),
                 "-vf", f"setpts=N/{fps:g}/TB", "-fps_mode", "passthrough"]
                + enc + ["-y", part],
                capture_output=True, text=True)
        else:
            _, frame, count = piece
            # PNG carries alpha, so a held frame keeps it — but only if the
            # frame was DECODED with alpha in the first place.
            still = os.path.join(tmp_dir, f"p{i}_still.png")
            r = subprocess.run(
                ["ffmpeg", "-v", "error"] + dec + ["-ss", f"{(frame - 1) / fps:.3f}",
                 "-i", src, "-frames:v", "1", "-y", still],
                capture_output=True, text=True)
            if r.returncode != 0:
                return r
            part = os.path.join(tmp_dir, f"p{i}_hold{ext}")
            r = subprocess.run(
                ["ffmpeg", "-v", "error", "-loop", "1", "-i", still,
                 "-frames:v", str(count),
                 "-vf", (f"fps={fps:g},setpts=N/{fps:g}/TB,format=yuva420p" if is_alpha(src)
                         else f"fps={fps:g},setpts=N/{fps:g}/TB"),
                 "-fps_mode", "passthrough"] + enc + ["-y", part],
                capture_output=True, text=True)
        if r.returncode != 0:
            return r
        parts.append(part)

    lst = os.path.join(tmp_dir, "list.txt")
    open(lst, "w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
    # `dec` again, and it is easy to miss here. The concat demuxer re-DECODES
    # every part, so without it the alpha is dropped at this last step — and the
    # result still comes out `yuva420p`, because the encoder happily writes an
    # alpha plane that is 100% opaque. Measured exactly that before this line
    # was fixed: a saved clip reported the right pixel format and was solid.
    # ── THE CLOCK IS RESTAMPED HERE, BY FRAME INDEX ─────────────────────────
    # `setpts=N/FRAME_RATE/TB` gives frame N the time N/fps, so a clip's
    # DURATION always follows from its frame COUNT. Without it a piece keeps
    # whatever presentation times its source had, and the concat writes them
    # through unchanged.
    #
    # Measured, on all eleven of ski-demo's avatars: 100% of them were short on
    # the clock. Update Frame Imbalance repeats the LAST frame to even the two
    # tracks up, and a tail pad is the final run in the map — so the frames went
    # in and the duration did not move. Scene 11 held 275 frames inside the 7.99
    # seconds its 266 originals had spanned, reading as 34.42fps. The build
    # matches streams by TIME, so it silently dropped frames (248 became 246 on
    # scene 4) and every clip's audio ended up to 3 seconds before its picture.
    #
    # Nothing was ever lost — the editor counts frames and was right all along.
    # What was missing was the clock, and this is where it is put back.
    return subprocess.run(
        ["ffmpeg", "-v", "error"] + dec + ["-f", "concat", "-safe", "0", "-i", lst]
        # NO setpts here. `N` RESTARTS on every concatenated segment, so a
        # three-part rebuild ended on the last part's own clock: 274 frames
        # reported as 6.56s, which is 164/25 — exactly the length of the final
        # piece. The pieces are each stamped correctly on the way in, and the
        # concat demuxer offsets them by their own durations, so the join is
        # right by construction. Only passthrough is needed, to stop ffmpeg
        # resampling what it was handed.
        + ["-fps_mode", "passthrough"]
        + enc + ["-y", dst],
        capture_output=True, text=True)


def find_repo_root(start):
    """
    Walk up from this file looking for the folder that has a Customers/
    subdirectory — not a hardcoded ../../.. depth, so moving this tool doesn't
    silently point the browser at the wrong place.
    """
    d = start
    for _ in range(8):
        if os.path.isdir(os.path.join(d, "Customers")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    sys.exit("could not find a Customers/ folder above this file — this repo's video "
             "data is gitignored and there is no script that fetches it; see "
             "ToDo.md P3.5")
