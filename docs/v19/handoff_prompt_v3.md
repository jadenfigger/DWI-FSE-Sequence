# Handoff v3: finish the v191 (ss-MGOT) / v192 (Alsop) PPL work

You are continuing an MRI pulse-sequence engineering task in
`C:\Miscellaneous\Coding_Projects\Python\mri_processing\processing\DWI-FSE-Sequence` (Windows; the Bash tool takes POSIX syntax).

The original request is `C:\Users\jaden\.codex\attachments\50b21090-d1e5-4a33-b139-cf27407fd4ac\Pasted text.txt`. Earlier handoffs are `docs/v19/handoff_prompt.md` and `handoff_prompt_v2.md`; this file supersedes them for current state.

Rules:
- Never deploy to a scanner.
- Never modify v18 (`scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl`, SHA-256 `3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2`).
- No vendor compiler exists; do not ask for one.
- Edit the PPLs **only via the generator** `examples/build_v19_ppl.py`. It regenerates both PPLs and both PPRs.
- Nothing is committed yet. Commit only if the user asks.
- The user asked that reports explain in **plain English how validation numbers are obtained**. Keep that section current (README and `implementation_report.md`).
- Patching tip: heredoc-Python patches with `\n` inside strings repeatedly broke PPL `printf` lines. Use the Edit tool, or a `.py` patch file written with the Write tool. After every regenerate, verify with `grep 'printf("[^"]*$' examples/build_v19_ppl.py` (expect 0 matches).

## Current state (all done and verified)

### Final reviewed files

| File | SHA-256 |
|---|---|
| v191.ppl | `f0156b48a1b9ff648dba7d69e508629b6fc51bebfcb27d91c5f9fc46ee205f2d` |
| v191.ppr | `faa77a11c2da4c5fe9876d6a842b9bc3025c66ddc09eaa4e8270dec9350faf0c` |
| v192.ppl | `35d0eeaa0c60dc1d95f9bbb9c44881e65bc9a58d533aa3636031b4273d15e855` |
| v192.ppr | `678f2af5bb2fa205c2b7cb9402879d9ce1e98ed8e2c5fa4264c318b3e6898fbf` |
| generator | `c0f39a5c…` |
| RF library `scanner/rf/v19_research_rf.seq` | `cca9935e…` |

### Tools
- **`dwfse/ppl/`**: PPL preprocessor, parser, typed 16/32-bit interpreter (event mapper), waveform reconstruction (`events.py`), ledgers/landmarks/k-audit (`ledger.py`), event-driven Bloch (`bloch.py`), b-tensor and solve_ivp check (`analysis.py`), PPR reader, `run.map_events`.
- **Cost model:** nominal = EVO manual §4.9.2 expression costs ×0.8 (`expr_costs=True, expr_scale=0.8, stmt_cost_us=0`). This is calibrated so v18's comment-measured windows match and v18 runs without overruns.
- **`complete()`** includes the `acqpad/10` filter flush. This is inferred from v18 self-consistency.

### Validation
- **`examples/v19_validate_events.py`** writes `docs/v19/event_validation/`. The final run used the final hashes and took about 16 min.
  - Control identity holds after `sync()`.
  - No hazards; all 13 rejection tests stop before any event; convergence passes.
  - Physical-frame moments are exact: k/D = 1.000 ± 0.002.
  - Bloch tables are in `bloch_results.json`, b-tensors in `btensor.json`.
- **`examples/v19_reference_benchmark.py`** writes `docs/v19/reference_benchmark/` (Gibbons geometry; separate from the adaptation).
- **`tests/test_v19_ppl_mapper.py`**: 4 tests. The legacy suites (`test_scanner_timing_review.py`, `test_scanner_v17.py`) also pass.

### Reviews
- **PPL review:** `docs/v19/review/ppl_review_round1.md`, then `ppl_review_round2.md` (which includes round 3). No open blocking or major items on the final hashes.
- **Physics review:** `docs/v19/review/physics_review_final.md`, with independent scripts in `docs/v19/review/physics_checks/`. It reproduced the Bloch results to 1e-14 and the b-tensors within 0.8. No blocking findings.

### Documentation
Current: `docs/v19/README.md`, `implementation_report.md`, `rf_install_calibration.md`, `upload_checklist.md` (deployment checklist). Stubs: `v191_implementation.md`, `v192_implementation.md`. Superseded builders and helpers have been `git rm`'d.

### Design facts to keep
- **Phases:** prep 0/270°; ss-MGOT tip-up 180°, re-excitation 0°; Alsop elimination 270°; imaging 270°.
- **D:** 2 cycles per 1-mm slice; DAC −2860, taking the train-crusher polarity. Recall +D and restoration −D ride on `slice_list_rp` via `aq_mat_sec`.
- **Method PPRs** use `crush_amp` −8223, 3× test1e. The PPL rejects |C| < 3|D| and rejects |C1| within |D|/2 of |C| or of |C|+|D|.
- **Timing:** RF centre = plateau centre + `rfdelay`. Constants: `V19_ADC_SLOW` 8997, `V19_MAX_WAIT` 49000, re-anchor before each RF, `v19_mode` latched at setup.

## Remaining work (physics review major/minor findings, NOT yet addressed)

1. **P1 (major): C1 guard insufficient.** My scan on the real v192 ledger, by `diff_crush_amp` (spread = maximum phase spread over 8 echoes at 0/45/90°):

   | `diff_crush_amp` (DAC) | Spread |
   |---:|---:|
   | −1500 | 0.19 |
   | −2500 | 0.32 |
   | −3500 | 0.04 |
   | −4000 | 0.125 |
   | −4500 | 0.04 |
   | −5000 | 0.063 |
   | **−5482 (shipped)** | **0.020** |
   | −6000 | 0.019 |
   | −7000 | 0.074 |
   | −9000 / −10000 | rejected |
   | −12000 | 0.154 |
   | −14000 | 0.062 |

   The landscape is bumpy, so no simple coincidence rule fits it. Recommended fix:
   - restrict method mode to the Bloch-validated crusher geometry: ratios C/D ≈ 3.83 and C1/D ≈ 2.55 within a small tolerance;
   - first run a small 2-D scan around the shipped point (`crush_amp` −7700/−8223/−8750 × `diff_crush_amp` −5150/−5482/−5800), for v192 and v191, to choose the tolerance;
   - make the PPL print "re-validate with examples/v19_validate_events.py" for other values;
   - consider rejecting `v19_cycles` ≠ 2 unless validated;
   - check v191 too (the reviewer reports it robust except near −12000).

   The scan script was `$TEMP/c1scan.py` (temp; rewrite if missing). It uses `map_events` with overrides + `EventBloch`, latency 60 µs, z grid 3000 over 5 mm, y grid 16 for v191.
2. **P2 (major):** the reference benchmark's C1 = 1.5C (2250 cycles/m) sits in a coincidence window and inflates Alsop's phase dependence. Change it, e.g. C1 = 1.7C (2550). Check the 4-cycle case (C1 = 4500 is near a family at 4667) and choose a value ≥ D/2 away from all families.
3. **P3 (major):** the reference z-grid of 3000 points over 30 mm aliases after about echo 33, for both methods. The reviewer's addendum compares 3000 with 9000 points, without relaxation:
   - echoes 1–16 agree to ≤ 7e-7;
   - ss-MGOT is off by up to 0.076 at echo 33, and its ADC76 landmark is 0.362 vs 0.342;
   - Alsop is off by up to 0.109.

   With T1/T2 relaxation the ss-MGOT difference is at most 0.0021. Final numbers are in `physics_checks/benchmark_zgrid_results.json`.

   **Note:** `tests/test_v19_ppl_mapper.py` was edited outside this session. Its rejection test now also expects these overrides to be refused before any event: `v19_cycles` 4, `diff_crush_amp` −1500 / −12000 / +5482, and `crush_amp` −7700. The current PPLs reject only some of these; at least `diff_crush_amp` −1500 and −12000 are accepted today. Treat that test as the target spec for the P1 guard fix. Use about 9000 points (slow: ss-MGOT has a 32-point y-grid; run in the background), or restrict the claims to echoes ≤ 32. See `review/physics_checks/benchmark_zgrid_stdout.txt`.
4. **P4:** README wording. With the final D polarity, the near-zero moment is C−D (−551 cycles/m). The "C+D ≈ −555" statement applied to the first draft, where D had the opposite sign. Clarify.
5. **P5:** `btensor.json` follows the carrier pathway at even echoes, which ends at about 2D. In `examples/v19_validate_events.py`, compute both branches and pick the one whose endpoint k ≈ 0. Conjugate branch: flip the sign of k at the elimination centre (v192), or at the re-excitation centre (v191). Slice b changes by ≤ 6 s/mm².
6. **P6:** README must report the Alsop ±128 Hz range across all phases (echo 1 spans 0.21–0.38), not 45° only.
7. **P7:** shift the gradient-defined landmark snapshot times by the gradient latency (`rfdelay`) in `run_bloch` (all landmarks except `pre_RF1_after_crusher`). Landmark B currently misses about 1% of D.
8. **P8/P9:** state the effects in README and report. The benchmark's 1.2 ms Alsop elimination biases the comparison against Alsop. The 30 ms prep TE only rescales amplitudes.
9. **Optional refinement (documented open issue):** off-resonance isodelay alignment. The ADC1 echo peak sits 185 µs (v192) and 95 µs (v191) after the middle sample under a ±150 Hz spread. Shift the train reference by the measured selective-pulse isodelay offsets, or leave it documented.
10. **After any PPL change:**
    - regenerate;
    - run `tests/test_v19_ppl_mapper.py`;
    - rerun `examples/v19_validate_events.py` (about 16 min; background);
    - if the reference changed, rerun `examples/v19_reference_benchmark.py`;
    - ask the PPL reviewer (any independent agent) for a short confirmation;
    - update the README hash table, results and "Open issues";
    - keep statuses separate: implemented yes / compiled no / simulated yes (nominal) / reviewed yes / verified on scanner no.
11. **Final report to the user:** concise, with exact file hashes, how the numbers were obtained (plain English), the findings that changed the design, and unresolved issues stated plainly.
