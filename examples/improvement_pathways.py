"""Sample-level PDG metrics for the saved improvement experiments.

python examples/improvement_pathways.py --group screen
python examples/improvement_pathways.py --group robust --variants base,varying,combined
Defaults to D=0 to compare with the static-spin Bloch model. D is MRzero's
diffusion coefficient in 10^-3 mm^2/s, not the requested sequence b-value.
"""
import argparse
import csv
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import matplotlib
matplotlib.use('Agg')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dwfse import epg, pathways


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--group',default='screen')
    ap.add_argument('--variants')
    ap.add_argument('--b1',nargs='+',type=float,default=[.8])
    ap.add_argument('--D',type=float,default=0)
    ap.add_argument('--closure',action='store_true')
    args=ap.parse_args()
    names=set(args.variants.split(',')) if args.variants else None
    records=[]
    for folder in sorted(Path('runs').glob('improve_'+args.group+'_*_b*_ph*')):
        if not (folder/'metrics.json').exists():
            continue
        meta=json.loads((folder/'metrics.json').read_text())[0]
        if names and meta['variant'] not in names:
            continue
        seq=epg.quiet(epg.mr0.Sequence.import_file,str(folder/'seq.seq'))
        for b1 in args.b1:
            a=SimpleNamespace(voxel_mm=[.2,.2,1],T1=1.5,T2=.08,T2dash=.03,D=args.D,b0=0,b1=b1)
            fn=pathways.with_mrzero_closure if args.closure else pathways.enumerate_center_pathways
            ms=epg.quiet(fn,seq,epg.make_phantom(a))
            (folder/f'pathways_b1{b1:g}_D{args.D:g}.json').write_text(json.dumps(
                [pathways.metric_record(m) for m in ms],indent=2))
            for m in ms:
                records.append(dict(group=args.group,variant=meta['variant'],b=meta['b'],
                    phase=meta['phase'],b1=b1,b0=0,D=args.D,echo=m.echo,
                    primary=abs(m.primary),total=abs(m.total),other=abs(m.other),
                    unwanted_fraction=m.other_l1_fraction,l1=m.l1_amplitude,
                    cancellation=m.cancellation_ratio,other_phase_deg=m.other_relative_phase_deg,
                    closure_relative_error=m.closure_relative_error,run=str(folder)))
            (folder/f'pathways_b1{b1:g}_D{args.D:g}.txt').write_text(pathways.format_report(ms))
            print(folder.name,b1, 'E8 P/S/U:',round(abs(ms[-1].primary),5),
                  round(abs(ms[-1].total),5),round(ms[-1].other_l1_fraction,4),flush=True)
    dest=Path('runs')/f'improve_{args.group}_pdg_D{args.D:g}.csv'
    keys=('group','variant','b','phase','b1','b0','D','echo')
    merged={}
    if dest.exists():
        with dest.open(newline='') as f:
            for row in csv.DictReader(f):
                merged[tuple(str(row[k]) for k in keys)]=row
    for row in records:
        merged[tuple(str(row[k]) for k in keys)]=row
    with dest.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(merged.values())
    print(dest)


if __name__=='__main__':
    main()
