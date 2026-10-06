# Scanner experiments — October 5, 2026

Comparison of all 20 scans, verified against each MRD-embedded PPR and its adjacent PPR. Rows use scan-name order; the second table records acquisition-counter order and elapsed time. These counters provide relative chronology, not civil timestamps. PPL versions identify the recorded file path; the exact v1.8 source/build is unavailable.

All scans request b=0, 1000, 6000 s/mm², TR 2000 ms, TE 54 ms, diffusion duration δ=4 ms and read-axis diffusion. They use 128 readout samples at 50 µs, FOV 35 mm, one 1 mm slice and centered zero-angle geometry. Crusher amplitudes and durations below are **first-DWI / subsequent train baseline**, before schedule scaling; durations are plateaus and exclude the 200 µs ramps.

| Order | Scan / PPR | PPL | `PE_order` | Raw / imaging views / ETL | Navigator | RX gain | TE / ESP / Δ (ms) | Crusher baseline (DAC) | First / train duration (µs) | Schedule (code; step %) |
|---|---|---|---|---|---|---:|---|---|---|---|
| 1 | [test0](FSE-DWI_10-05-2026_v18_test0/FSE-DWI_10-05-2026_v18_test0.ppr) | 1.8 | 5 — single echo | 128 / 128 / 1 | Off | 180 | 54 / 14 / 40 | 5482 / 2741 | 1000 / 1000 | Constant (0; 0) |
| 2 | [test1](FSE-DWI_10-05-2026_v18_test1/FSE-DWI_10-05-2026_v18_test1.ppr) | 1.8 | 1 — centric (egen) | 136 / 128 / 8 | On | 30 | 54 / 14 / 40 | 5482 / 2741 | 1000 / 1000 | Constant (0; 0) |
| 3 | [test1b](FSE-DWI_10-05-2026_v18_test1b/FSE-DWI_10-05-2026_v18_test1b.ppr) | 1.8 | 1 — centric (egen) | 136 / 128 / 8 | On | 30 | 54 / 16 / 40 | 2741 / 2741 | 2000 / 2000 | Constant (0; 0) |
| 4 | [test1c](FSE-DWI_10-05-2026_v18_test1c/FSE-DWI_10-05-2026_v18_test1c.ppr) | 1.8 | 1 — centric (egen) | 136 / 128 / 8 | On | 30 | 54 / 16 / 40 | -2741 / -2741 | 2000 / 2000 | Constant (0; 0) |
| 5 | [test1d](FSE-DWI_10-05-2026_v18_test1d/FSE-DWI_10-05-2026_v18_test1d.ppr) | 1.8 | 1 — centric (egen) | 136 / 128 / 8 | On | 30 | 54 / 16 / 40 | -5482 / -5482 | 2000 / 2000 | Constant (0; 0) |
| 6 | [test1e](FSE-DWI_10-05-2026_v18_test1e/FSE-DWI_10-05-2026_v18_test1.ppr) | 1.8 | 1 — centric (egen) | 136 / 128 / 8 | On | 30 | 54 / 14 / 40 | -5482 / -2741 | 1000 / 1000 | Constant (0; 0) |
| 7 | [test1f](FSE-DWI_10-05-2026_v18_test1f/FSE-DWI_10-05-2026_v18_test1.ppr) | 1.8 | 6 — reverse centric | 136 / 128 / 8 | On | 30 | 54 / 14 / 40 | -5482 / -2741 | 1000 / 1000 | Constant (0; 0) |
| 8 | [test1g](FSE-DWI_10-05-2026_v18_test1g/FSE-DWI_10-05-2026_v18_test1.ppr) | 1.8 | 7 — linear interleaved | 136 / 128 / 8 | On | 30 | 54 / 14 / 40 | -5482 / -2741 | 1000 / 1000 | Constant (0; 0) |
| 9 | [test2](FSE-DWI_10-05-2026_v18_test2/FSE-DWI_10-05-2026_v18_test2.ppr) | 1.8 | 1 — centric (egen) | 136 / 128 / 8 | On | 30 | 54 / 14 / 40 | 5482 / 2741 | 1000 / 1000 | Increasing (1; 40) |
| 10 | [test2b](FSE-DWI_10-05-2026_v18_test2b/FSE-DWI_10-05-2026_v18_test2b.ppr) | 1.8 | 1 — centric (egen) | 136 / 128 / 8 | On | 30 | 54 / 14 / 40 | -5482 / -2741 | 1000 / 1000 | Increasing (1; 40) |
| 11 | [test2c](FSE-DWI_10-05-2026_v18_test2c/FSE-DWI_10-05-2026_v18_test2c.ppr) | 1.8 | 6 — reverse centric | 136 / 128 / 8 | On | 30 | 54 / 14 / 40 | -5482 / -2741 | 1000 / 1000 | Increasing (1; 40) |
| 12 | [test2d](FSE-DWI_10-05-2026_v18_test2d/FSE-DWI_10-05-2026_v18_test2d.ppr) | 1.8 | 7 — linear interleaved | 136 / 128 / 8 | On | 30 | 54 / 14 / 40 | -5482 / -2741 | 1000 / 1000 | Increasing (1; 40) |
| 13 | [test3](FSE-DWI_10-05-2026_v18_test3/FSE-DWI_10-05-2026_v18_test3.ppr) | 1.8 | 1 — centric (egen) | 136 / 128 / 8 | On | 30 | 54 / 14 / 40 | 5482 / 2741 | 1000 / 1000 | Increasing + alternating (3; 40) |
| 14 | [test3b](FSE-DWI_10-05-2026_v18_test3b/FSE-DWI_10-05-2026_v18_test3b.ppr) | 1.8 | 1 — centric (egen) | 136 / 128 / 8 | On | 30 | 54 / 14 / 40 | -5482 / -2741 | 1000 / 1000 | Increasing + alternating (3; 40) |
| 15 | [test4](FSE-DWI_10-05-2026_v18_test4/FSE-DWI_10-05-2026_v18_test4.ppr) | 1.8 | 1 — centric (egen) | 136 / 128 / 8 | On | 30 | 54 / 14 / 40 | -5482 / -5482 | 1000 / 1000 | Decreasing (4; 40) |
| 16 | [test4b](FSE-DWI_10-05-2026_v18_test4b/FSE-DWI_10-05-2026_v18_test4b.ppr) | 1.8 | 1 — centric (egen) | 136 / 128 / 8 | On | 30 | 54 / 14 / 40 | -5842 / -5842 | 2000 / 1000 | Decreasing (4; 40) |
| 17 | [test5](FSE-DWI_10-05-2026_v18_test5/FSE-DWI_10-05-2026_v18_test5.ppr) | 1.8 | 1 — centric (egen) | 136 / 128 / 8 | On | 30 | 54 / 14 / 40 | -5482 / -2741 | 1000 / 1000 | Decreasing (4; 40) |
| 18 | [test6](FSE-DWI_10-05-2026_v18_test6/FSE-DWI_10-05-2026_v18_test6.ppr) | 1.8 | 1 — centric (egen) | 136 / 128 / 8 | On | 30 | 54 / 14 / 40 | -5482 / -2741 | 1000 / 1000 | Custom (5; 0) |
| 19 | [test7](FSE-DWI_10-05-2026_v18_test7/FSE-DWI_10-05-2026_v18_test7.ppr) | 1.8 | 1 — centric (egen) | 136 / 128 / 8 | On | 30 | 54 / 14 / 40 | -5482 / -2741 | 1000 / 1000 | Custom (5; 0) |
| 20 | [testa](FSE-DWI_10-05-2026_v13_testa/FSE-DWI_10-05-2026_v13_testa.ppr) | 1.3 | 1 — centric (egen) | 136 / 128 / 8 | On | 30 | 54 / 15 / 32 | Not exposed | 2000 / 2000 | Legacy; no field |

**Chronology, geometry/calibration differences and derived-file availability**

| Scan | Counter order | Minutes from test0 | Slice separation (mm) | `gp_init_var` | `SMY` | NIfTI + diffusion sidecars |
|---|---:|---:|---:|---:|---:|---|
| test0 | 1 | 0.00 | 1.2 | -941 | 0.0287441 | Absent; raw MRD available |
| test1 | 2 | 17.48 | 1.2 | -1000 | 0.0305406 | Present |
| test1b | 6 | 27.59 | 1.2 | -1000 | 0.0305406 | Present |
| test1c | 7 | 33.71 | 1.2 | -1000 | 0.0305406 | Present |
| test1d | 8 | 38.44 | 1.2 | -1000 | 0.0305406 | Present |
| test1e | 11 | 48.36 | 1.2 | -1000 | 0.0305406 | Present |
| test1f | 18 | 69.17 | 1.2 | -1000 | 0.0305406 | Present |
| test1g | 20 | 73.58 | 1.2 | -1000 | 0.0305406 | Present |
| test2 | 4 | 23.50 | 1.2 | -1000 | 0.0305406 | Present |
| test2b | 9 | 43.94 | 1.2 | -1000 | 0.0305406 | Present |
| test2c | 17 | 67.07 | 1.2 | -1000 | 0.0305406 | Present |
| test2d | 19 | 71.21 | 1.2 | -1000 | 0.0305406 | Present |
| test3 | 5 | 25.54 | 1.2 | -1000 | 0.0305406 | Present |
| test3b | 10 | 46.15 | 1.2 | -1000 | 0.0305406 | Present |
| test4 | 12 | 50.65 | 1.2 | -1000 | 0.0305406 | Present |
| test4b | 16 | 63.34 | 1.2 | -1000 | 0.0305406 | Present |
| test5 | 13 | 52.76 | 1.2 | -1000 | 0.0305406 | Present |
| test6 | 14 | 54.84 | 1.2 | -1000 | 0.0305406 | Present |
| test7 | 15 | 56.93 | 1.2 | -1000 | 0.0305406 | Present |
| testa | 3 | 21.33 | 1.09907 | -1000 | 0.0305406 | Absent; raw MRD available |

All scans record TX gain−205 and decoupler gain−453; RX gain differs for test0 as shown. No validated gain-to-amplitude conversion was supplied, so test0 is not an absolute-brightness control for the ETL8 scans.

All increasing, increasing-plus-alternating, and decreasing schedules use `crusher_step_pct=40` (40% of the train baseline per step). Constant and custom schedules use 0. The custom schedules specify eight percentages: test6 uses `100, 100, 171, 83, 137, 213, 109, 191`; test7 uses `100, -100, 171, -83, 137, -213, 109, -191`. These are the stored `crusher_custom_pct` entries, including the first value on the array header. All v1.8 PPRs enable independent crusher amplitudes (`crush_independent_on=1`), with maximum DAC and slew-limit fields both set to 32767.

First/train crusher durations are 1000/1000 µs except test1b, test1c, test1d, and testa (2000/2000 µs), and test4b (2000/1000 µs). Test4b stores **−5842 / −5842**, rather than −5482 / −5482; the table preserves this exact PPR value.

Phase-encoding order (`PE_order`) is 1 (centric / egen) except test0 (5, single echo), test1f and test2c (6, reverse centric), and test1g and test2d (7, linear interleaved). Navigators are on except test0. All PPRs specify `no_disacq=4` and `no_discard=0`, one slice, and one centered zero-angle orientation/offset entry. Slice separation is 1.2 mm except testa (1.09907 mm). Test0 also differs in phase-gradient initialization (`gp_init_var=-941` versus −1000) and `SMY` (0.0287441 versus 0.0305406).

The legacy testa uses v1.3, ESP 15 ms, diffusion separation 32 ms, and legacy b/direction arrays. The v1.8 scans use diffusion separation 40 ms and three acquisition-array entries with x-directed diffusion (`acq_x=1000`, `acq_y=acq_z=0`). All scans use the same stored RF calibration and excitation/refocusing scale settings (`rfcal=594`, `alpha=90`, `p180_scale=185`).

The PPR in each of test1e, test1f, and test1g is named `FSE-DWI_10-05-2026_v18_test1.ppr`; links above point to the actual file inside each scan folder. Their contents differ from test1, so they are cataloged separately.

The 20 physical-scanner experiments compare a single-echo v1.8 protocol with eight-echo protocols, then vary crusher amplitude, polarity, duration, schedule, and phase-encoding order. Test1 through test1g compare constant crushers; test2 through test2d compare increasing crushers; test3 and test3b compare increasing-plus-alternating crushers with opposite baseline signs. Test4, test4b, and test5 compare decreasing schedules with different baselines and first-crusher durations. Test6 and test7 compare custom percentage arrays with and without alternating signs. Testa provides a legacy v1.3 protocol comparison. This catalog records protocol settings; it does not assess scan quality.

**Controlled comparisons and important co-changes**

| Comparison | Intended factor | Other differences to retain in interpretation |
|---|---|---|
| test1 / test1e; test1b / test1c; test2 / test2b; test3 / test3b | Crusher baseline sign | Matching timing, PE order and absolute per-echo crusher areas within each pair |
| test1e / test1f / test1g; test2b / test2c / test2d | PE1 / PE6 / PE7 | Only PE order differs in embedded records apart from counters, within each group |
| test2 / test3; test2b / test3b; test6 / test7 | Per-echo signs / alternation | Identical per-echo absolute crusher areas within each pair |
| test2b / test5 | Increasing / decreasing | Same first crusher and total absolute area; train magnitudes reversed |
| test1 / test2; test1e / test2b | Constant / increasing | Total absolute area also increases; schedule shape is not isolated |
| test1 / test1b | Longer constant crushers | ESP, first amplitude and durations change together |
| test1c / test1d | Negative amplitude doubled | Absolute area doubles; timing and PE order match |
| test4 / test5 | Stronger decreasing baseline | Train absolute area also changes |
| test4 / test4b | Decreasing amplitude / first duration | Baseline and first duration both change |
| test0 / ETL8 scans | Single echo | PE order, navigator, RX gain and phase calibration also differ |
| testa / v1.8 scans | Legacy sequence | Δ, ESP, crusher implementation and slice separation differ |

The [complete comparison CSV](../docs/data/oct05_scan_comparison.csv) includes the table fields plus diffusion settings, custom arrays, RF scales, gradient calibration and crusher limits. The [embedded-protocol audit](../docs/data/oct05_protocol_audit.md) records source identities and pair differences. See the [analysis report with image and k-space comparisons](../docs/physical_scanner_experiments_2026-10-05.md) for observations and the conditional ramp-inclusive crusher-area calculations. Protocol settings alone do not establish scan quality.

Rebuild these tables after the protocol audit with `python docs/data/oct05_update_catalog.py`.
