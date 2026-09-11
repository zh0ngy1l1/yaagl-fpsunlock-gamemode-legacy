#!/usr/bin/env python3
"""Package a full install-lib build, retaining the identified release's dependencies."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

work = Path(sys.argv[1]).resolve()
engine = work / 'dist/wine'
runtime = work / 'runtime'
# No Wine implementation modules are taken from the existing engine.
for path in (runtime / 'lib').iterdir():
    if path.name == 'wine':
        continue
    dest = engine / 'lib' / path.name
    if path.is_symlink():
        if not dest.exists() and not dest.is_symlink():
            dest.symlink_to(os.readlink(path))
    elif path.is_dir():
        dest.mkdir(parents=True, exist_ok=True)
        subprocess.run(['rsync', '-a', str(path)+'/', str(dest)+'/'], check=True)
    else:
        shutil.copy2(path, dest)
for name in ('gecko', 'mono'):
    dest = engine / 'share/wine' / name
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(['rsync', '-a', str(runtime / 'share/wine' / name)+'/', str(dest)+'/'], check=True)
docs = engine / 'share/doc/wine-devel'
docs.mkdir(parents=True, exist_ok=True)
for name in ('ANNOUNCE.md', 'AUTHORS', 'COPYING.LIB', 'LICENSE', 'README.md'):
    shutil.copy2(work / 'wine-wine-11.0' / name, docs / name)
# Preserve DXMT files as YAAGL itself installs them; do not overwrite Wine's
# implementation of d3d11/dxgi. The launcher syncs its selected renderer on launch.
# Only Mach-O files built by Wine need path relocation and local ad-hoc signing.
binaries = []
for base in (engine / 'bin', engine / 'lib/wine'):
    for path in base.rglob('*'):
        if not path.is_file() or path.is_symlink():
            continue
        if path.open('rb').read(4) != b'\xcf\xfa\xed\xfe':
            continue
        binaries.append(path)
        listing = subprocess.check_output(['otool', '-l', str(path)], text=True)
        lines = listing.splitlines()
        rpaths = [lines[i+2].split('path ', 1)[1].split(' (offset', 1)[0]
                  for i, line in enumerate(lines) if line.strip() == 'cmd LC_RPATH']
        args = []
        for rpath in rpaths:
            if rpath.startswith(str(work)):
                args += ['-delete_rpath', rpath]
        lib = os.path.relpath(engine / 'lib', path.parent)
        required = ['@loader_path/' + lib,
                    '@loader_path/' + lib + '/GStreamer.framework/Versions/1.0/lib']
        for rpath in required:
            if rpath not in rpaths:
                args += ['-add_rpath', rpath]
        deps = subprocess.check_output(['otool', '-L', str(path)], text=True).splitlines()[1:]
        for dep in deps:
            old = dep.strip().split(' (compatibility', 1)[0]
            if old.startswith(str(work)):
                args += ['-change', old, '@rpath/' + Path(old).name]
        if args:
            subprocess.run(['install_name_tool', *args, str(path)], check=True)
        subprocess.run(['codesign', '--force', '--sign', '-', str(path)], check=True)
        subprocess.run(['codesign', '--verify', str(path)], check=True)
# A usable engine has native host components plus both PE architectures.
for name in ('bin/wine', 'bin/wineserver', 'lib/wine/x86_64-unix/winemac.so',
             'lib/wine/x86_64-windows/ntdll.dll', 'lib/wine/i386-windows/ntdll.dll'):
    assert (engine / name).is_file(), name
manifest = {str(p.relative_to(engine)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in binaries}
(work / 'logs/built-macho.sha256.json').write_text(json.dumps(manifest, indent=2)+'\n')
archive = work / 'dist/wine-11.0-yaagl-fixed-fullscreen.tar.xz'
with archive.open('wb') as output:
    tar = subprocess.Popen(['tar', '-cf', '-', '-C', str(engine.parent), 'wine'], stdout=subprocess.PIPE)
    try:
        subprocess.run(['xz', '-T4', '-3', '-c'], stdin=tar.stdout, stdout=output, check=True)
    finally:
        tar.stdout.close()
    if tar.wait():
        raise RuntimeError('tar failed')
print(engine)
print(archive)
print('sha256:', hashlib.sha256(archive.read_bytes()).hexdigest())
