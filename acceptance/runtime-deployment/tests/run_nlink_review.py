#!/usr/bin/env python3
"""Run only the nlink correction and directly relevant existing core regressions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import unittest
sys.dont_write_bytecode = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    forbidden = {"wineprefix", "hoyoplay-wines", "drive_c", "applications"}
    if not args.output.is_absolute() or args.output.exists() or args.output.is_symlink() or \
            forbidden.intersection(p.casefold() for p in args.output.parts) or \
            args.output.parent.resolve() != args.output.parent:
        raise ValueError("Fresh canonical disposable output outside protected products is required")
    args.output.mkdir(mode=0o700)
    for name, value in (("ORIGINAL", args.original), ("CANDIDATE", args.candidate), ("OUTPUT", args.output)):
        os.environ["YAAGL_TEST_" + name] = str(value.resolve(strict=True))
    tests = Path(__file__).resolve().parent
    sys.path.insert(0, str(tests))
    source_paths = [tests.parent / "transaction.py", tests.parent / "protected_guard.py",
                    tests / "test_nlink_guard.py", tests / "test_transaction.py", Path(__file__).resolve()]
    def identities(paths):
        return {str(p): {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "size": p.stat().st_size}
                for p in paths}
    before = identities(source_paths)
    inputs_before = identities([args.original, args.candidate])
    import test_nlink_guard
    import test_transaction
    selected_core = (
        "test_existing_temporary_collision_is_preserved",
        "test_late_copy_parent_swap_cannot_write_outside_case",
        "test_regular_parent_replacement_cannot_be_newly_enrolled",
        "test_late_replace_parent_swap_stays_bound_and_recovers",
        "test_preexisting_exact_restore_temporary_is_not_owned",
        "test_shared_core_temporary_ledger_tracks_phases",
        "test_external_same_hash_original_cannot_claim_restoration",
        "test_failure_after_replace_recovers_through_same_core",
        "test_interruption_after_replace_has_durable_recovery",
        "test_restoration_failure_cannot_seal_restored",
        "test_slot_changed_before_deploy_seal_cannot_pass",
        "test_slot_changed_before_restore_seal_cannot_pass",
    )
    suite = unittest.TestSuite([
        unittest.defaultTestLoader.loadTestsFromTestCase(test_nlink_guard.NlinkGuardTests),
        unittest.TestSuite(test_transaction.TransactionTests(name) for name in selected_core),
        unittest.defaultTestLoader.loadTestsFromTestCase(test_transaction.GuardNormalizationTests),
    ])
    cases = []
    class Results(unittest.TextTestResult):
        def startTest(self, test):
            self.began = time.monotonic(); super().startTest(test)
        def record(self, test, outcome, detail=None):
            cases.append({"test": test.id(), "outcome": outcome,
                          "seconds": time.monotonic() - self.began, "detail": detail})
        def addSuccess(self, test):
            self.record(test, "passed"); super().addSuccess(test)
        def addFailure(self, test, err):
            self.record(test, "failed", self._exc_info_to_string(err, test)); super().addFailure(test, err)
        def addError(self, test, err):
            self.record(test, "error", self._exc_info_to_string(err, test)); super().addError(test, err)
    result = unittest.TextTestRunner(verbosity=2, resultclass=Results).run(suite)
    after = identities(source_paths)
    inputs_after = identities([args.original, args.candidate])
    report = {"tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "successful": result.wasSuccessful() and before == after and inputs_before == inputs_after,
              "cases": cases, "sources_before": before, "sources_after": after,
              "inputs_before": inputs_before, "inputs_after": inputs_after,
              "limits": "Native static operations on fresh disposable replicas only. The new full roundtrip uses the actual production normalization, sealed ownership ledger and bound-parent validation with a native disposable inventory collector. Actual product dependency reads/admission are not mocked into production authority. Synthetic snapshot mutations are labeled. No Wine/game/companion/launcher execution or protected product mutation."}
    (args.output / "RESULTS.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("tests_run", "failures", "errors", "successful")}, indent=2))
    return 0 if report["successful"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
