# Independent PPL review: v191 and v192

Reviewer role: independent PPL reviewer, separate from both sequence writers. Initial audit: 2026-10-06. Final integrated review is recorded below once the writers' files are available.

## Evidence and scope

The supplied `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl` is the starting source, SHA-256 `3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2`. Its companion `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppr` starts with `:PPL FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl`. This establishes local source identity, not a cryptographic match to the historical `G:\J_Figger` source used for acquisitions: no acquisition-source hash is embedded in the supplied PPRs.

Review uses the supplied [EVO Pulse Sequence Program Manual](../../scanner/EVO%20Pulse%20Sequence%20Program%20Manual.pdf), supplied PPH dependencies, source and PPR, and source-specific timing/branch inspection. The review is static. Vendor waveform libraries became available in the later upload described below; no vendor compiler, console, or played-event trace is available. A source-level analysis or passing Python test is not a vendor compilation or verification of emitted physical waveforms.

## Dependency blockers

**Upload update, 2026-10-06:** the later `scanner/utilities` upload supplies all eleven baseline `.seq` files and six `.pph` files, including `tstex_15.pph`. D1-D3 below record the initial audit and are superseded as missing-file findings. The original absolute `C:\smis\seqlib` paths remain absent on this computer; a deliberate local dependency path mapping is required for new files. Availability does not certify decoding, compiler compatibility or calibration.

The newly supplied `tstex_15.pph` contains only three parameter checks: averages divisible by view block, view block divisible by slice block, and even averages for phase cycle 2. It contains no hardware initialization. Its SHA-256 is `3d64239f42684fcce6d3a3e77134a9cc1aaf6a4139e514470a4777c9be1300af`. The earlier unknown-initializer concern is resolved by inspection. The five PPH files now reside in `scanner/utilities`, and their hashes match the initially audited supplied versions.

The upload contains binary WavEd libraries, not Pulseq samples. `rfstd44.seq`: 62,325 bytes, SHA-256 `c84c023a8bbcd676e81a6308774570b973ee9d5cb525dcfe706589b88544df29`. `g3040_15.seq`: 28,493 bytes, SHA-256 `9cd5cec17bbd3131d1c90a647b3b84ed9934be9884dfc47c8d9b7607f3006c6b`. Named baseline RF/gradient frames are present in the binary payloads; sample data and metadata must still be decoded and independently checked. The RF header's count-like field does not directly equal the five named RF channels, so a guessed flat sample layout is insufficient.

`tree_output.txt` is an inventory of another `/smis` installation, not an uploaded executable toolchain. It lists `cpp.exe`, `compile.bat`, `pplc.exe`, `specsim.exe`, `specsim.ini`, `specsim.tlb`, `waved.exe`, `waved.hlp`, `waved.ini` and supporting DLLs. None of those actual files is present in the uploaded utilities directory. D4/D5 remain open. Scanner deployment is outside scope.

Independent raw parsing, without importing the coordinator's codec, confirms frame pointers, waits, 32-bit word counts, expression pointers and RF/gradient records for the referenced baseline shapes. RF words contain packed channel/control bits and signed 12-bit amplitude data; gradient records contain primary/secondary signed 16-bit samples. Exact storage roundtrip establishes file-layout preservation, not semantics of every control bit or vendor loading.

The baseline `3lobe_sinc_3kHz` frame has 668 RF records at wait 20, with the expression `1,0;666,sinc(...);1,0;` and a final changed phase-control nibble. The PPL's nominal duration is 1332 us (666 active records), while 668 records times 2 us is 1336 us. An event mapper must distinguish active RF, gate closure, endpoint zeros and sequencer end/hold flags. Similarly, the 50-record rising/falling gradient ramps have normalized sample sums 24.5200049 and 25.4800256; their combined sum is approximately 50.00003. Individual sampled ramp areas must be used where RF centers split them. These findings were sent to the coordinator and RF designer.

| ID | Finding | Classification and consequence |
|---|---|---|
| D1 | `tstex_15.pph`, included inside `main()` at v18 line 534, is not supplied. | Blocking dependency: declarations/setup/side effects cannot be inspected; cannot compile a complete baseline. |
| D2 | `C:\smis\seqlib` is absent. The ten RF files named by `#use RF1` are `RFstd44.seq`, `gs_240Hz.seq`, `presat.seq`, `opt90_a.seq`, `opt90_as.seq`, `asym.seq`, `hypsec.seq`, `rfchess.seq`, `9lobsinb.seq`, and `19lobsinb.seq`. | Blocking dependency: no sampled baseline RF, exact spatial transfer response, amplitude normalization, frame metadata, or RF board loading can be verified. |
| D3 | `g3040_15.seq`, named by `#use GRAD`, is absent. | Blocking dependency: ramp and held-list waveform sample definitions cannot be verified. |
| D4 | No `ppl`, `pplc`, or `pfgen` command was found on PATH; no vendor compiler is supplied in the repository. | Validation unavailable: compiler syntax, code memory, execution costs, generated `.fth`, and events remain unverified. |
| D5 | Hardware/calibration configuration (gradient amplitude per physical axis, slew, delays, RF normalization, transmit attenuation and board limits) is not supplied. | Console validation unavailable: logical signed DAC limits do not establish hardware safety, especially for oblique sums and simultaneous axes. |

The `.seq` files in `runs` and `examples` are Pulseq experiment artifacts, not the missing vendor WavEd libraries. They cannot replace D2/D3. Five top-level includes are supplied: `stdfn_15.pph`, `var_20.pph`, `offst_20.pph`, `m3040_15.pph`, and `m3031_15.pph`.

## Manual-derived integration constraints

| Requirement | Source | Implication for both implementations |
|---|---|---|
| RF assets are WavEd `.seq` files linked with `#use`, with named frames and board metadata. | Manual section 5.4.2, p132; `m3031_15.pph` lines 13-22. | Do not deliver text samples as loadable WavEd, invent frame names, or infer phase/amplitude semantics from duration and nominal bandwidth. |
| `phase_increment(1)` establishes 0.225-degree units; 90 degrees = 400. | Manual sections 3.3.1.9-14, pp53-54; v18 line 1326. | Use scanner phase units, account for `aqphase`, preparation axes and receiver demodulation together. `rphase` is reset by receive/acquire operations; audit actual receiver path. |
| Frequency offsets accumulate synthesizer phase. | Manual frequency discussion pp52-53. | Slab-selective preparation and slice re-excitation need consistent offset/phase bookkeeping. A changed gradient without corresponding frequency shift moves an off-center slab incorrectly. |
| `waittimer` uses 0.1-us ticks and a 50,000-tick period; missed deadlines add complete 5-ms periods. | Manual pp90-91; `stdfn_15.pph` line 91. | Include control-flow and macro/library costs in every new bracketed section. A positive wait target alone is insufficient. The supplied declaration accepts `int`; conversions from long retain low 16 bits. |
| `int`/`common int` are signed 16-bit; casts after evaluation do not prevent overflow of a preceding int expression. `long` is 32-bit and cannot be a PARAMLIST or common long. | Manual sections 4.8.7.1-2, pp97-98. | Promote before multiply/add; bound intermediates before narrowing. Do not assume assigning to long makes a pure-int right-hand expression safe. |
| Matrix calculations must not target an active matrix; secondary IDs add 256. | Manual sections 3.5.16-19, pp75-76; `m3040_15.pph` `caldelay` = 100 us. | Use inactive pairs and complete DSP calculation before selection. Verify physical sum and timing, not merely individual logical DAC values. |
| Identifier length beyond 31 characters is truncated by compiler. | Manual chapter 6, p157. | Avoid collisions between long new symbols after truncation. |

`#error` is not documented in the supplied manual; its compiler compatibility cannot be certified without the actual compiler. `#include` is documented (section 3.1, p46), as are the existing `printf`/`goto end` rejection idioms in v18.

## Execution branches that require method-specific verification

| Branch | v18 source landmark | Required review |
|---|---|---|
| Main preparation/read prephasing | lines 3721 onward | Replace preparation deliberately, preserve one read prephase, keep diffusion/preparation/RF center/first ADC timing distinct. |
| Imaging echo loop | `echo_loop`, line 3837; ADC phase at lines 4004-4008 | Recall/restoration area and signs at each actual ADC; selective RF/crusher gradients separate; correct receiver phase. |
| Subsequent train intervals | post-ADC block around lines 4093-4130 | Every first-to-second and later RF/ADC center interval; no missed timer or inserted unbudgeted calculations. |
| Navigator | `nav_on`, setup/reordering lines 977-984, 1200, 1239; play state around 2489 | No silent bypass/mislabeled method; navigator gradients and count handling included in trace. |
| Dummy scans and discard acquisition | `disacq_loop`, line 2484; `notDummy`, line 4025 | Same preparation and RF heating/timing as intended acquisition; receiver gate suppression only where established. |
| Multislice/interleave/orientation | `slice_batch_loop`, `multislice_loop`, lines 2480-2503; offset code lines 2523-2610 | Slab/slice frequency centers and phase for each slice; orientation-transformed moments; batch timing and crosstalk restrictions explicit. |
| Diffusion zero and nonzero amplitude | diffusion play before/after first 180 | Preparation still plays at b=0; no branch-dependent TE difference; complete b-tensor rather than diffusion-lobe-only nominal b. |
| 3D, flow compensation, Dixon, driven equilibrium, saturation and gating | compile/runtime switches in supplied source | Support through verified scheduling or reject explicitly. Preserving a baseline branch textually does not validate its compatibility with an inserted preparation. |
| Custom/increasing/decreasing/alternating crushers | table build around line 1459, next-update macro | Define signed schedule and index/ETL limits; avoid overwriting matrices and verify exact area at every echo. |

## Preliminary verdict

The local actual v18 source is available and auditable. The later upload completes the baseline file dependency set, subject to explicit path resolution. Both new methods require additional RF and event scheduling that cannot be validated from nominal acquisition parameters or Python approximations. D1-D3 missing-file findings are superseded; decoding, compiler/event mapping and physical calibration remain separate requirements. Any generated baseline copy with a compile/runtime gate is a scaffold, not an implemented ss-MGOT or Alsop sequence, and must be labeled accordingly.

## Integrated-file review, pass 1

The independently inspected files have these hashes:

| File | SHA-256 |
|---|---|
| `FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl` | `9506f8feb989fec09cc1d4a3063a73d5aa63aff7932f50dedef5c726f7b54519` |
| `FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppr` | `0085c4ea4567ab34b184e9e5a1420e9013cd1d70899889a918433da2fdc491af` |
| `FSE_dwi_CPMG_non_CPMG_twoTE-1.92.ppl` | `45a4b2967b7c950a56400319bab3d959f7846d9a04da387527c6b988b99df352` |
| `FSE_dwi_CPMG_non_CPMG_twoTE-1.92.ppr` | `8221fcce829722448a0dc301495b75ac2c2f4ad6055b5b45ac6d0d80c7103a3a` |

An independent byte comparison, without executing the writers' generators/auditors, verified that removing only each added header and early rejection block yields the unchanged v18 PPL bytes. Both PPRs are unchanged except for their PPL filename pointers. Both retain **ETL = 2**, not eight echoes. No new RF/gradient/ADC scheduling, amplitude calibration, method parameters, validation branches or tailored refocusing train has been implemented in either PPL.

The intentionally absent include occurs before the inherited source in both files. The additional runtime `printf`/`goto end` occurs before the missing `tstex_15.pph` initializer and the first hardware-control statements. The inherited `end:` label exits directly without accessing uninitialized hardware state. These guards and their placement pass static inspection. Missing-include rejection has not been demonstrated with a vendor compiler, and guard integrity does not constitute scanner validation.

| ID | Finding | Resolution/status |
|---|---|---|
| P1 | Both reserved method files retain v18 without implementing their labeled methods. | Explicitly labeled **METHOD NOT IMPLEMENTED** and gated. Mislabeling risk addressed; implementation requirement remains blocked/unmet. |
| P2 | Neither reference RF nor adapted played RF/gradient/ADC exists in these files. | Cannot audit actual slice phase, tip axes, recall/restoration signs, ADC coherences, RF transfer functions, physical gradient limits or b-tensor. No approval; open implementation/validation blocker. |
| P3 | Companion PPRs still use ETL=2 and source protocol. | Preservation passed. Eight-echo adaptation remains unmet; these must be described as reserved companion PPRs, not method acquisition protocols. |
| P4 | Initial proposed `#error` compatibility had no supplied-manual support. | Writers used documented `#include` plus established `printf`/`goto end` instead. Static source compatibility concern addressed; actual diagnostic still unverified. |
| P5 | Missing initializer/assets/compiler prevent full branch/played-event verification. | D1-D5 remain external blockers; unmodified branch text does not certify future method compatibility. |
| P6 | A uniform proposed pre-RF `C-D` / post-RF `C+D` pair contributes `2D` in the toggling frame. With initial dephasing `D`, it does not recall the first echo without an additional compensator. | Reported independently to Alsop writer and physics reviewer. First-echo and subsequent-echo moments must be distinguished; design-script headroom examples must not be presented as verified recall scheduling. Revision pending. |

**Verdict:** source preservation and static guard placement reviewed successfully. These are reserved, deliberately non-runnable scaffolds; neither method receives correctness approval. No claim that all required correctness defects are resolved is justified. This review did not compile, simulate played PPL events, or verify a scanner.

Revision review: pending final writers' documentation and coordinator revisions.

## Concrete implementation review after utilities upload

The user authorizes source implementation and explicit inference using the actual libraries/manual despite unavailable compiler/calibration. Compiler or console certification is still withheld. Source-based event mapping can be verified only against the actual integrated PPL, macro expansion, binary frames, parameter values, holds/continues, matrix latency and RF/receiver history. A Python sequence with similar geometry is insufficient.

Initial helper findings, before source integration:

| ID | Finding | Requested correction/status |
|---|---|---|
| H1 | `V191_PREPARE_RF` / `V191_PREPARE_GRAD` allowed a returned `gettimer` value up to 450 us, then waited to 500 us. Manual p90 specifies approximately 360.2 +/- 5 us timing-function overhead compensated by `gettimer`; the closing call/check can miss the deadline while the returned count passes. | Writer revised to 1000-us padding with conservative450-us threshold. Independently re-read helper; addressed at static source level. Compiler verification remains unavailable. |
| H2 | `V191_PLAY_RF` described `pred` as helper-entry-relative, but helper validation branches run before the inherited `MR3031_RFSTART` delay begins. | RF validation moved to separate preflight macro; play macro now contains only vendor `MR3031_RFSTART`, with explicitly macro-entry-relative `pred`. Independently re-read; addressed in helper. |
| H3 | Vendor `MR3031_RFSTART` does not set external PDD TX/RX masks; v18 explicitly sets them around every RF. The initial v192 elimination tip used the vendor macro without those masks. | Both writers notified: preserve timed switching or explicitly reject PDD mode before playback. Pending integrated review. |
| A2 | Initial concrete v192 timing subtracts arbitrary200-us transition instruction reserves without realizing corresponding fixed padded windows. Requested TE/ESP differs from actual scheduled delay plus call overhead, even when all residual delays are positive. | Require realized padded windows or a complete instruction-cost mapping and truthful actual-center reporting. Reported; pending revision. |
| A3 | Copied v192 loop adds preparation/flip-control arithmetic after an existing pre-RF timer wait, shifting the RF center; more new control flow sits outside the original empirical timer budgets. | Move scale/index work to validated setup before gradient start and audit every new timed branch. Reported; pending revision. |

`LONGDELAY` is present in the actual uploaded `var_20.pph` at lines127-132, with 140-us compensation, and documented in manual p145 with minimum150us. An earlier message saying the macro was absent was corrected after direct source inspection. It clobbers reserved vendor temporary variables; call arguments/state must not depend on those temporaries surviving the macro.
