# Genshin settings defaults and Wine compatibility

This update follows accepted revision `382e6bb8a58c58570bc6ab311e9b8c6bad0c5fe4` on `ui/genshin-only-upstream`. It retains the accepted main presentation, regional clients and launch implementation. Only the two frontend resource files are installed; the native launcher, wrapper, sidecars, original release companion, Wine distributions and prefix are retained.

The Wine tab now contains **Wine Distribution** and **Wine Renderer**, without the separate shared launcher section. An existing inherited selection retains its exact shared Wine object, executable path and prefix. Its current-only disabled option displays the known distribution name, or accurately states that the existing distribution is unidentified. Choosing a registered distribution still uses the original per-game namespace and installation/cache handling. No runtime or prefix is deleted by settings initialization.

Freshness requires absent shared Wine metadata and a readable application directory without a Wine or prefix entry. A fresh setup reserves its missing per-game distribution before the original initial installer writes shared metadata. The guard before installer construction preserves known saved distributions and recognized pending updates. Unknown or unreadable metadata, an unreadable application directory, and incomplete existing runtime/prefix state stop for inspection instead of entering the destructive default installer. An interrupted initial installation with partial files consequently requires inspection rather than an automatic retry. Only Neutralino's explicit missing-key error counts as an absent preference. Ready launch execution is unchanged.

Workaround #3's Genshin patch declarations were already commented out for both regions. Its exclusively used UI/factory plumbing is removed. Its historical stored key remains untouched and the generic patch implementation is unchanged.

`src/config/defaults.ts` defines the missing-preference fallbacks used by the existing consumers:

| Group | Fallbacks |
| --- | --- |
| General | Metal HUD on; Retina off; left CMD mapping off; proxy off; proxy host `127.0.0.1:8080`; English independently of system language |
| Game | FPS unlocking on; target 120; HDR off; patch-off false (patch enabled); Steam patch on; block-hosts fix off; custom resolution off with string dimensions `1920` and `1080`; timeout fix on |
| Wine | `11.0-dxmt-signed-with-patches`; DXMT renderer |

Explicit existing values remain intact, including false, other targets, languages and Wine distributions. Opening/closing settings does not populate missing values. The locale binding also avoids its previous unchanged-value write, and saved locale identifiers match case-insensitively, including French. The distribution identifier maps to Wine 11.0 DXMT (signed, with patches) in the existing distribution registry; its release URL and installation implementation are unchanged.

## FPS and execution limitations

The configured numeric target reaches the original release companion. The retained B transformation remains literal-150: at 150, game DXMT is 0 and companion DXMT/argument are 150; at the fallback 120, game DXMT, companion DXMT and numeric argument are all 120. This update does not generalize the override or establish a measured 120 FPS outcome. Saved 150 is preserved in the tested existing-profile fixtures. The actual local installation snapshot for this update already has target 120, which is retained without a settings write.

Observer registration, game supervision, companion scheduling/shutdown, Wine waiting, patch application/reversion and unrelated settings are unchanged. Recovery correction `a2f6568` remains excluded. No new gameplay or reliability claim is made.

## Verification and build

Reuse the accepted dependency/tool setup and existing built Sophon distribution:

```bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export PATH="$(brew --prefix node@22)/bin:$HOME/.local/share/yaagl-build-tools/node_modules/.bin:$PATH"
pnpm exec tsc --noEmit
pnpm exec vitest run src/launcher/hoyoplay-wine.spec.ts --threads false
env -u YAAGL_VERSION YAAGL_CHANNEL_CLIENT=hoyoplay node ./build-app.js
```

TypeScript and 42 focused Wine/installer tests pass. Isolated real settings components with mocked native operations cover fresh, partial and saved profiles; inherited runtime identities; English on a German system; persistence; keyboard navigation; regional context; and actual launch configuration consumers. Screenshots use the accepted real background asset. Packaging verification exercises extracted compiled launch functions, with all native operations replaced by mocks.

Focused ESLint has no errors and retains six pre-existing `app.tsx` warnings. Formatting passes for the changed settings/Wine code; the HK4E client retains its one pre-existing compact catch formatting mismatch, independently compared with the accepted base. Its only source change is removal of three inactive Workaround #3 references. Lockfiles and build inputs remain unchanged. All 19 packaged Sophon files retain the accepted bytes and modes; installed helper timestamps are also untouched.

Built resource: `Yaagl OS.app/Contents/Resources/resources.neu`, 1,056,475 bytes, SHA-256 `b679a7c3730e81eb9841e5368d9ce29adf88bd3c508eae5d5ddca68279c8b594`.

## Permanent installation and rollback

The durable release directory is `~/Library/Application Support/YAAGL Local Builds/genshin-defaults-20260909`. Use the existing `~/Downloads/Yaagl OS.app` after installation. The resource-only installer checks normal shutdown, clean patch state, current settings, retained helper trees and 16,510 inventoried executable/library files. It preserves fresh evidence and both accepted resource files with exact timestamps before substitution. Its new manifest binds the resource to this source commit. Temporary-file tests cover interrupted substitution, unknown state, current backups, evidence preservation and rollback.

The preparation snapshot records intervening session changes separately from the previous release's historical manifest. Current preferences and prefix files are preserved; no old setting or prefix snapshot is replayed. In particular, the release companion bytes still match the original although its timestamp changed before this update. Previous release archives remain intact.

After normal shutdown, verify:

```bash
P="$HOME/Library/Application Support/YAAGL Local Builds/genshin-defaults-20260909/deployment"
bash "$P/permanent.sh" verify
```

Restore the accepted `382e6bb` frontend, preserving current evidence first:

```bash
bash "$P/permanent.sh" rollback
bash "$P/permanent.sh" status
```

Rollback restores only the two accepted resources and their timestamps, using the fresh snapshot. It never recreates an old marker or backup. Unknown component, runtime or settings changes stop for inspection instead of overwriting them. No game is launched or process forcibly stopped by these commands.
