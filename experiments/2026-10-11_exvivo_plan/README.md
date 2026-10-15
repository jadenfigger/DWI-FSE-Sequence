# October 11: rat brain in PBS, v1.82 and ss-MGOT v1.912

All protocols use **35 mm FOV**, standard orientation, **one average**, ETL 8, 1-mm slices and the full train crusher (`-8223`). Each PPR has its own identically named experiment folder. The PPL path is `G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-<version>.ppl`. Install/compile the exact new PPL files there before loading these PPRs; the v1.912 RF libraries are unchanged from v1.911.

Slice spacing below means **centre-to-centre separation**. A 2.4-mm separation between 1-mm slices leaves a 1.4-mm gap between their nominal edges.

**Planned acquisition time: 39.3 minutes with the 256×256 final scan, or 34.0 minutes with its 128×128 alternative.** The two conditional off-resonance scans add 42 seconds. These are source duration predictions, including four dummy trains per volume. Loading, RF calibration, shimming, guard checks and operator pauses are additional. TR covers the entire automatic slice batch; three slices do not triple the listed duration.

The working assumption is a fixed brain in PBS, as in the earlier ex-vivo plan. Record fixation history and actual sample/bore temperature. Preserve the surrounding PBS in the images: it supplies the isotropic ROI needed to distinguish gradient-axis errors from brain anisotropy. Avoid bubbles near either ROI. Calibrate RF/receiver settings on this sample and hold them fixed within matched comparisons; the PPRs retain previous calibration fields as starting values, rather than inventing a new coil calibration.

## Run order

First compile/load A and B without acquiring. Check the three intentionally invalid PPRs **W, X and Y** in console validation: they must reject before acquisition. Return to the good protocols before scanning.

Then run **A → B → C → D → AB → AC → E → F → G → H → I → J → M → N → K → L → O → P → Q → R → S → T → U → V**. Insert Z/AA after R only if the common-frequency detuning procedure is available. **V is last.** If brain SNR is insufficient for the finer matrix, run **AD instead of V**, never both as part of this budget.

| Tests | Purpose | Acquisition time |
|---|---|---:|
| A / B | Each new PPL at 20 kHz: b0/5/10/20/100/1000/6000 along +x; low-b E1 defect, tissue signal and high-b PBS floor | 2.45 min each |
| C / D | Each PPL: b10 reference, ±x/±y/±z at b500 and b1000, repeated b10 reference | 4.90 min each |
| AB / AC | b1000 along `(577,577,577)` on each PPL; exercises simultaneous diffusion axes before future 12/36-direction scans | 0.35 min each |
| E / F | 40-kHz minimum ESP: v1.82 11 ms / v1.912 10 ms; b10/1000/6000, nav1 | 1.05 min each |
| G / H | 40-kHz minimum ESP + 1 ms: v1.82 12 / v1.912 11 ms; b10 | 0.35 min each |
| I / J | 20-kHz minimum ESP + 1 ms: v1.82 15 / v1.912 14 ms; b10 | 0.35 min each |
| M / N | Single-slice nav2, matched to E/F, b10/1000; navigator and crosstalk references | 0.70 min each |
| K / L | Three-slice nav2 b0/10/1000: v1.82 K-style ±1.2 mm / v1.912 minimum spacing ±2.7575 mm | 1.05 min each |
| O / P | Three-slice nav2 at ±5 mm, b10; larger-offset RF phase check | 0.35 min each |
| Q / R | Δ30 ms / TE44 ms, 40 kHz, minimum ESP, nav2; b10/1000/6000 | 1.05 min each |
| S | v1.82 ±2.4-mm gap, b10; wider-gap crosstalk check before the final pilot | 0.35 min |
| T / U | Short b10/1000 drift repeats of A/B | 0.70 min each |
| V | Final v1.82: 256×256, three slices at −2.4/0/+2.4 mm; three directions per shell | 12.33 min |
| AD | Alternative final v1.82 at 128×128, same slices/shells/Δ/average count; replaces V | 7.00 min |
| W / X / Y | Deliberate spacing / ESP guard rejection checks | No acquisition |
| Z / AA | Conditional v1.912 global off-resonance −128/+128 Hz, b10 | 0.35 min each |

Detailed parameters, folder names and volume order are in [run_order.csv](run_order.csv) and [manifest.json](manifest.json). `protocol_notes.json` inside each experiment folder records that PPR's purpose and checksum.

This schedule follows the unresolved questions in the [October 10 scanner report](../../docs/physical_scanner_experiments_2026-10-10.md) and the [new-sequence test plan](../../docs/v182_v1912/SCANNER_TEST_PLAN.md): A/B cover the low-b reference and first tissue comparison; C/D cover the missing negative-z calibration; E–J and Q/R cover bandwidth, timing and shorter diffusion preparation; K/L/O/P/S cover off-centre phase and spacing; M/N qualify the new per-shot navigator layout; T/U provide the missing drift repeat; Z/AA cover off-resonance conditionally. The stronger crusher is retained because the October 10 weaker-crusher scan increased unwanted high-b signal. The earlier archive/sidecar and synthetic phase-correction checks were completed during sequence development. A controlled motion challenge remains for the subsequent in-vivo/phantom session; today's static brain measurements cannot answer that question.

The numerical thresholds below are prospective acceptance targets. Record the measured outcomes before deciding whether either sequence is ready for tomorrow's comparison.

## What to measure

**A/B: b0 and real tissue.** Inspect navigator echoes separately. October 10 v1.81 had an approximately 4.4% E1 deficit and 6–10° phase error at b0. Today's low-b sweep tests whether b5/10/20 suppress it. Adopt b10 as the low-b reference only if its E1 behavior is clean; do not assume b10 is literally zero. Fit with the actual effective b difference and check echoes 2–8 as well as the centric image. High-b brain signal is allowed and expected to depend on the specimen; assess unwanted high-b rim/floor in **PBS**, not by demanding that the brain disappear.

**C/D/AB/AC: ADC and b verification.** Use a common interior PBS ROI away from brain edges and bubbles, noise correction, and effective b-matrix traces. The six signed axes distinguish polarity-sensitive cross terms from multiplicative axis errors. Compare each signed pair and fit all available low-b points; the geometric mean of a ± pair suppresses its odd cross term. Record the nominal and modeled effective ADCs separately. Target residual effective-ADC disagreement across PBS axes/versions below 3%; 3–5% warrants repeat/calibration review and above 5% is a quantitative calibration failure. Compare only points with adequate PBS signal; brain-direction ADCs can differ because the tissue is anisotropic.

The [predicted b table](effective_b_predictions.csv) comes from these actual PPRs, not the older seven-b lookup. For example, C at nominal b1000 predicts +z/−z traces about 1038.09/963.51 s/mm²; D predicts 1066.71/962.64. The ss-MGOT z cross term is therefore not assumed equal to v1.82's. Source predictions are **not measured gradient waveforms**. Isotropic PBS permits relative axis/polarity checks; absolute b-scale calibration still requires independently known PBS/reference diffusivity at measured temperature. Unknown fixed-brain ADC cannot supply that reference. Do not create an empirical calibration simply by forcing brain ADCs to agree.

**E–J: timing, bandwidth and echoes.** A/B are the 50-µs minimum-ESP cases; E/F are the 25-µs minima. G–J add one ms. Preserve all navigator echoes and measure total duration, shot count and echo-peak location. Target timing agreement within 2 ms per shot; a systematic additional 5 ms per shot indicates a missed timer period. Inspect echo-to-echo timing uniformity and odd/even peak shifts. At the same 128-point geometry, compare early/late brain signal and image sharpness against A/B, allowing the bandwidth noise increase. All minimum-ESP values are source predictions until these console runs accept them.

**M/N versus E/F: per-shot navigators.** Match b10 and b1000, slice, gains and timing. Reconstruct once with per-shot correction off, then with automatic constant+linear correction. Static brain/PBS interior signal should agree within `max(3%, 2× repeat-noise SD)` and show no new ghost/phase pattern. Mode 2 must retain the volume train and have nine raw echoes per ETL-8 shot. Its final echo is the shot navigator. Low-quality/noise-dominated navigators must fall back and be recorded in QA. These static measurements qualify layout and image preservation; they do not establish immunity to in-vivo motion.

**K/L/O/P/S: multi-slice phase and crosstalk.** Compare each outer slice's odd/even navigator phase with the centred slice, preferably at b10; require agreement within ±5° and no new arcs. Inspect b0 separately so its inherited E1 defect is not mistaken for an offset problem. Compare the centred b10 signal with M/N: aim for at least 95% retention at the spacing intended for use. K deliberately revisits the close 1.2-mm gap and may still show crosstalk even if phase is fixed; do not choose that gap merely because phase looks correct. S tests the 2.4-mm v1.82 pilot gap. L tests v1.912's 2.7575-mm default-thickness guard boundary. O/P test larger offsets, not continuous whole-brain coverage.

**Q/R: shorter diffusion preparation.** Compare with M/N at b10/1000 and with E/F at b6000, noting the nav-mode difference for the latter. Measure brain SNR, train decay, high-b PBS contamination and navigator quality. Δ40→30 changes diffusion time, so tissue ADC need not stay unchanged. Use effective b for each protocol. The same small-b reference and high-b scanner acceptance must work on both sequences before considering the next day's comparison.

**T/U: drift.** Compare b10 navigator/image signal and b1000/b10 with A/B. Aim for less than 3% drift after noise correction. Record temperature changes. A failed drift test makes between-block ADC comparisons uncertain.

## Final v1.82 pilot

V uses **35 mm FOV, 256×256 (136.7 µm in-plane), 1-mm thickness, three slices at −2.4/0/+2.4 mm, TR2000 ms, TE44 ms, Δ30 ms, δ4 ms, one average and nav2**. There is one b10 reference and **three positive scanner-axis directions (+x/+y/+z) at each shell b1000, b3000 and b6000**, ten volumes total. This is a protocol pilot for the later 12/36-direction, multi-average, multi-Δ study; three directions do not fit a full diffusion tensor, and three spaced slices are not whole-brain coverage.

At 256 readout samples and 25-µs dwell the readout is 6.4 ms, so V uses ESP14 ms rather than the 128-point ESP11 ms. Its raw-view count is **297**; the imaging matrix remains 256. Its phase-gradient calibration is scaled using the **264 logical views** (256 imaging + 8 volume-nav), not the 297 stored rows. Keep the supplied counts/calibration together when loading; verify the console still displays 35 mm FOV. The 128-matrix AD alternative has the same shells, three directions, single average, single Δ and spacing, but 273.4-µm pixels, ESP11 ms and 153 raw rows. It trades resolution for signal and a shorter acquisition. Select the final pilot after inspecting Q and S; the finer matrix is not guaranteed to win for this specimen at one average.

Use V/AD only after the relevant timing, small-b, navigator and spacing checks are satisfactory. This is a candidate optimized around the current source constraints, not a claim that ex-vivo or in-vivo performance has already been established.

## Guard and off-resonance details

- W is intentionally below the ss-MGOT spacing guard: ±1102 units must print minimum separation 1103 and E148 before acquisition.
- X requests v1.82 ESP10 at 25 µs: it must print an 11-ms minimum and reject.
- Y requests v1.912 ESP9 at 25 µs: it must print a 10-ms minimum and E147.
- Z/AA have the same stored centre-frequency settings as R. The real measured Larmor frequency is not known when generating a PPR. To perform those tests, record the on-resonance frequency and **manually shift the common transmit/receive centre** by −128/+128 Hz on the console, without automatically retuning away the offset. `rec_freq` is a receive-only offset and is intentionally zero; changing it alone is not an RF off-resonance test. Compare navigator echoes with R's b10 volume, restore the centre afterward, and flag any loss above 5% after noise/normalization review. Omit Z/AA if that procedure is unavailable; do not interpret identical unshifted PPRs as an off-resonance experiment.

Save the MRD and its embedded protocol in each named folder. Record actual order, temperature, fixation, shim/common frequency, RX/TX/RF calibration, console edits, compile/guard messages and measured acquisition durations. Reconstruct using the embedded protocol and preserve nominal `.bval/.bvec` alongside `_beff.bval`, `_bmatrix.txt`, JSON provenance and shot-navigator QA. Before tomorrow's in-vivo comparison, review today's actual results; a static ex-vivo run cannot qualify motion robustness or replace that comparison.

## Reproduce and inspect

`make_pprs.py` regenerates the PPRs/manifest. `check_pprs.py` checks acceptance, rejection, timing and raw storage through the existing event model; [validation.json](validation.json) records the results. `effective_b_predictions.py` generates [effective_b_predictions.json](effective_b_predictions.json) and the per-volume CSV. Neither script vendor-compiles the PPL or measures the played gradients.

**Final source checks passed:** all 30 PPRs match their generated bytes and recorded hashes; 99 acquisition-volume rows map successfully at nominal costs; W/X/Y reject before RF or ADC. One stress row each for K/L/Q/R/V passed all eight cost models, including V's +z b6000 row. No hard timer/list/matrix hazards were found, appended navigator PE stayed within tolerance, and the largest ADC midpoint error was 15.3 µs against a 25-µs limit. Scanner-reported source durations match the schedule, and both PPL hashes stayed unchanged. The effective-b table contains 70 predicted volumes across ten calibration/pilot protocols, including both final-scan alternatives. Console compilation and today's measured results remain the scanner checks described above.
