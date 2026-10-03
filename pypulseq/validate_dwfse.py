"""
Step-5 validation for dwfse_ppl_twoTE_1_6.py.

Reads the WRITTEN .seq back (so the checks cover what the simulator will load) and
reports: check_timing, one-TR plot, numerical b-value (all gradients and diffusion
lobes alone), TE / ESP from RF and ADC centres, k-space order/coverage, and 0th
gradient moments between refocusing pulses (CPMG condition).

    python validate_dwfse.py [--ppr F] [--params F.json] [--set key=value ...] [--tag NAME] [--full]
"""
import argparse
import math
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pypulseq as pp  # noqa: E402

import dwfse_ppl_twoTE_1_6 as gen  # noqa: E402

DT = 1e-6  # integration grid (s)


def sample_grads(seq, t0, t1):
    """Gradient waveforms (Hz/m) on a 1 us grid over [t0, t1]."""
    wave = seq.waveforms(time_range=[t0, t1])
    t = np.arange(t0, t1 + DT / 2, DT)
    g = np.zeros((3, t.size))
    for ax in range(3):
        if wave[ax].size:
            tt, aa = np.real(wave[ax][0]), np.real(wave[ax][1])
            g[ax] = np.interp(t, tt, aa, left=0.0, right=0.0)
    return t, g


def b_value(t, g, t_exc, t_refs, t_echo):
    """b (s/mm^2) for the primary spin-echo pathway; 180s treated as perfect inversions."""
    m = (t >= t_exc) & (t <= t_echo)
    tt, gg = t[m], g[:, m]
    sgn = np.ones_like(tt)
    for tr in t_refs:
        if t_exc < tr < t_echo:
            sgn[tt > tr] *= -1
    k = 2 * np.pi * np.cumsum(gg * sgn, axis=1) * DT          # rad/m
    bmat = np.einsum('it,jt->ij', k, k) * DT                    # s/m^2
    return np.trace(bmat) * 1e-6, np.diag(bmat) * 1e-6, k[:, -1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ppr', default=None)
    ap.add_argument('--params', default=None)
    ap.add_argument('--set', action='append', default=[])
    ap.add_argument('--tag', default='default', help='name used for output files')
    ap.add_argument('--full', action='store_true', help='also check k-space of the full protocol')
    ap.add_argument('--outdir', default='validation')
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    ov = {}
    if args.params:
        import json
        with open(args.params) as f:
            ov.update(json.load(f))
    ov.update(dict(gen.parse_set(x) for x in args.set))
    P = gen.load_params(args.ppr, ov)
    seq_b, P, D, log = gen.build_sequence(P, reduced=True)
    tag = args.tag
    fn = os.path.join(args.outdir, f'dwfse_reduced_{tag}.seq')
    seq_b.write(fn)
    seq = pp.Sequence(seq_b.system)          # same rasters as written
    seq.read(fn)
    row = log[0]['row']
    shot = log[0]['shot']
    dac2hz = P.grad_var[0] * 1000.0 / gen.DACMAX
    hz2mTm = 1e3 / 42.577478e6
    out = []

    def say(s=''):
        print(s)
        out.append(s)

    say(f'# Validation [{tag}] overrides {ov} - reduced sequence read back from {fn}')
    say(f'gradient delay {P.hw_grad_delay_us} us, refocus centering fix {P.sim_fix_refocus_centering}, flips {D.flip90:.1f}/{D.flip180:.1f}')
    ok, rep = seq.check_timing()
    say(f'check_timing: {"PASS" if ok else "FAIL"} ({len(rep)} errors)')

    # ---- RF / ADC times ----------------------------------------------------
    t_exc, _, t_ref, _ = seq.rf_times()
    t_adc, _ = seq.adc_times()
    n = P.no_samples + P.no_discard
    adc_c = t_adc.reshape(-1, n).mean(axis=1)   # sample times are delay+(i+0.5)*dwell -> mean = centre
    t_exc, t_ref = np.asarray(t_exc), np.asarray(t_ref)
    say(f'excitations: {len(t_exc)}, refocusing: {len(t_ref)}, readouts: {len(adc_c)}')
    te1 = adc_c[0] - t_exc[0]
    say('\n## TE / echo spacing (from RF centres and ADC centres)')
    say(f'90 -> 180_1           : {(t_ref[0]-t_exc[0])*1e3:.4f} ms (PPR te/2 = {P.te/2:.4f})')
    say(f'180_1 -> echo1 (ADC)  : {(adc_c[0]-t_ref[0])*1e3:.4f} ms (PPR te/2 = {P.te/2:.4f})')
    say(f'TE (90 -> echo1)      : {te1*1e3:.4f} ms (PPR te = {P.te})')
    d180 = np.diff(t_ref) * 1e3
    dech = np.diff(adc_c) * 1e3
    say(f'180_1 -> 180_2        : {d180[0]:.4f} ms (expected te/2+esp/2 = {P.te/2+P.esp/2})')
    if len(d180) > 1:
        say(f'180_k -> 180_k+1 (k>=2): min {d180[1:].min():.4f} max {d180[1:].max():.4f} ms (PPR esp = {P.esp})')
    say(f'echo_k -> echo_k+1    : min {dech.min():.4f} max {dech.max():.4f} ms (PPR esp = {P.esp})')
    e2r = (t_ref[1:] - adc_c[:-1]) * 1e3
    r2e = (adc_c[1:] - t_ref[1:]) * 1e3
    if len(e2r):
        say(f'echo_k -> 180_k+1     : min {e2r.min():.4f} max {e2r.max():.4f} ms; 180_k -> echo_k (k>=2): '
            f'min {r2e.min():.4f} max {r2e.max():.4f} ms (esp/2 = {P.esp/2})')
    say(f'last echo at {(adc_c[-1]-t_exc[0])*1e3:.3f} ms after 90 (te+(ETL-1)*esp = {P.te+(P.views_per_seg-1)*P.esp})')

    # ---- gradients on 1 us grid over the train ------------------------------
    t0 = t_exc[0] - 2e-3
    t1 = adc_c[-1] + 10e-3
    t, g = sample_grads(seq, t0, t1)

    # ---- plot one TR ---------------------------------------------------------
    fig, axs = plt.subplots(4, 2, figsize=(16, 10), sharex='col')
    rf_t, rf_a = [], []
    for col, (a, b) in enumerate([(t0, t1), (t0, adc_c[1] + 5e-3)]):
        m = (t >= a) & (t <= b)
        for i, name in enumerate(['Gx read', 'Gy phase', 'Gz slice']):
            axs[i + 1, col].plot((t[m] - t_exc[0]) * 1e3, g[i, m] * hz2mTm, lw=0.7)
            axs[i + 1, col].set_ylabel(name + ' [mT/m]')
        for te_ in t_exc:
            axs[0, col].axvline((te_ - t_exc[0]) * 1e3, color='r')
        for tr_ in t_ref:
            if a <= tr_ <= b:
                axs[0, col].axvline((tr_ - t_exc[0]) * 1e3, color='b')
        for ac in adc_c:
            if a <= ac <= b:
                axs[0, col].axvspan((ac - t_exc[0]) * 1e3 - 3.2, (ac - t_exc[0]) * 1e3 + 3.2, color='g', alpha=0.3)
        axs[0, col].set_ylabel('RF(red 90, blue 180) / ADC')
        axs[3, col].set_xlabel('time from 90 centre [ms]')
    axs[0, 0].set_title('One TR, centre slice: full echo train')
    axs[0, 1].set_title('Zoom: excitation, diffusion module, echoes 1-2')
    fig.tight_layout()
    png = os.path.join(args.outdir, f'one_TR_{tag}.png')
    fig.savefig(png, dpi=110)
    seq.plot(time_range=(t0, adc_c[1] + 5e-3), time_disp='ms', grad_disp='mT/m', plot_now=False)
    for i, f in enumerate(plt.get_fignums()[1:]):
        plt.figure(f).savefig(os.path.join(args.outdir, f'seqplot_{tag}_{i}.png'), dpi=100)
    plt.close('all')
    say(f'\nplots: {png}, seqplot_{tag}_*.png')

    # ---- b-value ---------------------------------------------------------------
    say('\n## b-value at echo 1 (TE), primary spin-echo pathway')
    b_all, bdiag, _ = b_value(t, g, t_exc[0], t_ref, adc_c[0])
    T = log[0]['train']
    gl = np.zeros_like(g)
    dr, dp_, ds = D.diff_rps[row]
    for (a, b) in (T.l1, T.l2):
        st = (log[0]['t0'] + P.sim_pre90_us * 10 + a + int(round(P.hw_grad_delay_us * 10))) * 1e-7
        tt = np.array([0, P.tramp, P.sm_delta, P.sm_delta + P.tramp]) * 1e-6 + st
        for ax, v in ((0, -dr), (1, -dp_), (2, -ds)):
            gl[ax] += np.interp(t, tt, np.array([0, v, v, 0]) * dac2hz, left=0, right=0)
    b_lobes, _, _ = b_value(t, gl, t_exc[0], t_ref, adc_c[0])
    G = math.sqrt(dr**2 + dp_**2 + ds**2) * dac2hz
    dl, Dl, ep = P.sm_delta * 1e-6, P.big_delta * 1e-6, P.diff_tramp * 1e-6
    b_st = (2 * np.pi * G) ** 2 * (dl ** 2 * (Dl - dl / 3) + ep ** 3 / 30 - dl * ep ** 2 / 6) * 1e-6
    say(f'PPR requested b (row {row})          : {P.acq_b[row]} s/mm^2')
    say(f'PPL nominal b (b_kfac, 39.69 kernel): {D.acq_b_nominal[row]} s/mm^2 (DAC {D.diff_grad[row]})')
    say(f'Stejskal-Tanner trapezoid, (2pi)^2  : {b_st:.1f} s/mm^2')
    say(f'numerical, diffusion lobes only     : {b_lobes:.1f} s/mm^2')
    say(f'numerical, ALL gradients            : {b_all:.1f} s/mm^2 (xx {bdiag[0]:.1f}, yy {bdiag[1]:.2f}, zz {bdiag[2]:.2f})')
    # b at later echoes (crushers/readouts accumulate)
    ks = sorted({1, 2, len(adc_c) - 1} & set(range(1, len(adc_c))))
    bl = [b_value(t, g, t_exc[0], t_ref, adc_c[k])[0] for k in ks]
    say(f'numerical ALL at echo {" / ".join(str(k + 1) for k in ks)}  : {" / ".join(f"{v:.1f}" for v in bl)} s/mm^2')

    # ---- k-space ---------------------------------------------------------------
    say(f'\n## k-space (reduced: shot {shot}, PE_order {P.PE_order})')
    ktraj_adc, _, _, _, _ = seq.calculate_kspace()
    k = ktraj_adc.reshape(3, -1, n)
    dkx = abs(D.read_amp) * dac2hz * P.sample_period * 1e-7
    n = P.no_samples + P.no_discard
    dky = abs(D.gp_inc) * dac2hz * (D.tdp + P.tramp) * 1e-6
    say(f'read  dk = {dkx:.3f} 1/m -> FOV_read  = {1e3/dkx:.2f} mm (PPR FOV {P.fov_mm})')
    say(f'phase dk = {dky:.3f} 1/m -> FOV_phase = {1e3/dky:.2f} mm (gp_inc {D.gp_inc})')
    gp = D.gp_order[log[0]['view']:log[0]['view'] + P.views_per_seg]
    ky_lines = k[1].mean(axis=1) / dky
    say('echo : gp_order | ky/dky (measured, mean over readout) | ky spread in readout')
    bad = 0
    for e in range(len(gp)):
        ok_e = abs(ky_lines[e] - (-gp[e])) < 1e-3 or abs(ky_lines[e] - gp[e]) < 1e-3
        bad += not ok_e
        if e < 4 or e >= len(gp) - 2:
            say(f'{e+1:4d} : {gp[e]:4d} | {ky_lines[e]:9.4f} | {np.ptp(k[1][e]):.2e}')
    sgn = np.sign(np.round(ky_lines[1] / gp[1])) if gp[1] else 1
    say(f'ky = {int(sgn)} * gp_order * dky for all echoes: {"YES" if bad == 0 else "NO (%d)" % bad}')
    kx = k[0] / dkx
    i0 = np.argmin(np.abs(kx), axis=1)
    say(f'kx/dkx range per readout: [{kx.min(axis=1).mean():.2f}, {kx.max(axis=1).mean():.2f}] '
        f'(readout direction {"+->-" if kx[0,0] > kx[0,-1] else "-->+"})')
    frac = []
    for e in range(kx.shape[0]):
        x = kx[e]
        j = np.where(np.sign(x[:-1]) != np.sign(x[1:]))[0]
        frac.append(j[0] + x[j[0]] / (x[j[0]] - x[j[0] + 1]) if len(j) else np.nan)
    frac = np.array(frac)
    say(f'kx = 0 at sample index (0-based, centre of ADC = {n/2-0.5}): echo1 {frac[0]:.3f}, '
        f'echoes 2..N {np.nanmin(frac[1:]):.3f}..{np.nanmax(frac[1:]):.3f}  '
        f'(offset vs ADC centre: {(frac[0]-(n/2-0.5))*P.sample_period/10:.1f} us)')

    # ---- moments -----------------------------------------------------------------
    say('\n## 0th moments (DAC*us and mT/m*ms) per axis')

    def mom(a, b):
        m = (t >= a) & (t < b)
        return g[:, m].sum(axis=1) * DT

    def fmt(m):
        d = m / dac2hz * 1e6
        return ' '.join(f'{ax}={d[i]:12.0f} ({m[i]*hz2mTm*1e3:9.4f})' for i, ax in enumerate('xyz'))

    m_exc = mom(t_exc[0], t_ref[0])
    say('half-intervals:')
    say(f'  90c   -> 180_1c : {fmt(m_exc)}')
    say(f'  180_1 -> echo1  : {fmt(mom(t_ref[0], adc_c[0]))}')
    say(f'  echo1 -> 180_2  : {fmt(mom(adc_c[0], t_ref[1]))}')
    say(f'  180_2 -> echo2  : {fmt(mom(t_ref[1], adc_c[1]))}')
    if len(t_ref) > 2:
        say(f'  echo2 -> 180_3  : {fmt(mom(adc_c[1], t_ref[2]))}')
    say('full intervals between successive refocusing pulses:')
    ref_m = []
    for i in range(len(t_ref) - 1):
        ref_m.append(mom(t_ref[i], t_ref[i + 1]))
    ref_m = np.array(ref_m)
    for i in sorted({0, 1, 2, len(ref_m) - 1} & set(range(len(ref_m)))):
        say(f'  180_{i+1:<2d}-> 180_{i+2:<2d}: {fmt(ref_m[i])}')
    base = ref_m[1] if len(ref_m) > 1 else ref_m[0]   # ETL 2: only 180_1 -> 180_2 exists
    flag = [i for i in range(len(ref_m)) if np.max(np.abs(ref_m[i] - base) / dac2hz * 1e6) > 1.0]
    say(f'intervals differing from 180_2->180_3 by > 1 DAC*us: {[f"180_{i+1}->180_{i+2}" for i in flag]}')
    # slice rephasing after 90 and read balance at echo 1
    rf90_end = t_exc[0] + D.tsel90 / 2 * 1e-6
    m_sl = mom(t_exc[0], rf90_end + 4e-3)
    say(f'\nslice moment 90 centre -> end of rephaser: {m_sl[2]/dac2hz*1e6:.0f} DAC*us '
        f'(= {m_sl[2]/dac2hz*1e6/abs(D.gs_var_rescale):.1f} us of slice-select plateau)')

    with open(os.path.join(args.outdir, f'report_{tag}.txt'), 'w') as f:
        f.write('\n'.join(out) + '\n')

    if args.full:
        print('\n## full protocol k-space coverage')
        sf, _, _, logf = gen.build_sequence(gen.load_params(args.ppr, ov), reduced=False)
        okf, repf = sf.check_timing()
        print('full check_timing:', 'PASS' if okf else 'FAIL')
        kf, _, _, _, _ = sf.calculate_kspace()
        kf = kf.reshape(3, -1, n)
        ky = np.round(kf[1].mean(axis=1) / dky).astype(int)
        nper = (len(ky)) // P.no_experiments
        for rep in range(P.no_experiments):
            kk = ky[rep * nper:(rep + 1) * nper]
            img = kk[P.views_per_seg * P.no_slices:]       # skip navigator trains (3 slices)
            print(f'volume {rep}: readouts {len(kk)}, imaging lines {len(img)}, '
                  f'unique ky per slice set {len(np.unique(img))}, range [{img.min()}, {img.max()}]')


if __name__ == '__main__':
    sys.exit(main())
