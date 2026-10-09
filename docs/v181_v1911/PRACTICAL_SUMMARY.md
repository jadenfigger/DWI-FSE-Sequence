# v1.81 and ss-MGOT v1.911: practical summary

This is the imaging-side guide to the two new sequences: what changed, what you should expect to see, which protocol parameters you can no longer change, and what to check on the scanner. The engineering detail is in `FINAL_REPORT.md`, the rejection messages in `ERROR_CODES.md`, and the step-by-step scanner checks in `SCANNER_TEST_PLAN.md`.

**Status (2026-10-09):** both sequences compile on the console on the first try and look correct in the vendor simulator. Neither has acquired data yet. Everything below about signal and b-values is a prediction from modelling, not a measurement.

---

## 1. The short version

| | v1.81 (DW-FSE, from v1.8) | v1.911 (ss-MGOT, from v1.91) |
|---|---|---|
| Main goal | More accurate b-values and more reliable timing | More signal in the echo train |
| Biggest visible change | Measured ADC drops (closer to the truth); b0 images unchanged | Echo spacing 14 → 13 ms; later echoes brighter |
| Echo spacing / TE | Unchanged | ESP 13 ms (was 14 ms); every echo arrives earlier |
| Minimum TR | 174 ms (v1.8: 173 ms) | 193 ms (v1.91: 199 ms) |
| Predicted signal change | About +1.6% everywhere (slightly less diffusion weighting from imaging gradients) | +3% at echo 1 rising to about +16% at echo 8 (T2 = 32 ms tissue) |
| Can I mix data with the old version? | **No, not by nominal b-value** (see section 2.1) | Yes for b-values; but signal levels differ, so don't mix within one fit |

---

## 2. v1.81: what changed and what you will see

### 2.1 b-values now mean what they say (most important)

In v1.8 the read-direction "prephaser" gradient was played in the middle of the diffusion preparation. It acted like a small extra diffusion gradient, so the true b-value was higher than the number you typed in, and how much higher depended on which way the diffusion gradient pointed. v1.81 moves that gradient to just after the diffusion preparation, where it no longer adds diffusion weighting.

True b-value of the first echo, diffusion along the read axis (s/mm²):

| You type | v1.8 actually gave | v1.81 gives |
|---|---|---|
| 0 | 12 | 4 |
| 100 | 165 | 104 |
| 1000 | 1176 (only 842 if the gradient polarity is flipped) | 1001 (either polarity) |
| 6000 | 6398 | 5981 |

What this means for you:

* **ADC values from v1.8 were overestimated** when fitted with the typed b-values: by about 16% for a b0/b1000 pair, and about 53% for b0/b100. Your archived phantom value of about 0.00215 mm²/s becomes about 0.00184 mm²/s once the true v1.8 b-values are used.
* **v1.81 images at b1000 will look brighter than v1.8 at b1000**, because they are less diffusion-weighted. For the same phantom, expect a b1000/b0 signal ratio of about **0.158–0.161** on v1.81 against **0.116–0.119** on v1.8. This is the single best first test of v1.81.
* **Do not pool v1.8 and v1.81 data by typed b-value.** If you need to compare, use the true b-values in the table above (full per-echo tables are in `FINAL_REPORT.md` section 8).
* **Discard any empirical b-correction** you tuned on v1.8 phantoms; it does not apply to v1.81.
* The b-value the console prints ("want/got") is calculated exactly as before. It only ever counted the diffusion lobes, which is now the right answer.

The echo position in the readout moves by 0.4 µs (less than 1% of a pixel in k-space), so images should not shift, blur or ghost differently.

### 2.2 Timing that does not break under load

v1.8 had a few places where the timing schedule was very tight. If the console's instructions ran even slightly slower than expected, a gradient could be dropped or a whole 5 ms period added to the shot. In modelling this happened in 4 of 8 timing scenarios for v1.8 and in none of the normal ones for v1.81. Practically, you should see more consistent echo trains and fewer odd/even echo artefacts or intermittent signal drops, especially on longer protocols.

The cost is that the minimum TR goes up by 0.9 ms (173 → 174 ms for the test protocol). The shortest allowed TE/ESP is also 0.08 ms longer, which only matters if you were already at the limit.

### 2.3 Removed: CEST/MTC

The CEST/MTC preparation was removed to free code space (the compiled program was too close to the console's size limit). No protocol in the repository used it. Old protocols still load; if `mtc_on` is switched on, the scan refuses to start with a clear message.

---

## 3. v1.911 (ss-MGOT): what changed and what you will see

### 3.1 Shorter echo spacing, more signal in later echoes

Around each refocusing pulse there were several separate slice-direction gradients (crushers and the pieces that keep the stimulated-echo preparation stored). v1.911 merges each group into one gradient with exactly the same total area. The echo train therefore selects exactly the same signal pathways as before, but each echo takes 1 ms less, so the echo spacing drops from 14 to 13 ms.

Because each echo arrives sooner, there is less T2 decay and less diffusion loss along the train. Predicted signal gain over v1.91 (T2 = 32 ms tissue, D = 0.002 mm²/s):

| Echo | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| Gain | +3% | +5% | +8% | +10% | +12% | +13% | +15% | +16% |

For longer-T2 samples (around 60 ms) the gain is smaller, roughly +2% rising to +10%.

* **Point-spread / blurring:** a flatter signal decay across the echo train means slightly less blurring in the phase-encode direction.
* **b-values:** essentially unchanged from v1.91 (b1000 → 1014.7 vs 1014.6 s/mm²).
* **Gradient load:** slightly lower: lower slice-axis peak, about 16% less gradient energy on the slice axis.

### 3.2 Off-resonance caveat

At exactly the right frequency, v1.911 and v1.91 behave identically. Far off-resonance (±128 Hz), simulation of a single frequency shows late echoes up to 3% lower. Averaged over a realistic spread of frequencies in a voxel, and with normal tissue T2, this disappears (less than 0.3% difference). It could still appear as a slight extra loss in late echoes for very long-T2 samples in regions with poor shim. Worth a look in a deliberately off-resonance or poorly shimmed phantom.

### 3.3 Cleaner end of each shot

After the last echo, the slice gradient that "undoes" the stored preparation is now played after the receiver has completely finished. In v1.91 it overlapped the end of the final acquisition window by about 1.4 ms. This has no visible effect on images, but removes a possible source of interference in the last echo.

### 3.4 One A/B caveat

v1.91 cannot run at 13 ms and v1.911 only runs at 13 ms. A v1.91 versus v1.911 comparison therefore shows the effect of the shorter ESP and the merged gradients together. If you want to measure them separately, v1.911 can be validated at ESP 14 as an extra control (not yet done; it is a re-validation, not a redesign).

---

## 4. ss-MGOT v1.911: parameters you cannot change

The merged gradients were designed and checked for one specific timing layout. Anything that would change that layout is rejected before any RF is played. The scan simply refuses to start and prints `V19 error E<number>`.

### 4.1 New locks in v1.911

| Parameter | Fixed at | Error | Why |
|---|---|---|---|
| Echo spacing `esp` | **13 ms** | E144 (14–16), E32 (11–12), E31/E143 (others) | The merged gradients are sized to fill exactly the gaps in a 13 ms echo. 12 ms is physically impossible: the next gradient would start while the receiver is still finishing the previous echo. 14–16 ms would probably work but were not validated, so they are blocked rather than shipped untested. |
| Crusher duration `tcrush` | **1000 µs** | E140 (or E82/E18 first) | The merged lobes have a fixed shape; their size is calculated assuming this crusher length. |
| Gradient ramp time `tramp` | **200 µs** | E140 (or E82 first) | Same reason: the merged lobe shapes and the gaps around each RF pulse depend on it. |
| Read prephase time (`tdp`, set via `tref_setup`) | **700 µs** (default `tref_setup`) | E140 | The read/phase gradients that run alongside the merged slice lobes must have this length so everything fits in the 13 ms echo. |
| Gradient delay `rfdelay` | **60 µs** | E140 | The gaps that keep the merged lobes away from the RF pulses were checked assuming a 60 µs gradient delay. A different value would shift the gradients relative to the RF. |
| Slice/orientation angles (`subj_angle_x/y/z`, `r/p/s_angle_var`) and `phase_var` | **0** (unrotated, standard orientation) | E146 | In v1.911 the slice gradient now plays at the same time as the read and phase gradients. In an oblique slice these combine on the physical gradient coils, and we have no gradient ratings to confirm the coils can take the combined demand. Restricting to an unrotated geometry keeps each coil's load identical to what was checked. |
| Train crusher amplitude `crush_amp` | **Shipped value, -8223** (or a few nearby "lattice" values: -8242, -8237, -8233, -8228, -8219, -8214, -8209, -8205) | E142 | The merged lobe area must match the sum of the separate lobes to within 0.01%. Because gradient amplitudes are whole numbers, only certain crusher values divide out cleanly. Arbitrary values are rejected rather than accepted with a small area error. |
| Readout length (`sample_period`, `no_samples`) | Shipped sampling; longer readouts rejected | E143 | A longer readout does not fit inside the 13 ms echo with the merged gradients. Shorter readouts were not specifically tested. |

### 4.2 Locks inherited from v1.91 (unchanged)

These were already enforced in v1.91 and remain the same:

| Parameter | Restriction | Error | Why |
|---|---|---|---|
| Diffusion | Must be ON | E1 | ss-MGOT is a diffusion preparation; it makes no sense without it. |
| Driven equilibrium | OFF | E1, E57 | Incompatible with the stored preparation. |
| Crusher mode | Independent constant crushers | E1 | The pathway selection relies on fixed crusher areas. |
| Flow compensation, Dixon, 3D, skipped echoes | Not allowed | E2 | Not part of the validated design. |
| Slices | **One slice, centred** | E3 | The RF frequency is fixed for all pulse widths; multi-slice would need per-slice frequency handling. |
| Presat, CHESS fat-sat, CEST, gating, TR arrays | Not allowed | E4 | Would insert extra events into the validated timing. |
| Crusher ratios | \|C\|/\|D\| = 3.83 and \|C1\|/\|D\| = 2.55 | E17, E18 | These ratios decide which echo pathways are kept and which are crushed. Other ratios could let unwanted echoes through, and would need a new pathway validation and scan. |
| Dephasing cycles | 2 | E7 | Only 2 was validated. |
| `diff_tramp` | Must equal `tramp` | E8 | Consistent diffusion timing. |
| `v19_on` | 1 | E38 | The PPL contains only the ss-MGOT method. Use the v1.8/v1.81 PPL for conventional DW-FSE. |

### 4.3 What you can still change

* b-values and diffusion directions (up to 64 rows)
* Diffusion timing `big_delta` / `little_delta` (subject to the b-value and gradient limits)
* TR (193 ms or more for the default protocol)
* FOV, slice thickness, views and averages, within the usual checks
* Echo train length: allowed by the code, but only ETL 8 was validated

One option worth knowing: reducing `big_delta` from 40 to 30 ms shortens the preparation and is predicted to give **+37% preparation signal** (T2 = 32 ms), or +18% at T2 = 60 ms. It needs 16% more diffusion gradient (about 71% of full scale) for the same b, and it changes the diffusion time, so ADC values are not directly comparable with Δ = 40 ms data. It is a protocol choice and needs no code change.

---

## 5. v1.81: parameters you cannot change

v1.81 is much less restricted than v1.911, because none of its changes depend on a special timing layout. Everything that worked in v1.8 still works, except:

| Parameter / combination | Restriction | Message | Why |
|---|---|---|---|
| Diffusion ON **with** flow compensation | Not allowed | `V181 DWI requires flow compensation off` | The relocated read prephaser is a simple single gradient, not the flow-compensated shape. Combining them would give the wrong read moment. Use v1.8 if you need both. |
| CEST/MTC (`mtc_on`) | Must be 0 | `V181 CEST/MTC not supported` | Removed to make room in the program (see 2.3). Use v1.8 for CEST. |
| Minimum ESP/TE | 0.08 ms longer than v1.8 | `V181 ESP leaves no (train) read balance` or `TE too short ...` | Pays for the new 100 µs safety window that prevents dropped slice gradients. Only matters at the very shortest echo spacing. |
| Minimum TR | 0.9 ms longer than v1.8 | `TR too short, increase to N ms` | Pays for the enlarged setup windows that prevent timing slips. |
| Extreme read gradients | The moved read prephaser must fit the gradient amplitude and slew limits | `V181 first read prephase exceeds DAC/slew`, `V181 read relocation scale outside DAC` | After the move, the first read gradient carries slightly more area. At very small FOV or very high resolution it could exceed the limits, so it is checked. You are unlikely to hit this with normal protocols. |

Everything else (multi-slice, orientations, crushers, ETL, PE ordering, navigator, b-values, flow compensation without diffusion) behaves as in v1.8.

---

## 6. What to check first on the scanner

In priority order (full pass/fail criteria in `SCANNER_TEST_PLAN.md`):

1. **v1.81 b-value check:** a uniform phantom at b0 and b1000. Expect a b1000/b0 ratio of about 0.158–0.161 (v1.8 gave about 0.116–0.119). If it matches, the b-value correction is confirmed.
2. **v1.911 vs v1.91 echo signal:** the same phantom and b-value. Expect later echoes about 10–16% brighter on v1.911.
3. **Timing sanity:** check that the scan duration matches the console's predicted time for both sequences (a 5 ms-per-shot excess would point to a timing slip), and that the echo trains look clean with no missing or doubled echoes.
4. **v1.911 off-resonance:** if convenient, repeat with a poor shim or deliberate frequency offset and look at the late echoes.
5. **Echo centring:** echo peaks should sit near sample 65 of the readout, as in earlier scans.

If v1.911 hangs or each shot runs 5 ms long, see the fallback edit in `SCANNER_TEST_PLAN.md`. One end-of-shot timer value relies on behaviour that earlier versions also relied on, but it has not been timed on hardware.

---

## 7. Considered but not done

| Idea | Status | Why |
|---|---|---|
| Wider refocusing slab (1.2–1.5× the excitation slice) | **Held, high value** | Predicted +9% (1.2×) to +15% (1.5×) signal from better refocusing at the slice edges. Not shipped because it changes crusher areas and slice-gradient compensation, which must be re-proved first. |
| Navigator echo inside every imaging shot | **Held, high value for in-vivo** | Would allow shot-by-shot phase correction. It needs an agreed format for how the extra navigator lines are stored and reconstructed, which does not exist yet. |
| Shorter preparation via `big_delta` | **Available now as a protocol option** | See section 4.3. |
| ESP 14 matched control for v1.911 | **Available on request** | Separates the ESP effect from the merged-gradient effect. |
| Fixed echo-timing shift ("isodelay") | Not needed | Archived scans show echo peaks consistently at samples 64.8–65.1 with no drift. This is a receiver timing convention, not an error. |
| Variable flip angle train (v1.8) | Declined | Too sensitive to phase errors. |
| Weaker ss-MGOT crushers | Declined | Would change which echo pathways are kept, and would need new scans to validate. |
| Flipping crusher polarity | Declined | The current polarity is supported by the October 5 paired scans. |
