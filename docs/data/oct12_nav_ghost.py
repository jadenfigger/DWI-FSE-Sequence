"""Sections 2-3 of oct12_navigators.py: high-b phase-encode ghosting per volume/slice, and the per-shot navigator test.

Ghost metric (see oct12_nav_common.ghost_metrics): mean |I| in a background zone along the phase-encode direction (columns
spanning the object, rows outside the dilated object) over mean |I| of the volume's own object mask; the same for a control
zone beside the object along the readout (pure noise unless something else leaks there); ghost_excess is their difference.
"""
import numpy as np
from oct12_nav_common import (load_scan, centre_slice, slice_offset, object_mask, ghost_metrics, direction_label, sigma_img_from_k,
                              recon_shot_variant, EXVIVO, INVIVO)

GHOST_SCANS = ['M', 'N', 'O', 'Q', 'Q1', 'R', 'C', 'iA', 'iB', 'iC', 'iD', 'iE', 'iF']


def sample_of(key):
    return 'in vivo (surface coil)' if key.startswith('i') else 'ex vivo (fixed brain in PBS)'


def b10_index(s):
    idx = [i for i, b in enumerate(s['b']) if abs(b-10) < 1e-6]
    return idx[0] if idx else 0


def _wrap_deg(x):
    return (np.asarray(x, float)+180.0) % 360.0-180.0


def _rstd(x):
    x = np.asarray(x, float)
    return float(1.4826*np.median(np.abs(x-np.median(x)))) if len(x) > 1 else np.nan


def shot_phase_stats(qa):
    """Per-shot phase spread from correct_shot_phase QA (the reference shot is 0 by construction and is left out).
    constant: wrapped to +-180 deg (the fit's intercept carries arbitrary 2 pi multiples); linear: deg across the 128-sample
    readout FOV (= slope x 128). 'robust' = 1.4826 x MAD (insensitive to the occasional unwrap failure at low navigator SNR).
    even-odd = mean over even-indexed minus odd-indexed shots (systematic shot-parity pattern)."""
    est = qa['Estimates']
    c = _wrap_deg(np.degrees([e['constant_rad'] for e in est])); l = np.degrees([e['linear_rad_per_voxel'] for e in est])*128
    ok = np.array([e['applied'] for e in est]); snr = np.array([e['navigator_snr'] for e in est]); coh = np.array([e['coherence'] for e in est])
    ref = qa['ReferenceShot']
    use = ok.copy(); use[ref] = False
    idx = np.arange(len(est)); ev = use & (idx % 2 == 0); od = use & (idx % 2 == 1)
    def sd(x, m):
        return float(np.std(x[m])) if m.sum() > 1 else np.nan
    return dict(n_shots=int(len(est)), n_applied=int(ok.sum()), reference_shot=int(ref),
                nav_snr_median=float(np.median(snr)), nav_snr_min=float(snr.min()), coherence_median=float(np.median(coh)),
                const_std_deg=sd(c, use), const_robust_std_deg=_rstd(c[use]) if use.sum() > 1 else np.nan,
                const_mean_deg=float(np.mean(c[use])) if use.any() else np.nan,
                lin_std_deg_over_fov=sd(l, use), lin_robust_std_deg_over_fov=_rstd(l[use]) if use.sum() > 1 else np.nan,
                lin_mean_deg_over_fov=float(np.mean(l[use])) if use.any() else np.nan,
                lin_max_abs_deg_over_fov=float(np.max(np.abs(l[use]))) if use.any() else np.nan,
                lin_even_minus_odd_deg_over_fov=float(l[ev].mean()-l[od].mean()) if ev.any() and od.any() else np.nan,
                const_even_minus_odd_deg=float(c[ev].mean()-c[od].mean()) if ev.any() and od.any() else np.nan,
                echo_shift_std_samples=sd(l, use)/360.0 if use.sum() > 1 else np.nan)


def run_ghosting():
    """Returns (rows for the CSV, per-scan loaded dicts, per-shot QA dict)."""
    rows = []; scans = {}; qa_all = {}
    for key in GHOST_SCANS:
        s = load_scan(key); scans[key] = s
        i10 = b10_index(s); csl = centre_slice(s)
        for sl in range(s['S']):
            ref = object_mask(s['img'][i10, sl], sigma_img_from_k(s['kspace'][i10, sl]))
            for e in range(s['E']):
                variants = [('plain', s['img'][e, sl], None)]
                if s['img_shot'] is not None:
                    variants.append(('shot', s['img_shot'][e, sl], None))
                for name, im, _ in variants:
                    own = object_mask(im, sigma_img_from_k(s['kspace'][e, sl]))
                    g = ghost_metrics(im, own, own | ref)            # zones outside the b10 object (tube / head) as well
                    h = ghost_metrics(im, own, own)                  # zones outside the volume's own object only
                    sig = g['ghost_ro']*g['obj_mean']/1.2533 if np.isfinite(g.get('ghost_ro', np.nan)) else np.nan
                    if not np.isfinite(sig):
                        sig = h['ghost_ro']*h['obj_mean']/1.2533 if np.isfinite(h.get('ghost_ro', np.nan)) else np.nan
                    row = dict(scan=key, version=s['version'], sample=sample_of(key), nav_requested=int(s['nav'] if key != 'N' else 2),
                               recon=name, volume=e+1, b=float(s['b'][e]), direction=direction_label(s['vec'][e]),
                               slice=sl+1, slice_offset_mm=slice_offset(s, sl), centre_slice=int(sl == csl),
                               obj_mean=g['obj_mean'], obj_snr=(g['obj_mean']/sig if sig and np.isfinite(sig) else np.nan),
                               n_obj_px=g['n_obj_px'], n_pe_px=g['n_pe_px'], n_ro_px=g['n_ro_px'],
                               ghost_pe=g['ghost_pe'], ghost_ro=g['ghost_ro'], ghost_excess=g['ghost_excess'],
                               ghost_p90_excess=g['ghost_p90_excess'], ghost_rms_excess=g['ghost_rms_excess'], ghost_excess_se=g['ghost_excess_se'],
                               n_pe_px_own=h['n_pe_px'], n_ro_px_own=h['n_ro_px'], ghost_pe_own=h['ghost_pe'], ghost_ro_own=h['ghost_ro'],
                               ghost_excess_own=h['ghost_excess'], ghost_p90_excess_own=h['ghost_p90_excess'], ghost_rms_excess_own=h['ghost_rms_excess'],
                               ghost_excess_own_se=h['ghost_excess_se'])
                    if name == 'shot':
                        qa = s['shot_qa'][e*s['S']+sl]
                        row.update({'shot_'+k: v for k, v in shot_phase_stats(qa).items()})
                        qa_all[(key, e, sl)] = qa
                    rows.append(row)
    return rows, scans, qa_all
