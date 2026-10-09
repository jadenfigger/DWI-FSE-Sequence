# Physics investigation for v1.81 and v1.911

Investigation date: 2026-10-08. This is a source/model investigation, not scanner verification. No baseline sequence, protocol, include or RF file was changed. The v1.911 baseline is the extracted method-only v7 PPL, SHA-256 `6a0d222b6c8689fbdee5f4ae412c4d5df0bea10a7da99a309fabf5dfab04d828`, rather than the workspace combined v6.

## Main decisions and dependencies

1. **Moving the v1.8 read prephaser after the diffusion pair has a strong physics case.** Its existing position produces diffusion/imaging cross terms; historical nominal b100/b6000 do not describe total played weighting. Preserve the required first-imaging read moment and recompute the complete per-echo tensors after relocation. This is an implementable candidate using existing gradient/matrix primitives, provided the event ledger proves the new lobe finishes before RF/ADC and all timing budgets pass.
2. **Combining the ss-MGOT train lobes is justified if interval areas and the RF-time selector are preserved.** Use separate first and repeated pre-RF contracts. Do not put the repeated `C-D` lobe before RF1: no preceding ADC restoration exists there. Preserve conventional slice selection throughout selective RF. The request to avoid slice-gradient/RF overlap can only sensibly apply to the fused free-precession lobes; a selective RF pulse requires its selector.
3. **Use the inherited played amplitude/ramp envelope for an initial compression candidate.** The PPR's full-scale DAC/slew controls are not measured hardware certificates. A longer merged lobe can remain below the already played 8223-DAC train crusher peak, at the existing 200-us ramp, while reducing sequential gradient time. Real gradient delay/slew, eddy currents and compilation are scanner-verify even when this inherited source envelope passes.
4. **Keep the validated crusher areas.** The Oct 7 data demonstrate no high-b advantage from the stronger v1.8 train crusher, but do not demonstrate that lowering ss-MGOT crushers preserves pathway rejection. Fusion and shorter free intervals can improve diffusion loss without changing C or D. Any crusher reduction needs a new finite-RF coincidence scan, B1/B0/phase sweeps and high-b phantom check.
5. **Refocusing width means spatial coverage, not merely RF duration.** Stretching the same sinc temporally at unchanged selector narrows its bandwidth and spatial coverage. A 1.2-1.5x spatial refocusing width can instead be obtained with a smaller diffusion/train selector, using the unchanged stock pulse, if all selector compensation and crusher-pathway checks are redone. This keeps nominal RF energy unchanged. Its net benefit must be demonstrated with finite pulse profiles; actual achieved flip/slice profile and SAR remain scanner-verify.

## Exact gradient contracts for train fusion

Let signed D be the preparation dephasing area, C the ordinary crusher area, and let Q-/Q+ denote the retained selector contributions before/after the effective RF reference. Separate gradient areas by **every RF and every ADC**, rather than comparing only whole echo intervals:

| Interval | Required ss-MGOT slice area |
|---|---|
| Re-excitation endpoint to first imaging RF | Existing re-excitation compensation + C + Q-; no preceding -D |
| Imaging RF j to ADC j | Q+ + C + D |
| ADC j to imaging RF j+1 | -D + C + Q- |
| After final ADC | Preserve original restoration/terminal contract separately |

If gsp_rp or other slice terms are nonzero they must also be included; the validated method protocol currently has gsp_rp=0 and forbids slice PE. The unchanged selector plateau/ramp integrals are not extra crushers and must not be counted twice. Preserve the complete sampled selector waveform during each RF, including the configured physical gradient lag. For the strongest finite-RF statement, compare free intervals from the last transmitted RF sample to ADC and ADC to the first transmitted next RF sample, then independently prove RF-time gradient/phase/multiplier/sample identity. Center-based effective_moment is a useful instantaneous-RF diagnostic but is not that finite-RF proof.

Proof: between RF boundaries a transverse Fourier state changes by the signed gradient area and a longitudinal state keeps its spatial Fourier order. An identical RF maps each incoming state through the same linear transfer coefficients. Equal areas at every intervening ADC/RF boundary therefore preserve each history's endpoint spatial phase by induction. This includes unwanted and stimulated histories, independent of flip angle. Equal aggregate area over an entire RF-to-RF interval alone does not preserve the two sides of the ADC and can fail the proof. Time compression changes off-resonance phase, T1/T2 relaxation and diffusion; none is covered by this area identity.

Decoded source-level v7 baseline values (manual expression costs x0.8, rfdelay=60 us):

| Quantity | Value |
|---|---:|
| tdp / tcrush / tramp | 700 / 1000 / 200 us |
| Imaging selector / plateau | -1652 DAC / 1320 us |
| C | -9,883,388.16 DAC.us = -7675.483825 cycles/m |
| D | -2,579,491.2 DAC.us = -2003.244501 cycles/m |
| C/D | 3.831526217 |
| C1/D | 2.554350812 |
| C-D | -7,303,896.96 DAC.us |
| C+D | -12,462,879.36 DAC.us |

The secondary positive ramp has a combined area equivalent to 1.0096*tramp, not exactly tramp. A fused top700/ramp200 lobe would require -8098.165 DAC before later RF and -13818.165 DAC after RF, excluding retained selector terms. A longer top1400/ramp200 lobe needs approximately -4560/-7780 DAC for those two areas and stays inside the inherited 8223-DAC peak. Integer DAC rounding leaves a small area residual that must be reported in cycles per slice; exact preservation cannot be claimed from the ideal trapezoid formula. Primary and secondary vendor ramp samples differ, so use decoded waveform integrals and actual matrices for the final comparison.

The overlap/amplitude check must examine the **sum** of primary and secondary output on each physical axis after orientation, not each logical component independently. Check sample jumps/dwell-derived slew, full-scale clipping, and transitions at merged/selector boundaries. Concurrent axes are not automatically unsafe, but a per-axis passing sum is required for every supported geometry. The method-only geometry restrictions materially narrow this audit.

## Diffusion and echo-train decay

For k in cycles/m, the pathway tensor is B=(2pi)^2 integral[k k^T dt], with conversion by 1e-6 to s/mm^2. A transverse state accumulates k from gradients with its coherence sign. An encoded longitudinal state ignores subsequent gradients but retains k, and continues to diffuse with B_Z=(2pi)^2 k k^T dt. It does not become immune to diffusion when stored.

This is directly supported by [Weigel et al., Extended phase graphs with anisotropic diffusion](https://pubmed.ncbi.nlm.nih.gov/20542458/) and the [MRzero primary implementation](https://raw.githubusercontent.com/MRsources/MRzero-Core/main/python/MRzeroCore/simulation/main_pass.py), whose longitudinal branch explicitly converts rotations/m to radians/m before the diffusion exponential. Pathway-dependent diffusion is a physically credible contributor to the scanner's faster train decay, especially with large crushers and low refocusing angles. The Oct 7 observations do not uniquely establish that cause; finite selective transfer, B1, off-resonance and hardware timing remain competing explanations.

**Existing tool defect discovered:** `dwfse/pathways.py` computes transverse b with `(2*pi)^2`, but its `z_diffusion` expression omits this factor for longitudinal spatial states. The missing factor is approximately 39.4784. Its current diffusion result must not serve as the independent physical oracle for this task. The module also intentionally rejects additional preparation RF and cannot directly enumerate ss-MGOT. No existing file was edited. Use a new generalized enumerator with an independent longitudinal heat-equation regression. EventBloch currently has relaxation but no molecular-diffusion evolution; its excellent static-spin numerical agreement cannot exclude stimulated-path diffusion loss.

Area preservation does not fix B: moving a lobe changes the time spent at high k and its correlation with other axes. The net b change can have either sign for a particular history; evaluate the actual compressed waveforms instead of asserting improvement from ESP alone. The complete complex sum of pathway contributions determines observed signal; an L1-weighted or primary-path tensor is not a universal effective b tensor for low-angle FSE.

For scale only, encoded k=7675 cycles/m held for 1 ms gives about 2.33 s/mm^2 of b and attenuation exp(-b*D). Ten milliseconds gives about 23.3 s/mm^2, or 4.6% loss at D=0.002 mm^2/s. Higher-order states can lose much more. These are analytic examples, not a fit to phantom temperature or measured scanner diffusivity.

## Timing, TE and isodelays

The stored baseline first imaging ADC center is about 73.7 ms after prep excitation; the re-excitation reference is about 59.7 ms. A 12-ms constant imaging ESP, if feasible in the final ledger, would move ADC1 approximately 2 ms earlier and save 16 ms by ADC8. For a pure transverse path at T2=32 ms these savings alone correspond to factors exp(2/32)=1.0645 and exp(16/32)=1.6487. The actual low-angle ss-MGOT signal is not a pure T2 decay, so these are illustrative upper-level timing gains, not Bloch or EPG predictions.

The existing source ledger already shows small cost-dependent timing offsets; use the final generated v7-derived sources under every calibrated/sensitivity cost model. Include RF start latency separately from gradient lag and do not add rfdelay twice. The stock decoded RF contains guard samples and its physical sample duration differs from the declared duration, whereas v19 pulses have their own 10-us samples. Compare physical RF samples and the actual geometric ADC center, with discard and even-sample conventions explicitly stated.

The documented approximately 95-us off-resonance shift is consistent with selective RF effective time differing from geometric center. The fitted excitation/re-excitation kappa is a spatial phase diagnostic, not a universal B0/B1-independent isodelay of arbitrary finite-angle RF. At 128 Hz, 95 us is about 4.38 degrees of phase. Correct timing through a reproducible finite-RF phase derivative/echo-peak analysis over the stated B1/B0 range, preserving selector compensation; do not simply hard-code a fitted +95-us shift and call every event exact. A common pulse-start latency need not move all echo references equally relative to ADC, so sensitivity over the requested ~3-us value is still necessary. Physical latency remains scanner-verify.

## Conservative decisions on remaining ideas

* **Preparation TE reduction:** worthwhile if free source gaps can be reduced with the same delta/Delta, moments and RF transfer. Changing delta or Delta changes required gradient amplitude and diffusion time; a stronger gradient to preserve b is outside the inherited conservative envelope unless independently supported. The large Delta=40 ms already fixes a substantial preparation floor. Do not promise a gain before the event inequality scan.
* **ss-MGOT crusher reduction:** retain current validated ratios in the first candidate. Consider later only after the complete coincidence scan and diffusion-aware pathway comparison identify a benign smaller-area window.
* **v1.8 variable flips:** decline as an initial change. This is phase-sensitive diffusion FSE, and a new low-angle schedule adds stimulated pathways/motion fragility without a demonstrated sensitivity gain. The scanner evidence does not justify that risk merely for nominal SAR reduction.
* **Per-shot navigation:** scientifically valuable for multishot diffusion, but adding an ADC does not itself implement phase correction or establish vendor data-layout support. A terminal unencoded echo after restored/rewound imaging moments is the conservative concept; it costs train time and needs an explicit receiver/storage/shot-association/reconstruction contract. This is an implementation uncertainty worth asking about if no repository evidence resolves it. [Van et al., phase errors in multishot dprep-TSE](https://pmc.ncbi.nlm.nih.gov/articles/PMC5418150/) explains why magnitude stabilization leaves shot-dependent phase that must be handled before multishot combination.

## Independent validation required before packaging

1. Compare the extracted v7 baseline and candidate at every RF-start/end and ADC boundary; retain first-echo and last-echo special cases. Cross-check effective_moment with exact waveform integrals and generalized pathway endpoints. Prove unchanged finite RF-time selector samples separately.
2. Compute both endpoint carrier/conjugate harmonics and every bounded instantaneous-RF history through eight imaging echoes. Record per-path B, attenuation and coherent sums at D=0 and representative positive diffusivities, B1=0.8-1.1, B0=0,+/-128 Hz, initial phases0/45/90. State finite-RF and ETL16 limits plainly.
3. Use exact polynomial integration of piecewise-constant physical gradients for k and B, cross-check an independent sampled k_path convergence, and verify encoded-Z diffusion against numerical heat-equation decay with the 2pi factor.
4. For spatially wider v1.8 refocusing, recompute finite slice transfer, complete Bloch trains and crusher coincidences. Hold RF energy/flip calibration assumptions explicit. Compare both original-crusher and Oct7 strong-crusher controls.
5. Check fused lobes do not enter transmitted RF or ADC windows; check conventional selector remains during RF; audit summed physical-axis amplitude/slew and matrices under all cost models.
6. Do not claim scanner validation. Required scanner checks include vendor compilation/image size, RF/gradient delay and isodelay timing, amplifier/coil limits and achieved flips, b0 echo centering, high-b suppression and multi-shot navigator interpretation.

## Questions / uncertainty policy

The parent has requested hardware limit and timing information from the user. If unavailable, conservative source-envelope candidates may still be modeled and clearly marked scanner-verify, but no unseen hardware certification is inferred. Do not silently turn a strongly justified but unresolved PPL/hardware change into a marginal-benefit proposal. Batch the precise unresolved implementation questions, describe the recommended source-envelope option and the console trace/calibration that would resolve them. The user's later instruction raises the question threshold and favors using repository evidence where it is sufficient.
