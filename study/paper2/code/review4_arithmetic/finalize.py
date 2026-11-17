
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
from run import ROOT,HERE,OUT,SUP,WIKI,GCC,GMP,digest,wiki_dimensions

def run(*args,env=None):
    subprocess.run([sys.executable,"-B",*map(str,args)],cwd=ROOT,env=env,check=True)
wiki_dimensions()
run(HERE/"run.py","recompile_boundary","boundary","stars")
run(HERE/"release_qa.py")
with (SUP/"witness_stats.csv").open() as f:
    positive={r["backend"]:r["max_upper_excess"] for r in csv.DictReader(f) if r["case"]=="positive_star"}
doc=SUP/"README.md";txt=doc.read_text()
key=" The same experiment with every edge probability"
if key not in txt:
    txt=txt.replace("Portable success on that example",f"The same experiment with every edge probability and every submitted threshold equal to 2^-60 gives D-plus={positive['fma']} fused and {positive['portable']} portable. One edge attains the claimed threshold and every nonempty feasible positive-level set contains a leaf. Portable success on that example")
    doc.write_text(txt)
run(HERE/"bundle.py")
dest=OUT/"release_extract"
dest.mkdir(exist_ok=False)
with zipfile.ZipFile(SUP/"reproduce.zip") as z:z.extractall(dest)
env=dict(os.environ,CXX=str(GCC),GMP_ROOT=str(GMP),WIKI_CASE=str(dest/"wiki"))
test=dest/"code/review4_arithmetic"
run(test/"prepare_wiki.py",WIKI.parents[1]/"wiki_fr_events.zip",dest/"wiki/WikiTalkFR.bin",env=env)
run(test/"run.py","build","endpoint","boundary","wiki",env=env)
re=dest/"paper/supplement/review4/arithmetic"
assert (re/"endpoint_cases.csv").read_bytes()==(SUP/"endpoint_cases.csv").read_bytes()
def read(path):
    with path.open() as f:return list(csv.DictReader(f))
ignore_fields={"elapsed_s","exact_s","service_s","load_s"}
for name in ["witness_stats.csv","boundary_cases.csv"]:
    a,b=read(SUP/name),read(re/name)
    normalize=lambda rows:[{k:v for k,v in r.items() if k not in ignore_fields} for r in rows]
    assert normalize(a)==normalize(b),name
manifest=dict(archive_sha256=digest(SUP/"reproduce.zip"),source_archive_files=len(z.namelist()),
                graph_sha256=digest(dest/"wiki/WikiTalkFR.bin"),byte_identical_endpoint_csv=True,
                witness_nontiming_fields_identical=True,all_14_answer_vectors_compared_to_exact=True)
(SUP/"clean_reproduction.json").write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest))
