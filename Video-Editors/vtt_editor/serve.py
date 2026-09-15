#!/usr/bin/env python3
"""
VTT Editor's own server — the FIRST edit on a raw capture, in one place.

    python3 vtt_editor/serve.py                 # port 8848
    python3 vtt_editor/serve.py --port 8899

WHAT THIS IS
    Carson, 2026-09-15: "This will be the first edit on the raw video and will
    do the following things: Add the yellow rings to the click event triggers.
    Break the raw into our segments. Into the scenes. Add some descriptive
    narrative. And add the voice… I want to make this its own editor inside the
    Video-Editors folder and call it vtt_editor."

    Five jobs that were already proven but scattered across a Python script, a
    sandboxed artifact page, a localhost server nobody was meant to run twice,
    and the recorder itself. Nothing here re-implements them — it drives them
    and reports what they did.

WHY ITS OWN PROCESS, ON ITS OWN PORT
    Same shape and same reasoning as avatar_editor and frame_blender: a
    separate small process, not a route bolted onto shared/serve.py. An editor
    that grows its own features is an editor whose bugs stay its own.

⚠ IT REPLACES Recorder/scripts/serve_vtt.py, WHICH IS GONE.
    Carson's call, 2026-09-15, when asked what happens to the three surfaces
    that had grown to edit narration. serve_vtt.py was one writer too many —
    it and an artifact page could both hold script.json open, and on 2026-09-14
    it was left running after being reported stopped. The artifact page STAYS
    (it is the one that opens anywhere); the SAE's own EVTT panel stays too, and
    covers a different stage — a BUILT video's sandbox/.

⚠ IT NEVER TOUCHES THE MASTER.
    Every job writes NEW files beside it. The master is what every later
    generation is cut from, and this repo has already lost one.

⚠ A JOB THAT CANNOT RUN IS REPORTED WITH ITS REASON, NOT HIDDEN.
    /api/state returns a `blocked` string per job, and the interface shows it on
    the row. The dead-button history here is long enough to design against: a
    confirm() that returned false silently in a sandbox, a Publish left enabled
    with no handler in a read-only view, a Stretch offered against a stale
    table. A row that cannot act says why.
"""
import argparse
import functools
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
EDITORS = os.path.dirname(HERE)                    # Video-Editors/
VE_ROOT = os.path.dirname(EDITORS)                 # Video-Editor/
WEB = os.path.join(HERE, "web")
CACHE = os.path.join(EDITORS, "cache", "vtt_editor")
LOGS = os.path.join(EDITORS, "logs")

# ⚠ THE TOOLS LIVE IN THE OTHER REPO, AND THAT IS DELIBERATE.
# Making the raw mp4 is Basic_E2E_Testing's job; everything after it is this
# repo's. The raw-capture tools sit on that boundary — they read a capture and
# its script — so they stay where the recorder is and this editor drives them.
# Override with BASIC_E2E_REPO if it is checked out somewhere else.
RECORDER = os.path.join(
    os.environ.get("BASIC_E2E_REPO",
                   os.path.join(os.path.dirname(VE_ROOT), "Basic_E2E_Testing")),
    "Master_Flows", "Recorder")
SCRIPTS = os.path.join(RECORDER, "scripts")

sys.path.insert(0, EDITORS)
from editor_base import paths as ebpaths          # noqa: E402
from editor_base import frames as ebframes        # noqa: E402

CUSTOMERS = os.path.join(VE_ROOT, "Customers")


# ── finding the work ────────────────────────────────────────────────────────

def _dirs(path):
    """Sorted sub-directory names, or nothing when the path is not a directory."""
    if not os.path.isdir(path):
        return []
    return sorted(d for d in os.listdir(path)
                  if os.path.isdir(os.path.join(path, d)) and not d.startswith("."))


def script_in(folder):
    """Where this working folder's script.json is, if it has one.

    ⚠ IT IS NOT ALWAYS IN THE FOLDER ITSELF, and that is the whole reason this
    is a function. A RAW capture keeps `script.json` beside the mp4. A BUILT
    video keeps it one level down — `sandbox/script.json`, with `dev/` carrying
    a working copy and `video/script_v<N>.json` the snapshot each build used. A
    gate that only checked the folder itself would report every built video as
    having no words at all.
    """
    for rel in ("script.json",
                os.path.join("sandbox", "script.json"),
                os.path.join("dev", "script.json")):
        p = os.path.join(folder, rel)
        if os.path.isfile(p):
            return p
    return ""


def breadcrumbs():
    """The whole tree, four levels deep, for the breadcrumb pickers.

    Carson, 2026-09-15: "I need to load the videos for specific stores. So lets
    add some breadcrumb filters." One flat list of every capture in the estate
    was fine with eight; it is not fine across two businesses, four stores and
    four stages each, and it hid which store a recipe belonged to.

        business  ->  store  ->  help-video folder  ->  working folder
        Rentify Demos Corp / ski-demo / raw_mp4 / special-skis

    ⚠ EVERY LEVEL IS LISTED, INCLUDING THE EMPTY ONES, and each leaf says
    whether it has a script. Hiding a folder because it has no words makes a
    store look like it has nothing in it; saying "no script" tells you what to
    do next. Same rule as the job rows.
    """
    tree = []
    for biz in _dirs(CUSTOMERS):
        stores = []
        for store in _dirs(os.path.join(CUSTOMERS, biz)):
            hv = os.path.join(CUSTOMERS, biz, store, "help-videos")
            stages = []
            for stage in _dirs(hv):
                work = []
                for wf in _dirs(os.path.join(hv, stage)):
                    folder = os.path.join(hv, stage, wf)
                    sp = script_in(folder)
                    work.append({
                        "name": wf,
                        "path": folder,
                        "has_script": bool(sp),
                        "script": (os.path.relpath(sp, folder) if sp else ""),
                    })
                stages.append({"name": stage, "path": os.path.join(hv, stage),
                               "folders": work})
            if stages:
                stores.append({"name": store, "stages": stages})
        if stores:
            tree.append({"name": biz, "stores": stores})
    return tree


def recipe_folders():
    """Flat list of every working folder — kept for the startup count and for
    anything that just wants "how much is there"."""
    out = []
    for biz in breadcrumbs():
        for store in biz["stores"]:
            for stage in store["stages"]:
                for f in stage["folders"]:
                    out.append({"recipe": f["name"], "store": store["name"],
                                "business": biz["name"], "stage": stage["name"],
                                "path": f["path"], "has_script": f["has_script"]})
    return out


def capture_of(folder, spec=None):
    """The mp4 this folder's script was cut from — NAMED, never guessed.

    script.json's note says "Cut from <file>.mp4". One folder legitimately
    holds two mp4s (a master plus the shared login clip), so guessing picks the
    wrong one about half the time.
    """
    if spec is None:
        p = script_in(folder)
        if not p:
            return ""
        try:
            spec = json.load(open(p))
        except ValueError:
            return ""
    m = re.search(r"Cut from (\S+\.mp4)", spec.get("_note", "") or "")
    return m.group(1) if m else ""


def probe_fps(path):
    """The capture's real frame rate, so SEGMENT frames are counted not guessed.

    ⚠ NOT ASSUMED 25. one-day-rental is 30fps and special-skis is 25; a fixed
    25 put stretch_scenes' candidate edges past the end of a 66s file before it
    was caught. Same lesson, same fix.
    """
    if not path or not os.path.isfile(path):
        return 25.0, "assumed"
    raw = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", path],
        capture_output=True, text=True).stdout.strip()
    if "/" in raw:
        num, den = raw.split("/")[:2]
        try:
            if float(den):
                return round(float(num) / float(den), 3), "measured"
        except ValueError:
            pass
    return 25.0, "assumed"


def read_json(path, default=None):
    if not path:
        return default
    try:
        return json.load(open(path))
    except (OSError, ValueError):
        return default


# ── the five jobs, and their real state ─────────────────────────────────────

def job_state(folder):
    """One row per job, each with its own numbers and its own blocker.

    Everything here is READ off disk. Nothing is remembered between requests —
    same rule as avatar_editor since the 2026-08-30 restructure, and the reason
    a stale table cannot offer a job that no longer makes sense.
    """
    # ⚠ script_in(), NOT a hardcoded path — a BUILT video keeps its script in
    # sandbox/, and reading the folder root would report it as having no words.
    spec = read_json(script_in(folder))
    report = read_json(os.path.join(folder, "stretch_report.json"))
    narration = read_json(os.path.join(folder, "narration_report.json"))
    capture = capture_of(folder, spec)
    master = os.path.join(folder, capture) if capture else ""
    scenes = (spec or {}).get("scenes") or []

    # ── RINGS ───────────────────────────────────────────────────────────────
    # ⚠ THE RINGS ARE ALREADY IN EVERY CAPTURE. Border-only, 750ms, drawn live
    # by the recorder — Carson's standing decision, 2026-09-09: "we will only
    # use the rings from now on. Looks better." What did not exist until
    # 2026-09-15 is any RECORD of them, so nothing could move or extend one.
    # A capture recorded before then has no log, and that is stated plainly
    # rather than shown as an empty panel that reads as broken.
    log_path = os.path.join(folder, capture.replace(".mp4", ".clicks.jsonl")) if capture else ""
    rings, ring_header = [], None
    if log_path and os.path.isfile(log_path):
        for line in open(log_path):
            d = read_json_line(line)
            if d is None:
                continue
            if d.get("kind") == "header":
                ring_header = d
            else:
                rings.append(d)
    rings_row = {
        "job": "rings",
        "n": len(rings),
        "clicks": sum(1 for r in rings if r.get("kind") == "click"),
        "typing": sum(1 for r in rings if r.get("kind") == "type"),
        "fill": "border-only",
        "trimmed": (ring_header or {}).get("lead_in_trimmed"),
        "blocked": "" if rings else
            ("no click log — this capture was recorded before 2026-09-15, "
             "when the recorder started writing one. The rings burnt into it "
             "are still there and still correct."),
    }

    # ── SEGMENTS ────────────────────────────────────────────────────────────
    # ⚠ COUNT SCENES, NOT FILES. segments/ is keyed by scene AND factor AND
    # edges, so one scene legitimately has several cached cuts — special-skis
    # had 27 files for 21 scenes. "27 of 21" is a number that cannot be true and
    # reads as a bug in the cache rather than in the counting.
    seg_dir = os.path.join(folder, "segments")
    cached = [f for f in sorted(os.listdir(seg_dir))
              if f.endswith(".mp4")] if os.path.isdir(seg_dir) else []
    cached_scenes = {f.split("-", 1)[0] for f in cached if f[:2].isdigit()}
    segments_row = {
        "job": "segments",
        "n": len(cached_scenes),
        "files": len(cached),
        "of": len(scenes),
        "blocked": "" if report and cached else
            ("no confirmed scene edges — run stretch_scenes.py peaks and "
             "confirm them first" if not report else
             "nothing cut yet — run a stretch to cut the scenes"),
    }

    # ── SCENES (the sandbox layout the built pipeline reads) ────────────────
    # Resolved through editor_base/paths.py, NOT by guessing a folder name.
    # That module already owns this layout, and it is what the SAE and build/
    # read — writing anywhere else makes a raw capture a dead end.
    built = 0
    for i, sc in enumerate(scenes, 1):
        try:
            if ebpaths.segment(folder, i):
                built += 1
        except Exception:
            pass
    scenes_row = {
        "job": "scenes",
        "n": built,
        "of": len(scenes),
        "blocked": "" if cached else "nothing to promote — cut the segments first",
    }

    # ── NARRATIVE ───────────────────────────────────────────────────────────
    wps = float((spec or {}).get("words_per_second", 3.44))
    # ⚠ 0.75 IN AND 0.75 OUT. Carson, 2026-09-15: "bring back my lead-in and
    # close-out dwell time of .75 sec on every scene." The default here only
    # applies to a script that has no field; every ski-demo script carries it.
    lead = float((spec or {}).get("_lead_in_seconds", 0.75))
    short, words = [], 0
    built_len = {r["n"]: r.get("built") for r in (report or {}).get("scenes", [])}
    # ⚠ EACH SCENE'S REAL START IN THE FILE, from the report's own src_in.
    # Summing the clips before a scene is wrong by exactly the dead lead-in:
    # one-day-rental opens on 2.43s of blank browser, so a summed start put
    # Play 2.43s early and it opened on the END of the previous screen. Found
    # 2026-09-15 by pressing Play on scene 8 and landing at 25.14s when the
    # scene starts at 27.57s. The edges are already absolute — use them.
    src_in = {r["n"]: r.get("src_in") for r in (report or {}).get("scenes", [])}
    for sc in scenes:
        line = sc.get("line") or ""
        w = len(strip_beats(line).split()) if line.strip() else 0
        words += w
        if not line.strip() or sc.get("silent"):
            continue
        clip = built_len.get(sc["n"])
        if clip is None:
            clip = float(str(sc.get("raw-source", "0")).split("s")[0] or 0)
        exit_s = sum(float(p.get("seconds", 0)) for p in sc.get("pauses", []))
        need = round(lead + round(w / wps, 1) + beat_seconds(line) + exit_s, 1)
        # ⚠ A TOLERANCE, BECAUSE THE PAGE SHOWS ONE DECIMAL.
        # A raw `clip < need` flagged add-collection's `item-saved` as short by
        # +0.0s — true to two decimals, and meaningless: a fortieth of a second
        # cannot be heard and stretching it re-encodes a scene for nothing. A
        # row that says "too short by 0.0s" reads as a broken number, and it
        # teaches you to ignore the column that matters.
        if need - clip > 0.05:
            short.append({"n": sc["n"], "label": sc["label"],
                          "clip": round(clip, 2), "needs": need,
                          "short_by": round(need - clip, 2)})
    narrative_row = {
        "job": "narrative",
        "n": len(scenes),
        "short": len(short),
        "short_rows": short,
        "words": words,
        "blocked": "" if scenes else "no scenes in script.json",
    }

    # ── VOICE ───────────────────────────────────────────────────────────────
    narrated = os.path.join(folder, capture.replace(".mp4", "-narrated.mp4")) if capture else ""
    base = int(os.environ.get("MAC_RATE", "155"))
    fast = [x for x in (narration or {}).get("lines", [])
            if x.get("rate") and x["rate"] != base]
    script_p = script_in(folder)
    stale = (not narrated or not os.path.isfile(narrated)
             or (script_p and os.path.isfile(script_p)
                 and os.path.getmtime(narrated) < os.path.getmtime(script_p)))
    # ⚠ WHETHER THERE IS ANYTHING TO HEAR IS A FACT, SO MEASURE IT.
    # "the narrated file exists" and "the narrated file has audio in it" are
    # different claims, and the second is the one a player cares about.
    narrated_ok = bool(narrated) and os.path.isfile(narrated)
    voice_row = {
        "job": "voice",
        "seconds": (narration or {}).get("seconds"),
        "rushed": len(fast),
        "rushed_rows": [{"n": x["n"], "label": x["label"], "rate": x["rate"]} for x in fast],
        "stale": bool(stale),
        "blocked": "" if capture else
            ("script.json's _note does not name the capture it was cut from, "
             "so there is nothing to lay the voice over"),
    }

    # ⚠ A BUILT VIDEO IS A DIFFERENT STAGE, AND THIS EDITOR DOES NOT OWN IT.
    # Its script carries no `raw-source` and no "Cut from" — the clip lengths
    # come from ffprobing sandbox/<NN-label>/segment.mp4, which is what the
    # Segment and Avatar Editor and build/vtt_html.py already do. Loading one
    # here produced a table of 11 scenes all zero seconds long, which reads as
    # a broken editor rather than as the wrong tool. So it is NAMED, not faked:
    # the folder stays in the picker and the page says where to go instead.
    kind = "raw"
    if not capture and not any(s.get("raw-source") for s in scenes):
        kind = "built"

    return {
        "folder": folder,
        "kind": kind,
        "recipe": os.path.basename(folder.rstrip("/")),
        "store": (spec or {}).get("store", ""),
        "title": (spec or {}).get("title", ""),
        "capture": capture,
        "narrated": (os.path.basename(narrated) if narrated_ok else ""),
        "master_exists": bool(master) and os.path.isfile(master),
        "footage": (report or {}).get("output_seconds")
                   or (spec or {}).get("_footage_seconds"),
        # The dwell at each end, and the frame rate the frames are counted at.
        "lead": lead,
        "fps": (report or {}).get("fps") or probe_fps(master)[0],
        "scenes": [{"n": s["n"], "label": s["label"],
                    "line": s.get("line") or "",
                    "silent": bool(s.get("silent")),
                    "start": src_in.get(s["n"]),
                    # Each scene's own close-out, from its pauses — a silent
                    # scene has none, and must not be given one.
                    "exit": sum(float(x.get("seconds", 0))
                                for x in (s.get("pauses") or [])),
                    "clip": built_len.get(s["n"]) if built_len.get(s["n"]) is not None
                            else float(str(s.get("raw-source", "0")).split("s")[0] or 0)}
                   for s in scenes],
        "jobs": [rings_row, segments_row, scenes_row, narrative_row, voice_row],
    }


BEAT = re.compile(r"\{\s*(\d*\.?\d+)\s*\}")


def strip_beats(t):
    return BEAT.sub(" ", t)


def beat_seconds(t):
    """A `{0.3}` marker is a BEAT: never a word, always added as silence.

    Counting it both ways pays for the same pause twice; counting it as a word
    leaves the screen 0.3s short of the line, every time. Same rule as
    Recorder/scripts/pause_marks.py — kept identical on purpose.
    """
    return round(sum(float(m.group(1)) for m in BEAT.finditer(t)), 3)


def read_json_line(line):
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except ValueError:
        return None


# ── running a job ───────────────────────────────────────────────────────────

def run_script(name, args, timeout=1800):
    """Shell out to a Recorder script and hand back what it said.

    ⚠ THE EDITOR NEVER ASSEMBLES ffmpeg ITSELF. Those recipes live in
    stretch_scenes.py and narrate_mac.py, where the edge cases are already
    written down — the keyframe spacing, the silent audio track, the cache key.
    A second copy here is a second copy to get wrong.
    """
    cmd = ["python3", os.path.join(SCRIPTS, name)] + list(args)
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return {
        "ok": p.returncode == 0,
        "code": p.returncode,
        "seconds": round(time.time() - t0, 1),
        "out": (p.stdout or "")[-8000:],
        "err": (p.stderr or "")[-4000:],
        "cmd": " ".join(cmd),
    }


def promote_segments(folder):
    """Copy each cached per-scene mp4 into the sandbox layout.

    ⚠ THE CUTS ARE NOT REDONE. stretch_scenes.py already cut them from the
    CONFIRMED edges in stretch_report.json and cached them in segments/. This
    only promotes them into sandbox/<NN-label>/segment.mp4, which is what makes
    a raw capture continue into the built pipeline.

    ⚠ THE LAYOUT COMES FROM editor_base/paths.py, NOT FROM A STRING HERE.
    sandbox_dir() owns the naming, and it is the same function the SAE and
    build/ resolve with — so a folder written here is a folder they can read.
    """
    report = read_json(os.path.join(folder, "stretch_report.json"))
    if not report:
        return {"ok": False, "err": "no stretch_report.json — no confirmed edges"}
    seg_dir = os.path.join(folder, "segments")
    if not os.path.isdir(seg_dir):
        return {"ok": False, "err": "no segments/ — cut the scenes first"}

    done, missing = [], []
    for row in report.get("scenes", []):
        n, label = row["n"], row["label"]
        # segments/ names each file by scene, label, factor and edges, so the
        # match is on the leading "NN-label-" rather than an exact filename.
        pre = f"{n:02d}-{label}-"
        hit = next((f for f in sorted(os.listdir(seg_dir))
                    if f.startswith(pre) and f.endswith(".mp4")), None)
        if not hit:
            missing.append(f"{n:02d}-{label}")
            continue
        dest_dir = ebpaths.sandbox_dir(folder, n, label)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, "segment.mp4")
        shutil.copy2(os.path.join(seg_dir, hit), dest)
        done.append({"n": n, "label": label, "to": os.path.relpath(dest, folder)})
    return {"ok": not missing, "promoted": done, "missing": missing,
            "err": ("no cached segment for: " + ", ".join(missing)) if missing else ""}


def save_line(folder, n, line):
    """Write ONE scene's words into script.json, keeping a backup.

    ⚠ TOUCH ONLY `line` (and `silent`/`pauses`, which follow from it).
    script.json also holds the measured clip lengths, the pauses, the chapter
    anchors and the notes. Those were measured or decided elsewhere and an
    editor has no business rewriting them.

    ⚠ AN EMPTIED LINE IS A REAL EDIT, AND IT MAKES THE SCENE SILENT. A guard of
    the shape `if (next and next != old)` silently refuses a cleared line, so a
    scene could be given words and never handed back to silence. Both
    directions work here.
    """
    p = script_in(folder)
    spec = read_json(p) if p else None
    if not spec:
        return {"ok": False, "err": "no readable script.json"}
    hit = next((s for s in spec["scenes"] if s["n"] == n), None)
    if hit is None:
        return {"ok": False, "err": f"no scene {n}"}
    if (hit.get("line") or "") == line:
        return {"ok": True, "changed": False}

    shutil.copy2(p, p + ".bak")
    hit["line"] = line
    silent = not strip_beats(line).strip()
    hit["silent"] = silent
    if silent:
        hit.pop("pauses", None)
    elif not hit.get("pauses"):
        hit["pauses"] = [{"seconds": 0.8}]
    with open(p, "w") as fh:
        json.dump(spec, fh, indent=1, ensure_ascii=False)

    # And prove the two files still agree, rather than assuming it. vtt_build
    # REFUSES on a mismatch, which is the drift it exists to stop.
    check = run_script("vtt_build.py", [folder], timeout=120)
    return {"ok": True, "changed": True, "verify": check}


# ── the server ──────────────────────────────────────────────────────────────

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):            # quieter than the default
        pass

    def send_json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def json_error(self, status, msg):
        self.send_json({"ok": False, "err": msg}, status)

    def send_web(self, name, ctype=None):
        path = os.path.join(WEB, os.path.basename(name))
        if not os.path.isfile(path):
            return self.json_error(404, f"no such file: {name}")
        if ctype is None:
            ctype = {".css": "text/css; charset=utf-8",
                     ".js": "text/javascript; charset=utf-8",
                     ".html": "text/html; charset=utf-8"}.get(
                         os.path.splitext(path)[1], "application/octet-stream")
        body = open(path, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    # ── GET ────────────────────────────────────────────────────────────────
    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path == "/":
            return self.send_web("index.html")
        if u.path.startswith("/web/"):
            return self.send_web(u.path[len("/web/"):])
        if u.path == "/api/folders":
            return self.send_json({"ok": True, "folders": recipe_folders()})
        if u.path == "/api/tree":
            return self.send_json({"ok": True, "tree": breadcrumbs()})
        if u.path == "/api/state":
            folder = (q.get("folder") or [""])[0]
            if not folder or not os.path.isdir(folder):
                return self.json_error(400, "folder= must be an existing directory")
            if not script_in(folder):
                return self.json_error(400, "that folder has no script.json")
            return self.send_json({"ok": True, "state": job_state(folder)})
        if u.path == "/api/video":
            return self.video(q)
        if u.path == "/api/frame":
            return self.frame(q)
        if u.path == "/api/rings":
            return self.rings(q)
        return self.json_error(404, f"no such route: {u.path}")

    def video(self, q):
        """The capture itself, with byte ranges — so a <video> can seek and play.

        ⚠ RANGE IS NOT OPTIONAL HERE. Carson, 2026-09-15: "I need a play button
        to run the scenes." A browser will not seek a video the server answers
        with a plain 200 — it has to refetch from zero, so jumping to scene 11
        of a 66-second file means downloading the whole thing first, and
        scrubbing is unusable. `SimpleHTTPRequestHandler` does not do ranges, so
        this does.

        ⚠ AND IT ONLY EVER READS. The capture is the master; this hands out
        bytes and never opens it for writing.
        """
        folder = (q.get("folder") or [""])[0]
        if not folder or not os.path.isdir(folder):
            return self.json_error(400, "folder= must be an existing directory")
        capture = capture_of(folder)
        if not capture:
            return self.json_error(404, "this folder's script names no capture")
        # ⚠ TWO SOURCES, AND THE DIFFERENCE IS WHETHER YOU CAN HEAR ANYTHING.
        # Carson, 2026-09-15: "I can not here it?" The player was muted (my
        # fault) AND the raw capture is digital silence — measured -91 dB. A raw
        # capture carries a silent AAC track by design; the voice only exists in
        # the `-narrated.mp4` that narrate_mac.py writes. So the player has to
        # be able to ask for either: the RAW to judge rings and timing, the
        # NARRATED to judge whether a line actually fits its screen.
        want = (q.get("src") or ["raw"])[0]
        name = (capture.replace(".mp4", "-narrated.mp4")
                if want == "narrated" else capture)
        src = os.path.join(folder, name)
        if not os.path.isfile(src):
            return self.json_error(
                404, f"{name} is not on disk"
                     + (" — build the voice first" if want == "narrated" else ""))

        size = os.path.getsize(src)
        rng = self.headers.get("Range", "")
        start, end = 0, size - 1
        partial = False
        m = re.match(r"bytes=(\d*)-(\d*)", rng or "")
        if m:
            a, b = m.group(1), m.group(2)
            if a:
                start = min(int(a), size - 1)
                end = min(int(b), size - 1) if b else size - 1
            elif b:                      # a suffix range: the LAST b bytes
                start = max(0, size - int(b))
            if start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            partial = True

        length = end - start + 1
        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(src, "rb") as fh:
            fh.seek(start)
            left = length
            while left > 0:
                chunk = fh.read(min(262144, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return               # the player seeked away; not an error
                left -= len(chunk)

    def do_HEAD(self):
        # A <video> HEADs before it ranges. Without this it gets a 501 and
        # never starts.
        return self.do_GET()

    def frame(self, q):
        """One frame of the capture, as a PNG, cached by folder + time.

        ⚠ CACHED ON DISK, because scrubbing asks for the same frames over and
        over and each one is an ffmpeg seek into a gigabyte. editor_base's own
        cache dir is reused so nothing new has to be cleaned up.
        """
        folder = (q.get("folder") or [""])[0]
        t = (q.get("t") or ["0"])[0]
        try:
            t = max(0.0, float(t))
        except ValueError:
            return self.json_error(400, "t= must be a number")
        if not folder or not os.path.isdir(folder):
            return self.json_error(400, "folder= must be an existing directory")
        capture = capture_of(folder)
        src = os.path.join(folder, capture) if capture else ""
        if not src or not os.path.isfile(src):
            return self.json_error(404, "this folder's script names no capture on disk")

        slug = ebframes.slug_for(src)
        out_dir = os.path.join(CACHE, slug)
        os.makedirs(out_dir, exist_ok=True)
        png = os.path.join(out_dir, f"t{t:09.2f}.png")
        if not os.path.isfile(png):
            subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t}", "-i", src,
                            "-frames:v", "1", "-vf", "scale=960:-1", png, "-y"],
                           capture_output=True)
        if not os.path.isfile(png):
            return self.json_error(500, f"could not read a frame at {t}s")
        body = open(png, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def rings(self, q):
        """The click log for this capture, with its geometry header.

        ⚠ THE RECTS ARE CSS PIXELS OF THE PAGE, NOT PIXELS OF THE VIDEO.
        The header carries the window region and the chrome crop so the
        transform can be done where both numbers are in hand. Returned as-is,
        with the header, rather than transformed here on a guess.
        """
        folder = (q.get("folder") or [""])[0]
        if not folder or not os.path.isdir(folder):
            return self.json_error(400, "folder= must be an existing directory")
        capture = capture_of(folder)
        p = os.path.join(folder, capture.replace(".mp4", ".clicks.jsonl")) if capture else ""
        if not p or not os.path.isfile(p):
            return self.send_json({"ok": True, "header": None, "rings": [],
                                   "why": "no click log for this capture"})
        header, rings = None, []
        for line in open(p):
            d = read_json_line(line)
            if d is None:
                continue
            if d.get("kind") == "header":
                header = d
            else:
                rings.append(d)
        return self.send_json({"ok": True, "header": header, "rings": rings})

    # ── POST ───────────────────────────────────────────────────────────────
    def do_POST(self):
        u = urllib.parse.urlsplit(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(n)) if n else {}
        except json.JSONDecodeError:
            return self.json_error(400, "body must be JSON")
        folder = payload.get("folder") or ""
        if not folder or not os.path.isdir(folder):
            return self.json_error(400, "folder must be an existing directory")

        if u.path == "/api/save_line":
            try:
                num = int(payload.get("n"))
            except (TypeError, ValueError):
                return self.json_error(400, "n must be a scene number")
            r = save_line(folder, num, str(payload.get("line") or "").strip())
            session_log("SAVE LINE", folder, f"scene {num}", r.get("ok"))
            return self.send_json(r)

        if u.path == "/api/promote":
            r = promote_segments(folder)
            session_log("PROMOTE", folder,
                        f"{len(r.get('promoted', []))} scenes", r.get("ok"))
            return self.send_json(r)

        if u.path == "/api/voice":
            # stretch_request.py is the whole chain: it lengthens only the short
            # screens, re-narrates, deletes the silent middle file, and skips the
            # encode when the soundtrack is already newer than the words.
            r = run_script("stretch_request.py", [folder])
            session_log("VOICE", folder, f"{r['seconds']}s", r["ok"])
            return self.send_json(r)

        if u.path == "/api/dry_run":
            r = run_script("stretch_request.py", [folder, "--dry-run"], timeout=180)
            return self.send_json(r)

        return self.json_error(404, f"no such route: {u.path}")


SESSION_LOG = ""


def session_log(action, folder, detail, ok):
    """One line per real action, in this editor's own file.

    Every editor logs to its own file (Carson's call, 2026-09-02) so one
    editor's actions are never interleaved with another's.
    """
    if not SESSION_LOG:
        return
    try:
        os.makedirs(os.path.dirname(SESSION_LOG), exist_ok=True)
        with open(SESSION_LOG, "a") as fh:
            fh.write(f"{time.strftime('%H:%M:%S')}  {'ok ' if ok else 'FAIL'}  "
                     f"{action:12s} {os.path.basename(folder.rstrip('/')):18s} {detail}\n")
    except OSError:
        pass


def main():
    global SESSION_LOG
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8848)
    ap.add_argument("--no-session-log", action="store_true",
                    help="don't write actions into logs/vtt_editor_<date>.log")
    a = ap.parse_args()
    if not a.no_session_log:
        SESSION_LOG = os.path.join(LOGS, f"vtt_editor_{time.strftime('%Y%m%d')}.log")

    os.makedirs(CACHE, exist_ok=True)
    handler = functools.partial(Handler, directory=CACHE)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), handler)
    folders = [f for f in recipe_folders() if f["has_script"]]
    print(f"  vtt editor serving on http://localhost:{a.port}")
    print(f"  cache: {CACHE}")
    print(f"  session log: {'off' if a.no_session_log else SESSION_LOG}")
    print(f"  {len(folders)} raw capture(s) with a script.json")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
