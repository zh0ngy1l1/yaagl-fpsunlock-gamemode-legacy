#!/usr/bin/env python3
"""Assert that this change preserves all keyboard sources, methods and settings."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
src = Path(sys.argv[1]).resolve()
repo = Path(__file__).resolve().parents[2]
def original(path):
    return subprocess.check_output(['git','show','yaagl-baseline:'+path],cwd=src)
results = {}
for name in ('keyboard.c','cocoa_app.m','cocoa_event.m','cocoa_main.m','event.c'):
    name='dlls/winemac.drv/'+name
    before=original(name); after=(src/name).read_bytes()
    assert before==after, name
    results[name]=hashlib.sha256(after).hexdigest()
# Every pre-existing Cocoa method must match except the window lifecycle methods
# in this patch. New eligibility affects no event, shortcut or modifier methods.
path='dlls/winemac.drv/cocoa_window.m'
def methods(data):
    s=data.decode()
    starts=list(re.finditer(r'^    [+-] \([^\n]+',s,re.M))
    out={}
    for i,m in enumerate(starts):
        end=starts[i+1].start() if i+1<len(starts) else s.find('\n@end',m.start())
        chunk=s[m.start():end].rstrip()
        signature=chunk.split('{',1)[0].strip()
        out[signature]=chunk
    return out
before=methods(original(path)); after=methods((src/path).read_bytes())
allowed=('createWindowWithFeatures:', 'adjustFullScreenBehavior:', 'setWindowFeatures:', 'setFrameFromWine:',
         '- (void) dealloc', 'windowDidExitFullScreen:', 'windowDidFailToEnterFullScreen:', 'windowWillEnterFullScreen:')
assert set(after)-set(before)=={'- (void) restoreNonFullscreenChildFrames'}
changed=[]
for signature, body in before.items():
    if after.get(signature)!=body:
        assert any(x in signature for x in allowed), signature
        changed.append(signature)
results['changed_cocoa_methods']=changed
old=original('dlls/winemac.drv/macdrv_main.c').decode()
new=(src/'dlls/winemac.drv/macdrv_main.c').read_text()
for setting in ('left_option_is_alt','right_option_is_alt','left_command_is_ctrl','right_command_is_ctrl'):
    old_lines=[line for line in old.splitlines() if setting in line]
    new_lines=[line for line in new.splitlines() if setting in line]
    assert old_lines==new_lines, setting
for setting in ('LeftOptionIsAlt','RightOptionIsAlt','LeftCommandIsCtrl','RightCommandIsCtrl'):
    pattern=r'    if \(!get_config_key\(hkey, appkey, "'+setting+r'"[^\n]+\n[^\n]+'
    assert re.search(pattern,old).group()==re.search(pattern,new).group(),setting
for path in ('src/wine','src/launcher','src/config'):
    assert not subprocess.check_output(['git','diff','bf4f5242a41bce71b711fca1bd57f1e1bc06efd6','--',path],cwd=repo),path
results['launcher_vs_start']='identical (wine, launcher, config)'
print(json.dumps(results,indent=2))
