#!/usr/bin/env python3
"""Read-only protected-product adapter for the shared runtime transaction.

Loads only the pinned read-only snapshot functions from the immutable stopped
transaction. It never calls its preflight/save/copy/install entry points. No live
admission record is created here; the only CLI operation is read-only verification.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, os, re, sys, types
from pathlib import Path
sys.dont_write_bytecode=True
import transaction as core

BASE=Path('/Users/david/Library/Application Support/YAAGL Local Builds/genshin-fps360-20260909')
STOPPED=BASE/'universal-automatic-deployment-review/deployments/20260911T014510484553Z-v2-controlled'
OLD_SCRIPT=STOPPED/'transaction.py'
OLD_HASH='9da889129544a5d514f9346ff24860d40c623e6990337fc8dba5bd659696b13a'
BASELINE_HASH='5ae82c6bcf81e53f8e792a1ff2c4e7d75ef0903a28f80fbad3e3bdd7d087e6c6'
CONTROLS_HASH='8b0822fa062346e5435b0a32db6bc2db97b0e18915304684c59e358d1ad33505'
HELPERS=BASE/'automatic-candidate-preparation/protected-deployment'
HELPER_HASHES={
 'permanent.py':'394f28461ca4caaf111e3a8bcfa4c8525e0d4538ece4df34b0751a6851cde0db',
 'evidence.py':'74c211d35695c017a03d5f2f34599f2790ceb3ff256403baa32678606683d7ae',
 'recovery.py':'6bec6e8a20ab23d7583ad5f1cecc181192fda9404034b6e4142cb9e6ed751175',
 'helper_primitives.py':'34a94377336f63773af68008f700e41e19d8d708cb89b5d2ee7cfba55b6f4e04',
 'resource_primitives.py':'7833b2930cc3c855f4e967a6b7140b0bd8badaa97ef035d85e16718435a09018',
 'prepared.json':'72794d02683290887e876bafc81a22e330f0a9790d732f0c4a2015bbe6f3e34e',
 'recovery-plan.json':'d0c52a515d5ce68a1082570b7fe97f51f57e38c99e9ccffec736456027ac0c6c',
 'original-runtime-inventory.json':'ac80f1bca840c4821b6b39752e01a36af263e67039ada208dfab75e3b00d7d3f',
}
LIB_RELATIVE='wine/lib/wine/x86_64-unix/ntdll.so'
PARENT_RELATIVE='wine/lib/wine/x86_64-unix'

def pinned_read(path,digest):
    snapshot,raw=core.inspect_document(path)
    core.require(snapshot['sha256']==digest,'Protected adapter dependency hash mismatch: '+str(path))
    return raw

def normalize(snapshot,transaction_id,allowed_phases=frozenset()):
    """Only the reviewed slot and the two exact owned temporary names may vary.

    APFS directory size counts 32 bytes per entry on this reviewed machine. A
    temporary increases the parent size by exactly one entry; retain that guard,
    rather than ignore directory size wholesale. Parent mtime/ctime naturally
    advance on entry changes. No other directory metadata is normalized.
    """
    core.require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}',transaction_id) is not None,'Unsupported transaction ID')
    value=copy.deepcopy(snapshot); tree=value['runtime_tree']
    core.require(LIB_RELATIVE in tree and PARENT_RELATIVE in tree,'Selected runtime slot or parent absent from inventory')
    library=tree.pop(LIB_RELATIVE)
    core.require(library['sha256'] in (core.ORIGINAL,core.CANDIDATE),'Unknown selected-runtime identity')
    removed=[]
    for phase,digest in (('deploy',core.CANDIDATE),('restore',core.ORIGINAL)):
        name=PARENT_RELATIVE+'/.ntdll-'+transaction_id+'-'+phase+'.tmp'
        if name in tree:
            core.require(phase in allowed_phases,'Unowned or out-of-phase runtime temporary')
            temp=tree.pop(name)
            core.require(temp.get('sha256')==digest and temp['stat']['size']==core.SIZE and temp['stat']['nlink']==1,'Invalid owned temporary in protected inventory')
            removed.append(name)
    parent=tree[PARENT_RELATIVE]['stat']
    parent['size']-=32*len(removed)
    parent.pop('mtime_ns'); parent.pop('ctime_ns')
    return value

class ProtectedGuard:
    def __init__(self,transaction_id,transaction_root=None):
        self.transaction_id=transaction_id; self.transaction_root=Path(transaction_root) if transaction_root else None
        source=pinned_read(OLD_SCRIPT,OLD_HASH)
        self.expected=json.loads(pinned_read(STOPPED/'02-before.json',BASELINE_HASH))
        self.controls=json.loads(pinned_read(STOPPED/'03c-metadata-controls.json',CONTROLS_HASH))
        match_historical_parents(self.controls['parents'])
        for name,digest in HELPER_HASHES.items(): pinned_read(HELPERS/name,digest)
        # Never permit a same-name imported module from an unreviewed directory.
        for name in ('recovery','resource_primitives','helper_primitives','evidence','permanent'):
            if name in sys.modules:
                module=sys.modules[name]
                core.require(Path(module.__file__).resolve()==HELPERS/(name+'.py'),'Unreviewed cached protected helper module')
        self.old=types.ModuleType('_immutable_stopped_read_only_functions')
        self.old.__file__=str(OLD_SCRIPT)
        exec(compile(source,str(OLD_SCRIPT),'exec'),self.old.__dict__)
        self.permanent,self.evidence=self.old.initialize()
        self.normalized_expected=normalize(self.expected,transaction_id)
    def __call__(self):
        # Recheck dependencies before executing cached helper bytecode.
        pinned_read(OLD_SCRIPT,OLD_HASH); pinned_read(STOPPED/'02-before.json',BASELINE_HASH)
        pinned_read(STOPPED/'03c-metadata-controls.json',CONTROLS_HASH); match_historical_parents(self.controls['parents'])
        for name,digest in HELPER_HASHES.items(): pinned_read(HELPERS/name,digest)
        self.old.initialize()  # Also verifies frozen source worktrees/artifact manifest.
        snapshot=self.old.snapshot(self.evidence,self.permanent)
        normalized=normalize(snapshot,self.transaction_id,allowed_temporary_phases(self.transaction_root) if self.transaction_root else frozenset())
        core.require(normalized==self.normalized_expected,'Protected product differs from the immutable pre-deployment baseline')
        return normalized

def allowed_temporary_phases(root):
    # A name/hash alone never establishes ownership. Require the fresh admission
    # and durable stage ledger; exclusive creation/inode checks remain in the core.
    root=Path(root); _,admission_raw=core.inspect_document(root/'admission.json')
    admission=json.loads(admission_raw); admission_hash=core.sha(admission_raw)
    core.require(admission['root']==str(root) and admission['transaction_id']==root.name,'Temporary admission binding mismatch')
    journal=root/'journal'; result=set()
    for phase,digest in (('deploy',core.CANDIDATE),('restore',core.ORIGINAL)):
        plan=journal/(phase+'-stage-plan.json')
        if not plan.exists(): continue
        _,raw=core.inspect_document(plan); value=json.loads(raw); seal=value.pop('_record_seal',None)
        core.require(seal=={'sha256':core.sha(core.canonical_json(value)),'admission_sha256':admission_hash},'Temporary stage ledger seal mismatch')
        expected=Path(admission['slot']).parent/('.ntdll-'+root.name+'-'+phase+'.tmp')
        core.require(value['destination']==str(expected) and value['expected_hash']==digest,'Unexpected temporary stage ledger')
        if (journal/(phase+'-complete.json')).exists() or (journal/'restored-idempotent.json').exists(): continue
        if phase=='deploy' and (journal/'restore-stage-plan.json').exists(): continue
        if phase=='restore': core.require((journal/'deploy-intent.json').exists(),'Restoration stage has no deployment lineage')
        result.add(phase)
    return frozenset(result)

def match_historical_parents(parents):
    # Historical records contain stat identities, not serialized parent ACLs.
    # Compare every recorded field; do not refresh them from current directories.
    # Native ACLs are also read here and bound exactly in the fresh admission.
    current={}
    for path,expected in parents.items():
        actual=core.directory_identity(Path(path))
        core.require(all(actual['stat'].get(k)==v for k,v in expected.items()),'Historical parent identity or metadata mismatch: '+path)
        current[path]=actual
    return current

def match_historical_file(current, historical):
    core.require(current['path']==historical['path'] and current['resolved']==historical['resolved'],'Historical runtime path mismatch')
    core.require(current['sha256']==historical['sha256'],'Historical runtime hash mismatch')
    core.require(all(current['stat'].get(k)==v for k,v in historical['stat'].items()),'Historical runtime metadata mismatch')
    core.require(current['xattrs']==historical['xattrs'],'Historical runtime xattr mismatch')

def match_historical_acl(current, historical):
    if historical['state']=='absence corroborated by native ls -e':
        core.require(current=={'state':'absent','errno':2},'Historical ACL absence mismatch')
    else:
        core.require(current['state']=='present' and current['serialized_hex']==historical['serialized_hex'],'Historical ACL content mismatch')

def create_authorized_admission(root, authorization_reference, *, managed_provenance_transition_authorized,
                                reviewed_core_sha256, reviewed_adapter_sha256, reviewed_procedure_sha256):
    """Future-only fresh admission builder; no installed-tree or prefix writes.

    The hash arguments must come from the reviewed package, not be refreshed from
    current files. This function is intentionally absent from the CLI. Calling it
    requires a NEW explicit user authorization, including the managed lineage rule.
    It validates against immutable historical records before creating external
    transaction directories. No runtime replacement follows automatically.
    """
    root=Path(root); procedure=Path(__file__).resolve().parent.parent/'DEPLOYMENT.md'
    core.require(core._build()==core.EXPECTED_BUILD,'Unreviewed macOS build')
    core.require(isinstance(authorization_reference,str) and bool(authorization_reference.strip()),'Explicit authorization reference required')
    core.require(managed_provenance_transition_authorized is True,'Managed provenance transition is not authorized')
    core.require(not os.path.lexists(root),'Fresh transaction root required')
    core.require(not core._inside(root,STOPPED) and root.name!=STOPPED.name,'Stopped transaction cannot be resumed or reused')
    core.require(not any(core._inside(root,r) for r in core.PROTECTED_ROOTS),'External transaction root required')
    core._safe_path(root,False)
    core.require(root.parent.stat().st_dev==core.INSTALLED.stat().st_dev,'Unreviewed cross-filesystem rollback location')
    for path,digest in ((Path(core.__file__),reviewed_core_sha256),(Path(__file__),reviewed_adapter_sha256),(procedure,reviewed_procedure_sha256)):
        core.require(core.sha(path.read_bytes())==digest,'Reviewed deployment input mismatch: '+str(path))
    historical=json.loads(pinned_read(STOPPED/'03-original-and-staged.json','a7e46c9342d0995542af3482cacc4c8bad6cc58b77a573ef77465456ebe3f03a'))
    controls=json.loads(pinned_read(STOPPED/'03c-metadata-controls.json',CONTROLS_HASH))
    match_historical_parents(controls['parents'])
    original=core.inspect_file(core.INSTALLED); candidate=core.inspect_file(core.REVIEWED_CANDIDATE)
    match_historical_file(original,historical['original']); match_historical_file(candidate,historical['staged'])
    match_historical_acl(original['acl'],controls['original_acl']); match_historical_acl(candidate['acl'],controls['staged_acl'])
    core.check_identity(original,core.ORIGINAL); core.check_identity(candidate,core.CANDIDATE)
    core.require(original['xattrs'].get(core.PROVENANCE)=='010000dcd5bccdc7edc92e','Protected original provenance mismatch')
    core.check_provenance(candidate,generated=True)
    guard=ProtectedGuard(root.name); state=guard()
    # Everything above is read-only. Everything below creates external admission
    # material only. The same native directory-bound APIs protect these creations.
    parent_fd=core._open_parent(root)
    try: os.mkdir(root.name,0o700,dir_fd=parent_fd); os.fsync(parent_fd)
    finally: os.close(parent_fd)
    root_identity=core.directory_identity(root)
    root_fd=core._open_parent(root/'entry',root_identity)
    try:
        for name in ('journal','rollback'): os.mkdir(name,0o700,dir_fd=root_fd)
        os.fsync(root_fd)
    finally: os.close(root_fd)
    admission={'mode':'controlled-deployment','transaction_id':root.name,'root':str(root),
               'root_identity':{k:core.stat_record(root.stat())[k] for k in ('dev','ino')},
               'slot':str(core.INSTALLED),'original':str(core.REVIEWED_ORIGINAL),'candidate':str(core.REVIEWED_CANDIDATE),
               'macos_build':core._build(),'original_hash':core.ORIGINAL,'candidate_hash':core.CANDIDATE,
               'authorization_reference':authorization_reference,'managed_provenance_transition_authorized':True,
               'expected_slot':original,'expected_candidate':candidate,'protected_state_sha256':core.sha(core.canonical_json(state)),
               'reviewed_core_sha256':reviewed_core_sha256,'reviewed_adapter_sha256':reviewed_adapter_sha256,
               'reviewed_procedure_sha256':reviewed_procedure_sha256,'procedure_path':str(procedure),
               'parent_bindings':core.parent_bindings([core.INSTALLED,core.REVIEWED_ORIGINAL,core.REVIEWED_CANDIDATE,root/'journal'/'entry',root/'rollback'/'ntdll.so'])}
    parent_fd=core._open_parent(root/'admission.json',root_identity); fd=None
    try:
        fd=os.open('admission.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent_fd)
        with os.fdopen(fd,'wb',closefd=False) as f:
            f.write(core.canonical_json(admission)+b'\n'); f.flush(); os.fsync(fd)
        os.fsync(parent_fd)
    finally:
        if fd is not None: os.close(fd)
        os.close(parent_fd)
    core.same_instance(original,core.inspect_file(core.INSTALLED)); core.same_instance(candidate,core.inspect_file(core.REVIEWED_CANDIDATE))
    guard()  # Final read-only baseline recheck; mismatch retains external evidence.
    return admission

def authorized_transaction(root):
    """Future authorized factory; does not create authorization/admission itself.

    Calling this factory in the current offline turn is forbidden. The caller must
    supply the new reviewed admission record after fresh explicit authorization.
    The class constructor independently requires the exact live path, old baseline
    provenance, reviewed hashes/build and explicit metadata-transition admission.
    """
    root=Path(root)
    _,raw=core.inspect_document(root/'admission.json'); admission=json.loads(raw)
    core.require(core.sha(Path(__file__).read_bytes())==admission['reviewed_adapter_sha256'],'Production adapter identity mismatch')
    return core.RuntimeTransaction(root,protected_guard=ProtectedGuard(root.name,root),production=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--verify-read-only',action='store_true',required=True)
    p.add_argument('--transaction-id',required=True)
    args=p.parse_args()
    result=ProtectedGuard(args.transaction_id)()
    print(json.dumps({'read_only_protected_verification':'passed','sha256':core.sha(core.canonical_json(result)),
                      'transaction_id':args.transaction_id,'product_mutation':False,'product_execution':False},indent=2))
if __name__=='__main__': main()
