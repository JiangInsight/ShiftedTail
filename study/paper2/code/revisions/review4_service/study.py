
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import time

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('PAPER2_ROOT', HERE.parents[2]))
WORK = Path(os.environ.get('PAPER2_WORK', 'C:/vldb_paper2_fair'))
SCRATCH = WORK / 'review4_service'
OUT = WORK / 'results/review4_service'
CODE = ROOT / 'code'
STRICT = ROOT/'results/review4_arithmetic/default_strict_verifier.exe'
STRICT_HASH = 'c1061ff07d7a8d13c3d2ddc3f8afdfd3f2c531dc7e818f5abe7b58d88054e8dc'
CAP = Path(os.environ.get('PAPER2_CAP', ROOT.parent/'paper1/code/memcap2.exe'))
GCC = Path(os.environ.get('PAPER2_GCC', ROOT.parent/'paper1/tools/dl_winlibs/mingw64/bin'))
GRAPH = {'WebGoogle': WORK / 'literature_coverage/WebGoogle/WebGoogle.bin',
         'Stack': ROOT / 'data/study/Stack.bin'}
BOUNDARY_FIXTURE = {'WebGoogle':'18698c263ab19123d9c8dd2526000adc897015bf8e5be2e797b458107b221039',
                    'Stack':'0dc4a1eff9f06b990c865917a5b06172a1430cdebf73163a4177d1930d207b3e'}
ENV = {k:v for k,v in os.environ.items() if not k.startswith(('UTHR_', 'OMP_', 'GATD_', 'MEMCAP_'))}
ENV.update(OMP_NUM_THREADS='24', UTHR_INDEXED='1', UTHR_GROUP_BASE='1', UTHR_COALESCE='1', UTHR_TOL='1e-12')
ENV['PATH'] = os.pathsep.join(map(str,[GCC, WORK/'deps/ucrt64/bin', ENV['PATH']]))

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def write(path, obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2)+'\n')

def invocation(args,inputs,extra=None):
    env=ENV|dict(extra or {})
    return dict(command=list(map(str,[CAP,32768,*args])),binary_sha256=sha(Path(args[0])),
                launcher_sha256=sha(CAP),inputs={str(Path(p).resolve()):sha(Path(p)) for p in inputs},
                environment={k:v for k,v in env.items() if k.startswith(('OMP_','UTHR_','MEMCAP_'))})

def stage_files(args,extra):
    name=Path(args[0]).stem
    if 'verif' in name:
        return args[1:4],[]
    if name=='ucef_order':
        return args[1:3],[args[3]]
    if name=='ucef':
        return [args[1]],[args[3]]
    if name=='export_rank':
        return [args[1]],args[2:]
    if name in ('uthr_native','uthr_study'):
        outputs=[args[6]]
        if extra and 'UTHR_CERT_ORDER' in extra:outputs.append(extra['UTHR_CERT_ORDER'])
        return [args[1]],outputs
    raise ValueError('unregistered service stage: '+name)

def cached(meta,identity):
    info=json.loads(meta.read_text())
    if info.get('identity')!=identity:
        raise ValueError('Cached run has different inputs, executable or settings; use a fresh workspace: '+str(meta))
    for path,expected in info.get('output_sha256',{}).items():
        if not Path(path).is_file() or sha(Path(path))!=expected:
            raise ValueError('Cached output is missing or changed: '+path)
    return info

def timed(label, args, extra=None, allow_failure=False):
    OUT.mkdir(exist_ok=True, parents=True)
    meta = OUT/(label+'.json')
    inputs,outputs=stage_files(args,extra)
    identity=invocation(args,inputs,extra)
    if meta.exists():
        info=cached(meta,identity)
        if info['rc'] and not allow_failure:
            raise RuntimeError(label)
        return info
    env=ENV|dict(extra or {})
    cmd=list(map(str,[CAP,32768,*args]))
    with (OUT/(label+'.log')).open('w') as log:
        start=time.perf_counter()
        status=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
        sec=time.perf_counter()-start
    output_hashes={str(Path(p).resolve()):sha(Path(p)) for p in outputs} if status.returncode==0 else {}
    info=dict(seconds=sec,rc=status.returncode,command=cmd,binary_sha256=sha(Path(args[0])),
              extra_environment=extra or {},identity=identity,output_sha256=output_hashes)
    write(meta,info)
    print(label,round(sec,3),status.returncode,flush=True)
    if status.returncode and not allow_failure:
        raise RuntimeError(label)
    return info

def setup():
    for g,path in GRAPH.items():
        d=SCRATCH/g
        d.mkdir(exist_ok=True,parents=True)
        timed(g+'_ucef_build',[WORK/'ucef.exe',path,24,d/'ucef.thr'])
        timed(g+'_frontier_build',[CODE/'uthr_native.exe',path,'frontier',5,24,1,d/'frontier.thr'],
              {'UTHR_CERT_ORDER':str(d/'frontier.ord')})
        timed(g+'_frontier_verify',[CODE/'verify_thresholds.exe',path,d/'frontier.thr',d/'frontier.ord',24])
        timed(g+'_rank',[CODE/'export_rank.exe',path,d/'rank'])

def certify():
    for g,path in GRAPH.items():
        d=SCRATCH/g
        timed(g+'_ucef_order',[SCRATCH/'ucef_order.exe',path,d/'ucef.thr',d/'ucef.ord',24])
        timed(g+'_ucef_verify',[CODE/'verify_thresholds.exe',path,d/'ucef.thr',d/'ucef.ord',24],allow_failure=True)

def strict_verify():
    build=json.loads((ROOT/'results/review4_arithmetic/strict-build.json').read_text())
    if sha(STRICT)!=build['binary_sha256'] or sha(CODE/'verify_thresholds.cpp')!=build['source_sha256'] or sha(CODE/'verified_tail.hpp')!=build['header_sha256']:
        raise ValueError('strict checker differs from the freshly built sources')
    for rep in (1,2,3):
        for g,path in GRAPH.items():
            base=SCRATCH/g;d=base if rep==1 else base/f'prep_r{rep}'
            for method in (('ucef','frontier') if rep!=2 else ('frontier','ucef')):
                timed(f'{g}_r{rep}_{method}_verify_strict',[STRICT,path,d/(method+'.thr'),d/(method+'.ord'),24])

def manifest():
    frozen=HERE/'requests'
    if frozen.exists():
        for g in GRAPH:
            record=json.loads((frozen/(g+'_manifest.json')).read_text())
            d=SCRATCH/g
            d.mkdir(parents=True,exist_ok=True)
            for tag,entry in record.items():
                q=entry['requests']
                if [float(v).hex() for v in q]!=entry['binary64']:
                    raise ValueError('request fixture lost binary64 precision')
                (d/(tag+'.txt')).write_text(''.join(format(x,'.17g')+'\n' for x in q))
            write(OUT/(g+'_manifest.json'),record)
        return
    base=[.5,.1,.9,.3,.7,.2,.8,.4,.6]
    for g in GRAPH:
        d=SCRATCH/g
        old=base+([.05,.95,.15,.85,.25,.75,.35,.65,.45] if g=='Stack' else [])
        seq={'original':old}
        meta={}
        for seed in (31721,84673):
            tag='perm'+str(seed)
            seq[tag]=np.random.Generator(np.random.PCG64(seed)).permutation(old).tolist()
            meta[tag]={'seed':seed,'rule':'permutation of original'}
        if g=='Stack':
            seq['load_first']=[.95]+[x for x in old if x!=.95]
            meta['load_first']={'rule':'original .95 request moved first, all other relative positions retained'}
        for tag,seed,mode in [('uniform',63247,'uniform'),('high',19739,'beta')]:
            r=np.random.Generator(np.random.PCG64(seed))
            x=r.uniform(.03,.97,len(old)) if mode=='uniform' else .03+.94*r.beta(4,1,len(old))
            seq[tag]=x.tolist()
            meta[tag]={'seed':seed,'rule': 'Uniform(.03,.97)' if mode=='uniform' else '.03+.94*Beta(4,1)'}


        source=(WORK/'literature_coverage/WebGoogle/reference.thr' if g=='WebGoogle'
                else ROOT/'results/study/stack_native_cert/values.thr')
        if not source.exists():source=d/'frontier.thr'
        if sha(source)!=BOUNDARY_FIXTURE[g]:
            raise ValueError('source differs from the preregistered threshold fixture')
        r=np.random.Generator(np.random.PCG64(74933))
        wanted={1,2,3,4,5,6}
        samples={}
        with source.open('rb') as f:
            while hdr:=f.read(12):
                k,n=struct.unpack('<IQ',hdr)
                if k not in wanted:
                    f.seek(n*8,1);continue
                row=np.fromfile(f,'<f8',n)
                choices=np.flatnonzero((row>.1)&(row<.9))
                ix=int(r.choice(choices))
                samples[k]=(ix,float(row[ix]))
        seq['boundary']=[]
        anchors=[]
        for k in range(1,len(old)//3+1):
            i,t=samples[k]
            seq['boundary'].extend([float(np.nextafter(t,-np.inf)),t,float(np.nextafter(t,np.inf))])
            anchors.append({'level':k,'rank_position':i,'theta':t.hex()})
        meta['boundary']={'seed':74933,'rule':'uniform eligible rank in each predeclared row; predecessor, stored, successor binary64',
                          'rows_processed_in':'descending k in {1,...,6}', 'anchors':anchors,'fixture_sha256':sha(source)}
        for tag,etas in seq.items():
            (d/(tag+'.txt')).write_text(''.join(format(x,'.17g')+'\n' for x in etas))
        write(OUT/(g+'_manifest.json'),{tag:{**meta.get(tag,{}),'requests':q,'binary64':[v.hex() for v in q]} for tag,q in seq.items()})

def query(g,tag,method):
    d=SCRATCH/g
    label=f'{g}_{tag}_{method}'
    meta=OUT/(label+'.json')
    dest=d/tag/method
    dest.mkdir(parents=True,exist_ok=True)
    index=method in ('ucef','frontier')
    if index:
        verification=[STRICT,GRAPH[g],d/(method+'.thr'),d/(method+'.ord'),24]
        proof=cached(OUT/f'{g}_r1_{method}_verify_strict.json',invocation(verification,verification[1:4]))
        if proof['rc']!=0:raise ValueError('Query table has not passed strict verification')
        args=[SCRATCH/'index.exe',d/(method+'.thr'),24,d/'rank',dest/'ans',GRAPH[g],d/(tag+'.txt')]
        inputs=[args[i] for i in (1,3,5,6)]
    else:
        args=[SCRATCH/'direct.exe',GRAPH[g],24,6 if method=='topdown' else 4,dest/'ans',d/(tag+'.txt')]
        inputs=[args[1],args[5]]
    identity=invocation(args,inputs)
    if meta.exists():
        if cached(meta,identity)['rc']!=0:raise RuntimeError(label)
        return
    cmd=list(map(str,[CAP,32768,*args]))
    prefixes=[]; internal=[]; elapsed=[]; emitted=[]; refinements=[]; ready=None
    with (OUT/(label+'.log')).open('w') as log:
        start=time.perf_counter()
        proc=subprocess.Popen(cmd,env=ENV,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace')
        for line in proc.stdout:
            if line.startswith('ANSWER '):
                prefixes.append(time.perf_counter()-start)
                _,i,eta,seconds,prefix=line.split()
                assert int(i)==len(prefixes)-1
                emitted.append(float(eta))
                internal.append(float(prefix));elapsed.append(float(seconds))
            elif line.startswith('REFINE '):
                refinements.append(list(map(int,line.split()[2:])))
            elif line.startswith('READY '):
                ready=float(line.split()[1])
            log.write(line);log.flush()
        rc=proc.wait()
        wall=time.perf_counter()-start
    q=json.loads((OUT/(g+'_manifest.json')).read_text())[tag]['requests']
    assert rc==0 and emitted==q and len(q)==len(prefixes)
    n=(d/'rank').stat().st_size//4
    outputs=[dest/f'ans-{i}.bin' for i in range(len(q))]
    assert all(p.stat().st_size==4*n for p in outputs)
    write(meta,dict(rc=rc,graph=g,tag=tag,method=method,ready=ready,seconds=wall,
                    requests=q,prefixes=prefixes,internal_prefixes=internal,answer_seconds=elapsed,
                    refinements=refinements,answer_sha256=[sha(p) for p in outputs],command=cmd,binary_sha256=sha(args[0]),
                    identity=identity,output_sha256={str(p.resolve()):sha(p) for p in outputs}))
    print(label,round(wall,2),flush=True)

def queries(part='all'):
    slow_crosscheck=None
    for g in GRAPH:
        tags=list(json.loads((OUT/(g+'_manifest.json')).read_text()))
        for tagnum,tag in enumerate(tags):
            early=tag in ('original','perm31721','boundary')
            if (part=='early' and not early) or (part=='late' and early):
                continue
            methods=['ucef','frontier','topdown']
            if g=='WebGoogle' or tag=='uniform':methods.append('bottomup')
            offset=tagnum%len(methods)
            for method in methods[offset:]+methods[:offset]:
                if g=='Stack' and tag=='uniform' and method=='bottomup':
                    slow_crosscheck=(g,tag,method)
                else:
                    query(g,tag,method)
    if slow_crosscheck:query(*slow_crosscheck)

def repeat_prep():
    for rep in (2,3):
        for g,path in GRAPH.items():
            base=SCRATCH/g;d=base/f'prep_r{rep}';d.mkdir(exist_ok=True)
            for method in (('frontier','ucef') if rep==2 else ('ucef','frontier')):
                label=f'{g}_r{rep}_{method}_'
                if method=='ucef':
                    timed(label+'build',[WORK/'ucef.exe',path,24,d/'ucef.thr'])
                    timed(label+'order',[SCRATCH/'ucef_order.exe',path,d/'ucef.thr',d/'ucef.ord',24])
                else:
                    timed(label+'build',[CODE/'uthr_native.exe',path,'frontier',5,24,1,d/'frontier.thr'],
                          {'UTHR_CERT_ORDER':str(d/'frontier.ord')})
                timed(label+'verify',[CODE/'verify_thresholds.exe',path,d/(method+'.thr'),d/(method+'.ord'),24])
                value_hash=sha(d/(method+'.thr'));order_hash=sha(d/(method+'.ord'))
                same_values=value_hash==sha(base/(method+'.thr'))
                same_order=order_hash==sha(base/(method+'.ord'))
                write(OUT/(label+'outputs.json'),dict(value_sha256=value_hash,order_sha256=order_hash,
                                                     values_reproduce_first=same_values,order_reproduces_first=same_order))
                assert same_values and (same_order or method=='frontier')
            timed(f'{g}_r{rep}_rank',[CODE/'export_rank.exe',path,d/'rank'])
            assert sha(d/'rank')==sha(base/'rank')

if __name__=='__main__':
    import sys
    if sys.argv[1]=='setup':
        setup()
    elif sys.argv[1]=='certify':certify()
    elif sys.argv[1]=='manifest':manifest()
    elif sys.argv[1]=='queries':queries(sys.argv[2] if len(sys.argv)>2 else 'all')
    elif sys.argv[1]=='repeat_prep':repeat_prep()
    elif sys.argv[1]=='strict_verify':strict_verify()
