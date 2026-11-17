
import csv
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from statistics import median

def check(directory):
    def rows(name):
        with (directory/name).open(newline='') as f:return list(csv.DictReader(f))
    def crossed(a,b):
        wins=[x<y for x,y in zip(a,b)]
        first=next((str(i+1) for i,w in enumerate(wins) if w),'')
        sustained=next((str(i+1) for i,w in enumerate(wins) if all(wins[i:])),'')
        return first,sustained
    with zipfile.ZipFile(directory/'reproduction.zip') as z:
        hashes=json.loads(z.read('source_hashes.json'))
        for name,digest in hashes.items():
            assert hashlib.sha256(z.read(name)).hexdigest()==digest,name
    totals={}
    with zipfile.ZipFile(directory/'raw_records.zip') as z:
        def raw(name):return json.loads(z.read('review4_service/'+name+'.json'))
        for line in rows('prep_repetitions.csv'):
            g,m,r=line['graph'],line['producer'],int(line['rep'])
            rp='' if r==1 else f'r{r}_'
            seconds=[]
            for s in ('build','order','verify','rank'):
                if s=='order' and m=='frontier':
                    assert float(line[s])==0;continue
                name=g+'_'+rp+(m+'_' if s!='rank' else '')+s
                if s=='verify':name=f'{g}_r{r}_{m}_verify_strict'
                meta=raw(name);assert meta['rc']==0
                if s=='verify':assert meta['binary_sha256']=='c1061ff07d7a8d13c3d2ddc3f8afdfd3f2c531dc7e818f5abe7b58d88054e8dc'
                assert float(line[s])==meta['seconds']
                seconds.append(meta['seconds'])
            assert abs(sum(seconds)-float(line['total']))<1e-10
            totals.setdefault((g,m),[]).append(float(line['total']))
        assert all(len(x)==3 for x in totals.values()) and len(totals)==4
        for line in rows('stages.csv'):
            assert float(line['charged_seconds'])==median(totals[line['graph'],line['producer']])
            log=z.read('review4_service/'+line['graph']+'_r1_'+line['producer']+'_verify_strict.log').decode()
            marker=re.search(r'^certificate (.+)$',log,re.M)
            actual=dict(entry.split('=') for entry in marker.group(1).split())
            assert all(line[field]==value for field,value in actual.items())
            assert max(float(line['max_lower_deficit']),float(line['max_upper_excess']))<=1e-9
        for item in rows('witness_controls.csv'):
            tag='rank_tie_control' if item['witness']=='threshold / rank order' else 'r1_ucef_verify_strict'
            assert int(item['verifier_exit'])==raw(item['graph']+'_'+tag)['rc']
        by_query={}
        for line in rows('direct_validation.csv'):
            key=line['graph'],line['sequence'],line['method']
            by_query.setdefault(key,[]).append(int(line['differing_vertices']))
        for line in rows('crossings.csv'):
            g,s,idx,d=line['graph'],line['sequence'],line['index'],line['direct']
            a=raw(f'{g}_{s}_{idx}');b=raw(f'{g}_{s}_{d}');other='frontier' if idx=='ucef' else 'ucef'
            assert a['answer_sha256']==raw(f'{g}_{s}_{other}')['answer_sha256']
            h=9 if g=='WebGoogle' else 18
            assert a['requests']==b['requests'] and len(a['requests'])==int(line['horizon'])==h
            errors=by_query[g,s,d]
            assert [x!=y for x,y in zip(a['answer_sha256'],b['answer_sha256'])]==[n>0 for n in errors]
            assert sum(errors)==int(line['direct_vertex_answers_differing'])
            costs=totals[g,idx]
            def result(cost):return crossed([t+cost for t in a['prefixes']],b['prefixes'])
            assert result(median(costs))==(line['first_cross'],line['sustained_cross'])
            for j,cost in enumerate(costs):
                xx=result(cost)
                assert tuple(x or '-' for x in xx)==tuple(line[col].split('|')[j] for col in ('first_by_prep_rep','sustained_by_prep_rep'))
        for line in rows('archived_original_validation.csv'):
            g,d,r,i=line['graph'],line['method'],int(line['rep']),int(line['prefix'])
            content=z.read(f'previous_original/{g}/{r}_{d}/query.log')
            assert hashlib.sha256(content).hexdigest()==line['direct_log_sha256']
            assert raw(g+'_original_ucef')['answer_sha256'][i-1]==line['reference_sha256']
    print('PASS: source bundle, 12 independent preparations, all recorded crossings, full-vector digests and historical direct checks')

if __name__=='__main__':check(Path(sys.argv[1]))
