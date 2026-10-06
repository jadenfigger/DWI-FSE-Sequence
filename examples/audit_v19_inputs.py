"""Inventory real v18 inputs and fail-closed v19 reservations; no event emulation.

Run from any directory: python examples/audit_v19_inputs.py
Only writes docs/v19/input_audit.json. Missing dependencies are data, not a
successful compilation. A baseline hash mismatch or an unsafe reservation fails.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "scanner"
UTILITIES = SCANNER / "utilities"
STEM = "FSE_dwi_CPMG_non_CPMG_twoTE-"
EXPECTED = {
    "1.8.ppl": "3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2",
    "1.8.ppr": "78c9845d090183d59cba956f36305e0e19d4a8dcdb3ae707062839159fd904da",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(path):
    return {"path": str(path), "exists": path.is_file(),
            "sha256": digest(path) if path.is_file() else None,
            "bytes": path.stat().st_size if path.is_file() else None}


def audit():
    failures = []
    baseline = {}
    for suffix, expected in EXPECTED.items():
        path = SCANNER / (STEM + suffix)
        item = record(path)
        item["expected_sha256"] = expected
        item["unchanged"] = item["sha256"] == expected
        baseline[suffix] = item
        if not item["unchanged"]:
            failures.append(f"Baseline changed or missing: {path}")
    source = (SCANNER / (STEM + "1.8.ppl")).read_text(encoding="latin1")
    includes, visited = [], set()

    def collect(text, parent):
        for name in re.findall(r'^\s*#include\s+"([^"]+)"', text, re.M):
            # This is a lexical inventory, not a PPL preprocessor.
            path = parent / name
            if not path.is_file() and (UTILITIES / name).is_file():
                path = UTILITIES / name
            item = record(path)
            item["declared_name"] = name
            includes.append(item)
            if path.is_file() and path not in visited:
                visited.add(path)
                collect(path.read_text(encoding="latin1"), path.parent)

    collect(source, SCANNER)
    libraries = []
    for board, declared, alias in re.findall(
            r'^\s*#use\s+(\w+)\s+"([^"]+)"\s+(\w+)', source, re.M):
        # Keep exact vendor path. Do not replace a vendor .seq with Pulseq.
        item = record(Path(declared))
        item.update(board=board, declared_path=declared, alias=alias)
        local = UTILITIES / declared.replace("\\", "/").split("/")[-1]
        item["uploaded_local_copy"] = record(local)
        item["available_for_local_inspection"] = local.is_file() or item["exists"]
        libraries.append(item)
    companion = (SCANNER / (STEM + "1.8.ppr")).read_text(encoding="latin1")
    ppr_pointer = re.search(r'^:PPL\s+(.+)$', companion, re.M).group(1).strip()
    acquisitions = []
    for path in sorted((ROOT / "experiments").glob("*v18*/*.ppr")):
        text = path.read_text(encoding="latin1")
        pointer = re.search(r'^:PPL\s+(.+)$', text, re.M)
        acquisitions.append({**record(path), "ppl_pointer": pointer.group(1).strip()
                             if pointer else None})
    references = [record(SCANNER / "EVO Pulse Sequence Program Manual.pdf")]
    references += [record(Path.home() / "Downloads" / name) for name in
                   ("Gibbons_2017.pdf", "mrm26971-sup-0001-suppinfo01.pdf")]
    reservations = []
    for version in ("1.91", "1.92"):
        ppl = SCANNER / (STEM + version + ".ppl")
        ppr = SCANNER / (STEM + version + ".ppr")
        item = {"version": version, "ppl": record(ppl), "ppr": record(ppr)}
        if ppl.is_file():
            text = ppl.read_text(encoding="latin1")
            first_directive = re.search(r'^\s*(#\w+.*)$', text, re.M)
            item["first_directive"] = first_directive.group(1) if first_directive else None
            gate = re.fullmatch(r'#include\s+"(V19[12]_[^"]+\.pph)"',
                                first_directive.group(1) if first_directive else "")
            item["pre_library_compile_gate"] = bool(gate and
                                                       not (SCANNER / gate.group(1)).exists())
            item["compile_gate_semantics"] = "Intentionally missing include; documented directive, vendor diagnostic untested"
            item["reservation_header"] = "NOT IMPLEMENTED" in text[:1000]
            if item["reservation_header"] and not item["pre_library_compile_gate"]:
                failures.append(f"Reservation lacks unresolved first-directive include gate: {ppl}")
        if ppr.is_file():
            text = ppr.read_text(encoding="latin1")
            pointer = re.search(r'^:PPL\s+(.+)$', text, re.M)
            item["ppr_pointer"] = pointer.group(1).strip() if pointer else None
            if item["ppr_pointer"] != ppl.name:
                failures.append(f"Wrong reservation PPR pointer: {ppr}")
            expected_ppr = re.sub(r'^:PPL[^\r\n]*', ':PPL ' + ppl.name, companion, count=1)
            item["baseline_parameters_preserved"] = text == expected_ppr
            if item.get("reservation_header") and not item["baseline_parameters_preserved"]:
                failures.append(f"Reservation unexpectedly changed baseline parameters: {ppr}")
        reservations.append(item)
    result = {
        "scope": "Lexical input inventory and preservation checks; not compilation or played-event validation",
        "baseline": baseline, "companion_ppr_pointer": ppr_pointer,
        "historical_source_identity": "PPR path labels identify version; acquisition-time PPL bytes not embedded or verified",
        "includes": includes, "libraries": libraries, "references": references,
        "acquisition_sidecar_pprs": acquisitions,
        "compiler_path_probe": {name: shutil.which(name) for name in ("ppl", "pplc", "pfgen", "specsim")},
        "missing_includes": [x["declared_name"] for x in includes if not x["exists"]],
        "missing_libraries": [x["declared_path"] for x in libraries if not x["exists"]],
        "missing_uploaded_libraries": [x["declared_path"] for x in libraries if not x["available_for_local_inspection"]],
        "upload_directory": str(UTILITIES),
        "scanner_tree_listing": record(UTILITIES / "tree_output.txt"),
        "reservations": reservations, "failures": failures,
        "status": {"method_implemented": "See per-method source and final review; inventory does not infer implementation",
                   "vendor_compiled": False,
                   "played_event_trace_verified": False, "finite_rf_validated": False,
                   "scanner_verified": False},
        "script_sha256": digest(Path(__file__)),
    }
    output = ROOT / "docs/v19/input_audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print(f"v18 unchanged: {all(x['unchanged'] for x in baseline.values())}")
    print(f"Missing local inputs: {len(result['missing_includes'])} include(s), {len(result['missing_uploaded_libraries'])} libraries")
    print(f"Preservation/gate failures: {len(failures)}")
    print(f"Inventory: {output}")
    if failures:
        raise SystemExit("\n".join(failures))


if __name__ == "__main__":
    audit()
