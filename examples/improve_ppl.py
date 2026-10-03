"""Reproducible one-factor DW-FSE experiments. Run from repository root.

python examples/improve_ppl.py screen
python examples/improve_ppl.py robust --variants base,centered,varying,combined

Raw runs are intentionally ignored by Git. Summary JSON/CSV can be archived in docs.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dwfse import generate, simulate, view

BASE = dict(views_per_seg=8, no_views=16, te=36, esp=16,
            acq_b=[0, 1000], no_diff_acq=2, no_experiments=2,
            acq_x=[1000, 1000], acq_y=[0, 0], acq_z=[0, 0],
            sim_reduced_shots=[1])  # ky=0 at echo 1; nav_on=0 in this PPR
VARY = [1, 1, 1.3, 1.7, 2.1, 2.6, 3.2, 3.9]
VARIANTS = {
    'base': {},
    'centered': dict(sim_fix_refocus_centering=True),
    'equal_first': dict(diff_crush_amp=5482),
    'double_crushers': dict(crush_amp=10964, diff_crush_amp=5508),
    'alternate': dict(sim_train_crusher_scales=[1,-1,1,-1,1,-1,1,-1]),
    'varying': dict(sim_train_crusher_scales=VARY),
    'linear_crushers': dict(sim_train_crusher_scales=[1,1,1.4,1.8,2.2,2.6,3,3.4]),
    'irregular_crushers': dict(sim_train_crusher_scales=[1,1,1.71,.83,1.37,2.13,1.09,1.91]),
    'duration_half': dict(tcrush=500),
    'equal_interval': dict(esp=36),
    'flip160': dict(sim_refocus_flip_deg=160),
    'flip200': dict(sim_refocus_flip_deg=200),
    'hanning': dict(sim_rf_apodization=.5),
    'bw_matched': dict(sim_rf_model='bw_matched_sinc'),
    'phase_alternate': dict(sim_refocus_phase_offsets_deg=[0,180]*4),
    'phase_xy': dict(sim_refocus_phase_offsets_deg=[0,90]*4),
    # Exploratory quadratic law, NOT the stabilized published Le Roux method.
    'phase_quadratic': dict(sim_refocus_phase_offsets_deg=[(65*k*k)%360 for k in range(8)]),
    'post_off': dict(post_crush_on=0),
    'prephaser100': dict(grp_lobe=100),
    'combined': dict(sim_fix_refocus_centering=True, sim_train_crusher_scales=VARY),
    'centered_xy': dict(sim_fix_refocus_centering=True,
                        sim_refocus_phase_offsets_deg=[0,90]*4),
    'centered_linear': dict(sim_fix_refocus_centering=True,
                            sim_train_crusher_scales=[1,1,1.4,1.8,2.2,2.6,3,3.4]),
}


def save_sequence(folder, overrides):
    folder.mkdir(parents=True, exist_ok=True)
    (folder/'overrides.json').write_text(json.dumps(overrides, indent=2))
    seq, c, d, log = generate.build_sequence(generate.load_params(overrides=overrides), reduced=True)
    ok, errors = seq.check_timing()
    if not ok:
        raise RuntimeError(errors)
    seq.write(str(folder/'seq.seq'))
    (folder/'seq.params.json').write_text(json.dumps(generate.params_dict(c), indent=2, default=str))
    (folder/'seq.gen.txt').write_text(generate.report(c,d)+'\ncheck_timing: PASS\n')
    txt, _ = view.analysis(seq, view.select_blocks(seq))
    (folder/'view.txt').write_text(txt)
    return seq


def run_case(group, variant, row, phase, b1s, b0s, n, rf_dt=1e-5, seed=1, extra=None):
    tag = f'{group}_{variant}_b{BASE["acq_b"][row]}_ph{phase:g}'
    folder = Path('runs')/('improve_'+tag)
    overrides = dict(BASE, **VARIANTS[variant])
    overrides.update(sim_reduced_rows=[row], sim_excitation_phase_deg=phase)
    overrides.update(extra or {})
    seq = save_sequence(folder, overrides)
    vox = simulate.make_voxel(n=n, seed=seed)
    records, signals = [], []
    for b1 in b1s:
        for b0 in b0s:
            r = simulate.simulate(seq, b1=b1, b0=b0, voxel=vox, rf_dt=rf_dt)
            signals.append(r['signal'])
            ends = np.cumsum(np.r_[0,r['adc_sizes']])
            for e,(a,b) in enumerate(zip(ends[:-1],ends[1:])):
                sig = r['signal'][a:b]
                ts = r['t_adc'][a:b]
                peaks = np.where((np.abs(sig)[1:-1]>np.abs(sig)[:-2]) &
                                 (np.abs(sig)[1:-1]>np.abs(sig)[2:]))[0]+1
                order = peaks[np.argsort(np.abs(sig[peaks]))[::-1]]
                records.append(dict(group=group, variant=variant, b=BASE['acq_b'][row],
                    phase=phase, b1=b1, b0=b0, echo=e+1,
                    center=float(r['echo_center'][e]), peak=float(r['echo_peak'][e]),
                    peak_offset_us=float((ts[np.argmax(abs(sig))]-ts.mean())*1e6),
                    second_peak=float(abs(sig[order[1]])) if len(order)>1 else 0,
                    run=str(folder)))
    np.savez_compressed(folder/'signals.npz', signal=np.asarray(signals), t_adc=r['t_adc'],
                        adc_sizes=r['adc_sizes'], b1=b1s, b0=b0s)
    settings=dict(n=n, seed=seed, rf_dt=rf_dt, b1=b1s, b0=b0s, T1=1.5,T2=.08,T2prime=.03)
    (folder/'sim_settings.json').write_text(json.dumps(settings,indent=2))
    (folder/'metrics.json').write_text(json.dumps(records,indent=2))
    (folder/'summary.txt').write_text('\n'.join(str(x) for x in records)+'\n')
    print(tag, 'E8:', [round(x['center'],5) for x in records if x['echo']==8], flush=True)
    return records


def write_table(records, name):
    path=Path('runs')/f'improve_{name}.csv'
    # Preserve earlier subsets when the investigation adds a bounded follow-up.
    keys=('group','variant','b','phase','b1','b0','echo')
    merged={}
    if path.exists():
        with path.open(newline='') as f:
            for row in csv.DictReader(f):
                merged[tuple(str(row[k]) for k in keys)]=row
    for row in records:
        merged[tuple(str(row[k]) for k in keys)]=row
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f, fieldnames=list(records[0]));w.writeheader();w.writerows(merged.values())
    return path


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('stage', choices=['screen','robust','sensitivity','steady'])
    ap.add_argument('--variants', default=None)
    args=ap.parse_args()
    names=args.variants.split(',') if args.variants else (
        [k for k in VARIANTS if k not in ('combined','centered_xy','centered_linear')] if args.stage=='screen'
        else ['base','post_off'] if args.stage=='steady' else ['base','centered','varying','combined'])
    records=[]
    if args.stage=='screen':
        for name in names:
            for ph in [0,90]:
                records+=run_case('screen',name,1,ph,[.8],[0],4096)
    elif args.stage=='robust':
        for name in names:
            for row in [0,1]:
                for ph in [0,45,90]:
                    records+=run_case('robust',name,row,ph,[.7,.8,1,1.2],[0,100],10000)
    elif args.stage=='steady':
        for name in names:
            records+=run_case('steady8',name,1,0,[.8],[0],4096,
                              extra={'sim_reduced_n_dummy':8})
    else:
        for name in names:
            for label,n,dt,seed,extra in [
                ('dense',40000,1e-5,1,{}), ('seed2',40000,1e-5,2,{}),
                ('dt2us',10000,2e-6,1,{}),
                ('hanning',10000,1e-5,1,dict(sim_rf_apodization=.5)),
                ('lag0',10000,1e-5,1,dict(hw_grad_delay_us=0))]:
                records+=run_case('sensitivity_'+label,name,1,90,[.8],[0],n,dt,seed,extra)
    print(write_table(records,args.stage))


if __name__=='__main__':
    main()
