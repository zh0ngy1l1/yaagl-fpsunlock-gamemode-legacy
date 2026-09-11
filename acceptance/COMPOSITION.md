# Frozen product composition and limits

The candidate changes the field-selection operand and temporary-protection calculation in the selected per-game Wine library.
The source correction has no FPS-number test. No frontend or companion source
change is included; build/test/acceptance tooling is separate from the product.

| Requirement | Frozen behavior / supporting source |
|---|---|
| Frontend identity | `a0e8c704327e0d2568fbb4a0c569eee1f2188110`, both resource files`4724889a…`; admission/close and request-owned Wine waits retained |
| Companion identity | Ordinary published v3.0.7`8543f45a…`, source`56b9c643…`; no d23 sidecar or automatic-write gate |
| Runtime identity | Selected Genshin Wine11.0 distribution; exact `ntdll.so` input`f26ade35…` replaced only by reviewed signed`eef64f61…` |
| Game identity / semantic scope | Exact native AMD64/NX-compatible Genshin image`a1a23cb7…`; controlled review is for this game/prefix, not a generally certified Wine32/WoW64 runtime patch |
| Prefix | Existing per-game-selected prefix and Wine path; no new prefix or global Wine selection |
| Default and maximum | `src/config/defaults.ts`:120; `src/launcher/fps-target.ts`:strict integer1–360; saved values remain authoritative when read successfully |
| Exact high targets | Every61–360 value remains distinct through preference validation, command generation and exact four-byte companion payload |
| Disabled | No companion invocation; existing renderer behavior and saved raw target preserved |
| Enabled≤60 | Companion still receives exact T; game and companion DXMT receive T; zero is not an enabled frontend target |
| Enabled>60/DXMT | Game DXMT0; companion DXMT T; numeric argument T; no150-only renderer branch |
| Companion precedence | CLI target overrides loaded FPS target; existing power-save setting can select a background value; accepted suite config requires power-save=false |
| Attachment and updates | Ordinary game-window/process attachment, module/address resolution and200ms read/compare/write loop; complete read required, equality skips, full-success write logged |
| Resets | A differing full read permits another exact-target write; no one-write limit, extra60-read rule or manual arm |
| Lifetime | Same process ownership, cancellation, game/companion waiting, normal close and patch cleanup paths |

The exact source-path review and release-source fixture are separate evidence for
these claims. Parameter forwarding establishes numeric behavior, not crash
reliability or achieved rendering throughput.

Two literal claims cannot honestly be made about the frozen baseline:

* The existing frontend **already contains waits**: its delayed-companion timer,
  process discovery and a10-second shell initialization wait are visible in
  `src/launcher/hoyoplay-injections.ts`; retries also wait. Keeping byte-identical
  `a0e8c704` precludes claiming that no timing code exists. This correction adds
  no timing heuristic and relies on none of those waits as a safe activation
  condition. Removing inherited waits would be a different product change.
* The selected runtime's helper correction affects all callers of that
  helper in that runtime, not just the FPS address. Wine's32-bit forced-execute
  compatibility mode can make logical protection diverge from host execution
  permission. Readable temporary protections can also regain host execution in
  this mode. The exact native Win64 game cannot normally enable that mode;
  this does not prove the absence of every other possible runtime caller or
  target. The semantic audit records this compatibility risk explicitly.

No new120/150/160 alias, arbitrary cap, manual activation requirement or hidden
diagnostic dependency is introduced. Existing generic storage-error fallback
and the DXMT config-section precedence edge case are documented baseline
caveats, not silently fixed in the crash candidate. Native shutdown SIGILL and
unobserved resolver/lifetime robustness paths remain separate. Recovery
`a2f6568` remains excluded.
