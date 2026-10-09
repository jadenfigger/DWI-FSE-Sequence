"""Which histories carry the v1.8 -> v1.81 ratio spread?  Split each ADC sum into slice-coherent (|kS|<1500) and
slice-incoherent (box-sinc sidelobe) parts, and into |kR|<300 vs displaced; same 36-case grid as the grid agent."""
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from physics_review_v181_reconcile import *
HERE = Path(__file__).resolve().parent
L = {}
for lab in ("v18", "v181"):
    it = mapped(lab, shots=2); led = build_ledger(it); ev, lag = events(it, led); L[lab] = (led, ev, lag)
ph = [p["phase_deg"] for p in L["v18"][0]["rf"]]
grid = json.load(open(HERE / "final_physics_grid.json"))["pathway"]["pairs"]["v181"]["rows"]
rows = []; kRmax = 0.0; dispw = {"v18": 0.0, "v181": 0.0}
for g in grid:
    S = {}
    for lab in L:
        o = run(*L[lab], ph, g["B1"], g["B0_Hz"], g["phase_deg"])
        tot, coh, disp_w = [], [], 0.0
        for j in range(1, 9):
            n, sig, a = o[j]
            m = np.abs(n[:, 0]) < 1500
            tot.append(abs(sig.sum())); coh.append(abs(sig[m].sum()))
            dm = m & (np.abs(n[:, 2]) >= 300)
            disp_w = max(disp_w, float(np.abs(sig[dm]).sum()) / max(abs(sig[0:0].sum()), 1) if dm.any() else 0.0)
            if dm.any(): kRmax = max(kRmax, float(np.abs(n[dm, 2]).min()))
        S[lab] = (np.array(tot), np.array(coh))
        dispw[lab] = max(dispw[lab], disp_w)
    rows.append({"B1": g["B1"], "df": g["B0_Hz"], "ph": g["phase_deg"], "tot18": S["v18"][0].tolist(), "tot181": S["v181"][0].tolist(),
                 "coh18": S["v18"][1].tolist(), "coh181": S["v181"][1].tolist()})
def rob(key18, key181):
    rat, sg = [], []
    for r in rows:
        b = np.array(r[key18]); a = np.array(r[key181]); m = b >= 0.05 * b[0]
        rat += list((a / b)[m]); sg.append(((a - b) / b[0]).min())
    return float(min(rat)), float(max(rat)), float(min(sg)), len(rat)
print("all histories (box sinc): ratio min/max, worst signed change/E1, n", rob("tot18", "tot181"))
print("slice-coherent only (|kS|<1500):", rob("coh18", "coh181"))
print("smallest |kR| among displaced slice-coherent histories (cyc/m):", kRmax, " (0 => none displaced)")
json.dump({"rows": rows}, open(HERE / "physics_review_v181_reconcile2.json", "w"))
