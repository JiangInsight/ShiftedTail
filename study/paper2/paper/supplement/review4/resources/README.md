# Worker count, resident capacity and GPU precision

The CPU experiments vary workers (1, 4, 8, 24) at a fixed capacity of eight resident levels, then vary capacity (1, 4, 8, 24) at 24 workers. Their common endpoint runs once. The builder writes values and its actual removal order. A second process verifies both. The sweep processes eligible vertices in parallel; peeling processes the resident rows in parallel, one worker per row. Sweep and peel measure in-process computation. Build and verification wall times include I/O and process startup. The memory cap is 32 GiB. The scheduler and verification probes are single runs. These phase curves time the frozen checker, pinned when the scheduler is built. The Wiki-Pe hub value and order hashes are both identical to the inputs checked by the strict FMA and portable releases in the arithmetic study. Deli verification uses the new strict MSVC build; set UTHR_STRICT_CHECKER to the corresponding local executable to reproduce it.

On Deli we retain the original 24-level out-of-memory record and earlier single-level verified run. The new diagnostic uses 24 workers and four resident levels, with both the original sweep and the same high-degree cap used on Wiki-Pe. The four-level builds succeeded, so the two-level contingency was not run. Deli comparisons use the verified full 1,108,044,432-byte file under one_level/Deli.thr; the historical 24-level reference exhausted memory after writing a partial file. Increasing capacity may increase peeling parallelism and peak snapshot memory together.

The hub probe affects only the cross-level sweep of vertices with original degree at least 50,000. Its highest retained coordinate H is the maximum support-core number plus 64. Coordinate t of the updated survival distribution depends only on prior coordinates t and t-1. Truncating the array therefore preserves all initial keys in exact arithmetic. A shifted lower-bound lookup beyond H returns zero. This conservative choice can change queue order and recomputation counts. The original backing pool remains fully allocated. At the default tolerance 1e-30, binary64 rounds 1-1e-30 to 1, so the strict low-end comparison does not trim survivals close to one. The PMF used within peeling has its own trimming rule.

The GPU probes use binary32 arithmetic with the original six-decimal quantization, binary64 with six-decimal quantization retained, and unrounded binary64. They use the same corrected port, input CSR and rank-packed sparse writer. Its optional legacy dense writer is disabled. The binary64 kernel changes probability storage, FMA, extrema and reductions, including a 64-bit atomic minimum for finite nonnegative probabilities. Quantization is inside peeling and can change the entire subsequent removal sequence. On Flickr we compare partition multipliers 16, 32 and 64 in forward and reverse order. Each variant keeps the multiplier with the best mean wall time among those for which both outputs pass the 1e-4 gate. The choice is fixed on SupUser, Wiki-Pe and HepPh. Each gets two runs in opposite variant order. The reported maximum difference compares every entry to a separately checked CPU reference and does not constitute an independent certificate for a GPU result.

Run these commands from this directory after preparing the matched inputs and dependencies. Resume from the same output directory to preserve completed records. To repeat a series, use a new copy with an empty runs directory.

    python -B build.py cpu fp64 fp64_6dp
    python -B run.py gpu
    python -B run.py cpu
    python -B run.py hub-match
    python -B run.py deli

[Source adapters](build.py) · [Serial driver](run.py) · [Every run](measurements.csv)

## Running one witnessed build

After running the build script, these environment options enable the measured high-degree rule and a four-row capacity on a heterogeneous graph. Replace the graph, table and order filenames with the intended paths. The executable follows the standard production argument order.

    $env:UTHR_RESIDENT_LEVELS = '4'
    $env:UTHR_CAP_HUB_TAIL = '1'
    $env:UTHR_CERT_ORDER = 'output.ord'
    $env:UTHR_TOL = '1e-12'
    $env:UTHR_GROUP_BASE = '1'
    $env:UTHR_INDEXED = '1'
    $env:UTHR_COALESCE = '1'
    & 'C:/vldb_paper2_fair/review4_resources/cpu/builder.exe' graph.bin frontier 5 24 1 output.thr

The homogeneous closed-form output does not emit an order. For a witnessed build on an exactly constant input, set UTHR_NOHOMOGENEOUS=1 before invoking the builder; this selects the general path. The strict checker and its portable retry take the resulting graph, threshold table and order. [Checker and launcher](../arithmetic/README.md)
