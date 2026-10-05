# Primary sources for the combined-factor DW-FSE investigation

Research date: 2026-10-04. Sources were browsed directly as papers, author
manuscripts, or original ISMRM proceedings; publication dates below are taken
from the proceedings/year and bibliographic records, not crawler dates.
This note supplies implementable components and explicitly separates them from
complete published acquisition and reconstruction methods.

## Recommendations for the present short-train experiment

1. Retain the symmetric crusher pairs and special first-refocusing baseline.
   Test increasing **and decreasing** ramps. The decreasing-ramp primary source
   below is directly relevant to diffusion TSE, but does not establish that its
   ordering will outperform this repository's increasing ramp.
2. Use refocusing-axis XY alternation as a small RF phase factor:
   offsets `[0, 90, 0, 90, 0, 90, 0, 90]` degrees relative to the existing
   refocusing axis. Record complex echoes and separate odd/even results. This
   implements the RF component; published imaging processing is still absent.
3. For ETL 8, test a conservative nominal-angle taper such as
   `[180, 180, 175, 170, 165, 160, 155, 150]` degrees, preserving RF1 and the
   center-of-k-space RF. This is an investigator-designed, TRAPS-inspired
   simplification, not an optimized published train. Keep RF duration and RF
   centers unchanged, alter amplitude only, and report the RF-energy proxy.
4. Combine each factor with the matched crusher/centering controls. Low-angle
   trains deliberately generate longitudinal storage; a crusher schedule that
   suppresses that storage's return can remove useful signal. The interaction
   is therefore scientifically meaningful, even if it rejects the combination.

These are simulation recommendations, not scanner-setting recommendations.
Actual tests and their results are recorded in the main investigation report.

## S1. Direct diffusion-TSE evidence for variable crusher amplitude

Ye Y, Zhuo Y, An J, Zhou XJ. *A Navigated non-CPMG Turbo Spin Echo Pulse
Sequence for High Resolution Diffusion Imaging.* ISMRM 2008, abstract 759.
[Original proceedings PDF](https://cds.ismrm.org/protected/08MProceedings/PDFfiles/00759.pdf).

The published sequence combines twice-refocused diffusion preparation, a 16×16
EPI navigator, reference-based intra-shot phase correction, and slice-axis
crushers that decrease linearly from 28 to 9 mT/m. ETL is 7. The paper reports
a minimum crusher area producing approximately 3.6π intra-voxel dephasing to
suppress FIDs. The paired crushers aim to preserve primary spin echoes while
separating stimulated histories. This is evidence for testing variable moments,
not for making all crushers uniformly stronger.

**Changes needed:** paired gradient tables, full waveform diffusion calibration,
navigator acquisition and motion/eddy-current phase reconstruction for the full
published method. **Faithfulness:** an isolated decreasing ramp reproduces only
the amplitude-order idea; this repository's different timing, slice profile,
first-RF baseline and gradient strengths preclude claiming the full method.
Suppression and diffusion costs must be measured in the present model.

## S2. Short RF phase factor with a clear imaging caveat

Li Z, Ooi MB, Karis JP. *Improving X-PROP with a more stable echo train for
diffusion weighted MRI.* ISMRM 2020, abstract 4306.
[Original proceedings](https://cds.ismrm.org/protected/20MProceedings/PDFfiles/4306.html).

The original XY2 implementation alternates RF rotation axes X/Y and processes
odd/even echoes in separate blades. The study replaces it with Le Roux-derived
LRX phase modulation in a GRASE-PROPELLER acquisition and reports improved
signal stability, with contrast differences. XY requires high refocusing angles
and remains sensitive to flip-angle variation.

**Why test it:** XY can change the relative phase of primary and stored/recalled
magnetization without changing RF energy. **Changes needed:** RF phase table;
receiver-phase convention and parity-aware reconstruction for images.
**Faithfulness:** `[0,90,...]` implements alternating axes relative to the existing
axis. Echo-magnitude screening is an RF-component experiment; it omits the
published GRASE readout, blades and their reconstruction. Improved echo magnitude
alone cannot establish improved images or lower unwanted-pathway L1 share.

## S3. A reproducible stabilized nCPMG algorithm, beyond a quadratic probe

Le Roux P. *Non CPMG phase modulation, the easy way.* ISMRM 2006,
abstract 3368.
[Original proceedings PDF](https://cds.ismrm.org/protected/06MProceedings/PDFfiles/03368.pdf).

The source supplies transmitter **and receiver** phases with startup correction.
In units of full turns, initialize `d=r=0`, use `D=161/843`, then each echo
updates `r=(r+2*d) mod 1`, `R=r`, `X=R-d`, and `d=(d+D) mod 1`.
The printed 71-element correction table modifies both X and R over the first
70 echoes. Its first nine entries are
`[-.2376,-.2515,-.6971,-.2034,.4780,-.4694,-1.0170,-.3567,.2410]`;
apply `X[i]+=.05*(dR[i]+dR[i+1])` and `R[i]+=.1*dR[i+1]`.

**Changes needed:** absolute phase-frame conversion, RF and receiver tables,
startup handling, longer-train validation and reconstruction. **Faithfulness:**
a quadratic law alone omits the explicitly published corrections. An eight-echo
prefix samples the startup, not established long-train equilibrium. The
repository's old `65*k*k` table is an interference probe, not this algorithm.

## S4. Published nCPMG reconstruction requirements

Lee PK, Hargreaves BA. *A Joint Linear Reconstruction for Multi-Shot Diffusion
Weighted non-CPMG Fast Spin Echo With Full Signal.* MRM 88:2139–2156 (2022),
DOI [10.1002/mrm.29393](https://doi.org/10.1002/mrm.29393).
[Accessible original manuscript](https://pmc.ncbi.nlm.nih.gov/articles/PMC9732866/).

The study uses quadratic phase increments following seven stabilization echoes;
the out-of-phase component alternates sign between echoes. A sequential
single-shot acquisition can shift that component by FOV/2. For multiple shots,
the reconstruction forward model uses a phase navigator for one parity and its
complex conjugate for the other, together with coil sensitivities and sampling.
Startup requires approximately 150° or greater; established steady state can
remain stable down to approximately 120° in the source's model.

**Implication:** a coherent excitation-phase error is not inherently signal
loss, but echo-dependent complex modulation changes image formation.
**Changes needed:** startup, shot phase navigation, parity-aware encoding and
joint reconstruction. **Faithfulness:** none of those follows automatically from
an RF table or from plotting echo magnitudes. Source search returned full indexed
method text; direct PMC opening encountered an access challenge during this run.

## S5. Direct diffusion-HASTE evidence for variable refocusing angles

Arbabi A, Norris DG. *Half Fourier Acquisition Single Shot Turbo Spin Echo
Diffusion Encoding with Transition between Pseudo-Steady States for 3T.*
ISMRM 2021, abstract 4196.
[Original proceedings](https://cds.ismrm.org/protected/21MProceedings/PDFfiles/4196.html).

The actual train retains nominal 180° for the first 30 echoes, including startup
echoes and central k-space, then ramps over six echoes to 90° and holds 90°.
The transition starts after the odd/even echo parities have equal magnitude.
The authors compare b=0/1000 images and report reduced scanner SAR with similar
sensitivity in their protocol. The underlying TRAPS method is Hennig, Weigel,
Scheffler, MRM 49:527–535 (2003).

**Changes needed:** RF-angle table, a transition designed for the actual echo
states, acquisition ordering, slice-profile/hardware/SAR qualification.
**Faithfulness:** the proposed short taper to 150° preserves the idea of keeping
early/central echoes at 180° and reducing late RF energy. It omits the 30-echo
equilibration and 90° plateau, so cannot inherit the paper's sensitivity or SAR
claims. Lower RF-energy proxy does not constitute measured SAR.

## S6. Variable angles together with parity separation and reconstruction

Arbabi A, Khlebnikov V, Norris DG, Marques JP. *Robust and Motion-Insensitive
Approach to Diffusion-Weighted Half-Fourier Acquisition Single-Shot Turbo
Spin-Echo Imaging.* ISMRM 2022, abstract 1039.
[Original proceedings](https://cds.ismrm.org/protected/22MProceedings/PDFfiles/1039.html),
DOI [10.58530/2022/1039](https://doi.org/10.58530/2022/1039).

The actual method combines selective parity-displacing gradients, SLR pulses,
TRAPS, alternating odd/even k-space sampling, and reconstruction that estimates
the CPMG phase map and enforces conjugacy between parity images. It keeps
nominal 180° at k-space center before reducing refocusing angles. This is a
combined acquisition/reconstruction method rather than an isolated crusher trick.

**Changes needed:** gradient displacement, RF design and angle train, view order,
multicoil phase calibration and iterative reconstruction. **Faithfulness:** a
short angle taper alone is a partial adaptation. Rejecting that taper does not
reject selective parity DW-HASTE; accepting it does not demonstrate the full
method's imaging performance. This source provides a concrete future imaging
experiment when parity-aware reconstruction becomes available.

## S7. Magnetization preparation as an alternative to retaining every component

Gibbons EK, Vasanawala SS, Pauly JM, Kerr AB. *Body diffusion-weighted imaging
using magnetization prepared single-shot fast spin echo and extended parallel
imaging signal averaging.* MRM 79:3032–3044 (2018),
DOI [10.1002/mrm.26971](https://doi.org/10.1002/mrm.26971).
[Primary abstract](https://pubmed.ncbi.nlm.nih.gov/29044721/),
[author manuscript](https://pmc.ncbi.nlm.nih.gov/articles/PMC6312718/).

After diffusion weighting the method dephases transverse magnetization, tips
the MG component longitudinally, spoils the non-MG component, and uses a
compatible FSE readout. Extended parallel imaging combines repeated acquisitions
to recover useful SNR. It deliberately pays a signal penalty for phase
robustness.

**Changes needed:** stabilizer/dephaser, tip-up RF, spoiling and matched readout
rephasing, plus repeated-acquisition reconstruction. **Faithfulness:** none is
implemented by a refocusing-phase offset alone. This is a future separate
preparation study, with timing-matched controls for added RF and delays; the
current factor screen should not claim to implement it.

## S8. Adiabatic preparation and navigation

Cervantes B et al. *Isotropic resolution diffusion tensor imaging of
lumbosacral and sciatic nerves using a phase-corrected diffusion-prepared 3D
turbo spin echo.* MRM 80:609–618 (2018), DOI
[10.1002/mrm.27072](https://doi.org/10.1002/mrm.27072).
[Accessible original manuscript](https://pmc.ncbi.nlm.nih.gov/articles/PMC5947302/).
[Direct university-hosted paper](https://mediatum.ub.tum.de/doc/1525810/document.pdf).

The actual preparation uses a modified BIR-4 RF configuration with gaps for
diffusion gradients, a magnitude stabilizer before tip-up, and balancing during
the TSE readout. RF segments total 10 ms excluding gaps. Startup echoes acquire
low-resolution navigators. Diffusion navigator phase relative to a T2 reference
corrects shot-dependent phase by complex multiplication before final 3D
reconstruction.

**Why it may help:** preparation robustness and explicit phase correction target
different problems from crusher-moment recurrence. **Changes needed:** adiabatic
RF shapes, preparation timing, stabilizer moments, navigator/reference scans and
hybrid-space reconstruction. **Faithfulness:** this is a researched future option;
no isolated current override constitutes a BIR-4 or navigated implementation.
The full paper was verified through its university-hosted PDF.

## Interpretation boundaries for all sources

Matched symmetric gradient lobes preserve primary gradient-history cancellation
in a static instantaneous-RF idealization. Varying pair moments can break
cancellation for histories that visit the longitudinal axis. It also changes
diffusion exposure; gradient area, gradient energy, b trace and b tensor are
different constraints and must not be conflated. The minimum-dephasing rule from
S1 depends on voxel dimensions and does not transfer as a fixed mT/m threshold.

RF phase tables rotate pathway coefficients. A useful net signal may increase
through constructive interference without decreasing the non-primary L1 share.
Angle trains change both pathway magnitudes and longitudinal storage. Startup
and receiver/reconstruction requirements are physical parts of the method, not
optional labels. Preserve complex signal; judge cancellation using complex sums.

All eight sources are primary research or original conference proceedings.
S1/S2/S3/S5/S6 were read directly in full proceedings form; S8 was verified in
the university-hosted full paper; S4 used indexed primary method text where
direct access was challenged; S7 used its primary
abstract and indexed author-manuscript text. No inaccessible numerical recipe
is represented as implemented. No scanner implementation was modified by this
literature task.
