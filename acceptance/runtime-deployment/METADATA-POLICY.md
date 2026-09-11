# Reviewed macOS metadata policy for the next deployment

This policy is limited to the reviewed machine, macOS 26.6.2 build **25G83**,
the selected Genshin Wine library, and a fresh, separately authorized static
transaction. It changes deployment tooling only. It neither authorizes an
installation nor changes the signed revision-2 runtime candidate.

## What failed, and what did not

The immutable transaction `20260911T014510484553Z-v2-controlled` stopped before
installation. Its independent rollback copy had the same 620,688 bytes and
SHA-256 `f26ade35f5b49e33b3780b6adc71f9eb9c831ea40222c1bae667ac14135d984b`,
valid signature, independent inode, and matching required permissions,
timestamps and ACL state. Its only reported mismatch was:

| Object | Raw `com.apple.provenance` |
|---|---|
| Protected original inode | `010000dcd5bccdc7edc92e` |
| New rollback inode | `01020059c71153554e5113` |

That is evidence of a failed all-xattrs-equal control. It is not a completed
deployment, corrupted rollback payload, or proof that provenance is irrelevant.
The old transaction, its rollback and its result remain immutable. The earlier
ACL-inspection stop also remains in that record; it is a separate issue.

The previous `DEPLOYMENT.md` required independent rollback bytes, signature,
permissions and timestamps and broadly referred to restored metadata. It did
not specifically require cross-inode raw provenance equality. The old
transaction introduced that stricter comparison. This revision explicitly
resolves the policy rather than deleting a check to make it pass.

## Platform evidence and its limits

Provenance is security-relevant attribution associated with application/process
activity and local ExecPolicy tracking. It is not a unique inode number and is
not part of the Mach-O embedded signature. Multiple files on this machine have
the same value. The exact historical database records for these two values
could not be read, and the leading three bytes are not a documented schema.
This policy treats both values as opaque reviewed constants, not decoded flags.

The exact host libcopyfile identifies itself as **240.160.2.0.1**, ARM64e UUID
`d0009b8a8ecc3d5692067e1839707f93`. The available Apple source is copyfile-240,
not an exact maintenance-build match. It enumerates generic xattrs and calls
`fsetxattr` (`copyfile.c:3872`); it does not establish persistent equality by
reading them back. The local `COPYFILE_ALL` API requests data, stat, ACL and
xattr copying. A success return alone is insufficient to prove the final raw
value. The installed security service has provenance/Tracking Gatekeeper
functionality; nearby public XNU source has security notification hooks for
metadata changes. The precise closed-source hook responsible here is unproved.

On this host, seven copy mechanisms each succeeded at three fresh destinations.
All 21 copies retained exact original bytes and valid signatures and recorded
`01020059c71153554e5113`. Their reviewed copied source already had that value;
this 21-case matrix alone does not establish an original-value-to-new-value
transition. A subsequent authorized read-only-source experiment opened the
protected original only `O_RDONLY` and made three fresh independent disposable
copies through the shared `fcopyfile` body. All three reproduced
`010000dcd5bccdc7edc92e` to `01020059c71153554e5113`, with exact original
hash/signature/required metadata. The source inode, bytes, xattrs, ACL and
required metadata remained unchanged after each copy. These new records
independently corroborate the immutable historical stopped-copy observation.
Three additional native copyfile
callback cases reported provenance copy START and FINISH. A control xattr was
copied, changed and removed normally. Attempts on disposable files to set the
historical provenance, zero/malformed values, or remove the attribute returned
success while readback stayed at the same current value. The independent
`xattr` command produced the same success/readback discrepancy.

Fresh creation, data writes, rename and atomic replacement retained the
observed current value in the disposable matrix. Rename transferred the
incoming inode; it did not create another inode. These are exact-machine
observations, not guarantees for every process, directory, volume or macOS
version. The transaction verifies the result of each operation.

Primary security research documents tagged dylibs acquiring linked ExecPolicy
entries when loaded. Exact byte/signature equality therefore cannot establish
identical future Gatekeeper, XProtect, loader or Rosetta behavior. Copying the
old raw key manually would not reconstruct its security database history.
Production tooling never sets or deletes provenance to force equality. Native
`fcopyfile` may attempt to copy it; its actual readback is checked and recorded.

References and saved source artifacts are in the external
`universal-runtime-metadata-review/metadata-audit/SEMANTIC-AUDIT.md` and
`AUDIT-ARTIFACTS.json`. Direct sources:

- [Apple copyfile source, pinned commit](https://github.com/apple-oss-distributions/copyfile/blob/9f91eb6ced021952278816cdc76ad68da8631ccb/copyfile.c)
- [Apple XNU xattr path, pinned nearby version](https://github.com/apple-oss-distributions/xnu/blob/ac9718fb1af618d5ce8678d0dc6e8a58f252216f/bsd/vfs/vfs_xattr.c)
- [FFRI original provenance research](https://github.com/FFRI/ShowProvenanceInfo)
- [FFRI whitepaper, Appendix B including dylib example](https://www.ffri.jp/wp-content/uploads/2026/01/USA-25-Koh-XUnprotect-Reverse-Engineering-macOS-XProtect-Remediator-wp.pdf)
- [Apple signature-verification limits](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/Procedures/Procedures.html)

## Rollback invariant

The rollback must restore the protected runtime's exact signed code and all
required file metadata. It does not recreate the old inode or historical
ExecPolicy database state. This disclosed security-attribution difference is
part of the policy requiring fresh authorization.

| Property | Required treatment |
|---|---|
| Executable bytes, size, hash, Mach-O contents and embedded signature | **1: exact in rollback payload.** Original hash and strict static signature verification both required; independently copied inode |
| Mode, owner/group, flags | **1/2: exact copy and captured restoration requirement.** No normalization or permission repair; drift blocks |
| mtime in nanoseconds | **1/2: exact copy and restored value.** Verify after metadata operations |
| atime | **4: evidence.** Verify native metadata copy preserves the copy-time value; later verification reads may advance it |
| ctime and birthtime | **3/4: new-instance metadata, captured.** Do not forge old inode history; pin within a stable object, allow the owned rename's ctime change |
| ACL absent, present-empty, present with entries | **1/2: exact state and serialized content.** Absence is distinct from empty ACL; inspection errors block |
| Quarantine and every other non-provenance xattr, including FinderInfo, ResourceFork and security namespaces | **1/2: exact complete name/value map.** Missing, extra or changed xattrs block. No general security-attribute exemption |
| Existing installed original provenance | **Exact preflight pin.** The next deployment requires the captured historical original value and inode; unexplained change blocks |
| Existing frozen staged candidate provenance | **Exact preflight pin.** Require the reviewed current value and captured file identity |
| Fresh rollback, candidate temporary, installed candidate and restored-original provenance | **3 plus explicit evidence.** Only `01020059c71153554e5113` is accepted for native transaction-created files with proved lineage; each new instance is pinned exactly thereafter |
| Inode | **3 plus control.** Rollback must be independent; temporary must be independent; installed result must be the staged inode; restoration must be the owned restoration inode |
| Link count | **Exact policy: one.** Hardlinked rollback and other unexpected links block |
| Device/filesystem and parent directories | **2 plus control.** Pin parent identities/permissions/ACLs; same filesystem for atomic replacement. Current reviewed scope is local APFS; no cross-volume fallback |
| Allocated blocks, APFS physical sharing, directory mtime/ctime changed by owned entries | **4: instance/operation evidence.** Logical independent copy is required; duplicate physical storage is not asserted |
| Unknown provenance or metadata state | **5: deployment-blocking** pending explicit investigation; never automatically enroll a new value |

An injected quarantine source `0081;00000000;YAAGLDisposableAudit;` was
normalized by native copying. The transaction rejected that copy. The tested
provenance rule does not excuse quarantine normalization or ignore all xattrs.

ACL handling uses a stable descriptor. NULL plus ENOENT requires corroborating
native successful ACL inspection; other failures stop. Nearby Apple Libc source
explains ENOENT for an absent filesec ACL property. Present-empty and present
nonempty serialized ACLs remain distinct from absence.

## Legal states and stopping rules

1. **Fresh pre-install:** current historical original, exact reviewed candidate,
   no selected processes, protected product guard passes, new transaction ID and
   provenance-aware authorization. No old stopped directory is reused.
2. **Rollback verified:** original hash/signature, independent inode, required
   metadata exact, known generated provenance confirmed by the actual native
   copy. This is the first controlled-copy calibration before any runtime
   temporary is created; it confirms the reviewed value rather than learning
   an arbitrary new value.
3. **Replacement prepared:** exclusively created owned temporary on the target
   filesystem, candidate hash/signature, original required metadata, known
   generated provenance; durable intent records prior and incoming instances.
4. **Installed candidate:** the incoming inode, exact candidate hash/signature
   and required metadata. Provenance must equal the pinned temporary value;
   an unexpected rename transformation is a failure.
5. **Restored:** an independently staged original created from verified rollback
   through the same replacement path; original hash/signature and required
   metadata, owned inode and known generated provenance, sealed restoration
   record. An unrelated same-hash file cannot be certified as this restoration.

Any mismatch stops the transaction and preserves evidence. There is no blind
automatic overwrite after failure. An interrupted owned replacement can be
restored only through its durable intent and exact current-instance checks;
unknown identity, metadata, provenance or ownership prevents restoration until
review. A failed restoration never records success. This distinguishes safe
recovery of a known candidate after an interrupted seal from overwriting an
unknown object merely because its hash is familiar.

After a successful restoration, the bytes are again the protected original but
its inode and attribution are the recorded new-instance values. Do not call
that drift from the historical inode, silently refresh the old baseline, or
pretend raw historical provenance was restored. Any later redeployment needs a
fresh admission anchored in the verified restoration record and renewed
authorization. The next deployment profile specifically starts from the
currently untouched historical original.

No runtime is loaded in this review. If a later authorized load changes
provenance, preserve it and stop acceptance/restoration for review; the current
static profile does not silently accept arbitrary post-load attribution.
Likewise the deployment-only full prefix/settings guard must not be reused to
claim gameplay leaves every cache or registry file unchanged. The gameplay
protocol needs its separately reviewed post-run guard and authorization.
