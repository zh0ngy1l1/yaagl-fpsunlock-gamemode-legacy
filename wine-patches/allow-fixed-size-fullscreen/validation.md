# Validation on this Mac

macOS 26.6.2, Apple Silicon, x86-64 Wine under Rosetta. Automated tests use the isolated
`/Users/david/code/home/yaagl-wine-fullscreen/test-prefix` and an actual logged-in
Cocoa/WindowServer session. The Genshin prefix was not used for automated test
launches. The subsequent user-reported game test used the actual YAAGL prefix.

Build and package checks completed:

- Pinned upstream source archive checksum and locally cached YAAGL engine archive
  checksum match their published values. The original installed macOS driver
  also matches the driver inside that release archive byte for byte.
- All 17 distribution patches applied in order, without fuzz.
- Driver compiled, including both i386 and x86_64 PE frontends and x86_64 Unix backend.
- Full engine `make -j8` and `make install-lib` completed. After the owned-window
  restoration fix, the full `make -j8` and install were repeated successfully.
- 33 built native binaries: correct x86-64 architecture, valid local signatures,
  and no absolute build/Homebrew/MacPorts dependency load paths.
- All 3,499 external dependency files match the original engine byte for byte.
- DXMT `macdrv_functions` and WoW64 driver exports are retained.
- Complete tar.xz extracted into `unpacked/wine`; all 33 native hashes match and
  the extracted engine reports `wine-11.0`.
- Archive SHA-256: `db2509b58851857f1cf206e980c0b951d8c2d5485f6c6a19e79a13e13495a53c`.

The initial enabled test found owned-window drift after repeated entry/exit.
The final patch saves/restores owned-window frames only for the opted-in fixed
parent. The rerun restores all 12 Win32 geometries exactly. The initial logs are
preserved as `logs/pre-owned-fix-*` to distinguish them from the final tests.

The first build attempts also exposed an old system Bison selected by `PATH`
and an inotify header missing from the general dependency include directory.
The checked-in build/prepare scripts include both fixes. No extra Wine source
changes were needed to solve those dependency issues.

Final runtime matrix (full native and Win32 geometry checks), completed 2026-09-11.
All nine runs passed; `validation-results.json` records log paths and SHA-256
digests. Final native-driver source diff: 6 files, 58 additions, 2 deletions.

| Engine / setting | Result |
| --- | --- |
| Original, absent | Pass |
| Original, N | Pass |
| Final build, absent | Pass |
| Final build, N | Pass |
| Final build, Y | Pass |
| Global Y + fullscreen.exe override N | Pass |
| Global N + fullscreen.exe override Y | Pass |
| Fixed Windows style, no explicit min/max limits, Y | Pass |
| 32-bit app on extracted WoW64 engine, Y | Pass |

The extra test without explicit application min/max limits expands to native
fullscreen dimensions, then restores its 480x300 windowed client and all original
styles/owned-window positions. The geometry checker was adjusted to distinguish
that permitted native-fullscreen resize from violating explicit application
limits; the captured runtime log passes the corrected check.

Integration is complete: built → original → built switching was exercised,
and the built engine is currently selected. All 11,038 original engine file
hashes were verified intact in `wine.original-before-fixed-fullscreen`. At the
initial integration check, the game prefix's `user.reg`, shared engine driver,
and both launcher selection files were byte-identical to the saved starting
state; `integration-audit.txt` records that historical check. The user subsequently
enabled `AllowFixedSizeFullscreen=Y` in the game prefix. Cleanup preserves this
enabled setting and the selected built engine.

User-reported manual Genshin validation (2026-09-11), separate from the automated
matrix: the user enabled the option with the supplied command, opened YAAGL,
launched Genshin, and confirmed working fullscreen with Wine in its own macOS
desktop/Space. No crash was observed during that test; the user quit manually.
This report does not test extended gameplay stability, game fullscreen-exit
geometry, or physical Command/Option input. Automated fixture restoration results
above should not be read as measurements of Genshin's exit geometry.

Each full test checks green-button/collection eligibility, a genuine fullscreen
Space (WindowServer type 4), three entry/exit cycles, exact restoration of
windowed bounds, normal resizable windows, maximize-box fixed windows,
application min/max limits, and exclusion of owned/tool/popup/dialog/ownerless
standard dialog/nonactivating/child/disabled windows. The Win32 log verifies all
12 final window/client rectangles and unchanged style bits. The eligible fixed
window uses a 480x300 client area. Cocoa's fullscreen flag is `0x4000`; its native
resizable flag `0x8` stays absent on that fixed window.

Keyboard verification:

- `keyboard.c`, `cocoa_app.m`, `cocoa_event.m`, `cocoa_main.m`, and `event.c` are
  byte-identical to the patched distribution baseline.
- Every pre-existing method in `cocoa_window.m` outside the eight window lifecycle
  methods in this patch is identical, including all event/shortcut/modifier methods.
- All four Command/Option option defaults and readers are unchanged.
- `src/wine`, `src/launcher`, and `src/config` match the launcher starting commit.
- See `keyboard-audit.json` and the reproducible `check-keyboard.py`.
- No synthetic keyboard input or remapping is present in the implementation/tests.

Remaining manual checks: physical Command/Option input before/after, extended
gameplay and game fullscreen-exit geometry, multiple-monitor/Retina changes, and
forced AppKit transition failure paths. These are not claimed as runtime-tested. Code paths restore saved
owned-window state on failed entry and retain it for retry on failed exit.

Final cleanup checks (2026-09-11): the exported patch exactly matches the Wine
diff against `yaagl-baseline`, passes reverse-application checking, and retains
its recorded SHA-256. The existing keyboard audit passes with identical output.
Python syntax, shell syntax/executable permissions, and JSON parsing pass.
The selection helper now also recognizes processes using the resolved built-engine
path; all 12 mocked process cases pass without changing the real engine selection.
Wine source and launcher `git diff --check` pass; the patch file's Git whitespace
attributes allow the space-only context lines inherent in a unified diff.
Only disposable Python caches and task-folder Finder metadata were removed.
No Wine runtime source changed during cleanup, and neither the engine build nor
the runtime suite was repeated. The manual game report covers the retained build.
