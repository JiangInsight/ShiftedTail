
from pathlib import Path
import struct
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"data/study"


def write(path, degree, adj, probability):
    if degree.max() > 2**31-1 or len(adj)>2**31-1:
        raise ValueError("Gatd uses signed 32-bit graph offsets")
    with path.open("wb") as f:
        f.write(struct.pack("<iq",len(degree),len(adj)))
        np.asarray(degree,"<i4").tofile(f); np.asarray(adj,"<i4").tofile(f)
        np.asarray(probability,"<f8").tofile(f)


def convert_text(name):
    edges=np.loadtxt(OUT/(name+".txt"),ndmin=2)
    a,b=edges[:,:2].astype(np.int64).T
    if np.any(a==b) or not np.all((edges[:,2]>0)&(edges[:,2]<=1)):
        raise ValueError("self loops or invalid probabilities")
    ids,code=np.unique(np.r_[a,b],return_inverse=True);n=len(ids);u,v=np.split(code,2)
    x=np.minimum(u,v); y=np.maximum(u,v); keys=x.astype(np.int64)*n+y
    if len(np.unique(keys))!=len(keys):raise ValueError("duplicated undirected pairs")
    src=np.r_[u,v]; dst=np.r_[v,u];order=np.lexsort((dst,src)); d=np.bincount(src,minlength=n)
    write(OUT/(name+".bin"),d,dst[order],np.tile(edges[:,2],2)[order])
    np.save(OUT/(name+".vertex_ids.npy"),ids)
    print(name,n,len(x),int(d.max()),flush=True)


def convert_csr(name, path, weighted):
    with path.open("rb") as f:
        n,m=struct.unpack("<QQ",f.read(16));off=np.fromfile(f,"<u8",n+1);adj=np.fromfile(f,"<u4",2*m)
        with (OUT/(name+".bin")).open("wb") as target:
            target.write(struct.pack("<iq",n,2*m));np.diff(off).astype("<i4").tofile(target)
            adj.tofile(target)
            for start in range(0,2*m,1_000_000):
                count=min(1_000_000,2*m-start)
                w=np.fromfile(f,"<u4",count) if weighted else np.ones(count)
                (-np.expm1(-.5*w)).astype("<f8").tofile(target)
    print(name,n,m,flush=True)


def convert_events(name, path):
    edge=np.loadtxt(path,usecols=(0,1),dtype=np.int64,ndmin=2)
    edge=edge[edge[:,0]!=edge[:,1]]
    ids,idx=np.unique(edge.reshape(-1),return_inverse=True)
    pairs=np.sort(idx.reshape(-1,2),axis=1)
    n=len(ids)
    keys,weight=np.unique(pairs[:,0]*n+pairs[:,1],return_counts=True)
    a,b=np.divmod(keys,n)
    src=np.r_[a,b];dst=np.r_[b,a];order=np.lexsort((dst,src))
    p=-np.expm1(-.5*weight)
    write(OUT/(name+".bin"),np.bincount(src,minlength=n),dst[order],np.tile(p,2)[order])
    np.save(OUT/(name+".vertex_ids.npy"),ids)
    print(name,n,len(keys),flush=True)


if __name__=="__main__":
    convert_text("Flickr")
    convert_events("SupUser",OUT/"sx-superuser.txt.gz")
    convert_csr("Stack",ROOT/"results/stack.wbin",True)
    convert_csr("Orkut",ROOT.parent/"paper1/data/bin/com-orkut.bin",False)
