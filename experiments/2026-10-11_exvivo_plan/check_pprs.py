"""Read-only source-model checks for the 2026-10-11 ex-vivo PPR set.

This checker reads the manifest/PPRs and maps them through the frozen scanner
PPLs. It never regenerates or edits an input PPR. Output is validation.json.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PLAN = Path(__file__).resolve().parent
MANIFEST = PLAN / "manifest.json"
OUT = PLAN / "validation.json"
sys.path.insert(0, str(ROOT))

from dwfse.ppl.run import map_events  # noqa: E402
from dwfse.ppl.ppr import read_ppr  # noqa: E402
from dwfse.ppl.ledger import build_ledger, adc_middle_times  # noqa: E402
from examples import v19_validate_events as old  # noqa: E402
from examples import validate_v181_v1911 as prior  # noqa: E402
from scanner.recon.effective_b import _integrate  # noqa: E402

SPEC = importlib.util.spec_from_file_location("exvivo_make_pprs", PLAN / "make_pprs.py")
GENERATOR = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(GENERATOR)

PPLS = {
    "v182": ROOT / "scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.82.ppl",
    "v1912": ROOT / "scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.912.ppl",
}
STRESS_LETTERS = {"K", "L", "Q", "R", "V"}
MIDPOINT_LIMIT_US = 25.0
NAV_PE_LIMIT_CYCLES_M = 0.03
PPL_V181 = ROOT / "scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl"
PPL_V1911 = ROOT / "scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl"
PPR_OCT10_I = ROOT / "experiments/FSE-DWI_10-10-2026_v1911_testI/FSE-DWI_10-10-2026_v1911_testI.ppr"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return str(value)


def error_code(it) -> int:
    var = it.vars.get("v19_error_code")
    return int(var.value) if var is not None and var.value is not None else 0


def ppr_path(item: dict) -> Path:
    return PLAN / item["ppr"]


def actual_hashes(protocols: list[dict]) -> dict:
    pprs = {x["letter"]: sha(ppr_path(x)) for x in protocols}
    return {
        "manifest": sha(MANIFEST),
        "generator": sha(PLAN / "make_pprs.py"),
        "checker": sha(Path(__file__)),
        "ppls": {key: sha(path) for key, path in PPLS.items()},
        "pprs": pprs,
        "timer_context_sources": {"v181_ppl": sha(PPL_V181), "v1911_ppl": sha(PPL_V1911),
                                  "oct10_v1911_ppr": sha(PPR_OCT10_I)},
    }


def flag_summary(it) -> dict:
    counts: dict[str, int] = {}
    messages: dict[str, list[str]] = {}
    for flag in it.flags:
        kind = str(flag.get("kind", "unknown"))
        msg = str(flag.get("msg", flag.get("message", "")))
        counts[kind] = counts.get(kind, 0) + 1
        examples = messages.setdefault(kind, [])
        if msg and msg not in examples and len(examples) < 4:
            examples.append(msg)
    ignored = [f for f in it.flags if "ignored" in str(f.get("msg", f.get("message", ""))).lower()]
    timer_overruns = [f for f in it.flags if f.get("kind") == "timer_overrun"]
    timer_args = [f for f in it.flags if f.get("kind") == "timer_arg"]
    timer_samples = []
    for flag in timer_args[:8]:
        where = flag.get("where")
        if isinstance(where, (list, tuple)) and len(where) >= 2:
            source = str(where[0])
            try:
                source = str(Path(source).resolve().relative_to(ROOT))
            except (ValueError, OSError):
                pass
            where = {"source": source, "line": where[1]}
        message = str(flag.get("msg", ""))
        match = re.search(r"waittimer argument (-?\d+)", message)
        signed = int(match.group(1)) if match else None
        unsigned = signed % 65536 if signed is not None else None
        timer_samples.append({"time_us": flag.get("t_us"), "message": message, "where": where,
                              "signed_value": signed, "unsigned_16bit_value": unsigned,
                              "within_0_65500_unsigned_window": unsigned is not None and 0 <= unsigned <= 65500})
    base, _ = prior.shot_ledgers(it)
    hazards = prior.hazards(it, base["issues"])
    return {
        "raw_flag_counts": counts,
        "raw_flag_examples": messages,
        "timer_arg_flag_examples": timer_samples,
        "timer_arg_narrowing_is_informational": counts.get("timer_arg", 0) > 0,
        "hard_hazards": {
            "timer_overruns": len(timer_overruns),
            "ignored_lists": len(hazards["ignored_lists"]),
            "premature_matrix_use": sum(len(v) for v in hazards["premature_matrix_use"].values()),
        },
    }


def selected_final_pe(it, led) -> float | None:
    if not led["rf"] or not led["adc"]:
        return None
    shift = float(it.vars["rfdelay"].value) if "rfdelay" in it.vars else 0.0
    selected = prior.selected_k(it, led, shift)
    final_name = f"ADC{len(led['adc'])}"
    row = next((x for x in selected if x.get("at") == final_name), None)
    if row is None:
        return None
    vector = row.get("selected", {}).get("k_cycles_m")
    # Ledger axes are S, P, R. The zero-PE check is specifically the phase
    # axis, not the norm of the full three-dimensional moment.
    return float(vector[1]) if vector is not None and len(vector) >= 2 else None


def image_shots(it, ledgers: list[dict]) -> list[dict]:
    """For nav2, nav_cnt=1 identifies actual image shots after volume navs."""
    nav_on = int(it.vars["nav_on"].value) if "nav_on" in it.vars else 0
    if nav_on == 2:
        return [s for s in ledgers if s["adc"] and int(s["adc"][0].get("vars", {}).get("nav_cnt", -1)) == 1]
    return [s for s in ledgers if s["rf"] and s["adc"]]


def matrix_for_shot(it, led: dict, echo: int = 1) -> tuple[str, list[list[float]]]:
    rf = led["rf"]
    adc = adc_middle_times(it, led)
    if not rf or len(adc) < echo:
        raise ValueError("actual imaging shot lacks RF or requested ADC")
    lag = float(it.vars["rfdelay"].value)
    method = any(str(p["frame"]).startswith("v19_") for p in rf)
    frozen = []
    if method:
        flips = [p["t_center"] for p in rf if "180" in p["frame"]]
        tip = next(p["t_center"] for p in rf if p["frame"] == "v19_slrtip90")
        reexc = next(p["t_center"] for p in rf if p["frame"] == "v19_reexc90")
        frozen = [(tip, reexc)]
        candidates = {"carrier": flips, "conjugate": sorted(flips + [reexc])}
    else:
        candidates = {"primary": [p["t_center"] for p in rf[1:]]}
    results = {name: _integrate(led, rf[0]["t_center"], adc[echo - 1][1], flips, frozen, lag)
               for name, flips in candidates.items()}
    branch = min(results, key=lambda name: np.linalg.norm(results[name][0]))
    b = results[branch][1][np.ix_([2, 1, 0], [2, 1, 0])]
    return branch, b.tolist()


def row_overrides(item: dict, row: tuple[int, list[int]]) -> dict:
    b, direction = row
    n = len(item["rows"])
    return {
        "no_disacq": 0,
        "acq_b": [int(b)] * n,
        "acq_x": [int(direction[0])] * n,
        "acq_y": [int(direction[1])] * n,
        "acq_z": [int(direction[2])] * n,
    }


def row_model(it, requested_row=None) -> dict:
    _, ledgers = prior.shot_ledgers(it)
    shots = image_shots(it, ledgers)
    matrices = []
    for shot in shots:
        branch, bmat = matrix_for_shot(it, shot, echo=1)
        trace = sum(bmat[i][i] for i in range(3))
        matrices.append({"shot": shot["shot"], "slice": shot["rf"][0].get("vars", {}).get("current_slice"),
                         "branch": branch, "trace_s_per_mm2": trace, "bmatrix_s_per_mm2": bmat,
                         "final_adc_PE_cycles_m": selected_final_pe(it, shot)})
    gradient_names = ("diff_read", "diff_phase", "diff_slice")
    gradient_dac = {axis: (float(it.vars[name].value) if name in it.vars else None)
                    for axis, name in zip("xyz", gradient_names)}
    return {"actual_image_shots": len(shots), "expected_image_shots_at_least": int(it.vars["no_slices"].value),
            "requested_row": requested_row, "diffusion_gradient_DAC": gradient_dac,
            "diff_grad_DAC": float(it.vars["diff_grad"].value) if "diff_grad" in it.vars else None,
            "image_shot_rows": matrices}


def duration_check(item: dict, ppl: Path, ppr: Path) -> dict:
    # Keep the PPR's original no_disacq dummies intact; validation mode only
    # prints the scanner-side duration and does not acquire RF/ADC.
    it = map_events(ppl, ppr, overrides={"validate": 1}, max_shots=1,
                    rf_latency_us=3.0, **old.NOMINAL)
    texts = "\n".join(text for _, text in it.out)
    values = [int(x) for x in re.findall(r"Duration\s*=\s*(\d+)", texts, re.I)]
    observed = values[-1] if values else None
    expected = int(round(float(item["nominal_duration_s"]) * 1000))
    params, _ = read_ppr(ppr)
    return {"ppr_no_disacq_preserved": int(params.get("no_disacq", -1)),
            "observed_duration_ms": observed, "manifest_duration_ms": expected,
            "matches_manifest": observed == expected,
            "error_code": error_code(it),
            "validation_output": [line.strip() for line in texts.splitlines() if "Duration=" in line or "error E" in line]}


def timer_context() -> dict:
    """Compare signed-narrow diagnostics with inherited unsigned-timer paths."""
    v_item = next(x for x in json.loads(MANIFEST.read_text())["protocols"] if x["letter"] == "V")
    r_item = next(x for x in json.loads(MANIFEST.read_text())["protocols"] if x["letter"] == "R")
    v_ppr = ppr_path(v_item)
    r_ppr = ppr_path(r_item)
    controls = []
    for name, ppl, ppr, overrides, shots in (
        ("v182 final V, current nav2", PPLS["v182"], v_ppr, {"no_disacq": 0}, 6),
        ("v1.81 inherited PPL with same V PPR core dimensions", PPL_V181, v_ppr,
         {"nav_on": 0, "no_views": 256, "no_slices": 1, "no_disacq": 0}, 2),
        ("v1912 R current Delta30/TE44 high-b protocol", PPLS["v1912"], r_ppr,
         {"no_disacq": 0}, 2),
        ("v1.911 Oct10 test I inherited short-Delta/TE44 control", PPL_V1911, PPR_OCT10_I,
         {"no_disacq": 0}, 2),
    ):
        it = map_events(ppl, ppr, overrides=overrides, max_shots=shots,
                        rf_latency_us=3.0, **old.NOMINAL)
        flags = flag_summary(it)
        params, _ = read_ppr(ppr)
        controls.append({"name": name, "ppl_sha256": sha(ppl), "ppr_sha256": sha(ppr),
                         "overrides": overrides, "max_shots": shots,
                         "ppr_timing_fields": {key: params.get(key) for key in
                             ("sample_period", "no_samples", "no_views", "views_per_seg", "nav_on",
                              "no_slices", "no_disacq", "esp", "te", "tr", "big_delta", "small_delta")},
                         "error_code": error_code(it), "RF_count": len(prior._rf_all(it)),
                         "ADC_count": len(it.adc), "hard_hazards": flags["hard_hazards"],
                         "raw_timer_arg_examples": flags["timer_arg_flag_examples"]})
    return {
        "purpose": "Raw timer_arg signed-narrow diagnostics are compared with inherited PPL paths and interpreted as 16-bit unsigned only as context; no timer_arg-only failure is asserted.",
        "comparisons": controls,
        "historical_v1911_control_note": "Compare the parsed timing fields above directly; this control is contextual inherited behavior, not exact protocol equivalence.",
    }


def acquisition_check(item: dict, ppl: Path, ppr: Path, model: dict, *, row=None) -> dict:
    params, _ = read_ppr(ppr)
    n_slices = int(params.get("no_slices", 1))
    max_shots = max(2, 2 * n_slices)
    overrides = {"no_disacq": 0}
    if row is not None:
        overrides.update(row_overrides(item, row))
    it = map_events(ppl, ppr, overrides=overrides, max_shots=max_shots,
                    rf_latency_us=3.0, **model)
    base, ledgers = prior.shot_ledgers(it)
    rf_count = sum(len(s["rf"]) for s in ledgers)
    adc_count = sum(len(s["adc"]) for s in ledgers)
    flags = flag_summary(it)
    midpoint_values = []
    for shot in ledgers:
        if shot["rf"] and shot["adc"]:
            midpoint_values += [abs(x) for x in prior.structure(it, shot)["ADC_minus_train_RF_midpoint_us"]]
    nav2_pe = []
    for shot in image_shots(it, ledgers):
        value = selected_final_pe(it, shot)
        if value is not None:
            nav2_pe.append({"shot": shot["shot"], "cycles_per_m": value})
    row_metrics = row_model(it, {"b": int(row[0]), "direction_1000norm": list(row[1])}) if row is not None else None
    return {
        "overrides": overrides, "max_shots": max_shots,
        "error_code": error_code(it), "RF_count": rf_count, "ADC_count": adc_count,
        "duration_messages": [m.strip() for _, m in it.out if "Duration=" in m],
        "raw_mapper_flags": flags,
        "max_abs_ADC_midpoint_error_us": max(midpoint_values, default=None),
        "navigator_appended_echo_PE": nav2_pe,
        "row_model": row_metrics,
        "messages": [m.strip() for _, m in it.out if re.search(r"error E\d+|minimum esp|minimum slice|too short|increase esp", m, re.I)],
        "input_sha256": {"ppl": it.inputs["ppl_sha256"], "ppr": it.inputs["ppr_sha256"]},
    }


def load_inputs() -> tuple[dict, list[dict]]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    protocols = manifest["protocols"]
    expected = {x["letter"]: x for x in GENERATOR.TESTS}
    checks = []
    for item in protocols:
        if item["letter"] not in expected:
            checks.append(f"manifest protocol {item['letter']} has no generator definition")
            continue
        generated = expected[item["letter"]]
        for key in ("version", "rows", "priority", "dwell_us", "esp", "tr", "te", "big_delta", "nav_on", "offsets", "matrix"):
            generated_value = json.loads(json.dumps(generated.get(key))) if key in generated else None
            if key in generated and item.get(key) != generated_value:
                checks.append(f"{item['letter']} manifest/generator mismatch in {key}")
        ppr = ppr_path(item)
        if not ppr.is_file():
            checks.append(f"{item['letter']} PPR missing: {ppr}")
        elif sha(ppr) != item["ppr_sha256"]:
            checks.append(f"{item['letter']} PPR SHA-256 differs from manifest")
    if set(expected) != {x["letter"] for x in protocols}:
        checks.append("generator and manifest protocol letter sets differ")
    return manifest, checks


def host_metadata_check(ppr: Path, params: dict, meta: dict, item: dict) -> dict:
    """Check serialized host-side slice spacing and per-slice angle arrays."""
    source = ppr.read_text(encoding="latin-1", errors="replace")
    sep_match = re.search(r"(?im)^:SLICE_SEPARATION\s+slice_offset,\s*(-?\d+),\s*(-?[\d.]+)\s*$", source)
    offsets = [float(x) for x in item.get("slice_offsets_mm", [])]
    expected_gap = abs(offsets[1] - offsets[0]) if len(offsets) > 1 else None
    displayed_gap = float(sep_match.group(2)) if sep_match else None
    angle_rows = {}
    for header, var in (("X_ANGLE", "r_angle_var"), ("Y_ANGLE", "p_angle_var"), ("Z_ANGLE", "s_angle_var")):
        match = re.search(rf"(?im)^:{header}\s+{var},\s*(\d+)\s*\r?\n([^\r\n]+)", source)
        continuation = match.group(2).strip() if match else ""
        values = [int(x) for x in re.findall(r"-?\d+", continuation)] if continuation.startswith(",") else []
        angle_rows[header] = {"declared_count": int(match.group(1)) if match else None,
                              "values": values, "expected_count": int(params.get("no_slices", 1)),
                              "matches_slice_count": bool(match and int(match.group(1)) == int(params.get("no_slices", 1)) and len(values) == int(params.get("no_slices", 1)))}
    offsets_match = [int(x) for x in params.get("fov_slice_off", [])]
    gap_matches = (expected_gap is None or displayed_gap is not None and abs(displayed_gap - expected_gap) < 1e-6)
    return {
        "slice_separation_console_units": int(sep_match.group(1)) if sep_match else None,
        "slice_separation_display_mm": displayed_gap,
        "manifest_slice_offsets_mm": offsets,
        "expected_adjacent_gap_mm": expected_gap,
        "slice_gap_matches_manifest": gap_matches,
        "fov_slice_offsets_console_units": offsets_match,
        "angle_arrays": angle_rows,
        "angle_arrays_match_slice_count": all(v["matches_slice_count"] for v in angle_rows.values()),
    }


def main() -> int:
    manifest, failures = load_inputs()
    protocols = manifest["protocols"]
    # Exercise the same JSON conversion path before any of the longer mapper runs.
    json.loads(json.dumps({"numpy_preflight": np.asarray([1, 2], dtype=np.int64)}, default=json_default))
    before = actual_hashes(protocols)
    report = {
        "scope": "Read-only source-model validation of all manifest PPRs; not scanner/vendor compilation or biological validation.",
        "manifest_core_duration_s": manifest["core_duration_s"],
        "manifest_conditional_duration_s": manifest["conditional_duration_s"],
        "protocol_count": len(protocols), "source_hashes_before": before,
        "calibration_contract": {
            "50us": {"sample_period_ticks": 500, "read_var": -735, "SMX": 0.0224563},
            "25us": {"sample_period_ticks": 250, "read_var": -1471, "SMX": 0.0449126},
            "read_scale_note": "PPR represents the acquired gradient DAC calibration; this checker does not apply an extra read-axis scale.",
        },
        "timer_arg_policy": "Raw signed-narrowing timer_arg flags are reported. They are not alone a failure when mapped wait duration is within the inherited unsigned 0..65500 range and the mapper reports no timer_overrun.",
        "stress_cost_models": list(old.COST_MODELS),
        "stress_profiles": sorted(STRESS_LETTERS),
        "timer_arg_context": timer_context(),
        "protocols": {}, "failures": failures,
    }
    model_stress = {}
    for item in protocols:
        ppr = ppr_path(item)
        ppl = PPLS[item["version"]]
        params, meta = read_ppr(ppr)
        rows = [(int(b), [int(x), int(y), int(z)]) for b, (x, y, z) in item["rows"]]
        row_arrays = {"acq_b": params.get("acq_b", [])[:len(rows)],
                      "acq_x": params.get("acq_x", [])[:len(rows)],
                      "acq_y": params.get("acq_y", [])[:len(rows)],
                      "acq_z": params.get("acq_z", [])[:len(rows)]}
        declared = {"acq_b": [r[0] for r in rows], "acq_x": [r[1][0] for r in rows],
                    "acq_y": [r[1][1] for r in rows], "acq_z": [r[1][2] for r in rows]}
        array_match = all(row_arrays[k] == declared[k] for k in declared)
        sample_ticks = int(params.get("sample_period", -1))
        read_var = int(params.get("gr_var", 0))
        smx = float(meta.get("SMX", "nan"))
        calibration_expected = report["calibration_contract"]["25us" if item["dwell_us"] == 25 else "50us"]
        calibration_match = sample_ticks == calibration_expected["sample_period_ticks"] and read_var == calibration_expected["read_var"] and abs(smx - calibration_expected["SMX"]) < 1e-8
        duration = duration_check(item, ppl, ppr)
        host_meta = host_metadata_check(ppr, params, meta, item)
        if item["priority"] == "guard":
            acquisition = acquisition_check(item, ppl, ppr, old.NOMINAL)
            msg = "\n".join(acquisition["messages"]).lower()
            exp = str(item.get("expected_rejection") or "").lower()
            expected_code = "148" if "e148" in exp else ("147" if "e147" in exp else None)
            minimum_esp = re.search(r"minimum\s+esp\s*=\s*(\d+)", exp)
            minimum_esp_message = bool(minimum_esp and (
                f"at least {minimum_esp.group(1)} ms" in msg or "minimum esp" in msg))
            guard_pass = acquisition["ADC_count"] == 0 and (
                acquisition["error_code"] != 0 or (bool(exp) and exp in msg) or minimum_esp_message)
            if expected_code:
                guard_pass &= str(acquisition["error_code"]) == expected_code or f"e{expected_code}" in msg
            if minimum_esp:
                guard_pass &= minimum_esp_message
            report["protocols"][item["letter"]] = {
                "version": item["version"], "priority": item["priority"],
                "ppr_sha256": sha(ppr), "static_arrays_match_manifest": array_match,
                "read_calibration_matches": calibration_match, "duration": duration,
                "host_metadata": host_meta,
                "no_acquisition_guard": {**acquisition, "expected_rejection": exp, "pass": bool(guard_pass)},
            }
            if not guard_pass:
                failures.append(f"{item['letter']} expected no-acquisition guard did not reject as requested")
            continue

        nominal = acquisition_check(item, ppl, ppr, old.NOMINAL)
        nslices = int(params.get("no_slices", 1))
        stress_row_idx = None
        if item["letter"] in STRESS_LETTERS:
            if item["letter"] == "V":
                stress_row_idx = next((i for i, (b, direction) in enumerate(rows)
                                       if b == 6000 and direction == [0, 0, 1000]), None)
            if stress_row_idx is None:
                stress_row_idx = max(range(len(rows)), key=lambda i: (rows[i][0], i))
        row_results = []
        for row_idx, row in enumerate(rows):
            per_model = {}
            # Every row gets nominal coverage; only one high-stress row per
            # selected protocol gets the full eight-model timing sweep.
            models = old.COST_MODELS if row_idx == stress_row_idx else {"manual_x0.8": old.NOMINAL}
            for model_name, model in models.items():
                modeled = acquisition_check(item, ppl, ppr, model, row=row)
                per_model[model_name] = {
                    "error_code": modeled["error_code"], "RF_count": modeled["RF_count"],
                    "ADC_count": modeled["ADC_count"], "max_abs_ADC_midpoint_error_us": modeled["max_abs_ADC_midpoint_error_us"],
                    "raw_mapper_flags": modeled["raw_mapper_flags"],
                    "navigator_appended_echo_PE": modeled["navigator_appended_echo_PE"],
                    "row_model": modeled["row_model"],
                }
            row_results.append({"row_index": row_idx, "b_requested": row[0], "direction_1000norm": row[1],
                               "model_by_cost": per_model})
        record = {
            "version": item["version"], "priority": item["priority"], "purpose": item["purpose"],
            "ppr_sha256": sha(ppr), "dimensions": {k: params.get(k) for k in ("no_samples", "no_views", "views_per_seg", "nav_on", "no_experiments", "no_diff_acq", "no_slices", "batch_slices", "no_disacq", "tr", "te", "esp", "big_delta", "b_input_mode", "gr_var", "gp_init_var")},
            "PPR_geometry_metadata": {k: meta.get(k) for k in ("FOV", "SMX", "SMY", "MULTI_ORIENTATION", "FOV_OFFSETS")},
            "host_metadata": host_meta,
            "fov_slice_off_console_units": params.get("fov_slice_off", []),
            "manifest_slice_offsets_mm": item.get("slice_offsets_mm", []),
            "SMX": smx, "sample_period_ticks": sample_ticks,
            "static_arrays_match_manifest": array_match, "read_calibration_matches": calibration_match,
            "duration": duration,
            "nominal_acquisition": nominal,
            "volume_rows": row_results,
            "eight_cost_model_stress_row_index": stress_row_idx,
            "eight_cost_model_stress_row": ({"b": rows[stress_row_idx][0], "direction_1000norm": rows[stress_row_idx][1]}
                                              if stress_row_idx is not None else None),
            "actual_image_shots_expected_per_row": nslices,
        }
        report["protocols"][item["letter"]] = record
        if item["letter"] in STRESS_LETTERS:
            model_stress[item["letter"]] = {row["row_index"]: row["model_by_cost"] for row in row_results}
        # Gate the actual normal path. Timer argument sign-narrowing is raw
        # informational unless it turns into a timer overrun.
        if error_code_from_record(nominal) != 0 or nominal["ADC_count"] == 0:
            failures.append(f"{item['letter']} normal no-disacq=0 path emitted no accepted ADC acquisition")
        if any(nominal["raw_mapper_flags"]["hard_hazards"].values()):
            failures.append(f"{item['letter']} normal nominal path has a hard timer/list/matrix hazard")
        if not array_match:
            failures.append(f"{item['letter']} PPR volume arrays differ from manifest rows")
        if not calibration_match:
            failures.append(f"{item['letter']} actual read calibration metadata differs from requested mapping")
        if not host_meta["slice_gap_matches_manifest"]:
            failures.append(f"{item['letter']} PPR SLICE_SEPARATION metadata differs from manifest offsets")
        if not host_meta["angle_arrays_match_slice_count"]:
            failures.append(f"{item['letter']} PPR angle arrays do not match slice count")
        if not duration["matches_manifest"]:
            failures.append(f"{item['letter']} PPL-reported duration differs from manifest under original dummy count")
        for row_record in row_results:
            for model_name, row_case in row_record["model_by_cost"].items():
                if row_case["error_code"] != 0 or row_case["ADC_count"] == 0:
                    failures.append(f"{item['letter']} row {row_record['row_index']} {model_name} rejected or emitted no ADC")
                if any(row_case["raw_mapper_flags"]["hard_hazards"].values()):
                    failures.append(f"{item['letter']} row {row_record['row_index']} {model_name} hard timer/list/matrix hazard")
                if row_case["max_abs_ADC_midpoint_error_us"] is not None and row_case["max_abs_ADC_midpoint_error_us"] > MIDPOINT_LIMIT_US:
                    failures.append(f"{item['letter']} row {row_record['row_index']} {model_name} ADC midpoint exceeds tolerance")
                gradient = row_case["row_model"]["diffusion_gradient_DAC"]
                scale = row_case["row_model"]["diff_grad_DAC"]
                expected_direction = row_record["direction_1000norm"]
                if scale is None or any(gradient[axis] is None or
                        abs(gradient[axis] - round(scale * expected_direction[idx] / 1000)) > 1.0
                        for idx, axis in enumerate("xyz")):
                    failures.append(f"{item['letter']} row {row_record['row_index']} {model_name} programmed gradient DACs do not match row direction")
                nav_pe = row_case["navigator_appended_echo_PE"]
                if int(params.get("nav_on", 0)) == 2 and any(abs(x["cycles_per_m"]) > NAV_PE_LIMIT_CYCLES_M for x in nav_pe):
                    failures.append(f"{item['letter']} row {row_record['row_index']} {model_name} appended navigator PE is nonzero")
                if int(params.get("nav_on", 0)) == 2 and len(row_case["row_model"]["image_shot_rows"]) < nslices:
                    failures.append(f"{item['letter']} row {row_record['row_index']} {model_name} did not reach image shots for all slices")
    report["stress_models"] = model_stress
    report["source_hashes_after"] = actual_hashes(protocols)
    report["inputs_stable_during_run"] = report["source_hashes_before"] == report["source_hashes_after"]
    if not report["inputs_stable_during_run"]:
        failures.append("manifest, generator, PPL, PPR or checker source bytes changed during run")
    report["failures"] = failures
    report["validation_pass"] = not failures
    # Preflight serialization before overwriting the deliverable.
    encoded = json.dumps(report, indent=2, default=json_default) + "\n"
    json.loads(encoded)
    OUT.write_text(encoded, encoding="utf-8")
    print(json.dumps({"validation_pass": report["validation_pass"], "protocols": len(protocols),
                      "failures": failures, "output": str(OUT)}, indent=2))
    return 0 if report["validation_pass"] else 1


def error_code_from_record(record: dict) -> int:
    return int(record.get("error_code", 0))


if __name__ == "__main__":
    raise SystemExit(main())
