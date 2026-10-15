# Oct 12 full-field reconstruction exports

All images are uncropped, unresampled full grids rendered on black using the scanner reconstruction script display convention. The image files show raw reconstructed magnitude in reconstruction units, with no σ normalization. The k-space files show `ln(1 + |K|)` from raw complex magnitude, with no per-panel normalization. Each sample/type group uses one fixed 0-to-maximum color scale across every selected sequence, b-value, volume, and slice. Colorbar ticks are readable and untruncated.

FSE k-space is the actual complex PE-reordered acquisition grid. EPI k-space is the native vendor-processed complex `_o.MRD` grid; EPI image is its inverse FFT with only the verified read-axis reversal used for display. EPI remains 128×168 and is shown without resampling; FSE retains its native grid. EPI direction labels are decoded from the acquisition b-table and remain provisional. Receiver gains and reconstruction/vendor processing differ across acquisitions, so displayed magnitude is not calibrated SNR and should not be treated as a cross-sequence intensity measurement.

The four shared limits are:

| Group | vmin | vmax |
|---|---:|---:|
| exvivo image | 0 | 2.45846462 |
| exvivo log_kspace | 0 | 9.11970497 |
| invivo image | 0 | 8.2144556 |
| invivo log_kspace | 0 | 8.9570303 |

Full exports are indexed in [`index.csv`](index.csv). Selected central slices for slide assembly are in [`slide_ready/`](slide_ready/) with a separate [`slide_ready/index.csv`](slide_ready/index.csv). The PNG bundle is [`oct12_full_field_exports.zip`](../oct12_full_field_exports.zip).

Full export index contains 147 acquisition-volume/slice rows across M, O, iA, iB, test0 EPI, and invivoA EPI.
