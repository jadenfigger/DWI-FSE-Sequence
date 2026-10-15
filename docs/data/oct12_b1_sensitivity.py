#!/usr/bin/env python
"""Transmit-field (kappa) and B0 sensitivity of ss-MGOT (v1.912) vs conventional DW-FSE (v1.83), 2026-10-12.

Question: in vivo, surface T/R coil, 9.4 T: ss-MGOT b10 / v1.83 b10 is ~0.5 at the dorsal surface and
~0.05 at 8-10 mm depth, and ~1.6x brighter left than right.  Is that B1+ (kappa = B1+/nominal) or B0?

Models (both reported everywhere):
  bloch  : the actual v1.83 / v1.912 PPL + Oct-12 in-vivo PPRs run through the repository's PPL event
           mapper (real RF samples, gradients, ADC timing, finite slice profiles) and played in a Bloch
           simulation (dwfse.ppl.bloch); includes B0 and slice-profile effects.      -> oct12_b1_bloch.py
  epg180 : simple ideal-pulse EPG (conventional CPMG with nominal 180 deg refocusing as specified;
           ss-MGOT main recalled branch with the factor 1/2 twist).                 -> oct12_b1_epg.py
  epg166 : same EPG but with the event-model refocusing flip of v1.83 (p180_scale 185 -> 166.4 deg).

Tissue: T1 = 1.9 s, T2 = 45 ms (in-vivo brain 9.4 T), ESP 11 ms, TE 44 ms, one 8-echo unencoded
(navigator-like) train; echo amplitude = |signal| at the ADC centre, in M0 x slice (1 mm) units.

Usage:  python docs/data/oct12_b1_sensitivity.py [--stage bloch|analysis|all] [--workers N]
Outputs: docs/data/oct12_b1_sensitivity.{csv,json}, docs/figures/physical_scanner_2026-10-12/sim_*.png,
         runs/oct12_b1/bloch_cache.json (git-ignored intermediate Bloch results).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import oct12_b1_bloch as B  # noqa: E402
import oct12_b1_epg as E  # noqa: E402

RUNS = ROOT / "runs/oct12_b1"
CACHE = RUNS / "bloch_cache.json"
FIG = ROOT / "docs/figures/physical_scanner_2026-10-12"
OUT_CSV = HERE / "oct12_b1_sensitivity.csv"
OUT_JSON = HERE / "oct12_b1_sensitivity.json"

VERS = ("v183", "v1912")
NAMES = {"v183": "conventional DW-FSE (v1.83)", "v1912": "ss-MGOT (v1.912)"}
T1, T2 = B.T1_DEFAULT, B.T2_DEFAULT
KAPPA_MAIN = np.round(np.arange(0.30, 1.2001, 0.05), 2)          # requested sweep
KAPPA_EXT = np.round(np.arange(1.25, 2.0001, 0.05), 2)           # extension for the near-coil region
KAPPA_ALL = np.concatenate([KAPPA_MAIN, KAPPA_EXT])
B0_GRID = np.array(sorted({25, 75} | set(range(50, 801, 50))), float)
B0_KAPPAS = (1.0, 0.7)
TR_KAPPAS = (0.5, 0.7, 1.0, 1.2)
KAPPA_FIT = np.round(np.arange(0.30, 1.3001, 0.05), 2)
T2_FIT = (0.015, 0.020, 0.025, 0.030, 0.035, 0.045, 0.055, 0.070, 0.090)   # in-vivo fit grid [s]
EXVIVO = dict(T1=3.0, T2=2.0)                                             # PBS phantom
REFOCUS_EVENT = 166.4                                                    # p180_scale 185 -> 166.4 deg

MEAS = {  # echo / echo 1, b10, whole-object projection, ESP 11 ms (from the task description)
    "v183_invivo": [1, 0.58, 0.56, 0.40, 0.34, 0.26, 0.22, 0.17],
    "v183_exvivo": [1, 0.84, 0.87, 0.80, 0.78, 0.74, 0.72, 0.69],
    "ssmgot_invivo": [1, 0.90, 0.64, 0.54, 0.45, 0.39, 0.35, 0.31],
    "ssmgot_exvivo": [1, 0.95, 0.74, 0.64, 0.57, 0.53, 0.49, 0.45],
}


# ----------------------------------------------------------------------------- Bloch jobs
def mk(ver, **kw):
    return B.make_job(ver, ny=64 if ver == "v1912" else 1, **kw)


def build_jobs():
    jobs = []
    for ver in VERS:
        for k in KAPPA_ALL:
            jobs.append(mk(ver, kappa=k))
        for k0 in B0_KAPPAS:
            for df in B0_GRID:
                jobs += [mk(ver, kappa=k0, df=df), mk(ver, kappa=k0, df=-df)]
        for k in TR_KAPPAS:
            jobs.append(mk(ver, kappa=k, tr_s=B.TR_S))
        for k in KAPPA_FIT:
            for t2 in T2_FIT:
                jobs.append(mk(ver, kappa=k, T2=t2))
            jobs.append(mk(ver, kappa=k, **EXVIVO))
    return jobs


def stage_bloch(workers):
    RUNS.mkdir(parents=True, exist_ok=True)
    return B.run_jobs(build_jobs(), CACHE, workers=workers)


# ----------------------------------------------------------------------------- accessors
def bl(cache, ver, kappa, df=0.0, t1=T1, t2=T2, tr_s=None):
    return B.get_echoes(cache, mk(ver, kappa=kappa, df=df, T1=t1, T2=t2, tr_s=tr_s))


def epg(ver, kappa, kind, t1=T1, t2=T2):
    """kind: 'epg180' (nominal 180 deg refocusing, as specified) or 'epg166' (event-model 166.4 deg)."""
    if ver == "v183":
        return E.conventional_epg(kappa, t1, t2, refocus_deg=180.0 if kind == "epg180" else REFOCUS_EVENT)
    return E.ssmgot_epg(kappa, t1, t2)


def curve(kv, rv):
    from scipy.interpolate import PchipInterpolator
    f = PchipInterpolator(np.asarray(kv, float), np.log(np.asarray(rv, float)))
    return lambda k: np.exp(f(k))


def crossings(f, target, lo, hi, n=8001):
    from scipy.optimize import brentq
    kk = np.linspace(lo, hi, n)
    g = np.log(f(kk)) - np.log(target)
    out = []
    for i in np.nonzero(np.sign(g[:-1]) * np.sign(g[1:]) < 0)[0]:
        out.append(float(brentq(lambda x: np.log(f(x)) - np.log(target), kk[i], kk[i + 1])))
    return out


def rms(a, b):
    return float(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)))


def norm_train(t):
    t = np.asarray(t, float)
    return t[1:] / t[0]


# ----------------------------------------------------------------------------- sweeps
def kappa_sweeps(cache):
    rows = []
    for model in ("bloch", "epg180", "epg166"):
        for k in KAPPA_ALL:
            if model == "bloch":
                c, s = bl(cache, "v183", k), bl(cache, "v1912", k)
            else:
                c, s = epg("v183", k, model), epg("v1912", k, model)
            rows.append(dict(sweep="kappa", model=model, kappa=float(k), b0_hz=0.0, T1_s=T1, T2_s=T2, tr_s=None,
                             c=c, s=s))
    return rows


def b0_sweeps(cache):
    rows = []
    for k0 in B0_KAPPAS:
        for df in np.concatenate([[0.0], B0_GRID, -B0_GRID]):
            rows.append(dict(sweep=f"b0_kappa{k0:g}", model="bloch", kappa=float(k0), b0_hz=float(df), T1_s=T1,
                             T2_s=T2, tr_s=None, c=bl(cache, "v183", k0, df=df), s=bl(cache, "v1912", k0, df=df)))
    return rows


def steady_state_rows(cache):
    rows = []
    for k in TR_KAPPAS:
        rows.append(dict(sweep="kappa_TR2000_steady_state", model="bloch", kappa=float(k), b0_hz=0.0, T1_s=T1,
                         T2_s=T2, tr_s=B.TR_S, c=bl(cache, "v183", k, tr_s=B.TR_S),
                         s=bl(cache, "v1912", k, tr_s=B.TR_S)))
    return rows


def t2_ratio_curves(cache):
    """Bloch echo-1 and mean ratios vs kappa (0.3-1.3) for each in-vivo T2 of the fit grid."""
    out = {}
    for t2 in sorted(set(T2_FIT)):
        c = np.array([bl(cache, "v183", k, t2=t2) for k in KAPPA_FIT])
        s = np.array([bl(cache, "v1912", k, t2=t2) for k in KAPPA_FIT])
        out[t2] = dict(kappa=KAPPA_FIT, c=c, s=s, r1=s[:, 0] / c[:, 0], rmean=s.mean(1) / c.mean(1))
    return out


def ratio_curves(rows_model):
    kv = np.array([r["kappa"] for r in rows_model])
    r1 = np.array([r["s"][0] / r["c"][0] for r in rows_model])
    rm = np.array([r["s"].mean() / r["c"].mean() for r in rows_model])
    return kv, r1, rm


def lr_table(f, kmax, factor=1.6, base=(0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1)):
    out = []
    for kr in base:
        target = factor * float(f(kr))
        roots = [x for x in crossings(f, target, kr, kmax) if x > kr]
        kk = np.array([kr * 0.97, kr * 1.03])
        n = float(np.diff(np.log(f(kk)))[0] / np.diff(np.log(kk))[0])
        out.append(dict(kappa_right=kr, ratio_right=float(f(kr)), local_exponent=n,
                        kappa_left=roots[0] if roots else None,
                        delta_kappa=(roots[0] - kr) if roots else None,
                        percent_higher=(100 * (roots[0] / kr - 1)) if roots else None))
    return out


def deep_vs_surface(f, kmin, drop=0.1, surfaces=(0.9, 1.0, 1.1, 1.2, 1.3, 1.5)):
    """kappa at depth that reduces the ratio by `drop` relative to the surface kappa."""
    out = []
    for ks in surfaces:
        target = drop * float(f(ks))
        roots = [x for x in crossings(f, target, kmin, ks) if x < ks]
        out.append(dict(kappa_surface=ks, ratio_surface=float(f(ks)), kappa_deep=roots[-1] if roots else None,
                        deep_over_surface=(roots[-1] / ks) if roots else None))
    return out


def b0_analysis(rows_b0):
    res = {}
    for k0 in B0_KAPPAS:
        sel = [r for r in rows_b0 if r["kappa"] == k0]
        d0 = next(r for r in sel if r["b0_hz"] == 0.0)
        r1_0 = d0["s"][0] / d0["c"][0]
        rm_0 = d0["s"].mean() / d0["c"].mean()
        tab = []
        for df in B0_GRID:
            rp = next(r for r in sel if r["b0_hz"] == df)
            rn = next(r for r in sel if r["b0_hz"] == -df)
            entry = dict(b0_hz=float(df))
            for tag, r in (("plus", rp), ("minus", rn)):
                entry[f"ratio_e1_{tag}"] = float(r["s"][0] / r["c"][0])
                entry[f"ratio_mean_{tag}"] = float(r["s"].mean() / r["c"].mean())
                entry[f"v183_e1_rel_{tag}"] = float(r["c"][0] / d0["c"][0])
                entry[f"ssmgot_e1_rel_{tag}"] = float(r["s"][0] / d0["s"][0])
                entry[f"v183_mean_rel_{tag}"] = float(r["c"].mean() / d0["c"].mean())
                entry[f"ssmgot_mean_rel_{tag}"] = float(r["s"].mean() / d0["s"].mean())
                entry[f"rel_ratio_e1_{tag}"] = float(r["s"][0] / r["c"][0] / r1_0)
                entry[f"rel_ratio_mean_{tag}"] = float(r["s"].mean() / r["c"].mean() / rm_0)
            tab.append(entry)
        res[k0] = dict(ratio_e1_at_0=float(r1_0), ratio_mean_at_0=float(rm_0), table=tab)
    return res


def b0_for_rel(tab, thresh, key="rel_ratio_e1"):
    """Smallest |B0| [Hz] at which the ratio relative to B0=0 falls to thresh (linear interpolation), per sign."""
    out = {}
    for tag in ("plus", "minus"):
        x = [0.0] + [e["b0_hz"] for e in tab]
        y = [1.0] + [e[f"{key}_{tag}"] for e in tab]
        hit = None
        for i in range(1, len(x)):
            if y[i] <= thresh < y[i - 1]:
                hit = x[i - 1] + (y[i - 1] - thresh) / (y[i - 1] - y[i]) * (x[i] - x[i - 1])
                break
        out[tag] = None if hit is None else float(hit)
    out["min_over_signs"] = None if all(v is None for v in out.values()) else float(min(v for v in out.values() if v is not None))
    out["min_rel_reached_to_800Hz"] = float(min(min(e[f"{key}_plus"], e[f"{key}_minus"]) for e in tab))
    return out


# ----------------------------------------------------------------------------- fits
def epg_model_fn(ver, kind, t1):
    if ver == "v183":
        ref = 180.0 if kind == "epg180" else REFOCUS_EVENT
        return lambda k, t2: E.conventional_epg(k, t1, t2, refocus_deg=ref)
    return lambda k, t2: E.ssmgot_epg(k, t1, t2)


def _interval(kg, prof, ib, rb, tol=0.01):
    lo = hi = ib
    while lo > 0 and prof[lo - 1] <= rb + tol:
        lo -= 1
    while hi < len(kg) - 1 and prof[hi + 1] <= rb + tol:
        hi += 1
    return [float(kg[lo]), float(kg[hi])]


def fit_epg(fn, y, kgrid, t2grid):
    """Grid search + Nelder-Mead polish for (kappa, T2); len(t2grid)==1 fits kappa only."""
    from scipy.optimize import minimize
    yy = norm_train(y)
    Lg = np.full((len(kgrid), len(t2grid)), 9.0)
    for i, k in enumerate(kgrid):
        for j, t2 in enumerate(t2grid):
            m = fn(k, t2)
            if m[0] > 1e-9:
                Lg[i, j] = rms(m[1:] / m[0], yy)
    i, j = np.unravel_index(np.argmin(Lg), Lg.shape)
    kb, tb, rb = float(kgrid[i]), float(t2grid[j]), float(Lg[i, j])
    if len(t2grid) > 1:
        def f(p):
            m = fn(p[0], p[1])
            return rms(m[1:] / m[0], yy) if (m[0] > 1e-9 and p[1] > 0.004 and p[0] > 0.05) else 9.0
        sol = minimize(f, [kb, tb], method="Nelder-Mead", options=dict(xatol=1e-4, fatol=1e-8))
        if sol.fun < rb:
            kb, tb, rb = float(sol.x[0]), float(sol.x[1]), float(sol.fun)
    else:
        def f1(p):
            m = fn(p[0], t2grid[0])
            return rms(m[1:] / m[0], yy) if (m[0] > 1e-9 and p[0] > 0.05) else 9.0
        sol = minimize(f1, [kb], method="Nelder-Mead", options=dict(xatol=1e-4, fatol=1e-8))
        if sol.fun < rb:
            kb, rb = float(sol.x[0]), float(sol.fun)
    prof = Lg.min(axis=1)
    m = fn(kb, tb)
    return dict(kappa=kb, T2_s=tb, rms=rb, kappa_interval=_interval(kgrid, prof, int(np.argmin(abs(kgrid - kb))), rb),
                profile_kappa=[float(x) for x in kgrid], profile_rms=[float(x) for x in prof],
                model_train=(m / m[0]).tolist(), echo1_epg=float(m[0]))


def bloch_fit_table(cache, ver, invivo):
    if invivo:
        return np.array([[bl(cache, ver, k, t2=t2) for t2 in T2_FIT] for k in KAPPA_FIT])        # [k, t2, 8]
    return np.array([bl(cache, ver, k, t1=EXVIVO["T1"], t2=EXVIVO["T2"]) for k in KAPPA_FIT])    # [k, 8]


def fit_bloch(Z, y, invivo):
    from scipy.interpolate import RectBivariateSpline, CubicSpline
    from scipy.optimize import minimize
    yy = norm_train(y)
    kf = KAPPA_FIT
    if invivo:
        t2ms = np.array(T2_FIT) * 1e3
        norm = Z[:, :, 1:] / Z[:, :, :1]
        sp = [RectBivariateSpline(kf, t2ms, norm[:, :, n], kx=3, ky=2) for n in range(7)]
        e1 = RectBivariateSpline(kf, t2ms, Z[:, :, 0], kx=3, ky=2)

        def model(k, t2):
            return np.array([float(s_(k, t2)[0, 0]) for s_ in sp])
        kg = np.arange(kf[0], kf[-1] + 1e-9, 0.01)
        tg = np.arange(t2ms[0], t2ms[-1] + 1e-9, 1.0)
        L = np.array([[rms(model(k, t), yy) for t in tg] for k in kg])
        i, j = np.unravel_index(np.argmin(L), L.shape)
        sol = minimize(lambda p: rms(model(*p), yy) if kf[0] <= p[0] <= kf[-1] and t2ms[0] <= p[1] <= t2ms[-1] else 9.0,
                       [kg[i], tg[j]], method="Nelder-Mead", options=dict(xatol=1e-4, fatol=1e-8))
        kb, tb, rb = float(sol.x[0]), float(sol.x[1]) * 1e-3, float(sol.fun)
        prof = L.min(axis=1)
        return dict(kappa=kb, T2_s=tb, rms=rb, kappa_interval=_interval(kg, prof, int(np.argmin(abs(kg - kb))), rb),
                    profile_kappa=kg.tolist(), profile_rms=prof.tolist(),
                    model_train=[1.0] + model(kb, tb * 1e3).tolist(), echo1_bloch=float(e1(kb, tb * 1e3)[0, 0]))
    norm = Z[:, 1:] / Z[:, :1]
    cs = [CubicSpline(kf, norm[:, n]) for n in range(7)]

    def model(k):
        return np.array([c(k) for c in cs])
    kg = np.arange(kf[0], kf[-1] + 1e-9, 0.005)
    L = np.array([rms(model(k), yy) for k in kg])
    ib = int(np.argmin(L))
    sol = minimize(lambda p: rms(model(p[0]), yy) if kf[0] <= p[0] <= kf[-1] else 9.0, [kg[ib]], method="Nelder-Mead",
                   options=dict(xatol=1e-4, fatol=1e-8))
    kb, rb = float(sol.x[0]), float(sol.fun)
    return dict(kappa=kb, T2_s=EXVIVO["T2"], rms=rb, kappa_interval=_interval(kg, L, ib, rb),
                profile_kappa=kg.tolist(), profile_rms=L.tolist(), model_train=[1.0] + model(kb).tolist())


# ----------------------------------------------------------------------------- output
def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write_csv(rows):
    cols = ["sweep", "model", "kappa", "b0_hz", "T1_s", "T2_s", "tr_s", "v183_echo1", "v183_mean_echo1_8",
            "ssmgot_echo1", "ssmgot_mean_echo1_8", "ratio_echo1", "ratio_mean_echo1_8"] \
        + [f"v183_echo{i}" for i in range(1, 9)] + [f"ssmgot_echo{i}" for i in range(1, 9)]
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            c, s = r["c"], r["s"]
            w.writerow([r["sweep"], r["model"], f"{r['kappa']:.3f}", f"{r['b0_hz']:.1f}", r["T1_s"], r["T2_s"],
                        "" if r["tr_s"] is None else r["tr_s"],
                        f"{c[0]:.6g}", f"{c.mean():.6g}", f"{s[0]:.6g}", f"{s.mean():.6g}",
                        f"{s[0] / c[0]:.6g}", f"{s.mean() / c.mean():.6g}"]
                       + [f"{x:.6g}" for x in c] + [f"{x:.6g}" for x in s])


def to_py(o):
    if isinstance(o, dict):
        return {str(k): to_py(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [to_py(v) for v in o]
    if isinstance(o, np.ndarray):
        return to_py(o.tolist())
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    return o


def analysis(workers):
    cache = B.load_cache(CACHE)
    missing = [j for j in build_jobs() if B.job_key(j) not in cache]
    if missing:
        raise SystemExit(f"{len(missing)} Bloch jobs missing; run --stage bloch first")
    ctx = {v: B.setup(v) for v in VERS}

    rows_k = kappa_sweeps(cache)
    rows_b = b0_sweeps(cache)
    rows_s = steady_state_rows(cache)
    all_rows = rows_k + rows_b + rows_s
    write_csv(all_rows)

    R = {}
    # ---------------- kappa sweep summary + inverse maps
    sweep = {}
    maps = {}
    for model in ("bloch", "epg180", "epg166"):
        rm = [r for r in rows_k if r["model"] == model]
        kv, r1, rmean = ratio_curves(rm)
        sweep[model] = [dict(kappa=float(r["kappa"]), v183_echo1=float(r["c"][0]), v183_mean=float(r["c"].mean()),
                             ssmgot_echo1=float(r["s"][0]), ssmgot_mean=float(r["s"].mean()),
                             ratio_echo1=float(r["s"][0] / r["c"][0]), ratio_mean=float(r["s"].mean() / r["c"].mean()))
                        for r in rm]
        f1, fm = curve(kv, r1), curve(kv, rmean)
        maps[model] = dict(kv=kv, r1=r1, rm=rmean, f1=f1, fm=fm)
    R["kappa_sweep"] = sweep

    inv = {}
    for model, m in maps.items():
        inv[model] = {}
        for tag, f in (("echo1", m["f1"]), ("mean", m["fm"])):
            inv[model][tag] = {
                "ratio_at_kappa_1": float(f(1.0)),
                "kappa_for_ratio_0.5": crossings(f, 0.5, 0.3, 2.0),
                "kappa_for_ratio_0.05": crossings(f, 0.05, 0.3, 2.0),
                "kappa_for_ratio_0.25": crossings(f, 0.25, 0.3, 2.0),
                "max_ratio_0.3_to_2.0": float(np.max(f(np.linspace(0.3, 2.0, 2000)))),
                "kappa_at_max": float(np.linspace(0.3, 2.0, 2000)[np.argmax(f(np.linspace(0.3, 2.0, 2000)))]),
                "deep_vs_surface_10x_drop": deep_vs_surface(f, 0.3),
            }
    R["inverse_maps"] = inv
    R["lr_1.6"] = {model: {"echo1": lr_table(m["f1"], 2.0), "mean": lr_table(m["fm"], 2.0)} for model, m in maps.items()}

    # T2 sensitivity of the Bloch ratio curve
    t2c = t2_ratio_curves(cache)
    R["t2_sensitivity_bloch"] = {}
    for t2, d in t2c.items():
        f = curve(d["kappa"], d["r1"])
        R["t2_sensitivity_bloch"][f"{t2 * 1e3:.0f}ms"] = {
            "ratio_echo1_at_kappa": {f"{k:.2f}": float(f(k)) for k in (0.5, 0.7, 1.0, 1.2)},
            "kappa_for_ratio_0.5": crossings(f, 0.5, 0.3, 1.3), "kappa_for_ratio_0.05": crossings(f, 0.05, 0.3, 1.3)}

    # ---------------- steady state vs single shot
    ss = []
    for r in rows_s:
        c0, s0 = bl(cache, "v183", r["kappa"]), bl(cache, "v1912", r["kappa"])
        ss.append(dict(kappa=r["kappa"], ratio_echo1_single_shot=float(s0[0] / c0[0]),
                       ratio_echo1_TR2000=float(r["s"][0] / r["c"][0]),
                       v183_echo1_change=float(r["c"][0] / c0[0]), ssmgot_echo1_change=float(r["s"][0] / s0[0])))
    R["steady_state_TR2000"] = ss

    # ---------------- B0
    b0 = b0_analysis(rows_b)
    R["b0"] = b0
    R["b0_equivalents"] = {}
    for k0 in B0_KAPPAS:
        tab = b0[k0]["table"]
        R["b0_equivalents"][f"kappa{k0:g}"] = {
            "ratio_e1_at_B0=0": b0[k0]["ratio_e1_at_0"],
            "B0_for_relative_ratio_0.1 (10x drop, e.g. 0.5->0.05)": b0_for_rel(tab, 0.1),
            "B0_for_relative_ratio_0.5": b0_for_rel(tab, 0.5),
            "B0_for_relative_ratio_1/1.6 (L/R 1.6 from B0 alone)": b0_for_rel(tab, 1 / 1.6),
            "B0_for_relative_ratio_0.9": b0_for_rel(tab, 0.9),
            "ratio_e1_rel_at_100Hz": [next(e for e in tab if e["b0_hz"] == 100)[k] for k in ("rel_ratio_e1_plus", "rel_ratio_e1_minus")],
        }

    # ---------------- fits
    fits = {}
    kg_e = np.arange(0.20, 1.601, 0.01)
    t2g_e = np.arange(0.008, 0.2001, 0.002)
    for key, y in MEAS.items():
        ver = key.split("_")[0]
        invivo = key.endswith("invivo")
        fits[key] = {"measured": y}
        for kind in (("epg180", "epg166") if ver == "v183" else ("epg180",)):
            if invivo:
                fits[key][kind] = fit_epg(epg_model_fn(ver, kind, T1), y, kg_e, t2g_e)
            else:
                fits[key][kind] = fit_epg(epg_model_fn(ver, kind, EXVIVO["T1"]), y, kg_e, [EXVIVO["T2"]])
        Z = bloch_fit_table(cache, ver_name(ver), invivo)
        fits[key]["bloch"] = fit_bloch(Z, y, invivo)
    # direct Bloch verification at the fitted points
    ver_jobs = []
    for key, d in fits.items():
        invivo = key.endswith("invivo")
        ver = ver_name(key.split("_")[0])
        kw = dict(kappa=round(d["bloch"]["kappa"], 4), T2=round(d["bloch"]["T2_s"], 5))
        if not invivo:
            kw.update(T1=EXVIVO["T1"], T2=EXVIVO["T2"])
        ver_jobs.append((key, mk(ver, **kw)))
    cache = B.run_jobs([j for _, j in ver_jobs], CACHE, workers=min(workers, len(ver_jobs)), verbose=False)
    for key, j in ver_jobs:
        t = B.get_echoes(cache, j)
        fits[key]["bloch"]["direct_bloch_train"] = (t / t[0]).tolist()
        fits[key]["bloch"]["direct_bloch_rms"] = rms(t[1:] / t[0], norm_train(MEAS[key]))
        fits[key]["bloch"]["direct_bloch_echo1"] = float(t[0])
    # EPG fit evaluated in Bloch? (event model uses 166.4 refocusing; the EPG fits above are shown separately)
    R["fits"] = fits

    # ---------------- sequence metadata
    meta = dict(
        question="ss-MGOT/v1.83 b10 ratio ~0.5 (surface) -> ~0.05 (8-10 mm deep), 1.6x L/R: B1+ (kappa) vs B0",
        tissue=dict(T1_s=T1, T2_s=T2, exvivo=EXVIVO),
        timing=dict(TE_ms=44, ESP_ms=11, TR_ms=2000, ETL=8, ordering="centric (echo 1 = k-space centre)"),
        refocus_event_model_deg=REFOCUS_EVENT,
        kappa_grid=dict(requested="0.30..1.20 step 0.05", extension="1.25..2.00 step 0.05"),
        b0_grid_hz=B0_GRID.tolist(),
        bloch=dict(grid="z: 1000 points over 5 slice widths (5 mm); y (ss-MGOT spoiler axis): 64 points over 35/128 mm; "
                        "RF 1 substep per 10 us (v1.912) or 2 us (v1.83) raw sample; nominal instruction-cost model; "
                        "rfdelay 60 us gradient lag; RF latency 3 us",
                   convergence="nz 1000 vs 3000 identical to 4 digits; ny 32 vs 64 changes ss-MGOT echoes by 0.5%"),
        files={v: dict(ppl=str(B.CASES[v]["ppl"].relative_to(ROOT)), ppl_sha256=sha(B.CASES[v]["ppl"]),
                       ppr=str(B.CASES[v]["ppr"].relative_to(ROOT)), ppr_sha256=sha(B.CASES[v]["ppr"]),
                       overrides=B.OVERRIDES) for v in VERS},
        rf_events={v: B.flip_table(ctx[v]) for v in VERS},
    )
    R["meta"] = meta
    R["_maps"] = maps
    R["_rows"] = dict(k=rows_k, b=rows_b, s=rows_s)
    R["_t2c"] = t2c
    R["_cache"] = cache
    return R


def ver_name(prefix):
    return {"v183": "v183", "ssmgot": "v1912", "v1912": "v1912"}[prefix]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all", choices=["bloch", "analysis", "all"])
    ap.add_argument("--workers", type=int, default=14)
    a = ap.parse_args()
    if a.stage in ("bloch", "all"):
        stage_bloch(a.workers)
    if a.stage in ("analysis", "all"):
        R = analysis(a.workers)
        try:
            import oct12_b1_figs as F
            F.make_all(R, FIG)
        except ImportError:
            print("[figs] oct12_b1_figs.py not available yet")
        out = {k: v for k, v in R.items() if not k.startswith("_")}
        OUT_JSON.write_text(json.dumps(to_py(out), indent=1))
        print(f"wrote {OUT_CSV.name}, {OUT_JSON.name}")


if __name__ == "__main__":
    main()
