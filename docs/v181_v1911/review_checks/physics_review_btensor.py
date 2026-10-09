"""Independent b-tensor / endpoint review for v1.8 vs v1.81 (read-prephaser relocation).

Own implementation: exact analytic integration of piecewise-constant gradients with
coherence-path tracking (k -> -k at each refocusing centre), split into diffusion-lobe
and imaging components to isolate the cross term.  Source-model only.
"""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from physics_review_common import *

HERE = Path(__file__).resolve().parent


def union_wave(led, comps):
    """Return dict axis -> (edges, values) for a linear combination of ledger waveforms.
    comps: list of (led, coeff)."""
    out = {}
    for ax in "SPR":
        edges = np.unique(np.concatenate([np.asarray(l["G"][ax].t, float) for l, _ in comps]))
        vals = np.zeros(len(edges) - 1)
        mid = (edges[:-1] + edges[1:]) / 2
        for l, c in comps:
            W = l["G"][ax]
            vals += c * W.sample(mid)
        out[ax] = (edges, vals)
    return out


def integrate(wave, H, lag, rf_centres, adc_times, rf_t0, comps_mask=None):
    """Primary path from first RF centre. wave: axis->(edges, DAC values) in *emitted* time.
    Returns per-ADC (k, B) with B = (2pi)^2 int k k^T dt in s/mm^2 (SPR logical)."""
    fac = H * 1e3 / 32767.0 * 1e-6          # DAC*us -> cycles/m
    ev = sorted([(t, 1) for t in rf_centres] + [(t, 0) for t in adc_times])
    # global edge list in physical time
    edges = set()
    for ax in "SPR":
        edges.update((wave[ax][0] + lag).tolist())
    edges = np.array(sorted(edges))
    k = np.zeros(3); B = np.zeros((3, 3)); res = []
    tprev = rf_t0
    for tev, kind in ev:
        pts = np.unique(np.concatenate([[tprev, tev], edges[(edges > tprev) & (edges < tev)]]))
        for a, b in zip(pts[:-1], pts[1:]):
            m = (a + b) / 2 - lag
            g = np.array([wave[ax][1][np.searchsorted(wave[ax][0], m, side="right") - 1]
                          if wave[ax][0][0] <= m < wave[ax][0][-1] else 0.0 for ax in "SPR"]) * fac * 1e6  # cycles/m/s
            dt = (b - a) * 1e-6
            # exact: k(s)=k+g s ;  int kk^T = kk^T dt + (k g^T + g k^T) dt^2/2 + g g^T dt^3/3
            B += np.outer(k, k) * dt + (np.outer(k, g) + np.outer(g, k)) * dt ** 2 / 2 + np.outer(g, g) * dt ** 3 / 3
            k = k + g * dt
        tprev = tev
        if kind == 1:
            k = -k
        else:
            res.append((k.copy(), (2 * np.pi) ** 2 * 1e-6 * B.copy()))
    return res


def adc_geometry(it, led):
    out = []
    n = it.vars["no_samples"].value
    for a in led["adc"]:
        sp = a["sample_period_ticks"] / 10.0
        out.append((a["t_init"] + a["discard"] * sp, a["t_init"] + (a["discard"] + n / 2) * sp,
                    a["t_init"] + (a["discard"] + n) * sp, sp))
    return out


def run(label, b, direction=(1000, 0, 0), rows=None):
    ov = {"acq_b": [b, 1000, 6000], "acq_x": [direction[0]] * 3, "acq_y": [direction[1]] * 3, "acq_z": [direction[2]] * 3}
    it = mapped(label, ov, shots=1)
    led = build_ledger(it)
    it0 = mapped(label, dict(ov, acq_b=[0, 1000, 6000]), shots=1)
    led0 = build_ledger(it0)
    return it, led, it0, led0


def analyse(label, b, direction):
    it, led, it0, led0 = run(label, b, direction)
    H = led["H"]; lag = float(it.vars["rfdelay"].value)
    rfc = [p["t_center"] for p in led["rf"][1:]]
    t0 = led["rf"][0]["t_center"]
    geo = adc_geometry(it, led)
    adc_mid = [g[1] for g in geo]
    full = union_wave(led, [(led, 1.0)])
    # imaging component = b=0 run (DAC 1 residual in diffusion lobes is part of "imaging" here; <1e-4 relative)
    img = union_wave(led0, [(led0, 1.0)])
    dif = union_wave(led, [(led, 1.0), (led0, -1.0)])
    kt = integrate(full, H, lag, rfc, adc_mid, t0)
    ki = integrate(img, H, lag, rfc, adc_mid, t0)
    kd = integrate(dif, H, lag, rfc, adc_mid, t0)
    rows = []
    for j in range(len(adc_mid)):
        Bt = kt[j][1]; Bi = ki[j][1]; Bd = kd[j][1]
        cross = Bt - Bi - Bd
        rows.append({"echo": j + 1, "k_total_SPR": kt[j][0].tolist(), "k_img_SPR": ki[j][0].tolist(),
                     "k_diff_SPR": kd[j][0].tolist(),
                     "trace_total": float(np.trace(Bt)), "trace_img": float(np.trace(Bi)),
                     "trace_diffonly": float(np.trace(Bd)), "trace_cross": float(np.trace(cross)),
                     "B_total": Bt.tolist()})
    return {"inputs": {"ppl_sha": it.inputs["ppl_sha256"], "ppr_sha": it.inputs["ppr_sha256"]},
            "adc_geometry_us": geo, "rfc": rfc, "rf0": t0, "echoes": rows, "H": H, "lag": lag,
            "imaging_ADC_sample_period_us": geo[0][3]}


if __name__ == "__main__":
    print(json.dumps(check_hashes(), indent=1))
    out = {"scope": "primary all-transverse conventional path (CPMG-like); instantaneous RF at sample-array midpoint; "
                    "no diffusion during RF; imaging overrides no_disacq=0,nav_on=0,no_views=128; shot 1; "
                    "gradient lag=rfdelay=60us; logical S/P/R", "runs": {}}
    for label in ("v18", "v181"):
        out["runs"][label] = {}
        for b in (0, 100, 1000, 6000):
            r = analyse(label, b, (1000, 0, 0))
            out["runs"][label][b] = r
            e = r["echoes"]
            print(label, b, "E1 trace %.4f (img %.4f diff %.4f cross %.4f)  E8 %.3f" % (
                e[0]["trace_total"], e[0]["trace_img"], e[0]["trace_diffonly"], e[0]["trace_cross"], e[7]["trace_total"]),
                "kR_E1 %.4f" % e[0]["k_total_SPR"][2])
    (HERE / "physics_review_btensor.json").write_text(json.dumps(out, indent=1))
