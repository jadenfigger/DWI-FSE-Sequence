# v191 ss-MGOT source reservation and integration contract

**The ss-MGOT mechanism is not implemented.** The reserved `.1.91.ppl` is supplied v18 with an explanatory header, a deliberately unresolved `#include`, and an unconditional `printf`/`goto end` before hardware setup. Its companion PPR changes only the PPL filename. These files cannot be presented as a working, compiled or simulated ss-MGOT sequence. They reserve the requested names while preserving the verified starting point for the work that requires missing inputs.

The missing-include gate uses the documented EVO `#include` syntax (manual §3.1, p46). Its filename is deliberately descriptive and absent, **not an RF library entry**. No `#error` directive is used because its support was not found in the supplied manual. The early runtime exit adds protection if someone accidentally supplies an empty include. Neither gate is an implementation-completion switch; do not remove them until the entire integration and independent validation are complete.

## Verified starting source

| Input | SHA-256 |
|---|---|
| [Actual supplied v18 PPL](../../scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl) | `3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2` |
| [Companion v18 PPR](../../scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppr) | `78c9845d090183d59cba956f36305e0e19d4a8dcdb3ae707062839159fd904da` |

The supplied filename and companion's `:PPL` line identify v18. The PPL header's last version entry still says 1.7; no attempt was made to infer an undocumented 1.8 change from that stale header. The acquisition archive records `G:\J_Figger\...1.8.ppl`; the absent G: drive means identity with the exact historical scanner bytes cannot be independently proved. The supplied source is now available and hash-verified, superseding the earlier repository-availability limitation in the October 5 audit. It is not a reconstruction from PPR metadata or a silent substitution of v17.

Five include files are present and inspected: `stdfn_15.pph`, `var_20.pph`, `offst_20.pph`, `m3040_15.pph`, `m3031_15.pph`. Their hashes are in [the source audit](v191_source_audit.json). `tstex_15.pph`, included inside `main` at v18 line 534, is absent. The `#use` inputs are unavailable:

- RF: `RFstd44.seq`, `gs_240Hz.seq`, `presat.seq`, `opt90_a.seq`, `opt90_as.seq`, `asym.seq`, `hypsec.seq`, `rfchess.seq`, `9lobsinb.seq`, `19lobsinb.seq`.
- Gradient: `g3040_15.seq`.

These are actual v18 references at `c:\smis\seqlib`; no invented filenames or pulse frames have been added. Compiler, vendor support/link libraries and compiled event traces are also unavailable.

## Source-linked requirements before implementation

Scientific sources: supplied `Gibbons_2017.pdf` (journal pp3034–3037, Figures 1, 3 and 4), supplied `mrm26971-sup-0001-suppinfo01.pdf` (S1–S2), [primary article](https://onlinelibrary.wiley.com/doi/10.1002/mrm.26971). Existing [replication audit](../gibbons_replication_audit.md), [prepared comparison](../prepared_fse_comparison.md) and [October 5 audit](../data/oct05_protocol_audit.md) are context and record prior limitations; they are not executable specifications.

| Requirement | Published benchmark | v18 adaptation contract / status | Source |
|---|---|---|---|
| Diffusion preparation | Slab-selective excitation and spin echo; 18-mm preparation slab, 6-mm imaged slice | Separate preparation RF/selection matrix/frequency from imaging RF/selection. Scale slab **selection** and its compensation by actual bandwidth/slab geometry; do not scale preparation crushers or diffusion Gz automatically | Gibbons Methods p3036; Fig1; v18 slice scaling lines1625–1665 |
| Preparation excitation | SLR, TBW3.55, 3.2ms, peak0.065G | Coefficients absent. Vendor sinc cannot be relabeled SLR. Need calibrated scanner waveform and measured transfer magnitude/phase | Gibbons p3036 |
| Preparation spin echo | SLR, TBW3.55, 3.2ms, peak0.191G | Separate preparation refocusing slot; v18 currently shares `rfnum` with all imaging refocusing | Gibbons p3036; v18 lines3741,3858 |
| Added dephasing | Two cycles over the 6-mm slice for Fig3/S2; two and four cycles for Fig4 | Define signed physical area independently of preparation slab selection, RF crushers and slice-selection compensation. At6mm, magnitudes333.333 or666.667 cycles/m; at1mm adaptation2000 or4000 cycles/m. Hardware feasibility unknown | Gibbons p3036; Fig1 |
| Desired MG storage | −90y selective tip-up stores desired paper X on Mz | Scanner-frame candidate phase `phase_90+2*deg_90`; not console calibrated. No substituted Hamming spatial sinc | Fig1; RF/physics independent derivation |
| Tip-up spectral response | Six-subpulse maximum-phase equiripple spectral envelope: water ±128Hz; lipid stopband−549…−306Hz; transfer0.995±0.005 water,0.05±0.01 stopband | Need actual complex RF and synchronized gradient samples. Passband and spatial phase must be verified jointly over B0/B1 | Gibbons p3036 |
| Tip-up spatial response | Linear-phase least-squares subpulse TBW3.55; transfer0.995±0.005 passband,0±0.01 stopband;10-mm selection; VERSE onto positive ramps | 10mm tip-up,18mm preparation slab and6mm imaging slice are **three distinct selections**. Do not apply a universal factor3 | Gibbons p3036 |
| Tip-up timing/hardware |5.64ms RF; flyback period1.022ms; peakG22.9mT/m, peakB1 0.226G | Cannot represent this as one constant Gz selection lobe. New MR3040 frame/list plus RF frame timing must be designed from supported WavEd format | Gibbons p3036; EVO §5.4.2 p132 |
| Spoiling while stored | Gy eight cycles across the voxel | Preserve local transverse vectors. Compute coherent spatial mean; no artificial Mx/My reset. Logical Gy depends on orientation. RF/gradient asset and calibration needed | Gibbons p3034–3035 |
| Imaging re-excitation | Windowed sinc TBW1.54,1.2ms | Distinct RF slot and compensation response. Do not copy v18's1.332ms/TBW≈4 frame and claim published response | Gibbons p3037; previous replication audit |
| CPMG train | Paper αx; ss-MGOT Busse tailored train, minimum55°, low-order-PE60° | Keep adaptation eight echoes separate from benchmark; no exact sampled flip-angle schedule supplied. Preserve phase cycling common axis and calculate receiver correction for changed frequency history | Gibbons p3036; EVO pp53–54 |
| Recall/restoration | Add recall to post-RF crusher; subtract restoration from subsequent pre-RF crusher | First pre-imaging crusher needs separate handling. See recurrence below. Every ADC must be checked using actual gradient areas | Fig1 caption and independent physics review |
| Receiver demodulation | CPMG-compatible phase and coherent acquisition/reconstruction | Keep PE/off-resonance/group-delay correction, replace timing-dependent history with actual prep-to-ADC history. Do not blindly reuse v18 `phase_ang` | EVO §3.3.1.8–14 pp52–54; v18 lines3051–3082,4008 |
| Imaging reference |ESP4.20ms; nominal76 echoes,46 acquired with acceleration/PF;128×128; Figure4T1=1300ms,T2=32ms | v18 companion is2 echoes,TE36ms,ESP36ms,1mm slice,128 samples/20kHz. No parameter change to an eight-echo or published reference was made while source is blocked | Gibbons pp3036–3037; companion PPR |

RF amplitudes above are published design peaks, not scanner RF DAC calibration values. Water/lipid spectral locations belong to the publication's implementation and must be adapted explicitly to the scanner field and chemical-shift convention rather than copied as universal fat offsets.

## Phase-frame contract

Figure1 uses `90y → 180x → −90y → 90y → αx`. A common RF-axis shift−90° maps this to the v18 basis `90x →180(−y)→90(−x)→90x→α(−y)`. Relative to the phase cycle, candidate scanner phase words are respectively `phase_90`, `phase_90+3*deg_90`, `phase_90+2*deg_90`, `phase_90`, `phase_90+3*deg_90`. In the repository's left-handed Bloch frame, this maps desired My to +Mz during storage and +Mz to My at re-excitation. Paper MG=X corresponds to repository My under the coordinate rotation.

This is an independently checked coordinate derivation, not an assertion that console RF polarity, gradient polarity or receiver sign have been calibrated. `var_20.pph` fixes `phase_res=225` (0.225°), source lines1327 onward derive `deg_90=400`, and EVO pp53–54 document `phase_increment(1)`. Integer phase words should wrap to `[0,deg_360)` after signed calculations; every preparation and imaging pulse must share the existing `aqphase(no_acq,phase_cycle)` cycle.

The phase of the perturbed preparation excitation is a simulation variable; it must not rotate the tip-up/re-excitation/train axes together, which would remove the intended non-MG challenge. Slab, tip-up and imaging RF offsets must be computed from their own selection gradients and slice location. EVO pp52–53 document accumulated phase from phase-continuous offset changes. Receiver phase requires the integral of this actual offset history, including storage and re-excitation, not only the original excitation-to-first-echo period.

## Signed moment and first-crusher contract

Use physical area `A=gamma_Hz_per_T * integral(Gz dt)` in cycles/m and repository evolution `Mxy→Mxy*exp(−i2πAz)`. Define D as the actual additional preparation dephasing area. After storage, coherent spoiling and re-excitation, ideal MG modulation is proportional to a **real** `cos(2πDz+phi)`; it has both +D and−D coherence orders. A spoiler does not remove each local transverse vector.

For an instantaneous ideal refocusing pulse, a branch with coherence order q evolves over pre/post moments L,P as `q_after=P−L−q`. A selected branch at an ADC must have q_after=0; this check must include actual selection/crusher moments and any moment between RF and ADC. In the simple matched-crusher derivation:

| Echo | Pre-RF physical moment | Post-RF physical moment | Ideal branch check |
|---|---|---|---|
| First | C | C+D | q_after=D−q; one of the prepared ±D branches reaches DC |
| Subsequent | C−D, including restoration after prior ADC | C+D | q_after=2D−q; paired cosine branches exchange through the train |

The first pre-RF event must not blindly receive the later `−D` restoration. Using `C−D` and `C+D` for the first pulse yields effective2D and misses the prepared ±D DC recall. Alternatively a symmetric ±R first correction would require2R=D and a redesigned subsequent history. The caption's qualitative area additions are insufficient to justify copying identical first/later DAC edits.

This derivation does not validate finite RF behavior or variable-angle stimulated pathways. Full Bloch/coherence simulation must evolve the actual selected waveforms; it must preserve both branches and Mz pathways. Imaging crushers, slab rephasers, selection gradients and recall moments need separate signed ledger entries. At each ADC middle sample, measure **total** effective slice/read/PE moments rather than comparing isolated DAC amplitudes.

## Integration locations and all execution branches

All line numbers below refer to unchanged v18, not the gated file's shifted lines. None of these method changes is scheduled yet.

| v18 execution path / location | Required integration and audit |
|---|---|
| RF registration634–654; durations/bandwidth/selection near1530–1665 | Assign actual library frames to preparation90/preparation180/tip-up/imaging90/imaging-refocusing separately. Existing arrays have40 entries; final indices must be bound-checked. Duration need not equal excitation duration; current single `rfnum` assumption must be removed deliberately |
| Gradient lists1910–2050 | Replace preparation selection independently; add verified synchronized tip-up gradient asset; spoiler and re-excitation compensation; first/later recall/restoration. `g3040_15.seq` samples needed to integrate ramp/flat area |
| Diffusion row2346–2483 | Continue validation for all rows including b=0. Zero-amplitude diffusion gradients still consume time (`diff_on`, not amplitude). New b calculation must use total played vector gradient history with RF coherence signs |
| Dummy/discard2484 and4310 onward | Preparation must execute for dummy scans and no_disacq; discarding ADC does not skip RF or moments. Reset per-shot phase/coherence, first-pulse state and flip-angle schedule |
| Multislice2503; slice_block2614 | Compute preparation slab/tip-up/re-excitation offsets at each current slice and orientation. Prepare all matrices while zero matrix active; restart preparation for every navigator/imaging shot and phase-cycle acquisition |
| Pre-saturation/CHESS/MTC3460–3724 | Preserve optional modules outside deliberate changes; re-evaluate TR/SAR and RF/frequency state before preparation. They cannot silently share altered imaging selection bandwidth |
| Excitation3741 through diffusion pair3940 | Separate diffusion-preparation spin echo from imaging train. Existing first180 currently leads directly to first acquired ADC; insert dephasing/tip-up/spoiling/re-excitation at preparation endpoint before leading imaging crusher, replacing first-echo timing model |
| Imaging echo_loop3832 and ADC3990–4095 | Reset imaging echo index after preparation spin echo; validate first-vs-later signed moments and flip-angle index at every ADC, including final. Preserve PE lookup/rewind and receiver/group-delay corrections |
| Navigator nav_cnt2489, PE indices914–1239,4337 | Navigator and imaging paths both require complete preparation and train. `nav_cnt=0` only suppresses phase encoding; it must not suppress spoiler, re-excitation, recall/restoration or reset |
| Single-echo/PE_order5; single-shot/PE_order2; PE orders0,1,3,6,7 | Derive image center echo and effectiveTE for actual acquired order. Unsupported/unsolved combinations must be rejected with specific messages before playing RF; cannot reuse a single first-echo branch |
| FSE3D/no_views_2 and slice/slab_ratio | Published method is2D slice-selective SS-FSE. v18 3D slab/PE2 mode is a distinct adaptation requiring explicit design; do not apply the2D slice-modulation method by silently changing all Gz terms |
| Echo discard; oversampling; variableTR; gating/clustering; interleave/batch | Verify array/loop resets and durations per executed shot. Discard echoes count as played RFs. MinTR must include all preparation and imaging events and gating overhead |
| Driven equilibrium4200–4270 | Current extra final180 and DE90 reverse v18 excitation model. Must reject until a separate ss-MGOT terminal-coherence/DE design is validated; preparation duration cannot simply become the reverse-DE delay |
| Dixon2800–3040; flow_comp3300–3320 | New multi-RF preparation changes phase/frequency and moment history. Retain disabled defaults; reject enabled combinations until center timings/flow moment constraints are independently rederived |
| Crusher original/up/alternate/up+alternate/down/custom | Published recall/restoration corrections must be added to independently validated baseline crushers, not substituted into the user schedule or multiplied with it. Alternating means signed `[+1,−1,+1,−1,...]` in played refocusing index, defined separately for preparation vs imaging |

No branch can currently execute from the v191 entry point because of the compile gate and early exit. Retained v18 code is context, not a claim that these branches have been adapted.

## Timing and hardware requirements

Maintain three distinct TE definitions: preparation spin-echo center; first acquired ADC center measured from original preparation excitation; effective imagingTE at the k-space-center echo, together with time since imaging re-excitation. The storage interval changes T1 weighting and breaks a simple overall spin-echo TE definition. Figure4's imaging signal model and S1's nCPMG comparison are distinct from Figure3/S2 A/B/C preparation profiles.

Current v18 `te` is first DWI echo, while `esp` controls later intervals. New preparation refocusing no longer counts as imaging echo1. New timing must be centered on actual RF waveform centers, including asymmetric/maximum-phase tip-up response. The source's empirical constants (`−185`, `−156`, timer branch overhead adjustments) apply to its original code path and cannot be transferred to added statements. No numerical new played timing table can be justified yet.

EVO pp90–91 describe a timer cycle of 50,000 ticks, each 100 ns. A missed `waittimer` adds 5 ms; all inserted function/branch/DSP overhead must be accounted before targets are selected. `stdfn_15.pph` declares `waittimer(int)` although existing code sometimes uses long intermediates; check signed narrowing before every call. `IntToLong` must promote operands **before** multiplication; assigning an overflowed 16-bit product to long does not repair it (manual pp97–101).

`CREATE_MATRIX`/secondary matrix use is available in `m3040_15.pph` but creation must target inactive matrices; `caldelay=100us` must finish before selection. Both logical and physically rotated/summed DACs, calibrated amplitude/slew, RF amplitude and waveform waits are needed for hardware validation. Current v18 clips p90/p180 RF scales at2047 (lines2621–2626); a completed method must instead reject infeasible requested calibration, without changing v18 itself. A square DAC/time formula is not enough to prove trapezoid area because the vendor gradient frame samples are missing.

Readout prephasing must be allocated once. V18 `read_pre_list` and `gr_dp` already distribute prephasing over excitation/refocusing/readout sections; a new imaging excitation must replace the appropriate original history rather than add another complete prephaser. Phase encoding must rewind using the same lookup as the corresponding ADC. Gy spoiler needs independent timing rather than sharing PE encode/rewind lobes. Full waveform integrals must determine cross terms and effective diffusion weighting.

## Validation and completion status

Run `python examples/v191_source_audit.py` for byte-level preservation and gate checks. The audit records hashes of both original inputs, reserved outputs and present include files. It verifies that v191 source differs only by the header and gates and its PPR only by the source reference. It is explicitly **not** a compiler, event trace or PPL-to-waveform mapper.

| Stage | Status |
|---|---|
| Actual supplied v18 located/hash verified | Complete |
| v18 preserved unchanged | Source audit complete |
| Source-linked requirements, phase/moment/branch integration contract | Complete; independent review requested |
| v191 ss-MGOT acquisition mechanism | **Not implemented** |
| Scanner-compatible new RF/gradient assets | **Not delivered**; source samples/format/calibration absent |
| Vendor compilation | **Unavailable / not attempted** |
| Scheduled event-trace verification | **Unavailable** |
| Scheduled v191 RF/gradient/ADC simulation | **Unavailable** |
| Scanner verification | **Not performed** |

No played sequence diagram, signed component plots or echo-train result is generated from this blocked source. Existing Pulseq figures are research adaptations and cannot certify this PPL. Once inputs arrive, validation must use exported/compiled scheduled events,3000isochromats/30mm and6mm/18mm reference geometry, correct per-figure relaxation settings, B1/B0 sweeps, RF/spatial convergence, coherent y-spoiling, and independent Bloch calculations. Explicit landmarks must include A, B, tip-up, spoiler, re-excitation+compensation, preparation endpoint **before** the leading imaging crusher, literal pre-RF **after** that crusher, and first/second/final ADC middle samples. Scanner eight-echo control comparisons require actual v18 waveform traces and protocol ordering; no PSF/image-quality claim follows from eight voxel amplitudes alone.

Required next inputs are `tstex_15.pph`; exact used RF/gradient WavEd libraries plus any transitive dependencies; documented creation/loading/calibration format for new complex RF and synchronized gradient frames; console compiler/support files and warning/event-trace exports; scanner gradient delay/amplitude/slew and RF calibration/rating; sampled published tip-up/SLR/re-excitation assets or sufficient validated design access; and explicit tailored flip-angle table/design targets and acquisition order for reference and adaptation. These missing inputs are operational blockers, not an invitation to invent nominal waveforms or library frames.
