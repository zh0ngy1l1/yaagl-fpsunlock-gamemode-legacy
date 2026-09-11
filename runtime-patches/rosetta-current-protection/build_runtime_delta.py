#!/usr/bin/env python3
"""Build an isolated, exact-input Wine runtime correction; never install or load it.

The known x86-64 Mach-O ntdll uses one folded load for two source references to
MEMORY_BASIC_INFORMATION.AllocationProtect. Change that load to Protect. Refuse
unknown inputs, overlap and preexisting outputs. Sign only the new copy, preserving
its identifier, then verify the signature and every non-signature changed byte.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import sys

INPUT_SHA256 = 'f26ade35f5b49e33b3780b6adc71f9eb9c831ea40222c1bae667ac14135d984b'
INSTRUCTION_ADDRESS = 0x66C6D
CONTEXT_ADDRESS = 0x66C4E
OLD_INSTRUCTION = bytes.fromhex('8b 8d 20 ff ff ff')
NEW_INSTRUCTION = bytes.fromhex('8b 8d 34 ff ff ff')
OLD_CONTEXT = bytes.fromhex(
    '48 8d 95 10 ff ff ff 4c 8d 45 d0 b9 30 00 00 00 '
    '4c 89 f7 4c 89 e6 e8 e7 e3 ff ff 85 c0 75 46 '
    '8b 8d 20 ff ff ff f6 c1 f0 74 3b 81 e1 0f ff ff ff 83 f9 01 83 d1 00')
SOURCE_PATCH = '0001-ntdll-use-current-protection-for-rosetta-toggle.patch'


class BuildError(RuntimeError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked(condition: bool, message: str) -> None:
    if not condition:
        raise BuildError(message)


def decode_name(data: bytes) -> str:
    try:
        return data.split(b'\0', 1)[0].decode('ascii')
    except UnicodeDecodeError as exc:
        raise BuildError('Mach-O name is not ASCII') from exc


class MachO:
    """Bounded parser for the specific thin little-endian x86-64 dylib format."""
    def __init__(self, data: bytes):
        self.data = data
        self.segments = []
        self.sections = []
        self.signatures = []
        magic, cpu, subtype, filetype, count, size, flags, reserved = self.unpack('<8I', 0)
        checked(magic == 0xFEEDFACF, 'Expected thin little-endian Mach-O 64')
        checked(cpu == 0x01000007 and filetype == 6, 'Expected x86-64 Mach-O dylib')
        checked(count <= 1000 and 32 + size <= len(data), 'Invalid Mach-O load commands')
        self.header = dict(cpu=cpu, subtype=subtype, filetype=filetype, command_count=count,
                           command_size=size, flags=flags, reserved=reserved)
        at = 32
        for _ in range(count):
            cmd, cmdsize = self.unpack('<II', at)
            checked(cmdsize >= 8 and cmdsize % 8 == 0 and at + cmdsize <= 32 + size,
                    'Invalid Mach-O load command extent')
            if cmd == 0x19:  # LC_SEGMENT_64
                checked(cmdsize >= 72, 'Truncated segment command')
                name, vm, vmsize, off, filesize, maxprot, initprot, nsec, segflags = self.unpack('<16s4Q4I', at + 8)
                checked(72 + nsec * 80 == cmdsize, 'Invalid section count')
                checked(off + filesize <= len(data), 'Segment extends past file')
                segment = dict(name=decode_name(name), address=vm, memory_size=vmsize,
                               offset=off, size=filesize, max_protection=maxprot,
                               initial_protection=initprot, flags=segflags, command_offset=at)
                self.segments.append(segment)
                for i in range(nsec):
                    pos = at + 72 + i * 80
                    sn, sg, addr, length, fileoff, alignment, reloc, nreloc, sf, r1, r2, r3 = self.unpack('<16s16s2Q8I', pos)
                    checked(decode_name(sg) == segment['name'], 'Section/segment mismatch')
                    checked(vm <= addr and addr + length <= vm + vmsize, 'Section outside segment memory')
                    backed = sf & 0xFF not in (1, 0xC, 0x12)  # zero-fill section types
                    if backed:
                        checked(off <= fileoff and fileoff + length <= off + filesize,
                                'Section outside segment file bytes')
                        checked(fileoff - off == addr - vm, 'Inconsistent section virtual/file mapping')
                    self.sections.append(dict(name=decode_name(sn), segment=decode_name(sg),
                                              address=addr, size=length, offset=fileoff,
                                              flags=sf, backed=backed))
            elif cmd == 0x1D:  # LC_CODE_SIGNATURE
                checked(cmdsize == 16, 'Invalid code-signature command')
                off, length = self.unpack('<II', at + 8)
                checked(off + length <= len(data), 'Signature extends past file')
                self.signatures.append(dict(offset=off, size=length, command_offset=at))
            at += cmdsize
        checked(at == 32 + size, 'Load command count/size mismatch')
        checked(len(self.signatures) == 1, 'Expected one embedded signature')
        checked(len([x for x in self.segments if x['name'] == '__LINKEDIT']) == 1,
                'Expected one __LINKEDIT segment')
        self.signature = self.signatures[0]

    def unpack(self, fmt: str, at: int):
        checked(at >= 0 and at + struct.calcsize(fmt) <= len(self.data), 'Truncated Mach-O data')
        return struct.unpack_from(fmt, self.data, at)

    def text_offset(self, address: int, size: int) -> int:
        matches = [s for s in self.sections if s['segment'] == '__TEXT' and s['name'] == '__text'
                   and s['backed'] and s['address'] <= address
                   and address + size <= s['address'] + s['size']]
        checked(len(matches) == 1, 'Instruction is not entirely in one __TEXT,__text section')
        s = matches[0]
        checked(bool(s['flags'] & 0x80000000), 'Expected pure-instruction __text section')
        return s['offset'] + address - s['address']


def changed_ranges(before: bytes, after: bytes) -> list[dict]:
    output = []
    i = 0
    maximum = max(len(before), len(after))
    while i < maximum:
        equal = i < len(before) and i < len(after) and before[i] == after[i]
        if equal:
            i += 1
            continue
        begin = i
        while i < maximum and not (i < len(before) and i < len(after) and before[i] == after[i]):
            i += 1
        output.append(dict(offset=begin, offset_hex=hex(begin), span=i - begin,
                           before_hex=before[begin:i].hex(' '), after_hex=after[begin:i].hex(' ')))
    return output


def prepare_bytes(original: bytes) -> tuple[bytes, MachO, dict]:
    checked(digest(original) == INPUT_SHA256, 'Unknown or already-patched input SHA-256; refusing runtime')
    image = MachO(original)
    context_at = image.text_offset(CONTEXT_ADDRESS, len(OLD_CONTEXT))
    at = image.text_offset(INSTRUCTION_ADDRESS, len(OLD_INSTRUCTION))
    checked(original[context_at:context_at + len(OLD_CONTEXT)] == OLD_CONTEXT,
            'Exact NtWriteVirtualMemory query/load/test context mismatch')
    checked(original[at:at + len(OLD_INSTRUCTION)] == OLD_INSTRUCTION,
            'Exact AllocationProtect instruction mismatch')
    changed = bytearray(original)
    changed[at:at + len(NEW_INSTRUCTION)] = NEW_INSTRUCTION
    unsigned = bytes(changed)
    changes = changed_ranges(original, unsigned)
    checked(changes == [dict(offset=at + 2, offset_hex=hex(at + 2), span=1,
                            before_hex='20', after_hex='34')], 'Expected exactly one unsigned changed byte')
    return unsigned, image, dict(instruction_address=hex(INSTRUCTION_ADDRESS), file_offset=at,
                                 file_offset_hex=hex(at), changed_file_offset=at + 2,
                                 context_address=hex(CONTEXT_ADDRESS), context_file_offset=context_at,
                                 old_instruction=OLD_INSTRUCTION.hex(' '),
                                 new_instruction=NEW_INSTRUCTION.hex(' '),
                                 source_change='Both info.AllocationProtect references become info.Protect; compiler folded them into one load.',
                                 old_structure_offset=16, new_structure_offset=36,
                                 unsigned_changed_ranges=changes)


def run_codesign(arguments: list[str]) -> dict:
    result = subprocess.run(['/usr/bin/codesign', *arguments], text=True, capture_output=True,
                            timeout=30, check=False)
    checked(result.returncode == 0,
            'codesign failed: ' + ' '.join(arguments[:3]) + '\n' + result.stderr.strip())
    return dict(arguments=arguments, returncode=result.returncode,
                stdout=result.stdout, stderr=result.stderr)


def signature_description(path: Path) -> tuple[str, dict]:
    result = run_codesign(['-dv', '--verbose=4', str(path)])
    ids = re.findall(r'^Identifier=(.+)$', result['stdout'] + '\n' + result['stderr'], re.MULTILINE)
    checked(len(ids) == 1, 'Cannot establish one signature identifier')
    checked('Signature=adhoc' in result['stdout'] + result['stderr'], 'Expected ad-hoc runtime signature')
    return ids[0], result


def verify_signed_bytes(unsigned: bytes, signed: bytes, original_image: MachO) -> dict:
    signed_image = MachO(signed)
    at = signed_image.text_offset(INSTRUCTION_ADDRESS, len(NEW_INSTRUCTION))
    checked(signed[at:at + len(NEW_INSTRUCTION)] == NEW_INSTRUCTION,
            'Signer changed the corrected instruction')
    checked(original_image.sections == signed_image.sections, 'Signer changed section layout')
    for section in original_image.sections:
        if section['backed']:
            a, b = section['offset'], section['offset'] + section['size']
            checked(unsigned[a:b] == signed[a:b], 'Signer changed section bytes: ' + section['name'])
    # The signature payload and its size/offset, plus __LINKEDIT allocation sizes,
    # may change. Everything else must match the unsigned one-byte correction.
    allowed = []
    for image in (original_image, signed_image):
        sig = image.signature
        allowed += [(sig['offset'], sig['offset'] + sig['size']),
                    (sig['command_offset'] + 8, sig['command_offset'] + 16)]
        linkedit = next(x for x in image.segments if x['name'] == '__LINKEDIT')
        cmd = linkedit['command_offset']
        allowed += [(cmd + 32, cmd + 40), (cmd + 48, cmd + 56)]
    differences = changed_ranges(unsigned, signed)
    for change in differences:
        checked(all(any(a <= p < b for a, b in allowed)
                    for p in range(change['offset'], change['offset'] + change['span'])),
                'Signer changed bytes outside allowed signature metadata/payload')
    return dict(all_file_backed_section_bytes_preserved=True,
                unsigned_to_signed_changed_ranges=differences,
                allowed_signature_change_ranges=[dict(begin=hex(a), end=hex(b)) for a, b in allowed],
                signature=signed_image.signature)


def read_stable_input(path: Path) -> tuple[bytes, dict]:
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        data = stream.read()
        after = os.fstat(stream.fileno())
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
    checked(all(getattr(before, name) == getattr(after, name) for name in fields),
            'Input changed while it was read')
    checked(stat.S_ISREG(before.st_mode), 'Input must be a regular file')
    return data, {name.removeprefix('st_'): getattr(before, name) for name in fields}


def destination(input_path: Path, output_directory: Path) -> tuple[Path, Path]:
    input_path = input_path.resolve(strict=True)
    checked(input_path.is_file(), 'Input must be a regular file')
    # Resolve only existing parent components; never create parent directories.
    parent = output_directory.parent.resolve(strict=True)
    checked(parent.is_dir(), 'Output parent must already exist')
    output = parent / output_directory.name
    checked(output.name not in ('', '.', '..'), 'Invalid output directory')
    checked(not output.exists() and not output.is_symlink(), 'Output directory already exists')
    checked(not input_path.is_relative_to(output) and not output.is_relative_to(input_path.parent),
            'Output overlaps source or source directory; require isolated staging')
    return input_path, output


def build(input_path: Path, output_directory: Path) -> dict:
    input_path, output = destination(input_path, output_directory)
    original, original_stat = read_stable_input(input_path)
    unsigned, image, patch = prepare_bytes(original)
    input_verify = run_codesign(['--verify', '--strict', '--verbose=2', str(input_path)])
    identifier, input_signature = signature_description(input_path)
    source_patch = Path(__file__).with_name(SOURCE_PATCH)
    checked(source_patch.is_file(), 'Missing accompanying source correction patch')
    source_patch_sha = digest(source_patch.read_bytes())
    owned = None
    try:
        output.mkdir(mode=0o700, exist_ok=False)
        st = output.stat()
        owned = st.st_dev, st.st_ino
        artifact = output / 'ntdll.so'
        artifact.write_bytes(unsigned)
        artifact.chmod(stat.S_IMODE(original_stat['mode']))
        checked(artifact.read_bytes() == unsigned, 'Staged unsigned copy mismatch')
        sign_result = run_codesign(['--force', '--sign', '-', '--identifier', identifier,
                                   '--timestamp=none', str(artifact)])
        signed = artifact.read_bytes()
        code_verification = verify_signed_bytes(unsigned, signed, image)
        signature_verify = run_codesign(['--verify', '--strict', '--verbose=2', str(artifact)])
        final_identifier, final_signature = signature_description(artifact)
        checked(identifier == final_identifier, 'Signature identifier changed')
        final_original, final_stat = read_stable_input(input_path)
        checked(original == final_original and original_stat == final_stat, 'Input changed during build')
        manifest = dict(schema=1, purpose='Isolated exact-runtime current-page protection correction; not installed or executed',
                        created_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                        input=dict(path=str(input_path), sha256=digest(original), size=len(original), stat=original_stat),
                        source_patch=dict(file=SOURCE_PATCH, sha256=source_patch_sha),
                        instruction_patch=patch,
                        unsigned=dict(sha256=digest(unsigned), size=len(unsigned)),
                        signed=dict(file=artifact.name, sha256=digest(signed), size=len(signed), identifier=identifier),
                        original_to_signed_changed_ranges=changed_ranges(original, signed),
                        code_verification=code_verification,
                        codesign=dict(input_verify=input_verify, input_description=input_signature,
                                      signing=sign_result, output_verify=signature_verify,
                                      output_description=final_signature),
                        source_unchanged=True,
                        limits=['This artifact is an exact binary delta plus ad-hoc signature, not a full Wine rebuild.',
                                'No runtime execution or gameplay validation is performed.',
                                'The corrected executable-page selection does not establish login/world readiness or retrospective crash causality.'])
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        return manifest
    except BaseException:
        if owned is not None and output.exists():
            st = output.lstat()
            if stat.S_ISDIR(st.st_mode) and (st.st_dev, st.st_ino) == owned:
                shutil.rmtree(output)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output-directory', required=True, type=Path)
    args = parser.parse_args()
    try:
        manifest = build(args.input, args.output_directory)
    except (BuildError, OSError, subprocess.SubprocessError) as exc:
        print('Build refused/failed: ' + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(dict(output_directory=str(args.output_directory.resolve()),
                          signed_sha256=manifest['signed']['sha256'],
                          instruction_file_offset=manifest['instruction_patch']['file_offset_hex'],
                          source_unchanged=True, signature_verified=True), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
