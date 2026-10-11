"""Small recon checks; archived scans are read-only, outputs under recon_checks.

python examples/test_v182_v1912_recon.py
"""
import ast
import contextlib
import csv
import io
import json
from pathlib import Path
import re
import sys
import struct
import time
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scanner/recon"))
import bare_bones_recon_fse as recon
from effective_b import effective_b
from shot_navigator import correct_shot_phase, readout_projection, projection_kspace, split_mode2

OUT = ROOT / "docs/v182_v1912/recon_checks"


def one_row(protocol, b, direction=(1000, 0, 0)):
    protocol = re.sub(r"(:VAR\s+no_diff_acq,\s*)\d+", r"\g<1>1", protocol)
    protocol = re.sub(r"(:EXPERIMENT_ARRAY\s+no_experiments,\s*)\d+", r"\g<1>1", protocol)
    for key, value in dict(acq_b=b, acq_x=direction[0], acq_y=direction[1], acq_z=direction[2]).items():
        protocol = re.sub(rf"(:VAR_ARRAY\s+{key},)\s*\d+,.*?(?=\r?\n:|\Z)", rf"\g<1> 1, {value}", protocol, flags=re.S)
    return protocol


def reference_checks():
    refs = json.loads((ROOT / "docs/v181_v1911/review_checks/final_physics_grid.json").read_text())["btensors"]
    rows = []
    for version, label in (("1.8", "v18"), ("1.81", "v181"), ("1.91", "v191_v7"), ("1.911", "v1911")):
        folder = ROOT / ("docs/v181_v1911/baseline_v7" if version == "1.91" else "scanner")
        ppr = folder / f"FSE_dwi_CPMG_non_CPMG_twoTE-{version}.ppr"
        if version == "1.8":
            ppr = ROOT / "experiments/FSE-DWI_10-05-2026_v18_test1e/FSE-DWI_10-05-2026_v18_test1.ppr"
        protocol = ppr.read_text(encoding="latin-1")
        for b in (0, 100, 1000, 6000):
            text = one_row(protocol, b)
            result = effective_b(text, recon.read_diffusion(text), 1, 128, cache_dir=OUT / "cache")
            expected = refs[label][str(b)]["echoes"][0]["selected_trace_s_mm2"]
            delta = result["EffectiveBValue"][0] - expected
            assert result["BMatrixSource"] == "event-model-primary-pathway", result
            assert abs(delta) < .5, (version, b, delta)
            rows.append(dict(version=version, nominal=b, actual=result["EffectiveBValue"][0], expected=expected, delta=delta))
    # Polarity and axis checks use independent earlier direction ledger evidence.
    dirs = json.loads((ROOT / "docs/v181_v1911/review_checks/physics_review_btensor2.json").read_text())["direction"]
    for version, label in (("1.8", "v18"), ("1.81", "v181")):
        protocol = (ROOT / "scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppr").read_text(encoding="latin-1")
        protocol = re.sub(r"^:PPL.*", f":PPL FSE_dwi_CPMG_non_CPMG_twoTE-{version}.ppl", protocol, flags=re.M)
        for name, d in (("-X(read)", (-1000, 0, 0)), ("+Y(phase)", (0, 1000, 0)), ("+Z(slice)", (0, 0, 1000))):
            text = one_row(protocol, 1000, d)
            result = effective_b(text, recon.read_diffusion(text), 1, 128, cache_dir=OUT / "cache")
            expected = dirs[f"{name} b1000"][label]["E1_total"]
            delta = result["EffectiveBValue"][0] - expected
            assert abs(delta) < .5, (version, name, delta)
            rows.append(dict(version=version, direction=name, nominal=1000, actual=result["EffectiveBValue"][0], expected=expected, delta=delta))
    return rows


def test_fallback_and_calibration():
    text = one_row((ROOT / "scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppr").read_text(encoding="latin-1"), 1000)
    missing = text.replace("1.81.ppl", "1.999.ppl")
    fallback = effective_b(missing, recon.read_diffusion(missing), 1, 128)
    assert fallback["BMatrixSource"] == "nominal-fallback"
    assert fallback["EffectiveBValue"] == [1000]
    OUT.mkdir(parents=True, exist_ok=True)
    calibration = OUT / "test_calibration.json"
    calibration.write_text(json.dumps({"versions": {"1.81": {"axis_scale": [1, 1, 1.01], "additive_bmatrix": [[1, 0, 0], [0, 0, 0], [0, 0, 0]]}}}))
    before = effective_b(text, recon.read_diffusion(text), 1, 128, cache_dir=OUT / "cache")
    after = effective_b(text, recon.read_diffusion(text), 1, 128, cache_dir=OUT / "cache", calibration_path=calibration)
    assert after["BMatrixCalibrationApplied"]
    assert abs(after["EffectiveBValue"][0] - before["EffectiveBValue"][0] - 1 - before["BMatrix"][0][2] * (1.01**2 - 1)) < 1e-8
    assert after["BMatrixModel"]["CacheHit"]
    # Broken cache bytes and shape are ordinary model failures, never a reason
    # to stop reconstruction or publish a partially loaded matrix table.
    broken_dir = OUT / "invalid_cache_test"
    valid = effective_b(text, recon.read_diffusion(text), 1, 128, cache_dir=broken_dir)
    assert valid["BMatrixSource"] == "event-model-primary-pathway"
    cache = broken_dir / (valid["BMatrixModel"]["CacheKey"] + ".json")
    original = cache.read_text()
    try:
        for payload in ("{broken", '{"matrices": [[1,2,3]], "branches": ["primary"]}', '{"matrices": [[[NaN,0,0],[0,1,0],[0,0,1]]], "branches": ["primary"]}'):
            cache.write_text(payload)
            invalid = effective_b(text, recon.read_diffusion(text), 1, 128, cache_dir=broken_dir)
            assert invalid["BMatrixSource"] == "nominal-fallback", invalid
            assert invalid["EffectiveBValue"] == [1000]
    finally:
        cache.write_text(original)
    # Timing/ignored-list failures are reported as fallback before integrating.
    sys.path.insert(0, str(ROOT))
    for flag in (dict(kind="timer_overrun", message="waittimer overrun"),
                 dict(kind="gradient", message="SetList on active channel R ignored")):
        fake = SimpleNamespace(vars={}, flags=[flag])
        with patch("dwfse.ppl.run.map_events", return_value=fake):
            invalid = effective_b(text, recon.read_diffusion(text), 1, 128)
        assert invalid["BMatrixSource"] == "nominal-fallback"
        assert invalid["EffectiveBValue"] == [1000]
        assert any("timing/gradient hazards" in warning for warning in invalid["BMatrixWarnings"])


def test_etl1_mode2():
    N, samples, etl = 16, 64, 1
    x = np.arange(samples) - (samples - 1) / 2
    base = np.exp(-x*x / 36).astype(complex)
    base[np.abs(x) > 16] = 0
    phases = np.linspace(-.7, .7, N)
    slopes = np.linspace(-.01, .01, N)
    projections = base[None] * np.exp(1j * (phases[:, None] + slopes[:, None] * x))
    nav = projection_kspace(projections).astype(np.complex64)
    blocks = np.stack([nav, nav], axis=1).reshape(2*N, samples)
    raw = np.concatenate([nav[:2], blocks])
    volume, image, navigators = split_mode2(raw, etl, N)
    assert volume.shape == (1, samples) and image.shape == (N, samples)
    assert np.array_equal(navigators, nav)
    for order in (1, 6, 7):
        assert np.array_equal(recon.pe_rows(N, etl, order), np.arange(N))
    corrected, qa = correct_shot_phase(image, navigators, etl)
    reference = qa["ReferenceShot"]
    assert all(q["applied"] for q in qa["Estimates"])
    assert np.linalg.norm(corrected - nav[reference]) / np.linalg.norm(nav) < 2e-6
    amp, phase, lines = recon.nav_envelope(volume, etl)
    assert np.array_equal(amp, [1]) and np.allclose(phase, [0], atol=1e-7)
    t2, mean, std = recon.nav_fit_t2_per_x(lines, 14)
    assert np.all(np.isnan(t2)) and np.isnan(mean) and np.isnan(std)


def synthetic_check(raw, mrd=None, protocol=None):
    rng = np.random.default_rng(182912)
    etl = 8
    image_lines = raw[etl:]
    nshots = len(image_lines) // etl
    x = np.arange(raw.shape[1]) - (raw.shape[1] - 1) / 2
    # Smooth the archived volume navigator and suppress background for a precise
    # known-signal oracle; its projection still comes from the acquired scan.
    projection = readout_projection(raw[:1])[0]
    projection[np.abs(projection) < .15 * np.max(np.abs(projection))] = 0
    phases = rng.uniform(-1.8, 1.8, nshots)
    slopes = rng.uniform(-.025, .025, nshots)
    corrupted = image_lines.copy()
    navs = []
    for shot in range(nshots):
        error = np.exp(1j * (phases[shot] + slopes[shot] * x))
        corrupted[shot*etl:(shot+1)*etl] = projection_kspace(readout_projection(image_lines[shot*etl:(shot+1)*etl]) * error)
        navs.append(projection_kspace(projection * error))
    navs = np.asarray(navs)
    corrected, qa = correct_shot_phase(corrupted, navs, etl)
    assert all(q["applied"] for q in qa["Estimates"]), qa
    ref = qa["ReferenceShot"]
    expected = projection_kspace(readout_projection(image_lines) * np.exp(1j * (phases[ref] + slopes[ref] * x)))
    relative = np.linalg.norm(corrected - expected) / np.linalg.norm(expected)
    assert relative < 2e-6, relative
    noisy = rng.normal(size=navs.shape) + 1j*rng.normal(size=navs.shape)
    unchanged, noisyqa = correct_shot_phase(corrupted, noisy, etl)
    assert not any(q["applied"] for q in noisyqa["Estimates"]), noisyqa
    assert np.array_equal(unchanged, corrupted)
    constant_corrected, constantqa = correct_shot_phase(corrupted, navs, etl, "constant")
    assert all(q["linear_rad_per_voxel"] == 0 for q in constantqa["Estimates"])
    off, _ = correct_shot_phase(corrupted, navs, etl, "off")
    assert np.array_equal(off, corrupted)
    contract = np.concatenate([raw[:etl], navs[:1], np.concatenate([corrupted.reshape(nshots, etl, -1), navs[:, None]], axis=1).reshape(-1, raw.shape[1])])
    volume, image, nav = split_mode2(contract, etl, len(image_lines))
    assert np.array_equal(image, corrupted) and np.array_equal(nav, navs)
    assert np.array_equal(volume, raw[:etl])
    end_to_end = {}
    image_errors = {}
    if mrd is not None:
        # Synthesise a real-format single-volume MRD under the output directory,
        # keeping its protocol embedded and allocating all 153 rows explicitly.
        with Path(mrd).open("rb") as stream:
            header = bytearray(stream.read(512))
        def write_mrd(path, lines, text):
            binary_header = bytearray(header)
            struct.pack_into("<4i", binary_header, 0, lines.shape[1], len(lines), 1, 1)
            struct.pack_into("<H", binary_header, 18, 0x15)  # complex float32
            struct.pack_into("<2i", binary_header, 152, 1, 1)
            floats = np.empty((len(lines), lines.shape[1], 2), dtype="<f4")
            floats[..., 0], floats[..., 1] = lines.real, lines.imag
            path.write_bytes(binary_header + floats.tobytes() + bytes(120) + text.encode("latin-1"))
        saved_nifti = recon.save_nifti
        recon.save_nifti = False
        try:
            mode2text = one_row(protocol, 0)
            mode2text = re.sub(r"(:VAR\s+nav_on,\s*)\d+", r"\g<1>2", mode2text)
            mode2text = re.sub(r"(:NO_VIEWS\s+no_views,\s*)\d+", rf"\g<1>{len(contract)}", mode2text)
            for version in ("1.82", "1.912"):
                text = re.sub(r"^:PPL.*", f":PPL FSE_dwi_CPMG_non_CPMG_twoTE-{version}.ppl", mode2text, flags=re.M)
                path = OUT / f"synthetic_mode2_{version}.MRD"
                write_mrd(path, contract, text)
                with contextlib.redirect_stdout(io.StringIO()):
                    result = recon.run_recon(path, OUT / f"synthetic_{version}")
                sorted_expected = np.zeros_like(result["kspace"][:, :, 0, 0])
                rows = recon.pe_rows(len(image_lines), etl, 1)
                acquired_ref = result["shot_navigator"][0]["ReferenceShot"]
                actual_expected = projection_kspace(readout_projection(image_lines) * np.exp(1j * (phases[acquired_ref] + slopes[acquired_ref] * x)))
                sorted_expected[rows] = actual_expected
                amp, phase, _ = recon.nav_envelope(raw, etl)
                sorted_expected[rows] *= recon.nav_correction(amp, phase, np.arange(len(image_lines)) % etl, rows, len(image_lines), "deramp", True, .01)[:, None]
                error = np.linalg.norm(result["kspace"][:, :, 0, 0] - sorted_expected) / np.linalg.norm(sorted_expected)
                assert error < 2e-6, (version, error)
                end_to_end[version] = float(error)
                ideal_image, _ = legacy_image(raw, etl, 1, "deramp")
                image_error = np.linalg.norm(result["image"][:, :, 0, 0] - ideal_image) / np.linalg.norm(ideal_image)
                assert image_error < 2e-6, (version, image_error)
                image_errors[version] = float(image_error)
            # Missing flag selects nav0 and leaves all imaging rows untouched.
            noflag = re.sub(r"^:VAR\s+nav_on,[^\r\n]*\r?\n", "", one_row(protocol, 0), flags=re.M)
            noflag = re.sub(r"(:NO_VIEWS\s+no_views,\s*)\d+", rf"\g<1>{len(image_lines)}", noflag)
            path = OUT / "synthetic_nav_absent.MRD"
            write_mrd(path, image_lines, noflag)
            with contextlib.redirect_stdout(io.StringIO()):
                result = recon.run_recon(path, OUT / "synthetic_nav_absent")
            sorted_expected = np.zeros_like(image_lines)
            sorted_expected[recon.pe_rows(len(image_lines), etl, 1)] = image_lines
            assert np.array_equal(result["kspace"][:, :, 0, 0], sorted_expected)
            badflag = noflag + ":VAR nav_on, 3\n"
            path = OUT / "synthetic_nav_unknown.MRD"
            write_mrd(path, image_lines, badflag)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    recon.run_recon(path, OUT / "synthetic_nav_unknown")
            except ValueError as error:
                assert "Unsupported embedded nav_on=3" in str(error)
            else:
                raise AssertionError("unknown mode must raise")
        finally:
            recon.save_nifti = saved_nifti
    return dict(relative_complex_kspace_error=float(relative), tolerance=2e-6,
                recovered_relative_to_reference=True, noise_fallback_all_shots=True,
                raw_views=len(contract), imaging_views=len(image_lines), qa=qa,
                end_to_end_mode2_error=end_to_end, absent_nav_bit_identical=True,
                end_to_end_image_error=image_errors, unknown_nav_rejected=True)


def legacy_image(raw, etl, order, mode, phase=True):
    N = len(raw) - etl
    rows = recon.pe_rows(N, etl, order)
    sorted_k = np.zeros((N, raw.shape[1]), np.complex64)
    sorted_k[rows] = raw[etl:]
    if mode != "off":
        amp, ph, _ = recon.nav_envelope(raw, etl)
        correction = recon.nav_correction(amp, ph, np.arange(N) % etl, rows, N, mode, phase, .01, order)
        sorted_k[rows] *= correction[:, None]
    image = np.abs(np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(sorted_k, axes=(0, 1)), axes=(0, 1)), axes=(0, 1)))
    return image, sorted_k


def archived_checks():
    import nibabel as nib
    recon.save_images_mode = None
    recon.nav_report = False
    results, scans = {}, {}
    for letter, tag in (("A", "v181"), ("C", "v18"), ("B", "v1911"), ("D", "v191"), ("E", "v181")):
        folder = ROOT / f"experiments/FSE-DWI_10-10-2026_{tag}_test{letter}"
        mrd = next(folder.glob("*.MRD"))
        start = time.perf_counter()
        with contextlib.redirect_stdout(io.StringIO()):
            result = recon.run_recon(mrd, OUT / letter)
        scans[letter] = result
        delta = 0.
        for volume in range(result["raw"].shape[3]):
            original, sorted_k = legacy_image(result["raw"][:, :, 0, volume], 8, 1, "deramp")
            assert np.array_equal(original, result["image"][:, :, 0, volume])
            assert np.array_equal(sorted_k, result["kspace"][:, :, 0, volume])
        nifti = next(folder.glob("*.nii.gz"))
        archived = np.asarray(nib.load(nifti).dataobj)
        delta = float(np.max(np.abs(archived - result["image"].transpose(1, 0, 2, 3))))
        assert delta / np.max(archived) < 1e-6
        metadata = json.loads((OUT / letter / (mrd.stem + ".json")).read_text())
        assert metadata["BMatrixSource"] == "event-model-primary-pathway", metadata
        nominal = (OUT / letter / (mrd.stem + ".bval")).read_text()
        assert np.array_equal(np.fromstring(nominal, sep=" "), result["diffusion"]["b"])
        results[letter] = dict(image_bit_identical_legacy=True, sorted_kspace_bit_identical_legacy=True,
                               archived_nifti_max_difference=delta,
                               runtime_seconds=time.perf_counter()-start, effective_b=metadata["EffectiveBValue"])
    # Repeat with navigator flag absent/off: unchanged arithmetic compared with
    # direct legacy imaging path, including identical complex64 row insertion.
    raw = scans["A"]["raw"][:, :, 0, 0]
    mrd = next((ROOT / "experiments/FSE-DWI_10-10-2026_v181_testA").glob("*.MRD"))
    synth = synthetic_check(raw, mrd, scans["A"]["header"])
    # Fit same measured echoes 2-8 low-b signal used by the scanner report. This
    # avoids the separately documented b0 echo-1 defect.
    measurements = list(csv.DictReader((ROOT / "docs/data/oct10_navigator_echoes.csv").open()))
    adcs = {}
    for letter in ("A", "C", "B", "D"):
        values = []
        bs = results[letter]["effective_b"]
        for echo in range(2, 9):
            samples = [r for r in measurements if r["scan"] == letter and int(r["slice"]) == 1 and int(r["echo"]) == echo and float(r["b"]) <= 1000]
            volume = np.array([int(r["volume"])-1 for r in samples])
            signal = np.array([float(r["noise_sub_amp"]) for r in samples])
            values.append(float(-np.polyfit(np.asarray(bs)[volume], np.log(signal), 1)[0]))
        adcs[letter] = float(np.median(values))
    assert max(adcs.values())/min(adcs.values()) - 1 < .03, adcs
    return results, synth, adcs


def new_sequence_checks():
    out = {"mode2": {}}
    for version in ("1.82", "1.912"):
        protocol = (ROOT / f"scanner/FSE_dwi_CPMG_non_CPMG_twoTE-{version}.ppr").read_text(encoding="latin-1")
        diff = recon.read_diffusion(protocol)
        N = int(re.search(r":NO_VIEWS\s+no_views,\s*(\d+)", protocol)[1]) - 8
        out[version] = effective_b(protocol, diff, diff["n"], N, cache_dir=OUT / "cache")
        assert out[version]["BMatrixSource"] == "event-model-primary-pathway"
        text = one_row(protocol, 1000)
        text = re.sub(r"(:VAR\s+nav_on,\s*)\d+", r"\g<1>2", text)
        text = re.sub(r"(:NO_VIEWS\s+no_views,\s*)\d+", rf"\g<1>{(N // 8 + 1) * 9}", text)
        out["mode2"][version] = effective_b(text, recon.read_diffusion(text), 1, N, cache_dir=OUT / "cache")
        assert out["mode2"][version]["BMatrixSource"] == "event-model-primary-pathway"
        assert out["mode2"][version]["BMatrixModel"]["RepresentativeImagingShotIndex"] == [2]
        if version == "1.82":
            text = re.sub(r"(:VAR\s+PE_order,\s*)\d+", r"\g<1>7", text)
            out["mode2"]["1.82_PE7"] = effective_b(text, recon.read_diffusion(text), 1, N, pe_order=7, cache_dir=OUT / "cache")
            assert out["mode2"]["1.82_PE7"]["BMatrixSource"] == "event-model-primary-pathway"
            assert out["mode2"]["1.82_PE7"]["BMatrixEcho"] == 5
    multi = ROOT / "docs/v182_v1912/test_pprs/v1912_nav2_3slices.ppr"
    if multi.exists():
        text = one_row(multi.read_text(encoding="latin-1"), 1000)
        out["mode2"]["1.912_3slices"] = effective_b(text, recon.read_diffusion(text), 1, 128, cache_dir=OUT / "cache")
        assert out["mode2"]["1.912_3slices"]["BMatrixSource"] == "event-model-primary-pathway"
        assert out["mode2"]["1.912_3slices"]["BMatrixModel"]["RepresentativeImagingShotIndex"] == [4]
    (OUT / "new_version_effective_b.json").write_text(json.dumps(out, indent=2))
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("Reference b-matrix checks...", flush=True)
    refs = reference_checks()
    test_fallback_and_calibration()
    test_etl1_mode2()
    print("Archived scans and synthetic phase checks...", flush=True)
    archives, synthetic, adcs = archived_checks()
    new_sequence_checks()
    report = dict(reference=refs, archived=archives, synthetic=synthetic,
                  effective_b_ADC_echoes2to8_mm2_s=adcs,
                  calibration_test="artificial factors verify mechanics only; no scanner calibration asserted")
    (OUT / "results.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(dict(reference_max_error=max(abs(r["delta"]) for r in refs), archives=archives, adc=adcs,
                          synthetic_error=synthetic["relative_complex_kspace_error"]), indent=2))


if __name__ == "__main__":
    main()
