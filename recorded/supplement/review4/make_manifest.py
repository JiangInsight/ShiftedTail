
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
RESULTS = BASE/"results"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


original = {row["graph"]:row for row in read(RESULTS/"study/input_manifest.json")}
full = {row["graph"]:row for row in read(RESULTS/"fair_study/matched_inputs.json") if row["kind"]=="full"}
rules = {
    "Flickr": "Input edge probabilities from the released uncertain network",
    "SupUser":"Drop loops; count unordered event pairs; p=-expm1(-w/2)",
    "Stack":"Drop loops; count unordered event pairs; p=-expm1(-w/2)",
    "Orkut":"Unweighted friendship graph; set w=1, p=-expm1(-1/2)",
    "DBLP":"Distributed DSAA snapshot, supplied edge probabilities",
    "BiomineDSAA":"Distributed DSAA snapshot, final occurrence per unordered pair; omit loops",
}
rows = []
for name, matched in sorted(full.items()):
    source=original[name]
    rows.append(dict(graph=name,vertices=matched["n"],edges=matched["edges"],source=source["source"],
                     rule=rules[name],seed="",p_min=matched["p_min"],p_max=matched["p_max"],
                     original_file_sha256=source["bin_sha256"],matched_file_sha256=matched["binary_sha256"]))
for path in sorted((RESULTS/"literature_coverage").glob("*_input.json")):
    source=read(path)
    raw_hash=source.get("input_sha256","")
    rows.append(dict(graph=source["graph"],vertices=source["vertices"],edges=source["edges"],
                     rule=source["rule"],seed=source.get("seed",""),source=source["source"],
                     p_min=source["p_min"],p_max=source["p_max"],
                     original_file_sha256=json.dumps(raw_hash,sort_keys=True) if isinstance(raw_hash,dict) else raw_hash,
                     matched_file_sha256=source["binary_sha256"]))
assert len(rows)==len({r["graph"] for r in rows})==13
with (HERE/"inputs.csv").open("w",newline="",encoding="utf8") as out:
    w=csv.DictWriter(out,fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
