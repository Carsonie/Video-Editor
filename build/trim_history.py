#!/usr/bin/env python3
"""
Keep a z_History useful and finite.

    python3 build/trim_history.py "<any folder>"            # shows, deletes nothing
    python3 build/trim_history.py "<any folder>" --apply
    python3 build/trim_history.py "<any folder>" --keep 5

WHY THIS EXISTS
    None of this is in git — video cannot be packed, so `Customers/` is
    ignored wholesale and z_History IS the undo. That makes it grow without
    limit and with nothing to notice. On 2026-08-28 ski-demo's one video held
    1.3 GB of history against an 80 MB sandbox, and 23 more videos are coming.

TWO RULES, AND THE FIRST IS THE BIG ONE

  1. A BACKUP DOES NOT KEEP BACKUPS.
     Every z_History nested inside another z_History is deleted outright, at
     any depth. This is not a judgement call: the snapshot already froze that
     moment, so the per-scene history it swept up with it can never be reached
     by anything. It was 514 MB of the 1.3 GB — more than a third of the
     history was history-of-history.

  2. KEEP THE 3 NEWEST OF ANYTHING, EVERYWHERE.
     A z_History holds two different kinds of child and they must not be
     ranked against each other:

       a BUCKET    a folder collecting dated snapshots of ONE thing —
                   segments/, scenes/, sarah_clips/, line-edits/
       a SNAPSHOT  one dated capture sitting directly in the z_History

     Trimming the mixed list would have kept three arbitrary buckets and
     deleted the rest of the KINDS. So each bucket is trimmed inside itself,
     and the loose snapshots are trimmed among themselves.

ORDER MATTERS: age comes from the DATE IN THE NAME, not the modification time.
    A bulk copy re-stamps every mtime to the same minute — here, eight
    distinct milestones all read as `08-26 12:00`, so mtime could not order
    them at all. The name is the honest record. mtime is the fallback for a
    name that carries no date.

ANYTHING NAMED `-broken` GOES FIRST, whatever its age. It is being kept only
because it was recent, and recency is the one thing that cannot make a known
bad snapshot worth a slot.
"""
import argparse
import os
import re
import shutil
import sys

# The shapes a dated snapshot is named with here. Ordered longest-first so a
# more specific pattern wins: `2026-08-27-v_4` must not be read as `2026-08-27`
# alone, or four versions of one day collapse into one sort key.
STAMPS = [
    re.compile(r"(\d{4})-(\d{2})-(\d{2})[-_]v_?(\d+)"),        # 2026-08-27-v_4
    re.compile(r"(\d{4})(\d{2})(\d{2})-(\d{6})"),              # 20260827-223904
    re.compile(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})"),  # 2026-08-20_11-02-16
    re.compile(r"(\d{2})-(\d{1,2})-(\d{1,2})_v(\d+)"),         # 26-8-27_v4   (Add-V)
    re.compile(r"(\d{4})-(\d{2})-(\d{2})"),                    # 2026-08-19_pre-25fps
    re.compile(r"(\d{4})(\d{2})(\d{2})"),                      # 20260828_pre-...  (no time)
]


def sort_key(path, name):
    """
    (has-a-date, the date, mtime) — newest first when reversed.

    A name with a date always outranks one without, because a dateless name is
    a hand-written label and those are the ones worth keeping longest anyway.
    """
    for rx in STAMPS:
        m = rx.search(name)
        if m:
            # Zero-pad each captured group so string order is date order:
            # `26-8-27_v4` and `26-8-27_v10` must not compare as text.
            return (1, tuple(int(g) for g in m.groups()), 0.0)
    try:
        return (0, (), os.path.getmtime(path))
    except OSError:
        return (0, (), 0.0)


def looks_dated(name):
    return any(rx.search(name) for rx in STAMPS)


def is_bucket(path):
    """
    A folder that COLLECTS dated snapshots, rather than being one.

    Judged by its children: two or more, and most of them dated. A bucket is
    trimmed inside itself; it is never a candidate for deletion.
    """
    if not os.path.isdir(path):
        return False
    kids = [k for k in os.listdir(path) if not k.startswith(".")]
    return len(kids) >= 2 and sum(looks_dated(k) for k in kids) > len(kids) / 2


def size(p):
    if os.path.isfile(p):
        try:
            return os.path.getsize(p)
        except OSError:
            return 0
    t = 0
    for d, _, fs in os.walk(p):
        for f in fs:
            try:
                t += os.path.getsize(os.path.join(d, f))
            except OSError:
                pass
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".", help="anything above the z_History folders")
    ap.add_argument("--keep", type=int, default=3)
    ap.add_argument("--apply", action="store_true", help="actually delete")
    a = ap.parse_args()
    ROOT = os.path.abspath(a.root)
    if not os.path.isdir(ROOT):
        sys.exit(f"  no such folder: {ROOT}")

    hists = [d for d, _, _ in os.walk(ROOT) if os.path.basename(d) == "z_History"]
    nested = sorted(h for h in hists if h.count(os.sep + "z_History") > 1)
    top = sorted(h for h in hists if h.count(os.sep + "z_History") == 1)

    print(f"\n  {os.path.relpath(ROOT, os.path.dirname(ROOT))}"
          f"   —  keep {a.keep}   {'APPLYING' if a.apply else 'dry run'}\n")

    freed = 0
    print(f"  1. history inside history — {len(nested)} folders")
    for h in nested:
        freed += size(h)
        if a.apply and os.path.isdir(h):
            shutil.rmtree(h)
    print(f"     {freed / 1e6:.1f} MB\n")

    print(f"  2. keep the {a.keep} newest, per bucket and per level\n")
    freed_b = 0

    def trim(folder, indent):
        nonlocal freed_b
        if not os.path.isdir(folder):
            return
        kids = [k for k in os.listdir(folder) if not k.startswith(".")]
        buckets = [k for k in kids if is_bucket(os.path.join(folder, k))]
        snaps = [k for k in kids if k not in buckets]

        # A snapshot the name itself calls bad loses its slot first.
        bad = [s for s in snaps if re.search(r"broken|bad|FAILED", s, re.I)]
        snaps = [s for s in snaps if s not in bad]
        ranked = sorted(snaps, key=lambda k: sort_key(os.path.join(folder, k), k),
                        reverse=True)
        drop = bad + ranked[a.keep:]
        for k in ranked[:a.keep]:
            print(f"{indent}   keep  {k}")
        for k in drop:
            p = os.path.join(folder, k)
            s = size(p)
            freed_b += s
            why = "  (named broken)" if k in bad else ""
            print(f"{indent}   DROP  {k}   ({s / 1e6:.1f} MB){why}")
            if a.apply:
                shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
        for b in sorted(buckets):
            print(f"{indent}   {b}/")
            trim(os.path.join(folder, b), indent + "    ")

    for h in top:
        if not os.path.isdir(h):
            continue
        print(f"     {os.path.relpath(h, ROOT)}")
        trim(h, "     ")
        print()
    print(f"     {freed_b / 1e6:.1f} MB\n")
    print(f"  TOTAL {'freed' if a.apply else 'that would go'}: {(freed + freed_b) / 1e6:.0f} MB")
    if not a.apply:
        print("  nothing was deleted — pass --apply\n")
    else:
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
