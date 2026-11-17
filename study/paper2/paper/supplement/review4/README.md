# Reproducing the two-builder comparison

The public [reproduction guide](https://github.com/JiangInsight/ShiftedTail/blob/main/docs/REPRODUCE.md) supplies the current paths, setup commands and executed release checks. This directory retains the historical study protocol and evidence definitions. The sources formerly distributed in reproduction-source.zip are expanded in this repository's study directory. Obtain the large public graphs and toolchains using the public guide; old measurement-host paths below are not prerequisites.

## Graphs and probability inputs

From the paper2 directory, run `python paper/supplement/review4/figures.py service phases` to regenerate the two-builder query and worker-scaling figures from the released CSV files.

| Full inputs | Probability on one undirected edge |
|---|---|
| Flickr, DBLP | Released probabilities. The DBLP snapshot has 618,821 vertices. |
| Twitter, Biomine | Released probabilities. The last record for a repeated unordered pair supplies its probability. Self-loops are omitted. |
| SupUser, Stack, HepPh, Wiki-Pe, Deli | For event count (w), use (1-\exp(-w/2)). Repeated events belong to a single Bernoulli variable. |
| Orkut | Assign every friendship (1-\exp(-1/2)). |
| Web-Google, Cit-Patents | Draw one uniform per unordered pair in ascending endpoint order using NumPy default_rng(20261106). |
| CN15k projection | Merge training, validation and test relation records, drop self-loops and take the maximum confidence per unordered pair. |

[Dataset sources, hashes and parameters for all 13 graphs](inputs.csv) include two input identifiers per row. For the six early datasets the first is the original weighted CSR; for the seven later ones it identifies the source file(s) used by the preparation driver. The last is always the prepared construction input. Construction uses a single binary32 rounding followed by exact widening to binary64 for all competitors. The Stack and Flickr service workloads use their original binary64 CSR. Web-Google uses the quantized graph generated for that topology. [Input preparation and byte validation](artifact/prepare.py) · [Manifest generator](make_manifest.py)

Run the following commands from the extracted `paper2` directory after installing the source dependencies named in `results/fair_study/REPRODUCE.md` and `results/literature_coverage/REPRODUCE.md`. The timing scripts were used on Windows. Scratch files reside under `C:/vldb_paper2_fair`. Timing drivers launch programs serially and retain failures and capped runs.

| Purpose | Executable or driver |
|---|---|
| Input preparation | `code/prepare_study_inputs.py`, `code/study_real_inputs.py`; the extension uses `code/fair_study/literature_coverage.py` and `large_literature.py` in the same directory. |
| Construction table | `python code/fair_study/run_matched.py`, followed by `run_extension.py`, `literature_coverage.py`, `large_literature.py`, `deli_memory.py` and `extended_caps.py`. |
| Matched bound kernels, shortcuts and offset ladders | [Same-code protocol, commands and raw measurements](bounds/README.md). |
| Strict arithmetic and exact boundary workloads | [Compiler contracts, original witnesses and commands](arithmetic/README.md). |
| Same-backend UCEF and proposed service | See [service commands, evidence and exported witnesses](service/README.md). |
| Reuse and order verification | `python code/fair_study/submission_mechanisms.py` and `python code/fair_study/submission_certificates.py`. |
| Original first-use sessions | `python code/fair_study/run_queries.py`, `python code/fair_study/run_extension.py` and `python code/fair_study/submission_queries.py`. |
| CPU scheduling probes and GPU arithmetic | `python paper/supplement/review4/resources/build.py`, then the gpu, cpu, hub-match and deli invocations of run.py in that directory. |

The original Gatd source is commit `88b5ba7f60560363bc1579c7ee7984ee3541be6e`. Apply `results/study/gatd_windows.patch`, `results/study/gatd_reduction.patch`, and `code/fair_study/gpu_sparse.patch` in order. The first adapts the host build and file handling, the second repairs device-side reduction and synchronization, and the third writes eligible entries in common rank order. The new binary64 probe preserves this sparse writer. It converts the distribution, reductions, extrema and atomic probability minimum to double precision. Its two variants retain the six-decimal quantization or retain all computed digits through peeling. The legacy optional record writer is disabled in the matched protocol.

The corrected port uses CUDA 13.1, an RTX 5080 Laptop GPU, target `sm_120`, optimization `-O3`, relocatable device code, and the host switches in `build_windows.bat`. The CPU reconstruction uses MSVC and OpenMP. The independent checker has additional floating-point requirements detailed with its regression results. Each timing record identifies its executable and prepared input by SHA-256. Datasets and upstream sources remain subject to their original distribution terms.
