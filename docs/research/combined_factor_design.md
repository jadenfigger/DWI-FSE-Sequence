# Combined-factor DW-FSE experiment design and prior-state audit

4 October 2026. This appendix records design choices and a bounded reproduction.
The completed investigation report contains the actual executed search and its
decisions; proposed conditions below must not be counted as completed tests.

## Current state and trustworthy controls

The default command-line generator still reads the v1.6 PPR. Its original scanner
sources are retained. The v1.7 PPL is a separate implemented successor, with the
independent-crusher centering and PE0 memory guards already integrated. It also
implements native constant, increasing, decreasing, alternating, increasing with
alternation, and signed custom schedules. Its default PPR has constant crushers;
the separately named increasing PPRs enable experiments. Neither those scanner
sources nor default PPRs need modification for this investigation.

The files in `scanner/patches` target v1.6. They are reviewable proposals relative
to that source, and must not be reapplied to v1.7. A v1.7 experiment already has
centering correction, even with its constant schedule. To isolate timing, use
v1.6 plus explicit simulator controls for all factorial cells. Native v1.7
readback is a useful separate transfer check, including integer rounding.

The older snapshot report calls increasing with alternating polarity a candidate
tested in four conditions. The newer `scanner_v17.md` reports a larger comparison:
48 static finite-RF conditions and 48 water/PDG conditions across four variants,
with excitation phases 0/45/90 degrees, B1 .8/1.0, B0 0/100 Hz and read-axis
requested b=1000. That is additional qualification, but still lacks heldout
diffusion directions, ETLs, broader B1, and reconstructed images.

The required six controls are original; centered constant; increasing without
centering; increasing with centering; alternating constant; and increasing with
alternating polarity. Add centered alternating constant and centered increasing
with alternation to complete the centering × amplitude progression × polarity
2×2×2 factorial. This prevents mistaking the incremental effect of centering for
the effect of the amplitude or sign table.

All symmetric-pair cases use the same signed amplitude, duration and shape for
the two crusher lobes around each RF pulse. The first DWI pulse retains its
special baseline, including the nominal b=0 diffusion-table row. Gradient
diffusion OFF is a separate condition: its first baseline is the ordinary
crusher in the native scanner semantics. It must not be conflated with b=0
with the diffusion module still enabled.

## Exact amplitude families

Multipliers below scale each pulse's own baseline. First entry 1 therefore
preserves the special first-refocusing baseline. For ETL 8 define the increasing
reference U = `[1,1,1.4,1.8,2.2,2.6,3,3.4]`. Its RF2–8 squared multiplier sum is
38.36 and its peak multiplier is 3.4.

| Family | Exact ETL-8 specification | Constraint comparison |
|---|---|---|
| Constant | `[1,1,1,1,1,1,1,1]` | Original amplitude and duration |
| Increasing | U | Reference |
| Decreasing | `[1,3.4,3,2.6,2.2,1.8,1.4,1]` | Same peak and crusher energy as U before DAC rounding |
| Alternating high/low ordering | `[1,1,3.4,1.4,3,1.8,2.6,2.2]` | Permutation of U tail: same peak and crusher energy |
| Two-level high/low | `[1,1,3.4,1,3.4,1,3.4,1]` | Peak matched; energy differs |
| Modulated ramp | first 1; tail `U[k]*(1+0.2*(-1)^k)` | Separate peak- and energy-normalized versions |
| Quadratic | first 1; tail `1+2.4*t*t`, t=`0,1/6,...,1` | Raw form peak matched |
| Geometric | first 1; tail `3.4**t`, t=`0,1/6,...,1` | Raw form peak matched |
| Bounded irregular | `[1,1,1.71,.83,1.37,2.13,1.09,1.91]` | Earlier reproducible irregular control, lower peak/energy |
| Seeded bounded search | first 1; seven tail values within declared bounds, generated from saved seed | Save all rejected candidates and normalization mode |

Apply positive constant polarity or `(-1)^k` independently, where zero-based
k=0 denotes RF1. The first sign remains positive. The first baseline is never
renormalized. For a nonzero raw tail v, a peak-matched version uses
`v * 3.4/max(abs(v))`; an energy-matched version uses
`v * sqrt(38.36/sum(v*v))`. These are distinct comparison arms. Energy matching
alone can increase peak strength; reject values exceeding the declared hardware
envelope and report the actual post-rounding gradient energy. Do not describe a
peak-matched quadratic schedule as energy matched.

For equal ramps and flat durations, gradient energy is proportional to the sum
of squared signed DACs. Permuting ordinary-pulse strengths preserves that energy
and the first-pulse contribution exactly before rounding. It does not preserve
the achieved b tensor: diffusion history depends on timing and signs. Native
DAC rounding can introduce small energy differences, so use measured waveform
integrals to report the actual match tolerance.

For other ETLs, preserve RF1 and interpolate RF2–ETL over the same endpoints
for a bounded-peak family. A fixed +40% per-pulse progression is a different
family whose peak increases with ETL. Label these separately; do not silently
truncate an eight-entry table.

## Staged search and selection

1. **Reproduction and controls.** Recreate selected archived settings, verify
   source hashes, and check every generated/read-back sequence's timing. Use the
   actual upper-middle ADC sample, not the 25-us earlier geometric midpoint.
2. **Schedule screen.** Use ETL8, TE36 ms, ESP16 ms, B1 .8/1.0, B0=0,
   excitation phase 0/90 degrees and requested b0/1000 along read. Screen both
   signs and amplitude families with explicit peak/energy matching. Save all
   per-echo outputs and rank the Pareto tradeoffs, not just L1 suppression.
3. **Interaction qualification.** Complete the centering factorial. Cross the
   selected schedule families with supported RF phase/angle strategies. Include
   ordinary constant crushers for each RF strategy. Full individual and combined
   cells are necessary: a gain in a combined cell alone is not an interaction.
4. **Frozen finalists and heldout validation.** Freeze candidate IDs before
   applying phase22.5/67.5 degrees, B1 .9/1.1, B0 -75/150 Hz, phase/slice-axis
   diffusion and a normalized oblique direction. Include ETL4/6, and T2 .06/.10 s
   with matched relaxation controls if budget permits. A compact stratified
   subset is preferable to accidentally consuming all reserved conditions in
   optimization. Declare executed combinations and omissions explicitly.
5. **Independent checks.** Recheck original, centered increasing and finalist
   on denser static sampling, another seed and smaller RF time step. Close all
   instantaneous-RF pathway sums against independent acquired MRzero signal.
   Validate tractable ETLs exactly before accepting any pruned long-train
   search. Reconstruct a phantom only if a supported acquisition/reconstruction
   model is available; otherwise image improvement remains unverified.

The screen should retain a balanced shortlist with preserved primary signal,
strong low-tail total magnitude, reduced unwanted L1 share, and modest added
diffusion/hardware burden. Use a noninferiority threshold only as an explicitly
declared engineering screen, such as no more than 10% added primary-water loss
relative to the matched baseline, rather than claiming a clinical threshold.
Reject dominance violations: a candidate with lower robust signal and higher
diffusion cost needs a substantial independently validated route-filter benefit.

Report screening and heldout results separately. Equal-weight grid medians are
descriptive summaries; they do not estimate patient SNR or probability of motion.
Include minimum, median, range and paired absolute differences for the
center-of-k-space echo (echo1 in this centric reference) as well as late echoes.

## Interactions and timing-matched duration changes

For scalar response Y and two binary factors A/B, report
`I=Y11-Y10-Y01+Y00` for each matched condition and echo. State whether Y is
primary magnitude, total magnitude, coherent stimulated magnitude, or L1 share.
For complex signal, record real/imaginary interaction components too; its
magnitude interaction is a separate nonlinear summary. When analyzing changes
in RF phase, choose a common receiver convention and separately inspect phase
aligned coherent contributions. An RF phase difference alone is not signal loss.

Crusher duration modifications should keep RF and ADC centers, TE, ESP, TR and
physical train duration fixed where the generator can rebalance the surrounding
delays. Include same-moment redistribution: a trapezoid's moment is
`amplitude*(flat_duration + ramp_duration)` for equal up/down ramps. Scale its
amplitude inversely to this full area, not inversely to flat duration alone.
Recompute peak, slew and gradient energy; the latter is proportional to
`amplitude**2*(flat_duration+2*ramp_duration/3)`. It is impossible to infer the
same b tensor from the same isolated crusher moment. Hardware/timing failures
are rejected experiments and should remain in the rejection log.

Angle-train support in the original generator is a scalar nominal angle only.
Per-echo refocusing angles require an isolated, tested simulation extension.
First-pulse angle preservation is a separate question from first-crusher
preservation. Record pulse-energy integrals rather than labeling lower nominal
angles as scanner SAR reduction: vendor waveform and RF limits are unavailable.

## Metrics and model limits

For every echo save complex total, explicit primary history, coherently summed
stimulated histories (`Z` storage after excitation, excluding `Z0` recovery),
remaining coherent non-primary contribution, relative phases and cancellation.
The unwanted L1 share is the sum of individual coherently grouped non-primary
history magnitudes divided by the sum of all grouped-history magnitudes. It is
neither signal power nor an artifact fraction. Ratios near baseline nulls must
be accompanied by absolute amplitudes.

Finite-duration static Bloch has inferred sinc RF/slice profiles and stationary
spins. Molecular diffusion is absent even when diffusion gradients play.
Instantaneous-RF PDG includes model diffusion with D=.001 mm²/s supplied as
MRzero D=1; D=0 is internally floored to a negligible value. Its current
longitudinal-diffusion convention differs from the transverse `(2*pi)^2`
convention. Water primary-path comparisons and independently calculated primary
b tensors are stronger evidence than physiological claims about the full
stimulated-water fraction. Never equate absolute Bloch and PDG amplitudes.

Save complete per-echo 3×3 primary-path b tensors, trace and tensor differences;
requested b and the scanner's nominal diffusion-module b are separate fields.
The tensor does not describe every unwanted route. Report TE, ESP, TR, peak
gradient, peak slew and full-waveform gradient-energy proxy in logical coordinates.
Oblique physical axes need verified scanner orientation/calibration transforms.

## Bounded archived-result reproduction

`runs/combined_design/reproduce_prior.py` recreates original v1.6 and centered
increasing with alternating polarity v1.7 at B1=.8, B0=0, excitation phase0,
ETL8, requested read b1000, for static PDG, water PDG and one finite-RF static
run each. It uses 10000 stratified spins, seed1, RF step10 us, T1=1.5 s,
T2=.08 s, T2prime=.03 s and 0.2×0.2×1 mm PDG box support. It compares all eight
echoes against `docs/data/scanner_v17_validation.csv`, preserving every prior
artifact. Raw signals and sequence files remain in the isolated run directory.

Acceptance tolerances are 1e-6 absolute complex error for PDG and Bloch,
1e-6 absolute L1-share difference, and 5e-4 relative MRzero closure. Numerical
results and original-source hash comparisons are in
`runs/combined_design/prior_reproduction.json`. This is a targeted reproduction
of existing evidence, not a new robustness grid.

The reproduction passed. Maximum archived-versus-current PDG complex error,
L1-share error and finite-RF complex error were all exactly zero. Independent
MRzero closure had maximum relative error 8.8240644e-5 (0.00883%), below the
5e-4 acceptance tolerance. Generated and fine-raster read-back sequences passed
timing checks. Installed versions were NumPy2.1.0, PyPulseq1.5.0.post1,
MRzeroCore1.1.1 and torch2.14.0.

Both original scanner hashes exactly match the earlier improvement provenance:

| File | SHA256 |
|---|---|
| v1.6 PPL | `c0e551e76234c8113eb2953dcf9c2bc9e427eee18264199e98b3edd2c2abfd0c` |
| v1.6 PPR | `00bd9e78573133e5df09da9fa64cf424bf6e338e05a1872ff916c3c03bc315ee` |
