
import json
from literature_coverage import OUT,SCRATCH,WORK,rm
from run_extension import environment

def run(name,path,ref,method):
    folder=OUT/'long_caps'/f'{name}_{method}';folder.mkdir(parents=True,exist_ok=True)
    record=folder/'record.json'
    if record.exists():return
    target=path.parent/f'long_budget_{method}.thr';env=environment(24)
    if method=='gpu':
        exe=rm.GPU;env['GATD_SPARSE_OUTPUT']=str(target);args=[exe,path,0,32]
    elif method=='ucef':
        exe=WORK/'ucef.exe';args=[exe,path,24,target]
    else:
        exe=rm.CPU;args=[exe,path,'frontier',5,24,1,target]
    status,t=rm.process(args,env,folder/'run.log',1800)
    row=dict(graph=name,method=method,status=status,wall_s=t,budget_s=1800,input_sha256=rm.digest(path),exe_sha256=rm.digest(exe))
    if status=='ok':
        row.update(rm.compare(ref,target));row['output_sha256']=rm.digest(target)
        if row['max_abs']>(1e-4 if method=='gpu' else 1e-9):row['status']='invalid'
        else:target.unlink()
    rm.save(record,row);print('long budget',name,method,row['status'],round(t,2),flush=True)

def main():
    p=SCRATCH/'CitPatents'
    for method in ('cpu','ucef','gpu'):run('CitPatents',p/'CitPatents.bin',p/'reference.thr',method)

    p=rm.ART/'orkut_full';run('Orkut',p/'Orkut.bin',p/'reference.thr','ucef')
if __name__=='__main__':main()
