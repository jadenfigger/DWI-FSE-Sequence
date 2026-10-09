"""Direction/polarity dependence, per-echo read endpoints and default-state (dummy/nav) shots, v1.8 vs v1.81."""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from physics_review_common import *
from physics_review_btensor import analyse, union_wave, integrate, adc_geometry
HERE = Path(__file__).resolve().parent
out = {}
# 1. direction dependence at b=1000 and 6000, E1 trace
dirs = {"+X(read)": (1000, 0, 0), "-X(read)": (-1000, 0, 0), "+Y(phase)": (0, 1000, 0), "+Z(slice)": (0, 0, 1000),
        "(+1,+1,+1)/sqrt3": (577, 577, 577), "(-1,+1,+1)/sqrt3": (-577, 577, 577)}
out["direction"] = {}
for dname, d in dirs.items():
    for b in (1000, 6000):
        r = {}
        for lab in ("v18", "v181"):
            a = analyse(lab, b, d)
            e = a["echoes"][0]
            r[lab] = {"E1_total": e["trace_total"], "E1_img": e["trace_img"], "E1_diffonly": e["trace_diffonly"], "E1_cross": e["trace_cross"],
                      "E8_total": a["echoes"][7]["trace_total"]}
        out["direction"][f"{dname} b{b}"] = r
        print(dname, b, {k: (round(v["E1_total"], 2), round(v["E1_cross"], 2)) for k, v in r.items()})
# 2. per-echo read endpoints (b=1000, +X)
out["read_endpoint"] = {}
for lab in ("v18", "v181"):
    a = analyse(lab, 1000, (1000, 0, 0))
    out["read_endpoint"][lab] = {"kR_cyc_m": [e["k_total_SPR"][2] for e in a["echoes"]],
                                  "kP_cyc_m": [e["k_total_SPR"][1] for e in a["echoes"]],
                                  "kS_cyc_m": [e["k_total_SPR"][0] for e in a["echoes"]]}
    print(lab, "kR per echo", np.round(out["read_endpoint"][lab]["kR_cyc_m"], 4))
# 3. readout slope at ADC1 centre -> echo shift in samples/us
it = mapped("v181", shots=1); led = build_ledger(it)
H = led["H"]; fac = H * 1e3 / 32767 * 1e-6
t, v = led["G"]["R"].t, led["G"]["R"].v
geo = adc_geometry(it, led)
mid = geo[0][1] - float(it.vars["rfdelay"].value)
i = np.searchsorted(t, mid, side="right") - 1
slope_cyc_m_per_us = v[i] * fac     # cycles/m per us
dk = out["read_endpoint"]["v181"]["kR_cyc_m"][0] - out["read_endpoint"]["v18"]["kR_cyc_m"][0]
fov = 35e-3; dk_pix = 1 / fov
out["echo_shift"] = {"read_amp_DAC_at_ADC1_centre": float(v[i]), "dk_cyc_m_per_us": slope_cyc_m_per_us, "dkR_E1_v181_minus_v18": dk,
                     "shift_us": -dk / slope_cyc_m_per_us, "sample_period_us": geo[0][3], "shift_samples": -dk / slope_cyc_m_per_us / geo[0][3],
                     "kspace_pixel_cyc_m": dk_pix, "shift_in_kpixels": dk / dk_pix}
print(out["echo_shift"])
# 4. default state (dummy+navigator+imaging) ADC1 read endpoint per shot
out["default_state"] = {}
for lab in ("v18", "v181"):
    it = mapped(lab, imaging=False, shots=8)
    shots = [e[1] for e in it.misc_events if e[0] == "shot"]
    H = float(it.vars["grad_var"].value[0]); lag = float(it.vars["rfdelay"].value)
    rows = []
    for s in range(1, 8):
        led = build_ledger(it, shot_index=s)
        if not led["rf"] or not led["adc"]:
            rows.append({"shot": s, "rf": len(led["rf"]), "adc": len(led["adc"])}); continue
        wave = union_wave(led, [(led, 1.0)])
        geo = adc_geometry(it, led)
        res = integrate(wave, H, lag, [p["t_center"] for p in led["rf"][1:]], [g[1] for g in geo], led["rf"][0]["t_center"])
        rows.append({"shot": s, "rf": len(led["rf"]), "adc": len(led["adc"]), "kR_E1": float(res[0][0][2]), "kR_E2": float(res[1][0][2]) if len(res) > 1 else None,
                     "trace_E1": float(np.trace(res[0][1]))})
    out["default_state"][lab] = rows
    print(lab, [(r["shot"], r["rf"], r["adc"], round(r.get("kR_E1", np.nan), 4), round(r.get("trace_E1", np.nan), 2)) for r in rows])
(HERE / "physics_review_btensor2.json").write_text(json.dumps(out, indent=1))
