#!/usr/bin/env python
"""Off-centre (multi-slice) RF phase calibration for the v1.83 refocusing pulses.

For each MRD and each slice of one volume, the navigator echo train (first views_per_seg raw views,
nav_on=1) gives the inner-product echo phase relative to echo 1. That phase is fitted as

    phi_e = a + s*(e-1) + h*(-1)^e,   e = 1..ETL

s is the echo-phase ramp (deg/echo) and h the odd/even alternation (deg). Per off-centre slice the tool
reports z, f = z * hz_per_mm, s, h, fit rms, tau = s/(360 f) and PASS/FAIL (|s| <= 5 and |h| <= 5 deg).

Ambiguities, both real:
* (s, h) and (s +/- 180, h +/- 90) give identical echo phases (180*e = 90 - 90*(-1)^e mod 360), so the
  ramp is only identifiable mod 180 once h is free. The tool reports the representation with the smaller
  |h| (the expected state of a healthy scan) and lists the alias.
* The ramp is known mod 360 per echo, so tau is known only mod 1/f.

Mode 1 (v183_phmode=1, v183_phcal=P): s(P) = s0 + sigma*k*P with k = 360*f*1e-7 deg/echo per 0.1-us tick
and sigma = +/-1 unknown. Scans with two or more distinct P fix sigma (the sign with the smaller residual)
and the P0 where the ramp is zero; the recommended v183_phcal is the median over slices of P0, rounded
to 10 ticks. A single P gives both candidate corrections, P -/+ s/k, for a second scan to decide.
Mode 0 (vendor scheme): ramp and alternation are reported only.

Usage:
  python tools/offcentre_phase_cal.py SCAN.MRD [SCAN2.MRD ...] [--volume N] [--out report.json] [--plot fig.png]
  python tools/offcentre_phase_cal.py --selftest
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scanner/recon"))
from get_mrd_3d4 import get_mrd_3d4  # noqa: E402

# Reuse the recon helpers (read_slice_offsets, read_thickness, ppr_array) without importing the whole
# recon module, which pulls in plotting and NIfTI code. Same pattern as docs/data/oct11_load.py.
_SRC = ROOT / "scanner/recon/bare_bones_recon_fse.py"
_NS = {"np": np, "re": re}
_TREE = ast.parse(_SRC.read_text(encoding="utf-8"))
exec(compile(ast.Module(body=[n for n in _TREE.body if isinstance(n, ast.FunctionDef)
                              and n.name in ("read_slice_offsets", "read_thickness", "ppr_array")],
                        type_ignores=[]), str(_SRC), "exec"), _NS)
read_slice_offsets = _NS["read_slice_offsets"]
read_thickness = _NS["read_thickness"]
ppr_array = _NS["ppr_array"]

FALLBACK_RF_BW = {1: 3000, 2: 1500, 3: 750, 4: 3000, 5: 1500, 6: 750, 7: 6000, 8: 4000}
PASS_LIMIT_DEG = 5.0


def rf_bandwidths():
    """rfnum -> bandwidth (Hz) from the NEWSHAPE_MAC lines of the v1.82 PPL in the repo."""
    bw = {}
    ppl = ROOT / "scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.82.ppl"
    if ppl.exists():
        pat = r'NEWSHAPE_MAC\(\s*(\d+)\s*,\s*pf\d+\s*,\s*"[^"]*"\s*,\s*\d+\s*,\s*(\d+)\s*\)'
        for m in re.finditer(pat, ppl.read_text(encoding="latin-1")):
            bw[int(m.group(1))] = int(m.group(2))
    return bw or FALLBACK_RF_BW


RF_BW = rf_bandwidths()


def wrap180(x):
    return (np.asarray(x, dtype=float) + 180.0) % 360.0 - 180.0


def wrap90(x):
    """Wrap into [-90, 90): the residual modulo 180 used by the calibration solver."""
    return (np.asarray(x, dtype=float) + 90.0) % 180.0 - 90.0


def _var(text, name, default=None):
    m = re.search(rf"^:[A-Z_]+\s+{re.escape(name)},\s*(-?[\d.]+)", text, re.M)
    return float(m.group(1)) if m else default


# ----------------------------------------------------------------------------- reading
def read_scan(path, volume=None, hz_per_mm=None):
    path = Path(path)
    blob = path.read_bytes()
    text = blob[blob.find(b":PPL"):].decode("latin1")
    raw, dims, params = get_mrd_3d4(path)
    n_vol, n_slice, nsamp = int(dims[0]), int(dims[2]), int(dims[5])
    if int(_var(text, "nav_on", 0)) != 1:
        raise ValueError(f"{path.name}: nav_on is not 1, there is no navigator train")
    L = int(_var(text, "views_per_seg", params.get("views_per_seg", 8)))
    navs = raw[:, 0, :, 0]                       # (volumes, slices, views, samples), echo 0, view_2 0

    n_b = int(_var(text, "no_diff_acq", n_vol))
    b = ppr_array(text, "acq_b")[:n_b]
    if volume is None:
        cand = [i for i, bb in enumerate(b) if bb <= 20]
        volume = cand[0] if cand else 0
    if not 0 <= volume < n_vol:
        raise ValueError(f"{path.name}: volume {volume} out of range 0..{n_vol - 1}")

    offsets = np.asarray(read_slice_offsets(text), dtype=float)
    if len(offsets) != n_slice:
        raise ValueError(f"{path.name}: {len(offsets)} slice offsets for {n_slice} slices")
    thk = read_thickness(text)
    rfnum = int(_var(text, "rfnum", 1))
    bw = RF_BW.get(rfnum, 3000)
    hz = hz_per_mm if hz_per_mm is not None else 0.71 * bw / thk

    ppl = re.search(r"^:PPL\s+(.*)$", text, re.M).group(1).strip()
    phmode = _var(text, "v183_phmode")
    if phmode is None:
        phmode = 1 if ppl.endswith("1.82.ppl") else 0
    phcal = int(_var(text, "v183_phcal", 0))

    ip = np.zeros((n_slice, L))
    for sl in range(n_slice):
        nav = navs[volume, sl, :L, :]
        ip[sl] = np.angle(np.sum(nav * np.conj(nav[0:1]), axis=-1))   # inner-product phase vs echo 1

    return dict(label=path.stem, path=str(path), ppl=ppl, phmode=int(phmode), phcal=phcal, L=L,
                volume=int(volume), b=float(b[volume]) if volume < len(b) else None, nsamp=nsamp,
                offsets_mm=offsets, thickness_mm=thk, rfnum=rfnum, rf_bw_hz=bw, hz_per_mm=float(hz),
                ip=ip)


# ----------------------------------------------------------------------------- fitting
def canonical(s, h, rms):
    """Pick the (s, h) representation with the smaller |h| among (s, h) and (s +/- 180, h +/- 90)."""
    s, h = float(wrap180(s)), float(wrap90(h))
    alt_s, alt_h = float(wrap180(s + 180.0)), float(wrap90(h + 90.0))
    alias = (alt_s, alt_h)
    if abs(alt_h) < abs(h) - 1e-9 or (abs(alt_h) == abs(h) and abs(alt_s) < abs(s)):
        s, h, alias = alt_s, alt_h, (float(wrap180(alt_s + 180.0)), float(wrap90(alt_h + 90.0)))
    return dict(s=s, h=h, rms=float(rms), alias_s=alias[0], alias_h=alias[1])


def fit_ramp(phase_rad):
    """phase_rad: (ETL,) inner-product echo phases vs echo 1 in radians, phase_rad[0] == 0.
    Grid search over h in [-90, 90] deg, np.unwrap of the residual, least squares for a and s."""
    n = len(phase_rad)
    e = np.arange(1, n + 1, dtype=float)
    A = np.stack([np.ones(n), e - 1.0], axis=1)
    best = None
    for hdeg in np.arange(-90.0, 90.0 + 1e-9, 0.1):
        u = np.unwrap(phase_rad - np.radians(hdeg) * (-1.0) ** e)
        p, *_ = np.linalg.lstsq(A, u, rcond=None)
        r = float(np.sqrt(np.mean((u - A @ p) ** 2)))
        if best is None or r < best[0]:
            best = (r, hdeg, float(np.degrees(p[1])))
    r, h, s = best
    return canonical(s, h, np.degrees(r))


def tau_us(s, f):
    return float(s / (360.0 * f) * 1e6) if f else float("nan")


def analyse_scan(scan):
    """Per-slice fits. The ramp is odd in slice frequency, so for each +z/-z pair the mod-180 alias is
    chosen jointly: the combination with s(+z) + s(-z) closest to 0 (mod 360), ties broken by the smaller
    sum of |h|. Unpaired slices and the centre keep the smaller-|h| representation."""
    z_list = [float(z) for z in scan["offsets_mm"]]
    fits = [fit_ramp(scan["ip"][sl]) for sl in range(len(z_list))]
    reps = [[(f["s"], f["h"]), (f["alias_s"], f["alias_h"])] for f in fits]
    choice = [0] * len(z_list)
    pair_err = {}
    done = set()
    for i, zi in enumerate(z_list):
        if abs(zi) < 0.05 or i in done:
            continue
        js = [j for j, zj in enumerate(z_list) if j != i and abs(zj + zi) < 0.05]
        if not js:
            continue
        j = js[0]
        done |= {i, j}
        combos = []
        for ci in (0, 1):
            for cj in (0, 1):
                (si, hi), (sj, hj) = reps[i][ci], reps[j][cj]
                combos.append((abs(float(wrap180(si + sj))), abs(hi) + abs(hj), ci, cj))
        best = min(c[0] for c in combos)
        err, _, ci, cj = min([c for c in combos if c[0] <= best + 1.0], key=lambda c: c[1])
        choice[i], choice[j] = ci, cj
        pair_err[i] = pair_err[j] = float(err)
    out = []
    for sl, z in enumerate(z_list):
        f = float(z * scan["hz_per_mm"])
        s, h = reps[sl][choice[sl]]
        alias_s, alias_h = reps[sl][1 - choice[sl]]
        centre = abs(z) < 0.05
        verdict = "reference" if centre else ("PASS" if abs(s) <= PASS_LIMIT_DEG and abs(h) <= PASS_LIMIT_DEG else "FAIL")
        out.append(dict(slice=sl, z_mm=z, z_key=round(z, 3), f_hz=f, s=float(s), h=float(h), rms_deg=fits[sl]["rms"],
                        alias_s=float(alias_s), alias_h=float(alias_h), tau_us=tau_us(s, f),
                        tau_alias_us=[tau_us(wrap180(s + 180.0), f), tau_us(wrap180(s - 180.0), f)],
                        period_tau_us=(1e6 / abs(f)) if f else float("nan"),
                        pair_antisymmetry_err_deg=pair_err.get(sl), centre=centre, verdict=verdict,
                        ip_deg=[round(float(np.degrees(x)), 3) for x in scan["ip"][sl]]))
    scan = dict(scan)
    scan["slices"] = out
    scan.pop("ip")
    return scan


def print_scan(sc):
    mode = {0: "mode 0 (vendor)", 1: f"mode 1 phcal {sc['phcal']}"}.get(sc["phmode"], f"mode {sc['phmode']}")
    print(f"\n== {sc['label']}  {mode}  ETL {sc['L']}  volume {sc['volume']} (b={sc['b']:g})  "
          f"{sc['hz_per_mm']:.0f} Hz/mm (rfnum {sc['rfnum']}, {sc['rf_bw_hz']} Hz / {sc['thickness_mm']:g} mm)")
    print(f"   {'z(mm)':>6} {'f(Hz)':>8} {'s(deg/e)':>9} {'h(deg)':>7} {'rms':>5} {'tau(us)':>8} "
          f"{'alt s+-180':>22} {'verdict':>9}")
    for sl in sc["slices"]:
        alt = f"{sl['alias_s']:+.1f} / {sl['alias_h']:+.1f}"
        print(f"   {sl['z_mm']:+6.2f} {sl['f_hz']:+8.0f} {sl['s']:+9.1f} {sl['h']:+7.1f} {sl['rms_deg']:5.1f} "
              f"{sl['tau_us']:+8.1f} {alt:>22} {sl['verdict']:>9}")
    if sc["phmode"] == 0:
        off = [sl for sl in sc["slices"] if not sl["centre"]]
        if any(abs(sl["s"]) > PASS_LIMIT_DEG for sl in off):
            print("   note: mode 0 shows an off-centre ramp (|s| > 5 deg/echo); mode 0 needs a different correction.")
        elif any(abs(sl["h"]) > PASS_LIMIT_DEG for sl in off):
            print("   note: mode 0 ramp is ~0 but the off-centre alternation exceeds 5 deg (not a phase-ramp error).")


# ----------------------------------------------------------------------------- calibration
def solve_joint(points):
    """points: {z_key: (f_hz, P array, s array)} with s the canonical ramp per scan. Returns the sign sigma,
    s0 per slice (s = s0 + sigma*k*P, k = 360 f 1e-7), the joint P, and P0 per slice."""
    s0grid = np.arange(-90.0, 90.0, 0.05)
    Pgrid = np.arange(-2000.0, 2001.0)
    fits = {}
    for sigma in (1, -1):
        tot, s0 = 0.0, {}
        for z, (f, P, s) in points.items():
            k = 360.0 * f * 1e-7
            cost = np.sum(wrap90(s[None, :] - s0grid[:, None] - sigma * k * P[None, :]) ** 2, axis=1)
            j = int(np.argmin(cost))
            s0[z] = float(s0grid[j])
            tot += float(cost[j])
        fits[sigma] = (tot, s0)
    sigma = min(fits, key=lambda g: fits[g][0])
    sse, s0 = fits[sigma]
    tot_grid = np.zeros_like(Pgrid)
    for z, (f, P, s) in points.items():
        k = 360.0 * f * 1e-7
        tot_grid += wrap90(s0[z] + sigma * k * Pgrid) ** 2
    # The ramp is zero every 180/|k| ticks (about 1956 for 1.2 mm, 978 for 2.4 mm), so several P are
    # consistent with the data. Accept every P whose rms residual is within 1 deg of the best, and take
    # the one nearest zero (the scanner's expected range); the other zeros are listed per slice.
    rms_grid = np.sqrt(tot_grid / max(1, sum(len(P) for _, P, _ in points.values())))
    accepted = np.flatnonzero(rms_grid <= rms_grid.min() + 1.0)
    Pj = float(Pgrid[accepted[np.argmin(np.abs(Pgrid[accepted]))]])
    P0, others = {}, {}
    for z, (f, P, s) in points.items():
        k = 360.0 * f * 1e-7
        base = -s0[z] / (sigma * k)
        period = 180.0 / abs(k)
        P0[z] = float(base + np.round((Pj - base) / period) * period)
        zeros = [P0[z] + n * period for n in range(-3, 4)]
        others[z] = [round(float(q)) for q in zeros if abs(q) <= 2000 and abs(q - P0[z]) > 1.0]
    return dict(sigma=sigma, sse_sign=sse, sse_other=fits[-sigma][0], s0=s0, P_joint=Pj, P0=P0, others=others)


def calibrate(scans):
    m1 = [sc for sc in scans if sc["phmode"] == 1]
    if not m1:
        return {"note": "no mode-1 scans; no v183_phcal recommendation (mode 0 is the vendor scheme)"}
    pts = {}
    for sc in m1:
        for sl in sc["slices"]:
            if sl["centre"]:
                continue
            d = pts.setdefault(sl["z_key"], dict(f=sl["f_hz"], P=[], s=[]))
            d["P"].append(float(sc["phcal"]))
            d["s"].append(sl["s"])
    Pset = sorted({sc["phcal"] for sc in m1})
    if len(Pset) == 1:
        P_cur = Pset[0]
        per = {}
        for z, d in sorted(pts.items()):
            k = 360.0 * d["f"] * 1e-7
            s = d["s"][0]
            per[z] = dict(f_hz=d["f"], s=s, minus=P_cur - s / k, plus=P_cur + s / k,
                          alias_minus=P_cur - (s + 180.0) / k, alias_plus=P_cur + (s - 180.0) / k)
        med_minus = float(np.median([v["minus"] for v in per.values()]))
        med_plus = float(np.median([v["plus"] for v in per.values()]))
        return dict(mode="single", P_current=P_cur, per_slice=per,
                    candidate_minus_median=int(round(med_minus / 10) * 10),
                    candidate_plus_median=int(round(med_plus / 10) * 10),
                    note="one phcal value only: a second scan at one of the two candidates decides the sign")
    points = {z: (d["f"], np.array(d["P"]), np.array(d["s"])) for z, d in pts.items()}
    j = solve_joint(points)
    P0s = np.array(list(j["P0"].values()))
    per = {}
    for z, (f, P, s) in points.items():
        k = 360.0 * f * 1e-7
        resid = float(wrap90(j["s0"][z] + j["sigma"] * k * j["P0"][z]))
        per[z] = dict(f_hz=f, P0=j["P0"][z], residual_deg_at_P0=resid, s0=j["s0"][z], other_zeros_in_range=j["others"][z])
    rec = int(round(float(np.median(P0s)) / 10) * 10)
    return dict(mode="joint", P_values=Pset, sign_sigma=j["sigma"], sse_chosen_sign=j["sse_sign"],
                sse_other_sign=j["sse_other"], P_joint=j["P_joint"], per_slice=per,
                recommended_phcal=rec, spread_ticks=float(P0s.max() - P0s.min()),
                note=("sign undetermined (residuals nearly equal)" if j["sse_other"] < 2 * j["sse_sign"] + 1e-6 else
                      "sign set by residual"))


def print_calibration(cal):
    print("\n== v183_phcal calibration")
    if "note" in cal and "mode" not in cal:
        print("  " + cal["note"])
        return
    if cal["mode"] == "single":
        print(f"  one phcal value only (P={cal['P_current']}): both candidates per off-centre slice")
        print(f"   {'z(mm)':>7} {'s':>7} {'P - s/k':>10} {'P + s/k':>10}")
        for z, v in cal["per_slice"].items():
            print(f"   {z:+7.2f} {v['s']:+7.1f} {v['minus']:+10.0f} {v['plus']:+10.0f}")
        print(f"  median candidate: P - s/k = {cal['candidate_minus_median']},  P + s/k = {cal['candidate_plus_median']}")
        print("  " + cal["note"])
        return
    print(f"  phcal values scanned: {cal['P_values']}; sign sigma = {cal['sign_sigma']:+d} "
          f"(residual SSE {cal['sse_chosen_sign']:.2f} vs {cal['sse_other_sign']:.2f} other sign; {cal['note']})")
    print(f"   {'z(mm)':>7} {'P0':>9} {'residual':>9}  other zeros in +/-2000 (aliases, period 180/k)")
    for z, v in cal["per_slice"].items():
        print(f"   {z:+7.2f} {v['P0']:+9.0f} {v['residual_deg_at_P0']:+9.2f}  {v['other_zeros_in_range']}")
    print(f"  RECOMMENDED v183_phcal = {cal['recommended_phcal']} (median over {len(cal['per_slice'])} "
          f"off-centre slices; spread {cal['spread_ticks']:.0f} ticks)")


# ----------------------------------------------------------------------------- plotting
def plot_report(scans, cal, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.8))
    for sc in scans:
        for sl in sc["slices"]:
            e = np.arange(1, len(sl["ip_deg"]) + 1)
            ax1.plot(e, sl["ip_deg"], "o-", ms=3, lw=1, label=f"{sc['label']} z={sl['z_mm']:+.1f}")
    ax1.set_xlabel("echo")
    ax1.set_ylabel("inner-product phase vs echo 1 (deg)")
    ax1.legend(fontsize=6)
    ax1.set_title("navigator echo phase")
    for sc in scans:
        zs = [sl["z_mm"] for sl in sc["slices"] if not sl["centre"]]
        ss = [sl["s"] for sl in sc["slices"] if not sl["centre"]]
        ax2.plot(zs, ss, "o", label=f"{sc['label']} (phcal {sc['phcal']})")
    ax2.axhline(0, color="k", lw=0.5)
    ax2.axhspan(-PASS_LIMIT_DEG, PASS_LIMIT_DEG, color="g", alpha=0.1)
    ax2.set_xlabel("slice z (mm)")
    ax2.set_ylabel("ramp s (deg/echo, canonical)")
    ax2.set_title("ramp vs slice position")
    ax2.legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


# ----------------------------------------------------------------------------- self test
def synthetic_ip(s_by_z, h, L=8, nsamp=128, noise=0.3, rng=None):
    rng = rng or np.random.default_rng(0)
    e = np.arange(1, L + 1, dtype=float)
    base = np.exp(1j * rng.uniform(0, 2 * np.pi, nsamp))
    ip = {}
    for z, s in s_by_z.items():
        phase = np.radians(s * (e - 1.0) + h * (-1.0) ** e)
        nav = base[None, :] * np.exp(1j * phase)[:, None]
        nav = nav + noise * (rng.standard_normal((L, nsamp)) + 1j * rng.standard_normal((L, nsamp))) / np.sqrt(2)
        ip[z] = np.angle(np.sum(nav * np.conj(nav[0:1]), axis=-1))
    return ip


def selftest():
    rng = np.random.default_rng(1)
    P0_true, sigma_true, h_true, hz = 520.0, -1, 3.0, 2130.0
    zs = [-2.4, -1.2, 1.2, 2.4]
    ok = True
    # fit recovers ramp and alternation on synthetic trains (noise 0.3 per sample)
    fit_err = 0.0
    for P in (-530.0, 0.0, 530.0):
        s_by = {z: sigma_true * 360.0 * z * hz * 1e-7 * (P - P0_true) for z in zs}
        ip = synthetic_ip(s_by, h_true, rng=rng)
        for z in zs:
            fit = fit_ramp(ip[z])
            err_s = abs(float(wrap180(fit["s"] - wrap180(s_by[z]))))
            err_h = abs(fit["h"] - h_true)
            fit_err = max(fit_err, err_s, err_h)
    fit_ok = fit_err < 1.0
    ok &= fit_ok
    print(f"selftest fit: max |error| in s,h = {fit_err:.2f} deg (limit 1.0) -> {'PASS' if fit_ok else 'FAIL'}")

    def run(Plist):
        pts = {}
        for P in Plist:
            s_by = {z: sigma_true * 360.0 * z * hz * 1e-7 * (P - P0_true) for z in zs}
            ip = synthetic_ip(s_by, h_true, rng=rng)
            for z in zs:
                fit = fit_ramp(ip[z])
                d = pts.setdefault(z, dict(f=z * hz, P=[], s=[]))
                d["P"].append(P)
                d["s"].append(fit["s"])
        points = {z: (d["f"], np.array(d["P"]), np.array(d["s"])) for z, d in pts.items()}
        return solve_joint(points)

    for label, Plist in (("3 scans P=-530,0,+530", (-530.0, 0.0, 530.0)), ("2 scans P=0,+530", (0.0, 530.0))):
        j = run(Plist)
        P0s = np.array(list(j["P0"].values()))
        rec = float(np.median(P0s))
        good = abs(rec - P0_true) <= 20 and j["sigma"] == sigma_true
        ok &= good
        print(f"selftest solver ({label}): sign {j['sigma']:+d} (true {sigma_true:+d}), "
              f"recovered P0 {rec:.0f} (true {P0_true:.0f}, error {rec - P0_true:+.0f} ticks) -> {'PASS' if good else 'FAIL'}")

    # single-scan candidates: P -/+ s/k must contain the true P0 within 20 ticks
    P_cur = 0.0
    s_by = {z: sigma_true * 360.0 * z * hz * 1e-7 * (P_cur - P0_true) for z in zs}
    ip = synthetic_ip(s_by, h_true, rng=rng)
    ok_single = True
    for z in zs:
        fit = fit_ramp(ip[z])
        k = 360.0 * z * hz * 1e-7
        cands = (P_cur - fit["s"] / k, P_cur + fit["s"] / k)
        ok_single &= min(abs(c - P0_true) for c in cands) <= 20
    ok &= ok_single
    print(f"selftest single scan: a candidate of P -/+ s/k within 20 ticks of {P0_true:.0f} for all slices -> "
          f"{'PASS' if ok_single else 'FAIL'}")
    print("selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


# ----------------------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description="Off-centre RF phase calibration from navigator echo trains.")
    ap.add_argument("mrd", nargs="*", type=Path, help="MRD files")
    ap.add_argument("--volume", type=int, default=None, help="volume index (default: first with b <= 20)")
    ap.add_argument("--out", type=Path, default=None, help="write the report as JSON")
    ap.add_argument("--plot", type=Path, default=None, help="write a PNG figure")
    ap.add_argument("--hz-per-mm", type=float, default=None, help="override the slice frequency per mm")
    ap.add_argument("--selftest", action="store_true", help="run the synthetic self test and exit")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.mrd:
        ap.error("give at least one MRD, or --selftest")
    scans = [analyse_scan(read_scan(p, args.volume, args.hz_per_mm)) for p in args.mrd]
    for sc in scans:
        print_scan(sc)
    cal = calibrate(scans)
    print_calibration(cal)
    if args.out:
        def clean(o):
            if isinstance(o, dict):
                return {str(k): clean(v) for k, v in o.items()}
            if isinstance(o, (list, tuple)):
                return [clean(v) for v in o]
            if isinstance(o, np.ndarray):
                return o.tolist()
            if isinstance(o, (np.floating, np.integer)):
                return o.item()
            return o
        args.out.write_text(json.dumps(clean(dict(scans=scans, calibration=cal)), indent=2))
        print(f"\nwrote {args.out}")
    if args.plot:
        plot_report(scans, cal, args.plot)
        print(f"wrote {args.plot}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
