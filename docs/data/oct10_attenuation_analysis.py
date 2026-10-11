"""Oct 10 attenuation, ADC (nominal vs modeled effective b), per-echo ADC and direction analysis.

Run after physical_scanner_analysis_2026-10-10.py (it recomputes from the original MRD files via that module).
Signals per volume: first-navigator echo amplitude with the noise floor removed (sqrt(L2^2 - 128*floor)),
first-navigator raw L2 (Oct 7 convention), fixed-interior image mean, fixed-interior noise-corrected rms.
b_eff is the modeled E1 (or echo e) trace b of docs/v181_v1911/FINAL_REPORT.md section 8; see
effective_b() / B_ASSUMPTIONS in the analysis module. The model is a single-path guide, not a calibrated b.
Outputs: oct10_attenuation_fits.csv/.json, oct10_per_echo_adc.csv, oct10_direction_ratios.csv, figures.
"""
from pathlib import Path
import importlib.util, json, csv
import numpy as np
from scipy.optimize import least_squares
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('oct10', HERE/'physical_scanner_analysis_2026-10-10.py')
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)
SIGNALS = ('nav_E1_noise_sub', 'nav_E1_raw_L2', 'image_interior_mean', 'image_interior_excess_rms')


def pair_D(s0, s1, b0, b1):
    if s0 is None or s1 is None or s0 <= 0 or s1 <= 0 or b1 <= b0:
        return None
    return float(np.log(s0/s1)/(b1-b0))


def lowb_D(bs, ss):
    bs = np.asarray(bs, float); ss = np.asarray(ss, float); ok = ss > 0
    if ok.sum() < 3:
        return None, None
    slope, icpt = np.polyfit(bs[ok], np.log(ss[ok]), 1)
    return float(-slope), float(np.sqrt(np.mean((np.polyval([slope, icpt], bs[ok])-np.log(ss[ok]))**2)))


def plateau_fit(bs, y):
    bs = np.asarray(bs, float)-bs[0]; y = np.asarray(y, float)
    mono = least_squares(lambda p: np.exp(-p[0]*bs)-y, [.002], bounds=(0, .01))
    off = least_squares(lambda p: (1-p[1])*np.exp(-p[0]*bs)+p[1]-y, [.002, .02], bounds=([0, 0], [.01, .5]), xtol=1e-12, ftol=1e-12, gtol=1e-12)
    return dict(mono_D=float(mono.x[0]), mono_rms=float(np.sqrt(np.mean(mono.fun**2))), plateau_D=float(off.x[0]), plateau_f=float(off.x[1]), plateau_rms=float(np.sqrt(np.mean(off.fun**2))))


def oct10_signals(scans, ctx, n, sl):
    """dict signal -> list over volumes; plus b, direction labels."""
    s = scans[n]; out = {k: [] for k in SIGNALS}
    for e in range(s['E']):
        nv = ctx['nav_idx'][(n, e, sl, 0)]; im = ctx['img_idx'][(n, e, sl, 'off')]
        out['nav_E1_noise_sub'].append(nv['noise_sub_amp']); out['nav_E1_raw_L2'].append(nv['norm'])
        out['image_interior_mean'].append(im['interior_mean']); out['image_interior_excess_rms'].append(im['interior_excess_rms'])
    return out


def series_rows(day, n, version, seq, sl, bs, dirs, sigs, floor_info):
    """bs, dirs: per-volume nominal b and direction labels. Fits for the b0 + '+x' series (and every direction for pairs)."""
    rows = []; plateau = []
    def val(sig, b, d):
        i = [k for k, (bb, dd) in enumerate(zip(bs, dirs)) if bb == b and (dd == d or (b == 0 and dd == 'none'))]
        return sigs[sig][i[0]] if i else None
    def beff(b, d, echo=1):
        return float(A.effective_b(seq, b, A.direction_code(d), echo)) if seq else None
    for sig in SIGNALS:
        for d in sorted({x for x in dirs if x != 'none'}):
            pairs = [(0, 100), (0, 500), (0, 1000), (0, 2000), (0, 3000), (1000, 3000), (2000, 3000)]
            for lo, hi in pairs:
                s0, s1 = val(sig, lo, d), val(sig, hi, d)
                if s0 is None or s1 is None:
                    continue
                for basis in ('nominal', 'effective'):
                    if basis == 'effective' and not seq:
                        continue
                    blo, bhi = (lo, hi) if basis == 'nominal' else (beff(lo, d), beff(hi, d))
                    D = pair_D(s0, s1, blo, bhi)
                    rows.append(dict(day=day, scan=n, version=version, slice=sl+1, direction=d, signal=sig, basis=basis, fit=f'pair_b{lo}_b{hi}', b_lo=lo, b_hi=hi, b_lo_used=blo, b_hi_used=bhi,
                                     n_points=2, D_mm2_s=D, ln_rms_residual=None, signal_lo=s0, signal_hi=s1, ratio_hi_over_lo=s1/s0 if s0 else None,
                                     hi_signal_over_noise=(s1/(np.sqrt(A.NSAMP*floor_info)) if sig.startswith('nav') else None)))
    # low-b log-linear and plateau on the +x series
    d = '+x' if '+x' in dirs else None
    if d is None:
        return rows, plateau
    idx = [k for k, (b, dd) in enumerate(zip(bs, dirs)) if dd in ('none', d)]
    bsx = [bs[k] for k in idx]
    for sig in SIGNALS:
        ss = [sigs[sig][k] for k in idx]
        for basis in ('nominal', 'effective'):
            if basis == 'effective' and not seq:
                continue
            bu = np.array(bsx, float) if basis == 'nominal' else np.array([beff(b, d) for b in bsx])
            low = np.array(bsx) <= 1000
            if low.sum() >= 3:
                D, res = lowb_D(bu[low], np.array(ss)[low])
                rows.append(dict(day=day, scan=n, version=version, slice=sl+1, direction=d, signal=sig, basis=basis, fit='lowb_loglinear_b<=1000', b_lo=0, b_hi=1000, b_lo_used=float(bu[low][0]), b_hi_used=float(bu[low][-1]),
                                 n_points=int(low.sum()), D_mm2_s=D, ln_rms_residual=res, signal_lo=ss[0], signal_hi=None, ratio_hi_over_lo=None, hi_signal_over_noise=None))
            if len(bsx) == 7 and ss[0] > 0:
                y = np.array(ss)/ss[0]
                pf = plateau_fit(bu, y)
                plateau.append(dict(day=day, scan=n, version=version, slice=sl+1, signal=sig, basis=basis, b_used=bu.tolist(), ratio=y.tolist(), **pf))
    return rows, plateau


def day10(scans, ctx):
    rows = []; plateau = []; curves = []
    for n, s in scans.items():
        seq = A.SEQ[n]
        for sl in range(s['S']):
            sigs = oct10_signals(scans, ctx, n, sl)
            dirs = [A.direction_label(s, e) for e in range(s['E'])]; bs = [float(b) for b in s['b']]; bs = [int(b) for b in bs]
            r, p = series_rows('oct10', n, A.VERSION[n], seq, sl, bs, dirs, sigs, ctx['floors'][n])
            rows += r; plateau += p
            for e in range(s['E']):
                code = A.direction_code(dirs[e])
                curves.append(dict(day='oct10', scan=n, version=A.VERSION[n], slice=sl+1, volume=e+1, b=bs[e], direction=dirs[e], b_eff_E1=float(A.effective_b(seq, bs[e], code, 1)),
                                   **{k: sigs[k][e] for k in SIGNALS}, **{k+'_ratio_to_b0': sigs[k][e]/sigs[k][0] for k in SIGNALS}))
    return rows, plateau, curves


def day07(o7):
    rows = []; plateau = []; curves = []
    for n, v in o7.items():
        seq = v['seq']
        if seq is None:
            continue
        b = [int(x) for x in v['b']]; dirs = ['none' if x == 0 else '+x' for x in b]
        sigs = {'nav_E1_noise_sub': v['nav_amp'][:, 0].tolist(), 'nav_E1_raw_L2': v['nav_norm'][:, 0].tolist(),
                'image_interior_mean': [v['img'][float(x)]['interior_mean'] for x in b], 'image_interior_excess_rms': [v['img'][float(x)]['interior_excess_rms_approx'] for x in b]}
        r, p = series_rows('oct07', n, v['version'], seq, 0, b, dirs, sigs, v['noise_floor'])
        rows += r; plateau += p
        for e in range(len(b)):
            curves.append(dict(day='oct07', scan=n, version=v['version'], slice=1, volume=e+1, b=b[e], direction=dirs[e], b_eff_E1=float(A.effective_b(seq, b[e], 'x', 1)),
                               **{k: sigs[k][e] for k in SIGNALS}, **{k+'_ratio_to_b0': sigs[k][e]/sigs[k][0] for k in SIGNALS}))
    return rows, plateau, curves


def per_echo(scans, ctx):
    rows = []
    for n, s in scans.items():
        seq = A.SEQ[n]
        for sl in range(s['S']):
            e0 = 0; dirs = [A.direction_label(s, e) for e in range(s['E'])]
            for hi in (1000, 3000):
                cand = [e for e in range(s['E']) if s['b'][e] == hi and dirs[e] == '+x']
                if not cand:
                    continue
                e1 = cand[0]
                for j in range(8):
                    a0 = ctx['nav_idx'][(n, e0, sl, j)]['noise_sub_amp']; a1 = ctx['nav_idx'][(n, e1, sl, j)]['noise_sub_amp']
                    lo_floor = np.sqrt(A.NSAMP*ctx['floors'][n])
                    for lo, e_lo in [(0, e0)] + ([(1000, [e for e in range(s['E']) if s['b'][e] == 1000 and dirs[e] == '+x'][0])] if hi == 3000 else []):
                        a_lo = ctx['nav_idx'][(n, e_lo, sl, j)]['noise_sub_amp']
                        if lo == 1000:
                            pass
                        blo_nom, bhi_nom = lo, hi
                        blo_eff, bhi_eff = float(A.effective_b(seq, lo, 'x', j+1)), float(A.effective_b(seq, hi, 'x', j+1))
                        rows.append(dict(scan=n, version=A.VERSION[n], slice=sl+1, echo=j+1, b_lo=lo, b_hi=hi, amp_lo=a_lo, amp_hi=a1, ratio_hi_over_lo=a1/a_lo if a_lo else None,
                                         hi_amp_over_noise=a1/lo_floor, b_lo_eff=blo_eff, b_hi_eff=bhi_eff, D_nominal=pair_D(a_lo, a1, blo_nom, bhi_nom), D_effective=pair_D(a_lo, a1, blo_eff, bhi_eff)))
    return rows


def directions(scans, ctx, fits):
    rows = []
    for n in ('E', 'G'):
        s = scans[n]; seq = A.SEQ[n]; dirs = [A.direction_label(s, e) for e in range(s['E'])]
        for sig in SIGNALS:
            sigs = oct10_signals(scans, ctx, n, 0)[sig]
            s0 = sigs[0]
            Dref = next(r['D_mm2_s'] for r in fits if r['scan'] == n and r['signal'] == sig and r['basis'] == 'effective' and r['fit'] == 'pair_b0_b1000' and r['direction'] == '+x')
            for b in (1000, 3000):
                ref_e = [e for e in range(s['E']) if s['b'][e] == b and dirs[e] == '+x'][0]
                for e in range(s['E']):
                    if s['b'][e] != b:
                        continue
                    d = dirs[e]; code = A.direction_code(d)
                    beff = float(A.effective_b(seq, b, code, 1)); beff_x = float(A.effective_b(seq, b, 'x', 1))
                    pred = float(np.exp(-Dref*(beff-beff_x)))
                    rows.append(dict(scan=n, version=A.VERSION[n], signal=sig, b=b, direction=d, echo=1, ratio_to_b0=sigs[e]/s0, ratio_to_plus_x=sigs[e]/sigs[ref_e] if sigs[ref_e] > 0 else None,
                                     b_eff_model=beff, predicted_ratio_to_plus_x=pred, D_ref_effective_b0_b1000_plusx=Dref,
                                     note=('z cross term +37.3 s/mm2 at b1000 (FINAL_REPORT 8)' if code == 'z' and seq == 'v181' else
                                           ('ASSUMED: v1.911 y/-x equal +x; z uses the v1.81 cross term (report gives only +X rows for v1.911)' if seq == 'v1911' else 'polarity independent on v1.81 (FINAL_REPORT 8)'))))
        # per-echo -x/+x and z/x, b1000, navigator noise-sub
        ex = bindex_dir(s, 1000, '+x'); em = bindex_dir(s, 1000, '-x'); ey = bindex_dir(s, 1000, '+y'); ez = bindex_dir(s, 1000, '+z')
        for j in range(8):
            g = lambda e: ctx['nav_idx'][(n, e, 0, j)]['norm']
            rows.append(dict(scan=n, version=A.VERSION[n], signal='nav_L2_per_echo', b=1000, direction='ratios', echo=j+1, ratio_to_b0=None, ratio_to_plus_x=None, b_eff_model=None,
                             predicted_ratio_to_plus_x=None, D_ref_effective_b0_b1000_plusx=None,
                             note=f'minus_x/plus_x={g(em)/g(ex):.4f}; plus_y/plus_x={g(ey)/g(ex):.4f}; plus_z/plus_x={g(ez)/g(ex):.4f}'))
    return rows


def bindex_dir(s, b, label):
    return next(e for e in range(s['E']) if s['b'][e] == b and A.direction_label(s, e) == label)


def write_csv(path, records):
    fields = list(dict.fromkeys(k for r in records for k in r))
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(records)


def figures(scans, ctx, curves, fits, plateau):
    A.OUT.mkdir(parents=True, exist_ok=True)
    col = {('oct10', 'A'): 'tab:blue', ('oct10', 'C'): 'tab:cyan', ('oct10', 'B'): 'tab:purple', ('oct10', 'D'): 'tab:pink', ('oct07', 'test1b'): 'k', ('oct07', 'test2c'): 'tab:green'}
    sel = [c for c in curves if (c['day'], c['scan']) in col and c['direction'] in ('none', '+x')]
    fig, axs = plt.subplots(2, 3, figsize=(18, 10), layout='constrained')
    grid = np.linspace(0, 6200, 300)
    for key in col:
        pts = [c for c in sel if (c['day'], c['scan']) == key]
        if not pts:
            continue
        b = np.array([p['b'] for p in pts]); be = np.array([p['b_eff_E1'] for p in pts]); lab = f'{key[1]}{" (Oct 7)" if key[0] == "oct07" else ""} {pts[0]["version"]}'
        ls = '--' if key[0] == 'oct07' else '-'
        for ax, x, sig in [(axs[0, 0], b, 'nav_E1_noise_sub'), (axs[0, 1], be, 'nav_E1_noise_sub'), (axs[0, 2], be, 'image_interior_excess_rms'), (axs[1, 0], b, 'image_interior_excess_rms')]:
            y = np.array([p[sig+'_ratio_to_b0'] for p in pts]); ok = y > 0
            ax.plot(x[ok], y[ok], 'o'+ls, color=col[key], label=lab, ms=4)
    for ax in (axs[0, 0], axs[0, 1], axs[0, 2], axs[1, 0]):
        for D, c in [(.0020, '0.6'), (.0023, '0.3')]:
            ax.plot(grid, np.exp(-D*grid), ':', color=c, label=f'exp(-{D} b)')
        ax.set_yscale('log'); ax.set_ylim(3e-4, 1.5); ax.grid(alpha=.2); ax.legend(fontsize=7)
    axs[0, 0].set_title('navigator E1 (noise-subtracted) / b0 vs NOMINAL b'); axs[0, 1].set_title('same vs modeled EFFECTIVE b (E1)')
    axs[0, 2].set_title('image interior (noise-corrected rms) / b0 vs EFFECTIVE b'); axs[1, 0].set_title('image interior / b0 vs NOMINAL b')
    # ADC summary: pair b0/b1000, nominal vs effective, nav and image
    names = ['A', 'C', 'B', 'D', 'E', 'G', 'H', 'I', 'J']
    ax = axs[1, 1]; xs = np.arange(len(names)); wd = .2
    for k, (sig, basis, c) in enumerate([('nav_E1_noise_sub', 'nominal', 'tab:blue'), ('nav_E1_noise_sub', 'effective', 'tab:orange'), ('image_interior_mean', 'nominal', 'tab:cyan'), ('image_interior_mean', 'effective', 'tab:red')]):
        vals = [next((r['D_mm2_s'] for r in fits if r['day'] == 'oct10' and r['scan'] == n and r['slice'] == 1 and r['direction'] == '+x' and r['signal'] == sig and r['basis'] == basis and r['fit'] == 'pair_b0_b1000'), np.nan) for n in names]
        ax.bar(xs+(k-1.5)*wd, np.array(vals)*1e3, wd, color=c, label=f'{sig.split("_")[0]} {basis}')
    ax.axhspan(2.0, 2.3, color='g', alpha=.15, label='free water 20-25 C')
    ax.set_xticks(xs, names); ax.set_ylabel('ADC (1e-3 mm^2/s), b0/b1000 pair'); ax.set_ylim(1.4, 2.8); ax.legend(fontsize=7); ax.set_title('Pair ADC: nominal vs modeled effective b'); ax.grid(alpha=.2)
    ax = axs[1, 2]
    for p in plateau:
        key = (p['day'], p['scan'])
        if key in col and p['signal'] == 'nav_E1_noise_sub' and p['basis'] == 'effective':
            ax.plot(np.array(p['b_used']), p['ratio'], 'o', color=col[key], ms=4)
            ax.plot(grid, (1-p['plateau_f'])*np.exp(-p['plateau_D']*grid)+p['plateau_f'], color=col[key], ls='--' if p['day'] == 'oct07' else '-', label=f"{p['scan']}: D={p['plateau_D']*1e3:.2f}e-3 f={p['plateau_f']:.1e}")
    ax.set_yscale('log'); ax.set_ylim(3e-4, 1.5); ax.legend(fontsize=7); ax.grid(alpha=.2); ax.set_title('(1-f)exp(-D b_eff)+f fits to noise-subtracted nav E1 (7-b scans)')
    for ax in axs.flat:
        ax.set_xlabel('b (s/mm^2)') if ax is not axs[1, 1] else None
    fig.suptitle('Oct 10 attenuation: A (v1.81), C (v1.8), B (v1.911), D (v1.91) with Oct 7 v1.8 test1b and v1.91 test2c (dashed)\nEffective b is a modeled single-path trace (FINAL_REPORT section 8), not a measured b')
    A.save_figure(fig, A.OUT/'attenuation_curves.png')


def figure_echo_adc(per, scans):
    fig, axs = plt.subplots(1, 2, figsize=(14, 5.5), layout='constrained')
    cols = dict(A='tab:blue', C='tab:cyan', E='tab:green', H='tab:olive', J='tab:red', K='tab:brown', B='tab:purple', D='tab:pink', G='tab:gray', I='tab:orange')
    for n in cols:
        pts = [r for r in per if r['scan'] == n and r['b_lo'] == 0 and r['b_hi'] == 1000 and r['slice'] == (2 if n == 'K' else 1)]
        for ax, key in [(axs[0], 'D_nominal'), (axs[1], 'D_effective')]:
            ax.plot([p['echo'] for p in pts], [p[key]*1e3 for p in pts], 'o-', color=cols[n], label=n, ms=4)
    for ax, t in [(axs[0], 'nominal b'), (axs[1], 'modeled effective b (per-echo rows)')]:
        ax.axhspan(2.0, 2.3, color='g', alpha=.12); ax.set_title('navigator ADC per echo, b0/b1000, '+t); ax.set_xlabel('echo'); ax.set_ylabel('ADC (1e-3 mm^2/s)'); ax.grid(alpha=.2); ax.legend(ncol=2, fontsize=8)
    fig.suptitle('Per-echo ADC from noise-subtracted navigator amplitudes (K: slice 2); green band = free water at 20-25 C')
    A.save_figure(fig, A.OUT/'per_echo_adc.png')


def figure_directions(dir_rows):
    fig, axs = plt.subplots(1, 2, figsize=(13, 5), layout='constrained')
    for ax, sig in zip(axs, ('nav_E1_noise_sub', 'image_interior_mean')):
        for k, n in enumerate('EG'):
            pts = [r for r in dir_rows if r['scan'] == n and r['signal'] == sig and r['b'] == 1000 and r['echo'] == 1 and r['direction'] in ('+x', '-x', '+y', '+z')]
            x = np.arange(len(pts))+(k-.5)*.35
            ax.bar(x, [p['ratio_to_plus_x'] for p in pts], .33, label=f'{n} measured')
            ax.plot(x, [p['predicted_ratio_to_plus_x'] for p in pts], 'k_', ms=18, mew=2, label=f'{n} predicted' if k == 0 else None)
        ax.set_xticks(np.arange(4), ['+x', '-x', '+y', '+z']); ax.axhline(1, color='0.5', lw=.5); ax.set_ylim(.7, 1.3); ax.set_title(f'b1000 signal / +x signal ({sig})'); ax.legend(fontsize=8); ax.grid(alpha=.2)
    fig.suptitle('Direction ratios at b1000, E (v1.81) and G (v1.911); black marks: model exp(-D_eff (b_eff,dir - b_eff,+x))')
    A.save_figure(fig, A.OUT/'direction_ratios.png')


def main():
    scans = A.load_scans(); ctx = A.compute_all(scans); o7 = A.load_oct07()
    r10, p10, c10 = day10(scans, ctx); r07, p07, c07 = day07(o7)
    fits = r10+r07; plateau = p10+p07; curves = c10+c07
    per = per_echo(scans, ctx); dir_rows = directions(scans, ctx, fits)
    payload = dict(method=('Pair ADC = ln(S_lo/S_hi)/(b_hi-b_lo); low-b = OLS of ln S on b over b0/100/500/1000 (free intercept, 7-b scans); plateau = least squares of '
                           'S/S0 to (1-f)exp(-D(b-b0))+f with D<=0.01, f<=0.5 (7-b scans); signals: noise-subtracted first navigator echo, raw first navigator L2 (Oct 7 convention), '
                           'fixed-interior image mean, fixed-interior noise-corrected rms. basis nominal uses requested b, effective uses effective_b() (see assumptions). No uncertainty estimates.'),
                   b_effective_assumptions=A.B_ASSUMPTIONS, fits=fits, plateau=plateau, curves=curves, per_echo=per, directions=dir_rows,
                   mrd_sha256={n: s['mrd_sha256'] for n, s in scans.items()})
    (HERE/'oct10_attenuation_fits.json').write_text(json.dumps(payload, indent=2))
    write_csv(HERE/'oct10_attenuation_fits.csv', fits+[dict(day=p['day'], scan=p['scan'], version=p['version'], slice=p['slice'], direction='+x', signal=p['signal'], basis=p['basis'], fit='plateau_exp_plus_constant', n_points=7,
                                                          D_mm2_s=p['plateau_D'], ln_rms_residual=None, ratio_hi_over_lo=p['plateau_f'], hi_signal_over_noise=None, b_lo_used=p['b_used'][0], b_hi_used=p['b_used'][-1],
                                                          signal_lo=p['plateau_rms'], note='D=plateau_D; ratio_hi_over_lo column holds plateau fraction f; signal_lo column holds rms ratio residual; mono_D=%.6g' % p['mono_D']) for p in plateau])
    write_csv(HERE/'oct10_attenuation_curves.csv', curves)
    write_csv(HERE/'oct10_per_echo_adc.csv', per)
    write_csv(HERE/'oct10_direction_ratios.csv', dir_rows)
    figures(scans, ctx, curves, fits, plateau); figure_echo_adc(per, scans); figure_directions(dir_rows)
    for r in fits:
        if r['day'] == 'oct10' and r['direction'] == '+x' and r['slice'] == 1 and r['fit'] == 'pair_b0_b1000' and r['signal'] in ('nav_E1_noise_sub', 'image_interior_mean'):
            print(r['scan'], r['signal'], r['basis'], 'D=%.6f' % r['D_mm2_s'])


if __name__ == '__main__':
    main()
