
import json
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import run_matched as rm
from run_extension import environment

ROOT=rm.ROOT
WORK=rm.WORK
OUT=ROOT/'results/literature_coverage'
SCRATCH=WORK/'literature_coverage'
GRAPHS=('HepPh','CN15kProjection','Twitter','WebGoogle','CitPatents')
def canonical_graph(name,folder):
    if name in ('WebGoogle','CitPatents'):
        fname={'WebGoogle':'web-Google.bin','CitPatents':'cit-Patents.bin'}[name]
        origin=ROOT.parent/'paper1/data/bin'/fname
        with origin.open('rb') as f:
            n,m=struct.unpack('<QQ',f.read(16));off=np.fromfile(f,'<u8',n+1);adj=np.fromfile(f,'<u4',2*m)
        degree=np.diff(off).astype('<u4')
        src=np.repeat(np.arange(n,dtype=np.uint32),degree)
        keys=np.minimum(src,adj).astype(np.uint64)*n+np.maximum(src,adj)
        ordered=np.sort(keys[src<adj])
        assert len(ordered)==m and np.all(ordered[1:]>ordered[:-1])
        rng=np.random.default_rng(20261106)
        values=rng.random(m).astype('<f4')
        prob=np.empty(len(adj),dtype='<f4')
        for i in range(0,len(keys),1_000_000):
            block=keys[i:i+1_000_000];ix=np.searchsorted(ordered,block)
            assert np.array_equal(ordered[ix],block)
            prob[i:i+len(block)]=values[ix]
        return n,degree,adj,prob,dict(source='https://snap.stanford.edu/data/'+fname.replace('.bin','.html'),input_sha256=rm.digest(origin),seed=20261106,rule='Uniform weights once per unordered edge in ascending endpoint order')
    if name=='HepPh':
        archive=WORK/'hepph_events.zip'
        with zipfile.ZipFile(archive) as z,z.open('ca-cit-HepPh.edges') as f:
            arr=np.loadtxt(f,comments='%',usecols=(0,1),dtype=np.int64)
        u,v=arr.T
        source=dict(source='https://nrvis.com/download/data/dynamic/ca-cit-HepPh.zip',input_sha256=rm.digest(archive),rule='1-exp(-multiplicity/2)')
    elif name=='Twitter':
        file=rm.DATA/'twitter.txt'
        arr=np.loadtxt(file);u,v=arr[:,:2].astype(np.int64).T;p=arr[:,2]
        source=dict(source='https://github.com/fgullo/uncertaincores/blob/370b2dbcaa02a3466a2afd10e24cd52019c3edb3/data/twitter.txt',input_sha256=rm.digest(file),rule='distributed edge probability')
    else:
        files=[rm.DATA/'cn15k'/(x+'.tsv') for x in ('train','val','test')]
        arr=np.concatenate([np.loadtxt(f) for f in files]);u,v=arr[:,[0,2]].astype(np.int64).T;p=arr[:,3]
        source=dict(source='https://github.com/stasl0217/UKGE/tree/5049b84501657abc44c36dd7d2db5f8519e5ee8f/data/cn15k',input_sha256={f.name:rm.digest(f) for f in files},rule='max observed confidence over relations and directions; drop loops')
    ids=np.unique(np.r_[u,v]);n=len(ids)
    keep=u!=v
    source.update(raw_rows=len(u),loops=int((~keep).sum()))
    u=np.searchsorted(ids,u[keep]);v=np.searchsorted(ids,v[keep])
    keys=np.minimum(u,v)*n+np.maximum(u,v)
    ordered,first,count=np.unique(keys,return_index=True,return_counts=True)
    if name=='HepPh':values=-np.expm1(-.5*count)
    elif name=='Twitter':
        order=np.argsort(keys,kind='stable')
        starts=np.r_[0,np.cumsum(count)[:-1]]
        sorted_p=p[keep][order]
        values=sorted_p[np.cumsum(count)-1]
        source.update(rule='author Java loader overwrites both directions with last input probability',repeated_pairs=int((count>1).sum()),conflicting_pairs=int((np.minimum.reduceat(sorted_p,starts)!=np.maximum.reduceat(sorted_p,starts)).sum()))
    else:
        values=np.zeros(len(ordered));np.maximum.at(values,np.searchsorted(ordered,keys),p[keep])
    assert np.all((values>0)&(values<=1))
    u,v=np.divmod(ordered,n);src=np.r_[u,v];dst=np.r_[v,u];perm=np.lexsort((dst,src))
    np.save(folder/'vertex_ids.npy',ids)
    return n,np.bincount(src,minlength=n).astype('<u4'),dst[perm].astype('<u4'),np.tile(values.astype('<f4'),2)[perm],source

def prepared(name):
    folder=SCRATCH/name;folder.mkdir(parents=True,exist_ok=True)
    path=folder/(name+'.bin');meta=OUT/(name+'_input.json')
    if meta.exists():return path,json.loads(meta.read_text())
    n,degree,adj,prob,source=canonical_graph(name,folder);narcs=len(adj)
    assert narcs==int(degree.sum()) and len(prob)==narcs
    with path.open('wb') as f:
        f.write(struct.pack('<IQ',n,narcs));degree.tofile(f);adj.tofile(f)
        for i in range(0,narcs,1_000_000):prob[i:i+1_000_000].astype('<f8').tofile(f)
    rank=folder/'rank';core=folder/'core'
    subprocess.run([rm.CODE/'export_rank.exe',path,rank,core],check=True)
    c=np.fromfile(core,'<u4');assert len(c)==n
    rec=dict(graph=name,vertices=n,edges=narcs//2,maximum_degree=int(degree.max()),maximum_core=int(c.max()),values=int(c.sum()),
             p_min=float(prob.min()),p_max=float(prob.max()),binary_sha256=rm.digest(path),**source)
    rm.save(meta,rec);return path,rec

def ucef(name,path,info,rep):
    out=OUT/'runs'/f'{name}_ucef_t24_r{rep}';out.mkdir(exist_ok=True)
    record=out/'record.json'
    if record.exists():return json.loads(record.read_text())
    exe=WORK/'ucef.exe';target=path.parent/'ucef.thr'
    status,t=rm.process([exe,path,24,target],environment(24),out/'run.log',300)
    row=dict(input=name,arm='ucef',workers=24,rep=rep,status=status,process_wall_s=t,budget_s=300,input_sha256=info['binary_sha256'],exe_sha256=rm.digest(exe))
    if status=='ok':
        row.update(rm.compare(path.parent/'reference.thr',target));row['output_bytes']=target.stat().st_size
        row['output_sha256']=rm.digest(target)
        if row['max_abs']>1e-9:row['status']='invalid'
        else:target.unlink()
    rm.save(record,row);return row

def main():
    rm.OUT=OUT/'runs';rm.OUT.mkdir(exist_ok=True,parents=True)
    for graph in GRAPHS:
        path,info=prepared(graph)
        ref=rm.run_arm(graph,path,info,'reference',0)
        assert ref['status']=='ok'
        methods=[('cpu',24),('ucef',24),('gpu',24)]
        if graph in ('Twitter','CN15kProjection'):methods += [('ctd',1),('cpu',1),('opti',1)]
        failed=set()
        for rep in range(1,6):
            for arm,t in methods[rep%len(methods):]+methods[:rep%len(methods)]:
                if (arm,t) in failed:continue
                r=ucef(graph,path,info,rep) if arm=='ucef' else rm.run_arm(graph,path,info,arm,rep,t)
                if r['status']!='ok':failed.add((arm,t))
        print('finished',graph,failed,flush=True)
if __name__=='__main__':main()
