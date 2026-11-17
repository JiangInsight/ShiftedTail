
import csv
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
DEST=HERE.parents[1]/"figures"
plt.rcParams.update({"font.size":8,"font.family":"DejaVu Sans","pdf.fonttype":42,
                     "axes.spines.top":False,"axes.spines.right":False,"axes.linewidth":.65,
                     "xtick.major.width":.6,"ytick.major.width":.6,"lines.linewidth":1.45})
COLORS=("#006158","#ac4b25","#385681","#6b5868")


def rows(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))


def service():
    data=rows(HERE/"service/prefixes.csv")
    fig, axes=plt.subplots(1,2,figsize=(3.34,1.87),constrained_layout=True)
    styles=[("frontier","Shifted-tail index","o"),("ucef","UCEF index","s"),
            ("topdown","Top-down","^"),("bottomup","Bottom-up","D")]
    handles,labels=[],[]
    for ax,graph,title in zip(axes,("WebGoogle","Stack"),("Web-Google","Stack Overflow")):
        for color,(method,label,marker) in zip(COLORS,styles):
            r=sorted((v for v in data if v["graph"]==graph and v["sequence"]=="original" and v["method"]==method),
                     key=lambda v:int(v["prefix"]))
            if not r: continue
            x=[int(v["prefix"]) for v in r]
            line,=ax.plot(x,[float(v["end_to_end_s"]) for v in r],color=color,marker=marker,
                          markersize=3,markevery=(2 if graph=="Stack" else 1),label=label)
            if method in ("frontier","ucef"):
                ax.fill_between(x,[float(v["end_to_end_min_s"]) for v in r],
                                  [float(v["end_to_end_max_s"]) for v in r],color=color,alpha=.13,linewidth=0)
            if label not in labels: handles.append(line);labels.append(label)
        ax.set_title(title,fontsize=8);ax.set_ylim(bottom=0)
        ax.set_xticks([1,3,5,7,9] if graph=="WebGoogle" else [1,6,12,18])
        ax.grid(axis="y",alpha=.18)
    axes[0].set_ylabel("Cumulative time (s)")
    fig.supxlabel("Requests answered",fontsize=8)
    fig.legend(handles,labels,loc="outside upper center",ncol=2,frameon=False,
               fontsize=7,handlelength=1.4,columnspacing=1.0)
    fig.savefig(DEST/"service_producers.pdf",metadata={"CreationDate":None});plt.close(fig)


def phases():
    data=[r for r in rows(HERE/"resources/measurements.csv") if r.get("capacity") and
          r["status"]=="ok" and r["rep"]=="1" and r["hub_cap"]=="False"]
    fig,axes=plt.subplots(1,3,figsize=(6.0,1.52),constrained_layout=True)
    for ax,g,title in zip(axes,("HepPh","WikiTalkFR"),("HepPh","Wiki-Pe")):
        subset=sorted((r for r in data if r["graph"]==g and r["capacity"]=="8"),key=lambda r:int(r["workers"]))
        assert len(subset)==4
        x=[int(r["workers"]) for r in subset]
        for color,key,title_key,marker in zip(COLORS,("sweep_s","peel_s","verify_wall_s"),
                                              ("Sweep","Peel","Check"),("o","s","^")):
            ax.plot(x,[float(r[key]) for r in subset],color=color,marker=marker,markersize=3.5,label=title_key)
        ax.set_title(title);ax.set_xlabel("Workers (8 levels)");ax.set_xticks([1,4,8,24])
        ax.set_yscale("log");ax.grid(axis="y",alpha=.18)
    axes[0].set_ylabel("Time (s, log scale)")
    axes[1].legend(loc="center right",frameon=False,fontsize=7,handlelength=1.3)
    for color,g,name,marker in zip(COLORS,("HepPh","WikiTalkFR"),("HepPh","Wiki-Pe"),("o","s")):
        subset=sorted((r for r in data if r["graph"]==g and r["workers"]=="24"),key=lambda r:int(r["capacity"]))
        assert len(subset)==4
        axes[2].plot([int(r["capacity"]) for r in subset],[int(r["build_peak_mib"]) for r in subset],
                     color=color,marker=marker,markersize=3.5,label=name)
    axes[2].set_title("Builder memory");axes[2].set_xlabel("Resident levels (24 workers)")
    axes[2].set_ylabel("Peak (MiB)");axes[2].set_xticks([1,4,8,24]);axes[2].set_ylim(bottom=0)
    axes[2].legend(loc="best",frameon=False,fontsize=7,handlelength=1.3);axes[2].grid(axis="y",alpha=.18)
    fig.savefig(DEST/"worker_phases.pdf",metadata={"CreationDate":None});plt.close(fig)


if __name__=="__main__":
    for name in sys.argv[1:] or ("service","phases"):
        {"service":service,"phases":phases}[name]()
