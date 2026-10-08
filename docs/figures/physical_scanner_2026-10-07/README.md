# October 7 comparison figures

Reproduce the figures and image/raw measurements from the original MRDs:

```powershell
python docs/data/physical_scanner_analysis_2026-10-07.py
```

`--metrics-only` refreshes the numerical JSON/CSV files and ROI illustration without regenerating the remaining figures. `--preview` generates the initial all-scan ROI inspection montage. Original acquisitions and adjacent reconstructed files are read only.

Image montages use the **uncorrected complex inverse FFT**, the acquired PE1 row ordering, and the full 35 mm field of view. Columns compare the same requested b value with the same absolute display limits; b columns have different limits. The two `all_scans` pages share the same limits. All October 7 scans record RX gain 30 and TX gain −195. No per-scan contrast normalization or image registration is applied. Read axis/sample index is horizontal and phase/image row is vertical; orientation is the scanner reconstruction convention, rather than an independently verified anatomical coordinate system.

The `kspace_` montages reorder the original **complex imaging ADC samples directly** and exclude the navigator train. Their display is `log10(1 + |K| / 1 acquisition unit)` with the same offset and limits per b column. They do not Fourier transform magnitude images. Energy is conserved by the row permutation, and the displayed data reproduce the corresponding complex images.

| Figures | Purpose |
|---|---|
| `all_scans_1.png`, `all_scans_2.png` and corresponding `kspace_` files | All ten acquisitions at b0, b1000 and b6000 |
| `new_methods_etl8.png`, `new_methods_etl16.png` and corresponding `kspace_` files | Matched train-length comparisons of baseline, v1.91 and v1.92 |
| `crusher_amplitude.png` and `kspace_crusher_amplitude.png` | Controlled test0/test1 baseline train-crusher amplitude change |
| `v191_comparison.png`, `v192_comparison.png` and corresponding `kspace_` files | Within-method train-length/b-sampling changes and repeated v1.92 protocol |
| `seven_b_comparison.png`, `test*_seven_b.png` | All seven requested b values; same limits across scans per b column |
| `roi_placement.png` | Fixed interior, rim and distant-corner background masks on all ten b1000 images |
| `raw_high_b_location.png` | Original b6000 navigator ADC magnitudes on one common absolute scale |
| `kspace_profiles.png` | Uncorrected imaging ADC/ky norms and navigator envelope by echo |
| `navigator_model_diagnostics.png`, `navigator_projections.png` | Navigator phase, best global-complex-scalar fit, spatial phase coherence and projected shape |
| `reconstruction_ablation_b0.png`, `reconstruction_ablation_b1000.png`, `reconstruction_ablation_b6000.png` | Fixed-raw-data comparison of no correction, amplitude correction, and amplitude-plus-phase correction |
| `signal_and_raw_metrics.png` | Absolute/normalized image signal, raw navigator signal, empirical background and texture |
| `v192_repeatability.png` | Fixed-coordinate profiles and magnitude-image differences for identical stored-protocol repeats |
| `attenuation_and_plateau.png` | Additional attenuation analysis; reproduced by `docs/data/oct07_attenuation_analysis.py` |

Numerical measurements are in `docs/data/physical_scanner_analysis_2026-10-07.json`, `oct07_image_measurements.csv`, `oct07_kspace_measurements.csv`, `oct07_correction_ablation.csv` and `oct07_alignment.csv`. `oct07_roi_masks.npz` preserves the exact masks. Mask center is (x=61, y=71), interior radius 34 pixels, rim radii 41–47 pixels; distant background uses y<20 and x<16 or x≥112.

The distant-corner background is an empirical reference that can contain artifacts. Interior/background contrast is not calibrated SNR. Gaussian-smoothed interior CV includes broad shading and any specimen nonuniformity; high-pass RMS includes noise as well as texture. Raw navigator excess-power estimates use approximate ADC background windows, not a noise-only reference. Magnitude attenuation near background has positive noise bias. Low edge power does not establish successful diffusion weighting: signal may instead remain coherently centered in the ADC window. Reported b values are requested values; figures alone do not validate the physical b-tensor of every coherence pathway.
