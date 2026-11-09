from fractions import Fraction as F
from itertools import combinations
from pathlib import Path
from tempfile import TemporaryDirectory
import struct
import subprocess
import sys

V = tuple(range(4))
EDGES = {(0, 1): F(3, 4), (0, 2): F(3, 4), (1, 2): F(3, 4), (2, 3): F(1, 2)}
ROWS = {2: [F(9, 16)] * 3, 1: [F(15, 16)] * 3 + [F(1, 2)]}
ORDER = {2: [0, 1, 2], 1: [3, 0, 1, 2]}

def tail(k, v, members):
    s = [F(1)] + [F(0)] * k
    for u in members:
        p = EDGES.get(tuple(sorted((u, v))), F(0))
        for j in range(k, 0, -1):
            s[j] = (1-p)*s[j] + p*s[j-1]
    return s[k]

def oracle(k, v):
    return max(min(tail(k, u, group) for u in group)
               for size in range(1, len(V)+1)
               for group in combinations(V, size) if v in group)

def errors(k, values, order):
    shortfall = max([F(0)] + [t - tail(k, v, [u for u, a in enumerate(values) if a >= t])
                              for v, t in enumerate(values)])
    upper = F(0)
    excess = F(0)
    for i, v in enumerate(order):
        upper = max(upper, tail(k, v, order[i:]))
        excess = max(excess, upper - values[v])
    return shortfall, excess

def write_rows(path, data, element):
    with path.open("wb") as out:
        for k in (2, 1):
            row = data[k]
            out.write(struct.pack("<IQ", k, len(row)))
            out.write(struct.pack("<" + element*len(row), *row))

def cross_check(exe):
    with TemporaryDirectory() as tmp:
        folder = Path(tmp)
        graph, values, order = [folder / n for n in ("graph", "values", "order")]
        lists = [[(u, EDGES[tuple(sorted((u,v)))]) for u in V if tuple(sorted((u,v))) in EDGES] for v in V]
        graph.write_bytes(struct.pack("<IQ4I", 4, 8, *map(len, lists)) +
                          struct.pack("<8I", *(u for row in lists for u,_ in row)) +
                          struct.pack("<8d", *(p for row in lists for _,p in row)))
        write_rows(values, ROWS, "d")
        write_rows(order, ORDER, "I")
        cmd = [str(exe), str(graph), str(values), str(order), "1"]
        subprocess.run(cmd, check=True)
        bad = {**ROWS, 1: [F(15, 16), F(15, 16), F(1), F(1, 2)]}
        write_rows(values, bad, "d")
        assert subprocess.run(cmd).returncode == 3
        write_rows(values, ROWS, "d")
        write_rows(order, {**ORDER, 1: [2, 3, 0, 1]}, "I")
        assert subprocess.run(cmd).returncode == 3

if __name__ == "__main__":
    for k, row in ROWS.items():
        for v in V:
            assert oracle(k, v) == (row[v] if v < len(row) else 0)
        assert errors(k, row, ORDER[k]) == (0, 0)
    assert errors(1, ROWS[1], [2, 3, 0, 1])[1] >= F(1, 32)
    assert errors(1, [F(15, 16), F(15, 16), F(1), F(1, 2)], ORDER[1])[0] == 1
    if len(sys.argv) > 1:
        cross_check(Path(sys.argv[1]).resolve())
    print("All exact subset checks and requested verifier checks passed.")
