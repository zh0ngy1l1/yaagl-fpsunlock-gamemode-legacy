# Prepared controlled deployment and restoration — DO NOT EXECUTE YET

This is a procedure for later explicit authorization. It is not an installer.
It performs no build inside the recovered installation and authorizes no game,
Wine invocation, tracing, diagnostic run or merge. Stop on any mismatch; do not
refresh an expected hash to match unexpected installed bytes.

## Frozen inputs

| Component | Expected identity |
|---|---|
| Selected game / Wine | Genshin; `11.0-dxmt-signed-with-patches` |
| Original `wine/lib/wine/x86_64-unix/ntdll.so` | 620688 bytes; SHA-256 `f26ade35f5b49e33b3780b6adc71f9eb9c831ea40222c1bae667ac14135d984b` |
| Reviewed signed replacement | 620688 bytes; SHA-256 `eef64f611ae9033261a70f46ec0be38d58823717f14e80331946c6d0cd3c85f7` |
| Protected frontend | Source `a0e8c704327e0d2568fbb4a0c569eee1f2188110`; both resources SHA-256 `4724889a8f29703f491c6ae2b1b4ad03819ca63c2229eca1dd4cd52a2ec42b96` |
| Ordinary companion v3.0.7 | SHA-256 `8543f45a4edced854ab8c5466ce2dc2e511fb4f89361bc4dfb474b68d998cc17`; 39661090 bytes; source tag `56b9c64381ef9fd59e916dc9bf547d3210ab5db1` |
| Exact game | SHA-256 `a1a23cb76d941df28c5156ca3152fa49421ec98842221b7d71633d42ee76ca45`; native AMD64 PE32+, NX compatible, launcher version7.0.0 |
| Excluded recovery | `a2f6568`; no checkout, artifact or restoration input from it |

Resolve the selected library under
`~/Library/Application Support/Yaagl OS/hoyoplay-wines/genshin/11.0-dxmt-signed-with-patches/`.
Resolve the existing prefix under
`~/Library/Application Support/Yaagl OS/wineprefix`, and the game at
`~/.gimpact/GenshinImpact.exe`. Resolve symlinks and record actual paths,
device/inode identities and ownership; refuse unexpected redirection. The ordinary
companion is under the existing prefix's `drive_c/fps-unlocker/unlockfps.exe`.
The final review package supplies the exact staged replacement path and its build
manifest. Take those already-reviewed bytes; do not call the builder with a live
Wine path as input or output.

## Ordered deployment transaction

1. **Verify recovered baseline.** Confirm no selected game, companion, launcher or
   per-game Wine processes are running using native process inspection only.
   Run the existing read-only protected verification. Independently verify the
   selected installed library's original hash, size, regular-file status, link
   policy, ownership/mode and signature. Refuse an already-patched installation.
2. **Bind the rest of the product.** Verify both frontend copies, ordinary
   companion and game against the table. Record the resolved prefix identity,
   its relevant configuration files and the saved FPS keys. The preparation
   baseline observed target160/enabled=true; compare against the review's captured
   baseline rather than silently replacing later user choices. Verify renderer,
   in-game60 setting, per-game Wine/prefix selection, power-save state, and absence
   of any diagnostic sidecar/arm file. Record missing config files as missing.
3. **Create rollback material.** In a fresh rollback directory outside the runtime
   and prefix, copy the original library as independent bytes, never a hardlink.
   Preserve and record its mode, ownership, timestamps and signature. Verify its
   hash/size against the protected original and verify its signature. Seal the
   pre-deployment identity/settings manifest and the rollback manifest.
4. **Refuse identity drift.** Re-read all required baseline identities and relevant
   settings immediately before replacement. Verify no selected process started.
   Refuse deployment if any expected input differs, backup verification failed,
   or the runtime changed while read. Retain evidence; do not proceed partially.
5. **Take the reviewed staged artifact.** Verify the final package's staged signed
   candidate hash, size, signature and provenance. Require the exact reviewed
   artifact, including its code-signature identity; a different valid signature
   is not interchangeable without review. No rebuild is part of deployment.
6. **Replace only the library.** Copy the reviewed staged bytes to a newly and
   exclusively created temporary regular file in the destination filesystem.
   Verify that copy before atomically replacing only `ntdll.so`. Preserve the
   original file's required permissions/ownership. Never follow an unexpected
   symlink, overwrite other files, replace the Wine directory, change its tag,
   reinstall the companion or rewrite preferences. Remove only owned temporary
   files. Keep the verified rollback copy outside the installation.
7. **Verify installed candidate hash.** Read back the installed file independently
   and require the reviewed signed hash and size. Record metadata and the exact
   changed destination. On failure, stop and perform the restoration transaction.
8. **Verify installed signature.** Use native static `codesign --verify --strict`
   and signature-description checks. Do not load the library or invoke Wine.
9. **Verify unchanged executables.** Recheck frontend, ordinary companion, game,
   all unrelated selected-runtime inventory entries and existing patch originals.
   Only the reviewed library delta may differ from the deployment snapshot.
10. **Verify unchanged prefix/settings.** Compare prefix identity and its captured
    contents/settings with the deployment snapshot. There was no game execution,
    so unexplained prefix/configuration mutations are failures. Confirm saved
    target/enabled/renderer values, absence/presence of each config file and no
    diagnostic dependency. Do not restore unrelated user changes silently.
11. **Seal the installed-candidate record.** Record authorization reference,
    timestamps, source commits, original/backup/staged/installed hashes and sizes,
    signature results, prefix identity, settings snapshots, per-game Wine path,
    component inventories and the allowed single-file difference. This record
    is the later acceptance precondition; deployment itself establishes no
    gameplay success or native shutdown resolution.
12. **Keep deterministic restoration available.** Preserve both original and
    candidate identities and the restoration procedure below. Stop here until
    gameplay is separately authorized. No automatic launch follows deployment.

## Restoration transaction

First collect logs/dumps/media and all post-run identities before changing bytes.
Require the game/launcher/companion and selected Wine processes to have exited;
do not kill unrelated processes or run a broad/global wineserver command.

Verify the rollback file's original hash, size and signature. Verify that the
installed file is exactly the reviewed candidate. If it is already the exact
original, record an idempotent restored result after checking the remaining
components. If it has any third identity, stop: do not overwrite unknown bytes
or report restoration success.

Copy the verified rollback bytes to a fresh owned temporary file in the target
filesystem, verify it, atomically replace only the selected library, restore the
captured metadata, and verify the original hash/size/signature after replacement.
Recheck the unchanged frontend/companion/game, prefix identity and relevant
settings. Run the existing protected verification and require all six patch
originals, no owned backups/marker and no selected processes. Seal restoration
results; retain the external rollback copy and evidence.

Gameplay legitimately writes caches, saves and registry data. For a future game
run, prefix **identity** and selected configuration invariants remain required;
record content changes instead of falsely requiring the whole prefix to be
byte-identical after play. This differs from deployment-only verification, where
no such writes are expected. Explicitly authorized suite target changes must be
recorded and returned to the saved baseline using the normal settings path;
unrelated settings changes are not silently discarded.
