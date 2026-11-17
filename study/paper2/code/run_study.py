
import hashlib
import json
import re
from pathlib import Path
import subprocess
import time
from study_cpu import run as cpu, ROOT, CODE, PAPER1
from study_gpu import run as gpu
from check_gpu import compare

STUDY=ROOT/"results/study"; DATA=ROOT/"data/study"
FIRST=ROOT/"results/threshold_gate/20261106_115627"
EXE=CODE/"uthr_audit.exe"
refs={"Flickr":STUDY/"flickr_ctd_24/values.thr", "Stack":FIRST/"stack.thr",
      "Orkut":FIRST/"orkut.thr"}
OUT=STUDY/"serial_protocol.log"


def event(s):
    with OUT.open("a") as f:f.write(time.strftime("%Y-%m-%d %H:%M:%S ")+s+"\n")
    print(s,flush=True)


def local(name,data,method="frontier",threads=24,variant="full",limit=900,keep=False,reference=True,binary=None):
    folder=STUDY/name; meta=folder/"record.json"
    if meta.exists():
        record=json.loads(meta.read_text())
        if record["status"] not in {"complete","timeout"}:
            raise RuntimeError(f"{name}: previous run is {record['status']}; inspect before resuming")
        return record
    exe=binary or (CODE/"opti_threshold.exe" if method=="opti" else EXE)
    event("start "+name)
    r=cpu(name,DATA/(data+".bin"),5,method,threads,variant,refs.get(data) if reference else None,limit,exe)
    if r["status"]=="error":raise RuntimeError(f"{name}: {r.get('diagnostic')}")
    if r["status"]=="complete" and not keep:

        raw=folder/"values.thr"
        with raw.open("rb") as f:r["output_sha256"]=hashlib.file_digest(f,"sha256").hexdigest()
        r["output_policy"]="checked against retained reference, then removed"
        meta.write_text(json.dumps(r,indent=2));raw.unlink()
    event(name+" "+r["status"]+" "+str(r.get("fields",{}).get("time","")))
    return r


def device(name,data,write=False,limit=7200):
    folder=STUDY/name;meta=folder/"record.json"
    r=json.loads(meta.read_text()) if meta.exists() else gpu(name,DATA/(data+".bin"),write,False,limit)
    if r["status"]=="complete" and write:
        accuracy=compare(refs[data],folder/"results"/(data+".bin"),DATA/(data+".rank"))
        (folder/"accuracy.json").write_text(json.dumps(accuracy,indent=2))
        if accuracy["nonfinite"] or accuracy["max_abs"]>.001:raise RuntimeError(f"{name}: GPU check {accuracy}")
    event(name+" "+str((r["status"],r.get("solver_seconds"))))
    return r


def audit(data,name):
    folder=STUDY/name; log=folder/"certificate.log"
    if log.exists():
        prior=log.read_text(errors="replace")
        bounds=re.search(r"certificate values=\d+ max_lower_deficit=(\S+) max_upper_excess=(\S+)",prior)
        if bounds and max(map(float,bounds.groups()))<=1e-9 and re.search(r"memcap:.* exit=0\s*$",prior):
            return
    event("verify "+name)
    with log.open("w") as f:
        p=subprocess.run([PAPER1/"code/memcap2.exe","32768",CODE/"verify_thresholds.exe",DATA/(data+".bin"),
                          folder/"values.thr",folder/"removals.bin","24"],stdout=f,stderr=subprocess.STDOUT,timeout=7200)
    if p.returncode!=0:raise RuntimeError(f"certificate failure in {name}: {p.returncode}")
    event(log.read_text(errors="replace").splitlines()[-2])


def main():

    active=STUDY/"stack_gpu_checked/record.json"
    while json.loads(active.read_text())["status"]=="running":time.sleep(3)
    if json.loads(active.read_text())["status"]=="complete":
        while not (active.parent/"accuracy.json").exists():time.sleep(2)
    local("sup_ctd_24","SupUser","ctd",limit=600,keep=True,reference=False)
    sup=STUDY/"sup_ctd_24/values.thr"
    if not sup.exists():
        local("sup_lazy_ref","SupUser","lazy",keep=True,reference=False)
        sup=STUDY/"sup_lazy_ref/values.thr"
    refs["SupUser"]=sup
    for g in ("Flickr","SupUser","Stack"):
        name=g.lower()+"_cert"
        local(name,g,variant="coalesce+order",keep=True);audit(g,name)
    local("opti_supuser_1","SupUser","opti",1,limit=600)
    local("supuser_frontier_1","SupUser",threads=1)

    for rep in range(1,6):
        for g in ("Flickr","SupUser","Stack"):
            methods=["lazy","frontier"] if rep%2 else ["frontier","lazy"]
            for method in methods:
                local(f"{g.lower()}_{method}_r{rep}",g,method,variant="coalesce" if method=="frontier" else "full")
        local(f"orkut_homogeneous_r{rep}","Orkut")

    for rep in range(1,6):
        for g in ("Flickr","SupUser"):
            for method in (["opti","frontier"] if rep%2 else ["frontier","opti"]):
                local(f"{g.lower()}_{method}_t1r{rep}",g,method,1,"coalesce" if method=="frontier" else "full",limit=600)

    device("supuser_gpu_checked","SupUser",True)
    for g in ("Flickr","SupUser"):
        for rep in range(1,21):device(f"{g.lower()}_gpu_r{rep}",g)

    for variant in ("full","no-shortcut","no-shift"):
        local("stack_ablation_"+variant,"Stack","lazy",variant=variant,limit=240)
    local("stack_no_core_floor","Stack",variant="coalesce+no-floor",limit=240)
    local("stack_general_plain_frontier","Stack",variant="full",limit=240)
    local("orkut_general_frontier","Orkut",variant="coalesce+general",limit=1800)
    for g in ("Stack","Orkut"):
        if g=="Orkut":device("orkut_gpu_checked",g,True)

        for rep in range(1,4):device(f"{g.lower()}_gpu_r{rep}",g)
    event("series complete")


if __name__=="__main__":main()
