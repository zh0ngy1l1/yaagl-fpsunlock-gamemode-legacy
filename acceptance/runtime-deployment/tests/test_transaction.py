"""Adversarial tests of the actual transaction core, on disposable copies only.

The runner supplies three explicit staging paths. No test opens the installed
runtime or the stopped deployment transaction for mutation.
"""
import copy
import ctypes
import hashlib
import importlib.util
import json
import os
import pwd
from pathlib import Path
import stat
import subprocess
import sys
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True

CORE_PATH = Path(__file__).resolve().parents[1] / "transaction.py"
spec = importlib.util.spec_from_file_location("reviewed_runtime_transaction", CORE_PATH)
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)
ORIGINAL = Path(os.environ["YAAGL_TEST_ORIGINAL"])
CANDIDATE = Path(os.environ["YAAGL_TEST_CANDIDATE"])
OUTPUT = Path(os.environ["YAAGL_TEST_OUTPUT"])


def load_guard():
    sys.modules["transaction"] = core
    path = CORE_PATH.with_name("protected_guard.py")
    spec = importlib.util.spec_from_file_location("reviewed_protected_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def set_xattr(path, name, value):
    """Test-only native setter, restricted to a disposable test output root."""
    path = Path(path)
    if not path.is_relative_to(OUTPUT) or path.is_symlink():
        raise AssertionError("Test mutation outside disposable output")
    libc = ctypes.CDLL(None, use_errno=True)
    libc.fsetxattr.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p,
                              ctypes.c_size_t, ctypes.c_uint32, ctypes.c_int]
    libc.fsetxattr.restype = ctypes.c_int
    fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
    try:
        buf = ctypes.create_string_buffer(value)
        if libc.fsetxattr(fd, name.encode(), buf, len(value), 0, 0):
            raise OSError(ctypes.get_errno(), "Test fsetxattr failed")
    finally:
        os.close(fd)


class SimulatedInterruption(BaseException):
    pass


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.root = OUTPUT / self._testMethodName
        self.tx = core.create_replica(self.root, ORIGINAL, CANDIDATE)
        self.notes = {"root": str(self.root), "real_core": str(CORE_PATH),
                      "runtime_executed": False, "production_mutated": False}
        self.frozen_inputs = {str(p): digest(p) for p in (ORIGINAL, CANDIDATE)}

    def tearDown(self):
        for path, expected in self.frozen_inputs.items():
            self.assertEqual(digest(path), expected, "Frozen staging input changed")
        self.notes["journal"] = sorted(p.name for p in self.tx.journal.iterdir())
        self.notes["slot_hash"] = digest(self.tx.slot) if self.tx.slot.is_file() else None
        (self.root / "test-evidence.json").write_text(json.dumps(self.notes, indent=2) + "\n")

    def assert_refused(self, action, phrase=None):
        with self.assertRaises(core.Stop) as caught:
            action()
        if phrase:
            self.assertIn(phrase, str(caught.exception))
        self.notes.setdefault("refusals", []).append(str(caught.exception))

    def prepare(self):
        self.tx.prepare()
        self.assertEqual(digest(self.tx.slot), core.ORIGINAL)
        self.assertEqual(digest(self.tx.rollback), core.ORIGINAL)
        self.assertNotEqual(self.tx.slot.stat().st_ino, self.tx.rollback.stat().st_ino)

    def complete_roundtrip(self):
        before = core.inspect_file(self.tx.slot)
        self.prepare()
        installed = self.tx.deploy()
        self.assertEqual(installed["sha256"], core.CANDIDATE)
        self.assertTrue(installed["signature"]["verified"])
        self.assertEqual(self.tx.status()["state"], "DEPLOYED")
        restored = core.RuntimeTransaction(self.root).restore()
        self.assertEqual(restored["sha256"], core.ORIGINAL)
        self.assertTrue(restored["signature"]["verified"])
        self.assertEqual(self.tx.status()["state"], "RESTORED")
        core.required_metadata(before, restored)
        self.assertNotEqual(before["stat"]["ino"], restored["stat"]["ino"])
        self.notes["roundtrip"] = {"before": before, "deployed": installed, "restored": restored,
                                   "same_deploy_restore_core": True,
                                   "required_metadata_verified": True}

    def test_fresh_roundtrip_one(self):
        self.complete_roundtrip()

    def test_fresh_roundtrip_two_with_required_xattr(self):
        for path in (self.tx.original, self.tx.slot):
            set_xattr(path, "com.yaagl.metadata-test", b"must survive deployment and restoration")
        self.complete_roundtrip()

    def test_fresh_roundtrip_three_with_acl_entry(self):
        username = pwd.getpwuid(os.getuid()).pw_name
        for path in (self.tx.original, self.tx.slot):
            subprocess.run(["/bin/chmod", "+a", f"user:{username} allow read", str(path)],
                           check=True, capture_output=True)
        self.assertEqual(core.inspect_file(self.tx.slot)["acl"]["state"], "present")
        self.complete_roundtrip()

    def test_wrong_original_hash(self):
        self.tx.slot.write_bytes(self.tx.slot.read_bytes()[:-1] + b"x")
        bad = digest(self.tx.slot)
        self.assert_refused(self.tx.prepare)
        self.assertEqual(digest(self.tx.slot), bad)

    def test_wrong_candidate_hash(self):
        self.tx.candidate.write_bytes(self.tx.candidate.read_bytes()[:-1] + b"x")
        self.assert_refused(self.tx.prepare)
        self.assertEqual(digest(self.tx.slot), core.ORIGINAL)

    def test_differently_signed_valid_candidate(self):
        subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", "--identifier",
                        "yaagl.disposable.alternate-signature", "--timestamp=none", str(self.tx.candidate)],
                       check=True, capture_output=True)
        subprocess.run(["/usr/bin/codesign", "--verify", "--strict", str(self.tx.candidate)],
                       check=True, capture_output=True)
        self.assertNotEqual(digest(self.tx.candidate), core.CANDIDATE)
        self.assert_refused(self.tx.prepare)
        self.assertEqual(digest(self.tx.slot), core.ORIGINAL)

    def test_already_patched_slot(self):
        self.tx.slot.write_bytes(self.tx.candidate.read_bytes())
        self.assert_refused(self.tx.prepare)
        self.assertEqual(digest(self.tx.slot), core.CANDIDATE)

    def test_wrong_rollback_hash(self):
        self.prepare()
        self.tx.rollback.write_bytes(self.tx.candidate.read_bytes())
        self.assert_refused(self.tx.deploy)
        self.assertEqual(digest(self.tx.slot), core.ORIGINAL)

    def test_truncated_rollback(self):
        self.prepare()
        self.tx.rollback.write_bytes(self.tx.rollback.read_bytes()[:-1])
        self.assert_refused(self.tx.deploy)
        self.assertEqual(digest(self.tx.slot), core.ORIGINAL)

    def test_third_identity_is_not_restored_over(self):
        self.prepare(); self.tx.deploy()
        self.tx.slot.write_bytes(b"unrecognized replacement; retain this evidence")
        third = digest(self.tx.slot)
        self.assert_refused(self.tx.restore)
        self.assertEqual(digest(self.tx.slot), third)

    def test_symlink_slot_preserves_outside_sentinel(self):
        sentinel = OUTPUT / (self._testMethodName + "-outside-sentinel")
        sentinel.write_bytes(b"must remain unchanged")
        old = digest(sentinel)
        self.tx.slot.unlink(); self.tx.slot.symlink_to(sentinel)
        self.assert_refused(self.tx.prepare, "Symlink")
        self.assertEqual(digest(sentinel), old)

    def test_hardlinked_rollback_is_rejected(self):
        self.prepare()
        os.link(self.tx.rollback, self.root / "extra-rollback-link")
        self.assert_refused(self.tx.deploy)
        self.assertEqual(digest(self.tx.slot), core.ORIGINAL)

    def test_mode_changed_after_pin(self):
        self.prepare(); self.tx.slot.chmod(0o600)
        self.assert_refused(self.tx.deploy)

    def test_flags_changed_after_pin(self):
        self.prepare(); os.chflags(self.tx.slot, self.tx.slot.stat().st_flags | stat.UF_HIDDEN)
        self.assert_refused(self.tx.deploy)

    def test_owner_changed_snapshot_is_rejected(self):
        self.prepare()
        actual_inspect = core.inspect_file
        def different_owner(path, *args, **kwargs):
            result = actual_inspect(path, *args, **kwargs)
            if Path(path) == self.tx.slot:
                result["stat"]["uid"] += 1
            return result
        self.notes["owner_case"] = "Snapshot fault injection; no privileged chown attempted"
        with patch.object(core, "inspect_file", different_owner):
            self.assert_refused(self.tx.deploy)

    def test_unexpected_acl_is_rejected(self):
        self.prepare()
        username = pwd.getpwuid(os.getuid()).pw_name
        subprocess.run(["/bin/chmod", "+a", f"user:{username} allow read", str(self.tx.slot)],
                       check=True, capture_output=True)
        self.assert_refused(self.tx.deploy)

    def test_allocated_empty_acl_is_distinct_from_absence(self):
        actual = core.inspect_file(self.tx.slot)
        self.assertEqual(actual["acl"]["state"], "absent")
        core.libc.acl_init.argtypes = [ctypes.c_int]
        core.libc.acl_init.restype = ctypes.c_void_p
        empty = core.libc.acl_init(0)
        self.assertTrue(empty)
        fd = os.open(self.tx.slot, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            with patch.object(core.libc, "acl_get_fd_np", lambda descriptor, kind: empty):
                observed = core._acl_fd(fd, self.tx.slot)
        finally:
            os.close(fd)  # _acl_fd owns and frees the returned native ACL.
        self.assertEqual(observed["state"], "present")
        self.assertNotEqual(observed, actual["acl"])
        changed = copy.deepcopy(actual); changed["acl"] = observed
        self.assert_refused(lambda: core.required_metadata(actual, changed), "ACL")
        self.notes["acl_case"] = "Native acl_init(0) object supplied by getter mock; no file ACL written"

    def test_acl_inspection_error_is_not_absence(self):
        def failed_getter(descriptor, kind):
            ctypes.set_errno(13)
            return None
        fd = os.open(self.tx.slot, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            with patch.object(core.libc, "acl_get_fd_np", failed_getter):
                self.assert_refused(lambda: core._acl_fd(fd, self.tx.slot), "ACL inspection error")
        finally:
            os.close(fd)
        self.notes["acl_case"] = "Getter error injection; EACCES is not treated as absent ACL"

    def test_missing_required_xattr_is_rejected(self):
        for path in (self.tx.original, self.tx.slot):
            set_xattr(path, "com.yaagl.metadata-test", b"required")
        self.prepare()
        subprocess.run(["/usr/bin/xattr", "-d", "com.yaagl.metadata-test", str(self.tx.rollback)],
                       check=True, capture_output=True)
        self.assert_refused(self.tx.deploy)

    def test_altered_security_xattr_is_rejected(self):
        self.prepare()
        set_xattr(self.tx.rollback, "com.apple.quarantine", b"0083;00000000;ChangedAudit;")
        self.assert_refused(self.tx.deploy)
        self.notes["security_xattr_case"] = "Real post-pin quarantine addition is rejected"

    def test_unpreserved_security_xattr_stops_rollback(self):
        set_xattr(self.tx.slot, "com.apple.quarantine", b"0081;00000000;YAAGLDisposableAudit;")
        self.assert_refused(self.tx.prepare, "Required xattr mismatch")
        self.assertEqual(digest(self.tx.slot), core.ORIGINAL)
        self.assertFalse((self.tx.journal / "01-rollback.json").exists())
        self.notes["security_xattr_case"] = {
            "source": core.inspect_file(self.tx.slot)["xattrs"],
            "copy": core.inspect_file(self.tx.rollback)["xattrs"],
            "conclusion": "Actual native copy quarantine transformation remains unsupported; never exempted with provenance"}

    def test_security_xattr_value_difference_is_not_exempted(self):
        original = core.inspect_file(self.tx.slot)
        original["xattrs"]["com.apple.quarantine"] = b"0081;00000000;Review;".hex()
        altered = copy.deepcopy(original)
        altered["xattrs"]["com.apple.quarantine"] = b"0281;00000000;Review;".hex()
        self.assert_refused(lambda: core.required_metadata(original, altered), "Required xattr mismatch")
        self.notes["security_xattr_case"] = "Captured-record value mutation; full policy checks all non-provenance xattrs"

    def test_unsupported_provenance_states(self):
        original = core.inspect_file(self.tx.slot)
        for value in (None, "", "01", "00" * 11, "010200" + "ff" * 8):
            altered = copy.deepcopy(original)
            if value is None:
                altered["xattrs"].pop(core.PROVENANCE, None)
            else:
                altered["xattrs"][core.PROVENANCE] = value
            self.assert_refused(lambda: core.required_metadata(original, altered), "provenance")
        self.notes["provenance_cases"] = "Policy snapshots; no platform-provenance setter used"

    def test_copy_pasted_allowed_provenance_after_pin_is_rejected(self):
        self.prepare(); self.tx.deploy()
        actual_inspect = core.inspect_file
        def changed_provenance(path, *args, **kwargs):
            result = actual_inspect(path, *args, **kwargs)
            if Path(path) == self.tx.slot:
                current = result["xattrs"][core.PROVENANCE]
                result["xattrs"][core.PROVENANCE] = next(v for v in core.PROVENANCE_VALUES if v != current)
            return result
        self.notes["provenance_case"] = "Post-seal snapshot substitution to another allowed opaque value"
        with patch.object(core, "inspect_file", changed_provenance):
            self.assert_refused(self.tx.restore)

    def test_original_provenance_in_new_copy_role_is_rejected(self):
        original = core.inspect_file(self.tx.slot)
        forged_copy = copy.deepcopy(original)
        forged_copy["xattrs"][core.PROVENANCE] = "010000dcd5bccdc7edc92e"
        self.assert_refused(lambda: core.required_metadata(original, forged_copy), "provenance")
        self.notes["provenance_case"] = "Captured-record wrong-role mutation; no platform setter used"

    def test_recorded_original_to_generated_copy_policy(self):
        original = core.inspect_file(self.tx.slot)
        copied = copy.deepcopy(original)
        original["xattrs"][core.PROVENANCE] = "010000dcd5bccdc7edc92e"
        copied["xattrs"][core.PROVENANCE] = "01020059c71153554e5113"
        transition = core.required_metadata(original, copied)
        self.assertTrue(transition["different"])
        self.notes["provenance_case"] = "Policy replay of recorded old0 to generated2; native fresh replicas start from generated2"

    def test_source_changes_during_verification(self):
        def mutate(event, path):
            if path == self.tx.original:
                path.chmod(0o600)
        self.assert_refused(lambda: core.inspect_file(self.tx.original, hook=mutate), "during inspection")

    def test_destination_changes_before_atomic_replace(self):
        self.prepare()
        def mutate(event, tx):
            if event == "before-deploy-replace":
                tx.slot.chmod(0o600)
        self.tx.hook = mutate
        self.assert_refused(self.tx.deploy)
        self.assertEqual(digest(self.tx.slot), core.ORIGINAL)

    def test_candidate_metadata_changed_after_initial_verification(self):
        self.prepare()
        def mutate(event, tx):
            if event == "before-deploy-copy":
                tx.candidate.chmod(0o600)
        self.tx.hook = mutate
        self.assert_refused(self.tx.deploy)
        self.assertEqual(digest(self.tx.slot), core.ORIGINAL)

    def test_existing_temporary_collision_is_preserved(self):
        self.prepare()
        temporary = self.tx.slot.parent / (".ntdll-" + self.root.name + "-deploy.tmp")
        temporary.write_bytes(b"unrelated existing temporary")
        before = digest(temporary)
        self.assert_refused(self.tx.deploy, "collision")
        self.assertEqual(digest(temporary), before)
        self.assertEqual(digest(self.tx.slot), core.ORIGINAL)

    def test_cross_filesystem_assumption_is_rejected(self):
        self.prepare()
        actual_inspect = core.inspect_file
        actual_copy_metadata = core._copy_metadata
        after_metadata = False
        def copied_metadata(*args, **kwargs):
            nonlocal after_metadata
            result = actual_copy_metadata(*args, **kwargs)
            after_metadata = True
            return result
        def different_device(path, *args, **kwargs):
            result = actual_inspect(path, *args, **kwargs)
            if after_metadata and Path(path).name.endswith("-deploy.tmp"):
                result["stat"]["dev"] += 1
            return result
        self.notes["filesystem_case"] = "Explicit snapshot device fault injection; no volume mounted"
        with patch.object(core, "inspect_file", different_device), \
                patch.object(core, "_copy_metadata", copied_metadata):
            self.assert_refused(self.tx.deploy, "same filesystem")
        self.assertEqual(digest(self.tx.slot), core.ORIGINAL)

    def test_late_copy_parent_swap_cannot_write_outside_case(self):
        self.prepare()
        runtime_parent = self.tx.slot.parent
        moved_parent = self.root / "bound-runtime-moved"
        outside = OUTPUT / (self._testMethodName + "-outside")
        outside.mkdir(mode=0o700)
        sentinel = outside / "sentinel"
        sentinel.write_bytes(b"outside the transaction root; inside disposable test output")
        before = {p.name: digest(p) for p in outside.iterdir()}
        actual_open = core.os.open
        injected = False
        expected_name = ".ntdll-" + self.root.name + "-deploy.tmp"
        def swap_parent_at_creation(path, flags, *args, **kwargs):
            nonlocal injected
            if not injected and flags & os.O_CREAT and Path(path).name == expected_name:
                injected = True
                runtime_parent.rename(moved_parent)
                runtime_parent.symlink_to(outside, target_is_directory=True)
            return actual_open(path, flags, *args, **kwargs)
        try:
            with patch.object(core.os, "open", swap_parent_at_creation):
                with self.assertRaises((core.Stop, OSError)) as caught:
                    self.tx.deploy()
                self.notes.setdefault("refusals", []).append(str(caught.exception))
        finally:
            if runtime_parent.is_symlink():
                runtime_parent.unlink()
                moved_parent.rename(runtime_parent)
        self.assertTrue(injected, "Late native open boundary was not exercised")
        self.assertEqual({p.name: digest(p) for p in outside.iterdir()}, before,
                         "Late parent replacement escaped the bound transaction directory")
        self.assertEqual(digest(self.tx.slot), core.ORIGINAL)
        self.notes["race_case"] = "Actual parent rename/symlink at native O_CREAT boundary; all paths disposable"

    def test_regular_parent_replacement_cannot_be_newly_enrolled(self):
        self.prepare()
        runtime = self.tx.slot.parent
        saved = self.root / "admitted-runtime-saved"
        rejected = self.root / "untrusted-runtime-retained"
        actual_parent = core._open_parent
        injected = False
        def replace_regular_parent(path, *args, **kwargs):
            nonlocal injected
            if not injected and Path(path).parent == runtime:
                injected = True
                runtime.rename(saved)
                runtime.mkdir(mode=0o700)
                (runtime / "sentinel").write_bytes(b"not the admitted directory")
            return actual_parent(path, *args, **kwargs)
        try:
            with patch.object(core, "_open_parent", replace_regular_parent):
                self.assert_refused(self.tx.deploy)
            self.assertEqual(sorted(p.name for p in runtime.iterdir()), ["sentinel"],
                             "A replacement parent was adopted before copying")
        finally:
            if injected:
                runtime.rename(rejected)
                saved.rename(runtime)
        self.assertTrue(injected)
        self.assertEqual(digest(self.tx.slot), core.ORIGINAL)
        self.notes["race_case"] = "Actual regular-directory replacement immediately before admitted parent open"

    def test_late_replace_parent_swap_stays_bound_and_recovers(self):
        self.prepare()
        runtime = self.tx.slot.parent
        saved = self.root / "runtime-held-during-replace"
        outside = OUTPUT / (self._testMethodName + "-outside")
        outside.mkdir(mode=0o700)
        sentinel = outside / "ntdll.so"
        sentinel.write_bytes(b"outside sentinel must not receive atomic replacement")
        before = {p.name: digest(p) for p in outside.iterdir()}
        actual_replace = core.os.replace
        injected = False
        expected_name = ".ntdll-" + self.root.name + "-deploy.tmp"
        def swap_parent_at_replace(source, destination, *args, **kwargs):
            nonlocal injected
            if not injected and Path(source).name == expected_name:
                injected = True
                runtime.rename(saved)
                runtime.symlink_to(outside, target_is_directory=True)
            return actual_replace(source, destination, *args, **kwargs)
        try:
            with patch.object(core.os, "replace", swap_parent_at_replace):
                with self.assertRaises((core.Stop, OSError)) as caught:
                    self.tx.deploy()
                self.notes.setdefault("refusals", []).append(str(caught.exception))
        finally:
            if runtime.is_symlink():
                runtime.unlink(); saved.rename(runtime)
        self.assertTrue(injected)
        self.assertEqual({p.name: digest(p) for p in outside.iterdir()}, before)
        self.assertEqual(digest(self.tx.slot), core.CANDIDATE)
        self.assertEqual(core.RuntimeTransaction(self.root).restore()["sha256"], core.ORIGINAL)
        self.notes["race_case"] = "Actual parent rename/symlink at native replace boundary; pinned dirfd confines replacement"

    def test_preexisting_exact_restore_temporary_is_not_owned(self):
        temp = self.tx.slot.parent / (".ntdll-" + self.root.name + "-restore.tmp")
        core._copy_exclusive(self.tx.slot, temp, 15)
        before = core.inspect_file(temp)
        self.assert_refused(self.tx.prepare)
        core.same_instance(before, core.inspect_file(temp))
        self.assertEqual(digest(self.tx.slot), core.ORIGINAL)

    def test_closed_idempotent_restoration_cannot_redeploy(self):
        self.prepare()
        restored = self.tx.restore()
        self.assertEqual(restored["sha256"], core.ORIGINAL)
        self.assert_refused(self.tx.deploy)
        self.assertEqual(digest(self.tx.slot), core.ORIGINAL)

    def test_shared_core_temporary_ledger_tracks_phases(self):
        guard = load_guard()
        observed = []
        self.assertEqual(guard.allowed_temporary_phases(self.root), frozenset())
        self.prepare()
        def inspect_phase(event, tx):
            if event in ("before-deploy-intent", "before-restore-intent"):
                phase = event.split("-")[1]
                allowed = guard.allowed_temporary_phases(self.root)
                self.assertEqual(allowed, frozenset({phase}))
                observed.append({"event": event, "allowed": sorted(allowed)})
        self.tx.hook = inspect_phase
        self.tx.deploy()
        self.assertEqual(guard.allowed_temporary_phases(self.root), frozenset())
        restored = core.RuntimeTransaction(self.root, hook=inspect_phase).restore()
        self.assertEqual(restored["sha256"], core.ORIGINAL)
        self.assertEqual(guard.allowed_temporary_phases(self.root), frozenset())
        self.assertEqual(len(observed), 2)
        self.notes["stage_ledger"] = observed

    def test_external_same_hash_original_cannot_claim_restoration(self):
        self.prepare()
        replacement = self.root / "external-original.so"
        core._copy_exclusive(self.tx.slot, replacement, 15)
        self.assertNotEqual(replacement.stat().st_ino, self.tx.slot.stat().st_ino)
        os.replace(replacement, self.tx.slot)
        self.assertEqual(digest(self.tx.slot), core.ORIGINAL)
        inode = self.tx.slot.stat().st_ino
        self.assert_refused(self.tx.restore)
        self.assertEqual(self.tx.slot.stat().st_ino, inode)
        self.assertFalse((self.tx.journal / "restored-idempotent.json").exists())

    def test_failure_after_replace_recovers_through_same_core(self):
        self.prepare()
        def fail(event, tx):
            if event == "after-deploy-replace":
                raise core.Stop("Injected post-replacement verification failure")
        self.tx.hook = fail
        self.assert_refused(self.tx.deploy, "Injected")
        self.assertEqual(digest(self.tx.slot), core.CANDIDATE)
        recovered = core.RuntimeTransaction(self.root)
        self.assertEqual(recovered.status()["state"], "INTERRUPTED_REQUIRES_EXPLICIT_RECOVERY")
        self.assertEqual(recovered.restore()["sha256"], core.ORIGINAL)

    def test_interruption_after_replace_has_durable_recovery(self):
        self.prepare()
        def interrupt(event, tx):
            if event == "after-deploy-replace":
                raise SimulatedInterruption("Process interrupted before deployment seal")
        self.tx.hook = interrupt
        with self.assertRaises(SimulatedInterruption):
            self.tx.deploy()
        recovered = core.RuntimeTransaction(self.root)
        self.assertEqual(recovered.status()["state"], "INTERRUPTED_REQUIRES_EXPLICIT_RECOVERY")
        self.assertEqual(recovered.restore()["sha256"], core.ORIGINAL)

    def abrupt_child_after_replace(self, phase):
        script = '''import importlib.util,os,sys
from pathlib import Path
sys.dont_write_bytecode=True
s=importlib.util.spec_from_file_location("transaction_child",sys.argv[1])
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
phase=sys.argv[3]
def interrupt(event,tx):
    if event=="after-"+phase+"-replace":os._exit(77)
tx=m.RuntimeTransaction(Path(sys.argv[2]),hook=interrupt)
getattr(tx,phase)()
raise RuntimeError("Required abrupt-exit boundary was not reached")
'''
        result = subprocess.run([sys.executable, "-c", script, str(CORE_PATH), str(self.root), phase],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 77, result.stderr)
        self.notes["interruption"] = {"method": "os._exit(77) in native Python child after atomic replacement",
                                      "phase": phase, "child_exit": result.returncode,
                                      "wine_or_runtime_loaded": False}

    def test_process_exit_after_deploy_replace_recovers(self):
        self.prepare()
        self.abrupt_child_after_replace("deploy")
        self.assertEqual(digest(self.tx.slot), core.CANDIDATE)
        recovered = core.RuntimeTransaction(self.root)
        self.assertEqual(recovered.status()["state"], "INTERRUPTED_REQUIRES_EXPLICIT_RECOVERY")
        self.assertEqual(recovered.restore()["sha256"], core.ORIGINAL)

    def test_process_exit_after_restore_replace_recovers(self):
        self.prepare(); self.tx.deploy()
        self.abrupt_child_after_replace("restore")
        self.assertEqual(digest(self.tx.slot), core.ORIGINAL)
        recovered = core.RuntimeTransaction(self.root)
        self.assertNotEqual(recovered.status()["state"], "RESTORED")
        self.assertEqual(recovered.restore()["sha256"], core.ORIGINAL)
        self.assertEqual(recovered.status()["state"], "RESTORED")

    def test_restoration_failure_cannot_seal_restored(self):
        self.prepare(); self.tx.deploy()
        def fail(event, tx):
            if event == "before-restore-replace":
                raise core.Stop("Injected restoration failure")
        self.tx.hook = fail
        self.assert_refused(self.tx.restore, "Injected")
        self.assertEqual(digest(self.tx.slot), core.CANDIDATE)
        self.assertFalse((self.tx.journal / "restore-complete.json").exists())

    def test_interruption_after_restore_replace_requires_verified_recovery(self):
        self.prepare(); self.tx.deploy()
        def interrupt(event, tx):
            if event == "after-restore-replace":
                raise SimulatedInterruption("Interrupted before restoration seal")
        self.tx.hook = interrupt
        with self.assertRaises(SimulatedInterruption):
            self.tx.restore()
        self.assertEqual(digest(self.tx.slot), core.ORIGINAL)
        recovered = core.RuntimeTransaction(self.root)
        self.assertNotEqual(recovered.status()["state"], "RESTORED")
        self.assertEqual(recovered.restore()["sha256"], core.ORIGINAL)
        self.assertEqual(recovered.status()["state"], "RESTORED")

    def test_slot_changed_before_deploy_seal_cannot_pass(self):
        self.prepare()
        def mutate(event, tx):
            if event == "before-deploy-seal":
                tx.slot.write_bytes(b"new third identity before sealing")
        self.tx.hook = mutate
        self.assert_refused(self.tx.deploy)
        self.assertFalse((self.tx.journal / "deploy-complete.json").exists())

    def test_slot_changed_before_restore_seal_cannot_pass(self):
        self.prepare(); self.tx.deploy()
        def mutate(event, tx):
            if event == "before-restore-seal":
                tx.slot.write_bytes(b"new third identity before restoration seal")
        self.tx.hook = mutate
        self.assert_refused(self.tx.restore)
        self.assertFalse((self.tx.journal / "restore-complete.json").exists())


class GuardNormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guard = load_guard()

    def snapshot(self):
        return {"runtime_tree": {
            self.guard.LIB_RELATIVE: {"sha256": core.ORIGINAL,
                "stat": {"size": core.SIZE, "nlink": 1}},
            self.guard.PARENT_RELATIVE: {"stat": {
                "size": 128, "mtime_ns": 10, "ctime_ns": 20,
                "mode": stat.S_IFDIR | 0o755, "uid": 501, "gid": 20, "flags": 0}},
            "unrelated.dll": {"sha256": "preserved runtime component"}},
            "settings": {"target": 160, "enabled": True},
            "prefix_identity": {"dev": 1, "ino": 2}}

    def normalized(self, value, allowed_phases=frozenset()):
        return self.guard.normalize(value, "review-test-001", allowed_phases)

    def test_exact_library_delta_normalizes(self):
        before = self.snapshot(); after = copy.deepcopy(before)
        after["runtime_tree"][self.guard.LIB_RELATIVE]["sha256"] = core.CANDIDATE
        self.assertEqual(self.normalized(before), self.normalized(after))

    def test_third_library_identity_is_not_normalized(self):
        snapshot = self.snapshot()
        snapshot["runtime_tree"][self.guard.LIB_RELATIVE]["sha256"] = "unknown"
        with self.assertRaises(core.Stop): self.normalized(snapshot)

    def test_known_temporary_requires_exact_bytes_size_and_link_count(self):
        original = self.snapshot()
        name = self.guard.PARENT_RELATIVE + "/.ntdll-review-test-001-deploy.tmp"
        for field, value in (("sha256", "wrong"), ("size", core.SIZE - 1), ("nlink", 2)):
            changed = copy.deepcopy(original)
            temp = {"sha256": core.CANDIDATE, "stat": {"size": core.SIZE, "nlink": 1}}
            if field == "sha256": temp[field] = value
            else: temp["stat"][field] = value
            changed["runtime_tree"][name] = temp
            changed["runtime_tree"][self.guard.PARENT_RELATIVE]["stat"]["size"] += 32
            with self.assertRaises(core.Stop): self.normalized(changed, frozenset({"deploy"}))

    def test_exact_known_temporary_and_directory_growth_normalize(self):
        original = self.snapshot(); changed = copy.deepcopy(original)
        changed["runtime_tree"][self.guard.PARENT_RELATIVE + "/.ntdll-review-test-001-deploy.tmp"] = {
            "sha256": core.CANDIDATE, "stat": {"size": core.SIZE, "nlink": 1}}
        changed["runtime_tree"][self.guard.PARENT_RELATIVE]["stat"]["size"] += 32
        self.assertEqual(self.normalized(original), self.normalized(changed, frozenset({"deploy"})))

    def test_exact_temporary_without_phase_lineage_is_rejected(self):
        changed = self.snapshot()
        changed["runtime_tree"][self.guard.PARENT_RELATIVE + "/.ntdll-review-test-001-restore.tmp"] = {
            "sha256": core.ORIGINAL, "stat": {"size": core.SIZE, "nlink": 1}}
        changed["runtime_tree"][self.guard.PARENT_RELATIVE]["stat"]["size"] += 32
        with self.assertRaises(core.Stop): self.normalized(changed)
        with self.assertRaises(core.Stop): self.normalized(changed, frozenset({"deploy"}))

    def test_unknown_temporary_and_unrelated_component_remain_visible(self):
        original = self.snapshot()
        for name in ("unrelated.dll", self.guard.PARENT_RELATIVE + "/.ntdll-other-run-deploy.tmp"):
            changed = copy.deepcopy(original)
            changed["runtime_tree"][name] = {"sha256": core.CANDIDATE,
                                           "stat": {"size": core.SIZE, "nlink": 1}}
            self.assertNotEqual(self.normalized(original), self.normalized(changed))

    def test_settings_and_parent_security_metadata_remain_visible(self):
        original = self.snapshot()
        changed = copy.deepcopy(original); changed["settings"]["target"] = 120
        self.assertNotEqual(self.normalized(original), self.normalized(changed))
        for field in ("mode", "uid", "gid", "flags", "size"):
            changed = copy.deepcopy(original)
            changed["runtime_tree"][self.guard.PARENT_RELATIVE]["stat"][field] += 1
            self.assertNotEqual(self.normalized(original), self.normalized(changed))

    def test_only_parent_entry_timestamps_are_normalized(self):
        original = self.snapshot(); changed = copy.deepcopy(original)
        changed["runtime_tree"][self.guard.PARENT_RELATIVE]["stat"].update(mtime_ns=999, ctime_ns=999)
        self.assertEqual(self.normalized(original), self.normalized(changed))

    def test_transaction_id_cannot_expand_allowed_names(self):
        with self.assertRaises(core.Stop): self.guard.normalize(self.snapshot(), "../../other")


if __name__ == "__main__":
    unittest.main(verbosity=2)
