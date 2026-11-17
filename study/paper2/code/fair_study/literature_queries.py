
import json
import re
import shutil
from pathlib import Path
import subprocess
import time
import struct

import numpy as np
from literature_coverage import OUT, SCRATCH, ROOT, WORK, rm
from run_extension import environment
from run_queries import QUERIES

def enclosure(values,rank,queries=QUERIES):
    lo=np.zeros((len(queries),len(rank)),dtype=np.int32);hi=lo.copy()
    with values.open('rb') as f:
        while header:=f.read(12):
            k,n=struct.unpack('<IQ',header)
            row=np.fromfile(f,'<f8',n)
            for i,eta in enumerate(queries):
                lo[i,:n]=np.maximum(lo[i,:n],np.where(np.nextafter(row-1e-9,-np.inf)>=eta,k,0))
                hi[i,:n]=np.maximum(hi[i,:n],np.where(np.nextafter(row+1e-9,np.inf)>=eta,k,0))
    return lo,hi

def google():
    g=SCRATCH/'WebGoogle';path=g/'WebGoogle.bin';rank=np.fromfile(g/'rank','<u4')
    bounds=enclosure(g/'reference.thr',rank)
    for rep in range(1,4):
        methods=('refined','topdown','bottomup') if rep%2 else ('bottomup','topdown','refined')
        for method in methods:
            case=OUT/'queries'/f'WebGoogle_{rep}_{method}';case.mkdir(exist_ok=True,parents=True)
            record=case/'record.json'
            if record.exists():continue
            dest=g/f'query_{rep}_{method}';dest.mkdir(exist_ok=True)
            env=environment(24)
            if method=='refined':
                env['UTHR_CERT_ORDER']=str(dest/'order')
                stages=[('build',[rm.CPU,path,'frontier',5,24,1,dest/'values']),
                        ('verify',[rm.CODE/'verify_thresholds.exe',path,dest/'values',dest/'order',24]),
                        ('rank',[rm.CODE/'export_rank.exe',path,dest/'rank']),
                        ('query',[WORK/'index_refined.exe',dest/'values',24,dest/'rank',dest/'result',path])]
            else:stages=[('query',[WORK/'dai_queries.exe',path,24,6 if method=='topdown' else 4,dest/'result'])]
            rec=dict(method=method,graph='WebGoogle',rep=rep,stages={},status='ok',input_sha=rm.digest(path))
            for key,args in stages:
                status,t=rm.process(args,env,case/(key+'.log'),300);rec['stages'][key]=t
                if status!='ok':rec['status']=key+'_'+status;break
            if rec['status']=='ok':
                if method=='refined':
                    assert rm.digest(dest/'values')==rm.digest(g/'reference.thr') and rm.digest(dest/'rank')==rm.digest(g/'rank')
                lines=(case/'query.log').read_text().splitlines()
                rec['prefix']=[float(s.split()[4])+sum(v for key,v in rec['stages'].items() if key!='query') for s in lines if s.startswith('ANSWER ')]
                assert len(rec['prefix'])==9
                rec['outside_enclosure']=[]
                for i in range(9):
                    a=np.fromfile(dest/f'result-{i}.bin','<i4');assert len(a)==len(rank)
                    a=a[rank];rec['outside_enclosure'].append(int(((a<bounds[0][i])|(a>bounds[1][i])).sum()))
                if any(rec['outside_enclosure']):rec['status']='invalid'
            rm.save(record,rec);print(case.name,rec['status'],flush=True)
        if all(json.loads((OUT/'queries'/f'WebGoogle_{rep}_{m}'/'record.json').read_text())['status']=='ok' for m in methods):
            counts={m:[] for m in ('topdown','bottomup')}
            for i in range(9):
                truth=np.fromfile(g/f'query_{rep}_refined'/f'result-{i}.bin','<i4')
                for m in counts:
                    actual=np.fromfile(g/f'query_{rep}_{m}'/f'result-{i}.bin','<i4')
                    counts[m].append(int((truth!=actual).sum()))
            rm.save(OUT/'queries'/f'WebGoogle_{rep}_disagreement.json',counts)

def bonchi():
    base=WORK/'bonchi_public'
    work=SCRATCH/'bonchi';work.mkdir(exist_ok=True)
    result=OUT/'kdd';result.mkdir(exist_ok=True)
    inputfile=base/'data/Flickr.txt'
    assert rm.digest(inputfile)==rm.digest(rm.DATA/'Flickr.txt')
    shutil.copyfile(inputfile,work/'Flickr.txt')
    shutil.copytree(base/'data/beta_function_values',work/'beta_function_values',dirs_exist_ok=True)
    stem='KEtaCores_DynamicProgramming_BigDecimals_IncrementalInitialEtaDegrees'
    java=shutil.which('java');javac=shutil.which('javac')
    subprocess.run([javac,'-d',str(work),str(base/(stem+'.java')),str(base/(stem+'_LB.java')),str(Path(__file__).with_name('BonchiBoundOutput.java'))],check=True)
    ids=np.load(rm.DATA/'Flickr.vertex_ids.npy')
    truth=np.fromfile(WORK/'refined/Flickr_t1_r1_refined/result-0.bin','<i4')
    rank=np.fromfile(rm.DATA/'Flickr.rank','<u4');lo,hi=enclosure(ROOT/'results/study/flickr_native_cert/values.thr',rank)
    capped=set()
    for rep in range(1,4):
        for suffix in (('', '_LB') if rep%2 else ('_LB','')):
            method='LB' if suffix else 'DP';recpath=result/f'{method}_{rep}.json'
            if recpath.exists():
                if json.loads(recpath.read_text())['status']!='ok':capped.add(method)
                continue
            if method in capped:continue
            log=result/f'{method}_{rep}.log'
            files=lambda:set((work/'output').glob('*coreNumbers*'))
            before=files();start=time.perf_counter()
            args=[rm.CAP,32768,java,'-Xmx16g','-XX:ActiveProcessorCount=1','-cp',work,('BonchiBoundOutput' if suffix else stem),'Flickr.txt','0.5','1']
            with log.open('w') as f:
                try:
                    rc=subprocess.run(list(map(str,args)),cwd=work,stdout=f,stderr=subprocess.STDOUT,timeout=300).returncode
                    status='ok' if rc==0 else 'error'
                except subprocess.TimeoutExpired:status='timeout'
            rec=dict(graph='Flickr',method=method,rep=rep,eta=.5,wall_s=time.perf_counter()-start,status=status,budget_s=300,
                     input_sha256=rm.digest(inputfile),author_source_sha256=rm.digest(base/(stem+suffix+'.java')))
            if status=='ok':
                new=files()-before;assert len(new)==1
                answer_file=new.pop()
                data=np.loadtxt(answer_file,dtype=np.int64);ordered=data[np.argsort(data[:,0])]
                assert np.array_equal(ordered[:,0],ids)
                a=ordered[:,1]
                rec.update(values=len(a),answer_sha256=rm.digest(answer_file),disagree_with_inclusive=int((a!=truth).sum()),
                           outside_enclosure=int(((a[rank]<lo[0])|(a[rank]>hi[0])).sum()))
                if rec['outside_enclosure']:rec['status']='invalid'
            if rec['status']!='ok':capped.add(method)
            rm.save(recpath,rec);print('KDD',method,rep,rec['status'],flush=True)

if __name__=='__main__':
    google();bonchi()
