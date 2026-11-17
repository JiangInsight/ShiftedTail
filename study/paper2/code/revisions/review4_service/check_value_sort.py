
import struct
import time
import numpy as np
from study import STRICT, GRAPH, SCRATCH, OUT, sha, timed, write

def main():
    for g,graph in GRAPH.items():
        d=SCRATCH/g;raw=d/'ucef.thr';order=d/'rank_ties.ord'
        start=time.perf_counter()
        with raw.open('rb') as f,order.open('wb') as out:
            while head:=f.read(12):
                k,n=struct.unpack('<IQ',head);row=np.fromfile(f,'<f8',n)
                assert len(row)==n and np.isfinite(row).all()
                out.write(head)
                np.argsort(row,kind='stable').astype('<u4').tofile(out)
        generated=time.perf_counter()-start
        check=timed(g+'_rank_tie_control',[STRICT,graph,raw,order,24],allow_failure=True)
        assert check['rc'] in (0,3)
        write(OUT/(g+'_rank_tie_order.json'),{'ucef_values_sha256':sha(raw),'naive_order_sha256':sha(order),
              'order_rule':'sort the unmodified binary64 thresholds; stable ties in increasing rank position',
              'generation_s_from_open_through_close':generated,
              'verifier_accepted':check['rc']==0})

if __name__=='__main__':main()
