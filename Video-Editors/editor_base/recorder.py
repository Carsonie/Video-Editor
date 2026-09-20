"""
The one way an editor reaches the RECORDER's scripts.

Making the raw mp4 belongs to `Basic_E2E_Testing`; everything after it belongs
to this repo. A handful of tools sit on that boundary — they read a capture and
its `script.json` and rewrite the cuts, the timing and the voice — so they stay
with the recorder and an editor drives them rather than re-implementing them.

⚠ THE EDITORS WERE EACH INVENTING THEIR OWN PATH TO THEM. vtt_editor derived it
from this repo's parent directory with a `BASIC_E2E_REPO` override;
segment_avatar_editor hard-coded `~/Rentify/Basic_E2E_Testing/...` with an
override of its own. Two spellings of one fact is one of them going stale in
silence on the day somebody moves a checkout. This module is that fact, once.

    from editor_base import recorder
    recorder.script("stretch_request.py")      # absolute path, or a clear error
    recorder.run("stretch_request.py", [folder])

`BASIC_E2E_REPO` overrides the repo root for a checkout somewhere else. Nothing
here knows what any individual script does — that stays with the caller, which
is the editor that has a reason to run it.
"""
import os
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EDITORS = os.path.dirname(HERE)                      # Video-Editors/
VE_ROOT = os.path.dirname(EDITORS)                   # the Video-Editor repo


def repo():
    """Where Basic_E2E_Testing is checked out."""
    return os.path.expanduser(os.environ.get(
        "BASIC_E2E_REPO", os.path.join(os.path.dirname(VE_ROOT), "Basic_E2E_Testing")))


def scripts_dir():
    return os.path.join(repo(), "Master_Flows", "Recorder", "scripts")


def script(name):
    """
    The absolute path to one recorder script.

    ⚠ RAISES RATHER THAN RETURNING A PATH THAT IS NOT THERE. A missing script
    used to surface as an ffmpeg-shaped error from deep inside a job, or as a
    500 with a stack trace in it; the useful message is which file is missing
    and which environment variable moves the search.
    """
    p = os.path.join(scripts_dir(), name)
    if not os.path.isfile(p):
        raise FileNotFoundError(
            f"{name} is not in {scripts_dir()} — set BASIC_E2E_REPO if that "
            f"repo is checked out somewhere else")
    return p


def run(name, args, timeout=1800):
    """
    Run one recorder script and hand back what it said, never raising on a
    non-zero exit: an editor turns that into a message on the page, and a job
    that failed loudly in a subprocess must not also kill the request thread.

    ⚠ THE EDITOR NEVER ASSEMBLES ffmpeg ITSELF. Those recipes live in
    stretch_scenes.py and narrate_mac.py, where the edge cases are already
    written down — the keyframe spacing, the silent audio track, the cache key.
    A second copy in an editor is a second copy to get wrong.
    """
    try:
        cmd = ["python3", script(name)] + [str(a) for a in args]
    except FileNotFoundError as e:
        return {"ok": False, "code": -1, "seconds": 0.0, "out": "", "err": str(e),
                "cmd": f"python3 {name} (not found)"}
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
