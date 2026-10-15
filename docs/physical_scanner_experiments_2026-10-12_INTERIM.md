# 2026-10-12 scanner session — interim findings (analysis not finished)

The full report has not been written yet. This note records the numbers measured so far. The scan catalog is complete: [scan_catalog_2026-10-12.md](../experiments/scan_catalog_2026-10-12.md).

**Scripts** (in `docs/data/`):
* `oct12_load.py`: loader. EPI comes from the vendor k-space (`_o.MRD`). Its read axis is reversed relative to the FSE.
* `oct12_rois.py`: whole-brain and PBS ROIs.
* `oct12_roi_analysis.py`: SNR and ADC.
* `oct12_effective_b.py`: effective b for all 22 FSE scans.
* `oct12_figures.py`: figures.
* `oct12_protocol_audit.py`: catalog.

Figures are in `docs/figures/physical_scanner_2026-10-12/`.

**Methods in brief:**
* ROIs are one whole-brain mask per sample, plus free PBS ex vivo (`roi_placement.png`).
* Noise σ is taken from the readout-side background. Ex vivo uses the right side only, because a tube-edge artifact sits on the left.
* SNR = √(mean I² − 2σ²)/σ.
* EPI is a 16-shot interleaved acquisition (8 echoes per shot, 48 s per volume). The FSE takes 34 s per volume at TR 2000.

## Key results so far

**Session**
* ss-MGOT (v1.912) works today. C, O and R show b-dependent signal, which confirms the 10-11 failure was the 2.8-kHz frequency error.
* EPI and FSE register with 0 px phase-encode shift. EPI has about 150 Hz/px along PE, so B0 offset and inhomogeneity across the brain are under about 50–75 Hz.

**SNR, b10/b0, centre slice**

| | v1.83 | v1.912 | EPI |
|---|---|---|---|
| Ex-vivo PBS | Q 118 | R 38 / O 44 | 111 |
| Ex-vivo brain | Q 62, M 68 | R 17 / O 21 | 56 |
| In-vivo brain | iA 47 | iB 12 | 57 |

* **Efficiency** (SNR/√s/µL), in-vivo brain: v1.83 107, EPI 72, v1.912 27.
* **Bandwidth:** A (20 kHz) / B (40 kHz) = 1.32–1.39, close to √2.
* **Multi-slice MT:** brain b10 SNR falls from 68 (1 slice) to 62 (3 slices) and 51 (7 slices). PBS is unaffected.

**ADC**
* **Ex-vivo PBS** (effective b): 1.77–1.84 along x/y and 1.87–1.91 along z. z stays about +4% high even after the model correction. Off-centre slices out to ±5.2 mm sit within ±3–5% of the centre slice, so there is no 10-11-style bias.
* **Ex-vivo brain, high b:** the b1000→b3000 ADC is identical in Q, Q1 and R (0.233, 0.233, 0.240). v1.83 and v1.912 agree.
* **Ex-vivo brain, low b:** the b10→b1000 ADC rises with slice count / RF burden (single slice 0.30, Q 0.32, R and Q1 0.35–0.36). This fits MT up-weighting the free-fluid fraction at b10. It is not temperature, because the high-b ADC does not change.
* **In vivo, low b:** MD is 0.70 for v1.83 and 0.69 for v1.912. EPI reads 0.77, because its b0 reference includes perfusion/CSF and it uses a 2-mm slice.
* **In vivo, b1000→b3000:** FSE 0.51 vs EPI 0.48, within 5%.
* **FSE in-vivo y bias:** FSE reads y (phase encode) about 20% high at b3000 (0.565 vs 0.465 along x). EPI does not. The likely cause is motion phase; this is unconfirmed.

**ss-MGOT left-right asymmetry in vivo** (`ssmgot_lr.png`)
* The iB/iA ratio is about 0.5 at the dorsal-left surface, which is the theoretical ½ from the magnitude stabilizer. It falls to about 0.05 at 8 mm depth.
* The left side is brighter at equal v1.83 intensity, and the phase difference between iB and iA is flat.
* Conclusion: transmit-B1 (B1⁺) sensitivity of ss-MGOT under the surface coil. The 9.4-T B1⁺ skew runs opposite to the receive (B1⁻) skew: v1.83 L/R is 0.82 and ss-MGOT L/R is 1.55–1.7.
* B0 is ruled out (bound above).
* ss-MGOT is unusable deeper than about 3 mm with this coil.

**Fat in in-vivo v1.83**
* The bright arc and spot over the skull keep 55% of their signal at b6000 (apparent ADC about 0.1).
* They are absent in the CHESS-on EPI and in ss-MGOT. ss-MGOT's low-bandwidth prep slab misses fat at −1.4 kHz.
* Enable CHESS for in-vivo FSE.

**ETL 16 vs ETL 8** (iF vs iE, `etl16_vs_etl8.png`)
* Time per volume is 27 s vs 51 s.
* b10 SNR is 22% lower, with the largest loss near the coil (0.69), consistent with MT. SNR efficiency is about +8%.
* The phase-encode PSF FWHM is 0.58 vs 0.44 mm (+31%) when computed from the measured echo train.

**Other**
* **v1.83 nav-mode-2 (N):** reconstructs as scrambled data. Its raw layout does not match `split_mode2`. R (v1.912 nav 2) reconstructs fine.
* **Off-centre banding:** off-centre v1.83 slices (D, Q, QQ, MM) still show horizontal banding at b10.

## Not yet done
* **Frequency check and off-centre phase calibration:** A/B, and D/E/F/G mode and phcal.
* **N raw layout:** diagnosis and fix.
* **Per-shot navigator benefit (R) and ghosting metrics:** M vs O, and in-vivo by direction.
* **Per-echo (k-space) ADC from the navigators.**
* **B1 sensitivity simulation** for the ss-MGOT explanation.
* **The final report and slide deck.**
