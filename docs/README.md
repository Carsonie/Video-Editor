# docs

The HeyGen knowledge `PIPELINE.md` cites. Brought over 2026-08-26 so the
playbook can answer *why*, not just *what*.

| File | What it is |
|---|---|
| `INSTRUCTIONAL.md` | the master guide: raw recording → finished narrated video |
| `Instructional_Lessons_Learned.md` | what went wrong on the pilot, and the pipeline that came out of it |
| `Video_Goal.md` | what a help video is FOR — the original brief |
| `avatar_compositing.md` | the compositing reference |
| `HEYGEN_RULES.md` | standing rules for HeyGen work. Rule 1: never edit a deliverable in place |
| `HANDOFF_example_paddle_sports.md` | one video's handoff, kept as the shape of a good one |
| `heygen_api.md`, `heygen_api_addendum.md` | the API reference |
| `avatar_launch.md`, `get_all_avatar_images.md`, `get_all_voices.md` | avatar and voice lookups |

## What did NOT come, and why

The `.py` scripts beside these docs — `generate_avatar_video.py`,
`find_avatar.py`, `get_all_voices.py`, `get_all_avatar_images.py` — stayed in
`Basic_E2E_Testing`.

`build/render_narration.py` replaced them. It is not an API wrapper: it retries
429/5xx with backoff, writes job ids the instant they exist, and **adopts**
renders already submitted so a re-run never pays twice. A `502` once orphaned
seven already-charged renders, which is why those guardrails exist. A second,
simpler path to the same paid endpoint is a way to lose money quietly.

Where these documents mention those scripts, read it as history.

## These are records, not instructions

They were written across the HeyGen work from June onwards. Where one disagrees
with `PIPELINE.md`, `PIPELINE.md` wins — it is the one kept current. Where one
disagrees with `CLAUDE.md`, `CLAUDE.md` wins.
