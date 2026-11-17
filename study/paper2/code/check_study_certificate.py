
import json
import os
from fractions import Fraction
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

CODE=Path(__file__).resolve().parent


def exhaustive(adj):
    best={}
    for mask in range(1,1<<len(adj)):
        vertices=[v for v in range(len(adj)) if mask>>v&1]
        tails=[]
        for v in vertices:
            mass=[Fraction(1)]
            for u,p in adj[v]:
                if mask>>u&1:
                    extended=[Fraction(0)]*(len(mass)+1)
                    for i,x in enumerate(mass):
                        extended[i]+=(1-p)*x;extended[i+1]+=p*x
                    mass=extended
            tails.append([sum(mass[k:]) for k in range(len(adj))])
        for k in range(1,len(vertices)):
            threshold=min(row[k] for row in tails)
            for v in vertices: best[k,v]=max(threshold,best.get((k,v),0))
    return best


def check(binary):
    adj=[[] for _ in range(7)]
    for u,v,p in [(0,1,3),(0,2,3),(0,3,3),(1,2,6),(1,3,5),(2,3,3),
                  (0,4,3),(1,4,3),(2,4,1),(4,5,7)]:
        adj[u].append((v,Fraction(p,8)));adj[v].append((u,Fraction(p,8)))
    expected=exhaustive(adj)
    with tempfile.TemporaryDirectory() as working:
        root=Path(working);graph=root/"toy.bin";value=root/"v.thr";order=root/"order.bin";rank=root/"rank"
        with graph.open("wb") as f:
            f.write(struct.pack("<iq",len(adj),sum(map(len,adj))))
            for a in adj:f.write(struct.pack("<i",len(a)))
            for a in adj:
                for v,p in sorted(a):f.write(struct.pack("<i",v))
            for a in adj:
                for v,p in sorted(a):f.write(struct.pack("<d",p))
        env=dict(os.environ,UTHR_CERT_ORDER=str(order),UTHR_COALESCE="1",UTHR_GROUP_BASE="1",UTHR_TOL="1e-12")
        subprocess.run([binary,graph,"frontier","5","1","1",value],env=env,check=True,capture_output=True)
        subprocess.run([CODE/"export_rank.exe",graph,rank],check=True)
        verts=struct.unpack("<7I",rank.read_bytes())
        checked=0;error=Fraction(0)
        raw=value.read_bytes();offset=0
        while offset<len(raw):
            k,n=struct.unpack_from("<IQ",raw,offset);offset+=12
            for i,x in enumerate(struct.unpack_from(f"<{n}d",raw,offset)):
                error=max(error,abs(Fraction(x)-expected[k,verts[i]]));checked+=1
            offset+=8*n
        assert error<=Fraction(1,10**12)
        command=[CODE/"verify_thresholds.exe",graph,value,order,"1"]
        subprocess.run(command,capture_output=True,check=True)
        x=struct.unpack_from("<d",raw,12)[0]
        value.write_bytes(raw[:12]+struct.pack("<d",1. if x<.5 else 0.)+raw[20:])
        wrong_value=subprocess.run(command,capture_output=True).returncode
        value.write_bytes(raw)
        rows=bytearray(order.read_bytes());rows[12:16]=rows[16:20];order.write_bytes(rows)
        wrong_order=subprocess.run(command,capture_output=True).returncode
        assert wrong_value==3 and wrong_order==1
        return dict(binary=Path(binary).name,subsets=2**len(adj)-1,checked=checked,
                    max_abs_exact_fraction=str(error),altered_value_exit=wrong_value,altered_order_exit=wrong_order)


if __name__=="__main__": print(json.dumps(check(Path(sys.argv[1]).resolve()),indent=2))
