# Execution details and reproducible outputs

4 October 2026. This appendix records the **executed** search; the design note also contains proposals that were not all run. No scanner or core simulation code was edited by the investigation. The shared-tree v1.7 timer-guard revision is an unrelated preserved change.

## Budget, scope and selection

The main runner completed **851 model evaluations**, containing **6,760 echo records**: 377 finite-duration RF Bloch evaluations and 474 exact instantaneous-RF pathway evaluations. The 41 configurations have four finite-RF screen conditions each. Forty configurations have eight exact screen conditions each; the centered permutation's exact results use the separately labeled timing-transfer stage. There are 1,364 sample-center tensor records across the generated sequences.

| Executed stage | Finite-RF evaluations | Exact-pathway evaluations | Purpose |
|---|---:|---:|---|
| Screen | 164 | 320 | Four static RF/phase points; exact static and model-water decomposition |
| Initial shortlist robustness | 120 | 90 | Five candidates, 24 total-signal conditions each; exact selected water panel |
| Initial shortlist heldout | 35 | 30 | Seven conditions each; exact omitted for ETL12 |
| Supplemental corrected-permutation robustness | 24 | 18 | Full unchanged robustness panel, explicit timing-transfer label |
| Supplemental corrected-permutation heldout | 7 | 6 | Full unchanged heldout panel, explicit timing-transfer label |
| Limited timing transfer | 2 | 10 | Two initial transfer observations and static/water decompositions |
| Dense sampling | 15 | 0 | 16,000 spins, seed2, including calibrated near-null controls |
| RF time-step sensitivity | 10 | 0 | 2 µs versus matched 10-µs cases |

Observed main-run cache creation span was **18.56 minutes**. Sum of cached per-case elapsed times was **36.16 minutes** under parallel execution; this is wall time per evaluation, not measured CPU-hours. Independent auditing, reproduction and imaging are additional work: 528 acquired-signal closure echo-condition records, a bounded prior reproduction, and 20 actual phantom acquisitions with convergence checks. The overall research turn also includes implementation, literature review and reporting.

Five candidates were frozen before the initial robustness/heldout panels. The centered permutation followed as a timing-correction supplement after two transfer points and the initial heldout run; its amplitudes were not tuned. [Selection metadata](../data/combined_factor_selection.json) preserves that chronology and posterior angle-screen exclusion notes. Selection considered signal preservation, desired-primary amplitude, non-primary share, hardware/diffusion cost and transferability. This was a bounded schedule screen, not exhaustive optimization, a statistical clinical design or a proven global optimum. Fixed/variable low angles were not advanced under the primary-preserving crusher objective; this does not disqualify methods designed to preserve useful stimulated signal with appropriate reconstruction.

One Windows CSV-sharing failure occurred after a successful simulation. Its cached point was recovered when all tables were rebuilt; no model evaluation remains missing. The [error record](../data/combined_factor_errors.json) retains the resolved infrastructure event. The separate phantom spatial-convergence failure remains unresolved and is reported, rather than being removed from the evidence.

## Exact factors and matched controls

The [41-row test table](../data/combined_summary_screen_tests.csv) provides all requested result columns: Test ID, exact changes, conditions, primary, total, stimulated contribution, non-primary share, robustness, added diffusion weighting, timing/hardware cost and decision. Numeric per-echo files retain the complex values behind its compact strings. The [configuration file](../params/combined_factor_configs.json) gives exact overrides and formula-generated tables.

| Test family | Changes, motivation and controls | Matching and interpretation |
|---|---|---|
| Eight factorial controls | Constant/increasing amplitudes × constant/alternating sign × original/centered timing; isolates recurrences, interference and centering | RF, first crusher, TE/ESP/TR and pair symmetry fixed; progression changes peak/energy/b |
| Increasing/decreasing/permuted | Increasing tail `[1,1.4,1.8,2.2,2.6,3,3.4]`, reversed tail, or `[1,3.4,1.4,3,1.8,2.6,2.2]`; changes order of the same ordinary strengths | Same peak and ordinary crusher energy; b tensors differ; first multiplier remains1 |
| Two-level high/low | `[1,3.4,1,3.4,1,3.4,1,3.4]`, with constant or alternating sign | Peak matched to increasing; energy differs; literal high/low repetition was not the useful permuted ordering |
| Modulated/nonlinear | Modulated tail `(1+2.4*t**1.5)` multiplied by alternating1/.8; quadratic `1+2.4*t**2`; geometric `3.4**t`, t=0…1 over7 entries | Peak3.4; energy differs; all first entries1; screen did not justify broad advancement |
| Bounded irregular | NumPy seed20261004, seven tail draws uniform1…3.4, with full-list entry4 set3.4 | Saved exact generated values; no adaptive retuning or global optimization claim |
| Energy matches | Scale only ordinary high/low or irregular amplitudes using a bounded root search for increasing's full played integral G² | Relative energy residuals +5.97×10⁻⁵ and −9.28×10⁻⁶; peaks3.00113 and3.42633 differ from3.4; b not matched |
| Gentler increasing | Tail1…2.2 in .2 steps, centered, also with polarity alternation | Lower gradient/b cost; not energy matched; water-primary retention higher, suppression weaker |
| RF phase combinations | Offset tables `[0,180]*4` and `[0,90]*4` alone, with increasing/centering and increasing/alternating/centering | Relative to existing transmitter phases; receiver phases unchanged; component probes, incomplete published imaging methods |
| RF angle combinations | Fixed160°, exploratory `[180,170,160,150,145,150,160,170]`, and conservative `[180,180,175,170,165,160,155,150]`, with matched crusher-only and RF-only controls | RF amplitude changed in isolated sequence blocks; duration/center held fixed; waveform shape preserved; RF energy changes; storage can be intentional useful signal |
| Duration/moment combinations | Ordinary flat duration1000→500µs and ordinary amplitude5482→9398DAC; first1000µs/DAC2754 pair unchanged; test alone and with increasing-alternating-centered | Area approximately matched using G×(flat+200µs ramp); DAC rounding retained; TE/ESP/TR fixed; peak/slew increase and b changes |

The core interaction is computed at identical conditions and echo as `Y_AB−Y_A−Y_B+Y_0`, for complex real/imaginary signal, magnitude, primary/stimulated magnitude and L1 share. The three-factor contrast is `Y111−Y110−Y101−Y011+Y100+Y010+Y001−Y000`. All eight vertices are present. CSV values are absolute contrasts; a contrast in magnitude is not a linear complex-vector decomposition. Interactions depend on RF strength and phase error, so one favorable cell cannot establish universal synergy.

No comparison is described as simultaneously peak-, energy- and b-tensor-matched. Equal gradient energy does not imply equal diffusion exposure. A scalar diffusion-amplitude adjustment could match one trace but generally not the directional tensor. Full hardware/tensor tables include every echo, all nine matrix elements, q, sequence timing and energy proxies; paired tables add tensor-element differences versus matched references.

## Conditions and diffusion direction

All single-shot cases use T1=1.5s, T2=.08s, T2′=.03s. Bloch has .2×.2-mm in-plane sampling and2-mm slice support; exact pathways use a .2×.2×1-mm box. Exact water uses physical D=.001mm²/s, passed as MRzero D=1. Nominal b0 retains the scanner's diffusion-DAC1 workaround and module timing. It is not a literal zero-gradient waveform, diffusion-OFF scanner branch, or zero total b: imaging and crushers still contribute.

Robustness panels use the Cartesian RF/phase subset `(b1000, read, phase0/45/90, B1 .7/.8/1/1.2, B0=0)` plus b0/1000, read/slice/oblique, phase45, B1=.8, B0=100, and mixed phase90/B1 .7/1.2/B0=100 direction challenges. This is a defined 24-point panel, not a full five-dimensional factorial. Exact water is evaluated on the 18 selected points per candidate; it is not the full finite-RF panel.

Four ETL8 heldout points pair phase/oblique directions with `(phase22.5,B1 .9,B0−75)` or `(phase67.5,B1 1.1,B0 150)`. Other heldout points are ETL4/slice/b1000/phase30/.9/−75, ETL6/read/b0/phase60/1.1/−75 and ETL12/new-oblique/b1000/phase60/.9/150. Requested30° and60° become29.925° and60.075° after hardware phase quantization. Heldout uses seed2 and4,096 spins. Longer/shorter trains preserve bounded peak and interpolate RF2–ETL over the same schedule endpoints; they do **not** continue an unbounded40%-per-echo progression. Exact decomposition is intentionally omitted at ETL12.

Direction tables use logical read/phase/slice coordinates. The full primary b trace changes substantially with diffusion direction even before changing crushers. Representative E8 traces below use nominal b1000 with otherwise matched waveforms:

Geometric last-echo times for ETL4/6/8/12 are84/116/148/212ms (sample centers are25µs later). Those ETL changes alter transverse-relaxation exposure as well as pathway history. Their separate result groups are not used as timing-matched proofs of a phase-filtering mechanism.

| Candidate | Read | Slice | Oblique `[577,577,577]` | Read Bzz / Bxz |
|---|---:|---:|---:|---:|
| Original | 1149.637 | 1002.236 | 1081.663 | 17.691 / −23.038 |
| Centered increasing | 1236.771 | 1096.798 | 1173.082 | 104.824 / −30.562 |
| Centered increasing-alternating | 1247.185 | 1107.212 | 1183.497 | 115.239 / −6.583 |
| Centered weak ramp | 1182.437 | 1042.464 | 1118.749 | 50.491 / −24.841 |
| Centered alternating permutation | 1244.332 | 1104.359 | 1180.644 | 112.385 / −13.121 |

All values s/mm². The read Bxx is1131.919 and Byy≈.027 for these cases. Differences in Bzz and Bxz demonstrate directional weighting and cross terms rather than a purely scalar extra b. Tensor coordinates and logical amplitude/slew bounds still require a verified scanner orientation/calibration transform before physical hardware qualification. The full waveform is available in each saved sequence and can be exported with `python -m dwfse.btensor PATH --out OUTPUT`.

## Audit reproduction and additional sensitivity commands

The main report lists screen, broad panels, summary and phantom reproduction. Additional dense near-null checks were run for original, centered increasing, centered increasing-alternating, weak and centered permutation at calibrated RF/phase90:

```powershell
@'
from examples.combined_factor_study import finite
for name in ['original','increasing_centering','increasing_alternating_centering','weak_increasing_centering','high_low_permutation_alternating_centering']:
    finite('sensitivity_dense',name,1000,'read',90,1.,0,n=16000,seed=2)
'@ | python -
python examples/combined_factor_study.py sensitivity --variants high_low_permutation_alternating_centering
```

To repeat the independently audited centered-permutation sequence, build/reuse its phase90 read-b1000 file and use the exact audit harness. Raw sequence paths are content-addressed by settings; the current file is `runs/combined_factor_study/sequences/5dd811482568c653/seq.seq`.

```powershell
python examples/audit_combined_factors.py --sequence high_low_permutation_alternating_centering=runs/combined_factor_study/sequences/5dd811482568c653/seq.seq --out runs/combined_audit/centered_permutation --support-relaxation
python examples/audit_combined_factors.py --summarize
python examples/verify_combined_artifacts.py
```

The auditor can accept repeated `--sequence ID=PATH` arguments; add `--bloch` for12,000-spin seed41, B0=37Hz,10/5/2.5µs RF-step checks. `--support-relaxation` adds .5/2-mm voxel support × T2 .06/.10s × D0/.001 at RF.8/phase90. `--skip-closure` is an explicit approximation option, and was not used for finalist acquired-signal validation. Summaries aggregate existing raw audit directories; they do not rerun their simulations. [Archived audit summary](../data/combined_audit_summary.json), [finalists](../data/combined_audit_finalists.csv) and [support comparisons](../data/combined_audit_support_relaxation.csv) keep compact evidence available.

For a clean-machine full audit, supply the generated original, centered increasing, increasing-alternating, weak and permutation files from their saved `seqid` settings. Complete raw results are under `runs/combined_audit`; the metadata retain input paths and hashes. The local Fourier longitudinal-diffusion sensitivity copy is generated from the enumerator source with one explicit coefficient substitution and is recorded in metadata. It does not modify upstream/core behavior. No RF history is pruned in the exact enumerator; the comparison MRzero graph uses zero magnitude thresholds and a sufficiently large state cap, with acquired-signal closure checked.

## Artifact integrity and source provenance

Dependencies are Python3.11.9, NumPy2.1.0, SciPy1.14.1, Matplotlib3.9.2, PyPulseq1.5.0.post1, torch2.14.0 and MRzeroCore1.1.1. The prior reproduction is tracked as `examples/reproduce_combined_prior.py`; its compact result is [archived](../data/combined_prior_reproduction.json).

[Study provenance](../data/combined_factor_provenance.json) distinguishes Git-blob baseline hashes from working-file byte hashes and LF-normalized content hashes. Windows line endings can change byte hashes without changing code. The concurrent v1.7 timing guard changes content relative to commit`c87b30e`; original v1.6 and numerical core content remain unchanged. Every study sequence explicitly uses v1.6 plus overrides. [Final verification](../data/combined_verification.json) independently inventories caches, checks sequence readback timing, first-crusher preservation, fixed TE/ESP/TR, finite metrics, tensor symmetry/positive semidefiniteness and report links. Arithmetic component closure in that inventory is distinguished from the acquired-MRzero audit. The current regression suite has31 passing tests; phantom spatial convergence still fails.
