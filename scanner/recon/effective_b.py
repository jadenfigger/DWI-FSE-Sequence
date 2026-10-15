"""Protocol-derived primary-pathway b matrices; model output, not calibration.

Logical axes are x=read, y=phase, z=slice, as in the nominal .bvec. The
instantaneous-RF convention and ss-MGOT branch selection match FINAL_REPORT §8.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
AXES = "logical x=read, y=phase, z=slice; s/mm^2; columns bxx byy bzz bxy bxz byz"
MODEL_REVISION = "primary-pwc-rf3us-gradient-rfdelay-v3-acquired-nav2-hazard-gated"


def components(matrix):
    b = np.asarray(matrix)
    return b[..., (0, 1, 2, 0, 0, 1), (0, 1, 2, 1, 2, 2)]


def resolve_ppl(protocol):
    m = re.search(r"^:PPL\s+([^\r\n]+)", protocol, re.M)
    if not m:
        raise ValueError("embedded :PPL is missing")
    name = m[1].strip().strip('"').replace("\\", "/").rsplit("/", 1)[-1]
    version = re.search(r"-([\d.]+)\.ppl$", name, re.I)
    if not version or version[1] not in ("1.8", "1.81", "1.82", "1.83", "1.91", "1.911", "1.912"):
        raise ValueError(f"unsupported sequence {name}")
    # Console v1.91 scans used the method-only v7 snapshot, whereas scanner/1.91
    # currently holds a different combined source. Resolve to the acquired lineage.
    folder = ROOT / ("docs/v181_v1911/baseline_v7" if version[1] == "1.91" else "scanner")
    paths = [p for p in folder.glob("*.ppl") if p.name.lower() == name.lower()]
    if len(paths) != 1:
        raise FileNotFoundError(f"repo PPL not found for {name}")
    return paths[0], version[1]


def _integrate(led, t0, t1, flips, frozen, lag):
    from dwfse.btensor import integrate_interval
    events = [(t, "flip") for t in flips if t0 < t < t1]
    events += [(a, "freeze") for a, _ in frozen if t0 < a < t1]
    events += [(b, "thaw") for _, b in frozen if t0 < b < t1]
    events.sort()
    marks = [t0] + [e[0] for e in events] + [t1]
    kinds = [None] + [e[1] for e in events]
    q, B, held = np.zeros(3), np.zeros((3, 3)), False
    fac = led["H"] * 1e3 / 32767
    for index, (a, b) in enumerate(zip(marks[:-1], marks[1:])):
        if kinds[index] == "flip":
            q = -q
        elif kinds[index] == "freeze":
            held = True
        elif kinds[index] == "thaw":
            held = False
        cuts = {a, b}
        for axis in "SPR":
            times = led["G"][axis].t + lag
            cuts.update(times[(times > a) & (times < b)].tolist())
        cuts = sorted(cuts)
        for start, end in zip(cuts[:-1], cuts[1:]):
            if end <= start:
                continue
            g = np.zeros(3) if held else np.array([
                led["G"][axis].value_at((start + end) / 2 - lag) for axis in "SPR"
            ]) * fac
            q, delta = integrate_interval(q, g, g, (end - start) * 1e-6)
            B += delta
    return q, B


def _model(ppl, protocol, diff, imaging_views, echo):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from dwfse.ppl.run import map_events
    from dwfse.ppl.ledger import build_ledger, adc_middle_times
    from dwfse.ppl.ppr import read_ppr
    count = diff["n"]
    matrices, branches, shot_indices = [], [], []
    # The mapper accepts a PPR file. Only this temporary copy is created; the
    # adjacent PPR and raw scan are never used or modified.
    with tempfile.TemporaryDirectory(prefix="dwfse_beff_") as directory:
        ppr = Path(directory) / "embedded.ppr"
        ppr.write_text(protocol, encoding="latin-1")
        acquired, _ = read_ppr(ppr)
        mode2 = acquired.get("nav_on", 0) == 2
        # One leading volume train per slice/block precedes imaging. Preserve
        # actual mode-2 waveforms, including its mirrored phase rewinder. Averages
        # occur outside this group; their absolute RF phase does not alter B.
        batch = acquired.get("batch_slices", 0) or acquired.get("no_slices", 1)
        leading_shots = batch * acquired.get("view_block", 1) * acquired.get("no_views_2", 1)
        max_shots = leading_shots + 1 if mode2 else 1
        for row in range(count):
            overrides = dict(no_disacq=0)
            if not mode2:
                overrides.update(nav_on=0, no_views=imaging_views)
            for axis in "xyz":
                m = re.search(rf":VAR_ARRAY\s+acq_{axis},\s*\d+,(.*?)(?=\r?\n:|\Z)", protocol, re.S | re.I)
                vals = [float(v) for v in re.findall(r"-?[\d.]+", m[1])]
                overrides[f"acq_{axis}"] = [int(vals[row])] * count
            key = "acq_b" if diff["b"] is not None else "acq_grad"
            # DAC mode scale remains in the protocol; do not apply it twice.
            m = re.search(rf":VAR_ARRAY\s+{key},\s*\d+,(.*?)(?=\r?\n:|\Z)", protocol, re.S | re.I)
            vals = [float(v) for v in re.findall(r"-?[\d.]+", m[1])]
            overrides[key] = [int(vals[row])] * count
            it = map_events(ppl, ppr, overrides=overrides, max_shots=max_shots,
                            rf_latency_us=3., stmt_cost_us=0., expr_costs=True, expr_scale=.8)
            if it.vars.get("v19_error_code") and it.vars["v19_error_code"].value:
                raise ValueError(f"event model rejected protocol: E{it.vars['v19_error_code'].value}")
            hazards = [f for f in it.flags if f["kind"] == "timer_overrun"
                       or (f["kind"] == "gradient" and "ignored" in f.get("message", f.get("msg", "")))]
            if hazards:
                raise ValueError(f"event model has timing/gradient hazards: {hazards[0]}")
            shot_index = 1
            if mode2:
                first_imaging = next((a for a in it.adc if a.get("vars", {}).get("nav_cnt") == 1), None)
                if first_imaging is None:
                    raise ValueError("event model produced no mode-2 imaging shot")
                starts = [e[1] for e in it.misc_events if e[0] == "shot"]
                shot_index = int(np.searchsorted(starts, first_imaging["t_init"], side="right"))
            led = build_ledger(it, shot_index)
            rf = led["rf"]
            adcs = adc_middle_times(it, led)
            if len(adcs) < echo or not rf:
                raise ValueError("event model produced no requested imaging echo")
            lag = float(it.vars["rfdelay"].value)
            method = any(p["frame"] == "v19_slrtip90" for p in rf)
            frozen = []
            if method:
                flips = [p["t_center"] for p in rf if "180" in p["frame"]]
                tip = next(p["t_center"] for p in rf if p["frame"] == "v19_slrtip90")
                reexc = next(p["t_center"] for p in rf if p["frame"] == "v19_reexc90")
                frozen = [(tip, reexc)]
                candidates = {"carrier": flips, "conjugate": sorted(flips + [reexc])}
            else:
                candidates = {"primary": [p["t_center"] for p in rf[1:]]}
            results = {name: _integrate(led, rf[0]["t_center"], adcs[echo - 1][1], times, frozen, lag)
                       for name, times in candidates.items()}
            branch = min(results, key=lambda name: np.linalg.norm(results[name][0]))
            b = results[branch][1]
            matrices.append(b[np.ix_([2, 1, 0], [2, 1, 0])])
            branches.append(branch)
            shot_indices.append(shot_index)
    return dict(matrices=np.asarray(matrices).tolist(), branches=branches, shot_indices=shot_indices)


def effective_b(protocol, diff, no_volumes, imaging_views, pe_order=1,
                cache_dir=None, calibration_path=None):
    """Never raise on modelling/calibration failure: retain a nominal fallback."""
    warnings = ["Source model only: instantaneous RF primary pathway, assumed RF latency 3 us, "
                "gradient delay=rfdelay; mixed FSE pathways and measured gradient calibration are not modelled."]
    step = np.arange(no_volumes) % max(diff["n"], 1)
    # ETL comes from embedded protocol for linear/reverse-centric centre echo.
    m = re.search(r":VIEWS_PER_SEGMENT\s+\w+,\s*(\d+)", protocol)
    etl = int(m[1]) if m else 8
    if re.search(r"^:VAR\s+nav_on,\s*2", protocol, re.M):
        etl -= 1   # mode 2 stores VIEWS_PER_SEGMENT = ETL+1
    echo = 1 if pe_order == 1 else (etl if pe_order == 6 else etl // 2 + 1)
    nominal = diff["b"]
    if nominal is None:
        d, D = diff["delta"] * .001, diff["big_delta"] * .001
        # Same nominal diffusion-lobe kernel as PPL (grad_var is Hz/mm).
        h = re.search(r":GRADIENT_STRENGTH\s+\w+,\s*\d+,\s*(-?\d+)", protocol)
        nominal = 39.69 * d*d*(D-d/3) * (diff["dac"] / 32767 * float(h[1]) * 1000)**2 if h else np.zeros(diff["n"])
    nominal_matrices = nominal[:, None, None] * diff["unit"][:, :, None] * diff["unit"][:, None, :]
    matrices = nominal_matrices.copy()
    source, applied, details = "nominal-fallback", False, {}
    try:
        ppl, version = resolve_ppl(protocol)
        hashes = dict(PPL=hashlib.sha256(ppl.read_bytes()).hexdigest(),
                      Protocol=hashlib.sha256(protocol.encode("latin-1")).hexdigest())
        key = hashlib.sha256(json.dumps([MODEL_REVISION, hashes, echo], sort_keys=True).encode()).hexdigest()
        details["CacheKey"] = key
        cache = Path(cache_dir) / (key + ".json") if cache_dir else None
        if cache and cache.exists():
            model = json.loads(cache.read_text())
            details["CacheHit"] = True
        else:
            model = _model(ppl, protocol, diff, imaging_views, echo)
            details["CacheHit"] = False
            if cache:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(json.dumps(model), encoding="utf-8")
        candidate = np.asarray(model["matrices"], dtype=float)
        if candidate.shape != (diff["n"], 3, 3) or not np.all(np.isfinite(candidate)) or not np.allclose(candidate, candidate.transpose(0, 2, 1)):
            raise ValueError("invalid cached/modelled b-matrix table")
        matrices = candidate
        source = "event-model-primary-pathway"
        details.update(Hashes=hashes, PPL=str(ppl), Branches=model["branches"], ModelRevision=MODEL_REVISION,
                       RepresentativeImagingShotIndex=model.get("shot_indices", []))
        if calibration_path and Path(calibration_path).exists():
            try:
                config = json.loads(Path(calibration_path).read_text())
                calibration = config.get("versions", {}).get(version)
                if calibration is not None:
                    scale = np.asarray(calibration.get("axis_scale", [1, 1, 1]), float)
                    additive = np.asarray(calibration.get("additive_bmatrix", np.zeros((3, 3))), float)
                    if scale.shape != (3,) or additive.shape != (3, 3) or not np.all(np.isfinite(scale)) or not np.all(np.isfinite(additive)) or np.any(scale <= 0) or not np.allclose(additive, additive.T):
                        raise ValueError("axis_scale must be 3 positive gradient factors; additive_bmatrix must be a finite symmetric 3x3 matrix")
                    calibrated = matrices * scale[None, :, None] * scale[None, None, :] + additive
                    if np.min(np.linalg.eigvalsh(calibrated)) < -1e-6:
                        raise ValueError("calibration produces a non-positive b matrix")
                    matrices, applied = calibrated, True
                    source += "+calibration"
                    details["Calibration"] = calibration
                    details["CalibrationSHA256"] = hashlib.sha256(Path(calibration_path).read_bytes()).hexdigest()
            except Exception as exc:
                warnings.append(f"Calibration ignored: {type(exc).__name__}: {exc}")
    except Exception as exc:
        matrices, source, applied = nominal_matrices.copy(), "nominal-fallback", False
        warnings.append(f"Effective-b model unavailable; nominal fallback: {type(exc).__name__}: {exc}")
    warnings.append("BMatrixEcho is the echo containing the k-space centre (centric: 1; "
                    "reverse-centric: ETL; linear: ETL/2+1), represented by the first imaging shot; "
                    "shot-dependent phase-encode b terms are not a volume average.")
    volumes = matrices[step]
    return dict(EffectiveBValue=np.trace(volumes, axis1=1, axis2=2).tolist(),
                BMatrix=components(volumes).tolist(), BMatrixEcho=echo,
                BMatrixSource=source, BMatrixWarnings=warnings, BMatrixAxes=AXES,
                BMatrixCalibrationApplied=applied, BMatrixModel=details)


def write_b_sidecars(stem, metadata):
    Path(str(stem) + "_beff.bval").write_text(" ".join(f"{b:.8g}" for b in metadata["EffectiveBValue"]) + "\n")
    np.savetxt(str(stem) + "_bmatrix.txt", metadata["BMatrix"], fmt="%.9g", header=AXES)
