# Scan evidence and implementation decisions for v1.81 / v1.911

Investigation date: 2026-10-08. Scope: independent scan-evidence, RF, navigator and loss-mechanism review. This document adds no implementation and makes no scanner-verified claim. The October 4, 5 and 7 analyses already contain independently reconstructed measurements; their quantitative results are used here without rewriting or rerunning scripts that overwrite those historical reports.

## What the acquisitions establish

| Evidence | Supported conclusion | Limit on the inference |
|---|---|---|
| October 4 test3/4/6: increasing then alternating crushers progressively suppress readout-edge high-b bursts; E8/E1 at b1000 falls 0.470 / 0.381 / 0.244 | Crusher schedules change acquired unwanted signal and useful-or-reinforcing late pathways | Increased suppression is not an unconditional signal or image-quality gain; these measurements do not identify the exact unwanted pathway |
| October 5 test1/test1e: sign reversal reduces high-b rim mean 74% and E2 edge excess 92%; b1000 interior changes -0.6% | Negative nonalternating crushers are the strongest acquired polarity choice for these protocols | Sequential single runs permit unrecorded drift; do not extrapolate to arbitrary geometry/area |
| October 5 test2/test2b and custom test6/test7: equal absolute per-echo areas, very different positive/negative burst behavior | Area magnitude alone is insufficient; the signed interaction with other gradients matters | Neither signed total nor absolute total is a substitute for pathway-resolved moments and diffusion weighting |
| October 7 test0/test1: only train crusher changes -5482 to -8223; both have background-level b6000 | Larger train crusher does not show a suppression advantage in this matched v1.8 pair | It reduces b0 interior 6.9%, b1000 3.3% and improves broad homogeneity; the trade-off is real, not uniformly adverse |
| October 7 test1/test2: matched strong-crusher v1.8 / ss-MGOT ETL8 | ss-MGOT is feasible and suppresses high-b object signal; retains 45.5% b0 and 59.8% b1000 interior mean | The intentional preparation selection has an ideal half-signal cost. This static phantom comparison does not demonstrate the anticipated phase/motion robustness |
| October 7 b1000 E8/E1: 0.735 v1.8 versus 0.443 ss-MGOT; ETL16 E16/E1: 0.577 versus 0.232 | ss-MGOT decays appreciably faster in the acquired train | Not a direct T2 measurement and not proof of crusher diffusion as the sole cause |
| October 7 smoothed interior b0 variation: 2.0% v1.8 versus 5.8% ss-MGOT; b1000 2.7% versus 5.6% | ss-MGOT broad shading is greater after normalizing by mean signal | Includes receive sensitivity, specimen structure and residual noise. Does not isolate transmit B1 variation |

Sources: [October 4 report](../physical_scanner_experiments_2026-10-04.md), [October 5 report](../physical_scanner_experiments_2026-10-05.md), [October 7 report](../physical_scanner_experiments_2026-10-07.md), [October 7 catalog](../../experiments/scan_catalog_2026-10-07.md).

High b is a contamination test in the confirmed water phantom. The ss-MGOT first high-b navigator is about 6.8-7.3 raw units, comparable to v1.8's 7.0-7.3 noise-dominated floor. Its larger high-b/b0 ratio mostly reflects smaller b0 signal. A cleaner high-b magnitude image does not establish additional diffusion sensitivity. The v1.92 object-shaped residual is outside this task; its previously established slice-edge mechanism is not a reason to modify v1.92 here.

## Protocol and build provenance

- MRD-embedded protocols take precedence over saved PPRs. October 4 test0 actually used ESP14 despite its saved ESP16; the named scans had 16 imaging lines rather than 128. These cannot isolate a centering or schedule effect against the numbered scans.
- October 7 ETL8 embeds `gp_init_var=-1000`, `SMY=0.0305406`; ETL16 embeds -1059 / 0.0323371. Adjacent PPRs for test1b, test2c and test3b are stale for these values. Treat ETL8/16 as a co-change, and compare b values rather than experiment positions in three- versus seven-b protocols.
- October 7 recorded TX is -195; October 5 is -205. No validated gain-to-B1 conversion is provided. Across-day brightness is not a sequence-only comparison.
- October 7 test1b is a late control, acquired after the seven-b methods. Counter order is test0, test1, test2, test3, test2b, test3b, test2c, test3c, test1b, test3d. Counters support elapsed time rather than civil timestamps.
- Current workspace v1.91 PPL is the v6 build (SHA-256 `92bdcb79081087c29dd045cd797cb8fbdd1e4f02ff4f341b9711eef706f16e4f`); the v7 zip PPL is `6a0d222b6c8689fbdee5f4ae412c4d5df0bea10a7da99a309fabf5dfab04d828`. v7 removes the old kernel and disabled feature paths, uses 64-row diffusion/crusher tables, and requires method mode before table access. Start the new method from v7.
- Local PPR/RF bytes match the v7 package. Intended method events were compared between v6/v7 in 47 protocols per method. That is source-model equivalence, not proof of identical console compilation or physical play.
- No scan supplies a console executable hash or physical timing trace. Historical RF documentation saying nothing had been installed predates the actual acquisitions. Preserve its calibration caveats but do not repeat the stale deployment status or v7-incompatible `v19_on=0` control instructions.

Sources: [sequence/provenance review](../data/oct07_sequence_review.md), [method-only v7 archive](../v19/compiler_compatibility/v19_method_only_v7.zip), [v19 README](../v19/README.md).

## Echo-train decay: what a diffusion-capable model must resolve

Low-angle ss-MGOT trains intentionally use stimulated pathways. Spatially modulated longitudinal magnetization can still attenuate by molecular diffusion while stored. Repeated large crushers can produce considerable pathway-specific diffusion weighting even when the desired echo's final gradient moment is zero. The relevant quantity is the integral of squared phase wavevector through time, including its stored spatial modulation, rather than just the final refocusing moment. Gradient area preserved at RF/ADC landmarks does not preserve this integral or motion sensitivity if lobe timing changes.

The existing primary-path b-tensor increases by about 82 s/mm² from echo 1 to 8 in the historical ss-MGOT model. At the descriptive October 7 slope 0.00187 mm²/s, that alone predicts a retention factor `exp(-82*0.00187)=0.858`. The nominal nonrelaxing finite-RF model gives E8/E1 `0.334/0.387=0.863`; the acquired b1000 ratio is 0.443. These are useful scales, not a fitted decomposition: the acquisitions and stored model differ in specimen relaxation, RF calibration, build provenance and pathway weighting. T2/T1 effects and B1/B0 variation could account for a substantial part of the gap.

For a timing-only comparison, `-(E8-E1)/ln(S8/S1)` at 14-ms ESP gives apparent decay constants about 120 ms ss-MGOT and 318 ms v1.8. ETL16 gives about 144 and 382 ms. These are envelope diagnostics, not measured tissue/phantom T2 values. They should not be used to set a diffusion correction or RF schedule.

The repository's [event-driven Bloch implementation](../../dwfse/ppl/bloch.py) includes T1/T2, B1/B0 and latency but no molecular diffusion. It therefore cannot verify that a crusher change improves stimulated-pathway diffusion loss. [Exact pathway enumeration](../../dwfse/pathways.py) includes diffusion but currently accepts one non-ADC excitation followed only by refocusing intervals and at most eight acquired echoes. It rejects the multi-RF ss-MGOT preparation and ETL16 directly. [MRzero EPG frontend](../../dwfse/epg.py) uses instantaneous RF and lacks selective slice profiles. A documented mapping/extension is needed; silently applying the v1.8 enumerator to the method is not valid.

Required local verification for any crusher/ESP change:

1. Preserve all pathway gradient transfers at each RF boundary and ADC, with a special first-imaging-echo contract. Independently check C/D and C1/D, including integer rounding and ramps.
2. Include both transverse and stored spatial harmonics in the diffusion EPG model; verify zero-diffusion closure against the non-diffusive model and an analytic diffusion attenuation case.
3. Sweep water-like diffusivities and plausible measured-later T1/T2 separately. Report diffusion-on / diffusion-off changes without claiming unknown phantom constants are measured.
4. Retain finite selective-RF Bloch B1/B0/initial-phase checks. A hard-pulse EPG alone cannot exclude increased slice-edge leakage.
5. Re-run coincidence searches before reducing crushers. The current method's narrow validated ratios are |C|/|D|≈3.83 and |C1|/|D|≈2.55; stronger or weaker is not monotonically safer.

These principles are supported by the original [ss-MGOT paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC6312718/) (whose cited phase-behavior simulation explicitly omitted diffusion), [diffusion modeling with butterfly gradients](https://pmc.ncbi.nlm.nih.gov/articles/PMC4312915/), and [slice-selective EPG formulation](https://pmc.ncbi.nlm.nih.gov/articles/PMC8485742/). The specific explanation of this scanner's excess decay remains an inference requiring the checks above.

## Refocusing spatial width is distinct from RF duration

The strong physics case is to refocus a spatial slab wider than the excited slice, so the excitation transition band lies within a more complete refocusing passband. The user-suggested factor 1.2-1.5 should be assessed as a **selected spatial width ratio**. Merely making the same-TBW pulse 1.2-1.5 times longer lowers its bandwidth; at fixed slice gradient it selects a narrower slice, which can worsen excitation/refocusing overlap.

For a fixed waveform, selected width is proportional to `RF bandwidth / |Gz|`. A 1.2-1.5 wider refocusing slab corresponds to |Gz| about 0.833-0.667 of excitation selection, with RF amplitude and duration unchanged. This introduces no RF-energy increase by itself. It does require separate refocusing selector matrices, recalculated gradient ramp/compensation areas, and correct slice-frequency offsets; changing the shared excitation selector is wrong. In coupled-crusher mode, changing that selector also changes crusher moment, so that mode cannot be claimed equivalent without separate analysis.

The [v1.8 source](../../scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl) uses the same `rfnum` and `tsel180=tsel90`, and one `gs_var_rescale` for excitation and refocusing. It also applies the inherited 71% bandwidth convention in 2D. Do not assume the 71% correction is a measured refocusing passband or alter it globally as an incidental cleanup. The decoded stock pulse has 668 two-microsecond records including guards (1336 µs) while source metadata declares 1332 µs; use actual gated waveform events, not metadata alone.

Changing duration at fixed flip generally reduces ideal RF energy if peak amplitude is reduced accordingly, but trades bandwidth/gradient amplitude and timing. Changing TBW at fixed duration to broaden bandwidth can demand additional peak B1/energy. Neither should be described simply as 'wider RF improves edges.' Prefer the unchanged-waveform, independent-refocusing-gradient candidate because it can be assessed with the supplied library and existing event/Bloch tools.

The benefit is strongly motivated; the exact optimum factor is not established. Test 1.2 and 1.5 spatial ratios with finite pulse profiles and full train moment checks before choosing. If source-player handling of independent selector matrices, offsets or pulse waits cannot be established, ask the user rather than relegating this to a marginal proposal.

## RF calibration, power and SAR

- `rfcal=594` is a stock-pulse calibration reference, not independent calibration of the six custom frames. Method branches ignore legacy `alpha` and `p180_scale`. The inferred stock `p180_scale=185` corresponds to about 166.5°, not a verified physical 180°.
- The custom prep180 has modeled peak B1 22.48 µT; imaging180 21.06 µT at nominal 180° before per-echo scaling. The documented comparison is about 3× and 1.1× stock peak B1. These are inferred physical values, not measured amplifier/coil output.
- RF integral normalization does not guarantee full-slice refocusing. The nominal custom imaging frame has reported maximum full-basis edge error 1.149; prep180 error 0.339. The imaging/re-excitation low-TBW Hamming pulses have broad transitions. Central flip calibration alone cannot settle shading or slice-edge behavior.
- Relative energy can be calculated reproducibly from decoded samples and board multipliers: sum over pulses of `dt * sum(B1_sample²)`. Report peak multiplier, RF duty, pulses per shot and average energy/TR, including preparation, navigators and dummies. Such a relative calculation is not a SAR certification.
- Absolute RF/SAR and coil/amplifier limits are absent. Increasing flip, changing RF duration/TBW or adding navigator refocusing pulses requires these physical checks. A pure refocusing selector-gradient change retains RF energy but still requires spatial-profile and gradient validation.
- A mild v1.8 VFA train offers plausible SAR reduction, but it creates more stimulated pathways and can worsen sensitivity to diffusion-induced initial phase. Existing v1.8 phase/B1 failures make automatic adoption unjustified. Retain fixed flip unless a full phase/B1/B0 and diffusion-pathway comparison demonstrates benefit.

Source: [RF calibration notes](../v19/rf_install_calibration.md), [finite-RF contract](../v19/reference_rf.md), [independent RF decoding/review](../v19/physics_review.md). **scanner-verify:** achieved flip/relative phase, B1 mapping if available, sample-specific T1/T2, RF power calibration and applicable coil/amplifier/SAR limits.

## Navigator: high-value work requiring an acquisition contract

The current navigator is one complete ky=0 train in a separate shot, preceding image shots. v1.8 source builds an initial `views_per_seg` zero-PE table; [reconstruction](../../scanner/recon/bare_bones_recon_fse.py) removes exactly that initial train and uses it for all imaging shots. It cannot measure the diffusion phase of each later shot. The current phase estimator sums read samples, selecting a spatial-projection location; it is not a full spatial phase map. October 4 spatial-profile residuals and October 7 correction ablations show why one scalar per echo can redistribute image shading without correcting spatially varying errors.

A per-shot ky=0 navigator has a strong physics case for future in-vivo multishot diffusion. It can estimate bulk shot phase and a one-dimensional projection phase; one projection cannot recover arbitrary two-dimensional motion phase, and a weak late navigator may not represent all preceding echoes.

Options for a concrete implementation:

| Option | Expected effect | Required proof |
|---|---|---|
| Append one ky=0 spin echo to every imaging shot (recommended first design to evaluate) | Leaves existing imaging echo indices/contrast assignment intact; obtains same-shot phase | Additional refocusing/ADC line storage, PE rewind, useful late navigator SNR and phase relation, RF energy/TR budget |
| Prepend a ky=0 navigator | Stronger earlier phase measurement | Delays/reassigns every imaging echo, changes first imaging flip/pathway and TE, requires revised raw layout and image mapping |
| Add a second ADC within an existing half-spacing | Potentially less RF cost | Requires a separate read-gradient rewind and timing space; 6.4-ms readout leaves little spare time and directly conflicts with shortest ESP |

Do not silently insert lines while preserving `no_views` metadata: current MRD/reconstruction assumptions would mix navigator and imaging lines or misreshape data. Acquisition and reconstruction need a versioned line-order/count contract and synthetic-data round-trip checks. A separate one-shot navigator reference still remains useful for echo-envelope characterization, but is not a replacement for shot-phase data.

### Questions to ask the user before this beneficial change is sidelined

1. **Per-shot navigator storage:** A same-shot ky=0 echo would address phase errors the present reference shot cannot measure. Can the console store one additional ADC line per imaging shot with explicit line tags, or with a documented custom raw-line order/count? Is compatibility with the existing MRD reader mandatory? Recommended first candidate is an appended navigator, with a leading navigator as the higher-signal/higher-TE alternative. A vendor example of multiple ADC records per shot or a documented view-counter/storage contract resolves the implementation uncertainty. This is an architecture question; the user cannot perform a fresh console test during this session.
2. **RF/gradient limits:** Independent spatial refocusing widening and shorter ESP have strong rationale, but any new waveform must meet physical axis and RF limits. Can the user supply the configured per-axis maximum gradient/slew and RF/coil/amplifier limits or their console configuration? Retain current conservative validated limits where explicitly supported; do not invent limits from DAC range. Configuration documentation is enough to assess the local candidate; eventual compilation/timing and RF checks remain scanner-verify.
3. **Meaning of refocusing width if still ambiguous:** Recommend 1.2-1.5 times wider **spatial selected slab**, retaining the existing waveform/duration and reducing only refocusing Gz. If the request instead requires longer RF duration, obtain that preference explicitly because the bandwidth, slice profile and minimum-ESP consequences differ. The independent finite-RF profile/moment comparison can continue while the answer is pending.

## Decisions supported by this investigation

**Prioritize and locally validate:** preserve negative nonalternating crusher polarity; move v1.8's read prephaser outside diffusion encoding to eliminate known cross-terms; independently widen the refocusing spatial slab; fix physical/isodelay and ledger deadline defects; shorten ESP only after complete moment/pathway, hardware and instruction-budget proofs; pursue a same-shot navigator contract rather than call its benefit marginal.

**Conditional on new diffusion/pathway evidence:** reducing method crusher strength, changing C/D ratios, shortening storage/preparation or δ/Δ. These can help but also create harmful coincidences, alter nominal/effective diffusion weighting or RF selection, and must retain feasible maximum b under real gradient limits. Re-run the coincidence analysis whenever crushers change. Shortening δ/Δ at fixed b increases required gradient amplitude; do not assume spare DAC implies hardware headroom.

**Decline for this conservative revision without stronger evidence:** a new global crusher schedule, automatic positive/alternating polarity, PE6/PE7 as an image-quality fix, mild VFA solely for an unmeasured SAR problem, and new complex/spectral-spatial RF encoding. These benefits are uncertain or their necessary RF encoding/calibration is absent. The ss-MGOT spatial water tip remains an explicit adaptation, not an exact published spectral-spatial implementation.

**Scanner test priorities:** first record exact PPL/PPR/RF/executable hashes and vendor compile/listing; measure played gradient/RF/ADC timing and gradient lag/isodelays; calibrate RF and verify RF/gradient limits; acquire matched b0/low-b constant-geometry controls with measured relaxation; compare unchanged versus shortened ESP and spatially widened refocusing; then test crusher diffusion/phase robustness and a navigator-enabled raw-layout round trip. Include return-to-baseline acquisitions, fixed gains/geometry, noise references and raw complex signals. None of these tests has been performed for v1.81/v1.911 in this investigation.
