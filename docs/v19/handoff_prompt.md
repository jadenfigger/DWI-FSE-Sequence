You are the coordinating MRI pulse-sequence coding engineer taking over an interrupted implementation. Continue the work below from the actual saved repository state. Do not restart the literature research or claim the current drafts are finished. The user wants concrete MR Solutions PPL implementations, not only Python/Pulseq models, and has authorized careful inference using the available scanner files. Work efficiently, prioritize the critical implementation and review path, and finish everything supported by the inputs.

## Objective and original requirements

Repository (Windows/PowerShell):
`C:\Miscellaneous\Coding_Projects\Python\mri_processing\processing\DWI-FSE-Sequence`

Preserve actual v18 unchanged. Finish these new sequences with matching PPRs and required native RF assets:

- `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl`: v191, Gibbons ss-MGOT mechanism.
- `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.92.ppl`: v192, Alsop mechanism.

Read the complete original user request, which is preserved at:
`C:\Users\jaden\.codex\attachments\50b21090-d1e5-4a33-b139-cf27407fd4ac\Pasted text.txt`.
That request defines the full deliverables, branch audit, RF fidelity, scientific benchmarks, validation landmarks and independent review requirements. This handoff supplements it; it does not reduce its scope.

Use distinct implementation and independent-review agents when available: reference/RF design, v191 writer, v192 writer, independent PPL reviewer, independent physics reviewer. Avoid shared-file concurrent edits. Writers must not solely approve their own changes. Both reviewers must inspect the final integrated PPL/PPR/assets after corrections. Report actual agent use and any unavailable capability honestly.

Do not deploy to the scanner or overwrite scanner libraries. Preserve unrelated existing changes; this workspace had numerous modified/untracked research artifacts before this task.

## User decisions: do not ask again for unavailable tools

The user uploaded actual scanner libraries and includes. Their location is **`scanner/utilities`**, not `experiments/utilities` as initially stated. They cannot supply compiler/simulator event exports, calibrated hardware limits/delays, or executable tools. They explicitly said to infer/inspect what is available and continue if there is a strong technical basis. Do not repeatedly request those inputs or use their absence to avoid supported source work. Keep compilation, physical timing/calibration and scanner verification explicitly unverified.

The user subsequently asked to hurry, then requested this handoff. No final new-method implementation or validation approval was achieved.

## Verified baseline

Actual local v18 PPL SHA-256:
`3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2`

Actual companion `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppr` SHA-256:
`78c9845d090183d59cba956f36305e0e19d4a8dcdb3ae707062839159fd904da`

Both hashes were rechecked immediately before this handoff. Do not reconstruct from acquisition metadata or substitute v17. Historical October 5 acquisition PPRs identify `G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl`; the local source is supplied, but acquisition-time byte identity has no independent hash attestation.

The local companion is **two echoes, TE/ESP36ms**, not the eight-echo adaptation. An actual eight-echo control is:
`experiments/FSE-DWI_10-05-2026_v18_test1e/FSE-DWI_10-05-2026_v18_test1.ppr`
(reused filename). Settings include ETL8, no_views136, first TE54ms, ESP14ms, rfnum1, rfcal594, p180_scale185, ramp200us, imaging crusher−2741DAC, first diffusion crusher−5482DAC, both crusher durations1000us, PE_order1. Verify all protocol records rather than relying only on this summary.

## Saved implementation state: important limitations

Inspect actual files and builders before making changes. Builders are unfinished and can overwrite newer manually edited PPLs. Do not blindly run them.

- **v191 PPL is still an intentionally blocked v18 reservation**, with `SS-MGOT MECHANISM NOT IMPLEMENTED` and an unresolved include. Last inspected hash: `9506f8feb989fec09cc1d4a3063a73d5aa63aff7932f50dedef5c726f7b54519`. Its PPR is also a reservation. There is no completed ss-MGOT shot in this PPL.
- `examples/build_v191.py` is an unfinished concrete-source transformation derived from the Alsop draft. It still contains copied `[V192]` annotations, arbitrary200us timing reserves and incomplete method-specific work. Check that it actually implements storage, transverse spoiler, distinct re-excitation, slab selection and correct RF compensation. Renaming Alsop code is not ss-MGOT.
- `scanner/v191_event_helpers.pph` contains verified-interface helper work: actual `LONGDELAY`, RF macros, padded setup windows and validation separation. It is not itself a complete sequence. Some initial helper findings were corrected; inspect the latest bytes and review record.
- **v192 PPL contains concrete but unfinished and uncompiled Alsop source**, a separate method path selected by `alsop_on`, with dephasing, elimination, recall/restoration and imaging-loop changes. Last inspected hash: `540ac8237aee5a1a5ab945045122102d92f176772bfcc14f2c44ae86806410ef`. Final timing fixes and new-RF integration had not been completed/reviewed when interrupted.
- `examples/build_v192.py` remains an older generator and still includes arbitrary200us instruction-reserve subtraction. Its state may lag the PPL. Reconcile source, builder and audits before regenerating.
- No verified full new-PPL-to-event mapper or final event ledger exists. No final played diagrams, full finite-RF preparation/echo comparison, effective-b comparison, compiler validation or scanner validation was completed.
- Some `docs/v19/README.md`, implementation reports and source-audit JSONs describe the earlier blocked reservations. They are stale snapshots, not current completion evidence. Update them after implementation/review.

## Inputs and completed reusable work

Read these first:

- `docs/v19/reference_rf.md`: completed source-linked requirements, primary references, figure-specific benchmarks, RF design provenance and measured errors.
- `docs/v19/ppl_review.md`: independent static review findings, including unfinished implementation defects.
- `docs/v19/physics_review.md`: axes, first-versus-later recall derivation, independent vendor-byte and finite-RF checks.
- `docs/v19/v191_implementation.md`, `v192_implementation.md`: earlier integration contracts; verify against actual current source.
- Original audits: `docs/gibbons_replication_audit.md`, `docs/prepared_fse_comparison.md`, `docs/data/oct05_protocol_audit.md`.
- `scanner/EVO Pulse Sequence Program Manual.pdf`.
- `C:\Users\jaden\Downloads\Gibbons_2017.pdf` and `mrm26971-sup-0001-suppinfo01.pdf`.

`scanner/utilities` contains all six includes, including `tstex_15.pph`, and all eleven linked vendor libraries. The initializer is a pure average/view/slice-block and phase-cycle parameter validator. The files named in `tree_output.txt` are only a listing: `pplc.exe`, `cpp.exe`, `compile.bat`, `specsim.exe`, `waved.exe`, their DLLs/configs are **not actually uploaded**. Do not mistake the listing for installed tools.

`dwfse/vendor_seq.py` is a strict binary WavEd decoder/encoder. All eleven uploaded libraries decode and re-encode byte-identically. It preserves formulas, comments, pointers, raw controls and gradient suffix bytes. `real_rf_frame()` reproduces known real-RF sample/control words and rejects clipping/fractional DAC input. Independent reviewer parsing, without importing this codec, confirmed RFstd44 and gradient raw layouts and samples. This is strong format evidence, **not vendor loader/compiler certification**.

Reproduce/inventory with:

```powershell
python examples/audit_vendor_libraries.py
python examples/audit_v19_inputs.py
python examples/build_v19_rf_library.py
```

The last command builds the shared local research asset:
`scanner/rf/v19_research_rf.seq`
SHA-256 `cca9935e58833c3c61fb5e76cc577659914f5c250cf2449676affd12d088bf5c`.
It has six **real** frames with exact digital-sample readback:
`v19_slrprep90`, `v19_slrprep180`, `v19_slrtip90`, `v19_slrelim90`, `v19_reexc90`, `v19_imaging180`.

Contract/provenance and actual numerical samples are in `docs/v19/reference_rf/real_rf_contract.json`, `.npz`, per-frame CSVs and `real_rf_transfer_results.json`. Binary metadata and inferred calibration factors are in `docs/v19/rf_library_manifest.json`.

All new frames use10us dwell (`wait_ticks=100`). Preparation/tip/elimination frames are320samples/3200us; re-excitation/imaging frames120samples/1200us. Integer PPL nominal bandwidths1109/1283Hz approximate exact1109.375/1283.333Hz; disclose/measure the quantization.

Pulse-specific scale numerators, denominator10000, relative to the supplied stock RF calibrated90-degree signed integral are respectively:
**3436,11509,3761,3761,5392,10783**.
Use the verified vendor `scale(rfcal,numerator,10000)` interface with explicit bounds before playback. These are **inferred linear DAC×board-multiplier calibration**, not measured gain. New nominal180 pulses must not reuse inherited185% scale and be called180 degrees. Under this nominal integral model, old `p180_scale=185` corresponds166.5 degrees.

## RF fidelity: what was measured, what failed

The native asset is a disclosed **water-only spatial approximation**, not Gibbons' spectral-spatial pulse. It includes new SLR spatial pulses and a distinct1.2ms Hamming-window re-excitation. It is not an exact Gibbons coefficient reproduction, and the imaging window was not specified by the paper. Do not claim paper fidelity from these files.

The published spectral-spatial design requires maximum-phase spectral filtering, water±128Hz/fat[−549,−306]Hz, six flyback subpulses,10mm tip target, VERSE on ramps,5.64ms duration,22.6uT RF/22.9mT/m gradient. The author-owned Kerr/Larson toolbox and MATLAB design experiments are saved with pinned provenance. The short candidate exceeded B1; the longer candidate failed required transfer/phase criteria. Neither was installed in the RF asset.

Arbitrary complex AP RF encoding is unresolved. Hypsec's phase words do not follow a simple4096- or4000-count-per-turn mapping. Do not invent a complex waveform encoding from channel titles. The real asset uses only verified realRF controls.

Measured nominal compensated full-basis errors over the reference6mm imaging interval include:

- SLR preparation90: maximum component error~0.0110.
- Area-renormalized SLR preparation180: maximum component error~0.339; scaling the original SLR waveform to nominalπ changed its finite response. This is a substantive limitation, not a validated reference pulse.
- Spatial10mm tip: desired storage0.995503–1 at the correct180-degree RF axis, unwanted quadrature up to0.023879; full-basis max error~0.0917.
- Hamming re-excitation: slice-edge amplitude~0.845 and full-basis max error~0.535.
- Hamming imaging180: full-basis max error~1.149 over the full6mm interval, including edges.
- Water-only tip fails fat suppression. Report actual spectral and spatial phase leakage, not only flip angle/TBW.

Fitted physical pre/post compensation areas are in `real_rf_transfer_results.json`. For the10mm tip, each correction is **−188.78848994cycles/m** at reference geometry, or×6 for the1mm adaptation. These fits exclude separately played ramps and must be translated into actual scheduled gradient moments. They are not automatically implemented by a generic half-selection rephaser.

Independent new-binary parsing and finite basis calculations passed; actual rounded board multipliers at rfcal594 give approximately89.96/179.83/89.83/89.83/89.85/179.70degrees. Inspect `physics_validation/new_disk_rf_independent_results.json`. This does not establish complete PPL mapping.

## Critical physics and PPL findings to resolve

1. In the repository frame, `dM/dt=2π(M×B)`, `Mxy=Mx+iMy`, positive-gradient phase is `exp(−i2πAz)`. Relative phases prep90/refocus180/storage/re-excitation/imaging are0/270/180/0/270degrees, plus the existing phase-cycle offset. Alsop elimination is270degrees, retaining My and moving Mx to−Mz. ss-MGOT storage is180degrees, storing My onMz, followed by coherent transverse spoiling and0-degree re-excitation. Physical transmitter polarity remains inferred.
2. First and later recall boundaries differ. For initial±D modulation, separated first precrusherC/postcrusherC+D recalls one branch; restore−D after ADC. Later restoration−D can fuse with next precrusher to giveC−D, but applyingC−D/C+D to the first RF cancels the ideal desired echo. Include finite RF compensation and receiver phase.
3. Keep preparation endpoint before leading imaging crusher separate from literal pre-RF after crusher. The crusher rotates My intoMx; do not score that known evolution as preparation leakage. Keep local vectors and coherent spatial means separate; never zero local Mxy to model spoiling.
4. RFstd44's baseline3lobe frame has668two-us records, including two guards, versus1332us declared activeRF. Gradient ramps have actual sampled sums, not identical linspace trapezoids: primary rise/fall sums24.5200049/25.4800256 normalized units. Use actual samples and verified hold/continue behavior.
5. Review H1/H2/H3/A2/A3 in `ppl_review.md`. Initial500us setup windows were unsafe around compensated `gettimer` overhead; revised helpers use1000us padding. RF validation must run before timed playback; RF `pred` is vendor-macro-entry-relative. `MR3031_RFSTART` omits externalPDD masks; implement correctly or reject PDD before events.
6. Arbitrary200us instruction reserves were subtracted without realized fixed windows; this is a known timing defect. New scale/branch work outside old empirical timers shifts RF centers. Fix with actual padded scheduling and source-expanded cost/center mapping; an uncompiled disclaimer does not excuse known incorrect arithmetic.
7. Account for final ADC rewind/restoration and TR tails, not only adding oneESP to minTR. Respect5ms timer periods,16-bit narrowing, LONGDELAY≥150us,31-character identifier collisions, inactive-matrix requirements/DSP latency, RF and gradient bounds and every array index.
8. Alsop reference preparation is slice-selective, matching the6mm imaging width; ss-MGOT uses18mm diffusion slab,10mm tip,6mm imaging slice. The same prep coefficients can be reused with the appropriate selector, but do not accidentally give Alsop ss-MGOT's wider slab without declaring that departure. Slab selection must not scale every Gz crusher/recall/diffusion event indiscriminately.
9. Preserve the original method-off control, one read prephaser, PE rewind and supported dummy/nav/multislice loops. Explicitly reject genuinely unsupported method-on combinations before events rather than silently bypassing preparation. Dynamic slice translation of VERSE/flyback RF requires time-varying phase; a constant offset is insufficient. Report any temporary central-slice restrictions.

## Finish and validate

First reconcile saved source/builders and close concrete reviewer defects. Integrate the actual new RF asset/calibration/compensation consistently. Finish genuine ss-MGOT and Alsop paths with informative infeasibility errors and matching deliberate eight-echo PPRs. Do not just remove the v191 gate.

Build an independently checked mapper from the **actual integrated PPL**, expanded vendor macros, real frame samples, lists, matrices, offsets and receiver/ADC operations. Label nominal source estimates separately from compiler-measured physical timing. Produce diagrams/timing tables from that mapping. An independently written Python lookalike is insufficient.

Then run finite-RF/Bloch checks with phases0/45/90degrees, B1nominal/reduced, justifiedB0range, spatial/RF-step convergence and independent solver cross-checks. Include A/B/tip/spoiler/re-excitation/endpoint/post-leading-crusher and first/second/final ADC middle samples, plus actual snapshot/ADC agreement when mapped. Distinguish reference benchmarks Figure3/S2, Figure4 (muscleT1=1300ms,T2=32ms), and S1 nCPMG comparison. Exact original coefficients/full Le Roux/Busse tables remain unavailable; approximations must be quantified and labeled.

Compare adaptation to verified v18 original/increasing/decreasing/alternating signed-crusher controls. Define alternating as polarity alternation with retained magnitude; keep the first diffusion crusher distinct. Report TE, RF train, profile and effective diffusion differences. No image-quality/PSF claim from eight echo magnitudes alone.

Useful reproducible checks:

```powershell
python examples/v19_physics_review.py
python examples/v19_physics_review.py --vendor-only
python examples/v19_physics_review.py --new-rf-only
python examples/v19_physics_review.py --candidate-ode-only
python -m unittest discover -s tests -p test_scanner_timing_review.py -v
python -m unittest discover -s tests -p test_scanner_v17.py -v
```

The existing8+20test suites passed earlier, but cover legacy arithmetic/generator behavior, not new-method compilation or full v18 event fidelity. Older source audits may assume gated reservations and need revision. Do not report them as new-method validation.

Finish with reproducible scripts/results/input hashes, RF loading/calibration instructions, concise source-linked implementation report, independent findings/resolutions and explicit separate statuses: **implemented, compiled, simulated, reviewed, verified on scanner**. Compiler/console stages remain unavailable unless a genuine local capability is discovered. Record the exact final files reviewed. State any unresolved correctness or fidelity issue plainly; do not present an approximate or incomplete implementation as validated.
