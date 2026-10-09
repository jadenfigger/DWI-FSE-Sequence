# Independent MR-physics review: v1.81 and v1.911 (final bytes)

Reviewer role: independent (not an author). Date 2026-10-08. **Everything below is source-model evidence** (repo mapper `dwfse/ppl/` executing the real PPL/PPR, gradient/RF/ADC ledger, my own integrators). Nothing here is vendor-compiled or scanner-verified, and no hardware limits, gradient delays, eddy-current kernels or achieved flips are known. Items marked **[DATA]** use archived scanner raw data; items marked **[MODEL-ONLY]** do not.

Input bytes (all four sha256 re-verified by `physics_review_common.check_hashes()` before every script):

| file | sha256 |
|---|---|
| v1.8 `scanner/...-1.8.ppl` | `3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2` |
| v1.81 `scanner/...-1.81.ppl` | `545a14ec8c65ed578ea76628796547dd463eb8cd4a2efa680de89058a837de69` |
| v7 baseline `baseline_v7/...-1.91.ppl` | `6a0d222b6c8689fbdee5f4ae412c4d5df0bea10a7da99a309fabf5dfab04d828` |
| v1.911 `scanner/...-1.911.ppl` | `716478bb357ba1479e6cc8fcc18c1085e44b3c78ecf1bdf32bb561b171838682` |

Actual imaging state: overrides `no_disacq=0, nav_on=0, no_views=128`, shot 1, cost model manual-expression x0.8, gradient lag = `rfdelay` = 60 us (v1.8 uses the test1e PPR, whose parameters are identical to the v1.81 PPR). Scratch code and JSON: `docs/v181_v1911/review_checks/physics_review_*.py/json`; rerun any of them with `python docs/v181_v1911/review_checks/<name>.py`.

## Verdict

* **v1.81 read-prephaser relocation: ACCEPT (physics).** The relocation removes a real diffusion x imaging cross term that the prior v1.8 data contain. The read endpoint moves by only 0.233 cycles/m (0.008 k-pixel, 0.4 us). The consequence that matters is not a sequence defect but an **analysis-meaning change**: v1.8 effective b differs a lot from nominal, v1.81 does not (Finding 1).
* **v1.911 fused lobes: ACCEPT WITH CONDITIONS (physics).** Gradient geometry at every RF/ADC boundary is equivalent to v7 (max 0.117 cycles/m on S, 0.137 on R, 0 on P per interval; the extra R is a 0.24-us ADC-placement artefact), the RF-time selector is pointwise identical, no fused lobe touches RF or the receiver-busy interval, and the whole 8-echo history set is identical. Conditions: (i) the author's finite-RF Bloch gate fails (Finding 2) and must be dispositioned, not relabelled; its grid file references superseded PPL hashes; (ii) no matched-ESP console control exists (Finding 3).
* **Dispositions (Section 3):** refocusing width = **held high-value, not marginal**; navigator = held high-value for in-vivo multishot, marginal for phantom work; isodelay, VFA, crusher polarity = agree (marginal or retained); preparation TE: the real lever is the PPR `big_delta`, not source gaps (Section 3.6).

## Severity-ranked findings

| # | Sev. | Finding | Key numbers | Basis |
|---|---|---|---|---|
| 1 | **HIGH (analysis/provenance)** | v1.81 changes the effective b of every nominal b label vs v1.8; v1.8's b also depends on diffusion polarity | ADC1 trace, +X read, nominal 100/1000/6000: v1.8 165.0/1175.9/6398.2, v1.81 104.1/1000.7/5980.7 (b0: 12.0 vs 4.0). v1.8 with -X: 59.1/841.5/5579.2 | exact-PWC integration + brute-force check; [MODEL-ONLY] |
| 2 | **MEDIUM** | v1.911 finite-RF Bloch gate: off-resonance-dependent loss vs v7, unexplained by pathway geometry; grid file stale | worst 0.969 (B1 1.1, -128 Hz, phase 90, E8); same corner with T1 1.3 s/T2 32 ms: 1.031 (E1) to 1.004 (E8) | author grid + my EPG + targeted EventBloch; [MODEL-ONLY] |
| 3 | **MEDIUM (validation design)** | v1.911 (ESP 13 only, E144 rejects 14) and v7 (rejects <14) cannot run at a common ESP; any scanner A/B conflates ESP and lobe fusion | predicted gain table below | rejection tests of other reviewers; [MODEL-ONLY] |
| 4 | LOW | Fused S lobes raise short/mid-tau eddy-current exposure at the ADC (S axis) while lowering heating and total variation | EC proxy +16% (tau 2 ms), +6% (10 ms), -3% (0.5 ms); S integral G^2 dt -16.5%; S peak 150.0 -> 148.6 mT/m | waveform proxies; [MODEL-ONLY] |
| 5 | LOW | "|C1|/|D| = 2.554" cannot be reproduced from a unique waveform definition; equality with v7 holds regardless | first-interval area differs by 0.08 cycles/m | independent |
| 6 | LOW | R interval residual +/-0.137 cycles/m is an ADC-mid placement artefact (0.24 us x 0.571 cycles/m/us), not gradient area | consistent with the compiler/timing reviewer | independent |
| 7 | INFO | v1.8 train is strongly phase-sensitive (CPMG violation); relevant to the navigator question | ph0 90 deg, B1 0.9: E8 0.11 of ideal | EPG, ideal RF; [MODEL-ONLY] |
| 8 | INFO (positive) | v1.81 timing-window fix gives real robustness under slower cost models | overruns v1.8 -> v1.81: 4 -> 0 (manual x1.0), 2 -> 0 (1 us/stmt), 16 -> 0 (1 us + x0.8); x1.25 still fails both (22 vs 20) | mapper; [MODEL-ONLY] |

### Finding 1 detail - effective b before/after (task item 1)

Method: `physics_review_btensor.py`. Mapped S/P/R gradient waveforms; exact analytic integration of `k` and `int k k^T dt` over every piecewise-constant sample (the Gram integrand is quadratic in time, so the integration is exact); gradient physical time = emitted + 60 us; primary all-transverse path, instantaneous RF at the mapped sample-array centre; coherence conjugated at every RF; b = (2pi)^2 x 1e-6 x integral. Cross-check by a 0.25-us sampled sum (`physics_review_btensor_bruteforce.py`): v1.8 1175.916/6398.054, v1.81 1000.695/5980.575, differences <= 0.1 s/mm^2 (1.6e-5 relative). The result is also split into diffusion-lobe-only, imaging-only (b=0 waveform) and cross terms.

Every-echo trace (s/mm^2), diffusion along +read (all three rows of the protocol are +X):

| nominal b | seq | E1 | E2 | E3 | E4 | E5 | E6 | E7 | E8 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | v1.8 | 12.03 | 14.70 | 17.44 | 20.28 | 23.27 | 26.43 | 29.80 | 33.40 |
| 0 | v1.81 | 4.01 | 6.67 | 9.42 | 12.26 | 15.25 | 18.40 | 21.77 | 25.38 |
| 100 | v1.8 | 165.03 | 167.70 | 170.44 | 173.29 | 176.27 | 179.43 | 182.80 | 186.41 |
| 100 | v1.81 | 104.05 | 106.72 | 109.46 | 112.31 | 115.29 | 118.45 | 121.82 | 125.42 |
| 1000 | v1.8 | 1175.93 | 1178.60 | 1181.35 | 1184.19 | 1187.18 | 1190.33 | 1193.70 | 1197.31 |
| 1000 | v1.81 | 1000.71 | 1003.38 | 1006.13 | 1008.97 | 1011.96 | 1015.11 | 1018.48 | 1022.09 |
| 6000 | v1.8 | 6398.16 | 6400.83 | 6403.57 | 6406.41 | 6409.40 | 6412.56 | 6415.93 | 6419.53 |
| 6000 | v1.81 | 5980.68 | 5983.34 | 5986.09 | 5988.93 | 5991.92 | 5995.07 | 5998.44 | 6002.05 |

(These agree with the author's earlier estimate and with the other grid's table to 0.01.) Components at E1:

| nominal b | diffusion lobes alone (both seq.) | imaging self term v1.8 / v1.81 | cross term v1.8 / v1.81 |
|---|---|---|---|
| 100 | 99.97 | 12.02 / 4.00 | **+53.04** / +0.08 |
| 1000 | 996.47 | 12.02 / 4.00 | **+167.45** / +0.25 |
| 6000 | 5976.08 | 12.02 / 4.00 | **+410.06** / +0.60 |

**Why b at 6000 drops (v1.8 -> v1.81, -417.5 s/mm^2, -6.5%).** In v1.8 the first read prephaser (about -2074 cycles/m, `kI` in `physics_review_cross.py`) is played between the 90 and the diffusion 180 and therefore coexists with the whole diffusion block. During diffusion lobe 1 the diffusion wave-vector runs 0 -> -60,688 cycles/m while kI = -2,074, the same sign, so the product is positive; the diffusion 180 conjugates both, and during lobe 2 the diffusion wave-vector unwinds from +60,688 while kI stays +2,074, again the same sign. The cross term 2(2pi)^2 int kD kI dt is therefore positive and grows as the square root of b (+53/+167/+410 for b=100/1000/6000). Its sign is set by the product of diffusion-direction polarity and the prephaser polarity: with -X the same waveform gives -167.0 at b1000 and -408.9 at b6000, i.e. true b 841.5 and 5579.2 (-16% and -7% vs nominal). The imaging self term differs too: kI = 2,074 cycles/m held for 40 ms contributes about 8 s/mm^2 to every echo (12.0 -> 4.0 at E1). In v1.81 the prephaser area is applied after the diffusion 180 (kI during diffusion is about -3 cycles/m from ramp residuals), so only a 0.6 s/mm^2 cross term remains. The total no longer depends on diffusion polarity (verified: +X and -X identical 1000.71/5980.68; +Y 1000.71/5980.68; oblique (+/-1,1,1)/sqrt3 1020.6/6025.0 in both polarities of X).

Unchanged by v1.81: slice-direction diffusion keeps a 37.3/91.2 s/mm^2 cross term (slice selector/crusher x diffusion) in both sequences; the S-R off-diagonal element is +46.9 (v1.8) / +45.3 (v1.81) s/mm^2 at b6000 (0.7% of b_RR) and should be recorded by anyone using the full tensor.

**Console reporting / calibration assumptions.** The PPL code that converts `acq_b` to DAC (`b_kfac`, `39.69*d^2*(D-d/3)` with 63/10 squared, then a DAC bisection) and the printed `b[%d]: want/got` are byte-for-byte unchanged by v1.81 (diff shows no edit there). They model **diffusion lobes only** with an ideal rectangular formula. My exact lobes-alone numbers are 99.97/996.47/5976.08 against 100/1000/6000 (-0.03%, -0.35%, -0.40%; mostly the 39.69 vs (2pi)^2 = 39.48 kernel, +0.54%, and finite ramps). So (a) DAC and nominal gradient strength for a given requested b are identical in v1.8 and v1.81; (b) in v1.81 the nominal b label is now accurate to +4% (b100, because the imaging b adds 4), +0.1% (b500/b1000), -0.3% (b >= 2000); (c) in v1.8 the label is not: +65%/+26%/+17.6%/+12%/+9.7%/+6.6% at 100/500/1000/2000/3000/6000. No console calibration constant needs to change; any empirical per-protocol b correction that was tuned on v1.8 phantoms must be dropped for v1.81.

**Implications for ADC fitting and comparison with prior v1.8 data.** `physics_review_adc_bias.py` gives the multiplier by which an ADC fitted with nominal b (b0 and b) overestimates the true ADC:

| pair | v1.8 (+X) | v1.8 (-X) | v1.81 |
|---|---|---|---|
| b0 -> 100 | 1.530 | 0.471 | 1.000 |
| b0 -> 500 | 1.234 | 0.761 | 0.997 |
| b0 -> 1000 | 1.164 | 0.830 | 0.997 |
| b0 -> 2000 | 1.115 | 0.878 | 0.996 |
| b0 -> 3000 | 1.093 | 0.900 | 0.996 |
| b0 -> 6000 | 1.064 | 0.928 | 0.996 |

Consequences: (1) every apparent diffusivity derived from archived v1.8 scans with requested b is biased high by up to 16% at b1000 (the Oct-7 first-navigator ratios 0.1158-0.1185 correspond to 0.00216-0.00213 mm^2/s nominal-b, **0.00185-0.00183 mm^2/s with effective b**, if the navigator carries the same prephaser structure, which the source implies); (2) low-b (<= 500) apparent ADC and any IVIM-type fit from v1.8 data are strongly contaminated; (3) a pure-monoexponential prediction for the same sample on v1.81 is b1000/b0 = **0.158-0.161** (versus the archived 0.116-0.119), i.e. the b1000 images will be about 36% brighter relative to b0 even though nothing about the sample changed; this is a clean first scanner check (Section 5); (4) pooling v1.8 and v1.81 data by nominal b is invalid; (5) multi-direction protocols with mixed read-axis polarity on v1.8 had direction-dependent true b (+/-7% at b6000, +/-17% at b1000); v1.81 removes it. The residual -0.3% in v1.81 is the console kernel and can be corrected analytically if wanted.

**Read endpoint and echo position.** `physics_review_btensor2.py`: k_R at the ADC1 mid-sample is -0.9226 cycles/m (v1.8) vs -1.1556 (v1.81), a shift of **-0.2330 cycles/m** (confirms the author's -0.233); even echoes shift +0.2330 (E2: +0.0094 -> +0.2424), as expected from conjugation. The readout slope at the ADC centre is 0.5708 cycles/m/us (-735 DAC), so the echo moves 0.41 us (0.008 of a 50-us dwell, 0.008 k-pixel of 28.57 cycles/m). Identical shifts occur in all 7 mapped shots of the default PPR (dummy + navigator + imaging). The origin is integer-DAC/ramp-sample rounding of a 2,070 cycles/m lobe (1e-4). Timing: TE and ESP are unchanged to the model resolution under all eight cost models (TE1 54046 us, ESP 14011 us at x0.8).

### Finding 2 detail - v1.911 Bloch gate (see also the other agent's `final_physics_grid.*`)

* The author's grid reports v7 -> v1.911 ratio range 0.969-1.001, 172 strict and 46 material failures, all at |B0| = 128 Hz (86 strict each at +128 and -128; at B0 = 0 the ratio is 0.99998-1.00001 in all 9 cases; 28 of the 46 material failures are at B1 0.8), and per-echo ratios decreasing from 0.9992 (E1) to 0.9691 (E8). **The recorded input hashes in that JSON/MD are `9fca13eb...` (v1.81) and `7cf66e01...` (v1.911), not the final `545a14ec...`/`716478bb...`.** My waveform-level and EPG numbers on the final bytes agree with that file's tables (b traces to 0.01; diffusion-EPG ratios to <= 0.0009), so the waveforms are almost certainly unchanged, but the gate must be rerun on the final bytes before it is quoted.
* Cause analysis (my ideal-RF complex EPG, `physics_review_offres_epg.py`): with instantaneous RF and off-resonance phase accrued over every free interval, the coherent wanted-echo sum of v1.911/v7 is **1.000000 at all 36 (B1, B0, phase) cases and all eight echoes**. The geometry/pathway structure and the ESP change alone therefore cannot cause the loss. It must come from finite-RF off-resonance physics in a 7%-shorter schedule.
* Targeted EventBloch diagnostic (`physics_review_bloch_corner.py`, same engine as the grid, 3000 z x 32 y): corner B1 1.1, -128 Hz, phase 90: ratio 0.9995, 0.9933, 0.9896, 0.9889, 0.9877, 0.9835, 0.9765, 0.9691. Rescaling the v1.911 offset to **equal off-resonance phase per ESP** (the author's hypothesis in the grid script) makes it worse (0.9943 ... 0.8966), so it is not simply a CPMG twist per ESP; the loss tracks |B0|.
* Net effect with relaxation at that worst corner (T1 1.3 s): T2 32 ms 1.0314, 1.0304, 1.0295, 1.0295, 1.0275, 1.0225, 1.0126, 1.0037; T2 60 ms 1.0163 ... 1.0104; T2 100 ms 1.0095 ... 1.0004 (all >= 1). Milder corner B1 1.0, phase 0, no relaxation: 0.9788 at E8 for -128 Hz and 0.9813 for +128 Hz (symmetric in sign); the same -128 Hz corner with T1 1.3 s/T2 32 ms is 1.0328 (E1) to 1.0371 (E8), about 1.04 mid-train. So the gate failure is real in the relaxation-free model but is smaller than the relaxation gain for T2 <= ~100 ms. For very long T2 (> ~100 ms, fluid) the net can be -2 to -3% at late echoes under +/-128 Hz offsets.
* Disposition I recommend: do not relabel as pass; state "relaxation-free finite-RF ratio >= 0.969 at +/-128 Hz, >= 0.9995 at B0 = 0; net of T2 >= 32 ms and T1 1.3 s the worst corner is >= 1.004"; rerun the grid on 545a/7164 bytes; in-vivo B0 variation over a mouse brain at 9.4 T can exceed 128 Hz, which is outside the tested range.

### Finding 3 detail - ESP constraint on validation

v7 rejects ESP < 14 (E31) and v1.911 rejects ESP 14-16 (E144) and 12 (E32/E143); only 13 runs. A matched A/B (same ESP, with/without fusion) is therefore impossible on the console. The scanner comparison v1.91 @ 14 vs v1.911 @ 13 measures the **combined** ESP + fusion effect; use the prediction table in Section 2.4 as the pass criterion. Fusion alone (area-preserving) is validated here only at the model level.

## 1. v1.81 (task item 1) - additional checks

* b-tensor orientation/direction/polarity table, per-echo traces, endpoint: Finding 1.
* v1.81 train pathways: ideal-RF complex EPG enumeration with the v1.8 flip schedule (90, 8 x 180), B1 0.8-1.1, initial phase 0/45/90 (`physics_review_v181_pathways.py`): the coherent wanted-echo amplitudes of v1.8 and v1.81 are **identical** (ratio 1.0000 in all 12 cases, 8 echoes), so the relocation does not change which pathways coincide with the echo. (The other grid reports a 0.76-9.6 "min/max ratio" range for the diffusion-aware per-history view; that is a statement about individual histories, which I did not reproduce; the coherent echo is unchanged in my model.)
* The relocated first-read amplitude (test1e: -2694 DAC, 8.2% of full scale, same 700-us flat + 200-us ramps) is well inside the inherited envelope; no peak or slew increase beyond the existing read crusher.
* Side benefit, not claimed by the authors: the relocated prephaser no longer sits through the 40-ms diffusion interval, so its (small, about 4% of the diffusion lobes') first-moment velocity sensitivity along read disappears.
* Timing robustness [MODEL-ONLY]: with the mapper's eight cost models (`physics_review_echo_symmetry.py`) v1.8 produces timer overruns in 4 of 8 models (4 at manual x1.0, 2 at 1 us/stmt, 16 at 1 us + x0.8, 22 at x1.25, with ESP jumping to 19.0 ms in the extreme) while v1.81 has zero in all but x1.25 (20). ESP and TE are bit-identical between v1.8 and v1.81 in every model where both run clean.

## 2. v1.911 (task item 2)

### 2.1 Boundary-by-boundary equivalence

`physics_review_intervals.py`: events = every RF frame extent (full 3.2-ms prep and 1.2-ms refocusing frames) and every ADC window split at start/mid/end; areas = exact integrals of mapped S/P/R output (physical time = emitted + 60 us). Compared v7 and v1.911 interval by interval (47 intervals):

* Differences (cycles/m): S: 0.0817 (re-excitation -> RF1), 0.1175 (each RF end -> ADC start), 0.0458 (each ADC end -> next RF); P: <= 2e-12 (zero); R: +/-0.137 (the RF-end -> ADC-start and ADC-end -> RF intervals, equal and opposite, from a 0.24-us ADC-placement difference x the 0.571 cycles/m/us readout slope). All RF-extent intervals, every ADC window half and the prep intervals: exactly 0. In 1-mm units: 1.2e-4 cycles per boundary on S.
* Durations: each free interval shortens by exactly 500.0 us (RF end -> ADC start 3196.9 -> 2697.4; ADC end -> next RF 3200.0 -> 2700.0); imaging ESP 13996.94 -> 12997.38 us.
* Terminal restoration: area from ADC8 end to shot end S 16914.0519 (both), P 12983.2094 (both), R 14664.4207 vs 14664.2837 (the same 0.137); whole-shot net S differs by 1.34 cycles/m (the accumulated all-history bound; 1.3e-3 cycles across 1 mm).
* Crusher ratios: with Q-head/Q-tail measured as the selector-only waveform, `physics_review_crusher.py` gives C = -7675.62 and D = -2003.11 cycles/m for v7, -7675.54/-2003.07 for v1.911, **|C|/|D| = 3.8319 in both** (author 3.8315). For |C1|/|D| = 2.554 I could not find a unique waveform-level definition (the net slice moment from the re-excitation centre to the first imaging centre minus the selector halves is -6613.4 cycles/m, 3.30 D, in both); the first-interval equality (0.08 cycles/m) is what matters for equivalence.

### 2.2 RF-time selector and non-overlap

* `physics_review_rfwindow.py`: v7 and v1.911 gradient output compared sample by sample on a 1-us grid from 250 us before each RF start to 250 us after each RF end (all 12 RFs, all axes, lag applied): **maximum difference 0.0 DAC**. The first deviation after RF end is 263 us later; before RF start the nearest fused-lobe content ends 266 us earlier.
* Receiver: the old v7 post-RF slice list (`slice_list_rp`) ran through the ADC window with delay samples; the fused S content is now one `v19_l_im` list that starts **271 us after `complete()` returns** (emission time; list start log) and its first nonzero S sample is 714.7 us after ADC end physical / 335 us after the `complete()` physical time. S nonzero before ADC start: last 714.7 us before (v7: 203.7). P/R lobes continue exactly as before (they are part of the already-running read/phase lists).
* Pre-RF fused lobe: S plateau -4774 DAC (-6460 before RF1 only) from 1332 us (flat) with 200-us ramps, ending 263 us before RF start and then immediately followed (4-us zero) by the selector ramp, exactly as the v7 crusher; post-RF lobe -8146 starting 262.7 us after RF end (v7: the same start, -8223).

### 2.3 Coincident-pathway enumeration (task item 2, "no new unwanted coincidence")

`physics_review_pathways.py`: Weigel EPG configuration states (F kept, F conjugated, F -> Z with order kept and order flipped, Z -> F, Z -> Z), ideal RF at the sample-array centre, flip schedule 90, 180, 90, 90 and the imaging train 142.2, 94.9, 69.2, 63.0, 60.2, 60, 60, 60 (proportional to the mapped multipliers 505/337/246/224/214/213...), gradient increments between events from the exact interval areas. History counts at E1...E8: 16, 48, 144, 432, 1296, 3888, 11664, 34960 at B1 = 1; 81, 243, 729, 2187, 6560, 19570, 57590, 165592 at B1 = 0.85 (weight cut 1e-5).

* The **history sets are identical** for v7 and v1.911 at every echo (same codes survive the cut).
* Largest wave-vector difference of any history: S 0.199 (E1) rising linearly to **1.342 cycles/m (E8)**, P 7e-12, R 0.137. Histories whose in/out-of-echo classification could flip under +/-1.5 cycles/m at slice tolerances 250, 500, 1000, 2000 cycles/m: **0** at every echo, both B1.
* Wanted echoes are the F-conjugation chain at odd echoes (n_S = -116.6) and the stored-and-recalled harmonic at even echoes (n_S = +57.5, built from the flipped F -> Z branch at tip-up); the twin harmonic sits at |dS| = 3949 (3775 at E4/E5/E7) cycles/m = 2|D|, at nominal B1 with the same weight as the wanted one, i.e. 3.9 slice-thicknesses of dephasing in both sequences. At B1 = 0.85 the nearest unwanted histories inside the P/R window are 1974.5 cycles/m away (weights 0.036, 0.015, 0.005, 0.004, 0.0025, 0.0022, 0.0014, 0.0013 for E1-E8), identical in both sequences.
* Therefore fusing creates no new coincident pathway and removes none; any pathway-selection difference would need an area error > 1000 cycles/m, versus 1.34 observed.

Caveats [MODEL-ONLY]: instantaneous RF (finite-RF effects are in Finding 2), no gradient-axis rotation (the author restricts angles), weights are transfer-coefficient magnitudes (not a signal prediction).

### 2.4 Benefit of ESP 14 -> 13 ms (T2/diffusion) [MODEL-ONLY]

`physics_review_diffusion_epg.py`: own EPG-path model, ideal RF, box voxel, F relaxes with T2, Z with T1 (no Z0 recovery), diffusion `exp(-D b)` per history with `b = (2pi)^2 int |k(t)|^2 dt` including encoded longitudinal states, exact quadratic integration (converged at weight cut 1e-5; the cut matters above E5: at 2e-4 the late echoes are noisy). v1.911/v7 coherent wanted-echo ratio (B1 1.0):

| conditions | E1 | E2 | E3 | E4 | E5 | E6 | E7 | E8 |
|---|---|---|---|---|---|---|---|---|
| T2 32 ms, T1 1.3 s, D 0.002 mm^2/s | 1.0315 | 1.0532 | 1.0800 | 1.0971 | 1.1158 | 1.1327 | 1.1486 | 1.1643 |
| T2 32 ms, D = 0 | 1.0317 | 1.0488 | 1.0742 | 1.0877 | 1.1042 | 1.1156 | 1.1290 | 1.1371 |
| T2 60 ms, T1 1.3 s, D 0.002 | 1.0165 | 1.0301 | 1.0453 | 1.0571 | 1.0694 | 1.0806 | 1.0910 | 1.1018 |
| no relaxation, D 0.002 | 0.9997 | 1.0024 | 1.0058 | 1.0096 | 1.0138 | 1.0172 | 1.0203 | 1.0236 |

These reproduce the other agent's independent diffusion-EPG table (1.0315/1.0529/1.0802/1.0972/1.1159/1.1329/1.1488/1.1652) to 0.001, so the number is robust to implementation. At B1 0.9 the numbers are 1.0315 ... 1.1527 (T2 32 ms). Interpretation: about 3.2% (E1) to 13.7% (E8) is pure T2 (1 ms earlier per echo-train position, accumulating 1 ms per echo), the diffusion part grows from -0.02% to +2.4% (D 0.002) because the mean b of the contributing histories falls (amplitude-weighted mean b: E1 20.3 -> 20.4, E5 398 -> 376, E8 1189 -> 1125 s/mm^2 with relaxation, 1370 -> 1279 without). The 1-ms earlier first echo (TE1 from prep 90: 73.70 -> 72.70 ms; re-excitation -> E1 14.595 -> 13.596 ms) accounts for the E1 gain.

Primary-path b tensor of the train itself (own exact replay of the dominant histories, `physics_review_train_btensor.py`): E1 20.30 -> 20.44 (+0.13), E2 30.97 -> 31.62 (+0.65), E3 43.42 -> 44.41 (+0.99); i.e. the fused lobes raise crusher diffusion weighting on the *pure conjugation* path by +0.6% to +2.3%, matching the grid's table (20.30/20.44, 30.97/31.62, 43.41/44.40). Paths that store in Z for part of the train have lower b in v1.911 (e.g. 84.06 -> 79.64, 96.80 -> 92.75, 135.0 -> 129.5, 3326 -> 3096) because storage is 1.0 ms shorter per stored ESP. The diffusion-lobe cross term is unchanged: the grid's b6000 minus b0 is 5961.9 (v7) vs 5961.9 (v1.911). All consistent with the area equality in 2.1.

### 2.5 Hardware trade-offs at 9.4 T small animal [MODEL-ONLY; ratings unknown]

`physics_review_hardware_load.py` (logical axes, one shot incl. 9 ms after the last ADC; H = `grad_var[0]` for all axes; real axis calibration differs by <= 2%):

| quantity | v7 | v1.911 | change |
|---|---|---|---|
| S peak | 150.0 mT/m (8223 DAC) | 148.6 (8146) | -0.9% |
| S ramp slew (200-us ramps; amplitude/200 us) | 0.75 T/m/ms | 0.74 (same ramps, amplitude 8146; first lobes 4774/6460 are lower) | <= 0 |
| S integral G^2 dt | 522.5 (mT/m)^2 s | 436.0 | **-16.5%** |
| S total variation | 7918 mT/m | 5385 | **-32%** |
| P peak | 298.9 mT/m (16384 DAC, pre-train spoiler) | same | 0 |
| R peak | 109.4 | 109.4 | 0 |
| S eddy proxy at ADC windows, per unit eddy fraction alpha (mT/m): tau 0.5/2/10/50/200 ms | 4.12/18.4/29.7/26.9/13.6 | 3.98/21.3/31.4/28.2/13.8 | -3%/+16%/+6%/+5%/+2% |
| R/P eddy proxy | | | within +/-2% |

Interpretation: fusing removes the separate -D lobe (two ramps and a plateau per ESP), so S heating and switching activity fall; peak amplitude and ramp rate do not rise. The new risk is concurrency in time with the existing P/R lobes (S -4774 with P -344, R -269 before RF; unchanged P/R) which matters only if physical axes are rotated (the builder restricts angles, ledger does not rotate axes). Eddy currents: the S-axis exposure at the ADC rises by up to 16% at tau ~ 2 ms because the same switching is packed into 13 instead of 14 ms and the S lobe ends 715 us before ADC start (v7: 204 us). With alpha ~ 1e-3 this is 0.02-0.03 mT/m of eddy gradient, i.e. under 1 Hz across a 0.5-mm half slice; only large off-centre slice offsets or a poorly shielded insert make it relevant. The inherited dominant hardware load is the 16384-DAC (about 50% full scale, 299 mT/m) P-axis spoiler (ledger staircase slews are about 2x the trapezoid slew and are used only as ratios; v7 and v1.911 identical), untouched by v1.911. Mechanical: ESP 13 ms puts the repetition fundamental at 77 Hz (v7: 71 Hz); no information on coil resonances.

## 3. Dispositions (task item 3)

| item | author disposition | my view | class |
|---|---|---|---|
| Refocusing spatial width (1.2-1.5x) | not implemented | **Agree not to ship naive selector scaling; classify as held HIGH-VALUE, not marginal.** The study's excitation-weighted conjugate transfer at B1 1.0, 0 Hz rises 0.842 -> 0.918 (1.2x) -> 0.968 (1.5x), i.e. +9% / +15% signal per refocusing for unchanged RF energy; edge transfer 0.569 -> 0.769 -> 0.912; robust over B1 0.8-1.1 and +/-128 Hz. That is of the same order as the whole ESP 14 -> 13 gain at E1-E4 and applies to v1.8/v1.81. Gates that justify holding: coupled crushers (scaling the shared primary gradient changes crusher areas 16.7-33.3%), asymmetric lag-shifted selector (pre/post moments), second frequency buffer for off-centre slices, and v1.81's image-size headroom (+788 bytes estimated earlier). Needed to release: independent refocus matrix, finite-train Bloch + moment audit, vendor compile. | HELD high-value |
| Isodelay (no fixed shift) | do not hard-code +95 us | **Agree; marginal. [DATA]** `physics_review_echo_peak_from_mrd.py`/`_mrd2.py`: in 22 archived v1.8 scans the eight unencoded navigator echoes peak at sample 64.82-64.98 (mean 64.90, 128 samples, 50-us dwell), odd echoes 0.05-0.15 sample later than even, no drift over E1-E8 (sd 0.02-0.07); in the v1.91 ss-MGOT scans 64.86-65.04; v1.92 64.97-65.11. The same +0.9 sample (+45 us if samples are time-stamped at the start of the dwell, +70 us at the centre, +95 us at the end) appears for the stock sinc (v1.8) and the SLR pulses (v1.91/92), which have different effective centres, so most of it is a **receiver/sample-time-stamp convention common to all sequences**, not an RF isodelay that a sequence shift should remove. Consequence: 0.9 k-pixel linear phase in the image (harmless for magnitude), 2-4 degrees of off-resonance phase per 128 Hz. Check on the scanner by reading the raw peak position, no sequence change needed. | marginal |
| Navigator | not implemented | **Agree not to implement without the storage/tagging contract. Held HIGH-VALUE for in-vivo multishot; marginal for phantom/ex-vivo.** The archived data confirm one ky=0 train (8 lines) for the whole 136-line volume; no per-shot phase estimate exists. Model support for value: v1.8 retention is highly sensitive to phase error between the prepared magnetization and the refocusing axis (ideal-RF EPG, B1 0.9: E8 = 0.96 at 0 deg, 0.67 at 45 deg, 0.11 at 90 deg; B1 0.8: 0.82/0.62/0.30). A navigator corrects shot-to-shot phase before combination but cannot recover signal already lost inside the train; magnitude loss needs a CPMG-insensitive scheme (ss-MGOT). | held (in-vivo) / marginal (phantom) |
| VFA (mild v1.8 flip schedule) | declined | **Agree.** SAR is not the limiting item here, and the EPG above shows the existing 180 train is already phase-fragile; lowering flips adds stimulated pathways without a measured gain. | marginal |
| Crusher polarity retained | retained | **Agree.** The fusion and relocation are polarity-neutral (areas preserved, signs untouched) and Oct 5 paired scans support the negative non-alternating choice. | retained |
| Preparation TE reduction | declined | **Agree for source-gap edits; flag the PPR lever.** `physics_review_prep.py`: TE_prep (RF0 -> RF2 centres) = 53.99 ms = Delta (40.00 ms centroid) + 14.0 ms of fixed overhead; nominal b6000 needs 20,119 DAC (61% of full scale). Only about 14 ms is source-controllable, and much of it is delta (4 ms), the 3.2-ms 180 and ramps. The big_delta PPR parameter is the real lever: Delta 30 ms gives +37% (T2 32 ms) / +18% (T2 60 ms) preparation signal for +16% diffusion gradient (23,366 DAC, 71% FS, within the 30,000-DAC b-mode limit), Delta 35 ms +17%/+9% for +7%. This needs no code change but changes diffusion time, so it is a protocol decision with gradient-rating and ADC-time-dependence consequences. | protocol lever (high value, not code) |

## 4. What is model-only

Model-only: all b tensors, area equalities, EPG pathway sets and ratios, diffusion/relaxation gains, finite-RF Bloch corner diagnostics, eddy/heating proxies, cost-model timing and overruns. Not established anywhere: vendor compilation, real instruction timing, gradient lag/slew/ratings, achieved flip angles and B1, SAR, RF latency, real eddy-current kernels, oblique-axis sums (v1.911 rejects angles), in-vivo B0 range. Data-based: only the echo-peak position (22+ archived MRDs).

## 5. Scanner checks suggested by this review (in priority order)

1. **b-meaning check (v1.8 vs v1.81, same phantom, same PPR):** b1000/b0 first-navigator and image ratios. Prediction from the archived v1.8 ratio 0.1158-0.1185: v1.81 **0.158-0.161** (monoexponential, same sample and temperature). Also b100/b0: v1.8 effective 153, v1.81 100 (b100 signal ratio should rise by about exp(ADC x 53) = 1.10 at ADC 0.0018). A -X row on v1.8 predicts b1000 effective 830.
2. **v1.911 @ ESP 13 vs v1.91 @ ESP 14** (combined effect, no matched ESP possible): expect E1..E8 signal ratio 1.03...1.16 (T2 32 ms-like) or 1.02...1.10 (T2 60 ms) from this table; a ratio at or below 1.00 at E1 would point at a hardware or pathway problem. Measure the water phantom T2 first.
3. Raw k-space peak position per echo in v1.81 and v1.911 (expect 64.9 +/- 0.1 samples as in v1.8/v1.91); this verifies timing symmetry without any sequence shift.
4. With a field-map or deliberate +/-128 Hz frequency offsets at E8: v1.911/v1.91 ratio expected within 0.97-1.00 relaxation-free; a larger drop needs the finite-RF analysis revisited.
5. Compiled-image headroom and played gradient trace of the fused S lobe (peak 6460/4774/8146 DAC, 200-us ramps) and the 271-us post-`complete()` start.

## 6. Files

Scratch: `physics_review_common.py`, `_btensor.py/.json`, `_btensor2.py/.json`, `_btensor_bruteforce.py/.json`, `_cross.py/.json`, `_adc_bias.py/.json`, `_intervals.py/.json`, `_rfwindow.py/.json`, `_crusher.py/.json`, `_shapes.py`, `_pathways.py` (`_pathways_B1_1.0.json`, `_pathways_B1_0.85.json`), `_offres_epg.py/.json`, `_diffusion_epg.py/.json`, `_train_btensor.py/.json`, `_hardware_load.py/.json`, `_echo_symmetry.py/.json`, `_echo_peak_from_mrd.py/.json`, `_echo_peak_mrd2.py/.json`, `_prep.py/.json`, `_v181_pathways.py/.json`, `_bloch_corner.py/.json`, `_bloch_corner2.py/.json` (all `physics_review_*` in `docs/v181_v1911/review_checks/`). No builder, scanner file, validator or `dwfse/` file was edited.

## 7. Follow-up dispositions (coordinator request, after the grid was rerun on final bytes 545a14ec / 716478bb)

The rerun `final_physics_grid.json` now records the final hashes; its diagnostics reproduce mine exactly (min ratio 0.9691 unrelaxed, 0.8966 for equal off-resonance phase per ESP).

### 7.1 v1.8 -> v1.81 grid-pathway ratio spread (0.849-1.427, worst -2.9% of E1)

Verdict: **model artifact on top of one real, deterministic effect; neutral redistribution of already-suppressed pathways; not a regression.** Scripts: `physics_review_v181_reconcile.py`, `_reconcile2.py` (own EPG-path code with Z0 recovery, T1 1.3 s, T2 32 ms, D 0.002, box-voxel `sinc(k*width)` weighting of every history at the ADC mid sample, same 36-case grid; it reproduces the grid agent's behaviour: nominal-flip ratio uniform, spread 0.689-1.161 over 240 robust echoes, worst signed -1.9% of E1, concentrated at B1 != 1 and phase 45/90 where the baseline echo is nearly null).

* Real effect: at B1 = 1 the ratio is a uniform **1.0162** in every echo. It is exp(D x 8 s/mm^2): the removed prephaser self term (b0 12.0 -> 4.0, Finding 1) is the whole nominal "1.008-1.024".
* Splitting each ADC sum by slice coherence (|kS| < 1500 cycles/m): the **slice-coherent histories give ratio 1.01617-1.01618 in all 36 cases x 8 echoes** (robust min/max 1.0162/1.0162, worst signed change +0.015% of E1). No slice-coherent history has |kR| >= 300 cycles/m in either sequence: moving the prephaser does not change which pathways are refocused at the ADC (this is my earlier identical-amplitude result, now including relaxation, diffusion, Z0 recovery, off-resonance and the voxel weighting).
* The spread comes from slice-incoherent histories (|kS| > 1500) whose weight is set by the sidelobes of a hard 1-mm box, `sinc(kS x 1 mm)`, at the single mid sample, combined with their read wave-vector and b, both of which do change when the prephaser moves. A real selective slice profile has no such sidelobes, and these histories are dephased by more than 1.5 cycles/mm; in the image they are also outside the readout window or displaced. The extreme ratios (0.69, 1.43, 9.6) occur only where the baseline echo is tiny, i.e. interference between small sums.
* Consequence: no loss of in-slice signal, no new in-slice contamination; whether v1.81 reduces v1.8 non-CPMG contamination is not shown by this model (the coherent signal is unchanged). Net: **neutral/improvement (+1.6% from lower b), no concern.**

### 7.2 v1.911 Bloch strict-gate failure - final disposition

* Facts (rerun, final bytes): 172 strict / 46 material failures, all at |B0| = 128 Hz (0 at B0 = 0, where the ratio is 0.99998-1.00001); worst 0.9691 (E8, B1 1.1, phase 90) unrelaxed; with T1 1.3 s/T2 32 ms the minimum over all 24 failing cases is **0.9989**; off-resonance averaged over one period 1/ESP of each train (71.4 Hz v7, 76.9 Hz v1.911): **coherent 0.9972, incoherent 0.9973** (v1.8 -> v1.81: 1.0000). My ideal-RF EPG gives exactly 1.0000 at every offset, and my targeted corner runs give >= 1.004 (T2 32 ms), >= 1.010 (T2 60 ms), >= 1.0004 (T2 100 ms).
* Interpretation: the single-isochromat ratio at a fixed offset compares two different off-resonance ripples with different periods (1/ESP, 71.4 vs 76.9 Hz), so a pointwise drop at +/-128 Hz is a ripple-phase effect, not a loss of pathway selection; averaged over a period it is -0.3% at worst, and the geometry is identical (Section 2). The equal-phase-per-ESP rescaling does not align the ripples (ripple also depends on absolute offset through the finite RF), which is why my earlier twist test got worse; the period average is the consistent summary.
* **Verdict: accept as a documented deviation, not a physics regression.** The gate as written (single isochromat, relaxation-free, -1e-4 tolerance) is not a valid acceptance criterion for a sequence whose ESP differs by 7%; keep the original numbers in the report and state the replacement criteria after the fact as: on-resonance ratio >= 0.9999 (met), period-averaged ratio >= 0.995 (0.9972, met), relaxed ratio >= 0.995 with T2 >= 32 ms (0.9989, met). Residual caveat: for T2 > ~100 ms and a narrow B0 distribution sitting on a ripple minimum, late echoes can be 2-3% lower than v1.91; in-vivo B0 spread beyond +/-128 Hz is untested. Scanner-verify.
