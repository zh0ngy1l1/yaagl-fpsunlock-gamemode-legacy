The current `run_offline.py` entrypoint runs the V2 source-helper and protection-validation tests. The V1 extractor and historical write replay are retained as import-only `legacy_trace_replay.py`; their function bodies are unchanged. The excluded V1 patch is kept under `vendor/0001-ntdll-current-protection-v1-excluded.patch` solely for the regression comparison.

V2 selects the queried current `Protect` field and computes:

```c
noexec = (info.Protect & ~0xff) | ((info.Protect & 0xf0) >> 4);
```

Its logical temporary protection maps EXECUTE→NOACCESS, EXECUTE_READ→READONLY, EXECUTE_READWRITE→READWRITE, and EXECUTE_WRITECOPY→WRITECOPY while retaining modifier bits. It intentionally changes temporary protection even when current and allocation executable protections agree. It does not claim that the old executable-page behavior is unchanged.

The runner hash-checks the pristine Wine 11.0 `virtual.c`, the pinned downstream overlay and both correction patches. It applies the actual V2 correction with exact hunk context and verifies the resulting helper SHA-256. The source patch hash is `88dd45f99c6438db828688239286192b1405c90f22d03ef5c54b62bb22c52458`; the exact compiled helper body, ending with one newline, is `dbbf5388d1ec2f918055119a79e56e72e5c0da2d7b798e79d98a8cfe3e161926`. The full `virtual.c` after overlay and V2 correction has a different scope and hash, `ee3feb8b45f94076f3502e79d0e2fa5112214a1adc2b7110c47b8397eb72b8df`.

Run from this package directory with native host Python and clang. Supply the existing read-only evidence and a fresh output directory with an existing parent. Run without Python optimization, since the archived replay includes assertions.

```sh
FPS_EVIDENCE_ROOT="$HOME/Library/Application Support/YAAGL Local Builds/genshin-fps360-20260909"
python3 -B run_offline.py \
  --wine-source "$FPS_EVIDENCE_ROOT/universal-automatic-implementation/runtime/ntdll-virtual-wine11.c" \
  --comparison "$FPS_EVIDENCE_ROOT/automatic160-crash-analysis/revalidation-20260910/companion-review/RUN-TRACE-COMPARISON.json" \
  --managed-results "$FPS_EVIDENCE_ROOT/universal-automatic-deployment-review/verification-audit/RESULTS-FINAL.json" \
  --output "$FPS_EVIDENCE_ROOT/universal-automatic-deployment-review/new-v2-offline-results"
```

`--candidate`, `--correction` and `--v1-correction` default to this package and its pinned patches. The managed result is explicitly reused: its release source files are rehashed, and the result path/hash and original counts appear in V2 output. Reuse does not claim another managed execution. That earlier host .NET fixture compiled unchanged release `ApplyFpsLimit` and span memory wrappers from commit `56b9c64381ef9fd59e916dc9bf547d3210ab5db1` with managed native-API mocks. It covered all 300 targets 61–360 with independently encoded exact bytes, all 60 primitive targets 1–60, nine failed/short-read combinations, ten write-result combinations, 300 equal/no-write cases, 300 game-reset reapplications and three foreground/power-save cases. Removing the equality, complete-read or complete-write guard failed the corresponding assertion.

The V2 native fixture compiles the actual helper body and the exact Wine `get_vprot_flags` validator. It covers the 300 distinct targets, 64 allocation/current base-protection pairs, modifiers, three refreshed-query sequences, query failures, partial/failed server write results, and the two read addresses (`0x1452b4244`, four bytes; `0x1452b4ad8`, eight bytes). Native interfaces and the page byte array are mocks. The constructed read during a protection change is an intentional schedule, not recovered historical timing.

The API-validity fixture additionally compiles exact `get_win32_prot` and `VIRTUAL_Win32Flags`. Their conversion produces the source-supported allocation `0x80` / current `0x180` guarded-page mismatch. The original helper requests `1` then restores `0x180`. V1 requests invalid base-less `0x100`, receives `STATUS_INVALID_PAGE_PROTECTION`, and its unchecked second call leaves `PAGE_NOACCESS`. V2 requests valid `0x108` and restores `0x180`. This negative control remains in every V2 run. Twenty executable-base/modifier mappings pass the extracted base validator, with explicit expected bases. The remaining native protection operation, view restrictions, image copy-on-write normalization and OS effects are still mocked. Synthetic matrix combinations do not prove that every pair can be returned by the real query implementation. For example, NOCACHE comes from the mapping and ordinarily appears in both allocation and current protection; per-page GUARD gives the stronger V1 regression example.

Six compiled helper mutations are rejected: allocation-based predicate, skipped executable classification, V1 temporary mapping, dropped modifiers, all executable states collapsed to NOACCESS, and an incorrect shift. `test_v2_binary_mutations.py` separately tests the actual V2 builder's byte admission in memory against the original runtime. It rejects wrong load and calculation offsets, wrong field displacement, wrong shift count and wrong shift register. It creates no runtime copy, invokes no signer and loads no library.

```sh
python3 -B test_v2_binary_mutations.py \
  --builder ./build_runtime_delta.py \
  --input-runtime "$FPS_EVIDENCE_ROOT/universal-automatic-deployment-review/artifacts/input/ntdll.so" \
  --output /absolute/path/to/new-binary-mutations.json
```

The historical replay still verifies four trace hashes and supplies all ten recorded successful writes/page samples to the original and V2 helpers. Their original survival/crash and interval verdicts remain unchanged. Separate preserved checks validate all 3,181 recorded read operations and 7,420 query records for identity and ordering, including the failed automatic run's final incomplete read. Metadata consistency and write-input replay do not execute the diagnostic gates, reconstruct fault-time protection, or establish historical crash causality.

First-protection and restoration failures remain explicit negative results. A failed remote APC queue can leave `origprot` uninitialized; clang static analysis diagnoses its use at the second call without executing undefined behavior. A target protection failure can return old protection NOACCESS, causing the ignored failure/second call to leave the page inaccessible. A failed restoration after V2's valid non-executable temporary request can leave execution disabled. The corrected FPS data page receives no protection call and bypasses these paths. The tests do not certify general executable-page error handling.

The logical protection mapping is not a proof of host execute-bit transitions or Rosetta cache invalidation. In Wine's `force_exec_prot` compatibility mode, `mprotect_exec` can add host execution to readable logical protections. Thus V2's READONLY temporary state may remain host RX even when the original page was logically executable, yielding no actual execute-bit toggle. It can also skip logically non-executable pages that are host-executable in that mode. The known Genshin image is native AMD64/PE32+ and NX-compatible; the matching native Win64 path rejects enabling this execution-policy mode, as independently reviewed in `runtime-audit/SEMANTIC-AUDIT.md` and the installed `NtSetInformationProcess` disassembly. That bounds the intended Genshin use; it does not establish correctness for every writer/target using the same Wine installation. Actual Rosetta stale-cache behavior is untested.

Enabled low-target forwarding and disabled unlocking are separate frontend coverage. Preserved packaged tests show exact enabled 1/30/59/60 forwarding and 32 disabled cases with no companion; their artifact is pinned in `verification-audit/REUSED-FRONTEND-CHECKS.json`. Native scalar zero is not evidence of a disabled launch. Default 120, maximum 360, saved preferences, Wine/prefix selection, admission, close protections and observer behavior remain covered by their existing checks and separate source reviews.

These tests compile host fixtures under AddressSanitizer and UndefinedBehaviorSanitizer. They do not import or execute Wine, start a game, attach to a process, call native remote-memory APIs, alter the recovered installation, or activate a candidate. The implementation has no target-specific delay, manual-arm requirement, additional-60-read condition or 150 special case. Rendered FPS, whole-game startup reliability and general translation-cache behavior remain outside offline verification.
