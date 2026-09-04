#!/usr/bin/env python3
"""
editor_base's own suite — the one package all five servers import from.

    python3 tests/test_editor_base.py

WHY THIS EXISTS
    Everything else in tests/ boots a server and drives it over HTTP. This
    one does not, because editor_base has no server in it: it is the pure
    layer underneath all of them (frame extraction, path shapes, the
    ffmpeg encode recipe). Testing it through an editor would only prove
    that one editor's use of it works.

    It also exists because of the rule that came with Carson's Option A
    (2026-09-03): a change here is not "one editor's change" — it can
    break four tools at once. That is the trade the shared package makes,
    and this file plus the other four suites is what makes the trade
    survivable.

WHAT IT ASSERTS
    Three things, and deliberately not more:

    1. THE PACKAGE IS ACTUALLY PURE. No routes, no Handler, no `self`,
       nothing that knows about HTTP. This is the constraint that keeps
       editor_base from quietly re-becoming the old combined server —
       which is exactly what shared/serve.py grew into.

    2. THE ONE PIECE OF STATE BEHAVES. frames.CACHE is process-level
       configuration, and use_cache() has to actually reach every function
       that reads it. If it did not, an editor would silently extract into
       the wrong tool's cache.

    3. THE PURE FUNCTIONS GIVE THE RIGHT ANSWERS on real files — real
       VP9-with-alpha, because plain ffprobe reports those as yuv420p
       unless the decoder is forced, and that is the trap a synthetic clip
       would hide.
"""
import ast
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import fixture  # noqa: E402
from editor_base import frames as eb_frames  # noqa: E402
from editor_base import paths as eb_paths    # noqa: E402

REPO = os.path.dirname(HERE)
BASE_DIR = os.path.join(REPO, "editor_base")

RESULTS = []
LOG = []
STEPS = []


def out(line=""):
    print(line)
    LOG.append(line)


def step(title):
    STEPS.append([len(STEPS) + 1, title, []])
    out(f"\n  Step {len(STEPS)}: {title}")


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    if STEPS:
        STEPS[-1][2].append(len(RESULTS) - 1)
    out(f"     {'✓' if ok else '✗'} {name}" + (f"   {detail}" if detail else ""))
    return bool(ok)


def eq(name, got, want, extra=""):
    return check(name, got == want,
                 f"got {got}, want {want}" if got != want else (extra or str(got)))


def s_purity():
    """
    The constraint that keeps this package from becoming a second server.
    shared/serve.py is the cautionary tale: it started as helpers and grew
    routes until four tools could not be untangled from it.
    """
    step("editor_base is pure — no routes, no handlers, no HTTP")
    for name in sorted(os.listdir(BASE_DIR)):
        if not name.endswith(".py"):
            continue
        src = open(os.path.join(BASE_DIR, name)).read()
        tree = ast.parse(src)

        classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        check(f"{name} defines no classes", not classes, classes or "none")

        selfish = [n.name for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef)
                   and n.args.args and n.args.args[0].arg == "self"]
        check(f"{name} has no method taking self", not selfish, selfish or "none")

        # http.server / socketserver here would mean a route crept in.
        imported = {a.name.split(".")[0] for n in ast.walk(tree)
                    if isinstance(n, ast.Import) for a in n.names}
        imported |= {(n.module or "").split(".")[0] for n in ast.walk(tree)
                     if isinstance(n, ast.ImportFrom)}
        forbidden = imported & {"http", "socketserver", "urllib"}
        check(f"{name} imports nothing HTTP", not forbidden, forbidden or "none")

        check(f"{name} defines no do_GET/do_POST",
              not [n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name.startswith("do_")])


def s_cache_is_configurable():
    """
    frames.CACHE is the one line that used to justify three copies of a
    776-line file. Now that it is configuration, use_cache() has to
    actually work — if it did not reach the functions, an editor would
    extract into another tool's cache and nothing would say so.
    """
    step("frames.CACHE — the one piece of state, and it is reachable")
    original = eb_frames.CACHE
    try:
        eq("there is a default", os.path.basename(original), "cache")

        probe = os.path.join(REPO, "cache_test_editor_base_probe")
        eq("use_cache returns what it set", eb_frames.use_cache(probe), probe)
        eq("...and the module now reads it", eb_frames.CACHE, probe)

        # Read at CALL time, not captured at import — the thing that would
        # silently break this.
        src = open(os.path.join(BASE_DIR, "frames.py")).read()
        check("no function captures CACHE as a default argument",
              "=CACHE" not in src and "= CACHE)" not in src)
        readers = [n.name for n in ast.walk(ast.parse(src))
                   if isinstance(n, ast.FunctionDef)
                   and any(isinstance(x, ast.Name) and x.id == "CACHE"
                           for x in ast.walk(n))]
        check("more than one function reads it, and all at call time",
              len(readers) > 1, ", ".join(sorted(readers)))
    finally:
        eb_frames.use_cache(original)
    eq("restored", eb_frames.CACHE, original)


def s_pure_functions_on_real_files():
    """
    The answers themselves, on the fixture's real clips. An alpha WebM is
    the case that matters: ffprobe calls it yuv420p unless the decoder is
    forced, so a synthetic file would prove nothing.
    """
    step("the pure functions, against real footage")
    fixture.build(quiet=True)
    try:
        seg = os.path.join(fixture.STORE, "sandbox", "01-alpha-scene", "segment.mp4")
        av = os.path.join(fixture.STORE, "sandbox", "01-alpha-scene", "avatar.webm")
        check("the fixture really built", os.path.isfile(seg) and os.path.isfile(av))

        # THE TRAP this package exists to get right: VP9 has no frame count
        # in its container, and an alpha WebM reports yuv420p unless the
        # decoder is forced with -c:v libvpx-vp9. Every editor's frame
        # maths rests on decoded_frames() getting this right; a wrong count
        # is the 87-vs-89 class of bug — a playable file that is wrong.
        VP9 = ["-c:v", "libvpx-vp9"]
        n_seg = eb_frames.decoded_frames(seg)
        n_av = eb_frames.decoded_frames(av, dec=VP9)
        eq("the mp4's decoded frame count", n_seg, fixture.frames(seg))
        eq("the alpha webm's decoded frame count", n_av,
           fixture.frames(av, alpha=True))
        check("both are real counts, not zero or None",
              bool(n_seg) and bool(n_av), (n_seg, n_av))

        # probe() is what every duration decision is made from. It adds the
        # "format="/"stream=" prefix itself and hands back a bare string.
        dur = eb_frames.probe(seg, "duration")
        check("probe returns a real duration", dur and float(dur) > 0, dur)

        # slug_for must be stable and unique per absolute path — the cache
        # depends on it, and two clips sharing a slug would share frames.
        s1, s2 = eb_frames.slug_for(seg), eb_frames.slug_for(av)
        check("slug is stable", s1 == eb_frames.slug_for(seg), s1)
        check("two different files never share a slug", s1 != s2)
        check("slug is URL-safe",
              all(c.isalnum() or c in "._-" for c in s1), s1)
    finally:
        fixture.destroy()


def s_paths_shapes():
    """paths.py is the shape of a store on disk — the regexes every tool
    reads filenames with. Byte-identical in three places before this."""
    step("paths — the filename shapes every editor agrees on")
    check("segment names", eb_paths.SEG_RE.match("Num_3-v6-segment.mp4") is not None)
    check("dev segment names", eb_paths.DEV_SEG_RE.match("segment-v6.mp4") is not None)
    check("dev avatar names", eb_paths.DEV_AV_RE.match("avatar-v1.webm") is not None)
    check("a nonsense name matches nothing",
          eb_paths.SEG_RE.match("segment.mp4") is None)
    eq("the archive folder is named once, here", eb_paths.ARCHIVE_DIR, "z_History")


def s_no_duplicate_copies_left():
    """
    The point of the package. If a copy comes back, the duplication comes
    back with it — so this fails if a real one reappears beside an editor.

    shared/ is the one deliberate exception, and it is a SHIM, not a copy.
    Nine scripts in build/ do `import paths as PTH`, resolved by having
    shared/ on sys.path, and one of them — build/assemble_video.py — is
    someone else's uncommitted work that must not be edited. So shared/
    keeps three files under the old names that do nothing but re-export
    editor_base. A shim is ~25 lines; a copy is 465 to 776. The size gap
    is wide enough that this check can simply measure it.
    """
    step("no editor keeps its own copy of what this package owns")
    OWNED = ("paths.py", "frames.py", "vtt.py")
    SHIM_MAX = 60          # the real modules are 465, 776 and 300+ lines

    for pkg in ("mp4_splitter", "segment_avatar_editor",
                "avatar_editor", "frame_blender"):
        for mod in OWNED:
            p = os.path.join(REPO, pkg, mod)
            check(f"{pkg}/{mod} is gone", not os.path.isfile(p),
                  "still there" if os.path.isfile(p) else "")

    for mod in OWNED:
        p = os.path.join(REPO, "shared", mod)
        if not os.path.isfile(p):
            check(f"shared/{mod} is gone", True)
            continue
        src = open(p).read()
        n = len(src.splitlines())
        check(f"shared/{mod} is a shim, not a copy", n <= SHIM_MAX, f"{n} lines")
        check(f"shared/{mod} says so in its docstring", "SHIM" in src)
        check(f"shared/{mod} re-exports from editor_base",
              "editor_base" in src)

    # A shim is only worth keeping if it still resolves for the callers it
    # exists for — build/ puts shared/ on sys.path but NOT the repo root,
    # which is the failure this bootstraps around.
    import subprocess
    r = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, 'shared');"
         "import paths, frames, vtt; print(paths.ARCHIVE_DIR, vtt.words('a b c'))"],
        cwd=REPO, capture_output=True, text=True)
    check("the shims still resolve the way build/ imports them",
          r.returncode == 0, (r.stdout or r.stderr).strip().splitlines()[-1:] or "")


FUNCTIONS = [s_purity, s_cache_is_configurable, s_pure_functions_on_real_files,
             s_paths_shapes, s_no_duplicate_copies_left]


def main():
    started = time.time()
    out(f"editor_base Test:  {time.strftime('%Y-%m-%dT%H:%M:%S')}")
    out(f"Package:           {BASE_DIR}")

    for fn in FUNCTIONS:
        fn()

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    out(f"\n  Checks:  {passed}/{len(RESULTS)} passed")
    out(f"  Elapsed: {time.time() - started:.0f}s")
    out(f"  Result:  {'PASS' if passed == len(RESULTS) else 'FAIL'}")

    base = fixture.write_report("editor_base", LOG, RESULTS, STEPS)
    out(f"  Report:  tests/editor_base/{base}.txt")

    if passed != len(RESULTS):
        sys.exit(1)


if __name__ == "__main__":
    main()
