"""
SHIM — the real module is editor_base/vtt.py.

Byte-identical to segment_avatar_editor/vtt.py until 2026-09-03, when both
were merged into editor_base/ under Carson's Option A.

Kept as a re-export for the same reason as shared/paths.py: scripts in
build/ do `import vtt as vtt_mod`, resolved by having shared/ on sys.path.
A shim keeps them working without editing them.

Nothing new should import this. Import editor_base.vtt directly.
"""
import os as _os
import sys as _sys

# Imported by scripts that put shared/ on sys.path but not the repo root,
# so it puts the root there itself before reaching for editor_base.
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

from editor_base.vtt import *        # noqa: F401,F403,E402
from editor_base import vtt as _v    # noqa: E402

# `import *` skips underscore names and honours __all__; callers use several
# of those, so hand the whole namespace over rather than guessing which.
_sys.modules[__name__].__dict__.update(
    {k: v for k, v in vars(_v).items() if k not in ("__name__", "__doc__", "__file__")})
