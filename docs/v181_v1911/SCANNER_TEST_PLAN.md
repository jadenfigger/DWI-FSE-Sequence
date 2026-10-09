# Prioritized scanner test plan: DW-FSE v1.81 and ss-MGOT v1.911

**These are source-validated candidates. They are NOT vendor-compiled and NOT scanner-verified.** Everything under "Prediction" below is a model prediction from the repository's source mapper, exact waveform integrals and conditional pathway models; the pass/fail thresholds are suggestions chosen to separate "model right" from "something is wrong", not vendor specifications. Stop at the first failed blocking item and report; do not scan in vivo with either candidate until Items 1-5 pass.

Final bytes (verify before testing, e.g. with `certutil -hashfile <file> SHA256`):

| File | SHA-256 |
|---|---|
| `FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl` | `545a14ec8c65ed578ea76628796547dd463eb8cd4a2efa680de89058a837de69` |
| `FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppr` | `ad82112ddfc7389a58caea6598cb5eb7583a271e71e62cd8c006190c52cdb159` |
| `FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl` | `716478bb357ba1479e6cc8fcc18c1085e44b3c78ecf1bdf32bb561b171838682` |
| `FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppr` | `b2976e7464367a7aa6b6b8e04765cc04a3fd85c0d2ec64c9c9a57963bf9635c2` |

Controls (do not modify): v1.8 PPL `3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2` with its own PPR; v1.91 = the v7 method-only build (PPL `6a0d222b6c8689fbdee5f4ae412c4d5df0bea10a7da99a309fabf5dfab04d828`, PPR `fc7f0218f5aaf7866e44ce65331a2f6c11526d0ce04f8e2e78f44dbb6cd0ebeb`). The workspace copy of `-1.91.ppl` is the older combined v6; confirm which build the console actually has before using it as a control.

## 0. Setup (before Item 1)

1. Keep original filenames (remove download suffixes such as " (1)"; the console compiler splits at spaces). The v1.81 PPR names `G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl`; the v1.911 PPR names the bare filename. Put each PPL where its PPR expects it, or edit nothing and enter the full path without quotes.
2. v1.911 only: the PPL loads six RF libraries from `g:\J_Figger\seqlib\`: `v19_slrprep90.seq`, `v19_slrprep180.seq`, `v19_slrtip90.seq`, `v19_slrelim90.seq`, `v19_reexc90.seq`, `v19_imaging180.seq`. They are byte-identical to those used by v1.91 (v7) and are included in the upload ZIP. If they are already installed, check the hashes (below) and do not overwrite; if not, copy them as new files, open each in the WavEd viewer and confirm a visible waveform. v1.81 uses stock libraries only. Never overwrite vendor libraries.

   | Library | SHA-256 |
   |---|---|
   | `v19_slrprep90.seq` | `ba1c47b36159676f3b1ede6be0166222a3115e29e8dd160d3f91d60d429d610e` |
   | `v19_slrprep180.seq` | `12893aa1c5b41b8e6b413d2c66309e1ec04be5ab0c183c68bbe77655863de432` |
   | `v19_slrtip90.seq` | `12011e69db23614590d9f1d8b7222d28667c49e54c2a387a7f30b130a584f6df` |
   | `v19_slrelim90.seq` | `14065908df72390a8032c1a0ebc50c60cd0281d18d9d82b03c9d50365b77c1f0` |
   | `v19_reexc90.seq` | `3c5c0b893c7568c72dbba2aa457ba73b7df2bd59e0e610c12437d13644688e29` |
   | `v19_imaging180.seq` | `b79da53484e0df66e7296db0896f0f73506a9b680b48779d3c1c4cc4db8f5cc9` |

3. Use the shipped PPRs. v1.81 PPR is the acquired test1e protocol (136 views, ETL 8, nav_on 1, ESP 14, b = 0/1000/6000, diffusion +X, `crush_amp` -2741, `diff_crush_amp` -5482). v1.911 PPR is the v7 PPR with `esp` 13 (64-row tables, b = 0/1000/6000). MRD-embedded protocols take precedence over stale adjacent PPRs when you analyse data.
4. For every A/B pair: same phantom, same temperature (record it), same coil, same positioning, same TX attenuation and receiver gain, same day, interleaved order (control, candidate, control) to track drift.

## Item 1 (BLOCKING): compile and load both sequences

Compile v1.81 and v1.911 with the console preprocessor/PPLC/Forth path used for v1.8 and v1.91, and load each with its PPR.

| Check | v1.81 prediction (model) | v1.911 prediction (model) |
|---|---|---|
| Fatal errors | none | none |
| Warnings | **11** W007/W008, same identities as the v1.8 compile (v1.8's own count is the reference: compile v1.8 on the same console and compare) | about **4**: 3 W007/W008 (`offset_frequency(fov_slice_freq+slice_freq_var)`, `IntToLong(slice_freq_var)`, `waittimer(templ1)`) plus possibly W003 for the unused label `pb_end` (v7 reference) |
| 20-message abort ("Too many errors") | must not occur | must not occur |
| E106 (far-scratch, about 147 forward gotos) | must not occur (21 forward gotos, v1.8: 145) | must not occur (18, as v7) |
| ".fth branch out of range" | must not occur (largest `if` body 369 nodes, same as v1.8) | must not occur (379, same as v7) |
| Program image | model estimate 56517 B versus v1.8 model 56664 B; **send the actual size of v1.8 and v1.81 images** so the real margin to 64K is known | model estimate 49626 B versus v7 48469 B (+1157 B); send the actual size of v1.91 (v7) and v1.911 |
| PPR load | `:PPL` line resolves; no table-length complaint | `:PPL` resolves; `acq_b` 64 rows accepted |
| RF libraries (v1.911) | n/a | all six visible in WavEd and loaded |

**Pass:** no fatal error; warning count equal to or below the predicted count (a count within the v1.8 / v7 reference counts is acceptable; any *new* warning text must be reported); image fits.
**Fail:** any fatal error, abort at 20 messages, E106, branch-out-of-range, or image overflow. Send the exact compiler text and stop.

Known fallbacks (use only if the specific message appears; do not edit timed statements blindly):

* **v1.911, `waittimer` argument rejected, or the terminal exit appears to hang** (the source passes the 16-bit-int variable `v1911_i_term_end` = 40000, which the signed 16-bit `int` stores as -25536 and relies on the controller reading it as unsigned, the same mechanism v7 uses for 40540 and 33075/33275): replace the last timer line of the terminal block, `waittimer(v1911_i_term_end);` (just before `goto v19_after_train;`), by the two lines `starttimer();` and `waittimer(12000);`. Model effect: shot time and `tr_min` unchanged, +2.4 to +6.4 us shift, no overruns. A what-if file with exactly this edit is in the repository (`docs/v181_v1911/review_checks/v1911_rereview_variant_split.ppl`, SHA-256 `808caec9e6ad042d7db68cb025373394e4570a0a6daa60d64a9ca1008c9cd2e7`; model-checked only, no independent approval). Report which was used.
* **v1.81, an empty-looking `if(mtc_on){ goto end; }` shell rejected:** report the line; do not delete it without telling us (it keeps untimed statement cost, and hence modeled timing, identical).
* **Anything else:** run the v1.8 / v1.91 control compile first to separate toolchain problems from candidate problems, then report.

## Item 2 (BLOCKING): validate-mode and guard spot checks (no RF is played)

Run with `validate=1` where available, then the normal path, and check that each rejection appears **before any RF** (no RF/gate click, no scan starts).

| Sequence | Edit | Expected message |
|---|---|---|
| v1.81 | defaults | validate prints a `Duration=...` value (repository default protocol: 126000; units as printed by the PPL) and does not reject |
| v1.81 | `mtc_on` = 1 | `V181 CEST/MTC not supported` |
| v1.81 | `flow_comp_on` = 1 with diffusion on | `V181 DWI requires flow compensation off` |
| v1.81 | very short ESP / TE | v1.8 text messages; for the narrow window `V181 ESP leaves no ... read balance` |
| v1.911 | defaults | validate prints a duration; normal run starts |
| v1.911 | `esp` = 14 | `V19 error E144` |
| v1.911 | `esp` = 12 | `V19 error E32` |
| v1.911 | `esp` = 10 | `V19 error E143` |
| v1.911 | any slice angle nonzero | `V19 error E146` |
| v1.911 | `rfdelay` 50 | `V19 error E140` |
| v1.911 | `crush_amp` = -8222 | `V19 error E142` (lattice; -8223 and -8219 accepted) |
| v1.911 | `tr` 150 ms | `TR too short, increase to 193 ms` |

**Pass:** all messages as listed. A candidate that *starts a scan* where a rejection is listed is a fail. Console message numbering for v1.911 is in `ERROR_CODES.md`.

## Item 3 (HIGH VALUE): v1.81 versus v1.8 effective b on a phantom

*Why:* v1.81 deliberately moves the read prephaser out of the diffusion pair; the played b changes. This is the cleanest check that the relocation was compiled and played.

*Protocol:* the shipped v1.81 PPR (b = 0/1000/6000) and the v1.8 control with the **same PPR parameters** (the test1e protocol; the repository's `experiments/FSE-DWI_10-05-2026_v18_test1e` PPR is the acquired control). Same water phantom and temperature, diffusion +X. Use the first-navigator echo or an ROI in the image interior, b0 and b1000, mean magnitude, with background-noise correction.

| Quantity | v1.8 (control) | v1.81 prediction | Pass | Fail |
|---|---|---|---|---|
| b1000 / b0 signal ratio, same sample (ADC about 0.00183-0.00185 mm2/s) | 0.116-0.119 (archived October 7 values; re-measure) | **0.158-0.161** | measured v1.81 / v1.8 ratio between 1.30 and 1.42 (predicted 1.36), and v1.81 within 0.150-0.168 | ratio near 1.0 (relocation not played or not effective), or below 1.2 |
| Apparent ADC (nominal b0 to b1000) v1.81 / v1.8 | | 0.86 (= 0.997 / 1.164) | 0.82-0.90 | outside |
| ADC computed with **effective b** (see below) | agreement between v1.8 and v1.81 within 3 % | | within 3 % | beyond 5 % |
| b6000 / b0 | background-level | background-level (unchanged, about 6.8-7.3 raw units first navigator) | same noise floor as v1.8 | visible object-shaped signal |
| b0 SNR | | unchanged (+0.8 % from lower b0 weighting; Bloch ratio 1.0000) | within 3 % of v1.8 | beyond 5 % loss |

Effective b used (diffusion +X, ADC1 trace): v1.8 b0/1000/6000 -> 12.0 / 1175.9 / 6398.2 s/mm2; v1.81 -> 4.0 / 1000.7 / 5980.7 s/mm2. Optional extra row (edit `acq_b` to add 100 and adjust `no_diff_acq` / experiment divisibility): b100/b0 should rise by about exp(0.0018 x 53) = 1.10 from v1.8 to v1.81 (effective b100 153 -> 100). Optional v1.8 row with diffusion direction -X predicts effective b1000 about 841 (polarity dependence that v1.81 removes). **Do not pool v1.8 and v1.81 data by nominal b.**

Also check in the same runs: echo peak position (Item 5) and that b0 image shading is not worse than v1.8 (expected equal).

## Item 4 (HIGH VALUE): timing windows, minimum TR and gradient lag

The mapper cannot see the real instruction costs. These checks look for the *symptoms* of a missed 5-ms timer period or an ignored gradient list.

| Window / item | Model margin | Symptom if wrong | How to check |
|---|---|---|---|
| v1.81 `waittimer(templ1)` = 32500 ticks window (relocation arithmetic now lives here) | 226 us at manual x1.0 (824 us at x0.8; first modeled overrun at x1.076) | one 5-ms period lost: shot 5 ms longer, TE/ESP shifted | Set TR to the minimum accepted (174 ms for the test1e protocol; 173 ms must be rejected) and 2 s; measure total scan time. **Pass:** scan time = TR x shots (x averages) within 0.2 %; **fail:** extra 5 ms (or multiple) per shot |
| v1.81 inherited `waittimer(8997)` ADC window | 595 ticks at x1.0 | same | as above; same fail signature |
| v1.81 `waittimer(32750)` matrix window | about 11000 ticks of slack | matrix not ready | image artefacts, missing slice lobe |
| v1.911 terminal `waittimer(28000)` window (create matrix + 100-us caldelay + SetList) | **161 us** (26389-26469 of 28000 ticks across 8 cost models) | the terminal -D lobe and 40000-tick exit slip one 5-ms period: shot 5 ms longer; terminal moment still correct | Set TR = 193 ms (192 must be rejected): scan time = TR x shots within 0.2 % |
| v1.911 terminal exit `waittimer(40000)`; 16-bit note | n/a | hang or very short/long exit | Item 1 fallback |
| v1.911 terminal matrix timing | create call lands 168.8-176.8 us after trailing P/R lobes end (about 109 us with the 60-us lag); matrix ready 168.4 us before terminal start | slice-lobe or P/R lobe corrupted at the shot end | image quality at the last echo / ghosting; compare high-b background to v1.91 |
| Gradient lag (`rfdelay` 60 us) and "SetList on active channel" | in the mapper stress mode where a 60-us lag extends list activity: v1.8 shows ignored lists in all 8 cost models, v1.81 in 3 of 8 (flat 0 us, 0.5 us, manual x0.8), v7 in all (13 per shot), v1.911 in all but only 5 per shot, all in the inherited preparation block (none in the fused train); with the lag applied in the ledger both candidates show none | a gradient lobe silently dropped: echo shift, phase ripple, ghosts, odd/even asymmetry | Item 5 (echo peak per echo, odd/even), b-value check (Item 3) |

If a scope or the console's event trace is available, the highest-value single measurement is the played time of: last imaging RF end to first S-lobe sample, ADC start to end, and ADC end to the following S-lobe start, compared with the model values in `FINAL_REPORT.md` section 6. Without a trace, use the scan-time test above.

**What to send for any failure:** exact TR used, measured scan time, number of shots/averages, console messages.

## Item 5 (HIGH VALUE): echo centring and symmetry (both sequences)

Read the raw k-space (MRD, 128 samples, 50-us dwell, even-sample convention index 64) and locate the echo peak per echo in the navigator (unencoded, ky = 0) lines.

| Check | Expected (archived v1.8 / v1.91 data) | Pass | Fail |
|---|---|---|---|
| Peak sample, E1-E8, each sequence | 64.9 +/- 0.1 (v1.8: 64.82-64.98, mean 64.90; v1.91: 64.86-65.04; v1.92: 64.97-65.11) | within 64.7-65.2 | outside, or drift of more than 0.15 sample across E1-E8 |
| Odd minus even echo peak | 0.05-0.15 sample (odd later) | at or below 0.2 sample | larger, or reversed with drift |
| v1.81 vs v1.8 peak shift | -0.233 cycles/m read endpoint = 0.41 us = 0.008 sample | below 0.05 sample | above 0.2 sample |
| v1.911 vs v1.91 | no sequence shift predicted; the +0.9 sample is a common receiver/time-stamp convention | within 0.15 sample | larger |

Do not apply the historical +95-us shift; the fitted whole-train peak depends on grid and B1/B0 and is not a universal RF isodelay.

## Item 6 (HIGH VALUE): v1.911 (ESP 13) versus v1.91 (ESP 14): signal and b

*Confound that cannot be removed:* v1.91/v7 rejects ESP < 14 and v1.911 accepts only ESP 13, so the comparison measures **ESP and fusion together**. Fusion alone (area-preserving) is validated here only at the model level. A matched-ESP control would need an ESP-14 variant of v1.911 (offered, not built).

*Protocol:* v1.91 (v7) PPR and v1.911 PPR otherwise identical (ETL 8, b = 0/1000/6000, crushers -8223 / -5482). Same phantom, gains and temperature; interleave 91 / 911 / 91. Measure the phantom T2 independently first (stock CPMG FSE at the same temperature), and record T1 if available.

*Prediction:* coherent wanted-echo ratio v1.911 / v1.91 (instantaneous-RF EPG with T1 1.3 s, D 0.002 mm2/s, B1 = 1):

| Echo | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| T2 = 32 ms | 1.031 | 1.053 | 1.080 | 1.097 | 1.116 | 1.133 | 1.149 | 1.165 |
| T2 = 60 ms | 1.017 | 1.030 | 1.045 | 1.057 | 1.069 | 1.081 | 1.091 | 1.102 |
| No relaxation (diffusion only) | 1.000 | 1.002 | 1.006 | 1.010 | 1.014 | 1.017 | 1.020 | 1.024 |

Timing alone (pure T2): the echo n is (n x 1.0 ms) earlier, so ratio about exp(n ms / T2). The model is conditional (instantaneous RF, no slice profile, B1 = 1); the finite-RF/phantom result can differ by several percent.

**Pass:** E1 ratio >= 1.00 (within noise, 1 sigma); ratios increase monotonically over E1-E8; E8 >= 1.03 for phantom T2 <= 100 ms; measured ratios between the "no relaxation" row and the row for the measured T2 (allow +/-3 percentage points).
**Investigate (possible hardware or pathway problem):** E1 ratio <= 1.00 clearly (more than 2 sigma below), or non-monotonic, or E8 below 1.0.
**Also compare (same runs):** b1000/b0 (nominal b-values are within 0.15 s/mm2 at E1: 1014.55 vs 1014.68 trace) should agree within 3 % between 91 and 911; b6000 images should stay at background level (same noise floor); shading no worse than v1.91 (v1.91 smoothed interior b0 variation 5.8 %, b1000 5.6 %); apparent decay constant `-(E8-E1)/ln(S8/S1)` should lengthen versus v1.91 (v1.91 about 120 ms at ESP 14 on the October 7 phantom).

## Item 7: off-resonance check (v1.911)

*Why:* the finite-RF Bloch strict gate failed at |B0| = 128 Hz (172 strict / 46 material failures; worst ratio 0.969 at E8, B1 1.1, phase 90); it was dispositioned as a documented deviation, not as a pass (`FINAL_REPORT.md` section 9). This test checks the post-hoc replacement criteria.

*Protocol:* repeat the Item 6 pair at centre-frequency offsets of 0 and +/-128 Hz (console frequency offset), same transmit settings, E1-E8.

| Criterion | Prediction | Pass | Fail |
|---|---|---|---|
| On resonance v1.911 / v1.91 | per Item 6 | per Item 6 | per Item 6 |
| Ratio at +/-128 Hz relative to ratio at 0 Hz (each echo) | 0.97-1.00 relaxation-free (E8 worst 0.969); with relaxation T2 >= 32 ms about 0.999 or above; period-averaged 0.997 | >= 0.97 for every echo and both signs | below 0.95 at any echo |
| Long-T2 fluid (> 100 ms) at a ripple minimum | late echoes can be 2-3 % lower than v1.91 | within 3 % | beyond 5 % |

Optional: v1.81 versus v1.8 at +/-128 Hz: predicted ratio 1.000 (Bloch), pass within 2 %.

## Item 8: RF calibration, SAR and gradient checks

* **RF:** no RF library, RF multiplier or RF frequency logic was changed in either candidate; RF energy per shot is unchanged. Re-run the standard RF/power calibration for the six v19 frames per `docs/v19/rf_install_calibration.md` (achieved flip angles, B1 maps, SAR are unknown here). Check the console's SAR/power estimate against the controls at the same TR. Average power at minimum TR rises about 3 % for v1.911 (193 versus 199 ms) and falls about 0.6 % for v1.81 (174 versus 173 ms); at an unchanged TR it is unchanged.
* **Gradients:** v1.911 fuses slice-axis lobes: S peak 8146 DAC (v7: 8223), ramps 200 us, first/pre/post amplitudes about -6460 / -4774 / -8146 DAC, played concurrently with P/R lobes (P up to 16384 DAC spoiler unchanged). Watch for gradient amplifier or thermal warnings that the controls do not show. S-axis integral G^2 dt is 16.5 % lower, total variation 32 % lower, but the model eddy-current proxy at the ADC is +16 % at tau about 2 ms (alpha about 1e-3 gives under 1 Hz across a half slice). Compare slice-profile/ghost quality against v1.91 on a phantom at the same slice offset (centred slice only is allowed).
* **v1.81:** first read prephase amplitude -2694 DAC (8.2 % of full scale) in the first read-list prelude; SAR/gradient demand otherwise unchanged.

## Item 9 (optional, protocol only): preparation delay

No code change. After Items 1-6 pass, `big_delta` 30 ms (from 40 ms) in the ss-MGOT diffusion preparation is predicted to raise preparation signal by about +37 % (T2 32 ms) / +18 % (T2 60 ms) at the same b, with +16 % diffusion gradient (b6000: 23,366 DAC = 71 % of full scale versus 20,119 DAC = 61 %); 35 ms gives +17 % / +9 % for +7 % gradient (21,561 DAC). It changes the diffusion time (check ADC time-dependence) and the gradient-limit headroom is unknown. Use `validate=1` first (E30 or E48-E52 may reject). Not run through the mapper.

## What to send back

1. For each file you installed: the SHA-256 you computed, and the control (v1.8, v1.91) hashes.
2. Compiler/PPLC/Forth output for v1.8 (control), v1.81, v1.91 (control) and v1.911: full text of warnings, any errors, program image size.
3. Validate-mode outputs and the exact rejection messages from Item 2.
4. MRD files for Items 3, 5, 6, 7 (the MRD-embedded protocol is authoritative) plus the PPR used, the scan counters, TX gain / attenuation, receiver gain, coil, phantom, and temperature.
5. Measured scan times against TR for Item 4 (and any scope or event-trace capture).
6. SAR/power estimates and any gradient-system warnings.
7. Anything unexpected on the console, including a candidate scan that starts when a rejection was predicted.

## Decision rules

* Items 1-2 fail: stay on v1.8 / v1.91; send compiler output. Fallbacks above first.
* Item 3 fails (ratio near 1.0): the relocated prephaser is not being played as modeled; do not use v1.81 for quantitative diffusion; send raw data and the played gradient trace if available.
* Items 4-5 fail: possible missed timer period or ignored gradient list; do not use in vivo; send timing evidence.
* Item 6 fails (E1 ratio at or below 1): possible hardware or pathway problem; do not adopt v1.911 for signal-limited work.
* Item 7 fails: restrict v1.911 to sites with B0 spread under the tested range, or revert to v1.91.
* Otherwise proceed to phantom robustness runs and only then in vivo, keeping the controls available for return-to-baseline scans.
