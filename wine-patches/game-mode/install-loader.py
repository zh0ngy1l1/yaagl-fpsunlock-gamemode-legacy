#!/usr/bin/env python3
"""Install/restore the opt-in bundle in an idle, standalone Wine 11.0 engine."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bundle_files(app):
    result = {}
    for path in sorted(app.rglob('*')):
        if path.is_symlink():
            raise RuntimeError(f'Unexpected symlink in bundle: {path}')
        if path.is_file():
            result[str(path.relative_to(app))] = digest(path)
    return result


def verify(path):
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(path)], check=True)


def require_idle(engine):
    # Wine rewrites argv to a Windows command line. Inspect the native executable,
    # including orphaned children, rather than matching the displayed process name.
    libproc = ctypes.CDLL('/usr/lib/libproc.dylib')
    for line in subprocess.check_output(['ps', '-axo', 'pid='], text=True).splitlines():
        pid = int(line.strip())
        buf = ctypes.create_string_buffer(4096)
        if libproc.proc_pidpath(pid, buf, len(buf)) > 0:
            if Path(os.fsdecode(buf.value)).resolve().is_relative_to(engine):
                raise RuntimeError(f'Engine process {pid} is still running; quit its applications first')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'restore'])
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--backup', type=Path, required=True, help='Separate rollback directory')
    parser.add_argument('--candidate', type=Path, help='build-loader.py output, required for install')
    args = parser.parse_args()
    engine, backup = args.engine.resolve(), args.backup.resolve()
    loader = engine / 'lib/wine/x86_64-unix/wine'
    app = loader.parent / 'WineGame.app'
    if backup.is_relative_to(engine):
        parser.error('Keep rollback data outside the engine')
    if any(p.suffix == '.app' for p in [engine, *engine.parents]):
        parser.error('An enclosing signed app requires a separate packaging/signing procedure')
    if loader.is_symlink() or not loader.is_file():
        parser.error('Expected the native inner loader at lib/wine/x86_64-unix/wine')
    for name in ['ntdll.so', 'winemac.so']:
        if not (loader.parent / name).is_file():
            parser.error(f'Missing engine component: {name}')
    if (loader.parent / 'wine-preloader').exists():
        parser.error('This recipe is for the validated loader without a preloader')
    require_idle(engine)
    verify(loader)

    if args.action == 'install':
        if args.candidate is None:
            parser.error('--candidate is required for install')
        candidate = args.candidate.resolve()
        if app.exists() or app.is_symlink() or backup.exists():
            parser.error('Bundle or rollback directory already exists; refusing to overwrite it')
        source = candidate / 'forwarder'
        source_app = candidate / 'WineGame.app'
        verify(source)
        verify(source_app)
        files = bundle_files(source_app)
        built = json.loads((candidate / 'build.json').read_text())['files']
        expected = {'WineGame.app/' + k: v for k, v in files.items()}
        expected['forwarder'] = digest(source)
        if built != expected:
            parser.error('Candidate differs from its build manifest')
        record = {'engine': str(engine), 'originalSHA256': digest(loader),
                  'forwarderSHA256': digest(source), 'bundleFiles': files}
        backup.mkdir(parents=True, exist_ok=False)
        shutil.copy2(loader, backup / 'wine')
        verify(backup / 'wine')
        if digest(backup / 'wine') != record['originalSHA256']:
            raise RuntimeError('Original loader backup did not match')
        (backup / 'state.json').write_text(json.dumps(record, indent=2) + '\n')
    else:
        record = json.loads((backup / 'state.json').read_text())
        if record['engine'] != str(engine):
            parser.error('Rollback record belongs to another engine')
        if digest(loader) != record['forwarderSHA256'] or bundle_files(app) != record['bundleFiles']:
            parser.error('Installed loader/bundle changed; refusing to overwrite or remove it')
        verify(app)
        source = backup / 'wine'
        if digest(source) != record['originalSHA256']:
            parser.error('Original loader backup changed')
        verify(source)

    # Stage and verify on the destination filesystem before changing either path.
    with tempfile.TemporaryDirectory(prefix='.game-mode-', dir=loader.parent) as temp:
        staged = Path(temp) / 'wine'
        shutil.copy2(source, staged)
        verify(staged)
        if digest(staged) != digest(source):
            raise RuntimeError('Staged loader did not match')
        if args.action == 'install':
            staged_app = Path(temp) / 'WineGame.app'
            shutil.copytree(source_app, staged_app)
            verify(staged_app)
            if bundle_files(staged_app) != record['bundleFiles']:
                raise RuntimeError('Staged bundle did not match')
        require_idle(engine)
        if args.action == 'install':
            staged_app.rename(app)
            try:
                os.replace(staged, loader)
            except BaseException:
                shutil.rmtree(app)
                raise
        else:
            os.replace(staged, loader)
            shutil.rmtree(app)
    verify(loader)
    print(f'{args.action}: {engine}')
    print(f'Rollback data retained: {backup}')


if __name__ == '__main__':
    main()
