# Ordinary-product acceptance observation

This package closes a specific mismatch: the repaired diagnostic observer's
journal controls require a companion whose startup eligibility differs from the
ordinary v3.0.7 product. The new profile uses the ordinary companion's existing
stdout, a passive native collector and continuous video. It introduces no product
algorithm, launch gate, sidecar, extra read, manual arm or gameplay shortcut.

Only native compilation, pure-model tests, temporary-file tests and archived-log
replay have been executed. No observer has attached to a real game/application,
no capture has started, and no Wine/game/candidate has executed in this review.

## Facts and attribution

| Evidence | Exact fact available | Product code/environment change | Attachment eligibility / first write / polling / focus |
|---|---|---|---|
| Existing ordinary companion stdout, copied before and after | Shell target/Wine/prefix and companion target, resolved address, HWND and Windows PID at attachment, successful complete four-byte write branch and its old/new values | None; the ordinary product already emits these lines | No change to any of these; post-run parsing adds no hot-path work |
| PassiveForeground host collector | A selected native Wine executable/PID/birth identity became foreground, unique final departure and termination; callback/heartbeat integrity | Separate host process only; product bytes and environment unchanged | No direct change; one-second **observer** snapshots do not change companion polling; scheduling perturbation remains possible |
| Continuous screen recording | Visible launch/login/world, scene continuity, measured media interval, readable HUD values, final game close/Ready/launcher quit | Separate recorder; product bytes and environment unchanged | No direct change; CPU/GPU/I/O load can affect scheduling and achieved FPS |
| External camera, if supplied | Same visible facts without host recording load | None on host | No host effect, but requires readable continuous footage and valid timing |

The chosen evidence supports ordinary production startup under declared passive
observation load. It cannot prove zero timing perturbation or unobserved
reliability. A native PID is **not** a Windows PID mapping. Single-session release
logs, a single native selected-Wine host, game identity and continuous footage
provide corroboration; ambiguous concurrent hosts stop acceptance.

Do not substitute d23, an instrumented companion, remote-memory polling, runtime
hooks or a reintroduced first-60/foreground rule to strengthen this profile.

## Source-supported write proof

Pinned ordinary source is commit `56b9c64381ef9fd59e916dc9bf547d3210ab5db1`;
ordinary executable SHA-256 is
`8543f45a4edced854ab8c5466ce2dc2e511fb4f89361bc4dfb474b68d998cc17`.
The archived source path and file hash are in `fixtures/PROVENANCE.json`.

`GameInstanceService.cs:184–194` logs `Find the game window` with HWND, class,
Windows PID and game name, followed by `Start applying FPS`. Lines 348–351
require a successful full four-byte read; lines 353–354 return on equality;
lines 356–360 construct the integer bytes and log `FPS Override: old -> target`
only after `WriteProcessMemory` succeeds and reports the whole payload length.
The parser therefore labels a matching line **source-supported complete-write
evidence**, not a sealed per-operation receipt. Failed/short operations have no
equivalent log; missing output is inconclusive. Wall-clock log timestamps are
not native-call boundaries. API success does not establish absence of side effects.

`production_evidence.py snapshot` opens the actual log with `O_NOFOLLOW`, records
device/inode/size/mtime/ctime/hash, checks that it stayed stable during the copy,
and writes an exclusive staging snapshot. `log` requires an unchanged old byte
prefix and inode, exactly one new shell/headless/attachment/apply session, exact
Wine/prefix/target/companion-renderer values and the pinned game address. It rejects
diagnostic output, duplicate sessions, ambiguous attachments, malformed/incorrect
writes, writes before attach or after stop, equality writes and truncation.

`fixtures/archived-release-session-150.log` is an exact 3,277-byte slice from an
existing archive, SHA-256
`89863f6c33ff3e1ccc528628e56d1e23151b49a19bec8daff6c3a1d2d827ab1e`.
Its four write messages and attachment PID are replay inputs only. It lacks a
normal-exit log tail and **is not promoted to full acceptance**. The provenance
records exact archive hash and byte range; the replay result records its limits.

## Native observation and its limits

`PassiveForeground.swift` reuses the repaired observer's NSWorkspace and
prohibited-AppKit approach, without its Carbon hotkeys, preflight subprocesses,
journal checks or Wine commands. It records sequenced monotonic/UTC events,
selected executable, native PID and full-precision `NSRunningApplication.launchDate`
value, activation, deactivation, termination, one-second heartbeat snapshots and
a synchronized footer. A missing birth identity, selected host already present,
multiple selected native hosts, PID reuse, observer activation, return after
departure, clock reversal, heartbeat gap over three seconds, snapshot/callback
disagreement or incomplete footer blocks acceptance.

The selected native executable observed in the earlier archives is:
`/Users/david/Library/Application Support/Yaagl OS/hoyoplay-wines/genshin/11.0-dxmt-signed-with-patches/wine/lib/wine/x86_64-unix/wine`.
The future manifest must confirm that path against the reviewed runtime.

The post-run `native` checker independently checks raw ordering, sequence,
heartbeat coverage, one activation/final departure/termination, selected path,
birth identity and every event's foreground snapshot. It rejects a delivered
other-app activation within the selected span even if the next heartbeat sees
the game again. It does not merely trust the footer or heartbeat samples.
NSWorkspace does not provide a lossless event-delivery certificate. A brief focus
excursion with all its callbacks lost between heartbeat samples is not ruled out
by native evidence alone. Continuous video is the independent control. Do not
rename "no detected loss" to "all native focus events guaranteed captured."

Normal game close can produce a deactivation callback just before termination.
One final departure is therefore retained and permitted; reactivation is not.
The reviewer must see the unique final game close corresponding to that departure
after the gameplay interval. Any ambiguous earlier loss, visible switch, return,
second host or uncertain correspondence makes the run inconclusive and stops
progression. This is an observation decision, never launch/write eligibility.

## Future operator interface — prepared, not executed

The later authorized operator/controller performs these staging steps; the user
has no Terminal or hotkey step:

1. Freeze the product identities/settings/environment using the acceptance
   manifest. Confirm ordinary companion hash and absence of diagnostic sidecars.
   Confirm no selected game/companion is already running. Snapshot the log.
2. Start the native collector before ordinary game launch. Its future argv is
   `PassiveForeground --observe EVENTS_JSONL EXACT_NATIVE_WINE_EXECUTABLE 1800 STOP_FILE`.
   Both output and stop request must be fresh staging paths. Require a `ready`
   record and no failure before allowing the user to open the game normally.
   It does not start or signal the launcher/game. The bound duration is only an
   observer safety bound, not a startup delay or arming condition.
3. Start a continuous noninteractive recording on the selected display before
   game launch. The local `/usr/share/man/man1/screencapture.1` documents `-v`,
   `-V seconds`, `-D display` and `-x`. Prepared argv is
   `[/usr/sbin/screencapture, -v, -V, 1800, -D, 1, -x, MOVIE_PATH]`.
   No microphone, interactive selection or app-opening option is used. Recording
   permission and readable output must be demonstrated **before** game launch.
   Process existence alone is not proof that recording started. Display 1 is a
   placeholder to be fixed in the frozen run manifest, not assumed universally.
4. The user launches and plays normally. No observer action affects the write.
   Do not react to a missing write line by restarting, delaying or arming anything.
5. After normal game exit, Ready and normal launcher quit, the controller may
   exclusively create the retained stop-request file containing exactly `stop\n`.
   This closes only the host observer with a footer. Otherwise its observation
   bound closes it. An unexpected observer death has no valid footer. Finish
   and preserve the recording, then snapshot the release log. Capture-specific
   stopping must preserve a finalized playable movie; it never signals Wine.
6. Run the post-run log and native checkers on immutable staging snapshots and
   retain their JSON, source/tool hashes and all failures. The full suite protocol
   separately verifies identities, Wine wait, cleanup and deterministic restoration.

No new permission prompt may be answered during the measured run. If capture
cannot be prepared without a prompt or readable evidence cannot be established,
stop before launching. This review has not exercised the native notification or
capture backend; their future preparation controls remain required.

## Video and full-acceptance review

Preserve the original media, SHA-256, size, duration, track/sample timestamps,
decode errors and timestamp-gap analysis. Review uninterrupted footage from game
appearance through its final close. Select the first settled playable-world
interval of at least 125 seconds before that close; record exact media timestamps
and readable HUD samples with their sampling method, minimum/median/maximum.
Distinguish requested target and successful write target from displayed/rendered
FPS. A requested cap is not guaranteed achieved FPS.

Require the selected interval to fit inside the unique native foreground span
and the footage's single uninterrupted visible game session. Do not invent a
precise recorder/native clock alignment from process launch timestamps. Categorical
containment and visible final-close correspondence are required. If multiple
transitions or timing ambiguity prevent that correspondence, stop as inconclusive.
Never bridge capture gaps or combine segments across lost focus.

The log/native checkers intentionally do not output "full acceptance." A separate
human review of media, game/world/lifecycle, unchanged product identities, wait,
cleanup and restoration is mandatory. This profile has weaker native-call timing
and failed-operation completeness than d23, while testing the intended ordinary
product startup algorithm. That is the declared evidentiary compromise.

## Focused offline verification

`verify_offline.py` compiles the native source and executes **only** its pure
`--self-test` branch, then runs Python temporary-file/mock/archived-input tests.
There is no observation or capture invocation in that verifier.

| Assumption/control | Check |
|---|---|
| Native observer does not need a live product | Swift `--self-test` exercises the pure reducer without AppKit initialization |
| Binding includes creation identity and rejects reuse | Swift missing-date/PID-reuse cases; Python birth-identity checks |
| Normal terminal departure is distinguishable from resumed play | Swift terminal-departure/return cases; Python raw activation/departure/exit ordering |
| Detected callback loss, stall or self-focus cannot pass | Swift snapshot/activation/gap/reversal/self-focus cases; Python forged-footer negative cases |
| Brief recorded focus loss cannot hide between heartbeats | Swift other-app activation and non-heartbeat snapshot cases; Python matching negatives, including contradictory other-app activation/game snapshot |
| Journal sequence/footer cannot silently be incomplete | Python missing-footer/sequence/backward-clock/heartbeat tests |
| Old or ambiguous logs cannot be counted as fresh writes | Inode, unchanged-prefix, empty-delta, duplicate-session, partial-line and second-attachment negatives |
| Exact selected target reaches logged write branch | 300 distinct target log fixtures, plus enabled 1/30/59/60 cases; **not crash-reliability tests** |
| Disabled behavior must not gain a false write claim | Empty disabled companion delta is rejected for write proof; full disabled testing remains in existing frontend checks |
| Existing production format actually parses | Pinned archived release log slice with source/PID/address/write evidence |
| Footage proves gameplay/HUD and native containment | Future media review, explicitly unperformed and not replaced by parser success |

The strongest remaining observation limitation is that there is no lossless,
zero-overhead external proof of every production memory operation or focus event.
The selected standard is sufficient to observe the ordinary product transparently
under declared recording load, with conservative ambiguity rejection; it cannot
match the diagnostic journal's per-operation detail without changing the product.
