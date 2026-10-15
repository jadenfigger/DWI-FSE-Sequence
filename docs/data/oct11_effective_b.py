"""Effective b-matrices for the acquired 2026-10-11 MRD scans (source model; no calibration).

Run from the repository root:  python docs/data/oct11_effective_b.py

Inputs: experiments/FSE-DWI_10-11-2026_*/*.MRD, embedded protocol text only (bytes from b':PPL').
Outputs: docs/data/oct11_effective_b.csv, docs/data/oct11_effective_b.json,
         docs/data/oct11_effective_b_vs_plan.csv.

Echo 1 (centric k-space centre) is computed through the public scanner/recon/effective_b.effective_b
with pe_order=1, exactly as the reconstruction does. Echoes 2..8 for scans A, C, E, Q, T, V call the
same private _model routine directly with the echo index, so per-echo navigator fits can use them.
Nothing here is calibrated or measured; the model is the instantaneous-RF primary pathway.

PPL resolution: resolve_ppl takes the basename of the embedded :PPL path (G:\\J_Figger\\...) and looks it
up in ROOT/scanner. On this machine that lookup succeeds for all versions used here, so no monkeypatch is
applied and effective_b.py is not edited. The 'repo PPL not found' failure in the sidecars was therefore
an environment difference on the reconstruction machine (the file was not present in its ROOT/scanner),
not a naming bug. This script refuses to continue if a required PPL is not found locally.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scanner/recon"))
sys.path.insert(0, str(ROOT))
import effective_b as eb  # noqa: E402
from bare_bones_recon_fse import read_diffusion, ppr_array, read_pe_order  # noqa: E402
from dwfse.ppl.ppr import read_ppr  # noqa: E402

EXP = ROOT / "experiments"
OUT = ROOT / "docs/data"
PLAN = EXP / "2026-10-11_exvivo_plan"
EXTRA_ECHO_SCANS = {"A", "C", "E", "Q", "T", "V"}
MAX_ECHO = 8
NAMES = "xyz"


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def ppr_params(protocol):
    with tempfile.TemporaryDirectory(prefix="oct11_beff_") as directory:
        path = Path(directory) / "embedded.ppr"
        path.write_text(protocol, encoding="latin-1")
        params, _ = read_ppr(path)
    return params


def dlabel(vector):
    if not any(vector):
        return "0"
    axis = [i for i, c in enumerate(vector) if c]
    if len(axis) != 1:
        return "mixed"
    i = axis[0]
    return ("+" if vector[i] > 0 else "-") + NAMES[i]


def valid_matrices(mats, n):
    mats = np.asarray(mats, dtype=float)
    ok = mats.shape == (n, 3, 3) and np.all(np.isfinite(mats)) and np.allclose(mats, mats.transpose(0, 2, 1))
    if not ok:
        raise ValueError("invalid b-matrix table")
    return mats


def main():
    started = time.perf_counter()
    script_sha = sha_bytes(Path(__file__).read_bytes())
    mrd_files = sorted(EXP.glob("FSE-DWI_10-11-2026_*/*.MRD"))
    print(f"{len(mrd_files)} MRD files", flush=True)

    csv_rows, scans, ppl_hashes = [], [], {}
    for mrd in mrd_files:
        folder = mrd.parent.name
        m = re.match(r"FSE-DWI_10-11-2026_(v\w+?)_test(\w+)$", folder)
        version_label, letter = m[1], m[2]
        t0 = time.perf_counter()
        data = mrd.read_bytes()
        protocol = data[data.find(b":PPL"):].decode("latin-1")
        params = ppr_params(protocol)
        diff = read_diffusion(protocol)
        n_steps = diff["n"]
        nvol = int(params["no_experiments"])
        etl, raw, mode = int(params["views_per_seg"]), int(params["no_views"]), int(params["nav_on"])
        N = (raw // (etl + 1) - 1) * etl if mode == 2 else raw - (etl if mode == 1 else 0)
        pe_order = read_pe_order(protocol)
        raw_dir = [ppr_array(protocol, "acq_" + a)[:n_steps] for a in NAMES]
        step_dirs = [tuple(int(raw_dir[i][s]) for i in range(3)) for s in range(n_steps)]

        if diff["b"] is not None:
            nominal_steps = np.asarray(diff["b"], float)
            nominal_source = "b-entered"
        else:
            d, D = diff["delta"] * .001, diff["big_delta"] * .001
            h = re.search(r":GRADIENT_STRENGTH\s+\w+,\s*\d+,\s*(-?\d+)", protocol)
            nominal_steps = (39.69 * d * d * (D - d / 3) * (diff["dac"] / 32767 * float(h[1]) * 1000) ** 2
                             if h else np.zeros(n_steps))
            nominal_source = "DAC-derived (Stejskal-Tanner kernel)"

        # Echo 1 through the public entry point (pe_order forced to 1 = centric echo 1).
        res = eb.effective_b(protocol, diff, nvol, N, 1)
        ppl_path, ppl_version = eb.resolve_ppl(protocol)
        ppl_hash = sha_bytes(ppl_path.read_bytes())
        ppl_hashes[ppl_version] = {"path": str(ppl_path.relative_to(ROOT)), "sha256": ppl_hash}
        echo1_src = res["BMatrixSource"]
        echo1_warn = " | ".join(res["BMatrixWarnings"])
        branches = res["BMatrixModel"].get("Branches", []) if echo1_src.startswith("event") else []
        shots = res["BMatrixModel"].get("RepresentativeImagingShotIndex", []) if echo1_src.startswith("event") else []
        for v in range(nvol):
            s = v % n_steps
            comp = res["BMatrix"][v]
            csv_rows.append(dict(
                scan=letter, folder=folder, version=version_label, volume=v + 1, echo=1,
                nominal_b_s_mm2=float(nominal_steps[s]),
                direction_x=step_dirs[s][0], direction_y=step_dirs[s][1], direction_z=step_dirs[s][2],
                bxx=comp[0], byy=comp[1], bzz=comp[2], bxy=comp[3], bxz=comp[4], byz=comp[5],
                trace_s_mm2=res["EffectiveBValue"][v],
                model_source=echo1_src,
                model_status="ok" if echo1_src.startswith("event") else "fallback (not modelled)",
                branch=branches[s] if branches else "",
                representative_imaging_shot=shots[s] if shots else "",
                warnings=echo1_warn,
            ))

        echo_status = {1: echo1_src}
        if letter in EXTRA_ECHO_SCANS:
            for echo in range(2, MAX_ECHO + 1):
                try:
                    out = eb._model(ppl_path, protocol, diff, N, echo)
                    mats = valid_matrices(out["matrices"], n_steps)
                    status, src = "ok", "event-model-primary-pathway"
                except Exception as exc:  # echo not reachable or model rejected
                    status, src = f"failed: {type(exc).__name__}: {exc}", "not-modelled"
                    mats = None
                echo_status[echo] = status
                for v in range(nvol):
                    s = v % n_steps
                    if mats is None:
                        vals = [float("nan")] * 6
                        trace = float("nan")
                    else:
                        comp = eb.components(mats[s])
                        vals = [float(c) for c in comp]
                        trace = float(np.trace(mats[s]))
                    csv_rows.append(dict(
                        scan=letter, folder=folder, version=version_label, volume=v + 1, echo=echo,
                        nominal_b_s_mm2=float(nominal_steps[s]),
                        direction_x=step_dirs[s][0], direction_y=step_dirs[s][1], direction_z=step_dirs[s][2],
                        bxx=vals[0], byy=vals[1], bzz=vals[2], bxy=vals[3], bxz=vals[4], byz=vals[5],
                        trace_s_mm2=trace, model_source=src, model_status=status,
                        branch="", representative_imaging_shot="",
                        warnings=("Echo %d computed via _model; source model only, no calibration" % echo)
                        if mats is not None else status,
                    ))
                if mats is None:
                    break

        scans.append(dict(
            scan=letter, folder=folder, version_folder=version_label, ppl_version=ppl_version,
            ppl=str(ppl_path.relative_to(ROOT)), ppl_sha256=ppl_hash,
            protocol_sha256=sha_bytes(protocol.encode("latin-1")),
            nav_on=mode, views_per_segment=etl, raw_views=raw, imaging_views=N,
            pe_order=pe_order, volumes=nvol, diffusion_steps=n_steps, nominal_source=nominal_source,
            echo1_source=echo1_src, echo1_warnings=echo1_warn,
            echo_status={str(k): v for k, v in echo_status.items()},
            runtime_seconds=round(time.perf_counter() - t0, 2),
        ))
        print(f"{letter:>4} {version_label:>6} vols={nvol:2d} nav={mode} pe={pe_order} "
              f"src={echo1_src} {time.perf_counter() - t0:.1f}s", flush=True)

    # Per-scan one-line summary of echo-1 traces.
    print("\nEcho-1 effective trace (s/mm2) per volume: nominal[dir]=trace")
    for scan in scans:
        rows = [r for r in csv_rows if r["scan"] == scan["scan"] and r["folder"] == scan["folder"] and r["echo"] == 1]
        print(f"{scan['scan']:>4} {scan['version_folder']:>6}: " + "  ".join(
            f"{r['nominal_b_s_mm2']:g}[{dlabel((r['direction_x'], r['direction_y'], r['direction_z']))}]={r['trace_s_mm2']:.2f}"
            for r in rows))

    # b10 -> b1000 denominator of the ADC relation, echo 1.
    denom_rows = []
    for scan in scans:
        rows = [r for r in csv_rows if r["folder"] == scan["folder"] and r["echo"] == 1]
        b10 = [r for r in rows if abs(r["nominal_b_s_mm2"] - 10) < 1e-6]
        for r in rows:
            if abs(r["nominal_b_s_mm2"] - 1000) > 1e-6:
                continue
            key = (r["direction_x"], r["direction_y"], r["direction_z"])
            same = [q for q in b10 if (q["direction_x"], q["direction_y"], q["direction_z"]) == key]
            if same:
                ref, flag = same[0], "same direction"
            elif b10:
                ref, flag = b10[0], "b10 reference in different direction (not valid for ADC)"
            else:
                ref, flag = None, "no b10 volume"
            denom_rows.append(dict(
                scan=scan["scan"], folder=scan["folder"], version=scan["version_folder"], direction=dlabel(key),
                trace_b1000=r["trace_s_mm2"], trace_b10=ref["trace_s_mm2"] if ref else None,
                denominator_s_mm2=(r["trace_s_mm2"] - ref["trace_s_mm2"]) if ref else None,
                nominal_difference=990.0, reference=flag,
            ))

    # Comparison with the planned-PPR predictions (matched on protocol letter and version).
    pred_rows = list(csv.DictReader((PLAN / "effective_b_predictions.csv").open(encoding="utf-8")))
    pred_json = json.loads((PLAN / "effective_b_predictions.json").read_text(encoding="utf-8"))["protocols"]
    cmp_rows = []
    for scan in scans:
        plan = [p for p in pred_rows if p["protocol"] == scan["scan"] and p["version"] == scan["version_folder"]]
        if not plan:
            continue
        plan_nav = pred_json[scan["scan"]]["nav_on"]
        echo1 = {r["volume"]: r for r in csv_rows if r["folder"] == scan["folder"] and r["echo"] == 1}
        for p in plan:
            v = int(p["volume"])
            if v not in echo1:
                continue
            c = echo1[v]
            pred = float(p["effective_trace_s_mm2"])
            cmp_rows.append(dict(
                scan=scan["scan"], folder=scan["folder"], version=scan["version_folder"], volume=v,
                nominal_b_s_mm2=c["nominal_b_s_mm2"],
                direction_x=c["direction_x"], direction_y=c["direction_y"], direction_z=c["direction_z"],
                plan_direction_x=p["direction_x"], plan_direction_y=p["direction_y"], plan_direction_z=p["direction_z"],
                plan_nav_on=plan_nav, acquired_nav_on=scan["nav_on"],
                predicted_trace_s_mm2=pred, computed_trace_s_mm2=c["trace_s_mm2"],
                difference_computed_minus_predicted=c["trace_s_mm2"] - pred,
            ))

    # Write outputs.
    OUT.mkdir(parents=True, exist_ok=True)
    fields = list(csv_rows[0])
    with (OUT / "oct11_effective_b.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(csv_rows)
    if cmp_rows:
        with (OUT / "oct11_effective_b_vs_plan.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(cmp_rows[0]))
            w.writeheader()
            w.writerows(cmp_rows)
    report = dict(
        status="SOURCE-MODEL PREDICTIONS FROM EMBEDDED PROTOCOLS; NOT MEASURED OR CALIBRATED",
        model_revision=eb.MODEL_REVISION, axes_and_units=eb.AXES,
        ppl_sha256_by_version=ppl_hashes, script_sha256=script_sha,
        echo_scope={"all_scans": 1, "extra_echoes_2_to_8": sorted(EXTRA_ECHO_SCANS)},
        scans=scans, b10_b1000_denominators=denom_rows, runtime_seconds=round(time.perf_counter() - started, 2),
    )
    (OUT / "oct11_effective_b.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    # Printed comparison table.
    print("\nComparison with planned predictions (echo 1, trace s/mm2)")
    print(f"{'scan':>4} {'vol':>3} {'nomB':>7} {'dir':>4} {'plan':>10} {'computed':>10} {'diff':>8}")
    for r in cmp_rows:
        print(f"{r['scan']:>4} {r['volume']:>3} {r['nominal_b_s_mm2']:>7g} "
              f"{dlabel((r['direction_x'], r['direction_y'], r['direction_z'])):>4} "
              f"{r['predicted_trace_s_mm2']:>10.3f} {r['computed_trace_s_mm2']:>10.3f} "
              f"{r['difference_computed_minus_predicted']:>8.3f}")
    print("\nb10 -> b1000 trace denominator (echo 1)")
    for r in denom_rows:
        print(f"{r['scan']:>4} {r['version']:>6} dir={r['direction']:>3} b1000={r['trace_b1000']:.2f} "
              f"b10={r['trace_b10'] if r['trace_b10'] is None else round(r['trace_b10'], 3)} "
              f"denom={r['denominator_s_mm2'] if r['denominator_s_mm2'] is None else round(r['denominator_s_mm2'], 2)} "
              f"({r['reference']})")
    print(f"\nWrote {len(csv_rows)} rows; runtime {report['runtime_seconds']} s")


if __name__ == "__main__":
    main()
