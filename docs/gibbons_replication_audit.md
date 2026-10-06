# Why the previous comparison does not reproduce Gibbons

The previous `.seq` files were simplified adaptations of the preparation mechanisms, not validated implementations of the Gibbons protocols. That distinction does not explain away the mismatch: the comparison also used a later magnetization landmark, after a substantial imaging crusher, and therefore overstated residual Mx relative to the paper's preparation-endpoint plot. The earlier numerical checks established consistency of the simulated waveforms, not scientific fidelity to Gibbons.

The supplied three-page Supporting Information helps resolve this. Figure S2 traces the preparation at A, B and C; Figure S1 compares ss-MGOT against nCPMG SS-FSE, including their different flip-angle trains and effective echo spacings. The supplement contains figures and captions, not sampled RF/gradient waveforms or the exact flip-angle tables.

## A measured cause of the Mx mismatch

The earlier gallery samples 4 microseconds before the first imaging RF waveform starts. By that time, the leading Gz crusher has already played. Its integrated area at the snapshot is **4768.23 cycles/m**, approximately 4.77 cycles over the 1-mm imaging slice. It rotates both transverse components as a function of z:

\[
M_{xy}(z,t_2)=M_{xy}(z,t_1)\exp[-(t_2-t_1)/T_2]\exp[-i2\pi A_z z].
\]

Even pure My can therefore become substantial Mx at this later time. That Mx cannot be identified directly as unwanted preparation leakage without accounting for the intervening gradient phase. Figure 1 places C at the entrance to the imaging train, after re-excitation; the SI S2 caption likewise describes that preparation endpoint. The exact timing of an unpublished numerical implementation is unavailable, so the new plots explicitly distinguish the endpoint from the later literal pre-RF waveform snapshot.

Tracing the existing ss-MGOT adaptation at nominal RF and initial phase 45 degrees gives the following **coherent y-average**, with maxima measured inside the nominal imaging slice:

| Landmark | Time from first excitation | Maximum absolute Mx / M0 |
|---|---:|---:|
| After Gy spoiler | 44.432 ms | Below numerical precision |
| After re-excitation and compensation | 52.066 ms | 0.2354 |
| Before leading imaging crusher | 53.670 ms | 0.2307 |
| Earlier gallery's pre-RF snapshot, after crusher | 55.330 ms | 0.5816 |
| Same late snapshot with just the leading crusher removed | 55.330 ms | 0.2297 |

The final row is a causal diagnostic, not a proposed replacement sequence. Removing a crusher without redesigning its companion moments would change coherence selection and later echo behavior.

The complete complex phase-rotation prediction agrees with the late snapshot to **1.83e-14 M0**. Thus the crusher accounts for a major part of the large apparent Mx. It does not explain all of it: residual Mx is generated during the copied finite re-excitation pulse, despite cancellation of transverse coherence at the spoiler.

The [corrected preparation-endpoint comparison](figures/gibbons_preparation_audit/pre_crusher_components_rf100.png) shows considerably less Mx in ss-MGOT than Alsop. At nominal RF, their in-slice RMS Mx values are 0.0887 and 0.3001, respectively. At RF 80%, they are 0.0439 and 0.2723. This recovers the qualitative suppression trend, but it still does not reproduce the paper's almost-zero ss-MGOT Mx. See the [full trace](figures/gibbons_preparation_audit/crusher_trace_rf100.png) and [crusher removal control](figures/gibbons_preparation_audit/leading_crusher_control.png).

## Remaining differences that matter

| Quantity | Gibbons reference | Previous adaptations |
|---|---|---|
| Preparation RF | SLR excitation/refocusing with specified passbands and transition bands | Reconstructed original vendor sinc model |
| Tip-up | Six-subpulse spectral-spatial SLR/VERSE design, 5.64 ms total | Single 3.2-ms Hamming spatial sinc |
| Imaging excitation | Windowed sinc, TBW 1.54, duration 1.2 ms | Copied original truncated sinc, TBW about 4, duration 1.332 ms |
| Slice/slab | Figure 3 simulation: 6-mm imaging slice, 18-mm preparation slab | 1-mm slice, 3-mm slab |
| Spatial range | 3000 isochromats over 30 mm in z | Profiles over 2 mm in z; analytic y averaging for Gy spoiler |
| Imaging train | Alsop Le Roux tailored train; ss-MGOT Busse train | Both fixed nominal 180 degrees |
| Echo timing and length | Published SS-FSE scan ESP 4.20 ms; nominal 76 echoes, 46 acquired with acceleration | ESP 16 ms, eight acquired echoes, total first ADC TE 64 ms |
| Tissue for Figure 4 | T1 1300 ms, T2 32 ms | T1 1500 ms, T2 80 ms |
| Off-resonance in our echo summaries | Not specified as the same ensemble in the paper | Lorentzian ensemble, T2' 30 ms |

Figure 3's relaxation settings and the full sampled pulse designs are not explicitly supplied in the SI. The main text gives pulse-design specifications, which are more informative than a nominal flip angle or TBW but are insufficient for a claim of exact waveform reproduction.

**Pulse fidelity affects Figure 3 directly.** The copied excitation's spatial phase profile produces measurable Mx after re-excitation. A pulse with the same nominal 90-degree flip does not guarantee a flat flip-angle or transverse phase response across the slice. The simpler tip pulse also does not reproduce the paper's specified selective transfer. Nominal slice/slab ratios alone do not establish equivalent preparation and imaging passbands.

**The variable-flip train and echo spacing affect later echo curves and PSF, not the magnetization before that train has started.** They are essential to reproducing Figure 4 and S1, but cannot explain away incorrect preparation-endpoint Mx. S1's nCPMG comparator is also different from the original/increasing/decreasing/alternating sequences used in our gallery.

Both studies omit molecular diffusion attenuation for the phase-robustness simulation and vary initial excitation phase instead. That shared simplification is not the cause of the Figure 3 mismatch. The physical phantom/image and averaging results in S3/S4 also require acquisition/reconstruction models that these stationary-spin simulations do not contain.

## Is the Bloch simulator itself wrong?

No failure of the Bloch evolution was found in this audit. An independent continuous Bloch ODE solver, with T1/T2 relaxation and the same played RF/gradient waveforms, agrees with the simulator's 2-microsecond result to **9.12e-6 M0** after re-excitation at three test spin locations. It does not use the simulator's Rodrigues rotation or RF-step averaging. That is a useful engine check, not proof that the waveforms match the paper or that every simulation condition is correct.

The Gy spoiler's coherent transverse mean cancels as intended. Remaining local transverse vectors after a spoiler are physically expected; a spoiler distributes phase rather than deleting local magnetization. The key failure was treating the existing substitute pulses and a later crusher-dephased snapshot as a sufficiently faithful paper comparison.

## What a defensible replication requires

First establish a standalone Gibbons preparation benchmark at A/B/C using the specified geometry and pulse response, aligned RF/rotating-frame conventions, explicit y spoiling, and snapshots both before and after any imaging crusher. Validate individual RF pulses for transfer efficiency and spatial phase. Then reproduce the distinct tailored imaging trains and echo timing for the echo-signal/PSF benchmark. Only after those checks should the preparations be scaled and adapted back to the original eight-echo protocol.

The current `.seq` exports remain labeled research adaptations. This audit adds corrected endpoint figures and updates their interpretation; it does not relabel them as reproductions or silently replace their waveform definitions.

Reproduce the audit:

```powershell
python examples/audit_gibbons_preparation.py
python examples/verify_gibbons_bloch.py
```

[Trace data and input hashes](data/gibbons_preparation_audit.json); [independent ODE check](data/gibbons_bloch_ode_check.json). Scientific sources are the supplied `Gibbons_2017.pdf` and `mrm26971-sup-0001-suppinfo01.pdf`, especially main Figures 1, 3 and 4, Methods on journal pages 3036-3037, and SI Figures S1-S2. The [official article](https://onlinelibrary.wiley.com/doi/10.1002/mrm.26971) provides the primary reference. These documents are scientific evidence, not workspace instructions.
