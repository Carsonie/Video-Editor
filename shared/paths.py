#!/usr/bin/env python3
"""
ONE place that knows where a help video's parts live.

Before this, nine tools each hardcoded `segments/`, `scenes/`, `sarah_clips/`
and `video/`. Renaming anything meant finding all nine, and the two that were
missed failed quietly — a folder that no longer exists reads as "no files",
which looks like an empty store rather than a broken path.

TWO LAYOUTS, ON PURPOSE
-----------------------
    FLAT (original)                 DEV (per scene)
    final/segments/                 final/dev/05-dates-and-review/
      Num_5-v6-segment.mp4            segment-v6.mp4
    final/scenes/                     narration-v1.webm
      sarah-scene-05-alpha.webm       avatar-v1.webm
    final/sarah_clips/                scene.json
      scene_overlays/v1/…

DEV is preferred and FLAT is the fallback, per file, so a half-migrated store
keeps working and the other three stores are untouched until they are moved.
That is deliberate: a migration that must be finished in one go is a migration
that gets abandoned halfway with nothing working.

⚠ The fallback is per FILE, not per store. A scene moved to dev/ resolves there
even if its neighbours have not moved yet.
"""
import glob
import json
import os
import re
import shutil
import time

SEG_RE = re.compile(r"^Num_(\d+)-v(\d+)-segment\.mp4$")
# The ORIGINAL naming, still used by canoe-demo, bike-demo and alpine-sports:
# `segment-04-search.mp4`. Unversioned, and the scene NUMBER is in the name.
LEGACY_SEG_RE = re.compile(r"^segment-(\d+)(?:_\d+)?-(.+)\.mp4$")
DEV_SEG_RE = re.compile(r"^segment-v(\d+)\.mp4$")
DEV_AV_RE = re.compile(r"^avatar-v(\d+)\.webm$")
DEV_NAR_RE = re.compile(r"^narration-v(\d+)\.webm$")


def slugify(label, n):
    """`5, "dates-and-review"` -> `05-dates-and-review`. Zero-padded so a
    directory listing is already in scene order rather than 1, 10, 11, 2."""
    lab = re.sub(r"[^a-z0-9]+", "-", (label or "").lower()).strip("-")
    return f"{n:02d}-{lab}" if lab else f"{n:02d}"


def dev_root(final):
    return os.path.join(final, "dev")


def sandbox_root(final):
    return os.path.join(final, "sandbox")


def sandbox_dir(final, n, label=None):
    """Your edits for this scene. Mirrors dev/'s folder names so the pairing is
    obvious by eye rather than by rule."""
    root = sandbox_root(final)
    if os.path.isdir(root):
        for d in sorted(os.listdir(root)):
            if re.match(rf"^{n:02d}(-|$)", d) and os.path.isdir(os.path.join(root, d)):
                return os.path.join(root, d)
    return os.path.join(root, slugify(label, n))


def _sandbox(final, n, label, names):
    """First of `names` present in this scene's sandbox folder.

    Sandbox files carry NO version. They are yours, they are the newest thing
    you did, and versioning them would only invite the question this whole
    layer exists to avoid — which of my edits is the build using.
    """
    sd = sandbox_dir(final, n, label)
    for nm in names:
        p = os.path.join(sd, nm)
        if os.path.isfile(p):
            return p
    return None


def scene_dir(final, n, label=None):
    """This scene's dev folder, found by NUMBER rather than by name.

    The label is only a convenience for humans; matching on it would break the
    moment a scene is renamed in script.json, which has happened twice already.
    """
    root = dev_root(final)
    if os.path.isdir(root):
        for d in sorted(os.listdir(root)):
            if re.match(rf"^{n:02d}(-|$)", d) and os.path.isdir(os.path.join(root, d)):
                return os.path.join(root, d)
    return os.path.join(root, slugify(label, n))


def _newest(dirpath, rx):
    """Highest-versioned file matching `rx` in `dirpath` -> (path, version)."""
    if not os.path.isdir(dirpath):
        return None, None
    best = (None, -1)
    for f in os.listdir(dirpath):
        m = rx.match(f)
        if m and int(m.group(1)) > best[1]:
            best = (os.path.join(dirpath, f), int(m.group(1)))
    return (best[0], best[1]) if best[0] else (None, None)


def segment(final, n, label=None, version=None):
    """This scene's footage: sandbox -> dev -> flat.

    An explicit `version` skips the sandbox, because asking for v6 means v6 and
    a sandbox file has no version to compare against.
    """
    if version is None:
        sb = _sandbox(final, n, label, ("segment.mp4", "segment.mov"))
        if sb:
            return sb
    sd = scene_dir(final, n, label)
    if version is not None:
        p = os.path.join(sd, f"segment-v{version}.mp4")
        if os.path.isfile(p):
            return p
    else:
        p, _ = _newest(sd, DEV_SEG_RE)
        if p:
            return p
    flat = os.path.join(final, "segments")
    cands = []
    for f in glob.glob(os.path.join(flat, f"Num_{n}-v*-segment.mp4")):
        m = SEG_RE.match(os.path.basename(f))
        if m:
            cands.append((int(m.group(2)), f))
    if cands:
        if version is not None:
            hit = [f for v, f in cands if v == version]
            return hit[0] if hit else None
        return max(cands)[1]

    # Legacy `segment-NN-name.mp4`. script.json NAMES the file, so trust it over
    # any pattern of ours — three stores still use this scheme and their scripts
    # have no `label` to build a name from.
    node = _script_node(final, n)
    if node and node.get("segment"):
        cand = os.path.join(flat, node["segment"])
        if os.path.isfile(cand):
            return cand
    for f in glob.glob(os.path.join(flat, f"segment-{n:02d}-*.mp4")):
        return f
    return None


def _script_node(final, n):
    p = script(final)
    if not os.path.isfile(p):
        return None
    try:
        for s in json.load(open(p)).get("scenes", []):
            if int(s.get("n", -1)) == n:
                return s
    except Exception:
        pass
    return None


def scene_label(final, n):
    """A folder-safe name for this scene.

    `label` from script.json when it has one. Otherwise the stem of the LEGACY
    segment filename — `segment-04-search.mp4` -> `search` — because the three
    unmigrated stores have no labels and `04-` alone is a worse folder name than
    `04-search`. Numbers still do the matching; this only affects readability.
    """
    node = _script_node(final, n) or {}
    if node.get("label"):
        return node["label"]
    m = LEGACY_SEG_RE.match(node.get("segment", "") or "")
    return m.group(2) if m else ""


def narration(final, n, label=None):
    """The raw HeyGen render — what assemble_video composites. sandbox first."""
    sb = _sandbox(final, n, label, ("narration.webm",))
    if sb:
        return sb
    p, _ = _newest(scene_dir(final, n, label), DEV_NAR_RE)
    if p:
        return p
    for cand in (os.path.join(final, "scenes", f"sarah-scene-{n:02d}-alpha.webm"),
                 os.path.join(final, f"sarah-scene-{n:02d}-alpha.webm")):
        if os.path.isfile(cand):
            return cand
    return None


def avatar(final, n, label=None):
    """The corner-composited preview — what the layered editor lays on top."""
    sb = _sandbox(final, n, label, ("avatar.webm",))
    if sb:
        return sb
    p, _ = _newest(scene_dir(final, n, label), DEV_AV_RE)
    if p:
        return p
    root = os.path.join(final, "sarah_clips", "scene_overlays")
    if os.path.isdir(root):
        vs = sorted((int(m.group(1)) for d in os.listdir(root)
                     for m in [re.match(r"^v(\d+)$", d)] if m), reverse=True)
        for v in vs:
            cand = os.path.join(root, f"v{v}", f"sarah-scene-{n:02d}-corner-alpha.webm")
            if os.path.isfile(cand):
                return cand
    return None


def sandbox_only(final, n, label=None):
    """This scene's parts in the SANDBOX, or None. No fallback to dev.

    The editor uses this rather than the resolving lookups: while it is still
    being built, everything it reads and writes stays in sandbox/ and dev/ is
    the untouched copy. A tool under development should not be the only thing
    between a bad edit and a paid HeyGen render — this one has already shipped a
    bug that showed stale frames after a delete.

    Returning None for a missing part is the point: the editor must SHOW the gap
    rather than quietly fall through to dev and let an edit appear to work.
    """
    return {
        "segment": _sandbox(final, n, label, ("segment.mp4", "segment.mov")),
        "narration": _sandbox(final, n, label, ("narration.webm",)),
        "avatar": _sandbox(final, n, label, ("avatar.webm",)),
    }


def source_of(final, path):
    """Which layer a resolved path came from: `sandbox`, `dev` or `flat`.

    Every tool that BUILDS something must report this. A sandbox file silently
    entering a finished video is the one failure this layer could introduce, and
    it would be invisible in the output — the video would simply be different
    from the one the folder names imply.
    """
    if not path:
        return None
    ap = os.path.abspath(path)
    if ap.startswith(os.path.abspath(sandbox_root(final)) + os.sep):
        return "sandbox"
    if ap.startswith(os.path.abspath(dev_root(final)) + os.sep):
        return "dev"
    return "flat"


def script(final):
    return os.path.join(final, "video", "script.json")


def videos(final):
    return os.path.join(final, "video")


def versions(final):
    """Every version on disk, so a caller can SHOW which three are in play
    rather than assume they agree. They move independently and a mismatch is
    invisible in the picture until the wrong voice plays."""
    out = {"segment": [], "avatar": [], "script": []}
    # A legacy store has no segment versions at all — the naming carries none.
    # Reporting [] is correct and is what tells a caller it is unmigrated.
    root = dev_root(final)
    if os.path.isdir(root):
        for d in os.listdir(root):
            sd = os.path.join(root, d)
            if not os.path.isdir(sd):
                continue
            for f in os.listdir(sd):
                for rx, key in ((DEV_SEG_RE, "segment"), (DEV_AV_RE, "avatar")):
                    m = rx.match(f)
                    if m:
                        out[key].append(int(m.group(1)))
    flat = os.path.join(final, "segments")
    if os.path.isdir(flat):
        for f in os.listdir(flat):
            m = SEG_RE.match(f)
            if m:
                out["segment"].append(int(m.group(2)))
    ovr = os.path.join(final, "sarah_clips", "scene_overlays")
    if os.path.isdir(ovr):
        out["avatar"] += [int(m.group(1)) for d in os.listdir(ovr)
                          for m in [re.match(r"^v(\d+)$", d)] if m]
    vd = videos(final)
    if os.path.isdir(vd):
        out["script"] = [int(m.group(1)) for f in os.listdir(vd)
                         for m in [re.match(r"^script_v(\d+)\.json$", f)] if m]
    return {k: sorted(set(v), reverse=True) for k, v in out.items()}


def layout(final):
    """`dev`, `flat`, or `mixed` — for a tool that wants to say which it found."""
    has_dev = os.path.isdir(dev_root(final)) and any(
        os.path.isdir(os.path.join(dev_root(final), d)) for d in os.listdir(dev_root(final))
    ) if os.path.isdir(dev_root(final)) else False
    has_flat = bool(glob.glob(os.path.join(final, "segments", "Num_*-v*-segment.mp4")))
    return "mixed" if (has_dev and has_flat) else ("dev" if has_dev else "flat")


def scenes_from_script(final):
    """[(n, label)] in scene order, from the store's own script."""
    p = script(final)
    if not os.path.isfile(p):
        return []
    return [(s["n"], s.get("label", "")) for s in json.load(open(p)).get("scenes", [])]


# ── generation archives ─────────────────────────────────────────────────────
# Every folder that gets WRITTEN keeps its own z_History, and each write that
# replaces a generation of work puts the old one there first.
#
# One archive per generation, not per file. The per-file archives that already
# exist inside a scene folder answer "what did this clip look like before I
# saved it"; these answer "what did the whole folder look like before this
# batch", which is the question you have after a bad cut or a bad build.
#
# Named by DATE plus a sequence within that date: 2026-08-26-v_1, then v_2 the
# next time that day. A timestamp would sort correctly and read as noise; a bare
# sequence would sort correctly and say nothing. This says when, and which one.
ARCHIVE_DIR = "z_History"
_ARCHIVE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-v_(\d+)$")


def archive_name(folder, day=None):
    """The next archive name for `folder`, e.g. 2026-08-26-v_3."""
    day = day or time.strftime("%Y-%m-%d")
    root = os.path.join(folder, ARCHIVE_DIR)
    seen = 0
    if os.path.isdir(root):
        for d in os.listdir(root):
            m = _ARCHIVE_RE.match(d)
            if m and m.group(1) == day:
                seen = max(seen, int(m.group(2)))
    return f"{day}-v_{seen + 1}"


def archive_contents(folder, keep=(), move=True, only=None):
    """
    Put `folder`'s current generation into folder/z_History/<date>-v_N/.

    `move` decides which of the two shapes this is:

      MOVE  — the folder is being REPLACED wholesale, as when a fresh cut lands
              in dev/. Afterwards the folder is empty and the new work has it to
              itself, which is the point: dev holds one generation, not a pile.

      COPY  — the folder is being edited in place, as when the sandbox is saved.
              Moving there would take away the scenes this save is not touching.

    `keep` names entries that never move — z_History itself, and any staging
    folder the caller is about to read from. `only` narrows it to specific
    entries, for a folder that holds more than one kind of thing.

    Returns the archive path, or None when there was nothing to archive. Doing
    nothing is the normal case for a first run and must not look like a failure.
    """
    if not os.path.isdir(folder):
        return None
    skip = set(keep) | {ARCHIVE_DIR}
    names = [x for x in sorted(os.listdir(folder))
             if x not in skip and not x.startswith(".")]
    if only is not None:
        names = [x for x in names if x in set(only)]
    if not names:
        return None
    dest = os.path.join(folder, ARCHIVE_DIR, archive_name(folder))
    os.makedirs(dest, exist_ok=True)
    for x in names:
        src = os.path.join(folder, x)
        dst = os.path.join(dest, x)
        if move:
            shutil.move(src, dst)
        elif os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
    return dest
