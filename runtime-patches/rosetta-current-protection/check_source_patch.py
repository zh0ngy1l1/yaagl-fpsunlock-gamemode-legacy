#!/usr/bin/env python3
"""Apply pinned downstream overlay and correction to a fresh source-only directory."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

PRISTINE = 'cc09fcaf2f5234eedf68ba068ffa6f7b586bca2753ce98bc0887d11002913419'
OVERLAY = '41277c5b18fffcd7aa71a33c5f6ba33d2c91f262dc7b1f5855b8951a563d464c'
CORRECTION = 'f901749a1fc93bbe9d44f4cafc8178f5e8e1f84ab67366a015fa71f19d7819bb'
WITH_OVERLAY = 'f3511868a91f4c2e62bb52f432f5aab0e3526085a35fcea3eedb44ac5a6e8a2f'
CORRECTED = 'e8ea8f4d6f255f658be38e6656e2e1924ccbd042e40d469b4133261506f265b0'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pristine-source', type=Path, required=True)
    parser.add_argument('--overlay-patch', type=Path, required=True)
    parser.add_argument('--patch', type=Path, required=True, help='External pinned correction patch')
    parser.add_argument('--output-directory', type=Path, required=True)
    args = parser.parse_args()
    inputs = [(args.pristine_source, PRISTINE), (args.overlay_patch, OVERLAY), (args.patch, CORRECTION)]
    snapshots = {}
    for path, expected in inputs:
        path = path.resolve(strict=True)
        data = path.read_bytes()
        if sha(data) != expected:
            raise ValueError('Unexpected source/patch hash: ' + str(path))
        snapshots[path] = data
    parent = args.output_directory.parent.resolve(strict=True)
    output = parent / args.output_directory.name
    if output.exists() or output.is_symlink():
        raise ValueError('Output directory already exists')
    if any(path.is_relative_to(output) or output.is_relative_to(path.parent) for path in snapshots):
        raise ValueError('Output overlaps source directory')
    output.mkdir(mode=0o700)
    owned = output.stat().st_dev, output.stat().st_ino
    try:
        target = output / 'dlls/ntdll/unix/virtual.c'
        target.parent.mkdir(parents=True)
        target.write_bytes(args.pristine_source.read_bytes())
        records = []
        for patch, expected in [(args.overlay_patch, WITH_OVERLAY), (args.patch, CORRECTED)]:
            run = subprocess.run(['/usr/bin/patch', '-p1', '-F0', '--batch', '--forward', '-i', str(patch.resolve())],
                                 cwd=output, text=True, capture_output=True, timeout=30)
            records.append(dict(patch=str(patch.resolve()), exit_code=run.returncode,
                                stdout=run.stdout, stderr=run.stderr))
            if run.returncode != 0 or sha(target.read_bytes()) != expected:
                raise ValueError('Patch application/result mismatch')
        text = target.read_text()
        begin = text.index('static void toggle_executable_pages_for_rosetta(')
        end = text.index('\n}\n', begin) + 3
        helper = text[begin:end]
        if helper.count('info.Protect') != 2 or 'AllocationProtect' in helper:
            raise ValueError('Corrected helper references mismatch')
        for path, data in snapshots.items():
            if path.read_bytes() != data:
                raise ValueError('Source input changed during check')
        result = dict(inputs=[dict(path=str(p), sha256=sha(data)) for p, data in snapshots.items()],
                      correction_references=2, applications=records,
                      corrected_source_sha256=sha(target.read_bytes()),
                      input_bytes_unchanged=True, all_checks_passed=True)
        (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))
    except BaseException:
        if output.is_dir() and (output.stat().st_dev, output.stat().st_ino) == owned:
            shutil.rmtree(output)
        raise


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print('Source check refused/failed: ' + str(exc), file=sys.stderr)
        sys.exit(1)
