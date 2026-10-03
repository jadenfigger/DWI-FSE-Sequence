# Technical reference: how the PPL becomes a Pulseq sequence

This is the detailed reference for `dwfse/generate.py`, which turns `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.6.ppl` plus a `.ppr` into a `.seq`. For day-to-day use see the main [README](../README.md); for the findings see [REPORT](../REPORT.md).

Citations: `PPL:n` / `PPR:n` = line numbers in the .ppl / .ppr (the original protocol PPR, ETL 32, b 6000); `var_20`, `m3040_15`, … = the .pph files; `MAN` = EVO manual.

## Controlling the sequence

Every parameter is a PPR variable name, exactly as in the `.ppr` file. Extra hardware and simulation settings use the prefixes `hw_*` and `sim_*`.

```bash
python dw.py gen out.seq --full                      # whole protocol from scanner/*.ppr
python dw.py gen out.seq                             # reduced simulation cut (default)
python dw.py gen out.seq --ppr my.ppr                # any other PPR of this PPL
python dw.py gen out.seq --set te=60 --set esp=18 --set acq_b=0,1000,3000 \
       --set no_diff_acq=3 --set no_experiments=3 --set acq_x=1000,1000,1000 --set acq_y=0,0,0 --set acq_z=0,0,0
python dw.py gen out.seq --params params_example.json --report
python dw.py run fixed --set sim_fix_refocus_centering=true    # generate + view + simulate + plot
```

From Python: `from dwfse import generate; seq, C, D, log = generate.build_sequence(generate.load_params('my.ppr', {'te': 60}), reduced=True)`.

The generator runs the PPL's own set-up checks and aborts with the PPL's message. Examples: "TE is too short…", "esp too short…", "TR too short, increase to N ms", "b=… too high…". `--report` prints the values the PPL's `report_on` would print (min TE/ESP/TR, DACs, nominal b), plus the derived set-up values.

**PARSETUP emulation** (`sim_parsetup=true`, default). On the scanner, the parameter editor recomputes `gs_var`, `gr_var`, `gp_init_var` and `fov_*_off` whenever you change FOV, slice thickness, offsets, views or bandwidth. The generator does the same from `fov_mm`, `slice_thickness_mm`, `fov_offsets_mm` (or `slice_separation_mm`), `no_views` and `sample_period`. These formulas are inferred, but for the protocol PPR they reproduce all stored values exactly. Set `sim_parsetup=false` to use the PPR's stored DAC values as they are.

### PPR parameters that act on the sequence

| group | parameters |
|---|---|
| geometry | `fov_mm`, `slice_thickness_mm`, `no_slices`, `slice_separation_mm`, `fov_offsets_mm`, `slice_mm_10`, `FOVf`, `oversample`, `oversample2`, `batch_slices`, `slice_clustering_on`, `interslice_delay` |
| matrix / ordering | `no_samples`, `no_discard`, `sample_period`, `no_views`, `views_per_seg` (ETL), `nav_on`, `PE_order` (1, 6, 7), `PF_echoes` |
| timing | `te`, `esp`, `tr` (0 = minimum), `TR_array`, `TR_array_size`, `tramp`, `tref_setup`, `post_90_delay1`, `rfdelay`, `rfgate_delay` (checked only) |
| crushers | `crush_independent_on` (0 = legacy, 1 = v1.6), `tcrush`, `diff_tcrush`, `crush_amp`, `diff_crush_amp`, `post_crush_on`, `post_tcrush`, `post_crush_amp` |
| compensation lobes | `gsp_lobe`, `gs_comp_scale`, `grp_lobe`, `gr_comp_scale`, `gs_on`, `gr_on`, `gp_on` |
| diffusion | `b_input_mode`, `sm_delta`, `big_delta`, `no_diff_acq`, `acq_b`, `acq_grad`, `acq_x`, `acq_y`, `acq_z`, `diff_tramp`, `diff_grad_scale` |
| RF | `rfnum` (sinc frames 1-8, 15, 16 are rebuilt from their names, see "RF pulse" below; others need a shape file), `alpha`, `rfcal`, `p180_scale`, `phcor0` |
| frequency / phase | `rec_freq`, `phcor_plus`, `phcor_minus`, `r_phcor`, `phase_cycle` |
| loops | `no_experiments`, `no_averages`, `view_block`, `no_disacq` |
| hardware | `grad_var` |

Not implemented: options that select other PPL variants. These abort with a message: `diff_on=0`, ETL = 1, flow compensation, driven equilibrium, presat, fat sat, CEST, gating, Dixon, 3D, and `echoes_to_discard>0` (limited to 0 by PPL:156).

### Extra parameters (not in the PPR)

| parameter | default | meaning |
|---|---|---|
| `hw_grad_delay_us` | 60 | physical gradient lag behind the commanded waveform; see "rfdelay" below |
| `hw_rf_dead_time_us` / `hw_rf_ringdown_time_us` / `hw_adc_dead_time_us` | 100 / 30 / 10 | typical Pulseq values (used by checks only) |
| `hw_max_grad_hz_per_m` / `hw_max_slew_hz_per_m_per_s` | full scale / full scale per 100 µs | limits (checks only) |
| `hw_gamma_hz_per_t` | 42.577478e6 | |
| `sim_excitation_flip_deg` | `alpha` | 90 flip |
| `sim_refocus_flip_deg` | 180 | `p180_scale` is treated as a calibration. `"linear"` gives 90 × p180_mul/p90_mul (166.4° for this PPR) |
| `sim_fix_refocus_centering` | false | false = PPL v1.6 as written (replicates the 180 centring bug); true = intended behaviour |
| `sim_excitation_phase_deg` | 0 | excitation-only phase-error surrogate; refocusing/receiver phases unchanged; rounded to 0.225° |
| `sim_refocus_phase_offsets_deg` | none | explicit ETL-length relative RF phase table, rounded to hardware phase units; receiver unchanged |
| `sim_train_crusher_scales` | none | explicit ETL-length signed first/train crusher multipliers, nearest-DAC rounding; symmetric lobes; independent mode only |
| `sim_rf_model` | `truncated_sinc` | `truncated_sinc` (N-lobe sinc, TBW = N+1) or `bw_matched_sinc` (sinc stretched to the PPL's 71 % slice bandwidth) |
| `sim_rf_apodization` | 0 | window (1−a) + a·cos(2πt/T): 0.5 = Hanning, 0.46 = Hamming |
| `sim_rf_bw_fraction` | 0.71 | `bw_matched_sinc` only |
| `sim_rf_shape_file` | none | your own frame (one amplitude per line); overrides the model |
| `sim_acqpad_ticks` | none | `acqpad(sample_period)`. Only needed for the per-echo RF/receiver phase correction of off-centre slices. The manual (5.6.4) gives tfilter ≈ 380 µs for SW < 100 kHz, i.e. ≈ 3800 ticks |
| `sim_aqphase_table` | none | `aqphase()` steps if `phase_cycle` ≠ 1 with averages > 1 (firmware function) |
| `sim_slice_order` | sequential | slice time order (confirmed sequential) |
| `sim_zeros_frame_us` | one ramp | length of gradient frame "zeros" (g3040_15.seq not available) |
| `sim_post_crush_gap_us` | 266 | last read list → post crusher (26 + 240 µs, PPL:2829, 2870) |
| `sim_pre90_us` | 10270 | slot start → 90 gradient start (PPL:2841) |
| `sim_reduced_slices` / `_rows` / `_shots` / `_n_dummy` / `_keep_slots` | centre slice / first b > 0 row / first imaging shot / 0 / true | the `--reduced` cut. Timing inside every TR is unchanged; other slices' slots become dead time |

## RF pulse (`dwfse/rf_pulses.py`)

The vendor RF library (`c:\smis\seqlib\RFstd44.seq`) is not published, so the sinc frames are rebuilt from their names. Every sinc frame in the PPL's table satisfies bandwidth × duration = lobes + 1:

| frame | duration × BW | lobes + 1 |
|---|---|---|
| `3lobe_sinc_3kHz` | 1332 µs × 3000 Hz = 4 | 4 |
| `5lobe_sinc_3kHz` | 2000 µs × 3000 Hz = 6 | 6 |
| `9lobe_sinc_5kHz` | 2000 µs × 5000 Hz = 10 | 10 |
| `19lobe_sinc_2ms` | 2000 µs × 10000 Hz = 20 | 20 |

So `3lobe_sinc_3kHz` is a sinc with zero crossings every 333 µs, cut after the central lobe and one side lobe on each side. That is the default `truncated_sinc` model, and it is the same pulse as the earlier placeholder (within 0.1 %).

**One inconsistency to know about.** MR Solutions treats this frame's slice-defining bandwidth as about 71 % of its name:

- the manual's GEDEM_MC example lists it as `NEWSHAPE_MAC(1, pf1, "3lobe_sinc_3kHz", 1332, 2140)`;
- the PPL multiplies 3000 Hz by `bw_override = 71` (PPL:1327-1333) and sets the slice gradient from the result.

A plain truncated sinc's 90° profile is as wide as its full name bandwidth, so at the PPL gradient the slices come out wider than nominal (1 mm protocol, `python dw.py rf`):

| model | 90° FWHM | 180° FWHM | spin-echo FWHM |
|---|---|---|---|
| `truncated_sinc` | 1.42 mm | 0.82 mm | 0.82 mm |
| `truncated_sinc`, Hanning 0.5 | 1.55 mm | 0.94 mm | 0.89 mm |
| `bw_matched_sinc` | 1.06 mm | 0.66 mm | 0.65 mm |

For the 5-lobe default pulse (`5lobe_sinc_1500Hz`, which PARSETUP's 1070 Hz reference assumes), the 180°/spin-echo FWHM is 0.74 × its name bandwidth. So the 71 % factor may be a spin-echo slice convention rather than a different pulse shape. That is unconfirmed.

The choice matters for B1 studies. Minimal protocol, echo 2 at B1 0.8 / 1.0 / 1.2:

| model | echo 2 |
|---|---|
| truncated sinc | 0.22 / 0.19 / 0.09 |
| Hanning | 0.15 / 0.19 / 0.14 |
| bw-matched | 0.12 / 0.14 / 0.09 |

The truncated sinc's echo peaks near B1 0.8 because of its Gibbs overshoot. `--report` prints the profile widths for the chosen model, and they are also written to the `.seq` definitions (`SliceFWHM_mm_exc_ref_SE`). `python dw.py rf` writes the shapes as text files (usable as `sim_rf_shape_file`) and the plot `docs/figures/rf_pulses.png`.

## rfdelay: what the PPL says, and the bug

The PPL states why `rfdelay` exists: "rf delay added to compensate for (isotropic) gradient group delay" (PPL:4100; also PPL:207, 3423, 3537). Every RF pulse and the ADC are commanded `rfdelay` later than the gradient plateau they belong to:

- 90: RF starts `rfdelay` after the ramp, and the ramp-down is commanded `rfdelay` before the RF ends (PPL:3425, 3443-3448).
- ADC: starts `tramp + rfdelay` after the readout ramp starts (PPL:3726).
- Legacy 180s (`crush_independent_on=0`): RF is centred `rfdelay` after the plateau centre (PPL:3543).

So the scanner is assumed to output gradients about 60 µs late, and the simulation default models that lag (`hw_grad_delay_us=60`). With it, the 90 slice rephasing is exact (1.5 µs residual) and the readout echo sits at the ADC centre (0.8 µs).

**The bug.** The v1.6 independent-crusher code removes this compensation for the 180s only. `crush_pre_pad` contains `−rfdelay` and `crush_post_pad` contains `+rfdelay` (PPL:1316-1317), and these cancel the `+rfdelay` in the RF start (PPL:3543). The result is that each 180 is centred on the *commanded* plateau. With the 60 µs lag, the physical slice-select plateau is 60 µs late relative to the 180: 4 µs margin before the RF, 124 µs after. Each spin echo then carries a through-slice moment of 331 662 DAC·µs, about 93° of phase across the 1 mm slice. No reason is given in the PPL.

- `sim_fix_refocus_centering=false` (default) replicates this.
- `true` commands the 180 slice lists, and the diffusion lobes chained to them, `rfdelay` earlier. This is the intended behaviour; it is not in any PPL. Big Δ, δ, TE and ESP are unchanged, and the slice-axis half-intervals become equal again.
- `hw_grad_delay_us=0` plays the commanded timing literally (90 rephasing off by 58.5 µs, readout echo 60 µs before the ADC centre).

## Step 1 – Branch resolution (protocol PPR)

| parameter | PPR value (line) | branch it selects | PPL lines |
|---|---|---|---|
| diff_on | 1 (268) | DWI path: te_eff = 1, te = first echo, esp = train spacing, tcrush1 = diff_tcrush, lobes played, first-180 list | 803-833, 1321, 1756-1770, 2137-2177, 2369-2374, 2435-2461, 2485, 2541-2553, 2645, 2694-2771, 2825, 3085-3092, 3467-3475, 3503-3526, 3541, 3603-3622, 3644-3677, 3806-3810 |
| views_per_seg | 32 (8) | multi-echo train | 3789-3790, 3842-3849 |
| PE_order | 1 (105) | egen ordering | 816-823, 1058-1088 |
| nav_on | 1 (13) | 32 navigator views; no_views_eff 128 | 855, 918-926, 2214-2215, 3570, 4023 |
| crush_independent_on | 1 (76) | separate crusher lobes, 1460 µs RF plateau | 1285-1318, 1741-1746, 1760-1766, 2563-2567, 3080-3092 |
| b_input_mode | 1 (269) | b → DAC search (b = 0 → DAC 1) | 686-687, 721-780 |
| no_diff_acq / no_experiments | 2 / 2 (272, 15) | row 0: b 0, row 1: b 6000 (DAC 20119), read axis | 673-684, 2103-2177, 4047-4055 |
| te / esp / tr | 54 / 16 / 2000 ms | explicit-TE branch; symmetric extra_delta | 2407-2429, 2496-2502 |
| phase_cycle | 1 (19) | phase_90 = 0, phase_180 = 270° | 2232, 2295-2296 |
| no_disacq | 4 (607) | 4 dummy nav passes, only at scan start | 2081, 3718-3719, 3999-4006 |
| post_crush_on | 1 (604) | +6000 DAC crusher, all axes | 3939-3950 |
| gsp_lobe / grp_lobe | 0 / 110 % | no slice lobe at readout; 110 % read dephase before the 180 | 2978-3013 |
| flow comp, DE, presat, CHESS, CEST, gating, Dixon, TR array | off | skipped | |

Resolved since the first version: slice order is sequential (confirmed), and `aqphase(0, ·) = 0`. Still open: `acqpad()` (off-centre slice phase only), and truncating PPL division (gp_inc = −40, which gives a phase FOV of 35.77 mm).

## Step 2 – Event timeline

t = 0 at the 90 slice-gradient start (commanded). Amplitudes are logical DAC; 1 DAC = 776.60 Hz/m = 0.018240 mT/m. With `hw_grad_delay_us=60` every gradient below is played 60 µs later; RF and ADC times do not move.

| # | event | axis | start (µs) | dur (µs) | amplitude (DAC) | RF phase | PPL |
|---|---|---|---|---|---|---|---|
| 1 | slice select | s | 0 | 200+1332+200 | −2741 | | 1721, 3071, 3414-3445 |
| 2 | RF 90 | | 260 | 1332 | 90° | 0° | 3425-3449 |
| 3 | slice rephaser | s | 1732 | 200+2800+200 | +699 | | 1723, 3074 |
| 4 | read prephaser | r | 1732 | 200+2800+200 | −889 | | 1726-1738 |
| 5 | diffusion lobe 1 | r | 5826 | 200+3800+200 | −20119 (b 6000) / −1 (b 0) | | 3503-3514, 3094 |
| 6 | first-180 crusher / select / crusher | s | 25596 | 1400 / 1860 / 1400 | +2754 / −2741 / +2754 | | 1760-1766, 3089 |
| 7 | RF 180 #1 | | 27260 | 1332 | 180° | 270° | 3459, 3530-3601 |
| 8 | diffusion lobe 2 | r | 45826 | 4200 | same as 5 | | 3603-3619 |
| 9 | read dephase / readout / rephase | r | 50366 | 1100 / 6800 / 1100 | −269 / −735 / −269 | | 1792-1795 |
| 10 | phase encode / rewinder | p | 50366 / 58266 | 1100 each | ∓40 × gp_mul (0 on nav) | | 1797-1802, 3570 |
| 11 | ADC 128 × 50 µs | | 51726 | 6400 | | rx 0° | 3722-3780 |
| 12 | train-180 crusher / select / crusher | s | 60596 | 1400 / 1860 / 1400 | +5482 / −2741 / +5482 | | 1740-1746, 3080 |
| 13 | RF 180 #2 | | 62260 | 1332 | 180° | 270° | 3786 |
| … | 9-13 repeat every 16000 µs | | | | | | |
| 14 | post-train crusher | s, p, r | 555632 | 200+3000+200 | +6000 | | 3939-3950 |

Key times: 90 centre 926; 180₁ centre 27926; echo 1 at 54926; echo k at 54926 + (k−1)·16000. Each train sits in a 666666 µs slot: 10270 µs of pre-90 code time, the train, then the TR fill.

Loops (PPL:2082-4055, outermost first): table rows → averages → slice batches → dummy (disacq) loop → shots (navigator, then 4 imaging) → view block → slices. Dummies are 4 navigator passes of all slices with the b = 0 row, before the first volume only. Total scan 28 s.

PE order (PE_order 1), gp_mul for echo e:

- shot 1: −2e
- shot 2: −2e + 1
- shot 3: 2(e − 1)
- shot 4: 2(e − 1) + 1

The k = 0 line is in echo 1.

## Step 3 – Units

| quantity | conversion | source |
|---|---|---|
| gradient | DAC/32767 × 25447 Hz/mm (full scale 597.66 mT/m) | PPR:5, var_20:96, m3040_15:241-282 |
| timer | 100 ns ticks | MAN 4.8 |
| gradient clock | tramp/5 × 100 ns per point, 50 points per ramp | PPL:1714, MAN 5.6.1.3 |
| phase | 0.225° per unit | var_20:108 |
| RF | flip from `alpha` and `sim_refocus_flip_deg`; shape from `dwfse/rf_pulses.py` | PPL:598, 2347-2348 |

## Step 5 – Validation (original protocol PPR, reduced sequence read back)

These checks are now part of `python dw.py view` (timing, CPMG moments, b per echo, k-space order) for any `.seq`. The numbers below are for the original protocol (ETL 32, b 6000), with and without the 60 µs gradient-delay model and the centring fix.


| check | default (lag 60, as written) | fixed centring | commanded (lag 0) |
|---|---|---|---|
| check_timing (reduced and full) | PASS | PASS | PASS |
| TE / 180₁→180₂ / ESP | 54.0000 / 35.0000 / 16.0000 ms | same | same |
| b lobes only / all gradients at TE | 5962.3 / 6380.1 s/mm² | 5962.3 / 6380.0 | 5962.3 / 6380.0 |
| b all gradients at echo 32 | 6523.5 | | 6523.0 |
| ky order | exact (ky = −gp_order Δky) | exact | exact |
| kx = 0 vs ADC centre | −0.8 µs | −0.8 µs | −60.8 µs |
| 90 slice residual | −1.5 µs of plateau | −1.5 µs | +58.5 µs |
| slice moment 180→echo vs echo→180 | 4 137 543 vs 4 469 205 (bug) | 4 302 004 vs 4 304 745 | 4 302 004 vs 4 304 745 |
| 180ₖ→180ₖ₊₁ net moment, k ≥ 2 | identical for all | identical | identical |
| 180₁→180₂ | differs (diffusion lobe 2, smaller first crushers) | same | same |
| full-protocol coverage | 128 unique ky per volume per slice | | |

The PPL's nominal b (6000) uses 39.69 instead of (2π)², so the true lobe b is 5962 s/mm². The read prephaser and readout cross-terms raise it to 6380 s/mm² at echo 1.

## Assumptions and placeholders

1. RF shape: rebuilt as a truncated sinc from the frame name (see "RF pulse"); the vendor file RFstd44.seq is not available.
2. Refocusing flip 180° (`p180_scale` treated as a calibration).
3. Timing follows the PPL's balance equations. The empirical tick constants cancel code overhead; residual overheads of a few µs are not modelled.
4. Hardware gradient lag = 60 µs (the PPR rfdelay), per PPL:4100.
5. Linear ramps; frame "zeros" lasts one ramp; plateaus quantised to the gradient clock as in `MR3040_Delay`.
6. ADC window = [initiate, initiate + tacq]; the filter delay only shifts `complete()` and is subtracted by the PPL (PPL:2720).
7. Post crusher 266 µs after the last read list; pre-90 time 10270 µs; slot = tr/batch (or tr_min + extension with clustering).
8. Off-centre slice phase correction needs `sim_acqpad_ticks` (not applied by default).
9. PPL `/` truncates toward zero.
10. PARSETUP formulas inferred (verified against the protocol PPR).
11. Logical read/phase/slice → x/y/z. Absolute gradient polarity is unknown (only relative signs are known), which may mirror slice positions.
12. 1 µs raster, or 0.1 µs automatically when a half-µs delay occurs (odd Δ with independent crushers).
13. Dummy TRs carry no ADC; `no_discard` samples are included in the ADC.

## PPL items flagged (kept as written)

- 180 centring vs rfdelay (see above).
- First-180 crushers 2754 vs train 5482 DAC. With diffusion lobe 2, the 180₁→180₂ moment differs from all later intervals.
- RF phases are CPMG (0° / 270°); "non-CPMG" refers only to the unequal first interval.
- `aq_mat` / `aq_mat_sec` are recomputed while active (PPL:3688, 3733). The values are unchanged, so no effect is modelled.
- gp_inc truncation 40.86 → 40: phase FOV 35.77 mm vs read FOV 35.04 mm.
- b = 0 rows play DAC 1, not zero.
- With `slice_clustering_on=1`, TR is rounded through integer ms (PPL:2946, 3976), so the real TR is 2001.1 ms for this protocol.
