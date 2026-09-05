# ⛔ DO NOT TOUCH — the six test suites' source footage

Three clips. Every one of `tests/`' suites builds its disposable store from
these, so **deleting, renaming, re-encoding or "tidying" anything in this
folder breaks all six at once.**

```
segment-v6.mp4       164 KB    the demo footage
avatar-v1.webm       1.8 MB    Sarah, VP9 with real alpha
narration-v1.webm    1.7 MB    the raw HeyGen render
```

They never change. They are not a working copy of anything, they are not a
version of a scene, and they are not covered by any keep-N rule.

## Why they live here

Until 2026-09-05 the suites read them from ski-demo's
`videos/01-first-time-ordering/dev/01-login-and-code/`. That was fine until
`dev/` became Carson's own safety mirror of `sandbox/` — a folder that is
**archived and replaced wholesale** every time he finishes a working session.

The first refresh moved `dev/` to `z_History` and would have killed all six
suites: the scene had also been renamed (`01-login-and-code` →
`01-intro-and-login`), so no path would have resolved. The tests were sitting
on ground that was designed to move.

They are here now, beside the code that reads them, where nothing else has a
reason to go.

## Not in git, on purpose

This repo keeps video out of git — `Customers/**`, `cache/`, every `.mp4`
and `.webm`. These follow that rule (see `.gitignore`), so **this README is
the only thing here that is committed**, which is the point: the rule
travels even though the bytes do not.

The cost is that a fresh clone cannot run the suites until these three files
are put back. That was already true before the move; nothing got worse.

## If they ever go missing

They came from ski-demo's original 12-scene `dev/` cut, archived at:

```
z_History/dev-20260905-112452/01-login-and-code/
```

`tests/fixture.py` points here via `SRC`. Nothing else references this
folder — and nothing else should.
