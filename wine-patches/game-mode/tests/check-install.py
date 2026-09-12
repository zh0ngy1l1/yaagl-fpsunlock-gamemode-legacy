#!/usr/bin/env python3
"""Exercise installation against a disposable copy of the published components."""
import hashlib,os,shutil,subprocess,sys,tempfile,time
from pathlib import Path
support=Path(sys.argv[1]).resolve(); runtime=Path(sys.argv[2]).resolve()
def hashes(root): return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
def run(args,ok=True):
    p=subprocess.run(list(map(str,args)),capture_output=True,text=True)
    assert (p.returncode==0)==ok,p.stdout+p.stderr
    return p.stdout+p.stderr
with tempfile.TemporaryDirectory(prefix='yaagl-support-install-') as d:
    root=Path(d); engine=root/'wine'; native=engine/'lib/wine/x86_64-unix'
    native.mkdir(parents=True)
    for name in ['wine','ntdll.so','winemac.so']: shutil.copy2(runtime/'lib/wine/x86_64-unix'/name,native/name)
    for arch in ['x86_64-windows','i386-windows']:
        target=engine/'lib/wine'/arch/'winemac.drv';target.parent.mkdir(parents=True)
        shutil.copy2(runtime/'lib/wine'/arch/'winemac.drv',target)
    command=['bash',support/'install-support.sh',engine,support]
    run(command)
    installed=hashes(engine);run(command);assert hashes(engine)==installed
    run(['codesign','--verify','--deep','--strict',native/'WineGame.app'])
    hold=root/'hold.c';hold.write_text('#include <unistd.h>\nint main(void){sleep(20);return 0;}\n')
    run(['clang',hold,'-o',engine/'hold'])
    child=subprocess.Popen([str(engine/'hold')])
    try:
        time.sleep(.2);assert child.poll() is None
        before=hashes(engine);run(command);assert hashes(engine)==before  # no-op while active
        (engine/'.native-fullscreen.sha256').write_text('old payload')
        before=hashes(engine)
        assert 'Quit applications using this Wine engine' in run(command,False)
        assert hashes(engine)==before
    finally: child.terminate();child.wait()
    (native/'ntdll.so').write_bytes(b'unsupported engine')
    before=hashes(engine)
    assert 'does not match this Wine engine' in run(command,False)
    assert hashes(engine)==before
print('Signed install, idempotence, no-op while active, blocked live upgrade, and unsupported-engine refusal passed.')
