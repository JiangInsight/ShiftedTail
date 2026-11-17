
import math
import struct
from fractions import Fraction
from pathlib import Path
import json
import sys
import numpy as np

graph,values,corefile=map(Path,sys.argv[1:4])
with graph.open("rb") as f:
    n,arcs=struct.unpack("<iq",f.read(12));f.seek(12+4*(n+arcs))
    p=None
    for start in range(0,arcs,1_000_000):
        arr=np.fromfile(f,"<f8",min(1_000_000,arcs-start))
        if p is None:p=float(arr[0])
        assert np.all(arr==p) and 0<=p<=1
A,B=p.as_integer_ratio()
cores=np.fromfile(corefile,'<u4');assert len(cores)==n and np.all(cores[:-1]>=cores[1:])
counts=np.bincount(cores.astype('int64'));ends=np.cumsum(counts[::-1])[::-1]
tails={};kmax=int(cores[0])
for c in range(1,kmax+1):
    if not counts[c]:continue
    mass=0;den=B**c
    for k in range(c,0,-1):
        mass+=math.comb(c,k)*A**k*(B-A)**(c-k)
        tails[c,k]=Fraction(mass,den)
worst=Fraction(0);checked=0
with values.open('rb') as f:
    for k in range(kmax,0,-1):
        level,cnt=struct.unpack('<IQ',f.read(12));assert level==k and cnt==ends[k]
        row=np.fromfile(f,'<f8',cnt);assert len(row)==cnt and np.isfinite(row).all()
        for c in range(k,kmax+1):
            if not counts[c]:continue
            part=row[ends[c]-counts[c]:ends[c]];ref=tails[c,k]
            for x in [part.min(),part.max()]:worst=max(worst,abs(Fraction.from_float(float(x))-ref))
        checked+=cnt
    assert not f.read(1)
print(json.dumps(dict(binary_p=p,values=checked,levels=kmax,
                      max_abs_upper=math.nextafter(float(worst),math.inf),
                      within_1e9=bool(worst<=Fraction(1,10**9))),indent=2))
