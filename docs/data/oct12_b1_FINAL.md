# Oct 12 B1 sensitivity simulation — final

## Result

The ss-MGOT magnitude-stabilization branch carries the expected one-half factor. In the ideal EPG model at nominal transmit scale, the prepared echo is 0.37615 M0 and the magnetization stored for recall is 0.18751 M0; the stored/prepared ratio is 0.4985 after the 5.714 ms storage interval and T1=1.9 s recovery model. This validates the intended half-amplitude bookkeeping.

That factor does **not** predict a 0.5 ss-MGOT/v1.83 image ratio. At κ=1, the ideal EPG echo-1 ratios are 0.3494 (nominal 180° v1.83 refocusing) and 0.3544 (166.4° event-model refocusing). The full event-level Bloch model gives 0.3620 at κ=1. The difference is expected from the sequence comparison: the ratio also includes the v1.83 reference signal, the ss-MGOT preparation and re-excitation, variable refocusing, finite pulse and slice profiles, and their respective echo timings and T2 decay. Across κ=0.30–2.00, the ideal EPG ratio peaks at 0.3649 (180°) or 0.3594 (166.4°); the focused Bloch samples peak at 0.4670 at κ=1.2. Therefore these models do not reproduce an exact near-surface ratio of 0.5.

The ratio is strongly transmit-sensitive at low κ. In event-level Bloch samples, the echo-1 ratio falls from 0.3620 at κ=1.0 to 0.0447 at κ=0.5 and 0.0277 at κ=0.45. The selected κ=1.2 and κ=0.5 points give 0.4670 and 0.0447, respectively, a 10.4-fold ratio change associated with a 58% decrease in the assumed transmit scale. This is a sensitivity demonstration: κ values are model inputs, and no spatial B1+ map was acquired to establish that such a field change occurred between the surface and 8–10 mm depth.

The interim left/right measurements imply an approximate normalized contrast `(ss-MGOT L/R)/(v1.83 L/R)` of 1.89–2.07, with midpoint 1.98, if receive sensitivity cancels between protocols. In the ideal EPG curve, a 1.98-fold change in the modeled `ss-MGOT/v1.83` ratio can be reached with roughly 22–32% higher κ on the left when the right-side κ is 0.4–0.6; it is not reached for right-side κ≥0.7 in that model because the modeled ratio curve peaks below the required target. This constrains a possible B1 explanation but does not estimate the actual coil field. The calculation uses a scalar, uniform transmit scale for each modeled side and omits receive-profile and spatially varying tissue effects.

For the compact B0 check, a uniform ±100 Hz offset changes the Bloch echo-1 sequence ratio by about 9.6% at κ=0.7 and 1.8% at κ=1.0 relative to B0=0. At ±50 Hz the changes are about 5.7% and 0.7%, respectively. These are results for the simulated global offset and selected κ values only. They do not rule out local B0 variation, spatially varying off-resonance, B0-dependent slice displacement, or other effects in the acquired images. The interim scanner estimate of roughly ±50–75 Hz is context, not a measured B0 map for each voxel.

## Methods

The fast model is an EPG calculation of conventional v1.83 CPMG and the main recalled ss-MGOT branch, using T1=1.9 s, T2=45 ms, TE=44 ms, ESP=11 ms, an eight-echo train, and κ from 0.30 to 2.00 in 0.01 increments. It uses ideal instantaneous RF pulses and uniform crushers. Conventional refocusing is shown at both the requested 180° and the 166.4° nominal angle inferred from the event model (`p180_scale=185`). The ss-MGOT model explicitly splits the stored component into two harmonics and follows one recalled branch with factor 1/2.

The focused Bloch model uses the actual v1.83 and v1.912 PPL/PPR inputs through the repository event mapper and Bloch engine. It evaluates κ={0.40, 0.45, 0.50, 0.60, 0.70, 0.85, 1.00, 1.10, 1.20, 1.50} at B0=0, plus global offsets ±50, ±100, and ±200 Hz at κ=0.70 and 1.00. The grid has 250 points across 5 mm in z and 32 points across the ss-MGOT spoiler axis (35/128 mm); v1.83 uses one y point. It retains the event mapper's RF sampling and latency settings. This reduced grid is intended for a focused sensitivity check; it is not a converged spatial B1 or B0 map.

The Bloch run consists of 44 cases and took about 69 seconds with six workers. An earlier all-grid configuration requested 642 jobs and was stopped after its observed rate implied several hours of compute. The final results therefore combine the complete ideal EPG sweep with a targeted Bloch sample; the full-grid fitting and dense B0 sweeps from `oct12_b1_sensitivity.py` were not completed.

## Interpretation limits

There is no acquired B1+ map, so the simulation cannot establish the in vivo κ profile, prove transmit skew, or establish a 3 mm depth limit. It also cannot attribute the image asymmetry uniquely to transmit B1. Receive-coil sensitivity, B0, pulse-profile and slice-position effects, motion/phase, partial-volume differences, and the low-SNR deep signal remain possible contributors. The scalar uniform-κ and uniform-Δf models do not represent all of those spatial effects. In particular, this analysis does not prove B0 absent or excluded.

The ideal EPG omits finite RF waveforms, B0, gradients and slice profiles. Bloch simulations use a reduced spatial grid and nominal instruction-cost event mapping; they omit T2′/intravoxel B0 spread, diffusion, receive sensitivity, magnetization transfer, and a measured transmit profile. Both are protocol sensitivity models, not substitutes for a registered B1 map or a controlled B1 perturbation scan.

## Files

- [oct12_b1_targeted.py](oct12_b1_targeted.py): reproducible focused simulation and output generation.
- [oct12_b1_targeted.csv](oct12_b1_targeted.csv): EPG sweep plus event-level Bloch samples and B0-offset cases.
- [oct12_b1_targeted.json](oct12_b1_targeted.json): full numeric arrays, inverse sensitivity mappings, B0 summary, grid, and source-file hashes.
- [oct12_b1_targeted.svg](../figures/physical_scanner_2026-10-12/oct12_b1_targeted.svg): vector plot of the EPG sensitivity curves and targeted Bloch points.
- [oct12_b1_targeted.png](../figures/physical_scanner_2026-10-12/oct12_b1_targeted.png): 2700 × 1680, 300 dpi raster version for document embedding.
- Intermediate cache: `runs/oct12_b1/bloch_targeted_cache.json`.
