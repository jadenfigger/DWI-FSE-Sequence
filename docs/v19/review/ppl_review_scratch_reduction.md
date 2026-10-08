# Independent review: PPLC scratch-reduction trial

Date: 2026-10-06. Scope: the final generator's `reduce_setup_conversions()` and generated PPLs addressing the console W010 warnings and E106 far-scratch overflow. The reviewer edited only this report.

**Verdict: no blocking or major source defect found in the final candidate below.** The final conversion rewrite preserves signed expression widths and is confined to untimed method setup. The reported E106 remains an unresolved compiler-resource limit until the console compiles this candidate successfully. Reduced conversion-call counts do not measure the compiler's scratch allocation.

## Exact files

| File | SHA-256 |
|---|---|
| `examples/build_v19_ppl.py` | `1b293b32510d2f35b9b499873c4dd8a35703bf1751de7e330505d8fa9575239f` |
| v191 PPL | `ada0e02cf3aab961393721ae2ea90acbe223ca18b6223507d090828dec88cac6` |
| v192 PPL | `f75914d08a79a480dd83bd5c9f0135aec9952ce4500b6759be39bc5d3be6df42` |
| v191 PPR | `faa77a11c2da4c5fe9876d6a842b9bc3025c66ddc09eaa4e8270dec9350faf0c` |
| v192 PPR | `678f2af5bb2fa205c2b7cb9402879d9ce1e98ed8e2c5fa4264c318b3e6898fbf` |
| v18 PPL | `3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2` |

The saved pre-scratch source snapshots reproduce the prior path-adjusted hashes: v191 `78ca063f914561513fb6967d76e93cbc9829542b2346e507b4640846843b8e06`; v192 `83d669c59b412c5f0da833e4ff6280dd1a0b9b9c5229f764663a812486b601e4`. These are comparison inputs, not final candidate hashes. I independently verified final generator/PPL/PPR byte reproducibility and the unchanged v18 hash.

## Why the final rewrite is safe

The abandoned adjacency-based version was not generally sound: `long_value + IntToLong(x)*y` can become `long_value+x*y`, allowing a 16-bit product to overflow before it is widened. Likewise, removing the first two casts from a left-associative sum can change its first addition to 16-bit. This inference is absent from the final reducer.

The final reducer uses three forms:

- In-range integer constant `IntToLong(n)` becomes `nL`.
- A complete assignment of a verified int expression to a declared long becomes `long_destination=(expression)`.
- Every other verified int expression becomes `(0L+(expression))`.

Under the documented PPL rules (manual section 4.8.7.1), the original conversion first receives a signed 16-bit argument and then sign-extends it. The replacement's inner parentheses preserve that original argument evaluation, including any 16-bit arithmetic wrap. The outer addition to `0L` sign-extends that same result before any enclosing product, division, comparison or addition. Direct complete long assignment performs the same documented signed extension. No function argument is evaluated twice.

I independently preprocessed the final v191 source with the supplied vendor includes, parsed its declaration tree, and checked all **66 identifiers** admitted by the base int whitelist or added int declarations. Every identifier is declared `int`; no missing or long declaration was found. This includes `tramp` and the `rf_length` int array from the vendor declarations, common-int parameters, v18 scalar ints, and added method ints. An int array element remains int regardless of indexing syntax. The actual rewritten arguments use only these identifiers, in-range decimal constants and ordinary int arithmetic/indexing.

The reducer rejects unknown identifiers, long-valued identifiers, unsupported expression characters and constants above 32767. I exercised the former product counterexample using admitted int identifiers: it now emits `v19_r+(0L+(v19_gabs))*v19_cycles`, retaining a long product. `IntToLong(sm_delta_us)` is rejected because its argument is long; that original call would narrow the argument to int before sign-extension and cannot be replaced by simple long arithmetic. Complete `v19_r=IntToLong(tramp)` becomes `v19_r=(tramp)`, with the long destination supplying conversion.

This is a review of the actual generated expressions and declared types. The reducer is intentionally restrictive rather than a general PPL expression optimizer; new expression syntax or names require renewed verification.

## Scope and timing preservation

The reducer runs only on the combined once-per-scan method setup insertion. Across the full generated source, `IntToLong` call counts decrease from **363 to 196** in v191 and **324 to 196** in v192: 167 and 128 calls removed respectively. No acquisition, CEST, crusher or RF arrays were resized, and no method parameter capacity was reduced.

I compared each final source with its saved pre-scratch snapshot. The entire tail beginning at the inherited `CREATE_MATRIX(ss_mat,0,0,0)` and continuing through the control calculations, padded windows, method matrices, RF/gradient/ADC shot and termination is **byte-identical**. Thus this change adds no work inside a successful timed RF/ADC window. The once-per-scan setup costs change, as intended; prior absolute startup timestamps should not be equated without their synchronization reference.

The coordinator's six-test mapper run includes old/new comparisons for nominal parameters, RF calibration 550, compensation flat 800 and the accepted negative crusher boundary. Those comparisons cover RF signatures, ADC timings relative to synchronization, gradient memory/samples/starts/segments and every `v19_*` value. This review independently confirms the static width/type argument and source boundaries; it does not substitute a vendor compile for those mapper checks. The full event/Bloch validation on this final candidate was still running when this report was written.

## Warning fixes and compiler limits

Exactly three inherited generated-copy comparisons now use `==(-32767-1)` in place of `==-32768`. The expression denotes the same signed minimum value using individually in-range literals, so the invalid -32768 crusher/custom-percentage values remain rejected and valid -32767 values remain accepted. These changes occur before playback; the actual v18 file is unchanged. Whether the vendor emits W010 after this rewrite is still a console result to verify.

The inherited W008 near `offset_frequency(fov_slice_freq+slice_freq_var)` remains separate from E106: `slice_freq_var` is long and the function expects int. The documented implicit conversion takes the low 16 bits. No new frequency conversion or timing change was introduced in this trial.

The supplied manual does not define E106, its far-scratch pool capacity, temporary reuse strategy or relationship to declared-variable storage. The error's appearance at later inherited arithmetic after expanded setup makes expression-generated scratch a plausible explanation, but does not prove a specific allocator model. Removing conversion calls is a targeted compiler-complexity reduction; it does not establish a measured amount of reclaimed scratch. Shrinking large inherited arrays would change control capabilities and is not justified by this evidence alone.

Successful console compilation of these exact final hashes remains outstanding. Hardware timing, RF/gradient calibration, SAR, image quality and deployment are not approved by this review. Prior numerical results retain their original input hashes until a completed candidate run or a documented comparison bridges them.

## Completion follow-up: full candidate event validation

The full event validator subsequently completed on the **same reviewed candidate hashes**, v191 `ada0e02cf3aab961393721ae2ea90acbe223ca18b6223507d090828dec88cac6` and v192 `f75914d08a79a480dd83bd5c9f0135aec9952ce4500b6759be39bc5d3be6df42`. I inspected the completed summary and supporting JSON outputs. Elapsed time is **695.1277010440826 s** and `control_identity_all` is true. The earlier pending-at-write statement above describes the historical state; the numerical run is now complete.

The detailed control comparison records identical RF, ADC, S/P/R gradient events and v18 matrix contents for both control paths, plus the increasing/decreasing/alternating crusher control comparisons. All **19 rejection cases per method** stop with zero RF and ADC events. There are zero ignored list selections, zero timer overruns and zero matrix-use issues. The reported narrowing and active-matrix diagnostic counts remain the same as the original v18 control; this is not a claim that every raw diagnostic is absent.

Completed numerical convergence results:

- z3000/z6000 maximum complex difference: **4.32e-7** for v191, **9.98e-7** for v192.
- RF one/four-substep maximum complex difference: **3.25e-16** / **7.58e-16**.
- v191 y32/y64 maximum complex difference: **1.15e-4**.
- Five-spin ODE versus exact-rotation maximum component difference: **6.69e-10** / **7.42e-10**, using the corrected physical-landmark windows.

For reproducibility, completed output SHA-256 hashes are:

| Output | SHA-256 |
|---|---|
| `summary.json` | `9990a2df190edb7bf933a227bee7491c7af974792bc9fc10d07cebf4755baf41` |
| `convergence.json` | `79e4e15d6d28972376e4c54f9a2edd0ce2ae9e64defda97d6d9e9802cfedc455` |
| `rejection_tests.json` | `7ca09702a7c292dd74f4b9876444dbec08ce0a279a70e017c33b504811a95116` |
| `control_identity.json` | `70d0172000bebd3e7668b8ecbfe6e564c4018b15d22a2a99aaedf41aae37e6a3` |
| `hazards.json` | `48defb3c02d05f177ad5e247473d0671b1aa01c94127ae7b101328b4cf5c9e21` |

This closes the pending full numerical-validation outcome for this candidate. It does **not** establish successful vendor compilation or resolution of console E106/W010. Those compiler outcomes and the hardware/calibration limits above remain unverified. No new blocking or major source finding emerged from these completed outputs.
