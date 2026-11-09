# Building and Verifying All-Level Core Thresholds in Uncertain Graphs

The shifted-tail builder bounds a vertex’s survival probability after neighbor deletions. It emits a removal order that an independent checker uses to bound the error of each stored threshold.

## Run

64-bit Windows, Python 3.10+ and Visual Studio C++ Build Tools with LLVM OpenMP. The timed builder uses AVX2.

~~~powershell
.\build.cmd
python run_example.py
~~~

[Data](data) includes the four-vertex graph and 48 builds crossing the deletion shift with cross-level distribution reuse.
