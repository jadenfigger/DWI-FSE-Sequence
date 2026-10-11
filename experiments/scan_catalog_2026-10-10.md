# Scanner experiments — October 10, 2026

All 10 acquisitions were verified using their MRD-embedded PPR, adjacent PPR, reconstructed NIfTI header, JSON and diffusion sidecars, and each embedded protocol was diffed against the PPR it was planned from ([2026-10-09 ex-vivo plan](2026-10-09_exvivo_plan/README.md)). Scans are named by plan letter, so the main tables are in letter order; the chronology table gives actual acquisition-counter order. **Plan scan F (v1.8 polarity) was not acquired. Scan K was added and is not in the plan.** Embedded metadata takes precedence where PPRs differ (here, adjacent PPRs match the embedded protocol exactly for all ten). A version label identifies the recorded scanner PPL path; it does not prove the source/build used on the scanner.

**Sample provenance:** The plan expected a fixed ex-vivo rat brain in PBS, but the reconstructed images appear to be a water phantom (uniform disc, signal at the noise floor by b3000). Sample identity and temperature were not supplied — confirm with user. Until then, treat any tissue interpretation in the plan README as unverified.

All scans use centric phase encoding (`PE_order=1`), navigators on, stored TR 2000 ms, nominal diffusion duration δ=4 ms, ETL 8 (136 raw views = 128 imaging + 8 navigator), 128 readout samples, 128 imaging phase-encode lines, FOV 35 mm, 1 mm slice thickness and 1.2 mm slice separation, and read-axis (x) diffusion except where E and G add y, z and −x. Crusher plateaus are 1000 / 1000 µs with 200 µs ramps; first diffusion-echo crusher is −5482 DAC in all scans and every schedule is constant (`crusher_schedule=0`, so the stored 40% step in v1.8/v1.81 is inactive). All record RX gain 30, TX gain −203 and decoupler gain −453. Unless stated, TE is 54 ms, ESP is 14 ms (13 ms for v1.911, 11 ms for J and K), Δ is 40 ms and dwell is 50 µs (20 kHz). For the ss-MGOT scans TE 54 ms is the preparation echo, not the first acquired imaging echo. The plan PPRs carry no gain records, so gains were set on the console and are recorded here from the MRDs only. No temperature or ambient notes accompany the data.

Crusher entries are **first diffusion echo / train baseline** in DAC units. ETL means echo train length; navigator views are additional raw lines, not extra imaging lines. Directions are in the scanner logical axes as stored (x = read); b=0 volumes embed a nominal +x vector but carry no diffusion weighting.

**Protocol identity**

| Scan / PPR | Role | PPL path / method | Volumes | b-values (s/mm²) | Directions | Raw / imaging views / ETL | First / train crusher (DAC) |
|---|---|---|---:|---|---|---|---|
| [A](FSE-DWI_10-10-2026_v181_testA/FSE-DWI_10-10-2026_v181_testA.ppr) | v1.81, seven b | 1.81 — revised legacy (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl`) | 7 | 0, 100, 500, 1000, 2000, 3000, 6000 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −8223 |
| [B](FSE-DWI_10-10-2026_v1911_testB/FSE-DWI_10-10-2026_v1911_testB.ppr) | ss-MGOT v1.911, seven b | 1.911 — ss-MGOT revised (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl`) | 7 | 0, 100, 500, 1000, 2000, 3000, 6000 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −8223 |
| [C](FSE-DWI_10-10-2026_v18_testC/FSE-DWI_10-10-2026_v18_testC.ppr) | v1.8 control, seven b | 1.8 — legacy (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl`) | 7 | 0, 100, 500, 1000, 2000, 3000, 6000 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −8223 |
| [D](FSE-DWI_10-10-2026_v191_testD/FSE-DWI_10-10-2026_v191_testD.ppr) | v1.91 control, seven b | 1.91 — ss-MGOT (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl`) | 7 | 0, 100, 500, 1000, 2000, 3000, 6000 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −8223 |
| [E](FSE-DWI_10-10-2026_v181_testE/FSE-DWI_10-10-2026_v181_testE.ppr) | v1.81 directions incl. -x | 1.81 — revised legacy (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl`) | 8 | 0, 1000, 1000, 1000, 1000, 3000, 3000, 3000 | b0; b1000 +x, −x, +y, +z; b3000 +x, +y, +z | 136 / 128 / 8 | −5482 / −8223 |
| [G](FSE-DWI_10-10-2026_v1911_testG/FSE-DWI_10-10-2026_v1911_testG.ppr) | v1.911 directions incl. -x | 1.911 — ss-MGOT revised (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl`) | 8 | 0, 1000, 1000, 1000, 1000, 3000, 3000, 3000 | b0; b1000 +x, −x, +y, +z; b3000 +x, +y, +z | 136 / 128 / 8 | −5482 / −8223 |
| [H](FSE-DWI_10-10-2026_v181_testH/FSE-DWI_10-10-2026_v181_testH.ppr) | v1.81 train crusher = selector | 1.81 — revised legacy (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl`) | 3 | 0, 1000, 3000 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −2741 |
| [I](FSE-DWI_10-10-2026_v1911_testI/FSE-DWI_10-10-2026_v1911_testI.ppr) | v1.911 delta 30 / TE 44 | 1.911 — ss-MGOT revised (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl`) | 3 | 0, 1000, 3000 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −8223 |
| [J](FSE-DWI_10-10-2026_v181_testJ/FSE-DWI_10-10-2026_v181_testJ.ppr) | v1.81 40 kHz console change | 1.81 — revised legacy (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl`) | 3 | 0, 1000, 3000 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −8223 |
| [K](FSE-DWI_10-10-2026_v181_testK/FSE-DWI_10-10-2026_v181_testK.ppr) | v1.81 three slices (unplanned) | 1.81 — revised legacy (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl`) | 2 | 0, 1000 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −8223 |

**Timing, geometry, gains and plan agreement**

| Scan | ESP (ms) | TE (ms) | TR (ms) | Δ / δ (ms) | Dwell (µs) / bandwidth (kHz) | Slices (z offsets, mm) | RX / TX gain | Adjacent PPR discrepancy | Console-side change vs planned PPR |
|---|---:|---:|---:|---|---|---|---|---|---|
| A | 14 | 54 | 2000 | 40 / 4 | 50 / 20 | 1 (0) | 30 / −203 | None | None |
| B | 13 | 54 | 2000 | 40 / 4 | 50 / 20 | 1 (0) | 30 / −203 | None | None |
| C | 14 | 54 | 2000 | 40 / 4 | 50 / 20 | 1 (0) | 30 / −203 | None | None |
| D | 14 | 54 | 2000 | 40 / 4 | 50 / 20 | 1 (0) | 30 / −203 | None | None |
| E | 14 | 54 | 2000 | 40 / 4 | 50 / 20 | 1 (0) | 30 / −203 | None | None |
| G | 13 | 54 | 2000 | 40 / 4 | 50 / 20 | 1 (0) | 30 / −203 | None | None |
| H | 14 | 54 | 2000 | 40 / 4 | 50 / 20 | 1 (0) | 30 / −203 | None | None |
| I | 13 | 44 | 2000 | 30 / 4 | 50 / 20 | 1 (0) | 30 / −203 | None | None |
| J | 11 | 54 | 2000 | 40 / 4 | 25 / 40 | 1 (0) | 30 / −203 | None | `SMX` 0.0224563→0.0449126; `esp` 14→11; `gr_var` −735→−1471; `sample_period` 500/12 (50 µs, 20 kHz)→250/17 (25 µs, 40 kHz) |
| K | 11 | 54 | 2000 | 40 / 4 | 25 / 40 | 3 (−1.2, 0, 1.2) | 30 / −203 | None | diffusion list 7→2 volumes (plan→acquired); slices 1→3, z offsets 0→−1.2, 0, +1.2 mm (plan→acquired); `SMX` 0.0224563→0.0449126; `esp` 14→11; `gr_var` −735→−1471; `sample_period` 500/12 (50 µs, 20 kHz)→250/17 (25 µs, 40 kHz) (vs plan A) |

**Chronology and acquisition integrity**

| Scan | Counter order | Minutes from first scan | Minutes to next start | Experiments / nonzero raw slots | Reconstructed NIfTI shape | Diffusion sidecars |
|---|---:|---:|---:|---|---|---|
| A | 1 | 0.00 | 5.00 | 7 / 7 | 128 × 128 × 1 × 7 | JSON / bval / bvec match embedded protocol |
| B | 2 | 5.00 | 4.48 | 7 / 7 | 128 × 128 × 1 × 7 | JSON / bval / bvec match embedded protocol |
| C | 3 | 9.48 | 4.40 | 7 / 7 | 128 × 128 × 1 × 7 | JSON / bval / bvec match embedded protocol |
| D | 4 | 13.87 | 4.48 | 7 / 7 | 128 × 128 × 1 × 7 | JSON / bval / bvec match embedded protocol |
| E | 5 | 18.36 | 5.19 | 8 / 8 | 128 × 128 × 1 × 8 | JSON / bval / bvec match embedded protocol |
| G | 6 | 23.54 | 5.04 | 8 / 8 | 128 × 128 × 1 × 8 | JSON / bval / bvec match embedded protocol |
| H | 7 | 28.59 | 2.18 | 3 / 3 | 128 × 128 × 1 × 3 | JSON / bval / bvec match embedded protocol |
| I | 8 | 30.77 | 2.09 | 3 / 3 | 128 × 128 × 1 × 3 | JSON / bval / bvec match embedded protocol |
| J | 9 | 32.86 | 2.54 | 3 / 3 | 128 × 128 × 1 × 3 | JSON / bval / bvec match embedded protocol |
| K | 10 | 35.41 | — | 2 / 2 | 128 × 128 × 3 × 2 | JSON / bval / bvec match embedded protocol |

Counter times provide relative acquisition order, not clock times; the MRD file modification times all fall within about one second of each other (2026-10-10 20:09 UTC) and reflect copying, not acquisition. The order is A, B, C, D, E, G, H, I, J, K, i.e. plan-letter order with no exact protocol repeats (the plan's optional end-of-session repeat of A was not run, and no scan has an identical active protocol to another); the planned core order A → C → B → D was not followed, B was run second. F was skipped and K was added last. Start-to-start intervals include the acquisition itself, so the longest gaps (about 4.4–5.2 min) belong to the seven- and eight-volume scans and the shortest (about 2.1–2.6 min) to the three-volume scans H, I and J. All 55 experiment slots contain nonzero raw data (55 nonzero), K's 3 × 2 slice blocks are all nonzero, and all expected complex payloads are present; this is a completeness check, not evidence of good signal.

**Diffusion directions and sign convention**

E and G both contain a −x volume: volume 3 of 8 (b=1000) embeds `acq_x=-1000, acq_y=0, acq_z=0`, and the bvec file stores `-1.000000 0 0` for it, so the bvec preserves the embedded sign (`bvec = acq/1000`, no axis permutation or sign flip). Volumes in E and G are b0; b1000 +x, −x, +y, +z; b3000 +x, +y, +z, and the embedded arrays, bval, bvec and JSON agree. For b=0 the embedded arrays hold a nominal +x (1000, 0, 0) while the bvec holds a zero vector; this is the same convention as 10-07. The embedded values are thousandths of a unit vector in the scanner's logical read/phase/slice axes. Whether these axes map to the NIfTI voxel axes with the same sign has not been validated here, so a "−x" in the bvec is a sequence-side polarity, not a verified image-space direction.

**New-method parameters**

B, D, G and I record `v19_on=1` (D is the v1.91 control for B), two cycles of added dephasing across the imaging slice (`v19_cycles=2`) and a 1000 µs compensation-lobe plateau. The stored refocusing flip array is in tenths of a degree; the active ETL8 flips are 142.2°, 94.9°, 69.2°, 63.0°, 60.2°, 60°, 60°, 60° (variable flip angle, VFA), identical to 10-07 v1.91. v1.8/v1.81 do not expose the VFA array. All protocols store `rfcal=594`, `alpha=90` and `p180_scale=185`, but the revised branches bypass the legacy `alpha` and `p180_scale` controls; achieved flip angles remain physically unverified. The v1.911 and v1.91 scans additionally store prep slab width 3000 per mille, tip-up width 1667 per mille, spoiler moment 32 cycles/mm and spoiler amplitude 16384 DAC. In all v1.91 and v1.911 scans `crusher_step_pct=0`.

**v1.911 ESP 13 ms.** B, G and I use echo spacing 13 ms rather than the 14 ms of the v1.91 control (D) and of 10-07; this is the planned change made in the PPR (no console edit), and it is the only embedded difference besides the PPL path between B and D. Because the shorter spacing and the merged lobes of v1.911 change together, B versus D cannot separate them. v1.911 requires zero slice offset and angle, and all three v1.911 scans have one slice at offset 0.

**Controlled comparisons and co-changes**

The "recorded differences" column is generated from the acquired embedded protocols (acquisition arrays trimmed at `no_diff_acq`, first scan → second scan).

| Comparison | Intended factor | Recorded differences (first → second) | Interpretation / co-changes |
|---|---|---|---|
| A / C | v1.81 vs v1.8 at identical protocol | PPL 1.81→1.8 | Only the PPL path differs; every embedded protocol field, gain and array matches. This isolates the v1.81 b-value correction (and any other v1.81 source change) with no parameter co-change. C was acquired 9.5 min after A. |
| B / D | ss-MGOT v1.911 vs v1.91 | PPL 1.911→1.91; `esp` 13→14 | PPL path and ESP 13 vs 14 ms. Planned co-change: the ESP reduction and v1.911 source changes cannot be separated. All other fields, gains and arrays match. |
| E / A | Direction set (b0; b1000 +x, −x, +y, +z; b3000 +x, +y, +z) vs seven-b series | diffusion list (b / directions) 8→7 volumes | Same PPL, geometry, crusher −8223, gains and timing; only the diffusion list differs (8 vs 7 volumes). Not a b-matched comparison except b0, b1000 +x and b3000 +x. |
| G / B | Direction set on v1.911 | diffusion list (b / directions) 8→7 volumes | Same as E vs A for v1.911: only the diffusion list differs; ESP 13 in both. |
| H / A | Train crusher equal to selector (−2741) vs −8223 | diffusion list (b / directions) 3→7 volumes; `crush_amp` −2741→−8223 | Only the train crusher baseline differs plus the three-b list (0/1000/3000 vs seven b). First-echo crusher stays −5482. |
| I / B | Δ 30 / TE 44 vs Δ 40 / TE 54 on v1.911 | diffusion list (b / directions) 3→7 volumes; `big_delta` 30000→40000; `te` 44→54 | Δ and TE change together by 10 ms each (planned, accepted by the console; no further TE adjustment was needed), with the three-b list. ESP 13 in both. Diffusion time changes, so tissue ADC is not directly comparable. |
| J / A | 40 kHz readout bandwidth and shorter ESP vs 20 kHz | diffusion list (b / directions) 3→7 volumes; `SMX` 0.0449126→0.0224563; `esp` 11→14; `gr_var` −1471→−735; dwell 25→50 µs (40→20 kHz) | Console-side changes on J: dwell 50→25 µs, `sample_period` code 500/12→250/17, read gradient `gr_var` −735→−1471, `SMX` 0.0224563→0.0449126, ESP 14→11 ms. TE stays 54 ms and Δ stays 40 ms. The three-b list also differs. Bandwidth, ESP, readout gradient and echo-train length in time all change together. |
| K / A | Three slices vs one | diffusion list (b / directions) 2→7 volumes; slices 3→1 (stored per-slice orientation/offset arrays also differ); `SMX` 0.0449126→0.0224563; `esp` 11→14; `gr_var` −1471→−735; dwell 25→50 µs (40→20 kHz) | Same J console-side changes (dwell 25 µs, ESP 11, `gr_var`, `SMX`) plus three slices at z = −1.2, 0, +1.2 mm (NO_SLICES 3, FOV_SLICE_OFF −480/0/480) and a two-b list (0/1000). Not a clean slice test against A; use K vs J. |
| E / G | v1.81 vs v1.911 at the eight-volume direction set | PPL 1.81→1.911; `crusher_step_pct` 40→0; `esp` 14→13; `v19_comp_flat` —→1000; `v19_cycles` —→2; `v19_flip_tenths` array differs; `v19_on` —→1; `v19_slab_pml` —→3000; `v19_spoil_cpmm` —→32; `v19_spoil_dac` —→16384; `v19_tip_pml` —→1667 | PPL, ESP 14 vs 13, crusher step 40 vs 0 (inactive under constant schedule) and the v1.911 `v19_*` fields. Diffusion list, crusher −8223, gains and geometry match. |
| K / J | Three slices vs one at the same readout | diffusion list (b / directions) 2→3 volumes; slices 3→1 (stored per-slice orientation/offset arrays also differ) | Slice geometry and the b list (0/1000 vs 0/1000/3000) only; dwell, ESP, `gr_var`, `SMX` and everything else match. Cleanest multi-slice comparison. |

**Metadata details that affect comparisons**

Adjacent PPRs match the embedded protocol exactly for all ten scans (no stale or hand-edited PPRs). J and K's adjacent PPRs already contain the console changes. Scanner gains, gradient/RF/receiver delays and masks (`_pts_mask` 13, `_pdd_*_mask` 8, `_use_pdd` 0, all delays 0) occur only in the MRD. Compared with the plan, the only console-side changes are in J (bandwidth, ESP, readout gradient scale) and the unplanned K. In particular, I's TE 44 and Δ 30 ms, the ESP 13 settings of B, G and I, and all b and direction lists are exactly as planned.

The v1.8/v1.81 arrays reserve 512 entries and the v1.91/v1.911 arrays 64; only the first `no_diff_acq` entries are active. `acq_grad` is an inactive cache in b-input mode 1 (stale from the 10-07 base protocols), as noted in the plan generator. The standalone PPR filenames match their scan folders. Scan K has three slices, so its reconstructed NIfTI is 128 × 128 × 3 × 2 with the JSON slice offsets −1.2, 0, 1.2 mm and NIfTI slice pixdim 1.2 mm; the other nine scans are single-slice.

All b-values are requested values. The v1.8 read-axis cross term makes the effective b differ from nominal for +x versus −x; the plan predicts about 1176 and 842 at nominal b1000. No F scan was acquired, and E and G use the revised v1.81 / v1.911 sources, so this effect is not directly measured today. Matching metadata does not validate the effective b-tensor or gradient calibration.

**Cross-day notes (vs October 7)**

RX gain is 30 on both days and decoupler gain is −453 on both, but TX gain is −203 today versus −195 on 10-07 (and −205 on 10-05). The gain-to-amplitude conversion has not been validated, so brightness comparisons across days confound sequence and gain changes. Embedded protocols otherwise inherit the 10-07 base protocols: 
- C vs 10-07 test1: diffusion list (b / directions) 3→7 volumes; `_ObserveTransmitGain` −195→−203.
- A vs 10-07 test1: diffusion list (b / directions) 3→7 volumes; PPL 1.8→1.81; `_ObserveTransmitGain` −195→−203.
- D vs 10-07 test2: diffusion list (b / directions) 3→7 volumes; `_ObserveTransmitGain` −195→−203.
- B vs 10-07 test2: diffusion list (b / directions) 3→7 volumes; PPL 1.91→1.911; `_ObserveTransmitGain` −195→−203; `esp` 14→13.

Today's sample appears to be a water phantom again, but this is unconfirmed. Geometry, phase-encode calibration (`gp_init_var=-1000`, `SMY=0.0305406`, ETL 8), RF scales and crusher baselines equal those of 10-07 test1/test2 apart from the items above.

The [complete comparison CSV](../docs/data/oct10_scan_comparison.csv) includes common important parameters and every new-method control. The [protocol audit](../docs/data/oct10_protocol_audit.md), [all varying embedded fields](../docs/data/oct10_protocol_variations.csv), [scan metadata CSV](../docs/data/oct10_protocol_scans.csv) and [all 45 pair comparisons](../docs/data/oct10_protocol_pairs.csv) retain the full differences. Rebuild the catalog and audit with `python docs/data/oct10_protocol_audit.py`.
