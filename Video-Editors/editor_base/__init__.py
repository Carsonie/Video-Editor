"""
editor_base — the code every editor genuinely shares.

WHY THIS EXISTS (2026-09-03, Carson's Option A)
    The 2026-09-02 split gave each editor its own process, port and cache,
    and duplicated the code to match. A year later the measurement said the
    duplication had bought nothing:

        paths.py    byte-identical in three places
        frames.py   776 lines, three copies, differing by ONE line of real
                    code — the name of the cache folder

    Meanwhile Avatar Editor and Frame Blender never duplicated at all: they
    imported 13 symbols from shared/serve.py, the "old combined server that
    cannot be removed". So the two pairs had made opposite trade-offs and
    neither was clean.

    This package is the answer. What is genuinely common lives here once;
    what is genuinely per-editor stays in that editor.

WHAT MAY LIVE HERE
    Pure functions and shared constants. Frame extraction, path shapes,
    the ffmpeg encode recipe.

WHAT MAY NOT
    Routes. Request state. Page rendering. A Handler class or anything
    that takes `self`. If it knows about HTTP, it belongs to an editor.

THE ONE PIECE OF STATE, AND ITS RULE
    frames.CACHE is process-level CONFIGURATION, set once at startup by
    whichever editor imported it (see use_cache()). That is safe here for
    one reason only: every editor is its own OS process, which is the
    whole point of the 2026-09-02 split. If two editors are ever made to
    share a process, this becomes a real bug — they would fight over one
    cache path. Nothing else in here holds state.

THE RULE THAT COMES WITH IT
    A change to this package is not "one editor's change". It runs ALL
    FIVE suites — the four editors plus tests/test_editor_base.py — and
    CLAUDE.md names this as the single exception to "editor changes stay
    inside the one editor in scope".
"""
