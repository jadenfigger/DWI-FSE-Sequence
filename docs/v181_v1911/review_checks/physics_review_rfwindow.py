"""Pointwise (1 us grid, RF-start-aligned) gradient equality v7 vs v1.911 inside and around every RF, plus
fused-lobe separation margins (physical time = emitted + rfdelay)."""
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from physics_review_common import *
from physics_review_intervals import events
HERE = Path(__file__).resolve().parent
L = {}
for lab in ("v7", "v1911"):
    it = mapped(lab, shots=2); led = build_ledger(it); ev, lag = events(it, led)
    L[lab] = (it, led, ev, lag)
out = {"hashes": check_hashes(), "rf": []}
rf7 = [e for e in L["v7"][2] if e["kind"] == "RF"]; rf9 = [e for e in L["v1911"][2] if e["kind"] == "RF"]
for j, (a, b) in enumerate(zip(rf7, rf9)):
    row = {"rf": j, "frame": a["frame"]}
    grid = np.arange(-250.0, (a["t1"] - a["t0"]) + 250.0, 1.0)
    for ax in "SPR":
        s7 = L["v7"][1]["G"][ax].sample(a["t0"] + grid - L["v7"][3])
        s9 = L["v1911"][1]["G"][ax].sample(b["t0"] + grid - L["v1911"][3])
        d = np.abs(s7 - s9)
        row[f"maxdiff_DAC_{ax}_in[-250us,RFend+250us]"] = float(d.max())
    # earliest/ latest deviation from RF window: find first deviation moving outward from RF start (pre) and end (post)
    for ax in "S":
        pre = np.arange(-1500.0, 0.0, 1.0); post = np.arange(0.0, 3000.0, 1.0) + (a["t1"] - a["t0"])
        s7 = L["v7"][1]["G"][ax].sample(a["t0"] + pre - lag); s9 = L["v1911"][1]["G"][ax].sample(b["t0"] + pre - lag)
        dpre = np.nonzero(np.abs(s7 - s9) > 0.5)[0]
        row["S_first_pre_deviation_us_before_RFstart"] = float(-pre[dpre[-1]]) if len(dpre) else None   # closest-to-RF deviation
        s7 = L["v7"][1]["G"][ax].sample(a["t0"] + post - lag); s9 = L["v1911"][1]["G"][ax].sample(b["t0"] + post - lag)
        dpost = np.nonzero(np.abs(s7 - s9) > 0.5)[0]
        row["S_first_post_deviation_us_after_RFend"] = float(post[dpost[0]] - (a["t1"] - a["t0"])) if len(dpost) else None
    out["rf"].append(row)
    print(j, a["frame"], {k: round(v, 3) for k, v in row.items() if k.startswith("maxdiff")}, row.get("S_first_pre_deviation_us_before_RFstart"))
(HERE / "physics_review_rfwindow.json").write_text(json.dumps(out, indent=1))
