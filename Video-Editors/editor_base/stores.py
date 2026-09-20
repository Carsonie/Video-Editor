"""
Which videos a Load picker can offer, for every editor that has one.

⚠ THIS WAS THE SAME LOOP, WRITTEN OUT THREE TIMES — in the Segment and Avatar
Editor, in Frame Blender and in Avatar Editor. All three named
`help-videos/videos/`, all three went blank on 2026-09-15 when every store was
split into `BCP_raw_mp4/`, `UI_raw_mp4/`, `development_videos/` and
`Completed_Videos/`, and all three stayed blank for six days because nothing
fails when a listing is empty — the picker just has nothing in it. Fixing one
copy would have left two.

The rule, and the reason it is a rule (see `record_flow.ts`'s `rawSubdirFor`
and `scene_script.py`'s `raw_folder`, which already work this way):

    NEVER NAME A STAGE FOLDER. READ WHAT IS THERE.

A store that gains a stage later needs no change here, and a store that has not
been split yet keeps working, because neither case is written down anywhere.

    from editor_base import stores
    stores.list_stores(CUSTOMERS_ROOT)     # -> [{business, store, videos: [...]}]
"""
import json
import os

from editor_base import paths as PTH

# Superseded work, not something to open. Everything else under help-videos/ is
# a stage a video can legitimately live in.
SKIP = {"z_History", "z_history", "z_history_old"}


def stage_dirs(hv):
    """Every folder under one store's help-videos/ that could hold a video."""
    if not os.path.isdir(hv):
        return []
    return [d for d in sorted(os.listdir(hv), key=str.lower)
            if not d.startswith(".") and d not in SKIP
            and os.path.isdir(os.path.join(hv, d))]


def videos_in(store_dir, biz, store):
    """
    Every video folder in one store, whatever stage it sits in.

    `script.json` is the check, not `sandbox/`: a video can have words and no
    scene folders yet (a fresh store, before its first build), and Load should
    still find it. Opening one is what needs `sandbox/`, and that fails on its
    own terms with a message about the folder.
    """
    hv = os.path.join(store_dir, "help-videos")
    out = []
    for stage in stage_dirs(hv):
        stage_root = os.path.join(hv, stage)
        for vname in sorted(os.listdir(stage_root), key=str.lower):
            vdir = os.path.join(stage_root, vname)
            if vname.startswith(".") or not os.path.isdir(vdir):
                continue
            script_p = PTH.script(vdir)
            if not os.path.isfile(script_p):
                continue
            try:
                doc = json.load(open(script_p))
                ns = sorted(x["n"] for x in doc.get("scenes", []) if "n" in x)
            except (OSError, ValueError, KeyError):
                ns = []                       # a listing is not the place to fail
            # ⚠ THE STAGE IS PART OF THE NAME. A store holds `login` under
            # UI_raw_mp4 and `store` under BCP_raw_mp4; two bare labels in a
            # picker cannot say which surface either came from.
            out.append({"name": f"{stage}/{vname}",
                        "root": f"{biz}/{store}/help-videos/{stage}/{vname}",
                        "stage": stage,
                        "scenes": ns,
                        "has_sandbox": os.path.isdir(PTH.sandbox_root(vdir))})
    return out


def list_stores(customers_root):
    """
    Two levels under Customers/ is Business/store — the same assumption each
    editor's own folder browser already makes, walked in one go here because a
    picker that asks which business first is a step nobody wanted.
    """
    out = []
    if not os.path.isdir(customers_root):
        return out
    for biz in sorted(os.listdir(customers_root), key=str.lower):
        biz_dir = os.path.join(customers_root, biz)
        if biz.startswith(".") or not os.path.isdir(biz_dir):
            continue
        for store in sorted(os.listdir(biz_dir), key=str.lower):
            store_dir = os.path.join(biz_dir, store)
            if store.startswith(".") or not os.path.isdir(store_dir):
                continue
            videos = videos_in(store_dir, biz, store)
            if videos:
                out.append({"business": biz, "store": store, "videos": videos})
    return out
