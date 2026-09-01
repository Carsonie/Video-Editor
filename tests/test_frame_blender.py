#!/usr/bin/env python3
"""
Exercise Frame Blender's own endpoints — Load, Save Scene, Build, Save MP4 —
against the same disposable store test_editor.py builds.

    python3 tests/test_frame_blender.py            # build, run, tear down
    python3 tests/test_frame_blender.py --keep      # leave the store to poke at

WHY A SEPARATE FILE, NOT MORE STEPS IN test_editor.py
    Frame Blender is a second, independent server (frame_blender/serve.py, its
    own port) that PROXIES three of its five endpoints to the main editor
    (shared/serve.py) rather than reimplementing them — see frame_blender/
    serve.py's MAIN_EDITOR / _proxy(). Testing it means two servers running at
    once, which test_editor.py's single-server harness was never built for.
    Keeping this separate means neither file has to bend its own shape to
    accommodate the other.

WHAT THIS PROVES THAT test_editor.py CANNOT
    Not whether /api/save or /api/siblings work in isolation — that suite
    already covers them exhaustively. This proves the PROXY relays them
    correctly (status code, error body, and all) from a second process, and
    exercises the two endpoints that exist ONLY here: /build_clip (the real
    one-pass picture+voice build) and /api/save_mp4 (the versioned copy into
    sandbox_mp4_scenes/ — which had a real, live bug: asking archive_name_v
    for a name it never records with a matching extension made it hand out
    "v1" forever. That bug is exactly what s_save_mp4_versions guards against.)
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fixture  # noqa: E402

PLAYERS = os.path.dirname(HERE)
MAIN_SERVE = os.path.join(PLAYERS, "shared", "serve.py")
FB_SERVE = os.path.join(PLAYERS, "frame_blender", "serve.py")

MAIN_BASE = None    # set by main()
FB_BASE = None
RESULTS = []
LOG = []
STEPS = []
SAVED_NAMES = []    # real files this run writes under a real store — cleaned up in main()


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


def fb_get(ep, **params):
    url = f"{FB_BASE}{ep}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            return json.load(r), r.status
    except urllib.error.HTTPError as e:
        try:
            return json.load(e), e.code
        except Exception:
            return {"error": e.read().decode(errors="replace")}, e.code


def fb_post(ep, **body):
    req = urllib.request.Request(
        FB_BASE + ep, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r), r.status
    except urllib.error.HTTPError as e:
        try:
            return json.load(e), e.code
        except Exception:
            return {"error": e.read().decode(errors="replace")}, e.code


def wait_up(url, tries=40):
    for _ in range(tries):
        time.sleep(0.25)
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            continue
    return False


def s_load_picker():
    """
    The two-step Load: /api/stores lists what can be opened, and
    /api/load_video opens one video folder's whole sandbox — every scene
    plus the narration script that belongs to them.
    """
    step("/api/stores + /api/load_video — the two-step Load")
    d, code = fb_get("/api/stores")
    eq("stores answers 200", code, 200)
    names = {f"{s['business']}/{s['store']}" for s in d.get("stores", [])}
    check("lists the real stores", "Rentify Demos Corp/ski-demo" in names, sorted(names))
    check("each store names its video folders",
          all("videos" in s for s in d.get("stores", [])), None)

    d, code = fb_get("/api/load_video", root=REAL_STORE_REL)
    eq("load_video answers 200", code, 200)
    rows = [r for v in d.get("by_version", {}).values() for r in v]
    check("returns the video's scenes", len(rows) >= 1, len(rows))
    # 1000_archive is a whole-generation backup, not a scene. Pulling it in
    # would put a duplicate of the entire history into the scene list.
    labels = [str(r.get("label", "")) for r in rows]
    check("1000_archive is NOT among them", not any("1000" in l for l in labels), labels)
    check("script.json comes back with them",
          isinstance(d.get("script"), dict) and "scenes" in (d.get("script") or {}),
          d.get("script_path"))

    _, code = fb_get("/api/load_video")
    eq("a missing root is refused", code, 400)
    _, code = fb_get("/api/load_video", root="Rentify Demos Corp/ski-demo")
    eq("a folder with no sandbox/ is refused", code, 400)


def s_load_store():
    step("/api/load_store — Frame Blender's Load, proxied to /api/siblings")
    seg = f"{fixture.ROOT_REL}/sandbox/01-alpha-scene/segment.mp4"
    d, code = fb_get("/api/load_store", path=seg)
    eq("200", code, 200)
    rows = [r for v in d.get("by_version", {}).values() for r in v]
    eq("finds all three fixture scenes", len(rows), 3)
    row1 = next((r for r in rows if r["n"] == 1), None)
    check("row 1 exists", row1 is not None)
    check("carries a real base_slug (for Save)", bool(row1 and row1.get("base_slug")),
          row1.get("base_slug") if row1 else None)
    eq("scene 1 starts pristine", row1.get("base_edited") if row1 else None, False)

    d2, code2 = fb_get("/api/load_store")   # no path at all
    eq("missing path is refused, not a crash", code2, 400)


def s_save_scene_proxy():
    """
    The proxy has to relay BOTH the happy path and the refusal path
    correctly — a proxy that only forwards 200s would hide the exact
    conflict the staleness check exists to surface.
    """
    step("/api/save_scene — proxied to /api/save, refusal included")
    seg = f"{fixture.ROOT_REL}/sandbox/01-alpha-scene/segment.mp4"
    d, _ = fb_get("/api/load_store", path=seg)
    rows = [r for v in d.get("by_version", {}).values() for r in v]
    slug = next(r for r in rows if r["n"] == 1)["base_slug"]

    d1, code1 = fb_post("/api/save_scene", slug=slug)
    eq("a normal save proxies through as 200", code1, 200)
    check("with the real save result", "nb_frames" in d1, d1)

    # Simulate a save from elsewhere (the main editor, another tab) landing
    # on the SAME file behind this cache's back.
    seg_path = os.path.join(fixture.STORE, "sandbox", "01-alpha-scene", "segment.mp4")
    os.utime(seg_path, None)
    d2, code2 = fb_post("/api/save_scene", slug=slug)
    eq("the conflict comes through as 409, not swallowed", code2, 409)
    eq("with the same error the direct endpoint gives", d2.get("error"), "stale")

    d3, code3 = fb_post("/api/save_scene", slug=slug, force=True)
    eq("force proxies through too", code3, 200)



# build_clip and save_mp4 need footage shaped like a real release — the
# 1152x1152 canvas, and an avatar clip that actually carries a voice track.
# The disposable fixture is deliberately lighter than that (it exists to
# test frame-level editing, not full builds), so these two checks borrow one
# scene from a real, already-committed store instead of asking the fixture
# to be something it was never built to be. REAL_SCENE is never written to —
# only read from — so this is safe to run against live customer data.
REAL_STORE_REL = ("Rentify Demos Corp/bike-demo/help-videos/videos/"
                   "01-first-time-ordering")
REAL_SEG = f"{REAL_STORE_REL}/sandbox/01-login/segment.mp4"
REAL_AV = f"{REAL_STORE_REL}/sandbox/01-login/avatar.webm"
SAVE_MP4_DIR = os.path.join(fixture.CUSTOMERS, REAL_STORE_REL, "video", "sandbox_mp4_scenes")

# ski-demo is the one store with a real sarah_clips/libs/ — the Frame
# Selector's own library — so these three tests borrow it the same way the
# builds above borrow bike-demo. Read-only: /api/lib_frames only ever
# EXTRACTS into cache/, it never writes into Customers/ itself.
SKI_STORE_REL = "Rentify Demos Corp/ski-demo/help-videos/videos/01-first-time-ordering"
SKI_SEG = f"{SKI_STORE_REL}/sandbox/01-intro-and-login/segment.mp4"
SKI_AV = f"{SKI_STORE_REL}/sandbox/01-intro-and-login/avatar.webm"
SKI_LIB_CLIP = f"{SKI_STORE_REL}/sarah_clips/libs/gap-fillers/gap-filler-1.0s.webm"
SKI_LIB_STILL = f"{SKI_STORE_REL}/sarah_clips/libs/stills/sarah-rest-pose-corner-300-alpha.png"


def s_build_clip():
    step("/build_clip — the real one-pass picture+voice build")
    # Stateless as of 2026-08-30: the pair is named on the request itself,
    # not remembered by the server from an earlier page load.
    d, code = fb_get("/api/open_pair", base=REAL_SEG, overlay=REAL_AV)
    eq("open_pair answers 200", code, 200)
    check("and returns both cache slugs", bool(d.get("base_slug") and d.get("over_slug")), d)

    d, code = fb_get("/build_clip", base=REAL_SEG, overlay=REAL_AV, n=10)
    eq("200", code, 200)
    eq("built exactly the frame count asked for", d.get("frames"), 10)
    check("names a real file", bool(d.get("url")), d.get("url"))

    # build_preview_clip's own docstring promises this is clamped rather than
    # erroring — asking for more frames than the avatar has should still
    # build the whole avatar's length, not fail or hang on a bad ffmpeg call.
    d2, code2 = fb_get("/build_clip", base=REAL_SEG, overlay=REAL_AV, n=999999)
    check("an over-large request is clamped, not a crash", code2 == 200 and not d2.get("error"),
          (code2, d2))


def s_save_mp4_versions():
    """
    The exact bug this locks in: naming the destination file WITH an
    extension (.mp4) while asking a helper that only recognises names
    WITHOUT one to find the last version. It found nothing, every call
    answered v1, and a second save silently overwrote the first instead of
    versioning past it. Three calls here have to produce three DIFFERENT
    files, or this regresses back to that.
    """
    step("/api/save_mp4 — versioned copy into sandbox_mp4_scenes/, and it actually increments")
    names = []
    for i in range(3):
        d, code = fb_get("/api/save_mp4", base=REAL_SEG, n=10)
        eq(f"save {i + 1}: 200", code, 200)
        names.append(d.get("saved"))
    check("three saves, three different filenames", len(set(names)) == 3, names)
    check("all three actually exist on disk", all(
        os.path.isfile(os.path.join(fixture.CUSTOMERS, n)) for n in names if n), names)

    d, code = fb_get("/api/save_mp4", base=REAL_SEG, n=99999)
    eq("a frame count nothing was built for is refused, not silently wrong", code, 400)

    global SAVED_NAMES
    SAVED_NAMES = names


def s_libs_list_paths():
    """
    Each file /api/libs_list returns now carries its own `path` (relative
    to Customers/), added specifically so the Frame Selector can hand it
    straight to /api/lib_frames. A name alone can't do that — two different
    library folders can hold a file with the same name.
    """
    step("/api/libs_list — every file carries a real, resolvable path")
    d, code = fb_get("/api/libs_list", base=SKI_SEG, overlay=SKI_AV)
    eq("200", code, 200)
    files = [f for g in d.get("groups", []) for f in g.get("files", [])]
    check("finds real library files", len(files) > 0, len(files))
    check("every file has a path", all("path" in f for f in files), files[:1])
    sample = files[0]
    check("that path is a real file under Customers/",
          os.path.isfile(os.path.join(fixture.CUSTOMERS, sample["path"])),
          sample["path"])


def s_lib_frames_clip():
    """
    /api/lib_frames on a real clip — the Frame Selector's own backend.
    Goes through the SAME extraction every OVERLAY track already uses
    (alpha_png=True, since every file in this library is a transparent
    Sarah render), so its frames must be servable the identical way.
    """
    step("/api/lib_frames — a real .webm clip")
    d, code = fb_get("/api/lib_frames", path=SKI_LIB_CLIP)
    eq("200", code, 200)
    eq("kind is clip", d.get("kind"), "clip")
    check("has a real, multi-frame count", isinstance(d.get("n"), int) and d["n"] > 1, d.get("n"))
    check("names a real cache slug", bool(d.get("slug")), d.get("slug"))
    eq("frames are alpha PNGs, like any overlay track", d.get("ext"), ".png")

    url = f"{FB_BASE}/{d['slug']}/frames/frame_00001{d['ext']}"
    r = urllib.request.urlopen(url, timeout=10)
    eq("frame 1 is really servable at that URL", r.status, 200)

    _, code2 = fb_get("/api/lib_frames")
    eq("a missing path is refused", code2, 400)
    _, code3 = fb_get("/api/lib_frames", path="not/a/real/file.webm")
    eq("a path that isn't a real file is refused, not a crash", code3, 400)


def s_lib_frames_still():
    """
    A still has no frames to extract — it gets a hand-built ONE-frame cache
    entry instead (see lib_frames()'s own docstring), so the page can
    address it through the exact same slug+frame URL scheme as a real
    clip, with no second code path in app.js just for stills.
    """
    step("/api/lib_frames — a still image gets a one-frame cache entry")
    d, code = fb_get("/api/lib_frames", path=SKI_LIB_STILL)
    eq("200", code, 200)
    eq("kind is still", d.get("kind"), "still")
    eq("exactly one frame", d.get("n"), 1)
    eq("keeps its own PNG extension", d.get("ext"), ".png")

    url = f"{FB_BASE}/{d['slug']}/frames/frame_00001{d['ext']}"
    r = urllib.request.urlopen(url, timeout=10)
    eq("that one frame is really servable", r.status, 200)

    # Asking again must reuse the same cache entry, not duplicate or rebuild it.
    d2, code2 = fb_get("/api/lib_frames", path=SKI_LIB_STILL)
    eq("asking again still answers 200", code2, 200)
    eq("same slug both times", d2.get("slug"), d.get("slug"))


def s_stateless():
    """
    The restructure's actual promise: this server remembers no scene. A
    scene-acting call that names no pair must be refused, no matter what
    was opened a moment ago — that is what makes Clear real and what stops
    two browser tabs fighting over one remembered pair.
    """
    step("stateless — a call that names no pair is refused, even right after opening one")
    fb_get("/api/open_pair", base=REAL_SEG, overlay=REAL_AV)   # open something first
    for ep in ("/build_clip", "/api/libs_list", "/api/save_mp4"):
        d, code = fb_get(ep, n=10)
        eq(f"{ep} refuses without a pair", code, 400)
        check(f"{ep} says why", "base is required" in str(d.get("error", "")), d)


def s_static_page():
    step("the page ships EMPTY — no scene baked into the HTML")
    html = urllib.request.urlopen(FB_BASE + "/", timeout=10).read().decode()
    check("says nothing is loaded", "nothing loaded" in html, html[:0] or "ok")
    for gone in ("base_slug", "over_slug", "01-opening-with-login"):
        check(f"no {gone} baked in", gone not in html)
    # gap-builder.js must be named BEFORE app.js — app.js's own bootstrap
    # calls straight into functions gap-builder.js defines, so if load
    # order here ever regressed, the page would fail at the very last line
    # of app.js with everything above it having worked perfectly.
    gb_pos = html.find("gap-builder.js")
    app_pos = html.find('src="/web/app.js"')
    check("gap-builder.js is named before app.js", -1 < gb_pos < app_pos, (gb_pos, app_pos))
    for asset, ctype in (("/web/app.js", "javascript"), ("/web/gap-builder.js", "javascript"),
                         ("/web/app.css", "css")):
        r = urllib.request.urlopen(FB_BASE + asset, timeout=10)
        eq(f"{asset} served", r.status, 200)
        check(f"{asset} content-type", ctype in r.headers.get("Content-Type", ""),
              r.headers.get("Content-Type"))
        # A stale copy is a fix that silently did not apply — it cost a real
        # round of confusion before the restructure, so this is asserted for
        # every script this page ships, not just the first one.
        if asset.endswith(".js"):
            eq(f"{asset} is no-store", r.headers.get("Cache-Control"), "no-store")


def s_app_js_parses():
    """
    The exact gap test_editor.py's own s_pages_parse() exists to close, for
    THIS page: every check in this whole file drives HTTP, so a script that
    throws on load would still answer every endpoint perfectly and this
    suite would stay green regardless — it happened here for real, twice,
    both times a syntax error that Python (there is none, in a static .js
    file) could never have caught: doubled backslash-escapes surviving the
    2026-08-30 extraction out of player.py's template, and later a modal's
    markup sitting after its own <script> tag.

    Checks each file's OWN syntax first, then both CONCATENATED in the same
    order the page loads them — gap-builder.js then app.js, exactly as
    index.html names them, and deliberately neither file wrapped in its own
    IIFE (see app.js's own header comment on why) specifically so each can
    call the other's top-level declarations directly. That same flat shared
    scope is also the one place a NEW kind of bug can now hide: two files
    that each parse perfectly alone can still declare the same `let` or
    `const` name and throw the moment they share a scope for real — a class
    of bug neither file's own syntax check would ever catch alone. Fetches
    the REAL served files, not the ones on disk, so a serving bug is
    caught too.
    """
    step("web/*.js — does the JavaScript actually parse, alone and together?")
    node = shutil.which("node")
    if node is None:
        check("node is available to parse it", False,
              "install node, or this can never catch a broken page again")
        return
    gb = urllib.request.urlopen(FB_BASE + "/web/gap-builder.js", timeout=10).read().decode()
    js = urllib.request.urlopen(FB_BASE + "/web/app.js", timeout=10).read().decode()

    def parses(name, text):
        tmp = os.path.join(tempfile.gettempdir(), f"fb_{name}_check.js")
        with open(tmp, "w") as fh:
            fh.write(text)
        r = subprocess.run([node, "--check", tmp], capture_output=True, text=True)
        os.remove(tmp)
        first = (r.stderr or "").strip().split("\n")
        check(f"{name} parses", r.returncode == 0,
              f"{len(text)} bytes" if r.returncode == 0
              else next((l for l in first if "Error" in l), first[0] if first else ""))

    parses("gap-builder.js", gb)
    parses("app.js", js)
    parses("gap-builder.js + app.js together (load order)", gb + "\n" + js)


FUNCTIONS = [s_static_page, s_app_js_parses, s_stateless, s_load_picker, s_load_store,
             s_save_scene_proxy, s_build_clip, s_save_mp4_versions,
             s_libs_list_paths, s_lib_frames_clip, s_lib_frames_still]


def main():
    global MAIN_BASE, FB_BASE
    ap = argparse.ArgumentParser()
    ap.add_argument("--main-port", type=int, default=8851)
    ap.add_argument("--fb-port", type=int, default=8852)
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    MAIN_BASE = f"http://localhost:{a.main_port}"
    FB_BASE = f"http://localhost:{a.fb_port}"

    out(f"Frame Blender Test:  {time.strftime('%Y-%m-%dT%H:%M:%S')}")
    out(f"Store:               {fixture.ROOT_REL}  (built, used, deleted)")
    out(f"Main editor:         {MAIN_BASE}")
    out(f"Frame Blender:       {FB_BASE}")

    step("Build the test store")
    for n, label, ns, na, nn, _ in fixture.SCENES:
        check(f"{n:02d}-{label}", True, f"segment={ns} avatar={na} narration={nn}")
    fixture.build(quiet=True)

    main_srv = subprocess.Popen(
        [sys.executable, MAIN_SERVE, "--port", str(a.main_port), "--no-session-log"],
        cwd=os.path.dirname(MAIN_SERVE), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    fb_srv = subprocess.Popen(
        [sys.executable, FB_SERVE, "--port", str(a.fb_port), "--no-session-log"],
        cwd=os.path.dirname(FB_SERVE), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env={**os.environ, "MAIN_EDITOR_URL": MAIN_BASE})
    try:
        if not wait_up(MAIN_BASE + "/browse.html"):
            sys.exit("  the main editor never came up")
        if not wait_up(FB_BASE + "/"):
            sys.exit("  frame_blender never came up")

        for fn in FUNCTIONS:
            fn()
    finally:
        # s_save_mp4_versions writes real files under bike-demo's real store
        # (there's no disposable fixture shaped like a real release build —
        # see the note above REAL_STORE_REL). Remove exactly what this run
        # created; never rm -rf the folder, since a real save could land
        # there between now and the next run.
        for rel in SAVED_NAMES:
            p = os.path.join(fixture.CUSTOMERS, rel)
            if os.path.isfile(p):
                os.remove(p)
        if os.path.isdir(SAVE_MP4_DIR) and not os.listdir(SAVE_MP4_DIR):
            os.rmdir(SAVE_MP4_DIR)

        if not a.keep:
            main_srv.terminate()
            fb_srv.terminate()
            fixture.destroy()
        else:
            out(f"\n  --keep: store at {fixture.STORE}")
            out(f"  --keep: servers still on {MAIN_BASE} and {FB_BASE} (kill them yourself)")

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    out(f"\n  Checks:  {passed}/{len(RESULTS)} passed")
    out(f"  Result:  {'PASS' if passed == len(RESULTS) else 'FAIL'}")
    if passed != len(RESULTS):
        sys.exit(1)


if __name__ == "__main__":
    main()
