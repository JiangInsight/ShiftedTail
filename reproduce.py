import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / 'study/paper2'
CODE = PROJECT / 'code'
PINNED = {
    'boost': ('https://github.com/boostorg/math', 'f1b0b95a04f56717b3454cb599e0647770c5852e'),
    'dai': ('https://github.com/qq-dai/UncertainCore', '315dee85ff5aae487c296a99fb600304bbee0f24'),
    'bonchi': ('https://github.com/fgullo/uncertaincores', '370b2dbcaa02a3466a2afd10e24cd52019c3edb3'),
    'gatd': ('https://github.com/AbigailJixiangyuyu/uco-gpu', '88b5ba7f60560363bc1579c7ee7984ee3541be6e'),
    'ukge': ('https://github.com/stasl0217/UKGE', '5049b84501657abc44c36dd7d2db5f8519e5ee8f'),
}

def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def environment(work):
    env = {k: v for k, v in os.environ.items() if not k.startswith(('UTHR_', 'REV_', 'OMP_', 'GATD_'))}
    env.update(PAPER2_WORK=str(work), PAPER2_ROOT=str(PROJECT), OMP_NUM_THREADS='1',
               UTHR_COALESCE='1', UTHR_GROUP_BASE='1', UTHR_INDEXED='1', UTHR_TOL='1e-12',
               UTHR_RESOURCE_SCRATCH=str(work/'review4_resources'))
    env.setdefault('BOOST_MATH_INCLUDE', str(PROJECT/'baselines/boost_math/include'))
    env.setdefault('GMP_ROOT', str(work/'deps/ucrt64'))
    env.setdefault('DAI_SRC', str(work/'UncertainCore/src'))
    env.setdefault('CXX', str(ROOT/'study/paper1/tools/dl_winlibs/mingw64/bin/g++.exe'))
    env.setdefault('PAPER2_GCC', str(Path(env['CXX']).parent))
    env['PATH'] = os.pathsep.join([str(Path(env['CXX']).parent), str(Path(env['GMP_ROOT'])/'bin'), env['PATH']])
    return env

def run(command, work, log=None, timeout=None, extra=None):
    env = environment(work) | (extra or {})
    command = list(map(str, command))
    print('RUN', ' '.join(command), flush=True)
    start = time.perf_counter()
    if log:
        Path(log).parent.mkdir(parents=True, exist_ok=True)
        with Path(log).open('w', encoding='utf-8') as stream:
            result = subprocess.run(command, cwd=PROJECT, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
    else:
        result = subprocess.run(command, cwd=PROJECT, env=env, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'exit {result.returncode}: {command[0]}; log={log}')
    return time.perf_counter()-start

def dependencies(names, work):
    destinations = {'boost': PROJECT/'baselines/boost_math', 'gatd': PROJECT/'baselines/gatd',
                    'dai': work/'UncertainCore', 'bonchi': work/'bonchi_public', 'ukge': work/'UKGE_source'}
    for name in names:
        url, revision = PINNED[name]
        dest = destinations[name]
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['git', 'init', '-q', dest], check=True)
            subprocess.run(['git', '-C', dest, 'remote', 'add', 'origin', url], check=True)
        dirty = subprocess.check_output(['git', '-C', dest, 'status', '--porcelain'], text=True)
        if dirty:
            raise RuntimeError(f'dependency has local changes: {dest}')
        subprocess.run(['git', '-C', dest, 'fetch', '--depth', '1', 'origin', revision], check=True)
        subprocess.run(['git', '-C', dest, 'checkout', '--detach', revision], check=True)
        got = subprocess.check_output(['git', '-C', dest, 'rev-parse', 'HEAD'], text=True).strip()
        if got != revision:
            raise RuntimeError(f'{name}: wrong revision')

def download(url, path, expected=None, windows_text=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        partial = path.with_suffix(path.suffix+'.part')
        with urllib.request.urlopen(url, timeout=120) as source, partial.open('wb') as target:
            shutil.copyfileobj(source, target, 1024*1024)
        if path.suffix=='.zip' and not zipfile.is_zipfile(partial):
            raise RuntimeError('The upstream server did not return a ZIP archive: '+url)
        partial.replace(path)
    actual = digest(path)
    source_digest = actual
    if expected and actual != expected and windows_text:
        converted = path.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        if hashlib.sha256(converted).hexdigest() == expected:
            path.write_bytes(converted)
            actual = digest(path)
    if expected and actual != expected:
        raise RuntimeError(f'{path.name}: downloaded bytes differ from the paper snapshot')
    return {'url': url, 'path': str(path), 'download_sha256': source_digest,
            'sha256': actual, 'crlf_normalized': source_digest != actual, 'bytes': path.stat().st_size}

def fetch_data(names, work):
    raw = PROJECT/'data/study'
    raw.mkdir(parents=True, exist_ok=True)
    snap = 'https://snap.stanford.edu/data/'
    downloads = {
        'SupUser': (snap+'sx-superuser.txt.gz', raw/'sx-superuser.txt.gz', None),
        'Stack': (snap+'sx-stackoverflow.txt.gz', raw/'sx-stackoverflow.txt.gz', None),
        'Orkut': (snap+'bigdata/communities/com-orkut.ungraph.txt.gz', raw/'com-orkut.ungraph.txt.gz', None),
        'WebGoogle': (snap+'web-Google.txt.gz', raw/'web-Google.txt.gz', None),
        'CitPatents': (snap+'cit-Patents.txt.gz', raw/'cit-Patents.txt.gz', None),
        'HepPh': ('https://nrvis.com/download/data/dynamic/ca-cit-HepPh.zip', work/'hepph_events.zip', '79f9bc88cdd026a920094feddd7099e252665dd3ef402b904457f23cc8ffec69'),
        'WikiTalkFR': ('https://networks.skewed.de/net/wiki_talk/files/fr.csv.zip', work/'wiki_fr_events.zip', 'ea7c61caae34a2413922c1cd7882607aae9bca47996105b38b8c9b8f5310d9b2'),
        'Deli': ('https://networks.skewed.de/net/delicious/files/ti.csv.zip', work/'delicious_ti.zip', '04cccfe8f21cf370caa8d6deb1c691de952ed0087efbd256c16a225ae623fec8'),
    }
    ledger_path = work/'downloads.json'
    ledger = json.loads(ledger_path.read_text(encoding='utf-8')) if ledger_path.exists() else []
    for name in names:
        if name in downloads:
            ledger.append(download(*downloads[name]))
        elif name in ('Flickr', 'Twitter'):
            file = 'Flickr.txt' if name == 'Flickr' else 'twitter.txt'
            revision = PINNED['bonchi'][1]
            target = raw/file
            expected = None if name == 'Flickr' else '8fb6f798720ad7433e4350bc1b75f1f3119fb5e5422f5dff12d43b5b7f011e16'
            ledger.append(download(f'https://raw.githubusercontent.com/fgullo/uncertaincores/{revision}/data/{file}', target, expected))
        elif name == 'CN15kProjection':
            for file, expected in [('train.tsv', 'c21fe1092d9b944b7966ef3ad136efde46293e4ce9ea818724e6697c035b74e4'),
                                   ('val.tsv', '5b161efbf0db6a483e303347e751d67fa51b2977fbdc644d8dcec240e2f703cd'),
                                   ('test.tsv', '4f875542716964109b32ddf7c5cccb5c540408202c69538dc7267f72cf60eb77')]:
                url = f"https://raw.githubusercontent.com/stasl0217/UKGE/{PINNED['ukge'][1]}/data/cn15k/{file}"
                ledger.append(download(url, raw/'cn15k'/file, expected, windows_text=True))
        elif name in ('DBLP', 'BiomineDSAA'):
            archive = raw/'uncertainty_dsaa_data.zip'
            url = 'https://drive.usercontent.google.com/download?id=12sNW29Dpo68vqvIw7uJl16Byn0z_whIw&export=download&confirm=t'
            ledger.append(download(url, archive))
        else:
            raise ValueError(name)
        ledger_path.write_text(json.dumps(list({row['path']: row for row in ledger}.values()), indent=2)+'\n', encoding='utf-8')

def prepare(names, work):
    raw = PROJECT/'data/study'
    (PROJECT/'results').mkdir(exist_ok=True)
    sibling = ROOT/'study/paper1'
    (sibling/'data/bin').mkdir(parents=True, exist_ok=True)
    for name in names:
        if name == 'Stack' and not (PROJECT/'results/stack.wbin').exists():
            run([sys.executable, sibling/'code/prep_temporal.py', raw/'sx-stackoverflow.txt.gz', PROJECT/'results/stack.tbin'], work)
            run([sys.executable, CODE/'prep_wbin.py', PROJECT/'results/stack.tbin', PROJECT/'results/stack.wbin'], work)
        if name in ('Orkut', 'WebGoogle', 'CitPatents'):
            stem = {'Orkut': 'com-orkut.ungraph', 'WebGoogle': 'web-Google', 'CitPatents': 'cit-Patents'}[name]
            dest = sibling/'data/bin'/('com-orkut.bin' if name == 'Orkut' else stem+'.bin')
            if not dest.exists():
                run([sys.executable, sibling/'code/prep.py', raw/(stem+'.txt.gz'), dest], work)
    run([sys.executable, PROJECT/'paper/supplement/review4/artifact/prepare.py', *names], work)

def build(work):
    env = environment(work)
    if os.name != 'nt':
        raise RuntimeError('The historical benchmark harness requires Windows x64; see docs/REPRODUCE.md.')
    for key, file in [('CXX', Path(env['CXX'])), ('GMP_ROOT', Path(env['GMP_ROOT'])/'include/gmp.h'),
                      ('BOOST_MATH_INCLUDE', Path(env['BOOST_MATH_INCLUDE'])/'boost/math/special_functions/beta.hpp'),
                      ('DAI_SRC', Path(env['DAI_SRC'])/'graph.cpp')]:
        if not file.exists():
            raise RuntimeError(f'{key}: dependency missing at {file}; see docs/REPRODUCE.md')
    run([sys.executable, PROJECT/'paper/supplement/review4/artifact/artifact.py', 'cpu-build', '--work', work], work, work/'cpu-build.log')
    run([CODE/'build.bat', CODE/'verify_thresholds.cpp', CODE/'verify_thresholds.exe'], work, work/'strict-msvc-build.log')
    run([sys.executable, '-c', "import sys;sys.path.insert(0,'code/fair_study');import submission_mechanisms as s;s.build()"], work, work/'ablation-build.log')
    run([sys.executable, CODE/'review4_arithmetic/run.py', 'build'], work, work/'arithmetic-build.log')
    (PROJECT/'results/review4_arithmetic').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CODE/'verify_thresholds.exe', PROJECT/'results/review4_arithmetic/default_strict_verifier.exe')
    (PROJECT/'results/review4_arithmetic/strict-build.json').write_text(json.dumps({
        'binary_sha256': digest(CODE/'verify_thresholds.exe'),
        'source_sha256': digest(CODE/'verify_thresholds.cpp'),
        'header_sha256': digest(CODE/'verified_tail.hpp'), 'fp_flags': '/fp:strict'}, indent=2)+'\n', encoding='utf-8')
    run([sys.executable, CODE/'revisions/review4_service/build.py'], work, work/'service-build.log')
    record = {'platform': sys.platform, 'python': sys.version, 'compiler': env['CXX'],
              'binaries': {str(p.relative_to(ROOT)): digest(p) for p in PROJECT.rglob('*.exe') if 'baselines' not in p.parts}}
    (work/'build.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')

def build_gpu(work):
    folder = PROJECT/'baselines/gatd_win_matched'
    run([sys.executable, PROJECT/'paper/supplement/review4/artifact/artifact.py', 'gpu',
         PROJECT/'baselines/gatd', '--output', folder], work, work/'gpu-stage.log')
    run([folder/'build_windows.bat'], work, work/'gpu-build.log')

def smoke(work):
    status=work/'smoke-pass.json'
    status.write_text(json.dumps({'status':'running','driver_sha256':digest(__file__)}))
    try:
        run([sys.executable, PROJECT/'paper/supplement/review4/artifact/release_smoke.py', '--work', work, '--strict'], work, work/'smoke.log')
        run([sys.executable, CODE/'review4_arithmetic/run.py', 'endpoint', 'boundary'], work, work/'arithmetic.log')
        run([sys.executable, CODE/'revisions/review4_service/test_witness.py'], work, work/'service-witness.log')
        run([sys.executable, CODE/'revisions/review4_service/test_cache.py'], work, work/'service-cache.log')
    except Exception as error:
        status.write_text(json.dumps({'status':'failed','error':str(error),'driver_sha256':digest(__file__)}))
        raise
    (work/'smoke-pass.json').write_text(json.dumps({'status': 'pass', 'checks': ['10 exhaustive uncertain graphs, 9 inclusive confidences each',
        'UCEF at 1 and 3 workers, OptiUCF, direct author solvers, rank export', 'FMA and non-FMA checkers',
        '988 exact-rational endpoint enclosures', '14 exact boundary refinement queries',
        'UCEF witness mutation and stale-cache rejection'],
        'logs': ['smoke.log', 'arithmetic.log','service-witness.log','service-cache.log'],
        'driver_sha256':digest(__file__),'build_sha256': digest(work/'build.json')}, indent=2)+'\n', encoding='utf-8')

def benchmark(graph, out, work, rounds, threads, limit):
    if out.exists() and any(out.iterdir()):
        raise RuntimeError('Use an empty output directory; existing measurements are not overwritten.')
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(CODE/'fair_study'))
    os.environ.update(environment(work))
    import run_matched as matched
    ref, order = out/'reference.thr', out/'removals.bin'
    run([CODE/'uthr_native.exe', graph, 'frontier', '5', str(threads), '1', ref], work,
        out/'reference.log', extra={'UTHR_CERT_ORDER': str(order), 'OMP_NUM_THREADS': str(threads)})
    run([CODE/'verify_thresholds.exe', graph, ref, order, str(threads)], work, out/'verification.log')
    instrument = work/'submission_study/instrumented'
    if not (instrument/'uthr_study.exe').exists():
        raise FileNotFoundError(instrument/'uthr_study.exe')
    arms = ['shifted', 'ctd', 'ucef', 'opti', 'reset', 'no_shift', 'neither']
    rows = []
    for rep in range(rounds):
        pivot = rep % len(arms)
        for arm in arms[pivot:]+arms[:pivot]:
            target = out/f'{arm}-{rep+1}.thr'
            workers = 1 if arm == 'opti' else threads
            extra = {'OMP_NUM_THREADS': str(workers)}
            if arm == 'ucef':
                command = [work/'ucef.exe', graph, workers, target]
            elif arm == 'opti':
                command = [CODE/'opti_native.exe', graph, 'opti', '5', '1', '1', target]
            else:
                binary = instrument/'uthr_study.exe'
                command = [binary, graph, 'ctd' if arm == 'ctd' else 'frontier', '5', workers, '1', target]
                if arm in ('reset', 'neither'):
                    extra['UTHR_RESET_LEVEL'] = '1'
                if arm in ('no_shift', 'neither'):
                    extra['UTHR_NOLB'] = '1'
            row = {'arm': arm, 'rep': rep+1, 'workers': workers, 'status': 'ok', 'limit_s': limit,
                   'input_sha256': digest(graph), 'binary_sha256': digest(command[0])}
            try:
                row['wall_s'] = run([ROOT/'study/paper1/code/memcap2.exe', 32768, *command], work,
                                    out/f'{arm}-{rep+1}.log', limit, extra)
                row.update(matched.compare(ref, target))
                if row['max_abs'] > 1e-9:
                    raise ValueError(f'{arm} failed the threshold comparison: {row}')
                row['output_sha256'] = digest(target)
            except subprocess.TimeoutExpired:
                row.update(status='timeout', wall_s=limit)
            rows.append(row)
            (out/'runs.json').write_text(json.dumps(rows, indent=2)+'\n', encoding='utf-8')
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with (out/'runs.csv').open('w', newline='', encoding='utf-8') as stream:
        writer=csv.DictWriter(stream, fieldnames=fields);writer.writeheader();writer.writerows(rows)
    summary = {}
    for arm in arms:
        values=[r['wall_s'] for r in rows if r['arm']==arm and r['status']=='ok']
        summary[arm]={'completed': len(values), 'median_s': statistics.median(values) if values else None,
                      'min_s': min(values) if values else None, 'max_s': max(values) if values else None}
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    plot_benchmark(out)

def plot_benchmark(out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    summary=json.loads((out/'summary.json').read_text())
    completed=[(label,row) for label,row in summary.items() if row['completed']]
    fig,ax=plt.subplots(figsize=(6.5,2.9),constrained_layout=True)
    for i,(label,row) in enumerate(completed):
        ax.bar(i,row['median_s'],color='#006158' if label=='shifted' else '#647990',width=.65)
        ax.errorbar(i,row['median_s'],yerr=[[row['median_s']-row['min_s']],[row['max_s']-row['median_s']]],color='black',capsize=3)
    ax.set_xticks(range(len(completed)),[label for label,row in completed])
    ax.set_ylabel('Process wall time (s)')
    ax.spines[['top','right']].set_visible(False)
    fig.savefig(out/'comparison.pdf');fig.savefig(out/'comparison.png',dpi=160);plt.close(fig)

def figures(work):
    run([sys.executable, PROJECT/'paper/make_figures.py', ROOT/'recorded/results'], work, work/'figures.log')
    run([sys.executable, PROJECT/'paper/supplement/review4/figures.py', 'service', 'phases'], work, work/'review-figures.log')

def gpu_check(graph, reference, out, work):
    if out.exists() and any(out.iterdir()):
        raise RuntimeError('Use an empty GPU-check output directory.')
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0,str(CODE/'fair_study'))
    import run_matched
    binary=PROJECT/'baselines/gatd_win_matched/gatd.exe'
    target=out/'gpu.thr'
    elapsed=run([ROOT/'study/paper1/code/memcap2.exe',32768,binary,graph,0,32],work,out/'run.log',300,
                {'GATD_SPARSE_OUTPUT':str(target)})
    result=run_matched.compare(reference,target)
    result.update(wall_s=elapsed,input_sha256=digest(graph),reference_sha256=digest(reference),
                  binary_sha256=digest(binary),output_sha256=digest(target),
                  comparison='GPU numerical comparison; not a strict certificate',tolerance=1e-4)
    result['within_paper_gpu_tolerance']=result['max_abs']<=1e-4
    (out/'check.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    if not result['within_paper_gpu_tolerance']:
        raise RuntimeError('GPU output exceeds the paper comparison tolerance; inspect check.json')

def java_check(work):
    import numpy as np
    from fractions import Fraction
    sys.path.insert(0,str(CODE/'fair_study'))
    from test_boundary import oracle
    base=work/'bonchi_public'
    root=work/'java-check'
    root.mkdir(parents=True,exist_ok=True)
    dest=Path(tempfile.mkdtemp(prefix='run-',dir=root))
    stem='KEtaCores_DynamicProgramming_BigDecimals_IncrementalInitialEtaDegrees'
    sources=[base/(stem+'.java'),base/(stem+'_LB.java'),CODE/'fair_study/BonchiBoundOutput.java']
    subprocess.run(['javac','-d',str(dest),*map(str,sources)],check=True)
    component={(0,1):.75,(1,2):.75,(0,2):.75,(2,3):.625}
    edges={(u+offset,v+offset):p for offset in range(0,100,4) for (u,v),p in component.items()}
    thresholds,_=oracle(4,component)
    expected=[max([0]+[k for k in range(1,4) if thresholds[k][v]>=.5]) for v in range(4)]*25
    checks=[]
    for label,klass in [('DP',stem),('LB','BonchiBoundOutput')]:
        case=dest/label
        if (case/'output').exists():
            raise RuntimeError('Java check already ran; use a fresh --work directory.')
        case.mkdir(parents=True,exist_ok=True)
        (case/'graph.txt').write_text(''.join(f'{u} {v} {p}\n' for (u,v),p in edges.items()))
        table=case/'beta_function_values'
        table.mkdir(exist_ok=True)
        lines=[]
        for vertex in range(100):
            probabilities=[Fraction(p) for edge,p in edges.items() if vertex in edge]
            degree=len(probabilities);p=min(probabilities)
            for n in (degree,degree-1):
                tails=[sum(Fraction(math.comb(n,j))*p**j*(1-p)**(n-j) for j in range(k,n+1)) for k in range(degree+1)]
                lines.append(f'{vertex}\t{float(p)}\t{degree}\t'+'\t'.join(format(float(value),'.17g') for value in tails)+'\n')
        (table/'graph.txt_beta_matlab.txt_output').write_text(''.join(lines))
        with (case/'run.log').open('w',encoding='utf-8') as log:
            subprocess.run(['java','-Xmx1g','-XX:ActiveProcessorCount=1','-cp',str(dest),klass,'graph.txt','0.5','1'],
                           cwd=case,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
        outputs=list((case/'output').glob('*coreNumbers*'))
        if len(outputs)!=1:
            raise RuntimeError(f'{label}: expected one dense answer')
        pairs=np.loadtxt(outputs[0],dtype=np.int64,ndmin=2)
        pairs=pairs[np.argsort(pairs[:,0])]
        if pairs[:,0].tolist()!=list(range(100)) or pairs[:,1].tolist()!=expected:
            raise AssertionError((label,pairs.tolist(),expected))
        checks.append({'baseline':label,'vertices':100,'expected':expected,'source_sha256':digest(sources[0 if label=='DP' else 1]),'answer_sha256':digest(outputs[0])})
    (root/'checks.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, default=ROOT/'work')
    sub = parser.add_subparsers(dest='action', required=True)
    dep=sub.add_parser('dependencies');dep.add_argument('names', nargs='+', choices=PINNED)
    for action in ('fetch-data', 'prepare'):
        p=sub.add_parser(action);p.add_argument('graphs', nargs='+')
    for action in ('build', 'build-gpu', 'smoke', 'figures', 'java-check'):
        sub.add_parser(action)
    bench=sub.add_parser('benchmark')
    bench.add_argument('graph', type=Path);bench.add_argument('output', type=Path)
    bench.add_argument('--rounds', type=int, default=5);bench.add_argument('--threads', type=int, default=1)
    bench.add_argument('--limit', type=float, default=300)
    gpu=sub.add_parser('gpu-check')
    gpu.add_argument('graph',type=Path);gpu.add_argument('reference',type=Path);gpu.add_argument('output',type=Path)
    plot=sub.add_parser('plot');plot.add_argument('output',type=Path)
    args=parser.parse_args();work=args.work.resolve();work.mkdir(parents=True, exist_ok=True)
    if args.action=='dependencies':dependencies(args.names, work)
    elif args.action=='fetch-data':fetch_data(args.graphs, work)
    elif args.action=='prepare':prepare(args.graphs, work)
    elif args.action=='benchmark':benchmark(args.graph.resolve(), args.output.resolve(), work, args.rounds, args.threads, args.limit)
    elif args.action=='gpu-check':gpu_check(args.graph.resolve(),args.reference.resolve(),args.output.resolve(),work)
    elif args.action=='plot':plot_benchmark(args.output.resolve())
    else:globals()[args.action.replace('-', '_')](work)

if __name__=='__main__':
    main()
