#!/usr/bin/env python3
"""Check the engine-switch guard with mocked processes; never switch an engine."""
from pathlib import Path
import os
import runpy
import sys
from unittest.mock import patch

script = Path(__file__).resolve().parents[1] / 'select-engine.py'
base = Path.home() / 'Library/Application Support/Yaagl OS'
work = Path('/Users/david/code/home/yaagl-wine-fullscreen')
roots = (base / 'hoyoplay-wines/genshin/11.0-dxmt-signed-with-patches/wine',
         base / 'wine', work / 'dist/wine')
checks = 0
for root in roots:
    for binary in ('bin/wine', 'bin/wineserver'):
        for action in ('built', 'original'):
            with patch.dict(os.environ, {'YAAGL_WINE_WORK': str(work)}), \
                 patch.object(sys, 'argv', [str(script), action]), \
                 patch('subprocess.check_output', return_value=f'123 {root / binary}\n'), \
                 patch.object(Path, 'rename', side_effect=AssertionError('unexpected rename')), \
                 patch.object(Path, 'unlink', side_effect=AssertionError('unexpected unlink')), \
                 patch.object(Path, 'symlink_to', side_effect=AssertionError('unexpected symlink')):
                try:
                    runpy.run_path(str(script), run_name='__main__')
                except SystemExit as exc:
                    assert str(exc).startswith('A YAAGL Wine process is running;'), exc
                else:
                    raise AssertionError(f'Guard did not reject {root / binary}')
            checks += 1
print(f'PASS {checks} mocked active-process cases rejected before engine selection')
