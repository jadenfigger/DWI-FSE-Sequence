"""Build local research WavEd RF asset from validated-format real samples.

Preserves real RF control words from the supplied RFstd44 format. This is not
WavEd/compiler load verification, scanner installation, or RF calibration.
"""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dwfse.vendor_seq import Library, decode, real_rf_frame


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    research = ROOT/"docs/v19/reference_rf"
    contract_path = research/"real_rf_contract.json"
    samples_path = research/"real_rf_contract.npz"
    contract = json.loads(contract_path.read_text())
    if sha(samples_path) != contract["contract_npz_sha256"]:
        raise ValueError("RF sample contract changed")
    template_path = ROOT/"scanner/utilities/rfstd44.seq"
    template = decode(template_path)
    stock = template.frame("3lobe_sinc_3kHz")
    stock_integral = stock.samples.sum()*stock.wait_ticks*1e-7/2047
    frames = []
    manifest = {
        "status": "Local research RF library; exact-format/sample checks passed; vendor loading and console calibration unverified",
        "template_sha256": sha(template_path), "sample_contract_sha256": sha(contract_path),
        "sample_npz_sha256": sha(samples_path), "encoder_sha256": sha(ROOT/"dwfse/vendor_seq.py"),
        "original_Gibbons_coefficients": False, "spectral_spatial_tip": False,
        "rf_amplitude_calibration_assumption": "Linear signed DAC x board multiplier; rfcal gives90deg on the supplied stock3lobe1332us interior. Per-pulse ratio is an inference, not measured transmit gain.",
        "stock_rf_integral_s": float(stock_integral), "rf_scale_denominator": 10000,
        "pulse_frames": {},
    }
    arrays = np.load(samples_path)
    for name, info in contract["pulses"].items():
        samples = arrays[name+"_dac"]
        if len(samples) != info["sample_count"]:
            raise ValueError("RF sample count mismatch")
        frame = real_rf_frame(name, samples, info["wait_ticks"])
        frames.append(frame)
        ratio = info["flip_deg"]/90 * stock_integral/info["signed_normalized_integral_s"]
        numerator = int(np.floor(ratio*10000+.5))
        if not 1 <= numerator <= 32767:
            raise ValueError("Calibration ratio not representable by verified scale interface")
        # Intended console multiplier is scale(rfcal,numerator,10000), with
        # explicit runtime >2047 rejection. Baseline p180_scale is independent.
        multiplier_594 = (594*numerator)//10000
        manifest["pulse_frames"][name] = {
            **info, "frame_stored_span_us": len(samples)*info["wait_ticks"]/10,
            "extra_guard_samples": 0,
            "rfcal_scale_numerator": numerator,
            "rfcal_scale_denominator": 10000,
            "rfcal594_inferred_board_multiplier": multiplier_594,
            "relative_factor_rounding_error": numerator/10000/ratio-1,
            "calibration_integer_truncation_relative_error_at594": multiplier_594/(594*ratio)-1,
            "sample_record_sha256": hashlib.sha256(frame.words.tobytes()).hexdigest(),
            "RF_board_flags": "Known realF0 word controls; lastphase-control0x6000 copied from stock. AP phase encoding unused.",
        }
    library = Library(template.format_id, template.header_value, template.titles, frames)
    data = library.encode()
    restored = decode(data)
    assert restored.encode() == data
    for frame in restored.frames:
        assert np.array_equal(frame.samples, arrays[frame.name+"_dac"])
    asset = ROOT/"scanner/rf/v19_research_rf.seq"
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_bytes(data)
    manifest["asset_sha256"] = sha(asset)
    manifest["asset_path"] = str(asset.relative_to(ROOT)).replace("\\", "/")
    manifest["all_samples_roundtrip_exact"] = True
    manifest_path = ROOT/"docs/v19/rf_library_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf8")
    print(f"Built {len(frames)} real RF frames with exact sample readback: {asset}")
    print("Inferred scale numerators /10000:", {name: item["rfcal_scale_numerator"] for name,item in manifest["pulse_frames"].items()})
    print("Not installed, vendor-loaded or scanner-calibrated")


if __name__ == "__main__":
    main()
