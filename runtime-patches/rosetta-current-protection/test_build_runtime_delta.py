#!/usr/bin/env python3
"""Focused offline builder tests using actual pinned Mach-O bytes, never Wine."""
import argparse
import json
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

    def test_known_image_has_exact_one_byte_unsigned_change(self):
        corrected, image, record = builder.prepare_bytes(RUNTIME_BYTES)
        self.assertEqual(builder.changed_ranges(RUNTIME_BYTES, corrected),
                         [dict(offset=0x66c6f, offset_hex='0x66c6f', span=1, before_hex='20', after_hex='34')])
        self.assertEqual(corrected[0x66c6d:0x66c73], builder.NEW_INSTRUCTION)
        self.assertEqual((record['old_structure_offset'], record['new_structure_offset']), (16, 36))

    def test_already_patched_image_refused(self):
        corrected, _, _ = builder.prepare_bytes(RUNTIME_BYTES)
        with self.assertRaisesRegex(builder.BuildError, 'Unknown or already-patched'):
            builder.prepare_bytes(corrected)

    def test_wrong_hash_refused(self):
        changed = bytearray(RUNTIME_BYTES)
        changed[0x66c73] ^= 1
        with self.assertRaisesRegex(builder.BuildError, 'SHA-256'):
            builder.prepare_bytes(bytes(changed))

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
        self.root = Path(self.temp.name)
        self.source_dir = self.root / 'source'
        self.source_dir.mkdir()
        self.source = self.source_dir / 'ntdll.so'
        self.source.write_bytes(RUNTIME_BYTES)
        self.destination = self.root / 'new-artifact'

    def tearDown(self):
        self.temp.cleanup()

    def test_wrong_input_never_reaches_signer_or_creates_output(self):
        self.source.write_bytes(b'unrecognized input')
        with patch.object(builder, 'run_codesign') as signer:
            with self.assertRaises(builder.BuildError):
                builder.build(self.source, self.destination)
        signer.assert_not_called()
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.source.read_bytes(), b'unrecognized input')

    def test_existing_output_is_not_changed_or_removed(self):
        self.destination.mkdir()
        marker = self.destination / 'unrelated-user-file'
        marker.write_text('preserve me')
        with patch.object(builder, 'run_codesign') as signer:
            with self.assertRaisesRegex(builder.BuildError, 'already exists'):
                builder.build(self.source, self.destination)
        signer.assert_not_called()
        self.assertEqual(marker.read_text(), 'preserve me')

    def test_source_directory_overlap_refused(self):
        target = self.source_dir / 'output'
        with patch.object(builder, 'run_codesign') as signer:
            with self.assertRaisesRegex(builder.BuildError, 'overlaps source'):
                builder.build(self.source, target)
        signer.assert_not_called()
        self.assertFalse(target.exists())
        self.assertEqual(self.source.read_bytes(), RUNTIME_BYTES)

    def test_source_file_itself_cannot_be_output(self):
        with self.assertRaises(builder.BuildError):
            builder.build(self.source, self.source)
        self.assertEqual(self.source.read_bytes(), RUNTIME_BYTES)

    def test_symlink_output_is_not_followed_or_removed(self):
        self.destination.symlink_to(self.source_dir, target_is_directory=True)
        with self.assertRaisesRegex(builder.BuildError, 'already exists'):
            builder.build(self.source, self.destination)
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
                builder.build(self.source, self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.source.read_bytes(), RUNTIME_BYTES)

    def test_post_sign_validation_failure_cleans_new_output(self):
        def fake(args):
            return dict(arguments=args, returncode=0, stdout='',
                        stderr='Identifier=test.preserved.identifier\nSignature=adhoc\n')
        with patch.object(builder, 'run_codesign', side_effect=fake), \
             patch.object(builder, 'verify_signed_bytes', side_effect=builder.BuildError('injected validation failure')):
            with self.assertRaisesRegex(builder.BuildError, 'injected validation'):
                builder.build(self.source, self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.source.read_bytes(), RUNTIME_BYTES)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--result-json', type=Path)
    args = parser.parse_args()
    RUNTIME_BYTES = args.input.read_bytes()
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
