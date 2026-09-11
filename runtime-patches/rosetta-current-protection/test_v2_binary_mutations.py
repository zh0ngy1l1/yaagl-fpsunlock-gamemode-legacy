#!/usr/bin/env python3
"""Exercise V2 byte admission using declared offline input; no copy/sign/load/install."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
INPUT='f26ade35f5b49e33b3780b6adc71f9eb9c831ea40222c1bae667ac14135d984b'
UNSIGNED='9cc5ac83007e7942fe422793875c90f81fd6d647e5694ac96478c3e6326bc53d'
def sha(data):return hashlib.sha256(data).hexdigest()
def need(ok,message):
    if not ok:raise ValueError(message)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--builder',type=Path,required=True)
    p.add_argument('--staging-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    need(not a.output.exists() and not a.output.is_symlink(),'Output must be new')
    builder_data=a.builder.read_bytes()
    spec=importlib.util.spec_from_file_location('v2_mutation_builder',a.builder);b=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=b;spec.loader.exec_module(b)
    # Reuse the production builder's copied-input admission. This call creates
    # nothing; the unused destination must be fresh just as for a real build.
    input_path,unused_output,staging=b.destination(a.staging_root,'mutation-admission-only')
    original,input_stat=b.read_stable_input(input_path);need(sha(original)==INPUT,'Wrong input runtime')
    unsigned,image,metadata=b.prepare_bytes(original)
    need(sha(unsigned)==UNSIGNED,'V2 baseline unsigned hash')
    cases=[('wrong_load_offset','INSTRUCTION_ADDRESS',b.INSTRUCTION_ADDRESS+1),
           ('wrong_calculation_offset','CALCULATION_ADDRESS',b.CALCULATION_ADDRESS+1),
           ('wrong_current_field_displacement','NEW_INSTRUCTION',bytes.fromhex('8b8d30ffffff')),
           ('wrong_shift_count','NEW_CALCULATION',bytes.fromhex('c0e905')+bytes([0x90])*9),
           ('wrong_shift_register','NEW_CALCULATION',bytes.fromhex('c0e804')+bytes([0x90])*9)]
    outcomes=[]
    for name,attribute,changed in cases:
        before=getattr(b,attribute);setattr(b,attribute,changed)
        try:b.prepare_bytes(original)
        except b.BuildError as error:outcomes.append({'mutation':name,'detected':True,'reason':str(error)})
        else:raise ValueError('Invalid binary mutation admitted: '+name)
        finally:setattr(b,attribute,before)
    final_input,final_stat=b.read_stable_input(input_path)
    need(final_input==original and final_stat==input_stat and a.builder.read_bytes()==builder_data,'Input changed')
    need(not unused_output.exists(),'Mutation check unexpectedly created runtime output')
    result={'builder':str(a.builder.resolve()),'builder_sha256':sha(builder_data),'input_sha256':INPUT,
            'copied_input_path':str(input_path),'staging':staging,
            'baseline_unsigned_sha256':UNSIGNED,'baseline_changed_ranges':metadata['unsigned_changed_ranges'],
            'mutations':outcomes,'input_bytes_unchanged':True,'runtime_output_created':False,
            'codesign_invoked':False,'runtime_loaded':False,'wine_executed':False}
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
