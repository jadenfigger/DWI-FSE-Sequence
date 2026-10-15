# v1.82 and ss-MGOT v1.912: practical summary

**Status:** Source-model candidates. Neither version has been vendor-compiled or scanner-verified. Console timing, played gradient limits, RF performance, slice crosstalk and motion benefit remain to be measured on hardware. See [SCANNER_TEST_PLAN.md](SCANNER_TEST_PLAN.md).

## What changed

v1.82 builds on v1.81. It adds phase accounting for frequency-offset slices and a per-shot navigator mode. The modeled RF centre phase relative to the first RF of each shot differs from the centred slice by at most 0.207° through ±5 mm across eight instruction-cost models; train echo midpoint error is at most 15.8 µs. The modeled image is 56,590 of 56,664 bytes, leaving 74 bytes. Because the v1.8x program image budget is tight, 3D and driven equilibrium are explicitly rejected. CHESS remains available. The v1.81 b-value generation and crusher behavior are retained. The minimum readout duration remains about 1.9 ms.

v1.912 builds on ss-MGOT v1.911. It adds multi-slice/off-centre support, RF phase handling, a spacing check, dwell-dependent minimum echo spacing and per-shot navigators. It preserves the fused slice-gradient areas at each RF and ADC boundary. The event model checks RF centre phase through ±5 mm across eight instruction-cost models, with a maximum centre-relative error of 1.298° and echo midpoint error of 9.25 µs. Its modeled program image is 52,542 of 52,568 bytes, leaving 26 bytes. Oblique orientations remain unsupported. The fused geometry (`tramp=200 us`, `tdp=700 us`, `tcrush=1000 us`, `rfdelay=60 us`, imaging selector 1320 us) and the `crush_amp` rounding lattice remain constrained.

## Navigators and raw views

`nav_on` has three values in both new protocols:

| Value | Meaning |
|---:|---|
| 0 | No navigator; inherited raw layout. |
| 1 | Existing per-volume navigator train; inherited layout. |
| 2 | Per-shot navigator echo, in addition to the per-volume navigator train. |

For mode 2, `NO_VIEWS` in the embedded protocol is the **total raw-line count**, and `VIEWS_PER_SEGMENT` is the **shot length, ETL+1** (updated 2026-10-12). The console rejects a protocol whose `NO_VIEWS` is not a multiple of `VIEWS_PER_SEGMENT` ("views per segment should be a divisor of Views1"), so 153 raw lines need `VIEWS_PER_SEGMENT` = 9. The PPL subtracts 1 to get the imaging ETL, and reconstruction does the same. With `N` imaging lines and ETL `E`, the protocol has `N/E` imaging shots. Each shot has `E` imaging echoes plus one unencoded navigator echo; the per-volume navigator contributes one more `E+1` train. Therefore:

`NO_VIEWS = (ETL + 1) × (1 + N / ETL)`

For example, 128 imaging lines and ETL 8 require `NO_VIEWS = 153`. Use the MRD-embedded protocol to determine the layout. Modes 0 and 1 keep their existing raw counts (136 for 128 imaging lines at ETL 8 with the current per-volume navigator). Mode 2 needs at least two total raw shots: the per-volume navigator train and at least one imaging shot. Unsupported values or inconsistent mode-2 raw counts are rejected.

The added navigator echo follows the imaging echo train, keeping centric k-space's centre at echo 1. Its phase-encode moment is zero at the echo centre, including after the last image echo in the shot. Both sequences use a matched phase-encode rewinder and secondary-matrix polarity rule for the appended echo. Mode 2 costs one extra ESP per shot and raises the minimum TR. Reconstruction uses the embedded `nav_on` and view-count fields; it does not infer layout from a filename. Mode-2 reconstruction estimates constant and linear readout phase relative to a high-quality reference shot. It uses the correction only when navigator SNR is at least 3 and projection coherence is at least 0.65; noise-dominated shots fall back to no correction. These gates need an acquired scan before they can be considered scanner-validated.

## Effective b output

Nominal `.bval` and `.bvec` remain for compatibility. Reconstruction also writes `<stem>_beff.bval` and `<stem>_bmatrix.txt`, plus JSON fields for effective b, the b-matrix, the echo convention, source and warnings. The b-matrix uses logical axes x=read, y=phase and z=slice; each off-diagonal column is the matrix entry itself, without a factor of two. The effective b-matrix is model-derived from the embedded protocol and resolved sequence source. It can fall back to nominal values with a warning if the source or model is unavailable. An optional per-version calibration may correct the known scanner axis discrepancy; the output records whether calibration was applied. The source model is not a measured waveform, and the scanner calibration remains unverified until measured.

The b-value search still chooses diffusion gradient amplitude from the nominal request. The effective-b output reports the full modeled gradient history; it does not alter the sequence's DAC selection.

The archived Oct 10 A/C/B/D/E data reconstructed with the new code retained bit-identical mode-1 k-space and image arrays. The effective-b echo-1 fits from nav echoes 2–8 were A/v1.81 1.8535, C/v1.8 1.8550, B/v1.911 1.8450 and D/v1.91 1.8608 ×10⁻³ mm²/s (0.86% full spread). The b-trace reproduction error was at most 0.0016 s/mm². These are retrospective model checks; the known z-axis discrepancy still needs scanner calibration.

## Limits to keep in mind

- v1.82 rejects 3D readout and driven equilibrium. CHESS remains available. Other v1.81 restrictions continue to apply, including flow compensation being off for DWI.
- v1.82 keeps the inherited dwell-derived ESP calculation. Its readout must remain at least about 1.9 ms; with 128 samples, very short dwell choices can make the readout timing invalid even when ESP is long enough.
- v1.912 allows standard-orientation multi-slice imaging only when slice offsets meet the computed minimum separation. The slab and tip-up widths remain as shipped; no oblique orientation support is added.
- v1.912 computes a minimum ESP from the active timing layout. Set ESP at or above the console-reported minimum for the chosen dwell, readout and mode. There is no fixed 13-ms requirement when the timing permits a shorter value.
- For `nav_on=2`, the raw-view count must match the `(ETL+1) × (1+N/ETL)` contract; it must include the per-volume train and at least one imaging shot.
- The v1.81 b=0 echo-1 defect is outside this change. Follow the small nonzero reference-b workaround for v1.82 until separately resolved.

## Source-model timing reference

The predictions below are from the source model, not scanner timing measurements. The centred single-slice minimum TR boundaries and their one-ms-below rejection are confirmed in [single_slice_tr_recheck.json](validation/single_slice_tr_recheck.json). The final combined event checks and targeted identity recheck pass with stable scanner inputs; see [REPORT.md](REPORT.md) for the recorded gate correction.

| Readout dwell | v1.82 minimum ESP | v1.82 minimum TR | v1.912 minimum ESP | v1.912 minimum TR |
|---:|---:|---:|---:|---:|
| 50 us | 14 ms | 174 ms | 13 ms | 193 ms |
| 25 us | 11 ms | 151 ms | 10 ms | 167 ms |
| 20 us | 11 ms | 151 ms | 10 ms | 167 ms |
| 16 us | 10 ms | 144 ms | 10 ms | 166 ms |

This reference is for a centred slice with `nav_on=0`; timings are source-model predictions, not scanner measurements. For `nav_on=2`, the v1.82 minimum TRs are 188/162/162/154 ms and the v1.912 minimum TRs are 206/177/177/176 ms at dwell 50/25/20/16 µs. Off-centre v1.912 slice-frequency setup also increases the TR floor by about 2.7 ms in the current model. Slice spacing must satisfy `thickness × ((max(slab, tip-up)/1000 + 1)/2 + 0.75)`, rounded up to console units. The 0.75-thickness margin is above the largest measured 5% pulse-transition width (0.69 mm for prep90), but it is not a guarantee of 1% slice-profile isolation. For the default 1-mm slice and 3000‰ slab, the spacing guard reports **1103 units = 2.7575 mm** at 400 units/mm. The formula also supports a future narrower slab study (for example 1.5×), but that RF change is outside this build and requires a separate slice-profile validation.
