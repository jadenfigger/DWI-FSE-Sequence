"""v1.8 vs v1.81: does moving the read prephaser change which unwanted histories land inside the echo?
Ideal-RF complex EPG-path enumeration with relaxation/diffusion off (geometry + flip-error mixing only)."""
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from physics_review_common import *
from physics_review_intervals import events
import physics_review_offres_epg as EP
import physics_review_diffusion_epg as DE
HERE = Path(__file__).resolve().parent
L = {}
for lab in ("v18", "v181"):
    it = mapped(lab, shots=2); led = build_ledger(it); ev, lag = events(it, led); L[lab] = (led, ev, lag)
    if lab == "v18":
        print("RF phases", [p["phase_deg"] for p in led["rf"]], "mul", [p["mul"] for p in led["rf"]])
ph = [p["phase_deg"] for p in L["v18"][0]["rf"]]
EP.FLIPS = [90] + [180] * 8; EP.PH = ph
res = []
for b1 in (0.8, 0.9, 1.0, 1.1):
    for ph0 in (0.0, 45.0, 90.0):
        o = {lab: EP.run(*L[lab], b1, 0.0, ph0) for lab in L}
        # In v1.8 ADC1 is after RF index 1 (diffusion 180); wanted box defined from the top path
        s = {lab: [EP.signal(o[lab][j]) for j in range(1, 9)] for lab in L}
        r = np.array(s["v181"]) / np.maximum(np.array(s["v18"]), 1e-12)
        res.append({"B1": b1, "ph0": ph0, "v18": s["v18"], "v181": s["v181"], "ratio": r.tolist(), "n_hist": [len(o["v18"][j][1]) for j in (1, 8)]})
        print(b1, ph0, "v18", np.round(s["v18"], 4), "ratio", np.round(r, 4), flush=True)
json.dump(res, open(HERE / "physics_review_v181_pathways.json", "w"), indent=1)
