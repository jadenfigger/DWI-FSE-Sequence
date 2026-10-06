"""Audit PE-order evidence and saved NIfTI consistency for Oct 5 scanner scans.

This checks the reconstruction implementation against each saved NIfTI. It does
not establish that the scanner's v1.8 PPL played the same 6/7 row order: that PPL
source is not present in this repository.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nibabel as nib
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scanner" / "recon"))
from get_mrd_3d4 import get_mrd_3d4  # noqa: E402

SCANS = ["test1e", "test1f", "test1g", "test2b", "test2c", "test2d"]
FIG_DIR = ROOT / "docs" / "figures" / "physical_scanner_2026-10-05"
OUT_JSON = ROOT / "docs" / "data" / "oct05_pe_reconstruction_audit.json"


def pe_rows(n: int, etl: int, order: int) -> np.ndarray:
    shots = n // etl
    s = np.arange(shots)[:, None]
    e = np.arange(etl)[None, :]
    if order == 7:
        return (s + e * shots).ravel()
    v = shots // 2
    if order == 6:
        e = etl - 1 - e
    return (n // 2 + s - v + np.where(s < v, -v * e, v * e)).ravel()


def nav_factor(nav: np.ndarray, rows: np.ndarray, order: int, n: int, etl: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    amp = np.linalg.norm(nav, axis=1)
    amp /= amp[0]
    dc = nav.sum(axis=1)
    phase = np.angle(dc * np.conj(dc[0]))
    echo = np.arange(n) % etl
    step_weight = amp[echo]
    ky = rows - n // 2
    coordinate = ky if order == 7 else np.abs(ky)
    centres = np.array([coordinate[echo == i].mean() for i in range(etl)])
    target = np.interp(coordinate, centres[np.argsort(centres)], amp[np.argsort(centres)])
    factor = target * step_weight / (step_weight**2 + 0.01**2)
    factor = factor * np.exp(-1j * phase[echo])
    return factor.astype(np.complex64), amp, phase


def main() -> None:
    records = []
    map_fig, map_axes = plt.subplots(2, 3, figsize=(15, 8), constrained_layout=True)
    consistency_fig, consistency_axes = plt.subplots(2, 3, figsize=(15, 8), constrained_layout=True)
    shared_b0_max = max(float(np.max(np.asarray(nib.load(str(ROOT/'experiments'/f'FSE-DWI_10-05-2026_v18_{n}'/f'FSE-DWI_10-05-2026_v18_{n}.nii.gz')).dataobj)[:, :, 0, 0])) for n in SCANS)

    for index, scan in enumerate(SCANS):
        folder = ROOT / "experiments" / f"FSE-DWI_10-05-2026_v18_{scan}"
        mrd = folder / f"FSE-DWI_10-05-2026_v18_{scan}.MRD"
        kspace, dims, embedded = get_mrd_3d4(mrd)
        order = int(embedded["PE_order"])
        etl = int(embedded["views_per_seg"])
        nav_on = bool(embedded["nav_on"])
        n = dims[4] - (etl if nav_on else 0)
        rows = pe_rows(n, etl, order)
        echo = np.arange(n) % etl

        # Current recon source drops the navigator shot, maps each acquired image
        # line to rows, applies deramp and navigator phase, then takes |IFFT2|.
        reconstructed_by_volume = []
        nav_amp_by_volume = []
        nav_phase_by_volume = []
        for volume in range(dims[0]):
            raw = kspace[volume, 0, 0, 0]
            k_image = raw[etl:, :] if nav_on else raw
            sorted_k = np.zeros((n, dims[5]), dtype=np.complex64)
            sorted_k[rows, :] = k_image
            nav_amp = nav_phase = None
            if nav_on:
                correction, nav_amp, nav_phase = nav_factor(raw[:etl], rows, order, n, etl)
                sorted_k[rows, :] *= correction[:, None]
            reconstructed_by_volume.append(np.abs(np.fft.fftshift(
                np.fft.ifft2(np.fft.ifftshift(sorted_k, axes=(0, 1)), axes=(0, 1)), axes=(0, 1)
            )))
            nav_amp_by_volume.append(nav_amp)
            nav_phase_by_volume.append(nav_phase)

        nifti_path = mrd.with_suffix(".nii.gz")
        saved_all = np.asarray(nib.load(str(nifti_path)).dataobj)[:, :, 0, :]
        # Recon writes transpose(img_all, (1,0,2,3)): image x/y are swapped.
        volume_checks = []
        for volume, reconstructed in enumerate(reconstructed_by_volume):
            saved = saved_all[:, :, volume]
            predicted = reconstructed.T
            residual = saved.astype(np.float64) - predicted
            scale = max(float(np.max(np.abs(saved))), 1e-12)
            nrmse = float(np.sqrt(np.mean(residual**2)) / scale)
            correlation = float(np.corrcoef(saved.ravel(), predicted.ravel())[0, 1])
            volume_checks.append({
                "volume": volume,
                "correlation": correlation,
                "normalized_RMSE_by_saved_max": nrmse,
                "max_absolute_difference": float(np.max(np.abs(residual))),
            })
        saved = saved_all[:, :, 0]
        first_check = volume_checks[0]

        ax = map_axes.flat[index]
        matrix = np.vstack([rows[echo == e] - n // 2 for e in range(etl)])
        ax.imshow(matrix, aspect="auto", interpolation="nearest", cmap="coolwarm",
                  vmin=-n // 2, vmax=n // 2 - 1)
        ax.set_title(f"{scan}: embedded PE_order={order}")
        ax.set_yticks(np.arange(etl), labels=np.arange(1, etl + 1))
        ax.set_xlabel("Shot index")
        ax.set_ylabel("Echo number")
        if nav_amp is not None:
            ax.text(0.99, 0.02, "ky rows per image echo", transform=ax.transAxes,
                    ha="right", va="bottom", fontsize=8, color="black",
                    bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none"})

        ax2 = consistency_axes.flat[index]
        ax2.imshow(saved.T, cmap="gray", interpolation="nearest", vmin=0, vmax=shared_b0_max)
        ax2.set_title(f"{scan}: saved vs replay\nr={first_check['correlation']:.6f}, NRMSE={first_check['normalized_RMSE_by_saved_max']:.2g}")
        ax2.set_axis_off()

        sidecar = json.loads((folder / f"FSE-DWI_10-05-2026_v18_{scan}.json").read_text())
        records.append({
            "scan": scan,
            "embedded_PE_order": order,
            "sidecar_PEOrder": sidecar.get("PEOrder"),
            "embedded_and_sidecar_agree": sidecar.get("PEOrder") == order,
            "embedded_views_per_seg": etl,
            "MRD_dimensions_expt_echo_slice_view2_view_samples": dims,
            "navigator_on": nav_on,
            "image_lines_after_navigator": n,
            "conditional_mapping_rows_ky_order_by_shot": (rows.reshape(-1, etl).T - n // 2).tolist(),
            "conditional_echo_number_that_acquires_ky_zero": int(np.where(rows == n // 2)[0][0] % etl + 1),
            "conditional_mean_absolute_ky_by_echo": [float(np.mean(np.abs(rows[echo == e] - n // 2))) for e in range(etl)],
            "navigator_amplitude_relative_to_echo1_by_volume": [a.tolist() if a is not None else None for a in nav_amp_by_volume],
            "navigator_phase_relative_to_echo1_deg_by_volume": [np.degrees(p).tolist() if p is not None else None for p in nav_phase_by_volume],
            "saved_NIfTI_matches_current_reconstruction_by_volume": volume_checks,
            "v18_scanner_PPL_mapping_verified_from_source": False,
        })

    map_fig.suptitle("Conditional echo-to-ky assignments from the repository recon formulas\n"
                     "Rows are ky indices relative to k-space center; shot columns follow acquisition order")
    map_fig.colorbar(map_axes[0,0].images[0],ax=map_axes.ravel().tolist(),shrink=.7,label='ky index relative to center')
    map_fig.savefig(FIG_DIR / "pe_echo_to_ky_assignments.png", dpi=180)
    consistency_fig.suptitle("Saved NIfTI magnitude images for the first volume\n"
                             "Shared linear scale and main-report orientation; titles report pixelwise replay agreement")
    consistency_fig.colorbar(consistency_axes[0,0].images[0],ax=consistency_axes.ravel().tolist(),shrink=.7,label='b0 magnitude (acquisition units)')
    consistency_fig.savefig(FIG_DIR / "pe_saved_nifti_replay.png", dpi=180)

    report = {
        "scope": SCANS,
        "evidence_boundary": {
            "actual_observation": "Embedded MRD PPR contains PE_order values; adjacent JSON sidecar values are also recorded.",
            "reconstruction_behavior": "Repository reconstruction supports 1, 6, and 7 explicitly; unsupported values raise ValueError. It reads the embedded PPR when no manual override is set.",
            "scanner_mapping_limit": "The repository includes v1.7 PPL source that explicitly exposes and implements orders 6/7, but no v1.8 PPL source. This proves the predecessor supported those modes, not that v1.8 retained them unchanged.",
            "conditional_labels": "PE-to-ky maps use scanner/recon/bare_bones_recon_fse.py's formulas, conditional on those formulas matching the scanner's actual acquisition order.",
        },
        "v17_predecessor_PPL_evidence": {
            "file": "scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.7.ppl",
            "ui_options": "Scrollbar labels 6=reverse centric and 7=linear interleaved.",
            "acquisition_logic": "PE_order_6_7 block; explicit validation and separate PE_order==6 branch.",
            "v18_source_available": False,
        },
        "reconstruction_code_path": "scanner/recon/bare_bones_recon_fse.py",
        "v18_ppl_source_files_in_scanner_directory": sorted(p.name for p in (ROOT / "scanner").glob("*.ppl") if "1.8" in p.name),
        "records": records,
    }
    OUT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"json": str(OUT_JSON), "figures": [str(FIG_DIR / "pe_echo_to_ky_assignments.png"), str(FIG_DIR / "pe_saved_nifti_replay.png")],
                      "replay": [{"scan": r["scan"], "volumes": r["saved_NIfTI_matches_current_reconstruction_by_volume"]} for r in records]}, indent=2))


if __name__ == "__main__":
    main()
