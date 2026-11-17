# Full-graph builder comparison

Run `python run.py PROJECT RESULTS` with the same matched input tree and instrumented builder as the four-switch study. The inputs are the complete Flickr, SupUser, DBLP and CN15k projection graphs. Before timing, the standalone verifier checks each reference threshold file and removal order. Each timed process reads the graph, builds all levels and closes its result file. The checker compares every row and threshold against the reference outside the timer.

The proposed builder runs with reuse and the shifted bound both enabled, either alone, or neither. The fifth arm is the same single-worker UCEF adaptation used in the study. The arms share inputs, output format and worker count. Across five repetitions each arm occupies every position. The per-run cap is 90 seconds. If an arm exceeds that cap, later repetitions of that arm on that input are marked unmeasured. Run `python summarize.py RESULTS DEST` to collect trial records and medians.
