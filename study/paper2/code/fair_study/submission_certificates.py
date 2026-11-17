
import json
import re
import struct

import numpy as np

import run_matched as rm
from literature_coverage import SCRATCH
from run_extension import environment
from submission_queries import OUT, WORK

CERT = OUT / 'certificates'
LITERATURE = rm.ROOT / 'results/literature_coverage'


def peak(path):
    return int(re.search(r'peak_mb=(\d+) exit=0', path.read_text()).group(1))


def certificate(path):
    line = re.search(r'^certificate (.+)$', path.read_text(), re.M).group(1)
    return dict(x.split('=') for x in line.split())


def measure(graph, values, order, build, verify, build_logs, verify_logs):
    recs = [certificate(p) for p in verify_logs]
    assert all(r == recs[0] for r in recs)
    c = recs[0]
    n = int(c['values'])
    assert values.stat().st_size - order.stat().st_size == 4 * n
    row = dict(graph=graph, values=n, table_bytes=values.stat().st_size, extra_witness_bytes=order.stat().st_size,
               values_sha256=rm.digest(values), witness_sha256=rm.digest(order),
               build_s=build, verify_s=verify, build_peak_mib=[peak(p) for p in build_logs],
               verify_peak_mib=[peak(p) for p in verify_logs], lower_deficit=float(c['max_lower_deficit']),
               upper_excess=float(c['max_upper_excess']), unique_six_decimal=int(c['unique_rounding_6dp']))
    assert max(row['lower_deficit'], row['upper_excess']) <= 1e-9
    return row


def flickr():
    path = rm.DATA/'Flickr.bin'
    vertices = (1986, 1987)
    with path.open('rb') as f:
        n, arcs = struct.unpack('<iq', f.read(12))
        degrees = np.fromfile(f, '<i4', n)
        off = np.r_[0, degrees.cumsum()]
        neighbors = np.fromfile(f, '<i4', arcs)
        probabilities = np.fromfile(f, '<f8', arcs)
    assert [degrees[v] for v in vertices] == [1, 1]
    assert [neighbors[off[v]] for v in vertices] == list(reversed(vertices))
    assert all(probabilities[off[v]] == .5 for v in vertices)
    paths = dict(point=rm.WORK/'answers/Flickr_24_1_index/result-0.bin',
                 refined=rm.WORK/'refined/Flickr_t24_r1_refined/result-0.bin',
                 dai_topdown=rm.WORK/'answers/Flickr_24_1_topdown/result-0.bin')
    answers = {k:np.fromfile(p,'<i4')[list(vertices)].tolist() for k,p in paths.items()}
    assert answers['point'] == [0,0] and answers['refined'] == answers['dai_topdown'] == [1,1]
    return dict(graph='Flickr', csr_vertex_ids=vertices, degrees=[1,1], eta=.5, edge_probability=.5,
                inclusive_truth=[1,1], actual_answers=answers, input_sha256=rm.digest(path))


def main():
    CERT.mkdir(parents=True, exist_ok=True)
    wiki = SCRATCH/'WikiTalkFR'
    wbuild = LITERATURE/'runs/WikiTalkFR_reference_t24_r0'
    wt = json.loads((wbuild/'record.json').read_text())
    assert wt['status'] == 'ok' and wt['output_sha256'] == rm.digest(wiki/'reference.thr')
    wr = []
    wlogs = []
    for rep in range(1,4):
        log = CERT/f'wiki_verify_{rep}.log'
        meta = CERT/f'wiki_verify_{rep}.json'
        if not meta.exists():
            args = [rm.CODE/'verify_thresholds.exe',wiki/'WikiTalkFR.bin',wiki/'reference.thr',wiki/'removals.bin',24]
            status, sec = rm.process(args, environment(24), log, 300)
            rm.save(meta, dict(status=status, seconds=sec))
        rec = json.loads(meta.read_text())
        assert rec['status'] == 'ok'
        wr.append(rec['seconds'])
        wlogs.append(log)
    rows = []
    builds, checks, blogs, logs = [], [], [], []
    for rep in range(1,4):
        case = OUT/'queries'/f'{rep}_refined'
        q = json.loads((case/'record.json').read_text())
        assert q['status'] == 'ok'
        builds.append(q['stages']['build'])
        checks.append(q['stages']['verify'])
        blogs.append(case/'build.log')
        logs.append(case/'verify.log')
    stack = WORK/'queries/1_refined'
    rows.append(measure('Stack', stack/'values', stack/'removals', builds, checks, blogs, logs))
    rows.append(measure('Wiki-Pe', wiki/'reference.thr', wiki/'removals.bin',
                        [wt['process_wall_s']], wr, [wbuild/'run.log'], wlogs))
    deli = SCRATCH/'one_level'
    logs = LITERATURE/'large/one_level'
    old = json.loads((logs/'Deli.json').read_text())
    assert old['status'] == old['check'] == 'ok' and old['output_sha256'] == rm.digest(deli/'Deli.thr')
    rows.append(measure('Deli, one level in flight', deli/'Deli.thr', deli/'Deli.ord',
                        [old['wall_s']], [old['verify_wall_s']], [logs/'Deli.log'], [logs/'Deli_verify.log']))
    rm.save(CERT/'summary.json',rows)
    rm.save(CERT/'flickr_pair.json',flickr())
    print('certified rows', [(r['graph'], r['values']) for r in rows], flush=True)


if __name__ == '__main__':
    main()
