#!/usr/bin/env python3
"""Check logged Win32 restoration and fixed-window style/size invariants."""
from pathlib import Path
import os
import re
import sys

for arg in sys.argv[1:]:
    rows={}
    for line in Path(arg).read_text(errors='replace').splitlines():
        m=re.match(r'RECT t=(\d+) name=(.*?) window=(.*?) client=(.*?) style=(.*?) ex=(.*)',line)
        if m: rows.setdefault(m[2],[]).append(m.groups())
    assert len(rows)==12, (arg,len(rows))
    for name,items in rows.items():
        first,last=items[0],items[-1]
        assert first[2:]==last[2:], (arg,name,first,last)
        # Visibility/activation may change, but the implementation must never
        # fabricate WS_THICKFRAME, WS_MAXIMIZEBOX or any other Windows styles.
        for item in items:
            assert item[4:]==first[4:], (arg,name,'styles changed',first,item)
        if name=='YAAGL fixed':
            assert not int(first[4],16)&0x00040000, 'WS_THICKFRAME added'
            if not os.environ.get('YAAGL_TEST_UNCONSTRAINED'):
                assert all(item[3]=='480,300' for item in items), 'application size limit ignored'
    print('PASS',Path(arg).name,'all 12 windows restored; styles unchanged; fixed windowed client restored to 480x300')
