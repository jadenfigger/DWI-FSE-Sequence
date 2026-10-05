# v1.7 timer and diffusion review — 4 October 2026

The scanner source remains **twoTE-1.7**. Three `gpt-6-luna` agents reviewed
timing, diffusion, and matrix/memory behavior against the bundled
[EVO manual](../scanner/EVO%20Pulse%20Sequence%20Program%20Manual.pdf), with a
second review of the edits. The v1.6 baseline, RF waveforms/angles/phases,
receiver phases, and experimental protocol files are preserved.

## Corrections

1. **Imaging RF spacing increased by 5 ms.** The user measured this in the
   vendor simulator. After `ret=gettimer()+250`, v1.6/v1.7 selected a balance,
   added long values, converted crusher pads, and performed a long multiply
   before `waittimer(ret-25)`. This was a marginal 25-us deadline. The manual
   says missed deadlines add complete 5-ms intervals (pp.90–91); long multiply
   alone costs 9 us (pp.118–121). Both complete tick targets are now computed
   inside the existing 3-ms matrix setup and selected **before** `gettimer()`.
   The short window retains only a subtraction, the original ret adjustment,
   and the wait. The absolute balance and the existing delay32 branch pattern
   remain unchanged, including the last-echo path. No TE/ESP extension is used.
   Source expression cost is 54 ticks; with a 30-tick dispatch allowance the
   estimate is 8.4 us inside 25 us. This estimate is not compiled timing.

2. **Diffusion scaling could wrap before its ceiling check.** DAC 20000 at
   200% yields 40000, which cannot fit a signed scanner `int`. The subsequent
   positive-only 30000 check could miss the negative wrapped result. All rows
   now receive a long-product preflight before narrowing, with the scale
   snapshotted for the run. Runtime retains the fast `scale()` operation;
   no long division is added to its timed acquisition-row setup.

3. **The b=0 DAC-1 workaround failed for oblique rows.** `scale(1,577,1000)`
   truncates to zero on all three axes. When b-value mode would produce an
   all-zero vector from a positive DAC, runtime assigns signed DAC 1 to the
   largest direction component. Ties prefer read, then phase, then slice.
   Original table directions remain available for reporting. Normal nonzero
   diffusion gradients and legacy explicitly zero DAC rows retain their values.

4. **Long refocusing waits could narrow outside the timer range.** Both pulse
   types' pre/post targets are checked in long arithmetic before acquisition.
   Targets outside 50..65500 ticks fail explicitly; long crusher settings are
   not wrapped or silently shortened. The 65500 limit follows the manual's
   6.5500-ms argument limit, including its documented unsigned bit patterns.

5. **Setup's achieved nominal b report ignored direction quantization/norm.**
   It now uses the actual integer direction components, matching the runtime
   diffusion-module report. The existing scalar DAC search and calibration
   kernel, including its units and 6.3² convention, are preserved. Accepted
   direction norms still span 0.95..1.05, so requested nominal b can differ
   from the played module b; the existing >5% warning now sees that difference.
   Neither value includes imaging/crusher contributions or their cross-terms.
   Full waveform tensors remain the appropriate offline calculation.

The user’s 30000-tick matrix setup and 24500-tick ceiling are retained. Its
1150-us increase over the old setup is included in minimum TR and the offline
absolute shot-start model. New post-ADC precomputations are included in this
measured setup budget, rather than added outside it. New diagnostic strings
are short. No new table or matrix storage is allocated.

## Validation and remaining checks

`python -m unittest discover -s tests -v` passes **39 tests**, including eight
new regressions. They cover deadline source structure and balance algebra,
ETL 1/2/8/1024 and final-echo selection, timer range boundaries, DAC overflow,
signed oblique b=0 fallback, quantized b reporting, model RF/ADC centres,
crusher schedules/pairing/reset, PE0 corruption/bounds, waveform readback and
full-waveform tensors. The unchanged v1.6 event hash passes.

`python examples/review_scanner_v17.py` exports
[compact results](data/scanner_v17_timing_review.json): six source/model cases
using the baseline and test3 protocol with constant, increasing, and
increasing-plus-alternating crushers. They include b=0 workaround rows and
nonzero b-weighted test3 rows,
pass Pulseq timing, predict 14-ms imaging RF spacing, and zero geometric ADC
midpoint residual. These are waveform-model checks; that model does not
execute scanner instructions and cannot reproduce a missed timer deadline.
The original complex-signal/pathway investigation results remain historical
artifacts; they are not claimed as a new vendor execution test.

The reviews found no further confirmed defects in the inspected crusher
matrix pairing/lifetime, reset counters, or PE scratch guards. PE order 0
remains unavailable for DWI. A remaining platform uncertainty is the PLATO
`CREATE_MATRIX` branch: it ignores native return status, while the non-PLATO
wrapper checks it. The manual's API prose and example disagree about matrix
return types; the lowercase PLATO intrinsic needs vendor verification before
changing that include. It has not been rewritten speculatively.

No local vendor compiler or scanner instruction simulator was available.
Recompile this edited PPL and rerun the vendor simulator. Check successive
imaging RF centres (RF 2 onward) equal ESP; for ADC 2 through the penultimate
echo check its geometric centre equals the midpoint of adjacent RF centres.
The first diffusion RF interval has the separate two-TE budget and should not
be judged by that imaging-only midpoint rule. With even sample counts, the
upper-middle sample is half a dwell later than the geometric window centre.
Also record the new `crusher_setup_ticks` and verify it stays at or below
24500 for the actual protocol. Instruction timing, optional scanner modes,
matrix settling, physical gradient delay (previously assumed 60 us), and
phantom/image behavior still require scanner verification.
