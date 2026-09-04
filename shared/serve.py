#!/usr/bin/env python3
"""
Local server for the video players — serves the extracted-frame cache (same as
`python3 -m http.server --directory cache`) and adds a folder-tree browser
rooted at Customers/, so a raw recording can be found and opened without
already knowing its path.

    python3 serve.py [--port 8842]

Routes:
  GET  /browse.html          folder-tree browser, rooted at Customers/
  GET  /api/list?path=<rel>  JSON: subfolders + .mp4/.webm files at that path
  GET  /api/open-pair?base=<rel>&overlay=<rel>
                              layered view — mp4 underneath, alpha WebM on top,
                              each independently editable via `which`
  GET  /api/open?path=<rel>  extracts (or reuses the cache for) that video,
                              returns {"url": "<slug>/viewer.html"}
  GET  /api/marks?slug=<s>   JSON: this video's marked break-point frames
  POST /api/mark             body {slug, frame, on} — set/clear one mark
  POST /api/clear-marks      body {slug} — clear every mark on this video
  POST /api/frames/dup       body {slug, at, count, side} — Frame Editor,
                              Add: insert `count` copies of frame `at`, to
                              `side` ('left' or 'right', default 'right'), in
                              the PREVIEW CACHE only (never the source video)
  POST /api/frames/del       body {slug, at, count, side} — Frame Editor,
                              Subtract: delete up to `count` frames immediately
                              `side` of `at` ('left' default, or 'right') in
                              the preview cache, clamped at either edge
  POST /api/cut              body {slug} — cut the SOURCE video (never the
                              preview JPEGs) at every marked frame; writes
                              Num_1-vN-segment.mp4, Num_2-vN-segment.mp4, ... to
                              the video's sandbox/_cuts/, where N is
                              one version higher than anything already there,
                              so re-cutting keeps every earlier attempt
  POST /api/save              body {slug} — rebuild the WHOLE current edited
                              clip (frame 1..N, via frame_map) and OVERWRITE
                              the file this viewer opened. The overwritten
                              file is archived to z_History/ first. This is
                              distinct from /api/cut: cut slices at MARKS into
                              a fresh versioned file and never touches the
                              source; save has no marks at all and replaces
                              the source in place — for committing Frame
                              Editor's length change back into the one file
                              this viewer is for. On success the cache is
                              re-extracted from the file just written, so the
                              editor stops reporting edits it has already
                              applied and a second save cannot rebuild against
                              frame numbers the shortened file no longer has.
  POST /api/clear-edits       body {slug} — discard every Frame Editor edit
                              and every break point, and re-extract a clean
                              preview straight from the source. The SOURCE
                              FILE is never touched, only the cache — the
                              opposite of /api/save, which writes the source
                              and leaves the cache's edit state alone.
  POST /api/reset-editor      body {slug} — delete this video's ENTIRE cache
                              (every extracted frame, meta.json,
                              breakpoints.json, viewer.html) — the tool's
                              whole regenerable working copy for this video.
                              The SOURCE FILE is never touched; reopening it
                              from Browse starts over from nothing. Distinct
                              from /api/clear-edits: that keeps this video
                              loaded and just discards edits/marks, this
                              unloads the video entirely.
  GET  /<slug>/viewer.html, /<slug>/frames/*.jpg, ...
                              static files — unchanged from before

`path` is always relative to Customers/ and is checked to stay inside it —
this server does not browse or open anything outside that folder, even if a
request tries to walk out of it with `..`. `slug` for the mark/cut routes is
checked the same way against the frame cache, not the filesystem at large.
"""
import functools
import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import tempfile
import time
import urllib.parse

# One server, several players. It lives in shared/ because the routes, the
# cache and the Customers/ boundary are common to all of them; what differs is
# only which module renders the page at the end.
HERE = os.path.dirname(os.path.abspath(__file__))          # <repo>/shared
ROOT = os.path.dirname(HERE)                                # <repo>
CACHE = os.path.join(ROOT, "cache")                         # shared by every player
sys.path.insert(0, ROOT)                                    # for the player packages
# frames.py, paths.py and vtt.py used to live in shared/ beside this file.
# Since 2026-09-03 they are editor_base/ — one copy instead of three. The
# files still here under those names are thin re-export shims, kept only so
# the scripts in build/ keep importing them unchanged; this module reaches
# past the shims and imports the real thing.
from editor_base import frames as build_mod                 # noqa: E402
from segment_avatar_editor import player as sae             # noqa: E402
from editor_base import paths as PTH                        # noqa: E402
# The word count comes from vtt.py rather than being written again here. It is
# not `line.split()`: a token with no letter or digit is punctuation standing
# alone, the voice does not say it, and counting it added 0.29s of imaginary
# speech to every line written with a spaced em dash.
from editor_base import vtt as vtt_mod                      # noqa: E402

# This server extracts into the repo-root cache/ and renders the Segment and
# Avatar Editor's page, so it points editor_base at both.
build_mod.use_cache(CACHE)
build_mod.use_player("segment_avatar_editor._splitter_player")

# Must match cut_segments.py's ENCODE exactly — this is the same "locked
# encode standard" every other segment in this project is cut with.
# `-crf 18` is explicit on purpose. x264's default is 23, which measured
# SSIM 0.9994 against the raw — fine, but this footage is fine UI TEXT on flat
# dark panels, where SSIM flatters a soft result. 18 costs ~35% more bytes on a
# file that is already tiny (a 14.8s segment went 137KB -> 186KB) and there is
# no reason to spend the quality. Verified 2026-08-21 against CRF 15 and 12 too:
# below 18 the picture stops changing and only the file grows.
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
    sys.exit("could not find a Customers/ folder above shared/ — run setup_demo.py first")


REPO_ROOT = find_repo_root(HERE)
CUSTOMERS_ROOT = os.path.join(REPO_ROOT, "Customers")


# ── session log ─────────────────────────────────────────────────────────────
# A record of real editing, kept as you work. The test writes its own log; this
# is the other half — what actually happened to your files, in the same shape.
#
# One file per DAY, appended, with a header each time the server starts. Only
# calls that CHANGE something are logged; opening a clip is logged too, because
# a line saying what you were working on is what makes the rest readable.
SESSION_DIR = os.path.join(ROOT, "logs")
SESSION_LOG = os.path.join(SESSION_DIR, f"editor_{time.strftime('%Y%m%d')}.log")

# endpoint -> (what to call it, which payload keys are worth showing)
ACTIONS = {
    "/api/frames/dup":      ("+ Frame",      ("at", "count", "side")),
    "/api/frames/del":      ("- Frame",      ("at", "count", "side")),
    "/api/frames/dup-span": ("+ Zone",       ("a", "b")),
    "/api/frames/del-span": ("- Zone",       ("a", "b")),
    "/api/frames/restore":  ("Undo",         ()),
    "/api/frames/paste":    ("Paste frame",  ("from", "at")),
    "/api/mark":            ("Mark",         ("frame", "on")),
    "/api/clear-marks":     ("Unmark all",   ()),
    "/api/save":            ("Save scene",   ()),
    "/api/cut":             ("Cut scene",    ()),
    "/api/clear-edits":     ("Discard edits", ()),
    "/api/reset-editor":    ("Reset editor", ()),
    "/api/join":            ("Join",         ("ns", "label", "tracks")),
    "/api/split":           ("Split",        ("n", "at", "labels", "tracks")),
    "/api/line":            ("Edit line",    ("n",)),
    "/api/renumber-clear":  ("Lift lock",    ()),
    "/api/handoff":         ("Hand off",     ("version", "names")),
    "/api/archive":         ("Archive",      ("folder",)),
    "/api/save-archive":    ("Save All archive", ("root",)),
    "/api/open":            ("Open clip",    ("path",)),
    "/api/open-pair":       ("Open layered", ("base",)),
    "/api/open-seq":        ("Open timeline", ("root", "ns")),
    "/api/open-pair-go":    ("Open layered", ("base",)),
    "/api/open-seq-go":     ("Open timeline", ("root", "ns")),
    "/api/load_video":      ("FB: Load video", ("root",)),
    # Frame Blender's own actions. Save/Undo used to proxy here and log
    # themselves on the way through; since 2026-09-02 Frame Blender's own
    # save_scene()/undo_scene() run standalone and call this SAME
    # session_log() directly with these SAME two keys ("/api/save",
    # "/api/frames/restore") instead — no new entries needed, the existing
    # "Save scene"/"Undo" labels above already cover it. Logged into this
    # SAME file (same day, same repo, same path formula) even though
    # frame_blender/serve.py is a separate process — one editing record
    # regardless of which tool acted.
    "/build_clip":          ("FB: Build clip", ("n",)),
    "/api/save_mp4":        ("FB: Save MP4",   ("n",)),
    "/api/load_store":      ("FB: Load store", ("path",)),
}
# result keys worth showing, in the order they read best
RESULT_KEYS = ("nb_frames", "count", "version", "duration_s", "joined", "split",
               "label", "labels", "line", "renamed", "url", "slug")


def session_start(port):
    os.makedirs(SESSION_DIR, exist_ok=True)
    ver_p = os.path.join(ROOT, "segment_avatar_editor", "VERSION")
    ver = open(ver_p).read().strip() if os.path.isfile(ver_p) else "?"
    with open(SESSION_LOG, "a") as fh:
        fh.write(f"\nEditor Session:  {time.strftime('%Y-%m-%dT%H:%M:%S')}\n"
                 f"Player:          Segment and Avatar Editor v{ver}\n"
                 f"Server:          http://localhost:{port}\n\n")


SESSION_OFF = False       # set by --no-session-log


def session_log(path, payload, result, status):
    """One line per action. Never raises: a log that can break the editor is
    worse than no log."""
    entry = ACTIONS.get(path)
    if entry is None or SESSION_OFF:
        return
    label, keys = entry
    try:
        args = " ".join(f"{k}={payload.get(k)}" for k in keys if payload.get(k) is not None)
        # what it acted on: a cache slug for frame work, a store for the rest
        who = payload.get("slug") or payload.get("root") or ""
        if path == "/api/open":
            who = os.path.basename(os.path.dirname(str(payload.get("path", "")))) or ""
            args = os.path.basename(str(payload.get("path", "")))
        res = result if isinstance(result, dict) else {}
        if status != 200 or res.get("error"):
            tail = f"REFUSED: {res.get('error', status)}"
        else:
            tail = "  ".join(f"{k}={res[k]}" for k in RESULT_KEYS if k in res)
        with open(SESSION_LOG, "a") as fh:
            fh.write(f"{time.strftime('%H:%M:%S')}  {label:<14} {who:<26} "
                     f"{args}  {tail}".rstrip() + "\n")
    except Exception:
        pass


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
    outdir = os.path.join(CACHE, slug)
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
    outdir = os.path.join(CACHE, build_mod.slug_for(path))
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


def speech_span(outdir):
    """
    WHERE THE VOICE ACTUALLY IS inside this clip's audio — not one span, but
    every run of speech, with the pauses between them left out.

    Two things made a single span wrong, and both were reported from the chair:

      * A scene's avatar does not begin talking on its first frame. Sarah
        settles into shot first, and how long that takes differs per scene —
        measured on ski-demo, 1.64s on the opening and 0.11s on the two after
        it. An offset guessed once is wrong everywhere but one scene.

      * Inside the span she does not talk at a constant rate. She pauses
        between sentences, then speaks faster than an even spread expects, so
        a highlight laid evenly over the whole span drifts ahead, waits, and
        drifts ahead again. Spreading the words over the SPEECH ONLY, run by
        run, holds it against her.

    Measured with ffmpeg's own silence detector rather than estimated, and
    written into the clip's meta.json the first time so it is paid for once —
    about 0.05s per clip. Adding keys there is safe: the cache-validity check
    compares a fixed list (source, size, mtime, box, alpha_png) and ignores
    everything else.

    Returns (start, end, runs). `runs` is [[a, b], ...] in seconds. All three
    are None/empty for a clip with no audio. Only the editor's highlight reads
    them; nothing that writes a file does.
    """
    meta_p = os.path.join(outdir, "meta.json")
    try:
        meta = json.load(open(meta_p))
    except OSError:
        return None, None, []
    if "speech_runs" in meta:
        return meta.get("speech_start"), meta.get("speech_end"), meta.get("speech_runs") or []

    audio = os.path.join(outdir, "audio.m4a")
    start = end = None
    runs = []
    if os.path.isfile(audio):
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", audio,
             # -45dB is below room tone and above nothing at all. 0.10s so the
             # ordinary gap between two words is not read as a pause; anything
             # longer than that is one she actually took.
             "-af", "silencedetect=noise=-45dB:d=0.10", "-f", "null", "-"],
            capture_output=True, text=True)
        log = r.stderr
        starts = [float(x) for x in re.findall(r"silence_start: ([\d.-]+)", log)]
        ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
        try:
            dur = float(build_mod.probe(audio, "duration"))
        except (ValueError, RuntimeError):
            dur = 0.0

        # Walk the silences and keep what is BETWEEN them. A silence with no
        # matching end is one that runs to the end of the file, so the voice
        # stopped where it opened and there is nothing after it.
        pos = 0.0
        for k, st in enumerate(starts):
            if st > pos + 0.01:
                runs.append([round(pos, 3), round(st, 3)])
            if k >= len(ends):
                pos = None
                break
            pos = ends[k]
        if pos is not None and dur - pos > 0.01:
            runs.append([round(pos, 3), round(dur, 3)])

        if runs:
            start, end = runs[0][0], runs[-1][1]

    meta["speech_start"], meta["speech_end"], meta["speech_runs"] = start, end, runs
    try:
        json.dump(meta, open(meta_p, "w"), indent=2)
    except OSError:
        pass
    return start, end, runs


def marks_path(outdir):
    return os.path.join(outdir, "breakpoints.json")


def load_marks(outdir):
    p = marks_path(outdir)
    if not os.path.exists(p):
        return []
    return sorted(set(json.load(open(p)).get("marks", [])))


def save_marks(outdir, marks):
    json.dump({"marks": sorted(set(marks))}, open(marks_path(outdir), "w"), indent=2)


def derive_segments_dir(source):
    """
    Where a cut lands: the video's `dev/`.

    REVERSED 2026-08-26, at the user's instruction. From 2026-08-22 this was
    sandbox/ and dev/ was read-only, because a tool still under development must
    not be the only thing standing between a bad edit and a paid HeyGen render —
    one had already shipped a bug that showed stale frames after a delete.

    That protection now comes from ARCHIVING rather than from read-only-ness: a
    deposit into dev/ moves the generation it replaces into
    dev/z_History/<date>-v_N/ first, so nothing is overwritten and the previous
    cut is always one folder away. It is the better shape anyway — a fresh cut
    IS the start of a video, and it belongs where the build looks for its
    source.

    Detected from the source path's own shape rather than a hardcoded depth:

        .../help-videos/raw_mp4/<file>          -> newest videos/<slug>/dev/_cuts
        .../videos/<slug>/{dev,sandbox}/...     -> that video's dev/_cuts
        anything else                           -> a sandbox/ beside the source

    Cutting a RAW recording is still allowed — that is where segments come from
    — but its output goes to sandbox like everything else.

    ⚠ Before this it targeted `final/segments/`, which no longer exists after
    the dev/ restructure. A cut would have landed in a fresh empty folder,
    invisible to everything downstream: the same silent divergence this
    function's previous note warned about, caused the same way.
    """
    d = os.path.abspath(os.path.dirname(source))
    parts = d.split(os.sep)

    # inside a video folder already? use its sandbox
    if "videos" in parts:
        i = len(parts) - 1 - parts[::-1].index("videos")
        if i + 1 < len(parts):
            return os.path.join(os.sep.join(parts[: i + 2]), "dev", "_cuts")

    # a raw recording: find the store's newest video folder
    if os.path.basename(d) == "raw_mp4":
        hv = os.path.dirname(d)
        vids = os.path.join(hv, "videos")
        if os.path.isdir(vids):
            subs = sorted(x for x in os.listdir(vids) if os.path.isdir(os.path.join(vids, x)))
            if subs:
                return os.path.join(vids, subs[-1], "dev", "_cuts")
        # an unsplit store still has final/
        if os.path.isdir(os.path.join(hv, "final")):
            return os.path.join(hv, "final", "dev", "_cuts")

    return os.path.join(d, "dev", "_cuts")


# Openable in the viewer. `.webm` was added 2026-08-21 so the AVATAR clips can be
# inspected frame by frame like anything else — the morphs, the narration renders
# and the close-out are where the hard-to-see faults live (a mouth moving with no
# audio behind it, a pose that pops), and they were previously only reviewable by
# building a whole video and watching it.
VIDEO_EXTS = (".mp4", ".webm")

SEGMENT_NAME_RE = re.compile(r"^Num_(\d+)-v(\d+)-segment\.(?:mp4|webm)$")


def next_version(dest_dir):
    """
    Every cut in dest_dir is one BATCH, all sharing one version number, one
    higher than anything already there — so re-cutting after moving a break
    point keeps every earlier attempt (Num_1-v1-segment.mp4, Num_1-v2-segment.mp4,
    ...) instead of overwriting it. Derived by scanning the real files on
    disk, not a counter kept anywhere that could drift from what's there.
    """
    if not os.path.isdir(dest_dir):
        return 1
    seen = (SEGMENT_NAME_RE.match(name) for name in os.listdir(dest_dir))
    versions = [int(m.group(2)) for m in seen if m]
    return max(versions, default=0) + 1


# What each track is called on disk. One mapping, so a track added here cannot
# be written under the wrong name by one operation and the right one by another.
TRACK_FILE = {"segment": "segment.mp4", "avatar": "avatar.webm",
              "narration": "narration.webm"}


def make_gap_filler(like, frames, dst, log=lambda m: None):
    """
    A transparent, silent clip `frames` long, matching `like`'s size and rate.

    Used where a scene HAS NO track the others have — the opening has no
    narration render. Concatenating without it makes the next scene's narration
    start at frame 1 instead of after the opening, so Sarah says the login line
    over the intro. The filler holds that time open.

    Transparent and silent is the honest content: for the opening's duration
    there IS no narration, and that is what "no narration" looks like once it
    has to occupy time.
    """
    w = build_mod.probe(like, "width", stream=True, dec=["-c:v", "libvpx-vp9"])
    h = build_mod.probe(like, "height", stream=True, dec=["-c:v", "libvpx-vp9"])
    num, _, den = build_mod.probe(like, "r_frame_rate", stream=True,
                        dec=["-c:v", "libvpx-vp9"]).partition("/")
    fps = f"{num}/{den or 1}"
    r = subprocess.run(
        ["ffmpeg", "-v", "error",
         # `,format=yuva420p` in the FILTER, not just -pix_fmt on the output.
         # Without it the colour source hands over yuv420p and the encoder adds
         # an OPAQUE alpha channel — measured 255 everywhere. The filler would
         # have blacked the opening out instead of being invisible.
         "-f", "lavfi", "-i", f"color=c=black@0.0:s={w}x{h}:r={fps},format=yuva420p",
         "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
         "-frames:v", str(frames)] + ENCODE_ALPHA + ["-shortest", "-y", dst],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"could not build the {frames}-frame filler: {r.stderr[-300:]}")
    log(f"  filled a {frames}-frame gap with a transparent silent clip")
    return dst


def renumber_sandbox_folders(final, scenes):
    """
    Rename sandbox folders so their NN- prefix matches the scene numbers.

    paths.sandbox_dir() finds a scene's folder by that prefix, so renumbering
    the script WITHOUT renaming the folders makes every moved scene
    unresolvable -- sandbox_only() returns None and the scene simply vanishes
    from the editor. Measured exactly that: after a join, scene 2's folder was
    still 03-logout-menu and its segment came back None.

    Matched by LABEL, not by the old number, because the numbers are what just
    changed. Renamed in TWO passes through a temporary name, so a folder is
    never renamed onto one that has not moved out of the way yet -- renumbering
    3->2 while 2 still exists is the normal case, not the exception.

    dev/ is deliberately NOT touched. It is the untouched copy of what was
    there before, and after a join or split it genuinely no longer mirrors
    sandbox -- pretending otherwise would lose the record.
    """
    root = PTH.sandbox_root(final)
    if not os.path.isdir(root):
        return []
    cur = {}
    for d in sorted(os.listdir(root)):
        m = re.match(r"^(\d+)-(.+)$", d)
        if m and os.path.isdir(os.path.join(root, d)):
            cur[m.group(2)] = os.path.join(root, d)
    moves = []
    for sc in scenes:
        lab = sc.get("label")
        if not lab or lab not in cur:
            continue
        want = os.path.join(root, f"{sc['n']:02d}-{lab}")
        if os.path.abspath(cur[lab]) != os.path.abspath(want):
            moves.append((cur[lab], want))
    staged = []
    for src, dst in moves:
        tmp = src + ".renumbering"
        os.rename(src, tmp)
        staged.append((tmp, dst))
    for tmp, dst in staged:
        os.rename(tmp, dst)
    return [os.path.basename(d) for _, d in moves]


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


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        # Only the three ways IN are logged, and only they need to be: a line
        # saying what you opened is what makes the edits under it readable.
        # Every other GET is a frame image or a poll, and logging those would
        # bury the record in its own noise.
        if parsed.path in ("/api/open", "/api/open-pair", "/api/open-seq",
                           "/api/open-pair-go", "/api/open-seq-go"):
            qs = urllib.parse.parse_qs(parsed.query)
            flat = {k: v[0] for k, v in qs.items() if v}
            self._last_json, self._last_status = None, 200
            self.route_get(parsed)
            return session_log(parsed.path, flat, self._last_json, self._last_status)
        return self.route_get(parsed)

    def route_get(self, parsed):
        if parsed.path == "/api/list":
            return self.api_list(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/stores":
            return self.api_stores()
        if parsed.path == "/api/open":
            return self.api_open(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/open-pair":
            return self.api_open_pair(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/open-pair-go":
            return self.api_open_pair_go(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/open-seq-go":
            return self.api_open_seq_go(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/open-seq":
            return self.api_open_seq(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/siblings":
            return self.api_siblings(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/renumber-state":
            return self.api_renumber_state(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/vtt":
            return self.api_vtt(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/frames/map":
            return self.api_map(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/marks":
            return self.api_marks(urllib.parse.parse_qs(parsed.query))
        if parsed.path in ("/", "/browse.html"):
            return self.send_html(BROWSE_HTML)
        return super().do_GET()

    def do_POST(self):
        """Parse, route, then log. Wrapped rather than logged inside each
        handler: there are fifteen of them and one forgotten call is a hole in
        the record that nothing would ever point at."""
        parsed = urllib.parse.urlsplit(self.path)
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return self.send_json({"error": "malformed JSON body"}, 400)
        self._last_json, self._last_status = None, 200
        # One writer at a time per cache folder. Taken HERE rather than inside
        # each of the nine handlers that mutate one, for the same reason the
        # session log is: nine places is nine chances to forget, and the one
        # forgotten is the one that corrupts a cache at two clicks a second.
        outdir = (resolve_outdir(payload.get("slug"), payload.get("which"))
                  if payload.get("slug") else None)
        if outdir:
            with build_mod.dir_lock(outdir):
                self.route_post(parsed, payload)
        else:
            self.route_post(parsed, payload)
        session_log(parsed.path, payload, self._last_json, self._last_status)

    def route_post(self, parsed, payload):
        if parsed.path == "/api/mark":
            return self.api_mark(payload)
        if parsed.path == "/api/clear-marks":
            return self.api_clear_marks(payload)
        if parsed.path == "/api/frames/dup":
            return self.api_frames_dup(payload)
        if parsed.path == "/api/frames/paste":
            return self.api_paste(payload)
        if parsed.path == "/api/frames/del":
            return self.api_frames_del(payload)
        if parsed.path == "/api/renumber-clear":
            return self.api_renumber_clear(payload)
        if parsed.path == "/api/split":
            return self.api_split(payload)
        if parsed.path == "/api/join":
            return self.api_join(payload)
        if parsed.path == "/api/handoff":
            return self.api_handoff(payload)
        if parsed.path == "/api/archive":
            return self.api_archive(payload)
        if parsed.path == "/api/save-archive":
            return self.api_save_archive(payload)
        if parsed.path == "/api/line":
            return self.api_line(payload)
        if parsed.path == "/api/frames/restore":
            return self.api_restore(payload)
        if parsed.path == "/api/frames/dup-span":
            return self.api_span(payload, "dup")
        if parsed.path == "/api/frames/del-span":
            return self.api_span(payload, "del")
        if parsed.path == "/api/cut":
            return self.api_cut(payload)
        if parsed.path == "/api/save":
            return self.api_save(payload)
        if parsed.path == "/api/clear-edits":
            return self.api_clear_edits(payload)
        if parsed.path == "/api/reset-editor":
            return self.api_reset_editor(payload)
        return self.send_json({"error": f"no such route: {parsed.path}"}, 404)

    def send_json(self, obj, status=200):
        self._last_json, self._last_status = obj, status
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html, status=200):
        body = html.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def api_list(self, qs):
        rel = qs.get("path", [""])[0]
        target = safe_join(rel)
        if target is None or not os.path.isdir(target):
            return self.send_json({"error": f"not a folder under Customers/: {rel}"}, 400)
        dirs, files = [], []
        for name in sorted(os.listdir(target), key=str.lower):
            if name.startswith("."):
                continue
            full = os.path.join(target, name)
            childrel = f"{rel.rstrip('/')}/{name}" if rel else name
            if os.path.isdir(full):
                # A STORE folder is any folder with its own help-videos/raw_mp4/ —
                # derived by checking the real filesystem, not assumed from depth,
                # so this works whether Customers/ is 2 levels deep or a hundred.
                # Clicking the row still jumps straight to raw_mp4/ (unchanged
                # default). A second shortcut, shown right beside it, jumps to
                # help-videos/final/segments/ when that folder exists too — the
                # cut segments this tool itself produces, so opening one for
                # frame-by-frame review doesn't mean walking raw_mp4 -> final ->
                # segments by hand.
                raw = os.path.join(full, "help-videos", "raw_mp4")
                raw_jump = f"{childrel}/help-videos/raw_mp4" if os.path.isdir(raw) else None
                segs = os.path.join(full, "help-videos", "final", "segments")
                segments_jump = f"{childrel}/help-videos/final/segments" if os.path.isdir(segs) else None
                dirs.append({"name": name, "path": childrel,
                             "jump": raw_jump, "segments_jump": segments_jump})
            elif name.lower().endswith(VIDEO_EXTS):
                files.append({"name": name, "path": childrel, "size": os.path.getsize(full)})
        parent = None
        if rel.strip("/"):
            parts = rel.strip("/").split("/")[:-1]
            parent = "/".join(parts)
        self.send_json({"path": rel.strip("/"), "parent": parent, "dirs": dirs, "files": files})

    def api_stores(self):
        """
        For the timeline editor's Load button, added 2026-08-29: every
        Business/store under Customers/ that has at least one video folder
        with a script.json ready to open (see paths.script() for where that
        can live), and for each, that store's list of video folders with
        their scene numbers.

        script.json is the check, not sandbox/ — a video can exist with a
        script and no sandbox yet built (a fresh store, before its first
        Backup Scenes/rebuild), and Load should still be able to find it;
        /api/open-seq-go is what actually needs sandbox/ scene folders to
        exist, and fails on its own if they don't, same as it always has.

        Two levels down from Customers/ is assumed to be Business/store —
        the same assumption /api/list's own STORE-folder detection makes,
        just walked directly here instead of one click at a time, since a
        picker choosing between two whole customer businesses first is a
        step nobody asked for.
        """
        out = []
        if not os.path.isdir(CUSTOMERS_ROOT):
            return self.send_json({"stores": out})
        for biz in sorted(os.listdir(CUSTOMERS_ROOT), key=str.lower):
            biz_dir = os.path.join(CUSTOMERS_ROOT, biz)
            if biz.startswith(".") or not os.path.isdir(biz_dir):
                continue
            for store in sorted(os.listdir(biz_dir), key=str.lower):
                store_dir = os.path.join(biz_dir, store)
                videos_root = os.path.join(store_dir, "help-videos", "videos")
                if store.startswith(".") or not os.path.isdir(videos_root):
                    continue
                videos = []
                for vname in sorted(os.listdir(videos_root), key=str.lower):
                    vdir = os.path.join(videos_root, vname)
                    script_p = PTH.script(vdir)
                    if vname.startswith(".") or not os.path.isfile(script_p):
                        continue
                    try:
                        doc = json.load(open(script_p))
                        ns = sorted(x["n"] for x in doc.get("scenes", []) if "n" in x)
                    except (OSError, ValueError, KeyError):
                        ns = []
                    has_sandbox = os.path.isdir(PTH.sandbox_root(vdir))
                    videos.append({"name": vname,
                                   "root": f"{biz}/{store}/help-videos/videos/{vname}",
                                   "scenes": ns, "has_sandbox": has_sandbox})
                if videos:
                    out.append({"business": biz, "store": store, "videos": videos})
        self.send_json({"stores": out})

    def api_open(self, qs):
        rel = qs.get("path", [""])[0]
        target = safe_join(rel)
        if target is None or not os.path.isfile(target) or not target.lower().endswith(VIDEO_EXTS):
            return self.send_json({"error": f"not a video under Customers/: {rel}"}, 400)
        try:
            # An ALPHA clip has to be extracted as PNG or its transparency is
            # gone. .webm was added to VIDEO_EXTS so an avatar could be opened
            # here and inspected frame by frame like anything else — but this
            # never passed alpha_png, so it came back flat, and the very thing
            # you open an avatar to look at was the thing that got dropped.
            # open-pair and open-seq both got this right; this did not.
            outdir = build_mod.build_frames(
                target, alpha_png=is_alpha(target),
                log=lambda m: sys.stderr.write(m + "\n"))
        except RuntimeError as e:
            return self.send_json({"error": str(e)}, 500)
        slug = os.path.basename(outdir)
        self.send_json({"url": f"{slug}/viewer.html"})

    def api_open_pair(self, qs, redirect=False):
        """
        Open TWO clips as one layered view: an mp4 running underneath and an
        alpha WebM on top, which is how the finished video is actually built.

        Each half gets its OWN complete extraction under `<slug>/base/` and
        `<slug>/overlay/` — frames, meta and break points — so either can be cut
        or frame-edited without touching the other. Compositing them to a single
        set of frames would have been less code and would have thrown that away.

        The overlay is extracted as PNG with its real alpha; the browser stacks
        the two <img>. That is also why the base stays JPEG: only the layer that
        needs transparency pays for it.
        """
        b_rel, o_rel = qs.get("base", [""])[0], qs.get("overlay", [""])[0]
        base, over = safe_join(b_rel), safe_join(o_rel)
        for label, p, rel in (("base", base, b_rel), ("overlay", over, o_rel)):
            if p is None or not os.path.isfile(p) or not p.lower().endswith(VIDEO_EXTS):
                return self.send_json({"error": f"{label} is not a video under Customers/: {rel}"}, 400)
        import hashlib
        slug = "pair_" + hashlib.sha1((base + "|" + over).encode()).hexdigest()[:10]
        outdir = os.path.join(CACHE, slug)
        os.makedirs(outdir, exist_ok=True)
        log = lambda m: sys.stderr.write(m + "\n")
        try:
            bmeta_dir = build_mod.build_frames(base, out=os.path.join(outdir, "base"),
                                               box=750, log=log)
            ometa_dir = build_mod.build_frames(over, out=os.path.join(outdir, "overlay"),
                                               box=750, log=log, alpha_png=True)
        except RuntimeError as e:
            return self.send_json({"error": str(e)}, 500)
        bmeta = json.load(open(os.path.join(bmeta_dir, "meta.json")))
        ometa = json.load(open(os.path.join(ometa_dir, "meta.json")))
        sae.write_pair(outdir, bmeta, ometa, box=750,
                                     base_rel=b_rel, overlay_rel=o_rel)
        if redirect:
            self.send_response(302)
            self.send_header("Location", f"/{slug}/viewer.html")
            self.end_headers()
            return
        self.send_json({"url": f"{slug}/viewer.html", "slug": slug,
                        "base_frames": bmeta["nb_frames"], "overlay_frames": ometa["nb_frames"]})

    def api_open_pair_go(self, qs):
        """
        Same as /api/open-pair but redirects straight to the viewer.

        The scene list needs a plain navigation, not a fetch-then-assign: the
        extraction can take a while and a link that simply goes somewhere is
        both simpler and honest about what is happening.
        """
        self.api_open_pair(qs, redirect=True)

    def api_open_seq_go(self, qs):
        """Build the timeline and redirect — extraction can take a while and a
        link that simply goes somewhere is honest about that."""
        self.api_open_seq(qs, redirect=True)

    def api_open_seq(self, qs, redirect=False):
        """
        Open SEVERAL scenes as one timeline.

        A scene on its own cannot show the thing that most often goes wrong —
        how one scene JOINS the next. A hard cut, a pose that jumps, a voice that
        starts before the picture settles: all of them live at a boundary, and a
        single-clip viewer has no boundaries in it.

        Each scene keeps its OWN extraction (they are ordinary pairs, cached and
        reused), and the sequence viewer holds a manifest that maps a global
        frame to a scene plus a local frame. Concatenating the frames into one
        new cache would have been simpler and would have thrown away both the
        reuse and the ability to say WHICH scene you are looking at.
        """
        root_rel = qs.get("root", [""])[0]
        ns = [x for x in qs.get("ns", [""])[0].split(",") if x.strip()]
        root = safe_join(root_rel)
        if root is None or not os.path.isdir(root):
            return self.send_json({"error": f"not a folder under Customers/: {root_rel}"}, 400)
        if not ns:
            return self.send_json({"error": "no scenes selected"}, 400)

        labels = {n: lab for n, lab in PTH.scenes_from_script(root)}
        log = lambda m: sys.stderr.write(m + "\n")
        manifest, missing = [], []
        for raw in ns:
            try:
                n = int(raw)
            except ValueError:
                continue
            seg = av_seg = None
            sb = PTH.sandbox_only(root, n, labels.get(n))
            seg, av_seg = sb["segment"], sb["avatar"]
            label = labels.get(n)
            if seg is None:                      # a bookend: not a script scene
                sroot = PTH.sandbox_root(root)
                for d in sorted(os.listdir(sroot)) if os.path.isdir(sroot) else []:
                    m = re.match(rf"^{n:02d}-(.+)$", d)
                    if m:
                        cand = os.path.join(sroot, d, "segment.mp4")
                        if os.path.isfile(cand):
                            seg, label = cand, m.group(1)
                            a = os.path.join(sroot, d, "avatar.webm")
                            av_seg = a if os.path.isfile(a) else None
                        break
            if seg is None:
                missing.append(n)
                continue
            try:
                bdir = build_mod.build_frames(seg, box=750, log=log)
                odir = (build_mod.build_frames(av_seg, box=750, log=log, alpha_png=True)
                        if av_seg else None)
            except RuntimeError as e:
                return self.send_json({"error": f"scene {n}: {e}"}, 500)
            bm = json.load(open(os.path.join(bdir, "meta.json")))
            om = json.load(open(os.path.join(odir, "meta.json"))) if odir else None
            # A bookend has no script node, so no label — but its FOLDER is named
            # (`00-opening`). Falling back to the number alone made the timeline
            # say "00", which is the one thing the reader already knows.
            if not label:
                folder = os.path.basename(os.path.dirname(seg))
                label = folder[3:] if re.match(r"^\d\d-", folder) else folder
            manifest.append({
                "n": n, "label": label or f"{n:02d}",
                # A bookend (00-opening, 99-closing) is a real folder with no row
                # in script.json. It can sit on a timeline — that is the point,
                # you watch the joins — but it cannot be joined or split, because
                # both rewrite the scene list and it is not in one. The page has
                # to know that BEFORE it offers to do it.
                "in_script": n in labels,
                # Whether this scene has a raw narration render. The opening has
                # none — it is built from TWO HeyGen clips plus the morph, so its
                # avatar IS the finished article and no single raw clip sits
                # behind it. A join across that gap has to fill it or the next
                # scene's narration slides forward on top of the opening.
                "has_narration": bool(sb["narration"]) if sb else False,
                # HAS THIS TRACK GOT EDITS THAT THE FILE HAS NOT?
                #
                # Read from the CACHE, which is where an edit actually lives
                # until it is saved. The page used to decide this from its own
                # undo history, and a reload throws that away — so ten scenes
                # padded by Update Frame Imbalance came back reading as
                # pristine, and Save All answered "no scene has unsaved edits"
                # over a cache full of them.
                #
                # `edited` is not derivable from the frame count either: equal
                # adds and deletes leave the count where it started with the
                # clip genuinely changed.
                "base_edited": bool(bm.get("edited")),
                "over_edited": bool(om.get("edited")) if om else False,
                "base_slug": os.path.basename(bdir), "base_n": bm["nb_frames"],
                "base_ext": bm.get("ext", ".jpg"), "base_audio": bool(bm.get("has_audio")),
                # WHEN THE VOICE STARTS, per scene. Sarah settles into shot
                # before she talks, and how long that takes differs scene to
                # scene, so the editor cannot place a spoken word from the
                # frame number alone. Read from the AVATAR, which is the clip
                # carrying her voice; measured once and cached in its meta.
                # WHERE HER VOICE IS, run by run, so the highlight can hold
                # through a pause instead of drifting past it. Read from the
                # AVATAR, which is the clip carrying her voice.
                "speech_runs": (speech_span(odir)[2] if odir else []),
                "over_slug": os.path.basename(odir) if odir else None,
                "over_n": om["nb_frames"] if om else 0,
                "over_ext": om.get("ext", ".png") if om else ".png",
                "over_audio": bool(om.get("has_audio")) if om else False,
                # The two SOURCE paths, so the read-only alert can offer to open
                # this scene where cutting actually happens. Without them the
                # alert could only say no.
                "base_rel": os.path.relpath(seg, CUSTOMERS_ROOT),
                "over_rel": os.path.relpath(av_seg, CUSTOMERS_ROOT) if av_seg else None,
                "fps": bm["fps"]})
        if not manifest:
            return self.send_json({"error": f"none of {ns} resolved"}, 400)

        import hashlib
        slug = "seq_" + hashlib.sha1(("|".join(str(m["n"]) for m in manifest)
                                       + root).encode()).hexdigest()[:10]
        outdir = os.path.join(CACHE, slug)
        os.makedirs(outdir, exist_ok=True)
        sae.write_seq(outdir, manifest, box=750,
                                   root_rel=os.path.relpath(root, CUSTOMERS_ROOT))
        if redirect:
            self.send_response(302)
            self.send_header("Location", f"/{slug}/viewer.html")
            self.end_headers()
            return
        self.send_json({"url": f"{slug}/viewer.html", "slug": slug,
                        "scenes": [m["n"] for m in manifest], "missing": missing})

    def api_siblings(self, qs):
        """
        Every scene of this store, resolved — not a directory listing.

        The old version parsed `Num_N-vV-segment.mp4` out of one folder. After
        the dev/ restructure a scene's footage lives in
        `dev/<NN>-<label>/segment-v6.mp4`, and a store may be half-migrated, so
        the only correct answer comes from paths.py. It also means a scene now
        reports which LAYER each part came from — sandbox, dev or flat — because
        an override you have forgotten about is the failure this whole layout
        makes possible.
        """
        rel = qs.get("path", [""])[0]
        target = safe_join(rel)
        if target is None or not os.path.isfile(target):
            return self.send_json({"error": f"not a file under Customers/: {rel}"}, 400)

        # Walk up to the store's `final/` — the folder holding script.json,
        # wherever PTH.script() currently resolves that to for this store.
        #
        # NEVER stop ON `sandbox/` or `dev/` themselves, only above them.
        # script.json can live INSIDE sandbox/ now (see paths.script()), so
        # while walking up FROM a scene folder the climb passes straight
        # through sandbox/ — and PTH.script(sandbox_dir) would find that
        # very file via its own flat-fallback tier, stopping one level too
        # early and leaving every path below built from the wrong `final`.
        final = os.path.dirname(target)
        for _ in range(4):
            if (os.path.basename(final) not in ("sandbox", "dev")
                    and os.path.isfile(PTH.script(final))):
                break
            final = os.path.dirname(final)
        if not os.path.isfile(PTH.script(final)):
            return self.send_json({"error": f"no script.json above {rel}"}, 400)

        # SANDBOX ONLY. The editor does not read dev/ — see paths.sandbox_only().
        # A scene with no sandbox copy is shown as missing rather than silently
        # resolved from dev, because an edit that appears to work on a file the
        # editor cannot write is worse than an obvious gap.
        items = []
        for n, label in PTH.scenes_from_script(final):
            sb = PTH.sandbox_only(final, n, label)
            seg, av = sb["segment"], sb["avatar"]
            nfr, nex = (frame_count(seg) if seg else (None, False))
            ofr, oex = (frame_count(av) if av else (None, False))
            dur = None
            if seg:
                try:
                    dur = round(float(build_mod.probe(seg, "duration")), 2)
                except (ValueError, RuntimeError):
                    dur = None
            base_slug, base_edited = cache_state(seg)
            over_slug, over_edited = cache_state(av)
            items.append({
                "n": n, "label": label,
                "name": os.path.basename(seg) if seg else "—",
                "dur": dur,
                "path": os.path.relpath(seg, CUSTOMERS_ROOT) if seg else None,
                "overlay": os.path.relpath(av, CUSTOMERS_ROOT) if av else None,
                "src": PTH.source_of(final, seg),
                "overlay_src": PTH.source_of(final, av),
                "missing": seg is None,
                "frames": nfr, "frames_exact": nex,
                "overlay_frames": ofr, "overlay_frames_exact": oex,
                "base_slug": base_slug, "base_edited": base_edited,
                "over_slug": over_slug, "over_edited": over_edited,
                "current": bool(seg) and os.path.abspath(seg) == os.path.abspath(target)})

        # BOOKENDS and anything else living in sandbox that is not a script scene.
        # The opening and closing are not "scenes" — they are not in script.json
        # and never will be — but they ARE a base + overlay pair, so the editor
        # can review them with the same controls. Numbered 00 and 99 so they sit
        # at the ends of the list where they belong.
        known = {it["n"] for it in items}
        sroot = PTH.sandbox_root(final)
        if os.path.isdir(sroot):
            for d in sorted(os.listdir(sroot)):
                m = re.match(r"^(\d+)-(.+)$", d)
                if not m or not os.path.isdir(os.path.join(sroot, d)):
                    continue
                n = int(m.group(1))
                if n in known:
                    continue
                seg = os.path.join(sroot, d, "segment.mp4")
                av = os.path.join(sroot, d, "avatar.webm")
                if not os.path.isfile(seg):
                    continue
                dur = None
                try:
                    dur = round(float(build_mod.probe(seg, "duration")), 2)
                except (ValueError, RuntimeError):
                    pass
                bfr, bex = frame_count(seg)
                afr, aex = (frame_count(av) if os.path.isfile(av) else (None, False))
                base_slug, base_edited = cache_state(seg)
                over_slug, over_edited = cache_state(av) if os.path.isfile(av) else (None, False)
                items.append({
                    "n": n, "label": m.group(2), "name": "segment.mp4", "dur": dur,
                    "frames": bfr, "frames_exact": bex,
                    "overlay_frames": afr, "overlay_frames_exact": aex,
                    "path": os.path.relpath(seg, CUSTOMERS_ROOT),
                    "overlay": os.path.relpath(av, CUSTOMERS_ROOT) if os.path.isfile(av) else None,
                    "src": "sandbox", "overlay_src": "sandbox" if os.path.isfile(av) else None,
                    "missing": False, "extra": True,
                    "base_slug": base_slug, "base_edited": base_edited,
                    "over_slug": over_slug, "over_edited": over_edited,
                    "current": os.path.abspath(seg) == os.path.abspath(target)})
        items.sort(key=lambda it: it["n"])

        v = PTH.versions(final)
        self.send_json({
            "layout": PTH.layout(final),
            "editor_scope": "sandbox",
            "versions": v["segment"],
            "current_version": v["segment"][0] if v["segment"] else None,
            "overlay_version": v["avatar"][0] if v["avatar"] else None,
            "script_version": v["script"][0] if v["script"] else None,
            "by_version": {str(v["segment"][0] if v["segment"] else 0): items},
            "folder": os.path.relpath(final, CUSTOMERS_ROOT)})

    def api_map(self, qs):
        """
        One clip's frame map: for each cache frame, the SOURCE frame it shows.

        The page asks for this before an edit so it can keep a snapshot to undo
        back to. It is not sent with the manifest because most scenes are never
        edited, and a map is one integer per frame -- paid for only when needed.
        """
        outdir = resolve_outdir((qs.get("slug") or [""])[0], (qs.get("which") or [None])[0])
        if outdir is None:
            return self.send_json({"error": "unknown slug"}, 400)
        meta = json.load(open(os.path.join(outdir, "meta.json")))
        self.send_json({"frame_map": build_mod.get_frame_map(meta),
                         "nb_frames": meta["nb_frames"]})

    def api_marks(self, qs):
        outdir = resolve_outdir(qs.get("slug", [""])[0], qs.get("which", [None])[0])
        if outdir is None:
            return self.send_json({"error": "unknown slug"}, 400)
        self.send_json({"marks": load_marks(outdir)})

    def api_mark(self, payload):
        outdir = resolve_outdir(payload.get("slug"), payload.get("which"))
        if outdir is None:
            return self.send_json({"error": "unknown slug"}, 400)
        try:
            frame = int(payload.get("frame"))
        except (TypeError, ValueError):
            return self.send_json({"error": "frame must be an integer"}, 400)
        nb_frames = json.load(open(os.path.join(outdir, "meta.json")))["nb_frames"]
        if not (1 <= frame <= nb_frames):
            return self.send_json({"error": f"frame {frame} is outside 1..{nb_frames}"}, 400)
        marks = set(load_marks(outdir))
        if payload.get("on", True):
            marks.add(frame)
        else:
            marks.discard(frame)
        save_marks(outdir, marks)
        self.send_json({"marks": sorted(marks)})

    def api_clear_marks(self, payload):
        outdir = resolve_outdir(payload.get("slug"), payload.get("which"))
        if outdir is None:
            return self.send_json({"error": "unknown slug"}, 400)
        save_marks(outdir, [])
        self.send_json({"marks": []})

    def api_frames_dup(self, payload):
        """
        Frame Editor, Add: insert `count` copies of the current frame, to its
        `side` ('left' or 'right') — into the PREVIEW CACHE (the extracted
        JPEGs) only. Never touches the source video; /api/cut still reads the
        source by time and does not yet know about frame edits made here.
        """
        outdir = resolve_outdir(payload.get("slug"), payload.get("which"))
        if outdir is None:
            return self.send_json({"error": "unknown slug"}, 400)
        try:
            at, count = int(payload.get("at")), int(payload.get("count"))
        except (TypeError, ValueError):
            return self.send_json({"error": "at and count must be integers"}, 400)
        if count < 1:
            return self.send_json({"error": "count must be at least 1"}, 400)
        side = payload.get("side", "right")
        if side not in ("left", "right"):
            return self.send_json({"error": "side must be 'left' or 'right'"}, 400)
        try:
            if side == "right":
                new_n, new_cur = build_mod.duplicate_frame_right(outdir, at, count)
                # right insert: `at` itself doesn't move, only what's AFTER it does
                marks = [m + count if m > at else m for m in load_marks(outdir)]
            else:
                new_n, new_cur = build_mod.duplicate_frame_left(outdir, at, count)
                # left insert: `at` itself moves too (its content shifts right)
                marks = [m + count if m >= at else m for m in load_marks(outdir)]
        except RuntimeError as e:
            return self.send_json({"error": str(e)}, 400)
        save_marks(outdir, marks)
        self.send_json({"nb_frames": new_n, "current": new_cur, "marks": sorted(marks)})

    def api_frames_del(self, payload):
        """
        Frame Editor, Subtract: delete up to `count` frames immediately to
        the `side` ('left' or 'right') of the current frame — the preview
        cache only, clamped so it can never delete past frame 1 or the last
        frame. Returns the ACTUAL count removed (can be less than asked near
        an edge) and how many marks were dropped because they pointed at
        content that no longer exists.
        """
        outdir = resolve_outdir(payload.get("slug"), payload.get("which"))
        if outdir is None:
            return self.send_json({"error": "unknown slug"}, 400)
        try:
            at, count = int(payload.get("at")), int(payload.get("count"))
        except (TypeError, ValueError):
            return self.send_json({"error": "at and count must be integers"}, 400)
        if count < 1:
            return self.send_json({"error": "count must be at least 1"}, 400)
        side = payload.get("side", "left")
        if side not in ("left", "right"):
            return self.send_json({"error": "side must be 'left' or 'right'"}, 400)
        try:
            if side == "left":
                new_n, new_cur, actual, rng = build_mod.delete_frames_left(outdir, at, count)
            else:
                new_n, new_cur, actual, rng = build_mod.delete_frames_right(outdir, at, count)
        except RuntimeError as e:
            return self.send_json({"error": str(e)}, 400)
        marks, dropped = [], 0
        if rng:
            del_start, del_end = rng
            for m in load_marks(outdir):
                if del_start <= m <= del_end:
                    dropped += 1
                elif m > del_end:
                    marks.append(m - actual)
                else:
                    marks.append(m)
            save_marks(outdir, marks)
        else:
            marks = load_marks(outdir)
        self.send_json({"nb_frames": new_n, "current": new_cur, "actual": actual,
                         "dropped_marks": dropped, "marks": sorted(marks)})

    def api_paste(self, payload):
        """
        Paste a copy of one frame after another, inside the same clip.

        `from` and `at` are both CACHE positions. The copy carries the source
        frame the original showed, so the map stays truthful and a pasted frame
        is the same frame, not a picture of one.
        """
        outdir = resolve_outdir(payload.get("slug"), payload.get("which"))
        if outdir is None:
            return self.send_json({"error": "unknown slug"}, 400)
        try:
            frm, at = int(payload.get("from")), int(payload.get("at"))
        except (TypeError, ValueError):
            return self.send_json({"error": "from and at must be integers"}, 400)
        try:
            n, cur = build_mod.paste_frame(outdir, frm, at)
        except Exception as e:
            return self.send_json({"error": str(e)}, 400)
        # A paste inserts one frame, so a mark AFTER the insert shifts by one.
        marks = [m + 1 if m > at else m for m in load_marks(outdir)]
        save_marks(outdir, marks)
        self.send_json({"nb_frames": n, "current": cur, "marks": marks,
                        "frame_map": build_mod.get_frame_map(build_mod.load_meta(outdir))})

    def api_span(self, payload, mode):
        """
        Repeat or remove a RUN of frames a..b in the preview cache — the marked
        zone the timeline is looping over. The single-frame endpoints act on one
        frame `count` times; this acts on a span once, which is what "loop this
        zone again" and "cut this zone out" actually mean.

        Marks are moved the same way the single-frame delete moves them: a mark
        inside a removed span is dropped, one after it shifts back; on a repeat,
        marks after the span shift forward. A mark that still points at content
        is kept pointing at the same content.
        """
        outdir = resolve_outdir(payload.get("slug"), payload.get("which"))
        if outdir is None:
            return self.send_json({"error": "unknown slug"}, 400)
        try:
            a, b = int(payload.get("a")), int(payload.get("b"))
        except (TypeError, ValueError):
            return self.send_json({"error": "a and b must be integers"}, 400)
        if b < a:
            a, b = b, a
        try:
            if mode == "dup":
                new_n, new_cur = build_mod.duplicate_span(outdir, a, b)
            else:
                new_n, new_cur = build_mod.delete_span(outdir, a, b)
        except RuntimeError as e:
            return self.send_json({"error": str(e)}, 400)

        k = b - a + 1
        marks, dropped = [], 0
        for m in load_marks(outdir):
            if mode == "dup":
                marks.append(m + k if m > b else m)
            else:
                if a <= m <= b:
                    dropped += 1
                elif m > b:
                    marks.append(m - k)
                else:
                    marks.append(m)
        save_marks(outdir, marks)
        self.send_json({"nb_frames": new_n, "current": new_cur, "span": k,
                         "dropped_marks": dropped, "marks": sorted(marks)})

    def api_restore(self, payload):
        """
        Put one clip's cache back to a given frame map — one step of the
        per-scene undo. The map comes from the page, which snapshotted it
        before making the edit being undone.

        Marks are moved with it where they still make sense. A mark points at a
        CACHE position, and undoing changes what sits at each position, so a
        mark past the restored end is dropped rather than left pointing at
        nothing.
        """
        outdir = resolve_outdir(payload.get("slug"), payload.get("which"))
        if outdir is None:
            return self.send_json({"error": "unknown slug"}, 400)
        target = payload.get("frame_map")
        if not isinstance(target, list) or not target:
            return self.send_json({"error": "frame_map must be a non-empty list"}, 400)
        try:
            n = build_mod.restore_map(outdir, target,
                                      log=lambda m: sys.stderr.write(m + "\n"))
        except (RuntimeError, OSError) as e:
            return self.send_json({"error": str(e)}, 400)

        marks = [m for m in load_marks(outdir) if 1 <= m <= n]
        save_marks(outdir, marks)
        # Whether the clip is still edited AFTER the undo. Undoing the last
        # change takes a clip back to the file on disk, and only the server
        # knows it has: the caller cannot tell from the frame count, and a page
        # that assumes "still edited" leaves Save armed with nothing to save.
        meta = json.load(open(os.path.join(outdir, "meta.json")))
        self.send_json({"nb_frames": n, "marks": sorted(marks),
                        "edited": bool(meta.get("edited"))})

    def api_vtt(self, qs):
        """
        The VTT rows for a store — Video Timing Table, not WebVTT subtitles.

        Sends the LINES and the maths behind them; the clip length is left to
        the page, which knows what is actually on the timeline including edits
        that have not been saved yet. vtt.py reads the file on disk instead,
        which is right for a report and wrong for an editor -- there, a gap that
        does not move while you add frames is just a lie with a decimal point.

        `words` comes from vtt.py itself rather than being re-implemented: it
        drops tokens with no letter or digit in them, because a spaced em dash
        is not spoken and counting it added 0.29s to every line that had one.
        """
        root_rel = qs.get("root", [""])[0]
        final = safe_join(root_rel)
        if final is None or not os.path.isdir(final):
            return self.send_json({"error": f"not a folder under Customers/: {root_rel}"}, 400)
        script_p = PTH.script(final)
        if not os.path.isfile(script_p):
            return self.send_json({"error": "this store has no script.json"}, 400)
        doc = json.load(open(script_p))
        rows = []
        for sc in doc.get("scenes", []):
            line = sc.get("line", "") or ""
            rows.append({
                "n": sc["n"], "label": sc.get("label", ""), "line": line,
                "words": vtt_mod.words(line),
                "pause": sum(x.get("seconds", 0) for x in sc.get("pauses", [])),
                "todo": bool(sc.get("_line_todo")),
            })
        self.send_json({"wps": doc.get("words_per_second", 3.44),
                        "store": doc.get("store", ""), "title": doc.get("title", ""),
                        "scenes": rows})

    def api_line(self, payload):
        """
        Rewrite ONE scene's narration line in script.json.

        script.json is the single source of truth for the copy -- vtt.py says so,
        and render_narration reads the same field -- so editing a line here is
        editing what HeyGen will be paid to say. The previous script is copied to
        z_History/line-edits/ first. They are a few kB each and the whole reason
        to edit copy in the player is to try wordings, so the cheap thing to keep
        is the trail of what the wording used to be.

        Writing `_line_todo` away is deliberate: a split leaves that marker on the
        half with no line, and the marker's whole job is done the moment someone
        writes one.
        """
        root_rel = payload.get("root", "")
        final = safe_join(root_rel)
        if final is None or not os.path.isdir(final):
            return self.send_json({"error": f"not a folder under Customers/: {root_rel}"}, 400)
        try:
            n = int(payload.get("n"))
        except (TypeError, ValueError):
            return self.send_json({"error": "n must be an integer"}, 400)
        line = payload.get("line")
        if not isinstance(line, str):
            return self.send_json({"error": "line must be text"}, 400)
        line = " ".join(line.split())
        script_p = PTH.script(final)
        if not os.path.isfile(script_p):
            return self.send_json({"error": "this store has no script.json"}, 400)
        doc = json.load(open(script_p))
        node = next((x for x in doc.get("scenes", []) if x["n"] == n), None)
        if node is None:
            return self.send_json({"error": f"scene {n} is not in the script"}, 400)
        if node.get("line", "") == line:
            return self.send_json({"n": n, "line": line, "words": vtt_mod.words(line),
                                   "unchanged": True})
        hist = os.path.join(final, "z_History", "line-edits")
        os.makedirs(hist, exist_ok=True)
        shutil.copy2(script_p, os.path.join(
            hist, f"script-{time.strftime('%Y%m%d-%H%M%S')}.json"))
        node["line"] = line
        node.pop("_line_todo", None)
        with open(script_p, "w") as fh:
            json.dump(doc, fh, indent=2)
        self.send_json({"n": n, "line": line, "words": vtt_mod.words(line)})

    def api_archive(self, payload):
        """
        Snapshot a video's sandbox into sandbox/z_History/<date>-v_N/.

        A COPY, not a move — which is the one way this differs from the deposit
        into dev. dev is replaced wholesale, so moving is right there. The
        sandbox is edited in place, one scene at a time, and moving it away
        would take the scenes this save is not touching with it.

        Called at a GENERATION boundary — "Save all scenes" — not on every
        single-scene save. The per-scene z_History inside each scene folder
        already answers "what did this clip look like before I saved it", and it
        costs one file; this answers "what did the whole sandbox look like
        before this batch", and ski-demo's sandbox is 80MB. One per batch is a
        record; one per click is a disk full of near-identical copies.

        `dry` asks what WOULD happen, so the editor's confirmation can name the
        destination before the user agrees to it rather than after.

        `naming` picks the folder name — the default `<date>-v_N`, or `"add-v"`
        for `26-8-27_v1`. Both live in the same z_History and the sequence is
        read from both, so they cannot hand out the same number on one day.
        """
        # Two ways in, one rule. The editor knows the video folder and passes
        # `root`; the splitter knows only the clip it opened, so it passes
        # `slug` and the video folder is derived exactly as the handoff derives
        # it. Deriving it a second time in the page would be a second rule to
        # keep in step, which is how the folders drifted apart before.
        if payload.get("slug"):
            outdir = resolve_outdir(payload.get("slug"), payload.get("which"))
            if outdir is None:
                return self.send_json({"error": "unknown slug"}, 400)
            try:
                meta = json.load(open(os.path.join(outdir, "meta.json")))
            except OSError:
                return self.send_json({"error": "this clip has no extraction"}, 400)
            cuts = derive_segments_dir(meta.get("source") or "")
            final = os.path.dirname(os.path.dirname(cuts))
        else:
            root_rel = payload.get("root", "")
            final = safe_join(root_rel)
        if final is None or not os.path.isdir(final):
            return self.send_json({"error": f"not a folder under Customers/: {payload.get('root', payload.get('slug'))}"}, 400)
        which = payload.get("folder", "sandbox")
        roots = {"sandbox": PTH.sandbox_root(final), "dev": PTH.dev_root(final)}
        if which not in roots:
            return self.send_json({"error": "folder must be 'sandbox' or 'dev'"}, 400)
        folder = roots[which]
        keep = ("_cuts",)
        if not os.path.isdir(folder):
            return self.send_json({"error": f"this video has no {which}/ folder"}, 400)
        skip = set(keep) | {PTH.ARCHIVE_DIR}
        holds = [x for x in sorted(os.listdir(folder))
                 if x not in skip and not x.startswith(".")]
        naming = payload.get("naming")
        would = os.path.join(folder, PTH.ARCHIVE_DIR,
                             PTH.archive_name_v(folder) if naming == "add-v"
                             else PTH.archive_name(folder))
        if payload.get("dry"):
            return self.send_json({"folder": folder, "would_archive": holds,
                                   "into": would, "empty": not holds})
        if not holds:
            return self.send_json({"folder": folder, "archived_to": None,
                                   "archived": [], "empty": True})
        dest = PTH.archive_contents(folder, keep=keep, move=(which == "dev"),
                                    naming=payload.get("naming"))
        self.send_json({"folder": folder, "archived_to": dest,
                        "archived": holds, "empty": False,
                        "moved": which == "dev"})

    def api_save_archive(self, payload):
        """
        Save All / Backup Scenes' own pre-step, added 2026-08-29: before the
        editor's current state lands, snapshot the GENERATION about to be
        overwritten into sandbox/1000_archive/<Add-V name>/ (26-8-29_v1,
        26-8-29_v2, ... one sequence per day, same convention as api_archive's
        "add-v" naming, just kept in a folder of its own) — every scene
        folder in sandbox/, PLUS the narrative script.

        The script used to be a special case here: Carson asked for "the
        current scenes and the narration script" archived together, but
        script.json lived at video/script.json — a SIBLING of sandbox/, not
        inside it — so sweeping sandbox/'s own contents alone left it out,
        and this endpoint copied it in as an extra step. As of the
        2026-08-29 move (see paths.script()) script.json normally lives
        INSIDE sandbox/ now, so the ordinary sweep already carries it —
        this only still copies it separately for a store that has not been
        migrated yet (PTH.script() falls back to video/ or the bare flat
        location for those, and archive_contents() only ever reaches
        inside `folder`, i.e. sandbox/ itself). Its own per-edit history
        stays exactly where it already was, at z_History/line-edits/ under
        the video folder root — this is an additional whole-generation
        copy, not a replacement for that.

        A COPY, not a literal move. Carson asked for the old generation moved
        out before the new one lands, but api_save's own rebuild reads each
        scene's video straight off its sandbox path (meta.json's "source" —
        see build_frames()) and refuses to run if that file is gone
        (`source no longer exists`). Moving it away first would make every
        save in the batch fail. Copying first gets the same end state Carson
        asked for — 1000_archive holds exactly the old generation, sandbox
        ends up holding exactly the new one — without breaking the save that
        has to read the old file to build the new one.
        """
        root_rel = payload.get("root", "")
        final = safe_join(root_rel)
        if final is None or not os.path.isdir(final):
            return self.send_json({"error": f"not a folder under Customers/: {root_rel}"}, 400)
        folder = PTH.sandbox_root(final)
        if not os.path.isdir(folder):
            return self.send_json({"error": "this video has no sandbox/ folder"}, 400)
        script_p = PTH.script(final)
        # Only a special case for a store PTH.script() had to fall back for —
        # once script.json lives in sandbox/, the ordinary sweep below already
        # carries it, and copying it a second time here would just duplicate it.
        needs_extra_copy = (os.path.isfile(script_p)
                            and os.path.dirname(os.path.abspath(script_p))
                                != os.path.abspath(folder))
        if payload.get("dry"):
            skip = {PTH.ARCHIVE_DIR, "1000_archive"}
            holds = [x for x in sorted(os.listdir(folder))
                     if x not in skip and not x.startswith(".")]
            if needs_extra_copy:
                holds.append(f"script.json ({os.path.relpath(os.path.dirname(script_p), final)}/)")
            would = os.path.join(folder, "1000_archive", PTH.archive_name_v(folder, archive_dir="1000_archive"))
            return self.send_json({"folder": folder, "would_archive": holds,
                                   "into": would, "empty": not holds})
        dest = PTH.archive_contents(folder, move=False, naming="add-v",
                                    archive_dir="1000_archive")
        if dest is None and not needs_extra_copy:
            return self.send_json({"folder": folder, "archived_to": None, "empty": True})
        if dest is None:
            # Sandbox had nothing, but the script still needs somewhere to
            # go — this endpoint's own promise is "scenes AND script", not
            # "script only when scenes also moved".
            dest = os.path.join(folder, "1000_archive",
                                PTH.archive_name_v(folder, archive_dir="1000_archive"))
            os.makedirs(dest, exist_ok=True)
        if needs_extra_copy:
            shutil.copy2(script_p, os.path.join(dest, "script.json"))
        self.send_json({"folder": folder, "archived_to": dest, "empty": False})

    def api_handoff(self, payload):
        """
        Hand a cut's segments over to the sandbox, named.

        The MP4 Splitter writes dev/_cuts/Num_3-v1-segment.mp4; naming it here
        makes it dev/03-catalogue-search/segment-v1.mp4 — a scene, and the
        starting point of a video.

        dev holds ONE generation. Depositing archives the one before it to
        dev/z_History/<date>-v_N/ and starts the numbering again at 1, so what
        is in dev is always exactly the cut you last made, not a pile of them.

        This is that step: name each cut, and it lands where the editor looks,
        with a scene row in script.json to match. That row is what makes it a
        scene rather than a loose file: paths.sandbox_dir() finds a folder by
        its NN- prefix, and the VTT and every scene list read the script.

        COPIES out of _cuts, never moves. _cuts is the versioned record of what
        the splitter produced, and a second attempt at naming has to stay
        possible.
        """
        outdir = resolve_outdir(payload.get("slug"), payload.get("which"))
        if outdir is None:
            return self.send_json({"error": "unknown slug"}, 400)
        try:
            meta = json.load(open(os.path.join(outdir, "meta.json")))
        except OSError:
            return self.send_json({"error": "this clip has no extraction to hand off"}, 400)
        src = meta.get("source")
        if not src or not os.path.isfile(src):
            return self.send_json({"error": f"source no longer exists: {src}"}, 400)

        cuts_dir = derive_segments_dir(src)
        if not os.path.isdir(cuts_dir):
            return self.send_json({"error": "nothing has been cut yet"}, 400)
        # The video folder is the one holding sandbox/ — two up from _cuts.
        final = os.path.dirname(os.path.dirname(cuts_dir))

        # derive_segments_dir() falls back to "a sandbox beside the source" for
        # a clip that is not inside a store's videos/<name>/ tree. That is fine
        # for CUTTING -- the pieces land next to what they came from -- but a
        # handoff there writes a whole parallel mini-store: measured once as
        # sandbox/01-alpha-scene/sandbox/01-login-screen/ plus its own
        # script.json, reported as a success, with nothing where the editor
        # looks. A scene only means something inside a video folder, so this
        # says no rather than building a store nobody asked for.
        parent = os.path.basename(os.path.dirname(final))
        if parent != "videos" and os.path.basename(final) != "final":
            return self.send_json(
                {"error": "this clip is not inside a store's videos/<name>/ folder, "
                          "so there is no video for these scenes to belong to. "
                          f"Cutting still works; the pieces are in {cuts_dir}."}, 400)

        try:
            version = int(payload.get("version"))
        except (TypeError, ValueError):
            return self.send_json({"error": "version must be an integer"}, 400)
        found = []
        for f in sorted(os.listdir(cuts_dir)):
            m = SEGMENT_NAME_RE.match(f)
            if m and int(m.group(2)) == version:
                found.append((int(m.group(1)), f))
        found.sort()
        if not found:
            return self.send_json({"error": f"no cut segments at version {version}"}, 400)

        names = payload.get("names") or []
        if len(names) != len(found):
            return self.send_json(
                {"error": f"{len(found)} segments but {len(names)} name(s)"}, 400)
        for nm in names:
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,48}", nm or ""):
                return self.send_json(
                    {"error": f"bad name: {nm!r} — lower-case letters, digits and hyphens"}, 400)
        if len(set(names)) != len(names):
            return self.send_json({"error": "two segments cannot share a name"}, 400)

        script_p = PTH.script(final)
        doc = json.load(open(script_p)) if os.path.isfile(script_p) else {}

        # A fresh cut REPLACES dev, it does not append to it. dev holds one
        # generation of segments — the starting point of one video — and the
        # generation it replaces goes to dev/z_History/<date>-v_N/ first, with
        # the script that described it, because a scene list and the folders it
        # names are only meaningful together.
        droot = PTH.dev_root(final)
        os.makedirs(droot, exist_ok=True)
        archived = PTH.archive_contents(droot, keep=("_cuts",))
        if archived and os.path.isfile(script_p):
            shutil.move(script_p, os.path.join(archived, "script.json"))
            doc.pop("scenes", None)
        scenes = doc.setdefault("scenes", [])
        start = 1

        sroot = droot
        planned = []
        for k, (num, fname) in enumerate(found):
            n = start + k
            d = os.path.join(sroot, f"{n:02d}-{names[k]}")
            # Checking the exact folder name is not enough. paths.sandbox_dir()
            # finds a scene by its NN- PREFIX, so any folder already using that
            # number wins the lookup and the new scene is invisible while a
            # different one answers to its number. Measured: handing off beside
            # an orphaned 02-bravo-scene made scene 2 resolve to bravo, not to
            # the segment just handed over.
            clash = [x for x in (os.listdir(sroot) if os.path.isdir(sroot) else [])
                     if re.match(rf"^{n:02d}(-|$)", x)
                     and os.path.isdir(os.path.join(sroot, x))]
            if clash:
                return self.send_json(
                    {"error": f"sandbox already has {clash[0]}, so scene {n} is taken. "
                              f"The script and the folders disagree — fix that before "
                              f"handing off, or these scenes cannot be found."}, 400)
            planned.append((n, names[k], d, os.path.join(cuts_dir, fname)))

        if scenes and os.path.isfile(script_p):
            hist = os.path.join(final, "z_History", "handoff")
            os.makedirs(hist, exist_ok=True)
            shutil.copy2(script_p, os.path.join(
                hist, f"script-{time.strftime('%Y%m%d-%H%M%S')}.json"))

        made = []
        for n, name, d, srcf in planned:
            os.makedirs(d, exist_ok=True)
            # dev's own convention: versioned filenames, which paths.py's
            # DEV_SEG_RE/DEV_AV_RE look for. A fresh deposit starts at v1 —
            # the generations above it live in z_History, not in the filename.
            dst = os.path.join(d, "avatar-v1.webm" if is_alpha(srcf) else "segment-v1.mp4")
            shutil.copy2(srcf, dst)
            scenes.append({"n": n, "label": name, "line": "",
                           "_line_todo": "written by the splitter's handoff; the line is still to write"})
            made.append({"n": n, "label": name,
                         "folder": os.path.basename(d),
                         "frames": build_mod.decoded_frames(dst, dec_for(dst))})

        os.makedirs(os.path.dirname(script_p), exist_ok=True)
        with open(script_p, "w") as fh:
            json.dump(doc, fh, indent=2)

        self.send_json({"handed_off": made, "first_n": start,
                        "scenes": len(scenes), "script": script_p,
                        "into": droot,
                        "archived_to": archived})

    def api_join(self, payload):
        """
        Join several scenes into one, in the store's sandbox.

        WHAT THIS TOUCHES, because it is more than media. A scene is a folder of
        clips AND an entry in script.json carrying its narration line, and
        script.json is read by nine tools in this pipeline including the one
        that spends money on renders. Joining therefore:

          * concatenates the segments, and the avatars, in scene order
          * joins the narration lines with a space, in the same order
          * writes ONE new sandbox folder for the result
          * renumbers EVERY scene in the script sequentially, because a join
            leaves a hole and downstream tools index by `n`
          * archives the whole previous state first

        Everything replaced goes to z_History/<stamp>/ before anything is
        written, script.json included. A join is not reversible from the editor,
        so it has to be reversible from disk.

        Concatenation is done on the FILES, by stream copy where the encodes
        already match, so joining does not add a generation of re-encoding to
        footage that has already been through one.
        """
        root_rel = payload.get("root", "")
        ns = payload.get("ns") or []
        label = (payload.get("label") or "").strip()
        tracks = payload.get("tracks") or ["segment", "avatar"]
        final = safe_join(root_rel)
        if final is None or not os.path.isdir(final):
            return self.send_json({"error": f"not a folder under Customers/: {root_rel}"}, 400)
        if len(ns) < 2:
            return self.send_json({"error": "a join needs at least two scenes"}, 400)
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,48}", label or ""):
            return self.send_json({"error": "name must be lower-case letters, digits and hyphens"}, 400)

        script_p = PTH.script(final)
        if not os.path.isfile(script_p):
            return self.send_json({"error": "this store has no script.json"}, 400)
        doc = json.load(open(script_p))
        scenes = doc.get("scenes", [])
        by_n = {s["n"]: s for s in scenes}
        ns = [int(x) for x in ns]
        missing = [n for n in ns if n not in by_n]
        if missing:
            return self.send_json({"error": f"not scenes in the script: {missing}"}, 400)

        # In SCRIPT order, not the order they were clicked: the join is a splice
        # of the video's own sequence, and any other order would silently
        # reorder the narration.
        order = [s["n"] for s in scenes if s["n"] in set(ns)]
        parts = []
        for n in order:
            sb = PTH.sandbox_only(final, n, by_n[n].get("label"))
            if not sb["segment"]:
                return self.send_json({"error": f"scene {n} has no segment in sandbox"}, 400)
            parts.append((n, sb["segment"], sb["avatar"], sb["narration"]))
        # A track some scenes have and others do not. Two ways this can go, and
        # the difference is the whole point: dropping it SILENTLY moves every
        # later clip forward — the opening has no narration, so scene 2's would
        # start at frame 1 and Sarah would say the login line over the intro.
        # Filling the gap holds that time open instead.
        fill = bool(payload.get("fill_gaps"))
        gaps = {}
        for idx, what in ((2, "avatar"), (3, "narration")):
            if "avatar" not in tracks:
                continue
            missing = [p for p in parts if p[idx] is None]
            present = [p for p in parts if p[idx]]
            if not (missing and present):
                continue
            if not fill:
                names = ", ".join(str(p[0]) for p in missing)
                return self.send_json(
                    {"error": f"scene(s) {names} have no {what} and the others do. "
                              f"Joining as-is would move every later {what} forward. "
                              f"Send fill_gaps to hold that time open with a "
                              f"transparent silent clip instead.",
                     "gap": what,
                     "scenes_missing": [p[0] for p in missing]}, 400)
            gaps[what] = (idx, [p[0] for p in missing], present[0][idx])

        stamp = time.strftime("%Y%m%d-%H%M%S")
        hist = os.path.join(final, "z_History", f"join-{stamp}")
        os.makedirs(hist, exist_ok=True)
        shutil.copy2(script_p, os.path.join(hist, "script.json"))

        first = order[0]
        new_dir = os.path.join(PTH.sandbox_root(final), f"{first:02d}-{label}")
        tmp_dir = tempfile.mkdtemp(prefix="video_players_join_")
        filled = []
        try:
            # Each gap gets a filler as long as that SCENE is — measured on its
            # segment, which is the scene's true duration. Built before the
            # concat so the parts list is complete when it runs.
            for what, (idx, missing_ns, like) in gaps.items():
                for k, prt in enumerate(parts):
                    if prt[0] not in missing_ns:
                        continue
                    n_frames = build_mod.decoded_frames(prt[1], dec_for(prt[1]))
                    dst = os.path.join(tmp_dir, f"fill_{what}_{prt[0]}.webm")
                    make_gap_filler(like, n_frames, dst)
                    row = list(prt)
                    row[idx] = dst
                    parts[k] = tuple(row)
                    filled.append({"scene": prt[0], "track": what, "frames": n_frames})
            # narration.webm rides with the AVATAR, and is not separately
            # choosable, because it is what the avatar was rendered from --
            # assemble_video composites the narration, not the avatar. Left
            # behind, the joined scene had no narration of its own and
            # paths.narration() fell back to dev/, quietly handing the build the
            # PRE-JOIN narration of the first half only. No error, just a
            # different video from the one the folder names imply.
            for kind, idx, needs in (("segment.mp4", 1, "segment"),
                                     ("avatar.webm", 2, "avatar"),
                                     ("narration.webm", 3, "avatar")):
                if needs not in tracks:
                    continue          # a track not chosen is not carried over
                srcs = [p[idx] for p in parts if p[idx]]
                if not srcs:
                    continue
                lst = os.path.join(tmp_dir, kind + ".txt")
                open(lst, "w").write("".join(f"file '{os.path.abspath(x)}'\n" for x in srcs))
                out = os.path.join(tmp_dir, kind)
                r = subprocess.run(
                    ["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
                     "-c", "copy", "-y", out], capture_output=True, text=True)
                if r.returncode != 0:
                    return self.send_json({"error": f"joining {kind}: {r.stderr[-400:]}"}, 500)

            # Archive every folder being consumed, then put the new one in place.
            for n, seg, *_ in parts:
                d = os.path.dirname(seg)
                shutil.copytree(d, os.path.join(hist, os.path.basename(d)), dirs_exist_ok=True)
            for n, seg, *_ in parts:
                shutil.rmtree(os.path.dirname(seg), ignore_errors=True)
            os.makedirs(new_dir, exist_ok=True)
            for kind in ("segment.mp4", "avatar.webm", "narration.webm"):
                built = os.path.join(tmp_dir, kind)
                if os.path.isfile(built):
                    shutil.copy2(built, os.path.join(new_dir, kind))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        joined = {
            "n": first, "label": label,
            "line": " ".join((by_n[n].get("line") or "").strip() for n in order).strip(),
            "_joined_from": [{"n": n, "label": by_n[n].get("label", "")} for n in order],
            "_joined_on": stamp,
        }
        kept = [s for s in scenes if s["n"] not in set(order)]
        kept.append(joined)
        kept.sort(key=lambda s: s["n"])
        # RENUMBER every scene. A join leaves a hole, and `n` is what the rest of
        # the pipeline indexes by, so the numbers have to stay 1..N with no gaps.
        renum = []
        for i, sc in enumerate(kept, 1):
            if sc["n"] != i:
                sc["_was_n"] = sc["n"]
                renum.append({"from": sc["n"], "to": i})
            sc["n"] = i
        doc["scenes"] = kept
        renamed = renumber_sandbox_folders(final, kept)
        doc["_join_note"] = (f"{stamp}: joined scenes {order} into '{label}'. "
                             f"Every scene renumbered sequentially. "
                             f"Previous state in z_History/join-{stamp}/.")
        with open(script_p, "w") as fh:
            json.dump(doc, fh, indent=2)

        self.send_json({"joined": order, "label": label, "new_n": joined["n"],
                         "renamed": renamed, "filled": filled,
                         "renumbered": renum, "scenes": len(kept),
                         "archived_to": os.path.relpath(hist, CUSTOMERS_ROOT)})

    def api_split(self, payload):
        """
        Split one scene in two at a frame, in the store's sandbox.

        The counterpart to /api/join and it costs the same: two new folders,
        script.json rewritten, every scene renumbered, and the previous state
        archived to z_History/split-<stamp>/ before anything is written.

        The cut is FRAME-ACCURATE. `-frames:v` for the head and `-ss` on the
        frame boundary for the tail, never a duration cutoff -- the same rule
        build_segment had to learn, for the same reason: a duration drops the
        frame that ends on the boundary, and here that frame would simply
        vanish from the video rather than being in one half or the other.

        THE NARRATION CANNOT BE SPLIT AUTOMATICALLY. A line belongs to a whole
        thought, not to a frame count, so the whole line stays with the FIRST
        half and the second is left empty for a human to write. The response
        says so; the page warns before the split.
        """
        root_rel = payload.get("root", "")
        final = safe_join(root_rel)
        if final is None or not os.path.isdir(final):
            return self.send_json({"error": f"not a folder under Customers/: {root_rel}"}, 400)
        try:
            n, at = int(payload.get("n")), int(payload.get("at"))
        except (TypeError, ValueError):
            return self.send_json({"error": "n and at must be integers"}, 400)
        names = payload.get("labels") or []
        tracks = payload.get("tracks") or ["segment", "avatar"]
        if len(names) != 2:
            return self.send_json({"error": "two names are needed, one per half"}, 400)
        for nm in names:
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,48}", nm or ""):
                return self.send_json({"error": f"bad name: {nm!r}"}, 400)
        if names[0] == names[1]:
            return self.send_json({"error": "the two halves need different names"}, 400)

        script_p = PTH.script(final)
        if not os.path.isfile(script_p):
            return self.send_json({"error": "this store has no script.json"}, 400)
        doc = json.load(open(script_p))
        scenes = doc.get("scenes", [])
        node = next((x for x in scenes if x["n"] == n), None)
        if node is None:
            return self.send_json({"error": f"scene {n} is not in the script"}, 400)

        sb = PTH.sandbox_only(final, n, node.get("label"))
        srcs = {"segment": sb["segment"], "avatar": sb["avatar"],
                "narration": sb["narration"]}
        # narration.webm is cut wherever the avatar is, for the same reason the
        # join carries it: it is the render the avatar came from and what
        # assemble_video actually composites. It is not separately choosable.
        needs = {"segment": "segment", "avatar": "avatar", "narration": "avatar"}
        chosen = [t for t in ("segment", "avatar", "narration")
                  if needs[t] in tracks and srcs[t]]
        if not chosen:
            return self.send_json({"error": "none of the chosen tracks exist on that scene"}, 400)

        # Every chosen track is measured and the cut point checked BEFORE a single
        # byte is written. The two tracks are routinely different lengths -- a
        # 190-frame segment under a 152-frame avatar is normal -- so a frame that
        # is fine for one can be off the end of the other. Checked late, the
        # refusal still left a z_History/split-<stamp>/ archive behind for a split
        # that never happened, which reads afterwards as if it had.
        plan = {}
        for t in chosen:
            src = srcs[t]
            num, _, den = build_mod.probe(src, "r_frame_rate", stream=True).partition("/")
            total = build_mod.decoded_frames(src, dec_for(src))
            if total is None or not (1 < at <= total):
                return self.send_json(
                    {"error": f"frame {at} is not inside {t} (1..{total})"}, 400)
            plan[t] = (float(num) / float(den or 1), total)

        stamp = time.strftime("%Y%m%d-%H%M%S")
        hist = os.path.join(final, "z_History", f"split-{stamp}")
        os.makedirs(hist, exist_ok=True)
        shutil.copy2(script_p, os.path.join(hist, "script.json"))
        old_dir = os.path.dirname(srcs[chosen[0]])
        shutil.copytree(old_dir, os.path.join(hist, os.path.basename(old_dir)), dirs_exist_ok=True)

        tmp_dir = tempfile.mkdtemp(prefix="video_players_split_")
        made = {0: {}, 1: {}}
        try:
            for t in chosen:
                src = srcs[t]
                fps, total = plan[t]
                dec, enc = dec_for(src), (ENCODE_ALPHA if is_alpha(src) else ENCODE)
                ext = ".webm" if is_alpha(src) else ".mp4"
                head = os.path.join(tmp_dir, f"{t}_a{ext}")
                tail = os.path.join(tmp_dir, f"{t}_b{ext}")
                r = subprocess.run(["ffmpeg", "-v", "error"] + dec + ["-i", src,
                                    "-frames:v", str(at - 1)] + enc + ["-y", head],
                                   capture_output=True, text=True)
                if r.returncode != 0:
                    return self.send_json({"error": f"splitting {t} head: {r.stderr[-300:]}"}, 500)
                r = subprocess.run(["ffmpeg", "-v", "error"] + dec +
                                   ["-ss", f"{(at - 1) / fps:.6f}", "-i", src,
                                    "-frames:v", str(total - at + 1)] + enc + ["-y", tail],
                                   capture_output=True, text=True)
                if r.returncode != 0:
                    return self.send_json({"error": f"splitting {t} tail: {r.stderr[-300:]}"}, 500)
                made[0][t] = head
                made[1][t] = tail

            shutil.rmtree(old_dir, ignore_errors=True)
            for half in (0, 1):
                d = os.path.join(PTH.sandbox_root(final), f"{n:02d}-{names[half]}")
                os.makedirs(d, exist_ok=True)
                for t, built in made[half].items():
                    shutil.copy2(built, os.path.join(d, TRACK_FILE[t]))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        head_node = dict(node, label=names[0], line=node.get("line", ""),
                          _split_on=stamp, _split_at=at)
        tail_node = {"n": node["n"], "label": names[1], "line": "",
                      "_split_on": stamp, "_split_from": node.get("label", ""),
                      "_line_todo": "the narration stayed with the first half; write this one"}
        out = []
        for sc in scenes:
            if sc["n"] == n:
                out.append(head_node); out.append(tail_node)
            else:
                out.append(sc)
        renum = []
        for i, sc in enumerate(out, 1):
            if sc["n"] != i:
                sc["_was_n"] = sc["n"]; renum.append({"from": sc["n"], "to": i})
            sc["n"] = i
        doc["scenes"] = out
        renamed = renumber_sandbox_folders(final, out)
        doc["_split_note"] = (f"{stamp}: split scene {n} at frame {at} into "
                              f"'{names[0]}' and '{names[1]}'. Tracks: {', '.join(chosen)}. "
                              f"Every scene renumbered. Previous state in "
                              f"z_History/split-{stamp}/.")
        with open(script_p, "w") as fh:
            json.dump(doc, fh, indent=2)

        self.send_json({"split": n, "at": at, "labels": names, "tracks": chosen,
                         "renamed": renamed,
                         "renumbered": renum, "scenes": len(out),
                         "line_stayed_with": names[0],
                         "archived_to": os.path.relpath(hist, CUSTOMERS_ROOT)})

    def api_renumber_state(self, qs):
        """
        Has this store been renumbered since it was last saved as a set?

        Read from script.json rather than remembered in the page. A join or a
        split RELOADS the timeline, so a flag held in JavaScript dies at exactly
        the moment it starts mattering -- the rule it enforces would be gone one
        navigation after the renumber that caused it.

        `_was_n` is written on every scene whose number moved and removed when
        the set is saved, so the file itself carries the answer.
        """
        final = safe_join((qs.get("root") or [""])[0])
        if final is None or not os.path.isdir(final):
            return self.send_json({"error": "not a folder under Customers/"}, 400)
        p = PTH.script(final)
        if not os.path.isfile(p):
            return self.send_json({"renumbered": False, "moved": []})
        scenes = json.load(open(p)).get("scenes", [])
        moved = [{"from": s["_was_n"], "to": s["n"]} for s in scenes if "_was_n" in s]
        self.send_json({"renumbered": bool(moved), "moved": moved})

    def api_renumber_clear(self, payload):
        """
        Drop the `_was_n` markers — the set has been written, so the numbers on
        disk and the numbers in the script agree again.
        """
        final = safe_join(payload.get("root", ""))
        if final is None or not os.path.isdir(final):
            return self.send_json({"error": "not a folder under Customers/"}, 400)
        p = PTH.script(final)
        if not os.path.isfile(p):
            return self.send_json({"error": "no script.json"}, 400)
        doc = json.load(open(p))
        cleared = 0
        for sc in doc.get("scenes", []):
            if sc.pop("_was_n", None) is not None:
                cleared += 1
        if cleared:
            with open(p, "w") as fh:
                json.dump(doc, fh, indent=2)
        self.send_json({"cleared": cleared})

    def api_cut(self, payload):
        """
        Cut the ORIGINAL source video at every marked frame — read straight
        from meta.json's `source` path with ffmpeg, FRAME-EDITOR-AWARE: each
        segment is built from `frame_map`, so a duplicate becomes a real held
        frame in the output and a deletion is really absent, not just hidden
        in the preview. The browser's CSS mark overlay is still never
        referenced anywhere in this path — there is no code here that could
        read it even if it wanted to.
        """
        outdir = resolve_outdir(payload.get("slug"), payload.get("which"))
        if outdir is None:
            return self.send_json({"error": "unknown slug"}, 400)
        meta = json.load(open(os.path.join(outdir, "meta.json")))
        marks = load_marks(outdir)
        if not marks:
            return self.send_json({"error": "no break points marked yet"}, 400)

        src, fps, nb_frames = meta["source"], meta["fps"], meta["nb_frames"]
        if not os.path.isfile(src):
            return self.send_json({"error": f"source no longer exists: {src}"}, 500)
        frame_map = build_mod.get_frame_map(meta)

        dest_dir = derive_segments_dir(src)
        os.makedirs(dest_dir, exist_ok=True)
        version = next_version(dest_dir)
        # An avatar cut stays a WebM. Writing Sarah's pieces as .mp4 would name
        # them correctly and strip the transparency they exist for.
        seg_ext = ".webm" if is_alpha(src) else ".mp4"

        tmp_dir = tempfile.mkdtemp(prefix="video_players_cut_")
        try:
            boundaries = [1] + marks + [nb_frames + 1]
            segments = []
            for i in range(len(boundaries) - 1):
                start_f, end_f = boundaries[i], boundaries[i + 1] - 1
                if end_f < start_f:
                    continue
                dur_s = (end_f - start_f + 1) / fps
                name = f"Num_{len(segments) + 1}-v{version}-segment{seg_ext}"
                dst = os.path.join(dest_dir, name)
                runs = build_mod.group_frame_runs(frame_map[start_f - 1:end_f])
                edited = len(runs) > 1
                r = build_segment(src, fps, runs, dst, tmp_dir)
                if r.returncode != 0:
                    segments.append({"name": name, "error": r.stderr[-500:]})
                    continue
                got = float(build_mod.probe(dst, "duration"))
                warning = None if abs(got - dur_s) < 0.15 else \
                    f"wanted {dur_s:.2f}s, got {got:.2f}s"
                segments.append({"name": name, "start_frame": start_f, "end_frame": end_f,
                                  "duration_s": round(got, 3), "edited": edited,
                                  "warning": warning})
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        self.send_json({"outdir": dest_dir, "version": version, "count": len(segments), "segments": segments})

    def api_save(self, payload):
        """
        Rebuild the WHOLE current edited frame sequence (1..N, via
        frame_map — the same runs/build_segment machinery /api/cut uses,
        just with no mark boundaries) and OVERWRITE the file this viewer
        opened. The confirmation with the destination path happens in the
        browser before this is ever called; this endpoint does not ask
        again — by the time it's hit, the user has already agreed.

        Archives the current source to z_History/ first, same convention
        every other tool in this project already follows before an
        overwrite — so a bad save is one file move away from undone, even
        though this endpoint itself does not offer to undo it.
        """
        outdir = resolve_outdir(payload.get("slug"), payload.get("which"))
        if outdir is None:
            return self.send_json({"error": "unknown slug"}, 400)
        meta = json.load(open(os.path.join(outdir, "meta.json")))
        src, fps, nb_frames = meta["source"], meta["fps"], meta["nb_frames"]
        if not os.path.isfile(src):
            return self.send_json({"error": f"source no longer exists: {src}"}, 500)

        # STALENESS CHECK. meta.json already stamps the source's size+mtime
        # from the moment this cache was built — that stamp normally only
        # changes when THIS save writes it. If it differs now, something
        # else (another tab, another tool, Frame Blender) already overwrote
        # this file since this editor session loaded it, and this save is
        # about to clobber that work with a cache that never saw it. Refused
        # unless the caller explicitly says `force` — set only after the
        # browser has shown the user this exact situation and they chose to
        # overwrite anyway.
        st = os.stat(src)
        stale = (st.st_size != meta.get("size") or st.st_mtime != meta.get("mtime"))
        if stale and not payload.get("force"):
            return self.send_json({
                "error": "stale",
                "message": f"{os.path.basename(src)} changed on disk since this was "
                           f"loaded here — probably saved from another tab or tool. "
                           f"Reload it to see the new version, or save again with "
                           f"force to overwrite it anyway.",
            }, 409)

        frame_map = build_mod.get_frame_map(meta)
        want_frames = len(frame_map)

        tmp_dir = tempfile.mkdtemp(prefix="video_players_save_")
        try:
            runs = build_mod.group_frame_runs(frame_map)
            built = os.path.join(tmp_dir, "built.webm" if is_alpha(src) else "built.mp4")
            r = build_segment(src, fps, runs, built, tmp_dir)
            if r.returncode != 0:
                return self.send_json({"error": r.stderr[-500:]}, 500)
            got = float(build_mod.probe(built, "duration"))

            hist_dir = os.path.join(os.path.dirname(src), "z_History", time.strftime("%Y%m%d-%H%M%S"))
            os.makedirs(hist_dir, exist_ok=True)
            archived = os.path.join(hist_dir, os.path.basename(src))
            shutil.copy2(src, archived)

            shutil.copy2(built, src)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        # The source on disk is now the edited clip, so every edit this cache
        # is still holding has ALREADY been applied. Re-extract from what was
        # just written, and drop the marks with it.
        #
        # Without this the cache keeps describing the PRE-save file: `edited`
        # stays true (so Save re-arms and the page still reads as unsaved —
        # which is exactly how a landed save gets reported as "it didn't
        # save"), and `frame_map` keeps pointing at source frame numbers that
        # the shortened file no longer has. build_segment() seeks by frame
        # number, so a SECOND save would rebuild against the wrong frames and
        # silently write a wrong, shorter clip.
        # alpha_png from the meta being replaced — SAME trap as clear-edits. An
        # overlay re-extracted without it comes back as flat JPEG: no alpha, and
        # named .jpg while the page asks for .png, so every overlay frame 404s
        # and Sarah simply is not there. This one fires after every SAVE of an
        # overlay, which is worse.
        #
        # This step can fail on its own — ffmpeg has thrown on a source with a
        # single bad-pts frame (non-monotonic dts) mid-extraction — and the FILE
        # is already saved by this point (src was overwritten above). Before
        # this was caught, that raised straight out of the handler: no response
        # ever went back, and the browser's fetch() reported it as a network
        # failure ("TypeError: Failed to fetch") on a scene that had, in fact,
        # already landed — which read as the save itself failing and left that
        # scene's edited-flag stuck on, re-arming a save that had nothing left
        # to do. Caught here, it is reported as what it is: saved, cache stale.
        nb_frames = wrote = None
        warning = None
        try:
            build_mod.build_frames(src, out=outdir, box=meta.get("box", 750),
                                    force=True,
                                    alpha_png=(meta.get("ext") == ".png"),
                                    log=lambda m: sys.stderr.write(m + "\n"))
            save_marks(outdir, [])
            new_meta = json.load(open(os.path.join(outdir, "meta.json")))
            nb_frames = new_meta["nb_frames"]

            # VERIFY WHAT WAS WRITTEN, in FRAMES. build_segment rebuilds a clip by
            # TIME (-ss/-t per piece) and each piece rounds on its own, so an edited
            # clip comes back short of the length that was on screen: measured, a
            # 89-frame preview wrote 87, one frame lost per cut. That is exactly the
            # class of fault this whole tool exists to catch, so a save says so
            # instead of letting it pass.
            wrote = build_mod.decoded_frames(src, dec_for(src))
            if wrote is not None and wrote != want_frames:
                warning = (f"wrote {wrote} frames, expected {want_frames} — the rebuild "
                           f"is time-based and loses a frame per cut")
        except RuntimeError as e:
            warning = (f"saved, but the live preview cache could not be refreshed "
                       f"({e}). Reload this scene to see the new frames.")
        self.send_json({"path": src, "archived_to": archived, "duration_s": round(got, 3),
                        "nb_frames": nb_frames,
                        "frames_written": wrote, "frames_expected": want_frames,
                        "warning": warning})

    def api_clear_edits(self, payload):
        """
        Reset this cache to exactly the state a first-ever `Open` produces —
        discards every Frame Editor edit and every break point, but the video
        stays loaded. Re-extracts straight from meta.json's `source`, which
        build_frames() never writes to; only the cache (frames/, meta.json,
        breakpoints.json) changes. Confirmation happens in the browser before
        this is ever called.
        """
        outdir = resolve_outdir(payload.get("slug"), payload.get("which"))
        if outdir is None:
            return self.send_json({"error": "unknown slug"}, 400)
        meta = json.load(open(os.path.join(outdir, "meta.json")))
        src, box = meta["source"], meta.get("box", 750)
        if not os.path.isfile(src):
            return self.send_json({"error": f"source no longer exists: {src}"}, 500)
        try:
            # alpha_png carried over from the meta being replaced. Without it an
            # OVERLAY came back as flat JPEG — no alpha, and named .jpg while the
            # page asks for .png. Every overlay frame then 404s, so the avatar
            # vanishes and only the background shows through. Silent: the clip is
            # still there, still the right length, just not transparent and not
            # where the page looks. restore_map already did this; this did not.
            build_mod.build_frames(src, out=outdir, box=box, force=True,
                                    alpha_png=(meta.get("ext") == ".png"),
                                    log=lambda m: sys.stderr.write(m + "\n"))
        except RuntimeError as e:
            return self.send_json({"error": str(e)}, 500)
        save_marks(outdir, [])
        new_meta = json.load(open(os.path.join(outdir, "meta.json")))
        self.send_json({"nb_frames": new_meta["nb_frames"]})

    def api_reset_editor(self, payload):
        """
        Unload this video from the tool entirely: delete its whole cache
        directory — every extracted frame, meta.json, breakpoints.json, and
        this very viewer.html. The SOURCE FILE named inside meta.json is
        never touched or even opened here; only the regenerable cache goes.
        There is no page left to reload afterward, so the browser navigates
        back to Browse once this succeeds.
        """
        outdir = resolve_outdir(payload.get("slug"), payload.get("which"))
        if outdir is None:
            return self.send_json({"error": "unknown slug"}, 400)
        shutil.rmtree(outdir, ignore_errors=True)
        self.send_json({"ok": True})

    def log_message(self, fmt, *args):
        sys.stderr.write("  " + (fmt % args) + "\n")


BROWSE_HTML = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Browse Customers — video editor</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin:0; background:#1a1a1a; color:#eee; font-family:-apple-system,sans-serif;
         display:flex; flex-direction:column; align-items:center; padding:16px 0; }}
  #panel {{ width:750px; }}
  h1 {{ font-size:15px; font-weight:600; margin:0 0 10px; color:#ccc; }}
  #crumb {{ font-size:12px; color:#888; margin-bottom:10px; word-break:break-all; }}
  #status {{ font-size:13px; color:#e0c060; min-height:18px; margin-bottom:8px; }}
  #list {{ border:1px solid #333; border-radius:8px; overflow:hidden; }}
  .row {{ padding:9px 14px; cursor:pointer; border-bottom:1px solid #2a2a2a;
         display:flex; justify-content:space-between; font-size:13px; }}
  .row:last-child {{ border-bottom:none; }}
  .row:hover {{ background:#2a2a2a; }}
  .row.file {{ color:#9fd0ff; }}
  .row .size {{ color:#777; font-variant-numeric:tabular-nums; }}
  .badges {{ display:flex; gap:8px; }}
  .chip {{ color:#9aa; padding:2px 8px; border:1px solid #444; border-radius:10px;
          font-size:11px; white-space:nowrap; }}
  .chip:hover {{ color:#fff; border-color:#6a6; background:#1f3320; }}
  .empty {{ padding:14px; color:#666; font-size:13px; }}
  .slotbtn {{ margin-left:8px; background:#2c3236; color:#eee; border:1px solid #4a5259;
              border-radius:5px; padding:2px 8px; font-size:13px; cursor:pointer; }}
  .slotbtn.base:hover {{ border-color:#2ecc40; color:#2ecc40; }}
  .slotbtn.overlay:hover {{ border-color:#a56cff; color:#a56cff; }}
</style></head>
<body>
  <div id="panel">
    <h1>Browse Customers/ for a raw recording</h1>
    <div id="crumb">Customers/</div>
    <div id="pairbar" style="display:none;gap:10px;align-items:center;flex-wrap:wrap;
       margin:8px 0;padding:8px 10px;border:1px solid #3a4248;border-radius:8px;background:#1b1f22">
    <span style="color:#2ecc40;font-weight:600">▩ background</span>
    <span id="pbBase" style="color:#ccc">—</span>
    <span style="color:#a56cff;font-weight:600">◈ overlay</span>
    <span id="pbOver" style="color:#ccc">—</span>
    <button id="pbGo" onclick="openPair()" disabled
      style="background:#2c3236;color:#eee;border:1px solid #4a5259;border-radius:6px;
             padding:6px 12px;cursor:pointer">Layer these ▶</button>
    <button onclick="PAIR.base=PAIR.overlay=null;paintPair()"
      style="background:none;color:#889;border:0;cursor:pointer">clear</button>
  </div>
  <div id="status"></div>
    <div id="list"></div>
  </div>
<script>
  function fmtSize(b) {{
    if (b > 1e6) return (b / 1e6).toFixed(1) + ' MB';
    if (b > 1e3) return (b / 1e3).toFixed(0) + ' KB';
    return b + ' B';
  }}
  function row(icon, label, sizeText, onclick, isFile) {{
    const d = document.createElement('div');
    d.className = 'row' + (isFile ? ' file' : '');
    const l = document.createElement('span'); l.textContent = `${{icon}}  ${{label}}`;
    d.appendChild(l);
    if (sizeText) {{ const s = document.createElement('span'); s.className = 'size'; s.textContent = sizeText; d.appendChild(s); }}
    d.onclick = onclick;
    return d;
  }}
  // A store row: clicking the name still jumps to raw_mp4 (unchanged default),
  // and a "segments" chip sits right beside it when that folder exists too —
  // added so the cut segments this tool itself produces are as reachable as
  // the raw recording they came from, not three folders deeper.
  function storeRow(d) {{
    const div = document.createElement('div');
    div.className = 'row';
    const label = document.createElement('span');
    label.textContent = `🎬  ${{d.name}}`;
    div.appendChild(label);
    const badges = document.createElement('span');
    badges.className = 'badges';
    const chip = (text, target) => {{
      const c = document.createElement('span');
      c.className = 'chip';
      c.textContent = text;
      c.onclick = (e) => {{ e.stopPropagation(); list(target); }};
      return c;
    }};
    badges.appendChild(chip('raw_mp4 →', d.jump));
    if (d.segments_jump) badges.appendChild(chip('segments →', d.segments_jump));
    div.appendChild(badges);
    div.onclick = () => list(d.jump);
    return div;
  }}
  async function list(path) {{
    setStatus('');
    const r = await fetch(`/api/list?path=${{encodeURIComponent(path)}}`);
    const data = await r.json();
    if (data.error) {{ setStatus('Error: ' + data.error); return; }}
    document.getElementById('crumb').textContent = 'Customers/' + data.path;
    const el = document.getElementById('list');
    el.innerHTML = '';
    if (data.parent !== null) el.appendChild(row('⬆️', '.. (up)', '', () => list(data.parent)));
    for (const d of data.dirs) {{
      el.appendChild(d.jump ? storeRow(d) : row('📁', d.name, '', () => list(d.path)));
    }}
    for (const f of data.files) {{
      const r = row('🎬', f.name, fmtSize(f.size), () => openFile(f.path), true);
      // Layering needs two files, usually from different folders, so the picks
      // have to survive navigating away — hence slots rather than a selection.
      for (const [slot, glyph, tip] of [['base','▩','use as BACKGROUND (mp4)'],
                                        ['overlay','◈','use as OVERLAY (webm)']]) {{
        const b = document.createElement('button');
        b.className = 'slotbtn ' + slot;
        b.textContent = glyph; b.title = tip;
        b.onclick = ev => {{ ev.stopPropagation(); PAIR[slot] = f.path; paintPair(); }};
        r.appendChild(b);
      }}
      el.appendChild(r);
    }}
    if (data.parent === null && data.dirs.length === 0 && data.files.length === 0)
      el.appendChild(Object.assign(document.createElement('div'), {{ className: 'empty', textContent: 'Customers/ is empty.' }}));
  }}
  const PAIR = {{ base: null, overlay: null }};
  function paintPair() {{
    const bar = document.getElementById('pairbar');
    const nm = p => p ? p.split('/').pop() : '—';
    document.getElementById('pbBase').textContent = nm(PAIR.base);
    document.getElementById('pbOver').textContent = nm(PAIR.overlay);
    document.getElementById('pbGo').disabled = !(PAIR.base && PAIR.overlay);
    bar.style.display = (PAIR.base || PAIR.overlay) ? 'flex' : 'none';
  }}
  async function openPair() {{
    setStatus('Extracting BOTH clips — the overlay keeps its alpha, so this takes a moment…');
    try {{
      const r = await fetch(`/api/open-pair?base=${{encodeURIComponent(PAIR.base)}}`
                            + `&overlay=${{encodeURIComponent(PAIR.overlay)}}`);
      const d = await r.json();
      if (d.error) {{ setStatus('Error: ' + d.error); return; }}
      location.href = d.url;
    }} catch (e) {{ setStatus('Error: ' + e); }}
  }}
  function setStatus(msg) {{ document.getElementById('status').textContent = msg; }}
  async function openFile(path) {{
    setStatus(`Extracting frames from ${{path}} — this can take a moment for a long recording…`);
    try {{
      const r = await fetch(`/api/open?path=${{encodeURIComponent(path)}}`);
      const data = await r.json();
      if (data.error) {{ setStatus('Error: ' + data.error); return; }}
      location.href = data.url;
    }} catch (e) {{ setStatus('Error: ' + e); }}
  }}
  paintPair();
  list('');
</script>
</body></html>
"""


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8842)
    # The test drives hundreds of calls and writes its own log. Without this it
    # would bury a day of real editing in its own fixture traffic.
    ap.add_argument("--no-session-log", action="store_true")
    a = ap.parse_args()
    global SESSION_OFF
    SESSION_OFF = a.no_session_log
    os.makedirs(CACHE, exist_ok=True)
    handler = functools.partial(Handler, directory=CACHE)
    httpd = ThreadingHTTPServer(("127.0.0.1", a.port), handler)
    if not SESSION_OFF:
        session_start(a.port)
    print(f"  video players serving on http://localhost:{a.port}")
    print(f"  browse root: {CUSTOMERS_ROOT}")
    print(f"  session log: {'off' if SESSION_OFF else SESSION_LOG}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
