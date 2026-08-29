#!/usr/bin/env python3
"""
Frame Blender's own server — a separate small process on its own port, not a
route bolted onto shared/serve.py.

    python3 frame_blender/serve.py                     # port 8843, ski-demo scene 1
    python3 frame_blender/serve.py --port 8899
    python3 frame_blender/serve.py --base <rel> --overlay <rel>   # any scene

WHY ITS OWN PROCESS, ON ITS OWN PORT
    Everything else the editors serve is reachable through shared/serve.py,
    which is one big router for two players plus the API every one of their
    buttons calls. Frame Blender does neither: it has no buttons that write
    anything, and Carson asked for it to have "its own localhost address" —
    a standalone diagnostic, not a feature bolted onto the editor that
    happens to share its cache.

    It still REUSES that cache (shared/frames.py's build_frames(), the same
    extraction every player already relies on) rather than re-implementing
    frame extraction a third time — opening a scene here that is already
    open in the editor is instant, because the frames are already on disk.

WHAT IT ACTUALLY SERVES
    GET /                                    ski-demo scene 1, the default
    GET /?base=<rel>&overlay=<rel>            any base/overlay pair
    GET /<slug>/frames/frame_NNNNN.{jpg,png}  the extracted frames themselves
"""
import argparse
import http.server
import os
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))       # <repo>/frame_blender
ROOT = os.path.dirname(HERE)                             # <repo>
CACHE = os.path.join(ROOT, "cache")                       # SAME cache the editor uses
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "shared"))
import frames as build_mod                               # noqa: E402
from serve import safe_join, CUSTOMERS_ROOT               # noqa: E402
import player as fb_player                                # noqa: E402

# The default pair this tool was built to chase down — ski-demo scene 1's
# blank-background-at-the-start finding. Overridable via ?base=&overlay=.
DEFAULT_BASE = ("Rentify Demos Corp/ski-demo/help-videos/videos/"
                 "01-first-time-ordering/sandbox/01-opening-with-login/segment.mp4")
DEFAULT_OVERLAY = ("Rentify Demos Corp/ski-demo/help-videos/videos/"
                    "01-first-time-ordering/sandbox/01-opening-with-login/avatar.webm")


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/":
            return self.open_pair(urllib.parse.parse_qs(parsed.query))
        return super().do_GET()   # frame images, served from CACHE (see main())

    def open_pair(self, qs):
        base_rel = (qs.get("base") or [DEFAULT_BASE])[0]
        over_rel = (qs.get("overlay") or [DEFAULT_OVERLAY])[0]
        base_p = safe_join(base_rel)
        over_p = safe_join(over_rel)
        if base_p is None or not os.path.isfile(base_p):
            return self.send_error(400, f"not a file under Customers/: {base_rel}")
        if over_p is None or not os.path.isfile(over_p):
            return self.send_error(400, f"not a file under Customers/: {over_rel}")

        # Same extraction every player already uses — box=750 matches the
        # editors' own default, alpha_png=True on the overlay so its real
        # transparency survives (a flat JPEG would turn Sarah's corner black).
        base_out = build_mod.build_frames(base_p, box=750, log=lambda m: None)
        over_out = build_mod.build_frames(over_p, box=750, alpha_png=True,
                                          log=lambda m: None)
        base_slug = os.path.relpath(base_out, CACHE)
        over_slug = os.path.relpath(over_out, CACHE)
        base_n = len([f for f in os.listdir(os.path.join(base_out, "frames"))
                      if f.startswith("frame_")])
        over_n = len([f for f in os.listdir(os.path.join(over_out, "frames"))
                      if f.startswith("frame_")])
        label = os.path.basename(os.path.dirname(base_rel)) or "pair"

        html = fb_player.render(base_slug, over_slug, base_n, over_n, label)
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
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
    ap.add_argument("--base", help="override the default base (segment) clip")
    ap.add_argument("--overlay", help="override the default overlay (avatar) clip")
    a = ap.parse_args()
    global DEFAULT_BASE, DEFAULT_OVERLAY
    if a.base:
        DEFAULT_BASE = a.base
    if a.overlay:
        DEFAULT_OVERLAY = a.overlay

    os.makedirs(CACHE, exist_ok=True)
    import functools
    handler = functools.partial(Handler, directory=CACHE)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), handler)
    print(f"  frame blender serving on http://localhost:{a.port}")
    print(f"  cache: {CACHE}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
