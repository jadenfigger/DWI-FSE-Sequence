# October 10 physical scanner protocol audit

Reproducible script: [oct10_protocol_audit.py](oct10_protocol_audit.py). Detailed outputs: [JSON](oct10_protocol_audit.json), [scans CSV](oct10_protocol_scans.csv), [pairs CSV](oct10_protocol_pairs.csv), [varying fields CSV](oct10_protocol_variations.csv), [comparison CSV](oct10_scan_comparison.csv). The script uses only Python’s standard library and the October 5 PPR/MRD parser.

All 10 MRDs have datatype 0x15 (complex 32-bit floating components), complete dimension-derived payloads and exactly 120 bytes between payload and embedded PPR. All 55 experiment slots (and all slice blocks of three-slice scan K) contain nonzero raw data. Every reconstructed NIfTI header is 128 × 128 × slices × acquired experiments. Every JSON PE order, b-input mode, diffusion flag, δ/Δ, b array, slice offset list and slice spacing agrees with embedded acquisition metadata. Every bval and bvec agrees, using a zero vector for b=0; non-zero bvec columns are unit vectors. These checks establish structural completeness and metadata consistency, not image quality or calibrated diffusion accuracy.

Acquisition chronology (counter order, minutes from first scan): A (0.00), B (5.00), C (9.48), D (13.87), E (18.36), G (23.54), H (28.59), I (30.77), J (32.86), K (35.41). All use the same 10 MHz hardware-counter frequency; counter values are not calendar timestamps. Exact active-protocol repeats: none.

Receiver gain 30, transmit gain −203 and decoupler gain −453 in every scan (10-07: 30 / −195 / −453). Adjacent PPRs omit scanner runtime gains, masks and delays but otherwise match the embedded protocol exactly in all ten scans.

## Differences from the planned PPRs (console-side changes)

Each embedded protocol is compared with the planned PPR in `experiments/2026-10-09_exvivo_plan/` (scan K against plan A). Differences below are active-protocol differences (plan → acquired); records that exist only in the MRD (gains, delays, masks) are not deviations because the plan PPRs carry none.

| Scan | Reference plan | Active differences (plan → acquired) |
|---|---|---|
| A | A | None |
| B | B | None |
| C | C | None |
| D | D | None |
| E | E | None |
| G | G | None |
| H | H | None |
| I | I | None |
| J | J | `SMX` 0.0224563→0.0449126; `esp` 14→11; `gr_var` −735→−1471; `sample_period` 500/12 (50 µs, 20 kHz)→250/17 (25 µs, 40 kHz) |
| K | A | diffusion list 7→2 volumes (plan→acquired); slices 1→3, z offsets 0→−1.2, 0, +1.2 mm (plan→acquired); `SMX` 0.0224563→0.0449126; `esp` 14→11; `gr_var` −735→−1471; `sample_period` 500/12 (50 µs, 20 kHz)→250/17 (25 µs, 40 kHz) |

MRD-only records common to all scans: `B0GradientDelay`, `RxDelay`, `TxDelay`, `XGradientDelay`, `YGradientDelay`, `ZGradientDelay`, `_DecoupleTransmitGain`, `_ObserveReceiverGain`, `_ObserveTransmitGain`, `_pdd_rx_mask`, `_pdd_tx_mask`, `_pts_mask`, `_use_pdd`.

## Planned-pair comparisons (acquired vs acquired)

| Pair | Differences (first → second) |
|---|---|
| A vs C | PPL 1.81→1.8 |
| B vs D | PPL 1.911→1.91; `esp` 13→14 |
| E vs A | diffusion list (b / directions) 8→7 volumes |
| G vs B | diffusion list (b / directions) 8→7 volumes |
| H vs A | diffusion list (b / directions) 3→7 volumes; `crush_amp` −2741→−8223 |
| I vs B | diffusion list (b / directions) 3→7 volumes; `big_delta` 30000→40000; `te` 44→54 |
| J vs A | diffusion list (b / directions) 3→7 volumes; `SMX` 0.0449126→0.0224563; `esp` 11→14; `gr_var` −1471→−735; dwell 25→50 µs (40→20 kHz) |
| K vs A | diffusion list (b / directions) 2→7 volumes; slices 3→1 (stored per-slice orientation/offset arrays also differ); `SMX` 0.0449126→0.0224563; `esp` 11→14; `gr_var` −1471→−735; dwell 25→50 µs (40→20 kHz) |
| E vs G | PPL 1.81→1.911; `crusher_step_pct` 40→0; `esp` 14→13; `v19_comp_flat` —→1000; `v19_cycles` —→2; `v19_flip_tenths` array differs; `v19_on` —→1; `v19_slab_pml` —→3000; `v19_spoil_cpmm` —→32; `v19_spoil_dac` —→16384; `v19_tip_pml` —→1667 |
| K vs J | diffusion list (b / directions) 2→3 volumes; slices 3→1 (stored per-slice orientation/offset arrays also differ) |

## Cross-day (October 7) active-protocol differences

- C vs 10-07 test1: diffusion list (b / directions) 3→7 volumes; `_ObserveTransmitGain` −195→−203
- A vs 10-07 test1: diffusion list (b / directions) 3→7 volumes; PPL 1.8→1.81; `_ObserveTransmitGain` −195→−203
- D vs 10-07 test2: diffusion list (b / directions) 3→7 volumes; `_ObserveTransmitGain` −195→−203
- B vs 10-07 test2: diffusion list (b / directions) 3→7 volumes; PPL 1.91→1.911; `_ObserveTransmitGain` −195→−203; `esp` 14→13

## Diffusion arrays and sign convention

| Scan | Volume | b | Embedded x, y, z (thousandths) | bvec column |
|---|---:|---:|---|---|
| E | 1 | 0 | 1000, 0, 0 | 0, 0, 0 |
| E | 2 | 1000 | 1000, 0, 0 | 1, 0, 0 |
| E | 3 | 1000 | -1000, 0, 0 | -1, 0, 0 |
| E | 4 | 1000 | 0, 1000, 0 | 0, 1, 0 |
| E | 5 | 1000 | 0, 0, 1000 | 0, 0, 1 |
| E | 6 | 3000 | 1000, 0, 0 | 1, 0, 0 |
| E | 7 | 3000 | 0, 1000, 0 | 0, 1, 0 |
| E | 8 | 3000 | 0, 0, 1000 | 0, 0, 1 |
| G | 1 | 0 | 1000, 0, 0 | 0, 0, 0 |
| G | 2 | 1000 | 1000, 0, 0 | 1, 0, 0 |
| G | 3 | 1000 | -1000, 0, 0 | -1, 0, 0 |
| G | 4 | 1000 | 0, 1000, 0 | 0, 1, 0 |
| G | 5 | 1000 | 0, 0, 1000 | 0, 0, 1 |
| G | 6 | 3000 | 1000, 0, 0 | 1, 0, 0 |
| G | 7 | 3000 | 0, 1000, 0 | 0, 1, 0 |
| G | 8 | 3000 | 0, 0, 1000 | 0, 0, 1 |

The −x volume (volume 3) is present in both E and G, with sign preserved in the bvec (−1). b=0 volumes embed +x but bvec is zero.

All 45 scan pairs are compared using every normalized embedded field and every raw PPR record, excluding only counter, frequency and END. The JSON contains full stored arrays. A second pair-difference field trims active acquisition arrays to `no_diff_acq` and removes inactive `acq_grad` caches in b-input mode 1.

Stored varying fields: `FOV_OFFSETS`, `FOV_PHASE_OFF`, `FOV_READ_OFF`, `FOV_SLICE_OFF`, `MULTI_ORIENTATION`, `NO_SLICES`, `PPL`, `SMX`, `X_ANGLE`, `Y_ANGLE`, `Z_ANGLE`, `acq_b`, `acq_grad`, `acq_x`, `acq_y`, `acq_z`, `big_delta`, `crush_amp`, `crusher_step_pct`, `esp`, `gr_var`, `no_diff_acq`, `no_experiments`, `sample_period`, `te`, `v19_comp_flat`, `v19_cycles`, `v19_flip_tenths`, `v19_on`, `v19_slab_pml`, `v19_spoil_cpmm`, `v19_spoil_dac`, `v19_tip_pml`. Common fields are retained in each scan’s `_embedded_values` and `_embedded_records`.

The MRDs embed release paths ending in 1.8, 1.81, 1.91 or 1.911. Repository source copies are present in `scanner/`; their SHA-256 identities are recorded under `available_current_sources` in the JSON. The MRD carries no source-content hash, so matching version/path labels cannot prove which build generated each acquisition.
