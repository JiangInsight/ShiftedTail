
import hashlib
import os
from pathlib import Path
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SUP=ROOT/"paper/supplement/review4/arithmetic"
WIKI=Path(os.environ.get("WIKI_CASE","C:/vldb_paper2_fair/literature_coverage/WikiTalkFR"))
paths=[ROOT/"code/build.bat",ROOT/"code/verify_thresholds.cpp",ROOT/"code/graph.hpp",ROOT/"code/verified_tail.hpp",ROOT/"code/fair_study/boundary_query.hpp",
       *(HERE/n for n in ["run.py","endpoint_probe.cpp","boundary_probe.cpp","verify_checked.py","prepare_wiki.py","release_qa.py"])]
files={p.relative_to(ROOT).as_posix():p for p in paths}
files.update({"README.md":SUP/"README.md","wiki/reference.thr":WIKI/"reference.thr","wiki/removals.bin":WIKI/"removals.bin",
              "wiki/wiki_inputs.json":SUP/"wiki_inputs.json"})
dest=SUP/"reproduce.zip"
with zipfile.ZipFile(dest,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=3) as z:
    for name,p in sorted(files.items()):z.write(p,name)
    z.writestr("SHA256SUMS.txt","".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {name}\n" for name,p in sorted(files.items())))
with zipfile.ZipFile(dest) as z:
    assert z.testzip() is None
    for name,p in files.items():assert z.read(name)==p.read_bytes()
