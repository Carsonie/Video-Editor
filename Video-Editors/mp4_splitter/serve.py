#!/usr/bin/env python3
"""
MP4 Splitter's own standalone server — split off shared/serve.py whole on
2026-09-02, at Carson's own request: the Segment and Avatar Editor used to
share this one process/port with it, and he asked for the two tools to be
genuinely independent, no shared code, each on its own port. This file
started as a literal copy of shared/serve.py and was trimmed down to just
what MP4 Splitter's own page (this package's player.py) actually calls —
SAE-only routes (Join, Split, Stores, Siblings, VTT, Edit line, layered/
timeline opening, ...) are gone ENTIRELY.

    Careful: for a year they were only HALF gone. The 2026-09-02 split
    removed them from the dispatch tables below but left their handler
    bodies in place — 15 unreachable methods, 930 lines, 36% of this
    file, plus 5 module-level helpers only they used. Every test passed
    the whole time, because a route with no dispatch entry 404s exactly
    like a route whose handler was deleted. Removed 2026-09-03. What
    stops it recurring is fixture.dead_handlers(), which walks out from
    do_GET/do_POST and fails the suite on anything it cannot reach.

It also gets its OWN extracted-frame cache (cache/mp4-splitter/, not the shared
cache/) and its own frames.py/paths.py — duplicated, not imported, same
reason. See segment_avatar_editor/serve.py for that tool's own copy of
this same split.

Serves the extracted-frame cache (same as
`python3 -m http.server --directory cache/mp4-splitter`) and adds a
folder-tree browser rooted at Customers/, so a raw recording can be found
and opened without already knowing its path.

    python3 mp4_splitter/serve.py [--port 8845]

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

# This tool's own process, own port, own cache — genuinely standalone since
# 2026-09-02.
#
# frames.py and paths.py used to sit right beside this file as private copies:
# 776 + 465 lines, duplicated three times over, differing by two lines of real
# code. On 2026-09-03 they became editor_base/ — the one package every editor
# may import from. Standalone still holds where it matters: own process, own
# port, own cache, own routes, own pages.
HERE = os.path.dirname(os.path.abspath(__file__))          # <repo>/mp4_splitter
ROOT = os.path.dirname(HERE)                                # <repo>
CACHE = os.path.join(ROOT, "cache", "mp4-splitter")         # this tool's OWN cache
sys.path.insert(0, ROOT)                                    # for the mp4_splitter package itself
from editor_base import frames as build_mod                 # noqa: E402
# No segment_avatar_editor import, no vtt.py — this tool never renders a
# layered/timeline/VTT page, so it has no use for either.
from editor_base import paths as PTH                        # noqa: E402
from mp4_splitter import player                             # noqa: E402  its name for the page footer

# editor_base's two per-editor knobs, set here at import time and not in
# main(): the test imports this module without ever calling main(), and an
# unset cache would extract frames into another tool's folder.
build_mod.use_cache(CACHE)

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
    sys.exit("could not find a Customers/ folder above this file — this repo's video "
             "data is gitignored and there is no script that fetches it; see "
             "ToDo.md P3.5")


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
SESSION_LOG = os.path.join(SESSION_DIR, f"mp4_splitter_{time.strftime('%Y%m%d')}.log")

# endpoint -> (what to call it, which payload keys are worth showing).
# Trimmed to just this tool's own routes (2026-09-02, alongside giving it
# its own dedicated log file) — the full multi-tool table this was copied
# from (shared/serve.py's ACTIONS) carried entries for routes this process
# never serves (Join, Split, Frame Blender's Build/Save MP4, ...); every
# entry left below is provably reachable — see this file's own do_POST/
# do_GET dispatch for the exact route list.
ACTIONS = {
    "/api/frames/dup":      ("+ Frame",      ("at", "count", "side")),
    "/api/frames/del":      ("- Frame",      ("at", "count", "side")),
    "/api/frames/restore":  ("Undo",         ()),
    "/api/mark":            ("Mark",         ("frame", "on")),
    "/api/clear-marks":     ("Unmark all",   ()),
    "/api/save":            ("Save scene",   ()),
    "/api/cut":             ("Cut scene",    ()),
    "/api/clear-edits":     ("Discard edits", ()),
    "/api/reset-editor":    ("Reset editor", ()),
    "/api/handoff":         ("Hand off",     ("version", "names")),
    "/api/archive":         ("Archive",      ("folder",)),
    "/api/open":            ("Open clip",    ("path",)),
}
# result keys worth showing, in the order they read best
RESULT_KEYS = ("nb_frames", "count", "version", "duration_s", "joined", "split",
               "label", "labels", "line", "renamed", "url", "slug")


def session_start(port):
    os.makedirs(SESSION_DIR, exist_ok=True)
    ver_p = os.path.join(HERE, "VERSION")
    ver = open(ver_p).read().strip() if os.path.isfile(ver_p) else "?"
    with open(SESSION_LOG, "a") as fh:
        fh.write(f"\nEditor Session:  {time.strftime('%Y-%m-%dT%H:%M:%S')}\n"
                 f"Player:          MP4 Splitter v{ver}\n"
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
        # Only the way IN is logged, and only it needs to be: a line saying
        # what you opened is what makes the edits under it readable. Every
        # other GET is a frame image or a poll, and logging those would bury
        # the record in its own noise.
        if parsed.path == "/api/open":
            qs = urllib.parse.parse_qs(parsed.query)
            flat = {k: v[0] for k, v in qs.items() if v}
            self._last_json, self._last_status = None, 200
            self.route_get(parsed)
            return session_log(parsed.path, flat, self._last_json, self._last_status)
        return self.route_get(parsed)

    def route_get(self, parsed):
        # This tool's own routes only. The SAE-only ones (Stores, layered/
        # timeline opening, Siblings, VTT, ...) were dropped here on
        # 2026-09-02 when the two tools split apart, and their handler
        # methods — 15 of them, plus 5 helpers only they called — were
        # deleted on 2026-09-03. tests/fixture.py's dead_handlers() walks
        # the dispatcher transitively and fails the suite if an unreachable
        # handler reappears.
        if parsed.path == "/api/list":
            return self.api_list(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/open":
            return self.api_open(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/frames/map":
            return self.api_map(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/marks":
            return self.api_marks(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/clip":
            return self.api_clip(urllib.parse.parse_qs(parsed.query))
        if parsed.path.startswith("/web/"):
            return self.send_web(parsed.path[len("/web/"):])
        if parsed.path in ("/", "/browse.html"):
            return self.send_html(BROWSE_HTML)
        # A clip's own page. Answered from web/index.html and NOT from the
        # file of the same name sitting in the clip's cache folder.
        #
        # THIS IS DELIBERATE, and it is what makes the 2026-09-04 migration
        # safe. player.write() used to render a complete page into
        # <cache>/<slug>/viewer.html, so every clip ever opened still has a
        # fully-rendered copy of the OLD page on disk. Serving the static
        # page here makes all of them correct at once — no re-extraction, no
        # migration pass, and no fresh-fixture blind spot where the suite
        # passes while months-old caches keep serving the old page.
        if parsed.path.endswith("/viewer.html"):
            return self.send_web("index.html", "text/html; charset=utf-8")
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
        # Same trim as route_get above — this tool's own routes only.
        if parsed.path == "/api/mark":
            return self.api_mark(payload)
        if parsed.path == "/api/clear-marks":
            return self.api_clear_marks(payload)
        if parsed.path == "/api/frames/dup":
            return self.api_frames_dup(payload)
        if parsed.path == "/api/frames/del":
            return self.api_frames_del(payload)
        if parsed.path == "/api/handoff":
            return self.api_handoff(payload)
        if parsed.path == "/api/archive":
            return self.api_archive(payload)
        if parsed.path == "/api/frames/restore":
            return self.api_restore(payload)
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

    def api_clip(self, qs):
        """
        Everything the clip page needs to draw itself — the 14 values that
        used to be baked into the HTML by player.py's str.format().

        This endpoint IS the contract between serve.py and web/app.js. Add a
        field here and read it there; there is no third place to keep in
        step any more, which was the whole point of making the page static.
        """
        outdir = resolve_outdir((qs.get("slug") or [""])[0], (qs.get("which") or [None])[0])
        if outdir is None:
            return self.send_json({"error": "unknown slug"}, 400)
        meta = json.load(open(os.path.join(outdir, "meta.json")))
        name = meta.get("source_name", os.path.basename(meta["source"]))
        self.send_json({
            "title": name,
            "source": name,
            "source_path": meta["source"],
            "slug": os.path.basename(outdir.rstrip(os.sep)),
            "nb_frames": meta["nb_frames"],
            "fps": meta["fps"],
            "disp_w": meta["disp_w"],
            "disp_h": meta["disp_h"],
            # Toolbelt puts a fixed-width drawer beside the stage: 264 + the
            # 14px grid gap. stack_w is the width below which that no longer
            # fits and the drawer drops under the video instead.
            "app_w": meta["disp_w"] + 278,
            "stack_w": meta["disp_w"] + 292,
            "has_audio": bool(meta.get("has_audio")),
            # `edited` means frames were added or removed, so the extracted
            # audio — which is the ORIGINAL — no longer lines up. The page
            # says so rather than letting a false sync be believed.
            "edited_flag": bool(meta.get("edited")),
            "edited": bool(meta.get("edited", False)),
            "player_label": player.label(),
        })

    def send_web(self, name, ctype=None):
        """
        One of this tool's own static files out of mp4_splitter/web/.

        Served from here rather than by pointing the handler's `directory` at
        web/, because that root is already the frame CACHE — the frames are
        the bulk of what this server hands out. `name` is resolved and then
        checked to still be inside web/, so a `..` cannot walk out.
        """
        root = os.path.join(HERE, "web")
        path = os.path.realpath(os.path.join(root, name))
        if not path.startswith(os.path.realpath(root) + os.sep) or not os.path.isfile(path):
            return self.send_json({"error": f"no such file: {name}"}, 404)
        if ctype is None:
            ctype = {".js": "application/javascript", ".css": "text/css",
                     ".html": "text/html; charset=utf-8"}.get(
                os.path.splitext(path)[1], "application/octet-stream")
        body = open(path, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # This page is edited while it is open. A cached copy of app.js is a
        # fix that silently did not apply.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

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


BROWSE_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>MP4 Splitter</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; background:#1a1a1a; color:#eee; font-family:-apple-system,sans-serif;
         display:flex; flex-direction:column; align-items:center; padding:16px 0; }
  #panel { width:750px; }
  h1 { font-size:15px; font-weight:600; margin:0 0 10px; color:#ccc; }
  #crumb { font-size:12px; color:#888; margin-bottom:10px; word-break:break-all; }
  #status { font-size:13px; color:#e0c060; min-height:18px; margin-bottom:8px; }
  #list { border:1px solid #333; border-radius:8px; overflow:hidden; }
  .row { padding:9px 14px; cursor:pointer; border-bottom:1px solid #2a2a2a;
         display:flex; justify-content:space-between; font-size:13px; }
  .row:last-child { border-bottom:none; }
  .row:hover { background:#2a2a2a; }
  .row.file { color:#9fd0ff; }
  .row .size { color:#777; font-variant-numeric:tabular-nums; }
  .badges { display:flex; gap:8px; }
  .chip { color:#9aa; padding:2px 8px; border:1px solid #444; border-radius:10px;
          font-size:11px; white-space:nowrap; }
  .chip:hover { color:#fff; border-color:#6a6; background:#1f3320; }
  .empty { padding:14px; color:#666; font-size:13px; }
</style></head>
<body>
  <div id="panel">
    <h1>Browse Customers/ for a raw recording</h1>
    <div id="crumb">Customers/</div>
    <div id="status"></div>
    <div id="list"></div>
  </div>
<script>
  function fmtSize(b) {
    if (b > 1e6) return (b / 1e6).toFixed(1) + ' MB';
    if (b > 1e3) return (b / 1e3).toFixed(0) + ' KB';
    return b + ' B';
  }
  function row(icon, label, sizeText, onclick, isFile) {
    const d = document.createElement('div');
    d.className = 'row' + (isFile ? ' file' : '');
    const l = document.createElement('span'); l.textContent = `${icon}  ${label}`;
    d.appendChild(l);
    if (sizeText) { const s = document.createElement('span'); s.className = 'size'; s.textContent = sizeText; d.appendChild(s); }
    d.onclick = onclick;
    return d;
  }
  // A store row: clicking the name still jumps to raw_mp4 (unchanged default),
  // and a "segments" chip sits right beside it when that folder exists too —
  // added so the cut segments this tool itself produces are as reachable as
  // the raw recording they came from, not three folders deeper.
  function storeRow(d) {
    const div = document.createElement('div');
    div.className = 'row';
    const label = document.createElement('span');
    label.textContent = `🎬  ${d.name}`;
    div.appendChild(label);
    const badges = document.createElement('span');
    badges.className = 'badges';
    const chip = (text, target) => {
      const c = document.createElement('span');
      c.className = 'chip';
      c.textContent = text;
      c.onclick = (e) => { e.stopPropagation(); list(target); };
      return c;
    };
    badges.appendChild(chip('raw_mp4 →', d.jump));
    if (d.segments_jump) badges.appendChild(chip('segments →', d.segments_jump));
    div.appendChild(badges);
    div.onclick = () => list(d.jump);
    return div;
  }
  async function list(path) {
    setStatus('');
    const r = await fetch(`/api/list?path=${encodeURIComponent(path)}`);
    const data = await r.json();
    if (data.error) { setStatus('Error: ' + data.error); return; }
    document.getElementById('crumb').textContent = 'Customers/' + data.path;
    const el = document.getElementById('list');
    el.innerHTML = '';
    if (data.parent !== null) el.appendChild(row('⬆️', '.. (up)', '', () => list(data.parent)));
    for (const d of data.dirs) {
      el.appendChild(d.jump ? storeRow(d) : row('📁', d.name, '', () => list(d.path)));
    }
    for (const f of data.files) {
      el.appendChild(row('🎬', f.name, fmtSize(f.size), () => openFile(f.path), true));
    }
    if (data.parent === null && data.dirs.length === 0 && data.files.length === 0)
      el.appendChild(Object.assign(document.createElement('div'), { className: 'empty', textContent: 'Customers/ is empty.' }));
  }
  function setStatus(msg) { document.getElementById('status').textContent = msg; }
  async function openFile(path) {
    setStatus(`Extracting frames from ${path} — this can take a moment for a long recording…`);
    try {
      const r = await fetch(`/api/open?path=${encodeURIComponent(path)}`);
      const data = await r.json();
      if (data.error) { setStatus('Error: ' + data.error); return; }
      location.href = data.url;
    } catch (e) { setStatus('Error: ' + e); }
  }
  list('');
</script>
</body></html>
"""


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8845)
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
    print(f"  mp4 splitter serving on http://localhost:{a.port}")
    print(f"  browse root: {CUSTOMERS_ROOT}")
    print(f"  session log: {'off' if SESSION_OFF else SESSION_LOG}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
