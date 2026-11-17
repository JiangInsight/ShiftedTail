
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo
import argparse
import hashlib
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
OUT=HERE/'reproduction-source.zip'
EXT={'.py','.cpp','.hpp','.h','.ps1','.bat','.patch','.java'}

def sources():
    files=set(p for p in (ROOT/'code').rglob('*') if p.is_file() and p.suffix.lower() in EXT and p.name!='check_ccas_input.py')
    files.add(ROOT/'icde_build/package_artifact.py')
    files.update((ROOT/'code/revisions').glob('*/README.md'))
    files.update((ROOT/'paper/supplement/review4').glob('*/README.md'))
    files.update((ROOT/'results/study').glob('*.patch'))
    files.update((ROOT/'results/study').glob('*_source.cpp'))
    files.update((ROOT/'baselines').glob('gatd_win*/build_windows.bat'))
    files.update((ROOT.parent/'paper1/code')/s for s in ['memcap.cpp','prep.py','prep_big.cpp','prep_events.cpp','prep_temporal.py'])
    files.update(p for p in (ROOT/'paper/supplement/review4').rglob('*') if p.is_file() and p.suffix.lower() in EXT)
    files.update((ROOT/'paper/supplement/review4'/n) for n in ('inputs.csv','README.md'))
    files.update(HERE/n for n in ('README.md','cuda_hashes.json','clean_build.json'))
    files.update((ROOT/'paper'/n) for n in ('verify_example.py','make_figures.py'))


    entries={p.relative_to(ROOT.parent).as_posix():p for p in files}
    for p in (ROOT/'results').glob('*/REPRODUCE.md'):
        entries['recorded/'+p.relative_to(ROOT).as_posix()]=p
    for p in [ROOT/'results/study/input_manifest.json',ROOT/'results/fair_study/matched_inputs.json',
              ROOT/'results/study/native_build.json',*(ROOT/'results/literature_coverage').glob('*_input.json')]:
        entries['recorded/'+p.relative_to(ROOT).as_posix()]=p
    return entries

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args()
    entries=sources()
    blobs={name:p.read_bytes() for name,p in entries.items()}
    sums={name:hashlib.sha256(data).hexdigest() for name,data in sorted(blobs.items())}
    blobs['SHA256.json']=(json.dumps(sums,sort_keys=True,indent=2)+'\n').encode()
    if not args.check:
        dest=OUT.with_suffix('.tmp')
        with ZipFile(dest,'w') as z:
            for name,data in sorted(blobs.items()):
                info=ZipInfo(name,date_time=(2026,11,7,0,0,0))
                z.writestr(info,data,compress_type=ZIP_DEFLATED,compresslevel=3)
        dest.replace(OUT)
    with ZipFile(OUT) as z:
        assert z.testzip() is None and set(z.namelist())==set(blobs)
        assert all(z.read(n)==v for n,v in blobs.items())
    print(f'{len(entries)} files, {OUT.stat().st_size} bytes, SHA256 {hashlib.sha256(OUT.read_bytes()).hexdigest()}')

if __name__=='__main__':main()
