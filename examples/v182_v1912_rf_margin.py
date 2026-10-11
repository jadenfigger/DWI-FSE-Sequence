"""Reproduce RF-library spatial transition margins for the v182/v1912 review.

This is a three-pulse, one-dimensional Bloch profile calculation from the
quantized sampled RF contract. It does not simulate a protocol event grid or
verify scanner playback/calibration.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dwfse.vendor_seq import decode  # noqa: E402

RF_DIR = ROOT / "docs/v19/reference_rf"
LIB_DIR = ROOT / "scanner/rf"
CONTRACT_PATH = RF_DIR / "real_rf_contract.json"
CONTRACT_NPZ = RF_DIR / "real_rf_contract.npz"
OUTPUT_JSON = ROOT / "docs/v182_v1912/validation/rf_margin.json"
GAMMA_HZ_T = 42.576e6
PROFILE_POSITIONS = 6001
PROFILE_LIMIT_M = 0.010
ADAPTATION_SCALE = 6.0
THRESHOLDS = (0.05, 0.01)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evolve_rf(b1_t: np.ndarray, gz_tm: np.ndarray, z_m: np.ndarray,
              dwell_s: float) -> np.ndarray:
    """Exact finite rotations for piecewise-constant 10-us RF rectangles.

    Matrices use rows as initial magnetization axes and columns as output axes,
    matching the repository's real_rf_transfer_results.json convention.
    """
    rotations = np.broadcast_to(np.eye(3), (z_m.size, 3, 3)).copy()
    for b1, gz in zip(b1_t, gz_tm):
        field = np.stack((np.full(z_m.size, b1 * GAMMA_HZ_T),
                          np.zeros(z_m.size), gz * GAMMA_HZ_T * z_m), axis=1)
        norm = np.linalg.norm(field, axis=1)
        axis = np.divide(field, norm[:, None], out=np.zeros_like(field),
                         where=norm[:, None] != 0)
        angle = -2.0 * np.pi * norm * dwell_s
        cosine = np.cos(angle)[:, None, None]
        sine = np.sin(angle)[:, None, None]
        rotations = (rotations * cosine
                     + np.cross(axis[:, None, :], rotations) * sine
                     + axis[:, None, :]
                     * np.sum(axis[:, None, :] * rotations, axis=2)[:, :, None]
                     * (1.0 - cosine))
    return rotations


def response_for(metric: str, rotation: np.ndarray) -> np.ndarray:
    if metric == "Mz_to_Mxy":
        # Initial Mz -> either transverse output; insensitive to z-phase.
        return np.linalg.norm(rotation[:, 2, :2], axis=1)
    if metric == "Mz_inversion_fraction":
        # Inversion of initial Mz, not irrelevant off-resonance z precession.
        return np.abs(1.0 - rotation[:, 2, 2]) / 2.0
    if metric == "Mxy_to_Mz":
        # Either transverse input -> Mz output; insensitive to z-phase.
        return np.linalg.norm(rotation[:, :2, 2], axis=1)
    raise ValueError(f"Unknown response metric {metric}")


def persistent_margin(z_m: np.ndarray, response: np.ndarray, edge_m: float,
                      threshold: float, direction: int) -> float:
    """Return outward distance beyond edge after which the tail stays below t."""
    outward = direction * z_m
    order = np.argsort(outward)
    distance = outward[order]
    values = response[order]
    eligible = np.flatnonzero(distance >= edge_m)
    # The profile is symmetric in these three real RF samples, but evaluate
    # each side independently and retain the more conservative result.
    for index in eligible:
        if np.max(values[index:]) <= threshold:
            return float(distance[index] - edge_m)
    raise ValueError("Profile extent did not contain a persistent threshold crossing")


def main() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    sample_contract_hash = sha256(CONTRACT_NPZ)
    if sample_contract_hash != contract["contract_npz_sha256"]:
        raise ValueError("Quantized RF sample contract hash mismatch")
    arrays = np.load(CONTRACT_NPZ)

    pulse_specs = (
        ("v19_slrprep90", 18.0, "Mz_to_Mxy"),
        ("v19_slrprep180", 18.0, "Mz_inversion_fraction"),
        ("v19_slrtip90", 10.0, "Mxy_to_Mz"),
    )
    # Gradient is increased sixfold for the centered 1-mm adaptation, so the
    # reference spatial widths and edge positions shrink by the same factor.
    z_m = np.linspace(-PROFILE_LIMIT_M, PROFILE_LIMIT_M, PROFILE_POSITIONS)
    pulse_results = []

    for name, reference_width_mm, metric in pulse_specs:
        metadata = contract["pulses"][name]
        csv_path = RF_DIR / metadata["numerical_csv"]
        library_path = LIB_DIR / f"{name}.seq"
        csv_hash = sha256(csv_path)
        library_hash = sha256(library_path)
        if csv_hash != metadata["numerical_csv_sha256"]:
            raise ValueError(f"Numerical sample hash mismatch for {name}")

        library = decode(library_path)
        frame = library.frame(name)
        expected_dac = arrays[f"{name}_dac"]
        if not np.array_equal(frame.samples, expected_dac):
            raise ValueError(f"Decoded WavEd samples differ from contract for {name}")
        if frame.wait_ticks != metadata["wait_ticks"]:
            raise ValueError(f"Decoded WavEd dwell differs from contract for {name}")
        if len(frame.samples) != metadata["sample_count"]:
            raise ValueError(f"Decoded WavEd sample count differs for {name}")

        csv = np.loadtxt(csv_path, delimiter=",")
        if not (np.array_equal(csv[:, 0], arrays[f"{name}_time_s"])
                and np.array_equal(csv[:, 1], arrays[f"{name}_B1_T"])
                and np.array_equal(csv[:, 3], arrays[f"{name}_Gz_Tm"])):
            raise ValueError(f"CSV waveform differs from quantized contract for {name}")

        # Adapt the gradient, not RF amplitude. The library stores RF only;
        # its decoded signed DAC samples are checked against the normalized
        # Tesla samples used by the Bloch calculation above.
        rotation = evolve_rf(arrays[f"{name}_B1_T"],
                             arrays[f"{name}_Gz_Tm"] * ADAPTATION_SCALE,
                             z_m, frame.wait_ticks * 1e-7)
        response = response_for(metric, rotation)
        center = int(np.argmin(np.abs(z_m)))
        center_response = float(response[center])
        if center_response <= 0:
            raise ValueError(f"Zero center response for {name}")
        response = response / center_response
        adapted_width_mm = reference_width_mm / ADAPTATION_SCALE
        edge_m = adapted_width_mm / 2000.0
        margins = {}
        for threshold in THRESHOLDS:
            per_side = [
                1000.0 * persistent_margin(z_m, response, edge_m, threshold, +1),
                1000.0 * persistent_margin(z_m, response, edge_m, threshold, -1),
            ]
            margins[f"{threshold:.2%}"] = {
                "margin_mm_each_side": per_side,
                "conservative_margin_mm": max(per_side),
                "margin_in_1mm_slice_thicknesses": max(per_side) / 1.0,
            }
        pulse_results.append({
            "name": name,
            "vendor_library": str(library_path.relative_to(ROOT)).replace("\\", "/"),
            "vendor_library_sha256": library_hash,
            "decoded_frame_name": frame.name,
            "decoded_sample_count": int(len(frame.samples)),
            "decoded_wait_ticks": int(frame.wait_ticks),
            "decoded_samples_exactly_match_quantized_contract": True,
            "numerical_csv": str(csv_path.relative_to(ROOT)).replace("\\", "/"),
            "numerical_csv_sha256": csv_hash,
            "quantized_dac_samples_sha256": hashlib.sha256(
                np.asarray(expected_dac, dtype="<i2").tobytes()).hexdigest(),
            "reference_width_mm": reference_width_mm,
            "adapted_width_mm": adapted_width_mm,
            "response_metric": metric,
            "center_response_before_normalization": center_response,
            "transition_margins": margins,
        })

    chosen = max(p["transition_margins"]["5.00%"]["conservative_margin_mm"]
                 for p in pulse_results)
    report = {
        "status": "reproducible quantized RF sample profile estimate; not scanner verification",
        "method": {
            "profile_count": len(pulse_results),
            "description": "One independent 1D spatial Bloch profile per RF pulse; no protocol/event grid.",
            "positions": PROFILE_POSITIONS,
            "adapted_z_range_mm": [-PROFILE_LIMIT_M * 1000, PROFILE_LIMIT_M * 1000],
            "dwell_us": 10,
            "gamma_Hz_T": GAMMA_HZ_T,
            "adaptation_gradient_scale": ADAPTATION_SCALE,
            "threshold_rule": "First outward position beyond nominal half-width where all farther profile samples through the simulated boundary remain below threshold, divided by center response.",
            "symmetric_side_check": "Both sides evaluated independently; conservative side reported.",
            "phase_handling": "Response norms and Mz inversion fraction are invariant to z-axis pre/post phase rotations; no phase correction is needed for these magnitude metrics.",
        },
        "sample_provenance": {
            "contract_json": str(CONTRACT_PATH.relative_to(ROOT)).replace("\\", "/"),
            "contract_json_sha256": sha256(CONTRACT_PATH),
            "contract_npz": str(CONTRACT_NPZ.relative_to(ROOT)).replace("\\", "/"),
            "contract_npz_sha256": sample_contract_hash,
            "wavEd_decoder": "dwfse/vendor_seq.py:decode",
            "all_three_vendor_frames_match_quantized_dac_samples_exactly": True,
        },
        "pulses": pulse_results,
        "selected_spacing_margin": {
            "value_mm": 0.75,
            "slice_thickness_mm": 1.0,
            "value_in_slice_thicknesses": 0.75,
            "criterion": "5% normalized response",
            "maximum_measured_pulse_margin_mm": chosen,
            "maximum_measured_pulse_margin_in_slice_thicknesses": chosen / 1.0,
            "interpretation": "0.75 slice is a rounded conservative margin over the largest measured 5% transition; it is not a 1% guarantee.",
        },
        "limitations": [
            "The library sample match proves local binary sample identity, not vendor loading, PPL gating, transmit calibration, or scanner playback.",
            "Bloch profiles use the contract's nominal normalized RF amplitudes and ideal centered gradients; physical B1 and gradient calibration are not measured.",
            "Per-pulse transitions do not model cross-talk or the complete preparation, crusher, re-excitation, and acquisition pathway.",
            "The selected 5% margin is intentionally not a 1% side-lobe guarantee; the prep90 1% margin is substantially larger.",
        ],
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["selected_spacing_margin"], indent=2))


if __name__ == "__main__":
    main()
