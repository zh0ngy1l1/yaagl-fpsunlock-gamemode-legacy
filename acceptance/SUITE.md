# Prepared acceptance protocol — no runs authorized or executed

The initial order is **90, 120, 150, 180**. There is no preliminary160 retry.
Use the ordinary release companion and the passive production-observation
profile described in `production-observation/DESIGN.md`. The d23 diagnostic
companion, sidecar, gate and receipt protocol are not production acceptance inputs.
No gameplay hotkey, manual FPS arm or user Terminal interaction is required.

## Before each target

Require explicit gameplay authorization in addition to the separately authorized
controlled deployment. Begin from a verified recovered baseline and deploy the
same reviewed runtime delta using `DEPLOYMENT.md`, preserving an independent
rollback copy. No binary is rebuilt between targets.

For each T, create a fresh acceptance record with a unique ID. Record the exact
signed runtime hash `eef64f611ae9033261a70f46ec0be38d58823717f14e80331946c6d0cd3c85f7`,
frontend `a0e8c704`/resource`4724889a…`, ordinary companion`8543f45a…`, exact
game`a1a23cb7…`, resolved prefix identity, native process inventory and full
component manifests. Require no competing game/companion and no diagnostic
sidecar. Record the original saved preference baseline before the suite.

Set target T through the existing validated preference path, enabled=true,
renderer DXMT, in-game60 and the established power-save=false configuration.
Record actual values; do not substitute, clamp or alias T. Expected game
`d3d11.preferredMaxFrameRate=0`; expected companion DXMT T and numeric argument T.
Record file/environment precedence and any active `dxmt.conf`/`fps_config.json`.
Unexpected active configuration must be reviewed before launch.

Snapshot relevant logs before the run with bytes, hashes, inode and lengths.
Start the declared passive native observer and continuous recording before game
launch. Verify recording permission and output readiness before play; do not
answer permission prompts during a measured run. Record observer/recorder binary
identities, arguments, selected display, clock domains and output locations.
Observer startup does not arm the companion or change product environment.

## During the run

1. Open the protected launcher and start the game normally. No additional
   diagnostic launch command, Wine probe, memory read or target-specific step.
2. Retain normal launcher/game/companion output. The new log session must show
   exact T, selected Wine/prefix, automatic game-window discovery, address
   resolution and a matching successful full-write branch. The source-supported
   `FPS Override: old -> T` record proves a complete API-success write path;
   it is not a d23 receipt or proof of continuous memory accessibility.
3. Log in and enter the world normally. Do not infer world entry from a60 read,
   focus event, target write or elapsed startup time. Preserve visible evidence
   of login/world entry and the user's explicit observations.
4. Keep the same game foreground with HUD visible for a settled playable interval
   of at least125 seconds. The video review uses the first qualifying interval
   after settled world entry; it does not cherry-pick around a failure. No start
   or end hotkey. Require native foreground containment, readable continuous
   recording and a declared media timestamp/coverage analysis. Do not sum across
   focus losses or substitute companion readback duration.
5. Record requested T, logged write T and achieved displayed HUD metrics as three
   separate facts. Preserve raw frames and timestamps. Report displayed minimum,
   median/typical and maximum using a predeclared one-second sampling grid over
   the accepted interval, together with plateaus/drops and user observations.
   Do not infer achieved FPS from T. Recording load is an explicit measurement
   condition; a high request does not guarantee hardware can render that rate.
6. Retain later override lines. A changed old value followed by T is evidence of
   another complete successful write; it does not identify the reset actor.
   Record unexpected targets, attachment changes, retries or write discrepancies.
7. Quit the game normally, wait for YAAGL Ready, then quit YAAGL normally. Keep
   observation through the final close. Correlate native termination with normal
   game close rather than treating a last deactivation alone as a crash. Record
   Wine waiting and cleanup results from their own command records.

## Collection and restoration

Collect fresh production logs, runtime/frontend/companion/game/configuration
identities, native observer events/footer, original media and metadata, user
observations, new dumps/error reports, Wine-wait result and cleanup evidence.
Verify preexisting log prefixes and session scope. Record observer sequence
continuity, heartbeat/capture gaps, failures and missing footer explicitly.
Do not invoke the old journal checker and relabel missing release journals as
missing activation; this profile has its own declared evidence standard.

Apply the deterministic restoration procedure after collection. Verify the
original runtime hash/signature, unchanged frontend and companion, intended
saved settings, prefix identity, patch cleanup and protected verification.
Return the explicitly changed target preference to the pre-suite saved baseline
between trials. Seal the complete result before considering the next target.

## Predeclared classifications

| Classification | Required evidence |
|---|---|
| Target-path success | Exact requested T in saved preference, generated numeric argument, effective companion configuration, expected game/companion renderer split; all identities match |
| Automatic-unlock success | Target-path success plus ordinary automatic attachment/resolution and a source-supported successful complete write to T in the single new session; no manual gate or algorithm substitution |
| Runtime-stability success | Automatic-unlock success, visible world entry and qualifying interval, no observed crash/hang/new game dump, normal game exit and relevant clean lifecycle evidence for this execution |
| Rendered-FPS observation | Raw HUD/video samples and declared sample interval/statistics; requested and achieved values kept distinct, hardware/recording conditions stated |
| Full acceptance success | All preceding required controls, normal Ready/launcher close, successful Wine wait, cleanup, observer integrity, collection and verified restoration; no unresolved control failure |
| Inconclusive | Required observation unavailable or ambiguous: missing/ambiguous log session, absent write log, unknown world/HUD interval, clock containment failure, unreadable/gapped recording or observer integrity failure; do not infer candidate success |
| Candidate failure | Crash/hang attributable to this execution, unexpected runtime/component identity, target/write-path discrepancy, or failed required product lifecycle control. Historical causality may still be unknown. Observation/restoration failures are separately labeled operational failures and also prevent acceptance |

Any crash, failed required control, unexpected identity, write-path discrepancy,
observer integrity failure or restoration failure stops progression to subsequent
targets until analyzed. Preserve the failed or inconclusive result; do not repeat
an unchanged target to obtain a pass. Native shutdown SIGILL is classified
separately from the game crash mechanism and can still prevent full lifecycle
acceptance. No failure is silently downgraded because the runtime patch looks
promising. A source/tooling correction needs review and fresh authorization
before resuming the suite.

## After the initial four targets pass

The following is a proposed follow-up matrix, not authorization or a requirement
to test all300 values. Keep the same product composition and controls.

| Values | Purpose |
|---|---|
| 61, 62 | Lower unlocked boundary and adjacent value; exact forwarding and above60 renderer split |
| 119, 121 | Neighbors of default120; challenge hidden default mapping |
| 159, 160, 161 | Neighbors of the historical160 value; show the same implementation path, without claiming intrinsic safety at160 |
| 240, 300 | Higher representative requests under increasing hardware/rendering pressure |
| 359, 360 | Upper neighbor and maximum; challenge cap/overflow/substitution mistakes |
| Three additional fresh launches each at61,160,360 | Repeated process attachment, initialization, resets where observed, exit and restoration at low/middle/high requests |
| One additional120 launch after each of those repeated-launch groups | Revisit the default after different prior targets to challenge stale configuration/lifecycle state |

All repetitions are predeclared lifecycle checks, not retries after failure.
The same stop rules apply. The initial suite and this matrix can support a claim
that every integer follows one verified target-independent implementation, with
representative controlled runtime evidence. They cannot establish a zero-crash
probability, every game state, arbitrary Wine versions or guaranteed rendered
FPS. The exhaustive offline61–360 tests establish common numeric handling and
modeled memory behavior; no multiplication of those cases converts them into300
gameplay observations. Additional testing should follow an observed mechanism or
new state transition, not merely the count of unplayed integer values.
