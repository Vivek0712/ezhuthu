#!/usr/bin/env bash
# 1280x720 thumbnail from thumbnail.html (p14 Brihadisvara at dusk, Cafeskool, CC BY-SA 4.0).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
node "$HERE/raster.mjs" "$HERE/thumbnail.html" "${1:-/Users/vivekrajaps/tamil-script/ezhuthu-video/thumbnail.png}" 1280 720
