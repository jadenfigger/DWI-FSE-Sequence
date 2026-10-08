# Independent physics / simulation review: v191 (ss-MGOT) and v192 (Alsop)

Reviewer role: independent physics and simulation reviewer. I did not write the sequences, the generator, `dwfse/ppl/` or the coordinator's documents, and I edited none of them. My only outputs are this file and `docs/v19/review/physics_checks/` (scripts plus their JSON/stdout outputs).

Scope: the final PPL/PPR pair for each method, the writer's validation and benchmark outputs (regenerated from the final hashes), and the writer's claims (a) to (d). This is a physics and simulation review only. **Nothing here is compiler, console or scanner verification.**

## 1. Verdict

- **Blocking: none.** The axis and phase logic, the harmonic recall, the first-echo and later-echo moment contracts, the 50% cost, the |C| ≥ 3|D| rule and the writer's event-driven Bloch numbers all hold up under independent derivation and independent code.
- **Major: 3. None changes the shipped scanner protocol's numbers.**
  - **P1.** The C1 guard set is not sufficient. With the real waveforms, several unguarded first-crusher values give 10–20× the protocol's phase dependence for v192, and up to 0.105 for v191.
  - **P2.** The reference benchmark's own C1 (= 1.5 C) sits in one of these unguarded coincidence windows. It inflates the Alsop phase dependence that the README cites as reproducing Gibbons.
  - **P3.** The benchmark's 3000-isochromat / 30-mm grid aliases high-order pathways after about echo 33. Late-echo benchmark values, including the Fig 3/S2 ADC76 landmark, are wrong by up to 0.11 without relaxation.

## 2. Hashes reviewed (SHA-256)

| File | SHA-256 |
|---|---|
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl` | `f0156b48a1b9ff648dba7d69e508629b6fc51bebfcb27d91c5f9fc46ee205f2d` |
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppr` | `faa77a11c2da4c5fe9876d6a842b9bc3025c66ddc09eaa4e8270dec9350faf0c` |
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.92.ppl` | `35d0eeaa0c60dc1d95f9bbb9c44881e65bc9a58d533aa3636031b4273d15e855` |
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.92.ppr` | `678f2af5bb2fa205c2b7cb9402879d9ce1e98ed8e2c5fa4264c318b3e6898fbf` |
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl` (v18) | `3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2` |
| `examples/build_v19_ppl.py` | `c0f39a5c9ae267e69e46a78adfaa8c30b440c4b18bef9b846671eb86320d15ce` |
| `examples/v19_validate_events.py` | `bbb01bc732c396e329882ab67d2b2b079f46d50430d637f8a71d0dbed02a89b7` |
| `examples/v19_reference_benchmark.py` | `309d90353146bc8357f90540c074e4ef0424ec4c1238b34ad40ac312d61c927a` |
| `dwfse/ppl/bloch.py` | `daee94bc9b41b6cad88b65a7480a68fde5f9bef9a0bc3899c2b4b8fa52d38ebd` |
| `dwfse/ppl/analysis.py` | `104e6bfd2be908af4aaf8f1bae9e0897fb835be9d8fecbee5cca342ef7c19d02` |
| `dwfse/ppl/events.py` | `abc5f91998ecdb5c9fddd4bcf9aaaccd1f93d0b7ce50f517b55b057c1f3ea73b` |
| `dwfse/ppl/ledger.py` | `bcdd4c16dd2f852678a748319a6f6fafe06a005e91d0060263378536abc762ff` |
| `dwfse/ppl/run.py` | `8524c9ea6f7f4a29a83f3c463b6d464296bc1e9ba61fe85913b3a42e473551ee` |
| `dwfse/ppl/interp.py` | `a655757cf2c4f489ab9b3ec4a5c0c517fb19abc0e1c4e4508c35fda31839e3e1` |
| `docs/v19/implementation_report.md` | `cb900be05cc387d8b9823fef5ec34660bc1d6d01a52b8d7f11251d7cf73bfef7` |
| `docs/v19/README.md` | `5102f7b9bd2b7438322a5f78d384b9f325edf40d6c8c03b49065a7351494c3ec` |
| `docs/v19/physics_review.md` | `629600ef3bfe7c106ddc51458e12cb24ab509555a327e8c9c85b0d43f576e788` |
| `docs/v19/reference_rf.md` | `c8ab6f8652809a5ffdad104e5f9af003295959171ac9708413adc46d9ddfb510` |
| `scanner/rf/v19_research_rf.seq` | `cca9935e58833c3c61fb5e76cc577659914f5c250cf2449676affd12d088bf5c` |
| `docs/v19/reference_rf/real_rf_transfer_results.json` | `d45ec96d5d1251f5ca56fda69aa242514292d08d6390ff1ce06b4f97be7af146` |
| `docs/v19/event_validation/summary.json` | `d3479e20091e458f9db5cab8da6212faa8f7afde25b9b84d822e6f84bdee10a6` |
| `docs/v19/event_validation/bloch_results.json` | `34fd8ca8d3c5a6f6a80af3b6229454ab419ff83df284a38ebe0e731c09e0c64c` |
| `docs/v19/event_validation/landmark_summary.json` | `7695279b9c9125ac5757011270828e1e953363a7fc4e9567aaef3d30a50e1382` |
| `docs/v19/event_validation/btensor.json` | `1d062bfdc1f3dfcc48dc94873cf234a91c602deab82430161e31da34466efc25` |
| `docs/v19/event_validation/moments.json` | `a938e4be201ce99cd35057f0def26f3fa0759a6103fc94bd467bab5fdca891ba` |
| `docs/v19/event_validation/convergence.json` | `83323beab5b94efe40dd3f25a9c2c48e59045dfd7ed0f5587f8b5a98e2b44da1` |
| `docs/v19/reference_benchmark/results.json` | `bb0cb51112bcd273c410882951b0dc607b4bbd05798e316e6ed591d8fcca6495` |

**Validity of the writer's outputs used here:**
- `event_validation/summary.json` (written 15:04:25) lists the final PPL hashes above for v191/v192 in its `inputs`, with `control_identity_all: true`.
- `reference_benchmark/results.json` (written 15:03:37) has `flips.ssmgot_busse_style` beginning 160, 110, 80, 65.
- My own ledger mappings report the same PPL/PPR hashes (`physics_checks/event_bloch_results.json → inputs`).

## 3. Findings

| ID | Severity | Finding | Evidence | Recommendation |
|---|---|---|---|---|
| P1 | **major** | **The C1 guards (reject \|C1\| within \|D\|/2 of \|C\| or \|C\|+\|D\|) are not sufficient.**<br>• Stray-pathway coincidences also arise for \|C1\|+δ ≈ \|D\|, \|C\|−2\|D\|, \|C\|−\|D\|, 2\|C\|−2\|D\|, 2\|C\|, …, where δ is the prep-180 half-selector area (≈1950 cycles/m for v192, the same order as D).<br>• The guards compare bare moments and ignore δ.<br>• The shipped C1 (−5482 DAC = 5109 cycles/m) is in a benign window, so the shipped protocol is not affected. | Real-ledger v192 scan with diff_crush_amp overrides and my own simulator (`physics_checks/event_bloch_c1scan.json`). Maximum phase spread of \|S\| over echoes 1–8 (phases 0/45/90):<br>• protocol −5482: **0.015–0.021**;<br>• −1000…−2500 DAC (0.9–2.3 kcycles/m, near \|D\|): **0.19–0.32**, all accepted by the PPL;<br>• −4000 (near \|C\|−2\|D\|): **0.125**;<br>• −7000: 0.074;<br>• −12000 (near 2\|C\|−2\|D\|): **0.154**;<br>• −7500…−11000: correctly rejected.<br>v191 (slab prep), same method: protocol 0.0024; 0.007–0.019 for −1500…−7000; **0.105 at −12000** (accepted). The guard gap affects ss-MGOT as well (§4.4). | Either lock C1 on the method path to a Bloch-validated value or window, or generalise the guard to the families above with margins ≥ \|D\| that include δ. Re-scan C1 with the event Bloch before any protocol change. State in the README that only the shipped C1 is validated. |
| P2 | **major** (benchmark) | **The benchmark's C1 = 1.5 C = 2250 cycles/m sits on a coincidence window** (2C−2D = 2333 family, 83 cycles/m away = 0.5 cycle across 6 mm). It inflates the Alsop phase dependence. The README's "Alsop is phase-dependent (echo 2 = 0.125/0.103/0.071) … reproduces Gibbons' qualitative result" is therefore confounded by the benchmark's own crusher choice. The 4-cycle runs have the same problem: C1 = 4500 vs 2C−2D = 4667. | Benchmark rebuilt with variable C1 and propagated by my simulator, no relaxation, 2 cycles, 16 echoes (`physics_checks/benchmark_c1_results.json`). Maximum Alsop phase spread:<br>• C1 = 2250: **0.175** (echo 2 = 0.377/0.303/0.202);<br>• C1 = 2550: **0.037**;<br>• 1950: 0.090; 3300: 0.082; 3750: 0.160.<br>ss-MGOT at 2250: 0.022; at 3750: 0.008. | Choose the benchmark C1 from a family scan (for example 1.7 C) and rerun Fig 3/4. Report Alsop phase dependence as a range over C1. Qualitative Alsop phase dependence does survive at C1 = 2550 (echo 4: 0.209/0.185/0.172), so the conclusion can be kept with corrected numbers. |
| P3 | **major** (benchmark) | **z-grid aliasing in the benchmark.**<br>• 3000 isochromats over 30 mm gives dz = 10 µm, so Nyquist is 50 000 cycles/m, about 33 echo intervals of 2C (C = 1500).<br>• Later echoes include aliased high-order pathways.<br>• The writer ran no convergence test for the benchmark. Their z3000/6000 check covers only the scanner files, which use 3000 points over 5 mm and are fine. | Writer's own builder (event list only) with my simulator, 3000 vs 9000 points (`physics_checks/benchmark_zgrid_results.json`):<br>• echoes 1–16 agree to ≤ 4e-7;<br>• Alsop without relaxation: maximum error **0.109 at echo 36**, ADC76 = 0.275 vs 0.233;<br>• with T1/T2 1300/32 ms: maximum 0.0051 at echo 36;<br>• ss-MGOT without relaxation (3000 vs 9000 × 32 y points): echoes 1–16 agree to ≤ 7e-7, but the maximum error is **0.076 at echo 33**, and ADC76 is 0.362 vs 0.342. With relaxation the maximum is 0.0021 at echo 33. The aliasing affects both methods. | Use ≥ 9000 points, or a z extent and crusher choice whose Nyquist exceeds the highest retained k. Add a benchmark convergence entry. Until then, label benchmark echoes > 30 and the ADC76 landmark as unconverged. |
| P4 | minor | **Mislabelled moment in finding (a).** README and implementation report: "post-RF moment C + D ≈ −555 cycles/m". D has the train-crusher polarity, so for the old protocol C + D = −4557 cycles/m. The near-zero quantity is C − D = −551 cycles/m (ADC → next RF), i.e. the residual D − C of RF_n's FID refocused by RF_{n+1}. The mechanism and conclusion are correct. | Moment arithmetic in `physics_checks/axes_pathways_results.json` (`old_C_minus_D` = 551.2). Ledger moments: RF→ADC = C+D+sel/2 = −10654.6; ADC→RF = C−D+sel/2 = −6646.5 cycles/m. | Reword as "the FID of each imaging RF, refocused by the next RF, is left with residual D − C ≈ 555 cycles/m". |
| P5 | minor | **The b-tensor path for even echoes is not the echo-forming branch.** At even echoes the recalled branch is the conjugate one, which needs a k → −k at the method RF T0. `btensor.json` reports k_end ≈ −3890 cycles/m (≈ 2D) at ADC2 and ADC8, so the text "for the signal pathway that actually forms each echo" is not literally true there. | My exact integration with the T0 flip gives:<br>• k_end at ADC2 = +57.5 (v191) / +113 (v192) cycles/m;<br>• b_SS changes by ≤ 6 s/mm²;<br>• b_RR is unchanged.<br>(`physics_checks/btensor_independent.json`) | Add the T0 conjugation for even echoes, or document that b_RR, the diffusion axis, is path-independent here. |
| P6 | minor | **Alsop off-resonance range understated.** The README quotes echo 1 = 0.37/0.29/0.26 at −128/0/+128 Hz, which is the 45° value only. | `bloch_results.json`:<br>• phase 0°: echo 1 = 0.381/0.303/0.211;<br>• phase 90°: 0.329/0.289/0.329.<br>The range over phase × B0 is **0.21–0.38**. ss-MGOT stays 0.380–0.387. | Quote the range over phases. |
| P7 | minor | **Landmarks are sampled at commanded list-end times, while the simulator delays gradients by rfdelay = 60 µs.** Snapshots B, after-tip-up, after-elimination and after-re-excitation therefore miss the last 60 µs of a ramp-down: about 1% of the D area for B. ADC samples are unaffected. | Landmark times from my independent detector equal the writer's. Ramp arithmetic: 60 µs tail of a 200 µs ramp. | Shift landmark times by rfdelay, or state the frame. |
| P8 | minor | **Benchmark elimination-pulse bias.** The Alsop elimination is the 1.2-ms TBW-1.54 Hamming sinc, against a TBW-3.55 SLR prep. Gibbons stresses that Alsop needs a highly selective elimination, so this choice biases the comparison against Alsop. It is disclosed as a departure, but its direction is not stated. | `v19_reference_benchmark.py` docstring and build(). | Say explicitly that the departure handicaps Alsop. |
| P9 | minor | **Assumed benchmark prep TE of 30 ms.** If Gibbons' TE 82.9 ms refers to the k-centre echo (16 × 4.2 = 67.2 ms of train), the implied prep plus tip/re-excitation is about 13–16 ms. The 30-ms assumption then scales all Fig 4 amplitudes by about exp(−15/32) ≈ 0.63. It is a common factor, so the phase comparison is unaffected. | Gibbons p. 3036–3037 text (TE, ESP, 76/46 echoes). | Disclose as a scale-only assumption. |
| P10 | info | **Benchmark Point C labelling.** Gibbons defines Point C as "immediately prior to the first refocusing RF". The benchmark figure labels "endpoint before leading crusher" as C. Both landmarks exist in the npz/JSON. | Gibbons Methods; S2 caption. | Label both, or note the ambiguity. |
| P11 | info | **The simulated scanner shot is the first (dummy, nav_cnt = 0) shot.** gp_var = 0, so there is no phase encoding: P-axis moment at every ADC = 0. The ADC records carry Dummy_Cycles = 1. Slice coherence is unaffected, but in-voxel PE dephasing of acquired views is not represented. | My P-moment audit of the v191 ledger. | None required; state it. |
| P12 | info | **The nominal-cost mapping gives ESP 13996.94 µs** (−3.06 µs per ESP). CPMG self-consistency is preserved: T0 → RF1 is exactly half the RF spacing, and ADC middles sit −1.58/−1.52 µs from the CPMG spin-echo times. Absolute timing depends on the cost model, as disclosed. | `physics_checks/event_bloch_results.json`. | None. |
| P13 | info | **Isodelay offsets** (writer: ADC1 off-resonance peak +95 µs v191, +185 µs v192) are consistent with (κ−0.5)·T: re-excitation 0.0547 × 1200 = 66 µs; prep excitation 0.0316 × 3200 = 101 µs. That is ≤ 5° at 128 Hz, too small to explain P6. The Alsop off-resonance sensitivity therefore comes mainly from the selective elimination/train response, which I did not decompose. | κ values from the generator/transfer JSON. | As the README says, fold isodelays into the timing. |
| P14 | info | **Crusher diffusion weighting.** The 3× train crushers add b_SS = 19 → 85 s/mm² (echo 1 → 8). Trace is 1015 → 1092 at nominal 1000, and 20 → 98 at nominal 0. v18 has b_SS 3.8 → 11.5. | Writer and reviewer b-tensors agree (§4.6). | Already disclosed. Keep the b-mismatch warning prominent. |

## 4. Verified independently (my numbers)

### 4.1 Axes, phases and recall

`check_axes_pathways.py` uses no dwfse code. It applies hard rotations in the repository convention: dM/dt = 2π M×B means rotation by −θ about B1. Results:

- Prep 90° at phase 0: +Mz → **+My**. Prep 180° at 270°: Mx → −Mx, My → My (MG = My).
- ss-MGOT tip-up 90° at **180°**: +My → **+Mz**, and Mx stays transverse. Re-excitation 90° at **0°**: +Mz → **+My**.
- Alsop elimination 90° at **270°**: My retained, **Mx → −Mz**.
- Control cases expose wrong axes. A tip-up at 0° stores My on −Mz. An elimination at 180° stores My instead of retaining it.
- **Ideal 180° train test**: 4000 points over exactly 1 mm, D = 2, C = 7 cycles/mm, sequence pre C | RF | post C, +D, ADC, −D.
  - Both methods give **|S| = 0.500000000000** at echoes 1–4 for φ = 0/45/90/137°.
  - The echo phase is 90° + φ and is constant across echoes, except a ±180° wrap for ss-MGOT at φ = 90°.
- **Recalled harmonic.** With a +D recall that has the D-lobe (and C) sign:
  - echo 1 recalls the branch m_A·e^{−i2πDz} that D itself created;
  - after the −D restoration, echo 2 recalls the conjugate branch;
  - the two contributions are in phase, so the magnitude is phase-invariant;
  - the ideal cost is exactly **50%**.
- **First-RF and later contracts in the real ledger** (physical frame, my integration). Here sel/2 ≈ 988 cycles/m is the imaging half-selector:
  - T0 → RF1 contains no −D;
  - RF→ADC = C + D + sel/2 = −10654.6 cycles/m at every echo;
  - ADC→RF = C − D + sel/2 = −6646.5 cycles/m.

  This realises the required "first RF: pre C, post C+D; later: fused C−D / C+D" contract. It also agrees with `moments.json`: k/D = 1.000 ± 0.002, restoration ≤ 0.002 D.

### 4.2 Pathway enumeration and the |C| ≥ 3|D| rule

My generalised EPG keeps states keyed by arbitrary real k, so non-commensurate C, C1 and D are handled exactly. It includes prep-180 imperfection, elimination/tip leakage and imaging-RF FIDs, and weights the slice with a box sinc. Settings: PPR moments C = 7663, C1 = 5109, D = 2003 cycles/m; slice 1.0006 mm; flips 142.2/94.9/69.2/63/60.2/60/60/60.

- **ss-MGOT ideal** = 0.5 × CPMG reference within 0.0013 (0.4468 vs 0.4466 at echo 1). It is phase-invariant to < 0.001.
- **Coincidence families of the train.** These come from imaging FIDs, from re-excited eliminated Mz at ±D, and from the opposite branch:

  (2j+1)|C| = |D|, (2j+1)|C| = 2|D|, j|C| = |D|

  All of these have |C| ≤ 2|D|. So **|C| > 2|D| is sufficient** for train-only families, and 3|D| leaves a margin of ≥ |D|. At the PPR the nearest family (C − 2D = 3657 cycles/m) is 1.83 D away.
  - The C/D scan (box slice, 150° prep, 80° elimination) peaks at C/D ≈ 1 (0.14–0.37), ≈ 1.4 and ≈ 2.1 (0.33).
  - Above 3 it stays ≤ 0.08. The box tails are pessimistic.
  - **The rule is justified and close to necessary**: a 2.5|D| rule would leave only |D|/2 margin from C = 2D.
- **4-cycle setting with the shipped C**: C − 2D = −349 cycles/m. The ideal model gives a 0.21 phase spread, so rejecting 4 cycles at this C is correct.
- **Old protocol C** (−2741 DAC): C − D = 551 cycles/m. This confirms the mechanism of writer finding (a). I did not reproduce the writer's quoted 0.07–0.51, because the PPL now rejects that C.
- **2C and C − D at the PPR**: 2C is never a coincidence for the train families. C − D (5660) matters only for C1 families (P1).
- **Alsop with ideal pulses** still shows a small phase dependence (≤ 0.045 in the box model). It comes from the eliminated ±D Mz being re-excited by the low-angle train at k = C, C − 2D, and so on. With smooth real slice profiles it is 0.015–0.02 (§4.3). This is intrinsic to Alsop: its eliminated half is dephased, not spoiled.
- **Spoiler residual** at 8.24 cycles/voxel (continuous sinc 0.026) changes ss-MGOT by ≤ 0.005 even with an imperfect tip-up.

### 4.3 Event-driven Bloch spot check (task 3)

`check_event_bloch.py` takes only the ledger from `map_events` (nominal ×0.8 manual-cost model, same as the writer). Everything else is my own code:

- calibration from the formula stock sinc, 2047·sinc over 666 × 2 µs at rfcal 594 → **1.39993 Hz/unit**;
- Rodrigues rotations, exact piecewise-constant gradient integration, and splitting of RF samples at gradient breakpoints;
- 60-µs gradient latency;
- landmark detection from list starts and waveform ends.

Nominal flips: prep 89.96/179.83°, elimination/tip 89.83°, re-excitation 89.93°, imaging 141.92/94.70/69.13/62.95/60.14/59.86°.

| Slice-coherent \|S\| at ADC middles | echo 1 | echo 2 | echo 8 | max \|mine − writer\| (8 echoes) |
|---|---|---|---|---|
| v192, 0° | 0.3032 | 0.2750 | 0.2572 | 2.8e-15 |
| v192, **45°** | **0.2933** | **0.2839** | 0.2438 | 7.7e-15 (phase 1.9e-12°) |
| v192, 90° | 0.2886 | 0.2863 | 0.2370 | 1.1e-14 |
| v191, 0° | 0.3871 | 0.4041 | 0.3335 | 7.5e-15 |
| v191, **45°** | **0.3867** | **0.4033** | 0.3343 | 7.6e-15 (phase 3.1e-13°) |
| v191, 90° | 0.3864 | 0.4028 | 0.3319 | 8.0e-15 |
| latency 0 (45°) | v192 0.2924 / v191 0.3829 | | | identical to writer |
| v191 y64 (45°) | 0.3867 / 0.4033 / 0.3342 | | | y32→y64 ≤ 1.1e-4 |

**Landmarks** (phase 45°; coherent mean |Mxy| / local |Mxy| / local Mz inside the slice) agree with `landmark_summary.json` to all printed digits.

| Landmark | v192 | v191 |
|---|---|---|
| A | 0.7251 / 0.8931 | 0.9932 / 0.9932 |
| B | 0.0906 | 0.0122 |
| after elimination / after tip-up | 0.0464 / 0.7463 / Mz 0.0705 | 0.133 / 0.646 |
| after spoiler (v191) | — | 0.0036 |
| after re-excitation + compensation (v191) | — | 0.0095 / 0.789 / local Mz 0.446 |
| endpoint before leading crusher | 0.0482 | 0.0086 |
| pre-RF1 after crusher | 0.1129 | 0.0141 |
| ADC1 | 0.2752 | 0.3339 |
| ADC2 | 0.2545 | 0.3402 |
| ADC8 | 0.2203 | 0.2789 |

**Caveat on what the agreement shows.** Agreement at 1e-14 is expected for two exact-rotation engines on the same piecewise-constant input: no gradient breakpoint falls inside an RF sample, and the writer's counter is 0. It therefore validates the writer's **numerics, landmark timing and normalisation**. It does not validate the ledger fidelity, the linear rfcal calibration model or the rfdelay latency model, which both engines share.

### 4.4 C1 sensitivity on real waveforms

- **v192**: see P1 (`event_bloch_c1scan.json`). The shipped value sits in a benign window: spread 0.015–0.021, while −5500 gives 0.021 and −6000 gives 0.019.
- **v191**: `c1_v191_results.json` / `c1_v191_stdout.txt`. The 3 mm (18/6) slab prep keeps the prep-180 imperfection out of the imaging slice, so ss-MGOT is far less C1-sensitive. Maximum phase spread by C1 DAC:

  | C1 DAC | −1500 | −2500 | −4000 | −5482 (protocol) | −7000 | −12000 |
  |---|---|---|---|---|---|---|
  | Spread | 0.019 | 0.0096 | 0.0070 | 0.0024 | 0.0033 | **0.105** |

  ss-MGOT is robust over most of the range. At C1 = −12000 DAC (11.2 kcycles/m, which the PPL accepts), echo 1 is 0.334/0.391/0.439 at 0/45/90°, so ss-MGOT loses its phase invariance there. P1 therefore applies to both methods.

### 4.5 Reference benchmark (task 5)

- **Fidelity to the published geometry**:
  - 3000 isochromats / 30 mm, 6/18/10 mm ✓;
  - phases 0/45/90 ✓;
  - 2 and 4 cycles ✓;
  - Fig 4 relaxation T1/T2 1300/32 ms ✓;
  - ESP 4.2 ms, 76 echoes ✓;
  - prep SLR TBW 3.55 / 3.2 ms, matching Gibbons' prep pulses ✓.
- **Disclosed departures**, all present in the docstring:
  - research RF;
  - 1.2-ms elimination (biased against Alsop: P8);
  - idealised 100/200-µs moment blocks;
  - Busse-style schedule 160/110/80/65 → 55 → 60° at the assumed k-centre echo 16. Echo 16 is consistent with PF 0.60, R = 2 and 20 ACS lines;
  - prep TE 30 ms (P9).
- **Figures are kept distinct and honestly labelled.** Fig 3/S2 (no relaxation, because the paper states none), Fig 4 and the S1 "signal-only illustration" each have their own result keys. S1 is explicitly not reproduced.
- **y-grid adequacy.** The benchmark uses 32 points with exactly 8 spoiler cycles per voxel, so the order-±1 to ±3 discrete means are exactly 0. That is ideal spoiling, equal to the continuous result for integer cycles. Order 4 aliases to DC but cannot occur, because the spoiler is played once and there is no other y gradient. The scanner case is 8.24 cycles, giving 0.0295 (grid) vs 0.0264 (continuous). Both are adequate.
- **Problems**: P2 (C1 coincidence) and P3 (z aliasing after about echo 33).

### 4.6 b-tensor (task 4)

`check_btensor.py` integrates k k^T exactly for piecewise-linear k (no sampling), with flips at refocusing centres and k frozen during ss-MGOT storage. Crushers, selectors, D and recall are all included.

| Nominal b = 1000, ADC1 | b_RR | b_SS | trace | writer (b_RR / trace) |
|---|---|---|---|---|
| v191 | 995.92 | 18.61 | 1014.54 | 995.9 / 1014.5 |
| v192 | 995.76 | 19.28 | 1015.04 | 995.7 / 1015.0 |
| v18 original | **1172.15** | 3.77 | 1175.93 | 1171.4 / 1175.2 |

- The analytic trapezoid Stejskal–Tanner value for the v19 lobes (diff_grad 8216 DAC, δ 4 ms, Δ 40 ms, ramps 200 µs) is **994.3**.
- **v18 excess.** An order-of-magnitude estimate of the cross term between the diffusion and read prephaser is 2(2π)²·(Gδ ≈ 25.6 kcycles/m)·(k_rp ≈ 1.8 kcycles/m)·Δ ≈ 150 s/mm². That matches the +172 found, so the v18 excess is plausible.
- **Methods ≈ 996.** In the methods the read prephaser is played after the method RF, outside the diffusion window, so there is no cross term.
- **Path choice.** Path choice is correct for odd echoes. For even echoes see P5: the impact is negligible for b_RR.

### 4.7 Landmarks and no artificial zeroing (task 6)

- `bloch.py` and my simulator never zero the transverse magnetization. Spoiling is the y-grid average only.
- **Both pre-imaging landmarks are reported.** The endpoint before the leading crusher and pre-RF1 after it are both present. In v192 the coherent mean rises from 0.048 to 0.113 between them, which is the known crusher rotation of the residual, not leakage.
- **Local and voxel means are reported separately**: the `*_local_*` and `*_mean_*` npz arrays, and `slice_mean_local_abs_mxy` vs `slice_coherent_*` in the JSON.
- Naming nit: `slice_mean_mz` in `landmark_summary.json` is the local column, not the voxel mean.
- Snapshot frame: see P7.

## 5. What is validated, approximate, or not established

**Validated, as source-level physics on the mapped ledger:**
- the RF axis and phase logic;
- the recalled harmonic and the 50% ideal cost;
- the first and later recall/restoration contracts;
- the |C| ≥ 3|D| rule for train pathways;
- the writer's Bloch numerics, landmarks and normalisation, reproduced to 1e-14;
- the b-tensor values (b_RR ≈ 996 for the methods vs 1172 for v18);
- ss-MGOT phase invariance on real waveforms (±0.0025);
- Alsop's residual phase dependence (≈ 0.015–0.02) at the shipped C1.

**Approximate:**
- RF calibration (a linear rfcal model, shared by both engines);
- the gradient-latency model (rfdelay);
- nominal statement costs (ESP short by 3 µs per echo);
- hard-pulse EPG coincidence maps (box slice, pessimistic tails);
- the benchmark's research RF, schedules, prep TE, crusher choice (P2) and z grid (P3).

**Not established:**
- vendor compilation;
- console timing and real instruction costs;
- hardware gradient/RF/receiver delays and eddy currents;
- the actual transmit calibration and flip angles of each frame;
- SAR/power;
- multi-slice behaviour;
- image quality, PSF or ghosting;
- the effect of phase encoding (the simulated shot has PE off);
- robustness to any C1, C or D other than the shipped values (P1);
- a quantitative match to Gibbons' figures.

## 6. Reproduce

```
python docs/v19/review/physics_checks/check_axes_pathways.py      # no dwfse import
python docs/v19/review/physics_checks/check_event_bloch.py        # ledger via map_events only
python docs/v19/review/physics_checks/check_event_bloch.py --c1-scan
python docs/v19/review/physics_checks/check_c1_v191.py
python docs/v19/review/physics_checks/check_btensor.py
python docs/v19/review/physics_checks/check_benchmark_c1.py
python docs/v19/review/physics_checks/check_benchmark_zgrid.py
```

Outputs are the JSON and `*_stdout.txt` files next to the scripts.
