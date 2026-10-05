# Independent combined-factor audit

4 October 2026. All tables refer to primary instantaneous-center RF unless explicitly labeled finite-RF Bloch. Scanner files were not changed.

## Metrics and conventions

Primary is the explicit excitation `+` then `- + - ...` transverse-only RF history. Stimulated is the coherent sum of histories containing `Z` and no `Z0`; recovery lineages and remaining transverse histories are reported separately. Total is the complex sum. Non-primary L1 share uses the sum of magnitudes of histories after coherent grouping. It is neither signal power nor an artifact fraction.

Gradients in the file are Hz/m, gradient moments cycles/m, q rad/m and B s/mm². MRzero D is in 10^-3 mm²/s. Requested D=0 is internally floored to 10^-6 in those units.

## Numerical validation

The acquired-signal closure audit covers 528 echo-condition records across ETL4/8. Maximum absolute complex discrepancy is 1.84e-05; maximum relative discrepancy is 0.000591. Pass rule: absolute <=3e-6 OR relative <=5e-4, so ratios at near-zero totals are not used alone. Failures: 0.

An analytic primary amplitude using imported RF angles, T2/T2′, box dephasing and exp(-D trace B_PDG) differs by at most 1.52e-08. No pathway magnitude pruning is applied. Only ETL<=8 is reported; no exact long-train claim is made.

Independent 10-us subdivided trapezoid integration of the played waveform differs from the analytic tensor by at most 0.000143 s/mm² per tensor element. A separately implemented three-node Gaussian quadrature agrees with its trace within 7.73e-12 s/mm². The numerical check tolerance is .002 s/mm².

## Full-waveform versus PDG diffusion weighting

| Candidate | Full E8 trace | Imported PDG trace | Difference (s/mm²) | Difference (%) |
|---|---:|---:|---:|---:|
| increasing_alternating_centering | 1247.184086 | 1246.602140 | 0.581946 | 0.0467 |
| inc_alt_center_duration500 | 1233.878352 | 1233.039438 | 0.838914 | 0.0680 |
| original | 1149.636742 | 1149.337228 | 0.299513 | 0.0261 |
| increasing_centering | 1236.769620 | 1236.086924 | 0.682696 | 0.0552 |
| high_low_permutation_alternating_centering | 1244.331013 | 1243.721591 | 0.609423 | 0.0490 |
| weak_increasing_centering | 1182.436623 | 1181.984417 | 0.452206 | 0.0382 |
| high_low_permutation_alternating | 1247.190479 | 1246.581057 | 0.609422 | 0.0489 |

Both models retain physical RF duration in elapsed time and played gradients while replacing rotations with instantaneous RF at pulse centers. The importer replaces each event interval with its average gradient, so it matches moment endpoints but approximates q within ramps. This explains the small b discrepancy. The largest discrepancy confined to actual RF-support windows is 8.58e-06 s/mm². Thus omitted RF time does not explain it. This check does not establish the effective b tensor of continuously rotating spins during imperfect finite RF.

## Longitudinal diffusion sensitivity

MRzeroCore 1.1.1 uses exp(-D_SI dt |k|²) for stored longitudinal gratings, while its transverse formula uses exp(-D_SI dt |2πk|²). The compatibility column reproduces that implementation; the Fourier column applies (2π)² to longitudinal storage only in a local exact-enumerator copy. The factor follows from applying the diffusion equation to exp(i2π k·r). This is a physically motivated sensitivity bracket, not a validated repair or an uncertainty probability. Desired transverse-only primary amplitudes are identical across both conventions.

[Weigel et al., original anisotropic diffusion EPG work](https://doi.org/10.1016/j.jmr.2010.05.011) establishes pathway-specific diffusion weighting for arbitrary gradient and RF histories. The specific convention diagnosis above is an independent source-code and Fourier-equation audit.

| Candidate | Primary D=.001 | Total compatibility | Total Fourier | L1 share compatibility | L1 share Fourier |
|---|---:|---:|---:|---:|---:|
| increasing_alternating_centering | 0.019190 | 0.017989 | 0.018183 | 31.73% | 30.22% |
| inc_alt_center_duration500 | 0.019452 | 0.018247 | 0.018441 | 31.31% | 29.80% |
| original | 0.021150 | 0.034608 | 0.032506 | 92.07% | 91.84% |
| increasing_centering | 0.019392 | 0.028912 | 0.027299 | 62.24% | 58.12% |
| high_low_permutation_alternating_centering | 0.019245 | 0.027006 | 0.025365 | 49.87% | 45.34% |
| weak_increasing_centering | 0.020471 | 0.035229 | 0.033535 | 69.56% | 67.20% |
| high_low_permutation_alternating | 0.019190 | 0.027036 | 0.025356 | 48.35% | 43.72% |

Conditions: ETL8, B1=.8, excitation phase90°, B0=37 Hz, T1=1.5s, T2=.08s, T2′=.03s, box voxel .2×.2×1 mm, read requested b1000. Relative phases and all echoes are retained in JSON/CSV. Physiological stimulated fractions remain uncertain; total magnitude can increase or decrease when diffusion changes cancellation.

## Timing, hardware and finite-RF limitations

All sequence timing checks pass within the modeled event system. Reported peaks/slew use calibrated logical waveform scaling, gamma42.577478 MHz/T and linear ramps. They are not measured amplifier ratings; no hardware acceptance follows from Pulseq timing alone. RF-energy is integral |B1_Hz|²dt, not SAR. Gradient energy integrates the full played waveform per axis.

The finite-RF Bloch audit uses stationary isochromats, 12000 samples, seed41, B0=37Hz and RF time steps10/5/2.5us at B1=1/.8. It includes shaped pulse profiles and off-resonance during RF; it contains no molecular diffusion. Its absolute amplitude must not be equated to the instantaneous-RF box-voxel pathway amplitude.

| Candidate | Maximum complex change10→5us | Maximum change5→2.5us |
|---|---:|---:|
| increasing_alternating_centering | 4.87821e-05 | 1.42423e-05 |
| inc_alt_center_duration500 | 4.87821e-05 | 1.42423e-05 |
| original | 4.85104e-05 | 1.34379e-05 |
| increasing_centering | 4.87821e-05 | 1.42423e-05 |

The additional shortlisted schedules are audited across .5/2-mm box slice support, T2=.06/.10s, D0/.001, B1=.8 and phase90°. Matched original/increasing controls use the same exact enumerator; acquired-MRzero closure in that supplementary grid is attached for new candidates, while control closures are checked separately in the base grid.

| Candidate | E8 total range across8 support/T2/D cells | Total/original range | Primary/original water range | L1-share change range |
|---|---:|---:|---:|---:|
| high_low_permutation_alternating_centering | 0.015523–0.142626 | 0.666–1.866 | 0.909933–0.909933 | -50.65–-25.80 percentage points |
| weak_increasing_centering | 0.003918–0.130430 | 0.162–1.727 | 0.967880–0.967880 | -40.98–-8.19 percentage points |
| high_low_permutation_alternating | 0.015386–0.142863 | 0.668–1.877 | 0.907335–0.907335 | -50.63–-26.31 percentage points |
| increasing_centering | 0.008412–0.137684 | 0.349–1.823 | 0.916907–0.916907 | -44.49–-16.35 percentage points |

These supplementary cells demonstrate support/relaxation sensitivity. Lower L1 share does not imply larger total: removal or attenuation of a coherent component can improve or worsen cancellation. Ratios are accompanied by absolute totals, and the full paired conditions are retained in `support_relaxation.csv`.

## Reproduction

Run `python examples/audit_combined_factors.py --sequence ID=path/to/seq.seq --out runs/combined_audit/GROUP` (repeat sequence arguments). Add `--bloch` for RF timestep checks, or `--support-relaxation` for the supplementary support/relaxation grid. `--skip-closure` explicitly omits acquired-MRzero closure. Run `python examples/audit_combined_factors.py --summarize` after all groups finish. Complete metadata, actual failures, sequence hashes, tensor matrices, complex components and dependency versions are in `runs/combined_audit/`.
