# CLAUDE.md — Rentify Help Videos (HeyGen)

Standing rules for this project. Claude must follow these on every session and every edit.
They override convenience.

---

## RULE 1 — Never edit a deliverable in place. Always copy + increment.

Whenever making an irreversible change (any ffmpeg cut / splice / overlay / concat, or any
operation producing a video deliverable), output to a NEW file with an incremented number
suffix. Never overwrite the file being edited.

- Editing `first-time-ordering-5.mp4` → write the result to `first-time-ordering-6.mp4`.
  Leave `-5` untouched as a fallback. Next edit: `-6` → `-7`, etc.
- NEVER `mv -f /tmp/out.mp4` over a file Claude just read from — destroys the original, no undo.
- NEVER have one ffmpeg command read and write the same filename — corrupts the file.
- Find the latest good version any time: `ls -lat videos/first_time_ordering/final/*.mp4 | head`

### Why (real incident)
A multi-step splice wrote to `/tmp`, then `mv -f /tmp/out5.mp4 first-time-ordering-5.mp4`.
One intermediate piece was bad, the concat produced a 15s truncated file, and the `mv`
overwrote the good `-5.mp4`. Unrecoverable because: Claude's sandbox can't reach the Mac
(no remote undo), ffmpeg keeps no backups, and the original was overwritten in place. Only
the separate clean pilot `first-time-ordering.mp4` survived.

### Pattern
```bash
# WRONG — destroys source:
ffmpeg ... -i first-time-ordering-5.mp4 ... /tmp/out.mp4
mv -f /tmp/out.mp4 videos/first_time_ordering/final/first-time-ordering-5.mp4

# RIGHT — increment, keep original:
ffmpeg ... -i first-time-ordering-5.mp4 ... videos/first_time_ordering/final/first-time-ordering-6.mp4
```

---

## RULE 2 — Verify intermediate pieces before splicing.

Before any concat/splice, confirm every input piece is valid (non-zero duration, expected
streams). A broken piece silently yields a truncated or empty output.
```bash
for f in /tmp/segA.mp4 /tmp/middle.mp4 /tmp/segB.mp4; do
  echo "$f:"; ffmpeg -i "$f" 2>&1 | grep Duration
done
```

---

## RULE 3 — Use `-y` on scripted ffmpeg, but only when writing to NEW names.

`-y` avoids the "overwrite? [y/N]" prompt that stalls pasted multi-command blocks. Safe ONLY
because Rule 1 means output is always a fresh incremented filename, never the source.

---

## RULE 4 — There is no undo. Claude cannot reach the Mac.

Claude's sandbox cannot read or write the user's files. All changes happen via commands the
user runs in their own terminal. Claude can only VIEW files the user places under
`/Users/carsonkramer/Documents`. Claude cannot revert anything — the numbered fallback files
(Rule 1) are the ONLY recovery mechanism. Treat every overwrite as permanent.

---

## Project quick-reference (so sessions stay consistent)

- Avatar "Sarah": Pamela look, avatar_id `468eabb3326a4d8587ba29d065b1eba7`
  (group `0484e7d80416443388aa1763f684f019`).
- Voice: Sarah (Starfish engine) `04d0ae1d0af2489ca7d3bb402a39a890`.
  (HeyGen's catalog name for this voice is "Derya" — use that when searching `heygen voice list`.)
- Brand background: `#E8F4F8`. Canvas: 1152x1080 @ 60fps, yuv420p, AAC.
- Generate clips via `Video Generation` (verbatim script), NOT the Video Agent.
- Transparent corner clips: `--webm`; ALWAYS decode with `-c:v libvpx-vp9` (alpha) in ffmpeg.
- Skills live in `.claude/skill/hey_gen/` (avatar/voice discovery, launch spec, compositing).

## Folder layout (current)

- Per-video media is namespaced: `videos/<slug>/{source,final,temp}/`. The on-disk
  video folder uses underscores even though the slug uses hyphens — slug
  `first-time-ordering` → folder `videos/first_time_ordering/`. `config/` and
  `audio/` keep the hyphenated slug. `paths.ts` handles the conversion.
- Each `videos/<slug>/` subfolder has a `README.md` explaining its contents.
- Avatar assets/tooling live under `avatars/`: shared tools (`find_avatar.py`,
  `v3_groups.json`) at the root, and one subfolder per avatar (`avatars/pamela/`,
  `avatars/annie/`, `avatars/dt/`). New avatars get their own subfolder.
- Reference docs are in `_README/`; older handoffs are parked in `_archive/`.
