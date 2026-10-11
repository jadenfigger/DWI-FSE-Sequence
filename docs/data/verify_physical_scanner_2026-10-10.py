"""Independent Oct 10 acquisition/artifact verification.

Run after the analysis and attenuation scripts: python docs/data/verify_physical_scanner_2026-10-10.py
Raw data are decoded here directly from the binary format. This script deliberately does not import
the analysis, the shared MRD reader, or the shared reconstruction helpers. It re-derives dimensions,
b-values and sidecars, navigator norms, the saved NIfTI volumes (amplitude + phase navigator correction),
energy/Parseval identities, ROI-based image and k-space numbers, noise floors, pair ADC values and a
few key reported ratios from the raw complex data and compares them with the saved CSV/JSON products.
"""
from pathlib import Path
import csv
import hashlib
import json
import re
import struct

import nibabel as nib
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'docs/data'
FIG = ROOT / 'docs/figures/physical_scanner_2026-10-10'
NUMBER = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'
LETTERS = {'A': 'v181_testA', 'B': 'v1911_testB', 'C': 'v18_testC', 'D': 'v191_testD', 'E': 'v181_testE', 'G': 'v1911_testG',
           'H': 'v181_testH', 'I': 'v1911_testI', 'J': 'v181_testJ', 'K': 'v181_testK'}
EXPECTED = {'A': (7, 1), 'B': (7, 1), 'C': (7, 1), 'D': (7, 1), 'E': (8, 1), 'G': (8, 1), 'H': (3, 1), 'I': (3, 1), 'J': (3, 1), 'K': (2, 3)}
EXPECTED_B = {'A': [0, 100, 500, 1000, 2000, 3000, 6000], 'E': [0, 1000, 1000, 1000, 1000, 3000, 3000, 3000], 'H': [0, 1000, 3000], 'K': [0, 1000]}
EXPECTED_BVEC = {'E': [[0, 0, 0], [1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 0, 0], [0, 1, 0], [0, 0, 1]]}


def variable(header, name):
    match = re.search(r'^:\w+\s+' + re.escape(name) + r',\s*(' + NUMBER + ')', header, re.M)
    assert match is not None, name
    return float(match[1])


def array(header, name):
    match = re.search(r'^:VAR_ARRAY\s+' + re.escape(name) + r',\s*\d+,(.*?)(?=\r?\n:)', header, re.M | re.S)
    assert match is not None, name
    return np.array([float(v) for v in re.findall(NUMBER, match[1])])


def gain(header, field):
    return float(re.search(rf'^:_{field}\s+(-?[\d.]+)', header, re.M).group(1))


def centric_destinations(size, echoes):
    shots = size // echoes
    half_shots = shots // 2
    result = []
    for shot in range(shots):
        for echo in range(echoes):
            offset = -half_shots * echo if shot < half_shots else half_shots * echo
            result.append(size // 2 + shot - half_shots + offset)
    assert sorted(result) == list(range(size))
    return np.array(result)


def csv_rows(name):
    with (DATA / name).open(encoding='utf-8-sig') as stream:
        return list(csv.DictReader(stream))


def masks_from_geometry(edge):
    yy, xx = np.indices((128, 128))
    radius = np.hypot(xx - 61, yy - 73)
    background = (yy < 20) & ((xx < 16) | (xx >= 112))
    d = (xx - edge['col_intercept'] - edge['col_slope'] * yy) / np.hypot(1, edge['col_slope'])
    rows = (yy >= edge['rows'][0]) & (yy <= edge['rows'][1])
    return dict(interior=radius <= 34, rim=(radius >= 41) & (radius <= 47), background=background,
                edge_line=(abs(d) <= edge['half_width']) & rows, edge_ref=(d >= edge['ref_offset'][0]) & (d <= edge['ref_offset'][1]) & rows)


def verify():
    analysis = json.loads((DATA / 'physical_scanner_analysis_2026-10-10.json').read_text())
    fits = json.loads((DATA / 'oct10_attenuation_fits.json').read_text())
    npz = np.load(DATA / 'oct10_roi_masks.npz')
    masks = masks_from_geometry(analysis['roi']['edge_line'])
    for key, mask in masks.items():
        assert np.array_equal(npz[key], mask), ('ROI mask differs from independent geometry', key)
        assert int(mask.sum()) == analysis['roi']['counts'][key]
    assert not np.any(masks['interior'] & masks['background']) and not np.any(masks['interior'] & masks['edge_line']) and not np.any(masks['interior'] & masks['edge_ref'])
    image_rows = {(r['scan'], int(r['volume']), int(r['slice']), r['mode']): r for r in csv_rows('oct10_image_measurements.csv')}
    k_rows = {(r['scan'], int(r['volume']), int(r['slice']), r['mode']): r for r in csv_rows('oct10_kspace_measurements.csv')}
    nav_rows = {(r['scan'], int(r['volume']), int(r['slice']), int(r['echo'])): r for r in csv_rows('oct10_navigator_echoes.csv')}
    assert len(analysis['measurements']) == len(image_rows) == len(k_rows) == 177 and len(nav_rows) == 472
    pair_rows = csv_rows('oct10_pair_comparisons.csv')
    results = {}
    navs = {}
    for letter, tag in LETTERS.items():
        folder = next(p for p in (ROOT / 'experiments').glob('FSE-DWI_10-10-2026_*') if p.name.endswith('_' + tag))
        path = next(folder.glob('*.MRD'))
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        summary = analysis['scans'][letter]
        assert digest == summary['mrd_sha256'] == fits['mrd_sha256'][letter], (letter, 'MRD identity')
        samples, views, views2, slices = struct.unpack_from('<4i', content, 0)
        echoes, experiments = struct.unpack_from('<2i', content, 152)
        assert struct.unpack_from('<H', content, 18)[0] == 0x15, (letter, 'complex float format')
        assert (experiments, slices) == EXPECTED[letter] and (samples, views2, echoes) == (128, 1, 1), (letter, samples, views, views2, slices, echoes, experiments)
        count = samples * views * views2 * slices * echoes * experiments
        end = 512 + count * 8
        assert content[end + 120:end + 124] == b':PPL', (letter, 'exact payload boundary')
        header = content[end + 120:].decode('latin1')
        raw = np.frombuffer(content, dtype='<c8', count=count, offset=512).reshape(experiments, echoes, slices, views2, views, samples)[:, 0, :, 0]
        assert np.isfinite(raw).all() and all(np.any(raw[e, s]) for e in range(experiments) for s in range(slices))
        assert summary['dims'] == [experiments, 1, slices, 1, views, samples]
        # header: gains, protocol, b-values
        assert (gain(header, 'ObserveReceiverGain'), gain(header, 'ObserveTransmitGain')) == (30.0, -203.0) == (summary['gains']['rx'], summary['gains']['tx'])
        assert variable(header, 'no_diff_acq') == experiments
        length = int(variable(header, 'views_per_seg')); nav_on = int(variable(header, 'nav_on'))
        assert nav_on == 1 and variable(header, 'PE_order') == 1 and length == 8
        size = views - length
        assert size == 128
        b = array(header, 'acq_b')[:experiments]
        assert np.array_equal(b, summary['b_values'])
        if letter in EXPECTED_B:
            assert np.array_equal(b, EXPECTED_B[letter]), (letter, b)
        assert variable(header, 'esp') == summary['parameters']['esp'] and variable(header, 'te') == summary['parameters']['te']
        assert variable(header, 'crush_amp') == summary['parameters']['crush_amp']
        sp = re.search(r':SAMPLE_PERIOD\s+sample_period,\s*(\d+),\s*(\d+),\s*"([\d.]+) KHz\s+([\d.]+)', header)
        assert sp is not None and [float(x) for x in sp.groups()] == summary['parameters']['sample_period_params'], sp.groups() if sp else None
        assert float(sp[4]) == summary['parameters']['dwell_us'] == (25.0 if letter in ('J', 'K') else 50.0)
        # sidecars
        assert np.array_equal(np.loadtxt(next(folder.glob('*.bval'))), b)
        bvec = np.loadtxt(next(folder.glob('*.bvec'))).reshape(3, -1).T
        assert np.array_equal(bvec, summary['bvec']) and np.array_equal(bvec.any(1), b != 0)
        if letter in ('E', 'G'):
            assert np.array_equal(bvec, EXPECTED_BVEC['E'])
        sidecar = json.loads(next(folder.glob('*.json')).read_text())
        assert np.array_equal(sidecar['bval_s_per_mm2'], b) and sidecar['PEOrder'] == 1 and sidecar['SmallDelta_ms'] == 4
        assert sidecar['BigDelta_ms'] == (30 if letter == 'I' else 40) and variable(header, 'big_delta') == 1000 * sidecar['BigDelta_ms']
        assert np.allclose(sidecar['SliceOffsets_mm'], summary['parameters']['slice_offsets_mm'])
        assert hashlib.sha256(next(folder.glob('*.ppr')).read_bytes()).hexdigest()  # sidecar PPR readable
        nii = nib.load(next(folder.glob('*.nii.gz')))
        volume = nii.get_fdata()
        assert volume.shape == (128, 128, slices, experiments)
        assert np.allclose(nii.header.get_zooms()[:2], [35 / 128, 35 / 128])
        destinations = centric_destinations(size, length)
        repeated_echo = np.tile(np.arange(length), size // length)
        ky_abs = abs(destinations - size // 2)
        centres = np.array([ky_abs[repeated_echo == e].mean() for e in range(length)])
        # noise floor: median navigator-window power / ln2 over b>=3000 volumes (independent)
        noise_window = np.r_[16:48, 80:112]
        window = {}
        for e in range(experiments):
            for s in range(slices):
                nav = raw[e, s, :length].astype(np.complex128)
                window[e, s] = float(np.median(abs(nav[:, noise_window]) ** 2) / np.log(2))
        high = [window[e, s] for e in range(experiments) for s in range(slices) if b[e] >= 3000]
        output = {'mrd_sha256': digest, 'b': b.tolist(), 'volumes': []}
        navs[letter] = {}
        errors = []
        for s in range(slices):
            for e, value in enumerate(b):
                nav = raw[e, s, :length].astype(np.complex128)
                nav_norm = np.sqrt(np.sum(nav.real ** 2 + nav.imag ** 2, axis=1))
                assert np.allclose(nav_norm, summary['navigators'][s * experiments + e]['norm'], rtol=2e-7)
                navs[letter][e, s] = nav_norm
                for j in range(length):
                    assert np.isclose(float(nav_rows[letter, e + 1, s + 1, j + 1]['norm']), nav_norm[j], rtol=2e-7)
                imaging = raw[e, s, length:].astype(np.complex128)
                acquisition_power = np.sum(imaging.real ** 2 + imaging.imag ** 2)
                kspace = np.empty((size, samples), dtype=np.complex128)
                kspace[destinations] = imaging
                assert np.isclose(acquisition_power, np.sum(abs(kspace) ** 2), rtol=2e-15)
                image = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(kspace)))
                image_power = np.sum(image.real ** 2 + image.imag ** 2)
                assert np.isclose(acquisition_power / (size * samples), image_power, rtol=2e-15)
                # independent reproduction of the saved amplitude+phase navigator-corrected NIfTI volume
                nav32 = raw[e, s, :length]
                amplitudes = np.linalg.norm(nav32, axis=1)
                amplitudes /= amplitudes[0]
                dc = nav32.sum(axis=1)
                phases = np.angle(dc * dc[0].conjugate())
                step = amplitudes[repeated_echo]
                target = np.interp(ky_abs, centres, amplitudes)
                factor = (target * step / (step ** 2 + .01 ** 2) * np.exp(-1j * phases[repeated_echo])).astype(np.complex64)
                corrected = np.empty_like(kspace)
                corrected[destinations] = imaging * factor[:, None]
                expected = abs(np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(corrected)))).T
                saved = volume[:, :, s, e]
                error = np.linalg.norm(saved - expected) / np.linalg.norm(saved)
                assert error < 8e-8, (letter, s, value, 'saved NIfTI mismatch', error)
                errors.append(float(error))
                # uncorrected ('off') image row and k-space row
                pixels = abs(image)
                ir = image_rows[letter, e + 1, s + 1, 'off']
                bg_power = np.mean(pixels[masks['background']] ** 2)
                hp = np.sqrt(np.mean((pixels - gaussian_filter(pixels, 2))[masks['interior']] ** 2))
                expected_image = {'interior_mean': pixels[masks['interior']].mean(), 'interior_median': np.median(pixels[masks['interior']]),
                                  'interior_excess_rms': np.sqrt(max(np.mean(pixels[masks['interior']] ** 2) - bg_power, 0)),
                                  'background_mean': pixels[masks['background']].mean(), 'background_rms': np.sqrt(bg_power), 'background_std': pixels[masks['background']].std(),
                                  'rim_mean': pixels[masks['rim']].mean(), 'edge_line_mean': pixels[masks['edge_line']].mean(), 'edge_ref_mean': pixels[masks['edge_ref']].mean(),
                                  'edge_line_excess_rms': np.sqrt(max(np.mean(pixels[masks['edge_line']] ** 2) - bg_power, 0)),
                                  'interior_highpass_over_mean': hp / pixels[masks['interior']].mean()}
                for key, expected_value in expected_image.items():
                    assert np.isclose(float(ir[key]), expected_value, rtol=1e-9, atol=1e-14), (letter, e, s, key, ir[key], expected_value)
                p = abs(kspace) ** 2
                kr = k_rows[letter, e + 1, s + 1, 'off']
                expected_k = {'total_power': p.sum(), 'total_l2': np.sqrt(p.sum()), 'readout_edge_power_fraction': p[:, np.r_[0:12, 116:128]].sum() / p.sum(),
                              'readout_center_power_fraction': p[:, 56:73].sum() / p.sum(), 'central_ky_band_power_fraction': p[56:72].sum() / p.sum(),
                              'nav_first_norm': nav_norm[0], 'nav_last_over_first': nav_norm[-1] / nav_norm[0]}
                for key, expected_value in expected_k.items():
                    assert np.isclose(float(kr[key]), expected_value, rtol=2e-7 if key.startswith('nav') else 1e-9), (letter, e, s, key)
                coefficients = (nav @ nav[0].conjugate()) / nav_norm[0] ** 2
                residual = np.linalg.norm(nav - coefficients[:, None] * nav[0], axis=1) / nav_norm
                assert np.allclose(residual, summary['navigators'][s * experiments + e]['shape_residual'], atol=1e-6)
                peaks = np.argmax(abs(nav), axis=1)
                assert np.array_equal(peaks, summary['navigators'][s * experiments + e]['peak_sample'])
                assert np.all((peaks >= 63) & (peaks <= 66)) or value >= 3000, (letter, e, s, 'echo peak position', peaks)
                output['volumes'].append({'b': float(value), 'slice': s + 1, 'first_navigator_l2': nav_norm[0], 'imaging_l2': np.sqrt(acquisition_power), 'nifti_relative_l2_error': float(error),
                                          'interior_mean': float(pixels[masks['interior']].mean())})
        floor = float(np.median(high)) if high else None
        output['noise_floor'] = floor
        if floor is not None:
            assert np.isclose(floor, summary['noise_power_floor'], rtol=1e-6)
        output['max_nifti_error'] = max(errors)
        results[letter] = output
    assert np.isclose(results['K']['noise_floor'] if results['K']['noise_floor'] else results['J']['noise_floor'], analysis['scans']['K']['noise_power_floor'], rtol=1e-6)
    # J's floor is ~2x A's (2x bandwidth); K borrows J's
    assert 1.9 < results['J']['noise_floor'] / results['A']['noise_floor'] < 2.1
    # key reported numbers, recomputed from independent navigator norms
    first = lambda L, e, s=0: navs[L][e, s][0]
    nav_ratio = {L: first(L, 3) / first(L, 0) for L in 'ABCD'}   # volume 4 is b1000 in the seven-b scans
    assert 0.158 <= nav_ratio['A'] <= 0.1700 and 0.1150 <= nav_ratio['C'] <= 0.1165, nav_ratio
    rep = {(r['pair'], r['metric'], r['b'], r['echo'], r['numerator']): r for r in pair_rows}
    for r in pair_rows:
        if r['pair'] == 'B_vs_D' and r['metric'] == 'nav L2 per echo (absolute)':
            j, b = int(r['echo']) - 1, int(float(r['b']))
            eb = 0 if b == 0 else 3
            assert np.isclose(float(r['ratio_num_over_den']), navs['B'][eb, 0][j] / navs['D'][eb, 0][j], rtol=1e-6), r
    # independent pair ADC (nominal and table-effective) for the navigator first echo, noise-subtracted
    table = {'A': (4.00, 1000.71), 'C': (12.03, 1175.93), 'B': (20.44, 1014.68), 'D': (20.30, 1014.55)}
    fit_rows = fits['fits']
    for L in 'ABCD':
        floor = results[L]['noise_floor']
        amp = lambda e: np.sqrt(max(navs[L][e, 0][0] ** 2 - 128 * floor, 0))
        i1000 = 3
        d_nom = np.log(amp(0) / amp(i1000)) / 1000
        d_eff = np.log(amp(0) / amp(i1000)) / (table[L][1] - table[L][0])
        for basis, expected_d in (('nominal', d_nom), ('effective', d_eff)):
            row = next(r for r in fit_rows if r['day'] == 'oct10' and r['scan'] == L and r['signal'] == 'nav_E1_noise_sub' and r['basis'] == basis and r['fit'] == 'pair_b0_b1000' and r['direction'] == '+x')
            assert np.isclose(row['D_mm2_s'], expected_d, rtol=1e-4), (L, basis, row['D_mm2_s'], expected_d)
    assert next(r for r in fit_rows if r['day'] == 'oct10' and r['scan'] == 'C' and r['signal'] == 'nav_E1_noise_sub' and r['basis'] == 'nominal' and r['fit'] == 'pair_b0_b1000')['D_mm2_s'] > 1.15 * \
        next(r for r in fit_rows if r['day'] == 'oct10' and r['scan'] == 'C' and r['signal'] == 'nav_E1_noise_sub' and r['basis'] == 'effective' and r['fit'] == 'pair_b0_b1000')['D_mm2_s']
    # direction scans: volume order and +x / -x navigators
    for L in 'EG':
        assert abs(navs[L][2, 0][0] / navs[L][1, 0][0] - 1) < .12   # -x vs +x on the E1 navigator (analysis reports exact ratios)
    # 10-07 reference numbers used in the cross-day comparisons
    a7 = json.loads((DATA / 'physical_scanner_analysis_2026-10-07.json').read_text())
    for name, ref in analysis['oct07_reference'].items():
        assert np.isclose(ref['first_nav_norm'][0], a7['scans'][name]['navigators'][0]['norm'][0])
    return results, analysis


def verify_artifacts(results, analysis):
    figures = sorted(FIG.glob('*.png'))
    expected = ['contact_7b_A_C_B_D', 'contact_8vol_E_G', 'contact_3b_H_I_J', 'contact_K_slices', 'A_vs_C_seven_b', 'B_vs_D_seven_b', 'E_vs_G_directions', 'H_vs_A', 'I_vs_B', 'J_vs_A',
                'K_three_slices', 'attenuation_curves', 'navigator_echo_trains', 'edge_line_feature', 'edge_line_vs_b', 'kspace_panels', 'roi_placement']
    names = {p.stem for p in figures}
    assert set(expected) <= names, set(expected) - names
    for path in figures:
        with Image.open(path) as im:
            assert im.width > 400 and im.height > 300
            im.verify()
    for name in ('oct10_attenuation_fits.csv', 'oct10_per_echo_adc.csv', 'oct10_direction_ratios.csv', 'oct10_attenuation_curves.csv'):
        assert len(csv_rows(name)) > 10, name
    # JSON and CSV agree exactly for the image and k-space tables
    for filename, rows in [('oct10_image_measurements.csv', analysis['measurements']), ('oct10_kspace_measurements.csv', analysis['kspace']['measurements'])]:
        csv_r = csv_rows(filename)
        assert len(csv_r) == len(rows)
        for c, r in zip(csv_r, rows):
            for key, value in r.items():
                assert c[key] == value if isinstance(value, str) else float(c[key]) == value
    for relative, expected_hash in [('scanner/recon/bare_bones_recon_fse.py', analysis['reconstruction_sha256']), ('docs/data/physical_scanner_analysis_2026-10-10.py', analysis['analysis_sha256'])]:
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected_hash, relative
    print(f'PASS: 10 independent MRD decodes, {sum(len(r["volumes"]) for r in results.values())} slice-volume NIfTI reproductions (max error '
          f'{max(r["max_nifti_error"] for r in results.values()):.2e}), 177 image and 177 k-space rows, 472 navigator rows, ROI masks from independent geometry, noise floors, '
          f'navigator ratios, pair ADC values, power/Parseval checks, sidecars, {len(figures)} readable figures.')


if __name__ == '__main__':
    results, analysis = verify()
    (DATA / 'oct10_independent_verification.json').write_text(json.dumps(results, indent=2))
    verify_artifacts(results, analysis)
