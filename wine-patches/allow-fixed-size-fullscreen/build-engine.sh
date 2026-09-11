#!/bin/bash
set -euo pipefail
here=$(cd -- "$(dirname -- "$0")" && pwd)
work=${YAAGL_WINE_WORK:-/Users/david/code/home/yaagl-wine-fullscreen}
export PATH="/opt/homebrew/opt/bison/bin:/opt/homebrew/bin:$PATH"
mkdir -p "$work/logs"
"$here/configure-engine.sh" > "$work/logs/configure.log" 2>&1
make -C "$work/build" -j"${YAAGL_BUILD_JOBS:-8}" dlls/winemac.drv/all > "$work/logs/build-driver.log" 2>&1
make -C "$work/build" -j"${YAAGL_BUILD_JOBS:-8}" > "$work/logs/build-engine.log" 2>&1
make -C "$work/build" install-lib > "$work/logs/install.log" 2>&1
python3 "$here/package-engine.py" "$work"
