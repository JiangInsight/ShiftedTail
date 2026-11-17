
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
import time
from fractions import Fraction

HERE = Path(__file__).resolve().parent
RESULTS = HERE / 'logs'
GRAPHS = ('Twitter', 'CN15kProjection')
ABC = ('shift', 'retained', 'combined')
OTHER = ('no_floor', 'tol_zero', 'no_trim', 'screen_on', 'fanout1', 'fanout4', 'cap8')
SWITCHES = dict(no_floor={'UTHR_NOCOREFLOOR':'1'}, tol_zero={'UTHR_TOL':'0'},
                no_trim={'REV_NOTRIM':'1'}, screen_on={'UTHR_TAIL_SCREEN':'1'},
                fanout1={'REV_FANOUT':'1'}, fanout4={'REV_FANOUT':'4'}, cap8={'REV_OFFSET_CAP':'8'})

def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

def write(p,obj):
    p.write_text(json.dumps(obj,indent=2)+'\n')

def clean():
    return {k:v for k,v in os.environ.items() if not k.startswith(('OMP_','UTHR_','REV_'))}

def build(work,boost):
    env=clean()
    env['CL']=f'/arch:AVX2 /fp:strict /I"{boost.resolve()}"'
    for stem in ('frontier','verify_thresholds'):
        with (RESULTS/(stem+'_build.log')).open('w') as out:
            subprocess.run(['cmd','/c',str(HERE/'build.bat'),str(HERE/(stem+'.cpp')),str(work/(stem+'.exe'))],
                           cwd=work,env=env,stdout=out,stderr=subprocess.STDOUT,check=True)
    triples=[(d,k,p) for d in (1,4,9,30,70,120) for k in sorted({1,max(1,d//3),d//2+1,d})
             for p in (0.,2**-40,0.001,0.1,0.5,0.9,1.-2**-52,1.)]
    triples.extend([(1200,1190,0.01),(1200,5,.99),(1200,1180,.99),(1200,7,.01)])
    output=subprocess.check_output([work/'frontier.exe','--binomial-test'],text=True,
                                   input=''.join(f'{d} {k} {p:.17g}\n' for d,k,p in triples),env=env)
    gaps=[]
    for (d,k,p),raw in zip(triples,output.splitlines(),strict=True):
        p=Fraction(p)
        if d-k<k:
            exact=sum(math.comb(d,j)*p**j*(1-p)**(d-j) for j in range(k,d+1))
        else:
            exact=1-sum(math.comb(d,j)*p**j*(1-p)**(d-j) for j in range(k))
        lower=Fraction(float(raw))
        assert 0<=lower<=exact<=1,(d,k,float(p),raw,float(exact))
        gaps.append(float(exact-lower))
    write(RESULTS/'build.json',dict(flags=env['CL'],build_driver='build.bat',exact_test_cases=len(gaps),
          maximum_binomial_slack=max(gaps),source={p.name:sha(p) for p in HERE.glob('*.cpp')},
          headers={p.name:sha(p) for p in HERE.glob('*.hpp')},
          binaries={p.name:sha(p) for p in work.glob('*.exe') if p.stem in ('frontier','verify_thresholds')}))

def timed(args,env,log,work,timeout=180):
    t=time.perf_counter()
    with log.open('w') as out:
        try:
            status=subprocess.run(args,cwd=work,env=env,stdout=out,stderr=subprocess.STDOUT,
                                  timeout=timeout,check=False).returncode
        except subprocess.TimeoutExpired:
            status='timeout'
    return status,time.perf_counter()-t

def one(work,inputs,graph,arm,rep):
    label=f'{graph}_{arm}_{rep}'
    record=RESULTS/(label+'.json')
    if record.exists():
        raise RuntimeError(f'existing observation {record}')
    path=inputs/graph/(graph+'.bin')
    out=work/(label+'.thr')
    rank=work/(label+'.ord')
    env=clean()
    env.update(OMP_NUM_THREADS='1',UTHR_TOL='1e-12',UTHR_GROUP_BASE='1',UTHR_INDEXED='1',
               UTHR_COALESCE='1',UTHR_CERT_ORDER=str(rank),
               REV_BOUND=arm if arm in (*ABC,'shadow') else 'shift')
    env.update(SWITCHES.get(arm,{}))
    if arm.endswith('_legacy'):
        env.update(REV_BOUND=arm.removesuffix('_legacy'),REV_LEGACY_BETA='1')
    if arm=='shadow':
        env['REV_SAMPLES']=str(RESULTS/(graph+'_samples.csv'))
    log=RESULTS/(label+'.log')
    rc,elapsed=timed([work/'frontier.exe',path,'frontier','5','1','1',out],env,log,work)
    raw=log.read_text()
    row=dict(graph=graph,arm=arm,rep=rep,status=rc,wall_s=elapsed,graph_sha256=sha(path),
             binary_sha256=sha(work/'frontier.exe'),flags={k:v for k,v in env.items() if k.startswith(('UTHR_','REV_','OMP_'))})
    if rc==0:
        for section in ('work','maintenance'):
            row[section]={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',re.search('^'+section+' (.+)',raw,re.M)[1])}
        row.update(theta_sha256=sha(out),order_sha256=sha(rank),ladder_length=int(re.search(r' L=(\d+)',raw)[1]))
        verify=RESULTS/(label+'_verify.log')
        ret,seconds=timed([work/'verify_thresholds.exe',path,out,rank,'1'],env,verify,work)
        row.update(verify_status=ret,verify_s=seconds)
        line=re.search(r'^certificate values=(\d+) max_lower_deficit=(\S+) max_upper_excess=(\S+)',verify.read_text(),re.M)
        if line:
            row.update(values=int(line[1]),Dminus=float(line[2]),Dplus=float(line[3]))
    write(record,row)
    print(label,rc,round(elapsed,3),row.get('verify_status'),flush=True)
    if rc!=0 or row.get('verify_status')!=0:
        raise RuntimeError(label)

def report():
    rows=[json.loads(p.read_text()) for p in RESULTS.glob('*.json') if p.name!='build.json']
    keys=['graph','arm','n','median_s','min_s','max_s','repeat_calls','distinct','peel_cells','probes','binomial_misses','Dminus','Dplus']
    with (HERE/'summary.csv').open('w',newline='') as f:
        wr=csv.writer(f);wr.writerow(keys)
        for g,a in sorted({(x['graph'],x['arm']) for x in rows}):
            runs=[x for x in rows if x['graph']==g and x['arm']==a]
            assert all(x['status']==x['verify_status']==0 for x in runs)
            first=runs[0];ts=[x['wall_s'] for x in runs]
            assert len({(x['theta_sha256'],x['order_sha256']) for x in runs})==1
            wr.writerow([g,a,len(ts),statistics.median(ts),min(ts),max(ts),first['work']['repeat_calls'],
                         first['work']['repeated_vertex_levels'],first['work']['peel_cells'],
                         first['maintenance']['ranked_probes'],first['maintenance']['binomial_misses'],first['Dminus'],first['Dplus']])
    with (HERE/'groups.csv').open('w',newline='') as f:
        wr=csv.writer(f);wr.writerow(['graph','k','degree','removed','events','shift_wins','retained_wins','ties','shift_only_above_T','retained_only_above_T','both_above_T'])
        for log in RESULTS.glob('*_shadow_1.log'):
            for line in log.read_text().splitlines():
                if not line.startswith('group '): continue
                b,s,r,t,so,ro,both=map(int,re.findall(r'=(\d+)',line))
                wr.writerow([log.name.split('_')[0],('1-4','5-16','17+')[b//6],('1-32','33+')[(b//3)%2],
                             ('1','2-4','5+')[b%3],s+r+t,s,r,t,so,ro,both])
    with (HERE/'tightness.csv').open('w',newline='') as f:
        wr=csv.writer(f)
        wr.writerow(['graph','retained_probability_range','samples','shift_win_pct','retained_win_pct',
                     'shift_slack_median','shift_slack_p95','retained_slack_median','retained_slack_p95',
                     'combined_slack_median','combined_slack_p95','max_observed_overshoot'])
        for sample in RESULTS.glob('*_samples.csv'):
            with sample.open() as source:
                data=[{k:float(v) for k,v in row.items()} for row in csv.DictReader(source)]
            for tag,lo,hi in [('all',0.,2.),('[0,.25)',0.,.25),('[.25,.75)',.25,.75),('[.75,1]',.75,2.)]:
                group=[x for x in data if lo<=x['pmax']-x['pmin']<hi]
                if not group: continue
                n=len(group)
                gaps=[[x['tail']-b(x) for x in group] for b in (
                    lambda x:x['shift'],lambda x:x['retained'],lambda x:max(x['shift'],x['retained']))]
                overshoot=max(0.,-min(min(g) for g in gaps))
                if overshoot>1e-9:raise RuntimeError(f'{sample} tail discrepancy {overshoot}')
                wr.writerow([sample.name.split('_')[0],tag,n,100*sum(x['shift']>x['retained'] for x in group)/n,
                             100*sum(x['retained']>x['shift'] for x in group)/n,
                             *(v for gap in gaps for v in (statistics.median(gap),sorted(gap)[math.ceil(.95*n)-1])),overshoot])

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('stage',choices=['build','first','repeat','shortcuts','legacy','shadow','report'])
    ap.add_argument('--work',type=Path,default=Path('C:/vldb_paper2_fair/review4_bounds'))
    ap.add_argument('--inputs',type=Path,default=Path('C:/vldb_paper2_fair/literature_coverage'))
    ap.add_argument('--boost',type=Path,default=HERE.parents[3]/'baselines/boost_math/include')
    opts=ap.parse_args();work=opts.work.resolve()
    work.mkdir(exist_ok=True,parents=True);RESULTS.mkdir(exist_ok=True)
    if opts.stage=='build':build(work,opts.boost)
    elif opts.stage=='report':report()
    else:
        for graph in GRAPHS:
            if opts.stage=='first': jobs=[(a,1) for a in ABC]
            elif opts.stage=='repeat': jobs=[(a,r) for r in (2,3) for a in ABC[r-1:]+ABC[:r-1]]
            elif opts.stage=='legacy':jobs=[(a,r) for r in (1,2,3) for a in (('retained_legacy','combined_legacy') if r%2 else ('combined_legacy','retained_legacy'))]
            elif opts.stage=='shadow':jobs=[('shadow',1)]
            else:jobs=[(a,r) for r in (1,2,3) for a in OTHER[r-1:]+OTHER[:r-1]]
            for arm,rep in jobs:one(work,opts.inputs,graph,arm,rep)
