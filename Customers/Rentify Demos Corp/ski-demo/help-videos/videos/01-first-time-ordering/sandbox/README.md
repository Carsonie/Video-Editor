# sandbox/ — your edits, kept out of the originals

Mirrors `dev/` folder for folder. Drop a file in a scene's folder and the next
build uses it INSTEAD of the dev copy, without touching the dev copy.

    sandbox/05-dates-and-review/segment.mp4     replaces that scene's footage
                               narration.webm  replaces its voice
                               avatar.webm     replaces the editor's overlay

No version numbers here. These are yours and they are the newest thing you did;
versioning them would only reintroduce the question this layer exists to avoid —
which of my edits is the build using.

## Building from it

Nothing to switch on. `assemble_video.py` resolves sandbox first and PRINTS
every override before it starts:

    ⚠ SANDBOX OVERRIDE — this build is NOT the committed material:
        scene 5 dates-and-review — segment

Name such a build so its file says so too, e.g.
`sandbox/_builds/2026-08-22_scene5-recut.mp4`, and keep it out of `video/` —
that folder is for finished, reproducible videos only.

## Getting back to clean

Delete the file. There is no revert step, because nothing in `dev/` was ever
modified.
