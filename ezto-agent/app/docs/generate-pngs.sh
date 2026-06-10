#!/usr/bin/env bash
# Generate PNGs from .mmd files for graph visualization.
# Usage: bash app/docs/generate-pngs.sh
# Requires: system Chrome at default path

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MMDC="npx -y @mermaid-js/mermaid-cli@10 mmdc"
CHROME="C:/Program Files/Google/Chrome/Application/chrome.exe"

generate() {
  local input="$SCRIPT_DIR/$1"
  local output="$SCRIPT_DIR/$2"
  echo "Generating $output ..."
  PUPPETEER_EXECUTABLE_PATH="$CHROME" \
    $MMDC -i "$input" -o "$output" -t neutral -b white --width 1024
  echo "  Done."
}

generate "graph.mmd" "graph.png"
generate "graph-cn.mmd" "graph-cn.png"
