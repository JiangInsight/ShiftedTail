
import json
from pathlib import Path
import struct
import numpy as np


def compare(reference, gpu, rankfile):
    order=np.fromfile(rankfile,'<u4')
    n=len(order); ids=np.arange(n,dtype=np.uint32)
    rec=np.dtype([("id","<u4"),("k","<u4"),("value","<f4")]); raw=np.memmap(gpu,dtype=rec,mode='r')
    assert len(raw)%n==0
    layers=len(raw)//n; count=0; exact6=0; worst=0.; above=0; nonfinite=0;total_abs=0.
    with Path(reference).open('rb') as f:
        for i in range(layers):
            k,cnt=struct.unpack('<IQ',f.read(12)); assert k==layers-i
            ref=np.fromfile(f,'<f8',cnt)
            row=raw[i*n:(i+1)*n]
            if not np.array_equal(row['id'],ids) or not np.all(row['k']==k):raise ValueError("invalid GPU record layout")
            got=row['value'][order[:cnt]].astype('float64'); diff=np.abs(ref-got)
            nonfinite+=int((~np.isfinite(diff)).sum());worst=max(worst,float(np.nanmax(diff)))
            total_abs+=float(diff.sum());above+=int((diff>1e-5).sum())
            exact6+=int((np.rint(ref*1e6)==np.rint(got*1e6)).sum());count+=cnt
        assert not f.read(1)
    return dict(layers=layers,thresholds=count,nonfinite=nonfinite,max_abs=worst,mean_abs=total_abs/count,
                rounded_6dp_match_fraction=exact6/count,above_1e_minus_5=above)


if __name__=='__main__':
    import sys
    print(json.dumps(compare(*sys.argv[1:]),indent=2))
