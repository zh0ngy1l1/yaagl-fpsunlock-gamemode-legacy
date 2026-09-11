#!/usr/bin/env python3
"""Compile only the native collector; run only mocks and archived-file tests."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

root = Path(__file__).resolve().parent
records = []
commands = [
    ["/usr/bin/swiftc", "-O", "PassiveForeground.swift", "-o", "PassiveForeground"],
    [str(root / "PassiveForeground"), "--self-test"],
    [sys.executable, "-m", "unittest", "-v", "test_production_evidence.py"],
]
for command in commands:
    result = subprocess.run(command, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    records.append({"argv": command, "exit_code": result.returncode,
                    "stdout": result.stdout, "stderr": result.stderr})
    if result.returncode:
        break
files = {}
for name in ("PassiveForeground.swift", "PassiveForeground", "production_evidence.py",
             "test_production_evidence.py", "verify_offline.py", "README.md"):
    data = (root / name).read_bytes()
    files[name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
native_checks = None
python_methods = None
if len(records) > 1 and records[1]["exit_code"] == 0:
    native_checks = json.loads(records[1]["stdout"])["checks"]
if len(records) > 2:
    count = re.search(r"\nRan (\d+) tests? in ", records[2]["stderr"])
    if count:
        python_methods = int(count[1])
report = {"profile": "ordinary-product-observation-offline", "commands": records,
          "files": files, "success": len(records) == 3 and all(r["exit_code"] == 0 for r in records),
          "native_model_checks": native_checks, "python_test_methods": python_methods,
          "distinct_target_log_cases": 300,
          "limits": "No game, Wine, runtime candidate, live observer or screen recording executed. Target parsing is not runtime reliability evidence."}
(root / "OFFLINE-VALIDATION.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({key: report[key] for key in ("success", "native_model_checks", "python_test_methods", "distinct_target_log_cases", "limits")}, indent=2))
sys.exit(0 if report["success"] else 1)
