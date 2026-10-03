# dwfse_minimal.seq — what the KomaMRI result shows

**Protocol (repo PPR):** ETL 2, 2 shots (PE lines −1, −2 then 0, +1), 1 slice, b = 0 (lobes at DAC 1), TE 36 ms, ESP 16 ms, TR 2 s, no dummies. Generator defaults: 60 µs gradient lag, 180 centring as written, 180° refocusing, placeholder sinc RF (TBW 4). Voxel: T1 1.5 s, T2 80 ms, T2′ 30 ms, z ± 1 mm.

| echo | time | KomaMRI | `bloch_sim.py` (check) | what sets it |
|---|---|---|---|---|
| TR1 echo 1 | 36 ms | 0.253 | 0.247 | T2 (0.64) × slice profile |
| TR1 echo 2 | 52 ms | 0.193 | 0.192 | ratio 0.78 vs T2-only 0.82: no stimulated echo |
| TR2 echo 1 | 2.036 s | 0.183 | 0.178 | ratio 0.72 = T1 recovery 1−e^(−1.94/1.5) |
| TR2 echo 2 | 2.052 s | 0.137 | 0.136 | as above |

An independent numpy Bloch simulator (`bloch_sim.py`, same voxel model) agrees with KomaMRI within Monte-Carlo noise. Changing the random seed alone moves KomaMRI-style 20k-spin results by 1–5%. So the KomaMRI run is behaving correctly.

![analysis](minimal_analysis.png)

## Findings

1. **Signal level is set by the slice profiles, and those come from the placeholder RF.** The placeholder excites a 1.41 mm slice (FWHM), not 1 mm. Its nominal BW is 3 kHz, but the PPL sets the gradient for 2.13 kHz (71 %, PPL:1327). Its refocusing profile is only 0.83 mm wide (right panel), so slice edges are excited but not refocused. Your block-3 snapshot shows the un-apodised sinc's Gibbs overshoot: Mz ≈ −0.3 at ±0.4 mm, i.e. about 107° there. The B1 curves peak near B1 ≈ 0.85 for the same reason. **Every B1-sensitivity number depends on the real `3lobe_sinc_3kHz` shape.** A Hanning-apodised placeholder (variant E) already changes echo2/echo1 from 0.78 to 0.69.
2. **TR2 is 72 % of TR1 because of T1 saturation, not an artefact.** With TR 2 s and T1 1.5 s, Mz has only recovered to about 0.73. The full protocol's 4 dummy TRs (`no_disacq`) put every acquired TR at steady state. For T2 analysis, compare echoes within one TR.
3. **Echo 2 is 5 % below pure T2 decay because the first interval breaks CPMG.** A non-ideal 180 creates a stimulated echo (transverse during 90→180₁, stored as Mz, recalled by 180₂). It only lands on echo 2 if TE/2 = ESP/2 and the crusher moments match. Here TE/2 = 18 ms ≠ ESP/2 = 8 ms, and the first crushers are 2754 vs 5482 DAC, so it is lost. Variant D (TE = ESP = 36 ms, equal crushers) puts it back: echo2/echo1 = 0.84 against T2-only 0.64, a +32 % stimulated contribution. That is the "non-CPMG" in the sequence name. Echoes generated *inside* the train (2…N) still satisfy CPMG among themselves. ETL 2 cannot show that; ETL ≥ 4 will.
4. **The DW-FSE timing makes echo 2 far more B1-sensitive** (middle panel). Over B1 0.7–1.2, echo 2 varies 2.5× in A against 1.6× in D, while echo 1 behaves the same in both.
5. **The gradient-lag and 180-centring switches matter little here.** Variants B and C change any echo by at most 3 %.
6. **b = 0 hides the real DW-FSE problem.** With b > 0, motion during the lobes adds a random phase, so the magnetization is no longer along the CPMG axis. A static KomaMRI phantom never shows this. `examples/ex6b` mimics it with a 90° excitation phase: at B1 0.8, echoes 3–4 collapse from 0.41 → 0.09.

## Next steps

- Get the RF frame, or tune the placeholder until its excitation FWHM is 1 mm (2130 Hz). Then redo the B1 sweeps.
- Simulate ETL ≥ 4 with dummies on, and add a phase-error or motion case for b > 0.
- Reproduce: `python analysis/analyze_minimal.py` (about 1 min; writes the figure and `minimal_results.json`).
