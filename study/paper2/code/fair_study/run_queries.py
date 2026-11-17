
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
WORK=Path(os.environ.get('PAPER2_WORK', str(Path(__file__).resolve().parents[2]/'work')))
OUT=ROOT/"results/fair_study/query"
DATA=ROOT/"data/study"
STUDY=ROOT/"results/study"
CAP=ROOT.parent/"paper1/code/memcap2.exe"
QUERIES=(.5,.1,.9,.3,.7,.2,.8,.4,.6)


def run(graph,workers,rep,method):
    case=OUT/f"{graph}_{workers}_{rep}_{method}"
    meta=case/"record.json"
    if meta.exists():return json.loads(meta.read_text())
    case.mkdir(parents=True,exist_ok=True)
    g=graph.lower()
    idx=STUDY/(g+"_native_cert")/"values.thr"
    rank=DATA/(graph+".rank")
    tmp=WORK/"answers"/case.name
    tmp.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy()
    env["PATH"]=os.pathsep.join(map(str,[ROOT.parent/"paper1/tools/dl_winlibs/mingw64/bin",WORK/"deps/ucrt64/bin",env["PATH"]]))
    env["OMP_NUM_THREADS"]=str(workers)
    if method=="index":
        exe=WORK/"index_queries.exe"
        args=[exe,idx,workers,rank,tmp/"result"]
    else:
        exe=WORK/"dai_queries.exe"
        args=[exe,DATA/(graph+".bin"),workers,6 if method=="topdown" else 4,tmp/"result"]
    cmd=list(map(str,[CAP,32768,*args]))
    start=time.perf_counter()
    state=dict(graph=graph,workers=workers,rep=rep,method=method,cmd=cmd,exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest())
    with (case/"run.log").open("w") as f:
        try:p=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,env=env,timeout=300);state["exit"]=p.returncode
        except subprocess.TimeoutExpired:state["timeout"]=True
    state["process_s"]=time.perf_counter()-start
    lines=(case/"run.log").read_text(errors="replace").splitlines()
    points=[line.split() for line in lines if line.startswith("ANSWER ")]
    state["seconds"]=[float(s[3]) for s in points];state["prefix_s"]=[float(s[4]) for s in points]
    state["status"]="ok" if state.get("exit")==0 and len(points)==9 else ("timeout" if state.get("timeout") else "error")
    if state["status"]=="ok":

        order=np.fromfile(rank,"<u4")
        lower=np.zeros((9,len(order)),dtype="<i4");upper=lower.copy()
        with idx.open("rb") as f:
            import struct
            while head:=f.read(12):
                k,n=struct.unpack("<IQ",head);v=np.fromfile(f,"<f8",n)
                for i,eta in enumerate(QUERIES):
                    lower[i,:n]=np.maximum(lower[i,:n],np.where(v-1e-9>=eta,k,0))
                    upper[i,:n]=np.maximum(upper[i,:n],np.where(v+1e-9>=eta,k,0))
        state["outside_enclosure"]=[];state["ambiguous_vertices"]=[];state["answer_sha256"]=[]
        for i in range(9):
            path=tmp/f"result-{i}.bin";x=np.fromfile(path,"<i4")
            if len(x)!=len(order):raise ValueError("dense core vector size mismatch")
            ranked=x[order];state["outside_enclosure"].append(int(((ranked<lower[i])|(ranked>upper[i])).sum()))
            state["ambiguous_vertices"].append(int((lower[i]!=upper[i]).sum()))
            state["answer_sha256"].append(hashlib.sha256(path.read_bytes()).hexdigest())
        if sum(state["outside_enclosure"]):state["status"]="invalid"
    if method=="index" and state["status"]=="ok":
        bench=f"{g}_native_indexed_"+(f"t1r{rep}" if workers==1 else f"r{rep}")
        build=json.loads((STUDY/bench/"record.json").read_text())["process_wall_s"]
        t=time.perf_counter()
        regenerated=tmp/"fresh.rank"
        subprocess.run(list(map(str,[CAP,32768,ROOT/"code/export_rank.exe",DATA/(graph+".bin"),regenerated])),check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        state["rank_build_s"]=time.perf_counter()-t
        assert rank.read_bytes()==regenerated.read_bytes()
        state["full_construction_s"]=build+state["rank_build_s"]
    meta.write_text(json.dumps(state,indent=2))
    print(case.name,state["status"],round(state["process_s"],3),state.get("outside_enclosure",[]),flush=True)
    return state


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for rep in range(1,4):
        for graph in ("Flickr","SupUser"):
            for workers in (24,1):
                sequence=("index","topdown","bottomup") if rep%2 else ("bottomup","topdown","index")
                for method in sequence:run(graph,workers,rep,method)

if __name__=="__main__":main()
