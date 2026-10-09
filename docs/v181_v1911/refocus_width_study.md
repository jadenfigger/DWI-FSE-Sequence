# v1.81 isolated finite-waveform refocusing-width study

Actual archived v1.8 source mapping and stock RF, isolated finite refocus transfer study. Not a full train or scanner qualification.

The stock RF is decoded from actual vendor bytes and gated through the archived v1.8 source. The excitation gradient is retained. Refocusing-only gradient scaling uses signed integer DAC truncation. RF duration, amplitude and modeled energy are unchanged. No measured B1, power or SAR is inferred.

| B1 | B0 Hz | Width | Edge conjugate transfer | Excitation-weighted transfer |
|---:|---:|---:|---:|---:|
| 0.8 | -128 | 1.0 | 0.6945 | 0.8370 |
| 0.8 | -128 | 1.2 | 0.8369 | 0.8802 |
| 0.8 | -128 | 1.5 | 0.9132 | 0.8974 |
| 0.8 | 0 | 1.0 | 0.7149 | 0.8466 |
| 0.8 | 0 | 1.2 | 0.8654 | 0.8901 |
| 0.8 | 0 | 1.5 | 0.9382 | 0.9036 |
| 0.8 | 128 | 1.0 | 0.6960 | 0.8370 |
| 0.8 | 128 | 1.2 | 0.8375 | 0.8802 |
| 0.8 | 128 | 1.5 | 0.9130 | 0.8974 |
| 1.0 | -128 | 1.0 | 0.5603 | 0.8320 |
| 1.0 | -128 | 1.2 | 0.7467 | 0.9048 |
| 1.0 | -128 | 1.5 | 0.8859 | 0.9560 |
| 1.0 | 0 | 1.0 | 0.5691 | 0.8422 |
| 1.0 | 0 | 1.2 | 0.7693 | 0.9177 |
| 1.0 | 0 | 1.5 | 0.9117 | 0.9676 |
| 1.0 | 128 | 1.0 | 0.5627 | 0.8320 |
| 1.0 | 128 | 1.2 | 0.7483 | 0.9048 |
| 1.0 | 128 | 1.5 | 0.8867 | 0.9560 |
| 1.1 | -128 | 1.0 | 0.4381 | 0.7626 |
| 1.1 | -128 | 1.2 | 0.6304 | 0.8460 |
| 1.1 | -128 | 1.5 | 0.7943 | 0.9138 |
| 1.1 | 0 | 1.0 | 0.4379 | 0.7720 |
| 1.1 | 0 | 1.2 | 0.6460 | 0.8597 |
| 1.1 | 0 | 1.5 | 0.8172 | 0.9281 |
| 1.1 | 128 | 1.0 | 0.4408 | 0.7626 |
| 1.1 | 128 | 1.2 | 0.6324 | 0.8460 |
| 1.1 | 128 | 1.5 | 0.7956 | 0.9138 |

These are isolated conjugate-coherence coefficients, not complete train signal or an image-quality prediction. They measure how much incoming transverse coherence can enter the refocused conjugate branch. Excitation weighting uses the actual isolated excitation profile, and is an incoherent magnitude diagnostic.

## Compensation and implementation

Study supports useful spatial widening, but source must use independent refocus primary matrices, unchanged excitation and separate pre/post compensation. Current symmetric crusher primitive cannot supply both required corrections by a single amplitude change. Nonzero offsets require separate scaled refocus frequency. Do not ship simple selector scaling; require integrated finite-train and moment/pathway review.

The complete selector ramp/plateau is asymmetric around the mapped RF center because of inherited RF delay and instruction timing. Scaling only that selector changes effective moment. Geometric-center correction areas for every RF are recorded in the JSON; they are not a finite-RF equivalence claim. A symmetric crusher-amplitude change cannot independently restore these two different areas. Excitation compensation gs_comp/gs_rp must remain unchanged. Refocus phase/offset and compensation must be audited in a complete finite-RF train before packaging.

Shared primary gradient contains selection and crushers. Simple selector scaling reduces all crusher areas by16.7% or33.3%, violates preserved-pathway requirement, and is excluded.

For nonzero slice position the refocus frequency must use the scaled selector; at isocenter both frequencies are zero. A restricted zero-offset independent-crusher implementation can avoid a second frequency buffer, but still needs the two compensation areas and independent timing review.

## Independent model checks

Hard-pulse conjugate-transfer identity sin²(flip/2) maximum error: 3.33e-16. The piecewise continuous ODE comparison at offsets0,128,1192.3Hz gives maximum component error 3.89e-15.

Raw records independently match the library decoder and the exact quantized stock sinc formula. The source-mapped flip integral is reported explicitly; p180_scale185 does not imply a measured physical180degree pulse.

Recommendation: evaluate1.2x first, since1.5x gives more coverage but changes a larger spatial slab and more gradient area. Strong isolated-profile benefit justifies a separately reviewed integrated implementation; this study alone is insufficient for upload.
