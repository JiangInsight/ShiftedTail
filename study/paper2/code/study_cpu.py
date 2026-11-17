
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

import numpy as np
from run_threshold_gate import ROOT, CODE, PAPER1, check_output


def run(name, graph, model, method, threads, variant, reference, limit, binary):
    folder = ROOT / "results/study" / name
    folder.mkdir(parents=True, exist_ok=False)
    env = {k: v for k,v in os.environ.items() if not k.startswith(("UTHR_", "OMP_", "MEMCAP_"))}
    env.update(OMP_NUM_THREADS=str(threads), UTHR_TOL="1e-12")
    flags={"no-shift":"UTHR_NOLB", "no-shortcut":"UTHR_NOSHORT",
           "coalesce":"UTHR_COALESCE", "general":"UTHR_NOHOMOGENEOUS",
           "no-floor":"UTHR_NOCOREFLOOR","group":"UTHR_GROUP_BASE","screen":"UTHR_TAIL_SCREEN","indexed":"UTHR_INDEXED"}
    for change in variant.split("+"):
        if change=="order":
            env["UTHR_CERT_ORDER"]=str(folder/"removals.bin")
        elif change!="full":
            env[flags[change]]="1"
    out = folder / "values.partial.thr"
    args = list(map(str,[PAPER1/"code/memcap2.exe",32768,binary,graph,method,model,threads,1,out]))
    state = dict(args=args,variant=variant,status="running",binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                 comparison_file=str(reference) if reference else None, tolerance=1e-12)
    meta = folder / "record.json"
    meta.write_text(json.dumps(state,indent=2))
    start = time.monotonic()
    try:
        with (folder/"run.log").open("w") as log:
            ret = subprocess.run(args,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=limit)
        state["process_wall_s"]=time.monotonic()-start
        ret.check_returncode()
        log = (folder/"run.log").read_text(errors="replace")
        match = re.search(r"n=(\d+) m=\d+ dmax=\d+ kmax=(\d+) sum_core=(\d+)",log)
        final = re.search(r"^result (.+)",log,re.M)
        if not final or not match or "ERROR level" in log or "memory limit reached" in log:
            raise RuntimeError("incomplete result, inspect run.log")
        n,k,total=map(int,match.groups())
        fields=dict(item.split("=",1) for item in final[1].split())
        assert int(fields['thresholds'])==total
        state.update(check_output(out,k,n,total), fields=fields)
        if reference:
            import struct
            mx=0.; bad=0; pairs=0
            with reference.open("rb") as a,out.open("rb") as b:
                while header:=a.read(12):
                    if b.read(12)!=header: raise ValueError("level/rank layout mismatch")
                    _,cnt=struct.unpack("<IQ",header)
                    delta=np.abs(np.fromfile(a,'<f8',cnt)-np.fromfile(b,'<f8',cnt))
                    mx=max(mx,float(delta.max())); bad+=int((delta>1e-9).sum()); pairs+=cnt
                assert not b.read(1) and pairs==total
            state.update(compared=pairs,max_abs=mx,above_1e_minus_9=bad)
            if bad: raise ValueError("threshold discrepancies above 1e-9")
        out.rename(folder/"values.thr")
        state["status"]="complete"
    except subprocess.TimeoutExpired:
        state["status"]="timeout"
    except Exception as e:
        state.update(status="error",diagnostic=str(e))
    state["wall_s"]=time.monotonic()-start
    meta.write_text(json.dumps(state,indent=2))
    print(name,state['status'],state.get('fields',{}).get('time'),flush=True)
    return state


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name"); p.add_argument("graph",type=Path);p.add_argument("model",type=int)
    p.add_argument("method"); p.add_argument("threads",type=int);p.add_argument("--variant",default="full")
    p.add_argument("--reference",type=Path);p.add_argument("--limit",type=int,default=1800)
    p.add_argument("--binary",type=Path,default=CODE/"uthr.exe")
    a=p.parse_args()
    s=run(a.name,a.graph.resolve(),a.model,a.method,a.threads,a.variant,a.reference,a.limit,a.binary.resolve())
    raise SystemExit(0 if s['status']=='complete' else 1)
