
import json
import subprocess
import sys
from statistics import median

import numpy as np

import run_matched as rm
from run_extension import environment
from run_queries import QUERIES
from literature_queries import enclosure

OUT = rm.ROOT / 'results/submission_study'
WORK = rm.WORK / 'submission_study'
STACK = rm.DATA / 'Stack.bin'
SOURCE = rm.ROOT / 'results/study/stack_native_cert'


def extended_drivers():
    dest = WORK / 'query_drivers'
    dest.mkdir(parents=True, exist_ok=True)
    original = rm.CODE / 'fair_study/query_workload.cpp'
    code = original.read_text()
    old = 'const double queries[]={.5,.1,.9,.3,.7,.2,.8,.4,.6};'
    assert code.count(old) == code.count('i<9;++i') == 1
    updated = code.replace(old, old.replace('.4,.6}', '.4,.6,.05,.95,.15,.85,.25,.75,.35,.65,.45}'))
    updated = updated.replace('i<9;++i','i<static_cast<int>(sizeof(queries)/sizeof(queries[0]));++i')
    source = dest / 'query_workload.cpp'
    source.write_text(updated)
    env = environment(24)
    gcc = rm.ROOT.parent / 'paper1/tools/dl_winlibs/mingw64/bin/g++.exe'
    lib = rm.WORK / 'deps/ucrt64'
    author = rm.WORK / 'UncertainCore/src'
    common = [gcc, '-O3', '-march=native', '-fopenmp', '-std=gnu++17']
    flags = {'index_refined': ['-DREFINE_QUERY', '-ffp-contract=off', source, '-I'+str(original.parent), '-I'+str(lib/'include'), '-L'+str(lib/'lib'), '-lgmpxx', '-lgmp'],
             'dai_queries': ['-DDIRECT','-I'+str(author),'-I'+str(lib/'include'),source,author/'graph.cpp',author/'uncertain-core.cpp',
                             author/'uncertain-core-topdown.cpp','-L'+str(lib/'lib'),'-lgsl','-lgslcblas','-lgmp']}
    for name,args in flags.items():
        exe = dest/(name+'.exe')
        record = dest/(name+'.json')
        if record.exists():
            cached = json.loads(record.read_text())
            assert cached['source'] == rm.digest(source) and cached['binary'] == rm.digest(exe)
            continue
        with (dest/(name+'.log')).open('w') as log:
            subprocess.run(list(map(str,common+args+['-o',exe])),env=env,cwd=dest,stdout=log,stderr=subprocess.STDOUT,check=True)
        rm.save(record,dict(original=rm.digest(original),source=rm.digest(source),binary=rm.digest(exe)))
    return dest


def stack_queries(extended=False):
    queries = QUERIES
    series = 'queries'
    binaries = rm.WORK
    if extended:
        base = {m: [json.loads((OUT/'queries'/f'{rep}_{m}'/'record.json').read_text()) for rep in range(1,4)]
                for m in ('refined','topdown','bottomup')}
        assert all(r['status']=='ok' for rows in base.values() for r in rows)
        last = {m: median(r['prefixes'][-1] for r in rows) for m,rows in base.items()}
        if last['refined'] < min(last['topdown'],last['bottomup']):
            return
        series = 'queries18'
        queries += (.05,.95,.15,.85,.25,.75,.35,.65,.45)
        binaries = extended_drivers()
    rank = np.fromfile(rm.DATA / 'Stack.rank', '<u4')
    lower, upper = enclosure(SOURCE / 'values.thr', rank, queries)
    graph_sha = rm.digest(STACK)
    for rep, methods in enumerate([('refined', 'topdown', 'bottomup'), ('bottomup', 'refined', 'topdown'),
                                   ('topdown', 'bottomup', 'refined')], 1):
        for method in methods:
            case = OUT / series / f'{rep}_{method}'
            work = WORK / series / f'{rep}_{method}'
            case.mkdir(parents=True, exist_ok=True)
            work.mkdir(parents=True, exist_ok=True)
            record = case / 'record.json'
            if record.exists():
                continue
            env = environment(24)
            stages = []
            if method == 'refined':
                env['UTHR_CERT_ORDER'] = str(work / 'removals')
                stages = [('build', [rm.CPU, STACK, 'frontier', 5, 24, 1, work / 'values']),
                          ('verify', [rm.CODE / 'verify_thresholds.exe', STACK, work / 'values', work / 'removals', 24]),
                          ('rank', [rm.CODE / 'export_rank.exe', STACK, work / 'rank'])]
                query = [binaries / 'index_refined.exe', work / 'values', 24, work / 'rank', work / 'result', STACK]
            else:
                query = [binaries / 'dai_queries.exe', STACK, 24, 6 if method == 'topdown' else 4, work / 'result']
            stages.append(('query', query))
            row = dict(graph='Stack', rep=rep, method=method, input_sha256=graph_sha, stages={}, cap_s=1800,
                       binary_sha256={}, status='ok', prefixes=[], outside=[], hashes=[])
            for name, args in stages:
                row['binary_sha256'][name] = rm.digest(args[0])
                status, sec = rm.process(args, env, case / (name + '.log'), row['cap_s'])
                row['stages'][name] = sec
                if status != 'ok':
                    row['status'] = name + '_' + status
                    break
            if method == 'refined' and 'query' in row['stages']:
                assert rm.digest(work / 'values') == rm.digest(SOURCE / 'values.thr')
                assert rm.digest(work / 'rank') == rm.digest(rm.DATA / 'Stack.rank')
            if 'query' in row['stages']:
                charge = sum(sec for key, sec in row['stages'].items() if key != 'query')
                for line in (case / 'query.log').read_text(errors='replace').splitlines():
                    if not line.startswith('ANSWER '):
                        continue
                    _, i, eta, _, prefix = line.split()
                    i = int(i)
                    assert i == len(row['prefixes']) and queries[i] == float(eta)
                    p = work / f'result-{i}.bin'
                    arr = np.fromfile(p, '<i4')
                    assert len(arr) == len(rank)
                    a = arr[rank]
                    row['prefixes'].append(charge + float(prefix))
                    row['outside'].append(int(((a < lower[i]) | (a > upper[i])).sum()))
                    row['hashes'].append(rm.digest(p))
                if any(row['outside']) or (row['status'] == 'ok' and len(row['prefixes']) != len(queries)):
                    row['status'] = 'invalid'
            if extended:
                previous = json.loads((OUT/'queries'/f'{rep}_{method}'/'record.json').read_text())
                assert row['hashes'][:9] == previous['hashes']
            rm.save(record, row)
            print(case.name, row['status'], row['prefixes'], flush=True)


if __name__ == '__main__':
    stack_queries(extended='--extended' in sys.argv)
