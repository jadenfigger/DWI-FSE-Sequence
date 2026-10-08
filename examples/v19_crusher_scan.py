"""Small 2-D finite-RF scan of the actual method PPL crusher geometry.

Maps retained byte-identical pre-restriction source copies, which permit the
exploratory samples. The output records exact inputs so these runs are not
mistaken for final-PPL acceptance tests. Use --boundary for the supported corners.
"""
from pathlib import Path
import json
import sys
import time
import argparse
import math
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))
import v19_validate_events as V
from dwfse.ppl.bloch import Grid, rf_calibration_hz_per_unit
from dwfse.ppl.ledger import build_ledger
from dwfse.vendor_seq import decode

OUT = ROOT / "docs/v19/event_validation/crusher_geometry_scan.json"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boundary", action="store_true", help="test the four allowed ratio-window corners and centre")
    args = ap.parse_args()
    out = OUT.with_name("crusher_geometry_boundary_scan.json") if args.boundary else OUT
    stock = decode(V.SC / "utilities/rfstd44.seq").frame("3lobe_sinc_3kHz")
    result = {"settings": {"z_points": 3000, "z_extent_mm": 5, "v191_y_points": 16,
                           "gradient_latency_us": 60, "phases_deg": [0, 45, 90],
                           "B1": 1.0, "B0_hz": 0, "relaxation": False}, "rows": []}
    t0 = time.time()
    for label in V.METHODS:
        # These are the byte-identical reviewed, pre-restriction files; retaining
        # them makes the exploratory scan reproducible after the guards change.
        ppl = OUT.parent / "crusher_scan_inputs" / f"{label}.ppl.txt"
        ppr = ppl.with_name(f"{label}.ppr")
        pairs = [(c, c1) for c in (-7700, -8223, -8750) for c1 in (-5150, -5482, -5800)]
        if args.boundary:
            base = V.mapping(ppl, ppr)
            val = lambda n: int(base.vars[n].value)
            d = abs(val("v19_d_dac")) * (val("tdp") + val("tramp"))
            ct = val("tcrush") + val("tramp")
            c1t = val("diff_tcrush") + val("tramp")
            cs = (math.ceil(3.81*d/ct), math.floor(3.85*d/ct))
            c1s = (math.ceil(2.53*d/c1t), math.floor(2.57*d/c1t))
            pairs = [(-c, -c1) for c in cs for c1 in c1s] + [(-8223, -5482)]
        for c, c1 in pairs:
                it = V.mapping(ppl, ppr, {"crush_amp": c, "diff_crush_amp": c1})
                led = build_ledger(it, 1)
                row = {"method": label, "C_DAC": c, "C1_DAC": c1, "inputs": it.inputs}
                if not led["adc"]:
                    row["rejected"] = it.out[-1][1].strip()
                else:
                    cal = rf_calibration_hz_per_unit(stock.samples, stock.wait_ticks / 10, it.vars["rfcal"].value)
                    ny = 16 if label == "v191" else 1
                    y = (np.arange(ny) + .5) / ny * V.VOXEL_Y - V.VOXEL_Y / 2 if ny > 1 else np.zeros(1)
                    signals = []
                    for ph in (0, 45, 90):
                        s, *_ = V.run_bloch(led, it, label, cal, phase=ph, latency=60,
                                            grid=Grid(V.Z, y), snapshots=False)
                        signals.append(np.abs(s).tolist())
                    a = np.array(signals)
                    row.update(abs_by_phase=signals, max_phase_spread=float(np.ptp(a, axis=0).max()))
                result["rows"].append(row)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(result, indent=1) + "\n")
                print(label, c, c1, row.get("max_phase_spread", row.get("rejected")), flush=True)
    result["elapsed_s"] = time.time() - t0
    out.write_text(json.dumps(result, indent=1) + "\n")

if __name__ == "__main__":
    main()
