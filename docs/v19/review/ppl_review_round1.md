# Independent PPL review, round 1: v191 (ss-MGOT) and v192 (Alsop)

Reviewer: independent PPL reviewer. I did not write these files, and this review modified only this file.
Date: 2026-10-06.

## Scope and limits

This is a **static source review without a vendor compiler, simulator or console**. `pplc`, `cpp` and `specsim` are not installed. Results come from four sources:

- reading the PPL source and the vendor includes (`m3031_15.pph`, `m3040_15.pph`, `stdfn_15.pph`, `var_20.pph`);
- the EVO manual text (`tmp/evo_manual_ppl_review.txt`);
- the v18 source comments, which record measured instruction costs;
- hand re-derivation of the timing arithmetic (a standalone integer script written for this review, which does **not** import `dwfse.ppl`).

Instruction costs are taken from the manual's tables (section 4.9.2 operator table, section 3.3.1 library functions) and from the v18 source comments. All of them are estimates until a console trace exists.

Files reviewed (snapshot hashes; the PPLs were regenerated during the review and now contain `V19_POST_RF = 200`):

| File | SHA-256 |
|---|---|
| scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl | 458acb6b615de640d14117adbbceaba5581f2856b3b70d148df69eb6f3201795 |
| scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppr | faa77a11c2da4c5fe9876d6a842b9bc3025c66ddc09eaa4e8270dec9350faf0c |
| scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.92.ppl | 3947e891f0bda707911b42cc3870c2b530ec522bcbd92cdcd618cb44df52137b |
| scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.92.ppr | 678f2af5bb2fa205c2b7cb9402879d9ce1e98ed8e2c5fa4264c318b3e6898fbf |
| examples/build_v19_ppl.py | 8fc0ee11014085bb56eedf4b8d570738121aab2c162b0525817a7732a04b99f7 |
| scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl (baseline) | 3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2 (unchanged, verified) |

Line numbers below refer to these snapshots. The notation `191:Lx` / `192:Ly` means v191 line x and v192 line y.

---

## 1. Findings

| ID | Severity | file:line | Finding | Evidence | Suggested fix |
|---|---|---|---|---|---|
| **B1** | **blocking** | 191:4894-4913, 192:4838-4857 (generator `SHOT_TRAIN`, `waittimer(3000)`) | The post-`initiate()` window is only 3000 ticks (300 us), but its contents need about 540 us. Every echo therefore misses its `waittimer(3000)` deadline. Per the manual (pp. 90-91), a missed deadline extends the window by a whole 5 ms. As a result, `delay32(v19_adc_mid)`, `complete()` and the anchor for the next RF all slip by 5 ms on **every echo**. ESP becomes about 19 ms, the CPMG timing is destroyed, and `complete()` comes 5 ms after the end of sampling. | The window holds `CREATE_MATRIX(aq_mat_sec,...)`, which v18 measures at "1356 clocks", i.e. 135.6 us (191:L4223 comment). It also holds three long divide/remainder operations: `templ3%IntToLong(deg_360)`, `templ5/1000L`, `templ5%1000L`. The manual's 4.9.2 table gives long `/` = 1232 and long `%` = 1208 (100-ns units), so these cost about 365 us. Two long multiplications (9 us each) plus assignments add about 30 us. Total is about 530-550 us against 300 us available. Cross-check: v18 performs the same work plus the ADC delay split in this window, gives it 8997 ticks, and comments the measured cost as "8236 ticks" (191:L4412-4433). My manual-based estimate of that v18 window is about 845 us, consistent with the comment. The writer's interpreter cannot detect this: its `COSTS` table (`dwfse/ppl/interp.py:51`) has no operator costs and uses `stmt_cost_us=0`. | Make the window at least 8000 ticks, matching v18's validated 8997 budget, and recompute `v19_adc_mid` and `templ1` in `SETUP_TIMING_TAIL` with the same constant. Also add a setup check that `adc_mid >= 100` still holds. Alternatively, move the `phase_correction` arithmetic into the post-`complete()` window (`post_a`) and keep only the `CREATE_MATRIX` here, with at least 2500 ticks. |
| **M1** | major | 191:4867, 4897; 192:4811, 4841 | `gp_sl_var` is never assigned on the method path. Its only assignment is v18's 191:L4150 / 192:L4118, which sits between the v18 90 and first 180 and is skipped by `goto v19_mat_window`. The +D recall and -D restoration DACs are `gs_on*(gsp_rp -/+ gp_sl_var*gp_sl_on*nav_cnt +/- v19_d_dac)`. The method PPR has `gp_sl_on = 1` and `nav_cnt = 1` on non-navigator shots, so the recall/restoration amplitude depends on whatever value `gp_sl_var` holds. Initialisation of non-common PPL ints is not documented. A stale non-zero value from a previous 3D v18 run, or garbage, corrupts the MG recall. | `grep gp_sl_var` shows the declaration at 191:L496 and the only assignment at 191:L4150. The `no_views_2 == 1` gate makes the correct value 0 (`put_gp_var_mul2(0,0)`), but nothing on the method path assigns it. | In the matrix window (or any setup window on the method path), set `gp_sl_var = -gp_sl_inc*get_gp_var_mul2(current_view_2);` exactly as v18 does, or simply `gp_sl_var = 0` since 3D is rejected. |
| **M2** | major | 191:L348 (`V19_MAX_WAIT 65000L`), 191:L381, 387-398, 2366-2369 (same in 192:L343, 376, 382-393, 2334-2337) | The validator allows `waittimer` targets up to 65000 ticks. It also allows later `waittimer` calls on the same anchor to be **issued more than 5 ms after `starttimer()`**. The timer counts 0-49999. The manual allows a target up to 6.55 ms only if the intervening code takes less than 4.9998 ms; otherwise the wait is extended by 5 ms. v18 deliberately never waits past about 48000 ticks: it splits with `waittimer(47975L)` + `delay` at 191:L4130-4136. Exposed sites: `waittimer(off+V19_POST_RF)` in `V19_RF_GO` (issued at elapsed time ≈ off), `waittimer(rem+TAIL)` (issued at ≈ rem), and the loop-top `waittimer(post_b)` (issued at ≈ post_a). Concrete case: with the v18 PARAMLIST default `diff_tcrush = 2000` (PPR uses 1000), go_rf = 27200 and off_rf = 59220 ticks. Setup accepts this (off+200 ≤ 65000; rem_rf = 25975), but the prep-180 block then slips by 5 ms. Separately, `waittimer(v19_b_d*10L)` (191:L4824-4828) and `waittimer(v19_b_sp*10L)` (191:L4846) have **no bound check at all**. With tdp up to 5000 us, tramp up to 1000 us and t_sp up to 6000 us these reach 71 200 / 81 200 ticks, which wraps the 16-bit argument. | Manual p. 90 ("clock cycles from 0 to 49999 ... extended by 5 ms if the intervening code occupies more than 4.9998 ms"); v18 191:L4128-4136. Hand derivation for the shipped PPR: off_rf+200 = 49420, so the call lands at about 49 300 ticks, only about 70 us below the 5-ms boundary. | Set `V19_MAX_WAIT` to 49000 (v18 precedent) and apply it to the **issue time** of every chained `waittimer`, not only to its target. Better: re-anchor (`starttimer()`) immediately after `rfon(0)` in `V19_RF_GO` so that `off` is the only long wait in an RF block. Add bound checks for `(v19_b_d)*10`, `(v19_b_sp)*10`, `v19_rd_a1` and `v19_post_a`. Split longer intervals with `delay32`. |
| **M3** | major | 191:L420, 433 (`common int v19_on, ...`); per-shot branches 191:L2960, 3229, 3485, 3776; 191:L4737, 4766 | `v19_on` is a `common int`, so it remains interactively adjustable in SCAN setup mode. All method lists, timings and validation are built **once**, inside `if (v19_on==1)` at setup. If the switch goes 0→1 while running, the per-shot `goto v19_mat_window` runs the method path with `v19_l_*` list addresses, `v19_go_*` timings and `v19_mul[]` never initialised. That plays gradient lists from arbitrary sequencer addresses, a gradient safety hazard. Related: the method matrices read `crush_amp` and `diff_crush_amp` live (191:L4766, 4737), while v18 uses the validated copies `crusher_saved_train` / `crusher_saved_first`. An interactive change therefore bypasses the |C| ≥ 3|D| check and the D polarity rule computed at setup. | Manual §2.3: common ints "must be performed within the main acquisition loop" for interactive setup. v18 191:L1515-1516 saves the crusher values once. | Latch the method switch into a non-common int at setup (`v19_mode = v19_on;`) and test only `v19_mode` in the four per-shot branches. Use `crusher_saved_train` / `crusher_saved_first` in `CREATE_MATRIX(v19_m_im+256, ...)` and `(v19_m_rf+256, ...)`. Optionally make the other `v19_*` controls plain `int`. |
| m1 | minor | 191:L346-347, 2364; 191:L4877-4915 | The timing model's constants are uncalibrated. `V19_ANCHOR = 0.5 us` covers the delay32/starttimer transitions, `V19_INIT_COST = 7.6 us` has a documented ±5 us, and delay32's own overhead is undocumented (delay32 is not in the manual at all). The method also starts the timer **before** `MR3040_Start`, whereas v18 calls `MR3040_Start` and then `starttimer`. The RF and ADC are therefore about 2.4 us earlier relative to their gradient lists than in v18's empirically tuned relation, and every post-ADC anchor (`post_b`) carries the unmodelled initiate/delay32 cost. The expected error is a few microseconds of ESP/CPMG offset per echo, not a 5-ms failure. | Manual 3.3.2 (initiate 7.6 ± 5.0 us); v18 comments "MR3040_Start ... 24 ticks" (191:L4067) and "-40 gives 0 delay" (191:L4076). | Measure RF-gate, ADC-gate and gradient start on the console (scope or trace) and calibrate `V19_ANCHOR`, `V19_INIT_COST` and the list-start offset. Until then, report them as estimates. |
| m2 | minor | 191:L2371, 191:L381 | Some guards are weaker than the work they guard. (a) `v19_rd_a2 - v19_rd_a1 >= 600` ticks is vacuous because tramp ≥ 100; v18 says "tramp+rfdelay should be at least 163us" (191:L4378) for resync, `frequency_buffer` and `reset_frequency`. (b) `rd_a1` (2·tramp+tdp) must hold `CREATE_MATRIX` plus a long `%` plus `rphase`, about 330 us, and is not checked; this is the same exposure as v18. (c) The imaging RF pre-window contains `pr()` plus `CREATE_MATRIX` (about 160 us) but is only checked for `go-lead >= 300` ticks. These pass for the shipped PPR (rd_a1 = 11000, go_im-lead = 16400 ticks). | Manual operator table; v18 comments. | Require `rd_a2-rd_a1 >= 1630`, `rd_a1 >= 4000` and `go_im - lead >= 2500` ticks. |
| m3 | minor | 191:L2266-2267 | Spoiler-flat arithmetic `IntToLong(v19_spoil_cpmm)*templ1*1000L` can overflow 32 bits when grad_varl < ~3050 Hz/mm with cpmm = 200 (for example a 40 mT/m system ≈ 1703 Hz/mm). The wrapped value can pass the range check. The shipped PPR value is 4.1e7, which is safe. | 200·(32767000/1000)·1000 = 6.55e9 > 2^31. | Bound `cpmm*templ1 ≤ 2147483` before the multiplication, or divide first. |
| m4 | minor | 191:L4758-4762 / 192:L4719-4723 | The read prephaser `v19_rp_dac = G1*(tref+tramp)/(tdp+tramp)` is about 3.3× the v18 G1 amplitude on a shorter lobe. Its amplitude is checked against `crusher_max_dac`, but its **slew** is not (every other new lobe has a slew check). The PPR value is about -2967 DAC, so it is not a practical issue. | Code inspection. | Add the same `*100 > slew*tramp` check. |
| m5 | minor | 191:L2215-2216, 2262-2263 (V19_RFMUL) | RF amplitudes are `scale(rfcal, numerator, 10000)`, a linear model that ignores the user's `alpha` and `p180_scale` calibration. The PPR has `p180_scale = 185`, not 200, which points to empirical non-linearity or a calibration offset that the method's 180s (numerators 11509 and 10783) do not inherit. Multipliers for the shipped PPR (rfcal 594): ex 204, prep-180 683, tip / elim 223, re-exc 320, imaging 505 (142.2°) to 213 (60°). All are in 1..2047. | `docs/v19/rf_library_manifest.json` ("inference, not measured transmit gain"). | Console flip-angle calibration of each frame. Report that `alpha`/`p180_scale` are ignored on the method path. |
| m6 | minor | 191:L377-378, 393-396 | RF gate closes 2 us after the nominal frame end (`off = go + L*10 + 20`). The v19 frames have `extra_guard_samples: 0`, while the stock frames carry 2 guard records (1336 us vs 1332 us nominal). The `MR3031_go` → first-sample latency is undocumented. If it exceeds 2 us, the final samples are gated off; the SLR tails are near zero. | Manifest; prior review note on `3lobe_sinc_3kHz`. | Either add 2-4 guard zero samples to the frames or close the gate at L+5 us. |
| m7 | minor | 191:L387-392 | `rfgate_delay` is ignored. The amplifier is unblanked (`rfampon`) about `lead - setup` ≈ 40-60 us before `rfon`, compared with v18's `warmup + (rfgate_delay-17)` ≈ 26 us. It is functionally acceptable, but it is an undisclosed deviation (longer unblank, so more noise injection). | v18 191:L4085-4091. | Document it, or place `rfampon` (rfgate_delay-17) us before `go` as v18 does. |
| m8 | minor | 191:L369-370, 376 | `V19_FLAT` rounds to tramp/10 but does not force an even plateau, unlike v18's `crush_rf_flat` (191:L1501). For tramp/10 odd (for example tramp = 110), `(flat-L)/2` and `f/2` truncate, giving a 0.5-us RF-centre error. | Code inspection. | Add v18's even-flat step. |
| i1 | info | 191:L69 / 192:L68 | `#use RF1 "c:\smis\seqlib\v19_research_rf.seq" pf19` is compiled and linked **even with v19_on=0**. The v18 control build therefore fails if the file is missing from `c:\smis\seqlib`; the repo copy is at `scanner/rf/v19_research_rf.seq`. RF-board memory and the number or names of `#use` aliases are unverified. The frame names are present in the binary (verified by string scan). | — | Deployment checklist item; compile once with v19_on=0 and compare the produced timing and events with v18. |
| i2 | info | whole file | Code and data growth: about 200 setup lines with 5 expanded selector macros, 13 matrices, 128 int array words, about 100 scalars, and 7 new common ints in v191 (3 in v192, in dual-port RAM). The v18 header records byte budgets ("818B", "558B"), which suggests memory pressure. A 5-argument `printf` (191:L2381) exceeds anything v18 uses (4). Compile acceptance is unverified. | v18 header comments. | Vendor compile. |
| i3 | info | both .ppr, line 68 | Both method PPRs change `crush_amp` from -2741 to -8223. Running a method PPR with `v19_on=0` is therefore **not** the v18 control; the control must use the original test1e PPR. The `:PPL` line is now relative (was `G:\J_Figger\...`). | `diff` against the test1e PPR. | State this in the upload checklist. |
| i4 | info | 191:L432 (`v19_l_mr`), `v19_trmin_us`, label `v19_shot`; NEWSHAPE 21 (v191), 20/22 (v192) | Unused declarations, label and frames. They are harmless. (The manual's "up to ten labels" statement is clearly not enforced; v18 has dozens.) | — | Optional cleanup. |
| i5 | info | 191:L3485 | TR model: the method charges v18's "70 us untimed pre-90" allowance. The method's actual untimed pre-shot code is two `resync()` calls (≤ 10.5 us each) plus a few statements. Played TR is therefore up to about 50 us shorter than requested. This is negligible. | Manual 3.3.1.23. | None required. |
| i6 | info | 191:L2676-2680, 2716-2720 | Inherited v18 behaviour. Two runtime aborts are not on the validator path: `diff_grad > 30000` per acquisition-table row, and `diff_tramp != tramp`. The first can abort mid-scan after earlier rows have been acquired. | v18 structure. | Optional: add `diff_tramp==tramp` to the V19 setup gate. |
| i7 | info (resolved in snapshot) | 191:L349-350, 380, 396-397 | **Earlier draft (read at the start of this review):** the post-RF window was `waittimer(off+50L)`, i.e. 5 us. Its contents were `rfon(0)` (1.7 us), `if (use_pdd>0)` (1.6 us), `userout(pdd_rx_mask)` (3.1 us) and the long argument evaluation of the next `waittimer` (2.0 us). That is about 8.4 us with PDD and 5.3 us without, plus waittimer's own entry cost. That version would have missed its deadline (+5 ms) after every RF. The current snapshot uses `V19_POST_RF = 200` ticks (20 us), which is sufficient. | Manual 3.3.1.26, 3.3.1.31, 4.9.2. | Keep it at ≥ 200 ticks. |

---

## 2. Hand re-derivation of the shipped protocol timing

Inputs: tramp 200, rfdelay 60, tdp 700 (tref 2800), tcrush 1000, diff_tcrush 1000, TE 54 ms, ESP 14 ms, 128 × 50 us (tacq 6400 us, nsp 64000 ticks), δ 4000, Δ 40000, comp_flat 1000, warmup 20 (fixed by `var_20.pph`, so lead = 800 ticks), V19_POST_RF 200. Times are in us unless marked as ticks (0.1 us).

Plateaus (`V19_FLAT`, tramp/10 = 20): 3200-us frames give f = 3320; 1200-us frames give f = 1320.

| Block | go (ticks) | off (ticks) | rem (ticks) | block length b | Checks |
|---|---|---|---|---|---|
| prep 90 (ex, list f+4r+comp = 5120) | 3200 | 35220 | 15975 | 5240 | go-lead 2400 ≥ 300 ✓ |
| prep 180 (list 2·dtc+f+6r = 6520) | 17200 | 49220 | 15975 | 6640 | off+200 = 49420 < 50000 ✓, but issued about 70 us before the 5-ms boundary (M2) |
| tip-up v191 (list comp+f+4r = 5120) | 17200 | 49220 | 1975 | 5240 | same as above |
| elimination v192 (list 2comp+f+6r = 6520) | 17200 | 49220 | 15975 | 6640 | R list mr_zero+tdp+2r = 6220 ≤ 6520 ✓ |
| re-excitation v191 (list max(5120, 4020)) | 3200 | 15220 | 15975 | 3240 | ✓ |
| imaging 180 (list 2tc+f+6r = 4640) | 17200 | 29220 | 15975 | 4640+120 | ✓ |

Timeline (prep-90 RF centre = 0):

- s_ex = -1920. The prep-180 RF centre falls at TE/2 = 27000 ✓.
- Diffusion lobes start at a1 = 4840 and a2 = 44840 (Δ = 40000 ✓). They are symmetric about the prep-180 plateau centre (26940 = TE/2 - rfdelay) ✓.
- D lobe starts at s_d = 49440. Tip-up/elimination list starts at s_m = 50680, which puts its RF centre at 54000 = TE ✓.
- Gaps (ticks): x1 15190, 1r 145190, r2 145190, 2d 2790, dm 190 (at the minimum), ir 1190. v191 additionally has ms 190 and sr 190, both by construction.
- v191: t_sp = 2316 (32.0 cycles/mm checked by hand). Re-excitation centre T0 = 59716. First imaging RF centre at 66716 = T0 + ESP/2 ✓. E1 = 69156, ADC start 70516, **ADC centre 73716 = T0 + ESP ✓**. Read flat-top centre is 73656, i.e. the v18 rfdelay convention ✓. first_wait = 40570, shot 178286 us.
- v192: T0 = 54000, first imaging RF centre 61000, ADC centre 68000 = T0 + ESP ✓. first_wait = 30570, shot 172570 us.
- Readout: rd_a1 = 11000, rd_a2 = 13600, adc_mid = 50977, post_a = 22427, post_b = 24722 (≥ post_a + 1200 ✓), post_end = 23427. Read lists (9000 us) end 10 us before `waittimer(post_a)` under the anchor model. ESP budget: (E-s1) + read_len + 120 = 13880 ≤ 14000 ✓, a tight 120-us margin.
- Recall/restoration: D = 2860 DAC with the crusher's sign (crush_amp -8223, so D = -2860). |C| area = 8223·1200 = 9.87e6 ≥ 3·2860·900 = 7.72e6 ✓. The D lobe and both slice_list_rp lobes are the same `POSPULSE_SEC(tdp)` shape, so recall and restoration areas are exactly ±D (given gsp_rp = 0 from gsp_lobe = 0, and **gp_sl_var = 0, see M1**).

With the anchor model as written, every waittimer target above is ≤ 49420 and reachable, **except** the post-initiate `waittimer(3000)` (B1).

---

## 3. Verified OK (static)

**Control-path preservation**

- Both PPLs are pure insertions into the exact v18 bytes (`diff` shows only `a` hunks). The generator output equals the files on disk (in-memory `build()` / `build_ppr()` comparison), and the v18 SHA-256 is unchanged.
- Changes that execute with `v19_on = 0`:
  - `#use` line (compile/link only; see i1);
  - PARAMLIST additions and declarations (no execution time);
  - `NEWSHAPE_MAC(18..23)`, which fills `rad`/`rwt`/`rbd`/`rf_length`/`rf_bwdth[18..23]`. The arrays have 40 entries, and v18 never reads 18-23: rfnum ≤ 16, sat 9-13, chess 14, MTC 17;
  - two `if`s in the untimed setup before `sync()`;
  - four `if (v19_on==1)` tests (≈ 1.9 us each) inside v18 padded windows:
    - 5300 window: documented margin 284 ticks (191:L3170);
    - 27500 window: two tests (191:L3229, 3483);
    - 30000 window: one test, after the `crusher_setup_ticks ≤ 24500` check, inside v18's 550-us reserve;
  - a no-code label (`v19_after_train`);
  - a `goto end;` equivalent to v18's fall-through to `end:`.

  The v19 gradient lists are created only when `v19_on == 1`, after all v18 lists, so v18 list addresses are unchanged. **No v18 event timing changes** under the documented costs.
- Method branch point: the jump at 191:L3776 is inside the timed 3000-us window, and `v19_mat_window` completes the same `waittimer(30000)`. The skips at 191:L2960 and L3229 land inside their windows (labels sit before `waittimer(5300)` and inside the 27500 window).

**Rejection before events**

- All V19 gates are in setup at 191:L2177-2380, before `CREATE_MATRIX(ss_mat)`, before the validator exit (191:L2422), and before `sync()`. The validator path therefore runs the method setup and enforces the method `tr_min` (TR override at 191:L3483-3490 precedes the TR check and the validator duration exit at 191:L3658).
- Gated combinations: DWI off, legacy crushers, crusher schedules, DE, flow compensation, Dixon, 3D, discarded echoes, TREF setup mode, multi-slice, slice offset, presat, CHESS, CEST, gating, mains gating, TR arrays, gs/gr off or read reversed, gsp_lobe ≠ 0, post_90_delay1, phcor0, ETL outside 1..64, cycles outside 1..8, gs_var range, tdp / comp_flat / δ raster.
- Parameters silently ignored on the method path: `alpha`, `p180_scale`, `rfnum`, `rfgate_delay`, `gs_comp_scale` (m5, m7).

**Language and compiler**

- No 31-character truncation collisions. All new identifiers are ≤ 15 characters, and the only case-insensitive overlap is "V19"/"v19" inside comments and strings.
- Declarations precede the first statement.
- Matrix IDs 40-46 / 296-302 do not overlap any v18 or vendor ID.
- `#define` names do not collide with vendor names.
- Labels inside if-blocks have v18 precedent (`crusher_custom_check`).
- Macro hygiene: all multi-statement macros are used as standalone statements, never after an un-braced `if`. `CREATE_MATRIX` is a single `if` statement. Macro parameters appear only inside sums or function arguments, so there are no precedence surprises.
- Array bounds: `v19_flip_tenths` and `v19_mul` have 64 entries and indices are < views_per_seg ≤ 64; `rf_length[40]` is indexed 18-23.
- Int/long arithmetic: every new product is promoted with `IntToLong` before multiplication (selector ≤ 1.54e9 within the gs_var ≤ 12000 gate; compensation ≤ 1e8; D ≤ 9e7; C/D check ≤ 6e8). Pure-int expressions stay < 32767 (`v19_mr_zero`, `V19_FLAT`, `2*tramp+post_tcrush+240`). Long→int narrowings are range-checked before assignment. The exception is m3.
- `waittimer` and `delay32` take long arguments, as in v18.
- The PPR `VAR_ARRAY` format matches the manual and the existing PPR entries.

**Gradients and matrices**

- No `MR3040_Start` is issued on a running channel. No `SetList` targets an active channel: each tail `SetList` lies ≥ 20 us after the list end by the rem / df_wait / (b-TAIL) arithmetic.
- Every `SelectMatrix` happens after all lists on all channels have ended.
- All 13 method matrices are created under `ss_mat`, `caldelay` apart, more than 2.5 ms before use, and are never recomputed during the shot. `diff_mat` comes from the v18 window.
- `aq_mat_sec` is recomputed at the loop top while `v19_m_im` is selected (not active), so +D is ready more than 1.5 ms before `SelectMatrix(aq_mat)`.
- The `aq_mat` primary and secondary recomputations during the readout mirror v18 exactly. They only touch components that are idle (zero `DELAY` / `SEC` segments) or unchanged.
- List durations match the `V19_RFTIMES` `list_us` arguments for every block, using the `POSPULSE`/`NEGPULSE`/`_SEC` = top + 2·tramp library structure. `DELAY` arguments are on the tramp/50 raster.
- Matrix windows: gettimer ≤ 20000 then `waittimer(25000)` leaves 500 us for the 360-us gettimer overhead. The estimated contents are about 1650 us and 1560 us respectively.

**RF**

- Frames: `NEWSHAPE_MAC` durations equal sample_count × dwell (320 × 10 us, 120 × 10 us), and the frame names are present in `scanner/rf/v19_research_rf.seq`. The `pf19` alias is used consistently. The bandwidth integers (1109, 1283) are informational only and not used by the method.
- Multipliers are checked to 1..2047.
- Phases with `phase_increment(1)` (0.225°/unit, deg_90 = 400):
  - prep 90 → phase_90 (0°);
  - prep 180 and imaging → phase_180 = phase_90 + 1200 (270°);
  - v191 tip-up → phase_90 + 800 (180°; the correct flip-back for CPMG-axis refocusing);
  - v191 re-excitation → 0°;
  - v192 elimination → 270°.

  Phase values above 360° are legal (manual 3.3.1.11). Every `phase()` call is placed in a tail window (29.3 us inside 100 us) before its RF and after `complete()` for the train.
- PDD: tx mask is set at every method RF block start and rx mask after `rfon(0)`; `rfon(0)` closes each frame 2 us after the nominal end (but see m6).
- `NEWSHAPE_SETUP` + `rfampon` + `delay(warmup)` fit in the 80-us lead. The warmup and gate idiom matches v18 apart from the unblank lead (m7).
- RF centre = plateau centre + rfdelay, consistent with v18's independent-crusher convention.

**Receiver and ADC**

- Same sequence as v18 on every echo: buffer 1 + `reset_frequency` at (2·tramp+tdp), `initiate` at 3·tramp+tdp+rfdelay, `complete` at nsp-3 ticks, then buffer 0, `reset_frequency` and `phase(phase_180+phase_correction)` after `complete`.
- `rphase(phase_rec+phase_correction)` is set before `initiate`; `phase_correction` is reset per shot (191:L3417) and accumulates with `total_echo_cnt`, as in v18. The `phase_ang` model is unchanged because the rx dwell (tramp+rfdelay+tacq) is unchanged.
- `Dummy_Cycles(!notDummy)` and the `no_disacq` dummies are as in v18, and the full preparation plays on dummies.
- Navigator: `nav_cnt` multiplies gp_var, phase_rec and the slice-PE term, while ±D is applied unconditionally (correct).
- Counters: `get_gp_order(current_view+echo_cnt)` and `echo_cnt`/`total_echo_cnt` are as in v18. `v19_mul[echo_cnt]` uses entry k-1 for RF k.
- The PE rewind (phase_list) is unchanged. ±D is applied around **every** ADC, including the first and last.
- TR: `tr_min` = shot + 11350 + 139 + 5000 (+ post crusher). The return lands at `v19_after_train`, ahead of v18's post-crusher and TR tail; the shot end equals `waittimer(post_end)` = last read-list end + 110 us.

---

## 4. Status of prior findings (docs/v19/ppl_review.md)

| ID | Status |
|---|---|
| H1 (gettimer margin) | **Resolved.** The matrix windows reserve 500 us beyond gettimer ≤ 20000 for the 360-us overhead, and there is no gettimer in the shot. |
| H2 (validation inside the RF play macro) | **Resolved.** RF validation runs at setup. `V19_RF_GO` is timer-anchored, and the RF start is relative to the block `starttimer`. |
| H3 (PDD masks) | **Resolved.** tx is set at every method RF block start and rx after `rfon(0)`. The post-RF window is now 20 us (an earlier 5-us version would have overrun; see i7). |
| A2 (unrealised instruction reserves) | **Partially resolved.** All events now sit in padded windows. Remaining: B1 (one window far too small), M2 (5-ms timer boundary), m1 (uncalibrated anchor and initiate constants). |
| A3 (arithmetic after a pre-RF wait) | **Resolved for RF blocks.** Multipliers are precomputed, and the loop-top `pr()`/`CREATE_MATRIX` run inside the pre-RF padded window. The same class of defect reappears in the post-initiate window (B1). |
| P6 (C±D does not recall echo 1) | **Resolved by redesign.** Crushers are symmetric C/C. +D and -D are carried by identical `POSPULSE_SEC(tdp)` lobes before and after every ADC. The amplitude is correct only once M1 is fixed. |
| P1/P3 | Resolved: methods are implemented and the PPRs use ETL = 8 with v19_on = 1. P2/P5: static events exist; compiler, console and physical verification remain open. |

## 5. Verdict

The structure is sound: the control path is preserved, rejection happens before events, matrix and list ordering is correct, and phases and recall signs are consistent. The sequences are **not ready to compile/run** until B1 is fixed (the readout window is underbudgeted by about 250 us, which costs +5 ms per echo) and M1-M3 are addressed. After fixes, the minimum validation is:

1. a vendor compile of both files with v19_on = 0, checking event-for-event identity with v18;
2. a console scope trace of RF gate, ADC gate and gradient start, to calibrate the m1 constants and confirm that no waittimer overruns occur.
