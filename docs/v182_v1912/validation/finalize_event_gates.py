"""Combine the frozen full run with the targeted matrix-identity gate recheck.

The original full-run result remains immutable. No waveform or phase results
are recomputed or relaxed here; only two timestamp-sensitive identity flags
are replaced by the recorded RF/ADC/gradient/matrix-value comparison.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    raw_path = HERE / "event_gates_full_run.json"
    recheck_path = HERE / "v1912_identity_gate_recheck.json"
    raw = json.loads(raw_path.read_text())
    recheck = json.loads(recheck_path.read_text())
    expected_failures = {
        "v1912 nav0 differs from v1911 event signature",
        "v1912 nav1 differs from v1911 event signature",
    }
    assert set(raw["failures"]) == expected_failures
    assert raw["inputs_stable_during_run"]
    assert raw["validator_stable_during_run"]
    assert raw["v182_items2to4_control"]["stable_during_run"]
    assert recheck["pass"] and recheck["inputs_stable_during_run"]
    assert recheck["hashes_before"] == recheck["hashes_after"]
    assert sha(ROOT / "examples/validate_v182_v1912.py") == recheck["hashes_after"]["validator"]
    for version, digest in recheck["hashes_after"]["ppl"].items():
        assert digest == raw["input_sha256_after"][version]["ppl_sha256"]
    assert {case["nav_on"] for case in recheck["cases"]} == {0, 1}
    for case in recheck["cases"]:
        assert case["pass"] and case["physical_event_identity"]
        assert case["RF_identical"] and case["ADC_identical"]
        assert all(case["played_SPR_identical"].values())
        assert case["matrix_values_identical"]
        key = f"v1912/nav{case['nav_on']}"
        recorded = raw["mode_identity"][key]["signature_comparison"]
        assert recorded["rf"]["identical"] and recorded["adc"]["identical"]
        assert all(recorded[f"grad_{axis}"]["identical"] for axis in "SPR")
        assert raw["mode_identity"][key]["ppr_sha256"] == recheck["hashes_after"]["ppr"][f"v1912_nav{case['nav_on']}"]
        recorded["matrix_values_identical"] = True
        recorded["max_matrix_write_shift_us"] = case["max_matrix_write_shift_us"]
        recorded["physical_event_identity"] = True
        recorded["physical_event_identity_source"] = recheck_path.name
    raw["gate_correction"] = {
        "scope": "Only v1912 nav0/nav1 physical identity gates; all other full-run evidence unchanged.",
        "reason": "Matrix register timestamps differ by 0.8 us inside padded inactive intervals; matrix values and played RF/ADC/S/P/R events match.",
        "full_run_file": raw_path.name,
        "full_run_sha256": sha(raw_path),
        "full_run_failures": sorted(expected_failures),
        "targeted_recheck_file": recheck_path.name,
        "targeted_recheck_sha256": sha(recheck_path),
        "corrected_validator_sha256": recheck["hashes_after"]["validator"],
        "finalizer_sha256": sha(Path(__file__)),
        "full_run_validator_fields_retained": True,
    }
    raw["failures"] = []
    raw["event_gates_pass"] = True
    (HERE / "event_gates.json").write_text(json.dumps(raw, indent=2) + "\n")
    print("Final event report PASS; original full-run and targeted recheck provenance retained.")


if __name__ == "__main__":
    main()
