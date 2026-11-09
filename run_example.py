import csv
import os
from pathlib import Path
import struct
import subprocess
import tempfile

from verify_example import V, oracle

root = Path(__file__).resolve().parent
with (root / "data/edges.csv").open(newline="") as stream:
    edges = list(csv.DictReader(stream))
adjacency = [[] for _ in V]
for edge in edges:
    u, v, p = int(edge["u"]), int(edge["v"]), float(edge["probability"])
    adjacency[u].append((v, p))
    adjacency[v].append((u, p))
neighbors = [pair for row in adjacency for pair in sorted(row)]
environment = {k:v for k,v in os.environ.items() if not k.startswith("UTHR_")}
environment.update(UTHR_COALESCE="1", UTHR_GROUP_BASE="1", UTHR_INDEXED="1")
with tempfile.TemporaryDirectory() as tmp:
    work = Path(tmp)
    graph, rows, order = (work / n for n in ("graph.bin","rows.thr","order.bin"))
    graph.write_bytes(struct.pack("<iQ",len(V),len(neighbors))
                      + b"".join(struct.pack("<I",len(row)) for row in adjacency)
                      + b"".join(struct.pack("<I",v) for v,p in neighbors)
                      + b"".join(struct.pack("<d",p) for v,p in neighbors))
    environment["UTHR_CERT_ORDER"] = str(order)
    subprocess.run([root/"build/shifted_tail.exe",graph,"frontier","5","1","1",rows],
                   check=True,env=environment)
    subprocess.run([root/"build/verify_thresholds.exe",graph,rows,order,"1"],check=True)
    seen = set()
    with rows.open("rb") as stream:
        while header := stream.read(12):
            level, count = struct.unpack("<IQ",header)
            values = struct.unpack(f"<{count}d",stream.read(8*count))
            for vertex, value in enumerate(values):
                if (level,vertex) in seen or abs(value-float(oracle(level,vertex)))>1e-12:
                    raise ValueError((level,vertex,value))
                seen.add((level,vertex))
    expected = {(1,v) for v in V} | {(2,v) for v in (0,1,2)}
    if seen != expected:
        raise ValueError(seen)
print("All seven thresholds agree with exhaustive vertex-subset evaluation.")
