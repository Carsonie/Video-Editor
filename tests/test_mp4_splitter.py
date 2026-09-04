#!/usr/bin/env python3
"""
Exercise MP4 Splitter's own endpoints — the standalone server
(mp4_splitter/serve.py, port 8845) — against the same disposable store
test_editor.py builds.

    python3 tests/test_mp4_splitter.py            # build, run, tear down
    python3 tests/test_mp4_splitter.py --keep      # leave the store to poke at

WHY THIS FILE DIDN'T EXIST UNTIL NOW
    MP4 Splitter and the Segment and Avatar Editor split off shared/serve.py
    into fully independent processes on 2026-09-02 (own port, own cache,
    duplicated code — see mp4_splitter/serve.py's own module docstring).
    That work was verified by hand at the time — curl and a real browser —
    but never got a permanent, automated suite of its own, so a regression
    in this tool's OWN dispatch table, cache, or log could ship unnoticed.
    This is that suite, added the same day logging was split apart per
    editor too (Carson's own call — see this file's own log-file check).

WHY NOT JUST REUSE test_editor.py
    test_editor.py drives shared/serve.py on port 8842 — the OLD combined
    process. Every route this file exercises is the SAME code (mp4_splitter/
    serve.py started as a literal copy, trimmed to this tool's own routes),
    so this suite is not re-proving that code is correct; it is proving the
    STANDALONE server — its own trimmed dispatch table, its own cache dir,
    its own session log — actually wires together and serves the real
    thing. Routes the split deliberately dropped (Join, Split, Line, Paste,
    the two multi-clip Open flows, ...) are checked as gone, not skipped.
"""
import argparse
import json
import os
import re
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
MP4_SERVE = os.path.join(PLAYERS, "mp4_splitter", "serve.py")

MP4_BASE = None    # set by main()
RESULTS = []
LOG = []
STEPS = []
SEG = None          # the single-clip slug, set by s_open


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


def get(ep, **params):
    url = f"{MP4_BASE}{ep}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            return json.load(r), r.status
    except urllib.error.HTTPError as e:
        try:
            return json.load(e), e.code
        except Exception:
            return {"error": e.read().decode(errors="replace")}, e.code


def post(ep, **body):
    req = urllib.request.Request(
        MP4_BASE + ep, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r), r.status
    except urllib.error.HTTPError as e:
        try:
            return json.load(e), e.code
        except Exception:
            return {"error": e.read().decode(errors="replace")}, e.code


def must(ep, **body):
    """POST and insist it worked — an unchecked call that silently failed
    is what made an earlier version of this pattern fail five LATER
    assertions, each looking like a different bug (see test_editor.py's
    own must(), which this copies)."""
    d, code = post(ep, **body)
    if code != 200 or d.get("error"):
        check(f"{ep} should have worked", False, f"{code}: {d.get('error', d)}")
    return d


def wait_up(url, tries=40):
    for _ in range(tries):
        time.sleep(0.25)
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            continue
    return False


def frames_of(rel, alpha=False):
    return fixture.frames(os.path.join(fixture.STORE, rel), alpha)


def archives(kind):
    d = os.path.join(fixture.STORE, "z_History")
    if not os.path.isdir(d):
        return []
    return sorted(x for x in os.listdir(d) if x.startswith(kind))


def s_static_page():
    step("the landing page — clean title, no scene baked in")
    html = urllib.request.urlopen(MP4_BASE + "/", timeout=10).read().decode()
    check("titled just \"MP4 Splitter\", no \"Browse Customers —\" prefix",
          "<title>MP4 Splitter</title>" in html, "ok" if "<title>MP4 Splitter</title>" in html else html[:120])
    for gone in ("Segment and Avatar Editor", "gap-builder.js", "sarah_clips"):
        check(f"nothing about {gone!r} on this page", gone not in html)


def s_list():
    step("/api/list — browse the store's folders")
    d, _ = get("/api/list", path=fixture.ROOT_REL + "/sandbox")
    eq("lists the three scene folders", len(d.get("dirs", [])), 3)
    d, code = get("/api/list", path="../outside")
    eq("refuses a path outside Customers/", code, 400)


def s_open():
    step("/api/open — open one clip")
    global SEG
    seg = f"{fixture.ROOT_REL}/sandbox/01-alpha-scene/segment.mp4"
    d, _ = get("/api/open", path=seg)
    SEG = (d.get("url") or "").split("/")[0]
    check("built a viewer page", bool(SEG), SEG or json.dumps(d)[:80])
    d, code = get("/api/open", path="../outside/x.mp4")
    eq("refuses a path outside Customers/", code, 400)


def s_own_cache():
    """
    Not a check that cache/<slug> is ABSENT — content-hash slugging means
    Frame Blender or Avatar Editor extracting this exact same fixture file
    on some earlier, unrelated run can legitimately leave a same-named
    folder sitting in the shared cache/ they use, and that is not a
    collision: it is a different directory. What actually matters, and
    what this checks, is that THIS extraction landed in this tool's own
    cache/mp4-splitter/ — the two never write into the same folder.
    """
    step("its own cache — cache/mp4-splitter/, not the shared cache/")
    own = os.path.join(PLAYERS, "cache", "mp4-splitter", SEG)
    check("the clip just opened landed in cache/mp4-splitter/", os.path.isdir(own), own)


def s_map():
    step("/api/frames/map — read the frame map")
    d, _ = get("/api/frames/map", slug=SEG)
    eq("40 entries, one per source frame", d.get("nb_frames"), 40)
    check("starts as an identity map", d["frame_map"] == list(range(1, 41)), "1..40")


def s_dup():
    step("/api/frames/dup — ＋ Frame")
    must("/api/frames/dup", slug=SEG, at=10, count=1, side="right")
    d, _ = get("/api/frames/map", slug=SEG)
    m = d["frame_map"]
    eq("one more frame", len(m), 41)
    eq("the new frame repeats frame 10", m[10], 10)
    _, code = post("/api/frames/dup", slug=SEG, at=10, count=1, side="sideways")
    eq("refuses a side that is neither left nor right", code, 400)
    _, code = post("/api/frames/dup", slug="../escape", at=1, count=1)
    eq("refuses a slug with a separator", code, 400)


def s_del():
    step("/api/frames/del — − Frame")
    before, _ = get("/api/frames/map", slug=SEG)
    d = must("/api/frames/del", slug=SEG, at=10, count=1, side="left")
    after, _ = get("/api/frames/map", slug=SEG)
    eq("one frame gone", after["nb_frames"], before["nb_frames"] - 1)
    eq("and reports how many it actually took", d.get("actual", 1), 1)


def s_restore():
    step("/api/frames/restore — Undo")
    original = list(range(1, 41))
    must("/api/frames/restore", slug=SEG, frame_map=original)
    d, _ = get("/api/frames/map", slug=SEG)
    check("put back to the exact 40-frame identity map", d["frame_map"] == original,
          f"{d.get('nb_frames')} frames")


def s_mark():
    step("/api/mark, /api/marks, /api/clear-marks — Mark / Unmark / Unmark all")
    must("/api/clear-marks", slug=SEG)
    must("/api/mark", slug=SEG, frame=5, on=True)
    must("/api/mark", slug=SEG, frame=20, on=True)
    d, _ = get("/api/marks", slug=SEG)
    eq("two marks set", sorted(d.get("marks", [])), [5, 20])
    must("/api/mark", slug=SEG, frame=5, on=False)
    d, _ = get("/api/marks", slug=SEG)
    eq("unmarking removes just that one", sorted(d.get("marks", [])), [20])
    must("/api/clear-marks", slug=SEG)
    d, _ = get("/api/marks", slug=SEG)
    eq("Clear All leaves none", d.get("marks", []), [])
    d, code = get("/api/marks", slug="../escape")
    eq("refuses a slug with a separator", code, 400)


def s_save():
    step("/api/save — 💾 Save scene")
    eq("the file starts at 40 frames",
       frames_of("sandbox/01-alpha-scene/segment.mp4"), 40)
    must("/api/frames/dup", slug=SEG, at=10, count=5, side="right")   # 40 -> 45
    d = must("/api/save", slug=SEG)
    check("no frame-count warning", not d.get("warning"), d.get("warning", "none"))
    eq("the FILE now has exactly 45 frames",
       frames_of("sandbox/01-alpha-scene/segment.mp4"), 45)
    check("archived the previous file", bool(d.get("archived_to")),
          os.path.basename(str(d.get("archived_to"))))


def s_save_stale():
    step("/api/save — refuses when the file changed elsewhere first")
    seg_path = os.path.join(fixture.STORE, "sandbox", "01-alpha-scene", "segment.mp4")
    os.utime(seg_path, None)
    d, code = post("/api/save", slug=SEG)
    eq("refused with 409", code, 409)
    eq("named as a stale conflict", d.get("error"), "stale")
    d2 = must("/api/save", slug=SEG, force=True)
    check("force overrides the refusal", not d2.get("error"), d2)


def s_clear_edits():
    step("/api/clear-edits — discard the cache's edits")
    d = must("/api/clear-edits", slug=SEG)
    eq("cache re-reads the saved 45-frame file", d.get("nb_frames"), 45)


def s_cut():
    step("/api/cut — ✂ Cut scene")
    must("/api/clear-marks", slug=SEG)
    must("/api/mark", slug=SEG, frame=15, on=True)
    must("/api/mark", slug=SEG, frame=30, on=True)
    d = must("/api/cut", slug=SEG)
    eq("two break points make three segments", d.get("count"), 3)
    eq("written as version 1", d.get("version"), 1)
    check("wrote them to disk", bool(d.get("outdir")) and os.path.isdir(str(d["outdir"])),
          str(d.get("outdir")))
    d2, _ = get("/api/marks", slug=SEG)
    eq("the marks survive the cut", sorted(d2.get("marks", [])), [15, 30])
    d3 = must("/api/cut", slug=SEG)
    eq("cutting again keeps the first attempt and bumps the version",
       d3.get("version"), 2)
    must("/api/clear-marks", slug=SEG)
    _, code = post("/api/cut", slug=SEG)
    eq("with no marks at all it refuses", code, 400)


def s_reset_editor():
    step("/api/reset-editor — reset")
    d = must("/api/reset-editor", slug=SEG)
    check("returns cleanly", d.get("ok") is True, json.dumps(d)[:60])
    check("really deleted the cache slug", not os.path.isdir(
        os.path.join(PLAYERS, "cache", "mp4-splitter", SEG)), SEG)


def live_clip(folder="03-charlie-scene", name="segment.mp4"):
    d, _ = get("/api/open", path=f"{fixture.ROOT_REL}/sandbox/{folder}/{name}")
    return (d.get("url") or "").split("/")[0]


def s_handoff():
    step("/api/handoff — the deposit into dev")
    live = live_clip()
    check("a live clip to hand off from", bool(live), live)

    d, code = post("/api/handoff", slug=live, version=1, names=["a"])
    eq("refuses before anything has been cut", code, 400)
    check("saying so plainly", "cut" in d.get("error", ""), d.get("error", "")[:50])

    must("/api/mark", slug=live, frame=10, on=True)
    cut = must("/api/cut", slug=live)
    eq("two pieces to hand over", cut.get("count"), 2)

    d, code = post("/api/handoff", slug=live, version=cut["version"], names=["one", "two"])
    eq("refuses a clip that is not inside a video folder", code, 400)
    check("and it is the guard refusing, not a stale slug or a missing cut",
          "videos/" in d.get("error", ""), d.get("error", "")[:70])

    d, code = post("/api/handoff", slug=live, version=cut["version"], names=["one"])
    eq("refuses when the names do not match the segments", code, 400)

    d, code = post("/api/handoff", slug="../escape", version=1, names=["a"])
    eq("refuses a slug with a separator", code, 400)


def s_archive():
    step("/api/archive — a folder's generation archive")
    d, _ = post("/api/archive", root=fixture.ROOT_REL, folder="sandbox", dry=True)
    check("dry run says what it WOULD move, before anyone agrees to it",
          isinstance(d.get("would_archive"), list), str(d.get("would_archive"))[:60])
    eq("and names the destination it would use", "z_History" in str(d.get("into")), True)
    check("nothing moved by a dry run",
          os.path.isdir(os.path.join(fixture.STORE, "sandbox")), "")

    d = must("/api/archive", root=fixture.ROOT_REL, folder="sandbox")
    check("sandbox is COPIED, not moved — the scenes stay put",
          d.get("moved") is False, f"moved={d.get('moved')}")
    kept = sorted(x for x in os.listdir(os.path.join(fixture.STORE, "sandbox"))
                  if not x.startswith(".") and x != "z_History")
    check("every scene folder is still there", bool(kept), f"{len(kept)} kept")

    d, code = post("/api/archive", root=fixture.ROOT_REL, folder="elsewhere")
    eq("refuses a folder that is not dev or sandbox", code, 400)


def s_dropped_routes_are_gone():
    """
    The other tools' own routes — Join/Split/Line/Paste/dup-span/del-span
    belong to the Segment and Avatar Editor now; the multi-clip Open flows
    (open-pair, open-seq) and Frame Blender's/Avatar Editor's Load-video/
    Load-store/Build/Save-MP4 belong to THEM. A route left reachable here
    by accident would mean the split's own trim silently regressed.
    """
    step("routes this split deliberately dropped — confirmed gone, not just unused")
    for ep in ("/api/join", "/api/split", "/api/line", "/api/frames/paste",
               "/api/frames/dup-span", "/api/frames/del-span",
               "/api/renumber-clear", "/api/renumber-state", "/api/save-archive",
               "/api/stores", "/api/open-pair", "/api/open-seq",
               "/api/open-pair-go", "/api/open-seq-go", "/api/vtt",
               "/api/load_video", "/api/load_store", "/build_clip", "/api/save_mp4",
               "/api/libs_list", "/api/lib_frames", "/api/lib_media"):
        _, code = get(ep)
        eq(f"{ep} is not served here", code, 404)


def s_session_log():
    """
    A dedicated file (logs/mp4_splitter_<date>.log), not shared/serve.py's
    combined logs/editor_<date>.log — split apart per editor 2026-09-02, at
    the same time this suite was added. Started WITHOUT --no-session-log
    (unlike every other suite in this repo) specifically so this check has
    something real to read; every other check in this file works the same
    either way.
    """
    step("its own dedicated session log")
    log_path = os.path.join(PLAYERS, "logs", f"mp4_splitter_{time.strftime('%Y%m%d')}.log")
    check("the file exists", os.path.isfile(log_path), log_path)
    text = open(log_path).read() if os.path.isfile(log_path) else ""
    check("carries this run's own actions (Save scene)", "Save scene" in text, text[-200:])
    check("labels are plain — no leftover \"FB:\" prefix from the old shared table",
          "FB:" not in text, text[-200:])


def s_app_js_parses():
    step("the pages' JavaScript — does it actually parse?")
    node = shutil.which("node")
    if node is None:
        check("node is available to parse it", False,
              "install node, or this can never catch a broken page again")
        return

    def parses(name, js):
        safe = re.sub(r"[^A-Za-z0-9]+", "_", name)   # "web/app.js" is not a filename
        tmp = os.path.join(tempfile.gettempdir(), f"mp4splitter_{safe}_check.js")
        with open(tmp, "w") as fh:
            fh.write(js)
        r = subprocess.run([node, "--check", tmp], capture_output=True, text=True)
        os.remove(tmp)
        first = (r.stderr or "").strip().split("\n")
        check(f"{name}: its JavaScript parses", r.returncode == 0,
              f"{len(js)} bytes" if r.returncode == 0
              else next((l for l in first if "Error" in l), first[0] if first else ""))

    # The landing page still carries an inline <script>.
    html = urllib.request.urlopen(MP4_BASE + "/", timeout=10).read().decode()
    parses("landing page", "\n".join(re.findall(r"<script>(.*?)</script>", html, re.S)))

    # The clip page does NOT any more — it is web/app.js, fetched as a file.
    # Scraping <script> out of its HTML would now find nothing and hand
    # `node --check` an empty string, which passes while proving nothing.
    # So this fetches the real file. That is the whole reason the step was
    # repointed on 2026-09-04 rather than left alone when it stayed green.
    app_js = urllib.request.urlopen(MP4_BASE + "/web/app.js", timeout=10).read().decode()
    check("web/app.js is really served, and is not empty", len(app_js) > 10000,
          f"{len(app_js)} bytes")
    parses("web/app.js", app_js)

    # ...and the page that loads it must actually reference it, or a served
    # file nothing links to would still pass the check above.
    live = live_clip("02-bravo-scene")
    page = urllib.request.urlopen(f"{MP4_BASE}/{live}/viewer.html", timeout=10).read().decode()
    check("the clip page loads web/app.js", "/web/app.js" in page)
    check("the clip page loads web/app.css", "/web/app.css" in page)
    check("the clip page bakes in NO clip values any more",
          "{" not in page.split("<body")[0].split("<!--")[-1]
          or "nb_frames" not in page, "ships empty")


def s_api_clip():
    """
    /api/clip IS the contract between serve.py and web/app.js since
    2026-09-04. Every value here used to be baked into the HTML by
    player.py's str.format(); if one goes missing the page draws itself
    wrong rather than failing, so all fourteen are named explicitly.
    """
    step("/api/clip — the page ships empty and the clip arrives over the API")
    live = live_clip("02-bravo-scene")
    check("a live clip to ask about", bool(live), live)
    clip, code = get("/api/clip", slug=live)
    eq("a real slug is answered", code, 200)

    WANT = ["title", "source", "source_path", "slug", "nb_frames", "fps",
            "disp_w", "disp_h", "app_w", "stack_w", "has_audio",
            "edited_flag", "edited", "player_label"]
    missing = [k for k in WANT if k not in clip]
    check("all fourteen fields are present", not missing, missing or "none")

    # Real answers, not just present keys.
    eq("nb_frames is the clip's real count", clip.get("nb_frames"),
       frames_of("sandbox/02-bravo-scene/segment.mp4"))
    check("fps is real", bool(clip.get("fps")), clip.get("fps"))
    check("the frame size is real",
          clip.get("disp_w", 0) > 0 and clip.get("disp_h", 0) > 0,
          (clip.get("disp_w"), clip.get("disp_h")))
    eq("app_w is disp_w + 278 (the toolbelt drawer)",
       clip.get("app_w"), clip.get("disp_w", 0) + 278)
    eq("stack_w is disp_w + 292", clip.get("stack_w"), clip.get("disp_w", 0) + 292)
    eq("the slug echoes back", clip.get("slug"), live)
    check("player_label names this tool",
          str(clip.get("player_label", "")).startswith("MP4 Splitter v"),
          clip.get("player_label"))

    # `title` is the BARE clip name. web/app.js composes the tab title as
    # "MP4 Splitter — <title>" (Carson's format, 2026-09-04: editor, dash,
    # what is open). Prefixing it here as well would read
    # "MP4 Splitter — MP4 Splitter — segment.mp4", which is the one way this
    # can break — and the suite cannot see document.title, so this guards
    # the half it can.
    check("title is the bare clip name, not prefixed with the editor",
          not str(clip.get("title", "")).startswith("MP4 Splitter"),
          clip.get("title"))

    _, code = get("/api/clip", slug="no-such-clip-at-all")
    eq("an unknown slug is refused, not answered", code, 400)


def s_stale_cached_pages():
    """
    THE MIGRATION HAZARD, kept as a permanent check.

    player.write() used to render a complete page into every clip's cache
    folder, so on 2026-09-04 there were real clips on disk carrying a fully
    baked copy of the OLD page — one of them from two days earlier. serve.py
    answers /<slug>/viewer.html from web/index.html and ignores the file on
    disk, which makes every one of those correct at once.

    A fresh fixture cannot show this on its own: its caches are new. So this
    writes an old-looking viewer.html into a real clip's folder and proves
    the server does not serve it.
    """
    step("a stale viewer.html on disk is ignored, not served")
    live = live_clip("02-bravo-scene")
    path = os.path.join(PLAYERS, "cache", "mp4-splitter", live, "viewer.html")
    marker = "STALE-BAKED-PAGE-FROM-BEFORE-THE-MIGRATION"
    with open(path, "w") as fh:
        fh.write(f"<!-- {marker} -->\n<html><body>old</body></html>\n")
    check("the stale file really is on disk", os.path.isfile(path))

    with urllib.request.urlopen(f"{MP4_BASE}/{live}/viewer.html", timeout=30) as r:
        page = r.read().decode()
    check("the stale page is NOT what gets served", marker not in page)
    check("the static page is served instead", "/web/app.js" in page)


def s_no_unreachable_handlers():
    """
    A route deleted from do_GET/do_POST leaves its handler BODY behind
    unless someone removes it too, and every "this route is gone" check
    in this file asserts a 404 — which an unreachable handler produces
    just as well as a deleted one. So those checks cannot tell the two
    apart. This one can.

    fixture.dead_handlers() walks out from the dispatchers and reports
    whatever is never reached. Reachability, not "is it called": dead
    code calling dead code looks alive to a plain call-site diff, and
    that is exactly how mp4_splitter's api_open_pair/api_open_seq stayed
    hidden behind two dead _go wrappers.
    """
    step("no handler is defined that the dispatcher cannot reach")
    eq("unreachable handlers", fixture.dead_handlers(MP4_SERVE), [])


FUNCTIONS = [s_static_page, s_list, s_open, s_own_cache, s_map, s_dup, s_del,
             s_restore, s_mark, s_save, s_save_stale, s_clear_edits, s_cut,
             s_reset_editor, s_handoff, s_archive, s_dropped_routes_are_gone,
             s_session_log, s_api_clip, s_stale_cached_pages, s_app_js_parses,
             s_no_unreachable_handlers]


def main():
    global MP4_BASE
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8855)
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    MP4_BASE = f"http://localhost:{a.port}"

    out(f"MP4 Splitter Test:  {time.strftime('%Y-%m-%dT%H:%M:%S')}")
    out(f"Store:              {fixture.ROOT_REL}  (built, used, deleted)")
    out(f"MP4 Splitter:       {MP4_BASE}")

    step("Build the test store")
    for n, label, ns, na, nn, _ in fixture.SCENES:
        check(f"{n:02d}-{label}", True, f"segment={ns} avatar={na} narration={nn}")
    fixture.build(quiet=True)

    # No --no-session-log: s_session_log() needs a real file to read.
    srv = subprocess.Popen(
        [sys.executable, MP4_SERVE, "--port", str(a.port)],
        cwd=os.path.dirname(MP4_SERVE), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not wait_up(MP4_BASE + "/"):
            sys.exit("  mp4_splitter never came up")

        for fn in FUNCTIONS:
            fn()
    finally:
        if not a.keep:
            srv.terminate()
            fixture.destroy()
        else:
            out(f"\n  --keep: store at {fixture.STORE}")
            out(f"  --keep: server still on {MP4_BASE} (kill it yourself)")

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    out(f"\n  Checks:  {passed}/{len(RESULTS)} passed")
    out(f"  Result:  {'PASS' if passed == len(RESULTS) else 'FAIL'}")

    # Own folder, own log + report — tests/mp4_splitter/, never another
    # editor's (see fixture.write_report()'s own docstring for why this
    # is shared code rather than copied four times).
    base = fixture.write_report("mp4_splitter", LOG, RESULTS, STEPS)
    out(f"  Report:  tests/mp4_splitter/{base}.txt")

    if passed != len(RESULTS):
        sys.exit(1)


if __name__ == "__main__":
    main()
