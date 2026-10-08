"""Reviewer check: prep-crusher (C1) sensitivity of v191 (ss-MGOT) on the real ledger.

Same method as check_event_bloch.py --c1-scan (ledger from map_events with a
diff_crush_amp override; propagation by the reviewer's simulator, 32 y points).
Run: python docs/v19/review/physics_checks/check_c1_v191.py
"""
import json
from pathlib import Path
import numpy as np
from check_event_bloch import get_led, stock_cal, adc_mid, simulate, Z, W

dz = (Z[1] - Z[0]) / W
out = {}
for dac in (-1500, -2500, -4000, -5482, -7000, -12000):
    it, led = get_led("v191", {"diff_crush_amp": dac})
    if len(led["rf"]) < 4:
        out[str(dac)] = {"rejected": it.out[-1][1].strip()}
        print(dac, out[str(dac)], flush=True)
        continue
    cal = stock_cal(it.vars["rfcal"].value)
    adc = adc_mid(led)
    sp = []
    for ph in (0.0, 45.0, 90.0):
        r = simulate(led, cal, ph, 60.0, 32, None, adc)
        sp.append([abs(r[n][0].mean(axis=0).sum() * dz) for n, _ in adc])
    sp = np.array(sp)
    out[str(dac)] = {"abs_by_phase": sp.round(4).tolist(), "max_phase_spread": float((sp.max(0) - sp.min(0)).max())}
    print(dac, out[str(dac)], flush=True)
(Path(__file__).resolve().parent / "c1_v191_results.json").write_text(json.dumps(out, indent=1) + "\n")
