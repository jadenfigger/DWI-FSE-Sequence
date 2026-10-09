# v1.81 compiler image-growth resolution (author record, not an approval)

Date: 2026-10-08. Author: v1.81 compaction worker. This is a source-model
record for independent PPL/compiler, timing and physics reviewers. Nothing here
is vendor-compiled or scanner-verified.

## Hashes

| Object | SHA-256 |
|---|---|
| v1.8 baseline PPL (unchanged) | `3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2` |
| v1.81 PPL before compaction | `3c90b80b31bf3cecfc38b8c1300061181fb3df0bcc3f60fb93027a45b6b51c7c` |
| **v1.81 PPL final** | `9fca0a13eb773d0e06d7bde0175dff4a3cd84d705db4211717fee9d23168f8b1` |
| v1.81 PPR (unchanged by this step) | `ad82112ddfc7389a58caea6598cb5eb7583a271e71e62cd8c006190c52cdb159` |
| `examples/build_v181_ppl.py` final | `d8178506016e24aa44912d6438131aa261d98790e0058d50ffab93071e2978b8` |

Reproducibility: the builder was run twice; both runs printed identical hashes,
and the in-memory `generate_ppl()` output equals the file bytes. No tracked file
changed (`git diff --stat` empty).

## Static gate (`examples/v181_v1911_static_audit.py`, unchanged tool)

| Metric | v1.8 | v1.81 before | v1.81 final | Gate |
|---|---:|---:|---:|---|
| Estimated image, bytes | 56664 | 57452 | **56501** | <= 56664: pass (163 margin) |
| Code AST nodes | 13097 | 13307 | 12957 | — |
| String bytes model | 6494 | 6736 | 6695 | — |
| Array bytes model | 16118 | 16118 | 16118 | — |
| Forward gotos | 145 | 21 | 21 | <= 145: pass |
| Predicted W007/W008 | 11 | 11 | 11 | identical identities: pass |
| Largest conditional body, nodes | 369 | 369 | 369 | not increased: pass |
| Undefined / unreferenced labels | 0 / 0 | 0 / 0 | 0 / 0 | pass |
| Added long literals, risky comments, function macros | — | none | none | pass |

All eight audit checks pass. Outputs: `compiler_v181_final_static_audit.json`,
`..._static_audit_v18_baseline.json`, `..._static_audit_pre_compaction.json`.
The gate was not relaxed. The estimate is still a model; actual PPLC/Forth
image size and warning list are scanner-verify.

## Compaction applied (one feature, in the new copy only)

**CEST/MTC compiled out** (`#define MTC` removed in v1.81 only). Measured alone
it saves ~1172 model bytes; the larger candidates (MULTIPRESAT, DE, AUTOGATE,
CHESS) were not touched.

Justification: `mtc_on` is 0 in every protocol in the repository (97 PPR/MRD
occurrences, 55 PPR `VAR` lines, including the test1e protocol); the v1.8
history already records the MTC crusher as disabled. v1.81 is a DW-FSE
candidate with no CEST requirement.

Exactly what changed:

1. `#define MTC` deleted. The PARAMLIST, declarations and PPR are untouched,
   so every CEST variable still exists and old protocols still load.
2. The unconditional setup block (`tselmtcl`, `mtc_rfnum=17`,
   `rwt[17]=tselmtc_ms*10`) is kept unconditionally. `rwt[17]` is otherwise set
   by `NEWSHAPE_MAC(17, ...)`, so keeping it removes any dependence on whether
   frame 17 could be selected elsewhere.
3. The unconditional per-TR expression `templ1 = (no_cest_pulses*tselmtcl ...)`
   is kept (it is dead: `templ1` is overwritten before any read). Each per-TR
   `if(mtc_on){ }` test is kept as an empty shell. Both are kept only so that
   untimed statement cost, and hence modeled event timing, is unchanged (see
   below; without them the manual cost models showed TR shortening by ~1 us).
4. Compiled out, all reachable only with `mtc_on!=0` or never used otherwise:
   the `mtc_list` InitList/POSPULSE (it is the last list created, so no later
   list addresses move), the `mtc_mat` (matrix 25) calculation and its
   `caldelay` (inside the fixed 3275-us `waittimer(32750)` matrix window, so the
   window length is unchanged), the CEST frequency setup, the CEST TR term and
   inter-CEST check, and the CEST pulse loop.
5. New rejection, immediately before the former CEST TR block (where v1.8
   performed its own inter-CEST rejection; on both the normal and the
   `validate==1` path, before any RF):
   `if (mtc_on!=0) { printf("V181 CEST/MTC not supported\n"); goto end; }`.
   `end:` is the early backward exit hub, so no forward goto is added.

Not done, by choice: error messages were not shortened or merged into a shared
coded path. The single feature removal met the gate while keeping every v1.8 and
v1.81 message text byte-identical, which is simpler to review.

## Behavior evidence (repository mapper, pre-compaction `3c90...` vs final `9fca...`)

`compiler_v181_final_event_equivalence.json`: all RF (time, frame, multiplier,
phase, frequency, duration, level), ADC (start, phase, frequency, sample
period, completion) and per-axis nonzero gradient segments compared relative to
the first library RF. Results for all **eight cost models** in three states —
default PPR 6 shots (dummy/navigator plus imaging), actual imaging 2 shots
(`no_disacq=0, nav_on=0, no_views=128`), and diffusion off 2 shots: **0.0 us
maximum time difference and 0 non-time mismatches in every case**, and no new
non-narrowing/matrix_active flags. Absolute time of the first RF moves ~11-26 us
earlier (one-time pre-scan setup no longer creates the CEST list/matrix); this is
before the first RF and does not affect any interval.

`compiler_v181_final_rejections.json` (manual_x0.8): all 37 guard cases from
`validate_v181_guards.unsafe_cases()` give byte-identical messages and 0 RF / 0
ADC in both versions. `validate=1` default gives the same `Duration=126000`.
`mtc_on=1` (also with diffusion off, array mode, and validate mode) now rejects
with 0 RF / 0 ADC; previously it ran CEST pulses (9 library RF in one shot).

## v1.81 error-message table (code = exact message text)

v1.81 uses v1.8's text messages, not numeric codes. All inherited v1.8 messages
are unchanged. The V181-specific rejections, all before RF:

| Code (message) | Meaning |
|---|---|
| `V181 DWI requires flow compensation off` | `diff_on==1` with `flow_comp_on!=0`; the relocated read prephase is not a flow-compensated waveform. |
| `V181 ESP leaves no read balance` | Diffusion off: pre-read balance after the enlarged 100-us list window (`te_balance_bl_temp1`) <= 25 ticks. |
| `V181 ESP leaves no train read balance` | Diffusion on, ETL>1: train read balance (`te_balance_bl_temp1_esp`) <= 25 ticks. |
| `V181 read relocation scale outside DAC` | Scaled relocated prephase `grp_dp*(tref+tramp)/(tdp+tramp)` outside +/-32767. |
| `V181 first read prephase exceeds DAC` | Fused first read prelude `|gr_dp - scaled|` exceeds 32767 or `crusher_max_dac`. |
| `V181 first read prephase exceeds slew` | Fused first read prelude exceeds `crusher_slew_dac_100us` over `tramp`. |
| `V181 CEST/MTC not supported` | **New in this step.** `mtc_on!=0`; CEST/MTC is compiled out of v1.81. |
| `Matrix setup exceeds timing budget` (inherited text) | Threshold changed earlier in v1.81 from 24500 to 27250 ticks for the 3275-us window (not changed in this step). |

## Unchanged by this step (for reviewers to confirm, not re-approved here)

Read-prephase relocation, block-C deadline / slice-list restart 100-us window
(-815 ticks), enlarged setup windows and +895-us TR accounting, the exit hub and
all other V181 guards are byte-identical to `3c90...` apart from the diff
described above (`diff` of the two sources shows only MTC-related lines).

## Open items / limitations

- Vendor compiled size, warnings and include versions remain scanner-verify.
  The 163-byte margin is under the model's conservative relative gate only.
- Observation by source inspection only, not changed: in `validate==1` mode v1.8 jumps to
  `averages_loop` before the flow-compensation V181 guard, so the console
  validator path does not show that message (normal run still rejects before
  RF). Inherited structure; reviewers may wish to consider it.
- The equivalence and rejection scripts were run from the session scratchpad
  (outside my file ownership); method and full results are in the JSONs. The
  pre-compaction source is reproducible from the earlier builder revision with
  hash `3c90...`, which is recorded above.
- Any earlier result JSON referencing `3c90...`, `48d11...` or `33e7...` does
  not cover the final bytes except where the equivalence above carries it.
