# Continuation prompt: finish and independently validate DW-FSE v1.81 / ss-MGOT v1.911

You are continuing an unfinished engineering task in this existing workspace:

`C:\Miscellaneous\Coding_Projects\Python\mri_processing\processing\DWI-FSE-Sequence`

Act as a senior MR physicist and MR Solutions PPL sequence engineer. Continue from the current files; do not restart the investigation or assume the candidates are approved. The previous session was interrupted by an account usage limit during implementation/review. No final upload package, full final Bloch sweep, or completed final independent approval exists.

## Updated objective and user preferences

Finish conservative, reproducible v1.81 and v1.911 improvements, resolve the open validation/compiler/physics findings below, obtain independent adversarial review of the final bytes, then deliver a before/after report and upload-candidate ZIP with SHA-256 hashes and a prioritized scanner test plan.

Use parallel agents for investigation, implementation and independent physics/PPL/timing review. The user explicitly required this: no change may ship solely on its author's word. Preserve every pre-existing repository file; additions from this unfinished task may be revised. Never overwrite v1.8, v1.91 or v1.92, historical tools/results or original tests. Alsop v1.92 is out of scope.

The scanner is an MR Solutions 9.4 T small-animal system. The user cannot run console checks during this session and has no additional gradient ratings/calibration or measured delay traces. Their latest instructions are to use the available information and **raise the threshold for questions**. Ask fewer, clearer questions with explanatory context, only for a consequential uncertainty that available evidence cannot resolve. Earlier they required asking about strongly beneficial changes with uncertain PPL/console implementation rather than quietly sidelining them; reconcile this with their later preference by investigating available source evidence first. Clearly distinguish a high-value implementation held by a specific unresolved gate from a marginal proposal. Do not repeatedly ask for unavailable hardware information.

Every change needs physics rationale, predicted effect and repository verification. All vendor compilation, physical timing, RF calibration/achieved flips, actual gradient limits/oblique sums and SAR qualification remain **scanner-verify**. Do not claim any candidate is scanner-verified.

## Read these materials in order

1. The complete original task, including mandatory evaluations, compiler constraints and deliverables:
   `C:\Users\jaden\.codex\attachments\07635064-b264-499d-a184-6a4e1ed09419\Pasted text.txt`.
2. Current work: `docs/v181_v1911/plan.md`, `physics_findings.md`, `ppl_findings.md`, `scan_findings.md`, `review_validation.md`, `review_compiler.md`, and `refocus_width_study.md`. Some reviews are unfinished and some results reference superseded candidate hashes. Check actual input hashes before relying on any result.
3. New builders and validators:
   - `examples/build_v181_ppl.py`
   - `examples/build_v1911_ppl.py`
   - `examples/validate_v181_v1911.py`
   - `examples/validate_v181_guards.py`
   - `examples/v181_v1911_static_audit.py`
   - `examples/v181_v1911_pathway_audit.py`
   - `examples/v181_refocus_width_study.py`
4. Independent evidence/helpers in `docs/v181_v1911/review_checks/`: `event_audit.py`, `finite_rf_peak.py`, `physics_oracles.py`, `read_relocation.py`, and their JSON outputs. Also inspect `timing_validate_candidate.py`, `timing_candidate_audit.json`, pathway comparison JSONs and `v181_writer_checks.json` in the parent directory.
5. Authoritative historical context: `docs/v19/{README,implementation_report,reference_rf,rf_install_calibration,physics_review,ppl_review}.md`; `docs/scanner_v17*.md`; `docs/ppl_experiment_log.md`; `docs/ppl_improvement_report.md`.
6. Actual sources, PPRs, includes and waveforms: `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.8.*`, `-1.91.*`, `scanner/utilities/`, `scanner/rf/v19_*.seq`. Read `dwfse/ppl/`, `examples/v19_validate_events.py`, `examples/build_v19_ppl.py`, `tests/test_v19_ppl_mapper.py`.
7. Scan evidence: `docs/physical_scanner_experiments_2026-10-04.md`, `-05.md`, `-07.md`, `docs/data/oct07_sequence_review.md`, `experiments/scan_catalog_2026-10-07.md`. MRD-embedded protocols take precedence over stale adjacent PPRs.

## Baseline provenance

- v1.8 source SHA-256: `3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2`.
- ss-MGOT must start from `docs/v19/compiler_compatibility/v19_method_only_v7.zip`. Its v1.91 PPL is extracted under `docs/v181_v1911/baseline_v7/`, SHA-256 `6a0d222b6c8689fbdee5f4ae412c4d5df0bea10a7da99a309fabf5dfab04d828`.
- The existing v19 generator's in-memory `build('ssmgot')` exactly reproduces ZIP v7. **Do not call its main**, which overwrites original sources.
- Workspace v1.91 PPL is combined v6, SHA `92bdcb79081087c29dd045cd797cb8fbdd1e4f02ff4f341b9711eef706f16e4f`. Workspace PPR and all six RF libraries already match v7. Do not describe the PPR as v6.
- Existing mapper suite initially ran 13 tests: 11 passed, two failed because tests expect method-only source while workspace PPL is v6 (image budget and method-only guards). Preserve originals; report those as pre-existing, not new regressions.

## Current candidates — neither is finally approved

At handoff, v1.81 PPL SHA-256 is `3c90b80b31bf3cecfc38b8c1300061181fb3df0bcc3f60fb93027a45b6b51c7c`; v1.911 is `7cf66e01f63765af2d8a0211f00013ce0a48e2def85047cb77dd04532b928e1d`. Rehash on entry. Many existing JSONs reference earlier `48d11...` / `33e7...` versions.

**v1.81:** Moves the diffusion-mode read prephaser into the first read-list prelude after diffusion, preserves later read lobes, and rejects diffusion with unsupported flow compensation. First-read DAC changes from 269 to -2694 for the test1e protocol. Negative secondary read ramps integrate exactly with `(plateau+tramp)`; do not incorrectly apply the positive crusher's 1.0096 ramp factor. Fixes the narrow block-C deadline and active slice-list restart using a 100-us window with settling. Physically enlarges pre-RF setup windows and accounts for +895 us in the TR floor; TE/ESP are retained. Adds a backward exit hub to avoid forward-goto exhaustion.

Independent exact primary-path tensor integration on an earlier timing-equivalent candidate found ADC1 total b traces (nominal 0/100/1000/6000) of approximately 3.9965/104.0414/1000.7032/5980.6667 versus baseline 12.0198/165.0228/1175.9254/6398.1492 s/mm². Desired read endpoint differs only about -0.233 cycles/m. Recompute on final bytes and imaging states.

**v1.911:** Fuses train C±D lobes, retains selective RF plateau, overlaps slice lobes with existing read/phase preludes, targets 13-ms ESP. Uses 1328-us fused tops and 200-us ramps; default first/pre/post DACs approximately -6460/-4774/-8146, below baseline peak 8223. Restricts geometry and orientation to audited cases; rejects ESP12. A 12-ms design was deliberately excluded because it would begin the next slice lobe before `complete()` finishes receiver filter flushing. Actual source-model nominal ESP is approximately 12997.38 us, versus v7 13996.94 us, constant within each cost model; do not call this exact physical timing.

Independent review caught a **missing terminal -D restoration** after the final ADC: merging restoration into the next RF pre-lobe does not handle the last echo. The latest builder now adds a final-only slice list, matrix setup, timer anchors and shot/TR-duration accounting. **That late fix is not fully revalidated or independently approved.** Audit final ADC→terminal lobe→exit, all cost models, final moments and TR minimum. Earlier positive results predate this fix.

## Critical next actions

1. **Fix actual-imaging coverage in the main validator before rerunning it.** Default PPRs have `no_disacq=4`, `nav_on=1`; first two mapped shots are dummy/navigation with `nav_cnt=0`, `gp_mul=0`. To test two actual imaging shots use overrides `no_disacq=0, nav_on=0, no_views=128`. Disabling navigation alone leaves 136 views and triggers E70. The main validator was just changed to set the first two overrides but **still needs `no_views=128`**. Alternatively map through at least six shots with the unmodified PPR. Assert that nonzero PE is exercised and test diffusion-row progression/directions; also retain default dummy/navigation coverage. Independent imaging audit JSON already exists—inspect its actual hashes and completeness.
2. Main-validator method detection was fixed to inspect RF frame names, not absent `v19_stage` variables. v1.8 ADC1 follows the diffusion 180; imaging midpoint checks must pair ADC2 onward with the train RFs. Existing `validation/event_gates.json` is stale and failed partly because the earlier detection was wrong. Do not treat it as a final sequence failure or success. Re-run from corrected code.
3. Resolve v1.81 **compiler image growth**. On the earlier `48d11...` source the model estimated 57452 bytes versus baseline 56664 (+~788), failing the conservative no-growth budget. Forward gotos were fixed to 21; warning identities stayed at 11 and largest branch body 369 nodes. Latest source adds more guards, so rerun. Conservatively compact unused features/diagnostics in the new copy if needed, preserve error semantics and independently verify. Do not simply relax the gate because the estimate is below 64K; fixed overhead is unknown and baseline was historically near the limit.
4. Reproduce builders exactly; check PPR filenames, method tables (64 rows), widths, integer overflow, added comments/macros/literals and all new error-code meanings. Earlier v1.911 PPR, matrix-settling and signed-32 scaling defects were fixed, but audit final bytes.
5. Complete the full finite-RF Bloch grid: B1 0.8/0.9/1.0/1.1, B0 -128/0/+128 Hz, initial phases 0/45/90, comparing both baselines and candidates. It has **not been completed**. Main script has explicit hazard, timing, rejection and Bloch-regression gates; failures must be investigated/dispositioned, never silently relabeled passes.
6. Revalidate every RF/ADC interval's gradient areas, first/last exceptions, RF-time selector equality, all-axis endpoints, crusher ratios |C|/|D|≈3.83 and |C1|/|D|≈2.55, no fused slice lobe overlapping RF or the full receiver busy interval. Selective slice gradients necessarily overlap selective RF; the nonoverlap requirement concerns added fused lobes. Report bounded integer-DAC errors rather than exact equality. Earlier maximum per-boundary error was ~0.00011753 cycles across 1 mm; accumulated all-history bound was ~0.0013423 cycles through eight echoes.
7. Finish diffusion-aware pathway analysis and every-echo b tensors. Earlier instantaneous-RF EPG at D=.002 mm²/s, T1=1.3 s/T2=.032 s predicted fused gains ~3.15% at E1 and ~16.52% at E8; this is conditional, not finite-RF or acquired performance. Run independent oracles and final comparisons. The existing EventBloch has **no molecular diffusion**. Existing `dwfse/pathways.py` omits `(2*pi)^2` in stored-Z diffusion and rejects the MGOT preparation; do not use it as the physical oracle or edit it. The new additive generalized model includes that factor. Its excitation-phase sweep is not automatically a motion-induced post-preparation phase test.
8. Run all eight cost models, both actual imaging shots and default states; zero overruns/ignored lists/premature matrix uses; all original 19+ method rejections and new geometry/orientation/overflow cases before RF. Raw inherited `matrix_active` diagnostics can occur during zero output; distinguish them from actual premature use and report honestly. The ledger does not rotate oblique physical axes; v1.911 guards restrict angles. Physical hardware qualification remains unavailable.
9. Obtain final independent physics, compiler and timing reviews with exact final hashes. `review_physics.md` was not completed. Fix findings, rerun only affected checks plus necessary final validation, then write the report, scanner plan, error-code lookup, candidate ZIP and SHA-256 manifest. Confirm no tracked originals changed.

## High-value unfinished evaluations

- **Refocusing spatial width:** Isolated actual-waveform study shows strong benefit at width 1.2/1.5× with unchanged RF energy: nominal edge conjugate transfer ~0.569→0.769→0.912. Simple selector scaling changes pre/post moments and off-center frequency handling; coupled-crusher mode is problematic. `refocus_experiment/run_experiment.py` is an unfinished protocol-specific experiment, not a scanner deliverable. Continue compensation feasibility if safely provable; do not insert naive scaling. Zero-lag versus assumed 60-us gradient lag changes the required compensation, so distinguish physical assumptions.
- **Isodelay:** Do not hard-code the historical +95-us shift. Independent peak probes moved +93.44→+65.46 us when changing z/y grids; y8 may alias the eight-cycle spoiler. Standard 3000z/32y baseline/candidate JSONs now exist; inspect values, hashes and convergence, including y64. A fitted whole-train peak is not a universal RF isodelay. RF latency 3 us and gradient lag 60 us are unmeasured assumptions; use sensitivity and leave real centering scanner-verify.
- **Navigator:** A same-shot navigator has strong benefit, but the current navigator is a separate train and reconstruction assumes that layout. Extra ADC storage/tagging/reconstruction contract remains unavailable. Do not silently add lines or claim shot-wise correction implemented. No answer to the earlier navigator question was supplied; avoid repeating it without a concrete new need.
- **Other decisions:** Keep negative nonalternating polarity supported by paired scans. Do not reduce ss-MGOT crushers without coincidence validation. Mild v1.8 VFA was declined because of phase fragility. Preparation TE/delta/Delta reduction needs proved timing and b/hardware accounting, not nominal edits. Explicitly complete the required evaluation/decline table in the final report.

Begin by reading the task and current findings, checking current hashes and validator overrides, then assign independent workers to close the remaining gates. Continue autonomously within the authorized conservative scope; never equate source-model success with console/scanner validation.
