#!/bin/bash
# =====================================================================
#  Mux Signed Video Launcher  —  double-click to play this video.
#  Mints a FRESH signed token every run, then opens the Mux player.
#  To add another video: copy this whole folder, then edit the three
#  values in the "EDIT THESE PER VIDEO" block below.
# =====================================================================

# ---------------- EDIT THESE PER VIDEO ----------------
VERSION="1.0"
TITLE="First Time Ordering"
PLAYBACK_ID="EIokhqWW2SNyYJIqM00HlhZTvq00d00N4GDh8cmFaPhcxk"
# ------------------------------------------------------

set -e

# Work from this script's own folder
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "=============================================="
echo "  $TITLE  (v$VERSION)"
echo "=============================================="

# Find the project's backend/.env  (folder lives in VSCode_Mux_Ex/test_mux_videos/<video>/)
ENV_FILE="$DIR/../../backend/.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: backend/.env not found at: $ENV_FILE"
  echo "This folder must stay inside 'VSCode_Mux_Ex/test_mux_videos/'."
  read -r -p "Press Return to close..."
  exit 1
fi

# Pull the Mux signing key id + private key out of .env
KID="$(grep '^MUX_SIGNING_KEY_ID=' "$ENV_FILE" | head -1 | sed 's/^MUX_SIGNING_KEY_ID=//' | tr -d '"')"
TMPKEY="$(mktemp)"
trap 'rm -f "$TMPKEY"' EXIT
RAW="$(grep '^MUX_SIGNING_PRIVATE_KEY=' "$ENV_FILE" | head -1 | sed 's/^MUX_SIGNING_PRIVATE_KEY=//')"
RAW="${RAW%\"}"; RAW="${RAW#\"}"
printf '%b' "$RAW" > "$TMPKEY"

# base64url helper
b64url() { openssl base64 -A | tr '+/' '-_' | tr -d '='; }

# Mint a signed JWT for an audience: v=video, t=thumbnail, s=storyboard
sign() {
  local aud="$1" now exp header payload h p sig
  now="$(date +%s)"; exp="$((now + 86400))"   # valid 24h from launch
  header="{\"alg\":\"RS256\",\"typ\":\"JWT\",\"kid\":\"$KID\"}"
  payload="{\"sub\":\"$PLAYBACK_ID\",\"aud\":\"$aud\",\"exp\":$exp,\"iat\":$now,\"nbf\":$now}"
  h="$(printf '%s' "$header" | b64url)"
  p="$(printf '%s' "$payload" | b64url)"
  sig="$(printf '%s' "$h.$p" | openssl dgst -sha256 -sign "$TMPKEY" -binary | b64url)"
  printf '%s.%s.%s' "$h" "$p" "$sig"
}

echo "Minting fresh signed tokens..."
VTOK="$(sign v)"; TTOK="$(sign t)"; STOK="$(sign s)"

# Build the player page
cat > player.html <<HTML
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>$TITLE — Mux</title>
<script src="https://cdn.jsdelivr.net/npm/@mux/mux-player"></script>
<style>
  body{margin:0;background:#0b0b0f;color:#e6e6ea;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}
  .wrap{max-width:900px;margin:40px auto;padding:0 16px;}
  h1{font-size:20px;font-weight:600;margin:0 0 2px;}
  .meta{font-size:13px;color:#9a9aa6;margin-bottom:20px;}
  mux-player{width:100%;border-radius:10px;overflow:hidden;}
</style>
</head>
<body>
  <div class="wrap">
    <h1>$TITLE</h1>
    <div class="meta">Signed Mux playback &middot; v$VERSION</div>
    <mux-player
      playback-id="$PLAYBACK_ID"
      playback-token="$VTOK"
      thumbnail-token="$TTOK"
      storyboard-token="$STOK"
      stream-type="on-demand"
      metadata-video-title="$TITLE">
    </mux-player>
  </div>
</body>
</html>
HTML

# Serve over http for reliable HLS playback, then open the browser.
PORT=8770
opn() { sleep 1; open "http://localhost:$PORT/player.html"; }

if command -v python3 >/dev/null 2>&1; then
  echo "Opening player at http://localhost:$PORT  (close this window to stop)"
  opn &
  python3 -m http.server "$PORT" >/dev/null 2>&1
elif command -v python >/dev/null 2>&1; then
  echo "Opening player at http://localhost:$PORT  (close this window to stop)"
  opn &
  python -m SimpleHTTPServer "$PORT" >/dev/null 2>&1
else
  echo "No python found; opening the file directly."
  open "player.html"
  read -r -p "Press Return to close..."
fi
