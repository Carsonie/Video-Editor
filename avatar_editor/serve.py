#!/usr/bin/env python3
"""
Avatar Editor's own server — a separate small process on its own port, not a
route bolted onto shared/serve.py.

    python3 avatar_editor/serve.py                # port 8844
    python3 avatar_editor/serve.py --port 8899

WHAT THIS IS
    A full duplicate of Frame Blender's own server (frame_blender/serve.py),
    copied whole on 2026-09-02 rather than shared — Carson's own call:
    Frame Blender and Avatar Editor are meant to grow different features
    from here, and code SHARED between them is code where a change to one
    can silently break the other. Everything below was true of Frame
    Blender at the moment of the copy; treat this file as its own thing
    from here on, not something to keep in sync with it.

WHY ITS OWN PROCESS, ON ITS OWN PORT
    Everything else the editors serve is reachable through shared/serve.py,
    which is one big router for two players plus the API every one of their
    buttons calls. Frame Blender started as a pure viewer with "its own
    localhost address" — a standalone diagnostic, not a feature bolted onto
    the editor that happens to share its cache — and Avatar Editor inherits
    that same shape on its own port.

    It has Build, Save Scene, Undo and Save MP4, plus its own store list
    (see stores()) — all standalone, none of them need shared/serve.py
    running on 8842 at all. Save Scene and Undo reuse shared/serve.py's own
    pure helper functions directly (build_segment, resolve_outdir, ...)
    rather than duplicating them, since that module is already imported
    here as a plain Python module — sharing the CODE, not the running
    PROCESS, so the ffmpeg recipe itself can't drift out of step with the
    main editor. See save_scene()'s own docstring for the cross-process
    dir_lock caveat this carries.

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
    GET  /api/libs_list?base=                 JSON: the store's sarah_clips/libs
    GET  /api/lib_media?path=                 a library file's raw bytes, audio intact
    GET  /api/load_store?path=                JSON: standalone — see siblings()/load_store()
    POST /api/save_scene, /api/undo_scene     standalone — see save_scene()
    POST /api/gap_log                         appends a Gap Builder click to logs/avatar_editor_gap_builder_<date>.log
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

HERE = os.path.dirname(os.path.abspath(__file__))       # <repo>/avatar_editor
ROOT = os.path.dirname(HERE)                             # <repo>
CACHE = os.path.join(ROOT, "cache")                       # SAME cache the editor uses
GAP_LOG_DIR = os.path.join(ROOT, "logs")                  # same logs/ the editor's own daily log lives in
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "shared"))
sys.path.insert(0, os.path.join(ROOT, "build"))
import frames as build_mod                               # noqa: E402
import serve as main_serve                                # noqa: E402  for its session_log — see log()
from serve import safe_join, CUSTOMERS_ROOT               # noqa: E402
import build_scenes                                       # noqa: E402  reuse its real ffmpeg recipe
import paths as PTH                                       # noqa: E402  script()/sandbox_root() — see stores()


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


def video_root_of(seg_path):
    """
    <video folder> from a .../sandbox/<NN-label>/segment.mp4 path — up three
    levels. Used by the libs list (reads sarah_clips/libs/ there). Returns
    None rather than guessing when the shape doesn't match, since a
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
        if parsed.path == "/api/stores":
            return self.stores()
        if parsed.path == "/api/load_video":
            return self.load_video(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/load_store":
            return self.load_store(urllib.parse.parse_qs(parsed.query))
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
        POST {event, ...} -> appends one JSON line to
        logs/avatar_editor_gap_builder_<date>.log — named distinctly from
        Frame Blender's own logs/gap_builder_<date>.log so the two tools'
        debug logs never collide if both run at once.

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
            path = os.path.join(GAP_LOG_DIR, f"avatar_editor_gap_builder_{time.strftime('%Y%m%d')}.log")
            line = {"t": time.strftime("%H:%M:%S"), **payload}
            with open(path, "a") as fh:
                fh.write(json.dumps(line, sort_keys=True) + "\n")
        except Exception:
            pass
        self._relay(200, {"ok": True})

    def send_web(self, name, ctype=None):
        """
        One of this tool's own static files out of avatar_editor/web/.

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
        api_stores()) — Carson asked for this tool to run standalone
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
        """
        POST {slug, which, force} -> rebuilds this cache slug's whole
        edited frame sequence and overwrites the file it came from.

        Was proxied straight to the main editor's own /api/save — Carson
        asked for this tool to run standalone instead. This is that
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
        it does NOT know about the main editor's own separate lock, OR
        Frame Blender's own, if either is also running. Don't Save/Undo
        the same slug from two of these at the same moment; that race is
        exactly what one shared process used to prevent for free, and
        every independent tool acting on the same cache reopens it.
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

            tmp_dir = tempfile.mkdtemp(prefix="avatar_editor_save_")
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
        # doesn't, this call is what keeps this tool's own saves in the
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

    def log_message(self, fmt, *args):
        # Frame requests alone would be one line per image, hundreds per
        # page load — worth silencing the same way shared/serve.py's own
        # noise-control does, just simpler since this tool has one real
        # action (open_pair) to ever want a record of.
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8844)
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
    print(f"  avatar editor serving on http://localhost:{a.port}")
    print(f"  cache: {CACHE}")
    print(f"  session log: {'off' if a.no_session_log else main_serve.SESSION_LOG}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
