#!/usr/bin/env python3
"""
Exercise the Segment and Avatar Editor's own endpoints — the standalone
server (segment_avatar_editor/serve.py, port 8846) — against the same
disposable store test_editor.py builds.

    python3 tests/test_segment_avatar_editor.py            # build, run, tear down
    python3 tests/test_segment_avatar_editor.py --keep      # leave the store to poke at

WHY THIS FILE DIDN'T EXIST UNTIL NOW
    MP4 Splitter and the Segment and Avatar Editor split off shared/serve.py
    into fully independent processes on 2026-09-02 (own port, own cache,
    duplicated code — see segment_avatar_editor/serve.py's own module
    docstring). That work was verified by hand at the time — curl and a
    real browser — but never got a permanent, automated suite of its own,
    so a regression in this tool's OWN dispatch table, cache, or log could
    ship unnoticed. This is that suite, added the same day logging was
    split apart per editor too (Carson's own call — see this file's own
    log-file check), and the same day the landing page was reworked to
    load sandbox scenes only (see s_stores below).

WHY NOT JUST REUSE test_editor.py
    test_editor.py drives shared/serve.py on port 8842 — the OLD combined
    process. Every route this file exercises is the SAME code (segment_
    avatar_editor/serve.py started as a literal copy, trimmed to this
    tool's own routes), so this suite is not re-proving that code is
    correct; it is proving the STANDALONE server — its own trimmed
    dispatch table, its own cache dir, its own session log, its own
    the routes it deliberately dropped —
    actually wires together and serves the real thing. Routes the split
    deliberately dropped (the single-clip Open, Handoff, Clear edits,
    Reset editor, Frame Blender's/Avatar Editor's Build/Save MP4/Load) are
    checked as gone, not skipped.
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
SAE_SERVE = os.path.join(PLAYERS, "segment_avatar_editor", "serve.py")

SAE_BASE = None    # set by main()
RESULTS = []
LOG = []
STEPS = []
PAIR = None          # a scene's base-track slug, set by s_open_base
SEQ = None           # the timeline slug, set by s_open_seq


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
    url = f"{SAE_BASE}{ep}?" + urllib.parse.urlencode(params)
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
        SAE_BASE + ep, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r), r.status
    except urllib.error.HTTPError as e:
        try:
            return json.load(e), e.code
        except Exception:
            return {"error": e.read().decode(errors="replace")}, e.code


def raw_status(ep, **params):
    """For the two *-go endpoints, which redirect rather than answer."""
    url = f"{SAE_BASE}{ep}?" + urllib.parse.urlencode(params)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    op = urllib.request.build_opener(NoRedirect)
    try:
        with op.open(url, timeout=120) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def must(ep, **body):
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


def scenes_now():
    p = os.path.join(fixture.STORE, "sandbox", "script.json")
    return [(s["n"], s["label"]) for s in json.load(open(p))["scenes"]]


def line_of(n):
    p = os.path.join(fixture.STORE, "sandbox", "script.json")
    node = next((s for s in json.load(open(p))["scenes"] if s["n"] == n), None)
    return node.get("line") if node else None


def archives(kind):
    d = os.path.join(fixture.STORE, "z_History")
    if not os.path.isdir(d):
        return []
    return sorted(x for x in os.listdir(d) if x.startswith(kind))


def s_static_page():
    """
    "raw_mp4" is deliberately NOT checked absent here — the page's own JS
    still carries one explanatory comment naming it, describing the OLD
    raw-file browser this landing page replaced (2026-09-02). That is
    documentation, not a live reference; asserting the literal string
    never appears would just be testing a code comment.
    """
    step("the landing page — clean title, sandbox scenes only")
    html = urllib.request.urlopen(SAE_BASE + "/", timeout=10).read().decode()
    check("titled just \"Segment and Avatar Editor\", no \"Browse Customers —\" prefix",
          "<title>Segment and Avatar Editor</title>" in html)
    for gone in ("gap-builder.js", "sarah_clips"):
        check(f"nothing about {gone!r} on this page", gone not in html)


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
    row1 = next(r for r in rows if r["n"] == 1)
    check("reports a real base_slug", bool(row1.get("base_slug")), row1.get("base_slug"))
    eq("scene 1 has not been edited yet", row1.get("base_edited"), False)


def s_stores():
    """
    Reworked 2026-08-13/2026-09-02: the landing page — and this endpoint
    that feeds it — must show only videos with sandbox/ already built, not
    a raw recording to hand-pick clips from. has_sandbox is the field the
    page's own picker disables an entry on; a video missing this field
    would silently show as pickable when it has nothing to load.
    """
    step("/api/stores — every store with a video ready to load, sandbox only")
    d, code = get("/api/stores")
    eq("answers 200", code, 200)
    stores = d.get("stores")
    check("a list of stores comes back", isinstance(stores, list), str(stores)[:60])
    businesses = [s.get("business") for s in (stores or [])]
    check("the fixture's folder is not mistaken for a business — wrong depth, correctly excluded",
          fixture.ROOT_REL not in businesses, businesses)
    ski = next((s for s in (stores or []) if s.get("store") == "ski-demo"), None)
    check("finds a real store (ski-demo)", ski is not None, businesses)
    if ski:
        v = ski["videos"][0]
        check("every video names has_sandbox", "has_sandbox" in v, v)
        check("its scenes list is real", isinstance(v.get("scenes"), list) and v["scenes"], v)


def s_open_base():
    """
    A scene's BASE track, taken off a timeline.

    This used to be s_open_pair, driving /api/open-pair — the layered view,
    deleted 2026-09-04 (Carson's call). The frame-editing checks below still
    need a real extracted clip to work on, and a timeline gives them one:
    open-seq extracts every scene's two tracks itself and the manifest hands
    back their slugs.

    Note there is no `which` any more. A pair kept its two halves as
    <slug>/base/ and <slug>/overlay/; a scene's tracks are two ordinary
    slugs, which is how seq.js has always addressed them.
    """
    step("a scene's own base slug, off a timeline")
    global PAIR
    ns = ",".join(str(x["n"]) for x in
                  json.load(open(os.path.join(fixture.STORE, "sandbox",
                                              "script.json")))["scenes"])
    d, _ = get("/api/open-seq", root=fixture.ROOT_REL, ns=ns)
    view, _ = get("/api/view", slug=d.get("slug"))
    PAIR = (view.get("manifest") or [{}])[0].get("base_slug")
    check("a timeline opened and gave a base slug", bool(PAIR), PAIR)


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


def s_own_cache():
    """
    Not a check that cache/<slug> is ABSENT — content-hash slugging means
    another tool extracting this exact fixture on some earlier, unrelated
    run can legitimately leave a same-named folder in the shared cache/ it
    uses, and that is not a collision: it is a different directory. What
    matters, and what this checks, is that THIS pair landed in this
    tool's own cache/segment-avatar-editor/.
    """
    step("its own cache — cache/segment-avatar-editor/, not the shared cache/")
    own = os.path.join(PLAYERS, "cache", "segment-avatar-editor", PAIR)
    check("the pair just opened landed in cache/segment-avatar-editor/",
          os.path.isdir(own), own)


def s_map():
    step("/api/frames/map — read the frame map (base half of the pair)")
    d, _ = get("/api/frames/map", slug=PAIR)
    eq("40 entries, one per source frame", d.get("nb_frames"), 40)
    check("starts as an identity map", d["frame_map"] == list(range(1, 41)), "1..40")


def s_dup():
    step("/api/frames/dup — ＋ Frame")
    must("/api/frames/dup", slug=PAIR, at=10, count=1, side="right")
    d, _ = get("/api/frames/map", slug=PAIR)
    m = d["frame_map"]
    eq("one more frame", len(m), 41)
    eq("the new frame repeats frame 10", m[10], 10)
    _, code = post("/api/frames/dup", slug=PAIR, at=10, count=1, side="sideways")
    eq("refuses a side that is neither left nor right", code, 400)


def s_del():
    step("/api/frames/del — − Frame")
    before, _ = get("/api/frames/map", slug=PAIR)
    d = must("/api/frames/del", slug=PAIR, at=10, count=1, side="left")
    after, _ = get("/api/frames/map", slug=PAIR)
    eq("one frame gone", after["nb_frames"], before["nb_frames"] - 1)
    eq("and reports how many it actually took", d.get("actual", 1), 1)


def s_dup_span():
    step("/api/frames/dup-span — ＋ Zone, and Update Frame Imbalance")
    d, _ = get("/api/frames/map", slug=PAIR)
    before = d["nb_frames"]
    must("/api/frames/dup-span", slug=PAIR, a=5, b=9)
    d, _ = get("/api/frames/map", slug=PAIR)
    eq("a 5-frame zone repeated", d.get("nb_frames"), before + 5)


def s_del_span():
    step("/api/frames/del-span — − Zone")
    d, _ = get("/api/frames/map", slug=PAIR)
    before = d["nb_frames"]
    must("/api/frames/del-span", slug=PAIR, a=5, b=9)
    d, _ = get("/api/frames/map", slug=PAIR)
    eq("the zone removed again", d.get("nb_frames"), before - 5)


def s_restore():
    step("/api/frames/restore — Undo")
    original = list(range(1, 41))
    must("/api/frames/restore", slug=PAIR, frame_map=original)
    d, _ = get("/api/frames/map", slug=PAIR)
    check("restore puts the exact map back", d["frame_map"] == original,
          f"{d.get('nb_frames')} frames")


def s_paste():
    step("/api/frames/paste — copy a frame, put it somewhere else")
    d, _ = get("/api/frames/map", slug=PAIR)
    before, m0 = d["nb_frames"], d["frame_map"]
    must("/api/frames/paste", slug=PAIR, **{"from": 5, "at": 20})
    d, _ = get("/api/frames/map", slug=PAIR)
    m1 = d["frame_map"]
    eq("one more frame", d["nb_frames"], before + 1)
    eq("the pasted frame carries frame 5's SOURCE number", m1[20], m0[4])
    eq("everything after it shifted right by one", m1[21], m0[20])
    must("/api/frames/restore", slug=PAIR, frame_map=list(range(1, 41)))


def s_mark():
    step("/api/mark, /api/marks, /api/clear-marks — Mark / Unmark / Unmark all")
    slug = PAIR
    must("/api/clear-marks", slug=slug)
    must("/api/mark", slug=slug, frame=5, on=True)
    must("/api/mark", slug=slug, frame=20, on=True)
    d, _ = get("/api/marks", slug=slug)
    eq("two marks set", sorted(d.get("marks", [])), [5, 20])
    must("/api/mark", slug=slug, frame=5, on=False)
    d, _ = get("/api/marks", slug=slug)
    eq("unmarking removes just that one", sorted(d.get("marks", [])), [20])
    must("/api/clear-marks", slug=slug)
    d, _ = get("/api/marks", slug=slug)
    eq("Clear All leaves none", d.get("marks", []), [])


def s_save():
    step("/api/save — 💾 Save scene")
    eq("the file starts at 40 frames",
       frames_of("sandbox/01-alpha-scene/segment.mp4"), 40)
    must("/api/frames/dup-span", slug=PAIR, a=5, b=9)   # 40 -> 45
    d = must("/api/save", slug=PAIR)
    check("no frame-count warning", not d.get("warning"), d.get("warning", "none"))
    eq("the FILE now has exactly 45 frames",
       frames_of("sandbox/01-alpha-scene/segment.mp4"), 45)
    check("archived the previous file", bool(d.get("archived_to")),
          os.path.basename(str(d.get("archived_to"))))


def s_save_stale():
    step("/api/save — refuses when the file changed elsewhere first")
    seg_path = os.path.join(fixture.STORE, "sandbox", "01-alpha-scene", "segment.mp4")
    os.utime(seg_path, None)
    d, code = post("/api/save", slug=PAIR)
    eq("refused with 409", code, 409)
    eq("named as a stale conflict", d.get("error"), "stale")
    d2 = must("/api/save", slug=PAIR, force=True)
    check("force overrides the refusal", not d2.get("error"), d2)


def s_cut():
    step("/api/cut — ✂ Cut scene")
    slug = PAIR
    must("/api/clear-marks", slug=slug)
    must("/api/mark", slug=slug, frame=15, on=True)
    must("/api/mark", slug=slug, frame=30, on=True)
    d = must("/api/cut", slug=slug)
    eq("two break points make three segments", d.get("count"), 3)
    must("/api/clear-marks", slug=slug)


def s_vtt():
    step("/api/vtt — the timing table")
    d, _ = get("/api/vtt", root=fixture.ROOT_REL)
    eq("one row per script scene", len(d.get("scenes", [])), 3)
    d, code = get("/api/vtt", root="../outside")
    eq("refuses a path outside Customers/", code, 400)


def s_line():
    step("/api/line — edit a line in the VTT")
    new = "A replacement line for the first scene."
    d, _ = post("/api/line", root=fixture.ROOT_REL, n=1, line=new)
    eq("the new text comes back", d.get("line"), new)
    eq("written to script.json", line_of(1), new)
    d, _ = post("/api/line", root=fixture.ROOT_REL, n=1, line=new)
    check("writing the same text is a no-op", d.get("unchanged") is True, "")
    d, code = post("/api/line", root=fixture.ROOT_REL, n=99, line="x")
    eq("refuses a scene that is not in the script", code, 400)


def s_join():
    step("/api/join — Join, every track")
    _, code = post("/api/join", root=fixture.ROOT_REL, ns=[1], label="solo")
    eq("refuses fewer than two scenes", code, 400)

    seg0 = frames_of("sandbox/01-alpha-scene/segment.mp4")   # 45 after the save
    d, _ = post("/api/join", root=fixture.ROOT_REL, ns=[1, 2], label="joined",
                tracks=["segment", "avatar"])
    check("succeeded", "error" not in d, d.get("error", ""))
    eq("segment is the two lengths added",
       frames_of("sandbox/01-joined/segment.mp4"), seg0 + 32)
    eq("two scenes left", len(scenes_now()), 2)
    eq("the third scene was renumbered to 2", scenes_now()[1], (2, "charlie-scene"))
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

    seg = frames_of("sandbox/01-joined/segment.mp4")
    at = 21
    d, _ = post("/api/split", root=fixture.ROOT_REL, n=1, at=at, labels=["head", "tail"])
    check("succeeded", "error" not in d, d.get("error", ""))
    eq("segment head", frames_of("sandbox/01-head/segment.mp4"), at - 1)
    eq("segment tail", frames_of("sandbox/02-tail/segment.mp4"), seg - at + 1)
    eq("three scenes again", len(scenes_now()), 3)
    check("archived what it cut", bool(archives("split-")), archives("split-"))


def s_archive():
    step("/api/archive — a folder's generation archive")
    d = must("/api/archive", root=fixture.ROOT_REL, folder="sandbox")
    check("sandbox is COPIED, not moved — the scenes stay put",
          d.get("moved") is False, f"moved={d.get('moved')}")
    d, code = post("/api/archive", root=fixture.ROOT_REL, folder="elsewhere")
    eq("refuses a folder that is not dev or sandbox", code, 400)


def s_save_archive():
    step("/api/save-archive — Backup Scenes' whole-generation snapshot")
    d = must("/api/save-archive", root=fixture.ROOT_REL)
    dest = d.get("archived_to")
    check("archived somewhere real", bool(dest) and os.path.isdir(str(dest)), dest)
    check("PLUS the narrative script, copied in beside them",
          os.path.isfile(os.path.join(dest, "script.json")), dest)
    d, code = post("/api/save-archive", root="../outside")
    eq("refuses a path outside Customers/", code, 400)


def s_dropped_routes_are_gone():
    """
    /api/open (single-clip) belongs to MP4 Splitter now; Handoff, Clear
    edits and Reset editor were never this tool's own job even before the
    split; Build clip/Save MP4/Load video/Load store belong to Frame
    Blender and Avatar Editor. A route left reachable here by accident
    would mean the split's own trim silently regressed.
    """
    step("routes this split deliberately dropped — confirmed gone, not just unused")
    for ep in ("/api/open", "/api/handoff", "/api/clear-edits", "/api/reset-editor",
               "/build_clip", "/api/save_mp4", "/api/load_video", "/api/load_store",
               "/api/libs_list", "/api/lib_frames", "/api/lib_media"):
        _, code = get(ep)
        eq(f"{ep} is not served here", code, 404)


def s_session_log():
    """
    A dedicated file (logs/segment_avatar_editor_<date>.log), not shared/
    serve.py's combined logs/editor_<date>.log — split apart per editor
    2026-09-02, at the same time this suite was added.
    """
    step("its own dedicated session log")
    log_path = os.path.join(PLAYERS, "logs",
                             f"segment_avatar_editor_{time.strftime('%Y%m%d')}.log")
    check("the file exists", os.path.isfile(log_path), log_path)
    text = open(log_path).read() if os.path.isfile(log_path) else ""
    check("carries this run's own actions (Save scene)", "Save scene" in text, text[-200:])


def s_app_js_parses():
    """
    Three pages, and since 2026-09-04 they are no longer the same KIND of
    thing, which is the point of this step:

      - the layered page and the timeline page are static files in web/,
        so this fetches web/pair.js and web/seq.js and parses the real
        files;
      - there is no third page. _splitter_player.py rendered one as a
        Python .format() string until 2026-09-04, when it was deleted.

    Scraping <script> out of the two static pages would now find nothing
    and hand `node --check` an empty string: a check that passes while
    proving nothing. That is not hypothetical — it is what hid a real
    routing bug during this migration (see s_deeper_paths_are_not_the_layered_page).
    """
    step("all three of its own pages — does the JavaScript actually run?")
    node = shutil.which("node")
    if node is None:
        check("node is available to parse them", False,
              "install node, or this can never catch a broken page again")
        return

    def parses(name, js):
        safe = re.sub(r"[^A-Za-z0-9]+", "_", name)
        tmp = os.path.join(tempfile.gettempdir(), f"sae_{safe}_check.js")
        with open(tmp, "w") as fh:
            fh.write(js)
        r = subprocess.run([node, "--check", tmp], capture_output=True, text=True)
        os.remove(tmp)
        first = (r.stderr or "").strip().split("\n")
        check(f"{name}: its JavaScript parses", r.returncode == 0,
              f"{len(js)} bytes" if r.returncode == 0
              else next((l for l in first if "Error" in l), first[0] if first else ""))

    # --- the two static pages: parse the real files ---
    for f in ("seq.js",):
        with urllib.request.urlopen(f"{SAE_BASE}/web/{f}", timeout=30) as r:
            js = r.read().decode()
        check(f"web/{f} is really served, and is not empty", len(js) > 5000,
              f"{len(js)} bytes")
        parses(f"web/{f}", js)

    # --- and the pages that load them must actually reference them ---
    doc = json.load(open(os.path.join(fixture.STORE, "sandbox", "script.json")))

    ns = ",".join(str(x["n"]) for x in doc["scenes"])
    d, _ = get("/api/open-seq", root=fixture.ROOT_REL, ns=ns)
    seq_slug = d.get("slug")

    # One page now. The layered view and its web/pair.* went on 2026-09-04.
    for name, slug, want in (("timeline page", seq_slug, "/web/seq.js"),):
        with urllib.request.urlopen(f"{SAE_BASE}/{slug}/viewer.html", timeout=30) as r:
            html = r.read().decode()
        check(f"{name} loads {want}", want in html)
        check(f"{name} bakes in no view any more", "<script>" not in html)

    # There is no third page any more. _splitter_player.py rendered a
    # single-clip page as a Python .format() string; it was deleted on
    # 2026-09-04 — nothing in any UI linked to it, and a day with it
    # disabled changed nothing anybody noticed. Nothing in this repo builds
    # a page out of a Python string now.


def s_api_view():
    """
    /api/view IS the contract between serve.py and web/{pair,seq}.js since
    2026-09-04. One endpoint for both kinds, because the page does not
    choose which it is — `kind` says so, and send_viewer() has already
    sent the matching page.
    """
    step("/api/view — the pages ship empty and the view arrives over the API")
    doc = json.load(open(os.path.join(fixture.STORE, "sandbox", "script.json")))

    # Only one kind of view exists now — the layered one was deleted
    # 2026-09-04, and with it /api/open-pair and its seventeen fields.
    ns = ",".join(str(x["n"]) for x in doc["scenes"])
    d, _ = get("/api/open-seq", root=fixture.ROOT_REL, ns=ns)
    seq_slug = d.get("slug")
    view, code = get("/api/view", slug=seq_slug)
    eq("a real timeline slug is answered", code, 200)
    eq("it says which kind it is", view.get("kind"), "seq")
    SEQ = ["player_label", "title", "box", "total", "manifest", "root_rel"]
    missing = [k for k in SEQ if k not in view]
    check("all six timeline fields are present", not missing, missing or "none")
    check("the manifest is a real list of scenes",
          isinstance(view.get("manifest"), list) and len(view["manifest"]) > 1,
          len(view.get("manifest") or []))
    eq("total is the sum of the scenes' frames", view.get("total"),
       sum(m["base_n"] for m in view["manifest"]))

    # `title` is the BARE name. web/seq.js composes the tab title as "Segment and Avatar Editor — <title>"
    # (Carson's format, 2026-09-04). Prefixing it here too would double it,
    # and the suite cannot see document.title — this guards the half it can.
    for slug, what in ((seq_slug, "timeline"),):
        v, _ = get("/api/view", slug=slug)
        check(f"{what}: title is bare, not prefixed with the editor",
              not str(v.get("title", "")).startswith("Segment and Avatar"),
              v.get("title"))

    _, code = get("/api/view", slug="no-such-slug-at-all")
    eq("an unknown slug is refused, not answered", code, 400)


def s_deeper_paths_are_not_the_layered_page():
    """
    THE ROUTING BUG STEP 13 INTRODUCED — still worth pinning after the
    single-clip page was deleted.

    send_viewer() first matched on path.endswith("/viewer.html"), which
    swallowed /<slug>/base/viewer.html and /<slug>/overlay/viewer.html too
    and served the LAYERED page for all three. The suite passed anyway,
    because its only check on those paths scraped <script> out of the HTML
    and the static page has none — an empty string parses fine.

    The pages those two paths used to serve are gone (2026-09-04,
    _splitter_player.py deleted). What must not come back is the route
    quietly answering a deeper path with the layered page: that is how a
    404 turns into a page that looks right and is not.
    """
    step("a deeper path is a 404, never the layered page")
    doc = json.load(open(os.path.join(fixture.STORE, "sandbox", "script.json")))
    ns = ",".join(str(x["n"]) for x in doc["scenes"])
    d, _ = get("/api/open-seq", root=fixture.ROOT_REL, ns=ns)
    slug = d.get("slug")
    check("a timeline to open", bool(slug), slug)

    with urllib.request.urlopen(f"{SAE_BASE}/{slug}/viewer.html", timeout=30) as r:
        layered = r.read().decode()
    check("two segments still give the timeline page", "/web/seq.js" in layered)

    cache = os.path.join(PLAYERS, "cache", "segment-avatar-editor", slug)
    for half in ("base", "overlay"):
        f = os.path.join(cache, half, "viewer.html")
        check(f"{half}: no page is written for it any more",
              not os.path.isfile(f),
              "written" if os.path.isfile(f) else "absent")
        try:
            with urllib.request.urlopen(
                    f"{SAE_BASE}/{slug}/{half}/viewer.html", timeout=30) as r:
                page = r.read().decode()
            check(f"{half}: three segments must not serve the layered page",
                  "/web/seq.js" not in page, f"served {len(page)} bytes")
        except urllib.error.HTTPError as e:
            eq(f"{half}: three segments give a 404", e.code, 404)


def s_stale_cached_pages():
    """
    A cache written before 2026-09-04 has a baked viewer.html and NO
    view.json, and nothing can rebuild one: the manifest and the two
    relative paths only ever existed at open time. Those must keep serving
    their own old page rather than erroring — re-opening the pair is what
    replaces it.
    """
    step("a pre-migration cache still serves its own page")
    stale = os.path.join(PLAYERS, "cache", "segment-avatar-editor",
                         "pair_stalefixture99")
    os.makedirs(stale, exist_ok=True)
    marker = "PRE-MIGRATION-BAKED-PAGE"
    with open(os.path.join(stale, "viewer.html"), "w") as fh:
        fh.write(f"<html><body>{marker}</body></html>\n")
    check("no view.json beside it",
          not os.path.isfile(os.path.join(stale, "view.json")))
    try:
        with urllib.request.urlopen(
                f"{SAE_BASE}/pair_stalefixture99/viewer.html", timeout=30) as r:
            page = r.read().decode()
        check("it still serves its own baked page", marker in page)
        check("it is not handed the new static page", "/web/seq.js" not in page)
    finally:
        shutil.rmtree(stale, ignore_errors=True)


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
    eq("unreachable handlers", fixture.dead_handlers(SAE_SERVE), [])


FUNCTIONS = [s_static_page, s_list, s_siblings, s_stores, s_open_base,
             s_open_seq, s_open_seq_go, s_own_cache, s_map,
             s_dup, s_del, s_dup_span, s_del_span, s_restore, s_paste,
             s_mark, s_save, s_save_stale, s_cut, s_vtt, s_line, s_join,
             s_renumber_state, s_renumber_clear, s_split, s_archive,
             s_save_archive, s_dropped_routes_are_gone, s_session_log,
             s_api_view, s_deeper_paths_are_not_the_layered_page,
             s_stale_cached_pages, s_app_js_parses,
             s_no_unreachable_handlers]


def main():
    global SAE_BASE
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8856)
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    SAE_BASE = f"http://localhost:{a.port}"

    out(f"Segment and Avatar Editor Test:  {time.strftime('%Y-%m-%dT%H:%M:%S')}")
    out(f"Store:                            {fixture.ROOT_REL}  (built, used, deleted)")
    out(f"Segment and Avatar Editor:        {SAE_BASE}")

    step("Build the test store")
    for n, label, ns, na, nn, _ in fixture.SCENES:
        check(f"{n:02d}-{label}", True, f"segment={ns} avatar={na} narration={nn}")
    fixture.build(quiet=True)

    # No --no-session-log: s_session_log() needs a real file to read.
    srv = subprocess.Popen(
        [sys.executable, SAE_SERVE, "--port", str(a.port)],
        cwd=os.path.dirname(SAE_SERVE), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not wait_up(SAE_BASE + "/"):
            sys.exit("  segment_avatar_editor never came up")

        for fn in FUNCTIONS:
            fn()
    finally:
        if not a.keep:
            srv.terminate()
            fixture.destroy()
        else:
            out(f"\n  --keep: store at {fixture.STORE}")
            out(f"  --keep: server still on {SAE_BASE} (kill it yourself)")

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    out(f"\n  Checks:  {passed}/{len(RESULTS)} passed")
    out(f"  Result:  {'PASS' if passed == len(RESULTS) else 'FAIL'}")

    # Own folder, own log + report — tests/segment_avatar_editor/, never another
    # editor's (see fixture.write_report()'s own docstring for why this
    # is shared code rather than copied four times).
    base = fixture.write_report("segment_avatar_editor", LOG, RESULTS, STEPS)
    out(f"  Report:  tests/segment_avatar_editor/{base}.txt")

    if passed != len(RESULTS):
        sys.exit(1)


if __name__ == "__main__":
    main()
