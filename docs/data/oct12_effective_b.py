"""Effective b-matrices for the acquired 2026-10-12 FSE MRD scans (source model; no calibration).

Run from anywhere:  python docs/data/oct12_effective_b.py
Outputs: docs/data/oct12_effective_b.csv, docs/data/oct12_effective_b.json

Adapted from docs/data/oct11_effective_b.py. Inputs are read-only: the embedded protocol text of each
scan's MRD (bytes from b':PPL', via oct12_load.header_text); nothing is written under experiments/.

Echo 1 (centric k-space centre) goes through the public scanner/recon/effective_b.effective_b with
pe_order=1, exactly as the reconstruction does. Echoes 2..ETL (and, for nav_on=2, echo ETL+1 = the
unencoded per-shot navigator echo) call the same private eb._model routine with the echo index.
The model is the instantaneous-RF primary pathway (v1.83) or the carrier/conjugate branch pick (v1.912);
it is not calibrated or measured, and echo >1 values are source-model predictions.

The model's imaging view count must be the true imaging view count N (raw views minus the volume
navigator train): feeding the raw count (136 instead of 128) makes the event model produce no ADC
echoes and the public effective_b silently falls back to nominal. N is derived as in oct12_load.load.

Extras (clearly labelled in the JSON, not part of the Oct 11 recipe):
  * model_b10_same_direction: the model run for a hypothetical b=10 volume along each direction used by
    the b>10 volumes, so b_eff(b)-b_eff(b10) can be formed along the same axis even when the acquired b10
    volume lies along a different axis (M, N, O, Q, Q1, R, iA, iB, iC...).
  * v1.83 vs v1.912 and TE44/D30 vs TE54/D40 comparisons at matched nominal b and direction.
  * nominal Stejskal-Tanner reference for the lab EPI protocols (typed b; EPI imaging cross terms not modelled).
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "scanner/recon"))
sys.path.insert(0, str(ROOT))
import oct12_load as L  # noqa: E402
import effective_b as eb  # noqa: E402
from bare_bones_recon_fse import read_diffusion, ppr_array  # noqa: E402
from dwfse.ppl.ppr import read_ppr  # noqa: E402

OUT = HERE
NAMES = "xyz"
COMP = ("bxx", "byy", "bzz", "bxy", "bxz", "byz")
OFFDIAG = ("bxy", "bxz", "byz")
EPI_DELTA_MS, EPI_BIG_DELTA_MS = 4.0, 30.0
GAMMA = 2.6752218744e8   # rad s^-1 T^-1 (1H)


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def ppr_params(protocol):
    with tempfile.TemporaryDirectory(prefix="oct12_beff_") as directory:
        path = Path(directory) / "embedded.ppr"
        path.write_text(protocol, encoding="latin-1")
        params, _ = read_ppr(path)
    return params


def dlabel(vec):
    vec = np.asarray(vec, float)
    if not np.any(vec):
        return "0"
    nz = np.flatnonzero(np.abs(vec) > 1e-9)
    if len(nz) == 1:
        return ("+" if vec[nz[0]] > 0 else "-") + NAMES[nz[0]]
    return "(" + ",".join(f"{c:+.3f}" for c in vec) + ")"


def set_leading(protocol, name, values):
    """Overwrite the first len(values) entries of VAR_ARRAY `name`, keeping the text layout."""
    m = re.search(rf"(:VAR_ARRAY\s+{name},\s*\d+,)(.*?)(?=\r?\n:|\Z)", protocol, re.S | re.I)
    body, counter = m[2], [0]

    def sub(match):
        i = counter[0]
        counter[0] += 1
        return str(int(values[i])) if i < len(values) else match[0]

    return protocol[:m.start(2)] + re.sub(r"-?\d+(?:\.\d+)?", sub, body) + protocol[m.end(2):]


def valid_matrices(mats, n):
    mats = np.asarray(mats, dtype=float)
    if not (mats.shape == (n, 3, 3) and np.all(np.isfinite(mats)) and np.allclose(mats, mats.transpose(0, 2, 1))):
        raise ValueError("invalid b-matrix table")
    return mats


def process_scan(key):
    """Worker: all model runs for one scan. Returns plain python data."""
    t0 = time.perf_counter()
    s = L.load(key, recon=False)                       # read-only header/geometry metadata
    mrd = s["mrd"]
    data, protocol = L.header_text(mrd)
    params = ppr_params(protocol)
    diff = read_diffusion(protocol)
    n_steps = diff["n"]
    nvol = int(params["no_experiments"])
    nav, vps, raw = int(params["nav_on"]), int(params["views_per_seg"]), int(params["no_views"])
    etl = vps - 1 if nav == 2 else vps
    n_img = (raw // (etl + 1) - 1) * etl if nav == 2 else raw - (etl if nav == 1 else 0)
    assert n_img == s["N"] and etl == s["L"], (key, n_img, s["N"], etl, s["L"])
    raw_dir = np.stack([ppr_array(protocol, "acq_" + a)[:n_steps] for a in NAMES], 1).astype(float)
    norms = np.linalg.norm(raw_dir, axis=1)
    unit = np.where(norms[:, None] > 0, raw_dir / np.maximum(norms, 1e-12)[:, None], 0.0)
    nominal = np.asarray(diff["b"], float) if diff["b"] is not None else None
    if nominal is None:
        raise ValueError(f"{key}: DAC-entered b not expected for these scans")

    # Echo 1 through the public entry point.
    res = eb.effective_b(protocol, diff, nvol, n_img, 1)
    ppl_path, ppl_version = eb.resolve_ppl(protocol)
    ppl_hash = sha_bytes(ppl_path.read_bytes())
    src1 = res["BMatrixSource"]
    model_ok = src1.startswith("event")
    warn1 = [w for w in res["BMatrixWarnings"] if w.startswith("Effective-b model unavailable")]
    branches = res["BMatrixModel"].get("Branches", []) if model_ok else []
    shots = res["BMatrixModel"].get("RepresentativeImagingShotIndex", []) if model_ok else []
    step = np.arange(nvol) % n_steps
    mats_by_echo = {1: [np.asarray(res["BMatrix"][v], float) for v in range(nvol)]}   # component vectors
    status = {1: src1 + (" | " + warn1[0] if warn1 else "")}

    # Echoes 2..(ETL, or ETL+1 incl. the unencoded navigator echo for nav_on=2).
    n_echo_max = etl + (1 if nav == 2 else 0)
    if model_ok:
        for echo in range(2, n_echo_max + 1):
            try:
                out = eb._model(ppl_path, protocol, diff, n_img, echo)
                mats = valid_matrices(out["matrices"], n_steps)
                mats_by_echo[echo] = [np.asarray(eb.components(mats[step[v]]), float) for v in range(nvol)]
                status[echo] = "ok"
            except Exception as exc:
                status[echo] = f"failed: {type(exc).__name__}: {exc}"
                break
    else:
        status["2+"] = "not attempted (echo 1 fell back to nominal)"

    # Extra: model b=10 along every direction used in the scan (echo 1). The directions are written into the
    # leading entries of the protocol arrays; the array length (no_diff_acq) is left unchanged because the
    # event model rejects shortened arrays. The acquired b10 direction doubles as a self-check.
    cf = {}
    if model_ok:
        dirs = []
        for i in range(n_steps):
            if not any(np.allclose(unit[i], d) for d in dirs):
                dirs.append(unit[i])
        dirs = [d for d in dirs if np.any(d)]
        if dirs:
            rows = [(10, *np.rint(d * 1000).astype(int)) for d in dirs]
            proto2 = protocol
            for j, name in enumerate(("acq_b", "acq_x", "acq_y", "acq_z")):
                proto2 = set_leading(proto2, name, [r[j] for r in rows])
            try:
                out = eb._model(ppl_path, proto2, diff, n_img, 1)
                mats = valid_matrices(out["matrices"], n_steps)
                for d, m in zip(dirs, mats):
                    cf[dlabel(d)] = dict(trace=float(np.trace(m)), components=[float(c) for c in eb.components(m)])
            except Exception as exc:
                cf = {"error": f"{type(exc).__name__}: {exc}"}

    meta = dict(
        scan=key, folder=s["folder"].name, version=f"v{ppl_version}", ppl=str(ppl_path.relative_to(ROOT)),
        ppl_sha256=ppl_hash, protocol_sha256=sha_bytes(protocol.encode("latin-1")), mrd_sha256=s["mrd_sha256"],
        sample="in-vivo (surface coil)" if key.startswith("i") else "ex-vivo (volume coil)",
        nav_on=nav, etl=etl, views_per_segment_stored=vps, raw_views=raw, imaging_views=n_img,
        volumes=nvol, diffusion_steps=n_steps, slices=s["S"], offsets_mm=s["offsets_mm"],
        te_ms=s["te"], esp_ms=s["esp"], big_delta_ms=s["big_delta_ms"], small_delta_ms=s["small_delta_ms"],
        dwell_us=s["dwell_us"], n_samples=s["nsamp"], fov_mm=s["fov_mm"], thickness_mm=s["thickness_mm"],
        pe_order_in_protocol=s["pe"], v183_phmode=s["phmode"], v183_phcal=s["phcal"],
        echo_status={str(k): v for k, v in status.items()},
        runtime_seconds=round(time.perf_counter() - t0, 2),
    )
    return dict(meta=meta, unit=unit.tolist(), raw_dir=raw_dir.tolist(), nominal=nominal.tolist(),
                step=step.tolist(), mats={e: [m.tolist() for m in v] for e, v in mats_by_echo.items()},
                branches=branches, shots=shots, model_ok=model_ok, warn=warn1[0] if warn1 else "",
                counterfactual_b10=cf, n_echo_max=n_echo_max)


def echo_note(meta, echo):
    if meta["nav_on"] == 2 and echo == meta["etl"] + 1:
        return "unencoded per-shot navigator echo (nav_on=2); not an imaging echo"
    if echo == 1:
        return "echo 1 = k-space centre (centric) of first imaging shot"
    return f"echo {echo} of the imaging train (source model, not used for reconstruction)"


def main():
    started = time.perf_counter()
    keys = list(L.SCANS)
    missing = [k for k in keys if L.mrd_path(k) is None]
    if missing:
        raise SystemExit(f"no MRD for {missing}")
    print(f"{len(keys)} FSE scans", flush=True)
    results = {}
    with ProcessPoolExecutor(max_workers=12) as pool:
        futures = {k: pool.submit(process_scan, k) for k in keys}
        for k in keys:
            try:
                results[k] = futures[k].result()
                m = results[k]["meta"]
                print(f"{k:>4} {m['version']:>6} nav={m['nav_on']} etl={m['etl']} vols={m['volumes']} "
                      f"echo1={'model' if results[k]['model_ok'] else 'NOMINAL-FALLBACK'} "
                      f"echoes={sorted(int(e) for e in results[k]['mats'])[-1]} {m['runtime_seconds']}s", flush=True)
            except Exception as exc:   # whole-scan failure: record and fall back to nominal, flagged
                print(f"{k:>4} FAILED: {type(exc).__name__}: {exc}", flush=True)
                results[k] = dict(error=f"{type(exc).__name__}: {exc}")

    csv_rows, scans_json, failures = [], {}, []
    for k in keys:
        r = results[k]
        if "error" in r:
            failures.append(dict(scan=k, error=r["error"], handling="no rows: scan could not be processed"))
            scans_json[k] = dict(error=r["error"])
            continue
        meta, unit, nominal, step = r["meta"], np.asarray(r["unit"]), np.asarray(r["nominal"]), r["step"]
        nvol = meta["volumes"]
        echoes = sorted(r["mats"])
        src = "model" if r["model_ok"] else "nominal-fallback"
        if not r["model_ok"]:
            failures.append(dict(scan=k, error=r["warn"], handling="echo 1 = nominal b * u u^T (flagged nominal-fallback)"))
        for echo in echoes:
            for v in range(nvol):
                comp = r["mats"][echo][v]
                st = step[v]
                trace = comp[0] + comp[1] + comp[2]
                notes = [echo_note(meta, echo), "source model only (instantaneous-RF primary pathway, no calibration)"]
                if r["model_ok"] and echo == 1:
                    notes.append(f"branch={r['branches'][st]}; representative shot={r['shots'][st]}")
                if not r["model_ok"]:
                    notes = [f"NOMINAL FALLBACK (b * u u^T): {r['warn']}"]
                notes.append("same for all slices (slice offset only changes frequency/phase)")
                csv_rows.append(dict(
                    scan=k, folder=meta["folder"], version=meta["version"], sample=meta["sample"],
                    volume=v + 1, echo=echo, nominal_b_s_mm2=float(nominal[st]),
                    dir_x=float(unit[st][0]), dir_y=float(unit[st][1]), dir_z=float(unit[st][2]),
                    direction=dlabel(unit[st]),
                    **{n: float(c) for n, c in zip(COMP, comp)}, trace_s_mm2=float(trace),
                    source=src, branch=r["branches"][st] if (r["model_ok"] and echo == 1) else "",
                    te_ms=meta["te_ms"], esp_ms=meta["esp_ms"], big_delta_ms=meta["big_delta_ms"],
                    small_delta_ms=meta["small_delta_ms"], etl=meta["etl"], nav_on=meta["nav_on"],
                    notes="; ".join(notes)))

        # --- per-scan summary (echo 1) ---
        vols = []
        for v in range(nvol):
            st = step[v]
            comp = r["mats"][1][v]
            off = {n: comp[3 + i] for i, n in enumerate(OFFDIAG)}
            big = max(off, key=lambda n: abs(off[n]))
            trace = comp[0] + comp[1] + comp[2]
            vols.append(dict(
                volume=v + 1, nominal_b=float(nominal[st]), direction=dlabel(unit[st]),
                direction_vector=[float(c) for c in unit[st]],
                components=dict(zip(COMP, map(float, comp))), trace=float(trace),
                trace_minus_nominal=float(trace - nominal[st]),
                largest_offdiagonal=dict(term=big, value=float(off[big]),
                                         fraction_of_trace=float(abs(off[big]) / trace) if trace else None),
                trace_by_echo={str(e): float(sum(r["mats"][e][v][:3])) for e in echoes}))
        b10 = [x for x in vols if abs(x["nominal_b"] - 10) < 1e-6]
        cf = r["counterfactual_b10"]
        diffs = []
        for x in vols:
            if x["nominal_b"] <= 10 + 1e-6:
                continue
            same = [q for q in b10 if q["direction"] == x["direction"]]
            ref, flag = (same[0], "same-direction b10 volume") if same else (
                (b10[0], "b10 reference lies along a different direction (not a valid ADC denominator)") if b10
                else (None, "no b10 volume"))
            d = dict(volume=x["volume"], nominal_b=x["nominal_b"], direction=x["direction"],
                     trace=x["trace"], reference_b10_volume=ref["volume"] if ref else None,
                     reference_direction=ref["direction"] if ref else None, reference_note=flag,
                     b_eff_difference=x["trace"] - ref["trace"] if ref else None,
                     nominal_difference=x["nominal_b"] - 10.0,
                     ratio_effective_to_nominal=(x["trace"] - ref["trace"]) / (x["nominal_b"] - 10.0) if ref else None)
            cfd = cf.get(x["direction"]) if isinstance(cf, dict) else None
            if cfd:
                d["model_b10_same_direction_trace"] = cfd["trace"]
                d["b_eff_difference_vs_model_same_direction_b10"] = x["trace"] - cfd["trace"]
                d["ratio_vs_model_same_direction_b10"] = (x["trace"] - cfd["trace"]) / (x["nominal_b"] - 10.0)
            diffs.append(d)
        self_check = [dict(volume=q["volume"], direction=q["direction"],
                           acquired_trace=q["trace"], rerun_trace=cf[q["direction"]]["trace"],
                           abs_diff=abs(q["trace"] - cf[q["direction"]]["trace"]))
                      for q in b10 if isinstance(cf, dict) and q["direction"] in cf]
        allo = sorted(((abs(x["components"][n]), n, x) for x in vols for n in OFFDIAG), key=lambda t: -t[0])
        largest = [dict(term=n, value=x["components"][n], volume=x["volume"], nominal_b=x["nominal_b"],
                        direction=x["direction"], fraction_of_trace=abs(x["components"][n]) / x["trace"])
                   for _, n, x in allo[:3]]
        scans_json[k] = dict(
            **meta, echo1_source=src, echo1_branches=r["branches"], model_b10_same_direction=cf,
            model_b10_self_check=self_check,
            b10_volume=[dict(volume=q["volume"], direction=q["direction"], nominal_b=q["nominal_b"],
                             trace=q["trace"], components=q["components"]) for q in b10],
            trace_difference_vs_nominal=diffs, largest_offdiagonal_terms=largest, volumes_table=vols)

    # ---------------------------------------------------------------- comparisons
    ok = {k: scans_json[k] for k in keys if "error" not in scans_json[k] and scans_json[k]["echo1_source"] == "model"}
    CLASS_FIELDS = ("etl", "te_ms", "esp_ms", "big_delta_ms", "small_delta_ms", "dwell_us", "n_samples",
                    "imaging_views", "fov_mm", "thickness_mm")

    def class_of(m):
        return tuple(m[f] for f in CLASS_FIELDS)

    def entry(items):
        """items: list of (scan, volume dict) sharing nominal b + direction."""
        tr = [v["trace"] for _, v in items]
        off = [max(abs(v["components"][n]) for n in OFFDIAG) for _, v in items]
        return dict(scans=[s for s, _ in items], trace_min=min(tr), trace_max=max(tr), trace=float(np.mean(tr)),
                    max_abs_offdiag=float(np.mean(off)),
                    bzz=float(np.mean([v["components"]["bzz"] for _, v in items])),
                    bxx=float(np.mean([v["components"]["bxx"] for _, v in items])),
                    byy=float(np.mean([v["components"]["byy"] for _, v in items])))

    def collect(keyset):
        out = {}
        for k in keyset:
            m = ok[k]
            for v in m["volumes_table"]:
                out.setdefault((round(v["nominal_b"], 6), v["direction"]), []).append((k, v))
        return out

    def matched_rows(a_items, b_items):
        rows = []
        for kk in sorted(a_items, key=lambda t: (t[0], t[1])):
            if kk in b_items:
                ea, eb_ = entry(a_items[kk]), entry(b_items[kk])
                rows.append(dict(nominal_b=kk[0], direction=kk[1], a=ea, b=eb_,
                                 trace_b_minus_a=eb_["trace"] - ea["trace"],
                                 rel_diff_percent=100 * (eb_["trace"] - ea["trace"]) / ea["trace"]))
        return rows

    classes = {}
    for k, m in ok.items():
        classes.setdefault(class_of(m), {}).setdefault(m["version"], []).append(k)
    cmp_83_912 = []
    for cls, byver in classes.items():
        desc = dict(zip(CLASS_FIELDS, cls))
        if "v1.83" in byver and "v1.912" in byver:
            rows = matched_rows(collect(byver["v1.83"]), collect(byver["v1.912"]))
            cmp_83_912.append(dict(
                protocol_class=desc, scans_v183=byver["v1.83"], scans_v1912=byver["v1.912"],
                nav_on_v183=sorted({ok[s]["nav_on"] for s in byver["v1.83"]}),
                nav_on_v1912=sorted({ok[s]["nav_on"] for s in byver["v1.912"]}),
                note="a = v1.83, b = v1.912; entries average the scans listed (nav_on 1 and 2 give the same echo-1 values)",
                matched=rows))
        else:
            cmp_83_912.append(dict(protocol_class=desc, scans=byver, note="only one version acquired in this class"))

    te_groups = {}
    for k, m in ok.items():
        if m["version"] == "v1.83":
            te_groups.setdefault((m["te_ms"], m["big_delta_ms"], m["thickness_mm"], m["etl"], m["esp_ms"], m["dwell_us"]), []).append(k)
    cmp_te = []
    base = [g for g in te_groups if g[0] == 44 and g[1] == 30 and g[4] == 11 and g[5] == 25]
    long_ = [g for g in te_groups if g[0] == 54 and g[1] == 40]
    for gl in long_:
        for gb in base:
            rows = matched_rows(collect(te_groups[gb]), collect(te_groups[gl]))
            if rows:
                cmp_te.append(dict(
                    a_te44_D30=dict(zip(("te_ms", "big_delta_ms", "thickness_mm", "etl", "esp_ms", "dwell_us"), gb),
                                    scans=te_groups[gb]),
                    b_te54_D40=dict(zip(("te_ms", "big_delta_ms", "thickness_mm", "etl", "esp_ms", "dwell_us"), gl),
                                    scans=te_groups[gl]),
                    note="slice thickness also differs between the two groups (1 vs 2 mm), so the slice-select terms differ too"
                         if gb[2] != gl[2] else "",
                    matched=rows))


    cmp_etl = []
    for ga in long_:
        for gb_ in long_:
            if ga < gb_ and ga[:3] == gb_[:3] and ga[3] != gb_[3]:
                cmp_etl.append(dict(
                    a=dict(etl=ga[3], scans=te_groups[ga]), b=dict(etl=gb_[3], scans=te_groups[gb_]),
                    matched=matched_rows(collect(te_groups[ga]), collect(te_groups[gb_]))))

    # ---------------------------------------------------------------- EPI nominal reference
    epi = {}
    for key in L.EPI_SCANS:
        _, text = L.header_text(L.mrd_path(key))
        nb, nd = int(L.var(text, "no_b_steps")), int(L.var(text, "no_diff_dir"))
        d, big = L.var(text, "sm_delta") / 1000.0, L.var(text, "big_delta") / 1000.0
        bsteps = ppr_array(text, "b_steps_array")[:nb]
        dirs = ppr_array(text, "diff_grad_dir")[:3 * nb].reshape(-1, 3)
        console_dirs = [list(map(float, ln.split("\t")[1:4])) for ln in
                        (L.folder(key) / "btable.txt").read_text().strip().splitlines()]
        steps = []
        for i, b in enumerate(bsteps):
            g = np.sqrt(b * 1e6 / (GAMMA ** 2 * (d * 1e-3) ** 2 * ((big - d / 3) * 1e-3))) if b > 0 else 0.0
            steps.append(dict(step=i + 1, typed_b_s_mm2=float(b), nominal_b_s_mm2=float(b),
                              implied_G_mT_per_m=float(g * 1e3), implied_G_Hz_per_mm=float(GAMMA * g / (2 * np.pi) * 1e-3),
                              embedded_diff_grad_dir=list(map(float, dirs[i] / 1000.0)),
                              console_btable_dir=console_dirs[i] if i < len(console_dirs) else None))
        epi[key] = dict(
            folder=L.folder(key).name, ppl=re.search(r"^:PPL\s+(.*)$", text, re.M)[1].strip(), te_ms=L.var(text, "te"),
            small_delta_ms=d, big_delta_ms=big, diff_tramp_us=L.var(text, "diff_tramp"), no_b_steps=nb, no_diff_dir=nd,
            no_experiments=int(re.search(r":EXPERIMENT_ARRAY\s+no_experiments,\s*(\d+)", text)[1]), steps=steps)
    epi_note = ("Nominal Stejskal-Tanner reference only: b = (gamma*G*delta)^2*(Delta - delta/3) with delta=4 ms, Delta=30 ms, "
                "rectangular lobes, b taken as typed. Implied G is the amplitude that formula needs. NOT MODELLED: "
                "the 200 us diffusion ramps, the EPI imaging-gradient (readout/phase-blip) cross terms with the diffusion "
                "lobes, and the slice-select/crusher terms, so the true EPI b-matrix is larger and has off-diagonal terms. "
                "The console btable.txt lists direction +x for every step (no_diff_dir=1), whereas the embedded "
                "diff_grad_dir array lists x/y/z per step; which one the EPI PPL actually plays is not resolved here "
                "(EPI PPL is not in the repository).")

    # ---------------------------------------------------------------- write outputs
    fields = list(csv_rows[0])
    with (OUT / "oct12_effective_b.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(csv_rows)
    ppl_hashes = {}
    for k in keys:
        if "error" not in scans_json[k]:
            ppl_hashes[scans_json[k]["version"]] = dict(path=scans_json[k]["ppl"], sha256=scans_json[k]["ppl_sha256"])
    report = dict(
        status="SOURCE-MODEL PREDICTIONS FROM EMBEDDED PROTOCOLS; NOT MEASURED OR CALIBRATED",
        model_revision=eb.MODEL_REVISION, axes_and_units=eb.AXES, ppl_sha256_by_version=ppl_hashes,
        script_sha256=sha_bytes(Path(__file__).read_bytes()),
        notes=[
            "b in s/mm^2; directions are unit vectors in logical read/phase/slice (x/y/z) from acq_x/y/z.",
            "Echo 1 via eb.effective_b(pe_order=1); echoes >1 via eb._model with the echo index; nav_on=2 echo ETL+1 is the "
            "unencoded navigator echo.",
            "Imaging view count passed to the model is the true N (raw views minus volume navigator); passing the raw "
            "count makes the model fail and silently fall back to nominal.",
            "The model represents the first imaging shot; shot-dependent phase-encode terms vary within a volume and "
            "are not averaged. Effective b is identical for all slices (offsets change frequency/phase only).",
            "model_b10_same_direction is an extra (hypothetical b=10 volume along the direction of each b>10 volume).",
        ],
        failures=failures, scans=scans_json,
        comparison_v183_vs_v1912=cmp_83_912, comparison_te44_D30_vs_te54_D40=cmp_te, comparison_etl16_vs_etl8_te54_D40=cmp_etl,
        epi_nominal_stejskal_tanner=dict(note=epi_note, scans=epi),
        runtime_seconds=round(time.perf_counter() - started, 2))
    (OUT / "oct12_effective_b.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {len(csv_rows)} CSV rows; {len(failures)} failures; runtime {report['runtime_seconds']} s")


if __name__ == "__main__":
    main()
