"""Focused staging-directory regressions using native disposable APFS replicas.

The replica collector supplies only disposable product inventory to the production
normalizer and sealed temporary-ledger reader. Copy, metadata, signature, intent,
rename, restoration and guard callbacks use the actual reviewed implementation.
No protected-product admission or production mutation is available in this test.
"""
import copy
import ctypes
import importlib.util
import json
import os
from pathlib import Path
import pwd
import stat
import subprocess
import sys
import unittest
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("nlink_transaction", ROOT / "transaction.py")
core = importlib.util.module_from_spec(spec); spec.loader.exec_module(core)
sys.modules["transaction"] = core
spec = importlib.util.spec_from_file_location("nlink_guard", ROOT / "protected_guard.py")
adapter = importlib.util.module_from_spec(spec); spec.loader.exec_module(adapter)
ORIGINAL = Path(os.environ["YAAGL_TEST_ORIGINAL"])
CANDIDATE = Path(os.environ["YAAGL_TEST_CANDIDATE"])
OUTPUT = Path(os.environ["YAAGL_TEST_OUTPUT"])


class ReplicaGuard:
    """Production normalization/ledger, native inventory of a disposable slot.

    This deliberately does not fake the parent nlink or size. Their changing
    native values are what exposed the original production-guard mismatch.
    """
    def __init__(self, root):
        self.root = root
        self.runtime = root / "runtime"
        self.mutate_snapshot = None
        self.observations = []
        self.initial_snapshot = self.snapshot()
        self.expected = adapter.normalize(self.initial_snapshot, root.name)
        self.bound_verifications = []

    def snapshot(self):
        parent = self.runtime
        fd = core._open_parent(parent / "entry")
        try:
            before = core.stat_record(os.fstat(fd))
            entry = {"kind": "directory", "stat": before,
                     "xattrs": core._xattrs_fd(fd), "acl": core._acl_fd(fd, parent)}
            tree = {adapter.PARENT_RELATIVE: entry}
            for name in sorted(os.listdir(fd)):
                path = parent / name
                child = os.stat(name, dir_fd=fd, follow_symlinks=False)
                core.require(stat.S_ISREG(child.st_mode), "Replica inventory rejects nonregular entry")
                record = core.inspect_file(path, signature=name != "baseline.dll")
                record.pop("access_time_ns_before_read", None)
                tree[adapter.PARENT_RELATIVE + "/" + name] = record
            core.require(core.stat_record(os.fstat(fd)) == before == core.stat_record(parent.stat()),
                         "Replica parent changed during bound inventory")
        finally:
            os.close(fd)
        return {"runtime_tree": tree, "configuration": {"target": 160, "enabled": True},
                "unrelated_product_marker": "constant replica fixture, not a production snapshot"}

    def __call__(self):
        snapshot = self.snapshot()
        if self.mutate_snapshot:
            self.mutate_snapshot(snapshot)
        owned = adapter.owned_temporary_records(self.root)
        normalized = adapter.normalize(snapshot, self.root.name, owned)
        self.observations.append({"owned_phases": sorted(owned),
                                  "parent": copy.deepcopy(snapshot["runtime_tree"][adapter.PARENT_RELATIVE]),
                                  "names": sorted(snapshot["runtime_tree"]),
                                  "normalized_matches": normalized == self.expected})
        core.require(normalized == self.expected, "Replica protected-product comparison failed")
        return normalized

    def verify_bound_parent(self, descriptor):
        owned = adapter.owned_temporary_records(self.root)
        adapter.verify_parent_snapshot(descriptor, self.runtime, self.initial_snapshot,
                                       owned, self.initial_snapshot["runtime_tree"][adapter.PARENT_RELATIVE]["acl"])
        self.bound_verifications.append({"owned_phases": sorted(owned),
                                         "parent": core.stat_record(os.fstat(descriptor))})


class NlinkGuardTests(unittest.TestCase):
    def setUp(self):
        self.root = OUTPUT / self._testMethodName
        core.create_replica(self.root, ORIGINAL, CANDIDATE)
        (self.root / "runtime" / "baseline.dll").write_bytes(b"preserved unrelated replica entry")
        self.guard = ReplicaGuard(self.root)
        self.tx = core.RuntimeTransaction(self.root, protected_guard=self.guard)
        self.before = core.inspect_file(self.tx.slot)
        self.notes = {"runtime_executed": False, "production_mutated": False,
                      "collector": "native disposable descriptor-bound directory inventory",
                      "guard": "actual production normalize and owned_temporary_records"}

    def tearDown(self):
        self.notes["observations"] = self.guard.observations
        self.notes["bound_verifications"] = self.guard.bound_verifications
        self.notes["journal"] = sorted(p.name for p in self.tx.journal.iterdir())
        (self.root / "TEST-EVIDENCE.json").write_text(json.dumps(self.notes, indent=2) + "\n")

    def prepare(self):
        self.tx.prepare()
        self.assertEqual(self.tx.slot.stat().st_ino, self.before["stat"]["ino"])

    def temp(self, phase="deploy"):
        return self.tx.slot.parent / (".ntdll-" + self.root.name + "-" + phase + ".tmp")

    def refuse_before_install(self, action):
        with self.assertRaises((core.Stop, OSError)) as caught:
            action()
        self.notes["refusal"] = str(caught.exception)
        core.same_instance(self.before, core.inspect_file(self.tx.slot))
        self.assertFalse((self.tx.journal / "deploy-intent.json").exists())

    def test_native_staging_delta_and_complete_guarded_roundtrip(self):
        initial_parent = self.tx.slot.parent.stat()
        self.prepare()
        backup = core.inspect_file(self.tx.rollback)
        deployed = self.tx.deploy()
        self.assertEqual(deployed["sha256"], core.CANDIDATE)
        self.assertTrue(deployed["signature"]["verified"])
        self.assertFalse(self.temp().exists())
        self.assertEqual(self.tx.slot.parent.stat().st_nlink, initial_parent.st_nlink)
        restored = core.RuntimeTransaction(self.root, protected_guard=self.guard).restore()
        self.assertEqual(restored["sha256"], core.ORIGINAL)
        self.assertTrue(restored["signature"]["verified"])
        core.required_metadata(self.before, restored)
        self.assertFalse(self.temp("restore").exists())
        self.assertEqual(self.tx.slot.parent.stat().st_nlink, initial_parent.st_nlink)
        for phase in ("deploy", "restore"):
            staging = [r for r in self.guard.observations if r["owned_phases"] == [phase]]
            self.assertTrue(staging, "Real guarded staging callback was not exercised")
            self.assertTrue(all(r["parent"]["stat"]["nlink"] == initial_parent.st_nlink + 1 for r in staging))
            self.assertTrue(all(r["parent"]["stat"]["size"] == initial_parent.st_size + 32 for r in staging))
            self.assertTrue(all(r["normalized_matches"] for r in staging))
            bound = [r for r in self.guard.bound_verifications if r["owned_phases"] == [phase]]
            self.assertTrue(bound, "Real bound-parent guard before atomic replacement was not exercised")
        self.assertNotEqual(self.before["stat"]["ino"], backup["stat"]["ino"])
        self.assertEqual(self.tx.status()["state"], "RESTORED")
        self.notes["roundtrip"] = {"original": self.before, "rollback": backup,
                                   "deployed": deployed, "restored": restored}

    def test_owned_temporary_missing_before_intent_is_refused(self):
        self.prepare()
        def remove(event, tx):
            if event == "before-deploy-intent": self.temp().unlink()
        self.tx.hook = remove
        self.refuse_before_install(self.tx.deploy)

    def test_foreign_additional_regular_file_remains_visible(self):
        self.prepare()
        def add(event, tx):
            if event == "before-deploy-intent":
                core._copy_exclusive(tx.candidate, tx.slot.parent / "foreign.so", 15)
        self.tx.hook = add
        self.refuse_before_install(self.tx.deploy)
        raw = self.guard.snapshot()
        normalized = adapter.normalize(raw, self.root.name, adapter.owned_temporary_records(self.root))
        self.assertIn(adapter.PARENT_RELATIVE + "/foreign.so", normalized["runtime_tree"])
        self.assertNotEqual(normalized, self.guard.expected)

    def test_missing_baseline_entry_is_not_hidden_by_owned_temporary(self):
        self.prepare()
        def remove(event, tx):
            if event == "before-deploy-intent": (tx.slot.parent / "baseline.dll").unlink()
        self.tx.hook = remove
        self.refuse_before_install(self.tx.deploy)

    def test_foreign_addition_cancelling_missing_baseline_count_is_refused(self):
        self.prepare()
        def cancel_count(event, tx):
            if event == "before-deploy-intent":
                (tx.slot.parent / "baseline.dll").unlink()
                core._copy_exclusive(tx.candidate, tx.slot.parent / "foreign.so", 15)
        self.tx.hook = cancel_count
        self.refuse_before_install(self.tx.deploy)
        raw = self.guard.snapshot()
        expected_stat = self.guard.initial_snapshot["runtime_tree"][adapter.PARENT_RELATIVE]["stat"]
        actual_stat = raw["runtime_tree"][adapter.PARENT_RELATIVE]["stat"]
        self.assertEqual(actual_stat["nlink"], expected_stat["nlink"] + 1)
        self.assertEqual(actual_stat["size"], expected_stat["size"] + 32)
        normalized = adapter.normalize(raw, self.root.name, adapter.owned_temporary_records(self.root))
        self.assertNotEqual(normalized, self.guard.expected)
        self.notes["attack"] = "Foreign addition cancels missing baseline directory count; full inventory still refuses"

    def test_preexisting_exact_candidate_name_is_not_owned(self):
        self.prepare()
        core._copy_exclusive(self.tx.candidate, self.temp(), 15)
        before = core.inspect_file(self.temp())
        self.refuse_before_install(self.tx.deploy)
        core.same_instance(before, core.inspect_file(self.temp()))

    def test_changed_temporary_inode_is_refused(self):
        self.prepare()
        def replace(event, tx):
            if event == "before-deploy-intent":
                self.temp().rename(self.root / "retained-real-owned.so")
                core._copy_exclusive(tx.candidate, self.temp(), 15)
        self.tx.hook = replace
        self.refuse_before_install(self.tx.deploy)
        self.assertNotEqual(self.temp().stat().st_ino, (self.root / "retained-real-owned.so").stat().st_ino)
        with self.assertRaises(core.Stop): adapter.owned_temporary_records(self.root)

    def test_parent_inode_and_device_changes_remain_visible(self):
        original = self.guard.snapshot()
        for field in ("ino", "dev"):
            with self.subTest(field=field):
                changed = copy.deepcopy(original)
                changed["runtime_tree"][adapter.PARENT_RELATIVE]["stat"][field] += 1
                self.assertNotEqual(adapter.normalize(changed, self.root.name), self.guard.expected)
        self.notes["injection"] = "Explicit snapshot inode/device mutations; actual redirection is tested separately"

    def test_parent_security_metadata_changes_remain_visible(self):
        original = self.guard.snapshot()
        for field in ("mode", "uid", "gid", "flags"):
            with self.subTest(field=field):
                changed = copy.deepcopy(original)
                changed["runtime_tree"][adapter.PARENT_RELATIVE]["stat"][field] += 1
                self.assertNotEqual(adapter.normalize(changed, self.root.name), self.guard.expected)
        for field, value in (("acl", {"state": "unexpected ACL"}),
                             ("xattrs", {"com.apple.quarantine": "unexpected"})):
            with self.subTest(field=field):
                changed = copy.deepcopy(original)
                changed["runtime_tree"][adapter.PARENT_RELATIVE][field] = value
                self.assertNotEqual(adapter.normalize(changed, self.root.name), self.guard.expected)
        self.notes["injection"] = "Snapshot-only ownership/flags/ACL/xattr mutations do not mutate OS identity"

    def test_native_bound_parent_security_drift_is_refused(self):
        parent = self.tx.slot.parent
        baseline = parent.stat()
        refused = []
        def check(label):
            fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                with self.assertRaises(core.Stop) as caught:
                    self.guard.verify_bound_parent(fd)
                refused.append({"native_mutation": label, "refusal": str(caught.exception)})
            finally:
                os.close(fd)
        os.chmod(parent, stat.S_IMODE(baseline.st_mode) ^ 0o040)
        try: check("mode")
        finally: os.chmod(parent, stat.S_IMODE(baseline.st_mode))
        os.chflags(parent, baseline.st_flags ^ stat.UF_HIDDEN)
        try: check("flags")
        finally: os.chflags(parent, baseline.st_flags)
        libc = ctypes.CDLL(None, use_errno=True)
        libc.fsetxattr.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.c_uint32, ctypes.c_int]
        libc.fremovexattr.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        name = b"org.yaagl.nlink-parent-test"
        try:
            value = ctypes.create_string_buffer(b"required control")
            self.assertEqual(libc.fsetxattr(fd, name, value, 16, 0, 0), 0)
            try: check("extra xattr")
            finally: self.assertEqual(libc.fremovexattr(fd, name, 0), 0)
        finally:
            os.close(fd)
        self.assertEqual(self.guard.initial_snapshot["runtime_tree"][adapter.PARENT_RELATIVE]["acl"]["state"], "absent")
        subprocess.run(["/bin/chmod", "+a", "user:" + pwd.getpwuid(os.getuid()).pw_name + " allow read", str(parent)],
                       check=True, capture_output=True)
        try: check("actual ACL entry")
        finally: subprocess.run(["/bin/chmod", "-N", str(parent)], check=True, capture_output=True)
        fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: self.guard.verify_bound_parent(fd)
        finally: os.close(fd)
        self.notes["native_bound_parent_security_checks"] = refused

    def test_unexpected_staging_nlink_delta_is_refused(self):
        self.prepare()
        def extra_delta(snapshot):
            if self.temp().exists(): snapshot["runtime_tree"][adapter.PARENT_RELATIVE]["stat"]["nlink"] += 1
        self.guard.mutate_snapshot = extra_delta
        self.refuse_before_install(self.tx.deploy)
        self.notes["injection"] = "Add one synthetic parent link beyond the real native owned +1"

    def test_staging_nlink_without_the_proven_increment_is_refused(self):
        self.prepare()
        def missing_delta(snapshot):
            if self.temp().exists(): snapshot["runtime_tree"][adapter.PARENT_RELATIVE]["stat"]["nlink"] -= 1
        self.guard.mutate_snapshot = missing_delta
        self.refuse_before_install(self.tx.deploy)
        self.notes["injection"] = "Remove native owned +1 from captured staging stat"

    def test_unexplained_post_replacement_nlink_drift_stops_and_recovers(self):
        self.prepare()
        def after_replace(event, tx):
            if event == "after-deploy-replace":
                def drift(snapshot): snapshot["runtime_tree"][adapter.PARENT_RELATIVE]["stat"]["nlink"] += 1
                self.guard.mutate_snapshot = drift
        self.tx.hook = after_replace
        with self.assertRaisesRegex(core.Stop, "Replica protected-product comparison failed"):
            self.tx.deploy()
        self.assertFalse((self.tx.journal / "deploy-complete.json").exists())
        self.assertEqual(core.inspect_file(self.tx.slot)["sha256"], core.CANDIDATE)
        self.assertFalse(self.temp().exists())
        self.guard.mutate_snapshot = None
        restored = core.RuntimeTransaction(self.root, protected_guard=self.guard).restore()
        self.assertEqual(restored["sha256"], core.ORIGINAL)
        self.notes["injection"] = "Post-replacement snapshot nlink fault; restore uses real durable intent and guard"

    def test_foreign_entry_at_bound_parent_recheck_stops_before_replace(self):
        self.prepare()
        actual_bound = self.guard.verify_bound_parent
        injected = False
        def add_late(descriptor):
            nonlocal injected
            if not injected:
                injected = True
                core._copy_exclusive(self.tx.candidate, self.tx.slot.parent / "late-foreign.so", 15)
            return actual_bound(descriptor)
        self.guard.verify_bound_parent = add_late
        with self.assertRaises((core.Stop, OSError)) as caught: self.tx.deploy()
        self.assertTrue(injected, "Bound-parent validation boundary was not exercised")
        self.assertTrue((self.tx.journal / "deploy-intent.json").exists())
        self.assertFalse((self.tx.journal / "deploy-complete.json").exists())
        core.same_instance(self.before, core.inspect_file(self.tx.slot))
        self.notes["refusal"] = str(caught.exception)
        self.notes["attack"] = "Actual foreign native copy between full snapshot guard and bound parent check"


if __name__ == "__main__":
    unittest.main(verbosity=2)
