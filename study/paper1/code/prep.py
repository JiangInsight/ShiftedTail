








import sys
import numpy as np
import pandas as pd


def main(src, dst):
    df = pd.read_csv(src, sep=r"\s+", comment="#", header=None, usecols=[0, 1],
                     dtype=np.int64, engine="c")
    u = df[0].to_numpy(); v = df[1].to_numpy()
    keep = u != v
    u, v = u[keep], v[keep]
    ids, inv = np.unique(np.concatenate([u, v]), return_inverse=True)
    n = len(ids)
    u, v = inv[: len(u)], inv[len(u):]
    a, b = np.minimum(u, v), np.maximum(u, v)
    key = np.unique(a.astype(np.int64) * n + b)
    a, b = key // n, key % n
    m = len(a)
    src_all = np.concatenate([a, b]); dst_all = np.concatenate([b, a])
    order = np.lexsort((dst_all, src_all))
    src_all, dst_all = src_all[order], dst_all[order]
    deg = np.bincount(src_all, minlength=n)
    off = np.zeros(n + 1, dtype=np.uint64); off[1:] = np.cumsum(deg)
    with open(dst, "wb") as f:
        np.array([n, m], dtype=np.uint64).tofile(f)
        off.tofile(f)
        dst_all.astype(np.uint32).tofile(f)
    print(f"{src}: n={n} m={m} maxdeg={deg.max()}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
