"""Echo-centering/ESP vs gradient-cost model: ADC centre vs mid-point of adjacent RF centres (v7, v1.911; v1.8, v1.81)."""
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from physics_review_common import *
from dwfse.ppl.run import map_events
HERE = Path(__file__).resolve().parent
MODELS = {"manual_x0.6": dict(stmt_cost_us=0.0, expr_costs=True, expr_scale=0.6), "manual_x0.8": dict(stmt_cost_us=0.0, expr_costs=True, expr_scale=0.8),
          "manual_x1.0": dict(stmt_cost_us=0.0, expr_costs=True, expr_scale=1.0), "manual_x1.25": dict(stmt_cost_us=0.0, expr_costs=True, expr_scale=1.25),
          "none": dict(stmt_cost_us=0.0, expr_costs=False), "stmt0.5": dict(stmt_cost_us=0.5, expr_costs=False),
          "stmt1.0": dict(stmt_cost_us=1.0, expr_costs=False), "stmt1.0+x0.8": dict(stmt_cost_us=1.0, expr_costs=True, expr_scale=0.8)}
out = {}
for lab in ("v18", "v181", "v7", "v1911"):
    ppl, ppr = SRC[lab]; out[lab] = {}
    for name, kw in MODELS.items():
        it = map_events(ppl, ppr, overrides=dict(IMAGING), max_shots=2, **kw)
        led = build_ledger(it)
        rfs = [p["t_center"] for p in led["rf"]]; adcs = [t for _, t in adc_middle_times(it, led)]
        imaging_rf = rfs[1:] if lab in ("v18", "v181") else rfs[4:]
        # ADC j sits between RF index (j) and (j+1) of the refocusing list
        if lab in ("v18", "v181"):
            pairs = list(zip(rfs[1:-1], rfs[2:]))
            esp = np.diff(rfs[2:]); asym = [a - (p + q) / 2 for a, (p, q) in zip(adcs[1:], pairs[1:])]   # echoes 2..8
        else:
            pairs = list(zip(rfs[4:-1], rfs[5:]))
            esp = np.diff(rfs[4:]); asym = [a - (p + q) / 2 for a, (p, q) in zip(adcs[:7], pairs)]
        out[lab][name] = {"esp_us": esp.tolist(), "esp_mean": float(esp.mean()), "esp_min": float(esp.min()), "esp_max": float(esp.max()),
                          "adc_minus_midpoint_us": [float(x) for x in asym],
                          "overruns": sum(f["kind"] == "timer_overrun" for f in it.flags), "kinds": sorted({f["kind"] for f in it.flags}),
                          "TE_first_adc_minus_exc_us": float(adcs[0] - rfs[0])}
        print(lab, name, "ESP %.2f (%.2f..%.2f)" % (esp.mean(), esp.min(), esp.max()), "ADC-mid asym", np.round(asym[:3], 2), "overruns", out[lab][name]["overruns"], "TE1 %.1f" % (adcs[0] - rfs[0]))
json.dump(out, open(HERE / "physics_review_echo_symmetry.json", "w"), indent=1)
