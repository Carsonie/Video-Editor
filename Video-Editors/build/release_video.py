#!/usr/bin/env python3
"""
Hand ONE finished build to the customer folder in Basic_E2E_Testing.

    python3 build/release_video.py "<video folder>" --version 27
    python3 build/release_video.py "<video folder>" --version 27 --dry-run

THE ONLY THING THAT MAY WRITE INTO A STORE'S help-videos/ OVER THERE.

WHY IT EXISTS
    Until 2026-08-28 both repos held the same working files, and the customer
    folder accumulated every attempt — ski-demo's held v10 through v22 beside
    2.2 GB of raw recordings and sandbox scenes. Nothing said which file a
    customer would actually be served.

    Now the rule is a folder-shaped one: a store's help-videos/ over there holds
    a README, and ONE FOLDER PER VIDEO. If it is in there it shipped. This
    tool is what puts it there.

    Widened 2026-09-04 (Carson): a release is no longer the mp4 on its own.
    The video, the words that made it, and the timing table travel together,
    in a folder named for the video — so a year from now the file and its
    script cannot be separated by a tidy-up.

WHAT IT DOES, EXACTLY
    Creates  <BASIC>/Customers/<Business>/<store>/help-videos/<NN-slug>/
    and puts three things in it:

        <store>_<title>_v<N>.mp4     the build            (required)
        script_v<N>.json             the words it used    (required)
        vtt.html                     the timing table     (if one exists)

    <NN-slug> is the video folder's own name — `01-first-time-ordering` —
    so the shape over there matches the shape here.

    Any EARLIER release of that same title moves into <NN-slug>/z_History/,
    so the folder always shows one video. It never deletes a release;
    superseding one is a move.

    script_v<N>.json is REQUIRED because build_scenes.py --join writes it on
    every join. If it is missing, the build did not come from a join and the
    release is refused rather than shipping a video whose words are unknown.
    vtt.html is optional — it is generated on demand by build/vtt_html.py.

    The copy is verified byte-for-byte before the old one is stood down. On one
    APFS volume `cp -c` clones, so a 6 MB video costs no disk and no time.

WHAT IT REFUSES TO DO
    - Release a build whose frame count does not match its own duration. That
      is the exact defect that shipped for weeks: a playable file, right frame
      count, wrong clock. Checked here because this is the last gate.
    - Overwrite a release that is already there with different bytes, unless
      --force. Two different files under one version number is the one mistake
      that cannot be untangled afterwards.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "shared"))

# The sibling repo that serves customers. Overridable so this is not a machine
# fact baked into a script — see BASIC_REPO in the environment.
DEFAULT_BASIC = os.path.join(os.path.expanduser("~"), "Rentify", "Basic_E2E_Testing")


def basic_root():
    root = os.environ.get("BASIC_REPO", DEFAULT_BASIC)
    if not os.path.isdir(os.path.join(root, "Customers")):
        sys.exit(f"  no Customers/ under {root}\n"
                 f"  set BASIC_REPO to where Basic_E2E_Testing is checked out")
    return root


def store_path_of(folder):
    """
    The `<Business>/<store>` pair this video belongs to, read off the path.

    A video folder is always
        Customers/<Business>/<store>/help-videos/videos/<NN-slug>/
    so the pair is two levels under Customers/. Derived rather than asked for:
    a mistyped store name would file a finished video under the wrong customer.
    """
    parts = os.path.abspath(folder).split(os.sep)
    try:
        i = len(parts) - 1 - parts[::-1].index("Customers")
    except ValueError:
        sys.exit(f"  {folder} is not under a Customers/ folder")
    if len(parts) < i + 3:
        sys.exit(f"  cannot read <Business>/<store> out of {folder}")
    return parts[i + 1], parts[i + 2]


def probe(path):
    """(decoded frame count, container duration, fps) — the three that must agree."""
    def q(*entries):
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-show_entries", *entries, "-of", "csv=p=0", path],
                           capture_output=True, text=True)
        return r.stdout.strip().splitlines()
    dur = float(q("format=duration")[0])
    fps_raw = q("stream=r_frame_rate")[0]
    num, den = (fps_raw.split("/") + ["1"])[:2]
    fps = float(num) / float(den)
    n = q("stream=nb_frames")[0]
    if not n or n == "N/A":
        r = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                            "-select_streams", "v:0", "-show_entries",
                            "stream=nb_read_frames", "-of", "csv=p=0", path],
                           capture_output=True, text=True)
        n = r.stdout.strip()
    return int(n), dur, fps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", help="a video folder, e.g. .../videos/01-first-time-ordering")
    ap.add_argument("--version", "-v", type=int, required=True, help="which build to release")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="replace a release already at this version number")
    a = ap.parse_args()

    F = os.path.abspath(a.folder)
    vdir = os.path.join(F, "video")
    if not os.path.isdir(vdir):
        sys.exit(f"  no video/ under {F}")

    rx = re.compile(rf"^(.+)_v{a.version}\.mp4$")
    builds = sorted(f for f in os.listdir(vdir) if rx.match(f))
    if not builds:
        have = sorted({int(re.findall(r"_v(\d+)\.mp4$", f)[0])
                       for f in os.listdir(vdir) if re.search(r"_v\d+\.mp4$", f)})
        sys.exit(f"  no build at v{a.version} in {vdir}\n"
                 f"  versions there: {', '.join(map(str, have)) or 'none'}")
    if len(builds) > 1:
        sys.exit(f"  {len(builds)} files claim v{a.version}: {', '.join(builds)}")
    name = builds[0]
    src = os.path.join(vdir, name)
    title = rx.match(name).group(1)

    frames, dur, fps = probe(src)
    expect = frames / fps
    drift = dur - expect
    print(f"\n  {name}")
    print(f"    {frames} frames at {fps:g}fps = {expect:.2f}s;  container says {dur:.2f}s"
          f"  ({drift:+.3f}s)")
    if abs(drift) > 0.10:
        sys.exit(f"\n  REFUSED — the clock and the frame count disagree by {drift:+.3f}s.\n"
                 f"  A build like this plays, and is wrong. Fix it before releasing.\n")
    print("    clock agrees with the frame count ✓")

    business, store = store_path_of(F)
    hv = os.path.join(basic_root(), "Customers", business, store, "help-videos")
    if not os.path.isdir(hv):
        sys.exit(f"  no help-videos/ for {store} at {hv}")
    # One folder per video, named exactly as the video folder is named here.
    slug = os.path.basename(F.rstrip(os.sep))
    dst_dir = os.path.join(hv, slug)
    dst = os.path.join(dst_dir, name)

    # The words that made this build. Not optional: --join writes one every
    # time, so its absence means this mp4 did not come from a join.
    script_src = os.path.join(vdir, f"script_v{a.version}.json")
    if not os.path.isfile(script_src):
        sys.exit(f"\n  REFUSED — no script_v{a.version}.json beside the build.\n"
                 f"  --join writes one on every join, so this mp4 did not come from one.\n"
                 f"  A video whose words are unknown is not releasable.\n")
    # The timing table, if it has been generated. build/vtt_html.py makes it.
    vtt_src = os.path.join(vdir, "vtt.html")
    extras = [script_src] + ([vtt_src] if os.path.isfile(vtt_src) else [])

    # Anything already there for this same title, at any other version.
    older = ([f for f in sorted(os.listdir(dst_dir))
              if f.startswith(title + "_v") and f.endswith(".mp4") and f != name]
             if os.path.isdir(dst_dir) else [])

    print(f"\n    -> Customers/{business}/{store}/help-videos/{slug}/")
    print(f"         {name}")
    for x in extras:
        print(f"         {os.path.basename(x)}")
    if vtt_src not in extras:
        print("         (no vtt.html — run build/vtt_html.py to include one)")
    for o in older:
        print(f"       standing down: {o}  -> z_History/")
    if os.path.exists(dst) and not a.force:
        import filecmp
        if filecmp.cmp(src, dst, shallow=False):
            print("\n    already released, identical bytes — nothing to do.\n")
            return 0
        sys.exit(f"\n  REFUSED — v{a.version} is already released with DIFFERENT bytes.\n"
                 f"  Two files under one version number cannot be told apart later.\n"
                 f"  Bump the version, or pass --force if you truly mean to replace it.\n")

    if a.dry_run:
        print("\n    --dry-run: nothing written.\n")
        return 0

    os.makedirs(dst_dir, exist_ok=True)
    if older:
        hist = os.path.join(dst_dir, "z_History")
        os.makedirs(hist, exist_ok=True)
        for o in older:
            shutil.move(os.path.join(dst_dir, o), os.path.join(hist, o))

    def put(a_src, a_dst):
        # cp -c clones on APFS: no disk, no wait. Falls back to a plain copy.
        if subprocess.run(["cp", "-c", a_src, a_dst], capture_output=True).returncode != 0:
            shutil.copy2(a_src, a_dst)
        if os.path.getsize(a_src) != os.path.getsize(a_dst):
            sys.exit(f"  {os.path.basename(a_dst)} came out a different size — "
                     f"left it in place, check by hand")

    put(src, dst)
    for x in extras:
        put(x, os.path.join(dst_dir, os.path.basename(x)))
    print(f"\n    released, {os.path.getsize(dst) / 1e6:.1f} MB "
          f"+ {len(extras)} file(s) beside it\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
