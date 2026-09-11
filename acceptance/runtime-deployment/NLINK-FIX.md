# Owned staging entry and parent link count

Authorization: `chat-2026-09-11-r2-nlink-fix-deploy`.

The stopped transaction `20260911T131353569146Z-r2-static` remains immutable
`PRE_INSTALL` evidence. It had no replacement intent or completion seal. Its
original installed inode2834486 was unchanged; its sole retained candidate
temporary was inode3128308. No rollback or admission from that transaction is
reused.

Evidence is retained outside the product under
`~/Library/Application Support/YAAGL Local Builds/genshin-fps360-20260909/nlink-fix-20260911T133040929939Z/`.
`CAUSE-PROOF.json` independently compares the historical/pre-staging parent,
stopped post-staging parent, full protected snapshot and bound shallow directory
inventory. Only the exact recorded temporary was added: no baseline entry was
missing or changed. After the old normalizer removed its name and 32-byte size
effect, the sole remaining difference was parent `stat.nlink`34→35.

`ONE-FILE-APFS.json` records a fresh ordinary-file experiment on the same APFS
device16777233: parent nlink2→3→2 and size64→96→64, with a stable parent inode.
`CAPTURE-NOTE.json` preserves the initial report-capture error and distinguishes
it from this recorded experiment. Neither experiment touched product files.

The old stop was correct under its implementation. The comparison was wrong for
its own intentional staging entry: the APFS link-count effect remained after
the entry itself had been normalized away. Directory nlink remains a control.

The correction makes the allowance depend on a sealed, fully verified temporary
record and its actual exclusive-copy inode. The prior stage-plan pathname alone
is insufficient. While that one exact entry is present, only its measured +1
nlink and +32 size effects are normalized. Foreign or missing baseline entries
remain in the comparison, even when their entry counts cancel. Parent identity,
device, mode, ownership, flags, ACL and xattrs remain checked. The complete guard
and a bound-parent inventory check run immediately before the existing rename.
After rename, the owned temporary must be gone and the incoming inode must occupy
the slot; no staging count allowance remains.

The small core change is necessary because the old verified inode record was
sealed in the replacement intent, after the failing staging guard. The core now
seals that record earlier and invokes the final descriptor-bound guard. Native
copy flags, metadata policy, replacement, fsync and recovery mechanisms are
unchanged. No runtime byte, signature, frontend, companion, prefix or setting is
changed by this source correction.

Focused verification is in `tests/test_nlink_guard.py`, run by
`tests/run_nlink_review.py`, alongside the directly relevant existing core and
normalization tests. The native complete disposable roundtrip uses the actual
production normalizer, ownership-ledger reader and bound-parent verifier, with a
disposable inventory collector. It exercises the +1 staging effect during both
deployment and restoration. Snapshot-only mutations are labeled separately from
native file/ACL/xattr/flag changes. These tests establish transaction guard
behavior, not Wine or gameplay reliability.

Authorized cleanup of the old retained temporary is a separate one-shot,
descriptor-bound operation recorded only in the new evidence root. It must
revalidate the immutable stopped records, absent intent, exact original and
temporary identities, full directory state and process absence before unlink.
A later deployment uses a new ID, new admission, new rollback and the corrected
reviewed source hashes. The signed revision-2 candidate remains
`eef64f611ae9033261a70f46ec0be38d58823717f14e80331946c6d0cd3c85f7`.
