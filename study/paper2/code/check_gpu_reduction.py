
import hashlib
import json
from pathlib import Path
import subprocess
from study_gpu import ROOT,run
from check_gpu import compare


def main():
    study=ROOT/"results/study";data=ROOT/"data/study"
    source=ROOT/"baselines/gatd_win_reduction";exe=source/"gatd.exe"
    subprocess.run([str(source/"build_windows.bat")],cwd=source,check=True)
    for graph in ("DBLP","BiomineDSAA"):
        tag=graph.lower()+"_reduction_checked";target=study/tag
        r=run(tag,data/(graph+".bin"),True,limit=1800,binary=exe)
        if r["status"]!="complete":raise RuntimeError(r)
        a=compare(study/(graph.lower()+"_group_cert")/"values.thr",target/"results"/(graph+".bin"),data/(graph+".rank"))
        a["binary_sha256"]=hashlib.sha256(exe.read_bytes()).hexdigest()
        (target/"accuracy.json").write_text(json.dumps(a,indent=2))
        print(graph,a,flush=True)
        if a["nonfinite"] or a["max_abs"]>.001:
            print(graph+" also fails the accuracy gate with corrected reductions; exclude GPU ratios.",flush=True)
            continue
        for i in range(1,6):
            t=run(f"{graph.lower()}_reduction_r{i}",data/(graph+".bin"),limit=1800,binary=exe)
            if t["status"]!="complete":raise RuntimeError(t)


if __name__=="__main__":main()
