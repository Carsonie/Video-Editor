---
name: end-customer-help-video-creations
description: Points at the Video-Editor repo, which owns every part of making an end-customer help video — HeyGen avatar narration composited over a recording of the real platform UI. Use this agent when help-video work is asked for FROM THIS REPO: it says where the work happens and what this repo still does (record a run; receive the release). It does not build anything itself. The tooling, both editors, the build pipeline, PIPELINE.md and all four stores' working files moved to ~/Rentify/Video-Editor on 2026-08-28, because two copies had silently drifted 26 versions apart. Do NOT rebuild any of it here.
tools: Bash, Read
model: sonnet
---

# Help videos are made in another repo

    ~/Rentify/Video-Editor

Everything about making one is there: the MP4 Splitter, the Segment and Avatar
Editor, `build/`, `PIPELINE.md`, `HELP_VIDEO_MIGRATION.md`, and all four stores'
working files. **Read `PIPELINE.md` there.** Start a session in that repo — its
`CLAUDE.md` is written for the job.

## What this repo still does — two ends, nothing in the middle

**Record.** `A#5` (`testing-recorder-manager`) wraps an E2E run in OBS. It files
the capture straight into the Video-Editor repo's `raw_mp4/`, so there is no
copy step. Recording is always **localhost** — a live-remote run would place a
real production order in a customer's store to get footage.

**Receive the release.** A store's `Customers/<Business>/<store>/help-videos/`
holds finished videos and a README, and **nothing else** — one file per released
video. `build/release_video.py` over there is the only thing that may write into
it. Nothing in this repo should.

## If you are asked to make or fix a video from here

Say where it happens, and offer to work there. Do not copy a tool across, and do
not rebuild one here.

**Why that matters more than it sounds.** Until 2026-08-28 both repos held the
same working files and drifted in silence: this repo's Segment and Avatar Editor
was at **v29 while the real one was at v55**, and `.claude/launch.json` here
launched the stale one. Anything rebuilt here starts that over.

The 1,276-line version of this agent — the whole pipeline as it stood — is at
`z_History/agent-6_help-videos_pre-2026-08-28.md`. It is history: it documents
an `assemble_video.py` build that was abandoned and a `final/` layout no store
uses. **Do not follow it.**
