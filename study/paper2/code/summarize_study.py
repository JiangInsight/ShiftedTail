
import csv
import json
import re
import statistics as stats
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STUDY=ROOT/"results/study"
GRAPHS=("Flickr","SupUser","Stack","Orkut")
PUBLISHED=(1.98,4.45,464.92,4483.69)
HARDWARE="Intel Core Ultra 9 275HX (24 CPU threads), RTX 5080 Laptop 16 GB"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def extract(tag):
    folder=STUDY/tag
    path=folder/"record.json"
    if not path.exists(): return None
    r=read(path)
    f=r.get("fields",{})
    duration=float(f["time"].rstrip("s")) if "time" in f else r.get("solver_seconds")
    memory=re.search(r"memcap:.*peak_mb=(\d+)",(folder/"run.log").read_text(errors="replace"))
    return dict(case=tag,status=r["status"],solver_s=duration,
                process_s=r.get("process_wall_s",r.get("wall_s") if "writer" in r else None),
                peak_host_mib=int(memory[1]) if memory else None,thresholds=r.get("thresholds"),
                max_abs_vs_reference=r.get("max_abs"),hash=r.get("output_sha256"))


def times(pattern,start,end):
    records=[extract(pattern.format(i)) for i in range(start,end+1)]
    return [r["solver_s"] for r in records if r and r["status"]=="complete"]


def walls(pattern,end):
    records=[extract(pattern.format(i)) for i in range(1,end+1)]
    return [r["process_s"] for r in records if r and r["status"]=="complete" and r["process_s"]]


def measured(values):
    if not values:return "—"
    return f"{stats.mean(values):.3f} ± {stats.stdev(values):.3f} ({len(values)})" if len(values)>1 else f"{values[0]:.3f} (1)"


def ratio(a,b):
    return f"{stats.mean(a)/stats.mean(b):.2f}×" if a and b else "—"


def generate():
    lines=["# Full η-threshold decomposition", "",HARDWARE+". Times are seconds, reported as mean ± sample standard deviation (completed runs).",
           "The CPU emits a binary64 threshold for each eligible vertex and level. The local GPU is the repaired public Gatd port, timed with its dense writer off. The published column uses the RTX 3090 numbers in Table 3. CPU and GPU native timing regions and output formats differ.",
           "", "| Graph | Frozen lazy CPU | Frontier CPU | Frequent-factor CPU | Local GPU | Local GPU / frontier | Local GPU / frequent-factor | Published GPU / frontier | Published GPU / frequent-factor |",
           "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for graph,pub in zip(GRAPHS,PUBLISHED):
        g=graph.lower()
        cpu=times(g+"_frontier_r{}",1,5) if g!="orkut" else times("orkut_homogeneous_r{}",1,5)
        lazy=times(g+"_lazy_r{}",1,5)
        group=times(g+"_seed_group_r{}",1,5)
        gpu=times(g+"_gpu_r{}",1,20 if g in ("flickr","supuser") else 3)
        lines.append("| "+" | ".join([graph,measured(lazy),measured(cpu),measured(group),measured(gpu),
                                   ratio(gpu,cpu),ratio(gpu,group),ratio([pub],cpu),ratio([pub],group)])+" |")
    lines+=["","Orkut has a single edge probability. Its frontier timing uses the deterministic-core/binomial shortcut. The general-path control is listed in the case records.",
            "","## Process wall time, including input and preparation",
            "","CPU process time includes native sparse output. GPU performance runs omit dense serialization. The separate GPU accuracy run writes 12 bytes for each vertex at every level, including ineligible vertices.",
            "","| Graph | Frontier CPU | Frequent-factor CPU | GPU, writer off | GPU, writer on (one accuracy run) |",
            "|---|---:|---:|---:|---:|"]
    for graph,checked in zip(GRAPHS,("flickr_gpu_subwarp_check","supuser_gpu_checked","stack_gpu_checked","orkut_gpu_checked")):
        g=graph.lower()
        cpu=walls(g+"_frontier_r{}",5) if g!="orkut" else walls("orkut_homogeneous_r{}",5)
        gpu=walls(g+"_gpu_r{}",20 if g in ("flickr","supuser") else 3)
        writer=extract(checked);w=[writer["process_s"]] if writer and writer["status"]=="complete" else []
        lines.append(f"| {graph} | {measured(cpu)} | {measured(walls(g+'_seed_group_r{}',5))} | {measured(gpu)} | {measured(w)} |")
    lines+=["","## Sequential comparison","","| Graph | OptiUCF reconstruction (1 thread) | Frontier (1 thread) | Ratio |","|---|---:|---:|---:|"]
    for g in ("flickr","supuser"):
        opti=times(g+"_opti_t1r{}",1,5);our=times(g+"_frontier_t1r{}",1,5)
        lines.append(f"| {g} | {measured(opti)} | {measured(our)} | {ratio(opti,our)} |")
    lines+=["","## Paired frequent-factor ablation and thread scaling",
            "","| Graph | Matched control | Frequent-factor | Control / frequent-factor |","|---|---:|---:|---:|"]
    for graph in GRAPHS[:3]:
        g=graph.lower()
        base=times(g+"_seed_control_r{}",1,5);opt=times(g+"_seed_group_r{}",1,5)
        lines.append(f"| {graph} | {measured(base)} | {measured(opt)} | {ratio(base,opt)} |")
    for g in ("flickr","stack"):
        lines+=["",f"| {g} CPU workers | Seconds |","|---:|---:|"]
        for t in (1,4,8,16,24):
            ts=times(g+f"_seed_t{t}r{{}}",1,3) if t!=24 else times(g+"_seed_group_r{}",1,5)
            lines.append(f"| {t} | {measured(ts)} |")
    lines+=["","## Additional real probability inputs","",
            "| Graph | Vertices | Edges | Lazy CPU | Frequent-factor CPU | Local GPU | Local GPU / frequent-factor |",
            "|---|---:|---:|---:|---:|---:|---:|"]
    for graph in ("BiomineDSAA","DBLP"):
        p=ROOT/"data/study"/(graph+".source.json")
        if not p.exists(): continue
        r=read(p)
        if not r["ready"]:
            lines.append(f"| {graph} (conflicting probabilities) | {r['vertices']:,} | — | — | — | — | — |")
            continue
        g=graph.lower();base=times(g+"_lazy_r{}",1,5);method=times(g+"_frontier_r{}",1,5);gpu=times(g+"_gpu_r{}",1,5)
        lines.append(f"| {graph} | {r['vertices']:,} | {r['edges']:,} | {measured(base)} | {measured(method)} | {measured(gpu)} | {ratio(gpu,method)} |")
    lines+=["","## Concentration-bound ablation",
            "","| Graph | Same binary, screen off | Screen on | Screen off / on | Local GPU / screen on | Published GPU / screen on |",
            "|---|---:|---:|---:|---:|---:|"]
    for graph in ("Stack","Flickr","SupUser","BiomineDSAA","DBLP"):
        g=graph.lower();a=times(g+"_tail_control_r{}",1,5);b=times(g+"_tail_screen_r{}",1,5)
        gpu=times(g+"_gpu_r{}",1,20 if g in ("flickr","supuser") else 5)
        pub=[PUBLISHED[GRAPHS.index(graph)]] if graph in GRAPHS else []
        lines.append(f"| {graph} | {measured(a)} | {measured(b)} | {ratio(a,b)} | {ratio(gpu,b)} | {ratio(pub,b)} |")
    lines+=["","## Native CPU instructions and indexed queue","",
            "| Graph | AVX2, reference heap | AVX2, indexed heap | Local GPU / indexed | Published GPU / indexed |",
            "|---|---:|---:|---:|---:|"]
    for graph in ("Stack","Flickr","SupUser","BiomineDSAA","DBLP"):
        g=graph.lower();a=times(g+"_native_control_r{}",1,5);b=times(g+"_native_indexed_r{}",1,5)
        gpu=times(g+"_gpu_r{}",1,20 if g in ("flickr","supuser") else 5)
        pub=[PUBLISHED[GRAPHS.index(graph)]] if graph in GRAPHS else []
        lines.append(f"| {graph} | {measured(a)} | {measured(b)} | {ratio(gpu,b)} | {ratio(pub,b)} |")
    lines+=["","| Graph | OptiUCF, AVX2, 1 thread | Indexed, AVX2, 1 thread | Ratio |","|---|---:|---:|---:|"]
    for g in ("flickr","supuser"):
        a=times(g+"_native_opti_t1r{}",1,5);b=times(g+"_native_indexed_t1r{}",1,5)
        lines.append(f"| {g} | {measured(a)} | {measured(b)} | {ratio(a,b)} |")
    lines+=["","## Final comparison using the same corrected GPU port on every graph","",
            "The first GPU port failed the predeclared accuracy gate on the DSAA inputs. Its times are excluded from speed ratios on these graphs. The second port also synchronizes the reset before global reduction, retains the minimum across every dirty vertex in a block, and synchronizes the block before reusing its scratch space.",
            "","| Graph | Mean GPU seconds with corrected reductions | CPU seconds (native indexed on heterogeneous graphs, homogeneous shortcut on Orkut) | Corrected GPU / CPU |","|---|---:|---:|---:|"]
    for graph in (*GRAPHS,"BiomineDSAA","DBLP"):
        g=graph.lower();a=times(g+"_reduction_r{}",1,20 if graph in ("Flickr","SupUser") else 5)
        b=times("orkut_homogeneous_r{}",1,5) if graph=="Orkut" else times(g+"_native_indexed_r{}",1,5)
        lines.append(f"| {graph} | {measured(a)} | {measured(b)} | {ratio(a,b)} |")
    lines+=["","## Independent checks","","| CPU result | Values | Lower deficit | Upper excess | Unambiguous at 6 decimals |","|---|---:|---:|---:|---:|"]
    for log in sorted(STUDY.glob("*_cert/certificate.log")):
        s=log.read_text(errors="replace")
        m=re.search(r"certificate values=(\d+) max_lower_deficit=(\S+) max_upper_excess=(\S+) unique_rounding_6dp=(\d+)",s)
        if m and re.search(r"memcap:.*exit=0\s*$",s): lines.append("| "+" | ".join([log.parent.name,*m.groups()])+" |")
    uniform=read(STUDY/"orkut_frontier_24/exact_check.json")
    lines+=["",f"On the uniform Orkut graph, all {uniform['values']:,} values were checked against the exact rational binomial law for the stored input probability. Largest absolute error ≤ {uniform['max_abs_upper']:.4g}.",
            "","| GPU result vs CPU reference | Values | Mean absolute error | Max absolute error | Same rounding at 6 decimals | Count above 1e-5 |",
            "|---|---:|---:|---:|---:|---:|"]
    for case in (["flickr_gpu_subwarp_check","supuser_gpu_checked","stack_gpu_checked","orkut_gpu_checked","biominedsaa_gpu_checked","dblp_gpu_checked"]+
                 [g.lower()+"_reduction_checked" for g in (*GRAPHS,"BiomineDSAA","DBLP")]):
        p=STUDY/case/"accuracy.json"
        if p.exists():
            r=read(p)
            lines.append(f"| {case} | {r['thresholds']:,} | {r['mean_abs']:.4g} | {r['max_abs']:.4g} | {r['rounded_6dp_match_fraction']:.2%} | {r['above_1e_minus_5']} |")
    lines+=["","## Selected controls","","| Run | Status | Solver s | Native process s | Host peak MiB |","|---|---|---:|---:|---:|"]
    for tag in ("flickr_ctd_1","flickr_ctd_24","sup_ctd_24","stack_ablation_full","stack_ablation_no-shortcut",
                "stack_ablation_no-shift","stack_no_core_floor","stack_general_plain_frontier","orkut_general_frontier","stack_opti_t1_limited"):
        r=extract(tag)
        if r:
            wall=r["process_s"]
            lines.append(f"| {tag} | {r['status']} | {r['solver_s'] or '—'} | {round(wall,3) if wall else '—'} | {r['peak_host_mib'] or '—'} |")
    lines+=["","The Stack feature ablations use a 240 s wall limit and the large sequential OptiUCF comparison uses an 1800 s wall limit. Local manuscript editing and short builds took place during the censored OptiUCF run; the study does not compute a speed ratio from that timeout. Host peak memory excludes GPU VRAM.",
            "","See [experimental protocol](PROTOCOL.md), [patch and binary provenance](build_provenance.json), and [raw case index](cases.csv). [Published GPU baseline and Table 3](https://www.vldb.org/pvldb/vol19/p2591-gao.pdf)."]
    start=lines.index("## Final comparison using the same corrected GPU port on every graph")
    end=lines.index("## Independent checks",start)
    primary=lines[start:end];del lines[start:end]
    highlights=["","## Interpretation","",
        "On heterogeneous Stack, the native indexed solver is measured across five runs. The predeclared 10× external target corresponds to 46.492 seconds against the published RTX 3090 time of 464.92 seconds. The external ratio is separate from the corrected same-host ratios above.",
        "The uniform Orkut input admits a different binomial algorithm, verified against exact arithmetic. Its general-path control and specialized time are reported separately. Matching structural counts does not establish identity of the edge probabilities in the published Orkut run.",
        "Five heterogeneous inputs have numerical certificates independent of the solver. The [timed output hashes](verified_timed_outputs.json) match the certified files in all five repetitions on each of the six graphs. The absolute numerical enclosure and agreement after rounding to six decimals describe different properties.",
        "","## Earlier portable CPU and first-port GPU measurements",""]
    idx=next(i for i,s in enumerate(lines) if s.startswith("| Graph | Frozen lazy CPU"))
    completed=STUDY/"completion.json"
    if completed.exists():
        audited=read(completed)
        stack=audited["graphs"]["Stack"]
        highlights[3]=(f"On heterogeneous Stack the indexed CPU averages {stack['cpu_mean_s']:.3f} s over five runs. "
                       f"The corrected GPU averages {stack['gpu_mean_s']:.3f} s over three runs on the same input ({stack['gpu_over_cpu']:.2f}×). "
                       f"Against the published RTX 3090 time of 464.92 s, the external ratio is {audited['external_stack_ratio']:.2f}×, passing the predeclared 10× screening threshold.")
        highlights[4]+=f" With the general method forced, Orkut took {extract('orkut_general_frontier')['solver_s']:.2f} s in one control run."
        highlights.insert(6,"[Validated completion record](completion.json) · [Input sizes, source locations and SHA-256](input_manifest.json).")
    lines[idx:idx]=primary+highlights
    (STUDY/"RESULTS.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    rows=[extract(p.parent.name) for p in sorted(STUDY.glob("*/record.json")) if (p.parent/"run.log").exists()]
    with (STUDY/"cases.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


if __name__=="__main__": generate()
