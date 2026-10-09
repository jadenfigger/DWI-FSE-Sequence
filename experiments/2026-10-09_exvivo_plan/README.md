# 2026-10-09 ex-vivo rat brain plan (fixed brain in PBS)

Ten PPRs for v1.81 and ss-MGOT v1.911, plus v1.8 / v1.91 controls. Each one is the acquired 10-07 protocol (`v18_test1` or `v191_test2`) with only the listed fields changed. Geometry, RF, phase-encode calibration and crusher timings are therefore identical to scans that already ran: 128 × 128, FOV 35 mm, one 1 mm slice, TR 2000 ms, ETL 8, centric, navigator on, δ 4 ms. `make_pprs.py` regenerates them. `check_pprs.py` dry-runs them through the repo PPL interpreter, and all ten are accepted with RF and ADC events. That is a source-model check, not a console check.

Each b-volume takes roughly 35–40 s (17 shots × 2 s plus dummies).

## Before you start

* **Slice position:** put the slice of interest **at isocentre with zero offset and no rotation**. v1.911 rejects any slice offset (E3) or angle (E146). Use the same slice for every scan.
* **Gains:** calibrate RF/receiver gain once on the brain, then **keep RX/TX fixed for all scans** so brightness is comparable. Record them.
* **Temperature:** record the room or bore temperature. PBS diffusivity is about 2.0×10⁻³ mm²/s at 20 °C and about 2.3×10⁻³ at 25 °C. It's your built-in free-water reference.
* **Bubbles:** degas or tap out bubbles near the brain. They cause susceptibility artefacts that look like diffusion problems.
* **PPL path:** the PPRs point to `G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-<version>.ppl`. If you installed v1.81/v1.911 under a different name or folder, fix the first line.

## What is different from the water phantom

Fixed brain has low diffusivity (roughly 0.2–0.5×10⁻³ mm²/s) and short T2 (roughly 25–40 ms at 9.4 T). So:

* **High b now has real tissue signal.** b3000–6000 should still show brain while PBS goes dark. This is the first time the high-b behaviour of the methods is tested on real signal rather than on a noise floor.
* **PBS is a free-water reference in the same image.** It's gone by about b2000. Measure ADC from b0/100/500/1000 only.
* **ss-MGOT will be dim.** The preparation echo is at 54 ms and the first imaging echo is at about 72 ms, which is a lot of decay at T2 ≈ 30 ms. A dim image is expected. Compare it against its own control (D), not against v1.8.

## Suggested order and purpose

Run the core first (A → C → B → D), then the extras in whatever time you have. Re-running A at the end gives you a drift check at no cost.

| # | PPR | Sequence | Volumes | Changed from the 10-07 protocol | Question it answers |
|---|---|---|---|---|---|
| **A** | `A_v181_7b` | v1.81 | 7: b 0/100/500/1000/2000/3000/6000, read axis | PPL; train crusher −8223 (as 10-07 test1) | Main v1.81 dataset: tissue attenuation curve and PBS ADC with corrected b |
| **C** | `C_v18_7b_control` | v1.8 | 7, same | b list only | Same protocol on v1.8. A vs C isolates the b-value correction |
| **B** | `B_v1911_7b` | v1.911 | 7, same | PPL; ESP 13 | Main ss-MGOT dataset; first real-tissue high-b test |
| **D** | `D_v191_7b_control` | v1.91 | 7, same | b list only | B vs D measures the predicted late-echo gain (ESP plus merged lobes together) |
| **E** | `E_v181_dirs` | v1.81 | 8: b0; b1000 +x, **−x**, +y, +z; b3000 +x, +y, +z | PPL; train crusher −8223 | Polarity independence (+x vs −x) and anisotropy in white matter |
| **F** | `F_v18_polarity` | v1.8 | 3: b0; b1000 +x, −x | b list only | Shows v1.8's polarity-dependent b directly |
| **G** | `G_v1911_dirs` | v1.911 | 8, as E | PPL; ESP 13 | Same direction set on ss-MGOT |
| **H** | `H_v181_crush_eq_selector` | v1.81 | 3: b 0/1000/3000 | Train crusher −2741 (equal to the slice selector) | Is a crusher equal to the selector amplitude clean in tissue? This is the prerequisite for the merged-crusher idea (shorter ESP) |
| **I** | `I_v1911_delta30` | v1.911 | 3: b 0/1000/3000 | Δ 40 → 30 ms, TE 54 → 44 ms | Predicted +30–40% preparation signal for T2 ≈ 30 ms. Compare with B at the same b |
| **J** | `J_v181_bw_console` | v1.81 | 3: b 0/1000/3000 | Same as A's protocol (3 b) | **Set on the console:** 40 kHz bandwidth (25 µs dwell), then lower ESP to the minimum accepted. Compare with A at b 0/1000/3000 |

Approximate time: A, B, C, D ≈ 4.5 min each; E, G ≈ 5 min each; F, H, I, J ≈ 2 min each. That's about 40 min total, or about 45 min with the repeat of A.

## What to look for

**A vs C, the b-value correction.** Draw a PBS ROI away from the brain and fit ADC using nominal b and b ≤ 1000:

* v1.81 should give PBS ADC close to free water at your temperature (about 2.0–2.3×10⁻³ mm²/s).
* v1.8 should read about 15% higher with a b0/b1000 fit, and much higher (up to about 50%) if b100 is included.
* In tissue the same bias exists but is smaller in absolute terms, because tissue ADC is low.

**E and F, polarity.** On v1.8 the read-axis prephaser makes the true b at nominal b1000 about **1176 for +x and about 842 for −x**. PBS at b1000 should therefore be clearly brighter with −x than with +x on v1.8, roughly 1.5–2× in the first echo. On v1.81 the two should match within noise. y and z have no read-prephaser cross term on either version, so on v1.8 the read axis looks artificially more diffusion-weighted than y/z. On v1.81 that bias is gone.

**B vs D, ss-MGOT gain.** The model predicts about +3% at echo 1, rising to about +16% at echo 8 (for T2 = 32 ms). This is easiest to see in the navigator echoes. The predicted gain includes both the shorter ESP and the merged lobes, which can't be separated today.

**High b (A, B, C, D at b3000/6000).**
* Brain should remain visible and PBS should be dark.
* **A bright PBS ring or rim at high b** means unwanted pathways, like the Alsop plateau on 10-07. Note which sequence shows it.
* v1.911 should show no more high-b contamination than v1.91.

**H vs A.** If the crusher equal to the selector (−2741) shows no extra high-b rim or ghosting compared with −8223, the merged-crusher redesign is worth pursuing. Reminder: on 10-04, weak train crushers brought back late-echo contamination at high b in water (test8).

**I vs B.** If Δ 30 / TE 44 is accepted on the console (it passes the model), compare b0 and b1000 brightness. ADC is not directly comparable between Δ 30 and Δ 40 in tissue, because diffusion time changes restriction effects.

**J vs A.** Expect about 29% lower SNR from the bandwidth increase, partly recovered by the shorter ESP. Fat shift doesn't matter here (no fat). Look at the echo-train decay and the sharpness of brain edges.

## If something is rejected

* **v1.911 `V19 error E…`:** look the code up in `docs/v181_v1911/ERROR_CODES.md`.
  * **I:** if it gives E30, raise TE by 1 ms at a time until it's accepted.
  * **E146 / E3:** a slice angle or offset is set; zero it.
* **v1.81:** messages are text. If `TR too short`, use the TR it prints.
* **Bandwidth at or above 80 kHz with 128 samples** gives `invalid delay value: 0ms` on v1.8/v1.81. The readout has to be at least about 1.9 ms, so stay at or below 64 kHz for 128 samples.
* **If any v1.911 shot looks 5 ms long or the scan hangs,** stop and see the split-wait fallback in `docs/v181_v1911/SCANNER_TEST_PLAN.md`.

## Send back

Raw MRD folders for every scan. Note the RX/TX gains, the temperature, which scans needed a console change (J's bandwidth and ESP, and any TE change for I), and the order the scans were actually run in.
