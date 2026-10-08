"""Independent reviewer check 3: own event-driven Bloch simulator on the mapped ledger.

dwfse.ppl.run.map_events / ledger.build_ledger are used ONLY to obtain the event
ledger (RF sample arrays, gradient breakpoints, ADC records, list starts). Everything
else -- calibration, rotations, gradient integration, latency handling, landmark
times and signal normalisation -- is written here independently. Differences from
the writer's engine (dwfse/ppl/bloch.py):
  * every RF sample is split at gradient breakpoints (writer: midpoint gradient);
  * RF calibration derived from the stock 3-lobe sinc formula (2047*sinc, 666 x 2 us)
    rather than from the decoded library frame;
  * gradient areas from my own cumulative-trapezoid of the piecewise-constant DAC.

Run: python docs/v19/review/physics_checks/check_event_bloch.py [--c1-scan]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from dwfse.ppl.run import map_events  # noqa: E402  (ledger only)
from dwfse.ppl.ledger import build_ledger  # noqa: E402  (ledger only)

OUT = Path(__file__).resolve().parent
SC = ROOT / "scanner"
PPL = {"v191": SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl", "v192": SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.92.ppl"}
W = 1e-3
Z = (np.arange(3000) + 0.5) / 3000 * 5 * W - 2.5 * W
VOXEL_Y = 35e-3 / 136


def stock_cal(rfcal):
    """Hz per (sample*mul/2047) unit so that the stock 3-lobe sinc at rfcal is 90 deg."""
    j = np.arange(666)
    x = (j - 333) * 2 * np.pi / 333
    s = np.round(2047 * np.where(x == 0, 1.0, np.sin(x) / np.where(x == 0, 1, x)))
    integral = s.sum() * rfcal / 2047 * 2e-6
    return 0.25 / integral


class Wave:
    """Piecewise-constant waveform with exact cumulative area (DAC*us)."""

    def __init__(self, t, v, shift=0.0):
        self.t = np.asarray(t, float) + shift
        self.v = np.asarray(v, float)
        self.cum = np.concatenate([[0.0], np.cumsum(self.v * np.diff(self.t))])

    def area_to(self, x):
        x = np.clip(x, self.t[0], self.t[-1])
        i = np.clip(np.searchsorted(self.t, x, side="right") - 1, 0, len(self.v) - 1)
        return self.cum[i] + self.v[i] * (x - self.t[i])

    def area(self, a, b):
        return float(self.area_to(b) - self.area_to(a))

    def value(self, x):
        i = np.searchsorted(self.t, x, side="right") - 1
        return float(self.v[i]) if 0 <= i < len(self.v) else 0.0

    def breaks(self, a, b):
        i0, i1 = np.searchsorted(self.t, [a, b])
        return self.t[i0:i1][(self.t[i0:i1] > a) & (self.t[i0:i1] < b)]


def rodrigues(m, mz, bx, by, bz, dt_us):
    mx, my = m.real, m.imag
    bn = np.sqrt(bx * bx + by * by + bz * bz)
    th = -2 * np.pi * bn * dt_us * 1e-6
    inv = np.where(bn > 0, 1.0 / np.where(bn > 0, bn, 1.0), 0.0)
    nx, ny, nz = bx * inv, by * inv, bz * inv
    c, s = np.cos(th), np.sin(th)
    dot = nx * mx + ny * my + nz * mz
    mx2 = mx * c + (ny * mz - nz * my) * s + nx * dot * (1 - c)
    my2 = my * c + (nz * mx - nx * mz) * s + ny * dot * (1 - c)
    mz2 = mz * c + (nx * my - ny * mx) * s + nz * dot * (1 - c)
    return mx2 + 1j * my2, mz2


def simulate(led, cal, phase0=45.0, latency=60.0, ny=1, snaps=None, adc_times=None, b1=1.0, z=None, yvox=None, t1t2=None):
    k = led["H"] * 1e3 / 32767.0 * 1e-6          # cycles/m per DAC*us ; Hz/m per DAC = k*1e6
    Gs = Wave(led["G"]["S"].t, led["G"]["S"].v, latency)
    Gp = Wave(led["G"]["P"].t, led["G"]["P"].v, latency)
    yv = VOXEL_Y if yvox is None else yvox
    y = (np.arange(ny) + 0.5) / ny * yv - yv / 2 if ny > 1 else np.zeros(1)
    Zg, Yg = np.meshgrid(Z if z is None else z, y)
    m = np.zeros(Zg.shape, complex)
    mz = np.ones(Zg.shape)
    ev = []
    for i, p in enumerate(led["rf"]):
        ph = np.deg2rad(p["phase_deg"] + (phase0 if i == 0 else 0.0))
        for t0, a in zip(p["t"], p["amp"]):
            if a != 0:
                ev.append((float(t0), 1, (float(p["dt"]), float(a) * cal * b1, ph)))
    for n, t in (snaps or {}).items():
        ev.append((t, 0, n))
    for n, t in (adc_times or []):
        ev.append((t, 0, n))
    ev.sort(key=lambda e: (e[0], e[1]))
    tcur = ev[0][0] - 1.0
    out = {}

    def free(t_from, t_to):
        nonlocal m
        if t_to <= t_from:
            return
        As = Gs.area(t_from, t_to) * k
        Ap = Gp.area(t_from, t_to) * k
        m = m * np.exp(-2j * np.pi * (As * Zg + Ap * Yg))
        if t1t2 is not None:
            dts = (t_to - t_from) * 1e-6
            m = m * np.exp(-dts / t1t2[1])
            e1 = np.exp(-dts / t1t2[0])
            mz[...] = mz * e1 + (1 - e1)

    for t, kind, pay in ev:
        if kind == 0:
            free(tcur, t)
            tcur = max(tcur, t)
            out[pay] = (m.copy(), mz.copy())
            continue
        dt, b1hz, ph = pay
        free(tcur, t)
        cuts = np.concatenate([[t], np.unique(np.concatenate([Gs.breaks(t, t + dt), Gp.breaks(t, t + dt)])), [t + dt]])
        for a, b in zip(cuts[:-1], cuts[1:]):
            gs = Gs.value(0.5 * (a + b)) * k * 1e6      # Hz/m
            gp = Gp.value(0.5 * (a + b)) * k * 1e6
            m, mz = rodrigues(m, mz, b1hz * np.cos(ph), b1hz * np.sin(ph), gs * Zg + gp * Yg, b - a)
        tcur = t + dt
    return out


def adc_mid(led, n=128):
    return [(f"ADC{i+1}", a["t_init"] + (a["discard"] + n / 2) * a["sample_period_ticks"] / 10) for i, a in enumerate(led["adc"])]


def landmarks(it, led):
    S = led["G"]["S"]
    starts = {}
    for t, ax, addr in it.grad.starts:
        if led["t_start"] <= t < led["t_end"]:
            starts.setdefault((ax, addr), []).append(t)

    def end_of(t0, W_):
        # commanded end of a list: first zero-output breakpoint after the lobe(s)
        i = np.searchsorted(W_.t, t0 + 1.0)
        seen = False
        for j in range(i, len(W_.v)):
            if W_.v[j] != 0:
                seen = True
            elif seen and (j + 1 >= len(W_.v) or W_.t[j + 1] - W_.t[j] > 30):
                return float(W_.t[j])
        return None

    lm = {}
    v = it.vars
    tD = starts[("S", v["v19_l_d"].value)][0]
    lm["A_before_dephasing"] = tD
    lm["B_after_dephasing"] = end_of(tD, S)
    tm = starts[("S", v["v19_l_m"].value)][0]
    if "v19_l_sp" in v:
        lm["after_tipup"] = end_of(tm, S)
        tsp = starts[("P", v["v19_l_sp"].value)][0]
        lm["after_spoiler"] = end_of(tsp, led["G"]["P"])
        tre = starts[("S", v["v19_l_re"].value)][0]
        lm["after_reexcitation_comp"] = end_of(tre, S)
    else:
        lm["after_elimination"] = end_of(tm, S)
    lm["endpoint_before_leading_crusher"] = starts[("S", v["v19_l_im"].value)][0]
    lm["pre_RF1_after_crusher"] = next(p["t_go"] for p in led["rf"] if p["frame"] == "v19_imaging180")
    return lm


def summarise(state, inside):
    m, mz = state
    mean = m.mean(axis=0)
    loc = m[m.shape[0] // 2]
    c = mean[inside].mean()
    return {"slice_coherent_mean_mx": float(c.real), "slice_coherent_mean_my": float(c.imag),
            "slice_coherent_mean_mxy_abs": float(abs(c)), "slice_mean_local_abs_mxy": float(np.abs(loc[inside]).mean()),
            "slice_mean_mz": float(mz[mz.shape[0] // 2][inside].mean())}


def get_led(label, overrides=None):
    ppl = PPL[label]
    it = map_events(ppl, ppl.with_suffix(".ppr"), overrides=overrides or {}, max_shots=1,
                    stmt_cost_us=0.0, expr_costs=True, expr_scale=0.8)
    return it, build_ledger(it, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--c1-scan", action="store_true")
    args = ap.parse_args()
    res = {"inputs": {}}
    dz = (Z[1] - Z[0]) / W
    inside = np.abs(Z) < W / 2
    for label in (() if args.c1_scan else ("v192", "v191")):
        it, led = get_led(label)
        res["inputs"][label] = {"ppl_sha256": it.inputs["ppl_sha256"], "ppr_sha256": it.inputs["ppr_sha256"]}
        cal = stock_cal(it.vars["rfcal"].value)
        rfc = [p["t_center"] for p in led["rf"]]
        # timing facts
        flips = [round(float(np.sum(p["amp"]) * p["dt"] * 1e-6 * cal * 360), 2) for p in led["rf"]]
        adc = adc_mid(led)
        im = [p["t_center"] for p in led["rf"] if p["frame"] == "v19_imaging180"]
        t0 = [p["t_center"] for p in led["rf"] if p["frame"] in ("v19_slrelim90", "v19_reexc90")][0]
        # spin-echo times of the CPMG train: e_1 = 2*RF1 - T0, e_n = 2*RF_n - e_{n-1}
        e = []
        prev = t0
        for r in im:
            prev = 2 * r - prev
            e.append(prev)
        res[label] = {"cal_hz_per_unit": cal, "nominal_flips_deg": flips,
                      "rf_centres_rel_us": [round(x - rfc[0], 3) for x in rfc],
                      "imaging_rf_spacing_us": np.round(np.diff(im), 3).tolist(),
                      "adc_mid_minus_spin_echo_us": [round(a[1] - ee, 3) for a, ee in zip(adc, e)],
                      "prep_echo_minus_method_rf_us": round(2 * rfc[1] - rfc[0] - t0, 3)}
        ny = 32 if label == "v191" else 1
        lm = landmarks(it, led)
        res[label]["landmark_times_rel_us"] = {n: round(t - rfc[0], 2) for n, t in lm.items()}
        for ph in (0.0, 45.0, 90.0):
            out = simulate(led, cal, ph, 60.0, ny, lm if ph == 45.0 else None, adc)
            S = [complex(out[n][0].mean(axis=0).sum() * dz) for n, _ in adc]
            res[label][f"phase{ph:g}"] = {"abs": [abs(s) for s in S], "angle_deg": [float(np.angle(s, deg=True)) for s in S]}
            if ph == 45.0:
                res[label]["landmarks_phase45"] = {n: summarise(out[n], inside) for n in list(lm) + ["ADC1", "ADC2", f"ADC{len(adc)}"]}
        if label == "v191":
            out = simulate(led, cal, 45.0, 60.0, 64, None, adc)
            res[label]["phase45_y64_abs"] = [abs(out[n][0].mean(axis=0).sum() * dz) for n, _ in adc]
        out = simulate(led, cal, 45.0, 0.0, ny, None, adc)
        res[label]["phase45_latency0_abs"] = [abs(out[n][0].mean(axis=0).sum() * dz) for n, _ in adc]
        print(label, json.dumps({k_: v for k_, v in res[label].items() if not k_.startswith("landmarks")}, indent=0)[:3000])
    if args.c1_scan:
        scan = {}
        for dac in list(range(-1000, -12001, -500)):
            row = {}
            for label in ("v192",):
                try:
                    it, led = get_led(label, {"diff_crush_amp": dac})
                except Exception as exc:  # noqa: BLE001
                    row[label] = str(exc)
                    continue
                if len(led["rf"]) < 4:
                    row[label] = {"rejected": [o[1].strip() for o in it.out[-1:]]}
                    continue
                cal = stock_cal(it.vars["rfcal"].value)
                adc = adc_mid(led)
                sp = []
                for ph in (0.0, 45.0, 90.0):
                    out = simulate(led, cal, ph, 60.0, 1, None, adc)
                    sp.append([abs(out[n][0].mean(axis=0).sum() * dz) for n, _ in adc])
                sp = np.array(sp)
                row[label] = {"C1_dac": int(it.vars["crusher_saved_first"].value), "abs_by_phase": sp.round(4).tolist(),
                              "max_phase_spread": float((sp.max(0) - sp.min(0)).max())}
            scan[str(dac)] = row
            print(dac, row)
        res["c1_scan_v192"] = scan
    name = "event_bloch_results.json" if not args.c1_scan else "event_bloch_c1scan.json"
    (OUT / name).write_text(json.dumps(res, indent=1, default=float) + "\n")


if __name__ == "__main__":
    main()
