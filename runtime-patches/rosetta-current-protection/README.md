# Current-page protection correction for the selected Genshin Wine runtime

This isolated candidate corrects a concrete error in the installed Wine build's
Rosetta executable-code invalidation workaround. It is a proposed crash correction,
not a claim that the historical crashes' exact interleaving has been established.
No target values, launch preferences, companion operations, renderer settings or
launcher ownership/cleanup behavior are changed.

## Mechanism

The downstream `toggle_executable_pages_for_rosetta()` helper runs after
`NtWriteVirtualMemory`. It queries the target process and tests
`MEMORY_BASIC_INFORMATION.AllocationProtect` for executable permissions. That field
describes the allocation's initial protection, not the written page's current
protection. In the failing archive, 530 successful queries report allocation
protection `0x80` (`PAGE_EXECUTE_WRITECOPY`) and current protection `0x08`
(`PAGE_WRITECOPY`) on the game data region beginning at `0x1452b4000`.

The workaround treats `0x80` as executable, clears `0xf0`, substitutes
`PAGE_NOACCESS` for zero, calls `NtProtectVirtualMemory`, and calls it again to
restore the prior protection. These are separate target-process operations. It
does not return their status to the caller: the original write status and byte
count are retained. A successful four-byte API result therefore does not establish
that the write caused no page-protection side effects.

Both observed read faults concern this page: one reads the FPS integer at
`0x1452b4244`; the other reads unrelated CanvasRenderer positive-infinity bounds
at `0x1452b4ad8`. This is a concrete mechanism consistent with both faults and
with intermittent survival. No captured fault-time page protections or scheduler
trace establish that this mechanism caused either historical exception.

The correction uses current `Protect` in both places. A current non-executable
data page now receives no protection toggle. The executable-page invalidation mechanism remains, with current protection
determining eligibility. When allocation and current protection agree, its
behavior is unchanged; when they differ, current protection now governs. This is independent of the four-byte value
being written, including every requested integer from 61 through 360.

## Exact source and binary correspondence

The helper is from
[CW HACK 18947 at the Wine 11.0 overlay commit](https://github.com/riverfog7/macports-wine/blob/0bf32337c0c2d2a699fc392f5db570cf42ca0f27/emulators/wine-devel/files/0001-ntdll-CW-HACK-18947.patch).
Its added helper is also unchanged in the
[release-era overlay](https://github.com/riverfog7/macports-wine/blob/098941d867f8793f559035e298ceb69a8e69f1f3/emulators/wine-devel/files/0001-ntdll-CW-HACK-18947.diff).
Upstream Wine 11.0 alone does not contain this addition.

The installed `ntdll.so` SHA-256 is
`f26ade35f5b49e33b3780b6adc71f9eb9c831ea40222c1bae667ac14135d984b`.
Its `NtWriteVirtualMemory` implementation at `0x66ac0` matches the added logic:
the query buffer is at `rbp-0xf0`, and the instruction at `0x66c6d` loads
`[rbp-0xe0]`, offset 16 (`AllocationProtect`). The corrected operand loads
`[rbp-0xcc]`, offset 36 (`Protect`). One instruction feeds both the executable
test and the protection calculation, so changing that displacement implements
both source edits.

The installed Wine archive SHA-256 is
`4ebba536115e937c3826fa5808dbed50cd5e91c8454999b54cbe0cd2a43d8b4c`,
matching the published `wine-devel-11.0-osx64-signed.tar.xz` release asset.
This establishes exact artifact identity and matching relevant source, not a
reproducible build of the entire downstream Wine distribution.

The build tool produces a strictly hash-pinned, statically patched and ad hoc
signed copy. It does not compile all of Wine, load the library, execute Wine,
change an installed file, or install the result. Input identity, instruction
context, Mach-O mapping, changed code bytes, output identity and signature are
checked separately. Unsupported or already patched input is rejected.

## Universal automatic behavior

The product composition retains protected frontend `a0e8c704` and the existing
ordinary release companion v3.0.7 (`8543f45a...`). The latter already accepts
the launcher's numeric argument without a diagnostic sidecar, manual arming,
hotkey or Terminal command. The diagnostic `d23d2779` companion remains a
separate observation profile; its first-full-60/foreground predicate is not a
safety condition and is not required by this correction.

The launcher retains default 120, maximum 360, exact per-integer forwarding,
saved preferences, disabled-unlocker behavior, and enabled targets at or below
60. Enabled DXMT unlocking above 60 retains game renderer rate 0 and the
requested target for the companion. Rendered FPS remains subject to game scene,
renderer, display and hardware throughput; a requested cap is not guaranteed
performance.

Attachment, address resolution, the complete four-byte read/compare/write loop,
subsequent configuration updates, and rewrites after a game reset remain as
implemented. Equal reads skip writes. Failed or short reads cannot authorize a
write. The bound process lifetime, cancellation, per-game Wine/prefix selection,
Wine waits and cleanup remain unchanged. The runtime correction applies to each
actual write, so it does not require predicting world readiness or limiting the
number of resets. No 120/150/160 aliases or timing heuristics are introduced.

## Verification and limits

The focused native fixture extracts the actual downstream helper, mocks its
native interfaces, and compares the original and corrected code. It constructs
a read interleaving during the legacy no-access pulse at both recorded addresses,
checks exact payloads for all 61–360 values, tests non-executable and executable
page classes, and replays recorded writes with their archived query metadata.
This is mechanism evidence, not execution of the game or of Wine under Rosetta.
The existing packaged target/ownership/wait and repaired observer checks remain
separate regression evidence; serialization checks do not prove crash reliability.

The following remain outside this narrow correction: executable-page toggle
failure/restoration handling, writes spanning regions, general Mach write
fallback behavior, resolver hardening, and the native launcher shutdown SIGILL.
The correction removes the demonstrated data-page misclassification. It does
not establish continuous accessibility if the game or another actor changes a
mapping, and it does not claim immunity from unrelated crashes.

No activation, installation, merge, gameplay acceptance or live Wine experiment
is part of this preparation. Recovery `a2f6568` remains excluded. The
90/120/150/180 acceptance suite stays pending candidate review and explicit
authorization for deployment and gameplay. A future controlled acceptance must
record the corrected runtime hash as well as frontend, companion, game and
configuration identities, preserve all original assessment verdicts, and stop
on a crash rather than repeat an unchanged candidate to seek success.

The existing observer's journal/receipt checks require the d23 observation
companion. The ordinary release companion does not emit that journal. An
instrumented d23 acceptance run must retain that identity and its different
startup gate in its conclusions; it cannot stand in for exact production
startup acceptance. Production-matching observation coverage remains a review
item before gameplay authorization.

The built 620,688-byte signed delta hashes to
`702394b643e83a4e2cd55fb0e013a4bcff6e20db01265246cce234eebda08f3d`.
The unsigned code change hashes to
`a7da31b9ac6f65b905d76b0d4cd5b7f0fb578337ebb5f8601c99018ec7a84bf7`.
Signing changes only the existing signature's page hash bytes. The output is
staged separately; the installed input still has its original hash.

See [TESTING.md](TESTING.md) for the source-extracted regression and recorded
trace replay. The helper fixture is a native host test with mocked interfaces;
it does not execute the corrected Wine library.
