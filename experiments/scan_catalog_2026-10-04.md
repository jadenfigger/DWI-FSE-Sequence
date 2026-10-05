# Scanner experiments — October 4, 2026

PPR comparison in acquisition order. All scans use TR 2000 ms, 128 readout samples at 50 µs, FOV 35 mm, slice thickness 1 mm, diffusion enabled, and diffusion duration (`sm_delta`) 4 ms. Crusher amplitudes below are **first-DWI / train baseline** in DAC units, before schedule scaling.

| Order | Scan / PPR | PPL version | Views / echoes per segment | TE / ESP / Δ (ms) | Requested b (s/mm²) | Crusher baseline | Crusher schedule |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [test0](FSE-DWI_10-04-2026_v16_test0/FSE-DWI_10-04-2026_v16_test0.ppr) | 1.6 | 160 / 32 | 54 / 16 / 40 | 0, 6000 | 2754 / 5482 | Constant |
| 2 | [test1](FSE-DWI_10-04-2026_v17_test1/FSE-DWI_10-04-2026_v17_test1.ppr) | 1.7 | 160 / 32 | 54 / 16 / 40 | 0, 6000 | 2754 / 5482 | Constant (0) |
| 3 | [test2](FSE-DWI_10-04-2026_v17_test2/FSE-DWI_10-04-2026_v17_test2.ppr) | 1.7 | 160 / 32 | 54 / 14 / 40 | 0, 1000, 6000 | 5482 / 5482 | Constant (0) |
| 4 | [test3](FSE-DWI_10-04-2026_v17_test3/FSE-DWI_10-04-2026_v17_test3.ppr) | 1.7 | 136 / 8 | 54 / 14 / 40 | 0, 1000, 6000 | 5482 / 2741 | Constant (0) |
| 5 | [test4](FSE-DWI_10-04-2026_v17_test4/FSE-DWI_10-04-2026_v17_test4.ppr) | 1.7 | 136 / 8 | 54 / 14 / 40 | 0, 1000, 6000 | 5482 / 2741 | Increasing (1) |
| 6 | [test5](FSE-DWI_10-04-2026_v13_test5/FSE_dwi_CPMG_non_CPMG_twoTE-1.3.ppr) | 1.3 | 136 / 8 | 54 / 15 / 32 | 0, 1000, 6000 | Not exposed in PPR | Legacy; no schedule field |
| 7 | [test6](FSE-DWI_10-04-2026_v17_test6/FSE-DWI_10-04-2026_v17_test6.ppr) | 1.7 | 136 / 8 | 54 / 14 / 40 | 0, 1000, 6000 | 5482 / 2741 | Increasing + alternating (3) |
| 8 | [increasing](FSE-DWI_10-04-2026_v17_increasing/FSE_dwi_CPMG_non_CPMG_twoTE-1.7-increasing.ppr) | 1.7 | 16 / 8 | 36 / 16 / 20 | 0, 1000 | 2754 / 5482 | Increasing (1) |
| 9 | [increasing-alternating](FSE-DWI_10-04-2026_v17_increasing-alternating/FSE_dwi_CPMG_non_CPMG_twoTE-1.7-increasing-alternating.ppr) | 1.7 | 16 / 8 | 36 / 16 / 20 | 0, 1000 | 2754 / 5482 | Increasing + alternating (3) |
| 10 | [test7](FSE-DWI_10-04-2026_v17_test7/FSE-DWI_10-04-2026_v17_test7.ppr) | 1.7 | 136 / 8 | 54 / 14 / 40 | 0, 1000, 6000 | 5482 / 5482 | Decreasing (4) |
| 11 | [test8](FSE-DWI_10-04-2026_v17_test8/FSE-DWI_10-04-2026_v17_test8.ppr) | 1.7 | 136 / 8 | 54 / 14 / 40 | 0, 1000, 6000 | 5482 / 2741 | Decreasing (4) |
| 12 | [test9](FSE-DWI_10-04-2026_v17_test9/FSE-DWI_10-04-2026_v17_test9.ppr) | 1.7 | 160 / 32 | 54 / 14 / 40 | 0, 1000, 6000 | 5482 / 5482 | Constant (0); exact PPR repeat of test2 |

All varying schedules use `crusher_step_pct=40` (40% of the train baseline per step); constant schedules use 0. First/train crusher durations are 1000/1000 µs except test5 (2000/2000 µs), which also uses legacy b/direction arrays and slice separation 1.09907 mm rather than 1.2 mm. Navigators are on with 4 discarded acquisitions except the two named increasing scans (off, 8 discarded acquisitions). Test0, test1, and the two named increasing scans store three zero-angle orientation/offset entries with slice offsets −1.2, 0, +1.2 mm; the others store one centered entry. Every PPR specifies `no_slices=1`.

The 12 physical-scanner experiments compared the v1.6 baseline with v1.7, then varied echo spacing, b-value coverage, first/train crusher balance, and echo-train length. The eight-echo tests compared constant, increasing, increasing-plus-alternating, and decreasing crusher schedules, with a v1.3 legacy-protocol comparison at test5. After test6, the two named increasing scans used shorter TE and diffusion separation, fewer views, and different navigator/dummy-acquisition settings, so their protocols differ in several factors from the numbered schedule tests. Test7 and test8 compared decreasing schedules at two train baselines, and test9 repeated test2 with a byte-identical PPR. This catalog records protocol settings; it does not assess scan quality.
