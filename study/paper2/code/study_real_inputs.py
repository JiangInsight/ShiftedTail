
import hashlib
import json
import subprocess
import zipfile
import numpy as np
from prepare_study_inputs import OUT, write
import run_study as study


def convert(member,name):
    archive=OUT/"uncertainty_dsaa_data.zip"
    meta=OUT/(name+".source.json")
    if meta.exists(): return json.loads(meta.read_text())["ready"]
    with zipfile.ZipFile(archive) as z, z.open(member) as f:
        e=np.loadtxt(f,dtype=np.float64)
    a,b=e[:,0].astype(np.int64),e[:,1].astype(np.int64)
    assert np.array_equal(a,e[:,0]) and np.array_equal(b,e[:,1])
    ids=np.unique(np.r_[a,b])
    loops=(a==b)
    prob=e[~loops,2].copy()
    assert np.isfinite(prob).all() and np.all((prob>=0)&(prob<=1))
    a=np.searchsorted(ids,a[~loops]); b=np.searchsorted(ids,b[~loops])
    n=len(ids); key=np.minimum(a,b)*n+np.maximum(a,b)
    order=np.argsort(key,kind="stable");key=key[order];prob=prob[order]
    duplicate=key[1:]==key[:-1]
    inconsistent=duplicate & (prob[1:]!=prob[:-1])
    source_projection=name=="BiomineDSAA"
    report=dict(archive=archive.name,member=member,source="https://github.com/toggled/uncertainty",
                rows=len(e),vertices=n,self_loops=int(loops.sum()),repeated_undirected_rows=int(duplicate.sum()),
                conflicting_adjacent_probabilities=int(inconsistent.sum()),ready=source_projection or not inconsistent.any())
    if report["ready"]:
        keep=np.r_[~duplicate,True] if source_projection else np.r_[True,~duplicate]
        if source_projection:
            report["projection"]="Simple undirected graph from the artifact's edict, which overwrites a pair with its last input probability; self-loops omitted"
            report["source_loader"]="https://github.com/toggled/uncertainty/blob/c55c50d3b529f4d91410f85e82ccb060a06aa3c9/src/graph.py"
        a,b=np.divmod(key[keep],n);p=prob[keep]
        src=np.r_[a,b];dst=np.r_[b,a];order=np.lexsort((dst,src))
        d=np.bincount(src,minlength=n)
        write(OUT/(name+".bin"),d,dst[order],np.tile(p,2)[order]);np.save(OUT/(name+".vertex_ids.npy"),ids)
        report.update(edges=len(a),max_degree=int(d.max()),min_probability=float(p.min()),max_probability=float(p.max()))
        with (OUT/(name+".bin")).open("rb") as f: report["sha256"]=hashlib.file_digest(f,"sha256").hexdigest()
    meta.write_text(json.dumps(report,indent=2))
    print(report,flush=True)
    return report["ready"]


def run():
    for member,g in [("data/large/biomine.txt","BiomineDSAA"),("data/casestudy/dblp.txt","DBLP")]:
        if not convert(member,g):
            study.event("excluded ambiguous undirected probabilities in "+g)
            continue
        tag=g.lower()
        subprocess.run([study.CODE/"export_rank.exe",OUT/(g+".bin"),OUT/(g+".rank")],check=True)

        study.local(tag+"_group_cert",g,variant="coalesce+group+order",keep=True,reference=False,limit=1800)
        study.audit(g,tag+"_group_cert")
        study.refs[g]=study.STUDY/(tag+"_group_cert")/"values.thr"
        checked=tag+"_gpu_checked"
        try:
            device=study.device(checked,g,True,limit=1800)
            device_ok=device["status"]=="complete"
        except RuntimeError:
            accuracy_path=study.STUDY/checked/"accuracy.json"
            if not accuracy_path.exists():raise
            checked_values=json.loads(accuracy_path.read_text())
            if not (checked_values["nonfinite"] or checked_values["max_abs"]>.001):raise
            study.event(f"{g} GPU excluded from speed comparisons: maximum error {checked_values['max_abs']}")
            device_ok=False
        for i in range(1,6):
            for method in (("lazy","frontier") if i%2 else ("frontier","lazy")):
                variant="coalesce+group" if method=="frontier" else "full"
                study.local(f"{tag}_{method}_r{i}",g,method,variant=variant,limit=1800)
            if device_ok:study.device(f"{tag}_gpu_r{i}",g,limit=1800)


if __name__=="__main__": run()
