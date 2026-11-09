# ShiftedTail

*Building and Verifying All-Level Core Thresholds in Uncertain Graphs*

The C++ builder computes a core threshold for each eligible vertex and degree. A separate verifier reads the thresholds and the removal order.

## Build and verify

Requires x64 Windows, an AVX2 processor, Visual Studio C++ Build Tools with LLVM OpenMP, and Python 3.10 or later.

```powershell
.\build.cmd
python run_example.py
```

The input is an [undirected edge list](data/edges.csv) with columns `u,v,probability`. On the four-vertex graph, the builder writes seven thresholds. The verifier checks them, and the example compares each value with exhaustive vertex-subset evaluation.

## Construction time

<img src="figures/construction-times.png" width="560" alt="UCEF and Gatd construction times divided by ShiftedTail time on thirteen graph topologies.">

Each point compares two builders on the same graph. Values above 1 favor ShiftedTail. On Stack Overflow all three wrote 28,341,100 thresholds. ShiftedTail took 38.9 s, UCEF’s parallel threshold stage took 78.6 s and the corrected Gatd GPU port took 573.3 s. [Per-graph times](data/construction-times.csv)
