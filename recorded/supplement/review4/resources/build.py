
from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SCRATCH = Path(os.environ.get("UTHR_RESOURCE_SCRATCH", "C:/vldb_paper2_fair/review4_resources"))


def change(source, before, after, count=1):
    if source.count(before) != count:
        raise ValueError(f"unexpected source at {before!r}")
    return source.replace(before, after)


def build_cpu():
    source = (ROOT/"code/uthr_study.cpp").read_text(encoding="utf-8-sig")
    source = change(source, "const u32 chunk = static_cast<u32>(std::max(1, threads));",
                    """const char* capacity = std::getenv("UTHR_RESIDENT_LEVELS");
  const int requested = capacity ? std::atoi(capacity) : threads;
  if (requested < 1) throw std::invalid_argument("resident capacity must be positive");
  const u32 chunk = static_cast<u32>(requested);""")
    source = change(source, "  std::vector<Snap> snaps;", """  const bool cap_hubs = std::getenv("UTHR_CAP_HUB_TAIL") != nullptr;
  std::vector<Snap> snaps;""")
    source = change(source, "        int l = lo[u], h = hi[u];", """        const auto degree = C.G.off[u + 1] - C.G.off[u];
        const int last = cap_hubs && degree >= 50000 ? static_cast<int>(C.kmax) + 64 : static_cast<int>(degree);
        int l = lo[u], h = hi[u];""")
    source = change(source, "          S[h + 1] = p * S[h];", "          if (h < last) S[h + 1] = p * S[h];")
    source = change(source, "          ++h;\n          er +=", "          if (h < last) ++h;\n          er +=")
    work = SCRATCH/"cpu"
    work.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT/"code/verify_thresholds.exe", work/"verify.exe")
    variant = work/"builder.cpp"
    variant.write_text(source, encoding="utf8")
    env = dict(os.environ, CL=f'/arch:AVX2 /I"{ROOT / "code"}" /I"{ROOT / "baselines/boost_math/include"}"')
    with (work/"build.log").open("w") as log:
        subprocess.run([ROOT/"code/build.bat", variant, work/"builder.exe"], cwd=work,
                       env=env, stdout=log, stderr=subprocess.STDOUT, check=True)


def build_gpu(rounded):
    original = ROOT/"baselines/gatd_win_matched"
    work = SCRATCH/("fp64_6dp" if rounded else "fp64")
    work.mkdir(parents=True, exist_ok=True)
    for source in original.iterdir():
        if source.suffix in (".cu", ".cuh", ".h", ".hpp"):
            shutil.copyfile(source, work/source.name)
    p = work/"common.h"
    s = change(p.read_text(encoding="utf8"), "#define Float float", "#define Float double")
    s = s.replace("#define Fma fmaf", "#define Fma fma").replace("#define Fmin fminf", "#define Fmin fmin")
    p.write_text(s, encoding="utf8")
    p = work/"uco.cu"
    s = p.read_text(encoding="utf8")

    s = change(s, "atomicMin((int *)minCurthres, __float_as_int(minCurthresBlock));",
               "atomicMin(reinterpret_cast<unsigned long long*>(minCurthres), "
               "static_cast<unsigned long long>(__double_as_longlong(minCurthresBlock)));", 4)
    s = change(s, "fmaxf(curThres", "fmax(curThres", 2)
    s = change(s, "sum = roundf(sum * 1e6f) / 1e6f;",
               "sum = round(sum * 1e6) / 1e6;" if rounded else "", 5)
    p.write_text(s, encoding="utf8")
    script = (original/"build_windows.bat").read_text().replace(r"%~dp0..\..\tools\cuda13.1",
                                                                str(ROOT/"tools/cuda13.1"))
    (work/"build.bat").write_text(script)
    with (work/"build.log").open("w") as log:
        subprocess.run([work/"build.bat"], cwd=work, stdout=log, stderr=subprocess.STDOUT, check=True)


if __name__ == "__main__":
    for variant in sys.argv[1:] or ("cpu", "fp64", "fp64_6dp"):
        if variant == "cpu":
            build_cpu()
        elif variant in ("fp64", "fp64_6dp"):
            build_gpu(variant == "fp64_6dp")
        else:
            raise SystemExit(variant)
        binary = SCRATCH/variant/("builder.exe" if variant == "cpu" else "gatd.exe")
        with binary.open("rb") as f:
            print(variant, hashlib.file_digest(f, "sha256").hexdigest(), flush=True)
