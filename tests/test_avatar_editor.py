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
    wc = urllib.request.urlopen(AE_BASE + "/web/working-clips.js", timeout=10).read().decode()
    gb = urllib.request.urlopen(AE_BASE + "/web/gap-builder.js", timeout=10).read().decode()
    js = urllib.request.urlopen(AE_BASE + "/web/app.js", timeout=10).read().decode()

    # ── the panel
    check("the panel is on the page", 'id="wcGroups"' in html)
    check("it has its own status line", 'id="wcStatus"' in html)
    check("it reuses the library panel's own classes, not a second layout",
          'class="panel libpanel wcpanel"' in html)
    for label in ("IDLE", "TRANSITIONS", "SOUND_BITS"):
        check(f"section {label}", f"label: '{label}'" in wc)
    check("exactly three sections", wc.count("{key: '") == 3)
    check("each row shows its frame count", "${entry.n}f" in wc)
    check("each row has its own checkbox", "cb.type = 'checkbox'" in wc)
    # One active item, not a list: Replace Selected needs ONE answer.
    check("ticking one unticks the rest",
          "cb.checked ? {section: sec.key, id: entry.id} : null" in wc)

    # ── saving
    # ONE control: picking a section IS the save, so there is no separate
    # button to press afterwards. The row wears a menu button's own box.
    check("Save to: is itself the button",
          'class="gapMenuBtn gapMenuRow" id="gmSaveToWorking"' in html)
    check("...with the dropdown inside it", 'id="gmSaveTarget"' in html)
    check("no second Save button",
          html.count('id="gmSaveToWorking"') == 1
          and "Save to Working Clips</button>" not in html)
    for value in ("idle", "sound_bits", "transitions"):
        check(f"...offers {value}", f'value="{value}"' in html)
    check("picking a section fires the save", "gmSaveTarget.onchange" in gb)
    # It is an action, not a setting, so it must never sit showing a
    # destination afterwards — saved or cancelled.
    check("...and the dropdown falls back to blank", "gmSaveTarget.value = '';" in gb)
    check("green when the Builder has frames",
          "save.classList.toggle('ready', n > 0);" in wc)
    # A <select> cannot live inside a <button>, so the row is a <div> and
    # cannot be :disabled — this class stands in for it.
    check("dimmed when it does not", "save.classList.toggle('isDisabled', !n);" in wc)
    check("...and the dropdown itself is disabled then", "target.disabled = !n;" in wc)
    check("it asks for a name in the page's own modal, not window.prompt",
          "modalPrompt({" in gb
          and "window.prompt(" not in gb and "= prompt(" not in gb)
    check("the modal's button says Continue", "okText = 'Continue'" in js)
    check("the whole Builder collection is saved, in order",
          "WorkingClips.saveBuilder(section" in gb and "BUILDER_FRAMES.slice()" in wc)
    # A stored URL would be a second copy of something derivable, and would
    # go stale if the frame cache were ever re-slugged.
    check("frames are stored compactly and their URLs rebuilt",
          "libFrameUrl(clip, p.local)" in wc and "packed.push({c: ci" in wc)
    check("saved clips survive a refresh",
          "saveStore({workingClips: DATA})" in wc and "WorkingClips.restore();" in js)

    # ── replacing
    check("Replace Selected button", 'id="gmReplaceSelected"' in html)
    check("it needs BOTH an active clip and a selection",
          "rep.disabled = !entry || !sel;" in wc)
    check("a different frame count warns first",
          "title: 'Mismatch frame count'" in gb)
    check("...with Yes and No", "yes: 'Yes', no: 'No'" in gb)
    check("No cancels and changes nothing",
          "if (!go) { libStatus.textContent = 'Replace cancelled.'; return; }" in gb)
    check("the replacement keeps the row's order",
          "LIB_FRAMES.splice(at, span, ...frames);" in gb)

    # ── the Audio Menu's Clear All
    check("Audio Menu Clear All", 'id="gmAudioClearAll"' in html)
    check("it resets every player", "gmAudioClearAll" in gb and "Players.reset();" in gb)
    # Unticking the library empties the Frame Selector too — a different
    # button's job, and destroying that collection here would be a surprise.
    clear_block = gb.split("gmAudioClearAll.onclick")[-1].split("// ── the three Play")[0]
    check("...and unticks nothing", "PICKED" not in clear_block)

    # ── logging
    for field in ("wcIdle", "wcTransitions", "wcSoundBits", "wcActive", "wcActiveN"):
        check(f"every click logs {field}", f"{field}:" in gb)


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
    gb = urllib.request.urlopen(AE_BASE + "/web/gap-builder.js", timeout=10).read().decode()
    fp = urllib.request.urlopen(AE_BASE + "/web/frame-player.js", timeout=10).read().decode()
    js = urllib.request.urlopen(AE_BASE + "/web/app.js", timeout=10).read().decode()

    for el in ("libGroupsCommon", "libStatusCommon"):
        check(f"the common panel has its own {el}", f'id="{el}"' in html)
    check("it is a real second panel, not a rename of the store's own",
          html.count('id="libGroups"') == 1 and html.count('id="libGroupsCommon"') == 1)

    check("one render function serves both panels",
          "function renderLibSource(d, groupsEl, statusEl, source, savedPaths)" in gb)
    check("loadLibs fetches the common library", "source=common" in gb)
    check("...and the store's own, unchanged", "fetch(`/api/libs_list?${pairQS()}`)" in gb)
    # Common renders FIRST, so its clips sort ahead of the store's own in
    # LIB_ORDER — the same left-to-right order the two panels sit in.
    common_at = gb.find("renderLibSource(d, libGroupsCommon")
    store_at = gb.find("renderLibSource(d, libGroups, libStatus, 'store'")
    check("common is rendered before the store panel, matching their on-screen order",
          -1 < common_at < store_at, (common_at, store_at))

    # Every request a checked clip triggers has to carry `source` — Sarah/
    # and a store's own sarah_clips/libs/ are siblings, not one inside the
    # other, so a bare path is ambiguous between them.
    check("checking a clip asks for ITS OWN source's frames",
          "/api/lib_frames?source=${f.source}&path=" in gb)
    check("PICKED remembers which library each clip came from",
          "source: f.source" in gb)
    check("playing a clip's audio carries its source too",
          "/api/lib_media?source=${f.source}&path=" in fp)
    # The rest pose is looked up in the common library FIRST, a store's own
    # copy only as a fallback — Sarah/ is the canonical source for it now.
    check("the rest pose prefers the common library",
          "restPosePath = f.path; restPoseSource = 'common';" in gb)
    check("...falling back to the store's own copy", "restPoseSource = 'store';" in gb)

    step("the store panel's header names the store and video, not the folder")
    # "sarah_clips/libs" told you the folder, not what you were looking at
    # (Carson's own call, 2026-09-03) — replaced with the store name, the
    # video name under it. HTTP can't open a pair to watch it fill in, so
    # this checks the WIRING: the two elements exist, the parser that fills
    # them reads SCENE's own base_rel (right even when that store's library
    # is empty or archived — it doesn't wait on /api/libs_list), and both
    # get put back to the loading placeholder on Clear.
    check("no more static 'sarah_clips/libs' label", "sarah_clips/libs</h3>" not in html)
    for el in ("libHeaderStore", "libHeaderVideo"):
        check(f"the header has its own {el}", f'id="{el}"' in html)
    check("storeVideoFromPath() parses <Business>/<store>/.../<video>/sandbox/...",
          "function storeVideoFromPath(rel)" in gb
          and "parts.indexOf('sandbox')" in gb)
    check("filled from SCENE.base_rel, not from the libs_list response",
          "storeVideoFromPath(SCENE.base_rel)" in gb)
    check("Clear puts both back to the placeholder",
          "libHeaderStore.textContent = '—';" in js
          and "libHeaderVideo.textContent = '—';" in js)

    step("the common panel's title, and both panels' loading spinners")
    # "Sarah/ (common)" -> "Sarah" (Carson's own call, 2026-09-03) — the
    # h3's own text-transform: uppercase already renders it SARAH; the
    # markup stays title case, matching every other h3 on this page
    # ("Timeline Scenes", "Working Clips").
    check("the common panel's h3 is just Sarah now",
          "<h3>Sarah</h3>" in html and "Sarah/ (common)" not in html)
    css = urllib.request.urlopen(AE_BASE + "/web/app.css", timeout=10).read().decode()
    for el in ("libSpinner", "libSpinnerCommon"):
        check(f"{el} exists, starts hidden", f'id="{el}" hidden' in html)
    check("a real spinner, not a static icon", ".spinner" in css and "@keyframes spin" in css)
    # Both fetches show their OWN spinner right before firing and hide it
    # in a `finally` — not just after the try block, because two of the
    # store fetch's own branches `return` early; only `finally` runs on
    # every one of those paths, success or not.
    check("common's spinner shows before its fetch fires",
          "libSpinnerCommon.hidden = false;\n  try {\n    const r = await fetch('/api/libs_list?source=common')" in gb)
    check("...and hides in a finally, not just after the try",
          "} finally {\n    libSpinnerCommon.hidden = true;\n  }" in gb)
    check("the store panel's spinner does the same",
          "libSpinner.hidden = false;\n  try {\n    const r = await fetch(`/api/libs_list?${pairQS()}`)" in gb)
    check("...also hidden in a finally",
          "} finally {\n    libSpinner.hidden = true;\n  }\n}" in gb)
    check("Clear hides both defensively, even mid-fetch",
          "libSpinner.hidden = true;" in js and "libSpinnerCommon.hidden = true;" in js)


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
    tt = urllib.request.urlopen(AE_BASE + "/web/tooltips.js", timeout=10).read().decode()

    check("three seconds, exactly", "const DELAY = 3000;" in tt)
    # Read at hover time, never cached: a Play button's title says how many
    # clips it would play, and Save to:'s how many frames it would save.
    check("the text comes from the live title", 'src.getAttribute(\'title\')' in tt)
    # Both tooltips showing at once would be worse than either alone.
    check("the browser's own tooltip is suppressed while hovering",
          "c.removeAttribute('title');" in tt)
    check("...and put back on the way out",
          "holding.setAttribute('title', heldTitle)" in tt)
    # The library's rows, Timeline Scenes' rows and Working Clips' rows are
    # all built at runtime, and more will be.
    check("delegated, so runtime-built controls are covered too",
          "document.addEventListener('mouseover'" in tt)
    check("a click cancels a pending tooltip", "'mousedown', 'wheel', 'keydown'" in tt)
    # Carson's own call: a tick box says what it does by being ticked.
    check("checkboxes are excluded",
          "if (c.matches('input[type=checkbox]')) return null;" in tt)
    # Long sentences on buttons that sit against the right edge.
    check("it is kept inside the window", "window.innerWidth" in tt and "window.innerHeight" in tt)
    check("it never steals the hover it describes", "pointer-events: none" in
          urllib.request.urlopen(AE_BASE + "/web/app.css", timeout=10).read().decode())

    # ── nothing silent
    # Every <button> and <select> written into index.html carries its own
    # title, EXCEPT the one that deliberately points at the row around it.
    import re as _re
    tags = _re.findall(r"<(?:button|select)\b[^>]*>", html)
    silent = [t for t in tags if "title=" not in t and "data-tip-from" not in t]
    check("every control in the page has a description", not silent, silent[:3])
    check("...and the count is what it should be", len(tags) >= 20, len(tags))
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
    # gap-builder.js must be named BEFORE app.js — app.js's own bootstrap
    # calls straight into functions gap-builder.js defines, so if load
    # order here ever regressed, the page would fail at the very last line
    # of app.js with everything above it having worked perfectly.
    # Match the <script src> attributes, never a bare filename — the
    # comments above these tags name all three files too, in a different
    # order, and matching those measures nothing.
    tt_pos = html.find('src="/web/tooltips.js"')
    wc_pos = html.find('src="/web/working-clips.js"')
    fp_pos = html.find('src="/web/frame-player.js"')
    gb_pos = html.find('src="/web/gap-builder.js"')
    app_pos = html.find('src="/web/app.js"')
    check("gap-builder.js is named before app.js", -1 < gb_pos < app_pos, (gb_pos, app_pos))
    # frame-player.js has to be FIRST: gap-builder.js's very last statement
    # is FramePlayer.configure({...}), so the component must already exist.
    check("frame-player.js is named before gap-builder.js", -1 < fp_pos < gb_pos,
          (fp_pos, gb_pos))
    # working-clips.js reads BUILDER_FRAMES and libFrameUrl from
    # gap-builder.js, and app.js's restoreGlobals() calls into it.
    check("working-clips.js sits between gap-builder.js and app.js",
          gb_pos < wc_pos < app_pos, (gb_pos, wc_pos, app_pos))
    check("tooltips.js is on the page", tt_pos > -1, tt_pos)
    for asset, ctype in (("/web/app.js", "javascript"), ("/web/gap-builder.js", "javascript"),
                         ("/web/frame-player.js", "javascript"),
                         ("/web/working-clips.js", "javascript"),
                         ("/web/tooltips.js", "javascript"),
                         ("/web/app.css", "css")):
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
    fp = urllib.request.urlopen(AE_BASE + "/web/frame-player.js", timeout=10).read().decode()
    gb = urllib.request.urlopen(AE_BASE + "/web/gap-builder.js", timeout=10).read().decode()
    wc = urllib.request.urlopen(AE_BASE + "/web/working-clips.js", timeout=10).read().decode()
    tt = urllib.request.urlopen(AE_BASE + "/web/tooltips.js", timeout=10).read().decode()
    js = urllib.request.urlopen(AE_BASE + "/web/app.js", timeout=10).read().decode()

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

    parses("frame-player.js", fp)
    parses("gap-builder.js", gb)
    parses("working-clips.js", wc)
    parses("tooltips.js", tt)
    parses("app.js", js)
    parses("all five together (load order)",
           fp + "\n" + gb + "\n" + wc + "\n" + tt + "\n" + js)


def s_original_audio_stack():
    """
    The Audio Menu's Play walks a STACK, and the stack is maintained by the
    checkbox events rather than worked out when Play is pressed. None of
    that is reachable over HTTP, so what is asserted here is the WIRING —
    the four joins that, if any one of them were dropped, would leave the
    button silently playing the wrong thing or nothing at all. Each one has
    already been the actual bug once.
    """
    step("Audio Menu — the OriginalAudio stack is wired to the checkboxes")
    fp = urllib.request.urlopen(AE_BASE + "/web/frame-player.js", timeout=10).read().decode()
    gb = urllib.request.urlopen(AE_BASE + "/web/gap-builder.js", timeout=10).read().decode()
    html = urllib.request.urlopen(AE_BASE + "/", timeout=10).read().decode()

    check("OriginalAudio owns a stack", "let STACK = []" in fp)
    check("built in library display order, not tick order",
          "LibSources.checkedInOrder()" in fp)
    check("silent clips are kept out of it", "filter(c => c.has_audio)" in fp)
    check("Play walks the stack, not a fresh list", "P.run(STACK)" in fp)
    # A tick mid-run must EXTEND the run, not stop the voice.
    check("a live run is re-pointed rather than killed", "P.resync(STACK)" in fp)
    # Both branches of toggleLibClip — tick AND untick — must rebuild it.
    # The trailing ";" is what separates the two real call sites from the
    # comment that just points at them.
    eq("every checkbox event rebuilds the stack",
       gb.count("OriginalAudio.rebuild();"), 2)
    # rebuildLibFrames tears the Frame Selector's own row apart, so its run
    # has to end — but ending the Audio Menu's run there was a real bug:
    # ticking a second box killed the voice that was already playing.
    check("rebuildLibFrames ends only the SELECTOR's run",
          "FrameSelector.endRun()" in gb)

    step("each panel's Play button drives its OWN player, not a shared one")
    # One <video> for every button meant the Frame Selector's Play took over
    # a previewer on the other side of the page. FramePlayer is a factory
    # now: one engine per panel, each with its own elements.
    check("FramePlayer is a factory, not a single instance",
          "function create(dom)" in fp and "return {create," in fp)
    for el in ("fsPlayer", "fsVideo", "fsName", "fsRate"):
        check(f"the Frame Selector has its own {el}", f'id="{el}"' in html)
    check("the Frame Selector's engine is built on those",
          "player: 'fsPlayer'" in fp and "video: 'fsVideo'" in fp)
    check("the Audio Menu keeps its own", "video: 'soundBitVideo'" in fp)
    # Two voices at once is never wanted, and this is the ONLY thing the
    # engines are allowed to say to each other.
    check("starting one player quiets the others", "function stopOthers(me)" in fp)
    # The Frame Selector's viewer DOES step with its own voice — that is
    # the whole point of its button. What must never happen again is the
    # AUDIO MENU moving it: that left the panel parked mid-clip, on frames
    # nobody had asked to see. So the stepper has to live inside the
    # FrameSelector scenario and nowhere else.
    fs_block = fp.split("const FrameSelector = ")[-1].split("const GapBuilder = ")[0]
    gb_block = fp.split("const GapBuilder = ")[-1].split("const Players = ")[0]
    check("the Frame Selector steps its own frames", "P.tick((t, dur, clip)" in fs_block)
    check("the Clip-Gap Builder steps its own frames", "P.tick((t, dur, clip)" in gb_block)
    # Each panel reaches ONLY its own viewer. Crossing over is the exact
    # fault that left a panel parked mid-clip with nobody driving it.
    check("only the Frame Selector touches the Frame Selector's viewer",
          fp.count("LibSources.showFrame(") == 1
          and "LibSources.showFrame(" in fs_block)
    check("only the Clip-Gap Builder touches the Clip-Gap Builder's viewer",
          fp.count("LibSources.builderShow(") == 1
          and "LibSources.builderShow(" in gb_block)
    check("the Audio Menu touches neither",
          "showFrame" not in fp.split("const OriginalAudio = ")[-1]
                               .split("const FrameSelector = ")[0])
    check("the engine itself knows nothing about frames",
          "showFrame" not in fp.split("const FramePlayer = ")[-1]
                              .split("const OriginalAudio = ")[0])
    # A row built by pasting can hold a clip in pieces, out of order, or
    # twice — so "the clip starts at P, frame k is at P+k" is wrong there.
    check("frames are located by their own index within the clip",
          "f.local === k" in fp)
    # Once a run ended, the loaded clip could be replayed with the picture
    # frozen, because the stepper was handed queue[0] and the queue was gone.
    check("stepping follows the LOADED clip, not just a live run",
          "fn(video.currentTime, video.duration, currentClip)" in fp)
    # 25 frames a second through a full collection rescan was pure waste.
    check("Frame Selector stepping skips the full button refresh", "libStepping" in gb)
    check("Clip-Gap Builder stepping skips it too", "builderStepping" in gb)
    # A rebuilt row makes every position a run held meaningless.
    check("rebuilding the Builder's row ends its run", "GapBuilder.endRun();" in gb)
    # The Clip-Gap Builder is a TIMELINE, not an audio picker: its run is
    # every clip in the collection, silent ones included, and its button is
    # green whenever there are FRAMES to run. Asking the other two panels'
    # question here left a full 482-frame collection reading as silent.
    check("the Builder's run keeps silent clips", "seen.has(c.path)" in fp
          and "distinctAudible(src.builderFrames" not in fp)
    check("the Builder's button goes green on FRAMES, not voices",
          "btn.classList.toggle('ready', rowHas > 0);" in gb_block)
    check("the other two still go green only on a voice",
          "btn.classList.toggle('ready', STACK.length > 0);" in fp
          and "btn.classList.toggle('ready', n > 0);" in fs_block)
    # No second viewer in either panel: both already have one.
    for vid in ("fsVideo", "gbVideo"):
        check(f"{vid} is the voice only, never a second viewer",
              f'<video id="{vid}" playsinline hidden>' in html)


FUNCTIONS = [s_static_page, s_app_js_parses, s_original_audio_stack, s_working_clips, s_common_library_wiring, s_tooltips, s_stateless, s_load_picker, s_load_store,
             s_save_scene_proxy,
             s_libs_list_paths, s_common_library, s_libs_group_order,
             s_lib_frames_clip, s_lib_frames_still]


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
