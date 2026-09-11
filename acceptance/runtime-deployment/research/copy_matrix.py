#!/usr/bin/env python3
"""Native filesystem-only matrix. All mutation is inside a fresh declared disposable root."""
from pathlib import Path
import argparse,ctypes,errno,hashlib,json,os,plistlib,stat,subprocess,sys,time
C=ctypes.CDLL(None,use_errno=True)
for name,args,restype in [('listxattr',[ctypes.c_char_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int],ctypes.c_ssize_t),('getxattr',[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_int],ctypes.c_ssize_t),('setxattr',[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_int],ctypes.c_int),('removexattr',[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int],ctypes.c_int),('fcopyfile',[ctypes.c_int,ctypes.c_int,ctypes.c_void_p,ctypes.c_uint32],ctypes.c_int),('copyfile',[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_uint32],ctypes.c_int),('clonefile',[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_uint32],ctypes.c_int)]:
 f=getattr(C,name);f.argtypes=args;f.restype=restype
ORIGINAL='f26ade35f5b49e33b3780b6adc71f9eb9c831ea40222c1bae667ac14135d984b'
PROV='com.apple.provenance'
def need(ok,msg):
 if not ok:raise RuntimeError(msg)
def digest(b):return hashlib.sha256(b).hexdigest()
def command(args):
 r=subprocess.run([str(x) for x in args],capture_output=True,text=True,timeout=60)
 return {'argv':[str(x) for x in args],'rc':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
def attrs(path):
 p=os.fsencode(path);n=C.listxattr(p,None,0,1);need(n>=0,'listxattr failed')
 if not n:return {}
 b=ctypes.create_string_buffer(n);need(C.listxattr(p,b,n,1)==n,'xattr list changed');out={}
 for name in sorted(x for x in b.raw[:n].split(b'\0') if x):
  n=C.getxattr(p,name,None,0,0,1);need(n>=0,'getxattr size failed');b=ctypes.create_string_buffer(n);need(C.getxattr(p,name,b,n,0,1)==n,'getxattr changed')
  out[os.fsdecode(name)]={'hex':b.raw[:n].hex(),'bytes':n,'sha256':digest(b.raw[:n])}
 return out
def capture(path,filesystem,signature=True):
 s=path.lstat();need(stat.S_ISREG(s.st_mode) and not path.is_symlink(),'capture expects regular file')
 result={'path':str(path),'resolved':str(path.resolve()),'filesystem':filesystem,'stat':{k:getattr(s,'st_'+k) for k in ('dev','ino','uid','gid','mode','nlink','size','flags','atime_ns','mtime_ns','ctime_ns','birthtime')},'sha256':digest(path.read_bytes()),'xattrs':attrs(path),'acl':command(['/bin/ls','-lde',path])}
 if signature:result['signature']=command(['/usr/bin/codesign','--verify','--strict','--verbose=2',path]);result['signature_description']=command(['/usr/bin/codesign','-dv','--verbose=4',path])
 need(result['stat']['ino']==path.lstat().st_ino,'capture path replaced')
 return result
def stable(r):return {k:v for k,v in r.items() if k not in ('stat','acl','signature','signature_description')}|{'stat':{k:v for k,v in r['stat'].items() if k!='atime_ns'}}
def native_call(name,*args):
 ctypes.set_errno(0);rc=getattr(C,name)(*args);err=ctypes.get_errno()
 return {'api':name,'rc':rc,'errno':err if rc else 0,'error':os.strerror(err) if rc else ''}
def set_attr(path,name,value):
 b=ctypes.create_string_buffer(value);return native_call('setxattr',os.fsencode(path),name.encode(),b,len(value),0,1)
def run_method(name,source,dest):
 need(not os.path.lexists(dest),'destination exists')
 if name=='fcopyfile_all':
  src=os.open(source,os.O_RDONLY|os.O_NOFOLLOW);dst=os.open(dest,os.O_CREAT|os.O_EXCL|os.O_RDWR|os.O_NOFOLLOW,0o600)
  try:return native_call('fcopyfile',src,dst,None,15)
  finally:os.close(src);os.close(dst)
 if name=='copyfile_all':return native_call('copyfile',os.fsencode(source),os.fsencode(dest),None,15|(1<<17)|(1<<18)|(1<<19))
 if name=='clonefile':return native_call('clonefile',os.fsencode(source),os.fsencode(dest),0)
 if name=='cp_p':return command(['/bin/cp','-p',source,dest])
 if name=='cp_a':return command(['/bin/cp','-a',source,dest])
 if name=='ditto':return command(['/usr/bin/ditto','--rsrc','--extattr','--acl',source,dest])
 if name=='fresh_explicit_xattrs':
  with dest.open('xb') as f:f.write(source.read_bytes());f.flush();os.fsync(f.fileno())
  calls={k:set_attr(dest,k,bytes.fromhex(v['hex'])) for k,v in attrs(source).items()}
  s=source.stat();os.chmod(dest,stat.S_IMODE(s.st_mode));os.utime(dest,ns=(s.st_atime_ns,s.st_mtime_ns))
  return {'method':name,'rc':0 if all(v['rc']==0 for v in calls.values()) else 1,'xattr_attempts':calls}
 raise RuntimeError(name)
def save(path,value):
 with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--root',type=Path,required=True);a=p.parse_args()
 source=a.source.resolve(strict=True);root=a.root
 need(root.is_absolute() and root.parent.resolve()==root.parent and not root.exists(),'fresh canonical root required')
 need(not any(part.lower() in ('hoyoplay-wines','wineprefix','drive_c') or part.lower().endswith('.app') for part in root.parts),'forbidden disposable path')
 need(not any(part.lower() in ('hoyoplay-wines','wineprefix','drive_c') for part in source.parts),'use reviewed copied input only')
 need(digest(source.read_bytes())==ORIGINAL,'wrong source')
 root.mkdir(mode=0o700);save(root/'.disposable-metadata-matrix.json',{'purpose':'disposable copies only','root':str(root),'source':str(source)})
 info=subprocess.run(['/usr/sbin/diskutil','info','-plist','/System/Volumes/Data'],capture_output=True,check=True);disk=plistlib.loads(info.stdout)
 filesystem={k:disk.get(k) for k in ('FilesystemType','FileSystemPersonality','DeviceIdentifier','DeviceNode','MountPoint','VolumeUUID')}
 save(root/'PLATFORM.json',{'sw_vers':command(['/usr/bin/sw_vers']),'uname':command(['/usr/bin/uname','-a']),'filesystem':filesystem,'df':command(['/bin/df','-P',root]),'pid':os.getpid(),'ppid':os.getppid()})
 initial=capture(source,filesystem);save(root/'SOURCE-BEFORE.json',initial)
 results=[]
 for method in ('fcopyfile_all','copyfile_all','cp_p','cp_a','ditto','clonefile','fresh_explicit_xattrs'):
  for index in range(3):
   folder=root/(method+'-'+str(index+1));folder.mkdir(mode=0o700);dest=folder/'ntdll.so'
   operation=run_method(method,source,dest);after=capture(dest,filesystem) if dest.exists() else None
   entry={'method':method,'index':index+1,'source':initial,'operation':operation,'destination':after};save(folder/'RESULT.json',entry);results.append(entry)
 # No production provenance assignment. These explicit set/remove attempts are
 # solely disposable experiments testing support and observed effects.
 probes=[]
 for name,value in [('copy_original_raw',bytes.fromhex('010000dcd5bccdc7edc92e')),('set_zero_11',bytes(11)),('set_wrong_length',b'bad'),('set_observed_creator',bytes.fromhex(initial['xattrs'][PROV]['hex']))]:
  path=root/(name+'.so');path.write_bytes(source.read_bytes());os.chmod(path,0o600)
  before=capture(path,filesystem);op=set_attr(path,PROV,value);after=capture(path,filesystem)
  probes.append({'probe':name,'requested_hex':value.hex(),'before':before,'operation':op,'after':after})
 path=root/'remove-provenance.so';path.write_bytes(source.read_bytes());os.chmod(path,0o600);before=capture(path,filesystem);op=native_call('removexattr',os.fsencode(path),PROV.encode(),1);probes.append({'probe':'remove_provenance','before':before,'operation':op,'after':capture(path,filesystem)})
 # Creation, ordinary data writes and atomic rename are observed separately.
 transitions=[]
 for index in range(3):
  folder=root/('transitions-'+str(index+1));folder.mkdir(mode=0o700);path=folder/'new.so';path.touch(mode=0o600)
  empty=capture(path,filesystem,False);path.write_bytes(source.read_bytes());written=capture(path,filesystem)
  renamed=folder/'renamed.so';os.rename(path,renamed);renamed_record=capture(renamed,filesystem)
  slot=folder/'slot.so';slot.write_bytes(b'old disposable slot');replaced_before=capture(slot,filesystem,False);os.replace(renamed,slot);replaced=capture(slot,filesystem)
  transitions.append({'index':index+1,'empty':empty,'written':written,'renamed':renamed_record,'slot_before':replaced_before,'after_replace':replaced})
 final=capture(source,filesystem);need(stable(initial)==stable(final),'source changed')
 summary={'source_unchanged':True,'source_before':initial,'source_after':final,'copies':results,'provenance_probes':probes,'creation_rename_replace':transitions,'real_installation_mutated':False,'runtime_executed':False,'limits':['This matrix does not load Wine or assess Gatekeeper execution decisions.','All observed paths use the same local APFS device; cross-filesystem mutation is not attempted.','Native commands inherit this session process ancestry; identical values do not establish a universal per-process or per-directory rule.']}
 save(root/'RESULTS.json',summary)
 print(json.dumps({'copy_cases':len(results),'methods':{m:[{'rc':r['operation']['rc'],'provenance':r['destination']['xattrs'].get(PROV,{}).get('hex') if r['destination'] else None,'signature_rc':r['destination']['signature']['rc'] if r['destination'] else None} for r in results if r['method']==m] for m in sorted({r['method'] for r in results})},'probes':[{'probe':x['probe'],'operation':x['operation'],'after':x['after']['xattrs'].get(PROV)} for x in probes],'source_unchanged':True},indent=2))
if __name__=='__main__':main()
