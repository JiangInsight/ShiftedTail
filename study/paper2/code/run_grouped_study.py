
import subprocess
import json
import hashlib
import os
import sys
from check_study_certificate import check
import run_study as study
import study_real_inputs


def prepare():
    study.EXE=study.CODE/"uthr_grouped.exe"
    study.OUT=study.STUDY/"grouped_protocol.log"
    study.refs["SupUser"]=study.STUDY/"sup_ctd_24/values.thr"
    frozen=study.STUDY/"uthr_grouped_source.cpp"
    sources={s:hashlib.sha256((study.CODE/s).read_bytes()).hexdigest() for s in ("graph.hpp","build.bat")}
    sources["uthr_study.cpp"]=hashlib.sha256(frozen.read_bytes()).hexdigest()
    provenance=study.STUDY/"grouped_build.json"
    saved=json.loads(provenance.read_text()) if provenance.exists() else {}
    if (sources!=saved.get("sources") or not study.EXE.exists()
        or saved.get("binary")!=hashlib.sha256(study.EXE.read_bytes()).hexdigest()):
        env=dict(os.environ,CL='/I"'+str(study.CODE)+'"')
        subprocess.run([str(study.CODE/"build.bat"),str(frozen),"uthr_grouped.exe"],
                       cwd=study.CODE,env=env,check=True)
        provenance.write_text(json.dumps(dict(sources=sources,binary=hashlib.sha256(study.EXE.read_bytes()).hexdigest()),indent=2))
    (study.STUDY/"grouped_toy_certificate.json").write_text(json.dumps(check(study.EXE),indent=2))
    for graph in ("Flickr","SupUser","Stack"):
        tag=graph.lower()+"_group_cert"
        study.local(tag,graph,variant="coalesce+group+order",keep=True)
        study.audit(graph,tag)


def main():
    prepare()
    if "--prepare-only" in sys.argv: return
    for rep in range(1,6):
        for graph in ("Flickr","SupUser","Stack"):
            for arm in (("control","group") if rep%2 else ("group","control")):
                flag="coalesce+group" if arm=="group" else "coalesce"
                study.local(f"{graph.lower()}_seed_{arm}_r{rep}",graph,variant=flag)

    for graph in ("Flickr","Stack"):
        for rep in range(1,4):
            for threads in ((1,4,8,16) if rep%2 else (16,8,4,1)):
                study.local(f"{graph.lower()}_seed_t{threads}r{rep}",graph,threads=threads,
                            variant="coalesce+group",limit=1800)
    study.local("supuser_seed_t1r1","SupUser",threads=1,variant="coalesce+group")
    study.local("stack_opti_t1_limited","Stack",method="opti",threads=1,limit=1800)
    study_real_inputs.run()
    study.EXE=study.CODE/"uthr_screen.exe"
    provenance=json.loads((study.STUDY/"screen_build.json").read_text())
    for path,digest in provenance.items():
        if hashlib.sha256((study.ROOT/path).read_bytes()).hexdigest()!=digest:
            raise ValueError("screen experiment provenance mismatch: "+path)
    for rep in range(1,6):
        for g in ("Stack","Flickr","SupUser","BiomineDSAA","DBLP"):
            tag=g.lower()
            for arm in (("control","screen") if rep%2 else ("screen","control")):
                variant="coalesce+group"+("+screen" if arm=="screen" else "")
                study.local(f"{tag}_tail_{arm}_r{rep}",g,variant=variant,limit=1800)
    study.event("grouped series complete")


if __name__=="__main__": main()
