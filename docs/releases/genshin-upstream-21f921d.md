# Genshin-only upstream UI: local release

The gameplay-tested source is `21f921d982cb44dda521e81b6af9416023d3b837`, on `ui/genshin-only-upstream`. The documentation commit following it adds this release record and input manifest; it does not change runtime source or rebuild the tested payloads. Keep the complete matching Sophon distribution with the frontend.

| Tested artifact                    | SHA-256                                                            |
| ---------------------------------- | ------------------------------------------------------------------ |
| `resources.neu` (1,057,762 bytes)  | `1f4c8b693865e85e1256a506687a1005559372037a90cde1409148ad66f35f83` |
| `sophon-server` (42,860,848 bytes) | `329958a1d208da65f3cb60f54a77a7b1e1328824fac262a59cd9ed52d39ca499` |

The matching helper distribution has 19 files totaling 77,957,888 bytes. [The portable input manifest](genshin-upstream-21f921d-inputs.json) records its complete file identities, build tools, lockfiles and required inputs. Local release payloads and installation/rollback records are preserved separately under `~/Library/Application Support/YAAGL Local Builds/genshin-upstream-21f921d`; The durable payload paths are `release-inputs/resources.neu` and `release-inputs/sophon_server/`, with `MANIFEST.json` and `SOPHON-MANIFEST.json` alongside them. Personal diagnostic evidence is not part of Git.

## Scope and validation limits

The presentation follows upstream revision `06c68119da74f19246419e93663a270f76506aae`: background/theme, logo/version link, compact launch/settings controls, progress/predownload and grouped settings. HSR/ZZZ registrations, client trees, settings, launch/update routes, exclusive assets/metadata and Sophon support were removed to keep this launcher focused on Genshin. Genshin OS/CN/Bilibili options and shared download/runtime infrastructure remain. Old users' installations, prefixes, saves and stored data are not removed.

The numeric FPS control remains editable. At selected target 150 the existing literal-150 interception passes argument 150 and DXMT 150 to the original release companion, while cloning the game environment and replacing that game's final DXMT rate with 0. Other environment entries are retained. This is not a generalized FPS implementation for other targets. Disabled unlocking, selected per-game Wine/prefix, ordering, companion lifecycle, Wine waiting and patch cleanup retain their tested Genshin behavior. Recovery correction `a2f6568` is excluded.

The candidate has **one user-reported successful one-minute run**: normal startup, login/world entry, no crashes, typical HUD 150, maximum 153, minimum unrecorded, no observed sustained drops or exact-120 plateau, launcher-ready return and normal shutdown. The UI was reported functional. Initial controls and natural cleanup passed; zero new dumps were reported. The planned two-minute duration and repeated reliability remain unverified. A later post-recovery cleanup value of `None` is not a replacement for the preserved initial natural-cleanup result. Matching source or launch commands do not establish equivalence to an older installed artifact.

Completed engineering checks included TypeScript, focused lint, mocked packaged launch/configuration checks, isolated UI/startup checks and screenshots, helper request/region/removal tests, and package inspection. These checks do not establish gameplay reliability or a Wine root-cause correction. The retained lint warning is an existing `any` in `src/sophon.ts`; unrelated formatting in the older build script was left unchanged.

## Pinned build procedure

Use a separate checkout/worktree of this documentation revision for reproduction; its runtime source is unchanged from the tested commit. Do not run the broad cleanup or dependency-refresh scripts in an installation or a shared build tree. Generated output stays ignored; existing tracked sidecars and their licenses are required. No game binaries, Wine installation or FPS companion is needed to compile the launcher.

The inspected build used Node 22.23.2, pnpm 9.15.9, Neutralino CLI 9.8.0, TypeScript 4.9.5, Vite 3.2.11, Solid 1.9.7 and semver 7.7.2. Use `pnpm install --frozen-lockfile`; do not regenerate `pnpm-lock.yaml`. The helper used Python Build Standalone 3.13.15 **x86_64**, uv 0.12.10, Nuitka 2.7.16, protoc 31.1, protobuf 6.31.1, clang 21.0.0 and Nuitka's ccache 4.2.1. `sophon_server/uv.lock` pins all Python packages. The stored `.python-version` names a Python minor/architecture, so explicitly select 3.13.15 when creating a fresh environment.

1. Prepare ignored native/client inputs from these versioned release assets, then verify the extracted files against the input manifest before use:

   - Neutralino binaries: `https://github.com/3Shain/neutralinojs/releases/download/v4.11.0-1/neutralinojs-v4.11.0.zip`, extracted under `bin/` as in `configure.sh`.
   - Client library: `https://github.com/neutralinojs/neutralino.js/releases/download/v3.9.0/neutralino.js`, saved as `neutralino.js`. The existing configuration's clientVersion label is 3.8.0; the pinned actual file, rather than that label, identifies the tested input.
   - Protobuf compiler: `https://github.com/protocolbuffers/protobuf/releases/download/v31.1/protoc-31.1-osx-universal_binary.zip`, extract its `bin/protoc` member as `bin/protoc`.
   - `sidecar/` binaries and licenses are tracked at the tested source revision. Do not replace them with current upstream binaries or run `neu update`.

2. Generate the ignored metadata source without printing its contents:

   ```bash
   python3 - <<'PY'
   import base64
   from pathlib import Path
   Path('src/clients/secret.ts').write_bytes(
       base64.b64decode(Path('src/clients/secret.b64').read_bytes()))
   PY
   pnpm install --frozen-lockfile
   ```

3. Prepare the helper in that isolated worktree. These commands compile source and do not launch the server or game:

   ```bash
   cp sidecar/hpatchz/hpatchz sophon_server/hpatchz
   (
     cd sophon_server
     ../bin/protoc --python_out=. manifest.proto manifest_ldiff.proto
     uv sync --frozen --python cpython-3.13.15-macos-x86_64-none
     NUITKA_CACHE_DIR=./.cache uv run --frozen --python cpython-3.13.15-macos-x86_64-none python -m nuitka \
       --warn-implicit-exceptions --warn-unusual-code --standalone \
       --python-flag=isolated --include-data-files=./hpatchz=./hpatchz \
       --output-filename=sophon-server --output-dir=./build \
       --assume-yes-for-downloads server.py
   )
   rm sophon_server/hpatchz
   ```

   Verify generated protobuf files and the pinned inputs:

   ```bash
   python3 - <<'PY'
   import hashlib, json
   from pathlib import Path
   m = json.loads(Path('docs/releases/genshin-upstream-21f921d-inputs.json').read_text())
   for name, info in {**m['inputs'], **m['tracked_sidecars']}.items():
       p = Path(name)
       assert p.is_file(), f'Missing input: {name}'
       assert p.stat().st_size == info['size'], f'Size differs: {name}'
       assert hashlib.sha256(p.read_bytes()).hexdigest() == info['sha256'], name
   print('Pinned file inputs verified')
   PY
   ```

4. Run focused validation and package the frontend using the same channel and **no YAAGL_VERSION**:

   ```bash
   pnpm exec tsc --noEmit
   pnpm exec eslint src/launcher/hoyoplay.tsx src/launcher/hoyoplay-injections.ts src/clients/mhy/patch.ts src/sophon.ts
   env -u YAAGL_VERSION YAAGL_CHANNEL_CLIENT=hoyoplay node ./build-app.js
   ```

   Outputs are `Yaagl OS.app/Contents/Resources/resources.neu` and `Yaagl OS.app/Contents/Resources/sidecar/sophon_server/`. For CN packaging use the preserved `hoyoplaycn` distribution; that would be a distinct artifact from the tested OS release.

The tested build reused its already-locked environment and generated protobuf files; it did not reinstall packages or regenerate code. A fresh environment using these instructions must be verified. Native toolchain paths, signatures and timestamps can change rebuilt outputs; byte-identical reproduction is not asserted. Promote the preserved exact tested resource/helper instead of replacing them with a new untested rebuild.

## Loading and updates

The existing app wrapper copies its `Contents/Resources` into `~/Library/Application Support/Yaagl OS` using `rsync -rlptu`, changes to that directory and launches the native executable with `--path` pointing there. Matching resource and complete helper payloads therefore belong in **both** the app bundle and active support directory. `-u` skips destination files newer than the bundle; promotion verifies both bytes and timestamp precedence. The native executable and wrapper can remain unchanged.

Genshin starts `./sidecar/sophon_server/sophon-server` directly. Its metadata/temp caches are not a separate helper extractor or executable loader. Do not preserve only the executable while replacing or omitting the matching libraries.

This exact resource embeds launcher version `development`. The compiled launcher updater returns `latest:true` before making a release API call; it does not immediately replace the promoted payload and no update-disable setting is required. Genshin metadata checks and its game-update/predownload functions remain enabled.

A future build with `YAAGL_VERSION` set checks upstream launcher releases and may show an update prompt. Downloading requires the launcher-update action; `ignore_launcher_update` suppresses one version's prompt, not all updates. Accepting an upstream launcher update can replace the custom active resource and may not supply this matching Genshin-only helper. Keep game updates separate from launcher updates and verify/redeploy the coherent local payload pair when intentionally changing launchers. Replacing the app bundle also changes the wrapper's next-start copy source.
