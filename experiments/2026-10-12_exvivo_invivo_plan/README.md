# October 12: ex-vivo checks, v1.83/v1.912 comparisons, then in-vivo rat brain (surface coil)

Each PPR is in its own folder: `FSE-DWI_10-12-2026_<version>_test<letter>/`. [run_order.csv](run_order.csv) lists every scan's settings and duration. All protocols share these settings, apart from the exceptions noted in each part:

| Setting | Value |
|---|---|
| FOV / matrix / slice | 35 mm, 128 × 128, 1-mm slices |
| Readout | 40 kHz (25 µs) |
| Timing | ESP 11 ms, TE 44 ms, Δ 30 ms, δ 4 ms, **TR 2000 ms** |
| Other | ETL 8, centric ordering, 1 average, 4 dummy trains |

Durations exclude setup.

**Before loading:**
* Copy the current `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.83.ppl` to `G:\J_Figger\` and compile it. It was rebuilt after the navigator fix. Use the v1.912 PPL you compiled after that fix.
* **Navigator mode 2 protocols store `VIEWS_PER_SEGMENT` = 9** (8 echoes + the per-shot navigator) and `NO_VIEWS` = 153. Leave these values as they are. The PPL turns them back into an ETL of 8.
* v1.83 protocols contain `v183_phmode` and `v183_phcal`. Don't load v1.82 PPRs into v1.83: the console rejects the missing records.

**Every session:**
* Fix the RX gain for the whole session and record TX gain, RX gain, frequency, shim and temperature.
* Set any in-plane FOV offset once, before the first scan, and keep it for every scan.
* Ex vivo: let the brain reach room temperature (2–3 h out of the fridge), degas, and keep bubbles away from the brain.

## Part 0: centre frequency and ss-MGOT rescue (3.5 min)

| Test | PPL | What | Time |
|---|---|---|---:|
| A | v1.83 | b10, single slice, **20 kHz** (ESP 14), navigator mode 1 | 0.7 min |
| B | v1.83 | Same as A at 40 kHz | 0.7 min |
| C | v1.912 | b10, b1000 +x, b3000 +x, single slice, navigator mode 1 | 2.1 min |

1. Set the centre frequency on the water peak. Run A and B, then `python tools/frequency_check.py <A>.MRD <B>.MRD`. It must print PASS (|shift| < 0.5 px). The 10-11 data give FAIL at 2.8 kHz, and 10-10 gives PASS. If it fails, re-set the frequency and repeat A and B.
2. Run C. **ss-MGOT is working only if C shows b-dependent signal**: a bright b10 image, with the brain dimmer at b1000. If C is noise again, skip all v1.912 scans (C, L, O, P, R, T, V, X) and report back.

## Part 1: off-centre RF phase calibration, v1.83 (6.3 min)

Follow [docs/v183/CALIBRATION.md](../../docs/v183/CALIBRATION.md). All scans are b10 with three slices, navigator mode 1, 0.7 min each.

| Test | Mode | `v183_phcal` | Slices |
|---|---|---:|---|
| D | 0 (vendor / v1.81) | — | ±1.2 mm |
| E / F / G | 1 (v1.82 gated) | 0 / +530 / −530 | ±1.2 mm |
| H / I | 0 | — | ±2.8 / ±5 mm |
| J / K | 1 | **set on the console to the tool's recommendation** | ±2.8 / ±5 mm |
| L | v1.912 (only if C passed) | — | ±2.8 mm (v1.912 guard ≥ 2.7575 mm) |

```bash
python tools/offcentre_phase_cal.py <D>.MRD
python tools/offcentre_phase_cal.py <E>.MRD <F>.MRD <G>.MRD --plot cal.png
python tools/offcentre_phase_cal.py <H>.MRD <I>.MRD <J>.MRD <K>.MRD <L>.MRD
```

* **Pass:** every off-centre slice has ramp ≤ 5°/echo and alternation ≤ 5°.
* **Choose a mode:** keep the mode with the smaller ramp at ±2.8 and ±5 mm, mode 0 if they tie.
* **All later v1.83 files** (Q, S, U, W and their fallbacks) **are saved with mode 0 and phcal 0.** If mode 1 wins, set `v183_phmode` = 1 and the recommended `v183_phcal` on the console before running them.
* L only measures v1.912's off-centre ramp. v1.912 has no calibration parameter yet, so its outer slices in Q–X may be degraded. Judge the comparisons on the centre slice.

## Part 2: per-shot navigators (11.2 min)

Single slice. Each scan has 4 volumes (b10, b1000 +x, b3000 +z, b6000 +z) and takes 2.8 min.

| Test | PPL | Navigator |
|---|---|---|
| M | v1.83 | 1 (volume only) |
| N | v1.83 | **2 (per shot)** |
| O | v1.912 | 1 |
| P | v1.912 | **2** |

On 10-11, b3000/b6000 along z had 20–35% phase-encode ghosting with navigator mode 1. Pass means N and P load, store 153 raw lines, reconstruct, and show clearly less z ghosting than M and O, with the b10 signal unchanged. Send me the MRDs and I'll quantify it.
* **If mode 2 works:** use Q–X below.
* **If it fails to load or acquire:** use the navigator mode 1 fallbacks with doubled letters (QQ, RR, SS, TT, UU, VV, WW, XX). They are otherwise identical.

## Part 3: matched v1.83 vs v1.912 comparisons (4.9 min each, 19.6 min)

Three slices at −2.8 / 0 / +2.8 mm, navigator mode 2, identical timing for both PPLs. ESP is 11 ms for both; v1.912's minimum is 10.

| Pair | v1.83 | v1.912 | Volumes |
|---|---|---|---|
| 1 | Q | R | b10; b1000 and b3000 along x, y, z (7) |
| 2 | S | T | b10; b2000 along 6 oblique directions (707, ±707, 0)-type (7) |

## Part 4: in-vivo rat brain, surface coil (60.2 min)

| Test | PPL | What | Volumes | Time |
|---|---|---|---:|---:|
| U | v1.83 | Quick check: b10, b1000 along x, y, z | 4 | 2.8 min |
| V | v1.912 | Quick check, matched to U | 4 | 2.8 min |
| W | v1.83 | Full: 3 × b10 and 12 directions at b1000, b3000 and b6000 | 39 | 27.3 min |
| X | v1.912 | Full, matched to W | 39 | 27.3 min |

All four use 3 slices at −2.8 / 0 / +2.8 mm, navigator mode 2 (fallbacks UU–XX), TR 2000, Δ30 / TE44.

The full scans are ordered by shell: b10, 12 × b1000, b10, 12 × b3000, b10, 12 × b6000. The first 26 volumes are therefore already a complete two-shell set. If time is short, run W and X with b6000 removed by editing the diffusion list (−8.4 min each).

**Surface-coil and in-vivo notes:**
* Repeat Part 0 A/B on the animal (1.4 min). Shim on the brain and re-check the frequency after shimming.
* Calibrate RF on the animal. With a surface coil, the flip angle varies with depth. v1.83 (CPMG with 180° pulses) tolerates this better than v1.912, whose prep, tip-up and variable flip angles are flip-sensitive. Expect v1.912 to lose signal away from the coil.
* The head is wider than the 35-mm FOV allows without wrap along phase encode. Place the brain near the coil and FOV centre, use an in-plane offset if needed, and keep it fixed. The FOV can be widened on the console if wrap covers the brain; the console recomputes the gradient scales.
* Monitor respiration. Without gating, respiratory motion is exactly what per-shot navigators (and ss-MGOT) must handle. Compare W against X on shot-to-shot ghosting, not only on SNR.
* b6000 along mixed directions needs the same peak gradient as along one axis. V ran b6000 x, y and z at Δ30 on 10-11 without rejection.

**12-direction set** (thousandths of a unit vector, logical read / phase / slice; electrostatic, minimum separation 39°):

| # | x | y | z | # | x | y | z |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | −468 | −435 | 769 | 7 | 492 | 641 | 589 |
| 2 | 448 | −77 | 891 | 8 | −506 | −856 | 110 |
| 3 | 178 | −694 | 698 | 9 | −200 | 184 | 962 |
| 4 | −790 | 374 | 486 | 10 | −925 | −280 | 256 |
| 5 | 188 | −981 | 55 | 11 | 917 | 86 | 389 |
| 6 | −200 | 783 | 589 | 12 | 781 | −587 | 214 |

## Reproduce and check

* `python experiments/2026-10-12_exvivo_invivo_plan/make_pprs.py` regenerates all PPRs, `manifest.json`, `run_order.csv` and the `protocol_notes.json` in each folder.
* `python experiments/2026-10-12_exvivo_invivo_plan/check_pprs.py` writes [validation.json](validation.json). All 32 protocols pass:
  * `NO_VIEWS` is a multiple of `VIEWS_PER_SEGMENT`;
  * every `:VAR` the PPL declares is present, in PPL order;
  * the diffusion lists fit (64 rows for v1.912, 512 for v1.83);
  * the event model maps each protocol, including its highest-b rows, with no error or minimum-timing messages, and emits 8 echoes per shot in navigator mode 1 and 9 in mode 2.
* These are source-model checks. The console is the final judge.
