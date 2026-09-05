# MUX-Management — video delivery, and everything that feeds it

Moved here from `Basic_E2E_Testing` on 2026-09-05, at Carson's direction.
That repo tests Rentify end to end; **its scope stops at producing the raw
mp4s.** Everything downstream of a raw capture — avatars, narration, hosting,
delivery — belongs with the video work, which lives in this repo.

```
Video-Editor/
├── Customers/          the videos
├── Video-Editors/      the code that makes them
└── MUX-Management/     delivery, and the avatar/narration source
```

## What is in here

| | |
|---|---|
| `Help_Videos/HeyGen/` | 722 MB — avatar and narration renders, and the goal docs |
| `Help_Videos/MUX/` | ⚠ live API tokens, `.env` files, `.pem` signing keys |
| `Help_Videos/Mux_Discovery_Plan/` | the plan and its session rules |
| `Help_Videos/VSCode_Mux_Ex/` | 22 MB — the example workspace |
| `VIDEO_CREATION.txt` | how a video got made, pre-split |
| `close_out_sarah.md` | Sarah's close-out notes |

## ⚠ Credentials

`Help_Videos/MUX/` holds **live MUX API tokens and `.pem` signing keys.**

They were MOVED, not copied — two copies of a credential is worse than one
in the wrong place. `.gitignore` was extended to cover this folder **before**
anything arrived, so no key was ever exposed to a commit. Only `.md` and
`.txt` files here travel to git; every `.env`, `.pem`, media file and
anything named `*token*` / `*key*` / `*secret*` is excluded.

**Do not read, print, or copy their contents.**

## What deliberately did NOT come

**`Basic_E2E_Testing/Help_Videos/OBS_Staging/` stayed there**, and must. It
is not an archive — it is the live path OBS writes into, named in that
repo's OBS profile as `RecFilePath` and read by
`Master_Flows/Recorder/scripts/{record_flow,preflight}.ts`. Moving it breaks
recording, which is the one video-adjacent job that repo keeps.

Making the raw mp4 is theirs. Everything after it is ours.
