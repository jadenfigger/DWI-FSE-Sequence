"""
analyze_minimal.py - explain the KomaMRI result of dwfse_minimal.seq.

Builds variants of the minimal protocol (repo PPR: ETL 2, 2 shots, 1 slice, b = 0),
simulates each with bloch_sim.py (same voxel model as koma_sim.jl, stratified),
and writes analysis/minimal_analysis.png + analysis/minimal_results.json.

    cd pypulseq && python analysis/analyze_minimal.py
"""
import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import bloch_sim as bs  # noqa: E402
import dwfse_ppl_twoTE_1_6 as gen  # noqa: E402

OUT = os.path.join(HERE, 'seq')
os.makedirs(OUT, exist_ok=True)
T1, T2 = 1.5, 0.08
VARIANTS = {
    'A as written (default)': {},
    'B 180 centring fixed': {'sim_fix_refocus_centering': True},
    'C commanded timing (no grad lag)': {'hw_grad_delay_us': 0},
    'D CPMG-matched (te=esp=36, equal crushers, fixed)': {'te': 36, 'esp': 36, 'diff_crush_amp': 5482,
                                                          'sim_fix_refocus_centering': True},
    'E Hanning-apodised placeholder RF': {'sim_rf_apodization': 0.5},
}


def build(name, ov):
    C = gen.load_params(overrides=ov)
    seq, C, D, log = gen.build_sequence(C)
    fn = os.path.join(OUT, name.split()[0] + '.seq')
    seq.write(fn)
    return fn, C


def tr1_blocks(fn):
    import pypulseq as pp
    s = pp.Sequence()
    s.read(fn)
    dur = 0
    for i in range(1, len(s.block_events) + 1):     # stop after the post-train crusher of TR 1
        dur += s.block_durations[i]
        if s.block_durations[i] > 0.5:
            return i - 1
    return len(s.block_events)


def main():
    vox = bs.make_voxel(n=20000, stratified=True)
    res = {}
    files = {}
    for name, ov in VARIANTS.items():
        fn, C = build(name, ov)
        files[name] = (fn, C)
        r = bs.simulate(fn, voxel=vox, rf_dt=1e-5, T1=T1, T2=T2)
        e = r['echo_center']
        res[name] = dict(echo=e.round(4).tolist(), te=C.te, esp=C.esp)
        print(f'{name:50s} echoes {np.round(e, 4)}  e2/e1 {e[1]/e[0]:.3f}  T2-only {np.exp(-C.esp/1e3/T2):.3f}'
              f'  TR2/TR1 {e[2]/e[0]:.3f}')

    # B1 sweep, TR 1 only
    b1s = [0.7, 0.8, 0.9, 1.0, 1.1, 1.2]
    sweep = {}
    for key in ('A as written (default)', 'D CPMG-matched (te=esp=36, equal crushers, fixed)'):
        fn, C = files[key]
        nb = tr1_blocks(fn)
        sweep[key] = [bs.simulate(fn, voxel=vox, rf_dt=1e-5, b1=b, max_blocks=nb)['echo_center'][:2].tolist()
                      for b in b1s]
        print(key, np.round(sweep[key], 4).tolist())

    # slice profiles of the placeholder RF (z only, no off-resonance)
    zv = dict(x=np.zeros(2001), y=np.zeros(2001), z=np.linspace(-1.5e-3, 1.5e-3, 2001), df=np.zeros(2001))
    prof = {}
    for key in ('A as written (default)', 'E Hanning-apodised placeholder RF'):
        fn, _ = files[key]
        ex = bs.simulate(fn, voxel=zv, rf_dt=1e-6, max_blocks=3, snapshot_blocks=(3,), T1=1e9, T2=1e9)
        mx, my, mz = ex['snapshots'][3]
        rf = bs.simulate(fn, voxel=zv, rf_dt=1e-6, start_block=7, max_blocks=7, snapshot_blocks=(7,),
                         T1=1e9, T2=1e9)
        eta = (1 - rf['snapshots'][7][2]) / 2
        prof[key] = (np.hypot(mx, my), eta)

    # ---- figure ----------------------------------------------------------------
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    names = list(res)
    w = 0.2
    for j, lab in enumerate(['TR1 echo1 (36 ms)', 'TR1 echo2', 'TR2 echo1', 'TR2 echo2']):
        ax[0].bar(np.arange(len(names)) + (j - 1.5) * w, [res[n]['echo'][j] for n in names], w, label=lab)
    ax[0].set_xticks(range(len(names)))
    ax[0].set_xticklabels([n.split()[0] for n in names])
    ax[0].set_ylabel('|signal| / M0 (k-centre sample)')
    ax[0].set_title('Echo amplitudes by variant (A-E, see report)')
    ax[0].legend(fontsize=8)
    for key, mk in zip(sweep, ('o-', 's--')):
        e = np.array(sweep[key])
        ax[1].plot(b1s, e[:, 0], mk, color='C0', label=f'{key.split()[0]} echo 1')
        ax[1].plot(b1s, e[:, 1], mk, color='C3', label=f'{key.split()[0]} echo 2')
    ax[1].set_xlabel('B1 scale')
    ax[1].set_ylabel('|signal| / M0')
    ax[1].set_title('B1 sensitivity: A (DW-FSE timing) vs D (CPMG-matched)')
    ax[1].legend(fontsize=8)
    z = zv['z'] * 1e3
    for key, c in zip(prof, ('C0', 'C2')):
        ax[2].plot(z, prof[key][0], color=c, label=f'{key.split()[0]} 90: |Mxy|')
        ax[2].plot(z, prof[key][1], '--', color=c, label=f'{key.split()[0]} 180: (1-Mz)/2')
    ax[2].axvspan(-0.5, 0.5, color='0.9', zorder=0, label='nominal 1 mm slice')
    ax[2].set_xlabel('z [mm]')
    ax[2].set_title('Slice profiles of the placeholder RF')
    ax[2].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'minimal_analysis.png'), dpi=120)

    def fwhm(p):
        z_ = zv['z'] * 1e3
        m = p >= p.max() / 2
        return z_[m].max() - z_[m].min()

    out = dict(variants=res, b1=b1s, sweep=sweep,
               fwhm_mm={k: dict(exc=fwhm(v[0]), ref=fwhm(v[1]), exc_peak=float(v[0].max()),
                                exc_centre=float(v[0][1000]), ref_centre=float(v[1][1000])) for k, v in prof.items()})
    print(json.dumps(out['fwhm_mm'], indent=1))
    with open(os.path.join(HERE, 'minimal_results.json'), 'w') as f:
        json.dump(out, f, indent=1)


if __name__ == '__main__':
    main()
