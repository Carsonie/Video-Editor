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
import tempfile
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
EDITORS = os.path.dirname(HERE)                    # Video-Editors/
VE_ROOT = os.path.dirname(EDITORS)                 # Video-Editor/
WEB = os.path.join(HERE, "web")
CACHE = os.path.join(EDITORS, "cache", "vtt_editor")
LOGS = os.path.join(EDITORS, "logs")

sys.path.insert(0, EDITORS)
from editor_base import paths as ebpaths          # noqa: E402
from editor_base import frames as ebframes        # noqa: E402
# ⚠ THE TOOLS LIVE IN THE OTHER REPO, AND THAT IS DELIBERATE.
# Making the raw mp4 is Basic_E2E_Testing's job; everything after it is this
# repo's. The raw-capture tools sit on that boundary — they read a capture and
# its script — so they stay where the recorder is and this editor drives them.
# WHERE they are is one fact, and it lives in editor_base/recorder.py now;
# this editor had its own spelling of it and the SAE had a second.
from editor_base import recorder                  # noqa: E402
SCRIPTS = recorder.scripts_dir()

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


def probe_duration(path):
    """A file's real length in seconds, or None. Measured, never assumed."""
    if not path or not os.path.isfile(path):
        return None
    raw = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True).stdout.strip()
    try:
        return float(raw)
    except ValueError:
        return None


def _run_ff(args):
    """One ffmpeg call, quiet, and it RAISES on failure.

    ⚠ NEVER `check=False` HERE. A failed head or tail leaves the concat list
    naming a file that does not exist, and ffmpeg's concat demuxer answers that
    with a short output rather than an error — so the segment would come back
    TRUNCATED and look like a successful freeze.
    """
    r = subprocess.run(["ffmpeg", "-v", "error", "-nostdin"] + args,
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "ffmpeg failed").strip()[:400])
    return r


def read_json(path, default=None):
    if not path:
        return default
    try:
        return json.load(open(path))
    except (OSError, ValueError):
        return default


# ── the five jobs, and their real state ─────────────────────────────────────

# ⚠ A SCENE'S NAME IS NOT ALWAYS IN `label`. Nine scripts written before the
# field existed carry it inside `segment`, as "segment-01-login.mp4". Reading
# sc["label"] on one of those raised KeyError INSIDE the request handler, and
# ThreadingHTTPServer answers a raised handler with a dropped connection — so
# the page showed "Failed to fetch — is the server running on 8848?" and the
# whole editor looked dead because ONE old script was in the folder list.
# A name is cosmetic. It must never be able to stop the server.
SEG_RE = re.compile(r"^(?:segment-)?(\d+)-(.+)$")


def scene_label(sc):
    lab = (sc.get("label") or "").strip()
    if lab:
        return lab
    seg = (sc.get("segment") or "").strip()
    if seg:
        base = os.path.splitext(os.path.basename(seg))[0]
        m = SEG_RE.match(base)
        return m.group(2) if m else base
    return f"scene {sc.get('n', '?')}"


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
    # ⚠ narration_report.json IS DEAD WEIGHT — DO NOT READ RATES OUT OF IT.
    # It was written by narrate_mac.py, which built ONE soundtrack for the whole
    # video. Since the voice went per scene (voice_scenes.py, 2026-09-21) nothing
    # writes it, so it freezes on the day of the last whole-film narration and
    # every number in it rots from there. This page no longer opens it.
    #
    # THE LIVE FACTS ARE IN voice/state.json, written by voice_scenes.py every
    # time Save Timeline speaks a dirty scene: per scene its measured `rate`,
    # its `spoken` seconds, the `built` length it was made for and the `lead`.
    # Carson found this on 2026-09-21: the table showed scene 13 at 185 wpm
    # wanting 58 more frames while the real voice sat at 155 with 4.5s of dead
    # air, and — worse — showed 14 and 21 calm at 155 while they really spoke at
    # 215 and 250. Two of the four lies were in the reassuring direction.
    vstate = (read_json(os.path.join(folder, "voice", "state.json")) or {}).get("scenes") or {}
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

    # ── SEGMENT FRAME DUPLICATOR ────────────────────────────────────────────
    # Carson, 2026-09-15: "add another panel like this one, called SEGMENT FRAME
    # DUPLICATOR and add 4 buttons to duplicate the trackers current image with
    # the 05 x / 10 x / 20 x / 50 x buttons."
    #
    # It freezes the frame under the playhead and adds N copies of it, so ONE
    # screen gets longer where you are looking, rather than the whole screen
    # being slowed. That is the difference from a Stretch: `stretch_scenes.py`
    # spreads duplicated frames across every part of a segment on purpose, and
    # this parks on one frame deliberately.
    #
    # ⚠ IT WRITES THE CACHED CUT IN `segments/`, IN PLACE. Carson's call, asked
    # outright, because that is the file the scene strip and the table already
    # read — sandbox/ is 0 of 44 on the folder he had open, so a panel aimed
    # there would have arrived greyed out. The name is unchanged on purpose:
    # the cache key IS the name, so promote/ and build/ keep finding it.
    #
    # ⚠ SO EVERY PRESS BACKS THE OLD CUT UP FIRST, into
    # `segments/z_History/<stamp>/`. That backup is why there is no two-click
    # arm on these four: an undoable button pressed often should not ask twice.
    dup_row = {
        "job": "dupframe",
        "files": len(cached),
        "fps": (report or {}).get("fps"),
        "blocked": "" if (report and cached) else
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
            short.append({"n": sc["n"], "label": scene_label(sc),
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
    # ⚠ ONE SOURCE FOR ALL OF IT: voice/state.json. `rate` and `spoken` are
    # facts the voice tool measured and stored; anything derived from them is
    # worked out where it is shown, never stored. Storing a derived number is
    # exactly what froze the old report.
    said_rate, said_spoken, said_engine = {}, {}, {}
    for k, v in vstate.items():
        try:
            n = int(k)
        except (TypeError, ValueError):
            continue
        if v.get("silent"):
            continue                      # a silent scene has no pace to report
        if v.get("rate"):
            said_rate[n] = v["rate"]
            said_spoken[n] = v.get("spoken")
            # ⚠ "rate" MEANS TWO DIFFERENT THINGS NOW. For the Mac voice it is
            # WORDS PER MINUTE, base 155. For HeyGen it is `speed`, base 1.0 —
            # voice_scenes.py --engine heygen writes the same JSON key to carry
            # it, so a HeyGen scene at 1.2x reads here exactly like a Mac scene
            # at 1.2 wpm unless the page is told which scale it is on. Old state
            # files predate the engine field at all; they are Mac by definition.
            said_engine[n] = v.get("engine", "mac")
    fast = [{"n": n, "rate": r} for n, r in sorted(said_rate.items()) if r != base]
    # The voice bed is exactly as long as the picture, scene by scene, so the
    # soundtrack's length is the sum of the lengths it was built for.
    voice_seconds = round(sum(float(v.get("built") or 0) for v in vstate.values()), 2) or None
    by_n = {x["n"]: scene_label(x) for x in scenes if "n" in x}
    # ⚠ HOW MANY FRAMES THIS SCENE IS SHORT OF SPEAKING AT 155.
    # narrate_mac.py speeds a line up only because the screen ran out, so the
    # cure is frames, and this is how many: the seconds the line WOULD take at
    # 155 (its own rate scaled back) minus the room it has, at the capture's own
    # fps. A line already at or under 155 needs none. Carson, 2026-09-20.
    # ⚠ PRISTINE OR DIRTY, ASKED OF THE TOOL THAT OWNS THE RULE.
    # voice_scenes.py decides what needs re-speaking — no audio yet, the line
    # changed, the length changed, the dwell changed. Re-deciding it here would
    # be a second copy of that rule and they would drift; a --status run is one
    # stat() per scene and comes back in about 0.05s.
    dirty_why = {}
    try:
        st = recorder.run("voice_scenes.py", [folder, "--status"], timeout=120)
        for line in (st.get("out") or "").splitlines():
            bits = line.strip().split(None, 2)
            if len(bits) >= 3 and bits[0].isdigit() and bits[2].startswith("DIRTY"):
                dirty_why[int(bits[0])] = bits[2].split("—", 1)[-1].strip()
    except Exception:
        dirty_why = {}                    # a status we cannot read is not a defect

    # ⚠ THE `add` COLUMN IS NOT COMPUTED HERE ANY MORE. It is
    #
    #     add = (spoken x rate / 155 - room) x fps,  room = clip - lead - exit
    #
    # and `exit` is the scene's own trailing hold, which Carson can change by
    # typing a `{1}` marker in the table with no voice rebuild. A number stored
    # here would be wrong from that keystroke until the next save, which is the
    # bug this whole change removes. The page has clip, lead, exit and fps
    # already, so it does the sum on the row it is drawing. Verified against the
    # old report on 2026-09-21: the formula matched all 19 scenes whose report
    # rows were still valid, and disagreed on exactly the 3 that had gone stale.
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
        "seconds": voice_seconds,
        "rushed": len(fast),
        "rushed_rows": [{"n": x["n"], "label": by_n.get(x["n"], ""),
                         "rate": x["rate"]} for x in fast],
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

    script_p2 = script_in(folder)
    return {
        "folder": folder,
        "kind": kind,
        # The same number /api/stamp polls, so a read here resets the watcher.
        "script_mtime": os.path.getmtime(script_p2) if script_p2 and os.path.isfile(script_p2) else 0,
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
        # ⚠ THE MEASURED RATE, NOT A PLANNED ONE. voice/state.json says how fast
        # the voice tool actually had to speak each line to fit its screen; the
        # table's own `speech` column is a PLAN at 3.44 words a second, which is
        # faster than the voice really is, so a line can look like it fits and
        # still come out at 185. Carson, 2026-09-20: "add a column called WPM".
        # A scene with no voice yet has none, and the column says so.
        "scenes": [{"n": s["n"], "label": scene_label(s),
                    "wpm": said_rate.get(s["n"]),
                    # The seconds the voice really took. The page turns this
                    # into the `add` column against the room the scene has.
                    "spoken": said_spoken.get(s["n"]),
                    # Which baseline `wpm` is measured against — 155 for mac,
                    # 1.0 for heygen. The ADD column cannot be right without it.
                    "engine": said_engine.get(s["n"], "mac"),
                    # "" when this scene's voice is current; the reason when not.
                    "dirty": dirty_why.get(s["n"], ""),
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
        "jobs": [rings_row, segments_row, dup_row, scenes_row,
                 narrative_row, voice_row],
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
    return recorder.run(name, args, timeout=timeout)


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
        n, label = row["n"], scene_label(row)
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


# ⚠ THE SAME ENCODE `stretch_scenes.py` USED TO MAKE THESE FILES.
# Copied deliberately from scripts/stretch_scenes.py:206-212 rather than
# invented: a cached cut and a frozen insert are concatenated with the concat
# DEMUXER, which does not re-encode and so demands identical codec parameters
# on both sides. A different crf or keyint here produces a file that plays but
# glitches at the seam, which is the kind of fault you only see on the master.
# If that recipe ever changes, this must change with it.
DUP_ENCODE = ["-c:v", "libx264", "-crf", "16", "-preset", "fast",
              "-pix_fmt", "yuv420p"]


def _dup_x264(fps: float) -> list:
    return ["-x264-params",
            f"keyint={int(round(fps * 2))}:min-keyint={int(round(fps))}"]


def cached_for_scene(folder: str, row: dict, fps: float):
    """The cached cut this report row describes, by its EXACT key.

    ⚠ A PREFIX MATCH IS NOT GOOD ENOUGH HERE. `segments/` is keyed by scene AND
    factor AND edges, so one scene legitimately has several cached cuts —
    add-collection has two for `02-enter-the-code` (f1.0355 and f1.0651) and 48
    files for 44 scenes. `promote_segments` takes the first sorted match, which
    for scene 2 is the OLDER factor; freezing a frame into the wrong one edits a
    file nothing reads. So rebuild the key the writer used and fall back to the
    prefix only when that misses.
    """
    seg_dir = os.path.join(folder, "segments")
    if not os.path.isdir(seg_dir):
        return None, "no segments/ — cut the scenes first"
    label = scene_label(row)
    key = (f"{row['n']:02d}-{label}-f{row['factor']:.4f}-"
           f"{row['src_in']:.2f}_{row['src_out']:.2f}-{fps:g}fps.mp4")
    exact = os.path.join(seg_dir, key)
    if os.path.isfile(exact):
        return exact, ""
    pre = f"{row['n']:02d}-{label}-"
    hit = next((f for f in sorted(os.listdir(seg_dir))
                if f.startswith(pre) and f.endswith(".mp4")), None)
    if hit:
        return os.path.join(seg_dir, hit), ""
    return None, f"no cached cut for scene {row['n']} ({label})"


def dup_frame(folder: str, n: int, at: float, copies: int):
    """Freeze the frame under the playhead and add `copies` of it to scene `n`.

    `at` is a time in the CAPTURE, because that is the clock the player and the
    scrub both run on. It is mapped into the segment's own clock here rather
    than in the page: the segment may be stretched, and the page should not have
    to know the factor to put a frame in the right place.
    """
    if copies < 1 or copies > 500:
        return {"ok": False, "err": f"{copies} copies is out of range (1-500)"}
    report = read_json(os.path.join(folder, "stretch_report.json"))
    if not report:
        return {"ok": False, "err": "no stretch_report.json — no confirmed edges"}
    fps = float(report.get("fps") or 25)
    row = next((r for r in report.get("scenes", []) if r["n"] == n), None)
    if row is None:
        return {"ok": False, "err": f"no scene {n} in the report"}

    seg, why = cached_for_scene(folder, row, fps)
    if not seg:
        return {"ok": False, "err": why}

    # ⚠ THE PLAYHEAD MUST ACTUALLY BE IN THIS SCENE. Play stops at a scene's
    # end and the strip parks on its start, so it normally is — but the scrub
    # can be dragged anywhere, and freezing scene 8's frame into scene 3 is a
    # silent wrong answer rather than an error.
    a, b = float(row["src_in"]), float(row["src_out"])
    if not (a - 0.04 <= at <= b + 0.04):
        return {"ok": False,
                "err": f"the playhead is at {at:.2f}s, outside scene {n} "
                       f"({a:.2f}-{b:.2f}s) — click the scene you mean first"}

    dur = float(probe_duration(seg) or row.get("built") or 0)
    factor = float(row.get("factor") or 1.0)
    # The segment's own clock: the capture offset, scaled by the stretch that
    # made it. Clamped inside the file, so a playhead on the very last frame
    # appends rather than failing.
    off = max(0.0, min(dur, (at - a) * factor))
    added = copies / fps

    # ⚠ FRAMES, NOT SECONDS, AND ONE PASS. The first build of this cut the
    # head, wrote a still, looped the still and concat-demuxed the three — the
    # `cut_with_holds` recipe. It was WRONG, and provably: `-ss` placed BEFORE
    # `-i` is a KEYFRAME seek, not a frame-accurate one, so the still came from
    # a keyframe rather than the frame on screen and the tail resumed somewhere
    # else again. Tested against a numbered synthetic clip, which is the only
    # way to see it: a real UI screen barely changes between frames, so every
    # frame "matches" every other and the fault hides.
    #
    # `select` + `loop` inside ONE filter graph indexes frames by NUMBER, so
    # there is no seek to be inexact about. Same synthetic test after the
    # change: 0..11, 12,12,12,12,12,12, 13..39 — frame 12 six times (its own
    # plus five), 40 frames in, 45 out. Nothing dropped, nothing doubled.
    #
    # ⚠ `loop=loop=N` YIELDS N+1 COPIES, so it is `copies - 1`. loop=5 added
    # six frames, not five — measured, not read off the docs.
    k = int(round(off * fps))
    frames_now = int(round(dur * fps))
    k = max(0, min(frames_now - 1, k))
    added = copies / fps

    stamp = time.strftime("%Y%m%d-%H%M%S")
    bak_dir = os.path.join(folder, "segments", "z_History", stamp)
    os.makedirs(bak_dir, exist_ok=True)
    shutil.copy2(seg, os.path.join(bak_dir, os.path.basename(seg)))

    tmp = tempfile.mkdtemp(prefix="dupframe_")
    try:
        fc = (f"[0:v]select='lte(n,{k})',setpts=N/{fps:g}/TB[a];"
              f"[0:v]select='eq(n,{k})',loop=loop={copies - 1}:size=1:start=0,"
              f"setpts=N/{fps:g}/TB[b];"
              f"[0:v]select='gt(n,{k})',setpts=N/{fps:g}/TB[c];"
              f"[a][b][c]concat=n=3:v=1[o]")
        out = os.path.join(tmp, "out.mp4")
        _run_ff(["-i", seg, "-filter_complex", fc, "-map", "[o]", "-an",
                 "-r", f"{fps:g}"] + DUP_ENCODE + _dup_x264(fps) + ["-y", out])
        if not os.path.isfile(out) or os.path.getsize(out) == 0:
            return {"ok": False, "err": "ffmpeg produced nothing"}
        shutil.move(out, seg)
    except RuntimeError as e:
        # ⚠ AND THE OLD CUT IS STILL THERE. The backup is taken before ffmpeg
        # runs and `shutil.move` is the last step, so a failure anywhere leaves
        # the segment exactly as it was. Say what broke; change nothing.
        return {"ok": False, "err": f"ffmpeg: {e}"}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ⚠ THE REPORT HOLDS THE LENGTH THE TABLE SHOWS, so it has to move too.
    # job_state reads each scene's `built` from stretch_report.json, never from
    # the file — so a longer segment with an unchanged report means the clip,
    # gap and frames columns all quietly keep the old numbers, and the gap is
    # the column this button exists to close. MEASURED back off the new file
    # rather than added up, so the report cannot drift from what is on disk.
    new_dur = round(float(probe_duration(seg) or (dur + added)), 2)
    row["built"] = new_dur
    row["frames_added"] = int(row.get("frames_added") or 0) + copies
    report["output_seconds"] = round(
        sum(float(r.get("built") or 0) for r in report["scenes"]), 2)
    # ⚠ `indent=1`, AND NO TRAILING NEWLINE — the exact shape
    # stretch_scenes.py:238 writes. It is a TRACKED file, and writing it back
    # with `indent=2` reformatted all 494 lines, so `git diff` showed "494
    # insertions, 494 deletions" for a single changed number and a review could
    # not see what actually moved. Match the writer, not your own taste.
    #
    # `ensure_ascii=False` for the same reason: the report's `_output_removed`
    # note carries an em-dash, `stretch_request.py:268` writes it literally,
    # and the default would have escaped it to \u2014 — one more line of diff
    # that is not a change.
    rp = os.path.join(folder, "stretch_report.json")
    shutil.copy2(rp, rp + ".bak")
    with open(rp, "w") as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)

    return {"ok": True, "n": n, "label": scene_label(row), "copies": copies,
            "added": round(added, 3), "at": round(at, 2), "off": round(off, 2),
            "frame": k,
            "was": round(dur, 2), "now": new_dur, "fps": fps,
            "frames_total": int(round(new_dur * fps)),
            "backup": os.path.relpath(os.path.join(bak_dir,
                                                   os.path.basename(seg)), folder),
            "segment": os.path.basename(seg)}


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
        # ⚠ ONE NUMBER, POLLED. The Segment and Avatar Editor writes a line edit
        # straight into script.json (its api_line), so this page can be showing
        # yesterday's words while the file on disk is minutes old — Carson hit
        # exactly that on 2026-09-20: "when I change the narrative in the SAE
        # vtt, that new narrative is not updating the VTT Editor". A full
        # /api/state on a timer would re-read the report and re-probe the
        # capture every few seconds; this is a stat() and nothing else, and the
        # page only refreshes when the number moves.
        if u.path == "/api/stamp":
            # ⚠ NOT JUST THE WORDS. A sync can change a scene's LENGTH, its cut
            # and the voice without touching script.json — and this page shows
            # all three. Watching the script alone left the table on old frame
            # counts until someone reloaded by hand. Carson, 2026-09-21: "do a
            # page refresh to make everything current, including the VTT
            # Editor." The newest of the four is the stamp.
            folder = (q.get("folder") or [""])[0]
            if not folder or not os.path.isdir(folder):
                return self.send_json({"mtime": 0})
            # ⚠ voice/state.json, NOT narration_report.json. The dead report
            # never changes, so watching it meant a voice-only rebuild — the
            # common case now that scenes are spoken one at a time — moved no
            # stamp and left this table on old wpm values until a hand reload.
            watched = [script_in(folder),
                       os.path.join(folder, "stretch_report.json"),
                       os.path.join(folder, "voice", "state.json")]
            spec = read_json(script_in(folder)) or {}
            cap = capture_of(folder, spec)
            if cap:
                watched.append(os.path.join(folder, cap.replace(".mp4", "-narrated.mp4")))
            times = [os.path.getmtime(p) for p in watched if p and os.path.isfile(p)]
            return self.send_json({"mtime": max(times) if times else 0})
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

        if u.path == "/api/dup_frame":
            try:
                num = int(payload.get("n"))
                at = float(payload.get("at"))
                copies = int(payload.get("copies"))
            except (TypeError, ValueError):
                return self.json_error(
                    400, "n, at and copies are all required numbers")
            r = dup_frame(folder, num, at, copies)
            session_log("DUP FRAME", folder,
                        f"scene {num} +{copies}f at {at:.2f}s", r.get("ok"))
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
