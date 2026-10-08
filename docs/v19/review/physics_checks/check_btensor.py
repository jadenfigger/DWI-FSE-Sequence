"""Independent reviewer check 4: b-tensor along the echo-forming pathway.

Uses map_events/build_ledger only to obtain the ledger; the k-integration and b
integral are written here (exact piecewise-constant integration, no sampling).
Also an analytic trapezoid Stejskal-Tanner value for the v19 diffusion lobes.

Path rules: k -> -k at every refocusing-RF centre; v191 k frozen between tip-up
and re-excitation centres; variant 'conj' adds a k -> -k at the method-RF time
T0 (the conjugate Fourier branch, which is the recalled one at even echoes).

Run: python docs/v19/review/physics_checks/check_btensor.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from dwfse.ppl.run import map_events  # noqa: E402  (ledger only)
from dwfse.ppl.ledger import build_ledger  # noqa: E402  (ledger only)

OUT = Path(__file__).resolve().parent
SC = ROOT / "scanner"
CTRL = ROOT / "experiments/FSE-DWI_10-05-2026_v18_test1e/FSE-DWI_10-05-2026_v18_test1.ppr"


def b_path(led, t0, t1, flips, frozen=(), latency=60.0):
    """Exact integral of k k^T for piecewise-constant gradients (k piecewise linear)."""
    kf = led["H"] * 1e3 / 32767.0 * 1e-6           # cycles/m per DAC*us
    axes = ("S", "P", "R")
    bps = {t0, t1}
    for a in axes:
        tt = led["G"][a].t + latency
        bps.update(tt[(tt > t0) & (tt < t1)].tolist())
    bps.update(f for f in flips if t0 < f < t1)
    for a_, b_ in frozen:
        bps.update(x for x in (a_, b_) if t0 < x < t1)
    bps = np.array(sorted(bps))
    k = np.zeros(3)
    B = np.zeros((3, 3))
    fl = sorted(f for f in flips if t0 < f < t1)
    for a, b in zip(bps[:-1], bps[1:]):
        if any(abs(a - f) < 1e-9 for f in fl):
            k = -k
        mid = 0.5 * (a + b)
        if any(fa <= mid < fb for fa, fb in frozen):
            g = np.zeros(3)
        else:
            g = np.array([led["G"][ax].value_at(mid - latency) for ax in axes]) * kf   # cycles/m per us
        dt = b - a
        # k(t) = k + g*s, s in [0, dt]: integral k k^T = k k^T dt + (k g^T + g k^T) dt^2/2 + g g^T dt^3/3
        B += np.outer(k, k) * dt + (np.outer(k, g) + np.outer(g, k)) * dt ** 2 / 2 + np.outer(g, g) * dt ** 3 / 3
        k = k + g * dt
    return (2 * np.pi) ** 2 * B * 1e-6 * 1e-6, k      # us -> s, then s/m^2 -> s/mm^2


def run(label, ppl, ppr, b):
    it = map_events(ppl, ppr, overrides={"acq_b": [b, 1000, 6000]}, max_shots=1,
                    stmt_cost_us=0.0, expr_costs=True, expr_scale=0.8)
    led = build_ledger(it, 1)
    rf = led["rf"]
    t0 = rf[0]["t_center"]
    if label == "v18":
        flips = [p["t_center"] for p in rf[1:]]
        T0 = None
    else:
        flips = [p["t_center"] for p in rf if "180" in p["frame"]]
        T0 = next(p["t_center"] for p in rf if p["frame"] in ("v19_slrelim90", "v19_reexc90"))
    frozen = []
    if label == "v191":
        tip = next(p["t_center"] for p in rf if p["frame"] == "v19_slrtip90")
        frozen = [(tip, T0)]
    n = it.vars["no_samples"].value
    adc = [a["t_init"] + (a["discard"] + n / 2) * a["sample_period_ticks"] / 10 for a in led["adc"]]
    rows = []
    for e, tc in enumerate(adc[:2] + adc[-1:]):
        B, kend = b_path(led, t0, tc, flips, frozen)
        row = {"adc_index": adc.index(tc) + 1, "b_SS": B[0, 0], "b_PP": B[1, 1], "b_RR": B[2, 2],
               "b_SR": B[0, 2], "trace": float(np.trace(B)), "k_end": kend.tolist()}
        if T0 is not None:
            Bc, kc = b_path(led, t0, tc, flips + [T0], frozen)
            row.update({"conj_b_RR": Bc[2, 2], "conj_b_SS": Bc[0, 0], "conj_trace": float(np.trace(Bc)), "conj_k_end": kc.tolist()})
        rows.append(row)
    # analytic trapezoid value for the diffusion lobes (G on the diffusion axis)
    out = {"rows": rows, "diff_grad_dac": int(it.vars["diff_grad"].value)}
    if label != "v18":
        G = abs(it.vars["diff_grad"].value) / 32767 * led["H"] * 1e3          # Hz/m
        r = it.vars["tramp"].value * 1e-6
        d = it.vars["sm_delta_us"].value * 1e-6
        D_ = it.vars["big_delta_us"].value * 1e-6
        # trapezoid lobes: ramp r, total duration d+r (flat d-r)  -> Stejskal-Tanner with ramps
        flat = d - r
        dd = flat + r               # effective delta (area/G)
        bST = (2 * np.pi * G) ** 2 * (dd ** 2 * (D_ - dd / 3) + r ** 3 / 30 - dd * r ** 2 / 6) * 1e-6
        out["analytic_trapezoid_b"] = bST
        out["G_Hz_per_m"] = G
    return out


def main():
    res = {}
    for label, ppl, ppr in (("v191", SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl", SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppr"),
                            ("v192", SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.92.ppl", SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.92.ppr"),
                            ("v18", SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl", CTRL)):
        res[label] = {str(b): run(label, ppl, ppr, b) for b in (0, 1000)}
        print(label, json.dumps(res[label], indent=0, default=float)[:2500])
    (OUT / "btensor_independent.json").write_text(json.dumps(res, indent=1, default=float) + "\n")


if __name__ == "__main__":
    main()
