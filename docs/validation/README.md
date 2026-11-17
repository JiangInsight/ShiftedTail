# Executed release checks

The CPU release was exported to a new source directory and rebuilt using provisioned Windows toolchains. Boost.Math, Dai and Bonchi were fetched at the published commits. No research executable or graph was copied into that clean source tree. The separately staged CUDA baseline was also rebuilt from its pinned public source and three verified patches.

| Check | Observed outcome |
|---|---|
| Ten exhaustive uncertain graphs, nine confidence queries each | Passed, including UCEF at one/three workers and the inclusive exact backend |
| Strict endpoint arithmetic | All 988 exact-rational enclosures passed |
| Boundary queue and GMP refinement | All 14 graph queries matched the independent exact oracle |
| UCEF order, accepted and deliberately corrupted certificates | Expected acceptance and rejection |
| Cache integrity | Changed graph, table, witness, request sequence and missing answers were rejected; unchanged stages and queries could be reused |
| Seven CPU construction/control arms on complete Twitter, two rounds | All 14 runs completed; 229,574 values each; maximum difference from the checked reference below 1e-12 |
| Gatd corrected port on complete Twitter | Maximum difference 1.402e-6; within the paper's GPU comparison tolerance, not a strict certificate |
| Author Java DP and LB | Both returned all 100 expected answers on 25 disjoint components; component answers were computed exhaustively, and the tiny LB binomial input was generated exactly |
| Public data reconstruction | Twitter, CN15k, Flickr, SupUser, DBLP, Biomine and Wiki-Pe match the paper input hashes |
| Full Wiki-Pe certificate | All 2,279,811 thresholds accepted by both FMA and non-FMA backends; both 280,001-vertex star controls were declined by FMA and accepted by the non-FMA checker as expected |
| Bound and scheduler controls | Rebuilt; exact binomial lower-bound checks passed |
| Plotting | Original paper figures regenerated from recorded data; new comparison plot generated from the new run ledger |

The small Java fixture has at least 20 vertices because the unmodified author's progress counter divides by `n/20`. Its original Flickr comparison still uses the author's released Beta-function file. This release test does not replace that measurement.

[report.json](report.json), the individual JSON/CSV files, and logs record these outcomes. New run timings were collected for workflow verification while other builds could be active; they are not used to revise paper speedups. Seven graph reconstructions used public downloads; five were reconstructed in the clean source directory.

The complete giant-graph repetitions, the full two-producer service study and every GPU precision control were not rerun in this release check. Their source drivers, input rules and original evidence are included. The public reproduction guide identifies their resource requirements and commands.
