# DW-FSE (twoTE-1.6) → PyPulseq

Files

| file | what |
|---|---|
| `dwfse_ppl_twoTE_1_6.py` | generator. `python dwfse_ppl_twoTE_1_6.py [--reduced]` |
| `validate_dwfse.py` | Step-5 checks. `python validate_dwfse.py --grad-delay 0 --full` |
| `dwfse_full.seq` | full protocol, 3 slices, 2 volumes, 4 dummy TRs, 28.0 s |
| `dwfse_reduced.seq` | centre slice, b = 6000 row, one imaging shot (32 echoes), one 2 s TR |
| `validation/` | reports and plots for gradient delay 0 and 60 µs |

Citations: `PPL:n` / `PPR:n` = line numbers in the .ppl / .ppr; `var_20`, `m3040_15`, … = the .pph files; `MAN` = EVO manual.

---

## Step 1 – Branch resolution

| parameter | PPR value (line) | branch it selects | PPL lines |
|---|---|---|---|
| diff_on | 1 (268) | DWI path everywhere: te_eff = 1, te = FIRST echo, esp = train spacing; tcrush1 = diff_tcrush; diffusion lobes played; first-180 list `slice_180_refocus_diff` | 803-833, 1321, 1756-1770, 2137-2177, 2369-2374, 2435-2461, 2485, 2541-2553, 2645, 2694-2695, 2729-2771, 2825, 3085-3092, 3467-3475, 3503-3526, 3541-3542, 3603-3622, 3644-3677, 3806-3810 |
| views_per_seg (ETL) | 32 (8) | multi-echo train, `echo_loop` repeats; esp balance for echoes 2..32 | 3789-3790, 3842-3849 |
| PE_order | 1 (105) | egen ordering (allowed for DWI) | 816-823, 967-968, 1058-1088 |
| nav_on | 1 (13) | 32 navigator views (gp_order = 0) first; no_views_eff = 128 | 855, 918-926, 2214-2215, 3570, 3698, 4023-4025 |
| no_views / no_views_2 | 160 / 1 (7, 9) | 5 shots per slice per volume (1 nav + 4 imaging); 2D (bw_override 71) | 878, 1327-1328, 1211-1221 |
| crush_independent_on | 1 (76) | separate crusher lobes (SEC) + slice-select lobe; padded RF plateau 1460 µs | 1285-1318, 1741-1746, 1760-1766, 2563-2567, 3080, 3085-3092 |
| crush_amp / diff_crush_amp | 5482 / 2754 (77-78) | train-180 / first-180 crusher DAC (slice axis) | 3080, 3089 |
| tcrush / diff_tcrush | 1000 / 1000 (74-75) | crusher plateaus; equal → no warning | 1297-1306, 2142, 1319-1321 |
| b_input_mode | 1 (269) | b-value table → DAC by binary search; b = 0 → DAC 1 | 686-687, 721-780 |
| no_diff_acq / no_experiments | 2 / 2 (272, 15) | one pass over the 2-row table: row 0 = b 0 (DAC 1), row 1 = b 6000 (DAC 20119), both along read (acq_x = 1000) | 673-684, 2103-2177, 4047-4055 |
| acq_b, acq_x/y/z | [0, 6000], x = [1000, 1000], y = z = 0 (273-274, 403-404, 468-469, 533-534) | diffusion on read axis only | 2160-2162, 3094 |
| te / esp / tr | 54 / 16 / 2000 ms (67-69) | te ≠ 0 → explicit-TE branch; extra_delta split symmetrically (branch 1) | 2407-2429, 2496-2502 |
| sm_delta / big_delta | 4000 / 40000 µs (270-271) | inside the b_kfac envelope | 576-585, 2440-2460 |
| phase_cycle | 1 (19) | phase_90 = aqphase(no_acq = 0, ·)·deg_90 = 0; phase_180 = 270° | 2232, 2295-2296 |
| flow_comp_on | 0 (108) | plain read prephaser, G2 = 0 | 1736-1738, 3015-3041, 3053-3064 |
| de_on | 0 (113) | no driven equilibrium | 828, 3624, 3871 |
| echoes_to_discard | 0 (112) | no discarded echoes | 3561-3566 |
| no_disacq | 4 (607) | 4 dummy passes (nav train, all slices) at the very start only (disacq_cnt is set to 0 only once) | 2081, 2209-2210, 3718-3719, 3999-4006 |
| post_crush_on | 1 (604) | post-train crusher +6000 DAC on all 3 axes, plateau 3000 µs | 2869-2870, 3939-3950 |
| gsp_lobe / grp_lobe | 0 / 110 % (79, 81) | no slice lobe at readout; 110 % of read dephase before the 180, −10 % after | 2978-2985, 3006-3013 |
| batch_slices / no_slices | 0 → 3 / 3 (26-27) | slices interleaved within TR, slice period = tr/3 | 1338-1339, 2929 |
| gating, mains gating, sat_on, chess_on, mtc_on, dixon_on, TR_array_size | 0 | all skipped (MAINSGATE undefined, PPL:257) | 3186, 3213, 3277, 3349, 2091, 1666 |
| tramp, tsel90 | 200 µs, 1332 µs | tramp ≥ 130 → no extra TR terms; tsel90 ≥ 300 → 300 µs + remainder branch | 2830-2835, 3576-3592 |

Branches I cannot resolve with certainty:

1. **Slice time order** `BatchTimeToPos(...)` (offst_20:17). The function body isn't provided. I assume slice_interleave = 1 means sequential order (positions −1.2, 0, +1.2 mm).
2. **`aqphase(0, 1)`**. I take it as 0, since no_acq = 0 for every train and the first step of any phase cycle is 0°.
3. **`acqpad(500)`** (PPL:623). This is a firmware function. It only affects the per-echo phase correction of the two off-centre slices.
4. **PPL `/` for negative operands**. I assume truncation toward zero, because `FloorDiv` exists separately (stdfn_15). It decides gp_inc = −40 (not −41), gs_var_rescale = −2741, gs_comp = −699 and grp_dp/gr_dp.

## Step 2 – Event timeline (one TR = one slice train, t = 0 at the start of the 90 slice gradient, `MR3040_Start` PPL:3418)

Amplitudes are logical-axis DAC; 1 DAC = 776.60 Hz/m = 0.018240 mT/m. Timing = the PPL's intended timing (balance equations). See assumption A3.

| # | event | axis | start (µs) | dur (µs) | amplitude (DAC) | RF phase | PPL |
|---|---|---|---|---|---|---|---|
| 1 | slice select ramp/plateau/ramp | s | 0 | 200+1332+200 | −2741 (gs_var_rescale) | | 1721-1722, 3071, 3414-3445 |
| 2 | RF 90 "3lobe_sinc_3kHz" | | 260 | 1332 | 90° | 0° | 3425-3449 |
| 3 | slice rephaser (NEGPULSE_SEC tref) | s | 1732 | 200+2800+200 | +699 (−gs_rp) | | 1723, 3074 |
| 4 | read prephaser (NEGPULSE_SEC tref) | r | 1732 | 200+2800+200 | −889 (−G1) | | 1726-1738, 3074 |
| 5 | diffusion lobe 1 | r | 5826 | 200+3800+200 | −diff_grad (−20119 / −1) | | 3503-3514, 3094 |
| 6 | first-180 crusher (POSPULSE_SEC 1000) | s | 25596 | 1400 | +2754 | | 1760-1765, 3089 |
| 7 | 180 slice select (POSPULSE 1460) | s | 26996 | 200+1460+200 | −2741 | | 1764, 3089 |
| 8 | RF 180 #1 | | 27260 | 1332 | 166.4° (A2) | 270° | 3459, 3530-3601 |
| 9 | first-180 crusher | s | 28856 | 1400 | +2754 | | 1765 |
| 10 | diffusion lobe 2 | r | 45826 | 4200 | −diff_grad | | 3603-3619 |
| 11 | read dephase (NEGPULSE_SEC tdp) | r | 50366 | 1100 | −269 (−gr_dp) | | 1792-1795, 3733 |
| 12 | phase encode (NEGPULSE_SEC tdp) | p | 50366 | 1100 | −gp_var = −40·gp_mul (0 on nav) | | 1797-1798, 3570-3572 |
| 13 | readout (POSPULSE tacq) | r | 51466 | 200+6400+200 | −735 | | 1794, 3688 |
| 14 | ADC 128 × 50 µs | | 51726 | 6400 | | rx 0° | 3722-3780 |
| 15 | read rephase (NEGPULSE_SEC tdp) | r | 58266 | 1100 | −269 | | 1795 |
| 16 | phase rewinder (POSPULSE_SEC tdp) | p | 58266 | 1100 | +gp_var | | 1802 |
| 17 | train-180 crusher / select / crusher | s | 60596 | 4660 | +5482 / −2741 / +5482 | | 1740-1746, 3080 |
| 18 | RF 180 #2 | | 62260 | 1332 | 166.4° | 270° (+corr) | 3786 |
| … | items 11-18 repeat every 16000 µs | | | | | | |
| 19 | post-train crusher | s, p, r | 555632 | 200+3000+200 | +6000 each | | 3939-3950 |

Key times: 90 centre 926; 180₁ centre 27926; echo 1 (ADC centre) 54926; 180ₖ centre = 54926 + (k − 1.5)·16000; echo k = 54926 + (k − 1)·16000; echo 32 at 550926. Δ (lobe onset to onset) = 40000 µs and δ = 4000 µs (plateau + one ramp). Each slice train sits in a 666666 µs slot: 10270 µs pre-90 code time (PPL:2841), the train, the crusher, then the tr_extend delay (PPL:3955-3983).

Loop structure (PPL:2082-4055, outer → inner): volume (acq-table row 0, then 1) → averages (1) → slice batch (1) → disacq/dummy loop → shot loop (5 shots: nav, then 4 imaging) → view block (1) → slices 1..3. Dummies: 4 passes of the nav shot for all 3 slices, b = 0 row, no data, only before the first volume. Per volume: 15 trains = 10 s. Total 4 × 2 s + 2 × 10 s = 28 s.

PE order (PE_order 1, PPL:1058-1088), gp_mul per echo e = 1..32:

- shot 1: −2e
- shot 2: −2e + 1
- shot 3: 2(e − 1)
- shot 4: 2(e − 1) + 1

Echo 1 holds k ≈ 0 (TE_eff = 54 ms).

## Step 3 – Units

| quantity | conversion | source |
|---|---|---|
| gradient | G = DAC/32767 × 25447 Hz/mm → 776.60 Hz/m per DAC, full scale 597.66 mT/m | PPR:5 (grad_var[0]), var_20:96 (dacmax), m3040_15:241-282 (isotropic base matrix, CREATE_MATRIX divisor) |
| timer tick | 100 ns (waittimer/delay32) | MAN 4.8 |
| gradient clock | tramp/5 = 40 × 100 ns = 4 µs/point, 50 points/ramp | PPL:1714, MAN 5.6.1.3 |
| phase | 0.225° per unit; deg_90 = 400 | var_20:108, PPL:1255 |
| sample period | 500 × 100 ns = 50 µs | PPR:4 |
| 90° | p90_mul = 594 = rfcal → 90° | PPL:2347 |
| 180 | p180_mul = 1098 → 166.36° if the amplifier is linear (A2) | PPL:2348 |
| RF shape | rfnum 1: 1332 µs, nominal BW 3000 Hz (TBW 4); slice gradient uses 71 % → 2130 Hz → 1.0006 mm | PPL:598, 1327-1333, 1437-1448 |

## Step 5 – Validation (reduced .seq read back; `validation/report_gd*.txt`)

| check | GRAD_DELAY_US = 0 | = 60 |
|---|---|---|
| `check_timing` (reduced and full) | PASS | PASS |
| 90 → 180₁, 180₁ → echo 1 | 27.0000 / 27.0000 ms | same |
| TE | 54.0000 ms (PPR 54) | same |
| 180ₖ → 180ₖ₊₁ (k ≥ 2), echo spacing | 16.0000 ms (PPR 16) | same |
| 180₁ → 180₂ | 35.0000 ms (= te/2 + esp/2) | same |
| b, diffusion lobes only | 5962.3 s/mm² | 5962.3 |
| b, all gradients, echo 1 | 6380.0 (xx 6379.3, zz 0.73) | 6380.1 |
| b, all gradients, echo 2 / 3 / 32 | 6384 / 6389 / 6523 | same |
| PPL nominal (39.69 kernel) / PPR | 6000 / 6000 | |
| FOV read / phase from Δk | 35.04 / 35.77 mm (gp_inc truncation) | same |
| ky order vs gp_order | exact, ky = −gp_order·Δky | same |
| full protocol coverage | 128 unique ky per volume per slice | |
| kx = 0 sample (ADC centre 63.5) | 62.28 (−60.8 µs) | 63.48 (−0.8 µs) |
| slice residual after 90 rephase | +160483 DAC·µs (58.5 µs of plateau) | −3976 (1.5 µs) |
| net moment 180ₖ → 180ₖ₊₁, k ≥ 2 | x −5 335 197, y 0, z 8 606 748 DAC·µs, identical for all | same |
| 180₁ → 180₂ | x −85 811 165, z 5 333 145 → **differs (flagged)** | same |

The b = 6000 request becomes 5962 s/mm² from the lobes. That is because the PPL kernel uses 39.69 instead of (2π)² = 39.48. Cross-terms with the 110 % read prephaser and the readout raise the echo-1 b to 6380 s/mm² (+7 %).

## Assumptions and placeholders

- **A1** RF shape: placeholder sinc, TBW 4, no apodisation, 1332 µs. Real frame "3lobe_sinc_3kHz" in RFstd44.seq. Set `RF_SHAPE_FILE`.
- **A2** Refocusing flip = 90 × 1098/594 = 166.36° (linear amplifier). Set `REFOCUS_FLIP_DEG = 180` if 185 % is an amplifier calibration.
- **A3** Timing = the PPL's balance equations. The empirical tick constants (−21, −6, −185, −156, −36, −210, +250, tfilter) exist to cancel code overhead, so I don't model residual overhead (a few µs) or the untimed MR3040 set-up calls. The 90 and 180 RF start = list start + (crusher budget) + tramp + rfdelay, which is the intent of `temp_mac` (PPL:3425, 3543).
- **A4** Gradients follow the commanded timing (`GRAD_DELAY_US = 0`). The PPL delays RF/ADC by rfdelay = 60 µs to offset hardware gradient delay. The 60 µs model aligns the read echo and the 90 rephasing, but makes every 180 select lobe asymmetric by 120 µs (the 180 is centred in command time).
- **A5** Ramps are linear (frames "0_max", "max_0", "0_mx_sec", … are 50-point ramps; the actual frame data in g3040_15.seq is not available). Frame "zeros" lasts one ramp (200 µs).
- **A6** The ADC samples the window [initiate, initiate + 6400 µs]. The filter group delay (tfilter) only shifts the `complete()` return, and the PPL subtracts it (PPL:2720).
- **A7** Post-train crusher starts 266 µs after the last read list (26 + 240 µs, tr_min accounting PPL:2829, 2870).
- **A8** Pre-90 code time is 10270 µs and the slice period is 666666 µs exactly (PPL:2841, 2929). The real slot = actual code time + tr_extend.
- **A9** Off-centre slices get ±2556 Hz. Their per-echo phase correction needs acqpad(500), so it is not applied (`OffsetSlicePhaseCorr` definition). It is irrelevant for the centre slice.
- **A10** Logical read/phase/slice → Pulseq x/y/z. The absolute polarity of all gradients (base-matrix sign) is unknown, which mirrors slice positions (−480 → +1.2 mm here). Relative signs are exact.
- **A11** The 1 µs gradient/RF raster is finer than a vendor scanner's. The 4 µs DAC staircase is not modelled. Odd extra_delta values (half-µs delays) would need a 0.1 µs raster (the script asserts).
- **A12** System: max grad = full scale; max slew = full scale / 100 µs (min tramp, PPL:114); rf_dead_time = warmup 20 µs (var_20:107); rf_ringdown and adc_dead_time = 0 (not in files; they don't change any waveform).
- **A13** Dummy TRs play no ADC events (data are discarded on the scanner).

## PPL items flagged (kept as written)

- First-180 crushers (2754) are about half the train crushers (5482). With the diffusion lobes, the 180₁→180₂ interval moment differs from every other interval, so the CPMG condition is broken by design. All later intervals are identical.
- The RF phases are CPMG (90 at 0°, all 180s at 270°). Nothing in this code path makes the RF phases non-CPMG; the "non-CPMG" in the file name is only the unequal first interval (te/2 ≠ esp/2).
- `CREATE_MATRIX(aq_mat …)` (PPL:3688) and `aq_mat_sec` (PPL:3733) are recomputed while that matrix is active (MAN 3.5.19: "unpredictable"). The values are unchanged and the affected frames are zero at that moment, so I expect no effect, but it is not modelled.
- The 90 RF ends 60 µs into the slice ramp-down in command time, because rfdelay is applied asymmetrically (PPL:3443-3448).
- gp_inc truncates 40.86 → 40, so the phase FOV is 35.77 mm against 35.04 mm in read.
- b = 0 rows play DAC 1 (0.018 mT/m lobes), not zero.
