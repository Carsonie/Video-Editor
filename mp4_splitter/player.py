#!/usr/bin/env python3
"""
The MP4 Splitter — the player that opens ONE clip and cuts it into numbered
segments at the break points you mark.

Its page is also every clip's own page: a layered or timeline view is built
from individual clips, and this is what each of them opens on its own.

Frame extraction, the frame map and the edit maths live in editor_base/ —
the one package every editor imports from (2026-09-03).

WHAT IS LEFT OF THIS FILE, AND WHY IT IS SHORT
    Until 2026-09-04 this module was 1,568 lines, almost all of them one
    Python string called TEMPLATE holding the entire clip page — HTML, CSS
    and 1,018 lines of JavaScript — with every brace doubled to survive
    str.format(). No editor could lint it, highlight it, or tell a CSS
    brace from a format placeholder, and a stray apostrophe killed the page
    at RENDER time rather than at edit time.

    The page is now three plain files in web/ — index.html, app.css,
    app.js — and the fourteen values that used to be baked into it arrive
    over GET /api/clip. What remains here is the player's identity.
"""
import os

from editor_base import frames

probe = frames.probe

# The player's name and version, shown at the foot of its page. The version
# lives in a VERSION file beside this module rather than in the source, so a
# bump is a one-line diff that a commit hook can see and a reader can trust.
NAME = "MP4 Splitter"

def _version():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")
    try:
        return open(p).read().strip() or "?"
    except OSError:
        return "?"

def label():
    return f"{NAME} v{_version()}"


def write(outdir, meta):
    """
    Called by editor_base.frames.write_viewer() after an extraction or a
    frame edit. It no longer writes anything, and that is the point.

    It used to render TEMPLATE into <cache>/<slug>/viewer.html — a complete,
    fully-baked copy of the page, one per clip. Since 2026-09-04 serve.py
    answers every `/<slug>/viewer.html` from web/index.html instead and
    ignores whatever file is on disk, so re-rendering would only produce a
    stale copy nothing reads.

    Leaving it as a no-op rather than deleting it keeps the one call site in
    editor_base shared with the Segment and Avatar Editor, whose own player
    has not been migrated yet (that is Step 13).

    `meta` is unused for the same reason: the page reads it back live from
    /api/clip, so it is always current rather than current as of the last
    write.
    """
    return None
