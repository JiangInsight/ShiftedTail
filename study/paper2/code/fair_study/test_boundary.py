
from fractions import Fraction as F
from itertools import combinations
import json
import random
import struct
import subprocess

import numpy as np
from run_queries import QUERIES
from run_matched import WORK
from run_extension import environment


def oracle(n, edges):
    levels = [[F(0)] * n for _ in range(n)]
    support = [0] * n
    for mask in range(1, 1 << n):
        nodes = [u for u in range(n) if mask >> u & 1]
        incident = {u: [] for u in nodes}
        for (u, v), p in edges.items():
            if u in incident and v in incident:
                incident[u].append(F(p))
                incident[v].append(F(p))
        degree = min(map(len, incident.values()))
        for u in nodes:
            support[u] = max(support[u], degree)
        tails = []
        for probs in incident.values():
            a = [F(1)] + [F(0)] * degree
            for p in probs:
                for k in range(degree, 0, -1):
                    a[k] = (1 - p) * a[k] + p * a[k-1]
            tails.append(a)
        for k in range(1, degree + 1):
            minimum = min(t[k] for t in tails)
            for u in nodes:
                levels[k][u] = max(levels[k][u], minimum)
    return levels, support


def main():
    folder = WORK / 'boundary_smoke'
    folder.mkdir(exist_ok=True)
    stats = []
    for seed in range(10):
        rng = random.Random(seed)
        n = 7
        edges = {(0,1): .5, (2,3): 1., (2,4): .5, (3,4): 1.}
        if seed:
            for pair in combinations(range(n), 2):
                if rng.random() < .48:
                    edges[pair] = rng.choice([.1, .3, .5, .7, 1., float(np.nextafter(.5, 0)), .8])
        levels, support = oracle(n, edges)
        rank = sorted(range(n), key=lambda u: -support[u])
        with (folder/'g.bin').open('wb') as out:
            out.write(struct.pack('<IQ', n, len(edges)*2))
            rows = [sorted((b if a == u else a, p) for (a,b),p in edges.items() if u in (a,b)) for u in range(n)]
            np.array(list(map(len,rows)), '<u4').tofile(out)
            np.array([v for r in rows for v,p in r], '<u4').tofile(out)
            np.array([p for r in rows for v,p in r], '<f8').tofile(out)
        np.array(rank, '<u4').tofile(folder/'rank')
        with (folder/'values').open('wb') as out:
            for k in range(max(support), 0, -1):
                nodes = [v for v in rank if support[v] >= k]
                out.write(struct.pack('<IQ', k, len(nodes)))
                np.array([min(1.,max(0.,float(levels[k][v]) + rng.choice([-.4e-9, .4e-9]))) for v in nodes], '<f8').tofile(out)
        run = subprocess.run([WORK/'index_refined.exe', folder/'values','2',folder/'rank',folder/'result',folder/'g.bin'],
                             capture_output=True, check=True, text=True, env=environment(2))
        for i, eta in enumerate(QUERIES):
            actual = np.fromfile(folder/f'result-{i}.bin','<i4').tolist()
            expected = [max([0]+[k for k in range(1,n) if levels[k][v]>=F(eta)]) for v in range(n)]
            assert actual == expected,(seed,eta,actual,expected)

        for threads in (1, 3):
            subprocess.run([WORK/'ucef.exe',folder/'g.bin',str(threads),folder/'ucef'],check=True)
            with (folder/'ucef').open('rb') as out:
                for k in range(max(support),0,-1):
                    level,count = struct.unpack('<IQ',out.read(12))
                    assert level == k and count == sum(c>=k for c in support)
                    delta = abs(np.fromfile(out,'<f8',count)-[float(levels[k][u]) for u in rank[:count]])
                    assert delta.max() <= 1e-12,(seed,threads,k,delta.max())
                assert not out.read(1)
        stats.append(dict(seed=seed,checks=[list(map(int,line.split()[2:])) for line in run.stdout.splitlines() if line.startswith('REFINE ')]))
    assert sum(row[2] for case in stats for row in case['checks']) > 0
    from run_extension import OUT
    (OUT/'exhaustive.json').write_text(json.dumps(stats,indent=2))


if __name__=='__main__':main()
