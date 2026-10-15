"""Independent quantitative caveat table for the Oct 12 comparison.

Consumes the existing ROI signal table and, when the navigator fit is confirmed,
recomputes only the R centre-slice PBS/whole-brain metrics using the same Q-defined
physical masks transformed for R's narrower phase FOV. Does not rewrite baseline
signal tables or figure results.
"""
from __future__ import annotations

import ast
import csv
import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MASK_FILE = HERE / 'oct12_roi_masks.npz'
SIGNALS_FILE = HERE / 'oct12_roi_signals.csv'
EFFECTIVE_B_FILE = HERE / 'oct12_effective_b.csv'
OUT_CSV = HERE / 'oct12_quant_audit.csv'
OUT_JSON = HERE / 'oct12_quant_audit.json'

# Updated from the independent navigator image-fit when confirmed. alpha is the
# fitted R-pixel to Q-pixel scale; its reciprocal expands the Q mask onto R.
R_ROW_SCALE_TO_Q = 0.8925
R_PHASE_FOV_MM = 35.0 / 1.125
FOV_MM = 35.0
N = 128
CENTRE = (N - 1) / 2


def read_rows(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))


def by_scan(rows, scan, roi, recon='off'):
    return [r for r in rows if r['scan'] == scan and r['roi'] == roi and r['recon'] == recon]


def row_for(rows, scan, roi, volume, recon='off'):
    return next(r for r in rows if r['scan'] == scan and r['roi'] == roi
                and r['recon'] == recon and int(r['volume']) == volume)


def move(mask, shift):
    return np.roll(mask, (-shift[0], -shift[1]), axis=(0, 1))


def transform_mask(mask):
    # Each output pixel on R maps to alpha pixels in the Q reference mask;
    # this expands the ROI by 1/alpha in R coordinates.
    return ndi.affine_transform(mask.astype(np.uint8),
                                matrix=np.diag([R_ROW_SCALE_TO_Q, 1.0]),
                                offset=[CENTRE * (1 - R_ROW_SCALE_TO_Q), 0],
                                output_shape=mask.shape, order=0, mode='constant', cval=0) > 0


def sigma_of(image, cols):
    return float(np.sqrt(np.mean(image[4:124, cols] ** 2) / 2))


def roi_signal(image, mask, sigma):
    return float(np.sqrt(max(float(np.mean(image[mask] ** 2)) - 2 * sigma ** 2, 0)))


def r_geometry_rows(base_rows):
    """Re-evaluate only R's centre-slice ROI samples with physically scaled masks."""
    sys.path.insert(0, str(HERE))
    from oct12_load import load  # delayed: input-table summary can still run alone

    masks = dict(np.load(MASK_FILE))
    source = load('R')
    centre_sl = int(np.argmin(np.abs(source['offsets_mm'])))
    old = row_for(base_rows, 'R', 'ex_brain', 0)
    shift = ast.literal_eval(old['shift'])
    cols = np.arange(115, 127)
    rows = []
    for roi, base_mask in [('ex_brain', masks['ex_brain']), ('ex_pbs', masks['ex_pbs'])]:
        mk = move(transform_mask(base_mask), shift)
        for v in range(source['E']):
            image = source['img'][v, centre_sl]
            sigma = sigma_of(image, cols)
            signal = roi_signal(image, mk, sigma)
            orig = row_for(base_rows, 'R', roi, v)
            rows.append({
                'scan': 'R', 'roi': roi, 'volume': v, 'b': float(orig['b']),
                'b_eff': float(orig['b_eff']) if orig['b_eff'] else float(orig['b']),
                'dir': orig['dir'], 'signal_scaled_roi': signal,
                'signal_nominal_roi': float(orig['signal']), 'sigma': sigma,
                'snr_scaled_roi': signal / sigma, 'snr_nominal_roi': float(orig['snr']),
                'n_px_scaled_roi': int(mk.sum()), 'n_px_nominal_roi': int(orig['n_px']),
                'shift_px': shift,
            })
    return rows


def adc_entries(rows, roi, signal_key, b_key):
    rs = [r for r in rows if r['roi'] == roi]
    ref = next(r for r in rs if float(r['b']) == 10 and r['dir'] == '0')
    out = {}
    for r in rs:
        if r['dir'] not in ('+x', '+y', '+z') or float(r['b']) not in (1000, 3000):
            continue
        adc = np.log(float(ref[signal_key]) / float(r[signal_key])) / (float(r[b_key]) - float(ref[b_key])) * 1e3
        out[f"b{int(float(r['b']))}{r['dir']}"] = float(adc)
    for b in (1000, 3000):
        xyz = [r for r in rs if float(r['b']) == b and r['dir'] in ('+x', '+y', '+z')]
        if len(xyz) == 3:
            gm = np.exp(np.mean([np.log(float(r[signal_key])) for r in xyz]))
            bgeom = float(np.mean([float(r[b_key]) for r in xyz]))
            out[f'MD_b{b}'] = float(np.log(float(ref[signal_key]) / gm) / (bgeom - float(ref[b_key])) * 1e3)
    return out


def highb_adc(rows, roi, signal_key, b_key):
    rs = [r for r in rows if r['roi'] == roi]
    by_dir = {}
    for d in ('+x', '+y', '+z'):
        lo = next(r for r in rs if float(r['b']) == 1000 and r['dir'] == d)
        hi = next(r for r in rs if float(r['b']) == 3000 and r['dir'] == d)
        by_dir[d] = float(np.log(float(lo[signal_key]) / float(hi[signal_key])) /
                           (float(hi[b_key]) - float(lo[b_key])) * 1e3)
    by_dir['mean'] = float(np.mean([by_dir[d] for d in ('+x', '+y', '+z')]))
    return by_dir


def main():
    base = read_rows(SIGNALS_FILE)
    # EPI's ROI signals are measured on a 128-wide grid resampled from 168 native
    # samples. For a 35-mm FOV the output grid is 35/128 mm in both in-plane axes.
    epi = [r for r in base if r['scan'] in ('epi0', 'epiA')]
    epi_vol_old = float(epi[0]['voxel_ul'])
    epi_vol_resampled = (FOV_MM / N) ** 2 * float(epi[0]['thickness'])
    epi_eff_scale = epi_vol_old / epi_vol_resampled

    table = []
    for scan, roi in [('Q', 'ex_brain'), ('Q', 'ex_pbs'), ('R', 'ex_brain'), ('R', 'ex_pbs'),
                      ('iA', 'iv_brain'), ('iB', 'iv_brain'), ('epiA', 'iv_brain'),
                      ('epi0', 'ex_brain'), ('epi0', 'ex_pbs')]:
        candidates = by_scan(base, scan, roi, 'off' if not scan.startswith('epi') else 'vendor-kspace FFT')
        if not candidates:
            continue
        b0 = next((r for r in candidates if float(r['b']) in (0, 10) and r['dir'] == '0'), None)
        if not b0:
            continue
        old_v = float(b0['voxel_ul'])
        new_v = epi_vol_resampled if scan.startswith('epi') else old_v
        corrected_eff = float(b0['snr_eff']) * old_v / new_v
        table.append(dict(scan=scan, roi=roi, reference_b=float(b0['b']), snr=float(b0['snr']),
                          snr_eff_stored=float(b0['snr_eff']), voxel_ul_stored=old_v,
                          voxel_ul_analysis_grid=new_v, snr_eff_grid_adjusted=corrected_eff))

    result = {
        'status': 'independent audit; baseline ROI table preserved',
        'map_audit': {
            'metric': 'voxelwise directional-geometric-mean two-point ADC proxy; not a tensor MD fit',
            'signal_smoothing': 'Gaussian sigma 0.7 px before log ratios',
            'noise_floor_correction': 'none; only 1e-9 numerical floors are applied',
            'legacy_exvivo_mask': 'ex_brain union ex_pbs; pooled median is not a brain-only statistic and is dominated by PBS',
            'low_b_reference': 'FSE acquired b10 +x; EPI b0',
            'high_b_reference': 'b1000→b3000, direction-specific effective b for FSE and nominal b for EPI',
        },
        'epi_geometry': {
            'native_read_samples': 168,
            'roi_grid_read_samples': 128,
            'fov_mm_assumed': FOV_MM,
            'native_read_pixel_mm_assumed': FOV_MM / 168,
            'resampled_read_pixel_mm': FOV_MM / N,
            'phase_pixel_mm': FOV_MM / N,
            'stored_voxel_ul': epi_vol_old,
            'roi_grid_voxel_ul': epi_vol_resampled,
            'efficiency_multiplier_from_stored': epi_eff_scale,
            'caveat': 'The 168-point vendor-processed EPI read axis is linearly resampled to 128 for ROI sampling. The stored voxel volume uses 35/168 by 35/128 mm, mixing native and resampled grids. Adjusted efficiency assumes 35-mm FOV remains unchanged across interpolation; it does not correct interpolation-induced noise correlation or vendor reconstruction effects.'
        },
        'snr_efficiency_rows': table,
        'r_geometry': {
            'fit_row_scale_R_to_Q': R_ROW_SCALE_TO_Q,
            'inferred_phase_fov_mm': R_PHASE_FOV_MM,
            'fit_implied_phase_fov_mm': 35.0 * R_ROW_SCALE_TO_Q,
            'protocol_predicted_phase_fov_mm': 35.0 / 1.125,
            'navigator_fit_range_R_to_Q': [0.8768, 0.9023],
            'phase_pixel_mm': R_PHASE_FOV_MM / N,
            'read_pixel_mm': FOV_MM / N,
            'voxel_ul': (R_PHASE_FOV_MM / N) * (FOV_MM / N) * 1.0,
            'geometry_adjustment': 'Same Q physical ROI transformed onto R grid with fitted row scale; translation taken from existing registration; original rows retained.'
        },
    }
    try:
        rr = r_geometry_rows(base)
        q_metrics = {}
        for roi in ('ex_brain', 'ex_pbs'):
            q0 = row_for(base, 'Q', roi, 0)
            q_metrics[roi] = dict(
                b10_snr=float(q0['snr']),
                b10_snr_eff=float(q0['snr_eff']),
                b10_voxel_ul=float(q0['voxel_ul']),
                adc_nominal=adc_entries([dict(r, signal_scaled_roi=r['signal'], b_eff=float(r['b']))
                                         for r in by_scan(base, 'Q', roi)], roi,
                                        'signal_scaled_roi', 'b_eff'),
                adc_effective_b=adc_entries([dict(r, signal_scaled_roi=r['signal'],
                                                   b_eff=float(r['b_eff']) if r['b_eff'] else float(r['b']))
                                             for r in by_scan(base, 'Q', roi)], roi,
                                            'signal_scaled_roi', 'b_eff'),
                highb_adc_nominal=highb_adc([dict(r, signal_scaled_roi=r['signal'], b_eff=float(r['b']))
                                             for r in by_scan(base, 'Q', roi)], roi,
                                            'signal_scaled_roi', 'b_eff'),
                highb_adc_effective_b=highb_adc([dict(r, signal_scaled_roi=r['signal'],
                                                      b_eff=float(r['b_eff']) if r['b_eff'] else float(r['b']))
                                                for r in by_scan(base, 'Q', roi)], roi,
                                               'signal_scaled_roi', 'b_eff'),
            )
            q_metrics[roi]['lowb_adc_directional_mean_effective_b'] = float(np.mean([
                q_metrics[roi]['adc_effective_b'][f'b1000{d}'] for d in ('+x', '+y', '+z')]))
        for roi in ('ex_brain', 'ex_pbs'):
            rroi = [r for r in rr if r['roi'] == roi]
            r0 = next(r for r in rroi if r['volume'] == 0)
            r_vox = float(result['r_geometry']['voxel_ul'])
            for r in rroi:
                r['snr_eff_geometry'] = r['snr_scaled_roi'] / np.sqrt(float(row_for(base, 'R', roi, r['volume'])['t_vol_s'])) / r_vox
            q_metrics[roi]['R_b10_snr_nominal_roi'] = float(row_for(base, 'R', roi, 0)['snr'])
            q_metrics[roi]['R_b10_snr_geometry_roi'] = r0['snr_scaled_roi']
            q_metrics[roi]['R_b10_voxel_ul_geometry'] = r_vox
            q_metrics[roi]['R_b10_snr_eff_geometry_roi'] = r0['snr_eff_geometry']
            q_metrics[roi]['R_adc_nominal_geometry_roi'] = adc_entries(rroi, roi, 'signal_scaled_roi', 'b')
            q_metrics[roi]['R_adc_effective_geometry_roi'] = adc_entries(rroi, roi, 'signal_scaled_roi', 'b_eff')
            q_metrics[roi]['R_lowb_adc_directional_mean_effective_b'] = float(np.mean([
                q_metrics[roi]['R_adc_effective_geometry_roi'][f'b1000{d}'] for d in ('+x', '+y', '+z')]))
            q_metrics[roi]['R_highb_adc_nominal_geometry_roi'] = highb_adc(rroi, roi, 'signal_scaled_roi', 'b')
            q_metrics[roi]['R_highb_adc_effective_geometry_roi'] = highb_adc(rroi, roi, 'signal_scaled_roi', 'b_eff')
        result['r_geometry']['metrics'] = q_metrics
        result['r_geometry']['rows'] = rr
    except Exception as exc:
        result['r_geometry']['recompute_error'] = f'{type(exc).__name__}: {exc}'
    # Write current compact geometry/efficiency summary even if raw loader is unavailable.
    OUT_JSON.write_text(json.dumps(result, indent=2))
    with OUT_CSV.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['scan', 'roi', 'reference_b', 'snr', 'snr_eff_stored',
                                          'voxel_ul_stored', 'voxel_ul_analysis_grid', 'snr_eff_grid_adjusted'])
        w.writeheader(); w.writerows(table)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
