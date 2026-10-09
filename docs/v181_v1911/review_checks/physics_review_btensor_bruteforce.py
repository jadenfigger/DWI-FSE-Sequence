"""Brute-force 0.25 us midpoint-sampled cross-check of the exact b-tensor integrator (E1, b=1000 and 6000)."""
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from physics_review_common import *
from physics_review_btensor import run, adc_geometry
res = {}
for lab in ("v18", "v181"):
    for b in (1000, 6000):
        it, led, _, _ = run(lab, b, (1000, 0, 0))
        H = led["H"]; lag = float(it.vars["rfdelay"].value); fac = H * 1e3 / 32767 * 1e-6
        t0 = led["rf"][0]["t_center"]; rf1 = led["rf"][1]["t_center"]
        tadc = adc_geometry(it, led)[0][1]
        dt = 0.25
        t = np.arange(t0 + dt / 2, tadc, dt)
        G = np.stack([led["G"][a].sample(t - lag) for a in "SPR"], 1) * fac * 1e6   # cyc/m/s
        k = np.zeros((len(t), 3)); cur = np.zeros(3); flipped = False
        for i, ti in enumerate(t):
            if not flipped and ti >= rf1:
                cur = -cur; flipped = True
            cur_mid = cur + G[i] * dt * 1e-6 / 2
            k[i] = cur_mid
            cur = cur + G[i] * dt * 1e-6
        B = (2 * np.pi) ** 2 * 1e-6 * dt * 1e-6 * np.einsum("ti,tj->ij", k, k)
        res[f"{lab} b{b}"] = {"trace_bruteforce": float(np.trace(B)), "kR_end": float(cur[2])}
        print(lab, b, res[f"{lab} b{b}"])
json.dump(res, open(Path(__file__).with_name("physics_review_btensor_bruteforce.json"), "w"), indent=1)
