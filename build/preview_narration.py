#!/usr/bin/env python3
"""
Hear a line, and watch the scene run out under it — for FREE.

    python3 build/preview_narration.py "<video folder>"            # every scene
    python3 build/preview_narration.py "<video folder>" --scene 3 7
    python3 build/preview_narration.py "<video folder>" --audio-only
    python3 build/preview_narration.py "<video folder>" --voice Karen --rate 150

WHAT THIS IS FOR
    Rewriting a line is free. Finding out it is four seconds too long, by
    rendering it at HeyGen, is not. This speaks the lines with the Mac's own
    voice, measures how long each really takes, and lays it over that scene's
    footage so the timing can be watched rather than estimated.

    Nothing here touches the network and nothing costs anything.

WHAT IT IS NOT
    Not Sarah, and not her mouth. There are no lip-sync frames — the picture is
    the DEMO footage with a voice over it. What it gives you is the two things
    a rewrite actually needs: the words in your ears, and the real length.

    The default rate is tuned to 3.56 words/sec against the 3.44 measured from
    Sarah's own rendered clips — about 3% fast, and `say`'s rates quantise so
    it cannot be dialled finer. Treat a gap inside half a second as "close",
    not as settled.

WHERE IT WRITES
    <video>/preview/NN-<label>.mp4  — the scene with the line spoken over it
    Nothing else is touched. The preview folder is disposable; delete it any
    time and re-run.
"""
import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "shared"))
import paths as PTH  # noqa: E402
import vtt as vtt_mod  # noqa: E402

# Samantha at 155 lands at 3.56 words/sec against Sarah's measured 3.44. The
# rates quantise — 160, 165 and 170 all produce the same duration — so this is
# as close as the synthesiser gets.
VOICE = "Samantha"
RATE = 155


def dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def with_pauses(line, pauses, sentence_ms=0):
    """
    Put the pauses into the line, as `say`'s own [[slnc N]] markers.

    A pause entry is `{"seconds": 0.6}` and may carry `{"after": "some words"}`
    to place it. Without `after` it lands at the end of the line. This is the
    SAME `pauses` field vtt.py already sums into the spoken length — one place
    describing a pause, not two that can disagree.

    ⚠ The real pipeline does not cut these in yet. PIPELINE.md says scene 7's
    pauses were spliced by hand and `assemble_video.py` does not perform the
    splice. So this previews what a pause WOULD sound like; it does not prove
    one exists in a build.

    `sentence_ms` adds the same gap after every sentence — the quick way to try
    "give it more room" without editing anything.
    """
    out = line
    for p in pauses or []:
        ms = int(round(float(p.get("seconds", 0)) * 1000))
        if ms <= 0:
            continue
        after = (p.get("after") or "").strip()
        if after and after in out:
            out = out.replace(after, f"{after} [[slnc {ms}]]", 1)
        else:
            out = f"{out} [[slnc {ms}]]"
    if sentence_ms > 0:
        # After a full stop, question or exclamation that ENDS a sentence — not
        # after the dot in "4 digit" or an abbreviation, which is why this looks
        # for the space and capital that follow a real sentence break.
        out = re.sub(r'([.!?])(\s+)(?=[A-Z"\u201c])',
                     lambda m: f"{m.group(1)} [[slnc {sentence_ms}]]{m.group(2)}", out)
    return out


def speak(line, dst, voice, rate):
    """Render `line` to an audio file. Returns its real duration."""
    r = subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", dst, line],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"  say failed: {r.stderr[-200:]}\n"
                 f"  is '{voice}' installed? list them with:  say -v '?'")
    return dur(dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", help="a video folder, e.g. .../videos/01-first-time-ordering")
    ap.add_argument("--scene", type=int, nargs="*", help="only these scene numbers")
    ap.add_argument("--voice", default=VOICE)
    ap.add_argument("--rate", type=int, default=RATE)
    ap.add_argument("--audio-only", action="store_true",
                    help="just the spoken lines, no video muxing — much faster")
    ap.add_argument("--sentence-pause", type=int, default=0, metavar="MS",
                    help="add this gap after every sentence, e.g. 400. "
                         "Tries 'more room' without editing script.json")
    a = ap.parse_args()

    F = os.path.abspath(a.folder)
    script = PTH.script(F)
    if not os.path.isfile(script):
        sys.exit(f"  no video/script.json under {F}")
    doc = json.load(open(script))
    wps = doc.get("words_per_second", 3.44)
    scenes = [s for s in doc.get("scenes", [])
              if not a.scene or s["n"] in a.scene]
    if not scenes:
        sys.exit("  no matching scenes")

    out_dir = os.path.join(F, "preview")
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n  Preview narration — {a.voice} at {a.rate}, free and offline")
    print(f"  {os.path.basename(F)}\n")
    print(f"    {'#':>3}  {'scene':24s} {'clip':>7} {'spoken':>7} {'gap':>7}  ")
    print(f"    {'':>3}  {'':24s} {'-'*7} {'-'*7} {'-'*7}")

    rows, over = [], []
    for s in scenes:
        n, label = s["n"], s.get("label", "")
        line = (s.get("line") or "").strip()
        seg = PTH.sandbox_only(F, n, label)["segment"] or PTH.segment(F, n, label)
        clip = dur(seg) if seg and os.path.isfile(seg) else 0.0

        if not line:
            print(f"    {n:>3}  {label:24s} {clip:6.2f}s {'—':>7} {'—':>7}   no line yet")
            continue

        aiff = os.path.join(out_dir, f"{n:02d}-{label}.aiff")
        pauses = s.get("pauses") or []
        spoken_text = with_pauses(line, pauses, a.sentence_pause)
        spoken = speak(spoken_text, aiff, a.voice, a.rate)
        gap = clip - spoken
        held = sum(float(x.get("seconds", 0)) for x in pauses)
        flag = "  ⚠ OVERRUNS" if gap < 0 else ("  ⚠ over 2.5s" if gap > 2.5 else "")
        if gap < 0:
            over.append(n)
        note = f"  +{held:g}s pause" if held else ""
        print(f"    {n:>3}  {label:24s} {clip:6.2f}s {spoken:6.2f}s {gap:+6.2f}s{note}{flag}")
        rows.append((n, label, clip, spoken, gap))

        if not a.audio_only and seg and os.path.isfile(seg):
            mp4 = os.path.join(out_dir, f"{n:02d}-{label}.mp4")
            # The VIDEO is never re-encoded — it is the scene as it is, with a
            # voice laid over it. -shortest so a line that outruns its footage
            # ends with the footage, which is exactly what the finished video
            # would do and the thing you are looking for.
            r = subprocess.run(
                ["ffmpeg", "-v", "error", "-i", seg, "-i", aiff,
                 "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                 "-c:a", "aac", "-b:a", "128k", "-shortest", "-y", mp4],
                capture_output=True, text=True)
            if r.returncode != 0:
                print(f"         could not build the preview: {r.stderr[-160:]}")

    if not rows:
        return 0
    tc = sum(r[2] for r in rows)
    ts = sum(r[3] for r in rows)
    print(f"\n    {'':>3}  {'total':24s} {tc:6.2f}s {ts:6.2f}s {tc-ts:+6.2f}s")
    print(f"\n    words-per-second here: {sum(vtt_mod.words(s.get('line') or '') for s in scenes if s.get('line')) / ts:.2f}"
          f"   Sarah's measured: {wps}")
    if over:
        print(f"    ⚠ scene(s) {', '.join(map(str, over))} OVERRUN their footage — "
              f"the line is still being said when the picture has moved on.")
    if not a.audio_only:
        print(f"\n    {out_dir}")
    print("\n    Free: nothing here went to HeyGen. Re-run after every rewrite.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
