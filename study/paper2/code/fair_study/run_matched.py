
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
CODE=ROOT/"code"
WORK=Path(os.environ.get('PAPER2_WORK', str(Path(__file__).resolve().parents[2]/'work')))
ART=WORK/"matched"
OUT=ROOT/"results/fair_study/matched"
DATA=ROOT/"data/study"
CAP=ROOT.parent/"paper1/code/memcap2.exe"
GPU=ROOT/"baselines/gatd_win_matched/gatd.exe"
CPU=CODE/"uthr_native.exe"
SEEDS=(11,23,47)
FULL=("Flickr","SupUser","DBLP","BiomineDSAA","Stack","Orkut")


def digest(p):
    with p.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()


def save(path,record):
    path.write_text(json.dumps(record,indent=2))


def read_graph(path):
    with path.open("rb") as f:
        n,arcs=struct.unpack("<iq",f.read(12))
        degree=np.fromfile(f,"<i4",n)
        ids=np.fromfile(f,"<i4",arcs)
        values=np.fromfile(f,"<f8",arcs)
    src=np.repeat(np.arange(n,dtype=np.int32),degree);keep=src<ids
    return n,src[keep],ids[keep],values[keep]


def derived(tag,graph,kind,seed=0,frac=100):
    folder=ART/tag;folder.mkdir(parents=True,exist_ok=True)
    path=folder/(graph+".bin");meta=folder/"input.json";source=DATA/(graph+".bin")
    if meta.exists():return path,json.loads(meta.read_text())
    if kind=="full":
        shutil.copyfile(source,path)
        with path.open("rb") as f:n,arcs=struct.unpack("<iq",f.read(12))
        prob=np.memmap(path,dtype="<f8",mode="r+",offset=12+4*n+4*arcs,shape=(arcs,))
        low=1.;high=0.
        for i in range(0,arcs,1000000):
            chunk=prob[i:i+1000000];chunk[:]=chunk.astype("<f4")
            low=min(low,float(chunk.min()));high=max(high,float(chunk.max()))
        prob.flush();del prob
    else:
        n,u,v,p=read_graph(source);rng=np.random.default_rng(seed)
        if kind=="scale":
            selection=np.sort(rng.permutation(n)[:n*frac//100]);mapping=np.full(n,-1,np.int32)
            mapping[selection]=np.arange(len(selection));mask=(mapping[u]>=0)&(mapping[v]>=0)
            u=mapping[u[mask]];v=mapping[v[mask]];p=p[mask];n=len(selection)
        elif kind=="constant":p=np.full_like(p,float(np.mean(p)))
        elif kind=="narrow":p=p.mean()+.01*(p-p.mean())
        elif kind=="shuffled":p=rng.permutation(p)
        elif kind=="uniform":p=rng.uniform(.000001,.999999,len(p))
        else:raise ValueError(kind)
        p=p.astype("<f4").astype("<f8")
        low,high=float(p.min()),float(p.max())
        src=np.r_[u,v];dst=np.r_[v,u];order=np.lexsort((dst,src));arcs=len(src)
        with path.open("wb") as f:
            f.write(struct.pack("<iq",n,arcs))
            np.bincount(src,minlength=n).astype("<i4").tofile(f)
            dst[order].astype("<i4").tofile(f);np.tile(p,2)[order].tofile(f)
    record=dict(tag=tag,graph=graph,kind=kind,seed=seed,percent=frac,n=int(n),edges=arcs//2,
                p_min=low,p_max=high,binary_sha256=digest(path),probability="binary32 values stored exactly as binary64")
    save(meta,record)
    return path,record


def process(args,env,log,limit):
    start=time.perf_counter()
    with log.open("w") as f:
        try:
            proc=subprocess.run(list(map(str,[CAP,32768,*args])),env=env,stdout=f,stderr=subprocess.STDOUT,timeout=limit)
            status="ok" if proc.returncode==0 else "error"
        except subprocess.TimeoutExpired:status="timeout"
    return status,time.perf_counter()-start


def compare(ref,out):
    sum_abs=0.;max_err=0.;n=0;exact=0;above=0;six=0
    if ref.stat().st_size!=out.stat().st_size:raise ValueError("different materialized file lengths")
    with ref.open("rb") as a,out.open("rb") as b:
        while head:=a.read(12):
            if b.read(12)!=head:raise ValueError("inconsistent rank/layer header")
            k,count=struct.unpack("<IQ",head)
            x=np.fromfile(a,"<f8",count);y=np.fromfile(b,"<f8",count);d=np.abs(x-y)
            if len(d)!=count or not np.isfinite(d).all():raise ValueError("invalid numeric data")
            n+=count;max_err=max(max_err,float(d.max()));sum_abs+=float(d.sum())
            exact+=int((np.rint(x*1e6)==np.rint(y*1e6)).sum());above+=int((d>1e-5).sum());six+=int((d>1e-6).sum())
        if b.read(1):raise ValueError("unexpected trailing data")
    return dict(values=n,max_abs=max_err,mae=sum_abs/n,match6=exact/n,above_1e5=above,above_1e6=six)


def run_arm(tag,path,inp,arm,rep,workers=24):
    name=f"{tag}_{arm}_t{workers}_r{rep}";folder=OUT/name;folder.mkdir(parents=True,exist_ok=True)
    meta=folder/"record.json"
    if meta.exists():return json.loads(meta.read_text())
    ref=path.parent/"reference.thr"
    env={k:v for k,v in os.environ.items() if not k.startswith(("UTHR_","GATD_","OMP_","MEMCAP_"))}
    env.update(OMP_NUM_THREADS=str(workers),UTHR_TOL="1e-12")
    output=path.parent/(name+".thr");method="frontier"
    if arm=="gpu":
        exe=GPU;env["GATD_SPARSE_OUTPUT"]=str(output);args=[exe,path,0,32]
    else:
        exe=CODE/"opti_native.exe" if arm=="opti" else CPU
        method={"opti":"opti","ctd":"ctd"}.get(arm,"frontier")
        env.update(UTHR_COALESCE="1",UTHR_GROUP_BASE="1",UTHR_INDEXED="1")
        if arm=="general":env["UTHR_NOHOMOGENEOUS"]="1"
        if arm=="reference" and inp["p_min"]!=inp["p_max"]:env["UTHR_CERT_ORDER"]=str(path.parent/"removals.bin")
        args=[exe,path,method,5,workers,1,output]
    limit=1800 if inp["graph"] in ("Stack","Orkut","BiomineDSAA") else 300
    status,elapsed=process(args,env,folder/"run.log",limit)
    rec=dict(input=tag,arm=arm,rep=rep,workers=workers,status=status,process_wall_s=elapsed,budget_s=limit,
             exe_sha256=digest(exe),input_sha256=inp["binary_sha256"])
    if status=="ok":
        raw=(folder/"run.log").read_text(errors="replace")
        m=re.search(r"peak_mb=(\d+)",raw);rec["host_peak_mib"]=int(m[1]) if m else None
        if arm!="gpu":
            final=re.search(r"^result (.+)",raw,re.M)
            if not final or "ERROR level" in raw:raise ValueError(name+" invalid CPU completion")
            rec["fields"]=dict(item.split("=",1) for item in final[1].split())
            rec["solver_s"]=float(rec["fields"]["time"].rstrip("s"))
        else:
            m=re.search(r"Total run time is (\d+)ms",raw)
            if not m or "CUDA error" in raw:raise ValueError(name+" invalid GPU completion")
            rec["solver_s"]=int(m[1])*.001
        rec["output_bytes"]=output.stat().st_size
        rec["output_sha256"]=digest(output)
        if arm=="reference":
            output.replace(ref)
            if inp["p_min"]==inp["p_max"]:
                rank=path.parent/"rank";core=path.parent/"core"
                subprocess.run([str(CODE/"export_rank.exe"),str(path),str(rank),str(core)],check=True)
                cmd=[sys.executable,"-I",CODE/"check_uniform.py",path,ref,core]
            else:cmd=[CODE/"verify_thresholds.exe",path,ref,path.parent/"removals.bin","24"]
            checked,_=process(cmd,env,folder/"accuracy.log",7200)
            if checked!="ok":rec["status"]="certificate_failure"
            elif inp["p_min"]==inp["p_max"] and not json.loads((folder/"accuracy.log").read_text().split("memcap:")[0])["within_1e9"]:
                rec["status"]="certificate_failure"
        else:
            rec.update(compare(ref,output))
            if rec["max_abs"]>(1e-4 if arm=="gpu" else 1e-9):rec["status"]="invalid"
            if rec["status"]=="ok":output.unlink()
    save(meta,rec)
    print(name,rec["status"],round(elapsed,3),flush=True)
    if arm=="reference" and rec["status"]!="ok":raise RuntimeError(name+" incomplete reference")
    return rec


def experiment(tag,graph,kind,seed=0,frac=100):
    path,inp=derived(tag,graph,kind,seed,frac)
    reference=run_arm(tag,path,inp,"reference",0)
    if reference['status']!='ok':raise RuntimeError(tag+' has an incomplete cached reference')
    for rep in range(1,4):
        for arm in (("cpu","gpu") if rep%2 else ("gpu","cpu")):
            run_arm(tag,path,inp,arm,rep)
    if kind=="constant":
        for rep in range(1,4):run_arm(tag,path,inp,"general",rep)
    if kind=="full" and graph in ("Flickr","SupUser"):
        for rep in range(1,4):
            for arm,workers in ((("cpu",1),("ctd",1),("opti",1),("ctd",24)) if rep%2 else (("ctd",24),("opti",1),("ctd",1),("cpu",1))):
                run_arm(tag,path,inp,arm,rep,workers)


def main():
    OUT.mkdir(parents=True,exist_ok=True); ART.mkdir(parents=True,exist_ok=True)
    for g in FULL[:2]:experiment(g.lower()+"_full",g,"full")
    for seed in SEEDS:
        for percent in (20,40,60,80):
            for g in FULL[:2]:
                experiment(f"{g.lower()}_n{percent}_s{seed}",g,"scale",seed,percent)
    for kind in ("constant","narrow"):experiment("flickr_"+kind,"Flickr",kind)
    for seed in SEEDS:
        for kind in ("shuffled","uniform"):experiment(f"flickr_{kind}_s{seed}","Flickr",kind,seed)
    for g in FULL[2:]:experiment(g.lower()+"_full",g,"full")

if __name__=="__main__":main()
