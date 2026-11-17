
import json
import os
import time
from pathlib import Path

import numpy as np
from run_matched import ART, CAP, CODE, DATA, ROOT, WORK, compare, digest, process, save
from run_queries import OUT as DIRECT, QUERIES
OUT = ROOT/'results/fair_study/extension'


def environment(workers):
    env = {k:v for k,v in os.environ.items() if not k.startswith(('UTHR_', 'GATD_', 'OMP_', 'MEMCAP_'))}
    env.update(OMP_NUM_THREADS=str(workers), UTHR_TOL='1e-12', UTHR_GROUP_BASE='1', UTHR_INDEXED='1', UTHR_COALESCE='1')
    env['PATH'] = os.pathsep.join(map(str,[ROOT.parent/'paper1/tools/dl_winlibs/mingw64/bin',WORK/'deps/ucrt64/bin',env['PATH']]))
    return env


def refined(graph,workers,rep):
    label=f'{graph}_t{workers}_r{rep}_refined'
    folder=OUT/label
    folder.mkdir(exist_ok=True)
    if (folder/'record.json').exists(): return
    work=WORK/'refined'/label
    work.mkdir(parents=True,exist_ok=True)
    path=DATA/(graph+'.bin')
    values=work/'values.thr'
    rank=work/'rank'
    removals=work/'removals'
    env=environment(workers)
    env['UTHR_CERT_ORDER']=str(removals)
    stages=[
        ('build',[CODE/'uthr_native.exe',path,'frontier',5,workers,1,values]),
        ('verify',[CODE/'verify_thresholds.exe',path,values,removals,workers]),
        ('rank',[CODE/'export_rank.exe',path,rank]),
        ('query',[WORK/'index_refined.exe',values,workers,rank,work/'result',path])]
    result=dict(graph=graph,workers=workers,rep=rep,method='refined',stages={},status='ok')
    for stage,args in stages:
        code,elapsed=process(args,env,folder/(stage+'.log'),300)
        result['stages'][stage]=elapsed
        if code!='ok':
            result['status']=stage+'_'+code
            save(folder/'record.json',result)
            raise RuntimeError(label+' '+result['status'])
    log=(folder/'query.log').read_text().splitlines()
    result['prefix_s']=[float(line.split()[4]) for line in log if line.startswith('ANSWER ')]
    result['refinements']=[list(map(int,line.split()[2:])) for line in log if line.startswith('REFINE ')]
    assert len(result['prefix_s'])==len(result['refinements'])==len(QUERIES)
    result['build_s']=sum(result['stages'][k] for k in ('build','verify','rank'))
    result['answer_sha256']=[]
    result['disagreements']={m:[] for m in ('topdown','bottomup','index')}
    assert json.loads((DIRECT/f'{graph}_{workers}_{rep}_index'/'record.json').read_text())['status']=='ok'
    assert digest(rank)==digest(DATA/(graph+'.rank'))
    assert digest(values)==digest(ROOT/'results/study'/(graph.lower()+'_native_cert')/'values.thr')
    for i in range(len(QUERIES)):
        file=work/f'result-{i}.bin'
        answer=np.fromfile(file,'<i4')
        assert file.stat().st_size==rank.stat().st_size
        if graph=='Flickr' and i==0:
            assert answer[1986]==answer[1987]==1
        result['answer_sha256'].append(digest(file))
        for method in result['disagreements']:
            other=WORK/'answers'/f'{graph}_{workers}_{rep}_{method}'/file.name
            result['disagreements'][method].append(int((answer!=np.fromfile(other,'<i4')).sum()))
    result['binary_sha256']=digest(path)
    result['exec_sha256']={stage:digest(args[0]) for stage,args in stages}
    save(folder/'record.json',result)
    print(label,round(result['build_s'],3),result['disagreements'],flush=True)


def ucef(graph,workers,rep,budget=300):
    tag=graph.lower()+'_full'
    label=f'{tag}_ucef_t{workers}_r{rep}'
    folder=OUT/label
    folder.mkdir(exist_ok=True)
    record=folder/'record.json'
    if record.exists():return json.loads(record.read_text())['status']
    path=ART/tag/(graph+'.bin')
    output=path.parent/(label+'.thr')
    exe=WORK/'ucef.exe'
    status,elapsed=process([exe,path,workers,output],environment(workers),folder/'run.log',budget)
    row=dict(input=tag,arm='ucef',workers=workers,rep=rep,status=status,process_wall_s=elapsed,budget_s=budget,
             input_sha256=digest(path),exe_sha256=digest(exe))
    if status=='ok':
        row.update(compare(path.parent/'reference.thr',output))
        row['output_sha256']=digest(output)
        row['output_bytes']=output.stat().st_size
        if row['max_abs']>1e-9:row['status']='invalid'
        else:output.unlink()
    save(record,row)
    print(label,row['status'],round(elapsed,3),flush=True)
    return row['status']


def main():
    OUT.mkdir(exist_ok=True,parents=True)
    from test_boundary import main as smoke
    smoke()
    for rep in range(1,4):
        for graph in ('Flickr','SupUser'):
            for workers in ((1,24) if rep==2 else (24,1)):
                refined(graph,workers,rep)
    for graph in ('Flickr','SupUser','DBLP','BiomineDSAA','Stack','Orkut'):
        for workers in ((1,24) if graph in ('Flickr','SupUser','DBLP') else (24,)):
            for rep in range(1,4):
                if ucef(graph,workers,rep)!='ok':break


if __name__=='__main__':main()
