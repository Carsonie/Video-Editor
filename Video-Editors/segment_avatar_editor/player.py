#!/usr/bin/env python3
"""
The Segment and Avatar Editor — one scene's footage with its alpha avatar laid
over it, in two shapes:

  layered   (PAIR_TEMPLATE)  one scene, mp4 underneath and WebM on top
  timeline  (SEQ_TEMPLATE)   several scenes joined, to judge how they JOIN

They are one player because they edit the same two layers with the same tools;
only the span differs. Frame extraction and the edit maths live in this
same package's own frames.py — duplicated from shared/frames.py on
2026-09-02 when this tool and MP4 Splitter split into fully independent
tools, not imported from shared/ any more.
"""
import json
import os

from editor_base import frames

probe = frames.probe
get_frame_map = frames.get_frame_map

# The player's name and version, shown at the foot of its page. The version
# lives in a VERSION file beside this module rather than in the source, so a
# bump is a one-line diff that a commit hook can see and a reader can trust.
NAME = "Segment and Avatar Editor"

def _version():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")
    try:
        return open(p).read().strip() or "?"
    except OSError:
        return "?"

def label():
    return f"{NAME} v{_version()}"


# ---------------------------------------------------------------------------
# THE TWO VIEWS — written as DATA, not as pages
# ---------------------------------------------------------------------------
#
# Until 2026-09-04 this file was 3,966 lines, and almost all of it was two
# Python strings — PAIR_TEMPLATE (733 lines) and SEQ_TEMPLATE (3,225) — each
# holding a whole page's HTML, CSS and JavaScript, rendered with
# str.format(). Every CSS and JS brace had to be doubled to survive that, no
# editor could lint or highlight any of it, and a stray apostrophe killed the
# page at RENDER time rather than at edit time.
#
# The page is now static files in web/ — seq.html/.css/.js — and
# write_seq() writes a small view.json instead. serve.py hands that back over /api/view, and the page fills
# itself in once it arrives.
#
# WHY A FILE AND NOT A REBUILD FROM meta.json. Most of what a view needs is
# not recoverable afterwards. `base_rel` and `overlay_rel` are handed in when
# a pair is opened; the timeline's `manifest`, which maps every global frame
# to (scene, local frame), is built at open time and exists nowhere else. A
# rebuild would have to guess them. So the open writes them down.


VIEW_FILE = "view.json"


def _write_view(outdir, view):
    with open(os.path.join(outdir, VIEW_FILE), "w") as fh:
        json.dump(view, fh, indent=2)


# ---------------------------------------------------------------------------
# SEQUENCE VIEW — several scenes on ONE timeline
# ---------------------------------------------------------------------------
#
# Each scene keeps its OWN extraction and its own cache; the manifest maps a
# global frame to (scene, local frame). Concatenating frames into one new
# cache would have been simpler and would have cost both the reuse and the
# ability to say WHICH scene is on screen.
#
# Frames are addressed as `../<slug>/frames/...`. Each clip keeps the SAME
# standalone cache it would get on its own, so opening a scene by itself and
# opening it in a timeline share one extraction instead of doubling it.


def write_seq(outdir, manifest, box=750, root_rel=""):
    """Record the multi-scene timeline view."""
    total = sum(m["base_n"] for m in manifest)
    names = ", ".join(str(m["n"]) for m in manifest)
    _write_view(outdir, {
        "kind": "seq",
        "player_label": label(),
        "title": f"timeline: scenes {names}",
        "box": box,
        "total": max(1, total),
        "manifest": manifest,
        "root_rel": root_rel,
    })
