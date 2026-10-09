# v1.81 review fixes (M1, m1)

Writer record, 8 October 2026. Source-level mapper and audit evidence only; no vendor cpp/PPLC/Forth compile, console or scanner run exists. Not self-approved; independent re-review required.

## Identity

| Object | SHA-256 |
|---|---|
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl` before (reviewed) | `9fca0a13eb773d0e06d7bde0175dff4a3cd84d705db4211717fee9d23168f8b1` |
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl` after | `545a14ec8c65ed578ea76628796547dd463eb8cd4a2efa680de89058a837de69` |
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppr` (unchanged) | `ad82112ddfc7389a58caea6598cb5eb7583a271e71e62cd8c006190c52cdb159` |
| `examples/build_v181_ppl.py` before / after | `d8178506016e24aa44912d6438131aa261d98790e0058d50ffab93071e2978b8` / `9d169b5681bcfcc02e612f88a92ccba6c57e7882be9a097ae51af38b52e4fb7e` |

The builder was run twice; both runs gave the same PPL and PPR hashes.

## M1: no empty `{ }` bodies

Each of the three `if(mtc_on){` shells now contains `goto end;` as its only compiled statement (the CEST body stays compiled out by `#ifdef MTC`).

Reachability finding: the review assumed `mtc_on!=0` was rejected before all three shells. It was not: the first shell (frequency setup, v1.81 line 2603) precedes the old rejection at line 3180, so a bare `goto end;` there would have exited silently for `mtc_on=1` and changed the printed message. To keep the claim true and the message byte-identical, the existing rejection (`if (mtc_on!=0) { printf("V181 CEST/MTC not supported\n"); goto end; }`) was moved, not duplicated, to just before the first `#ifdef VALIDATOR` jump (setup, before `averages_loop`). That point precedes all three shells and runs on both normal and validate paths. The old copy near the CEST TR term was removed. All three new `goto end;` are unreachable at run time.

`goto end` is backward: `end:` is the early hub at line 555, and every shell is after line 2600. Hub semantics are unchanged: `end: goto v181_exit;` and `v181_exit:` is the original program epilogue label (formerly `end:` before the closing `}`), so each exit is the same early termination as before. Independent raw-text count: 18 forward gotos in the main file plus 3 in `tstex_15.pph` = 21 (unchanged).

## m1: guards on both normal and validate paths

Done. Messages are byte-identical.

| Guard | Old location | New location | Variables used, and where they are final |
|---|---|---|---|
| diffusion + flow comp | in `diff_acq_loop` (after the validate jump) | just before the early `#ifdef VALIDATOR` jump | `diff_on`, `flow_comp_on`: protocol parameters |
| `mtc_on` (see M1) | after `waittimer(19700)` | same place as above | `mtc_on`: parameter |
| read relocation scale outside DAC; first read prephase exceeds DAC; exceeds slew | after `waittimer(templ1)` | just before the second `#ifdef VALIDATOR` exit (after the flow-comp read-gradient block) | `gr_dp`, `grp_dp` (final after the flow-comp block), `tref`, `tdp` (set at 1574-1575), `tramp`, `crusher_max_dac`, `crusher_slew_dac_100us` (EDITTEXT parameters) |

The relocation block moved as a whole, including `v181_first_read_dp=gr_dp;` and the `scale()` result, so no arithmetic was duplicated (image estimate +16 bytes: the three goto statements and the relocated lines net of removed ones). `templ1`/`templ2` are scratch: `templ1` is reassigned by the validate print and by `if (flow_comp_on) templ1 = ...` before any use, and nothing reads `templ2` afterwards (checked by grep over the rest of the file).

### Cost: timing window moved (read this)

The relocation arithmetic now runs in the 3.25-ms real-time window that ends at `waittimer(templ1)` (32500 ticks, 42500 with flow comp) instead of in the matrix-setup window that ends at `waittimer(32750)`. Mapper window use, diffusion on, default protocol, ticks:

| Cost model | `waittimer(32500)` used, before -> after | `waittimer(32750)` used, before -> after |
|---|---|---|
| manual x0.8 | 22646 -> 24263 | 23260 -> 21628 |
| manual x1.0 | 28261 -> 30243 | 23727 -> 21727 |

Slack on the 32500 window falls from 4239 to 2257 ticks (226 us) at manual x1.0 and from 9854 to 8237 ticks at x0.8; the 32750 window gains about 2000 ticks. Scaling the manual expression costs, the first `timer_overrun` in the whole sequence moves from x1.09 (an inherited `waittimer(8997)` window) to x1.08 (the 32500 window). No overrun at x1.0 or x1.05 in either version. If this trade is not acceptable, the alternative is to leave the relocation guards where they were and duplicate them inside the `validate==1` block (image cost not measured; estimated above the 163-byte margin), or accept the validator gap.

## Results (all source-model only)

* Builder reproducibility: two builds identical (hashes above).
* Static audit (`examples/v181_v1911_static_audit.py`): pass; `estimated_image_bytes` 56517 (limit 56664, was 56501); forward gotos 21; predicted W007/W008 warnings 11 with identical identities (`new_warning_signatures` empty); largest conditional body 369 nodes; no undefined or unreferenced labels; no added long literals, risky comments or function macros.
* Event timing vs `9fca0a13` (`review_checks/compaction_reltime.py`, 3 states x 8 cost models = 24 cases, times relative to the first RF): RF, ADC and S/P/R gradient events all have max time difference 0.0 us and zero non-time mismatches; flag kinds identical (`matrix_active`, `narrowing`); zero bad flags. Output: `review_checks/v181_fix_reltime.json`.
* `compaction_equiv.py` (absolute times; `v181_fix_equiv.json`): RF count, ADC count, `flags` and `t_end` identical in the four flat models; only matrix-creation timestamps and matrix-select history differ (15.6 us earlier in the flat models: pre-RF setup writes under the zero matrix, caused by removing the `scale()` call cost from the later window). In the manual models the one-time setup offset moves the first RF and `t_end` by +4.7 to +5.9 us (relative timing identical as above). The `mtc_on` and `flow_comp_dwi` cases differ only in `t_end`/`misc`/`printf` (both rejected before RF, 0 RF and 0 ADC, same message).
* `compaction_reject.py` (`v181_fix_reject.json`): 43 rejection cases (38 unsafe plus CEST variants and validator): messages identical to `9fca0a13`, 0 RF and 0 ADC in all.
* `examples/validate_v181_guards.py` (run from a scratchpad copy with output redirected so shared validation files were not overwritten): 38/38 unsafe protocols rejected with no RF/ADC, all 6 crusher schedules pass in all 8 cost models, `reproducible` true, `moment_error` -0.233 cycles/m (unchanged). `all_pass` is false only because of the inherited 60-us gradient-lag sensitivity cases (flat_0us, flat_0.5us, manual_x0.8: SetList on an active channel); the same three cases fail on `9fca0a13` with identical flag times, and in the earlier recorded `validation/v181_guards.json`.
* `examples/validate_v181_v1911.py` (also a scratchpad copy with redirected output): `event_gates_pass` true, 0 failures; v1.81 rejections 2/2 (CEST/MTC, diffusion with flow comp); v1.81 minimum accepted TR 174 ms with 0 timer overruns and 0 ignored lists in manual x0.8, x1.0 and flat_2us; v1.81 hazards, ADC states, shots and moments identical to the previously recorded `validation/` files. The v1.911 part of that run belongs to the other agent's file and is not part of this record.
* Validate mode (`validate=1`), before -> after: `new_first_read_DAC_ceiling` printed `Duration=126000`, now `V181 first read prephase exceeds DAC`; `new_first_read_slew_ceiling` printed `Duration=126000`, now `V181 first read prephase exceeds slew`; `diffusion_flow_compensation` was rejected only by the incidental "TE too short" check, now `V181 DWI requires flow compensation off`. Normal-path (`validate=0`) messages unchanged. Remaining validate gap: the inherited `diff_tramp != tramp` guard (case `ramp_mismatch`) still prints `Duration=126000` under validate (out of scope; no RF is played in validate).

## Not claimed

PPLC acceptance of `goto end;` as the sole statement of an `if(...){ }` body is not proven by a compile, but the same `{ ...; goto end; }` shape is used throughout the file. Image size, warnings and timing remain scanner-verify.

## Exact diff vs `9fca0a13` (CR-stripped)

```diff
@@ -2106,6 +2106,12 @@
 		if (report_on==1) printf("Crusher update max=%ld ticks; reserved extra=10000 ticks\n",crusher_update_max_ticks);
 	}
 
+	// V181: the relocated read prephase is not a flow-compensated waveform.
+	if ((diff_on==1)&&(flow_comp_on!=0))
+	{ printf("V181 DWI requires flow compensation off\n"); goto end; }
+	if (mtc_on!=0)
+	{ printf("V181 CEST/MTC not supported\n"); goto end; }
+
 #ifdef VALIDATOR
 	if (validate==1)
 	{
@@ -2406,11 +2412,7 @@
 		goto end;
 	}
 	
-	// V181: the relocated read prephase is not a flow-compensated waveform.
-	if ((diff_on==1)&&(flow_comp_on!=0))
-	{ printf("V181 DWI requires flow compensation off\n"); goto end; }
 	// Set diffusion gradient strengths according to matrix directions, assume matrix is normalized to a value of 1000.
-
 	tcrush1 = tcrush;
 	// Check if the diffusion gradients are zero; if they are, we switch the diffusion part off
 	diff_non_zero = 0;
@@ -2601,6 +2603,7 @@
 #endif
 
     if(mtc_on){
+		goto end;
 #ifdef MTC
         frequency_buffer(5);   
         frequency(MHz, kHz, Hz, rx1MHz);
@@ -3177,13 +3180,12 @@
 	   10+ ms per slice. Diffusion mode now flows through the ENTIRE legacy
 	   overhead chain; only the part-1 term above differs. */
 	\\printf("tr_min = %ld\n",tr_min);
-	if (mtc_on!=0)
-	{ printf("V181 CEST/MTC not supported\n"); goto end; }
 	
 	
 	templ1 = (no_cest_pulses*tselmtcl + (no_cest_pulses-1)*IntToLong(inter_cest_delay)*1000L + IntToLong(mtc_tcrush+2*tramp) + IntToLong(post_cest_delay)*1000L);	
 	// Calculate the inter-CEST-pulse delay 
     if(mtc_on){
+		goto end;
 #ifdef MTC
 		// Should remain in us!
 		tr_min = tr_min + templ1;
@@ -3337,6 +3339,26 @@
 		grp_dp = -gr_flow;
 	}
 	
+	// V181: an RF conjugates the old negative read prephase. Play its
+	// positive equivalent in the first read-list prelude after diffusion.
+	// Both use the same secondary ramp samples; only the plateau changes.
+	// Checked before the validate exit so validate and played paths agree.
+	v181_first_read_dp=gr_dp;
+	if (diff_on==1)
+	{
+		templ1=IntToLong(grp_dp)*(IntToLong(tref)+IntToLong(tramp));
+		templ1=templ1/(IntToLong(tdp)+IntToLong(tramp));
+		if ((templ1<-32767L)||(templ1>32767L))
+		{ printf("V181 read relocation scale outside DAC\n"); goto end; }
+		templ2=IntToLong(gr_dp)-templ1;
+		if (templ2<0L) templ2=0L-templ2;
+		if ((templ2>32767L)||(templ2>IntToLong(crusher_max_dac)))
+		{ printf("V181 first read prephase exceeds DAC\n"); goto end; }
+		if (templ2*100L>IntToLong(crusher_slew_dac_100us)*IntToLong(tramp))
+		{ printf("V181 first read prephase exceeds slew\n"); goto end; }
+		v181_first_read_dp=gr_dp-scale(grp_dp,tref+tramp,tdp+tramp);
+	}
+
 #ifdef VALIDATOR
 	if (validate==1)
 	{
@@ -3361,24 +3383,6 @@
 	// Long multiplication and the echo branch must NOT follow gettimer()+250.
 	post_adc_base_ticks=te_balance_bl_temp2*10L;
 	post_adc_train_ticks=(te_balance_bl_temp2+te_balance_bl_esp+IntToLong(crush_post_pad-crush_pre_pad))*10L;
-	// V181: an RF conjugates the old negative read prephase. Play its
-	// positive equivalent in the first read-list prelude after diffusion.
-	// Both use the same secondary ramp samples; only the plateau changes.
-	v181_first_read_dp=gr_dp;
-	if (diff_on==1)
-	{
-		templ1=IntToLong(grp_dp)*(IntToLong(tref)+IntToLong(tramp));
-		templ1=templ1/(IntToLong(tdp)+IntToLong(tramp));
-		if ((templ1<-32767L)||(templ1>32767L))
-		{ printf("V181 read relocation scale outside DAC\n"); goto end; }
-		templ2=IntToLong(gr_dp)-templ1;
-		if (templ2<0L) templ2=0L-templ2;
-		if ((templ2>32767L)||(templ2>IntToLong(crusher_max_dac)))
-		{ printf("V181 first read prephase exceeds DAC\n"); goto end; }
-		if (templ2*100L>IntToLong(crusher_slew_dac_100us)*IntToLong(tramp))
-		{ printf("V181 first read prephase exceeds slew\n"); goto end; }
-		v181_first_read_dp=gr_dp-scale(grp_dp,tref+tramp,tdp+tramp);
-	}
 	G1 = grp_dp; /* if flow_comp_on = 0 */
 	if (diff_on==1) G1=0;
 
@@ -3561,6 +3565,7 @@
 	MR3040_Clock(clock);
 	
     if(mtc_on){
+		goto end;
 #ifdef MTC
 		cest_count = 0;								\\ CEST pulse loop counter
 		cest_loop:
```
