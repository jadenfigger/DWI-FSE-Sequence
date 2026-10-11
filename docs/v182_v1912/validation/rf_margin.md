# RF spatial transition margin

The three local WavEd frames match the quantized RF contract exactly after
decoding: 320 signed samples per frame at 100 ticks (10 us) per sample. The
profile calculation uses those contract samples and the nominal normalized RF
amplitudes. It evaluates one independent one-dimensional Bloch profile per
pulse at 6,001 positions across +/-10 mm of the adapted coordinate. The sixfold
gradient adaptation changes the nominal 18 mm prep widths to 3 mm and the 10 mm
tip width to 1.667 mm for the 1 mm slice protocol.

| Frame | Response measure | 5% margin beyond nominal edge | 1% margin |
|---|---|---:|---:|
| `v19_slrprep90` | Initial Mz to transverse magnitude | 0.690 mm | 2.627 mm |
| `v19_slrprep180` | Initial Mz inversion fraction, `|1-Rzz|/2` | 0.327 mm | 0.517 mm |
| `v19_slrtip90` | Transverse-to-Mz conjugate transfer magnitude | 0.450 mm | 1.187 mm |

The selected spacing margin is **0.75 mm (0.75 slice thickness)**. It rounds up
the largest measured 5% transition, 0.690 mm. This is a 5% response criterion,
not a 1% side-lobe guarantee; prep90 needs 2.627 mm for the persistent 1%
criterion. The metric for prep180 uses longitudinal inversion so off-resonance
precession about z does not count as pulse response. Both sides of every profile
were checked; the results are symmetric to the sampling precision.

The local frame sample hashes and the quantized CSV sample hashes are recorded
in [rf_margin.json](rf_margin.json). The decoder matched every frame's signed
DAC samples to the quantized contract exactly. Reproduce the report with
`python examples/v182_v1912_rf_margin.py`.

This estimates per-pulse spatial selectivity from research samples. It does not
verify vendor loading, PPL gating, physical RF/gradient calibration, scanner
playback, or cross-talk through the complete preparation and imaging pathway.
