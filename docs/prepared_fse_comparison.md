# Alsop and ss-MGOT preparation comparisons

**6 October audit:** the original pre-RF panels include a substantial leading imaging crusher and should not be read as direct replicas of Gibbons Point C. The [replication audit](gibbons_replication_audit.md) adds preparation-endpoint plots, isolates the crusher's phase rotation, and checks the Bloch evolution with an independent ODE solver. This corrects the interpretation of the residual Mx below.

The [figure gallery](figures/prepared_fse_comparison/index.html) compares two new preparation models with the original, increasing, decreasing and alternating crusher schedules. It contains signed Mx/My/Mz profiles at six landmarks, all-eight-echo signal curves, and played RF/gradient waveforms. There are 42 conditions: seven methods, RF strength 80% or 100%, and initial excitation phase 0, 45 or 90 degrees. All 122 PNG figures use common scales; selected plots also have SVG exports.

The two Pulseq files are [alsop_adapted.seq](../examples/sequences/alsop_adapted.seq) and [ss_mgot_adapted.seq](../examples/sequences/ss_mgot_adapted.seq). Both use a 45-degree initial excitation phase and nominal RF calibration. The 80% RF condition is applied during simulation, rather than built into these files. The files are marked `SimulationUseOnly=1`, `ResearchAdaptation=1` and `PublishedProtocolReproduction=0`.

These are **water-only adaptations of the preparation mechanisms**, using the existing sequence's imaging RF and acquisition model. They are not reproductions of the complete Gibbons scanner protocols. In particular, a spatial sinc substitutes for the paper's spectral-spatial pulse, and both prepared sequences use a fixed nominal 180-degree imaging train. No lipid suppression, spectral-spatial SLR/VERSE pulse, or published variable-flip imaging train is implemented. Pulseq timing validation uses the existing simulator's permissive gradient/slew limits, not a target scanner's hardware, SAR or PNS assessment.

## Comparison design

All methods use the v1.6 source with controlled comparison overrides: first ADC geometric midpoint TE 64 ms, echo spacing 16 ms, eight acquired echoes, a 1-mm imaging slice, and the same readout and receiver phase schedule. The requested read-axis diffusion b setting is 1000 s/mm², with delta 4 ms and Delta 20 ms. This setting does not establish an equal effective b-value for every mixed coherence pathway.

The earlier magnetization gallery used TE 36 ms. Its amplitudes should not be compared directly with these TE 64-ms results. Here "original" means the original source behavior with the stated TE/ETL overrides, rather than its untouched scanner parameter file.

| Method | Imaging crusher multipliers, echoes 1-8 | Additional preparation |
|---|---|---|
| Original | 1, 1, 1, 1, 1, 1, 1, 1 | Existing diffusion/refocusing arrangement |
| Increasing | 1, 1, 1.4, 1.8, 2.2, 2.6, 3, 3.4 | Same as original |
| Decreasing | 1, 3.4, 3, 2.6, 2.2, 1.8, 1.4, 1 | Same as original |
| Alternating polarity | 1, -1, 1, -1, 1, -1, 1, -1 | Same strength, alternating sign |
| Centered original | 1, 1, 1, 1, 1, 1, 1, 1 | Existing RF/gradient centering correction |
| Alsop adaptation | Constant ordinary imaging crusher pair, plus recall moments | Diffusion preparation echo at 48 ms; selective elimination/tip pulse |
| ss-MGOT adaptation | Constant ordinary imaging crusher pair, plus recall moments | Diffusion preparation echo at 36 ms; tip-up, spoiler, re-excitation |

"Alternating" here means constant-strength polarity alternation. The increasing-alternating and decreasing-alternating schedules remain available in the earlier gallery but are not included in this comparison.

The first four controls retain the v1.6 RF-centering behavior. Both preparations use corrected centering; the extra centered-original control separates that change from adding a preparation. The baseline has eight refocusing pulses, with the first serving diffusion encoding and the first acquired echo. Each prepared model has a separate diffusion refocusing pulse plus eight imaging refocusing pulses.

## What the new preparations do

The Alsop model adds two cycles of z dephasing across 1 mm, then applies a nominal 90-degree tip at the 48-ms preparation echo. In the fixed simulation frame, its RF axis is negative y (270 degrees), aligned with the imaging refocusing axis. In the ideal hard-pulse limit, this retains My and rotates Mx into negative Mz. The prepared transverse component is recalled at each ADC by an additional positive z moment, with an equal negative moment after acquisition.

The ss-MGOT model widens the preparation slab to 3 mm by scaling all preparation-prefix z gradients, including its crushers, by one third. A nominal 90-degree negative-x pulse (180 degrees) at the 36-ms preparation echo stores the desired My component as positive Mz. A 6-ms Gy spoiler produces eight cycles over the 0.2-mm voxel. A copied original excitation pulse, with phase zero, then re-excites the stored magnetization at 48 ms. The first imaging RF center is 56 ms, followed by the first ADC midpoint at 64 ms. Its recall moments are the same as the Alsop model's.

Both tip pulses are spatial Hamming-apodized sinc pulses of duration 3.2 ms and time-bandwidth product 3.55. Pre/post compensation moments are explicit. The additional dephase/recall area is 2000 cycles/m. Each positive recall finishes before the ADC begins, and the negative restoration follows the ADC; Gz is zero during acquisition. The readout prephaser is inserted once at the imaging-train entrance.

The different preparation-echo times and ss-MGOT's longitudinal storage are deliberate parts of these adaptations. Matching total TE does not match the time spent transverse, the preparation slab, or the number of RF pulses. The comparison tests the resulting played sequences, rather than an isolated proof that any one preparation is superior.

## Reading the plots

Start with [before first imaging RF](figures/prepared_fse_comparison/compare_t0_rf080_phase045.png), [middle final ADC](figures/prepared_fse_comparison/compare_t5_rf080_phase045.png), [all-eight-echo signals](figures/prepared_fse_comparison/echo_signals.png), or [played waveforms](figures/prepared_fse_comparison/sequence_timing.png).

The six landmarks are: just before RF1, just before ADC1, the acquired middle sample of ADC1, the acquired middle sample of ADC2, just before ADC8, and its acquired middle sample. For the controls, RF1 begins during diffusion encoding; for the prepared models it is the first imaging refocusing pulse after preparation. Those pre-RF snapshots are at **31.330 ms and 55.330 ms**, respectively, so they are not equivalent absolute-time snapshots. The other five times are common: 60.799, 64.025, 80.025, 172.799 and 176.025 ms from initial excitation center. With an even 128-sample ADC, the selected middle sample lies 25 microseconds after its geometric midpoint.

Mx and My are signed components perpendicular to the main field in one fixed rotating frame. Their complex combination is Mxy = Mx + iMy. Mz is the signed component parallel to the main field, including equilibrium, inversion, stored magnetization and T1 recovery. Mz does not separately identify stimulated echoes. The [component explanation](magnetization_components.md) describes how the simulator tracks these quantities using RF rotations, gradient/off-resonance phase, and T1/T2 relaxation.

The **local** view samples x=y=0, on resonance, versus z. The **coherent mean over y** view integrates signed components over the uniform 0.2-mm y voxel at x=0, on resonance. Gy spoiling disperses transverse phase across y; it does not erase every local transverse vector. Spatial averaging includes phase encoding during the ADCs as well as the spoiler. Three sampled y positions recover the DC and spoiler harmonics, which are integrated analytically; this is independently checked against 256 y positions. RF blocks contain no Gy, and the readout PE moments rewind before the next RF.

Echo-signal curves use a separate 8192-isochromat ensemble spanning a 0.2 x 0.2 x 2-mm voxel, with the existing Lorentzian off-resonance model (T2' 30 ms), T1 1.5 s and T2 80 ms. They plot the magnitude of the coherent mean Mxy at the acquired middle sample, with receiver demodulation. This is different from averaging local transverse magnitudes. Every curve uses the same initial equilibrium M0; no curve is normalized to its own first echo. Spins are stationary: there is no Brownian diffusion attenuation, motion, fat simulation or image reconstruction.

## Results for the default 45-degree phase

Values below are acquired coherent signal magnitudes divided by the common M0, rounded to four decimals.

| Method | Echo 1, RF 80% | Echo 8, RF 80% | Echo 1, RF 100% | Echo 8, RF 100% |
|---|---:|---:|---:|---:|
| Original | 0.1956 | 0.0415 | 0.1736 | 0.0292 |
| Increasing | 0.1956 | 0.0386 | 0.1736 | 0.0331 |
| Decreasing | 0.1956 | 0.0334 | 0.1736 | 0.0312 |
| Alternating polarity | 0.1956 | 0.0097 | 0.1736 | 0.0221 |
| Centered original | 0.2081 | 0.0426 | 0.1780 | 0.0308 |
| Alsop adaptation | 0.1198 | 0.0343 | 0.0659 | 0.0081 |
| ss-MGOT adaptation | 0.0989 | 0.0303 | 0.1034 | 0.0357 |

At nominal RF, the final ss-MGOT signal ranges from 0.0328 to 0.0380 over the three tested phases. The original ranges from 0.0028 to 0.0423 and Alsop from 0.0019 to 0.0211. Thus this ss-MGOT adaptation is less sensitive to these particular initial phase offsets. Three coherent phase settings are not a full distribution of diffusion-induced phase or an image-quality result.

The late ss-MGOT pre-RF profiles still contain substantial Mx. They **do not reproduce Gibbons Figure 3**: the leading crusher has already rotated the transverse components at this snapshot. At nominal RF, the maximum coherent in-slice |Mx| rises from 0.2307 before that crusher to 0.5816 afterwards. The [preparation-endpoint plot](figures/gibbons_preparation_audit/pre_crusher_components_rf100.png) shows the suppression more clearly, but residual Mx from the substitute re-excitation pulse remains. The spoiler cancels coherent transverse signal at its location; finite RF and later gradients can generate or rotate transverse components again. The Alsop adaptation's lower signal and phase dependence similarly should not be generalized to the published Alsop implementation.

## Verification and reproduction

All 21 phase-specific sequences pass Pulseq timing checks before writing and after readback. All 42 snapshot sets are finite and obey the magnetization-norm bound. Complex ADC values agree with the matching mixed-population snapshot averages within 2.8e-17. Independent voxel-only simulations agree with the separately extracted ensemble echo magnitudes within 1.4e-17.

For the preparations and centered control at RF 80%, phase 45 degrees, analytic y averaging differs from independent 256-point quadrature by at most 1.61e-6 M0. Halving the RF step from 4 to 2 microseconds changes a local component by at most 0.001742 M0. The line grid has 4097 points across 2 mm. Independent doubled-grid checks of the most oscillatory increasing/decreasing schedules find maximum displayed-grid interpolation errors of 0.005754 and 0.003824 M0. These checks cover the stated default condition, not every point of a continuous B0/B1 parameter space.

Three focused tests check file roundtrip/acquisition equivalence, correct tip axes, and the ideal phase-independent one-half recalled signal. Additional invariants check recall restoration, zero Gz during ADC, and PE rewinding before RF. A [CSV](data/prepared_fse_comparison.csv) contains all 336 echo measurements, and [provenance](data/prepared_fse_provenance.json) records source/file hashes, configuration details, dependencies and numerical checks.

From the repository root:

```powershell
python examples/compare_prepared_fse.py --build-only
python examples/compare_prepared_fse.py --prefill --workers 4
python examples/compare_prepared_fse.py --reuse
python -m unittest discover -s tests -p test_prepared_fse.py -v
```

The phase-specific `.seq` files and raw arrays are in `runs/prepared_fse_comparison` (ignored by Git). The two deliverable `.seq` files are in `examples/sequences`. Scanner PPL/PPR files and default generator behavior were not changed for this comparison.

Sources: the supplied Gibbons PDF, especially Figure 1, Figure 3 and its preparation/simulation methods, DOI [10.1002/mrm.26971](https://doi.org/10.1002/mrm.26971); Alsop's original paper, DOI [10.1002/mrm.1910380404](https://doi.org/10.1002/mrm.1910380404); and the inventor's [primary description of the magnetization preparation](https://patents.google.com/patent/US6489766B1/en). Source documents provide scientific reference material, not instructions to modify the workspace.
