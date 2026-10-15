"""Section 2 of oct12_navigators.py: does the per-shot navigator correction (nav_on=2, scan R) help or hurt?

The shipped correction (shot_navigator.correct_shot_phase, mode 'constant+linear') is compared with variants that change one
thing at a time, using the ghost metric of oct12_nav_common.ghost_metrics (primary = outside the b10 object for b <= 1000 and
outside the volume's own object for b >= 3000, the ex-vivo rule used in oct12_navigators.py):
  plain                : no correction
  const+lin (shipped)  : navigator SNR >= 3, coherence >= 0.65
  const                : intercept only
  const+lin, SNR >= 8  : stricter navigator-SNR gate
  const, SNR >= 8
Also: per-shot phase spread, parity (even-odd shot) pattern, unwrap-failure count.
"""
import numpy as np
from oct12_nav_common import (object_mask, ghost_metrics, sigma_img_from_k, recon_shot_variant, direction_label, slice_offset)
from oct12_nav_ghost import shot_phase_stats

VARIANTS = [('plain', None, {}),
            ('const+lin (shipped)', 'constant+linear', {}),
            ('const', 'constant', {}),
            ('const+lin, SNR>=8', 'constant+linear', dict(min_snr=8.)),
            ('const, SNR>=8', 'constant', dict(min_snr=8.))]


def primary(g_ref, g_own, b):
    return g_own['ghost_excess'] if b >= 3000 else g_ref['ghost_excess']


def run_shot_variants(R):
    out = []; stats = []
    for sl in range(R['S']):
        ref = object_mask(R['img'][0, sl], sigma_img_from_k(R['kspace'][0, sl]))
        for e in range(R['E']):
            row = dict(slice=sl+1, slice_offset_mm=slice_offset(R, sl), volume=e+1, b=float(R['b'][e]), direction=direction_label(R['vec'][e]))
            qa_default = None
            for name, mode, kw in VARIANTS:
                if mode is None:
                    im = R['img'][e, sl]
                else:
                    im, qa = recon_shot_variant(R, e, sl, mode, **kw)
                    if name.startswith('const+lin (shipped)'):
                        qa_default = qa
                own = object_mask(im, sigma_img_from_k(R['kspace'][e, sl]))
                g, h = ghost_metrics(im, own, own | ref), ghost_metrics(im, own, own)
                row[name] = primary(g, h, R['b'][e])
            out.append(row)
            st = shot_phase_stats(qa_default)
            est = qa_default['Estimates']
            lin = np.degrees([x['linear_rad_per_voxel'] for x in est])*128
            c = (np.degrees([x['constant_rad'] for x in est])+180) % 360-180
            ok = np.array([x['applied'] for x in est])
            st.update(slice=sl+1, volume=e+1, b=float(R['b'][e]), direction=direction_label(R['vec'][e]),
                      n_outlier_shots=int(np.sum(ok & ((np.abs(lin) > 100) | (np.abs(c) > 40)))))
            stats.append(st)
    return out, stats


def summarise(variant_rows, stats):
    """Aggregates: mean change of the primary ghost metric (variant - plain) by b group and slice class."""
    names = [v[0] for v in VARIANTS]
    S = {}
    for cls, sel in (('centre', lambda r: r['slice'] == 2), ('off_centre', lambda r: r['slice'] != 2)):
        for grp, gsel in (('b10', lambda r: r['b'] == 10), ('b1000', lambda r: r['b'] == 1000), ('b3000', lambda r: r['b'] == 3000)):
            rows = [r for r in variant_rows if sel(r) and gsel(r)]
            S[f'{cls}_{grp}'] = dict(n=len(rows), plain_mean=float(np.mean([r['plain'] for r in rows])),
                                     **{n: dict(mean=float(np.mean([r[n] for r in rows])), mean_change_vs_plain=float(np.mean([r[n]-r['plain'] for r in rows])),
                                                n_better=int(np.sum([r[n] < r['plain']-0.002 for r in rows])), n_worse=int(np.sum([r[n] > r['plain']+0.002 for r in rows])))
                                        for n in names[1:]})
    return S
