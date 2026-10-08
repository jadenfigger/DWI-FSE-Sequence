# v191 (ss-MGOT) and v192 (Alsop): implementation report

Status: source implementation complete; **not compiled, not console-verified**. Read the statuses in [README.md](README.md) before using any file. Primary sources:
- [Gibbons et al., MRM 2018](https://doi.org/10.1002/mrm.26971): Fig 1, Methods pp. 3034–3037, SI S1/S2.
- [Alsop, MRM 1997](https://doi.org/10.1002/mrm.1910380404): pp. 529–530.
- The supplied EVO PPL manual.
- The actual v18 source (SHA-256 `3b420376…598db2`, unchanged).

## Files

| File | Role |
|---|---|
| `examples/build_v19_ppl.py` | Single generator. It applies anchored insertions to the verified v18 bytes and derives both PPRs from the October test1e protocol. It replaces the superseded `build_v191.py` / `build_v192.py`, which were removed. |
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl` / `.ppr` | v191 ss-MGOT. Eight-echo test1e protocol plus V19 parameters. |
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.92.ppl` / `.ppr` | v192 Alsop. Same base protocol. |
| `scanner/rf/v19_research_rf.seq` | Six real research RF frames. See [rf_install_calibration.md](rf_install_calibration.md). |
| `dwfse/ppl/` | PPL preprocessor, parser, typed interpreter/event mapper, waveform reconstruction, ledgers, event-driven Bloch, b-tensor and ODE checks. |
| `examples/v19_validate_events.py` | Validation of the actual PPLs through the mapper. Writes `docs/v19/event_validation/`. |
| `examples/v19_reference_benchmark.py` | Gibbons-geometry reference benchmark, deliberately separate from the scanner adaptation. Writes `docs/v19/reference_benchmark/`. |
| `tests/test_v19_ppl_mapper.py` | Fast regression: v18 hash, control identity, method RF centres, absence of hazards, rejection before events. |

## Control path (`v19_on = 0`)

Both PPLs consist of the v18 bytes plus insertions. With `v19_on = 0` the only additions that execute are:
- a one-time setup `if` before `sync()`;
- writes to the unused `NEWSHAPE` indices 18–23;
- four `v19_mode` tests, all inside v18's padded timer windows.

The method branch (`if (v19_mode==1) goto v19_mat_window;`) sits inside v18's timed 3000 µs setup window, so the control path gains no untimed statement.

The mapper compares v191/v192 against v18 over two shots, for the original schedule and for crusher schedules 1, 2 and 4. RF, ADC, gradient segments and matrix values after `sync()`, including the sync→first-RF interval, are identical. One-time setup before `sync()` moves by a few µs of untimed statements and is compared by content.

The `#use … pf19` line requires the new library to be present even in control mode.

## Method path (`v19_on = 1`)

`v19_on`, `v19_cycles` and the other method parameters are plain ints. Setup validates them once and latches `v19_mode`, so an interactive toggle cannot run unbuilt lists. Each shot runs:

1. `v19_mat_window`: completes v18's 3000 µs window, then creates every method matrix under `ss_mat` in two padded windows of 2500 µs each.
2. **Preparation (both methods).**
   - SLR 90° excitation at axis 0°. v191 uses a slab of `v19_slab_pml` = 3000‰ of the slice (Gibbons 18/6); v192 uses the imaging width.
   - Compensation lobe sized from the fitted post-RF correction (κ·G·T) plus the actual plateau pad and the ramp-down area. Ramp areas come from the library samples: 0.4904/0.5096 primary, 0.5/0.5 for `NEGPULSE_SEC`.
   - Diffusion lobe 1, then the SLR 180° at axis 270° with the first diffusion crushers C1, then diffusion lobe 2. The lobes are symmetric about the 180°, with Δ measured onset to onset.
3. **Added dephasing D**: a `POSPULSE_SEC(tdp)` lobe of `v19_cycles` across the slice. The DAC is computed in PPL as cycles·|gs_var|·10⁶ / (1070·(tdp+tramp)), so the gradient calibration cancels. D takes the train-crusher polarity (Gibbons Fig 1: left C−D, right C+D). Landmarks A and B fall before and after this lobe.
4. **Method block**, centred on the preparation echo at `te`:
   - **v192 Alsop.** Selective SLR 90° elimination at axis 270° (the refocusing axis). My is retained and Mx goes to −Mz. Pre- and post-compensation lobes are applied. The single read prephaser of v18 is played here on R, with area G1·(tref+tramp) on a tdp lobe. No storage, spoiler or re-excitation exists in v192.
   - **v191 ss-MGOT.** Pre-compensated SLR 90° tip-up at axis 180° over `v19_tip_pml` = 1667‰ (10/6), which stores the MG component (My) on Mz. A phase-axis spoiler of `v19_spoil_cpmm` cycles/mm follows (32, i.e. 8 cycles per 0.257 mm phase voxel). Then a slice-selective re-excitation at axis 0° with post-compensation, and the read prephaser on R.
5. **Imaging train**, starting from T0 (the elimination centre, or the re-excitation centre):
   - RF k is centred at T0 + (k−½)·ESP and the echo at T0 + k·ESP.
   - Each refocusing pulse is a 1.2 ms Hamming-sinc 180° frame with crushers C | RF | C and flip `v19_flip_tenths[k]`. The multiplier is precomputed at setup, so no arithmetic runs in timed sections.
   - The pre-ADC slice-PE lobe of v18's `slice_list_rp` carries **+D recall**; the post-ADC lobe carries **−D restoration**. Both use the same `POSPULSE_SEC(tdp)` shape as the D lobe, so the areas match exactly and no time is added. This realises the first-RF contract (pre C, post C+D) and the later fused C−D contract from the physics review.
   - Readout, PE, ADC, receiver phase and phase correction follow v18's structure.
6. **Return**: the shot rejoins v18 at `v19_after_train`, which runs the post-ETL crusher and the TR delay. TR uses the method shot length, v18's 11350 µs of setup windows and the method matrix windows.

**Timing construction.** Every event starts at a known offset from a gradient-list start, inside padded `starttimer`/`waittimer` windows that stay below 4.9 ms after their anchor, or after an exact `delay32` gap.
- RF centre = plateau centre + `rfdelay`, which is v18's documented gradient-group-delay compensation.
- The ADC uses v18's placement (3·tramp + tdp + rfdelay after the read-list start).
- The post-initiate calculation window keeps v18's 8997-tick budget.
- The amplifier is unblanked warmup + (rfgate_delay − 17) + 10 µs before each RF.
- No arbitrary reserves are subtracted (prior finding A2).

Three named, documented estimates remain until a console trace exists: V19_ANCHOR (0.5 µs), V19_INIT_COST (7.6 µs) and `delay32` overhead (0).

**Rejected before any event**, with an informative message:
- DWI off; legacy or scheduled crushers; DE, flow compensation, Dixon, 3D, skipped echoes, TREF setup.
- Multislice or slice offset. The constant transmit frequency only serves widths centred on isocentre; a temporary central-slice restriction.
- Presat, CHESS, CEST, gating, mains gating, TR arrays.
- Slice or read off, gsp_lobe, post-90/phcor0 trims.
- diff_tramp ≠ tramp; rfgate_delay < 17; tramp + rfdelay < 163 µs.
- Raster violations; any TE/Δ/δ/ESP/ADC/TR infeasibility.
- Any flip outside 0.1–180°; DAC, slew or 16-bit window overflows.
- Dephasing cycles other than 2, nonnegative crushers, or |C|/|D| outside 3.83 ± 0.02 or |C1|/|D| outside 2.55 ± 0.02. The rounded integer comparisons are deliberately narrow around the validated geometry.

## Method-specific protocol choices (disclosed departures)

| Item | Choice | Reason / status |
|---|---|---|
| Train crusher | `crush_amp` = −8223 DAC, 3× test1e | With the old \|C\| ≈ \|D\| setting, the FID of one RF refocused by the next has residual \|D−C\| ≈ 551 cycles/m and interferes with the recalled echo. C+D was an incorrect label from the draft with reversed D polarity. Alsop echo 1 varied 0.07–0.51 in that exploratory setting. The PPL now locks the scanned C/D geometry. **Comparisons with v18 controls differ in train crusher.** |
| First crusher | test1e −5482 DAC | The scanned point is retained. The earlier coincidence guards were insufficient; a narrow C1/D window now excludes unvalidated families. |
| D | 2 cycles across the 1 mm slice (2003 cycles/m) | Gibbons uses 2 cycles (Fig 3/S2) and 2/4 (Fig 4). Only two cycles are validated for the scanner files; other values are refused. |
| RF | Research SLR / Hamming frames, inferred calibration | Not Gibbons' spectral-spatial tip-up or windowed sincs. The tip-up does not suppress fat. |
| Refocusing schedule | 142.2/94.9/69.2/63.0/60.2/60/60/60° for both methods | Alsop 1997 published first five angles, completed at 60°. Gibbons' Busse schedule is unpublished, and the centric eight-echo control puts the k-space centre at echo 1, so ss-MGOT uses the same stabilised ramp (minimum 60° ≥ the published 55°). The two adaptations differ only in their preparation mechanism. |
| Imaging RF | 1.2 ms Hamming 180° frame instead of v18's 1332 µs 3-lobe sinc ×185% | New RF train: report-level difference from the v18 controls. |
| `alpha`, `p180_scale`, `rfnum` | Ignored on the method path | Each frame needs its own console calibration. |

## Coordinate convention and phases

Repository frame: dM/dt = 2π(M×B), m = Mx + iMy, phase 0 rotates +Mz to +My, positive gradient area A gives m·exp(−i2πAz). With `phase_increment(1)` (0.225° per unit, `deg_90` = 400), the relative axes are:

| Pulse | Axis |
|---|---|
| Preparation 90° | 0° (`phase_90`) |
| Preparation 180° | 270° (`phase_180`) |
| ss-MGOT tip-up | 180° (`phase_90 + 2·deg_90`): My → +Mz |
| ss-MGOT re-excitation | 0° |
| Alsop elimination | 270°: My retained, Mx → −Mz |
| Imaging refocusing | 270°, plus v18's `phase_correction` |

This is the coordinate transformation φ = φ_paper − 90° of the Gibbons Fig 1 axes. Physical transmitter polarity is not calibrated. The event Bloch confirms the mechanisms with these exact mapped phases (see README).

## How the validation numbers are produced (plain English)

No MR Solutions compiler, simulator or scanner was available, so nothing here was compiled or run on hardware. Every number comes from the following chain.

1. **Read the real sequence file.** A Python program (`dwfse/ppl/`) reads the actual `.ppl` file, including the vendor include files and their macros, exactly as written. It runs it line by line, like a very literal computer. It obeys the scanner's 16-bit and 32-bit integer rules, so overflows and truncations show up as they would on the scanner. It loads the real protocol values from the `.ppr` file, e.g. TE 54 ms, ESP 14 ms, eight echoes.
2. **Pretend to be the hardware.** Whenever the program reaches a command that would drive hardware, the Python program records what that command would do and when:
   - "start this gradient list", "select this matrix";
   - "play this RF frame at this phase", "open the receiver";
   - "wait until this timer value".

   It uses the real gradient ramp shapes and RF waveforms from the binary library files. It obeys the documented timer rule: if code runs past a requested wait, the scanner adds a full 5 ms. The result is a time-stamped list of every RF pulse, gradient waveform and receiver window in one repetition, called the "event ledger".
3. **Estimate how long the code itself takes.** The scanner's processor needs time to execute statements. I used the manual's published per-operation times (for example, a 32-bit division takes about 123 µs), scaled by 0.8. That scale makes v18's own timing windows match the usage that v18's authors measured and wrote in its comments (for example 5016 and 8236 timer ticks). It also lets v18 run without overruns, which it must, since it produced real images. I re-ran everything with faster and slower cost assumptions to check that the new sequences still hold their timing.
4. **Check the ledger directly.** From the ledger the scripts measure:
   - **RF pulse centre times and echo times**, compared with the design. Example: the Alsop elimination target is 54.000 ms; the nominal manual-cost model differs by a few microseconds.
   - **Gradient areas between events**, giving the "k-value" that sets each signal pathway's phase pattern. This shows whether the added dephasing D is recalled before every acquisition and undone after it.
   - **Hazards**: missed timer deadlines, gradient lists started while another is still playing, matrices used before they are computed.
   - **Rejection behaviour**: illegal protocols must stop before any RF or gradient is played.
   - **The v19_on = 0 control path**: its ledger is compared item by item with v18's.
5. **Simulate the magnetization from the ledger.** The recorded RF waveforms and gradients are fed into a Bloch-equation simulator that tracks thousands of tiny magnet "spins" spread across the slice. For ss-MGOT it also spreads spins across one in-plane voxel, so the spoiler's dephasing averages out naturally instead of being deleted by hand. The simulator rotates each spin exactly as the RF and gradients dictate. At each landmark and at the middle sample of each acquisition it reports:
   - the signed Mx, My, Mz of individual spins;
   - the average over the voxel;
   - the summed slice signal, expressed as a fraction of the signal the whole slice would give if perfectly refocused.

   The runs vary the starting magnetization phase (0°/45°/90°), the RF strength (nominal and 80%) and the off-resonance (−128/0/+128 Hz).
6. **Check the simulator itself.** The same cases are re-run with twice as many spins and with each RF sample split into four. An independent general-purpose ODE solver also integrates the Bloch equations over a full RF-plus-echo window for selected spins. The answers must agree to tiny tolerances.
7. **Diffusion weighting.** The script follows both recalled branches, including conjugation at the elimination centre (Alsop) or re-excitation centre (ss-MGOT), and chooses the branch whose wave-vector ends nearest zero at each acquisition. This corrects the earlier even-echo carrier-only calculation. Both candidates are saved in the JSON. Sign flips at refocusing pulses and the ss-MGOT storage interval are included. The b-tensor integrates the squared wave-vector history, including crushers, selectors and recall lobes.
8. **Reference benchmark (separate).** A second script builds idealized sequences at the paper's geometry (30 mm, 6 mm slice, 18 mm slab, 10 mm tip-up) using the same research RF pulses. It uses 9000 z points for two cycles and 18000 for four, compared against 18000/27000, because 3000 points aliased late pathways. The 32 in-plane spins fall into four equally weighted phase groups after the complete eight-cycle spoiler; this exact grouping is checked against all 32 spins, and retains the displayed local spin. No transverse state is deleted by hand. C1 is moved away from measured coincidence windows (2550 and 5100 cycles/m). These numbers describe the mechanisms at the paper's scale; they cannot reproduce the paper exactly because its RF pulses and flip schedules are unavailable. The short, broad-transition 1.2-ms elimination biases the benchmark against Alsop. The assumed 30-ms preparation TE mainly rescales the desired transverse signal by T2 decay; it does not support matching the paper's absolute amplitudes.
9. **Crusher-window evidence.** The actual pre-restriction PPLs were mapped at nine C/C1 combinations for each method. Three initial phases were simulated at each point, and the largest difference between phases over eight echoes was recorded. Four corners of the narrow supported window were then checked the same way. The retained text copies and input hashes make these exploratory runs reproducible; the final scanner PPLs reject values outside that window.

Gradient-defined landmark snapshots include the assumed 60-µs gradient latency, so they are taken after the physical ramp ends. The pre-RF1 snapshot remains referenced to RF timing. Receiver samples retain their original acquisition times.

**What these numbers do not show.** They do not show:
- the real execution speed of the console;
- hardware delays: gradient lag, RF pipeline, receiver filter;
- actual RF calibration on the scanner;
- image quality.

The timing numbers are "nominal source-level" estimates. The simulations assume the inferred RF calibration and a gradient lag equal to `rfdelay`, as v18 intends. All of these need a compiler trace and scanner tests.

## Validation evidence

See README.md for the result summary and `docs/v19/event_validation/`:
- `control_identity.json`, `timing_*.csv`, `timing_summary.json` (cost-model sensitivity);
- `hazards.json`, `rejection_tests.json`, `moments.json`, `btensor.json`;
- `bloch_results.json`, `landmark_summary.json`, `profiles_*.npz/png`, `convergence.json`, diagrams.

The reference benchmark is in `docs/v19/reference_benchmark/`.

## Final follow-up: P1–P9

The final files and outputs are inventoried with exact SHA-256 hashes in [final_manifest.json](final_manifest.json). The README lists the PPL, PPR, RF library and generator hashes explicitly. v18 retains its original hash.

| Finding | Resolution and evidence |
|---|---|
| P1: first-crusher guard | The 3×3 C/C1 scan and four supported-window corners cover both actual PPL methods. The generator now restricts method mode to two cycles, negative crushers, C/D = 3.83 ± 0.02 and C1/D = 2.55 ± 0.02 using rounded integer areas. Boundary maximum phase spread is 0.00379 for ss-MGOT and 0.02120 for Alsop. |
| P2: reference crusher coincidence | C1 is 2550/5100 cycles/m for two/four cycles. An independent simulator confirms smaller phase spread than 2250/4500 over the first 16 echoes. This is a supported choice, not a proved global optimum. |
| P3: late-echo aliasing | Reference grids are 9000/18000 points, checked against 18000/27000 through echo 76. The maximum normalized magnitude difference is 3.25194e-6. Checks use phase 45°, two cycles without relaxation and four cycles with muscle relaxation. |
| P4: moment label | The old small residual is labelled \|D−C\|, rather than the reversed-polarity draft's C+D. |
| P5: even-echo b pathway | Both carrier and conjugate histories are retained. The smallest endpoint wave-vector selects each ADC's desired branch. Independent piecewise integration confirms the selection; sampled bSS/bRR differences are at most 0.166/0.044 s/mm² in the checked cases. |
| P6: off-resonance range | Alsop's nominal-B1 echo-1 range, 0.21–0.38, now includes all three phases and −128/0/+128 Hz. |
| P7: landmark latency | Gradient-defined snapshots include the assumed 60-µs latency; the pre-RF1 snapshot remains RF-referenced. The corrected five-spin ODE checks agree within 7.43e-10. |
| P8: elimination profile | The broad-transition 1.2-ms reference elimination biases the comparison against Alsop; it is explicitly disclosed. |
| P9: preparation TE | The assumed 30-ms preparation TE mainly sets the desired transverse T2 amplitude scale; the benchmark does not match the paper's absolute amplitude. |

All five mapper regression tests passed on the final PPL bytes. The full event validator completed successfully in 694.12 seconds: control identity holds for both methods, all 19 rejection cases stop before RF/ADC, and the declared numerical checks pass. Doubling the slice grid changes the complex signal by at most 9.99e-7; refining RF samples changes it by less than 8e-16. The ss-MGOT y32/y64 check differs by 1.16e-4. The reference benchmark also completed successfully, including every declared 76-echo grid check. Its exact four-group spoiler reduction agrees with all 32 positions to 2.51e-17 over eight echoes.

These errors are obtained by subtracting the two runs' signals or magnetization components and taking the largest absolute difference in the stated comparison. Phase spread is the largest difference between the three initial-phase signal magnitudes at any echo; it is not a relative percentage. The b-tensor spot check independently integrates the piecewise gradient history rather than reusing the writer's sampled integrator.

[PPL review round 4](review/ppl_review_round4.md) confirms generator reproducibility and the new guards on the final hashes. [Physics follow-up](review/physics_followup.md) confirms the branch and landmark fixes and closes P3 for the tested reference cases. No blocking or major finding remains within that scope.

Implemented: yes. Compiled: no. Simulated: yes, under the nominal source-level assumptions. Independently reviewed: yes. Verified on scanner: no. Nothing was deployed. The optional 95/185-µs isodelay refinement, console timing, RF/gradient calibration, RF fidelity and full finite-RF diffusion-path modelling remain unresolved as described in the README.

## Console compiler compatibility correction

On 2026-10-06 the user attempted console compilation of both methods. The vendor preprocessor expanded function-macro names inside new `//` comments and ran out of argument-expansion space in `V19_COMP`. The generator now writes every function-like V19 helper as ordinary statements and emits no comments in its additions, including the added parameter entries. Vendor macros and the inherited v18 code remain intact. Added diagnostic messages are split into literals of at most 48 source characters, without splitting format conversions or separating them from their arguments. The actual vendor string cutoff remains unknown.

The fifth regression check compares all preprocessed computational tokens against hashes captured before this correction, excluding diagnostic print statements. Both complete sequences match exactly, including integer calculations, pulse/gradient calls and timing operations. The PPRs and RF library are unchanged. The original numerical results therefore describe the same computations; the full event validator completed on the compiler-corrected PPLs in 694.12 seconds, with unchanged numerical results. The subsequent user-requested RF library path change is checked separately against those exact full-run sources over two shots: all RF, receiver, gradient, matrix and timer histories match. The full-run summary retains its actual input hashes; [rf_path_event_identity.json](compiler_compatibility/rf_path_event_identity.json) links them to the final source hashes without relabelling historical outputs. The earlier validation summary, b-tensors, convergence results and manifest are retained under [compiler_compatibility/](compiler_compatibility/) as historical provenance. Successful console recompilation remains unverified.

## PPLC v7 scratch reduction trial

The next console compile passed preprocessing but failed with E106 (far scratch space overflow) in both methods. Its exact allocator limit is not documented in the supplied manual. This trial removes 167 setup `IntToLong` calls in v191 and 128 in v192. Each verified signed16-bit argument remains parenthesized before promotion through `0L+`; complete assignment to long relies on the manual's signed implicit widening. This preserves intermediate16-bit arithmetic and subsequent32-bit operations without relying on textual adjacency or operator precedence. Constants use long literals. Unknown or long-valued arguments cause generation to fail rather than being silently rewritten.

The three inherited comparisons with signed minimum now use `(-32767-1)` in the generated files, avoiding the compiler's positive32768 constant warning while preserving the same rejection. v18 itself is unchanged. The inherited v192 frequency conversion warning W008 is unchanged. No timed RF, gradient or ADC source was modified, and the PPRs and RF library are unchanged.

Six mapper tests pass, including event and setup-variable equality versus the preceding files at nominal, rfcal550, compensation flat800us, and a supported crusher-window corner. Timing comparisons round at1e-6us, well below the0.1us hardware tick; setup duration can change. [Scratch trial evidence](compiler_compatibility/scratch_reduction_results.json) records exact input hashes. The fresh full event/Bloch validator completed on the exact candidate hashes in 695.13 seconds. Control identity holds, all 19 rejection cases per method have zero RF/ADC, and convergence results remain within the previously reported bounds. The numerical b-diagnostic comparison differs from the original by at most 2.92e-11 (in an event timestamp). Successful vendor compilation and resolution of E106 remain unconfirmed.

## Second E106 trial: diagnostic and workspace compaction

The console retry reported E106 at the same source lines2998/3268 despite the preceding conversion rewrite; W010 disappeared. This weakens the conversion-call explanation. The original v18 history documents earlier compaction to fit near65500 bytes, but the supplied manual still does not identify the E106 pool. The current trial makes measurable reductions in diagnostic literals and print calls without cutting any normal control mode or table capacity.

Generated-copy terminating prints are replaced by a single scalar error-code assignment followed by their original goto. The statement remains atomic, preserving braced and unbraced control semantics. Added method failures use the same shared handler. The code is explicitly reset before the first executable source statement, and normal completion prints nothing. Diagnostic numeric arguments are omitted; full code/message mappings are bundled with the ZIP. The original v18 and vendor headers are unchanged.

The computed method multiplier array now uses the native crusher workspace. The non-common schedule variable must be0 at the method gate before any write, and all later inherited table reads are under nonzero-schedule branches bypassed in this mode. The method-off path keeps the original workspace. The independent input flip array remains separate. This saves128 bytes, or126 net after the error-code int. Seven mapper tests cover nominal and modified method settings, rejection dispatch, and normal control schedules0/1/2; source/event timing remains a nominal estimate. Successful compilation and E106 resolution remain outstanding.

The final follow-up preserves the successful `validate=1` Duration print; it is not a fatal message. Eight tests pass, including exact agreement of that output with v18 and zero ADC/error events. The full validator completed in677.22seconds on the recorded pre-restoration hashes. The restoration changes diagnostic behavior and subsequent fatal code numbers only; two-shot event comparisons over seven cases per method bridge those exact input sources to the final hashes. The final manifest retains both identities. Source literal counts include54printf calls per method after retaining Duration, with quoted contents5007/4937 characters; this is not measured compiler allocation. E106 remains unverified on the scanner.

## Third E106 trial: forward label references

The compact build failed E106 again, at v191 line 2974 (`goto end`) and v192 line 3247 (`goto v19_skip_te2`): the same statements as both earlier trials. Counting over the preprocessed token stream, each of the six failing compiles fails at exactly its 147th forward `goto`. The string, token, `if`, conversion and pending-reference counts at those sites all differ, and the earlier reductions did not move the site. v18 compiles with 145 forward gotos in total. The exhausted far-scratch resource is therefore PPLC's table of references to labels not yet defined. v19 added 70 (v191) and 57 (v192) forward jumps, mostly error guards to `end`.

The generator's final pass `backward_stop_hub()` defines `v19_fail:`/`end:` in a hub immediately after the first executable statement, skipped by one `goto v19_run`. The hub jumps once to `v19_exit:`, the former `end` position with the shared error print. All later `goto end`/`goto v19_fail`, including those expanded from vendor matrix/deglitch macros and `tstex_15.pph`, become backward references. Forward gotos fall to 22 per method; no other line changes. The extra jump runs only on terminating paths. Over two shots in 10 cases per method, RF, gradient, ADC, printed output and error codes are identical to the v2 files. A new mapper test caps forward gotos at 40; nine tests pass. [Results](compiler_compatibility/forward_label_results.json). Console compilation remains unconfirmed.

## Fourth trial: compiler warning limit

The v3 build cleared E106 and compiled to about line 4900. Both methods then stopped with "Too many errors - aborting" after 20 messages, all W007/W008. PPLC counts warnings toward that abort. The manual declares `waittimer(int exit_time)` and states that a long argument is converted to its low 16 bits with a warning. Eleven messages are inherited from v18 statements. The rest came from the method shot, where 46 (v191) / 37 (v192) `waittimer` calls received long tick expressions. A static AST check reproduces both 20-message console lists exactly (reported line = statement end + 1). `scale()` takes a long first argument without warning, as in v18.

The generator's `int_timer_arguments()` assigns each long argument to an int (`v19_i_*`) once in setup, immediately before `v19_mode = 1` and after every feasibility check. Long-to-int assignment keeps the same low 16 bits without a warning. Constants become int literals, and `v19_wait_next` becomes int. The pass asserts that no operand is assigned after setup. Arguments are evaluated before the wait, so waittimer exits are unchanged and timed windows gain slack. The unreferenced `v19_shot` label, a latent W003, is removed. Predicted W007/W008 now equal v18's 11 in each method, and no W002/W003/W005/W006 candidate remains. Over two shots in 14 cases per method, RF, gradients, ADC, output, error codes and overrun flags are identical to v3. A new test pins the long-argument set to v18's; ten tests pass. [Results](compiler_compatibility/warning_limit_results.json). Console compilation remains unconfirmed.

## Fifth trial: .fth branch range

The v4 PPLs compiled with exactly the 11 predicted warnings. The .fth stage then reported "error branch is out of range" at lines 10235 (v191) and 9405 (v192). The whole method setup sat inside one `if (v19_on==1) { … }` body: 3964 / 3230 AST nodes, against a v18 maximum of 369. Every other v19 conditional body is v18-sized. The reported lines fall at the end of that block in both methods, about 0.92 .fth lines per preceding node. The 830-line difference between methods matches their 769-node setup difference, while the block starts differ by 35 nodes. The manual times `if`/`until` as a 100-ns conditional branch and `goto` as a 1.1-us jump, and v18 runs with gotos spanning 13,050 nodes. The setup therefore opens with `if (v19_on!=1) goto v19_setup_done;` and closes at that label; no setup statement changes. The largest conditional body is now 379 nodes: v18's crusher block, in which each printf became an error-code assignment (one extra node, less code). Events, outputs, error codes and overrun flags are identical to v4 over 14 cases per method. A new test bounds conditional bodies by v18's largest; eleven tests pass. The longest v19 goto (18,918 nodes) exceeds v18's proven span, but the .fth stage did not flag any goto. [Results](compiler_compatibility/branch_range_results.json). Download and execution remain unconfirmed.

## Seventh trial: method-only PPLs

The v6 PPLs compiled and passed the .fth stage, but pplsim reported "step math opcodes not supported", v1.91 printed a tstex message that requires phase_cycle=2 although the PPR sets 1, and a rerun crashed. The v6 .fth files contain no Forth word or inline opcode absent from v18's console .fth. v18's history documents a hard 64K image ("too big to fit in 64K", "default size 65490"). A size model (2.6 bytes per AST node from the console .fth files, plus arrays and strings) puts the combined builds 11.1 / 8.6 KB above v18; corrupted parameters and undecodable instructions are the expected symptoms of an overlapping image. The image size was not measured on the console.

`method_only()` in the generator removes the v18 regions the method always skipped (TE calculations, TE-extend checks, the echo-train kernel, replaced by `goto v19_mat_window`). It comments out nine optional features the method rejects, returns `MAX_DIFF_ACQ` to its earlier 64 (PARAMLIST counts, `no_diff_acq` range and PPR arrays follow) and sets `MAX_CRUSHER_ETL` to 64. Guards immediately after the stop hub require `v19_on=1` and 1 ≤ `no_diff_acq` ≤ 64 before any table is read. An intermediate prototype without the `v19_on` guard ran the method shot without setup when `v19_on=0`; the guard and a regression test prevent that. Estimated images are 48.5 / 46.0 KB, 8.2 / 10.7 KB below v18.

Over 19 valid and 28 rejected protocols per method, RF timing, frames, multipliers and phases, ADC timing, played gradients, printed output and error meanings equal the v6 build; only the `v19_on` message and the SKIP_FIRST_ECHOES report line differ. Gradient list ids shift because CHESS/MTC setup lists are no longer compiled. Predicted warnings: three W008 from v18 code and one W003 (`pb_end`). The full event/Bloch validator ran on the method-only build (757 s); its control-identity section now confirms that `v19_on=0` is rejected before any event. Thirteen mapper tests pass, including an image budget 4 KB below v18. [Results](compiler_compatibility/method_only_results.json). Compilation and simulation remain to be confirmed.

