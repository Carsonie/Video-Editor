#!/usr/bin/env python3
"""
Build each scene into its own mp4 and PROVE it. Only then join them.

    python3 build/build_scenes.py "<video folder>"              # every scene
    python3 build/build_scenes.py "<video folder>" --scene 4
    python3 build/build_scenes.py "<video folder>" --join 27     # join into _v27
    python3 build/build_scenes.py "<video folder>" --join 27 --rebuild

⚠ THE DIRECTIVE: SCENES FIRST, ALWAYS.
    Never build the whole video to find out whether it works. Build every scene
    on its own, check each one, and only join once they all pass.

    This is not tidiness. Between v23 and v26 four whole-video builds shipped
    faults that a single scene would have shown in seconds: an 11.4-second hole
    where one scene's avatar was transparent; a doubled opening; a scene cut
    2.4s short; a voice that fell behind and never caught up. Each cost a full
    rebuild and a viewing to find, and each was visible in one scene alone.

    A joined video hides its faults inside 110 seconds. A scene cannot.

WHAT A SCENE IS BUILT FROM — and it is NOT what assemble_video.py used
    segment.mp4   the demo footage, silent
    avatar.webm   Sarah, VP9 with real alpha, already placed in her corner,
                  and carrying the narration audio

    `avatar.webm` is the file the Segment and Avatar Editor shows. Until
    2026-08-27 the build composited `narration.webm` instead — the raw 1920x1080
    HeyGen render — so every frame balanced in the editor was balancing a file
    the build never opened. The editor was right and the video was wrong, with
    no way for the two to disagree out loud. Build what the editor shows.

THE THREE THINGS THAT MUST AGREE, AND EACH HAS BEEN WRONG ONCE
    1. FRAME COUNT.  The avatar's decoded frame count is the scene's length.
       `-frames:v N`, never `-t`: a duration cutoff drops the frame that lands
       on the boundary, and `shortest=1` dropped one too (87 of 88).
    2. THE CLOCK.  A segment may start at a non-zero timestamp — 0.021016s is
       real and measured here. Left alone it shifts the pairing; forced with
       `setpts=N/fps/TB` it compressed 248 frames into 7.5s and the scene
       played fast. `setpts=PTS-STARTPTS` is the one that is right: remove the
       offset, keep the spacing.
    3. THE AUDIO.  Padded with `apad` and cut to the picture's exact length.
       Unpadded, each scene ends a few ms short, and the concat demuxer lays
       audio and video end-to-end SEPARATELY — so those milliseconds accumulate.
       They reached 13.8 seconds of drift before this was understood.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "shared"))
import paths as PTH  # noqa: E402

CANVAS = 1152          # the square every finished scene is delivered on
FPS = 25


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"\n  ffmpeg failed:\n    {' '.join(cmd[:12])} ...\n"
                 f"    {r.stderr.strip()[-500:]}\n")
    return r


def probe(path, alpha=False):
    """(frames, duration, width, height, start_time) — decoded, not claimed."""
    dec = ["-c:v", "libvpx-vp9"] if alpha else []
    r = subprocess.run(["ffprobe", "-v", "error"] + dec + ["-count_frames",
                       "-select_streams", "v:0", "-show_entries",
                       "stream=nb_read_frames,width,height,start_time",
                       "-of", "csv=p=0", path], capture_output=True, text=True)
    w, h, st, n = (r.stdout.strip().split(",") + ["", "", "", ""])[:4]
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True).stdout.strip()
    return int(n), float(d or 0), int(w), int(h), float(st or 0)


def audio_len(path, alpha=False):
    dec = ["-c:v", "libvpx-vp9"] if alpha else []
    r = subprocess.run(["ffprobe", "-v", "error"] + dec + ["-select_streams", "a:0",
                       "-show_entries", "stream=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def build_one(sdir, out, label):
    seg = os.path.join(sdir, "segment.mp4")
    av = os.path.join(sdir, "avatar.webm")
    for f in (seg, av):
        if not os.path.isfile(f):
            return None, f"missing {os.path.basename(f)}"

    n, _, aw, ah, _ = probe(av, alpha=True)
    _, _, sw, sh, sst = probe(seg)
    if (aw, ah) != (CANVAS, CANVAS):
        return None, f"avatar is {aw}x{ah}, expected {CANVAS}x{CANVAS}"

    # The segment: strip its start offset, then fit the square. A raw capture is
    # 2304x1926 — scaled to the canvas width it is 1152x963, and the remaining
    # rows are padded rather than cropped, because cropping would cut the demo.
    vf = ["setpts=PTS-STARTPTS"]
    if (sw, sh) != (CANVAS, CANVAS):
        vf.append(f"scale={CANVAS}:-2")
        vf.append(f"pad={CANVAS}:{CANVAS}:(ow-iw)/2:(oh-ih)/2:color=black")
    vf.append("setsar=1")
    # HOLD the last frame if the footage runs out before Sarah stops talking.
    # `overlay` ends when its BACKGROUND ends, so a segment even one frame short
    # truncates the scene — catalogue-search delivered 188 of 248 frames that
    # way, and the shortfall reads as "the section was cut off", not as a
    # missing hold. tpad clones the final frame; -frames:v then cuts to length,
    # so an over-long pad costs nothing.
    vf.append("tpad=stop_mode=clone:stop_duration=60")

    dur = n / FPS
    run(["ffmpeg", "-v", "error",
         "-i", seg,
         "-c:v", "libvpx-vp9", "-i", av,          # the decoder MUST precede -i
         "-filter_complex",
         f"[0:v]{','.join(vf)}[bg];"
         f"[1:v]setpts=PTS-STARTPTS,format=yuva420p[fg];"   # yuva in the FILTER
         f"[bg][fg]overlay=0:0:format=auto[v]",
         "-map", "[v]",
         "-map", "1:a",
         # Pad the voice to the picture's EXACT length. `-t` cannot do this: it
         # cuts on an AAC frame boundary, leaving each scene 10-20ms short, and
         # the concat demuxer lays audio and video end-to-end separately — so
         # those milliseconds accumulate down the whole video. That is the drift
         # that reached 13.8 seconds before it was understood.
         "-af", f"apad=whole_dur={dur:.6f}",
         "-frames:v", str(n),                     # -frames:v, never -t
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", "-r", str(FPS),
         "-c:a", "aac", "-b:a", "128k",
         "-movflags", "+faststart", "-y", out])

    gn, gd, _, _, _ = probe(out)
    ga = audio_len(out)
    return (gn, gd, ga, n, dur), None


def report(rows):
    print(f"\n    {'scene':30s} {'frames':>7} {'video':>9} {'audio':>9} {'A/V':>8}")
    print(f"    {'-' * 30} {'-' * 7} {'-' * 9} {'-' * 9} {'-' * 8}")
    bad = []
    for label, got, err in rows:
        if err:
            print(f"    {label:30s}   {err}")
            bad.append(label)
            continue
        gn, gd, ga, want_n, want_d = got
        flag = ""
        if gn != want_n:
            flag = f"  ✗ {want_n} expected"
            bad.append(label)
        elif abs(gd - want_d) > 0.05:
            flag = f"  ✗ clock off {gd - want_d:+.3f}s"
            bad.append(label)
        elif abs(ga - gd) > 0.05:
            flag = f"  ✗ audio off {ga - gd:+.3f}s"
            bad.append(label)
        print(f"    {label:30s} {gn:7d} {gd:8.3f}s {ga:8.3f}s {ga - gd:+7.3f}s{flag}")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--scene", type=int, nargs="*", help="only these scene numbers")
    ap.add_argument("--join", type=int, metavar="N",
                    help="after the scenes pass, join them into _v<N>.mp4")
    ap.add_argument("--rebuild", action="store_true",
                    help="rebuild a scene even if its mp4 is already there")
    a = ap.parse_args()

    F = os.path.abspath(a.folder)
    sroot = PTH.sandbox_root(F)
    vdir = os.path.join(F, "video")
    os.makedirs(vdir, exist_ok=True)

    scenes = sorted(d for d in os.listdir(sroot)
                    if d[:2].isdigit() and os.path.isdir(os.path.join(sroot, d)))
    if a.scene:
        want = {f"{n:02d}" for n in a.scene}
        scenes = [s for s in scenes if s[:2] in want]
    if not scenes:
        sys.exit("  no sandbox scenes matched")

    print(f"\n  {os.path.basename(F)} — {len(scenes)} scene(s)\n")
    rows = []
    for s in scenes:
        label = s[3:] or s
        out = os.path.join(vdir, f"{label}_v1.mp4")
        if os.path.exists(out) and not a.rebuild:
            gn, gd, _, _, _ = probe(out)
            ga = audio_len(out)
            an, _, _, _, _ = probe(os.path.join(sroot, s, "avatar.webm"), alpha=True)
            rows.append((label, (gn, gd, ga, an, an / FPS), None))
            continue
        print(f"    building {label} ...")
        got, err = build_one(os.path.join(sroot, s), out, label)
        rows.append((label, got, err))

    bad = report(rows)
    total = sum(r[1][0] for r in rows if r[1])
    print(f"\n    {total} frames, {total / FPS:.2f}s expected")

    if bad:
        print(f"\n  ✗ {len(bad)} scene(s) did not pass: {', '.join(bad)}")
        print("    Fix these before joining. A joined video hides them.\n")
        return 1
    print("\n  ✓ every scene passes: frame count, clock and audio all agree.\n")

    if a.join is None:
        print("    Nothing joined. Re-run with --join <N> when you are ready.\n")
        return 0
    if a.scene:
        sys.exit("  --join needs every scene built, not a subset. Drop --scene.\n")

    doc = json.load(open(PTH.script(F)))
    store, title = doc.get("store", "video"), doc.get("title", "").lower().replace(" ", "-")
    out = os.path.join(vdir, f"{store}_{title}_v{a.join}.mp4")
    lst = os.path.join(vdir, ".join.txt")
    with open(lst, "w") as fh:
        for label, _, _ in rows:
            p = os.path.join(vdir, f"{label}_v1.mp4").replace("'", r"'\''")
            fh.write(f"file '{p}'\n")
    # The concat DEMUXER, safe here only because every scene's audio was already
    # padded to its own picture. It lays the two streams end-to-end separately,
    # so any per-scene deficit would accumulate across the whole video.
    run(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
         "-c", "copy", "-movflags", "+faststart", "-y", out])
    os.remove(lst)

    gn, gd, _, _, _ = probe(out)
    ga = audio_len(out)
    print(f"    v{a.join}:  {gn} of {total} frames   video {gd:.2f}s   "
          f"audio {ga:.2f}s   drift {ga - gd:+.3f}s")
    print(f"           {os.path.getsize(out) / 1e6:.1f} MB")
    if gn != total:
        print(f"\n  ✗ the join lost {total - gn} frame(s).\n")
        return 1
    print(f"\n  ✓ {out}\n")

    snap = os.path.join(vdir, f"script_v{a.join}.json")
    if not os.path.exists(snap):
        json.dump(doc, open(snap, "w"), indent=2, ensure_ascii=False)
        print(f"    script snapshotted as script_v{a.join}.json\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
