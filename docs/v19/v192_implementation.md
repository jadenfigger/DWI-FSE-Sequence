# v192 Alsop integration status and insertion contract

**METHOD NOT IMPLEMENTED.** The reserved `.ppl` and companion `.ppr` are a fail-closed integration scaffold, not a scanner sequence. The original v18 body is retained byte-for-byte after removing the scaffold header and runtime guard. No Alsop RF/gradient/ADC block has been added. The PPR changes only the source pointer; its two-echo protocol is inherited input, not the requested eight-echo adaptation. Both filenames are deliverable placeholders with explicit operational gates, not evidence of implementation.

The compile-stop uses the manual's documented `#include` directive and an intentionally absent project-local guard `V192_METHOD_NOT_IMPLEMENTED_BLOCK.pph`, before any vendor library loading. A second unconditional `printf`/`goto end` precedes `tstex_15.pph` and all hardware calls in `main`. It blocks the retained v18 body even if the compile-stop line is manually removed. Neither creating the guard include nor deleting either gate completes the method.

## Verified inputs

| Input | SHA-256 / finding |
|---|---|
| `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl` | `3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2` |
| Companion `FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppr` | `78c9845d090183d59cba956f36305e0e19d4a8dcdb3ae707062839159fd904da`; first line already references the local v18 filename |
| Five top-level includes | Present: `stdfn_15.pph`, `var_20.pph`, `offst_20.pph`, `m3040_15.pph`, `m3031_15.pph` |
| Nested include | `tstex_15.pph`, v18 line 534, missing; contains unknown initialization/control behavior |
| Vendor libraries | All eleven v18 `#use` paths unavailable locally; complete list in `v192_design_audit.json` |
| Compiler | No target compiler or event trace supplied; no vendor compilation performed |

The source is actual supplied v18, not reconstructed v17 or the older Pulseq model. The baseline hash is checked before every audit run. All line numbers below refer to verified v18 and are machine-extracted in the JSON.

## Source-linked method requirements

Scientific sources are [Alsop 1997](https://doi.org/10.1002/mrm.1910380404), particularly pp. 529-530; [Gibbons et al.](https://doi.org/10.1002/mrm.26971), pp. 3034 and 3036, Figures 3-4 and supplement S2; and [Le Roux and Hinks 1993](https://doi.org/10.1002/mrm.1910300208). Vendor interfaces are documented in the local EVO manual, §§3.3.1.9-14, 4.4.1 and 5.7.4, and in the actual supplied includes. Prior [preparation comparison](../prepared_fse_comparison.md) and [replication audit](../gibbons_replication_audit.md) are contextual evidence of approximations, not replacement scanner events.

| Element | Scientific requirement | Actual v18 integration point / disposition |
|---|---|---|
| Diffusion preparation | Excite and spin-refocus before elimination; prep echo at elimination RF center | v18 RF excitation 3721-3810 and first refocus/diffusion 3837-3932 currently lead directly to the first ADC. Must split preparation refocus from imaging refocus and its echo index. Not implemented |
| Added dephasing | Distribute transverse phase across slice; compare 2 and 4 cycles | New moment after second diffusion lobe and before elimination; retain RF slice compensation separately. For 6 mm: 333.333/666.667 cycles/m; 1 mm adaptation: 2000/4000 cycles/m |
| Selective elimination | Store unwanted quadrature on Mz; retain desired MG component transverse | RF axis parallel to imaging refocus axis, opposite in purpose to ss-MGOT storage. Requires measured complex transfer of selective 90° RF, new RF index/calibration and timing centers |
| Spoiling/re-excitation | Neither ss-MGOT storage-spoiler-reexcitation step belongs here | No MGOT spoiler or re-excitation is to be inserted into v192. Longitudinal unwanted component remains and may reappear under finite RF |
| Imaging train | Low-angle tailored Alsop/Le Roux train | `NEWSHAPE_SETUP(rfnum,p180_mul)` at 3858 uses the same v18 shape/scaling every echo. A separate indexed shape/amplitude schedule is required, not relabeling fixed `p180_scale` |
| Recall/restoration | Recall selected harmonic at every ADC; restore before subsequent RF | Modify first post crusher by +D. Restore -D after ADC; it can fuse into later pre crushers only. First pre stays C for an Alsop retained transverse component with ±D harmonics |
| Readout/PE | Exactly one train-entry read prephaser; PE rewind every echo | `read_pre_list` constructed 1934 and launched 3722; presently coupled to initial excitation. Move deliberately to imaging entrance; do not leave it there and add a duplicate |
| Receiver | Preserve coherent phase with phase cycle and frequency offsets | `phase_90=aqphase(...)*deg_90` 2569; `phase_180=phase_90+3*deg_90` 2570; offsets/phase corrections 2517-2611, 3047-3088, 3997-4010 and 4042-4061 require complete re-derivation |

Original Alsop places elimination half an echo spacing before first imaging refocus. The low-angle example's first five flips are 142.2°, 94.9°, 69.2°, 63.0°, 60.2°, approaching 60°. This is a source-derived candidate design, not Gibbons' complete exact waveform/schedule. Completing echoes 6-8 as exactly 60° would be a disclosed approximation. Original Alsop discards two train echoes before phase encoding; an eight-acquired-echo adaptation would then play ten RF pulses and needs the appropriate extended schedule and recalculated PE ordering. Keeping eight physical RF pulses and acquiring all eight is a separate departure that must be labeled and reviewed. No choice has been silently applied to the companion PPR.

Gibbons' reference simulation geometry is 3000 isochromats over 30 mm, 6-mm slice (18-mm ss-MGOT prep slab). Figure 3/S2 preparation profiles use a 45° initial excitation phase and two added cycles. Figure 4 uses 0°, 45°, 90° and 2/4 cycles; its muscle constants are T1=1300 ms and T2=32 ms. These are distinct from an eight-echo scanner adaptation. S1 compares ss-MGOT and nCPMG, not Alsop. Exact Gibbons Alsop refocus amplitudes/coefficient files remain absent.

## Tip axis and harmonic bookkeeping

The paper's MG X direction corresponds to the repository's displayed MG My direction under an in-plane rotation of -90°. With the repository's left-handed rotation convention and a reference 0° excitation, a 270° elimination RF axis gives

`Mx_after = Mx_before*cos(alpha) + Mz_before*sin(alpha)`

`My_after = My_before`

`Mz_after = -Mx_before*sin(alpha) + Mz_before*cos(alpha)`.

At ideal alpha=90° and pre-tip Mz=0, desired My stays transverse and unwanted Mx maps to -Mz. The 180° tip axis used to store desired My in the earlier ss-MGOT adaptation would implement the wrong method here. The scanner candidate is `phase_90+3*deg_90`, aligned with v18's refocus axis, but every tip/train phase must share the appropriate reference accumulated through frequency changes. This is a coordinate/physics design; vendor RF coefficients and console polarity are needed to establish the physical scanner transfer. The manual gives `phase_increment(1)`=0.225° per unit and v18 calculates `deg_90=400`; 270° is 1200 units before phase-cycle/frequency corrections.

In the same convention, initial dephasing gives ±D harmonics after transverse projection. The coherent recalled signal is one-half the original ideal complex signal, up to a conjugation/sign controlled by selected harmonic and receiver frame. It is not full-signal preservation. At nominal B1=0.8, even an otherwise ideal hard tip has unwanted transverse transfer `cos(72°)=0.3090`; spatial edges and off-resonance further change that transfer. The hard-pulse expression is not a validated selective slice profile. Plot signed components and coherent spatial mean separately; retain local vectors.

Let C be an ordinary balanced slice crusher moment and D the added preparation modulation magnitude. For v192's ±D transverse content:

1. First imaging RF: pre crusher C, post crusher C+D. This recalls a DC harmonic at ADC1.
2. After ADC1: restore -D before ordinary next pre C; fuse these only when justified, giving next pre C-D.
3. Later RF pulses: pre C-D, post C+D, where restoration is already fused. Repeat through final ADC; decide whether final restoration remains before any recovery/spoiler.

Blindly copying the ss-MGOT drawing as first pre C-D/post C+D introduces an effective 2D excursion at RF1 and misses the initial ±D DC harmonic. ss-MGOT re-excitation has a different transfer/modulation history. The independent physics review identified this first-pulse exception. The Gibbons schematic's subtraction/addition needs this method-specific entry treatment. Original Alsop's pp. 529-530 caution about dephase/crusher harmonics when both use Gz also requires checking the full C/D schedule for unwanted DC pathways; logical moment balance alone is insufficient.

## Feasibility calculations supported by inputs

For an **assumed linear trapezoid** with ramp r, flat p and PPR calibration H=`grad_var[0]` Hz/mm at 32767 DAC, the added moment is

`D_cycles_per_m = DAC * H * (p_us+r_us)/(32767*1000)`.

There are two ramps; their combined area equals one ramp duration times amplitude. A separate lobe occupies p+2r, while a fused lobe can retain duration but needs different signed amplitudes. These are ideal-ramp calculations until `g3040_15.seq` samples/trace are available; they do not certify actual vendor ramp area or physical gradient delay.

Using inherited H=25447, r=200 us, p=1000 us, C=5482 DAC:

| Slice / cycles | Target cycles/m | Nearest D DAC | First pre / later pre / post DAC | Quantized area error |
|---|---:|---:|---|---:|
| 1 mm / 2 | 2000 | 2146 | 5482 / 3336 / 7628 | -0.0044% |
| 1 mm / 4 | 4000 | 4292 | 5482 / 1190 / 9774 | -0.0044% |
| 6 mm / 2 | 333.333 | 358 | 5482 / 5124 / 5840 | +0.0888% |
| 6 mm / 4 | 666.667 | 715 | 5482 / 4767 / 6197 | -0.0510% |

All fit a logical ±32767 bound. They are not certified physical amplitudes/slew, especially after oblique rotation; the configured PPR ceilings 32767 are numeric ceilings, not independently rated hardware. `CREATE_MATRIX` must verify physical combinations at every orientation and finish after `caldelay` before matrix selection. Do not mutate active crusher secondary matrices inside an RF/gradient interval.

For reference Gibbons preparation pulses, duration 3.2 ms and TBW3.55 imply 1109.375-Hz nominal bandwidth. Relative to v18's nominal PARSETUP1070-Hz value, selector DAC magnitude at the inherited 1-mm protocol would be approximately 1428 instead of the current 3-kHz RF's 3860; slice-selection moment is distinct from D and crusher C. This arithmetic does not specify an RF waveform or its compensating spatial phase. No Gz preparation event is globally slab-scaled in this design.

The supplied PPR has TE=36 ms and ESP=36 ms. v18's TE is the first acquired diffusion echo; the new method needs separate preparation echo Tprep, first acquired echo Tfirst, and effective TE Tfirst+(central acquired index-1)*ESP. Original Alsop timing places elimination center at Tprep and first imaging refocus center Tprep+ESP/2, so first physical imaging echo is Tprep+ESP before accounting for deliberate startup discards. T1/T2 weighting and effective b must be calculated from actual landmarks/coherences, not inherited TE labels. There is no measured Tprep or valid new TE minimum until elimination RF and its gradients are known.

Recompute v18 `min_pre/min_post` (2640-2648), `te_a/te_b` (2903-2911), `te_balance_bl_esp` (3036), RF center delays (3847-3903) and TR accumulation. A separate ideal 1000-us flat/200-us-ramp moment costs 1400 us; added RF needs its measured duration/ramp/settling budget. Every `starttimer`/`waittimer` section needs instruction-cost budget: EVO pp.90-91 documents 5-ms extension on missed deadlines, and phase/frequency/matrix calls cost time. Negative residual or missed deadline must reject the requested protocol, never enlarge TE silently. Integer expressions must widen before multiplication, round/check in long before int conversion, account for exact gradient raster, and exclude -32768 DAC.

## Branch inventory and required future behavior

This is a source inspection, not execution validation. Both gates stop every branch before initialization. No imaging mode is currently enabled in v192.

| Existing execution path | v18 site | Required method integration before enabling |
|---|---|---|
| Validator | 2100 and 2464; timing exit3318 | Worst-case prep/train lengths and all diffusion rows/orientations must pass before exit; no skipping new guards |
| Imaging | 3837-4172 | One preparation refocus outside imaging index; first-pre exception; recall every ADC; preserve PE rewind |
| Navigator | 2488-2489, 3877-3879,4005,4337 | `nav_cnt=0` suppresses PE, not method D/recall; same preparation and RF train for navigator |
| Dummy acquisitions | 4025-4026,4314-4320 | RF and gradients still play; suppress receiver storage only; reset preparation/RF indices per shot |
| Skipped first echoes | 3865-3873,4013-4021 | Count physical RF separately from acquired echo; moment/schedule array bounds cover all physical pulses |
| Multislice/orientation | `multislice_loop`2503,4310 | Per-slice RF offset/phase recalculated for elimination; do not inherit 1-mm hardcoded offset2527 for arbitrary thickness |
| Slice batching/interleave | 2480,4349; vendor macros | No shared preparation state across slice/batch; verify library initializations after missing tstex is supplied |
| Diffusion off and DAC1 b0 | 2455-2464,3810,3910 | Define method control with full preparation even for nominal b0; retaining v18 as off-path is a separate explicit control, never silently call it Alsop |
| Acquisition ordering | PE0/1/2/5/6/7 at 894-1275 | Rebuild physical/acquired-central echo mapping after discards; preserve pfgen/reorder interface; no PSF claim from eight amplitudes |
| Scheduled crushers | 1393-1541,2065-2097,4066 | Preserve signed C schedule and add D algebra per physical echo; check combined DAC/slew before narrowing; avoid active matrix writes |
| Flow compensation /3D | 1669-1692,1939-1946,3860-3879 | Dedicated spatial/coherence/TE validation; no assumed compatible branch. Reject until independently traced |
| Dixon /DE | 1871-1892,2984-2989,4183-4249 | Extra RF/frequency history affects selection; reject until method-specific derivation exists. Existing independent crushers already reject DE |
| Presat /CHESS /CEST | 3521-3720 | Keep before preparation; adjust TR accounting, preserve RF/gradient channel reset and offset buffers |
| Gating /TR arrays | 2130-2446,1897-1904,3438-3508 | Preparation starts after gate; minimum shot duration and per-entry TR feasible; no state reuse across hostrequest |

## Missing dependencies, RF delivery and validation status

Supply the actual `tstex_15.pph`; all libraries named in JSON, especially `RFstd44.seq` and `g3040_15.seq`; and an example RF `.seq` with documented WavEd export/edit workflow or original waveform coefficients. Existing `NEWSHAPE_MAC` records `.address/.waits/.board1` and nominal duration/bandwidth; `NEWSHAPE_SETUP` loads scale/address/waits. These interfaces are verified, but they do not define the vendor RF waveform file's samples/format. Arbitrary text sampled RF would not be a scanner-compatible asset. No invented vendor names/macros/assets are provided.

Also needed are the exact selected Alsop/Gibbons RF transfer/schedule or a redesigned approximate counterpart with disclosed and measured error, nominal/reduced B1 calibration, target physical amplitude/slew and RF power limits, compiler version/toolchain, and exported RF/gradient/ADC trace with actual delays. The user already authorizes disclosed approximations; no additional permission is required for that design work. Once interfaces and inputs are available, design selective RF and validate complex magnitude/spatial phase before creating calibrated WavEd assets; install only into a separate review directory, never overwrite console libraries as part of this task.

`python docs/v19/v192_design_audit.py` reproduces baseline/source-preservation/PPR-pointer checks, dependency inventory, first/later crusher feasibility arithmetic, and rejection examples. It writes `v192_design_audit.json`; this is **not** a PPL parser, compiler trace, Bloch simulation, or hardware validation.

| Stage | Status |
|---|---|
| Actual v18 verified/preserved | Yes, hashes and byte comparison |
| Alsop method implemented in PPL | **No**; reserved gated scaffold only |
| Scientific/branch/moment design | Prepared; independently reviewed design limitations recorded |
| Scanner-compatible RF assets | Not produced; coefficients/vendor asset workflow absent |
| Compiled | No |
| PPL-to-event trace verified | No |
| Played waveform simulated | No |
| Independent review | Source/physics reviewers inspect gates and design; see integrated review reports |
| Verified on scanner | No; no deployment performed |

Required future simulation landmarks remain A, B, after elimination, preparation endpoint before leading imaging crusher, after that crusher before first imaging RF, and ADC1/ADC2/final middle sample. For Alsop, post-spoiler and post-reexcitation landmarks are not applicable. The leading crusher changes displayed Mx/My, so preparation leakage must be assessed at the earlier endpoint. Use 0/45/90° initial phase, nominal/reduced B1, justified B0 sweep, RF/spatial convergence, ADC/snapshot agreement and independent Bloch evolution against actually traced pulses before claiming method validation.
