#!/usr/bin/env python3
"""Reversibly select this local engine for YAAGL's existing Wine 11.0 entry.

Close YAAGL and its Wine applications first. Does not touch prefix, registry,
launcher preferences, shared engine, or keyboard settings.
"""
import os
from pathlib import Path
import subprocess
import sys

if len(sys.argv)!=2 or sys.argv[1] not in ('built','original'):
    sys.exit('Usage: select-engine.py built|original')
base=Path.home()/'Library/Application Support/Yaagl OS'
slot=base/'hoyoplay-wines/genshin/11.0-dxmt-signed-with-patches/wine'
backup=slot.with_name('wine.original-before-fixed-fullscreen')
work=Path(os.environ.get('YAAGL_WINE_WORK','/Users/david/code/home/yaagl-wine-fullscreen')).resolve()
# Preserve the original tree in place and select a complete locally built engine.
built=work/'dist/wine'
processes=subprocess.check_output(['ps','-axo','pid=,comm='],text=True)
for line in processes.splitlines():
    # ps may report the resolved build path instead of the YAAGL slot symlink.
    if (str(base) in line and ('/wine/' in line or '/wineserver' in line)) or str(built)+'/' in line:
        sys.exit('A YAAGL Wine process is running; close it before switching: '+line.strip())
if sys.argv[1]=='built':
    assert (built/'bin/wine').is_file() and (built/'lib/wine/x86_64-unix/winemac.so').is_file(),built
    if slot.is_symlink():
        assert slot.resolve()==built.resolve(), 'Unexpected symlink; left untouched'
    else:
        assert slot.is_dir(), 'Original engine is missing'
        assert not backup.exists() and not backup.is_symlink(), 'Backup already exists; left untouched'
        slot.rename(backup)
        try:
            slot.symlink_to(built, target_is_directory=True)
        except Exception:
            backup.rename(slot)
            raise
    print('Selected:',slot,'->',built)
else:
    if slot.is_symlink() and slot.resolve()==built.resolve():
        assert backup.is_dir(), 'Original backup is missing'
        slot.unlink()
        backup.rename(slot)
    elif backup.exists():
        sys.exit('Unexpected slot contents; left untouched')
    print('Selected original:',slot)
