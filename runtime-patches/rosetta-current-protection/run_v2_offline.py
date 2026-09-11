#!/usr/bin/env python3
"""V2 source-extracted native helper and API-validity regressions; host mocks only.

Unchanged managed-release test results are explicitly reused. Historical writes
are read-only inputs. No Wine/game or native process-memory operation runs.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
WINE_SHA='cc09fcaf2f5234eedf68ba068ffa6f7b586bca2753ce98bc0887d11002913419'
V1_PATCH_SHA='f901749a1fc93bbe9d44f4cafc8178f5e8e1f84ab67366a015fa71f19d7819bb'
V2_PATCH_SHA='88dd45f99c6438db828688239286192b1405c90f22d03ef5c54b62bb22c52458'
V2_HELPER_SHA='dbbf5388d1ec2f918055119a79e56e72e5c0da2d7b798e79d98a8cfe3e161926'

def need(ok,message):
    if not ok: raise ValueError(message)

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def text_digest(value):return hashlib.sha256(value.encode()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path); result=importlib.util.module_from_spec(spec)
    sys.modules[name]=result;spec.loader.exec_module(result);return result

def extract(source,signature):
    start=source.index(signature); begin=source.index('{',start); depth=1;end=begin+1
    while depth: depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]

def apply_exact(helper,patch):
    old,new,hunks=[],[],[];active=False
    for line in patch.read_text().splitlines(keepends=True):
        if line.startswith('@@'):
            if active:hunks.append((''.join(old),''.join(new)))
            old,new,active=[],[],True
        elif active:
            if line.startswith(' '):old.append(line[1:]);new.append(line[1:])
            elif line.startswith('-'):old.append(line[1:])
            elif line.startswith('+'):new.append(line[1:])
            elif line.startswith('\\ No newline'):pass
            else:raise ValueError('Unexpected correction patch content')
    if active:hunks.append((''.join(old),''.join(new)))
    need(hunks,'No correction hunks')
    result=helper
    for old,new in hunks:
        need(result.count(old)==1,'Correction context must match exactly once')
        result=result.replace(old,new,1)
    return result

def run(args,directory,label,success=True):
    command=[str(x) for x in args]
    result=subprocess.run(command,text=True,capture_output=True,timeout=60,cwd=directory)
    (directory/(label+'.stdout')).write_text(result.stdout);(directory/(label+'.stderr')).write_text(result.stderr)
    need((result.returncode==0)==success,label+': unexpected exit '+str(result.returncode)+': '+result.stderr)
    return result

def native(source,directory,cc,old,new,validator):
    directory.mkdir()
    (directory/'helper-legacy.inc').write_text(old);(directory/'helper-corrected.inc').write_text(new)
    (directory/'wine-protection.inc').write_text(validator+'\n')
    binary=directory/'native_fixture'
    run([cc,'-std=c11','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
         '-fno-omit-frame-pointer','-I',directory,source,'-o',binary],directory,'build')
    return binary

def static_failure(new,directory,cc):
    directory.mkdir()
    # This exact API failure branch leaves old untouched, as does the pinned
    # Wine remote queue-error return. The helper is analyzed, never executed.
    preamble='''#include <stdint.h>\n#include <stddef.h>
typedef void *HANDLE;typedef uint32_t DWORD;typedef uint32_t NTSTATUS;typedef size_t SIZE_T;
typedef struct{void *BaseAddress,*AllocationBase;DWORD AllocationProtect;uint16_t PartitionId;SIZE_T RegionSize;DWORD State,Protect,Type;}MEMORY_BASIC_INFORMATION;
enum{MemoryBasicInformation=0,PAGE_NOACCESS=1};
static int is_apple_silicon(void){return 1;}
static NTSTATUS NtQueryVirtualMemory(HANDLE p,const void*a,int k,MEMORY_BASIC_INFORMATION*i,SIZE_T l,SIZE_T*r){*i=(MEMORY_BASIC_INFORMATION){.AllocationProtect=0x80,.Protect=0x20};*r=sizeof(*i);return 0;}
static int calls;
static NTSTATUS NtProtectVirtualMemory(HANDLE p,void**a,SIZE_T*s,DWORD requested,DWORD*old){if(calls++==0)return 0xc0000022;*old=0x20;return 0;}
'''
    source=directory/'first_failure_static.c'
    source.write_text(preamble+new+'\nint main(void){toggle_executable_pages_for_rosetta((HANDLE)0x99,(void*)0x1452b4244,4);return 0;}\n')
    result=run([cc,'--analyze','-std=c11','-Xanalyzer','-analyzer-output=text',source],directory,'analyze')
    need('uninitialized' in result.stderr.lower() and 'origprot' in result.stderr,'Uninitialized origprot diagnosis expected')
    return {'exact_v2_helper_analyzed':True,'uninitialized_origprot_negative_reproduced':True,'undefined_behavior_executed':False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate',type=Path,default=ROOT)
    p.add_argument('--correction',type=Path,default=ROOT/'0001-ntdll-use-current-protection-for-rosetta-toggle.patch')
    p.add_argument('--v1-correction',type=Path,default=ROOT/'vendor/0001-ntdll-current-protection-v1-excluded.patch')
    p.add_argument('--wine-source',type=Path,required=True)
    p.add_argument('--comparison',type=Path,required=True)
    p.add_argument('--managed-results',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--cc',default='/usr/bin/clang')
    a=p.parse_args()
    need(__debug__,'Run without Python optimization; archived replay uses assertions')
    need(digest(a.wine_source)==WINE_SHA,'Wrong Wine source')
    need(digest(a.correction)==V2_PATCH_SHA,'Wrong V2 correction')
    need(digest(a.v1_correction)==V1_PATCH_SHA,'Wrong archived V1 correction')
    output=a.output.resolve();need(not output.exists() and not a.output.is_symlink(),'Fresh output required')
    need(output.parent.is_dir(),'Output parent must exist')
    original_inputs={str(path.resolve()):digest(path) for path in [a.wine_source,a.correction,a.v1_correction,a.comparison,a.managed_results]}
    output.mkdir()
    runner=module(ROOT/'legacy_trace_replay.py','v2_archived_replay')
    old,v1=runner.extract(a.candidate/'vendor/0001-ntdll-CW-HACK-18947.patch',a.v1_correction)
    new=apply_exact(old,a.correction)
    need(text_digest(new)==V2_HELPER_SHA,'Corrected source helper hash mismatch')
    need(new.count('info.Protect')==3 and 'AllocationProtect' not in new,'V2 field references mismatch')
    wine=a.wine_source.read_text()
    validator=extract(wine,'static NTSTATUS get_vprot_flags(')
    binary=native(ROOT/'native_fixture.c',output/'native',a.cc,old,new,validator)
    native_result=json.loads(run([binary],output/'native','run').stdout)
    replay=runner.replay(binary,a.comparison,output/'native')

    validity=output/'protection-validity';validity.mkdir()
    template=(ROOT/'protection_validity_fixture.c.in').read_text()
    chunks={'CONVERSION_TABLE':extract(wine,'static const BYTE VIRTUAL_Win32Flags[16] =')+';',
            'GET_WIN32_PROT':extract(wine,'static DWORD get_win32_prot('),'GET_VPROT_FLAGS':validator,
            'LEGACY_HELPER':old,'V1_HELPER':v1,'CORRECTED_HELPER':new}
    for name,value in chunks.items():template=template.replace('@@'+name+'@@',value)
    source=validity/'protection_validity_fixture.c';source.write_text(template)
    validity_binary=validity/'protection_validity_fixture'
    run([a.cc,'-std=c11','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
         '-fno-omit-frame-pointer',source,'-o',validity_binary],validity,'build')
    validity_result=json.loads(run([validity_binary],validity,'run').stdout)
    need(validity_result['v1_guard_mismatch_regression_reproduced'] and validity_result['v2_guard_mismatch_regression_fixed'],
         'V1/V2 guarded protection regression comparison failed')

    mutants=[
      ('allocation_predicate_reversion',new.replace('if (!status && (info.Protect & 0xf0))','if (!status && (info.AllocationProtect & 0xf0))')),
      ('skip_executable_classification',new.replace('if (!status && (info.Protect & 0xf0))','if (!status && 0)')),
      ('v1_invalid_temporary_mapping',v1),
      ('drop_current_modifiers',new.replace('(info.Protect & ~0xff) | ((info.Protect & 0xf0) >> 4)','((info.Protect & 0xf0) >> 4)')),
      ('collapse_all_executable_to_noaccess',new.replace('(info.Protect & ~0xff) | ((info.Protect & 0xf0) >> 4)','(info.Protect & ~0xff) | PAGE_NOACCESS')),
      ('wrong_access_shift',new.replace('>> 4','>> 5')),
    ]
    mutations=[]
    for name,changed in mutants:
        need(changed!=new,'Mutation did not change source')
        directory=output/('mutation-'+name)
        mutant=native(ROOT/'native_fixture.c',directory,a.cc,old,changed,validator)
        result=run([mutant],directory,'run',success=False)
        need('FAIL:' in result.stderr,'Mutation must fail an explicit assertion')
        mutations.append({'mutation':name,'detected':True,'failure':result.stderr.strip()})
    residual=static_failure(new,output/'first-protect-failure-static',a.cc)
    managed=json.loads(a.managed_results.read_text())
    need(managed['release_source_commit']=='56b9c64381ef9fd59e916dc9bf547d3210ab5db1','Wrong managed source release')
    need(managed['release_methods']['distinct_61_through_360_targets']==300,'Missing managed target coverage')
    source_hashes={path:sha for path,sha in managed['original_input_hashes'].items()
                  if path.endswith('/source/Services/GameInstanceService.cs') or path.endswith('/source/Utils/NativeMethods.cs')}
    need(len(source_hashes)==2 and all(digest(Path(path))==sha for path,sha in source_hashes.items()),'Managed source changed since tests')
    need(all(digest(Path(path))==sha for path,sha in original_inputs.items()),'Original input changed')
    result={'source_patch_sha256':V2_PATCH_SHA,'source_helper_sha256':V2_HELPER_SHA,
            'source_patch_applied_exactly':True,'api_validator_from_pinned_wine_source':True,
            'native_helper':native_result,'protection_validity':validity_result,'historical_write_replay':replay,
            'native_mutations':mutations,'first_protection_failure_static':residual,
            'reused_unchanged_managed_release_results':{'path':str(a.managed_results.resolve()),'sha256':digest(a.managed_results),
                  'release_method_results':managed['release_methods'],'managed_source_bytes_unchanged':True,
                  'other_reused_results':'Managed guard mutations, recorded-operation consistency checks and frontend results remain in the V1 verification audit; not re-executed here.'},
            'original_inputs':original_inputs,'original_input_bytes_unchanged':True,'wine_executed':False,'game_executed':False,
            'native_remote_memory_operation_executed':False,
            'limits':['Source/API model proof; actual Wine, Mach, Rosetta, APC scheduling and game execution remain outside these tests.',
                      'Executable protection failures remain unsafe: failed queue may use uninitialized origprot; target failure may leave NOACCESS; restoration failure may leave execution disabled.',
                      'V2 preserves appropriate non-executable read/write/copy access and modifiers; it intentionally changes temporary protection even when allocation/current executable values agree.',
                      'Synthetic modifier combinations validate argument mapping, not universal query reachability or all set_protection/view restrictions.']}
    save(output/'RESULTS.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
