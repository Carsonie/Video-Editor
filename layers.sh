#!/usr/bin/env bash
# Start the video editor and open a LAYERED view — an mp4 underneath, an alpha
# WebM on top — in Chrome, in one command.
#
# The editor is ALWAYS restarted, never reused: serve.py is imported once, so a
# running server silently keeps serving the code it started with.
#
#   ./layers.sh                          browse, pick the two files by hand
#   ./layers.sh <base.mp4> <overlay.webm>   straight to the layered view
#   ./layers.sh --dev                    also bring up the Rentify dev servers
#   ./layers.sh --stop                   stop the editor
#
# Paths may be absolute, repo-relative, or relative to Customers/ — all three
# are resolved, because the two files usually live in different folders and
# typing full paths for both is the reason this script exists.
set -euo pipefail
# ⚠ Keep every echo in this file ASCII-only, and brace every ${VAR}.
# A multibyte character touching an expansion — `$PORT…` — is swallowed into the
# variable NAME under some locales, so `set -u` aborts with "PORT?: unbound
# variable". It works on the machine that wrote it and fails on the next one.

REPO="/Users/carsonkramer/Rentify/Basic_E2E_Testing"
PLAYERS_DIR="$REPO/.claude/agent-tools/6_end-customer-help-video-creations/video_players"
CUSTOMERS="$REPO/Customers"
PORT=8842
LOG="/tmp/video_players_${PORT}.log"

die() { printf '  x %s\n' "$1" >&2; exit 1; }

# Everything the editor opens must live under Customers/ — that is the server's
# own boundary, and a path outside it is rejected there rather than here.
to_rel() {
  local p="$1" abs
  for cand in "$p" "$REPO/$p" "$CUSTOMERS/$p"; do
    if [ -f "$cand" ]; then abs="$(cd "$(dirname "$cand")" && pwd)/$(basename "$cand")"; break; fi
  done
  [ -n "${abs:-}" ] || die "no such file: $p"
  case "$abs" in
    "$CUSTOMERS"/*) printf '%s' "${abs#"$CUSTOMERS"/}" ;;
    *) die "not under Customers/: $abs" ;;
  esac
}

urlenc() { python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1],safe=""))' "$1"; }

if [ "${1:-}" = "--stop" ]; then
  pkill -f "serve.py --port ${PORT}" 2>/dev/null && echo "  editor stopped" || echo "  editor was not running"
  exit 0
fi

if [ "${1:-}" = "--dev" ]; then
  shift
  echo "  starting the Rentify dev servers..."
  node "$REPO/Local_Host/manage-servers.js" start >/dev/null
  node "$REPO/Local_Host/manage-servers.js" store \
    | python3 -c 'import json,sys;d=json.load(sys.stdin);print("  serving:",d["active"]["title"])'
fi

# ALWAYS kill and restart — never reuse a running server.
#
# serve.py is imported ONCE, when the process starts. A server left running
# keeps serving the code it was started with, so every edit to serve.py is
# invisible until it is restarted — and the symptom is not an error, it is the
# old behaviour quietly persisting, which is the worst kind of stale.
#
# (viewer.html is rewritten on each open, so template edits DO appear without a
# restart. That inconsistency is exactly what makes reuse a trap: some changes
# land and some do not, and there is nothing on screen to say which.)
#
# A restart costs about a second. The frame cache is on disk and survives it,
# so nothing is re-extracted.
if pkill -f "serve.py --port ${PORT}" 2>/dev/null; then
  echo "  stopped the running editor"
  sleep 0.6                     # let the port come free before rebinding
fi
echo "  starting the editor on ${PORT}..."
( cd "$PLAYERS_DIR/shared" && nohup python3 serve.py --port "${PORT}" >"$LOG" 2>&1 & )
for _ in $(seq 1 40); do
  curl -fsS -o /dev/null --max-time 1 "http://localhost:${PORT}/browse.html" 2>/dev/null && break
  sleep 0.25
done
curl -fsS -o /dev/null --max-time 2 "http://localhost:${PORT}/browse.html" \
  || die "editor did not come up - see ${LOG}"
echo "  editor ready on ${PORT}"

if [ $# -ge 2 ]; then
  B="$(to_rel "$1")"; O="$(to_rel "$2")"
  echo "  background: $B"
  echo "  overlay   : $O"
  echo "  extracting both (the overlay keeps its alpha - this can take a moment)..."
  URL="$(curl -fsS --max-time 1800 \
      "http://localhost:${PORT}/api/open-pair?base=$(urlenc "$B")&overlay=$(urlenc "$O")" \
    | python3 -c 'import json,sys
d=json.load(sys.stdin)
if d.get("error"): sys.exit("  x "+d["error"])
print(d["url"])')"
  FULL="http://localhost:${PORT}/$URL"
elif [ $# -eq 1 ]; then
  die "layering needs TWO files - a background .mp4 and an overlay .webm"
else
  FULL="http://localhost:${PORT}/browse.html"
  echo "  no files given - opening Browse. Pick the background and overlay chips, then 'Layer these'."
fi

echo "  -> ${FULL}"
open -a "Google Chrome" "$FULL"
