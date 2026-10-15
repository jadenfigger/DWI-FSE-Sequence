"""Navigator echo analysis for the 2026-10-11 scans, with a 10-10 v1.911 comparison.

Run from the repository root:  python docs/data/oct11_navigator_analysis.py
Reads the MRDs read-only through docs/data/oct11_load.py (the 10-10 comparison scans are
loaded through the same loader with its folder lookup redirected). Writes:
  docs/data/oct11_navigator_echoes.csv      one row per session/scan/volume/slice/echo
  docs/data/oct11_navigator_summary.json    analyses a-g (also printed)
  docs/figures/physical_scanner_2026-10-11/navigator_echo_trains.png
  docs/figures/physical_scanner_2026-10-11/multislice_phase.png

Definitions
- Noise power per complex sample (one value per scan): for each volume and slice, median |k|^2 over the
  32 x 32 outer corner of the imaging k-space (16 outermost PE rows at each end, 16 samples at each readout
  end), divided by ln 2. The scan value is the median over volumes and slices.
- A_e = sqrt(max(sum|nav_e|^2 - nsamp*sigma^2, 0)), noise-subtracted echo amplitude.
- amp_over_noise_rms = A_e / sigma.  energy_z = (sum|nav_e|^2 - nsamp*sigma^2) / (sqrt(nsamp)*sigma^2),
  which is ~N(0,1) for noise alone; it is the significance of the echo energy above the noise floor.
- DC phase = angle(sum(nav_e) * conj(sum(nav_1))).  Inner-product phase = angle(sum(nav_e * conj(nav_1))).
  Both are relative to echo 1 and wrapped to [-180, 180].
- Peak centroid = power-weighted centroid of the 5 samples around argmax|nav_e| (clipped at the edges).
- Echo time = TE + (n-1)*ESP from the header (ms, as stored by the loader).
"""
from pathlib import Path
import sys, json, csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

DATA = Path(__file__).resolve().parent
ROOT = DATA.parents[1]
sys.path.insert(0, str(DATA))
import oct11_load as O  # noqa: E402
from oct11_load import load, SCANS, direction_label  # noqa: E402

FIG = ROOT/'docs/figures/physical_scanner_2026-10-11'
CSV_PATH = DATA/'oct11_navigator_echoes.csv'
JSON_PATH = DATA/'oct11_navigator_summary.json'
ETL = 8
TEN_TEN = {'1010_B': 'v1911_testB', '1010_G': 'v1911_testG', '1010_I': 'v1911_testI'}


def load_1010(key):
    """10-10 v1.911 scan through the shared loader, with the folder lookup redirected."""
    folder = O.EXP/f'FSE-DWI_10-10-2026_{TEN_TEN[key]}'
    orig = O.folder
    O.folder = lambda _letter: folder
    try:
        s = load(key[-1])
    finally:
        O.folder = orig
    s['version'] = 'v1.911 (10-10)'
    return s


def wrap(x):
    return (np.asarray(x, float) + 180.0) % 360.0 - 180.0


def cmean(deg):
    return float(np.degrees(np.angle(np.mean(np.exp(1j*np.radians(np.asarray(deg, float)))))))


def outer_noise_volume(s):
    k = s['kspace']; N, n = s['N'], s['nsamp']
    rows = np.r_[0:16, N-16:N]; cols = np.r_[0:16, n-16:n]
    p = np.abs(k[:, :, rows][:, :, :, cols])**2
    return np.median(p.reshape(p.shape[0], p.shape[1], -1), axis=2)/np.log(2)


def echo_stats(nav, sigma2, n):
    p = np.abs(nav)**2
    tot = p.sum(1)
    excess = tot - n*sigma2
    amp = np.sqrt(np.maximum(excess, 0.0))
    dc = nav.sum(1)
    ip = nav @ nav[0].conj()
    peak = np.argmax(np.abs(nav), axis=1)
    cen = np.empty(len(nav))
    for e, pk in enumerate(peak):
        lo, hi = max(pk-2, 0), min(pk+3, n)
        w = p[e, lo:hi]
        cen[e] = (np.arange(lo, hi)*w).sum()/w.sum()
    return dict(raw_norm=np.sqrt(tot), amp=amp, excess=excess, z=excess/(np.sqrt(n)*sigma2),
                snr=amp/np.sqrt(sigma2), dc_phase=np.degrees(np.angle(dc*np.conj(dc[0]))),
                ip_phase=np.degrees(np.angle(ip)), cen=cen, peak=peak)


def analyse(key, s):
    est = outer_noise_volume(s)
    sigma2 = float(np.median(est))
    st = {(v, sl): echo_stats(s['navs'][v, sl], sigma2, s['nsamp'])
          for v in range(s['E']) for sl in range(s['S'])}
    return dict(key=key, s=s, sigma2=sigma2, est=est, st=st,
                labels=[direction_label(x) for x in s['vec']],
                t_ms=float(s['te']) + np.arange(ETL)*float(s['esp']))


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return jsonable(o.tolist())
    if isinstance(o, (bool, np.bool_)):
        return bool(o)
    if isinstance(o, (int, np.integer)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return float(o) if np.isfinite(o) else None
    return o


def write_csv(D):
    cols = ['session', 'scan', 'version', 'volume', 'b', 'direction', 'slice', 'slice_offset_mm', 'echo', 'echo_time_ms',
            'rx_gain', 'dwell_us', 'nsamp', 'nav_norm_raw', 'noise_power_per_sample', 'noise_outer_volume',
            'amp_noise_sub', 'amp_over_noise_rms', 'energy_z', 'amp_norm_echo1', 'dc_phase_deg_vs_echo1',
            'ip_phase_deg_vs_echo1', 'peak_centroid_sample', 'peak_argmax_sample']
    n_rows = 0
    with open(CSV_PATH, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for key, d in D.items():
            s = d['s']
            session = '2026-10-10' if key.startswith('1010') else '2026-10-11'
            scan = key
            for v in range(s['E']):
                for sl in range(s['S']):
                    st = d['st'][(v, sl)]
                    for e in range(ETL):
                        a1 = st['amp'][0]
                        w.writerow(dict(
                            session=session, scan=scan, version=s['version'], volume=v+1, b=float(s['b'][v]),
                            direction=d['labels'][v], slice=sl+1, slice_offset_mm=float(s['offsets_mm'][sl]),
                            echo=e+1, echo_time_ms=float(d['t_ms'][e]), rx_gain=s['gains']['rx'], dwell_us=s['dwell_us'],
                            nsamp=s['nsamp'], nav_norm_raw=float(st['raw_norm'][e]), noise_power_per_sample=d['sigma2'],
                            noise_outer_volume=float(d['est'][v, sl]), amp_noise_sub=float(st['amp'][e]),
                            amp_over_noise_rms=float(st['snr'][e]), energy_z=float(st['z'][e]),
                            amp_norm_echo1=float(st['amp'][e]/a1) if a1 > 0 else '',
                            dc_phase_deg_vs_echo1=float(st['dc_phase'][e]), ip_phase_deg_vs_echo1=float(st['ip_phase'][e]),
                            peak_centroid_sample=float(st['cen'][e]), peak_argmax_sample=int(st['peak'][e])))
                        n_rows += 1
    return n_rows


def main():
    D = {}
    for k in SCANS:
        D[k] = analyse(k, load(k))
    for k in TEN_TEN:
        D[k] = analyse(k, load_1010(k))

    def ST(key, v, sl=0):
        return D[key]['st'][(v, sl)]

    def A(key, v, sl=0):
        return ST(key, v, sl)['amp']

    def ix(key, b):
        idx = [i for i, x in enumerate(D[key]['s']['b']) if abs(x-b) < 1e-6]
        if not idx:
            raise KeyError(f'{key}: no volume with b={b}')
        return idx[0]

    def med_ratio(num, den):
        den = np.asarray(den, float)
        num = np.asarray(num, float)
        r = np.divide(num[1:8], den[1:8], out=np.full(7, np.nan), where=den[1:8] > 0)
        return dict(median_e2_e8=float(np.nanmedian(r)), per_echo_e2_e8=r.tolist())

    out = {}
    # ---- noise table and sanity ----
    out['noise'] = {}
    print('=== Noise floor (per scan, outer k-space corner, median over volumes/slices) ===')
    for k, d in D.items():
        s = d['s']
        est = d['est']
        out['noise'][k] = dict(version=s['version'], rx_gain=s['gains']['rx'], dwell_us=s['dwell_us'], nsamp=s['nsamp'],
                               b=s['b'].tolist(), sigma2=d['sigma2'], sigma_rms=float(np.sqrt(d['sigma2'])),
                               per_volume_outer_min=float(est.min()), per_volume_outer_max=float(est.max()),
                               mean_power_per_sample_e1=[float(np.mean(np.abs(s['navs'][v, 0])**2)) for v in range(s['E'])])
        print(f"{k:8s} {s['version']:14s} rx={s['gains']['rx']:6.1f} dw={s['dwell_us']:4.0f} nsamp={s['nsamp']:3d} "
              f"sigma2={d['sigma2']:10.3f} sigma={np.sqrt(d['sigma2']):7.3f}  outer-vol range [{est.min():.3f}, {est.max():.3f}]")
    print()

    # ---- (a) Scan A E1 deficit and phases ----
    print('=== (a) Scan A: E1 deficit, phases ===')
    ib100 = ix('A', 100)
    ratio_v = [A('A', v)[0]/np.median(A('A', v)[1:]) for v in range(len(D['A']['s']['b']))]
    a_rows = []
    for v in range(len(ratio_v)):
        ip = ST('A', v)['ip_phase']; dc = ST('A', v)['dc_phase']
        oe = wrap(cmean(ip[[2, 4, 6]]) - cmean(ip[[1, 3, 5]]))
        succ = float(np.mean(np.abs(wrap(np.diff(ip)))))
        row = dict(b=float(D['A']['s']['b'][v]), e1_over_median_e2_e8=float(ratio_v[v]),
                   e1_deficit_pct_vs_b100=float((1-ratio_v[v]/ratio_v[ib100])*100),
                   e1_rel_e2_ip_deg=float(-ip[1]), e1_rel_e2_dc_deg=float(-dc[1]),
                   odd_minus_even_ip_deg=oe, mean_abs_successive_ip_deg=succ,
                   echo1_amp=float(A('A', v)[0]), echo1_snr=float(ST('A', v)['snr'][0]))
        a_rows.append(row)
        print(f"  b={row['b']:6g} E1/med(E2-8)={row['e1_over_median_e2_e8']:.4f} E1 deficit vs b100={row['e1_deficit_pct_vs_b100']:+6.2f}% "
              f"E1 rel E2 ip={row['e1_rel_e2_ip_deg']:+7.2f} dc={row['e1_rel_e2_dc_deg']:+7.2f} deg  odd-even={oe:+7.2f} deg  "
              f"mean|succ|={succ:6.2f}  E1 amp={row['echo1_amp']:.4g}")
    out['a'] = dict(volumes=a_rows, reference_volume_b100_index=int(ib100))
    print()

    # ---- (b) attenuation from navigators ----
    print('=== (b) Attenuation from navigator amplitudes (median over echoes 2-8) ===')
    b = {}
    b['A_b1000_over_b10'] = med_ratio(A('A', ix('A', 1000)), A('A', ix('A', 10)))
    b['A_b1000_over_b0'] = med_ratio(A('A', ix('A', 1000)), A('A', ix('A', 0)))
    b['A_b6000_over_b10'] = med_ratio(A('A', ix('A', 6000)), A('A', ix('A', 10)))
    ref_c = (A('C', 0) + A('C', len(D['C']['s']['b'])-1))/2
    c_dir = {}
    for v in range(1, len(D['C']['s']['b'])-1):
        key_ = f"b{int(D['C']['s']['b'][v])}{D['C']['labels'][v]}"
        c_dir[key_] = med_ratio(A('C', v), ref_c)
    b['C_per_direction_over_mean_b10'] = c_dir
    b['C_axis_geomean'] = {}
    for bb in (500, 1000):
        for ax in 'xyz':
            rp = c_dir[f'b{bb}+{ax}']['median_e2_e8']; rm = c_dir[f'b{bb}-{ax}']['median_e2_e8']
            b['C_axis_geomean'][f'b{bb}_{ax}'] = float(np.sqrt(rp*rm))
    b['T_b1000_over_b10'] = med_ratio(A('T', ix('T', 1000)), A('T', ix('T', 10)))
    b['TT_b1000_over_b10'] = med_ratio(A('TT', ix('TT', 1000)), A('TT', ix('TT', 10)))
    b['E_b1000_over_b10'] = med_ratio(A('E', ix('E', 1000)), A('E', ix('E', 10)))
    b['E_b6000_over_b10'] = med_ratio(A('E', ix('E', 6000)), A('E', ix('E', 10)))
    b['M_b1000_over_b10'] = med_ratio(A('M', ix('M', 1000)), A('M', ix('M', 10)))
    b['Q_b1000_over_b10'] = med_ratio(A('Q', ix('Q', 1000)), A('Q', ix('Q', 10)))
    b['Q_b6000_over_b10'] = med_ratio(A('Q', ix('Q', 6000)), A('Q', ix('Q', 10)))
    b['AB_b1000_raw_amp_per_echo'] = A('AB', 0).tolist()
    b['AB_b1000_snr_per_echo'] = ST('AB', 0)['snr'].tolist()
    for k_, v_ in b.items():
        if k_ in ('C_per_direction_over_mean_b10', 'C_axis_geomean', 'AB_b1000_raw_amp_per_echo', 'AB_b1000_snr_per_echo'):
            continue
        print(f"  {k_:28s} {v_['median_e2_e8']:.4f}")
    for k_, v_ in c_dir.items():
        print(f"  C {k_:10s} {v_['median_e2_e8']:.4f}")
    for k_, v_ in b['C_axis_geomean'].items():
        print(f"  C geomean {k_:10s} {v_:.4f}")
    print(f"  AB raw amp per echo: {np.round(A('AB', 0), 1).tolist()}")
    out['b'] = b
    print()

    # ---- (c) echo train decay at low-b reference ----
    print('=== (c) Echo train decay A_e/A_1 at b10 (and per slice) ===')
    c = {}
    specs = [('A', [0]), ('C', [0]), ('E', [0]), ('G', [0]), ('I', [0]), ('M', [0]), ('Q', [0]), ('T', [0]),
             ('TT', [0]), ('K', [0, 1, 2]), ('O', [0, 1, 2]), ('S', [0, 1, 2]), ('V', [0, 1, 2])]
    for key, sls in specs:
        v10 = ix(key, 10)
        for sl in sls:
            am = A(key, v10, sl)
            dec = am/am[0] if am[0] > 0 else np.full(ETL, np.nan)
            name = key if len(sls) == 1 else f'{key}_slice{sl+1}'
            c[name] = dict(volume_b10_index=v10, offset_mm=float(D[key]['s']['offsets_mm'][sl]),
                           decay=dec.tolist(), echo8_over_echo1=float(dec[-1]))
            print(f"  {name:10s} v{v10} off={c[name]['offset_mm']:+5.1f}mm  " +
                  ' '.join(f'{x:.3f}' for x in dec) + f"   E8/E1={dec[-1]:.3f}")
    out['c'] = c
    print()

    # ---- (d) multi-slice odd/even phase ----
    print('=== (d) Multi-slice phase (ip phase vs echo 1, degrees) ===')
    dres = {}
    for key in ('K', 'O', 'S', 'V'):
        s = D[key]['s']
        dres[key] = []
        print(f"  {key}: slices offsets {np.round(s['offsets_mm'], 2).tolist()}")
        for sl in range(s['S']):
            vals = []
            for v in range(s['E']):
                st = ST(key, v, sl)
                ip = st['ip_phase']
                oe = wrap(cmean(ip[[2, 4, 6]]) - cmean(ip[[1, 3, 5]]))
                rec = dict(volume=v+1, b=float(s['b'][v]), slice=sl+1, offset_mm=float(s['offsets_mm'][sl]),
                           odd_minus_even_deg=float(oe), e4_rel_e1_deg=float(wrap(ip[3])),
                           echo1_snr=float(st['snr'][0]), echo2_to_8_snr_min=float(np.min(st['snr'][1:])))
                vals.append(rec)
                print(f"    slice{sl+1} off={rec['offset_mm']:+5.1f} v{v+1} b={rec['b']:6g}  odd-even={oe:+8.2f}  "
                      f"E4 rel E1={rec['e4_rel_e1_deg']:+8.2f}  SNR E1={rec['echo1_snr']:9.2f} min(E2-8)={rec['echo2_to_8_snr_min']:9.2f}")
            dres[key].append(vals)
    out['d'] = dres
    print()

    # ---- (e) echo peak centroids ----
    print('=== (e) Echo peak centroid (samples, 0-indexed) ===')
    e_out = {}
    for key in ('E', 'G', 'I', 'A', 'M', 'Q', 'V'):
        s = D[key]['s']
        rows = np.array([ST(key, v, sl)['cen'] for v in range(s['E']) for sl in range(s['S'])])
        per_echo = rows.mean(0)
        oe_rows = rows[:, [0, 2, 4, 6]].mean(1) - rows[:, [1, 3, 5, 7]].mean(1)
        e_out[key] = dict(version=s['version'], esp=float(s['esp']), nsamp=s['nsamp'], centre_expected=s['nsamp']/2,
                          mean_per_echo=per_echo.tolist(), min_all=float(rows.min()), max_all=float(rows.max()),
                          odd_minus_even_mean=float(oe_rows.mean()), odd_minus_even_sd=float(oe_rows.std()),
                          n_volume_slices=int(rows.shape[0]))
        print(f"  {key:2s} ESP{s['esp']:4.0f} nsamp={s['nsamp']:3d} expect~{s['nsamp']/2:.1f}  mean/echo=" +
              ' '.join(f'{x:.2f}' for x in per_echo) +
              f"  odd-even (1,3,5,7 minus 2,4,6,8)={oe_rows.mean():+.3f} (sd {oe_rows.std():.3f}) over {rows.shape[0]} vol-slices")
    out['e'] = e_out
    print()

    # ---- (f) drift: T vs A, TT vs T ----
    print('=== (f) Drift: T vs A, TT vs T (ratios only; RX gain differs) ===')
    f_out = {}
    f_out['A_b1000_over_b10'] = b['A_b1000_over_b10']
    f_out['T_b1000_over_b10'] = b['T_b1000_over_b10']
    f_out['TT_b1000_over_b10'] = b['TT_b1000_over_b10']
    decay_t = A('T', ix('T', 10))/A('T', ix('T', 10))[0]
    decay_tt = A('TT', ix('TT', 10))/A('TT', ix('TT', 10))[0]
    decay_a = A('A', ix('A', 10))/A('A', ix('A', 10))[0]
    f_out['decay_b10'] = dict(A=decay_a.tolist(), T=decay_t.tolist(), TT=decay_tt.tolist(),
                              E8_over_E1=dict(A=float(decay_a[-1]), T=float(decay_t[-1]), TT=float(decay_tt[-1])))
    print(f"  A  b1000/b10 median e2-8 = {b['A_b1000_over_b10']['median_e2_e8']:.4f}")
    print(f"  T  b1000/b10 median e2-8 = {b['T_b1000_over_b10']['median_e2_e8']:.4f}")
    print(f"  TT b1000/b10 median e2-8 = {b['TT_b1000_over_b10']['median_e2_e8']:.4f}")
    print('  per-echo b1000/b10 e2..e8:')
    print('    A ', np.round(b['A_b1000_over_b10']['per_echo_e2_e8'], 4).tolist())
    print('    T ', np.round(b['T_b1000_over_b10']['per_echo_e2_e8'], 4).tolist())
    print('    TT', np.round(b['TT_b1000_over_b10']['per_echo_e2_e8'], 4).tolist())
    print(f"  b10 decay A_e/A_1: {np.round(decay_a, 3).tolist()}")
    print(f"  b10 decay T_e/T_1:  {np.round(decay_t, 3).tolist()}")
    print(f"  b10 decay TT_e/TT_1: {np.round(decay_tt, 3).tolist()}")
    out['f'] = f_out
    print()

    # ---- (g) ss-MGOT scans and 10-10 comparison ----
    print('=== (g) ss-MGOT scans: per-volume echo SNR (A_e/sigma), energy z, echo count above threshold ===')
    g = {}
    for key in ('B', 'N', 'U', 'UU', '0', '1010_B', '1010_G', '1010_I'):
        s = D[key]['s']
        vols = []
        print(f"  {key}  {s['version']}  rx={s['gains']['rx']:.0f} dw={s['dwell_us']:.0f} sigma={np.sqrt(D[key]['sigma2']):.3f}")
        for v in range(s['E']):
            st = ST(key, v)
            n5 = int(np.sum(st['snr'] > 5)); nz5 = int(np.sum(st['z'] > 5))
            rec = dict(volume=v+1, b=float(s['b'][v]), direction=D[key]['labels'][v],
                       snr_per_echo=st['snr'].tolist(), energy_z_per_echo=st['z'].tolist(),
                       n_echoes_amp_snr_gt5=n5, n_echoes_energy_z_gt5=nz5,
                       echo1_snr=float(st['snr'][0]), echo1_z=float(st['z'][0]))
            vols.append(rec)
            print(f"    v{v+1} b={rec['b']:6g}  SNR:" + ' '.join(f'{x:7.2f}' for x in st['snr']) +
                  f"  | z E1={st['z'][0]:6.2f}  max z={st['z'].max():6.2f}  #amp>5={n5}  #z>5={nz5}")
        g[key] = dict(version=s['version'], rx_gain=s['gains']['rx'], dwell_us=s['dwell_us'], sigma2=D[key]['sigma2'],
                      volumes=vols)
    # b dependence within each scan: low-b (b<=20) vs high-b (b>=1000)
    g_dep = {}
    for key in ('B', 'N', 'U', 'UU', '0', '1010_B'):
        s = D[key]['s']
        lo = [v for v in range(s['E']) if s['b'][v] <= 20]
        hi = [v for v in range(s['E']) if s['b'][v] >= 1000]
        dep = {}
        for name, grp in (('low_b<=20', lo), ('high_b>=1000', hi)):
            if grp:
                dep[name] = dict(volumes=[int(v+1) for v in grp],
                                 echo1_snr_mean=float(np.mean([ST(key, v)['snr'][0] for v in grp])),
                                 echo1_z_mean=float(np.mean([ST(key, v)['z'][0] for v in grp])),
                                 echo2to8_z_mean=float(np.mean([ST(key, v)['z'][1:].mean() for v in grp])))
        g_dep[key] = dep
        print(f"  b-dependence {key}: {json.dumps(jsonable(dep))}")
    print('  Echo-1 comparison (echo-1 SNR = A_1/sigma; z = energy significance):')
    comp = {}
    for key, v in (('B', 0), ('0', 0), ('N', 0), ('U', 0), ('UU', 0), ('1010_B', 0), ('1010_G', 0), ('1010_I', 0)):
        st = ST(key, v)
        comp[key] = dict(b=float(D[key]['s']['b'][v]), rx_gain=D[key]['s']['gains']['rx'], dwell_us=D[key]['s']['dwell_us'],
                         echo1_snr=float(st['snr'][0]), echo1_z=float(st['z'][0]), echo1_amp=float(st['amp'][0]),
                         sigma=float(np.sqrt(D[key]['sigma2'])))
        print(f"    {key:7s} b={comp[key]['b']:4g} rx={comp[key]['rx_gain']:5.0f} dw={comp[key]['dwell_us']:3.0f} "
              f"sigma={comp[key]['sigma']:8.3f}  E1 SNR={comp[key]['echo1_snr']:10.2f}  E1 z={comp[key]['echo1_z']:8.2f}")
    g['b_dependence'] = g_dep
    g['echo1_comparison'] = comp
    out['g'] = g
    print()

    # ---- CSV and JSON ----
    n_rows = write_csv(D)
    print(f'Wrote {CSV_PATH} ({n_rows} rows)')
    out['meta'] = dict(echo_time_formula='TE + (n-1)*ESP (ms, header)', noise_definition=(
        'per-scan median over volumes/slices of the median |k|^2 over the outer 32x32 k-space corner, divided by ln 2'),
        amplitude_definition='A_e = sqrt(max(sum|nav_e|^2 - nsamp*sigma^2, 0))',
        threshold_definition='A_e/sigma > 5 (amp_over_noise_rms) and energy_z > 5 both reported; noise-only A_e/sigma is typically ~3')
    JSON_PATH.write_text(json.dumps(jsonable(out), indent=1))
    print(f'Wrote {JSON_PATH}')

    # ---- figure 1: echo trains ----
    FIG.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    ax = axes[0]
    panel1 = [('A', 2, 0), ('E', 0, 0), ('G', 0, 0), ('I', 0, 0), ('Q', 0, 0), ('T', 0, 0), ('TT', 0, 0), ('V', 0, 1)]
    for key, v, sl in panel1:
        d = D[key]; st = ST(key, v, sl); amp = st['amp']
        if amp[0] <= 0:
            continue
        lab = f"{key} b{d['s']['b'][v]:g} {d['labels'][v]}" + (f" slice{sl+1}" if d['s']['S'] > 1 else '')
        ax.plot(d['t_ms'], amp/amp[0], 'o-', ms=4, lw=1.2, label=lab)
    ax.set_xlabel('echo time (ms) = TE + (n-1) ESP')
    ax.set_ylabel('A_e / A_1 (noise-subtracted navigator)')
    ax.set_title('Normalised echo trains (low-b reference)')
    ax.grid(alpha=.3)
    ax.legend(fontsize=7.5)
    ax = axes[1]
    panel2 = [('A', 2, 0), ('T', 0, 0), ('B', 0, 0), ('0', 0, 0), ('U', 0, 0), ('UU', 0, 0), ('1010_B', 0, 0)]
    styles = {'1010_B': dict(ls='--', color='k')}
    for key, v, sl in panel2:
        d = D[key]; st = ST(key, v, sl); snr = st['snr']
        m = snr > 0
        lab = f"{key} b{d['s']['b'][v]:g} rx{d['s']['gains']['rx']:.0f} ({d['s']['version']})"
        ax.semilogy(d['t_ms'][m], snr[m], marker='o', ms=4, lw=1.2, label=lab, **styles.get(key, {}))
        if not m.all():
            ax.semilogy(d['t_ms'][~m], np.full(np.sum(~m), 1e-2), 'x', color='0.5', ms=4)
    ax.axhline(5, color='0.4', lw=.8, ls=':')
    ax.set_xlabel('echo time (ms) = TE + (n-1) ESP')
    ax.set_ylabel('A_e / sigma (log)')
    ax.set_title('Amplitude / noise rms per echo (x = noise-subtracted zero)')
    ax.grid(alpha=.3, which='both')
    ax.legend(fontsize=7.5)
    fig.tight_layout()
    fig.savefig(FIG/'navigator_echo_trains.png', dpi=130)
    plt.close(fig)

    # ---- figure 2: multislice phase ----
    fig, axes = plt.subplots(1, 4, figsize=(14, 4.2), sharey=True)
    for ax, key in zip(axes, ('K', 'O', 'S', 'V')):
        s = D[key]['s']
        vals = dres[key]
        cmap = plt.get_cmap('viridis')
        for v in range(s['E']):
            xs = [vals[sl][v]['offset_mm'] for sl in range(s['S'])]
            ys = [vals[sl][v]['odd_minus_even_deg'] for sl in range(s['S'])]
            ax.plot(xs, ys, 'o', ms=6, color=cmap(v/max(s['E']-1, 1)), label=f"b{s['b'][v]:g} {D[key]['labels'][v]}")
        ax.axhspan(-5, 5, color='0.85', zorder=0)
        ax.axhline(0, color='0.5', lw=.7)
        ax.set_title(f"{key}  ({s['version']}, ESP {s['esp']:.0f}, {s['S']} slices)")
        ax.set_xlabel('slice offset (mm)')
        ax.grid(alpha=.3)
        ax.legend(fontsize=6.5)
    axes[0].set_ylabel('odd minus even echo phase (deg)\n(echoes 3,5,7 minus 2,4,6, vs echo 1)')
    fig.tight_layout()
    fig.savefig(FIG/'multislice_phase.png', dpi=130)
    plt.close(fig)
    print(f'Wrote figures to {FIG}')


if __name__ == '__main__':
    main()
