"""Forensic checks for the 2026-10-11 ss-MGOT (v1.911 / v1.912) scans that returned noise.

Run from the repository root:  python docs/data/oct11_ssmgot_forensics.py
Writes docs/data/oct11_ssmgot_forensics.json. Reads MRDs, PPL/PPR files and RF libraries only.

Conventions: image[row, col] as in oct11_load; slice 0 only; noise = complex rms of the outer
readout samples (first/last 16) of the outer k-space rows (first/last 16), per volume, median
over volumes. "rms" ratios are complex rms over readout samples divided by that noise.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import oct11_load as O  # noqa: E402  (header_text, var, get_mrd_3d4, ns, ROOT, EXP)
from oct05_protocol_audit import parse_mrd, stable_equal  # noqa: E402

ROOT, EXP = O.ROOT, O.EXP
sys.path.insert(0, str(ROOT))
from dwfse.vendor_seq import decode  # noqa: E402

OUT = HERE / "oct11_ssmgot_forensics.json"

FOLDERS = {
    "11_A_v182": "FSE-DWI_10-11-2026_v182_testA",
    "11_C_v182": "FSE-DWI_10-11-2026_v182_testC",
    "11_TT_v182": "FSE-DWI_10-11-2026_v182_testTT",
    "11_0_v1911": "FSE-DWI_10-11-2026_v1911_test0",
    "11_B_v1912": "FSE-DWI_10-11-2026_v1912_testB",
    "11_N_v1912": "FSE-DWI_10-11-2026_v1912_testN",
    "11_U_v1912": "FSE-DWI_10-11-2026_v1912_testU",
    "11_UU_v1912": "FSE-DWI_10-11-2026_v1912_testUU",
    "10_A_v181": "FSE-DWI_10-10-2026_v181_testA",
    "10_D_v191": "FSE-DWI_10-10-2026_v191_testD",
    "10_B_v1911": "FSE-DWI_10-10-2026_v1911_testB",
    "10_G_v1911": "FSE-DWI_10-10-2026_v1911_testG",
    "10_I_v1911": "FSE-DWI_10-10-2026_v1911_testI",
}
PAIRS = [("10_I_v1911", "11_0_v1911"), ("10_B_v1911", "11_B_v1912"),
         ("11_A_v182", "11_B_v1912"), ("10_A_v181", "11_A_v182")]
SIGNAL_SCANS_11 = ["11_A_v182", "11_C_v182", "11_TT_v182", "11_0_v1911", "11_B_v1912",
                   "11_N_v1912", "11_U_v1912", "11_UU_v1912"]
SIGNAL_SCANS_10 = ["10_I_v1911", "10_B_v1911", "10_G_v1911", "10_D_v191", "10_A_v181"]
REF_MASK_SCAN = "11_A_v182"


def rms(x):
    return float(np.sqrt(np.mean(np.abs(x) ** 2)))


def scale(a, b, c):
    """Assumed PPL scale(a,b,c) = a*b/c with integer division (exact rounding rule not in repo)."""
    return (int(a) * int(b)) // int(c)


def load(name):
    folder = EXP / FOLDERS[name]
    mrd = next(folder.glob("*.MRD"))
    _, text = O.header_text(mrd)
    raw, dims, params = O.get_mrd_3d4(mrd)
    raw = raw[:, 0, :, 0]                        # (E, S, V, nsamp)
    E, S, V, nsamp = dims[0], dims[2], dims[4], dims[5]
    L = int(O.var(text, "views_per_seg", params["views_per_seg"]))
    nav = int(O.var(text, "nav_on", 0))
    N = V - nav * L
    pe = int(O.var(text, "PE_order"))
    rows = O.ns["pe_rows"](N, L, pe)
    kspace = np.zeros((E, S, N, nsamp), complex)
    navs = np.zeros((E, S, L, nsamp), complex)
    for e in range(E):
        for s in range(S):
            kspace[e, s, rows] = raw[e, s, nav * L:]
            if nav:
                navs[e, s] = raw[e, s, :L]
    k0 = kspace[:, 0]
    img = np.abs(np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(k0, axes=(-2, -1)), axes=(-2, -1)),
                                 axes=(-2, -1)))
    parsed = parse_mrd(mrd)
    n = int(O.var(text, "no_diff_acq", E))
    b = O.ns["ppr_array"](text, "acq_b")[:n]
    return dict(name=name, folder=str(folder), mrd=mrd, E=E, N=N, L=L, nav=nav, nsamp=nsamp,
                rows=rows, kspace=kspace, navs=navs, img=img, b=b, parsed=parsed,
                raw_abs_max=float(np.abs(raw[:, 0]).max()))


def sigma_noise(d, w=16):
    N, ns_ = d["N"], d["nsamp"]
    r = np.r_[0:w, N - w:N]
    c = np.r_[0:w, ns_ - w:ns_]
    x = d["kspace"][:, 0][:, r][:, :, c]
    per_vol = np.sqrt(np.mean(np.abs(x) ** 2, axis=(1, 2)))
    return float(np.median(per_vol)), [float(v) for v in per_vol]


def object_mask(d_ref, b_target):
    e = int(np.argmin(np.abs(d_ref["b"] - b_target)))
    im = d_ref["img"][e]
    return im > 0.3 * np.percentile(im, 99), e


def signal_metrics(d, sigma, mask):
    E, L, N, ns_ = d["E"], d["L"], d["N"], d["nsamp"]
    out = {"b": [float(x) for x in d["b"]], "sigma_complex_rms": sigma}
    out["raw_absmax_over_sigma"] = d["raw_abs_max"] / sigma
    if d["nav"]:
        out["nav_rms_over_sigma"] = [[rms(d["navs"][e, 0, m]) / sigma for m in range(L)] for e in range(E)]
    cc = slice(N // 2 - 4, N // 2 + 4)
    cs = slice(ns_ // 2 - 4, ns_ // 2 + 4)
    out["kcentre_rms_over_sigma"] = [rms(d["kspace"][e, 0, cc, cs]) / sigma for e in range(E)]
    echo_rows = [d["rows"][(np.arange(N) % L) == m] for m in range(L)]
    out["kecho_rms_over_sigma"] = [[rms(d["kspace"][e, 0][rr][:, ns_ // 2 - 32:ns_ // 2 + 32]) / sigma
                                    for rr in echo_rows] for e in range(E)]
    snr, con = [], []
    for e in range(E):
        sm = gaussian_filter(d["img"][e], sigma=3, mode="nearest")
        inside, outside = sm[mask], sm[~mask]
        snr.append(float(inside.mean() / outside.std()))
        con.append(float(inside.mean() / outside.mean()))
    out["image_snr_like"] = snr
    out["image_contrast_in_over_out"] = con
    return out


def diff_pair(a, b):
    ra, rb = a["parsed"]["records"], b["parsed"]["records"]
    va, vb = a["parsed"]["values"], b["parsed"]["values"]
    rec = []
    for k in sorted(set(ra) | set(rb)):
        x = " ".join(str(ra.get(k, "<absent>")).split())
        y = " ".join(str(rb.get(k, "<absent>")).split())
        if x != y:
            rec.append({"key": k, "a": x, "b": y})
    val = []
    for k in sorted(set(va) | set(vb)):
        x, y = va.get(k, "<absent>"), vb.get(k, "<absent>")
        if not stable_equal(x, y):
            val.append({"key": k, "a": x, "b": y})
    return {"records_differing": rec, "values_differing": val,
            "n_records_differing": len(rec), "n_values_differing": len(val)}


def overlap_fraction(df_hz, p, img):
    """Rectangular model. Slice centre shift dz = df * width / B. Returns overlap fraction of img slice."""
    dz_p = df_hz * p["w_mm"] / p["B_Hz"]
    dz_i = df_hz * img["w_mm"] / img["B_Hz"]
    half_p = p["w_mm"] / 2 + p.get("margin_mm", 0.0)
    half_i = img["w_mm"] / 2
    lo = max(dz_p - half_p, dz_i - half_i)
    hi = min(dz_p + half_p, dz_i + half_i)
    return max(0.0, hi - lo) / (2 * half_i)


def first_zero_overlap_hz(p, img):
    for df in range(0, 6001, 5):
        if overlap_fraction(df, p, img) <= 0:
            return df
    return None


def hashes_in_docs(hexdigest):
    hits = []
    for path in (ROOT / "docs").rglob("*"):
        if path.suffix.lower() not in (".md", ".json", ".txt", ".py", ".csv"):
            continue
        try:
            if hexdigest in path.read_text(encoding="utf-8", errors="ignore"):
                hits.append(path.relative_to(ROOT).as_posix())
        except OSError:
            pass
    return hits[:12]


def main():
    data = {k: load(k) for k in FOLDERS}
    results = {}

    # ---- Check 1: full embedded-record diffs
    results["check1_embedded_record_diffs"] = {f"{a} vs {b}": diff_pair(data[a], data[b])
                                              for a, b in PAIRS}

    # ---- Check 2: noise
    sig = {k: sigma_noise(data[k]) for k in FOLDERS}
    results["check2_noise"] = {
        k: {"dwell_us": float(data[k]["parsed"]["values"].get("sample_period", [0, 0, 0, 0])[-1]),
            "rx_gain": data[k]["parsed"]["values"].get("_ObserveReceiverGain"),
            "tx_gain": data[k]["parsed"]["values"].get("_ObserveTransmitGain"),
            "sigma_complex_rms_median": sig[k][0], "sigma_per_volume": sig[k][1]}
        for k in FOLDERS}

    # ---- Check 3/4: signal metrics. Masks: A b10 (11-10 ss-MGOT), TT b10 for UU, own b0 for 10-10.
    mask_a, e_a = object_mask(data[REF_MASK_SCAN], 10)
    mask_tt, _ = object_mask(data["11_TT_v182"], 10)
    results["check3_signal"] = {}
    for k in SIGNAL_SCANS_11 + SIGNAL_SCANS_10:
        if k == "11_UU_v1912":
            mask, src = mask_tt, "TT b10 (v182 testTT) mask"
        elif k.startswith("10_"):
            mask, _ = object_mask(data[k], 0)
            src = "own b0 volume mask (10-10 water)"
        else:
            mask, src = mask_a, f"A b10 volume (index {e_a}) mask"
        results["check3_signal"][k] = {"mask_source": src, "mask_fraction": float(mask.mean()),
                                       **signal_metrics(data[k], sig[k][0], mask)}
    results["check3_signal"]["_note"] = (
        "nav_rms_over_sigma: complex rms over readout of navigator echo m (1..L) divided by noise; "
        "kecho: rms over rows acquired at echo m, centre 64 readout samples; image_snr_like = mean of "
        "gaussian(sigma=3) magnitude inside mask / std outside mask.")

    # ---- Check 5: TX gain text search and RF pulse peak analysis
    tx_hits = []
    for base in [ROOT / "scanner", ROOT / "docs", ROOT / "dwfse", ROOT / "examples"]:
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in (".ppl", ".ppr", ".pph", ".py", ".md", ".txt", ".json"):
                continue
            if "docs/data" in p.as_posix() or "experiments" in p.as_posix():
                continue
            try:
                txt = p.read_text(encoding="latin1", errors="ignore")
            except OSError:
                continue
            for m in re.finditer(r"TransmitGain|tx_gain|TX gain|Tx attenuation|transmit gain", txt, re.I):
                line_no = txt.count("\n", 0, m.start()) + 1
                tx_hits.append(f"{p.relative_to(ROOT).as_posix()}:{line_no}")
    results["check5_tx_gain_search_hits"] = tx_hits[:40]
    results["check5_tx_gain_search_total_hits"] = len(tx_hits)

    frames = {}
    for f in sorted((ROOT / "scanner" / "rf").glob("v19_*.seq")):
        for fr in decode(f).frames:
            frames[fr.name] = fr.samples.astype(float)
    stock = decode(ROOT / "scanner" / "utilities" / "rfstd44.seq")
    stock_frame = [fr for fr in stock.frames if fr.name == "3lobe_sinc_3kHz"][0].samples.astype(float)
    frames["3lobe_sinc_3kHz"] = stock_frame

    bvals = data["11_B_v1912"]["parsed"]["values"]
    rfcal = int(bvals["rfcal"]); alpha = int(bvals["alpha"]); p180s = int(bvals["p180_scale"])
    flips = [int(x) for x in bvals["v19_flip_tenths"][:8]]
    pulses = [
        dict(name="v182 excitation 90 (rfnum 1)", frame="3lobe_sinc_3kHz", dur_us=1332, B_Hz=3000,
             w_mm=1.0, mul=scale(rfcal, alpha, 90), role="v1.82 exc"),
        dict(name="v182 refocus 180 (rfnum 1, same shape)", frame="3lobe_sinc_3kHz", dur_us=1332,
             B_Hz=3000, w_mm=1.0 * float(bvals["slab_ratio"]) / 100.0,
             mul=scale(rfcal, p180s, 100), role="v1.82 refocus/diffusion 180"),
        dict(name="v19 slrprep90", frame="v19_slrprep90", dur_us=3200, B_Hz=1109, w_mm=3.0,
             margin_mm=0.690, mul=scale(rfcal, 3436, 10000), role="prep90"),
        dict(name="v19 slrprep180", frame="v19_slrprep180", dur_us=3200, B_Hz=1109, w_mm=3.0,
             margin_mm=0.327, mul=scale(rfcal, 11509, 10000), role="prep180"),
        dict(name="v19 slrtip90", frame="v19_slrtip90", dur_us=3200, B_Hz=1109, w_mm=1.667,
             margin_mm=0.450, mul=scale(rfcal, 3761, 10000), role="tip-up 90"),
        dict(name="v19 reexc90", frame="v19_reexc90", dur_us=1200, B_Hz=1283, w_mm=1.0,
             mul=scale(rfcal, 5392, 10000), role="re-excitation 90 (imaging slice)"),
    ]
    for i, fl in enumerate(flips):
        pulses.append(dict(name=f"v19 imaging180 echo {i + 1} (flip {fl / 10:.1f} deg)",
                           frame="v19_imaging180", dur_us=1200, B_Hz=1283, w_mm=1.0,
                           mul=scale(rfcal, scale(10783, fl, 1800), 10000), role="train refocus 180"))
    ref_frame = frames["3lobe_sinc_3kHz"]
    ref_area = pulses[0]["mul"] * ref_frame.sum() * (pulses[0]["dur_us"] / len(ref_frame)) / 2047
    ref_energy_tr = None
    rf_rows = []
    for p in pulses:
        fr = frames[p["frame"]]
        dt = p["dur_us"] / len(fr)
        area = p["mul"] * fr.sum() * dt / 2047
        energy = (p["mul"] / 2047) ** 2 * (fr ** 2).sum() * dt
        rf_rows.append(dict(name=p["name"], role=p["role"], mul=p["mul"], peak_frame_dac=float(np.abs(fr).max()),
                            peak_drive_mul=float(p["mul"] * np.abs(fr).max() / 2047),
                            headroom_to_2047=2047 / p["mul"], flip_proxy_vs_v182_90=area / ref_area,
                            energy_us_rel=energy, dwell_us=dt, duration_us=p["dur_us"], B_Hz=p["B_Hz"],
                            w_mm=p["w_mm"]))
    v182_energy = (rf_rows[0]["energy_us_rel"] + 8 * rf_rows[1]["energy_us_rel"])
    v19_energy = (rf_rows[2]["energy_us_rel"] + rf_rows[3]["energy_us_rel"] + rf_rows[4]["energy_us_rel"]
                  + rf_rows[5]["energy_us_rel"] + sum(r["energy_us_rel"] for r in rf_rows[6:]))
    results["check5_rf_pulses"] = {
        "header": {"rfcal": rfcal, "alpha": alpha, "p180_scale": p180s, "rfnum": bvals.get("rfnum"),
                   "slab_ratio_percent": bvals.get("slab_ratio"), "v19_slab_pml": bvals.get("v19_slab_pml"),
                   "v19_tip_pml": bvals.get("v19_tip_pml"), "v19_flip_tenths_first8": flips,
                   "_ObserveTransmitGain_11": data["11_B_v1912"]["parsed"]["values"].get("_ObserveTransmitGain"),
                   "_ObserveTransmitGain_10": data["10_B_v1911"]["parsed"]["values"].get("_ObserveTransmitGain")},
        "pulses": rf_rows,
        "tr_energy_rel_v182_90_units": {"v182_exc_plus_8_refocus": v182_energy, "v19_prep_tip_reexc_8_imaging": v19_energy,
                                        "ratio_v19_over_v182": v19_energy / v182_energy},
        "clip_note": ("Frames are all normalized to peak 2047, so peak drive = mul. Largest mul: "
                      f"{max(rf_rows, key=lambda r: r['mul'])['name']} = {max(r['mul'] for r in rf_rows)}. "
                      "TX gain units not defined in repo; relative amplitude per 74 units unknown."),
    }

    # ---- Check 6: hashes
    expect = {
        "FSE_dwi_CPMG_non_CPMG_twoTE-1.912.ppl": "07b202660258a5c6843ffb88c4b2bfe630261a36d4d64d5b7f02594839444423",
        "FSE_dwi_CPMG_non_CPMG_twoTE-1.912.ppr": "11aca86556f0cfa1c4b51f2b60615c79e320b14b37f460b7718c4c35d458f554",
        "FSE_dwi_CPMG_non_CPMG_twoTE-1.82.ppl": "7257c4b2cada0e293b973402c0b897f57a47be6e6c36a592c2b04fe34aad133e",
        "FSE_dwi_CPMG_non_CPMG_twoTE-1.82.ppr": "44474269a39ebaa8efed9526000413dd4f8372082f520e890e005ffa8fd4f84b",
        "FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl": "716478bb357ba1479e6cc8fcc18c1085e44b3c78ecf1bdf32bb561b171838682",
        "FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppr": "b2976e7464367a7aa6b6b8e04765cc04a3fd85c0d2ec64c9c9a57963bf9635c2",
        "FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl": "545a14ec8c65ed578ea76628796547dd463eb8cd4a2efa680de89058a837de69",
        "FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl": "92bdcb79081087c29dd045cd797cb8fbdd1e4f02ff4f341b9711eef706f16e4f",
        "v7 ss-MGOT baseline PPL (docs/v181_v1911/baseline_v7)": "6a0d222b6c8689fbdee5f4ae412c4d5df0bea10a7da99a309fabf5dfab04d828",
    }
    h6 = {}
    for fname, want in expect.items():
        if fname.startswith("v7"):
            path = ROOT / "docs/v181_v1911/baseline_v7" / "FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl"
            if not path.exists():
                hits = sorted((ROOT / "docs/v181_v1911/baseline_v7").glob("*.ppl"))
                path = hits[0] if hits else None
        else:
            path = ROOT / "scanner" / fname
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path and path.exists() else None
        h6[fname] = {"expected": want, "scanner_file_sha256": actual,
                     "match": actual == want,
                     "docs_mentioning_expected_hash": hashes_in_docs(want)}
    results["check6_hashes"] = h6
    results["check6_embedded_ppl_paths"] = {k: data[k]["parsed"]["values"].get("PPL") for k in FOLDERS}
    results["check6_shim_string_count_in_mrd"] = {
        k: int(len(re.findall(rb"shim", data[k]["mrd"].read_bytes(), re.I))) for k in FOLDERS}

    # ---- Frequency-offset check (lead-analyst request): df = +/- 2830 Hz
    DF = 2830.0
    img = dict(name="v19 reexc90 / imaging180 (imaging slice)", w_mm=1.0, B_Hz=1283)
    v19_defs = [
        dict(name="v19 slrprep90", w_mm=3.0, B_Hz=1109, margin5=0.690, margin1=2.627),
        dict(name="v19 slrprep180", w_mm=3.0, B_Hz=1109, margin5=0.327, margin1=0.517),
        dict(name="v19 slrtip90", w_mm=1.667, B_Hz=1109, margin5=0.450, margin1=1.187),
    ]
    v182_def = dict(name="v182 exc90 (rfnum 1)", w_mm=1.0, B_Hz=3000)
    v182_ref = dict(name="v182 refocus180 (rfnum 1)", w_mm=1.0 * float(bvals["slab_ratio"]) / 100.0, B_Hz=3000)
    freq = {"df_Hz": DF, "pulses": []}
    for pdef in v19_defs:
        for label, m in (("5pct", pdef["margin5"]), ("1pct", pdef["margin1"])):
            p = dict(w_mm=pdef["w_mm"], B_Hz=pdef["B_Hz"], margin_mm=m)
            freq["pulses"].append(dict(
                pulse=pdef["name"], profile_margin=label,
                dz_mm_relative_to_own_df=DF * pdef["w_mm"] / pdef["B_Hz"],
                dz_imaging_slice_mm=DF * img["w_mm"] / img["B_Hz"],
                relative_offset_mm=DF * pdef["w_mm"] / pdef["B_Hz"] - DF * img["w_mm"] / img["B_Hz"],
                overlap_fraction_of_imaging_slice=overlap_fraction(DF, p, img),
                overlap_fraction_at_minus_df=overlap_fraction(-DF, p, img),
                df_Hz_where_overlap_vanishes_positive=first_zero_overlap_hz(p, img)))
    # v1.82: excitation and refocus both 3 kHz, 1 mm (slab_ratio 100) -> same shift
    p_v182 = dict(w_mm=v182_ref["w_mm"], B_Hz=v182_ref["B_Hz"])
    img_v182 = dict(w_mm=v182_def["w_mm"], B_Hz=v182_def["B_Hz"])
    freq["v182"] = {
        "exc_shift_mm": DF * 1.0 / 3000.0, "refocus_shift_mm": DF * v182_ref["w_mm"] / 3000.0,
        "relative_shift_mm": DF * (v182_ref["w_mm"] - 1.0) / 3000.0,
        "overlap_refocus_with_exc_slice": overlap_fraction(DF, p_v182, img_v182),
        "df_Hz_threshold_none": None,
    }
    freq["v19_imaging_shift_mm"] = DF * 1.0 / 1283.0
    freq["v19_reexc_vs_prep_relative_mm_range"] = [DF * 3.0 / 1109 - DF / 1283, DF * 1.667 / 1109 - DF / 1283]
    freq["note"] = ("dz = df*w/B; B is the nominal integer PPL bandwidth (1109 / 1283 Hz, handoff: exact "
                    "1109.375 / 1283.333). Imaging slice assumed 1 mm (reexc/imaging, B 1283). Overlap is a rectangular "
                    "model; profile margins from docs/v182_v1912/validation/rf_margin.md added per side.")
    results["check7_frequency_offset_slices"] = freq

    # ---- Summaries to stdout
    print("Noise (complex rms, median over volumes) by scan:")
    for k in FOLDERS:
        r = results["check2_noise"][k]
        print(f"  {k:14s} RX {r['rx_gain']:>5} TX {r['tx_gain']:>5} dwell {r['dwell_us']:>4} "
              f"sigma {r['sigma_complex_rms_median']:.4g}")
    print("Check 1 differing-record counts:")
    for pk, pv in results["check1_embedded_record_diffs"].items():
        print(f"  {pk}: records {pv['n_records_differing']}, values {pv['n_values_differing']}")
    print("Check 7 overlap at df=+2830 Hz (fraction of 1 mm imaging slice):")
    for pr in freq["pulses"]:
        print(f"  {pr['pulse']:16s} {pr['profile_margin']}: dz_rel {pr['relative_offset_mm']:+.2f} mm, "
              f"overlap {pr['overlap_fraction_of_imaging_slice']:.2f}, zero-overlap df {pr['df_Hz_where_overlap_vanishes_positive']} Hz")
    print(f"  v182 exc shift {freq['v182']['exc_shift_mm']:.2f} mm, relative exc-refocus {freq['v182']['relative_shift_mm']:.2f} mm,"
          f" refocus-exc overlap {freq['v182']['overlap_refocus_with_exc_slice']:.2f}")
    print(f"  TR energy ratio v19/v182: {results['check5_rf_pulses']['tr_energy_rel_v182_90_units']['ratio_v19_over_v182']:.2f}")

    OUT.write_text(json.dumps(results, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)),
                   encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
