# October 5 crusher area audit

The reproducible calculation is in [oct05_crusher_area.py](oct05_crusher_area.py). It reads the protocol section appended to each acquisition MRD, since that is the saved acquisition-time record. It writes [per-echo areas](oct05_crusher_echo_areas.csv), [train totals](oct05_crusher_train_areas.csv), [JSON provenance and summary](oct05_crusher_area.json), and three figures in `docs/figures/physical_scanner_2026-10-05/`.

## Model and limits

Each Oct. 5 v1.8 MRD points to `FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl`, which is not present in this checkout. The only checked-in implementation with independent signed crusher schedules is [v1.7](../../scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.7.ppl). The table therefore emulates its schedule logic; every v1.8 area and comparison is conditional on v1.8 retaining that behavior. The embedded v1.3 `testa` is excluded because it has coupled crushers and no usable independent signed crusher table.

The v1.7 source and [m3040_15.pph](../../scanner/m3040_15.pph) show that each independent 180-degree block is a secondary crusher trapezoid, the primary slice-selection plateau, then a second secondary crusher trapezoid. `POSPULSE_SEC(flat, clock)` emits ramp-up, flat delay and ramp-down aliases. For an ideal linear ramp of duration `r` on both sides and flat duration `f`, a signed crusher DAC value `C` gives the per-lobe area

```text
Q = C × (f + r)  DAC·µs
```

The two commanded lobes around one RF have the same sign and equal area, so their commanded sum is `2Q`; their absolute sum is `2|Q|`. In the ideal intended primary transverse pathway, the 180-degree pulse reverses the effective sign between the lobes, making the RF-sign-weighted within-pair sum zero. That cancellation assumes exact RF refocusing and equal played lobes; it does not assert cancellation for other coherence pathways.

The schedule emulator follows the v1.7 integer rules: first-DWI versus train baselines; additive percentage progression; alternation on even-numbered pulses; custom signed percentages; positive-magnitude half-up rounding `(abs(base)*abs(percent)+50)//100`; then sign application. Crusher flat durations and ramp durations come from the embedded PPR. The area formula includes one ramp duration, not two: the two ramps each have half the area of a full-amplitude flat of duration `r`.

The saved `tramp` is 200 µs; the ordinary crusher flat is 1000 µs. Consequently, equal-amplitude ordinary crusher areas are 20% larger than a flat-only rectangle. For example, a 5482-DAC lobe is 6,578,400 DAC·µs, and a 2741-DAC lobe is 3,289,200 DAC·µs. The 2-ms crusher scans use 2,200 µs of equivalent full-amplitude area per lobe. Test4b has a 2-ms first crusher and 1-ms train crushers.

The PPR amplitude and slew ceilings are both 32767, the v1.7 software defaults. The largest modeled scheduled DAC magnitude is 19,863 (test4b); at the stored 200-µs ramp its requested slope is about 9,932 DAC per 100 µs. Thus no modeled value reaches the configured software ceilings, and the v1.7 preflight would accept those nominal checks. The source labels these as calibrated logical-DAC ceilings that require hardware qualification. No physical clipping or slew headroom can be established without the scanner ratings and actual gradient readback. No schedule-value truncation occurs beyond the specified integer half-up rounding; actual ramp raster samples are unavailable.

Nominal physical conversion is possible under the PPR calibration convention. The embedded `grad_var[0]` is 25,447 Hz/mm at full DAC. Using the proton gyromagnetic ratio `42.57747892 MHz/T`, the nominal logical S full-scale field is `25447 × 1000 / 42.57747892e6 = 0.598 T/m`. The CSV's optional nominal moment uses

```text
area(T·s/m) = area(DAC·µs) × grad_var[0]/32767 × 10⁻³ / gamma(Hz/T)
```

This is defensible as a conversion of the stored nominal calibration convention, not as a measured physical crusher moment. `S` is a logical slice axis; its physical coil mixture depends on orientation and axis calibration. The sequence's referenced gradient shape library (`g3040_15.seq`) is not included, and no amplifier waveform, gradient lag, or independent field calibration is available. Treat DAC·µs as the primary result.

The crusher-area tables alone do not provide effective b-values. An ideal primary-pathway b tensor could be calculated from a fully specified v1.7 event waveform, RF centers, and diffusion waveform. The actual Oct. 5 v1.8 effective b is blocked by the absent v1.8 PPL, absent gradient shape library, and absent physical waveform/calibration response. The embedded nominal requested b-values remain protocol targets, not effective-b measurements.

## Area-matched comparisons and confounds

- **test1 versus test1e:** the signed lobe areas are exact sign reversals pulse by pulse; absolute areas, durations, schedule, and PE order match. The first/train baselines change from `+5482/+2741` to `−5482/−2741` DAC. This is the cleanest constant-schedule polarity pair.
- **test2 versus test2b:** again exact signed reversals pulse by pulse with identical absolute areas, durations, schedule and PE order. **test2b, test2c and test2d** also have identical crusher waveforms/areas; only their PE ordering differs (1, 6, 7).
- **test2 versus test3:** per-pulse absolute areas match exactly. Test3 changes the signs of even-numbered crusher pairs while retaining RF1's sign. **test3 versus test3b** are exact whole-train sign reversals with matching absolute areas.
- **test6 versus test7:** custom schedules have identical absolute DAC amplitudes and per-pulse absolute areas. Test7 reverses the signs of pulses 2, 4, 6, and 8 while pulses 1, 3, 5, and 7 retain test6's signs.
- **test2 versus test5:** the lobe-area magnitudes form the same multiset, but the train order is reversed after RF1 and every sign is reversed. This is a temporal-order plus polarity comparison, not a pure sign comparison.
- **test1b versus test1c:** exact signed polarity reversal and matched 2-ms duration, with identical per-pulse absolute areas. Their lobe-area magnitudes are 6,030,200 DAC·µs for RF1 and 6,030,200 DAC·µs for each train RF.
- **test1b/test1c RF1 versus test1/test1e RF1:** their first-lobe absolute areas are close but not equal: 6,030,200 versus 6,578,400 DAC·µs (−8.33%). The longer crusher duration makes RF2–RF8 6,030,200 versus 3,289,200 DAC·µs (1.833×), so whole-train areas are not matched.
- **test4/test4b:** not area matched. Test4b changes the baseline magnitudes (`−5482` to `−5842`) and doubles the first crusher flat from 1 ms to 2 ms; its largest scheduled amplitude is 19,863 versus 18,639 DAC in test4.

The reported areas help separate total commanded moment from polarity and echo placement. They do not rank image quality by themselves: even equal absolute areas can produce different pathway behavior when signs or train order change, and the parent analysis' image/raw-signal comparisons remain necessary.
