# v191 (ss-MGOT) and v192 (Alsop) diffusion-prepared FSE

Two new MR Solutions PPL sequences were built from the actual v18 source; v18 is unchanged (SHA-256 `3b420376…598db2`).
- **v191** implements Gibbons' ss-MGOT mechanism.
- **v192** implements Alsop's mechanism.

## Status

| Stage | v191 ss-MGOT | v192 Alsop |
|---|---|---|
| Implemented in PPL source | **Yes** | **Yes** |
| Compiled | Combined v6 compiled but overflowed the 64K image in pplsim. **Method-only v7** (no v18 control path) awaits compile/simulation. | **Same** |
| Simulated | **Yes, from the actual PPL** through a source-level event mapper and Bloch simulator. Timing is a nominal estimate. | **Yes**, same |
| Reviewed | **Yes.** Independent PPL review rounds 1–4 and the compiler-compatibility review leave no open blocking/major source item. Physics review and its follow-up distinguish the earlier findings from the revised validation. | **Yes**, same |
| Verified on scanner | **No.** Nothing deployed. | **No** |

Final files reviewed (SHA-256):

| File | SHA-256 |
|---|---|
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl` | `cc452f0f8bd14e1934f0dcfcaf614ddd652ffe9546ea283b978e2ea6e75674b6` |
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppr` | `faa77a11c2da4c5fe9876d6a842b9bc3025c66ddc09eaa4e8270dec9350faf0c` |
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.92.ppl` | `f2ce7ccbd70fbfdb09fe2da925356d61fee2e6d5a5012eeaffa87888766616b8` |
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.92.ppr` | `678f2af5bb2fa205c2b7cb9402879d9ce1e98ed8e2c5fa4264c318b3e6898fbf` |
| `scanner/rf/v19_*.seq` (six per-pulse libraries) | see [rf_install_calibration.md](rf_install_calibration.md) |
| `examples/build_v19_ppl.py` (generator; reproduces all four byte-for-byte) | `7fdc1c29f16afd0c8ce73f2b1cf7afd93d36e9f54ad4fe69d7565b79295b52eb` |

Further reading: [implementation_report.md](implementation_report.md) for design, departures and phases; [rf_install_calibration.md](rf_install_calibration.md) for RF installation and calibration; [upload_checklist.md](upload_checklist.md) for deployment steps.

**Console compilation follow-up (2026-10-06).** The user's first compile attempts failed in `cpp`: function-macro names inside added `//` comments were expanded, and `V19_COMP` exceeded its argument-expansion buffer. The generator now expands every function-like V19 helper into ordinary statements, removes comments from its additions, and splits added printed-message literals into at most 48 source characters. This is a conservative bound, not a measured vendor string limit. The original v18 source and both PPRs are unchanged. At that stage, five regression checks included equality of fully expanded computational tokens with the previous validated versions, excluding diagnostic printing. A successful console recompile is still unverified.

[final_manifest.json](final_manifest.json) records the complete SHA-256 inventory of final source, validation inputs, results and review reports.

Both sources use the requested `g:\J_Figger\seqlib\v19_research_rf.seq` location. The full validator finished on the compiler-corrected versions before this one-line path change; [rf_path_event_identity.json](compiler_compatibility/rf_path_event_identity.json) records identical RF, ADC, gradient, matrix and timing histories for the preceding files over two shots, using the same library contents. Its source hashes link the completed validation to the preceding sources. The scanner's G-drive file presence and successful recompilation remain unconfirmed.

**First far scratch trial (superseded).** Both sources reached PPLC v7 but failed with E106. The first trial removed 167 / 128 setup conversion calls by using signed implicit widening, with an explicit `0L+` where necessary to preserve intermediate widths. It rewrites the three signed-minimum comparisons to avoid W010. No timed RF, gradient or ADC source changed; the PPRs, RF library and v18 remain unchanged. Six mapper tests pass, including event and setup-value equality against the preceding files for four protocol cases per method. See [scratch_reduction_results.json](compiler_compatibility/scratch_reduction_results.json). This is a source-tested reduction; E106 resolution remains unconfirmed until console compilation. The inherited v192 W008 frequency conversion is unchanged. The full event/Bloch validator completed on those preceding source hashes in 695.13 seconds: control identity holds, all 19 rejection cases per method have zero RF/ADC, and the declared convergence checks pass. [Independent scratch review](review/ppl_review_scratch_reduction.md) confirms expression widths and the unchanged timed code.

**Second E106 trial: compact resources.** The user reported the same E106 locations after the first trial, while W010 disappeared. The current candidate replaces terminating diagnostic prints with a shared error-code handler: preprocessed print calls fall from227/215 to54 in each method and quoted literal contents decrease by6782/6341 source characters (not a measured allocation). Stopping conditions and destinations remain intact, but numeric values previously embedded in fatal messages are omitted. Code meanings are included as `v19_error_codes.txt` in [v19_compact_fix_v2.zip](compiler_compatibility/v19_compact_fix_v2.zip).

The internal multiplier array aliases the existing native crusher workspace only in method mode, after the immutable schedule gate requires0; all subsequent normal crusher-array reads require a nonzero schedule. Method-off never overwrites it. This saves126 native bytes net after adding the error-code int. Host-loaded input arrays and all table capacities remain intact. Eight mapper tests pass, including normal control with schedules0/1/2 and method event/setup equivalence. [Compaction evidence](compiler_compatibility/compact_resource_results.json) and [independent review](review/ppl_review_compact_resources.md) distinguish this candidate from prior files. The full validator completed in677.22seconds with control identity, all38 rejection checks, and convergence passing. Its exact inputs precede the final restoration of the successful Duration report. [validator_report_event_identity.json](compiler_compatibility/validator_report_event_identity.json) records identical RF/gradient/ADC/matrix histories over two shots in seven cases per method between those inputs and the final files. The original validation hashes remain intact; E106 clearance remains unverified until console compilation.

**Third E106 trial: forward label references (cleared E106).** The compact trial still failed E106 at the same statements. In all six failing compiles, the error falls at exactly the 147th forward `goto` of the preprocessed stream, while string, token and conversion counts differ. v18 compiles with 145. PPLC holds a far-scratch record per jump to a not-yet-defined label, and v19's error guards jumping forward to `end` exhausted it. `end`/`v19_fail` now label a hub right after the first statement, forwarding once to the unchanged shared exit (`v19_exit`), so all later jumps, including vendor-macro `goto end`, are backward. Forward gotos fall from 215/202 to 22. Events, outputs and error codes are identical to the v2 files over 10 cases per method; nine mapper tests pass. Upload [v19_label_fix_v3.zip](compiler_compatibility/v19_label_fix_v3.zip); see [forward_label_results.json](compiler_compatibility/forward_label_results.json). Console compilation remains to be confirmed.

**Fourth trial: warning limit (PPL compiled).** The label hub cleared E106. Both methods then compiled to about line 4900 and aborted with "Too many errors" after 20 messages. PPLC counts warnings toward that limit. v18 contributes 11 W007/W008 of its own. The method shot passed long tick expressions to `waittimer(int)` 46 / 37 times, each a W008. A static check reproduces all 20 console messages per method. Each long argument is now assigned to an int once in setup after validation, which keeps the same low 16 bits without a warning, and constants are int literals. The predicted W007/W008 set now equals v18's 11; no W002/W003/W005/W006 candidates remain. Events, outputs, error codes and overrun flags are identical to v3 over 14 cases per method; ten mapper tests pass. Upload [v19_warning_fix_v4.zip](compiler_compatibility/v19_warning_fix_v4.zip); see [warning_limit_results.json](compiler_compatibility/warning_limit_results.json).

**Fifth trial: .fth branch range (compiled).** Both PPLs compiled with exactly the 11 predicted warnings. The .fth stage then reported "error branch is out of range" once per method. The method setup was a single `if (v19_on==1) { … }` body ten times larger than any conditional body in v18. The reported .fth lines fall at that block's end in both methods. `if`/`until` compile to a short conditional branch, while v18 already runs with `goto` spans far larger than this block. The setup now begins `if (v19_on!=1) goto v19_setup_done;` and ends at that label, with no setup statement changed. The largest conditional body is now v18-sized. Events and outputs are identical to v4; eleven mapper tests pass. Upload [v19_branch_fix_v5.zip](compiler_compatibility/v19_branch_fix_v5.zip); see [branch_range_results.json](compiler_compatibility/branch_range_results.json).

**Sixth trial: simulator and RF viewer.** v5 compiled and the .fth stage passed. The simulator then reported "step math opcodes not supported" for both methods. The RTX2000 uses step instructions for multiply/divide, and every math word in the .fth is also used by v18-inherited code, so a v18 simulator run is needed to tell whether this is v19-specific. Separately, the combined RF library displayed blank: its frames had no WavEd expressions, while every vendor frame has one. Each pulse is now its own library stored like the vendor `opt90_as.seq` (`N,user("x.txt");` with the samples embedded); the encoder reproduces `opt90_as.seq` byte for byte, and the sample records are unchanged. The compiled v5 RF address table placed the v19 frames contiguously with correct dwell and no overlap. Upload [v19_rf_fix_v6.zip](compiler_compatibility/v19_rf_fix_v6.zip); see [rf_viewer_results.json](compiler_compatibility/rf_viewer_results.json).

**Seventh trial: method-only PPLs (current).** pplsim showed corrupted parameters (v1.91 saw phase_cycle=2) and undecodable instructions, while the v6 .fth files contain no word or opcode absent from v18's. v18's history documents a hard 64K program image, and the combined v18+method programs were an estimated 8.6–11.1 KB larger than v18. The v19 PPLs are now **method-only**: the v18 regions the method always skipped (TE calculations, TE-extend checks, echo-train kernel) are removed; nine rejected features are compiled out; diffusion tables return to 64 rows (with PARAMLIST and PPR) and the crusher table to 64 entries. `v19_on` must be 1 and `no_diff_acq` 1..64, checked before any table is read. Estimated images fall to 48.5 / 46.0 KB, 8.2 / 10.7 KB below v18. Over 47 protocols per method, events, output and error meanings equal v6; controls now run on the unchanged v18 PPL. Upload [v19_method_only_v7.zip](compiler_compatibility/v19_method_only_v7.zip) (includes new PPRs and error codes); see [method_only_results.json](compiler_compatibility/method_only_results.json).

## How the validation numbers were obtained (plain English)

There was no MR Solutions compiler, simulator or scanner available, so I built a stand-in and ran the real sequence files through it.

1. **Run the actual `.ppl` file.** A Python program reads the real sequence source, including MR Solutions' include files and macros, together with the real protocol (`.ppr`). It executes it statement by statement, using the scanner's 16-bit and 32-bit integer rules.
2. **Record what the hardware would do.** Each hardware command ("start gradient list", "play RF frame", "open receiver", "wait until timer = X") is logged with its time, using the real ramp and RF waveforms from the binary libraries. The result is a timeline of every RF pulse, gradient and acquisition window, called the "event ledger".
3. **Charge time for the code itself.** The manual's per-operation costs are used, scaled by 0.8 so that v18's own measured window usages (written in its comments) are reproduced and v18 runs cleanly, which it must, since it produced real images. Everything was re-checked with slower and faster cost assumptions.
4. **Measure the ledger.** From the ledger the scripts read:
   - RF and echo times;
   - gradient areas between events, i.e. how much each signal pathway is dephased;
   - timing or hardware conflicts;
   - whether bad protocols are refused before any pulse plays;
   - whether `v19_on = 0` reproduces v18 exactly.
5. **Simulate the magnetization.** The logged RF and gradients drive a Bloch simulation of 3000 spins across the slice (×32 across an in-plane voxel for the ss-MGOT spoiler). It reports the magnetization at each landmark and the summed slice signal at the middle of each acquisition, as a fraction of a perfectly refocused full slice. Runs cover starting phase 0/45/90°, RF strength 100/80% and off-resonance −128/0/+128 Hz.
6. **Check the simulator.** It was re-run with twice the spins and with finer RF steps, and compared against a general-purpose ODE solver.
7. **Diffusion weighting.** Both recalled branches are integrated, including the conjugate branch at the elimination or re-excitation centre. For each acquisition the branch whose final wave-vector is closest to zero is used for the b-tensor. The output retains both candidates so the choice is inspectable.
8. **The Gibbons comparison is separate.** It uses idealized sequences at the paper's geometry with the same RF pulses, because the paper's exact pulses and flip tables are not published.

**Not established:**
- real console instruction timing;
- hardware delays: gradient lag, RF and receiver latency;
- actual RF calibration;
- image quality or PSF.

Full description: [implementation_report.md § How the validation numbers are produced](implementation_report.md#how-the-validation-numbers-are-produced-plain-english).

## Results: scanner adaptations

All results below come from the event ledger, 1-mm slice, eight-echo test1e-based protocol.

**Control path.** With `v19_on = 0`, v191 and v192 produce exactly v18's RF, ADC, gradient and matrix events after `sync()` over two shots. This holds for the original schedule and for increasing, decreasing and alternating crushers. ([control_identity.json](event_validation/control_identity.json))

**Timing.** RF centres, in µs from the preparation excitation:

| | Prep 180° | Method RF | Re-excitation | First imaging RF | ESP |
|---|---|---|---|---|---|
| v192 | 27000 | 54000 elimination | — | 61000 | 14000 |
| v191 | 27000 | 54000 tip-up | 59716 | 66716 | 14000 |

- Under the calibrated manual-cost model the preparation, method and first imaging centres differ from design by a few µs. ESP is about 13996.9 µs, so a roughly 3-µs discrepancy accumulates per later echo. Under a 0.5 µs/statement model the centres are exact.
- There are no timer overruns, ignored list starts or premature matrix uses in the tested flat 0–2 µs/statement models, manual expression costs ×0.8–1.0, or ×0.8 plus 0.5 µs/statement. v18 itself overruns at a flat 1 µs/statement. ([timing_summary.json](event_validation/timing_summary.json), [hazards.json](event_validation/hazards.json), timing tables `timing_*.csv`, diagrams `diagram_*.png`)

The raw mapper log retains inherited diagnostics: one 40000-to-signed-int narrowing and sixteen writes to a selected matrix per method, also present in the v18 control. These are not counted as clean hardware validation. The reconstructed waveforms show zero premature matrix-use issues, ignored list starts or timer overruns on the method paths.

**Rejections.** All 19 unsupported or infeasible settings tested are refused before any RF or ADC event. This includes four dephasing cycles, unsafe first-crusher values, the wrong polarity and crusher settings outside the validated range. ([rejection_tests.json](event_validation/rejection_tests.json))

**Gradient moments** (physical frame, gradients lagging RF by `rfdelay` as v18 intends; [moments.json](event_validation/moments.json)):
- Every ADC recalls one dephasing branch: k/D = 1.000 ± 0.002.
- Restoration returns to ≤ 0.002·D before the next refocusing RF.
- The elimination/tip-up input phase error is < 0.002 cycle across the slice.
- The read echo is at the ADC centre (k ≈ 1 cycle/m).
- Phase-encode rewinding is exact.

**Bloch, slice-coherent |S|** (fraction of full-slice signal; [bloch_results.json](event_validation/bloch_results.json), [echo_amplitudes.png](event_validation/echo_amplitudes.png), landmark profiles `profiles_*.png/npz`):

| Echo 1 / 2 / 8 | phase 0° | 45° | 90° |
|---|---|---|---|
| v191 ss-MGOT | 0.387 / 0.404 / 0.334 | 0.387 / 0.403 / 0.334 | 0.386 / 0.403 / 0.332 |
| v192 Alsop | 0.303 / 0.275 / 0.257 | 0.293 / 0.284 / 0.244 | 0.289 / 0.286 / 0.237 |
| v18 control (original crushers) | 0.845 / 0.751 / 0.782 | 0.844 / 0.726 / 0.577 | 0.844 / 0.705 / 0.233 |

- **ss-MGOT** is phase-invariant (±0.003) and within ~3% across ±128 Hz.
- **Alsop** has a few-percent phase dependence and is off-resonance sensitive: at nominal B1, across all three phases and −128 / 0 / +128 Hz, echo 1 spans **0.21–0.38**. The earlier 0.37 / 0.29 / 0.26 triplet covered only phase 45°.
- **v18** avoids the methods' half-signal projection cost but loses phase robustness: at 90° and 80% B1, echo 4 falls to 0.03.
- **Both methods** have an ideal 50% projection/storage cost. Finite RF profiles cause further losses; their amplitudes are not expected to be exactly half of v18's because the pulses and protocol differ.
- **80% B1, zero off-resonance:** across all eight echoes and three initial phases, ss-MGOT spans ~0.22–0.27 and Alsop ~0.17–0.31.
- **Muscle relaxation** (T1/T2 1300/32 ms) shrinks all signals strongly at this long TE. Echo 1 is about 0.047 (v191), 0.036–0.043 (v192) and 0.157 (v18).

**Simulator checks** ([convergence.json](event_validation/convergence.json)):
- z 3000 vs 6000 spins differ by ≤ 1e-6;
- RF substeps 1 vs 4 differ by ≤ 1e-15;
- y 32 vs 64 differ by 1e-4;
- the independent ODE agrees within 8e-10.

**Off-resonance echo position.** With an intravoxel ±150 Hz spread, the ADC1 echo peak lies 95 µs (v191) and 185 µs (v192) after the middle sample. The middle sample keeps 99.8% and 99.4% of the peak. This comes from the selective pulses' isodelays not being folded into the RF timing (see open issues).

**Effective diffusion weighting** at ADC1, nominal b = 1000 ([btensor.json](event_validation/btensor.json)):
- v191/v192: b_read ≈ 996 and b_slice ≈ 19 (crushers, D and recall), trace ≈ 1015, rising to **1096/1097** by echo 8. Even echoes now use the conjugate recalled branch; both candidate endpoints are saved.
- v18 control: b_read ≈ 1171, because the read prephaser sits between its diffusion lobes and adds cross-terms. Trace ≈ 1175.

At nominal 6000, ADC1 trace is ≈ 5982 for the methods and ≈ 6394 for v18. **The nominal b-values are therefore not equivalent between v18 and the new methods.**

**Controls compared** (same mapper and simulator):

| Control | Source settings |
|---|---|
| original | test1e |
| increasing | test2b settings (schedule 1, +40%) |
| decreasing | test5 settings (schedule 4) |
| alternating | schedule 2 on test1e: sign alternation with magnitude kept, first diffusion crusher separate; never acquired, simulation only |

Differences from v18:
- **TE:** v18's first echo is 54 ms. v192's first echo is 68 ms and v191's is 73.7 ms, both after a 54 ms preparation echo.
- **RF train:** v18 uses a 1332 µs 3-lobe sinc at 166.5°. The methods use a 1.2 ms Hamming 180° frame at 142→60°.
- **Slice profile:** different research SLR / Hamming pulses.
- **Train crusher:** 3× larger in the methods, required to spoil RF FIDs.

No image-quality or PSF claim is made from echo amplitudes.

## Results: Gibbons reference benchmark

This benchmark is separate from the scanner adaptation and uses idealized timing at the paper's geometry. Settings: 30 mm, **9000 z points for two cycles and 18000 for four**, 6/18/10 mm, research RF, ESP 4.2 ms, 76 echoes. The published 3000-point grid aliases late pathways with these research crushers. Grid refinement is checked against 18000/27000 points. ([reference_benchmark/](reference_benchmark/), `results.json`, `fig3_S2_endpoint_profiles.png`, `fig4_echo_trains.png`)

The 32 in-plane spoiler positions have only four distinct phases after the complete eight-cycle spoiler; each phase occurs eight times. Four equally weighted states therefore reproduce their average exactly, while keeping the same physical position for the displayed local spin. The code checks this against the full 32-position simulation. It never manually deletes transverse magnetization.

The completed grid checks differ by at most **3.26e-6 across all 76 echoes**: two cycles at phase 45° without relaxation, and four cycles at phase 45° with muscle relaxation. The full 32-position versus four-group check differs by **2.51e-17** in complex signal over eight echoes. These checks cover the stated cases, not every B0/B1/phase combination. [Results](reference_benchmark/results.json), [independent confirmation](review/physics_followup.md).

- **Fig 3/S2 analogue** (45°, 2 cycles): landmark profiles A, B, tip-up, spoiler, re-excitation, endpoint before the leading crusher, pre-RF after the crusher, and ADC1/2/76.
- **Fig 4 analogue** (T1/T2 1300/32 ms, 2 and 4 cycles):
  - The revised comparison uses C1 = 2550 cycles/m (two cycles) or 5100 cycles/m (four cycles). The old 1.5·C value exaggerated Alsop's phase dependence through a stray-pathway coincidence.
  - For two cycles, Alsop echo 2 is 0.106/0.115/0.119 at phases 0/45/90°. The maximum phase spread across 76 echoes is **0.02325 for Alsop and 0.002537 for ss-MGOT**. For four cycles it is **0.003097 and 0.000300**, respectively. These are differences in normalized signal magnitude, not percentages relative to each echo.
  - Absolute values are not comparable to the paper: different RF, flip schedules and preparation TE. The 1.2-ms benchmark elimination has a broader transition than the preparation SLR and **biases the comparison against Alsop**.
  - The assumed 30-ms preparation TE changes the common transverse amplitude scale through T2 decay; it does not establish a matched absolute signal for the paper. For example, 15 ms extra preparation time at T2 = 32 ms multiplies the desired transverse signal by about 0.63.
- **S1 (ss-MGOT vs nCPMG PSF) is not reproduced.** It needs double phase encoding and reconstruction. A signal-only illustration shows an uncorrected fixed-160° train collapsing at 90° phase (echo 3: 0.001 vs 0.185 at 0°).

## Findings that changed the design

1. **Crusher size (event-driven Bloch).** With the old protocol's train crusher C ≈ D, the FID from one imaging RF, refocused by the next, has a small residual **|D−C| ≈ 551 cycles/m**. The earlier C+D label applied to the first draft's opposite D polarity and was incorrect for the final design. Alsop echo 1 varied 0.07–0.51 with phase in that exploratory configuration. The PPRs now use `crush_amp` −8223 (3×).
2. **Preparation-crusher coincidences (P1/P2).** Simple exclusions around C and C+D missed other families. The 3×3 scanner scan found phase spread up to 0.070 for Alsop, versus 0.020 at the shipped point, and up to 0.006 for ss-MGOT. At the narrow window's four corners, the maxima are **0.0212 (Alsop) and 0.0038 (ss-MGOT)**. Method mode now requires negative crusher polarity, two dephasing cycles, |C|/|D| = 3.83 ± 0.02 and |C1|/|D| = 2.55 ± 0.02. The comparisons use rounded integer areas. Other settings stop with a request to re-validate using `examples/v19_validate_events.py`. [Coarse scan](event_validation/crusher_geometry_scan.json), [boundary scan](event_validation/crusher_geometry_boundary_scan.json) and [PPL confirmation](review/ppl_review_round4.md) retain the evidence.
3. **PPL review round 1:**
   - **B1:** the 300 µs post-ADC calculation window would have added 5 ms to every echo; it now has v18's 8997-tick budget.
   - **M1:** `gp_sl_var` was never set on the method path.
   - **M2:** some waits ran past the 5 ms timer period.
   - **M3:** `v19_on` could be toggled live without setup; it is now latched.
   - **Minors:** several, all fixed.
   - **Round 2 N1:** an unbounded spoiler window, fixed.

   The mapper now includes the manual's operator costs, so it reproduces B1 before the fix and its absence after.
4. **v18 fragilities, reported rather than changed:**
   - v18's block-C window (18.5 µs) overruns by 5 ms at 1 µs/statement.
   - With zero instruction cost, its train `SetList` hits a still-active channel.
   - Its train RF spacing depends on the undocumented `acqpad()` filter flush.

## Open issues (not resolved here)

- **No vendor compile or console trace.** The constants V19_ANCHOR (0.5 µs), V19_INIT_COST (7.6 µs), the `delay32` overhead and the RF start latency (~3 µs) are estimates.
- **RF calibration.** It is inferred from `rfcal` (linear model); every frame needs a console flip-angle check. Power/SAR and physical gradient limits are not supplied.
- **Off-resonance isodelay alignment** (v192 185 µs, v191 95 µs). Recommended refinement: shift the train reference by the measured isodelay offsets. Alsop's ±128 Hz sensitivity is reported, not corrected.
- **RF fidelity.**
  - The tip-up is water-only and spatial, not Gibbons' spectral-spatial pulse, so there is no fat suppression.
  - Imaging and re-excitation use Hamming sincs with broad transitions.
  - The Busse schedule is unpublished; approximations are labelled.
- **Method-on restrictions.**
  - Only the shipped two-cycle, negative-polarity crusher geometry is supported. The small ratio windows allow integer rounding around it; they are not permission to retune the protocol without validation.
  - Single centred slice only: the transmit frequency is fixed for all pulse widths.
  - No 3D, flow compensation, Dixon, DE, presat, CHESS, CEST, gating or crusher schedules.
- **The `#use pf19` library line is needed even for `v19_on = 0`.**

## Reproduce

```bash
python examples/build_v19_ppl.py
```
```bash
python examples/v19_validate_events.py
```
```bash
python examples/v19_reference_benchmark.py
```
```bash
python -m unittest discover -s tests -p test_v19_ppl_mapper.py -v
```

## Agents used in this session

| Role | Who | Outcome |
|---|---|---|
| Coordinator and writer of both PPLs, generator, mapper, simulations and docs | Main session | The writers in the earlier session's plan were replaced by one writer. Both methods share one generator to avoid inconsistency. |
| Independent PPL reviewer | Separate agents, four design rounds plus compiler follow-up | [review/ppl_review_round1.md](review/ppl_review_round1.md), [review/ppl_review_round2.md](review/ppl_review_round2.md) (includes round 3), [review/ppl_review_round4.md](review/ppl_review_round4.md), and [compiler-compatibility review](review/ppl_review_compiler_compatibility.md). The reports retain their reviewed hashes. The scratch reduction has a separate review; E106 remains a console compilation issue until a successful retry. |
| Independent physics/simulation reviewer | Separate agent | [review/physics_review_final.md](review/physics_review_final.md) records the earlier findings; [review/physics_followup.md](review/physics_followup.md) confirms the final branch, landmark, crusher and convergence corrections. No open blocking or major finding within the declared numerical scope; compilation and hardware remain unverified. |

The writer did not approve its own changes: every fix was re-reviewed by the PPL reviewer. Earlier records ([ppl_review.md](ppl_review.md), [physics_review.md](physics_review.md), [reference_rf.md](reference_rf.md)) document the prior session's work and are retained.
