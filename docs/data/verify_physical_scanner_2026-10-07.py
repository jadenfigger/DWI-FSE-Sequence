"""Independent Oct 7 acquisition/artifact verification.

Run after the analysis: python docs/data/verify_physical_scanner_2026-10-07.py
Raw data are decoded here directly from the binary format. This script deliberately
does not import the analysis, shared MRD reader, or shared reconstruction helpers.
Its independent energy, complex-line and export checks can expose data ordering,
volume labeling and numerical errors that image inspection alone cannot identify.
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
from scipy.optimize import minimize_scalar

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'docs/data'
NUMBER = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'


def variable(header, name):
    match = re.search(r'^:\w+\s+' + re.escape(name) + r',\s*(' + NUMBER + ')', header, re.M)
    assert match is not None, name
    return float(match[1])


def array(header, name):
    match = re.search(r'^:VAR_ARRAY\s+' + re.escape(name) + r',\s*\d+,(.*?)(?=\r?\n:)', header, re.M | re.S)
    assert match is not None, name
    return np.array([float(v) for v in re.findall(NUMBER, match[1])])


def centric_destinations(size, echoes):
    # Enumerate each shot rather than reuse the analysis's vectorized mapper.
    shots = size // echoes
    half_shots = shots // 2
    result = []
    for shot in range(shots):
        for echo in range(echoes):
            offset = -half_shots * echo if shot < half_shots else half_shots * echo
            result.append(size // 2 + shot - half_shots + offset)
    assert sorted(result) == list(range(size))
    return np.array(result)


def verify_acquisitions():
    audit = json.loads((DATA / 'oct07_protocol_audit.json').read_text())
    attenuation = json.loads((DATA / 'oct07_attenuation_fits.json').read_text())
    fits = {r['scan']: r for r in attenuation['scans']}
    analysis_path = DATA / 'physical_scanner_analysis_2026-10-07.json'
    analysis = json.loads(analysis_path.read_text()) if analysis_path.exists() else None
    masks = np.load(DATA/'oct07_roi_masks.npz') if analysis is not None else None
    if masks is not None:
        assert all(masks[key].shape == (128,128) and int(masks[key].sum()) == analysis['roi']['counts'][key] for key in masks)
        assert not np.any(masks['interior'] & masks['background'])
        assert not np.any(masks['interior'] & masks['rim'])
    image_rows = {(r['scan'], r['b'], r['mode']): r for r in analysis['measurements']} if analysis else {}
    k_rows = {(r['scan'], r['b'], r['mode']): r for r in analysis['kspace']['measurements']} if analysis else {}
    assert len(audit['scans']) == len(fits) == 10
    results = {}
    for row in audit['scans']:
        name = row['scan']
        path = ROOT / row['mrd']
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        assert digest == row['mrd_sha256'] == fits[name]['mrd_sha256'], (name, 'MRD identity')
        assert hashlib.sha256((ROOT / row['sidecar_ppr']).read_bytes()).hexdigest() == row['sidecar_ppr_sha256']
        samples, views, views2, slices = struct.unpack_from('<4i', content, 0)
        echoes, experiments = struct.unpack_from('<2i', content, 152)
        assert struct.unpack_from('<H', content, 18)[0] == 0x15, (name, 'complex float format')
        assert (samples, views2, slices, echoes) == (128, 1, 1, 1)
        count = samples * views * experiments
        end = 512 + count * 8
        assert content[end + 120:end + 124] == b':PPL', (name, 'exact payload boundary')
        header = content[end + 120:].decode('latin1')
        raw = np.frombuffer(content, dtype='<c8', count=count, offset=512).reshape(experiments, views, samples)
        assert np.isfinite(raw).all()
        assert all(np.any(v) for v in raw), (name, 'nonempty volumes')
        assert variable(header, 'no_diff_acq') == experiments
        length = int(variable(header, 'views_per_seg'))
        nav_on = int(variable(header, 'nav_on'))
        assert nav_on == 1 and variable(header, 'PE_order') == 1
        size = views - length
        assert size == 128 and length in (8, 16)
        b = array(header, 'acq_b')[:experiments]
        assert np.array_equal(b, row['b_values']) and np.array_equal(b, fits[name]['b'])
        folder = path.parent
        assert np.array_equal(np.loadtxt(next(folder.glob('*.bval'))), b)
        bvec = np.loadtxt(next(folder.glob('*.bvec')))
        assert np.array_equal(bvec[0], (b != 0).astype(float)) and np.all(bvec[1:] == 0)
        sidecar = json.loads(next(folder.glob('*.json')).read_text())
        assert np.array_equal(sidecar['bval_s_per_mm2'], b)
        assert sidecar['PEOrder'] == 1 and sidecar['SmallDelta_ms'] == 4 and sidecar['BigDelta_ms'] == 40
        nii = nib.load(next(folder.glob('*.nii.gz')))
        volume = nii.get_fdata()
        assert volume.shape == (128, 128, 1, experiments)
        assert np.allclose(nii.header.get_zooms()[:3], [35/128, 35/128, 1.2])
        destinations = centric_destinations(size, length)
        repeated_echo = np.tile(np.arange(length), size // length)
        ky_abs = abs(destinations - size // 2)
        centres = np.array([ky_abs[repeated_echo == e].mean() for e in range(length)])
        output = {'mrd_sha256': digest, 'b': b.tolist(), 'etl': length, 'volumes': []}
        for index, value in enumerate(b):
            # Float64 accumulation independently verifies the recorded float32 norms.
            nav = raw[index, :length].astype(np.complex128)
            nav_norm = np.sqrt(np.sum(nav.real**2 + nav.imag**2, axis=1))
            assert np.isclose(nav_norm[0], fits[name]['first_navigator_norm'][index], rtol=2e-7)
            if analysis is not None:
                summary = analysis['scans'][name]
                assert summary['mrd_sha256'] == digest
                assert summary['dims'] == [experiments, 1, 1, 1, views, samples]
                assert summary['L'] == length and summary['N'] == size
                assert np.allclose(nav_norm, summary['navigators'][index]['norm'], rtol=2e-7)
            imaging = raw[index, length:].astype(np.complex128)
            acquisition_power = np.sum(imaging.real**2 + imaging.imag**2)
            kspace = np.empty((size, samples), dtype=np.complex128)
            kspace[destinations] = imaging
            reordered_power = np.sum(kspace.real**2 + kspace.imag**2)
            assert np.isclose(acquisition_power, reordered_power, rtol=2e-15)
            image = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(kspace)))
            image_power = np.sum(image.real**2 + image.imag**2)
            assert np.isclose(acquisition_power / (size*samples), image_power, rtol=2e-15)
            # Independently reproduce saved amplitude+phase navigator correction.
            # Its float32 intermediate arithmetic is part of the saved pipeline.
            nav32 = raw[index, :length]
            amplitudes = np.linalg.norm(nav32, axis=1)
            amplitudes /= amplitudes[0]
            dc = nav32.sum(axis=1)
            phases = np.angle(dc * dc[0].conjugate())
            step = amplitudes[repeated_echo]
            target = np.interp(ky_abs, centres, amplitudes)
            factor = (target*step/(step**2+.01**2) * np.exp(-1j*phases[repeated_echo])).astype(np.complex64)
            corrected = np.empty_like(kspace)
            corrected[destinations] = imaging * factor[:, None]
            expected = abs(np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(corrected)))).T
            saved = volume[:, :, 0, index]
            error = np.linalg.norm(saved-expected)/np.linalg.norm(saved)
            assert error < 8e-8, (name, value, 'saved NIfTI mismatch', error)
            if analysis is not None:
                amp_factor = (target*step/(step**2+.01**2)).astype(np.complex64)
                for mode, weights in [('off', np.ones(size)), ('deramp_mag', amp_factor), ('deramp', factor)]:
                    candidate = np.empty_like(kspace)
                    candidate[destinations] = imaging * weights[:,None]
                    power = abs(candidate)**2
                    total = power.sum()
                    kr = k_rows[name,value,mode]
                    expected_power = {'total_power': total, 'total_l2': np.sqrt(total),
                                      'readout_edge_power_fraction': power[:,np.r_[0:12,116:128]].sum()/total,
                                      'readout_center_power_fraction': power[:,56:73].sum()/total,
                                      'central_ky_band_power_fraction': power[56:72].sum()/total,
                                      'all_ky_edge_sample_l2': np.sqrt(power[:,np.r_[0:12,116:128]].sum()),
                                      'all_ky_center_sample_l2': np.sqrt(power[:,56:73].sum())}
                    for key, expected_value in expected_power.items():
                        assert np.isclose(kr[key], expected_value, rtol=2e-12 if mode == 'off' else 5e-7), (name,value,mode,key)
                    pixels = abs(np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(candidate))))
                    ir = image_rows[name,value,mode]
                    interior = pixels[masks['interior']]
                    background = pixels[masks['background']]
                    rim = pixels[masks['rim']]
                    hp = np.sqrt(np.mean((pixels-gaussian_filter(pixels,2))[masks['interior']]**2))
                    expected_image = {'interior_mean': interior.mean(), 'interior_median': np.median(interior),
                                      'interior_rms': np.sqrt(np.mean(interior**2)),
                                      'background_mean': background.mean(), 'background_rms': np.sqrt(np.mean(background**2)),
                                      'rim_mean': rim.mean(), 'rim_p95': np.percentile(rim,95),
                                      'interior_highpass_rms': hp, 'interior_highpass_over_mean': hp/interior.mean()}
                    for key, expected_value in expected_image.items():
                        assert np.isclose(ir[key], expected_value, rtol=2e-12 if mode == 'off' else 5e-7), (name,value,mode,key)
            coefficients = (nav @ nav[0].conjugate()) / nav_norm[0]**2
            residual = np.linalg.norm(nav - coefficients[:, None] * nav[0], axis=1)/nav_norm
            if analysis is not None:
                assert np.allclose(residual, summary['navigators'][index]['shape_residual'], atol=1e-6), (name, value, 'complex shape residual')
            output['volumes'].append({'b': value, 'first_navigator_l2': nav_norm[0],
                                      'imaging_l2': np.sqrt(acquisition_power),
                                      'readout_edge_power_fraction': (abs(kspace[:, np.r_[0:12,116:128]])**2).sum()/acquisition_power,
                                      'parseval_relative_error': abs(image_power*(size*samples)/acquisition_power-1),
                                      'nifti_relative_l2_error': error,
                                      'navigator_last_echo_complex_shape_residual': residual[-1]})
        results[name] = output
    # Repeated v192 high-b coherent data are far larger than prepared/legacy data.
    for left, right in [('test2','test3'), ('test2b','test3b'), ('test2c','test3c')]:
        a = next(v for v in results[left]['volumes'] if v['b'] == 6000)
        z = next(v for v in results[right]['volumes'] if v['b'] == 6000)
        assert z['first_navigator_l2'] > 40*a['first_navigator_l2']
    for source in audit['available_current_sources']:
        assert hashlib.sha256((ROOT/source['path']).read_bytes()).hexdigest() == source['sha256']
    return results, analysis


def verify_artifacts(results, analysis):
    if analysis is None:
        print('Analysis JSON not yet available; acquisition/export checks completed.')
        return
    with (DATA/'oct07_scan_comparison.csv').open(encoding='utf-8-sig') as stream:
        comparison = list(csv.DictReader(stream))
    assert len(comparison) == 10 and {r['scan'] for r in comparison} == set(results)
    for row in comparison:
        name = row['scan']
        assert row['mrd_sha256'] == results[name]['mrd_sha256']
        assert int(row['etl']) == results[name]['etl']
        assert int(row['imaging_views']) == 128
        assert np.array_equal(json.loads(row['b_values']), results[name]['b'])
    for relative, expected in analysis.get('source_sha256', {}).items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() == expected, relative
    assert hashlib.sha256((ROOT/'scanner/recon/bare_bones_recon_fse.py').read_bytes()).hexdigest() == analysis['reconstruction_sha256']
    assert hashlib.sha256((DATA/'physical_scanner_analysis_2026-10-07.py').read_bytes()).hexdigest() == analysis['analysis_sha256']
    assert len(analysis['measurements']) == len(analysis['kspace']['measurements']) == 138
    for filename, rows in [('oct07_image_measurements.csv', analysis['measurements']), ('oct07_kspace_measurements.csv', analysis['kspace']['measurements'])]:
        with (DATA/filename).open(encoding='utf-8-sig') as stream:
            csv_rows = list(csv.DictReader(stream))
        assert len(csv_rows) == len(rows)
        for csv_row, row in zip(csv_rows, rows):
            for key, value in row.items():
                assert csv_row[key] == value if isinstance(value,str) else float(csv_row[key]) == value
    documents = [ROOT/'experiments/scan_catalog_2026-10-07.md', ROOT/'docs/physical_scanner_experiments_2026-10-07.md']
    for path in documents:
        assert path.exists(), path
        for link in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
            if link.startswith(('https:', 'http:', '#')):
                continue
            assert (path.parent/link.split('#')[0]).exists(), (path.name, link)
    # Verify displayed tables at their actual printed precision, including the
    # important distinction between normalized high-b ratio and absolute norm.
    report = documents[1].read_text(encoding='utf-8')
    image_rows = {(r['scan'],r['b']):r for r in analysis['measurements'] if r['mode']=='off'}
    def rounded(display, actual):
        decimals = len(display.split('.')[1]) if '.' in display else 0
        assert abs(float(display)-actual) <= .5001*10**(-decimals), (display,actual)
    section = report.split('## Image performance and the signal cost')[1].split('## Raw echoes')[0]
    for line in section.splitlines():
        if not line.startswith('| test'):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        name = cells[0]
        values = [image_rows[name,b]['interior_mean'] for b in (0,1000,6000)]
        values += [image_rows[name,6000]['interior_to_background_mean']]
        for display, actual in zip(cells[2:],values):
            rounded(display,actual)
    section = report.split('## Raw echoes')[1].split('## The seven-b scans')[0]
    for line in section.splitlines():
        if not line.startswith('| test'):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        name = cells[0].split(',')[0]
        sc = analysis['scans'][name]
        nav = {b:sc['navigators'][i] for i,b in enumerate(sc['b_values'])}
        actuals = [nav[1000]['norm'][0]/nav[0]['norm'][0],nav[6000]['norm'][0]/nav[0]['norm'][0],nav[1000]['norm'][-1]/nav[1000]['norm'][0]]
        for display, actual in zip(cells[1:],actuals):
            rounded(display,actual)
    # Independent fit by profiling out the linear offset, using scalar search.
    attenuation = json.loads((DATA/'oct07_attenuation_fits.json').read_text())
    for record in attenuation['scans']:
        name = record['scan']
        b = np.array(results[name]['b'])
        norms = np.array([r['first_navigator_l2'] for r in results[name]['volumes']])
        y = norms/norms[0]
        assert np.allclose(y,record['ratio_to_b0'],rtol=3e-7)
        low = b <= 1000
        mono = minimize_scalar(lambda d: np.mean((np.exp(-d*b[low])-y[low])**2), bounds=(0,.01),method='bounded',options={'xatol':1e-14})
        assert np.isclose(mono.x,record['low_b_anchored_mono_slope_mm2_s'],rtol=1e-5)
        if len(b)==7:
            def offset_profile(d):
                exponential = np.exp(-d*b)
                basis = 1-exponential
                f = np.clip(np.dot(y-exponential,basis)/np.dot(basis,basis),0,.5)
                rms = np.sqrt(np.mean((exponential+f*basis-y)**2))
                return rms,f
            optimum = minimize_scalar(lambda d: offset_profile(d)[0],bounds=(1e-12,.01),method='bounded',options={'xatol':1e-14})
            rms,f = offset_profile(optimum.x)
            assert np.isclose(f,record['offset_fraction'],rtol=2e-5,atol=1e-7)
            assert np.isclose(rms,record['offset_rms_ratio_residual'],rtol=2e-5,atol=1e-8)
            assert np.isclose(optimum.x,record['offset_slope_mm2_s'],rtol=2e-5)
    figures = list((ROOT/'docs/figures/physical_scanner_2026-10-07').glob('*.png'))
    assert len(figures) >= 8
    for path in figures:
        with Image.open(path) as im:
            assert im.width > 400 and im.height > 300
            im.verify()
    print(f'PASS: 10 independent MRD decodes, 46 b-labeled NIfTI reproductions, 138 image and 138 k-space rows, power/Parseval checks, raw complex-line observations, independent attenuation fits, report tables, source hashes, sidecars, catalog and report links, {len(figures)} readable figures.')


if __name__ == '__main__':
    results, analysis = verify_acquisitions()
    (DATA/'oct07_independent_verification.json').write_text(json.dumps(results, indent=2))
    verify_artifacts(results, analysis)
