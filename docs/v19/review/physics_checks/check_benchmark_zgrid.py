"""Reviewer check 5c: z-grid (aliasing) convergence of the Gibbons-geometry benchmark.

3000 isochromats over 30 mm -> dz = 10 um, Nyquist |k| = 50,000 cycles/m, i.e. only
~33 echo intervals of 2C (C = 1500 cycles/m). Compare 3000 vs 9000 isochromats for
all 76 echoes (no relaxation = worst case, as in the Fig 3/S2 ADC76 landmark) and
with muscle relaxation (Fig 4). Writer's benchmark builder is used for the event
list only; propagation is the reviewer's simulator (relaxation applied in free
intervals only, which is adequate for a grid-convergence comparison).

Run: python docs/v19/review/physics_checks/check_benchmark_zgrid.py
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
import v19_reference_benchmark as B  # noqa: E402  (event list only)
from check_event_bloch import simulate  # noqa: E402


def main():
    busse = B.busse_style_schedule(B.N_ECHO, B.K_CENTRE)
    out = {}
    for method in ("alsop", "ssmgot"):
        flips = B.ALSOP if method == "alsop" else busse
        s = B.build(method, 2, flips, 1500.0)
        led = s.ledger()
        ny = 32 if method == "ssmgot" else 1
        for relax in (False, True):
            res = {}
            for nz in (3000, 9000):
                z = (np.arange(nz) + 0.5) / nz * 30e-3 - 15e-3
                dz = (z[1] - z[0]) / B.SLICE
                r = simulate(led, 1.0, 45.0, 0.0, ny, None, s.adc, z=z, yvox=1e-3,
                             t1t2=(B.T1, B.T2) if relax else None)
                res[nz] = np.array([abs(r[n][0].mean(axis=0).sum() * dz) for n, _ in s.adc])
            d = np.abs(res[3000] - res[9000])
            key = f"{method}_{'relax' if relax else 'norelax'}"
            out[key] = {"max_abs_diff_all": float(d.max()), "max_abs_diff_echo1_16": float(d[:16].max()),
                        "echo_of_max": int(d.argmax()) + 1, "z3000_first8": res[3000][:8].round(4).tolist(),
                        "z9000_first8": res[9000][:8].round(4).tolist(), "z3000_echo76": float(res[3000][-1]),
                        "z9000_echo76": float(res[9000][-1])}
            print(key, out[key], flush=True)
    (HERE / "benchmark_zgrid_results.json").write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
