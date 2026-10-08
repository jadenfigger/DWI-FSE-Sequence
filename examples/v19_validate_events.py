"""Validate the actual v191/v192 PPLs through the PPL-to-event mapper.

Outputs docs/v19/event_validation/: timing ledgers, control-path identity,
moment audits, hazard flags, b-tensors, event-driven Bloch results,
convergence/independent-solver checks and diagrams.

Every result is a *nominal source-level* mapping (dwfse/ppl, documented
expression costs scaled by 0.8, no extra flat statement cost): not compiler/console timing.

Run:  python examples/v19_validate_events.py [--quick]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dwfse.ppl.run import map_events, sha256  # noqa: E402
from dwfse.ppl.ledger import (build_ledger, effective_moment, dac_us_to_cyc_m,  # noqa: E402
                              method_landmarks, adc_middle_times, list_starts, list_duration_us)
from dwfse.ppl.bloch import EventBloch, Grid, SimConfig, rf_calibration_hz_per_unit  # noqa: E402
from dwfse.ppl.analysis import k_path, b_tensor, ode_crosscheck  # noqa: E402
from dwfse.ppl.events import gradient_pwc  # noqa: E402
from dwfse.vendor_seq import decode  # noqa: E402

OUT = ROOT / "docs/v19/event_validation"
SC = ROOT / "scanner"
V18 = SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl"
CTRL_PPR = ROOT / "experiments/FSE-DWI_10-05-2026_v18_test1e/FSE-DWI_10-05-2026_v18_test1.ppr"
METHODS = {"v191": ("ss-MGOT", SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl"),
           "v192": ("Alsop", SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.92.ppl")}
CONTROLS = {"original": {}, "increasing": {"crusher_schedule": 1, "crusher_step_pct": 40},
            "decreasing": {"crusher_schedule": 4, "crusher_step_pct": 40},
            "alternating": {"crusher_schedule": 2, "crusher_step_pct": 0}}
CONTROL_SOURCE = {"original": "test1e (acquired)", "increasing": "test2b settings (acquired)",
                  "decreasing": "test5 settings (acquired)",
                  "alternating": "schedule 2 on test1e settings (not acquired; simulated control)"}
# Nominal instruction-cost model: EVO manual 4.9.2 expression/access costs x0.8
# (calibrated so v18's own measured window usages, e.g. 5016 and 8236 ticks, are
# reproduced and v18 runs without overruns) plus documented library-call costs.
NOMINAL = {"stmt_cost_us": 0.0, "expr_costs": True, "expr_scale": 0.8}
COST_MODELS = {"flat_0us": {"stmt_cost_us": 0.0}, "flat_0.5us": {"stmt_cost_us": 0.5},
               "flat_1us": {"stmt_cost_us": 1.0}, "flat_2us": {"stmt_cost_us": 2.0},
               "manual_x0.8": NOMINAL, "manual_x0.9": {"stmt_cost_us": 0.0, "expr_costs": True, "expr_scale": 0.9},
               "manual_x1.0": {"stmt_cost_us": 0.0, "expr_costs": True, "expr_scale": 1.0},
               "manual_x0.8_plus_0.5us_stmt": {"stmt_cost_us": 0.5, "expr_costs": True, "expr_scale": 0.8}}
W = 1e-3                     # protocol slice width (m), from gs_var=-1377 at 1070 Hz
Z = (np.arange(3000) + 0.5) / 3000 * 5 * W - 2.5 * W     # 5 x slice width (Gibbons 30/6)
VOXEL_Y = 35e-3 / 136        # phase-axis voxel (FOV 35 mm / 136 views)


def jdump(obj, name):
    (OUT / name).write_text(json.dumps(obj, indent=1, default=float) + "\n")


def pathf(p):
    return str(Path(p).relative_to(ROOT)).replace("\\", "/")


# --------------------------------------------------------------------- mapping
def mapping(ppl, ppr, overrides=None, shots=1, model=None):
    return map_events(ppl, ppr, overrides=overrides or {}, max_shots=shots, **(model or NOMINAL))


def rejected(it):
    return [o for o in it.out if "V19" in o[1] and ("too" in o[1] or "outside" in o[1] or "need" in o[1] or "reject" in o[1] or "must" in o[1])]


# --------------------------------------------------------------------- identity
def event_signature(it, n_shots=2):
    """Relative event ledger of the first n shots (v18 events)."""
    from dwfse.ppl.events import rf_pulses
    rf = [p for p in rf_pulses(it) if p.get("library")]
    if not rf:
        return None
    t0 = rf[0]["t_go"]
    sig = {"rf": [(round(p["t_go"] - t0, 3), p["frame"], p["mul"], p["phase_units"]) for p in rf],
           "adc": [(round(a["t_init"] - t0, 3), round(a["t_complete"] - t0, 3), a["rx_phase_units"],
                    a["Dummy_Cycles"]) for a in it.adc],
           "grad": {}}
    # One-time setup before sync() (deglitch, list building, base matrices) is
    # compared by content only: untimed setup statements shift it in absolute
    # time without affecting any shot event. Everything after sync() is timed.
    ts = it.sync_t
    rel = lambda x: round(x - t0, 3) if x >= ts else "setup"
    for ax in "SPR":
        segs = it.grad.ch[ax].segments
        sig["grad"][ax] = [(rel(a), rel(b) if a >= ts else round(b - a, 3), p, s) for a, b, p, s in segs]
    sig["matrices"] = {m: [(rel(d[0]), d[2], d[3], d[4]) for d in v] for m, v in it.grad.mats.items() if m not in (0, 256)}
    sig["sync_minus_first_rf_us"] = round(ts - t0, 3)
    return sig


def compare_signatures(a, b):
    diffs = {}
    for key in ("rf", "adc"):
        diffs[key] = {"n": (len(a[key]), len(b[key])), "identical": a[key] == b[key]}
    for ax in "SPR":
        diffs["grad_" + ax] = {"n": (len(a["grad"][ax]), len(b["grad"][ax])), "identical": a["grad"][ax] == b["grad"][ax]}
    ma = {k: v for k, v in a["matrices"].items()}
    mb = {k: v for k, v in b["matrices"].items() if k in ma}
    extra = sorted(set(b["matrices"]) - set(a["matrices"]))
    diffs["matrices"] = {"identical_for_v18_ids": ma == mb, "extra_ids": extra}
    diffs["sync_to_first_rf_us"] = (a["sync_minus_first_rf_us"], b["sync_minus_first_rf_us"])
    diffs["all_identical"] = all(v.get("identical", True) for k, v in diffs.items() if isinstance(v, dict) and "identical" in v) and diffs["matrices"]["identical_for_v18_ids"]
    return diffs


# --------------------------------------------------------------------- ledgers
def ledger_rows(it, led, label):
    rows = []
    t0 = next(p["t_center"] for p in led["rf"])
    names = {}
    for n, v in it.vars.items():
        if v.size is None and (n.startswith("v19_l_") or n.endswith("_list") or n in ("slice_180_refocus", "slice_180_refocus_diff", "slice_list_rp")):
            names.setdefault(v.value, n)
    flips = {}
    cal = led["cal"]
    for p in led["rf"]:
        area = float(np.sum(p["amp"])) * p["dt"] * 1e-6 * cal
        rows.append({"event": "RF", "name": p["frame"], "axis": "", "start_us": p["t_go"] - t0,
                     "centre_us": p["t_center"] - t0, "end_us": p["t_go"] + p["duration_us"] - t0,
                     "multiplier": p["mul"], "phase_deg": round(p["phase_deg"], 3),
                     "nominal_flip_deg": round(360 * area, 2), "gated_samples": p["gated_samples"]})
    for t, ax, addr in it.grad.starts:
        if led["t_start"] <= t < led["t_end"]:
            nm = names.get(addr, f"list@{addr}")
            dur = None
            for var in (nm,):
                if var in it.vars:
                    dur = list_duration_us(it, var)
            rows.append({"event": "GRAD", "name": nm, "axis": ax, "start_us": t - t0,
                         "centre_us": "", "end_us": (t + dur - t0) if dur is not None else "",
                         "multiplier": "", "phase_deg": "", "nominal_flip_deg": "", "gated_samples": ""})
    n = it.vars["no_samples"].value
    for k, a in enumerate(led["adc"]):
        sp = a["sample_period_ticks"] / 10
        rows.append({"event": "ADC", "name": f"ADC{k+1}", "axis": "", "start_us": a["t_init"] - t0,
                     "centre_us": a["t_init"] + (a["discard"] + n / 2) * sp - t0,
                     "end_us": a["t_init"] + (a["discard"] + n) * sp - t0,
                     "multiplier": "", "phase_deg": round(a["rx_phase_deg"], 3),
                     "nominal_flip_deg": "", "gated_samples": f"dummy={a['Dummy_Cycles']}"})
    rows.sort(key=lambda r: (r["start_us"], r["event"]))
    for r in rows:
        for k in ("start_us", "centre_us", "end_us"):
            if r[k] != "":
                r[k] = round(r[k], 2)
    with open(OUT / f"timing_{label}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return rows


# --------------------------------------------------------------------- moments
KAPPA = {"v19_slrprep90": 0.5316, "v19_slrtip90": 0.5318, "v19_slrelim90": 0.5309, "v19_reexc90": 0.5547}


def moment_audit(it, led, latency):
    """k-space audit (instantaneous refocusing) in a frame where gradients lag RF by `latency`."""
    led2 = dict(led)
    led2["G"] = {a: type(led["G"][a])(led["G"][a].t + latency, led["G"][a].v) for a in "SPR"}
    rf = led["rf"]
    S = led2["G"]["S"]
    H = led["H"]
    tdp = it.vars["tdp"].value
    D_dac = it.vars["v19_d_dac"].value
    D = dac_us_to_cyc_m(D_dac * (tdp + it.vars["tramp"].value * 1.0096), H)
    ex = rf[0]
    sel = lambda p: S.value_at(p["t_center"])
    k_ex = dac_us_to_cyc_m(KAPPA[ex["frame"]] * sel(ex) * ex["duration_us"], H)
    refs = [p["t_center"] for p in rf if "180" in p["frame"]]
    m = next(p for p in rf if p["frame"] in ("v19_slrelim90", "v19_slrtip90"))
    km = dac_us_to_cyc_m(KAPPA[m["frame"]] * sel(m) * m["duration_us"], H)
    k_in = effective_moment(led2, "S", ex["t_go"] + ex["duration_us"], m["t_go"], refs, k0=k_ex)
    out = {"D_cycles_per_m": D, "frame_latency_us": latency,
           "method_rf": m["frame"], "k_at_method_rf_start": k_in,
           "required_k_at_method_rf_start(D - kappa*G*T)": D - km,
           "input_phase_error_cycles_across_slice": (k_in - (D - km)) * W}
    r = m if m["frame"] == "v19_slrelim90" else next(p for p in rf if p["frame"] == "v19_reexc90")
    k_r = dac_us_to_cyc_m(KAPPA[r["frame"]] * sel(r) * r["duration_us"], H)
    im = [p["t_center"] for p in rf if p["frame"] == "v19_imaging180"]
    adc = [t for _, t in adc_middle_times(it, led)]
    per = []
    for k, tc in enumerate(adc):
        kS = effective_moment(led2, "S", r["t_go"] + r["duration_us"], tc, im, k0=k_r)
        kR = effective_moment(led2, "R", r["t_center"], tc, im)
        kP = effective_moment(led2, "P", r["t_center"], tc, im)
        nxt = (im[k + 1] - 1) if k + 1 < len(im) else None
        k_before = effective_moment(led2, "S", r["t_go"] + r["duration_us"], nxt - 2400, im, k0=k_r) if nxt else None
        kP_rew = effective_moment(led2, "P", r["t_center"], nxt - 2400, im) if nxt else None
        per.append({"adc": k + 1, "k_slice_over_D": kS / D, "k_slice_after_restore_over_D": (k_before / D) if k_before is not None else None,
                    "k_read_cyc_m": kR, "k_phase_cyc_m": kP, "k_phase_after_rewind_cyc_m": kP_rew})
    out["per_adc"] = per
    # crusher symmetry about each imaging RF (moment between ADC centres)
    sym = []
    for k in range(1, len(im)):
        left = dac_us_to_cyc_m(S.integral(adc[k - 1], im[k]), H)
        right = dac_us_to_cyc_m(S.integral(im[k], adc[k]), H)
        sym.append({"rf": k + 1, "left_cyc_m": left, "right_cyc_m": right, "right_minus_left_over_2D": (right - left) / (2 * D)})
    out["crusher_symmetry"] = sym
    return out


# --------------------------------------------------------------------- Bloch
def sim_grid(label):
    ny = 32 if label == "v191" else 1
    y = (np.arange(ny) + 0.5) / ny * VOXEL_Y - VOXEL_Y / 2 if ny > 1 else np.zeros(1)
    return Grid(Z, y)


def physical_landmarks(it, led, latency):
    """List-defined landmarks follow physical gradients; the pre-RF snapshot follows RF."""
    lm = method_landmarks(it, led)
    return {name: t + (0.0 if name == "pre_RF1_after_crusher" else latency) for name, t in lm.items()}


def run_bloch(led, it, label, cal, phase=0.0, b1=1.0, df=0.0, latency=None, relax=None, grid=None,
              snapshots=True, substeps=1):
    lat = it.vars["rfdelay"].value if latency is None else latency
    cfg = SimConfig(b1_scale=b1, df_hz=df, grad_latency_us=lat, extra_phase_deg={0: phase},
                    t1_s=relax[0] if relax else None, t2_s=relax[1] if relax else None)
    g = grid or sim_grid(label)
    sim = EventBloch(led, g, cal, cfg)
    lm = physical_landmarks(it, led, lat) if snapshots and label.startswith("v19") else {}
    adc = adc_middle_times(it, led)
    snaps, ad = sim.run(led["rf"], lm, adc, rf_substeps=substeps)
    dz = (g.z[1] - g.z[0]) / W
    S = [complex(ad[n][0].mean(axis=0).sum() * dz) for n, _ in adc]
    return S, snaps, ad, sim


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t_start = time.time()
    stock = decode(SC / "utilities/rfstd44.seq").frame("3lobe_sinc_3kHz")
    summary = {"status": "nominal source-level PPL-to-event mapping; NOT compiled, NOT console-verified",
               "cost_model": NOMINAL, "inputs": {}}

    # ---------------- mapping of methods and controls
    runs = {}
    for label, (name, ppl) in METHODS.items():
        ppr = ppl.with_suffix(".ppr")
        it = mapping(ppl, ppr)
        led = build_ledger(it, 1)
        led["cal"] = rf_calibration_hz_per_unit(stock.samples, stock.wait_ticks / 10, it.vars["rfcal"].value)
        runs[label] = (it, led)
        summary["inputs"][label] = it.inputs
    for cname, ov in CONTROLS.items():
        it = mapping(V18, CTRL_PPR, ov)
        led = build_ledger(it, 1)
        led["cal"] = rf_calibration_hz_per_unit(stock.samples, stock.wait_ticks / 10, it.vars["rfcal"].value)
        runs["v18_" + cname] = (it, led)
    summary["inputs"]["v18"] = runs["v18_original"][0].inputs

    # ---------------- method-only PPLs: controls run on v18 itself. A control
    # setting (v19_on=0) must stop before any RF, gradient list start or ADC.
    ident = {}
    for label, (_, ppl) in METHODS.items():
        it = mapping(ppl, ppl.with_suffix(".ppr"), {"v19_on": 0}, shots=2)
        ident[label] = {"v19_on0_rejected": it.vars["v19_error_code"].value != 0,
                        "rf_events": len(it.rf.events), "adc_events": len(it.adc),
                        "all_identical": it.vars["v19_error_code"].value != 0 and not it.adc
                        and not [e for e in it.rf.events if e.get("library")]}
    jdump(ident, "control_identity.json")
    summary["control_identity_all"] = all(v["all_identical"] for v in ident.values())

    # ---------------- ledgers, hazards, timing sensitivity
    hazards = {}
    timing = {}
    for label, (it, led) in runs.items():
        rows = ledger_rows(it, led, label)
        kinds = {}
        for f in it.flags:
            kinds.setdefault(f["kind"], []).append(f["msg"])
        hazards[label] = {k: {"count": len(v), "examples": sorted(set(v))[:6]} for k, v in kinds.items()}
        grad_issues = {a: len(led["issues"][a]) for a in "SPR"}
        hazards[label]["matrix_use_issues"] = grad_issues
        hazards[label]["setlist_ignored"] = sum(1 for f in it.flags if "ignored" in f["msg"])
        hazards[label]["timer_overruns"] = sum(1 for f in it.flags if f["kind"] == "timer_overrun")
        rfc = [r["centre_us"] for r in rows if r["event"] == "RF"]
        timing[label] = {"rf_centres_us": rfc, "adc_centres_us": [r["centre_us"] for r in rows if r["event"] == "ADC"],
                         "printed": [o[1].strip() for o in it.out if "V19" in o[1] or "TE" in o[1] or "TR" in o[1]][:12]}
    # statement-cost sensitivity of the method paths
    for label, (name, ppl) in METHODS.items():
        sens = {}
        for cost, model in COST_MODELS.items():
            it = mapping(ppl, ppl.with_suffix(".ppr"), model=model)
            led = build_ledger(it, 1)
            c = [p["t_center"] for p in led["rf"]]
            sens[str(cost)] = {"rf_centres_rel_us": [round(x - c[0], 2) for x in c],
                               "overruns": sum(1 for f in it.flags if f["kind"] == "timer_overrun"),
                               "setlist_ignored": sum(1 for f in it.flags if "ignored" in f["msg"]),
                               "rejected": rejected(it)}
        timing[label]["stmt_cost_sensitivity"] = sens
    sens = {}
    for cost, model in COST_MODELS.items():
        it = mapping(V18, CTRL_PPR, model=model)
        try:
            led = build_ledger(it, 1)
            c = [p["t_center"] for p in led["rf"]]
        except Exception:
            c = []
        sens[cost] = {"rf_centres_rel_us": [round(x - c[0], 2) for x in c] if c else [],
                      "overruns": sum(1 for f in it.flags if f["kind"] == "timer_overrun"),
                      "setlist_ignored": sum(1 for f in it.flags if "ignored" in f["msg"]),
                      "aborts": [o[1].strip() for o in it.out if "exceed" in o[1] or "error" in o[1].lower()]}
    timing["v18_original_cost_sensitivity"] = sens
    jdump(hazards, "hazards.json")
    jdump(timing, "timing_summary.json")

    # ---------------- rejection tests (each must stop before any event)
    rej = {}
    tests = {"3D": {"no_views_2": 2}, "multislice": {"no_slices": 2}, "slice offset": {"slice_mm_10": 10},
             "presat": {"sat_on": 1}, "flow comp": {"flow_comp_on": 1}, "DE": {"de_on": 1},
             "gating": {"gating": 1}, "crusher schedule": {"crusher_schedule": 1},
             "crusher too small": {"crush_amp": -2741}, "TE too short": {"te": 52},
             "ESP too short": {"esp": 11}, "flip out of range": {"v19_flip_tenths": [0] * 8},
             "TR too short": {"tr": 150}, "cycles not validated": {"v19_cycles": 4},
             "C1 small coincidence": {"diff_crush_amp": -1500},
             "C1 large coincidence": {"diff_crush_amp": -12000},
             "C outside validated window": {"crush_amp": -7700},
             "C1 opposite polarity": {"diff_crush_amp": 5482},
             "crusher polarity not validated": {"crush_amp": 8223, "diff_crush_amp": 5482}}
    for label, (name, ppl) in METHODS.items():
        rej[label] = {}
        for tname, ov in tests.items():
            it = mapping(ppl, ppl.with_suffix(".ppr"), ov)
            from dwfse.ppl.events import rf_pulses
            n_rf = len([p for p in rf_pulses(it) if p.get("library")])
            rej[label][tname] = {"rf_events": n_rf, "adc_events": len(it.adc),
                                 "message": (it.out[-1][1].strip() if it.out else "")}
            assert n_rf == 0 and len(it.adc) == 0, (label, tname, rej[label][tname])
    jdump(rej, "rejection_tests.json")

    # ---------------- moments (commanded and physical frames)
    moments = {}
    for label in METHODS:
        it, led = runs[label]
        moments[label] = {"commanded_frame": moment_audit(it, led, 0.0),
                          "physical_frame_latency_rfdelay": moment_audit(it, led, float(it.vars["rfdelay"].value))}
    jdump(moments, "moments.json")

    # ---------------- b-tensors for b rows 0/1000/6000
    btab = {}
    for label in list(METHODS) + ["v18_original"]:
        btab[label] = {}
        for b in (0, 1000, 6000):
            if label in METHODS:
                ppl = METHODS[label][1]
                it = mapping(ppl, ppl.with_suffix(".ppr"), {"acq_b": [b, 1000, 6000]})
            else:
                it = mapping(V18, CTRL_PPR, {"acq_b": [b, 1000, 6000]})
            led = build_ledger(it, 1)
            rf = led["rf"]
            lat = float(it.vars["rfdelay"].value)
            t0 = rf[0]["t_center"]
            if label in METHODS:
                flips = [p["t_center"] for p in rf if "180" in p["frame"]]
            else:
                flips = [p["t_center"] for p in rf[1:]]   # v18: every RF after the excitation refocuses
            frozen = []
            if label == "v191":
                tip = next(p for p in rf if p["frame"] == "v19_slrtip90")
                re = next(p for p in rf if p["frame"] == "v19_reexc90")
                frozen = [(tip["t_center"], re["t_center"])]
            adc = adc_middle_times(it, led)
            res = []
            method_rf = next((p for p in rf if p["frame"] in ("v19_slrelim90", "v19_reexc90")), None)
            for n, tc in adc[:3] + adc[-1:]:
                branches = [("carrier", flips)]
                if method_rf is not None:
                    branches.append(("conjugate", flips + [method_rf["t_center"]]))
                candidates = []
                for branch, branch_flips in branches:
                    t, k = k_path(led, t0, tc, branch_flips, frozen, dt_us=2.0, latency_us=lat)
                    B = b_tensor(t, k)
                    candidates.append((float(np.linalg.norm(k[-1])), branch, B, k))
                _, branch, B, k = min(candidates, key=lambda item: item[0])
                res.append({"adc": n, "t_from_exc_us": tc - t0, "selected_branch": branch,
                            "b_SS": B[0, 0], "b_PP": B[1, 1], "b_RR": B[2, 2],
                            "trace": float(np.trace(B)), "k_end_cyc_m": k[-1].tolist(),
                            "candidate_branches": [{"branch": c[1], "k_end_cyc_m": c[3][-1].tolist(),
                                                    "b_SS": float(c[2][0, 0]), "b_RR": float(c[2][2, 2])}
                                                   for c in candidates]})
            btab[label][str(b)] = {"diff_dac": int(it.vars["diff_grad"].value), "echoes": res}
    jdump(btab, "btensor.json")

    # ---------------- Bloch sweep
    phases = (0.0, 45.0, 90.0)
    b1s = (1.0, 0.8)
    b0s = (-128.0, 0.0, 128.0)
    if args.quick:
        b0s = (0.0,)
    bloch = {}
    profiles = {}
    for label in list(METHODS) + [f"v18_{c}" for c in CONTROLS]:
        it, led = runs[label]
        bloch[label] = []
        for ph in phases:
            for b1 in b1s:
                for df in b0s:
                    if label.startswith("v18") and (df != 0.0):
                        continue
                    S, snaps, ad, sim = run_bloch(led, it, label, led["cal"], ph, b1, df,
                                                  snapshots=(label in METHODS and b1 == 1.0 and df == 0.0))
                    bloch[label].append({"phase_deg": ph, "b1": b1, "df_hz": df,
                                         "abs": [abs(s) for s in S], "angle_deg": [float(np.angle(s, deg=True)) for s in S],
                                         "gradient_change_inside_rf_samples": getattr(sim, "gradient_change_in_rf", 0)})
                    if snaps:
                        profiles[(label, ph)] = (snaps, {n: ad[n] for n in ("ADC1", "ADC2", f"ADC{len(ad)}")})
        # relaxation (Gibbons Figure 4 muscle constants) at nominal B1/B0
        for ph in phases:
            S, *_ = run_bloch(led, it, label, led["cal"], ph, 1.0, 0.0, relax=(1.300, 0.032), snapshots=False)
            bloch[label].append({"phase_deg": ph, "b1": 1.0, "df_hz": 0.0, "T1_s": 1.3, "T2_s": 0.032,
                                 "abs": [abs(s) for s in S], "angle_deg": [float(np.angle(s, deg=True)) for s in S]})
        # latency sensitivity (commanded frame)
        S, *_ = run_bloch(led, it, label, led["cal"], 45.0, 1.0, 0.0, latency=0.0, snapshots=False)
        bloch[label].append({"phase_deg": 45.0, "b1": 1.0, "df_hz": 0.0, "grad_latency_us": 0.0,
                             "abs": [abs(s) for s in S]})
    jdump(bloch, "bloch_results.json")

    # landmark profile summaries + npz
    prof_json = {}
    for (label, ph), (snaps, ads) in profiles.items():
        arr = {}
        prof_json.setdefault(label, {})[str(ph)] = {}
        inside = np.abs(Z) < W / 2
        for n, (m, mz) in list(snaps.items()) + list(ads.items()):
            local = m[m.shape[0] // 2]          # one phase-axis isochromat column
            mean = m.mean(axis=0)               # coherent mean over the phase voxel
            mzl = mz[mz.shape[0] // 2]
            arr[f"{n}_local_mx"] = local.real
            arr[f"{n}_local_my"] = local.imag
            arr[f"{n}_local_mz"] = mzl
            arr[f"{n}_mean_mxy"] = mean
            arr[f"{n}_mean_mz"] = mz.mean(axis=0)
            prof_json[label][str(ph)][n] = {
                "slice_coherent_mean_mxy_abs": abs(mean[inside].mean()),
                "slice_coherent_mean_mx": mean[inside].mean().real, "slice_coherent_mean_my": mean[inside].mean().imag,
                "slice_mean_local_abs_mxy": float(np.abs(local[inside]).mean()),
                "slice_mean_mz": float(mzl[inside].mean())}
        np.savez_compressed(OUT / f"profiles_{label}_phase{int(ph):03d}.npz", z_m=Z, **arr)
    jdump(prof_json, "landmark_summary.json")

    # ---------------- convergence and independent checks
    conv = {}
    for label in METHODS:
        it, led = runs[label]
        ref, *_ = run_bloch(led, it, label, led["cal"], 45.0, snapshots=False)
        z2 = (np.arange(6000) + 0.5) / 6000 * 5 * W - 2.5 * W
        g2 = Grid(z2, sim_grid(label).y)
        fine, *_ = run_bloch(led, it, label, led["cal"], 45.0, grid=g2, snapshots=False)
        sub, *_ = run_bloch(led, it, label, led["cal"], 45.0, snapshots=False, substeps=4)
        conv[label] = {"z3000_vs_z6000_max_abs_diff": float(np.max(np.abs(np.array(ref) - np.array(fine)))),
                       "rf_substeps1_vs_4_max_abs_diff": float(np.max(np.abs(np.array(ref) - np.array(sub))))}
        if label == "v191":
            g3 = Grid(Z, (np.arange(64) + 0.5) / 64 * VOXEL_Y - VOXEL_Y / 2)
            y64, *_ = run_bloch(led, it, label, led["cal"], 45.0, grid=g3, snapshots=False)
            conv[label]["y32_vs_y64_max_abs_diff"] = float(np.max(np.abs(np.array(ref) - np.array(y64))))
        # independent ODE through the method RF and first imaging echo for 5 spins
        cfg = SimConfig(grad_latency_us=float(it.vars["rfdelay"].value), extra_phase_deg={0: 45.0})
        sim = EventBloch(led, Grid(np.array([-0.4e-3, -0.1e-3, 0.0, 0.2e-3, 0.45e-3]), np.zeros(1)), led["cal"], cfg)
        lm = physical_landmarks(it, led, float(it.vars["rfdelay"].value))
        t_a = lm["B_after_dephasing"]
        t_b = adc_middle_times(it, led)[0][1]
        snaps, ad = sim.run(led["rf"], {"a": t_a}, [("b", t_b)])
        m0, mz0 = snaps["a"][0][0], snaps["a"][1][0]
        ode = ode_crosscheck(led, led["rf"], led["cal"], sim.grid.z, t_a, t_b, cfg, m0, mz0)
        eng = np.stack([ad["b"][0][0].real, ad["b"][0][0].imag, ad["b"][1][0]], axis=1)
        conv[label]["ode_vs_exact_rotation_max_component_diff"] = float(np.max(np.abs(ode - eng)))
        conv[label]["ode_window_us"] = [t_a, t_b]
        # snapshot/ADC agreement: echo peak position inside the ADC window
        it_, led_ = runs[label]
        n = it_.vars["no_samples"].value
        a = led_["adc"][0]
        sp = a["sample_period_ticks"] / 10
        times = [(f"s{i}", a["t_init"] + (a["discard"] + i) * sp) for i in range(n)]
        # Intravoxel off-resonance spread (uniform +/-150 Hz, 15 values) makes the
        # spin-echo peak resolvable; the slice-coherent echo is summed over it.
        dz = (Z[1] - Z[0]) / W
        acc = np.zeros(n, complex)
        gy = Grid(Z, (np.arange(8) + 0.5) / 8 * VOXEL_Y - VOXEL_Y / 2) if label == "v191" else sim_grid(label)
        for df in np.linspace(-150, 150, 15):
            sim = EventBloch(led_, gy, led_["cal"], SimConfig(grad_latency_us=float(it_.vars["rfdelay"].value), extra_phase_deg={0: 45.0}, df_hz=df))
            _, ad = sim.run(led_["rf"], {}, times)
            acc += np.array([ad[k][0].mean(axis=0).sum() * dz for k, _ in times])
        sig = np.abs(acc) / 15
        tt = np.array([t for _, t in times])
        conv[label]["adc1_peak_offset_from_middle_us"] = float(tt[int(np.argmax(sig))] - tt[n // 2])
        # parabolic refinement of the peak position
        i = int(np.argmax(sig))
        if 0 < i < n - 1:
            d = 0.5 * (sig[i - 1] - sig[i + 1]) / (sig[i - 1] - 2 * sig[i] + sig[i + 1])
            conv[label]["adc1_peak_offset_refined_us"] = float(tt[i] + d * sp - tt[n // 2])
        conv[label]["adc1_peak_sample_index"] = int(np.argmax(sig))
        conv[label]["adc1_middle_sample_index"] = n // 2
        conv[label]["adc1_middle_over_peak"] = float(sig[n // 2] / sig.max())
        np.save(OUT / f"adc1_slice_echo_{label}.npy", sig)
    jdump(conv, "convergence.json")

    # ---------------- figures
    make_figures(runs, bloch, profiles)

    summary["elapsed_s"] = time.time() - t_start
    summary["outputs"] = sorted(p.name for p in OUT.iterdir())
    jdump(summary, "summary.json")
    print(json.dumps({"identity": summary["control_identity_all"], "elapsed_s": summary["elapsed_s"]}, indent=1))


def make_figures(runs, bloch, profiles):
    from dwfse.ppl.events import rf_pulses
    for label in METHODS:
        it, led = runs[label]
        t0 = led["rf"][0]["t_center"]
        t1 = led["adc"][1]["t_complete"] + 3000
        fig, axs = plt.subplots(5, 1, figsize=(13, 9), sharex=True)
        for p in led["rf"]:
            axs[0].plot((p["t"] - t0) / 1e3, p["amp"] * led["cal"] / 42.576, lw=0.8)
        axs[0].set_ylabel("B1 (uT, inferred)")
        tt = np.arange(led["rf"][0]["t_go"] - 3000, t1, 2.0)
        for ax, a in zip(axs[1:4], "SPR"):
            g = led["G"][a].sample(tt) / 32767 * led["H"] * 1e3 / 42.576e3   # mT/m
            ax.plot((tt - t0) / 1e3, g, lw=0.7)
            ax.set_ylabel(f"G{a.lower()} (mT/m)")
        for a in led["adc"]:
            axs[4].axvspan((a["t_init"] - t0) / 1e3, (a["t_complete"] - t0) / 1e3, color="tab:green", alpha=0.3)
        axs[4].set_ylabel("ADC")
        axs[4].set_xlabel("time from preparation-excitation RF centre (ms)")
        axs[0].set_title(f"{label} ({METHODS[label][0]}): mapped commanded events, first shot (nominal source mapping)")
        fig.tight_layout()
        fig.savefig(OUT / f"diagram_{label}.png", dpi=130)
        axs[0].set_xlim(-3, (led["adc"][1]["t_complete"] - t0) / 1e3)
        for ax in axs:
            ax.set_xlim(((led["rf"][2]["t_go"] - t0) / 1e3) - 6, (led["adc"][1]["t_complete"] - t0) / 1e3 + 1)
        fig.savefig(OUT / f"diagram_{label}_zoom.png", dpi=130)
        plt.close(fig)
    # echo amplitudes
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.2), sharey=True)
    for ax, b1 in zip(axs, (1.0, 0.8)):
        for label, res in bloch.items():
            for r in res:
                if r.get("T1_s") or r.get("grad_latency_us") is not None:
                    continue
                if r["b1"] == b1 and r["df_hz"] == 0.0:
                    ls = {0.0: "-", 45.0: "--", 90.0: ":"}[r["phase_deg"]]
                    col = {"v191": "tab:blue", "v192": "tab:red"}.get(label, None)
                    if label.startswith("v18"):
                        col = {"v18_original": "0.2", "v18_increasing": "0.4", "v18_decreasing": "0.6", "v18_alternating": "0.8"}[label]
                    ax.plot(range(1, len(r["abs"]) + 1), r["abs"], ls, color=col, label=f"{label} {int(r['phase_deg'])}deg")
        ax.set_title(f"slice-coherent |signal| at ADC middle samples, B1 x{b1}")
        ax.set_xlabel("echo")
    axs[0].set_ylabel("|S| / ideal full-slice signal")
    axs[1].legend(fontsize=6, ncol=2)
    fig.tight_layout()
    fig.savefig(OUT / "echo_amplitudes.png", dpi=130)
    plt.close(fig)
    # landmark profiles
    for (label, ph), (snaps, ads) in profiles.items():
        items = list(snaps.items()) + list(ads.items())
        fig, axs = plt.subplots(len(items), 2, figsize=(12, 2.0 * len(items)), sharex=True)
        for i, (n, (m, mz)) in enumerate(items):
            local = m[m.shape[0] // 2]
            mean = m.mean(axis=0)
            axs[i, 0].plot(Z * 1e3, local.real, lw=0.6, label="Mx")
            axs[i, 0].plot(Z * 1e3, local.imag, lw=0.6, label="My")
            axs[i, 0].plot(Z * 1e3, mz[mz.shape[0] // 2], lw=0.6, label="Mz")
            axs[i, 0].set_ylabel(n, fontsize=7)
            axs[i, 1].plot(Z * 1e3, mean.real, lw=0.6)
            axs[i, 1].plot(Z * 1e3, mean.imag, lw=0.6)
            axs[i, 1].plot(Z * 1e3, mz.mean(axis=0), lw=0.6)
            for a in axs[i]:
                a.axvspan(-0.5, 0.5, color="0.9", zorder=0)
                a.set_ylim(-1.05, 1.05)
        axs[0, 0].set_title("local isochromat column (signed Mx/My/Mz)")
        axs[0, 1].set_title("coherent mean over the phase-axis voxel")
        axs[0, 0].legend(fontsize=6)
        axs[-1, 0].set_xlabel("z (mm)")
        axs[-1, 1].set_xlabel("z (mm)")
        fig.suptitle(f"{label} landmarks, initial phase {int(ph)} deg, B1 nominal, B0 0 Hz (event-driven Bloch)")
        fig.tight_layout()
        fig.savefig(OUT / f"profiles_{label}_phase{int(ph):03d}.png", dpi=110)
        plt.close(fig)


if __name__ == "__main__":
    main()
