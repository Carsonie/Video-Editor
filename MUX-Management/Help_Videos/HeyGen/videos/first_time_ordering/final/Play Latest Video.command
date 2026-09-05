#!/bin/bash
#
# Play Latest Video.command
# Double-click in Finder to open the highest-numbered First_Time_Ordering_<N>.mp4
# in this folder with your default macOS video player (QuickTime).
#
# Works no matter where it's launched from — it resolves to its own folder first.

# Move to this script's own directory (the final/ folder).
cd "$(dirname "$0")" || { echo "Could not enter script folder."; exit 1; }

# Find the highest-numbered First_Time_Ordering_<N>.mp4 (numeric sort on the _<N> field).
latest=$(ls First_Time_Ordering_*.mp4 2>/dev/null | sort -t_ -k4 -n | tail -1)

if [ -z "$latest" ]; then
  echo "No First_Time_Ordering_<number>.mp4 files found in:"
  echo "  $(pwd)"
  echo
  read -n 1 -s -r -p "Press any key to close..."
  exit 1
fi

echo "Opening latest video: $latest"
open "$latest"
