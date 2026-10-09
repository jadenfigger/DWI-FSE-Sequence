"""v7 vs v1.911: gradient area in every inter-event interval (RF extents, ADC windows) per logical axis.

Own implementation. Events from the mapper: each transmitted RF frame extent [t_go, t_go + n*dt] and each
ADC window [t_init + discard*sp, ... + N*sp] split at its middle.  Gradient physical time = emitted + rfdelay.
"""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from physics_review_common import *
HERE = Path(__file__).resolve().parent


def events(it, led):
    lag = float(it.vars["rfdelay"].value)
    n = it.vars["no_samples"].value
    ev = []
    for j, p in enumerate(led["rf"]):
        t0 = float(p["t_go"]); t1 = t0 + p["dt"] * len(p["samples"])
        nz = np.nonzero(p["amp"])[0]
        ev.append({"kind": "RF", "idx": j, "frame": p["frame"], "t0": t0, "t1": t1, "centre": p["t_center"],
                   "nz0": float(p["t"][nz[0]]) if len(nz) else t0, "nz1": float(p["t"][nz[-1]] + p["dt"]) if len(nz) else t1})
    for j, a in enumerate(led["adc"]):
        sp = a["sample_period_ticks"] / 10.0
        s0 = a["t_init"] + a["discard"] * sp
        ev.append({"kind": "ADC", "idx": j, "t0": s0, "t1": s0 + n * sp, "centre": s0 + n * sp / 2, "t_init": a["t_init"]})
    ev.sort(key=lambda e: e["t0"])
    return ev, lag


def axis_area_cyc_m(led, ax, a, b, lag):
    t, v = led["G"][ax].t, led["G"][ax].v
    lo = np.clip(t[:-1] + lag, a, b); hi = np.clip(t[1:] + lag, a, b)
    return float(np.sum(v * (hi - lo))) * led["H"] * 1e3 / 32767.0 * 1e-6


def interval_table(it, led, mode="full"):
    ev, lag = events(it, led)
    rows = []
    # boundary list: for RF -> (t0,t1) ; ADC -> (t0, centre, t1)
    bnd = []
    for e in ev:
        if e["kind"] == "RF":
            t0, t1 = (e["t0"], e["t1"]) if mode == "full" else (e["nz0"], e["nz1"])
            bnd += [(t0, f"RF{e['idx']}_start"), (t1, f"RF{e['idx']}_end")]
        else:
            bnd += [(e["t0"], f"ADC{e['idx']+1}_start"), (e["centre"], f"ADC{e['idx']+1}_mid"), (e["t1"], f"ADC{e['idx']+1}_end")]
    bnd.sort()
    for (ta, na), (tb, nb) in zip(bnd[:-1], bnd[1:]):
        rows.append({"from": na, "to": nb, "dur_us": tb - ta,
                     "area_SPR_cyc_m": [axis_area_cyc_m(led, ax, ta, tb, lag) for ax in "SPR"]})
    return rows


if __name__ == "__main__":
    out = {"hashes": check_hashes(), "mode": "gradient physical time = emitted + rfdelay (60 us); RF extents full frame", "cases": {}}
    cases = {"imaging_shot1": dict(overrides={}, imaging=True),
             }
    for label in ("v7", "v1911"):
        it = mapped(label, shots=2)
        led = build_ledger(it)
        out["cases"][label] = {"rows": interval_table(it, led, "full"), "rows_nz": interval_table(it, led, "nz"),
                               "events": events(it, led)[0]}
    a, b = out["cases"]["v7"]["rows"], out["cases"]["v1911"]["rows"]
    assert [r["from"] for r in a] == [r["from"] for r in b], "event order differs"
    worst = 0; tab = []
    for ra, rb in zip(a, b):
        d = np.array(rb["area_SPR_cyc_m"]) - np.array(ra["area_SPR_cyc_m"])
        tab.append({"from": ra["from"], "to": ra["to"], "v7": ra["area_SPR_cyc_m"], "v1911": rb["area_SPR_cyc_m"], "diff": d.tolist(),
                    "dur_v7": ra["dur_us"], "dur_v1911": rb["dur_us"]})
        worst = max(worst, float(np.abs(d).max()))
    out["comparison_full"] = tab; out["max_abs_diff_cyc_m"] = worst
    # the same with RF nonzero-sample extents
    a, b = out["cases"]["v7"]["rows_nz"], out["cases"]["v1911"]["rows_nz"]
    out["max_abs_diff_nz_cyc_m"] = max(float(np.abs(np.array(rb["area_SPR_cyc_m"]) - np.array(ra["area_SPR_cyc_m"])).max()) for ra, rb in zip(a, b))
    print("max |area diff| per interval, full RF extents: %.6f cyc/m; nonzero-RF extents: %.6f" % (worst, out["max_abs_diff_nz_cyc_m"]))
    for r in tab:
        print("%-16s -> %-16s dur %8.1f/%8.1f  v7 %s  d %s" % (r["from"], r["to"], r["dur_v7"], r["dur_v1911"],
              np.round(r["v7"], 3), np.round(r["diff"], 5)))
    # remove bulky per-case rows? keep
    (HERE / "physics_review_intervals.json").write_text(json.dumps(out, indent=1, default=float))
