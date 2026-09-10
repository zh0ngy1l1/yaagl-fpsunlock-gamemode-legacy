# Genshin settings consolidation

This presentation update follows accepted build `21f921d982cb44dda521e81b6af9416023d3b837` and its documentation commit `3f678ad9d4c133d9351c16376460d5b490269868`, on `ui/genshin-only-upstream`. It does not change the helper or execution implementation.

The main gear opens YAAGL settings directly. The Game tab contains the existing FPS enable checkbox and numeric target; the Wine tab contains the existing **per-game Genshin Wine** selector and renderer. Shared launcher Wine remains separately labeled. General, existing Advanced enablement and Licenses retain their previous controls. Explicit Save uses the original save functions; opening, closing or changing tabs does not save or reset the relocated controls.

The redundant Genshin settings modal, its intermediate navigation, the news button and the foreground logo were removed. The news button called `open(client.uiContent.url)`; the Genshin client supplies HoYoPlay's `icon.link`, which was verified as the requested `blue-post` page. No metadata fetching or client initialization order was changed.

The actual selected background is `0f93f69e7ad2b6e5cf3c6099b2203cfa_8197460319677977597.webp` from HoYoPlay's launcher-public artwork. Its SHA-256 is `6be7316ff72920459ada1e583afc487be077d9f4b34ea844b9bc1188bd038e89`. Retrieved bytes exactly matched the installed WebKit cache, and visual inspection confirmed the embedded upper-left Genshin Impact logo. The unchanged background supplies the single visible logo; the main region retains its accessible Genshin name. Screenshots use these real bytes, not synthetic artwork. Future server artwork can change independently of this source.

## Build and verification

Use the pinned tools and inputs in [the accepted release instructions](genshin-upstream-21f921d.md). Reuse the existing matching Sophon distribution; do not rebuild it for this UI update. Package with:

```bash
pnpm exec tsc --noEmit
pnpm exec eslint src/launcher/hoyoplay.tsx src/config/index.tsx
pnpm exec prettier --check src/launcher/hoyoplay.tsx src/config/index.tsx src/app.css
env -u YAAGL_VERSION YAAGL_CHANNEL_CLIENT=hoyoplay node ./build-app.js
```

The new `resources.neu` is 1,056,067 bytes, SHA-256 `30054271d7ed63962456323416a9faa21b5c48a144860441e858355511b37c99`. Both packaged and retained Sophon distributions match the accepted 19 files, including executable SHA-256 `329958a1d208da65f3cb60f54a77a7b1e1328824fac262a59cd9ed52d39ca499`. Lockfiles, native inputs, build procedure and helper sources remain unchanged.

TypeScript, focused lint and formatting passed. Fifty-two protected source checks and eight compiled function comparisons cover the retained launch and cleanup implementation; twenty mocked packaged launch cases cover FPS/environment preservation, disabled unlocking, renderers and companion cleanup. Real Hope/Solid settings are checked in an isolated browser with mocked native storage/operations and the real cached background. No game is launched by these checks. This update makes no new gameplay or reliability claim.

At selected target 150, the retained literal-150 behavior is game DXMT rate 0, companion DXMT rate 150 and numeric companion argument 150. This comparison does not generalize that behavior to other targets. Genshin regional clients, selected Wine/prefix, launch ordering, companion scheduling/shutdown, Wine waiting and patch handling are retained. Recovery correction `a2f6568` remains excluded.

## Resource-only installation and rollback

The durable update record is `~/Library/Application Support/YAAGL Local Builds/genshin-settings-ui-20260909`. The existing `~/Downloads/Yaagl OS.app` entry point is retained. Only its bundled `resources.neu` and the active support-directory copy are replaced. Matching whole-second timestamps preserve the existing wrapper's copy precedence. Helper distributions, other sidecars, native launcher, wrapper, release companion, Wine, settings and game files are not substituted.

The deployment scripts require normal shutdown, verify retained identities and clean patch state, and capture current evidence plus a fresh snapshot of both accepted resources before replacement. Rollback restores that snapshot and exact original timestamps. It preserves fresh evidence first and never replays obsolete markers/backups. Unknown changes stop for review; later legitimate settings/runtime updates are not automatically reset. The previous release archive and verifier remain unchanged.

After normal shutdown:

```bash
P="$HOME/Library/Application Support/YAAGL Local Builds/genshin-settings-ui-20260909/deployment"
bash "$P/permanent.sh" verify
```

To return to the accepted Genshin-only build:

```bash
bash "$P/permanent.sh" rollback
bash "$P/permanent.sh" status
```

The two-resource installer and rollback passed 26 temporary-file tests, including actual rsync behavior, interrupted substitution, unexpected helper/runtime/settings changes and current owned-backup validation. Installation and independent review records, screenshots and mock-test evidence are kept outside Git. The tested resource and this source commit are bound by the new installation manifest; no extra rebuild is required for documentation.
