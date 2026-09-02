#!/usr/bin/env python3
"""
Frame Blender's own server — a separate small process on its own port, not a
route bolted onto shared/serve.py.

    python3 frame_blender/serve.py                # port 8843
    python3 frame_blender/serve.py --port 8899

WHY ITS OWN PROCESS, ON ITS OWN PORT
    Everything else the editors serve is reachable through shared/serve.py,
    which is one big router for two players plus the API every one of their
    buttons calls. Frame Blender started as a pure viewer, and Carson asked
    for it to have "its own localhost address" — a standalone diagnostic,
    not a feature bolted onto the editor that happens to share its cache.

    It has since grown Build, Save Scene, Undo and Save MP4. Save Scene and
    Undo are PROXIED straight to shared/serve.py rather than reimplemented,
    so staying separate never meant staying read-only — only that there is
    still exactly one real save/undo path, and this is a client of it.

    It also REUSES that cache (shared/frames.py's build_frames()), so
    opening a scene here that is already open in the editor is instant.

STATELESS, AS OF THE 2026-08-30 RESTRUCTURE
    This server holds NO current scene. Every request that acts on a pair
    names that pair in its own query string.

    It used to work the other way: `/` rendered a whole page around one
    pair and the process remembered it in module globals. Three things were
    wrong with that, and all three were reported as bugs before the cause
    was understood — the page could not truly be Cleared (the scene was
    baked into the HTML), "Load" could list scenes but never open one (the
    page could not change scene without a reload), and two browser tabs
    silently fought over the single remembered pair.

WHAT IT SERVES
    GET  /                                    the (empty) page
    GET  /web/*                               its css and js
    GET  /api/open_pair?base=&overlay=        JSON: slugs, frame counts, label
    GET  /api/libs_list?base=                 JSON: the store's sarah_clips/libs
    GET  /api/lib_media?path=                 a library file's raw bytes, audio intact
    GET  /api/load_store?path=                JSON: proxied /api/siblings
    GET  /build_clip?base=&overlay=&n=        build a real mp4 of N frames
    GET  /api/save_mp4?base=&n=               copy that build into the store
    POST /api/save_scene, /api/undo_scene     proxied to the main editor
    POST /api/gap_log                         appends a Gap Builder click to logs/gap_builder_<date>.log
    GET  /<slug>/frames/frame_NNNNN.{jpg,png} the extracted frames
"""
import argparse
import http.server
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))       # <repo>/frame_blender
ROOT = os.path.dirname(HERE)                             # <repo>
CACHE = os.path.join(ROOT, "cache")                       # SAME cache the editor uses
PREVIEWS = os.path.join(CACHE, "_previews")               # this tool's own mp4 output
GAP_LOG_DIR = os.path.join(ROOT, "logs")                  # same logs/ the editor's own daily log lives in
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "shared"))
sys.path.insert(0, os.path.join(ROOT, "build"))
import frames as build_mod                               # noqa: E402
import serve as main_serve                                # noqa: E402  for its session_log — see log()
from serve import safe_join, CUSTOMERS_ROOT               # noqa: E402
import build_scenes                                       # noqa: E402  reuse its real ffmpeg recipe


def log(path, payload, result, status):
    """
    Write one line into the SAME daily editing log shared/serve.py's own
    process writes — same file, same format, same day, even though this is
    a separate process. /api/save_scene and /api/undo_scene log themselves
    already: they're real HTTP calls INTO that other process's /api/save and
    /api/frames/restore, which log on the way through. Only this tool's own
    three actions (never touching that process) need to be told to.
    """
    main_serve.session_log(path, payload, result, status)

# The main editor, running separately on its own port. Save, Undo and Load
# all proxy to IT rather than re-implementing any of the three — one save
# path, one undo path, one source of the pristine/dirty flag, whichever tool
# asks. This means that server has to actually be running for those three
# buttons to work; Build MP4 and the frame-review tools underneath do not
# need it, since they never touch anything outside this tool's own cache.
MAIN_EDITOR = os.environ.get("MAIN_EDITOR_URL", "http://localhost:8842")


def _proxy(method, path, payload=None, timeout=120):
    """
    Forward one request to the main editor and hand back (status, body_dict).

    Never raises on the editor's OWN error responses (400/409/500) — those
    are real, meaningful answers ("stale", "unknown slug", ...) that the
    frame_blender frontend needs to see and act on, not failures of the
    proxy itself. Only a genuine connection failure (editor not running)
    is turned into a clear message instead of a raw stack trace.
    """
    url = MAIN_EDITOR + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {"error": f"editor returned {e.code}"}
    except urllib.error.URLError as e:
        return 503, {"error": f"main editor not reachable at {MAIN_EDITOR} — "
                               f"start it (python3 shared/serve.py) first. ({e.reason})"}



def next_versioned_name(folder, ext):
    """
    Next `YY-M-D_v<N><ext>` name in `folder` — same Add-V scheme
    shared/paths.py's archive_name_v already uses (two-digit year, unpadded
    month/day, sequence resetting daily), reimplemented small here because
    that one matches a bare folder name with no extension, and this always
    has one (`.mp4`) — matching it verbatim would never find last save and
    silently hand out v1 forever.
    """
    now = time.localtime()
    yy, mm, dd = now.tm_year % 100, now.tm_mon, now.tm_mday
    stem = f"{yy}-{mm}-{dd}"
    pat = re.compile(rf"^{re.escape(stem)}_v(\d+){re.escape(ext)}$")
    seen = 0
    if os.path.isdir(folder):
        for f in os.listdir(folder):
            m = pat.match(f)
            if m:
                seen = max(seen, int(m.group(1)))
    return f"{stem}_v{seen + 1}{ext}"


def build_preview_clip(seg, av, n, out):
    """
    The SAME one-pass recipe build_scenes.py uses for a real release build —
    picture and voice combined in a single ffmpeg call, never two passes —
    just capped to the first `n` frames instead of the whole scene. Reuses
    build_scenes' own probe()/run()/CANVAS/FPS rather than re-typing them,
    so this can't quietly drift from the tool that makes the real thing.

    `n` is clamped to the avatar's actual frame count — asking for more
    frames than exist would either error deep in ffmpeg or silently hold
    on nothing, neither of which says "you asked for too many" plainly.
    """
    B, P, R = build_scenes, build_scenes.probe, build_scenes.run
    CANVAS, FPS = B.CANVAS, B.FPS

    avail, _, aw, ah, _ = P(av, alpha=True)
    n = max(1, min(n, avail))
    if (aw, ah) != (CANVAS, CANVAS):
        return None, f"avatar is {aw}x{ah}, expected {CANVAS}x{CANVAS}"

    _, _, sw, sh, _ = P(seg)
    vf = ["setpts=PTS-STARTPTS"]
    if (sw, sh) != (CANVAS, CANVAS):
        vf.append(f"scale={CANVAS}:-2")
        vf.append(f"pad={CANVAS}:{CANVAS}:(ow-iw)/2:(oh-ih)/2:color=black")
    vf.append("setsar=1")
    vf.append("tpad=stop_mode=clone:stop_duration=60")   # hold if footage runs short

    dur = n / FPS
    R(["ffmpeg", "-v", "error",
       "-i", seg,
       "-c:v", "libvpx-vp9", "-i", av,          # the decoder MUST precede -i
       "-filter_complex",
       f"[0:v]{','.join(vf)}[bg];"
       f"[1:v]setpts=PTS-STARTPTS,format=yuva420p[fg];"
       f"[bg][fg]overlay=0:0:format=auto[v]",
       "-map", "[v]",
       "-map", "1:a",
       "-af", f"apad=whole_dur={dur:.6f}",       # pad HER VOICE to the picture's exact length
       "-frames:v", str(n),                      # -frames:v, never -t — see build_scenes.py
       "-c:v", "libx264", "-preset", "medium", "-crf", "20",
       "-pix_fmt", "yuv420p", "-r", str(FPS),
       "-c:a", "aac", "-b:a", "128k",
       "-movflags", "+faststart", "-y", out])
    return n, None

def video_root_of(seg_path):
    """
    <video folder> from a .../sandbox/<NN-label>/segment.mp4 path — up three
    levels. Shared by save_mp4 (writes video/sandbox_mp4_scenes/ there) and
    the libs list (reads sarah_clips/libs/ there), so the one assumption
    about the folder shape lives once. Returns None rather than guessing
    when the shape doesn't match, since a silently wrong folder here would
    make an action land somewhere that just looks empty.
    """
    label_dir = os.path.dirname(seg_path)
    sandbox_root = os.path.dirname(label_dir)
    if os.path.basename(sandbox_root) != "sandbox":
        return None
    return os.path.dirname(sandbox_root)


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/":
            return self.send_web("index.html", "text/html; charset=utf-8")
        if parsed.path.startswith("/web/"):
            return self.send_web(parsed.path[len("/web/"):])
        if parsed.path == "/api/open_pair":
            return self.open_pair(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/build_clip":
            return self.build_clip(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/stores":
            return self.stores()
        if parsed.path == "/api/load_video":
            return self.load_video(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/load_store":
            return self.load_store(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/save_mp4":
            return self.save_mp4(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/libs_list":
            return self.libs_list(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/lib_frames":
            return self.lib_frames(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/lib_media":
            return self.lib_media(urllib.parse.parse_qs(parsed.query))
        return super().do_GET()   # frame images, served from CACHE (see main())

    def do_POST(self):
        parsed = urllib.parse.urlsplit(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length)) if length else {}
        except json.JSONDecodeError:
            return self.json_error(400, "body must be JSON")
        if parsed.path == "/api/save_scene":
            return self.save_scene(payload)
        if parsed.path == "/api/undo_scene":
            return self.undo_scene(payload)
        if parsed.path == "/api/gap_log":
            return self.client_log(payload)
        return self.json_error(404, f"no such route: {parsed.path}")

    def client_log(self, payload):
        """
        POST {event, ...} -> appends one JSON line to logs/gap_builder_<date>.log.

        A debugging aid for the Gap Builder Controller Menu specifically:
        Carson tests through his own real browser tab, which this process
        cannot see into — the only way to know what he actually clicked, in
        order, and what state each click landed in, is if the page tells
        this server itself (see gapLog() in gap-builder.js, wired into every
        Controller Menu button plus both frame rows). Never raises: a log
        that can break the page is worse than no log — same promise
        shared/serve.py's own session_log() makes.
        """
        try:
            os.makedirs(GAP_LOG_DIR, exist_ok=True)
            path = os.path.join(GAP_LOG_DIR, f"gap_builder_{time.strftime('%Y%m%d')}.log")
            line = {"t": time.strftime("%H:%M:%S"), **payload}
            with open(path, "a") as fh:
                fh.write(json.dumps(line, sort_keys=True) + "\n")
        except Exception:
            pass
        self._relay(200, {"ok": True})

    def send_web(self, name, ctype=None):
        """
        One of this tool's own static files out of frame_blender/web/.

        Served from here rather than by pointing the handler's `directory`
        at web/ because that root is already the frame CACHE — the frames
        are the bulk of what this server hands out. `name` is resolved and
        then checked to still be inside web/, so a `..` cannot walk out.
        """
        root = os.path.join(HERE, "web")
        path = os.path.realpath(os.path.join(root, name))
        if not path.startswith(os.path.realpath(root) + os.sep) or not os.path.isfile(path):
            return self.json_error(404, f"no such file: {name}")
        if ctype is None:
            ctype = {".js": "application/javascript", ".css": "text/css"}.get(
                os.path.splitext(path)[1], "application/octet-stream")
        body = open(path, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # This page is edited constantly while it is open. A cached copy of
        # app.js is a fix that silently did not apply — which cost a real
        # round of "same problem???" before the restructure.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _relay(self, status, body):
        """Pass a proxied response straight through, status and all."""
        out = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def json_error(self, status, message):
        """
        The JSON-API equivalent of send_error() — and NOT interchangeable
        with it. http.server's send_error() writes `message` straight into
        the HTTP status line, which the library encodes as latin-1; an
        em dash or a curly quote in the text — exactly the house style used
        everywhere else in this codebase — throws UnicodeEncodeError there
        and takes the whole request thread down with it. Found by the test
        suite hitting "no pair open yet — load / first" for the first time;
        every message on this server had the same landmine sitting under it.
        A JSON body has no such limit, so this is also just the right
        response shape for an endpoint every other route here answers in JSON.
        """
        self._relay(status, {"error": message})

    def stores(self):
        """
        GET /api/stores -> every business/store, and the video folders each
        one has. Step one of Load: pick a store, then pick a video.

        Proxied to the main editor, which already answers exactly this for
        its own Load — one place decides what counts as a store.
        """
        status, body = _proxy("GET", "/api/stores")
        self._relay(status, body)

    def load_video(self, qs):
        """
        GET /api/load_video?root=<video folder> -> everything in that
        video's sandbox/ worth working on: one row per scene, plus the
        narration script that belongs to them.

        WHAT IS AND IS NOT A SCENE HERE
            A scene folder is `<NN>-<label>/`. `1000_archive/` is not one —
            it is a whole-generation backup Save All writes, and pulling it
            in would put an entire duplicate history in the scene list.
            Anything without the `<digits>-` shape is skipped for the same
            reason, so `z_History`, `_builds` and future siblings are
            excluded by the rule rather than by a list that has to be
            maintained.

        The per-scene rows (frame counts, cache slugs, pristine/dirty) come
        from the main editor's /api/siblings, so Frame Blender and the
        Segment and Avatar Editor cannot disagree about a scene's state.
        script.json is read here and returned alongside, because siblings
        answers about tracks and says nothing about the words.
        """
        rel = (qs.get("root") or [""])[0]
        if not rel:
            return self.json_error(400, "root is required")
        root = safe_join(rel)
        if root is None or not os.path.isdir(root):
            return self.json_error(400, f"not a folder under Customers/: {rel}")
        sandbox = os.path.join(root, "sandbox")
        if not os.path.isdir(sandbox):
            return self.json_error(400, f"no sandbox/ in {rel} — nothing to load")

        scene_re = re.compile(r"^(\d+)-(.+)$")
        first_seg = None
        for name in sorted(os.listdir(sandbox)):
            if not scene_re.match(name):
                continue          # 1000_archive, z_History, script.json, ...
            cand = os.path.join(sandbox, name, "segment.mp4")
            if os.path.isfile(cand):
                first_seg = cand
                break
        if first_seg is None:
            return self.json_error(400, f"no scene folders with a segment.mp4 in {rel}/sandbox")

        seg_rel = os.path.relpath(first_seg, CUSTOMERS_ROOT)
        status, body = _proxy(
            "GET", f"/api/siblings?{urllib.parse.urlencode({'path': seg_rel})}")
        if status != 200 or body.get("error"):
            return self._relay(status, body)

        script_p = os.path.join(sandbox, "script.json")
        script = None
        if os.path.isfile(script_p):
            try:
                script = json.load(open(script_p))
            except (json.JSONDecodeError, OSError) as e:
                script = {"error": f"script.json is unreadable: {e}"}
        body["script"] = script
        body["script_path"] = (os.path.relpath(script_p, CUSTOMERS_ROOT)
                                if os.path.isfile(script_p) else None)
        body["root"] = rel
        log("/api/load_video", {"root": rel}, body, status)
        self._relay(status, body)

    def load_store(self, qs):
        """
        GET /api/load_store?path=<rel to any scene file in the store>
        -> the main editor's own /api/siblings response, unchanged — the
        real per-scene list, frame counts, and pristine/dirty state, from
        the same place the SAE reads it. Frame Blender never computes this
        itself, so the two tools cannot disagree about what "dirty" means.
        """
        rel = (qs.get("path") or [""])[0]
        if not rel:
            return self.json_error(400, "path is required")
        status, body = _proxy("GET", f"/api/siblings?{urllib.parse.urlencode({'path': rel})}")
        log("/api/load_store", {"path": rel}, body, status)
        self._relay(status, body)

    # Fixed display order for sarah_clips/libs/'s known subfolders — plain
    # alphabetical would put "sound_bits" between "idle" and "stills",
    # ahead of "transitions"; Carson asked for it to show LAST instead. Any
    # future folder not in this list still shows up (libs_list() has always
    # auto-discovered whatever subfolders exist, unchanged here) — it just
    # sorts alphabetically after all of these.
    LIBS_GROUP_ORDER = ["gap-fillers", "idle", "stills", "transitions", "sound_bits"]

    def libs_list(self, qs):
        """
        GET /api/libs_list -> every file under this pair's sarah_clips/libs/,
        grouped by subfolder — the gap-filler library (see its own README).
        Read-only: this only reports what's there, it never writes to it.
        """
        base_p, _, _, _ = self._pair_from(qs)
        if base_p is None:
            return
        video_root = video_root_of(base_p)
        if video_root is None:
            return self.json_error(500, f"expected .../sandbox/<label>/segment.mp4, "
                                         f"got {base_p}")
        libs_dir = os.path.join(video_root, "sarah_clips", "libs")
        if not os.path.isdir(libs_dir):
            return self._relay(200, {"root": None, "groups": []})

        # sound_bits files are named "<NN>-<scene label>.<ext>", matching a
        # sandbox scene folder — so the SAME script.json that already holds
        # every scene's spoken line can supply it here too, keyed by that
        # label, rather than needing a second place to keep the words in
        # sync. Best-effort: a sound bit with no matching label just has no
        # "line" in its entry, and the client falls back to its filename.
        label_lines = {}
        script_path = os.path.join(video_root, "sandbox", "script.json")
        if os.path.isfile(script_path):
            try:
                script = json.load(open(script_path))
                label_lines = {s["label"]: s["line"] for s in script.get("scenes", []) if s.get("label")}
            except Exception:
                pass

        def sort_key(folder):
            try:
                return (self.LIBS_GROUP_ORDER.index(folder), folder)
            except ValueError:
                return (len(self.LIBS_GROUP_ORDER), folder)

        groups = []
        for folder in sorted(os.listdir(libs_dir), key=sort_key):
            fdir = os.path.join(libs_dir, folder)
            if not os.path.isdir(fdir):
                continue
            files = []
            for name in sorted(os.listdir(fdir)):
                if name.startswith("."):
                    continue
                p = os.path.join(fdir, name)
                if not os.path.isfile(p):
                    continue
                entry = {"name": name, "size": os.path.getsize(p),
                         "path": os.path.relpath(p, CUSTOMERS_ROOT)}
                if name.lower().endswith((".webm", ".mp4", ".mov")):
                    # A .webm here is always a transparent HeyGen render —
                    # same rule shared/serve.py's is_alpha() uses, inlined
                    # rather than importing one more name for one check.
                    try:
                        entry["dur"] = round(float(build_scenes.probe(
                            p, alpha=name.lower().endswith(".webm"))[1]), 2)
                    except Exception:
                        entry["dur"] = None
                if folder == "sound_bits":
                    label = re.sub(r"^\d+-", "", os.path.splitext(name)[0])
                    if label in label_lines:
                        entry["line"] = label_lines[label]
                files.append(entry)
            groups.append({"folder": folder, "files": files})

        self._relay(200, {"root": os.path.relpath(libs_dir, CUSTOMERS_ROOT), "groups": groups})

    def lib_frames(self, qs):
        """
        GET /api/lib_frames?path=<rel to a file under sarah_clips/libs/>
        -> {"kind": "clip"|"still", "n": <frame count>, "slug": <cache dir>,
            "ext": <frame file extension>}

        A clip (.webm/.mp4) goes through the SAME extraction every pair
        already uses -- alpha_png=True, because every file in this library
        is a transparent Sarah overlay, exactly like the OVERLAY track. A
        still (.png/.jpg) has no frames to extract, so it gets a one-frame
        cache entry built by hand instead — that way the page can address a
        still through the exact same slug+frame URL scheme as a real clip,
        rather than needing a second code path just for stills.
        """
        rel = (qs.get("path") or [""])[0]
        if not rel:
            return self.json_error(400, "path is required")
        p = safe_join(rel)
        if p is None or not os.path.isfile(p):
            return self.json_error(400, f"not a file under Customers/: {rel}")

        ext = os.path.splitext(p)[1].lower()
        if ext in (".png", ".jpg", ".jpeg"):
            import shutil
            outdir = os.path.join(CACHE, build_mod.slug_for(p))
            frames_dir = os.path.join(outdir, "frames")
            os.makedirs(frames_dir, exist_ok=True)
            frame_ext = ".jpg" if ext in (".jpg", ".jpeg") else ".png"
            dest = os.path.join(frames_dir, f"frame_00001{frame_ext}")
            if not os.path.isfile(dest):
                shutil.copyfile(p, dest)
            return self._relay(200, {"kind": "still", "n": 1,
                                      "slug": os.path.relpath(outdir, CACHE),
                                      "ext": frame_ext})

        out = build_mod.build_frames(p, box=750, alpha_png=True, log=lambda m: None)
        n = len([f for f in os.listdir(os.path.join(out, "frames")) if f.startswith("frame_")])
        self._relay(200, {"kind": "clip", "n": n,
                           "slug": os.path.relpath(out, CACHE), "ext": ".png"})

    def lib_media(self, qs):
        """
        GET /api/lib_media?path=<rel to a file under sarah_clips/libs/>
        -> the raw file, bytes as-is, WITH its audio track intact.

        /api/lib_frames above only ever extracts silent picture frames —
        every other Frame Selector feature works off those PNGs and never
        needed the sound. A sound bit's whole point is being heard, so it
        gets its own route straight to the source file, for a <video> tag
        to play directly rather than going through frame extraction at all.
        """
        rel = (qs.get("path") or [""])[0]
        if not rel:
            return self.json_error(400, "path is required")
        p = safe_join(rel)
        if p is None or not os.path.isfile(p):
            return self.json_error(400, f"not a file under Customers/: {rel}")
        ctype = {".webm": "video/webm", ".mp4": "video/mp4",
                 ".mov": "video/quicktime"}.get(os.path.splitext(p)[1].lower(),
                                                 "application/octet-stream")
        body = open(p, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def save_scene(self, payload):
        """POST {slug, which, force} -> proxied straight to /api/save."""
        status, body = _proxy("POST", "/api/save", payload)
        self._relay(status, body)

    def undo_scene(self, payload):
        """POST {slug, which, frame_map} -> proxied straight to /api/frames/restore."""
        status, body = _proxy("POST", "/api/frames/restore", payload)
        self._relay(status, body)

    def save_mp4(self, qs):
        """
        GET /api/save_mp4?n=<N> -> copy this tool's own build_clip output
        for N frames into <video folder>/video/sandbox_mp4_scenes/, named
        with the SAME dated version scheme (YY-M-D_v#) already used
        elsewhere in this repo for a kept, versioned copy of real work —
        reused here via shared/paths.py rather than a second naming rule.
        """
        base_p, _, _, _ = self._pair_from(qs)
        if base_p is None:
            return
        try:
            n = int((qs.get("n") or [""])[0])
        except ValueError:
            return self.json_error(400, "n must be an integer frame count")
        src = os.path.join(PREVIEWS, f"preview_{n}.mp4")
        if not os.path.isfile(src):
            return self.json_error(400, f"no built clip for {n} frames yet — "
                                         f"use Build (real speed) or Build MP4 first")

        video_root = video_root_of(base_p)
        if video_root is None:
            return self.json_error(500, f"expected .../sandbox/<label>/segment.mp4, "
                                         f"got {base_p}")

        dest_dir = os.path.join(video_root, "video", "sandbox_mp4_scenes")
        os.makedirs(dest_dir, exist_ok=True)
        name = next_versioned_name(dest_dir, ".mp4")
        dest = os.path.join(dest_dir, name)
        import shutil
        shutil.copy2(src, dest)
        result = {"saved": os.path.relpath(dest, CUSTOMERS_ROOT), "frames": n}
        log("/api/save_mp4", {"n": n}, result, 200)
        self._relay(200, result)

    def _pair_from(self, qs):
        """
        (base_path, overlay_path, base_rel, over_rel) from a request's own
        query string, or (None, ...) with the error already sent.

        Every scene-acting endpoint goes through here. That is the whole
        of the statelessness: the pair is an argument, never a thing this
        process remembers between requests.
        """
        base_rel = (qs.get("base") or [""])[0]
        over_rel = (qs.get("overlay") or [""])[0]
        if not base_rel:
            self.json_error(400, "base is required")
            return None, None, None, None
        base_p = safe_join(base_rel)
        if base_p is None or not os.path.isfile(base_p):
            self.json_error(400, f"not a file under Customers/: {base_rel}")
            return None, None, None, None
        over_p = None
        if over_rel:
            over_p = safe_join(over_rel)
            if over_p is None or not os.path.isfile(over_p):
                self.json_error(400, f"not a file under Customers/: {over_rel}")
                return None, None, None, None
        return base_p, over_p, base_rel, over_rel

    def open_pair(self, qs):
        """
        GET /api/open_pair?base=&overlay= -> what the page needs to render
        one pair: the two cache slugs, their frame counts and extensions, a
        label, and the paths echoed back so the page can name the pair in
        its own later requests.

        Returns JSON, not a page. The page is static and already loaded by
        the time this is called — which is what lets one tab open a
        different scene without a reload, and what lets Clear mean
        something.
        """
        base_p, over_p, base_rel, over_rel = self._pair_from(qs)
        if base_p is None:
            return
        if over_p is None:
            return self.json_error(400, "overlay is required")

        # Same extraction every player already uses — box=750 matches the
        # editors' own default, alpha_png=True on the overlay so its real
        # transparency survives (a flat JPEG would turn Sarah's corner black).
        base_out = build_mod.build_frames(base_p, box=750, log=lambda m: None)
        over_out = build_mod.build_frames(over_p, box=750, alpha_png=True,
                                          log=lambda m: None)
        base_meta = json.load(open(os.path.join(base_out, "meta.json")))
        over_meta = json.load(open(os.path.join(over_out, "meta.json")))
        base_n = len([f for f in os.listdir(os.path.join(base_out, "frames"))
                      if f.startswith("frame_")])
        over_n = len([f for f in os.listdir(os.path.join(over_out, "frames"))
                      if f.startswith("frame_")])
        self._relay(200, {
            "label": os.path.basename(os.path.dirname(base_rel)) or "pair",
            "base_slug": os.path.relpath(base_out, CACHE),
            "over_slug": os.path.relpath(over_out, CACHE),
            "base_n": base_n, "over_n": over_n,
            "max_n": max(base_n, over_n),
            "base_ext": base_meta.get("ext", ".jpg"),
            "over_ext": over_meta.get("ext", ".png"),
            "base_rel": base_rel, "over_rel": over_rel,
        })

    def build_clip(self, qs):
        """
        GET /build_clip?n=<N> -> {"url": "/_previews/preview_N.mp4", "frames": N}

        Builds a REAL mp4 of the first N frames of the pair currently open in
        the browser — same one-pass picture+voice recipe as a production
        build (see build_preview_clip's own docstring), just short. Exists so
        "run 100 frames, then look at them as an actual video" doesn't need
        the full scene finished first.
        """
        base_p, over_p, _, _ = self._pair_from(qs)
        if base_p is None:
            return
        if over_p is None:
            return self.json_error(400, "overlay is required")
        try:
            n = int((qs.get("n") or [""])[0])
        except ValueError:
            return self.json_error(400, "n must be an integer frame count")
        if n < 1:
            return self.json_error(400, "n must be at least 1")

        os.makedirs(PREVIEWS, exist_ok=True)
        # Named from the REQUESTED n until the build finishes, then renamed to
        # the ACTUAL frame count build_preview_clip clamped to. Naming it from
        # the request up front made "n=999999" on a 142-frame avatar produce
        # a file called preview_999999.mp4 holding 142 real frames — a
        # filename that lied about its own content the moment a request
        # asked for more than existed.
        tmp_out = os.path.join(PREVIEWS, f"_building_{os.getpid()}_{n}.mp4")
        try:
            got, err = build_preview_clip(base_p, over_p, n, tmp_out)
        except SystemExit as e:
            # build_scenes.run() exits the process on an ffmpeg failure — the
            # right call in a one-shot CLI tool, the wrong one inside a
            # request thread. Turn it back into an HTTP error instead of
            # letting it kill this request's thread silently.
            return self.json_error(500, str(e))
        if err:
            return self.json_error(400, err)

        out = os.path.join(PREVIEWS, f"preview_{got}.mp4")
        os.replace(tmp_out, out)

        result = {"url": f"/_previews/{os.path.basename(out)}", "frames": got}
        log("/build_clip", {"n": got}, result, 200)

        import json
        body = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Frame requests alone would be one line per image, hundreds per
        # page load — worth silencing the same way shared/serve.py's own
        # noise-control does, just simpler since this tool has one real
        # action (open_pair) to ever want a record of.
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8843)
    ap.add_argument("--no-session-log", action="store_true",
                     help="don't write Build/Save MP4/Load into logs/editor_<date>.log "
                          "— for a test run, not normal use")
    a = ap.parse_args()
    # A module attribute on the OTHER server's imported code, set from THIS
    # process — safe because it's a plain Python global, not shared state
    # between the two actual server processes, and read back by the same
    # module's own session_log() every time this process calls it.
    main_serve.SESSION_OFF = a.no_session_log

    os.makedirs(CACHE, exist_ok=True)
    import functools
    handler = functools.partial(Handler, directory=CACHE)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), handler)
    print(f"  frame blender serving on http://localhost:{a.port}")
    print(f"  cache: {CACHE}")
    print(f"  session log: {'off' if a.no_session_log else main_serve.SESSION_LOG}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
