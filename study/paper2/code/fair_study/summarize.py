
import csv
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from run_matched import ART, FULL, ROOT, SEEDS
from run_queries import QUERIES
BASE=ROOT/'results/fair_study'
median=st.median


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def table(name,rows):
    with (BASE/(name+'.csv')).open('w',newline='',encoding='utf-8') as f:
        wr=csv.DictWriter(f,fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)


def line(*items):return '| '+' | '.join(map(str,items))+' |'
def grid(headers,rows):return '\n'.join([line(*headers),line(*['---']*len(headers)),*[line(*r) for r in rows]])


def main():
    cases={f.parent.name:read(f) for f in ART.glob('*/input.json')}
    groups=defaultdict(list)
    for folder in ('matched','extension'):
        for f in (BASE/folder).glob('*/record.json'):
            r=read(f)
            if 'arm' in r: groups[r['input'],r['arm'],r['workers']].append(r)
    assert len(cases)==38
    required={(tag,arm,24):3 for tag in cases for arm in ('cpu','gpu')}
    required.update({(tag,'reference',24):1 for tag in cases})
    required['flickr_constant','general',24]=3
    for g in FULL[:2]:
        for a,t in [('cpu',1),('ctd',1),('opti',1),('ctd',24)]:required[g.lower()+'_full',a,t]=3
    for key,n in required.items():
        assert sorted(r['rep'] for r in groups[key])==([0] if key[1]=='reference' else list(range(1,n+1))),key
        if key[1]=='reference':assert groups[key][0]['status']=='ok',key
    for graph in FULL:
        for t in ((1,24) if graph in ('Flickr','SupUser','DBLP') else (24,)):
            runs=sorted(groups[graph.lower()+'_full','ucef',t],key=lambda r:r['rep'])
            assert runs and (len(runs)==3 or runs[-1]['status']!='ok')
    summary=[]
    for (tag,arm,t),rs in sorted(groups.items()):
        rs.sort(key=lambda x:x['rep'])
        assert all(r['input_sha256']==cases[tag]['binary_sha256'] for r in rs)
        good=[r for r in rs if r['status']=='ok']
        times=[r['process_wall_s'] for r in good]
        if arm!='reference':
            for r in good:
                assert r['output_bytes']==groups[tag,'reference',24][0]['output_bytes']
                assert r['max_abs']<=(1e-4 if arm=='gpu' else 1e-9)
        summary.append(dict(case=tag,method=arm,threads=t,trials=len(rs),ok=len(good),
                            status='/'.join(r['status'] for r in rs),median_s=median(times) if times else '',min_s=min(times,default=''),max_s=max(times,default=''),
                            max_error=max((r['max_abs'] for r in good if 'max_abs' in r),default=''),output_bytes=next((r['output_bytes'] for r in good),''),
                            max_count_above_1e6=max((r['above_1e6'] for r in good if 'above_1e6' in r),default=''),
                            max_count_above_1e5=max((r['above_1e5'] for r in good if 'above_1e5' in r),default=''),
                            worst_6dp_fraction=min((r['match6'] for r in good if 'match6' in r),default='')))
    table('all_arms',summary)
    keyed={(r['case'],r['method'],r['threads']):r for r in summary}
    rows=[]
    for tag,inp in sorted(cases.items()):
        cpu=keyed[tag,'cpu',24];gpu=keyed[tag,'gpu',24]
        ok=cpu['ok']==gpu['ok']==3
        ref=groups[tag,'reference',24][0]
        pairs=[b['process_wall_s']/a['process_wall_s'] for a,b in zip(groups[tag,'cpu',24],groups[tag,'gpu',24])] if ok else []
        rows.append(dict(case=tag,graph=inp['graph'],kind=inp['kind'],seed=inp['seed'],percent=inp['percent'],vertices=inp['n'],edges=inp['edges'],
                         values=int(ref['fields']['thresholds']),output_bytes=ref['output_bytes'],
                         cpu_median_s=cpu['median_s'],gpu_median_s=gpu['median_s'],ratio=median(pairs) if ok else '',
                         pair_min=min(pairs,default=''),pair_max=max(pairs,default=''),gpu_status=gpu['status'],
                         gpu_max_error=gpu['max_error'],cpu_evals=ref['fields'].get('evals',''),cpu_dp_cells=ref['fields'].get('cells','')))
    table('matched_cases',rows)
    inputs=[dict(cases[tag]) for tag in sorted(cases)];(BASE/'matched_inputs.json').write_text(json.dumps(inputs,indent=2))
    direct=[read(f) for f in (BASE/'query').glob('*/record.json')]
    refined=[read(f) for f in (BASE/'extension').glob('*refined/record.json')]
    assert len(direct)==36 and len(refined)==12 and all(x['status']=='ok' for x in direct+refined)
    assert not any(sum(r['outside_enclosure']) for r in direct)
    by_work=defaultdict(list)
    for r in direct+refined:by_work[r['graph'],r['workers'],r['method']].append(r)
    workloads=[];comparison=[]
    for g in FULL[:2]:
        strings={tuple(r['answer_sha256']) for r in refined if r['graph']==g}
        assert len(strings)==1
        for t in (1,24):
            cross=[]
            for i,q in enumerate(QUERIES):
                record=dict(graph=g,threads=t,queries=i+1,last_eta=q)
                for m in ('topdown','bottomup','refined'):
                    cohort=by_work[g,t,m]
                    prefixes=[r['prefix_s'][i]+r.get('build_s',0) for r in cohort]
                    record[m+'_s']=median(prefixes)
                    record[m+'_min_s']=min(prefixes);record[m+'_max_s']=max(prefixes)
                rr=by_work[g,t,'refined']
                record['prebuilt_s']=median(r['prefix_s'][i] for r in rr)
                for m in ('topdown','bottomup','index'):
                    record[m+'_max_different_vertices']=max(r['disagreements'][m][i] for r in rr)
                record['ambiguous_vertex_levels']=rr[0]['refinements'][i][0]
                record['gmp_calls']=rr[0]['refinements'][i][2]
                workloads.append(record)
                cross.append(record['refined_s']<min(record['topdown_s'],record['bottomup_s']))
            stable=next((j+1 for j in range(9) if all(cross[j:])),None)
            end=workloads[-1]
            comparison.append([g,t,f"{median(r['build_s'] for r in rr):.3f}",f"{end['refined_s']:.3f}",
                               f"{end['topdown_s']:.3f}",f"{end['bottomup_s']:.3f}",stable or 'beyond measured range'])
    table('query_prefixes',workloads)
    mainrows=[]
    for g in FULL:
        r=next(row for row in rows if row['case']==g.lower()+'_full')
        fmt=lambda v: f'{v:.3f}' if isinstance(v,(float,int)) else 'unvalidated'
        mainrows.append([g,f"{r['values']:,}",fmt(r['cpu_median_s']),fmt(r['gpu_median_s']),fmt(r['ratio']),f"{r['gpu_max_error']:.2g}" if r['gpu_max_error']!='' else '—'])
    sf=[]
    for g in FULL[:2]:
        for percent in (20,40,60,80,100):
            rs=[r for r in rows if r['graph']==g and r['kind'] in ('scale','full') and r['percent']==percent]
            ratios=[r['ratio'] for r in rs if r['ratio']!='']
            sf.append(dict(graph=g,percent=percent,validated=len(ratios),instances=len(rs),cpu_s=median(r['cpu_median_s'] for r in rs if r['cpu_median_s']!=''),
                           gpu_s=median([r['gpu_median_s'] for r in rs if r['gpu_median_s']!='']) if ratios else '',ratio=median(ratios) if ratios else '',
                           min_ratio=min(ratios,default=''),max_ratio=max(ratios,default='')))
    table('scaling',sf)
    sens=[r for r in rows if r['graph']=='Flickr' and r['kind']!='scale']
    table('probability_sensitivity',sens)
    def sec(row):
        return ('%.3f'%row['median_s']) if row['ok']==row['trials'] and row['ok'] else row['status']
    base_rows=[[g,t,*(sec(keyed[g.lower()+'_full',m,t]) if (g.lower()+'_full',m,t) in keyed else '—' for m in ('cpu','ctd','opti','ucef'))] for g in FULL for t in ((1,24) if g in ('Flickr','SupUser','DBLP') else (24,))]
    plot(sf,workloads)
    tests=read(BASE/'extension/exhaustive.json')
    assert len(tests)==10 and sum(r[2] for case in tests for r in case['checks'])>0
    md=['# All-level decomposition and the cost of repeated confidence queries','',
        'Same machine, Intel Core Ultra 9 275HX and RTX 5080 Laptop 16 GB. The full output contains one threshold per eligible vertex and support-core level. Both solvers read the same graph with probabilities representable exactly in binary32, then close identically sized binary64 row files. The native arithmetic differs. Time is wall time from process launch through exit, including graph loading, transfers, and output. Files use ordinary OS caching. Each time is the median of three trials. The ratio is the median of three paired GPU/CPU ratios. Only validated outputs enter a ratio. Independent offline checks are outside both full-decomposition timings.',
        '',grid(['Full graph','Thresholds','CPU 24 (s)','Gatd (s)','Paired ratio','GPU max absolute difference'],mainrows),'',
        'Orkut has constant edge probability and uses a binomial shortcut. Its speedup has a separate interpretation. SupUser and Stack derive edge probabilities from event counts. The provenance and input hashes are in [the original manifest](../study/input_manifest.json) and [the matched manifest](matched_inputs.json). The 56 earlier GPU trials used a different output policy and form a separate series.',
        '','## All-level CPU comparisons','',grid(['Graph','Threads','Proposed (s)','CTD (s)','OptiUCF (s)','UCEF (s)'],base_rows),'',
        'CTD is a shared-code recomputation baseline. OptiUCF and the threshold stage of UCEF are independent reconstructions. The one-thread UCEF uses the published active vertex sweeps and previous-level initialization. Its 24-thread entry is our level-parallel adaptation. A timeout denotes the 300 s cap on UCEF. The sparse row output contains no connectivity trees. [Wen et al.](https://ronghuali.github.io/PaperFiles/Computing%20K-Cores%20in%20Large%20Uncertain%20Graphs%20An%20Index-based%20Optimal%20Approach.pdf) · [Sun et al.](https://arxiv.org/abs/2504.20795)',
        '', 'The UCEF reconstruction changes the CPU comparison. On Stack the medians are '+sec(keyed['stack_full','cpu',24])+' s for the proposed solver and '+sec(keyed['stack_full','ucef',24])+' s for parallel UCEF. UCEF has a lower median on SupUser and DBLP. The Biomine ranges overlap; its small difference in medians does not establish a stable advantage. This bounds the speed claim to particular graphs and competing implementations.',
        '','## Graph size and edge-probability distribution','',
        'The nested induced samples follow the size fractions in the Gatd study, with three sampled vertex orders and one shared 100% endpoint per graph. [Chen et al., PVLDB](https://www.vldb.org/pvldb/vol19/p2591-gao.pdf). The [scaling table](scaling.csv) gives median time and the range of the paired ratios across input seeds. Three timings on the same sample measure timing spread. Different graph samples measure a different source of variation.',
        '',grid(['Flickr weights','Instances','CPU seconds, range of medians','Gatd seconds, range of medians','Validated ratios'],[sens_row(sens,k) for k in ('full','constant','narrow','shuffled','uniform')]),'',
        'The constant-weight control with the general solver forced takes '+sec(keyed['flickr_constant','general',24])+' s. [Per-instance weights and operation counts](probability_sensitivity.csv).',
        '','## Repeated confidence queries','',
        'This question asks for a dense core-number vector for each confidence. The author implementations of Dai et al. load and sort the original binary64 graph once per session. The index side pays for the full build, independent verification and rank generation at the same thread count, then reads the table, resolves ambiguous membership, and closes each answer file. The prefix clock begins inside the common query driver on all methods. The construction stages additionally include external process overhead. A prebuilt query time still includes loading the index and any lazy graph read. Nine distinct binary64 confidence values are used in the fixed order in the protocol. [Dai et al., TKDE](https://ronghuali.github.io/PaperFiles/Core%20Decomposition%20on%20Uncertain%20Graphs%20Revisited.pdf) · [Author implementation](https://github.com/qq-dai/UncertainCore).',
        '',grid(['Graph','Threads','Build+verify+rank (s)','Indexed 9 (s)','Top-down 9 (s)','Bottom-up 9 (s)','First prefix faster through query 9'],comparison),'',
        'The crossover compares medians against the faster direct method at each prefix. [All prefixes, timing spread, exact-boundary work and per-query integer disagreements](query_prefixes.csv). Upstream Dai code uses native comparison margins (including 1e-16). The direct timings describe that original numerical policy; the indexed workload uses exact inclusive comparisons on binary64 inputs for ambiguous memberships. Record their integer disagreement counts rather than asserting equal accuracy. The bounded numerical thresholds alone allow integer ambiguities. The refined outputs agree across all six runs per graph. Exhaustive exact rational subset enumeration also checked 90 query vectors and all UCEF thresholds on ten small graphs, including exact and adjacent binary64 confidence values.',
        '', 'Flickr contains an independently checkable equality. In the stored CSR, vertices 1986 and 1987 form an isolated pair with edge probability exactly 0.5. At confidence 0.5 each has core number 1. The pilot point lookup returned 0 for both, while the refined lookup and the author top-down implementation return 1. This example explains why endpoint handling changes integer answers even when threshold errors are tiny.',
        '','## Scope for submission','',
        'The decomposition comparison supports an all-level CPU algorithm against the local corrected GPU implementation on these inputs. The repeated-query comparison tests when investing in that computation pays off. Indexing all confidence levels was already introduced in [Yang et al., ICDE](https://ronghuali.github.io/PaperFiles/Index-Based%20Optimal%20Algorithm%20for%20Computing%20K-Cores%20in%20Large%20Uncertain%20Graphs.pdf). The paper needs to identify the new threshold-computation mechanism, prove it, and use its ablations to attribute gains. ImpliCert studies maintenance after edge updates for clique density. This study has fixed inputs, independent probabilistic edges and all-level outputs.',
        '', 'The six full inputs, one CPU/GPU pair and two query graphs bound generalization. Gatd’s specialized Galois/Julienne implementations have no same-host measurements here. UCEF ran on every full graph at 24 threads; CTD and OptiUCF have fewer matched full-graph timings. The three largest UCEF arms were added after inspecting the first three graphs. Standalone timing does not establish equivalence to the upstream authors’ entire index or external-memory implementations. Paper acceptance also depends on the novelty argument and presentation.',
        '', '[Raw arm summaries with minima, maxima, precision and status](all_arms.csv) · [Matched case records](matched_cases.csv) · [Protocol](PROTOCOL.md) · [Figure](scaling_queries.png).']
    (BASE/'RESULTS.md').write_text('\n'.join(md)+'\n',encoding='utf-8')


def sens_row(rows,kind):
    group=[r for r in rows if r['kind']==kind]
    def rng(field):
        xs=[r[field] for r in group if r[field]!='']
        if not xs:return 'unvalidated'
        return f'{min(xs):.3f}' if len(xs)==1 else f'{min(xs):.3f}–{max(xs):.3f}'
    return [kind,len(group),rng('cpu_median_s'),rng('gpu_median_s'),rng('ratio')]


def plot(scale,work):
    fig,axs=plt.subplots(2,2,figsize=(8.5,5.8),constrained_layout=True)
    for j,g in enumerate(FULL[:2]):
        ax=axs[0,j];ss=[r for r in scale if r['graph']==g]
        for field,label,color in [('cpu_s','CPU, 24 threads','#126c67'),('gpu_s','Gatd, GPU','#ac4a22')]:
            valid=[r for r in ss if r[field]!='']
            ax.plot([r['percent'] for r in valid],[r[field] for r in valid],marker='o',label=label,color=color)
        ax.set(yscale='log',xlabel='Vertices retained (%)',ylabel='Full output (s)',title=g)
        ax=axs[1,j];ww=[r for r in work if r['graph']==g and r['threads']==24]
        for field,label,color in [('refined_s','Verified index, incl. build','#126c67'),('topdown_s','Dai top-down','#ac4a22'),('bottomup_s','Dai bottom-up','#635195')]:
            ax.plot([r['queries'] for r in ww],[r[field] for r in ww],marker='.',label=label,color=color)
        ax.set(xlabel='Completed confidence queries',ylabel='Cumulative time (s)',xticks=[1,3,5,7,9])
    for ax in axs.flat:
        ax.spines[['right','top']].set_visible(False)
        ax.legend(fontsize=8,frameon=False)
        ax.grid(axis='y',alpha=.18)
    fig.savefig(BASE/'scaling_queries.png',dpi=190)
    plt.close(fig)


if __name__=='__main__':main()
