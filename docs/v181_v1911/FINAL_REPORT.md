# DW-FSE v1.81 and ss-MGOT v1.911: final before/after report

Date: 2026-10-08. Workspace: `DWI-FSE-Sequence`.

> **STATUS: source-validated candidates. NOT vendor-compiled and NOT scanner-verified.**
> Every number below comes from the repository's source-level PPL mapper (`dwfse/ppl/`), exact
> waveform integration, a finite-RF event Bloch model, an instantaneous-RF pathway model, static
> source audits and independent reviews of the same models. Nothing has been run through the
> MR Solutions PPLC/Forth toolchain or on the 9.4 T scanner. Compiled image size, the exact
> warning list, real instruction timing, gradient lag, RF latency, achieved flip angles, SAR,
> gradient/amplifier limits and every acquired-signal prediction are **scanner-verify**.

## 1. Summary

| | v1.81 (from v1.8) | v1.911 (from ss-MGOT v1.91 method-only v7) |
|---|---|---|
| Net intent | Remove the read-prephaser/diffusion b cross term, fix two documented v1.8 timing fragilities, keep ESP/TE | Fuse the slice-axis train lobes, ESP 14 ms to 13 ms, fix terminal restoration |
| ESP / first echo | Unchanged (14.011 ms; first echo 54.043 ms, manual x0.8 model) | 12.997 ms (v7 13.997); first imaging echo 72.70 ms from prep 90 (v7 73.70); echo 8 is 8.0 ms earlier |
| Min accepted TR | 174 ms (v1.8: 173 ms; +895 us TR-floor accounting) | 193 ms (v7: 199 ms) |
| Effective b | **Changed on purpose** (see section 8): b1000 true 1000.7 s/mm2 instead of 1175.9 | Unchanged (E1: 1014.68 vs 1014.55 at nominal 1000) |
| Bloch grid (36 cases x 8 echoes) | ratio 1.00000 everywhere: PASS | **Strict gate FAILED** (172 strict, 46 material, all at B0 = +/-128 Hz); documented-deviation disposition in section 9 |
| Hazards (8 cost models, 4 protocol states) | zero overruns, zero ignored lists, zero premature matrix uses | same (raw inherited `matrix_active` notices 17 per shot vs 16 in v7) |
| Static compiler model | image 56517 B (limit 56664), 21 forward gotos, 11 predicted W007/W008, largest branch 369 nodes: PASS | image 49626 B (v7 48469, limit 52568), 18 forward gotos, 3 predicted W007/W008 (+ W003 for `pb_end`), largest branch 379 nodes: PASS |
| Independent review | Compiler/PPL: no blocker on final bytes. Physics: ACCEPT | Compiler/PPL: ACCEPT on final bytes (after two findings fixed). Physics: ACCEPT WITH CONDITIONS, Bloch deviation disposition accepted |

Held (high value, specific unresolved gate), not implemented: wider refocusing slab (v1.81), same-shot navigator (both), isodelay correction (marginal; convention question). Declined: mild VFA, crusher reduction, crusher polarity change, source-gap prep-TE edits. See section 13.

## 2. Final identity (verified by SHA-256 before this report was written)

| Object | SHA-256 |
|---|---|
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl` | `545a14ec8c65ed578ea76628796547dd463eb8cd4a2efa680de89058a837de69` |
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppr` | `ad82112ddfc7389a58caea6598cb5eb7583a271e71e62cd8c006190c52cdb159` |
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl` | `716478bb357ba1479e6cc8fcc18c1085e44b3c78ecf1bdf32bb561b171838682` |
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppr` | `b2976e7464367a7aa6b6b8e04765cc04a3fd85c0d2ec64c9c9a57963bf9635c2` |
| Baseline v1.8 PPL (unchanged) | `3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2` |
| Baseline v7 ss-MGOT PPL (`docs/v181_v1911/baseline_v7/`) | `6a0d222b6c8689fbdee5f4ae412c4d5df0bea10a7da99a309fabf5dfab04d828` |
| Baseline v7 ss-MGOT PPR | `fc7f0218f5aaf7866e44ce65331a2f6c11526d0ce04f8e2e78f44dbb6cd0ebeb` |
| Acquired test1e PPR (v1.8 control; base of the v1.81 PPR) | `84611fcb854deab5e9e7110aa7fdd68cfed25ba17d988231ab092c51a66b8fbc` |
| `examples/build_v181_ppl.py` (final) | `9d169b5681bcfcc02e612f88a92ccba6c57e7882be9a097ae51af38b52e4fb7e` |

Provenance of the files:

* v1.81 PPL = v1.8 plus the diff listed in section 4; the builder reproduces PPL and PPR byte for byte (verified independently by the compiler reviewer). The v1.81 PPR is the acquired **test1e protocol** (136 views, ETL 8, nav_on 1, esp 14, `crush_amp` -2741, `diff_crush_amp` -5482) with only the `:PPL` line changed. It is **not** the repository `scanner/...-1.8.ppr`.
* v1.911 PPL = v7 method-only (not the workspace combined v6, SHA `92bdcb79...`) plus `examples/build_v1911_ppl.py`. v1.911 PPR = v7 PPR with `:PPL` filename changed and `esp 14` changed to `esp 13`. 64-row tables, as v7.
* The six RF libraries `scanner/rf/v19_*.seq` are byte-identical to the v7 ZIP members (checked). v1.911 references them; v1.81 does not (stock libraries only).

## 3. Which evidence files are final and which are stale

Rule used: an artifact counts as final only if the SHA-256 values recorded inside it equal the finals above. Stale files are kept for history and must not be quoted for the final bytes.

| Final (input hashes match) | Stale / superseded (reason) |
|---|---|
| `validation/event_gates.json`, `events.json`, `moments.json`, `rejections.json` (545a14ec / 716478bb recorded; `inputs_stable_during_run` true). `tr_minimum.json` records no hash but is from the same run | `validation/v181_guards.json` (records `9fca0a13`; re-run on 545a14ec in a scratchpad copy gave the same results per `v181_review_fixes.md`) |
| `review_checks/final_physics_grid.json/.md` (Bloch grid, per-echo b, diffusion pathway; records finals; its isodelay section lists two older candidate files and flags them as non-matching) | `validation/btensors.json`, `pathway_comparison_v181.json`, `pathway_comparison_v1911.json` (hashes `48d11...`, `33e7...`) |
| `review_checks/physics_review_*.json` (record or reproduce finals) | `compiler_v181_final*.json` and `compiler_v181_final.md` numbers (record `3c90b80b` / `9fca0a13`; superseded by `v181_review_fixes.md`: image 56517 B, margin 147, not 56501 / 163) |
| `review_checks/v1911_rereview_*.json` (716478bb) | `review_checks/v1911_final_*` (7cf66e01, before the terminal fix), `v1911_static.json`, `v181_static.json`, `v181_initial_static.json`, `independent_event_audit*.json`, `read_relocation.json`, `compiler_guard_probe.json`, `compiler_reproduction.json`, `finite_rf_peak_candidate_standard.json`, `timing_candidate_audit.json`, `v181_writer_checks.json` |
| `review_checks/v181_fix_*.json` and `v181_rereview_*.json` (compare 9fca0a13 vs 545a14ec by design) | `review_final_v1911.md` first half (reviewed 7cf66e01; its HIGH and MEDIUM findings were fixed; second half re-reviews 716478bb) |
| `refocus_width_study.json/.md` (archived v1.8 bytes and stock RF only) | `review_compiler.md`, `review_validation.md` (interim reviews of intermediate builds `3978fb01`, `c3a7aa8e`; their findings are folded into the final builds) |
| `finite_rf_peak_baseline*.json` (v7 and v1.8 baselines) | |

## 4. v1.81: every change

All v1.81 timing is unchanged relative to the first RF (verified 24 + 80 cases, 0.0 us difference) except the explicitly listed enlarged setup windows, which are before the first RF or inside windows that already existed.

### 4.1 Read prephaser moved out of the diffusion pair

* **Physics:** v1.8 plays the first read prephaser (-2074 cycles/m) between the 90 and the diffusion 180, so it coexists with the 40 ms diffusion block. Its product with the diffusion wave-vector is a b cross term (+53 / +167 / +410 s/mm2 at nominal b 100 / 1000 / 6000, sign set by diffusion polarity), and its self term adds about 8 s/mm2. In v1.81 the equivalent positive lobe (-2694 DAC in the first read-list prelude, same 700-us flat and 200-us ramps) is played after the diffusion 180.
* **Predicted effect:** effective b becomes independent of diffusion polarity and within +4 % (b100) to -0.3 % (b >= 2000) of the nominal label (section 8). Read endpoint moves by -0.233 cycles/m (0.41 us, 0.008 k-pixel); TE and ESP unchanged.
* **Repository verification:** exact piecewise-constant integration plus a 0.25-us brute-force check (agree to <= 0.1 s/mm2); negative secondary ramps verified to integrate to exactly `(plateau+tramp)` (no 1.0096 factor; decoded `g3040_15.seq`); coherent wanted-echo EPG amplitudes identical (ratio 1.0000, 12 cases x 8 echoes); finite-RF Bloch ratio 1.00000 in all 36 cases; guards for DAC, slew and scale overflow.
* **Scanner-verify:** phantom b1000/b0 ratio (section prediction in `SCANNER_TEST_PLAN.md`), raw echo peak position, played first-read amplitude.

### 4.2 Block-C deadline and enlarged pre-RF windows

* **Physics/engineering:** v1.8 has windows that are missed at modestly higher instruction cost (`waittimer(185)`, `waittimer(5300)`, `waittimer(27500)`); a missed 5-ms timer period shifts the sequence by 5 ms.
* **Changes:** `waittimer(5300)` -> `6500` (+120 us); `waittimer(templ1)` 27500 -> 32500 ticks (+500 us; flow-comp variant 37500 -> 42500); matrix window `waittimer(30000)` -> `32750` with the setup threshold 24500 -> 27250 (+275 us, 550-us check reserve kept). Total +895 us, carried exactly in the TR floor (11350 -> 12245).
* **Predicted effect:** timer overruns in the model 4 -> 0 (manual x1.0), 2 -> 0 (flat 1 us), 16 -> 0 (flat 2 us), 16 -> 0 (manual x0.8 + 0.5 us); x1.25 still fails both versions (22 vs 20).
* **Verification:** all 8 cost models x 3-4 states; first-overrun cost scale moves from x1.085 (inherited `waittimer(8997)`) to x1.076 (`waittimer(32500)`, slack 226 us at x1.0, 824 us at x0.8). This is the one real cost of the fix and is the first scanner-verify timing item.

### 4.3 Active slice-list restart

* **Physics/engineering:** v1.8 restarts the slice list while the previous list is still active in some cost models ("SetList on active channel S ignored"; 14 ignored lists and 98 premature matrix uses at flat 0 us), losing a train lobe. v1.81 replaces `waittimer(210+temp-25)` by `delay(50,us); waittimer(1000)` (100-us window including 50-us settling) and subtracts 815 ticks (81.5 us) from the read balance so ESP is unchanged.
* **Predicted effect / verification:** 0 ignored lists and 0 premature matrix uses in all 8 cost models (v1.8: flat 0 us has 14 ignored lists). Side effect: the `TE too short: first-echo balance` and `V181 ... read balance` guards sit 81.5 us tighter than in v1.8.
* **Scanner-verify:** physical list restart ordering, odd/even echo symmetry.

### 4.4 TR-floor accounting and exit hub

* TR floor 11350 -> 12245 (+895 us). Minimum accepted TR 173 -> 174 ms (manual x0.8, x1.0, flat 2 us).
* Backward exit hub: `end: goto v181_exit;` with the original epilogue label renamed `v181_exit:`. Forward gotos 145 (v1.8, right at the E106 threshold of about 147) -> 21.

### 4.5 CEST/MTC compiled out, plus new guards

* `#define MTC` removed in the new copy only (about 1172 model bytes). PARAMLIST, declarations and PPR untouched; `mtc_on` is 0 in all 97 PPR/MRD occurrences in the repository. `mtc_on != 0` now prints `V181 CEST/MTC not supported` and exits before any RF (also under `validate=1`). The three `if(mtc_on){ goto end; }` shells keep untimed statement cost (and thus modeled timing) identical.
* Added guards, all before the first RF and, after review fix m1, before the validate exits: diffusion + flow compensation (relocated prephaser is not flow-compensated), ESP read-balance (two), relocation scale, first-read DAC, first-read slew. Message table in `ERROR_CODES.md`.

## 5. v1.911: every change

### 5.1 Fused slice-axis train lobes (ESP 14 -> 13 ms)

* **Physics:** v7 plays the restore/recall lobe D, the crusher C and the selector compensation as separate slice-axis lobes on each side of every imaging 180. Between RF boundaries a transverse state changes by the signed gradient area, and a stored longitudinal state keeps its spatial order, so equal area at **every** intervening RF and ADC boundary preserves every coherence history (including unwanted and stimulated ones) independent of flip angle. v1.911 replaces the separate lobes by single fused lobes with 1328-us tops and 200-us ramps: first (before the first imaging RF) about -6460 DAC, pre-RF about -4774 DAC, post-RF about -8146 DAC (v7 peak 8223). The conventional selector stays on during RF. Each free interval shortens by exactly 500.0 us; ESP falls by 1.0 ms.
* **Predicted effect:** T2 and stimulated-pathway diffusion gain, conditional (section 10): +3.2 % (E1) to +16.5 % (E8) at T2 32 ms / T1 1.3 s / D 0.002 mm2/s; +1.7 % to +10 % at T2 60 ms. Primary-path b rises slightly (+0.13 s/mm2 at E1, about 3 s/mm2 by E8); stored-path b falls.
* **Repository verification:** interval areas versus v7 at every RF/ADC boundary (section 6); RF-time selector sample-identical (0.0 DAC over 12 RFs, +/-250 us); no fused lobe within 196.5 us of nonzero RF (256.5 us with 60-us lag) and zero overlap with every ADC receiver-busy interval; identical history sets (same codes survive at every echo, weight cut 1e-5), largest wave-vector difference 1.34 cycles/m (needs > 1000 cycles/m to change pathway selection); |C|/|D| = 3.8319 and |C1|/|D| = 2.554 preserved; peak S 8146 DAC (v7 8223), S integral G^2 dt -16.5 %, S total variation -32 %.
* **Scanner-verify:** actual S/P/R concurrency limits and (oblique) sums, eddy-current effect (proxy +16 % at tau about 2 ms at the ADC), achieved ESP, compiled timing.
* **Why 13 ms, not 12:** a 12-ms design would begin the next slice lobe before `complete()` finishes flushing the receiver filter. ESP 12 is rejected (E32).

### 5.2 Read/phase preludes overlap the fused slice lobes

R and P lobes now run concurrently with the fused S sides instead of after all S. P area differences vs v7 are zero; R differs by +/-0.137 cycles/m per interval, which is a 0.24-us ADC-placement difference (not gradient area).

### 5.3 Terminal -D restoration (fix of an independent-review finding)

The merged next-RF pre-lobe cannot restore the final echo, so a final-only list `v1911_l_end` (`POSPULSE_SEC(tdp)`) plays after the last ADC. Review of the first fix found (HIGH) the terminal `CREATE_MATRIX` rewrote matrix 259 while the trailing P/R lobes played, and (MEDIUM) an unguarded `waittimer(18000)` window. Final bytes: `waittimer(24000)` before the terminal matrix, `waittimer(28000)` before the terminal `Start`, exit `waittimer(v1911_i_term_end)` = 40000, `v19_shot_us` +1000 us. Result in 88 shots x 8 models: zero ledger matrix issues, zero overruns, zero ignored lists; terminal S area +2,579,491 DAC.us (identical to v7's final restoration), starts 1428.5-1430.5 us after `complete()`, and **never overlaps the receiver-busy interval** (v7's final restoration overlapped it by 1394-1474 us).

### 5.4 Source guards

E140 (geometry/rfdelay), E141 (fused DAC bounds), E142 (integer-area residual), E143 (ESP window), E144 (ESP must be 13), E145 (area overflow guard), E146 (any orientation angle). Meaning, reachability and remedies in `ERROR_CODES.md`. Note E142 is a **lattice** on `crush_amp` (section 12).

## 6. Timing tables

Definitions: ESP = spacing of consecutive imaging RF centres (constant in every echo and shot); echo time = ADC centre measured from the first excitation RF centre; ADC-RF midpoint offset = ADC centre minus the RF-pair midpoint (echo centring; tolerance used 25 us). All from the source mapper with an assumed 3-us RF latency and 60-us gradient lag; **not physical timing**.

### 6.1 ESP in microseconds by cost model

| Cost model | v1.8 | v1.81 | v7 (v1.91) | v1.911 |
|---|---:|---:|---:|---:|
| flat 0 us/stmt | 13977.40 (14 ignored lists) | 13977.40 | 13995.50 | 12996.50 |
| flat 0.5 us | 13992.40 | 13992.40 | 14000.00 | 13000.50 |
| flat 1 us | 14007.40 (2 overruns: +5 ms on ADC1) | 14007.40 | 14004.50 | 13004.50 |
| flat 2 us | 19037.40 (16 overruns) | 14037.40 | 14013.50 | 13012.50 |
| manual x0.8 (nominal) | 14011.32 | 14011.32 | 13996.94 | **12997.38** |
| manual x0.9 | 14015.56 | 14015.56 | 13997.12 | 12997.49 |
| manual x1.0 | 14019.80 (4 overruns) | 14019.80 | 13997.30 | 12997.60 |
| manual x0.8 + 0.5 us | 19026.32 (16 overruns) | 14026.32 | 14001.44 | 13001.38 |

ESP is constant within each model. Do not call any of these exact physical timing; the spread between models (up to 15 us) is the instruction-cost uncertainty.

### 6.2 Echo times (manual x0.8), ms from first excitation centre

| Echo | v1.8 / v1.81 | v7 (v1.91) | v1.911 | v1.911 minus v7 |
|---|---:|---:|---:|---:|
| 1 | 54.043 | 73.701 | 72.702 | -1.000 |
| 2 | 68.054 | 87.698 | 85.699 | -2.000 |
| 3 | 82.066 | 101.695 | 98.697 | -2.998 |
| 4 | 96.077 | 115.692 | 111.694 | -3.998 |
| 5 | 110.088 | 129.689 | 124.691 | -4.998 |
| 6 | 124.100 | 143.686 | 137.689 | -5.997 |
| 7 | 138.111 | 157.683 | 150.686 | -6.997 |
| 8 | 152.122 | 171.680 | 163.684 | -7.996 |

v1.8 and v1.81 are bit-identical in every cost model in which v1.8 runs without a timer overrun. For v7/v1.911 the prep (90 to second 180) is unchanged: RF centres 0 / 26.998 / 53.995 ms in both, so the user-set `te` = 54 ms prep TE is unchanged. Re-excitation to echo 1: 14.595 -> 13.596 ms.

### 6.3 Echo centring (ADC-RF midpoint offset, us) and minimum TR

| | v1.8 | v1.81 | v7 | v1.911 |
|---|---:|---:|---:|---:|
| Offset, manual x0.8 | -5.58 | -5.58 | -4.55 | -4.33 |
| Offset range over 8 models (clean runs) | +0.10 to -7.00 | +0.10 to -11.90 | -3.75 to -8.75 | -3.25 to -9.25 |
| Min accepted TR, ms (rejected one ms lower) | 173 | **174** | 199 | **193** |
| Timer overruns at min TR (x0.8 / x1.0 / flat 2 us) | 0 / 4 / 16 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Shot spacing at min TR, manual x0.8 (us) | 173034 | 174034 | 198845 | 192849 |

The v1.8 ADC1-versus-RF offset of 2488 us in flat 2 us and x0.8 + 0.5 us models is the 5-ms overrun effect, absent in v1.81.

## 7. Event and pathway moments

Net gradient area between consecutive events, cycles/m, shot 1, manual x0.8, from `validation/moments.json` (exact integration of mapped output; physical time = emitted + 60 us gradient lag).

### 7.1 v1.8 versus v1.81 (selected rows; all other rows identical)

| Interval | Axis | v1.8 | v1.81 |
|---|---|---:|---:|
| Exc 90 to diffusion 180 | R | -2074.313 | **-3.109** |
| Diffusion 180 to ADC1 | R | -2075.236 | **-4.265** |
| Exc 90 to diffusion 180 | S | -6888.750 | -6888.750 |
| Diffusion 180 to ADC1 | S / P | -6873.869 / 240.437 | identical |
| Every later ADC and RF interval | S / P / R | identical in both sequences | identical |

The relocated read lobe leaves the diffusion window and appears after the diffusion 180: desired-path read endpoint at ADC1: -0.9226 -> -1.1556 cycles/m (-0.233); even echoes +0.233.

### 7.2 v7 versus v1.911 (cycles/m per interval)

| Quantity | v7 | v1.911 | Difference |
|---|---:|---:|---:|
| Re-excitation to RF1, S | -8563.483 | -8563.401 | +0.082 |
| RF to ADC, S | -10650.718 | -10650.601 | +0.117 |
| ADC to RF, S | -6650.336 | -6650.290 | +0.046 |
| RF to ADC / ADC to RF, P | per-echo values identical | identical | <= 2e-12 |
| RF to ADC / ADC to RF, R | -2070.380 / -2072.960 | -2070.243 / -2073.097 | +0.137 / -0.137 (ADC-placement artefact) |
| Terminal restoration (ADC8 end to shot end), S, P | 16914.052, 12983.209 | identical | 0 |
| Whole-shot net S | | | 1.34 cycles/m (accumulated bound; 1.3e-3 cycles across 1 mm) |
| Per-boundary S error | | | max 0.1175 cycles/m = 1.2e-4 cycles over 1 mm |

Integer-DAC rounding makes exact equality impossible; the figures above are the bounded residuals. Crusher areas: C = -7675.48 cycles/m, D = -2003.24, |C|/|D| = 3.8315, |C1|/|D| = 2.5544 (identical to v7; the reviewer could not find a unique waveform-level definition of C1 but equality with v7 holds regardless).

Pathway view (ideal-RF Weigel EPG, B1 = 1 and 0.85, flip schedule 90/180/90/90 and imaging train, weight cut 1e-5): history sets identical at every echo, 16 to 34,960 histories at B1 = 1; wanted and nearest unwanted histories are separated by 3949 cycles/m (2|D|) and 1974.5 cycles/m, identical in both sequences. Fusing creates no new coincident pathway and removes none.

## 8. Every-echo b tensors (trace, s/mm2), primary branch

Source: `review_checks/final_physics_grid.json` section `btensors` (exact PWC integration from excitation centre including imaging gradients, 60-us lag, instantaneous RF; branch with smallest |k_end|). Full 3x3 tensors (order S, P, R) are in the JSON. Diffusion direction +X (read) in all three protocol rows.

| Sequence | Nominal b | E1 | E2 | E3 | E4 | E5 | E6 | E7 | E8 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v1.8 | 0 | 12.03 | 14.69 | 17.44 | 20.28 | 23.27 | 26.42 | 29.80 | 33.40 |
| v1.8 | 100 | 165.03 | 167.70 | 170.44 | 173.28 | 176.27 | 179.43 | 182.80 | 186.40 |
| v1.8 | 1000 | 1175.93 | 1178.60 | 1181.35 | 1184.19 | 1187.18 | 1190.33 | 1193.70 | 1197.31 |
| v1.8 | 6000 | 6398.16 | 6400.82 | 6403.57 | 6406.41 | 6409.40 | 6412.55 | 6415.92 | 6419.53 |
| v1.81 | 0 | 4.00 | 6.67 | 9.42 | 12.26 | 15.25 | 18.40 | 21.77 | 25.38 |
| v1.81 | 100 | 104.05 | 106.72 | 109.46 | 112.30 | 115.29 | 118.45 | 121.82 | 125.42 |
| v1.81 | 1000 | 1000.71 | 1003.38 | 1006.12 | 1008.97 | 1011.95 | 1015.11 | 1018.48 | 1022.08 |
| v1.81 | 6000 | 5980.67 | 5983.34 | 5986.09 | 5988.93 | 5991.92 | 5995.07 | 5998.44 | 6002.05 |
| v7 (v1.91) | 0 | 20.30 | 30.97 | 43.41 | 55.01 | 66.93 | 79.61 | 91.15 | 105.04 |
| v7 (v1.91) | 100 | 120.10 | 130.77 | 143.21 | 154.81 | 166.73 | 179.40 | 190.95 | 204.83 |
| v7 (v1.91) | 1000 | 1014.55 | 1025.21 | 1037.65 | 1049.25 | 1061.18 | 1073.85 | 1085.39 | 1099.28 |
| v7 (v1.91) | 6000 | 5982.20 | 5992.87 | 6005.31 | 6016.91 | 6028.83 | 6041.51 | 6053.05 | 6066.93 |
| v1.911 | 0 | 20.44 | 31.62 | 44.40 | 56.46 | 68.78 | 81.86 | 93.86 | 108.09 |
| v1.911 | 100 | 120.23 | 131.41 | 144.20 | 156.26 | 168.58 | 181.66 | 193.65 | 207.89 |
| v1.911 | 1000 | 1014.68 | 1025.86 | 1038.64 | 1050.70 | 1063.02 | 1076.10 | 1088.10 | 1102.33 |
| v1.911 | 6000 | 5982.33 | 5993.51 | 6006.30 | 6018.36 | 6030.68 | 6043.76 | 6055.75 | 6069.99 |

Decomposition at E1 (v1.8 / v1.81): diffusion lobes alone 99.97 / 996.47 / 5976.08 at nominal 100 / 1000 / 6000; imaging self term 12.02 / 4.00; cross term +53.04 / +0.08 (b100), +167.45 / +0.25 (b1000), +410.06 / +0.60 (b6000). With diffusion along -X, v1.8 gives 59.1 / 841.5 / 5579.2 at nominal 100 / 1000 / 6000; v1.81 is identical for +X, -X and +Y (1000.71 / 5980.68), and 1020.6 / 6025.0 for an oblique (1,1,1)/sqrt3 direction in both X polarities. Slice-direction diffusion keeps a 37.3 / 91.2 s/mm2 cross term in both sequences; the S-R off-diagonal is +46.9 (v1.8) / +45.3 (v1.81) s/mm2 at b6000.

### 8.1 What changed between v1.8 and v1.81 (read this before comparing data)

* The console's own b-to-DAC conversion (`b_kfac`, `39.69*d^2*(D-d/3)`) is **unchanged** in v1.81. For a given requested b the diffusion gradient DAC is identical in v1.8 and v1.81. What changes is the **effective** b actually experienced, because the read prephaser no longer rides on the diffusion lobes.
* v1.8 label error (diffusion +X): +65 % / +26 % / +17.6 % / +12 % / +9.7 % / +6.6 % at nominal 100 / 500 / 1000 / 2000 / 3000 / 6000, and it depends on diffusion polarity. v1.81 label error: +4 % (b100), +0.1 % (b500, b1000), -0.3 % (b >= 2000); the residual -0.3 to -0.4 % is the 39.69 versus (2 pi)^2 console kernel and can be corrected analytically if desired.
* Apparent-ADC overestimate when fitting with nominal b: v1.8 (+X) 1.530 / 1.234 / 1.164 / 1.115 / 1.093 / 1.064 for b0 to 100 / 500 / 1000 / 2000 / 3000 / 6000; v1.8 (-X) 0.471 ... 0.928; v1.81 1.000 ... 0.996.
* **Do not pool v1.8 and v1.81 data by nominal b.** Re-fit archived v1.8 data with effective b (the October 7 first-navigator ratios 0.1158-0.1185 correspond to 0.00216-0.00213 mm2/s with nominal b but 0.00185-0.00183 mm2/s with effective b). Any empirical per-protocol b correction tuned on v1.8 phantoms must be dropped for v1.81. Low-b (<= 500) apparent ADC and IVIM-type fits from v1.8 are strongly contaminated.
* Prediction for the same sample and temperature: b1000/b0 signal ratio **0.158-0.161 on v1.81 versus the archived 0.116-0.119 on v1.8** (about 36 % brighter b1000). That is a bookkeeping change, not a sequence defect.
* b rises by about 21 s/mm2 from E1 to E8 in the v1.8 family and about 85 s/mm2 in ss-MGOT; use per-echo b for echo-resolved fits. These are single-path traces; low-angle FSE signal is a sum over pathways, so the trace is a guide, not a universal effective b.

## 9. Finite-RF Bloch grid

Grid: B1 0.8 / 0.9 / 1.0 / 1.1 x B0 -128 / 0 / +128 Hz x initial phase 0 / 45 / 90 deg = 36 cases x 8 echoes per pair; EventBloch, finite selective RF, slice grid 3000 points over 5 slice widths (z), 32 phase-voxel points (y) for ss-MGOT and 1 for v1.8/v1.81; relaxation and diffusion off; assumed RF latency 3 us, gradient lag 60 us. Gate as set before running: STRICT failure = any magnitude drop below -1e-4 (normalized to unit-flip on-resonance slice integral); MATERIAL failure = candidate/baseline < 0.98. Source: `review_checks/final_physics_grid.md/.json` (final bytes).

### 9.1 Results

| Pair | cases | min ratio | max ratio | min ratio per echo E1..E8 | STRICT | MATERIAL |
|---|---:|---:|---:|---|---|---|
| v1.8 -> v1.81 | 36 | 1.00000 | 1.00000 | 1.0000 (all eight) | PASS | PASS |
| v7 -> v1.911 | 36 | 0.96914 | 1.00098 | 0.9992, 0.9902, 0.9824, 0.9768, 0.9738, 0.9730, 0.9725, 0.9691 | **FAIL (172)** | **FAIL (46)** |

Nominal case (B1 1, B0 0, phase 0) per-echo |S| is identical between v1.8 and v1.81 (0.8434 ... 0.7809) and between v7 and v1.911 (0.3845, 0.3919, 0.3237, 0.2984, 0.2774, 0.2568, 0.2309, 0.2009); the v7/v1.911 ratio on resonance is 0.99998-1.00001 in every B0 = 0 case (12 of the 36 grid cases; the physics review text says nine, see section 17).

### 9.2 The v1.911 strict-gate failure, recorded verbatim

From `final_physics_grid.md`, section "Disposition":

> v191_v7->v1911: GATE FAILED (STRICT 172, MATERIAL 46); worst {'B1': 1.1, 'B0_Hz': -128.0, 'phase_deg': 90.0, 'echo': 8, 'delta': -0.006206979863268125, 'ratio': 0.969141169521035}. Not relabelled; see reviewer disposition in the report/handback. Model omits diffusion and relaxation (unless stated), so a time-compressed candidate's T2/diffusion benefit is not credited here.

> v1911 diagnostics over 24 failing cases: STRICT failures by B1 {'0.8': 43, '0.9': 42, '1.0': 43, '1.1': 44}, by B0 {'-128.0': 86, '0.0': 0, '128.0': 86}, by phase {'0.0': 57, '45.0': 56, '90.0': 59}, by echo {'1': 4, '2': 24, '3': 24, '4': 24, '5': 24, '6': 24, '7': 24, '8': 24}. ESP {'v191_v7': 13996.940000000028, 'v1911': 12997.380000000032}. Min ratio no relaxation 0.9691; with T1 1.3 s/T2 32 ms 0.9989; candidate evaluated at B0 scaled to equal off-resonance phase per ESP 0.8966.

Failure facts: every failing case is at |B0| = 128 Hz (86 strict failures at each sign, none at 0 Hz); 28 of the 46 material failures are at B1 = 0.8; per-echo ratio falls from 0.9992 (E1) to 0.9691 (E8). The gate was **not** relabelled as a pass.

### 9.3 Physics-reviewer disposition (documented deviation) and replacement criteria

Independent physics review (`review_physics.md`, section 7.2), on the final bytes:

* The geometry cannot be the cause: with instantaneous RF and off-resonance phase accrued in every free interval, the coherent wanted-echo sum of v1.911 over v7 is exactly 1.000000 in all 36 (B1, B0, phase) cases and all eight echoes. The pathway history sets are identical (section 7). The loss therefore comes from finite-RF off-resonance physics in a 7 %-shorter schedule: a single isochromat at a fixed offset compares two different off-resonance ripples with different periods (1/ESP = 71.4 Hz for v7, 76.9 Hz for v1.911), so the pointwise drop is a ripple-phase effect, not a loss of pathway selection.
* Period-averaged over one 1/ESP of each train: coherent 0.9972, incoherent 0.9973 (v1.8 -> v1.81: 1.0000).
* Net of relaxation at T1 1.3 s, T2 32 ms the minimum over all 24 failing cases is 0.9989 (worst corner >= 1.004; T2 60 ms >= 1.010; T2 100 ms >= 1.0004).
* The equal-off-resonance-phase-per-ESP rescaling (0.8966) does not align the ripples (the ripple also depends on absolute offset through the finite RF), so it is not a valid like-for-like criterion.
* **Verdict: accept as a documented deviation, not a physics regression.** The gate as written (single isochromat, relaxation-free, -1e-4 tolerance) is not a valid acceptance criterion for a sequence whose ESP differs by 7 %. The original numbers are kept above; the replacement criteria, stated after the fact, are:
  1. on-resonance ratio >= 0.9999 (met: 0.99998);
  2. period-averaged ratio >= 0.995 (met: 0.9972);
  3. relaxed ratio >= 0.995 with T2 >= 32 ms (met: 0.9989).
* Residual caveats: for T2 > about 100 ms and a narrow B0 distribution sitting on a ripple minimum, late echoes can be 2-3 % lower than v1.91 (unrelaxed worst case 0.9691 at E8); in-vivo B0 spread beyond +/-128 Hz is untested. These criteria are post-hoc and must be confirmed on the scanner (`SCANNER_TEST_PLAN.md`, off-resonance check).

## 10. Diffusion-aware pathway (EPG) conditional gains

**Conditional model:** instantaneous-RF, stationary box voxel, no finite slice profile, no diffusion during RF, no motion, T1 1.3 s, T2 32 ms, D = 0.002 mm2/s, `(2 pi)^2` included for stored longitudinal states, self-checks passed. It is not a finite-RF result and not a prediction of acquired signal. The existing `dwfse/pathways.py` was not used as the oracle (it omits `(2 pi)^2` for stored-Z diffusion and rejects the MGOT preparation) and was not edited; `EventBloch` has no molecular diffusion.

Coherent wanted-echo ratio v1.911 / v7 (B1 1.0):

| Conditions | E1 | E2 | E3 | E4 | E5 | E6 | E7 | E8 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Grid agent: T2 32 ms, T1 1.3 s, D 0.002 | 1.0315 | 1.0529 | 1.0802 | 1.0972 | 1.1159 | 1.1329 | 1.1488 | 1.1652 |
| Physics reviewer: same | 1.0315 | 1.0532 | 1.0800 | 1.0971 | 1.1158 | 1.1327 | 1.1486 | 1.1643 |
| Reviewer: T2 32 ms, D = 0 | 1.0317 | 1.0488 | 1.0742 | 1.0877 | 1.1042 | 1.1156 | 1.1290 | 1.1371 |
| Reviewer: T2 60 ms, T1 1.3 s, D 0.002 | 1.0165 | 1.0301 | 1.0453 | 1.0571 | 1.0694 | 1.0806 | 1.0910 | 1.1018 |
| Reviewer: no relaxation, D 0.002 | 0.9997 | 1.0024 | 1.0058 | 1.0096 | 1.0138 | 1.0172 | 1.0203 | 1.0236 |

Across the full grid (B1 0.8-1.1, phases) the v1.911/v7 ratio is 1.0272 to 1.1902 (robust min/max over 288 echoes). Interpretation: 3.2 % (E1) to 13.7 % (E8) is pure T2 (1 ms earlier per echo position); the diffusion part grows from -0.02 % to +2.4 % because the amplitude-weighted mean b of the contributing histories falls. Nominal diffusion-only attenuation exp(-D b) per echo: v7 0.9594 ... 0.6301, v1.911 0.9591 ... 0.6446 (D 0.002 vs 0).

v1.8 -> v1.81 (same model): nominal-flip ratio 1.0160 at E1 (uniform 1.0162 per the reviewer's slice-coherent split, equal to exp(D x 8 s/mm2), the removed prephaser self term) down to 1.0000 at E8. The per-history spread (0.76-9.6 overall, 0.849-1.427 robust, worst signed change -2.9 % of E1) was dispositioned by the physics reviewer as a model artifact on slice-incoherent histories weighted by hard-box sinc sidelobes at one sample, neutral redistribution of already-suppressed pathways, not a regression (section 7.1 of `review_physics.md`). The coherent wanted echo and slice-coherent histories are unchanged (+0.015 % worst).

## 11. Compiler limits (static source model; not PPLC)

| Metric (tool `examples/v181_v1911_static_audit.py`) | v1.8 | v1.81 | v7 | v1.911 | Gate |
|---|---:|---:|---:|---:|---|
| Estimated image, bytes | 56664 | **56517** | 48469 | **49626** | v1.81 <= v1.8; v1.911 <= v1.8 - 4096 = 52568 |
| Forward gotos | 145 | 21 | 18 | 18 | PPLC E106 near 147 |
| Predicted W007/W008 | 11 | 11 (identical identities) | 3 | 3 (identical identities) | no new identity |
| Largest conditional body, AST nodes | 369 | 369 | 379 | 379 | <= 405 (110 % of v1.8) |
| Undefined jump targets | 0 | 0 | 0 | 0 | 0 |
| Unreferenced labels | 0 | 0 | `pb_end` | `pb_end` (may give W003) | informational |
| Added printed literals > 48 characters | | none | | none | none |
| Added function-like macro calls in `//` comments | | none | | none | none |
| New function-like `#define`s | | none | | none | none |
| Method tables | 512-row legacy | PPR unchanged | 64 rows | 64 rows (`acq_b` `VAR_ARRAY 64`) | 64 |

The v1.81 margin to the model gate is only 147 bytes (it was 163 before review fix m1); any further edit must re-run the audit. The v1.911 growth is +1157 model bytes over v7. The estimate uses an unknown fixed overhead; **compiled size and the exact warning count are scanner-verify**. The three predicted v1.911 W007/W008 identities are `offset_frequency(fov_slice_freq+slice_freq_var)`, `IntToLong(slice_freq_var)` and `waittimer(templ1)`. v1.81 timer arguments added: `waittimer(6500)`, `waittimer(32750)`, `waittimer(1000)` (all int literals), and the existing `waittimer(templ1)` (existing warning identity). New v1.911 timer arguments: `waittimer(24000)`, `waittimer(28000)` (literals) and `waittimer(v1911_i_term_end)`.

Signed arithmetic: v1.81 `templ1 = grp_dp*(tref+tramp)` worst case <= 1.1e9 < 2^31 (promoted to long first); v1.911 worst product `|C|+|D| <= 21,474,000` guarded by E145 so the rounded numerator is <= 2,147,476,496 < 2,147,483,647.

### 11.1 The 16-bit integer waittimer note and the split-wait fallback

`int` is a signed 16-bit type; `waittimer(int)` takes a 16-bit argument with a documented maximum of 65500 ticks, and a long-to-int assignment keeps the low 16 bits without warning. v1.911 passes `v1911_i_term_end` = 40000 (stored as -25536) to `waittimer`. This works only if the controller reads the cell as unsigned. Precedent in the scanner-run lineage: v7 passes `v19_i_first_wait` = 40540 (stored -24996) at the start of every train and 33075 / 33275 (stored -32461 / -32261) before every RF pulse, and the October 7 ss-MGOT acquisitions (test2, test2b, test2c on v1.91) ran with them. Caveat: those scans carry no timing trace and do not distinguish v6 from v7.

**Fallback if the console rejects or mistimes the 40000 argument** (optional hardening requested of nobody; reviewer-measured what-if): replace the single source line `waittimer(v1911_i_term_end);` at the end of the terminal block (just before `goto v19_after_train;`) by the two lines `starttimer();` and `waittimer(12000);`. Reviewer measurement on 8 cost models: `v19_shot_us` unchanged (171943), `tr_min` unchanged, pre-`waittimer(690)` moment and shot period shift by +2.4 to +6.4 us, no overruns, mapper `timer_arg` flags 28 -> 24. The unshipped what-if file is `docs/v181_v1911/review_checks/v1911_rereview_variant_split.ppl` (SHA-256 `808caec9e6ad042d7db68cb025373394e4570a0a6daa60d64a9ca1008c9cd2e7`); it was timing-checked in the model only and has no independent approval.

## 12. Source-validation coverage and rejections

* **Cost models:** all eight (flat 0 / 0.5 / 1 / 2 us; manual x0.8 / x0.9 / x1.0; x0.8 + 0.5 us). **States:** actual imaging shots (overrides `no_disacq=0, nav_on=0, no_views=128`, nonzero PE exercised), diffusion-row progression (16 views, 6 shots), default PPR (dummy, navigation, imaging; 6-8 shots) and a four-direction diffusion table. Events gates: **zero timer overruns, zero ignored lists, zero premature matrix uses** for v1.81 and v1.911 in every model; baseline v1.8 shows 14 ignored lists + 98 premature uses (flat 0 us) and timer overruns in 4 of 8 models (flat 1 us, flat 2 us, manual x1.0, manual x0.8 + 0.5 us); v7 shows only the known final-restoration receiver-busy overlap at minimum TR (fixed in v1.911). Raw inherited `matrix_active` notices occur during zero output (32 for v1.8/v1.81/v7, 34 for v1.911 = 17 per shot, the terminal create on the selected pair with no list playing); they are not premature use.
* **Rejection cases (before any RF/ADC):** v1.81: 38/38 unsafe protocols in `validate_v181_guards.py` rejected (this set includes CEST/MTC and diffusion with flow compensation), plus 2/2 V181 cases in the event-gate run; v1.911: 38/38 pass, including all 19 original method-only cases (identical codes to v7 except ESP-too-short E31 -> E32 and the TR message "increase to 193 ms"), plus the new E140/E143/E144/E146 cases; v7 baseline 24/24. Every rejection prints its message with RF count 0 and ADC count 0, also under `validate=1`.
* **E142 lattice (found while writing this report, not previously documented):** the train crusher amplitude `crush_amp` must land on a lattice where the fused DAC integer rounding keeps the area residual within 0.01 % of |D|. Mapper probe at manual x0.8, one shot: accepted values within +/-40 DAC of the default are -8242, -8237, -8233, -8228, -8223 (default), -8219, -8214, -8209, -8205; all others in -8245..-8201 give E142. This is a **designed narrowing of the already narrow E18 coincidence window**, not a bug, but the user should not hand-tune `crush_amp` freely. `diff_crush_amp` (C1) values -5500..-5466 are all accepted by E142.

## 13. Required evaluation and decline table

| Item | Decision | Reason, evidence and gate |
|---|---|---|
| Merge slice-axis gradients in the imaging train (v1.911) | **Implemented** | Section 5.1; area identity at every RF/ADC boundary, 3.83 / 2.55 ratios kept, no overlap of fused lobes with RF or ADC busy, peak below inherited 8223 DAC. Physical-axis sums/oblique, eddy and hardware limits scanner-verify (angles rejected by E146) |
| Shorten ESP to the minimum this allows | **Implemented: 13 ms** | ESP 12 ms would start the next slice lobe before `complete()` flushes the receiver; rejected (E32). Constant across the train |
| Verify timing of every event | **Done in model; physical timing scanner-verify** | Section 6; echo centring within -3 to -12 us offset under all models; CPMG spacing constant to 0.0 us |
| Isodelay (about 95 us, v1.91) | **Not changed; marginal, convention question** | The historical +95 us is not a universal RF isodelay: peak probes moved +93.4 -> +65.9 us as z/y grids converged (3000 z x 32/64 y; y8 aliases the spoiler); current bytes give +65.8 to +65.9 us (v7, v1.911) and -41 us (v1.8, v1.81). In 22 archived v1.8 scans the unencoded navigator echoes peak at sample 64.82-64.98 (mean 64.90), v1.91 64.86-65.04, v1.92 64.97-65.11 on 128 samples at 50 us; the same +0.9 sample appears for the stock sinc and the SLR pulses, so most of it is a receiver/sample-time-stamp convention common to all sequences. Effect: 0.9 k-pixel linear phase (harmless for magnitude), 2-4 degrees of phase per 128 Hz. Check the raw peak position; no sequence shift |
| Refocusing slab width 1.2-1.5x (v1.81) | **HELD, high value, gated** (not marginal) | Isolated finite-waveform study: edge conjugate transfer 0.569 -> 0.769 (1.2x) -> 0.912 (1.5x), excitation-weighted 0.842 -> 0.918 -> 0.968 at B1 1.0, 0 Hz, robust over B1 0.8-1.1 and +/-128 Hz, same RF energy. Gates: independent refocus primary matrix and separate pre/post compensation (the shared primary gradient also carries the crushers, whose areas would change 16.7-33.3 %), asymmetric lag-shifted selector, second frequency buffer for off-centre slices, zero-lag versus 60-us-lag compensation difference, v1.81 image headroom (147 bytes), finite-train Bloch and vendor compile. Naive selector scaling is excluded |
| Per-shot navigator (v1.81, v1.911) | **HELD, high value for in-vivo multishot** (marginal for phantom/ex-vivo) | The navigator is one ky=0 train for the whole 136-line volume. A same-shot navigator needs the raw storage/tagging/reconstruction contract (one extra ADC line per shot with line tags, `bare_bones_recon_fse.py` assumptions). Pending recon contract; recommended first design: append one ky=0 echo per imaging shot. Cannot recover signal already lost in-train (v1.8 train is phase-fragile: E8 = 0.96 / 0.67 / 0.11 of ideal at phase 0 / 45 / 90 deg, B1 0.9) |
| Variable flip angles (mild, v1.8) | **Declined** | SAR is not shown to be limiting; adds stimulated pathways to an already phase-fragile train without a measured gain |
| Crusher polarity | **Retained** | Negative non-alternating, supported by October 5 paired scans (high-b rim -74 %, E2 edge excess -92 %); fusion and relocation are polarity-neutral |
| Crusher area reduction (ss-MGOT, v1.8 re-run) | **Declined** | No coincidence re-validation; Oct 7 shows no suppression advantage for the stronger v1.8 crusher but also no evidence that smaller ss-MGOT crushers keep pathway rejection. Areas C and D, ratios 3.83 / 2.55 unchanged. Any change needs a new finite-RF coincidence scan |
| Preparation TE | **No code change; protocol option `big_delta` = 30 ms** | TE_prep (RF0 to RF2 centres) 53.99 ms = Delta 40.00 ms + about 14.0 ms fixed (delta 4 ms, 3.2-ms 180, ramps); source-gap edits would not move it meaningfully. The PPR lever (ss-MGOT analysis): `big_delta` 30 ms gives preparation signal +37 % (T2 32 ms) / +18 % (T2 60 ms) for +16 % diffusion gradient (b6000: 23,366 DAC = 71 % of full scale vs 20,119 DAC = 61 %, within the 30,000-DAC b-mode limit); 35 ms gives +17 % / +9 % for +7 % (21,561 DAC). Costs: changed diffusion time (ADC/time-dependence), gradient rating unknown, not run through the mapper. Protocol decision for the user |
| ESP-14 matched-control unlock (v1.911) | **Offered, not done** | v1.911 accepts only ESP 13 (E144), and v7 rejects ESP < 14, so no common ESP exists for a fusion-only A/B on the console. An optional build that admits ESP 14 with fused lobes would need its own audit of the fused geometry at 14 ms; ask for it if the scanner A/B shows an ESP/fusion confound that matters |
| Alsop v1.92 | **Out of scope** | Unchanged |
| v1.8 timing fragilities (block C, active list) | **Implemented (v1.81)** | Sections 4.2-4.4 |
| Read prephaser out of the diffusion pair | **Implemented (v1.81)** | Section 4.1 |

## 14. Pre-existing test failures

`tests/test_v19_ppl_mapper.py` (unmodified): 13 tests, **11 pass, 2 fail**, re-run during this report with no file changes. The two failures are pre-existing and caused by the test's method-only assumptions meeting the user's workspace combined-v6 `scanner/...-1.91.ppl`: `test_method_only_image_below_v18` (image model 67744.8 versus budget 52568.2) and `test_method_only_rejects_control_mode_and_large_tables` (the v6 source still contains `v19_mode==1) goto v19_mat_window`). Neither involves v1.81 or v1.911. They were not repaired, to preserve the original files.

## 15. Open and inherited items

1. **`diff_tramp != tramp` validate gap (inherited from v1.8).** Under `validate=1` this guard is skipped and the console prints `Duration=126000` instead of rejecting (no RF is played in validate). The normal path rejects it. Not fixed (out of scope; optional cheap fix noted by the reviewer).
2. **60-us gradient-lag sensitivity (inherited, reduced, not eliminated).** The mapper has a stress mode in which a 60-us gradient lag extends list activity (`grad_latency_us=60`). I re-ran it for this report (2 shots; v1.8 and v1.81 with the v1.81 PPR, v7 and v1.911 with their own PPRs and the imaging overrides): v1.8 shows "SetList on active channel R/P/S ignored" in all 8 cost models (71-87 flags); **v1.81 in 3 of 8 models** (flat 0 us: 52, flat 0.5 us: 33, manual x0.8: 19) and none in flat 1 / 2 us and manual x0.9 / x1.0 / x0.8 + 0.5 us; v7 26 flags in every model (13 per shot: 5 in the diffusion-preparation block, 8 in the train); **v1.911 10 flags (5 per shot) in every model, all in the inherited preparation block and none in the fused train**. This is the reason `validate_v181_guards.py` reports `all_pass` false (same three v1.81 cases fail on `9fca0a13`). The main event gates, which apply the lag in the ledger, show zero ignored lists for both candidates. The true lag/list-activity semantics are scanner-verify; the same mapper also emits `timer_arg` flags (14 per two shots in v7 and v1.911) for the signed-16-bit-stored timer arguments of section 11.1.
3. **Guards not exercised by any test:** `V181 ESP leaves no read balance`, `V181 ESP leaves no train read balance`, `V181 read relocation scale outside DAC` (the relocation DAC and slew guards are exercised); E141 and E145 (shadowed by E17/E18/E142 in every tested case); E144's tfilter clause (needs tfilter > 1100 us; E32 stops earlier).
4. **Orientation guard coverage:** E146 checks only element `[0]` of `r_angle_var`, `p_angle_var`, `s_angle_var`; elements `[1..]` are unchecked (unreachable with the single-slice E3 restriction).
5. **Timing margins that matter on hardware:** v1.81 `waittimer(32500)` window 226 us slack at x1.0; inherited `waittimer(8997)` window 595 ticks; v1.911 `waittimer(28000)` terminal window 161 us slack (26389-26469 of 28000 ticks); terminal matrix create lands 168.8-176.8 us after the trailing P/R lobes end (about 109 us allowing the 60-us lag); matrix ready 168.4-168.6 us before terminal `Start`; the terminal list ends 98-100 us before the 40000 exit. A slip costs a 5-ms period (terminal moment still correct, shot 5 ms longer).
6. **Eddy-current exposure:** v1.911 S-axis proxy at the ADC +16 % (tau 2 ms), +6 % (10 ms), -3 % (0.5 ms); under 1 Hz across a half slice for alpha about 1e-3. Mechanical repetition fundamental 77 Hz (v7 71 Hz); coil resonances unknown.
7. **R-interval residual** +/-0.137 cycles/m is an ADC-placement artefact (0.24 us), not gradient area; reported, not hidden.
8. **v1.911 acceptance narrowness:** ESP 13 only; angles zero; geometry exactly 200 / 700 / 1000 us ramps/tdp/tcrush and `rfdelay` = 60; `crush_amp` on the E142 lattice.
9. **Bloch deviation** (section 9) rests on post-hoc criteria; in-vivo B0 beyond +/-128 Hz and long-T2 fluid are untested.
10. **Undocumented dated history:** the in-file MODIFICATION HISTORY block has no dated v1.81 entry (header comment only); cosmetic.
11. **PPL path in the PPRs:** the v1.81 PPR names `G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl` (inherited from the acquired test1e PPR), whereas the v1.911 PPR names the bare filename `FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl`. Keep each PPL beside/under the name its PPR expects, without download suffixes such as " (1)".

## 16. Independent reviews and the hashes they approved

| Review (file) | Reviewer role | Bytes reviewed | Outcome |
|---|---|---|---|
| `review_final_compiler_v181.md` first half | PPL/compiler, did not write code | v1.81 `9fca0a13...f8b1`, PPR `ad82112d...` | No blocker; M1 (empty `if(mtc_on){ }` bodies) and m1 (validate-path guards) found and fixed |
| `review_final_compiler_v181.md` re-review | same | **v1.81 `545a14ec8c65...de69`**, PPR `ad82112d...`, builder `9d169b56...` | No blocker, no major; M1, m1 resolved; 80 strict timing cases 0 differences; **approved at source-model level** |
| `review_final_v1911.md` first half | PPL/compiler + timing | v1.911 `7cf66e01...28e1`, PPR `b2976e74...` | HIGH (terminal `CREATE_MATRIX` during trailing P/R lobes), MEDIUM (unguarded `waittimer(18000)`), LOW items; fixed in the next build |
| `review_final_v1911.md` re-review | same | **v1.911 `716478bb357b...8682`**, PPR `b2976e74...` | Accept; HIGH and MEDIUM resolved; diff verified exact (reverse-apply reproduces `7cf66e01`) |
| `review_physics.md` | MR physics, did not write code | v1.8 `3b420376...`, **v1.81 `545a14ec...`**, v7 `6a0d222b...`, **v1.911 `716478bb...`** | v1.81 read relocation ACCEPT; v1.911 ACCEPT WITH CONDITIONS; follow-up section 7: Bloch deviation accepted as documented deviation, v1.81 pathway spread dispositioned as model artifact |
| `review_validation.md`, `review_compiler.md` | validation / compiler | intermediate builds | Interim findings, folded into the final builds |

No change shipped on the sole word of its author. Reviews approve only the hashes in the third column.

## 17. Inconsistencies found among the documents

1. `compiler_v181_final.md` records v1.81 `9fca0a13` with image 56501 B and margin 163; the final `545a14ec` is 56517 B and margin 147 (`v181_review_fixes.md`, reproduced by the audit run for this report).
2. `review_final_v1911.md` first half describes E144 as `esp<13`, ESP 14 and 15 accepted and ESP 16 newly accepted, TR floor 191 / 198 ms; the final build uses `esp!=13`, rejects ESP 14-16, and has TR floor 192 (accepted 193) versus v7 198 (accepted 199). The re-review section is authoritative.
3. `v181_guards.json` still records `9fca0a13` and `all_pass` false (the 60-us lag cases); `v181_review_fixes.md` records a scratchpad re-run on `545a14ec` with the same outcome. The file itself was not regenerated.
4. `physics_findings.md` and `plan.md` pose the hardware-ceiling, delay-semantics and navigator-contract questions as pending; the final dispositions rely on the inherited played envelope and are listed as held / scanner-verify rather than answered.
5. `review_physics.md` mentions "+788 bytes" v1.81 image headroom; the compaction in `compiler_v181_final.md` resolved it (now below v1.8's model).
6. The handoff describes the v1.911 DAC triplet as "approximately" -6460 / -4774 / -8146; the source computes them with integer rounding from the PPR crusher values (E142 lattice).
7. The v1.81 PPR is the acquired test1e protocol, not the repository v1.8 PPR, and carries a `G:\J_Figger\` path while the v1.911 PPR does not.
8. `validation/event_gates.json` records `overall_pass: false` by design ("stays false until the delegated Bloch grid passes"); the Bloch strict gate then failed and was dispositioned as a documented deviation (section 9.3), so that flag was never flipped. Its `event_gates_pass` is true with zero failures.
9. `review_physics.md` says the v7/v1.911 on-resonance ratio holds "in all 9 cases"; a grid with 4 B1 x 3 phases has 12 B0 = 0 cases. The ratio range quoted (0.99998-1.00001) is consistent with `final_physics_grid.md`.
10. `review_physics.md` Finding 2 text still says the grid's recorded hashes are `9fca13eb...`/`7cf66e01...`; its section 7 (written after the rerun) confirms the grid now records `545a14ec` / `716478bb`, which is what the file contains.

## 18. What is NOT claimed

* Nothing here is vendor-compiled (no PPLC, Forth, simulator or linker run) or scanner-verified. The warning counts and image sizes are predictions from a historical model.
* No achieved flip angle, B1, SAR, RF calibration, gradient rating/lag, RF latency, instruction cost, eddy-current kernel, oblique-axis sum or in-vivo B0 range is known.
* Every signal-gain and b-value statement is a model prediction with the stated assumptions. The diffusion-aware EPG is conditional and instantaneous-RF.
* Scanner checks are ordered in `SCANNER_TEST_PLAN.md`; error meanings in `ERROR_CODES.md`.

## 19. Reproduction

* `python examples/build_v181_ppl.py` and `python examples/build_v1911_ppl.py` write the PPL and PPR (never run the old `examples/build_v19_ppl.py` main; it overwrites originals). Use `generate_ppl()`/`generate_ppr()` or the builders' `build()` functions to regenerate in memory and compare.
* `python examples/v181_v1911_static_audit.py <ppl> [--method-only --baseline-source docs/v181_v1911/baseline_v7/FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl]` for section 11.
* `python examples/validate_v181_v1911.py` (event gates), `python examples/validate_v181_guards.py` (v1.81 guards; the 60-us lag cases are expected to report), `python docs/v181_v1911/review_checks/final_physics_grid.py --isodelay-probe` (re-runs only the non-Bloch sections in about 106 s and merges the Bloch, off-resonance and b-tensor sections from the earlier full run only when the recorded input hashes are identical; a full Bloch regeneration, the default with no `--sections` restriction, took 2474 s).
* All of these write into `docs/v181_v1911/`; run from a scratch copy if you want to keep the recorded JSONs.

## 20. Upload package

`dist/v181_v1911_upload_candidates.zip` contains the four scanner files (`sequences/`), the six v19 RF libraries needed by v1.911 (`rf/`, byte-identical to the v7 ZIP and to `scanner/rf/`), this report, `ERROR_CODES.md`, `SCANNER_TEST_PLAN.md` and a `README.md` stating "source-validated candidates; NOT vendor-compiled or scanner-verified". The v1.911 PPL references the six RF libraries by `g:\J_Figger\seqlib19_*.seq`; the v1.81 PPL references only stock `c:\smis\seqlib` libraries and vendor includes (`stdfn_15.pph`, `var_20.pph`, `offst_20.pph`, `m3040_15.pph`, `m3031_15.pph`, `tstex_15.pph`, `g3040_15.seq`), which are already part of the scanner toolchain used for v1.8 / v1.91 and are not redistributed. SHA-256 of every file inside the ZIP and of the ZIP itself is in `dist/SHA256SUMS.txt` (the ZIP hash cannot be embedded in the ZIP or in this report). The ZIP is built deterministically with Python `zipfile` (sorted names, fixed 2026-10-08 timestamps, fixed attributes).
