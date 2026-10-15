# v1.83: selectable off-centre RF phase for multi-slice v1.82

**Status:** source-model candidate. It has not been vendor-compiled or run on the scanner. Install `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.83.ppl` at `G:\J_Figger\` and compile it before use.

## Why

On 2026-10-11, every off-centre v1.82 slice showed an echo-phase ramp of about 41° per echo per mm of slice offset: ±49° at ±1.2 mm and ±98° at ±2.4 mm ([report §3](../physical_scanner_experiments_2026-10-11.md)). That breaks the CPMG condition. It is what causes the doubled edges, the stripes and the roughly 20% ADC bias in the outer slices.

The centre slice is unaffected. v1.81 on 2026-10-10 showed no ramp at ±1.2 mm.

The two versions handle off-centre RF phase differently:

| | Transmit carrier | Phase correction |
|---|---|---|
| **v1.81 (and the vendor's original FSE, v1.0)** | Stays at the slice frequency | Every refocusing pulse and the receiver get a per-echo increment, `phase_ang`. It includes the console-calibrated `phcor_plus`/`phcor_minus` (23). |
| **v1.82** | Switched on only around each RF pulse | Explicit bookkeeping that assumes the offset is active for exactly RF length + 180 µs |

The ramp equals the phase of about 53 µs per pulse at the 2130 Hz/mm slice frequency, which v1.82's bookkeeping does not account for.

## What changed

Only the off-centre RF phase handling changed, through two new console parameters:

| Parameter | Values | Effect |
|---|---|---|
| `v183_phmode` | **0 (default)**: vendor / v1.81 scheme | The transmit buffer keeps the slice carrier, and the per-echo `phase_ang` increment includes the slice term again. v1.82's gated branches are skipped, so off-centre slices use v1.82's own centred-slice timing. |
| | 1: v1.82 gated scheme | v1.82's code, with `v183_phcal` added to the modelled window |
| `v183_phcal` | −2000 … 2000 ticks of 0.1 µs (mode 1 only) | `v182_step = f × (tsel90×10 + 1800 + v183_phcal) mod 10⁷`. Each off-centre refocusing pulse's phase changes by 360·f·phcal·10⁻⁷ degrees, accumulating pulse by pulse: 48.7° per pulse at 1.2 mm for phcal 530. |

Nothing changes at zero slice offset, and nothing else changes in the sequence. The overflow guard of the gated path now assumes the longest window allowed (+2000 ticks).

## Compiler fix (2026-10-12)

The first v1.83 build failed on the console with "error branch is out of range". v1.81 routes every error through an early `end:` label whose `goto v181_exit` jumps forward over the whole program. v1.82 was just inside the compiler's branch range, and v1.83's few extra statements pushed it over. v1.83 now relays that jump through a label in once-only setup code before the gating and experiment loops. The longest forward jump drops from 16,826 to 8,584 tokens; the longest backward jump is 16,446, below v1.82's compiled 16,801. Normal flow skips the relay with one untimed goto. One v1.82 error message was shortened to pay for it ("V182 raw views").

## Validation (event model; `python examples/validate_v183.py`)

* **Static image:** 56,652 of 56,664 modelled bytes (12 spare). All static checks pass.
* **Mode 1, phcal 0, matches v1.82** under all eight instruction-cost models at 0, ±1.2, 2.4 and −5 mm: RF, ADC, gradient and phase events are identical. Only untimed slice-setup frequency commands before each excitation move, by ≤ 6 µs.
* **Every mode is identical at zero offset.**
* **Mode 0** issues a constant per-echo `phase_ang` increment on the RF and receiver commands, from its own carrier, which is the vendor scheme. Its off-centre RF and ADC timing equals the centred slice. Its carrier is within 0.08% of v1.81's, because v1.82's DAC-exact slice frequency is kept.
* **A nonzero phcal** shifts only the gated off-centre RF phase commands, by exactly k·P·f·10⁻⁷ turns at pulse k. Timing and gradients are unchanged.
* **Reconstruction:** `scanner/recon/effective_b.py` accepts 1.83, and the effective b-values equal v1.82's.

The repository's synthesizer model cannot decide which mode is physically right. That model predicted v1.82 to within 0.2°, and the scanner disagreed. The choice of mode and the value of `v183_phcal` are scanner measurements; see [CALIBRATION.md](CALIBRATION.md) and `tools/offcentre_phase_cal.py`.

## Files

* `examples/build_v183_ppl.py`: builds v1.83 from hash-checked v1.82 bytes.
* `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.83.ppl` and `.ppr`: the generated sequence and protocol (the PPR adds `v183_phmode 0` and `v183_phcal 0`).
* `examples/validate_v183.py` → `docs/v183/validation/v183_events.json`: the event-model validation.
* `tools/offcentre_phase_cal.py`: the navigator ramp/alternation fit and phcal solver.
* `docs/v183/CALIBRATION.md`: the scanner procedure.

The 3D and driven-equilibrium compile-outs and the nav-mode-2 contract of v1.82 are unchanged. Mode 2 still needs the PPL host-interface fix before it can run on the console.
