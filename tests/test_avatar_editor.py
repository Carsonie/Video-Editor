#!/usr/bin/env python3
"""
Exercise Avatar Editor's own endpoints — Load, Save Scene, Build, Save MP4 —
against the same disposable store test_editor.py builds.

    python3 tests/test_avatar_editor.py            # build, run, tear down
    python3 tests/test_avatar_editor.py --keep      # leave the store to poke at

WHY A SEPARATE FILE, NOT MORE STEPS IN test_editor.py
    Avatar Editor is a second, independent server (avatar_editor/serve.py, its
    own port), standalone since 2026-09-02 — it used to PROXY three of its
    endpoints to the main editor (shared/serve.py) instead of reimplementing
    them, but no longer does; its own save_scene()/undo_scene()/stores()/
    siblings() now call the main editor's pure helper functions directly as
    a plain Python module. This suite still runs both servers because the
    fixture and some checks share test_editor.py's own conventions, not
    because Avatar Editor itself needs the main editor up. Keeping this
    separate means neither file has to bend its own shape to accommodate
    the other.

WHAT THIS PROVES THAT test_editor.py CANNOT
    Not whether /api/save or /api/siblings work in isolation — that suite
    already covers them exhaustively. This proves the PROXY relays them
    correctly (status code, error body, and all) from a second process, and
    exercises the endpoints that exist ONLY here: /api/libs_list and
    /api/lib_frames, the Gap Builder's own backend for browsing and
    extracting sarah_clips/libs.

    /build_clip and /api/save_mp4 — this tool's own frame-by-frame
    overlay+base COMBINE and build-mp4 flow — were removed 2026-09-02
    (Carson's call: that job stays in Frame Blender; this tool keeps only
    what edits the avatar overlay itself). Their tests went with them; see
    tests/test_frame_blender.py for the mirror-image change, where the
    opposite half — the Gap Builder — was the one removed instead.
"""
import argparse
import ast
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
MAIN_SERVE = os.path.join(PLAYERS, "shared", "serve.py")
AE_SERVE = os.path.join(PLAYERS, "avatar_editor", "serve.py")

MAIN_BASE = None    # set by main()
AE_BASE = None
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


def fb_get(ep, **params):
    url = f"{AE_BASE}{ep}?" + urllib.parse.urlencode(params)
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
        AE_BASE + ep, data=json.dumps(body).encode(),
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
    step("/api/load_store — Avatar Editor's Load, proxied to /api/siblings")
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



# A real, already-committed store's own scene, used by s_load_picker and
# s_stateless below — REAL_SEG/REAL_AV are never written to, only read from,
# so this is safe to run against live customer data.
REAL_STORE_REL = ("Rentify Demos Corp/bike-demo/help-videos/videos/"
                   "01-first-time-ordering")
REAL_SEG = f"{REAL_STORE_REL}/sandbox/01-login/segment.mp4"
REAL_AV = f"{REAL_STORE_REL}/sandbox/01-login/avatar.webm"

# ski-demo is the one real store this suite exercises Load/lib_frames
# against — s_load_picker borrows bike-demo for the same reason. Its OWN
# sarah_clips/libs/ was archived to sarah_clips/z_history/<ts>/libs/ on
# 2026-09-03 (Carson's own call: work off the common Sarah/ library from
# here on, not a per-store copy) — so the two frame-extraction tests below
# borrow the COMMON library instead, which is where real content actually
# lives now. Read-only either way: /api/lib_frames only ever EXTRACTS into
# cache/, it never writes into Customers/ or Sarah/ itself.
SKI_STORE_REL = "Rentify Demos Corp/ski-demo/help-videos/videos/01-first-time-ordering"
SKI_SEG = f"{SKI_STORE_REL}/sandbox/01-intro-and-login/segment.mp4"
SKI_AV = f"{SKI_STORE_REL}/sandbox/01-intro-and-login/avatar.webm"
COMMON_LIB_CLIP = "idle/sarah-idle-10s-alpha.webm"
COMMON_LIB_STILL = "stills/sarah-rest-pose-corner-300-alpha.png"


def s_libs_list_paths():
    """
    ski-demo's OWN sarah_clips/libs/ was archived away on 2026-09-03
    (Carson's own call — see the SKI_STORE_REL comment above): work off
    the common Sarah/ library from here on, not a per-store copy. What's
    left in a store's own sarah_clips/ after that is loose leftover files
    (openings, closings, one-off tests, ...) with no fixed taxonomy of
    their own — /api/libs_list?base=&overlay= shows exactly those now,
    under one plain "sarah_clips" group, EXCEPT z_history/ itself, which
    stays out of the browse on purpose — it's where the archived material
    actually lives, not something to pick clips from.
    """
    step("/api/libs_list — ski-demo's own sarah_clips/, its loose leftovers")
    d, code = fb_get("/api/libs_list", base=SKI_SEG, overlay=SKI_AV)
    eq("200", code, 200)
    check("root points at sarah_clips/ itself, not .../libs",
          (d.get("root") or "").endswith("sarah_clips"), d.get("root"))
    eq("exactly one group: the loose files", len(d.get("groups", [])), 1)
    group = d["groups"][0]
    eq("...named plainly", group.get("folder"), "sarah_clips")
    files = group.get("files", [])
    check("finds the real loose files", len(files) > 0, len(files))
    check("every file has a real, resolvable path",
          all(os.path.isfile(os.path.join(fixture.CUSTOMERS, f["path"])) for f in files),
          files[:1])
    check("every entry is tagged source='store'",
          all(f.get("source") == "store" for f in files), files[:1])
    names = {f["name"] for f in files}
    check("a real leftover clip shows up", "TRACK_front_sarah.webm" in names, sorted(names))
    check("z_history/ is never browsed — it's the archive, not a source",
          not any("z_history" in f["path"] for f in files), names)

    z = os.path.join(fixture.CUSTOMERS, SKI_STORE_REL, "sarah_clips", "z_history")
    check("...and it's genuinely still there, just out of the browse", os.path.isdir(z), z)
    libs_dirs = [os.path.join(z, d2, "libs") for d2 in os.listdir(z)] if os.path.isdir(z) else []
    check("...with the archived library's real files still in it",
          any(os.path.isdir(p2) and os.listdir(p2) for p2 in libs_dirs), libs_dirs)


def s_common_library():
    """
    Sarah's COMMON library — Sarah/ at the repo root, the same across every
    store (Carson's own split, 2026-09-03; see Sarah/README.md). A second,
    independent /api/libs_list?source=common, alongside the per-store one
    above rather than replacing it — a store's own sarah_clips/libs/ still
    holds the clips DEVELOPED for that one video.

    Also proves the one real security boundary this split needed: Sarah/
    sits BESIDE Customers/, not inside it, so /api/lib_frames and
    /api/lib_media have to resolve `path` against a DIFFERENT root
    depending on `source` — get that wrong in either direction and a
    request either 400s on a real file or, worse, reads outside the root
    it was supposed to be confined to.
    """
    step("Sarah's common library — /api/libs_list?source=common")
    d, code = fb_get("/api/libs_list", source="common")
    eq("200", code, 200)
    eq("root is Sarah", d.get("root"), "Sarah")
    files = [f for g in d.get("groups", []) for f in g.get("files", [])]
    check("finds real files", len(files) > 0, len(files))
    check("every entry is tagged source='common'",
          all(f.get("source") == "common" for f in files), files[:1])
    sample = next(f for f in files if f["name"] == "sarah-rest-pose-corner-300-alpha.png")
    check("its path is real, resolved against Sarah/ — not Customers/",
          os.path.isfile(os.path.join(fixture.REPO, "Sarah", sample["path"])),
          sample["path"])
    present = {g["folder"]: len(g["files"]) for g in d.get("groups", [])}
    check("same 7-folder taxonomy as the store's own library",
          set(present) >= {"openings", "gap-fillers", "idle", "stills",
                            "transitions", "sound_bits", "closings"}, present)
    # The 11 sound bits copied in from ski-demo — a real bug, caught live:
    # they first landed one level deeper (sound_bits/HeyGen-originals/),
    # invisible to a listing that only walks ONE level down. Flattened to
    # match every other folder; this guards it staying that way.
    check("sound_bits are flat, not nested — the folder walk is one level deep",
          present.get("sound_bits", 0) >= 11, present.get("sound_bits"))

    step("source=common resolves against Sarah/, never against Customers/")
    d2, code2 = fb_get("/api/lib_frames", source="common", path=sample["path"])
    eq("200", code2, 200)
    eq("kind is still", d2.get("kind"), "still")
    # The exact escape a naive "just reuse safe_join" would have allowed:
    # a relative climb OUT of Sarah/ and back into Customers/.
    d3, code3 = fb_get("/api/lib_frames", source="common",
                        path=f"../Customers/{fixture.ROOT_REL}")
    eq("...a path escaping Sarah/ is refused, not resolved", code3, 400)
    # And the reverse: the STORE endpoint must never accept a Sarah/-only
    # path just because source was left off (defaults to 'store').
    d4, code4 = fb_get("/api/lib_frames", path=sample["path"])
    eq("...and Sarah/'s own paths are foreign to the store root", code4, 400)

    step("source=common media — the real bytes, not just metadata")
    url = f"{AE_BASE}/api/lib_media?source=common&path=" + urllib.parse.quote(
        next(f["path"] for f in files if f["name"].endswith(".webm") and f.get("has_audio")))
    with urllib.request.urlopen(url, timeout=30) as r:
        eq("200", r.status, 200)
        check("real bytes came back", len(r.read(1024)) > 0)


def s_libs_group_order():
    """
    LIBS_GROUP_ORDER in avatar_editor/serve.py names the fixed display
    order for sarah_clips/libs/'s subfolders — and, per Carson's own
    direction (2026-09-03), those 7 names are also the top-level Sarah/
    folder's own 7 subfolders (Sarah/README.md's reference stash), so a
    store's own library and Sarah's reference library agree on what a
    "kind" of clip is called. Checked against Sarah/ ON DISK rather than a
    second hardcoded list, so this fails the moment the two drift apart in
    either direction — a folder added to one and not the other.
    """
    step("sarah_clips/libs/'s 7 folder names line up with Sarah/'s own")
    serve_src = open(os.path.join(fixture.REPO, "avatar_editor", "serve.py")).read()
    m = re.search(r'LIBS_GROUP_ORDER = (\[[^\]]+\])', serve_src)
    check("LIBS_GROUP_ORDER is defined", m is not None)
    order = ast.literal_eval(m.group(1)) if m else []

    sarah_dir = os.path.join(fixture.REPO, "Sarah")
    on_disk = sorted(n for n in os.listdir(sarah_dir)
                      if os.path.isdir(os.path.join(sarah_dir, n)) and not n.startswith("."))
    check("exactly 7 folders", len(order) == 7, order)
    eq("the same 7 names as Sarah/ itself", sorted(order), on_disk)

    # And the real endpoint honours that order for whichever of the 6
    # ski-demo actually has files in — closings/ has none there today, so
    # this checks the ORDER of what's present, not that all 6 show up.
    d, code = fb_get("/api/libs_list", base=SKI_SEG, overlay=SKI_AV)
    eq("200", code, 200)
    present = [g["folder"] for g in d.get("groups", [])]
    ranked = sorted(present, key=lambda f: order.index(f) if f in order else len(order))
    eq("groups come back in LIBS_GROUP_ORDER's order", present, ranked)


def s_lib_frames_clip():
    """
    /api/lib_frames on a real clip — the Frame Selector's own backend.
    Goes through the SAME extraction every OVERLAY track already uses
    (alpha_png=True, since every file in this library is a transparent
    Sarah render), so its frames must be servable the identical way.
    """
    step("/api/lib_frames — a real .webm clip")
    d, code = fb_get("/api/lib_frames", source="common", path=COMMON_LIB_CLIP)
    eq("200", code, 200)
    eq("kind is clip", d.get("kind"), "clip")
    check("has a real, multi-frame count", isinstance(d.get("n"), int) and d["n"] > 1, d.get("n"))
    check("names a real cache slug", bool(d.get("slug")), d.get("slug"))
    eq("frames are alpha PNGs, like any overlay track", d.get("ext"), ".png")

    url = f"{AE_BASE}/{d['slug']}/frames/frame_00001{d['ext']}"
    r = urllib.request.urlopen(url, timeout=10)
    eq("frame 1 is really servable at that URL", r.status, 200)

    _, code2 = fb_get("/api/lib_frames")
    eq("a missing path is refused", code2, 400)
    _, code3 = fb_get("/api/lib_frames", source="common", path="not/a/real/file.webm")
    eq("a path that isn't a real file is refused, not a crash", code3, 400)


def s_lib_frames_still():
    """
    A still has no frames to extract — it gets a hand-built ONE-frame cache
    entry instead (see lib_frames()'s own docstring), so the page can
    address it through the exact same slug+frame URL scheme as a real
    clip, with no second code path in app.js just for stills.
    """
    step("/api/lib_frames — a still image gets a one-frame cache entry")
    d, code = fb_get("/api/lib_frames", source="common", path=COMMON_LIB_STILL)
    eq("200", code, 200)
    eq("kind is still", d.get("kind"), "still")
    eq("exactly one frame", d.get("n"), 1)
    eq("keeps its own PNG extension", d.get("ext"), ".png")

    url = f"{AE_BASE}/{d['slug']}/frames/frame_00001{d['ext']}"
    r = urllib.request.urlopen(url, timeout=10)
    eq("that one frame is really servable", r.status, 200)

    # Asking again must reuse the same cache entry, not duplicate or rebuild it.
    d2, code2 = fb_get("/api/lib_frames", source="common", path=COMMON_LIB_STILL)
    eq("asking again still answers 200", code2, 200)
    eq("same slug both times", d2.get("slug"), d.get("slug"))


def s_working_clips():
    """
    Working Clips, and the two things that read and write it: Save to
    Working Clips in the Gap Builder Menu, and Replace Selected in the
    Frame Selector Menu. Plus the Audio Menu's own Clear All.

    HTTP cannot press a button, so what is asserted here is the WIRING and
    the SHAPE — every control present with the id its handler looks up, the
    three sections named, and the handful of rules that are easy to lose in
    a later edit and expensive to notice by hand.
    """
    step("Working Clips — the panel, saving into it, and replacing from it")
    html = urllib.request.urlopen(AE_BASE + "/", timeout=10).read().decode()
    # gap-builder.js was split on 2026-09-04. The Audio Menu's Clear All and
    # the three Play buttons live in gap-menu.js; this panel's own Save to /
    # Replace Selected wiring moved into working-clips.js beside the module
    # it drives. Both are read here, joined, so an absence assertion still
    # covers wherever the code actually ended up.
    gb = "\n".join(
        urllib.request.urlopen(AE_BASE + "/web/" + f, timeout=10).read().decode()
        for f in ("gap-menu.js", "working-clips.js", "library.js",
                  "clip-gap-builder.js"))

    # Every control this panel needs must EXIST in the served page, with
    # the id its handler looks up. That is a real contract between the
    # HTML and the JS, and breaking it breaks the panel — so it is worth
    # a check even though it is read out of the page's text.
    for el in ("wcGroups", "wcStatus", "gmSaveTarget", "gmReplaceSelected",
               "gmAudioClearAll"):
        check(f"the page carries {el}", f'id="{el}"' in html)
    check("the panel reuses the library's own classes, not a second layout",
          'class="panel libpanel wcpanel"' in html)

    # ONE control: picking a section IS the save. The absence half of this
    # is the part worth asserting — a second Save button coming back is a
    # regression nothing else would catch.
    check("Save to: is itself the button",
          'class="gapMenuBtn gapMenuRow" id="gmSaveToWorking"' in html)
    check("...and there is no second Save button",
          html.count('id="gmSaveToWorking"') == 1
          and "Save to Working Clips</button>" not in html)
    for value in ("idle", "sound_bits", "transitions"):
        check(f"...offers {value}", f'value="{value}"' in html)

    # window.prompt/confirm are blocked in some contexts, cannot be styled
    # and cannot be tested. This asserts we did not quietly go back to
    # them — an ABSENCE check, which nothing else in the suite covers.
    check("the name is asked for in the page's own modal, never window.prompt",
          "window.prompt(" not in gb and "= prompt(" not in gb)

    # Clear All must not untick the library: that would empty the Frame
    # Selector too, which is a different button's job. Destroying a
    # collection by surprise is exactly the kind of regression worth an
    # absence check.
    clear_block = gb.split("gmAudioClearAll.onclick")[-1].split("// ── the three Play")[0]
    check("Audio Menu's Clear All unticks nothing", "PICKED" not in clear_block)


def s_common_library_wiring():
    """
    The client half of the common-library split (2026-09-03): a second
    library panel beside the store's own, feeding the SAME Frame Selector /
    Clip-Gap Builder / Audio Menu — Carson's own call, so a build can mix
    clips from both. HTTP cannot tick a checkbox, so what's asserted here
    is the WIRING: the second panel exists with its own elements, and every
    later request a checked clip triggers carries the `source` that says
    which root to resolve it against.
    """
    step("the common library panel exists and is wired through, not bolted on")
    html = urllib.request.urlopen(AE_BASE + "/", timeout=10).read().decode()

    # The element contract: every id the JS looks up must exist in the
    # served page. Breaking one breaks the panel silently.
    for el in ("libGroupsCommon", "libStatusCommon", "libHeaderStore",
               "libHeaderVideo"):
        check(f"the page carries {el}", f'id="{el}"' in html)
    check("it is a real second panel, not a rename of the store's own",
          html.count('id="libGroups"') == 1 and html.count('id="libGroupsCommon"') == 1)

    # Both spinners must ship HIDDEN — a spinner that starts visible spins
    # forever on a page that never fetched.
    for el in ("libSpinner", "libSpinnerCommon"):
        check(f"{el} exists and starts hidden", f'id="{el}" hidden' in html)

    # Labels that were deliberately REMOVED. Their absence is the whole
    # assertion, and nothing else in the suite would notice them coming
    # back.
    check("no static 'sarah_clips/libs' heading left",
          "sarah_clips/libs</h3>" not in html)
    check("the common panel's h3 is just Sarah",
          "<h3>Sarah</h3>" in html and "Sarah/ (common)" not in html)


def s_tooltips():
    """
    Every control on the page explains itself after a 3-second hover.

    The two things worth asserting from here: that no control is MISSING a
    description (the whole point — one silent button is the one you have to
    guess at), and that the description is read from the element's own
    `title` at hover time rather than copied at load, because several of
    them are rewritten as the page works.
    """
    step("tooltips — every control says what it does, after 3 seconds")
    html = urllib.request.urlopen(AE_BASE + "/", timeout=10).read().decode()

    # The 3-second delay, the suppression of the browser's own tooltip, the
    # click-cancels behaviour, the keep-it-inside-the-window maths: all of
    # it is browser behaviour, none of it is reachable over HTTP. The
    # source-text greps that used to assert those were asserting spelling —
    # "const DELAY = 3000;" passes whether or not a tooltip ever appears.
    # Removed 2026-09-03; README-CODE-CLEANUP-PLAN.md Step 7.
    #
    # THIS is the check worth having, and it is a genuine contract rather
    # than a grep for an identifier: every control written into the page
    # must carry a description, because one silent button is the one you
    # have to guess at. It reads the served HTML and finds any control
    # that has neither a title of its own nor a pointer to another
    # element's.
    import re as _re
    tags = _re.findall(r"<(?:button|select)\b[^>]*>", html)
    silent = [t for t in tags if "title=" not in t and "data-tip-from" not in t]
    check("no control in the page is left without a description",
          not silent, silent[:3] if silent else f"{len(tags)} controls, all described")
    check("...and there are really that many controls to describe",
          len(tags) >= 20, len(tags))
    # The Save to: dropdown borrows the row's, because the row is the button.
    check("the dropdown borrows its row's description",
          'data-tip-from="gmSaveToWorking"' in html)


def s_stateless():
    """
    The restructure's actual promise: this server remembers no scene. A
    scene-acting call that names no pair must be refused, no matter what
    was opened a moment ago — that is what makes Clear real and what stops
    two browser tabs fighting over one remembered pair.
    """
    step("stateless — a call that names no pair is refused, even right after opening one")
    fb_get("/api/open_pair", base=REAL_SEG, overlay=REAL_AV)   # open something first
    for ep in ("/api/libs_list",):
        d, code = fb_get(ep, n=10)
        eq(f"{ep} refuses without a pair", code, 400)
        check(f"{ep} says why", "base is required" in str(d.get("error", "")), d)


def s_static_page():
    step("the page ships EMPTY — no scene baked into the HTML")
    html = urllib.request.urlopen(AE_BASE + "/", timeout=10).read().decode()
    check("says nothing is loaded", "nothing loaded" in html, html[:0] or "ok")
    for gone in ("base_slug", "over_slug", "01-opening-with-login"):
        check(f"no {gone} baked in", gone not in html)
    # THE LOAD ORDER IS A BEHAVIOUR CONTRACT, and this is what pins it.
    #
    # None of these files is wrapped in an IIFE — they share ONE flat
    # top-level scope, so a `const` used at load time must be declared in a
    # file loaded earlier. gap-builder.js was split into five of them on
    # 2026-09-04, and the order below is the order that one file ran in.
    #
    # Match the <script src> attributes, never a bare filename — the
    # comment above these tags names every file too, and matching that
    # measures nothing.
    ORDER = ["frame-player.js",      # owns the Play buttons; wire.js needs it
             "gap-state.js",         # LIB / BUILDER / SHARED, before any mutator
             "library.js",
             "clip-gap-builder.js",
             "gap-menu.js",          # withActiveFlash + the gm* elements
             "wire.js",              # FramePlayer.configure(...) — needs all above
             "working-clips.js",     # reads BUILDER.frames; needs gap-menu.js
             "tooltips.js",
             "app.js"]               # its bootstrap calls into library.js
    pos = {f: html.find(f'src="/web/{f}"') for f in ORDER}
    missing = [f for f, p_ in pos.items() if p_ == -1]
    check("every script the page needs is named", not missing, missing or "all nine")
    seq = [pos[f] for f in ORDER]
    check("they are named in the required order", seq == sorted(seq),
          [f for f in ORDER if pos[f] != -1])

    # The old single file must be gone, not merely unreferenced — a stale
    # copy left on disk would keep being served and quietly shadow nothing,
    # while the reader assumes it is still the source of truth.
    try:
        urllib.request.urlopen(AE_BASE + "/web/gap-builder.js", timeout=10)
        check("gap-builder.js is gone (it was split)", False, "still served")
    except urllib.error.HTTPError as e:
        eq("gap-builder.js is gone (it was split)", e.code, 404)

    tt_pos = pos["tooltips.js"]
    check("tooltips.js is on the page", tt_pos > -1, tt_pos)
    for asset, ctype in ([(f"/web/{f}", "javascript") for f in ORDER]
                         + [("/web/app.css", "css")]):
        r = urllib.request.urlopen(AE_BASE + asset, timeout=10)
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
    ORDER = ["frame-player.js", "gap-state.js", "library.js",
             "clip-gap-builder.js", "gap-menu.js", "wire.js",
             "working-clips.js", "tooltips.js", "app.js"]
    src = {}
    for f in ORDER:
        src[f] = urllib.request.urlopen(AE_BASE + "/web/" + f, timeout=10).read().decode()

    def parses(name, text):
        safe = re.sub(r"[^A-Za-z0-9]+", "_", name)
        tmp = os.path.join(tempfile.gettempdir(), f"ae_{safe}_check.js")
        with open(tmp, "w") as fh:
            fh.write(text)
        r = subprocess.run([node, "--check", tmp], capture_output=True, text=True)
        os.remove(tmp)
        first = (r.stderr or "").strip().split("\n")
        check(f"{name} parses", r.returncode == 0,
              f"{len(text)} bytes" if r.returncode == 0
              else next((l for l in first if "Error" in l), first[0] if first else ""))

    for f in ORDER:
        parses(f, src[f])

    # AND CONCATENATED, in load order. This is the check that matters most
    # now there are nine files instead of two: they share one flat scope, so
    # two files that each parse perfectly alone can still declare the same
    # `const` and throw the moment the page loads them together. Nothing
    # else in this suite can see that.
    parses("all nine together (load order)",
           "\n".join(src[f] for f in ORDER))


def s_original_audio_stack():
    """
    The Audio Menu's Play walks a STACK, and the stack is maintained by the
    checkbox events rather than worked out when Play is pressed. None of
    that is reachable over HTTP, so what is asserted here is the WIRING —
    the four joins that, if any one of them were dropped, would leave the
    button silently playing the wrong thing or nothing at all. Each one has
    already been the actual bug once.
    """
    step("structure — the players' own elements and their isolation")
    fp = urllib.request.urlopen(AE_BASE + "/web/frame-player.js", timeout=10).read().decode()
    html = urllib.request.urlopen(AE_BASE + "/", timeout=10).read().decode()

    # WHAT THIS STEP IS, AND IS NOT.
    # What each Play button actually PLAYS — the stack's order, that a tick
    # mid-run extends rather than kills a run, that the picture steps with
    # the voice — is browser behaviour. This suite drives HTTP. There is no
    # honest way to assert any of it from here, and the ~40 source-text
    # greps that used to sit in this step did not do so: they asserted that
    # a line of JavaScript was spelled a certain way, which passes when the
    # feature is broken and fails when a variable is renamed. Removed
    # 2026-09-03; see README-CODE-CLEANUP-PLAN.md Step 7.
    #
    # What survives is the part that IS a real contract and IS checkable:
    # the elements each engine looks up must exist in the served page, and
    # each panel must reach only its own viewer.

    # Every panel has its own <video>, its own name label, its own speed
    # dropdown. A missing id here breaks that panel silently.
    for el in ("fsPlayer", "fsVideo", "fsName", "fsRate",
               "gbPlayer", "gbVideo", "gbName", "gbRate",
               "soundBitPlayer", "soundBitVideo"):
        check(f"the page carries {el}", f'id="{el}"' in html)

    # The two hidden ones carry the VOICE only; the picture is the panel's
    # own frame viewer. A second visible viewer appearing is a regression.
    for vid in ("fsVideo", "gbVideo"):
        check(f"{vid} is the voice only, never a second viewer",
              f'<video id="{vid}" playsinline hidden>' in html)

    # THE ONE INVARIANT WORTH A STRUCTURAL CHECK. A panel's Play button
    # must move that panel and nothing else. This has been broken twice —
    # a frame stepper driven by the Audio Menu that left the Frame Selector
    # parked on frame 327 of 482, and one shared <video> that let the Frame
    # Selector's Play take over the Audio Menu's previewer. Both were found
    # by eye, not by a test. Counting the call sites is a blunt instrument,
    # but it fails loudly if a second caller appears, which is exactly the
    # regression in question.
    fs_block = fp.split("const FrameSelector = ")[-1].split("const GapBuilder = ")[0]
    gb_block = fp.split("const GapBuilder = ")[-1].split("const Players = ")[0]
    check("only the Frame Selector moves the Frame Selector's viewer",
          fp.count("LibSources.showFrame(") == 1
          and "LibSources.showFrame(" in fs_block)
    check("only the Clip-Gap Builder moves the Clip-Gap Builder's viewer",
          fp.count("LibSources.builderShow(") == 1
          and "LibSources.builderShow(" in gb_block)
    # The shared engine must stay ignorant of frames entirely — the moment
    # it knows about a viewer, every panel can move every other panel.
    check("the engine itself knows nothing about frames",
          "showFrame" not in fp.split("const FramePlayer = ")[-1]
                              .split("const OriginalAudio = ")[0])


def s_load_order_forward_refs():
    """
    Does any file USE, at load time, a name only DECLARED in a later one?

    THE BUG THIS EXISTS FOR, found the day the split was made. timeline.js
    does, at its top level:

        document.getElementById('tlLoadBtn').onclick = pickStores;

    and pickStores() lives in another file. Inside ONE script that works —
    function declarations hoist. Across two <script> tags they do not: the
    earlier script runs first and reads a name that does not exist yet, and
    the page threw "pickStores is not defined" on every load.

    Nothing else could see it. Every check in this suite drives HTTP, so the
    server answered perfectly while the page was broken; `node --check`
    parses each file and the concatenation, and both are valid JavaScript —
    the failure is at RUNTIME, in load order, not in syntax.

    The heuristic: collect every top-level DECLARATION per file and every
    top-level STATEMENT that is not one, then flag a statement referencing a
    name declared in a file loaded later. It is deliberately conservative —
    it only looks at the real top level, so a name used inside a function
    body (which runs long after every file has loaded) is correctly ignored.
    """
    ORDER = ["frame-player.js", "gap-state.js", "library.js",
             "clip-gap-builder.js", "gap-menu.js", "wire.js",
             "working-clips.js", "tooltips.js", "app.js"]
    step("load order — no file reads a name declared in a later one")
    DECL = re.compile(r"^(?:async\s+)?(?:function|const|let|var|class)\s+([A-Za-z_$][\w$]*)")
    pat = re.compile(rf"^{' ' * 0}(\S.*)$")

    declared, stmts = {}, []
    for i, f in enumerate(ORDER):
        text = urllib.request.urlopen(AE_BASE + "/web/" + f, timeout=10).read().decode()
        for line in text.splitlines():
            m = pat.match(line)
            if not m or m.group(1).startswith("//"):
                continue
            s = m.group(1)
            d = DECL.match(s)
            if d:
                declared.setdefault(d.group(1), i)
            else:
                stmts.append((i, f, s))

    check("the files really were read", len(declared) > 10, f"{len(declared)} names")
    bad = []
    for i, f, s in stmts:
        for ident in set(re.findall(r"\b([A-Za-z_$][\w$]*)\b", s)):
            j = declared.get(ident)
            if j is not None and j > i:
                bad.append(f"{f} uses `{ident}` from {ORDER[j]}")
    check("no file reads a later file's declaration at load time",
          not bad, bad[:3] or "none")


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
    eq("unreachable handlers", fixture.dead_handlers(AE_SERVE), [])


def s_timeline_load_buttons():
    """
    Timeline Scenes has TWO load buttons since 2026-09-04, and they do very
    different things:

      Load Sandbox         the store's whole scene list, from sandbox/
      Load Frame Selector  the OPEN scene's avatar track, into the Frame
                           Selector's own collection

    The second is pure front-end — openPair() already put over_slug, over_n
    and over_ext on SCENE, so no endpoint was added for it. That means the
    only thing this suite can check is the CONTRACT between the HTML and the
    JS: both ids must exist, because a handler that looks up a missing id
    dies silently and takes the panel with it. Whether the button actually
    fills the Frame Selector is browser behaviour, and was verified there —
    482 frames from ski-demo's 01-intro-and-login, the frame URL serving 200,
    and a second press refusing to stack the same scene twice.
    """
    step("Timeline Scenes — its two load buttons")
    html = urllib.request.urlopen(AE_BASE + "/", timeout=10).read().decode()
    for el in ("tlLoadBtn", "tlLoadFsBtn", "tlClearBtn"):
        check(f"the page carries {el}", f'id="{el}"' in html)
    check("the old bare 'Load' label is gone — it never said from WHERE",
          ">&#128193; Load<" not in html)
    check("Load Sandbox says which folder it reads",
          "Load Sandbox" in html and "sandbox/" in html)
    check("Load Frame Selector is on the page", "Load Frame Selector" in html)

    js = urllib.request.urlopen(AE_BASE + "/web/app.js", timeout=10).read().decode()
    check("its handler is wired", "tlLoadFsBtn" in js)
    # The one thing that would break it silently rather than loudly: a scene
    # clip carries source:'scene', which is neither of Sarah's two libraries,
    # so /api/lib_media could never serve it. has_audio:false is what keeps
    # it out of the audio stack, which is the only code path that would ask.
    check("a scene clip is marked has_audio:false, keeping it out of the "
          "audio stack that would call /api/lib_media with source:'scene'",
          "has_audio: false" in js)


def s_own_cache():
    """
    Its own cache — cache/avatar-editor/, not the shared cache/.

    MP4 Splitter and the SAE each got their own extraction cache at the
    2026-09-02 split; Avatar Editor and Frame Blender were missed and
    shared <repo>/cache/ until 2026-09-04. Two tools writing frames into
    one folder means one tool's Clear can throw away frames the other is
    still using, and neither can be reasoned about alone.

    There is an ordering hazard behind this that no test would otherwise
    see: shared/serve.py calls editor_base's use_cache(<repo>/cache) at
    ITS import time, and avatar_editor/serve.py imports it. Setting this
    tool's cache before that line would be silently undone — the server
    would come up looking correct and extract into the wrong folder.
    """
    # LAST in FUNCTIONS on purpose: these checks share state in the order the
    # work happens, and opening a pair up front made the save step see the
    # file as "stale" and fail with a 409.
    step("its own cache — cache/avatar-editor/, not the shared cache/")
    d, code = fb_get("/api/open_pair", base=REAL_SEG, overlay=REAL_AV)
    check("a pair opened", code == 200, code)
    slug = (d or {}).get("base_slug") or (d or {}).get("slug")
    check("it reported a slug", bool(slug), slug)

    own = os.path.join(PLAYERS, "cache", "avatar-editor")
    check("the frames landed in cache/avatar-editor/",
          bool(slug) and os.path.isdir(os.path.join(own, slug)),
          os.path.join(own, str(slug)))

    # The hazard itself, asserted directly: the module's own CACHE constant
    # and the one editor_base will actually extract into must be the same
    # folder. They are set on different lines, and only their order keeps
    # them equal.
    sys.path.insert(0, PLAYERS)
    from avatar_editor import serve as ae_serve       # noqa: E402
    eq("serve.py's CACHE is this tool's own",
       os.path.basename(ae_serve.CACHE), "avatar-editor")
    eq("editor_base will extract into that same folder",
       ae_serve.build_mod.CACHE, ae_serve.CACHE)

    # The third one, and the one that actually broke. This tool CALLS
    # shared/serve.py's pure helpers rather than copying them, and two of
    # them — resolve_outdir() and frame_count() — read that module's own
    # CACHE. Leave it pointing at <repo>/cache and extraction goes to one
    # folder while every lookup goes to another: Save then fails with
    # "changed on disk since this was loaded here", a staleness error about
    # a file nobody touched.
    eq("shared/serve.py's borrowed helpers look in that folder too",
       ae_serve.main_serve.CACHE, ae_serve.CACHE)


FUNCTIONS = [s_static_page, s_app_js_parses, s_load_order_forward_refs, s_original_audio_stack, s_working_clips, s_common_library_wiring, s_tooltips, s_stateless, s_load_picker, s_load_store,
             s_save_scene_proxy,
             s_libs_list_paths, s_common_library, s_libs_group_order,
             s_lib_frames_clip, s_lib_frames_still,
             s_no_unreachable_handlers,
             s_timeline_load_buttons, s_own_cache]


def main():
    global MAIN_BASE, AE_BASE
    ap = argparse.ArgumentParser()
    ap.add_argument("--main-port", type=int, default=8851)
    ap.add_argument("--fb-port", type=int, default=8852)
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    MAIN_BASE = f"http://localhost:{a.main_port}"
    AE_BASE = f"http://localhost:{a.fb_port}"

    out(f"Avatar Editor Test:  {time.strftime('%Y-%m-%dT%H:%M:%S')}")
    out(f"Store:               {fixture.ROOT_REL}  (built, used, deleted)")
    out(f"Main editor:         {MAIN_BASE}")
    out(f"Avatar Editor:       {AE_BASE}")

    step("Build the test store")
    for n, label, ns, na, nn, _ in fixture.SCENES:
        check(f"{n:02d}-{label}", True, f"segment={ns} avatar={na} narration={nn}")
    fixture.build(quiet=True)

    main_srv = subprocess.Popen(
        [sys.executable, MAIN_SERVE, "--port", str(a.main_port), "--no-session-log"],
        cwd=os.path.dirname(MAIN_SERVE), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    fb_srv = subprocess.Popen(
        [sys.executable, AE_SERVE, "--port", str(a.fb_port), "--no-session-log"],
        cwd=os.path.dirname(AE_SERVE), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env={**os.environ, "MAIN_EDITOR_URL": MAIN_BASE})
    try:
        if not wait_up(MAIN_BASE + "/browse.html"):
            sys.exit("  the main editor never came up")
        if not wait_up(AE_BASE + "/"):
            sys.exit("  avatar_editor never came up")

        for fn in FUNCTIONS:
            fn()
    finally:
        if not a.keep:
            main_srv.terminate()
            fb_srv.terminate()
            fixture.destroy()
        else:
            out(f"\n  --keep: store at {fixture.STORE}")
            out(f"  --keep: servers still on {MAIN_BASE} and {AE_BASE} (kill them yourself)")

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    out(f"\n  Checks:  {passed}/{len(RESULTS)} passed")
    out(f"  Result:  {'PASS' if passed == len(RESULTS) else 'FAIL'}")

    # Own folder, own log + report — tests/avatar_editor/, never another
    # editor's (see fixture.write_report()'s own docstring for why this
    # is shared code rather than copied four times).
    base = fixture.write_report("avatar_editor", LOG, RESULTS, STEPS)
    out(f"  Report:  tests/avatar_editor/{base}.txt")

    if passed != len(RESULTS):
        sys.exit(1)


if __name__ == "__main__":
    main()
