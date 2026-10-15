# October 12 scanner analysis figures

[Scientific report](../../physical_scanner_experiments_2026-10-12.md) · [Scan catalog](../../../experiments/scan_catalog_2026-10-12.md)

Read the report for methods and limitations. Image panels use independent windows and do not compare absolute magnitude. FSE ADC uses source-model effective b; EPI uses recorded nominal b. Coverage on quality-masked maps is QC retention, not a precision estimate.

## Current audited summaries

- [Audited SNR summary](snr_summary_audited.png)
- [Audited ADC summary](adc_summary_audited.png)
- [Ex-vivo brain quality maps](slide_adc_exvivo_brain.png)
- [Ex-vivo PBS quality maps](slide_adc_exvivo_pbs.png)
- [In-vivo quality maps](slide_adc_invivo.png)
- [Combined ex-vivo quality-map report figure](adc_quality_maps_exvivo_full.png)
- [Preliminary in-vivo-only map](adc_quality_maps.png) — superseded by the final in-vivo panel above.

## Slide-ready scan comparisons

- [Ex-vivo v1.83, v1.912, and EPI](slide_exvivo_three_sequence.png)
- [In-vivo v1.83, v1.912, and EPI](slide_invivo_three_sequence.png)
- [Ex-vivo EPI and v1.83](slide_exvivo_epi_vs_v183.png) — b1000 directions differ; see panel labels.
- [In-vivo EPI and v1.83](slide_invivo_epi_vs_v183.png)
- [Baseline SNR bars](slide_snr_baseline.png)
- [Normalized SNR efficiency](slide_snr_efficiency.png)

## Revised presentation comparisons

These revised panels use square 20 mm physical crops for ex-vivo and in-vivo images. Reconstructed magnitude is displayed as linear I/σ using the established background-RMS estimator and a shared window within each sample/b-value comparison. K-space panels use the actual complex acquisition grids (FSE centric PE-reordered; EPI vendor-processed native grid), shown as per-panel peak-normalized 20 log10 magnitude from −50 to 0 dB; this normalization supports shape inspection only, not amplitude comparison. EPI played directions remain provisional, and ex-vivo EPI/FSE b=1000 uses different directions (+y and +x respectively).

- [Ex-vivo baseline sequence comparison](revised_exvivo_baseline.png) · [Ex-vivo b=6000 comparison](revised_exvivo_b6000.png)
- [In-vivo baseline sequence comparison](revised_invivo_baseline.png) · [In-vivo b=6000 comparison](revised_invivo_b6000.png)
- [Ex-vivo EPI/FSE comparison](revised_exvivo_epi_vs_fse.png) · [In-vivo EPI/FSE comparison](revised_invivo_epi_vs_fse.png)
- [Ex-vivo baseline k-space](revised_exvivo_kspace_baseline.png) · [Ex-vivo b=6000 k-space](revised_exvivo_kspace_b6000.png)
- [In-vivo baseline k-space](revised_invivo_kspace_baseline.png) · [In-vivo b=6000 k-space](revised_invivo_kspace_b6000.png)

## Other signal and sequence results

- [ETL 8 vs ETL 16](etl16_vs_etl8.png)
- [Smoothed descriptive MD maps](md_maps.png)
- [ss-MGOT left/right and depth](ssmgot_lr.png)
- [High-b ghost examples](ghost_examples_highb.png)
- [Ghost metric bars](ghost_metric_bars.png), [ex vivo](ghost_metric_bars_exvivo.png), [in vivo](ghost_metric_bars_invivo.png)

## Frequency and phase calibration

- [A/B frequency check](freq_check_AB.png)
- [D/E/F/G echo phase fits](phasecal_echo_phase_DEFG.png)
- [Reconstructed off-centre image strips](phasecal_image_strips.png)
- [Artifact vs phase](phasecal_artefact_vs_phase.png)
- [Phase-calibration scan at ±1.2 mm](phasecal_phcal_scan_pm1p2mm.png)
- [Ramp vs offset](phasecal_ramp_vs_offset.png)

## Navigator and raw layout analysis

- [N fixed vs M](nav_N_fixed_vs_M.png)
- [N layout diagnosis](nav_N_layout_diagnosis.png)
- [Per-echo ADC](nav_per_echo_adc.png)
- [Per-shot R](nav_per_shot_R.png)
- [Navigator trains, iA vs iB](nav_trains_iA_vs_iB.png)
- [Navigator trains, Q vs R](nav_trains_Q_vs_R.png)

## B1 simulation

- [Targeted B1 sensitivity simulation](oct12_b1_targeted.png) · [SVG](oct12_b1_targeted.svg) — modeled output, not a measured B1 map.

## Legacy summaries

These earlier files predate the audited calculations. Use the audited replacements above for current SNR and ADC summaries.

- [Legacy SNR summary](snr_summary.png)
- [Legacy ADC summary](adc_summary.png)
