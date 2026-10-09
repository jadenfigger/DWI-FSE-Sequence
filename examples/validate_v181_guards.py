"""Additive v1.81 writer checks: rejection, schedules and relocation moments.

Independent reviewers must still approve the final source. No scanner compiled
program, measured gradient response or RF calibration is available here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dwfse.ppl.run import map_events
from dwfse.ppl.events import rf_pulses
from dwfse.ppl.ledger import build_ledger, adc_middle_times, effective_moment, dac_us_to_cyc_m
from dwfse.vendor_seq import decode
from examples.build_v181_ppl import PPL, PPR, BASE, generate_ppl, generate_ppr
from examples.v19_validate_events import COST_MODELS, NOMINAL

OUT = ROOT / "docs/v181_v1911/validation/v181_guards.json"


def mapped(overrides=None, model=None, shots=1, grad_latency_us=0):
    return map_events(PPL, PPR, overrides=overrides or {}, max_shots=shots,
                      rf_latency_us=3.0, grad_latency_us=grad_latency_us,
                      **(model or NOMINAL))


def actual_rf(it):
    return [p for p in rf_pulses(it) if p.get("library")]


def clean(it):
    led = build_ledger(it)
    bad = [f for f in it.flags if f["kind"] not in ("narrowing", "matrix_active")]
    return len(actual_rf(it)) == 18 and len(it.adc) == 16 and not bad and not any(led["issues"].values()), bad


def unsafe_cases():
    return {
        "diffusion_flow_compensation": {"flow_comp_on": 1},
        "CEST_MTC_unsupported": {"mtc_on": 1},
        "ramp_mismatch": {"diff_tramp": 300},
        "ramp_too_short": {"tramp": 50, "diff_tramp": 50},
        "ramp_off_raster": {"tramp": 201, "diff_tramp": 201},
        "crusher_zero_duration": {"tcrush": 0},
        "crusher_excessive_duration": {"tcrush": 5001},
        "first_crusher_zero_duration": {"diff_tcrush": 0},
        "crusher_invalid_signed_DAC": {"crush_amp": -32768},
        "crusher_amplitude_ceiling": {"crusher_max_dac": 2000},
        "crusher_slew_ceiling": {"crusher_slew_dac_100us": 100},
        "invalid_amplitude_ceiling": {"crusher_max_dac": 0},
        "invalid_slew_ceiling": {"crusher_slew_dac_100us": 0},
        "invalid_schedule": {"crusher_schedule": 6},
        "invalid_schedule_step": {"crusher_step_pct": 1001},
        "custom_count_mismatch": {"crusher_schedule": 5, "crusher_custom_count": 7},
        "custom_invalid_percentage": {"crusher_schedule": 5, "crusher_custom_count": 8,
                                      "crusher_custom_pct": [-32768] + [100] * 63},
        "schedule_without_independent_crushers": {"crusher_schedule": 1, "crush_independent_on": 0},
        "schedule_short_ADC": {"crusher_schedule": 1, "no_samples": 32, "sample_period": 100},
        "driven_equilibrium": {"de_on": 1},
        "invalid_RF_gradient_lag": {"rfdelay": 101},
        "invalid_diffusion_scale_low": {"diff_grad_scale": 99},
        "invalid_diffusion_scale_high": {"diff_grad_scale": 201},
        "invalid_direction_component": {"acq_x": [1001] + [1000] * 511},
        "nonunit_direction": {"acq_x": [500] + [1000] * 511},
        "unachievable_b": {"acq_b": [30000] + [0] * 511},
        "invalid_views": {"no_views": 0},
        "invalid_ETL": {"views_per_seg": 0},
        "navigator_without_imaging_views": {"no_views": 8},
        "unsupported_DWI_PE_order": {"PE_order": 0},
        "implicit_diffusion_TE": {"te": 0},
        "diffusion_TE_too_short": {"te": 20},
        "diffusion_delta_outside_b_kernel": {"sm_delta": 11000},
        "diffusion_Delta_too_short": {"big_delta": 5000},
        "first_refocus_timer_overrange": {"diff_tcrush": 10000, "te": 100, "big_delta": 70000},
        "new_first_read_DAC_ceiling": {"crusher_max_dac": 1000, "crush_amp": -100, "diff_crush_amp": -100},
        "new_first_read_slew_ceiling": {"crusher_slew_dac_100us": 100, "crush_amp": -100, "diff_crush_amp": -100},
        "new_intermediate_read_scale": {"grp_lobe": 300, "tref_setup": 100, "gr_var": -1000},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="nominal schedule checks only")
    args = ap.parse_args()
    result = {"scope": "writer checks, not independent review or scanner verification",
              "ppl_sha256": hashlib.sha256(PPL.read_bytes()).hexdigest(),
              "ppr_sha256": hashlib.sha256(PPR.read_bytes()).hexdigest(),
              "reproducible": PPL.read_bytes() == generate_ppl().replace("\n", "\r\n").encode("latin-1")
                              and PPR.read_bytes() == generate_ppr().replace("\n", "\r\n").encode("latin-1"),
              "unsafe_protocols": {}, "schedules": {}, "latency_sensitivity": {}}
    for name, overrides in unsafe_cases().items():
        it = mapped(overrides)
        passed = len(actual_rf(it)) == 0 and len(it.adc) == 0 and bool(it.out)
        result["unsafe_protocols"][name] = {"pass": passed, "RF": len(actual_rf(it)),
                                          "ADC": len(it.adc), "messages": [x[1] for x in it.out]}
    models = {"manual_x0.8": NOMINAL} if args.quick else COST_MODELS
    for schedule in range(6):
        overrides = {"crusher_schedule": schedule, "crusher_step_pct": 40}
        if schedule == 5:
            overrides.update(crusher_custom_count=8, crusher_custom_pct=[100, 100, 120, 140, 160, 180, 200, 220] + [100] * 56)
        cases = {}
        for label, model in models.items():
            it = mapped(overrides, model, shots=2)
            passed, flags = clean(it)
            cases[label] = {"pass": passed, "RF": len(actual_rf(it)), "ADC": len(it.adc),
                            "bad_flags": flags, "setup_ticks": it.vars["crusher_setup_ticks"].value,
                            "messages": [x[1] for x in it.out]}
        result["schedules"][str(schedule)] = cases
    for lag in (0, 60):
        cases = {}
        for label, model in models.items():
            it = mapped(model=model, shots=2, grad_latency_us=lag)
            passed, flags = clean(it)
            cases[label] = {"pass": passed, "bad_flags": flags}
        result["latency_sensitivity"][str(lag)] = cases
    # Independently read the actual negative secondary ramp sums. The old and
    # fused read lobes use these same ramps, not the asymmetric positive pair.
    library = decode(ROOT / "scanner/utilities/g3040_15.seq")
    frames = {f.name: f for f in library.frames}
    sums = {n: int(np.asarray(frames[n].samples, dtype=np.int64)[:, 1].sum())
            for n in ("0_mn_sec", "mn_0_sec", "0_mx_sec", "mx_0_sec")}
    it = mapped(shots=2)
    led = build_ledger(it)
    u = lambda k: it.vars[k].value
    old_prephase = -u("grp_dp") * (u("tref") + u("tramp"))
    moved_prephase = (u("gr_dp") - u("v181_first_read_dp")) * (u("tdp") + u("tramp"))
    moment_rows = []
    t0 = led["rf"][0]["t_center"]
    centers = [p["t_center"] for p in led["rf"][1:]]
    for name, t in adc_middle_times(it, led):
        moment_rows.append({"ADC": name, "time_from_excitation_us": t - t0,
                            "effective_read_cycles_m": effective_moment(led, "R", t0, t, centers)})
    result["relocation_area"] = {"negative_secondary_ramp_sums": sums,
                                 "negative_ramp_exact_unit_factor": (sums["0_mn_sec"] + sums["mn_0_sec"]) / (32767 * 50),
                                 "old_read_prephase_DAC_us": old_prephase,
                                 "new_read_prephase_DAC_us": moved_prephase,
                                 "desired_path_area_error_DAC_us": old_prephase + moved_prephase,
                                 "desired_path_area_error_cycles_m": dac_us_to_cyc_m(old_prephase + moved_prephase, led["H"]),
                                 "ADC_effective_read_moments": moment_rows}
    result["ppl_sha256_at_end"] = hashlib.sha256(PPL.read_bytes()).hexdigest()
    result["inputs_stable_during_run"] = result["ppl_sha256_at_end"] == result["ppl_sha256"]
    result["all_pass"] = result["inputs_stable_during_run"] and result["reproducible"] and all(x["pass"] for x in result["unsafe_protocols"].values()) \
        and all(x["pass"] for cases in result["schedules"].values() for x in cases.values()) \
        and all(x["pass"] for cases in result["latency_sensitivity"].values() for x in cases.values())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"all_pass": result["all_pass"], "unsafe_cases": len(result["unsafe_protocols"]),
                      "failed_rejections": [n for n, c in result["unsafe_protocols"].items() if not c["pass"]],
                      "failed_schedules": [(s, n) for s, c in result["schedules"].items() for n, v in c.items() if not v["pass"]],
                      "failed_latencies": [(s, n) for s, c in result["latency_sensitivity"].items() for n, v in c.items() if not v["pass"]],
                      "moment_error": result["relocation_area"]["desired_path_area_error_cycles_m"]}, indent=2))


if __name__ == "__main__":
    main()
