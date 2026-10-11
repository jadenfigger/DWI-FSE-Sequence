# Handoff prompt: v1.82 (from v1.81) and v1.912 (from v1.911), plus effective-b recon output

You are working in the repository `C:\Miscellaneous\Coding_Projects\Python\mri_processing\processing\DWI-FSE-Sequence`. It develops diffusion-weighted fast spin echo (DW-FSE) pulse sequences for an MR Solutions 9.4 T small-animal scanner. The sequences are written in PPL, the vendor's C-like pulse programming language, which compiles through PPLC/Forth. The next goal is reliable **in-vivo multi-slice mouse-brain** imaging.

You will produce two new sequence versions and the matching recon changes. The five work items are listed below. Keep the existing v1.81 and v1.911 files untouched; they are the scanner-validated baselines.

## Working style

* **Use smaller or cheaper subagents for most tasks.** That covers reading and summarising the long existing documents, searching the PPL for every place a variable is used, running the event model and static audits, writing test PPRs, and independent review passes. Keep the design decisions and final integration in the main agent. Run independent subagent tasks in parallel.
* **Read before writing.** A lot of validation and debugging history already exists. Reuse it, and don't rediscover it (see "Lessons" below).
* **Keep validation proportionate.** Every change needs:
  * a builder that reproduces the PPL exactly;
  * an event-model dry run of the test PPRs;
  * the static compiler-limit audit;
  * one targeted check per feature, listed under each item.

  Do **not** build new multi-thousand-case Bloch grids or multi-round review cycles. One independent review pass of the final bytes is enough.
* **Be honest about what is source-model-only.** Nothing is scanner-verified until it runs on the console. Hand back a short scanner test plan instead of claiming success.
* Do not commit unless asked. Do not modify `experiments/` raw data.

## Required reading (have subagents summarise these first)

| Document | Why |
|---|---|
| `docs/physical_scanner_experiments_2026-10-10.md` | First scanner results of v1.81/v1.911. §2 covers the b0 echo-1 defect, §3 the z-axis extra b, §6 the multi-slice phase failure (scan K). |
| `experiments/scan_catalog_2026-10-10.md`, `docs/data/oct10_echo_consistency.json` | K's per-slice echo phases: off-centre slices alternate odd/even by ±30–45°; the centre slice is normal. |
| `docs/v181_v1911/FINAL_REPORT.md` | How v1.81/v1.911 were built, timing tables (§6), moments (§7), effective b-tensors (§8), compiler limits (§11), source guards. |
| `docs/v181_v1911/PRACTICAL_SUMMARY.md`, `ERROR_CODES.md` | User-facing locks and error codes. New codes must be added here in the same style. |
| `docs/v181_v1911/compiler_v181_final.md`, `review_final_compiler_v181.md`, `review_final_v1911.md`, `ppl_findings.md` | Compiler and PPL pitfalls already hit. |
| `docs/v19/ppl_review.md`, `docs/v19/compiler_compatibility/` | Vendor-manual notes. In particular, *frequency offsets accumulate synthesizer phase* (manual pp52–53, `scanner/EVO Pulse Sequence Program Manual.pdf`), plus the multi-slice / offset code map. |
| `examples/build_v181_ppl.py`, `examples/build_v1911_ppl.py`, `examples/v181_v1911_static_audit.py`, `examples/validate_v181_v1911.py`, `examples/validate_v181_guards.py`, `dwfse/ppl/` (event model, `map_events`), `dwfse/btensor.py` | The existing build and validation tooling. Extend it rather than writing new frameworks. |
| `experiments/2026-10-09_exvivo_plan/make_pprs.py`, `check_pprs.py` | How test PPRs are generated and dry-run. |

## Lessons from past work (apply them)

1. **Program image size is the tightest constraint for v1.8x.** v1.81 had only about 147 bytes of modelled headroom after CEST/MTC was compiled out. Budget every addition, and prefer table or arithmetic changes over new code paths. Re-run the static audit after each change. If you run out of room, report it and propose what to compile out; do not exceed the limit silently.
2. **Timer windows and 16-bit integers.**
   * A missed `waittimer` window costs a whole 5-ms period per shot.
   * `int` is signed 16-bit (the v1.911 terminal timer relies on 40000 being read unsigned).
   * Use the existing long/fixed-point patterns, and check every new window with the multi-cost-model timing mapper.
3. **v1.911's fused slice lobes are exact-area constructions.** The `crush_amp` E142 lattice, the |C|/|D| ratios and the 200/700/1000-µs geometry locks all exist because integer DAC rounding has to preserve areas within 0.01%. Any timing generalisation must keep the per-boundary area equivalence that `FINAL_REPORT.md` §7.2 documents.
4. **Embedded MRD protocol beats the adjacent PPR.** Recon and analysis must read the protocol embedded in the MRD.
5. **The b-value search uses lobes only.** It applies `b_kfac = 39.69·δ²(Δ−δ/3)` to the diffusion lobes. Imaging, crusher and cross terms are not in it, and nothing records the achieved b (`FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl` lines 610–830). b = 0 rows play DAC 1 on purpose. Do **not** change how the sequence chooses diffusion DAC; record effective b instead (item 1).
6. **Do not touch the diffusion-180 crushers or b0 handling.** The b0 echo-1 defect will first be tested on the scanner with a protocol change (`diff_crush_amp` and small-b series). It is out of scope here.
7. Previous reviews found real bugs, including a terminal matrix rewrite during playing lobes and an unguarded timer window. One independent review of the final bytes is worth doing; a long sequence of reviews isn't.

## Work items

### Item 1: record effective b in recon output (v1.8, v1.81, v1.82, v1.91, v1.911 and v1.912)

The file is `scanner/recon/bare_bones_recon_fse.py`, whose `read_diffusion()` currently writes nominal `acq_b` to `.bval` and JSON.

* **Keep** the existing `.bval`/`.bvec` as nominal, for backward compatibility.
* **Add** these outputs:
  * `<stem>_beff.bval`: effective trace b per volume.
  * `<stem>_bmatrix.txt`: 6 components per volume (bxx, byy, bzz, bxy, bxz, byz), with the axis convention stated in the file.
  * JSON fields `EffectiveBValue`, `BMatrix`, `BMatrixEcho` (which echo: echo 1, the k-space-centre echo for centric ordering; optionally all echoes), `BMatrixSource` and `BMatrixWarnings`.
* **Source of truth:** compute it from the acquired protocol, not from hard-coded tables. Preferred: integrate the gradient waveform from the event model (`dwfse/ppl` `map_events` plus `dwfse/btensor.py`) using the embedded PPR and the PPL named in its `:PPL` line, resolved to the repo copy by version. Cache results by (PPL hash, protocol hash).
  * The integration must include every gradient between excitation and echo: diffusion lobes, crushers, slice select/rephasers and read prephaser.
  * It must respect sign changes at each refocusing pulse.
  * For ss-MGOT, use the same primary-branch convention as `docs/v181_v1911/review_checks/final_physics_grid.json`.
* **Calibration override:** an optional JSON (for example `scanner/recon/b_calibration.json`) with per-axis multiplicative scale and/or an additive b-matrix term, per sequence version. It exists because scanner data show z-axis b about 74 s/mm² above nominal at b1000, about twice the model's 37 s/mm². Record whether a calibration was applied.
* **Fallbacks:** if the PPL cannot be resolved or the model fails, write nominal values with `BMatrixSource: "nominal-fallback"` and a warning. Never fail the recon.
* **Check:** reproduce the `FINAL_REPORT.md` §8 echo-1 traces for v1.8, v1.81, v1.91 and v1.911 at b = 0/100/1000/6000 (+x) to within 0.5 s/mm². Reproduce the documented −x / +y / z behaviour for v1.8/v1.81. Run the recon on the 10-10 scans A, C, B, D and E and confirm that the effective-b ADCs agree as in `docs/physical_scanner_experiments_2026-10-10.md` §1. Keep recon run time reasonable: the model may be slow, so cache it.

### Item 2: ESP derived from the actual readout, with shorter readouts allowed (main goal: shorter ESP)

**Goal.** The user wants **shorter ESP by shortening the readout**: a shorter dwell, meaning higher bandwidth, with the same 128 samples. Longer ESP is not a goal.

**Principle.** The sequence should compute the minimum ESP from the protocol actually entered: readout duration, RF durations, fused-lobe durations, ramps and set-up windows. It should then accept any ESP at or above that minimum. Do not reject a value just because it was not simulated. Only reject what is physically or timing-impossible, or what would break an exact-area construction, and print the minimum accepted ESP in the message.

* **v1.81 → v1.82:** v1.81 already behaves this way. Scan J ran at 40 kHz (25 µs dwell) and ESP 11 ms and was accepted. Confirm that the minimum-ESP calculation tracks the readout length correctly at the dwell values the console offers (for example 50, 25, 20 and 16 µs). Keep the existing rule that the readout must be at least about 1.9 ms (≥80 kHz with 128 samples gives `invalid delay value: 0ms`). Change nothing else unless you find a lock.
* **v1.911 → v1.912:**
  * **Remove the fixed locks:**
    * ESP = 13 (E144, and E32 at 11–12);
    * the readout lock E143, which rejects longer readouts and was never checked for shorter ones.
  * **Lay the train out from the real readout.** The fused slice lobes keep their exact areas and shapes (1328-µs tops, 200-µs ramps, E142 lattice). Only their placement and the free intervals change.
  * **Minimum ESP** = the largest of the constraints that actually bind:
    * refocusing RF duration plus the fused pre- and post-lobes and their RF gaps;
    * readout duration plus the read/phase preludes and rewinders that overlap the fused lobes;
    * receiver flush or ADC padding;
    * the existing set-up and timer windows.
  * **Re-derive what E32 rejected.** E32 rejects ESP 12 at the 50-µs dwell because the next lobe would start while the receiver is still finishing. Re-derive that bound from the readout length so a shorter readout lowers it automatically.
  * **No arbitrary maximum.** Allow longer ESP if it falls out of the same layout naturally. Only reject what a 16-bit timer, buffer or other real limit cannot represent.
  * **Keep the other geometry locks** (`tcrush` 1000, `tramp` 200, `tdp` 700, `rfdelay` 60, angles) unless the generalisation makes one of them unnecessary. Say which ones remain and why.
* **Check (both versions, proportionate):**
  * event-model dry runs at 50 µs and 25 µs dwell, each at its minimum ESP and at minimum + 1 ms. For v1.912, also run 13 ms at 50 µs, which must reproduce v1.911;
  * a value just below the minimum, which must be rejected with the correct printed minimum;
  * per-boundary slice-axis area equivalence to v1.911, same tolerance as `FINAL_REPORT.md` §7.2;
  * echo centring within the existing tolerance;
  * no timer overruns across the cost models;
  * a small table of minimum ESP and minimum TR against dwell.

  Bonus if it falls out naturally: at 50 µs dwell and ESP 14, v1.912 would be the matched-ESP control against v1.91 that `SCANNER_TEST_PLAN.md` Item 6 lacked.

### Item 3: multi-slice in v1.912 (ss-MGOT)

* Remove the single-centred-slice restriction (E3). Allow `no_slices > 1` and off-centre slices, with **no orientation change**: the E146 angle lock stays.
* **Minimum spacing guard (new error code).** Interleaved slices must not let one slice's preparation slab or tip-up touch another slice's imaging slice. Implement:
  * `slice_separation_centre ≥ thickness × (max(v19_slab_pml, v19_tip_pml)/1000 + 1)/2 + margin`;
  * the margin covers the RF transition band, taken from the pulse library. Document the value, for example a few tenths of a slice thickness;
  * reject with a clear message that prints the minimum accepted separation in the console units.

  With the current 3000‰ slab this requires a gap of at least one slice thickness. Do not change the slab or tip-up widths in this task; a narrower slab (about 1.5×) is a separate future RF project. Write it down as a follow-up, with the guard formula already supporting it.
* **Per-slice frequency for every pulse width.** v1.911's transmit frequency is currently fixed for all widths, which is why off-centre slices were rejected. Each RF event selects with a different gradient amplitude: preparation slab 90/180, tip-up, re-excitation and imaging/VFA refocusing. Each therefore needs its own frequency offset `Δf = γ·G_sel·z_slice` for the current slice, set before that pulse, using the existing frequency-buffer mechanism (see `ppl_review.md` and the v1.8 multi-slice offset code).
* **Phase:** same requirement as item 4; implement once and share.
* Multi-slice batch/loop handling and dummies should reuse the inherited v1.8 multi-slice loop structure where possible.
* **Check:**
  * an event-model dry run of a 3-slice protocol at the minimum spacing, and one 1 µm (or one unit) below it, which must be rejected;
  * per-slice confirmation that every RF event's frequency matches its own selection gradient and slice centre;
  * the phase check from item 4;
  * static audit and timing.

### Item 4: off-centre slice phase (v1.82 and v1.912)

* **Observed:** on v1.81 scan K (slices at −1.2/0/+1.2 mm), the centre slice is normal. The off-centre slices show odd/even echo phase alternation of about ±40° and ±30°, and arc artefacts. That means the CPMG phase relation between the excitation and the refocusing pulses is broken only when there is a frequency offset.
* **Likely cause (verify in the code and the manual):** the synthesizer phase accumulates while the offset frequency is on. Pulses of different duration and centre therefore start at different effective phases, and the inherited code does not compensate. The other candidate is that the refocusing pulses use a different offset (or offset timing) from the excitation. In the PPL, find how the offset frequency and RF phase are set for excitation, the diffusion 180, and the train refocusing pulses; read the manual pages on frequency offsets (pp52–53).
* **Fix:** for every RF pulse of every slice, the RF phase must equal the intended CPMG phase **at that pulse's centre** in the rotating frame of the on-resonance (centre) frequency. Typical implementations are a phase-continuous offset scheme, or a per-pulse phase correction `φ = 2π·Δf·t_centre` (mod 360°) written to the phase register. Choose whichever fits the code-size budget.
  * Apply it in v1.82 (excitation, diffusion 180, train).
  * Apply it in v1.912 (prep 90/180, tip-up, re-excitation, train).
  * In ss-MGOT, the train only needs to be consistent with the re-excitation pulse, but implement the same rule for every pulse anyway.
* **Check:** in the event model, for the K protocol (3 slices, ±1.2 mm) and a larger offset (±5 mm), compute each RF pulse's effective phase at its centre in the centre-frequency frame. The off-centre slices must match the centre slice to within a few degrees for every pulse. Optionally, run one ideal-RF EPG/Bloch run of an off-centre slice to show that the odd/even alternation goes away. Keep it to one or two cases.

### Item 5: optional per-shot navigator (v1.82 and v1.912), handled automatically in recon

**Why.** In vivo, motion during diffusion encoding gives each shot a different phase. Combining multi-shot k-space without correcting this produces ghosting and signal loss. Both sequences currently support `nav_on`, which adds **one unencoded echo train per volume** as an extra shot. That cannot estimate shot-to-shot phase. The v1.81 review held "navigator in every shot" as high-value for in vivo. It was blocked only because there was no agreed rule for how the extra lines are stored and reconstructed (`docs/v181_v1911/PRACTICAL_SUMMARY.md` §7; `review_physics.md` disposition table). This item defines that rule and implements both ends.

**Sequence (both versions):**
* **Extend the existing `nav_on` parameter to three values; do not add a new parameter:**
  * `0`: off.
  * `1`: the current per-volume navigator train (unchanged behaviour).
  * `2`: per-shot navigator.

  Default: keep `2` as a **superset**, meaning the current per-volume train plus a navigator echo in every shot. The existing amplitude-envelope (deramp) correction then keeps working and the per-shot echo adds phase information. If you find a strong reason to make `2` per-shot only, justify it and state the cost.
  * Widen the PPR control range (`SCROLLBAR "Navigator?" ... 0,1 ... nav_on` → 0–2, label it for example "0=off, 1=per volume, 2=per shot").
  * **Audit every use of `nav_on` in both PPLs.** The current code mixes `if(nav_on)` and `if(nav_on==1)` (for example the `no_views_eff` and set-up branches). With value 2 those would disagree, so make each branch explicit about which modes it serves.
  * `nav_on` = 0 or 1 must produce sequences and raw data **identical to the current behaviour**.
* **Design choice (document the reasoning).** Recommended: one extra **unencoded echo (phase-encode moment zero) appended after the last imaging echo of every shot.** That keeps the centric k-space centre at echo 1, so TE and contrast are unchanged. It costs one extra ESP per shot and the TR minimum rises accordingly.
  * Prepending a navigator echo would move k-space centre to echo 2, so reject that unless you justify it.
  * If there is a strong reason for something else (for example a short gradient-echo navigator between echoes), justify it against timing and code size.
* **Phase encoding.** The navigator echo must have net phase-encode moment zero at its centre, and the phase-encode rewinder logic must stay balanced. In v1.912, the navigator echo must keep the same fused slice-lobe pattern and areas as any other train echo; treat it as echo ETL+1 of the same train.
* **Coexistence.** Make it work with multi-slice (items 3–4) and the new ESP/dwell freedom (item 2). Check the code-size budget first; if it doesn't fit v1.82, report that before implementing.

**Raw-data contract (write it down in `docs/v182_v1912/REPORT.md` and in a comment block in both PPLs):**
* exactly where the navigator lines sit in the MRD (per shot, per slice, per diffusion volume);
* how the views count changes;
* which embedded PPR variables let recon detect the layout without guessing;
* how mode 2 lays out the per-volume train together with the per-shot echoes.

The recon must work only from the embedded protocol.

**Recon (`scanner/recon/bare_bones_recon_fse.py`, automatic, for both versions):**
* Read `nav_on` from the embedded protocol. For 0 and 1 run the current path unchanged, with bit-identical output on archived scans. Audit the recon's own `nav_on` uses: for example `acq_offset = etl if nav_on else 0` and the navigator report treat any nonzero value as mode 1, so they must branch on the mode. An unknown value must raise a clear error instead of silently mis-parsing.
* When `nav_on == 2`:
  * separate the navigator lines from the imaging lines and build k-space from the imaging lines only;
  * for each shot, estimate the phase difference against a reference shot (median or first) from its navigator echo, using the readout projection. Model it as constant plus linear phase along the readout, weighted by magnitude, with phase unwrapping. Apply the conjugate correction to that shot's imaging lines (in the hybrid x-ky domain for the linear term).
* Keep a mode switch (`off`, `constant`, `constant+linear`) like the existing navigator correction modes. Record in the JSON:
  * which mode ran;
  * the per-shot phase estimates;
  * a navigator-quality metric (navigator SNR or projection coherence), with automatic fallback to `off` for shots whose navigator is noise-dominated, as at high b. The 10-07 report showed phase estimates from noise-dominated navigators do harm.
* Save the per-shot navigator phases to the output folder for QA, for example as `.npy` or `.csv`.

**Check (proportionate):**
* event-model dry run with `nav_on=2` for both versions, single- and multi-slice: an extra unencoded echo in every shot, zero phase-encode moment at its centre, timing and TR minimum reported, no overruns;
* `nav_on=0` and `nav_on=1` must reproduce the item 2–4 build bit-for-bit in the event model;
* recon on archived scans: unchanged output when the flag is absent;
* recon synthetic test:
  * take one archived scan (for example 10-10 A or B);
  * synthesise per-shot navigator lines from its existing volume-navigator echo;
  * apply known random constant + linear phase errors per shot to both the imaging lines and the synthetic navigators;
  * confirm the recon recovers the error-free image within a stated tolerance, and that the noise-dominated fallback triggers at high b.

## Deliverables

* New PPL/PPR: `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.82.ppl/.ppr` and `-1.912.ppl/.ppr`.
* Builders: `examples/build_v182_ppl.py` and `examples/build_v1912_ppl.py`, derived from the v1.81/v1.911 builders. They must reproduce the PPLs exactly, and the diff to the baseline must be reviewable.
* Updated `scanner/recon/bare_bones_recon_fse.py` (items 1 and 5), an optional calibration JSON, and small tests: recon on two archived scans unchanged or with effective-b sidecars, plus the synthetic per-shot-navigator test.
* Docs in `docs/v182_v1912/`:
  * `REPORT.md`: changes, checks run, results, what is source-only, code-size budget used.
  * `ERROR_CODES.md` additions.
  * `PRACTICAL_SUMMARY.md`: what the user can now set (bandwidth/dwell, the resulting minimum ESP, slice spacing rule) and what is still locked.
  * `SCANNER_TEST_PLAN.md`: short and prioritised. It should cover:
    * multi-slice phase on a phantom (K-style protocol on v1.82 and v1.912, checking per-slice odd/even navigator phase);
    * minimum-spacing crosstalk check (signal of the middle slice vs single-slice);
    * v1.912 at 25 µs dwell and its minimum ESP vs v1.911 (signal, echo-train decay, high-b floor);
    * recon effective-b sidecars on the 7-b scans;
    * per-shot navigator: phantom scan with `nav_on` 1 vs 2, where the image must not change beyond noise and the TR/time change must match the prediction, then a first in-vivo pilot with correction off vs on;
    * pass/fail numbers.
  * SHA-256 of the final PPL/PPR files.
* One independent review (a separate subagent with fresh context) of the final PPL bytes for compiler/timing risk and physics, with findings fixed or explicitly dispositioned.

## Out of scope

* b0 echo-1 defect fix and diffusion-180 crusher changes, which await a scanner protocol test.
* Narrower preparation slab or tip-up RF.
* Oblique orientations for v1.912.
* 3D readout.
* Magnitude-only or partial-Fourier navigator schemes, and 2D (ky) navigator correction. Per-shot navigators here are 1D readout-direction phase only.
* Any change to how diffusion DAC is chosen from the typed b.
