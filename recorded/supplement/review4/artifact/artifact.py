
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
UPSTREAM='88b5ba7f60560363bc1579c7ee7984ee3541be6e'
SIX={'Flickr','SupUser','Stack','Orkut','DBLP','BiomineDSAA'}
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def eq(got,expected,what):
    if got!=expected:raise ValueError(f'{what}: expected {expected}, got {got}')
def rehydrate_gpu(up,out):
    rev=subprocess.check_output(['git','rev-parse','HEAD'],cwd=up,text=True).strip()
    eq(rev,UPSTREAM,'upstream revision')

    with tempfile.TemporaryDirectory() as tmp:
        tree=Path(tmp);src=tree/'src';src.mkdir()
        for name in subprocess.check_output(['git','ls-tree','--name-only','HEAD:src'],cwd=up,text=True).splitlines():
            (src/name).write_bytes(subprocess.check_output(['git','show',f'HEAD:src/{name}'],cwd=up))
        for wd,patch in [(tree,'results/study/gatd_windows.patch'),(tree,'results/study/gatd_reduction.patch'),(src,'code/fair_study/gpu_sparse.patch')]:
            subprocess.run(['git','apply','--ignore-space-change','--ignore-whitespace',str(ROOT/patch)],cwd=wd,check=True)
        hashes=json.loads((HERE/'cuda_hashes.json').read_text())
        for name,h in hashes.items():
            data=(src/name).read_bytes()
            eq(hashlib.sha256(data.replace(b'\r\n',b'\n')).hexdigest(),h,name)
        if out:
            out.mkdir(exist_ok=True,parents=True)

            for n in hashes:
                dest=out/n
                if dest.exists():eq(dest.read_bytes().replace(b'\r\n',b'\n'),(src/n).read_bytes().replace(b'\r\n',b'\n'),n)
                else:shutil.copyfile(src/n,dest)
            build=ROOT/'baselines/gatd_win_matched/build_windows.bat'
            if build.resolve()!=(out/build.name).resolve():shutil.copyfile(build,out/build.name)
        print(f'{len(hashes)} port files match all three patches')
def check_graph(name,path,kind):
    with (HERE.parent/'inputs.csv').open() as src:
        rows={r['graph']:r for r in csv.DictReader(src)}
    row=rows[name]
    if kind=='original' and name not in SIX:
        raise ValueError('This graph was prepared directly for the matched cohort; use its matched hash.')
    hasher=hashlib.sha256()
    with path.open('rb') as f:
        header=f.read(12);n,arcs=struct.unpack('<IQ',header)
        eq((n,arcs),(int(row['vertices']),2*int(row['edges'])),'CSR shape')
        eq(path.stat().st_size,12+4*n+12*arcs,'CSR length')
        hasher.update(header)
        for data in iter(lambda:f.read(8*1024**2),b''):hasher.update(data)
    eq(hasher.hexdigest(),row['matched_file_sha256' if kind=='matched' else 'original_file_sha256'],name)
    print(name,kind,n,arcs//2,hasher.hexdigest())
def check_zip(path):
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:raise ValueError('failed CRC')
        sums=json.loads(z.read('SHA256.json'))
        eq(set(z.namelist()),set(sums)|{'SHA256.json'},'source inventory')
        for n,h in sums.items():eq(hashlib.sha256(z.read(n)).hexdigest(),h,n)
        print(len(sums),'source/manifest files verified')
def make_cpu(work):
    boost=Path(os.environ.get('BOOST_MATH_INCLUDE',ROOT/'baselines/boost_math/include'))
    env=dict(os.environ,CL=f'/arch:AVX2 /I"{boost}"')
    work.mkdir(parents=True,exist_ok=True)
    code=ROOT/'code';vc=code/'build.bat'
    for exe,src in [(code/'uthr_native.exe',code/'uthr_study.cpp'),(code/'opti_native.exe',code/'opti_threshold.cpp'),
                    (code/'export_rank.exe',code/'export_rank.cpp'),(work/'ucef.exe',code/'fair_study/ucef.cpp'),
                    (ROOT.parent/'paper1/code/memcap2.exe',ROOT.parent/'paper1/code/memcap.cpp')]:
        subprocess.run([vc,src,exe],cwd=work,env=env,check=True)

    subprocess.run([vc,HERE.parent/'bounds/verify_thresholds.cpp',code/'verify_thresholds.exe'],cwd=work,env=env,check=True)
    gcc=Path(os.environ.get('CXX',ROOT.parent/'paper1/tools/dl_winlibs/mingw64/bin/g++.exe'))
    gmp=Path(os.environ.get('GMP_ROOT',work/'deps/ucrt64'));author=Path(os.environ.get('DAI_SRC',work/'UncertainCore/src'))
    src=code/'fair_study/query_workload.cpp'
    common=[gcc,'-O3','-march=native','-fopenmp','-std=gnu++17']
    env['PATH']=os.pathsep.join([str(gcc.parent),str(gmp/'bin'),env['PATH']])
    for exe,args in [('index_queries',[src]),('index_refined',['-DREFINE_QUERY','-ffp-contract=off',src,'-I'+str(gmp/'include'),'-L'+str(gmp/'lib'),'-lgmpxx','-lgmp']),
                     ('dai_queries',['-DDIRECT','-I'+str(author),'-I'+str(gmp/'include'),src,author/'graph.cpp',author/'uncertain-core.cpp',
                      author/'uncertain-core-topdown.cpp','-L'+str(gmp/'lib'),'-lgsl','-lgslcblas','-lgmp'])]:
        subprocess.run([*common,*args,'-o',work/(exe+'.exe')],cwd=work,env=env,check=True)
def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='sub',required=True)
    g=sub.add_parser('gpu');g.add_argument('upstream',type=Path);g.add_argument('--output',type=Path)
    i=sub.add_parser('input');i.add_argument('name');i.add_argument('kind',choices=['original','matched']);i.add_argument('path',type=Path)
    a=sub.add_parser('source-zip');a.add_argument('path',type=Path)
    c=sub.add_parser('cpu-build');c.add_argument('--work',type=Path,default=Path('C:/vldb_paper2_fair'))
    args=ap.parse_args()
    if args.sub=='gpu':rehydrate_gpu(args.upstream.resolve(),args.output)
    elif args.sub=='input':check_graph(args.name,args.path,args.kind)
    elif args.sub=='cpu-build':make_cpu(args.work.resolve())
    else:check_zip(args.path)
if __name__=='__main__':main()
