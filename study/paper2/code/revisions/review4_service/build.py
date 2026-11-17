
import subprocess
import os
from pathlib import Path
from study import HERE, CODE, GCC, WORK, ROOT, ENV, OUT, SCRATCH, sha, write

def main():
    SCRATCH.mkdir(parents=True,exist_ok=True)
    OUT.mkdir(parents=True,exist_ok=True)
    author=Path(os.environ.get('DAI_SRC',WORK/'UncertainCore/src'))
    lib=Path(os.environ.get('GMP_ROOT',WORK/'deps/ucrt64'))
    ref=CODE/'fair_study/query_workload.cpp'
    code=ref.read_text()
    old='const double queries[]={.5,.1,.9,.3,.7,.2,.8,.4,.6};'
    new='''std::ifstream requests(argv[argc-1]);
    if(!requests)throw std::runtime_error("missing request manifest");
    std::vector<double> queries;double eta;
    while(requests>>eta){
        if(!(eta>0 && eta<=1))throw std::runtime_error("invalid confidence");
        queries.push_back(eta);
    }
    if(!requests.eof()||queries.empty())throw std::runtime_error("invalid request manifest");'''
    for left,right in [('argc!=6','argc!=7'),('argc!=5','argc!=6'),(old,new),('i<9;++i','i<static_cast<int>(queries.size());++i'),
                        ('setprecision(10)','setprecision(17)')]:
        if code.count(left)!=1:raise ValueError('workload source changed')
        code=code.replace(left,right)
    generated=SCRATCH/'query_workload.cpp'
    generated.write_text(code)
    backend=HERE/'boundary_query.hpp'
    flags=[GCC/'g++.exe','-O3','-march=native','-fopenmp','-std=gnu++17']
    targets={'ucef_order': [ROOT/'code/build.bat',HERE/'ucef_order.cpp',SCRATCH/'ucef_order.exe'],
             'index':flags+['-DREFINE_QUERY','-ffp-contract=off',generated,'-I'+str(HERE),'-I'+str(lib/'include'),'-L'+str(lib/'lib'),'-lgmpxx','-lgmp','-o',SCRATCH/'index.exe'],
             'direct':flags+['-DDIRECT','-I'+str(author),'-I'+str(lib/'include'),generated,author/'graph.cpp',author/'uncertain-core.cpp',author/'uncertain-core-topdown.cpp','-L'+str(lib/'lib'),'-lgsl','-lgslcblas','-lgmp','-o',SCRATCH/'direct.exe']}
    sources=[ref,backend,generated,HERE/'ucef_order.cpp',CODE/'graph.hpp',CODE/'fair_study/ucef.cpp',CODE/'verify_thresholds.cpp',CODE/'export_rank.cpp',CODE/'uthr_study.cpp',CODE/'peel_queue.hpp',*sorted(author.glob('*.h')),*sorted(author.glob('*.cpp'))]
    for tag,args in targets.items():
        exe=SCRATCH/(tag+'.exe')
        if exe.exists():exe.unlink()
        with (OUT/('compile_'+tag+'.log')).open('w') as f:
            subprocess.run(list(map(str,args)),env=ENV|{'CL':'/arch:AVX2'},cwd=SCRATCH,stdout=f,stderr=subprocess.STDOUT,check=True)
        if not exe.is_file():raise RuntimeError('compiler did not produce '+str(exe))
        write(OUT/('compile_'+tag+'.json'),{'cmd':list(map(str,args)),'binary':sha(exe),
              'source_hashes':{str(p):sha(p) for p in sources},'flags_env':{'CL':'/arch:AVX2'}})

if __name__=='__main__':main()
