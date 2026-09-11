# Prepared controlled deployment and restoration — fresh authorization required

This is a procedure for later explicit authorization. It is not an installer.
It performs no build inside the recovered installation and authorizes no game,
Wine invocation, tracing, diagnostic run or merge. Stop on any mismatch; do not
refresh an expected hash to match unexpected installed bytes.

The stopped transaction `20260911T014510484553Z-v2-controlled` is immutable
historical evidence. Do not resume it or repair/reuse its rollback. Its
provenance mismatch was a correct stop under its implemented all-xattrs-equal
rule. This revised procedure requires a **new deployment ID and new explicit
authorization**, including the disclosed managed-provenance transition below.
The earlier authorization does not carry over to the revised transaction.

## Required metadata policy and implementation

Read [the metadata policy](runtime-deployment/METADATA-POLICY.md) and the
review package before preparing admission. It is restricted to macOS build
`25G83` and the exact reviewed file/process context. Provenance is
security-relevant attribution; this procedure does not claim to recreate the
original inode's ExecPolicy or Gatekeeper history.

For this next deployment, the protected original must still carry
`com.apple.provenance=010000dcd5bccdc7edc92e` with its captured original
inode/metadata. The frozen staged input and newly transaction-created files
must carry the reviewed value `01020059c71153554e5113`. The actual independent
rollback copy confirms that new-file value before any temporary is created in
the installed runtime directory. It cannot authorize a different new value.
Pin each object's raw value and inode through its subsequent operations.
Record source/destination provenance and the native copy/rename lineage.
Never manually assign or remove provenance to force a match.

Every **other** xattr name and raw value remains an exact control, including
quarantine, FinderInfo, resource forks and security attributes. Mode, owner,
group, flags, mtime and ACL state/content must also match the captured original.
ACL absence, present-empty ACL and inspection errors remain distinct. Record
copy-time atime and later read drift; new inode, ctime and birthtime are instance
metadata. Restoration recreates required metadata and protected signed bytes;
its new provenance must be the reviewed generated value, not forged history.

The shared implementation is
[`runtime-deployment/transaction.py`](runtime-deployment/transaction.py).
Its command-line mutation interface admits disposable replicas only. A future
production invocation must use the reviewed production admission/guard adapter
and a fresh authorization record. The same copy, verification, intent,
replacement and restoration code exercised in the offline rehearsal is used
for production. The adapter may load the hash-pinned old script's read-only
snapshot functions; never call its preflight/save/copy/install entry points or
execute it as a command. This does not resume the stopped transaction.

This is a controlled, stopped-process transaction, not protection against an
actively malicious same-user writer. Directory descriptors and rechecks bind
owned operations; a competing updater/writer must be absent. Durable journal
records are fsynced for process-interruption recovery. No power-loss guarantee
or authenticated journal against same-user tampering is claimed.

After fresh authorization, use the package-pinned hashes (never hashes refreshed
to match unexpected local files) with
`protected_guard.create_authorized_admission(...)`. Supply a fresh external
transaction root, the actual authorization reference, explicit consent to this
managed-provenance policy, and the reviewed core/adapter/procedure hashes. This
first checks historical file and parent identities, signatures, ACLs and the
protected product before creating external admission material. Historical
parent mode/owner/group/flags/device/inode must match; historical parent ACLs
were not captured, so inspect and pin their current state without claiming
retroactive equality.

Then obtain `protected_guard.authorized_transaction(root)`, call `prepare()`
to verify rollback, and call `deploy()` only after that succeeds. Reopening the
same authorized transaction and inspecting `status()` uses its durable records;
`restore()` is the shared recovery path under the explicit restoration policy.
No step automatically launches a product process. Do not call these production
functions during offline review. The CLI remains replica-only.

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
   hash/size against the protected original and verify its signature. Require
   a single link and a different inode. Verify exact required metadata and all
   non-provenance xattrs, and the explicitly allowed provenance transition.
   Seal the pre-deployment identity/settings manifest and rollback manifest.
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
   reinstall the companion or rewrite preferences. Remove owned temporary
   files only after ownership/identity verification; retain evidence on failure.
   Keep the verified rollback copy outside the installation. Fsync the verified
   temporary and a durable intent binding prior and incoming identities before
   the directory-descriptor-bound same-filesystem replacement. Refuse existing
   temporary names and cross-filesystem replacement; no copy fallback.
7. **Verify installed candidate hash.** Read back the installed file independently
   and require the reviewed signed hash and size. Record metadata and the exact
   changed destination, including incoming inode and exact pinned provenance.
   On failure, stop and preserve evidence. Restoration is permitted only when
   the durable intent and current object still establish the known owned state;
   an unknown identity/metadata/provenance or path state must not be overwritten.
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
or report restoration success. A familiar hash alone is insufficient: an
idempotent original must be the pinned baseline instance or this transaction's
verified restoration instance. The candidate must be the instance bound by the
deployment seal or durable interrupted-replacement intent. Any unexplained
same-hash replacement or metadata drift also stops recovery.

Copy the verified rollback bytes to a fresh owned temporary file in the target
filesystem, apply and verify the captured required metadata there, and atomically
replace only the selected library. Verify the original hash/size/signature and
required metadata after replacement.
Recheck the unchanged frontend/companion/game, prefix identity and relevant
settings. Run the existing protected verification and require all six patch
originals, no owned backups/marker and no selected processes. Seal restoration
results; retain the external rollback copy and evidence.

Post-restoration provenance is the recorded managed value
`01020059c71153554e5113`; original code/hash/signature and required metadata are
restored, while the inode and security attribution are new. A later deployment
must be anchored in that verified restoration record with a newly reviewed
admission; do not update the historical-original expectation merely to match a
new object. If a later authorized load changes provenance or another required
metadata field, stop for review before restoration rather than widening this
static policy automatically.

Gameplay legitimately writes caches, saves and registry data. For a future game
run, prefix **identity** and selected configuration invariants remain required;
record content changes instead of falsely requiring the whole prefix to be
byte-identical after play. This differs from deployment-only verification, where
no such writes are expected. Explicitly authorized suite target changes must be
recorded and returned to the saved baseline using the normal settings path;
unrelated settings changes are not silently discarded.
