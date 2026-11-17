
import csv
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
from run import ROOT,HERE,OUT,SUP,WIKI,GCC,ENV,js,call,digest

def build_msvc():
    target=OUT/"default_strict_verifier.exe"
    res=subprocess.run([str(ROOT/"code/build.bat"),str(ROOT/"code/verify_thresholds.cpp"),str(target)],cwd=OUT,capture_output=True)
    (SUP/"msvc_build.log").write_bytes(res.stdout+res.stderr)
    if res.returncode or not target.is_file():raise RuntimeError("MSVC build failed")
    return target
def main():
    msvc=build_msvc()
    graph=WIKI/"WikiTalkFR.bin";v=WIKI/"reference.thr";o=WIKI/"removals.bin"
    z=call([msvc,graph,v,o,1]);(SUP/"wiki_msvc.log").write_text(z.stdout+z.stderr)
    if z.returncode!=0:raise RuntimeError(z.stderr)
    doc={"msvc_sources":{p.name:digest(p) for p in [ROOT/"code/build.bat",ROOT/"code/verify_thresholds.cpp",ROOT/"code/verified_tail.hpp"]},"msvc_binary_sha256":digest(msvc),"wiki_status":z.returncode,"windows":platform.platform()}
    g,v,o=[OUT/n for n in ["positive_star.bin","positive_star.thr","positive_star.ord"]]
    launcher=[sys.executable,HERE/"verify_checked.py",g,v,o,1,"--fma-exe",msvc,"--portable-exe",OUT/"portable.exe"]
    for name,cmd,expected in [("retry_positive_star",launcher,0),("portable_positive_star",launcher+["--portable"],0),
                              ("bad_input",[*launcher[:2],OUT/"nonexistent.bin",*launcher[3:]],1)]:
        r=call(cmd);(SUP/(name+".log")).write_text(r.stdout+r.stderr)
        assert r.returncode==expected
        assert ("retrying" in r.stdout)==(name=="retry_positive_star")
        if name=="bad_input":assert "outward-nonfma" not in r.stdout
        doc[name]=r.returncode
    for tag in ("fma","portable"):
        d=call([GCC.parent/"objdump.exe","-d",OUT/(tag+".exe")],check=True)
        instr=sorted(set(re.findall(r"\bv(?:fmadd|fmsub|fnmadd|fnmsub)[a-z0-9]+",d.stdout)))
        if tag=="portable":assert not instr
        doc[tag+"_fused_instructions"]=instr
    js("release_validation.json",doc)
if __name__=="__main__":main()
