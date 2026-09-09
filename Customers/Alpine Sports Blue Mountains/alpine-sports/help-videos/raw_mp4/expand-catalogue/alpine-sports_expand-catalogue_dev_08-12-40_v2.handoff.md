# Handoff — alpine-sports_expand-catalogue_dev_08-12-40_v2.mp4

Step 1 of `CROSS_PROJECT_HANDOFF_PLAN.md`. Written by `Basic_E2E_Testing`
(`5_testing-recorder-manager`-style capture) in the SAME step that filed the
mp4 — this file and the video are one write, not two.

| field | value |
|---|---|
| store + business | alpine-sports / Alpine Sports Blue Mountains |
| recipe / sequence | expand-catalogue (see "How this was actually run" below — the recorded flow itself ran the `items`-only sequence) |
| surface | BCP admin (`--surface bcp`) |
| target + type | localhost — `http://localhost:8080` (local dev) |
| pass / fail | **PASS** — exit 0, `RUN PASSED`, all 4 flow steps ✅ |
| what it created | Collection **Womens Skis** → `collection_dag3k372djacbd72sr2g` (created just before this recording, unfilmed — see below); Item **Womens Skis - Black Pearl 88 - 150 cm** → `item_dag3klv2djacbd72srd0` ($99.99, qty 100); Item **Womens Skis - Volkl Secret 96 - 160 cm** → `item_dag3kuf2djacbd72srig` ($104.99, qty 100) |
| duration, fps, size | 80.28s, 25.00fps, 2304x1926, 241,136,776 bytes (241.1 MB / 230.0 MB reported) |
| the exact command | see "How this was actually run" below — NOT the single `expand-catalogue --surface bcp` invocation, for a documented, verified reason |
| purpose | **video seed** (help-video/promotional footage), per this task's own instruction — always localhost, per project rule |
| click pacing | `CLICK_HIGHLIGHT_MS=250` / `CLICK_DELAY_MS=500`, set automatically by `record_flow.ts`. Confirmed VISIBLE on inspection: the frame at 60s shows the "Item Description" field for the second item outlined and washed yellow at click time |

## How this was actually run — and why it deviates from the literal one-shot command

The originally-specified command was:

```bash
cd Master_Flows/Recorder
STORE_FILE="Alpine Sports Blue Mountains/alpine-sports/yaml/_new_collections.Store.yaml" \
  npx tsx scripts/record_flow.ts alpine-sports expand-catalogue --surface bcp
```

Read directly from source before running: `bcp_runner.ts`'s `expand-catalogue`
sequence runs `create_collections` and `create_items` as two **separate**
`spawnSync` (jest) child processes, back-to-back, with **no pause between
them**. `create_collections.test.ts` never writes the id it mints back to
`STORE_FILE` on disk — it only logs `Name → collection_...`.
`create_items.test.ts` reads the *same* `STORE_FILE` fresh from disk and
throws immediately (`collection "Womens Skis" has no real id yet — run
create_collections.test.ts first`) if that id isn't already there. There is
no window inside one `bcp_runner` invocation for an outside operator to patch
the yaml between the two steps — confirmed by reading `bcp_runner.ts`'s `for`
loop directly, and confirmed empirically: a `v1` attempt at the literal
one-shot command is sitting right beside this file
(`alpine-sports_expand-catalogue_dev-FAILED_08-10-52_v1.mp4`), left from
before this run.

This exact gap is what the calling task's own brief flagged ("You must write
that id into the temp yaml between the two flows... Watch for it") and it is
also exactly the documented precedent already recorded in this store's own
temp yaml history (`_new_collections.Store.yaml`, "Runs already done": Run 1
was an unfilmed direct `create_collections` run, Run 2 was a filmed
`create_items`-only run). This run followed that same, already-established
pattern:

1. **Unfilmed** — `create_collections.test.ts` run directly via jest (not
   through the recorder) to create `Womens Skis` and mint its real id:
   ```bash
   cd Master_Flows/BCP/Nav
   STORE_FILE="Alpine Sports Blue Mountains/alpine-sports/yaml/_new_collections.Store.yaml" \
   BUSINESS_ID=business_d6tadnn2rd0c73e1jce0 STORE_ID=store_d6tafdn2rd0c73e1jf1g \
   NODE_OPTIONS=--experimental-vm-modules npx jest --testPathPattern 'flows/create_collections'
   ```
   Result: `Womens Skis → collection_dag3k372djacbd72sr2g`, verified against
   the DB by the flow's own Step 3.
2. The printed id was hand-written into
   `_new_collections.Store.yaml`'s `collections[0].id`.
3. **Filmed — this video.** The actual recorded command, scenario forced to
   `items` (the sequence that runs `create_items` only, now that the
   collection's real id is already in the yaml) with `RECIPE=expand-catalogue`
   set explicitly so the file/folder still read as the `expand-catalogue`
   recipe:
   ```bash
   cd Master_Flows/Recorder
   STORE_FILE="Alpine Sports Blue Mountains/alpine-sports/yaml/_new_collections.Store.yaml" \
   RECIPE=expand-catalogue \
   npx tsx scripts/record_flow.ts alpine-sports items --surface bcp
   ```

Net effect: the collection itself is not on camera (it was created seconds
earlier, off-camera), but both items — login, collection search, requirement,
both option-group selections, save, for each of the two items — are captured
in full, at the click-paced speed, with the DB-verify and logout also on
camera. This is the same tradeoff the store's own prior "Run 2" made.

## What happens next — this side cannot do it

This repo (`Basic_E2E_Testing`) only produces the raw capture. Turning this
footage into an actual help/promotional video — script, HeyGen avatar track,
scene join, release — happens in the **Video-Editor** repo
(`~/Rentify/Video-Editor`), and this agent **cannot invoke** the agent or
tooling that does that work. The next step in
`CROSS_PROJECT_HANDOFF_PLAN.md` has to be picked up from that side.

## Verification performed (this run)

- DB: `Womens Skis` collection has exactly 2 items (`item_dag3klv2djacbd72srd0`
  $99.99, `item_dag3kuf2djacbd72srig` $104.99).
- Alpine Sports has exactly **4** collections (Mens Ski Coats, Ski Goggles,
  Mens Skis, Womens Skis) — no duplicate created.
- `status_runner.ts --store .../alpine-sports/yaml/Store.yaml` →
  **32 exist, 0 mismatched, 0 missing** (up from 29/0/3 before this run).
- Frame pulled at 60s shows the yellow click-highlight live on the "Item
  Description" field for the second item.
