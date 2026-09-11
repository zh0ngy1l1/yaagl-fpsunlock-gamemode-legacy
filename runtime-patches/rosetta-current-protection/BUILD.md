This package corrects the Rosetta page-toggle helper to use current page protection (`Protect`) for its decision and intermediate protection. It changes two source references and one machine-code operand in the exact installed x86_64 `ntdll.so`. The checked-in patch is supported by the pinned downstream source and matching disassembly; this package does not represent a full Wine source rebuild.

`SOURCE-PROVENANCE.json` pins the Wine 11.0 source, January downstream overlay, May release-era reinforcement, correction patch, application results and binary hashes. The helper additions in both downstream revisions are byte-identical. The executable-page selection follows current protection in both directions: a non-executable page is skipped even when its allocation protection was executable, and a currently executable page is processed even when its allocation protection was non-executable. The executable-page toggle mechanism remains present.

Use Python 3.9 or newer on macOS. The builder requires the exact input SHA-256 `f26ade35f5b49e33b3780b6adc71f9eb9c831ea40222c1bae667ac14135d984b`. Keep the correction patch beside `build_runtime_delta.py`. Supply an existing parent directory and a new output directory outside the input file's parent directory. The script reads and verifies the input, creates only the requested fresh output directory, patches a copy, ad-hoc signs it using the original identifier, verifies the signature and executable bytes, and records a manifest. It never installs or executes the runtime.

```sh
python3 -B build_runtime_delta.py \
  --input /absolute/path/to/original/ntdll.so \
  --output-directory /absolute/path/to/new-artifact-directory
```

The offline builder regression tests use the original Mach-O file without executing or changing it. They cover the real virtual-address/file-offset mapping, one-byte delta, rejection of wrong/already-patched bytes, malformed structures, output overlap and existing destinations, signer corruption, and cleanup after a failed build.

```sh
python3 -B test_build_runtime_delta.py \
  --input /absolute/path/to/original/ntdll.so \
  --result-json /absolute/path/to/new-test-results.json
```

The portable source check accepts external pinned inputs. Download or reuse the exact source and overlay identified in `SOURCE-PROVENANCE.json`; it verifies their SHA-256 values before applying them. Supply a fresh output directory outside all three input parent directories. It uses zero-fuzz patch application, verifies the intermediate and corrected source hashes, checks both corrected field references, and confirms all input bytes remain unchanged.

```sh
python3 -B check_source_patch.py \
  --pristine-source /absolute/source-dir/virtual.c \
  --overlay-patch /absolute/overlay-dir/0001-ntdll-CW-HACK-18947.patch \
  --patch /absolute/package-dir/0001-ntdll-use-current-protection-for-rosetta-toggle.patch \
  --output-directory /absolute/separate-artifact-dir/new-source-check
```

Completed local validation: 17 builder regression tests passed; the portable source check passed; the signed artifact passed strict code-signature verification while retaining its original ad-hoc identifier; signing preserved every file-backed Mach-O section. The unsigned artifact differs from the input only at file offset `0x66c6f`, byte `20` to `34`. The signed artifact additionally changes 31 bytes within its existing code-signature payload.

The prepared artifact SHA-256 is `702394b643e83a4e2cd55fb0e013a4bcff6e20db01265246cce234eebda08f3d`; its unsigned precursor is `a7da31b9ac6f65b905d76b0d4cd5b7f0fb578337ebb5f8601c99018ec7a84bf7`. Its manifest records all changed ranges, signing results, and unchanged input metadata. It remains isolated and has not been loaded. These offline checks establish the supported field-selection correction; they do not establish retrospective crash causality or gameplay behavior.
