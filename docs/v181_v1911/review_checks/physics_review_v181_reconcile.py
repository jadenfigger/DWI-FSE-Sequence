"""Reconcile v1.8 -> v1.81 grid-pathway ratios (0.85-1.43) with my coherent-box EPG (identical).
Own EPG-path model with: Z0 recovery lineages, T1/T2, diffusion, box-voxel sinc weighting of every history at the
ADC mid sample (sinc(k*width), widths S 1 mm, P 35/136 mm, R 35/128 mm), B1/phase/B0 grid.  Ideal RF at array centre.
RF flips from mapped multipliers: 90 / 8 x 180 (nominal), B1 scales the angle.  MODEL-ONLY."""
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from physics_review_common import *
from physics_review_intervals import events
import physics_review_diffusion_epg as DE
HERE = Path(__file__).resolve().parent
W = np.array([1e-3, 35e-3 / 136, 35e-3 / 128])
FL = [90] + [180] * 8


def run(led, ev, lag, ph, b1, df, ph0, T1=1.3, T2=0.032, D=0.002, amin=1e-5, record=False):
    rf = [e for e in ev if e["kind"] == "RF"]; adc = [e for e in ev if e["kind"] == "ADC"]
    seq = sorted([(e["centre"], "RF", e["idx"]) for e in rf] + [(e["centre"], "ADC", e["idx"]) for e in adc])
    typ = np.array([1]); n = np.zeros((1, 3)); a = np.ones(1, complex); bacc = np.zeros(1)
    tprev = seq[0][0]; out = {}
    for t, kind, idx in seq:
        n, a, bacc = DE.evolve(typ, n, a, bacc, led, lag, tprev, t, T1, T2)
        dt = (t - tprev) * 1e-6
        a[typ == 0] *= np.exp(1j * 2 * np.pi * df * dt)
        if dt > 0:                                   # Z0 recovery lineage
            rec = 1 - np.exp(-dt / T1)
            typ = np.append(typ, 1); n = np.vstack((n, np.zeros(3))); a = np.append(a, rec + 0j); bacc = np.append(bacc, 0.0)
        tprev = t
        if kind == "ADC":
            F = typ == 0
            sig = a[F] * np.sinc(n[F] * W).prod(1) * np.exp(-D * bacc[F])
            out[idx + 1] = (n[F].copy(), sig, a[F].copy())
            continue
        al = -np.deg2rad(FL[idx] * b1); phi = np.deg2rad(ph[idx] + (ph0 if idx == 0 else 0))
        c2, s2, sa, ca = np.cos(al / 2) ** 2, np.sin(al / 2) ** 2, np.sin(al), np.cos(al)
        e = np.exp; F = typ == 0; Z = ~F
        parts = [(F, 0, 1, c2 * a), (F, 0, -1, s2 * e(2j * phi) * np.conj(a)), (F, 1, 1, -0.5j * e(-1j * phi) * sa * a),
                 (F, 1, -1, 0.5j * e(1j * phi) * sa * np.conj(a)), (Z, 0, 1, -1j * e(1j * phi) * sa * a), (Z, 1, 1, ca * a)]
        nt, nn, na, nb = [], [], [], []
        for src, d_, sg, amp in parts:
            keep = src & (np.abs(amp) > amin)
            nt.append(np.full(keep.sum(), d_)); nn.append(n[keep] * sg); na.append(amp[keep]); nb.append(bacc[keep])
        typ = np.concatenate(nt); n = np.vstack(nn); a = np.concatenate(na); bacc = np.concatenate(nb)
    return out


if __name__ == "__main__":
    L = {}
    for lab in ("v18", "v181"):
        it = mapped(lab, shots=2); led = build_ledger(it); ev, lag = events(it, led); L[lab] = (led, ev, lag)
    ph = [p["phase_deg"] for p in L["v18"][0]["rf"]]
    grid = json.load(open(HERE / "final_physics_grid.json"))["pathway"]["pairs"]["v181"]["rows"]
    res = []
    for g in grid:
        o = {lab: run(*L[lab], ph, g["B1"], g["B0_Hz"], g["phase_deg"]) for lab in L}
        s = {lab: np.array([abs(o[lab][j][1].sum()) for j in range(1, 9)]) for lab in L}
        res.append({"B1": g["B1"], "df": g["B0_Hz"], "ph": g["phase_deg"], "v18": s["v18"].tolist(), "v181": s["v181"].tolist(),
                    "ratio": (s["v181"] / s["v18"]).tolist(), "grid_before": g["before_abs"], "grid_after": g["after_abs"]})
        print(g["B1"], g["B0_Hz"], g["phase_deg"], "mine v18", np.round(s["v18"][:4], 4), "grid", np.round(g["before_abs"][:4], 4),
              "ratio mine", np.round((s["v181"] / s["v18"])[:8], 3), "grid", np.round(g["after_over_before"], 3), flush=True)
    json.dump(res, open(HERE / "physics_review_v181_reconcile.json", "w"), indent=1)
