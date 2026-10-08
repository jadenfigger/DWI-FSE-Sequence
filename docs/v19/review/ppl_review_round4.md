# Independent PPL confirmation, round 4

Date: 2026-10-06. Independent static review of the regenerated source; no vendor compiler, simulator or scanner execution. The reviewer wrote only this report.

**Verdict: no new blocking or major PPL finding on the bytes below.** The two-cycle and crusher-geometry gates are confined to method setup. This confirmation does not establish hardware timing, RF calibration or physical efficacy outside the independently simulated cases.

## Exact reviewed files

| File | SHA-256 |
|---|---|
| `examples/build_v19_ppl.py` | `e232da4e528ce7d3f0f6ddd0f7e0512449cae6210500d5a9b1ef022bed223eca` |
| v191 PPL | `b8d2c4cae6443ba150464db95fcd113a787fd70f0cf9de64bc85da7cf255625d` |
| v191 PPR | `faa77a11c2da4c5fe9876d6a842b9bc3025c66ddc09eaa4e8270dec9350faf0c` |
| v192 PPL | `7e6393eaaac57f23d1f0f5d1718315ddf29e9df7ceffd923a1fd114920d20e55` |
| v192 PPR | `678f2af5bb2fa205c2b7cb9402879d9ce1e98ed8e2c5fa4264c318b3e6898fbf` |
| v18 PPL | `3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2` |

I imported the generator without executing its write functions and compared `build()` and `build_ppr()` directly with every on-disk output: all four match byte-for-byte. The v18 baseline retains its required hash. Independent line comparison finds 15 insertion hunks and no replacement/deletion hunks in each method PPL relative to v18.

## Confirmation of the changes

- **Two cycles only:** v191 line 2208 / v192 line 2199 rejects `v19_cycles!=2` inside `if (v19_on==1)`. The parameter editor still advertises 1..8; selecting another value now exits with an explicit explanation. Neither method silently substitutes another value.
- **Crusher geometry:** v191 lines 2275–2278 / v192 lines 2266–2269 require both saved crusher amplitudes to be strictly negative, then test rounded area ratios against C/D 3.81..3.85 and C1/D 2.53..2.57. Zero, opposite polarity and matching positive polarity are rejected. This correctly limits the polarity to the shipped geometry that was simulated.
- **Gate placement:** all these checks occur in once-per-scan method setup, before `v19_mode=1`, the validator exit and any RF/gradient playback or ADC. Earlier list definitions configure memory; they do not start playback. Rejection uses the existing `goto end` exit. There is no new calculation inside a timed shot window.
- **Integer widths:** area products use explicit `IntToLong` conversion and `L` constants; chained division/multiplication uses the existing PPL arithmetic syntax. The prior independent-crusher checks reject -32768 and enforce ramp 100..1000 us, train flat 1..5000 us, first flat 1..10000 us and DAC magnitudes <=32767. With declared rephase flat <=5000 us, the largest C or D area product is 196,602,000 DAC.us, and C1 is <=360,437,000. The new largest multiply-before-final-divide is `(D/100)*385 <=756,917,700`, comfortably below signed-32 maximum 2,147,483,647; `3*D <=589,806,000` also fits. No new 16-bit narrowing is introduced.
- **Shipped protocol:** D=2,574,000, C=9,867,600 and C1=6,578,400 DAC.us. Exact ratios are 3.8335664 and 2.5557110. PPL rounded C bounds are 98,069..99,099, with actual 98,676; C1 bounds are 65,122..66,151, with actual 65,784. Both pass with clear margin.
- **Source syntax and reporting:** the gate expressions, polarity comparisons, `%ld` long fields and `%d` integer fields use existing syntax. Both regenerated PPLs have zero unterminated `printf` starts. The new rejection messages contain literal `\n` escapes and direct the user to the event validator; the first-imaging-RF report remains the corrected centre expression. The geometry message could additionally name the required negative polarity, but its omission does not alter rejection.

The ratios are integer-rounded comparisons: division by 100 DAC.us makes the accepted interval edges slightly different from exact real-valued 3.81/3.85 and 2.53/2.57. This is an informational precision limit, not a new blocking finding. The shipped values are far from the edges. Physical acceptance should be based on the boundary simulations, not on the appearance of decimal constants alone.

## Control identity and retained limits

`v19_on=0` skips the entire new gate, keeps `v19_mode=0` and executes the existing v18 path. v18 statements remain intact, and the new rejection checks add no work to its padded shot windows. The previously reviewed branch tests and research-RF library dependency remain. A source-level event comparison is still needed to substantiate control identity under the assumed instruction-cost model; only a vendor compiler/console trace can confirm it on hardware.

Round-3 closures of spoiler/post-ADC timer bounds and the corrected RF-centre reporting remain present. The existing limitations concerning inferred timing costs, RF scale calibration and effective RF gate-off margin remain unchanged. No vendor compilation or scanner deployment was performed.
