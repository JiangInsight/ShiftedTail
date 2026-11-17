
import json
import platform
import shutil
import sys
import zipfile
import numpy as np
from study import HERE, ROOT, WORK, OUT, SCRATCH, CODE, CAP, GCC, STRICT, sha, write

def main():
    dest=ROOT/'paper/supplement/review4/service'
    dest.mkdir(parents=True,exist_ok=True)
    for path in sorted(OUT.glob('*.csv')):
        shutil.copyfile(path,dest/path.name)
    for name in ('artifact_hashes.json','WebGoogle_manifest.json','Stack_manifest.json','toy_regression.json','degree_one_disagreements.json'):
        shutil.copyfile(OUT/name,dest/name)
    shutil.copyfile(HERE/'README.md',dest/'README.md')
    with zipfile.ZipFile(dest/'raw_records.zip','w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for path in sorted(OUT.iterdir()):
            if path.suffix in ('.json','.log'):z.write(path,'review4_service/'+path.name)
        for path in sorted((SCRATCH/'witness_regression').glob('*')):
            if path.is_file():z.write(path,'four_vertex_witness/'+path.name)
        for g in ('WebGoogle','Stack'):
            for method in ('bottomup','topdown'):
                for rep in (1,2,3):
                    folder=(ROOT/'results/literature_coverage/queries'/f'WebGoogle_{rep}_{method}' if g=='WebGoogle'
                            else ROOT/'results/submission_study/queries18'/f'{rep}_{method}')
                    for name in ('query.log','record.json'):
                        z.write(folder/name,f'previous_original/{g}/{rep}_{method}/{name}')
    entries={}
    def add(path,rel):entries[rel]=path
    for p in HERE.iterdir():
        if p.is_file():add(p,'paper2/code/revisions/review4_service/'+p.name)
    for name in ('graph.hpp','peel_queue.hpp','uthr_study.cpp','verify_thresholds.cpp','verified_tail.hpp','export_rank.cpp','build.bat',
                 'prepare_study_inputs.py','prep_wbin.py','run_native_study.py','fair_study/ucef.cpp','fair_study/query_workload.cpp','fair_study/boundary_query.hpp',
                 'fair_study/build_cpu_baselines.ps1','fair_study/literature_coverage.py','fair_study/run_matched.py','fair_study/run_queries.py','fair_study/run_extension.py'):
        add(CODE/name,'paper2/code/'+name)
    add(OUT/'archived_original_validation.csv','paper2/code/revisions/review4_service/legacy_direct.csv')
    add(SCRATCH/'query_workload.cpp','generated/query_workload.cpp')
    add(ROOT/'results/study/native_build.json','build_metadata/native_build.json')
    add(CAP.with_name('memcap.cpp'),'paper1/code/memcap.cpp')
    add(ROOT.parent/'paper1/code/prep_temporal.py','paper1/code/prep_temporal.py')
    add(ROOT.parent/'paper1/code/prep.py','paper1/code/prep.py')
    for p in (CODE/'verify_thresholds.exe',CODE/'export_rank.exe',CODE/'uthr_native.exe'):
        add(p,'paper2/code/'+p.name)
    add(CAP,'paper1/code/memcap2.exe')
    add(WORK/'ucef.exe','scratch_base/ucef.exe')
    add(STRICT,'paper2/results/review4_arithmetic/default_strict_verifier.exe')
    add(ROOT/'paper/supplement/review4/arithmetic/release_validation.json','build_metadata/strict_release_validation.json')
    add(ROOT/'paper/supplement/review4/bounds/verify_thresholds.cpp','historical_verifier/verify_thresholds.cpp')
    with zipfile.ZipFile(dest/'reproduction.zip','w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for rel,p in sorted(entries.items()):z.write(p,rel)
        z.writestr('source_hashes.json',json.dumps({rel:sha(p) for rel,p in sorted(entries.items())},indent=2))
    deps=[p for p in (WORK/'deps/ucrt64/bin').glob('*.dll')]
    write(dest/'environment.json',dict(python=sys.version,numpy=np.__version__,platform=platform.platform(),
                                      compiler_msvc='14.51.36231',compiler_gcc='16.2.0',gpp_sha256=sha(GCC/'g++.exe'),
                                      author_direct_commit='315dee85ff5aae487c296a99fb600304bbee0f24',
                                      measured_dll_sha256={p.name:sha(p) for p in deps},cap_mib=32768,threads=24,
                                      env=dict(OMP_NUM_THREADS='24',UTHR_GROUP_BASE='1',UTHR_COALESCE='1',UTHR_INDEXED='1',UTHR_TOL='1e-12')))

if __name__=='__main__':main()
