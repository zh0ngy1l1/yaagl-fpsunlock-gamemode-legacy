#!/usr/bin/env python3
"""Focused final-adapter checks; production dependencies and mutation are inert."""
import argparse
import contextlib
import copy
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("transaction", ROOT / "transaction.py")
core = importlib.util.module_from_spec(spec); sys.modules["transaction"] = core; spec.loader.exec_module(core)
spec = importlib.util.spec_from_file_location("adapter_under_review", ROOT / "protected_guard.py")
adapter = importlib.util.module_from_spec(spec); spec.loader.exec_module(adapter)
OUTPUT = None
ORIGINAL_INPUT = CANDIDATE_INPUT = None


class MutationBoundary(core.Stop):
    pass


class AdapterTests(unittest.TestCase):
    def parents(self):
        return {"/captured/ancestor": {"dev": 1, "ino": 2, "uid": 501,
                                     "gid": 20, "mode": 0o40700, "flags": 0}}

    def current_parent(self):
        return {"stat": copy.deepcopy(self.parents()["/captured/ancestor"]),
                "acl": {"state": "absent", "errno": 2}}

    def test_every_historical_parent_field_is_required(self):
        for key in self.parents()["/captured/ancestor"]:
            altered = self.current_parent(); altered["stat"][key] += 1
            with self.subTest(field=key), patch.object(core, "directory_identity", return_value=altered):
                with self.assertRaisesRegex(core.Stop, "Historical parent"):
                    adapter.match_historical_parents(self.parents())

    def test_missing_historical_parent_field_fails_closed(self):
        altered = self.current_parent(); del altered["stat"]["flags"]
        with patch.object(core, "directory_identity", return_value=altered):
            with self.assertRaises(core.Stop): adapter.match_historical_parents(self.parents())

    def test_matching_parents_return_current_acl_for_fresh_binding(self):
        current = self.current_parent()
        with patch.object(core, "directory_identity", return_value=current):
            result = adapter.match_historical_parents(self.parents())
        self.assertEqual(result, {"/captured/ancestor": current})
        self.assertNotIn("acl", self.parents()["/captured/ancestor"])
        # The historical record has no ACL: this must not be presented as a
        # retrospective ACL comparison. Current ACL becomes a fresh exact pin.

    def test_parent_native_inspection_error_is_not_a_new_baseline(self):
        with patch.object(core, "directory_identity", side_effect=core.Stop("Inspection failed")):
            with self.assertRaises(core.Stop): adapter.match_historical_parents(self.parents())

    def test_historical_acl_absence_and_present_are_distinct(self):
        absent = {"state": "absence corroborated by native ls -e"}
        adapter.match_historical_acl({"state": "absent", "errno": 2}, absent)
        with self.assertRaises(core.Stop):
            adapter.match_historical_acl({"state": "present", "serialized_hex": "00"}, absent)
        with self.assertRaises(core.Stop):
            adapter.match_historical_acl({"state": "absent", "errno": 13}, absent)

    def test_explicit_authorization_and_transition_consent_are_required(self):
        for reference, transition in (("", True), ("   ", True), ("unit test only", False)):
            with patch.object(core, "_build", return_value=core.EXPECTED_BUILD), \
                    patch.object(core, "_open_parent", side_effect=AssertionError("Mutation reached")):
                with self.assertRaises(core.Stop):
                    adapter.create_authorized_admission(OUTPUT / "must-not-exist", reference,
                        managed_provenance_transition_authorized=transition,
                        reviewed_core_sha256="bad", reviewed_adapter_sha256="bad", reviewed_procedure_sha256="bad")

    def test_stopped_transaction_cannot_be_readmitted(self):
        with patch.object(core, "_build", return_value=core.EXPECTED_BUILD), \
                patch.object(os.path, "lexists", return_value=False), \
                patch.object(core, "_open_parent", side_effect=AssertionError("Mutation reached")):
            with self.assertRaisesRegex(core.Stop, "Stopped transaction"):
                adapter.create_authorized_admission(adapter.STOPPED, "unit test only",
                    managed_provenance_transition_authorized=True,
                    reviewed_core_sha256="bad", reviewed_adapter_sha256="bad", reviewed_procedure_sha256="bad")

    def inert_admission(self, *, bad_hash=False, parent_drift=False, expect_boundary=False):
        """Execute validation with fully mocked production reads; never create admission."""
        case = OUTPUT / self._testMethodName
        case.mkdir(mode=0o700)
        installed = case / "inert-stat-marker"
        installed.write_bytes(b"not a runtime; stat-only test marker")
        destination = case / "fresh-but-never-created-admission"
        def record(path, digest, provenance):
            return {"path": str(path), "resolved": str(path), "sha256": digest,
                    "stat": {"size": core.SIZE, "nlink": 1},
                    "xattrs": {core.PROVENANCE: provenance},
                    "signature": {"verified": True}, "acl": {"state": "absent", "errno": 2}}
        original = record(installed, core.ORIGINAL, "010000dcd5bccdc7edc92e")
        candidate = record(core.REVIEWED_CANDIDATE, core.CANDIDATE, "01020059c71153554e5113")
        historical = {"original": copy.deepcopy(original), "staged": copy.deepcopy(candidate)}
        controls = {"parents": self.parents(),
                    "original_acl": {"state": "absence corroborated by native ls -e"},
                    "staged_acl": {"state": "absence corroborated by native ls -e"}}
        def pinned(path, digest):
            return json.dumps(controls if Path(path).name == "03c-metadata-controls.json" else historical).encode()
        parent = self.current_parent()
        if parent_drift: parent["stat"]["ino"] += 1
        procedure = ROOT.parent / "DEPLOYMENT.md"
        hashes = {"reviewed_core_sha256": hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest(),
                  "reviewed_adapter_sha256": hashlib.sha256(Path(adapter.__file__).read_bytes()).hexdigest(),
                  "reviewed_procedure_sha256": hashlib.sha256(procedure.read_bytes()).hexdigest()}
        if bad_hash: hashes["reviewed_core_sha256"] = "00" * 32
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(core, "INSTALLED", installed))
            stack.enter_context(patch.object(core, "_build", return_value=core.EXPECTED_BUILD))
            stack.enter_context(patch.object(core, "inspect_file", side_effect=lambda p: copy.deepcopy(original if Path(p) == installed else candidate)))
            stack.enter_context(patch.object(core, "directory_identity", return_value=parent))
            stack.enter_context(patch.object(adapter, "pinned_read", side_effect=pinned))
            stack.enter_context(patch.object(adapter, "ProtectedGuard", return_value=lambda: {"inert": "unchanged"}))
            opened = stack.enter_context(patch.object(core, "_open_parent", side_effect=MutationBoundary("Native creation deliberately blocked")))
            if expect_boundary:
                with self.assertRaises(MutationBoundary):
                    adapter.create_authorized_admission(destination, "INERT TEST; NOT USER AUTHORIZATION",
                        managed_provenance_transition_authorized=True, **hashes)
                self.assertEqual(opened.call_count, 1)
            else:
                with self.assertRaises(core.Stop):
                    adapter.create_authorized_admission(destination, "INERT TEST; NOT USER AUTHORIZATION",
                        managed_provenance_transition_authorized=True, **hashes)
                opened.assert_not_called()
        self.assertFalse(destination.exists())
        self.assertEqual(installed.read_bytes(), b"not a runtime; stat-only test marker")

    def test_reviewed_hash_mismatch_stops_before_creation(self):
        self.inert_admission(bad_hash=True)

    def test_historical_parent_drift_stops_before_creation(self):
        self.inert_admission(parent_drift=True)

    def test_matching_inert_preflight_reaches_only_mocked_mutation_boundary(self):
        self.inert_admission(expect_boundary=True)


class CoreAddendumTests(unittest.TestCase):
    def setUp(self):
        self.root = OUTPUT / self._testMethodName
        self.tx = core.create_replica(self.root, ORIGINAL_INPUT, CANDIDATE_INPUT)

    def test_parent_binding_failure_closes_opened_source_descriptor(self):
        expected = core.inspect_file(self.tx.candidate)
        native_open = core.os.open
        descriptors = []
        def remember_source(path, flags, *args, **kwargs):
            fd = native_open(path, flags, *args, **kwargs)
            if Path(path) == self.tx.original and flags == (os.O_RDONLY | os.O_NOFOLLOW):
                descriptors.append(fd)
            return fd
        with patch.object(core.os, "open", remember_source), \
                patch.object(core, "_open_parent", side_effect=core.Stop("Injected parent bind failure")):
            with self.assertRaisesRegex(core.Stop, "Injected parent bind"):
                core._copy_metadata(self.tx.original, self.tx.candidate, expected)
        self.assertEqual(len(descriptors), 1, "Expected source-open failure boundary was not exercised")
        closed = []
        for fd in descriptors:
            try:
                os.fstat(fd)
            except OSError as error:
                self.assertEqual(error.errno, errno.EBADF)
                closed.append(fd)
            else:
                os.close(fd)
                self.fail("Source descriptor leaked after parent binding failed")
        core.same_instance(expected, core.inspect_file(self.tx.candidate))
        (self.root / "FD-CLOSURE.json").write_text(json.dumps({
            "source_descriptors_opened": descriptors, "descriptors_confirmed_closed": closed,
            "candidate_unchanged": True, "test_used_real_source_descriptor": True,
            "parent_failure_injected": True}, indent=2) + "\n")

    def test_final_core_fresh_roundtrip(self):
        original = core.inspect_file(self.tx.slot)
        backup = self.tx.prepare()
        deployed = self.tx.deploy()
        restored = core.RuntimeTransaction(self.root).restore()
        self.assertEqual(backup["sha256"], core.ORIGINAL)
        self.assertNotEqual(original["stat"]["ino"], backup["stat"]["ino"])
        self.assertEqual(deployed["sha256"], core.CANDIDATE)
        self.assertTrue(deployed["signature"]["verified"])
        self.assertEqual(restored["sha256"], core.ORIGINAL)
        self.assertTrue(restored["signature"]["verified"])
        core.required_metadata(original, restored)
        self.assertEqual(core.RuntimeTransaction(self.root).status()["state"], "RESTORED")
        (self.root / "ROUNDTRIP.json").write_text(json.dumps({
            "original": original, "backup": backup, "deployed": deployed, "restored": restored,
            "same_core_deploy_restore": True, "runtime_executed": False}, indent=2) + "\n")


def main():
    global OUTPUT, ORIGINAL_INPUT, CANDIDATE_INPUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args(); OUTPUT = args.output
    ORIGINAL_INPUT, CANDIDATE_INPUT = args.original, args.candidate
    core.require(OUTPUT.is_absolute() and not OUTPUT.exists(), "Fresh absolute output required")
    core.require(not any(core._inside(OUTPUT, p) for p in core.PROTECTED_ROOTS), "Product output forbidden")
    core._safe_path(OUTPUT, False); OUTPUT.mkdir(mode=0o700)
    paths = (ROOT / "transaction.py", ROOT / "protected_guard.py", Path(__file__).resolve())
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    input_before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (ORIGINAL_INPUT, CANDIDATE_INPUT)}
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(AdapterTests),
                               unittest.defaultTestLoader.loadTestsFromTestCase(CoreAddendumTests)])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    input_after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (ORIGINAL_INPUT, CANDIDATE_INPUT)}
    report = {"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "success": result.wasSuccessful() and before == after and input_before == input_after, "sources_before": before,
              "sources_after": after, "source_unchanged": before == after,
              "input_hashes_before": input_before, "input_hashes_after": input_after,
              "failure_details": [(test.id(), detail) for test, detail in result.failures + result.errors],
              "limits": "Final adapter policy/preflight checks use mocked production dependencies and blocked native creation. Two focused final-core checks use fresh disposable copies and real descriptors/copy/rename/signature interfaces. No actual authorization/admission, live factory, product mutation, runtime/game/Wine execution. Core55-case record reused separately."}
    (OUTPUT / "RESULTS.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("tests", "failures", "errors", "success", "source_unchanged")}, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
