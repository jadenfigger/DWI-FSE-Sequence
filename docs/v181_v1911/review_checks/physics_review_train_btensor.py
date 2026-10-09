"""Exact b tensor (incl. encoded longitudinal storage) of the dominant wanted histories of v7 and v1.911.
Histories are the top-weight members of the wanted box from the ideal-RF enumerator (physics_review_pathways)."""
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from physics_review_common import *
from physics_review_intervals import events
import physics_review_pathways as PW
from physics_review_diffusion_epg import segments
HERE = Path(__file__).resolve().parent


def replay(led, ev, lag, digits, upto_adc):
    """digits: base-7 tags per RF (1 F->F, 2 F->F*, 3 F->Z kept, 6 F->Z flipped, 4 Z->F, 5 Z->Z). Returns k_end, B(3x3), time on Z."""
    rf = [e for e in ev if e["kind"] == "RF"]; adc = [e for e in ev if e["kind"] == "ADC"]
    seq = sorted([(e["centre"], "RF", e["idx"]) for e in rf] + [(e["centre"], "ADC", e["idx"]) for e in adc])
    k = np.zeros(3); isF = False; B = np.zeros((3, 3)); tprev = seq[0][0]; zt = 0.0
    for t, kind, idx in seq:
        s0, s1, g = segments(led, lag, tprev, t)
        for x0, x1, gg in zip(s0, s1, g):
            dt = (x1 - x0) * 1e-6
            if isF:
                B += np.outer(k, k) * dt + (np.outer(k, gg) + np.outer(gg, k)) * dt ** 2 / 2 + np.outer(gg, gg) * dt ** 3 / 3
                k = k + gg * dt
            else:
                B += np.outer(k, k) * dt; zt += dt
        tprev = t
        if kind == "ADC":
            if idx + 1 == upto_adc:
                return k, (2 * np.pi) ** 2 * 1e-6 * B, zt
            continue
        tag = digits[idx]
        if tag == 1: pass
        elif tag == 2: k = -k
        elif tag == 3: isF = False
        elif tag == 6: isF = False; k = -k
        elif tag == 4: isF = True
        elif tag == 5: pass
        elif tag == 0: isF = True        # first RF (Z->F) handled as tag 4 below
    return None


if __name__ == "__main__":
    out = {"hashes": check_hashes(), "rows": []}
    L = {}
    for lab in ("v7", "v1911"):
        it = mapped(lab, shots=2); led = build_ledger(it); ev, lag = events(it, led); L[lab] = (led, ev, lag)
    # enumerate with codes in v7
    E7 = PW.enumerate_shot(*L["v7"], 1.0)
    for j in range(1, 9):
        n, w, c = E7[j]
        m = (np.abs(n[:, 0]) < 1500) & (np.abs(n[:, 2]) < 2000)
        top = np.argsort(-np.where(m, w, 0))[:3]
        for rank, ii in enumerate(top):
            code = int(c[ii]); digs = []
            while code: digs.append(code % 7); code //= 7
            digs = digs[::-1]
            row = {"echo": j, "rank": rank + 1, "weight": float(w[ii]), "digits": "".join(map(str, digs)), "n_S_end_v7": float(n[ii][0])}
            for lab in ("v7", "v1911"):
                k, B, zt = replay(*L[lab], digs, j)
                row[lab] = {"k_end": k.tolist(), "trace": float(np.trace(B)), "B": B.tolist(), "z_time_us": zt * 1e6}
            out["rows"].append(row)
            print(j, rank + 1, "w %.3f" % w[ii], row["digits"], "trace v7 %.2f v1911 %.2f  (d %+0.2f)  Z-time %.0f/%.0f us" % (
                row["v7"]["trace"], row["v1911"]["trace"], row["v1911"]["trace"] - row["v7"]["trace"], row["v7"]["z_time_us"], row["v1911"]["z_time_us"]),
                " kS_end %.1f/%.1f" % (row["v7"]["k_end"][0], row["v1911"]["k_end"][0]))
    (HERE / "physics_review_train_btensor.json").write_text(json.dumps(out, indent=1))
