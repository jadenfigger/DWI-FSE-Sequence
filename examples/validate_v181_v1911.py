"""Independent, additive event-gate validation of the v1.81 / v1.911 candidates.

Every result is a source-model mapping of the actual PPL/PPR bytes through
dwfse/ppl (interpreter cost models, assumed RF latency and PPR rfdelay as the
gradient lag). It is neither vendor compilation nor console/scanner timing,
and the ledger does not rotate physical oblique axes.

Inputs are read fresh on each run and the SHA-256 of every PPL/PPR is recorded
next to every result, because candidate bytes may change between runs.

Gate families (all written to docs/v181_v1911/validation/event_gates.json):
  * coverage: actual imaging (no_disacq=0, nav_on=0, no_views=128; 2 shots),
    diffusion-row progression (no_views=16 -> 2 shots/row, 6 shots = 3 rows) and
    unmodified default PPR mapped through 6 shots (dummy/navigator + imaging);
  * all eight cost models: timer overruns, ignored lists, actual premature
    matrix use (raw inherited ``matrix_active`` notices are reported separately);
  * ADC/RF structure, constant ESP, ADC-vs-imaging-RF midpoint pairing
    (v1.8 family: ADC1 follows the diffusion 180, ADC2.. pair with train RFs);
  * method/geometry/orientation/overflow rejections before any RF or ADC;
  * per RF/ADC interval gradient areas vs baseline (bounded integer-DAC error),
    selected-branch k endpoints, crusher area ratios, fused-lobe overlap with
    RF and the whole receiver busy interval, and the v1.911 final ADC ->
    terminal -D -> exit moments, timer anchors and minimum TR.

The finite-RF Bloch grid is NOT run here (``--bloch`` runs the legacy grid);
by default it is recorded as ``not_run`` and never counted as a pass.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import re
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dwfse.ppl.run import map_events  # noqa: E402
from dwfse.ppl.ledger import build_ledger, adc_middle_times, dac_us_to_cyc_m  # noqa: E402
from dwfse.ppl.analysis import k_path, b_tensor  # noqa: E402
from examples import v19_validate_events as old  # noqa: E402

OUT = ROOT / "docs/v181_v1911/validation"
SC = ROOT / "scanner"
V7 = ROOT / "docs/v181_v1911/baseline_v7/FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl"
SOURCES = {
    "v18": (old.V18, old.CTRL_PPR),
    "v181": (SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl", SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppr"),
    "v191_v7": (V7, V7.with_suffix(".ppr")),
    "v1911": (SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl", SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppr"),
}
BASELINE_OF = {"v181": "v18", "v1911": "v191_v7"}
CANDIDATES = ("v181", "v1911")
# Coverage states. Overrides are applied on top of each source's own PPR.
STATES = {
    "imaging": ({"no_disacq": 0, "nav_on": 0, "no_views": 128}, 2),
    "diffusion_rows": ({"no_disacq": 0, "nav_on": 0, "no_views": 16}, 6),
    "default_ppr": ({}, 6),
    # Four rows (b0, then b1000 along x, y, z) mapped through 8 shots.
    "diffusion_directions": ({"no_disacq": 0, "nav_on": 0, "no_views": 16, "no_diff_acq": 4,
                              "no_experiments": 4,
                              "acq_b": [0, 1000, 1000, 1000] + [0] * 60,
                              "acq_x": [1000, 1000, 0, 0] + [0] * 60,
                              "acq_y": [0, 0, 1000, 0] + [0] * 60,
                              "acq_z": [0, 0, 0, 1000] + [0] * 60}, 8),
}
IMAGING = STATES["imaging"][0]
METHOD_REJECTIONS = {
    "3D": {"no_views_2": 2}, "multislice": {"no_slices": 2},
    "slice offset": {"slice_mm_10": 10}, "presat": {"sat_on": 1},
    "flow comp": {"flow_comp_on": 1}, "DE": {"de_on": 1}, "gating": {"gating": 1},
    "crusher schedule": {"crusher_schedule": 1}, "crusher too small": {"crush_amp": -2741},
    "TE too short": {"te": 52}, "original ESP too short": {"esp": 11}, "ESP below new floor": {"esp": 9},
    "flip out of range": {"v19_flip_tenths": [0] * 8}, "TR too short": {"tr": 150},
    "cycles not validated": {"v19_cycles": 4}, "C1 small coincidence": {"diff_crush_amp": -1500},
    "C1 large coincidence": {"diff_crush_amp": -12000},
    "C outside validated window": {"crush_amp": -7700},
    "C1 opposite polarity": {"diff_crush_amp": 5482},
    "crusher polarity not validated": {"crush_amp": 8223, "diff_crush_amp": 5482},
    "method off": {"v19_on": 0}, "method invalid": {"v19_on": 2},
    "zero diffusion rows": {"no_diff_acq": 0}, "too many diffusion rows": {"no_diff_acq": 65},
}
# New v1.911-only guards: geometry/orientation (E146), fixed fused-lobe timing
# (E140), ESP12 (E144) and signed-32 area overflow / DAC bounds (E145/E141).
V1911_REJECTIONS = {
    "subject angle x": {"subj_angle_x": 10}, "subject angle y": {"subj_angle_y": 10},
    "subject angle z": {"subj_angle_z": 10},
    "read angle": {"r_angle_var": [10]}, "phase angle": {"p_angle_var": [10]},
    "slice angle": {"s_angle_var": [10]}, "phase orientation swap": {"phase_var": 1},
    "tramp changed": {"tramp": 300}, "tdp changed (via tref_setup)": {"tref_setup": 800},
    "tcrush changed": {"tcrush": 1200}, "rfdelay changed": {"rfdelay": 50},
    "ESP12": {"esp": 12},
    "crusher area overflow / fused DAC bound": {"crush_amp": -32767},
    "crusher at DAC limit positive": {"crush_amp": 32767},
}
V181_REJECTIONS = {"CEST/MTC": {"mtc_on": 1}, "diffusion with flow comp": {"flow_comp_on": 1}}
TOL = {
    "esp_variation_us": 1.0,
    "adc_rf_midpoint_us": 25.0,
    # One DAC unit for one ramped 1.2-ms lobe is ~2.5e-5 cycles/mm; the earlier
    # reported per-boundary maximum was 1.1753e-4 cycles across 1 mm.
    "interval_area_cycles_per_mm": 2.5e-4,
    "endpoint_cycles_per_mm": 1.5e-3,
    "v181_read_endpoint_cycles_per_m": 0.5,
    "crusher_ratio_rel": 0.02,
}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def jdefault(x):
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, (tuple, set)):
        return list(x)
    return str(x)


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, indent=1, default=jdefault) + "\n")


def is_method(rf):
    """Detect ss-MGOT from RF frame names (never from absent stage variables)."""
    return any(str(p["frame"]).startswith("v19_") for p in rf)


def mapping(label, overrides=None, model=None, shots=1, rf_latency=3.0):
    ppl, ppr = SOURCES[label]
    it = map_events(ppl, ppr, overrides=dict(overrides or {}), max_shots=shots,
                    rf_latency_us=rf_latency, **(model or old.NOMINAL))
    it.inputs["RF_latency_assumed_us"] = rf_latency
    return it


def shot_ledgers(it):
    """Per-shot ledgers sharing one gradient reconstruction (shots with RF)."""
    base = build_ledger(it, 1)
    shots = [e[1] for e in it.misc_events if e[0] == "shot"]
    out = []
    for i, t0 in enumerate(shots):
        t1 = shots[i + 1] if i + 1 < len(shots) else it.t
        rf = [p for p in _rf_all(it) if t0 <= p["t_go"] < t1]
        adc = [a for a in it.adc if t0 <= a["t_init"] < t1]
        if not rf and not adc:
            continue
        out.append({**base, "rf": rf, "adc": adc, "t_start": t0, "t_end": t1, "shot": i + 1})
    return base, out


_RF_CACHE = {}


def _rf_all(it):
    key = id(it)
    if key not in _RF_CACHE:
        from dwfse.ppl.events import rf_pulses
        _RF_CACHE.clear()
        _RF_CACHE[key] = [p for p in rf_pulses(it) if p.get("library")]
    return _RF_CACHE[key]


def structure(it, led):
    """Refocuser/ADC pairing. v18 family: rf[0] exc, rf[1] diffusion 180,
    rf[2:] train; ADC1 follows the diffusion 180 and ADC2.. sit between train
    RFs. Method: imaging pairs are the v19_imaging180 frames, all ADCs."""
    rf = led["rf"]
    adc = [t for _, t in adc_middle_times(it, led)]
    method = is_method(rf)
    if method:
        train = [p for p in rf if p["frame"] == "v19_imaging180"]
        adc_off = 0
    else:
        train = rf[2:]
        adc_off = 1
    c = np.array([p["t_center"] for p in train])
    mid = [float(adc[i + adc_off] - (c[i] + c[i + 1]) / 2)
           for i in range(min(len(adc) - adc_off, len(c) - 1))]
    t_ex = rf[0]["t_center"] if rf else 0.0
    return {"method": method, "RF_count": len(rf), "ADC_count": len(adc),
            "RF_frames": [p["frame"] for p in rf],
            "train_RF_spacing_us": np.diff(c).tolist(),
            "ADC_minus_train_RF_midpoint_us": mid,
            "ADC_pairing": "ADC[i] with train RF i,i+1" if method else "ADC1 after diffusion 180; ADC[i+1] with train RF i,i+1",
            "RF_centers_from_excitation_us": [p["t_center"] - t_ex for p in rf],
            "ADC_centers_from_excitation_us": [t - t_ex for t in adc]}


def hazards(it, issues):
    raw_active = [f for f in it.flags if f["kind"] == "matrix_active"]
    return {"timer_overruns": [f for f in it.flags if f["kind"] == "timer_overrun"],
            "ignored_lists": [f for f in it.flags if "ignored" in f["msg"]],
            "premature_matrix_use": {a: [(float(t), m) for t, m in v] for a, v in issues.items() if v},
            "raw_matrix_active_notices": len(raw_active),
            "raw_matrix_active_note": "CREATE_MATRIX while the same id is selected; counted only as a hazard when a nonzero sample uses it before DSP-ready (premature_matrix_use).",
            "other_flag_kinds": sorted({f["kind"] for f in it.flags} - {"matrix_active", "timer_overrun"})}


def adc_states(it):
    return [{k: a["vars"].get(k) for k in ("current_view", "gp_mul", "nav_cnt", "diff_acq_cnt", "disacq_cnt", "echo_cnt")}
            | {"dummy": a.get("Dummy_Cycles")} for a in it.adc]


def diffusion_peaks(led, shift):
    """Peak |G| and integral |G|dt per axis between excitation and first ADC."""
    t0 = led["rf"][0]["t_center"]
    t1 = led["adc"][0]["t_init"] if led["adc"] else led["t_end"]
    out = {}
    for a in "SPR":
        g = led["G"][a]
        m = (g.t[:-1] + shift < t1) & (g.t[1:] + shift > t0)
        out[a] = float(np.max(np.abs(g.v[m]))) if m.any() else 0.0
        lo = np.clip(g.t[:-1] + shift, t0, t1)
        hi = np.clip(g.t[1:] + shift, t0, t1)
        out["abs_area_" + a] = float(np.sum(np.abs(g.v) * (hi - lo)))
    return out


def run_job(job):
    """One (source, cost model, state) mapping -> gate metrics (picklable)."""
    label, model_name, state = job
    overrides, shots = STATES[state]
    model = old.COST_MODELS[model_name]
    it = mapping(label, overrides, model, shots)
    base, leds = shot_ledgers(it)
    shift = float(it.vars["rfdelay"].value)
    res = {"inputs": {"ppl_sha256": it.inputs["ppl_sha256"], "ppr_sha256": it.inputs["ppr_sha256"],
                      "overrides": overrides, "shots_mapped": shots, "cost_model": model_name},
           "hazards": hazards(it, base["issues"]), "adc_states": adc_states(it),
           "shots": [], "messages_tail": [m for _, m in it.out[-3:]]}
    for led in leds:
        s = structure(it, led)
        s["shot"] = led["shot"]
        if led["rf"]:
            s["diffusion_window_peak_DAC"] = diffusion_peaks(led, shift)
        s["ADC_vars"] = [{k: a["vars"].get(k) for k in ("current_view", "gp_mul", "nav_cnt", "diff_acq_cnt")} for a in led["adc"]]
        res["shots"].append(s)
    if label == "v1911" or label == "v191_v7":
        res["terminal"] = terminal_audit(it, leds, shift)
    return label, model_name, state, res


# ------------------------------------------------------------ moment audits
def interval_areas(it, led, shift):
    """Per-axis area (cycles/m) between consecutive RF/ADC centres, plus the
    final ADC -> shot end interval (terminal restoration)."""
    ev = [("RF:" + p["frame"], p["t_center"]) for p in led["rf"]]
    ev += [(n, t) for n, t in adc_middle_times(it, led)]
    ev.sort(key=lambda e: e[1])
    ev.append(("shot_end", led["t_end"]))
    rows = []
    for (na, a), (nb, b) in zip(ev[:-1], ev[1:]):
        rows.append({"from": na, "to": nb, "duration_us": b - a,
                     **{ax: dac_us_to_cyc_m(led["G"][ax].integral(a - shift, b - shift), led["H"]) for ax in "SPR"}})
    return rows


def exact_k(led, t0, t1, flips, frozen, shift):
    """Exact piecewise-constant k (cycles/m, S/P/R) at t1 along one branch:
    instantaneous conjugation at each flip, no accrual inside frozen spans.
    (A sampled k_path at 2-us steps carries up to ~1 us of edge error per
    lobe, ~6 cycles/m at 8223 DAC, so it is not used for endpoint gates.)"""
    cuts = sorted({t0, t1, *[f for f in flips if t0 < f < t1],
                   *[x for a, b in frozen for x in (a, b) if t0 < x < t1]})
    k = np.zeros(3)
    for a, b in zip(cuts[:-1], cuts[1:]):
        if a in set(flips):
            k = -k
        if any(fa <= a and b <= fb for fa, fb in frozen):
            continue
        k = k + np.array([dac_us_to_cyc_m(led["G"][ax].integral(a - shift, b - shift), led["H"]) for ax in "SPR"])
    return k.tolist()


def selected_k(it, led, shift, dt_us=2.0):
    """Selected carrier/conjugate branch k at each ADC centre and at shot end."""
    rf = led["rf"]
    method = is_method(rf)
    if method:
        flips = [p["t_center"] for p in rf if "180" in p["frame"]]
        tip = next(p for p in rf if p["frame"] == "v19_slrtip90")
        re_ = next(p for p in rf if p["frame"] == "v19_reexc90")
        frozen = [(tip["t_center"], re_["t_center"])]
        branches = [("carrier", flips), ("conjugate", flips + [re_["t_center"]])]
    else:
        flips = [p["t_center"] for p in rf[1:]]
        frozen = []
        branches = [("carrier", flips)]
    t0 = rf[0]["t_center"]
    targets = [(n, t) for n, t in adc_middle_times(it, led)] + [("shot_end", led["t_end"] - 1.0)]
    out = []
    for name, t1 in targets:
        cands = []
        for bname, fl in branches:
            cands.append({"branch": bname, "k_cycles_m": exact_k(led, t0, t1, fl, frozen, shift)})
        sel = min(cands[:-1] if name == "shot_end" and len(cands) > 1 else cands,
                  key=lambda c: np.linalg.norm(c["k_cycles_m"]))
        out.append({"at": name, "selected": sel, "candidates": cands})
    return out


def overlap_secondary_S(led, shift, a, b):
    """Duration and peak of nonzero *secondary* (added crusher/fused) S output
    overlapping [a, b] in physical time. Primary selector during selective RF is
    excluded by construction."""
    segs = led["_segS"]
    dur, peak = 0.0, 0.0
    for t0, t1, prim, sec, val in segs:
        if sec == 0 or val == 0:
            continue
        lo, hi = max(t0 + shift, a), min(t1 + shift, b)
        if hi > lo + 1e-8:
            dur += hi - lo
            peak = max(peak, abs(val))
    return {"duration_us": dur, "peak_DAC": peak}


def s_segments(it, led):
    ch = it.grad.ch["S"]
    out = []
    for t0, t1, prim, sec in ch.segments:
        if t1 <= t0 or t1 < led["t_start"] - 1e4 or t0 > led["t_end"]:
            continue
        out.append((t0, t1, prim, sec, led["G"]["S"].value_at((t0 + t1) / 2)))
    return out


def overlap_audit(it, led, shift):
    led = {**led, "_segS": s_segments(it, led)}
    rf_rows, rx_rows = [], []
    for p in led["rf"]:
        on = np.flatnonzero(np.abs(p["amp"]) > 1e-9)
        if not len(on):
            continue
        a, b = p["t"][on[0]], p["t"][on[-1]] + p["dt"]
        rf_rows.append({"frame": p["frame"], **overlap_secondary_S(led, shift, a, b)})
    for i, adc in enumerate(led["adc"]):
        rx_rows.append({"ADC": i + 1, "busy_us": adc["t_complete"] - adc["t_init"],
                        **overlap_secondary_S(led, shift, adc["t_init"], adc["t_complete"])})
    return {"RF_nonzero_vs_secondary_S": rf_rows, "receiver_busy_vs_secondary_S": rx_rows}


def terminal_audit(it, leds, shift):
    """Final ADC -> terminal list -> exit for every mapped shot with ADCs."""
    rows = []
    for led in leds:
        if not led["adc"] or not led["rf"]:
            continue
        last = led["adc"][-1]
        g = led["G"]["S"]
        m = (g.t[:-1] + shift >= last["t_init"]) & (g.t[:-1] < led["t_end"]) & (np.abs(g.v) > 0)
        lobes = []
        if m.any():
            idx = np.flatnonzero(m)
            lobes = [{"start_us": float(g.t[i] + shift), "end_us": float(g.t[i + 1] + shift), "DAC": float(g.v[i])} for i in idx]
        first_nz = lobes[0]["start_us"] if lobes else None
        last_nz = max((l["end_us"] for l in lobes), default=None)
        nxt = [p for p in _rf_all(it) if p["t_go"] >= led["t_end"]]
        rows.append({"shot": led["shot"],
                     "final_receiver_complete_us": last["t_complete"],
                     "first_S_after_final_ADC_init_us": first_nz,
                     "terminal_starts_after_receiver_busy": first_nz is None or first_nz >= last["t_complete"] - 1e-6,
                     "last_S_output_end_us": last_nz,
                     "S_area_final_ADC_centre_to_shot_end_cycles_m": dac_us_to_cyc_m(
                         g.integral(adc_middle_times(it, {**led, "adc": [last]})[0][1] - shift, led["t_end"] - shift), led["H"]),
                     "margin_last_output_to_next_RF_us": (nxt[0]["t_go"] - last_nz) if (nxt and last_nz) else None,
                     "margin_last_output_to_shot_label_us": (led["t_end"] - last_nz) if last_nz else None})
    return rows


def tr_minimum(label, model_name):
    """Smallest accepted TR (ms, binary search) and a 2-shot run at that TR."""
    lo, hi = 50, 2000
    accepted = lambda tr: bool(mapping(label, {**IMAGING, "tr": tr}, old.COST_MODELS[model_name], 1).adc)
    if not accepted(hi):
        return {"error": "nominal TR rejected"}
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if accepted(mid):
            hi = mid
        else:
            lo = mid
    it = mapping(label, {**IMAGING, "tr": hi}, old.COST_MODELS[model_name], 2)
    base, leds = shot_ledgers(it)
    shift = float(it.vars["rfdelay"].value)
    term = terminal_audit(it, leds, shift) if is_method(leds[0]["rf"]) else None
    rf = _rf_all(it)
    shots = [e[1] for e in it.misc_events if e[0] == "shot"]
    # Last gradient output of shot 1 vs first RF of shot 2 (physical time).
    last_out = 0.0
    for a in "SPR":
        g = base["G"][a]
        m = (np.abs(g.v) > 0) & (g.t[:-1] < shots[1] if len(shots) > 1 else True)
        if np.any(m):
            last_out = max(last_out, float(g.t[1:][m].max()) + shift)
    rf2 = [p["t_go"] for p in rf if len(shots) > 1 and p["t_go"] >= shots[1]]
    h = hazards(it, base["issues"])
    return {"min_accepted_tr_ms": hi, "rejected_tr_ms": lo,
            "two_shot_ADC": len(it.adc), "two_shot_RF": len(rf),
            "timer_overruns": len(h["timer_overruns"]), "ignored_lists": len(h["ignored_lists"]),
            "premature_matrix_use": h["premature_matrix_use"],
            "shot1_last_gradient_output_to_shot2_first_RF_us": (rf2[0] - last_out) if rf2 else None,
            "shot_spacing_us": float(np.diff(shots[:2])[0]) if len(shots) > 1 else None,
            "terminal": term}


def rejection_case(label, overrides):
    it = mapping(label, {**IMAGING, **overrides})
    nrf = len(_rf_all(it))
    msgs = [m for _, m in it.out]
    code = next((int(x) for m in msgs for x in re.findall(r"error E(\d+)", m)), None)
    return {"overrides": overrides, "RF_count": nrf, "ADC_count": len(it.adc),
            "pass": nrf == 0 and not it.adc, "error_code": code, "messages": msgs[-3:],
            "ppl_sha256": it.inputs["ppl_sha256"]}


def rej_job(job):
    label, name, ov = job
    return label, name, rejection_case(label, ov)


def tr_job(job):
    return job, tr_minimum(*job)


# ------------------------------------------------------------ static checks
def crusher_ratios(label):
    it = mapping(label, IMAGING)
    v = lambda k: it.vars[k].value if k in it.vars else None
    tcr, tdp, tramp, dtc = v("tcrush"), v("tdp"), v("tramp"), v("diff_tcrush")
    C, C1, D = v("crusher_saved_train"), v("diff_crush_amp"), v("v19_d_dac")
    ramp = 19200 / 10000  # ramp-shape area beyond plateau+tramp used by the source
    res = {"C_DAC": C, "C1_DAC": C1, "D_DAC": D}
    if D:
        cA = C * (tcr + tramp) + C * ramp
        c1A = C1 * (dtc + tramp) + C1 * ramp
        dA = D * (tdp + tramp) + D * ramp
        res.update({"C_over_D_area": abs(cA / dA), "C1_over_D_area": abs(c1A / dA),
                    "C_over_D_DAC": abs(C / D), "C1_over_D_DAC": abs(C1 / D)})
    if label == "v1911":
        res.update({k: v(k) for k in ("v1911_first_dac", "v1911_pre_dac", "v1911_post_dac")})
    return res


def event_rows(label, it, led):
    t0 = led["rf"][0]["t_center"]
    rows = []
    lat = float(it.vars["rfdelay"].value)
    for p in led["rf"]:
        rows.append(["RF", p["frame"], p["t_go"] - t0, p["t_center"] - t0,
                     p["t_go"] + p["duration_us"] - t0, "", p["mul"], p["phase_deg"]])
    for axis in "SPR":
        g = led["G"][axis]
        for i, value in enumerate(g.v):
            if g.t[i + 1] > led["t_start"] and g.t[i] < led["t_end"]:
                rows.append(["GRAD_SAMPLE", axis, g.t[i] + lat - t0, "", g.t[i + 1] + lat - t0, value, "", ""])
    for i, (a, (_, tc)) in enumerate(zip(led["adc"], adc_middle_times(it, led))):
        period = a["sample_period_ticks"] / 10
        rs = a["t_init"] + a["discard"] * period
        rows.append(["ADC_RETAINED_WINDOW", str(i + 1), rs - t0, tc - t0, rs + it.vars["no_samples"].value * period - t0, "", "", a["rx_phase_deg"]])
        rows.append(["RECEIVER_INIT_THROUGH_FILTER_FLUSH", str(i + 1), a["t_init"] - t0, "", a["t_complete"] - t0, "", "", a["rx_phase_deg"]])
    with (OUT / f"events_{label}.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["event", "name_or_axis", "start_us", "center_us", "end_us", "DAC", "RF_multiplier", "phase_deg"])
        w.writerows(sorted(rows, key=lambda r: r[2]))


def moment_job(label):
    """Nominal-model imaging shots: interval areas, selected k, overlaps."""
    it = mapping(label, IMAGING, shots=2)
    base, leds = shot_ledgers(it)
    shift = float(it.vars["rfdelay"].value)
    event_rows(label, it, leds[0])
    out = {"ppl_sha256": it.inputs["ppl_sha256"], "ppr_sha256": it.inputs["ppr_sha256"], "shots": []}
    for led in leds:
        out["shots"].append({"shot": led["shot"], "intervals": interval_areas(it, led, shift),
                             "selected_k": selected_k(it, led, shift),
                             "overlap": overlap_audit(it, led, shift)})
    return label, out


# ------------------------------------------------------------ gate evaluation
def evaluate(results, rejections, moments, ratios, trmin):
    F, notes = [], []
    for label in SOURCES:
        cand = label in CANDIDATES
        for (lab, model, state), r in results.items():
            if lab != label:
                continue
            tag = f"{label}/{model}/{state}"
            h = r["hazards"]
            bad = []
            if h["timer_overruns"]:
                bad.append(f"{len(h['timer_overruns'])} timer overruns")
            if h["ignored_lists"]:
                bad.append(f"{len(h['ignored_lists'])} ignored lists")
            if h["premature_matrix_use"]:
                n = sum(len(v) for v in h["premature_matrix_use"].values())
                bad.append(f"{n} premature matrix uses on {sorted(h['premature_matrix_use'])}: e.g. {next(iter(h['premature_matrix_use'].values()))[0][1]}")
            for s in r["shots"]:
                if s["ADC_count"] != 8:
                    bad.append(f"shot{s['shot']}: ADC count {s['ADC_count']}")
                sp = s["train_RF_spacing_us"]
                if sp and max(sp) - min(sp) > TOL["esp_variation_us"]:
                    bad.append(f"shot{s['shot']}: ESP variation {max(sp)-min(sp):.2f} us")
                if any(abs(x) > TOL["adc_rf_midpoint_us"] for x in s["ADC_minus_train_RF_midpoint_us"]):
                    bad.append(f"shot{s['shot']}: ADC/train-RF midpoint {max(map(abs, s['ADC_minus_train_RF_midpoint_us'])):.2f} us")
            # coverage
            st = r["adc_states"]
            if state == "imaging":
                if not st or any(x["nav_cnt"] != 1 for x in st) or not any(x["gp_mul"] for x in st):
                    bad.append("imaging coverage: navigator/dummy or zero PE only")
                if len({x["current_view"] for x in st}) < 2:
                    bad.append("imaging coverage: no view progression across shots")
            if state == "diffusion_rows":
                rows = sorted({x["diff_acq_cnt"] for x in st})
                if rows != [0, 1, 2]:
                    bad.append(f"diffusion-row coverage {rows}")
                peaks = [s.get("diffusion_window_peak_DAC", {}) for s in r["shots"]]
                if len(peaks) >= 6 and not (peaks[0]["R"] < peaks[4]["R"] or peaks[0]["S"] != peaks[4]["S"] or peaks[0]["P"] != peaks[4]["P"]):
                    bad.append("diffusion-row coverage: b=0 and b=6000 shots have identical diffusion-window gradients")
            if state == "diffusion_directions":
                rows = sorted({x["diff_acq_cnt"] for x in st})
                if rows != [0, 1, 2, 3]:
                    bad.append(f"direction coverage rows {rows}")
                pk = [sh.get("diffusion_window_peak_DAC", {}) for sh in r["shots"]]
                if len(pk) >= 8:
                    dom = []
                    for row in (1, 2, 3):
                        ex = {a: pk[2 * row]["abs_area_" + a] - pk[0]["abs_area_" + a] for a in "SPR"}
                        dom.append(max(ex, key=ex.get))
                    r["direction_dominant_axes"] = dom
                    if dom != ["R", "P", "S"]:
                        bad.append(f"direction coverage: x/y/z rows drive axes {dom}, expected R,P,S")
            if state == "default_ppr":
                if not any(x["nav_cnt"] == 0 for x in st):
                    bad.append("default coverage: no dummy/navigator ADC")
                if not any(x["nav_cnt"] == 1 and x["gp_mul"] for x in st):
                    bad.append("default coverage: imaging not reached in 6 shots")
            if bad:
                (F if cand else notes).extend(f"{tag}: {b}" for b in bad)
    for label, cases in rejections.items():
        for name, c in cases.items():
            if not c["pass"]:
                F.append(f"{label}: rejection not before RF: {name} (RF={c['RF_count']}, ADC={c['ADC_count']})")
    # Moments
    for cand in CANDIDATES:
        b = moments[BASELINE_OF[cand]]
        c = moments[cand]
        for sb, sc in zip(b["shots"], c["shots"]):
            ib, ic = sb["intervals"], sc["intervals"]
            if len(ib) != len(ic):
                F.append(f"{cand}/shot{sc['shot']}: interval count {len(ic)} vs baseline {len(ib)}")
                continue
            errs = []
            for i, (x, y) in enumerate(zip(ib, ic)):
                for ax in "SPR":
                    errs.append((abs(y[ax] - x[ax]) * 1e-3, i, ax, x["from"], x["to"]))
            sc["interval_area_delta_cycles_per_mm"] = [(e, i, ax, a, b_) for e, i, ax, a, b_ in errs if e > 1e-9]
            # Exceptions: v1.81 relocates the read prephaser across the
            # excitation->diffusion-180->ADC1 intervals (by design); v1.911 has
            # none (fused lobes must preserve every RF/ADC interval area).
            exempt = {0, 1} if cand == "v181" else set()
            over = [e for e in errs if e[0] > TOL["interval_area_cycles_per_mm"] and e[1] not in exempt]
            if over:
                worst = max(over)
                F.append(f"{cand}/shot{sc['shot']}: {len(over)} RF/ADC interval areas differ from baseline; worst {worst[0]:.3g} cycles/mm on {worst[2]} {worst[3]}->{worst[4]}")
            kb = {r["at"]: r["selected"]["k_cycles_m"] for r in sb["selected_k"]}
            kc = {r["at"]: r["selected"]["k_cycles_m"] for r in sc["selected_k"]}
            for at in kb:
                d = np.abs(np.array(kc[at]) - kb[at])
                lim = np.full(3, TOL["endpoint_cycles_per_mm"] * 1e3)
                if cand == "v181":
                    lim[2] = TOL["v181_read_endpoint_cycles_per_m"]
                if np.any(d > lim):
                    F.append(f"{cand}/shot{sc['shot']}: selected-branch k at {at} differs from baseline by {d.round(4).tolist()} cycles/m (S,P,R)")
        for s in c["shots"]:
            if cand != "v1911":
                continue
            for row in s["overlap"]["RF_nonzero_vs_secondary_S"]:
                if row["duration_us"] > 0:
                    F.append(f"v1911/shot{s['shot']}: secondary S lobe overlaps nonzero RF {row['frame']} for {row['duration_us']:.1f} us")
            for row in s["overlap"]["receiver_busy_vs_secondary_S"]:
                if row["duration_us"] > 0:
                    F.append(f"v1911/shot{s['shot']}: secondary S lobe overlaps receiver busy ADC{row['ADC']} for {row['duration_us']:.1f} us")
    r = ratios.get("v1911", {})
    for key, target in (("C_over_D_area", 3.83), ("C1_over_D_area", 2.55)):
        if key not in r or abs(r[key] / target - 1) > TOL["crusher_ratio_rel"]:
            F.append(f"v1911 crusher ratio {key}={r.get(key)} not ~{target}")
    for (label, model), t in trmin.items():
        sink = F if label in CANDIDATES else notes
        if t.get("error"):
            sink.append(f"{label}/{model} TR minimum: {t['error']}")
            continue
        if t["timer_overruns"] or t["ignored_lists"] or t["premature_matrix_use"] or t["two_shot_ADC"] != 16:
            sink.append(f"{label}/{model} at minimum TR {t['min_accepted_tr_ms']} ms: overruns={t['timer_overruns']} ignored={t['ignored_lists']} premature={bool(t['premature_matrix_use'])} ADC={t['two_shot_ADC']}")
        gap = t["shot1_last_gradient_output_to_shot2_first_RF_us"]
        if gap is not None and gap < 0:
            sink.append(f"{label}/{model} at minimum TR: shot-1 gradient output runs {-gap:.1f} us into shot-2 RF")
        for row in t.get("terminal") or []:
            if not row["terminal_starts_after_receiver_busy"]:
                sink.append(f"{label}/{model} at minimum TR: post-final-ADC slice output starts during receiver busy")
    for (lab, model, state), res in results.items():
        if lab == "v1911":
            for row in res.get("terminal", []):
                if not row["terminal_starts_after_receiver_busy"]:
                    F.append(f"v1911/{model}/{state}/shot{row['shot']}: terminal -D starts before receiver complete")
                if row["margin_last_output_to_shot_label_us"] is not None and row["margin_last_output_to_shot_label_us"] < 0:
                    F.append(f"v1911/{model}/{state}/shot{row['shot']}: terminal output crosses shot boundary")
    return F, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bloch", action="store_true", help="also run the legacy Bloch grid (normally delegated)")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    started = time.time()
    hashes_before = {l: {"ppl": sha(p), "ppr": sha(r)} for l, (p, r) in SOURCES.items()}
    jobs = [(l, m, s) for l in SOURCES for m in old.COST_MODELS for s in STATES]
    rjobs = [(l, n, ov) for l in ("v191_v7", "v1911") for n, ov in METHOD_REJECTIONS.items()]
    rjobs += [("v1911", n, ov) for n, ov in V1911_REJECTIONS.items()]
    rjobs += [("v181", n, ov) for n, ov in V181_REJECTIONS.items()]
    tjobs = [(l, m) for l in ("v18", "v181", "v191_v7", "v1911") for m in ("manual_x0.8", "manual_x1.0", "flat_2us")]
    results, rejections, trmin = {}, {}, {}
    with ProcessPoolExecutor(args.workers) as ex:
        mfut = ex.map(moment_job, list(SOURCES))
        for label, model, state, res in ex.map(run_job, jobs):
            results[(label, model, state)] = res
        print(f"event mappings: {len(results)}", flush=True)
        for label, name, case in ex.map(rej_job, rjobs):
            rejections.setdefault(label, {})[name] = case
        for job, t in ex.map(tr_job, tjobs):
            trmin[job] = t
        moments = dict(mfut)
    ratios = {l: crusher_ratios(l) for l in ("v191_v7", "v1911")}
    hashes_after = {l: {"ppl": sha(p), "ppr": sha(r)} for l, (p, r) in SOURCES.items()}
    failures, notes = evaluate(results, rejections, moments, ratios, trmin)
    stable = hashes_before == hashes_after
    if not stable:
        failures.append("input bytes changed during the run; rerun required")
    dump("events.json", {f"{l}/{m}/{s}": r for (l, m, s), r in results.items()})
    dump("rejections.json", rejections)
    dump("moments.json", moments)
    dump("tr_minimum.json", {f"{l}/{m}": t for (l, m), t in trmin.items()})
    bloch = {"status": "not_run", "note": "Finite-RF Bloch grid is run by a separate agent; this file does not certify it."}
    if args.bloch:
        bloch = {"status": "not_implemented_in_this_revision"}
    gates = {
        "generated_unix": time.time(), "elapsed_s": time.time() - started,
        "input_sha256": hashes_after, "inputs_stable_during_run": stable,
        "event_gates_pass": not failures,
        "overall_pass": False if bloch["status"] != "pass" else not failures,
        "overall_note": "overall_pass stays false until the delegated Bloch grid passes; event_gates_pass covers only the gates below.",
        "failures": failures, "baseline_notes": notes,
        "bloch": bloch,
        "crusher_ratios": ratios,
        "coverage_states": {k: {"overrides": v[0], "shots": v[1]} for k, v in STATES.items()},
        "cost_models": list(old.COST_MODELS),
        "rejection_counts": {l: {"total": len(c), "pass": sum(x["pass"] for x in c.values())} for l, c in rejections.items()},
        "tr_minimum": {f"{l}/{m}": {k: t.get(k) for k in ("min_accepted_tr_ms", "timer_overruns", "ignored_lists", "shot1_last_gradient_output_to_shot2_first_RF_us")} for (l, m), t in trmin.items()},
        "tolerances": TOL,
        "scope": "Source-model gates only (dwfse/ppl mapper, assumed 3-us RF latency, PPR rfdelay gradient lag, logical axes). Not vendor compilation, console timing or hardware qualification.",
    }
    dump("event_gates.json", gates)
    print(json.dumps({"event_gates_pass": gates["event_gates_pass"], "n_failures": len(failures),
                      "rejections": gates["rejection_counts"], "elapsed_s": round(gates["elapsed_s"], 1)}, indent=1))
    for f in failures:
        print("FAIL", f)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
