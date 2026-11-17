
import array
import struct
import subprocess
from fractions import Fraction
from study import SCRATCH, OUT, WORK, CODE, STRICT, ENV, write

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    folder=SCRATCH/'witness_regression'
    folder.mkdir(exist_ok=True)
    edges={(0,1):Fraction(3,4),(1,2):Fraction(3,4),(0,2):Fraction(3,4),(2,3):Fraction(1,2)}
    n=4
    nbr=[[(j,edges[tuple(sorted([i,j]))]) for j in range(n) if tuple(sorted([i,j])) in edges] for i in range(n)]
    graph=folder/'graph'
    with graph.open('wb') as f:
        f.write(struct.pack('<IQ',n,2*len(edges)))
        array.array('I',[len(row) for row in nbr]).tofile(f)
        array.array('I',[u for row in nbr for u,p in row]).tofile(f)
        array.array('d',[float(p) for row in nbr for u,p in row]).tofile(f)
    def run(tag,args,expected):
        proc=subprocess.run(list(map(str,args)),env=ENV,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (OUT/f'toy_{tag}.log').write_bytes(proc.stdout)
        assert proc.returncode==expected,(tag,proc.returncode)
    vals=folder/'values';order=folder/'order';bad=folder/'bad'
    run('ucef',[WORK/'ucef.exe',graph,2,vals],0)
    run('order',[SCRATCH/'ucef_order.exe',graph,vals,order,2],0)
    run('accept',[CODE/'verify_thresholds.exe',graph,vals,order,2],0)
    run('accept_strict',[STRICT,graph,vals,order,2],0)
    truth=[[Fraction(0) for _ in range(n)] for _ in range(3)]
    for k in (1,2):
        for mask in range(1,1<<n):
            vertices=[i for i in range(n) if mask>>i&1]
            guaranteed=[]
            for i in vertices:
                dist=[Fraction(1)]
                for j,p in nbr[i]:
                    if j not in vertices:continue
                    acc=[Fraction(0)]*(len(dist)+1)
                    for m,mass in enumerate(dist):
                        acc[m]+=mass*(1-p);acc[m+1]+=mass*p
                    dist=acc
                guaranteed.append(sum(dist[k:]))
            for i in vertices:truth[k][i]=max(truth[k][i],min(guaranteed))
    raw=bytearray(vals.read_bytes())
    off=0
    for expected in (2,1):
        k,num=struct.unpack_from('<IQ',raw,off);off+=12
        assert k==expected
        row=struct.unpack_from('<'+'d'*num,raw,off)
        assert all(Fraction(x)==truth[k][i] for i,x in enumerate(row))
        if k==1:struct.pack_into('<d',raw,off+16,1.)
        off+=num*8
    assert off==len(raw)
    bad.write_bytes(raw)
    run('reject',[CODE/'verify_thresholds.exe',graph,bad,order,2],3)
    run('reject_strict',[STRICT,graph,bad,order,2],3)
    write(OUT/'toy_regression.json',{'exact_rows':[[str(x) for x in truth[k]] for k in (1,2)],
          'source':'real UCEF above; independent exhaustive calculation over all 15 nonempty vertex subsets',
          'accept_rc':0,'reject_rc':3,'mutation':'set vertex 2 k=1 threshold to 1; keep original order'})

if __name__=='__main__':main()
