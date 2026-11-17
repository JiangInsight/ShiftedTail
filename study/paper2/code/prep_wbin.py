






import sys

import numpy as np


def main():
    src, dst = sys.argv[1], sys.argv[2]
    with open(src, "rb") as f:
        n, M = (int(x) for x in np.fromfile(f, dtype=np.uint64, count=2))
        u = np.fromfile(f, dtype=np.uint32, count=M)
        v = np.fromfile(f, dtype=np.uint32, count=M)
    key = u.astype(np.uint64) * np.uint64(n) + v.astype(np.uint64)
    del u, v
    pairs, w = np.unique(key, return_counts=True)
    del key
    a = (pairs // np.uint64(n)).astype(np.uint32)
    b = (pairs % np.uint64(n)).astype(np.uint32)
    m = len(pairs)
    src_ = np.concatenate([a, b])
    dst_ = np.concatenate([b, a])
    ww = np.concatenate([w, w]).astype(np.uint32)
    order = np.lexsort((dst_, src_))
    src_, dst_, ww = src_[order], dst_[order], ww[order]
    deg = np.bincount(src_, minlength=n).astype(np.uint64)
    off = np.zeros(n + 1, dtype=np.uint64)
    np.cumsum(deg, out=off[1:])
    with open(dst, "wb") as f:
        np.array([n, m], dtype=np.uint64).tofile(f)
        off.tofile(f)
        dst_.astype(np.uint32).tofile(f)
        ww.tofile(f)
    print(f"{src}: n={n} events={M} edges={m} maxdeg={int(deg.max())} w_max={int(w.max())} "
          f"share_w1={float((w == 1).mean()):.3f}")


if __name__ == "__main__":
    main()
