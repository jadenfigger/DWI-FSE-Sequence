# October 12 quantitative comparison audit

This audit checks the existing centre-slice signal table, its SNR and ADC calculations, the EPI/FSE sampling grids, and the effective-b denominators. The legacy signal and result tables remain unchanged. The reproducible calculations and geometry-aware R rows are in [oct12_quant_audit.py](oct12_quant_audit.py), [oct12_quant_audit.json](oct12_quant_audit.json), and [oct12_quant_audit.csv](oct12_quant_audit.csv).

## SNR and efficiency

The raw SNR calculation is (S/\sigma), where (S=\sqrt{\max(\mathrm{mean}(I^2)-2\sigma^2,0)}) over the ROI and \(\sigma=\sqrt{\mathrm{mean}(I^2)/2}\) in background columns. FSE uses a plain FFT. EPI uses vendor regridded and ghost-corrected `_o.MRD` k-space before a plain FFT. The Rayleigh-background estimate is therefore a common numerical convention, but the two reconstructions can have different noise correlation and processing. The SNR values should be read as within-reconstruction descriptions, not calibrated cross-sequence sensitivity measurements.

The existing EPI loader FFTs 168 native read samples, then linearly resamples magnitude images to 128 columns for the ROI calculation. Its stored voxel volume combines the native read pixel (35/168) mm with the 128-grid phase pixel (35/128) mm, yielding 0.11393 µL for a 2-mm slice. If the 35-mm read FOV is retained through interpolation, the ROI-grid pixel size is (35/128) mm on both in-plane axes, and the corresponding volume is 0.14954 µL. Under that assumption, voxel-normalized EPI efficiency is 0.762 times the stored value. This is an explicit sensitivity correction, not a certified absolute EPI efficiency: the `_o.MRD` crop/FOV mapping and the interpolation-induced noise covariance have not been independently calibrated. The catalog NIfTI uses an interpolated 256 × 128 grid with 0.13672 × 0.27344-mm spacing; that does not make the 168-native and 128-ROI grids interchangeable.

The audited display [snr_summary_audited.png](../figures/physical_scanner_2026-10-12/snr_summary_audited.png) reports measured SNR and SNR/√(volume time) directly. Its voxel-volume panel labels the two EPI conventions, and it shows the geometry-scaled R masks. Representative b10/b0 values are:

| Sample and ROI | Scan | SNR | SNR/√s | SNR/√s/µL |
|---|---|---:|---:|---:|
| Ex-vivo brain | Q v1.83 | 62.43 | 10.71 | 143.21 |
| Ex-vivo brain | R v1.912, scaled ROI | 17.02 | 2.92 | 43.91 |
| Ex-vivo brain | EPI, 168-pixel divisor | 56.12 | 8.10 | 71.10 |
| Ex-vivo brain | EPI, 128-grid divisor | 56.12 | 8.10 | 54.17 |
| In-vivo whole brain | iA v1.83 | 46.80 | 8.03 | 107.35 |
| In-vivo whole brain | iB v1.912 | 11.88 | 2.04 | 27.24 |
| In-vivo whole brain | EPI, 168-pixel divisor | 56.78 | 8.20 | 71.93 |
| In-vivo whole brain | EPI, 128-grid divisor | 56.78 | 8.20 | 54.80 |

The PBS b10 SNRs are 117.60 for Q, 37.59 for geometry-scaled R, and 111.33 for EPI test0. EPI uses a b0 reference; FSE uses b10. Time per volume is 34 s for Q/R and 48 s for these EPI scans. The voxel-normalized column additionally divides by volume and is sensitive to the stated EPI FOV assumption. R's physical voxel volume uses the protocol-derived 31.11-mm PE FOV and 35-mm read FOV; its whole-brain mask is from Q transformed with the independently fitted R-to-Q row scale.

## R geometry and ROI comparison

R was acquired with `gp_init_var=-1125` and 153 raw views, while Q/M use −1000 and 136. The navigator analysis reports an R-to-Q row-scale median of 0.8925 across slice/volume fits (range 0.8768–0.9023), close to the predicted 8/9 = 0.8889. That predicts a 31.11-mm phase FOV from the nominal 35 mm. R has the full set of 128 acquired phase-encode rows on its scanner/header grid; its field of view is compressed by the phase step. The separate 112-row sparse-grid issue applies to N: its PPL row mapping omits 16 edge ky lines, and no missing data were recovered by compact remapping.

The audit applies the same Q-defined whole-brain and free-PBS masks to R using the fitted centre-slice scale and the existing integer translation. The protocol-derived R voxel is 0.0664605 µL (0.2734375 × 0.2430556 × 1 mm), versus 0.07477 µL for Q. The geometry correction changes R b10 brain SNR from 16.83 to 17.02 and PBS SNR from 37.94 to 37.59; the corresponding brain SNR/√s/µL is 43.9117. It does not close the difference from Q (62.43 brain, 117.60 PBS). R and Q still differ in navigator mode and receiver gain, so that remaining gap is not attributable to sequence version alone.

For ADC, two conventions are retained: nominal b values and the source-model FSE effective trace b values. Effective b is a model prediction for the first imaging shot, not a measurement; it can differ by direction and volume. FSE's low-b reference is the acquired b10 +x volume, while EPI's is b0. Thus the low-b values have different references and should not be treated as a direct matched-reference comparison. Per-direction FSE effective-b ADCs use each direction's own effective-b denominator. The headline directional mean is their arithmetic mean; the legacy `MD_b1000` field instead takes the geometric mean signal and divides by the mean effective-b difference, so it is retained in the JSON with that label.

| Centre-slice ROI | Scan | b10→b1000 directional mean, effective b | b1000→b3000 directional mean, effective b |
|---|---|---:|---:|
| Ex-vivo brain | Q | 0.32461 | 0.23334 |
| Ex-vivo brain | R, scaled ROI | 0.37267 | 0.23064 |
| Free PBS | Q | 1.83713 | 1.13880 |
| Free PBS | R, scaled ROI | 1.83961 | 1.31719 |

Units are ×10⁻³ mm²/s. For R, the same-direction high-b estimates are x 0.22069, y 0.23103, z 0.24019. The high-b R mean is 1.16% below Q's 0.23334. The low-b R estimate remains about 15% above Q's effective-b directional mean. The reported high-b PBS values are below the signal-noise floor in places, so they are especially sensitive to magnitude-noise bias.

The [audited ADC figure](../figures/physical_scanner_2026-10-12/adc_summary_audited.png) labels the centre-slice R values as geometry-aware. The off-centre PBS panel remains exploratory: its PBS masks are regenerated per scan and slice from that image's signal threshold, and R uses the legacy translation-only mask placement there. It is not a same-physical-ROI slice comparison.

## Smoothed maps and pool summaries

The figure saved as [md_maps.png](../figures/physical_scanner_2026-10-12/md_maps.png) is a voxelwise two-point directional-geometric-mean ADC proxy, not a tensor MD fit. It smooths magnitude signals with a 0.7-pixel Gaussian before taking log ratios and does not subtract a noise floor. For ex-vivo panels the displayed mask is `ex_brain ∪ ex_pbs`; therefore the legacy `md_map_medians` values (including Q's approximately 1.82 at low b and 1.01 at high b) are pooled, PBS-dominated medians, not brain ADC summaries. The brain ROI summaries above use the fixed whole-brain mask and the ROI signal calculation instead.

## Scope and outputs

The legacy ROI CSV/JSON and original SNR/ADC figures were not rewritten. The independently recalculated R rows, masks, scale, voxel volume, nominal/effective-b per-direction ADCs, high-b interval ADCs, and both EPI voxel conventions are recorded in [oct12_quant_audit.json](oct12_quant_audit.json). The corrected figure labels in [oct12_figures.py](oct12_figures.py) replace the receive-profile cancellation, B1⁻, and prep-phase causal claims with descriptive wording. The revised figures were generated by calling only their figure functions, so the incomplete `oct12_extra_results.json` was not overwritten.
