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

## Phase-aware directory guard regression

`run_nlink_review.py` runs the focused staging-directory tests plus the directly
relevant existing parent, temporary, recovery and normalization checks. It uses
the same three path arguments as `run_audit.py` and requires a fresh disposable
output. The updated normalization fixtures explicitly include parent `nlink` and
verified temporary records; a phase name alone no longer stands in for ownership.

`test_nlink_guard.py` supplies a native, descriptor-bound disposable inventory to
the actual production normalization, sealed temporary-ledger reader and final
bound-parent verifier. Its full prepare/deploy/restore round trip therefore tests
the guard/core integration that the earlier blank-guard core rehearsals omitted.
The APFS parent must show exactly one extra link and 32 extra bytes while its own
verified temporary exists, and return to the baseline after replacement. No
actual product admission or installation is available to this fixture.

The focused tests reject missing/substituted/unowned temporaries, foreign entries,
missing baseline entries, and a foreign addition that cancels a missing baseline
entry's count. They challenge both excessive and missing staging `nlink` effects,
post-replacement drift, and a foreign entry introduced at the final bound-parent
check. Actual disposable mode, flags, xattr and ACL mutations reach that verifier;
UID/GID/device substitutions are explicitly labeled snapshot mutations. The
selected existing tests retain native late-parent-redirection and durable
recovery coverage.

Recorded correction validation is under
`nlink-fix-20260911T133040929939Z/focused-002/RESULTS.json`: 35 passing focused
checks, with a separate 12 passing existing adapter-addendum checks in
`final-adapter-addendum-001/RESULTS.json`. `focused-001` remains a failed test run:
34 checks passed and the native ACL test's unsupported numeric `chmod` principal
caused a fixture error. The fixture was corrected to use the account name before
the fresh successful run. Neither that error nor its archived source is erased.
