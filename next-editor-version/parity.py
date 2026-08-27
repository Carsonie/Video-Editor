#!/usr/bin/env python3
"""
What the rebuild still cannot do — measured, not remembered.

    python3 next-editor-version/parity.py
    python3 next-editor-version/parity.py --missing     # only the gaps

WHY THIS EXISTS
    `tests/test_editor.py` drives HTTP. Every check in it ends in an endpoint,
    so it proves the two BACKENDS agree and says NOTHING about whether a
    control exists to reach them. Both servers can answer perfectly while the
    rebuild has no button for half of it — and both do, today.

    So this asks the other question: for each control the Python players put on
    screen, does the React rebuild have one?

HOW IT DECIDES
    The Python side is read from the players' own markup — the `id` on every
    button, select, input and link inside their page templates. That list
    cannot go stale, because it IS the page.

    The React side has no ids, so a control is matched by a NEEDLE: a short
    string from the source that only that control's implementation contains.
    The needles are written down below, one per control, and each is a claim
    that can be checked by reading the line it points at.

    A needle is therefore the weak part, and deliberately so: it is easier to
    keep one honest string per control right than to keep a hand-written ToDo
    list right. When a control is built, its needle starts matching and it
    leaves this report without anyone editing anything.
"""
import argparse
import ast
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# control -> a string that only its React implementation contains
#
# Grouped by the PAGE the Python side puts it on, because that is the unit a
# person rebuilds: "the layered view" is one job, not six.
GROUPS = [
    ("MP4 Splitter", "next-editor-version/web/src/routes/Splitter.tsx", [
        ("Play / pause",              "play.toggle"),
        ("Mute",                      "setMuted"),
        ("Playback speed",            "0.125"),
        ("Six step buttons",          "onStep(-100)"),
        ("Loop Zone",                 "Loop Zone"),
        ("Timeline slider",           'className="slider"'),
        ("Mark / unmark",             "onMark"),
        ("Frame Editor mode",         "frame-editor"),
        ("Add / Subtract",            "＋ Add"),
        ("＋ / － Zone",               "＋ Zone"),
        ("Undo",                      "↶ Undo"),
        ("Break points / File tabs",  "Tabs.Tab"),
        ("Clear all marks",           "Clear all"),
        ("Cut into segments",         "Cut into segments"),
        ("Hand off to dev",           "Hand off to dev"),
        ("Save edited segment",       "Save edited segment"),
        ("Clear all edits",           "Clear all edits"),
        ("Reset Editor",              "Reset Editor"),
        ("Frame preloading",          "preloadFrames"),
    ]),
    ("Segment and Avatar Editor — timeline", "next-editor-version/web/src/routes/Editor.tsx", [
        ("Play / mute / speed",       "play.setRate"),
        ("Step 1 and 10 frames",      "onStep(10)"),
        ("Previous / next scene",     "onScene"),
        ("Mark, prev / next mark",    "onJumpMark"),
        ("Loop Zone",                 "loopZone"),
        ("Join, with a track picker", "onJoinTrack"),
        ("Split, with a track picker","onSplitTrack"),
        ("＋ / － Frame",              "onFrame("),
        ("＋ / － Zone",               "onZone("),
        ("Copy / Paste a frame",      "onPaste"),
        ("Cut scene",                 "Cut scene"),
        ("Save scene",                "Save scene"),
        ("Rebuild the timeline",      "onRebuild"),
        ("Select all / none",         "onSelectAll"),
        ("Update Frame Imbalance",    "onBalance"),
        ("Save all scenes",           "onSaveAll"),
        ("VTT, lines edited inline",  "VttPanel"),
        ("Per-scene undo",            "undoScene"),
        ("The naming MODAL",          "NameModal"),
        ("Per-row ＋ / － in the list","onRowEdit"),
        ("The balance report table",  "BalanceReport"),
        # `'left'` alone matched api.ts's own type signature — the API has
        # always taken a side, and no button reaches it. A needle has to point
        # at the CONTROL, not at the call it would make.
        ("＋ / － Frame on the LEFT",  "onFrameSide"),
    ]),
    ("Segment and Avatar Editor — layered (one scene)", None, [
        ("A dedicated layered page",  "routes/Pair.tsx"),
        ("Solo one layer",            "soloLayer"),
        ("Show / hide each layer",    "showLayer"),
        ("Segment version selector",  "versionSelect"),
        ("Pair slots on the browser", "PAIR_SLOT"),
        ("Sibling scene list",        "SiblingList"),
    ]),
]


def python_controls():
    """Every control id in the three Python page templates."""
    out = {}
    jobs = [("MP4 Splitter", "mp4_splitter/player.py", "TEMPLATE"),
            ("SAE layered", "segment_avatar_editor/player.py", "PAIR_TEMPLATE"),
            ("SAE timeline", "segment_avatar_editor/player.py", "SEQ_TEMPLATE")]
    for name, mod, var in jobs:
        src = open(os.path.join(REPO, mod)).read()
        tpl = ""
        for n in ast.parse(src).body:
            if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == var:
                tpl = ast.literal_eval(n.value)
        body = tpl.split("</style>", 1)[-1].split("<script>", 1)[0]
        out[name] = sorted(set(
            re.findall(r'<(?:button|select|input|a)\b[^>]*\bid="([\w-]+)"', body)))
    return out


def react_source():
    text = ""
    for f in sorted(glob.glob(os.path.join(HERE, "web", "src", "**", "*.ts*"),
                              recursive=True)):
        text += f"\n/* {os.path.relpath(f, REPO)} */\n" + open(f).read()
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--missing", action="store_true", help="only what is not built")
    a = ap.parse_args()

    react = react_source()
    py = python_controls()

    print(f"\n  Control parity — the Python players against the React rebuild")
    print(f"  {sum(len(v) for v in py.values())} controls in the Python markup: "
          + ", ".join(f"{k} {len(v)}" for k, v in py.items()))

    total = built = 0
    gaps = []
    for group, home, rows in GROUPS:
        lines = []
        for label, needle in rows:
            total += 1
            ok = needle in react
            built += ok
            if not ok:
                gaps.append((group, label))
            if ok and a.missing:
                continue
            lines.append(f"    {'✓' if ok else '✗'}  {label}")
        if lines:
            print(f"\n  {group}")
            if home:
                print(f"    {home}")
            print("\n".join(lines))

    print(f"\n  {built}/{total} controls built"
          + (f" — {len(gaps)} still to do" if gaps else " — nothing outstanding"))
    print("\n  A control leaves this report the moment its needle starts matching.")
    print("  Nothing here is hand-maintained except the needles themselves.\n")
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
