# How the ADC and b-values in the 10-10-2026 slides were calculated

Read this before presenting `10-10-2026_report.pptx`. All numbers come from `docs/data/oct10_slide_numbers.json`, produced by `docs/data/oct10_slide_figures.py`. The deck is built by `docs/data/oct10_build_slides.py`. The full write-up is `docs/physical_scanner_experiments_2026-10-10.md`.

## 1. Signal used for every ADC

* **Images.** The saved reconstructed NIfTI magnitude images (the same recon as your PNGs), slice 1.
* **ROI.** One fixed interior disk of radius 34 pixels, about 9.3 mm at 0.27 mm/pixel, centred on the phantom. The same disk is used for every scan and b-value. It stays clear of the phantom edge and the bright edge line.
* **Noise correction.** Magnitude images never reach zero, because noise leaves a positive floor. Each ROI value is therefore corrected:
  * S = √(mean(I²) − 2σ²)
  * σ is measured in the four background corners.
  * The correction changes the signal by less than 0.1% up to b1000. It matters only at b2000–3000, where the signal approaches the noise.
* **b6000 is not used.** The water signal is pure noise there.

## 2. ADC on each slide

| Slide | Calculation |
|---|---|
| Direction table (slide 2) | Two points: **ADC = ln(S(b0) / S(b1000)) / 1000**, using the typed b-value. "% diff" is relative to the mean of the four directions. Only b0/b1000 could be used, because −x was acquired only at b1000 and b3000 is close to the noise floor. Only +z was acquired, not −z. |
| Fit graphs (slide 3) | Least-squares straight line of **ln S against b** over **b = 100–3000**, with ADC = −slope. The b0 point is plotted but **excluded from the fit**, as in the 09-10 report. The reason this time is the v1.81 b0 echo-1 artifact (§4). R² is for the log fit. |
| Apparent ADC graph (slides 4 and 6) | Same method as 09-10: **ADC(b) = ln(S(b100) / S(b)) / (b − 100)** for b = 500, 1000, 2000, 3000. A flat line means the b-values are self-consistent. A sloping line means the b-values are wrong, or that something other than diffusion is changing the signal. |
| ADC table (slide 5) and v1.81/v1.911 table (slide 8) | The fit from slide 3 (b100–3000), done with typed b ("Nominal b") and with effective b ("Effective b"). |

## 3. What the "effective b-value" is and how it was obtained

The b-value you type only counts the two diffusion lobes. The spins also see every other gradient between the excitation and the echo: slice-select and refocusing lobes, crushers and the read prephaser. The **effective b** includes all of them:

> b = (2π)² ∫ k(t)² dt from excitation to echo, where k(t) is the gradient area accumulated so far. The 180° pulses flip its sign.

**Where the numbers come from.** The values were computed in October from the sequence code itself. The PPL was run through the repository's event model to get the exact timing and amplitude of every gradient, and that timeline was integrated for echo 1 along +x. The source tables are `docs/v181_v1911/FINAL_REPORT.md` §8 and `review_checks/final_physics_grid.json`. They are **calculated, not measured on the scanner.**

**Why v1.8 is wrong.** In v1.8 the read prephaser sits *between* the two diffusion lobes. Its gradient area adds to (+x) or subtracts from (−x) the diffusion area, which creates a large cross term. v1.81 moves the prephaser to *after* the diffusion pair, so the cross term disappears.

| Typed b | v1.8, +x | v1.8, −x | v1.81 (either sign) |
|---:|---:|---:|---:|
| 0 | 12 | 12 | 4 |
| 100 | 165 | 59 | 104 |
| 1000 | 1176 | 842 | 1001 |
| 6000 | 6398 | 5579 | 5981 |

**Intermediate b-values.** The model only gives 0, 100, 1000 and 6000, so 500, 2000 and 3000 were filled in with the model's own decomposition:

* **v1.8 / v1.81:** effective b = (diffusion lobes) + (fixed imaging-gradient term) + (cross term). The cross term grows with √b: 167.5 √(b/1000) for v1.8 +x, and 0.25 √(b/1000) for v1.81.
* **ss-MGOT:** a smooth three-parameter curve through the four table points, accurate to within 0.1 s/mm².

**ADC with effective b.** The same fits, with the effective b on the x-axis instead of the typed b. Only differences in b matter for ADC, so the constant offset at b0 cancels.

**Limits of the effective b:**

* It is modelled for **echo 1, along x**. y has no cross term, so y uses the x value. z has an extra cross term that the model puts at about 37 s/mm² at b1000, but the data suggest about 74. That is why the direction table uses typed b, and why +z reads about 5–7% high.
* Δ30 and the 40 kHz scans were not modelled; they are not in the deck.

## 4. Things to be ready to explain

* **Why b0 is excluded from the fits.** On v1.81 only, at b = 0 only, echo 1 comes back about 4–5% weak. It disappears at every b ≥ 100 and never happens on v1.8. It is probably a stray signal pathway that the old (misplaced) read prephaser used to dephase. Centric ordering puts echo 1 at the centre of k-space, so the b0 image is slightly dim. That makes a b0-based ADC about 2% low and the b0→b100 slope look wrong. Next step: use b ≈ 10 as the reference.
* **Why the image-based ADCs differ by a few %, when the raw-echo values agree to 0.7%.**
  * The image ROI includes coil shading and the b0 artifact.
  * The navigator echoes (raw, un-phase-encoded echoes, echoes 2–8) avoid both. They give, ×10⁻³ mm²/s (typed b → effective b):

    | Sequence | Typed b | Effective b |
    |---|---:|---:|
    | v1.8 | 2.159 | 1.855 |
    | v1.81 | 1.843 | 1.849 |
    | v1.91 | 1.852 | 1.862 |
    | v1.911 | 1.841 | 1.852 |

  * That is the cleanest evidence that the b correction is right.
* **What the water ADC means.** About 1.85×10⁻³ mm²/s implies roughly 16–17 °C if the phantom is pure water. The room or bore temperature was not recorded.
* **Polarity.** v1.81 +x and −x agree to about 1% (0.3% in the raw echoes). For v1.8 the model predicts that −x would be roughly 1.8× brighter at b1000. That scan (F) was not run today.
* **Other quantities in the deck:**
  * **SNR** (image slide) = ROI mean ÷ (background standard deviation / 0.655), the usual magnitude-noise correction.
  * **Echo-train graph:** raw navigator echo amplitude, noise-subtracted, with no correction. Echo times are from the sequence model: 54 + 14(n−1) ms for v1.81 and 72.7 + 13(n−1) ms for v1.911.
  * **Sequence diagrams:** drawn from the same source model, not measured gradient traces.
