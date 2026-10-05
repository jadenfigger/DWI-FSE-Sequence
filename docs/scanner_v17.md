# DW-FSE twoTE-1.7 implementation and validation

3 October 2026. v1.6 PPL/PPR remain unchanged. The command-line generator still
defaults to v1.6. Select a v1.7 PPR explicitly; its `:PPL` directive selects the
new arithmetic and centering correction, even if the protocol file is renamed.

## Scanner files and parameters

- [v1.7 PPL](../scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.7.ppl) and
  [default PPR](../scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.7.ppr): original schedule.
- [Increasing PPR](../experiments/FSE-DWI_10-04-2026_v17_increasing/FSE_dwi_CPMG_non_CPMG_twoTE-1.7-increasing.ppr):
  ETL 8, TE 36 ms, ESP 16 ms, diffusion rows 0/1000, read direction, step 40%.
- [Increasing + alternating PPR](../experiments/FSE-DWI_10-04-2026_v17_increasing-alternating/FSE_dwi_CPMG_non_CPMG_twoTE-1.7-increasing-alternating.ppr):
  the same protocol with alternating crusher polarity.

PPR `:PPL` paths are local filenames; set them to the installed v1.7 scanner
source path when importing into Powerscan. RF parameters and receiver phases
are copied from v1.6. No 80% RF scanner setting is introduced.

| Parameter | Meaning / bounds |
|---|---|
| `crusher_schedule` | 0 original, 1 increasing, 2 alternating, 3 increasing + alternating, 4 decreasing, 5 custom; default 0 |
| `crusher_step_pct` | Additive percentage of ordinary baseline, 0..1000; default 0 |
| `crusher_custom_count` | Active custom entries; must equal ETL and be 1..64 in mode 5 |
| `crusher_custom_pct[64]` | Native signed integer percentages, array entry 0 corresponds to RF 1 |
| `crusher_max_dac` | Maximum crusher magnitude in calibrated logical DAC, 1..32767 |
| `crusher_slew_dac_100us` | Maximum ramp slope in calibrated logical DAC per 100 us, 1..32767 |

The last two defaults are 32767: the existing **software envelope** (full DAC
over the minimum 100-us ramp), not measured or rated scanner limits. Before
hardware use, enter ceilings derived from the target system's amplitude/slew
ratings and its gradient calibration. If full-scale logical strength is
`G_FS` T/m, one DAC is `G_FS/32767` T/m; a slew ceiling `L` corresponds to
`(L/32767)*G_FS/0.0001` T/m/s. Use the most restrictive physical axis after
orientation/gain calibration. The repository does not supply those ratings.
Native matrix creation also checks each scheduled value at each configured
orientation before acquisition; its return status is not a slew qualification.

For one-based pulse k, first DWI baseline is `diff_crush_amp`, including nominal
b=0; later baselines are `crush_amp`. Constant mode preserves v1.6 behavior in
diffusion-OFF scans too: its first baseline is then `crush_amp`. Increasing
factor is 100% for RF 1/2 and `100+(k-2)*step_pct` thereafter. Decreasing
preserves RF 1 and uses `100+(ETL-k)*step_pct` for k>=2. Alternation multiplies
even pulse numbers by -1. Signed bases keep their sign before alternation.
ETL 1 has just its first baseline; ETL 2 has no progression. Built-ins support
ETL 1..1024 subject to the existing view/PE/timing checks and DAC ceilings.
The offline generator now supports ETL 1 with PE order 5.

Magnitude is rounded half up using `(abs(base)*abs(percent)+50)/100`, then sign
is applied. The progression, product and rounding addition are bounded before
32-bit arithmetic; -32768 inputs and values beyond signed DAC or configured
amplitude/slew ceilings abort. Values are never clamped. With step 40, the
increasing DWI DACs are exactly
`2754,5482,7675,9868,12060,14253,16446,18639`.

For the tested irregular design, set mode 5, count 8, and the first eight
custom percentages to `100,100,171,83,137,213,109,191`; fill the remaining 56
native storage entries with zero. Negative percentages are supported. Custom
count must exactly match ETL; custom ETL >64 is rejected. Unused storage is not
played. This is an explicit bounded table, with no repetition or implicit
eight-entry truncation. The manual documents VAR_ARRAY, zero-based integer
arrays and common-array restrictions (§2.2.1.3, §4.8.5–4.8.7).

## Played lists, matrix lifetime and timing

Independent refocusing lists already contain SEC crusher, primary slice RF
gradient, SEC crusher. Both SEC lobes use the same matrix, duration, shape and
signed amplitude. Diffusion matrix 60, read/PE lists and primary slice gradients
are not rescaled by the schedule.

Variable mode reuses primary/secondary pairs 21/277 and 22/278. Under zero
matrix 1, every shot prepares identical primary slice matrices and secondaries
for RF 1/2, then selects 21 for RF 1. During RF k and both its crushers, its
matrix remains untouched. By ADC k, the crusher list has ended and imaging
matrix 3 is selected. After the existing ADC phase calculations, the macro
toggles 21/22, waits 100 us for the previous acquisition DSP calculation,
prepares the inactive secondary for RF k+1, then waits another 100 us. Selection
at the next `echo_loop` occurs only after this completion. The final RF does
not read entry ETL. Setup and the zeroed echo counter run for every shot,
slice, navigator, direction/row, experiment, and dummy. Schedule/base values
are snapshotted for the run; changing them requires restarting acquisition.

Before acquisition, the exact update macro is benchmarked under the zero
matrix across scheduled entries/orientations, with a 9000-tick ceiling. Its
extra ADC budget is 10000 ticks (1000 us), leaving 100 us for dispatch/check
overhead. The padded ADC calculation window grows from 8997 to 18997 ticks;
the remaining delay decreases by exactly 1 ms. **Sample duration and centres,
TE, ESP and TR do not grow.** Unsupported sampling-window splits abort in
setup. Following the measured 22413-tick setup, matrix setup uses a
30000-tick window, reads `gettimer()` once into an `int`, and aborts on a
negative reading or above 24500 ticks.
This leaves 550 us for timer/check overhead, including the manual's documented
360.2 +/- 5.0 us timing-function overhead and the assignment/comparisons.
The crusher-update benchmark also rejects negative readings. These signed
checks do not detect an entire timer wrap; compiler/runtime timing still needs
verification. DWI creates the same matrix count
as v1.6; scheduled diffusion-OFF needs two more setup calculations and must
fit that window. The extra 1150 us versus the original 18500-tick window is
included in minimum TR and taken from TR idle time; RF/ADC intervals remain
unchanged. The offline v1.7 absolute pre-excitation start is updated too.
The global preflight benchmark precedes acquisition and
is outside the requested TR. DSP settling follows the supplied include's
`caldelay=100`; instruction/settling budgets still need vendor validation.

A local `refocus_mat` variable in v1.6 collides with the include's
`#define refocus_mat 5`; v1.7 uses `crusher_play_mat`. No matrix IDs change.
Schedules require independent crushers, DE OFF and no skipped echoes.
Storage adds 1088 integer words (1024 DAC +64 custom) outside PE scratch RAM;
array bounds are checked, while target executable/RAM capacity requires the
vendor linker. No new gradient lists or matrix slots are allocated.

## Fixed centering and scratch bugs

Independent pads now both equal `2*tramp+crush_rf_pad/2`. For the tested PPR,
old pre/post pads 404/524 us become 464/464 us; their sum remains 928 us and
RF gradient flat remains 1460 us. RF-start wait at the original hook 3543
gains 60 us, post-RF wait at hook 3596 loses 60 us, and their net block duration
is unchanged. The balance equations offset list starts by -60 us, leaving RF
and ADC centres fixed and shifting refocusing/diffusion gradient lists earlier.
Excitation/imaging gradients and RF/receiver phases are unchanged. At the
assumed physical gradient lag of 60 us, the RF is centered on the physical
slice plateau; commanded timing alone uses lag 0. The lag and empirical
instruction constants have not been measured here.

Model setup recomputes minimum TE 33652→33532 us and minimum ESP
13822→13702 us. Both protocol ESPs remain 16 ms; after the setup-window revision,
minimum per-slice TR is 168521 us (previously 167371 us). The v1.6 baseline
event hash test still passes. Disabling the centering
correction **only in the simulator** reproduces v1.6 gradient events exactly;
the actual v1.7 PPL always includes the correction. The later setup-window
revision separately shifts absolute v1.7 shot starts by 1150 us.

The 4 October timer/diffusion corrections and review limitations are documented
in [scanner_v17_timing_review.md](scanner_v17_timing_review.md).

PE0 reserves centre addresses 0..511, location 512..1023, GP 1024..2047 and
GP2 2048..3071. Centre indices are 1..2*ETL; location indices 1..2*views_per_echo;
GP indices 0..no_views-1. Strict `<512` scratch bounds protect every write/read,
and the doubled GP product is bounded by 1024. Thus ETL<=255 and
views_per_echo<=255 pass the memory guard, subject to PE divisibility.
ETL 256 touches address 512, an unused location word: this is conservative
rejection, not demonstrated output corruption. The ETL-512/no_views-1024
replay produces three corrupt PE outputs and is now rejected. The supplied
v1.6 already has the terminating short-train `goto end`; it is retained.
Diffusion-ON PE0 remains forbidden.

## Full waveform and b tensor

`dwfse.btensor` reads **all** Pulseq blocks, including dummies, subsequent
shots, ramps, slice/rephase/PE/read gradients, crushers and diffusion lobes.
It exports interval endpoint gradients (`waveform.csv`) and RF centres/sign
events plus per-echo 3x3 tensors (`btensor.json`). Waveforms/tensors use the
generator's logical read/phase/slice coordinates. Physical oblique axes require
the verified scanner orientation/calibration transform; measured amplifier
waveforms are not available here.

In Hz/m gradient units, `q=2*pi*integral(sign*G dt)` and
`B=integral(q q^T dt)*1e-6` s/mm². Each linear-gradient interval is integrated
analytically, including quadratic q on ramps and off-diagonal cross terms.
Refocusing flips the effective sign at its RF centre; excitation resets the
primary pathway's q/B. Both geometric ADC centre and the actual upper-middle
sample are reported (25 us apart in this PPR). Labels retain slice/echo/shot
context where present. The tensor describes the primary pathway with
instantaneous RF at centres; imperfect RF gives many different pathway
weightings, not one tensor for their combined signal.

The source diffusion calibration formula, its units/conventions, 6.3² factor
and b=0 DAC-1 workaround are preserved. Requested diffusion b, scanner nominal
module b and achieved modeled primary total b are separate fields. Scalar
diffusion-amplitude adjustment cannot generally recover this tensor.

## Reproduction and compact results

```powershell
python -m unittest discover -s tests -v
python examples/validate_scanner_v17.py
python dw.py gen runs/v17.seq --ppr experiments/FSE-DWI_10-04-2026_v17_increasing/FSE_dwi_CPMG_non_CPMG_twoTE-1.7-increasing.ppr
python -m dwfse.btensor runs/v17.seq --out runs/v17_tensor
# Use --full with dw.py gen to export every slice/shot/row/dummy.
# Commanded timing: append --set hw_grad_delay_us=0 to dw.py gen.
```

Core dependencies are in requirements.txt; the signal comparison also needs
MRzeroCore and torch. [CSV](data/scanner_v17_validation.csv) records every echo's
complex primary/other/total PDG signal, static finite-RF Bloch total, unwanted
L1 share, relative phase and closure. [JSON](data/scanner_v17_validation.json)
contains settings, hashes, versions, tensors and compact grid summaries.
Raw readback sequences, exact parameters, signals and waveform exports are in
`runs/scanner_v17`. Existing investigation tables are preserved.

39 tests pass after the 4 October review: timer critical-window checks,
diffusion overflow/b=0 regressions, setup allowance and signed timer checks,
baseline event identity, native signed schedules/rounding,
invalid/overflow/ceiling rejection, ETL 1/2/1024, table capacity, matched pairs,
matrix lifetime/reset source checks, full protocol/navigators/dummies,
RF/ADC timing, fine-raster readback, PE0 alias replay, analytic ramp/cross-term
integration, refocusing sign, tensor reset and symmetry/positive semidefiniteness.
No pathway-reporting or fine-raster fixes were duplicated: both were already
present and their tests remain passing.

The comparison has 48 finite-RF static conditions and 48 additional water/PDG
conditions: four variants, B1 .8/1.0, excitation phase 0/45/90°, B0 0/100 Hz,
requested b=1000 along read, ETL 8, 10000 static Bloch spins, seed 1,
10-us RF step, PDG D=0/.001 mm²/s, T1=1.5 s, T2=80 ms, T2'=30 ms.
All 768 echo records close to independent MRzero acquired signal; maximum
relative discrepancy is 0.000140 (0.014%). All sequence/readback timing checks pass.

| Variant | Median/minimum static Bloch E8 | Static PDG unwanted share at B1=.8, phase0, B0=0 | Primary total b at E8 (s/mm²) |
|---|---|---|---|
| Original v1.6 | .04834 / .00190 | 91.6% | 1149.64 |
| Centered constant | .04841 / .00155 | 92.0% | 1149.52 |
| Centered increasing | .04930 / .03412 | 53.0% | 1236.77 |
| Centered increasing + alternating | .03845 / .03455 | 25.8% | 1247.18 |

These are equal-weight grid statistics, not expected scanner SNR. At that
imperfect RF/phase0 condition, static primary magnitude is .06675 for all four;
the coherent other contribution falls from .05374 to .03571/.00196 for the
increasing/alternating-increasing candidates. With water diffusivity, primary
E8 falls from .02115 to .01939/.01919 (8.3%/9.3% losses). Finite-RF Bloch
does not simulate Brownian motion; the water values are instantaneous-RF PDG.
Its longitudinal-diffusion convention lacks the transverse (2*pi)² factor,
so unwanted water fractions are model diagnostics, not physiological predictions.
Coherent excitation phase offsets are not a motion model. The stronger broader
investigation still supports increasing + centering as the initial balanced
candidate. Neither alternating mode is universally superior; reconstruction,
more RF conditions, diffusion directions and phantom tests remain necessary.

All specifically requested evidence files were available and inspected.
The 4 October 2026 timing-guard revision retains v1.7 and changes no generated
waveforms or requested timing. Archived signal results above precede this guard
revision; they do not validate its execution time on the scanner.
No vendor compiler was found in the executable path or expected scanner
installation directories. Vendor RF/gradient waveform libraries and
`tstex_15.pph` are absent. **Scanner compilation, target RAM/linking, exact
instruction timing, physical gradient delay/rated limits and phantom/image
qualification remain unverified.** Source/model validation is not scanner
qualification. Compile on the target EVO installation, inspect the generated
instruction timings and preflight budget report, then measure RF/gradient/ADC
centres and compare stationary/water phantom complex echoes and reconstructed
images before using either experimental PPR.
