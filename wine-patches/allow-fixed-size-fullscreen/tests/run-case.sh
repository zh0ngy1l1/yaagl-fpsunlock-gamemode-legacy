#!/bin/bash
# Usage: run-case.sh ENGINE_ROOT CASE EXPECT_FIXED [Y|N|absent] [Y|N|absent]
# The last argument optionally sets an application override for fullscreen.exe.
set -euo pipefail
work=${YAAGL_WINE_WORK:-/Users/david/code/home/yaagl-wine-fullscreen}
here=$(cd -- "$(dirname -- "$0")" && pwd)
engine=$1
case_name=$2
expected=$3
value=${4:-absent}
app_value=${5:-absent}
test_app=${YAAGL_TEST_APP:-fullscreen.exe}
export WINEPREFIX="$work/test-prefix"
export WINEDEBUG=-all
export WINEDLLOVERRIDES='mscoree,mshtml='
export MVK_CONFIG_LOG_LEVEL=0
key='HKCU\Software\Wine\Mac Driver'
app_key="HKCU\\Software\\Wine\\AppDefaults\\$test_app\\Mac Driver"
# This prefix is dedicated to this test. Never point this script at the game prefix.
"$engine/bin/wineserver" -w
if [[ $value == absent ]]; then
    "$engine/bin/wine" reg delete "$key" /v AllowFixedSizeFullscreen /f > /dev/null 2>&1 || true
else
    "$engine/bin/wine" reg add "$key" /v AllowFixedSizeFullscreen /t REG_SZ /d "$value" /f
fi
if [[ $app_value == absent ]]; then
    "$engine/bin/wine" reg delete "$app_key" /v AllowFixedSizeFullscreen /f > /dev/null 2>&1 || true
else
    "$engine/bin/wine" reg add "$app_key" /v AllowFixedSizeFullscreen /t REG_SZ /d "$app_value" /f
fi
"$engine/bin/wineserver" -w
: > "$work/logs/$case_name-native.log"
YAAGL_TEST_SECONDS=60 YAAGL_EXPECT_FIXED="$expected" \
YAAGL_OBSERVER_LOG="$work/logs/$case_name-native.log" \
DYLD_INSERT_LIBRARIES="$work/tests/observe-fullscreen.dylib" \
"$engine/bin/wine" "$work/tests/$test_app" > "$work/logs/$case_name-windows.log" 2>&1
"$engine/bin/wineserver" -w
rg '^RESULT failures=0$' "$work/logs/$case_name-native.log"
if rg '^FAIL ' "$work/logs/$case_name-native.log"; then exit 1; fi
python3 "$here/check-geometry.py" "$work/logs/$case_name-windows.log"
