"""Where does the diffusion x imaging cross term come from? Segment-wise decomposition (read axis)."""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from physics_review_common import *
from physics_review_btensor import union_wave, run

HERE = Path(__file__).resolve().parent


def segments(label, b=6000):
    it, led, it0, led0 = run(label, b, (1000, 0, 0))
    H = led["H"]; lag = float(it.vars["rfdelay"].value)
    fac = H * 1e3 / 32767.0 * 1e-6
    img = union_wave(led0, [(led0, 1.0)])["R"]; dif = union_wave(led, [(led, 1.0), (led0, -1.0)])["R"]
    rfc = [p["t_center"] for p in led["rf"]]
    adc1 = [a for a in led["adc"]][0]
    sp = adc1["sample_period_ticks"] / 10.0; n = it.vars["no_samples"].value
    t_adc1 = adc1["t_init"] + (adc1["discard"] + n / 2) * sp
    edges = np.unique(np.concatenate([img[0] + lag, dif[0] + lag, rfc[:2], [t_adc1]]))
    edges = edges[(edges >= rfc[0]) & (edges <= t_adc1)]
    def val(w, m):
        i = np.searchsorted(w[0], m - lag, side="right") - 1
        return w[1][i] * fac * 1e6 if 0 <= i < len(w[1]) else 0.0
    kd = ki = 0.0; cross = 0.0; rows = []
    sign = 1
    for a, b_ in zip(edges[:-1], edges[1:]):
        m = (a + b_) / 2; dt = (b_ - a) * 1e-6
        gd, gi = val(dif, m), val(img, m)
        # cross: 2 int kd ki dt exact
        c = 2 * (kd * ki * dt + (kd * gi + ki * gd) * dt ** 2 / 2 + gd * gi * dt ** 3 / 3)
        kd0, ki0 = kd, ki
        kd += gd * dt; ki += gi * dt
        cross += c
        # RF conjugation at diffusion 180 centre
        if any(abs(b_ - r) < 1e-6 for r in rfc[1:2]):
            kd, ki = -kd, -ki
        rows.append((a, b_, gd, gi, kd0, ki0, c * (2 * np.pi) ** 2 * 1e-6))
    return rows, (2 * np.pi) ** 2 * 1e-6 * cross


if __name__ == "__main__":
    out = {}
    for label in ("v18", "v181"):
        rows, tot = segments(label)
        print(label, "cross (read-axis, to ADC1) = %.3f s/mm2" % tot)
        big = [r for r in rows if abs(r[6]) > 0.02 * max(1e-9, abs(tot)) or abs(r[3]) > 1]
        for a, b_, gd, gi, kd0, ki0, c in rows:
            if abs(c) > 0.5 or (abs(gi) > 1 and abs(kd0) > 1):
                print("  %9.1f-%9.1f gD=%9.1f gI=%9.1f cyc/m/s  kD0=%8.2f kI0=%8.3f cross=%.3f" % (a, b_, gd, gi, kd0, ki0, c))
        out[label] = {"cross_total": tot, "rows": [list(map(float, r)) for r in rows]}
    (HERE / "physics_review_cross.json").write_text(json.dumps(out))
