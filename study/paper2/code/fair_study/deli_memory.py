
import json
import os
import subprocess
from literature_coverage import OUT, SCRATCH, rm
from run_extension import environment

def main():
    folder=OUT/'large/one_level';folder.mkdir(exist_ok=True)
    work=SCRATCH/'one_level';work.mkdir(exist_ok=True)
    binary=work/'one_level.exe'
    original=rm.CODE/'uthr_study.cpp'
    source=original.read_text(encoding='utf-8-sig')
    old='const u32 chunk = static_cast<u32>(std::max(1, threads));'
    assert source.count(old)==1
    variant=work/'uthr_one_level.cpp'
    variant.write_text(source.replace(old,'const u32 chunk = 1;'),encoding='utf-8')
    env=environment(24);env['CL']=f'/arch:AVX2 /I"{rm.CODE}" /I"{rm.ROOT}/baselines/boost_math/include"'
    baseline=folder/'HepPh.json'
    if baseline.exists():
        prior=json.loads(baseline.read_text())
        assert prior['exe_sha256']==rm.digest(binary) and prior['diagnostic_source_sha256']==rm.digest(variant)
    else:
        with (folder/'build.log').open('w') as f:
            subprocess.run([rm.CODE/'build.bat',variant,binary],cwd=work,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    for name in ('HepPh','Deli'):
        data=SCRATCH/name;path=data/(name+'.bin');record=folder/(name+'.json')
        if record.exists():continue
        values=work/(name+'.thr');order=work/(name+'.ord');env['UTHR_CERT_ORDER']=str(order)
        status,t=rm.process([binary,path,'frontier',5,24,1,values],env,folder/(name+'.log'),7200)
        row=dict(graph=name,workers=24,concurrent_levels=1,status=status,wall_s=t,budget_s=7200,input_sha256=rm.digest(path),
                 exe_sha256=rm.digest(binary),base_source_sha256=rm.digest(original),diagnostic_source_sha256=rm.digest(variant))
        if status=='ok':
            expected=json.loads((OUT/(name+'_input.json')).read_text())
            assert values.stat().st_size==8*expected['values']+12*expected['maximum_core']
            check,t2=rm.process([rm.CODE/'verify_thresholds.exe',path,values,order,24],env,folder/(name+'_verify.log'),7200)
            row.update(check=check,verify_wall_s=t2,output_sha256=rm.digest(values),output_bytes=values.stat().st_size)
            if check!='ok':row['status']='certificate_'+check
            if name=='HepPh':
                row['identical_to_frozen_reference']=row['output_sha256']==rm.digest(data/'reference.thr')
                assert row['identical_to_frozen_reference']
            if name=='Deli' and row['status']=='ok':
                row['retrospective']={}
                for m in ('cpu','ucef','gpu'):
                    measured=OUT/'large'/m/'record.json'
                    if measured.exists():
                        r=json.loads(measured.read_text())
                        if r['status']=='unverified':
                            result=data/(m+'.thr');assert rm.digest(result)==r['output_sha256']
                            fields=rm.compare(values,result)
                            fields['validated']=fields['max_abs']<=(1e-4 if m=='gpu' else 1e-9)
                            row['retrospective'][m]=fields
        rm.save(record,row);print('one-level',name,row['status'],round(t,1),flush=True)
        if name=='HepPh' and row['status']!='ok':raise RuntimeError('small reference regression')
def time_without_order():
    folder=OUT/'large/one_level'
    record=folder/'Deli_no_order.json'
    if record.exists():return
    reference=json.loads((folder/'Deli.json').read_text())
    assert reference['status']=='ok'
    work=SCRATCH/'one_level';binary=work/'one_level.exe'
    assert rm.digest(binary)==reference['exe_sha256']
    graph=SCRATCH/'Deli/Deli.bin';target=work/'Deli_no_order.thr'
    env=environment(24)
    assert 'UTHR_CERT_ORDER' not in env
    status,t=rm.process([binary,graph,'frontier',5,24,1,target],env,folder/'Deli_no_order.log',7200)
    row=dict(status=status,wall_s=t,workers=24,concurrent_levels=1,budget_s=7200,input_sha256=rm.digest(graph),exe_sha256=rm.digest(binary))
    if status=='ok':
        row['output_sha256']=rm.digest(target)
        row['identical_to_verified_file']=row['output_sha256']==reference['output_sha256']
        if not row['identical_to_verified_file']:row['status']='invalid'
    rm.save(record,row);print('Deli matched writer, one level',row['status'],round(t,1),flush=True)

if __name__=='__main__':main();time_without_order()
