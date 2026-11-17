# Responses to the all-confidence index reviews



## Which results belong to the builder?



The index format, independent checker and inclusive membership test can also serve a table from another producer. Our UCEF reconstruction outputs its own thresholds. Its preparation time also includes constructing a suitable removal order, verifying the rows and exporting the rank map. The service study keeps the thresholds from each producer separate and charges each path to its first client request. The 13-graph construction table compares algorithms that materialize the same eligible thresholds from the same probabilities. Its clock and inputs differ from first-use service.



On Web-Google the median initial charge over three runs was 3.752 s for UCEF (3.267–3.891 s) and 9.646 s for our producer (9.164–9.662 s). Through nine original requests the full totals were 3.955, 9.776 and 6.052 s for UCEF, our index and bottom-up. The UCEF crossing occurs at query seven with median preparation, or 7, 6 and 7 using the individual preparations. Our index does not cross. On Stack the analogous preparation medians were 98.494 s (94.019–100.855 s) and 57.618 s (57.436–57.828 s). The shifted-tail producer crosses top-down at query 13 for all three preparations. UCEF does not cross. The original 18-request totals in this new cohort were 99.408, 58.582 and 79.464 s for UCEF, the shifted-tail producer and top-down. The earlier three-run full-session experiment on the shifted-tail producer had a median-prefix crossover at query 14. These results charge a complete output to all methods. The new reconstruction timings use the strict checker for both producers. [Complete prefixes and hexadecimal confidences](service/prefixes.csv)

Across all 180 paired index requests from 13 sessions, the full integer outputs agree byte for byte. The two numerical tables and witness orders need not coincide. For the five Web-Google sequences with matching direct answers, UCEF crossed at requests six or seven and the shifted-tail builder never crossed by nine. For the six matching Stack sequences UCEF never crossed; the shifted-tail builder crossed once at 12, four times at 13 and once at 14. Moving the graph-loading request ($0.95$) to the front increased the first index prefix from 0.228 to 0.527 s. Direct times also varied. Under boundary-focused confidences, the Web-Google bottom-up and Stack top-down comparators disagreed with the verified answers on 3 of 9 and 13 of 18 requests, respectively. Their clocks do not represent equivalent-answer crossovers. [Methods, prefix timestamps and vector hashes](service/prefixes.csv)

## When does combining the bounds save time?



For the same retained neighbors, the maximum of the shifted lower bound, a retained top-$k$ product and a binomial tail based on the smallest retained probability is at least as strong as any of the three. Finding the surviving extrema and top probabilities requires additional adjacency probes. On Twitter, combining the bounds saved 397.5 million peel cells but required 166.0 million such probes. The implementation took 2.006 s against 0.963 s for shift alone. On CN15k it took 1.341 s against 0.632 s. Shadow evaluation used one fixed removal order so that deletion counts, neighborhoods and current thresholds were the same for the two comparisons. A different output order is allowed in the actual executions. The retained-only arm isolates the two OptiUCF lower bounds; the separately measured full OptiUCF reconstruction also has its own upper bound, activation policy and evaluation kernel. [Full-table timings](bounds/summary.csv) · [Same-neighborhood comparisons](bounds/groups.csv) · [Tightness against recomputed tails](bounds/tightness.csv)



## Which builder shortcuts mattered?



The default offset ladder retains progressively fewer offsets per unit deletion distance. Capping it at eight increased peel work from 0.755 to 1.990 billion cells on Twitter and from 0.202 to 1.060 billion on CN15k. From the default, four offsets per octave reduced the respective counts to 0.709 and 0.184 billion. Disabling the global minimum-probability floor increased work by 11.6% on Twitter and made no difference on CN15k. Turning off trimming increased work by 8.5% and 7.1%. Setting the shortcut tolerance to zero caused 2.5% and 3.2% more reevaluations. Across all 74 construction runs the independent checker accepted the complete table and order at the same tolerance. The data distinguish numerical approximation in a producer from the error actually verified for its output. [Protocol, complete controls and legacy numerical kernel](bounds/README.md)



## Which fixed-confidence algorithms apply?



Guo et al. use the same marginal degree-survival predicate as Equation (1) for a fixed confidence. Their screened M-PA uses two stages to concentrate peeling on candidate vertices for dense cores. A service returning a dense vector at all levels would additionally need answers for the screened vertices. A deterministic core framework or a core-membership probability in a random sampled graph also changes the computation being timed. [Guo et al., ASONAM 2021](https://doi.org/10.1145/3487351.3489470)



## What if the graph changes?



A verified row is tied to its edge probabilities and eligible ranks. After an edit, a row's candidate superlevel sets may cease to support their lower endpoints, and its suffix ordering may fail to establish the upper endpoints. A dynamic producer could update the graph and offer revised rows and orders for certification. Identifying a smaller set of affected witness checks would require an additional argument about the changed supports. Our timings concern confidence changes on a fixed graph.



## What exactly does the arithmetic check establish?



For 494 small inputs per kernel an independent integer coefficient convolution enclosed the exact tail in all 988 computed intervals. The longest oracle denominator had 12,889 bits. The strict fused implementation requires IEC binary64 intermediates, nearest-even rounding, gradual underflow, explicit FMA and the supplied build flags. The portable version instead encloses the complement, two products and sum at each recurrence step. Its launcher can retry a table rejected by the fused error budget; invalid inputs and unsupported arithmetic environments still fail. On a star with 280,000 leaves and edge probabilities $2^{-60}$ the first-level thresholds are exactly $2^{-60}$. The fused upper discrepancy was $1.05738\times10^{-9}$, outside the $10^{-9}$ gate; the launcher automatically retried the same table and order with the portable checker, which passed at $2.43\times10^{-13}$. The all-zero star also exercised this fallback. On the full Wiki-Pe input both accepted. Single-worker checks took 1.51 and 31.95 s, respectively. A million original neighbors do not all appear in a verification subgraph. The lower and upper witness degrees peaked at 2,258 and 2,237; the longest fused recurrence actually consumed 244 and 235 factors. [Witness statistics](arithmetic/witness_stats.csv) · [Exact endpoint oracle](arithmetic/endpoint_summary.json)



Naive ordering by value and vertex rank failed independently on both UCEF tables with upper excess near one. The tie-aware postprocessor took median 0.614 s on Web-Google and 6.539 s on Stack. Successful witnesses reduced those upper excesses to $2.034\times10^{-10}$ and $2.096\times10^{-10}$ with the same table bytes. In the Stack boundary workload, the 13 differing direct responses contained 837,376 distinct vertex–request disagreements counted over the session; a vertex may occur more than once. On Web-Google a simple exact counterexample is vertex 794864. Its only incident edge has binary64 probability 0x1.0ae4760000000p-1. At its immediate successor both direct solvers report one; the exact membership test gives zero. [Witness control](service/witness_controls.csv) · [Exact degree-one witnesses](service/degree_one_disagreements.json)

## What happens at a concentration of equal thresholds?



At confidence one half on 4,096 independent equal-probability edges, all 8,192 endpoints required an exact test. Resolving them took about 20 ms on this instance, including about 11 ms for the first graph load and 6 ms inside GMP. The adjacent upper binary64 confidence removed every endpoint. A heterogeneous 63-neighbor instance produced a 3,184-bit denominator and up to 3,237 bits in a comparison. A 256-vertex cycle required 254 queue revisits. These are controlled stress inputs with known candidate brackets. Their 14 complete output vectors matched an independent integer-PMF and synchronous-deletion oracle. The exact denominator of a product has exponent at most the sum of the input denominator exponents. A cache of exact results is reusable for an unchanged neighborhood, degree and probability vector; removing a neighbor changes that key. Precomputing all possible residual subsets can take exponential space. The supplied query engine reuses the loaded graph within a session and recomputes exact comparisons as needed. [All boundary requests and timings](arithmetic/boundary_cases.csv)


## Does double precision change the GPU comparison?

The CUDA probe retains the original queues and repartitioning and the corrected synchronization on the RTX 5080 Laptop GPU. The partition sweep used Flickr only and selected 32 for all three arithmetic variants. With this setting fixed, unrounded binary64 met the CPU-reference difference gate of $10^{-9}$ on every SupUser, Wiki-Pe and HepPh entry. The largest difference on any of the three was below $10^{-12}$. Keeping six-decimal quantization inside double-precision peeling left maximum differences near $5\times10^{-7}$. The mean wall times for unrounded binary64 were 7.92, 19.07 and 101.90 s, compared with 4.61, 10.55 and 41.52 s for binary32. Rounding can change the next queue minimum and the work that follows. All clocks include host-to-device transfer and packed file output. The 13-graph historical comparison retains its original precision labels. [Protocol and implementation](resources/README.md) · [Precision, cost and error by run](resources/measurements.csv)

## Why do more workers help on HepPh but do little on Wiki-Pe?

With eight resident levels the builder can peel at most eight rows concurrently. On HepPh, increasing workers from one to eight reduced peel time from 95.28 to 7.79 s; 24 workers at that capacity took 8.07 s. Raising capacity to 24 then reduced peeling to 4.13 s. Wiki-Pe instead spent 105.50–113.12 s in the sweep across all four worker counts at eight resident levels. A single long neighborhood recurrence remains with one worker. Its adjacent Bernoulli factors cannot be split among workers by that scheduler.

We tested a different way to shorten that recurrence. Tail updates at order $t$ read only orders $t$ and $t-1$. On a vertex of original degree at least 50,000 the variant therefore preserves all coordinates up to $h+64$ and uses zero for missing higher-order lower bounds. On Wiki-Pe $h=120$. The paired trials used 0.46 and 0.44 s of sweep time with the cutoff, against 116.35 and 109.44 s without it. The complete values file was identical and the independent checker accepted both witnesses. The value-only comparison with UCEF gave overlapping times; neither builder won both repetitions. This option retains the preallocated backing array. The measured allocation stayed near 710 MiB for the 24-level runs. The per-run phase, peak memory, independent verification time and hashes are archived together. [Resource probes](resources/README.md) · [Per-run data](resources/measurements.csv)

On Deli, the historical 24-level run exhausted the 32 GiB allocation budget and never produced a complete table. Across the old single-level and the new four-level witnessed builds, peeling fell from 544.13 to 142.40 s, while the sweep still took 1,045.86 s at four levels. The with-order times were 1,733.06 and 1,215.68 s and peak footprints were 16,820 and 28,676 MiB. The four-level full-window output reproduced the complete one-level file exactly. Applying the same degree threshold and $h+64$ rule as on Wiki-Pe reduced the four-level sweep to 37.40 s. Peeling took 144.42 s; the complete witnessed build took 209.57 s with the same 28,676 MiB peak. Both 138,505,284-entry tables passed the strict MSVC checker with maximum lower deficit $6.267\times10^{-12}$ and upper excess $2.245\times10^{-12}$. The truncated table differs from the original by up to $1.57\times10^{-12}$. Its proof preserves low-order recurrence dependence, while weaker offset bounds may alter the peeling trajectory. Deli verification took 101.19 and 103.37 s, respectively. Every comparison uses the *complete* one-level reference retained after the historical capacity failure. [Raw phase and validation records](resources/measurements.csv)

The final values-only Deli comparison took 197.30 s and 28,337 MiB for the capped sweep and 126.84 s and 5,526 MiB for UCEF, one run per method. The capped values file had exactly the hash of its independently verified witnessed build. UCEF retained both the lower elapsed time and lower peak memory on this graph.
