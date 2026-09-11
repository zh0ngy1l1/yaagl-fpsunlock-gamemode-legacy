The V2 builder creates a pinned offline binary derivative. It does not install, load, or execute Wine. Use only an archived or separately byte-copied original as input. Never pass an installed Wine path to the builder or its tests.

The old arbitrary `--input` / `--output-directory` interface has been removed. Both commands now require an explicitly declared staging root. The builder reads only `<root>/input/ntdll.so` and creates only `<root>/builds/<output-name>/`; the output name must be a new, simple directory name. It never creates the staging root, declaration, input copy, or `builds` parent itself.

Prepare a fresh absolute, canonical offline directory outside applications, launcher support, Wine distributions, and prefixes. Create real `input` and `builds` directories owned by the current user, with no write permission for other users. Byte-copy the reviewed original from an archive or existing offline capture into `input/ntdll.so`; symlinks, hardlinks, and special files are rejected. Use directory mode `0700`, declaration mode `0600`, and copied-input mode `0400` or `0600`. The copied file must have size 620688 and this SHA-256:

```
f26ade35f5b49e33b3780b6adc71f9eb9c831ea40222c1bae667ac14135d984b
```

Write `.yaagl-offline-runtime-staging.json` in that root with the following exact fields, replacing the example root with its canonical absolute path. The declaration is an explicit caller action; the builder does not write it or treat elapsed time as authorization.

```json
{
  "schema": 1,
  "purpose": "offline-runtime-build-only",
  "root": "/absolute/path/to/offline-artifacts",
  "input": "input/ntdll.so",
  "outputs": "builds",
  "input_sha256": "f26ade35f5b49e33b3780b6adc71f9eb9c831ea40222c1bae667ac14135d984b"
}
```

Run from this package, using that declared root:

```sh
python3 build_runtime_delta.py \
  --staging-root "/absolute/path/to/offline-artifacts" \
  --output-name v2-review-one

python3 test_build_runtime_delta.py \
  --staging-root "/absolute/path/to/offline-artifacts" \
  --result-json "/absolute/path/to/offline-builder-tests.json"
```

The builder enforces the complete input, source-patch, pre-sign, and signed SHA-256 values. Unknown or previously patched input, existing output, signature variation, source-patch mismatch, changed code, wrong paths, or detected input/staging changes cause failure. It verifies the original signature, uses host `/usr/bin/codesign` with the preserved identifier and no timestamp, verifies the final signature, and checks the complete signed hash. Failure removes only the newly created output directory if its recorded identity still matches; it preserves the input and preexisting destinations. The staging checks prevent accidental live-tree use and common path mistakes; they are not an isolation boundary against another process with the same user privileges.

A successful output contains:

| File | SHA-256 / meaning |
| --- | --- |
| `ntdll.pre-sign.so` | `9cc5ac83007e7942fe422793875c90f81fd6d647e5694ac96478c3e6326bc53d` |
| `ntdll.so` | `eef64f611ae9033261a70f46ec0be38d58823717f14e80331946c6d0cd3c85f7` |
| `manifest.json` | Records pinned hashes, staging declaration, exact changes, code-signing checks, and unchanged input. |

`ntdll.pre-sign.so` is a byte-review artifact containing the stale original embedded signature. “Unsigned” in historical manifest keys means these pre-sign bytes; the signature has not been stripped. It must not be loaded or deployed. The signed artifact preserves identifier `ntdll-55554944a111d5d496a533f9923073e9beb51434`.

The source correction patch is pinned to SHA-256 `88dd45f99c6438db828688239286192b1405c90f22d03ef5c54b62bb22c52458`. It selects current `Protect`, then maps the executable base to its corresponding non-executable base while preserving higher modifier bits. This produces three `info.Protect` references. In the exact binary, byte `0x66c6f` changes `20` to `34`; twelve bytes at `0x66c78` become `c0 e9 04` followed by nine `90` bytes (`SHR CL,4` plus NOPs). The total change before signing is 13 bytes, with no change in code extent. Signing changes 31 bytes within one CodeDirectory page-hash slot and nothing else.

The source-only check applies the pinned downstream patch and V2 correction to fresh source, without compiling or running Wine:

```sh
python3 check_source_patch.py \
  --pristine-source "/absolute/path/to/offline-source/ntdll-virtual-wine11.c" \
  --overlay-patch "$PWD/vendor/0001-ntdll-CW-HACK-18947.patch" \
  --patch "$PWD/0001-ntdll-use-current-protection-for-rosetta-toggle.patch" \
  --output-directory "/absolute/path/to/new-source-check"
```

The full corrected `virtual.c` hash is `ee3feb8b45f94076f3502e79d0e2fa5112214a1adc2b7110c47b8397eb72b8df`. The extracted helper hash is separately recorded in `SOURCE-PROVENANCE.json`. Both patches apply with zero fuzz, and the correction reverse dry-run passed.

Validation: 39 focused builder tests passed, including wrong calculation opcode/immediate, wrong offset, complete hash pins, valid but unreviewed signature rejection, copied-input requirements, declared-root constraints, symlink/hardlink/special-file cases, and failure cleanup. Two fresh builds from the copied original produced byte-identical pre-sign and signed files. Independent metadata analysis confirms unchanged load commands, relocations, function boundaries, branch targets, and compact unwind data. These are offline source and artifact checks; they do not establish runtime compatibility, gameplay behavior, or retrospective crash causality.

The protection helper still ignores both `NtProtectVirtualMemory` statuses. Separate remote calls can interleave, and the first call's target-side failure can leave `old_prot = PAGE_NOACCESS` before the unchecked second call. The correction does not cover cross-region or lifetime races. Execute-only pages still map to `PAGE_NOACCESS`. In `force_exec_prot` mode Wine may add host execute permission to the readable temporary protection, so equivalent Rosetta invalidation in that broader mode is unverified. These limits require separate review and are not a reason to run or install this artifact automatically.
