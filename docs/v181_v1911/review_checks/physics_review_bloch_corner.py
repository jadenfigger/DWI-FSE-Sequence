"""Targeted diagnostic of the worst v7->v1.911 finite-RF Bloch corner (B1 1.1, B0 -128 Hz, phase 90): is the loss a
pure off-resonance-phase-per-ESP (CPMG twist) effect of the 1-ms shorter spacing?  Uses the repo EventBloch
(same engine as the author's grid; this is a *diagnostic*, not a replacement for the full grid)."""
import sys, json, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from physics_review_common import *
from dwfse.ppl.bloch import EventBloch, Grid, SimConfig, rf_calibration_hz_per_unit
from dwfse.vendor_seq import decode
HERE = Path(__file__).resolve().parent
SLICE_W, FOV = 1e-3, 35e-3
NZ, NY = 3000, 32


def run(label, b1, df, ph, relax=None):
    it = mapped(label, shots=2, rf_latency_us=3.0); led = build_ledger(it)
    stock = decode(SC / "utilities/rfstd44.seq").frame("3lobe_sinc_3kHz")
    cal = rf_calibration_hz_per_unit(stock.samples, stock.wait_ticks / 10, it.vars["rfcal"].value)
    z = (np.arange(NZ) + .5) / NZ * 5 * SLICE_W - 2.5 * SLICE_W
    vy = FOV / float(it.vars["no_views"].value); y = (np.arange(NY) + .5) / NY * vy - vy / 2
    grid = Grid(z, y)
    cfg = SimConfig(b1_scale=b1, df_hz=df, grad_latency_us=float(it.vars["rfdelay"].value), extra_phase_deg={0: ph},
                    t1_s=relax[0] if relax else None, t2_s=relax[1] if relax else None)
    sim = EventBloch(led, grid, cal, cfg)
    adc = adc_middle_times(it, led)
    _, ad = sim.run(led["rf"], {}, adc)
    dz = (z[1] - z[0]) / SLICE_W
    s = np.array([complex(ad[n][0].mean(axis=0).sum() * dz) for n, _ in adc])
    return np.abs(s), np.rad2deg(np.angle(s))


if __name__ == "__main__":
    esp7, esp9 = 13996.94, 12997.38
    res = {"hashes": check_hashes(), "cases": []}
    for (b1, df, ph) in ((1.1, -128.0, 90.0),):
        t = time.time()
        a7, p7 = run("v7", b1, df, ph); print("v7", np.round(a7, 4), round(time.time() - t), "s", flush=True)
        a9, p9 = run("v1911", b1, df, ph); print("v1911 same df", np.round(a9, 4), "ratio", np.round(a9 / a7, 4), flush=True)
        dfm = df * esp7 / esp9
        a9m, p9m = run("v1911", b1, dfm, ph); print("v1911 df scaled to equal phase/ESP (%.1f Hz)" % dfm, np.round(a9m, 4), "ratio", np.round(a9m / a7, 4), flush=True)
        a7r, _ = run("v7", b1, df, ph, (1.3, 0.032)); a9r, _ = run("v1911", b1, df, ph, (1.3, 0.032))
        print("with T1 1.3 / T2 32 ms: ratio v1911/v7", np.round(a9r / a7r, 4), flush=True)
        res["cases"].append({"B1": b1, "df": df, "ph": ph, "v7": a7.tolist(), "v1911": a9.tolist(), "ratio": (a9 / a7).tolist(), "df_matched": dfm,
                             "v1911_matched": a9m.tolist(), "ratio_matched": (a9m / a7).tolist(), "v7_relaxed": a7r.tolist(), "v1911_relaxed": a9r.tolist(),
                             "ratio_relaxed": (a9r / a7r).tolist()})
    (HERE / "physics_review_bloch_corner.json").write_text(json.dumps(res, indent=1))
