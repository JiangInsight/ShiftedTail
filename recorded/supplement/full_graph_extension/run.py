
import argparse
import json
from pathlib import Path
import re
import sys
import tempfile


def run(root, out):
    sys.path.insert(0, str(root / "code/fair_study"))
    import run_matched as rm
    from submission_mechanisms import BUILD
    from run_extension import environment
    from literature_coverage import SCRATCH

    cpu, ucef = BUILD / "uthr_study.exe", rm.WORK / "ucef.exe"
    checker = root / "code/verify_thresholds.exe"
    arms = ["both", "no_shift", "reset", "neither", "ucef"]
    cases = {"Flickr": rm.ART/"flickr_full", "SupUser": rm.ART/"supuser_full",
             "DBLP": rm.ART/"dblp_full", "CN15kProjection": SCRATCH/"CN15kProjection"}
    out.mkdir(exist_ok=True, parents=True)
    limit = 90
    manifests = {"worker": 1, "seconds_limit": limit, "rounds": 5, "sha256": {}, "graphs": {}}
    for program in [cpu, ucef, checker]:
        manifests["sha256"][program.name] = rm.digest(program)
    for name, folder in cases.items():
        graph = folder/(name+".bin")
        ref, order = folder/"reference.thr", folder/"removals.bin"
        manifests["graphs"][name] = [rm.digest(f) for f in [graph, ref, order]]
    mf = out/"manifest.json"
    text = json.dumps(manifests, indent=2)
    if mf.exists() and mf.read_text()!=text:
        raise ValueError("A measured input changed")
    mf.write_text(text)
    for ci, (name, folder) in enumerate(cases.items()):
        graph = folder/(name+".bin")
        ref = folder/"reference.thr"
        check_log = out/(name+"-verification.log")
        completed, _ = rm.process([checker, graph, ref, folder/"removals.bin", 1], environment(1), check_log, 900)
        if completed!="ok":
            raise RuntimeError(f"{name}: failed reference verification")
        censored = set()
        for rep in range(5):
            pivot = (rep+ci) % len(arms)
            for pos, arm in enumerate(arms[pivot:]+arms[:pivot]):
                tag = f"{name}-{rep+1}-{arm}"
                record = out/(tag+".json")
                if record.exists():
                    if json.loads(record.read_text())["status"]=="timeout": censored.add(arm)
                    continue
                row = dict(graph=name, arm=arm, repetition=rep+1, position=pos+1, status="not-repeated-after-timeout")
                if arm not in censored:
                    env = environment(1)
                    if arm in ("reset","neither"): env["UTHR_RESET_LEVEL"]="1"
                    if arm in ("no_shift","neither"): env["UTHR_NOLB"]="1"
                    with tempfile.TemporaryDirectory() as scratch:
                        dst=Path(scratch)/"rows.thr"
                        cmd=[ucef,graph,1,dst] if arm=="ucef" else [cpu,graph,"frontier",5,1,1,dst]
                        log=out/(tag+".log")
                        status,elapsed=rm.process(cmd,env,log,limit)
                        row.update(status=status,seconds=elapsed)
                        if status=="timeout":
                            censored.add(arm)
                        elif status=="ok":
                            row.update(rm.compare(ref,dst),output_sha256=rm.digest(dst))
                            if row["max_abs"]>1e-9:
                                raise ValueError(f"{tag}: threshold mismatch {row}")
                            match=re.search(r"^work (.+)$",log.read_text(),re.M)
                            if match:
                                row.update({k:int(v) for k,v in (f.split("=") for f in match[1].split())})
                        else:
                            raise RuntimeError(tag+" "+status)
                temp=record.with_suffix(".tmp")
                temp.write_text(json.dumps(row)); temp.replace(record)
            print(name,rep+1,"complete",flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("project",type=Path); p.add_argument("out",type=Path)
    args=p.parse_args()
    run(args.project.resolve(),args.out.resolve())
