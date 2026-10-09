# PPL, compiler and upload baseline investigation

Investigation date: 2026-10-08. Source review and repository checks only; nothing
in this report is scanner-verified. Existing sequence, protocol, include and RF
files were not edited.

## Exact source baseline

The last uploaded method-only v7 archive is the authoritative ss-MGOT baseline.
The workspace is mixed: its v1.91 **PPL is combined v6**, while its PPR and the
current generator already correspond to v7.

| Object | Bytes | Lines | SHA-256 |
|---|---:|---:|---|
| Immutable v1.8 PPL | — | — | `3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2` |
| Workspace v1.8 PPR | — | — | `78c9845d090183d59cba956f36305e0e19d4a8dcdb3ae707062839159fd904da` |
| Workspace v1.91 PPL, combined v6 | 206516 | 5589 | `92bdcb79081087c29dd045cd797cb8fbdd1e4f02ff4f341b9711eef706f16e4f` |
| ZIP v7 v1.91 PPL | 168659 | 4403 | `6a0d222b6c8689fbdee5f4ae412c4d5df0bea10a7da99a309fabf5dfab04d828` |
| Workspace and ZIP v7 v1.91 PPR | 9190 | 368 | `fc7f0218f5aaf7866e44ce65331a2f6c11526d0ce04f8e2e78f44dbb6cd0ebeb` |
| Current `examples/build_v19_ppl.py` | — | — | `8965d0a160d1ecbab30161f1052733b050af5c51d25eb72d3d43378cd418ee0c` |
| v7 ZIP archive | — | — | `fc1ebff58b40b57a7045b849fc027f97e364775151a2ea3a9ace96449ee9ff95` |

Direct in-memory calls to `build('ssmgot')` and
`build_ppr('ssmgot', 'FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl')` reproduce both ZIP
members byte-for-byte. The workspace PPL exactly equals the historical
`pre_method_only_v191.ppl.txt`; its PPR does **not** equal the historical combined
PPR, which had 512-row tables. All six current `scanner/rf/v19_*.seq` files equal
the respective v7 ZIP members byte-for-byte.

For other agents, the v7 PPL, matching PPR and original error-code text were
extracted without alteration under `docs/v181_v1911/baseline_v7/`.

The main investigation agent ran the existing mapper suite: 13 tests, 11 pass
and two fail before this work. Both failures identify the workspace mismatch:
the combined PPL exceeds the method-only size budget and still contains the v18
control branch. Do not repair these by overwriting the user's original files.

## What v7 changes relative to the workspace source

The current generator and `compiler_compatibility/method_only_results.json`
establish the following changes:

- Remove the native v18 TE calculations, TE extension checks and echo-train
  kernel that the method branch always bypassed. Controls use v1.8 separately.
- Compile out nine method-rejected optional features: MULTIPRESAT, FSE3D,
  DRIVEN_EQUILIBRIUM, SKIP_FIRST_ECHOES, CHESS, AUTOGATE, MTC,
  PRESAT_FREQ_FLIP and DIXON3P. Their protocol variables remain declared.
- Reduce acquisition tables from 512 to 64 rows and the crusher workspace from
  1024 to 64 entries. PARAMLIST limits and PPR array lengths agree.
- Require `v19_on==1` and `1<=no_diff_acq<=64` before reading tables. A v7
  protocol with method off must reject before any RF.
- Renumber compact error codes. Ship the new code table with each generated
  source; the v6 table must not be reused.

These are program-size changes, not intended RF/gradient changes. The historical
v7 report records 47 protocol comparisons per method against v6, including 28
rejections, plus a completed validator. Those historical results retain their
original input hashes and do not verify a future v1.911 candidate.

## Confirmed vendor constructs and remaining model assumptions

The necessary constructs exist locally, so their availability does not require
inventing a new vendor macro:

- `stdfn_15.pph` declares `waittimer(int)`. Long arguments trigger the warning
  problem. Precompute validated timer targets into ints during setup, preserving
  their 16-bit pattern; the mapper interprets the timer word unsigned. Physical
  timer execution still requires console confirmation.
- `m3040_15.pph` defines `PULSE`, `NEGPULSE`, `NEGPULSE_SEC`,
  `MR3040_SetList`, `MR3040_Delay` and matrix commands. A secondary negative lobe
  uses separate up/down ramp frames; its area is not simply plateau amplitude
  times plateau duration. Use decoded ramp samples and `effective_moment`.
- `m3031_15.pph` defines `NEWSHAPE_MAC` and `NEWSHAPE_SETUP`; the latter sets RF
  board multipliers. Changing library samples alone is insufficient to establish
  a calibrated flip angle.
- `var_20.pph` defines `LONGDELAY` with a 140-us subtraction and reserved
  `temp_mac`/`temp_mac_long` scratch state. It is available but is not an exact
  arbitrary microsecond delay and cannot preserve that scratch state.
- A new list start on an active channel is ignored in the mapper. Finish lists
  physically, including the gradient-lag interpretation, before restarting an
  axis. Matrix calculation must finish before selection and later use.
- The local loader resolves library paths by basename. It proves waveform
  identity locally, not the presence of those files on console drive G:.
- The preprocessor deliberately strips `//` comments before expansion; the
  historical console cpp did not. Mapper success alone cannot detect the
  comment expansion failure. Static scanning must inspect the raw source.

The protocol contains `rfdelay=60 us`, not the PARAMLIST default 6 us. The source
models it as a gradient lag. The nominal RF latency is approximately 3 us; the
actual console RF/gradient/ADC relative timing is not measured here. The current
PPR sets `crusher_max_dac=32767` and `crusher_slew_dac_100us=32767`; these are
source guard values, not independent hardware certificates.

## Static compiler checks added for new sources

`examples/v181_v1911_static_audit.py` accepts either proposed PPL and optionally
`--baseline-source` and `--method-only`. It imports the existing parser without
running old generators or changing old source files. Results are JSON with
explicit limitations. The static checks include resolved goto targets, forward
jump counts, exact historical W007/W008 call/argument/expression identities,
conditional-body node sizes, relative image estimates, new long source literals,
new function-like macro definitions and macro calls in added `//` comments.

| Static metric | v1.8 | v7 ss-MGOT |
|---|---:|---:|
| Forward gotos | 145 | 18 |
| Predicted W007/W008 | 11 | 3 |
| Largest conditional body, AST nodes | 369 | 379 |
| Estimated image, bytes | 56664 | 48469 |
| Undefined jump targets | 0 | 0 |
| Other unreferenced labels | 0 | `pb_end` |

Both baseline audits pass. The v7 warning expressions are inherited
`offset_frequency(fov_slice_freq+slice_freq_var)`,
`IntToLong(slice_freq_var)` and `waittimer(templ1)`. An unreferenced `pb_end` may
produce W003; the tool reports this informationally and does not pretend that
its W007/W008 predictor covers all vendor warnings.

The audit conservatively permits no additional warning identity, a largest
conditional body at most 110% of v18 (405 nodes), at most 40 forward gotos in a
method-only source and 145 in a legacy source. The image estimate uses the
historical `2.6*AST_nodes + arrays + strings` model. Method-only sources retain
at least 4096 model bytes below v18; legacy sources must not exceed the v18
model estimate. These are source budgets and cannot guarantee a 64K target
image because runtime overhead is unknown.

Baseline outputs are `baseline_v18_static.json` and `baseline_v7_static.json`.
Five deliberately unsafe temporary sources independently demonstrated rejection
of an added 49-character literal, a macro call in a new comment, a long timer
argument, excess forward jumps and a huge conditional body. The evidence is
`static_audit_selfcheck.json`. Independent review of this new audit is still
required before relying on it for shipment.

## Safe additive generation strategy

1. Add a separate builder; never run the old generator's `main()` or
   `main_ppr()`, since those overwrite v1.91/v1.92 and historical error tables.
2. Hash-check the immutable v1.8 bytes. For ss-MGOT, import the old builder,
   call its pure-returning build functions, and assert equality with the v7 ZIP
   members before applying any changes. This keeps the source reproducible and
   prevents accidentally starting from workspace combined v6.
3. Transform only exact, unique source anchors. Keep CRLF and Latin-1 output
   compatible with the baseline. Strip comments from added executable regions,
   expand added helper macros in Python and split newly printed literals to
   48 source characters. Preserve the backward exit hub.
4. Produce new v1.81 and v1.911 PPL/PPR files and new diagnostic tables. Update
   each PPR's `:PPL` filename and every changed PARAMLIST/table capacity together.
   Preserve old protocols, libraries and sources. Avoid adding acquisition
   rows or large arrays; any v1.81 size growth needs a compensating reduction
   rather than assuming unused 64K capacity.
5. Reuse the existing vendor gradient primitives and RF files wherever possible.
   Merge concurrent gradient axes with matrices only after pathway/moment,
   rotation, amplitude, slew and nonoverlap proof. A matrix combination is
   technically expressible; its physics and physical-axis limits remain separate
   requirements.
6. Map each exact new PPL/PPR pair under all cost models, record hashes, and then
   run static checks, independent reviews and the full numerical validator.
   Retain the 5-ms timer horizon and 8997-tick post-ADC calculation window.

## Precise uncertainties to ask the user about when triggered

The following must not be silently reclassified as low-priority proposals when
their physics benefit is strong. Ask while continuing independent work.

**Concurrent lobe hardware ceilings.** Combining D/compensation/crushers can
shorten ESP, but source values are not hardware documentation. Ask for known
per-physical-axis maximum amplitude/slew, the calibrated DAC-to-gradient scale
and any vector-sum or simultaneous-axis restriction at the actual orientation.
Recommend preserving existing guards and proving the rotated waveform against
documented limits; if the limits are unavailable, ask whether to hold this
implementation for the planned console check. A new literal hardware limit
must not be guessed.

**Exact RF and gradient-delay semantics.** Is the stored `rfdelay=60 us` an
empirically measured lag for this console, and does RF start latency include the
`rfon`/pulse-start issue time? An isodelay correction is beneficial only with a
defined physical timing convention. Recommend using the repository's existing
lag convention for source proofs, then an RF/gradient/ADC event export or scope
trace for exact physical centering. Ask for any existing trace/specification;
the user has already said a new live console run is unavailable this session.

**Per-shot navigator integration.** `nav_on=1` in the baseline is a separate
shot, not a navigator acquired within each imaging shot. Adding the latter is
potentially valuable, but the vendor acquisition/reordering/host storage and
reconstruction contracts must agree on extra ADCs. Ask whether an existing
vendor sequence or reconstruction supports a per-shot phase navigator and how
it labels/discards that ADC. Recommend reuse of an existing supported contract;
an additional ADC cannot be safely inserted by source timing alone.

**Compiler acceptance after source changes.** Historical limits are empirical.
The v7 archive was last uploaded, but repository history does not contain a
verified successful vendor compile of its exact bytes. Future changes still
need PPLC/Forth compilation, warning inspection, image size and PPR loading on
the console. Do not ask for a live check that the user cannot perform now;
ask for available existing output if a high-benefit implementation depends on
unknown accepted syntax, and otherwise pause that dependent change with its
specific unresolved constraint.
