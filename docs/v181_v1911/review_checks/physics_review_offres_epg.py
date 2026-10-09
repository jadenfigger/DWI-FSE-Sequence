"""Why can a pure time-compression (ESP 14.0 -> 13.0 ms) change the echo amplitude at B0 != 0 although all
gradient pathways are identical?  Complex ideal-RF EPG-path coherent sum with off-resonance phase advance per free
interval (instantaneous RF at centre; no relaxation/diffusion; no finite-RF/slice-profile).  v7 vs v1.911 ratio of
|sum of wanted-box paths|.  Handedness: repo phase 0 maps Mz->+My; implemented by alpha -> -alpha in standard EPG."""
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from physics_review_common import *
from physics_review_intervals import events, axis_area_cyc_m
HERE = Path(__file__).resolve().parent
FLIPS = [90, 180, 90, 90, 142.2, 94.9, 69.2, 63.0, 60.2, 60.0, 60.0, 60.0]
PH = [0, 270, 180, 0, 270, 270, 270, 270, 270, 270, 270, 270]
AMIN = 3e-4


def run(led, ev, lag, b1, df, ph0):
    rf = [e for e in ev if e["kind"] == "RF"]; adc = [e for e in ev if e["kind"] == "ADC"]
    seq = sorted([(e["centre"], "RF", e["idx"]) for e in rf] + [(e["centre"], "ADC", e["idx"]) for e in adc])
    typ = np.array([1]); n = np.zeros((1, 3)); a = np.ones(1, complex)
    tprev = seq[0][0]; out = {}
    for t, kind, idx in seq:
        dt = (t - tprev) * 1e-6
        inc = np.array([axis_area_cyc_m(led, ax, tprev, t, lag) for ax in "SPR"]) if False else None
        tprev_old = tprev; tprev = t
        inc = np.array([axis_area_cyc_m(led, ax, tprev_old, t, lag) for ax in "SPR"])
        F = typ == 0
        n[F] += inc
        a[F] *= np.exp(1j * 2 * np.pi * df * dt)
        if kind == "ADC":
            out[idx + 1] = (n[F].copy(), a[F].copy()); continue
        al = -np.deg2rad(FLIPS[idx] * b1)
        phi = np.deg2rad(PH[idx] + (ph0 if idx == 0 else 0))
        c2, s2, sa, ca = np.cos(al / 2) ** 2, np.sin(al / 2) ** 2, np.sin(al), np.cos(al)
        e = np.exp
        Z = ~F
        parts = []
        parts.append((F, 0, 1, c2 * a))
        parts.append((F, 0, -1, s2 * e(2j * phi) * np.conj(a)))
        parts.append((F, 1, 1, -0.5j * e(-1j * phi) * sa * a))
        parts.append((F, 1, -1, 0.5j * e(1j * phi) * sa * np.conj(a)))
        parts.append((Z, 0, 1, -1j * e(1j * phi) * sa * a))
        parts.append((Z, 1, 1, ca * a))
        nt, nn, na = [], [], []
        for src, dt_, sg, amp in parts:
            keep = src & (np.abs(amp) > AMIN)
            nt.append(np.full(keep.sum(), dt_)); nn.append(n[keep] * sg); na.append(amp[keep])
        typ = np.concatenate(nt); n = np.vstack(nn); a = np.concatenate(na)
    return out


def signal(out_j, box=250.0, tolP=1e3 / 35.0, tolR=1828.0):
    n, a = out_j
    m = (np.abs(n[:, 0]) < 1500) & (np.abs(n[:, 2]) < 2000)
    top = np.argmax(np.where(m, np.abs(a), 0)); ref = n[top]
    sel = (np.abs(n[:, 0] - ref[0]) < box) & (np.abs(n[:, 1] - ref[1]) < tolP) & (np.abs(n[:, 2] - ref[2]) < tolR)
    return abs(a[sel].sum())


if __name__ == "__main__":
    L = {}
    for lab in ("v7", "v1911"):
        it = mapped(lab, shots=2); led = build_ledger(it); ev, lag = events(it, led); L[lab] = (led, ev, lag)
    rows = []
    for b1 in (0.8, 0.9, 1.0, 1.1):
        for df in (-128.0, 0.0, 128.0):
            for ph0 in (0.0, 45.0, 90.0):
                s = {lab: [signal(run(*L[lab], b1, df, ph0)[j]) for j in range(1, 9)] for lab in L}
                r = np.array(s["v1911"]) / np.maximum(np.array(s["v7"]), 1e-12)
                rows.append({"B1": b1, "df": df, "ph0": ph0, "v7": s["v7"], "v1911": s["v1911"], "ratio": r.tolist()})
    allr = np.array([r["ratio"] for r in rows])
    print("EPG(ideal RF, no relaxation) ratio v1911/v7 per echo: min", np.round(allr.min(0), 4), "max", np.round(allr.max(0), 4))
    print("df=0 rows: min/max ratio", np.array([r["ratio"] for r in rows if r["df"] == 0]).min(), np.array([r["ratio"] for r in rows if r["df"] == 0]).max())
    for df in (-128.0, 128.0):
        rr = np.array([r["ratio"] for r in rows if r["df"] == df]); print("df", df, "min", np.round(rr.min(0), 4), "max", np.round(rr.max(0), 4))
    print("nominal(B1 1,df 0, ph0 0) |S| v7", np.round([r for r in rows if r['B1']==1.0 and r['df']==0 and r['ph0']==0][0]['v7'], 4))
    (HERE / "physics_review_offres_epg.json").write_text(json.dumps({"hashes": check_hashes(), "rows": rows}, indent=1))
