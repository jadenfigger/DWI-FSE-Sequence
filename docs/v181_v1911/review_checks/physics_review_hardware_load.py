"""Gradient hardware-load / eddy-current exposure proxies, v7 vs v1.911 (and v1.8 vs v1.81), imaging shot 1.

All numbers are MODEL-ONLY proxies from the mapped waveforms (logical axes, H = grad_var[0] for all axes,
physical time = emitted + rfdelay). They are not a hardware envelope: the real gradient ratings, amplifier
limits and eddy-current kernels of the scanner are unknown.
"""
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from physics_review_common import *
from physics_review_intervals import events
HERE = Path(__file__).resolve().parent
GAM = 42.576e6
TAUS_MS = (0.5, 2.0, 10.0, 50.0, 200.0)


def metrics(label):
    it = mapped(label, shots=2); led = build_ledger(it)
    lag = float(it.vars["rfdelay"].value); H = led["H"]
    fT = H * 1e3 / 32767 / GAM                      # T/m per DAC
    t0, t1 = led["t_start"], led["t_start"] + 0 + (led["adc"][-1]["t_complete"] - led["t_start"]) + 9000
    ev, _ = events(it, led)
    adc = [e for e in ev if e["kind"] == "ADC"]
    res = {"label": label, "T_shot_active_us": t1 - t0}
    for ax in "SPR":
        t = led["G"][ax].t + lag; v = led["G"][ax].v
        m = (t[:-1] >= t0) & (t[:-1] < t1)
        tt = np.concatenate([t[:-1][m], [t[1:][m][-1]]]); vv = v[m]
        dt = np.diff(tt) * 1e-6
        # staircase -> piecewise slopes between sample mid points
        mid = (tt[:-1] + tt[1:]) / 2
        slope = np.diff(vv) / np.maximum(np.diff(mid) * 1e-6, 1e-12) * fT          # T/m/s between consecutive steps
        res[ax] = {"peak_mT_m": float(np.abs(vv).max() * fT * 1e3),
                   "peak_slew_T_m_s_(staircase)": float(np.abs(slope[np.abs(np.diff(mid)) < 20]).max()) if len(slope) else 0.0,
                   "rms_mT_m_active": float(np.sqrt((vv ** 2 * dt).sum() / dt.sum()) * fT * 1e3),
                   "int_G2_dt_(mT/m)^2_s": float((vv ** 2 * dt).sum() * (fT * 1e3) ** 2),
                   "total_variation_mT_m": float(np.abs(np.diff(vv)).sum() * fT * 1e3)}
        # eddy-current proxy: EC_G(t) = sum_i dG_i exp(-(t-t_i)/tau) over steps before t (per unit alpha), T/m
        dG = np.diff(np.concatenate([[0], vv])) * fT; ts = mid
        ec = {}
        for tau in TAUS_MS:
            vals = []
            for a in adc:
                tm = np.linspace(a["t0"], a["t1"], 9)
                # exposure = G_ec(t) averaged over ADC window ; use all steps before t
                acc = []
                for x in tm:
                    k = ts < x
                    acc.append(np.sum(dG[k] * np.exp(-(x - ts[k]) * 1e-3 / tau)))
                vals.append(np.mean(acc) * 1e3)    # mT/m per unit alpha
            ec[str(tau)] = {"ADC_mean_mT_m": [float(x) for x in vals], "absmax_over_echoes": float(np.max(np.abs(vals)))}
        res[ax]["EC_proxy_per_unit_alpha_at_ADC"] = ec
    return res


if __name__ == "__main__":
    out = {"hashes": check_hashes(), "runs": {}}
    for lab in ("v18", "v181", "v7", "v1911"):
        out["runs"][lab] = metrics(lab)
        r = out["runs"][lab]
        print(lab, {ax: (round(r[ax]["peak_mT_m"], 1), round(r[ax]["peak_slew_T_m_s_(staircase)"]), round(r[ax]["rms_mT_m_active"], 2), round(r[ax]["total_variation_mT_m"], 0)) for ax in "SPR"})
        print("    EC proxy S (tau: absmax mT/m per unit alpha):", {k: round(v["absmax_over_echoes"], 4) for k, v in r["S"]["EC_proxy_per_unit_alpha_at_ADC"].items()})
        print("    EC proxy R:", {k: round(v["absmax_over_echoes"], 4) for k, v in r["R"]["EC_proxy_per_unit_alpha_at_ADC"].items()})
    (HERE / "physics_review_hardware_load.json").write_text(json.dumps(out, indent=1))
