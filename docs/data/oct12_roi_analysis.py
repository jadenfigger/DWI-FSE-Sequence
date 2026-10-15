"""ROI signals, SNR, SNR efficiency and ADC for the 2026-10-12 scans (FSE v1.83 / v1.912 and the lab EPI).

Run after oct12_rois.py. Writes docs/data/oct12_roi_signals.csv (one row per scan/slice/volume/ROI) and
docs/data/oct12_roi_results.json (ADC and SNR summaries).

Conventions
* FSE images: plain centric-reordered FFT ('off'); for nav_on=2 the per-shot-corrected recon is also given
  (recon='shot'). EPI: plain FFT of the vendor-processed k-space, resampled 168 -> 128 along read.
* Noise sigma: Rayleigh background, sigma = sqrt(mean(I^2)/2) over readout-side columns (rows 4-123):
  in vivo columns 2-13 and 115-126; ex vivo 115-126 (the left columns carry a tube-edge artifact).
  EPI sigma is measured on the native 168-column magnitude (columns 2-15 and 152-165 in vivo, 152-165 ex vivo).
* ROI signal: noise-floor corrected S = sqrt(max(mean(I^2) - 2 sigma^2, 0)). SNR = S / sigma.
* Masks are translated by the integer b10 phase-correlation shift of each scan vs its reference (Q / iA).
* SNR efficiency = SNR / sqrt(time per volume [s]) / voxel volume [uL]. Time per volume: FSE (shots + 1
  navigator shot) x TR; EPI 16 shots x TR. Dummies excluded.
* ADC (two-point) = ln(S_ref / S_b) / (b - b_ref) with nominal b (FSE ref b10, EPI ref b0), and with model
  effective b when docs/data/oct12_effective_b.csv exists (FSE only).
"""
from pathlib import Path
import csv, json
import numpy as np
from oct12_load import load, load_epi, direction_label, ROOT
from oct12_rois import NOISE_COLS_IV, NOISE_COLS_EX

OUT = ROOT/'docs/data'
M = dict(np.load(OUT/'oct12_roi_masks.npz'))
EX_ROIS = ['ex_pbs', 'ex_brain']
IV_ROIS = ['iv_brain']
EX_FSE = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'M', 'O', 'Q', 'QQ', 'QQQ', 'R', 'Q1']
IV_FSE = ['iA', 'iB', 'iC', 'iD', 'iE', 'iF']


def centre_index(offsets):
    return int(np.argmin(np.abs(np.asarray(offsets)))) if len(offsets) else 0


def shift_to(ref, img):
    F = np.fft.fft2(ref/ref.max()); G = np.fft.fft2(img/img.max())
    R = F*np.conj(G); R /= np.abs(R)+1e-12
    r = np.abs(np.fft.ifft2(R)); i = np.unravel_index(r.argmax(), r.shape)
    return tuple(int(x if x < 64 else x-128) for x in i)   # (rows, cols) to move masks by (-) ... see apply


def move(mask, sh):
    return np.roll(mask, (-sh[0], -sh[1]), axis=(0, 1))


def sigma_of(I, cols):
    return float(np.sqrt(np.mean(I[4:124, cols]**2)/2))


def roi_signal(I, mask, sigma):
    m2 = float(np.mean(I[mask]**2))
    return float(np.sqrt(max(m2 - 2*sigma**2, 0.0)))


def eff_b_table():
    p = OUT/'oct12_effective_b.csv'
    if not p.exists():
        return {}
    t = {}
    for r in csv.DictReader(open(p)):
        if r['echo'] == '1' and r['source'] == 'model':      # echo 1 = k-space centre; CSV volumes are 1-based
            t[(r['scan'], int(r['volume'])-1)] = float(r['trace_s_mm2'])
    return t


def fse_rows(key, rois, noise_cols, ref_img, beff):
    s = load(key)
    S = s['S']; c = centre_index(s['offsets_mm'])
    sh = shift_to(ref_img, s['img'][0, c])
    shots = s['N']//s['L'] + (1 if s['nav'] else 0)
    tvol = shots*s['tr']/1000
    vox = 0.2734375**2*s['thickness_mm']
    recons = [('off', s['img'])] + ([('shot', s['img_shot'])] if s['nav'] == 2 else [])
    rows = []
    for recon, img in recons:
        for sl in range(S):
            for e in range(s['E']):
                I = img[e, sl]; sig = sigma_of(I, noise_cols)
                for roi in rois:
                    if sl != c:
                        continue
                    mk = move(M[roi], sh)
                    S_ = roi_signal(I, mk, sig)
                    rows.append(dict(scan=key, seq=s['version'], recon=recon, slice_mm=s['offsets_mm'][sl] if s['offsets_mm'] else 0.0,
                                     volume=e, b=float(s['b'][e]), b_eff=beff.get((key, e)), dir=direction_label(s['vec'][e]) if s['b'][e] > 10 else '0',
                                     roi=roi, signal=S_, sigma=sig, snr=S_/sig, n_px=int(mk.sum()), shift=str(sh),
                                     t_vol_s=tvol, voxel_ul=vox, snr_eff=S_/sig/np.sqrt(tvol)/vox, rx=s['gains']['rx'],
                                     tr=s['tr'], te=s['te'], etl=s['L'], nav=s['nav'], thickness=s['thickness_mm']))
    return rows


def epi_rows(key, rois, ref_img, noise_cols):
    e = load_epi(key)
    c = centre_index(e['offsets_mm'])
    sh = shift_to(ref_img, e['img'][0, c])
    tvol = e['shots']*e['tr']/1000
    vox = (35/e['read_px'])*(35/128)*e['thickness_mm']
    rows = []
    for v in range(e['E']):
        sig = float(np.sqrt(np.mean(e['mag'][v, c][4:124, noise_cols]**2)/2))
        for roi in rois:
            mk = move(M[roi], sh)
            S_ = roi_signal(e['img'][v, c], mk, sig)
            rows.append(dict(scan=key, seq='EPI', recon='vendor-kspace FFT', slice_mm=e['offsets_mm'][c], volume=v, b=float(e['b'][v]), b_eff=None,
                             dir=direction_label(e['vec'][v]) if e['b'][v] > 0 else '0', roi=roi, signal=S_, sigma=sig, snr=S_/sig,
                             n_px=int(mk.sum()), shift=str(sh), t_vol_s=tvol, voxel_ul=vox, snr_eff=S_/sig/np.sqrt(tvol)/vox, rx=None,
                             tr=e['tr'], te=e['te'], etl=8, nav=None, thickness=e['thickness_mm']))
    return rows


def adc_summary(rows):
    """Two-point ADC per scan/recon/roi/direction/shell, nominal and effective b."""
    out = {}
    by = {}
    for r in rows:
        by.setdefault((r['scan'], r['recon'], r['roi']), []).append(r)
    for (scan, recon, roi), rs in by.items():
        ref = [r for r in rs if r['dir'] == '0']
        if not ref:
            continue
        r0 = ref[0]
        d = {}
        for r in rs:
            if r['dir'] == '0' or r['signal'] <= 0 or r0['signal'] <= 0:
                continue
            adc = np.log(r0['signal']/r['signal'])/(r['b']-r0['b'])
            ent = dict(adc_nom=adc*1e3, snr=r['snr'], b=r['b'])
            if r['b_eff'] is not None and r0['b_eff'] is not None:
                ent['adc_eff'] = np.log(r0['signal']/r['signal'])/(r['b_eff']-r0['b_eff'])*1e3
            d[f"b{int(r['b'])}{r['dir']}"] = ent
        # mean diffusivity per shell from geometric mean of x,y,z signals
        for b in sorted({r['b'] for r in rs if r['dir'] != '0'}):
            xyz = [r for r in rs if r['b'] == b and r['dir'] in ('+x', '+y', '+z')]
            if len(xyz) == 3 and all(r['signal'] > 0 for r in xyz):
                g = np.exp(np.mean([np.log(r['signal']) for r in xyz]))
                d[f'MD_b{int(b)}'] = dict(adc_nom=np.log(r0['signal']/g)/(b-r0['b'])*1e3,
                                          min_snr=min(r['snr'] for r in xyz))
        out[f'{scan}|{recon}|{roi}'] = dict(b_ref=r0['b'], snr_ref=r0['snr'], **d)
    return out


def main():
    beff = eff_b_table()
    ex_ref = load('Q')['img'][0, 1]
    iv_ref = load('iA')['img'][0, 3]
    rows = []
    for k in EX_FSE:
        rows += fse_rows(k, EX_ROIS, NOISE_COLS_EX, ex_ref, beff)
    rows += epi_rows('epi0', EX_ROIS, ex_ref, np.r_[152:166])
    for k in IV_FSE:
        rows += fse_rows(k, IV_ROIS, NOISE_COLS_IV, iv_ref, beff)
    rows += epi_rows('epiA', IV_ROIS, iv_ref, np.r_[2:16, 152:166])
    with open(OUT/'oct12_roi_signals.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    res = dict(adc=adc_summary(rows), effective_b_used=bool(beff),
               shifts={r['scan']: r['shift'] for r in rows})
    (OUT/'oct12_roi_results.json').write_text(json.dumps(res, indent=1, default=float))
    print('rows', len(rows), 'effective b available:', bool(beff))


if __name__ == '__main__':
    main()
