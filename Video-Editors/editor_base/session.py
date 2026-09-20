"""
One line per action, in every editor's own log.

⚠ THIS WAS BORROWED, NOT SHARED. Frame Blender and Avatar Editor each did
`import serve as main_serve` and then wrote into that module's globals —
`main_serve.ACTIONS = ...`, `main_serve.SESSION_LOG = ...` — to make ITS logger
write THEIR file. So two editors were configured by reaching into a third
editor's module state, and the log you got depended on which import ran last.

Here each editor configures its own logger and nothing reaches into anything:

    from editor_base import session
    session.configure(os.path.join(LOGS, "frame_blender_20260921.log"),
                      ACTIONS, off=args.no_session_log)
    session.log(path, payload, result, status)

`actions` maps a route to (label, keys-worth-showing). A route that is not in
it is not logged — that is how the noise stays out: every GET of a frame image
would otherwise bury the lines that say what someone did.
"""
import os
import time

# Set by configure(). Module state on purpose: one process serves one editor.
_LOG = None
_ACTIONS = {}
_OFF = False

# What a result is worth saying back. A handler returns plenty; these are the
# numbers a person reads a log for.
RESULT_KEYS = ("nb_frames", "current", "span", "actual", "dropped_marks",
               "duration_s", "wrote", "scenes", "error")


def configure(log_path, actions, off=False, result_keys=None):
    """Point this process's logger at its own file and its own route table."""
    global _LOG, _ACTIONS, _OFF, RESULT_KEYS
    _LOG, _ACTIONS, _OFF = log_path, dict(actions or {}), bool(off)
    if result_keys:
        RESULT_KEYS = tuple(result_keys)
    if _LOG and not _OFF:
        os.makedirs(os.path.dirname(_LOG), exist_ok=True)
    return _LOG


def log_path():
    """Where this process is writing, for the line an editor prints at boot."""
    return _LOG or "(not configured)"


def header(lines):
    """Write the few lines that open a session — which editor, which port."""
    if not _LOG or _OFF:
        return
    try:
        with open(_LOG, "a") as fh:
            for line in lines:
                fh.write(line.rstrip() + "\n")
            fh.write("\n")
    except OSError:
        pass


def log(path, payload, result, status):
    """
    One line per action. NEVER RAISES: a log that can break the editor is worse
    than no log, and this runs inside a request handler.
    """
    entry = _ACTIONS.get(path)
    if entry is None or _OFF or not _LOG:
        return
    label, keys = entry
    try:
        args = " ".join(f"{k}={payload.get(k)}" for k in keys if payload.get(k) is not None)
        # what it acted on: a cache slug for frame work, a store for the rest
        who = payload.get("slug") or payload.get("root") or ""
        res = result if isinstance(result, dict) else {}
        if status != 200 or res.get("error"):
            tail = f"REFUSED: {res.get('error', status)}"
        else:
            tail = "  ".join(f"{k}={res[k]}" for k in RESULT_KEYS if k in res)
        with open(_LOG, "a") as fh:
            fh.write(f"{time.strftime('%H:%M:%S')}  {label:<14} {who:<26} "
                     f"{args}  {tail}".rstrip() + "\n")
    except Exception:
        pass
