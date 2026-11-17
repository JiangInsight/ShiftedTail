import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import study as service

def rejects(function):
    try:
        function()
    except ValueError:
        return
    raise AssertionError('stale cached evidence was accepted')

def main():
    fixture=service.SCRATCH/'witness_regression/graph'
    if not fixture.exists():
        raise FileNotFoundError('Run test_witness.py first')
    destination=service.OUT/'cache_regression.json'
    with tempfile.TemporaryDirectory(dir=service.WORK) as temporary:
        folder=Path(temporary)
        service.OUT=folder/'records'
        service.OUT.mkdir()
        graph=folder/'graph.bin'
        shutil.copyfile(fixture,graph)
        table=folder/'values.thr'
        command=[service.WORK/'ucef.exe',graph,1,table]
        first=service.timed('builder',command)
        assert service.timed('builder',command)==first
        original=table.read_bytes()
        table.write_bytes(original[:-1])
        rejects(lambda:service.timed('builder',command))
        table.write_bytes(original)
        raw=graph.read_bytes()
        graph.write_bytes(raw+b'changed')
        rejects(lambda:service.timed('builder',command))
        graph.write_bytes(raw)
        service.GRAPH={'tiny':graph}
        case=folder/'tiny'
        case.mkdir()
        shutil.copyfile(table,case/'ucef.thr')
        for stem in ('index','direct','ucef_order'):
            shutil.copyfile(service.SCRATCH/(stem+'.exe'),folder/(stem+'.exe'))
        service.SCRATCH=folder
        subprocess.run([folder/'ucef_order.exe',graph,case/'ucef.thr',case/'ucef.ord','24'],env=service.ENV,check=True)
        subprocess.run([service.CODE/'export_rank.exe',graph,case/'rank'],env=service.ENV,check=True)
        service.timed('tiny_r1_ucef_verify_strict',[service.STRICT,graph,case/'ucef.thr',case/'ucef.ord',24])
        order=(case/'ucef.ord').read_bytes()
        (case/'ucef.ord').write_bytes(order[:-1])
        rejects(lambda:service.query('tiny','original','ucef'))
        (case/'ucef.ord').write_bytes(order)
        (case/'original.txt').write_text('0.5\n')
        service.write(service.OUT/'tiny_manifest.json',{'original':{'requests':[.5]}})
        service.query('tiny','original','ucef')
        service.query('tiny','original','ucef')
        (case/'original.txt').write_text('0.9\n')
        rejects(lambda:service.query('tiny','original','ucef'))
        (case/'original.txt').write_text('0.5\n')
        (case/'original/ucef/ans-0.bin').unlink()
        rejects(lambda:service.query('tiny','original','ucef'))
    service.write(destination,{'passed':True,'rejected':['changed builder output','changed graph',
        'changed strictly checked witness','changed request sequence','missing cached answer'],
        'unchanged_stage_reused':True,'unchanged_query_reused':True})

if __name__=='__main__':
    main()
