"""Independent diffusion+relaxation EPG-path model (ideal instantaneous RF) for v7 vs v1.911.

Per history: complex amplitude, wave-vector n (cycles/m), type F|Z, scalar b = (2pi)^2 int |n(t)|^2 dt (s/mm^2),
including encoded longitudinal (Z) states that keep n.  Exact quadratic integration over the mapped PWC gradient
segments (physical time = emitted + rfdelay).  Relaxation: F exp(-t/T2), Z exp(-t/T1) (no Z0 recovery).
Signal at each ADC = |sum of amplitude*exp(-D b) over histories inside the wanted box|.  CONDITIONAL / MODEL-ONLY.
"""
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from physics_review_common import *
from physics_review_intervals import events
HERE = Path(__file__).resolve().parent
FLIPS = [90, 180, 90, 90, 142.2, 94.9, 69.2, 63.0, 60.2, 60.0, 60.0, 60.0]
PH = [0, 270, 180, 0, 270, 270, 270, 270, 270, 270, 270, 270]
FAC2 = (2 * np.pi) ** 2 * 1e-6      # (cyc/m)^2 * s -> s/mm^2


def segments(led, lag, ta, tb):
    """Constant-gradient sub-segments of [ta, tb]: list of (a, b, g[3] in cyc/m/s)."""
    edges = {ta, tb}
    for ax in "SPR":
        t = led["G"][ax].t + lag
        edges.update(t[(t > ta) & (t < tb)].tolist())
    e = np.array(sorted(edges))
    mid = (e[:-1] + e[1:]) / 2
    fac = led["H"] * 1e3 / 32767 * 1e-6 * 1e6      # DAC -> cyc/m/s
    g = np.stack([led["G"][ax].sample(mid - lag) for ax in "SPR"], 1) * fac
    return e[:-1], e[1:], g


def evolve(typ, n, a, bacc, led, lag, ta, tb, T1, T2):
    s0, s1, g = segments(led, lag, ta, tb)
    F = typ == 0
    nF = n[F].copy(); bF = np.zeros(F.sum()); bZ = 0.0
    nZ = n[~F]
    bz_acc = np.zeros((~F).sum())
    for x0, x1, gg in zip(s0, s1, g):
        dt = (x1 - x0) * 1e-6
        bF += ((nF ** 2).sum(1) * dt + (nF @ gg) * dt ** 2 + (gg @ gg) * dt ** 3 / 3)
        nF = nF + gg * dt
        bz_acc += (nZ ** 2).sum(1) * dt
    n[F] = nF
    bacc[F] += bF * FAC2; bacc[~F] += bz_acc * FAC2
    T = (tb - ta) * 1e-6
    a[F] *= np.exp(-T / T2); a[~F] *= np.exp(-T / T1)
    return n, a, bacc


def run(led, ev, lag, b1, T1=1.3, T2=0.032, amin=1e-5):
    rf = [e for e in ev if e["kind"] == "RF"]; adc = [e for e in ev if e["kind"] == "ADC"]
    seq = sorted([(e["centre"], "RF", e["idx"]) for e in rf] + [(e["centre"], "ADC", e["idx"]) for e in adc])
    typ = np.array([1]); n = np.zeros((1, 3)); a = np.ones(1, complex); bacc = np.zeros(1)
    tprev = seq[0][0]; out = {}
    for t, kind, idx in seq:
        n, a, bacc = evolve(typ, n, a, bacc, led, lag, tprev, t, T1, T2)
        tprev = t
        if kind == "ADC":
            F = typ == 0
            out[idx + 1] = (n[F].copy(), a[F].copy(), bacc[F].copy()); continue
        al = -np.deg2rad(FLIPS[idx] * b1); phi = np.deg2rad(PH[idx])
        c2, s2, sa, ca = np.cos(al / 2) ** 2, np.sin(al / 2) ** 2, np.sin(al), np.cos(al)
        e = np.exp; F = typ == 0; Z = ~F
        parts = [(F, 0, 1, c2 * a, False), (F, 0, -1, s2 * e(2j * phi) * np.conj(a), True),
                 (F, 1, 1, -0.5j * e(-1j * phi) * sa * a, False), (F, 1, -1, 0.5j * e(1j * phi) * sa * np.conj(a), True),
                 (Z, 0, 1, -1j * e(1j * phi) * sa * a, False), (Z, 1, 1, ca * a, False)]
        nt, nn, na, nb = [], [], [], []
        for src, d_, sg, amp, _ in parts:
            keep = src & (np.abs(amp) > amin)
            nt.append(np.full(keep.sum(), d_)); nn.append(n[keep] * sg); na.append(amp[keep]); nb.append(bacc[keep])
        typ = np.concatenate(nt); n = np.vstack(nn); a = np.concatenate(na); bacc = np.concatenate(nb)
    return out


def echo_signal(o, D):
    n, a, b = o
    m = (np.abs(n[:, 0]) < 1500) & (np.abs(n[:, 2]) < 2000)
    top = np.argmax(np.where(m, np.abs(a), 0)); ref = n[top]
    sel = (np.abs(n[:, 0] - ref[0]) < 250) & (np.abs(n[:, 1] - ref[1]) < 1e3 / 35) & (np.abs(n[:, 2] - ref[2]) < 1828)
    return abs((a[sel] * np.exp(-D * b[sel])).sum()), float(np.average(b[sel], weights=np.abs(a[sel]))), int(sel.sum())


if __name__ == "__main__":
    import time
    res = {"hashes": check_hashes(), "note": "MODEL-ONLY: ideal RF, box voxel, no finite slice profile, no Z0 recovery", "cases": []}
    L = {}
    for lab in ("v7", "v1911"):
        it = mapped(lab, shots=2); led = build_ledger(it); ev, lag = events(it, led); L[lab] = (led, ev, lag)
    for b1 in (1.0, 0.9):
        for (T1, T2, tag) in ((1e9, 1e9, "no_relax"), (1.3, 0.032, "T1 1.3 T2 32ms"), (1.3, 0.060, "T1 1.3 T2 60ms")):
            O = {}
            for lab in L:
                t0 = time.time(); O[lab] = run(*L[lab], b1, T1, T2); print(lab, b1, tag, round(time.time() - t0, 1), "s", flush=True)
            for D in (0.0, 0.0005, 0.002):
                s7 = [echo_signal(O["v7"][j], D) for j in range(1, 9)]; s9 = [echo_signal(O["v1911"][j], D) for j in range(1, 9)]
                r = [x[0] / y[0] for x, y in zip(s9, s7)]
                res["cases"].append({"B1": b1, "relax": tag, "D": D, "v7": [x[0] for x in s7], "v1911": [x[0] for x in s9], "ratio": r,
                                     "mean_b_v7": [x[1] for x in s7], "mean_b_v1911": [x[1] for x in s9], "n_sel": [x[2] for x in s7]})
                print(b1, tag, D, "ratio v1911/v7:", np.round(r, 4), " mean b(v7):", np.round([x[1] for x in s7], 1), "(v1911):", np.round([x[1] for x in s9], 1))
    (HERE / "physics_review_diffusion_epg.json").write_text(json.dumps(res, indent=1))
