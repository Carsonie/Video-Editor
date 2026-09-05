#!/usr/bin/env python3
"""
Build a complete "Sarah Opening" for any help video, from two script lines.

The opening is identical in every video — Sarah centred on a dark screen for
the intro, then the first scene fades in as she morphs down into the corner and
holds. Only the WORDS change per video. This builds the whole thing:

    intro line  -> HeyGen alpha clip -> centred on canvas
    bridge line -> HeyGen alpha clip -> morph to corner + corner hold
                                     -> FRONT track (transparent, has the audio)
    dark + first scene fading in     -> REAR track (opaque, silent)
    overlay front over rear          -> scenes/OPENING.mp4 (or final/ if no scenes/)

Why two clips and not one: the background must stay dark until the intro
FINISHES, so the morph needs footage that exists after the intro's last word.
One clip cannot do it - you would freeze her or move her mid-sentence.

Full reasoning, and the traps behind every step, are in
`.claude/agents/6_end-customer-help-video-creations.md` -> "Sarah Opening".

USAGE
-----
    python3 build_sarah_opening.py \\
      --intro  "Hi, I'm Sarah. Let me show you how to place your first order with <Store>." \\
      --bridge "Let's get started. Here are the steps to complete your first <thing> rental." \\
      --scene1 segments/segment-01-login.mp4 \\
      --outdir .

    # re-assemble without paying for new clips (uses the ones already on disk)
    python3 build_sarah_opening.py --skip-generate --scene1 ... --outdir .

⚠ Generating costs real money against the HeyGen wallet - two clips per run.
  Check the script lines before running; a typo costs another render.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from morph_avatar_corner import measure, run  # noqa: E402

try:
    from PIL import Image  # noqa: F401
except ImportError:
    sys.exit("Pillow required:  .claude/agent-tools/venv/bin/pip install pillow")

API = "https://api.heygen.com/v3"
AVATAR_ID = "468eabb3326a4d8587ba29d065b1eba7"   # Sarah / Pamela look
VOICE_ID = "04d0ae1d0af2489ca7d3bb402a39a890"    # Derya, Starfish
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ENV = os.path.join(REPO, "Help_Videos", "HeyGen", ".env.local")


def api_key():
    """Read the key from HeyGen's own .env.local. Never printed or logged."""
    try:
        with open(ENV) as f:
            for line in f:
                m = re.match(r'\s*(?:export\s+)?HEYGEN_API_KEY\s*=\s*["\']?([^"\'\s]+)', line)
                if m:
                    return m.group(1)
    except OSError:
        pass
    sys.exit(f"HEYGEN_API_KEY not found in {ENV}")


def post_json(url, payload, key):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"X-Api-Key": key, "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def get_json(url, key):
    req = urllib.request.Request(url, headers={"X-Api-Key": key})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def generate(script, title, key, dest):
    """One transparent avatar clip. `output_format: webm` is the whole switch."""
    print(f"  generating: {title}")
    # NOTE the FLAT schema. Nesting script inside `input` (as a studio scene
    # does) fails with "An audio source is required" - a confusing error,
    # because the script IS there, just one level too deep.
    r = post_json(f"{API}/videos", {
        "type": "avatar", "avatar_id": AVATAR_ID, "script": script,
        "voice_id": VOICE_ID, "title": title,
        "resolution": "1080p", "output_format": "webm",
    }, key)
    if "error" in r and r["error"]:
        sys.exit(f"generate failed: {r['error']}")
    vid = r["data"]["video_id"]
    for _ in range(60):
        time.sleep(12)
        d = get_json(f"{API}/videos/{vid}", key).get("data", {})
        if d.get("status") == "completed":
            urllib.request.urlretrieve(d["video_url"], dest)
            print(f"    -> {dest}")
            return dest
        if d.get("status") == "failed":
            sys.exit(f"render failed: {d}")
    sys.exit("timed out waiting for the render")


def probe(path, entries):
    out = subprocess.run(["ffprobe", "-v", "error", "-c:v", "libvpx-vp9",
                          "-show_entries", entries, "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.strip()
    return out.splitlines()


# ⚠ 25, NOT 30 — and this must match everywhere downstream.
#
# HeyGen renders avatars at 25fps and offers no way to change it, and OBS now
# records at 25 to match (RECORD_FPS in Master_Flows/Recorder/lib/obs.ts). Both
# sources are therefore 25. Compositing at 30 resampled BOTH of them, duplicating
# one frame in six in each — and before the OBS change it was worse in a
# different way: the demo was native 30 and only Sarah was resampled.
#
# Anything that converts seconds to frames must divide by THIS, not by a literal.
# `round(seconds * 30)` was scattered through the hold arithmetic and would make
# every hold 20% too long at 25.
FPS = 25

# The avatar's clips live in a folder named for the AVATAR, not for the job they
# do. `sarah_intro_tools` was accurate when the only thing in it was the opening;
# it now also holds the closing morph, the close-out line and the exported
# bookends, and a second presenter would need a folder of their own. Renamed
# 2026-08-21 to `sarah_clips` so the pattern extends: `<name>_clips`.
SARAH_DIR = "sarah_clips"
LEGACY_SARAH_DIRS = ("sarah_intro_tools",)


def sarah_dir(folder):
    """
    Where this store's avatar clips live. Prefers `<final>/sarah_clips/`, accepts
    the pre-rename `sarah_intro_tools/`, and falls back to `<final>/` itself so a
    store that never had the folder keeps working rather than failing obscurely.

    ⚠ Several of these are PAID HeyGen renders and the build scripts overwrite
    them by name with no backup. Losing them costs money to replace.
    """
    import os
    d = os.path.join(folder, SARAH_DIR)
    if os.path.isdir(d):
        return d
    for legacy in LEGACY_SARAH_DIRS:
        ld = os.path.join(folder, legacy)
        if os.path.isdir(ld):
            return ld
    return folder


def archive_existing(od, names):
    """
    Move any existing opening asset into `z_History/<timestamp>/` before a build
    overwrites it.

    ⚠ This exists because the previous behaviour destroyed PAID renders. On
    2026-08-20 a re-run of this script overwrote `sarah-intro-alpha.webm` and
    `sarah-bridge-alpha.webm` — two HeyGen clips that had been paid for — with no
    backup, and the only surviving trace of that opening was the composited
    video built from it. A#6 had already worked around the same hazard by hand
    the day before, backing up the morph before the tool could clobber it.

    Moved, not copied: the build is about to replace them, so leaving a copy in
    place would just be the stale file the next run archives again.
    """
    import os, shutil, datetime
    present = [n for n in names if os.path.exists(os.path.join(od, n))]
    if not present:
        return None
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dest = os.path.join(od, "z_History", stamp)
    os.makedirs(dest, exist_ok=True)
    for n in present:
        shutil.move(os.path.join(od, n), os.path.join(dest, n))
    print(f"  archived {len(present)} existing asset(s) -> z_History/{stamp}/")
    for n in present:
        print(f"      {n}")
    return dest


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--intro"); p.add_argument("--bridge")
    p.add_argument("--scene1", required=True, help="first demo scene, becomes the reveal")
    p.add_argument("--outdir", default=".")
    # ⚠ Must match assemble_video.py's CANVAS/CORNER, or the opening it builds
    # cannot be composited with the scenes. 1152 matches the OBS capture width so
    # the demo is never rescaled (1080 cost 21% of the text's edge sharpness);
    # 320 keeps the corner at the same 27.8% of the canvas that 300/1080 did.
    p.add_argument("--canvas", type=int, default=1152)
    p.add_argument("--corner", type=int, default=320)
    p.add_argument("--inset", type=int, default=0)
    p.add_argument("--morph", type=float, default=1.2, help="morph duration, seconds")
    p.add_argument("--fade", type=float, default=0.6, help="background fade-in, seconds")
    p.add_argument("--skip-generate", action="store_true",
                   help="reuse sarah-intro-alpha.webm / sarah-bridge-alpha.webm already on disk")
    a = p.parse_args()

    o = a.outdir
    os.makedirs(o, exist_ok=True)
    # Opening assets live in Sarah_intro_tools/ when it exists, so they are not
    # loose in the root of final/. Created here if missing, so a first run for a
    # new store lays the folder down rather than scattering.
    od = os.path.join(o, SARAH_DIR)
    os.makedirs(od, exist_ok=True)

    # Archive whatever is already here BEFORE writing anything. Includes the two
    # raw clips only when they are about to be regenerated — with
    # --skip-generate they are the INPUT and must stay put.
    _doomed = [f"sarah-intro-{a.canvas}-alpha.webm",
               "sarah-bridge-transition-to-corner.webm",
               f"sarah-bridge-corner-{a.corner}-alpha.webm",
               "TRACK_front_sarah.webm", "TRACK_rear_background.mp4"]
    if not a.skip_generate:
        _doomed += ["sarah-intro-alpha.webm", "sarah-bridge-alpha.webm"]
    archive_existing(od, _doomed)
    intro_raw = os.path.join(od, "sarah-intro-alpha.webm")
    bridge_raw = os.path.join(od, "sarah-bridge-alpha.webm")

    if not a.skip_generate:
        if not (a.intro and a.bridge):
            sys.exit("--intro and --bridge are required unless --skip-generate")
        key = api_key()
        generate(a.intro, "Sarah intro alpha", key, intro_raw)
        generate(a.bridge, "Sarah corner transition alpha", key, bridge_raw)
    for f in (intro_raw, bridge_raw):
        if not os.path.exists(f):
            sys.exit(f"missing {f} - run without --skip-generate")

    # ---- measure both clips. HeyGen's output size is NOT consistent between
    # calls (1080x1920 and 608x1080 seen for identical requests), so nothing
    # here may assume dimensions.
    mi = measure(intro_raw, 2.0)
    mb = measure(bridge_raw, 0.5)
    print(f"  intro  {mi['w']}x{mi['h']}  subject cx={mi['subject_cx']}")
    print(f"  bridge {mb['w']}x{mb['h']}  subject cx={mb['subject_cx']}")

    # --scene1 is relative to the OUTDIR, not to wherever the caller happens to
    # be standing. Resolving it against the cwd is how a bike-demo run rendered
    # both paid clips and then died on "segments/segment-01-login.mp4: No such
    # file" at the very last step.
    if a.scene1 and not os.path.isabs(a.scene1) and not os.path.exists(a.scene1):
        cand = os.path.join(o, a.scene1)
        if os.path.exists(cand):
            a.scene1 = cand

    C = a.canvas
    # Centre HER, not the frame - she sits off-centre in HeyGen's output.
    iw = round(C * mi["w"] / mi["h"])
    ipos = round(C / 2 - mi["subject_cx"] * (iw / mi["w"]))
    intro_dur = float(probe(intro_raw, "format=duration")[0])

    # ---- morph + corner element, from the BRIDGE clip's opening
    here = os.path.dirname(os.path.abspath(__file__))
    run([sys.executable, os.path.join(here, "morph_avatar_corner.py"),
         "--src", bridge_raw, "--outdir", od, "--start-at", "0", "--measure-at", "0.5",
         "--canvas", str(C), "--corner", str(a.corner), "--inset", str(a.inset),
         "--fps", str(FPS),   # pass it explicitly, do not rely on the default
         "--duration", str(a.morph)])
    morph = os.path.join(od, "sarah-bridge-transition-to-corner.webm")
    corner = os.path.join(od, f"sarah-bridge-corner-{a.corner}-alpha.webm")
    cx = cy = C - a.corner - a.inset

    # `assemble_video.py` reads `sarah-intro-<CANVAS>-alpha.webm`, so write it
    # here rather than leaving it to be produced by hand — bike-demo's had to be,
    # because this script only ever built the combined front track.
    intro_canvas = os.path.join(od, f"sarah-intro-{C}-alpha.webm")
    run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", intro_raw,
         "-filter_complex",
         f"color=c=black@0.0:s={C}x{C}:r={FPS},format=yuva420p[bg];"
         f"[0:v]scale={iw}:{C},format=yuva420p[s];"
         f"[bg][s]overlay=x={ipos}:y=0:shortest=1,format=yuva420p[v]",
         # ⚠ KEEP THE AUDIO. This clip carries Sarah's intro narration, and it
         # is the first piece of the front track — the track that carries ALL the
         # audio. Writing it with -an produces a silent front track, and the
         # final composite then dies on `-map 1:a: Stream map matches no streams`
         # after every paid render has already been made.
         "-map", "[v]", "-map", "0:a",
         "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "2M",
         "-c:a", "libopus", "-y", intro_canvas])
    print(f"  wrote {os.path.basename(intro_canvas)}")

    # ---- FRONT track: intro centred ++ morph ++ corner hold, one alpha clip
    front = os.path.join(od, "TRACK_front_sarah.webm")
    run(["ffmpeg", "-v", "error",
         "-c:v", "libvpx-vp9", "-i", intro_raw,
         "-c:v", "libvpx-vp9", "-i", morph,
         "-c:v", "libvpx-vp9", "-i", corner,
         "-filter_complex",
         f"color=c=black@0.0:s={C}x{C}:r={FPS},format=yuva420p[ibg];"
         f"[0:v]scale={iw}:{C},format=yuva420p[iv];"
         f"[ibg][iv]overlay=x={ipos}:y=0:shortest=1,fps={FPS},format=yuva420p[intro];"
         f"color=c=black@0.0:s={C}x{C}:r={FPS},format=yuva420p[cbg];"
         f"[2:v]trim=start={a.morph},setpts=PTS-STARTPTS[cc];"
         f"[cbg][cc]overlay=x={cx}:y={cy}:shortest=1,format=yuva420p[hold];"
         f"[1:v]fps={FPS},format=yuva420p[mv];"
         f"[intro][mv][hold]concat=n=3:v=1:a=0,format=yuva420p[v];"
         f"[0:a][2:a]concat=n=2:v=0:a=1[a]",
         "-map", "[v]", "-map", "[a]",
         "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "2M", "-c:a", "libopus",
         "-y", front])
    print(f"  wrote {front}")

    # ---- REAR track: dark for the intro, then scene 1 fading in.
    # Pad colour is SAMPLED from the scene's own edge - guessing it (#2A2A2A
    # against a real #212121) leaves a visible band across every frame.
    tmp = tempfile.mkdtemp()
    fr = os.path.join(tmp, "e.png")
    run(["ffmpeg", "-v", "error", "-ss", "1", "-i", a.scene1, "-frames:v", "1", "-update", "1", "-y", fr])
    im = Image.open(fr).convert("RGB")
    pad = "0x%02X%02X%02X" % im.getpixel((5, im.size[1] // 2))
    print(f"  sampled pad colour {pad}")

    rear = os.path.join(od, "TRACK_rear_background.mp4")
    bridge_dur = float(probe(bridge_raw, "format=duration")[0])
    run(["ffmpeg", "-v", "error",
         "-f", "lavfi", "-t", f"{intro_dur:.3f}", "-i", f"color=c={pad}:s={C}x{C}:r={FPS}",
         "-i", a.scene1,
         "-filter_complex",
         # HOLD scene 1's first frame under the bridge — do not play it. Playing
         # it consumes footage the scene needs for its own narration later.
         # ⚠ The held frame must be a SETTLED page. Freezing frame 0 of a clip
         # once froze a loading spinner ("three dots") for the whole 4.16s
         # bridge; a scene's first frames are often mid-render. Cut the scene to
         # start on the settled view, then hold that.
         f"[1:v]trim=duration=0.04,scale={C}:-2:flags=lanczos,pad={C}:{C}:0:({C}-ih)/2:color={pad},setsar=1,fps={FPS},"
         f"tpad=stop_mode=clone:stop_duration={bridge_dur:.3f},setpts=PTS-STARTPTS,"
         f"fade=t=in:st=0:d={a.fade}:color={pad}[s1];"
         f"[0:v]format=yuv420p,setsar=1[d];[d][s1]concat=n=2:v=1:a=0,format=yuv420p[v]",
         "-map", "[v]", "-c:v", "libx264", "-movflags", "+faststart", "-an", "-y", rear])
    print(f"  wrote {rear}")

    # ---- composite. Front is canvas-sized and transparent, so 0:0.
    # Write it into scenes/ when that folder exists, so there is ONE copy.
    # It used to land in final/ and get copied to scenes/ by hand, which meant
    # the scenes/ copy went stale the next time the opening was rebuilt — the
    # exact drift this repo keeps paying for.
    _sc = os.path.join(o, "scenes")
    out = os.path.join(_sc if os.path.isdir(_sc) else o, "OPENING.mp4")
    run(["ffmpeg", "-v", "error", "-i", rear, "-c:v", "libvpx-vp9", "-i", front,
         "-filter_complex", "[0:v][1:v]overlay=x=0:y=0:shortest=1,format=yuv420p[v]",
         "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-c:a", "aac",
         "-movflags", "+faststart", "-y", out])
    print(f"\n  OPENING: {out}")
    print(f"  intro ends {intro_dur:.2f}s | background fades in over {a.fade}s | "
          f"morph {a.morph}s | corner at {cx},{cy}")


if __name__ == "__main__":
    main()
