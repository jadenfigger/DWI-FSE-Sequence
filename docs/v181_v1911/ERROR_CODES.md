# Error codes and rejection messages: v1.81 and v1.911

Source-validated candidates; **not vendor-compiled or scanner-verified**. All rejections below occur before any RF pulse or ADC (verified in the source mapper with RF count 0 and ADC count 0, normal and `validate=1` paths unless stated). Final bytes: v1.81 PPL `545a14ec8c65ed578ea76628796547dd463eb8cd4a2efa680de89058a837de69`, v1.911 PPL `716478bb357ba1479e6cc8fcc18c1085e44b3c78ecf1bdf32bb561b171838682`.

## 1. v1.81: text messages (no numeric codes)

v1.81 inherits **every v1.8 message text unchanged** (v1.8 prints text, not codes). The following are new in v1.81. The console shows the message in the PPL output and the scan does not start.

| Message (exact) | Meaning | Remedy |
|---|---|---|
| `V181 DWI requires flow compensation off` | `diff_on == 1` with `flow_comp_on != 0`. The relocated read prephaser is not a flow-compensated waveform. Checked before the validate exit, so it also appears in validate mode. | Turn flow compensation off for diffusion scans, or use v1.8 |
| `V181 CEST/MTC not supported` | `mtc_on != 0`. The CEST/MTC code is compiled out of v1.81 (the parameters still exist so old protocols load). Checked before the validate exit. | Set `mtc_on` to 0, or use v1.8 for CEST |
| `V181 ESP leaves no read balance` | Diffusion off: the pre-read balance (`te_balance_bl_temp1`, now 81.5 us tighter than v1.8) is <= 25 ticks. | Increase ESP/TE |
| `V181 ESP leaves no train read balance` | Diffusion on, ETL > 1: the train read balance (`te_balance_bl_temp1_esp`) is <= 25 ticks. | Increase ESP (the extra 81.5 us pays for the 100-us slice-list restart window) |
| `V181 read relocation scale outside DAC` | The scaled relocated prephase `grp_dp*(tref+tramp)/(tdp+tramp)` is outside +/-32767. | Reduce the read prephase/compensation demand or lengthen the read prephase time |
| `V181 first read prephase exceeds DAC` | The fused first read prelude amplitude (`gr_dp` minus the scaled relocated lobe, absolute value) exceeds 32767 or `crusher_max_dac`. | Reduce read amplitude/FOV demand, or raise `crusher_max_dac` only within hardware limits |
| `V181 first read prephase exceeds slew` | The same lobe exceeds `crusher_slew_dac_100us` over `tramp` (test: amplitude*100 > slew*tramp). | Lengthen `tramp` or raise the slew ceiling only within hardware limits |

Changed behaviour of inherited v1.8 messages (text unchanged):

| Message | Change in v1.81 |
|---|---|
| `TR too short, increase to N ms` | The TR floor includes +895 us (11350 -> 12245), so the minimum accepted TR for the test1e protocol is 174 ms (v1.8: 173 ms) |
| `Matrix setup exceeds timing budget` | Threshold 24500 -> 27250 ticks for the enlarged 3275-us matrix window |
| `TE too short: first-echo balance = N ticks` | The balance now carries -815 ticks (81.5 us) for the slice-list restart window, so the shortest accepted TE/ESP is 81.5 us longer |
| `TE too short: pre-180 balance = N ticks` | Unchanged formula |

Inherited and not fixed: the `diff_tramp != tramp` check is skipped under `validate=1` (the validator prints a `Duration=...` value instead of rejecting; the normal path rejects it).

Message priority for multi-fault protocols changed slightly: `mtc_on=1` with a too-short TE now reports the CEST message; under `validate=1`, diffusion with flow compensation reports the flow-compensation message instead of an incidental TE message.

## 2. v1.911: how errors appear

Fatal rejections print `V19 error E<number>` (v7 compact scheme) and exit before any RF. The meaning of E1-E123 is the **v7 table in section 5, unchanged** (the table shipped with v7 describes v1.91; do not use the v6 table). Some codes now fire under different conditions; those and the new codes E140-E146 are listed below. Codes E124-E139 are unused. Non-coded messages that remain: `TR too short, increase to N ms` (N = 193 for the default protocol; v7: 199) and the v1.8 text messages emitted inside inherited helper blocks.

## 3. New codes E140-E146 (v1.911 only)

Checks run in the setup block just before the first list is built, in this order: E146, E140, E145, E141, E142. E143 and E144 come later in the timing section.

| Code | Meaning (what the source tests) | Reachable? Evidence | Remedy |
|---|---|---|---|
| **E140** | Fused-lobe geometry or gradient-lag assumption violated: `tramp != 200`, `tdp != 700`, `tcrush != 1000`, `rfdelay != 60`, or the imaging selector plateau `v19_f_im != 1320`. The fused lobes (1328-us tops, 200-us ramps) were audited only for this geometry. | **Yes** for `rfdelay` (50 and 70 tested) and `tref_setup = 800` (changes `tdp`). `tramp` and `tcrush` changes are normally stopped earlier by E82 / E18 (tramp 300 gives E82; tcrush 1200 gives E18). `v19_f_im` is not exercised by a tested parameter | Restore tramp 200, tcrush 1000, rfdelay 60 and the default `tref_setup`; or use v1.91 |
| **E141** | A fused DAC value is outside `[crusher_saved_train, 0)`: the first, pre-RF or post-RF fused amplitude would be more negative than the validated train crusher, or non-negative. | **Not reached** in any test. Positive-polarity and large crushers stop at E18 first; in the validated C/D = 3.83 window the fused peak (8146 DAC) is below the crusher (8223) | Use negative crusher polarity within the validated window |
| **E142** | Integer-DAC rounding residual of a fused lobe area exceeds 0.01 % of \|D\| (about 258 DAC.us, 0.2 cycles/m). One test each for the first, pre-RF and post-RF lobe. | **Yes, readily.** Mapper probe at manual x0.8: near the default only `crush_amp` = -8242, -8237, -8233, -8228, -8223, -8219, -8214, -8209, -8205 are accepted (spacing about 4.6 DAC); every other integer from -8245 to -8201 gives E142. `diff_crush_amp` -5500 to -5466 is not affected | Use the shipped `crush_amp` (-8223) or another lattice value; do not hand-tune the train crusher |
| **E143** | The remaining wait between the first-RF read lists and the ADC (`v19_rem_im`) is outside 300..49000 ticks: ESP too short (or too long) for the fused geometry. | **Yes**: ESP 8, 9, 10 and 21 give E143; `sample_period 1000` and `no_samples 256` also give E143 (readout too long) | Use ESP 13 and the shipped sampling |
| **E144** | `esp != 13`, or the terminal-timer allowance fails (`10000 + 10*tfilter + 3000 > 24000`, that is tfilter > 1100 us). | **ESP clause: yes** (ESP 14, 15, 16 give E144; ESP 17-20 give E31; ESP 11-12 give E32 first). **tfilter clause: effectively dead** (E32 stops the shot at an acquisition pad of about 5500 ticks, long before 1100 us) | Set ESP 13. Only ESP 13 was audited for this fused geometry |
| **E145** | `-(C_area + D_area) > 21,474,000` DAC.us: the area is too large for the signed 32-bit scaling used to compute the fused DACs (the guard keeps the rounded numerator at or below 2,147,476,496). | **Not reached** (shadowed by E17 / E18 / E142 in all tested cases); defensive | Reduce crusher/dephasing amplitude |
| **E146** | Any nonzero `subj_angle_x/y/z`, `r_angle_var[0]`, `p_angle_var[0]`, `s_angle_var[0]` or `phase_var`. Fused S lobes run concurrently with P/R lobes and the physical-axis sums for oblique orientations were not audited; the ledger does not rotate axes. | **Yes** (all seven tested). Elements `[1..]` of the angle arrays are not checked (unreachable with the single-slice E3 restriction) | Use an unrotated orthogonal geometry, or use v1.91 |

## 4. Inherited codes whose trigger changed in v1.911

| Code | v7 meaning | What changed |
|---|---|---|
| **E31** | ESP too short after method block or before readout | The imaging-gap clause is now a constant 200 ticks against the minimum 20 x 10 = 200 ticks, so it can never fire. Remaining triggers: `v19_s_1 - v19_len < 20` or `v19_first_wait > 49000`. In practice ESP 17-20 (too long) give E31 |
| **E32** | ESP/ADC too short for readout and restoration | The post-ADC conditions now compare against the receiver flush `10000 + 10*tfilter + 1000` ticks instead of the v7 tail. **ESP 11 and 12 now give E32 (v7: E31)**; this is the code that rejects ESP 12 |
| **E34** | ESP too short for crusher + readout | New inequality: `v19_e_1 + 3*v19_r + tdp < v19_s_1 + 2656 + v19_f_im + 6*v19_r + 20` |
| E30, E33, E35-E37 | unchanged | Unchanged conditions |
| Other E1-E123 | see section 5 | Unchanged |

ESP lookup for the default protocol (manual x0.8 model): 8-10 -> E143; 11-12 -> E32; **13 accepted**; 14-16 -> E144; 17-20 -> E31; 21 -> E143. All 19 original method-only rejection tests return the same codes as v7 except ESP-too-short (E31 -> E32) and the TR message.

## 5. Complete v1.911 table, E1-E123 (unchanged v7 / v1.91 numbering)

Numeric values formerly embedded in messages are omitted ([value]). Copied unchanged from `docs/v181_v1911/baseline_v7/v19_error_codes.txt` (v191 section).

| Code | Meaning |
|---|---|
| E1 | V19 needs DWI ON, independent constant crushers, DE OFF |
| E2 | V19 rejects flow comp, Dixon, 3D, skipped echoes, TREF setup |
| E3 | V19 supports one centred slice (fixed tx frequency for all widths) |
| E4 | V19 rejects presat, CHESS, CEST, gating and TR arrays |
| E5 | V19 needs slice/read ON, gsp_lobe 0, no post-90/phcor0 trims |
| E6 | V19 needs ETL 1..64 and 1..8 dephasing cycles |
| E7 | V19 supports only 2 dephasing cycles; re-validate other values with examples/v19_validate_events.py |
| E8 | V19 needs diff_tramp=tramp, rfgate_delay>=17, tramp+rfdelay>=163 us |
| E9 | V19 slice selector outside 1..12000 DAC, or warmup outside 0..200 us |
| E10 | V19 compensation flat must be a multiple of tramp/50 |
| E11 | V19 tdp and little delta-tramp must be multiples of tramp/50 |
| E12 | V19 RF multiplier outside 1..2047 |
| E13 | V19 refocusing flip [value] outside 0.1..180 deg |
| E14 | V19 selector DAC [value] outside amplitude/slew ceiling |
| E15 | V19 added-dephasing DAC [value] outside ceiling |
| E16 | V19 needs a nonzero train crusher |
| E17 | V19 train crusher area must be >= 3x added dephasing (C=[value], D=[value] DAC.us) |
| E18 | V19 crusher geometry unvalidated; use C/D=3.83 and C1/D=2.55, then re-validate with examples/v19_validate_events.py |
| E19 | V19 needs imaging <= tip-up <= slab width |
| E20 | V19 compensation DAC [value] outside amplitude/slew ceiling |
| E21 | V19 spoiler amplitude outside ceiling |
| E22 | V19 spoiler moment too large for this gradient |
| E23 | V19 spoiler flat [value] us outside tramp..6000 us |
| E24 | V19 RF block window infeasible (rf [value]) |
| E25 | V19 RF block window infeasible (rf [value]) |
| E26 | V19 RF block window infeasible (rf [value]) |
| E27 | V19 RF block window infeasible (rf [value]) |
| E28 | V19 RF block window infeasible (rf [value]) |
| E29 | V19 spoiler window [value] us exceeds the 4.9-ms timer budget; raise spoiler DAC |
| E30 | V19 TE/Delta/delta too short for prep (gaps [value] [value] [value] [value] ticks) |
| E31 | V19 ESP too short after method block or before readout ([value] [value]) |
| E32 | V19 ESP/ADC too short for readout and restoration ([value] [value] [value]) |
| E33 | V19 readout/imaging/D windows outside budget (need 2*tramp+tdp>=400 us) |
| E34 | V19 ESP too short for crusher + readout |
| E35 | V19 matrix window 1 overrun |
| E36 | V19 read prephaser DAC [value] outside ceiling |
| E37 | V19 matrix window 2 overrun |
| E38 | V19 method-only PPL: v19_on must be 1 |
| E39 | V19 needs 1..64 diffusion acquisitions |
| E40 | Illegal parameter |
| E41 | Illegal parameter (2) |
| E42 | Illegal parameter (3) |
| E43 | No expts should be divisible by no of diffusion acqs ([value]) |
| E44 | Set the Experiment Array Size to [value] |
| E45 | Invalid diffusion scale |
| E46 | Invalid diffusion direction |
| E47 | all directions normalised to 1000 |
| E48 | b-value mode needs delta <= 10 ms and Delta <= 80 ms |
| E49 | Max b = [value]. Raise delta, Delta or grads |
| E50 | b-value DAC search did not converge |
| E51 | b-value DAC conversion outside array limits |
| E52 | Diffusion DAC exceeds limit |
| E53 | Diffusion DAC overflows int |
| E54 | Views (including navigator) must be 1..[value]; ETL must be 1..views |
| E55 | Base TE (esp) be a multiple of eff. echo time (TE) when Diffusion is OFF |
| E56 | Set PE order to 1, 5, 6 or 7 for DWI |
| E57 | Set Driven Equilibrium OFF when Diffusion is ON |
| E58 | PE 6/7 requires DWI ON, ETL > 1, and no discarded echoes |
| E59 | PE 6/7 requires full Fourier: PF echoes = 0 or ETL |
| E60 | Unsupported PE order |
| E61 | Navigator leaves no imaging views |
| E62 | Effective number of views must be even number |
| E63 | PF eff echoes must be >= VPS |
| E64 | PF eff echoes must be < 2*VPS |
| E65 | no_views must be > te_eff |
| E66 | te_eff must be >0 |
| E67 | The eff echo time is too large |
| E68 | Set PE order to 5 for single echo |
| E69 | Set Echo train to 1 for single echo |
| E70 | Number of views / (2*views per segment) must be an integer |
| E71 | Linear interleaved requires imaging views divisible by ETL |
| E72 | Minimum echo train length is 4 for selected PE order |
| E73 | PE order 0 exceeds scratch table capacity |
| E74 | PE order 0 exceeds GP table capacity |
| E75 | Internal PE table length error |
| E76 | Navigators are not supported with selected PE order |
| E77 | Views per segment (ETL) must be equal number of Views for this PE order |
| E78 | Sampling time too long |
| E79 | Independent crusher switch must be 0 or 1 |
| E80 | Independent crushers require ramp 100..1000 us, multiple of 10 |
| E81 | Crusher amplitudes must be -32767..32767 DAC |
| E82 | tcrush must be 1..5000 us and an exact multiple of tramp/50 us |
| E83 | diff_tcrush must be 1..10000 us and an exact multiple of tramp/50 us |
| E84 | Independent crushers require Driven Equilibrium OFF |
| E85 | Invalid independent-crusher RF timing |
| E86 | Independent-crusher RF plateau overflow |
| E87 | Invalid crusher schedule or additive step |
| E88 | Crusher ETL exceeds storage capacity |
| E89 | Scheduled crushers require independent mode, DE OFF, no skipped echoes |
| E90 | Crusher orientation count exceeds storage |
| E91 | Invalid scheduled-crusher sampling parameters |
| E92 | ADC window too short for scheduled crusher update |
| E93 | Crusher amplitude/slew ceilings must be positive |
| E94 | Custom crusher count must equal ETL and be 1..64 |
| E95 | Custom crusher storage contains invalid percentage |
| E96 | Crusher progression overflow |
| E97 | Invalid custom crusher percentage |
| E98 | Crusher magnitude product overflow |
| E99 | Crusher amplitude exceeds DAC/gradient ceiling |
| E100 | Crusher ramp exceeds slew ceiling |
| E101 | Refocus wait exceeds timer range |
| E102 | No of slices should be an integer number of batch size |
| E103 | Can't do phase oversampling with rect FOV - adjust FOVf! |
| E104 | FOV too small in PE dir |
| E105 | FOV too small in slice direction |
| E106 | Slice thickness too small for pulse selected |
| E107 | FOV too small for read comp |
| E108 | Flow comp grad amp caused overflow |
| E109 | Decrease bw or select a longer pulse |
| E110 | PB [[value]] thk too small! |
| E111 | Pre-sat block thk too small! |
| E112 | Number of experiments must be 3 in W-F mode! |
| E113 | Exper array size ([value]) must be divisable by the TR array size ([value])! |
| E114 | Crusher update exceeds reserved ADC instruction budget |
| E115 | Diffusion gradient amp [value]DAC is too high |
| E116 | diff_tramp ([value] us) must equal tramp ([value] us) for consistent DW timing |
| E117 | Reduce receive frequency |
| E118 | Inter-CEST delay too short, extend by [value] ms |
| E119 | , or decrease number of slices (batch) to [value] |
| E120 | Reduce slice grad comp |
| E121 | FOV in slice direction too small |
| E122 | Reduce read grad comp |
| E123 | Matrix setup exceeds timing budget |
| E124-E139 | unused |
| E140-E146 | see section 3 |

## 6. Common situations

| You see | Most likely cause | Do this |
|---|---|---|
| v1.911: E142 after editing the train crusher | `crush_amp` off the integer-rounding lattice | Restore -8223 |
| v1.911: E144 | ESP is not 13 | Set ESP 13 (the shipped PPR already does) |
| v1.911: E146 | A slice angle or orientation swap is set | Zero all angles, `phase_var` 0 |
| v1.911: E38 | `v19_on` is not 1 (method-only PPL) | Use the shipped v1.911 PPR; controls use the v1.8 PPL |
| v1.911: E39 | `no_diff_acq` not in 1..64 | Use the shipped 64-row PPR |
| v1.911: E17 / E18 | Crusher area or ratios outside the validated window (\|C\|/\|D\| = 3.83, \|C1\|/\|D\| = 2.55) | Restore shipped crusher values |
| v1.81: `V181 ... read balance` | ESP/TE too short by the 81.5 us added to the slice-list restart | Raise ESP or TE by 0.1 ms |
| v1.81: `TR too short, increase to N ms` | TR floor is 0.895 ms higher than v1.8 | Use the printed N |
| Either: a shot that is 5 ms longer than predicted, or a hang | A `waittimer` window slipped or a 16-bit timer argument was mis-read (`FINAL_REPORT.md` section 11.1) | Apply the split-wait fallback in `SCANNER_TEST_PLAN.md` and report |
