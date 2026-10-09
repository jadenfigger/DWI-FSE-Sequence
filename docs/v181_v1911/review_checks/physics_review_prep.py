"""Preparation-timing anatomy of v1.911 (b=6000, +read) and the value of the Delta protocol lever (model-only)."""
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from physics_review_common import *
from physics_review_intervals import events
HERE = Path(__file__).resolve().parent
it = mapped("v1911", {"acq_b": [6000, 1000, 6000]}, shots=1); led = build_ledger(it); ev, lag = events(it, led)
rf = [e for e in ev if e["kind"] == "RF"]
t, v = led["G"]["R"].t + lag, led["G"]["R"].v
big = np.abs(v) > 5000
idx = np.nonzero(big & (t[:-1] > rf[0]["centre"]) & (t[:-1] < rf[2]["centre"]))[0]
# group contiguous
groups = []
for i in idx:
    if groups and t[i] - groups[-1][-1][1] < 50: groups[-1].append((t[i], t[i + 1], v[i]))
    else: groups.append([(t[i], t[i + 1], v[i])])
out = {"RF_centres_us": [e["centre"] for e in rf[:4]], "TE_prep_us_RF0_to_RF2_centres": rf[2]["centre"] - rf[0]["centre"],
       "RF0_to_RF1_us": rf[1]["centre"] - rf[0]["centre"], "lobes": []}
for g in groups:
    a, b = g[0][0], g[-1][1]
    w = np.array([x[2] for x in g]); dt = np.array([x[1] - x[0] for x in g])
    cen = float((np.array([(x[0] + x[1]) / 2 for x in g]) * np.abs(w) * dt).sum() / (np.abs(w) * dt).sum())
    out["lobes"].append({"start_us": a, "end_us": b, "span_us": b - a, "peak_DAC": float(np.abs(w).max()), "centroid_us": cen})
if len(out["lobes"]) >= 2:
    out["Delta_centroid_us"] = out["lobes"][1]["centroid_us"] - out["lobes"][0]["centroid_us"]
print(json.dumps(out, indent=1))
fixed = out["TE_prep_us_RF0_to_RF2_centres"] / 1000 - out.get("Delta_centroid_us", 0) / 1000
print("TE_prep %.2f ms ; Delta(centroid) %.2f ms ; remainder %.2f ms" % (out["TE_prep_us_RF0_to_RF2_centres"] / 1e3, out.get("Delta_centroid_us", 0) / 1e3, fixed))
dac = out["lobes"][0]["peak_DAC"]
print("diffusion DAC at b6000: %.0f (%.1f%% of 32767); b ~ DAC^2 (delta=4 ms, Delta=40 ms)" % (dac, 100 * dac / 32767))
res = []
for D in (40, 35, 30, 25, 20):
    scale = np.sqrt((40 - 4 / 3) / (D - 4 / 3))
    for T2 in (32, 60):
        res.append({"Delta_ms": D, "T2_ms": T2, "signal_gain_vs_Delta40": float(np.exp((40 - D) / T2)), "diff_gradient_scale": float(scale), "DAC_b6000": float(dac * scale), "pct_FS": float(100 * dac * scale / 32767)})
for r in res:
    print(r)
out["lever"] = res
json.dump(out, open(HERE / "physics_review_prep.json", "w"), indent=1)
