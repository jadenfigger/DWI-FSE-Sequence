# v1.81 and v1.911 work plan

Date: 2026-10-08. All new sequences are source-level candidates. Nothing is scanner-verified.

## Baselines and process

Preserve every existing repository file. Start v1.81 from the archived v1.8 source. Start v1.911 from the method-only v7 ZIP, not the workspace combined v6. Check the in-memory v19 generator against the ZIP before reuse. New builders must reproduce new PPL/PPR bytes without calling the old generator's file-writing entry point.

Parallel investigations cover physics, timing, compiler constraints and acquisition evidence. Implementation authors must not approve their own changes: separate physics, timing and compiler reviewers will audit the final bytes. Record failures as well as successes. The initial existing mapper suite has 11 passes and two failures caused by its method-only assumptions against the workspace v6; preserve those historical inputs and tests.

## Decisions and verification gates

| Change | Rationale and predicted effect | Risk and gate | Repository verification | Scanner-verify |
|---|---|---|---|---|
| v1.81 timing fragilities | Remove missed 185-tick calculation deadline and active slice-list restart; prevent an unintended extra 5 ms or ignored train lobe | Preserve supported baseline event geometry and integer widths; do not hide missed deadlines | All eight existing cost models, two shots, schedules and matrix readiness; before/after ledgers | Compiled instruction timing and physical gradient/RF/ADC trace |
| v1.81 read prephaser relocation | Moving it after diffusion preparation removes its diffusion cross-term, making low-b labeling more faithful | Preserve one complete prephaser, desired echo position and timing; implement only if an existing safe slot is proved | Per-echo effective moments and full b tensors at b0/100/1000/6000; Bloch grid comparison | Compiled trace and phantom diffusion calibration |
| v1.81 wider spatial refocusing slab | Better refocusing at excitation-slice edges; lower selector gradient at fixed pulse duration/flip need not increase nominal RF energy | Study 1.2–1.5x spatial coverage, never infer benefit from lengthening the same sinc; require slice compensation, offsets and crushers to remain correct | Decoded finite-waveform Bloch profile, RF energy and moment/pathway checks | Actual achieved flips, slice profiles, RF calibration and console SAR |
| v1.911 v7 foundation | Avoid combined image overflow and retain existing method-only guards | Exact ZIP/generator equality; table capacity 64 | Static image estimate, forward gotos, branch size, warnings, rejected protocols | Vendor compilation, linked image and RF loading |
| Merge ss-MGOT train lobes and reduce ESP | Combine restore/recall, crusher and selector compensation on each RF side; may reduce T2 and pathway diffusion loss | Preserve area separately at every RF/ADC boundary, first pulse special handling, no **fused** lobe over RF or ADC; the slice selector itself must overlap selective RF. Physical-axis hardware envelope currently unknown and question pending | Effective moments, k paths, generalized pathway/EPG diffusion, crusher ratio 3.83/2.55, logical and physical amplitude/slew | Rated limits/calibration, orientation sums, compiler and played trace |
| Timing/isodelay correction | Align echo and RF effective centers without per-echo drift | The reported 95 us whole-train peak offset is not a universal RF-center correction. Delay provenance is pending; no blind fixed shift | All-model event ledger, RF-latency sensitivity, finite-RF off-resonance peak study | RF pipeline, gradient lag, ADC/filter convention and selective isodelays |
| Per-shot navigator | Shot-wise phase correction has strong benefit for multishot diffusion | Extra ADC storage/tagging and reconstruction contract unknown; question pending. Do not quietly relegate to a marginal proposal | Existing vendor loop/storage investigation; implement only after contract supplied | Raw navigator identity and correction on moving/in-vivo phantom |

Existing EventBloch is finite RF but has no molecular diffusion. Its results cannot certify stimulated-pathway diffusion losses. Add a bounded independent instantaneous-RF pathway model with encoded longitudinal diffusion, keeping this limitation explicit. Investigate the apparent missing 2-pi factor in the existing longitudinal diffusion expression without editing the original file.

## Retained, rejected and pending choices

Retain negative nonalternating baseline crusher polarity supported by the October 5 paired scans. Do not reduce ss-MGOT crushers just to improve signal: changed coincidence selection requires a new scan and pathway validation. Do not add an optional low-flip v1.8 train without evidence of phase robustness. Do not shorten delta/Delta or the preparation just by changing nominal TE: it changes available b, calibration and diffusion contrast, and requires a proved timing budget. Alsop v1.92 remains out of scope.

Hardware-limited fusion, calibrated timing correction and navigator storage are **high-value pending questions**, not rejected marginal ideas. Continue independent safe work while awaiting answers. If information is unavailable, clearly identify the unfulfilled gate and exact future check; exclude unqualified changes from upload candidates.

## Deliverables and review

New additive builders and matching scanner PPL/PPR files; investigation documents; independent validation scripts/results; before/after report covering ESP/TE, event and pathway moments, Bloch grid, all-echo b tensors and compiler limits; independent adversarial reviews followed by any fixes and reruns; candidate upload ZIP and SHA-256 manifest. Candidate packaging must distinguish source validation from vendor compilation and scanner qualification.
