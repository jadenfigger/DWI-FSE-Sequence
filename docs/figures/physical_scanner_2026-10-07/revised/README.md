# Revised comparison figures

Six simpler presentation copies of the crusher amplitude and ETL8/ETL16
method comparisons, including their k-space counterparts.

Reproduce from the repository root:

```powershell
python docs/data/revise_physical_scanner_figures_2026-10-07.py
```

The plots use shorter titles, one b-value label per column, one scan/method or
crusher label per row, and unlabeled colorbars. Repeated k-space axes and the
long explanatory subtitles are omitted. Fonts, white backgrounds, and the
grayscale/magma palettes follow ordinary Matplotlib styling.

All six revised figures apply the navigator correction used by
`scanner/recon/bare_bones_recon_fse.py`: `nav_mode="deramp"`,
`nav_apply_phase=True`, and `nav_eps=0.01`. The shared `nav_envelope` and
`nav_correction` functions are used through the original analysis module.
Correction factors multiply complex imaging ADC lines before the inverse FFT
and before the k-space magnitude/log display; navigator lines themselves are
excluded from the panels.

Image panels show corrected magnitude; k-space panels show
`log10(1 + |K_corrected| / 1 acquisition unit)`. Display maxima are recomputed
from the corrected panels and shared across scans within each b-value column;
there is no per-scan brightness normalization. Raw acquisitions, full field of
view, orientation, and nearest-pixel display are unchanged.
Columns show requested b-values in s/mm². Crusher row labels show the signed
imaging train amplitude in DAC units; the first crusher is −5482 DAC in both
scans. Method labels are original (v1.8), ss-MGOT (v1.91), and Alsop (v1.92),
with the original scan IDs retained.

The original, fully annotated, uncorrected figures remain in the parent folder.
