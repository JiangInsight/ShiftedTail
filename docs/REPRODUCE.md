# Reproducing ShiftedTail

The release contains the construction implementation, independent strict checker, inclusive GMP query backend, CPU reconstructions, adapters for author baselines, all study drivers, and the recorded observations used by the paper. `recorded/` is immutable evidence. New runs go into `work/`, `outputs/`, and the ignored `study/paper2/results/`. A workflow check is not a new measurement of the paper's speedups.

## Environment

The measured harness supports x64 Windows, Python 3.11+, Visual Studio C++ Build Tools with LLVM OpenMP, and Git. Install `requirements.txt`. The exact query backend also requires MinGW-w64 GCC, GMP and GSL. Set `CXX` to `g++.exe` and `GMP_ROOT` to the directory containing `include`, `lib`, and `bin`. The artifact used GCC 16.2, GMP 6.3.0, GSL 2.8, MSVC 14.51, and a 32-GiB process cap. Native binaries are rebuilt; no precompiled research executable is required.

The tested MSYS2 packages are available from the [UCRT64 repository](https://repo.msys2.org/mingw/ucrt64/): `mingw-w64-ucrt-x86_64-gmp-6.3.0-2-any.pkg.tar.zst` (SHA-256 `e82a75968a556484a50084578238a84eb60fb93e34986fd6695c537975bd39ea`) and `mingw-w64-ucrt-x86_64-gsl-2.8-1-any.pkg.tar.zst` (`841bb5f98a3a008bac2561483e230f7ecb44326c41161ce53634d2ce7a0ab3f5`). Extract both, then point `GMP_ROOT` at their `ucrt64` directory. Keep the compiler's and these libraries' runtime DLLs available; the launcher adds both directories to `PATH`.

```powershell
python -m pip install -r requirements.txt
$env:CXX = 'C:/toolchains/mingw64/bin/g++.exe'
$env:GMP_ROOT = 'C:/toolchains/deps/ucrt64'
python reproduce.py dependencies boost dai
python reproduce.py build
python reproduce.py smoke
```

The first two environment paths are examples to replace with installed toolchains. `dependencies` fetches fixed public commits. `build` creates the production builder, CTD/OptiUCF/UCEF controls, instrumentation for the reuse/shift ablations, the independent verifier, direct author query solvers, and strict FMA/non-FMA probes. `smoke` tests ten small uncertain graphs against exhaustive exact subset answers, 90 inclusive confidence queries, UCEF with one and three workers, corrupted certificates, 988 exact-rational endpoint enclosures, and 14 boundary queries against an independent exact oracle. Check `work/smoke-pass.json` and the accompanying logs.

## Public data and a full-graph comparison

```powershell
python reproduce.py fetch-data Twitter CN15kProjection Flickr SupUser
python reproduce.py prepare Twitter CN15kProjection Flickr SupUser
python reproduce.py benchmark work/literature_coverage/Twitter/Twitter.bin outputs/twitter --rounds 5 --threads 1
python reproduce.py benchmark work/matched/flickr_full/Flickr.bin outputs/flickr --rounds 5 --threads 1
```

These are full graph inputs, not the quarter-vertex ablation samples. Preparation rejects a graph if its shape or byte hash differs from the published [13-input manifest](../study/paper2/paper/supplement/review4/inputs.csv). CN15k's source hashes were recorded after Windows Git checkout; the downloader verifies the exact CRLF form and records the downloaded hash separately. Numerical input values are unchanged. Construction probabilities are rounded once to binary32 and widened to binary64 for every competitor. Original binary64 Stack/Flickr query inputs are distinct from this matched construction cohort.

The comparison rotates seven arms, checks every completed threshold against an independently verified reference, retains failures/timeouts, writes per-run hashes and logs, and produces CSV plus median/min/max summaries. All ablations use the selected worker count; OptiUCF is intrinsically one worker. Use `--threads 1` for the matched single-worker comparison. Each timed process is limited to 32 GiB and 300 seconds by default. Failed correctness checks abort; they do not become performance wins. Use a new output directory for each run. Do not run timed suites concurrently.

The same fetch/prepare commands accept `DBLP BiomineDSAA Stack Orkut WebGoogle CitPatents HepPh WikiTalkFR Deli`. DBLP/Biomine use the public DSAA archive; the script downloads it from its authors' linked Google Drive file. If that service requires interactive access, obtain the archive using its [source link](https://github.com/toggled/uncertainty/tree/c55c50d3b529f4d91410f85e82ccb060a06aa3c9) and place it at `study/paper2/data/study/uncertainty_dsaa_data.zip`. Hash-checked graph conversion remains mandatory. Large inputs require substantial download, scratch disk, and memory; Deli has 137,240,382 undirected edges after the stated projection. Inputs remain subject to their providers' terms and are fetched instead of republished.

## Original study suites

`benchmark` also writes `comparison.pdf` and `comparison.png`; `python reproduce.py plot <output>` redraws them from a fresh-run summary. These use only the selected output directory. Input integrity checks warm the filesystem cache; the timings are not cold-disk measurements.

The source layout keeps sibling `paper1` (shared graph converters and memory-cap launcher) and `paper2` under `study/`. It contains no dependency on a separate research checkout. Set these environment variables before invoking a historical suite directly:

```powershell
$env:PAPER2_ROOT = (Resolve-Path study/paper2).Path
$env:PAPER2_WORK = (Resolve-Path work).Path
$env:PAPER2_GCC = Split-Path $env:CXX
$env:PATH = "$env:PAPER2_GCC;$env:GMP_ROOT/bin;$env:PATH"
Set-Location study/paper2
```

Run the following serially after preparing the relevant inputs. All paths below are relative to `study/paper2`. The archived companion guides explain historical stage names and counters; the paths and setup above supersede their original machine paths.

| Paper evidence | Executable driver |
|---|---|
| Six main construction inputs and scaling/probability cohorts | `python code/fair_study/run_matched.py` |
| Seven additional complete graph topologies | `python code/fair_study/literature_coverage.py`, then `large_literature.py`, `deli_memory.py`, `extended_caps.py` in the same directory |
| Single-worker work counters and 25% controls | `python code/fair_study/submission_mechanisms.py` |
| Five-arm full-graph controls, 100 trials | `python paper/supplement/full_graph_extension/run.py . <fresh-output>`; its sibling `summarize.py` aggregates the ledger |
| Shifted/retained bound controls, shortcuts, offset grid | `paper/supplement/review4/bounds/run.py`: `build`, `first`, `repeat`, `legacy`, `shortcuts`, `shadow`, `report`; supply `--work "$env:PAPER2_WORK/review4_bounds" --inputs "$env:PAPER2_WORK/literature_coverage"` |
| Worker/capacity and GPU precision controls | `paper/supplement/review4/resources/build.py`; sibling `run.py` takes `cpu`, `gpu`, `hub-match`, `deli` |
| Query pilots, author direct baselines and Java controls | `code/fair_study/run_queries.py`, `run_extension.py`, `literature_queries.py`, `submission_queries.py` |
| Independent all-row certificates | `python code/fair_study/submission_certificates.py` |
| Strict arithmetic and exact boundary stress | `python code/review4_arithmetic/run.py build endpoint boundary` |
| Wiki-Pe archived certificate and fallback stars | Prepare `WikiTalkFR`, place the released `data/wiki` witnesses beside the graph, set `WIKI_CASE` to that directory, then `python code/review4_arithmetic/run.py wiki` |
| Two independently built certified query services | `code/revisions/review4_service/`: `build.py`, `study.py setup`, `study.py certify`, `test_witness.py`, `study.py manifest`, `study.py repeat_prep`, `study.py strict_verify`, `study.py queries`, `check_value_sort.py`, `report.py` |

`prepare.py query-prerequisites` in `paper/supplement/review4/artifact/` generates the original-precision certificates and repeated index-build charges used by the query pilots. Run this after preparing Flickr/SupUser/Stack and before those pilots. The frozen query manifest in `code/revisions/review4_service/requests/` preserves every original binary64 request, including boundary triples, without making UCEF depend on another producer's newly computed answers. Fresh strict verifier binaries are validated against the build manifest, not against one machine's archived executable hash.

Historical report scripts that assert an exact censoring cohort audit the recorded session; a different machine can have different timeout outcomes. The new `benchmark` command summarizes its own ledger without requiring the paper's timing cohort. The arithmetic checker uses strict floating-point flags and checks rounding/subnormal behavior at runtime. A successful numerical build alone is not a certificate. Homogeneous Orkut's values-only shortcut does not produce a removal-order witness; order-producing runs use the general construction path.

## Author baselines and GPU

The service suite now writes under `$env:PAPER2_WORK/results/review4_service`. Cached stages are reusable only when the command, binary, launcher, input/witness/request hashes and relevant environment still agree; their outputs must still exist and match. A changed or incomplete cache is rejected. `smoke` includes real-process regression checks for these cases.

UCEF is an in-memory threshold-stage reconstruction of Wen et al.'s Algorithm 5, not the complete external-memory/component-tree system. OptiUCF is a threshold reconstruction of Sun et al.; it excludes the optional query index. CTD shares graph preparation with the proposed builder. These labels also appear in the paper. Dai top-down/bottom-up and Bonchi DP/LB use pinned author sources; their native I/O, thread counts and numerical disagreements remain visible in the ledgers.

```powershell
python reproduce.py dependencies bonchi gatd
python reproduce.py java-check
$env:CUDA_PATH = 'C:/toolchains/cuda13.1'
$env:CUDA_ARCH = 'sm_120'
python reproduce.py build-gpu
python reproduce.py gpu-check work/literature_coverage/Twitter/Twitter.bin outputs/twitter/reference.thr outputs/twitter-gpu
```

Gatd is the author source at `88b5ba7f60560363bc1579c7ee7984ee3541be6e`, with the released Windows, synchronization/reduction, and sparse-output patches applied in order. All 14 staged source hashes must match the measured port before compilation. Choose a CUDA architecture supported by your GPU; the recorded machine used an RTX 5080 Laptop GPU and CUDA 13.1. The binary64 precision variants are generated by the resource suite. The baseline code and dependencies retain upstream licenses and attribution in their fetched checkouts. No upstream source is relabeled as this implementation.

## Figures and evidence

From the repository root, `python reproduce.py figures` regenerates the original tables and vector result figures from `recorded/results`, plus the service/worker figures from the released observations. Output is `study/paper2/paper/figures/`. `recorded/supplement/` retains the revision controls and their logs. Fresh benchmark output is deliberately separate. The [release check](validation/README.md) lists what was actually executed for this release; it does not claim that all giant-graph timing suites were rerun.
