# v191 / v192 preparation work: pending scanner inputs

The actual local v18 source and companion parameters have been identified and preserved. **Neither new method is implemented or runnable yet.** The requested filenames currently contain explicit compile/runtime blocks and preserved v18 bodies, rather than unsupported RF substitutions or invented vendor interfaces. These reservations are review artifacts, not deliverable pulse sequences. The user has offered to upload the missing scanner files; the exact request is [upload_checklist.md](upload_checklist.md).

## Status and evidence

| Stage | v191 ss-MGOT | v192 Alsop |
|---|---|---|
| Actual local starting source identified | Yes, supplied v18 | Yes, same supplied v18 |
| Historical October 5 source byte identity | Unconfirmed | Unconfirmed |
| Source-linked method design | [Reference/RF requirements](reference_rf.md), [integration contract](v191_implementation.md) | Same reference requirements, [integration contract](v192_implementation.md) |
| Method implemented in PPL | **No** | **No** |
| Companion PPR | Pointer-only reservation, retains two-echo v18 companion | Pointer-only reservation, retains two-echo v18 companion |
| Compatible new RF assets | Not available | Not available |
| Vendor compiled | No; dependencies/compiler missing | No; dependencies/compiler missing |
| Played event trace verified | No | No |
| Simulated | Independent **ideal mechanism only** | Independent **ideal mechanism only** |
| Reviewed | Static source/gate and design review; implementation approval withheld | Same |
| Verified on scanner | No | No |

Do not remove the gates to use these files. Their removal would expose the unchanged baseline, not implement either preparation. No scanner sequence library was overwritten or deployed.

## Starting-source verification

Local source: `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl`, SHA-256:

`3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2`

Local companion: `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppr`, SHA-256:

`78c9845d090183d59cba956f36305e0e19d4a8dcdb3ae707062839159fd904da`

The companion points to the local v18 filename. The October 5 acquisition PPRs point to `G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl`; that drive is not mounted here. A path/version label does not prove that the local bytes match the acquisition-time source. No v17 substitute was used as the new starting source. The [input audit](input_audit.json) records hashes, recursive lexical include inventory, all vendor library declarations, PDF hashes and acquisition companion paths. Five top-level includes are present; `tstex_15.pph` and all eleven linked waveform libraries are absent.

The earlier [October 5 audit](../data/oct05_protocol_audit.md) described v18 as unavailable at the time. This new local file inventory supersedes that availability statement, while retaining the historical source-identity uncertainty.

## Reference benchmark versus scanner adaptation

The [source-linked requirements table](reference_rf.md) distinguishes Gibbons Figure 3/S2 preparation profiles, Figure 4 Alsop-versus-ss-MGOT echo trains, and S1 ss-MGOT-versus-nCPMG signal/PSF comparisons. Their comparators, relaxation settings, train designs and reconstruction requirements must stay separate. Primary sources are [Gibbons et al.](https://doi.org/10.1002/mrm.26971), [Alsop](https://doi.org/10.1002/mrm.1910380404), and the primary RF/train references linked in that table.

| Protocol identity | Echo count | Timing | Use here |
|---|---:|---|---|
| Supplied v18 scanner companion | 2 | First TE 36 ms, ESP 36 ms | Preserved source/parameter baseline; not the eight-echo comparison |
| October 5 test1e actual eight-echo PPR | 8 | First TE 54 ms, ESP 14 ms | Future controlled scanner adaptation baseline; finite waveforms still unavailable |
| Gibbons Figure 3/S2 | Preparation profiles | Published RF/preparation response; 3000 spins across 30 mm, 6-mm imaging slice, 18-mm ss-MGOT diffusion slab | Reference target, not reproduced here |
| Independent ideal diagnostic | 8 | Chosen 16-ms ideal spacing, infinite T1/T2 | Algebra/coherence test only; neither scanner adaptation nor paper replication |

Test1e's PPR is `experiments/FSE-DWI_10-05-2026_v18_test1e/FSE-DWI_10-05-2026_v18_test1.ppr` (reused filename). Its readout/source phase convention, RF train, thickness, ordering and full acquisition table must remain attached to its identity when adapting it. Increasing/decreasing/alternating comparisons must derive from the verified v18 source's signed schedule, not the earlier v1.6 Pulseq comparison.

The eight-echo signed schedule design is documented by the writers. “Alternating” means alternating polarity with retained amplitude magnitude; the first diffusion-refocusing crusher and imaging crusher amplitudes remain separate. Complete physical moments and per-echo diffusion tensors require the missing gradient samples and scheduled-event traces. No new equal-effective-b, image-quality or PSF claim is made from eight echo amplitudes.

## Independent work completed

Five distinct agents used the available multi-agent workflow, with separate writer ownership and independent reviewers:

| Role | Owned artifacts | Outcome |
|---|---|---|
| Reference and RF design | [reference_rf.md](reference_rf.md), dedicated RF research assets | Published specifications/primary design sources and explicit missing coefficients/schedules; inspect report for any pulse-design attempt and its measured status |
| ss-MGOT writer | v191 reserved PPL/PPR, [v191_implementation.md](v191_implementation.md) | Actual-v18 integration/branch/timing contract; explicitly unimplemented reservation |
| Alsop writer | v192 reserved PPL/PPR, [v192_implementation.md](v192_implementation.md), design audit | Correct transverse-retention method contract; explicitly unimplemented reservation |
| Independent PPL reviewer | [ppl_review.md](ppl_review.md) | Reviewed baseline, final reserved files and revision; approval limited to preservation/gates, method approval withheld |
| Independent physics reviewer | [physics_review.md](physics_review.md), [ideal results](physics_validation/ideal_mechanism_results.json) | Separate coherence/tip-axis checks and final source review; finite-RF/PPL approval withheld |

The workflow used the environment's exposed agent spawn/message/review capabilities. No separate tool/version attestation named “multi-agent v2” was exposed; this report does not claim an independently certified API version.

The ideal diagnostic checks both preparations for initial phases 0/45/90 degrees, B1 100/80%, and B0 -128/0/+128 Hz, with exact rotations, local vectors and coherent spatial means kept separate. It includes preparation A/B/tip/storage/re-excitation landmarks as applicable, separate preparation-end and post-leading-crusher states, and ideal first/second/final echo centers. Uniform rectangular-pulse ODE/matrix checks and spatial convergence are independent numerical cross-checks. They do not validate selective RF transfer, RF-step convergence of the final pulse, physical ADC midpoint alignment, or compiled PPL events.

One consequential design finding is the initial recall boundary: in the review's explicit separate-moment ideal convention, first RF uses pre `C`, post `C+D`; after each ADC, restoration `-D` can combine with the next pre-crusher to give later pre `C-D`, post `C+D`. Applying the later fused pair to the first RF cancels the ideal recalled signal. Actual selective RF compensation and signed physical-gradient convention must be included before translating this contract to scanner events. Both writers received this finding; implementation remains blocked rather than falsely marked corrected in executable code.

## Reproduce available checks

From the repository root:

```powershell
python examples/audit_v19_inputs.py
python examples/v19_physics_review.py
python docs/v19/v192_design_audit.py
python -m unittest discover -s tests -p test_scanner_timing_review.py -v
python -m unittest discover -s tests -p test_scanner_v17.py -v
```

The two existing suites passed 8 and 20 tests respectively. These cover existing scanner arithmetic/generator contracts and v17 regression behavior; they are **not** v191/v192 vendor compilation tests, nor a verified v18-to-events mapping. The existing generator warns that off-center slice phase correction is unapplied without `sim_acqpad_ticks`; those modeled off-center events cannot establish console phase accuracy. The new input audit verifies v18 preservation and documented unresolved-include gates. Independent ideal results include their input hashes and declare all departures.

## Completion boundary

Played RF/gradient/ADC diagrams, physical timing tables, final finite-profile simulations, new scanner-compatible RF libraries and console qualification cannot be produced from the available samples/interfaces. Schematic or ideal plots are labeled as such. Open dependencies and method correctness requirements remain unresolved; the request for working PPL implementations is still pending. After uploads, inspect formats/includes, establish RF calibration and full complex transfer response, implement the two methods, compile/export actual scheduled events, run the figure-specific and adapted-protocol validations, and repeat both independent reviews on those final integrated implementations.
