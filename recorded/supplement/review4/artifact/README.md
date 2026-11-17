# Reproduction kit

The full supplement contains archived observations under paper2/results, the manuscript and the revision suites. To regenerate its tables from the archived evidence, start in paper2 and run:

    python paper/verify_example.py
    python paper/make_figures.py results

For new measurements, extract reproduction-source.zip into an empty directory, keeping its sibling paper1 and paper2 layout. This small companion has the local C++/CUDA patches, native and Java adapters, Python drivers, original implementation snapshots, compiler drivers and input manifests. Its SHA256.json covers every member. Historical timing drivers resume existing case records and cannot reconstruct missing large scratch files from those records. Start with an empty scratch path on the measurement machine and keep archived observations in a separate extraction. The commands below run from the newly extracted paper2 directory. The original machine used Windows; timings are machine-dependent.

    python paper/supplement/review4/artifact/artifact.py source-zip <path-to-reproduction-source.zip>
    python paper/verify_example.py

## Toolchains and pinned sources

Use Python 3.11+ with NumPy, pandas, requests and Matplotlib (host versions 2.4.6, 2.2.3, 2.32.5 and 3.10.9 respectively), Git, a Java JDK with java and javac on PATH, Visual Studio 18 Community with MSVC x64 C++ and LLVM OpenMP, WinLibs GCC 16.2 x64 UCRT/OpenMP, and CUDA 13.1 for the GPU suite. The native builders use /O2 /Oi /GL /std:c++20 /openmp:llvm /arch:AVX2 and LTCG. The historical MSVC batch files expect vcvars64.bat under the standard VS18 Community location. Put the full WinLibs distribution in ../paper1/tools/dl_winlibs/mingw64, or make a directory junction there to the installed distribution. Several historical drivers look for g++.exe relative to the extracted paper2 root. Place the NVIDIA toolkit in tools/cuda13.1, or make a junction to the local toolkit. The NVIDIA port used sm_120 and -rdc=true. Double-precision GPU variants are generated from the patched float source in the resource suite.

Use an empty C:/vldb_paper2_fair as the scratch root for the historical series. Current suite-specific options are documented with their drivers. Set up dependencies once in PowerShell:

    $work = 'C:/vldb_paper2_fair'
    New-Item -Force -ItemType Directory $work,baselines | Out-Null
    git clone https://github.com/boostorg/math baselines/boost_math
    git -C baselines/boost_math checkout f1b0b95a04f56717b3454cb599e0647770c5852e
    git clone https://github.com/AbigailJixiangyuyu/uco-gpu baselines/gatd
    git -C baselines/gatd checkout 88b5ba7f60560363bc1579c7ee7984ee3541be6e
    git clone https://github.com/qq-dai/UncertainCore "$work/UncertainCore"
    git -C "$work/UncertainCore" checkout 315dee85ff5aae487c296a99fb600304bbee0f24
    git clone https://github.com/fgullo/uncertaincores "$work/bonchi_public"
    git -C "$work/bonchi_public" checkout 370b2dbcaa02a3466a2afd10e24cd52019c3edb3
    git clone https://github.com/stasl0217/UKGE "$work/UKGE_source"
    git -C "$work/UKGE_source" checkout 5049b84501657abc44c36dd7d2db5f8519e5ee8f

Unpack MSYS2 UCRT64 GSL 2.8-1 and GMP 6.3.0-2 into $work/deps, retaining the ucrt64/include, lib and bin layout. Verify the downloaded packages against the SHA-256 digests below. The historical direct solver uses GSL, gslcblas and GMP; inclusive query refinement uses gmpxx and GMP. Set PATH to include the GNU and GMP bin directories for direct invocations. BOOST_MATH_INCLUDE, DAI_SRC, CXX and GMP_ROOT can point the smoke/build helper at existing dependency installations. The historical CPU-build command below produces the frozen row checker used by the timings; the current rigorous checker with monitored arithmetic is built separately.

    841bb5f98a3a008bac2561483e230f7ecb44326c41161ce53634d2ce7a0ab3f5  mingw-w64-ucrt-x86_64-gsl-2.8-1-any.pkg.tar.zst
    e82a75968a556484a50084578238a84eb60fb93e34986fd6695c537975bd39ea  mingw-w64-ucrt-x86_64-gmp-6.3.0-2-any.pkg.tar.zst

    python paper/supplement/review4/artifact/artifact.py cpu-build
    python paper/supplement/review4/artifact/artifact.py gpu baselines/gatd --output baselines/gatd_win_matched
    & ./baselines/gatd_win_matched/build_windows.bat
    python paper/verify_example.py code/verify_thresholds.exe
    python paper/supplement/review4/artifact/release_smoke.py --strict

The GPU staging command reads committed upstream bytes, applies the Windows port and reduction patches to the upstream root, and applies the sparse-writer patch inside src/. It validates every resulting CUDA/header hash against the measured source before installing it. The sequential command-line CPU peers are the local OptiUCF threshold reconstruction and shared CTD kernel. UCEF is the local in-memory threshold-stage reconstruction and has separate one- and multi-worker controls. Dai's bottom-up/top-down algorithms and Bonchi's Java DP/LB are pinned public author sources. No paper table reports locally measured Galois/Julienne/Medusa/Gunrock uncertain-core adaptations.

## Graph files and two precision cohorts

The 13-row inputs.csv supplies per-file checksums and graph rules. For its six early graphs, original_file_sha256 is the unrounded binary64 CSR. For the seven later inputs, that field identifies raw source files, not an additional unrounded CSR. Their construction and service graphs are the prepared matched CSR, including Web-Google. Original Stack and Flickr service inputs must be kept separate from their quantized construction inputs. All construction files store probabilities after one binary32 rounding and a widening to binary64. The file starts with (uint32 n,uint64 directed_arc_count), then n int32 degrees, int32 adjacency IDs and binary64 probabilities, all little-endian.

Put sx-superuser.txt.gz, sx-stackoverflow.txt.gz and com-orkut.ungraph.txt.gz from SNAP in data/study. Put the DSAA data archive at data/study/uncertainty_dsaa_data.zip; its two members used here are data/large/biomine.txt and data/casestudy/dblp.txt. The upstream README provides the [dataset download](https://github.com/toggled/uncertainty/blob/c55c50d3b529f4d91410f85e82ccb060a06aa3c9/README.md). Flickr and Twitter use the pinned Bonchi checkout above. Place [HepPh](https://nrvis.com/download/data/dynamic/ca-cit-HepPh.zip) at $work/hepph_events.zip. Put the SNAP web-Google.txt.gz and cit-Patents.txt.gz in data/study. Wiki-Pe and Deli are downloaded by the preparation driver, or may be placed at $work/wiki_fr_events.zip and $work/delicious_ti.zip first. Snapshot sizes and hashes are recorded in inputs.csv; input-specific JSONs in recorded/results identify each extended loader.

    New-Item -Force -ItemType Directory ../paper1/data/bin,results,data/study | Out-Null
    python ../paper1/code/prep_temporal.py data/study/sx-stackoverflow.txt.gz results/stack.tbin
    python code/prep_wbin.py results/stack.tbin results/stack.wbin
    python ../paper1/code/prep.py data/study/com-orkut.ungraph.txt.gz ../paper1/data/bin/com-orkut.bin
    python ../paper1/code/prep.py data/study/web-Google.txt.gz ../paper1/data/bin/web-Google.bin
    python ../paper1/code/prep.py data/study/cit-Patents.txt.gz ../paper1/data/bin/cit-Patents.bin
    python paper/supplement/review4/artifact/prepare.py Flickr SupUser Stack Orkut DBLP BiomineDSAA
    python paper/supplement/review4/artifact/prepare.py HepPh CN15kProjection Twitter WebGoogle CitPatents WikiTalkFR Deli

The script calls the original converters and checks all prepared graphs against the recorded byte hashes. To independently check an existing original/matched pair:

    python paper/supplement/review4/artifact/artifact.py input Flickr original data/study/Flickr.bin
    python paper/supplement/review4/artifact/artifact.py input Flickr matched C:/vldb_paper2_fair/matched/flickr_full/Flickr.bin

## Measurements and tables

Run complete timing suites serially. On a new machine a budgeted case can change status. Preserve its new log. Historical reports that assert an exact censoring cohort are audits of the reported session. For the archived paper tables, the rendering command above consumes the shipped observations.

    New-Item -Force -ItemType Directory results/study | Out-Null
    Copy-Item ../recorded/results/study/input_manifest.json results/study/input_manifest.json -Force
    python paper/supplement/review4/artifact/prepare.py query-prerequisites
    python code/fair_study/run_matched.py
    python code/fair_study/run_queries.py
    python code/fair_study/run_extension.py
    python code/fair_study/literature_coverage.py
    python code/fair_study/literature_queries.py
    python code/fair_study/large_literature.py
    python code/fair_study/deli_memory.py
    python code/fair_study/extended_caps.py
    python code/fair_study/submission_mechanisms.py
    python code/fair_study/submission_queries.py
    python code/fair_study/submission_queries.py --extended
    python code/fair_study/submission_certificates.py
    python code/fair_study/summarize.py
    python code/fair_study/literature_report.py
    python code/fair_study/submission_report.py
    python paper/make_figures.py results

For the latest study use the corresponding suite; output names and CSV definitions accompany the logs.

| Evidence | Drivers, executed from paper2 unless specified |
|---|---|
| Formula comparison, numerical shortcuts and grid sensitivity | From paper/supplement/review4/bounds run python run.py build, first, repeat, legacy, shortcuts, shadow, report as separate invocations. The full checksums and counters are in summary.csv, groups.csv, tightness.csv and logs/. |
| Worker/capacity curves, capped hub sweep and GPU precision | python paper/supplement/review4/resources/build.py, then python paper/supplement/review4/resources/run.py with gpu, cpu, hub-match and deli separately; measurements.csv contains the ledger. |
| Arithmetic and boundary stress | From the arithmetic suite's extracted reproduce.zip use its README and checksummed Wiki-Pe witness: python code/review4_arithmetic/run.py build endpoint boundary, then python code/review4_arithmetic/run.py wiki using the supplied witness and documented graph. The interval backend uses explicit std::fma or separately outward-rounded operations. GCC flags include -fno-fast-math -frounding-math -ffp-contract=off and respectively -mfma or -mno-fma. |
| Two builders, independent checking and confidence-order study | Follow the [service guide](../service/README.md) from paper2. Its commands include the numerical and strict checks, comparison against value sorting, and separate repeated preparation and query phases. Its reproduction.zip and raw_records.zip identify the frozen inputs and runner. |

The arithmetic and service bundles include version-specific fixtures. The full supplement has raw outcomes for censored and failed cases as well as completed runs. Building the paper needs pdfLaTeX, BibTeX and the included figures. The artifact contains no author credentials and requires no account on the measurement host.

[Clean-host-path smoke result](clean_build.json) records the tested production-source fingerprints and compiler outputs. The check used a new extracted tree with public dependencies mounted from the tested installations. It built the CPU drivers, ran the ten exact small graphs, and exercised both strict arithmetic variants. Full graph timing and CUDA compilation were separate study runs; staging verifies all three CUDA source patches against the timed port.
