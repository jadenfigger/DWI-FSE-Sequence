# ADC center snapshots and alternating crusher interpretation

All comparison PNGs are together in [echo_snapshot_comparison](figures/echo_snapshot_comparison/). Start with `00_read_me_first.png`, then the `00_compare_echo08` images. The detailed images show all eight echoes for each alternative. The same axes are used throughout.

## What the images show

There are ten alternatives, each at RF scales 0.8 and 1.0 and excitation phase offsets 0 and 90 degrees. Each of the 40 conditions has two PNGs:

- **bloch_snapshots:** total local transverse magnitude, phase, and longitudinal magnetization across the slice, using finite-duration sinc RF pulses. All signal routes are mixed together. Longitudinal magnetization is what is currently stored; it is not an isolated stimulated echo.
- **stimulated_pathways:** primary, stimulated, and total transverse profiles in the separate instantaneous-RF model. Red isolates routes containing longitudinal storage after excitation, excluding equilibrium/T1-recovery lineages. The bottom row shows complex voxel-integrated contributions. Gray denotes remaining routes and recovery; blue denotes primary; black denotes total.

The samples are actual ADC samples at index `N//2`, the upper-middle sample when N is even. In this protocol they are 25 microseconds after the geometric ADC midpoint. This matches the acquired-signal convention used in the investigation, rather than choosing a nearby unsampled time.

The profiles in the two models are not interchangeable. Bloch spans 2 mm in z to include slice-profile edges; pathway profiles use a 1-mm box and average analytically over the 0.2 by 0.2 mm in-plane support. The Bloch snapshot phase is in the simulation frame; the pathway profiles include receiver phase, and their bottom-row arrows are rotated to place the primary on the positive real axis. Their absolute amplitudes and phase frames should not be equated across models.

## The alternatives

| Image prefix | Change from the original |
|---|---|
| 01_original | Original crusher amplitudes and RF phases |
| 02_linear_increasing | Crusher multipliers `[1,1,1.4,1.8,2.2,2.6,3,3.4]` |
| 03_irregular | `[1,1,1.71,0.83,1.37,2.13,1.09,1.91]` |
| 04_alternating | `[1,-1,1,-1,1,-1,1,-1]` |
| 05_rf_xy | RF phase offsets `[0,90,0,90,0,90,0,90]` degrees |
| 06_rf_180 | RF phase offsets `[0,180,0,180,0,180,0,180]` degrees |
| 07_rf_quadratic | RF phase offsets `65*k*k mod 360`, k from 0 through 7 |
| 08_linear_decreasing | `[1,3.4,3,2.6,2.2,1.8,1.4,1]` |
| 09_linear_centered | Increasing crushers plus the existing gradient-delay correction |
| 10_alternating_increasing | `[1,-1,1.4,-1.8,2.2,-2.6,3,-3.4]` |

The first multiplier always acts on the separate first-pulse amplitude. The decreasing example leaves that pulse unchanged and reverses pulse 2 through 8 amplitudes from the increasing design. Both therefore use the same set of later strengths; the order changes. This is a controlled local comparison, not a reproduction of a published scanner protocol.

The alternating-increasing and corrected-timing examples are additional comparisons. The other alternatives retain original timing, allowing the individual changes to be compared separately. Both lobes within every crusher pair match in strength and polarity.

## Why our simple alternating schedule lost so much signal

The new decomposition sharpens the earlier explanation. It is not enough to say that crushers removed helpful extra echoes. For this schedule, substantial extra signal remains and actively opposes the primary.

At echo 8, RF scale 0.8, and zero excitation phase error, the instantaneous-RF results are:

| Quantity | Original | Simple alternating |
|---|---:|---:|
| Primary amplitude | 0.06675 | 0.06675 |
| All-other coherent amplitude | 0.05374 | 0.05256 |
| All-other direction relative to primary | about 2 degrees | about 175 degrees |
| Acquired total amplitude | 0.12047 | 0.01504 |

The primary survives. With original crushers the extra contribution points almost the same way and reinforces it. With alternating crushers it points almost the opposite way and cancels most of it. The stimulated-only sum changes from about **+0.04673 to -0.05919** after expressing these aligned-case signals in the primary's frame. This directly identifies stored routes as a major contributor to the cancellation.

With a 90-degree excitation offset, the alternating design's all-other sum is almost exactly opposite the primary, leaving only 0.01149 total in that model. The 10,000-spin finite-RF calculation also shows a substantial loss relative to the original at RF scale 0.8. It does not independently decompose its routes, so the precise fraction of its loss attributable to this mechanism remains an interpretation.

The snapshot study has stationary spins and effectively zero diffusivity. Consequently, the large loss in these comparisons cannot be explained as extra attenuation from simulated Brownian diffusion. Nor is it receiver averaging of differently phased echoes: the loss is already present within individual acquired echoes.

The result rejects this particular constant-magnitude alternating pattern under these tested settings. It does not reject alternating crushers as a general design method.

## What changing the alternating amplitudes revealed

The additional alternating-increasing schedule strongly changes this result. At RF scale 0.8 it reduces unwanted amplitude share to **25.3%**, compared with 85.6% for simple alternation and 56.9% for the increasing same-sign schedule. The coherent stimulated amplitude at echo 8 falls to about 0.00154 in the aligned case and 0.00126 with a 90-degree excitation offset. The intended stationary-route amplitude remains 0.06675.

| Schedule at RF scale 0.8 | Unwanted amplitude share | Total finite-RF signal at echo 8 with phase error 0 / 90 degrees |
|---|---:|---:|
| Original | 91.6% | 0.06785 / 0.03921 |
| Simple alternating | 85.6% | 0.01613 / 0.01863 |
| Increasing same-sign | 56.9% | 0.05765 / 0.04969 |
| Decreasing same-sign | 56.2% | 0.05631 / 0.04265 |
| Alternating and increasing | 25.3% | 0.04166 / 0.04334 |

My interpretation is that varying the alternating amplitudes breaks gradient-history cancellations left intact by a repeating plus/minus pattern. It is a much stronger route filter in these conditions and substantially recovers total signal relative to simple alternation. It still loses aligned total signal compared with the original and increasing same-sign design. At RF scale 1.0 it also has mixed total-signal results. This is a promising additional candidate, not a newly established best design: it has only these four conditions, not the earlier 48-condition robustness grid or a separate water-diffusion comparison.

The decreasing design gives a similar unwanted share to the increasing design. This supports the importance of changing strengths, rather than a universal need to increase them. Echo-8 finite-RF signal favors the increasing schedule in these four conditions, but this comparison does not establish the optimal direction or schedule over longer trains and other RF errors.

## What the literature actually supports

**Diffusion multi-spin-echo imaging with alternating crushers:** [Tu and colleagues, 2014, Phase-Aligned Multiple Spin-Echo Averaging](https://pmc.ncbi.nlm.nih.gov/articles/PMC4252722/) explicitly alternate crusher-pair signs between echoes. They use tailored SLR refocusing pulses and phase-align echoes before averaging. Importantly, they repeat the same k-space line across echoes, whereas accelerated FSE typically acquires different lines. This is direct diffusion refocusing-train evidence, but not an exact reproduction of our FSE readout.

**TSE with sign and amplitude variation:** [Targeted Radiofrequency Field Mapping using 3D Reduced Field-of-View Catalyzed Double-Angle Method, 2012](https://pmc.ncbi.nlm.nih.gov/articles/PMC3375110/) describes crushers alternating in sign and varying in amplitude to isolate the primary route. It is TSE RF mapping, not DWI; it supports the approach in an RF echo train, not a claim that our specific DWI pattern must work.

**Direct diffusion TSE with decreasing crushers:** [Ye and colleagues, ISMRM 2008](https://cds.ismrm.org/protected/08MProceedings/PDFfiles/00759.pdf) use crusher strengths decreasing across the train, with navigation and phase correction. It supports varying crusher strength in FSE-DWI; the text does not establish simple alternating crusher signs.

**Diffusion-specific crusher design:** [Nagy and Weiskopf, 2014](https://onlinelibrary.wiley.com/doi/full/10.1002/mrm.24676) demonstrate why crusher and diffusion-gradient contributions must be considered together in twice-refocused diffusion imaging. That preparation differs from a long FSE readout. In our main comparison the diffusion gradients are along read and the crushers along slice, so simple same-axis crusher/diffusion cancellation is not a demonstrated explanation for our loss.

These sources support testing designed crusher schedules, not changing signs without checking which routes reappear at the ADC. Changing RF phase between echoes also differs from correcting acquired echo phase afterward. Post-acquisition phase alignment can fix cancellation between separate echoes; it cannot recover cancellation that has already occurred inside an individual echo.

## Conditions and validation

TE is 36 ms, echo spacing 16 ms, and echo train length 8. Requested b is 1000 s/mm2 along the read axis. B0 is zero; T1 is 1.5 s, T2 80 ms, and T2 prime 30 ms. Finite-RF Bloch uses 10,000 stationary spins with the same spatial/off-resonance sampling and seed 1 in every condition, and a 10-microsecond RF time step. RF scale applies to both excitation and refocusing. Excitation phase offset is a coherent phase perturbation, not actual motion.

The instantaneous model requests D=0. MRzero internally floors it to 1e-6 in its D units; the spatial reconstruction retains that negligible floor to match the exact enumerator. It also retains the enumerator's longitudinal-diffusion convention. Neither this floor nor that convention is used to make a physiological diffusion prediction here.

Every generated sequence passes the modeled timing checks. Every Bloch snapshot's mean transverse magnitude is checked against the signal at the actual selected ADC sample. Analytically integrating each reconstructed spatial component is checked against the existing exact pathway enumeration at every echo; the largest absolute discrepancy is 1.7e-8. Independent MRzero signal closure is checked for both newly introduced schedules at both RF strengths and both phase errors; the largest relative discrepancy is 5.0e-5, or about 0.005%. [Closure results](data/echo_snapshot_closure.json).

Reproduce with `python examples/compare_echo_snapshots.py`. Raw settings, full pathway lists, sequences and Bloch arrays are under `runs/echo_snapshot_comparison`. A compact numerical table is saved at [echo_snapshot_comparison.csv](data/echo_snapshot_comparison.csv). This study extends the earlier investigation; it does not overwrite its original evidence tables.
