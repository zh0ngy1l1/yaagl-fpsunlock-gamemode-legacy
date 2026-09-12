#!/bin/bash
# Install a versioned, already signed payload. Preference changes never call for
# a different payload or edit a plist. Only the supported distribution calls this.
set -euo pipefail
engine=$(cd "$1" && pwd -P)
support=$(cd "$2" && pwd -P)
marker="$engine/.native-fullscreen.sha256"
if cmp -s "$support/payload.sha256" "$marker"; then exit 0; fi
"$support/check-idle" "$engine"
actual=$(shasum -a 256 "$engine/lib/wine/x86_64-unix/ntdll.so")
actual=${actual%% *}
if ! grep -Fxq "$actual" "$support/compatible-ntdll.txt"; then
  echo 'Native Fullscreen support does not match this Wine engine. Reinstall Wine 11.0 DXMT (signed, with patches).' >&2
  exit 1
fi
(cd "$support" && shasum -a 256 -c payload.sha256)
stage=$(mktemp -d "$engine/.native-fullscreen-XXXXXX")
cleanup() { rm -rf "$stage"; }
trap cleanup EXIT
tar -xzf "$support/payload.tar.gz" -C "$stage"
(cd "$stage" && shasum -a 256 -c files.sha256)
codesign --verify --deep --strict "$stage/lib/wine/x86_64-unix/WineGame.app"
codesign --verify --strict "$stage/lib/wine/x86_64-unix/wine"
codesign --verify --strict "$stage/lib/wine/x86_64-unix/winemac.so"
"$support/check-idle" "$engine"
# Keep the previous deployment for investigation; stage rollback before writes.
backup="$stage/previous"
mkdir "$backup"
paths=(lib/wine/x86_64-unix/wine lib/wine/x86_64-unix/winemac.so
       lib/wine/x86_64-windows/winemac.drv lib/wine/i386-windows/winemac.drv
       lib/wine/x86_64-unix/WineGame.app)
for path in "${paths[@]}"; do
  mkdir -p "$backup/$(dirname "$path")"
  if test -e "$engine/$path"; then cp -pR "$engine/$path" "$backup/$path"; fi
done
rollback() {
  for path in "${paths[@]}"; do
    rm -rf "$engine/$path"
    if test -e "$backup/$path"; then cp -pR "$backup/$path" "$engine/$path"; fi
  done
}
trap 'rollback' ERR
for path in "${paths[@]}"; do
  rm -rf "$engine/$path"
  cp -pR "$stage/$path" "$engine/$path"
done
codesign --verify --deep --strict "$engine/lib/wine/x86_64-unix/WineGame.app"
codesign --verify --strict "$engine/lib/wine/x86_64-unix/wine"
# A final hash marker makes subsequent launches no-ops, including while busy.
cp "$support/payload.sha256" "$stage/marker"
mv "$stage/marker" "$marker"
trap - ERR
if ! test -e "$engine/.native-fullscreen-backup"; then
  mv "$backup" "$engine/.native-fullscreen-backup"
fi
