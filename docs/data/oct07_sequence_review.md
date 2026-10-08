# October 7 sequence review: intended behavior and evidence limits

Read-only review of the sequence inputs, completed 2026-10-07. This memo supports the scan report; it does not diagnose hardware from source alone. No sequence or protocol was changed.

## The two methods

**v1.91 is ss-MGOT; v1.92 is Alsop.** Both first create a diffusion-prepared spin echo and add a spatial phase pattern, D, across the slice. The useful signal becomes one of two spatial harmonics. The recall gradient brings one harmonic back into phase at the receiver, while the opposite lobe restores its pattern before the next refocusing pulse. This intentionally retains about half the original coherent signal under ideal pulses. Finite pulse profiles and relaxation add further losses.

ss-MGOT tips the selected transverse component onto the longitudinal axis, where it can be stored, spoils the component left transverse, and re-excites the stored component. Alsop uses a 90° elimination pulse parallel to the refocusing axis: it keeps the wanted transverse component and moves the unwanted component onto the longitudinal axis. Alsop does not contain the ss-MGOT storage/spoiler/re-excitation block. In the repository coordinates the RF axes are preparation 90° at 0°, preparation 180° at 270°, ss-MGOT tip-up at 180° and re-excitation at 0°, or Alsop elimination at 270°; imaging refocusing is at 270° plus the inherited phase correction. These are relative phases, and physical transmitter polarity has not been established from the stored data.

Evidence: [implementation_report.md](../v19/implementation_report.md), lines 50–69 and 112–125; [reference_rf.md](../v19/reference_rf.md), section “Axis derivation and ideal signal cost”; the actual v191 method block is in [the workspace PPL](../../scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl), around lines 4900–5135. Those documentation passages describe the design, rather than a measured hardware trace.

## What the October 7 protocols request

The method protocols request `v19_on=1`, two D cycles, `rfcal=594`, negative train crusher −8223 DAC, first diffusion crusher −5482 DAC, TE 54 ms, ESP 14 ms, δ 4 ms, Δ 40 ms, and an x/read diffusion direction. The refocusing schedule is 142.2°, 94.9°, 69.2°, 63.0°, 60.2°, then 60° for the remaining echoes. ETL is either 8 or 16. The v18 controls instead use their original RF train, including `p180_scale=185`, which corresponds to approximately 166.5° under the inferred linear calibration model.

The method path calculates its own RF multipliers. It ignores `alpha`, `p180_scale` and the inherited pulse selection `rfnum`; listing those PPR values without their method-specific meaning would imply a false match between v18 and v19. At `rfcal=594`, nominal preparation 90°/180° multipliers are 204/683; tip/elimination is 223; ss-MGOT re-excitation is 320; the 180° imaging frame reference is 640 before applying the requested flip schedule. These numbers are requested board settings, not measured flip angles. Six custom RF files are required.

Evidence: [rf_install_calibration.md](../v19/rf_install_calibration.md), lines 20–29 and 44–52; v191 source lines 2196–2206 and 2314–2316; for example [test2c PPR](../../experiments/FSE-DWI_10-07-2026_v191_test2c/FSE-DWI_10-07-2026_v191_test2c.ppr), lines 349–363.

The ss-MGOT preparation slab is 3× the requested slice width, and its tip-up width is 1.667×. Alsop prepares and eliminates at the imaging slice width. Here the requested imaging slice is 1 mm: the 18/10/6-mm widths in the RF-design reference describe a different geometry. The method computes selectors from the actual protocol gradient and exact pulse bandwidth; it does not use v18’s 71% bandwidth override. Slice profile and RF waveforms therefore differ between the control and methods.

The acquired MRD-embedded protocol is authoritative for phase-gradient calibration. All ETL8 scans (test0, test1, test2 and test3) embed `gp_init_var=-1000` and `SMY=0.0305406`; all ETL16 scans (test1b, test2b, test2c, test3b, test3c and test3d) embed −1059 and 0.0323371 despite an unchanged nominal 35-mm FOV tag. Thus ETL8→ETL16 includes a phase-gradient calibration change, but test2b→test2c and test3b→test3c do not. The adjacent PPRs for test1b, test2c and test3b are stale for these two fields: they contain −1000/0.0305406 while their MRDs embed −1059/0.0323371. Test3c and test3d have identical embedded protocol/scanner records except acquisition counter; this is a useful repeat comparison, but does not prove every hardware condition was identical. Evidence: [October 7 catalog](../../experiments/scan_catalog_2026-10-07.md), main table and “Metadata details that affect comparisons”; [protocol audit](oct07_protocol_audit.md).

## Timing: the 54-ms TE tag has different meanings

For v18, TE 54 ms locates the first image echo. In the new methods it locates the preparation endpoint. The intended first image echo is 68 ms for Alsop and approximately 73.716 ms for ss-MGOT. Subsequent echoes add 14 ms each. For ETL 16 this gives final echo times of approximately 278 ms and 283.716 ms, compared with v18’s 264 ms. PE order 1 puts the central phase-encode region in the early echoes.

The extra elapsed ss-MGOT interval includes longitudinal storage, during which the selected magnetization relaxes mainly by T1 rather than T2. It would be incorrect to predict its entire extra-time penalty with a simple T2 exponential. A low-angle train also mixes spin and stimulated echoes, so the physical acquisition time is not automatically the contrast-equivalent TE.

Evidence: [README.md](../v19/README.md), timing table near lines 86–90 and difference list at lines 143–147; v192 source lines 2365–2372; v191 source timing construction around lines 2350–2440. These are design/source-model times, not newly measured scanner timings.

## Expected signatures, without mistaking them for proof

The design predicts a lower initial signal than a conventional near-180° v18 train. Its purpose is to preserve a more stable echo train when diffusion produces an unfavorable initial magnetization phase. The stored nominal eight-echo Bloch model predicts ss-MGOT coherent amplitude around 0.39 at echo 1 and 0.33 at echo 8, and Alsop approximately 0.29–0.30 at echo 1 and 0.24–0.26 at echo 8. Those are fractions of a perfectly refocused full slice, not predicted scanner intensity units. ss-MGOT is the more phase-invariant modeled adaptation, while Alsop has greater off-resonance sensitivity. The two custom adaptations do not reproduce the published RF design exactly; the tip-up is spatial water RF rather than the spectral-spatial tip-up and does not provide the reference fat suppression.

Those simulations are for a specific eight-echo, central-slice protocol and inferred calibration. The paper-geometry 76-echo benchmark is a separate experiment. Neither benchmark proves that today’s ETL16 acquisition has the same behavior or that an image will have the corresponding point-spread function. An acquired ETL16 data set is the appropriate evidence for ETL16 performance.

Evidence: [README.md](../v19/README.md), lines 103–119 and 150–165; [rf_install_calibration.md](../v19/rf_install_calibration.md), lines 55–58; [bloch_results.json](../v19/event_validation/bloch_results.json).

The navigator is one full unencoded echo train, followed by the encoded imaging trains. The method navigator executes the same preparation and RF train as the image shots, with phase encoding suppressed. The method has no deliberate odd/even navigator RF phase alternation. Receiver phase and RF phase correction retain the inherited source logic. A strongly alternating or incoherent raw navigator therefore cannot be called an intentional feature merely because the sequence is new. Finite RF profiles and unwanted coherence pathways can still cause physical phase changes. Reconstruction ablations are needed to determine whether applying a single navigator phase/envelope to all imaging shots helps or harms the image.

Evidence: v191 source lines 2937–2940, 3020–3021, 4810–4812 and 5055–5124. PE1/6/7 table construction is inherited, with PE6 reversing PE1’s echo assignment and PE7 interleaving negative-to-positive phase encodes. [bare_bones_recon_fse.py](../../scanner/recon/bare_bones_recon_fse.py), lines 148–168, implements these same mappings. Every October 7 protocol requests PE1.

## Diffusion and crushers

A nominal b value labels the requested diffusion pair. The total diffusion weighting also contains crushers, slice selectors, recall lobes and cross terms. In the stored model, the method’s nominal b0 first echo has trace about 20 s/mm², rising to about 102–103 by echo 8. At nominal b1000 the method trace is about 1014–1015 at echo 1 and 1096–1097 at echo 8; at nominal b6000 it is about 5982 and 6064. The historical original-crusher v18 control instead has about 1175/6394 at its first echo for nominal b1000/b6000. Its read prephaser sits between the diffusion lobes and adds cross terms.

These are historical modeled values, rather than actual measured b-tensors today. October 7’s stronger-crusher v18 control differs from the historical original-crusher v18 input. Comparisons should retain nominal b labels and avoid treating them as exactly equivalent effective diffusion weighting. The late-echo weighting and low-angle pathways complicate a single quantitative ADC fit even before imaging artifacts are considered.

Crushers are gradients intended to dephase unwanted signal pathways. Larger amplitude does not universally improve an echo train: a stray pathway can accidentally rephase when crusher and recall areas coincide. The current design restricts negative crusher polarity, two D cycles, and narrow area ratios |C|/|D|≈3.83 and |C1|/|D|≈2.55 because these were explicitly simulated. The method’s larger train crusher is deliberate. A signal collapse could arise from RF calibration, timing, RF phase polarity, selector/rephaser mismatch or stray pathways; it cannot uniquely identify one of these from a magnitude image.

Evidence: [btensor.json](../v19/event_validation/btensor.json); [README.md](../v19/README.md), lines 128–136 and 168–170; v191 source ratio guards around lines 2240–2255.

## Critical provenance mismatch found during this review

The two workspace PPL files are byte-exact sixth-trial RF-fix v6 files, while the seventh-trial method-only zip and latest event-validation ledger record different bytes:

| Method | Workspace SHA-256 | v7 zip / event-validation SHA-256 |
|---|---|---|
| v191 | `92bdcb79081087c29dd045cd797cb8fbdd1e4f02ff4f341b9711eef706f16e4f` | `6a0d222b6c8689fbdee5f4ae412c4d5df0bea10a7da99a309fabf5dfab04d828` |
| v192 | `373d10d4952a466eccec75aab0c60e94a7abc6d19767502211f145e8d5061803` | `0adcd5ada3eb156e869cdee1eea045acdb1dc2ac966bfc563599d72396ea1843` |

This is not a CRLF/LF difference: normalizing CRLF to LF still leaves different contents. The workspace retains 512-row diffusion tables, a 1024-entry crusher table, enabled rejected features, the v18 control path and old TE/kernel blocks. The v7 zip reduces those arrays to 64/64, compiles the rejected features out, removes the old kernel and requires `v19_on=1` before reading a table. PPL byte lengths are 206516/201359 in the workspace versus 168659/163502 in the v7 zip. The October 7 method PPRs declare 64-row diffusion arrays, consistent with the method-only protocol format.

Direct zip comparisons also confirm that the workspace PPLs equal the v6 RF-fix zip payloads byte for byte. Both workspace scanner PPRs and all six workspace RF libraries equal their v7 zip payloads byte for byte. Thus the mismatch is specifically between PPL builds; there is no corresponding local RF sample-file mismatch. This does not identify which copies existed on the scanner.

Evidence: [rf_viewer_results.json](../v19/compiler_compatibility/rf_viewer_results.json), lines 26–28, lists the workspace hashes; [method_only_results.json](../v19/compiler_compatibility/method_only_results.json), lines 14–22 and 63–70, lists the v7 changes and hashes; [summary.json](../v19/event_validation/summary.json), lines 11 and 118, records the v7 validation hashes; exact bytes were read directly from [v19_method_only_v7.zip](../v19/compiler_compatibility/v19_method_only_v7.zip) and compared with the workspace.

The documented equivalence test compared 47 protocols per method and found the intended method RF, gradients, ADC timing and outputs equal between v6 and v7, except identified reporting/control-path changes. That supports preservation of the intended method in the local mapping model. It does not prove an identical vendor executable or its real timing. The documented 64K image-overflow assessment is an estimated explanation of earlier simulator errors, not a measured root cause of today’s acquisitions.

No October 7 scan folder supplies the compiled scanner executable or a hash of the console-side PPL and RF assets. Thus the images can establish performance of the acquired data under the named protocols, but this repository cannot identify the exact compiled program or installed RF samples that produced them. Do not claim the mismatch proves the old build ran, and do not claim the v7 source validation hardware-validated today’s build. Preserve both versions and their hashes for later traceability.

Several documentation status/control passages predate the method-only revision and the user’s acquisition. In particular, old `v19_on=0` control instructions are superseded by the v7 requirement to run controls on the unchanged v18 PPL. Statements that nothing had been deployed describe the earlier documentation session; they should not be repeated as the status of today’s supplied scanner data.

## Practical interpretation for the report

Judge the new methods against the stronger-crusher v18 controls as well as the original control, report raw and corrected reconstruction behavior, and examine b0 before attributing losses at high b to diffusion. An expected half-signal cost does not explain an anatomically unusable b0 image by itself. Separate what the data show (raw navigator shape and phase, background/artifact levels, image organization, repeat behavior) from plausible causes. RF calibration and a console timing/executable trace are the best discriminating follow-ups, because the PPR’s stock `rfcal` value does not calibrate six new frames. Once the b0 echo train is coherent, intermediate-b repeats can test diffusion attenuation without the high-b magnitude noise floor dominating the comparison.
