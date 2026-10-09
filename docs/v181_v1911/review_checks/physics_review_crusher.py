"""Recover C, D, C1 (slice-axis dephasing areas, cycles/m) from the mapped waveforms of v7 and v1.911.

Free-interval decomposition (echo j>=2, RF j-1 -> ADC j -> RF j):
   E_post = area[RF end, ADC start]  = (C + D) + Qtail      (Qtail = selector ramp-down after RF end)
   E_pre  = area[ADC end, RF start]  = (C - D) + Qhead      (Qhead = selector ramp-up before RF start)
with Qtail/Qhead measured as the selector-only waveform in [RFend, RFend+258us] (stops at the zero gap before the lobe) / [RFstart-250us, RFstart]
(pointwise identical in v7 and v1.911, see physics_review_rfwindow.py).
"""
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from physics_review_common import *
from physics_review_intervals import events, axis_area_cyc_m
HERE = Path(__file__).resolve().parent
res = {}
for lab in ("v7", "v1911"):
    it = mapped(lab, shots=2); led = build_ledger(it); ev, lag = events(it, led)
    rfs = [e for e in ev if e["kind"] == "RF"]; adcs = [e for e in ev if e["kind"] == "ADC"]
    rows = []
    for j in range(8):       # ADC j sits after imaging RF j (rfs[4+j]) and before RF j+1
        r = rfs[4 + j]; a = adcs[j]
        Epost = axis_area_cyc_m(led, "S", r["t1"], a["t0"], lag)
        Qt = axis_area_cyc_m(led, "S", r["t1"], r["t1"] + 258, lag)
        row = {"echo": j + 1, "E_post": Epost, "Qtail": Qt, "C_plus_D": Epost - Qt}
        if j < 7:
            rn = rfs[5 + j]
            Epre = axis_area_cyc_m(led, "S", a["t1"], rn["t0"], lag)
            Qh = axis_area_cyc_m(led, "S", rn["t0"] - 250, rn["t0"], lag)
            row.update({"E_pre": Epre, "Qhead": Qh, "C_minus_D": Epre - Qh})
            C = ((Epost - Qt) + (Epre - Qh)) / 2; D = ((Epost - Qt) - (Epre - Qh)) / 2
            row.update({"C": C, "D": D, "C_over_D": C / D})
        rows.append(row)
    # first imaging RF: lobe-only area in [t0-2000, t0-250] and total interval RF3_end->RF4_start
    r4 = rfs[4]
    first_lobe = axis_area_cyc_m(led, "S", r4["t0"] - 2400, r4["t0"] - 250, lag)
    first_pre_total = axis_area_cyc_m(led, "S", rfs[3]["t1"], r4["t0"], lag)
    Qh4 = axis_area_cyc_m(led, "S", r4["t0"] - 250, r4["t0"], lag)
    D = np.mean([r["D"] for r in rows[:7]])
    r3 = rfs[3]
    X = axis_area_cyc_m(led, "S", r3["centre"], r4["centre"], lag)
    Q3p = axis_area_cyc_m(led, "S", r3["centre"], r3["t1"] + 258, lag)
    Q4m = axis_area_cyc_m(led, "S", r4["t0"] - 250, r4["centre"], lag)
    C1net = X - Q3p - Q4m
    # net slice moment accumulated between re-excitation centre (rfs[3]) and the first imaging 180 centre
    res[lab] = {"rows": rows, "D_mean": D, "C_mean": float(np.mean([r["C"] for r in rows[:7]])),
                "first_pre_lobe_only_area": first_lobe, "first_pre_total_RF3end_to_RF4start": first_pre_total, "Qhead4": Qh4,
                "ratio_lobe_only_over_D": first_lobe / D, "C1_net_between_RF3c_RF4c_minus_selectors": C1net, "C1net_over_D": C1net / D, "ratio_total_minus_Q_over_D": (first_pre_total - Qh4) / D}
    print(lab, "C %.3f D %.3f C/D %.5f ; first lobe-only %.3f (%.4f D) ; RF3end->RF4start %.3f minus Qhead %.3f = %.3f (%.4f D)" % (
        res[lab]["C_mean"], D, res[lab]["C_mean"] / D, first_lobe, first_lobe / D, first_pre_total, Qh4, first_pre_total - Qh4, (first_pre_total - Qh4) / D))
    print("   C1net (RF3 centre -> RF4 centre minus selector halves) = %.3f ; /D = %.5f" % (C1net, C1net / D))
    print("   per-echo C/D:", [round(r["C_over_D"], 5) for r in rows[:7]], " D:", [round(r["D"], 3) for r in rows[:7]])
    print("   terminal (echo 8) E_post-Qtail = C+D:", rows[7]["C_plus_D"])
json.dump(res, open(HERE / "physics_review_crusher.json", "w"), indent=1)
