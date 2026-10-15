"""Section 1 of oct12_navigators.py: raw view layout of scan N (v1.83, nav_on=2) versus R (v1.912, nav_on=2).

Evidence collected (all from the MRD data; the PPL source is only used to explain it):
 * where the file is non-zero (N: first 476 of 612 view slots = 4 x 119) and where the unencoded navigator trains start;
 * the period of the view stream (autocorrelation of log|k|: 7 for N, 9 for R);
 * the echo-1 amplitude profile along ky and the first-7-echoes train of M reappearing in N;
 * the phase-encode step of N/R relative to the nav_on=1 scans (image registration against M / Q).
"""
import numpy as np
from scipy import ndimage, optimize
from oct12_nav_common import (load, load_scan, ns, fft_img, split_mode2, N_STORED, N_ETL, N_LINES, outer_noise_power)


def acf_lag(x, lags=range(2, 13)):
    x = np.asarray(x, float); x = x-x.mean()
    return {int(l): float(np.sum(x[:-l]*x[l:])/np.sum(x*x)) for l in lags}


def view_table(s, e=0, sl=0):
    k = s['raw'][e, sl]
    return np.abs(k).max(1), np.abs(k).argmax(1), np.sqrt((np.abs(k)**2).sum(1))


def stats(a, b):
    a = np.ravel(a); b = np.ravel(b); c = (a@b)/(b@b)
    return float(np.corrcoef(a, b)[0, 1]), float(np.sqrt(np.mean((a-c*b)**2))/np.sqrt(np.mean((c*b)**2))), float(c)


def warp_rows(a, alpha, dl, n_src_rows, n_dst_rows=128, centre_src=None, centre_dst=64):
    """Resample image `a` (rows = PE) onto an n_dst_rows grid: dst row r <- src row centre_src + (r-centre_dst-dl)/alpha."""
    if centre_src is None:
        centre_src = n_src_rows//2
    r = np.arange(n_dst_rows)
    src = centre_src+(r-centre_dst-dl)/alpha
    valid = (src >= 2) & (src <= n_src_rows-3)
    cc = np.arange(a.shape[1])
    z = ndimage.map_coordinates(a, [np.clip(src, 0, n_src_rows-1)[:, None]*np.ones((1, a.shape[1])), cc[None, :]*np.ones((n_dst_rows, 1))],
                                order=3, mode='nearest')
    return z, valid


def fit_scale(a, b, n_src_rows, centre_src=None):
    """Free fit of (alpha, row shift) mapping image a onto b (both rows = PE): minimise NRMSE."""
    def f(p):
        z, v = warp_rows(a, p[0], p[1], n_src_rows, b.shape[0], centre_src)
        return stats(z[v], b[v])[1]
    best = optimize.minimize(f, [1.0, 0.0], method='Nelder-Mead', options=dict(xatol=1e-3, fatol=1e-6))
    return float(best.x[0]), float(best.x[1]), float(best.fun)


def noise_sigma_from_ro(im, obj):
    dil = ndimage.binary_dilation(obj, iterations=6)
    r = np.flatnonzero(obj.any(1))
    z = np.zeros_like(obj); z[r.min():r.max()+1, :] = True; z &= ~dil
    return float(im[z].mean()/1.2533) if z.sum() > 30 else np.nan


def run_layout():
    out = {}
    Nraw = load('N', recon=False)
    N_scr = load('N')                       # as the shipped recon assumes (split_mode2): garbage
    Nf = load_scan('N')
    R = load('R')
    M = load('M'); Q = load('Q'); O = load('O')
    E = Nraw['E']; nsamp = Nraw['nsamp']
    flat = Nraw['raw'][:, 0].reshape(-1, nsamp)
    nrm = np.sqrt((np.abs(flat)**2).sum(1))
    nz = np.flatnonzero(nrm > 0)
    out['N_stream'] = dict(slots=int(flat.shape[0]), nonzero_views=int(len(nz)), last_nonzero=int(nz.max()), first_zero_after=int(nz.max()+1),
                           all_zero_after=bool(np.all(nrm[nz.max()+1:] == 0)), expected_if_153=int(E*153), observed_per_volume=int(len(nz)//E))
    # navigator train starts: unencoded echoes = high amplitude, peak at sample ~65, decaying; test the two candidate periods
    cand = {}
    for name, per in (('153_per_volume(split_mode2)', 153), ('119_per_volume(recovered)', N_STORED)):
        starts = [per*j for j in range(E)]
        e1 = [float(nrm[st]) for st in starts]
        cand[name] = dict(start_flat_index=starts, norm_first_view=e1,
                          argmax_sample=[int(np.abs(flat[st]).argmax()) for st in starts])
    out['N_volume_starts'] = cand
    # volume-j navigator train (7 echoes) amplitude as a fraction of M's matching volume (same b-list)
    vols = flat[:E*N_STORED].reshape(E, N_STORED, nsamp)
    out['N_nav_E1_vs_M'] = [dict(b=float(Nraw['b'][j]), N_echo1_norm=float(np.linalg.norm(vols[j, 0])),
                                 M_echo1_norm=float(np.linalg.norm(M['navs'][j, 0, 0])),
                                 ratio=float(np.linalg.norm(vols[j, 0])/np.linalg.norm(M['navs'][j, 0, 0]))) for j in range(E)]
    # period of the stream: autocorrelation of log10 norm within the imaging part of the first volume(s)
    out['acf_log_norm'] = dict(
        N_b10_stream_views_7_to_118=acf_lag(np.log10(nrm[7:N_STORED])),
        R_b10_centre_slice_views_9_to_152=acf_lag(np.log10(np.sqrt((np.abs(R['raw'][0, 1, 9:])**2).sum(1)))),
        M_b10_imaging_views_8_to_135=acf_lag(np.log10(np.sqrt((np.abs(M['raw'][0, 0, 8:])**2).sum(1)))))
    # per-echo-slot amplitude within the 7-view groups of N (b10), vs M's first 7 echoes
    g = np.sqrt((np.abs(vols[0, 7:])**2).sum(1)).reshape(16, 7)
    gm = np.sqrt((np.abs(M['raw'][0, 0, 8:])**2).sum(1)).reshape(16, 8)
    out['N_vs_M_group_median_norm_by_echo'] = dict(N=np.median(g, 0).tolist(), M_first7=np.median(gm[:, :7], 0).tolist(), M_echo8=float(np.median(gm[:, 7])))
    # echo-1 profile along ky (centric, shots 0..15): N echo-1 amplitudes vs M's (relative to the centre shot)
    e1N = np.abs(vols[0, 7:]).max(1).reshape(16, 7)[:, 0]
    e1M = np.abs(M['raw'][0, 0, 8:]).max(1).reshape(16, 8)[:, 0]
    out['echo1_profile_over_shots'] = dict(N=(e1N/e1N.max()).tolist(), M=(e1M/e1M.max()).tolist(),
                                          corr_log=float(np.corrcoef(np.log(e1N), np.log(e1M))[0, 1]), centre_shot_index=int(np.argmax(e1N)))
    # R layout check under split_mode2: per-shot navigator (9th echo) amplitude and E1 of volume train
    kR = R['raw'][0, 1]
    nrmR = np.sqrt((np.abs(kR)**2).sum(1)).reshape(17, 9)
    out['R_layout'] = dict(views=int(kR.shape[0]), nav_train_norm=nrmR[0].tolist(), shot_nav_norm_median=float(np.median(nrmR[1:, 8])),
                           shot_nav_norm_min=float(nrmR[1:, 8].min()), shot_nav_norm_max=float(nrmR[1:, 8].max()),
                           shot_echo8_norm_median=float(np.median(nrmR[1:, 7])), shot_echo1_norm_max=float(nrmR[1:, 0].max()))
    # PE-step / FOV scaling versus the nav_on=1 scans: N vs M (b10), R vs Q (b10 + b1000 x, centre slice)
    def hdr_scale(s):
        import re
        t = s['text']
        return float(re.search(r'^:PHASE_VAR\s+\w+,\s*(-?[\d.]+)', t, re.M).group(1)), float(re.search(r'^:NO_VIEWS\s+\w+,\s*(-?[\d.]+)', t, re.M).group(1))
    out['header_gp_init_var_no_views'] = {k: hdr_scale(s) for k, s in (('M', M), ('Q', Q), ('O', O), ('N', Nraw), ('R', R))}
    fits = []
    for j in range(Nf['E']):
        a, b = Nf['img'][j, 0], M['img'][j, 0]
        al, dl, nr = fit_scale(a, b, N_LINES)
        fits.append(dict(volume=j+1, b=float(Nf['b'][j]), alpha_free=al, row_shift_free=dl, nrmse_free=nr))
    out['N_vs_M_scale_fit'] = fits
    fitsR = []
    for sl in range(R['S']):
        for e in (0, 1):
            al, dl, nr = fit_scale(R['img'][e, sl], Q['img'][e, sl], 128, 64)
            fitsR.append(dict(slice=sl+1, volume=e+1, alpha_R_to_Q=al, row_shift=dl, nrmse=nr))
    out['R_vs_Q_scale_fit'] = fitsR
    # theory: gp_inc divides by the reduced no_views (136) but the console computed gp_init_var for NO_VIEWS=153
    rho = (1125/1000.)
    out['pe_step_theory'] = dict(delta_k_ratio_vs_nav1=rho, fov_phase_mm=35/rho, R_pixel_ratio_vs_Q=1/rho,
                                 N_pixel_ratio_vs_M=1/rho, N_alpha_theory=1/rho,
                                 R_alpha_theory=1/rho)
    # final N vs M comparison on the M grid (theory scale, no free parameters except the common centre)
    alpha_th = 1/rho                     # N and M both use a 128-row grid; account for the 1.125 PE step separately
    rows = []
    for j in range(Nf['E']):
        a, b = Nf['img'][j, 0], M['img'][j, 0]
        z, v = warp_rows(a, alpha_th, 0.0, N_LINES)
        r_, n_, c_ = stats(z[v], b[v])
        om = ndimage.binary_dilation(ndimage.gaussian_filter(b, 1.5) > 0.2*np.percentile(ndimage.gaussian_filter(b, 1.5), 99), iterations=1)
        vm = v[:, None] & om
        ro, no, co = stats(z[vm], b[vm])
        sM = noise_sigma_from_ro(b, om); sN = noise_sigma_from_ro(Nf['img'][j, 0], ndimage.gaussian_filter(Nf['img'][j, 0], 1.5) > 0.2*np.percentile(ndimage.gaussian_filter(Nf['img'][j, 0], 1.5), 99))
        # noise-only expectation of the object-pixel NRMSE: sqrt(sN^2 + c^2 sM^2)/(c * rms(M))
        rmsM = np.sqrt(np.mean(b[vm]**2))
        exp_noise = float(np.sqrt(sN**2+(c_*sM)**2)/(c_*rmsM)) if np.isfinite(sM) and np.isfinite(sN) else np.nan
        # benchmark: independent nav_on=1 acquisition of the same geometry (Q centre slice vs M, same b/direction) where available
        bench = np.nan
        for qj in range(Q['E']):
            if abs(Q['b'][qj]-Nf['b'][j]) < 1 and np.allclose(Q['vec'][qj], Nf['vec'][j]):
                qq = Q['img'][qj, 1]
                bench = stats(qq[vm], b[vm])[1]
        rows.append(dict(volume=j+1, b=float(Nf['b'][j]), dir=direction_label_safe(Nf['vec'][j]), corr_all=r_, nrmse_all=n_, scale_c=c_,
                         corr_object=ro, nrmse_object=no, nrmse_object_noise_only_expected=exp_noise, nrmse_object_Q_centre_vs_M=bench))
    out['N_vs_M_final'] = dict(alpha_theory=alpha_th, per_volume=rows)
    # naive recon (split_mode2) vs M
    out['N_split_mode2_vs_M'] = [dict(volume=j+1, corr=stats(N_scr['img'][j, 0], M['img'][j, 0])[0],
                                      nrmse=stats(N_scr['img'][j, 0], M['img'][j, 0])[1]) for j in range(E)]
    out['_objects'] = dict(Nraw=Nraw, N_scr=N_scr, Nf=Nf, R=R, M=M, Q=Q, O=O, alpha_th=alpha_th, flat_norm=nrm)
    return out


def direction_label_safe(v):
    from oct12_nav_common import direction_label
    return direction_label(v)
