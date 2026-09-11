#!/usr/bin/env python3
"""Static, descriptor-bound runtime replacement; never builds, signs or loads code.

Replica CLI is the only command-line mutation admission. A future production caller
must separately supply a fresh authorization record and the protected-product guard.
The copy, verification, journal, replacement and restoration bodies are shared.
"""
from __future__ import annotations
import argparse, ctypes, datetime, errno, hashlib, json, os, platform, stat, subprocess
from pathlib import Path
from typing import Callable

ORIGINAL = 'f26ade35f5b49e33b3780b6adc71f9eb9c831ea40222c1bae667ac14135d984b'
CANDIDATE = 'eef64f611ae9033261a70f46ec0be38d58823717f14e80331946c6d0cd3c85f7'
SIZE = 620688
IDENTIFIER = 'ntdll-55554944a111d5d496a533f9923073e9beb51434'
PROVENANCE = 'com.apple.provenance'
# Exact locally reviewed states, opaque: these are not a general macOS format parser.
PROVENANCE_VALUES = frozenset(('010000dcd5bccdc7edc92e', '01020059c71153554e5113'))
GENERATED_PROVENANCE = '01020059c71153554e5113'
EXPECTED_BUILD = '25G83'
INSTALLED = Path('/Users/david/Library/Application Support/Yaagl OS/hoyoplay-wines/genshin/11.0-dxmt-signed-with-patches/wine/lib/wine/x86_64-unix/ntdll.so')
REVIEWED_ARTIFACTS = Path('/Users/david/Library/Application Support/YAAGL Local Builds/genshin-fps360-20260909/universal-automatic-deployment-review/artifacts')
REVIEWED_ORIGINAL = REVIEWED_ARTIFACTS/'input/ntdll.so'
REVIEWED_CANDIDATE = REVIEWED_ARTIFACTS/'builds/v2-reproducibility-one/ntdll.so'
PROTECTED_ROOTS = (Path('/Users/david/Library/Application Support/Yaagl OS'), Path('/Users/david/.gimpact'), Path('/Applications/YAAGL.app'))
REQUIRED_STAT = ('mode', 'uid', 'gid', 'flags', 'mtime_ns')

class Stop(RuntimeError): pass

def require(condition, message):
    if not condition: raise Stop(message)

def sha(data): return hashlib.sha256(data).hexdigest()
def canonical_json(obj): return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def stat_record(s):
    return {k: getattr(s, 'st_' + k) for k in ('dev','ino','nlink','mode','uid','gid','flags','size','mtime_ns','ctime_ns','birthtime')}
def _build():
    return subprocess.check_output(['/usr/bin/sw_vers','-buildVersion'], text=True).strip()
def _safe_path(path: Path, must_exist=True):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'Path must be absolute without traversal')
    chain = [path, *path.parents] if must_exist else list(path.parents)
    for item in chain:
        s = item.lstat()
        require(not stat.S_ISLNK(s.st_mode), 'Symlink path component: ' + str(item))
        if item != path: require(stat.S_ISDIR(s.st_mode), 'Non-directory parent: ' + str(item))
    require(path.resolve(strict=must_exist) == path, 'Noncanonical path: ' + str(path))
    return path

def _inside(path, root):
    try: Path(path).relative_to(root); return True
    except ValueError: return False

def directory_identity(path):
    path=_safe_path(Path(path)); fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        before=stat_record(os.fstat(fd))
        require(stat_record(path.stat())==before,'Directory changed before inspection')
        acl=_acl_fd(fd,path)
        require(stat_record(os.fstat(fd))==before==stat_record(path.stat()),'Directory changed during inspection')
        return {'stat':{k:before[k] for k in ('dev','ino','mode','uid','gid','flags')},'acl':acl}
    finally: os.close(fd)

def parent_bindings(paths):
    result={}
    for path in paths:
        for parent in Path(path).parents:
            if str(parent) not in result: result[str(parent)]=directory_identity(parent)
    return result

def _open_parent(path, admitted_parent=None):
    # Resolve and bind once, then perform mutations relative to the pinned inode.
    path=Path(path); _safe_path(path.parent)
    expected=directory_identity(path.parent)
    if admitted_parent is not None: require(expected==admitted_parent,'Mutation parent differs from admitted identity')
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        actual=stat_record(os.fstat(fd))
        require(all(actual[k]==v for k,v in expected['stat'].items()),'Mutation parent changed before binding')
        require(directory_identity(path.parent)==expected,'Mutation parent path redirected')
        return fd
    except BaseException:
        os.close(fd); raise

def _fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)

def _run(args):
    p = subprocess.run([str(a) for a in args], capture_output=True, text=True, timeout=60)
    require(p.returncode == 0, 'Native command failed: ' + repr(args) + '\n' + p.stderr)
    return {'argv': [str(a) for a in args], 'stdout': p.stdout, 'stderr': p.stderr, 'returncode': p.returncode}

libc = ctypes.CDLL(None, use_errno=True)
libc.flistxattr.argtypes=[ctypes.c_int,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int]; libc.flistxattr.restype=ctypes.c_ssize_t
libc.fgetxattr.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_int]; libc.fgetxattr.restype=ctypes.c_ssize_t
libc.fcopyfile.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_void_p,ctypes.c_uint32]; libc.fcopyfile.restype=ctypes.c_int
libc.acl_get_fd_np.argtypes=[ctypes.c_int,ctypes.c_int]; libc.acl_get_fd_np.restype=ctypes.c_void_p
libc.acl_to_text.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ssize_t)]; libc.acl_to_text.restype=ctypes.c_void_p
libc.acl_free.argtypes=[ctypes.c_void_p]; libc.acl_free.restype=ctypes.c_int

def _xattrs_fd(fd):
    n = libc.flistxattr(fd, None, 0, 0); require(n >= 0, 'flistxattr failed')
    buf = ctypes.create_string_buffer(n)
    require(libc.flistxattr(fd, buf, n, 0) == n, 'Xattr list changed')
    names = sorted(x for x in buf.raw[:n].split(b'\0') if x)
    require(len(names) == len(set(names)), 'Duplicate xattr names')
    result = {}
    for name in names:
        length = libc.fgetxattr(fd, name, None, 0, 0, 0); require(length >= 0, 'Cannot size xattr')
        value = ctypes.create_string_buffer(length)
        require(libc.fgetxattr(fd, name, value, length, 0, 0) == length, 'Xattr changed')
        result[os.fsdecode(name)] = value.raw[:length].hex()
    n2 = libc.flistxattr(fd, None, 0, 0); require(n2 == n, 'Xattr names changed during read')
    buf2=ctypes.create_string_buffer(n2)
    require(libc.flistxattr(fd,buf2,n2,0)==n2 and sorted(x for x in buf2.raw[:n2].split(b'\0') if x)==names, 'Xattr set changed')
    return result

def _acl_fd(fd, path):
    acl = text = None
    try:
        ctypes.set_errno(0); acl = libc.acl_get_fd_np(fd, 0x100); error = ctypes.get_errno()
        if not acl:
            # NULL is not an empty ACL. ENOENT plus native listing corroborates absence.
            require(error == errno.ENOENT, 'ACL inspection error: ' + str(error))
            require('\n' not in str(path), 'Unsupported ACL path')
            listing = _run(['/bin/ls','-lde',path])
            require(not listing['stderr'] and len(listing['stdout'].splitlines()) == 1, 'ACL absence not corroborated')
            return {'state':'absent', 'errno':error}
        length = ctypes.c_ssize_t()
        text = libc.acl_to_text(acl,ctypes.byref(length)); require(bool(text), 'ACL serialization failed')
        return {'state':'present', 'serialized_hex':ctypes.string_at(text,length.value).hex()}
    finally:
        if text: libc.acl_free(text)
        if acl: libc.acl_free(acl)

def inspect_file(path: Path, signature=True, hook=None, include_bytes=False):
    """Capture bytes and complete metadata from one stable regular-file descriptor."""
    path=_safe_path(Path(path)); before=stat_record(path.lstat())
    require(stat.S_ISREG(before['mode']), 'Not a regular file: '+str(path))
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        require(stat_record(os.fstat(fd)) == before, 'File changed before inspection')
        access_time_before_read=os.fstat(fd).st_atime_ns
        h=hashlib.sha256(); chunks=[]
        while True:
            data=os.read(fd,1024*1024)
            if not data: break
            h.update(data)
            if include_bytes: chunks.append(data)
        attrs=_xattrs_fd(fd); acl=_acl_fd(fd,path)
        if hook: hook('inspection-before-recheck', path)
        require(stat_record(os.fstat(fd)) == before == stat_record(path.lstat()), 'File changed during inspection')
        result={'path':str(path),'resolved':str(path.resolve()),'sha256':h.hexdigest(),'stat':before,'xattrs':attrs,'acl':acl,
                'access_time_ns_before_read':access_time_before_read}
        if include_bytes: result['content_hex']=b''.join(chunks).hex()
        if signature:
            verify=_run(['/usr/bin/codesign','--verify','--strict','--verbose=2',path])
            desc=_run(['/usr/bin/codesign','-dv','--verbose=4',path]); content=desc['stdout']+desc['stderr']
            require('Identifier='+IDENTIFIER+'\n' in content and 'Signature=adhoc\n' in content, 'Unexpected code signature identity')
            result['signature']={'verified':True,'identifier':IDENTIFIER,'adhoc':True,
                                 'description_lines':[line for line in content.splitlines() if not line.startswith('Executable=')]}
            require(stat_record(os.fstat(fd)) == before == stat_record(path.lstat()), 'File changed during signature check')
        return result
    finally: os.close(fd)

def inspect_document(path):
    record=inspect_file(path,signature=False,include_bytes=True)
    raw=bytes.fromhex(record.pop('content_hex'))
    return record,raw

def check_identity(record, digest):
    require(record['sha256']==digest and record['stat']['size']==SIZE, 'Runtime byte identity mismatch')
    require(record['stat']['nlink']==1, 'File must have one link')
    require(record.get('signature',{}).get('verified'), 'Signature verification missing')

def check_provenance(record, generated=False):
    value=record['xattrs'].get(PROVENANCE)
    require(value in PROVENANCE_VALUES, 'Unsupported provenance state')
    if generated: require(value==GENERATED_PROVENANCE, 'Unexpected newly generated provenance state')

def same_instance(a,b):
    # Verification itself may advance atime. Retain it as evidence, not identity.
    a={k:v for k,v in a.items() if k!='access_time_ns_before_read'}
    b={k:v for k,v in b.items() if k!='access_time_ns_before_read'}
    require(a==b, 'Previously verified file-instance identity or metadata changed')

def same_after_rename(before, after):
    # An owned same-filesystem rename changes path and ctime, not the file payload,
    # ACL, provenance or other xattrs. Any such change stops even if allowlisted.
    a=json.loads(json.dumps(before)); b=json.loads(json.dumps(after))
    for value in (a,b):
        value.pop('path'); value.pop('resolved'); value.pop('access_time_ns_before_read',None); value['stat'].pop('ctime_ns')
    require(a==b, 'Owned rename changed unexpected file-instance metadata')

def required_metadata(original, derived, new_instance=True):
    """Cross-instance invariant; never silently ignore other xattrs or unknown provenance."""
    for key in REQUIRED_STAT:
        require(original['stat'][key]==derived['stat'][key], 'Required metadata mismatch: '+key)
    require(original['acl']==derived['acl'], 'Required ACL mismatch')
    check_provenance(original); check_provenance(derived, generated=new_instance)
    without=lambda attrs:{k:v for k,v in attrs.items() if k!=PROVENANCE}
    require(without(original['xattrs'])==without(derived['xattrs']), 'Required xattr mismatch')
    return {'source':original['xattrs'][PROVENANCE], 'destination':derived['xattrs'][PROVENANCE],
            'different':original['xattrs'][PROVENANCE]!=derived['xattrs'][PROVENANCE],
            'basis':'native fcopyfile/owned rename lineage; exact local reviewed values; no provenance assignment'}

def _copy_exclusive(source,destination,flags,admitted_parent=None):
    """Native fcopyfile; flags ALL=15 or DATA=8 or metadata=7. Never set provenance."""
    source=_safe_path(Path(source)); destination=_safe_path(Path(destination),False)
    before=inspect_file(source); src=os.open(source,os.O_RDONLY|os.O_NOFOLLOW)
    dst=None; parent_fd=None
    try:
        require(stat_record(os.fstat(src))==before['stat'],'Copy source replaced before open')
        parent_fd=_open_parent(destination,admitted_parent)
        dst=os.open(destination.name,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent_fd)
        owned=stat_record(os.fstat(dst))
        source_atime=os.fstat(src).st_atime_ns
        require(libc.fcopyfile(src,dst,None,flags)==0,'fcopyfile failed errno '+str(ctypes.get_errno()))
        destination_atime=os.fstat(dst).st_atime_ns
        if flags & 2: require(source_atime==destination_atime,'fcopyfile did not preserve requested access time')
        require((os.fstat(dst).st_dev,os.fstat(dst).st_ino)==(owned['dev'],owned['ino']), 'Owned copy destination changed')
        os.fsync(dst); os.fsync(parent_fd)
        require(stat_record(os.fstat(src))==before['stat'], 'Copy source descriptor changed')
    finally:
        if dst is not None: os.close(dst)
        if parent_fd is not None: os.close(parent_fd)
        os.close(src)
    same_instance(before,inspect_file(source))
    return {'method':'fcopyfile','flags':flags,'source':before,'destination':str(destination),'owned':owned,
            'source_atime_before_copy':source_atime,'destination_atime_before_verification':destination_atime}

def _copy_metadata(source,destination,expected_destination,admitted_parent=None):
    source_before=inspect_file(source); same_instance(expected_destination,inspect_file(destination))
    src=os.open(source,os.O_RDONLY|os.O_NOFOLLOW); parent_fd=None; dst=None
    try:
        parent_fd=_open_parent(destination,admitted_parent)
        dst=os.open(Path(destination).name,os.O_RDWR|os.O_NOFOLLOW,dir_fd=parent_fd)
        require(stat_record(os.fstat(src))==source_before['stat'],'Metadata source changed')
        require(stat_record(os.fstat(dst))==expected_destination['stat'],'Metadata destination changed')
        source_atime=os.fstat(src).st_atime_ns
        require(libc.fcopyfile(src,dst,None,7)==0,'Metadata fcopyfile failed errno '+str(ctypes.get_errno()))
        destination_atime=os.fstat(dst).st_atime_ns
        require(source_atime==destination_atime,'Metadata copy did not preserve requested access time')
        os.fsync(dst)
    finally:
        if dst is not None: os.close(dst)
        if parent_fd is not None: os.close(parent_fd)
        os.close(src)
    same_instance(source_before,inspect_file(source))
    return {'method':'fcopyfile','flags':7,'source':source_before,'destination':str(destination),
            'source_atime_before_copy':source_atime,'destination_atime_before_verification':destination_atime}

class RuntimeTransaction:
    """Shared implementation: fresh admission, prepare, deploy, restore, recover.

    hook is test-only fault injection. Production admission refuses it. A production
    protected_guard must return the same canonical captured product state throughout;
    it must exclude only the selected slot and its parent replacement timestamps.
    """
    def __init__(self, root, hook=None, protected_guard: Callable | None=None, production=False):
        self.root=_safe_path(Path(root)); self.hook=hook or (lambda event,tx:None)
        self.record_pins={}
        self.production=production; self.guard=protected_guard or (lambda:{})
        self.admission_path=self.root/'admission.json'
        require(self.admission_path.is_file(),'Missing admission record')
        self.admission_snapshot,self.admission_raw=inspect_document(self.admission_path)
        require(self.admission_snapshot['stat']['nlink']==1,'Admission must be independent')
        self.a=json.loads(self.admission_raw)
        require(self.a['root']==str(self.root),'Admission root mismatch')
        require(self.a['root_identity']=={k:stat_record(self.root.stat())[k] for k in ('dev','ino')},'Admission root identity mismatch')
        require(_build()==EXPECTED_BUILD and self.a['macos_build']==EXPECTED_BUILD,'Unreviewed macOS build')
        require(self.a['original_hash']==ORIGINAL and self.a['candidate_hash']==CANDIDATE,'Admission hash mismatch')
        self.slot=Path(self.a['slot']); self.original=Path(self.a['original']); self.candidate=Path(self.a['candidate'])
        self.journal=self.root/'journal'; self.rollback=self.root/'rollback'/'ntdll.so'
        require(len({str(self.slot),str(self.original),str(self.candidate),str(self.rollback)})==4,'Transaction file roles overlap')
        if production:
            require(self.a.get('mode')=='controlled-deployment' and hook is None and protected_guard is not None,'Production admission requirements missing')
            require(self.slot==INSTALLED,'Unsupported production destination')
            require(self.original==REVIEWED_ORIGINAL and self.candidate==REVIEWED_CANDIDATE,'Unreviewed production source paths')
            require(not any(_inside(self.root,r) for r in PROTECTED_ROOTS),'Production journal/rollback must be outside protected trees')
            require(self.root.stat().st_dev==self.slot.stat().st_dev,'Production rollback/journal must use the reviewed runtime filesystem')
            require(bool(self.a.get('authorization_reference')) and self.a.get('managed_provenance_transition_authorized') is True,'Fresh provenance-aware authorization missing')
            require(self.a.get('transaction_id')==self.root.name,'Production transaction identity mismatch')
            require(sha(Path(__file__).read_bytes())==self.a['reviewed_core_sha256'],'Production core identity mismatch')
            require(sha(Path(self.a['procedure_path']).read_bytes())==self.a['reviewed_procedure_sha256'],'Production procedure identity mismatch')
        else:
            require(self.a.get('mode')=='replica','Replica admission required')
            for p in [self.root,self.slot,self.original,self.candidate]:
                require(not any(_inside(p,r) for r in PROTECTED_ROOTS),'Replica cannot mutate protected product paths')
                require(_inside(p,self.root),'Replica path escapes root')
        for p in [self.slot,self.original,self.candidate,self.journal,self.rollback.parent]: _safe_path(p)
        self.bound_paths=[self.slot,self.original,self.candidate,self.journal/'entry',self.rollback]
        require(parent_bindings(self.bound_paths)==self.a['parent_bindings'],'Admission parent identity or metadata mismatch')
        require(self.slot.parent.stat().st_dev==self.slot.stat().st_dev,'Slot filesystem mismatch')
        self.baseline=self._load('00-baseline.json') if (self.journal/'00-baseline.json').exists() else None
    def _load(self,name):
        path=self.journal/name; snapshot,raw=inspect_document(path)
        if name in self.record_pins: same_instance(self.record_pins[name],snapshot)
        else: self.record_pins[name]=snapshot
        value=json.loads(raw); seal=value.pop('_record_seal',None)
        require(seal=={'sha256':sha(canonical_json(value)),'admission_sha256':sha(self.admission_raw)},'Journal record seal mismatch')
        return value
    def _save(self,name,obj):
        self._admit(); path=self.journal/name
        obj=dict(obj,_record_seal={'sha256':sha(canonical_json(obj)),'admission_sha256':sha(self.admission_raw)})
        parent_fd=_open_parent(path,self.a['parent_bindings'][str(path.parent)]); fd=None
        try:
            fd=os.open(path.name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent_fd)
            with os.fdopen(fd,'wb',closefd=False) as f: f.write(canonical_json(obj)+b'\n'); f.flush(); os.fsync(fd)
            os.fsync(parent_fd)
        finally:
            if fd is not None: os.close(fd)
            os.close(parent_fd)
        self.record_pins[name]=inspect_file(path,signature=False)
    def _admit(self):
        _safe_path(self.root); admission,raw=inspect_document(self.admission_path)
        same_instance(self.admission_snapshot,admission)
        require(raw==self.admission_raw,'Admission changed')
        require(parent_bindings(self.bound_paths)==self.a['parent_bindings'],'Parent identity or metadata changed')
        require(self.a['root_identity']=={k:stat_record(self.root.stat())[k] for k in ('dev','ino')},'Root replaced')
        for p in [self.slot.parent,self.journal,self.rollback.parent]: _safe_path(p)
        for name,want in self.record_pins.items(): same_instance(want,inspect_file(self.journal/name,signature=False))
    def _event(self,name): self.hook(name,self); self._admit()
    def _guard(self):
        current=self.guard()
        if self.baseline is not None:
            require(current==self.baseline['protected_guard'],'Protected product drift')
            same_instance(self.baseline['source'],inspect_file(self.original))
            same_instance(self.baseline['candidate'],inspect_file(self.candidate))
        return current
    def _no_owned_temps(self):
        for phase in ('deploy','restore'):
            require(not os.path.lexists(self.slot.parent/('.ntdll-'+self.root.name+'-'+phase+'.tmp')),'Unconsumed owned temporary requires analysis')
    def prepare(self):
        self._admit(); self._no_owned_temps(); require(self.baseline is None,'Transaction already prepared')
        require(not list(self.journal.iterdir()) and not list(self.rollback.parent.iterdir()),'Transaction destination collision')
        old=inspect_file(self.slot); source=inspect_file(self.original); candidate=inspect_file(self.candidate)
        check_identity(old,ORIGINAL); check_identity(source,ORIGINAL); check_identity(candidate,CANDIDATE)
        check_provenance(old); check_provenance(source); check_provenance(candidate,generated=True)
        require(old['stat']['uid']==os.getuid(),'Unexpected installed-slot owner')
        # Production admission includes the exact read-only baseline captured before authorization.
        if self.production:
            require(old['xattrs'].get(PROVENANCE)=='010000dcd5bccdc7edc92e','Production baseline provenance differs from protected original')
            same_instance(self.a['expected_slot'],old); same_instance(self.a['expected_candidate'],candidate)
        self.baseline={'slot':old,'source':source,'candidate':candidate,'protected_guard':self._guard(),'at':now()}
        self._save('00-baseline.json',self.baseline)
        self._event('before-rollback-copy')
        lineage=_copy_exclusive(self.slot,self.rollback,15,self.a['parent_bindings'][str(self.rollback.parent)]); backup=inspect_file(self.rollback)
        check_identity(backup,ORIGINAL)
        require((backup['stat']['dev'],backup['stat']['ino'])!=(old['stat']['dev'],old['stat']['ino']),'Rollback is not independent')
        transition=required_metadata(old,backup); same_instance(old,inspect_file(self.slot))
        self._guard()
        self._save('01-rollback.json',{'backup':backup,'lineage':lineage,'provenance':transition})
        self._event('rollback-verified')
        return backup
    def _checked_rollback(self):
        require((self.journal/'01-rollback.json').exists(),'Verified rollback missing')
        want=self._load('01-rollback.json')['backup']; actual=inspect_file(self.rollback)
        same_instance(want,actual); check_identity(actual,ORIGINAL); required_metadata(self.baseline['slot'],actual)
        return actual
    def _replace(self,source,expected_current,digest,phase):
        self._admit(); self._guard(); rollback=self._checked_rollback()
        same_instance(expected_current,inspect_file(self.slot))
        temp=self.slot.parent/('.ntdll-'+self.root.name+'-'+phase+'.tmp')
        require(not os.path.lexists(temp),'Owned temporary destination collision')
        self._save(phase+'-stage-plan.json',{'at':now(),'source':str(source),'destination':str(temp),'expected_hash':digest,'installed_replaced':False})
        self._event('before-'+phase+'-copy')
        lineage=_copy_exclusive(source,temp,8,self.a['parent_bindings'][str(temp.parent)]); copied=inspect_file(temp)
        metadata=_copy_metadata(self.rollback,temp,copied,self.a['parent_bindings'][str(temp.parent)])
        staged=inspect_file(temp); check_identity(staged,digest); transition=required_metadata(self.baseline['slot'],staged)
        require(staged['stat']['dev']==expected_current['stat']['dev'],'Atomic replacement requires same filesystem')
        require((staged['stat']['dev'],staged['stat']['ino'])!=(expected_current['stat']['dev'],expected_current['stat']['ino']),'Temporary is not independent')
        self._event('before-'+phase+'-intent')
        same_instance(expected_current,inspect_file(self.slot)); same_instance(staged,inspect_file(temp)); self._checked_rollback(); self._guard()
        intent={'phase':phase,'at':now(),'prior':expected_current,'temporary':staged,'rollback':rollback,'lineage':lineage,'metadata':metadata,'provenance':transition}
        self._save(phase+'-intent.json',intent)
        self._event('before-'+phase+'-replace')
        # Directory descriptor binds both entries to one verified directory and filesystem.
        dfd=_open_parent(self.slot,self.a['parent_bindings'][str(self.slot.parent)])
        try:
            same_instance(expected_current,inspect_file(self.slot)); same_instance(staged,inspect_file(temp))
            os.replace(temp.name,self.slot.name,src_dir_fd=dfd,dst_dir_fd=dfd)
            os.fsync(dfd)
        finally: os.close(dfd)
        self._event('after-'+phase+'-replace')
        installed=inspect_file(self.slot); check_identity(installed,digest)
        require((installed['stat']['dev'],installed['stat']['ino'])==(staged['stat']['dev'],staged['stat']['ino']),'Replacement inode mismatch')
        post_transition=required_metadata(self.baseline['slot'],installed)
        same_after_rename(staged,installed)
        self._guard(); self._checked_rollback()
        self._event('before-'+phase+'-seal')
        same_instance(installed,inspect_file(self.slot)); self._checked_rollback(); self._guard()
        self._save(phase+'-complete.json',{'phase':phase,'at':now(),'installed':installed,'provenance':post_transition})
        return installed
    def _failure(self,phase,error):
        # A durable intent remains the recovery authority even when this record
        # cannot be written (for example admission/path integrity has failed).
        try:
            self._save(phase+'-stop-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json',
                       {'phase':phase,'error':str(error),'type':type(error).__name__,'at':now(),
                        'replacement_intent_exists':(self.journal/(phase+'-intent.json')).exists(),
                        'action':'Stopped; no automatic overwrite or cleanup of mismatched objects'})
        except BaseException: pass
    def deploy(self):
        try: return self._deploy()
        except BaseException as error:
            self._failure('deploy',error); raise
    def _deploy(self):
        require(self.baseline is not None,'Prepare required')
        require(not any(p.name.startswith(('deploy-','restore-','restored-')) for p in self.journal.iterdir()),'Deployment already attempted or transaction restored; new transaction required')
        same_instance(self.baseline['candidate'],inspect_file(self.candidate))
        return self._replace(self.candidate,self.baseline['slot'],CANDIDATE,'deploy')
    def restore(self):
        try: return self._restore()
        except BaseException as error:
            self._failure('restore',error); raise
    def _restore(self):
        require(self.baseline is not None,'Baseline required')
        self._checked_rollback(); self._guard(); actual=inspect_file(self.slot)
        require(actual['sha256'] in (ORIGINAL,CANDIDATE),'Unknown third installed identity; restoration forbidden')
        check_identity(actual,actual['sha256']); required_metadata(self.baseline['slot'],actual,new_instance=actual['sha256']==CANDIDATE)
        if actual['sha256']==ORIGINAL:
            self._no_owned_temps()
            if (self.journal/'restored-idempotent.json').exists():
                same_instance(self._load('restored-idempotent.json')['installed'],actual); return actual
            elif (self.journal/'restore-complete.json').exists():
                same_instance(self._load('restore-complete.json')['installed'],actual)
            elif (self.journal/'restore-intent.json').exists():
                same_after_rename(self._load('restore-intent.json')['temporary'],actual)
            else:
                same_instance(self.baseline['slot'],actual)
            self._save('restored-idempotent.json',{'installed':actual,'at':now()}); return actual
        # Only the inode committed by this transaction's durable replacement intent may be restored.
        intent=self._load('deploy-intent.json')
        if (self.journal/'deploy-complete.json').exists():
            same_instance(self._load('deploy-complete.json')['installed'],actual)
        else:
            same_after_rename(intent['temporary'],actual)
        require((actual['stat']['dev'],actual['stat']['ino'])==(intent['temporary']['stat']['dev'],intent['temporary']['stat']['ino']),'Candidate is not this transaction replacement')
        return self._replace(self.rollback,actual,ORIGINAL,'restore')
    def status(self):
        self._admit(); actual=inspect_file(self.slot)
        result={'slot':actual,'journal':sorted(p.name for p in self.journal.iterdir())}
        if actual['sha256'] not in (ORIGINAL,CANDIDATE): result['state']='UNKNOWN_IDENTITY_STOP'
        elif actual['sha256']==ORIGINAL and (self.journal/'restored-idempotent.json').exists():
            same_instance(self._load('restored-idempotent.json')['installed'],actual); result['state']='RESTORED'
        elif actual['sha256']==ORIGINAL and (self.journal/'restore-complete.json').exists():
            same_instance(self._load('restore-complete.json')['installed'],actual); result['state']='RESTORED'
        elif actual['sha256']==CANDIDATE and (self.journal/'deploy-complete.json').exists():
            same_instance(self._load('deploy-complete.json')['installed'],actual); result['state']='DEPLOYED'
        elif (self.journal/'deploy-intent.json').exists(): result['state']='INTERRUPTED_REQUIRES_EXPLICIT_RECOVERY'
        else: result['state']='PRE_INSTALL'
        return result

def create_replica(root,original,candidate):
    """Fresh disposable admission only. Does not accept a live-product destination."""
    root=Path(root); require(root.is_absolute(),'Replica root must be absolute')
    require(not any(_inside(root,r) for r in PROTECTED_ROOTS),'Protected replica root forbidden')
    _safe_path(root,False); root.mkdir(mode=0o700)
    for name in ('input','runtime','rollback','journal'): (root/name).mkdir(mode=0o700)
    for source,destination in ((original,root/'input'/'original.so'),(candidate,root/'input'/'candidate.so'),(original,root/'runtime'/'ntdll.so')):
        _copy_exclusive(Path(source),destination,15)
    admission={'mode':'replica','transaction_id':root.name,'root':str(root),'root_identity':{k:stat_record(root.stat())[k] for k in ('dev','ino')},
               'slot':str(root/'runtime'/'ntdll.so'),'original':str(root/'input'/'original.so'),'candidate':str(root/'input'/'candidate.so'),
               'macos_build':_build(),'original_hash':ORIGINAL,'candidate_hash':CANDIDATE,
               'parent_bindings':parent_bindings([root/'runtime'/'ntdll.so',root/'input'/'original.so',root/'input'/'candidate.so',root/'journal'/'entry',root/'rollback'/'ntdll.so'])}
    with (root/'admission.json').open('x') as f: json.dump(admission,f,indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
    _fsync_dir(root)
    return RuntimeTransaction(root)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('create-replica'); p.add_argument('root',type=Path);p.add_argument('original',type=Path);p.add_argument('candidate',type=Path)
    for command in ('prepare','deploy','restore','status'):
        p=sub.add_parser(command);p.add_argument('root',type=Path)
    args=parser.parse_args()
    if args.command=='create-replica': tx=create_replica(args.root,args.original,args.candidate); result=tx.status()
    else:
        tx=RuntimeTransaction(args.root)
        result=getattr(tx,args.command)()
    print(json.dumps(result,indent=2))
if __name__=='__main__': main()
