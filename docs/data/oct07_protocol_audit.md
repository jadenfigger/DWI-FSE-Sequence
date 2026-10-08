# October 7 physical scanner protocol audit

Reproducible script: [oct07_protocol_audit.py](oct07_protocol_audit.py). Detailed outputs: [JSON](oct07_protocol_audit.json), [scans CSV](oct07_protocol_scans.csv), [pairs CSV](oct07_protocol_pairs.csv), [varying fields CSV](oct07_protocol_variations.csv), [comparison CSV](oct07_scan_comparison.csv). The script uses only Python’s standard library and the existing October 5 PPR/MRD parser.

All 10 MRDs have datatype 0x15 (complex 32-bit floating components), complete dimension-derived payloads and exactly 120 bytes between payload and embedded PPR. All 46 experiment slots contain nonzero raw data. Every reconstructed NIfTI header is 128 × 128 × 1 × the acquired experiment count. Every JSON PE order, b-input mode, diffusion flag, δ/Δ, b array, centered slice offset and slice spacing agrees with embedded acquisition metadata. Every bval and bvec agrees, using a zero vector for b=0. These checks establish structural completeness and metadata consistency, not image quality or calibrated diffusion accuracy.

Acquisition chronology: test0, test1, test2, test3, test2b, test3b, test2c, test3c, test1b, test3d. All use the same 10 MHz hardware-counter frequency; counter values are not calendar timestamps. File modification timestamps are separately recorded in UTC as file metadata.

All scans record receiver gain 30, transmit gain −195 and decoupler gain −453. Adjacent PPRs omit scanner runtime gains, masks and delays. Shared normalized fields disagree only for test1b, test2c and test3b:

| Scan | Field | Adjacent PPR | MRD embedded acquisition |
|---|---|---:|---:|
| test1b | `SMY` | 0.0305406 | 0.0323371 |
| test1b | `gp_init_var` | -1000 | -1059 |
| test2c | `SMY` | 0.0305406 | 0.0323371 |
| test2c | `gp_init_var` | -1000 | -1059 |
| test3b | `SMY` | 0.0305406 | 0.0323371 |
| test3b | `gp_init_var` | -1000 | -1059 |

The embedded values are authoritative for cataloging acquired settings. Test1b and test2b also reuse PPR filenames from test1 and test2; folder association and content comparison resolve them.

All 45 scan pairs are compared using every normalized embedded field and every raw PPR record, excluding only counter, frequency and END. The JSON contains full stored arrays. A second pair-difference field trims active acquisition arrays to `no_diff_acq` and removes inactive `acq_grad` caches in b-input mode 1, separating actual requested acquisition differences from reserved tails. Both representations remain available for inspection.

Stored varying fields: `PPL`, `SMY`, `VIEWS_PER_SEGMENT`, `acq_b`, `acq_grad`, `acq_x`, `acq_y`, `acq_z`, `crush_amp`, `crusher_step_pct`, `gp_init_var`, `no_diff_acq`, `no_experiments`, `no_views`, `v19_comp_flat`, `v19_cycles`, `v19_flip_tenths`, `v19_on`, `v19_slab_pml`, `v19_spoil_cpmm`, `v19_spoil_dac`, `v19_tip_pml`. Common fields are still retained in each scan’s complete `_embedded_values` and `_embedded_records`.

Test3c/test3d are an exact protocol repeat: no normalized or raw embedded-record difference remains after excluding acquisition counter/frequency/END. Their MRD hashes differ. A late repeat can reveal stability but the absence of an intervention record cannot prove the physical setup was unchanged.

The MRDs embed release paths ending in 1.8, 1.91 or 1.92. Current v1.91/v1.92 source copies are present in `scanner/`; their SHA-256 identities are recorded under `available_current_sources`. The MRD carries no source-content hash, so matching version/path labels cannot prove which compiler-compatible build generated each acquisition. See the current [compiler-compatibility artifacts](../v19/compiler_compatibility) and sequence-source analysis in the [scan report](../physical_scanner_experiments_2026-10-07.md).
