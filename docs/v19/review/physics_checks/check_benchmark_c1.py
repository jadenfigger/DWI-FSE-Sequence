"""Reviewer check 5b: prep-crusher (C1) sensitivity of the Gibbons-geometry benchmark.

Rebuilds the writer's idealised benchmark event list (same geometry, RF contract,
moment blocks) with a variable C1, and propagates it with the reviewer's own
simulator (check_event_bloch.simulate). The writer's code is used only for the RF
contract loader (Seq) and the flip lists. No relaxation (Fig 3 style), 2 cycles.

Families predicted by the pathway analysis (cycles/m, C=1500, D=333.3):
  d=333, C-2D=833, C-D=1167, C=1500, C+D=1833, 2C-2D=2333, 2C=3000.
The writer's benchmark uses C1 = 1.5*C = 2250, 83 cycles/m from 2C-2D.

Run: python docs/v19/review/physics_checks/check_benchmark_c1.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "examples"))
import v19_reference_benchmark as B  # noqa: E402  (RF contract + flip lists only)
from check_event_bloch import simulate  # noqa: E402

N = 16


def build(method, cycles, flips, crusher, C1):
    s = B.Seq()
    D = cycles / B.SLICE
    slab = 18e-3 if method == "ssmgot" else B.SLICE
    a, T = s.add_rf(0.0, "v19_slrprep90", 90, 0.0, slab)
    s.kick("S", T / 2 + 10, -s.kappa["v19_slrprep90"] * a)
    s.kick("S", B.TE_PREP / 2 - 1600 - 100, C1)
    s.add_rf(B.TE_PREP / 2, "v19_slrprep180", 180, 270.0, slab)
    s.kick("S", B.TE_PREP / 2 + 1600, C1)
    tD = B.TE_PREP - 1600 - 600
    s.kick("S", tD, D)
    if method == "alsop":
        am, Tm = 1.2 * 1283.3333333 / B.SLICE * 1e-3, 1200.0
        s.kick("S", B.TE_PREP - Tm / 2 - 110, -s.kappa["v19_reexc90"] * am)
        s.add_rf(B.TE_PREP, "v19_reexc90", 90, 270.0, B.SLICE)
        s.kick("S", B.TE_PREP + Tm / 2 + 10, -s.kappa["v19_reexc90"] * am)
        t0 = B.TE_PREP
    else:
        am, Tm = 3.2 * 1109.375 / 10e-3 * 1e-3, 3200.0
        s.kick("S", B.TE_PREP - Tm / 2 - 110, -s.kappa["v19_slrtip90"] * am)
        s.add_rf(B.TE_PREP, "v19_slrtip90", 90, 180.0, 10e-3)
        ts = B.TE_PREP + Tm / 2 + 50
        s.kick("P", ts, 8.0 / 1e-3, dur=500.0)
        t0 = ts + 500 + 50 + 600
        ar, Tr = s.add_rf(t0, "v19_reexc90", 90, 0.0, B.SLICE)
        s.kick("S", t0 + Tr / 2 + 10, -s.kappa["v19_reexc90"] * ar)
    for k in range(N):
        tc = t0 + (k + 0.5) * B.ESP
        s.kick("S", tc - 600 - 220, crusher, dur=200.0)
        s.add_rf(tc, "v19_imaging180", flips[k], 270.0, B.SLICE)
        s.kick("S", tc + 600 + 20, crusher, dur=200.0)
        s.kick("S", tc + 600 + 240, D, dur=200.0)
        te = t0 + (k + 1) * B.ESP
        s.adc.append((f"ADC{k+1}", te))
        s.kick("S", te + 200, -D, dur=200.0)
    return s


def main():
    C = 1500.0
    busse = B.busse_style_schedule(B.N_ECHO, B.K_CENTRE)
    out = {"busse_first16": busse[:16]}
    dz = (B.Z[1] - B.Z[0]) / B.SLICE
    for method in ("alsop", "ssmgot"):
        flips = B.ALSOP if method == "alsop" else busse
        rows = {}
        c1_list = (1.5 * C, 1.3 * C, 1.7 * C, 2.2 * C, 2.5 * C, 2333.3) if method == "alsop" else (1.5 * C, 2.5 * C)
        for c1 in c1_list:
            sp = []
            for ph in (0.0, 45.0, 90.0):
                s = build(method, 2, flips, C, c1)
                led = s.ledger()
                ny = 32 if method == "ssmgot" else 1
                res = simulate(led, 1.0, ph, 0.0, ny, None, s.adc, z=B.Z, yvox=1e-3)
                sp.append([abs(res[n][0].mean(axis=0).sum() * dz) for n, _ in s.adc])
            sp = np.array(sp)
            rows[f"C1={c1:.0f}"] = {"abs_by_phase": sp.round(4).tolist(), "max_phase_spread": float((sp.max(0) - sp.min(0)).max())}
            print(method, f"C1={c1:.0f}", rows[f"C1={c1:.0f}"]["max_phase_spread"], sp[:, :6].round(3).tolist())
        out[method] = rows
    (HERE / "benchmark_c1_results.json").write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
