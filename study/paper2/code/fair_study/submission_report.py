
import csv
import json
from collections import defaultdict
from statistics import median

import numpy as np

from run_queries import QUERIES
from submission_queries import OUT, WORK


def save_csv(name, rows):
    with (OUT/name).open('w', newline='') as f:
        keys = dict.fromkeys(k for row in rows for k in row)
        writer = csv.DictWriter(f, fieldnames=list(keys))
        writer.writeheader()
        writer.writerows(rows)


def query_report(series='queries'):
    extended = series == 'queries18'
    queries = QUERIES + ((.05,.95,.15,.85,.25,.75,.35,.65,.45) if extended else ())
    file_prefix = 'stack_query18_prefixes' if extended else 'stack_query_prefixes'
    groups = defaultdict(list)
    for p in sorted((OUT/series).glob('*/record.json')):
        r = json.loads(p.read_text())
        groups[r['method']].append(r)
    assert set(groups) == {'refined','topdown','bottomup'} and all(len(rs)==3 for rs in groups.values())
    for rs in groups.values():
        assert all(r['status']=='ok' and len(r['prefixes'])==len(queries) and sum(r['outside'])==0 for r in rs)
        assert len({tuple(r['hashes']) for r in rs}) == 1
    rows = []
    for i, eta in enumerate(queries):
        row = dict(prefix=i+1, eta=eta)
        for m, rs in groups.items():
            times=[r['prefixes'][i] for r in rs]
            row[m]=median(times)
            row[m+'_min'],row[m+'_max']=min(times),max(times)
        truth=np.fromfile(WORK/series/'1_refined'/f'result-{i}.bin','<i4')
        for m in ('bottomup','topdown'):
            alt=np.fromfile(WORK/series/f'1_{m}'/f'result-{i}.bin','<i4')
            row[m+'_diff']=int(np.count_nonzero(alt!=truth))
        rows.append(row)
    save_csv(file_prefix+'.csv',rows)
    cross=next((i+1 for i in range(len(rows)) if all(r['refined']<min(r['topdown'],r['bottomup']) for r in rows[i:])),None)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(6.9,3.7),layout='constrained')
    for m,label,style,marker in [('refined','Verified table incl. build','#11775e','o'),('topdown','Dai top-down','#9e4f16','s'),('bottomup','Dai bottom-up','#40638c','^')]:
        x=[r['prefix'] for r in rows]
        ax.plot(x,[r[m] for r in rows],label=label,c=style,marker=marker)
        ax.fill_between(x,[r[m+'_min'] for r in rows],[r[m+'_max'] for r in rows],color=style,alpha=.14)
    ax.set(yscale='log',xticks=([1,3,5,7,9,11,13,15,18] if extended else range(1,10)),xlabel='Distinct confidence queries',ylabel='Cumulative time (s, log scale)')
    ax.legend(frameon=False)
    ax.spines[['top','right']].set_visible(False)
    fig.savefig(OUT/(file_prefix+'.png'),dpi=190)
    plt.close(fig)

    text=[f'## Fixed-confidence queries on full Stack, {len(queries)} prefixes','',
          f'The three sessions per method produced {9*len(queries)} complete vertex vectors, each with 2,584,164 entries. All entries lie in the independently certified query enclosures. Within each method, each query produced byte-identical answers across the three sessions.',
          '', '| Queries | Confidence added | Build + verified index, s | Dai top-down, s | Dai bottom-up, s | Top-down / bottom-up disagreements with inclusive answers |',
          '|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        text.append(f"| {r['prefix']} | {r['eta']:g} | {r['refined']:.2f} | {r['topdown']:.2f} | {r['bottomup']:.2f} | {r['topdown_diff']} / {r['bottomup_diff']} |")
    text += ['', ('First sustained crossover at query '+str(cross)+'.') if cross else f'There is no sustained crossover against the faster direct method within these {len(queries)} measured prefixes.',
             'Medians include the build with witness, independent check and rank generation on the index side. Both direct algorithms reuse preparation within each session. The confidence sequence is fixed and these results apply to that sequence.',
             '', f'![Cumulative time, median and full range across three sessions]({file_prefix}.png)', '']
    by_rep = {m:{r['rep']:r['prefixes'] for r in rs} for m,rs in groups.items()}
    crossings = []
    for rep in (1,2,3):
        prefix = next((i+1 for i in range(len(queries)) if all(
            by_rep['refined'][rep][j] < min(by_rep['topdown'][rep][j],by_rep['bottomup'][rep][j])
            for j in range(i,len(queries)))), None)
        crossings.append(str(prefix) if prefix else 'beyond measured range')
    text += ['The first sustained crossover in each repetition was '+', '.join(crossings)+', respectively.','']
    return text


def mechanisms():
    records=defaultdict(list)
    for p in sorted((OUT/'mechanisms').glob('*.json')):
        r=json.loads(p.read_text())
        if 'arm' in r: records[r['graph'],r['arm']].append(r)
    all_rows=[]
    for (g,arm),rs in records.items():
        for r in rs:
            all_rows.append({k:v for k,v in r.items() if k!='work'} | r.get('work',{}))
    save_csv('mechanism_runs.csv',all_rows)
    text=['## Matched single-worker mechanism study','',
          'All times include full sparse binary output. DP counts cover recurrence cells in initialization and peeling. Calls and pairs count post-deletion vertex reevaluations. A pair is counted once for its vertex and level however often it is reevaluated. OptiUCF uses its own setup and truncated DP; its single DP count includes initial activation. Other preprocessing, heaps, bound evaluation, and binomial seed construction are charged in elapsed time.',
          '', '| Graph | Mode | Completed / attempted | Median s (range) | Sweep DP cells | Peel DP cells | OptiUCF DP cells | Repeat calls | Distinct vertex-level pairs |',
          '|---|---|---:|---|---:|---:|---:|---:|---:|']
    for g in sorted({g for g,a in records}):
        for arm in ('full','opti','no_shift','no_reuse'):
            rs=records[g,arm]
            assert rs and len({r['input_sha256'] for a in ('full','opti','no_shift','no_reuse') for r in records[g,a]})==1
            good=[r for r in rs if r['status']=='ok']
            if not good:
                text.append(f"| {g} | {arm} | 0 / {len(rs)} | {rs[0]['status']} ({rs[0]['seconds']:.1f} s) | — | — | — | — | — |")
                continue
            assert len(good)==3 and all(r['max_abs']<=1e-9 for r in good)
            assert all(r['work']==good[0]['work'] for r in good)
            t=[r['seconds'] for r in good]
            w=good[0]['work']
            cells=[format(w[k],',d') if k in w else '—' for k in ('sweep_cells','peel_cells','opti_dp_cells','repeat_calls','repeated_vertex_levels')]
            text.append(f"| {g} | {arm} | 3 / {len(rs)} | {median(t):.3f} ({min(t):.3f}–{max(t):.3f}) | "+' | '.join(cells)+' |')
    def seconds(graph, arm):
        return median(r['seconds'] for r in records[graph,arm] if r['status']=='ok')
    tw_ratio = seconds('Twitter','no_shift') / seconds('Twitter','full')
    hep_ratio = seconds('HepPh','no_reuse') / seconds('HepPh','full')
    web_ratio = seconds('WebGoogle','opti') / seconds('WebGoogle','full')
    text += ['', f'Disabling the deletion-shift lower bound increases median time by {tw_ratio:.2f}× on full Twitter; the full HepPh and Web-Google arms hit their 300 s limit under that ablation. On full HepPh resetting the sweep at every level increases time by {hep_ratio:.2f}× with exactly the same peel DP count. On Web-Google our single-worker solver beats the OptiUCF reconstruction by {web_ratio:.2f}×; the earlier 24-worker UCEF reconstruction remains faster than our 24-worker solver on this graph. On Twitter and Web-Google, OptiUCF performs fewer DP cell updates while taking longer overall. These timings cannot establish that fewer DP cell updates explain the difference between implementations.']
    return text+['','The quarter suffix indicates a distinct induced input with one quarter of the original vertices. Capped output is excluded from all accuracy and speed ratios. The instrumentation suite and frozen 24-worker headline runs are separate cohorts.','']


def certificates():
    rows=json.loads((OUT/'certificates/summary.json').read_text())
    pair=json.loads((OUT/'certificates/flickr_pair.json').read_text())
    lines=['## Independently checking a materialized table','',
           '| Graph | Values | Table MiB | Extra order MiB | Build with order, s | Verify, s | Build / verify peak MiB | Lower deficit / upper excess | Build / verify trials |',
           '|---|---:|---:|---:|---:|---:|---:|---|---:|']
    for r in rows:
        lines.append(f"| {r['graph']} | {r['values']:,} | {r['table_bytes']/2**20:.2f} | {r['extra_witness_bytes']/2**20:.2f} | {median(r['build_s']):.2f} | {median(r['verify_s']):.2f} | {max(r['build_peak_mib']):,} / {max(r['verify_peak_mib']):,} | {r['lower_deficit']:.3g} / {r['upper_excess']:.3g} | {len(r['build_s'])} / {len(r['verify_s'])} |")
    assert pair['actual_answers']['refined']==[1,1]
    lines += ['', 'Build includes graph reading, generation of all threshold rows and their removal orders. Verification starts a separate process, reads both files and the graph and computes a numerical enclosure for the stored edge probabilities. Medians are reported for elapsed time and maxima for measured peak committed memory. The order adds four bytes per eligible value and 12 bytes per level. Deli uses the one-level memory schedule and represents a single completed trial. The original 24-level build hit the host memory limit.',
              '', 'At confidence 0.5, Flickr CSR vertices 1986 and 1987 have exactly one neighbor each, one another, with edge probability exactly 0.5. Each has inclusive core number 1 by definition. Reading the point estimate returned 0 for each; boundary refinement and the author top-down algorithm both returned 1. Scripts rechecked both adjacency lists and the saved answer vectors.','']
    return lines


def main():
    lines=['# Submission experiments on all-level uncertain-core thresholds','',
           '[Protocol and reproduction](PROTOCOL.md) · [Earlier full-input comparisons](../literature_coverage/RESULTS.md)','']
    lines += ['## What the ablations test', '',
              'At a fixed level k, couple the Bernoulli edge trials before and after removing r neighbors of a vertex. In every outcome the remaining degree is at least the old degree minus r. Hence the old survival probability at k+r is a lower bound on the new survival probability at k. A stored offset greater than r gives a weaker valid bound. Recomputing the local distribution refreshes those entries. Across support-core levels, the cumulative survival sweep incorporates newly eligible neighbors while retaining the factors incorporated at higher levels.',
              '', 'The OptiUCF reconstruction uses the extreme remaining probabilities for beta-function bounds and the product of the top k remaining probabilities. The bounds have no universal ordering. For k=1, removing one certain edge while retaining probabilities 0.01, 0.99 and 0.99 leaves the old two-success tail at 0.999901, above the top-edge bound 0.99. With an old 0.1 edge removed and a single 0.8 edge retained, that shift bound is 0.08 while the top-edge bound is 0.8. These examples refer to the underlying mathematical bounds before the optional static core floor and numerical rounding. [Sun et al., Section 4.1](https://arxiv.org/html/2504.20795v1).','']
    lines += mechanisms()+certificates()+query_report()
    if len(list((OUT/'queries18').glob('*/record.json'))) == 9:
        lines += query_report('queries18')
    (OUT/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')
    print('Wrote',OUT/'RESULTS.md',flush=True)


if __name__=='__main__':
    main()
