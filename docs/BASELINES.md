# Source attribution and comparison scope

| Component | Source | Role |
|---|---|---|
| ShiftedTail, CTD, OptiUCF reconstruction, UCEF reconstruction | `study/paper2/code/` | Paper implementation and local comparison kernels |
| Dai direct uncertain-core solvers | https://github.com/qq-dai/UncertainCore/tree/315dee85ff5aae487c296a99fb600304bbee0f24 | Original author routines linked through the released request adapter |
| Bonchi DP and LB | https://github.com/fgullo/uncertaincores/tree/370b2dbcaa02a3466a2afd10e24cd52019c3edb3 | Author Java source and probability datasets; LB output adapter is included |
| Gatd | https://github.com/AbigailJixiangyuyu/uco-gpu/tree/88b5ba7f60560363bc1579c7ee7984ee3541be6e | Author CUDA source; three explicit correctness/port/output patches |
| Boost.Math | https://github.com/boostorg/math/tree/f1b0b95a04f56717b3454cb599e0647770c5852e | Binomial special functions; upstream Boost Software License applies |
| CN15k | https://github.com/stasl0217/UKGE/tree/5049b84501657abc44c36dd7d2db5f8519e5ee8f | Relation confidence data projected as specified in the input manifest |

The UCEF reconstruction implements the in-memory threshold component of Wen et al., TKDE 2022, Algorithm 5 and Section 6.4. The OptiUCF reconstruction implements Sun et al., algorithms 2–3 and equation (8); it does not include their eta-tree. Original attribution formerly held in implementation comments is retained here. Reconstruction and author-code results must not be conflated.

`source-map.json` records the research-source hashes before packaging. Source comments were removed, build paths made configurable, and instrumentation patches regenerated against the released sources. Consequently the released source bytes and newly compiled binaries need not have the historical hashes. Inputs and saved observations retain their original provenance. The strict arithmetic contract and independently checked answers, not equality to an archived compiler output, govern a fresh run.
