# Independent PPL review, round 2: v191 (ss-MGOT) and v192 (Alsop)

Reviewer: independent PPL reviewer. The only file I wrote is this one.
Date: 2026-10-06.

This is a **static source review without a vendor compiler, simulator or console**. All timing was re-derived by hand from the source, the vendor `.pph` macros and the EVO manual cost tables, using a standalone integer script that does not import `dwfse.ppl`. The coordinator's new mapper cost model is noted but was not relied on.

## Files reviewed

I computed these hashes myself. The generator reproduces all four outputs byte-for-byte: `build()` and `build_ppr()` match the files on disk for both methods.

| File | SHA-256 |
|---|---|
| FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl | 0e726d39d494a1cafefbd737fdc45eebb21be63a0fb31a5e85ef0bdad7808881 |
| FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppr | faa77a11c2da4c5fe9876d6a842b9bc3025c66ddc09eaa4e8270dec9350faf0c |
| FSE_dwi_CPMG_non_CPMG_twoTE-1.92.ppl | fe6652c74676b49d1ce9da748b5ef41fb5bfdd46ed1e76edc02456174d9275dd |
| FSE_dwi_CPMG_non_CPMG_twoTE-1.92.ppr | 678f2af5bb2fa205c2b7cb9402879d9ce1e98ed8e2c5fa4264c318b3e6898fbf |
| examples/build_v19_ppl.py | d09248c07cbf531af2a605a4ea28883bc7dcdcd1d69b4dbcbd79a233c0aafe66 |
| FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl (baseline) | 3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2 (unchanged) |

- The hashes 26b4bfe3… and 9fca7aa7… quoted in the coordinator's first round-2 note do not exist on disk; the coordinator has since withdrawn them.
- The **report-printf change described in that note is not in the reviewed bytes.** 191:L2411 and the generator at L478 still print `v19_s_1`, the imaging-crusher **list start** (64396 us for the PPR), under the label "first imaging RF". The true first imaging RF centre is 66716 us. See n2.
- Both PPLs are still pure insertions into the v18 bytes: `diff` against v1.8 shows only `a` hunks.

Notation: `191:Lx` is v191 line x and `192:Ly` is v192 line y.

## 1. Verdict on each round-1 finding

| ID | Verdict | Evidence (file:line) |
|---|---|---|
| **B1** post-initiate window | **CLOSED** | `V19_ADC_SLOW 8997L` (191:L352, 192:L347). It is used in the window (191:L4950, `waittimer(V19_ADC_SLOW)`), in `v19_adc_mid` (191:L2387) and in the anchor `templ1` (191:L2389). The window holds about 540 us of work (CREATE_MATRIX 135.6 us, three long `/`/`%` at about 122 us each, plus the rest) in 899.7 us, the same budget as v18 (measured 823.6 us there). For the PPR: adc_mid = 44980 (≥ 100 ✓); post_a = 22427 and post_b = 24722, unchanged because adc_mid absorbs the difference. `complete()` still falls at nsp−3 ticks after the post-initiate anchor. The comment at 191:L2388 still says "+ 3000" (stale text only). |
| **M1** gp_sl_var | **CLOSED** | `gp_sl_var = 0;` at the top of `v19_shot` (191:L4806 and the corresponding v192 line). This is untimed pre-shot code (0.6 us), covered by the 70-us TR allowance. 3D is rejected, so 0 is the correct value. |
| **M2** 5-ms timer period | **CLOSED for every RF block and for v192; OPEN for v191's spoiler window (see N1)** | `V19_MAX_WAIT 49000L` (191:L349). `V19_RF_GO` now re-anchors right after `waittimer(go-v19_lead)` (191:L398-411). Every later wait in the macro is relative to that anchor: unblank 665, lead−ANCHOR 1025, offl 33075, offl+POST 33275 ticks for 3200-us frames. `V19_RFTIMES` checks go−lead, offl+POST and rem+TAIL against 49000 (191:L391). Setup checks first_wait, post_b, rd_a2, b_d·10, post_a, rd_a1 ≥ 4000 and go_im−lead ≥ 2500 (191:L2396-2402). With the v18-default `diff_tcrush=2000`, which failed in round 1, the prep-180 block now gives go−lead = 26170, offl = 33075, rem = 25945: no wait above 49000. Block geometry is unchanged: RF start = S+go, gate-off = S+off, post-RF anchor = S+off+POST+ANCHOR, rem ends at S+(list+20)·10. |
| **M3** common-int switch | **CLOSED** | No `common int v19_*` remains (191:L432-451); all V19 PARAMLIST variables are plain `int`. Plain-int SCROLLBAR/EDITTEXT parameters have v18 precedent (`int de_on`, `int dixon_on`, `int mains_gating`). `v19_mode = 0;` is set at 191:L2192 before the gate, and `v19_mode = 1;` only after every check passes (191:L2408), before the validator exit. All four per-shot branches test `v19_mode`: 191:L2991, L3260, L3514, L3807. The method matrices use `crusher_saved_first` and `crusher_saved_train` (191:L4768, L4798), and the D-sign and |C| ≥ 3|D| checks use `crusher_saved_train` (191:L2259-2264). |
| m1 uncalibrated anchors | open (documented estimate, accepted) | Unchanged in substance. See also n1. |
| m2 weak guards | **CLOSED** | `diff_tramp!=tramp`, `rfgate_delay<17`, `tramp+rfdelay<163` (191:L2207-2208); rd_a1 ≥ 4000; go_im−lead ≥ 2500 (191:L2401). |
| m3 spoiler overflow | **CLOSED** | `cpmm*templ1 > 2000000` rejected before the ×1000 (191:L2296). The worst case is 2.000033e9 < 2^31. |
| m4 read-prephaser slew | **CLOSED** | Both signs checked (191:L4789-4791). |
| m5 RF calibration | open (documented; `alpha`/`p180_scale` intentionally ignored) | Needs per-frame console calibration. |
| m6 gate-off margin | **CLOSED nominally, small residual** | Gate-off is at lead−ANCHOR + L·10 + 50 from the re-anchor, i.e. **5 us after the `rfon` call**. The frame actually starts after `rfon` (0.9 us + 1.2 us common-int argument + 0.6 us return) plus the `MR3031_go` latency. Measured from frame start, the effective margin is therefore about 2 us or less (minor, see n1). |
| m7 unblank lead | **CLOSED** | `v19_lead = (warmup+rfgate_delay+60)·10` and `v19_unblank = lead − (warmup+rfgate_delay−7)·10 − 5`, which is constant at 665 ticks. `rfampon` is called (rfgate_delay−7+warmup) us before `rfon`, i.e. 36 us for the PPR, the v18 idiom plus 10 us. The work in that interval (rfampon, `if`, `delay(warmup)`, long argument evaluation ≈ warmup + 4.4 us) leaves ≥ 5.6 us slack at the minimum rfgate_delay of 17. `NEWSHAPE_SETUP` has 66.5 us (v18 budgets 22 us for it). |
| m8 even plateau | **CLOSED** | `if (dest%2!=0) dest = dest+temp;` (191:L370). For odd tramp/10 this gives an even result that stays on the tramp/50 DELAY raster. PPR flats are unchanged (3320 / 1320). |
| i1–i6 | unchanged (informational) | i3 still applies: both method PPRs carry crush_amp −8223. |
| New C1 guard | **verified** | 191:L2268-2275. `(t3−t2<t4/2)&&(t2−t3<t4/2)` is exactly \|C1−C\| < D/2, and the second test is exactly \|C1−(C+D)\| < D/2, in area units DAC·us. PPR: C = 9 867 600, C1 = 6 578 400, D = 2 574 000. \|C1−C\| = 3.29e6 and \|C1−C−D\| = 5.86e6 are both above 1.287e6, so the PPR passes. There is no overflow (≤ 3.6e8). Note that it compares magnitudes only; it does not test C−D or opposite-sign C1. Whether that is sufficient is for the physics reviewer. |

## 2. New findings

| ID | Severity | file:line | Finding | Evidence | Suggested fix |
|---|---|---|---|---|---|
| **N1** | **major** (latent; shipped PPR OK) | 191:L4874-4879 (`waittimer((v19_b_sp-V19_TAIL_US)*10L)`, `waittimer(v19_b_sp*10L)`); setup 191:L2296-2302, 2356 | The v191 spoiler window has **no ≤ V19_MAX_WAIT check**, a residue of M2. t_sp may be up to 6000 us, which allows b_sp·10 = (t_sp + 2·tramp + 120)·10 up to 65 200 ticks at tramp 200 and 81 200 at tramp 1000 (a 16-bit wrap). Accepted parameters reach this. For example, spoil_dac 8192 with cpmm 32 gives t_sp = 4828 and b_sp·10 = 53 480 ticks. The second `waittimer` is then issued about 5.25 ms after its `starttimer` and is extended by 5 ms. That moves the re-excitation (T0) 5 ms away from the tip-up and breaks the designed TE/ESP. Shipped PPR: t_sp 2316 → 28 360 ✓. | Manual p. 90; hand arithmetic. | Add `(v19_b_sp*10L > V19_MAX_WAIT)` to the 191:L2401 check, or split the spoiler wait with `delay32`. |
| n1 | minor | 191:L398-411 | Re-anchored `V19_RF_GO`: no statement sits between a `waittimer` exit and its `starttimer`. Every wait is issued and targeted below 49000 (verified for ex, rf, tip/elim, re, im, including diff_tcrush 2000). The remaining uncalibrated items are: (a) the `rfon` and `MR3031_go` costs between the `waittimer(lead−ANCHOR)` exit and the frame start, about 3 us, which shift every RF centre late by the same amount; (b) the m6 effective margin of ≤ 2 us after frame end. | Manual 3.3.1.26. | Console trace, or close the gate at L+10 us. |
| n2 | minor (reporting only) | 191:L2411 / 192 same; generator L478 | The `report_on` printf labels `v19_s_1` (the crusher list start) as "first imaging RF". The change announced by the coordinator (to print `v19_t0+v19_esp_us/2L`) is **not** in the reviewed files. | grep. | Apply the announced change and regenerate. |
| n3 | info | 191:L2391, L4963 | `waittimer(v19_post_end)` has target post_a + 1000, but only post_a ≤ 49000 is checked. At the edge (post_a = 49000) the target is 50000, past the 49 999-tick timer period. Shipped PPR: 23427 ✓. | Code inspection. | Check `post_end ≤ V19_MAX_WAIT` instead of `post_a`. |
| n4 | info | 191:L247, L432 | `v19_on` is now a non-common int with no initializer. If the v191/v192 PPL is ever loaded with an old v18 PPR, the parameter editor must supply the PARAMLIST default 0. Garbage values other than 0/1 are rejected; a garbage 1 would select the method (and then still pass through the full gate). | Manual §2.2.1.3 (defaults generated when the PPL is read). | For control runs, use the v18 PPL itself, or save the PPR with `:VAR v19_on, 0` explicitly. |

## 3. Control path with v19_on = 0 (re-verified)

All additions are still pure insertions. What executes when `v19_on = 0`:

- **Untimed setup:**
  - the range check on `v19_on`;
  - `v19_mode = 0;`;
  - the skipped `if (v19_on==1)` block;
  - `NEWSHAPE_MAC(18..23)`, which writes array indices that v18 never reads.
- **Inside v18's padded windows (5300, 27500 twice, 30000):** four `if (v19_mode==1)` tests. Each now reads a plain int, about 1.1 us instead of 1.9 us, so it is cheaper than in round 1. The 5300 window keeps its documented ≥ 284-tick margin. The 30000-window test sits after the `crusher_setup_ticks ≤ 24500` check, inside v18's 550-us reserve.
- **Unchanged from round 1:** a no-code label, and a `goto end` equivalent to v18's fall-through. No v19 lists are built and the v18 list addresses are unchanged.
- **Parameters and memory:** all V19 PARAMLIST variables are plain ints, so v18's dual-port RAM layout shrinks by 7 (v191) or 3 (v192) common ints compared with round 1. v18's own common ints are untouched.

Conclusion: **no v18 event timing changes** under the documented costs. The deployment dependency on the `#use RF1 … pf19` library remains (i1).

## 4. Hand re-derivation, shipped PPR

Inputs: tramp 200, rfdelay 60, rfgate 23, warmup 20, tdp 700, tcrush 1000, diff_tcrush 1000, TE 54 ms, ESP 14 ms, 128 × 50 us.

Derived constants: lead 1030, unblank 665 ticks.

| Block | go | go−lead | offl | rem |
|---|---|---|---|---|
| prep 90 | 3200 | 2170 | 33075 | 15945 |
| prep 180 | 17200 | 16170 | 33075 | 15945 |
| tip-up v191 | 17200 | 16170 | 33075 | 1945 |
| elim v192 | 17200 | 16170 | 33075 | 15945 |
| re-exc v191 | 3200 | 2170 | 13075 | 15945 |
| imaging 180 | 17200 | 16170 | 13075 | 15945 |

All values are in ticks and all are ≤ 49000.

- **Other waits:** first_wait 40540 (v191) / 30540 (v192); rd_a1 11000; rd_a2 13600; ADC_SLOW 8997; adc_mid 44980; post_a 22427; post_b 24722; b_d·10 12200; b_sp·10 28360.
- **ADC centres** remain exactly at T0+ESP: 73716 us (v191) and 68000 us (v192). First imaging RF centres are 66716 and 61000 us. Prep echo is at TE = 54000 us. Gaps are unchanged from round 1.

## 5. Overall verdict

B1, M1, M3, m2, m3, m4, m7 and m8 are closed. M2 is closed except for the v191 spoiler window (N1, major, latent, simple fix). m1 and m5 remain documented estimates that need console calibration. m6 is nominally closed with a residual of about 2 us.

The restructured `V19_RF_GO` introduced no new blocking defect: every wait is issued and targeted below 4.9 ms after its anchor, and there are no statements between a waittimer exit and its re-anchor. v192 has no open blocking or major item. v191 has one open major item (N1).

Vendor compile and console trace are still required before scanning.

---

## Round 3 confirmation (static; no compiler)

**Files reviewed.** I computed these hashes myself, and the generator (`c0f39a5c9ae267e69e46a78adfaa8c30b440c4b18bef9b846671eb86320d15ce`) reproduces all four outputs byte-for-byte:

- v191.ppl `f0156b48a1b9ff648dba7d69e508629b6fc51bebfcb27d91c5f9fc46ee205f2d`
- v192.ppl `35d0eeaa0c60dc1d95f9bbb9c44881e65bc9a58d533aa3636031b4273d15e855`
- v191.ppr `faa77a11…`
- v192.ppr `678f2af5…`

The v18 baseline is unchanged (`3b420376…`). Both PPLs are still pure insertions into v18: `diff` shows only `a` hunks. The line counts changed as expected: v191 gained 2 lines (5416 to 5418) and v192 is unchanged at 5358.

| ID | Verdict | Evidence |
|---|---|---|
| N1 | **CLOSED** | 191:L2366-2367: `if (v19_b_sp*10L>V19_MAX_WAIT) { printf(...); goto end; }`. It runs after `v19_b_sp` is assigned (191:L2356) and before the validator exit, so it covers both spoiler waits; the first wait, `(b_sp-TAIL)*10`, is smaller. 16-bit wrap is impossible because any value above 49000 is rejected. Shipped PPR: 28360 ✓. |
| n3 | **CLOSED** | 191:L2403 and 192:L2367 now test `v19_post_end>V19_MAX_WAIT`. `post_end` is assigned before the check (191:L2393, 192:L2357). post_a < post_end, so post_a stays bounded too. Shipped PPR: 23427 ✓. |
| n2 | **CLOSED** | 191:L2413 and 192:L2377 now print `v19_t0+v19_esp_us/2L` as "first imaging RF centre". That is 66716 us for v191 and 61000 us for v192, which matches my hand derivation. The printf still has 4 arguments. |
| n4 | open by design (documented) | `v19_on` is still a plain int with PARAMLIST default 0. Control runs must use the v18 PPL/PPR, or a PPR with an explicit `:VAR v19_on, 0`. |
| m1, m5, m6 residual, i1-i6 | unchanged (documented estimates / informational) | These still need a vendor compile and a console trace. |

**New defects:** none. The round-3 edits are confined to the three items above. No timed code changed, and the `v19_on=0` path is untouched by this round.

**Verdict:** both files have no open blocking or major findings at static-review level. A vendor compile, a `v19_on=0` event-identity check against v18, and console calibration of the m1/m5/m6 items are still required before scanning.
