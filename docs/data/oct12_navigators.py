"""2026-10-12 navigators, per-shot navigators, high-b ghosting and per-echo ADC (v1.83 vs v1.912; ex vivo and in vivo).

Run from the repository root:  python docs/data/oct12_navigators.py
Reads the MRDs read-only (docs/data/oct12_load.py); writes
  docs/data/oct12_navigator_echoes.csv   one row per scan/volume/slice/echo (navigator amplitude, phase, per-echo ADC)
  docs/data/oct12_ghosting.csv           one row per scan/volume/slice/recon variant (ghost metrics, per-shot phase spread for R)
  docs/data/oct12_navigators.json        structured results of all four questions
  docs/figures/physical_scanner_2026-10-12/{nav_*,ghost_*}.png

Helpers (all oct12_nav*): _common (loader fix for scan N, masks, ghost metric, echo statistics), _layout (section 1),
_shot (section 2), _ghost (section 3), _adc (section 4), _figs.

Sections: 1 why scan N reconstructs as garbage; 2 per-shot navigator correction in R; 3 high-b ghosting; 4 per-echo ADC.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from oct12_nav_common import ROOT, DATA, FIG, jsonable, centre_slice  # noqa: E402
import oct12_nav_layout as LAY  # noqa: E402
import oct12_nav_ghost as GH  # noqa: E402
import oct12_nav_shot as SH  # noqa: E402
import oct12_nav_adc as ADC  # noqa: E402
import oct12_nav_figs as F  # noqa: E402


def primary(row):
    """ex vivo b>=3000: zone outside the volume's own object (PBS is gone); otherwise outside the b10 object (tube / head)."""
    if row['sample'].startswith('ex') and row['b'] >= 3000:
        return row['ghost_excess_own'], row['ghost_excess_own_se']
    return row['ghost_excess'], row['ghost_excess_se']


def echo_trend(y, err):
    """echo-1 value, weighted mean of echoes 2..L, and weighted slope per echo (error floor 0.5 % of the value as a systematic floor)."""
    y = np.asarray(y, float); err = np.asarray(err, float); n = np.arange(1, len(y)+1)
    ok = np.isfinite(y) & np.isfinite(err)
    if ok.sum() < 4 or not ok[0]:
        return None
    e = np.maximum(err, 0.005*np.abs(y)); w = 1/e**2
    later = ok & (n >= 2)
    mean_later = float(np.sum(w[later]*y[later])/np.sum(w[later])); se_later = float(np.sqrt(1/np.sum(w[later])))
    A = np.stack([np.ones(ok.sum()), n[ok]-1], 1); W = np.diag(w[ok])
    cov = np.linalg.inv(A.T@W@A); p = cov@A.T@W@y[ok]
    return dict(echo1=float(y[0]), echo1_err=float(e[0]), mean_echoes_2_to_L=mean_later, mean_err=se_later,
                later_minus_first_pct=float(100*(mean_later/y[0]-1)), slope_per_echo=float(p[1]), slope_err=float(np.sqrt(cov[1, 1])),
                slope_pct_of_echo1_per_echo=float(100*p[1]/y[0]), n_echoes_used=int(ok.sum()))


def main():
    out = dict(meta=dict(date='2026-10-12', scripts='docs/data/oct12_navigators.py + oct12_nav_*.py',
                         note='raw data read-only; ghost zones/metric see oct12_nav_common.ghost_metrics'))
    # ------------------------------------------------------------------ 1. layout of N
    print('1. N layout ...')
    lay = LAY.run_layout()
    figs = {}
    figs['layout'] = F.fig_n_layout(lay)
    figs['n_vs_m'] = F.fig_n_vs_m(lay)
    Nf = lay['_objects']['Nf']
    acquired_rows = np.asarray(Nf['rows'], dtype=np.int16)
    missing_rows = np.setdiff1d(np.arange(Nf['N']), acquired_rows).astype(np.int16)
    recovered_meta = dict(
        scan='N', version='v1.83', description='Recovered N using contiguous 119-view volumes and sparse planned 128-row PE table.',
        raw_views_per_volume=119, raw_layout='7 volume navigator echoes + 16 shots × 7 imaging echoes',
        image_shape='4 × 128 × 128', acquired_imaging_lines=int(len(acquired_rows)), zero_filled_pe_lines=int(len(missing_rows)),
        row_mapping='pe_rows(128,8,1).reshape(16,8)[:,:7].ravel()',
        phase_fov_mm=35/(1125/1000), actual_pe_step_ratio=1125/1000,
        navigator='volume navigator only; no per-shot navigator was acquired; no motion correction applied',
        b_value_units='s/mm^2, nominal', vectors_axes='scanner logical x/y/z',
    )
    np.savez_compressed(DATA/'oct12_N_recovered.npz',
                        magnitude=np.asarray(Nf['img'][:, 0], np.float32),
                        kspace=np.asarray(Nf['kspace'][:, 0], np.complex64),
                        acquired_pe_rows=acquired_rows, zero_filled_pe_rows=missing_rows,
                        volume_navigator=np.asarray(Nf['navs'][:, 0], np.complex64),
                        b_values=np.asarray(Nf['b'], np.float32),
                        directions=np.asarray(Nf['vec'], np.float32),
                        metadata_json=np.asarray(json.dumps(recovered_meta)))
    L = {k: v for k, v in lay.items() if k != '_objects'}
    L['ppl_explanation'] = dict(
        recon_assumes='split_mode2: 153 views per volume = 9 + 16 x 9 (volume train of ETL+1, then 16 shots of 8 imaging echoes + 1 unencoded navigator echo)',
        data_contain='119 views per volume = 7 + 16 x 7, written contiguously (4 x 119 = 476 views, rest of the 4 x 153 file zero)',
        ppl_v183_line_1412='crusher_etl = views_per_seg+(nav_on==2);   (views_per_seg already reduced to 8 by the nav_on==2 block at line 586)',
        ppl_echo_loop_lines='4337-4346: if (echo_cnt < crusher_etl) goto echo_loop   (non-DRIVEN_EQUILIBRIUM branch)',
        ppl_arithmetic='PPL relational operators evaluate to -1 for TRUE (EVO PPL manual, "== EQUALS Operator"; the vendor idiom notDummy = -(disacq_cnt >= no_disacq) at line 4204 relies on it) -> crusher_etl = 8 + (-1) = 7',
        consequence='7 echoes per train: the 8th imaging echo and the per-shot navigator echo (echo 9) are never played; echo_cnt==views_per_seg (the gp_mul=0 test) is never reached; volume navigator also has 7 echoes; 17 shots x 7 = 119 views per volume. The sparse 128-row grid leaves 16 missing lines zero-filled; its line ordering equals pe_rows(112,7,1) after subtracting a common 8-row offset, but the compact 112-row FFT has a different pixel spacing and needs explicit physical rescaling.',
        v1912='uses v1912_echoes = views_per_seg; if (nav_on==2) v1912_echoes = v1912_echoes+1 (line 2591-2592) and echo_cnt < v1912_echoes (line 4206) -> 9 echoes; R matches the recon contract',
        v182='the same line 1402 exists in v1.82 (and v1.83 PPL inherits it): any v1.82/v1.83 nav_on=2 scan would behave like N',
        fix_suggestion='crusher_etl = views_per_seg; if (nav_on==2) crusher_etl = crusher_etl+1;   (and make the python event model use PPL boolean semantics)',
        pe_step='gp_inc = scale(templ1,2,no_views) at line 1620 runs after the nav_on==2 reduction (no_views 153 -> 136) while the console computed gp_init_var=-1125 for NO_VIEWS=153 (gp_init_var / NO_VIEWS = -7.353 in every 10-12 scan) -> phase-encode step 1.125x the nav_on=1 value in both N and R (PE FOV 31.1 mm instead of 35 mm; R pixel 0.243 mm vs 0.273 mm along PE; fitted row scale R/Q 0.89 vs theory 0.889). Fix: divide by the embedded NO_VIEWS (153) or scale gp_init_var by 136/153.',
        scrambling='the recon takes 9-view blocks from a 7-view stream: every shot is mis-assigned (ky rows wrong, the navigator train and shot starts walk through the data), giving a scrambled k-space and horizontal banding',
        reorder='per volume j: stream = MRD.raw[:, 0].reshape(-1,128)[119 j : 119 (j+1)]; stream[0:7] = volume navigator; stream[7:] reshaped 16 x 7 and placed at pe_rows(128,8,1).reshape(16,8)[:,:7]; zero-fill to 128 x 128 before FFT. This has the same acquisition order as pe_rows(112,7,1) up to a +8 row origin, but preserves scanner-grid coordinates. The actual PE step is 1.125x, giving a 31.1-mm phase FOV.')
    out['section1_N_layout'] = L

    # ------------------------------------------------------------------ 3. ghosting (also loads all scans)
    print('3. ghosting ...')
    rows, scans, qa_all = GH.run_ghosting()
    df = pd.DataFrame(rows)
    df['reliable'] = ((df.obj_snr >= 4) & (df.n_obj_px >= 150) & np.isfinite(df.ghost_excess)).astype(int)
    prim = df.apply(lambda r: primary(r), axis=1)
    df['ghost_primary'] = [p[0] for p in prim]; df['ghost_primary_se'] = [p[1] for p in prim]
    df.to_csv(DATA/'oct12_ghosting.csv', index=False, float_format='%.6g')
    figs['ghost_bars'] = F.fig_ghost_bars(df)
    figs['ghost_examples'] = F.fig_ghost_examples(scans)

    def tab(d):
        return [dict(scan=r.scan, version=r.version, b=r.b, direction=r.direction, ghost=(None if not r.reliable else float(r.ghost_primary)),
                     se=float(r.ghost_primary_se) if np.isfinite(r.ghost_primary_se) else None, obj_snr=float(r.obj_snr) if np.isfinite(r.obj_snr) else None,
                     reliable=bool(r.reliable)) for r in d.itertuples()]
    G = {}
    plain = df[df.recon == 'plain']
    cen = plain[plain.centre_slice == 1]
    G['definition'] = ('ghost_primary = (mean |I| in the phase-encode zone - mean |I| in the readout control zone) / mean |I| of the volume object; '
                       'PE zone = columns spanning the object, outside the dilated object (4 % of rows); RO zone = rows spanning the object, outside the dilated object. '
                       'ex vivo b>=3000: object = the volume\'s own mask (brain) so the PBS-filled tube interior counts as zone; all other cases: object = own mask U b10 mask '
                       '(outside the whole tube / head). reliable = object SNR >= 4 and >= 150 object pixels.')
    G['centre_slice'] = tab(cen[cen.b > 10])
    # version comparison ex vivo, centre slice, plain recon
    comp = []
    for (b, d), g in cen[(cen['sample'].str.startswith('ex')) & (cen.b > 10)].groupby(['b', 'direction']):
        g = g[g.reliable == 1]
        v183 = g[g.version == 'v1.83']; v1912 = g[g.version == 'v1.912']
        comp.append(dict(b=float(b), direction=d,
                         v183={r.scan: round(float(r.ghost_primary), 4) for r in v183.itertuples()},
                         v1912={r.scan: round(float(r.ghost_primary), 4) for r in v1912.itertuples()},
                         v183_mean=float(v183.ghost_primary.mean()) if len(v183) else None, v1912_mean=float(v1912.ghost_primary.mean()) if len(v1912) else None))
    G['exvivo_version_comparison_centre_plain'] = comp
    # all-slice means (reliable), plain
    sl_means = []
    for (sc, b, d), g in plain[plain.b > 10].groupby(['scan', 'b', 'direction']):
        gg = g[g.reliable == 1]
        sl_means.append(dict(scan=sc, version=g.version.iloc[0], b=float(b), direction=d, n_slices=int(len(g)), n_reliable=int(len(gg)),
                             mean_over_slices=float(gg.ghost_primary.mean()) if len(gg) else None,
                             sd_over_slices=float(gg.ghost_primary.std()) if len(gg) > 1 else None))
    G['all_slices_mean'] = sl_means
    # in vivo comparison
    iv = []
    for (b, d), g in cen[(cen['sample'].str.startswith('in')) & (cen.b > 10)].groupby(['b', 'direction']):
        iv.append(dict(b=float(b), direction=d, **{r.scan: (round(float(r.ghost_primary), 4) if r.reliable else None) for r in g.itertuples()}))
    G['invivo_by_scan_centre_plain'] = iv
    out['section3_ghosting'] = G

    # ------------------------------------------------------------------ 2. per-shot navigator (R)
    print('2. per-shot navigators ...')
    R = scans['R']
    shot_rows, shot_stats = SH.run_shot_variants(R)
    S2 = dict(variants=SH.VARIANTS and [v[0] for v in SH.VARIANTS], per_volume=shot_rows,
              per_shot_phase=[{k: (None if (isinstance(v, float) and not np.isfinite(v)) else v) for k, v in s.items()} for s in shot_stats],
              summary=SH.summarise(shot_rows, shot_stats),
              N_note='scan N has no per-shot navigator echo (7 echoes per shot, none unencoded), so no per-shot correction is possible')
    # shipped correction on the CSV rows: plain vs shot (primary metric), by b group
    sh = df[(df.scan == 'R')]
    pl = sh[sh.recon == 'plain'].set_index(['slice', 'volume']); co = sh[sh.recon == 'shot'].set_index(['slice', 'volume'])
    S2['shipped_vs_plain_primary'] = [dict(slice=int(s_), volume=int(v_), b=float(pl.loc[(s_, v_), 'b']), direction=pl.loc[(s_, v_), 'direction'],
                                           plain=float(pl.loc[(s_, v_), 'ghost_primary']), shipped=float(co.loc[(s_, v_), 'ghost_primary']),
                                           n_applied=int(co.loc[(s_, v_), 'shot_n_applied']), nav_snr_median=float(co.loc[(s_, v_), 'shot_nav_snr_median']))
                                      for (s_, v_) in pl.index]
    c3 = [r for r in shot_stats if r['slice'] == 3 and r['b'] == 1000]
    c2 = [r for r in shot_stats if r['slice'] == 2 and r['b'] == 1000]
    S2['diagnosis_plus2p8_b1000'] = dict(
        nav_snr_median_plus2p8=[r['nav_snr_median'] for r in c3], nav_snr_median_centre=[r['nav_snr_median'] for r in c2],
        lin_max_abs_deg_over_fov_plus2p8=[r['lin_max_abs_deg_over_fov'] for r in c3], lin_max_abs_deg_over_fov_centre=[r['lin_max_abs_deg_over_fov'] for r in c2],
        lin_std_deg_plus2p8=[r['lin_std_deg_over_fov'] for r in c3], lin_robust_std_deg_plus2p8=[r['lin_robust_std_deg_over_fov'] for r in c3],
        lin_robust_std_deg_centre=[r['lin_robust_std_deg_over_fov'] for r in c2],
        n_outlier_shots_plus2p8=[r['n_outlier_shots'] for r in c3], n_outlier_shots_centre=[r['n_outlier_shots'] for r in c2],
        coherence_median_plus2p8=[r['coherence_median'] for r in c3])
    S2['spread_centre_slice'] = [{k: v for k, v in s.items() if k in ('b', 'direction', 'volume', 'n_applied', 'nav_snr_median', 'const_std_deg', 'const_robust_std_deg',
                                'lin_std_deg_over_fov', 'lin_robust_std_deg_over_fov', 'lin_even_minus_odd_deg_over_fov', 'const_even_minus_odd_deg',
                                'echo_shift_std_samples', 'reference_shot')} for s in S2['per_shot_phase'] if s['slice'] == 2]
    out['section2_per_shot_navigator'] = S2
    figs['per_shot'] = F.fig_per_shot(R, shot_rows, shot_stats)

    # ------------------------------------------------------------------ 4. navigator trains and per-echo ADC
    print('4. navigator echoes / ADC ...')
    nav_rows, J = ADC.run_navigators(scans)
    ADC.write_csv(nav_rows, DATA/'oct12_navigator_echoes.csv')
    ndf = pd.DataFrame(nav_rows)
    # high-b brain-only pairs (b3000 -> b6000), centre slice
    pair = {}
    def amp_of(sc, vol):
        d = ndf[(ndf.scan == sc) & (ndf.volume == vol) & (ndf.centre_slice == 1)].sort_values('echo')
        return d.amp_noise_sub.values, d.amp_sd.values
    for sc, v1, v2, key in (('M', 3, 4, 'M'), ('O', 3, 4, 'O'), ('iA', 5, 8, 'iA_x'), ('iA', 6, 9, 'iA_y'), ('iA', 7, 10, 'iA_z'), ('iB', 5, 8, 'iB_x')):
        a1, s1 = amp_of(sc, v1); a2, s2 = amp_of(sc, v2)
        adc, err = ADC.pair_adc(a1, s1, a2, s2, 3000.0)
        pair[key] = dict(adc=adc.tolist(), err=err.tolist(), trend=echo_trend(adc, err))
    J['highb_pair'] = pair
    # per-volume trends
    summ = []
    for sc in ADC.ADC_SCANS:
        for vk, v in J['adc'][sc]['volumes'].items():
            for meas in ('adc_total', 'adc_pbs_cols', 'adc_brain_cols', 'adc_brain_2comp', 'adc_pbs_2comp', 'adc_kband'):
                if meas in v:
                    t = echo_trend(v[meas], v[meas+'_err'] if meas+'_err' in v else np.full(len(v[meas]), 0.0))
                    if t:
                        summ.append(dict(scan=sc, version=J['per_scan'][sc]['version'], volume=vk, measure=meas, **t))
    J['adc_trend_summary'] = summ
    # phase ramp / alternation (CPMG consistency) of the navigator train, b10
    ph = ndf[(ndf.echo == 1) & (ndf.b == 10)][['scan', 'version', 'slice', 'slice_offset_mm', 'centre_slice', 'phase_ramp_deg_per_echo',
                                                'phase_half_alternation_deg', 'phase_fit_rms_deg']]
    J['phase_b10'] = ph.replace({np.nan: None}).to_dict('records')
    # decay at b10 per slice
    dec = ndf[(ndf.b == 10)].pivot_table(index=['scan', 'slice', 'slice_offset_mm'], columns='echo', values='amp_norm_echo1')
    J['decay_b10_by_slice'] = {f'{i[0]}_slice{i[1]}_{i[2]:+.1f}mm': r.tolist() for i, r in dec.iterrows()}
    e2 = ndf[(ndf.echo == 2) & (ndf.centre_slice == 1)][['scan', 'version', 'volume', 'b', 'direction', 'ip_phase_deg_vs_echo1', 'amp_over_noise_rms']]
    J['echo2_phase_vs_echo1_centre_slice'] = e2[e2.amp_over_noise_rms > 5].round(2).to_dict('records')
    figs['adc'] = F.fig_adc(J)
    figs['trains_QR'] = F.fig_trains(J, 'Q', 'R', 'nav_trains_Q_vs_R.png', range(7), range(7),
                                     'Volume-navigator echo trains, ex vivo: Q (v1.83) vs R (v1.912, nav_on=2): amplitude (log) and phase vs echo number')
    figs['trains_iAiB'] = F.fig_trains(J, 'iA', 'iB', 'nav_trains_iA_vs_iB.png', range(10), range(10),
                                       'Volume-navigator echo trains, in vivo: iA (v1.83) vs iB (v1.912): amplitude (log) and phase vs echo number')
    J.pop('trains')
    out['section4_navigator_adc'] = J
    out['figures'] = figs

    # ------------------------------------------------------------------ headline numbers
    out['headline'] = headline(out, df, J)
    with open(DATA/'oct12_navigators.json', 'w') as f:
        json.dump(jsonable(out), f, indent=1)
    print('written:', DATA/'oct12_navigators.json')
    for k, v in out['headline'].items():
        print(f'  {k}: {v}')


def headline(out, df, J):
    h = {}
    f = out['section1_N_layout']['N_vs_M_final']['per_volume']
    h['N_vs_M'] = [dict(b=x['b'], corr=round(x['corr_all'], 4), nrmse_object=round(x['nrmse_object'], 3), nrmse_Q_vs_M=(None if x['nrmse_object_Q_centre_vs_M'] is None else round(x['nrmse_object_Q_centre_vs_M'], 3)),
                        noise_only=round(x['nrmse_object_noise_only_expected'], 3)) for x in f]
    return h


if __name__ == '__main__':
    main()
