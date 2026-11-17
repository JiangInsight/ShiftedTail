
import argparse
from pathlib import Path
import subprocess
import sys

def main():
    p=argparse.ArgumentParser()
    p.add_argument("graph");p.add_argument("values");p.add_argument("order");p.add_argument("threads")
    p.add_argument("--fma-exe",type=Path,default=Path("verify_fma.exe"))
    p.add_argument("--portable-exe",type=Path,default=Path("verify_portable.exe"))
    p.add_argument("--portable",action="store_true",help="skip the fused build entirely")
    args=p.parse_args()
    files=[args.graph,args.values,args.order,args.threads]
    def check(exe,name):
        print(f"arithmetic_backend={name}",flush=True)
        return subprocess.run([str(exe.resolve()),*files]).returncode
    if not args.portable:
        status=check(args.fma_exe,"strict-fma")
        if status!=3:return status
        print("fused row error exceeded 1e-9; retrying the same input with outward bounds",flush=True)
    return check(args.portable_exe,"outward-nonfma")

if __name__=="__main__":
    try: raise SystemExit(main())
    except OSError as e:
        print(e,file=sys.stderr);raise SystemExit(1)
