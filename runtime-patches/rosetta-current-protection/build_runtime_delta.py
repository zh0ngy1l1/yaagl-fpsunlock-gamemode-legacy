#!/usr/bin/env python3
"""Build a pinned Wine correction only inside an explicitly declared offline root.

The known x86-64 Mach-O ntdll uses a folded AllocationProtect load and a twelve-
byte no-execute calculation. Select current Protect and map its executable base
to the corresponding non-executable base while preserving modifiers. Refuse
unknown inputs, outputs, signatures and preexisting destinations. The only input
is a copied root/input/ntdll.so; the only output is root/builds/<output-name>.
Installed Wine paths are never accepted. This tool does not create its offline
root declaration, install anything, load a library, or execute Wine.
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
UNSIGNED_SHA256 = '9cc5ac83007e7942fe422793875c90f81fd6d647e5694ac96478c3e6326bc53d'
SIGNED_SHA256 = 'eef64f611ae9033261a70f46ec0be38d58823717f14e80331946c6d0cd3c85f7'
EXPECTED_SIZE = 620688
INSTRUCTION_ADDRESS = 0x66C6D
CONTEXT_ADDRESS = 0x66C4E
OLD_INSTRUCTION = bytes.fromhex('8b 8d 20 ff ff ff')
NEW_INSTRUCTION = bytes.fromhex('8b 8d 34 ff ff ff')
CALCULATION_ADDRESS = 0x66C78
OLD_CALCULATION = bytes.fromhex('81 e1 0f ff ff ff 83 f9 01 83 d1 00')
NEW_CALCULATION = bytes.fromhex('c0 e9 04') + bytes.fromhex('90') * 9
OLD_CONTEXT = bytes.fromhex(
    '48 8d 95 10 ff ff ff 4c 8d 45 d0 b9 30 00 00 00 '
    '4c 89 f7 4c 89 e6 e8 e7 e3 ff ff 85 c0 75 46 '
    '8b 8d 20 ff ff ff f6 c1 f0 74 3b 81 e1 0f ff ff ff 83 f9 01 83 d1 00')
SOURCE_PATCH = '0001-ntdll-use-current-protection-for-rosetta-toggle.patch'
SOURCE_PATCH_SHA256 = '88dd45f99c6438db828688239286192b1405c90f22d03ef5c54b62bb22c52458'
STAGING_DECLARATION = '.yaagl-offline-runtime-staging.json'


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
    checked(len(original) == EXPECTED_SIZE, 'Unexpected input size')
    image = MachO(original)
    context_at = image.text_offset(CONTEXT_ADDRESS, len(OLD_CONTEXT))
    at = image.text_offset(INSTRUCTION_ADDRESS, len(OLD_INSTRUCTION))
    checked(original[context_at:context_at + len(OLD_CONTEXT)] == OLD_CONTEXT,
            'Exact NtWriteVirtualMemory query/load/test context mismatch')
    checked(original[at:at + len(OLD_INSTRUCTION)] == OLD_INSTRUCTION,
            'Exact AllocationProtect instruction mismatch')
    calc_at = image.text_offset(CALCULATION_ADDRESS, len(OLD_CALCULATION))
    checked(original[calc_at:calc_at + len(OLD_CALCULATION)] == OLD_CALCULATION,
            'Exact no-execute calculation mismatch')
    checked(len(NEW_CALCULATION) == len(OLD_CALCULATION), 'Calculation replacement changes code extent')
    changed = bytearray(original)
    changed[at:at + len(NEW_INSTRUCTION)] = NEW_INSTRUCTION
    changed[calc_at:calc_at + len(NEW_CALCULATION)] = NEW_CALCULATION
    unsigned = bytes(changed)
    changes = changed_ranges(original, unsigned)
    checked(changes == [dict(offset=at + 2, offset_hex=hex(at + 2), span=1,
                            before_hex='20', after_hex='34'),
                       dict(offset=calc_at, offset_hex=hex(calc_at), span=12,
                            before_hex=OLD_CALCULATION.hex(' '), after_hex=NEW_CALCULATION.hex(' '))],
            'Expected only the current-Protect load byte and twelve-byte no-execute calculation')
    checked(digest(unsigned) == UNSIGNED_SHA256, 'Unsigned output does not match reviewed SHA-256')
    return unsigned, image, dict(instruction_address=hex(INSTRUCTION_ADDRESS), file_offset=at,
                                 file_offset_hex=hex(at), changed_file_offset=at + 2,
                                 context_address=hex(CONTEXT_ADDRESS), context_file_offset=context_at,
                                 old_instruction=OLD_INSTRUCTION.hex(' '),
                                 new_instruction=NEW_INSTRUCTION.hex(' '),
                                 calculation_address=hex(CALCULATION_ADDRESS), calculation_file_offset=calc_at,
                                 calculation_file_offset_hex=hex(calc_at),
                                 old_calculation=OLD_CALCULATION.hex(' '), new_calculation=NEW_CALCULATION.hex(' '),
                                 source_change='Use current info.Protect for selection and map its executable base to the corresponding non-executable base while preserving modifier bits.',
                                 calculation_equivalence='SHR CL,4 preserves ECX bits 8-31 and replaces bits 0-7 with original bits 4-7, exactly (Protect & ~0xff) | ((Protect & 0xf0) >> 4).',
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
    calc_at = signed_image.text_offset(CALCULATION_ADDRESS, len(NEW_CALCULATION))
    checked(signed[calc_at:calc_at + len(NEW_CALCULATION)] == NEW_CALCULATION,
            'Signer changed the corrected no-execute calculation')
    checked(original_image.sections == signed_image.sections, 'Signer changed section layout')
    for section in original_image.sections:
        if section['backed']:
            a, b = section['offset'], section['offset'] + section['size']
            checked(unsigned[a:b] == signed[a:b], 'Signer changed section bytes: ' + section['name'])
    # The signature payload and its size/offset, plus __LINKEDIT allocation sizes,
    # may change. Everything else must match the exact pre-sign correction.
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
    checked(len(signed) == EXPECTED_SIZE and digest(signed) == SIGNED_SHA256,
            'Signed output does not match reviewed SHA-256; refusing signer variation')
    checked(digest(unsigned) == UNSIGNED_SHA256, 'Unsigned input to signer does not match reviewed SHA-256')
    return dict(all_file_backed_section_bytes_preserved=True,
                unsigned_to_signed_changed_ranges=differences,
                allowed_signature_change_ranges=[dict(begin=hex(a), end=hex(b)) for a, b in allowed],
                signature=signed_image.signature)


def read_stable_input(path: Path) -> tuple[bytes, dict]:
    # Opening a FIFO must not block before its type can be rejected. O_NOFOLLOW
    # also rejects a leaf symlink replaced after the path checks.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        checked(stat.S_ISREG(before.st_mode), 'Copied input must be a regular file')
        checked(before.st_nlink == 1, 'Copied input must not be a hardlink')
        checked(before.st_size == EXPECTED_SIZE, 'Copied input has unexpected size')
        data = stream.read()
        after = os.fstat(stream.fileno())
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
    checked(all(getattr(before, name) == getattr(after, name) for name in fields),
            'Input changed while it was read')
    checked(stat.S_ISREG(before.st_mode), 'Input must be a regular file')
    return data, {name.removeprefix('st_'): getattr(before, name) for name in fields}


def staging_declaration(root: Path) -> dict:
    """Expected reviewable declaration. The builder never writes this file."""
    return dict(schema=1, purpose='offline-runtime-build-only', root=str(root),
                input='input/ntdll.so', outputs='builds', input_sha256=INPUT_SHA256)


def checked_staging_directory(path: Path) -> dict:
    info = path.lstat()
    checked(stat.S_ISDIR(info.st_mode) and not path.is_symlink(),
            'Staging directories must be real directories, not symlinks')
    checked(path.resolve(strict=True) == path, 'Staging path traverses a symlink or noncanonical component')
    checked(info.st_uid == os.getuid() and not (info.st_mode & 0o022),
            'Staging directories must be owned by the caller and not writable by other users')
    return dict(device=info.st_dev, inode=info.st_ino, mode=info.st_mode)


def reject_installation_location(root: Path) -> None:
    """Defend the offline declaration against accidentally naming a live tree."""
    parts = {part.casefold() for part in root.parts}
    forbidden = {'applications', 'wineprefix', 'hoyoplay-wines', 'drive_c', 'system32', 'syswow64'}
    checked(not parts.intersection(forbidden) and not any(part.casefold().endswith('.app') for part in root.parts),
            'Installed application, prefix, or Wine locations cannot be staging roots')
    home = Path.home().resolve()
    live_support = home / 'Library/Application Support/Yaagl OS'
    checked(root != home and not root.is_relative_to(live_support),
            'Home or active launcher support directory cannot be a staging root')
    for parent in (root, *root.parents):
        wine_root = (parent / 'bin/wine').exists() and (parent / 'lib/wine').is_dir()
        wine_distribution = (parent / 'wine/bin/wine').exists() and (parent / 'wine/lib/wine').is_dir()
        checked(not wine_root and not wine_distribution, 'Recognized Wine installation cannot contain staging')


def destination(staging_root: Path, output_name: str) -> tuple[Path, Path, dict]:
    checked(staging_root.is_absolute(), 'Staging root must be an explicit absolute canonical path')
    reject_installation_location(staging_root)
    checked(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', output_name) is not None,
            'Output name must be one simple directory component')
    root = staging_root.resolve(strict=True)
    checked(root == staging_root, 'Staging root must not traverse symlinks or noncanonical components')
    reject_installation_location(root)
    directories = {str(p): checked_staging_directory(p)
                   for p in (root, root / 'input', root / 'builds')}
    declaration = root / STAGING_DECLARATION
    info = declaration.lstat()
    checked(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and not declaration.is_symlink(),
            'Offline staging declaration must be a regular independent file')
    checked(info.st_uid == os.getuid() and not (info.st_mode & 0o022) and info.st_size <= 16384,
            'Offline staging declaration ownership, permissions or size is invalid')
    fd = os.open(declaration, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        raw_declaration = stream.read(16385)
    try:
        policy = json.loads(raw_declaration)
    except (ValueError, UnicodeError) as exc:
        raise BuildError('Invalid offline staging declaration JSON') from exc
    checked(policy == staging_declaration(root), 'Offline staging declaration does not match this root and profile')
    input_path = root / 'input/ntdll.so'
    info = input_path.lstat()
    checked(stat.S_ISREG(info.st_mode) and not input_path.is_symlink(), 'Input must be a copied regular file, not a symlink')
    checked(info.st_nlink == 1, 'Copied input must not be a hardlink')
    checked(info.st_uid == os.getuid() and not (info.st_mode & 0o022), 'Copied input ownership or permissions are invalid')
    output = root / 'builds' / output_name
    checked(not output.exists() and not output.is_symlink(), 'Output directory already exists')
    return input_path, output, dict(root=str(root), declaration_sha256=digest(raw_declaration),
                                   input_relative='input/ntdll.so', output_relative='builds/' + output_name,
                                   directories=directories)


def build(staging_root: Path, output_name: str) -> dict:
    input_path, output, staging = destination(staging_root, output_name)
    original, original_stat = read_stable_input(input_path)
    unsigned, image, patch = prepare_bytes(original)
    input_verify = run_codesign(['--verify', '--strict', '--verbose=2', str(input_path)])
    identifier, input_signature = signature_description(input_path)
    source_patch = Path(__file__).with_name(SOURCE_PATCH)
    checked(source_patch.is_file(), 'Missing accompanying source correction patch')
    source_patch_sha = digest(source_patch.read_bytes())
    checked(source_patch_sha == SOURCE_PATCH_SHA256, 'Source correction patch does not match reviewed SHA-256')
    owned = None
    try:
        output.mkdir(mode=0o700, exist_ok=False)
        st = output.stat()
        owned = st.st_dev, st.st_ino
        pre_sign_artifact = output / 'ntdll.pre-sign.so'
        pre_sign_artifact.write_bytes(unsigned)
        pre_sign_artifact.chmod(0o400)
        checked(pre_sign_artifact.read_bytes() == unsigned, 'Persisted pre-sign bytes mismatch')
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
        checked(pre_sign_artifact.read_bytes() == unsigned, 'Signer or another actor changed the pre-sign artifact')
        final_original, final_stat = read_stable_input(input_path)
        checked(original == final_original and original_stat == final_stat, 'Input changed during build')
        for path, expected in staging['directories'].items():
            checked(checked_staging_directory(Path(path)) == expected, 'Staging directory changed during build')
        checked(digest((staging_root / STAGING_DECLARATION).read_bytes()) == staging['declaration_sha256'],
                'Offline staging declaration changed during build')
        manifest = dict(schema=1, purpose='Isolated V2 exact-runtime current-page selection and non-executable base mapping; not installed or executed',
                        created_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                        staging=staging,
                        input=dict(path=str(input_path), sha256=digest(original), size=len(original), stat=original_stat),
                        source_patch=dict(file=SOURCE_PATCH, sha256=source_patch_sha),
                        instruction_patch=patch,
                        pre_sign=dict(file=pre_sign_artifact.name, sha256=digest(unsigned), size=len(unsigned),
                                      signature_state='Stale original embedded signature; byte-review artifact only, not for loading or deployment'),
                        unsigned=dict(file=pre_sign_artifact.name, sha256=digest(unsigned), size=len(unsigned),
                                      terminology='Pre-sign bytes, not a stripped-signature Mach-O'),
                        signed=dict(file=artifact.name, sha256=digest(signed), size=len(signed), identifier=identifier),
                        expected_hashes=dict(input=INPUT_SHA256, unsigned=UNSIGNED_SHA256, signed=SIGNED_SHA256,
                                             source_patch=SOURCE_PATCH_SHA256, all_matched=True),
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
    parser.add_argument('--staging-root', required=True, type=Path,
                        help='Existing declared offline root containing copied input/ntdll.so and builds/')
    parser.add_argument('--output-name', required=True,
                        help='New single-component directory name below the declared builds/')
    args = parser.parse_args()
    try:
        manifest = build(args.staging_root, args.output_name)
    except (BuildError, OSError, subprocess.SubprocessError) as exc:
        print('Build refused/failed: ' + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(dict(output_directory=str(args.staging_root / 'builds' / args.output_name),
                          signed_sha256=manifest['signed']['sha256'],
                          instruction_file_offset=manifest['instruction_patch']['file_offset_hex'],
                          source_unchanged=True, signature_verified=True), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
