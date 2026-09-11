#!/usr/bin/env python3
"""Build the tested Wine 11.0 Game Mode bundle without changing an installed engine."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shlex
import subprocess


def run(args):
    print(shlex.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--work', type=Path, default=Path(os.environ.get(
    'YAAGL_WINE_WORK', '/Users/david/code/home/yaagl-wine-fullscreen')))
parser.add_argument('--output', type=Path, required=True, help='New staging directory')
args = parser.parse_args()
work, output = args.work.resolve(), args.output.resolve()
source = work / 'wine-wine-11.0'
main = source / 'loader/main.c'
if '/WineGame.app/Contents/MacOS' not in main.read_text():
    parser.error('Apply bundle-loader.patch to the Wine source first')
if '#define PACKAGE_VERSION "11.0"' not in (work / 'build/include/config.h').read_text():
    parser.error('This recipe requires the configured Wine 11.0 build')

# Match the one-key experiment, including the size of its embedded section.
# The original generated plist and all window/keyboard sources stay untouched.
original = (work / 'build/loader/wine_info.plist').read_bytes()
info = plistlib.loads(original)
if 'LSSupportsGameMode' in info or info.get('CFBundleExecutable') != 'wine':
    parser.error('Unexpected baseline loader plist')
changed = original.replace(b'</dict>', b'    <key>LSSupportsGameMode</key>\n    <true/>\n</dict>')
changed = re.sub(rb'(?m)^ +', b'', changed)
if len(changed) > len(original):
    parser.error('Opt-in plist no longer fits the baseline section')
changed += b' ' * (len(original) - len(changed))
info['LSSupportsGameMode'] = True
if plistlib.loads(changed) != info:
    parser.error('Unexpected plist transformation')

output.mkdir(parents=True, exist_ok=False)
plist = output / 'wine_info.plist'
plist.write_bytes(changed)
copy = output / 'main.c'
copy.write_bytes(main.read_bytes())
obj = output / 'main.o'
run(['clang', '-arch', 'x86_64', '-m64', '-c', '-o', obj, copy,
     '-I' + str(source / 'loader'), '-I' + str(work / 'build/include'),
     '-I' + str(source / 'include'), '-D__WINESRC__', '-DWINE_UNIX_LIB',
     '-fPIE', '-fvisibility=hidden', '-fno-stack-protector', '-fno-strict-aliasing',
     '-fcf-protection=none', '-O2', '-mmacosx-version-min=14.0',
     '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0'])
app = output / 'WineGame.app'
binary = app / 'Contents/MacOS/wine'
binary.parent.mkdir(parents=True)
(app / 'Contents/Info.plist').write_bytes(plistlib.dumps(info, sort_keys=False))
# Preserve the selected loader's zero-fill address reservations and link layout.
# Its observed LC_BUILD_VERSION minimum is 26.0, also used by the validated bundle.
run(['clang', '-arch', 'x86_64', '-m64', '-mmacosx-version-min=26.0', '-o', binary, obj,
     '-Wl,-segalign,0x1000,-pagezero_size,0x1000,-sectcreate,__TEXT,__info_plist,' + str(plist),
     '-Wl,-no_pie,-image_base,0x200000000,-no_huge,-no_fixup_chains,-segalign,0x1000,'
     '-segaddr,WINE_RESERVE,0x1000,-segaddr,WINE_TOP_DOWN,0x7ff000000000',
     '-L' + str(work / 'runtime/lib'), '-Wl,-rpath,' + str(work / 'runtime/lib')])
run(['install_name_tool', '-delete_rpath', work / 'runtime/lib', binary])
run(['codesign', '--force', '--sign', '-', app])
run(['codesign', '--verify', '--deep', '--strict', app])

forwarder = output / 'forwarder'
forwarder_source = Path(__file__).with_name('forwarder.c')
run(['clang', '-arch', 'x86_64', '-mmacosx-version-min=14.0', '-O2',
     '-Wall', '-Wextra', forwarder_source, '-o', forwarder])
run(['codesign', '--force', '--sign', '-', forwarder])
run(['codesign', '--verify', '--strict', forwarder])
record = {
    'wineSourceRevision': subprocess.check_output(
        ['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip(),
    'loaderSourceSHA256': digest(main),
    'forwarderSourceSHA256': digest(forwarder_source),
    'files': {str(p.relative_to(output)): digest(p) for p in sorted(app.rglob('*')) if p.is_file()},
    'plist': info,
}
record['files']['forwarder'] = digest(forwarder)
(output / 'build.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2))
