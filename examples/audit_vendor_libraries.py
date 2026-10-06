"""Decode real uploaded WavEd assets and record exhaustive binary checks.

Not a compilation/played-event trace. RF duration here is stored record span;
RF gate and end flags can make active duration differ from this span.
"""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dwfse.vendor_seq import decode


def main():
    result = {
        "scope": "Exact binary library decode/encode and independent embedded-formula oracles; no vendor load/compile/hardware validation",
        "codec_sha256": hashlib.sha256((ROOT/"dwfse/vendor_seq.py").read_bytes()).hexdigest(),
        "libraries": [],
    }
    for path in sorted((ROOT/"scanner/utilities").glob("*.seq")):
        raw = path.read_bytes()
        library = decode(raw)
        assert library.encode() == raw
        record = {"name": path.name, "sha256": hashlib.sha256(raw).hexdigest(),
                  "bytes": len(raw), "format_id": library.format_id,
                  "header_value_retained": library.header_value,
                  "byte_identical_roundtrip": True, "frames": []}
        for frame in library.frames:
            details = {"name": frame.name, "wait_ticks": frame.wait_ticks,
                       "record_count": len(frame.records),
                       "stored_record_span_us": len(frame.records)*frame.wait_ticks/10,
                       "expressions_latin1": [x[:-1].decode("latin1") for x in frame.expressions],
                       "raw_records_sha256": hashlib.sha256(frame.words.tobytes()).hexdigest(),
                       "raw_tail_bytes": len(frame.trailing_words),
                       "control_word_upper_nibbles": [np.unique(frame.records[:, i]>>12).tolist()
                                                       for i in range(frame.records.shape[1])]}
            if library.format_id == 6:
                amp = frame.samples
                details.update(amplitude_signed12_min=int(amp.min()), amplitude_signed12_max=int(amp.max()),
                               amplitude_signed12_sum=int(amp.sum()))
            else:
                grad = frame.samples
                details["gradient_signed16_minmax"] = [[int(grad[:, i].min()), int(grad[:, i].max())] for i in range(2)]
                details["gradient_normalized_sums"] = (grad.astype(float).sum(axis=0)/32767).tolist()
            record["frames"].append(details)
        result["libraries"].append(record)
    rf = decode(ROOT/"scanner/utilities/rfstd44.seq").frame("3lobe_sinc_3kHz")
    expected = np.r_[0, np.round(2047*np.sinc((np.arange(666)-333)*2/333)), 0].astype(int)
    assert np.array_equal(rf.samples, expected)
    ramp = decode(ROOT/"scanner/utilities/g3040_15.seq")
    expected_up = np.round(np.arange(50)*32767/50).astype(int); expected_up[-1] = 32767
    assert np.array_equal(ramp.frame("0_max").samples[:, 0], expected_up)
    result["embedded_formula_checks"] = {
        "rf_sinc_exact_all_668_records": True,
        "primary_ramp_exact_50_records": True,
        "rf_active_interior_us": 666*rf.wait_ticks/10,
        "rf_stored_span_us": len(rf.records)*rf.wait_ticks/10,
        "rf_gate_note": "Active interior 1332us vs stored span1336us. Do not add guard records to nominal PPL RF length or infer physical gate latency.",
        "gradient_note": "Primary0_max is j/50 with forced final endpoint, not linspace(j/49). Integrate actual samples using verified hold/continuation semantics.",
        "complex_phase_encoding": "Unresolved for AP frames; raw bits retained. No new complex RF encoding asserted.",
    }
    output = ROOT/"docs/v19/vendor_library_audit.json"
    output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf8")
    print(f"{len(result['libraries'])} libraries decoded and byte-identically rebuilt; sinc/ramp oracles pass")
    print(output)


if __name__ == "__main__":
    main()
