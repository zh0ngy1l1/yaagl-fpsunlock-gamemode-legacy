# Current-page protection candidate, revision 2

This isolated, target-independent candidate removes an unnecessary protection
cycle from the recorded Genshin FPS data-page write path. It is not proof of
historical crash causation, a generic Wine/Rosetta fix, or accepted production
software. Nothing has been installed, loaded, launched or merged into the
protected frontend.

## Original defect and rejected first candidate

Downstream CW HACK 18947 adds `toggle_executable_pages_for_rosetta()` after
`NtWriteVirtualMemory`. It attempts to invalidate stale Rosetta code following
cross-process Mach writes by changing execution protection in the target.
It uses allocation-wide `AllocationProtect`, clears the executable nibble and
substitutes `PAGE_NOACCESS` if the result is zero. Two separate protection calls
apply and restore that value; their failures do not replace the write result.

Matching Wine allocates the PE image with broad executable/write-copy metadata,
then applies section-specific current protections. The writable data section
can legitimately have allocation protection `0x80` and current protection `0x08`,
as archived queries report. Allocation metadata is not proof of executable code.

Revision 1 changed only the field. Independent review falsified its calculation:
allocation `0x80`, current `0x180` (executable write-copy with guard) produced
modifier-only `0x100`, which matching Wine rejects. Target APC failure writes
`PAGE_NOACCESS` into the old-protection result; unchecked restoration can then
leave the page inaccessible. Actual helper and matching protection-validation
fixtures reproduce this source-reachable regression. Revision 1 signed artifact
`702394b6…` is preserved as evidence and is **not a deployment input**.

## Revision 2

```c
if (info.Protect & 0xf0)
{
    ULONG noexec = (info.Protect & ~0xff) | ((info.Protect & 0xf0) >> 4);
    /* Existing protection and restoration calls follow. */
}
```

Current non-executable data pages receive no protection calls. Executable base
protections map to their non-executable equivalents: execute-only to no-access,
execute/read to read-only, execute/read/write to read/write, and execute/write-copy
to write-copy. High modifier bits remain intact. This removes execution while
preserving readable access where present and avoids modifier-only protection.
Executable handling is retained. Existing failure/restoration handling remains
a separate limitation; this correction does not redesign that contract.

The helper never examines the payload. Every integer 61–360 follows this path,
including later writes after game resets. No delay, extra 60 read, foreground
predicate, manual arming or target special case is added.

## Exact source and binary correspondence

The base is Wine 11.0; CW HACK 18947 is a downstream addition, present with
identical helper additions in the pinned January and release-era overlays.
`SOURCE-PROVENANCE.json` pins those sources and the archive matching the published
release. Exact disassembly verifies this relevant path; a reproducible build of
the entire Wine distribution has not been established.

The x64 MBI is 48 bytes: `AllocationProtect` at offset 16, `Protect` at offset 36.
The query buffer is at `rbp-0xf0`. At VA `0x66c6d`, the original load
`8b 8d 20 ff ff ff` feeds both classification and calculation. Replacing it with
`8b 8d 34 ff ff ff` selects current protection. At VA `0x66c78`, the 12-byte
legacy calculation becomes `c0 e9 04` (`shr cl,4`) plus nine NOPs. That byte shift
preserves ECX's upper 24 bits and implements the formula exactly.

The builder resolves both VAs through `__TEXT,__text`; file offsets happen to
equal the VAs in this image. Thirteen code bytes change: one at `0x66c6f`, twelve
at `0x66c78–0x66c83`. Function extent, branches, relocation and unwind data remain
unchanged. Signing changes 31 further bytes within the existing signature payload;
header and load-command bytes remain identical. All artifacts are 620,688 bytes.

| Artifact | SHA-256 |
|---|---|
| Exact original | `f26ade35f5b49e33b3780b6adc71f9eb9c831ea40222c1bae667ac14135d984b` |
| Revision 2 pre-sign | `9cc5ac83007e7942fe422793875c90f81fd6d647e5694ac96478c3e6326bc53d` |
| Revision 2 signed | `eef64f611ae9033261a70f46ec0be38d58823717f14e80331946c6d0cd3c85f7` |

Pre-sign means the unsigned candidate still contains its stale original embedded
signature. Only the final signed artifact is a deployment input. The builder
requires copied input within a declared offline staging root, pins both output
hashes and checks the strict signature. See [BUILD.md](BUILD.md). Never supply an
installed Wine path to the builder.

## Semantic scope and residual risks

Current protection is the correct logical classifier for this native Win64 data
page. Rosetta W^X handling preserves Wine's logical execute bit; physical NX alone
does not contradict the classifier. A later logical RW→RX transition invokes
in-target `mprotect`, supporting deferred invalidation of formerly executable
pages. Public Apple material does not establish the complete cache contract.

A concrete exception is Wine's `force_exec_prot` mode: logically readable NX pages
can become host-executable. Revision 2 can skip them; its readable temporary
protections can also regain host execution, defeating a toggle. Matching native
Win64 code rejects enabling this mode, and the exact AMD64/NX-compatible Genshin
image is outside the known counterexample. The runtime still serves other callers.
This is a bounded compatibility risk, not an all-caller or WoW64-certified fix.

Ignored protection/restoration failures, mixed-page writes, other mapping actors,
Mach fallback failure paths and resolver/lifetime robustness remain outside the
correction. The aligned four-byte field does not span pages. Both historical
read faults hit page `0x1452b4000`: the FPS integer and unrelated CanvasRenderer
bounds. The mechanism can explain both; actual crash-time interleaving remains
unproved. Native shutdown SIGILL is separate. Recovery `a2f6568` stays excluded.

## Product and acceptance

The product retains frontend `a0e8c704`, ordinary v3.0.7 companion `8543f45a…`,
the existing per-game prefix, default 120, maximum 360, saved settings, disabled
and enabled ≤60 behavior, exact targets, DXMT policy, automatic attachment,
read/compare/write, resets, ownership, Wine waits and cleanup. Inherited waits
remain; none is claimed as a safe-start rule. Requested target, successful write
and rendered throughput remain separate facts.

[Verification](TESTING.md) exercises extracted helpers, matching protection
validation, release read/compare/write code, archive replay and builder rejection.
Native mocks do not execute Wine or Rosetta. Ordinary-production acceptance uses
existing companion output, passive native focus events and continuous video.
It preserves product bytes and startup rules, with weaker write completeness than
d23 and declared observation load; d23 is not substituted.

See [composition](../../acceptance/COMPOSITION.md),
[observation](../../acceptance/production-observation/DESIGN.md),
[deployment](../../acceptance/DEPLOYMENT.md), and the prepared
[90/120/150/180 protocol](../../acceptance/SUITE.md). These plans are unexecuted.
Offline evidence supports controlled review, not universal production reliability.
