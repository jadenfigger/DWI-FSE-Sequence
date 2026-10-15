"""Source-model b tables for the planned PBS/rat-brain qualification protocols.

Run from any directory: python experiments/2026-10-11_exvivo_plan/effective_b_predictions.py
Reads generated PPRs and repository PPLs; never modifies their bytes. No empirical
calibration is applied. These are predictions, not scanner measurements.
"""
from pathlib import Path
import csv
import hashlib
import json
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scanner/recon"))
sys.path.insert(0, str(ROOT))
from bare_bones_recon_fse import read_diffusion, ppr_array, read_pe_order
from effective_b import effective_b, AXES
from dwfse.ppl.ppr import read_ppr

SELECTED = ("A", "B", "C", "D", "Q", "R", "V", "AD", "AB", "AC")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    started = time.perf_counter()
    manifest_hash = sha(HERE / "manifest.json")
    manifest = json.loads((HERE / "manifest.json").read_text())
    records = {p["letter"]: p for p in manifest["protocols"]}
    missing = set(SELECTED) - records.keys()
    if missing:
        raise ValueError(f"Missing requested protocols: {sorted(missing)}; regenerate manifest first")
    tables, flat = {}, []
    for label in SELECTED:
        entry = records[label]
        path = HERE / entry["ppr"]
        protocol = path.read_text(encoding="latin-1")
        ppr_hash = sha(path)
        if ppr_hash != entry["ppr_sha256"]:
            raise ValueError(f"{label}: PPR hash differs from manifest")
        params, _ = read_ppr(path)
        diff = read_diffusion(protocol)
        etl, raw = params["views_per_seg"], params["no_views"]
        mode = params["nav_on"]
        N = (raw // (etl + 1) - 1) * etl if mode == 2 else raw - (etl if mode == 1 else 0)
        nvol = params["no_experiments"]
        t0 = time.perf_counter()
        # In-memory/temp-file mapping only: no additional cache/output files.
        model = effective_b(protocol, diff, nvol, N, read_pe_order(protocol),
                            cache_dir=None, calibration_path=None)
        if model["BMatrixSource"] != "event-model-primary-pathway":
            raise RuntimeError(f"{label}: effective-b prediction blocked: {model['BMatrixWarnings']}")
        if model["BMatrixCalibrationApplied"]:
            raise AssertionError(f"{label}: unexpected empirical calibration")
        if sha(path) != ppr_hash or model["BMatrixModel"]["Hashes"]["PPL"] != manifest["ppl_sha256"][entry["version"]]:
            raise ValueError(f"{label}: source/PPR changed or differs from manifest; rerun on frozen inputs")
        runtime = time.perf_counter() - t0
        raw_vectors = [ppr_array(protocol, "acq_" + axis)[:diff["n"]] for axis in "xyz"]
        rows = []
        for volume in range(nvol):
            step = volume % diff["n"]
            row = dict(protocol=label, version=entry["version"], volume=volume + 1,
                       nominal_b_s_mm2=float(diff["b"][step]),
                       direction_x=int(raw_vectors[0][step]), direction_y=int(raw_vectors[1][step]),
                       direction_z=int(raw_vectors[2][step]),
                       effective_trace_s_mm2=model["EffectiveBValue"][volume],
                       **dict(zip(("bxx", "byy", "bzz", "bxy", "bxz", "byz"), model["BMatrix"][volume])),
                       echo=model["BMatrixEcho"], imaging_shot_index=model["BMatrixModel"]["RepresentativeImagingShotIndex"][step],
                       source=model["BMatrixSource"], ppl_sha256=model["BMatrixModel"]["Hashes"]["PPL"],
                       ppr_sha256=ppr_hash, protocol_text_sha256=model["BMatrixModel"]["Hashes"]["Protocol"])
            rows.append(row)
            flat.append(row)
        # Actual PPR amplitudes and metadata remain explicit; FOV alone is not
        # enough to establish the read/phase waveform at 128 versus 256 samples.
        tables[label] = dict(ppr=entry["ppr"], purpose=entry["purpose"],
                             runtime_seconds=runtime, raw_views=raw, imaging_views=N,
                             samples=params["no_samples"], nav_on=mode,
                             protocol_gradient_parameters={k: params[k] for k in
                                 ("gr_var", "gp_init_var", "sample_period", "esp", "te", "big_delta", "sm_delta", "no_slices")},
                             SMX=re.search(r"^:SMX\s+([^\r\n]+)", protocol, re.M)[1],
                             model=model, volumes=rows)
        if label in ("V", "AD") and mode == 2:
            if model["BMatrixModel"]["RepresentativeImagingShotIndex"] != [4] * diff["n"]:
                raise AssertionError(f"{label}: multi-slice mode2 did not select the first imaging shot after three leading slice trains")
        print(f"{label}: {nvol} volumes, source model valid, {runtime:.2f} s", flush=True)
    if sha(HERE / "manifest.json") != manifest_hash:
        raise ValueError("Manifest changed during prediction; rerun on frozen inputs")
    report = dict(status="SOURCE-MODEL PREDICTIONS; NOT MEASURED OR EMPIRICALLY CALIBRATED",
                  axes_and_units=AXES,
                  method="Complete mapped PPL gradient waveform integrated analytically with dwfse.btensor; "
                         "instantaneous RF centres/sign changes; ss-MGOT carrier/conjugate branch with "
                         "smallest echo endpoint, longitudinal interval retained. RF latency=3 us and "
                         "gradient latency=embedded rfdelay. Representative first imaging shot; all "
                         "mode2 leading volume trains and actual phase rewinder retained.",
                  interpretation="PBS polarity/axis comparisons test relative calibration and cross-term hypotheses. "
                                 "Absolute b calibration requires an independent reference diffusivity and measured "
                                 "temperature; fixed-brain diffusivity is not an absolute b reference. No empirical "
                                 "z-axis correction is assumed. These predictions do not describe mixed FSE pathways.",
                  manifest_sha256=manifest_hash, script_sha256=sha(__file__),
                  runtime_seconds=time.perf_counter()-started, protocols=tables)
    (HERE / "effective_b_predictions.json").write_text(json.dumps(report, indent=2) + "\n")
    with (HERE / "effective_b_predictions.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)
    print(f"Wrote {len(flat)} volume predictions in {report['runtime_seconds']:.2f} s", flush=True)


if __name__ == "__main__":
    main()
