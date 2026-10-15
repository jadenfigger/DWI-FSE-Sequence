"""Section 4 of oct12_navigators.py: volume-navigator echo trains and per-echo apparent ADC.

Navigator = the unencoded echo train acquired before the imaging shots of each volume/slice (first ETL raw views; ETL-1 = 7 echoes
in N). Definitions (as oct11_navigator_analysis.py):
  A_n  = sqrt(max(sum_x |nav_n|^2 - nsamp sigma^2, 0)), sigma^2 = noise power per complex k sample (outer k-space corners, median
         over volumes/slices of the scan); sd(A_n) from  Var(energy) = nsamp sigma^4 + 2 sigma^2 S^2.
  ADC_n(b) = ln(A_n(b10)/A_n(b)) / (b - 10)   [mm^2/s, nominal b];  ADC_eff uses the model b-trace difference of the volume pair.
Four views of the same question "does the apparent diffusion change along the echo train / across k-space?":
  total      : whole navigator line (sum over the projection);
  cols       : same, restricted to readout columns (projection pixels) -- PBS-only columns (tube columns outside the brain's
               columns) and brain columns (brain + the PBS above/below it);
  2-comp     : complex least-squares of each echo's readout projection onto PBS and brain templates (column sums of the b10
               image restricted to the PBS / brain masks) -> separate PBS and brain amplitudes per echo;
  k-band     : sum of |k|^2 over the imaging lines that belong to echo n (centric: echo n fills ky band n), noise subtracted --
               a second, independent per-echo measurement that includes the outer k-space.
"""
import csv
import numpy as np
from scipy import ndimage
from oct12_nav_common import (load_scan, centre_slice, slice_offset, direction_label, outer_noise_power, echo_stats, fit_ramp_alternation,
                              object_mask, sigma_img_from_k, readout_projection, DATA, ROOT)

NAV_SCANS = ['M', 'N', 'O', 'Q', 'Q1', 'R', 'C', 'iA', 'iB', 'iC', 'iD', 'iE', 'iF']
ADC_SCANS = ['Q', 'M', 'O', 'R', 'C', 'iA', 'iB']          # requested for the per-echo ADC


def effective_dtrace():
    """{(scan, volume): [trace per echo]} from oct12_effective_b.csv (source model; echo-independent differences)."""
    out = {}
    for r in csv.DictReader(open(DATA/'oct12_effective_b.csv')):
        out.setdefault((r['scan'], int(r['volume'])), {})[int(r['echo'])] = float(r['trace_s_mm2'])
    return out


def pair_adc(a10, sd10, a, sd, db):
    """ADC (mm^2/s) from two noise-subtracted amplitudes and its 1-sigma error; NaN if either is not > 0.5 SD..."""
    ok = (a10 > 0) & (a > 0) & (a10 > 2*sd10) & (a > 2*sd)
    adc = np.where(ok, np.log(np.where(ok, a10, 1)/np.where(ok, a, 1))/db, np.nan)
    err = np.where(ok, np.sqrt((sd10/np.where(ok, a10, 1))**2+(sd/np.where(ok, a, 1))**2)/db, np.nan)
    return adc, err


def ref_volume(s):
    idx = [i for i, b in enumerate(s['b']) if abs(b-10) < 1e-6]
    return idx[0]


def column_sets(s, sl):
    """Brain / PBS-only column sets of an ex-vivo slice from the b10 image and the highest-b volume (brain only there)."""
    i10 = ref_volume(s); ih = int(np.argmax(s['b']))
    tube = object_mask(s['img'][i10, sl], sigma_img_from_k(s['kspace'][i10, sl]))
    brain = object_mask(s['img'][ih, sl], sigma_img_from_k(s['kspace'][ih, sl]), frac=0.3)
    brain &= tube
    chord = tube.sum(0); bcols = np.flatnonzero(brain.sum(0) >= 2)
    c0, c1 = bcols.min(), bcols.max()
    n = tube.shape[1]; x = np.arange(n)
    pbs_cols = np.flatnonzero((chord >= 0.5*chord.max()) & ((x < c0-3) | (x > c1+3)))
    brain_cols = np.flatnonzero((x >= c0) & (x <= c1))
    return dict(tube=tube, brain=brain, pbs_cols=pbs_cols, brain_cols=brain_cols, brain_col_range=(int(c0), int(c1)),
                highest_b_volume=ih, tube_col_range=(int(np.flatnonzero(chord > 0).min()), int(np.flatnonzero(chord > 0).max())))


def two_component_templates(s, sl, cs):
    """Complex column-sum templates from the b10 complex image: PBS = tube minus brain (eroded), brain."""
    i10 = ref_volume(s)
    cimg = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(s['kspace'][i10, sl])))
    pbs = ndimage.binary_erosion(cs['tube'] & ~ndimage.binary_dilation(cs['brain'], iterations=3), iterations=2)
    brain = ndimage.binary_erosion(cs['brain'], iterations=1)
    return (cimg*pbs).sum(0), (cimg*brain).sum(0), pbs, brain


def two_comp_fit(p, T, sigma2_x, cols):
    """p: (E, n) complex projections; T: (n, 2) templates. Returns complex coefficients (E,2) and SE (2,)."""
    A = T[cols]; G = A.conj().T@A
    coef = np.linalg.solve(G, A.conj().T@p[:, cols].T).T
    se = np.sqrt(np.real(np.diag(np.linalg.inv(G)))*sigma2_x)
    res = p[:, cols]-coef@A.T
    return coef, se, float(np.sum(np.abs(res)**2)/np.sum(np.abs(p[:, cols])**2))


def band_amplitudes(s, e, sl, sigma2):
    """Noise-subtracted k-space amplitude of the imaging lines of each echo number (centric: echo n <-> ky band n)."""
    L = s['L']; k = s['kspace'][e, sl]; rows = s['rows']
    A = np.zeros(L); SD = np.zeros(L)
    nsamp = k.shape[1]
    for n in range(L):
        lines = rows[n::L]
        en = float(np.sum(np.abs(k[lines])**2)); nn = len(lines)*nsamp
        ex = en-nn*sigma2
        A[n] = np.sqrt(max(ex, 0)); sd = np.sqrt(nn*sigma2**2+2*sigma2*max(ex, 0))
        SD[n] = sd/(2*A[n]) if A[n] > 0 else np.sqrt(sd)
    return A, SD


def run_navigators(scans=None):
    """Returns (csv_rows, json_dict). `scans` may be a dict of already loaded scans."""
    eff = effective_dtrace()
    rows = []; J = dict(per_scan={}, adc={}, trains={}, notes=[])
    for key in NAV_SCANS:
        s = scans[key] if scans and key in scans else load_scan(key)
        sigma2, est = outer_noise_power(s)
        E, S, L, nsamp = s['E'], s['S'], s['L'], s['nsamp']
        esp, te = float(s['esp']), float(s['te'])
        i10 = ref_volume(s)
        info = dict(version=s['version'], sigma2=sigma2, sigma=float(np.sqrt(sigma2)), etl_navigator_echoes=int(L), nsamp=int(nsamp),
                    rx_gain=s['gains']['rx'], volumes=[dict(volume=i+1, b=float(s['b'][i]), direction=direction_label(s['vec'][i])) for i in range(E)],
                    slices=[slice_offset(s, sl) for sl in range(S)], centre_slice=int(centre_slice(s)+1))
        st = {(e, sl): echo_stats(s['navs'][e, sl], sigma2) for e in range(E) for sl in range(S)}
        for sl in range(S):
            a10 = st[(i10, sl)]
            for e in range(E):
                x = st[(e, sl)]
                if e != i10 and abs(s['b'][e]-s['b'][i10]) > 1:
                    db = float(s['b'][e]-s['b'][i10])
                    adc, aerr = pair_adc(a10['amp'], a10['sd_amp'], x['amp'], x['sd_amp'], db)
                    ek = eff.get((key, e+1)); e0 = eff.get((key, i10+1))
                    dbe = (np.mean([ek[n+1]-e0[n+1] for n in range(min(L, len(ek)))]) if ek and e0 else np.nan)
                    adce, _ = pair_adc(a10['amp'], a10['sd_amp'], x['amp'], x['sd_amp'], dbe) if np.isfinite(dbe) else (np.full(L, np.nan), None)
                else:
                    adc = aerr = adce = np.full(L, np.nan); dbe = np.nan
                ramp, alt, rms = (np.nan, np.nan, np.nan)
                good = x['snr'] > 5
                if good[:L].sum() >= 5 and good.all():
                    ramp, alt, rms = fit_ramp_alternation(x['ip_phase'])
                for n in range(L):
                    rows.append(dict(scan=key, version=s['version'], sample='in vivo' if key.startswith('i') else 'ex vivo', volume=e+1,
                                     b=float(s['b'][e]), direction=direction_label(s['vec'][e]), slice=sl+1, slice_offset_mm=slice_offset(s, sl),
                                     centre_slice=int(sl == centre_slice(s)), echo=n+1, echo_time_ms=te+n*esp, rx_gain=s['gains']['rx'],
                                     nav_norm_raw=float(x['norm'][n]), noise_power_per_sample=sigma2, amp_noise_sub=float(x['amp'][n]),
                                     amp_sd=float(x['sd_amp'][n]), amp_over_noise_rms=float(x['snr'][n]),
                                     amp_norm_echo1=float(x['amp'][n]/x['amp'][0]) if x['amp'][0] > 0 else np.nan,
                                     ip_phase_deg_vs_echo1=float(x['ip_phase'][n]), dc_phase_deg_vs_echo1=float(x['dc_phase'][n]),
                                     peak_argmax_sample=int(x['peak'][n]),
                                     adc_nominal_mm2_s=float(adc[n]), adc_err_mm2_s=float(aerr[n]), adc_effb_mm2_s=float(adce[n]), delta_b_eff=float(dbe),
                                     phase_ramp_deg_per_echo=ramp, phase_half_alternation_deg=alt, phase_fit_rms_deg=rms))
        J['per_scan'][key] = info
        # --- ADC summaries (centre slice) -------------------------------------------------------------
        if key in ADC_SCANS:
            csl = centre_slice(s)
            res = dict(centre_slice=int(csl+1), volumes={})
            a10 = st[(i10, csl)]
            decay10 = (a10['amp']/a10['amp'][0]).tolist()
            res['decay_b10_norm_echo1'] = decay10
            res['b10_snr_per_echo'] = a10['snr'].tolist()
            res['b10_phase_ramp_alt_rms'] = list(fit_ramp_alternation(a10['ip_phase'])) if (a10['snr'] > 5).all() else None
            # k-band amplitudes
            kb10, kbsd10 = band_amplitudes(s, i10, csl, sigma2)
            ex = key in EXVIVO_ADC
            if ex:
                cs = column_sets(s, csl)
                Tp, Tb, pbs_m, brain_m = two_component_templates(s, csl, cs)
                T2 = np.stack([Tp, Tb], 1)
                tube_cols = np.flatnonzero(cs['tube'].sum(0) >= 10)
                sig_x = sigma2/nsamp                               # noise power per projection pixel (ifft has 1/N)
                P10 = readout_projection(s['navs'][i10, csl])
                coef10, se10, resid10 = two_comp_fit(P10, T2, sig_x, tube_cols)
                res['columns'] = dict(pbs_only=cs['pbs_cols'].tolist(), brain=cs['brain_cols'].tolist(), brain_col_range=cs['brain_col_range'],
                                      tube_col_range=cs['tube_col_range'], brain_mask_volume=int(cs['highest_b_volume']+1),
                                      n_pbs_px=int(pbs_m.sum()), n_brain_px=int(brain_m.sum()))
                res['two_comp_b10'] = dict(pbs_amp=np.abs(coef10[:, 0]).tolist(), brain_amp=np.abs(coef10[:, 1]).tolist(),
                                           se=se10.tolist(), residual_fraction=resid10,
                                           pbs_phase_deg=np.degrees(np.angle(coef10[:, 0]*np.conj(coef10[0, 0]))).tolist(),
                                           brain_phase_deg=np.degrees(np.angle(coef10[:, 1]*np.conj(coef10[0, 1]))).tolist(),
                                           brain_minus_pbs_phase_deg=np.degrees(np.angle(coef10[:, 1]*np.conj(coef10[:, 0]))).tolist())
            for e in range(E):
                if e == i10 or abs(s['b'][e]-s['b'][i10]) < 1:
                    continue
                x = st[(e, csl)]; db = float(s['b'][e]-s['b'][i10])
                adc, aerr = pair_adc(a10['amp'], a10['sd_amp'], x['amp'], x['sd_amp'], db)
                ek, e0 = eff.get((key, e+1)), eff.get((key, i10+1))
                dbe = float(np.mean([ek[n+1]-e0[n+1] for n in range(L)])) if ek and e0 else np.nan
                kb, kbsd = band_amplitudes(s, e, csl, sigma2)
                kadc, kerr = pair_adc(kb10, kbsd10, kb, kbsd, db)
                v = dict(b=float(s['b'][e]), direction=direction_label(s['vec'][e]), delta_b_nominal=db, delta_b_eff_model=dbe,
                         nav_snr_per_echo=x['snr'].tolist(), amp_ratio_to_b10=(x['amp']/np.where(a10['amp'] > 0, a10['amp'], np.nan)).tolist(),
                         adc_total=adc.tolist(), adc_total_err=aerr.tolist(),
                         adc_total_effb=(adc*db/dbe).tolist() if np.isfinite(dbe) else None,
                         adc_kband=kadc.tolist(), adc_kband_err=kerr.tolist(), kband_snr=(kb/np.maximum(kbsd, 1e-12)).tolist(),
                         phase_ip_deg=x['ip_phase'].tolist())
                if ex:
                    P = readout_projection(s['navs'][e, csl])
                    coef, se, resid = two_comp_fit(P, T2, sig_x, tube_cols)
                    for name, cols in (('pbs_cols', cs['pbs_cols']), ('brain_cols', cs['brain_cols'])):
                        pe_ = np.sum(np.abs(P[:, cols])**2, 1)-len(cols)*sig_x
                        p0 = np.sum(np.abs(P10[:, cols])**2, 1)-len(cols)*sig_x
                        sd_e = np.sqrt(len(cols)*sig_x**2+2*sig_x*np.maximum(pe_, 0)); sd_0 = np.sqrt(len(cols)*sig_x**2+2*sig_x*np.maximum(p0, 0))
                        A_e = np.sqrt(np.maximum(pe_, 0)); A_0 = np.sqrt(np.maximum(p0, 0))
                        a_ = adc_cols = pair_adc(A_0, np.where(A_0 > 0, sd_0/(2*np.maximum(A_0, 1e-12)), np.sqrt(sd_0)),
                                                 A_e, np.where(A_e > 0, sd_e/(2*np.maximum(A_e, 1e-12)), np.sqrt(sd_e)), db)
                        v['adc_'+name] = a_[0].tolist(); v['adc_'+name+'_err'] = a_[1].tolist()
                        v['snr_'+name] = (A_e/np.sqrt(sig_x*len(cols))).tolist()
                    amp_b, amp_p = np.abs(coef[:, 1]), np.abs(coef[:, 0])
                    for name, i_c in (('brain_2comp', 1), ('pbs_2comp', 0)):
                        A0 = np.abs(coef10[:, i_c]); A1 = np.abs(coef[:, i_c])
                        a_ = pair_adc(A0, np.full(L, se10[i_c]), A1, np.full(L, se[i_c]), db)
                        v['adc_'+name] = a_[0].tolist(); v['adc_'+name+'_err'] = a_[1].tolist()
                        v[name+'_amp'] = A1.tolist(); v[name+'_amp_se'] = float(se[i_c])
                    v['two_comp_residual_fraction'] = resid
                res['volumes'][f'v{e+1}_b{s["b"][e]:g}{direction_label(s["vec"][e])}'] = v
            J['adc'][key] = res
        # --- train summaries for figures (all slices, all volumes) ---
        J['trains'][key] = dict(amp=[[st[(e, sl)]['amp'].tolist() for sl in range(S)] for e in range(E)],
                                ip_phase=[[st[(e, sl)]['ip_phase'].tolist() for sl in range(S)] for e in range(E)],
                                snr=[[st[(e, sl)]['snr'].tolist() for sl in range(S)] for e in range(E)])
    return rows, J


EXVIVO_ADC = {'Q', 'M', 'O', 'R', 'C'}


def write_csv(rows, path):
    cols = list(rows[0])
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
