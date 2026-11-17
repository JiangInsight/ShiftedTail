
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
PAPER1 = ROOT.parent / "paper1"
JOBS = [
    ("stack", ROOT / "results/stack.wbin", 4, 464.92),
    ("orkut", PAPER1 / "data/bin/com-orkut.bin", 3, 4483.69),
]


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def persist(folder, state):
    tmp = folder / "status.tmp"
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(folder / "status.json")


def check_output(path, levels, vertices, total):

    count = 0
    higher = np.empty(0)
    max_inversion = 0.
    with path.open("rb") as stream:
        for expected in range(levels, 0, -1):
            level, n = struct.unpack("<IQ", stream.read(12))
            if level != expected or not len(higher) <= n <= vertices:
                raise ValueError(f"unexpected layer {level}, size {n}")
            values = np.fromfile(stream, dtype="<f8", count=n)
            if len(values) != n or not np.isfinite(values).all():
                raise ValueError(f"incomplete or nonfinite layer {level}")
            if values.min() < -1e-9 or values.max() > 1 + 1e-9:
                raise ValueError(f"probability out of range in layer {level}")
            if higher.size:
                max_inversion = max(max_inversion, float(np.max(higher - values[:higher.size])))
            higher = values
            count += n
        if count != total or stream.read(1) or max_inversion > 1e-9:
            raise ValueError(f"layer audit failed: count={count}, inversion={max_inversion}")
    return {"layers": levels, "thresholds": count, "max_layer_monotonicity_violation": max_inversion}


def run(folder, job, record):
    name, graph, model, published = job
    partial = folder / f"{name}.partial.thr"
    args = [PAPER1 / "code/memcap2.exe", "32768", CODE / "uthr.exe", graph, "lazy",
            str(model), "24", "1", partial]
    env = {k: v for k, v in os.environ.items() if not k.startswith(("UTHR_", "OMP_", "MEMCAP_"))}
    env["UTHR_TOL"] = "1e-12"
    env["OMP_NUM_THREADS"] = "24"
    record.update(args=[str(a) for a in args], input_sha256=sha(graph),
                  input_bytes=graph.stat().st_size, published_gpu_seconds=published)
    start = time.monotonic()
    logfile = folder / f"{name}.log"
    with logfile.open("x") as log:
        result = subprocess.run(args, cwd=CODE, env=env, stdout=log, stderr=subprocess.STDOUT,
                                timeout=8*3600)
    record.update(wall_seconds=time.monotonic()-start, exit_code=result.returncode)
    result.check_returncode()
    log = logfile.read_text(errors="replace")
    header = re.search(r"\bn=(\d+) m=(\d+) dmax=(\d+) kmax=(\d+) sum_core=(\d+)", log)
    final = re.search(r"^result method=lazy time=([\d.]+)s .*?thresholds=(\d+) .*?hash=([a-f\d]+)", log, re.M)
    if not header or not final or "ERROR level" in log or "memory limit reached" in log:
        raise ValueError("incomplete result or solver diagnostic")
    vertices, edges, dmax, levels, total = map(int, header.groups())
    if total != int(final[2]):
        raise ValueError("computed output count differs from the support-core sum")
    record.update(check_output(partial, levels, vertices, total))
    output = folder / f"{name}.thr"
    partial.replace(output)
    seconds = float(final[1])
    record.update(status="complete", solver_seconds=seconds, vertices=vertices, edges=edges,
                  max_degree=dmax, solver_hash=final[3], output=output.name,
                  published_gpu_to_cpu_ratio=published/seconds)


def main():
    folder = ROOT / "results/threshold_gate" / datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    folder.mkdir(parents=True)
    state = {"pid":os.getpid(), "status":"running", "threads":24, "seed":1,
             "memory_limit_mib":32768, "shortcut_tolerance":1e-12,
             "reference":"https://www.vldb.org/pvldb/vol19/p2591-gao.pdf#page=10",
             "reference_note":"Table 3, published RTX 3090, single precision. Local CPU uses doubles; input files were reconstructed, not supplied by the authors.",
             "binary_sha256":sha(CODE/"uthr.exe"), "source_sha256":sha(CODE/"uthr.cpp"),
             "jobs":{j[0]:{"status":"queued"} for j in JOBS}}
    print(folder, flush=True)
    for job in JOBS:
        record = state["jobs"][job[0]]
        record.update(status="running", started=datetime.datetime.now().isoformat(timespec="seconds"))
        persist(folder,state)
        try:
            run(folder, job, record)
        except (OSError, ValueError, struct.error, subprocess.SubprocessError) as e:
            record.update(status="failed", error=str(e))
        record["ended"] = datetime.datetime.now().isoformat(timespec="seconds")
        persist(folder,state)
    state["status"] = "complete" if all(r["status"]=="complete" for r in state["jobs"].values()) else "needs_review"
    persist(folder,state)
    return int(state["status"]!="complete")


if __name__ == "__main__":
    raise SystemExit(main())
