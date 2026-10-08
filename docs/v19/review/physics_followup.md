# Independent physics follow-up: P2, P3, P5 and P7

Date: 2026-10-06. Scope: the fixes following `physics_review_final.md`, plus the new four-position phase-axis grouping. This review edits no implementation. It combines static inspection, existing independent C1-scan evidence and fresh bounded numerical checks. No scanner execution or vendor compilation was performed.

**Finding summary:** P2's benchmark crusher choice, P5's branch accounting and P7's landmark frame are corrected and supported by the checks below. Four-position phase grouping is valid for the present benchmark. The completed benchmark now passes the all-76-echo convergence checks, closing P3 for the tested cases. The completed event validator also passes the ODE comparison from the corrected physical landmark. No new blocking or major physics finding was found within this numerical scope.

## Reviewed bytes

| File | SHA-256 |
|---|---|
| `examples/v19_reference_benchmark.py` | `4287c10200ec13c6224a1785ea0f790d0bb80d8632c267ef534fc23403d225dc` |
| `examples/v19_validate_events.py` | `e4a6c5fc60914a7ce37b2854df9b3bb4d5d23554750276fe3396dd5fd3ea2d6b` |
| `dwfse/ppl/bloch.py` | `daee94bc9b41b6cad88b65a7480a68fde5f9bef9a0bc3899c2b4b8fa52d38ebd` |
| `dwfse/ppl/analysis.py` | `104e6bfd2be908af4aaf8f1bae9e0897fb835be9d8fecbee5cca342ef7c19d02` |
| `reference_benchmark/c1_resolution_scan.json` | `3a75c805acd420511c932121e022e0a4dcb925fc6dae5d212eaa3df505c3fea7` |
| `event_validation/btensor.json` at inspection | `9145856ff521c290ce5ae8c30ecda080b6c3e63e84e345d6ad74885e0099291d` |
| `reference_benchmark/results.json` completed output | `a3826bc96464fecc211bc715ed0662cd02bcaf8dc447ae1b5176904e5c9d09a5` |
| `event_validation/summary.json` completed output | `f3946106230fee32bf86411307473991af52dd4811ca9796bf35fd14e2f8c67c` |
| `event_validation/convergence.json` completed output | `c0159e7c429ad7fc43df1befb0777acd63209f936c30220d7fd6e645bcb37438` |

Fresh ledger checks used v191 `b8d2c4cae6443ba150464db95fcd113a787fd70f0cf9de64bc85da7cf255625d` and v192 `7e6393eaaac57f23d1f0f5d1718315ddf29e9df7ceffd923a1fd114920d20e55`; the source-generation confirmation is in `ppl_review_round4.md`. The completed validator summary records these same PPL hashes and unchanged PPR hashes, the required v18 baseline hash, `control_identity_all=true`, and nominal manual expression costs scaled by 0.8. The validator source hash was refreshed after its cost-model docstring was corrected; the inspected completed outputs report that same computational cost model.

## P2: reference C1 coincidence

The benchmark builder now uses C1=2550 cycles/m for two cycles and C1=5100 cycles/m for four, replacing 2250/4500. The independent-simulator scan records the following maximum magnitude spread over phases 0/45/90 degrees across the first 16 echoes without relaxation:

| Method | Cycles | Previous C1 and spread | Current C1 and spread |
|---|---:|---:|---:|
| Alsop | 2 | 2250: 0.174771 | 2550: 0.036945 |
| ss-MGOT | 2 | 2250: 0.022096 | 2550: 0.005034 |
| Alsop | 4 | 4500: 0.158759 | 5100: 0.014657 |
| ss-MGOT | 4 | 4500: 0.003172 | 5100: 0.002536 |

These values substantiate removing the old benchmark coincidence. They do not establish zero phase dependence or an exact reproduction of Gibbons. The scan also found smaller spreads at some other values (for example 5400 in the four-cycle cases); the present choice is a disclosed benign window, not a proved global optimum. The completed refreshed benchmark records C1=2550/5100 and the corrected grid sizes; its figure amplitudes supersede the older benchmark output.

## P3: late-echo spatial resolution

The source now uses 9000 z positions over 30 mm for two cycles and 18000 for four. It explicitly reruns all 76 echoes at 18000/27000 respectively, comparing the no-relaxation phase-45 Fig3 case for two cycles and the muscle-relaxation phase-45 Fig4 case for four. Each method/cycle pair must have maximum magnitude difference below 1e-5 before `results.json` is saved. Both maximum all-echo and first-32-echo differences are recorded.

The completed `results.json` now records these maximum magnitude differences across all 76 echoes:

| Method | Cycles | z-grid comparison | Maximum difference |
|---|---:|---|---:|
| Alsop | 2 | 9000 vs 18000 | 3.251931e-6 |
| ss-MGOT | 2 | 9000 vs 18000 | 8.612665e-7 |
| Alsop | 4 | 18000 vs 27000 | 5.365785e-9 |
| ss-MGOT | 4 | 18000 vs 27000 | 5.058868e-9 |

All four pass the 1e-5 assertion. **P3 is closed for these reference cases**, including the late echoes and ADC76. This is convergence evidence for the declared phase-45/no-relaxation two-cycle and phase-45/muscle-relaxation four-cycle comparisons; it does not constitute a grid-convergence sweep over every phase, B0 and B1 case.

### Four representative y positions

For the present benchmark, the replacement of 32 y positions by original indices `[18,19,16,17]` is exact for all exported snapshots and ADCs:

1. The original positions are `y_j=(j+1/2)/32` mm. The phase-axis spoiler is exactly 8 cycles/mm, so its completed phase is `(j+1/2)/4` turns. Positions separated by four indices differ by one full turn. There are four phase groups, each appearing eight times.
2. Before the spoiler, all RF and gradients are independent of y. The spoiler overlaps no RF; the next RF starts only after it ends. Its effect is a phase rotation of the existing transverse state, leaving longitudinal magnetization unchanged except for ordinary relaxation.
3. After the spoiler there are no further P gradients or y-dependent fields. Equal states within each group therefore remain equal. RF rotations and free evolution preserve this property; the common T1 recovery term makes relaxation affine rather than strictly homogeneous-linear, which still preserves equality and equal-weight means.
4. Every saved snapshot is either before or after the complete spoiler. The reduction would not reproduce an arbitrary snapshot during the spoiler, where the four-index separation has not yet accumulated a full turn. The current exports contain no such snapshot.
5. Each representative receives weight 1/4, identical to eight repetitions of each group in the original 32-point mean. Folded index 2 is original index 16, so the exported middle-column local magnetization remains the same physical sample.

I ran a fresh folded/full comparison with 300 z positions, phase 45 degrees, B0 +128 Hz, muscle relaxation, and the first two echoes using a 160/110/80/65/60-degree train. Maximum complex echo-signal difference was **4.22e-16**. Maximum mean-state difference across every saved landmark was **8.88e-16**; original local column 16 and folded column 2 matched **exactly** at every landmark and ADC. This is a check of phase grouping, not z-grid convergence.

The completed benchmark additionally records its own full-y32 versus four-group first-eight-echo maximum complex difference of **2.50e-17**, passing the 1e-11 assertion. This agrees with the independent bounded spot check and the phase-group derivation.

There is no hidden removal of transverse magnetization: `EventBloch.precess()` multiplies the full local complex transverse state by its phase and T2 factor, and RF samples rotate it. The grouping chooses representative positions; it never resets transverse state. A zero coherent average after the complete spoiler is cancellation among retained local states. The argument depends on the current exact spoiler area, absence of RF overlap/later P gradients, uniform y-independent preparation, and snapshot positions; future changes to these conditions require reconsidering the reduction.

## P5: carrier and conjugate b paths

The validator now computes both the carrier path and a conjugate path with an extra `k -> -k` at the method RF centre (Alsop elimination or ss-MGOT re-excitation). It retains the ss-MGOT longitudinal freeze between tip-up and re-excitation. Both candidate endpoint vectors and diagonal b values are recorded, and the candidate with smallest endpoint-vector norm is selected.

I freshly mapped the current PPLs at nominal b=1000 and integrated each candidate using the independent exact piecewise-linear k integrator in `physics_checks/check_btensor.py`. This integration uses gradient breakpoints and the analytic integral of `k k^T` in each interval; it does not use the writer's sampled `k_path()` or `b_tensor()`.

| Method | ADC | Selected branch | Exact kS endpoint, cycles/m | Exact bSS, s/mm² | Exact bRR, s/mm² |
|---|---:|---|---:|---:|---:|
| v191 | 1 | carrier | -116.602 | 18.613593 | 995.924486 |
| v191 | 2 | conjugate | 57.487 | 27.716250 | 997.448247 |
| v191 | 8 | conjugate | 57.487 | 89.728682 | 1006.583766 |
| v192 | 1 | carrier | -105.838 | 19.281096 | 995.755166 |
| v192 | 2 | conjugate | 113.034 | 27.911433 | 997.278928 |
| v192 | 8 | conjugate | 113.034 | 90.693413 | 1006.414446 |

The saved sampled results choose the same branches. Maximum absolute bSS difference is **0.166 s/mm²**, and maximum bRR difference is **0.044 s/mm²**, across these fresh checks. Residual endpoint differences reach about 17 cycles/m by ADC8 because the writer samples k with a 2-us step; this is far below the prior approximately 2D mismatch. Thus the even-echo omission is corrected within the existing numerical model.

The branch selection is a diagnostic for the two desired harmonic histories. It is not a full enumeration of the diffusion tensors and weights of every pathway created by finite, imperfect or low-angle RF. The instantaneous-conjugation and longitudinal-freeze approximations of the earlier b calculation remain.

## P7: physical gradient landmarks

The shared `physical_landmarks()` helper shifts all list-defined landmarks by the configured gradient latency and leaves `pre_RF1_after_crusher` at its RF-defined time. Fresh current-ledger inspection gives +60 us for A, B, after-tip/elimination, after-spoiler/re-excitation and the endpoint before the leading crusher; pre-RF1 shifts by zero for both methods.

`run_bloch()` uses this helper with the same latency passed to its simulator. The ODE comparison now uses this same helper for its initial B snapshot and integration start. It therefore starts from the state after the delayed physical dephasing lobe, rather than mixing a commanded snapshot time with delayed gradients.

The completed validator's five-spin ODE versus exact-rotation maximum component errors are **6.69e-10 for v191** and **7.42e-10 for v192**. The recorded windows are 112663.74..135774.14 us and 110903.82..128300.10 us respectively. This supports the corrected physical-frame comparison and closes the previously pending ODE outcome. The same completed output records scanner-adaptation z3000/z6000 maximum complex differences of 4.32e-7 / 9.98e-7, RF substep differences below 8e-16, and v191 y32/y64 difference 1.15e-4. These numerical checks retain the disclosed event, calibration and delay assumptions.

## Retained limits

The benchmark still uses research RF, an assumed prep TE and crushers, and an approximate Busse-style train. The broader Alsop elimination profile and prep-TE amplitude scaling are now explicitly disclosed in its docstring. Local phase grouping does not validate the scanner adaptation's different non-integer phase-voxel spoiler, phase encoding or hardware behavior. Scanner calibration, console instruction costs, finite-RF diffusion-path modeling and quantitative reproduction of the publication remain outside these checks.
