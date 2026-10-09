# Independent validation review

Reviewer: independent validation agent, 2026-10-08. This review inspects the
validator implementation and source-model assumptions independently of the
sequence authors. It does not certify scanner behavior. Final PPL byte review
is pending until the candidate files are complete.

## Findings requiring action or explicitly limited claims

1. **The numerical validator currently reports rather than enforces most
   acceptance criteria.** `examples/validate_v181_v1911.py` has no assertion or
   nonzero exit for timer overruns, ignored lists, matrix hazards, nonconstant
   timing, Bloch regressions, or unsafe protocol rejection. Its summary records
   only the rejection Boolean. A successful process exit is therefore not a
   validation pass. Inspect all JSON outputs and implement a separate explicit
   acceptance decision before packaging. Baseline hazards should remain visible
   without failing candidates simply because historical controls are unsafe.
2. **The method read-moment diagnostic uses the wrong coherence model.**
   `timing()` passes every RF after excitation to `effective_moment`, including
   ss-MGOT tip-up and re-excitation 90-degree pulses. A 90-degree transfer is not
   an unconditional transverse conjugation. Use the same explicit carrier and
   conjugate branch definitions and frozen longitudinal interval as the
   per-echo tensor routine, or omit this diagnostic for the method. The existing
   per-echo tensor routine correctly labels its scope as selected branches,
   rather than every stimulated path.
3. **The timing report cannot establish selective RF isodelay or echo centering.**
   Its references are decoded sample-envelope midpoints, which its own output
   honestly acknowledges. It reports geometric RF spacing and an RF-midpoint
   residual, but no echo-window peak sweep or finite-RF phase derivative.
   A claimed correction of the approximately 95-us offset requires independent
   finite-RF evidence; otherwise retain it as unresolved scanner verification.
4. **RF latency is assumed rather than swept.** `mapping()` exposes a latency
   argument, but `main()` uses 3 us for every run. Add bounded sensitivity cases
   if claiming robustness to the approximately known pipeline delay. Gradient
   lag is applied once in exported gradient times, once through shifted moment
   integration coordinates, or once through the Bloch configuration; it is not
   currently double counted in those paths.
5. **ADC export conflates retained-sample support and console busy time.**
   `event_rows()` uses `t_complete` as ADC end. In the mapper this is completion
   return after digital-filter flush, not the last retained sample. For RF/ADC
   overlap and echo centering, report retained support independently using
   `t_init + discard * sample_period` through the sample-count duration. Preserve
   busy/flush end as a separate timing field. The even-sample convention uses
   index `n/2` as k-space center, not mean of the first/last sample coordinates;
   make that convention explicit before interpreting a 25-us difference at
   50-us dwell as a timing error.
6. **Two mapped shots do not provide two timing ledgers.** Global interpreter
   flags and matrix-use issues span both mapped shots, but `build_ledger(test)`
   defaults to shot 1. Timing, gradients/RF overlap and per-shot spacing must
   also inspect `build_ledger(test, 2)`. The first protocol and diffusion row
   alone cannot verify every supported crusher schedule or diffusion direction.
7. **Logical hardware demand is not physical hardware qualification.**
   `hardware_demands()` correctly states that its values are logical-only.
   The mapper flags patient/scan obliquity but does not rotate those waveforms.
   A merged candidate must separately prove summed primary/secondary values,
   the actual supported orientation envelope and inherited amplitude/ramp
   margins. Full-scale PPR guard values are not rated amplifier limits. The
   user lacks additional hardware documentation; this limitation must remain
   explicit rather than be converted into a fabricated rated limit.
8. **Bloch comparisons need interpretation, not a bare minimum difference.**
   The full new grid covers B1 0.8/0.9/1.0/1.1, B0 +/-128/0 Hz and phases
   0/45/90 degrees. Quick mode omits off-resonance and B1 0.9, and cannot fulfill
   the task's final acceptance grid. Comparisons presently omit relaxation and
   diffusion; neither T2 benefit nor stimulated-path diffusion improvement can
   follow from these output files alone. The reported minimum is an absolute
   signal change; preserve before/after amplitudes, per-case effects and intended
   tradeoffs rather than imposing an arbitrary relative error on weak echoes.

## Static compiler audit

The new audit has appropriate bounded scope: its output explicitly excludes
PPLC, Forth, fixed runtime overhead and physical include versions. Its warning
signature comparison and image/branch estimates follow historical predictors.
The historical warning evidence explicitly documents `scale` accepting a long
first argument despite the local prototype; this exception should not be
removed merely from reading that prototype.

The five recorded mutation checks exercise useful failure branches. There is
no independent numerical evidence that 405 AST nodes guarantees a Forth branch
range, or that the relative image estimate guarantees 64K. Consequently final
packaging may claim these source budgets pass, never that compilation succeeds.
The generic array estimate uses two bytes per element regardless of declared
type and only constant numeric dimensions. Current candidate declarations need
inspection for added long arrays before relying on that estimate. W003 and
other vendor warning classes remain outside the predictor; the warning-count
requirement is therefore scanner-verify even if all predicted W007/W008 match.

## Pending final review

Review hashes, source changes, matching PPR settings, exact regeneration and
independent all-cost/all-shot numerical checks after final candidates arrive.
No candidate is approved by this document yet.
