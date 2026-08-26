#!/usr/bin/env python3
"""
Copy the ski-demo data the editors run against into this repo.

    python3 setup_demo.py            # copy what is missing
    python3 setup_demo.py --force    # throw it away and copy it again
    python3 setup_demo.py --check    # say what is there, copy nothing

WHY THIS EXISTS INSTEAD OF COMMITTING THE VIDEO
    dev/ and sandbox/ are the folders the editors WRITE to. Running the tools
    changes 106MB of files. Git keeps every version of every file forever and
    cannot pack video down, so every commit of a working state would add its
    full size again — and taking it back out later means rewriting history.

    Both repos are on the same machine, so the data is a copy away. The repo
    stays a few hundred KB of code, clones instantly, needs no LFS and no
    quota, and nobody can accidentally commit a chewed-up sandbox.

    The cost, stated plainly: this repo is not self-contained. On a machine
    that has never had Basic_E2E_Testing, run it against a copy of that store
    with --from, or bring the data by hand.

WHAT IT COPIES — about 150MB of ski-demo's 2.2GB
    dev/                  12 scenes, the segments a cut lands on
    sandbox/              14 folders, the editor's whole scope, bookends and all
    video/script.json     the scene list, the lines, the words-per-second
    one raw recording     the smallest, so the splitter has something to cut

WHAT IT LEAVES BEHIND
    nine more raw recordings (1.5GB), fourteen finished builds, every archive,
    and onepass/. None of it is an input to either editor.
"""
import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Where the data comes from. Overridable, because a path that only works on one
# machine should say so out loud rather than fail three functions deep.
DEFAULT_SOURCE = os.path.expanduser("~/Rentify/Basic_E2E_Testing")

STORE = os.path.join("Customers", "Rentify Demos Corp", "ski-demo", "help-videos")
VIDEO = os.path.join(STORE, "videos", "01-first-time-ordering")
RAW = "ski-demo_owner-one-item_dev_19-17-45_v5.mp4"      # the smallest, 48MB

# Copied whole, minus the archives. Each entry is (relative path, what to skip).
TREES = [
    (os.path.join(VIDEO, "dev"), ("z_History", "_cuts")),
    (os.path.join(VIDEO, "sandbox"), ("z_History", "_cuts")),
]
FILES = [
    os.path.join(VIDEO, "video", "script.json"),
    os.path.join(STORE, "raw_mp4", RAW),
]


def mb(n):
    return f"{n / 1048576:.0f} MB"


def measure(path):
    """(files, bytes) under `path`, or (0, 0) if it is not there."""
    if os.path.isfile(path):
        return 1, os.path.getsize(path)
    n = t = 0
    for root, _, files in os.walk(path):
        for f in files:
            n += 1
            t += os.path.getsize(os.path.join(root, f))
    return n, t


def copy_tree(src, dst, skip):
    """Copy `src` to `dst`, leaving out any directory named in `skip`.

    Written out rather than using copytree's ignore= so the skip is by DIRECTORY
    NAME at any depth: the archives sit one level down in dev/ and two levels
    down in sandbox/, and a pattern that only caught one of those would quietly
    bring 20MB of history along.
    """
    n = t = 0
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in skip]
        rel = os.path.relpath(root, src)
        out = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(out, exist_ok=True)
        for f in files:
            # Dotfiles are left behind on purpose. The only ones here are
            # .gitkeep, which exist so git tracks those folders in the OTHER
            # repo; Customers/ is ignored here, so they would mean nothing.
            if f.startswith("."):
                continue
            s = os.path.join(root, f)
            shutil.copy2(s, os.path.join(out, f))
            n += 1
            t += os.path.getsize(s)
    return n, t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="source", default=DEFAULT_SOURCE,
                    help=f"the repo to copy from (default {DEFAULT_SOURCE})")
    ap.add_argument("--force", action="store_true",
                    help="delete what is here and copy it again")
    ap.add_argument("--check", action="store_true",
                    help="report what is present and copy nothing")
    a = ap.parse_args()

    print("\n  ski-demo demo data\n")

    if a.check:
        total_n = total_t = 0
        for rel, _ in TREES:
            n, t = measure(os.path.join(HERE, rel))
            total_n += n; total_t += t
            print(f"    {'✓' if n else '✗'} {rel:52s} {n:3d} files  {mb(t)}")
        for rel in FILES:
            n, t = measure(os.path.join(HERE, rel))
            total_n += n; total_t += t
            print(f"    {'✓' if n else '✗'} {rel:52s} {n:3d} files  {mb(t)}")
        print(f"\n    {total_n} files, {mb(total_t)}")
        print("\n    nothing copied — this was --check\n")
        return 0

    src_root = os.path.abspath(os.path.expanduser(a.source))
    if not os.path.isdir(os.path.join(src_root, STORE)):
        sys.exit(f"  no ski-demo store under {src_root}\n"
                 f"  looked for: {STORE}\n"
                 f"  pass --from <path> if that repo lives somewhere else\n")

    total_n = total_t = 0
    for rel, skip in TREES:
        s, d = os.path.join(src_root, rel), os.path.join(HERE, rel)
        if os.path.isdir(d):
            if not a.force:
                n, t = measure(d)
                print(f"    · {rel:52s} already here ({n} files) — --force to refresh")
                total_n += n; total_t += t
                continue
            shutil.rmtree(d)
        if not os.path.isdir(s):
            sys.exit(f"  missing in the source repo: {rel}")
        n, t = copy_tree(s, d, skip)
        print(f"    + {rel:52s} {n:3d} files  {mb(t)}")
        total_n += n; total_t += t

    for rel in FILES:
        s, d = os.path.join(src_root, rel), os.path.join(HERE, rel)
        if os.path.isfile(d) and not a.force:
            n, t = measure(d)
            print(f"    · {rel:52s} already here — --force to refresh")
            total_n += n; total_t += t
            continue
        if not os.path.isfile(s):
            sys.exit(f"  missing in the source repo: {rel}")
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(s, d)
        n, t = measure(d)
        print(f"    + {rel:52s} {n:3d} files  {mb(t)}")
        total_n += n; total_t += t

    print(f"\n    {total_n} files, {mb(total_t)}")
    print(f"    under {os.path.join(HERE, 'Customers')} — gitignored\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
