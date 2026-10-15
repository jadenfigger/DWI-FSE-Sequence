"""Event-model gates for the v1.83 off-centre RF phase switch.

The repository mapper's synthesizer model predicted v1.82 off-centre RF phase to
within 0.21 degrees, but the 2026-10-11 scanner data show a ramp of about 41
degrees per echo per mm. The mapper therefore cannot certify which scheme is
physically right. These gates check only what the source change must do, against
the two schemes the scanner has actually run:

1. Mode 1 with v183_phcal 0 plays exactly the v1.82 events (all cost models).
2. Mode 0 issues the v1.81 (vendor) RF phase commands, receiver phases and
   frequency settings at every slice offset; timing is compared and reported.
3. Mode 1 with v183_phcal P shifts only the off-centre gated RF phase commands,
   by k * P * f * 1e-7 turns at the k-th refocusing pulse; nothing else changes.
4. At zero slice offset all modes and calibrations play identical events.
Also runs the static image audit. Writes docs/v183/validation/v183_events.json.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from examples import validate_v182_v1912 as v182  # noqa: E402
from examples.v181_v1911_static_audit import audit  # noqa: E402

SC = ROOT / "scanner"
OUT = ROOT / "docs/v183/validation"
PPRS = ROOT / "docs/v183/test_pprs"
PPL = {"v181": SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl", "v182": SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.82.ppl",
       "v183": SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.83.ppl"}
SEED = ROOT / "experiments/FSE-DWI_10-10-2026_v181_testK/FSE-DWI_10-10-2026_v181_testK.ppr"
IMAGING = {"no_disacq": 0, "nav_on": 0, "no_views": 128, "no_slices": 1}
PHASE_UNITS_PER_TURN = 1600   # deg_90 = 400 units (0.225 degree each)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def make_ppr(name, z_mm):
    lines = SEED.read_bytes().decode("latin-1").replace("\r\n", "\n").split("\n")
    v182.set_record(lines, "no_slices", 1)
    v182.set_array(lines, "fov_slice_off", [round(z_mm * 400)])
    PPRS.mkdir(parents=True, exist_ok=True)
    path = PPRS / f"{name}.ppr"
    path.write_bytes("\r\n".join(lines).encode("latin-1"))
    return path


def mapped(label, ppr, extra=None, model=None):
    from dwfse.ppl.run import map_events
    return map_events(PPL[label], ppr, overrides={**IMAGING, **(extra or {})}, max_shots=1, rf_latency_us=3.0,
                      **(model or v182.NOMINAL))


def signature(it):
    sig = v182.full_event_signature(it)
    return json.loads(json.dumps(sig, default=v182.json_default))


def same_played(a, b, setup_tol_us=10.0):
    """RF, ADC, gradient and phase events identical; frequency commands identical except that
    untimed setup commands outside the echo train (before the excitation or after the last
    acquisition, i.e. the next TR's slice setup) may move by setup_tol_us (arithmetic cost)."""
    if any(a[k] != b[k] for k in ("rf", "adc", "grad", "phase")) or len(a["freq"]) != len(b["freq"]):
        return False
    end = max([t for row in a["adc"] for t in row[:2]] + [row[0] for row in a["rf"]])
    for x, y in zip(a["freq"], b["freq"]):
        if x[1:] != y[1:]:
            return False
        outside = (x[0] < 0 and y[0] < 0) or (x[0] > end and y[0] > end)
        if x[0] != y[0] and not (outside and abs(x[0]-y[0]) <= setup_tol_us):
            return False
    return True


def rf_rows(it):
    return [dict(t=p["t_go"], frame=p["frame"], phase=p["phase_units"], f=p.get("tx_freq_hz")) for p in v182.rf_all(it)]


def adc_rows(it):
    return [dict(t=a["t_init"], phase=a["rx_phase_units"]) for a in it.adc]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    res = {"inputs": {k: sha(v) for k, v in PPL.items()}, "seed_ppr": str(SEED.relative_to(ROOT)), "failures": [], "cases": {}}
    st = audit(PPL["v183"], baseline_source=PPL["v182"])
    res["static"] = {k: st[k] for k in ("pass", "checks", "estimated_image_bytes", "relative_image_limit_bytes", "code_nodes")}
    if not st["pass"]:
        res["failures"].append("static audit")

    offsets = (0, 1.2, -1.2, 2.4, -5)
    # 1 + 4: mode 1 / phcal 0 identical to v1.82 under every cost model; zero offset identical for all modes.
    for model_name, model in v182.MODELS.items():
        for z in offsets:
            ppr = make_ppr(f"z{z}".replace("-", "m").replace(".", "p"), z)
            a = signature(mapped("v182", ppr, model=model))
            b = signature(mapped("v183", ppr, {"v183_phmode": 1, "v183_phcal": 0}, model=model))
            ok = same_played(a, b)
            res["cases"][f"mode1_phcal0_vs_v182/{model_name}/z{z}"] = ok
            if not ok:
                res["failures"].append(f"mode 1 phcal 0 differs from v1.82 ({model_name}, z={z})")
            if z == 0:
                for extra in ({"v183_phmode": 0}, {"v183_phmode": 1, "v183_phcal": 530}):
                    c = signature(mapped("v183", ppr, extra, model=model))
                    same = same_played(a, c)
                    res["cases"][f"zero_offset_{extra}_vs_v182/{model_name}"] = same
                    if not same:
                        res["failures"].append(f"zero offset differs for {extra} ({model_name})")

    # 2: mode 0 is the vendor per-echo scheme: constant per-echo increment phase_ang on the RF
    # and receiver phase commands, computed from its own carrier; timing equals the centred slice.
    # v1.81 is the same scheme with v1.81's slice-frequency rounding (2-5 Hz different).
    res["mode0"] = {}
    centre = mapped("v183", make_ppr("z0", 0), {"v183_phmode": 0})
    c_rf, c_adc = rf_rows(centre), adc_rows(centre)
    for z in offsets[1:]:
        ppr = make_ppr(f"z{z}".replace("-", "m").replace(".", "p"), z)
        a, b = mapped("v181", ppr), mapped("v183", ppr, {"v183_phmode": 0})
        row = {}
        for name, it in (("v181", a), ("v183_mode0", b)):
            deg360 = int(it.vars["deg_360"].value); ang = int(it.vars["phase_ang"].value)
            rx = [x["phase"] for x in adc_rows(it)]
            rf = [x["phase"] for x in rf_rows(it)]
            rx_inc = sorted({(rx[k+1]-rx[k]) % deg360 for k in range(len(rx)-1)})
            rf_inc = sorted({(rf[k+1]-rf[k]) % deg360 for k in range(2, len(rf)-1)})
            carrier = [x["f"] for x in rf_rows(it) if x["f"] is not None]
            row[name] = dict(carrier_hz=float(carrier[-1]) if carrier else float("nan"), phase_ang_units=ang, deg_360_units=deg360,
                             rx_increments=rx_inc, train_rf_increments=rf_inc)
        b_rf, b_adc = rf_rows(b), adc_rows(b)
        row["timing_equals_centred_slice"] = ([round(x["t"]-b_rf[0]["t"], 3) for x in b_rf] == [round(x["t"]-c_rf[0]["t"], 3) for x in c_rf]
                                              and [round(x["t"]-b_rf[0]["t"], 3) for x in b_adc] == [round(x["t"]-c_rf[0]["t"], 3) for x in c_adc])
        m = row["v183_mode0"]
        tol = 2  # phase_correction carries a +/-1 rounding unit per echo
        vendor_like = (max(m["rx_increments"]) - min(m["rx_increments"]) <= tol and
                       min(abs(m["rx_increments"][0] - (m["phase_ang_units"] % m["deg_360_units"])),
                           m["deg_360_units"] - abs(m["rx_increments"][0] - (m["phase_ang_units"] % m["deg_360_units"]))) <= tol)
        row["vendor_scheme_reproduced"] = vendor_like
        row["carrier_rel_diff_vs_v181"] = abs(m["carrier_hz"]-row["v181"]["carrier_hz"])/abs(row["v181"]["carrier_hz"])
        if not vendor_like:
            res["failures"].append(f"mode 0 is not a constant per-echo phase_ang scheme at z={z}")
        if not row["timing_equals_centred_slice"]:
            res["failures"].append(f"mode 0 off-centre timing differs from the centred slice at z={z}")
        if row["carrier_rel_diff_vs_v181"] > 1e-3:
            res["failures"].append(f"mode 0 carrier differs from v1.81 by more than 0.1% at z={z}")
        res["mode0"][f"z{z}"] = row

    # 3: phcal shifts only gated RF phase commands, by k*P*f*1e-7 turns.
    res["phcal_shift"] = {}
    for z in (1.2, -1.2, 2.4):
        ppr = make_ppr(f"z{z}".replace("-", "m").replace(".", "p"), z)
        base = mapped("v183", ppr, {"v183_phmode": 1, "v183_phcal": 0})
        f_hz = float(base.vars["slice_freq_long"].value)
        for P in (530, -530):
            alt = mapped("v183", ppr, {"v183_phmode": 1, "v183_phcal": P})
            r0, r1 = rf_rows(base), rf_rows(alt)
            s0, s1 = signature(base), signature(alt)
            same_timing = [x["t"] for x in r0] == [x["t"] for x in r1] and s0["adc"] == s1["adc"] and s0["grad"] == s1["grad"]
            # k counts refocusing pulses (the excitation is k=0); command units are 1/1600 turn.
            measured = [((y["phase"]-x["phase"]) % PHASE_UNITS_PER_TURN) for x, y in zip(r0, r1)]
            expected = []
            acc0 = acc1 = 0
            for k in range(len(r0)):
                if k:
                    acc0 = (acc0 + round(f_hz) * (0 + base_window(base))) % 10_000_000 if k > 1 else (round(f_hz) * base_window(base)) % 10_000_000
                    acc1 = (acc1 + round(f_hz) * (P + base_window(base))) % 10_000_000 if k > 1 else (round(f_hz) * (P + base_window(base))) % 10_000_000
                expected.append(((-(acc1 // 6250)) - (-(acc0 // 6250))) % PHASE_UNITS_PER_TURN)
            mism = [k for k, (m, e) in enumerate(zip(measured, expected)) if min((m-e) % 1600, (e-m) % 1600) > 1]
            res["phcal_shift"][f"z{z}/P{P}"] = dict(slice_freq_hz=f_hz, timing_and_gradients_identical=same_timing,
                                                    measured_units=measured, expected_units=expected, mismatched_pulses=mism,
                                                    per_pulse_deg_model=360*f_hz*P*1e-7)
            if not same_timing:
                res["failures"].append(f"phcal {P} changes timing at z={z}")
            if mism:
                res["failures"].append(f"phcal {P} phase shift mismatch at z={z}, pulses {mism}")
    res["pass"] = not res["failures"]
    (OUT/"v183_events.json").write_text(json.dumps(res, indent=1, default=v182.json_default) + "\n", encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("static", "mode0", "failures", "pass")}, indent=1, default=v182.json_default))
    for k, v in res["phcal_shift"].items():
        print(k, "timing same:", v["timing_and_gradients_identical"], "mismatched:", v["mismatched_pulses"], "deg/pulse:", round(v["per_pulse_deg_model"], 2), "first units:", v["measured_units"][:5])


def base_window(it):
    return int(it.vars["tsel90"].value)*10 + 1800


if __name__ == "__main__":
    main()
