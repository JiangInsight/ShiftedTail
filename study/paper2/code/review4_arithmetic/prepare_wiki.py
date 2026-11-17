
import argparse
import hashlib
from pathlib import Path
import struct
import zipfile
import numpy as np
import pandas as pd

def sha(path):
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
p=argparse.ArgumentParser()
p.add_argument("archive",type=Path);p.add_argument("output",type=Path)
a=p.parse_args()
if sha(a.archive)!="ea7c61caae34a2413922c1cd7882607aae9bca47996105b38b8c9b8f5310d9b2":raise ValueError("unexpected event archive")
if a.output.exists():raise FileExistsError(a.output)
width=1420367;parts=[];rows=0
with zipfile.ZipFile(a.archive) as z,z.open("edges.csv") as f:
    for chunk in pd.read_csv(f,comment="#",header=None,usecols=[0,1,2],dtype=np.int64,chunksize=1000000):
        x,y,w=chunk.to_numpy().T;rows+=len(x)
        assert (w==1).all() and min(x.min(),y.min())>=0 and max(x.max(),y.max())<width
        keep=x!=y;x=x[keep];y=y[keep]
        parts.append(np.minimum(x,y)*width+np.maximum(x,y))
assert rows==4641928
pairs,count=np.unique(np.concatenate(parts),return_counts=True)
x,y=np.divmod(pairs,width)
ids=np.unique(np.r_[x,y]);n=len(ids)
x=np.searchsorted(ids,x);y=np.searchsorted(ids,y)
edges=np.r_[x*n+y,y*n+x];perm=np.argsort(edges)
deg=np.bincount(x,minlength=n)+np.bincount(y,minlength=n)
prob=(-np.expm1(-.5*count)).astype("<f4")
a.output.parent.mkdir(parents=True,exist_ok=True)
with a.output.open("xb") as f:
    f.write(struct.pack("<IQ",n,len(edges)));deg.astype("<u4").tofile(f)
    (edges[perm]%n).astype("<u4").tofile(f);np.tile(prob,2)[perm].astype("<f8").tofile(f)
assert sha(a.output)=="b1f0a071555ff50507b91e8f1301fbc838c25ad02310a6f9827d835dc815337a"
