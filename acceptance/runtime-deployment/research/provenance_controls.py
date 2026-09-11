#!/usr/bin/env python3
"""Additional disposable xattr controls and copyfile status callbacks; no runtime loading."""
from pathlib import Path
import argparse,ctypes,json,os,sys
import copy_matrix as M
C=M.C
C.copyfile_state_alloc.argtypes=[];C.copyfile_state_alloc.restype=ctypes.c_void_p
C.copyfile_state_free.argtypes=[ctypes.c_void_p];C.copyfile_state_free.restype=ctypes.c_int
C.copyfile_state_set.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p];C.copyfile_state_set.restype=ctypes.c_int
C.copyfile_state_get.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p];C.copyfile_state_get.restype=ctypes.c_int
CALLBACK=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_void_p,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_void_p)
def main():
 p=argparse.ArgumentParser();p.add_argument('--matrix-root',type=Path,required=True);a=p.parse_args();base=a.matrix_root.resolve(strict=True)
 declaration=json.loads((base/'.disposable-metadata-matrix.json').read_text());M.need(declaration['root']==str(base),'matrix declaration mismatch')
 root=base/'additional-controls';root.mkdir(mode=0o700);filesystem=json.loads((base/'PLATFORM.json').read_text())['filesystem'];source=Path(declaration['source'])
 data=source.read_bytes();M.need(M.digest(data)==M.ORIGINAL,'source hash mismatch');probe=root/'controlled-source.so';probe.write_bytes(data)
 control_name='org.yaagl.disposable-metadata-control';control_value=b'copyfile-control\x00\xff\x01'
 before=M.capture(probe,filesystem);set_result=M.set_attr(probe,control_name,control_value);after=M.capture(probe,filesystem)
 M.need(after['xattrs'][control_name]['hex']==control_value.hex(),'ordinary xattr did not persist')
 callbacks=[]
 for index in range(3):
  dest=root/('callback-'+str(index+1)+'.so');events=[];state=C.copyfile_state_alloc();M.need(bool(state),'state allocation failed')
  @CALLBACK
  def callback(what,stage,st,src,dst,ctx):
   name=ctypes.c_char_p();result=C.copyfile_state_get(st,9,ctypes.byref(name)) if what==5 else None
   events.append({'what':what,'stage':stage,'xattr_name_rc':result,'xattr_name':os.fsdecode(name.value) if name.value else None})
   return 0
  M.need(C.copyfile_state_set(state,6,ctypes.cast(callback,ctypes.c_void_p))==0,'callback registration failed')
  try:operation=M.native_call('copyfile',os.fsencode(probe),os.fsencode(dest),state,15|(1<<17)|(1<<18)|(1<<19))
  finally:C.copyfile_state_free(state)
  result=M.capture(dest,filesystem);M.need(result['xattrs'][control_name]['hex']==control_value.hex(),'ordinary xattr copy mismatch')
  M.need(any(e['what']==5 and e['stage']==1 and e['xattr_name']==M.PROV for e in events),'missing provenance START callback')
  M.need(any(e['what']==5 and e['stage']==2 and e['xattr_name']==M.PROV for e in events),'missing provenance FINISH callback')
  callbacks.append({'index':index+1,'operation':operation,'events':events,'destination':result})
 delete=M.native_call('removexattr',os.fsencode(probe),control_name.encode(),1);after_delete=M.capture(probe,filesystem);M.need(control_name not in after_delete['xattrs'],'ordinary xattr removal did not persist')
 cli_probe=root/'cli-probe.so';cli_probe.write_bytes(data);cli_before=M.capture(cli_probe,filesystem)
 cli=M.command(['/usr/bin/xattr','-wx',M.PROV,'010000dcd5bccdc7edc92e',cli_probe]);cli_after=M.capture(cli_probe,filesystem)
 result={'ordinary_xattr_control':{'set':set_result,'before':before,'after':after,'remove':delete,'after_remove':after_delete},'copyfile_callbacks':callbacks,'cli_original_provenance_attempt':{'operation':cli,'before':cli_before,'after':cli_after},'source_bytes_unchanged':source.read_bytes()==data,'no_installed_or_prefix_mutation':True,'no_runtime_executed':True}
 M.save(root/'RESULTS.json',result)
 print(json.dumps({'ordinary_xattr_persisted_and_removed':True,'provenance_start_finish_callbacks':len(callbacks),'native_cli_set_rc':cli['rc'],'requested_original_provenance': '010000dcd5bccdc7edc92e','readback':cli_after['xattrs'][M.PROV]['hex']},indent=2))
if __name__=='__main__':main()
