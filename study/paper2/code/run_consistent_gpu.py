
import hashlib
import json
from pathlib import Path
import tempfile
import time
from check_gpu import compare
from study_gpu import ROOT,run


def main():
    study=ROOT/"results/study";data=ROOT/"data/study"
    exe=ROOT/"baselines/gatd_win_reduction/gatd.exe"
    sha=hashlib.sha256(exe.read_bytes()).hexdigest()
    old=json.loads((study/"dblp_reduction_checked/accuracy.json").read_text())
    assert sha==old["binary_sha256"]
    while (study/"paper1_priority.running").exists(): time.sleep(15)
    for graph in ("Flickr","SupUser","Stack","Orkut"):
        short=graph.lower();tag=short+"_reduction_checked";folder=study/tag
        ref=study/("orkut_frontier_24" if graph=="Orkut" else short+"_native_cert")/"values.thr"
        if (folder/"accuracy.json").exists():
            a=json.loads((folder/"accuracy.json").read_text())
        else:

            with tempfile.TemporaryDirectory(prefix="PVLDB-Gatd-check-") as temp:
                r=run(tag,data/(graph+".bin"),True,binary=exe,output_directory=temp)
                if r["status"]!="complete": raise RuntimeError(r)
                path=Path(temp)/"results"/(graph+".bin")
                a=compare(ref,path,data/(graph+".rank"))
                with path.open("rb") as f:a["dump_sha256"]=hashlib.file_digest(f,"sha256").hexdigest()
                a.update(binary_sha256=sha,reference=str(ref),output_policy="temporary dense dump checked and hashed")
                (folder/"accuracy.json").write_text(json.dumps(a,indent=2))
        print(graph,a,flush=True)
        if a["nonfinite"] or a["max_abs"]>.001:continue
        for i in range(1,21 if graph in ("Flickr","SupUser") else 4):
            case=f"{short}_reduction_r{i}"
            if (study/case/"record.json").exists():
                r=json.loads((study/case/"record.json").read_text())
            else:r=run(case,data/(graph+".bin"),binary=exe)
            if r["status"]!="complete":raise RuntimeError(r)


if __name__=="__main__": main()
