# Independent PPL review: console-preprocessor compatibility

Date: 2026-10-06. This review concerns the source changes responding to the reported console warnings and fatal `V19_COMP` macro-argument expansion failure. It is a static/source-preprocessing confirmation, not a successful vendor recompilation. The reviewer edited only this report.

**Verdict: no new blocking or major source finding on the hashes below.** The generator removes the added comment/macro constructs implicated by the reported diagnostics and preserves the previously validated executable calculations. The scanner console must still compile these exact regenerated files to establish that the vendor buffer/string limits are satisfied.

## Reviewed bytes

| File | SHA-256 |
|---|---|
| `examples/build_v19_ppl.py` | `a37c9fb8fcb281811158f01b89b0c102e8631092216f7d59f4aab8d4568b0534` |
| v191 PPL | `41a938b532321b1b0a8554b01062f24edd79b77ab70c2e5d00303abff2ad91d7` |
| v192 PPL | `f8b8896dc0da45d71659b9db06a318b6773b1f2075ece703f04cfddde70e6e77` |
| v191 PPR | `faa77a11c2da4c5fe9876d6a842b9bc3025c66ddc09eaa4e8270dec9350faf0c` |
| v192 PPR | `678f2af5bb2fa205c2b7cb9402879d9ce1e98ed8e2c5fa4264c318b3e6898fbf` |
| v18 PPL | `3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2` |
| `compiler_compatibility/pre_fix_token_baseline.json` | `e5a2e184822d94edb19b2326a1559966b760f9148f9e0b9e58b9804893d1f9a8` |

I imported the generator without invoking its write functions. Both `build()` outputs and both `build_ppr()` outputs match the current files byte-for-byte. The PPRs retain their preceding hashes and the v18 source retains its immutable baseline hash. Each PPL differs from v18 by 14 insertion hunks, with no replacement or deletion hunk.

## Expansion and parameter compatibility

`compiler_compatible()` applies comment removal to each insertion before it enters the inherited source. String literals are retained, so path text, messages and labels survive. The parameter block is still the original vendor PARAMLIST structure; the added parameter rows between `V19 method ON` and `DSP_ROUTINE` contain no `//`, `/*` or `*/`. The new top header is no longer emitted. Original v18 comments and statements are intact.

All seven function-like V19 helpers (`SELECTOR`, `COMP`, `RFMUL`, `FLAT`, `RFTIMES`, `RF_START`, `RF_GO`) are expanded in the Python generator. Their bodies become ordinary statements and are not sent as large function-like macro definitions to console cpp. Simple numeric V19 constants and matrix identifiers remain object-like defines. Supported vendor macros such as `CREATE_MATRIX` and `NEWSHAPE_SETUP` remain in their original call form.

The argument collector tracks parentheses and brackets and protects quoted strings. Substitution uses identifier boundaries, preserving unrelated identifiers and quoted text. For the actual calls, destinations, array indices, constants and expressions are substituted without new arithmetic rearrangement. The previously problematic V19 comment text containing vendor macro names is removed from the emitted additions.

## Preservation of executable calculations

I independently preprocessed both final files with the repository preprocessor, removed complete `printf` statements, and compared the remaining token kind/value stream with the saved pre-fix baselines:

| Method | Computational token count | Token-stream SHA-256 |
|---|---:|---|
| v191 | 26,598 | `d8cf3fb97e1a4acf5bfaeacbc2a6a4c258003db0e4d92cc599868dec102fa09c` |
| v192 | 25,360 | `7bc2f6524da576e57e89d7dc2731e1443f4d19ecea6551b7df5b5447168ebbf3` |

Both counts and hashes match exactly. I also disabled the compatibility transformation **in memory**, reconstructed the generator's unexpanded insertions, preprocessed them through the same vendor include files, and compared their computational tokens directly against the final source: identical. No temporary implementation file was written.

This establishes equality of assignments, expression order, checks, branches, labels, gradient/RF/ADC calls and timer calculations in the repository's supported preprocessing model. The historical event/Bloch results remain evidence about the same computational stream; their older source-byte hashes must not be relabelled as the new hashes. This check does not establish identical vendor compiler output or real console instruction timing.

## Short print calls

Added literals are split into calls of at most **48 source characters per literal**, including all continuation chunks that no longer begin with `V19`. My direct check found a maximum of 48 in both methods. Escapes and complete format conversions remain atomic, including `\n`, `%d` and `%ld`. Arguments remain associated with their respective conversions.

An independent token-based comparison of the pre-compatibility and final source shows that concatenating the format-string bodies gives exactly the same text, and that the ordered argument-expression lists are identical. Print-call totals rise from 198 to 227 in v191 and 189 to 215 in v192 because of splitting. Added successful report calls are in untimed setup; error-report splits stay inside their existing braced rejection blocks and still exit. No print split inserts extra work into a successful timed RF/ADC section.

The value 48 is a conservative chosen bound, not a measured vendor string-limit specification. The actual console cutoff and its presentation of successive print calls are still unverified. Existing inherited v18 print literals were intentionally not rewritten.

## Remaining confirmation

The reported failure occurred in the preceding macro form. These regenerated files remove that form, but a successful vendor compile of these exact hashes has not yet been supplied. This review makes no hardware, calibration, SAR, image-quality or deployment approval. The earlier physics limitations and inferred timing/calibration assumptions remain applicable.

## Follow-up: completed source validation and requested RF path

The complete event validation subsequently finished on the original compiler-compatible PPL hashes `41a938b5…` / `f8b8896d…` listed above. I inspected its final `event_validation/summary.json`: it records those exact full hashes, `control_identity_all=true`, and elapsed time 694.1167936325073 s. These remain the historical full-run input hashes; they must not be relabelled as the later path-adjusted source bytes.

At the user's explicit request, both PPLs now contain this RF library directive at line 61:

```text
#use RF1 "g:\J_Figger\seqlib\v19_research_rf.seq" pf19
```

The final path-adjusted hashes are:

| File | SHA-256 |
|---|---|
| Generator | `6672d304878c824de67ca88e3b66e4ef3d18bc786324f0f1de49fa127b42733b` |
| v191 PPL | `78ca063f914561513fb6967d76e93cbc9829542b2346e507b4640846843b8e06` |
| v192 PPL | `83d669c59b412c5f0da833e4ff6280dd1a0b9b9c5229f764663a812486b601e4` |

Independent checks:

- Restoring the previous `USE_LINE` **in memory** reproduces each preceding compiler-compatible PPL hash exactly. Comparing those reconstructed bytes with the final bytes shows only the single RF-path directive change, with no other source change.
- The final generator reproduces both current PPLs and both PPRs byte-for-byte. The PPR hashes and immutable v18 hash remain those in the original table.
- The mapper's actual `resolve_library()` resolves both old and new directory strings to the same local file, `scanner/rf/v19_research_rf.seq`, with SHA-256 `cca9935e58833c3c61fb5e76cc577659914f5c250cf2449676affd12d088bf5c`. The RF alias remains `pf19` and all executable statements are unchanged.

This provides a source/library bridge from the completed run to the requested final path bytes. Local simulation deliberately resolves libraries by basename; it establishes neither the existence nor the contents of `g:\J_Figger\seqlib\v19_research_rf.seq` on the console. Successful vendor recompilation of the final path-adjusted hashes and console G-drive file presence remain unverified. No new blocking or major source finding was found.
