#!/usr/bin/env python3
"""Fetch the pinned distribution source and matching SDK headers; no system MacPorts install.

Requires Homebrew mingw-w64, bison, pkgconf and autoconf; Apple Command Line Tools;
x86-64 Rosetta execution. The supplied installed engine is used only for its
existing external dependencies and as a baseline test engine.
"""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request

work = Path(os.environ.get('YAAGL_WINE_WORK', '/Users/david/code/home/yaagl-wine-fullscreen')).resolve()
original = Path(os.environ.get('YAAGL_ORIGINAL_ENGINE', str(Path.home() / 'Library/Application Support/Yaagl OS/hoyoplay-wines/genshin/11.0-dxmt-signed-with-patches/wine')))
if 'YAAGL_ORIGINAL_ENGINE' not in os.environ and original.with_name('wine.original-before-fixed-fullscreen').is_dir():
    original = original.with_name('wine.original-before-fixed-fullscreen')
here = Path(__file__).resolve().parent
if (work / 'wine-wine-11.0').exists():
    sys.exit('Source directory already exists; use it as-is or choose a fresh YAAGL_WINE_WORK. Nothing was overwritten.')
for name in ('downloads', 'deps', 'logs'):
    (work/name).mkdir(parents=True, exist_ok=True)
def run(*args, **kw):
    return subprocess.run(args, check=True, **kw)
def download(name, url, sha256):
    path = work/'downloads'/name
    if not path.exists():
        urllib.request.urlretrieve(url, path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
        sys.exit('Checksum mismatch: '+str(path))
    return path
wine = download('wine-11.0.tar.gz', 'https://github.com/wine-mirror/wine/archive/refs/tags/wine-11.0.tar.gz',
                'f09e8153aa46a581d2b56a5b1363b04832070b9409d9244a68cf482b243ff14a')
if not (work/'macports-wine/.git').exists():
    run('git', 'clone', 'https://github.com/riverfog7/macports-wine.git', str(work/'macports-wine'))
# Refuse to overwrite edits in a pre-existing overlay checkout.
assert not subprocess.check_output(['git','status','--porcelain'], cwd=work/'macports-wine')
run('git','switch','--detach','0d029255bce8f2f4ac47a1984b59ba82e09d9829',cwd=work/'macports-wine')
run('tar','-xf',str(wine),'-C',str(work))
src = work/'wine-wine-11.0'
run('git','init','-q',cwd=src)
run('git','add','.',cwd=src)
def commit(message):
    run('git','-c','user.name=YAAGL Local Build','-c','user.email=local@invalid','commit','-qm',message,cwd=src)
commit('Wine 11.0 archive db11d0fe6a169c457e23d007e20404643d067aa8')
port = work/'macports-wine/emulators/wine-devel'
text = (port/'Portfile').read_text().split('configure.checks.implicit_function_declaration')[0]
patches = re.findall(r'^    (\S+\.patch)',text,re.M)
with (work/'logs/downstream-patches.log').open('w') as log:
    for patch in patches:
        run('patch','-p1','--batch','--fuzz=0','-i',str(port/'files'/patch),cwd=src,stdout=log,stderr=subprocess.STDOUT)
for name in ('configure','configure.ac'):
    p = src/name
    p.write_text(''.join(line for line in p.read_text().splitlines(keepends=True) if 'PKG_CONFIG_LIBDIR' not in line))
(work/'logs/downstream-series.txt').write_text('\n'.join(patches)+'\n')
run('git','add','.',cwd=src)
commit('Apply wine-11.0-fix overlay 0d029255bce8f2f4ac47a1984b59ba82e09d9829')
run('git','tag','yaagl-baseline',cwd=src)
run('git','apply',str(here/'allow-fixed-size-fullscreen.patch'),cwd=src)
for name, url, checksum in (
 ('gnutls-devel-3.8.13_0.darwin_24.x86_64.tbz2','https://packages.macports.org/gnutls-devel/gnutls-devel-3.8.13_0.darwin_24.x86_64.tbz2','c3914242829ba35db15031e96d0eec6b6b3f7c50d1b71ff07f7c4eef599827d9'),
 ('libsdl2-2.32.10_2.darwin_24.x86_64.tbz2','https://packages.macports.org/libsdl2/libsdl2-2.32.10_2.darwin_24.x86_64.tbz2','4c4ddefa8c5f859f3c4ff54534abb3f67d48a824de3899fc814a6768afd03740'),
 ('libinotify-20240724.tar.gz','https://github.com/libinotify-kqueue/libinotify-kqueue/archive/refs/tags/20240724.tar.gz','120398ff95336d04f3ce7ac820e0490059625976264100dcc9af9d11e992b0ca')):
    p = download(name,url,checksum)
    args = ['tar','-xf',str(p),'-C',str(work/'deps')]
    if name.endswith('.tbz2'): args.append('opt/local/include')
    run(*args)
(work/'deps/opt/local/include/sys').mkdir(parents=True, exist_ok=True)
shutil.copy2(work/'deps/libinotify-kqueue-20240724/sys/inotify.h',
             work/'deps/opt/local/include/sys/inotify.h')
# APFS clone where available; a full normal copy is also fine.
assert not (work/'runtime').exists()
run('cp','-cR',str(original),str(work/'runtime'))
for alias, target in {'libfreetype.dylib':'libfreetype.6.dylib','libgnutls.dylib':'libgnutls.30.dylib',
    'libSDL2.dylib':'libSDL2-2.0.0.dylib','libinotify.dylib':'libinotify.0.dylib',
    'libintl.dylib':'libintl.8.dylib','libpcap.dylib':'libpcap.A.dylib'}.items():
    link=work/'runtime/lib'/alias
    if not link.exists() and not link.is_symlink():
        link.symlink_to(target)
print('Prepared:', work)
