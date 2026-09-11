# Wine 11.0 Game Mode on macOS Tahoe

Genshin now activates macOS Game Mode through the existing YAAGL Launch Game
button. The native Wine process runs inside a signed `WineGame.app` declaring
`LSSupportsGameMode=true`. Its existing AppKit fullscreen implementation is
unchanged. The Metal HUD shows **On**, and the user confirmed both Command-Escape
Game Overlay and the controller icon in the macOS menu bar.

This is an opt-in packaging step for the locally built, per-game Wine engine.
It does not alter YAAGL's application plist, TypeScript launch code, Wine's
fullscreen code, prefix configuration, or Command/Option mapping. Detailed
measurements, the full runtime bundle dictionary, and research are in
[validation.md](validation.md).

## Why the embedded key was insufficient

The native process owning `WineWindow`/`WineApplication` was
`wine/lib/wine/x86_64-unix/wine`. Although `NSBundle.mainBundle` read its embedded
`org.winehq.wine` metadata, the executable was outside any app bundle and
`NSRunningApplication.bundleIdentifier` was nil. YAAGL's own bundle identity
does not transfer to this game process.

A controlled first experiment added only `LSSupportsGameMode=true` to that
embedded plist and re-signed the loader. Every other file-backed Mach-O section
was identical. The key was visible inside Genshin, but a clean launch in a native
fullscreen Space still showed HUD Off and no Game Overlay.

Packaging the loader in a real app, with the same metadata values, changed the
result. GamePolicy identified Genshin with `labelReason=infoPlist` and enabled
Game Mode when it was frontmost in fullscreen. `open` was unnecessary for this
tested setup. Apple's documented direct-Terminal-launch issue motivated the
experiment, but does not establish that every direct spawn on Tahoe fails.
See the [macOS 26 release notes](https://developer.apple.com/documentation/macos-release-notes/macos-26-release-notes).

## The tested layout

```text
wine/
  bin/wine                              existing native wrapper
  lib/wine/x86_64-unix/
    wine                                small native exec forwarder
    ntdll.so                            unchanged
    winemac.so                          unchanged, including native fullscreen
    WineGame.app/
      Contents/Info.plist                Wine metadata + LSSupportsGameMode=true
      Contents/MacOS/wine                Wine loader with one extra path case
      Contents/_CodeSignature/CodeResources
```

`bundle-loader.patch` adds one case to `loader/main.c`: a loader running at
`WineGame.app/Contents/MacOS/wine` finds `ntdll.so` beside the app. Wine resolves
the real ntdll path and keeps its existing engine, DLL, prefix, and child-loader
paths. No Wine implementation libraries are moved into the bundle.

`forwarder.c` occupies the established inner-loader path and calls `execv` on
the real app executable. It preserves the PID, environment, current directory,
inherited descriptors, Wine server context, and arguments after argv[0]. A
symlink alone was insufficient in the probe: Foundation retained the alias
directory as its main bundle and the external identifier remained nil.

The bundle retains `CFBundleIdentifier=org.winehq.wine`, `CFBundleName=Wine`,
and the existing `LSUIElement` value. No games category, borrowed application
identity, private Game Mode API, or launch mechanism change is needed here.
This identity is shared by processes using this opted-in engine; it is not a
separate macOS identity for each Windows application. The selected local engine
is currently used by Genshin. Other games/engines were not validated.

## Build and install

Start with the configured and fully packaged engine described in
[the fullscreen build instructions](../allow-fixed-size-fullscreen/README.md).
The base launcher commit is `24afae70bd13bacf47d406bb6fb6fdbee32ed918`; the base
Wine source commit is `bc9a0e81d168c99bb63ed716b0455245144aadc7`.
The separate Wine source change is the local `loader: Support an opt-in macOS
game application bundle` commit recorded in validation.md.

For fresh sources, apply this patch after the fullscreen patch. The current
workspace already has it applied and committed, and already has the candidate
installed; these commands are for reproduction.

```sh
work=/Users/david/code/home/yaagl-wine-fullscreen
patch_path="$PWD/wine-patches/game-mode/bundle-loader.patch"
git -C "$work/wine-wine-11.0" apply --check "$patch_path"
git -C "$work/wine-wine-11.0" apply "$patch_path"

python3 wine-patches/game-mode/build-loader.py \
  --work "$work" --output "$work/game-mode-candidate"

# Quit applications using this engine first. YAAGL itself may remain open.
python3 wine-patches/game-mode/install-loader.py install \
  --engine "$work/dist/wine" --candidate "$work/game-mode-candidate" \
  --backup "$work/game-mode-backup"
```

The builder compiles only the loader and forwarder into a new staging directory.
It leaves the installed engine, generated baseline plist, and fullscreen build
objects untouched. The recipe reproduces the validated x86_64 Mach-O address
reservations and locally signs the result. The original loader and bundled loader
both report macOS 26.0 as their Mach-O minimum; this recipe explicitly preserves
that observed value. Runtime validation was on macOS 26.6.2, SDK 26.5, M4/Rosetta.

The installer verifies signatures and hashes, refuses existing bundle/backup
paths, checks native process paths before changing the engine, saves the original
loader, and stages replacements on the destination filesystem. Do not start a
game while installation/restoration is in progress. The scripts are scoped to the
tested standalone layout without a Wine preloader or an enclosing signed app.

The current per-game selection remains:

`~/Library/Application Support/Yaagl OS/hoyoplay-wines/genshin/11.0-dxmt-signed-with-patches/wine`
→ `/Users/david/code/home/yaagl-wine-fullscreen/dist/wine`.

The original distribution backup and the fullscreen archive are unchanged. A
future full engine rebuild should start from a restored/clean engine, then apply
this separate packaging step again.

## Signing and rollback

Changing the embedded plist invalidates the loader signature. Changing a real
bundle's plist requires re-signing the app. This app has only its main executable;
`codesign --force --sign - WineGame.app` signs it and the bundle metadata. The
external forwarder is signed separately. Any modified nested code would need to
be signed before its containing app. Unchanged `ntdll.so`, `winemac.so`, and
YAAGL.app require no re-signing because the engine is outside YAAGL's bundle.
See [Apple's signing guidance](https://developer.apple.com/library/archive/technotes/tn2206/_index.html).

Both installed artifacts pass:

```sh
native=/Users/david/code/home/yaagl-wine-fullscreen/dist/wine/lib/wine/x86_64-unix
codesign --verify --deep --strict "$native/WineGame.app"
codesign --verify --strict "$native/wine"
```

The original loader is retained at
`/Users/david/code/home/yaagl-wine-fullscreen/game-mode-backup/wine`, with a hash
record in `state.json`. The installed experimental files were verified against
the reproducible build before recording this rollback state; the running game
was not modified or restarted by that bookkeeping.

After quitting applications using this engine:

```sh
python3 wine-patches/game-mode/install-loader.py restore \
  --engine /Users/david/code/home/yaagl-wine-fullscreen/dist/wine \
  --backup /Users/david/code/home/yaagl-wine-fullscreen/game-mode-backup
```

Restore refuses changed installed files or a changed backup. It restores the
exact pre-Game-Mode loader and removes only the recorded bundle. Fullscreen and
keyboard settings remain as they were. The rollback directory is retained;
choose a new backup directory for a later installation.

To check Game Mode, launch through YAAGL, enter native fullscreen, and keep the
game frontmost. Check Metal HUD **Game Mode On**, then Command-Escape Game Overlay
and the controller menu icon. Apple documents that switching Game Mode off in
the overlay persists for that game; see [Use Game Mode](https://support.apple.com/en-us/105118).
