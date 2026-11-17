
import argparse
from array import array
from collections import deque
import csv
from functools import lru_cache
from fractions import Fraction
import hashlib
from itertools import combinations
import json
import math
import os
from pathlib import Path
import random
import re
import struct
import subprocess
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/"results/review4_arithmetic"
SUP=ROOT/"paper/supplement/review4/arithmetic"
GCC=Path(os.environ.get("CXX",ROOT.parent/"paper1/tools/dl_winlibs/mingw64/bin/g++.exe"))
GMP=Path(os.environ.get("GMP_ROOT","C:/vldb_paper2_fair/deps/ucrt64"))
WIKI=Path(os.environ.get("WIKI_CASE","C:/vldb_paper2_fair/literature_coverage/WikiTalkFR"))
ENV=dict(os.environ,PATH=str(GCC.parent)+os.pathsep+str(GMP/"bin")+os.pathsep+os.environ["PATH"],
         OMP_NUM_THREADS="1",UCORE_WITNESS_STATS="1")
SEP=math.nextafter(0.,1.)
EPS=2.**-52

def js(name,x): (SUP/name).write_text(json.dumps(x,indent=2)+"\n",encoding="utf-8")
def table(name,rows):
    with (SUP/name).open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
def digest(path):
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def call(args,**kwargs):
    return subprocess.run(list(map(str,args)),env=ENV,capture_output=True,text=True,**kwargs)
def build(only=None):
    record=SUP/"build.json"
    out=[row for row in json.loads(record.read_text())["executables"] if row["name"]!=only] if only else []
    for tag,src,extra in [("fma",ROOT/"code/verify_thresholds.cpp",["-mfma"]),("portable",ROOT/"code/verify_thresholds.cpp",["-mno-fma","-DUCORE_NO_FMA"]),
                          ("pfma",HERE/"endpoint_probe.cpp",["-mfma"]),("pportable",HERE/"endpoint_probe.cpp",["-mno-fma","-DUCORE_NO_FMA"]),
                          ("boundary",HERE/"boundary_probe.cpp",["-mno-fma","-DUCORE_BOUNDARY_STATS","-I"+str(GMP/"include"),"-L"+str(GMP/"lib")])]:
        if only and only!=tag:continue
        args=[GCC,"-O2","-std=c++17","-fopenmp","-fno-fast-math","-frounding-math","-ffp-contract=off",*extra,src,"-o",OUT/(tag+".exe")]
        if tag=="boundary":args+=["-lgmpxx","-lgmp"]
        z=call(args)
        if z.returncode:raise RuntimeError(z.stderr)
        out.append(dict(name=tag,args=list(map(str,args)),binary_sha256=digest(OUT/(tag+".exe"))))
    js("build.json",dict(compiler=call([GCC,"--version"],check=True).stdout,executables=out))
    for name in ("pfma","pportable"):
        for invalid in ("wrong-round","flush-zero","denormals-zero"):
            assert call([OUT/(name+".exe"),invalid]).returncode==4


@lru_cache(maxsize=20000)
def truth(k,probs):
    if len(probs)<k:return Fraction(0)
    a=[1];den=1
    for p in probs:
        x,q=p.as_integer_ratio();den*=q;y=q-x
        a=[a[0]*y,*[a[i]*y+a[i-1]*x for i in range(1,len(a))],a[-1]*x]
    return Fraction(sum(a[k:]),den)

def recompile_boundary():
    build("boundary")

def endpoint():
    tau=1e-15
    T=[0.,SEP,2*SEP,2.**-1022,math.nextafter(tau,0.),tau,math.nextafter(tau,1.),2.**-52,
       math.nextafter(.5,0.),.5,math.nextafter(.5,1.),math.nextafter(1.-tau,0.),1.-tau,math.nextafter(1.-tau,1.),math.nextafter(1.,0.),1.]
    cases=[(1,[p]) for p in T]
    cases += [(k,list(p)) for p in [(0.,1.),(SEP,1.),(tau,tau,1.-tau),(.5,1.,1.,0.),(.5,)*9,(SEP,)*12,(1.-tau,)*24,
                      tuple(math.nextafter(.5,1.) if i%2 else math.nextafter(.5,0.) for i in range(64))]
                 for k in range(1,len(p)+2)]
    rng=random.Random(7112026)
    for _ in range(350):
        n=rng.randrange(1,24);cases.append((rng.randint(1,n+1),[rng.choice(T) if rng.random()<.7 else rng.random() for i in range(n)]))
    stream="".join(f"{k} {len(p)} "+" ".join(x.hex() for x in p)+"\n" for k,p in cases)
    rows=[]
    for backend in ["fma","portable"]:
        z=call([OUT/("p"+backend+".exe")],input=stream,check=True)
        lines=z.stdout.splitlines()
        assert len(lines)==len(cases)
        for i,((k,p),line) in enumerate(zip(cases,lines)):
            lo,hi,n,c=line.split();val=truth(k,tuple(p))
            assert Fraction(float(lo))<=val<=Fraction(float(hi)),(backend,i,line)
            rows.append(dict(backend=backend,case=i,k=k,n=len(p),lo=lo,hi=hi,factors=n,cells=c,
                             exact_num_bits=val.numerator.bit_length(),exact_denom_bits=val.denominator.bit_length()))
    table("endpoint_cases.csv",rows)
    js("endpoint_summary.json",dict(seed=7112026,cases_per_kernel=len(cases),oracle="full integer coefficient convolution",exact_enclosures=len(rows),
                        max_exact_denom_bits=max(r['exact_denom_bits'] for r in rows)))

def csr(path,adj):
    n=len(adj);degrees=list(map(len,adj))
    with path.open("wb") as f:
        f.write(struct.pack("<IQ",n,sum(degrees)));f.write(struct.pack(f"<{n}I",*degrees))
        for nb in adj:f.write(struct.pack(f"<{len(nb)}I",*(u for u,p in nb)))
        for nb in adj:f.write(struct.pack(f"<{len(nb)}d",*(p for u,p in nb)))

def study(name,n,k,edges,requests,rows):
    adj=[[] for _ in range(n)]
    for a,b,p in edges:adj[a].append((b,p));adj[b].append((a,p))
    for nb in adj:nb.sort()
    path=OUT/(name+".bin");csr(path,adj)
    z=call([OUT/"boundary.exe",path,n,k,*[x.hex() for x in requests]],check=True)
    (SUP/(name+".log")).write_text(z.stdout)
    for eta,line in zip(requests,z.stdout.splitlines(),strict=True):

        live=set(range(n))
        while True:
            reject={v for v in live if truth(k,tuple(sorted(p for u,p in adj[v] if u in live)))<Fraction(eta)}
            if not reject:break
            live-=reject
        d=dict(re.findall(r"(\w+)=([^ ]+)",line));assert int(d["retained"])==len(live)
        assert int(d["min_answer"])==(k if len(live)==n else k-1) and int(d["max_answer"])==(k-1 if not live else k)
        h=14695981039346656037
        for v in range(n):
            for byte in struct.pack("<I", k if v in live else k-1): h=((h^byte)*1099511628211)&(2**64-1)
        assert int(d["answer_hash"])==h
        exact_answers=b"".join(struct.pack("<i",k if v in live else k-1) for v in range(n))
        assert Path(str(path)+".q"+d["id"]+".answers").read_bytes()==exact_answers
        rows.append(dict(graph=name,k=k,n=n,**d))
def boundary():
    rows=[]
    n=8192
    study("constant_pairs",n,1,((v,v+1,.5) for v in range(0,n,2)),[.5,math.nextafter(.5,1.),math.nextafter(.5,0.)],rows)
    study("zero_one_pairs",64,1,((v,v+1,float(v%4==0)) for v in range(0,64,2)),[1.,math.nextafter(1.,0.),SEP],rows)
    study("subnormal_pairs",128,1,((v,v+1,SEP) for v in range(0,128,2)),[SEP,2*SEP],rows)
    n=64;prob=[]
    for i in range(15):
        x=(2**51+1+2*i)/2**53;prob.extend([x,1.-x])
    prob.extend([.5,.5])
    study("long_denominator",n,32,((i,j,prob[min(j-i,n-j+i)-1]) for i,j in combinations(range(n),2)),
          [.5,math.nextafter(.5,1.),math.nextafter(.5,0.)],rows)
    n=256
    study("revisit_cycle",n,2,((v,(v+1)%n,math.nextafter(.5,0.) if v==n-2 else .5) for v in range(n)),
          [.25,math.nextafter(.25,0.),math.nextafter(.25,1.)],rows)
    assert int(rows[-3]["revisits"])>0
    table("boundary_cases.csv",rows)

def check(tag,graph,files,wanted,rows):
    paths=[graph,*files]
    for mode in ("fma","portable"):
        t=time.monotonic();z=call([OUT/(mode+".exe"),*paths,1]);seconds=time.monotonic()-t
        (SUP/(tag+"_"+mode+".log")).write_text(z.stdout+z.stderr)
        if z.returncode!=wanted[mode]:raise RuntimeError((tag,mode,z.returncode,z.stderr,z.stdout[-300:]))
        for line in z.stdout.splitlines():
            if not line.startswith("witness "):continue
            fields=dict(re.findall(r"(\w+)=([^ ]+)",line));summary=dict(re.findall(r"(\w+)=([^ ]+)",z.stdout.splitlines()[-1]))
            rows.append(dict(case=tag,backend=mode,status=z.returncode,elapsed_s=seconds,**fields,**summary))
def star(tag,prob,rows):
    n=280001;graph=OUT/(tag+".bin");v=OUT/(tag+".thr");o=OUT/(tag+".ord")

    with graph.open("wb") as f:
        f.write(struct.pack("<IQI",n,2*(n-1),n-1));f.write(struct.pack("<I",1)*(n-1))
        f.write(struct.pack(f"<{n-1}I",*range(1,n))+bytes(4*(n-1))+struct.pack("<d",prob)*(2*(n-1)))
    v.write_bytes(struct.pack("<IQ",1,n)+struct.pack("<d",prob)*n);o.write_bytes(struct.pack("<IQ",1,n)+struct.pack(f"<{n}I",*range(n)))
    check(tag,graph,[v,o],dict(fma=3,portable=0),rows)

def stars():
    with (SUP/"witness_stats.csv").open() as f: rows=[r for r in csv.DictReader(f) if r["case"]=="wiki"]
    star("zero_star",0.,rows);star("positive_star",2.**-60,rows)
    table("witness_stats.csv",rows)

def wiki_dimensions():
    graph=WIKI/"WikiTalkFR.bin"
    with graph.open("rb") as f:
        n,arcs=struct.unpack("<IQ",f.read(12))
        degrees=array("I");degrees.fromfile(f,n);peak=max(degrees)
    js("wiki_dimensions.json",dict(vertices=n,arcs=arcs,edges=arcs//2,max_original_degree=peak,one_maximizer=degrees.index(peak)))

def wiki():
    wiki_dimensions()
    rows=[];paths=[WIKI/f for f in ["WikiTalkFR.bin","reference.thr","removals.bin"]]
    check("wiki",paths[0],paths[1:],dict(fma=0,portable=0),rows)
    table("witness_stats.csv",rows)
    js("wiki_inputs.json",{p.name:dict(bytes=p.stat().st_size,sha256=digest(p)) for p in paths})
    stars()

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("tasks",nargs="+",choices=["build","recompile_boundary","endpoint","boundary","wiki","stars"])
    OUT.mkdir(exist_ok=True,parents=True);SUP.mkdir(exist_ok=True,parents=True)
    for task in ap.parse_args().tasks:globals()[task]()
