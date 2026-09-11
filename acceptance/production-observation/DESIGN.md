# Observe the ordinary product, without substituting the diagnostic algorithm

The chosen evidence path uses the ordinary release companion's existing log,
passive native foreground events, and a continuous screen recording. Frontend,
companion, corrected Wine library, prefix selection and launch environment stay
identical to the intended product. No diagnostic sidecar, first-60/foreground
gate, manual arm, measurement hotkey, remote-memory reader, injected library or
additional Wine command is part of this observer.

The recording and passive host observer start during acceptance preparation,
before the user opens the game normally. They do not release a launch gate or
signal the launcher. The user has no Terminal step or gameplay shortcut.
Preparation and all acceptance execution remain unperformed in this review.

## What ordinary logging already proves

Pinned v3.0.7 `GameInstanceService.ApplyFpsLimit` performs a full four-byte read,
returns on failed/short reads or equality, then constructs the exact target bytes.
Its `FPS Override: old -> target` message occurs only after WriteProcessMemory
returns success and exactly four bytes. The release source is pinned at
`56b9c64381ef9fd59e916dc9bf547d3210ab5db1`; the installed/published executable
hash is `8543f45a4edced854ab8c5466ce2dc2e511fb4f89361bc4dfb474b68d998cc17`.
The generated production shell already appends stdout to
`logs/hoyoplay_genshin_fps_unlocker.log`. Reading its newly appended bytes after
the run adds no observation work to the companion's polling loop.

A new, unambiguous launch session with the expected target, selected Wine/prefix,
resolved FPS address and a matching override line is source-supported evidence
that the requested value reached a successful complete write path. It does not
provide a sealed per-write Windows PID binding, sequence number, exact native-call
timestamp, memory protection, or journal receipt. The existing attachment line
does record the Windows PID; native host PID is a separate identity. Missing log output is inconclusive
for the write, not proof that no write occurred. A logged API result does not
prove that the operation had no side effects.

The log must be scoped by a pre-run byte snapshot, inode/size/hash and post-run
snapshot. Require an unchanged old prefix, exactly one new production launch
session, the expected component identities, no concurrent competing game or
companion, and no unexplained truncation, second attachment, target mismatch or
restart. Preserve all new lines, including unsuccessful outcomes. Repeated
override messages demonstrate later successful writes after differing reads;
they do not identify the actor or instant of a game reset.

## Observation alternatives and attribution

| Approach | Fact available | Production change | Limitation / decision |
|---|---|---|---|
| Existing release log, read after exit | Configured target, attachment/address messages, successful full-write branch, later writes | No bytes, environment, eligibility, first-write or polling change | Chosen; source-dependent log evidence, without per-operation journal completeness |
| Passive native workspace events | Native app identity and foreground transitions, launch/termination notifications | Separate observer process; no focus requests or production hooks | Chosen; delivery latency and possible loss must be reported; native PID is not automatically a Windows PID |
| Continuous screen recording | Visible login/world transition, uninterrupted gameplay interval and displayed HUD samples | Separate recorder; no production byte/environment/eligibility change | Chosen compromise; recording consumes CPU/GPU/I/O and may affect achieved FPS or scheduling |
| External camera, if available | Same visible scene/HUD evidence with no host capture load | No host process or environment change | Optional lower-overhead substitute only if readable timing and continuous footage are available; equipment is not assumed |
| Additional external RPM polling | Readback samples | Extra process, Wine/API activity and scheduling | Rejected: adds operations without proving the companion's exact write |
| d23 journal/receipt profile | Strong per-operation journal evidence | Different binary, sidecar and first-60/foreground gate | Rejected for ordinary-production acceptance |
| Add logging to release source | More operation metadata | Different binary and hot-path work | Not needed for the selected evidence standard; would need separate attribution and validation |
| Runtime hooks or tracing | More precise native operations | Runtime behavior and scheduling changes | Excluded by scope and restrictions |

The chosen observer does not directly alter attachment eligibility, the
production write decision, polling frequency, process focus, saved preferences
or launch environment. It cannot promise zero scheduling perturbation: every
external observer and screen recorder consumes resources. A later success is
therefore ordinary product startup **under the declared passive observation
load**, not a claim of unobserved timing equivalence or universal reliability.

## Foreground and gameplay without a hotkey

Capture starts before game launch and continues through game exit, Ready and
normal launcher quit. Do not derive world readiness from FPS, elapsed startup
time or a foreground event. A reviewer identifies the first settled playable-world
frame in the recording and selects the first subsequent uninterrupted interval
of at least 125 seconds. Record exact media start/end timestamps, frame/sample
coverage, visible world/HUD confirmation, and the user's gameplay observations.

Use native foreground events as an independent control. The conservative initial
protocol requires a single bound native game host, with no recorded focus loss
between its first foreground activation and its final departure for normal
game close. A single final deactivation before termination is permitted only
when the video corroborates normal close after the accepted interval; any
reactivation or earlier focus loss is rejected. The continuous video must
show that same game appearing after observer startup and disappearing at exit,
with the entire selected gameplay interval inside that span. This avoids inventing
an exact video-to-host-clock offset from asynchronous recorder startup. If this
containment cannot be established, the run is inconclusive and progression stops.
Do not splice intervals across focus changes or fill capture gaps with assumptions.

The recording must be continuous and readable. Preserve original media, duration,
sample timestamps, decode errors and maximum timestamp gap. An unexplained gap,
missing world/HUD view, capture failure, observer sequence gap or missing footer
prevents full acceptance. No time inferred from repeated FPS reads substitutes
for visible gameplay. HUD samples are displayed metrics, not measurements of
every rendered frame; report their sampling method and min/median/max separately
from requested target and successful write value.

The macOS `screencapture(1)` manual on this machine documents noninteractive
video (`-v`), bounded duration (`-V`) and display selection (`-D`). A later operator
can start recording through the prepared observer/controller without a user
Terminal or game hotkey. Omit interactive/UI, microphone and sound options.
Screen-recording access must already be verified before game launch; no permission
prompt may be answered during the measured run. This review does not execute
screen capture, the observer against a game, Wine or the candidate.

## Evidentiary compromise

This closes the production-algorithm gap by keeping the actual product binaries
and behavior intact. It deliberately provides weaker write timing/completeness
than d23's journal. Full acceptance under this protocol requires independently
scoped production log evidence, identity checks, native foreground integrity,
continuous visible gameplay/HUD evidence, normal lifecycle and restoration.
It does not require or fabricate a d23 receipt. The earlier d23 assessments and
their original verdicts remain unchanged; this is a separately named acceptance
profile with explicit controls and limits.
