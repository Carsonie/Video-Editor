#!/usr/bin/env python3
"""
Move a store's per-scene files into `final/dev/<NN>-<label>/`.

    python3 migrate_to_dev.py "<store>/help-videos/final" [--apply]

Without --apply it only PRINTS the plan. Every file move is listed before
anything happens, because this rearranges the only copy of work that took real
money and real recordings to produce.

WHAT MOVES
    segments/Num_5-v6-segment.mp4                  -> dev/05-…/segment-v6.mp4
    scenes/sarah-scene-05-alpha.webm               -> dev/05-…/narration-v1.webm
    sarah_clips/scene_overlays/v1/…-corner-…webm   -> dev/05-…/avatar-v1.webm
    (script.json's scene node)                     -> dev/05-…/scene.json

WHAT DOES NOT
    video/          finished videos, already versioned and already tidy
    sarah_clips/    the OPENING and CLOSING pieces are not per-scene
    work/           the cut plan
    z_History/      history

The narration clips have never carried a version — they are overwritten by name
on every render — so they are stamped v1 here, matched to the avatar set built
from them. From now on a re-render is a new version rather than a silent
replacement, which is the whole point.

`scene.json` is that scene's node from script.json, copied so a scene folder is
self-describing. script.json stays the source of truth; this is a convenience
and says so in the file.
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "shared"))
import paths as P


def main():
    if len(sys.argv) < 2:
        sys.exit('usage: migrate_to_dev.py "<store>/help-videos/final" [--apply]')
    final = os.path.abspath(sys.argv[1])
    apply = "--apply" in sys.argv
    scenes = [(n, lab or P.scene_label(final, n)) for n, lab in P.scenes_from_script(final)]
    if not scenes:
        sys.exit(f"no scenes in {P.script(final)}")

    cfg = json.load(open(P.script(final)))
    nodes = {s["n"]: s for s in cfg["scenes"]}

    moves, missing = [], []
    for n, label in scenes:
        dest = os.path.join(P.dev_root(final), P.slugify(label, n))
        seg = P.segment(final, n, label)
        nar = P.narration(final, n, label)
        av = P.avatar(final, n, label)
        if seg and "/dev/" not in seg:
            m = P.SEG_RE.match(os.path.basename(seg))
            # A legacy `segment-04-search.mp4` carries no version. It becomes v1:
            # it is the first tracked version of that footage, and calling it
            # anything else would imply a history the files do not have.
            v = m.group(2) if m else "1"
            moves.append((seg, os.path.join(dest, f"segment-v{v}.mp4")))
        if nar and "/dev/" not in nar:
            moves.append((nar, os.path.join(dest, "narration-v1.webm")))
        if av and "/dev/" not in av:
            avv = os.path.basename(os.path.dirname(av))
            avv = avv[1:] if avv.startswith("v") else "1"
            moves.append((av, os.path.join(dest, f"avatar-v{avv}.webm")))
        for what, got in (("segment", seg), ("narration", nar), ("avatar", av)):
            if not got:
                missing.append(f"scene {n} has no {what}")

    print(f"\n  {final}")
    print(f"  layout now: {P.layout(final)}   ->   dev/\n")
    cur = None
    for src, dst in moves:
        d = os.path.basename(os.path.dirname(dst))
        if d != cur:
            print(f"  {d}/")
            cur = d
        print(f"      {os.path.basename(dst):<22} <- {os.path.relpath(src, final)}")
    print(f"\n  {len(moves)} file(s) to move, {len(scenes)} scene folder(s)")
    for m in missing:
        print(f"  ⚠ {m}")

    if not apply:
        print("\n  DRY RUN — nothing moved. Re-run with --apply.\n")
        return

    for src, dst in moves:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
    for n, label in scenes:
        dest = os.path.join(P.dev_root(final), P.slugify(label, n))
        os.makedirs(dest, exist_ok=True)
        node = dict(nodes[n])
        node["_note"] = ("This scene's node, copied from script.json so this folder is "
                         "self-describing. script.json remains the source of truth — edit it "
                         "there, not here.")
        with open(os.path.join(dest, "scene.json"), "w") as fh:
            json.dump(node, fh, indent=2, ensure_ascii=False)
    # Leave the emptied folders behind only if something is still in them.
    for d in ("segments", "scenes"):
        p = os.path.join(final, d)
        if os.path.isdir(p) and not os.listdir(p):
            os.rmdir(p)
            print(f"  removed empty {d}/")
    print(f"\n  moved {len(moves)} file(s). layout is now: {P.layout(final)}\n")


main()
