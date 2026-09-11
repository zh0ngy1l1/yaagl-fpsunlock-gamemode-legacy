#!/usr/bin/env python3
"""Explicitly authorized read-only protected source; all writes in fresh output.

This is a metadata experiment, never a binary builder or installer. It cannot
select another source and opens the installed original only O_RDONLY.
"""
from pathlib import Path
import argparse, json, sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import transaction as core

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(); root=args.output
    core._safe_path(root,False)
    core.require(not root.exists(),'Fresh experiment output required')
    core.require(not any(core._inside(root,r) for r in core.PROTECTED_ROOTS),'Protected output forbidden')
    before=core.inspect_file(core.INSTALLED)
    core.check_identity(before,core.ORIGINAL)
    core.require(before['stat']['ino']==2834486 and before['xattrs']=={core.PROVENANCE:'010000dcd5bccdc7edc92e'},'Historical source identity mismatch')
    root.mkdir(mode=0o700); cases=[]
    for number in range(1,4):
        destination=root/('independent-'+str(number)+'.so')
        operation=core._copy_exclusive(core.INSTALLED,destination,15)
        copied=core.inspect_file(destination); core.check_identity(copied,core.ORIGINAL)
        transition=core.required_metadata(before,copied)
        core.require(copied['stat']['ino']!=before['stat']['ino'],'Copy inode is not independent')
        after=core.inspect_file(core.INSTALLED); core.same_instance(before,after)
        cases.append({'number':number,'source_open':'O_RDONLY | O_NOFOLLOW',
                      'operation':operation,'destination':copied,'transition':transition,'source_after':after})
    report={'source_before':before,'cases':cases,'source_unchanged':True,
            'mutations_confined_to':str(root),'runtime_execution':False,
            'core_source_sha256':core.sha(Path(core.__file__).read_bytes())}
    with (root/'RESULTS.json').open('x') as f: json.dump(report,f,indent=2); f.write('\n')
    print(json.dumps({'fresh_independent_copies':len(cases),'source_provenance':before['xattrs'][core.PROVENANCE],
                      'destination_provenance':[c['destination']['xattrs'][core.PROVENANCE] for c in cases],
                      'original_hash_signature_and_required_metadata_passed':True,'installed_source_unchanged':True},indent=2))
if __name__=='__main__': main()
