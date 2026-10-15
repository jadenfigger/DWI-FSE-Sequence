"""Quality-masked in-vivo and ex-vivo ADC maps for the October 12 scanner session.

Creates unsmoothed, raw-magnitude two-point log-slope maps for iA, iB, EPI-invivoA,
and the acquired three-direction Q/R ex-vivo scans.
The map mask is the existing whole-brain ROI intersected with a 5*sigma floor on every
raw magnitude endpoint in the interval. This is a display/QC censor, not an unbiased ADC
estimator. FSE b-values are the source-model echo-1 traces; EPI uses the typed b-values.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from oct12_load import ROOT, load, load_epi, direction_label
from oct12_roi_analysis import M, NOISE_COLS_EX, NOISE_COLS_IV, centre_index, move, shift_to, sigma_of

OUT = ROOT / "docs/data"
FIGDIR = ROOT / "docs/figures/physical_scanner_2026-10-12"
FIGDIR.mkdir(parents=True, exist_ok=True)
MASK_KEY = "iv_brain"
FSE_KEYS = ("iA", "iB", "Q", "R")
EPI_KEY = "epiA"
EX_EPI_KEY = "epi0"
THRESHOLD_SIGMA = 5.0
DIRECTIONS = ("+x", "+y", "+z")
INTERVALS = {"low_baseline_to_1000": (None, 1000.0), "high_1000_to_3000": (1000.0, 3000.0)}


def effective_b_table() -> dict[tuple[str, int], float]:
    import csv

    table = {}
    with open(OUT / "oct12_effective_b.csv", newline="") as f:
        for row in csv.DictReader(f):
            if row["echo"] == "1" and row["source"] == "model":
                table[(row["scan"], int(row["volume"]) - 1)] = float(row["trace_s_mm2"])
    return table


def fse_scan(key: str, beff: dict[tuple[str, int], float], ref_img: np.ndarray,
             sample: str = "in_vivo") -> dict:
    s = load(key)
    sl = centre_index(s["offsets_mm"])
    shift = shift_to(ref_img, s["img"][0, sl])
    mask_names = (MASK_KEY,) if sample == "in_vivo" else ("ex_brain", "ex_pbs")
    masks = {name: move(M[name], shift) for name in mask_names}
    noise_cols = NOISE_COLS_IV if sample == "in_vivo" else NOISE_COLS_EX
    images, sigmas, nominal, effective, dirs = [], [], [], [], []
    for v in range(s["E"]):
        im = s["img"][v, sl]
        images.append(im)
        sigmas.append(sigma_of(im, noise_cols))
        nominal.append(float(s["b"][v]))
        effective.append(beff[(key, v)])
        dirs.append(direction_label(s["vec"][v]) if s["b"][v] > 10 else "0")
    return dict(key=key, images=np.asarray(images), sigmas=np.asarray(sigmas), nominal=np.asarray(nominal),
                effective=np.asarray(effective), dirs=dirs, masks=masks, shift=shift,
                slice_mm=float(s["offsets_mm"][sl]), b_source="source-model echo-1 effective b trace", sample=sample)


def epi_scan(key: str, ref_img: np.ndarray, sample: str = "in_vivo") -> dict:
    e = load_epi(key)
    sl = centre_index(e["offsets_mm"])
    shift = shift_to(ref_img, e["img"][0, sl])
    mask_names = (MASK_KEY,) if sample == "in_vivo" else ("ex_brain", "ex_pbs")
    masks = {name: move(M[name], shift) for name in mask_names}
    noise_cols = np.r_[2:16, 152:166] if sample == "in_vivo" else np.r_[152:166]
    sigmas = [float(np.sqrt(np.mean(e["mag"][v, sl][4:124, noise_cols] ** 2) / 2)) for v in range(e["E"])]
    dirs = [direction_label(e["vec"][v]) if e["b"][v] > 0 else "0" for v in range(e["E"])]
    return dict(key=key, images=np.asarray(e["img"][:, sl]), sigmas=np.asarray(sigmas), nominal=np.asarray(e["b"], float),
                effective=np.asarray(e["b"], float), dirs=dirs, masks=masks, shift=shift,
                slice_mm=float(e["offsets_mm"][sl]), b_source="typed EPI b-values", sample=sample)


def select_vol(scan: dict, b: float, direction: str | None = None) -> int:
    matches = [i for i, value in enumerate(scan["nominal"]) if np.isclose(value, b)
               and (direction is None or scan["dirs"][i] == direction)]
    if len(matches) != 1:
        raise ValueError(f"{scan['key']}: expected one b={b:g}, direction={direction}; got {matches}")
    return matches[0]


def make_maps(scan: dict, roi_key: str) -> dict[str, dict]:
    out = {}
    brain = scan["masks"][roi_key]
    for label, (b0, b1) in INTERVALS.items():
        baseline_b = (0.0 if scan["key"] == EPI_KEY else 10.0) if b0 is None else b0
        direction_maps, direction_masks = [], []
        endpoint_idxs = []
        for direction in DIRECTIONS:
            if label == "low_baseline_to_1000":
                # The low-b baseline is the acquired b10 volume (along +x); the 1000
                # endpoint is selected direction by direction.
                v0 = select_vol(scan, baseline_b)
            else:
                v0 = select_vol(scan, b0, direction)
            v1 = select_vol(scan, b1, direction)
            I0, I1 = scan["images"][v0], scan["images"][v1]
            s0, s1 = scan["sigmas"][v0], scan["sigmas"][v1]
            b_eff0, b_eff1 = scan["effective"][v0], scan["effective"][v1]
            if b_eff1 <= b_eff0:
                raise ValueError(f"{scan['key']} {label} {direction}: non-positive effective b difference")
            passed = brain & (I0 >= THRESHOLD_SIGMA * s0) & (I1 >= THRESHOLD_SIGMA * s1)
            adc = np.full(I0.shape, np.nan, dtype=float)
            # Raw magnitudes are used directly; no Rician/noise-floor correction.
            adc[passed] = np.log(I0[passed] / I1[passed]) / (b_eff1 - b_eff0)
            direction_maps.append(adc)
            direction_masks.append(passed)
            endpoint_idxs.extend([v0, v1])
        valid = np.logical_and.reduce(direction_masks)
        stack = np.stack(direction_maps)
        # Arithmetic mean of the three direction-wise voxel log slopes.
        mean = np.full(brain.shape, np.nan, dtype=float)
        mean[valid] = np.mean(stack[:, valid], axis=0)
        out[label] = dict(map=mean, valid=valid, coverage=float(valid.sum() / brain.sum()),
                          covered_pixels=int(valid.sum()), brain_pixels=int(brain.sum()),
                          endpoint_volumes=sorted(set(endpoint_idxs)), interval=(baseline_b, b1))
    return out


def crop_box(masks: list[np.ndarray], margin: int = 10) -> tuple[int, int, int, int]:
    union = np.logical_or.reduce(masks)
    rr, cc = np.where(union)
    r0, r1 = max(0, int(rr.min()) - margin), min(union.shape[0], int(rr.max()) + margin + 1)
    c0, c1 = max(0, int(cc.min()) - margin), min(union.shape[1], int(cc.max()) + margin + 1)
    return r0, r1, c0, c1


def add_map_panel(ax, result: dict, mask: np.ndarray, crop: tuple[int, int, int, int], title: str,
                  vmin: float = 0.0, vmax: float = 2.0):
    # White outside the physical ROI; light gray inside the ROI where the 5*sigma
    # rule censored a voxel; colored where the voxel passed.
    panel = np.full(mask.shape, -1.0, dtype=float)
    panel[mask] = np.nan
    panel[result["valid"]] = result["map"][result["valid"]] * 1e3
    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad("#c9c9c9")
    cmap.set_under("white")
    im = ax.imshow(panel, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest", origin="upper")
    r0, r1, c0, c1 = crop
    ax.set_xlim(c0 - 0.5, c1 - 0.5)
    ax.set_ylim(r1 - 0.5, r0 - 0.5)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(title, fontsize=10, pad=5)
    return im


def save_invivo_figure(scans: dict, maps: dict, outpath: Path) -> None:
    keys = ("iA", "iB", "EPI-invivoA")
    crop = crop_box([scans[k]["masks"][MASK_KEY] for k in keys], margin=10)
    labels = {"iA": "v1.83", "iB": "v1.912", "EPI-invivoA": "EPI"}
    fig, axes = plt.subplots(2, 3, figsize=(11.0, 6.3), constrained_layout=True)
    image = None
    for col, key in enumerate(keys):
        for row, interval in enumerate(INTERVALS):
            result = maps[key][interval]
            title = f"{labels[key]} · {result['coverage']:.0%} retained"
            image = add_map_panel(axes[row, col], result, scans[key]["masks"][MASK_KEY], crop, title)
            if col == 0:
                axes[row, col].set_ylabel("baseline→1000" if row == 0 else "1000→3000", fontsize=10)
    fig.colorbar(image, ax=axes, shrink=0.84, label="ADC (10⁻³ mm²/s)")
    fig.suptitle("In-vivo centre-slice ADC", fontsize=14)
    fig.text(0.5, -0.012,
             "Mean of x/y/z voxel log slopes; raw magnitude, unsmoothed. FSE uses source-model effective b; EPI uses typed b. "
             "Gray = inside whole-brain ROI but censored (<5σ endpoint); white = outside ROI. Coverage is QC retention, not an unbiased estimator.",
             ha="center", fontsize=8.5)
    fig.savefig(outpath, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_exvivo_figure(scans: dict, maps: dict, outpath: Path) -> None:
    cols = (("Q", "ex_brain", "Q · brain"), ("Q", "ex_pbs", "Q · free PBS"),
            ("R", "ex_brain", "R · brain"), ("R", "ex_pbs", "R · free PBS"))
    crop = crop_box([scans[k]["masks"][roi] for k, roi, _ in cols], margin=10)
    fig, axes = plt.subplots(2, 4, figsize=(14.4, 6.4), constrained_layout=True)
    image = None
    for col, (key, roi, label) in enumerate(cols):
        for row, interval in enumerate(INTERVALS):
            result = maps[key][roi][interval]
            image = add_map_panel(axes[row, col], result, scans[key]["masks"][roi], crop,
                                  f"{label} · {result['coverage']:.0%} retained")
            if col == 0:
                axes[row, col].set_ylabel("b10→1000" if row == 0 else "1000→3000", fontsize=10)
    fig.colorbar(image, ax=axes, shrink=0.84, label="ADC (10⁻³ mm²/s)")
    fig.suptitle("Ex-vivo centre-slice ADC · brain and free PBS", fontsize=14)
    fig.text(0.5, -0.012,
             "Mean of x/y/z voxel log slopes; raw magnitude, unsmoothed. Q/R use source-model effective b. "
             "Gray = inside ROI but censored (<5σ endpoint); white = outside ROI. Coverage is QC retention only. "
             "EPI test0 lacks a complete 3-direction b1000 shell and b3000.",
             ha="center", fontsize=8.5)
    fig.savefig(outpath, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_exvivo_slide_figures(scans: dict, maps: dict, brain_path: Path, pbs_path: Path) -> None:
    brain_cols = ("Q", "R")
    brain_crop = crop_box([scans[k]["masks"]["ex_brain"] for k in brain_cols], margin=10)
    fig, axes = plt.subplots(2, 2, figsize=(7.4, 5.6), constrained_layout=True)
    image = None
    for col, key in enumerate(brain_cols):
        for row, interval in enumerate(INTERVALS):
            result = maps[key]["ex_brain"][interval]
            image = add_map_panel(axes[row, col], result, scans[key]["masks"]["ex_brain"], brain_crop,
                                  f"{key} · {result['coverage']:.0%} retained", vmax=0.6)
            if col == 0:
                axes[row, col].set_ylabel("b10→1000" if row == 0 else "1000→3000", fontsize=9)
    fig.colorbar(image, ax=axes, shrink=0.82, label="ADC (10⁻³ mm²/s)")
    fig.suptitle("Ex-vivo brain ADC · centre slice", fontsize=13)
    fig.text(0.5, -0.012, "Mean x/y/z raw-magnitude log slopes; source-model effective b; unsmoothed. Gray = censored below 5σ.",
             ha="center", fontsize=8)
    fig.savefig(brain_path, dpi=230, bbox_inches="tight")
    plt.close(fig)

    pbs_cols = ("Q", "R")
    pbs_crop = crop_box([scans[k]["masks"]["ex_pbs"] for k in pbs_cols], margin=10)
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.7), constrained_layout=True)
    image = None
    for col, key in enumerate(pbs_cols):
        result = maps[key]["ex_pbs"]["low_baseline_to_1000"]
        image = add_map_panel(axes[col], result, scans[key]["masks"]["ex_pbs"], pbs_crop,
                              f"{key} · {result['coverage']:.0%} retained", vmax=2.5)
        axes[col].set_xlabel("b10→1000", fontsize=9)
    fig.colorbar(image, ax=axes, shrink=0.86, label="ADC (10⁻³ mm²/s)")
    fig.suptitle("Ex-vivo free PBS ADC · centre slice", fontsize=13)
    fig.text(0.5, -0.02, "Mean x/y/z raw-magnitude log slopes; source-model effective b; unsmoothed. "
             "High interval: 0% retained in both scans at 5σ.", ha="center", fontsize=8)
    fig.savefig(pbs_path, dpi=230, bbox_inches="tight")
    plt.close(fig)


def main() -> dict:
    beff = effective_b_table()
    ref = load("iA")
    ref_img = ref["img"][0, centre_index(ref["offsets_mm"])]
    exref = load("Q")
    ex_ref_img = exref["img"][0, centre_index(exref["offsets_mm"])]
    scans = {key: fse_scan(key, beff, ref_img) for key in ("iA", "iB")}
    scans["EPI-invivoA"] = epi_scan(EPI_KEY, ref_img)
    scans.update({key: fse_scan(key, beff, ex_ref_img, "ex_vivo") for key in ("Q", "R")})
    scans["EPI-test0"] = epi_scan("epi0", ex_ref_img, "ex_vivo")
    iv_maps = {key: make_maps(scans[key], MASK_KEY) for key in ("iA", "iB", "EPI-invivoA")}
    ex_maps = {key: {roi: make_maps(scans[key], roi) for roi in ("ex_brain", "ex_pbs")}
               for key in ("Q", "R")}
    save_invivo_figure(scans, iv_maps, FIGDIR / "slide_adc_invivo.png")
    save_exvivo_figure(scans, ex_maps, FIGDIR / "adc_quality_maps_exvivo_full.png")
    save_exvivo_slide_figures(scans, ex_maps, FIGDIR / "slide_adc_exvivo_brain.png",
                              FIGDIR / "slide_adc_exvivo_pbs.png")
    # Keep the original figure name as the in-vivo comparison for existing references.
    save_invivo_figure(scans, iv_maps, FIGDIR / "adc_quality_maps.png")

    labels = {
        "iA": "v1.83 FSE effective b",
        "iB": "v1.912 FSE effective b",
        "EPI-invivoA": "EPI typed b",
        "Q": "v1.83 FSE effective b",
        "R": "v1.912 FSE effective b",
        "EPI-test0": "EPI typed b",
    }

    result_json = {
        "status": "descriptive quality-masked maps; not a tissue-segmented or unbiased ADC estimator",
        "map": "arithmetic mean of +x, +y, +z voxelwise two-point log slopes; unsmoothed",
        "magnitude": "raw magnitude, no noise-floor correction",
        "mask": "existing central physical ROI intersected with all interval endpoints >= 5*sigma",
        "coverage_definition": "passing pixels / pixels in the translated original whole-brain ROI; QC censor fraction only",
        "sigma_method": {
            "FSE": "sqrt(mean(I^2)/2) on centre-slice readout-side background columns 2:14 and 115:127, rows 4:123",
            "EPI": "same Rayleigh estimate on native 168-column centre-slice magnitude, columns 2:15 and 152:165, rows 4:123",
        },
        "b_values": {
            "FSE": "source-model echo-1 effective b trace from oct12_effective_b.csv; low-b reference is acquired +x volume; directional b shells are matched by axis",
            "EPI": "typed b-values",
        },
        "intervals": {k: ("baseline" if v[0] is None else v[0], v[1]) for k, v in INTERVALS.items()},
        "threshold_sigma": THRESHOLD_SIGMA,
        "scans": {
            key: {
                "display_label": labels[key], "sample": scan["sample"], "slice_mm": scan["slice_mm"], "mask_shift_row_col": list(scan["shift"]),
                "sigma_by_volume": [float(x) for x in scan["sigmas"]], "nominal_b_by_volume": [float(x) for x in scan["nominal"]],
                "effective_b_by_volume": [float(x) for x in scan["effective"]], "direction_by_volume": scan["dirs"],
                "b_source": scan["b_source"],
                "rois": ({MASK_KEY: {name: {"coverage_fraction": iv_maps[key][name]["coverage"],
                                           "covered_pixels": iv_maps[key][name]["covered_pixels"],
                                           "roi_pixels": iv_maps[key][name]["brain_pixels"],
                                           "endpoint_volumes_zero_based": iv_maps[key][name]["endpoint_volumes"],
                                           "adc_valid_median_10-3_mm2_s": (float(np.nanmedian(iv_maps[key][name]["map"]) * 1e3) if iv_maps[key][name]["valid"].any() else None),
                                           "adc_valid_p10_p90_10-3_mm2_s": ([float(x * 1e3) for x in np.nanpercentile(iv_maps[key][name]["map"], [10, 90])] if iv_maps[key][name]["valid"].any() else None),
                                           "adc_map_10-3_mm2_s": np.where(np.isfinite(iv_maps[key][name]["map"]), iv_maps[key][name]["map"] * 1e3, None).tolist()}
                                  for name in INTERVALS}}
                           if key in iv_maps else
                           {roi: {name: {"coverage_fraction": ex_maps[key][roi][name]["coverage"],
                                         "covered_pixels": ex_maps[key][roi][name]["covered_pixels"],
                                         "roi_pixels": ex_maps[key][roi][name]["brain_pixels"],
                                         "endpoint_volumes_zero_based": ex_maps[key][roi][name]["endpoint_volumes"],
                                         "adc_valid_median_10-3_mm2_s": (float(np.nanmedian(ex_maps[key][roi][name]["map"]) * 1e3) if ex_maps[key][roi][name]["valid"].any() else None),
                                         "adc_valid_p10_p90_10-3_mm2_s": ([float(x * 1e3) for x in np.nanpercentile(ex_maps[key][roi][name]["map"], [10, 90])] if ex_maps[key][roi][name]["valid"].any() else None),
                                         "adc_map_10-3_mm2_s": np.where(np.isfinite(ex_maps[key][roi][name]["map"]), ex_maps[key][roi][name]["map"] * 1e3, None).tolist()}
                                for name in INTERVALS} for roi in ("ex_brain", "ex_pbs")} if key in ex_maps else
                           {"unavailable": {"reason": "EPI test0 acquired b0, b1000 +y, and b6000 +z only; no full 3-direction shell and no b3000, so neither requested arithmetic-mean interval is computable."}}),
            } for key, scan in scans.items()
        },
        "figures": {"in_vivo": "docs/figures/physical_scanner_2026-10-12/slide_adc_invivo.png",
                    "ex_vivo_report": "docs/figures/physical_scanner_2026-10-12/adc_quality_maps_exvivo_full.png",
                    "ex_vivo_brain_slide": "docs/figures/physical_scanner_2026-10-12/slide_adc_exvivo_brain.png",
                    "ex_vivo_pbs_slide": "docs/figures/physical_scanner_2026-10-12/slide_adc_exvivo_pbs.png"},
    }
    (OUT / "oct12_adc_quality.json").write_text(json.dumps(result_json, indent=1, allow_nan=False))
    print(json.dumps({"in_vivo": {k: {n: round(v["coverage"], 4) for n, v in m.items()} for k, m in iv_maps.items()},
                      "ex_vivo": {k: {roi: {n: round(v["coverage"], 4) for n, v in m.items()} for roi, m in r.items()}
                                  for k, r in ex_maps.items()},
                      "EPI-test0": "unavailable: no b3000 and only b1000 +y"}, indent=1))
    return result_json


if __name__ == "__main__":
    main()
