
import argparse
import csv
import json
import os
import re
import statistics
import sys
from pathlib import Path

from build import HERE, ROOT, SCRATCH
sys.path.insert(0, str(ROOT/"code/fair_study"))
import run_matched as rm
from run_extension import environment

OUT = HERE/"runs"


def paths(graph):
    if graph in ("HepPh", "WikiTalkFR", "Deli"):
        folder = rm.WORK/"literature_coverage"/graph
    else:
        folder = rm.ART/(graph.lower()+"_full")
    if graph=="Deli":

        reference=rm.WORK/"literature_coverage/one_level/Deli.thr"
        if reference.stat().st_size!=1108044432:
            raise ValueError("missing or incomplete certified Deli reference")
    else:
        reference=folder/"reference.thr"
    return folder/(graph+".bin"), reference


def store(tag, row):
    (OUT/(tag+".json")).write_text(json.dumps(row, indent=2), encoding="utf8")
    print(tag, row["status"], round(row["wall_s"], 2), flush=True)


def cpu(graph, workers, cap, rep, hub_cap=False):
    tag = f"cpu_{graph}_t{workers}_b{cap}_r{rep}" + ("_hubcap" if hub_cap else "")
    if (OUT/(tag+".json")).exists():
        return
    source, ref = paths(graph)
    exe = SCRATCH/"cpu/builder.exe"
    output = SCRATCH/(tag+".thr")
    order = SCRATCH/(tag+".ord")
    env = environment(workers)
    env.update(UTHR_RESIDENT_LEVELS=str(cap), UTHR_CERT_ORDER=str(order))
    if hub_cap: env["UTHR_CAP_HUB_TAIL"]="1"
    args = [exe, source, "frontier", 5, workers, 1, output]
    log = OUT/(tag+".log")
    limit = 5400 if graph == "Deli" else 600
    status, wall = rm.process(args, env, log, limit)
    row = dict(graph=graph, workers=workers, capacity=cap, rep=rep, hub_cap=hub_cap, status=status, wall_s=wall,
               limit_s=limit, input_sha256=rm.digest(source), exe_sha256=rm.digest(exe))
    logtxt = log.read_text(errors="replace")
    peak = re.search(r"peak_mb=(\d+)", logtxt)
    if peak: row["build_peak_mib"] = int(peak[1])
    if status == "ok":
        fields = dict(x.split("=") for x in re.search(r"^result (.*)", logtxt, re.M)[1].split())
        row.update(sweep_s=float(fields["sweep"][:-1]), peel_s=float(fields["peel"][:-1]),
                   thresholds=int(fields["thresholds"]), output_sha256=rm.digest(output),order_sha256=rm.digest(order))
        row.update(rm.compare(ref, output))
        verifier = SCRATCH/"cpu/verify.exe"
        if graph == "Deli":
            verifier = Path(os.environ.get("UTHR_STRICT_CHECKER",
                                           ROOT/"results/review4_arithmetic/default_strict_verifier.exe"))
        vlog = OUT/(tag+"_verify.log")
        vst, verify_time = rm.process([verifier, source, output, order, workers], env, vlog, limit)
        vr = vlog.read_text(errors="replace")
        row.update(verify_status=vst, verify_wall_s=verify_time, verify_exe_sha256=rm.digest(verifier))
        if vst == "ok":
            cert = dict(x.split("=") for x in re.search(r"^certificate (.*)",vr,re.M)[1].split())
            row.update(verify_peak_mib=int(re.search(r"peak_mb=(\d+)",vr)[1]),
                       lower_deficit=float(cert["max_lower_deficit"]),upper_excess=float(cert["max_upper_excess"]))
        if vst != "ok" or row["max_abs"] > 1e-9: row["status"]="invalid"
    store(tag,row)
    if row["status"] == "ok":
        output.unlink()
        order.unlink()


def gpu(graph, variant, multiply, rep):
    tag=f"gpu_{graph}_{variant}_m{multiply}_r{rep}"
    dest=OUT/(tag+".json")
    if dest.exists(): return json.loads(dest.read_text())
    source, ref = paths(graph)
    exe = rm.GPU if variant=="fp32" else SCRATCH/variant/"gatd.exe"
    output = SCRATCH/(tag+".thr")
    env = environment(24)
    env["GATD_SPARSE_OUTPUT"]=str(output)
    log=OUT/(tag+".log")
    status, wall = rm.process([exe,source,0,multiply],env,log,900)
    row=dict(graph=graph,prec=variant,multiply=multiply,rep=rep,status=status,wall_s=wall,
             exe_sha256=rm.digest(exe),input_sha256=rm.digest(source))
    if status=="ok":
        row.update(rm.compare(ref,output))
        row["tight"]=row["max_abs"]<=1e-9
        row["coarse"]=row["max_abs"]<=1e-4
        row["host_peak_mib"]=int(re.search(r"peak_mb=(\d+)",log.read_text(errors="replace"))[1])
        row["output_sha256"]=rm.digest(output)
    store(tag,row)
    if status=="ok": output.unlink()
    return row


def matched_hub(graph, cap, rep, method):

    tag=f"matched_{graph}_b{cap}_{method}_r{rep}"
    if (OUT/(tag+".json")).exists(): return
    source, ref=paths(graph)
    env=environment(24)
    output=SCRATCH/(tag+".thr")
    if method=="hubcap":
        exe=SCRATCH/"cpu/builder.exe"
        env.update(UTHR_RESIDENT_LEVELS=str(cap),UTHR_CAP_HUB_TAIL="1")
        args=[exe,source,"frontier",5,24,1,output]
    else:
        exe=rm.WORK/"ucef.exe"
        args=[exe,source,24,output]
    log=OUT/(tag+".log")
    status,wall=rm.process(args,env,log,5400 if graph=="Deli" else 300)
    row=dict(graph=graph,method=method,matched_capacity=cap,rep=rep,status=status,wall_s=wall,
             exe_sha256=rm.digest(exe),input_sha256=rm.digest(source))
    if status=="ok":
        row.update(rm.compare(ref,output))
        row["output_sha256"]=rm.digest(output)
        row["host_peak_mib"]=int(re.search(r"peak_mb=(\d+)",log.read_text(errors="replace"))[1])
        if row["max_abs"]>1e-9: row["status"]="invalid"
    store(tag,row)
    if row["status"]=="ok": output.unlink()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("suite",choices=["cpu","deli","gpu","hub-match"])
    arg=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if arg.suite=="cpu":

        for graph in ("HepPh","WikiTalkFR"):
            for workers,cap in [(1,8),(4,8),(8,8),(24,8),(24,1),(24,4),(24,24)]:
                cpu(graph,workers,cap,1)
        for rep, cap_hubs in ((1,True),(2,True),(2,False)):
            cpu("WikiTalkFR",24,24,rep,cap_hubs)
    elif arg.suite=="deli":
        cpu("Deli",24,4,1)
        cpu("Deli",24,4,1,True)
        first=json.loads((OUT/"cpu_Deli_t24_b4_r1.json").read_text())
        if first["status"]!="ok":
            cpu("Deli",24,2,1)
            cpu("Deli",24,2,1,True)
        cap=4 if first["status"]=="ok" else 2
        if json.loads((OUT/f"cpu_Deli_t24_b{cap}_r1_hubcap.json").read_text())["status"]!="ok":
            cap=1
            cpu("Deli",24,cap,1,True)
        for method in ("ucef","hubcap"): matched_hub("Deli",cap,1,method)
    elif arg.suite=="hub-match":
        for rep,order in ((1,("ucef","hubcap")),(2,("hubcap","ucef"))):
            for method in order: matched_hub("WikiTalkFR",24,rep,method)
    else:
        arms=("fp32","fp64_6dp","fp64")

        tuning={a:{m:[] for m in (16,32,64)} for a in arms}
        for rep in (1,2):
            for m in ((16,32,64) if rep==1 else (64,32,16)):
                for a in (arms if rep==1 else arms[::-1]):
                    row=gpu("Flickr",a,m,rep)
                    if row["status"]=="ok" and row["coarse"]: tuning[a][m].append(row["wall_s"])
        selected={a:min((m for m,v in d.items() if len(v)==2),key=lambda m:statistics.mean(d[m]))
                  for a,d in tuning.items() if any(len(v)==2 for v in d.values())}
        (OUT/"gpu_tuning.json").write_text(json.dumps(selected,indent=2))
        for graph in ("SupUser","WikiTalkFR","HepPh"):
            for rep in (1,2):
                for a in (arms if rep==1 else arms[::-1]):
                    if a in selected: gpu(graph,a,selected[a],rep)
    records=[json.loads(p.read_text()) for p in sorted(OUT.glob("*.json")) if p.name!="gpu_tuning.json"]
    with (HERE/"measurements.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,sorted({k for r in records for k in r}));w.writeheader();w.writerows(records)


if __name__=="__main__": main()
