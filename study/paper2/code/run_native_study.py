
import hashlib
import json
import os
import subprocess
import sys
from check_study_certificate import check
import run_study as s


def build():
    files=("uthr_study.cpp","opti_threshold.cpp","graph.hpp","peel_queue.hpp","build.bat")
    config={f:hashlib.sha256((s.CODE/f).read_bytes()).hexdigest() for f in files}
    meta=s.STUDY/"native_build.json"
    saved=json.loads(meta.read_text()) if meta.exists() else {}
    binaries={"uthr_native.exe":"uthr_study.cpp","opti_native.exe":"opti_threshold.cpp"}
    if saved.get("sources")==config and all((s.CODE/b).exists() and
           hashlib.sha256((s.CODE/b).read_bytes()).hexdigest()==saved["binaries"].get(b) for b in binaries):
        return
    flags='/arch:AVX2 /I"'+str(s.ROOT/"baselines/boost_math/include")+'"'
    for name,source in binaries.items():
        subprocess.run([s.CODE/"build.bat",source,name],cwd=s.CODE,env=dict(os.environ,CL=flags),check=True)
    hashes={b:hashlib.sha256((s.CODE/b).read_bytes()).hexdigest() for b in binaries}
    meta.write_text(json.dumps(dict(sources=config,binaries=hashes,flags=flags),indent=2))


def main():
    build()
    s.EXE=s.CODE/"uthr_native.exe";s.OUT=s.STUDY/"native_protocol.log"
    s.refs["SupUser"]=s.STUDY/"sup_ctd_24/values.thr"
    for graph in ("BiomineDSAA","DBLP"):
        s.refs[graph]=s.STUDY/(graph.lower()+"_group_cert")/"values.thr"
    os.environ["UTHR_INDEXED"]="1"
    (s.STUDY/"native_toy_certificate.json").write_text(json.dumps(check(s.EXE),indent=2))
    del os.environ["UTHR_INDEXED"]
    variant="group+coalesce+indexed"
    graphs=("Stack","Flickr","SupUser","BiomineDSAA","DBLP")
    for g in graphs:
        case=g.lower()+"_native_cert"
        s.local(case,g,variant=variant+"+order",keep=True,limit=1800)
        s.audit(g,case)
    if "--prepare-only" in sys.argv: return
    for rep in range(1,6):
        for g in graphs:
            for arm in (("control","indexed") if rep%2 else ("indexed","control")):
                flag=variant if arm=="indexed" else "group+coalesce"
                s.local(f"{g.lower()}_native_{arm}_r{rep}",g,variant=flag,limit=1800)
    for g in ("Flickr","SupUser"):
        for rep in range(1,6):
            for arm in (("opti","indexed") if rep%2 else ("indexed","opti")):
                case=f"{g.lower()}_native_{arm}_t1r{rep}"
                if arm=="indexed":s.local(case,g,threads=1,variant=variant)
                else:s.local(case,g,method="opti",threads=1,binary=s.CODE/"opti_native.exe")
        s.local(g.lower()+"_native_ctd",g,method="ctd",threads=1,limit=600)
    s.event("native series complete")


if __name__=="__main__":main()
