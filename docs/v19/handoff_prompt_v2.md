# Handoff v2: continue v191 (ss-MGOT) / v192 (Alsop) PPL implementation

You are the coordinating MRI pulse-sequence engineer. Continue from the saved repository state at
`C:\Miscellaneous\Coding_Projects\Python\mri_processing\processing\DWI-FSE-Sequence`. The full original request is
`C:\Users\jaden\.codex\attachments\50b21090-d1e5-4a33-b139-cf27407fd4ac\Pasted text.txt`; the prior handoff is
`docs/v19/handoff_prompt.md`. Both still define scope. Do not deploy to the scanner; v18 must stay unchanged
(`scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl`, SHA-256 `3b420376…598db2`; it was unchanged as of this handoff).
No vendor compiler/simulator exists locally; do not ask the user for one again.

## What now exists (new this session, uncommitted)

- **PPL interpreter / event mapper** `dwfse/ppl/`: `preprocess.py` (case-sensitive macros, case-insensitive
  identifiers), `parser.py`, `interp.py` (16/32-bit semantics, gradient sequencer lists/HOLD/matrices, RF frames,
  phase/frequency, ADC, timer 5-ms overrun rule; `ASSUMPTIONS` list; `complete()` includes `acqpad/10` filter
  flush; nominal `stmt_cost_us=0.5`), `events.py` (exact PWC waveforms), `ledger.py` (ledgers, k-space audit with
  `k0` conjugation, landmarks), `bloch.py` (event-driven exact-rotation Bloch, repository convention), `analysis.py`
  (b-tensor along a coherence path, independent `solve_ivp` cross-check).
  Calibration on v18 + test1e: RF-centre→ADC-centre 6999.5 µs; with 0 µs/statement v18's own train `SetList`
  hits an active channel, and at 1 µs/statement v18's 18.5-µs block-C window overruns (v18 fragility finding).
- **Generator (single source of truth)** `examples/build_v19_ppl.py` → writes both PPLs and both PPRs. Old
  `examples/build_v191.py`, `build_v192.py`, `v191_source_audit.py`, `scanner/v191_event_helpers.pph`,
  `docs/v19/v192_design_audit.*` are SUPERSEDED (old builders overwrite the PPLs with stale drafts: delete them).
- **PPLs** `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl` / `1.92.ppl`: `v19_on=0` → v18 path (mapper shows
  event-identical RF/ADC/gradient/matrix ledgers to v18 for 2 shots, incl. crusher schedules 1/2/4);
  `v19_on=1` → separate method shot entered from inside v18's timed 3000-µs window (`v19_mat_window`, `v19_shot`,
  `v19_echo_loop`, rejoins at `v19_after_train`). Padded windows anchored on list starts; RF centre = plateau centre
  + rfdelay. New RF library `#use RF1 "c:\smis\seqlib\v19_research_rf.seq" pf19`, NEWSHAPE indices 18–23,
  multipliers `scale(rfcal, num, 10000)`. D lobe = POSPULSE_SEC(tdp); recall +D / restore −D ride on v18
  `slice_list_rp` via `CREATE_MATRIX(aq_mat_sec, …±v19_d_dac)`. D takes the train-crusher polarity; PPL rejects
  |C| < 3|D|.
- **PPRs** `…1.91.ppr`, `…1.92.ppr`: test1e eight-echo protocol + V19 params; **crush_amp changed −2741 → −8223**
  (disclosed: with |C|≈|D| imaging-RF FIDs are unspoiled and Alsop echoes become strongly phase-dependent —
  found by the event Bloch). Flips both `[1422,949,692,630,602,600,600,600]` (Alsop 1997 ramp; Busse unpublished).
- **Validation** `examples/v19_validate_events.py` → `docs/v19/event_validation/` (a full run was started in the
  background at handoff; rerun it). Quick-run results: control identity TRUE; all 13 unsupported/infeasible cases
  rejected before any RF/ADC; no SetList/matrix hazards; z 3000 vs 6000 diff 1e-6; RF substeps 1e-16; ODE vs exact
  7e-10. Moment audit: elimination input k matches requirement to 2 cycles/m; every ADC recalls one branch
  (k≈1.03–1.04 D commanded frame), restoration returns to ≈0.04 D. Bloch (B1 1, B0 0, no relaxation, physical
  frame latency=rfdelay): v191 |S| ≈ 0.39/0.40/0.35/0.34… for 0/45/90° (±0.002); v192 ≈ 0.29–0.30 echo 1, a few %
  phase dependence (elimination-profile leakage).
- **Reference benchmark** `examples/v19_reference_benchmark.py` → `docs/v19/reference_benchmark/` (Gibbons
  geometry, real research RF, idealised moment blocks, EPG Busse-style schedule). **Results are suspect**: echo
  signals ~0.05–0.16 and ss-MGOT phase-dependent (echo 1 0.001 at 90°). Debug before using (check: comp-kick
  signs/κ use, tip-up pre-comp sign, re-excitation output compensation, spoiler y-grid, 4-cycle crusher ratio,
  whether 6-mm normalisation is right). Alsop elimination there uses the 1.2-ms pulse (disclosed).

## Independent PPL review round 1 (agent) — MUST FIX
Report: `docs/v19/review/ppl_review_round1.md`.
- **B1 (blocking):** post-`initiate()` window `waittimer(3000)` (300 µs) is too short for CREATE_MATRIX(aq_mat_sec)
  (~136 µs) + three long divisions (~123 µs each per manual) → +5 ms every echo on hardware. Widen to ≥ 8997 ticks
  (v18 value) and recompute `v19_adc_mid`/A2 with the same constant, or move phase_correction math to post_a window.
  Also add operator costs (long `/`,`%` ≈123 µs; `*`) to `interp.py` COSTS so the mapper can see this class.
- **M1:** `gp_sl_var` is never assigned on the method path → set `gp_sl_var = 0` (3D rejected) in the shot.
- **M2:** timer period is 5 ms: any waittimer *issued* > ~4.9 ms after starttimer slips. Cap windows (≈49000
  ticks) by issue time, re-anchor (`starttimer()`) right after `rfon(0)`, bound `v19_b_d*10L`, `v19_b_sp*10L`.
  v18 default diff_tcrush=2000 would slip.
- **M3:** latch `v19_on` into a non-common int at setup (toggling in SCAN would run unbuilt lists); use
  `crusher_saved_train/first` instead of live `crush_amp/diff_crush_amp` in method matrices.
- Minor m1–m8, i1–i7 in the report (e.g. tramp+rfdelay ≥163 µs guard, spoiler overflow, read-prephaser slew check,
  alpha/p180_scale ignored by design — document, rfgate_delay ignored, odd plateau).

## Remaining work (in order)
1. Fix B1, M1–M3 (+ reasonable minors) in `examples/build_v19_ppl.py`; regenerate; rerun
   `python examples/v19_validate_events.py` and check identity, rejections, overruns at stmt cost 0–2 µs, moments.
2. Debug and rerun the reference benchmark; Fig 3/S2 profiles (A, B, tip, spoiler, re-exc, endpoint, pre-RF1,
   ADC1/2/last), Fig 4 (0/45/90°, 2/4 cycles, T1/T2 1300/32 ms). S1 is not reproducible (state so).
3. Compare adaptations vs v18 controls (original=test1e, increasing=test2b, decreasing=test5, alternating=schedule 2
   simulated only): TE, RF train, profiles, b-tensors (`btensor.json`), echo amplitudes. Note method PPRs use 3× crusher.
4. Independent reviewers on FINAL files: PPL reviewer round 2 (send it the fixes) and an independent physics reviewer
   (must re-derive axes/recall/b-tensor and check event_validation + reference_benchmark outputs).
5. Rewrite stale docs: `docs/v19/README.md`, `v191_implementation.md`, `v192_implementation.md` (they describe
   blocked reservations), add RF install/calibration instructions (copy `scanner/rf/v19_research_rf.seq` to
   `c:\smis\seqlib` under its new name; never overwrite vendor libs; multipliers inferred, need console B1 cal),
   exact reviewed-file hashes, and separate statuses: implemented (source yes) / compiled (no) / simulated (event-mapped
   nominal) / reviewed (round 1 found blockers) / verified on scanner (no).
6. Add a fast unit test (`tests/test_v19_ppl_mapper.py`): control identity, rejection, RF centre exactness.
