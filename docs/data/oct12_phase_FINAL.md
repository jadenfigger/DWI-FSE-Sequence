# October 12 frequency and off-centre phase checks

This note completes the A/B frequency comparison and the D/E/F/G off-centre phase-calibration checks. It uses the MRD reconstructions and navigator-phase fits summarized in [`oct12_phase_calibration.json`](oct12_phase_calibration.json), [`oct12_phase_calibration.csv`](oct12_phase_calibration.csv), and the figures in `docs/figures/physical_scanner_2026-10-12/`.

## A/B readout-bandwidth frequency check

A and B are matched v1.83, ex-vivo b10 scans with 20 kHz and 40 kHz readout bandwidth, respectively. Their same-FOV image registration gives a relative readout displacement of **−0.05 pixel** and a phase-encode displacement of **0.00 pixel** at the analysis setting (upsample factor 20). The sign convention for frequency offset is not calibrated. At 40 kHz, one readout pixel corresponds to 312.5 Hz, so this displacement corresponds to a nominal estimate of **−16 Hz**. The measured displacement is well inside the tool's 0.5-pixel pass limit, equivalent to about 156 Hz; the upsample-factor sensitivity check gives −0.04 to 0.00 pixel in readout and 0.00 to +0.02 pixel in phase encode.

The result supports the conclusion that A and B were acquired at a sufficiently matched centre frequency for the planned bandwidth comparison. It is an image-registration estimate, not a direct frequency readout: the MRD has a zero placeholder for observe frequency, the subpixel estimate has finite precision, and the comparison cannot distinguish small frequency change from other changes in the object or acquisition. The independent October 11 comparison registered at 9.1 pixels (about 2.83 kHz by the same conversion), so A/B are consistent with the good October 10 check and differ strongly from the known October 11 failure.

This check does **not** measure a spatial B0 map and does not exclude local or spatially varying off-resonance. Image registration constrains net geometric displacement for these scans; it cannot by itself establish a bound on B0 across the brain or rule out B0 as a contributor to other image effects.

Evidence: [`freq_check_AB.png`](../figures/physical_scanner_2026-10-12/freq_check_AB.png).

## D/E/F/G off-centre phase calibration

The four ex-vivo v1.83 scans use three slices at z = −1.2, 0, and +1.2 mm. D uses mode 0. E, F, and G use mode 1 with phcal 0, +530, and −530 ticks. Fits use the first navigator echo train and the model `phase(e) = c + s(e−1) + h(−1)^e`, where `s` is the echo-to-echo ramp and `h` is odd/even alternation. The stated per-slice pass limits are |s| ≤ 5°/echo and |h| ≤ 5°.

| Scan | Mode / phcal | z = −1.2 mm: ramp / alternation | z = +1.2 mm: ramp / alternation | Finding |
|---|---|---:|---:|---|
| D | 0 / n.a. | −0.2 / −12.6° | +0.1 / +14.8° | Ramp is near zero; both slices fail the alternation limit. |
| E | 1 / 0 | −49.7 / +21.0° | +49.9 / −24.0° | Large, opposite-sign ramps; fails both criteria. |
| F | 1 / +530 | −0.9 / +5.7° | +0.8 / −8.7° | Ramp is near zero; alternation improves but both slices remain outside the strict limit. |
| G | 1 / −530 | +81.8 / −44.1° | −82.2 / +40.2° | Large, opposite-sign ramps and alternation; fails both criteria. |

The sign test is clear: at this geometry, +530 ticks is the corrective direction. It reduces the mode 1 ramps from about 50°/echo in E to below 1°/echo in F; −530 ticks in G increases their magnitude to about 82°/echo. F therefore verifies the ramp correction near the candidate setting, but it does not pass the full calibration criterion because alternation remains 5.7° and 8.7° in magnitude. Mode 0 D also has a small ramp but alternation of 12.6° and 14.8°.

The three mode 1 settings give per-slice ramp-zero estimates of about 539 ticks at −1.2 mm and 538 ticks at +1.2 mm. The fitting tool rounds their joint recommendation to **+540 ticks**. This is an interpolated recommendation, not an acquired setting or a demonstrated full pass. The measured +530 scan is close to the estimated ramp zero and already shows that the remaining failure is alternation. No measurement at +540 ticks was made, so neither the ramp nor alternation criteria are experimentally verified at that value.

These checks cover only ±1.2 mm, one ex-vivo subject and one acquisition per setting. They do not establish performance at larger offsets, in vivo, or across subjects. The fitted ramp has a 180°/echo alias coupled to a 90° alternation shift; the solver chooses a representation using paired-slice consistency. Fit residuals for D/F/G are roughly 1–16°, and E about 6°, while the displayed threshold is applied to the fitted parameters. The fits and thresholds should therefore be read as navigator-based diagnostics for these scans, not direct measurements of each RF pulse's phase.

Evidence: [`phasecal_echo_phase_DEFG.png`](../figures/physical_scanner_2026-10-12/phasecal_echo_phase_DEFG.png), [`phasecal_phcal_scan_pm1p2mm.png`](../figures/physical_scanner_2026-10-12/phasecal_phcal_scan_pm1p2mm.png), and [`phasecal_image_strips.png`](../figures/physical_scanner_2026-10-12/phasecal_image_strips.png). The numeric per-slice values and fit diagnostics are in the linked JSON and CSV above.
