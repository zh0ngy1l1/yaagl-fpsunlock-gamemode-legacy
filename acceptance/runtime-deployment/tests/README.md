# Offline transaction audit

`run_audit.py` exercises the actual `RuntimeTransaction` prepare, deploy,
replacement, inspection, journaling and restore methods on fresh disposable
copies. It never calls the production factory, runs Wine, loads the runtime,
starts a product process, or writes the recovered installation or prefix.

Provide the frozen copied original (`f26ade35…`) and reviewed staged signed V2
candidate (`eef64f61…`) as `--original` and `--candidate`, and a fresh canonical
directory outside product paths as `--output`. The runner preserves every
replica and writes `RESULTS.json`; each transaction case writes its own
`test-evidence.json`. Source hashes before and after execution must agree.
Existing output directories are never reused. Python bytecode caches are
disabled during the audit.

The three ordinary round trips use fresh destinations: the recorded metadata
profile, an additional ordinary required xattr, and an actual ACL entry. They
verify original bytes, an independent rollback inode, the signed candidate after
atomic replacement, restoration through the same core in a new object,
original signature/metadata, and final state. Separate interruption tests use
both explicit faults and an actual native Python child that exits immediately
after deploy/restore replacement, before a completion record can be written.
Those children execute only the transaction tool, never the Wine artifact.

| Assumption | Coverage |
|---|---|
| Only frozen runtime bytes are admitted | Wrong original/candidate/rollback, truncated rollback, valid differently signed candidate, already-patched slot, third identity |
| Rollback and installed paths retain object identity | Symlink slot, rollback hardlink, external same-hash original inode, late parent swap at native creation boundary |
| Required security metadata is preserved | Actual mode/flags/ACL changes, native required-xattr removal, actual quarantine addition, quarantine value policy mutation |
| Provenance is narrowly qualified | Recorded old0→generated2 policy replay; missing/unsupported values; wrong role; same-inode post-seal replacement with another allowlisted value |
| ACL absence is not every unsuccessful query | Native absent ACL, a real allocated empty ACL object delivered through a getter mock, explicit native error injection |
| Verification cannot seal a stale observation | Source changes during inspection, candidate changes after first verification, destination changes before replacement, slot changes immediately before deployment/restoration seal |
| Atomic replacement assumptions are enforced | Existing temporary collision, device mismatch injected at the explicit same-filesystem check, actual late directory rename/symlink with outside sentinel |
| Interrupted operations remain recoverable | Post-replacement failure, missing completion seal, fresh transaction recovery, actual abrupt child exit, restoration failure, idempotent restored-state verification |
| Protected-product guard keeps unrelated differences visible | Pure normalization fixtures for exact runtime/owned temporary changes, unknown identities, unrelated files/settings, parent ownership/mode/flags/size |

Owner mismatch, unsupported/forged provenance, cross-device identity and some
native inspection errors are explicitly injected captured records or interfaces.
They are policy/branch checks, not claims that a privileged chown, different
volume, arbitrary provenance assignment, or OS error occurred. Native ACL/xattr
copying, static signature verification, same-filesystem replacement and the
ordinary round trips use real host interfaces and real copied files.

The fresh transaction source copies already carry the locally generated
provenance value. They do not reproduce the original installation's old value.
Separate `universal-runtime-metadata-review/direct-source-reproduction/RESULTS.json`
records three native copies from the installed source opened read-only into
fresh external destinations: all reproduced old0→generated2, preserved the
required metadata and signature, and left the source unchanged. The immutable
stopped-copy evidence and the transaction policy replay remain separate records.
No test writes or resumes the stopped transaction.

The sealed broad record is `test-audit/run-005/RESULTS.json`: 55 passing tests
against core `1dc0b331…` and adapter `cced3c67…`. The final targeted record is
`test-audit/final-addendum-001/RESULTS.json`: 12 passing tests against final core
`f996ea36…` and adapter `1f7f337e…`. The latter covers the added historical-parent
admission checks, mocked preflight refusals, descriptor cleanup on parent-binding
failure, and one additional fresh full round trip. The unchanged broad mechanism
coverage is reused; the 55 tests are not represented as having run against the
later files. Both records pin unchanged sources throughout their own run.

The quarantine control deliberately constructs an unsupported security-metadata
copy: native copying changes its quarantine value, so rollback verification must
stop. This is a negative result, not an invitation to ignore quarantine with
provenance or to edit the original attribute.

Frozen staging input hashes and disposable outside sentinels are checked. These
checks, restricted mutation paths and the separate protected-product snapshots
bound the unchanged-product claim; they are not a global machine-wide proof that
no unrelated process changed any filesystem object.
