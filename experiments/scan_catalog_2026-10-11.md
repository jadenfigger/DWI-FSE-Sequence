# Scanner experiments — October 11, 2026

All 19 acquisitions were verified using their MRD-embedded PPR, adjacent PPR, reconstructed NIfTI header where one exists, JSON and diffusion sidecars where they exist, and each embedded protocol was diffed against the console-compatible PPR it was run from and against the original plan ([2026-10-11 ex-vivo plan](2026-10-11_exvivo_plan/README.md); [console-compatible copies](2026-10-11_exvivo_plan_console_fixed/README.md)). Scans are named by plan letter and listed in plan order, with the unplanned repeats TT and UU after T and U and the unplanned v1.911-0 last; the chronology table gives actual acquisition-counter order. **Planned scans D, F, H, J, L, P, R, Z, AA and AC were not acquired. AD has a PPR and protocol_notes.json but no MRD. The v182_testUU folder is empty; the acquired UU scan is in v1912_testUU. The guard tests W, X and Y have no acquisition records.** Embedded metadata takes precedence where PPRs differ (here, adjacent PPRs match the embedded protocol exactly for all 19 scans). A version label identifies the recorded scanner PPL path; it does not prove the source/build used on the scanner. The operator reports that every v1.912 scan and v1.911-0 produced essentially noise; the reconstructions confirm it (navigator echo 1 at 1-12x noise against about 250x for v1.82; see the [10-11 report](../docs/physical_scanner_experiments_2026-10-11.md)).

**Sample provenance:** The images show the planned sample: a fixed rat brain (coronal sections) held at the bottom of a PBS-filled tube by a three-spoke holder with beads along one spoke. The brain occupies about a quarter of the PBS disk. Fixation history and bore temperature were not supplied. **The centre frequency was about 2.8 kHz off resonance during this session** (bandwidth-dependent readout shift; see the report), and the sample sits about 4 mm from isocentre along the phase-encode axis, so the 128-matrix scans without an in-plane offset wrap the bottom of the tube into the top of the image.

All scans use centric phase encoding (`PE_order=1`), one average (`NO_AVERAGES=1`), navigator volumes (`nav_on=1`) and ETL 8. Stored TR is 1000 ms except v1.911-0 and V (2000 ms) and UU (5000 ms). Raw views are 136 for the 128-line scans (128 imaging + 8 navigator views) and 264 for V (256 + 8); samples are 128 for the 128-matrix scans and 256 for V. FOV is 35 mm and slices are 1 mm thick. The nominal diffusion duration δ is 4 ms in every scan. Unless stated, TE is 54 ms, ESP is 14 ms and dwell is 50 µs (20 kHz). Crusher plateaus are 1000 / 1000 µs with 200 µs ramps and every schedule is constant (`crusher_schedule=0`, `crusher_step_pct=0`). First diffusion-echo and train crusher values are tabulated below. The planned per-shot navigators (`nav_on=2`) were not acquired; the console-compatible copies were run with `nav_on=1` (see the metadata section). The planned PPRs carry no gain records, so gains are recorded here from the MRDs only.

Crusher entries are **first diffusion echo / train baseline** in DAC units. ETL means echo train length; navigator views are additional raw lines, not extra imaging lines. Directions are in the scanner logical axes as stored (x = read); b=0 volumes embed a nominal +x vector but carry no diffusion weighting.

**Protocol identity**

| Scan / PPR | Role | PPL path / method | Volumes | b-values (s/mm²) | Directions | Raw / imaging views / ETL | First / train crusher (DAC) |
|---|---|---|---:|---|---|---|---|
| [A](FSE-DWI_10-11-2026_v182_testA/FSE-DWI_10-11-2026_v182_testA.ppr) | Load/compile, low-b E1 diagnostic, tissue/PBS high-b baseline | 1.82 — v1.82 (plan label; no method label in plan generator) (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.82.ppl`) | 7 | 0, 5, 10, 20, 100, 1000, 6000 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −8223 |
| [B](FSE-DWI_10-11-2026_v1912_testB/FSE-DWI_10-11-2026_v1912_testB.ppr) | Load/compile, matched ss-MGOT baseline and low-b/high-b diagnostic | 1.912 — ss-MGOT v1.912 (plan label) (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.912.ppl`) | 7 | 0, 5, 10, 20, 100, 1000, 6000 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −8223 |
| [C](FSE-DWI_10-11-2026_v182_testC/FSE-DWI_10-11-2026_v182_testC.ppr) | PBS ADC and axis calibration: +/-x,+/-y,+/-z at b500/b1000; bracketed reference | 1.82 — v1.82 (plan label; no method label in plan generator) (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.82.ppl`) | 14 | 10, 500, 500, 500, 500, 500, 500, 1000, 1000, 1000, 1000, 1000, 1000, 10 | b10 +x, +x; b500 +x, −x, +y, −y, +z, −z; b1000 +x, −x, +y, −y, +z, −z | 136 / 128 / 8 | −5482 / −8223 |
| [AB](FSE-DWI_10-11-2026_v182_testAB/FSE-DWI_10-11-2026_v182_testAB.ppr) | Mixed-axis b1000 direction (577,577,577), for future non-axis direction sets | 1.82 — v1.82 (plan label; no method label in plan generator) (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.82.ppl`) | 1 | 1000 | b1000 (0.577x, 0.577y, 0.577z) | 136 / 128 / 8 | −5482 / −8223 |
| [E](FSE-DWI_10-11-2026_v182_testE/FSE-DWI_10-11-2026_v182_testE.ppr) | 40-kHz minimum ESP, short-T2 benefit and high-b cleanliness | 1.82 — v1.82 (plan label; no method label in plan generator) (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.82.ppl`) | 3 | 10, 1000, 6000 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −8223 |
| [G](FSE-DWI_10-11-2026_v182_testG/FSE-DWI_10-11-2026_v182_testG.ppr) | 40-kHz minimum ESP + 1 ms timing control | 1.82 — v1.82 (plan label; no method label in plan generator) (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.82.ppl`) | 1 | 10 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −8223 |
| [I](FSE-DWI_10-11-2026_v182_testI/FSE-DWI_10-11-2026_v182_testI.ppr) | 20-kHz minimum ESP + 1 ms timing control | 1.82 — v1.82 (plan label; no method label in plan generator) (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.82.ppl`) | 1 | 10 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −8223 |
| [M](FSE-DWI_10-11-2026_v182_testM/FSE-DWI_10-11-2026_v182_testM.ppr) | Single-slice nav2 control against E; crosstalk reference for K/O/S | 1.82 — v1.82 (plan label; no method label in plan generator) (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.82.ppl`) | 2 | 10, 1000 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −8223 |
| [N](FSE-DWI_10-11-2026_v1912_testN/FSE-DWI_10-11-2026_v1912_testN.ppr) | Single-slice nav2 control against F; crosstalk reference for L/P | 1.912 — ss-MGOT v1.912 (plan label) (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.912.ppl`) | 2 | 10, 1000 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −8223 |
| [K](FSE-DWI_10-11-2026_v182_testK/FSE-DWI_10-11-2026_v182_testK.ppr) | K-style off-centre phase and tight-gap crosstalk with shot navigators | 1.82 — v1.82 (plan label; no method label in plan generator) (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.82.ppl`) | 3 | 0, 10, 1000 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −8223 |
| [O](FSE-DWI_10-11-2026_v182_testO/FSE-DWI_10-11-2026_v182_testO.ppr) | Large off-centre RF phase at +/-5 mm | 1.82 — v1.82 (plan label; no method label in plan generator) (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.82.ppl`) | 1 | 10 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −8223 |
| [Q](FSE-DWI_10-11-2026_v182_testQ/FSE-DWI_10-11-2026_v182_testQ.ppr) | Delta30/TE44 tissue benefit and high-b gradient headroom with nav2 | 1.82 — v1.82 (plan label; no method label in plan generator) (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.82.ppl`) | 3 | 10, 1000, 6000 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −8223 |
| [S](FSE-DWI_10-11-2026_v182_testS/FSE-DWI_10-11-2026_v182_testS.ppr) | 2.4-mm gap crosstalk qualification before final pilot | 1.82 — v1.82 (plan label; no method label in plan generator) (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.82.ppl`) | 1 | 10 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −8223 |
| [T](FSE-DWI_10-11-2026_v182_testT/FSE-DWI_10-11-2026_v182_testT.ppr) | End-of-tests drift repeat against A (b10/b1000) | 1.82 — v1.82 (plan label; no method label in plan generator) (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.82.ppl`) | 2 | 10, 1000 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −8223 |
| [TT](FSE-DWI_10-11-2026_v182_testTT/FSE-DWI_10-11-2026_v182_testTT.ppr) | Unplanned: T with in-plane FOV offset (read +3.99875, phase −6.0025 mm) | 1.82 — v1.82 (plan label; no method label in plan generator) (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.82.ppl`) | 2 | 10, 1000 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −8223 |
| [U](FSE-DWI_10-11-2026_v1912_testU/FSE-DWI_10-11-2026_v1912_testU.ppr) | End-of-tests drift repeat against B (b10/b1000) | 1.912 — ss-MGOT v1.912 (plan label) (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.912.ppl`) | 2 | 10, 1000 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −8223 |
| [UU](FSE-DWI_10-11-2026_v1912_testUU/FSE-DWI_10-11-2026_v1912_testUU.ppr) | Unplanned: U with the same in-plane offset, TR 5000, TE 34, Δ 20 ms, single b10 | 1.912 — ss-MGOT v1.912 (plan label) (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.912.ppl`) | 1 | 10 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −8223 |
| [V](FSE-DWI_10-11-2026_v182_testV/FSE-DWI_10-11-2026_v182_testV.ppr) | Final ex-vivo pilot: 256x256, 3 slices, 1 average, Delta30, 3 directions/shell | 1.82 — v1.82 (plan label; no method label in plan generator) (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.82.ppl`) | 10 | 10, 1000, 1000, 1000, 3000, 3000, 3000, 6000, 6000, 6000 | b10 +x; b1000 +x, +y, +z; b3000 +x, +y, +z; b6000 +x, +y, +z | 264 / 256 / 8 | −5482 / −8223 |
| [v1.911-0](FSE-DWI_10-11-2026_v1911_test0/FSE-DWI_10-11-2026_v1911_test0.ppr) | Unplanned: 10-10 scan I protocol at new gains (RX 180, TX −129) | 1.911 — ss-MGOT revised (`G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl`) | 3 | 0, 1000, 3000 | +x (read) for every b>0 | 136 / 128 / 8 | −5482 / −8223 |

**Timing, geometry, gains and plan agreement**

| Scan | ESP (ms) | TE (ms) | TR (ms) | Δ / δ (ms) | Dwell (µs) / bandwidth (kHz) | Slices (z offsets, mm) | RX / TX gain | Adjacent PPR discrepancy | Console-side change vs planned PPR |
|---|---:|---:|---:|---|---|---|---|---|---|
| A | 14 | 54 | 1000 | 40 / 4 | 50 / 20 | 1 (0) | 180 / −129 | None | None vs console-compatible PPR |
| B | 13 | 54 | 1000 | 40 / 4 | 50 / 20 | 1 (0) | 180 / −129 | None | None vs console-compatible PPR |
| C | 14 | 54 | 1000 | 40 / 4 | 50 / 20 | 1 (0) | 180 / −129 | None | None vs console-compatible PPR |
| AB | 11 | 54 | 1000 | 40 / 4 | 25 / 40 | 1 (0) | 0 / −129 | None | None vs console-compatible PPR |
| E | 11 | 54 | 1000 | 40 / 4 | 25 / 40 | 1 (0) | 0 / −129 | None | None vs console-compatible PPR |
| G | 12 | 54 | 1000 | 40 / 4 | 25 / 40 | 1 (0) | 0 / −129 | None | None vs console-compatible PPR |
| I | 15 | 54 | 1000 | 40 / 4 | 50 / 20 | 1 (0) | 0 / −129 | None | None vs console-compatible PPR |
| M | 11 | 54 | 1000 | 40 / 4 | 25 / 40 | 1 (0) | 0 / −129 | None | None vs console-compatible PPR (original plan: nav_on 2→1; raw views 153→136; workaround in console-compatible copy) |
| N | 10 | 54 | 1000 | 40 / 4 | 25 / 40 | 1 (0) | 0 / −129 | None | None vs console-compatible PPR (original plan: nav_on 2→1; raw views 153→136; workaround in console-compatible copy) |
| K | 11 | 54 | 1000 | 40 / 4 | 25 / 40 | 3 (−1.2, 0, 1.2) | 0 / −129 | None | None vs console-compatible PPR (original plan: FOV_OFFSETS rows restored (original plan had count only); nav_on 2→1; raw views 153→136; workaround in console-compatible copy) |
| O | 11 | 54 | 1000 | 40 / 4 | 25 / 40 | 3 (−5, 0, 5) | 0 / −129 | None | None vs console-compatible PPR (original plan: FOV_OFFSETS rows restored (original plan had count only); nav_on 2→1; raw views 153→136; workaround in console-compatible copy) |
| Q | 11 | 44 | 1000 | 30 / 4 | 25 / 40 | 1 (0) | 0 / −129 | None | None vs console-compatible PPR (original plan: nav_on 2→1; raw views 153→136; workaround in console-compatible copy) |
| S | 11 | 54 | 1000 | 40 / 4 | 25 / 40 | 3 (−2.4, 0, 2.4) | 0 / −129 | None | None vs console-compatible PPR (original plan: FOV_OFFSETS rows restored (original plan had count only); nav_on 2→1; raw views 153→136; workaround in console-compatible copy) |
| T | 14 | 54 | 1000 | 40 / 4 | 50 / 20 | 1 (0) | 0 / −129 | None | None vs console-compatible PPR |
| TT | 14 | 54 | 1000 | 40 / 4 | 50 / 20 | 1 (0) | 0 / −129 | None | in-plane FOV offset (read, phase) 0, 0→3.99875, −6.0025 mm [unplanned; reference T] |
| U | 13 | 54 | 1000 | 40 / 4 | 50 / 20 | 1 (0) | 0 / −129 | None | None vs console-compatible PPR |
| UU | 13 | 34 | 5000 | 20 / 4 | 50 / 20 | 1 (0) | 0 / −129 | None | diffusion list 2→1 volumes (b 10/1000 → 10); in-plane FOV offset (read, phase) 0, 0→3.99875, −6.0025 mm; Δ 40→20 ms; TE 54→34 ms; TR 1000→5000 ms [unplanned; reference U] |
| V | 14 | 44 | 2000 | 30 / 4 | 25 / 40 | 3 (−2.4, 0, 2.4) | 0 / −129 | None | in-plane FOV offset (read, phase) 0, 0→3.99875, −6.0025 mm; `gp_init_var` −1941→−1942 (original plan: nav_on 2→1; raw views 297→264; workaround in console-compatible copy) |
| v1.911-0 | 13 | 44 | 2000 | 30 / 4 | 50 / 20 | 1 (0) | 180 / −129 | None | None vs 10-10 scan I protocol (scanner gains differ; see gains) |

Gains are recorded from the MRDs only. RX gain is 180 for A, B, C and v1.911-0 and 0 for all other scans; TX gain is −129 throughout (−203 on 2026-10-10). Decoupler gain is −453 throughout.

**Chronology and acquisition integrity**

| Scan | Counter order | Minutes from first scan | Minutes to next start | Experiments / nonzero raw slots | Reconstructed NIfTI shape | Diffusion sidecars |
|---|---:|---:|---:|---|---|---|
| A | 1 | 0.00 | 2.59 | 7 / 7 | 128 × 128 × 1 × 7 | JSON / bval / bvec match embedded protocol |
| B | 2 | 2.59 | 2.72 | 7 / 7 | 128 × 128 × 1 × 7 | JSON / bval / bvec match embedded protocol |
| C | 3 | 5.31 | 7.59 | 14 / 14 | — | none in folder (protocol_notes.json only) |
| AB | 5 | 19.84 | 0.75 | 1 / 1 | 128 × 128 × 1 × 1 | JSON / bval / bvec match embedded protocol |
| E | 6 | 20.59 | 1.35 | 3 / 3 | 128 × 128 × 1 × 3 | JSON / bval / bvec match embedded protocol |
| G | 7 | 21.94 | 0.91 | 1 / 1 | — | none in folder (protocol_notes.json only) |
| I | 8 | 22.84 | 19.04 | 1 / 1 | — | none in folder (protocol_notes.json only) |
| M | 9 | 41.88 | 2.48 | 2 / 2 | 128 × 128 × 1 × 2 | JSON / bval / bvec match embedded protocol |
| N | 19 | 70.01 | — | 2 / 2 | 128 × 128 × 1 × 2 | JSON / bval / bvec match embedded protocol |
| K | 10 | 44.36 | 1.24 | 3 / 3 | 128 × 128 × 3 × 3 | JSON / bval / bvec match embedded protocol |
| O | 11 | 45.60 | 0.72 | 1 / 1 | 128 × 128 × 3 × 1 | JSON / bval / bvec match embedded protocol |
| Q | 12 | 46.31 | 1.38 | 3 / 3 | — | none in folder (MRD and PPR only) |
| S | 13 | 47.69 | 0.70 | 1 / 1 | 128 × 128 × 3 × 1 | JSON / bval / bvec match embedded protocol |
| T | 14 | 48.39 | 1.29 | 2 / 2 | 128 × 128 × 1 × 2 | JSON / bval / bvec match embedded protocol |
| TT | 16 | 52.83 | 2.65 | 2 / 2 | 128 × 128 × 1 × 2 | JSON / bval / bvec match embedded protocol |
| U | 15 | 49.69 | 3.15 | 2 / 2 | 128 × 128 × 1 × 2 | JSON / bval / bvec match embedded protocol |
| UU | 18 | 67.85 | 2.16 | 1 / 1 | 128 × 128 × 1 × 1 | JSON / bval / bvec match embedded protocol |
| V | 17 | 55.48 | 12.37 | 10 / 10 | 256 × 256 × 3 × 10 | JSON / bval / bvec match embedded protocol |
| v1.911-0 | 4 | 12.90 | 6.94 | 3 / 3 | 128 × 128 × 1 × 3 | JSON / bval / bvec match embedded protocol |

Counter times provide relative acquisition order, not clock times. The order is A, B, C, v1.911-0, AB, E, G, I, M, K, O, Q, S, T, U, TT, V, UU, N. All 66 volumes contain nonzero raw data (66 nonzero), including every slice block of the three-slice scans K, O, S and V; this is a completeness check, not evidence of good signal.

Start-to-start intervals include each acquisition. The RX gain changes once in the session: 180 for A, B, C and v1.911-0 (counters 0.00–12.90 min) and 0 from AB (19.84 min) onward. No PPR records this change, and the gains exist only in the MRDs. The longest intervals are 19.04 min between I and M, which no record explains, and 12.37 min after V, which matches V's planned 12.33-min scan. C's 7.59-min interval exceeds its planned 4.9-min scan by 2.7 min, also unexplained.

**Diffusion directions and sign convention**

E has b10, b1000 and b6000 volumes, all along +x. M, G, I, K, O, Q, S, T, TT, U, UU and v1.911-0 use +x for every b>0 volume (see the protocol identity table). V adds +y and +z at each of its three shells. AB is one b1000 volume along (577, 577, 577)/1000. Its bvec is normalised to unit length (0.577350 per axis), while the MRD stores the rounded integers (vector norm 0.9993); the bmatrix diagonal (333.3 s/mm²) follows the normalised vector. C has ±x, ±y and ±z at b500 and b1000 with two b10 references; C has no sidecars, so its signs are checked against the MRD arrays only. Every b=0 volume embeds a nominal +x vector (1000, 0, 0) with a zero bvec. The bvec is the embedded direction normalised to unit length with no axis permutation or sign flip, the same convention as 2026-10-10. The logical axes have not been mapped to NIfTI image axes here.

**New-method parameters**

B, N, U, UU and v1.911-0 record identical new-method fields: `v19_on=1`, `v19_cycles=2`, a 1000 µs compensation-lobe plateau, prep slab width 3000 per mille, tip-up width 1667 per mille, spoiler moment 32 cycles/mm and spoiler amplitude 16384 DAC. The v1.82 scans do not expose these fields. The active ETL8 flip angles are 142.2°, 94.9°, 69.2°, 63°, 60.2°, 60°, 60°, 60° (variable flip angle, VFA, on the v1.912 / v1.911 scans). All protocols store `rfcal=594`, `alpha=90` and `p180_scale=185`; the revised branches bypass the legacy `alpha` and `p180_scale` controls, so achieved flip angles remain unverified.

**Controlled comparisons and co-changes**

The "recorded differences" column is generated from the acquired embedded protocols (acquisition arrays trimmed at `no_diff_acq`, first scan → second scan). Gain differences are listed separately as scanner records.

| Comparison | Intended factor | Recorded differences (first → second) | Interpretation / co-changes |
|---|---|---|---|
| A / B | v1.82 vs v1.912 at the matched seven-b 20-kHz baseline | PPL 1.82→1.912; ESP 14→13 ms | Same b-list and gains (RX 180, TX −129). Only the PPL (1.82 vs 1.912) and ESP (14 vs 13 ms) differ, so the ss-MGOT source change and the ESP change cannot be separated. |
| A / T | Drift repeat of A (two volumes, b10/b1000) | diffusion list 7→2 volumes (b 0/5/10/20/100/1000/6000 → 10/1000); scanner records: `_ObserveReceiverGain` 180→0 | Drift-repeat pair, but RX gain changed from 180 (A) to 0 (T) between the two scans. The gain change confounds any drift measurement; the b10 and b1000 volumes and timing are otherwise matched. |
| B / U | Drift repeat of B (two volumes, b10/b1000) | diffusion list 7→2 volumes (b 0/5/10/20/100/1000/6000 → 10/1000); scanner records: `_ObserveReceiverGain` 180→0 | Drift-repeat pair with the same RX 180 → 0 gain change as A/T; PPL, ESP, Δ and dwell match. |
| M / N | Planned matched navigator pair (acquired as volume navigators in both) | PPL 1.82→1.912; ESP 11→10 ms | Both were planned as nav2 controls but were acquired as nav1 volume-navigator scans, so this is a v1.82 vs v1.912 single-slice repeat, not a navigator comparison. |
| E / M | Planned nav2 control against E (acquired nav1 in both) | diffusion list 3→2 volumes (b 10/1000/6000 → 10/1000) | M was planned as the nav2 control for E but was acquired with nav1, so the pair differs only by the volume list (M has no b6000). This is a repeat, not a navigator test. |
| E / G | 40-kHz ESP 11 vs 12 ms with the three-volume vs single-volume lists | diffusion list 3→1 volumes (b 10/1000/6000 → 10); ESP 11→12 ms | Same 40-kHz readout and gains. G is the ESP-12 timing control with a single b10 volume; ESP 11 → 12 ms is the only timing change. |
| G / I | 40-kHz vs 20-kHz readout at ESP 12 vs 15 ms | `SMX` 0.0449126→0.0224563; ESP 12→15 ms; `gr_var` −1471→−735; dwell 25→50 µs (40→20 kHz) | Bandwidth, ESP and readout gradient change together: 40 kHz at ESP 12 vs 20 kHz at ESP 15, with SMX and gr_var scaled to match. The pair cannot separate bandwidth from ESP. |
| Q / E | Δ30 / TE44 vs Δ40 / TE54 at 40 kHz | Δ 30→40 ms; TE 44→54 ms | Planned Δ30 / TE44 change: Δ and TE move together by 10 ms, with the same ESP 11, 40-kHz readout and b10/b1000/b6000 list. Diffusion time differs, so ADC is not directly comparable. |
| K / O | Spacing and off-centre phase: ±1.2 mm (three volumes) vs ±5 mm (one volume) | diffusion list 3→1 volumes (b 0/10/1000 → 10); z offsets −1.2, 0, 1.2→−5, 0, 5 mm; slice separation 1.2→5 mm | Different slice geometry and b-list: K has three volumes at ±1.2 mm; O has one volume at ±5 mm. Neither is a clean spacing comparison. |
| O / S | Off-centre slice spacing: ±5 mm vs ±2.4 mm | z offsets −5, 0, 5→−2.4, 0, 2.4 mm; slice separation 5→2.4 mm | Clean geometry-only contrast: both have three slices, one b10 volume and the same readout; only the slice separation changes (5 vs 2.4 mm). |
| K / S | Slice spacing: ±1.2 mm vs ±2.4 mm | diffusion list 3→1 volumes (b 0/10/1000 → 10); z offsets −1.2, 0, 1.2→−2.4, 0, 2.4 mm; slice separation 1.2→2.4 mm | Spacing and b-list differ together: ±1.2 mm with three volumes (K) vs ±2.4 mm with one b10 volume (S). Use O/S for geometry alone. |
| T / TT | In-plane FOV offset only (read +3.99875, phase −6.0025 mm) | in-plane FOV offset (read, phase) 0, 0→3.99875, −6.0025 mm | Clean in-plane offset contrast on the same T protocol: read 3.99875 mm and phase −6.0025 mm (FOV_READ_OFF 457, FOV_PHASE_OFF −686 DAC). Unplanned. |
| U / UU | Single-b10 variant with TR 5000, TE 34, Δ 20 ms and the same in-plane offset | diffusion list 2→1 volumes (b 10/1000 → 10); in-plane FOV offset (read, phase) 0, 0→3.99875, −6.0025 mm; Δ 40→20 ms; TE 54→34 ms; TR 1000→5000 ms | Not a clean offset contrast: UU also changes TR (5000 ms), TE (34 ms), Δ (20 ms) and the b-list (single b10), in addition to the same in-plane offset. |
| S / V | Same ±2.4-mm spacing: one-volume 128 matrix vs 256 matrix, 10-volume pilot | diffusion list 1→10 volumes (b 10 → 10/1000/1000/1000/3000/3000/3000/6000/6000/6000); in-plane FOV offset (read, phase) 0, 0→3.99875, −6.0025 mm; `SMY` 0.0305406→0.0592847; Δ 40→30 ms; ESP 11→14 ms; `gp_init_var` −1000→−1942; samples 128→256; raw views 136→264; TE 54→44 ms; TR 1000→2000 ms | Same ±2.4-mm spacing, but V has 256 samples and 256 imaging lines, ten volumes, ESP 14, TE 44, Δ 30, TR 2000, the in-plane offset, and rescaled SMY and gp_init_var for the 256 matrix. Not a controlled comparison; it shows how the final pilot differs from S. |

**Metadata details that affect comparisons**

Adjacent PPRs match the embedded protocol for every scan (scanner records excluded). The folder PPRs of A, B, C, AB, E, G, I, M, N, K, O, Q, S, T, U are byte-identical to the console-compatible copies, and their embedded protocols match those copies. TT, UU, V differ from their reference, for the in-plane offsets and the UU reduced protocol described below; v1.911-0 has no console-compatible copy and is compared with the 2026-10-10 scan I MRD.

The embedded protocols match the console-compatible copies, not the original plan PPRs. The original PPRs for M, N, K, O, Q, S and V use `nav_on=2` (153 raw views, or 297 for V), and K, O, S and V also lack FOV_OFFSETS rows (the original stores only a count). Every one of these seven scans was acquired with `nav_on=1` and the console-compatible raw views. None of them is therefore a per-shot navigator test.

**In-plane FOV offsets.** V, TT and UU carry read/phase offsets of 3.99875 / −6.0025 mm, recorded as FOV_READ_OFF 457 and FOV_PHASE_OFF −686 DAC on every slice. No planned PPR contains them, and every other scan has zero in-plane offset. For V this is the one console-side geometry change to the final pilot. V's gp_init_var is also −1942 against the planned −1941. The records do not explain this one-unit change.

Scanner gains, gradient/RF/receiver delays and masks (`_pts_mask`, `_pdd_*_mask`, `_use_pdd`, `*Delay`) occur only in the MRD. The gains are discussed above; delays and masks are identical across scans and are not deviations from the plan.

Sidecars are missing for C, G, I and Q (no bval, bvec or JSON; NIfTI is also missing for those four). Q also has no protocol_notes.json. B's diffusion sidecars use the lowercase `testb` stem. Every one of the 15 JSON files reports `BMatrixSource` as `nominal-fallback` with the warning "repo PPL not found" for its PPL version, and `EffectiveBValue` equals the nominal b-values. No effective-b model was applied by that reconstruction, and the `_beff.bval` files repeat the nominal b-values. The model itself resolves the repository PPLs on this machine; per-volume effective b-matrices for all 19 scans are in [oct11_effective_b.csv](../docs/data/oct11_effective_b.csv) (`python docs/data/oct11_effective_b.py`). For v1.82 the b10-to-b1000 trace difference is 986.4 s/mm² along ±x/±y (nominal 990), and the b1000 ±z traces of C are 1038.1 / 963.5.

**Cross-day notes (vs October 10)**

RX gain is 30 on 2026-10-10 and 180 (A, B, C, v1.911-0) or 0 (all others) on 2026-10-11. TX gain is −203 on 2026-10-10 and −129 on 2026-10-11, and decoupler gain is −453 on both days. Sequence, gain and b-list changes therefore co-vary across days; brightness comparisons across days confound gain changes. The same-letter comparisons below use the 2026-10-10 MRDs (embedded protocol, active fields only).

- A vs 2026-10-10 v181_testA: diffusion list 7 volumes, b 0/100/500/1000/2000/3000/6000 → 0/5/10/20/100/1000/6000; PPL 1.81→1.82; `crusher_step_pct` 40→0; TR 2000→1000 ms; scanner records: `_ObserveReceiverGain` 30→180; `_ObserveTransmitGain` −203→−129.
- B vs 2026-10-10 v1911_testB: diffusion list 7 volumes, b 0/100/500/1000/2000/3000/6000 → 0/5/10/20/100/1000/6000; PPL 1.911→1.912; TR 2000→1000 ms; scanner records: `_ObserveReceiverGain` 30→180; `_ObserveTransmitGain` −203→−129.
- C vs 2026-10-10 v18_testC: diffusion list 7→14 volumes (b 0/100/500/1000/2000/3000/6000 → 10/500/500/500/500/500/500/1000/1000/1000/1000/1000/1000/10); directions differ; PPL 1.8→1.82; `crusher_step_pct` 40→0; TR 2000→1000 ms; scanner records: `_ObserveReceiverGain` 30→180; `_ObserveTransmitGain` −203→−129.
- E vs 2026-10-10 v181_testE: diffusion list 8→3 volumes (b 0/1000/1000/1000/1000/3000/3000/3000 → 10/1000/6000); directions differ; PPL 1.81→1.82; `SMX` 0.0224563→0.0449126; `crusher_step_pct` 40→0; ESP 14→11 ms; `gr_var` −735→−1471; dwell 50→25 µs (20→40 kHz); TR 2000→1000 ms; scanner records: `_ObserveReceiverGain` 30→0; `_ObserveTransmitGain` −203→−129.
- G vs 2026-10-10 v1911_testG: diffusion list 8→1 volumes (b 0/1000/1000/1000/1000/3000/3000/3000 → 10); PPL 1.911→1.82; `SMX` 0.0224563→0.0449126; ESP 13→12 ms; `gr_var` −735→−1471; dwell 50→25 µs (20→40 kHz); TR 2000→1000 ms; scanner records: `_ObserveReceiverGain` 30→0; `_ObserveTransmitGain` −203→−129.
- I vs 2026-10-10 v1911_testI: diffusion list 3→1 volumes (b 0/1000/3000 → 10); PPL 1.911→1.82; Δ 30→40 ms; ESP 13→15 ms; TE 44→54 ms; TR 2000→1000 ms; scanner records: `_ObserveReceiverGain` 30→0; `_ObserveTransmitGain` −203→−129.
- K vs 2026-10-10 v181_testK: diffusion list 2→3 volumes (b 0/1000 → 0/10/1000); PPL 1.81→1.82; `crusher_step_pct` 40→0; TR 2000→1000 ms; scanner records: `_ObserveReceiverGain` 30→0; `_ObserveTransmitGain` −203→−129.
- v1.911-0 vs 2026-10-10 v1911_testI: none; scanner records: `_ObserveReceiverGain` 30→180; `_ObserveTransmitGain` −203→−129.

The [complete plan-difference CSV](../docs/data/oct11_protocol_plan_diffs.csv), [scan metadata CSV](../docs/data/oct11_protocol_scans.csv) and [audit JSON](../docs/data/oct11_protocol_audit.json) retain the full differences. Rebuild the catalog and audit with `python docs/data/oct11_protocol_audit.py`.
