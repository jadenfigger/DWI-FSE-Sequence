# DW FSE alternatives and their physics

This guide explains what the tested changes mean, what happened in the simulations, and my interpretation of why. The most promising change was to vary crusher strength between echoes. This reduced the contribution of unwanted signal routes while keeping a better balance of total signal than the more aggressive alternatives.

The results are simulations, not scanner measurements. Here, a substantial change means a large difference in a modeled result; it does not mean statistical significance from repeated scanner experiments. The physical explanations below distinguish direct model evidence from interpretations that still need testing.

## Where to find the original descriptions

- [Main report](ppl_improvement_report.md): Section 4 lists every alternative and its results. Section 5A describes the selected crusher schedule. Section 6 describes the limits and proposed physical tests.
- [Experiment definitions](../examples/improve_ppl.py): the `VARIANTS` list gives the exact settings for each named alternative.
- [Balanced candidate](params/improvement_candidate.json): the gradual crusher schedule with the timing correction.
- [Stronger candidate](params/improvement_purity_candidate.json): the more aggressive crusher schedule with the timing correction.

The main report contained some mechanism explanations, but did not provide a complete, accessible explanation of every alternative. This guide fills that gap.

## Picture the MRI signal as a collection of small arrows

Think of the local MRI signal as many small arrows rotating in a plane. When they point in the same direction, their signals add. When they point in different directions, they partly cancel. Their direction around the circle is called **phase**.

A **gradient** makes the magnetic field vary with position. During a gradient pulse, arrows at different positions turn by different amounts. This spreads their directions apart. The amount of spreading depends on the area under the gradient pulse: its strength integrated over its duration.

A **refocusing RF pulse** reverses the phase evolution of the intended signal route. With suitable timing, the arrows come back into alignment and produce an **echo**. In fast spin echo, the sequence repeats this process to collect several echoes after one excitation.

Real RF pulses do not refocus every spin perfectly. Some signal takes other routes, including spending time along the main magnetic field rather than rotating in the plane. That is called **longitudinal storage**. A later RF pulse can bring this stored signal back into the plane and make a **stimulated echo**. It carries a different history of gradients and relaxation.

These extra routes are not always harmful. They can reinforce the intended signal, or oppose it and cause a signal dip. Their changing contribution can also complicate image contrast and echo consistency. That is why I examined both unwanted-route contributions and total signal.

## What linear crushers means

The clearer name is **crusher strengths that increase in equal steps between refocusing pulses**. “Linear” describes the schedule across the echo train. Each crusher still has its usual trapezoidal shape, and its duration stays fixed.

A crusher pair consists of one gradient lobe before an RF pulse and another after it. In these tests, both lobes around a given RF pulse have the same strength and polarity. For the intended stationary-spin route, the RF pulse reverses the first lobe's phase effect, allowing the second lobe to cancel it. Other routes do not necessarily receive that same cancellation.

The tested gradual schedule was:

| Refocusing pulse | Crusher strength relative to the ordinary train value |
|---|---:|
| 1 | Original special first-pulse value, about 50% |
| 2 | 100% |
| 3 | 140% |
| 4 | 180% |
| 5 | 220% |
| 6 | 260% |
| 7 | 300% |
| 8 | 340% |

After pulse 2, each step adds 40% of the original train strength. It does not multiply the previous pulse by 1.4. The parameter list `[1, 1, 1.4, 1.8, 2.2, 2.6, 3, 3.4]` uses the first pulse's own smaller baseline for its first entry.

**Why I think it helped:** an unwanted route may skip some phase accumulation while stored longitudinally, or experience a different sequence of phase reversals. With repeated equal crushers, different parts of that route's gradient history can cancel later, allowing it to reappear in an acquired echo. Changing the crusher areas breaks many of these repeated cancellations. The intended route retains the equal pair around each RF pulse.

The exact pathway model supports this interpretation: with RF strength at 80% of its intended value, the eighth echo's unwanted amplitude share fell from **91.6% to 56.9%** with gradual crushers alone, while the intended route's amplitude stayed unchanged for stationary spins. Adding the timing correction brought the share to **53.0%**.

Varying crushers have also been used experimentally to separate primary and stimulated echoes in diffusion TSE. One published design used a *decreasing* schedule, illustrating that variation between pulses is the key idea; our increasing schedule is a tested candidate for this particular sequence, not a universal rule. [Ye and colleagues, ISMRM 2008](https://cds.ismrm.org/protected/08MProceedings/PDFfiles/00759.pdf).

## Why less unwanted signal can mean more or less total signal

Signals add as arrows, not just as positive numbers. Consider this illustrative example:

| Extra signal direction | Intended signal | Extra contribution | Total before suppression | Total after suppression |
|---|---:|---:|---:|---:|
| Same direction | 1.0 | +0.6 | 1.6 | 1.0 |
| Opposite direction | 1.0 | -0.6 | 0.4 | 1.0 |

Suppressing the extra route reduces total signal in the first case and increases it in the second. It does not create more intended signal.

This is my main interpretation of why varying crushers helped some phase-error cases but reduced signal in some aligned cases. Across 48 conditions, gradual crushers alone increased median eighth-echo total amplitude by about **14%**; gradual crushers with corrected timing increased it by **10.3%**. Those are grid summaries, not predictions of image SNR. The realistic RF simulation did not separately identify its intended route, so its total-signal changes cannot all be assigned conclusively to one mechanism.

## The other crusher alternatives

### Making the first crusher equal to the later ones

**Change:** increase the special first-pulse crusher to the ordinary train value, leaving later crushers constant (`equal_first`).

**Result:** unwanted amplitude share was **91.8%**, essentially unchanged from 91.6%.

**Interpretation:** matching the first pair does not remove the repeated pattern later in the train. It changes some early phase history, but does not prevent the unwanted routes that dominate the later echo in this test.

### Doubling every crusher

**Change:** double both the special first-pulse strength and the ordinary train strength (`double_crushers`). Durations stay fixed.

**Result:** unwanted share was **91.4%**, almost unchanged.

**Interpretation:** if an unwanted route has an exact cancellation of gradient areas, doubling every area preserves that cancellation. For example, doubling both sides of a zero balance still gives zero. Stronger repeated crushers may suppress some routes, but do not necessarily eliminate routes that return because of the repeated pattern.

### More aggressive varying crushers

**Change:** use multipliers `[1, 1, 1.3, 1.7, 2.1, 2.6, 3.2, 3.9]` (`varying`). The later pulses become stronger than in the gradual schedule. The version with timing correction is `combined`.

**Result:** with the correction, unwanted share fell to **49.0%**, but median total signal across 48 conditions was about **27% below the original**.

**Interpretation:** it filters unwanted routes more aggressively, including routes that had been reinforcing the signal. The unchanged intended amplitude in the stationary, instantaneous-RF model supports filtering as a mechanism there. It does not prove that all signal lost in the realistic RF model was expendable. The extra suppression was a poor trade for the total-signal loss.

### An irregular crusher schedule

**Change:** use a deliberately uneven sequence, `[1, 1, 1.71, 0.83, 1.37, 2.13, 1.09, 1.91]` (`irregular_crushers`).

**Result:** unwanted share fell to **64.6%**, but total signal was lower than with the gradual schedule in both screened phase conditions.

**Interpretation:** breaking repetition can help, but an arbitrary uneven pattern is not automatically a good filter. Which gradient histories remain aligned at the sample matters more than how irregular the table looks.

### Alternating crusher polarity

**Change:** switch the sign of the pair from one RF pulse to the next, using `[1, -1, 1, -1, ...]` (`alternate`). Both lobes within each pair still match.

**Result:** unwanted share improved only to **85.6%**, while total signal fell substantially: about **76%** in the aligned screening case and **54%** in the phase-offset case.

**Interpretation:** changing sign rearranges which routes can align and how they interfere. A subsequent [ADC snapshot decomposition](echo_snapshot_comparison.md) makes this more specific: at echo 8 the primary amplitude stays at 0.06675, but the other coherent contribution points about 175 degrees opposite it and cancels most of it. Substantial stimulated signal remains; the loss is not simply the removal of helpful routes. This particular pattern is unattractive under the tested settings, but is not evidence against alternating crushers generally. [Tu and colleagues](https://pmc.ncbi.nlm.nih.gov/articles/PMC4252722/) explicitly alternate crusher signs in diffusion multi-spin-echo imaging with different RF and acquisition details. Other diffusion sequences also use reversals tailored to their diffusion gradients. [Wu and colleagues, ISMRM 2011](https://cds.ismrm.org/protected/11MProceedings/PDFfiles/1964.pdf).

### Halving crusher duration

**Change:** halve the train crusher's flat-top duration from 1000 to 500 microseconds (`duration_half`). The ramps retain their duration, so the full pulse area is not exactly halved.

**Result:** unwanted share was **92.1%**; total signal in the phase-offset case fell about **65%**.

**Interpretation:** shortening the lobe reduces spatial phase spreading and changes the phase histories that can return to the echo. It also changes their interference. The tested reduction offered neither better route suppression nor better phase-offset signal.

## Correcting gradient alignment around the RF pulse

**Change:** restore the intended compensation for the assumed 60-microsecond delay between a commanded gradient and its physical playback (`centered`). RF and echo centers remain fixed; the relevant gradient timing is shifted to restore alignment.

**Result:** the modeled residual slice-direction phase slope became much smaller. Alone, the correction barely changed the grid median total signal, about **+0.9%**, and did not reduce unwanted share: **92.0%** versus 91.6%.

**Physics explanation:** refocusing depends on the gradient area actually experienced before and after the RF pulse. Misalignment can leave a residual phase variation across the slice, even when the commanded waveform looks balanced. Correcting the alignment restores the intended balance under the assumed hardware delay.

**My interpretation:** this is a timing correctness change, with effects on slice response and phase. It is not by itself a solution to the many unwanted routes produced by imperfect RF. Its interaction with varying crushers explains why the combined result differs from either change alone. The physical delay still needs measurement on the scanner.

## Changing RF phases

**Change:** rotate the RF pulse's rotation axis between echoes while retaining the nominal flip angle. The tests used alternating 0/180-degree offsets (`phase_alternate`), alternating 0/90-degree offsets (`phase_xy`), and a curved progression of offsets defined by `65*k*k mod 360` (`phase_quadratic`). Receiver phases were unchanged.

**Result:** some phase-offset signals increased substantially, but unwanted amplitude share stayed at **91.6%** in the idealized model. Adding the timing correction to XY phases did not establish a purity improvement either.

**Physics explanation:** RF phase changes the direction in which the pulse rotates magnetization. Different signal routes can acquire different final arrow directions. Their individual strengths can remain the same while their combined signal changes from partial cancellation to reinforcement.

**My interpretation:** these tests mainly rearranged interference rather than removing unwanted routes. A phase scheme can still be useful, but it needs suitable handling of the complex echoes and image reconstruction. Our short quadratic table was not a complete implementation of the published non-CPMG method, which uses additional preparation and signal handling. [Le Roux and McKinnon, ISMRM 1998](https://cds.ismrm.org/ismrm-1998/PDF2/p0574.pdf).

## Changing RF strength or shape

### Nominal refocusing angles of 160 or 200 degrees

**Change:** set the nominal refocusing angle below or above 180 degrees (`flip160`, `flip200`).

**Result:** neither improved both screened phase conditions. At 80% RF strength, the 200-degree setting increased the idealized intended-route amplitude, but total signal in the phase-offset case became much worse.

**Physics explanation:** at 80% strength, nominal angles of 160, 180 and 200 degrees become approximately 128, 144 and 160 degrees. The 200-degree setting is therefore closer to a perfect 180-degree refocus in this specific underpowered case. That can preserve more signal through each pulse, with the effect accumulating across eight pulses. It also changes how much signal enters other routes and how those routes interfere.

**My interpretation:** correcting a known RF calibration error can help, but a fixed overflip is not a general solution. With properly calibrated or stronger RF it can overshoot, and the phase-offset result here was poor.

### Changing the RF waveform model

**Change:** taper the assumed RF waveform with a Hanning window (`hanning`), or use a sinc waveform matched to the assumed bandwidth (`bw_matched`). These are alternative models of the unavailable vendor RF pulse, not validated scanner replacements.

**Result:** realistic RF signal changed substantially, especially with phase error. The instantaneous-RF pathway model reported the same unwanted share because it does not represent the waveform shape or slice profile.

**Physics explanation:** waveform shape affects which positions and frequencies receive the intended flip angle. The excitation and refocusing slice profiles may not match. Spins near the slice edge can therefore experience different rotations and contribute different echo histories.

**My interpretation:** the size of the response shows why obtaining the actual RF waveform and measuring slice profiles is necessary before trusting exact signal predictions.

## Increasing echo spacing

**Change:** increase spacing between successive echoes from 16 to 36 milliseconds, matching the 36-millisecond first echo time (`equal_interval`).

**Result:** echo 8 moved from **148 to 288 milliseconds**. The intended amplitude fell from **0.06675 to 0.01160**, and unwanted share rose to **95.8%**.

**Physics explanation:** the intended route remains in the rotating plane and loses signal through T2 relaxation throughout the extra waiting time. With the model's T2 of 80 milliseconds, the extra 140 milliseconds leaves only about **17%** of that route's previous amplitude. This closely explains the observed intended-signal reduction. Routes stored longitudinally have a different relaxation history.

**My interpretation:** the large loss is mainly a waiting-time penalty. This test changed train length as well as interval matching, so it does not cleanly determine whether unequal spacing itself is the cause of the original behavior.

## Removing the final crusher or changing the read prephaser

**Final crusher off (`post_off`):** this removes a gradient after the acquired echo train. It cannot change echoes already acquired. It could affect the next repetition by changing residual magnetization. Even after eight dummy repetitions, the modeled difference was negligible at a two-second repetition time. Shorter repetition times and scanner effects remain separate questions.

**Read prephaser from 110% to 100% (`prephaser100`):** this changes the gradient that positions the signal for the readout. It can change which part of a spatially wound signal is sampled. Unwanted share stayed near the baseline, **91.7%**, and there was no useful acquired-signal advantage. The tested adjustment did not act as an effective unwanted-route filter.

## Why preserving stationary signal does not guarantee preserving water signal

Equal crusher lobes can cancel phase for a spin that stays in the same place. A water molecule that diffuses between the lobes experiences different positions and therefore different phase changes. The second lobe cannot perfectly undo the first. Across many molecules, this causes signal loss.

In the water check, the gradual schedule with corrected timing reduced the intended eighth-echo amplitude by **8.3%**. The full modeled diffusion weighting at echo 8 increased from about **1150 to 1237 s/mm²**, although the requested diffusion setting was still 1000. Crushers and imaging gradients contribute to diffusion weighting too. Research on stimulated-echo diffusion imaging demonstrates why those contributions and their interactions need to be included in the full calculation. [Lundell and colleagues, 2014](https://pmc.ncbi.nlm.nih.gov/articles/PMC4312915/).

The crusher change also adds weighting along the slice direction. Reducing the main diffusion gradient to recover a single b-value would not automatically recover the original directional weighting.

## What I would test next and why

1. **Compare original, gradual-only, and gradual-plus-timing designs in a stationary phantom.** This separates the effect of changing gradient histories from the effect of correcting timing. Record the complex echoes, because magnitude alone hides reinforcement and cancellation.
2. **Measure RF strength, slice profiles and physical gradient delay.** These determine whether the assumed rotations and timing match the scanner.
3. **Repeat with diffusion on and off and in several directions.** This tests whether the route-suppression benefit outweighs added diffusion loss and directional bias.
4. **Introduce controlled phase errors or motion and reconstruct images.** This tests whether the modeled improvement translates into fewer artifacts and adequate useful signal.

I favor the gradual schedule because it showed the best measured compromise in these tests. The result supports changing the gradient history between pulses, rather than assuming that larger gradients always work better. It remains incomplete: at 70% RF strength, the balanced candidate's unwanted share was still about 85%. The next useful result is a scanner comparison showing how much image quality improves and how much useful signal it costs.

All numerical comparisons above come from the [main report](ppl_improvement_report.md) and its archived simulation data. The unwanted percentage is the sum of other-route amplitude magnitudes divided by the sum of all-route amplitude magnitudes at the acquired sample. It is not a percentage of image artifacts. The explanations of individual effects are physical interpretations; the tests did not independently isolate every mechanism in the realistic RF model.
