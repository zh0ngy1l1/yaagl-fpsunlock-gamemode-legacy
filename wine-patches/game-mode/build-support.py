#!/usr/bin/env python3
"""Package both signed loader targets and the unchanged validated fullscreen driver."""
import argparse, hashlib, json, plistlib, shutil, subprocess, tempfile
from pathlib import Path

def run(*args): subprocess.run(list(map(str,args)),check=True)
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--work',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args(); work=args.work.resolve(); out=args.output.resolve()
source=work/'wine-wine-11.0'; here=Path(__file__).resolve().parent
if 'select_game_bundle' not in (source/'loader/main.c').read_text():
    parser.error('Apply the production native-fullscreen-loader.patch first')
out.mkdir(parents=True,exist_ok=False)
with tempfile.TemporaryDirectory(prefix='yaagl-fullscreen-build-') as d:
    stage=Path(d); obj=stage/'main.o'; payload=stage/'payload'; native=payload/'lib/wine/x86_64-unix'
    native.mkdir(parents=True)
    run('clang','-arch','x86_64','-m64','-c','-o',obj,source/'loader/main.c',
        '-I'+str(source/'loader'),'-I'+str(work/'build/include'),'-I'+str(source/'include'),
        '-D__WINESRC__','-DWINE_UNIX_LIB','-fPIE','-fvisibility=hidden','-fno-stack-protector',
        '-fno-strict-aliasing','-fcf-protection=none','-O2','-mmacosx-version-min=14.0',
        '-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0')
    info=plistlib.loads((work/'build/loader/wine_info.plist').read_bytes())
    assert 'LSSupportsGameMode' not in info
    for bundled in [False,True]:
        data=dict(info)
        if bundled: data['LSSupportsGameMode']=True
        plist=stage/('game.plist' if bundled else 'ordinary.plist')
        plist.write_bytes(plistlib.dumps(data,sort_keys=False))
        app=native/'WineGame.app'; binary=app/'Contents/MacOS/wine' if bundled else native/'wine'
        binary.parent.mkdir(parents=True,exist_ok=True)
        if bundled: shutil.copy2(plist,app/'Contents/Info.plist')
        run('clang','-arch','x86_64','-m64','-mmacosx-version-min=14.0','-o',binary,obj,
            '-Wl,-segalign,0x1000,-pagezero_size,0x1000,-sectcreate,__TEXT,__info_plist,'+str(plist),
            '-Wl,-no_pie,-image_base,0x200000000,-no_huge,-no_fixup_chains,-segalign,0x1000,'
            '-segaddr,WINE_RESERVE,0x1000,-segaddr,WINE_TOP_DOWN,0x7ff000000000')
        run('codesign','--force','--sign','-',app if bundled else binary)
        run('codesign','--verify','--deep','--strict',app if bundled else binary)
    # Copy both PE sides of the driver as well as its Cocoa Unix implementation.
    for rel in ['x86_64-unix/winemac.so','x86_64-windows/winemac.drv','i386-windows/winemac.drv']:
        dest=payload/'lib/wine'/rel; dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(work/'dist/wine/lib/wine'/rel,dest)
    files={str(p.relative_to(payload)):sha(p) for p in sorted(payload.rglob('*')) if p.is_file()}
    (payload/'files.sha256').write_text(''.join(f'{digest}  {name}\n' for name,digest in files.items()))
    run('tar','-czf',out/'payload.tar.gz','-C',payload,'.')
    (out/'payload.sha256').write_text(sha(out/'payload.tar.gz')+'  payload.tar.gz\n')
    (out/'compatible-ntdll.txt').write_text('\n'.join(sorted({sha(work/p/'lib/wine/x86_64-unix/ntdll.so') for p in ['runtime','dist/wine']}))+'\n')
    run('clang','-arch','arm64','-arch','x86_64','-O2','-Wall','-Wextra','-mmacosx-version-min=14.0',
        here/'check-idle.c','-o',out/'check-idle')
    run('codesign','--force','--sign','-',out/'check-idle')
    shutil.copy2(here/'install-support.sh',out/'install-support.sh')
    # Keep the license text while avoiding upstream trailing blank-line spaces.
    (out/'COPYING.LIB').write_text('\n'.join(line.rstrip() for line in (source/'COPYING.LIB').read_text().splitlines())+'\n')
    (out/'provenance.json').write_text(json.dumps({'distribution':'11.0-dxmt-signed-with-patches',
        'wineSourceHead':subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip(),
        'loaderSourceSHA256':sha(source/'loader/main.c'),
        'fullscreenBaseline':'bc9a0e81d168c99bb63ed716b0455245144aadc7',
        'reproduction':'wine-patches/game-mode/build-support.py','files':files},indent=2)+'\n')
print(out)
