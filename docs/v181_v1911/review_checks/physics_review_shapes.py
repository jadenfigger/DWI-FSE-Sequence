"""Piecewise-linear skeleton (vertices) of each logical-axis output around chosen RF/ADC events, v7 vs v1.911."""
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from physics_review_common import *
from physics_review_intervals import events
HERE = Path(__file__).resolve().parent


def skeleton(t, v, lag, lo, hi, tol=0.6):
    """Return vertices [(t_phys, value)] of a piecewise-linear fit of the PWC (sample-hold) staircase."""
    m = (t[:-1] + t[1:]) / 2 + lag
    sel = (m >= lo) & (m <= hi)
    tt, vv = m[sel], v[sel]
    if len(tt) == 0:
        return []
    verts = [(float(t[:-1][sel][0] + lag), float(vv[0]))]
    # collapse equal-slope runs
    i = 0
    pts = [(tt[j], vv[j]) for j in range(len(tt))]
    out = [pts[0]]
    for j in range(1, len(pts) - 1):
        s1 = (pts[j][1] - pts[j - 1][1]) / max(pts[j][0] - pts[j - 1][0], 1e-9)
        s2 = (pts[j + 1][1] - pts[j][1]) / max(pts[j + 1][0] - pts[j][0], 1e-9)
        gap = pts[j + 1][0] - pts[j][0] > 20 or pts[j][0] - pts[j - 1][0] > 20
        if abs(s1 - s2) > 0.02 * max(1, abs(s1), abs(s2)) or gap or abs(pts[j][1]) < 0.5 and abs(pts[j - 1][1]) > 0.5:
            out.append(pts[j])
    out.append(pts[-1])
    return [(round(float(a), 1), round(float(b), 1)) for a, b in out]


if __name__ == "__main__":
    which = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    res = {}
    for lab in ("v7", "v1911"):
        it = mapped(lab, shots=2); led = build_ledger(it); ev, lag = events(it, led)
        rf = [e for e in ev if e["kind"] == "RF"]
        r0 = rf[which]; rprev = rf[which - 1]
        lo = r0["t0"] - 5600; hi = r0["t1"] + 600
        print("=====", lab, "RF%d" % which, r0["t0"], r0["t1"], "window rel RF start")
        res[lab] = {}
        for ax in "SPR":
            sk = skeleton(led["G"][ax].t, led["G"][ax].v, lag, lo, hi)
            res[lab][ax] = sk
            rel = [(round(a - r0["t0"], 1), b) for a, b in sk]
            print(" ", ax, rel)
        adcs = [e for e in ev if e["kind"] == "ADC"]
        for e in adcs:
            if lo - 4000 < e["t0"] < hi:
                print("  ADC t0..t1 rel RF start:", round(e["t0"] - r0["t0"], 1), round(e["t1"] - r0["t0"], 1), "t_init", round(e["t_init"] - r0["t0"], 1))
        for a in led["adc"]:
            if lo - 4000 < a["t_init"] < hi:
                print("  ADC t_complete rel RF start:", round(a["t_complete"] - r0["t0"], 1))
        print("  prev RF end rel:", round(rprev["t1"] - r0["t0"], 1))
