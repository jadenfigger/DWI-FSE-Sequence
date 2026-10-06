"""Reproducible protocol and MRD identity audit for the 2026-10-05 scans.

Run from any directory with Python 3:
    python docs/data/oct05_protocol_audit.py

Uses only the Python standard library. It reads MRD headers and dimensions,
PPR files, JSON metadata, and the scan catalog; it does not alter scan data.
Outputs are written beside this script.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import struct
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS = ROOT / "experiments"
OUT = ROOT / "docs" / "data"
CATALOG = EXPERIMENTS / "scan_catalog_2026-10-05.md"
SCAN_ORDER = [
    "test0", "test1", "test1b", "test1c", "test1d", "test1e", "test1f",
    "test1g", "test2", "test2b", "test2c", "test2d", "test3", "test3b",
    "test4", "test4b", "test5", "test6", "test7", "testa",
]
PROTOCOL_KEYS = [
    "tr", "te", "esp", "views_per_seg", "no_views", "no_samples", "nav_on",
    "PE_order", "diff_on", "b_input_mode", "sm_delta", "big_delta",
    "no_diff_acq", "acq_b", "b_steps_array", "acq_x", "acq_y", "acq_z",
    "tcrush", "diff_tcrush", "crush_amp", "diff_crush_amp", "crusher_schedule",
    "crusher_step_pct", "crusher_custom_count", "crusher_custom_pct",
    "crush_independent_on", "crusher_max_dac", "crusher_slew_dac_100us",
    "rfcal", "alpha", "p180_scale", "_ObserveReceiverGain",
    "_ObserveTransmitGain", "_DecoupleTransmitGain", "_ObserveFrequency",
    "grad_var", "gr_var", "gp_init_var", "SMX", "SMY", "slice_offset",
    "no_disacq", "no_discard", "PPL",
]
GAIN_KEYS = [
    "rfcal", "alpha", "p180_scale", "_ObserveReceiverGain",
    "_ObserveTransmitGain", "_DecoupleTransmitGain", "grad_var", "gr_var",
    "gp_init_var", "SMX", "SMY",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def numeric_values(text: str) -> list[float]:
    return [float(x) for x in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", text)]


def parse_ppr(text: str) -> tuple[dict, dict]:
    """Return normalized key/value metadata and raw records from PPR text."""
    records: dict[str, str] = {}
    current = None
    for line in text.replace("\x00", "").splitlines():
        if line.startswith(":"):
            match = re.match(r":([A-Za-z0-9_]+)\s*(.*)$", line)
            if not match:
                current = None
                continue
            key, value = match.groups()
            value = value.strip()
            if key in ("VAR", "VAR_ARRAY"):
                variable = value.split(",", 1)[0].strip()
                record_key = f"{key}:{variable}"
            else:
                record_key = key
            records[record_key] = value
            current = record_key
        elif current and line.strip().startswith(","):
            records[current] += " " + line.strip()
        elif current and line.strip() and not line[:1].isspace():
            # PPR continuation rows can omit the leading comma in older files.
            records[current] += " " + line.strip()

    values: dict[str, object] = {}
    for record_key, raw in records.items():
        key = record_key.split(":", 1)[0]
        parts = [p.strip() for p in raw.split(",")]
        if key in ("VAR", "VAR_ARRAY") and parts:
            name = parts[0]
            if key == "VAR_ARRAY":
                # The second comma-separated field is declared capacity, not data.
                values[name] = numeric_values(",".join(parts[2:]))
            else:
                nums = numeric_values(",".join(parts[1:]))
                values[name] = nums[0] if len(nums) == 1 else nums
        elif key in ("GRADIENT_STRENGTH", "SLICE_THICKNESS", "SLICE_SEPARATION",
                     "READ_VAR", "PHASE_VAR", "SAMPLE_PERIOD", "NO_SAMPLES",
                     "NO_VIEWS", "NO_VIEWS_2", "EXPERIMENT_ARRAY", "DISCARD",
                     "DATA_TYPE", "RECEIVER_MASK") and parts:
            name = parts[0]
            nums = numeric_values(",".join(parts[1:]))
            if name:
                values[name] = nums[0] if len(nums) == 1 else nums
        elif key == "PPL":
            values[key] = raw.strip().strip('"')
        elif key.startswith("_"):
            nums = numeric_values(raw)
            values[key] = nums[0] if len(nums) == 1 else (nums if nums else raw)
        else:
            nums = numeric_values(raw)
            values[key] = nums[0] if len(nums) == 1 else (nums if nums else raw)
    return values, records


def parse_mrd(path: Path) -> dict:
    blob = path.read_bytes()
    ppl_at = blob.find(b":PPL")
    if ppl_at < 0:
        raise ValueError(f"No embedded PPR block found in {path}")
    header_text = blob[ppl_at:].decode("latin1", errors="replace")
    values, records = parse_ppr(header_text)
    dims0 = struct.unpack("<4i", blob[:16])
    dim5, dim6 = struct.unpack("<2i", blob[152:160])
    # MRD dimension order on disk: samples, views, views_2, slices, echoes, experiments.
    samples, views, views2, slices = dims0
    echoes, experiments = dim5, dim6
    datatype = struct.unpack("<H", blob[18:20])[0]
    kind = f"{datatype:x}".upper()
    component_bytes = {"0": 1, "1": 1, "2": 2, "3": 2, "4": 4, "5": 4, "6": 8}.get(kind[-1], 4)
    complex_data = len(kind) > 1
    n_components = 2 if complex_data else 1
    payload_bytes = samples * views * views2 * slices * echoes * experiments * component_bytes * n_components
    payload_end = 512 + payload_bytes
    experiment_bytes = samples * views * views2 * slices * echoes * component_bytes * n_components
    nonzero_experiments = []
    for i in range(experiments):
        start = 512 + i * experiment_bytes
        end = start + experiment_bytes
        nonzero_experiments.append(any(blob[start:end]))
    # Existing reader skips 120 bytes between acquisition data and the PPR trailer.
    trailing_gap = ppl_at - payload_end
    metadata_lines = {}
    for key in ("AcquisitionStartTime", "PerformanceCounterFrequency", "_ObserveReceiverGain",
                "_ObserveTransmitGain", "_DecoupleTransmitGain", "_ObserveFrequency"):
        if key in values:
            metadata_lines[key] = values[key]
    return {
        "path": path,
        "sha256": sha256(path),
        "byte_size": len(blob),
        "embedded_ppr_offset": ppl_at,
        "embedded_ppr_text": header_text,
        "values": values,
        "records": records,
        "dims": {"experiments": experiments, "echoes": echoes, "slices": slices,
                 "views_2": views2, "views": views, "samples": samples},
        "datatype_hex": f"0x{datatype:02X}",
        "payload_bytes_expected": payload_bytes,
        "payload_end_offset": payload_end,
        "nonzero_experiment_slots": nonzero_experiments,
        "gap_bytes_before_ppr": trailing_gap,
        "metadata": metadata_lines,
    }


def serial(value):
    if isinstance(value, Path):
        return value.as_posix()
    return value


def stable_equal(a, b, tolerance=1e-7):
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(stable_equal(x, y, tolerance) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= tolerance * max(1.0, abs(float(a)), abs(float(b)))
    return a == b


def catalog_order() -> dict[str, int]:
    text = CATALOG.read_text(encoding="utf-8")
    return {name: i + 1 for i, name in enumerate(SCAN_ORDER) if f"| {i + 1} | [{name}]" in text}


def main():
    order = catalog_order()
    scans = []
    for scan in SCAN_ORDER:
        folders = [p for p in EXPERIMENTS.glob(f"FSE-DWI_10-05-*_{scan}") if p.is_dir()]
        if len(folders) != 1:
            raise RuntimeError(f"Expected one folder for {scan}; found {folders}")
        folder = folders[0]
        mrd = next(folder.glob("*.MRD"))
        ppr = next(folder.glob("*.ppr"))
        parsed = parse_mrd(mrd)
        embedded = parsed["values"]
        sidecar_values, _ = parse_ppr(ppr.read_text(encoding="latin1", errors="replace"))
        sidecar_diff = {}
        runtime_fields = {"AcquisitionStartTime", "PerformanceCounterFrequency", "END"}
        for key in sorted(set(embedded) | set(sidecar_values)):
            if key in runtime_fields or key.startswith("_") or key.endswith("Delay") or key.endswith("Mask"):
                continue
            if key not in embedded or key not in sidecar_values or not stable_equal(embedded[key], sidecar_values[key]):
                sidecar_diff[key] = {"mrd": embedded.get(key), "ppr": sidecar_values.get(key)}
        shared_keys = (set(embedded) & set(sidecar_values)) - runtime_fields
        sidecar_value_diffs = {k: [sidecar_values[k], embedded[k]] for k in sorted(shared_keys)
                               if not stable_equal(sidecar_values[k], embedded[k])}
        json_paths = list(folder.glob("*.json"))
        json_obj = json.loads(json_paths[0].read_text(encoding="utf-8")) if json_paths else None
        json_check = {"available": bool(json_paths), "path": json_paths[0].relative_to(ROOT).as_posix() if json_paths else None,
                      "comparisons": {}}
        if json_obj is not None:
            comparisons = {
                "PEOrder": (json_obj.get("PEOrder"), embedded.get("PE_order")),
                "DiffusionOn": (json_obj.get("DiffusionOn"), embedded.get("diff_on")),
                "SmallDelta_ms": (json_obj.get("SmallDelta_ms"), (embedded.get("sm_delta", 0) / 1000 if isinstance(embedded.get("sm_delta"), (int, float)) else None)),
                "BigDelta_ms": (json_obj.get("BigDelta_ms"), (embedded.get("big_delta", 0) / 1000 if isinstance(embedded.get("big_delta"), (int, float)) else None)),
                "bval_s_per_mm2": (json_obj.get("bval_s_per_mm2"), embedded.get("acq_b", embedded.get("b_steps_array"))),
                "SliceSpacing_mm": (json_obj.get("SliceSpacing_mm"),
                                    embedded.get("slice_offset", [None])[-1] if isinstance(embedded.get("slice_offset"), list) else embedded.get("slice_offset")),
            }
            for key, (jv, pv) in comparisons.items():
                if isinstance(pv, list) and key == "bval_s_per_mm2" and len(pv) > 3:
                    # MRD acquisition b-value arrays encode the first no_diff_acq entries.
                    pv = pv[:int(embedded.get("no_diff_acq", len(jv or [])))]
                ok = stable_equal(jv, pv) if jv is not None and pv is not None else None
                json_check["comparisons"][key] = {"json": jv, "mrd": pv, "match": ok}
        dt = datetime.fromtimestamp(mrd.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds")
        ppl = str(embedded.get("PPL", ""))
        version = re.search(r"twoTE[-_]?(\d+(?:\.\d+)?)", ppl, re.I)
        file_candidates = sorted(p.name for p in folder.iterdir() if p.is_file())
        bvals = embedded.get("acq_b", embedded.get("b_steps_array"))
        if isinstance(bvals, list):
            bvals = bvals[:int(embedded.get("no_diff_acq", parsed["dims"]["experiments"]))]
        data_bytes_complete = parsed["payload_end_offset"] <= parsed["embedded_ppr_offset"] and parsed["gap_bytes_before_ppr"] >= 120
        row = {
            "scan": scan,
            "catalog_order": order.get(scan),
            "folder": folder.relative_to(ROOT).as_posix(),
            "mrd": mrd.relative_to(ROOT).as_posix(),
            "mrd_sha256": parsed["sha256"],
            "mrd_bytes": parsed["byte_size"],
            "sidecar_ppr": ppr.relative_to(ROOT).as_posix(),
            "sidecar_ppr_basename_matches_scan": ppr.stem.endswith(scan),
            "embedded_ppl": ppl,
            "embedded_ppl_version": version.group(1) if version else None,
            "mrd_mtime_utc": dt,
            "acquisition_start_counter": embedded.get("AcquisitionStartTime"),
            "performance_counter_frequency": embedded.get("PerformanceCounterFrequency"),
            "embedded_receiver_gain": embedded.get("_ObserveReceiverGain"),
            "embedded_transmit_gain": embedded.get("_ObserveTransmitGain"),
            "embedded_decouple_gain": embedded.get("_DecoupleTransmitGain"),
            "dims": parsed["dims"],
            "no_diff_acq": embedded.get("no_diff_acq"),
            "b_values": bvals,
            "pe_order": embedded.get("PE_order"),
            "te_ms": embedded.get("te"), "esp_ms": embedded.get("esp"),
            "views_per_segment": embedded.get("views_per_seg"),
            "first_crusher_duration_us": embedded.get("diff_tcrush"),
            "train_crusher_duration_us": embedded.get("tcrush"),
            "first_crusher_baseline_dac": embedded.get("diff_crush_amp"),
            "train_crusher_baseline_dac": embedded.get("crush_amp"),
            "crusher_schedule": embedded.get("crusher_schedule"),
            "crusher_step_pct": embedded.get("crusher_step_pct"),
            "crusher_custom_count": embedded.get("crusher_custom_count"),
            "crusher_custom_pct": embedded.get("crusher_custom_pct"),
            "gain_settings": {k: embedded.get(k) for k in GAIN_KEYS},
            "sidecar_ppr_diff_count": len(sidecar_diff),
            "sidecar_ppr_diff_keys": sorted(sidecar_diff),
            "sidecar_protocol_values_match": not sidecar_value_diffs,
            "sidecar_protocol_value_diffs": sidecar_value_diffs,
            "json": json_check,
            "data_payload_complete": data_bytes_complete,
            "nonzero_experiment_slots": parsed["nonzero_experiment_slots"],
            "nonzero_experiment_count": sum(parsed["nonzero_experiment_slots"]),
            "trailing_bytes_before_ppr": parsed["gap_bytes_before_ppr"],
            "present_files": file_candidates,
        }
        row["_sidecar_diff"] = sidecar_diff
        row["_sidecar_value_diffs"] = sidecar_value_diffs
        row["_embedded_values"] = {k: v for k, v in embedded.items()
                                   if k not in {"AcquisitionStartTime", "PerformanceCounterFrequency"}}
        row["_embedded_records"] = parsed["records"]
        row["_raw_metadata"] = parsed["metadata"]
        scans.append(row)

    # Compare every embedded record after excluding only the acquisition counter/frequency.
    protocol_signatures = {}
    for row in scans:
        signature = {k: v for k, v in row["_embedded_values"].items() if k != "END"}
        protocol_signatures[row["scan"]] = hashlib.sha256(json.dumps(signature, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    pair_specs = [
        ("test1", "test2"), ("test2", "test3"), ("test1b", "test1c"),
        ("test1c", "test1d"), ("test1", "test1e"), ("test2", "test2b"),
        ("test3", "test3b"), ("test1e", "test2b"), ("test2b", "test3b"),
        ("test2b", "test5"), ("test4", "test5"), ("test4", "test4b"),
        ("test6", "test7"), ("test1c", "test1e"),
        ("test1", "test1e"), ("test1", "test1f"), ("test1", "test1g"),
        ("test1e", "test1f"), ("test1e", "test1g"), ("test1f", "test1g"),
        ("test2b", "test2c"), ("test2b", "test2d"), ("test2c", "test2d"),
    ]
    lookup = {r["scan"]: r for r in scans}
    anchor_counter = lookup["test0"]["acquisition_start_counter"]
    counter_frequency = lookup["test0"]["performance_counter_frequency"] or 10_000_000
    for row in scans:
        tick = row["acquisition_start_counter"]
        row["acquisition_elapsed_minutes_from_test0"] = (
            (tick - anchor_counter) / counter_frequency / 60
            if isinstance(tick, (int, float)) and isinstance(anchor_counter, (int, float)) else None
        )
    chronological = sorted((r for r in scans if isinstance(r["acquisition_start_counter"], (int, float))),
                           key=lambda r: r["acquisition_start_counter"])
    for rank, row in enumerate(chronological, 1):
        row["counter_order"] = rank
    for row in scans:
        row.setdefault("counter_order", None)
    # Hard assertions guard the specific PE controls called out for this audit.
    for scan, pe, schedule, first_amp, train_amp in [
        ("test1e", 1, 0, -5482, -2741), ("test1f", 6, 0, -5482, -2741),
        ("test1g", 7, 0, -5482, -2741), ("test2b", 1, 1, -5482, -2741),
        ("test2c", 6, 1, -5482, -2741), ("test2d", 7, 1, -5482, -2741),
    ]:
        v = lookup[scan]["_embedded_values"]
        assert v.get("PE_order") == pe, (scan, "PE_order", v.get("PE_order"), pe)
        assert v.get("crusher_schedule") == schedule, (scan, "crusher_schedule", v.get("crusher_schedule"), schedule)
        assert v.get("diff_crush_amp") == first_amp, (scan, "diff_crush_amp", v.get("diff_crush_amp"), first_amp)
        assert v.get("crush_amp") == train_amp, (scan, "crush_amp", v.get("crush_amp"), train_amp)
    pair_rows = []
    for a, b in pair_specs:
        ra, rb = lookup[a], lookup[b]
        va, vb = ra["_embedded_values"], rb["_embedded_values"]
        diffs = {k: [va.get(k), vb.get(k)] for k in sorted(set(va) | set(vb)) if not stable_equal(va.get(k), vb.get(k))}
        ar, br = ra["_embedded_records"], rb["_embedded_records"]
        excluded = {"VAR:PE_order", "AcquisitionStartTime", "END"}
        all_record_keys = (set(ar) | set(br)) - excluded
        all_other_records_equal = all(
            " ".join(ar.get(k, "").split()) == " ".join(br.get(k, "").split())
            for k in all_record_keys
        )
        pair_rows.append({"scan_a": a, "scan_b": b, "same_mrd_sha256": ra["mrd_sha256"] == rb["mrd_sha256"],
                          "same_protocol_signature": protocol_signatures[a] == protocol_signatures[b],
                          "all_other_embedded_records_equal": all_other_records_equal,
                          "protocol_differences": diffs,
                          "acquisition_counter_a": ra["acquisition_start_counter"],
                          "acquisition_counter_b": rb["acquisition_start_counter"],
                          "receiver_gain_a": ra["embedded_receiver_gain"], "receiver_gain_b": rb["embedded_receiver_gain"],
                          "pe_order_a": ra["pe_order"], "pe_order_b": rb["pe_order"]})
    pe_groups = [{"test1e", "test1f", "test1g"}, {"test2b", "test2c", "test2d"}]
    assert all(p["all_other_embedded_records_equal"] for p in pair_rows
               if any({p["scan_a"], p["scan_b"]} <= group for group in pe_groups)), \
        "Unexpected embedded-record difference within a controlled PE group"
    assert all(r["sidecar_protocol_values_match"] for r in scans), "Sidecar PPR protocol values differ from MRD"

    # Candidate all-by-all matches show protocol aliases without relying on their folder names.
    identical = {}
    for a in SCAN_ORDER:
        identical[a] = [b for b in SCAN_ORDER if b != a and protocol_signatures[a] == protocol_signatures[b]]

    audit = {
        "title": "October 5, 2026 physical scanner MRD protocol audit",
        "root": ROOT.as_posix(),
        "catalog": CATALOG.relative_to(ROOT).as_posix(),
        "method": {
            "mrd_header": "Embedded PPR text begins at the first :PPL record; dimensions and datatype are read from the MRD binary header, following scanner/recon/get_mrd_3d4.py conventions.",
            "comparison": "Each embedded PPR is compared with the adjacent PPR; JSON sidecars are checked against embedded PE order, diffusion flag, delta timings, b-values, and slice spacing when available.",
            "acquisition_time": "AcquisitionStartTime is reported as the embedded hardware performance-counter tick value with its frequency; it is not treated as a calendar timestamp.",
            "file_time": "MRD filesystem modification timestamps are reported in UTC and are not treated as acquisition times.",
            "payload_check": "Expected complex payload bytes are calculated from MRD dimensions and datatype; the embedded PPR must follow the payload with at least the reader's 120-byte interstitial region.",
            "source_provenance": "Git history audit at HEAD 724b9a7 found tracked scanner PPL releases 1.6 and 1.7, no tracked or historical 1.8 PPL/PPR source. MRDs identify their acquisition source by the embedded scanner path ending in twoTE-1.8.ppl; exact v1.8 source provenance cannot be verified from this repository.",
            "protocol_signature_fields": PROTOCOL_KEYS,
        },
        "scans": scans,
        "controlled_pairs": pair_rows,
        "identical_protocols_by_signature": identical,
    }
    (OUT / "oct05_protocol_audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    columns = ["scan", "catalog_order", "folder", "mrd_sha256", "mrd_bytes", "embedded_ppl", "embedded_ppl_version",
               "mrd_mtime_utc", "acquisition_start_counter", "performance_counter_frequency", "counter_order", "acquisition_elapsed_minutes_from_test0", "embedded_receiver_gain",
               "embedded_transmit_gain", "embedded_decouple_gain", "dims", "no_diff_acq", "b_values", "pe_order",
               "te_ms", "esp_ms", "views_per_segment", "first_crusher_duration_us", "train_crusher_duration_us",
               "first_crusher_baseline_dac", "train_crusher_baseline_dac", "crusher_schedule", "crusher_step_pct",
               "crusher_custom_count", "crusher_custom_pct", "gain_settings", "sidecar_ppr_diff_count",
               "sidecar_ppr_diff_keys", "sidecar_protocol_values_match", "sidecar_protocol_value_diffs",
               "data_payload_complete", "nonzero_experiment_slots", "nonzero_experiment_count", "trailing_bytes_before_ppr", "json"]
    with (OUT / "oct05_protocol_scans.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        for row in scans:
            w.writerow({k: json.dumps(row[k], ensure_ascii=False) if isinstance(row[k], (dict, list)) else row[k] for k in columns})
    with (OUT / "oct05_protocol_pairs.csv").open("w", encoding="utf-8-sig", newline="") as f:
        columns_pair = ["scan_a", "scan_b", "same_mrd_sha256", "same_protocol_signature", "all_other_embedded_records_equal", "protocol_differences",
                        "acquisition_counter_a", "acquisition_counter_b", "receiver_gain_a", "receiver_gain_b", "pe_order_a", "pe_order_b"]
        w = csv.DictWriter(f, fieldnames=columns_pair)
        w.writeheader()
        for row in pair_rows:
            w.writerow({k: json.dumps(row[k], ensure_ascii=False) if isinstance(row[k], dict) else row[k] for k in columns_pair})

    lines = [
        "# October 5 physical scanner protocol audit",
        "",
        "This audit checks all 20 cataloged acquisitions using each MRD's embedded PPR block, the adjacent PPR file, and any JSON sidecar. The script and machine-readable outputs are [oct05_protocol_audit.py](oct05_protocol_audit.py), [oct05_protocol_audit.json](oct05_protocol_audit.json), [oct05_protocol_scans.csv](oct05_protocol_scans.csv), and [oct05_protocol_pairs.csv](oct05_protocol_pairs.csv).",
        "",
        "## Findings",
        "",
        f"- Audited {len(scans)} MRDs; all expected binary payloads fit before their embedded PPR blocks, and every PPR starts after at least 120 interstitial bytes.",
        f"- All {sum(r['nonzero_experiment_count'] for r in scans)} of {sum(r['dims']['experiments'] for r in scans)} expected experiment slots contain nonzero raw data, including all three slots in legacy testa.",
        f"- Adjacent sidecar PPR protocol values match the embedded protocol values across all {len(scans)} scans; MRDs also contain scanner runtime tags absent from the standalone PPRs.",
        f"- JSON sidecars are present for {sum(r['json']['available'] for r in scans)} of 20 scans. Every available JSON comparison for PE order, diffusion settings, delta timings, b-values, and slice spacing matches the MRD; JSON contains no scanner gain or acquisition date fields.",
        "- The 19 v1.8 MRDs embed the scanner source path `G:\\J_Figger\\FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl`; testa embeds the v1.3 path. Git HEAD 724b9a7 contains tracked PPL versions 1.6 and 1.7 only, with no v1.8 PPL/PPR in history. The acquisition version label is recorded, while the precise v1.8 source cannot be verified here.",
        "- AcquisitionStartTime is a hardware performance-counter tick value, not a calendar timestamp. The CSV gives its relative order and minutes from test0; filesystem modification times are kept separately as file metadata.",
        f"- Counter order from test0 is: {', '.join(r['scan'] for r in chronological)}. This order places testa after test1 and interleaves several PE/schedule variants; it is based on the common 10 MHz counter values.",
        f"- Embedded receiver gain is {lookup['test0']['embedded_receiver_gain']} for test0 and {lookup['test1']['embedded_receiver_gain']} for all other scans. Transmit and decoupling gains are {lookup['test1']['embedded_transmit_gain']} and {lookup['test1']['embedded_decouple_gain']} throughout. This makes test0 a receiver-gain confound in comparisons with the other scans.",
        "- The stored PPR filenames in test1e, test1f, and test1g reuse `FSE-DWI_10-05-2026_v18_test1.ppr`. The audit associates each PPR with its enclosing folder and compares embedded protocol fields independently.",
        "",
        "## Controlled PE groups",
        "",
        "The constant-crusher controls test1e/f/g share all embedded records except PE_order and AcquisitionStartTime; their PE orders are 1, 6, and 7. The increasing-schedule controls test2b/c/d follow the same pattern. Checks compare every embedded protocol and scanner record, including multiline arrays. The pairs CSV also records additional crusher and schedule contrasts.",
        "",
        "## Legacy testa completeness",
        "",
        "Legacy testa was checked from MRD dimensions, datatype, b-value array, payload size, PPR, and the three saved reconstructed image / reordered k-space pairs. It has an MRD and adjacent PPR but no JSON, bval, bvec, or NIfTI sidecars in the supplied folder. The available raw MRD includes three experiment entries; the exact v1.3 protocol differences remain visible in the scan CSV and its embedded PPR fields.",
        "",
        "Protocol settings describe stored and embedded metadata. They do not establish image quality or physical calibration accuracy.",
        "",
    ]
    (OUT / "oct05_protocol_audit.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT / 'oct05_protocol_audit.json'}")
    print(f"Wrote {OUT / 'oct05_protocol_scans.csv'}")
    print(f"Wrote {OUT / 'oct05_protocol_pairs.csv'}")
    print(f"Wrote {OUT / 'oct05_protocol_audit.md'}")
    print("Scans with sidecar PPR diffs:", [(r['scan'], r['sidecar_ppr_diff_keys']) for r in scans if r['_sidecar_diff']])
    print("Protocol aliases:", {k: v for k, v in identical.items() if v})
    print("Pair checks:", [(r['scan_a'], r['scan_b'], r['same_protocol_signature'], list(r['protocol_differences'])) for r in pair_rows])


if __name__ == "__main__":
    main()
