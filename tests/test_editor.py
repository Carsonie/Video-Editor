#!/usr/bin/env python3
"""
Exercise every function the Segment and Avatar Editor offers, against a
disposable store built from real footage.

    python3 tests/test_editor.py              # build, run, tear down
    python3 tests/test_editor.py --keep       # leave the store to poke at
    python3 tests/test_editor.py --port 8899  # if 8850 is busy
    python3 tests/test_editor.py --server go   # drive the Go rebuild instead

WHY ONE SUITE FOR TWO SERVERS
    Every check here drives HTTP. Nothing in it knows or cares what language
    answers, which is exactly what makes it the right thing to validate a
    rewrite with: point it at the Go backend and it says, in the same checks,
    which of the 29 endpoints that backend has got right.

WHAT IT TESTS AND WHAT IT CANNOT
    Every editor control ends in an HTTP call, and this drives those calls
    directly. That covers everything that CHANGES A FILE — which is everything
    that can lose work.

    It does not drive the browser, so the purely visual controls are out of
    scope by construction: Play, the speed dropdown, Loop Zone, Solo, the
    layer toggle, the tooltips and the border colours. They own no state on
    disk. `--keep` exists for checking those by eye.

    Two UI actions are covered through the endpoint they call rather than by
    name: "Update Frame Imbalance" pads the shorter track and is /api/frames/
    dup-span, and the scene rows' Save is /api/save.

WHY THE ASSERTIONS ARE FRAME COUNTS
    Every real bug this tool has had was an off-by-a-frame that still produced
    a playable file. Save wrote 87 frames for an 89-frame edit for three weeks
    without erroring, because -t drops the frame on the boundary. Nothing
    crashed; the video was just wrong. So every check here asserts an exact
    count, decoded, never a duration and never "the file exists".
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
SERVE = os.path.join(PLAYERS, "shared", "serve.py")
GO_SERVER = os.path.join(PLAYERS, "next-editor-version", "server")

# Which server this run is driving. Set by main(); everything below reads these
# rather than assuming, so the suite itself stays ONE file.
#
#   python   shared/serve.py — the players in use today
#   go       next-editor-version — the rebuild's backend
SERVER = "python"
CACHE = None            # set by main() — a cache each, see the note there

ENDPOINTS_TESTED = ENDPOINTS_TOTAL = 0


def cache_for(server):
    return os.path.join(PLAYERS, "cache" if server == "python" else "cache-go")


def endpoint_counts():
    """How many endpoints the server under test has, and how many this file names.

    Read from the SOURCE rather than written down. A hardcoded "28 of 28" went
    stale the moment an endpoint was added, and read as full coverage while one
    was untested — which is exactly what happened to /api/frames/paste.

    Each server declares its routes in its own shape, so the pattern follows the
    server. Both answer the same question: what does this thing actually serve?
    """
    mine = set(re.findall(r'"(/api/[a-z/-]+)"', open(__file__).read()))
    if SERVER == "go":
        src = open(os.path.join(GO_SERVER, "internal", "editor", "server.go")).read()
        total = set(re.findall(r'"(/api/[a-z/-]+)":', src))
    else:
        src = open(os.path.join(PLAYERS, "shared", "serve.py")).read()
        total = set(re.findall(r'parsed\.path == "(/api/[a-z/-]+)"', src))
    return len(total & mine), len(total)


def start_server(port):
    """Bring the server under test up, and hand back the process.

    The Go one is BUILT first, into a temp binary. `go run` would work and would
    make this test's failure modes worse: it holds the compiler open under the
    server, and a compile error then arrives as a dead port rather than as the
    error it is.
    """
    if SERVER == "go":
        binary = os.path.join(tempfile.gettempdir(), "editord_test")
        r = subprocess.run(["go", "build", "-o", binary, "./cmd/editord"],
                           cwd=GO_SERVER, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"  the Go server does not build:\n{r.stderr}")
        return subprocess.Popen(
            [binary, "--port", str(port), "--no-session-log",
             "--root", PLAYERS, "--cache", CACHE],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return subprocess.Popen(
        [sys.executable, SERVE, "--port", str(port), "--no-session-log"],
        cwd=os.path.join(PLAYERS, "shared"),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)



BASE = None            # set by main()
RESULTS = []           # (name, ok, detail)
LOG = []               # every line, for the log file
STEPS = []             # (number, title, [check indexes])
LOG_DIR = os.path.join(HERE, "log_reports")


def out(line=""):
    """Print it and keep it. The log is the same text the run showed."""
    print(line)
    LOG.append(line)


def step(title):
    STEPS.append([len(STEPS) + 1, title, []])
    out(f"\n  Step {len(STEPS)}: {title}")


# ── plumbing ────────────────────────────────────────────────────────────────
def get(ep, **params):
    url = f"{BASE}{ep}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=600) as r:
            return json.load(r), r.status
    except urllib.error.HTTPError as e:
        return json.load(e), e.code


def post(ep, **body):
    req = urllib.request.Request(
        BASE + ep, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            return json.load(r), r.status
    except urllib.error.HTTPError as e:
        return json.load(e), e.code


def raw_status(ep, **params):
    """For the two *-go endpoints, which redirect rather than answer."""
    url = f"{BASE}{ep}?" + urllib.parse.urlencode(params)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    op = urllib.request.build_opener(NoRedirect)
    try:
        with op.open(url, timeout=600) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def must(ep, **body):
    """POST and insist it worked. The first version of this test called post()
    and ignored the answer; a 400 for a bad `side` value passed silently and
    then failed the next FIVE assertions, each looking like a different bug.
    An unchecked call is worse than no call — it reports the wrong cause."""
    d, code = post(ep, **body)
    if code != 200 or d.get("error"):
        check(f"{ep} should have worked", False, f"{code}: {d.get('error', d)}")
    return d


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    if STEPS:
        STEPS[-1][2].append(len(RESULTS) - 1)
    out(f"     {'✓' if ok else '✗'} {name}" + (f"   {detail}" if detail else ""))
    return bool(ok)


def eq(name, got, want, extra=""):
    return check(name, got == want,
                 f"got {got}, want {want}" if got != want else (extra or str(got)))


def frames(rel, alpha=False):
    return fixture.frames(os.path.join(fixture.STORE, rel), alpha)


def scenes_now():
    p = os.path.join(fixture.STORE, "video", "script.json")
    return [(s["n"], s["label"]) for s in json.load(open(p))["scenes"]]


def line_of(n):
    p = os.path.join(fixture.STORE, "video", "script.json")
    node = next((s for s in json.load(open(p))["scenes"] if s["n"] == n), None)
    return node.get("line") if node else None


def archives(kind):
    d = os.path.join(fixture.STORE, "z_History")
    if not os.path.isdir(d):
        return []
    return sorted(x for x in os.listdir(d) if x.startswith(kind))


# ── the tests: ONE STEP PER DISK FUNCTION ───────────────────────────────────
# 26 endpoints, 26 steps, in the order the work happens. Grouped into 10 steps
# before this; the log then showed "Frame edits" as one green tick covering
# five different functions, and a report that cannot say WHICH function ran is
# not a report.
SEG = None       # the single-clip slug, set by s_open
PAIR = None
SEQ = None


def s_list():
    step("/api/list — browse the store's folders")
    d, _ = get("/api/list", path=fixture.ROOT_REL + "/sandbox")
    eq("lists the three scene folders", len(d.get("dirs", [])), 3)
    d, code = get("/api/list", path="../outside")
    eq("refuses a path outside Customers/", code, 400)


def s_siblings():
    step("/api/siblings — find a scene's other tracks")
    seg = f"{fixture.ROOT_REL}/sandbox/01-alpha-scene/segment.mp4"
    d, _ = get("/api/siblings", path=seg)
    rows = [r for v in d.get("by_version", {}).values() for r in v]
    eq("finds all three scenes", len(rows), 3)
    check("pairs the segment with its avatar",
          any(r.get("overlay", "").endswith("avatar.webm") for r in rows),
          f"scope={d.get('editor_scope')}")


def s_open():
    step("/api/open — open one clip")
    global SEG
    seg = f"{fixture.ROOT_REL}/sandbox/01-alpha-scene/segment.mp4"
    d, _ = get("/api/open", path=seg)
    SEG = (d.get("url") or "").split("/")[0]
    check("built a viewer page", bool(SEG), SEG or json.dumps(d)[:80])
    d, code = get("/api/open", path="../outside/x.mp4")
    eq("refuses a path outside Customers/", code, 400)


def s_map():
    step("/api/frames/map — read the frame map")
    d, _ = get("/api/frames/map", slug=SEG)
    eq("40 entries, one per source frame", d.get("nb_frames"), 40)
    check("starts as an identity map", d["frame_map"] == list(range(1, 41)), "1..40")


def s_open_pair():
    step("/api/open-pair — the layered view")
    global PAIR
    seg = f"{fixture.ROOT_REL}/sandbox/01-alpha-scene/segment.mp4"
    av = f"{fixture.ROOT_REL}/sandbox/01-alpha-scene/avatar.webm"
    d, _ = get("/api/open-pair", base=seg, overlay=av)
    PAIR = d.get("slug")
    check("segment under avatar, both extracted", bool(PAIR), PAIR or json.dumps(d)[:90])


def s_open_pair_go():
    step("/api/open-pair-go — and its redirect")
    seg = f"{fixture.ROOT_REL}/sandbox/01-alpha-scene/segment.mp4"
    av = f"{fixture.ROOT_REL}/sandbox/01-alpha-scene/avatar.webm"
    eq("redirects to the page it built",
       raw_status("/api/open-pair-go", base=seg, overlay=av), 302)


def s_open_seq():
    step("/api/open-seq — the timeline")
    global SEQ
    d, _ = get("/api/open-seq", root=fixture.ROOT_REL, ns="1,2,3")
    SEQ = d.get("slug")
    eq("three scenes on one timeline", d.get("scenes"), [1, 2, 3])
    eq("none missing", d.get("missing"), [])


def s_open_seq_go():
    step("/api/open-seq-go — and its redirect")
    eq("redirects to the page it built",
       raw_status("/api/open-seq-go", root=fixture.ROOT_REL, ns="1,2,3"), 302)


def s_dup():
    step("/api/frames/dup — ＋ Frame")
    must("/api/frames/dup", slug=SEG, at=10, count=1, side="right")
    d, _ = get("/api/frames/map", slug=SEG)
    m = d["frame_map"]
    eq("one more frame", len(m), 41)
    eq("the new frame repeats frame 10", m[10], 10)
    check("nothing before the insert moved", m[:10] == list(range(1, 11)), "")
    must("/api/frames/dup", slug=SEG, at=10, count=1, side="left")
    d, _ = get("/api/frames/map", slug=SEG)
    eq("inserting on the left also adds one", d.get("nb_frames"), 42)
    _, code = post("/api/frames/dup", slug=SEG, at=10, count=1, side="sideways")
    eq("refuses a side that is neither left nor right", code, 400)
    _, code = post("/api/frames/dup", slug="../escape", at=1, count=1)
    eq("refuses a slug with a separator", code, 400)


def s_del():
    step("/api/frames/del — − Frame")
    # Deletes the frames BESIDE the current one, and defaults to side="left".
    # Worth stating: at=10 does not remove frame 10.
    before, _ = get("/api/frames/map", slug=SEG)
    d = must("/api/frames/del", slug=SEG, at=10, count=2, side="left")
    after, _ = get("/api/frames/map", slug=SEG)
    eq("two frames gone", after["nb_frames"], before["nb_frames"] - 2)
    eq("it removed the two to the LEFT of frame 10, not frame 10",
       after["frame_map"][6:9], [7, 10, 10])
    eq("and reports how many it actually took", d.get("actual", 2), 2)

    d = must("/api/frames/del", slug=SEG, at=1, count=5, side="left")
    eq("clamped at the start — nothing before frame 1 to take",
       d.get("actual", 0), 0)

    n = get("/api/frames/map", slug=SEG)[0]["nb_frames"]
    must("/api/frames/del", slug=SEG, at=5, count=1, side="right")
    d, _ = get("/api/frames/map", slug=SEG)
    eq("side=right takes the one after instead", d["nb_frames"], n - 1)

    must("/api/frames/restore", slug=SEG, frame_map=list(range(1, 41)))
    d, _ = get("/api/frames/map", slug=SEG)
    eq("put back to 40 for the steps that follow", d["nb_frames"], 40)


def s_dup_span():
    step("/api/frames/dup-span — ＋ Zone, and Update Frame Imbalance")
    must("/api/frames/dup-span", slug=SEG, a=5, b=9)
    d, _ = get("/api/frames/map", slug=SEG)
    eq("a 5-frame zone repeated", d.get("nb_frames"), 45)


def s_del_span():
    step("/api/frames/del-span — − Zone")
    must("/api/frames/del-span", slug=SEG, a=5, b=9)
    d, _ = get("/api/frames/map", slug=SEG)
    eq("the zone removed again", d.get("nb_frames"), 40)


def s_restore():
    step("/api/frames/restore — Undo")
    original = list(range(1, 41))
    must("/api/frames/dup-span", slug=SEG, a=1, b=3)
    d, _ = get("/api/frames/map", slug=SEG)
    eq("an edit to undo", d.get("nb_frames"), 43)
    must("/api/frames/restore", slug=SEG, frame_map=original)
    d, _ = get("/api/frames/map", slug=SEG)
    check("restore puts the exact map back", d["frame_map"] == original,
          f"{d.get('nb_frames')} frames")


def s_mark():
    step("/api/mark — Mark / Unmark")
    must("/api/clear-marks", slug=SEG)
    must("/api/mark", slug=SEG, frame=5, on=True)
    must("/api/mark", slug=SEG, frame=20, on=True)
    d, _ = get("/api/marks", slug=SEG)
    eq("two marks set", sorted(d.get("marks", [])), [5, 20])
    must("/api/mark", slug=SEG, frame=5, on=False)
    d, _ = get("/api/marks", slug=SEG)
    eq("unmarking removes just that one", sorted(d.get("marks", [])), [20])


def s_marks():
    step("/api/marks — read the marks back")
    d, _ = get("/api/marks", slug=SEG)
    eq("lists what is marked", sorted(d.get("marks", [])), [20])
    d, code = get("/api/marks", slug="../escape")
    eq("refuses a slug with a separator", code, 400)


def s_clear_marks():
    step("/api/clear-marks — Unmark all")
    must("/api/clear-marks", slug=SEG)
    d, _ = get("/api/marks", slug=SEG)
    eq("none left", d.get("marks", []), [])


def s_save():
    step("/api/save — 💾 Save scene")
    eq("the file starts at 40 frames",
       frames("sandbox/01-alpha-scene/segment.mp4"), 40)
    must("/api/frames/dup-span", slug=SEG, a=5, b=9)          # 40 -> 45
    d = must("/api/save", slug=SEG)
    check("no frame-count warning", not d.get("warning"), d.get("warning", "none"))
    eq("the FILE now has exactly 45 frames",
       frames("sandbox/01-alpha-scene/segment.mp4"), 45)
    check("archived the previous file", bool(d.get("archived_to")),
          os.path.basename(str(d.get("archived_to"))))


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

    # Cutting does NOT consume the marks. Every attempt is kept as its own
    # version, so a second cut is a second try, not an error.
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


def s_vtt():
    step("/api/vtt — the timing table")
    d, _ = get("/api/vtt", root=fixture.ROOT_REL)
    eq("one row per script scene", len(d.get("scenes", [])), 3)
    eq("the voice's measured words-per-second", d.get("wps"), 3.44)
    eq("counts the spoken words of scene 1",
       next(r for r in d["scenes"] if r["n"] == 1)["words"], 7)
    d, code = get("/api/vtt", root="../outside")
    eq("refuses a path outside Customers/", code, 400)


def s_line():
    step("/api/line — edit a line in the VTT")
    new = "A replacement line for the first scene."
    d, _ = post("/api/line", root=fixture.ROOT_REL, n=1, line=new)
    eq("the new text comes back", d.get("line"), new)
    eq("written to script.json", line_of(1), new)
    check("archived the script first",
          os.path.isdir(os.path.join(fixture.STORE, "z_History", "line-edits")), "")
    d, _ = post("/api/line", root=fixture.ROOT_REL, n=1, line=new)
    check("writing the same text is a no-op", d.get("unchanged") is True, "")
    d, _ = post("/api/line", root=fixture.ROOT_REL, n=1, line="  spaced   out  ")
    eq("whitespace is tidied", d.get("line"), "spaced out")
    d, code = post("/api/line", root=fixture.ROOT_REL, n=99, line="x")
    eq("refuses a scene that is not in the script", code, 400)


def s_join():
    step("/api/join — Join, every track")
    _, code = post("/api/join", root=fixture.ROOT_REL, ns=[1], label="solo")
    eq("refuses fewer than two scenes", code, 400)
    _, code = post("/api/join", root=fixture.ROOT_REL, ns=[1, 2], label="Bad Name!")
    eq("refuses a name that is not a slug", code, 400)

    seg0 = frames("sandbox/01-alpha-scene/segment.mp4")        # 45 after the save
    d, _ = post("/api/join", root=fixture.ROOT_REL, ns=[1, 2], label="joined",
                tracks=["segment", "avatar"])
    check("succeeded", "error" not in d, d.get("error", ""))
    eq("segment is the two lengths added",
       frames("sandbox/01-joined/segment.mp4"), seg0 + 32)
    eq("avatar is the two lengths added",
       frames("sandbox/01-joined/avatar.webm", True), 30 + 32)
    eq("narration travelled with the avatar",
       frames("sandbox/01-joined/narration.webm", True), 35 + 28)
    eq("two scenes left", len(scenes_now()), 2)
    eq("the third scene was renumbered to 2", scenes_now()[1], (2, "charlie-scene"))
    check("its FOLDER was renamed to match",
          os.path.isdir(os.path.join(fixture.STORE, "sandbox", "02-charlie-scene")),
          "02-charlie-scene")
    check("archived what it consumed", bool(archives("join-")), archives("join-"))


def s_renumber_state():
    step("/api/renumber-state — the save-as-a-set lock")
    d, _ = get("/api/renumber-state", root=fixture.ROOT_REL)
    check("set by the join, and survives a reload", d.get("renumbered") is True, "")
    eq("and says which scene moved where", d.get("moved"), [{"from": 3, "to": 2}])


def s_renumber_clear():
    step("/api/renumber-clear — lift the lock")
    must("/api/renumber-clear", root=fixture.ROOT_REL)
    d, _ = get("/api/renumber-state", root=fixture.ROOT_REL)
    check("cleared once the set is written", d.get("renumbered") is False, "")


def s_split():
    step("/api/split — Split, every track")
    _, code = post("/api/split", root=fixture.ROOT_REL, n=1, at=10,
                   labels=["same", "same"])
    eq("refuses two halves with the same name", code, 400)

    before = archives("split-")
    av = frames("sandbox/01-joined/avatar.webm", True)
    _, code = post("/api/split", root=fixture.ROOT_REL, n=1, at=av + 5,
                   labels=["head", "tail"])
    eq("refuses a frame past the shorter track", code, 400)
    eq("leaves NO archive for a split that never ran", archives("split-"), before)

    seg = frames("sandbox/01-joined/segment.mp4")
    nar = frames("sandbox/01-joined/narration.webm", True)
    at = 21
    d, _ = post("/api/split", root=fixture.ROOT_REL, n=1, at=at, labels=["head", "tail"])
    check("succeeded", "error" not in d, d.get("error", ""))
    eq("segment head", frames("sandbox/01-head/segment.mp4"), at - 1)
    eq("segment tail", frames("sandbox/02-tail/segment.mp4"), seg - at + 1)
    eq("avatar head", frames("sandbox/01-head/avatar.webm", True), at - 1)
    eq("avatar tail", frames("sandbox/02-tail/avatar.webm", True), av - at + 1)
    eq("narration head", frames("sandbox/01-head/narration.webm", True), at - 1)
    eq("narration tail", frames("sandbox/02-tail/narration.webm", True), nar - at + 1)
    eq("three scenes again", len(scenes_now()), 3)
    check("the line stayed with the first half", bool(line_of(1)), "")
    eq("the second half is left empty for a human", line_of(2), "")
    check("archived what it cut", bool(archives("split-")), archives("split-"))


def s_handoff():
    step("/api/handoff — the MP4 Splitter's deposit into dev")
    # The splitter's step, not the editor's, but it writes into the sandbox the
    # editor reads and it is served from here, so it is tested here.
    # The fixture is a bare store — no videos/<name>/ level — which is exactly
    # the shape the guard exists for.
    # A LIVE slug, opened here. Using the one from earlier steps made this pass
    # for the wrong reason: reset-editor had deleted that cache, so the 400 came
    # back as "unknown slug" and the guard under test never ran.
    d, _ = get("/api/open",
               path=f"{fixture.ROOT_REL}/sandbox/03-charlie-scene/segment.mp4")
    live = (d.get("url") or "").split("/")[0]
    check("a live clip to hand off from", bool(live), live)

    d, code = post("/api/handoff", slug=live, version=1, names=["a"])
    eq("refuses before anything has been cut", code, 400)
    check("saying so plainly", "cut" in d.get("error", ""), d.get("error", "")[:50])

    # Cut it, so the handoff gets past "nothing has been cut" and reaches the
    # guard that is actually under test.
    must("/api/mark", slug=live, frame=10, on=True)
    cut = must("/api/cut", slug=live)
    eq("two pieces to hand over", cut.get("count"), 2)

    d, code = post("/api/handoff", slug=live, version=cut["version"],
                   names=["one", "two"])
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
    eq("and names the destination it would use",
       "z_History" in str(d.get("into")), True)
    check("nothing moved by a dry run",
          os.path.isdir(os.path.join(fixture.STORE, "sandbox")), "")

    d = must("/api/archive", root=fixture.ROOT_REL, folder="sandbox")
    check("sandbox is COPIED, not moved — the scenes stay put",
          d.get("moved") is False, f"moved={d.get('moved')}")
    kept = sorted(x for x in os.listdir(os.path.join(fixture.STORE, "sandbox"))
                  if not x.startswith(".") and x != "z_History")
    check("every scene folder is still there", bool(kept), f"{len(kept)} kept")
    snap = d.get("archived_to")
    eq("and the snapshot holds the same folders", sorted(os.listdir(snap)), kept)

    d2 = must("/api/archive", root=fixture.ROOT_REL, folder="sandbox")
    check("a second archive the same day is v_2, not a clash",
          str(d2.get("archived_to", "")).endswith("v_2"),
          os.path.basename(str(d2.get("archived_to"))))

    d, code = post("/api/archive", root=fixture.ROOT_REL, folder="elsewhere")
    eq("refuses a folder that is not dev or sandbox", code, 400)
    d, code = post("/api/archive", root="../outside", folder="sandbox")
    eq("refuses a path outside Customers/", code, 400)


def s_pages_parse():
    step("both players' pages — does the JavaScript actually run?")
    # The gap that let a broken page ship. Every check here drives HTTP, so a
    # page whose script dies on load still answers every endpoint perfectly and
    # the suite stays green. It happened: an apostrophe in "the video's dev/
    # folder" closed a single-quoted string, the whole script threw at load, and
    # nothing in the MP4 Splitter worked — not even Play. Python parsed it, the
    # 94 checks passed, and it was pushed.
    node = shutil.which("node")
    if node is None:
        check("node is available to parse the pages", False,
              "install node, or this can never catch a broken page again")
        return
    # Read the folder from the SCRIPT. Naming one directly fails here: this
    # runs last, and the join and split above have renamed every scene by now.
    doc = json.load(open(os.path.join(fixture.STORE, "video", "script.json")))
    sc = doc["scenes"][-1]
    folder = f"{sc['n']:02d}-{sc['label']}"
    seg = f"{fixture.ROOT_REL}/sandbox/{folder}/segment.mp4"
    av = f"{fixture.ROOT_REL}/sandbox/{folder}/avatar.webm"
    pages = {}
    d, _ = get("/api/open", path=seg)
    pages["MP4 Splitter"] = d.get("url")
    d, _ = get("/api/open-pair", base=seg, overlay=av)
    pages["Segment and Avatar Editor (layered)"] = f"{d.get('slug')}/viewer.html"
    ns = ",".join(str(x["n"]) for x in doc["scenes"])
    d, _ = get("/api/open-seq", root=fixture.ROOT_REL, ns=ns)
    pages["Segment and Avatar Editor (timeline)"] = f"{d.get('slug')}/viewer.html"

    for name, url in pages.items():
        if not url or url.startswith("None"):
            check(f"{name}: page built", False, str(url))
            continue
        try:
            with urllib.request.urlopen(f"{BASE}/{url}", timeout=120) as r:
                html = r.read().decode()
        except Exception as e:
            check(f"{name}: page served", False, str(e)[:60])
            continue
        js = "\n".join(re.findall(r"<script>(.*?)</script>", html, re.S))
        tmp = os.path.join(tempfile.gettempdir(), "vp_check.js")
        with open(tmp, "w") as fh:
            fh.write(js)
        r = subprocess.run([node, "--check", tmp], capture_output=True, text=True)
        os.remove(tmp)
        first = (r.stderr or "").strip().split("\n")
        check(f"{name}: its JavaScript parses", r.returncode == 0,
              f"{len(js)} bytes" if r.returncode == 0
              else next((l for l in first if "Error" in l), first[0] if first else ""))


def live_clip(folder="03-charlie-scene", name="segment.mp4"):
    """Open a clip and return its cache slug.

    The steps below run AFTER reset-editor has deleted the slug the earlier
    ones shared, so each opens its own. Reusing a slug across a reset is how
    the first version of these steps failed — with a KeyError, which reads as a
    test bug rather than as "that cache is gone".
    """
    d, _ = get("/api/open", path=f"{fixture.ROOT_REL}/sandbox/{folder}/{name}")
    return (d.get("url") or "").split("/")[0]


def s_clip():
    step("/api/clip — the clip's own facts, for a front end that was not generated")
    # THE ONE ENDPOINT THE REBUILD ADDS. The Python players baked these values
    # straight into the page — `const N = 40; const FPS = 25.0;` were written
    # into the JavaScript at extraction time, so the page never had to ask. A
    # React front end is served as a static bundle and handed a slug, so it does.
    #
    # Skipped against the Python server, which has no such endpoint and needs
    # none. Saying so beats a red tick that means "not applicable".
    if SERVER != "go":
        check("only the Go backend serves this — nothing to check here", True,
              "the Python players generate their pages instead")
        return
    slug = live_clip("03-charlie-scene")
    d, _ = get("/api/clip", slug=slug)
    eq("the frame count matches the fixture", d.get("nb_frames"), 25)
    eq("and the frame rate", d.get("fps"), 25.0)
    eq("an opaque clip is extracted as JPEG", d.get("ext"), ".jpg")
    check("it names the source file", str(d.get("source", "")).endswith("segment.mp4"),
          os.path.basename(str(d.get("source"))))
    check("and says where a cut would land — derived in the BACKEND, so the "
          "page never has to know the folder rules",
          "_cuts" in str(d.get("cuts_dir")), str(d.get("cuts_dir"))[-40:])

    # An alpha clip. `alpha` is what swaps the break-point colour from green to
    # purple, and in the single-clip view the marks are the ONLY thing that can
    # say which kind of file is open.
    av = live_clip("03-charlie-scene", "avatar.webm")
    d, _ = get("/api/clip", slug=av)
    check("an avatar clip reports itself as alpha", d.get("alpha") is True,
          f"ext={d.get('ext')}")
    eq("and is extracted as PNG, which is what carries the transparency",
       d.get("ext"), ".png")

    d, code = get("/api/clip", slug="../escape")
    eq("refuses a slug with a separator", code, 400)


def s_paste():
    step("/api/frames/paste — copy a frame, put it somewhere else")
    slug = live_clip()
    d, _ = get("/api/frames/map", slug=slug)
    before, m0 = d["nb_frames"], d["frame_map"]

    must("/api/frames/paste", slug=slug, **{"from": 5, "at": 20})
    d, _ = get("/api/frames/map", slug=slug)
    m1 = d["frame_map"]
    eq("one more frame", d["nb_frames"], before + 1)
    # The whole point: the pasted frame IS frame 5, not a picture of it.
    eq("the pasted frame carries frame 5's SOURCE number", m1[20], m0[4])
    eq("the frame it was pasted after is untouched", m1[19], m0[19])
    eq("everything after it shifted right by one", m1[21], m0[20])
    check("and the frame it was copied FROM still stands", m1[4] == m0[4], "")

    _, code = post("/api/frames/paste", slug=slug, **{"from": 5, "at": 9999})
    eq("refuses a target past the end", code, 400)
    _, code = post("/api/frames/paste", slug=slug, **{"from": 9999, "at": 5})
    eq("refuses a source past the end", code, 400)
    _, code = post("/api/frames/paste", slug="../escape", **{"from": 1, "at": 1})
    eq("refuses a slug with a separator", code, 400)

    must("/api/frames/restore", slug=slug, frame_map=m0)
    d, _ = get("/api/frames/map", slug=slug)
    eq("put back for the steps that follow", d["nb_frames"], before)


def s_alpha_survives():
    step("alpha survives a rebuild — the bug that made the avatar vanish")
    # An OVERLAY is extracted as PNG with real transparency. clear-edits and
    # save both re-extract with force=True, and both used to drop alpha_png —
    # so the clip came back as flat JPEG, named .jpg while the page asks for
    # .png. Every overlay frame 404s and the avatar is simply not there.
    av = f"{fixture.ROOT_REL}/sandbox/03-charlie-scene/avatar.webm"
    d, _ = get("/api/open", path=av)
    slug = (d.get("url") or "").split("/")[0]
    check("an alpha clip opened", bool(slug), slug)

    meta = os.path.join(CACHE, slug, "meta.json")
    m = json.load(open(meta))
    eq("extracted as PNG, with alpha", m.get("ext"), ".png")
    check("and the flag is recorded", m.get("alpha_png") is True, str(m.get("alpha_png")))

    must("/api/clear-edits", slug=slug)
    m = json.load(open(meta))
    eq("clear-edits keeps it PNG", m.get("ext"), ".png")
    check("clear-edits keeps the alpha flag", m.get("alpha_png") is True,
          str(m.get("alpha_png")))

    must("/api/frames/dup", slug=slug, at=3, count=1, side="right")
    must("/api/save", slug=slug)
    m = json.load(open(meta))
    eq("a SAVE keeps it PNG too", m.get("ext"), ".png")
    check("a save keeps the alpha flag", m.get("alpha_png") is True,
          str(m.get("alpha_png")))
    check("and the written file still has real alpha",
          fixture.probe_pix_fmt(os.path.join(fixture.STORE, "sandbox",
                                             "03-charlie-scene", "avatar.webm")) == "yuva420p",
          fixture.probe_pix_fmt(os.path.join(fixture.STORE, "sandbox",
                                             "03-charlie-scene", "avatar.webm")))


def s_restore_is_safe():
    step("/api/frames/restore — refuses without destroying anything")
    slug = live_clip("03-charlie-scene")
    d, _ = get("/api/frames/map", slug=slug)
    n, m0 = d["nb_frames"], d["frame_map"]
    # It used to re-extract FIRST and validate second, so a map that failed the
    # check had already wiped the edits it was meant to restore.
    _, code = post("/api/frames/restore", slug=slug,
                   frame_map=list(range(1, n + 500)))
    eq("an impossible map is refused", code, 400)
    d, _ = get("/api/frames/map", slug=slug)
    eq("and the cache is untouched", d["nb_frames"], n)
    check("byte for byte, the same map", d["frame_map"] == m0, "")

    _, code = post("/api/frames/restore", slug=slug, frame_map=[])
    eq("an empty map is refused", code, 400)


def s_one_writer_per_cache():
    step("one writer per cache folder — six edits at once stay consistent")
    # The server is threaded. Nothing used to lock a cache folder, so two
    # clicks a second apart re-extracted into the same frames/ directory and
    # stomped on each other: a 440-frame clip ended up with a 204-frame cache.
    import threading
    slug = live_clip("03-charlie-scene")
    d, _ = get("/api/frames/map", slug=slug)
    start = d["nb_frames"]
    errs = []

    def hit():
        d, c = post("/api/frames/dup", slug=slug, at=10, count=1, side="right")
        if c != 200 or d.get("error"):
            errs.append(d.get("error", c))

    ts = [threading.Thread(target=hit) for _ in range(6)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    eq("all six succeeded", errs, [])
    d, _ = get("/api/frames/map", slug=slug)
    files = len(os.listdir(os.path.join(CACHE, slug, "frames")))
    eq("the count is exactly six more", d["nb_frames"], start + 6)
    eq("and the files on disk agree", files, start + 6)

    must("/api/frames/restore", slug=slug, frame_map=list(range(1, start + 1)))
    d, _ = get("/api/frames/map", slug=slug)
    eq("put back", d["nb_frames"], start)


def s_bookends_and_gaps():
    step("bookends and missing tracks — what a join refuses, and what it fills")
    d, _ = get("/api/open-seq", root=fixture.ROOT_REL, ns="1,2,3")
    seq_slug = d.get("slug")
    page = open(os.path.join(CACHE, seq_slug, "viewer.html")).read()
    check("the manifest marks which scenes are in the script",
          '"in_script"' in page, "in_script")
    check("and which have a narration render",
          '"has_narration"' in page, "has_narration")

    # A scene with no narration joined to scenes that have one. Without
    # fill_gaps the next scene's narration would start at frame 1.
    #
    # The folder is read from the SCRIPT, not assumed: by this point the join
    # and split above have renamed every scene, so 01-alpha-scene is long gone.
    # Naming it directly made this step delete nothing and then assert on a gap
    # that was never created.
    doc = json.load(open(os.path.join(fixture.STORE, "video", "script.json")))
    first = doc["scenes"][0]
    folder = f"{first['n']:02d}-{first['label']}"
    nar = os.path.join(fixture.STORE, "sandbox", folder, "narration.webm")
    check(f"scene 1 is {folder}, and it has a narration to remove",
          os.path.isfile(nar), folder)
    os.remove(nar)
    seg1 = fixture.frames(os.path.join(fixture.STORE, "sandbox", folder, "segment.mp4"))
    d, code = post("/api/join", root=fixture.ROOT_REL, ns=[1, 2], label="mixed",
                   tracks=["segment", "avatar"])
    eq("refuses a mixed narration without being told to fill", code, 400)
    eq("and names the track", d.get("gap"), "narration")
    eq("and the scene missing it", d.get("scenes_missing"), [1])

    d, _ = post("/api/join", root=fixture.ROOT_REL, ns=[1, 2], label="mixed",
                tracks=["segment", "avatar"], fill_gaps=True)
    check("with fill_gaps it joins", "error" not in d, d.get("error", ""))
    filled = d.get("filled") or []
    eq("and says what it filled", [f["scene"] for f in filled], [1])
    nar_n = fixture.frames(os.path.join(fixture.STORE, "sandbox", "01-mixed",
                                        "narration.webm"), alpha=True)
    eq("the filler is as long as the scene that had none",
       filled[0]["frames"], seg1)
    check("so the narration is the filler plus the one that existed",
          nar_n > seg1, f"{nar_n} frames, filler was {seg1}")


# Every disk function, in dependency order. The count in the log's footer is
# taken from this list, so a new endpoint that is not here is visibly missing.
FUNCTIONS = [
    s_list, s_siblings, s_open, s_map, s_open_pair, s_open_pair_go,
    s_open_seq, s_open_seq_go,
    s_dup, s_del, s_dup_span, s_del_span, s_restore,
    s_mark, s_marks, s_clear_marks,
    s_save, s_clear_edits, s_cut, s_reset_editor,
    s_vtt, s_line,
    s_join, s_renumber_state, s_renumber_clear, s_split,
    s_clip, s_paste, s_alpha_survives, s_restore_is_safe, s_one_writer_per_cache,
    s_handoff, s_archive, s_bookends_and_gaps,
    s_pages_parse,
]


# ── runner ──────────────────────────────────────────────────────────────────
def main():
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8850)
    ap.add_argument("--keep", action="store_true",
                    help="leave the test store and the server up afterwards")
    ap.add_argument("--server", choices=("python", "go"), default="python",
                    help="which backend to drive (default: the Python one)")
    a = ap.parse_args()
    BASE = f"http://localhost:{a.port}"

    global SERVER, CACHE
    SERVER = a.server
    # A cache each. The two servers derive an extraction's mtime independently,
    # so ONE shared folder would have each of them decide the other's work was
    # stale and redo it — slow, and confusing to read afterwards.
    CACHE = cache_for(SERVER)

    global ENDPOINTS_TESTED, ENDPOINTS_TOTAL
    ENDPOINTS_TESTED, ENDPOINTS_TOTAL = endpoint_counts()
    ver = open(os.path.join(PLAYERS, "segment_avatar_editor", "VERSION")).read().strip()
    started = time.time()
    stamp = time.strftime("%H_%M_%S")
    name = f"editor_{stamp}.log" if SERVER == "python" else f"editor_go_{stamp}.log"
    out(f"Editor Test:  {time.strftime('%Y-%m-%dT%H:%M:%S')}")
    out(f"Player:       Segment and Avatar Editor v{ver}")
    out(f"Backend:      {'Go — next-editor-version' if SERVER == 'go' else 'Python — shared/serve.py'}")
    out(f"Endpoints:    {ENDPOINTS_TESTED} of {ENDPOINTS_TOTAL} exercised")
    out(f"Store:        {fixture.ROOT_REL}  (built, used, deleted)")
    out(f"Target:       local → {BASE}")
    out(f"Log:          {name}")

    step("Build the test store")
    for n, label, ns, na, nn, _ in fixture.SCENES:
        check(f"{n:02d}-{label}", True, f"segment={ns} avatar={na} narration={nn}")
    fixture.build(quiet=True)

    # --no-session-log: the test writes its own log, and its fixture traffic
    # must not bury a day of real editing in the editor's session log.
    srv = start_server(a.port)
    try:
        for _ in range(40):                     # wait for it to answer
            time.sleep(0.25)
            try:
                urllib.request.urlopen(BASE + "/", timeout=2)
                break
            except Exception:
                continue
        else:
            sys.exit("  the server never came up")

        for fn in FUNCTIONS:
            fn()
    finally:
        if not a.keep:
            srv.terminate()
            fixture.destroy()
        else:
            out(f"\n  --keep: store at {fixture.STORE}")
            out(f"  --keep: server still on {BASE} (kill it yourself)")

    bad = [n for n, ok, _ in RESULTS if not ok]
    out("")
    for num, title, idxs in STEPS:
        ok = all(RESULTS[i][1] for i in idxs)
        out(f"  {'✅' if ok else '❌'} Step {num}: {title}")
    # Counted from the source, not written down — a new endpoint then shows
    # up as a smaller number here instead of quietly going untested.
    out(f"\n  Endpoints:  {ENDPOINTS_TESTED}/{ENDPOINTS_TOTAL} exercised")
    out(f"  Steps:        {len(FUNCTIONS)} + the store build")
    out(f"  Checks:     {len(RESULTS) - len(bad)}/{len(RESULTS)} passed")
    out(f"  Elapsed:    {time.time() - started:.0f}s")
    out(f"  Result:     {'PASS' if not bad else 'FAIL'}")
    if bad:
        out("  Failed:")
        for n in bad:
            out(f"    - {n}")
    out(f"  Log:        {name}")

    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, name)
    with open(path, "w") as fh:
        fh.write("\n".join(LOG) + "\n")
    print(f"\n  written to {path}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
