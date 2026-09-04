"""
SHIM — the real module is editor_base/frames.py.

776 lines, and it existed three times over (here, mp4_splitter/,
segment_avatar_editor/) differing by ONE line of real code: the name of
the cache folder. Merged into editor_base/ on 2026-09-03, where that one
line became configuration — see editor_base.frames.use_cache().

Kept as a re-export so shared/serve.py and anything else resolving
`import frames` through shared/ keeps working untouched.

Nothing new should import this. Import editor_base.frames directly.
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

from editor_base.frames import *     # noqa: F401,F403
from editor_base import frames as _f
_sys.modules[__name__].__dict__.update(
    {k: v for k, v in vars(_f).items() if k not in ("__name__", "__doc__", "__file__")})
