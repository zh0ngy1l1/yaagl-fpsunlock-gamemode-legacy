import copy
import json
from pathlib import Path
import tempfile
import unittest

import production_evidence as evidence


WINE = "/selected/wine/bin/wine"
PREFIX = "/existing/prefix"


def session(target=120):
    return (f"----- Thu Sep 10 12:00:00 EDT 2026 -----\nWINE={WINE}\n"
            f"WINEPREFIX={PREFIX}\nDXMT_CONFIG=d3d11.preferredMaxFrameRate={target};\n"
            f"WINEPREFIX={PREFIX}\nStarting unlockfps.exe with target {target}...\n"
            f"Starting in headless mode with FPS limit: {target}\r\n"
            "[12:00:01.000] INFO GameInstanceService: Get FPS address successfully: 5455430212\r\n"
            "[12:00:01.001] INFO GameInstanceService: Find the game window: [0x000000000003006E UnityWndClass] (200 GenshinImpact.exe) Genshin Impact\r\n"
            "[12:00:01.002] INFO GameInstanceService: Start applying FPS.\r\n"
            f"[12:00:01.010] INFO GameInstanceService: FPS Override: -1 -> {target}\r\n"
            f"[12:00:01.210] INFO GameInstanceService: FPS Override: 60 -> {target}\r\n"
            "[12:03:20.000] INFO GameInstanceService: Process exit: GenshinImpact\r\n"
            "[12:03:20.001] INFO GameInstanceService: Stop applying FPS.\r\n").encode()


def snapshots(data):
    old = b"old immutable session\n"
    def meta(value):
        return {"source": "/log", "dev": 1, "ino": 2, "size": len(value), "sha256": evidence.sha256(value)}
    return (meta(old), old), (meta(old + data), old + data)


def assess(data, target=120):
    return evidence.assess_release_log(*snapshots(data), target=target, wine=WINE, prefix=PREFIX)


def native_rows():
    bound = {"pid": 10, "executable": "/selected/wine", "launchDate": "2026-09-10T00:00:00.000Z", "name": "game"}
    other = {"pid": 20, "executable": "/launcher", "launchDate": "date", "name": "launcher"}
    state = {"bound": bound, "integrity_ok": True, "complete_native_lifecycle": True,
             "selected_host_count": 1, "failures": []}
    events = [("startup", None, other), ("ready", None, other), ("activate", bound, bound)]
    events.extend(("heartbeat", None, bound) for _ in range(128))
    events.extend([("deactivate", bound, other), ("terminate", bound, other),
                   ("heartbeat", None, other), ("footer", None, other)])
    rows = [{"kind": kind, "sequence": i + 1, "monotonic_ns": 100_000_000 + i * 500_000_000,
             "expected_native_executable": "/selected/wine", "observer_pid": 99,
             "affected": copy.deepcopy(affected), "foreground": copy.deepcopy(front), "state": copy.deepcopy(state)}
            for i, (kind, affected, front) in enumerate(events)]
    rows[-1].update(event_count_before_footer=len(rows) - 1, production_processes_signaled=False)
    return rows


class LogTests(unittest.TestCase):
    def rejects(self, data, phrase):
        with self.assertRaisesRegex(evidence.EvidenceError, phrase):
            assess(data)

    def test_release_branch_evidence_for_each_target(self):
        for target in range(61, 361):
            with self.subTest(target=target):
                result = assess(session(target), target)
                self.assertEqual([w["target"] for w in result["writes"]], [target, target])
                self.assertEqual(result["windows_pid_at_attachment"], 200)
        # Parameter/log interpretation only: not runtime reliability evidence.

    def test_archived_release_format(self):
        base = Path(__file__).parent / "fixtures"
        raw = (base / "archived-release-session-150.log").read_bytes()
        provenance = json.loads((base / "PROVENANCE.json").read_text())
        self.assertEqual(evidence.sha256(raw), provenance["fixture_sha256"])
        meta = {"source": "archive", "dev": 0, "ino": 0}
        result = evidence.assess_release_log((meta, b""), (meta, raw), target=150,
            wine="/Users/david/Library/Application Support/Yaagl OS/hoyoplay-wines/genshin/11.0-dxmt-signed-with-patches/wine/bin/wine",
            prefix="/Users/david/Library/Application Support/Yaagl OS/wineprefix")
        self.assertEqual(result, json.loads((base / "ARCHIVED-REPLAY.json").read_text()))

    def test_enabled_below_or_equal_60_uses_same_log_path(self):
        for target in (1, 30, 59, 60):
            data = session(target).replace(f"FPS Override: 60 -> {target}".encode(), f"FPS Override: 30 -> {target}".encode())
            if target == 30:
                data = data.replace(b"FPS Override: 30 -> 30", b"FPS Override: 60 -> 30")
            self.assertTrue(assess(data, target)["source_supported_complete_write"])

    def test_disabled_no_companion_cannot_claim_write(self):
        self.rejects(b"\n", "exactly one new shell")

    def test_mismatched_target(self):
        self.rejects(session().replace(b"FPS Override: -1 -> 120", b"FPS Override: -1 -> 150"), "Write target mismatch")

    def test_duplicate_session(self):
        self.rejects(session() + session(), "exactly one new shell")

    def test_duplicate_headless(self):
        self.rejects(session() + b"Starting in headless mode with FPS limit: 120\n", "one headless")

    def test_duplicate_companion(self):
        self.rejects(session() + b"Another instance of the unlocker is already running.\n", "Duplicate companion")

    def test_diagnostic_companion(self):
        self.rejects(session() + b"diagnostic run initialized\n", "Diagnostic companion")

    def test_no_successful_write(self):
        self.rejects(b"\n".join(line for line in session().split(b"\n") if b"FPS Override" not in line), "No successful complete-write")

    def test_malformed_success(self):
        self.rejects(session().replace(b"FPS Override: -1 -> 120", b"FPS Override: failed -> 120"), "Unrecognized write")

    def test_equality(self):
        self.rejects(session().replace(b"FPS Override: -1 -> 120", b"FPS Override: 120 -> 120"), "Equality")

    def test_wrong_address(self):
        self.rejects(session().replace(b"5455430212", b"5455430216"), "Resolved address")

    def test_second_attachment(self):
        line = next(line for line in session().splitlines() if b"Find the game window:" in line)
        self.rejects(session() + line + b"\n", "one Genshin attachment")

    def test_wrong_game(self):
        self.rejects(session().replace(b"GenshinImpact.exe", b"OtherGame.exe"), "one Genshin attachment")

    def test_write_before_attachment(self):
        line = next(line for line in session().splitlines() if b"FPS Override:" in line)
        self.rejects(line + b"\n" + session(), "Write precedes")

    def test_write_after_stop(self):
        line = next(line for line in session().splitlines() if b"FPS Override:" in line)
        self.rejects(session() + line + b"\n", "Write after stopped")

    def test_environment_mismatch(self):
        self.rejects(session().replace(PREFIX.encode(), b"/wrong"), "prefix mismatch")
        self.rejects(session() + b"WINE=/other\n", "Conflicting Wine")
        self.rejects(session().replace(b"preferredMaxFrameRate=120", b"preferredMaxFrameRate=150"), "renderer target")

    def test_unscoped_existing_write_not_reused(self):
        before, after = snapshots(session())
        with self.assertRaisesRegex(evidence.EvidenceError, "No appended"):
            evidence.appended(after, after)

    def test_changed_inode(self):
        before, after = snapshots(session())
        after[0]["ino"] = 3
        with self.assertRaisesRegex(evidence.EvidenceError, "inode changed"):
            evidence.appended(before, after)

    def test_truncated_prefix(self):
        before, after = snapshots(session())
        with self.assertRaisesRegex(evidence.EvidenceError, "prefix changed"):
            evidence.appended(before, (after[0], b"x" + after[1][1:]))

    def test_partial_lines(self):
        self.rejects(session()[:-1], "Incomplete final")
        before, after = snapshots(session())
        with self.assertRaisesRegex(evidence.EvidenceError, "splits a log line"):
            evidence.appended((before[0], before[1][:-1]), after)

    def test_snapshot_roundtrip_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "log").write_bytes(b"first\n")
            evidence.snapshot(path / "log", path / "before")
            with (path / "log").open("ab") as stream:
                stream.write(session())
            evidence.snapshot(path / "log", path / "after")
            self.assertEqual(evidence.appended(evidence.load_snapshot(path / "before"), evidence.load_snapshot(path / "after")), session())
            with self.assertRaises(FileExistsError):
                evidence.snapshot(path / "log", path / "before")
            (path / "link").symlink_to(path / "log")
            with self.assertRaises(OSError):
                evidence.snapshot(path / "link", path / "symlink")
            (path / "after" / "log.bin").write_bytes(b"changed")
            with self.assertRaisesRegex(evidence.EvidenceError, "identity mismatch"):
                evidence.load_snapshot(path / "after")


class NativeTests(unittest.TestCase):
    def test_terminal_departure_allowed(self):
        result = evidence.assess_native(native_rows(), expected_executable="/selected/wine")
        self.assertLess(result["terminal_departure_ns"], result["termination_ns"])

    def test_missing_footer(self):
        with self.assertRaisesRegex(evidence.EvidenceError, "footer missing"):
            evidence.assess_native(native_rows()[:-1], expected_executable="/selected/wine")

    def test_sequence_gap(self):
        rows = native_rows(); rows[5]["sequence"] += 1
        with self.assertRaisesRegex(evidence.EvidenceError, "sequence gap"):
            evidence.assess_native(rows, expected_executable="/selected/wine")

    def test_backward_clock(self):
        rows = native_rows(); rows[5]["monotonic_ns"] = 1
        with self.assertRaisesRegex(evidence.EvidenceError, "monotonic clock"):
            evidence.assess_native(rows, expected_executable="/selected/wine")

    def test_heartbeat_gap(self):
        rows = native_rows()
        for row in rows[10:]: row["monotonic_ns"] += 4_000_000_000
        with self.assertRaisesRegex(evidence.EvidenceError, "heartbeat missing or gap"):
            evidence.assess_native(rows, expected_executable="/selected/wine")

    def test_forged_footer_cannot_hide_second_activation(self):
        rows = native_rows(); rows[5]["kind"] = "activate"; rows[5]["affected"] = rows[2]["affected"]
        with self.assertRaisesRegex(evidence.EvidenceError, "not singular"):
            evidence.assess_native(rows, expected_executable="/selected/wine")

    def test_forged_footer_cannot_hide_focus_loss(self):
        rows = native_rows(); rows[5]["foreground"] = rows[0]["foreground"]
        with self.assertRaisesRegex(evidence.EvidenceError, "foreground differs"):
            evidence.assess_native(rows, expected_executable="/selected/wine")

    def test_recorded_other_activation_between_heartbeats(self):
        rows = native_rows()
        rows[5].update(kind="activate", affected=rows[0]["foreground"], foreground=rows[0]["foreground"])
        with self.assertRaisesRegex(evidence.EvidenceError, "Other application activated"):
            evidence.assess_native(rows, expected_executable="/selected/wine")

    def test_other_activation_cannot_hide_behind_matching_snapshot(self):
        rows = native_rows()
        rows[5].update(kind="activate", affected=rows[0]["foreground"])
        with self.assertRaisesRegex(evidence.EvidenceError, "Other application activated"):
            evidence.assess_native(rows, expected_executable="/selected/wine")

    def test_nonheartbeat_snapshot_can_disprove_foreground_span(self):
        rows = native_rows()
        rows[5].update(kind="launch", affected=rows[0]["foreground"], foreground=rows[0]["foreground"])
        with self.assertRaisesRegex(evidence.EvidenceError, "foreground differs"):
            evidence.assess_native(rows, expected_executable="/selected/wine")

    def test_identity_reuse(self):
        rows = native_rows(); rows[5]["foreground"]["launchDate"] = "reused"
        with self.assertRaises(evidence.EvidenceError): evidence.assess_native(rows, expected_executable="/selected/wine")

    def test_observer_failure_survives_good_footer(self):
        rows = native_rows(); rows[5]["state"]["failures"] = ["observer_became_foreground"]
        with self.assertRaisesRegex(evidence.EvidenceError, "detected failure"):
            evidence.assess_native(rows, expected_executable="/selected/wine")

    def test_missing_birth_identity(self):
        rows = native_rows(); rows[-1]["state"]["bound"]["launchDate"] = ""
        with self.assertRaisesRegex(evidence.EvidenceError, "Incomplete native"):
            evidence.assess_native(rows, expected_executable="/selected/wine")


if __name__ == "__main__":
    unittest.main(verbosity=2)
