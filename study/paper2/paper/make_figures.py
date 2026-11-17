
from pathlib import Path
from statistics import median
import csv
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "results"
OUT = HERE / "figures"
OUT.mkdir(exist_ok=True)
FAIR = ROOT / "fair_study"
LIT = ROOT / "literature_coverage"
SUB = ROOT / "submission_study"
plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":8, "pdf.fonttype":42,
                     "axes.spines.top":False, "axes.spines.right":False})
COLORS = ["#006157", "#ac4b25", "#385681", "#5d4669"]

def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as src:
        return list(csv.DictReader(src))

def record(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def tex_rows(name, data):
    (OUT / name).write_text("".join(" & ".join(items) + r" \\" + "\n" for items in data),
                            encoding="ascii")

def finish(fig, name):
    fig.tight_layout(pad=.55)
    fig.savefig(OUT / name, bbox_inches="tight", pad_inches=.035,
                metadata={"CreationDate":None, "ModDate":None})
    plt.close(fig)

def shown(x):
    return f"{x:.3f}" if x < 100 else f"{x:,.2f}"

def build_table():
    base = rows(FAIR / "matched_cases.csv")
    arms = rows(FAIR / "all_arms.csv")
    later = rows(LIT / "new_full_baselines.csv")
    full = {}
    for row in base:
        if row["kind"] != "full":
            continue
        graph = row["graph"]
        u = next(a for a in arms if a["case"] == row["case"] and a["method"] == "ucef" and a["threads"] == "24")
        sec = float(u["median_s"]) if u["median_s"] else record(LIT / "long_caps/Orkut_ucef/record.json")["wall_s"]
        full[graph] = (int(row["vertices"]), int(row["edges"]), int(row["values"]),
                       float(row["cpu_median_s"]), sec, float(row["gpu_median_s"]))
    for g in dict.fromkeys(a["graph"] for a in later):
        meta = record(LIT / f"{g}_input.json")
        methods = {a["arm"]:float(a["median_s"]) if a["median_s"] else None
                   for a in later if a["graph"] == g and a["threads"] == "24"}
        full[g] = (meta["vertices"], meta["edges"], meta["values"], methods["cpu"], methods["ucef"], methods["gpu"])
    meta = record(LIT / "Deli_input.json")
    checks = record(LIT / "large/one_level/Deli.json")
    assert all(a["validated"] for a in checks["retrospective"].values())
    full["Deli"] = (meta["vertices"], meta["edges"], meta["values"],
                    record(LIT / "large/one_level/Deli_no_order.json")["wall_s"],
                    record(LIT / "large/ucef/record.json")["process_wall_s"],
                    record(LIT / "large/gpu/record.json")["process_wall_s"])
    names = {"WikiTalkFR":"Wiki-Pe","CN15kProjection":"CN15k projection","BiomineDSAA":"Biomine"}
    graph_order = ["Flickr","SupUser","DBLP","BiomineDSAA","Stack","Orkut","HepPh","CN15kProjection","Twitter","WebGoogle","CitPatents","WikiTalkFR","Deli"]
    assert set(graph_order) == set(full)
    weights = {"Flickr":"supplied", "SupUser":"events", "DBLP":"supplied", "BiomineDSAA":"last",
               "Stack":"events", "Orkut":"constant", "HepPh":"events", "CN15kProjection":"maximum",
               "Twitter":"last", "WebGoogle":"uniform", "CitPatents":"uniform", "WikiTalkFR":"events",
               "Deli":"events"}
    result = []
    for g in graph_order:
        n, m, values, *times = full[g]
        fastest = min(t for t in times if t is not None)
        seconds = []
        for method, t in zip(("cpu", "ucef", "gpu"), times):
            if t is None:
                attempt = record(LIT / f"long_caps/{g}_{method}/record.json")
                assert attempt["status"] == "timeout"
                budget = format(int(attempt["budget_s"]), ",").replace(",", "{,}")
                seconds.append(f"$>{budget}$")
            else:
                seconds.append(r"\textbf{" + shown(t) + "}" if t == fastest else shown(t))
        result.append([names.get(g,g), weights[g], f"{n:,}", f"{m:,}", f"{values:,}", *seconds])
    tex_rows("build_rows.tex",result)

    fig, ax = plt.subplots(figsize=(3.45,2.85))
    display = list(reversed(graph_order))
    for y,g in enumerate(display):
        cpu, ucef, gpu = full[g][3:]
        ax.scatter(ucef/cpu, y+.12, c=COLORS[0], marker="o", s=17,
                   label="UCEF / proposed" if y==0 else None)
        if gpu is not None:
            ax.scatter(gpu/cpu, y-.12, c=COLORS[1], marker="^", s=19,
                       label="Gatd / proposed" if y==0 else None)
    ax.axvline(1, lw=1, color=".2")
    ax.set(xscale="log", xlim=(.011,90), yticks=range(len(display)),
           yticklabels=[names.get(g,g) for g in display],
           xlabel="Competitor time / proposed time", xticks=[.02,.1,1,10,50],
           xticklabels=[".02",".1","1","10","50"])
    ax.tick_params(axis="y",length=0,labelsize=7)
    ax.grid(axis="x",alpha=.25)
    ax.legend(loc="lower left",bbox_to_anchor=(0,1),ncol=2,frameon=False,fontsize=7)
    finish(fig,"build_ratios.pdf")

def scale_plot():
    data = rows(FAIR / "scaling.csv")
    fig, axes = plt.subplots(1,2,figsize=(6.8,2.28),sharey=True)
    for ax,g in zip(axes,["Flickr","SupUser"]):
        sample = [r for r in data if r["graph"] == g]
        for metric,label,c,mark in zip(["cpu_s","gpu_s"],["Proposed CPU","Gatd GPU"],COLORS,"os"):
            ax.plot([int(r["percent"]) for r in sample],[float(r[metric]) for r in sample],
                    color=c,label=label,marker=mark,ms=4)
        ax.set(title=g, xlabel="Sampled vertices (%)",yscale="log",xticks=[20,40,60,80,100])
        ax.grid(axis="y",alpha=.25)
    axes[0].set_ylabel("Full build (seconds)")
    axes[0].legend(frameon=False)
    finish(fig,"scaling.pdf")

def query_plot():
    data=rows(SUB / "stack_query18_prefixes.csv")
    fig,(ax,zoom)=plt.subplots(1,2,figsize=(6.8,2.55),gridspec_kw={"width_ratios":[1.2,1]})
    x=np.array([int(r["prefix"]) for r in data])
    for metric,label,c,m in zip(["refined","topdown","bottomup"],["Verified index","Direct top-down","Direct bottom-up"],COLORS,"os^"):
        val=np.array([float(r[metric]) for r in data])
        lo=np.array([float(r[metric+"_min"]) for r in data])
        hi=np.array([float(r[metric+"_max"]) for r in data])
        for a in [ax,zoom] if metric!="bottomup" else [ax]:
            a.fill_between(x,lo,hi,color=c,alpha=.17,linewidth=0)
            a.plot(x,val,c=c,marker=m,ms=2.8,lw=1.4,label=label)
    ax.set(yscale="log",xticks=[1,5,9,14,18],ylabel="Cumulative seconds",title="All 18 queries")
    zoom.set(xlim=(10.8,16.2),ylim=(42,64),xticks=[11,12,13,14,15,16],title="Near the crossover")
    zoom.axvline(14,color=".45",ls=":",lw=.8)
    for a in [ax,zoom]:
        a.set_xlabel("Queries answered")
        a.grid(axis="y",alpha=.25)
    ax.legend(frameon=False,fontsize=7)
    finish(fig,"queries.pdf")

def mechanism_table():
    data=rows(SUB / "mechanism_runs.csv")
    result=[]
    for g in ["HepPh","Twitter","WebGoogle","HepPh_quarter","WebGoogle_quarter"]:
        for mode,label in [("full","Both"),("no_reuse","Reset"),("no_shift","No shift"),("opti","OptiUCF")]:
            group=[r for r in data if r["graph"]==g and r["arm"]==mode]
            timed=[r for r in group if r["status"]=="ok"]
            title=g.replace("_quarter",r" 25\%")
            if not timed:
                assert group and all(r["status"] == "timeout" for r in group)
                budget=max(int(r["budget_s"]) for r in group)
                result.append([title,label,f"$>{budget}$",r"\multicolumn{4}{c}{No final counters (timeout)}"])
                continue
            r=timed[0]
            phase_keys = {"opti_dp_cells"} if mode == "opti" else {"sweep_cells", "peel_cells"}
            def unit(key,scale):
                if key == "repeat_calls" or key in phase_keys:
                    return f"{int(r[key])/scale:,.3f}"
                assert not r[key]
                return "n/a"
            result.append([title,label,shown(median(float(x["seconds"]) for x in timed)),
                           unit("sweep_cells",1e9),unit("peel_cells",1e9),
                           unit("opti_dp_cells",1e9),unit("repeat_calls",1e6)])
    tex_rows("mechanisms.tex",result)

def certificates():
    data=record(SUB / "certificates/summary.json")
    result=[]
    for r in data:
        result.append([r["graph"].split(",")[0],f'{r["values"]:,}',f'{r["table_bytes"]/2**20:,.2f}',
                       f'{r["extra_witness_bytes"]/2**20:,.2f}',f'{median(r["build_s"]):,.2f}',
                       f'{median(r["verify_s"]):,.2f}',f'{max(r["verify_peak_mib"]):,}',
                       f'{r["lower_deficit"]*1e12:.2f}',f'{r["upper_excess"]*1e12:.2f}'])
    tex_rows("checks.tex",result)

def boundary_table():
    data = rows(FAIR / "query_prefixes.csv")
    result = [[r["last_eta"], r["ambiguous_vertex_levels"], r["gmp_calls"], r["topdown_max_different_vertices"]]
              for r in data if r["graph"] == "Flickr" and r["threads"] == "24"]
    assert len(result) == 9
    tex_rows("boundary.tex", result)

def precision_table():
    data = {r["case"]:r for r in rows(FAIR / "all_arms.csv") if r["method"] == "gpu"}
    result = []
    for name in ("Flickr", "SupUser", "DBLP", "BiomineDSAA", "Stack", "Orkut"):
        item = data[name.lower() + "_full"]
        mantissa, exponent = f'{float(item["max_error"]):.2e}'.split("e")
        err = "$" + mantissa + r"\times 10^{" + str(int(exponent)) + "}$"
        result.append([name.replace("BiomineDSAA","Biomine"), err,
                       item["max_count_above_1e5"], f'{float(item["worst_6dp_fraction"])*100:.2f}' + r"\%"])
    tex_rows("precision.tex", result)

if __name__ == "__main__":
    boundary_table()
    precision_table()
    build_table()
    scale_plot()
    query_plot()
    mechanism_table()
    certificates()
