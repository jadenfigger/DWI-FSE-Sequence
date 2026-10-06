"""Read-only v192 source/moment audit. Does not generate scanner events.

Run from repository root: python docs/v19/v192_design_audit.py
The trapezoid calculations assume ideal linear ramps and the PPR calibration;
they are feasibility examples, not verified g3040_15.seq waveform integrals.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCANNER = ROOT / "scanner"
BASE = SCANNER / "FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl"
PPR = BASE.with_suffix(".ppr")
DRAFT = SCANNER / "FSE_dwi_CPMG_non_CPMG_twoTE-1.92.ppl"
EXPECTED_PPL = "3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2"
EXPECTED_PPR = "78c9845d090183d59cba956f36305e0e19d4a8dcdb3ae707062839159fd904da"
MARKER_BEGIN = b"\t/* [V192-GATE-BEGIN]"
MARKER_END = b"\t/* [V192-GATE-END] */\r\n"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_moment(cycles: float, slice_mm: float, calibration: int,
                 ramp_us: int, flat_us: int, crusher_dac: int,
                 max_dac: int = 32767) -> dict:
    if cycles <= 0 or slice_mm <= 0 or calibration <= 0:
        raise ValueError("cycles, slice thickness and calibration must be positive")
    if not 100 <= ramp_us <= 1000 or ramp_us % 10:
        raise ValueError("ramp must be 100..1000 us, multiple of 10")
    if flat_us <= 0 or flat_us > 5000 or flat_us * 50 % ramp_us:
        raise ValueError("flat must be 1..5000 us, exact multiple of ramp/50")
    if not 1 <= max_dac <= 32767 or abs(crusher_dac) > max_dac:
        raise ValueError("invalid DAC ceiling or baseline crusher")
    target = 1000 * cycles / slice_mm
    factor = calibration * (flat_us + ramp_us) / (32767 * 1000)
    nearest = round(target / factor)
    pre, post = crusher_dac - nearest, crusher_dac + nearest
    if max(abs(pre), abs(post), abs(nearest)) > max_dac:
        raise ValueError("recall/restoration plus crusher exceeds signed DAC limit")
    return {
        "status": "ideal-linear-ramp design calculation; not scanner verified",
        "cycles_across_slice": cycles, "slice_mm": slice_mm,
        "target_cycles_per_m": target, "moment_dac_nearest": nearest,
        "achieved_cycles_per_m": nearest * factor,
        "area_error_percent": 100 * (nearest * factor / target - 1),
        "ramp_us": ramp_us, "flat_us": flat_us,
        "separate_lobe_duration_us": flat_us + 2 * ramp_us,
        "baseline_crusher_dac": crusher_dac,
        "candidate_first_pre_crusher_dac": crusher_dac,
        "candidate_later_pre_crusher_dac": pre,
        "candidate_post_crusher_dac": post,
        "moment_contract": "first pre C; post C+D; restore -D after ADC (fused into subsequent pre C-D)",
        "logical_dac_feasible": True,
        "physical_oblique_sum_and_slew_verified": False,
    }


def main() -> None:
    baseline_hashes = {str(BASE.relative_to(ROOT)): digest(BASE),
                       str(PPR.relative_to(ROOT)): digest(PPR)}
    if digest(BASE) != EXPECTED_PPL or digest(PPR) != EXPECTED_PPR:
        raise RuntimeError("verified v18 input changed; re-review source before using audit")
    text = BASE.read_text(encoding="cp1252")
    includes = re.findall(r'#include\s+"([^"]+)"', text)
    dependencies = [{"name": name, "present": (SCANNER / name).is_file()}
                    for name in includes]
    libraries = [{"name": name, "present": Path(name).is_file()}
                 for name in re.findall(r'#use\s+\w+\s+"([^"]+)"', text)]
    draft = DRAFT.read_bytes()
    split = draft.index(b"/* [V192-V18-BODY-BEGIN] */\r\n")
    inherited = draft[split + len(b"/* [V192-V18-BODY-BEGIN] */\r\n"):]
    start = inherited.index(MARKER_BEGIN)
    end = inherited.index(MARKER_END, start) + len(MARKER_END)
    inherited = inherited[:start] + inherited[end:]
    if inherited != BASE.read_bytes():
        raise RuntimeError("v192 preserved body differs from verified v18")
    guard = "V192_METHOD_NOT_IMPLEMENTED_BLOCK.pph"
    if not draft.startswith(f'#include "{guard}"'.encode("ascii")):
        raise RuntimeError("v192 compiler gate missing")
    if (SCANNER / guard).exists():
        raise RuntimeError("v192 compile-stop guard unexpectedly exists")
    gate = draft.index(b"goto end;", split)
    if gate > draft.index(b'#include "tstex_15.pph"', split):
        raise RuntimeError("v192 runtime gate must precede tstex initialization")
    companion = DRAFT.with_suffix(".ppr").read_bytes()
    expected = PPR.read_bytes().replace(b":PPL FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl",
                                       b":PPL FSE_dwi_CPMG_non_CPMG_twoTE-1.92.ppl", 1)
    if companion != expected:
        raise RuntimeError("v192 PPR differs beyond reserved source pointer")
    anchors = ["NEWSHAPE_MAC(1", "tsel90 = rf_length", "slice_180_refocus =",
               "slice_180_refocus_diff =", "slice_list_rp =", "phase_90 = aqphase",
               "phase_180 = phase_90", "p90_mul =", "min_pre =", "min_post =",
               "te_a =", "te_b =", "te_balance_bl_esp =", "CREATE_MATRIX(fse_mat,",
               "MR3040_SetList( read_pre_list", "echo_loop:", "initiate(sample_period)",
               "PREPARE_NEXT_CRUSHER }", "nav_cnt == 0"]
    sites = {a: [i + 1 for i, line in enumerate(text.splitlines()) if a in line]
             for a in anchors}
    moment_examples = [check_moment(n, thk, 25447, 200, 1000, 5482)
                       for thk in (1, 6) for n in (2, 4)]
    rejected = []
    for label, args in [
        ("zero thickness", (2, 0, 25447, 200, 1000, 5482)),
        ("invalid ramp raster", (2, 1, 25447, 205, 1000, 5482)),
        ("flat outside gradient raster", (2, 1, 25447, 200, 1001, 5482)),
        ("combined DAC overflow", (40, 0.1, 25447, 200, 1000, 5482)),
    ]:
        try:
            check_moment(*args)
        except ValueError as exc:
            rejected.append({"case": label, "reason": str(exc)})
        else:
            raise RuntimeError(f"infeasible design unexpectedly accepted: {label}")
    result = {
        "status": "v192 METHOD NOT IMPLEMENTED; fail-closed source scaffold",
        "baseline_sha256": baseline_hashes,
        "v192_ppl_sha256": digest(DRAFT),
        "v192_ppr_sha256": digest(DRAFT.with_suffix(".ppr")),
        "v18_body_preserved": True, "ppr_pointer_only_change": True,
        "compiler_gate": True, "runtime_gate_before_tstex": True,
        "includes": dependencies, "libraries": libraries,
        "v18_line_anchors": sites, "ideal_moment_examples": moment_examples,
        "rejected_design_examples": rejected,
        "compilation": "not performed; missing compiler/libraries/tstex",
        "event_trace": "unavailable", "played_waveform_simulation": "not performed",
        "scanner_verification": "not performed",
    }
    output = ROOT / "docs/v19/v192_design_audit.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output.relative_to(ROOT)}; preserved baseline, two gates, four moment examples")


if __name__ == "__main__":
    main()
