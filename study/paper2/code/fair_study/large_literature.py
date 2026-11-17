
import json
import os
import struct
import subprocess
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from literature_coverage import OUT, SCRATCH, WORK, rm, ucef
from run_extension import environment

def download(url,dest):
    if dest.exists():
        with zipfile.ZipFile(dest) as z: assert 'edges.csv' in z.namelist()
        return
    tmp=dest.with_suffix('.partial')

    with requests.get(url,headers={'Range':'bytes=0-0'},stream=True,timeout=(20,90)) as probe:
        probe.raise_for_status()
        total=int(probe.headers['Content-Range'].split('/')[-1]) if probe.status_code==206 else int(probe.headers['Content-Length'])
    block=16*1024**2
    start=tmp.stat().st_size if tmp.exists() else 0
    if start>total:raise ValueError('oversize partial file')
    while start<total:
        end=min(total,start+block)-1
        for attempt in range(4):
            try:
                with requests.get(url+'?offset='+str(start),headers={'Range':f'bytes={start}-{end}'},timeout=(25,150),stream=True) as response:
                    response.raise_for_status()
                    if response.status_code!=206 or response.headers.get('Content-Range')!=f'bytes {start}-{end}/{total}':
                        raise IOError('server returned a different range')
                    content=response.content
                    if len(content)!=end-start+1:raise IOError('short range')
                break
            except (OSError,requests.RequestException):
                if attempt==3:raise
        with tmp.open('ab') as file:file.write(content)
        start=end+1
        if start% (256*1024**2)==0:print('source download',start,'/',total,flush=True)
    with zipfile.ZipFile(tmp) as z: assert 'edges.csv' in z.namelist()
    tmp.replace(dest)

def event_input(graph,n_declared,observations,archive,url):
    folder=SCRATCH/graph;folder.mkdir(exist_ok=True)
    path=folder/(graph+'.bin');meta=OUT/(graph+'_input.json')
    if meta.exists():return path,json.loads(meta.read_text())
    download(url,archive)
    keys=np.empty(observations,dtype=np.uint64)
    rows=accepted=0
    with zipfile.ZipFile(archive) as z,z.open('edges.csv') as f:
        for frame in pd.read_csv(f,comment='#',header=None,usecols=[0,1,2],dtype=np.int64,chunksize=2_000_000):
            a,b,w=frame.to_numpy().T
            assert np.all(w==1) and a.min()>=0 and b.min()>=0 and max(a.max(),b.max())<n_declared
            rows+=len(a);keep=a!=b
            a=a[keep].astype(np.uint64);b=b[keep].astype(np.uint64)
            length=len(a)
            keys[accepted:accepted+length]=np.minimum(a,b)*n_declared+np.maximum(a,b);accepted+=length
    assert rows==observations
    keys=keys[:accepted];keys.sort()
    first=np.empty(accepted,dtype=bool);first[0]=True;first[1:]=keys[1:]!=keys[:-1]
    idx=np.flatnonzero(first);del first
    weight=np.diff(idx,append=accepted)
    unique=keys[idx];del keys,idx
    u=(unique//n_declared).astype('<u4');v=(unique%n_declared).astype('<u4')
    del unique
    prob=(-np.expm1(-.5*weight)).astype('<f4');del weight
    active=np.zeros(n_declared,bool);active[u]=True;active[v]=True;n=int(active.sum())
    if n!=n_declared:
        code=np.cumsum(active,dtype=np.uint32)-1;u=code[u];v=code[v];del code
    m=len(u)

    uv=np.r_[u.astype(np.uint64)*n+v,v.astype(np.uint64)*n+u]
    deg=np.bincount(u,minlength=n);deg+=np.bincount(v,minlength=n)
    perm=np.argsort(uv,kind='quicksort');del u,v
    with path.open('wb') as f:
        f.write(struct.pack('<IQ',n,2*m));deg.astype('<u4').tofile(f)
        for i in range(0,2*m,2_000_000):(uv[perm[i:i+2_000_000]]%n).astype('<u4').tofile(f)
        for i in range(0,2*m,2_000_000):prob[perm[i:i+2_000_000]%m].astype('<f8').tofile(f)
    del uv,perm
    subprocess.run([rm.CAP,'32768',rm.CODE/'export_rank.exe',path,folder/'rank',folder/'core'],check=True)
    core=np.fromfile(folder/'core','<u4')
    rec=dict(graph=graph,vertices=n,edges=m,maximum_degree=int(deg.max()),maximum_core=int(core.max()),values=int(core.sum()),raw_rows=rows,loops=rows-accepted,
             p_min=float(prob.min()),p_max=float(prob.max()),binary_sha256=rm.digest(path),source=url,input_sha256=rm.digest(archive),
             rule='remove loops and isolated vertices, deduplicate unordered pairs and set p=1-exp(-event_count/2), rounded once to binary32')
    rm.save(meta,rec);return path,rec

def large_arm(method,path,info):
    folder=OUT/'large'/method;folder.mkdir(exist_ok=True,parents=True);meta=folder/'record.json'
    if meta.exists():return json.loads(meta.read_text())
    env=environment(24);target=path.parent/(method+'.thr')
    if method=='gpu':
        exe=rm.GPU;env['GATD_SPARSE_OUTPUT']=str(target);args=[exe,path,0,32]
    elif method=='ucef':
        exe=WORK/'ucef.exe';args=[exe,path,24,target]
    else:
        exe=rm.CPU
        if method=='reference':env['UTHR_CERT_ORDER']=str(path.parent/'removals.bin')
        args=[exe,path,'frontier',5,24,1,target]
    status,t=rm.process(args,env,folder/'run.log',7200)
    result=dict(arm=method,status=status,process_wall_s=t,budget_s=7200,exe_sha256=rm.digest(exe),input_sha256=info['binary_sha256'])
    if status=='ok':
        result['output_bytes']=target.stat().st_size
        expected=info['values']*8+info['maximum_core']*12
        if expected!=result['output_bytes']:result['status']='invalid_length'
        else:
            result['output_sha256']=rm.digest(target)
            if method=='reference':
                check,elapsed=rm.process([rm.CODE/'verify_thresholds.exe',path,target,path.parent/'removals.bin',24],env,folder/'accuracy.log',7200)
                result['verification_s']=elapsed
                if check!='ok':result['status']='certificate_'+check
            else:
                ref=OUT/'large/reference/record.json'
                if json.loads(ref.read_text())['status']=='ok':
                    result.update(rm.compare(path.parent/'reference.thr',target))
                    if result['max_abs']>(1e-4 if method=='gpu' else 1e-9):result['status']='invalid'
                    if result['status']=='ok':target.unlink()
                else:result['status']='unverified'
    rm.save(meta,result);print('Deli',method,result['status'],round(t,2),flush=True)
    return result

def wiki():
    rm.OUT=OUT/'runs'
    path,info=event_input('WikiTalkFR',1420367,4641928,WORK/'wiki_fr_events.zip','https://networks.skewed.de/net/wiki_talk/files/fr.csv.zip')
    ref=rm.run_arm('WikiTalkFR',path,info,'reference',0);assert ref['status']=='ok'
    stop=set()
    for rep in range(1,6):
        methods=['cpu','gpu','ucef'];methods=methods[rep%3:]+methods[:rep%3]
        for method in methods:
            if method in stop:continue
            rec=ucef('WikiTalkFR',path,info,rep) if method=='ucef' else rm.run_arm('WikiTalkFR',path,info,method,rep)
            if rec['status']!='ok':stop.add(method)

def deli():
    path,info=event_input('Deli',38289740,301183605,WORK/'delicious_ti.zip','https://networks.skewed.de/net/delicious/files/ti.csv.zip')
    for method in ('reference','cpu','ucef','gpu'):large_arm(method,path,info)
if __name__=='__main__':
    wiki();deli()
