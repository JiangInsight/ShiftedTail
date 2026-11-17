
from pathlib import Path
import argparse
import os
import subprocess
import sys
import json

from artifact import ROOT

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--work',type=Path,default=Path('C:/vldb_paper2_fair'))
    ap.add_argument('--strict',action='store_true',help='build FMA/outward checkers in this extraction')
    args=ap.parse_args();work=args.work.resolve()
    gcc=Path(os.environ.get('CXX',ROOT.parent/'paper1/tools/dl_winlibs/mingw64/bin/g++.exe'))
    gmp=Path(os.environ.get('GMP_ROOT',work/'deps/ucrt64'))
    os.environ['PATH']=os.pathsep.join([str(gcc.parent),str(gmp/'bin'),os.environ['PATH']])
    code=ROOT/'code'
    sys.path.insert(0,str(code/'fair_study'))
    import test_boundary
    import run_extension
    test_boundary.WORK=work
    run_extension.OUT.mkdir(parents=True,exist_ok=True)
    test_boundary.main()
    checks=[code/'verify_thresholds.exe']
    for check in checks:
        subprocess.run([sys.executable,'-B',ROOT/'paper/verify_example.py',check],check=True)
    case=work/'boundary_smoke';graph=case/'g.bin';rank=case/'rank';order=case/'frontier.order';values=case/'frontier.thr'
    env=dict(os.environ,UTHR_CERT_ORDER=str(order),UTHR_INDEXED='1',UTHR_GROUP_BASE='1',UTHR_COALESCE='1',OMP_NUM_THREADS='1')
    subprocess.run([code/'uthr_native.exe',graph,'frontier','5','1','1',values],check=True,env=env)
    subprocess.run([checks[0],graph,values,order,'1'],check=True)
    subprocess.run([code/'opti_native.exe',graph,'opti','5','1','1',case/'opti.thr'],check=True)
    from run_matched import compare
    delta=compare(values,case/'opti.thr')
    if delta['max_abs']>1e-9:raise AssertionError(delta)
    fresh_rank=case/'fresh.rank'
    subprocess.run([code/'export_rank.exe',graph,fresh_rank],check=True)
    if rank.read_bytes()!=fresh_rank.read_bytes():raise AssertionError('rank mismatch')
    for algorithm in ('4','6'):
        subprocess.run([work/'dai_queries.exe',graph,'1',algorithm,case/('dai'+algorithm)],check=True)
    if args.strict:
        out=ROOT/'results/release_smoke';out.mkdir(parents=True,exist_ok=True)
        for name,fma in (('fma',['-mfma']),('outward',['-mno-fma','-DUCORE_NO_FMA'])):
            exe=out/(name+'.exe')
            subprocess.run([gcc,'-O2','-std=c++17','-fopenmp','-fno-fast-math','-frounding-math','-ffp-contract=off',
                            *fma,code/'verify_thresholds.cpp','-o',exe],check=True)
            subprocess.run([sys.executable,'-B',ROOT/'paper/verify_example.py',exe],check=True)
            subprocess.run([exe,graph,values,order,'1'],check=True)
    print(json.dumps(dict(exhaustive_graphs=10,confidences_per_graph=9,ucef_worker_counts=[1,3],
                          opti_max_abs=delta['max_abs'],direct_algorithm_ids=[4,6],strict=args.strict)))
if __name__=='__main__':main()
