"""Proportionate event-model gates for the v1.82 and v1.912 candidates.

This maps the final PPL/PPR bytes through ``dwfse.ppl``. It checks dwell-driven
ESP bounds, echo placement, fused-lobe areas, timers, slice selection/phase,
and navigator layouts. It does not certify vendor compilation or scanner RF
performance. Generated case PPRs and JSON results live in docs/v182_v1912/.
"""
from __future__ import annotations

import hashlib
import argparse
import json
import math
import re
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dwfse.ppl.run import map_events  # noqa: E402
from dwfse.ppl.events import rf_pulses  # noqa: E402
from dwfse.ppl.ledger import (build_ledger, adc_middle_times, dac_us_to_cyc_m,
                              list_starts, list_duration_us)  # noqa: E402
from dwfse.ppl.phase import rf_centre_phase_deg, circular_difference_deg  # noqa: E402
from dwfse.ppl.ppr import read_ppr  # noqa: E402
from examples import validate_v181_v1911 as prior  # noqa: E402
from examples import v19_validate_events as old  # noqa: E402

SC = ROOT / "scanner"
DOCS = ROOT / "docs/v182_v1912"
PPRS = DOCS / "test_pprs"
OUT = DOCS / "validation"
V182_CONTROL = OUT / "v182_items2to4_control.ppl"
V182_CONTROL_REPORT = OUT / "v182_nav_identity.json"
SOURCES = {
    "v181": SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl",
    "v182": SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.82.ppl",
    "v1911": SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl",
    "v1912": SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.912.ppl",
}
SEEDS = {
    "v181": ROOT / "experiments/FSE-DWI_10-10-2026_v181_testK/FSE-DWI_10-10-2026_v181_testK.ppr",
    "v182": ROOT / "experiments/FSE-DWI_10-10-2026_v181_testK/FSE-DWI_10-10-2026_v181_testK.ppr",
    "v1911": ROOT / "experiments/FSE-DWI_10-10-2026_v1911_testB/FSE-DWI_10-10-2026_v1911_testB.ppr",
    "v1912": ROOT / "experiments/FSE-DWI_10-10-2026_v1911_testB/FSE-DWI_10-10-2026_v1911_testB.ppr",
}
PPL_NAMES = {"v181": "1.81", "v182": "1.82", "v1911": "1.911", "v1912": "1.912"}
MODELS = old.COST_MODELS
NOMINAL = old.NOMINAL
TOL = {"echo_midpoint_us": 25.0, "fused_boundary_area_rel": 1e-4,
       "rf_effective_phase_deg": 3.0}
IMAGING = {"no_disacq": 0, "nav_on": 0, "no_views": 128}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    return str(value)


def save(name: str, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, default=json_default) + "\n", encoding="utf-8")


def set_record(lines, name, value):
    found = [i for i, line in enumerate(lines) if re.match(rf":[A-Z_]+\s+{re.escape(name)}\s*,", line, re.I)]
    if len(found) != 1:
        raise ValueError(f"expected one PPR record for {name}, got {len(found)}")
    i = found[0]
    parts = lines[i].split(",")
    parts[1] = f" {value}"
    lines[i] = ",".join(parts)


def set_array(lines, name, values):
    found = [i for i, line in enumerate(lines) if re.match(rf":(?:VAR_ARRAY|FOV_SLICE_OFF)\s+{re.escape(name)}\s*,", line, re.I)]
    if len(found) != 1:
        raise ValueError(f"expected one PPR array for {name}, got {len(found)}")
    i = found[0]
    head = lines[i].split(",")
    old_n = int(head[1])
    vals = list(values)
    record_type, record_name = head[0].split()
    n = len(vals) if record_type.upper() == ":FOV_SLICE_OFF" else old_n
    if len(vals) > n:
        raise ValueError(f"{name} has {n} cells, cannot write {len(vals)}")
    vals.extend([0] * (n - len(vals)))
    end = i + 1
    while end < len(lines) and lines[end].startswith(","):
        end += 1
    # Preserve the record's format while allowing slice arrays to grow/shrink.
    chunks = [f"{record_type} {record_name}, {n}, {vals[0]}"]
    rest = vals[1:]
    chunks.extend(", " + ", ".join(map(str, rest[k:k + 8])) for k in range(0, len(rest), 8))
    lines[i:end] = chunks


def make_ppr(label, name, *, dwell_us=None, edits=None, arrays=None):
    """Write a reproducible test PPR, preserving all acquired calibration fields."""
    seed = SEEDS[label]
    lines = seed.read_bytes().decode("latin-1").replace("\r\n", "\n").split("\n")
    lines[0] = f":PPL G:\\J_Figger\\FSE_dwi_CPMG_non_CPMG_twoTE-{PPL_NAMES[label]}.ppl"
    if dwell_us is not None:
        ticks = int(round(dwell_us * 10))
        set_record(lines, "sample_period", ticks)
    for key, value in (edits or {}).items():
        set_record(lines, key, value)
    for key, values in (arrays or {}).items():
        set_array(lines, key, values)
    path = PPRS / f"{name}.ppr"
    path.write_bytes("\r\n".join(lines).encode("latin-1"))
    return path


def map_case(label, ppr, *, overrides=None, shots=2, model=None):
    it = map_events(SOURCES[label], ppr, overrides=overrides or {}, max_shots=shots,
                    rf_latency_us=3.0, **(model or NOMINAL))
    return it


def rf_all(it):
    return [p for p in rf_pulses(it) if p.get("library")]


def printed_minimum(it, unit="ESP"):
    text = "\n".join(m for _, m in it.out)
    patterns = [rf"minimum\s+{unit}\s*(?:is|=|:)?\s*(\d+(?:\.\d+)?)\s*ms",
                rf"min(?:imum)?\s+{unit}\s*(?:is|=|:)?\s*(\d+(?:\.\d+)?)\s*ms",
                rf"{unit}\s*\(?(\d+(?:\.\d+)?)\s*ms\)?\s*(?:minimum|min)"]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return float(match.group(1))
    return None


def reject_summary(it):
    return [m.strip() for _, m in it.out if re.search(r"error E\d+|too short|minimum|invalid|reject|increase", m, re.I)]


def hazard_summary(it, ledger=None):
    h = prior.hazards(it, (ledger or build_ledger(it, 1))["issues"])
    return {"timer_overruns": h["timer_overruns"], "ignored_lists": h["ignored_lists"],
            "premature_matrix_use": h["premature_matrix_use"]}


def shot_ledgers(it):
    return prior.shot_ledgers(it)


def echo_metrics(it):
    _, shots = shot_ledgers(it)
    rows = []
    for shot in shots:
        structure = prior.structure(it, shot)
        mids = structure["ADC_minus_train_RF_midpoint_us"]
        rows.append({"shot": shot["shot"], "RF_count": len(shot["rf"]), "ADC_count": len(shot["adc"]),
                     "ESP_us": structure["train_RF_spacing_us"], "ADC_midpoint_error_us": mids,
                     "max_abs_midpoint_error_us": max((abs(x) for x in mids), default=None)})
    return rows


def min_esp_search(label, seed, dwell, *, lo=1, hi=40, model=NOMINAL):
    """Scan to the first accepted integer-ms ESP; upper timing limits are real."""
    ppr = make_ppr(label, f"search_{label}_{dwell}", dwell_us=dwell, edits={"esp": hi})
    minimum, at_min = None, None
    for esp in range(lo, hi + 1):
        trial = map_case(label, ppr, overrides={**IMAGING, "esp": esp}, shots=1, model=model)
        if trial.adc:
            minimum, at_min = esp, trial
            break
    if minimum is None:
        trial = map_case(label, ppr, overrides={**IMAGING, "esp": hi}, shots=1, model=model)
        return {"error": f"no accepted integer ESP from {lo} to {hi} ms",
                "messages_at_upper_bound": reject_summary(trial), "ppr_sha256": sha(ppr)}
    below_ppr = make_ppr(label, f"below_min_{label}_{dwell}", dwell_us=dwell,
                         edits={"esp": minimum - 1, "report_on": 1})
    below = map_case(label, below_ppr, overrides={**IMAGING, "esp": minimum - 1, "report_on": 1}, shots=1, model=model)
    return {"min_accepted_esp_ms": minimum, "one_ms_below_accepted": bool(below.adc),
            "rejection_messages_below": reject_summary(below),
            "printed_minimum_ms": printed_minimum(below), "below_boundary_ppr_sha256": sha(below_ppr),
            "ppr_sha256": sha(ppr), "cost_model": model}


def interval_area_rows(it):
    base, shots = shot_ledgers(it)
    shift = float(it.vars.get("rfdelay").value) if "rfdelay" in it.vars else 0.0
    return [{"shot": led["shot"], "rows": prior.interval_areas(it, led, shift)} for led in shots]


def full_event_signature(it):
    """Timing, RF carrier/phase, phase/frequency commands and gradient signature."""
    _, shots = shot_ledgers(it)
    events = shots[0]["rf"] if shots else rf_all(it)
    if not events:
        return None
    t0 = events[0]["t_center"]
    return {
        "rf": [(round(p["t_go"] - t0, 3), p["frame"], p["mul"], p["phase_units"],
                 p.get("tx_freq_hz"), p.get("tx_mhz")) for p in events],
        "adc": [(round(a["t_init"] - t0, 3), round(a["t_complete"] - t0, 3),
                 a["rx_phase_units"], a["Dummy_Cycles"]) for a in it.adc],
        "freq": [(round(e["t_us"] - t0, 3), e["kind"], e.get("buffer"), e.get("frequency_hz"),
                  e.get("mhz"), e.get("mode")) for e in it.frequency_events],
        "phase": [(round(e["t_us"] - t0, 3), e["kind"], e.get("phase_deg")) for e in it.phase_events],
        "grad": {axis: [(round(a - t0, 3) if a >= it.sync_t else "setup",
                         round(b - a, 3) if a < it.sync_t else round(b - t0, 3), p, s)
                        for a, b, p, s in it.grad.ch[axis].segments]
                 for axis in "SPR"},
    }


def navigator_pe_audit(it):
    """Check phase-axis k at the appended echo of every mapped shot.

    Also report the leading volume navigator's complete nine-line PE path
    separately, so its naturally zero moments cannot stand in for imaging
    shots' appended echoes.
    """
    _, shots = shot_ledgers(it)
    shift = float(it.vars["rfdelay"].value) if "rfdelay" in it.vars else 0.0
    shot_rows, volume_rows = [], []
    for led in shots:
        if not led["rf"] or not led["adc"]:
            continue
        selected = prior.selected_k(it, led, shift)
        adc_rows = [row for row in selected if str(row["at"]).startswith("ADC")]
        final = next((row for row in adc_rows if row["at"] == f"ADC{len(led['adc'])}"), None)
        k = final["selected"].get("k_cycles_m") if final else None
        adc_times = adc_middle_times(it, led)
        t0 = led["rf"][0]["t_center"]
        t_adc = adc_times[-1][1] if adc_times else t0
        p_wave = led["G"]["P"]
        active_p_us = 0.0
        for i, value in enumerate(p_wave.v):
            if abs(value) <= 1e-12:
                continue
            a, b = p_wave.t[i], p_wave.t[i + 1]
            active_p_us += max(0.0, min(b, t_adc) - max(a, t0))
        one_lsb_bound = dac_us_to_cyc_m(active_p_us, led["H"])
        shot_rows.append({"shot": led["shot"], "final_adc": f"ADC{len(led['adc'])}",
                          "PE_k_cycles_m": k[1] if k else None,
                          "active_P_us_before_final_ADC": active_p_us,
                          "one_DAC_LSB_over_active_P_us_bound_cycles_m": one_lsb_bound,
                          "selected_branch": final["selected"].get("branch") if final else None,
                          "zero_PE": bool(k is not None and abs(k[1]) <= 0.03)})
        if led is shots[0]:
            for row in adc_rows:
                moment = row["selected"].get("k_cycles_m")
                volume_rows.append({"adc": row["at"], "PE_k_cycles_m": moment[1] if moment else None,
                                    "zero_PE": bool(moment is not None and abs(moment[1]) <= 0.03)})
    all_final_zero = bool(shot_rows) and all(x["zero_PE"] for x in shot_rows)
    max_residual = max((abs(row["PE_k_cycles_m"]) for row in shot_rows
                        if row["PE_k_cycles_m"] is not None), default=None)
    max_quantization_bound = max((row["one_DAC_LSB_over_active_P_us_bound_cycles_m"]
                                  for row in shot_rows), default=0.0)
    return {"PE_zero_tolerance_cycles_m": 0.03,
            "max_abs_final_echo_PE_cycles_m": max_residual,
            "quantization_context": {
                "conservative_bound_definition": "one integer DAC LSB integrated over all active P-gradient time from first RF centre to final ADC centre; this is reported for context and is not used to accept a residual",
                "max_DAC_quantization_bound_cycles_m": max_quantization_bound},
            "shot_final_echoes": shot_rows,
            "all_imaging_final_echoes_zero_PE": all_final_zero,
            "volume_navigator_adc_moments": volume_rows,
            "volume_navigator_all_zero_PE": bool(volume_rows)
            and len(volume_rows) == len(shots[0]["adc"])
            and all(row["zero_PE"] for row in volume_rows) if shots else False,
            "all_zero_PE": all_final_zero}


def d_reference_area_cycles_m(it):
    base, shots = shot_ledgers(it)
    if not shots:
        return 0.0
    starts = [(t, axis) for t, axis in list_starts(it, shots[0], "v19_l_d") if axis == "S"]
    duration = list_duration_us(it, "v19_l_d")
    shift = float(it.vars["rfdelay"].value) if "rfdelay" in it.vars else 0.0
    values = [abs(dac_us_to_cyc_m(base["G"]["S"].integral(t - shift, t + duration - shift), base["H"]))
              for t, _ in starts]
    return max(values, default=0.0)


def compare_interval_areas(reference, candidate):
    a, b = interval_area_rows(reference), interval_area_rows(candidate)
    comp = []
    d_area = d_reference_area_cycles_m(reference)
    unmatched = []
    for ra, rb in zip(a, b):
        by_key = {(x["from"], x["to"]): x for x in rb["rows"]}
        for x in ra["rows"]:
            y = by_key.pop((x["from"], x["to"]), None)
            if y is None:
                unmatched.append({"shot": ra["shot"], "baseline_boundary": (x["from"], x["to"])})
                continue
            for axis in "SPR":
                av, bv = float(x[axis]), float(y[axis])
                delta = abs(bv - av)
                if axis == "S":
                    error = delta / max(d_area, 1e-12)
                    limit = TOL["fused_boundary_area_rel"]
                    unit = "fraction_of_D_area"
                else:
                    error = delta * 1e-3
                    limit = 2.5e-4
                    unit = "cycles_per_mm"
                comp.append({"shot": ra["shot"], "from": x["from"], "to": x["to"], "axis": axis,
                             "reference_cycles_m": av, "candidate_cycles_m": bv, "delta_cycles_m": delta,
                             "error": error, "error_unit": unit, "limit": limit, "pass": error <= limit})
        unmatched.extend({"shot": rb["shot"], "candidate_boundary": key} for key in by_key)
    all_ok = not unmatched and all(row["pass"] for row in comp)
    return {"comparisons": comp, "D_area_cycles_m": d_area,
            "max_slice_error_fraction_of_D": max((x["error"] for x in comp if x["axis"] == "S"), default=0.0),
            "max_other_axis_error_cycles_per_mm": max((x["error"] for x in comp if x["axis"] != "S"), default=0.0),
            "unmatched_boundaries": unmatched, "pass": all_ok}


def phase_rows(it, z_mm, reference_hz, origin_us):
    """Compute effective RF centre phase from mapper frequency/phase histories.

    The mapper must expose the commanded frequency and programmed-phase history,
    plus an accumulated centre-phase field for each RF. Missing instrumentation
    is reported as unvalidated; a nominal phase register value is not accepted as
    an effective phase measurement.
    """
    ledger, shots = shot_ledgers(it)
    events = [p for shot in shots for p in shot["rf"]] if shots else rf_all(it)
    lag = float(it.vars["rfdelay"].value) if "rfdelay" in it.vars else 0.0
    h_scale = float(it.vars["grad_var"].value[0]) if "grad_var" in it.vars else None
    origin = origin_us
    mhz = events[0].get("tx_mhz") if events else None
    rows = []
    shot_for_event = {id(p): shot["shot"] for shot in shots for p in shot["rf"]}
    for pulse in events:
        phase = rf_centre_phase_deg(it, pulse, origin, reference_hz, mhz=mhz)
        freq = pulse.get("tx_freq_hz")
        selected_dac = float(ledger["G"]["S"].value_at(pulse["t_center"] - lag))
        rows.append({"shot": shot_for_event.get(id(pulse)), "frame": pulse["frame"], "t_center_us": pulse["t_center"],
                     "z_mm": z_mm, "tx_freq_hz": freq,
                     "selection_gradient_DAC": selected_dac, "gradient_H_scale": h_scale,
                     "programmed_phase_deg": pulse.get("phase_deg"),
                     "effective_phase_center_deg": phase})
    # Slice-specific carrier changes can produce a common phase offset before
    # a shot's first RF centre. Preserve it for inspection but normalize each
    # shot to its own first RF centre for the echo-train phase comparison.
    shot_common = {}
    for row in rows:
        shot_common.setdefault(row["shot"], row["effective_phase_center_deg"])
    for row in rows:
        row["common_phase_deg"] = shot_common[row["shot"]]
        row["normalized_effective_phase_center_deg"] = circular_difference_deg(
            row["effective_phase_center_deg"], row["common_phase_deg"])
    known = bool(rows) and all(row["tx_freq_hz"] is not None for row in rows)
    return {"status": "source_model_integrated" if known else "mapper_frequency_history_unavailable",
            "phase_origin_us": origin, "reference_hz": reference_hz, "tx_mhz_bank": mhz,
            "rows": rows}


def centre_frequency_anchor(it):
    """Return last TX-buffer-6 delivery before the excitation centre."""
    _, shots = shot_ledgers(it)
    events = shots[0]["rf"] if shots else rf_all(it)
    if not events:
        return None, None, None
    first = events[0]
    mhz = first.get("tx_mhz")
    candidates = [row for row in it.frequency_events
                  if row.get("kind") == "send" and row.get("buffer") == 6
                  and row.get("mhz") == mhz and row.get("t_us", math.inf) <= first["t_center"]]
    if not candidates:
        return None, float(first.get("tx_freq_hz", 0.0)), mhz
    anchor = max(candidates, key=lambda row: row["t_us"])
    # Integrate the synthesizer offset from the centre-frequency anchor. The
    # first RF's selected-slice carrier is not the phase reference; returning
    # it here double-counts the slice offset accumulated before the first RF.
    return float(anchor["t_us"]), float(anchor.get("frequency_hz", 0.0)), mhz


def run(labels=("v182", "v1912")):
    PPRS.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    started = time.time()
    references = {"v182": "v181", "v1912": "v1911"}
    source_labels = sorted(set(labels) | {references[x] for x in labels})
    before = {name: {"ppl_sha256": sha(SOURCES[name]), "seed_ppr_sha256": sha(SEEDS[name])} for name in source_labels}
    control_report = json.loads(V182_CONTROL_REPORT.read_text(encoding="utf-8"))
    control_before = {"ppl_sha256": sha(V182_CONTROL), "report_sha256": sha(V182_CONTROL_REPORT)}
    control_cases = {(case["nav_on"], case["cost_model"]): case
                     for case in control_report.get("cases", [])}
    control_valid = (
        control_report.get("pass") is True
        and control_report.get("final_ppl_sha256") == sha(SOURCES["v182"])
        and control_report.get("control_ppl_sha256") == control_before["ppl_sha256"]
        and len(control_cases) == 16
        and all(case.get("pass") is True for case in control_cases.values())
    )
    results = {"scope": "source-model event gates only; not vendor compilation or scanner qualification",
               "input_sha256_before": before, "tol": TOL, "failures": [], "cases": {},
               "v182_items2to4_control": {"inputs_before": control_before,
                                             "report_pass": control_report.get("pass"),
                                             "matches_frozen_final_ppl": control_report.get("final_ppl_sha256") == sha(SOURCES["v182"]),
                                             "all_16_nav01_cases_pass": control_valid,
                                             "case_summary": {f"nav{nav}/{model}": case
                                                              for (nav, model), case in control_cases.items()}},
               "validator_sha256_before": sha(Path(__file__)),
               "esp_summary": {}, "minimum_tr_by_dwell": {}, "mode_identity": {},
               "multislice_guard": {}, "phase": {}, "fused_area": {}, "elapsed_s": None}

    # Dwell-dependent minimum ESP and cost-model timing at min and min + 1 ms.
    for label in labels:
        for dwell in (50, 25):
            minimum = min_esp_search(label, SEEDS[label], dwell)
            results["esp_summary"][f"{label}/{dwell}us"] = minimum
            if minimum.get("error"):
                results["failures"].append(f"{label}/{dwell} us minimum ESP could not be found")
                continue
            accepted = minimum["min_accepted_esp_ms"]
            if minimum["one_ms_below_accepted"]:
                results["failures"].append(f"{label}/{dwell} us accepts one ms below its measured minimum")
            if minimum.get("printed_minimum_ms") != accepted:
                results["failures"].append(f"{label}/{dwell} us prints minimum ESP {minimum.get('printed_minimum_ms')} ms, event boundary is {accepted} ms")
            ppr = make_ppr(label, f"{label}_dwell{dwell}", dwell_us=dwell, edits={"esp": accepted})
            for esp in (accepted, accepted + 1):
                key = f"{label}/{dwell}us/esp{esp}"
                results["cases"][key] = {}
                for model_name, model in MODELS.items():
                    it = map_case(label, ppr, overrides={**IMAGING, "esp": esp}, shots=2, model=model)
                    rows = echo_metrics(it)
                    hazards = hazard_summary(it)
                    results["cases"][key][model_name] = {
                        "input_sha256": {"ppl": it.inputs["ppl_sha256"], "ppr": it.inputs["ppr_sha256"]},
                        "hazards": hazards, "shots": rows, "messages": reject_summary(it)}
                    if not it.adc:
                        results["failures"].append(f"{key}/{model_name}: rejected at expected accepted ESP")
                    if hazards["timer_overruns"] or hazards["ignored_lists"] or hazards["premature_matrix_use"]:
                        results["failures"].append(f"{key}/{model_name}: timer/list/matrix hazard")
                    if any(row["max_abs_midpoint_error_us"] is not None and row["max_abs_midpoint_error_us"] > TOL["echo_midpoint_us"] for row in rows):
                        results["failures"].append(f"{key}/{model_name}: echo centre outside tolerance")

    # v1.912 at 13 ms / 50 us must match v1.911, and 14 ms is the matched control.
    if "v1912" in labels:
        ppr11 = make_ppr("v1911", "v1911_13ms_50us", dwell_us=50, edits={"esp": 13})
        ppr12 = make_ppr("v1912", "v1912_13ms_50us", dwell_us=50, edits={"esp": 13})
        ref = map_case("v1911", ppr11, overrides={**IMAGING, "esp": 13}, shots=2)
        cand13 = map_case("v1912", ppr12, overrides={**IMAGING, "esp": 13}, shots=2)
        results["fused_area"]["v1912_13ms_vs_v1911"] = compare_interval_areas(ref, cand13)
        if not cand13.adc:
            results["failures"].append("v1912 rejects the v1.911 13 ms / 50 us control")
        if not results["fused_area"]["v1912_13ms_vs_v1911"]["pass"]:
            results["failures"].append("v1912 fused per-boundary gradient areas differ from v1.911")
        ppr14 = make_ppr("v1912", "v1912_14ms_50us_control", dwell_us=50, edits={"esp": 14})
        control14 = map_case("v1912", ppr14, overrides={**IMAGING, "esp": 14}, shots=2)
        results["cases"]["v1912/50us/esp14_matched_control"] = {
            "adc_count": len(control14.adc), "hazards": hazard_summary(control14),
            "shots": echo_metrics(control14), "ppr_sha256": sha(ppr14)}

    # Minimum ESP and TR table across console dwell choices; source-model binary search.
    for label in labels:
        for dwell in (50, 25, 20, 16):
            e = min_esp_search(label, SEEDS[label], dwell)
            if e.get("error"):
                results["minimum_tr_by_dwell"][f"{label}/{dwell}us"] = {"esp": e}
                continue
            ppr = make_ppr(label, f"tr_{label}_{dwell}", dwell_us=dwell,
                           edits={"esp": e["min_accepted_esp_ms"]})
            lo, hi = 50, 4000
            def tr_accept(tr):
                return bool(map_case(label, ppr, overrides={**IMAGING, "esp": e["min_accepted_esp_ms"], "tr": tr}, shots=1).adc)
            if not tr_accept(hi):
                trmin = None
            else:
                while hi - lo > 1:
                    mid = (lo + hi) // 2
                    if tr_accept(mid): hi = mid
                    else: lo = mid
                trmin = hi
            results["minimum_tr_by_dwell"][f"{label}/{dwell}us"] = {
                "minimum_esp_ms": e["min_accepted_esp_ms"], "minimum_tr_ms": trmin,
                "tr_previous_ms_rejected": lo, "ppr_sha256": sha(ppr)}

    # Slice-frequency and phase checks at centre, +/-1.2 mm and +/-5 mm.
    for label in labels:
        for model_name, model in MODELS.items():
            phase_sets = {}
            for z in (0, 1.2, -1.2, 5, -5):
                suffix = str(z).replace("-", "m").replace(".", "p")
                ppr = make_ppr(label, f"{label}_slice_{suffix}mm",
                               edits={"no_slices": 1}, arrays={"fov_slice_off": [round(z * 400)]})
                it = map_case(label, ppr, overrides={**IMAGING, "nav_on": 0}, shots=1, model=model)
                if z == 0:
                    center_origin, reference_hz, _ = centre_frequency_anchor(it)
                    if center_origin is None:
                        center_origin = 0.0
                origin, _, _ = centre_frequency_anchor(it)
                rows = phase_rows(it, z, reference_hz, origin if origin is not None else center_origin)
                phase_sets[z] = rows
                results["phase"][f"{label}/{model_name}/z{z}mm"] = rows
                if rows["status"] != "source_model_integrated":
                    results["failures"].append(f"{label}/{model_name}/z{z} mm effective RF phase unavailable")
            center = phase_sets[0]["rows"]
            for z in (1.2, -1.2, 5, -5):
                off = phase_sets[z]["rows"]
                if len(off) != len(center):
                    results["failures"].append(f"{label}/{model_name}/z{z} mm RF count differs from centre")
                    continue
                for c, p in zip(center, off):
                    if (c.get("shot"), c["frame"]) != (p.get("shot"), p["frame"]):
                        results["failures"].append(f"{label}/{model_name}/z{z} mm RF order differs at {c.get('shot')}/{c['frame']}")
                        continue
                    err = abs(circular_difference_deg(p["normalized_effective_phase_center_deg"],
                                                      c["normalized_effective_phase_center_deg"]))
                    p["phase_error_vs_centre_deg"] = err
                    if err > TOL["rf_effective_phase_deg"]:
                        results["failures"].append(f"{label}/{model_name}/z{z} mm {p['frame']} effective phase differs by {err:.2f} degrees")
                    # Each RF frame must receive a slice-specific carrier update.
                    p["frequency_delta_hz_vs_centre"] = float(p["tx_freq_hz"] or 0) - float(c["tx_freq_hz"] or 0)
                    if abs(p["frequency_delta_hz_vs_centre"]) < 1.0:
                        results["failures"].append(f"{label}/{model_name}/z{z} mm {p['frame']} has no per-slice frequency shift")
                    expected_df = (-p["selection_gradient_DAC"] * p["gradient_H_scale"] / 32767.0 * z
                                   if p["gradient_H_scale"] is not None else None)
                    p["expected_frequency_delta_hz_from_selector"] = expected_df
                    p["frequency_gradient_error_hz"] = (p["frequency_delta_hz_vs_centre"] - expected_df
                                                          if expected_df is not None else None)
                    if expected_df is None or abs(p["frequency_gradient_error_hz"]) > 5.0:
                        results["failures"].append(f"{label}/{model_name}/z{z} mm {p['frame']} frequency misses selector prediction by {p['frequency_gradient_error_hz']}")
            for z_a, z_b in ((1.2, 5), (-1.2, -5)):
                aa, bb = phase_sets[z_a]["rows"], phase_sets[z_b]["rows"]
                for a, b in zip(aa, bb):
                    da, db = float(a["frequency_delta_hz_vs_centre"]), float(b["frequency_delta_hz_vs_centre"])
                    if abs(da) > 1 and abs(db / da - z_b / z_a) > 0.08:
                        results["failures"].append(f"{label}/{model_name} {a['frame']} frequency shift not proportional to offset")

    # Repeat the RF-centre phase and carrier checks with mode 2 enabled and
    # actual imaging shots reached (the seed's dummy acquisitions are removed).
    # Six mapped shots exercise the volume train and appended imaging trains.
    results["nav2_phase"] = {}
    for label in labels:
        for model_name, model in MODELS.items():
            phase_sets = {}
            for z in (0, 1.2, -1.2, 5, -5):
                suffix = str(z).replace("-", "m").replace(".", "p")
                ppr = make_ppr(label, f"{label}_{model_name}_nav2_phase_{suffix}mm",
                               edits={"no_slices": 1, "no_disacq": 0, "nav_on": 2, "no_views": 153, "views_per_seg": 9},
                               arrays={"fov_slice_off": [round(z * 400)]})
                it = map_case(label, ppr, overrides={"no_slices": 1, "no_disacq": 0,
                                                    "nav_on": 2, "no_views": 153, "views_per_seg": 9},
                              shots=6, model=model)
                if z == 0:
                    center_origin, reference_hz, _ = centre_frequency_anchor(it)
                    if center_origin is None:
                        center_origin = 0.0
                origin, _, _ = centre_frequency_anchor(it)
                phase_sets[z] = phase_rows(it, z, reference_hz,
                                           origin if origin is not None else center_origin)
                phase_sets[z]["ADC_count"] = len(it.adc)
                phase_sets[z]["per_shot_ADC_counts"] = [len(s["adc"]) for s in shot_ledgers(it)[1]]
                results["nav2_phase"][f"{label}/{model_name}/z{z}mm"] = phase_sets[z]
                if not it.adc or phase_sets[z]["status"] != "source_model_integrated":
                    results["failures"].append(f"{label}/{model_name}/nav2/z{z} mm lacks integrated RF/ADC events")
            center = phase_sets[0]["rows"]
            for z in (1.2, -1.2, 5, -5):
                off = phase_sets[z]["rows"]
                if len(off) != len(center):
                    results["failures"].append(f"{label}/{model_name}/nav2/z{z} mm RF count differs from centre")
                    continue
                for c, p in zip(center, off):
                    if (c.get("shot"), c["frame"]) != (p.get("shot"), p["frame"]):
                        results["failures"].append(f"{label}/{model_name}/nav2/z{z} mm RF order differs at {c.get('shot')}/{c['frame']}")
                        continue
                    err = abs(circular_difference_deg(p["normalized_effective_phase_center_deg"],
                                                      c["normalized_effective_phase_center_deg"]))
                    p["phase_error_vs_centre_deg"] = err
                    if err > TOL["rf_effective_phase_deg"]:
                        results["failures"].append(f"{label}/{model_name}/nav2/z{z} mm shot{p.get('shot')} {p['frame']} phase differs by {err:.2f} degrees")
                    p["frequency_delta_hz_vs_centre"] = float(p["tx_freq_hz"] or 0) - float(c["tx_freq_hz"] or 0)
                    expected_df = (-p["selection_gradient_DAC"] * p["gradient_H_scale"] / 32767.0 * z
                                   if p["gradient_H_scale"] is not None else None)
                    p["expected_frequency_delta_hz_from_selector"] = expected_df
                    p["frequency_gradient_error_hz"] = (p["frequency_delta_hz_vs_centre"] - expected_df
                                                          if expected_df is not None else None)
                    if expected_df is None or abs(p["frequency_gradient_error_hz"]) > 5.0:
                        results["failures"].append(f"{label}/{model_name}/nav2/z{z} mm shot{p.get('shot')} {p['frame']} frequency misses selector prediction")

    # Three-slice separation guard: position arrays are in 400 units/mm; vary
    # adjacent centre spacing directly because SLICE_SEPARATION is acquisition
    # geometry metadata and does not feed the source guard.
    label = "v1912"
    guard = {}
    lo, hi = 0, 4000
    def spacing_trial(gap):
        ppr = make_ppr(label, f"v1912_spacing_{gap}", edits={"no_slices": 3},
                       arrays={"fov_slice_off": [-gap, 0, gap]})
        it = map_case(label, ppr, overrides=IMAGING, shots=1)
        return ppr, it
    _, upper_it = spacing_trial(hi)
    if upper_it.adc:
        while hi - lo > 1:
            mid = (lo + hi) // 2
            _, trial = spacing_trial(mid)
            if trial.adc: hi = mid
            else: lo = mid
        at_min_ppr, at_min = spacing_trial(hi)
        accepted_sha = sha(at_min_ppr)
        below_ppr, below = spacing_trial(lo)
        below_text = "\n".join(reject_summary(below))
        msg_min = re.search(r"minimum slice separation\s*=\s*(\d+)\s*units", below_text, re.I)
        guard = {"min_accepted_console_units": hi, "one_unit_below": lo,
                 "accepted_RF_count": len(rf_all(at_min)), "accepted_ADC_count": len(at_min.adc),
                 "below_RF_count": len(rf_all(below)), "below_ADC_count": len(below.adc),
                 "printed_minimum_console_units": int(msg_min.group(1)) if msg_min else None,
                 "below_error_codes": re.findall(r"error E(\d+)", below_text),
                 "below_messages": reject_summary(below), "ppr_sha256": accepted_sha,
                 "below_ppr_sha256": sha(below_ppr)}
        if not at_min.adc or rf_all(below) or below.adc:
            results["failures"].append("v1912 3-slice spacing boundary failed at min/min-1")
        if guard["printed_minimum_console_units"] != hi or "148" not in guard["below_error_codes"]:
            results["failures"].append("v1912 3-slice spacing guard lacks the expected printed E148 minimum")
    else:
        guard = {"error": "upper spacing bound rejected", "messages": reject_summary(upper_it)}
        results["failures"].append("v1912 3-slice spacing guard has no accepted upper bound")
    results["multislice_guard"] = guard

    # nav0/1 is gated against the isolated v182 items 2-4 control and v1911;
    # nav2 additionally checks the per-shot appended-echo behavior.
    for label, baseline in (("v182", "v181"), ("v1912", "v1911")):
        if label not in labels:
            continue
        for nav in (0, 1, 2):
            raw_views = {0: 128, 1: 136, 2: 153}[nav]
            edits = {"nav_on": nav, "no_views": raw_views,
                     "no_slices": 1, "no_disacq": 0}
            overrides = dict(edits)
            ppr = make_ppr(label, f"{label}_nav{nav}", edits=edits,
                           arrays={"fov_slice_off": [0]})
            shots_to_map = {0: 1, 1: 2, 2: 3}[nav]
            it = map_case(label, ppr, overrides=overrides, shots=shots_to_map)
            baseline_views = 128 if nav == 0 else 136
            base_edits = {"nav_on": min(nav, 1), "no_views": baseline_views,
                          "no_slices": 1, "no_disacq": 0}
            base_ppr = make_ppr(baseline, f"{baseline}_nav{nav}_baseline", edits=base_edits,
                                arrays={"fov_slice_off": [0]})
            bit = map_case(baseline, base_ppr, overrides=base_edits, shots=shots_to_map)
            # Existing signature compares event timing/gradient content relative to first RF.
            sig_new = old.event_signature(it, n_shots=2)
            sig_base = old.event_signature(bit, n_shots=2)
            identity = (old.compare_signatures(sig_base, sig_new)
                        if sig_base is not None and sig_new is not None else
                        {"all_identical": False, "error": "baseline or candidate emitted no RF events"})
            sig_full_new = full_event_signature(it)
            sig_full_base = full_event_signature(bit)
            if sig_full_base is not None and sig_full_new is not None:
                identity["frequency_commands_identical"] = sig_full_base["freq"] == sig_full_new["freq"]
                identity["phase_commands_identical"] = sig_full_base["phase"] == sig_full_new["phase"]
                identity["RF_carriers_identical"] = sig_full_base["rf"] == sig_full_new["rf"]
                identity["programmed_command_traces_identical"] = all(
                    identity[k] for k in ("frequency_commands_identical", "phase_commands_identical"))
                matrix_base = sig_base.get("matrices", {}) if sig_base else {}
                matrix_new = sig_new.get("matrices", {}) if sig_new else {}
                matrix_ids = set(matrix_base)
                matrix_values_identical = matrix_ids == set(matrix_new)
                max_matrix_write_shift = 0.0
                for matrix_id in matrix_ids & set(matrix_new):
                    left, right = matrix_base[matrix_id], matrix_new[matrix_id]
                    matrix_values_identical &= len(left) == len(right)
                    for a, b in zip(left, right):
                        matrix_values_identical &= a[1:] == b[1:]
                        if isinstance(a[0], (int, float)) and isinstance(b[0], (int, float)):
                            max_matrix_write_shift = max(max_matrix_write_shift, abs(b[0] - a[0]))
                identity["matrix_values_identical"] = bool(matrix_values_identical)
                identity["max_matrix_write_shift_us"] = round(max_matrix_write_shift, 6)
                # Added setup commands may differ while fixed padding keeps
                # physical RF/ADC/gradient events identical. Preserve that
                # distinction in the report. Matrix writes inside the padded
                # window are informational; their values remain part of the
                # identity gate while timestamps are reported separately.
                identity["physical_event_identity"] = (
                    identity.get("rf", {}).get("identical", False)
                    and identity.get("adc", {}).get("identical", False)
                    and all(identity.get("grad_" + axis, {}).get("identical", False) for axis in "SPR")
                    and identity["matrix_values_identical"])
            if label == "v182" and nav in (0, 1):
                control_case = control_cases.get((nav, "flat_0us"), {})
                # The immutable v1.81 comparison remains useful context, but
                # items 2--4 deliberately alter the RF phase-gate instructions.
                # Gate navigator behavior against the isolated items 2--4 PPL.
                identity["legacy_v181_physical_event_identity"] = identity.get("physical_event_identity", False)
                identity["items2to4_control_identity"] = control_case.get("checks")
                identity["items2to4_control_max_matrix_write_shift_us"] = control_case.get("matrix_max_write_shift_us")
                identity["physical_event_identity"] = bool(control_valid and control_case.get("pass"))
            results["mode_identity"][f"{label}/nav{nav}"] = {
                "baseline": baseline, "signature_comparison": identity,
                "ADC_count": len(it.adc), "baseline_ADC_count": len(bit.adc),
                "adc_states": prior.adc_states(it), "hazards": hazard_summary(it),
                "raw_no_views": raw_views,
                "expected_mode2_raw_dimension": 153 if nav == 2 else None,
                "ppr_sha256": sha(ppr)}
            if nav in (0, 1) and not identity.get("physical_event_identity", identity.get("all_identical", False)):
                baseline_name = "items 2-4 control" if label == "v182" else baseline
                results["failures"].append(f"{label} nav{nav} differs from {baseline_name} event signature")
            if nav == 2:
                has_extra_per_shot = len(it.adc) > len(bit.adc)
                pe_audit = navigator_pe_audit(it)
                results["mode_identity"][f"{label}/nav2"]["extra_ADC_vs_baseline"] = len(it.adc) - len(bit.adc)
                results["mode_identity"][f"{label}/nav2"]["navigator_PE_audit"] = pe_audit
                if not has_extra_per_shot or not pe_audit["all_zero_PE"]:
                    results["failures"].append(f"{label} nav2 lacks the expected per-shot ADC layout or zero-P appended echoes")

    # nav2 is also mapped with one slice and a three-slice protocol under every
    # instruction-cost model; the latter uses each version's intended spacing.
    results["nav2_layout"] = {}
    for label in ("v182", "v1912"):
        if label not in labels:
            continue
        for n_slices in (1, 3):
            offsets = [0] if n_slices == 1 else ([-480, 0, 480] if label == "v182" else [-1103, 0, 1103])
            ppr = make_ppr(label, f"{label}_nav2_{n_slices}slices", edits={
                "nav_on": 2, "no_views": 153, "views_per_seg": 9, "no_slices": n_slices, "no_disacq": 0},
                arrays={"fov_slice_off": offsets})
            embedded, _ = read_ppr(ppr)
            case_key = f"{label}/{n_slices}slices"
            results["nav2_layout"][case_key] = {"embedded_no_views": embedded.get("no_views"),
                                                 "raw_contract_no_views": 153,
                                                 "models": {}}
            if embedded.get("no_views") != 153:
                results["failures"].append(f"{case_key} embedded nav2 protocol does not declare raw no_views=153")
            for model_name, model in MODELS.items():
                it = map_case(label, ppr, overrides={"nav_on": 2, "no_views": 153, "views_per_seg": 9,
                                                     "no_slices": n_slices, "no_disacq": 0},
                              shots=2 * n_slices, model=model)
                _, ledgers = shot_ledgers(it)
                pe_audit = navigator_pe_audit(it)
                hazards = hazard_summary(it)
                record = {"RF_count": len(rf_all(it)), "ADC_count": len(it.adc),
                          "per_shot_ADC_counts": [len(s["adc"]) for s in ledgers],
                          "per_shot_RF_counts": [len(s["rf"]) for s in ledgers],
                          "navigator_PE_audit": pe_audit, "hazards": hazards,
                          "messages": reject_summary(it),
                          "input_sha256": {"ppl": it.inputs["ppl_sha256"], "ppr": it.inputs["ppr_sha256"]}}
                results["nav2_layout"][case_key]["models"][model_name] = record
                if not it.adc or not pe_audit["all_zero_PE"]:
                    results["failures"].append(f"{case_key}/{model_name} has no ADC or a nonzero appended-echo PE moment")
                if hazards["timer_overruns"] or hazards["ignored_lists"] or hazards["premature_matrix_use"]:
                    results["failures"].append(f"{case_key}/{model_name} has timing/list/matrix hazard")

    results["input_sha256_after"] = {name: {"ppl_sha256": sha(SOURCES[name]), "seed_ppr_sha256": sha(SEEDS[name])} for name in source_labels}
    results["inputs_stable_during_run"] = results["input_sha256_before"] == results["input_sha256_after"]
    if not results["inputs_stable_during_run"]:
        results["failures"].append("input PPL/PPR bytes changed during validation")
    results["v182_items2to4_control"]["inputs_after"] = {
        "ppl_sha256": sha(V182_CONTROL), "report_sha256": sha(V182_CONTROL_REPORT)}
    results["v182_items2to4_control"]["stable_during_run"] = (
        results["v182_items2to4_control"]["inputs_before"]
        == results["v182_items2to4_control"]["inputs_after"])
    if not control_valid or not results["v182_items2to4_control"]["stable_during_run"]:
        results["failures"].append("v182 items 2-4 navigator control is stale, invalid, or changed during validation")
    results["validator_sha256_after"] = sha(Path(__file__))
    results["validator_stable_during_run"] = results["validator_sha256_before"] == results["validator_sha256_after"]
    if not results["validator_stable_during_run"]:
        results["failures"].append("validator source changed during validation")
    results["elapsed_s"] = round(time.time() - started, 2)
    results["event_gates_pass"] = not results["failures"]
    save("event_gates.json", results)
    print(json.dumps({"event_gates_pass": results["event_gates_pass"], "failures": results["failures"],
                      "elapsed_s": results["elapsed_s"]}, indent=2))
    return results


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    PPRS.mkdir(parents=True, exist_ok=True)
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version", choices=("v182", "v1912"), help="run one sequence family; default runs both")
    args = ap.parse_args()
    result = run((args.version,) if args.version else ("v182", "v1912"))
    raise SystemExit(0 if result["event_gates_pass"] else 1)
