#!/usr/bin/env python3
"""
Cut a raw E2E recording into the segments a help video is built from.

WHY THIS EXISTS
---------------
Segment boundaries used to be found by hand, and `HANDOFF.md` recorded the
result as one-off: "If this is ever re-cut from a new recording, redo this — do
not reuse these timestamps." That made every new video an investigation. It is
the same job every time, so it is a tool.

TWO CLOCKS, JOINED BY ONE STAMP
-------------------------------
1. **The flow log** stamps every action with an absolute wall-clock time
   (`▶ [HH:MM:SS.mmm] Login …`), added 2026-08-19.
2. **The recorder log** stamps when OBS actually began writing frames
   (`RECORDING_STARTED_AT HH:MM:SS.mmm`), added the same day.

`step_time - recording_start` is therefore that step's exact offset into the
video. No inference.

⚠ **Do not go back to summing the `(NNNNms)` durations.** That was the first
attempt and it fails in a way that looks like success: the totals agreed almost
exactly (71.12s of log against a 72.00s recording, a tidy-looking 0.88s offset)
while individual boundaries were out by a whole scene. The reason is that the
time BETWEEN steps — page waits, navigation — is logged nowhere, and that
unlogged time is not constant. Measured against three anchors in one run it was
3.96s, 5.98s and 3.64s. No single offset can absorb that.

3. **Frame-difference detection** then supplies the exact instant. The stamps
   say which transition; detection says which frame. Detection alone gives far
   too many candidates — 29 for 11 segments on ski-demo, since typing and clicks
   register alongside page loads — and misses transitions inside the same dark
   layout, which is how a boundary was once wrong by 2.8s.

So: take the boundary from the stamps, SNAP it to the nearest real transition
within `--snap`, and only fall back to the stamp if there is none.

THEN ADVANCE TO THE SETTLED FRAME
---------------------------------
A page-load instant is the WRONG cut point. The frames immediately after it are
mid-render — on the first ski-demo build, scene 1's opening 0.17s was a loading
spinner, and because that frame gets held under the whole opening bridge, three
frozen dots were the most visible defect in the finished video.

After snapping, this walks forward to the first frame whose successor differs by
less than `--settle-pct`, i.e. the picture has stopped changing. That is the
frame a viewer would call "the page".

ONE PAGE CAN CARRY MORE THAN ONE SCENE
--------------------------------------
This tool's unit is the PAGE LOAD. That is what it can detect, and it is the
right boundary most of the time — but it is not always the same as a scene.

ski-demo's requirements form and its checkout summary are **the same page**.
Nothing navigates between them, so no page load separates them and this tool
cannot find that boundary. It has to be given one.

**Naming, when a page's segment is split:** `segment-<NN>_<k>-<name>.mp4`.

    segment-07_1-requirements.mp4     same page, first part
    segment-07_2-checkout.mp4         same page, second part

The hyphen sequence (`-07-`, `-08-`) stays reserved for genuinely distinct
pages. The underscore says "this is a slice of one page", so the numbering
itself records why the boundary exists — which matters when a later take needs
re-cutting and someone has to know whether to look for a page load or not.

Split a page when its segment is long enough to want two narrations, or long
enough that one line would leave a large gap. The boundary comes from
`--override`, since detection cannot supply it.

⚠ **NOT YET SUPPORTED IN CODE.** `DEFAULT_MAP`'s stem is parsed with
`^segment-` + digits + `-`, which does not match `segment-07_1-` — the digits are followed
by `_`, not `-`. The regex and the map need updating before this convention can
be used. Documented 2026-08-20 ahead of that change.

ALWAYS LOOK BEFORE CUTTING
--------------------------
`analyse` writes a contact sheet of every proposed first-frame. Sub-second
render states hide between samples and a metric will not catch them — the
spinner survived a full build and a frame-by-frame review because the review
sampled every 6 seconds. Look at the sheet, then cut.

USAGE
-----
  cut_segments.py analyse <final-folder> --raw <rec.mp4> \
      --log <store testing/log_reports/…log> --rec-log <Recorder/_logs/…log>
  cut_segments.py cut <final-folder>

`analyse` is free and writes `work/boundaries.json` + `work/boundaries.png`.
`cut` reads that same proposal and writes `segments/`.
"""

import argparse
import glob
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

try:
    from PIL import Image, ImageChops, ImageDraw
except ImportError:
    sys.exit("Pillow required:  .claude/agent-tools/venv/bin/python -m pip install pillow")

# Locked encode standard — every segment in the library uses these.
# `-crf 18` is explicit on purpose. x264's default is 23, which measured
# SSIM 0.9994 against the raw — fine, but this footage is fine UI TEXT on flat
# dark panels, where SSIM flatters a soft result. 18 costs ~35% more bytes on a
# file that is already tiny (a 14.8s segment went 137KB -> 186KB) and there is
# no reason to spend the quality. Verified 2026-08-21 against CRF 15 and 12 too:
# below 18 the picture stops changing and only the file grows.
ENCODE = ["-c:v", "libx264", "-crf", "18", "-c:a", "aac", "-pix_fmt", "yuv420p",
          "-movflags", "+faststart"]

# Which flow-log actions make up each scene. Keyed by the scene's `segment`
# name in script.json, so a store with a different flow supplies its own.
# Matching is "the action line CONTAINS this text", first match wins, in order.
DEFAULT_MAP = {
    "login":        ["Login ("],
    "neworder":     ["Click order card"],
    "addmyself":    ["Add a Person"],
    "search":       ["Search item"],
    "dates":        ["Select dates"],
    "additem":      ["Add Item"],
    "requirements": ["Complete requirements"],
    # A store with no question set never shows a requirements form — canoe-demo
    # goes straight from the item to the terms checkboxes and on to payment, with
    # no separate checkout page. Its script has TEN scenes, not eleven. Do not
    # force ski-demo's shape onto a store whose flow differs; give it its own
    # segment names and map them here.
    "terms":        ["Complete requirements"],
    "checkout":     ["Save and Continue to Checkout"],
    "payment":      ["Pay ("],
    # NB "Order completed — Already Paid shown" is logged outside step(), so it
    # has no ▶ stamp. The return-from-payment wait is the anchor that does.
    "complete":     ["Wait for order completion"],
    "history":      ["Verify the order appears in dashboard history"],
}


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"failed: {' '.join(cmd[:8])}…\n{r.stderr.strip()[-700:]}")
    return r


def probe(path, entries, stream=False):
    c = ["ffprobe", "-v", "error"]
    if stream:
        c += ["-select_streams", "v", "-show_entries", f"stream={entries}"]
    else:
        c += ["-show_entries", f"format={entries}"]
    c += ["-of", "csv=p=0", path]
    return subprocess.run(c, capture_output=True, text=True).stdout.strip()


def _hms(t):
    """`HH:MM:SS.mmm` -> seconds since midnight."""
    h, m, rest = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)


def parse_log(path):
    """
    [(action, absolute_seconds_since_midnight)] from `▶ [HH:MM:SS.mmm] action`.

    ⚠ Absolute stamps, NOT summed `(NNNNms)` durations. Summing is the obvious
    approach and it is wrong: the time BETWEEN steps — page waits, navigation —
    is logged nowhere, so the running total falls behind the recording by a
    varying amount. Measured on one ski-demo run it drifted 3.6s to 6.0s, which
    put whole scenes in the wrong segment while the totals still looked right
    (71.12s of log against a 72.00s video).
    """
    out = []
    for ln in open(path, encoding="utf-8", errors="replace"):
        m = re.search(r"▶\s+\[(\d{2}:\d{2}:\d{2}\.\d{3})\]\s+(.*?)\s*$", ln.rstrip())
        if m:
            out.append((m.group(2), _hms(m.group(1))))
    if not out:
        sys.exit(
            f"no `▶ [HH:MM:SS.mmm] …` lines in {path}.\n"
            f"  Either it is the recorder's 5-step log rather than the flow's, or the\n"
            f"  run predates the timestamped logger (added 2026-08-19). A log without\n"
            f"  absolute stamps cannot be aligned to a recording — re-record."
        )
    return out


def parse_record_start(path):
    """`RECORDING_STARTED_AT HH:MM:SS.mmm` from the recorder's log."""
    for ln in open(path, encoding="utf-8", errors="replace"):
        m = re.search(r"RECORDING_STARTED_AT\s+(\d{2}:\d{2}:\d{2}\.\d{3})", ln)
        if m:
            return _hms(m.group(1))
    return None


def diff_profile(raw, tmp, fps, width=576):
    # ⚠ 576, not 192. The MEAN is a ratio and barely moves with resolution, but
    # the changed-PIXEL count scales with area — and that count is the only
    # signal that sees a keystroke. At 192px the caret that caused the "R"
    # defect moved ~8 pixels, inside the noise; at 576px it moves 70, which is
    # cleanly separable from the 3,950 of a form finishing its render.
    # If this width changes, --pixel-eps and --render-px must change with it.
    """Per-frame change against the previous frame: mean %, and pixels moved."""
    d = os.path.join(tmp, "fr")
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    run(["ffmpeg", "-v", "error", "-i", raw, "-vf", f"scale={width}:-1",
         "-c:v", "png", os.path.join(d, "f_%05d.png")])
    files = sorted(glob.glob(os.path.join(d, "f_*.png")))
    prof, moved, prev = [], [], None
    for f in files:
        im = Image.open(f).convert("L")
        if prev is not None:
            df = ImageChops.difference(prev, im)
            h = df.histogram()
            n = im.size[0] * im.size[1]
            prof.append(sum(i * c for i, c in enumerate(h)) / n / 255 * 100)
            # Count of pixels that moved a LOT, alongside the mean. The mean
            # cannot see a single typed character — it is ~0.014% of the frame
            # either way, indistinguishable from noise, and raising the analysis
            # resolution does not help because the mean is a ratio (576px gave
            # 0.018%). A localized change is invisible to a mean and obvious to
            # a count: the caret that put the "R" in v11 moved 70 pixels.
            moved.append(sum(c for v, c in enumerate(h) if v > 30))
        prev = im
    return prof, moved, files


def transitions(prof, fps, threshold, gap_frames=8):
    """Cluster frames above `threshold` into transitions; return peak frame of each."""
    peaks = [(i + 1, v) for i, v in enumerate(prof) if v >= threshold]
    if not peaks:
        return []
    clusters, cur = [], [peaks[0]]
    for p in peaks[1:]:
        if p[0] - cur[-1][0] <= gap_frames:
            cur.append(p)
        else:
            clusters.append(cur)
            cur = [p]
    clusters.append(cur)
    return [max(c, key=lambda x: x[1])[0] for c in clusters]


def settle(prof, frame, fps, settle_pct, max_walk, hold=0.4):
    """
    First frame at/after `frame` that stays still for `hold` seconds.

    ⚠ One quiet frame is not enough. A loading spinner is a few small dots on a
    large frame: at analysis resolution its animation moves less than the settle
    threshold, so a single-frame test declares the spinner "settled" and the cut
    opens on it. That is the three-dots defect, and it survived a whole build.
    Requiring a sustained quiet run breaks the tie, because a spinner keeps
    ticking over the window even when each tick is small.
    """
    need = max(2, int(hold * fps))
    limit = min(len(prof), frame + int(max_walk * fps))
    f = frame
    while f < limit:
        window = prof[f - 1: f - 1 + need]
        if window and len(window) == need and max(window) < settle_pct:
            return f
        f += 1
    return frame


def build_plan(a):
    cfg = json.load(open(script_path(a.folder)))
    scenes = cfg["scenes"]
    dur = float(probe(a.raw, "duration"))
    num, den = probe(a.raw, "r_frame_rate", stream=True).split("/")
    fps = float(num) / float(den)

    actions = parse_log(a.log)
    t0 = parse_record_start(a.rec_log) if a.rec_log else None
    if t0 is None:
        sys.exit(
            "need the recorder's log too (--rec-log), for its RECORDING_STARTED_AT line.\n"
            "  That stamp is the zero point: step_time - recording_start = the step's\n"
            "  exact offset into the video. Without it there is nothing to align to."
        )
    print(f"  recording {dur:.2f}s at {fps:g}fps")

    # Check the store's SHAPE before anything else. A sub-second gap between two
    # consecutive steps means the screen between them barely existed — most often
    # a store with no question set, where "Complete requirements" is followed
    # almost immediately by "Save and Continue to Checkout" because there is
    # nothing to fill in. Those stores have TEN scenes, not eleven, and no
    # separate checkout page. canoe-demo measured 0.44s there and alpine-sports
    # 0.44s; both needed segment-07-terms instead of requirements + checkout.
    #
    # Reading it here is far cheaper than the alternative: canoe was only caught
    # after a full slice produced an implausible 0.48s segment.
    for (n1, t1), (n2, t2) in zip(actions, actions[1:]):
        if 0 < t2 - t1 < 0.6 and "registration" not in n1.lower():
            print(f"  ⚠ only {t2-t1:.2f}s between \"{n1[:38]}\" and \"{n2[:38]}\"")
            print(f"    That screen barely existed — check the store's SHAPE before "
                  f"writing a script.")
    print(f"  first step is {actions[0][1] - t0:+.2f}s into the recording")
    if actions[0][1] < t0:
        print("  ⚠ the flow starts BEFORE the recording — mismatched log and take?")

    # each action's exact offset into the video
    cum = [(name, at - t0, None) for name, at in actions]
    if cum[-1][1] > dur:
        print(f"  ⚠ last step lands at {cum[-1][1]:.2f}s, past the {dur:.2f}s video")

    tmp = os.path.join(a.folder, "work")
    os.makedirs(tmp, exist_ok=True)
    prof, moved, files = diff_profile(a.raw, tmp, fps)
    trans = transitions(prof, fps, a.threshold)
    print(f"  {len(trans)} transitions detected at >={a.threshold}%")

    ov = {}
    for spec in (a.override or []):
        k, v = spec.split("=", 1)
        ov[int(k)] = float(v)
    if ov:
        print(f"  overrides: " + ", ".join(f"scene {k} -> {v}s" for k, v in sorted(ov.items())))

    plan = []
    for i, sc in enumerate(scenes):
        # Strips `segment-07-` AND `segment-07_1-`. The underscore form marks a
        # same-page split, so both parts share one page and both map to an
        # action; the stem after it is what DEFAULT_MAP is keyed on.
        stem = re.sub(r"^segment-\d+(?:_\d+)?-|\.mp4$", "", sc["segment"])
        # A scene may name its own anchor. DEFAULT_MAP is keyed on the stem of
        # names like `segment-04-search.mp4`, which yields a useless bare
        # "segment" for the MP4 Splitter's `Num_4-v4-segment.mp4` — so a store cut
        # in the editor cannot be mapped at all without this. `cut-map` is also
        # the only way to express a MERGED scene, whose span covers several
        # steps and is anchored by the first of them.
        keys = [sc["cut-map"]] if sc.get("cut-map") else DEFAULT_MAP.get(stem)
        if not keys:
            sys.exit(f"no action mapping for segment '{stem}' — give the scene a "
                     f"`cut-map` in script.json, or add the stem to DEFAULT_MAP")
        hit = next((c for c in cum if any(k in c[0] for k in keys)), None)
        if not hit:
            avail = "\n".join(f"       {c[0]}" for c in cum)
            sys.exit(f"segment '{stem}' matched no action in the log (looked for {keys}).\n"
                     f"  Actions this run logged a ▶ stamp for:\n{avail}\n"
                     f"  Add the right one to DEFAULT_MAP. Note some lines are logged\n"
                     f"  outside step() and so carry no ▶ — those cannot be anchors.")
        want = hit[1]
        wf = max(1, round(want * fps))
        # A step's visible result is its LAST repaint, not its first, and not the
        # nearest transition to the stamp. Two ways the nearest one is wrong:
        #   - a step that navigates (click "Pay with Stripe") is still showing the
        #     OLD page at its stamp; the new one paints a beat later.
        #   - a page arrives in stages — skeleton, spinner, content — and only the
        #     final paint is the picture a viewer would call "the page".
        # So take the last transition in a window that starts just before the
        # stamp and runs forward.
        # The window runs from just before the stamp to just before the NEXT
        # step's stamp. Bounding it by the next step rather than by a fixed
        # number of seconds is what makes a slow transition safe: checkout ->
        # Stripe takes over 2s, and a fixed 2s window stopped on the "submitting"
        # button spinner instead of reaching the page that followed it.
        # FIRST transition at/after the stamp, then walk to the first sustained
        # quiet. Both halves are needed and neither alone works:
        #   - Settling straight from the stamp returns the OLD page, because a
        #     step that navigates begins while the previous screen is still up
        #     and already still. The first transition is what leaves it.
        #   - Snapping to the NEAREST transition can land before the stamp;
        #     snapping to the LAST one in a window overshoots into whatever came
        #     next — with a 2s window that was the submit-button spinner, and
        #     with a window bounded by the next step it was the following page
        #     entirely, which put the dashboard in segment 1.
        # First-then-settle is the only rule that handled fast and slow
        # transitions with the same constants.
        # MAJOR transitions are page repaints; MINOR ones are keystrokes and
        # clicks. On ski-demo the login page painted at 67% and 86% while the
        # first typed character measured 0.64% — two orders of magnitude apart,
        # so one threshold separates them cleanly.
        #
        # Take the LAST major repaint in the window: a page can paint in stages
        # (67% then 86% here) and only the final one is the finished view.
        nxt = next((c[1] for c in cum if c[1] > want + 0.05), None)
        hard = round(nxt * fps) - 1 if nxt else len(prof)
        lo = wf - int(0.2 * fps)
        hi = min(wf + int(a.snap * fps), hard)
        major = [t for t in trans if lo <= t <= hi and prof[t - 1] >= a.major_pct]
        minor = [t for t in trans if lo <= t <= hi]
        snapped = max(major) if major else (min(minor) if minor else wf)
        # ⚠ The settle walk must NOT cross the next transition of ANY size.
        # Without that bound it walks past the first keystroke into the quiet
        # after it, and the held frame opens with a character already typed —
        # the "R" defect, which came back in v11 because the gap between the
        # page painting and the first keystroke was only 0.12s, far shorter than
        # the quiet run the walk was looking for.
        # Take the LAST frame before the next change, not the first quiet one.
        #
        # A page paints in stages. The first frame that looks quiet is often only
        # partly rendered — on ski-demo's login, frame 60 was quiet but still
        # mid-paint, while frame 62 was the finished form. And the very next
        # change after that is the first keystroke, so the last frame before it
        # is both fully painted and free of typed input. That single frame is the
        # only correct answer here: 63 has the "R", 60 is half-drawn, 62 is right.
        #
        # Capped at +0.6s so a page that simply sits idle for seconds does not
        # eat the front of its own segment.
        # Ceiling comes from the PIXEL-COUNT signal, not the clustered
        # transitions. Clustering merges anything within 8 frames, and on the
        # login page the first keystroke lands 3 frames after the paint — so the
        # keystroke vanished into the paint's cluster and the walk sailed past it.
        # Stop at the first LOCALIZED change — an interaction. Big changes after
        # the paint are the page still rendering and must be absorbed, or the cut
        # lands on a half-drawn form. On ski-demo's login: 277,022 px is the
        # paint, 3,950 px is the form finishing, 70 px is the caret. Only the
        # last of those means "someone started typing".
        nxt_change = next((f for f in range(snapped + 1, len(moved))
                           if a.pixel_eps < moved[f - 1] < a.render_px), None)
        ceiling = (nxt_change - 1) if nxt_change else len(prof)
        first = max(snapped, min(ceiling, hard, snapped + int(0.6 * fps)))
        forced = ov.get(sc["n"])
        if forced is not None:
            first = max(1, round(forced * fps))
        plan.append({
            "n": sc["n"], "segment": sc["segment"], "action": hit[0],
            "log_s": round(want, 2), "snapped_f": snapped,
            "first_f": first, "start_s": round(first / fps, 3),
            "snapped": bool(major or minor), "major": bool(major), "overridden": sc["n"] in ov,
        })

    # Each segment runs to the next one's start, unless --length caps it.
    #
    # A segment often outlives its own scene: ski-demo's dashboard segment ran
    # 6.2s, but by 2.3s in it had already navigated to the order page — scene 3's
    # content. Running to the next start showed the next page under the previous
    # line. Capping the length keeps a segment to what its line is about; the
    # footage between the cap and the next segment is simply not used.
    lengths = {}
    for spec in (a.length or []):
        k, v = spec.split("=", 1)
        lengths[int(k)] = float(v)
    for i, p in enumerate(plan):
        end = plan[i + 1]["start_s"] if i + 1 < len(plan) else round(dur, 3)
        p["dur_s"] = round(end - p["start_s"], 3)
        if p["n"] in lengths:
            p["dur_s"] = round(min(lengths[p["n"]], p["dur_s"]), 3)
            p["capped"] = True

    json.dump({"raw": a.raw, "fps": fps, "duration": dur,
               "recording_start_hms": t0, "first_step_offset_s": round(actions[0][1] - t0, 3),
               "plan": plan}, open(os.path.join(tmp, "boundaries.json"), "w"), indent=2)
    return plan, fps, tmp, files


def sheet(plan, files, tmp):
    """Contact sheet of every proposed FIRST frame — the thing to actually look at."""
    CELL = 210
    cols = min(6, len(plan))
    rows = math.ceil(len(plan) / cols)
    sh = Image.new("RGB", (cols * (CELL + 6) + 6, rows * (CELL + 26) + 6), (18, 18, 18))
    dr = ImageDraw.Draw(sh)
    for i, p in enumerate(plan):
        f = files[min(p["first_f"], len(files) - 1)]
        im = Image.open(f).convert("RGB")
        im = im.resize((CELL, round(CELL * im.size[1] / im.size[0])))
        x = 6 + (i % cols) * (CELL + 6)
        y = 6 + (i // cols) * (CELL + 26)
        sh.paste(im, (x, y))
        tag = "  (forced)" if p.get("overridden") else ("" if p["snapped"] else "  (no snap)")
        dr.text((x + 2, y + im.size[1] + 3),
                f"{p['n']:02d} {p['start_s']:.2f}s {p['dur_s']:.2f}s{tag}", fill=(235, 235, 235))
    out = os.path.join(tmp, "boundaries.png")
    sh.save(out)
    return out


def cut_with_holds(raw, start, dur, holds, dst, tmp):
    """
    Cut a segment and freeze specified frames inside it, to stretch a short
    segment under a longer line WITHOUT slowing the demo down.

    `holds` is [(offset_into_segment, seconds), …].

    Why freeze rather than slow the footage: the demo always plays at natural
    speed — a sped-up or slowed-down UI reads as wrong immediately. Freezing a
    settled state does not, because the page genuinely is still at that moment.
    Hold the LAST frame of a state, not the first: the state is complete by then,
    the same reason a segment's cut lands on the settled page.

    ski-demo's calendar is the case this was built for: a 6.8s segment under a
    12.2s line, extended by freezing each of the four states the viewer needs to
    read — empty calendar, pickup chosen, range chosen, spinner.
    """
    # ⚠ Match the SOURCE rate. Hardcoding 30 here injects 30fps stills into a
    # 25fps segment, and everything upstream is 25 now: OBS records at 25 to
    # match HeyGen, which renders at 25 and cannot be changed. A mixed-rate
    # segment gets resampled at the concat, which is the duplication this whole
    # 25fps change exists to avoid.
    num, den = probe(raw, "r_frame_rate", stream=True).split("/")
    src_fps = float(num) / float(den)
    parts, prev = [], 0.0
    for i, (at, secs) in enumerate(sorted(holds)):
        if at > prev:
            seg = os.path.join(tmp, f"h_{i}_run.mp4")
            run(["ffmpeg", "-v", "error", "-ss", f"{start + prev:.3f}", "-i", raw,
                 "-t", f"{at - prev:.3f}"] + ENCODE + ["-y", seg])
            parts.append(seg)
        still = os.path.join(tmp, f"h_{i}_still.png")
        run(["ffmpeg", "-v", "error", "-ss", f"{start + at:.3f}", "-i", raw,
             "-frames:v", "1", "-y", still])
        frozen = os.path.join(tmp, f"h_{i}_hold.mp4")
        run(["ffmpeg", "-v", "error", "-loop", "1", "-t", f"{secs:.3f}", "-i", still,
             "-vf", f"fps={src_fps:g}"] + ENCODE + ["-y", frozen])
        parts.append(frozen)
        prev = at
    if dur > prev:
        seg = os.path.join(tmp, "h_tail.mp4")
        run(["ffmpeg", "-v", "error", "-ss", f"{start + prev:.3f}", "-i", raw,
             "-t", f"{dur - prev:.3f}"] + ENCODE + ["-y", seg])
        parts.append(seg)

    lst = os.path.join(tmp, "h_list.txt")
    open(lst, "w").write("".join(f"file '{os.path.abspath(x)}'\n" for x in parts))
    run(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst]
        + ENCODE + ["-y", dst])
    return dst


def cmd_analyse(a):
    plan, fps, tmp, files = build_plan(a)
    print(f"\n  {'#':>3} {'segment':<26}{'log':>8}{'start':>8}{'dur':>8}  snap")
    print("  " + "-" * 64)
    for p in plan:
        print(f"  {p['n']:>3} {p['segment'][:26]:<26}{p['log_s']:>7.2f}s"
              f"{p['start_s']:>7.2f}s{p['dur_s']:>7.2f}s  "
              f"{'FORCED' if p.get('overridden') else ('yes' if p['snapped'] else 'NO — log time used')}")
    print(f"\n  proposal -> {os.path.join(tmp,'boundaries.json')}")
    print(f"  ⚠ LOOK AT {sheet(plan, files, tmp)} before cutting — a mid-render")
    print(f"    frame here becomes the frozen frame under the opening bridge.")


def cmd_cut(a):
    bj = os.path.join(a.folder, "work", "boundaries.json")
    if not os.path.exists(bj):
        sys.exit("run `analyse` first — and look at its contact sheet")
    d = json.load(open(bj))
    out = os.path.join(a.folder, "segments")
    os.makedirs(out, exist_ok=True)
    holds = {}
    for spec in (a.hold or []):
        k, rest = spec.split("=", 1)
        at, secs = rest.split(":", 1)
        holds.setdefault(int(k), []).append((float(at), float(secs)))

    tmp = tempfile.mkdtemp(prefix="holds_")
    for p in d["plan"]:
        dst = os.path.join(out, p["segment"])
        h = holds.get(p["n"])
        if h:
            cut_with_holds(d["raw"], p["start_s"], p["dur_s"], h, dst, tmp)
            added = sum(x[1] for x in h)
            print(f"  {p['segment']:<28} {p['start_s']:>7.2f}s  "
                  f"{p['dur_s']:>5.2f}s +{added:.1f}s held")
            continue
        run(["ffmpeg", "-v", "error", "-ss", f"{p['start_s']:.3f}", "-i", d["raw"],
             "-t", f"{p['dur_s']:.3f}"] + ENCODE + ["-y", dst])
        got = float(probe(dst, "duration"))
        flag = "" if abs(got - p["dur_s"]) < 0.15 else "   ⚠ length differs"
        print(f"  {p['segment']:<28} {p['start_s']:>7.2f}s  {got:>6.2f}s{flag}")
    print(f"\n  {len(d['plan'])} segments -> {out}/")


def script_path(folder):
    """
    Locate a video's script.

    Moved to `<final>/sandbox/script.json` 2026-08-29 -- Carson's own call,
    to keep the script beside the scene folders it describes rather than a
    level up. `<final>/video/script.json` (2026-08-20 through 2026-08-29)
    and the bare `<final>/script.json` before that are both still accepted,
    so an un-migrated store keeps working rather than failing obscurely.

    Versioned snapshots (`script_v13.json`) are RECORDS written when a build is
    copied to a version, not inputs. At edit time the next version number is not
    known yet, so the working file stays unversioned.
    """
    import os
    new = os.path.join(folder, "sandbox", "script.json")
    mid = os.path.join(folder, "video", "script.json")
    old = os.path.join(folder, "script.json")
    if os.path.exists(new):
        return new
    if os.path.exists(mid):
        print(f"  ⚠ using {mid} — move it to sandbox/script.json")
        return mid
    if os.path.exists(old):
        print(f"  ⚠ using {old} — move it to sandbox/script.json")
        return old
    raise SystemExit(f"no script.json in {os.path.join(folder,'sandbox')}, "
                     f"{os.path.join(folder,'video')}, or {folder}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("analyse", cmd_analyse), ("cut", cmd_cut)):
        p = sub.add_parser(name)
        p.add_argument("folder")
        p.add_argument("--raw", required=(name == "analyse"))
        p.add_argument("--log", required=(name == "analyse"),
                       help="the FLOW's log (store testing/log_reports/), which carries ▶ stamps")
        p.add_argument("--rec-log", required=(name == "analyse"),
                       help="the RECORDER's log (Master_Flows/Recorder/_logs/), for RECORDING_STARTED_AT")
        p.add_argument("--threshold", type=float, default=0.5,
                       help="%% frame change that counts as a transition (default 0.5)")
        p.add_argument("--snap", type=float, default=6.0,
                       help="max seconds after the stamp to look (default 6.0; the next step's "
                            "stamp caps it anyway, so this rarely binds)")
        p.add_argument("--pixel-eps", type=int, default=20,
                       help="pixels that must move for a frame to count as CHANGED "
                            "(default 20). This is what sees a keystroke; the mean "
                            "cannot, at any resolution.")
        p.add_argument("--render-px", type=int, default=1000,
                       help="above this many changed pixels a change is the page still "
                            "RENDERING, not an interaction, and is absorbed (default 1000)")
        p.add_argument("--major-pct", type=float, default=5.0,
                       help="%% change that counts as a PAGE REPAINT rather than a "
                            "keystroke (default 5.0; paints measured 67-86%%, typing 0.64%%)")
        p.add_argument("--settle-pct", type=float, default=0.05,
                       help="below this the picture has stopped changing (default 0.05)")
        p.add_argument("--hold", action="append", metavar="N=AT:SECS",
                       help="freeze scene N's segment at AT seconds in, for SECS. "
                            "Repeatable. Stretches a short segment under a longer line "
                            "without slowing the demo down.")
        p.add_argument("--length", action="append", metavar="N=SECS",
                       help="cap scene N's segment at SECS instead of running it to the "
                            "next segment's start. Use when a segment outlives its scene "
                            "— it navigates onward while the line is still about the "
                            "previous page.")
        p.add_argument("--override", action="append", metavar="N=SECS",
                       help="force scene N to start at SECS. The detector gets most "
                            "boundaries; a step whose visible result lands far from its "
                            "stamp may need one. Read them off the contact sheet.")
        p.add_argument("--max-walk", type=float, default=2.0,
                       help="give up walking forward after this many seconds (default 2.0)")
        p.set_defaults(fn=fn)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
