from pathlib import Path
from statistics import median
from collections import defaultdict
import csv
import json
import sys


def main(data, out):
    rows=[json.loads(p.read_text()) for p in sorted(data.glob("*.json")) if p.name!="manifest.json"]
    assert len(rows)==100
    groups=defaultdict(list)
    for x in rows: groups[x["graph"],x["arm"]].append(x)
    for group, values in groups.items():
        assert len(values)==5 and {x["position"] for x in values}==set(range(1,6))
        done=[x for x in values if x["status"]=="ok"]
        if len(done)!=5: print(group,"completed",len(done),"of 5")
        else: assert max(x["max_abs"] for x in done)<=1e-9
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with (out/"trials.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=keys, lineterminator="\n"); w.writeheader();w.writerows(rows)
    suff=[]
    for key,values in groups.items():
        times=[x["seconds"] for x in values if x["status"]=="ok"]
        suff.append(dict(graph=key[0],arm=key[1],completed=len(times),timeouts=sum(x["status"]=="timeout" for x in values),
            skipped=sum(x["status"]=="not-repeated-after-timeout" for x in values),
            median_s=median(times) if times else "",min_s=min(times) if times else "",max_s=max(times) if times else ""))
    with (out/"summary.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=suff[0], lineterminator="\n"); w.writeheader();w.writerows(suff)
    for g in sorted({k[0] for k in groups}):
        print(g, {r["arm"]:round(r["median_s"],3) if r["completed"] else "censored" for r in suff if r["graph"]==g})


if __name__=="__main__": main(Path(sys.argv[1]),Path(sys.argv[2]))
