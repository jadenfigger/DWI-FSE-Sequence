# Signed Mx, My and Mz snapshots

The [interactive figure gallery](figures/magnetization_components/index.html) shows the original sequence, four crusher schedules and five RF variants. Select the sequence, RF strength, excitation phase and either a local spatial profile or a voxel mean by slice position. Every figure uses identical axes and one fixed rotating frame. The default 45° excitation phase matches the phase used for Gibbons Figure 3.

The [original six-landmark figure](figures/magnetization_components/original_rf080_phase045_line.png) and [final-ADC crusher comparison](figures/magnetization_components/compare_crushers_rf080_phase045.png) are useful starting points. All full-size PNGs are in the gallery folder.

## What Figure 3 in Gibbons shows

Source: Gibbons, Vasanawala, Pauly and Kerr, *Body Diffusion-Weighted Imaging Using Magnetization Prepared Single-Shot Fast Spin Echo and Extended Parallel Imaging Signal Averaging*, DOI [10.1002/mrm.26971](https://doi.org/10.1002/mrm.26971). Published online in 2017 and in the 2018 journal volume. The supplied `Gibbons_2017.pdf` was inspected directly, including Figure 3 and the simulation methods.

Figure 3 plots **signed local Cartesian components versus slice position**, immediately before the first imaging-train refocusing pulse, at Point C in Figure 1. Its two rows compare Alsop and ss-MGOT preparations. These are not transverse magnitudes, integrated echo amplitudes or separately isolated echo pathways. A negative curve is magnetization pointing along the negative component axis.

The paper's simulation methods use 3,000 isochromats over 30 mm along z, a 6-mm imaging slice, a 45° excitation phase and two cycles of added z dephasing. ss-MGOT uses an 18-mm preparation slab. Diffusion effects are omitted in those simulations; excitation phase variation supplies the MG violation. The paper uses specially designed preparation/tip-up/re-excitation pulses and different imaging RF trains. Its Figure 3 highlights residual transverse Mx after Alsop preparation and its substantial suppression with ss-MGOT. The visible sinusoidal profiles and stored Mz follow that preparation history.

Our sequence does not contain their complete tip-up, spoil and re-excitation preparation. Matching the component plot format does not imply reproduction of Alsop or ss-MGOT, or equivalent CPMG robustness. Here RF1 is the refocusing pulse within the diffusion encoding interval and precedes ADC1; it is not a separate imaging RF pulse following a completed magnetization preparation. The pre-RF1 panel is our closest timing diagnostic, rather than an identical Point C.

## What the components mean

For each simulated isochromat (a small spin ensemble with one position and frequency), the state is a vector

\[
\mathbf m=(M_x,M_y,M_z)/M_0.
\]

**Mx and My are signed transverse components in the rotating frame.** The two transverse axes describe RF/receive phase directions, not two different tissue populations. They combine into complex transverse magnetization

\[
m_\perp=m_x+i m_y,\qquad |m_\perp|=\sqrt{m_x^2+m_y^2}.
\]

Changing the phase reference rotates the pair without changing transverse magnitude. This is why “Mx is unwanted” is not a universal statement: the relation to the refocusing RF axis matters. In the unmodulated sequence the RF phase is 270°, so its axis is −y: My lies along that axis and Mx lies perpendicular to it. At a refocusing phase \(\phi\), the projections are

\[
m_{\parallel}=m_x\cos\phi+m_y\sin\phi,\qquad
m_{\perp,\mathrm{RF}}=-m_x\sin\phi+m_y\cos\phi.
\]

The MG condition concerns transverse magnetization parallel or antiparallel to the refocusing axis at the relevant refocusing time. Gradients can deliberately disperse phase before a pulse and later refocus it. Inspecting one component or one timestamp alone does not establish pathway suppression. With RF modulation, the axis changes; the figures keep the original fixed axes instead of rotating each panel to hide this change. The paper's abstract X/Y signal decomposition and its plotted Mx/My labels should also be interpreted with their RF phase convention.

**Mz is signed longitudinal magnetization along the static field.** At equilibrium it is +1; zero means no net longitudinal component; −1 means full inversion in this normalization. RF can move transverse magnetization onto z and later recall it. However, these Mz plots include unexcited equilibrium magnetization, inversion, RF-generated storage and T1 recovery together. Mz is neither the stimulated-echo signal nor a stimulated-echo percentage. Isolating stimulated routes requires RF-history tracking, as in the separate instantaneous-RF pathway analysis already in this repository.

The acquired complex signal is a coherent average of the transverse vectors, with receiver demodulation:

\[
S(t)=\left\langle m_x(t)+i m_y(t)\right\rangle
\exp[-i(\phi_{\rm ADC}+2\pi f_{\rm ADC}(t-t_{\rm ADC,start}))].
\]

Consequently \(|\langle m_\perp\rangle|\) can be much smaller than \(\langle |m_\perp|\rangle\): substantial local magnetization can cancel when its phases differ. The CSV reports both. Mz does not directly enter the receiver signal; it contributes after RF converts it back to transverse magnetization.

## How the simulation tracks them

The existing finite-duration Bloch simulator initializes every isochromat to `(0,0,1)` and carries its three components continuously through all events. It does not reset magnetization at each echo.

Outside RF, gradient integration and free precession are analytic. Pulseq gradients are in Hz/m, positions in m and off-resonance in Hz:

\[
\Phi=2\pi\left[\Delta f\,\Delta t+\sum_{a=x,y,z}r_a\int G_a(t)\,dt\right],
\]
\[
m_\perp(t+\Delta t)=m_\perp(t)e^{-i\Phi}e^{-\Delta t/T_2},\qquad
m_z(t+\Delta t)=1+[m_z(t)-1]e^{-\Delta t/T_1}.
\]

This simulator uses left-handed precession, `exp(-i Phi)`, with `Mxy=Mx+iMy`. Sign comparisons to another simulator require matching its convention and RF phase reference.

During each finite RF block, the complex RF waveform is averaged over each 2-µs simulation step while preserving its pulse area. Its real and imaginary parts, including amplitude scaling and phase/frequency offsets, form the transverse effective field. The played gradient and each spin's off-resonance form the longitudinal effective field:

\[
\mathbf b_{\rm eff}=(\mathrm{Re}\,B_1,\mathrm{Im}\,B_1,\Delta f+G_xx+G_yy+G_zz)\quad[\mathrm{Hz}].
\]

A Rodrigues rotation about this vector by \(-2\pi|\mathbf b_{\rm eff}|\Delta t\) updates all three components, followed by T1/T2 relaxation. Finite selective RF naturally produces a slice profile and couples transverse and longitudinal components. At a requested timestamp the arrays are copied, retaining their signs and all accumulated history. No fit to the paper's curves or per-panel amplitude normalization is applied.

## Protocol and sampling times

“Original” means the repository's **v1.6 source behavior with the established controlled eight-echo comparison overrides**: TE 36 ms, ESP 16 ms, 16 phase views, requested b=1000 s/mm² along readout, reduced imaging shot 1, no navigator, and the original centering behavior. The untouched default v1.6 PPR has ETL2; extending it to ETL8 is necessary to show echo 8. These are not simulations of the later TE54/ESP14 physical scanner tests or the v1.7 timing correction.

All times below are relative to the excitation RF center:

| Snapshot | Time | Definition |
|---|---:|---|
| Before RF1 | 17.332 ms | 2 µs before the RF waveform begins, after its leading crusher; sampled on an exact RF-step boundary |
| Before ADC1 | 32.799 ms | 1 µs before the first acquisition window opens |
| Middle ADC1 | 36.025 ms | Acquired sample index 64 of 128, zero-based |
| Middle ADC2 | 52.025 ms | Same sample convention in the second window |
| Before ADC8 | 144.799 ms | 1 µs before the eighth acquisition window opens |
| Middle ADC8 | 148.025 ms | Same sample convention in the final window |

“Before echo” here means before its ADC window, not before its preceding RF pulse or before the geometric echo center. The extra pre-RF1 panel supplies the different reference-paper view. ADC dwell is 50 µs, so the upper-middle acquired sample is 25 µs after the unsampled geometric midpoint. Actual block IDs, RF phases, ADC starts/midpoints and sample times are saved in the provenance JSON.

## Variants

Crusher multipliers apply to `[2754,5482,5482,5482,5482,5482,5482,5482]` DAC baselines. Both lobes within a pair use the same signed strength. Pulse 1 stays unchanged; decreasing reverses the increasing strengths for pulses 2–8.

| Variant | Crusher multipliers | Extra refocusing RF phase / nominal angles |
|---|---|---|
| Original | `[1,1,1,1,1,1,1,1]` | 0° / all 180° |
| Increasing | `[1,1,1.4,1.8,2.2,2.6,3,3.4]` | Unchanged |
| Increasing-alternating | `[1,-1,1.4,-1.8,2.2,-2.6,3,-3.4]` | Unchanged |
| Decreasing | `[1,3.4,3,2.6,2.2,1.8,1.4,1]` | Unchanged |
| Decreasing-alternating | `[1,-3.4,3,-2.6,2.2,-1.8,1.4,-1]` | Unchanged |
| Original + RF 0/90 | Original | `[0,90]` repeated / all 180° |
| Original + RF 0/180 | Original | `[0,180]` repeated / all 180° |
| Original + quadratic RF | Original | `65*k*k mod 360`, k=0…7 / all 180° |
| Increasing + RF 0/90 | Increasing | `[0,90]` repeated / all 180° |
| Increasing + RF taper | Increasing | 0° / `[180,180,175,170,165,160,155,150]` |

The phase tables are offsets from existing refocusing phases, with hardware phase quantization retained and receiver phases unchanged. They are exploratory tests, not implementations of a complete published stabilized nCPMG sequence. The angle taper is also an exploratory eight-pulse train, not the paper's Busse design. RF strengths 80% and 100% scale **both excitation and refocusing**. At 80%, a nominal 180° center flip becomes approximately 144° for an on-resonance spin. Excitation phase offsets 0°, 45° and 90° test different initial transverse orientations.

## Local profiles versus voxel means

The paper-style figures use **8,193 stationary isochromats along z from −1 to +1 mm**, with x=y=0 and off-resonance=0 Hz. Thus each curve is a local magnetization component, with no transverse spatial cancellation. The shaded region marks the nominal 1-mm slice. Read-axis diffusion/readout gradients have zero phase effect on this particular central line; these figures emphasize slice/RF/crusher history.

Companion figures use **8,192 stratified voxel isochromats**, seed 1, over a 0.2×0.2×2 mm support, and a clipped Lorentzian off-resonance distribution with T2′=30 ms. Each plotted point is the signed component averaged within one of 128 z bins; x/y/frequency and within-bin z phase cancellation are included. These conditional means therefore differ from individual spin profiles and depend on bin width and finite sampling. They are visual diagnostics, not a converged ranking of image quality.

Both models use T1=1.5 s, T2=80 ms and global B0=0. The local line has no off-resonance spread, so it does not acquire the ensemble's T2′ dephasing. T2′ is implemented by static frequency dispersion, rather than an extra decay factor applied to every spin. Diffusion gradients are played, but positions remain fixed; **Brownian diffusion attenuation is not simulated**. This follows the reference paper's omission of diffusion dynamics for its component plots, while preserving our own gradient waveform. The nominal b label alone does not make these water-diffusion predictions.

All variants share the same first RF and crusher. Their pre-RF1, pre-ADC1 and middle-ADC1 profiles therefore coincide for a matched RF strength and excitation phase; later changes cannot affect earlier magnetization. Differences begin with RF2. Rapid late spatial oscillations indicate phase dispersion, not necessarily loss of local transverse magnetization. Large or oscillating Mz shows longitudinal state structure, not a quantified stimulated route. Stronger or alternating crushers should be assessed through coherent transverse signal and pathway history, rather than by how flat one curve looks.

## Reproduction and verification

Run `python examples/compare_magnetization_components.py`; add `--reuse` to reuse matching raw component arrays. The script produces 60 conditions (10 variants × 2 RF strengths × 3 excitation phases), 120 detailed PNGs, 12 final-ADC comparison figures and an HTML gallery. Raw sequences and signed arrays remain under `runs/magnetization_components/`.

Three vector SVGs are also saved for zooming or export: the [original snapshots](figures/magnetization_components/original_rf080_phase045_line.svg), [crusher comparison](figures/magnetization_components/compare_crushers_rf080_phase045.svg) and [RF comparison](figures/magnetization_components/compare_rf_rf080_phase045.svg), at RF 80% and excitation phase 45°.

For a faster fresh run, first compute the independent raw simulations with `python examples/compare_magnetization_components.py --prefill --workers 4`, then generate figures and verification with `python examples/compare_magnetization_components.py --reuse`.

The [compact CSV](data/magnetization_components.csv) stores ensemble component means and transverse magnitudes. The [provenance JSON](data/magnetization_components_provenance.json) records source hashes, dependency versions, exact schedules/timestamps and numerical checks. Every generated sequence is checked before and after Pulseq readback. The three ADC snapshots are checked against the simulated complex receiver signal, including phase demodulation; the mixed line/voxel population used for that algebra check is not reported as a physical voxel signal. The CSV statistics use only the voxel population.

Additional checks compare signed components at 2-µs versus 1-µs RF steps, measure half-grid interpolation error for rapidly wound profiles, enforce finite bounded spin vectors and verify the shared early profiles. These validate the modeled component tracking; they do not validate the assumed vendor RF waveform or establish scanner performance.

Observed maximum ADC complex-signal closure error across all 60 conditions is **2.9×10⁻¹⁷ M0**. In five representative variants at RF 80% and excitation offset 90°, halving the RF step changes any tested component by at most **5.6×10⁻⁵ M0**. Linear interpolation from every other z point differs from the full grid by at most **0.00582 M0**; the taper has the largest spatial-resolution discrepancy. Independent full simulations agree with the saved component arrays, including the pre-RF checkpoint, within **3.9×10⁻¹⁴ M0**. Early profiles agree across all variants for each matched condition. No molecular-diffusion or scanner-image ranking follows from these numerical checks.
