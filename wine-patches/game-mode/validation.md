# Game Mode investigation and validation

Date: 2026-09-11. Host: macOS 26.6.2 (25G83), Apple Silicon M4, x86_64 Wine under
Rosetta, DXMT with Metal HUD enabled. Launcher baseline:
`24afae70bd13bacf47d406bb6fb6fdbee32ed918`. Wine fullscreen baseline:
`bc9a0e81d168c99bb63ed716b0455245144aadc7`.
Validated Wine loader source commit: `fc3ed053ebc146f51ea2ce27005364dbe523bd55`.

## Native process and runtime bundle

Baseline Darwin PID **41430** owned WindowServer window **42015**, titled
`Genshin Impact`. `proc_pidpath` and `NSRunningApplication.executableURL` identified
the native executable as:

`/Users/david/code/home/yaagl-wine-fullscreen/dist/wine/lib/wine/x86_64-unix/wine`

Its displayed argv was `Z:\Users\david\.gimpact\GenshinImpact.exe`, and its observed
parent PID was 1 after its parent exited. The separate Wine server PID was 41416.
The game process loads `winemac.so`, which implements `WineApplication` and
`WineWindow`. YAAGL does not own the game's Cocoa application or window.

LLDB read the following directly inside Genshin's baseline process:

| NSBundle.mainBundle property | Value |
| --- | --- |
| bundlePath | `/Users/david/code/home/yaagl-wine-fullscreen/dist/wine/lib/wine/x86_64-unix` |
| bundleIdentifier | `org.winehq.wine` |
| executablePath | `/Users/david/code/home/yaagl-wine-fullscreen/dist/wine/lib/wine/x86_64-unix/wine` |
| LSSupportsGameMode | nil / absent |

Complete baseline `infoDictionary`:

```json
{
  "CFBundleAllowMixedLocalizations": true,
  "CFBundleDevelopmentRegion": "English",
  "CFBundleExecutable": "wine",
  "CFBundleIdentifier": "org.winehq.wine",
  "CFBundleInfoDictionaryVersion": "6.0",
  "CFBundleName": "Wine",
  "CFBundlePackageType": "APPL",
  "CFBundleShortVersionString": "11.0",
  "CFBundleSignature": "????",
  "CFBundleVersion": "11.0",
  "LSUIElement": "1",
  "NSPrincipalClass": "WineApplication"
}
```

The separate, external `NSRunningApplication.bundleIdentifier` was **nil**, and
its bundleURL pointed at the executable. An internal Foundation identifier from
an embedded plist did not establish the external app identity.

The engine was unbundled. `bin/wine` is a native Mach-O wrapper without a plist;
the inner loader embeds a 936-byte `__TEXT,__info_plist` generated from
`loader/wine_info.plist.in`. There was no loose runtime Info.plist or enclosing
Wine `.app`, and this build has no preloader. Editing the build-tree plist alone
would not affect the installed binary; it must be relinked and re-signed.

## YAAGL launch path and relevant plist

YAAGL itself was launched with `open` and ran from an App Translocation path,
PID 41289, identifier `com.3shain.yaagl.os`. Its Launch Game button takes this path:

```text
src/launcher/hoyoplay-wine.ts: wineExec2
  -> src/utils/neu.ts: exec2
  -> Neutralino.os.spawnProcess
  -> /bin/sh -c ENV .../wine/bin/wine C:\windows\system32\steam.exe Z:\Users\david\.gimpact\GenshinImpact.exe
  -> Wine bootstrap creates the Genshin child
  -> Wine ntdll execs the native inner loader for that child
```

The shell redirects game output to YAAGL's game log. No `open`/LaunchServices
operation launches the Wine game through this path. The optional FPS unlocker
is disabled; the selected renderer and environment were retained.

At baseline, the inner loader's embedded plist was the game's Foundation
metadata. YAAGL.app's plist was not the game's main bundle plist. The successful
experiment exposes the real `WineGame.app/Contents/Info.plist` with the opt-in
key, and GamePolicy then records `labelReason=infoPlist`. It contains the same
values as the embedded opt-in plist, with no added game category or changed ID.

## Controlled results

| Experiment through unchanged YAAGL | Native fullscreen | External bundle ID | Metal HUD | Game Overlay / controller icon |
| --- | --- | --- | --- | --- |
| Baseline loader | Yes | nil | Off | No overlay reported |
| Only embedded LSSupportsGameMode=true, re-signed | Yes, Space 1981 type 4 | nil | Off, including after loading | No overlay after a frontmost shortcut test |
| Real signed app + native exec forwarder | Yes, Space 1994 type 4 | org.winehq.wine | **On** | **Both confirmed by user** |

The key-only candidate changed only the plist section; every other file-backed
Mach-O section was byte-identical to baseline. Genshin PID 41779 confirmed the
key at runtime. Subsequent optional debugger expressions failed under Rosetta
and that process exited, so it was excluded from activation/stability results.
The clean, debugger-free key-only run was PID **41907**, which remained Off.
No further debugger attachment was used for the successful game run.

The bundled Genshin PID was **42262**, window **43361**. Its native executable
and external executableURL were:

`/Users/david/code/home/yaagl-wine-fullscreen/dist/wine/lib/wine/x86_64-unix/WineGame.app/Contents/MacOS/wine`

Its external bundleURL was the corresponding `WineGame.app` directory and
bundleIdentifier was `org.winehq.wine`. A separate hidden WineWindow probe,
with a passive Cocoa observer, confirmed `NSBundle.bundlePath` at the real app,
the same executablePath and ID, and `LSSupportsGameMode=true`. Its infoDictionary
contained the baseline entries above plus the boolean opt-in and Foundation's
synthesized `CFBundleNumericVersion=285245440`. These post-bundle in-process
values were captured in the probe, not by attaching to live Genshin.

GamePolicy's actual Genshin records included:

```text
18:57:01.480 Found game GameProcess(Optional("wine"), pid=42262, euid=501, labelReason=infoPlist)
18:57:20.883 Game mode status is now on.
```

The HUD screenshot independently shows **Game Mode On** while Genshin is active
and AXFullScreen=true. The user separately confirmed: “Game overlay gets opened
with command + escape. THe controller icon appears.” No manual Game Mode toggle
was needed. Logs also show automatic pause/resume with loss/regain of frontmost
status. This is validation of activation, not a performance benchmark or a claim
of long gameplay stability. A second complete game relaunch was not required
to verify the byte-identical reproduction.

RunningBoard still labels the successful process `anon<wine>`. That label alone
is therefore not a valid failure criterion. The decisive observations are the
real bundle identity, GamePolicy game classification, HUD, and user UI checks.

## Signing and preservation

The original loader was ad-hoc signed, with no entitlements, TeamIdentifier, or
sealed resource envelope. Its embedded plist was bound to its code signature.
The key-only binary was relinked then re-signed. The final app and forwarder
were signed separately after all link/path edits, and both pass strict signature
verification; the app also passes deep verification. An attempted bundle with
an escaping ntdll symlink failed strict verification and was never installed.
The successful bundle has no such symlink; its loader opens the adjacent library.

The final audit compared all **33** Mach-O files in the baseline engine manifest.
Only `lib/wine/x86_64-unix/wine` changed. The other **32** match exactly; the app
adds three new files. The Wine source diff changes only `loader/main.c`.
The existing fullscreen sources, `winemac.so`, keyboard sources, YAAGL launch
code, and modifier settings are unchanged. The actual prefix still has
`AllowFixedSizeFullscreen="Y"`, `LeftCommandIsCtrl="n"`, and `RetinaMode="n"`.
No diagnostics are injected into the deployed game or compiled into the loader.

| Artifact | SHA-256 |
| --- | --- |
| Original inner loader / rollback | `6e85a58755262fd59fb87cbe6b7640f6b609019f9345661b3d6559fc9ddaebdd` |
| Embedded-key-only loader | `273cbbaaced90ab50583519a367d559a1f4b5c6069c9507f03ccb24f0791037d` |
| Bundled loader | `2a05b263fe578cfc166ea7a7ea82b1ddc672f7387dcc7d0e70d0ae1b6397dc33` |
| Native forwarder | `8c1e1fe5c9192ec8a0ae60cc46492c52a482f670ec5aa3c605dadcece14ce7a1` |
| Unchanged winemac.so | `4e1999a1d1fbd8d1e5e9d8c6b4d345b3cc86939557e435c9c0ee2bbb838b366b` |

The checked-in build recipe reproduced all deployed app files and the forwarder
byte for byte. Installer checks on a disposable fixture verified install, exact
restore, refusal to overwrite a changed bundle, and refusal while a real native
process in the target engine was alive. Python syntax and Git whitespace checks
passed. No unrelated launcher tests or fullscreen rebuilds were needed.

## Related implementations and Apple documentation

- Apple's [LSSupportsGameMode reference](https://developer.apple.com/documentation/bundleresources/information-property-list/lssupportsgamemode)
  documents the opt-in. Its [Game Mode instructions](https://support.apple.com/en-us/105118)
  describe native fullscreen, Command-Escape, and the controller menu icon.
- The [macOS 26 release notes](https://developer.apple.com/documentation/macos-release-notes/macos-26-release-notes)
  list issue 153127050 for direct Terminal launches and recommend `open`; the
  earlier ignored-key issue 153125166 is listed as fixed. Our bundled direct-exec
  result on 26.6.2 does not require a launcher conversion to `open`.
- The inspected [upstream Wine loader plist](https://github.com/wine-mirror/wine/blob/master/loader/wine_info.plist.in)
  and Wine 11.0 omit the key. The inspected upstream `winemenubuilder` code does
  not generate macOS app bundles. This is not an exhaustive downstream survey.
- [CrossOver's guide](https://support.codeweavers.com/en_US/crossover-mac-user-guide)
  documents per-Windows-application launchers and Apps/Dock integration. CrossOver
  has used macOS `.app` shortcuts; a shortcut alone does not prove the native game
  child's identity. CrossOver is not installed here, and its current proprietary
  Game Mode behavior was not verified.
- Apple's public [GPTK Homebrew formula](https://github.com/apple/homebrew-apple/blob/main/Formula/game-porting-toolkit.rb)
  builds an older CrossOver-derived Wine with an embedded preloader plist and no
  opt-in addition in that formula. This does not establish the implementation of
  the separately distributed current GPTK evaluation runtime.
- [ForgePlay's published design](https://github.com/Facta-Leopard/ForgePlay/blob/main/README.md)
  describes an opt-in fixed `GameModeProcessHost.app` with the key and games
  category. It routes selected Windows game children into a native x86_64 host
  before PE mapping, preserving PID and inherited Wine context. This supports
  investigating the actual native game host's identity; it was not installed
  or tested here, and its implementation was not copied.
- [Apple TN2206](https://developer.apple.com/library/archive/technotes/tn2206/_index.html)
  covers signed metadata/resources and signing nested code before its container.
  This deployment uses local ad-hoc signatures; no notarization was performed.

## Local evidence

Detailed raw captures are outside both repositories at
`/Users/david/code/home/yaagl-game-mode/evidence`:

- `genshin-baseline-lldb-retry.txt`: actual baseline in-process bundle capture.
- `key-only-clean-fullscreen.json`, `key-only-hud-later.png`: clean key-only failure.
- `bundled-forwarder-smoke/`: in-process bundle probe (select its main hidden-window process).
- `bundled-existing-yaagl-retry-fullscreen.json`, `bundled-existing-yaagl-retry-hud.png`:
  active native fullscreen and HUD On.
- `bundled-existing-gamepolicy.txt`: classification and activation for PID 42262.
- `bundled-success-external.json`: the real Genshin app/executable identity.
- `reproducible-build.log`, `final-engine-audit.json`, `installer-validation.json`,
  `final-deployment.json`: build equivalence, unchanged files, rollback tests, and deployment.

All experimental changes were tested before making local source commits. Nothing
was pushed. The successful bundle remains installed in the selected local engine.
