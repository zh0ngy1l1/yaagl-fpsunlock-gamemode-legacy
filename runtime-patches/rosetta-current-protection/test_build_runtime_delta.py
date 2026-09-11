#!/usr/bin/env python3
"""Focused offline builder tests using actual pinned Mach-O bytes, never Wine."""
import argparse
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
import build_runtime_delta as builder

RUNTIME_BYTES = None


class ImageChecks(unittest.TestCase):
    def test_maps_actual_instruction_through_macho_section(self):
        image = builder.MachO(RUNTIME_BYTES)
        self.assertEqual(image.text_offset(builder.INSTRUCTION_ADDRESS, 6), 0x66c6d)
        self.assertEqual(image.data[0x66c6d:0x66c73], builder.OLD_INSTRUCTION)
        self.assertEqual(image.signature, dict(offset=597760, size=22928, command_offset=0x890))

    def test_known_image_has_exact_load_and_calculation_changes(self):
        corrected, image, record = builder.prepare_bytes(RUNTIME_BYTES)
        self.assertEqual(builder.changed_ranges(RUNTIME_BYTES, corrected),
                         [dict(offset=0x66c6f, offset_hex='0x66c6f', span=1, before_hex='20', after_hex='34'),
                          dict(offset=0x66c78, offset_hex='0x66c78', span=12,
                               before_hex='81 e1 0f ff ff ff 83 f9 01 83 d1 00',
                               after_hex='c0 e9 04 90 90 90 90 90 90 90 90 90')])
        self.assertEqual(corrected[0x66c6d:0x66c73], builder.NEW_INSTRUCTION)
        self.assertEqual((record['old_structure_offset'], record['new_structure_offset']), (16, 36))
        self.assertEqual(corrected[0x66c78:0x66c84], builder.NEW_CALCULATION)
        self.assertEqual(record['calculation_file_offset'], 0x66c78)
        self.assertEqual(len(corrected), len(RUNTIME_BYTES))

    def test_already_patched_image_refused(self):
        corrected, _, _ = builder.prepare_bytes(RUNTIME_BYTES)
        with self.assertRaisesRegex(builder.BuildError, 'Unknown or already-patched'):
            builder.prepare_bytes(corrected)

    def test_wrong_hash_refused(self):
        changed = bytearray(RUNTIME_BYTES)
        changed[0x66c73] ^= 1
        with self.assertRaisesRegex(builder.BuildError, 'SHA-256'):
            builder.prepare_bytes(bytes(changed))

    def test_unsigned_hash_is_enforced_not_only_recorded(self):
        with patch.object(builder, 'UNSIGNED_SHA256', '0' * 64):
            with self.assertRaisesRegex(builder.BuildError, 'Unsigned output.*reviewed SHA-256'):
                builder.prepare_bytes(RUNTIME_BYTES)

    def test_wrong_calculation_address_refused(self):
        with patch.object(builder, 'CALCULATION_ADDRESS', 0x66c79):
            with self.assertRaisesRegex(builder.BuildError, 'calculation mismatch'):
                builder.prepare_bytes(RUNTIME_BYTES)

    def test_wrong_calculation_opcode_refused_by_output_hash(self):
        # SHR ECX,4 would discard modifier bits; the artifact must use SHR CL,4.
        with patch.object(builder, 'NEW_CALCULATION', bytes.fromhex('c1 e9 04') + b'\x90' * 9):
            with self.assertRaisesRegex(builder.BuildError, 'Unsigned output.*reviewed SHA-256'):
                builder.prepare_bytes(RUNTIME_BYTES)

    def test_wrong_shift_immediate_refused_by_output_hash(self):
        with patch.object(builder, 'NEW_CALCULATION', bytes.fromhex('c0 e9 03') + b'\x90' * 9):
            with self.assertRaisesRegex(builder.BuildError, 'Unsigned output.*reviewed SHA-256'):
                builder.prepare_bytes(RUNTIME_BYTES)

    def test_signer_cannot_mutate_corrected_calculation(self):
        corrected, image, _ = builder.prepare_bytes(RUNTIME_BYTES)
        changed = bytearray(corrected)
        changed[0x66c7a] = 3
        with self.assertRaisesRegex(builder.BuildError, 'corrected no-execute calculation'):
            builder.verify_signed_bytes(corrected, bytes(changed), image)

    def test_parser_rejects_wrong_architecture(self):
        changed = bytearray(RUNTIME_BYTES)
        struct.pack_into('<I', changed, 4, 0x0100000c)
        with self.assertRaisesRegex(builder.BuildError, 'x86-64'):
            builder.MachO(bytes(changed))

    def test_parser_rejects_load_command_out_of_file(self):
        changed = bytearray(RUNTIME_BYTES)
        struct.pack_into('<I', changed, 36, len(changed) * 2)
        with self.assertRaisesRegex(builder.BuildError, 'load command extent'):
            builder.MachO(bytes(changed))

    def test_parser_rejects_inconsistent_text_mapping(self):
        changed = bytearray(RUNTIME_BYTES)
        # First section's offset field; this is inside __TEXT's real LC_SEGMENT_64.
        struct.pack_into('<I', changed, 32 + 72 + 48, 0x1c41)
        with self.assertRaisesRegex(builder.BuildError, 'virtual/file mapping'):
            builder.MachO(bytes(changed))

    def test_instruction_must_fit_in_text(self):
        image = builder.MachO(RUNTIME_BYTES)
        text = next(s for s in image.sections if s['name'] == '__text')
        with self.assertRaisesRegex(builder.BuildError, 'entirely'):
            image.text_offset(text['address'] + text['size'] - 1, 6)

    def test_signer_cannot_mutate_other_code(self):
        corrected, image, _ = builder.prepare_bytes(RUNTIME_BYTES)
        changed = bytearray(corrected)
        changed[0x66c74] ^= 1
        with self.assertRaisesRegex(builder.BuildError, 'section bytes'):
            builder.verify_signed_bytes(corrected, bytes(changed), image)

    def test_signer_cannot_mutate_unrelated_load_command(self):
        corrected, image, _ = builder.prepare_bytes(RUNTIME_BYTES)
        changed = bytearray(corrected)
        # LC_UUID occupies a non-signature header range; changing its bytes is forbidden.
        at = 32
        while struct.unpack_from('<I', changed, at)[0] != 0x1b:
            at += struct.unpack_from('<I', changed, at + 4)[0]
        changed[at + 8] ^= 1
        with self.assertRaisesRegex(builder.BuildError, 'outside allowed'):
            builder.verify_signed_bytes(corrected, bytes(changed), image)


class BuilderGuards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='yaagl-runtime-builder-test-')
        self.root = Path(self.temp.name).resolve()
        self.source_dir = self.root / 'input'
        self.source_dir.mkdir()
        (self.root / 'builds').mkdir()
        self.declaration = self.root / builder.STAGING_DECLARATION
        self.declaration.write_text(json.dumps(builder.staging_declaration(self.root)))
        self.source = self.source_dir / 'ntdll.so'
        self.source.write_bytes(RUNTIME_BYTES)
        self.destination = self.root / 'builds/new-artifact'

    def tearDown(self):
        self.temp.cleanup()

    def test_wrong_input_never_reaches_signer_or_creates_output(self):
        self.source.write_bytes(b'unrecognized input')
        with patch.object(builder, 'run_codesign') as signer:
            with self.assertRaises(builder.BuildError):
                builder.build(self.root, 'new-artifact')
        signer.assert_not_called()
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.source.read_bytes(), b'unrecognized input')

    def test_existing_output_is_not_changed_or_removed(self):
        self.destination.mkdir()
        marker = self.destination / 'unrelated-user-file'
        marker.write_text('preserve me')
        with patch.object(builder, 'run_codesign') as signer:
            with self.assertRaisesRegex(builder.BuildError, 'already exists'):
                builder.build(self.root, 'new-artifact')
        signer.assert_not_called()
        self.assertEqual(marker.read_text(), 'preserve me')

    def test_output_name_cannot_escape_declared_builds(self):
        with patch.object(builder, 'run_codesign') as signer:
            with self.assertRaisesRegex(builder.BuildError, 'one simple directory component'):
                builder.build(self.root, '../input/output')
        signer.assert_not_called()
        self.assertFalse((self.source_dir / 'output').exists())
        self.assertEqual(self.source.read_bytes(), RUNTIME_BYTES)

    def test_source_file_itself_cannot_be_output(self):
        with self.assertRaises(builder.BuildError):
            builder.build(self.root, '../../input/ntdll.so')
        self.assertEqual(self.source.read_bytes(), RUNTIME_BYTES)

    def test_symlink_output_is_not_followed_or_removed(self):
        self.destination.symlink_to(self.source_dir, target_is_directory=True)
        with self.assertRaisesRegex(builder.BuildError, 'already exists'):
            builder.build(self.root, 'new-artifact')
        self.assertTrue(self.destination.is_symlink())
        self.assertEqual(self.source.read_bytes(), RUNTIME_BYTES)

    def fake_codesign(self, args):
        if '--sign' in args:
            self.assertTrue((self.destination / 'ntdll.so').is_file())
            raise builder.BuildError('injected signing failure')
        return dict(arguments=args, returncode=0, stdout='',
                    stderr='Identifier=test.preserved.identifier\nSignature=adhoc\n')

    def test_signing_failure_cleans_only_new_output(self):
        with patch.object(builder, 'run_codesign', side_effect=self.fake_codesign):
            with self.assertRaisesRegex(builder.BuildError, 'injected signing'):
                builder.build(self.root, 'new-artifact')
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.source.read_bytes(), RUNTIME_BYTES)

    def test_post_sign_validation_failure_cleans_new_output(self):
        def fake(args):
            return dict(arguments=args, returncode=0, stdout='',
                        stderr='Identifier=test.preserved.identifier\nSignature=adhoc\n')
        with patch.object(builder, 'run_codesign', side_effect=fake), \
             patch.object(builder, 'verify_signed_bytes', side_effect=builder.BuildError('injected validation failure')):
            with self.assertRaisesRegex(builder.BuildError, 'injected validation'):
                builder.build(self.root, 'new-artifact')
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.source.read_bytes(), RUNTIME_BYTES)

    def test_explicit_staging_root_is_required(self):
        with patch.object(builder, 'run_codesign') as signer:
            with self.assertRaisesRegex(builder.BuildError, 'explicit absolute'):
                builder.build(Path('relative-staging'), 'new-artifact')
        signer.assert_not_called()

    def test_missing_staging_declaration_prevents_signing(self):
        self.declaration.unlink()
        with patch.object(builder, 'run_codesign') as signer:
            with self.assertRaises(OSError):
                builder.build(self.root, 'new-artifact')
        signer.assert_not_called()
        self.assertFalse(self.destination.exists())

    def test_declaration_cannot_be_reused_for_another_root(self):
        policy = builder.staging_declaration(self.root)
        policy['root'] = str(self.root / 'other')
        self.declaration.write_text(json.dumps(policy))
        with patch.object(builder, 'run_codesign') as signer:
            with self.assertRaisesRegex(builder.BuildError, 'does not match this root'):
                builder.build(self.root, 'new-artifact')
        signer.assert_not_called()

    def test_unknown_declaration_profile_rejected(self):
        policy = builder.staging_declaration(self.root)
        policy['purpose'] = 'install-runtime'
        self.declaration.write_text(json.dumps(policy))
        with self.assertRaisesRegex(builder.BuildError, 'does not match this root'):
            builder.build(self.root, 'new-artifact')

    def test_malformed_declaration_rejected(self):
        self.declaration.write_text('not json')
        with self.assertRaisesRegex(builder.BuildError, 'declaration JSON'):
            builder.build(self.root, 'new-artifact')

    def test_symlink_declaration_rejected(self):
        copy = self.root / 'declaration-copy'
        self.declaration.rename(copy)
        self.declaration.symlink_to(copy)
        with self.assertRaisesRegex(builder.BuildError, 'regular independent file'):
            builder.build(self.root, 'new-artifact')

    def test_symlink_root_rejected(self):
        link = self.root / 'root-alias'
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(builder.BuildError, 'must not traverse symlinks'):
            builder.build(link, 'new-artifact')

    def test_symlink_input_rejected(self):
        original = self.root / 'other-copy'
        self.source.rename(original)
        self.source.symlink_to(original)
        with patch.object(builder, 'run_codesign') as signer:
            with self.assertRaisesRegex(builder.BuildError, 'copied regular file'):
                builder.build(self.root, 'new-artifact')
        signer.assert_not_called()

    def test_hardlink_input_rejected(self):
        original = self.root / 'other-copy'
        self.source.rename(original)
        os.link(original, self.source)
        with patch.object(builder, 'run_codesign') as signer:
            with self.assertRaisesRegex(builder.BuildError, 'hardlink'):
                builder.build(self.root, 'new-artifact')
        signer.assert_not_called()

    def test_fifo_input_rejected_before_read(self):
        self.source.unlink()
        os.mkfifo(self.source)
        with self.assertRaisesRegex(builder.BuildError, 'copied regular file'):
            builder.build(self.root, 'new-artifact')

    def test_symlink_builds_directory_rejected(self):
        builds = self.root / 'builds'
        actual = self.root / 'actual-builds'
        builds.rename(actual)
        builds.symlink_to(actual, target_is_directory=True)
        with self.assertRaisesRegex(builder.BuildError, 'real directories'):
            builder.build(self.root, 'new-artifact')

    def test_other_user_writable_staging_refused(self):
        self.root.chmod(0o777)
        with self.assertRaisesRegex(builder.BuildError, 'not writable by other users'):
            builder.build(self.root, 'new-artifact')

    def test_installed_location_rejected_before_filesystem_access(self):
        for location in [Path('/no-such/Applications/Test.app/staging'),
                         Path('/no-such/hoyoplay-wines/genshin/staging'),
                         Path('/no-such/wineprefix/staging')]:
            with self.subTest(location=location):
                with patch.object(builder, 'run_codesign') as signer:
                    with self.assertRaisesRegex(builder.BuildError, 'Installed application'):
                        builder.build(location, 'new-artifact')
                signer.assert_not_called()

    def test_renamed_wine_installation_marker_rejected(self):
        (self.root / 'bin').mkdir()
        (self.root / 'bin/wine').write_text('inert installation marker')
        (self.root / 'lib/wine').mkdir(parents=True)
        with self.assertRaisesRegex(builder.BuildError, 'Recognized Wine installation'):
            builder.build(self.root, 'new-artifact')

    def test_source_patch_hash_is_enforced(self):
        def fake(args):
            return dict(arguments=args, returncode=0, stdout='',
                        stderr='Identifier=test.preserved.identifier\nSignature=adhoc\n')
        with patch.object(builder, 'run_codesign', side_effect=fake) as signer, \
             patch.object(builder, 'SOURCE_PATCH_SHA256', '0' * 64):
            with self.assertRaisesRegex(builder.BuildError, 'Source correction patch.*reviewed SHA-256'):
                builder.build(self.root, 'new-artifact')
        self.assertFalse(any('--sign' in call.args[0] for call in signer.call_args_list))
        self.assertFalse(self.destination.exists())

    def test_valid_but_unreviewed_signature_is_rejected_and_cleaned(self):
        real_codesign = builder.run_codesign
        observed = {}
        def altered_signer(args):
            if '--sign' not in args:
                return real_codesign(args)
            changed_args = [*args[:-1], '--options', 'runtime', args[-1]]
            result = real_codesign(changed_args)
            artifact = self.destination / 'ntdll.so'
            real_codesign(['--verify', '--strict', '--verbose=2', str(artifact)])
            observed['valid_signature'] = True
            observed['sha256'] = builder.digest(artifact.read_bytes())
            return result
        with patch.object(builder, 'run_codesign', side_effect=altered_signer):
            with self.assertRaisesRegex(builder.BuildError, 'Signed output.*reviewed SHA-256'):
                builder.build(self.root, 'new-artifact')
        self.assertTrue(observed['valid_signature'])
        self.assertNotEqual(observed['sha256'], builder.SIGNED_SHA256)
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.source.read_bytes(), RUNTIME_BYTES)

    def test_changed_pre_sign_artifact_is_rejected_and_cleaned(self):
        real_codesign = builder.run_codesign
        def altered_signer(args):
            result = real_codesign(args)
            if '--sign' in args:
                pre_sign = self.destination / 'ntdll.pre-sign.so'
                self.assertEqual(builder.digest(pre_sign.read_bytes()), builder.UNSIGNED_SHA256)
                pre_sign.chmod(0o600)
                pre_sign.write_bytes(b'changed adjacent pre-sign artifact')
            return result
        with patch.object(builder, 'run_codesign', side_effect=altered_signer):
            with self.assertRaisesRegex(builder.BuildError, 'changed the pre-sign artifact'):
                builder.build(self.root, 'new-artifact')
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.source.read_bytes(), RUNTIME_BYTES)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staging-root', required=True, type=Path)
    parser.add_argument('--result-json', type=Path)
    args = parser.parse_args()
    copied_input, _, _ = builder.destination(args.staging_root, 'test-input-admission')
    RUNTIME_BYTES, _ = builder.read_stable_input(copied_input)
    if builder.digest(RUNTIME_BYTES) != builder.INPUT_SHA256:
        parser.error('Tests require the pinned, unmodified runtime bytes')
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(ImageChecks),
                               unittest.defaultTestLoader.loadTestsFromTestCase(BuilderGuards)])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if args.result_json:
        args.result_json.write_text(json.dumps(dict(tests=result.testsRun, failures=len(result.failures),
                                                   errors=len(result.errors), successful=result.wasSuccessful(),
                                                   input_sha256=builder.INPUT_SHA256,
                                                   scope='Offline parser, exact patch/refusal, signing boundary and cleanup tests; no Wine execution'), indent=2) + '\n')
    sys.exit(0 if result.wasSuccessful() else 1)
