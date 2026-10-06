# Independent physics review

Reviewer role: `/root/physics_review`. Ownership: this report, `examples/v19_physics_review.py`, and `physics_validation/`; no edits to either implementation writer's PPL/PPR. This is an independent review of the proposed mechanism and final source, not console certification.

## Scientific baseline and separate experiments

The supplied [Gibbons main paper](../../../tmp/pdfs/Gibbons_2017.txt), journal pages 3034–3038, and [supplement](../../../tmp/pdfs/mrm26971-sup-0001-suppinfo01.txt), S1/S2, establish the following distinct experiments. The [official primary article](https://doi.org/10.1002/mrm.26971) identifies the published source.

| Experiment | Requirements established by supplied source | Unavailable items / limits |
|---|---|---|
| Figure 3 / S2 preparation components | 3000 isochromats, 30-mm z extent; imaging slice 6 mm; ss-MGOT slab 18 mm; initial excitation phase 45°; added z modulation 2 cycles; A before added dephasing, B after, C at preparation endpoint | Sampled complex RF/Gz waveforms, exact compensation timing, and Figure 3 relaxation specification |
| Figure 4 Alsop versus ss-MGOT train | Phases 0°,45°,90°; 2 and 4 dephasing cycles; T1=1300 ms, T2=32 ms; different Le Roux and Busse tailored trains | Exact pulse coefficients and full flip tables are not supplied by main paper/SI |
| S1 ss-MGOT versus nCPMG | nCPMG fixed160° and double phase encoding; ss-MGOT tailored train and different effective ESP; PSF derives from acquisition/signal model | Not a comparison to original/increasing/decreasing/alternating v18 crushers; eight voxel echo amplitudes do not reproduce S1 PSF |
| Scanner adaptation | Actual v18 source and actual companion protocol must define timing, RF libraries, geometry and supported modes | A phase convention, sampled RF/calibration, and verified compiler/event traces are required before played-waveform simulation |

The 76 nominal/46 acquired echoes, 4.20-ms ESP, and 82.9-ms TE appear in the scan-design description. They should not automatically be assigned to every undocumented simulation detail. The scanner protocol supplied by the coordinator for test1e has eight echoes, TE54 ms, ESP14 ms, `rfnum=1`, `rfcal=594`, `p180_scale=185`, ramp200 us, train crusher−2741 DAC and first crusher−5482 DAC, and both crusher durations1000 us. The local scanner companion PPR has two echoes and TE/ESP36 ms. Neither is the reference benchmark.

## Axes and phase derivation

Use the repository rotating-frame convention explicitly: `dM/dt=2π(M×B)`, `m=Mx+iMy`, and free evolution `m→m exp(−i2π A z)` for gradient area A in cycles/m. A +x90° pulse maps +Mz→+My. Consequently, MG is My when the imaging refocusing axis is ±y in this frame.

The proposed paper-to-candidate phase transform is `φcandidate=φpaper−90°`, plus the common existing shot phase. It maps paper preparation90y/refocus180x/tip−90y/reexcite90y/trainαx to relative phases0°/270°/180°/0°/270°. This is a coordinate transformation, not a measured MR Solutions transmitter polarity. Receiver sign and slice-offset phase must be verified with loaded waveforms and vendor frequency/phase behavior.

Independent hard-pulse checks establish:

* ss-MGOT uses the180° RF **axis** with a90° flip: desired +My→+Mz. A0° axis90° re-excitation maps +Mz→+My. Between these events transverse vectors acquire spoiler phase; local Mxy survives while its coherent mean cancels.
* Alsop uses the270° RF axis with a90° flip: My is retained; Mx→−Mz. Using the ss-MGOT180° tip axis would store My instead and implement the wrong mechanism. Finite flip α leaves unwanted transverse Mx proportional to cosα, before subsequent slice-profile/gradient effects.
* Phase invariance does not imply full signal. The spatially varying desired projection contains two complex Fourier branches. Recalling one yields one half of the initial ideal signal; initial phase changes its complex phase. Both methods therefore incur ideal50% signal loss.

The theory section of the paper names MG X while plotted/simulation axes can be rotated. Compare the physical RF axis and component transformation, not just axis labels. Slice-frequency offsets and a common RF phase require the corresponding rotating-frame transformation of these equations.

## First crusher versus repeated crusher contract

Let D be the complete **added preparation dephasing** in cycles/m, C the ordinary imaging crusher area, and `m=i f(z)` the ideal preparation endpoint, where real f contains Fourier components at ±D. For a180° RF around−y, `m→−m*`.

With separate moments, the first RF has precrusher C and postcrusher C+D. This leaves `mADC=i f(z) exp(−i2πDz)` and recalls one Fourier branch. Following each ADC, a−D restoration returns `i f(z)` before the next ordinary crusher C. Thus restoration−D plus the **next** ordinary precrusher C can be fused into later precrusher C−D, while postcrusher remains C+D.

The first RF does not have an earlier ADC restoration. Applying C−D before the first RF and C+D afterwards gives effective2D and moves the initial±D branches to nonzero harmonics. The included ideal counterexample then gives a vanishing first coherent echo. This is a finding about the stated initial modulation and instantaneous RF model; a finite selective re-excitation may introduce a different spatial phase that changes the first-event contract. Such phase must be measured, not inferred from the schematic.

An alternative symmetric first pair C−R/C+R requires `2R=D` for that same initial modulation. It is not interchangeable with the later restoration convention. Therefore a uniform `C−D/C+D` prescription needs explicit definitions and a special first-event or compensated-RF treatment. Both writers were informed before integration.

Positive and negative recall can select conjugate branches; the receiver must track the chosen complex sign/phase. Ordinary crusher cancellation, added modulation, slab-select refocusing, and diffusion lobes remain separate quantities. The presence of other gradients and finite-angle RF means a single-path scalar b-value cannot establish equal effective diffusion weighting.

## Reproducible independent ideal study

Run `python examples/v19_physics_review.py`. Results: [JSON](physics_validation/ideal_mechanism_results.json), [Alsop profiles](physics_validation/alsop_ideal_profiles.png), [ss-MGOT profiles](physics_validation/ss_mgot_ideal_profiles.png); compressed numerical signed profiles are adjacent `.npz` files.

This study uses3000 z samples over30 mm, ideal box masks of6-mm imaging slice and18-mm ss-MGOT slab, and an ideal10-mm ss-MGOT tip mask. A mask is not a selective RF waveform. It uses zero-duration gradient moments, exact hard rotations, no relaxation, no molecular diffusion, and eight toy16-ms echo intervals with a chosen one-cycle ordinary crusher. It does **not** reproduce Figure3/4/S1, any PPL timing, or any actual ADC sample. The deliberate idealization isolates the axis/recall mechanism.

The36 cases cover both methods, initial phases0°/45°/90°, nominal/reduced0.8 B1, and B0−128/0/+128 Hz. The B0 range is motivated by the published water passband±128 Hz, but the ideal study only tests phase accrual/rephasing; it says nothing about spectral-spatial transfer fidelity. Both nominal ideal methods give0.5 coherent magnitude at every toy echo within1e−12, independently of initial phase. Reduced-B1 behavior is recorded without an acceptance claim. No local transverse state is artificially set to zero.

Signed profiles include A, B, after tip, after spoiler/re-excitation where applicable, preparation endpoint **before** leading crusher, literal pre-RF **after** crusher, and first/second/final toy echo centers. Local y=0 and coherent y-average are plotted separately. The known crusher rotates My into Mx between the two pre-imaging landmarks; the explicit complex rotation predicts the second landmark within1e−12. It must not be scored as preparation leakage.

Independent verification includes a scalar Fourier half-signal identity versus vector evolution,3000/64 versus6000/128 spatial convergence, and continuous `solve_ivp` Bloch evolution versus independent matrix exponentials for uniform rectangular RF at128 Hz and both B1 values. An RK4 step study at20/10/5 us converges. These rectangular pulses verify the mathematical rotation engine only; they are not the Gibbons RF coefficients, published-pulse RF convergence, or sampled PPL RF validation. There is no real ADC in the ideal study; reading a toy echo state is not an independent snapshot/ADC agreement test.

## Final source-review status

The newly uploaded `scanner/utilities` supersedes the earlier missing-vendor-library condition: actual RF/gradient libraries and `tstex_15.pph` are present. Source implementation is being revised against these inputs. Final integrated PPL/PPR review remains pending those revisions. Compiler/event-trace verification, Gibbons benchmark reproduction, physical RF calibration, console timing and scanner verification cannot be claimed from the ideal checks above.

## Independent inspection of actual vendor bytes and finite RF

Run `python examples/v19_physics_review.py --vendor-only`. [Independent decode results](physics_validation/vendor_independent_decode.json) and [finite transfer matrices](physics_validation/baseline_decoded_rf_transfer.npz) now use supplied binary `rfstd44.seq`/`g3040_15.seq`, independently reading offsets and raw records rather than calling the coordinator's decoder. All16 RF frames and14 gradient frames match the coordinator's independently developed decoder at the raw-record/dwell level.

An external formula oracle is particularly useful: the `3lobe_sinc_3kHz` frame's666 interior amplitude samples exactly equal rounded `2047*sinc((j−333)*2π/333)` for j0…665. Its amplitude is signed12-bit two's complement under RF control bits. Its complete frame has668 two-microsecond records, including two guard zeros:1336 us total, while the PPL's `NEWSHAPE_MAC` declares1332 us. This4-us difference must be resolved against RF gate/board timing rather than treating metadata as physical sample length. Ordinary phase words0x2000 and terminal0x6000 have identical low phase bits; the terminal control flag is not a180° phase flip.

The gradient ramp shapes are not identical to sampled `linspace` trapezoids. Primary `0_max` has mean16068.94 DAC over50 records and `max_0` mean16698.08. Their combined means are32767.02, so the paired area nearly matches a full peak-times-ramp area under uniform hold sampling. Secondary `0_mx_sec` uses a different sampled ramp and mean16383.5. Exact frame/matrix integration must replace a blanket linear-ramp approximation; MR3040 waiting/hold/instruction semantics still need event mapping.

An isolated **actual baseline waveform** transfer study uses3000 z positions across10 mm, RF axes0/180/270° and B1=1/0.8. The supplied selector arithmetic gives−2741 DAC and−2128672.964… Hz/m using the inherited calibration. The signed RF integral is normalized to90° on resonance for this study; that is an explicit model assumption, not scanner B1 calibration. No post-RF compensation is applied to these raw pulse matrices. An independent continuous piecewise Bloch ODE agrees with exact finite-rotation evolution for18 selected basis/position conditions within1e−9. These checks establish the math and decoded baseline shape, **not** new-method transfer acceptance or PPL-to-events fidelity.

The `hypsec` AP frames expose a distinct unresolved encoding question. Their amplitude matches the embedded sech expression, but the second word's low bits do not reproduce the stated complex phase under a4096-count-per-turn linear conversion. For example, at j252 the desired phase is−0.0039989 rad, predicting4093 counts, while the stored low word is3993; a4000-count-per-turn hypothesis also fails. The manual does not specify this AP conversion. Arbitrary complex spectral-spatial RF cannot be encoded by guessing this transform. Real-waveform record round trips and signed-amplitude checks do not certify AP hardware phase.

The published-pulse design agent's longer research spectral-spatial candidate is separately checked by `python examples/v19_physics_review.py --candidate-ode-only`: sampled CSV fields are centered four-microsecond rectangles in tesla and tesla/m, gamma42.576 MHz/T, with no fitted phase/compensation. [Independent ODE matrices](physics_validation/candidate_long_independent_ode.json) compare continuous piecewise evolution to independent matrix exponentials. This is a research candidate, not an installed scanner waveform or proof of transverse-to-longitudinal storage.
