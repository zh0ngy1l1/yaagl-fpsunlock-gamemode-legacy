#!/usr/bin/env python3
"""Check engine architecture, signing, relocatable loads, and retained dependencies."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
work=Path(sys.argv[1]).resolve()
root=work/'dist/wine'
deps=work/'runtime/lib'
paths=json.loads((work/'logs/built-macho.sha256.json').read_text())
for rel in paths:
    p=root/rel
    subprocess.run(['codesign','--verify',str(p)],check=True,capture_output=True)
    desc=subprocess.check_output(['file',str(p)],text=True)
    assert 'x86_64' in desc,desc
    data='\n'.join(subprocess.check_output(['otool','-L',str(p)],text=True).splitlines()[1:])
    assert '/opt/homebrew' not in data and '/opt/local/' not in data and str(work) not in data,(rel,data)
print('PASS',len(paths),'built native binaries are x86_64, signed and free of absolute build/dependency load paths')
n=0
for p in deps.rglob('*'):
    if not p.is_file() or p.is_symlink() or 'wine' in p.relative_to(deps).parts: continue
    target=root/'lib'/p.relative_to(deps)
    assert hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256(target.read_bytes()).digest(),target
    n+=1
print('PASS',n,'external dependency files match the existing engine')
for arch,kind in (('x86_64','PE32+'),('i386','PE32 ')):
    for name in ('ntdll.dll','winemac.drv'):
        desc=subprocess.check_output(['file',str(root/'lib/wine'/f'{arch}-windows'/name)],text=True)
        assert kind in desc,desc
print('PASS both x86_64 and i386 Windows modules installed')
exports=subprocess.check_output(['nm','-gU',str(root/'lib/wine/x86_64-unix/winemac.so')],text=True)
assert '_macdrv_functions' in exports and '___wine_unix_call_wow64_funcs' in exports
print('PASS DXMT and WoW64 driver exports retained')
