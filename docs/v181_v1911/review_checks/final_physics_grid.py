"""Final independent physics evidence grid for v1.8->v1.81 and v1.91(v7)->v1.911.

Reviewer-side, additive, read-only with respect to builders, validators,
scanner files and dwfse/. Every input PPL/PPR is recorded with its SHA-256 so a
rerun after source changes is a single command:

    python docs/v181_v1911/review_checks/final_physics_grid.py

Optional explicit paths (e.g. after v1.81 compaction):

    python docs/v181_v1911/review_checks/final_physics_grid.py \
        --v181 scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl

Sections
1. Finite-RF EventBloch grid (B1 0.8/0.9/1.0/1.1 x B0 -128/0/+128 Hz x initial
   phase 0/45/90), every echo, actual imaging shot state
   (no_disacq=0, nav_on=0, no_views=128). Regression gate defined below.
2. Every-echo full b tensors (exact piecewise-constant integration, imaging
   gradients included) at nominal b 0/100/1000/6000 for all four sequences.
3. Diffusion-aware generalized instantaneous-RF pathway enumeration
   (examples/v181_v1911_pathway_audit.analyze_pathways; includes (2pi)^2 for
   encoded longitudinal states; dwfse/pathways.py is NOT used).
4. Isodelay: summary of existing finite-RF peak-probe JSONs (with hash
   staleness), and an optional fresh probe (--isodelay-probe) including y64
   convergence and RF-latency / gradient-lag sensitivity.

Nothing here is a vendor compilation or scanner verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from dwfse.ppl.run import map_events  # noqa: E402
from dwfse.ppl.ledger import build_ledger, adc_middle_times  # noqa: E402
from dwfse.ppl.bloch import EventBloch, Grid, SimConfig, rf_calibration_hz_per_unit  # noqa: E402
from dwfse.ppl.analysis import k_path, b_tensor  # noqa: E402
from dwfse.vendor_seq import decode  # noqa: E402
from examples.v181_v1911_pathway_audit import analyze_pathways, self_checks  # noqa: E402

HERE = Path(__file__).resolve().parent
SC = ROOT / "scanner"
V7 = ROOT / "docs/v181_v1911/baseline_v7/FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl"
DEFAULTS = {
    "v18": (SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl",
            ROOT / "experiments/FSE-DWI_10-05-2026_v18_test1e/FSE-DWI_10-05-2026_v18_test1.ppr"),
    "v181": (SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl", SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppr"),
    "v191_v7": (V7, V7.with_suffix(".ppr")),
    "v1911": (SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl", SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppr"),
}
PAIRS = (("v18", "v181"), ("v191_v7", "v1911"))
IMAGING = {"no_disacq": 0, "nav_on": 0, "no_views": 128}
COST = {"stmt_cost_us": 0.0, "expr_costs": True, "expr_scale": 0.8}
RF_LATENCY_US = 3.0                      # assumed, unmeasured
SLICE_W = 1e-3                           # protocol slice width (m)
FOV_PHASE = 35e-3                        # protocol FOV (m); voxel = FOV/no_views
B1S, B0S, PHASES = (0.8, 0.9, 1.0, 1.1), (-128.0, 0.0, 128.0), (0.0, 45.0, 90.0)
NOMINAL_B = (0, 100, 1000, 6000)

# Regression gate (defined before results were seen; never relabelled).
#  STRICT: candidate-baseline |S| change >= -1e-4 (normalized units; numerical noise)
#  MATERIAL: candidate/baseline |S| ratio >= 0.98 per echo per case
GATE = {"strict_abs_tolerance": 1e-4, "material_ratio_floor": 0.98,
        "phase_flag_deg": 10.0,
        "definition": "Per echo and per (B1,B0,phase) case. STRICT failure = any magnitude drop "
                      "below -1e-4 (normalized to unit-flip on-resonance slice integral). MATERIAL "
                      "failure = candidate/baseline < 0.98. Phase changes > 10 deg are flagged, not gated, "
                      "because intended timing changes legitimately move off-resonance phase."}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def stock_cal(it):
    stock = decode(SC / "utilities/rfstd44.seq").frame("3lobe_sinc_3kHz")
    return rf_calibration_hz_per_unit(stock.samples, stock.wait_ticks / 10, it.vars["rfcal"].value)


EXPECTED = {}  # path -> sha256 recorded at start; guards against bytes changing mid-run


def mapped(src, overrides=None, rf_latency=RF_LATENCY_US, shots=2):
    ppl, ppr = src
    for f in (ppl, ppr):
        if str(f) in EXPECTED and sha(f) != EXPECTED[str(f)]:
            raise RuntimeError(f"{f} changed during the run; rerun on stable bytes")
    params = dict(IMAGING)
    params.update(overrides or {})
    it = map_events(ppl, ppr, overrides=params, max_shots=shots, rf_latency_us=rf_latency, **COST)
    if "v19_error_code" in it.vars and it.vars["v19_error_code"].value:
        raise RuntimeError(f"{ppl}: rejected with error {it.vars['v19_error_code'].value}")
    return it


def shot_state(it, led):
    P = led["G"]["P"]
    m = (P.t[:-1] >= led["t_start"]) & (P.t[:-1] < led["t_end"])
    return {"rf_count": len(led["rf"]), "adc_count": len(led["adc"]),
            "rf_frames": [r["frame"] for r in led["rf"]],
            "phase_axis_peak_DAC": float(np.max(np.abs(P.v[m]), initial=0.)),
            "flag_kinds": sorted({f["kind"] for f in it.flags}),
            "timer_overruns": sum(f["kind"] == "timer_overrun" for f in it.flags)}


# --------------------------------------------------------------------- 1. Bloch
def imaging_esp_us(label, led):
    rf = led["rf"]
    refs = [p for p in rf if p["frame"] == "v19_imaging180"] if label.startswith("v191") else rf[2:]
    return float(np.mean(np.diff([p["t_center"] for p in refs])))


def bloch_grid(label, it, led, nz, ny, quick=False, relax=None, cases=None):
    method = label.startswith("v191")
    z = (np.arange(nz) + .5) / nz * 5 * SLICE_W - 2.5 * SLICE_W
    vy = FOV_PHASE / float(it.vars["no_views"].value)
    y = (np.arange(ny) + .5) / ny * vy - vy / 2 if (method and ny > 1) else np.zeros(1)
    grid = Grid(z, y)
    cal = stock_cal(it)
    adc = adc_middle_times(it, led)
    lag = float(it.vars["rfdelay"].value)
    rows = []
    if cases is None:
        cases = [(1.0, 0.0, 0.0)] if quick else [(b, d, p) for b in B1S for d in B0S for p in PHASES]
    for b1, df, ph in cases:
        cfg = SimConfig(b1_scale=b1, df_hz=df, grad_latency_us=lag, extra_phase_deg={0: ph},
                        t1_s=relax[0] if relax else None, t2_s=relax[1] if relax else None)
        sim = EventBloch(led, grid, cal, cfg)
        _, ad = sim.run(led["rf"], {}, adc)
        dz = (z[1] - z[0]) / SLICE_W
        s = np.array([complex(ad[n][0].mean(axis=0).sum() * dz) for n, _ in adc])
        rows.append({"B1": b1, "B0_Hz": df, "phase_deg": ph, "abs": np.abs(s).tolist(),
                     "phase_deg_echo": np.rad2deg(np.angle(s)).tolist(),
                     "real": s.real.tolist(), "imag": s.imag.tolist(),
                     "gradient_change_inside_RF_samples": getattr(sim, "gradient_change_in_rf", 0)})
    return {"grid": {"nz": nz, "z_span_m": 5 * SLICE_W, "ny": len(y), "y_span_m": vy if len(y) > 1 else 0.0},
            "gradient_lag_us": lag, "relaxation": relax, "cases": rows}


def compare_bloch(before, after):
    out, strict, material, flags = [], [], [], []
    for a, b in zip(before["cases"], after["cases"]):
        assert (a["B1"], a["B0_Hz"], a["phase_deg"]) == (b["B1"], b["B0_Hz"], b["phase_deg"])
        A, B = np.array(a["abs"]), np.array(b["abs"])
        dphi = (np.array(b["phase_deg_echo"]) - a["phase_deg_echo"] + 180) % 360 - 180
        ratio = np.where(A > 0, B / np.where(A > 0, A, 1), np.nan)
        key = {"B1": a["B1"], "B0_Hz": a["B0_Hz"], "phase_deg": a["phase_deg"]}
        for e in range(len(A)):
            if B[e] - A[e] < -GATE["strict_abs_tolerance"]:
                strict.append({**key, "echo": e + 1, "delta": float(B[e] - A[e]), "ratio": float(ratio[e])})
            if ratio[e] < GATE["material_ratio_floor"]:
                material.append({**key, "echo": e + 1, "ratio": float(ratio[e])})
            if abs(dphi[e]) > GATE["phase_flag_deg"]:
                flags.append({**key, "echo": e + 1, "delta_phase_deg": float(dphi[e])})
        out.append({**key, "before_abs": A.tolist(), "after_abs": B.tolist(), "ratio": ratio.tolist(),
                    "delta_abs": (B - A).tolist(), "delta_phase_deg": dphi.tolist()})
    allr = np.array([r["ratio"] for r in out])
    return {"cases": out, "min_ratio": float(np.nanmin(allr)), "max_ratio": float(np.nanmax(allr)),
            "min_ratio_per_echo": np.nanmin(allr, axis=0).tolist(),
            "max_ratio_per_echo": np.nanmax(allr, axis=0).tolist(),
            "strict_failures": strict, "material_failures": material, "phase_flags": flags,
            "strict_pass": not strict, "material_pass": not material}


def offres_period(runs, nz, ny, b1s=(0.8, 1.0), centers=(0.0, 128.0), npts=8):
    """Average each sequence over one full off-resonance period (1/own ESP) about each centre.

    A single isochromat at +/-128 Hz samples a different point of the train's
    periodic off-resonance response when ESP changes; a uniform intravoxel
    distribution spanning one period removes that sampling artefact.
    """
    out = {}
    for before, after in PAIRS:
        rows = []
        for b1 in b1s:
            for c in centers:
                rec = {}
                for lab in (before, after):
                    it, led = runs[lab]
                    period = 1e6 / imaging_esp_us(lab, led)
                    dfs = c + ((np.arange(npts) + .5) / npts - .5) * period
                    res = bloch_grid(lab, it, led, nz, ny, cases=[(b1, float(d), 0.0) for d in dfs])["cases"]
                    S = np.array([np.array(x["real"]) + 1j * np.array(x["imag"]) for x in res])
                    rec[lab] = {"period_Hz": period, "coherent": np.abs(S.mean(axis=0)), "incoherent": np.abs(S).mean(axis=0)}
                rows.append({"B1": b1, "center_Hz": c, "phase_deg": 0.0,
                             "period_Hz": {k: v["period_Hz"] for k, v in rec.items()},
                             "before_coherent": rec[before]["coherent"].tolist(),
                             "after_coherent": rec[after]["coherent"].tolist(),
                             "ratio_coherent": (rec[after]["coherent"] / rec[before]["coherent"]).tolist(),
                             "ratio_incoherent_mean_abs": (rec[after]["incoherent"] / rec[before]["incoherent"]).tolist()})
                print(f"offres {after} B1 {b1} centre {c}", flush=True)
        out[after] = {"baseline": before, "npts": npts, "rows": rows,
                      "min_ratio_coherent": float(min(min(r["ratio_coherent"]) for r in rows)),
                      "min_ratio_incoherent": float(min(min(r["ratio_incoherent_mean_abs"]) for r in rows))}
    return out


# ------------------------------------------------------------------ 2. b tensors
def exact_path(led, t0, t1, flips, frozen, lag):
    """Exact PWC integration of k and int k k^T dt along one coherence path."""
    events = sorted([(f, "flip") for f in flips if t0 < f < t1])
    for a, b in frozen:
        events += [(a, "freeze"), (b, "thaw")]
    events = sorted(events)
    fac = led["H"] * 1e3 / 32767
    k, T = np.zeros(3), np.zeros((3, 3))
    frozen_now = False
    marks = [t0] + [e[0] for e in events] + [t1]
    kinds = [None] + [e[1] for e in events]
    for i in range(len(marks) - 1):
        kind = kinds[i]
        if kind == "flip":
            k = -k
        elif kind == "freeze":
            frozen_now = True
        elif kind == "thaw":
            frozen_now = False
        a, b = marks[i], marks[i + 1]
        if b <= a:
            continue
        cuts = {a, b}
        for ax in "SPR":
            tt = led["G"][ax].t + lag
            cuts.update(tt[(tt > a) & (tt < b)].tolist())
        cuts = sorted(cuts)
        for x, y in zip(cuts[:-1], cuts[1:]):
            dt = (y - x) * 1e-6
            g = np.zeros(3) if frozen_now else np.array(
                [led["G"][ax].value_at((x + y) / 2 - lag) for ax in "SPR"]) * fac
            e = k + g * dt
            m = (k + e) / 2
            T += dt / 6 * (np.outer(k, k) + 4 * np.outer(m, m) + np.outer(e, e))
            k = e
    return k, (2 * np.pi) ** 2 * 1e-6 * T


def btensors(label, src):
    out = {}
    for b in NOMINAL_B:
        it = mapped(src, {"acq_b": [b, 1000, 6000]}, shots=1)
        led = build_ledger(it, 1)
        rf = led["rf"]
        lag = float(it.vars["rfdelay"].value)
        method = label.startswith("v191")
        if method:
            flips = [p["t_center"] for p in rf if "180" in p["frame"]]
            tip = next(p for p in rf if p["frame"] == "v19_slrtip90")
            re = next(p for p in rf if p["frame"] == "v19_reexc90")
            frozen = [(tip["t_center"], re["t_center"])]
            branches = {"carrier": flips, "conjugate": sorted(flips + [re["t_center"]])}
        else:
            frozen, branches = [], {"primary": [p["t_center"] for p in rf[1:]]}
        echoes = []
        for name, tc in adc_middle_times(it, led):
            cands = {}
            for br, fl in branches.items():
                k, B = exact_path(led, rf[0]["t_center"], tc, fl, frozen, lag)
                cands[br] = {"k_end_cycles_m_SPR": k.tolist(), "B_s_mm2_SPR": B.tolist(),
                             "trace_s_mm2": float(np.trace(B)),
                             "eigenvalues_s_mm2": np.linalg.eigvalsh(B).tolist()}
            sel = min(cands, key=lambda c: np.linalg.norm(cands[c]["k_end_cycles_m_SPR"]))
            # Sampled cross-check with the repository k_path (dt=1 us); not an oracle.
            t, kp = k_path(led, rf[0]["t_center"], tc, branches[sel], frozen, dt_us=1.0, latency_us=lag)
            sampled = float(np.trace(b_tensor(t, kp)))
            echoes.append({"echo": name, "selected_branch": sel, "branches": cands,
                           "selected_trace_s_mm2": cands[sel]["trace_s_mm2"],
                           "sampled_kpath_trace_s_mm2": sampled,
                           "sampled_minus_exact": sampled - cands[sel]["trace_s_mm2"]})
        out[str(b)] = {"inputs_sha256": {"ppl": it.inputs["ppl_sha256"], "ppr": it.inputs["ppr_sha256"]},
                       "acq_b_row0": b, "echoes": echoes}
    return out


# -------------------------------------------------------------------- 3. pathway
def pathway(pairs_led, quick=False):
    res = {"self_checks": self_checks(), "conditions": {"D_mm2_s": .002, "T1_s": 1.3, "T2_s": .032},
           "scope": "CONDITIONAL instantaneous-RF model: RF collapsed to signed-area rotation at the sample "
                    "envelope centre, stationary box voxel, no finite slice profile, no diffusion during "
                    "finite RF, no motion. (2pi)^2 included for encoded longitudinal states. Not a "
                    "prediction of acquired signal and not a finite-RF result.", "pairs": {}}
    cases = [(1.0, 0.0, 0.0)] if quick else [(b, d, p) for b in B1S for d in B0S for p in PHASES]
    for before, after in PAIRS:
        rows, nominal = [], {}
        for b1, df, ph in cases:
            rec = {}
            for lab in (before, after):
                it, led = pairs_led[lab]
                r = analyze_pathways(it, led, b1=b1, df_hz=df, initial_phase_deg=ph,
                                     diffusivity_mm2_s=.002, T1_s=1.3, T2_s=.032,
                                     top=5 if (b1, df, ph) == (1.0, 0.0, 0.0) else 0)
                rec[lab] = r
                if (b1, df, ph) == (1.0, 0.0, 0.0):
                    nominal[lab] = [{"echo": e["echo"], "signal_abs": e["signal_abs"],
                                     "signal_no_diff_abs": e["signal_no_diff_abs"],
                                     "diffusion_signal_ratio": e["diffusion_signal_ratio"],
                                     "coherent_over_l1": e["coherent_over_l1"],
                                     "top_paths": e["top_paths"]} for e in r["echoes"]]
            A = np.array([e["signal_abs"] for e in rec[before]["echoes"]])
            B = np.array([e["signal_abs"] for e in rec[after]["echoes"]])
            dA = np.array([e["diffusion_signal_ratio"] for e in rec[before]["echoes"]])
            dB = np.array([e["diffusion_signal_ratio"] for e in rec[after]["echoes"]])
            rows.append({"B1": b1, "B0_Hz": df, "phase_deg": ph, "before_abs": A.tolist(),
                         "after_abs": B.tolist(), "after_over_before": (B / A).tolist(),
                         "before_diffusion_ratio": dA.tolist(), "after_diffusion_ratio": dB.tolist()})
        ratios = np.array([r["after_over_before"] for r in rows])
        befores = np.array([r["before_abs"] for r in rows]); afters = np.array([r["after_abs"] for r in rows])
        e1 = befores[:, :1]
        robust = befores >= .05 * e1   # ratios of near-cancelled echoes are numerically meaningless
        res["pairs"][after] = {"baseline": before, "rows": rows, "nominal": nominal,
                               "max_abs_delta_over_baseline_E1": float(np.max(np.abs(afters - befores) / e1)),
                               "min_signed_delta_over_baseline_E1": float(np.min((afters - befores) / e1)),
                               "robust_echo_rule": "baseline |S| >= 5% of that case's baseline E1",
                               "robust_min_after_over_before": float(ratios[robust].min()),
                               "robust_max_after_over_before": float(ratios[robust].max()),
                               "robust_echo_count": int(robust.sum()), "total_echo_count": int(robust.size),
                               "min_after_over_before": float(ratios.min()),
                               "max_after_over_before": float(ratios.max()),
                               "min_per_echo": ratios.min(axis=0).tolist(),
                               "nominal_after_over_before": rows[[ (r["B1"], r["B0_Hz"], r["phase_deg"]) for r in rows].index((1.0, 0.0, 0.0))]["after_over_before"]}
    return res


# -------------------------------------------------------------------- 4. isodelay
def isodelay_summary(current_sha):
    files = sorted(HERE.glob("finite_rf_peak*.json"))
    rows = []
    for f in files:
        d = json.loads(f.read_text())
        for lab, v in d["sequences"].items():
            s = v["inputs"]["ppl_sha256"]
            key = "v191_v7" if lab == "v191_v7" else lab
            rows.append({"file": f.name, "label": lab, "nz": d["configuration"]["nz"],
                         "ny": d["configuration"]["ny"], "rf_latency_us": d["configuration"]["latency"],
                         "B1": d["configuration"]["b1"], "phase_deg": d["configuration"]["phase"],
                         "ppl_sha256": s, "matches_current_input": s == current_sha.get(key),
                         "peak_offset_us": v["peak_offset_from_retained_center_us"],
                         "center_over_peak": v["center_over_peak"],
                         "peak_at_probe_edge": v["peak_at_probe_edge"]})
    return rows


def peak_probe(src, label, nz, ny, rf_latency, grad_lag):
    it = mapped(src, rf_latency=rf_latency, shots=1)
    led = build_ledger(it, 1)
    cal = stock_cal(it)
    center = adc_middle_times(it, led)[0][1]
    offsets = np.arange(-500, 501, 10, dtype=float)
    req = [(str(i), center + o) for i, o in enumerate(offsets)]
    z = (np.arange(nz) + .5) / nz * 5 * SLICE_W - 2.5 * SLICE_W
    method = label.startswith("v191")
    vy = FOV_PHASE / float(it.vars["no_views"].value)
    y = (np.arange(ny) + .5) / ny * vy - vy / 2 if (method and ny > 1) else np.zeros(1)
    total = np.zeros(len(offsets), complex)
    dfs = np.linspace(-150, 150, 15)
    for df in dfs:
        cfg = SimConfig(b1_scale=1.0, df_hz=df, grad_latency_us=grad_lag, extra_phase_deg={0: 45.0})
        _, ad = EventBloch(led, Grid(z, y), cal, cfg).run(led["rf"], {}, req)
        total += np.array([ad[n][0].mean() for n, _ in req])
    env = np.abs(total) / len(dfs)
    k = int(np.argmax(env))
    peak = float(offsets[k])
    if 0 < k < len(offsets) - 1:
        peak += 10 * float(.5 * (env[k-1] - env[k+1]) / (env[k-1] - 2 * env[k] + env[k+1]))
    return {"label": label, "nz": nz, "ny": len(y), "rf_latency_us": rf_latency, "gradient_lag_us": grad_lag,
            "ppl_sha256": it.inputs["ppl_sha256"], "peak_offset_us": peak,
            "peak_at_probe_edge": k in (0, len(offsets) - 1),
            "center_over_peak": float(env[len(offsets) // 2] / env.max())}


# ------------------------------------------------------------------------ report
def write_md(R, path):
    L = ["# Final physics grid (reviewer evidence)", "",
         "Source-model evidence only: not vendor compilation, not scanner verification. "
         "Generated by `final_physics_grid.py`; JSON holds full numbers.", "",
         f"Rerun: `{R['rerun_command']}`", "", f"Runtime: {R['elapsed_s']:.0f} s", "", "## Inputs", "",
         "| label | PPL | PPL sha256 | PPR sha256 |", "|---|---|---|---|"]
    for lab, v in R["inputs"].items():
        L.append(f"| {lab} | {Path(v['ppl']).name} | `{v['ppl_sha256']}` | `{v['ppr_sha256']}` |")
    L += ["", f"Imaging state overrides: `{IMAGING}`; RF latency {RF_LATENCY_US} us (assumed); gradient lag = PPR rfdelay; cost model {COST}.", ""]
    if "shot_state" in R:
        L += ["Shot state (shot 1): " + "; ".join(f"{k}: RF {v['rf_count']}, ADC {v['adc_count']}, |P|max {v['phase_axis_peak_DAC']:.0f}, overruns {v['timer_overruns']}" for k, v in R["shot_state"].items()), ""]
    if "bloch" in R:
        L += ["## 1. Finite-RF Bloch grid", "", GATE["definition"], "",
              "| pair | cases | min ratio | max ratio | min ratio per echo | STRICT | MATERIAL | phase flags |",
              "|---|---|---|---|---|---|---|---|"]
        for cand, c in R["bloch"]["comparisons"].items():
            L.append(f"| {c['baseline']}->{cand} | {len(c['cases'])} | {c['min_ratio']:.5f} | {c['max_ratio']:.5f} | "
                     + ", ".join(f"{x:.4f}" for x in c["min_ratio_per_echo"])
                     + f" | {'PASS' if c['strict_pass'] else 'FAIL (%d)' % len(c['strict_failures'])}"
                     f" | {'PASS' if c['material_pass'] else 'FAIL (%d)' % len(c['material_failures'])} | {len(c['phase_flags'])} |")
        L += ["", "Nominal case (B1 1, B0 0, phase 0) per-echo |S| and phase:", ""]
        for lab, r in R["bloch"]["runs"].items():
            c0 = next(c for c in r["cases"] if (c["B1"], c["B0_Hz"], c["phase_deg"]) == (1.0, 0.0, 0.0))
            L.append(f"- {lab}: |S| " + ", ".join(f"{x:.4f}" for x in c0["abs"]) +
                     "; phase deg " + ", ".join(f"{x:.1f}" for x in c0["phase_deg_echo"]))
        if R["bloch"].get("shot2_nominal"):
            L += ["", "Shot-2 nominal consistency (max |abs| difference vs shot 1): " +
                  ", ".join(f"{k}: {v:.2e}" for k, v in R["bloch"]["shot2_nominal"].items())]
        if R["bloch"].get("relaxed_nominal"):
            L += ["", "Nominal case with T1 1.3 s / T2 32 ms (informational): " +
                  "; ".join(f"{k}: " + ", ".join(f"{x:.4f}" for x in v) for k, v in R["bloch"]["relaxed_nominal"].items())]
        for cand, d in R["bloch"].get("diagnostics", {}).items():
            L += ["", f"Failing-case diagnostics for {cand} (per-echo minimum over echoes):", "",
                  "| B1 | B0 Hz | phase | min ratio (gated, no relax) | min ratio T1/T2 | min ratio equal phase/ESP |", "|---|---|---|---|---|---|"]
            for x in d["cases"]:
                L.append(f"| {x['B1']} | {x['B0_Hz']:+.0f} | {x['phase_deg']:.0f} | {min(x['ratio_no_relaxation']):.4f} | "
                         f"{min(x['ratio_T1_1.3s_T2_32ms']):.4f} | {min(x['ratio_equal_offresonance_phase_per_ESP']):.4f} |")
        L += ["", "### Disposition", ""] + [f"- {d}" for d in R["bloch"]["disposition"]] + [""]
    if "offres_period_average" in R:
        L += ["## 1b. Off-resonance period-averaged Bloch (diagnostic for the +/-128 Hz regression)", "",
              "Each sequence averaged over 8 isochromats spanning one period 1/ESP of its own train about the centre "
              "(phase 0). Coherent = |mean complex signal| (uniform intravoxel distribution). Diagnostic only; not the gate.", "",
              "| pair | B1 | centre Hz | coherent ratio per echo | incoherent mean-|S| ratio per echo |", "|---|---|---|---|---|"]
        for cand, o in R["offres_period_average"].items():
            if not isinstance(o, dict) or "rows" not in o:
                continue
            for r in o["rows"]:
                L.append(f"| {o['baseline']}->{cand} | {r['B1']} | {r['center_Hz']:+.0f} | "
                         + ", ".join(f"{x:.4f}" for x in r["ratio_coherent"]) + " | "
                         + ", ".join(f"{x:.4f}" for x in r["ratio_incoherent_mean_abs"]) + " |")
            L += ["", f"{o['baseline']}->{cand}: min period-averaged coherent ratio {o['min_ratio_coherent']:.4f}, "
                  f"min incoherent ratio {o['min_ratio_incoherent']:.4f} (material floor {GATE['material_ratio_floor']}). "
                  "This does not change the gated single-isochromat result above.", ""]
        L.append("")
    if "btensors" in R:
        L += ["## 2. Every-echo b tensors (selected primary branch, trace s/mm^2)", "",
              "Exact PWC integration from excitation centre incl. imaging gradients, gradient lag = rfdelay, "
              "RF centres instantaneous; ss-MGOT stored interval tip-up->re-excitation held; branch with smallest |k_end| selected. "
              "Full 3x3 tensors and both branches in JSON.", "",
              "| sequence | nominal b | E1 | E2 | E3 | E4 | E5 | E6 | E7 | E8 | max |sampled-exact| |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for lab, bt in R["btensors"].items():
            for b, v in bt.items():
                tr = [e["selected_trace_s_mm2"] for e in v["echoes"]]
                err = max(abs(e["sampled_minus_exact"]) for e in v["echoes"])
                L.append(f"| {lab} | {b} | " + " | ".join(f"{x:.2f}" for x in tr) + f" | {err:.2e} |")
        L.append("")
    if "pathway" in R:
        P = R["pathway"]
        L += ["## 3. Diffusion-aware generalized pathway model (CONDITIONAL)", "", P["scope"], "",
              f"Conditions: {P['conditions']}. Self-checks passed: {P['self_checks']['passed']}.", "",
              "| pair | min ratio (all) | max ratio (all) | robust min/max ratio | min signed dS/E1 | nominal after/before per echo | min per echo |", "|---|---|---|---|---|---|---|"]
        for cand, c in P["pairs"].items():
            L.append(f"| {c['baseline']}->{cand} | {c['min_after_over_before']:.4f} | {c['max_after_over_before']:.4f} | "
                     f"{c.get('robust_min_after_over_before', float('nan')):.4f}/{c.get('robust_max_after_over_before', float('nan')):.4f} "
                     f"({c.get('robust_echo_count')}/{c.get('total_echo_count')} echoes) | {c.get('min_signed_delta_over_baseline_E1', float('nan')):+.4f} | "
                     + ", ".join(f"{x:.4f}" for x in c["nominal_after_over_before"]) + " | "
                     + ", ".join(f"{x:.4f}" for x in c["min_per_echo"]) + " |")
        L += ["", "Robust ratio excludes echoes whose baseline amplitude is below 5% of its E1 (coherent cancellation makes ratios unstable); "
              "dS/E1 is the signed amplitude change normalized to the baseline first echo.", "",
              "Nominal diffusion-only signal ratio (D=0.002 vs D=0) per echo:", ""]
        for cand, c in P["pairs"].items():
            for lab, ech in c["nominal"].items():
                L.append(f"- {lab}: " + ", ".join(f"{e['diffusion_signal_ratio']:.4f}" for e in ech))
        L.append("")
    if "isodelay" in R:
        I = R["isodelay"]
        L += ["## 4. Isodelay (sensitivity only; real centring is scanner-verify)", "",
              "Existing probe JSONs (first-echo envelope peak of +/-150 Hz intravoxel distribution, B1 1, phase 45). "
              "A fitted whole-train peak is not a universal RF isodelay.", "",
              "| file | label | nz | ny | peak offset us | centre/peak | sha matches current |", "|---|---|---|---|---|---|---|"]
        for r in I["existing"]:
            L.append(f"| {r['file']} | {r['label']} | {r['nz']} | {r['ny']} | {r['peak_offset_us']:+.2f} | {r['center_over_peak']:.5f} | {r['matches_current_input']} |")
        if I.get("fresh_probe"):
            L += ["", "Fresh probes on current bytes:", "",
                  "| label | nz | ny | RF lat us | grad lag us | peak offset us | centre/peak |", "|---|---|---|---|---|---|---|"]
            for r in I["fresh_probe"]:
                L.append(f"| {r['label']} | {r['nz']} | {r['ny']} | {r['rf_latency_us']} | {r['gradient_lag_us']} | {r['peak_offset_us']:+.2f} | {r['center_over_peak']:.5f} |")
        L += ["", "### Notes", ""] + [f"- {n}" for n in I["notes"]] + [""]
    L += ["## Limitations", ""] + [f"- {x}" for x in R.get("limitations", [])] + [""]
    path.write_text("\n".join(L))


def bloch_disposition(comparisons, diagnostics):
    out = []
    for cand, c in comparisons.items():
        if c["strict_pass"] and c["material_pass"]:
            out.append(f"{c['baseline']}->{cand}: no magnitude regression beyond 1e-4 in any echo/case "
                       f"(ratio range {c['min_ratio']:.5f}-{c['max_ratio']:.5f}).")
            continue
        worst = min(c["strict_failures"], key=lambda f: f["delta"]) if c["strict_failures"] else None
        out.append(f"{c['baseline']}->{cand}: GATE FAILED (STRICT {len(c['strict_failures'])}, MATERIAL "
                   f"{len(c['material_failures'])}); worst {worst}. Not relabelled; see reviewer disposition in "
                   "the report/handback. Model omits diffusion and relaxation (unless stated), so a time-compressed "
                   "candidate's T2/diffusion benefit is not credited here.")
        d = diagnostics.get(cand)
        if d:
            out.append(f"{cand} diagnostics over {d['failing_cases']} failing cases: STRICT failures by B1 {d['strict_by_B1']}, "
                       f"by B0 {d['strict_by_B0']}, by phase {d['strict_by_phase']}, by echo {d['strict_by_echo']}. "
                       f"ESP {d['imaging_ESP_us']}. Min ratio no relaxation {d['min_ratio_no_relaxation']:.4f}; "
                       f"with T1 1.3 s/T2 32 ms {d['min_ratio_T1_1.3s_T2_32ms']:.4f}; candidate evaluated at B0 scaled "
                       f"to equal off-resonance phase per ESP {d['min_ratio_equal_offresonance_phase_per_ESP']:.4f}.")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for lab in DEFAULTS:
        ap.add_argument(f"--{lab}", type=Path, help=f"{lab} PPL (default {DEFAULTS[lab][0].name})")
        ap.add_argument(f"--{lab}-ppr", type=Path)
    ap.add_argument("--sections", default="bloch,offres,btensor,pathway,isodelay",
                    help="subset reruns merge into an existing output JSON only if all input hashes match")
    ap.add_argument("--nz", type=int, default=3000)
    ap.add_argument("--ny", type=int, default=32)
    ap.add_argument("--quick", action="store_true", help="nominal case only (smoke test)")
    ap.add_argument("--isodelay-probe", action="store_true",
                    help="fresh peak probes: v191 pair at y32/y64 (3000z), and RF-latency 0/3 x lag 0/60 sensitivity at 2000z/16y")
    ap.add_argument("--out", default="final_physics_grid")
    args = ap.parse_args(argv)
    started = time.time()
    sections = set(args.sections.split(","))
    src = {}
    for lab, (ppl, ppr) in DEFAULTS.items():
        p = getattr(args, lab) or ppl
        r = getattr(args, lab.replace("-", "_") + "_ppr") or (ppr if getattr(args, lab) is None else Path(p).with_suffix(".ppr"))
        src[lab] = (Path(p).resolve(), Path(r).resolve())
    R = {"rerun_command": "python docs/v181_v1911/review_checks/final_physics_grid.py" + (" --isodelay-probe" if args.isodelay_probe else ""),
         "arguments": {k: str(v) for k, v in vars(args).items()},
         "script_sha256": sha(__file__),
         "pathway_tool_sha256": sha(ROOT / "examples/v181_v1911_pathway_audit.py"),
         "inputs": {lab: {"ppl": str(p), "ppl_sha256": sha(p), "ppr": str(r), "ppr_sha256": sha(r)} for lab, (p, r) in src.items()},
         "imaging_overrides": IMAGING, "cost_model": COST, "rf_latency_assumed_us": RF_LATENCY_US,
         "regression_gate": GATE}
    out_json = HERE / f"{args.out}.json"
    if out_json.exists():
        old = json.loads(out_json.read_text())
        if old.get("inputs") == R["inputs"] and set(sections) != set(ap.get_default("sections").split(",")):
            keep = {k: v for k, v in old.items() if k not in R}
            R.update(keep)
            R["merged_from_previous_run_sections"] = sorted(keep)
            R["rerun_command"] = "python docs/v181_v1911/review_checks/final_physics_grid.py --isodelay-probe"

    def save():
        R["elapsed_s"] = time.time() - started
        out_json.write_text(json.dumps(R, indent=2, default=float) + "\n")
        write_md(R, HERE / f"{args.out}.md")

    for lab, (p, r) in src.items():
        EXPECTED[str(p)], EXPECTED[str(r)] = sha(p), sha(r)
    runs = {}
    for lab, s in src.items():
        it = mapped(s)
        runs[lab] = (it, build_ledger(it, 1))
    R["shot_state"] = {lab: shot_state(it, led) for lab, (it, led) in runs.items()}
    if "bloch" in sections:
        t = time.time()
        B = {"runs": {}, "comparisons": {}}
        for lab, (it, led) in runs.items():
            B["runs"][lab] = bloch_grid(lab, it, led, args.nz, args.ny, args.quick)
            print(f"bloch {lab} {time.time()-t:.0f}s", flush=True)
        for before, after in PAIRS:
            B["comparisons"][after] = {"baseline": before, **compare_bloch(B["runs"][before], B["runs"][after])}
        B["shot2_nominal"], B["relaxed_nominal"] = {}, {}
        for lab, (it, _) in runs.items():
            led2 = build_ledger(it, 2)
            s2 = bloch_grid(lab, it, led2, args.nz, args.ny, quick=True)["cases"][0]["abs"]
            s1 = next(c for c in B["runs"][lab]["cases"] if (c["B1"], c["B0_Hz"], c["phase_deg"]) == (1.0, 0.0, 0.0))["abs"]
            B["shot2_nominal"][lab] = float(np.max(np.abs(np.array(s2) - s1)))
            B["relaxed_nominal"][lab] = bloch_grid(lab, it, runs[lab][1], args.nz, args.ny, quick=True,
                                                   relax=(1.3, .032))["cases"][0]["abs"]
        B["diagnostics"] = {}
        for before, after in PAIRS:
            c = B["comparisons"][after]
            fails = c["strict_failures"] + c["material_failures"]
            if not fails:
                continue
            keys = sorted({(f["B1"], f["B0_Hz"], f["phase_deg"]) for f in fails})
            esp0, esp1 = imaging_esp_us(before, runs[before][1]), imaging_esp_us(after, runs[after][1])
            D = {"failing_cases": len(keys),
                 "strict_by_B1": {str(b): sum(f["B1"] == b for f in c["strict_failures"]) for b in B1S},
                 "strict_by_B0": {str(d): sum(f["B0_Hz"] == d for f in c["strict_failures"]) for d in B0S},
                 "strict_by_phase": {str(p): sum(f["phase_deg"] == p for f in c["strict_failures"]) for p in PHASES},
                 "strict_by_echo": {str(e): sum(f["echo"] == e for f in c["strict_failures"]) for e in range(1, 9)},
                 "imaging_ESP_us": {before: esp0, after: esp1}, "cases": []}
            relaxed = {lab: bloch_grid(lab, runs[lab][0], runs[lab][1], args.nz, args.ny, relax=(1.3, .032), cases=keys)["cases"]
                       for lab in (before, after)}
            matched = bloch_grid(after, runs[after][0], runs[after][1], args.nz, args.ny,
                                 cases=[(b, d * esp0 / esp1, p) for b, d, p in keys])["cases"]
            for i, key in enumerate(keys):
                base = next(x for x in B["runs"][before]["cases"] if (x["B1"], x["B0_Hz"], x["phase_deg"]) == key)
                cand = next(x for x in B["runs"][after]["cases"] if (x["B1"], x["B0_Hz"], x["phase_deg"]) == key)
                A0 = np.array(base["abs"])
                D["cases"].append({"B1": key[0], "B0_Hz": key[1], "phase_deg": key[2],
                    "ratio_no_relaxation": (np.array(cand["abs"]) / A0).tolist(),
                    "ratio_T1_1.3s_T2_32ms": (np.array(relaxed[after][i]["abs"]) / np.array(relaxed[before][i]["abs"])).tolist(),
                    "candidate_B0_scaled_to_equal_phase_per_ESP_Hz": key[1] * esp0 / esp1,
                    "ratio_equal_offresonance_phase_per_ESP": (np.array(matched[i]["abs"]) / A0).tolist()})
            for name in ("ratio_no_relaxation", "ratio_T1_1.3s_T2_32ms", "ratio_equal_offresonance_phase_per_ESP"):
                D["min_" + name] = float(min(min(x[name]) for x in D["cases"]))
            B["diagnostics"][after] = D
            print(f"diagnostics {after} {time.time()-t:.0f}s", flush=True)
        B["disposition"] = bloch_disposition(B["comparisons"], B["diagnostics"])
        B["elapsed_s"] = time.time() - t
        R["bloch"] = B
        save()
    if "offres" in sections:
        t = time.time()
        R["offres_period_average"] = offres_period(runs, args.nz, args.ny)
        R["offres_period_average"]["elapsed_s"] = time.time() - t
        save()
    if "btensor" in sections:
        t = time.time()
        R["btensors"] = {lab: btensors(lab, s) for lab, s in src.items()}
        R["btensor_elapsed_s"] = time.time() - t
        print(f"btensor {time.time()-t:.0f}s", flush=True)
        save()
    if "pathway" in sections:
        t = time.time()
        R["pathway"] = pathway(runs, args.quick)
        R["pathway"]["elapsed_s"] = time.time() - t
        print(f"pathway {time.time()-t:.0f}s", flush=True)
        save()
    if "isodelay" in sections:
        cur = {lab: v["ppl_sha256"] for lab, v in R["inputs"].items()}
        I = {"existing": isodelay_summary(cur), "notes": [
            "Existing candidate JSONs whose sha does not match the current inputs are stale for that candidate.",
            "y8 probes can alias the eight-cycle spoiler; use ny>=32 values. Convergence: compare ny 16/32/64.",
            "RF latency 3 us and gradient lag 60 us are unmeasured assumptions and used only for sensitivity.",
            "The historical +95 us shift is not hard-coded; the first-echo peak depends on grid, B1, B0 distribution."]}
        if args.isodelay_probe:
            fresh = []
            for lab in ("v191_v7", "v1911"):
                for ny in (32, 64):
                    fresh.append(peak_probe(src[lab], lab, 3000, ny, 3.0, 60.0)); print(fresh[-1], flush=True)
                    I["fresh_probe"] = fresh; R["isodelay"] = I; save()
            for lab in src:
                for lat in (0.0, 3.0):
                    for lag in (0.0, 60.0):
                        fresh.append(peak_probe(src[lab], lab, 2000, 16, lat, lag)); print(fresh[-1], flush=True)
                        I["fresh_probe"] = fresh; R["isodelay"] = I; save()
        R["isodelay"] = I
    R["limitations"] = [
        "Source-model PPL interpretation; no vendor compiler, no console timing, no measured RF/gradient delays.",
        "EventBloch: finite RF with exact sample rotations, slice (z) and phase-voxel (y, ss-MGOT only) grids; "
        "no molecular diffusion, no read-axis spatial coordinate (read relocation in v1.81 is invisible to it), "
        "relaxation off in the gated grid.",
        "RF calibration inferred from stock pulse and rfcal (linear model); achieved flips are scanner-verify.",
        "b tensors are single selected coherence paths; low-angle FSE signal is a sum over pathways (see section 3).",
        "Pathway model is instantaneous-RF, conditional on D=0.002 mm^2/s, T1 1.3 s, T2 32 ms.",
        "Logical axes only; oblique physical axes not modelled.",
        f"Phase-voxel width assumes FOV {FOV_PHASE*1e3:.0f} mm / no_views."]
    save()
    print(out_json, f"{time.time()-started:.0f}s")


if __name__ == "__main__":
    main()
