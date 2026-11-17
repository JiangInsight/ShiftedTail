from pathlib import Path
import json,re,statistics as stats
from datetime import datetime

ROOT=Path(__file__).resolve().parents[1]
STUDY=ROOT/"results/study"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def audit():
    verified=read(STUDY/"verified_timed_outputs.json")
    result={}
    expected_hash=None
    for graph in ("Flickr","SupUser","Stack","BiomineDSAA","DBLP","Orkut"):
        g=graph.lower();hashed=verified[g]
        assert hashed['repetitions']==hashed['identical_repetitions']==5
        cpu=[]
        for i in range(1,6):
            tag=f"{g}_native_indexed_r{i}" if g!="orkut" else f"orkut_homogeneous_r{i}"
            entry=read(STUDY/tag/"record.json")
            assert entry["status"]=="complete" and entry["output_sha256"]==hashed["sha256"]
            cpu.append(float(entry["fields"]["time"][:-1]))
        checked=read(STUDY/(g+"_reduction_checked")/"accuracy.json")
        assert not checked["nonfinite"] and checked["max_abs"]<=.001
        actual_hash=checked["binary_sha256"]
        if expected_hash is None: expected_hash=actual_hash
        assert expected_hash==actual_hash
        n=20 if g in ("flickr","supuser") else (3 if g in ("stack","orkut") else 5)
        gpu=[]
        for i in range(1,n+1):
            entry=read(STUDY/f"{g}_reduction_r{i}"/"record.json")
            assert entry["status"]=="complete" and not entry["writer"] and "gatd_win_reduction" in entry["args"][2]
            gpu.append(entry["solver_seconds"])
        if g=="orkut":
            numeric=read(STUDY/"orkut_frontier_24/exact_check.json")["max_abs_upper"]
        else:
            txt=(STUDY/(g+"_native_cert")/"certificate.log").read_text()
            match=re.search(r"certificate values=(\d+) max_lower_deficit=(\S+) max_upper_excess=(\S+)",txt)
            assert int(match[1])==checked["thresholds"] and re.search(r"memcap:.*exit=0\s*$",txt)
            numeric=max(float(match[2]),float(match[3]))
        result[graph]=dict(cpu_n=len(cpu),gpu_n=len(gpu),cpu_mean_s=stats.mean(cpu),gpu_mean_s=stats.mean(gpu),
                           gpu_over_cpu=stats.mean(gpu)/stats.mean(cpu),cpu_abs_error_bound=numeric,
                           gpu_vs_cpu_max_abs=checked["max_abs"],values=checked["thresholds"])
    out=dict(finalized_local=datetime.now().astimezone().isoformat(timespec="seconds"),device_sha256=expected_hash,
             graphs=result,external_stack_ratio=464.92/result["Stack"]["cpu_mean_s"])
    (STUDY/"completion.json").write_text(json.dumps(out,indent=2))
    return out


if __name__=="__main__":print(json.dumps(audit(),indent=2))
