# Runtime deployment metadata review

This package corrects the independent-copy metadata invariant and supplies one
shared static deployment/restoration implementation. It is isolated from the
Wine correction, frontend, companion, observer, real prefix and protected source
baseline. The signed revision-2 candidate remains
`eef64f611ae9033261a70f46ec0be38d58823717f14e80331946c6d0cd3c85f7`.

Read [METADATA-POLICY.md](METADATA-POLICY.md), the parent
[DEPLOYMENT.md](../DEPLOYMENT.md), and the external review's `HANDOFF.md` before
using this package. No command in this README authorizes production mutation.

## Files

- `transaction.py`: shared descriptor-bound capture/copy, required metadata
  comparison, exclusive staging, durable intent, atomic replacement, exact
  post-verification, owned-instance restoration and interruption recovery.
- `protected_guard.py`: pinned read-only product snapshot adapter and future
  production admission. It reuses only the old transaction's verified read-only
  functions; it never invokes its deployment or evidence-writing entry points.
- `tests/test_transaction.py`, `tests/run_audit.py`: disposable native filesystem
  rehearsals, actual child-process interruption and explicit fault/mutation
  cases. Native operations versus injected record/API failures are labeled.
- `research/copy_matrix.py`, `research/provenance_controls.py`: the seven-method
  matrix and independent generic-xattr/provenance callback controls. These are
  research harnesses, not production installers. Explicit provenance setters
  occur only in their disposable probes.
- `research/reproduce_protected_copy.py`: separately authorized `O_RDONLY`
  source copies from the historical original into three fresh disposable
  files. It reproduces the original-to-current attribution transition and
  checks that the protected source remains unchanged after each copy.

The command-line transaction interface permits **replica paths only**. The
production factory requires a new admission and protected guard; it must not be
called in an offline review turn. Merely constructing a file that says
"authorized" does not provide user authorization.

## Reproducing offline verification

Use the already-reviewed copied original, never an installed Wine path, and the
already-reviewed staged candidate as read-only sources. Supply a new disposable
output outside every installed runtime, prefix and app tree:

```sh
python3 -B acceptance/runtime-deployment/tests/run_audit.py \
  --original '/absolute/review/artifacts/input/ntdll.so' \
  --candidate '/absolute/review/artifacts/builds/v2-reproducibility-one/ntdll.so' \
  --output '/absolute/disposable/new-test-id'
```

The runner refuses an existing output, retains per-case native metadata and
signature records and verifies that the executed source files stayed unchanged.
Each full rehearsal calls the same `prepare()`, `deploy()` and `restore()` bodies
as a future authorized transaction. It never loads either Mach-O library.
The final external validation record pins the exact executed source hashes.

Do not repeatedly run passing cases against unchanged code to inflate evidence.
The retained intermediate failed reviews document defects and fixture errors;
the final reviewed run is identified in the external handoff.

## Assumption-to-evidence matrix

| Assumption/control | Native experiment, regression or static evidence |
|---|---|
| Provenance is not ordinary payload metadata or unique per inode | Independent platform/source audit; 21 fresh copies share one value; three read-only original-source copies reproduce the attribution transition; raw setter/remove success with unchanged readback |
| Copyfile actually attempts provenance | Three native START/FINISH callback traces; nearby Apple copyfile source; ordinary xattr persistence/removal control |
| New value is constrained, not auto-approved | Exact original/new role checks; unsupported/missing/zero/novel provenance record mutations; copied-original value in new-file role rejected |
| Provenance exemption is not ignore-all-xattrs | Real missing xattr and quarantine tamper tests; native quarantine-normalization refusal; arbitrary required xattr full roundtrip |
| Required security metadata survives | Mode/flags native mutations; owner record mutation; ACL native entry roundtrip, unexpected ACL, absent versus allocated-empty and inspection-error cases |
| Exact signed artifacts only | Original/candidate/rollback wrong bytes, truncation, alternate valid signature, already-patched and unknown-third-identity refusals |
| Rollback and restored instance ownership | Independent inode/link checks; hardlink refusal; unowned same-hash replacement regression; full restoration instance checks |
| Copy/path containment | Symlink/sentinel tests; native late parent substitution and admitted-parent binding tests; exclusive creation and collision refusals |
| Atomic replacement assumptions | Same-directory descriptor-relative rename, device mismatch fault injection; no EXDEV copy fallback. No different-volume success claim |
| No stale verification seal | Actual source/destination metadata mutations and mutations after replacement/before final sealing |
| Known interrupted installation can be recovered | Actual Python child `os._exit(77)` after deploy and restore rename; new process verifies durable intent and uses real restoration body |
| Failed restoration cannot claim success | Failure before restoration replace, interruption before restoration seal and unknown-object refusal |
| Protected product guard has only intended exceptions | Snapshot mutation tests for exact phase-owned temporary, unrelated files/settings, library identity, parent security metadata and transaction-name constraints; read-only full real-product comparison |
| Old stop remains immutable; real product untouched | Independent before/after hashes and metadata of all 20 old transaction files, frozen input inspection, full read-only protected snapshot and no runtime temporaries |

## Limits

All filesystem successes here are on this machine's local APFS volume. Device
mismatch is fault-injected; no cross-volume deployment is claimed. Owner changes
and unforgeable provenance states are tested using captured-record mutations;
they are not misreported as privileged native changes. Ordinary quarantine and
custom-xattr mutations, ACL entries, path substitutions, renames and child exits
are real operations on disposable copies.

The 21-case matrix source already has the current attribution value. Three
separate descriptor-bound read-only-source copies independently reproduce the
original-value-to-current-value observation from the immutable stopped
deployment. None of these copies is an installation or a restoration experiment
on the historical inode.

Tests establish filesystem behavior and failure handling, not loading policy,
actual Rosetta behavior, gameplay stability or historical crash causation.
Security database history is not reproduced. Process-interruption tests do not
prove power-loss durability, and the transaction is not a defense against an
actively malicious same-user writer. No output claims that every file on the
machine was globally monitored: containment tests, protected snapshots, frozen
inputs and explicit external sentinels are the evidence for mutation scope.
