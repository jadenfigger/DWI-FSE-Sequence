"""Own EPG-style (instantaneous RF) configuration-state enumeration of the 12-RF / 8-ADC ss-MGOT shot.

Each history = (type F|Z, wave-vector n in cycles/m, weight).  Flip schedule: prep 90, 180, tip 90, reexc 90,
imaging 142.2/94.9/69.2/63.0/60.2/60/60/60 (mapped RF multipliers 505,337,246,224,214,213... are proportional to
these); RF treated as ideal, B1 = 1 (and optionally 0.9).  Gradient increments between events are exact PWC areas
of the mapped waveforms with physical delay = rfdelay.  Pure geometry/weight bookkeeping: no relaxation, diffusion
or finite-RF effects.  Compares v7 and v1.911 history-by-history.
"""
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from physics_review_common import *
from physics_review_intervals import events, axis_area_cyc_m
HERE = Path(__file__).resolve().parent
FLIPS = [90, 180, 90, 90, 142.2, 94.9, 69.2, 63.0, 60.2, 60.0, 60.0, 60.0]
WMIN = 1e-5


def enumerate_shot(led, ev, lag, b1=1.0, flips=FLIPS):
    rf = [e for e in ev if e["kind"] == "RF"]; adc = [e for e in ev if e["kind"] == "ADC"]
    seq = sorted([(e["centre"], "RF", e["idx"]) for e in rf] + [(e["centre"], "ADC", e["idx"]) for e in adc])
    typ = np.array([1]); n = np.zeros((1, 3)); w = np.ones(1)         # Z at equilibrium
    tprev = seq[0][0]; out = {}
    ids = [np.zeros(1, dtype=np.int64)]                                 # history id per state (base-5 code)
    code = np.zeros(1, dtype=np.int64)
    for t, kind, idx in seq:
        inc = np.array([axis_area_cyc_m(led, ax, tprev, t, lag) for ax in "SPR"])
        n[typ == 0] += inc
        tprev = t
        if kind == "ADC":
            m = typ == 0
            out[idx + 1] = (n[m].copy(), w[m].copy(), code[m].copy())
            continue
        a = np.deg2rad(flips[idx] * b1)
        # Z_k' receives F_k (order kept) and F*_{-k} (order flipped): two Z branches (tags 3, 6)
        c2, s2, sa, ca = np.cos(a / 2) ** 2, np.sin(a / 2) ** 2, abs(np.sin(a)), abs(np.cos(a))
        nt, nn, nw, nc = [], [], [], []
        F = typ == 0; Z = ~F
        for (src, dst_t, dst_sign, coef, tag) in ((F, 0, +1, c2, 1), (F, 0, -1, s2, 2), (F, 1, +1, sa / 2, 3), (F, 1, -1, sa / 2, 6), (Z, 0, +1, sa, 4), (Z, 1, +1, ca, 5)):
            keep = src & (w * coef > WMIN)
            nt.append(np.full(keep.sum(), dst_t)); nn.append(n[keep] * dst_sign); nw.append(w[keep] * coef)
            nc.append(code[keep] * 7 + tag)
        typ = np.concatenate(nt); n = np.vstack(nn); w = np.concatenate(nw); code = np.concatenate(nc)
    return out


if __name__ == "__main__":
    B1 = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    res = {"hashes": check_hashes(), "B1": B1, "WMIN": WMIN, "flips_deg": FLIPS, "per_echo": [],
           "model": "Weigel-EPG ideal-RF configuration states; F->Z has two branches (order kept / flipped); weights are |transfer coefficients|"}
    E = {}
    for lab in ("v7", "v1911"):
        it = mapped(lab, shots=2); led = build_ledger(it); ev, lag = events(it, led)
        E[lab] = enumerate_shot(led, ev, lag, B1)
    TOL_P, TOL_R = 1e3 / 35.0, 1828.0
    for j in range(1, 9):
        n7, w7, c7 = E["v7"][j]; n9, w9, c9 = E["v1911"][j]
        same = (len(c7) == len(c9)) and np.array_equal(np.sort(c7), np.sort(c9))
        row = {"echo": j, "n_hist_v7": int(len(w7)), "n_hist_v1911": int(len(w9)), "same_history_set": bool(same)}
        o7 = np.argsort(c7); o9 = np.argsort(c9)
        if same:
            d = n9[o9] - n7[o7]
            row["max_abs_dn_cyc_m_SPR"] = np.abs(d).max(axis=0).tolist()
        for lab, (n, w, c) in (("v7", E["v7"][j]), ("v1911", E["v1911"][j])):
            top = np.argmax(np.where((np.abs(n[:, 0]) < 1500) & (np.abs(n[:, 2]) < 2000), w, 0))
            ref = n[top]
            dS = n[:, 0] - ref[0]; dP = n[:, 1] - ref[1]; dR = n[:, 2] - ref[2]
            base = (np.abs(dP) < TOL_P) & (np.abs(dR) < TOL_R)
            wanted = base & (np.abs(dS) < 250)
            unw = base & (np.abs(dS) >= 250) & (np.abs(dS) < 4000) & (w > 1e-3)
            near = np.sort(np.abs(dS[unw]))[:3] if unw.any() else np.array([])
            row[lab] = {"ref_n": ref.tolist(), "wanted_hist": int(wanted.sum()), "wanted_weight": float(w[wanted].sum()),
                        "unwanted_nearP,R_hist(250<=|dS|<4000,w>1e-3)": int(unw.sum()),
                        "unwanted_weight": float(w[unw].sum()), "closest_unwanted_dS": near.tolist(),
                        "closest_unwanted_weight": float(w[unw][np.argmin(np.abs(dS[unw]))]) if unw.any() else None}
            # boundary-sensitivity: histories whose classification could flip under +-1.5 cyc/m
            for tol in (250, 500, 1000, 2000):
                row[lab][f"borderline_dS_{tol}_(+-1.5cyc/m,w>1e-4)"] = int((base & (np.abs(np.abs(dS) - tol) < 1.5) & (w > 1e-4)).sum())
        res["per_echo"].append(row)
        print(j, "hist", row["n_hist_v7"], row["n_hist_v1911"], same, np.round(row.get("max_abs_dn_cyc_m_SPR"), 3),
              "wanted w %.4f/%.4f" % (row["v7"]["wanted_weight"], row["v1911"]["wanted_weight"]),
              "unw closest dS", np.round(row["v7"]["closest_unwanted_dS"][:1], 1), np.round(row["v1911"]["closest_unwanted_dS"][:1], 1),
              "w", row["v7"]["closest_unwanted_weight"] and round(row["v7"]["closest_unwanted_weight"], 4),
              "borderline", [row["v7"][k] for k in row["v7"] if k.startswith("borderline")])
    (HERE / f"physics_review_pathways_B1_{B1}.json").write_text(json.dumps(res, indent=1))
