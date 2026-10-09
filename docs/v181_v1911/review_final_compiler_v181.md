# Independent final compiler/PPL review: DW-FSE v1.81

Reviewer: independent adversarial PPL/compiler reviewer (did not write the code). Date: 2026-10-08.
Scope: source-level and repository-mapper review only. No vendor cpp/PPLC/Forth compile, console or scanner run exists. Nothing below is a vendor-compile or scanner verification.

## Input identity (verified before any other work)

| Object | SHA-256 | Match |
|---|---|---|
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl` | `9fca0a13eb773d0e06d7bde0175dff4a3cd84d705db4211717fee9d23168f8b1` | yes |
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppr` | `ad82112ddfc7389a58caea6598cb5eb7583a271e71e62cd8c006190c52cdb159` | yes (author record) |
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl` (baseline) | `3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2` | yes |
| `examples/build_v181_ppl.py` | `d8178506016e24aa44912d6438131aa261d98790e0058d50ffab93071e2978b8` | yes |
| `examples/v181_v1911_static_audit.py` | `4db7b7d1bad2dd7adb53c2518c21d1ca812ff5dfad61dae5d7571763c706d624` | (unchanged tool) |

I wrote nothing except this file (scratch probes went to the session scratchpad). `git status` is unchanged: only the pre-existing untracked candidate files; `git diff --stat` is empty (no tracked file changed).

## Verdict

**No blocker found in the source. One major finding (M1: first-of-its-kind empty `{ }` bodies, a compile risk absent from every previously compiled source) and several minor/note findings.** I recommend fixing M1 (a one-line-class change) before the console upload. All the numeric gates the author reported reproduce on the final bytes. All of this remains scanner-verify.

## Pass/fail summary

| # | Check | Result |
|---|---|---|
| 1 | Rebuild reproducibility | PASS |
| 2 | Full v1.8 -> v1.81 hunk enumeration | PASS (every hunk explained; 1 derived addition noted) |
| 3 | Compiler constraints | PASS with M1 (empty-body shells) and minor notes |
| 4 | Guards before first RF, normal and validate paths | PASS for RF safety; validate path skips 4 V181 guards (minor, m1) |
| 5 | Static audit rerun | PASS (56501 <= 56664; 21 forward gotos; 11 warnings; 369 nodes) |
| 6 | Negative secondary read ramp area math | PASS |

## 1. Rebuild reproducibility: PASS

I imported `examples/build_v181_ppl.py` and called only `generate_ppl()` and `generate_ppr()` (never `build()`/`main`, which write files), converted `\n` to `\r\n`, latin-1 encoded, and compared with the on-disk files.

- PPL: regenerated sha256 `9fca0a13...f8b1`, `bytes == file`: True.
- PPR: regenerated sha256 `ad82112d...cb159`, `bytes == file`: True.
- The builder verifies the v1.8 hash (`BASE_SHA256`, builder lines 16, 24-26) and the acquired test1e PPR hash (line 17) and asserts the exact anchor count on every replacement (builder `replace()`), so a drifting baseline fails loudly. Files are CRLF throughout (4874 lines, 4874 CRLF); non-ASCII bytes (128,147,178,194,226) are inherited.
- PPR check: `diff` against `experiments/FSE-DWI_10-05-2026_v18_test1e/FSE-DWI_10-05-2026_v18_test1.ppr` shows exactly one changed line (line 1, `:PPL G:\J_Figger\...-1.81.ppl`). Note (n4): the v1.81 PPR is the acquired test1e protocol, not `scanner/...-1.8.ppr`, so it differs from the repository v1.8 PPR in views/ETL/orientation etc. This is intended (acquired control) but should be stated in release notes.

## 2. Full diff v1.8 -> v1.81 (all hunks; `diff` of CR-stripped files, 151 diff lines)

Line numbers refer to the v1.81 file.

| Hunk (v1.81 lines) | Content | Explained by |
|---|---|---|
| 18-23 | header comment (inside the existing `/* */` banner; no `*/` or `//`-macro hazard) | documentation |
| 258 (removed) | `#define MTC` | CEST/MTC removal |
| 378-379 | `int v181_first_read_dp, v181_read_dp;` | read-prephaser relocation |
| 554-558 | `goto v181_run; end: goto v181_exit; v181_run:` and old `end:` -> `v181_exit:` (4373 -> 4423) | backward exit hub (same pattern as v1.91 lines 607-609) |
| 1570-1573 (was 1559-1563) | `#ifdef MTC ... #endif` removed around `tselmtcl`, `mtc_rfnum=17`, `rwt[17]` so they stay unconditional | CEST removal (keeps `rwt[17]` setup) |
| 2409-2411 | `diff_on==1 && flow_comp_on!=0` -> "V181 DWI requires flow compensation off" | diffusion+flow-comp rejection |
| 2603-2616 (+3186-3198, 3563-3623 same shape) | `if(mtc_on){` now followed by `#ifdef MTC`... block moved inside braces; bodies compiled out, empty shells remain | CEST removal (see M1) |
| 2862 | `waittimer(5300)` -> `waittimer(6500)` (+120 us) | enlarged pre-RF setup window (block-C deadline) |
| 3007 | `te_balance_bl_temp1 = ... - 210L - 815L` | slice-list restart 100-us window |
| 3051 | `te_balance_bl_temp1_esp = ... - 36L - 815L` | same |
| 3061-3066 | two "V181 ESP leaves no (train) read balance" guards | **derived, not in the checklist**: rejects configurations whose read balance goes <=25 ticks because of the extra 81.5 us; explained in compiler_v181_final.md table. Acceptable. |
| 3133, 3136 | comment and `11350L` -> `12245L` | +895 us TR floor (see arithmetic below) |
| 3180-3181 | `if (mtc_on!=0) { printf("V181 CEST/MTC not supported\n"); goto end; }` | mtc_on rejection |
| 3183-3198 | CEST TR block, bodies compiled out | CEST removal |
| 3351, 3353 | `37500L`->`42500L`, `27500`->`32500` (+500 us) | enlarged setup window |
| 3364-3382 | relocation math, three guards, `v181_first_read_dp=gr_dp-scale(...)`, `if (diff_on==1) G1=0;` | read-prephaser relocation |
| 3471 | threshold `24500` -> `27250`; 3466 comment; 3476 `waittimer(30000)` -> `waittimer(32750)` (+275 us) | enlarged matrix window with 550-us check reserve preserved |
| 3444-3446, 3564-3623 | `mtc_mat` CREATE_MATRIX and CEST pulse loop compiled out | CEST removal |
| 3922-3926 | `v181_read_dp` selection; `aq_mat_sec` uses `gr_on*v181_read_dp` (first echo of diffusion only) | relocation |
| 3986-3987, 3997 | `delay(50,us);` and `waittimer(210+temp-25)` -> `waittimer(1000)` | slice-list restart (100 us total window incl. 50 us settling) |
| cosmetic | one trailing tab removed (3990), blank lines added at 2413, 3069, 3926, 3992, 3383-3384 | none functional |

Arithmetic of the TR floor: +120 us (5300->6500) + 500 us (27500->32500) + 275 us (30000->32750) = 895 us = 12245 - 11350. The tick sum comment `31000+6500+19700+32500+32750 = 122450` is correct. The flow-comp variant (37500->42500) gets the same +500 us. Consistent.

Nothing unexplained. `PARAMLIST` (lines ~30-250) has no hunk, so it is unchanged (the CEST scrollbars at lines 190-203 stay, so old protocols load).

Mapper evidence (my own runs, `map_events` with v1.8 vs v1.81 on the v1.81 PPR, 2 shots):
- RF centre times relative to the first RF, and ADC times, identical (max difference 0.0 us) for: diff off, diff off + DE, diff on TE=60, diff on fixed TR=800 ms, flow-comp diff-off ESP 18, ETL 4 diff on/off, ETL 1 PE-order 5 diff on, in cost models flat_0us and manual_x0.8 (and x1.0 where it ran). The sole exception is a 10000-us difference under manual_x1.0 for two states, which is a v1.8 timer overrun (missed 5-ms periods) that v1.81 does not have.
- Hazard flags: v1.8 shows `gradient` flags (flat_0us) and `timer_overrun` flags (flat_1us, flat_2us, manual_x1.0, manual_x0.8+0.5us) in diff-on and diff-off; v1.81 shows none in any of these. In oblique/multislice/presat/slice-offset/schedule-3/CHESS states v1.81 is never worse than v1.8 (one inherited CHESS flat_2us timer_overrun remains in both; inherited `orientation`/`assumption` mapper flags are identical).
- Total TR (`t_end` over 2 shots) is unchanged except the first RF is ~11-16 us earlier (one-time setup no longer builds the CEST list/matrix).

## 3. Compiler constraints

| Constraint | Evidence | Result |
|---|---|---|
| Forward gotos <= 145 (E106 at 147) | Auditor: 21 (v1.8: 145). My independent raw-text count: 18 forward gotos (554, 556, 743, 803, 838, 1035-1044 x5, 1140, 1172, 1205, 1243, 1277, 1721, 2125, 3980); the other 3 are `goto end` inside `tstex_15.pph` (lines 15, 20, 26), included at line 541 before the `end:` hub at 555, so they are forward. Same pattern as v1.91 (607-609). All 113 `goto end` in the main file are backward. | PASS |
| Labels | All jump targets defined; no unreferenced labels; new names `v181_run`, `v181_exit` (<=31 chars). | PASS |
| Long literals | New printf strings max 40 chars (<=48). Auditor: no added long literals. I also scanned every added line: none >48. | PASS |
| Macros in `//` comments | Auditor: none. I independently checked all 44 function-like macro names against every added/changed line: the only hit is the real code line `CREATE_MATRIX(aq_mat_sec,...)` (3925), not a comment. No function-like `#define` added. | PASS |
| `#if/#endif` balance | Balanced (depth 0) in v1.8 and v1.81. | PASS |
| Warnings | 11 predicted W007/W008, identical identities to v1.8; no new `waittimer(long)`: `waittimer(1000)`, `waittimer(6500)`, `waittimer(32750)` are int literals; the 42500L/32500 windows still go through `waittimer(templ1)` which was an existing identity. | PASS |
| Largest conditional body | 369 nodes (<= 405 limit, unchanged). | PASS |
| Estimated image | 56501 bytes <= 56664. Model only; fixed overhead unknown. | PASS (model) |
| PARAMLIST | No hunk in PARAMLIST region. | PASS |
| PPR filename | One `:PPL` line changed; `...-1.81.ppl` matches. PPR has no new table rows (method table untouched; array bytes model unchanged at 16118). | PASS |
| Signed 32-bit / int16 overflow | See below. | PASS |
| Integer division / truncation | See below. | PASS with m3 |

Signed-arithmetic worst case for the new expressions (tref = 4*tref_setup, tref_setup <= 5000 per EDITTEXT, so tref <= 20000; tramp <= 1000; |grp_dp| <= 32768):
- `templ1 = IntToLong(grp_dp)*(IntToLong(tref)+IntToLong(tramp))` (3370): <= 32768 * 21000 = 6.9e8 < 2^31. Even with tref forced to 32767: 32768 * 33767 = 1.1e9 < 2^31. Promoted before multiplying, so no int16 intermediate.
- `templ1/(IntToLong(tdp)+IntToLong(tramp))` (3371): denominator >= 100+100 (EDITTEXT minima) and is the same denominator the inherited `grp_dp` and `gsp_rp` divisions use (3282, 3310); no division by zero not already present.
- `templ2 = IntToLong(gr_dp)-templ1` (3374): templ1 range-checked to +/-32767 first, so |templ2| <= 65535 in long.
- `templ2*100L` and `slew*tramp` (3378): <= 65535*100 = 6.6e6 and 32767*1000 = 3.3e7. Safe. Guard compares with `templ2 <= 32767` and `crusher_max_dac` first.
- `v181_first_read_dp = gr_dp - scale(grp_dp, tref+tramp, tdp+tramp)` (3380) is int arithmetic. `tref+tramp <= 21000` fits int16. The difference equals the guarded `templ2` so it is bounded by 32767. Safe unless vendor `scale()` rounds the quotient up to 32768 for a value in [32767.5, 32768), unreachable at default `crusher_max_dac` in practice (m3).
- `te_balance_bl*10L - 210L - 815L`, `12245L`, `122450` ticks: long, well below 2^31.
- `waittimer` literal arguments 6500/32750/1000 are <= 32767; 42500 (existing 37500 class) is a long variable narrowed to 16 bits exactly as before (< 50000, inside the 5-ms period, matching the historical use).

### M1 (major): three empty-body `if(mtc_on){ }` statements, a construct with no compiled precedent

Lines 2603, 3186, 3563. After preprocessing, `#define MTC` is gone, so each block reads `if ( mtc_on ) { }`. I ran the repository preprocessor over every scanner PPL: v1.3, 1.6, 1.7, 1.8, 1.91, 1.911 and 1.92 contain **zero** empty `{ }` pairs; v1.81 contains exactly these three. The project's own history is that each unproven construct has cost an upload. The author kept the shells only so the untimed statement cost, and hence the mapper's modeled timing, is unchanged.

Recommended fix (zero timing change, no new forward goto, a few image bytes of the 163-byte margin): put the already-existing guard statement inside each shell, for example `if(mtc_on){ goto end; }` (it is unreachable at run time because the earlier guard at 3180 rejects mtc_on!=0 before any of the three, and `end` is backward), then re-run the static audit, builder reproducibility and event-equivalence checks. A trivial assignment would also work but changes statement cost. I did not apply this because I may not edit the candidate.

### Compiler notes (none block)

- n1: The image gate has 163 bytes of modeled margin and the model has unknown fixed overhead; keep it conservative. After fixing M1 re-check the gate.
- n2: The v1.81 candidate has no dated entry in the in-file MODIFICATION HISTORY block (only the header at lines 18-23). Cosmetic.
- n3: `mtc_mat` (`#define mtc_mat 25`, line 583) and the MTC variables remain declared but unused; harmless.

## 4. Guards versus first RF, normal and validate paths

First RF/`rfon` in the main flow is at lines 3585+ (CEST loop, compiled out) and 3791 (the 90-degree RF); all V181 guards precede it.

| Guard | Line | Normal path | Validate path (`validate==1`) |
|---|---|---|---|
| mtc_on rejection | 3180 | before RF | evaluated (validate exits at 3338-3347, after it) |
| ESP read-balance (x2) | 3061-3066 | before RF | evaluated (after the 2125 jump to `averages_loop`@2491, before the 3341 exit) |
| flow-comp + diffusion | 2409-2411 | before RF (in `diff_acq_loop`, after 2356) | **skipped**: jump at 2110-2125 lands at `averages_loop` (2491), past 2409 |
| read relocation scale / first-read DAC / first-read slew | 3372-3379 | before RF (after `waittimer`, before matrix setup and the echo loop) | **skipped**: the validate exit prints `Duration=...` and does `goto end` at 3338-3347, before 3364 |

Mapper evidence (`validate_v181_guards.unsafe_cases()` re-run by me with `validate=0` and `validate=1`): all 38 unsafe cases give 0 RF and 0 ADC on the normal path. On the validate path every case also gives 0 RF/ADC (validate never plays RF), but these print `Duration=126000` instead of rejecting: `new_first_read_DAC_ceiling`, `new_first_read_slew_ceiling` (V181 guards skipped), plus the inherited `ramp_mismatch` (diff_tramp != tramp). `diffusion_flow_compensation` under validate is rejected, but only incidentally by the inherited "TE too short: pre-180 balance" check (the flow-comp guard is skipped), so a different TE could validate cleanly. `mtc_on=1` rejects on both paths and with diffusion on/off.

m1 (minor): Does this matter? Not for hardware safety: validate mode plays no RF and no gradients. It matters for the console validator workflow: a protocol can show a green `Duration=` but be rejected when scanned. Cheap fix: move the flow-comp guard above the `#ifdef VALIDATOR`/`validate==1` jump at 2110 (it needs only `diff_on` and `flow_comp_on`), and move the three relocation guards above the validate exit at 3338 (they need only values already computed at 3310). `goto end` is backward, so no forward-goto cost.

m2 (minor): The two ESP read-balance guards and the "read relocation scale outside DAC" guard were not exercised by any test in the repository suite or by my sweeps. My sweep (11 `no_samples` values x diffusion on/off x ESP 14-18 x validate 0/1) produced no hit on the ESP guards, and the suite's `new_intermediate_read_scale` case is rejected by an inherited "Reduce read grad comp" check first (that guard can only fire for gr_comp*grp_lobe near 3e4 DAC). The code is simple and reviewed above, so this is only a coverage gap; do not rely on them as exercised.

m3 (minor): The scale guard uses truncating long division (3371) while the played value uses vendor `scale()` (3380); the mapper models both as C truncation, but vendor rounding is unverified. The effect is at most 1 DAC on the relocated amplitude, which is already within the documented bounded residual.

m4 (minor/note): The reported "Minimum esp" (`report_on`) and the min-ESP check use `te_b`, not the extra 81.5 us pre-ADC window, so the report can be optimistic by up to about 163 us of echo spacing; the new V181 balance guards reject such a protocol before RF, so it is a message-quality issue, not a safety one.

## 5. Static audit rerun on final bytes: PASS

`python examples/v181_v1911_static_audit.py scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl --output <scratchpad>` (tool unchanged, output outside the repository): `pass: true`; ppl_sha256 `9fca0a13...`; `estimated_image_bytes` 56501 (limit 56664, margin 163); `forward_gotos` 21; 11 predicted W007/W008, `new_warning_signatures` empty; `largest_conditional_body_nodes` 369 (limit 405); `code_nodes` 12957; `undefined_labels` []; `unreferenced_labels_informational` []; no added long literals, risky comments or function macros. All eight checks true. This is a model, not PPLC; the audit parser also accepts the empty bodies in M1, so it cannot detect that risk.

## 6. Negative secondary read ramps: PASS

- Formula: `grp_dp = -(templ2*(tdp+tramp))/(tref+tramp)` (3310, inherited) and the relocation `scale(grp_dp, tref+tramp, tdp+tramp)` (3380), with the guard at 3370-3371, all use `(plateau + tramp)` and **no 1.0096 factor**. The only 1.0096 use in the repository is the positive crusher, in `examples/build_v19_ppl.py:253` and `examples/v19_validate_events.py:179`.
- Library evidence: I decoded `scanner/utilities/g3040_15.seq` with `dwfse.vendor_seq`. Secondary frame sample sums over 50 samples: `0_mn_sec` -25.000, `mn_0_sec` -25.000, so the negative pair sums to exactly 1.0000 * tramp. The positive pair `0_mx_sec` 25.000 + `mx_0_sec` 25.480 is 1.0096 * tramp. Both the removed lobe (`NEGPULSE_SEC(tref)` in `read_pre_list`, source line 1955) and the receiving lobe (first `NEGPULSE_SEC(tdp)` in `read_list`, source line 2011) are negative secondary, so the same exact-unit ramp applies and the area ratio is exactly `(tref+tramp)/(tdp+tramp)`.
- Default numbers (mapper): `gr_comp -2695`, `grp_lobe 110`, `tref=2800`, `tdp=700`, `tramp=200`, `grp_dp=889`, `gr_dp=269`; `scale(889,3000,900)=2963`, `v181_first_read_dp = 269 - 2963 = -2694`, matching the handoff. Area removed pre-RF 889*3000 = 2,667,000 DAC*us; area added 2963*900 = 2,666,700 DAC*us; truncation residual 300 DAC*us (0.011 percent), consistent with the stated ~0.233 cycles/m endpoint difference.
- The post-ADC lobe is unaffected: `aq_mat_sec` is rebuilt during the ADC with `gr_dp` (4090), and the relocated amplitude applies only when `diff_on==1 && total_echo_cnt==0` (3922-3924). DE is rejected with diffusion (899-903), so `read_de90_list` is never played with `G1=0`.

## Open items for the author (none are vendor-compile claims)

1. Fix M1 (give the three `if(mtc_on)` shells a non-empty body, e.g. `goto end;`), rebuild, re-run the static audit and event-equivalence, and update `compiler_v181_final.md` hashes.
2. Optionally fix m1 (move the four guards above the validate exits) so the console validator matches the run-time behavior.
3. Compile and run on the console remain required; this review cannot establish PPLC acceptance, final image size, exact warning list, or any physical timing.


---

# Re-review of 545a14ec

Reviewer: same independent reviewer role (did not write the code), 8 October 2026. Source-level and repository-mapper review only. No vendor cpp/PPLC/Forth compile, console or scanner run. Scratch and outputs: `docs/v181_v1911/review_checks/v181_rereview_*` (the reconstructed 9fca0a13 file lives only in the session scratchpad; `v181_rereview_fix.diff` plus `patch -R` regenerates it).

## Identity

| Object | SHA-256 | Match |
|---|---|---|
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl` | `545a14ec8c65ed578ea76628796547dd463eb8cd4a2efa680de89058a837de69` | yes |
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppr` | `ad82112ddfc7389a58caea6598cb5eb7583a271e71e62cd8c006190c52cdb159` | yes (unchanged) |
| `examples/build_v181_ppl.py` | `9d169b5681bcfcc02e612f88a92ccba6c57e7882be9a097ae51af38b52e4fb7e` | yes; `generate_ppl()`/`generate_ppr()` reproduce both files byte for byte |
| Reconstructed predecessor | `9fca0a13eb773d0e06d7bde0175dff4a3cd84d705db4211717fee9d23168f8b1` | yes |

Reconstruction: I applied the CR-stripped diff from `v181_review_fixes.md` in reverse (`patch -R`) to the LF-normalised target and restored CRLF. The result hashes to exactly `9fca0a13...f8b1`. So the documented diff is the complete change set (nothing undocumented in the target) and it is exactly: three `goto end;` in the shells, the flow-comp and mtc_on rejections moved to before the first VALIDATOR jump, and the relocation block (with its three guards) moved to before the second VALIDATOR exit. No file was edited except this appendix and the scratch files.

## Verdict

No blocker and no major finding. M1 and m1 are resolved as claimed. Several minor items and notes (below). Everything remains scanner-verify.

## Check results

| # | Check | Result |
|---|---|---|
| 1 | Moved-guard inputs complete at new locations, no dependence on old location | PASS |
| 2 | Messages byte-identical, fire before any RF, normal and validate, mtc_on=1 not silent | PASS |
| 3 | `goto end` all backward, forward gotos 21, audit <= 56664 | PASS (56517) |
| 4 | Timing window cost | PASS, acceptable (see below) |
| 5 | Event timing identical relative to first RF | PASS (80 strict cases, 0 differences) |
| 6 | `ramp_mismatch` validate gap inherited from v1.8 | CONFIRMED inherited, unchanged |

### 1. Input availability (trace)

- Flow-comp guard (line 2110) uses only `diff_on` and `flow_comp_on` (parameters). mtc rejection (2112) uses `mtc_on` (parameter). Neither is assigned anywhere in the file, and no use of `mtc_on` exists before 2112 other than the declaration. Both sit after all setup that precedes the first `#ifdef VALIDATOR` jump and before `averages_loop`, so they run on both paths and precede the first shell (2606), the second (3182) and the third (3567). The `averages_loop_setup`/`averages_loop` back-edges (4410, 4414) only re-enter after this point, so no entry into the shells bypasses 2110-2113.
- Relocation block (3346-3360): `tref` and `tdp` are assigned at 1574-1575 (setup, both paths); `tramp`, `crusher_max_dac` and `crusher_slew_dac_100us` are EDITTEXT parameters (the positivity check at 1451 is conditional on `crush_independent_on==1`, exactly as before, and the EDITTEXT minimum is 1, so this is unchanged from 9fca0a13); `gr_dp` is assigned once (3311) and `grp_dp` at 3312, then overwritten only in the `flow_comp_on` block (3339), which the relocation block follows. With `diff_on==1` flow comp is already rejected, so the post-flow-comp `grp_dp` equals the 3312 value wherever the block acts. No assignment to `gr_dp`, `grp_dp`, `tref`, `tdp` or `tramp` exists between the new and old location (grep).
- `templ1`/`templ2`: after the block, the next reads are `templ1` in the validate print (assigned first at 3365-3366) and at 3373/3375 (assigned). From 3379 on, every read of `templ1`-`templ5` is preceded by an assignment (3810-3811, 4018, 4055, 4097-4107, 4123-4160). Nothing reads `templ2` from the old location. `v181_first_read_dp` is read only at 3929 and is assigned on every pass through 3346.
- The block is top level in the slice loop (no enclosing `if`) with no label between 3346 and the validate exit, so every path to the exit passes it.

### 2. Messages and ordering (mapper, my own runs)

Ran all 43 cases of the author's `compaction_reject.py` on old and new: output equals `v181_fix_reject.json` (43/43), 0 RF and 0 ADC in every rejection. I additionally ran every unsafe case plus 10 extra cases (`mtc_diffoff`, `mtc_flow`, `mtc_te_short`, `mtc_array`, flow-comp with a valid TE, relocation DAC/slew, valid controls) with `validate=0` and `validate=1` in flat_0us and manual_x1.0.

- Normal path: every message identical to 9fca0a13, 0 RF/0 ADC for each rejection; valid controls still run (9 RF, 8 ADC).
- `mtc_on=1`: prints `V181 CEST/MTC not supported` on both paths, with diffusion on and off and with `mtc_array_on`, 0 RF/0 ADC. Not a silent exit.
- Validate path now reports `V181 first read prephase exceeds DAC`, `V181 first read prephase exceeds slew` and `V181 DWI requires flow compensation off` (previously `Duration=126000`, `Duration=126000` and an incidental "TE too short"). The valid controls still print `Duration=126000` under validate.

### 3. Compiler constraints

- Independent raw-text count: 18 forward gotos in the main file (554, 556, 743, 803, 838, 1035-1044 x5, 1140, 1172, 1205, 1243, 1277, 1721, 2131, 3985) plus 3 `goto end` in `tstex_15.pph` = 21, unchanged. 134 backward gotos in the main file include every `goto end` (label `end:` at 555) and the three new shell gotos. No undefined label.
- Static audit on the target: pass, `estimated_image_bytes` 56517 (limit 56664, margin 147, was 56501), forward gotos 21, `new_warning_signatures` empty, largest conditional body 369 nodes. On the reconstructed predecessor the same tool gives 56501, so the +16-byte claim reproduces.
- Shell shape: each shell is `if(mtc_on){ goto end; #ifdef MTC ... #endif }`; after preprocessing it is `if ( mtc_on ) { goto end ; }`, the `{ ...; goto end; }` shape used throughout the file. v1.8 itself had non-empty bodies at these three places, so the not-taken path is structurally closer to the scanner-proven v1.8 than the empty braces were. M1 is resolved. The third shell sits after `resync()` and `MR3040_Clock(clock)` before the 90 RF; its not-taken cost is unverifiable here (the mapper charges nothing for it, in either version).

### 4. Timing (mapper, diff_on=1 default)

| Metric | 9fca0a13 | 545a14ec |
|---|---|---|
| `waittimer(32500)` slack, x0.8 (ticks) | 9854 | 8237 |
| `waittimer(32500)` slack, x1.0 | 4239 | 2257 (226 us) |
| `waittimer(32500)` slack, x1.05 | 2835 | 762 |
| `waittimer(32750)` slack, x0.8 / x1.0 | 9490 / 9023 | 11122 / 11023 |
| First timer_overrun scale (1 shot, bisected) | 1.0852 (inherited `waittimer(8997)`) | 1.0758 (`waittimer(32500)`) |

Slack numbers match the author's. Slack is independent of protocol (identical across TE, ESP, TR, pre-sat, independent crushers, oblique angles, slice offset; CHESS costs 58 ticks more in both). With diff_on=0 nothing changes (the block is skipped). Overrun at x1.08 (new, 32500 window) versus x1.09 (old, 8997 window) agrees with the author.

Judgment: acceptable. (a) v1.8, which ran on the scanner, has negative slack at x1.0 in two windows (27500: -613 ticks; 5300: -228 ticks) and 4 timer overruns in that model, so x1.0 is demonstrably pessimistic and the nominal model is x0.8. (b) At x0.8 the 32500 window keeps 824 us of 3250 us. (c) The inherited `waittimer(8997)` window is already tighter (595 ticks at x1.0) and sets the first overrun within about 1 percent of the new one, so no new weakest link appears by more than that. (d) The trade gives the `waittimer(32750)` matrix window +2000 ticks. It remains a real cost and should be the first scanner-verify timing item: if a missed 5-ms period appears, look at the `waittimer(templ1)` window first.

### 5. Event timing (reran everything)

- `compaction_reltime.py` (3 states x 8 cost models = 24): output equals `v181_fix_reltime.json` (24/24). `compaction_equiv.py` shows the differences the author states (matrix-creation timestamps and select history only in flat models; a 4.7 to 5.9 us global offset in manual models; `mtc_on` and `flow_comp_dwi` rows differ only in `t_end`/misc/printf with the same message and 0 RF/ADC).
- My own stricter script (`v181_rereview_strict.py`) compares, relative to the first library RF, every RF event (including non-library), every ADC field, every S/P/R gradient segment (not only non-zero), all misc events (including waittimer targets), printf output and all flags except narrowing. 10 valid protocol states (default 3 shots, imaging, diff off, TE 60, ESP 18, TR 800, pre-sat, CHESS, independent crushers, flow comp with diff off) x 8 cost models = 80 cases: 0 differences. No timer_overrun at x0.8 or x1.0 in either file.

So event timing relative to the first RF is identical in all 8 models.

### 6. Inherited validate gap

The `diff_tramp != tramp` guard (v1.81 line 2409) is also in v1.8 (line 2393), inside `diff_acq_loop` after the `goto averages_loop` validate jump (v1.8 line 2115; v1.81 line 2131). Text and position relative to the jump are unchanged. Under `validate=1` it still prints `Duration=126000` (same in old and new; 0 RF/ADC). It is inherited, not introduced.

## Findings, severity-ranked

1. (Minor) 32500-tick window slack reduced from 424 us to 226 us at manual x1.0 (985 to 824 us at x0.8); first modeled overrun x1.085 to x1.076. Acceptable as argued; record as the first scanner-verify timing item.
2. (Minor) Modeled image margin is now 147 bytes (56517 of 56664); the audit's fixed-overhead assumption is unverified, so any further edit must re-run it.
3. (Minor/note) Message priority changed for multi-fault protocols: `mtc_on=1` with a too-short TE now reports the CEST message instead of the TE message (both paths), and under `validate=1` a DWI + flow-comp protocol now reports the flow-comp message instead of an incidental TE message. Message text is byte-identical and each fires before any RF.
4. (Minor/inherited) `diff_tramp != tramp` is still skipped under validate; inherited from v1.8 unchanged, no RF in validate. Optional cheap fix: it needs only `diff_on`, `diff_tramp`, `tramp`, so it could sit beside the other two moved guards (a few image bytes, no timing change). Not required.
5. (Note, from the first review) The two ESP read-balance guards and the "read relocation scale outside DAC" guard are still not exercised by any test; the relocation DAC and slew guards are exercised.
6. (Note) PPLC acceptance of `goto end;` as a sole statement in an `if` body, final image size, exact warning list and all physical timing remain unproven without the vendor toolchain; the author's "Not claimed" section is accurate.

Nothing here blocks the console upload from a source-review standpoint. Compile and scanner verification remain required.
