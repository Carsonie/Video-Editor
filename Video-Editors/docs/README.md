# docs

The HeyGen knowledge `PIPELINE.md` cites. Brought over 2026-08-26 so the
playbook can answer *why*, not just *what*.

| File | What it is |
|---|---|
| `INSTRUCTIONAL.md` | the master guide: raw recording → finished narrated video |
| `Instructional_Lessons_Learned.md` | what went wrong on the pilot, and the pipeline that came out of it |
| `Video_Goal.md` | what a help video is FOR — the original brief |
| `HEYGEN_RULES.md` | standing rules for HeyGen work. Rule 1: never edit a deliverable in place |
| `HANDOFF_example_paddle_sports.md` | one video's handoff, kept as the shape of a good one |

## ⚠ SIX FILES LEFT THIS FOLDER ON 2026-09-21 — THEY WERE DUPLICATES

`heygen_api.md`, `heygen_api_addendum.md`, `avatar_compositing.md`,
`avatar_launch.md`, `get_all_voices.md` and `get_all_avatar_images.md` were
**byte-identical copies**. They now live once, in the **`heygen` skill**:

    .claude/skills/heygen/

That folder registers as a skill and loads on its own; this one never could.
Two copies of one fact is one of them going stale in silence, and it was
already happening — the copies here sat untouched from 2026-08-26 while the
HeyGen API moved on. `PIPELINE.md` and the `sarah-library` skill were
re-pointed at the same time.

⚠ **DO NOT COPY THEM BACK.** If this playbook needs to answer *why*, cite the
skill by path. `git show` has the deleted copies if you ever need to compare.

## What did NOT come, and why

The `.py` scripts beside these docs — `generate_avatar_video.py`,
`get_all_voices.py`, `get_all_avatar_images.py` — never came here. They are in
the `heygen` skill now, beside the docs they belong to. `find_avatar.py` is in
`Studio/avatars/`, with the avatar data it reads.

`build/render_narration.py` replaced them. It is not an API wrapper: it retries
429/5xx with backoff, writes job ids the instant they exist, and **adopts**
renders already submitted so a re-run never pays twice. A `502` once orphaned
seven already-charged renders, which is why those guardrails exist. A second,
simpler path to the same paid endpoint is a way to lose money quietly.

Where these documents mention those scripts, read it as history.

## `z_History/`

`PIPELINE_pre-2026-08-28.md` — the playbook as it stood before it was rewritten,
1,323 lines of it. It had become a record of the struggle rather than the
procedure: three dated session logs correcting each other, a `final/` layout no
store uses, an `assemble_video.py` build that was abandoned, and a HeyGen-native
pivot that was tried and dropped. Kept because it holds real findings that were
paid for. **It is not instructions.**

## These are records, not instructions

They were written across the HeyGen work from June onwards. Where one disagrees
with `PIPELINE.md`, `PIPELINE.md` wins — it is the one kept current. Where one
disagrees with `CLAUDE.md`, `CLAUDE.md` wins.
