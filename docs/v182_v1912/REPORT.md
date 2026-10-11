# v1.82, ss-MGOT v1.912 and protocol-derived effective b

These are source-model candidates. Vendor compilation, console acceptance, actual synthesizer timing, RF phase and slice crosstalk remain scanner tests. No scanner qualification is claimed. The immutable v1.81 and v1.911 PPL/PPR files and experiment raw bytes are preserved. A subsequent user request authorizes committing and pushing all pending repository changes, including the earlier scanner data, analyses and presentations.

## Build and scope

`examples/build_v182_ppl.py` transforms hash-checked v1.81 bytes; `examples/build_v1912_ppl.py` transforms hash-checked v1.911 bytes. Both also generate the matching PPR. They use anchored replacements so a changed baseline fails rather than silently producing a different lineage.

The diffusion-DAC search, nominal b input, b=0 DAC handling, diffusion-180 crushers, and shipped RF widths are retained. v1.82 explicitly compiles out 3D and driven equilibrium to fit the constrained image; CHESS remains available. Driven equilibrium was already excluded from the DWI path. v1.912 retains its method-only scope and standard-orientation lock.

## Readout and minimum echo spacing

v1.82 retains its actual-readout calculation and approximately 1.9-ms readout floor. v1.912 replaces the fixed 13-ms and fixed-readout rules with constraints derived from RF/fused-gradient gaps, the read/phase gradient overlap, receiver flush and representable timer targets. It prints the minimum ESP when a lower value is rejected. A real timer range may still reject a larger ESP; no list of simulated ESP values is an acceptance rule.

The v1.912 exact-area geometry remains locked: 200-us ramps, 700-us phase tops, 1000-us crusher reference, 60-us RF delay, 1320-us imaging selector and 1328-us fused tops. The E142 crusher DAC lattice and E146 angles remain because changing them would change the integer exact-area construction or its orientation. Placement/free intervals vary with the actual readout.

| Dwell, 128 samples | v1.82 min ESP | v1.82 min TR | v1.912 min ESP | v1.912 min TR |
|---:|---:|---:|---:|---:|
| 50 us | 14 ms | 174 ms | 13 ms | 193 ms |
| 25 us | 11 ms | 151 ms | 10 ms | 167 ms |
| 20 us | 11 ms | 151 ms | 10 ms | 167 ms |
| 16 us | 10 ms | 144 ms | 10 ms | 166 ms |

These are centred single-slice, mode-0 source predictions. [single_slice_tr_recheck.json](validation/single_slice_tr_recheck.json) confirms every minimum TR and rejection one ms below it, for both modes 0 and 2. Mode 2 adds one ESP to each shot's minimum TR. Off-centre v1.912 also reserves 2.7 ms for per-width frequency setup. Other protocol changes can change the printed minimum. The combined validator's v1.82 TR search uses its inherited three-slice K seed and therefore reports 521/453/452/430 ms, rather than the single-slice values above.

## Multi-slice frequency and phase

v1.912 reuses the inherited slice/batch/dummy loops. It checks actual slice-offset arrays pairwise and enforces:

`separation >= thickness * ((max(slab_pml, tip_pml)/1000 + 1)/2 + 0.75)`.

Rounding is upward in console units. The default 1-mm slice, 3000-permille slab gives 1103 units at 400 units/mm, or 2.7575 mm. A request at 1102 units is rejected before acquisition. A narrower 1.5-times preparation slab is a future RF project; the formula already accommodates its width.

The 0.75-thickness transition margin comes from the quantized shipped pulse profiles: largest persistent 5% transition is 0.690 mm for prep90. It is a 5% response criterion, not a guarantee of 1% isolation or measured whole-sequence crosstalk. Pulse sample hashes, decoded-frame equivalence and the one-profile-per-pulse calculation are in [validation/rf_margin.md](validation/rf_margin.md).

Every v1.912 width selects its own frequency from its actual selection DAC: prep90/180, tip-up, re-excitation and train refocusing. v1.82 likewise uses its actual selected DAC. Console z preserves the inherited vendor sign convention; the physical-axis comparison uses physical z opposite console z. This sign convention needs confirmation with a phantom.

Both builds explicitly account for phase accumulated while the sub-MHz offset is active. Restoring the centre-frequency buffer is not treated as clearing oscillator phase. v1.82 anchors offset on/off and RF gates in one timer; v1.912 uses per-width accumulated offset spans and anchored centre restoration. The event mapper now records delivered frequency and phase histories without changing waveform arithmetic. The phase check integrates those histories at every RF centre and compares off-centre pulses with centred pulses using a common shot phase origin. The unobservable common shot phase is retained; CPMG phase relationships are checked.

## Navigator storage contract

`nav_on=0` is off and `nav_on=1` is the inherited per-volume navigator train. Mode 2 is a superset: the leading per-volume train remains and **every** shot has one appended echo after its `E=views_per_seg` imaging echoes. The appended RF uses the same train geometry and the last imaging flip. The centric centre stays at imaging echo 1.

For each diffusion volume, average and slice, the MRD view dimension contains:

1. One leading volume-navigator block of `E+1` rows. Its first E rows feed the existing amplitude envelope; its appended row is discarded by recon.
2. `N/E` imaging-shot blocks of `E+1` rows each. Each block contains E imaging rows followed by its one per-shot navigator row.

All outer volume/slice/average ordering follows the inherited MRD contract. `NO_VIEWS` in the **embedded protocol** is the total raw count R; `views_per_seg` remains E:

`R=(E+1)*(1+N/E)` and `N=(R/(E+1)-1)*E`.

For 128 imaging rows and ETL 8, mode 2 requires R=153. Mode 1 requires 136; mode 0 requires 128. The PPL validates R then locally reduces its loop/phase-table view count to `R/(E+1)*E`; the stored protocol remains R. Recon uses embedded `nav_on`, `NO_VIEWS` and `VIEWS_PER_SEGMENT`, verifies the actual MRD count, and never guesses from the adjacent PPR. v1.912 mode 2 currently requires centric PE order 1. Unknown navigator modes are errors.

The appended echo has net zero phase-encoding moment. The inherited positive and negative secondary ramp frames differ by about 1.92 us of normalized area. Mode 2 uses the same negative frame for both lobes, with the secondary P-matrix sign inverted after acquisition starts while the P waveform is zero. Thus each encoded line's prephaser and rewinder cancel sample for sample. Live S/R matrix components retain their scheduled values. Mode 2 also removes the old small accumulated imaging PE drift; modes 0/1 keep their old sampled waveforms. Final model residuals are at numerical precision. Dummy shots are disabled in the navigator tests so the leading unencoded volume train cannot hide an imaging-shot residual.

Navigator modes 0/1 are compared with the new phase/readout build before navigator-only changes. For v1.82 that controlled comparison has identical RF/ADC events and all S/P/R played segments in eight cost models over two actual shots. Register-write timestamps within a padded zero-P interval may differ while the played trajectory is unchanged. Comparison with the older v1.81 itself is reported separately: the phase-window conditions add 3.2 us per RF in the nominal manual model, so strict legacy RF/ADC timing identity is not claimed. That intentional phase-feature instruction cost is reflected in the new model-derived b values. v1.912 retains centred RF/ADC/gradient timing versus v1.911, with only an inactive secondary matrix-write timestamp difference. Off-centre carrier/phase behavior necessarily changes to implement the requested fix.

The validation-only [items 2–4 control](validation/v182_items2to4_control.ppl), its [16-case result](validation/v182_nav_identity.json) and [reproduction notes](validation/v182_nav_identity_notes.md) make that comparison reviewable. The control SHA-256 is `9c53507fd98073a522ee0f1827d9d95d4c82920a8bac30cfc044fac59eb56e36`. It is not a scanner upload candidate.

Recon fits magnitude-weighted unwrapped phase in each navigator's readout projection against the strongest-SNR shot. It applies the conjugate constant plus linear correction in hybrid x-ky. `--shot-nav-mode off|constant|constant+linear` selects the model; the default is constant+linear. SNR below 3 or coherence below 0.65 leaves that shot unchanged. JSON and `_shot_nav_phases.npy/.json` record fitted intercept, slope, quality and disposition per shot/slice/volume. Edge projection noise estimation can conservatively disable correction when the object fills the FOV. These quality thresholds need acquired mode-2 data.

## Effective-b reconstruction

The nominal `.bval/.bvec` arithmetic is retained. Recon additionally writes `_beff.bval`, `_bmatrix.txt` and JSON `EffectiveBValue`, `BMatrix`, `BMatrixEcho`, `BMatrixSource`, `BMatrixWarnings`, calibration status and model provenance. Matrix columns are bxx, byy, bzz, bxy, bxz, byz in logical read/phase/slice axes, s/mm²; off-diagonals are tensor entries without a factor of two.

The acquired embedded protocol selects the versioned repo PPL and all parameters. The full mapped gradient history from excitation to the selected echo includes diffusion, crushers, selection/rephasing and read/phase prephasers. Integration follows instantaneous RF sign flips and ss-MGOT longitudinal storage; the carrier/conjugate branch with the smaller echo endpoint follows the existing final-physics-grid convention. Centric PE uses echo 1; reverse-centric uses ETL and linear ordering ETL/2+1, represented by the first imaging shot with a warning about shot-dependent terms.

For acquired v1.91, source resolution uses the method-only v7 snapshot under `docs/v181_v1911/baseline_v7`, because the current scanner/1.91 file is a different combined source. Cache keys include PPL/protocol SHA-256, model revision and echo. Missing source, rejected protocol, invalid cache or model failure returns nominal matrices with `BMatrixSource="nominal-fallback"` and a warning instead of failing reconstruction.

Optional `--b-calibration PATH` JSON supports per-version gradient amplitude factors and an additive symmetric b-matrix, with `B'ij=si*sj*Bij+Aij`. Applied entries and calibration file hash are recorded. No empirical calibration is shipped: the test calibration has artificial factors solely to check mechanics. The known scanner z-axis discrepancy remains a measurement task.

## Validation evidence

The mapper cost models are flat 0/0.5/1/2-us statement costs and manual 0.8/0.9/1.0 plus the mixed 0.8+0.5-us model. They explore source timing sensitivity, not the vendor implementation.

The final [event_gates.json](validation/event_gates.json) passes. The 347-second full dry run retained stable PPL/PPR, control and validator hashes. Minimum and minimum-plus-one ESP cases are clean across all eight cost models; below-minimum cases print the correct bounds. Maximum RF phase errors relative to each shot's first RF are 0.207° for v1.82 and 1.298° for v1.912, including mode 2, against a 3° gate. Maximum echo midpoint errors are 15.8 and 9.25 µs respectively, against 25 µs. Single- and three-slice mode-2 runs produce nine ADCs per ETL-8 shot, with maximum appended-echo PE residuals of 5.73e-11 and 6.16e-13 cycles/m respectively. No targeted timer, list or premature matrix-use hazard remains. Fused boundary-area errors are at most 9.10e-14 of the D area; the 1103-unit spacing accepts and 1102 rejects with E148.

The original [full-run report](validation/event_gates_full_run.json) is preserved with its two timestamp-sensitive v1.912 nav0/nav1 identity flags. Its RF, ADC and all played gradients already match. A [targeted recheck](validation/v1912_identity_gate_recheck.json) confirms exact matrix values and a 0.8-µs register-write shift inside padded inactive intervals. The corrected validator gates physical events and matrix values, while retaining command timestamps as information. The [finalizer](validation/finalize_event_gates.py) combines that recheck with the unchanged full-run evidence and records both report hashes, the original failures and the corrected validator hash. It does not claim the full mapper was rerun under the corrected reporting code. This resolves only those two identity flags; it changes no scanner source or timing/phase tolerance. The v1.82 items 2–4 control passes all 16 nav0/1 comparisons.

The static audits pass on the final hashes: no added W007/W008 signatures, undefined jump targets, macro definitions or macro calls in slash comments; conditional bodies and forward jumps remain within the inherited limits. The relative image model is 2.6 bytes per AST node plus arrays and strings, with unknown target runtime overhead. It is not a vendor compilation guarantee.

| Candidate | Modeled image | Relative limit | Modeled headroom | Forward jumps |
|---|---:|---:|---:|---:|
| v1.82 | 56,590 B | 56,664 B | 74 B | 25 |
| v1.912 | 52,542 B | 52,568 B | 26 B | 18 |

v1.82 reclaims inactive 3D/DE branches and zero-valued 3D expressions in padded setup windows. v1.912 shortens four optional diffusion-report labels while retaining all printed argument values. The image budget remains extremely tight. Audit details are [static_v182.json](validation/static_v182.json) and [static_v1912.json](validation/static_v1912.json). Reviewable baseline diffs are [changes_v182.diff](validation/changes_v182.diff) and [changes_v1912.diff](validation/changes_v1912.diff).

Exact builder reproduction and original baseline raw-byte hashes pass in [build_hashes.json](validation/build_hashes.json). Git's line-ending normalization is handled separately from raw-byte identity.

| File | Final SHA-256 |
|---|---|
| v1.82 PPL | `7257c4b2cada0e293b973402c0b897f57a47be6e6c36a592c2b04fe34aad133e` |
| v1.82 PPR | `44474269a39ebaa8efed9526000413dd4f8372082f520e890e005ffa8fd4f84b` |
| v1.912 PPL | `07b202660258a5c6843ffb88c4b2bfe630261a36d4d64d5b7f02594839444423` |
| v1.912 PPR | `11aca86556f0cfa1c4b51f2b60615c79e320b14b37f460b7718c4c35d458f554` |

Archived A/C/B/D/E sorted complex k-space and reconstruction arrays remain bit-identical to the old mode-1 arithmetic; saved NIfTI differences are only float32 serialization rounding below 10^-6 relative. Reference echo-1 b traces and direction behaviour agree within 0.0016 s/mm² (required 0.5). Effective-b ADC fits from navigator echoes 2-8 give A 1.8535, C 1.8550, B 1.8450 and D 1.8608 times 10^-3 mm²/s: 0.86% full spread (required under 3%). The known b0 echo-1 defect is excluded from that fit and remains out of scope.

Synthetic phase errors injected into A-derived navigators and imaging lines recover complex k-space within 9.36e-8 relative (limit 2e-6). Synthetic MRDs for both new version labels exercise automatic storage parsing and full reconstruction. Noise-only navigators leave images unchanged and flag every shot; off/constant modes, missing flag, unknown flag and calibration/fallback paths are checked. Detailed measurements and output sidecars are in [recon_checks/README.md](recon_checks/README.md) and [recon_checks/results.json](recon_checks/results.json).

The actual final new-version b models, including mode-2 storage/waveform selection, PE7 echo 5 for v1.82, and three-slice v1.912, are in [new_version_effective_b.json](recon_checks/new_version_effective_b.json). Mode 2 models its actual leading train and first imaging shot rather than substituting a mode-0 waveform. Independent analytic tests confirm persistent phase integration and separate coherent MHz receive-bank handling; small recon tests cover ETL 1 and corrupted-cache/hazard fallbacks.

The single fresh-context [independent review](INDEPENDENT_REVIEW.md) checked the frozen hashes, compiler rules, 96 multi-slice mode-2 shots across eight costs, per-width phase, minimum rejection and fused areas. It established no high- or medium-severity defect. Its low-risk findings are dispositioned as follows:

- **Compiler image headroom:** accepted as an explicitly unverified model risk; require actual PPLC/Forth compilation of these exact bytes before acquisition. Any source edit requires a size recheck.
- **Hardware phase delivery and receiver behavior:** accepted within the source-model scope; require the planned complex phantom phase checks before in-vivo use. A common shot phase in the RF comparison does not measure acquired absolute phase.
- **Console position units and RF isolation:** retain the repository's 400-units/mm convention and measured 5% pulse-margin scope; confirm actual slice positions and crosstalk on the console, including any non-default thickness.

No second independent review cycle was requested or performed. The shipped PPL/PPR bytes remain the bytes reviewed. A separately probed CHESS-on/use-PDD-on, flat-2-us cost-model corner has a 2.4-us factory CHESS timer miss in both v1.81 and v1.82; it is inherited and outside the clean targeted DWI runs. CHESS remains supported, but the model does not qualify every optional legacy combination.

Reproduction commands, from the repository root:

```text
python examples/build_v182_ppl.py
python examples/build_v1912_ppl.py
python examples/validate_v182_v1912.py
python examples/test_v182_v1912_recon.py
python examples/v182_v1912_rf_margin.py
python -m unittest discover -s tests -p test_ppl_phase.py -v
```

See [PRACTICAL_SUMMARY.md](PRACTICAL_SUMMARY.md), [ERROR_CODES.md](ERROR_CODES.md) and the prioritised [SCANNER_TEST_PLAN.md](SCANNER_TEST_PLAN.md) before console testing. The b0 defect, diffusion-180 crusher changes, narrower RF widths, oblique v1.912 orientations, 3D and ky navigator correction remain outside this work.
