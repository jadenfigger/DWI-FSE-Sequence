"""Audit the intentionally blocked v191 reservation against supplied v18 bytes.

This is a source-preservation/dependency audit, not a PPL compiler or event mapper.
No hardware events or Bloch results are inferred from unavailable WavEd libraries.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "scanner"
BASE = "FSE_dwi_CPMG_non_CPMG_twoTE-1.8"
TARGET = "FSE_dwi_CPMG_non_CPMG_twoTE-1.91"
EXPECTED = {
    ".ppl": "3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2",
    ".ppr": "78c9845d090183d59cba956f36305e0e19d4a8dcdb3ae707062839159fd904da",
}
HEADER = (
    "/* V191 RESERVED SOURCE - SS-MGOT MECHANISM NOT IMPLEMENTED.\r\n"
    "   This file retains supplied v18 for review; it is NOT a runnable ss-MGOT.\r\n"
    "   Validated RF/gradient assets, tstex_15.pph, compiler traces and scanner\r\n"
    "   calibration are required. See docs/v19/v191_implementation.md.\r\n"
    "   The following deliberately absent include blocks compilation. Do not\r\n"
    "   create an empty include or remove either gate to enable this source.\r\n"
    "*/\r\n"
    '#include "V191_SS_MGOT_NOT_IMPLEMENTED_REQUIRES_VALIDATED_RF.pph"\r\n'
    "\r\n"
).encode("ascii")
ANCHOR = b"#ifdef MAINSGATE\r\n\tbad_cnt = 0;"
RUNTIME_GATE = (
    '\tprintf("V191 SS-MGOT NOT IMPLEMENTED: validated RF/gradient assets and event traces required.\\n");\r\n'
    "\tgoto end;\r\n\r\n"
).encode("ascii")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def audit() -> dict:
    sources = {}
    original = {}
    for suffix, expected in EXPECTED.items():
        path = SCANNER / (BASE + suffix)
        original[suffix] = path.read_bytes()
        actual = digest(original[suffix])
        if actual != expected:
            raise ValueError(f"Supplied v18 changed: {path} ({actual})")
        sources[str(path.relative_to(ROOT))] = actual
    if original[".ppl"].count(ANCHOR) != 1:
        raise ValueError("Runtime gate insertion anchor must occur exactly once")
    expected_ppl = HEADER + original[".ppl"].replace(ANCHOR, RUNTIME_GATE + ANCHOR, 1)
    old_ppl_line = (":PPL " + BASE + ".ppl").encode("ascii")
    new_ppl_line = (":PPL " + TARGET + ".ppl").encode("ascii")
    if original[".ppr"].count(old_ppl_line) != 1:
        raise ValueError("Companion PPR must identify supplied v18 exactly once")
    expected_ppr = original[".ppr"].replace(old_ppl_line, new_ppl_line, 1)
    for suffix, expected in ((".ppl", expected_ppl), (".ppr", expected_ppr)):
        path = SCANNER / (TARGET + suffix)
        actual = path.read_bytes()
        if actual != expected:
            raise ValueError(f"Reserved source unexpectedly differs: {path}")
        sources[str(path.relative_to(ROOT))] = digest(actual)
    compile_gate = SCANNER / "V191_SS_MGOT_NOT_IMPLEMENTED_REQUIRES_VALIDATED_RF.pph"
    if compile_gate.exists():
        raise ValueError("Compile gate must remain deliberately absent")
    include_paths = ["stdfn_15.pph", "var_20.pph", "offst_20.pph", "m3040_15.pph", "m3031_15.pph", "tstex_15.pph"]
    dependencies = {}
    for name in include_paths:
        path = SCANNER / name
        if not path.is_file():
            path = SCANNER / "utilities" / name
        dependencies[name] = {"present": path.is_file(), "path": str(path.relative_to(ROOT)), "sha256": digest(path.read_bytes()) if path.is_file() else None}
    # This text location proves the fallback gate precedes source hardware setup.
    gate_pos = expected_ppl.index(RUNTIME_GATE)
    hardware_pos = expected_ppl.index(b"\t\tuserout(pdd_rx_mask);")
    if gate_pos >= hardware_pos:
        raise ValueError("Runtime gate is not before first hardware statement")
    return {
        "scope": "source preservation and explicit execution blocking only",
        "ss_mgot_mechanism_implemented": False,
        "vendor_compilation_attempted": False,
        "played_event_mapping_verified": False,
        "ppl_scheduled_waveforms_simulated": False,
        "scanner_verified": False,
        "supplied_v18_hashes_match": True,
        "v191_ppl_only_header_and_gates_changed": True,
        "v191_ppr_only_ppl_reference_changed": True,
        "compile_gate_deliberately_absent": True,
        "runtime_gate_before_hardware_statement": True,
        "input_and_output_sha256": sources,
        "includes": dependencies,
    }


if __name__ == "__main__":
    result = audit()
    target = ROOT / "docs" / "v19" / "v191_source_audit.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
