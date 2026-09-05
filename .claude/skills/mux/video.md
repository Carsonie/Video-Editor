---
name: mux-video-upload
description: Upload, update, and delete MP4 videos on Mux and manage video assets for the Rentify/Weloveh organization. Use this skill whenever the user needs to upload new videos, update existing videos, delete assets, or manage help video playback IDs at the default or customer store level.
---

# Mux Video Asset Management

Mux account: organization Weloveh, environment 4meb6g.
Dashboard: https://dashboard.mux.com/organizations/9qohee/environments/4meb6g/video/assets

## Credentials

Located in `deploy/app/etc/config.json`:

```json
"mux": {
  "token_id": "4e43304b-24c4-4e1d-9d47-34807c5f044b",
  "token_secret": "AbDqBeP/mD/PjmcGrssPEzTrgwKkDCbMR41D82eE8txMnR2cJ0v/dCIM9hr79oh/xrXG02CfOl7"
}
```

## How the frontend resolves videos

The frontend calls `fetchVideoRegistry` (`web/src/api/index.ts`) which:

1. Tries `/customers/{RENTIFY_STORE_ID}/help_videos/playback_ids.json` (customer-specific)
2. Falls back to `/customers/default/help_videos/playback_ids.json` (default)

The Go backend serves `customers/` as static files (`app/api.go:102`). No code changes are needed when adding or updating videos — only `playback_ids.json` changes.

## Directory structure

```
customers/
  default/help_videos/              ← default videos (fallback for all stores)
    playback_ids.json
    *.mp4
  store_abc123/help_videos/         ← customer-specific overrides (optional)
    playback_ids.json
    *.mp4
```

## Current video registry (default)

| Key in `playback_ids.json` | Page                      |
| -------------------------- | ------------------------- |
| `The Dashboard Page`       | `/` (dashboard)           |
| `My Calendar Page`         | `/order/:id/items`        |
| `My Order Page`            | `/order/:id`              |
| `The Agreement Page`       | `/order/:id/requirements` |
| `Pay With Stripe`          | `/order/:id/checkout`     |

---

## Uploading New Videos

Use this when adding brand new videos that don't exist in Mux yet.

### For default videos (all customers)

Set `VIDEO_DIR` to `customers/default/help_videos`.

### For customer-specific videos

Set `VIDEO_DIR` to `customers/{storeId}/help_videos`. Create the directory first if it doesn't exist. The customer's `playback_ids.json` only needs entries for videos that differ from the defaults — the frontend falls back to default for any missing keys.

### Upload script

Write this to `upload_to_mux.sh`, run it, then delete it when done.

```bash
#!/usr/bin/env bash
set -e

TOKEN_ID="4e43304b-24c4-4e1d-9d47-34807c5f044b"
TOKEN_SECRET="AbDqBeP/mD/PjmcGrssPEzTrgwKkDCbMR41D82eE8txMnR2cJ0v/dCIM9hr79oh/xrXG02CfOl7"
AUTH="${TOKEN_ID}:${TOKEN_SECRET}"
VIDEO_DIR="${1:-customers/default/help_videos}"   # pass as argument or defaults to default
RESULTS_FILE="${VIDEO_DIR}/playback_ids.json"

# Preserve existing entries if the file exists, otherwise start fresh
if [ ! -f "$RESULTS_FILE" ]; then
  echo "{}" > "$RESULTS_FILE"
fi

for MP4 in "$VIDEO_DIR"/*.mp4; do
  [ -f "$MP4" ] || continue
  NAME=$(basename "$MP4" .mp4)

  # Skip if already in registry
  EXISTING=$(jq -r --arg name "$NAME" '.[$name].playback_id // empty' "$RESULTS_FILE")
  if [ -n "$EXISTING" ]; then
    echo "==> Skipping: $NAME (already in registry)"
    continue
  fi

  echo ""
  echo "==> Uploading: $NAME"

  # Step 1: Create direct upload
  UPLOAD=$(curl -s -X POST "https://api.mux.com/video/v1/uploads" \
    -u "$AUTH" \
    -H "Content-Type: application/json" \
    -d '{"new_asset_settings":{"playback_policy":["public"]}}')

  UPLOAD_URL=$(echo "$UPLOAD" | jq -r '.data.url')
  UPLOAD_ID=$(echo "$UPLOAD" | jq -r '.data.id')
  echo "    Upload ID: $UPLOAD_ID"

  # Step 2: PUT file to signed URL
  curl -s -X PUT "$UPLOAD_URL" \
    -H "Content-Type: video/mp4" \
    --data-binary @"$MP4" > /dev/null
  echo "    File uploaded."

  # Step 3: Poll until asset_id is available (max 120s)
  echo -n "    Waiting for asset"
  ASSET_ID=""
  for i in $(seq 1 24); do
    sleep 5
    echo -n "."
    UPLOAD_STATUS=$(curl -s "https://api.mux.com/video/v1/uploads/${UPLOAD_ID}" -u "$AUTH")
    ASSET_ID=$(echo "$UPLOAD_STATUS" | jq -r '.data.asset_id // empty')
    if [ -n "$ASSET_ID" ]; then break; fi
  done
  echo ""

  if [ -z "$ASSET_ID" ]; then
    echo "    ERROR: timed out waiting for asset_id"
    continue
  fi
  echo "    Asset ID: $ASSET_ID"

  # Step 4: Get playback ID
  ASSET=$(curl -s "https://api.mux.com/video/v1/assets/${ASSET_ID}" -u "$AUTH")
  PLAYBACK_ID=$(echo "$ASSET" | jq -r '.data.playback_ids[0].id')
  echo "    Playback ID: $PLAYBACK_ID"

  # Save to results file (merge into existing)
  UPDATED=$(jq --arg name "$NAME" --arg pid "$PLAYBACK_ID" --arg aid "$ASSET_ID" \
    '. + {($name): {"playback_id": $pid, "asset_id": $aid}}' "$RESULTS_FILE")
  echo "$UPDATED" > "$RESULTS_FILE"
done

echo ""
echo "=== Done ==="
cat "$RESULTS_FILE" | jq .
```

### Usage

```bash
# Default videos
bash upload_to_mux.sh customers/default/help_videos

# Customer-specific videos
bash upload_to_mux.sh customers/store_d6uki4n2rd0c73e36620/help_videos
```

### Notes

- Requires `curl` and `jq` (both available on this machine)
- Skips videos already in `playback_ids.json` — only uploads new ones
- Processing typically takes 5–10s per video
- Delete the script when done

---

## Updating an Existing Video Asset

Mux does **not** support replacing video content in-place or transferring a playback ID between assets. The "Create a playback ID" endpoint only accepts a `policy` parameter — you cannot specify a custom ID string. The "Update an asset" endpoint only updates metadata (`passthrough`, `meta`), not video content.

**Every new video = new asset = new playback ID.** The `playback_ids.json` file must be updated after each replacement.

### Process

1. **Upload the new MP4** using the same upload process above → new `asset_id` + new `playback_id`
2. **Delete the old asset** (cleanup):
   ```bash
   curl -s -X DELETE "https://api.mux.com/video/v1/assets/{OLD_ASSET_ID}" \
     -u "${TOKEN_ID}:${TOKEN_SECRET}"
   ```
3. **Update `playback_ids.json`** with the new `playback_id` and `asset_id`
4. No code changes needed — the frontend reads from `playback_ids.json` at runtime

### After updating

- Works the same for both default and customer-specific videos
- The frontend picks up the new playback ID on next page load

Sources: [Create a playback ID](https://www.mux.com/docs/api-reference/video/assets/create-asset-playback-id), [Update an asset](https://www.mux.com/docs/api-reference/video/assets/update-asset)

---

## Deleting a Video Asset

Use this when a video is no longer needed and should be removed from Mux entirely.

### Process

1. **Delete the asset from Mux:**
   ```bash
   curl -s -X DELETE "https://api.mux.com/video/v1/assets/{ASSET_ID}" \
     -u "${TOKEN_ID}:${TOKEN_SECRET}"
   ```
   A successful delete returns HTTP 204 (No Content).

2. **Remove the entry from `playback_ids.json`** (if the asset is referenced there):
   - For default videos: `customers/default/help_videos/playback_ids.json`
   - For customer-specific videos: `customers/{storeId}/help_videos/playback_ids.json`
   - Use `jq` or edit manually to remove the key whose `asset_id` matches the deleted asset.

3. **Delete the local MP4** (if one exists in the `help_videos/` directory for the deleted video).

### Notes

- If the asset ID is not in any `playback_ids.json`, only step 1 is needed (orphan cleanup).
- The frontend will stop showing the video on next page load once the entry is removed from `playback_ids.json`.

Sources: [Delete an asset](https://www.mux.com/docs/api-reference/video/assets/delete-asset)
