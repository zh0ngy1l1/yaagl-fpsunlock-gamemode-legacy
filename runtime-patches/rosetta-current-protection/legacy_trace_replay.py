# Import-only archive: original V1 extract()/replay() bodies retained verbatim.
#!/usr/bin/env python3
"""Extract matching helper, compile host-only mocks, replay existing trace inputs.

No Wine executable/library, game process, native process-memory interface or
observer is started. Historical traces are read-only inputs. The concurrent read
is an intentional model schedule, not a recovered historical event.
"""
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
PATCH_SHA = '41277c5b18fffcd7aa71a33c5f6ba33d2c91f262dc7b1f5855b8951a563d464c'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')

def extract(patch, correction):
    if digest(patch) != PATCH_SHA:
        raise ValueError('Matching downstream patch hash changed; review before extracting')
    additions = '\n'.join(line[1:] for line in patch.read_text().splitlines()
                          if line.startswith('+') and not line.startswith('+++'))
    start = additions.index('static void toggle_executable_pages_for_rosetta(')
    brace = additions.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (additions[end] == '{') - (additions[end] == '}')
        end += 1
    helper = additions[start:end] + '\n'
    if helper.count('info.AllocationProtect') != 2:
        raise ValueError('Expected exactly the two reviewed AllocationProtect references')
    # Apply the actual submitted source patch to the helper, using its complete
    # context with no fuzz. The compiled corrected helper is not a blind string
    # replacement oracle. The final assertion restricts this candidate's scope.
    hunks = []
    old, new, active = [], [], False
    for line in correction.read_text().splitlines(keepends=True):
        if line.startswith('@@'):
            if active: hunks.append((''.join(old), ''.join(new)))
            old, new, active = [], [], True
        elif active:
            if line.startswith(' '): old.append(line[1:]); new.append(line[1:])
            elif line.startswith('-'): old.append(line[1:])
            elif line.startswith('+'): new.append(line[1:])
            elif line.startswith('\\ No newline'): pass
            else: raise ValueError('Unexpected source correction patch content')
    if active: hunks.append((''.join(old), ''.join(new)))
    if not hunks: raise ValueError('Source correction has no patch hunks')
    corrected = helper
    for before, after in hunks:
        if corrected.count(before) != 1:
            raise ValueError('Source correction context does not match helper exactly once')
        corrected = corrected.replace(before, after, 1)
    if corrected != helper.replace('info.AllocationProtect', 'info.Protect'):
        raise ValueError('Source correction does not contain exactly the reviewed two operand changes')
    return helper, corrected

def replay(binary, comparison_path, output):
    comparison = json.loads(comparison_path.read_text())
    records, native_inputs, write_metadata = {}, [], []
    labels = {
        'failure103906': 'Startup crash after automatic activation; original verdict remains failed.',
        'automatic095434': 'World/gameplay survival reported; original observer interval failure remains.',
        'manual012240': 'Successful first manually delayed foreground interval; separate later failures remain.',
        'lateworld111957': 'World/gameplay survival reported; original missing-end-marker measurement failure remains.'
    }
    for name, item in comparison.items():
        path = Path(item['path'])
        if digest(path) != item['sha256']:
            raise ValueError(f'{name}: historical trace hash changed')
        events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        queries, reads, writes, read_counts, read_order = {}, {}, [], collections.Counter(), []
        identity = next(e['detail'] for e in events if e['kind'] == 'identity')
        for event in events:
            operation = event.get('operation', 0)
            if event['kind'] == 'query_before_write':
                queries[operation] = event
            elif event['kind'] == 'read':
                reads[operation] = event
                key = (event.get('api_success'), event.get('bytes'), event.get('value'), event.get('target'))
                read_counts[str(event.get('value'))] += 1
                if read_order and read_order[-1]['input'] == list(key): read_order[-1]['count'] += 1
                else: read_order.append({'input': list(key), 'count': 1, 'first_operation': operation})
            elif event['kind'] == 'write_attempt':
                query, read = queries[operation], reads[operation]
                assert query.get('api_success') and query.get('bytes') == 48
                assert query['sequence'] < event['sequence'] and query['address'] == event['address']
                assert read.get('api_success') and read.get('bytes') == 4
                assert read['value'] != event['target'] and event['value'] == read['value']
                assert event.get('api_success') and event.get('bytes') == 4
                region = query['region']
                assert int(event['address'], 16) == 0x1452b4244
                assert region['allocation_protect'] == 0x80 and region['protect'] == 8
                assert region['state'] == 0x1000 and region['type'] == 0x1000000
                write = {'operation': operation, 'sequence': event['sequence'],
                         'before': read['value'], 'target': event['target'],
                         'pid': event['pid'], 'address': event['address'],
                         'sample_sequence': query['sequence'], 'sample_region': region,
                         'recorded_api_success': event['api_success'], 'recorded_bytes': event['bytes']}
                writes.append(write)
                for corrected in (0, 1):
                    native_inputs.append(f"{corrected} {event['target']} {read['value']} "
                                         f"{region['allocation_protect']:x} {region['protect']:x} 0 4 0 1\n")
                    write_metadata.append((name, len(writes) - 1, corrected))
        records[name] = {'trace': str(path), 'trace_sha256': item['sha256'],
                         'identity': identity, 'preserved_verdict': labels[name],
                         'read_counts': dict(read_counts), 'read_order_runs': read_order,
                         'writes': writes}
    batch = subprocess.run([str(binary), '--batch'], input=''.join(native_inputs),
                           text=True, capture_output=True, check=True)
    native_outputs = [json.loads(line) for line in batch.stdout.splitlines()]
    assert len(native_outputs) == len(write_metadata)
    for metadata, result in zip(write_metadata, native_outputs):
        name, index, corrected = metadata
        write = records[name]['writes'][index]
        assert result['status'] == 0 and result['bytes'] == 4
        assert result['value'] == write['target'] and result['neighbor_unchanged'] == 1
        assert result['protect_calls'] == (0 if corrected else 2)
        assert result['fps_probe_faults'] == (0 if corrected else 1)
        assert result['neighbor_probe_faults'] == (0 if corrected else 1)
        write['corrected_model' if corrected else 'legacy_model'] = result
    expected = {'failure103906': 4, 'automatic095434': 4, 'manual012240': 1, 'lateworld111957': 1}
    assert {name: len(record['writes']) for name, record in records.items()} == expected
    report = {
        'method': 'Source-extracted helper with mocked target query/protection APIs; recorded pre-write page samples and write payloads.',
        'historical_outcomes_reclassified': False,
        'fault_time_page_state_recovered': False,
        'concurrent_read_schedule': 'Constructed: after first protection change if any; otherwise after helper returns with unchanged protection.',
        'limits': [
            'Pre-write VirtualQueryEx samples are inputs; the actual helper query and fault-time page state were not recorded.',
            'All legacy replayed writes expose the modeled hazard under the forced schedule, including writes from surviving runs.',
            'This establishes a code path and its removal for the sampled data pages; it does not establish historical fault timing or gameplay reliability.',
            'Other threads, Mach memory copying, APC delivery and Rosetta translation are mocked or outside this fixture.'
        ],
        'runs': records,
        'write_cases': sum(expected.values()),
        'helper_variant_cases': len(native_outputs),
        'trace_inputs_unchanged': all(digest(Path(v['path'])) == v['sha256'] for v in comparison.values()),
    }
    save(output / 'TRACE-REPLAY.json', report)
    return {'runs': len(records), 'writes': sum(expected.values()),
            'legacy_protection_calls': sum(w['legacy_model']['protect_calls'] for r in records.values() for w in r['writes']),
            'corrected_protection_calls': sum(w['corrected_model']['protect_calls'] for r in records.values() for w in r['writes']),
            'original_verdicts_preserved': True, 'trace_inputs_unchanged': report['trace_inputs_unchanged']}
