#!/usr/bin/env python3
"""
Build the frame-by-frame video editor for ANY recording — a raw_mp4 capture, a cut
segment, a narration clip, anything ffprobe can read.

    python3 build.py <video.mp4> [--out DIR] [--box 750] [--force]

Extracts every frame as a JPEG once, then writes a self-contained HTML page
next to them: a slider that jumps to any frame instantly, ◀/▶ buttons and the
left/right arrow keys that step exactly one frame, and a frame/timecode
readout. Every position shown is a REAL decoded frame, not a player's seek —
this project has already hit more than one bug (the stray "R", frame 0 vs
frame 1) caused by trusting a video element's or ffmpeg's `-ss` seek instead of
extracting the actual frame and looking at it. This tool exists so "look at
frame N" never depends on a seek mode again.

Caching: keyed on the resolved source path. A rebuild is skipped if a prior
extraction exists and the source's size + mtime haven't changed — pass
--force to redo it anyway (e.g. after re-encoding the source).

The real work lives in build_frames() so serve.py (the "Browse…" button's
folder-tree server) can call it directly on whatever file gets clicked,
without shelling out to this file as a subprocess.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading

# The cache is SHARED by every player: one extraction of a clip serves the
# splitter, the layered editor and the timeline alike. It therefore lives at
# video_players/cache, one level above this package, not inside it.
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# THE ONE LINE THAT MADE THREE COPIES OF THIS FILE.
#
# Until 2026-09-03 this module existed three times over — shared/frames.py,
# mp4_splitter/frames.py, segment_avatar_editor/frames.py — 776 lines each,
# and the ONLY difference between them in real code was this constant:
#
#     shared/                 cache
#     mp4_splitter/           cache_mp4_splitter
#     segment_avatar_editor/  cache_segment_avatar_editor
#
# One line of configuration, paid for with two full duplicate files. So it
# is configuration now, and there is one file.
#
# This is process-level config, set once at startup, NOT request state —
# and it is safe for exactly one reason: every editor is its own OS
# process. That is the whole point of the 2026-09-02 split. If two editors
# are ever put in one process they will fight over this value, and that
# would be a real bug. See editor_base/__init__.py.
CACHE = os.path.join(ROOT, "cache")


def use_cache(path):
    """
    Point this process's extraction cache somewhere else. Call once, at
    startup, before anything extracts — every editor does it in main().

    Takes an absolute path so the caller owns the decision; this module
    does not guess a folder name from a tool's name.
    """
    global CACHE
    CACHE = path
    return CACHE

# ── one worker at a time, per cache folder ──────────────────────────────────
# The server is threaded, so two clicks a second apart run at once. Nothing
# stopped two of them re-extracting into the SAME frames/ directory, and they
# stomped on each other: six Undo clicks in six seconds left a 440-frame clip
# with a 204-frame cache, by way of 216 and 381, and one "[Errno 66] Directory
# not empty" as two swaps collided.
#
# Keyed on the folder, so edits to different clips still run in parallel —
# which is the whole reason the server is threaded.
_DIR_LOCKS = {}
_LOCKS_GUARD = threading.Lock()


def dir_lock(outdir):
    key = os.path.abspath(outdir)
    with _LOCKS_GUARD:
        lock = _DIR_LOCKS.get(key)
        if lock is None:
            lock = _DIR_LOCKS[key] = threading.Lock()
    return lock


def probe(path, entry, stream=False, dec=None):
    """`dec` is the decoder to force — ["-c:v","libvpx-vp9"] for an alpha WebM,
    which must be given BEFORE the input or the alpha is dropped."""
    cmd = ["ffprobe", "-v", "error"] + (["-select_streams", "v"] if stream else []) + \
          (dec or []) + \
          ["-show_entries", ("stream=" if stream else "format=") + entry, "-of", "csv=p=0", path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {path}:\n{r.stderr}")
    return r.stdout.strip()


def decoded_frames(path, dec=None):
    """
    How many frames this file really decodes. Slower than reading the header —
    it decodes the whole stream — so it is only used where the header cannot be
    trusted or where the output has to be capped to it exactly.
    """
    cmd = ["ffprobe", "-v", "error"] + list(dec or []) + [
        "-select_streams", "v", "-count_frames",
        "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = r.stdout.strip()
    return int(out) if out.isdigit() else None


def slug_for(path):
    """
    A slug becomes a URL PATH SEGMENT (`<slug>/viewer.html`), so it must be
    made of characters that survive there unescaped. `#` is not one of them —
    it is the URL fragment delimiter, so a source name like `#1-v2-segment.mp4`
    (this tool's own cut-segment naming) produced a slug starting with `#`,
    and `location.href = "#slug/viewer.html"` was read as an in-page anchor
    jump on the CURRENT page rather than a navigation. Nothing errored; the
    page just silently stayed put. Fixed by keeping only [A-Za-z0-9._-] from
    the basename and dropping everything else, rather than special-casing `#`
    — any other URL-meaningful character (`?`, `%`, `&`, ...) would have hit
    the same failure mode.
    """
    abspath = os.path.abspath(path)
    h = hashlib.sha1(abspath.encode()).hexdigest()[:8]
    base = os.path.splitext(os.path.basename(path))[0]
    safe = re.sub(r"[^A-Za-z0-9._-]", "", base) or "video"
    return f"{safe}_{h}"


def extract_audio(src, outdir, log=print):
    """
    Pull `src`'s audio to outdir/audio.m4a. True if the clip ends up with sound.

    Re-encoded to AAC in m4a rather than copied: sources here are Opus-in-WebM
    and AAC-in-mp4, and only one of those plays everywhere. A viewer that works
    for the mp4 and is silent for the WebM is worse than no audio at all,
    because the silence looks like the clip.

    Split out of build_frames so the CACHE-REUSE path can call it too. It only
    ran on a fresh extraction, so a clip whose frames were extracted before this
    existed stayed silent for good — reopening reused the cache and never looked
    for the audio. Measured on a raw ski-demo recording: frames from 2026-08-22,
    no audio.m4a, a perfectly good AAC track in the source, and no way to get it
    short of re-extracting 3325 frames. The audio itself takes half a second.
    """
    audio_path = os.path.join(outdir, "audio.m4a")
    has_audio = bool(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
         "stream=codec_type", "-of", "csv=p=0", src],
        capture_output=True, text=True).stdout.strip())
    if has_audio:
        ar = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-vn",
                             "-c:a", "aac", "-b:a", "128k", "-y", audio_path],
                            capture_output=True, text=True)
        if ar.returncode != 0:
            has_audio = False
            log(f"  ⚠ audio extraction failed, continuing silent: {ar.stderr[-200:]}")
    if not has_audio and os.path.exists(audio_path):
        os.remove(audio_path)
    return has_audio


def build_frames(video, out=None, box=750, force=False, log=print, alpha_png=False):
    """
    Extract every frame of `video` and write its viewer.html. Returns the
    outdir. Callable from the CLI (main(), below) or from serve.py's browse
    endpoint — raises RuntimeError on any failure rather than exiting the
    process, since a server calls this from a request-handling thread and
    needs to turn a failure into a JSON error response, not a dead thread.
    """
    src = os.path.abspath(video)
    if not os.path.exists(src):
        raise RuntimeError(f"no such file: {src}")

    outdir = out or os.path.join(CACHE, slug_for(src))
    frames_dir = os.path.join(outdir, "frames")
    meta_path = os.path.join(outdir, "meta.json")

    st = os.stat(src)
    sig = {"source": src, "size": st.st_size, "mtime": st.st_mtime, "box": box,
           "alpha_png": bool(alpha_png)}

    cached = os.path.exists(meta_path) and os.path.isdir(frames_dir)
    if cached and not force:
        prior = json.load(open(meta_path))
        if all(prior.get(k) == sig[k] for k in sig):
            # Same reasoning as the viewer rewrite below: a cache built before
            # audio was extracted should not have to be thrown away to gain it.
            # Half a second, against re-extracting every frame.
            if prior.get("has_audio") and not os.path.isfile(
                    os.path.join(outdir, "audio.m4a")):
                log("  cached extraction has no audio — pulling just the audio")
                prior["has_audio"] = extract_audio(src, outdir, log=log)
                json.dump(prior, open(meta_path, "w"))
            elif "has_audio" not in prior:
                # Older caches predate the flag entirely, so ask the source.
                got = extract_audio(src, outdir, log=log)
                if got:
                    log("  cached extraction had no audio — recovered it")
                prior["has_audio"] = got
                json.dump(prior, open(meta_path, "w"))
            # Frames are cached, but always rewrite viewer.html against the
            # CURRENT template — otherwise a template fix never reaches an old
            # cache without a wasteful full re-extraction.
            write_viewer(outdir, prior)
            log(f"  using cached extraction: {outdir}")
            log(f"  ({prior['nb_frames']} frames, {prior['fps']:g}fps) — open video_players/cache/{os.path.basename(outdir)}/viewer.html")
            log(f"  --force to re-extract")
            return outdir
        log("  source changed since last extraction — re-extracting")

    os.makedirs(frames_dir, exist_ok=True)
    for f in os.listdir(frames_dir):
        os.remove(os.path.join(frames_dir, f))

    # An alpha WebM MUST be decoded with `-c:v libvpx-vp9` given BEFORE `-i`.
    # Without it ffmpeg picks a decoder that silently drops the alpha channel and
    # still reports yuva420p, so the failure is invisible until a composite comes
    # out with a black box where the transparency was.
    alpha = src.lower().endswith(".webm")
    dec = ["-c:v", "libvpx-vp9"] if alpha else []

    num, den = probe(src, "r_frame_rate", stream=True, dec=dec).split("/")
    fps = float(num) / float(den)
    width = int(probe(src, "width", stream=True, dec=dec))
    height = int(probe(src, "height", stream=True, dec=dec))
    duration = float(probe(src, "duration", dec=dec))

    log(f"  source: {width}x{height} @ {fps:g}fps, {duration:.2f}s")
    log(f"  extracting frames into {frames_dir} ...")

    # JPEG cannot carry alpha, and a transparent frame written straight to JPEG
    # comes out BLACK — which for an avatar clip means a black rectangle with a
    # person somewhere in it, unreviewable. Composite onto the same flat grey the
    # finished video uses, so what the viewer shows is roughly what will ship.
    # `alpha_png` keeps the REAL alpha, as PNG, for layering one clip over
    # another in the browser. Otherwise alpha is flattened onto the same grey the
    # finished video uses, because JPEG cannot carry it and a transparent frame
    # written to JPEG comes out black.
    ext = ".png" if alpha_png else ".jpg"
    vf = f"scale={box}:{box}:force_original_aspect_ratio=decrease"
    if alpha and not alpha_png:
        vf = (f"color=c=0x232323:s={width}x{height}[bg];[bg][0:v]overlay=0:0:shortest=1,"
              + vf)
        cmd = ["ffmpeg", "-v", "error"] + dec + ["-i", src, "-filter_complex", vf]
        # `shortest=1` is not enough to end this on the clip's last frame. The
        # background here is an INFINITE `color=` source, and on two of ski-demo's
        # clips the composite still ran past the input: 00-opening decodes 284
        # frames and wrote 285, 99-closing decodes 83 and wrote 85. Every other
        # alpha clip happened to come out right, which is what makes it a trap.
        # So the count is decoded first and the output capped to it outright.
        n = decoded_frames(src, dec)
        if n:
            cmd += ["-frames:v", str(n)]
    else:
        cmd = ["ffmpeg", "-v", "error"] + dec + ["-i", src, "-vf", vf]
    if alpha_png:
        cmd += ["-pix_fmt", "rgba"]
    else:
        cmd += ["-q:v", "3"]
    # -fps_mode passthrough: write EXACTLY the frames the file decodes, and no
    # others. Without it ffmpeg's image writer runs at constant frame rate and
    # fills the container's declared duration, which on every MP4 here is ~0.021s
    # longer than the last frame -- so it DUPLICATED the final frame to pad.
    # Measured: 01-login-and-code decodes 198 frames and produced 199 JPEGs;
    # 11-logout-menu decodes 125 and produced 127, its last three files
    # byte-identical. A preview that invents frames cannot be used to judge
    # length, and /api/save rebuilds from these frames, so the padding could be
    # written back into the real clip.
    r = subprocess.run(
        cmd + ["-fps_mode", "passthrough", "-start_number", "1",
               os.path.join(frames_dir, f"frame_%05d{ext}")],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg extraction failed:\n{r.stderr}")

    # Audio, alongside the frames. Frames alone cannot show SYNC — whether her
    # mouth matches her words is the one fault this tool kept missing — so the
    # clip's own audio is extracted once and played against the playhead.
    #
    # Re-encoded to AAC in m4a rather than copied: sources here are Opus-in-WebM
    # and AAC-in-mp4, and only one of those is playable everywhere. A viewer
    # that works for the mp4 and stays silent for the WebM would be worse than
    # no audio at all, because the silence looks like the clip.
    has_audio = extract_audio(src, outdir, log=log)

    nb_frames = len([f for f in os.listdir(frames_dir) if f.startswith("frame_")])
    if nb_frames == 0:
        raise RuntimeError("ffmpeg produced no frames — check the source file")

    disp_w = width if width <= box else box
    disp_h = height if height <= box else box
    if width >= height:
        disp_w, disp_h = box, round(box * height / width)
    else:
        disp_h, disp_w = box, round(box * width / height)

    meta = dict(sig, ext=ext, has_audio=has_audio, fps=fps, nb_frames=nb_frames, width=width, height=height,
                duration=duration, disp_w=disp_w, disp_h=disp_h,
                source_name=os.path.basename(src),
                # frame_map[i] is the SOURCE frame number cache frame i+1 shows.
                # Starts as the identity (cache frame N *is* source frame N) —
                # every Frame Editor edit updates this in lockstep with the
                # JPEGs, so a cut can later rebuild the same duplicates/gaps
                # from the real source instead of only ever matching it 1:1.
                frame_map=list(range(1, nb_frames + 1)),
                # Set true by any Frame Editor edit — lets the Save button
                # start disabled and only light up once there's something a
                # save would actually change, and lets a page reload after
                # edits know to re-enable it without guessing from N alone
                # (equal adds and deletes could leave N unchanged but the
                # clip genuinely edited).
                edited=False)
    json.dump(meta, open(meta_path, "w"), indent=2)
    write_viewer(outdir, meta)

    log(f"  {nb_frames} frames extracted ({fps:g}fps)")
    log(f"  wrote {os.path.join(outdir, 'viewer.html')}")
    return outdir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", help="cache dir (default: video_players/cache/<slug>/)")
    ap.add_argument("--box", type=int, default=750, help="viewer box, pixels (default 750)")
    ap.add_argument("--force", action="store_true", help="re-extract even if cached")
    a = ap.parse_args()
    try:
        build_frames(a.video, out=a.out, box=a.box, force=a.force)
    except RuntimeError as e:
        sys.exit(str(e))


def load_meta(outdir):
    return json.load(open(os.path.join(outdir, "meta.json")))


def save_meta(outdir, meta):
    json.dump(meta, open(os.path.join(outdir, "meta.json"), "w"), indent=2)


def get_frame_map(meta):
    """
    `frame_map` is missing on any cache built before this field existed —
    default to the identity mapping (cache frame N is source frame N), which
    is exactly correct for a cache nothing has ever edited. Never mutates
    `meta` itself; callers that edit the map must write it back explicitly.
    """
    return meta.get("frame_map") or list(range(1, meta["nb_frames"] + 1))


def group_frame_runs(seq):
    """
    Group a slice of `frame_map` values — the SOURCE frame each cache frame
    in this segment actually shows — into pieces a cut can build directly:

      ("cut", src_start, src_end)  a contiguous ascending run: cut straight
                                    from the source, exactly as before.
      ("hold", src_frame, count)   a repeated value — a Frame Editor
                                    duplicate — synthesized as that one
                                    source frame held for `count` frames.

    A jump that is neither +1 nor a repeat (a Frame Editor deletion sitting
    between two marks, or two marks either side of one) just ends one cut run
    and starts the next — nothing special has to happen for it; the deleted
    source frames are simply never referenced by any run.

    An unedited segment collapses to a single ("cut", start, end) — the exact
    shape /api/cut always produced before Frame Editor existed.
    """
    runs, i, n = [], 0, len(seq)
    while i < n:
        j = i
        if j + 1 < n and seq[j + 1] == seq[j]:
            while j + 1 < n and seq[j + 1] == seq[j]:
                j += 1
            runs.append(("hold", seq[i], j - i + 1))
        else:
            while j + 1 < n and seq[j + 1] == seq[j] + 1:
                j += 1
            runs.append(("cut", seq[i], seq[j]))
        i = j + 1
    return runs


def paste_frame(outdir, from_frame, at):
    """
    Put a COPY of frame `from_frame` immediately after frame `at`.

    Duplicate with two positions instead of one: the pixels come from
    `from_frame`, the insert happens at `at`. Everything after `at` shifts right
    by one, renamed in DESCENDING order so a shift never overwrites a file it
    has not read yet — the same rule duplicate_frame_right follows, for the same
    reason.

    EXACT, and that is the whole point. The frame map records the SOURCE frame
    the copy shows, so a pasted frame is the same frame the original was, not a
    re-encode of a picture of it. Going out to the system clipboard and back
    would cost a decode, a PNG round trip and an encode, and the map would have
    no idea what the pasted frame was — it would be a new picture that merely
    looks the same.

    Returns (new_nb_frames, new_current_frame) — the viewer lands ON the pasted
    frame, which is the one you want to look at after pasting.
    """
    meta = load_meta(outdir)
    n = meta["nb_frames"]
    for name, f in (("source", from_frame), ("target", at)):
        if not (1 <= f <= n):
            raise RuntimeError(f"{name} frame {f} is outside 1..{n}")
    frames_dir = os.path.join(outdir, "frames")
    ext = meta.get("ext", ".jpg")
    path = lambda f: os.path.join(frames_dir, f"frame_{f:05d}{ext}")

    # Read the pixels BEFORE any renaming — from_frame may itself be one of the
    # frames about to move.
    with open(path(from_frame), "rb") as r:
        pixels = r.read()
    fmap = get_frame_map(meta)
    src_index = fmap[from_frame - 1]

    for f in range(n, at, -1):
        os.rename(path(f), path(f + 1))
        _restamp(path(f + 1))
    with open(path(at + 1), "wb") as w:
        w.write(pixels)
    _restamp(path(at + 1))

    fmap[at:at] = [src_index]
    meta["frame_map"] = fmap
    meta["nb_frames"] = n + 1
    save_meta(outdir, meta)
    return n + 1, at + 1


def duplicate_frame_right(outdir, at, count):
    """
    Insert `count` copies of frame `at` immediately to its right, in the
    PREVIEW CACHE — the extracted JPEGs, never the source video. Frame `at`
    keeps its number; everything after it shifts right by `count` to make
    room. Files are renamed in DESCENDING order (highest frame first) so a
    shift never overwrites a file it hasn't read yet.

    No lower/upper bound beyond 1..n — duplicating the LAST frame is valid
    (extending a hold at the very end of the clip) and is exactly why this
    doesn't refuse at at == n.

    Returns (new_nb_frames, new_current_frame) — new_current_frame is the
    LAST inserted copy, so the viewer lands on the new content.
    """
    meta = load_meta(outdir)
    n = meta["nb_frames"]
    if not (1 <= at <= n):
        raise RuntimeError(f"frame {at} is outside 1..{n}")
    frames_dir = os.path.join(outdir, "frames")
    ext = meta.get("ext", ".jpg")
    path = lambda f: os.path.join(frames_dir, f"frame_{f:05d}{ext}")

    for f in range(n, at, -1):
        os.rename(path(f), path(f + count))
        _restamp(path(f + count))
    src_frame = path(at)
    for i in range(1, count + 1):
        # copy, not move — frame `at` itself must survive every iteration
        with open(src_frame, "rb") as r, open(path(at + i), "wb") as w:
            w.write(r.read())

    fmap = get_frame_map(meta)
    fmap[at:at] = [fmap[at - 1]] * count  # insert right after cache index at-1
    meta["frame_map"] = fmap
    meta["edited"] = True

    new_n = n + count
    meta["nb_frames"] = new_n
    meta["duration"] = new_n / meta["fps"]
    save_meta(outdir, meta)
    write_viewer(outdir, meta)
    return new_n, at + count


def duplicate_frame_left(outdir, at, count):
    """
    Insert `count` copies of frame `at` immediately to its LEFT. Frame `at`'s
    own content survives, but its number shifts to `at + count` — the new
    copies take the slots it used to occupy. Valid at at == 1 too (extending
    a hold at the very start of the clip).

    Read frame `at`'s bytes BEFORE shifting — the shift moves that same file
    out from under `at`'s old path.
    """
    meta = load_meta(outdir)
    n = meta["nb_frames"]
    if not (1 <= at <= n):
        raise RuntimeError(f"frame {at} is outside 1..{n}")
    frames_dir = os.path.join(outdir, "frames")
    ext = meta.get("ext", ".jpg")
    path = lambda f: os.path.join(frames_dir, f"frame_{f:05d}{ext}")
    original = open(path(at), "rb").read()

    for f in range(n, at - 1, -1):
        os.rename(path(f), path(f + count))
        _restamp(path(f + count))
    for i in range(count):
        open(path(at + i), "wb").write(original)

    fmap = get_frame_map(meta)
    fmap[at - 1:at - 1] = [fmap[at - 1]] * count  # insert right before cache index at-1
    meta["frame_map"] = fmap
    meta["edited"] = True

    new_n = n + count
    meta["nb_frames"] = new_n
    meta["duration"] = new_n / meta["fps"]
    save_meta(outdir, meta)
    write_viewer(outdir, meta)
    return new_n, at + count


def _restamp(path):
    """
    Give a frame file the current mtime.

    os.rename() carries a file's mtime with it, so after a Frame Editor shift
    `frame_00090.jpg` holds different pixels while still claiming the timestamp
    of whatever frame moved into that slot. The viewer fetches frames by a URL
    that does not change, so the browser revalidates with If-Modified-Since,
    the server truthfully answers 304, and the STALE picture is shown.

    The visible symptom is badly misleading: the frame count drops but the
    pictures do not move, so a delete in the middle of a clip looks exactly
    like frames being removed from the END. Reported 2026-08-21 as that.

    A frame's URL is its position, so its position changing IS its content
    changing, and the mtime has to say so.
    """
    try:
        os.utime(path, None)
    except OSError:
        pass


def delete_frames_left(outdir, at, count):
    """
    Delete up to `count` frames immediately to the LEFT of frame `at` — the
    preview cache only, never the source video. Clamped so it can never
    delete frame 1 or below; returns the ACTUAL number removed, which can be
    less than requested near the start of the clip.

    Files are shifted in ASCENDING order (lowest surviving frame first) so
    the shift never overwrites a file before it's been read.

    Returns (new_nb_frames, new_current_frame, actual_count, deleted_range) —
    new_current_frame is where frame `at`'s own content ends up after the
    gap closes; deleted_range is (first, last) of the removed frame numbers,
    for adjusting marks and for reporting to the user what was actually lost.
    """
    meta = load_meta(outdir)
    n = meta["nb_frames"]
    if not (1 <= at <= n):
        raise RuntimeError(f"frame {at} is outside 1..{n}")
    actual = min(count, at - 1)
    if actual <= 0:
        return n, at, 0, None

    frames_dir = os.path.join(outdir, "frames")
    ext = meta.get("ext", ".jpg")
    path = lambda f: os.path.join(frames_dir, f"frame_{f:05d}{ext}")
    del_start, del_end = at - actual, at - 1

    for f in range(del_start, del_end + 1):
        os.remove(path(f))
    for f in range(at, n + 1):
        os.rename(path(f), path(f - actual))
        _restamp(path(f - actual))

    fmap = get_frame_map(meta)
    del fmap[del_start - 1:del_end]
    meta["frame_map"] = fmap
    meta["edited"] = True

    new_n = n - actual
    meta["nb_frames"] = new_n
    meta["duration"] = new_n / meta["fps"]
    save_meta(outdir, meta)
    write_viewer(outdir, meta)
    return new_n, at - actual, actual, (del_start, del_end)


def delete_frames_right(outdir, at, count):
    """
    Delete up to `count` frames immediately to the RIGHT of frame `at` —
    frame `at` itself is never touched, so it keeps its own number and the
    viewer's current position doesn't move. Clamped so it can never delete
    past the last frame; returns the ACTUAL number removed.

    Files are shifted in ASCENDING order (lowest surviving frame first).
    """
    meta = load_meta(outdir)
    n = meta["nb_frames"]
    if not (1 <= at <= n):
        raise RuntimeError(f"frame {at} is outside 1..{n}")
    actual = min(count, n - at)
    if actual <= 0:
        return n, at, 0, None

    frames_dir = os.path.join(outdir, "frames")
    ext = meta.get("ext", ".jpg")
    path = lambda f: os.path.join(frames_dir, f"frame_{f:05d}{ext}")
    del_start, del_end = at + 1, at + actual

    for f in range(del_start, del_end + 1):
        os.remove(path(f))
    for f in range(del_end + 1, n + 1):
        os.rename(path(f), path(f - actual))
        _restamp(path(f - actual))

    fmap = get_frame_map(meta)
    del fmap[del_start - 1:del_end]
    meta["frame_map"] = fmap
    meta["edited"] = True

    new_n = n - actual
    meta["nb_frames"] = new_n
    meta["duration"] = new_n / meta["fps"]
    save_meta(outdir, meta)
    write_viewer(outdir, meta)
    # frame `at` itself was never moved — only frames after it were removed —
    # so the current position stays exactly where it was, unlike the left
    # variant where everything from `at` onward shifts.
    return new_n, at, actual, (del_start, del_end)


def duplicate_span(outdir, a, b):
    """
    Insert a copy of frames a..b immediately after b, in the PREVIEW CACHE.

    The single-frame version duplicates ONE frame `count` times; this repeats a
    RUN, which is what "loop this marked zone once more" means. Files shift in
    DESCENDING order so a move never lands on a file that has not been read yet
    — the same rule the single-frame path follows, and for the same reason.
    """
    meta = load_meta(outdir)
    n = meta["nb_frames"]
    a, b = int(a), int(b)
    if not (1 <= a <= b <= n):
        raise RuntimeError(f"span {a}..{b} is outside 1..{n}")
    k = b - a + 1
    frames_dir = os.path.join(outdir, "frames")
    ext = meta.get("ext", ".jpg")
    path = lambda f: os.path.join(frames_dir, f"frame_{f:05d}{ext}")

    for f in range(n, b, -1):
        os.rename(path(f), path(f + k))
        _restamp(path(f + k))
    for i in range(k):
        with open(path(a + i), "rb") as r, open(path(b + 1 + i), "wb") as w:
            w.write(r.read())

    fmap = get_frame_map(meta)
    fmap[b:b] = fmap[a - 1:b]
    meta["frame_map"] = fmap
    meta["edited"] = True
    new_n = n + k
    meta["nb_frames"] = new_n
    meta["duration"] = new_n / meta["fps"]
    save_meta(outdir, meta)
    write_viewer(outdir, meta)
    return new_n, b + k


def delete_span(outdir, a, b):
    """
    Remove frames a..b from the PREVIEW CACHE. The source video is untouched;
    only the extracted JPEGs and the frame map change.

    Refuses to empty the clip: something has to be left to look at, and a
    zero-frame cache is a broken viewer rather than a short one.
    """
    meta = load_meta(outdir)
    n = meta["nb_frames"]
    a, b = int(a), int(b)
    if not (1 <= a <= b <= n):
        raise RuntimeError(f"span {a}..{b} is outside 1..{n}")
    k = b - a + 1
    if k >= n:
        raise RuntimeError("that span is the whole clip — refusing to leave it empty")
    frames_dir = os.path.join(outdir, "frames")
    ext = meta.get("ext", ".jpg")
    path = lambda f: os.path.join(frames_dir, f"frame_{f:05d}{ext}")

    for f in range(a, b + 1):
        if os.path.exists(path(f)):
            os.remove(path(f))
    for f in range(b + 1, n + 1):
        os.rename(path(f), path(f - k))
        _restamp(path(f - k))

    fmap = get_frame_map(meta)
    del fmap[a - 1:b]
    meta["frame_map"] = fmap
    meta["edited"] = True
    new_n = n - k
    meta["nb_frames"] = new_n
    meta["duration"] = new_n / meta["fps"]
    save_meta(outdir, meta)
    write_viewer(outdir, meta)
    return new_n, max(1, a - 1)


def restore_map(outdir, target, log=print):
    """
    Put a cache back to a previous frame map — the mechanism behind per-scene
    undo.

    A frame map is the whole truth about an edited clip: it lists, for each
    cache frame, which SOURCE frame it shows. So any past state can be rebuilt
    from the source plus its map, and no history of the JPEGs themselves has to
    be kept.

    Re-extracting first is deliberate. Undoing an ADD could be done by deleting
    the inserted copies, but undoing a DELETE cannot -- those JPEGs are gone
    from disk. Rather than have undo work for one kind of edit and not the
    other, both go the same way: extract the source clean, then lay the target
    map over it. One path, always correct.

    Files are built into a temp directory and swapped in, so a failure part way
    through cannot leave a half-renumbered frames/ behind.
    """
    meta = load_meta(outdir)
    src = meta["source"]
    if not os.path.isfile(src):
        raise RuntimeError(f"source no longer exists: {src}")
    ext = meta.get("ext", ".jpg")

    # VALIDATED BEFORE ANYTHING IS RE-EXTRACTED. This used to re-extract first
    # and check afterwards, so a map that failed the check had already wiped the
    # edits it was meant to restore — the error read as "nothing happened" while
    # the cache was already back to raw.
    #
    # The count comes from the SOURCE, not from the cache, because the cache is
    # exactly what is about to be replaced.
    target = [int(x) for x in target]
    if not target:
        raise RuntimeError("refusing to restore an empty map")
    n_src = decoded_frames(src, ["-c:v", "libvpx-vp9"] if ext == ".png" else None)
    if n_src is None:
        raise RuntimeError(f"could not count the frames in {os.path.basename(src)}")
    bad = [x for x in target if not (1 <= x <= n_src)]
    if bad:
        raise RuntimeError(f"map refers to frames outside 1..{n_src}: {sorted(set(bad))[:5]}")

    build_frames(src, out=outdir, box=meta.get("box", 750), force=True,
                 log=log, alpha_png=(ext == ".png"))

    frames_dir = os.path.join(outdir, "frames")
    staging = os.path.join(outdir, "frames.restoring")
    shutil.rmtree(staging, ignore_errors=True)
    os.makedirs(staging)
    path = lambda d, f: os.path.join(d, f"frame_{f:05d}{ext}")
    try:
        for i, srcf in enumerate(target, 1):
            with open(path(frames_dir, srcf), "rb") as r, open(path(staging, i), "wb") as w:
                w.write(r.read())
        shutil.rmtree(frames_dir)
        os.rename(staging, frames_dir)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    meta["frame_map"] = target
    meta["nb_frames"] = len(target)
    meta["duration"] = len(target) / meta["fps"]
    meta["edited"] = target != list(range(1, n_src + 1))
    save_meta(outdir, meta)
    write_viewer(outdir, meta)
    return len(target)


# The second of this module's two per-editor knobs (CACHE is the other).
# Which player module writes a clip's own page differs by tool: the MP4
# Splitter uses its own player.py, the Segment and Avatar Editor uses its
# private _splitter_player.py copy. That single differing import line was
# half the reason three near-identical copies of this 776-line file existed.
#
# It stays a dotted NAME rather than an imported module because the import
# must happen late — inside the call. This module is the layer every player
# is built ON, so importing one at module level would make frames depend on
# the thing that depends on it, and neither would load.
PLAYER = "mp4_splitter.player"


def use_player(dotted_name):
    """Point write_viewer() at this editor's own player module.

    Call once at startup, beside use_cache(). Takes a dotted import path
    ("segment_avatar_editor._splitter_player"), not a module object, so the
    import stays late.
    """
    global PLAYER
    PLAYER = dotted_name
    return PLAYER


def write_viewer(outdir, meta):
    """
    (Re)write a clip's OWN page from meta.json, using whichever player this
    process was pointed at — see use_player() above.

    Every extracted clip gets one, including the clips a layered or timeline
    view is built from: it is what "Open this scene on its own" opens, and it
    is what a frame edit has to refresh.
    """
    import importlib
    importlib.import_module(PLAYER).write(outdir, meta)


