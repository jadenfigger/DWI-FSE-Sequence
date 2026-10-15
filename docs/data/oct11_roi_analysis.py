"""ROI signal, SNR and ADC measurements for the 10-11 v1.82 scans (fixed rat brain in PBS).

Run: python docs/data/oct11_roi_analysis.py
Outputs: docs/data/oct11_roi_signals.csv (every image x ROI), docs/data/oct11_roi_results.json (derived quantities),
         docs/data/oct11_roi_masks.npz, docs/figures/physical_scanner_2026-10-11/roi_placement.png

ROIs are drawn automatically from the b1000/b10 ratio map, which separates free PBS (~0.14) from fixed brain (~0.6-0.8):
  brain = smoothed ratio > 0.45 inside the object, largest component, eroded 1 px (2 px at 256);
  pbs   = smoothed ratio < 0.25, b10 > 40% of its 99th percentile, eroded 4 px (8 px at 256), restricted to rows away from the
          phase-encode wrap (rows 36-92 at 128 for the zero-offset geometry) and to columns >= 12 (20-kHz left-edge clipping).
Three geometries, because the readout position depends on bandwidth (2.8-kHz frequency error, see report) and on FOV offset:
  g20  = 20-kHz, zero offset (A, C, I, T)      masks from C (b10 mean of vols 1/14, b1000 = geometric mean of 6 directions)
  g40  = 40-kHz, zero offset (AB, E, G, M, K, O, Q, S) masks from g20 shifted by +9 columns (measured registration 9.0-9.1 px)
  TT   = 20-kHz with FOV offset (own masks);  V = 256 matrix, 40 kHz, FOV offset (own masks per slice)
Signal = noise-corrected ROI value sqrt(mean(I^2) - 2 sigma^2) with sigma (per channel, image domain) from the k-space
periphery of the same image. ADC = ln(S_ref/S_b)/(b - b_ref) with nominal b; effective-b versions are added in the report
from docs/data/oct11_effective_b.csv where available.
"""
import sys, csv, json
from pathlib import Path
import numpy as np
from scipy import ndimage
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0, str(Path(__file__).parent))
from oct11_load import load, ROOT, direction_label

FIG = ROOT/'docs/figures/physical_scanner_2026-10-11'; FIG.mkdir(parents=True, exist_ok=True)
DATA = ROOT/'docs/data'
G20 = ['A', 'C', 'I', 'T']; G40 = ['AB', 'E', 'G', 'M', 'K', 'O', 'Q', 'S']; SHIFT40 = 9


def sigma_img(k):
    n, m = k.shape; r = np.r_[0:n//16, n-n//16:n]; c = np.r_[0:m//16, m-m//16:m]
    return float(np.sqrt(np.mean(abs(k[np.ix_(r, c)])**2)/2)/np.sqrt(n*m))


def make_masks(s10, s1k, wrap_rows=None, min_col=0):
    n = s10.shape[0]; f = n/128
    a = ndimage.gaussian_filter(s10, 1.5*f); b = ndimage.gaussian_filter(s1k, 1.5*f)
    obj = a > .15*np.percentile(a, 99); r = np.where(obj, b/np.maximum(a, 1e-12), 0)
    brain = obj & (r > .45)
    lab, k = ndimage.label(brain); brain = lab == (1+np.argmax(ndimage.sum(brain, lab, range(1, k+1))))
    brain = ndimage.binary_erosion(brain, iterations=int(round(f)))
    pbs = obj & (r < .25) & (a > .4*np.percentile(a, 99))
    pbs = ndimage.binary_erosion(pbs, iterations=int(round(4*f)))
    if wrap_rows is not None:
        rr = np.arange(n)[:, None]; pbs &= (rr >= wrap_rows[0]) & (rr <= wrap_rows[1])
    pbs[:, :min_col] = False
    return dict(brain=brain, pbs=pbs)


def roi_signal(im, mask, sig):
    return float(np.sqrt(max(np.mean(im[mask]**2)-2*sig**2, 0)))


def main():
    scans = {L: load(L) for L in G20+G40+['TT', 'V']}
    C = scans['C']
    s10 = (C['img'][0, 0]+C['img'][13, 0])/2; s1k = np.exp(np.mean(np.log(C['img'][7:13, 0]+1e-12), 0))
    m20 = make_masks(s10, s1k, wrap_rows=(36, 92), min_col=12)
    m40 = {k: np.roll(v, SHIFT40, axis=1) for k, v in m20.items()}
    TT = scans['TT']; mTT = make_masks(TT['img'][0, 0], TT['img'][1, 0])
    V = scans['V']; mV = [make_masks(V['img'][0, sl], np.exp(np.mean(np.log(V['img'][1:4, sl]+1e-12), 0))) for sl in range(3)]
    masks = {}
    for L in G20: masks[L] = [m20]*scans[L]['S']
    for L in G40: masks[L] = [m40]*scans[L]['S']
    masks['TT'] = [mTT]; masks['V'] = mV
    np.savez_compressed(DATA/'oct11_roi_masks.npz', **{f'{L}_sl{i+1}_{k}': v for L, ms in masks.items() for i, m in enumerate(ms) for k, v in m.items() if L in ('C', 'E', 'TT', 'V')})

    rows = []
    for L, s in scans.items():
        for e in range(s['E']):
            for sl in range(s['S']):
                im = s['img'][e, sl]; sig = sigma_img(s['kspace'][e, sl])
                for roi in ('brain', 'pbs'):
                    m = masks[L][sl][roi]
                    rows.append(dict(scan=L, version=s['version'], vol=e+1, slice=sl+1, z_mm=(s['offsets_mm'] or [0])[sl], b=float(s['b'][e]),
                                     dir=direction_label(s['vec'][e]), roi=roi, n_px=int(m.sum()), mean=float(im[m].mean()), sigma=sig,
                                     signal=roi_signal(im, m, sig), snr=roi_signal(im, m, sig)/sig, rx=s['gains']['rx'], dwell=s['dwell_us'],
                                     esp=s['esp'], te=s['te'], tr=s['tr'], Delta=s['big_delta_ms']))
    with open(DATA/'oct11_roi_signals.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

    def S(L, vol, roi, sl=1):
        return next(r['signal'] for r in rows if r['scan'] == L and r['vol'] == vol and r['slice'] == sl and r['roi'] == roi)

    def snr(L, vol, roi, sl=1):
        return next(r['snr'] for r in rows if r['scan'] == L and r['vol'] == vol and r['slice'] == sl and r['roi'] == roi)

    adc = lambda s0, s1, db: float(np.log(s0/s1)/db*1e3)   # 1e-3 mm2/s
    res = {}
    # --- C: six signed axes at b500 / b1000 with bracketing b10 references
    Cref = {roi: np.sqrt(S('C', 1, roi)*S('C', 14, roi)) for roi in ('brain', 'pbs')}
    res['C_ref_drift'] = {roi: S('C', 14, roi)/S('C', 1, roi) for roi in ('brain', 'pbs')}
    dirs = ['+x', '-x', '+y', '-y', '+z', '-z']; out = {}
    for roi in ('brain', 'pbs'):
        d = {}
        for bi, b in ((2, 500), (8, 1000)):
            for j, lab in enumerate(dirs):
                d[f'b{b}{lab}'] = dict(ratio=S('C', bi+j, roi)/Cref[roi], adc_nominal=adc(Cref[roi], S('C', bi+j, roi), b-10))
            for ax in 'xyz':
                p, m = S('C', bi+dirs.index('+'+ax), roi), S('C', bi+dirs.index('-'+ax), roi)
                d[f'b{b}_{ax}_geomean'] = dict(ratio=np.sqrt(p*m)/Cref[roi], adc_nominal=adc(Cref[roi], np.sqrt(p*m), b-10), plus_over_minus=p/m)
        d['b500_b1000_pbs_fit'] = None
        out[roi] = d
    res['C_axes'] = out
    # --- A: low-b sweep + high b
    res['A'] = {roi: {f"b{s:g}": S('A', i+1, roi)/S('A', 3, roi) for i, s in enumerate(scans['A']['b'])} for roi in ('brain', 'pbs')}
    res['A_snr'] = {roi: {f"b{s:g}": snr('A', i+1, roi) for i, s in enumerate(scans['A']['b'])} for roi in ('brain', 'pbs')}
    res['A_adc_nominal'] = {roi: dict(b10_1000=adc(S('A', 3, roi), S('A', 6, roi), 990), b0_1000=adc(S('A', 1, roi), S('A', 6, roi), 1000),
                                      b10_100=adc(S('A', 3, roi), S('A', 5, roi), 90), b1000_6000=adc(S('A', 6, roi), S('A', 7, roi), 5000))
                            for roi in ('brain', 'pbs')}
    # --- two-volume and three-volume scans
    for L in ('E', 'M', 'Q', 'T', 'TT'):
        s = scans[L]; b = list(s['b'])
        res[L] = {roi: dict(snr_b10=snr(L, 1, roi), ratio_1000=S(L, b.index(1000)+1, roi)/S(L, 1, roi), adc_10_1000=adc(S(L, 1, roi), S(L, b.index(1000)+1, roi), 990),
                            **({'ratio_6000': S(L, b.index(6000)+1, roi)/S(L, 1, roi), 'snr_b6000': snr(L, b.index(6000)+1, roi),
                                'adc_1000_6000': adc(S(L, b.index(1000)+1, roi), S(L, b.index(6000)+1, roi), 5000)} if 6000 in b else {}))
                  for roi in ('brain', 'pbs')}
    # --- AB mixed axis b1000 against E b10 (same protocol, acquired 45 s apart, same gains) and against E/M +x b1000
    res['AB'] = {roi: dict(ratio_vs_E_b10=S('AB', 1, roi)/S('E', 1, roi), adc_nominal=adc(S('E', 1, roi), S('AB', 1, roi), 990),
                           vs_E_x_b1000=S('AB', 1, roi)/S('E', 2, roi), vs_M_x_b1000=S('AB', 1, roi)/S('M', 2, roi)) for roi in ('brain', 'pbs')}
    # --- single-volume b10 timing scans: SNR
    res['b10_snr'] = {L: {roi: snr(L, list(scans[L]['b']).index(10)+1, roi, sl=(2 if scans[L]['S'] == 3 else 1)) for roi in ('brain', 'pbs')}
                      for L in ('A', 'C', 'E', 'G', 'I', 'M', 'K', 'O', 'Q', 'S', 'T', 'TT')}
    res['b10_signal_raw'] = {L: {roi: S(L, list(scans[L]['b']).index(10)+1, roi, sl=(2 if scans[L]['S'] == 3 else 1)) for roi in ('brain', 'pbs')}
                             for L in ('A', 'C', 'E', 'G', 'I', 'M', 'K', 'O', 'Q', 'S', 'T', 'TT')}
    res['sigma'] = {L: sigma_img(scans[L]['kspace'][0, 0]) for L in scans}
    # --- multi-slice: centre-slice and outer-slice b10 signal relative to single-slice M (same 40 kHz ESP11 protocol)
    res['multislice'] = {}
    for L in ('K', 'S', 'O'):
        s = scans[L]; v = list(s['b']).index(10)+1
        res['multislice'][L] = {f"sl{sl+1}_z{s['offsets_mm'][sl]:+g}": {roi: S(L, v, roi, sl+1)/S('M', 1, roi) for roi in ('brain', 'pbs')} for sl in range(3)}
    # --- V: per slice, per direction, per shell
    res['V'] = {}
    for sl in range(3):
        d = {}
        for e in range(1, 10):
            b = V['b'][e]; lab = direction_label(V['vec'][e])
            d[f'b{b:g}{lab}'] = {roi: dict(ratio=S('V', e+1, roi, sl+1)/S('V', 1, roi, sl+1), snr=snr('V', e+1, roi, sl+1),
                                           adc_from_b10=adc(S('V', 1, roi, sl+1), S('V', e+1, roi, sl+1), b-10)) for roi in ('brain', 'pbs')}
        d['snr_b10'] = {roi: snr('V', 1, roi, sl+1) for roi in ('brain', 'pbs')}
        res['V'][f'sl{sl+1}'] = d
    # --- drift: T vs A (b1000/b10), TT vs T
    res['drift'] = {roi: dict(A_ratio=S('A', 6, roi)/S('A', 3, roi), T_ratio=S('T', 2, roi)/S('T', 1, roi), TT_ratio=S('TT', 2, roi)/S('TT', 1, roi),
                              C_b10_end_over_start=S('C', 14, roi)/S('C', 1, roi), E_vs_M_b10=S('M', 1, roi)/S('E', 1, roi), E_vs_M_b1000=S('M', 2, roi)/S('E', 2, roi))
                    for roi in ('brain', 'pbs')}
    with open(DATA/'oct11_roi_results.json', 'w') as f:
        json.dump(res, f, indent=1, default=float)

    # --- ROI figure
    fig, axs = plt.subplots(1, 6, figsize=(21, 4))
    show = [('C b10 (20 kHz)', s10, m20), ('E b10 (40 kHz)', scans['E']['img'][0, 0], m40), ('TT b10 (offset FOV)', TT['img'][0, 0], mTT)] + \
           [(f'V b10 sl{sl+1}', V['img'][0, sl], mV[sl]) for sl in range(3)]
    for ax, (t, im, m) in zip(axs, show):
        ax.imshow(im, cmap='gray', vmax=np.percentile(im, 99.5))
        ax.contour(m['brain'], [.5], colors='orange', linewidths=1); ax.contour(m['pbs'], [.5], colors='cyan', linewidths=1)
        ax.set_title(f"{t}\nbrain {m['brain'].sum()} px (orange), PBS {m['pbs'].sum()} px (cyan)", fontsize=9); ax.axis('off')
    fig.tight_layout(); fig.savefig(FIG/'roi_placement.png', dpi=100); plt.close(fig)
    print(json.dumps(res, indent=1, default=lambda x: round(float(x), 4)))


if __name__ == '__main__':
    main()
