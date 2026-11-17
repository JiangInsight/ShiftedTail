
import csv
import json
import re
import struct
from collections import Counter
import numpy as np
from study import HERE, OUT, GRAPH, SCRATCH, WORK, ROOT, sha, write

def rec(name):
    return json.loads((OUT/(name+'.json')).read_text())

def csvout(name, rows):
    with (OUT/(name+'.csv')).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)

def crossing(a,b):
    won=np.array(a)<np.array(b)
    first=next((i+1 for i,v in enumerate(won) if v),None)
    sustained=next((i+1 for i in range(len(won)) if np.all(won[i:])),None)
    return first,sustained

def prep_components(graph,method,rep):
    prefix=graph+'_'+('' if rep==1 else f'r{rep}_')
    parts={s:rec(prefix+method+'_'+s)['seconds'] for s in (('build','order','verify') if method=='ucef' else ('build','verify'))}
    parts.setdefault('order',0.)
    parts['verify']=rec(f'{graph}_r{rep}_{method}_verify_strict')['seconds']
    parts['rank']=rec(prefix+'rank')['seconds']
    return parts

def response_rows(prof,charges):
    center=float(np.median(charges))
    loaded_at=next((i for i,z in enumerate(prof['refinements']) if z[0]),None)
    for i,x in enumerate(prof['requests']):
        t=prof['prefixes'][i];stats=prof['refinements'][i] if prof['refinements'] else ['','','']
        yield dict(graph=prof['graph'],sequence=prof['tag'],method=prof['method'],prefix=i+1,eta=x,eta_hex=x.hex(),
                   preparation_s=center,preparation_min_s=min(charges),preparation_max_s=max(charges),
                   query_prefix_s=t,end_to_end_s=t+center,end_to_end_min_s=t+min(charges),end_to_end_max_s=t+max(charges),
                   driver_ready_s=prof['ready'],driver_answer_s=prof['answer_seconds'][i],lazy_graph_load=int(i==loaded_at),
                   undecided=stats[0],checks=stats[1],exact=stats[2],answer_sha256=prof['answer_sha256'][i])

def original_figure():
    if not all((OUT/f'{g}_r{r}_{m}_verify_strict.json').exists() for g in GRAPH for m in ('ucef','frontier') for r in (1,2,3)):
        raise SystemExit('Run study.py strict_verify before producing strict-release figure data.')
    rows=[]
    for graph in GRAPH:
        for method in ('ucef','frontier','topdown','bottomup'):
            if graph=='Stack' and method=='bottomup':continue
            charges=([sum(prep_components(graph,method,r).values()) for r in (1,2,3)] if method in ('ucef','frontier') else [0.])
            rows.extend(response_rows(rec(graph+'_original_'+method),charges))
    with (SCRATCH/'final_original.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    stages=[];prefixes=[];cross=[];correct=[];provenance={};repeated=[];legacy=[];old_checks=[];leaf_examples=[];controls=[];tables=[];verifiers=[]
    fallback=HERE/'legacy_direct.csv'
    evidence={}
    if fallback.exists():
        with fallback.open(newline='') as f:
            evidence={(r['graph'],r['method'],int(r['rep']),int(r['prefix'])):r for r in csv.DictReader(f)}
    for graph,graphfile in GRAPH.items():
        d=SCRATCH/graph
        with graphfile.open('rb') as f:
            n,arcs=struct.unpack('<IQ',f.read(12))
            degree=np.fromfile(f,'<u4',n)
        off=np.concatenate(([0],np.cumsum(degree,dtype=np.int64)))
        probabilities=np.memmap(graphfile,mode='r',dtype='<f8',offset=12+4*n+4*arcs,shape=(arcs,))
        neighbors=np.memmap(graphfile,mode='r',dtype='<u4',offset=12+4*n,shape=(arcs,))
        for label,stage in [('threshold / rank order',graph+'_rank_tie_control'),('tie-aware postprocessor',graph+'_r1_ucef_verify_strict')]:
            marker=re.search(r'^certificate (.+)$',(OUT/(stage+'.log')).read_text(),re.M)
            assert marker
            controls.append(dict(graph=graph,witness=label,verifier_exit=rec(stage)['rc'],
                                 **dict(v.split('=') for v in marker.group(1).split())))
        setup={};observed_charges={}
        for method in ('ucef','frontier'):
            charges={'build':rec(graph+'_'+method+'_build')['seconds'],
                     'order':rec(graph+'_ucef_order')['seconds'] if method=='ucef' else 0.,
                     'verify':rec(graph+'_'+method+'_verify')['seconds'],
                     'rank':rec(graph+'_rank')['seconds']}
            observed_charges[method]=[]
            for rep in (1,2,3):
                parts=prep_components(graph,method,rep)
                total=sum(parts.values());observed_charges[method].append(total)
                repeated.append(dict(graph=graph,producer=method,rep=rep,**parts,total=total))
                for version,label in [('historical',graph+'_'+('' if rep==1 else f'r{rep}_')+method+'_verify'),
                                      ('strict-release',f'{graph}_r{rep}_{method}_verify_strict')]:
                    meta=rec(label);log=(OUT/(label+'.log')).read_text()
                    bounds=dict(z.split('=') for z in re.search(r'^certificate (.+)$',log,re.M).group(1).split())
                    verifiers.append(dict(graph=graph,producer=method,rep=rep,checker=version,
                                          seconds=meta['seconds'],binary_sha256=meta['binary_sha256'],exit=meta['rc'],**bounds))
            setup[method]=float(np.median(observed_charges[method]))
            final=(OUT/f'{graph}_r1_{method}_verify_strict.log').read_text()
            cert=re.search(r'^certificate (.+)$',final,re.M)
            assert cert and rec(f'{graph}_r1_{method}_verify_strict')['rc']==0
            c=dict(v.split('=') for v in cert.group(1).split())
            for rep in (2,3):
                text=(OUT/f'{graph}_r{rep}_{method}_verify_strict.log').read_text()
                same=re.search(r'^certificate (.+)$',text,re.M)
                assert same and dict(v.split('=') for v in same.group(1).split())==c
            peak={}
            for s in ('build','order','verify','rank'):
                p=(OUT/(f'{graph}_{method}_{s}.log' if s!='rank' else graph+'_rank.log'))
                if s=='verify':p=OUT/f'{graph}_r1_{method}_verify_strict.log'
                peak[s+'_peak_MiB']=int(re.search(r'peak_mb=(\d+) exit=0',p.read_text()).group(1)) if p.exists() else 0
            stages.append(dict(graph=graph,producer=method,**{s:float(np.median([r[s] for r in repeated if r['graph']==graph and r['producer']==method])) for s in charges},
                               charged_seconds=setup[method],prep_min_s=min(observed_charges[method]),prep_max_s=max(observed_charges[method]),**peak,**c,
                               values_bytes=(d/(method+'.thr')).stat().st_size,order_bytes=(d/(method+'.ord')).stat().st_size))
        provenance[graph]={str(p.name):sha(p) for p in [graphfile,d/'rank',d/'ucef.thr',d/'ucef.ord',d/'frontier.thr',d/'frontier.ord']}
        count=different=0;maximum=0.
        with (d/'ucef.thr').open('rb') as uf,(d/'frontier.thr').open('rb') as ff:
            while head:=uf.read(12):
                assert ff.read(12)==head
                _,nrow=struct.unpack('<IQ',head)
                x=np.fromfile(uf,'<f8',nrow);y=np.fromfile(ff,'<f8',nrow)
                count+=nrow
                different+=int(np.count_nonzero(x.view('<u8')!=y.view('<u8')))
                maximum=max(maximum,float(np.max(np.abs(x-y))))
            assert not ff.read(1)
        tables.append(dict(graph=graph,entries=count,different_binary64_entries=different,max_absolute_difference=maximum,
                           ucef_sha256=provenance[graph]['ucef.thr'],frontier_sha256=provenance[graph]['frontier.thr']))
        for tag,requests in rec(graph+'_manifest').items():
            q=requests['requests'];t={};profs={}
            methods=['frontier','ucef','topdown']
            if graph=='WebGoogle' or tag=='uniform':methods.append('bottomup')
            for method in methods:
                prof=rec('_'.join([graph,tag,method]));profs[method]=prof
                assert prof['requests']==q and prof['rc']==0
                t[method]=[x+setup.get(method,0) for x in prof['prefixes']]
                prefixes.extend(response_rows(prof,observed_charges.get(method,[0.])))
            assert profs['ucef']['answer_sha256']==profs['frontier']['answer_sha256']
            diff={}
            for method in methods[2:]:
                errors=[]
                for i in range(len(q)):
                    if profs[method]['answer_sha256'][i]==profs['ucef']['answer_sha256'][i]:errors.append(0)
                    else:
                        direct=np.fromfile(d/tag/method/f'ans-{i}.bin','<i4')
                        exact=np.fromfile(d/tag/'ucef'/f'ans-{i}.bin','<i4')
                        errors.append(int(np.count_nonzero(direct!=exact)))
                        witness=np.flatnonzero((direct!=exact)&(degree==1))
                        if witness.size:
                            v=int(witness[0]);pos=int(off[v]);p=float(probabilities[pos])


                            assert int(exact[v])==int(p>=q[i])
                            leaf_examples.append(dict(graph=graph,sequence=tag,method=method,query=i+1,
                              eta=q[i].hex(),vertex=v,neighbor=int(neighbors[pos]),probability=p.hex(),
                              inclusive=int(exact[v]),direct=int(direct[v]),differing_degree_one_vertices=int(witness.size)))
                    correct.append(dict(graph=graph,sequence=tag,method=method,prefix=i+1,differing_vertices=errors[-1]))
                diff[method]=errors
            for method in ('ucef','frontier'):
                for direct in methods[2:]:
                    first,sustained=crossing(t[method],t[direct])
                    spread=[crossing([z+cost for z in profs[method]['prefixes']],t[direct]) for cost in observed_charges[method]]
                    cross.append(dict(graph=graph,sequence=tag,index=method,direct=direct,horizon=len(q),
                                      first_cross=first,sustained_cross=sustained,index_total_s=t[method][-1],direct_total_s=t[direct][-1],
                                      first_by_prep_rep='|'.join(str(x[0] or '-') for x in spread),
                                      sustained_by_prep_rep='|'.join(str(x[1] or '-') for x in spread),
                                      direct_queries_with_disagreement=sum(x>0 for x in diff[direct]),
                                      direct_vertex_answers_differing=sum(diff[direct])))
            if tag=='original':

                for direct in ('topdown','bottomup'):
                    archive_runs=[]
                    for rep in (1,2,3):
                        case=(WORK/'literature_coverage/WebGoogle'/f'query_{rep}_{direct}' if graph=='WebGoogle' else
                              WORK/'submission_study/queries18'/f'{rep}_{direct}')
                        raw=(ROOT/'results/literature_coverage/queries'/f'WebGoogle_{rep}_{direct}' if graph=='WebGoogle' else
                             ROOT/'results/submission_study/queries18'/f'{rep}_{direct}')
                        local=case.is_dir() and (raw/'query.log').is_file()
                        if local:
                            lines=[l.split() for l in (raw/'query.log').read_text().splitlines() if l.startswith('ANSWER ')]
                            assert [float(l[2]) for l in lines]==q
                            series=[float(l[4]) for l in lines]
                            log_sha=sha(raw/'query.log')
                        else:
                            series=[float(evidence[graph,direct,rep,i+1]['direct_prefix_s']) for i in range(len(q))]
                        archive_runs.append(series)
                        for i in range(len(q)):
                            p=case/f'result-{i}.bin'
                            if local:
                                value=sha(p)
                            else:
                                old=evidence[graph,direct,rep,i+1]
                                value=old['reference_sha256']
                                log_sha=old['direct_log_sha256']
                            assert value==profs['ucef']['answer_sha256'][i],f'original answer disagrees {p}'
                            old_checks.append(dict(graph=graph,method=direct,rep=rep,prefix=i+1,eta=q[i],
                                                   direct_prefix_s=series[i],reference_sha256=value,
                                                   historical_answer_path=str(p),direct_log_sha256=log_sha,
                                                   validation_source='historical answer file' if local else 'shipped historical answer digest'))
                    direct_prefix=np.median(np.array(archive_runs),axis=0)
                    for producer in ('ucef','frontier'):
                        idx=[setup[producer]+s for s in profs[producer]['internal_prefixes']]
                        first,sustained=crossing(idx,direct_prefix)
                        legacy.append(dict(graph=graph,index=producer,direct=direct,first=first,sustained=sustained,
                                           index_last_s=idx[-1],direct_last_s=direct_prefix[-1],
                                           clock='query driver entry; preparatory stages external; historical direct prefixwise median (three runs)'))
    csvout('stages',stages);csvout('prep_repetitions',repeated);csvout('prefixes',prefixes);csvout('crossings',cross);csvout('direct_validation',correct)
    csvout('archived_original_comparison',legacy);csvout('archived_original_validation',old_checks)
    distribution=[]
    for g,fast in (('WebGoogle','bottomup'),('Stack','topdown')):
        for m in ('ucef','frontier'):
            curves=[r for r in cross if r['graph']==g and r['index']==m and r['direct']==fast]
            for filt,selected in [('all measured timing curves',curves),('all responses equal',[r for r in curves if not r['direct_queries_with_disagreement']])]:
                for mode in ('first_cross','sustained_cross'):
                    bins=Counter(str(r[mode] if r[mode] is not None else 'none') for r in selected)
                    distribution.append(dict(graph=g,index=m,direct=fast,scope=filt,endpoint=mode,
                                             sequences=len(selected),no_cross=bins['none'],histogram=json.dumps(bins,sort_keys=True)))
    csvout('crossover_distribution',distribution)
    csvout('witness_controls',controls)
    csvout('table_comparison',tables)
    csvout('verifier_versions',verifiers)
    write(OUT/'artifact_hashes.json',provenance)
    write(OUT/'degree_one_disagreements.json',leaf_examples)

if __name__=='__main__':
    import sys
    if '--original-figure' in sys.argv:original_figure()
    else:main()
