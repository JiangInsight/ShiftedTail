
import json
import re
import shutil
import subprocess
import struct

import numpy as np

import run_matched as rm
from literature_coverage import SCRATCH
from run_extension import environment
from submission_queries import OUT, WORK

BUDGET = 300
ARMS = ('full', 'opti', 'no_shift', 'no_reuse')
BUILD = WORK / 'instrumented'
RESULTS = OUT / 'mechanisms'


def build():
    BUILD.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    env = environment(1)
    env['CL'] = f'/arch:AVX2 /I"{rm.CODE}" /I"{rm.ROOT}/baselines/boost_math/include"'
    for name in ('uthr_study', 'opti_threshold'):
        src = rm.CODE / (name + '.cpp')
        patch = rm.CODE / 'fair_study' / (src.name + '.patch')
        binary = BUILD / (name + '.exe')
        manifest = RESULTS / (name + '.json')
        if manifest.exists():
            prior = json.loads(manifest.read_text())
            assert prior['source'] == rm.digest(src) and prior['patch'] == rm.digest(patch)
            assert prior['exe'] == rm.digest(binary) and prior['instrumented'] == rm.digest(BUILD/src.name)
            continue
        shutil.copyfile(src, BUILD / src.name)
        subprocess.run(['git', 'apply', '--ignore-space-change', str(patch)], cwd=BUILD, check=True)
        with (RESULTS / (name + '_build.log')).open('w') as log:
            subprocess.run([rm.CODE / 'build.bat', BUILD / src.name, binary], cwd=BUILD,
                           env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        rm.save(manifest, dict(source=rm.digest(src), patch=rm.digest(patch), instrumented=rm.digest(BUILD/src.name),
                               exe=rm.digest(binary), flags=env['CL']))


def sample(graph):
    parent = SCRATCH / graph
    folder = WORK / (graph + '_quarter')
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (graph + '.bin')
    n, u, v, p = rm.read_graph(parent / path.name)
    vertices = np.sort(np.random.default_rng(47).permutation(n)[:n // 4])
    index = np.full(n, -1, np.int32)
    index[vertices] = np.arange(len(vertices))
    keep = (index[u] >= 0) & (index[v] >= 0)
    u, v, p = index[u[keep]], index[v[keep]], p[keep]
    src, dst = np.r_[u, v], np.r_[v, u]
    perm = np.lexsort((dst, src))
    with path.open('wb') as f:
        f.write(struct.pack('<iq', len(vertices), len(src)))
        np.bincount(src, minlength=len(vertices)).astype('<i4').tofile(f)
        dst[perm].astype('<i4').tofile(f)
        np.tile(p, 2)[perm].astype('<f8').tofile(f)
    ref = folder / 'reference.thr'
    env = environment(1)
    env['UTHR_CERT_ORDER'] = str(folder / 'witness')
    for key, args in [('build', [rm.CPU, path, 'frontier', 5, 1, 1, ref]),
                      ('verify', [rm.CODE / 'verify_thresholds.exe', path, ref, folder / 'witness', 1])]:
        status, _ = rm.process(args, env, RESULTS / f'{graph}_quarter_{key}.log', BUDGET)
        assert status == 'ok'
    rm.save(RESULTS / f'{graph}_quarter_input.json', dict(vertices=len(vertices), edges=len(u),
            input_sha256=rm.digest(path), parent_sha256=rm.digest(parent/path.name), seed=47))
    return path


def series(label, path):
    ref = path.parent / 'reference.thr'
    graph_hash = rm.digest(path)
    censored = set()
    for rep in range(1, 4):
        methods = ARMS[rep-1:] + ARMS[:rep-1]
        for arm in methods:
            if arm in censored:
                continue
            name = f'{label}_{rep}_{arm}'
            record = RESULTS / (name + '.json')
            if record.exists():
                row = json.loads(record.read_text())
                assert row['input_sha256'] == graph_hash
            else:
                exe = BUILD / ('opti_threshold.exe' if arm == 'opti' else 'uthr_study.exe')
                target = BUILD / (name + '.thr')
                env = environment(1)
                if arm == 'no_reuse': env['UTHR_RESET_LEVEL'] = '1'
                if arm == 'no_shift': env['UTHR_NOLB'] = '1'
                log = RESULTS / (name + '.log')
                status, sec = rm.process([exe, path, 'opti' if arm == 'opti' else 'frontier', 5, 1, 1, target],
                                         env, log, BUDGET)
                row = dict(graph=label, arm=arm, rep=rep, status=status, seconds=sec, budget_s=BUDGET,
                           workers=1, exe_sha256=rm.digest(exe), input_sha256=graph_hash)
                if status == 'ok':
                    row.update(rm.compare(ref,target))
                    raw = log.read_text()
                    counters = re.search(r'^work (.+)$', raw, re.M).group(1)
                    row['work'] = {k:int(v) for k,v in (x.split('=') for x in counters.split())}
                    row['host_peak_mib'] = int(re.search(r'peak_mb=(\d+)', raw).group(1))
                    row['output_sha256'] = rm.digest(target)
                    if row['max_abs'] > 1e-9: row['status'] = 'invalid'
                    if arm == 'full': assert row['output_sha256'] == rm.digest(ref)
                rm.save(record, row)
                print(name, row['status'], round(sec, 2), flush=True)
            if row['status'] != 'ok':
                censored.add(arm)
    return censored


def main():
    build()
    for graph in ('Twitter', 'HepPh', 'WebGoogle'):
        missing = series(graph, SCRATCH / graph / (graph + '.bin'))
        if missing:
            series(graph + '_quarter', sample(graph))


if __name__ == '__main__':
    main()
