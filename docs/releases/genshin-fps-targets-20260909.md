# Genshin DXMT FPS target correction

This resource-only update follows accepted revision `417ed5c2be7c1262b2b3cf3edc609ffe3b04958f` on `ui/genshin-only-upstream`.

The accepted implementation passes the selected FPS target to the original companion, but its final game-execution interception changes `d3d11.preferredMaxFrameRate` to zero only when its value is exactly 150. Thus target160 leaves game DXMT160 while target150 uses game DXMT0. This is a demonstrated configuration defect consistent with the reported target160 presentation plateau; configuration tests alone do not establish the resulting gameplay performance.

The correction applies one explicit rule at the existing launch call: enabled Genshin + DXMT + target greater than60 receives a final game-only environment transformation. The companion retains the selected target environment before that transformation, and its numeric argument remains the same target. Each environment is cloned; exact semicolon-delimited DXMT rate options, including whitespace and duplicates, are replaced without changing unrelated options. No target-specific exception remains.

| Launch configuration | Game DXMT rate | Companion DXMT rate | Companion argument |
| --- | --- | --- | --- |
| Enabled DXMT, target `T > 60` | 0 | T | T |
| Enabled DXMT, target `T <= 60` | T, as before | T | T |
| Unlocking disabled | Original environment | No companion | None |
| Other renderer | Existing renderer environment; no DXMT override added | Existing renderer environment | Selected target when enabled |

The settings loader still reads the existing Genshin keys. Launch/save validation still truncates positive finite input and falls back to120 for invalid/nonpositive input. The UI has min1 and step1, with no maximum. The original release v3.0.7 companion parses a single signed Int32 argument; its supported positive headless range ends at2147483647. The loaded configuration's clamp to420 occurs before headless argument assignment and does not clamp that argument. Values outside the companion's argument range remain unsupported; this update does not change the existing UI validation or companion binary. Current inspected `fps_config.json` locations were absent, so no configured power-save override was found; this is a filesystem inspection, not runtime file-open tracing.

The client initially supplies DXMT60. The wrapper replaces it with selectedT for the companion, then zero for the qualifying game. Both existing Wine implementations merge caller environment values after their defaults. The native command builder forwards those values without another FPS override. The selected per-game Wine executable and prefix remain unchanged.

The only runtime source edits are the DXMT option merger, optional final game-environment transformation, and its explicitly scoped launch call. UI, defaults, saved preferences, Genshin regions, Wine installation safeguard, launcher/update initialization, observer registration, companion script/scheduling/shutdown, Wine waiting and patch handling remain unchanged. Recovery correction `a2f6568` is excluded. The original companion, native launcher, helper and runtime distributions are retained.

## Build and regression checks

Reuse the accepted dependencies, Node22 and existing helper build:

```bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export PATH="$(brew --prefix node@22)/bin:$HOME/.local/share/yaagl-build-tools/node_modules/.bin:$PATH"
pnpm exec tsc --noEmit
pnpm exec vitest run src/launcher/hoyoplay-injections.spec.ts src/launcher/hoyoplay-wine.spec.ts --threads false
pnpm exec eslint src/launcher/hoyoplay.tsx src/launcher/hoyoplay-injections.ts src/launcher/hoyoplay-injections.spec.ts
pnpm exec prettier --check src/launcher/hoyoplay.tsx src/launcher/hoyoplay-injections.ts src/launcher/hoyoplay-injections.spec.ts scripts/verify-packaged-fps.cjs
env -u YAAGL_VERSION YAAGL_CHANNEL_CLIENT=hoyoplay node ./build-app.js
node scripts/verify-packaged-fps.cjs "Yaagl OS.app/Contents/Resources/resources.neu"
```

The packaged regression tool reads the real resource archive, validates entry integrity, discovers compiled functions through guarded AST matches, and executes them using inert process/timer callbacks. Its79 launch cases cover60,61,90,120,121,144,150,160,420, the Int32 upper boundary, lower targets, disabled unlocking, other renderers, original invalid-input behavior, unrelated/duplicate/whitespace DXMT options, repeated targets on the same Wine object, failure cleanup, and shutdown before companion startup. It verifies target150's original game0/companion150/argument150 configuration and target160's corrected game0/companion160/argument160 configuration. Nine additional cases execute the actual packaged per-game Wine environment merge and native command builders, capturing final game and companion command strings at an inert Neutralino spawn boundary. The accepted resource fails the precise target160 game-rate assertion. Mocked client callbacks establish routing/finalization; unchanged actual patch/wait implementations are checked separately in source.

TypeScript, focused lint/format, 12 new FPS tests and42 existing Wine tests pass. Independent source/input checks verify the limited runtime scope. Deployment/rollback has40 temporary-file tests. These checks do not launch Genshin, Wine, the companion or native helpers.

The built resource is `Yaagl OS.app/Contents/Resources/resources.neu`, 1,056,377 bytes, SHA-256 `b37e84a73714410f5e3a5a12ff1da75443616ae11aafa8fa48e528b4da4c138a`. Dependencies, lockfiles, build procedure and19 helper files retain their accepted inputs/bytes. Installed resources are bound to this source commit by the installation manifest.

## Installation and rollback

The durable release directory is `~/Library/Application Support/YAAGL Local Builds/genshin-fps-targets-20260909`. The existing app remains `~/Downloads/Yaagl OS.app`. Only its bundled `resources.neu` and the active support copy are replaced, after verified normal shutdown and clean final patch state. A fresh snapshot preserves both accepted417ed5c resources and exact timestamps, current settings, logs and inventory. Previous release archives remain untouched.

After normal shutdown:

```bash
P="$HOME/Library/Application Support/YAAGL Local Builds/genshin-fps-targets-20260909/deployment"
bash "$P/permanent.sh" verify
```

To restore accepted417ed5c:

```bash
bash "$P/permanent.sh" rollback
bash "$P/permanent.sh" status
```

Rollback preserves fresh evidence first, restores only the two resource files, and retains current preferences. It never recreates stale markers or old backups. Promotion uses exact baseline checks. After installation, only a canonical supported numeric FPS change, the corresponding two numeric sites in the otherwise exact generated companion script, and companion timestamp drift with identical bytes/mode are permitted. The script may describe the last launched target while the UI already holds the next selected target. Unrelated settings/script/binary changes stop for inspection. Final clean files do not independently prove natural cleanup ordering.

## Pending manual gameplay check

1. Open the existing app. Use unlocker target160, per-game Wine `11.0-dxmt-signed-with-patches`, DXMT, in-game FPS60, and the same other settings and comparable scene as the successful150 run.
2. Attempt login/world entry and play for at least two minutes. Record numerical HUD minimum/typical/maximum, sustained drops or an exact120 plateau. Quit the game normally; record whether YAAGL returns ready, then quit YAAGL normally and allow cleanup to finish. If it crashes or startup unexpectedly requests repair/update, stop and collect without retrying.
3. Preserve this run before another launch:

   ```bash
   bash "$P/permanent.sh" collect
   bash "$P/permanent.sh" verify
   ```

4. If the160 run completed normally, change only the launcher FPS target to90 and repeat the same scene, duration, observations and collection commands. Keep the in-game limit at60 and the same Wine/renderer.

Collection prints a unique evidence directory and preserves logs, dumps, configuration, identities and final cleanup state. Report each target's observations alongside that directory, including normal ready return and quit separately. Expected configuration is gameDXMT0, companionDXMT/argument160 or90 respectively. The generated companion log records its target; launcher logs record the final game command/environment. Exact requested FPS continuously is not required: hardware workload can keep performance below the target, and short HUD excursions are not a sustained limiter. A lower resulting limit around90 compared with the160 run supports target control. Neither the configuration checks nor this update establish gameplay acceptance until these observations exist.
