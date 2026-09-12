> The user-facing control is now **Settings → General → Native Fullscreen**
> (Off by default), supporting only **Wine 11.0 DXMT (signed, with patches)**.
> See [the production toggle](../game-mode/native-fullscreen-toggle.md). The
> manual registry/build instructions below document the original Wine opt-in.

# Wine 11.0: opt-in native fullscreen for fixed-size windows

This patch lets ordinary fixed-size top-level Wine windows use Cocoa native
fullscreen, including a separate macOS fullscreen Space. It retains application
sizing constraints and fixed-size behavior when windowed. With explicit size
limits, Cocoa centers the fixed content in the Space; without them, Cocoa can
expand the content to the screen during fullscreen and restore it on exit.
It does not turn the window into a resizable Windows window.

## Source and engine provenance

YAAGL launcher starting revision: `bf4f5242a41bce71b711fca1bd57f1e1bc06efd6`.
The working tree was clean, and no applicable `AGENTS.md` was found. Existing
launcher keyboard configuration is unchanged. After the automated checks, the
user enabled the option in the game prefix and manually validated Genshin.

The selected distribution, confirmed in `src/wine/distro.ts`,
`src/config/defaults.ts` and both installed `.storage/*wine_tag.neustorage`
files, is `11.0-dxmt-signed-with-patches`. It downloads:

- [YAAGL Wine 11.0 release](https://github.com/yaagl/anime-game-wine/releases/tag/wine-11.0-signed)
- Asset: `wine-devel-11.0-osx64-signed.tar.xz`, root directory `wine/`.
- SHA-256: `4ebba536115e937c3826fa5808dbed50cd5e91c8454999b54cbe0cd2a43d8b4c`.
  The locally cached archive has exactly this digest.
- The distribution repository links to [riverfog7/macports-wine](https://github.com/riverfog7/macports-wine).
  The matching [wine-11.0-fix revision](https://github.com/riverfog7/macports-wine/tree/0d029255bce8f2f4ac47a1984b59ba82e09d9829)
  is `0d029255bce8f2f4ac47a1984b59ba82e09d9829` (2026-05-28).
- Its `emulators/wine-devel/Portfile` uses [Wine 11.0](https://github.com/wine-mirror/wine/tree/db11d0fe6a169c457e23d007e20404643d067aa8),
  upstream commit `db11d0fe6a169c457e23d007e20404643d067aa8`.
  Source archive SHA-256:
  `f09e8153aa46a581d2b56a5b1363b04832070b9409d9244a68cf482b243ff14a`.
- All 17 patches listed for `wine-devel` are applied, in order, without fuzz.
  They cover Rosetta/ntdll/wow64cpu (0001–0010 with the Portfile's numbering),
  Steam/kernelbase (0011–0012), DXMT exports/loader/stub (0013–0015),
  ws2_32 timeout, crypt32 CN compatibility, and mfreadwrite video processing.
  See `downstream-series.txt` for the exact list. Staging patches are not applied.
- The Portfile's post-extract removal of `PKG_CONFIG_LIBDIR` lines is also retained.

The publisher does **not** supply a build manifest or exact packaging script.
The source revision above is the matching published source branch, supported by
its version, release date and patch list; the binary does not attest that commit.
This is a complete rebuild of that pinned distribution recipe, not a claim of
bit-identical reproduction of its release binary.

Separate sources/builds: `/Users/david/code/home/yaagl-wine-fullscreen`.
`macports-wine/` is the pinned overlay checkout; `wine-wine-11.0/` is the verified
upstream archive initialized as a local Git repository, with a `yaagl-baseline`
tag after the downstream patches (`4fdbd4b77742756167dd4d3df57b7c76a8cad7f4`).
The fullscreen source commit is `bc9a0e81d168c99bb63ed716b0455245144aadc7`.
`allow-fixed-size-fullscreen.patch` here is the exact `git diff yaagl-baseline HEAD`
for that commit. Fresh-source preparation applies this same patch after recreating
the downstream baseline.

## Implementation

Wine's `WineWindow::adjustFullScreenBehavior:` previously required
`NSWindowStyleMaskResizable`. Fixed windows without a maximize box lack that
style and were marked `FullScreenAuxiliary`. The new window feature permits
`FullScreenPrimary` for eligible fixed windows when the registry option is on.

The extension requires a titled, unshaped, unowned top-level window without
`WS_THICKFRAME`. Child/popup windows, tool windows, nonactivating windows,
layered windows, modal-frame windows and standard `#32770` dialogs are excluded.
Existing cycle/parent/utility/maximized checks remain in place. Existing
resizable-window eligibility is unchanged. Disabled windows still cannot toggle.

No native resizable style is added. `WM_GETMINMAXINFO`, Cocoa min/max constraints,
Windows styles and resizing remain unchanged.
An option-scoped guard prevents Wine frame updates during native fullscreen
from overwriting the saved windowed frame. AppKit callbacks restore it and the saved positions of attached/latent owned windows.
This additional restoration fixes owned-window drift observed in repeated fixed
fullscreen cycles; weak references allow owned windows to close normally.

Changed Wine files:

- `dlls/winemac.drv/macdrv_main.c`: default-off registry option via `get_config_key`.
- `dlls/winemac.drv/macdrv.h`: option declaration.
- `dlls/winemac.drv/window.c`: conservative eligibility for the new feature.
- `dlls/winemac.drv/macdrv_cocoa.h`: internal feature bit.
- `dlls/winemac.drv/cocoa_window.h`: per-window feature state and weak saved owned-window frames.
- `dlls/winemac.drv/cocoa_window.m`: native fullscreen eligibility and window/owned-window frame restoration.

## Registry contract and actual YAAGL prefix

- Key: `HKCU\Software\Wine\Mac Driver`
- Value: `AllowFixedSizeFullscreen`
- Type: **REG_SZ**
- Recommended values: **Y** to enable, **N** to disable.
- Missing is disabled. Wine's existing first-character parser also accepts
  `y`, `t`, `T`, or `1` as true; every other first character is false.
- `HKCU\Software\Wine\AppDefaults\<executable.exe>\Mac Driver` with the same
  value takes precedence over the default key. An app-specific `N` overrides
  global `Y`, and an app-specific `Y` overrides global `N` or a missing value.
- Read once when the macOS driver initializes in each Windows process. Quit and
  relaunch affected Wine applications. For predictable testing or switching
  engines, close YAAGL/game and wait for that prefix's Wine server to exit.

The current launcher uses the prefix below even for its per-game engine:

```sh
prefix="$HOME/Library/Application Support/Yaagl OS/wineprefix"
engine="/Users/david/code/home/yaagl-wine-fullscreen/dist/wine"

# Enable. Close the game before running this and relaunch it afterwards.
WINEPREFIX="$prefix" "$engine/bin/wine" reg add 'HKCU\Software\Wine\Mac Driver' /v AllowFixedSizeFullscreen /t REG_SZ /d Y /f
WINEPREFIX="$prefix" "$engine/bin/wineserver" -w

# Disable.
WINEPREFIX="$prefix" "$engine/bin/wine" reg add 'HKCU\Software\Wine\Mac Driver' /v AllowFixedSizeFullscreen /t REG_SZ /d N /f
WINEPREFIX="$prefix" "$engine/bin/wineserver" -w

# Remove, restoring the default.
WINEPREFIX="$prefix" "$engine/bin/wine" reg delete 'HKCU\Software\Wine\Mac Driver' /v AllowFixedSizeFullscreen /f
WINEPREFIX="$prefix" "$engine/bin/wineserver" -w
```

If an application override exists, change/remove that value too; deleting the
global value does not delete overrides. None of these commands changes any
Command/Option setting. The real prefix's existing `LeftCommandIsCtrl="n"` and
`RetinaMode="n"` are preserved. Automated checks varied the option only in a
disposable test prefix. The user subsequently enabled `AllowFixedSizeFullscreen`
with `Y` in the actual game prefix; that enabled setting is preserved.

## Build

This Mac is arm64, macOS 26.6.2, with Apple Command Line Tools and Rosetta.
The installed engine uses x86-64 Mach-O host binaries plus i386/x86_64 PE modules
(new WoW64), minimum macOS 14.0, SDK 26.5. Its PE binaries identify GCC 15.2.0.
This build uses Apple clang 21.0.0/installed SDK and MinGW GCC 16.2.0 (Homebrew
mingw-w64 14.0.0_3), Bison 3.8.2, and pkgconf 3.0.7. No ARM Wine engine is mixed in.

`configure-engine.sh` transcribes the pinned Portfile's x86_64, macOS 14.0,
`+gstreamer` options. `make install-lib` installs the complete build. Since
MacPorts is not installed, SDK headers are extracted locally from checksummed
MacPorts SDL/GnuTLS archives and the pinned libinotify source. Freetype,
gettext, FFmpeg, GStreamer and Vulkan headers come from the actual engine's
bundled GStreamer framework. The actual release's external dylibs/framework,
Gecko and Mono are retained. Every Wine implementation module is rebuilt.
Mach-O rpaths are relocated for the standalone `wine/` layout and rebuilt host
binaries are ad-hoc signed locally. This is local signing, not a published or
notarized release. Rendering configuration is unchanged; YAAGL installs its
selected DXMT files through its existing launch path.

To reproduce from the launcher repository (the scripts encode the preparation
and build steps used in this workspace):

```sh
export YAAGL_WINE_WORK=/Users/david/code/home/yaagl-wine-fullscreen
HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 brew install mingw-w64 bison pkgconf autoconf xz

# For a fresh build directory only; refuses to overwrite existing sources.
python3 wine-patches/allow-fixed-size-fullscreen/prepare-sources.py

# Configure, compile driver and full engine, install and package.
wine-patches/allow-fixed-size-fullscreen/build-engine.sh
```

The equivalent individual build commands are:

```sh
wine-patches/allow-fixed-size-fullscreen/configure-engine.sh
export PATH="/opt/homebrew/opt/bison/bin:/opt/homebrew/bin:$PATH"
make -C "$YAAGL_WINE_WORK/build" -j8 dlls/winemac.drv/all
make -C "$YAAGL_WINE_WORK/build" -j8
make -C "$YAAGL_WINE_WORK/build" install-lib
python3 wine-patches/allow-fixed-size-fullscreen/package-engine.py "$YAAGL_WINE_WORK"
```

Outputs:

- Engine: `/Users/david/code/home/yaagl-wine-fullscreen/dist/wine`
- Archive: `/Users/david/code/home/yaagl-wine-fullscreen/dist/wine-11.0-yaagl-fixed-fullscreen.tar.xz`
- Build/runtime logs and checksums: `/Users/david/code/home/yaagl-wine-fullscreen/logs`

## Selection and rollback

This launcher has no custom-engine selector: `getWineDistributions()` returns
only the built-in list. Its per-game path is
`hoyoplay-wines/genshin/<distribution-id>/wine`, and it uses `bin/wine64` if
present, otherwise `bin/wine`, with the shared `wineprefix`. It skips download
when that engine's `bin/wine` exists.

The installed local integration retains the selected **Wine 11.0 DXMT (signed,
with patches)** entry and replaces only its local engine directory with a
symlink to the complete build. The original directory is renamed to
`wine.original-before-fixed-fullscreen` in the same parent. The shared `Yaagl OS/wine`
engine is untouched. Close YAAGL/game before switching:

```sh
python3 wine-patches/allow-fixed-size-fullscreen/select-engine.py built
# Select Wine 11.0 DXMT (signed, with patches) in Genshin's Wine settings.
# The current installed preference already selects this entry.

# Roll back the directory selection:
python3 wine-patches/allow-fixed-size-fullscreen/select-engine.py original
```

Selection has been exercised built → original → built; the built engine is currently selected.
All 11,038 original engine file hashes are preserved in the rollback directory.

The registry option is ignored by the original engine. Use the remove command
above if you also want to remove the opt-in value.

## Reproducible checks

The Windows application creates fixed, resizable, fixed-with-maximize-box,
constrained-resizable, owned, tool, popup, dialog, ownerless-dialog,
nonactivating, child and disabled windows. It logs Windows styles, window/client
rectangles and any physical key messages. No synthetic key events are sent.

The test-only injected Cocoa observer invokes `toggleFullScreen:` directly,
checks native style/collection behavior, and queries WindowServer for an actual
fullscreen Space (Space type 4). These diagnostic private APIs are never included
in the engine patch. Tests are restricted to `test-prefix`, not the game prefix.

```sh
work=/Users/david/code/home/yaagl-wine-fullscreen
x86_64-w64-mingw32-gcc -O2 -Wall wine-patches/allow-fixed-size-fullscreen/tests/fullscreen.c -o "$work/tests/fullscreen.exe" -lgdi32
clang -arch x86_64 -dynamiclib -mmacosx-version-min=14.0 -framework Cocoa wine-patches/allow-fixed-size-fullscreen/tests/observe-fullscreen.m -o "$work/tests/observe-fullscreen.dylib"

wine-patches/allow-fixed-size-fullscreen/tests/run-case.sh "$work/dist/wine" patched-absent 0 absent
wine-patches/allow-fixed-size-fullscreen/tests/run-case.sh "$work/dist/wine" patched-disabled 0 N
wine-patches/allow-fixed-size-fullscreen/tests/run-case.sh "$work/dist/wine" patched-enabled 1 Y
wine-patches/allow-fixed-size-fullscreen/tests/run-case.sh "$work/dist/wine" override-disabled 0 Y N
wine-patches/allow-fixed-size-fullscreen/tests/run-case.sh "$work/dist/wine" override-enabled 1 N Y
# Additional style-only fixed window and 32-bit WoW64 coverage:
x86_64-w64-mingw32-gcc -O2 -Wall wine-patches/allow-fixed-size-fullscreen/tests/fullscreen.c -o "$work/tests/fullscreen-unconstrained.exe" -lgdi32
i686-w64-mingw32-gcc -O2 -Wall wine-patches/allow-fixed-size-fullscreen/tests/fullscreen.c -o "$work/tests/fullscreen32.exe" -lgdi32
YAAGL_TEST_UNCONSTRAINED=1 YAAGL_TEST_APP=fullscreen-unconstrained.exe wine-patches/allow-fixed-size-fullscreen/tests/run-case.sh "$work/dist/wine" fixed-default-size 1 Y
mkdir -p "$work/unpacked"
tar -xJf "$work/dist/wine-11.0-yaagl-fixed-fullscreen.tar.xz" -C "$work/unpacked"
YAAGL_TEST_APP=fullscreen32.exe wine-patches/allow-fixed-size-fullscreen/tests/run-case.sh "$work/unpacked/wine" wow64-enabled 1 Y
python3 wine-patches/allow-fixed-size-fullscreen/check-keyboard.py "$work/wine-wine-11.0"
# Static helper check only; mocks processes and never switches engines.
python3 wine-patches/allow-fixed-size-fullscreen/tests/check-selection.py
```

Actual results are recorded in `validation.md`; compilation alone is not runtime
verification. The user manually enabled the option, opened YAAGL and launched
Genshin, confirmed fullscreen in its own macOS desktop/Space, and observed no
crash during that test before quitting manually. This report does not establish
extended gameplay stability or game fullscreen-exit geometry. Physical
Command/Option input remains untested. The keyboard audit checks byte-identical keyboard/event
sources, all pre-existing Cocoa methods outside the eight window lifecycle methods, all
four modifier-option declarations/readers, and unchanged launcher Wine/config
code against its starting commit.

For a manual physical-key comparison, run `tests/fullscreen.exe` with the
original engine (`$work/runtime/bin/wine`) and then the built engine, each with
`WINEPREFIX="$work/test-prefix"` and stdout redirected to separate files. Omit
`DYLD_INSERT_LIBRARIES`. Press the same physical left/right Command and Option
keys and letter combinations in the fixed test window and compare `KEY` lines.
No keyboard event generator is used by these tests.
