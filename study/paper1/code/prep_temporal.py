





import sys

import numpy as np
import pandas as pd


def main():
    src, dst = sys.argv[1], sys.argv[2]
    df = pd.read_csv(src, sep=r"\s+", header=None, names=["u", "v", "t"], dtype=np.int64, comment="#")
    df = df[df.u != df.v]
    df = df.sort_values("t", kind="stable")
    ids, inv = np.unique(np.concatenate([df.u.values, df.v.values]), return_inverse=True)
    m = len(df)
    a, b = inv[:m].astype(np.uint32), inv[m:].astype(np.uint32)
    u, v = np.minimum(a, b), np.maximum(a, b)
    with open(dst, "wb") as f:
        np.array([len(ids), m], dtype=np.uint64).tofile(f)
        u.tofile(f)
        v.tofile(f)
        df.t.values.astype(np.int64).tofile(f)
    pairs = np.unique(u.astype(np.uint64) * len(ids) + v)
    print(f"{src}: n={len(ids)} events={m} distinct_pairs={len(pairs)} t=[{df.t.min()}, {df.t.max()}]")


if __name__ == "__main__":
    main()
