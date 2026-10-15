#!/usr/bin/env python
"""2026-10-12: v1.83 frequency check, off-centre RF phase (mode 0 vs 1, phcal), and phase-vs-artefact analysis.

Reads the MRDs through docs/data/oct12_load.py (read-only). Writes
    docs/data/oct12_phase_calibration.csv   one row per (scan, volume, slice) navigator fit (+ b10 image metrics)
    docs/data/oct12_phase_calibration.json  summary
    docs/figures/physical_scanner_2026-10-12/{freq_*,phasecal_*}.png

Method (same as tools/offcentre_phase_cal.py, whose functions are imported, not re-implemented):
  navigator echo e phase = angle(sum_samples nav_e * conj(nav_1)), fitted as c + s*(e-1) + h*(-1)^e with the
  tool's grid search (fit_ramp) and its +z/-z alias pairing (analyse_scan). s = ramp (deg/echo), h = alternation (deg).
  (s,h) and (s+-180, h+-90) are the same data; the tool reports the smaller-|h| one, this script also lists the alias.
  Statistical error = parametric Monte Carlo (100 draws): complex Gaussian noise, sigma from the first/last 10 readout samples of each
  echo, added to every navigator sample and refitted. It is tiny (echo-peak SNR is 10^2-10^3) and is NOT scan-to-scan repeatability.

Run:  python docs/data/oct12_phase_calibration.py
"""
import csv
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import scipy.ndimage as ndi
from scipy import stats
from skimage.registration import phase_cross_correlation

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools"))
import oct12_load as L  # noqa: E402
import offcentre_phase_cal as opc  # noqa: E402
import frequency_check as fc  # noqa: E402

FIGDIR = ROOT / "docs/figures/physical_scanner_2026-10-12"
CSV_OUT = HERE / "oct12_phase_calibration.csv"
JSON_OUT = HERE / "oct12_phase_calibration.json"
PASS = opc.PASS_LIMIT_DEG
NBOOT = 100          # Monte-Carlo noise draws per fit
RNG = np.random.default_rng(12)
warnings.filterwarnings("ignore", category=RuntimeWarning)

FIT_KEYS = ["D", "E", "F", "G", "QQ", "QQQ", "Q", "MM", "Q1", "R", "iA", "iD", "iE", "iF", "iB"]
CENTRE_ONLY = ["A", "B", "M", "N", "C", "O", "iC"]          # single centre slice, reported as references
CENTRE_REF = {"MM": "QQQ"}                                   # MM has no centre slice: use QQQ (same RX gain, mode 0, TR 2000)
EXVIVO_IMG = ["D", "E", "F", "G", "QQ", "QQQ", "Q", "MM", "Q1", "R"]   # PBS disk present, banding metrics valid


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(f"{float(o):.6g}")
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def wrap180(x):
    return opc.wrap180(x)


# =============================================================================================== 1. frequency
def register(a, b, up=20):
    sh = phase_cross_correlation(a, b, upsample_factor=up)[0]
    return float(sh[0]), float(sh[1])


def frequency_section(data):
    pa = L.mrd_path("A")
    pb = L.mrd_path("B")
    a, da = fc.image(pa)
    b, db = fc.image(pb)
    if da < db:
        (a, da), (b, db) = (b, db), (a, da)
    res = {}
    for up in (10, 20, 100):
        r, c = register(a, b, up)
        res[f"upsample{up}"] = dict(pe_px=r, read_px=c)
    nread = a.shape[1]
    bw_fast = 1e6 / db
    hz_per_px = bw_fast / nread
    r, c = register(a, b, 20)
    out = dict(
        tool="tools/frequency_check.py A B (re-run through its own image(); same call as the CLI)",
        A=str(pa.relative_to(ROOT)), B=str(pb.relative_to(ROOT)),
        dwell_us=dict(A=da, B=db), readout_px_relative=c, phase_encode_px_relative=r,
        implied_df_hz=c * hz_per_px, hz_per_40kHz_pixel=hz_per_px,
        verdict="PASS" if abs(c) < 0.5 else "FAIL",
        upsample_sensitivity=res,
        resolution_note="phase_cross_correlation upsample_factor 20 -> 0.05 px resolution = +-16 Hz; shifts at factor 10/20/100 agree to 0.01 px",
        ref_2026_10_10=dict(read_px=0.2, verdict="PASS"),
        ref_2026_10_11=dict(read_px=9.1, df_hz=2830, verdict="FAIL"),
        sign_note="sign of df is not calibrated (as in the tool)",
    )
    # independent check: intensity-weighted column centroid of each image (A at 20 kHz moves 2x B per Hz)
    def cen(im):
        p = im.sum(0)
        p = np.clip(p - 0.2 * p.max(), 0, None)
        return float((p * np.arange(len(p))).sum() / p.sum())
    out["column_centroid_px"] = dict(A_20kHz=cen(a), B_40kHz=cen(b), A_minus_B=cen(a) - cen(b),
                                     note="centroid of the readout projection above 20% of its peak; A-B should be ~0 if df~0 "
                                          "(A displaced 2x B per Hz). In pixels of the same FOV.")
    # cross-version / cross-time readout registration of centre-slice b10 magnitude images (same BW 40 kHz -> df = d*312.5 Hz)
    def cimg(key, vol=0):
        s = data[key]
        ci = int(np.argmin(np.abs(s["offsets_mm"])))
        return s["img"][vol, ci]
    pairs = [("B", "C", "ex vivo single slice: v1.83 vs v1.912"), ("M", "O", "ex vivo single slice: v1.83 vs v1.912 (4-volume scans)"),
             ("Q", "R", "ex vivo centre slice of Q/R (matched 3-slice, v1.83 vs v1.912)"),
             ("iA", "iB", "in vivo centre slice: v1.83 vs v1.912 (the requested comparison)"),
             ("iA", "iC", "in vivo: v1.83 vs v1.912 single slice"), ("iB", "iC", "in vivo: v1.912 vs v1.912 (same-sequence control)"),
             ("iA", "iD", "in vivo: v1.83 vs v1.83 (same-sequence control)")]
    cross = []
    hz_px40 = 40000.0 / 128
    for k1, k2, why in pairs:
        if k1 not in data or k2 not in data:
            continue
        i1, i2 = cimg(k1), cimg(k2)
        r, c = register(i1 / np.percentile(i1, 99), i2 / np.percentile(i2, 99), 20)
        cross.append(dict(ref=k1, moving=k2, note=why, read_px=c, pe_px=r, df_equiv_hz=c * hz_px40))
    out["cross_version_registration"] = cross
    out["cross_version_note"] = ("Both scans of a pair use 40 kHz, so a readout shift d corresponds to df = d*312.5 Hz only if nothing else moved. "
                                 "In vivo, motion contributes too: the phase-encode shift of the same pair is the motion control, and the "
                                 "same-sequence in-vivo pairs (iB-iC, iA-iD) show the shift between unrelated acquisitions.")
    return out, (a, b)


# =============================================================================================== 2. navigator fits
H_GRID = np.arange(-90.0, 90.0 + 1e-9, 0.1)


def fit_fast(phase_rad):
    """Vectorised version of opc.fit_ramp (identical algorithm: grid over h, unwrap, least squares); verified against it."""
    n = len(phase_rad)
    e = np.arange(1, n + 1, dtype=float)
    u = np.unwrap(phase_rad[None, :] - np.radians(H_GRID)[:, None] * ((-1.0) ** e)[None, :], axis=1)
    x = e - 1.0
    xc = x - x.mean()
    slope = (u * xc).sum(1) / (xc ** 2).sum()
    icpt = u.mean(1) - slope * x.mean()
    res = u - icpt[:, None] - slope[:, None] * x[None, :]
    rms = np.sqrt((res ** 2).mean(1))
    j = int(np.argmin(rms))
    return opc.canonical(float(np.degrees(slope[j])), float(H_GRID[j]), float(np.degrees(rms[j])))


def hz_per_mm(s):
    rfnum = int(opc._var(s["text"], "rfnum", 1))
    return 0.71 * opc.RF_BW.get(rfnum, 3000) / s["thickness_mm"]


def category(s):
    subj = "in vivo" if s["key"].startswith("i") else "ex vivo"
    if s["version"] == "v1.83":
        mode = "mode 1" if s["phmode"] == 1 else "mode 0"
        return f"{subj} v1.83 {mode}"
    return f"{subj} {s['version']}"


def noise_mc(nav, ms, mh, B=NBOOT):
    """Monte-Carlo noise error of (s, h): add complex Gaussian noise (sigma from the outermost 10 readout samples each side, where the
    k-space echo has no signal) to all navigator samples, refit, map each draw to the representation of the main fit."""
    tails = np.concatenate([nav[:, :10], nav[:, -10:]], axis=1)
    sig = float(np.sqrt(np.mean(np.abs(tails) ** 2) / 2.0))
    noise = RNG.standard_normal((B,) + nav.shape) + 1j * RNG.standard_normal((B,) + nav.shape)
    nb = nav[None] + sig * noise
    ph = np.angle((nb * np.conj(nb[:, 0:1])).sum(-1))
    ds, dh = [], []
    for b in range(B):
        f = fit_fast(ph[b])
        c = [(f["s"], f["h"]), (f["alias_s"], f["alias_h"])]
        sb, hb = min(c, key=lambda t_: float(wrap180(t_[0] - ms)) ** 2 + float(wrap180(t_[1] - mh)) ** 2)
        ds.append(float(wrap180(sb - ms)))
        dh.append(float(wrap180(hb - mh)))
    snr_last = float(np.abs(nav[-1]).max() / (sig * np.sqrt(2.0)))
    return float(np.sqrt(np.mean(np.square(ds)))), float(np.sqrt(np.mean(np.square(dh)))), snr_last


def echo_ratio(nav):
    """complex echo ratio c_e = <n_e, n_1>/<n_1, n_1> (magnitude = relative amplitude, angle = ip phase)."""
    return (nav * np.conj(nav[0:1])).sum(-1) / (np.abs(nav[0]) ** 2).sum()


def analyse_navigators(key, s):
    navs = s["navs"]
    E, S_, Lh, _ = navs.shape
    hz = hz_per_mm(s)
    b = np.asarray(s["b"], float)
    primary = next((i for i, bb in enumerate(b) if bb <= 20), 0)
    cat = category(s)
    rows = []
    parity = 0.0
    for v in range(E):
        ip = np.zeros((S_, Lh))
        for sl in range(S_):
            n = navs[v, sl]
            ip[sl] = np.angle(np.sum(n * np.conj(n[0:1]), axis=-1))
        res = opc.analyse_scan(dict(ip=ip, offsets_mm=np.asarray(s["offsets_mm"], float), hz_per_mm=hz))
        centre_ratio = None
        for r in res["slices"]:
            sl = r["slice"]
            if r["centre"]:
                a_last = np.abs(navs[v, sl]).sum(-1)
                centre_ratio = a_last[-1] / a_last[0]
        for r in res["slices"]:
            sl = r["slice"]
            nav = navs[v, sl]
            f = fit_fast(ip[sl])
            parity = max(parity, abs(f["rms"] - r["rms_deg"]), min(abs(float(wrap180(f["s"] - r["s"]))), abs(float(wrap180(f["alias_s"] - r["s"])))))
            sd_s, sd_h, snr_last = noise_mc(nav, r["s"], r["h"])
            fss = fit_fast(ip[sl][2:] - ip[sl][2])
            ss_off = float(np.degrees(np.angle(np.exp(1j * ip[sl][2:]).mean())))
            amp = np.abs(nav).sum(-1)
            ratio = float(amp[-1] / amp[0])
            reps = [(r["s"], r["h"]), (r["alias_s"], r["alias_h"])]
            low = min(reps, key=lambda t: abs(t[0]))
            alt_min = min(abs(r["h"]), abs(r["alias_h"]))
            z = r["z_mm"]
            robust = "reference" if r["centre"] else (
                "PASS" if any(abs(a) <= PASS and abs(c) <= PASS for a, c in reps) else "FAIL")
            ipd = np.degrees(ip[sl])
            circ_mean = np.angle(np.exp(1j * np.radians(ipd[1:])).mean())
            phase_dev = float(np.sqrt(np.mean(wrap180(ipd[1:] - np.degrees(circ_mean)) ** 2)))
            rows.append(dict(
                scan=key, folder=s["folder"].name, version=s["version"], subject="in vivo" if key.startswith("i") else "ex vivo",
                category=cat, phmode=("" if s["phmode"] is None else int(s["phmode"])), phcal=("" if s["phcal"] is None else int(s["phcal"])),
                etl=Lh, tr_ms=s["tr"], esp_ms=s["esp"], rx_gain=s["gains"]["rx"], volume=v, b=float(b[v]), primary_b10=bool(v == primary),
                slice=sl, z_mm=z, centre=bool(r["centre"]), f_hz_nominal=r["f_hz"],
                ramp_deg_per_echo=r["s"], alt_deg=r["h"], alias_ramp=r["alias_s"], alias_alt=r["alias_h"],
                ramp_low=low[0], alt_low=low[1], alt_min_any_rep=alt_min, rep_ambiguous=bool(alt_min >= 30 and not r["centre"]),
                fit_rms_deg=r["rms_deg"], noise_sd_ramp=sd_s, noise_sd_alt=sd_h, snr_last_echo=snr_last,
                ramp_ss=fss["s"], alt_ss=fss["h"], rms_ss=fss["rms"], ss_offset_deg=ss_off,
                tau_us_nominal=r["tau_us"], ramp_per_mm=(r["s"] / z if abs(z) > 0.05 else None),
                amp_last_over_first=ratio, amp_ratio_vs_centre=(ratio / centre_ratio if centre_ratio else None),
                phase_dev_deg=phase_dev, verdict_tool=r["verdict"], verdict_either_rep=robust,
                ip_deg=[float(x) for x in ipd],
            ))
    return rows, parity


def select_plot_rep(rows, cal):
    """Representation used for figures/correlations: tool-canonical, except (i) rep-ambiguous slices -> the |ramp|<=90 rep,
    (ii) mode-1 E/F/G -> the rep continuous with the linear phcal model s0 + sigma*k*P (so the three scans line up)."""
    for r in rows:
        s, h = r["ramp_deg_per_echo"], r["alt_deg"]
        if r["rep_ambiguous"]:
            s, h = r["ramp_low"], r["alt_low"]
        if r["scan"] in ("E", "F", "G") and not r["centre"] and cal.get("mode") == "joint":
            zk = round(r["z_mm"], 3)
            pz = cal["per_slice"].get(zk) or cal["per_slice"].get(str(zk))
            if pz:
                kk = 360.0 * pz["f_hz"] * 1e-7
                sphys = pz["s0"] + cal["sign_sigma"] * kk * r["phcal"]
                cands = [(r["ramp_deg_per_echo"], r["alt_deg"]), (r["alias_ramp"], r["alias_alt"])]
                s, h = min(cands, key=lambda t: abs(float(wrap180(t[0] - sphys))))
        r["ramp_plot"], r["alt_plot"] = float(s), float(h)


# =============================================================================================== 3. image metrics
def disk(r):
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def objmask(im):
    sm = ndi.gaussian_filter(im, 1.5)
    m = sm > 0.2 * np.percentile(sm, 98)
    lab, n = ndi.label(m)
    if n > 1:
        m = lab == (1 + int(np.argmax(ndi.sum(m, lab, range(1, n + 1)))))
    m = ndi.binary_closing(m, disk(4))
    return ndi.binary_fill_holes(m)


def pbs_roi(centre_img, m_off, shift=(0, 0)):
    """Uniform-PBS ROI: centre-slice mask eroded 6 px, intersected with the off-centre slice's eroded mask and with pixels within
    +-25% of the PBS median in the centre slice (drops brain, holder rods, bubbles)."""
    m = objmask(centre_img)
    e = ndi.binary_erosion(m, disk(6)) & ndi.binary_erosion(m_off, disk(6))
    med = np.median(centre_img[e])
    sm = ndi.gaussian_filter(centre_img, 1.0)
    return ndi.binary_erosion(e & (sm > 0.75 * med) & (sm < 1.25 * med), disk(1))


def band_metric(im, roi):
    rows = np.flatnonzero(roi.sum(1) >= 10)
    if len(rows) < 20:
        return np.nan, np.nan
    rm = np.array([im[r][roi[r]].mean() for r in rows])
    x = np.arange(len(rows))
    res = rm - np.polyval(np.polyfit(x, rm, 3), x)
    return float(res.std() / rm.mean()), float((res.max() - res.min()) / rm.mean())


def ghost_frac(im, m):
    out = ~ndi.binary_dilation(m, disk(3))
    return float((im[out] ** 2).sum() / (im ** 2).sum())


def echo_of_row(s):
    e = np.zeros(s["N"], int)
    e[s["rows"]] = np.arange(s["N"]) % s["L"]
    return e


def recon_mag(k):
    return np.abs(np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(k))))


def image_metrics(data, fits):
    """b10 volume only. Adds band/ghost columns to the rows of fits (dict key -> rows)."""
    sims = {}
    for key in EXVIVO_IMG + ["iA", "iD", "iE", "iF", "iB"]:
        s = data[key]
        rows = [r for r in fits[key] if r["primary_b10"]]
        v = rows[0]["volume"]
        ref_key = CENTRE_REF.get(key, key)
        sr = data[ref_key]
        ci = int(np.argmin(np.abs(sr["offsets_mm"])))
        cen_img = sr["img"][v if ref_key == key else 0, ci]
        roi_ok = key in EXVIVO_IMG
        shift_note = None
        masks = {}
        for r in rows:
            sl = r["slice"]
            im = s["img"][v, sl]
            m = objmask(im)
            masks[sl] = m
            r["ghost_frac"] = ghost_frac(im, m)
            r["mask_area_px"] = int(m.sum())
        cen_rows = [r for r in rows if r["centre"]]
        if ref_key != key:
            # MM: centre reference from QQQ; make sure the disk sits at the same place
            mo = objmask(s["img"][v, rows[0]["slice"]])
            mc = objmask(cen_img)
            c1 = np.array(ndi.center_of_mass(mo))
            c2 = np.array(ndi.center_of_mass(mc))
            shift_note = dict(mask_centroid_shift_px=(c1 - c2).tolist())
        base_ghost = None
        if cen_rows:
            base_ghost = cen_rows[0]["ghost_frac"]
        elif ref_key != key:
            base_ghost = ghost_frac(cen_img, objmask(cen_img))
        for r in rows:
            sl = r["slice"]
            im = s["img"][v, sl]
            r["ghost_frac_centre_ref"] = base_ghost
            r["ghost_excess"] = (r["ghost_frac"] - base_ghost) if base_ghost is not None else None
            r["ghost_ratio_vs_centre"] = (r["ghost_frac"] / base_ghost) if base_ghost else None
            if not roi_ok:
                continue
            roi = pbs_roi(cen_img, masks[sl])
            bm, bp = band_metric(im, roi)
            bc, _ = band_metric(cen_img, roi)
            r["band_cv"], r["band_ptp"], r["band_cv_centre"] = bm, bp, bc
            r["band_excess"] = float(np.sqrt(max(bm ** 2 - bc ** 2, 0.0))) if not r["centre"] else 0.0
            r["roi_px"] = int(roi.sum())
            # nav-driven simulation: apply the measured echo-by-echo complex ratio (off-centre / centre) to the centre k-space
            if not r["centre"]:
                cs = data[ref_key]
                cvol = v if ref_key == key else 0
                nav_c = cs["navs"][cvol, ci]
                nav_o = s["navs"][v, sl]
                g = echo_ratio(nav_o) / echo_ratio(nav_c)
                kc = cs["kspace"][cvol, ci]
                eor = echo_of_row(cs)
                sim = recon_mag(kc * g[eor][:, None])
                bs, _ = band_metric(sim, roi)
                r["band_excess_pred"] = float(np.sqrt(max(bs ** 2 - bc ** 2, 0.0)))
                r["ghost_excess_pred"] = ghost_frac(sim, masks[sl]) - ghost_frac(cen_img, objmask(cen_img))
                sims[(key, sl)] = sim
            else:
                r["band_excess_pred"] = 0.0
                r["ghost_excess_pred"] = 0.0
        if shift_note:
            for r in rows:
                r["note"] = f"centre reference from {ref_key}; {shift_note}"
    return sims


# =============================================================================================== 4. phcal solver + alternation
def phcal_section():
    scans = {k: opc.analyse_scan(opc.read_scan(L.mrd_path(k))) for k in ("D", "E", "F", "G")}
    cal = opc.calibrate([scans[k] for k in ("E", "F", "G")])
    return scans, cal


def alternation_vs_phcal(scans, cal):
    """Per +-1.2 mm slice: unwrapped (continuity) ramp and alternation vs phcal for E/F/G; linear h(P) fit; where is each zero."""
    out = {}
    sigma = cal["sign_sigma"]
    for z in (-1.2, 1.2):
        P, S_, H_ = [], [], []
        for k in ("E", "F", "G"):
            sc = scans[k]
            sl = next(x for x in sc["slices"] if abs(x["z_mm"] - z) < 0.05)
            pz = cal["per_slice"][round(z, 3)] if round(z, 3) in cal["per_slice"] else cal["per_slice"][str(round(z, 3))]
            kk = 360.0 * pz["f_hz"] * 1e-7
            sphys = pz["s0"] + sigma * kk * sc["phcal"]
            c = [(sl["s"], sl["h"]), (sl["alias_s"], sl["alias_h"])]
            s_, h_ = min(c, key=lambda t: abs(float(wrap180(t[0] - sphys))))
            P.append(float(sc["phcal"])); S_.append(float(s_)); H_.append(float(h_))
        P, S_, H_ = map(np.array, (P, S_, H_))
        o_ = np.argsort(P)
        P, S_, H_ = P[o_], S_[o_], H_[o_]
        kk = 360.0 * (z * 2130.0) * 1e-7
        b, a = np.polyfit(P, H_, 1)
        hres = H_ - (a + b * P)
        # model for the ramp: exact line s0 + sigma*k*P with s0 from the solver
        s0 = cal["per_slice"][round(z, 3)]["s0"] if round(z, 3) in cal["per_slice"] else cal["per_slice"][str(round(z, 3))]["s0"]
        grid = np.arange(-1000, 1501)
        s_grid = s0 + sigma * kk * grid
        s_grid = wrap180(s_grid)
        h_grid_lin = a + b * grid
        # piecewise-linear interpolation through the three measured points (extrapolate linearly outside)
        h_grid_pw = np.interp(grid, P, H_, left=np.nan, right=np.nan)
        out[f"{z:+.1f}"] = dict(P=P, ramp_unwrapped=S_, alt=H_, k_deg_per_echo_per_tick=kk, linear_fit_alt=dict(slope_deg_per_tick=b, intercept=a, resid=hres),
                                P_ramp_zero=float(-s0 / (sigma * kk)),
                                P_alt_zero_linear=float(-a / b) if b else None,
                                alt_at_540_linear=float(a + b * 540), alt_at_540_piecewise=float(np.interp(540, P, H_)),
                                ramp_at_540=float(wrap180(s0 + sigma * kk * 540)),
                                P_range_ramp_pass=[float(grid[np.abs(s_grid) <= PASS].min()), float(grid[np.abs(s_grid) <= PASS].max())])
    # P minimising the worst normalised error over both slices, using the piecewise (interpolated) h and exact s
    grid = np.arange(0, 1001)
    worst = np.zeros(len(grid))
    for zs, v in out.items():
        z = float(zs)
        s0 = cal["per_slice"][round(z, 3)]["s0"] if round(z, 3) in cal["per_slice"] else cal["per_slice"][str(round(z, 3))]["s0"]
        s_g = np.abs(wrap180(s0 + sigma * v["k_deg_per_echo_per_tick"] * grid))
        h_g = np.abs(np.interp(grid, v["P"], v["alt"]))
        worst = np.maximum(worst, np.maximum(s_g, h_g))
    j = int(np.argmin(worst))
    out["best_P_minimax_over_0_1000_ticks"] = dict(P=int(grid[j]), worst_of_ramp_and_alt_deg=float(worst[j]),
                                                   note="interpolated through only three phcal values (-530, 0, +530) per slice, so +-50 ticks")
    return out


# =============================================================================================== 5. mode-0 alternation vs z
def alt_vs_z_fit(rows, label):
    """Descriptive fit h(z) = a*z modulo 90 deg (ramp-0 / ramp-180 alias) using the |ramp|<=90 representation of each slice."""
    pts = [(r["z_mm"], r["alt_low"], r["fit_rms_deg"]) for r in rows if not r["centre"]]
    if len(pts) < 3:
        return None
    z = np.array([p[0] for p in pts]); h = np.array([p[1] for p in pts])
    best = None
    for a in np.arange(0, 30.001, 0.05):
        res = ((h - a * z + 45.0) % 90.0) - 45.0
        sse = float(np.sum(res ** 2))
        if best is None or sse < best[0]:
            best = (sse, a, res)
    sse, a, res = best
    best180 = min(((float(np.sum((((h - a2 * z + 90.0) % 180.0) - 90.0) ** 2)), a2) for a2 in np.arange(0, 30.001, 0.05)))
    # local scan of the mod-90 SSE, to show how sharply a is determined
    sse_grid = []
    for a2 in np.arange(0, 30.001, 0.05):
        r2 = ((h - a2 * z + 45.0) % 90.0) - 45.0
        sse_grid.append(float(np.sum(r2 ** 2)))
    sse_grid = np.array(sse_grid)
    agrid = np.arange(0, 30.001, 0.05)
    near = agrid[sse_grid <= sse + 90.0 * 0 + len(h) * 4.0 ** 2]   # within 4 deg rms-equivalent
    return dict(label=label, n_points=len(h), slope_deg_per_mm_mod90=float(a), rms_resid_deg=float(np.sqrt(sse / len(h))),
                slope_range_within_rms4=[float(near.min()), float(near.max())],
                slope_deg_per_mm_mod180=float(best180[1]), rms_resid_mod180_deg=float(np.sqrt(best180[0] / len(h))),
                implied_timing_us_at_2130Hz_per_mm=float(a / (360.0 * 2130.0) * 1e6),
                points=[dict(z=float(zz), h=float(hh), resid=float(rr)) for zz, hh, rr in zip(z, h, res)])


# =============================================================================================== figures
CAT_STYLE = {
    "ex vivo v1.83 mode 0": dict(c="#2a78d6", m="o"),
    "ex vivo v1.83 mode 1": dict(c="#eb6834", m="s"),
    "ex vivo v1.912": dict(c="#1baf7a", m="D"),
    "in vivo v1.83 mode 0": dict(c="#4a3aa7", m="p"),
    "in vivo v1.912": dict(c="#52514e", m="H"),
}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#dcdcd8"


def style_ax(ax):
    ax.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.xaxis.label.set_color(INK2)
    ax.yaxis.label.set_color(INK2)


def fig_echo_phase(fits, scans_tool, out):
    import matplotlib.pyplot as plt
    keys = ["D", "E", "F", "G"]
    fig, axs = plt.subplots(1, 4, figsize=(17, 5.3), sharey=True)
    colours = {-1.2: "#2a78d6", 0.0: "#52514e", 1.2: "#eb6834"}
    for ax, k in zip(axs, keys):
        rows = [r for r in fits[k] if r["primary_b10"]]
        for r in sorted(rows, key=lambda r: r["z_mm"]):
            z = round(r["z_mm"], 1)
            e = np.arange(1, r["etl"] + 1)
            ip = np.array(r["ip_deg"])
            col = colours[z]
            ax.plot(e, ip, "o", color=col, ms=5, mec="white", mew=0.8, zorder=3)
            s_, h_ = r["ramp_plot"], r["alt_plot"]
            resid = np.radians(ip) - np.radians(s_ * (e - 1) + h_ * (-1.0) ** e)
            a0 = np.degrees(np.angle(np.exp(1j * resid).mean()))
            model = wrap180(a0 + s_ * (e - 1) + h_ * (-1.0) ** e)
            xs, ys = [e[0]], [model[0]]
            for i in range(1, len(e)):
                if abs(model[i] - model[i - 1]) > 180:
                    xs.append(np.nan); ys.append(np.nan)
                xs.append(e[i]); ys.append(model[i])
            ax.plot(xs, ys, "--", color=col, lw=1.2, zorder=2,
                    label=f"z {z:+.1f} mm: s {s_:+.1f}, h {h_:+.1f}" if abs(z) > 0.05 else f"z 0 (centre): s {s_:+.1f}, h {h_:+.1f}")
        r0 = rows[0]
        title = f"{k}: " + ("mode 0 (vendor / v1.81 scheme)" if r0["phmode"] == 0 else f"mode 1 (v1.82 gated), phcal {r0['phcal']:+d}")
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        ax.set_xlabel("echo number")
        ax.set_ylim(-190, 190); ax.set_yticks(range(-180, 181, 90)); ax.set_xticks(range(1, 9))
        ax.axhspan(-PASS, PASS, color="#1baf7a", alpha=0.10, lw=0)
        ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.17), frameon=False, labelcolor=INK2)
        style_ax(ax)
    axs[0].set_ylabel("navigator echo phase vs echo 1 (deg, wrapped)")
    fig.suptitle("Navigator echo phase per slice, b10, ex vivo, ETL 8. Dashed: ramp+alternation fit (s deg/echo, h deg). Green band: +-5 deg",
                 fontsize=10, color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out, dpi=130, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def fig_ramp_vs_z(fits, out):
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 3, figsize=(17, 5.2))
    seen = set()
    mark_mode1 = {0: "s", 530: "^", -530: "v"}
    for k in FIT_KEYS + CENTRE_ONLY:
        for r in fits[k]:
            if not r["primary_b10"]:
                continue
            st = dict(CAT_STYLE[r["category"]])
            lab = r["category"]
            if r["category"] == "ex vivo v1.83 mode 1":
                st["m"] = mark_mode1.get(r["phcal"], "s")
                lab = f"ex vivo v1.83 mode 1 (phcal {r['phcal']:+d})"
            poor = (r["fit_rms_deg"] > 35) or (r["noise_sd_ramp"] > 5) or (r["noise_sd_alt"] > 10)
            hollow = bool(r["rep_ambiguous"])
            kw = dict(marker=st["m"], s=58, linewidths=1.5, zorder=3, alpha=0.3 if poor else 1.0)
            if hollow:
                kw.update(facecolors="white", edgecolors=st["c"])
            else:
                kw.update(color=st["c"], edgecolors="white")
            off_ = {"in vivo v1.83 mode 0": 0.07, "in vivo v1.912": 0.14, "ex vivo v1.912": -0.07}.get(r["category"], 0.0) if abs(r["z_mm"]) > 0.05 else 0.0
            zz = r["z_mm"] + off_
            amp = r["amp_ratio_vs_centre"]
            vals = [r["ramp_plot"], r["alt_plot"], amp]
            for ax, v in zip(axs, vals):
                if v is None:
                    continue
                ax.scatter([zz], [v], label=lab if (lab not in seen) else None, **kw)
            seen.add(lab)
    zz = np.linspace(-6, 6, 3)
    axs[0].plot(zz, 41.4 * zz, color="#c0392b", lw=1, ls=":", label="10-11 v1.82 (41.4 deg/echo/mm)")
    axs[0].set_ylim(-155, 155)
    for ax in axs[:2]:
        ax.axhspan(-PASS, PASS, color="#1baf7a", alpha=0.12, lw=0)
        ax.axhline(0, color=INK2, lw=0.6)
    axs[0].set_ylabel("ramp s (deg/echo), b10 volume")
    axs[1].set_ylabel("alternation h (deg), b10 volume")
    axs[1].set_ylim(-95, 95)
    axs[2].set_ylabel("(echo-last/echo-1 amplitude) / same ratio in centre slice")
    axs[2].set_ylim(0, 1.7)
    axs[2].axhline(1, color=INK2, lw=0.6)
    titles = ["Ramp vs slice offset", "Alternation vs slice offset", "Echo-train amplitude retention vs centre slice"]
    for ax, t_ in zip(axs, titles):
        ax.set_xlabel("slice offset z (mm)")
        ax.set_title(t_, fontsize=10, color=INK, loc="left")
        ax.set_xlim(-6.2, 6.2)
        style_ax(ax)
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=4, fontsize=8, frameon=False, labelcolor=INK2)
    fig.text(0.01, 0.005, "Hollow = ramp/alternation representation ambiguous (both |h| >= 30 deg; the |ramp|<=90 representation is plotted). Faded = poor fit "
             "(fit rms > 35 deg or noise sd large). E/F/G: representation continuous in phcal. Green band: +-5 deg pass limit. In-vivo / v1.912 markers offset in z by <=0.14 mm.",
             fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.10, 1, 1))
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)


def fig_strips(data, fits, out):
    import matplotlib.pyplot as plt
    rows_spec = [("D", "D  mode 0"), ("E", "E  mode 1, phcal 0"), ("F", "F  mode 1, phcal +530"), ("G", "G  mode 1, phcal -530"),
                 ("QQ", "QQ  mode 0, +-2.8 mm"), ("MM", "MM  mode 0, +2.8 mm"), ("Q1", "Q1  mode 0, 7 slices")]
    ncol = 7
    fig, axs = plt.subplots(len(rows_spec), ncol, figsize=(15.5, 2.35 * len(rows_spec)))
    for ax in axs.ravel():
        ax.axis("off")
    for i, (k, lab) in enumerate(rows_spec):
        s = data[k]
        frows = {r["slice"]: r for r in fits[k] if r["primary_b10"]}
        tiles = []
        if k == "MM":
            m = data["M"]
            ci = int(np.argmin(np.abs(m["offsets_mm"])))
            mrow = [r for r in fits["M"] if r["primary_b10"]][0]
            tiles.append((m["img"][0, ci], "M centre (reference scan)", mrow))
        for sl in range(s["S"]):
            tiles.append((s["img"][0, sl], None, frows[sl]))
        for j, (im, ttl, r) in enumerate(tiles):
            ax = axs[i, j]
            ax.axis("on")
            ax.imshow(im, cmap="gray", vmin=0, vmax=np.percentile(im, 99.5), interpolation="nearest")
            ax.set_xticks([]); ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_visible(False)
            ztxt = ttl or f"z {r['z_mm']:+.1f} mm"
            if r["centre"]:
                txt = f"{ztxt}\ncentre: s {r['ramp_plot']:+.1f}, h {r['alt_plot']:+.1f}"
            else:
                txt = f"{ztxt}\ns {r['ramp_plot']:+.0f}, h {r['alt_plot']:+.0f}"
                if r.get("band_excess") is not None:
                    txt += f", band {r['band_excess'] * 100:.1f}%"
            ax.set_title(txt, fontsize=8, color=INK, pad=2)
        axs[i, 0].text(-0.06, 0.5, lab, transform=axs[i, 0].transAxes, rotation=90, va="center", ha="right", fontsize=9, color=INK)
    fig.suptitle("b10 magnitude images, ex vivo brain in PBS, no navigator correction; each tile scaled to its own 99.5th percentile.\n"
                 "s = navigator ramp (deg/echo), h = alternation (deg), band = excess row-mean banding in uniform PBS "
                 "(std of detrended row means / mean, quadrature-subtracted vs the centre slice).",
                 fontsize=9.5, color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0.02, 0, 1, 0.955), h_pad=0.6, w_pad=0.2)
    fig.savefig(out, dpi=100, facecolor="white")
    plt.close(fig)


def fig_phcal(alt, cal, out):
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 2, figsize=(11.5, 4.4))
    colours = {"-1.2": "#2a78d6", "+1.2": "#eb6834"}
    grid = np.arange(-700, 1001)
    for zs, v in alt.items():
        if zs.startswith("best"):
            continue
        z = float(zs)
        c = colours[zs]
        k = v["k_deg_per_echo_per_tick"]
        s0 = cal["per_slice"][round(z, 3)]["s0"] if round(z, 3) in cal["per_slice"] else cal["per_slice"][str(round(z, 3))]["s0"]
        axs[0].plot(grid, s0 + cal["sign_sigma"] * k * grid, color=c, lw=1.2, ls="--")
        axs[0].plot(v["P"], v["ramp_unwrapped"], "o", color=c, ms=7, mec="white", label=f"z {z:+.1f} mm")
        axs[1].plot(v["P"], v["alt"], "o-", color=c, ms=7, mec="white", lw=1.2, label=f"z {z:+.1f} mm")
    for ax in axs:
        ax.axhspan(-PASS, PASS, color="#1baf7a", alpha=0.12, lw=0)
        ax.axhline(0, color=INK2, lw=0.6)
        ax.axvline(cal["recommended_phcal"], color="#c0392b", lw=1, ls=":")
        ax.set_xlabel("v183_phcal (0.1 us ticks), mode 1")
        ax.legend(fontsize=8, frameon=False, labelcolor=INK2, loc="lower right" if ax is axs[0] else "upper right")
        style_ax(ax)
    axs[0].set_ylabel("ramp s (deg/echo)")
    axs[1].set_ylabel("alternation h (deg)")
    p0s = [v["P0"] for v in cal["per_slice"].values()]
    axs[0].set_title(f"Ramp is zero at P0 = {p0s[0]:+.0f} / {p0s[1]:+.0f} ticks (tool recommends {cal['recommended_phcal']}, dotted)", fontsize=9.5, color=INK, loc="left")
    axs[1].set_title("Alternation (not modelled by the tool): lines join the 3 scans", fontsize=9.5, color=INK, loc="left")
    axs[0].set_ylim(-110, 110)
    fig.tight_layout()
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)


def fig_artefacts(fits, corr, out):
    import matplotlib.pyplot as plt
    pts = [r for k in EXVIVO_IMG for r in fits[k] if r["primary_b10"] and not r["centre"] and r.get("band_excess") is not None]
    fig, axs = plt.subplots(2, 3, figsize=(15.5, 8.2))
    spec = [("band_excess", "banding excess (std detrended row means / mean)", 0), ("ghost_excess", "ghost-energy excess outside mask+3 px (vs centre)", 1)]
    xs = [("|ramp| (deg/echo)", lambda r: abs(r["ramp_plot"])), ("|alternation| (deg)", lambda r: abs(r["alt_plot"])),
          ("nav-simulated prediction", None)]
    for (ycol, ylab, i) in spec:
        for j, (xl, fn) in enumerate(xs):
            ax = axs[i, j]
            for r in pts:
                st = CAT_STYLE[r["category"]]
                m = st["m"]
                if r["category"] == "ex vivo v1.83 mode 1":
                    m = {0: "s", 530: "^", -530: "v"}.get(r["phcal"], "s")
                x = fn(r) if fn else r[ycol + "_pred"]
                ax.scatter([x], [r[ycol]], color=st["c"], marker=m, s=44, edgecolors="white", linewidths=0.8, zorder=3)
            ax.set_xlabel(xl if fn else f"predicted {ycol.split('_')[0]} excess from navigator echo ratios")
            ax.set_ylabel(ylab, fontsize=8)
            c = corr[ycol]["vs_ramp" if j == 0 else ("vs_alt" if j == 1 else "vs_pred")]
            ax.set_title(f"Spearman rho {c['spearman_rho']:+.2f} (p {c['spearman_p']:.2g}), n {c['n']}", fontsize=9, color=INK, loc="left")
            style_ax(ax)
            if not fn:
                lim = max(max(r[ycol + "_pred"] for r in pts), max(r[ycol] for r in pts))
                ax.plot([0, lim], [0, lim], color=INK2, lw=0.7, ls=":")
    handles = []
    from matplotlib.lines import Line2D
    for lab, st in CAT_STYLE.items():
        if lab.startswith("ex vivo"):
            handles.append(Line2D([], [], marker=st["m"], color="none", markerfacecolor=st["c"], markeredgecolor="white", markersize=8, label=lab))
    for m, lab in ((("^", "mode 1 phcal +530")), (("v", "mode 1 phcal -530"))):
        handles.append(Line2D([], [], marker=m, color="none", markerfacecolor="#eb6834", markeredgecolor="white", markersize=8, label=lab))
    fig.legend(handles=handles, loc="lower center", ncol=5, fontsize=8, frameon=False, labelcolor=INK2)
    fig.suptitle("Off-centre ex-vivo slices (b10): image artefact vs navigator phase error. One point per slice; slices of a scan share conditions "
                 "(not independent)", fontsize=9.5, color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.05, 1, 0.96))
    fig.savefig(out, dpi=125, facecolor="white")
    plt.close(fig)


def fig_freq(freq, ab, out):
    import matplotlib.pyplot as plt
    a, b = ab
    fig, axs = plt.subplots(1, 3, figsize=(16, 4.6), gridspec_kw=dict(width_ratios=[1.2, 1.0, 1.2]))
    pa, pb = a.sum(0), b.sum(0)
    x = np.arange(len(pa))
    axs[0].plot(x, pa / pa.max(), color="#2a78d6", lw=1.3, label="A: 20 kHz")
    axs[0].plot(x, pb / pb.max(), color="#eb6834", lw=1.3, ls="--", label="B: 40 kHz")
    axs[0].set_xlabel("readout pixel")
    axs[0].set_ylabel("column-summed magnitude (norm.)")
    axs[0].set_title(f"A vs B readout projection: relative shift {freq['readout_px_relative']:+.2f} px = {freq['implied_df_hz']:+.0f} Hz", fontsize=9.5, color=INK, loc="left")
    axs[0].legend(fontsize=8, frameon=False)
    style_ax(axs[0])
    # sessions
    sess = [("10-10\nv1.81", 0.2), ("10-11\nv1.82", 9.1), ("10-12\nv1.83 (A/B)", abs(freq["readout_px_relative"]))]
    axs[1].bar(range(3), [v for _, v in sess], color=["#2a78d6", "#c0392b", "#2a78d6"], width=0.55)
    axs[1].axhline(0.5, color=INK2, ls=":", lw=1)
    axs[1].text(2.4, 0.7, "pass < 0.5 px", fontsize=8, color=INK2, ha="right")
    axs[1].set_xticks(range(3)); axs[1].set_xticklabels([s for s, _ in sess], fontsize=8)
    axs[1].set_ylim(0, 10.8)
    axs[1].set_ylabel("|20/40 kHz readout shift| (px)")
    for i, (_, v) in enumerate(sess):
        axs[1].text(i, v + 0.2, f"{v:.2f} px", ha="center", fontsize=8.5, color=INK)
    axs[1].set_title("Frequency check by session", fontsize=9.5, color=INK, loc="left")
    style_ax(axs[1])
    cr = freq["cross_version_registration"]
    lab = [f"{c['ref']} vs {c['moving']}" for c in cr]
    axs[2].barh(range(len(cr)), [c["read_px"] for c in cr], color="#52514e", height=0.5, label="readout")
    axs[2].barh(np.arange(len(cr)) + 0.3, [c["pe_px"] for c in cr], color="#9a9893", height=0.3, label="phase encode (motion control)")
    axs[2].set_yticks(range(len(cr))); axs[2].set_yticklabels(lab, fontsize=8)
    axs[2].invert_yaxis()
    axs[2].axvline(0, color=INK2, lw=0.6)
    axs[2].set_xlabel("registration shift (px, 40 kHz both; 1 px = 312.5 Hz)")
    axs[2].set_title("Same-FOV image registration across sequences/times", fontsize=9.5, color=INK, loc="left")
    axs[2].legend(fontsize=8, frameon=False, loc="upper left")
    style_ax(axs[2])
    fig.tight_layout()
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)


# =============================================================================================== main
def spearman(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 4:
        return dict(n=int(ok.sum()), spearman_rho=np.nan, spearman_p=np.nan, pearson_r=np.nan)
    rho, p = stats.spearmanr(x[ok], y[ok])
    r, _ = stats.pearsonr(x[ok], y[ok])
    return dict(n=int(ok.sum()), spearman_rho=float(rho), spearman_p=float(p), pearson_r=float(r))


def median_range(v):
    v = np.asarray(v, float)
    return dict(median=float(np.median(v)), min=float(v.min()), max=float(v.max()), n=int(len(v)))


def main():
    t0 = time.time()
    FIGDIR.mkdir(parents=True, exist_ok=True)
    keys = FIT_KEYS + CENTRE_ONLY
    data = {}
    for k in keys:
        data[k] = L.load(k)
        print(f"loaded {k} ({data[k]['version']}, {time.time() - t0:.0f} s)", flush=True)

    # ---- 1. frequency
    freq, ab = frequency_section(data)
    print(f"[freq] A/B readout shift {freq['readout_px_relative']:+.2f} px -> {freq['implied_df_hz']:+.0f} Hz {freq['verdict']}")
    for c in freq["cross_version_registration"]:
        print(f"       {c['ref']:>3} vs {c['moving']:<3}: readout {c['read_px']:+.2f} px ({c['df_equiv_hz']:+.0f} Hz), PE {c['pe_px']:+.2f} px  [{c['note']}]")

    # ---- 2. navigator fits
    fits = {}
    parity = 0.0
    for k in keys:
        rows, p = analyse_navigators(k, data[k])
        fits[k] = rows
        parity = max(parity, p)
    print(f"[fit] vectorised fit vs tool fit_ramp: max discrepancy {parity:.3f} (deg or deg-rms)")
    for k_, ref_ in CENTRE_REF.items():
        cr_ = [r for r in fits[ref_] if r["centre"] and r["primary_b10"]][0]["amp_last_over_first"]
        for r in fits[k_]:
            r["amp_ratio_vs_centre"] = r["amp_last_over_first"] / cr_

    scans_tool, cal = phcal_section()
    # tool parity on D,E,F,G: same numbers as the loader-based fits?
    par = 0.0
    for k in ("D", "E", "F", "G"):
        for r in scans_tool[k]["slices"]:
            mine = next(x for x in fits[k] if x["primary_b10"] and x["slice"] == r["slice"])
            par = max(par, abs(mine["ramp_deg_per_echo"] - r["s"]), abs(mine["alt_deg"] - r["h"]))
    print(f"[fit] loader-based fits vs CLI-style read_scan for D/E/F/G: max |diff| {par:.4f} deg")
    select_plot_rep([r for k in keys for r in fits[k]], cal)
    alt = alternation_vs_phcal(scans_tool, cal)

    # ---- 3. image metrics
    sims = image_metrics(data, fits)

    # ---- tables
    b10 = {k: [r for r in fits[k] if r["primary_b10"]] for k in keys}

    def off(k):
        return [r for r in b10[k] if not r["centre"]]

    corr = {}
    pts = [r for k in EXVIVO_IMG for r in off(k) if r.get("band_excess") is not None]
    for ycol in ("band_excess", "ghost_excess"):
        y = [r[ycol] for r in pts]
        corr[ycol] = dict(
            vs_ramp=spearman([abs(r["ramp_plot"]) for r in pts], y),
            vs_alt=spearman([abs(r["alt_plot"]) for r in pts], y),
            vs_phase_dev=spearman([r["phase_dev_deg"] for r in pts], y),
            vs_amp_loss=spearman([1 - r["amp_ratio_vs_centre"] for r in pts], y),
            vs_abs_z=spearman([abs(r["z_mm"]) for r in pts], y),
            vs_pred=spearman([r[ycol + "_pred"] for r in pts], y),
        )
    # ramp/alt at fixed |z| = 1.2 only (D,E,F,G): phase error varies 0..98 deg/echo at fixed z
    p12 = [r for r in pts if abs(abs(r["z_mm"]) - 1.2) < 0.05]
    corr["at_abs_z_1p2_only"] = {
        yc: dict(vs_ramp=spearman([abs(r["ramp_plot"]) for r in p12], [r[yc] for r in p12]),
                 vs_alt=spearman([abs(r["alt_plot"]) for r in p12], [r[yc] for r in p12]),
                 vs_phase_dev=spearman([r["phase_dev_deg"] for r in p12], [r[yc] for r in p12])) for yc in ("band_excess", "ghost_excess")}
    corr["n_slices"] = len(pts)
    # fit in vivo: ghost only
    pts_iv = [r for k in ("iA", "iD", "iE", "iF", "iB") for r in off(k)]
    corr["in_vivo_ghost_excess"] = dict(
        vs_alt=spearman([abs(r["alt_plot"]) for r in pts_iv], [r["ghost_excess"] for r in pts_iv]),
        vs_ramp=spearman([abs(r["ramp_plot"]) for r in pts_iv], [r["ghost_excess"] for r in pts_iv]),
        vs_abs_z=spearman([abs(r["z_mm"]) for r in pts_iv], [r["ghost_excess"] for r in pts_iv]),
        note="surface-coil images: mask = threshold of the head+coil profile; ghost fraction only, no banding metric")

    # ---- figures
    fig_echo_phase(fits, scans_tool, FIGDIR / "phasecal_echo_phase_DEFG.png")
    fig_ramp_vs_z(fits, FIGDIR / "phasecal_ramp_vs_offset.png")
    fig_strips(data, fits, FIGDIR / "phasecal_image_strips.png")
    fig_phcal(alt, cal, FIGDIR / "phasecal_phcal_scan_pm1p2mm.png")
    fig_artefacts(fits, corr, FIGDIR / "phasecal_artefact_vs_phase.png")
    fig_freq(freq, ab, FIGDIR / "freq_check_AB.png")

    # ---- summaries for JSON
    def slim(r):
        keep = ["z_mm", "ramp_deg_per_echo", "alt_deg", "alias_ramp", "alias_alt", "ramp_plot", "alt_plot", "ramp_low", "alt_low", "rep_ambiguous",
                "fit_rms_deg", "noise_sd_ramp", "noise_sd_alt", "ramp_ss", "alt_ss", "rms_ss", "ss_offset_deg", "amp_last_over_first", "amp_ratio_vs_centre", "phase_dev_deg", "verdict_tool",
                "verdict_either_rep", "band_cv", "band_excess", "band_excess_pred", "ghost_frac", "ghost_excess", "ghost_excess_pred"]
        return {k_: r.get(k_) for k_ in keep}

    per_scan = {}
    for k in keys:
        r0 = b10[k][0]
        sl = sorted(b10[k], key=lambda r: r["z_mm"])
        offs = [r for r in sl if not r["centre"]]
        per_scan[k] = dict(category=r0["category"], version=r0["version"], phmode=r0["phmode"], phcal=r0["phcal"], tr_ms=r0["tr_ms"], etl=r0["etl"],
                           rx_gain=r0["rx_gain"], b=r0["b"], slices=[slim(r) for r in sl],
                           all_offcentre_pass_tool=(all(r["verdict_tool"] == "PASS" for r in offs) if offs else None),
                           all_offcentre_pass_either_rep=(all(r["verdict_either_rep"] == "PASS" for r in offs) if offs else None),
                           max_abs_ramp_offcentre=(max(abs(r["ramp_plot"]) for r in offs) if offs else None),
                           max_abs_alt_offcentre=(max(abs(r["alt_plot"]) for r in offs) if offs else None))

    # ramp per mm (tool-reported s/z, only meaningful where |s| small or mode-1 / v1.912 with clean alternation)
    ramp_per_mm = {}
    for k in ("E", "G", "R", "iB"):
        v = [r["ramp_plot"] / r["z_mm"] for r in off(k) if abs(r["alt_plot"]) < 30]
        if v:
            ramp_per_mm[k] = dict(values=v, mean=float(np.mean(v)))
    r_e = [r["ramp_plot"] / r["z_mm"] for r in off("E")]
    r_f = [r["ramp_plot"] / r["z_mm"] for r in off("F")]

    # all b>10 volumes: aggregate per (scan, |z|) in plot-rep... use ramp (tool canonical -> low rep for |h|>=30) and alt_min
    agg = []
    for k in keys:
        zs = sorted({round(abs(r["z_mm"]), 2) for r in fits[k]})
        for z in zs:
            sel = [r for r in fits[k] if abs(abs(r["z_mm"]) - z) < 0.01]
            for grp, f in (("b<=20", lambda r: r["b"] <= 20), ("b>20", lambda r: r["b"] > 20)):
                ss = [r for r in sel if f(r)]
                if not ss:
                    continue
                # alternation signed in +z convention (h * sign(z)) in the |ramp|<=90 representation
                hs = [r["alt_low"] * (1 if r["z_mm"] > 0 else -1) for r in ss]
                agg.append(dict(scan=k, abs_z=z, group=grp, n_fits=len(ss), ramp_low_median=float(np.median([r["ramp_low"] * (1 if r["z_mm"] >= 0 else -1) for r in ss])),
                                ramp_low_abs_max=float(max(abs(r["ramp_low"]) for r in ss)),
                                alt_low_signed_median=float(np.median(hs)), alt_min_median=float(np.median([r["alt_min_any_rep"] for r in ss])),
                                rms_median=float(np.median([r["fit_rms_deg"] for r in ss])),
                                amp_last_over_first_median=float(np.median([r["amp_last_over_first"] for r in ss]))))
    # mode 0 alternation vs z
    ex_m0 = [r for k in ("D", "QQ", "QQQ", "Q", "MM", "Q1") for r in off(k)]
    iv_m0 = [r for k in ("iA", "iD", "iE", "iF") for r in off(k) if r["fit_rms_deg"] <= 25]
    alt_z = dict(ex_vivo_mode0=alt_vs_z_fit(ex_m0, "ex vivo v1.83 mode 0 (D, QQ, QQQ, Q, MM, Q1; b10)"),
                 in_vivo_mode0=alt_vs_z_fit(iv_m0, "in vivo v1.83 mode 0 (iA, iD, iE, iF; b10, fit rms <= 25 deg)"))
    # scan-to-scan repeatability of mode 0 at +-2.8 (low-ramp rep, sign-folded to +z)
    rep28 = {}
    for zsign in (-2.8, 2.8):
        v = []
        for k in ("QQ", "QQQ", "Q", "MM"):
            for r in off(k):
                if abs(r["z_mm"] - zsign) < 0.05:
                    v.append((k, round(r["alt_low"], 1), round(r["ramp_low"], 1)))
        rep28[f"{zsign:+.1f}"] = v

    centre = {}
    for k in keys:
        cs = [r for r in fits[k] if r["centre"]]
        if not cs:
            centre[k] = None          # MM: single off-centre slice, no centre slice in the scan
            continue
        pc = [r for r in cs if r["primary_b10"]][0]
        hi = [r for r in cs if not r["primary_b10"] and r["b"] > 20]
        centre[k] = dict(b10=dict(s=pc["ramp_deg_per_echo"], h=pc["alt_deg"], rms=pc["fit_rms_deg"], amp_last_over_first=pc["amp_last_over_first"],
                                  clean=bool(abs(pc["ramp_deg_per_echo"]) <= PASS and abs(pc["alt_deg"]) <= PASS)),
                         higher_b=(dict(n=len(hi), max_abs_s=max(abs(r["ramp_deg_per_echo"]) for r in hi), max_abs_h=max(abs(r["alt_deg"]) for r in hi),
                                        n_clean=sum(1 for r in hi if abs(r["ramp_deg_per_echo"]) <= PASS and abs(r["alt_deg"]) <= PASS)) if hi else None))

    # centre-slice repeatability (noise floor of s and h across scans of the same kind)
    rep = {}
    for lab, ks in (("ex vivo v1.83 (D,E,F,G,QQ,QQQ,Q,Q1,M,A,B; nav mode 1)", ["D", "E", "F", "G", "QQ", "QQQ", "Q", "Q1", "M", "A", "B"]),
                    ("ex vivo v1.912 (R,C,O)", ["R", "C", "O"]), ("in vivo v1.83 (iA,iD,iE,iF)", ["iA", "iD", "iE", "iF"]),
                    ("in vivo v1.912 (iB,iC)", ["iB", "iC"])):
        cs_ = [[r for r in b10[k] if r["centre"]][0] for k in ks]
        rep[lab] = dict(n=len(cs_), s_mean=float(np.mean([r["ramp_deg_per_echo"] for r in cs_])), s_sd=float(np.std([r["ramp_deg_per_echo"] for r in cs_], ddof=1)),
                        s_range=[float(min(r["ramp_deg_per_echo"] for r in cs_)), float(max(r["ramp_deg_per_echo"] for r in cs_))],
                        h_mean=float(np.mean([r["alt_deg"] for r in cs_])), h_sd=float(np.std([r["alt_deg"] for r in cs_], ddof=1)),
                        h_range=[float(min(r["alt_deg"] for r in cs_)), float(max(r["alt_deg"] for r in cs_))],
                        ss_offset_range=[float(min(r["ss_offset_deg"] for r in cs_)), float(max(r["ss_offset_deg"] for r in cs_))])
    # ex vivo vs in vivo, mode 0, by |z| (b10; ramp/alternation in the |ramp|<=90 representation, sign-folded to +z)
    evi = {}
    for z in (1.2, 2.8, 4.0, 5.2):
        d = {}
        for lab, ks in (("ex_vivo", ["D", "QQ", "QQQ", "Q", "MM", "Q1"]), ("in_vivo_all", ["iA", "iD", "iE", "iF"])):
            rs = [r for k in ks for r in off(k) if abs(abs(r["z_mm"]) - z) < 0.05]
            if not rs:
                continue
            sg = [1.0 if r["z_mm"] > 0 else -1.0 for r in rs]
            d[lab] = dict(n=len(rs), ramp_low_median=float(np.median([a * r["ramp_low"] for a, r in zip(sg, rs)])),
                          ramp_low_abs_max=float(max(abs(r["ramp_low"]) for r in rs)),
                          alt_low_signed_median=float(np.median([a * r["alt_low"] for a, r in zip(sg, rs)])),
                          alt_low_abs_median=float(np.median([abs(r["alt_low"]) for r in rs])),
                          alt_low_abs_range=[float(min(abs(r["alt_low"]) for r in rs)), float(max(abs(r["alt_low"]) for r in rs))],
                          amp_vs_centre_median=float(np.median([r["amp_ratio_vs_centre"] for r in rs])),
                          fit_rms_median=float(np.median([r["fit_rms_deg"] for r in rs])),
                          ss_offset_abs_median=float(np.median([abs(r["ss_offset_deg"]) for r in rs])))
        rs_ok = [r for k in ("iA", "iD", "iE", "iF") for r in off(k) if abs(abs(r["z_mm"]) - z) < 0.05 and r["fit_rms_deg"] <= 25]
        if rs_ok:
            d["in_vivo_rms_le_25"] = dict(n=len(rs_ok), alt_low_abs_median=float(np.median([abs(r["alt_low"]) for r in rs_ok])),
                                          alt_low_abs_range=[float(min(abs(r["alt_low"]) for r in rs_ok)), float(max(abs(r["alt_low"]) for r in rs_ok))],
                                          ramp_low_abs_max=float(max(abs(r["ramp_low"]) for r in rs_ok)))
        evi[f"{z:.1f}"] = d
    # ramp tolerance of a phcal error at each geometry
    tol = {f"{z:.1f}": dict(deg_per_echo_per_tick=360 * z * 2130 * 1e-7, ticks_for_5deg=5.0 / (360 * z * 2130 * 1e-7)) for z in (1.2, 2.8, 4.0, 5.2)}

    summary = dict(
        generated=time.strftime("%Y-%m-%d %H:%M"), script="docs/data/oct12_phase_calibration.py",
        criteria=dict(ramp_deg_per_echo=PASS, alternation_deg=PASS, source="docs/v183/CALIBRATION.md"),
        fit_method=dict(model="phi_e = c + s*(e-1) + h*(-1)^e", tool="tools/offcentre_phase_cal.py fit_ramp/analyse_scan (imported)",
                        vectorised_fit_max_discrepancy=parity, uncertainty="parametric Monte Carlo noise, 100 draws per fit (statistical only; tiny). Systematic spread: see centre_slice_repeatability and mode0_repeatability_pm2p8",
                        alias_note="(s,h) == (s+-180, h+-90); tool reports smaller |h|; rep_ambiguous = both |h| >= 30"),
        frequency_check=freq,
        phcal_solver_E_F_G=dict(tool_output=cal, per_scan={k: [dict(z=r["z_mm"], s=r["s"], h=r["h"], rms=r["rms_deg"], alias_s=r["alias_s"], alias_h=r["alias_h"], verdict=r["verdict"])
                                                              for r in scans_tool[k]["slices"]] for k in ("D", "E", "F", "G")}),
        alternation_vs_phcal_pm1p2=alt,
        per_scan_b10=per_scan,
        ramp_per_mm=dict(E_mode1_phcal0_deg_per_echo_per_mm=r_e, F_mode1_phcal530=r_f, others=ramp_per_mm, ref_10_11_v182=41.0),
        aggregated_all_volumes=agg,
        mode0_alternation_vs_z=alt_z,
        mode0_repeatability_pm2p8=rep28,
        centre_slice=centre,
        centre_slice_repeatability=rep,
        exvivo_vs_invivo_mode0_by_abs_z=evi,
        phcal_tolerance_for_5deg_ramp=tol,
        artefacts=dict(correlation=corr, metric_definitions=dict(
            band_cv="std of 3rd-order-detrended row means over a uniform-PBS ROI / mean; band_excess = sqrt(band_cv^2 - band_cv_centre^2) of the same scan's centre slice",
            ghost_frac="sum |I|^2 outside (object mask dilated 3 px) / total; ghost_excess = off-centre minus centre of the same scan",
            band_excess_pred="same metric on the centre-slice k-space multiplied by the off-centre/centre navigator echo ratio (complex, per echo) -> predicted from navigator only",
            phase_dev="rms deviation of echo 2..N phases from their circular mean (representation-free)",
            mm_reference="MM has no centre slice: ROI/baseline from QQQ centre")),
        figures=sorted(p.name for p in FIGDIR.glob("*.png") if p.name.startswith(("phasecal_", "freq_"))),
        runtime_s=time.time() - t0)
    JSON_OUT.write_text(json.dumps(clean(summary), indent=1))

    # ---- CSV
    cols = ["scan", "folder", "version", "subject", "category", "phmode", "phcal", "etl", "tr_ms", "esp_ms", "rx_gain", "volume", "b", "primary_b10", "slice", "z_mm", "centre",
            "f_hz_nominal", "ramp_deg_per_echo", "alt_deg", "alias_ramp", "alias_alt", "ramp_low", "alt_low", "alt_min_any_rep", "rep_ambiguous", "ramp_plot", "alt_plot",
            "fit_rms_deg", "noise_sd_ramp", "noise_sd_alt", "snr_last_echo", "ramp_ss", "alt_ss", "rms_ss", "ss_offset_deg", "tau_us_nominal", "ramp_per_mm", "amp_last_over_first", "amp_ratio_vs_centre", "phase_dev_deg",
            "verdict_tool", "verdict_either_rep", "ghost_frac", "ghost_excess", "ghost_ratio_vs_centre", "band_cv", "band_cv_centre", "band_excess", "band_ptp",
            "band_excess_pred", "ghost_excess_pred", "mask_area_px", "roi_px", "note"]
    with open(CSV_OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for k in keys:
            for r in fits[k]:
                row = {c: (round(r[c], 4) if isinstance(r.get(c), float) else r.get(c)) for c in cols}
                w.writerow(row)
    print(f"wrote {CSV_OUT.name}, {JSON_OUT.name}, {len(summary['figures'])} figures in {FIGDIR.relative_to(ROOT)}  ({time.time() - t0:.0f} s)")
    return summary, fits, data, cal, alt


if __name__ == "__main__":
    main()
