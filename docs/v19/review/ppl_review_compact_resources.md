# Independent review: compact compiler-resource candidate

Date: 2026-10-06. The reviewer inspected the generated source, generator and error tables, ran bounded source-mapper checks, and edited only this report.

**No blocking or major source defect found in the exact candidate below.** The changes reduce diagnostic literals and reuse an existing array without changing successful method calculations, guard conditions or normal control features. They remain a compiler-resource trial: neither E106 resolution nor scanner compilation is established by this review. The earlier conversion-only trial still failed E106 at the same console locations.

## Exact reviewed bytes

| File | SHA-256 |
|---|---|
| `examples/build_v19_ppl.py` | `5dd76bc6f7825d531209d191c5364c0c1ebf23ce619013863e8e7f1db83e208a` |
| v191 PPL | `2542cddc68a047752d8e7b92e7ef1ca5acf078dee43c5f8f8fe60d0eb1c05582` |
| v192 PPL | `6a70f90ccf4995f322ca4aec0729b802d08309169f443f397d54ce94b0a92fc3` |
| v191 PPR | `faa77a11c2da4c5fe9876d6a842b9bc3025c66ddc09eaa4e8270dec9350faf0c` |
| v192 PPR | `678f2af5bb2fa205c2b7cb9402879d9ce1e98ed8e2c5fa4264c318b3e6898fbf` |
| immutable v18 PPL | `3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2` |
| `scanner/rf/v19_research_rf.seq` | `cca9935e58833c3c61fb5e76cc577659914f5c250cf2449676affd12d088bf5c` |

Both PPLs reproduce byte-for-byte from in-memory generator calls. Independently reconstructed per-method error tables match the saved JSON exactly (135 ss-MGOT codes; 129 Alsop codes). PPR and RF hashes retain the previously reviewed values.

## Terminating diagnostics and control flow

`compact_stopping_diagnostics()` masks comments with equal-length whitespace and rewrites only a real `printf` immediately followed by `; goto end;`. It replaces that call with one scalar assignment, preserving the original semicolon, goto and controlling statement. This matters for unbraced guards: the replacement remains a single statement. The insertion-only compactor redirects its terminating calls to `v19_fail`, which immediately aliases `end`.

I reconstructed uncompacted generation in memory by disabling only the two diagnostic compactors. After omitting printf statements and diagnostic-code assignments, and normalizing `v19_fail` to its `end` alias, the complete preprocessed computational/control token streams are equal: 26,974 tokens for ss-MGOT and 25,623 for Alsop. This includes all guard conditions, calculations, labels and successful event instructions. All 718 comment tokens/blocks per generated file are unchanged between these reconstructions, including the parameter-list comment. No actual string literal contains a misleading `printf(` occurrence. All omitted original printf argument expressions in the tables are pure arithmetic/reads: there are no function calls, assignments or increments with lost side effects. This establishes the transformation for these sources, rather than claiming the regex is a general-purpose PPL parser.

`v19_error_code=0` occurs before the first executable source guard and before the executable include following it. Every later diagnostic-code write immediately precedes a terminating goto. The shared handler prints only when that code is nonzero; ordinary completion therefore prints no error. The largest code, 135, fits signed int. Original human-readable messages and original value expressions remain in the method-specific JSON tables; the console now prints the code rather than the original interpolated values.

## Multiplier overlay

`v19_mul` expands to `crusher_dac`, which is an ordinary non-parameter int array with its original `MAX_CRUSHER_ETL` capacity. The method gate rejects `crusher_schedule!=0` before any multiplier write. There is no executable assignment to `crusher_schedule`, so its accepted zero value remains fixed through the shot loop. ETL is checked against 1..64 before multiplier indexing. Later native reads of `crusher_dac` are confined to the nonzero-schedule setup/benchmark/shot-matrix branches or the nonzero-schedule calls of `PREPARE_NEXT_CRUSHER`. Accepted method playback takes its dedicated train path and reads the aliased multiplier values. The constant native crusher path uses the saved amplitudes.

With `v19_on=0`, the multiplier writes are skipped, preserving native scheduled-crusher array contents and modes. The seven mapper tests passed, including RF identity and complete crusher-array equality with v18 for control schedules 0, 1 and 2, plus nominal and perturbed method RF/gradient/ADC identity and multiplier-overlay equality. No acquisition, CEST, crusher or phase-encode capacity was reduced. Removing the separate 64-int multiplier array saves 128 nominal declaration bytes; the new int diagnostic code costs two nominal bytes, for a net 126 bytes under the documented int width. This is not a measurement of PPLC far-scratch allocation.

## Completion and resource evidence

I independently mapped both v192 method and original-control protocols to natural termination (`max_shots=1000`): each completed 55 shots and 440 ADCs, with error code zero and no shared error print. The parent separately reported the same natural-completion check for v191.

Compared with the saved pre-scratch sources, independent preprocessing counts 227 to 53 printf calls for v191 and 215 to 53 for v192. Summing source string-literal contents, excluding quote characters, gives 11,789 to 4,993 characters and 11,278 to 4,923 respectively. These reductions are real source evidence; escape decoding, literal deduplication, compiler overhead and target storage remain unknown. They do not prove any particular E106 pool mechanism or that the candidate now fits it.

The full event/Bloch validator for these exact compact hashes was still running when this report was written. Earlier full numerical validations belong to their earlier recorded hashes. No console compilation, G-drive RF-file presence, scanner event export, calibrated EVO gradient strength or hardware validation is asserted here.

## Follow-up: preserve the successful validator Duration report

The preceding review covers the pre-restoration `2542cdd…` / `6a70f90…` sources. After that review, the parent identified one classification defect: the inherited `validate==1` success branch prints `Duration=%ld` and then terminates normally. The initial compactor had mistaken that print for a fatal diagnostic. My initial review established computational/control equivalence but missed this diagnostic distinction. Its initial no-defect verdict therefore needs this correction; its hashes and numerical-run scope remain historical.

The final compactor exempts the `Duration=` call and leaves its original printf, numeric expression and goto intact. I independently examined all 101 inherited printf calls immediately followed by `goto end`, including their surrounding guards. Duration was the only successful stop report in that set. The remaining compacted calls belong to invalid-parameter, infeasible-timing, amplitude/storage-limit or internal-failure branches. The application tables no longer contain a Duration error. No further successful stop was found misclassified.

| Final file | SHA-256 |
|---|---|
| `examples/build_v19_ppl.py` | `7fdc1c29f16afd0c8ce73f2b1cf7afd93d36e9f54ad4fe69d7565b79295b52eb` |
| final v191 PPL | `cc452f0f8bd14e1934f0dcfcaf614ddd652ffe9546ea283b978e2ea6e75674b6` |
| final v192 PPL | `f2ce7ccbd70fbfdb09fe2da925356d61fee2e6d5a5012eeaffa87888766616b8` |

Both final PPLs reproduce byte-for-byte from the generator, and their reconstructed error tables match the saved JSON (134 ss-MGOT and 128 Alsop codes). After omitting only printf statements and error-code assignments, the complete preprocessed computational/control tokens match their exact preserved pre-restoration snapshots `validated_pre_validator_report_v191.ppl.txt` and `validated_pre_validator_report_v192.ppl.txt`, whose hashes remain `2542cdd…` / `6a70f90…`. The fix restores a diagnostic and renumbers later application error codes; it does not change successful acquisition calculations or control flow.

All eight mapper tests independently passed. Additional direct `validate=1` mappings using both the method and original-control protocols produced `Duration=126000\n`, error code zero and zero ADCs in each final PPL. The control Duration output matches v18 in the regression test. Final source literal-content totals are 5,007 and 4,937 characters, with 54 printf calls per preprocessed file.

**No blocking or major source defect found in these final restored bytes.** The full validator started before this restoration and uses the preserved pre-restoration input hashes; its results must remain attributed to those hashes. The computational-token bridge above is independent follow-up evidence, not a relabeling of that numerical run. E106 resolution and console compilation of the final bytes remain unverified.

## Final completion note (2026-10-07)

I inspected the completed `event_validation/summary.json`, `control_identity.json`, `rejection_tests.json`, `convergence.json` and `compiler_compatibility/validator_report_event_identity.json`. The full numerical run completed in 677.2216491699219 seconds and records `control_identity_all=true`. Its actual input hashes remain v191 `2542cddc68a047752d8e7b92e7ef1ca5acf078dee43c5f8f8fe60d0eb1c05582` and v192 `6a70f90ccf4995f322ca4aec0729b802d08309169f443f397d54ce94b0a92fc3`. All 19 rejection cases per method record zero RF and ADC events. Convergence outputs are complete: z-grid maximum differences are approximately 4.32e-7 and 9.98e-7; independent ODE comparisons differ by at most 6.69e-10 and 7.42e-10. Both mapped methods record zero timer overruns.

The bridge file explicitly links these historical run inputs to the final `cc452f…` / `f2ce7c…` hashes, which I verified against the present files. All seven two-shot comparisons per method pass: nominal method, rfcal550, compensation800, original control, increasing, decreasing and alternating controls. Recorded RF, ADC, all three gradient histories, matrix comparisons and sync-relative RF timing are identical. This complements the independent computational/control-token equivalence above and closes the pending numerical follow-up without relabeling the completed run's input hashes. Separate timer-history equality is not a field in that bridge artifact.

No new source defect was found. Scanner compilation and E106 resolution remain unverified; this completion note records source-level numerical evidence only.
