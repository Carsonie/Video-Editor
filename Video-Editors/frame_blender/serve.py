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

    It has since grown Build, Save Scene, Undo and Save MP4, plus its own
    store list (see stores()) — all standalone now, none of them need
    shared/serve.py running on 8842 at all. Save Scene and Undo used to be
    PROXIED there instead of reimplemented, so staying separate never meant
    staying read-only, but only one real save/undo path existed; Carson
    asked for genuine independence anyway (2026-09-02), accepting the
    tradeoff that came with it — see save_scene()'s own docstring for the
    cross-process dir_lock caveat that split brings back. Both still reuse
    shared/serve.py's own pure helper functions directly (build_segment,
    resolve_outdir, ...) rather than duplicating them, since that module is
    already imported here as a plain Python module — sharing the CODE, not
    the running PROCESS, so the ffmpeg recipe itself can't drift out of
    step between the two tools.

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
    GET  /api/stores                          JSON: every business/store and its videos
    GET  /api/open_pair?base=&overlay=        JSON: slugs, frame counts, label
    GET  /api/load_store?path=                JSON: standalone — see siblings()/load_store()
    GET  /build_clip?base=&overlay=&n=        build a real mp4 of N frames
    GET  /api/save_mp4?base=&n=               copy that build into the store
    POST /api/save_scene, /api/undo_scene     standalone — see save_scene()
    GET  /<slug>/frames/frame_NNNNN.{jpg,png} the extracted frames
"""
import argparse
import http.server
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))       # <repo>/frame_blender
ROOT = os.path.dirname(HERE)                             # <repo>
CACHE = os.path.join(ROOT, "cache", "_shared")            # SAME cache the old 8842 server uses
PREVIEWS = os.path.join(CACHE, "_previews")               # this tool's own mp4 output
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "shared"))
sys.path.insert(0, os.path.join(ROOT, "build"))
# frames.py and paths.py are editor_base/ since 2026-09-03 — one copy
# instead of three. The names still resolvable through shared/ are
# re-export shims for build/; import the real package directly.
from editor_base import frames as build_mod               # noqa: E402
import serve as main_serve                                # noqa: E402  for its session_log — see log()
from serve import safe_join, CUSTOMERS_ROOT               # noqa: E402
import build_scenes                                       # noqa: E402  reuse its real ffmpeg recipe
from editor_base import paths as PTH                      # noqa: E402  script()/sandbox_root() — see stores()


# This tool's own action labels, set as main_serve.ACTIONS in main() (same
# technique as the SESSION_LOG override there). shared/serve.py's own
# ACTIONS carries these same two routes labelled "FB: Load video"/"FB:
# Load store" — a prefix that made sense combined into one shared log
# with every other tool's actions in it, and is just noise now that this
# is this tool's OWN dedicated file. Every route this process actually
# logs against is here; nothing is dropped, only relabelled.
SESSION_ACTIONS = {
    "/api/save":           ("Save scene", ()),
    "/api/frames/restore": ("Undo",       ()),
    "/api/load_video":     ("Load video", ("root",)),
    "/api/load_store":     ("Load store", ("path",)),
    "/build_clip":         ("Build clip", ("n",)),
    "/api/save_mp4":       ("Save MP4",   ("n",)),
}


def log(path, payload, result, status):
    """
    Write one line into this tool's own daily editing log — a dedicated
    file (logs/frame_blender_<date>.log, set in main()), not shared/
    serve.py's logs/editor_<date>.log. Reuses that module's session_log()
    for the FORMATTING only (same shape every other editor's log uses) —
    it's still a plain Python function call, not an HTTP request, so
    nothing here proxies through the other process. Every real action
    (Load, Save, Undo, Build, Save MP4) calls this explicitly; none of
    them log themselves for free.
    """
    main_serve.session_log(path, payload, result, status)


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
    levels. Used by save_mp4, which writes video/sandbox_mp4_scenes/ there.
    Returns None rather than guessing when the shape doesn't match, since a
    silently wrong folder here would make an action land somewhere that
    just looks empty.
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
        return self.json_error(404, f"no such route: {parsed.path}")

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

        Was proxied to the main editor's OWN /api/stores (shared/serve.py's
        api_stores()) — Carson asked for Frame Blender to run standalone
        instead, sharing CODE (paths.py, same as here) rather than sharing
        a live PROCESS. This is that same walk, copied over rather than
        called over HTTP; keep the two in step if either changes.

        script.json is the check, not sandbox/ — a video can exist with a
        script and no sandbox yet built, and Load should still find it.
        Two levels down from Customers/ is assumed to be Business/store,
        same as /api/list's own STORE-folder detection.
        """
        out = []
        if not os.path.isdir(CUSTOMERS_ROOT):
            return self._relay(200, {"stores": out})
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
        self._relay(200, {"stores": out})

    def siblings(self, rel):
        """
        Every scene of this store, resolved — not a directory listing.
        Same recipe as the main editor's own api_siblings() (shared/
        serve.py), called directly rather than proxied: PTH.script(),
        .scenes_from_script(), .sandbox_only(), .source_of(),
        .sandbox_root(), .versions() and .layout() are already imported
        here as plain functions (paths.py never touched a live server to
        begin with), and frame_count()/cache_state() are pure module-level
        functions in shared/serve.py too — called off main_serve directly,
        not copied, so a scene's frame count and pristine/dirty state stay
        computed exactly one way no matter which tool asks. Only this
        orchestration is actually duplicated (see save_scene()'s own
        docstring for why that's the accepted tradeoff here).

        Returns (status, body) — the same shape _proxy() used to hand
        back, so load_video()/load_store() below barely had to change.
        """
        target = safe_join(rel)
        if target is None or not os.path.isfile(target):
            return 400, {"error": f"not a file under Customers/: {rel}"}

        # Walk up to the store's `final/` — the folder holding script.json.
        # NEVER stop ON `sandbox/` or `dev/` themselves, only above them —
        # script.json can live INSIDE sandbox/, so PTH.script(sandbox_dir)
        # would find that very file and stop one level too early.
        final = os.path.dirname(target)
        for _ in range(4):
            if (os.path.basename(final) not in ("sandbox", "dev")
                    and os.path.isfile(PTH.script(final))):
                break
            final = os.path.dirname(final)
        if not os.path.isfile(PTH.script(final)):
            return 400, {"error": f"no script.json above {rel}"}

        # SANDBOX ONLY — the editor does not read dev/.
        items = []
        for n, label in PTH.scenes_from_script(final):
            sb = PTH.sandbox_only(final, n, label)
            seg, av = sb["segment"], sb["avatar"]
            nfr, nex = (main_serve.frame_count(seg) if seg else (None, False))
            ofr, oex = (main_serve.frame_count(av) if av else (None, False))
            dur = None
            if seg:
                try:
                    dur = round(float(build_mod.probe(seg, "duration")), 2)
                except (ValueError, RuntimeError):
                    dur = None
            base_slug, base_edited = main_serve.cache_state(seg)
            over_slug, over_edited = main_serve.cache_state(av)
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

        # BOOKENDS and anything else in sandbox that is not a script scene —
        # numbered 00/99 so they sit at the ends of the list.
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
                bfr, bex = main_serve.frame_count(seg)
                afr, aex = (main_serve.frame_count(av) if os.path.isfile(av) else (None, False))
                base_slug, base_edited = main_serve.cache_state(seg)
                over_slug, over_edited = (main_serve.cache_state(av) if os.path.isfile(av)
                                           else (None, False))
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
        return 200, {
            "layout": PTH.layout(final),
            "editor_scope": "sandbox",
            "versions": v["segment"],
            "current_version": v["segment"][0] if v["segment"] else None,
            "overlay_version": v["avatar"][0] if v["avatar"] else None,
            "script_version": v["script"][0] if v["script"] else None,
            "by_version": {str(v["segment"][0] if v["segment"] else 0): items},
            "folder": os.path.relpath(final, CUSTOMERS_ROOT)}

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
        from siblings() above — the same recipe the Segment and Avatar
        Editor's own api_siblings() uses, called directly now rather than
        proxied to it, so the two tools still cannot disagree about a
        scene's state. script.json is read here and returned alongside,
        because siblings() answers about tracks and says nothing about
        the words.
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
        status, body = self.siblings(seg_rel)
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
        -> siblings() above — the real per-scene list, frame counts, and
        pristine/dirty state, computed the same way the SAE's own
        api_siblings() does (same shared helpers, called directly). Frame
        Blender never computes this a second, different way, so the two
        tools still cannot disagree about what "dirty" means.
        """
        rel = (qs.get("path") or [""])[0]
        if not rel:
            return self.json_error(400, "path is required")
        status, body = self.siblings(rel)
        log("/api/load_store", {"path": rel}, body, status)
        self._relay(status, body)

    def save_scene(self, payload):
        """
        POST {slug, which, force} -> rebuilds this cache slug's whole
        edited frame sequence and overwrites the file it came from.

        Was proxied straight to the main editor's own /api/save — Carson
        asked for Frame Blender to run standalone instead. This is that
        same recipe (shared/serve.py's api_save()), with its own pure
        helpers (resolve_outdir, is_alpha, build_segment, save_marks, ...)
        called directly off main_serve rather than copied, since that
        module is already imported here — same functions, same behavior,
        no second copy of the ffmpeg recipe to drift out of step. Only
        the orchestration below (archive-then-overwrite, the stale check,
        the frame-count warning) is actually duplicated, because that part
        is a Handler method bound to a different response convention
        (send_json there, _relay here).

        ⚠ dir_lock only guards THIS process's own concurrent requests —
        it does NOT know about the main editor's own separate lock if
        that's also running. Don't Save/Undo the same slug from both
        Frame Blender and the main editor at the same moment; that race
        is exactly what the single shared process used to prevent for
        free, and splitting the process reopens it.
        """
        outdir = main_serve.resolve_outdir(payload.get("slug"), payload.get("which"))
        if outdir is None:
            return self.json_error(400, "unknown slug")
        with build_mod.dir_lock(outdir):
            meta = json.load(open(os.path.join(outdir, "meta.json")))
            src, fps = meta["source"], meta["fps"]
            if not os.path.isfile(src):
                return self.json_error(500, f"source no longer exists: {src}")

            st = os.stat(src)
            stale = (st.st_size != meta.get("size") or st.st_mtime != meta.get("mtime"))
            if stale and not payload.get("force"):
                return self._relay(409, {
                    "error": "stale",
                    "message": f"{os.path.basename(src)} changed on disk since this was "
                               f"loaded here — probably saved from another tab or tool. "
                               f"Reload it to see the new version, or save again with "
                               f"force to overwrite it anyway.",
                })

            frame_map = build_mod.get_frame_map(meta)
            want_frames = len(frame_map)

            tmp_dir = tempfile.mkdtemp(prefix="frame_blender_save_")
            try:
                runs = build_mod.group_frame_runs(frame_map)
                built = os.path.join(tmp_dir, "built.webm" if main_serve.is_alpha(src) else "built.mp4")
                r = main_serve.build_segment(src, fps, runs, built, tmp_dir)
                if r.returncode != 0:
                    return self.json_error(500, r.stderr[-500:])
                got = float(build_mod.probe(built, "duration"))

                hist_dir = os.path.join(os.path.dirname(src), "z_History", time.strftime("%Y%m%d-%H%M%S"))
                os.makedirs(hist_dir, exist_ok=True)
                archived = os.path.join(hist_dir, os.path.basename(src))
                shutil.copy2(src, archived)

                shutil.copy2(built, src)
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

            nb_frames = wrote = None
            warning = None
            try:
                build_mod.build_frames(src, out=outdir, box=meta.get("box", 750),
                                        force=True,
                                        alpha_png=(meta.get("ext") == ".png"),
                                        log=lambda m: sys.stderr.write(m + "\n"))
                main_serve.save_marks(outdir, [])
                new_meta = json.load(open(os.path.join(outdir, "meta.json")))
                nb_frames = new_meta["nb_frames"]

                wrote = build_mod.decoded_frames(src, main_serve.dec_for(src))
                if wrote is not None and wrote != want_frames:
                    warning = (f"wrote {wrote} frames, expected {want_frames} — the rebuild "
                               f"is time-based and loses a frame per cut")
            except RuntimeError as e:
                warning = (f"saved, but the live preview cache could not be refreshed "
                           f"({e}). Reload this scene to see the new frames.")
        result = {"path": src, "archived_to": archived, "duration_s": round(got, 3),
                  "nb_frames": nb_frames,
                  "frames_written": wrote, "frames_expected": want_frames,
                  "warning": warning}
        # Logged as "/api/save" (not "/api/save_scene") on purpose — that's
        # the ACTIONS key shared/serve.py's own "Save scene" label is
        # registered under, and a proxied save used to land in this same
        # log automatically by making that literal HTTP call. Now that it
        # doesn't, this call is what keeps Frame Blender's saves in the
        # one editing record, same as before.
        log("/api/save", payload, result, 200)
        self._relay(200, result)

    def undo_scene(self, payload):
        """
        POST {slug, which, frame_map} -> restore one clip's cache to the
        given frame map — one step of the per-scene undo, same recipe as
        the main editor's own api_restore(). There is no server-side undo
        HISTORY on either side: frame_map is supplied by the page itself
        (it snapshots the map before making the edit being undone), so
        there is no in-memory state a separate process could fail to see.
        See save_scene's own docstring for the dir_lock cross-process
        caveat — it applies here too.
        """
        outdir = main_serve.resolve_outdir(payload.get("slug"), payload.get("which"))
        if outdir is None:
            return self.json_error(400, "unknown slug")
        target = payload.get("frame_map")
        if not isinstance(target, list) or not target:
            return self.json_error(400, "frame_map must be a non-empty list")
        with build_mod.dir_lock(outdir):
            try:
                n = build_mod.restore_map(outdir, target, log=lambda m: sys.stderr.write(m + "\n"))
            except (RuntimeError, OSError) as e:
                return self.json_error(400, str(e))
            marks = [m for m in main_serve.load_marks(outdir) if 1 <= m <= n]
            main_serve.save_marks(outdir, marks)
            meta = json.load(open(os.path.join(outdir, "meta.json")))
        result = {"nb_frames": n, "marks": sorted(marks), "edited": bool(meta.get("edited"))}
        # "/api/frames/restore" — the ACTIONS key "Undo" is registered
        # under; see save_scene()'s own comment on why this call exists now.
        log("/api/frames/restore", payload, result, 200)
        self._relay(200, result)

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
                     help="don't write Build/Save MP4/Load into logs/frame_blender_<date>.log "
                          "— for a test run, not normal use")
    a = ap.parse_args()
    # Module attributes on the OTHER server's imported code, set from THIS
    # process — safe because they're plain Python globals, not shared state
    # between the two actual server processes, and read back by the same
    # module's own session_log() every time this process calls it.
    main_serve.SESSION_OFF = a.no_session_log
    # A dedicated file, not shared/serve.py's own logs/editor_<date>.log —
    # every editor logs to its own file now (Carson's own call, 2026-09-02),
    # so one editor's actions are never interleaved with another's in the
    # same log. Reuses session_log()'s own FORMATTING code (still imported
    # as a plain module, per this file's own "share code not process" note
    # above) — only the destination file changes.
    main_serve.SESSION_LOG = os.path.join(
        main_serve.SESSION_DIR, f"frame_blender_{time.strftime('%Y%m%d')}.log")
    # Same idea, for the LABELS session_log() writes — see SESSION_ACTIONS'
    # own comment above for why the "FB:" prefix drops off here.
    main_serve.ACTIONS = SESSION_ACTIONS

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
