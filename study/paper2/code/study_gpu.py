
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]


def run(case,graph,write=False,full=False,limit=7200,binary=None,output_directory=None):
    path=ROOT/"results/study"/case
    path.mkdir(parents=True,exist_ok=False)
    exe=binary or ROOT/"baselines/gatd_win/gatd.exe"
    args=[ROOT.parent/"paper1/code/memcap2.exe","32768",exe,graph,"0","32"]
    if write:args+=["-w"]
    env=os.environ.copy()
    env.pop("GATD_FULL_WARP",None)
    if full:env["GATD_FULL_WARP"]="1"
    record=dict(args=list(map(str,args)),full_warp=full,writer=write,status="running")
    meta=path/"record.json";meta.write_text(json.dumps(record,indent=2))
    start=time.monotonic()
    try:
        with (path/"run.log").open("w") as log:
            p=subprocess.run(args,cwd=output_directory or path,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=limit)
        p.check_returncode()
        text=(path/"run.log").read_text(errors="replace")
        m=re.search(r"Total run time is (\d+)ms",text)
        if not m or "CUDA error" in text:raise ValueError("no valid completion marker")
        record.update(status="complete",solver_seconds=int(m[1])/1000)
    except subprocess.TimeoutExpired:record.update(status="timeout")
    except Exception as e:record.update(status="error",diagnostic=str(e))
    record["wall_s"]=time.monotonic()-start
    meta.write_text(json.dumps(record,indent=2))
    print(case,record,flush=True)
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('case');p.add_argument('graph',type=Path);p.add_argument('--write',action='store_true')
    p.add_argument('--full',action='store_true');p.add_argument('--limit',type=int,default=7200)
    a=p.parse_args();r=run(a.case,a.graph.resolve(),a.write,a.full,a.limit)
    raise SystemExit(0 if r['status']=='complete' else 1)
