"""
SHIM — the real module is editor_base/paths.py.

This file used to be one of three byte-identical copies (here,
mp4_splitter/, segment_avatar_editor/). They were merged into
editor_base/ on 2026-09-03 under Carson's Option A.

It stays as a re-export for one reason: nine scripts in build/ do
`import paths as PTH`, resolved by having shared/ on sys.path, and one
of them — build/assemble_video.py — is someone else's uncommitted work
that must not be edited. A shim keeps every one of them working without
touching a line of them.

Nothing new should import this. Import editor_base.paths directly.
"""
import os as _os
import sys as _sys

# This shim is imported by scripts that put shared/ on sys.path but not
# the repo root, so it puts the root there itself before reaching for
# editor_base. Without this, `import paths` from build/ dies with
# ModuleNotFoundError: No module named 'editor_base'.
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

from editor_base.paths import *      # noqa: F401,F403
from editor_base import paths as _p
import sys as _sys

# `from paths import *` skips underscore-prefixed names and anything not
# in __all__; the callers use several of those (_newest, SEG_RE, ...), so
# hand the whole module's namespace over rather than guessing which.
_sys.modules[__name__].__dict__.update(
    {k: v for k, v in vars(_p).items() if k not in ("__name__", "__doc__", "__file__")})
