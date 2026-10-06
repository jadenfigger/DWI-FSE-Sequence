"""Reproduce the conditional Oct. 5 crusher-area audit from MRD-embedded PPRs.

The checked-in scanner implementation is v1.7. Oct. 5 acquisition PPRs name
v1.8, whose PPL source is absent from this checkout. Therefore all played
amplitudes below are conditional on the v1.7 schedule rules matching v1.8.
Areas are commanded ideal trapezoid areas; no hardware trace is available.
"""
from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "docs" / "data"
FIG = ROOT / "docs" / "figures" / "physical_scanner_2026-10-05"
GAMMA_HZ_T = 42.57747892e6


def embedded_protocol(path: Path) -> str:
    raw = path.read_bytes().decode("latin-1", errors="ignore")
    pos = raw.find(":PPL")
    if pos < 0:
        raise ValueError(f"MRD has no embedded PPR section: {path}")
    return raw[pos:]


def vars_from_ppr(text: str) -> tuple[dict[str, str], dict[str, list[int]]]:
    # Scanner PPRs serialize both editable :VAR values and named controls such
    # as :VIEWS_PER_SEGMENT as `directive variable, value` records.
    scalars = {m.group(1): m.group(2) for m in re.finditer(
        r"(?m)^:(?!VAR_ARRAY\b)[A-Z0-9_]+\s+(\w+)\s*,\s*(-?\d+)(?:\s*,|\s*$)", text)}
    arrays: dict[str, list[int]] = {}
    for m in re.finditer(
        r"(?m)^:VAR_ARRAY\s+(\w+)\s*,\s*(\d+)\s*,\s*([^\r\n]*(?:\r?\n,[^\r\n]*)*)",
        text,
    ):
        vals = [int(x) for x in re.findall(r"-?\d+", m.group(3))]
        arrays[m.group(1)] = vals[: int(m.group(2))]
    return scalars, arrays


def num(v: dict[str, str], key: str, default: int = 0) -> int:
    return int(float(v.get(key, default)))


def round_half_up(n: int, d: int) -> int:
    return (n + d // 2) // d


def schedule(v: dict[str, str], arrays: dict[str, list[int]]) -> list[int]:
    etl = num(v, "views_per_seg")
    base_train, base_first = num(v, "crush_amp"), num(v, "diff_crush_amp")
    mode, step = num(v, "crusher_schedule"), num(v, "crusher_step_pct")
    out = []
    custom = arrays.get("crusher_custom_pct", [])
    for i in range(etl):
        base = base_first if i == 0 and num(v, "diff_on", 1) == 1 else base_train
        sign = -1 if base < 0 else 1
        mag = abs(base)
        factor = 100
        if i >= 1 and mode in (1, 3):
            steps = i - 1
            factor = 100 + steps * step
        elif i >= 1 and mode == 4:
            steps = etl - i - 1
            factor = 100 + steps * step
        if mode == 5:
            if i >= len(custom):
                raise ValueError("custom table shorter than ETL")
            factor = custom[i]
            if factor < 0:
                factor, sign = -factor, -sign
        if mode in (2, 3) and i % 2 == 1:
            sign = -sign
        out.append(sign * round_half_up(mag * factor, 100))
    return out


def scan_records():
    rows, excluded = [], []
    for folder in sorted((ROOT / "experiments").glob("FSE-DWI_10-05-*")):
        mrds = list(folder.glob("*.MRD"))
        if not mrds:
            continue
        mrd = mrds[0]
        text = embedded_protocol(mrd)
        v, a = vars_from_ppr(text)
        ppl = re.search(r"(?m)^:PPL\s+([^\r\n]+)", text).group(1).strip()
        if "twoTE-1.8" not in ppl:
            excluded.append({"scan": folder.name.rsplit("_", 1)[-1],
                             "mrd": str(mrd.relative_to(ROOT)),
                             "reason": f"Embedded protocol names {ppl}; v1.3 legacy crusher is coupled and has no independent signed crusher table."})
            continue
        scan = folder.name.rsplit("_", 1)[-1]
        etl = num(v, "views_per_seg")
        amp = schedule(v, a)
        ramp, flat_train = num(v, "tramp"), num(v, "tcrush")
        flat_first = num(v, "diff_tcrush", flat_train) if num(v, "diff_on", 1) else flat_train
        # v1.7 POSPULSE_SEC trapezoids have ramps of tramp on both sides:
        # integral = signed DAC * (flat + tramp), in DAC-us.
        for i, dac in enumerate(amp):
            flat = flat_first if i == 0 and num(v, "diff_on", 1) else flat_train
            lobe = dac * (flat + ramp)
            rows.append({
                "scan": scan, "folder": folder.name, "mrd": str(mrd.relative_to(ROOT)),
                "ppl": ppl,
                "etl": etl, "pe_order": num(v, "PE_order"),
                "schedule_code": num(v, "crusher_schedule"),
                "step_pct": num(v, "crusher_step_pct"),
                "base_first_dac": num(v, "diff_crush_amp"),
                "base_train_dac": num(v, "crush_amp"),
                "tramp_us": ramp, "flat_first_us": flat_first,
                "flat_train_us": flat_train, "pulse": i + 1, "crusher_dac": dac,
                "lobe_area_dac_us": lobe, "lobe_abs_area_dac_us": abs(lobe),
                "pair_commanded_area_dac_us": 2 * lobe,
                "pair_abs_area_dac_us": 2 * abs(lobe),
                # The intended primary transverse coherence changes sign at RF.
                "primary_pathway_signed_net_dac_us": 0,
                "grad_var0_hz_per_mm": _gradvar0(text),
                "lobe_area_nominal_T_s_per_m": (
                    lobe * _gradvar0(text) / 32767 * 1e-3 / GAMMA_HZ_T
                ),
                "notes": "conditional_v1.7; commanded ideal trapezoid",
            })
    return rows, excluded


def _gradvar0(text: str) -> int:
    m = re.search(r"(?m)^:GRADIENT_STRENGTH\s+grad_var\s*,\s*\d+\s*,\s*(-?\d+)", text)
    return int(m.group(1)) if m else 0


def write_outputs(rows, excluded):
    DATA.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    per_echo_path = DATA / "oct05_crusher_echo_areas.csv"
    grouped: dict[str, list[dict]] = {}
    for r in rows:
        grouped.setdefault(r["scan"], []).append(r)
    for rr in grouped.values():
        signed_cum = absolute_cum = 0
        for x in rr:
            signed_cum += x["lobe_area_dac_us"]
            absolute_cum += x["lobe_abs_area_dac_us"]
            x["cumulative_lobe_signed_area_dac_us"] = signed_cum
            x["cumulative_lobe_absolute_area_dac_us"] = absolute_cum
            x["cumulative_pair_signed_area_dac_us"] = 2 * signed_cum
            x["cumulative_pair_absolute_area_dac_us"] = 2 * absolute_cum
    with per_echo_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    summary = []
    for scan, rr in grouped.items():
        signed = sum(x["lobe_area_dac_us"] for x in rr)
        absolute = sum(x["lobe_abs_area_dac_us"] for x in rr)
        # Two equal-polarity lobes per RF; report both commanded and primary
        # refocusing-sign-weighted signed sums.
        summary.append({
            "scan": scan, "mrd": rr[0]["mrd"], "ppl": rr[0]["ppl"],
            "etl": rr[0]["etl"], "pe_order": rr[0]["pe_order"],
            "schedule_code": rr[0]["schedule_code"], "step_pct": rr[0]["step_pct"],
            "tramp_us": rr[0]["tramp_us"], "flat_first_us": rr[0]["flat_first_us"],
            "flat_train_us": rr[0]["flat_train_us"],
            "crusher_dac_by_pulse": ";".join(str(x["crusher_dac"]) for x in rr),
            "lobe_signed_area_cumulative_dac_us": signed,
            "lobe_absolute_area_cumulative_dac_us": absolute,
            "pair_signed_area_cumulative_dac_us": 2 * signed,
            "pair_absolute_area_cumulative_dac_us": 2 * absolute,
            "primary_pathway_net_pair_area_dac_us": 0,
            "max_abs_lobe_area_dac_us": max(x["lobe_abs_area_dac_us"] for x in rr),
            "nominal_pair_abs_area_T_s_per_m": sum(2 * abs(x["lobe_area_nominal_T_s_per_m"]) for x in rr),
            "conditional_on_v1.7": True,
        })
    with (DATA / "oct05_crusher_train_areas.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0]))
        w.writeheader(); w.writerows(summary)
    (DATA / "oct05_crusher_area.json").write_text(json.dumps({
        "source": "Oct. 5 MRD-embedded PPR sections",
        "implementation_condition": "All Oct. 5 v1.8 acquisitions are modeled using the checked-in v1.7 PPL because v1.8 source is absent.",
        "area_formula": "For one POSPULSE_SEC trapezoid: signed DAC * (flat_us + ramp_us); pair has two same-sign commanded lobes. Intended primary pathway RF-sign-weighted net within the pair is zero for equal lobes.",
        "units": {"primary": "DAC-us; nominal T*s/m only by embedded grad_var[0] calibration convention and proton gamma"},
        "limitations": ["commanded ideal trapezoids; no scanner waveform readback", "v1.8 implementation equivalence unverified", "PPR gradient calibration is not an independent field probe", "physical axis orientation/gradient response and timing lag are not measured"],
        "excluded_scans": excluded,
        "summary": summary,
    }, indent=2), encoding="utf-8")

    # One plot shows each schedule's commanded per-lobe signed area. Keeping
    # scan labels in catalog order exposes exact sign-reversed and equal-area runs.
    scans = [x["scan"] for x in summary]
    matrix = np.full((max(x["etl"] for x in summary), len(summary)), np.nan)
    for j, scan in enumerate(scans):
        for r in grouped[scan]:
            matrix[r["pulse"] - 1, j] = r["lobe_area_dac_us"] / 1e6
    fig, ax = plt.subplots(figsize=(13, 6.4), constrained_layout=True)
    lim = float(np.nanmax(np.abs(matrix)))
    im = ax.imshow(matrix, aspect="auto", cmap="coolwarm", vmin=-lim, vmax=lim, interpolation="nearest")
    ax.set_xticks(range(len(scans)), scans, rotation=55, ha="right")
    ax.set_yticks(range(matrix.shape[0]), [f"RF {k}" for k in range(1, matrix.shape[0]+1)])
    ax.set_title("Oct. 5 commanded crusher area per lobe (conditional v1.7 model)")
    ax.set_xlabel("Scan; area shown in 10⁶ DAC·µs")
    cb = fig.colorbar(im, ax=ax); cb.set_label("Signed lobe area (10⁶ DAC·µs)")
    fig.savefig(FIG / "crusher_signed_lobe_areas.png", dpi=180)
    plt.close(fig)

    cum_signed = np.full_like(matrix, np.nan)
    cum_abs = np.full_like(matrix, np.nan)
    for j, scan in enumerate(scans):
        for r in grouped[scan]:
            i = r["pulse"] - 1
            cum_signed[i, j] = r["cumulative_lobe_signed_area_dac_us"] / 1e6
            cum_abs[i, j] = r["cumulative_lobe_absolute_area_dac_us"] / 1e6
    lim = float(np.nanmax(np.abs(cum_signed)))
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.2), constrained_layout=True)
    im0 = axes[0].imshow(cum_signed, aspect="auto", cmap="coolwarm", vmin=-lim, vmax=lim, interpolation="nearest")
    im1 = axes[1].imshow(cum_abs, aspect="auto", cmap="viridis", vmin=0, vmax=float(np.nanmax(cum_abs)), interpolation="nearest")
    for a in axes:
        a.set_xticks(range(len(scans)), scans, rotation=55, ha="right")
        a.set_yticks(range(matrix.shape[0]), [f"RF {k}" for k in range(1, matrix.shape[0]+1)])
        a.set_xlabel("Scan")
    axes[0].set_title("Cumulative signed lobe area")
    axes[1].set_title("Cumulative absolute lobe area")
    axes[0].set_ylabel("Through RF pulse")
    fig.colorbar(im0, ax=axes[0], label="10⁶ DAC·µs")
    fig.colorbar(im1, ax=axes[1], label="10⁶ DAC·µs")
    fig.suptitle("Crusher area accumulated through the echo train (conditional v1.7 model)")
    fig.savefig(FIG / "crusher_cumulative_by_echo.png", dpi=180)
    plt.close(fig)

    # Matched-area comparison focuses on absolute train area against signed train area.
    fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)
    x = np.arange(len(summary))
    s = np.array([z["lobe_signed_area_cumulative_dac_us"] for z in summary]) / 1e6
    a = np.array([z["lobe_absolute_area_cumulative_dac_us"] for z in summary]) / 1e6
    ax.bar(x - .2, s, width=.4, label="signed sum")
    ax.bar(x + .2, a, width=.4, label="absolute sum")
    ax.axhline(0, color="black", linewidth=.7)
    ax.set_xticks(x, scans, rotation=55, ha="right")
    ax.set_ylabel("Cumulative one-lobe area (10⁶ DAC·µs)")
    ax.set_title("Signed cancellation versus total absolute crusher area")
    ax.legend()
    fig.savefig(FIG / "crusher_cumulative_area.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    records, excluded = scan_records()
    if not records:
        raise SystemExit("No Oct. 5 MRDs found")
    write_outputs(records, excluded)
    print(f"Wrote {len(records)} echo-pair rows across {len({x['scan'] for x in records})} scans")
