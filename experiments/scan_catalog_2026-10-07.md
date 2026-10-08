# Scanner experiments — October 7, 2026

All 10 acquisitions were verified using their MRD-embedded PPR, adjacent PPR, reconstructed NIfTI header, JSON and diffusion sidecars. The main table keeps scan-name order; the second table gives actual acquisition-counter chronology. Embedded metadata takes precedence where adjacent PPRs differ. A version label identifies the recorded scanner PPL path; it does not prove the source/build used on the scanner.

**Sample provenance:** Water phantom, per user; temperature not supplied. The user identifies b=6000 s/mm² as a condition where primary water signal is not expected.

All scans use centric phase encoding (`PE_order=1`), navigators on, stored TR 2000 ms, TE 54 ms and echo spacing 14 ms, nominal diffusion duration δ=4 ms and separation Δ=40 ms, with read-axis (x) diffusion. For the new methods, TE 54 ms denotes the preparation echo, not the first acquired imaging echo. Current-source modeling places the first imaging echo at approximately 73.716 ms for v1.91 and 68 ms for v1.92, versus 54 ms for v1.8; these source-modeled times are not scanner timing measurements. They have 128 readout samples at 50 µs, 128 imaging phase-encode lines, FOV 35 mm, one 1 mm imaging slice and 1.2 mm slice separation. All record RX gain 30, TX gain −195 and decoupler gain −453.

Crusher entries are **first diffusion echo / subsequent train baseline** in DAC units, with 1000 / 1000 µs plateaus and 200 µs ramps throughout. All schedules are constant (`crusher_schedule=0`); the stored 40% step in v1.8 is inactive for this schedule. ETL means echo train length; navigator views are additional raw lines, not extra imaging lines.

| Order | Scan / PPR | PPL / method | b-values (s/mm²) | Raw / imaging views / ETL | First / train crusher (DAC) | Schedule code / stored step % | Embedded `gp_init_var` / `SMY` | Adjacent PPR discrepancy |
|---|---|---|---|---|---|---|---|---|
| 1 | [test0](FSE-DWI_10-07-2026_v18_test0/FSE-DWI_10-07-2026_v18_test0.ppr) | 1.8 — legacy | 0, 1000, 6000 | 136 / 128 / 8 | -5482 / -5482 | 0 / 40 | -1000 / 0.0305406 | None |
| 2 | [test1](FSE-DWI_10-07-2026_v18_test1/FSE-DWI_10-07-2026_v18_test1.ppr) | 1.8 — legacy | 0, 1000, 6000 | 136 / 128 / 8 | -5482 / -8223 | 0 / 40 | -1000 / 0.0305406 | None |
| 3 | [test1b](FSE-DWI_10-07-2026_v18_test1b/FSE-DWI_10-07-2026_v18_test1.ppr) | 1.8 — legacy | 0, 100, 500, 1000, 2000, 3000, 6000 | 144 / 128 / 16 | -5482 / -8223 | 0 / 40 | -1059 / 0.0323371 | `gp_init_var`, `SMY` |
| 4 | [test2](FSE-DWI_10-07-2026_v191_test2/FSE-DWI_10-07-2026_v191_test2.ppr) | 1.91 — ss-MGOT | 0, 1000, 6000 | 136 / 128 / 8 | -5482 / -8223 | 0 / 0 | -1000 / 0.0305406 | None |
| 5 | [test2b](FSE-DWI_10-07-2026_v191_test2b/FSE-DWI_10-07-2026_v191_test2.ppr) | 1.91 — ss-MGOT | 0, 1000, 6000 | 144 / 128 / 16 | -5482 / -8223 | 0 / 0 | -1059 / 0.0323371 | None |
| 6 | [test2c](FSE-DWI_10-07-2026_v191_test2c/FSE-DWI_10-07-2026_v191_test2c.ppr) | 1.91 — ss-MGOT | 0, 100, 500, 1000, 2000, 3000, 6000 | 144 / 128 / 16 | -5482 / -8223 | 0 / 0 | -1059 / 0.0323371 | `gp_init_var`, `SMY` |
| 7 | [test3](FSE-DWI_10-07-2026_v192_test3/FSE-DWI_10-07-2026_v192_test3.ppr) | 1.92 — Alsop | 0, 1000, 6000 | 136 / 128 / 8 | -5482 / -8223 | 0 / 0 | -1000 / 0.0305406 | None |
| 8 | [test3b](FSE-DWI_10-07-2026_v192_test3b/FSE-DWI_10-07-2026_v192_test3b.ppr) | 1.92 — Alsop | 0, 1000, 6000 | 144 / 128 / 16 | -5482 / -8223 | 0 / 0 | -1059 / 0.0323371 | `gp_init_var`, `SMY` |
| 9 | [test3c](FSE-DWI_10-07-2026_v192_test3c/FSE-DWI_10-07-2026_v192_test3c.ppr) | 1.92 — Alsop | 0, 100, 500, 1000, 2000, 3000, 6000 | 144 / 128 / 16 | -5482 / -8223 | 0 / 0 | -1059 / 0.0323371 | None |
| 10 | [test3d](FSE-DWI_10-07-2026_v192_test3d/FSE-DWI_10-07-2026_v192_test3d.ppr) | 1.92 — Alsop | 0, 100, 500, 1000, 2000, 3000, 6000 | 144 / 128 / 16 | -5482 / -8223 | 0 / 0 | -1059 / 0.0323371 | None |

**Chronology and acquisition integrity**

| Scan | Counter order | Minutes from test0 | Experiments / nonzero raw slots | Reconstructed NIfTI shape | Diffusion sidecars |
|---|---:|---:|---|---|---|
| test0 | 1 | 0.00 | 3 / 3 | 128 × 128 × 1 × 3 | JSON / bval / bvec match embedded protocol |
| test1 | 2 | 2.07 | 3 / 3 | 128 × 128 × 1 × 3 | JSON / bval / bvec match embedded protocol |
| test1b | 9 | 32.89 | 7 / 7 | 128 × 128 × 1 × 7 | JSON / bval / bvec match embedded protocol |
| test2 | 3 | 4.27 | 3 / 3 | 128 × 128 × 1 × 3 | JSON / bval / bvec match embedded protocol |
| test2b | 5 | 14.39 | 3 / 3 | 128 × 128 × 1 × 3 | JSON / bval / bvec match embedded protocol |
| test2c | 7 | 17.14 | 7 / 7 | 128 × 128 × 1 × 7 | JSON / bval / bvec match embedded protocol |
| test3 | 4 | 6.31 | 3 / 3 | 128 × 128 × 1 × 3 | JSON / bval / bvec match embedded protocol |
| test3b | 6 | 15.77 | 3 / 3 | 128 × 128 × 1 × 3 | JSON / bval / bvec match embedded protocol |
| test3c | 8 | 21.95 | 7 / 7 | 128 × 128 × 1 × 7 | JSON / bval / bvec match embedded protocol |
| test3d | 10 | 57.73 | 7 / 7 | 128 × 128 × 1 × 7 | JSON / bval / bvec match embedded protocol |

Counter times provide relative acquisition order, not clock times. The order is test0, test1, test2, test3, test2b, test3b, test2c, test3c, test1b, test3d. Test3d repeats the exact embedded protocol of test3c approximately 35.78 minutes later. Test1b is a late v1.8 control, despite its name. All 46 experiment slots contain nonzero raw data, and all expected complex payloads are present; this is a completeness check, not evidence of good signal.

**New method parameters**

Both v1.91 (ss-MGOT) and v1.92 (Alsop) record `v19_on=1`, two cycles of added dephasing across the imaging slice (`v19_cycles=2`) and a 1000 µs compensation-lobe plateau (`v19_comp_flat=1000`). Their stored refocusing flip array is in tenths of a degree. The active ETL8 flips are 142.2°, 94.9°, 69.2°, 63.0°, 60.2°, 60°, 60°, 60°; ETL16 adds eight further 60° pulses. VFA means variable flip angle: the refocusing pulses intentionally change angle through the train. v1.8 does not expose that VFA array. All protocols store `rfcal=594`, `alpha=90` and `p180_scale=185`, but the revised method branches bypass the legacy `alpha` and `p180_scale` controls. RF calibration and actual achieved method flip angles remain physically unverified; matching stored scales do not imply identical transmitted pulses.

v1.91 additionally stores prep slab width 3000 per mille (3 × the imaging-slice width), tip-up width 1667 per mille (1.667 ×), spoiler moment 32 cycles/mm on the phase axis, and spoiler amplitude 16384 DAC. v1.92 omits those preparation-only fields. The intended mechanisms and the revised compiler-compatible source are discussed in the [analysis report](../docs/physical_scanner_experiments_2026-10-07.md) and [compiler-compatibility documentation](../docs/v19/compiler_compatibility).

**Controlled comparisons and co-changes**

| Comparison | Intended factor | Other recorded differences / interpretation |
|---|---|---|
| test0 / test1 | Stronger train crushers | Only `crush_amp` changes, −5482 to −8223; first crusher remains −5482. Both are ETL8. Today’s test0 is not a single-echo control. |
| test1 / test2 / test3 | v1.8 / ss-MGOT v1.91 / Alsop v1.92 at ETL8 | Matching imaging geometry, gains, stored timing fields, nominal b entries and crusher baselines. Actual first imaging echo occurs later in the new-method source models. New methods intentionally change RF/dephasing and preparation; inactive array capacities and stored schedule step also differ. |
| test2 / test2b; test3 / test3b | ETL8 / ETL16 | Raw views 136→144, embedded phase calibration −1000 / 0.0305406→−1059 / 0.0323371, and eight more VFA pulses. ETL is not the only metadata change. |
| test2b / test3b | ss-MGOT / Alsop at ETL16, three b entries | Matching stored timing, gains, imaging geometry, b entries and common VFA/dephasing fields; preparation and source-modeled first imaging echo time differ. |
| test2c / test3c; test1b / test2c / test3c | Seven-b ETL16 method comparisons | Matching active diffusion arrays, imaging geometry, gains, stored timing fields and crusher baselines. Preparation, RF path and first imaging echo time differ between methods. Test1b was acquired later. |
| test2b / test2c; test3b / test3c | Three / seven b entries | Nominal protocol otherwise matches within method; elapsed time differs. Compare by b-value rather than experiment number. |
| test3c / test3d | Repeatability | All embedded protocol/scanner records match except acquisition counter. Different raw files; no intervention is documented in their metadata. |

**Metadata details that affect comparisons**

For test1b, test2c and test3b, the adjacent PPR stores `gp_init_var=-1000`, `SMY=0.0305406`, while the acquired MRD embeds −1059 and 0.0323371. The catalog and numerical analysis use the embedded values. Other shared normalized PPR fields match; scanner gains and delay/mask tags occur only in the embedded acquisition record. Do not use the standalone PPR to infer these three acquisitions’ phase calibration.

Test1b and test2b reuse PPR basenames ending in test1 and test2, respectively. Each link points to the actual PPR within the relevant scan folder; filenames are not used as protocol identities. The v1.8 acquisition arrays reserve 512 entries and the v1.9 arrays 64. Only the first `no_diff_acq` entries are active. In particular, trailing nonzero direction entries in v1.8 test1b do not add experiments; the MRD, JSON, bval, bvec and NIfTI all agree on seven entries.

All b-values are requested values. Additional gradients and coherence pathways can affect actual diffusion weighting; the metadata agreement does not independently validate the effective b-tensor or the physical gradient calibration. The legacy and new methods also differ in the intended RF and gradient events, so an equal requested b-value alone does not establish an equal signal pathway.

Compared with October 5, the recorded TX gain is −195 rather than −205. No validated gain-to-amplitude conversion is available, so comparisons across days should not treat brightness changes as sequence performance alone.

The [complete comparison CSV](../docs/data/oct07_scan_comparison.csv) includes common important parameters and every new-method control. The [protocol audit](../docs/data/oct07_protocol_audit.md), [all varying embedded fields](../docs/data/oct07_protocol_variations.csv), and [all 45 pair comparisons](../docs/data/oct07_protocol_pairs.csv) retain the full differences. See the [report and comparison figures](../docs/physical_scanner_experiments_2026-10-07.md) for quality assessment. Rebuild the catalog and audit with `python docs/data/oct07_protocol_audit.py`.
