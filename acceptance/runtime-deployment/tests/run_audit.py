#!/usr/bin/env python3
"""Run transaction-core tests using copied artifacts and fresh disposable roots."""
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
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output
    forbidden = {"wineprefix", "hoyoplay-wines", "drive_c", "applications"}
    if not output.is_absolute() or output.exists() or output.is_symlink() or \
            forbidden.intersection(p.casefold() for p in output.parts) or \
            output.parent.resolve() != output.parent:
        raise ValueError("A fresh canonical disposable output outside product paths is required")
    output.mkdir(mode=0o700)
    os.environ["YAAGL_TEST_ORIGINAL"] = str(args.original.resolve(strict=True))
    os.environ["YAAGL_TEST_CANDIDATE"] = str(args.candidate.resolve(strict=True))
    os.environ["YAAGL_TEST_OUTPUT"] = str(output)
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root))
    source_paths = (root.parent / "transaction.py", root.parent / "protected_guard.py",
                    root / "test_transaction.py", Path(__file__).resolve())
    sources_before = {str(p): {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
                      for p in source_paths}
    cases = []
    class Results(unittest.TextTestResult):
        def startTest(self, test):
            self.began = time.monotonic()
            super().startTest(test)
        def record(self, test, outcome, detail=None):
            cases.append({"test": test.id(), "outcome": outcome,
                          "seconds": time.monotonic() - self.began, "detail": detail})
        def addSuccess(self, test):
            self.record(test, "passed"); super().addSuccess(test)
        def addFailure(self, test, err):
            self.record(test, "failed", self._exc_info_to_string(err, test)); super().addFailure(test, err)
        def addError(self, test, err):
            self.record(test, "error", self._exc_info_to_string(err, test)); super().addError(test, err)
        def addSkip(self, test, reason):
            self.record(test, "skipped", reason); super().addSkip(test, reason)
    suite = unittest.defaultTestLoader.discover(str(root), pattern="test_transaction.py")
    result = unittest.TextTestRunner(verbosity=2, resultclass=Results).run(suite)
    sources = {str(p): {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
               for p in source_paths}
    unchanged_sources = sources_before == sources
    report = {"tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "skips": len(result.skipped), "successful": result.wasSuccessful() and unchanged_sources, "cases": cases,
              "sources_before": sources_before, "sources": sources,
              "executed_source_files_unchanged": unchanged_sources, "output": str(output),
              "limits": "Actual transaction core and native static metadata/copy/signature operations on fresh disposable replicas. No Wine, game, companion, launcher, recovered runtime or prefix mutation. Injected OS/owner/provenance cases are labeled in individual evidence."}
    (output / "RESULTS.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("tests_run", "failures", "errors", "skips", "successful")}, indent=2))
    return 0 if report["successful"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
