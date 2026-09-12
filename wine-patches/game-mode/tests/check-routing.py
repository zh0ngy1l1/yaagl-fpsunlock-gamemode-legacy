#!/usr/bin/env python3
import json, os, subprocess, sys, tarfile, tempfile
from pathlib import Path
support=Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix='yaagl-native-routing-') as d:
    root=Path(d)
    with tarfile.open(support/'payload.tar.gz') as archive: archive.extractall(root,filter='data')
    native=root/'lib/wine/x86_64-unix'; loader=native/'wine'; app=native/'WineGame.app'
    subprocess.run(['clang','-arch','x86_64','-dynamiclib','-mmacosx-version-min=14.0',
        '-framework','Foundation',str(Path(__file__).with_name('loader-probe.m')),
        '-o',str(native/'ntdll.so')],check=True)
    args=['unchanged argv[0]', 'C:\\game dir\\GenshinImpact.exe','', 'a "quote"',"a'b",'$HOME; $(touch nope)', '日本語']
    for flag in ['1','0','1',None,'true']:
        readfd,writefd=os.pipe()
        environment={'PATH':'/usr/bin:/bin','KEPT':'spaces and $literal\nnext line','PROBE_FD':str(writefd)}
        if flag is not None: environment['YAAGL_NATIVE_FULLSCREEN']=flag
        child=subprocess.Popen(args,executable=loader,cwd=root,env=environment,pass_fds=(writefd,),stdout=subprocess.PIPE)
        os.close(writefd); output,_=child.communicate(timeout=20)
        assert child.returncode==0,child.returncode
        actual=json.loads(output)
        assert actual['pid']==child.pid
        assert actual['args']==args,actual
        assert Path(actual['cwd']).resolve()==root.resolve()
        # Foundation may initialize this macOS bookkeeping variable itself.
        env=actual['environment']; env.pop('__CF_USER_TEXT_ENCODING',None)
        assert env==environment,(env,environment)
        assert os.read(readfd,20)==b'inherited';os.close(readfd)
        expected=app/'Contents/MacOS/wine' if flag=='1' else loader
        assert Path(actual['executable']).resolve()==expected.resolve()
        assert actual['gameMode']==(flag=='1'),actual
        assert Path(actual['bundlePath']).resolve()==(app if flag=='1' else native).resolve(),actual
    # A missing ON target must fail, not quietly start an unbundled game.
    (app/'Contents/MacOS/wine').rename(app/'Contents/MacOS/removed')
    result=subprocess.run([str(loader)],env={'YAAGL_NATIVE_FULLSCREEN':'1'},capture_output=True)
    assert result.returncode!=0 and b'cannot exec native fullscreen loader' in result.stderr
print('Routing, argv (including argv[0]), environment, PID, cwd, inherited FD, plist identity, and missing-target checks passed.')
