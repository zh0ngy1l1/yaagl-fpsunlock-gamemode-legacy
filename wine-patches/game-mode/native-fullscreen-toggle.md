# Native Fullscreen: launcher-controlled behavior

**Settings → General → Native Fullscreen**, directly above Metal HUD, is the
single control for fixed-size native fullscreen and Game Mode eligibility.
It currently supports only **Wine 11.0 DXMT (signed, with patches)**
(`11.0-dxmt-signed-with-patches`). Other selections show the disabled row with
the compatibility note; their engines and registry are not modified by this
feature. The saved preference is retained if the user changes distributions,
but its effective value is false for an unsupported selection.

The default is **Off**. The key is `config_nativeFullscreen`, stored as
`"true"`/`"false"` through the same `getKey`/`setKey` routing as Metal HUD.
Ordinary client namespaces stay separate. HoYoPlay's Genshin namespace uses the
existing Genshin compatibility storage route in `Yaagl OS/.storage`, exactly as
neighboring launch settings do. No new storage system or migration of unrelated
preferences is introduced.

The row says **Applies on next launch**. Clicking it only saves the preference;
it neither rewrites an engine nor changes a running game's registry or identity.
Launch preparation snapshots the effective value before starting the game.
Metal HUD remains independently controlled.

## Runtime contract

| State | Mac Driver opt-in | Native game executable | Game Mode metadata |
| --- | --- | --- | --- |
| Off (including default) | `AllowFixedSizeFullscreen=N` | `lib/wine/x86_64-unix/wine` | Ordinary unbundled loader; no LSSupportsGameMode key |
| On | `AllowFixedSizeFullscreen=Y` | `lib/wine/x86_64-unix/WineGame.app/Contents/MacOS/wine` | Signed real app, org.winehq.wine, LSSupportsGameMode=true |

Both the global `HKCU\Software\Wine\Mac Driver` value and the game's
`HKCU\Software\Wine\AppDefaults\<game.exe>\Mac Driver` value are set explicitly
before launch. This overrides stale global or game-specific values left by
manual experiments. Only this value is changed. Existing RetinaMode,
LeftCommandIsCtrl, Option mapping, cursor behavior, and other driver settings
are preserved. Registry commands run through the ordinary loader and finish
before the game starts. A registry failure aborts preparation.

For the supported engine, YAAGL sets `YAAGL_NATIVE_FULLSCREEN=1` on the game
launch only when enabled. It explicitly sets `0` otherwise, including setup
commands and unsupported engines, so an inherited environment flag cannot
enable an unsupported selection. The flag is inherited by Windows child
processes. Environment merging preserves the existing rendering, HUD, prefix,
and other values. The separate shared Wine object is not prepared merely by
constructing it: support is installed only when that engine is actually used.

Wine's ordinary loader now contains the small routing decision. With flag `0`
or absent, it continues its existing unbundled initialization. With flag `1`, it
execs the adjacent app's real executable before ntdll initialization. The app
recognizes its own executable directory and does not exec again. Both targets
are compiled from the same loader source; their bundle metadata differs.
`execv(target, argv)` preserves every argument, **including argv[0]**, environment,
PID, cwd, inherited descriptors, and Wine server context. An absent On target
fails explicitly instead of silently starting without the requested feature.

YAAGL still uses its existing spawn/exec path, including the Steam bootstrap
where configured. Wine is not launched through `open`, and no persistent wrapper
process is added. The old standalone `forwarder.c` remains only as historical
experimental tooling. The Wine Cocoa fullscreen implementation is unchanged;
Off takes its existing disabled branches and retains upstream fixed-window
eligibility rules.

## Packaging and updates

`sidecar/native-fullscreen/` contains the signed native idle-check helper,
installer, checksums, source provenance, LGPL license, and a roughly 230 KB
compressed payload. The payload includes:

- ordinary signed inner loader with no Game Mode key;
- signed WineGame.app with the key;
- the unchanged validated winemac.so and both x86_64/i386 PE driver files.

The existing full-app build copies the sidecar. Vite also embeds the assets in
`resources.neu` through explicit URL imports, so a resource-only launcher update
can materialize the same signed support files locally without a separate network
download, Python, a compiler, or user-run installer commands.

Only the exact supported distribution is eligible for installation. The payload
also checks the native ntdll hash against the identified published engine or the
validated local full rebuild; it refuses unidentified/mismatched engines rather
than patching them. The published release archive URL remains unchanged. After
extraction, normal launcher preparation adds the versioned support payload before
using that engine. A matching `.native-fullscreen.sha256` makes subsequent
preparation a no-op. Changing the setting never changes payload files.

An installation/update enumerates native executable paths with libproc, including
Wine processes whose displayed argv has been rewritten, and refuses an engine
with a live process. It verifies the archive, staged file hashes, and signatures
before copying the fixed set of files, rechecks idleness immediately before
the replacement, and writes the completion marker last. A failure rolls back
those files. Existing replaced files are retained in `.native-fullscreen-backup`
for developer investigation. Do not launch a second external Wine instance while
an engine update is taking place.

WineGame.app remains sealed and signed; the ordinary loader and idle helper are
signed separately. Toggle-time plist/signature edits are unnecessary. The
unchanged external Wine libraries are not re-signed. These local payloads use
ad-hoc signatures, as in the validated experiments; Developer ID signing and
notarization are a release-distribution task.

## Developer reproduction

Start with the configured/full build described in the fullscreen README. The
existing `bundle-loader.patch` corresponds to Wine commit `fc3ed05`, after
fullscreen commit `bc9a0e8`. `native-fullscreen-loader.patch` applies the additional
startup routing on top of fc3ed05. The fullscreen driver source is untouched.
The validated routing is committed separately in Wine as
`dabf5e83e53e8379aa1146744c110f53b070f6d4`.

```sh
work=/Users/david/code/home/yaagl-wine-fullscreen
# For an fc3ed05 source checkout only; current workspace already has this patch.
git -C "$work/wine-wine-11.0" apply "$PWD/wine-patches/game-mode/native-fullscreen-loader.patch"
python3 wine-patches/game-mode/build-support.py --work "$work" --output /tmp/new-fullscreen-support

python3 wine-patches/game-mode/tests/check-routing.py /tmp/new-fullscreen-support
python3 wine-patches/game-mode/tests/check-install.py /tmp/new-fullscreen-support "$work/runtime"
```

Publish updated checked-in sidecar files only after validation; the build script
refuses an existing output directory. It records every payload hash and the
loader source hash in `provenance.json`. The complete baseline source and
downstream/fullscreen patches remain reproducible through the original Wine
build instructions. No complete engine rebuild is needed to toggle the UI.

The historical `build-loader.py`, `install-loader.py`, `forwarder.c`, and manual
rollback record describe the initial always-bundled experiment. They are not
called by the launcher and must not be used to switch this production payload.
For ordinary upstream fullscreen behavior, turn Native Fullscreen Off and
relaunch. This retains the signed assets for a future On launch.

## Validation in this workspace

Host: macOS 26.6.2 (25G83), M4/Rosetta, DXMT. Date: 2026-09-11.

Automated checks performed:

- Setting defaults Off without a write, persists both values, follows actual
  client/Genshin storage routing, and leaves Metal HUD unchanged.
- UI row order and unsupported gating; the live UI also confirmed Off/disabled
  on Wine 9.9 and enabled again after restoring Wine 11.0.
- Both registry scopes receive N/Y for Off/On, including repeated transitions;
  no other registry values are included, and write errors propagate.
- Unsupported distributions cannot opt in through an inherited/caller flag and
  do not invoke the support installer or registry helper.
- Native loader tests run both targets, exercise On→Off→On, and compare argv
  (empty/quoted/Unicode arguments and argv[0]), environment, PID, cwd, inherited
  descriptor, actual executable path, Foundation bundle path/key, and failure
  when the On target is missing.
- Installer tests verify signatures, idempotence, no-op behavior when a current
  engine is active, refusal to upgrade an active engine, and hash mismatch refusal.
- The original 12-window fullscreen regression suite passes with N/N and Y/Y
  using a copy of the **published** supported engine plus this payload. Both
  runs report zero native failures and restore all 12 window geometries/styles.
- All 462 launcher tests, TypeScript, targeted ESLint, and the full HoYoPlay app build
  pass. The app build uses the unchanged existing Sophon binary and PNPM 9.15.9,
  matching the existing lockfile version; no dependency versions were changed.
- Resource-only update tests cover signed asset extraction, matching full-app
  sidecar reuse, and missing-resource failure. An installed-engine support error
  propagates without triggering a fresh download over that engine.
- The reproduction patch applies to fc3ed05 and yields the exact tested loader
  source. `git diff --check` passes in both repositories.

Manual Genshin validation **passed**, as confirmed by the user after testing the
production launcher setting. Both On and Off were tested more than twice, with
each state running for over four minutes total. Both behaved exactly as expected,
with no crashes or other apparent issues. Repeated changes between states and
relaunches passed; the user also tested Native Fullscreen together with **FPS
Unlock** and confirmed that combination works correctly.

This user confirmation completes the previously pending interactive checks for
the production toggle, rather than relying on the earlier always-bundled
experiment. The first captured Off run (PID 45166) independently records the
ordinary unbundled executable, nil external bundle ID, N in both registry scopes,
and a regular type-0 Space. The later repeated interactive results are user
reported; no additional process captures or precise per-run timings are claimed.
The Wine fullscreen implementation and Command/Option mapping remain unchanged.

Raw new evidence is preserved under
`/Users/david/code/home/yaagl-game-mode/evidence/toggle-*`; original fullscreen
and Game Mode evidence remains unchanged in its existing locations.

## Cleanup and retained assets

Temporary diagnostic binaries, experimental candidates, disposable engine/prefix
copies, generated test executables, Python/Vite caches, and task-only package
manager shims are removed after final checks. Diagnostic source and experiment
metadata are archived with the local evidence so earlier observations remain
explainable. Reusable regression tests and developer reproduction tools remain
in this repository; none inject diagnostics into the production game.

The validated launcher app, selected Wine engine, full Wine build/source inputs,
original published runtime, investigation logs/screenshots, and rollback assets
are retained. In particular, `game-mode-backup`, the original inner-loader copy,
and the selected engine's `.native-fullscreen-backup` are preserved. Cleanup does
not change the installed engine, game prefix, saved preferences, or game files.
