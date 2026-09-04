#!/usr/bin/env python3
"""
Build the disposable store the editor test runs against.

WHY A FIXTURE AND NOT A REAL STORE
    Every function worth testing WRITES: save overwrites a segment, cut replaces
    it, join deletes the folders it consumed, split deletes the scene it cut in
    two. Pointed at ski-demo those are real edits to a finished video, and the
    z_History archive only makes them recoverable, not harmless. So the test
    builds its own store, uses it up, and deletes it.

WHY IT LIVES UNDER Customers/
    Not a choice. serve.py's safe_join() resolves every path under
    CUSTOMERS_ROOT and returns None for anything outside it, so a fixture
    anywhere else is unreachable by the very endpoints under test. It sits at
    Customers/_Editor_Test/ — the leading underscore keeps it out of the way of
    the real businesses, alongside the other non-business folders already there
    (BCP, Master Yamls).

WHY REAL FOOTAGE
    The clips are cut from ski-demo's scene 1. A synthetic clip from
    testsrc would be faster to make and would not exercise the thing that
    actually bites: real avatar tracks are VP9 with alpha, and plain ffprobe
    reports those as yuv420p unless the decoder is forced. A green test on a
    synthetic file would prove nothing about the files this tool is for.

    Deliberately SHORT — 40/30/25 frames, not the 200+ a real scene runs. The
    test re-encodes these files dozens of times, and every frame is paid for on
    each pass.

    The three tracks are deliberately DIFFERENT lengths, because that is the
    normal state of a real scene and the state that has produced bugs: a
    segment longer than its avatar is what "Update Frame Imbalance" exists for,
    and a split point valid in one track but past the end of another is what
    the split's pre-flight check refuses.
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# One level up: tests/ sits at the repo root here. It was five in
# Basic_E2E_Testing, where this lived at
# .claude/agent-tools/6_.../video_players/tests/ — a count that is wrong the
# moment the tree changes, which is what just happened.
REPO = os.path.abspath(os.path.join(HERE, ".."))
CUSTOMERS = os.path.join(REPO, "Customers")
STORE = os.path.join(CUSTOMERS, "_Editor_Test")
ROOT_REL = "_Editor_Test"                      # what the API is given

SRC = os.path.join(CUSTOMERS, "Rentify Demos Corp", "ski-demo", "help-videos",
                   "videos", "01-first-time-ordering", "dev", "01-login-and-code")
SRC_SEG = os.path.join(SRC, "segment-v6.mp4")
SRC_AV = os.path.join(SRC, "avatar-v1.webm")
SRC_NAR = os.path.join(SRC, "narration-v1.webm")

ENCODE = ["-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
ENCODE_ALPHA = ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0",
                "-b:v", "1M"]

# scene n -> (label, segment frames, avatar frames, narration frames, line)
SCENES = [
    (1, "alpha-scene", 40, 30, 35, "The first line of the test store."),
    (2, "bravo-scene", 32, 32, 28, "A second line, deliberately shorter."),
    (3, "charlie-scene", 25, 18, 22, "The third and last line here."),
]


def frames(path, alpha=False):
    """Count DECODED frames. VP9 has no frame count in its container, and an
    alpha WebM must have its decoder forced or ffprobe reports yuv420p and
    silently hands back the wrong stream."""
    dec = ["-c:v", "libvpx-vp9"] if alpha else []
    r = subprocess.run(["ffprobe", "-v", "error"] + dec + ["-select_streams", "v",
                        "-count_frames", "-show_entries", "stream=nb_read_frames",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    out = r.stdout.strip()
    return int(out) if out.isdigit() else None


def probe_pix_fmt(path):
    """The pixel format, with the decoder FORCED. Plain ffprobe reports an alpha
    WebM as yuv420p and hands back the wrong answer — which is exactly what the
    alpha test exists to catch."""
    r = subprocess.run(["ffprobe", "-v", "error", "-c:v", "libvpx-vp9",
                        "-i", path, "-select_streams", "v",
                        "-show_entries", "stream=pix_fmt", "-of", "csv=p=0"],
                       capture_output=True, text=True)
    return r.stdout.strip()


def cut(src, dst, n, alpha):
    """First `n` frames of `src`. -frames:v, never -t: a duration cutoff drops
    the frame that lands on the boundary, which is the bug that made Save write
    87 frames for an 89-frame edit."""
    dec = ["-c:v", "libvpx-vp9"] if alpha else []
    enc = ENCODE_ALPHA if alpha else ENCODE
    r = subprocess.run(["ffmpeg", "-v", "error"] + dec + ["-i", src, "-an",
                        "-frames:v", str(n), "-fps_mode", "passthrough"] + enc
                       + ["-y", dst], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"fixture: could not cut {os.path.basename(dst)}: {r.stderr[-300:]}")


def build(quiet=False):
    """Make the store from scratch. Any previous one is removed first — a test
    that inherits the last run's leftovers is not a test."""
    for p in (SRC_SEG, SRC_AV, SRC_NAR):
        if not os.path.isfile(p):
            sys.exit(f"fixture: source clip missing: {p}")
    shutil.rmtree(STORE, ignore_errors=True)
    os.makedirs(os.path.join(STORE, "sandbox"))
    say = (lambda m: None) if quiet else (lambda m: print(m))

    doc = {"store": "_editor_test", "title": "Editor Test", "words_per_second": 3.44,
           "scenes": [{"n": n, "label": lab, "line": line}
                      for n, lab, _, _, _, line in SCENES]}
    for n, label, ns, na, nn, _ in SCENES:
        d = os.path.join(STORE, "sandbox", f"{n:02d}-{label}")
        os.makedirs(d)
        cut(SRC_SEG, os.path.join(d, "segment.mp4"), ns, False)
        cut(SRC_AV, os.path.join(d, "avatar.webm"), na, True)
        cut(SRC_NAR, os.path.join(d, "narration.webm"), nn, True)
        say(f"    {n:02d}-{label}: segment={ns} avatar={na} narration={nn}")
    # sandbox/script.json 2026-08-29 — was video/script.json; see paths.script().
    with open(os.path.join(STORE, "sandbox", "script.json"), "w") as fh:
        json.dump(doc, fh, indent=2)
    return STORE


def expected():
    """What build() just wrote, for the test to assert against."""
    return {n: {"label": lab, "segment": ns, "avatar": na, "narration": nn,
                "line": line}
            for n, lab, ns, na, nn, line in SCENES}


def destroy():
    shutil.rmtree(STORE, ignore_errors=True)


def dead_handlers(serve_py_path):
    """
    Handler methods that no dispatcher can reach, transitively.

    A route can be deleted from do_GET/do_POST while its handler body
    stays behind. Every suite's own "this route is gone" check asserts a
    404 — and a 404 is exactly what an unreachable handler produces — so
    those checks pass either way. This is the only thing that can see
    the body is still there. That is not hypothetical: the 2026-09-02
    split left 15 such handlers in mp4_splitter (930 lines, 36% of its
    serve.py) and 4 in segment_avatar_editor, all of them invisible to
    a green test run for a year.

    REACHABILITY, NOT "IS IT CALLED ANYWHERE". Those differ, and the
    difference hides code: mp4_splitter's api_open_pair and api_open_seq
    ARE called — but only from api_open_pair_go and api_open_seq_go,
    which are themselves dead. A call-site diff counts them live and
    misses 171 lines. So this walks OUT from do_GET/do_POST following
    self.<name>() calls, and whatever is never arrived at is dead —
    including a whole chain of dead handlers calling each other.

    The candidate set is one rule for all four editors, no per-editor
    prefix lists: everything on the Handler class except framework and
    base-class plumbing (do_*, _*, send_*, end_*, translate_*, log_*,
    address_*). mp4_splitter/SAE name their handlers api_*; avatar_editor
    and frame_blender use plain names. One rule covers both.

    AST only. Never imports or runs the server — a test that had to boot
    four servers to find dead code would be too slow to keep.

    Returns a sorted list of names, so `eq(..., [], ...)` reads as the
    assertion and a failure prints exactly what to delete.
    """
    import ast
    tree = ast.parse(open(serve_py_path).read())
    handler = next((n for n in ast.walk(tree)
                    if isinstance(n, ast.ClassDef) and n.name == "Handler"), None)
    if handler is None:                      # no Handler class — nothing to judge
        return []

    methods = {m.name: m for m in handler.body if isinstance(m, ast.FunctionDef)}

    # name -> the set of sibling methods it calls as self.<name>(...)
    calls = {
        name: {c.func.attr for c in ast.walk(node)
               if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
               and isinstance(c.func.value, ast.Name) and c.func.value.id == "self"}
        for name, node in methods.items()
    }

    # walk out from the dispatchers until the reachable set stops growing
    reachable, stack = set(), [f for f in ("do_GET", "do_POST") if f in methods]
    while stack:
        fn = stack.pop()
        if fn in reachable:
            continue
        reachable.add(fn)
        stack.extend(c for c in calls.get(fn, ()) if c in methods and c not in reachable)

    PLUMBING = ("do_", "_", "send_", "end_", "translate_", "log_", "address_")
    candidates = {n for n in methods if not n.startswith(PLUMBING)}
    return sorted(candidates - reachable)


def write_report(editor, log_lines, results, steps):
    """
    Write one run's output to tests/<editor>/ — a .log (the full printed
    transcript, same text the terminal showed) and a .txt (a short,
    structured pass/fail report), same base filename, `.log`/`.txt` the
    only difference. One per editor (Carson's own split, 2026-09-03,
    alongside each of the four now having its own standalone process,
    cache and session log) — so a run's output can never land in, or be
    confused with, another editor's.

    `steps` is the (number, title, [result-indexes]) list `step()`/`check()`
    build as a run goes; a step's own state is PASS only if every check
    inside it passed. `results` is the flat (name, ok, detail) list
    `check()`/`eq()` append to.

    Shared here rather than copied into each of the four test files: the
    shape is identical for all of them, and a change to what the report
    looks like should not mean editing it four times.
    """
    import time
    stamp = time.strftime("%H_%M_%S")
    out_dir = os.path.join(HERE, editor)
    os.makedirs(out_dir, exist_ok=True)
    base = f"{editor}_{stamp}"

    with open(os.path.join(out_dir, base + ".log"), "w") as fh:
        fh.write("\n".join(log_lines) + "\n")

    passed = sum(1 for _, ok, _ in results if ok)
    failed = [(name, detail) for name, ok, detail in results if not ok]

    lines = [
        f"{editor} Test Report",
        f"Run:         {time.strftime('%Y-%m-%dT%H:%M:%S')}",
        f"Log:         {base}.log",
        "",
        f"Tests run:   {len(results)}",
        f"Passed:      {passed}",
        f"Failed:      {len(failed)}",
        f"Result:      {'PASS' if not failed else 'FAIL'}",
        "",
        "Steps:",
    ]
    for num, title, idxs in steps:
        ok = all(results[i][1] for i in idxs) if idxs else True
        lines.append(f"  {'PASS' if ok else 'FAIL'}  Step {num}: {title}")

    if failed:
        lines.append("")
        lines.append("Failures:")
        for name, detail in failed:
            lines.append(f"  - {name}" + (f"   {detail}" if detail else ""))

    with open(os.path.join(out_dir, base + ".txt"), "w") as fh:
        fh.write("\n".join(lines) + "\n")

    return base


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "destroy":
        destroy()
        print(f"  removed {STORE}")
    else:
        print("  building the editor test store")
        build()
        print(f"  at {STORE}")
