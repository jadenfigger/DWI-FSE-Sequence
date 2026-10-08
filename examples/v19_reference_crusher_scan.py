"""Resolve the reference C1 choice with the independent reviewer's rotation engine.

First 16 echoes use the non-aliased 3000-point grid; no relaxation is the worst case.
The independent builder and simulator are retained under docs/v19/review/physics_checks.
"""
from pathlib import Path
import sys
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs/v19/review/physics_checks"))
import check_benchmark_c1 as C
from check_event_bloch import simulate

def main():
    z = (np.arange(3000) + .5) / 3000 * .030 - .015
    dz = (z[1] - z[0]) / C.B.SLICE
    busse = C.B.busse_style_schedule(C.B.N_ECHO, C.B.K_CENTRE)
    result = {"grid_points": 3000, "echoes": 16, "relaxation": False, "rows": []}
    for cycles in (2, 4):
        crusher = 1500.0 if cycles == 2 else 3000.0
        candidates = (2250, 2550) if cycles == 2 else (4500, 5100, 5400)
        for method in ("alsop", "ssmgot"):
            for c1 in candidates:
                s = C.build(method, cycles, C.B.ALSOP if method == "alsop" else busse, crusher, c1)
                led = s.ledger()
                signals = []
                for ph in (0, 45, 90):
                    state = simulate(led, 1.0, ph, 0.0, 32 if method == "ssmgot" else 1,
                                     None, s.adc, z=z, yvox=.001)
                    signals.append([abs(state[n][0].mean(axis=0).sum() * dz) for n, _ in s.adc])
                spread = float(np.ptp(np.array(signals), axis=0).max())
                row = dict(method=method, cycles=cycles, C=crusher, C1=c1,
                           max_phase_spread=spread, abs_by_phase=signals)
                result["rows"].append(row)
                path = ROOT / "docs/v19/reference_benchmark/c1_resolution_scan.json"
                path.write_text(json.dumps(result, indent=1) + "\n")
                print(method, cycles, c1, spread, flush=True)

if __name__ == "__main__":
    main()
