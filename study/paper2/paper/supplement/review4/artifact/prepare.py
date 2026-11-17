
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import sys
import time
import json

from artifact import ROOT, HERE, SIX, check_graph

CODE=ROOT/'code'
sys.path[:0]=[str(CODE),str(CODE/'fair_study')]
import prepare_study_inputs as init
import run_matched as matched
import literature_coverage as lit
import large_literature as large
from run_extension import environment
from study_real_inputs import convert as dsaa

def prepare(name):
    raw=ROOT/'data/study';raw.mkdir(parents=True,exist_ok=True)
    path=raw/(name+'.bin')
    if name in SIX:
        if not path.exists():
            if name=='Flickr':
                if not (raw/'Flickr.txt').exists():shutil.copyfile(matched.WORK/'bonchi_public/data/Flickr.txt',raw/'Flickr.txt')
                init.convert_text(name)
            elif name=='SupUser':init.convert_events(name,raw/'sx-superuser.txt.gz')
            elif name=='Stack':init.convert_csr(name,ROOT/'results/stack.wbin',True)
            elif name=='Orkut':init.convert_csr(name,ROOT.parent/'paper1/data/bin/com-orkut.bin',False)
            else:
                if (raw/(name+'.source.json')).exists():
                    raise ValueError('Use a fresh data/study without a stale preparation marker')
                member='data/large/biomine.txt' if name=='BiomineDSAA' else 'data/casestudy/dblp.txt'
                if not dsaa(member,name):raise ValueError('unusable DSAA graph')
        check_graph(name,path,'original')
        subprocess.run([CODE/'export_rank.exe',path,raw/(name+'.rank')],check=True)
        out,_=matched.derived(name.lower()+'_full',name,'full')
    else:
        lit.SCRATCH.mkdir(exist_ok=True,parents=True);lit.OUT.mkdir(exist_ok=True,parents=True)
        if (lit.OUT/(name+'_input.json')).exists() and not (lit.SCRATCH/name/(name+'.bin')).exists():
            raise ValueError('Existing result marker has no graph. Use an empty reproduction tree.')
        if name in lit.GRAPHS:out,_=lit.prepared(name)
        elif name=='WikiTalkFR':out,_=large.event_input(name,1420367,4641928,lit.WORK/'wiki_fr_events.zip','https://networks.skewed.de/net/wiki_talk/files/fr.csv.zip')
        elif name=='Deli':out,_=large.event_input(name,38289740,301183605,lit.WORK/'delicious_ti.zip','https://networks.skewed.de/net/delicious/files/ti.csv.zip')
        else:raise ValueError(name)
    check_graph(name,out,'matched')

def query_prerequisites():
    for name in ('Flickr','SupUser','Stack'):
        p=ROOT/'data/study'/(name+'.bin');check_graph(name,p,'original')
        folder=ROOT/'results/study'/(name.lower()+'_native_cert');folder.mkdir(parents=True,exist_ok=True)
        values=folder/'values.thr';order=folder/'removals.bin'
        env=environment(24);env['UTHR_CERT_ORDER']=str(order)
        subprocess.run([matched.CAP,'32768',matched.CPU,p,'frontier','5','24','1',values],env=env,check=True)
        subprocess.run([matched.CAP,'32768',CODE/'verify_thresholds.exe',p,values,order,'24'],check=True)
        if name=='Stack':continue

        for workers in (24,1):
            for rep in range(1,4):
                suffix=('t1' if workers==1 else '')+f'r{rep}'
                dest=ROOT/'results/study'/f'{name.lower()}_native_indexed_{suffix}'
                dest.mkdir(parents=True,exist_ok=True)
                marker=dest/'record.json'
                if marker.exists():raise FileExistsError(marker)
                t=time.perf_counter()
                with (dest/'run.log').open('w') as f:
                    subprocess.run([matched.CAP,'32768',matched.CPU,p,'frontier','5',str(workers),'1'],env=environment(workers),
                                   stdout=f,stderr=subprocess.STDOUT,check=True)
                marker.write_text(json.dumps(dict(process_wall_s=time.perf_counter()-t,reproduction=True)))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('names',nargs='+');args=ap.parse_args()
    for name in args.names:
        if name=='query-prerequisites':query_prerequisites()
        else:prepare(name)
