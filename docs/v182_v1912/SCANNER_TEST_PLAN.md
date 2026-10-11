# Scanner test plan: v1.82 and v1.912

**All results below are prospective. The sequences and event-model checks are not scanner-verified.** Keep the first session on a uniform phantom, record temperature and shim, and save each acquired MRD with its embedded protocol. Use the current scanner PPL/PPR bytes and preserve the checksums from the final build report.

## 1. Console acceptance and timing

Run one short single-slice scan with each version at 50-us and 25-us dwell, using ESP equal to the event-model minimum and then minimum + 1 ms. Also run v1.912 at ESP 13 ms / dwell 50 us to compare with v1.911. Use the approved test PPR and keep all fused-gradient geometry and angles at their validated settings.

**Pass:** the console accepts each model-accepted setting; no hang, rejection or missing/doubled echoes; measured scan duration differs from console prediction by less than 2 ms per shot; echo spacing is uniform. An excess of 5 ms per shot is a timing failure; 2–5 ms per shot requires investigation before proceeding. Record the actual dwell, ESP, TR, shot count and total scan duration.

## 2. Off-centre multi-slice phase

Use the October 10 K geometry (three 1-mm slices at −1.2, 0, +1.2 mm) on v1.82. For v1.912, that exact K spacing is below the new guard and must be rejected; use three 1-mm slices at centre and ±2.7575 mm (or the printed guard threshold), or test one off-centre slice with the same separation from the centre. Acquire a navigator-enabled b0 train and inspect each slice's echo phase. Include an additional off-centre protocol at ±5 mm if allowed by the planned FOV.

**Pass:** odd/even phase alternation on each slice is within ±5° of the centre-slice CPMG phase; no arc artefact or systematic phase ramp appears. The October 10 v1.81 baseline was about ±40° and ±30° in the two off-centre slices.

## 3. Minimum-spacing and slice crosstalk

For v1.912, acquire a three-slice b0 dataset at the computed minimum separation (1103 units / 2.7575 mm for the default 1-mm slice and 3000‰ slab) and a single-slice reference with otherwise identical parameters. Also verify that a request one scanner unit below the minimum (1102 units for that default protocol) is rejected before RF/ADC. Use the slab and tip-up widths stored in the PPR.

**Pass:** the below-minimum protocol reports the computed minimum and does not start; at the allowed minimum, the centre-slice b0 navigator and image interior are at least 95% of the matched single-slice reference after noise correction. Record all slice offsets and the exact printed threshold.

## 4. Shorter readout on v1.912

At 25-us dwell, use ESP at the computed minimum and compare with v1.911 at 50-us dwell / 13-ms ESP, matching b-values, slice, receiver gain and sample. Record navigator signal per echo, echo-8/echo-1, b1000/b0, image SNR and b6000 floor/rim.

**Pass:** the console accepts the reported minimum; echo spacing and scan duration match prediction within the timing tolerance in item 1; all echoes are present; high-b remains at the noise floor with no new rim or edge pathway. Treat signal/SNR differences as measured outcomes, not a presumed gain.

## 5. Effective-b sidecars

Reconstruct the October 10 seven-b scans A, C, B and D with the updated recon. Check that nominal `.bval`/`.bvec` remain unchanged and that `_beff.bval`, `_bmatrix.txt` and JSON fields are produced from the embedded protocol. Check the declared axis convention, echo convention, source and warnings. Repeat with calibration disabled and enabled only after the calibration file is reviewed.

**Pass:** model-generated echo-1 b traces reproduce the v1.8/v1.81/v1.91/v1.911 reference values within 0.5 s/mm²; the A/C/B/D effective-b ADCs agree with the October 10 analysis within 3%; unavailable sequence/model falls back to nominal b with a JSON warning and does not fail reconstruction. Do not interpret the source trace as a measured waveform.

## 6. Per-shot navigator and recon

Acquire one phantom scan at `nav_on=1` and one at `nav_on=2`, with matched b-values and geometry. Verify mode 2 uses total raw `NO_VIEWS=(ETL+1)×(1+N/ETL)` (153 for 128 imaging lines at ETL 8), while `views_per_seg` remains the imaging ETL. Reconstruct from the embedded protocol. Then run a motion/phase challenge with known per-shot phase variation before considering an in-vivo pilot.

**Pass:** mode 2 has one unencoded extra navigator echo per imaging shot plus the existing per-volume train, with zero phase-encode moment at the navigator centre; `nav_on=0/1` keeps the old layout. In the static phantom, the interior ROI signal from modes 1 and 2 differs by no more than `max(3%, 2× repeat-noise SD)`, with no systematic complex-phase shift; scan-time/TR increase matches the event-model prediction within 2 ms per shot. In the phase challenge, the correction recovers the uncorrupted image within 2% normalized RMS error; noise-dominated high-b shots automatically fall back to no correction and are flagged in JSON/QA output.

After the phantom checks pass, acquire a short in-vivo motion pilot and reconstruct the same MRD with correction off and on. Compare ghost-to-signal ratio in a preselected brain ROI, shot-to-shot dropout, and ADC. **Pass:** correction reduces ghost-to-signal ratio or dropout by at least 50%, preserves median ROI signal within 5%, and changes ADC by no more than 3%. If those thresholds are not met, retain correction off pending review.

## Record for every scan

Save the embedded PPR/MRD, sequence/PPR checksums, console messages, actual dwell/ESP/TR, scan duration, phantom temperature, shim/frequency offset, navigator phases and signal, reconstructed images, effective-b outputs, and any rejection. A scanner pass does not validate conditions that were not acquired.
