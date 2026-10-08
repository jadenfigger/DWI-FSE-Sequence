# v19 research RF library: installation and calibration

**Status: not installed, not vendor-loaded, not console-calibrated.** Nothing in this repository has been copied to a scanner.

## Assets

Six single-frame WavEd libraries in `scanner/rf/`, one per pulse, built by `python examples/build_v19_rf_library.py` from `docs/v19/reference_rf/real_rf_contract.npz`:

| File | SHA-256 |
|---|---|
| `scanner/rf/v19_imaging180.seq` | `b79da53484e0df66e7296db0896f0f73506a9b680b48779d3c1c4cc4db8f5cc9` |
| `scanner/rf/v19_reexc90.seq` | `3c5c0b893c7568c72dbba2aa457ba73b7df2bd59e0e610c12437d13644688e29` |
| `scanner/rf/v19_slrelim90.seq` | `14065908df72390a8032c1a0ebc50c60cd0281d18d9d82b03c9d50365b77c1f0` |
| `scanner/rf/v19_slrprep180.seq` | `12893aa1c5b41b8e6b413d2c66309e1ec04be5ab0c183c68bbe77655863de432` |
| `scanner/rf/v19_slrprep90.seq` | `ba1c47b36159676f3b1ede6be0166222a3115e29e8dd160d3f91d60d429d610e` |
| `scanner/rf/v19_slrtip90.seq` | `12011e69db23614590d9f1d8b7222d28667c49e54c2a387a7f30b130a584f6df` |

Each file is stored the way WavEd stores the vendor `opt90_as.seq`: Amplitude expression `N,user("v19….txt");`, Frequency `NF,0;`, and the N-sample text embedded in the file. Rebuilding `opt90_as.seq` with the same encoder reproduces the vendor file byte for byte. The real-RF sample records are those of the earlier combined `v19_research_rf.seq` (kept as `compiler_compatibility/superseded_v19_research_rf.seq`), whose frames had empty expressions and displayed blank in the viewer. This is format evidence only: viewer display, compiler load and RF output still need console confirmation.

| Frame | NEWSHAPE index | Samples × dwell | Flip | Reference width | `rfcal` numerator / 10000 | Multiplier at rfcal 594 | Nominal peak B1 |
|---|---:|---|---:|---|---:|---:|---:|
| v19_slrprep90 | 18 | 320 × 10 µs | 90° | 18 mm (ref) | 3436 | 204 | 6.71 µT |
| v19_slrprep180 | 19 | 320 × 10 µs | 180° | 18 mm (ref) | 11509 | 683 | 22.48 µT |
| v19_slrtip90 | 20 | 320 × 10 µs | 90° | 10 mm (ref) | 3761 | 223 | 7.35 µT |
| v19_slrelim90 | 21 | 320 × 10 µs | 90° | 6 mm (ref) | 3761 | 223 | 7.35 µT |
| v19_reexc90 | 22 | 120 × 10 µs | 90° | 6 mm (ref) | 5392 | 320 | 10.53 µT |
| v19_imaging180 | 23 | 120 × 10 µs | 180° (scaled per echo) | 6 mm (ref) | 10783 | 640 | 21.06 µT |

The method PPLs compute each selector gradient from the protocol slice (`gs_var`, which corresponds to 1070 Hz) and the pulse's exact bandwidth (TBW/duration). They do not use the `NEWSHAPE_MAC` bandwidth integers or v18's 71% `bw_override`.

Geometry by method:
- v191 prepares a slab of `v19_slab_pml` per mille of the slice (3000 = 18/6) and tips up over `v19_tip_pml` (1667 = 10/6).
- v192 prepares and eliminates at the imaging slice width.

## Installation (manual, by the user)

1. Copy the six `scanner/rf/v19_*.seq` files to `g:\J_Figger\seqlib\` as **new files** with the same names. Do not overwrite or rename any vendor library. The old `v19_research_rf.seq` is no longer used.
2. Open each of the six files in the WavEd viewer before compiling. Each should show one frame with a visible amplitude shape: the SLR pulses (`v19_slr*`, 320 samples) peak at 2047 with small side lobes; `v19_reexc90` / `v19_imaging180` (120 samples) are single smooth positive lobes (low time-bandwidth windowed sinc). Compare with `compiler_compatibility/v19_rf_expected_waveforms.png`. A blank display means the file must not be used.
3. Both new PPLs contain six `#use RF1 "g:\J_Figger\seqlib\v19_….seq"` lines (aliases `pf18`–`pf23`) and need all six files to compile, even when `v19_on=0`.
4. Compile v191 and v192 with `v19_on=0` and the original test1e protocol, then confirm the produced timing/events equal v18's. The repository mapper shows identical event ledgers; a vendor compile and trace are still required.

## Calibration (required before any method acquisition)

The multipliers come from `scale(rfcal, numerator, 10000)`. This is an **inferred** linear model: DAC × board multiplier, with `rfcal` giving 90° for the stock `3lobe_sinc_3kHz` frame (1332 µs). Under that model the inherited `p180_scale=185` corresponds to about 166.5°.

The method paths ignore `alpha` and `p180_scale`. Each new frame needs its own console flip-angle check:

1. Measure the nominal 90° of `v19_slrprep90` and of `v19_reexc90` with a standard flip-angle calibration. Each measurement gives a frame-specific correction factor relative to the inferred numerator.
2. Measure `v19_slrprep180` and `v19_imaging180` for refocusing efficiency. Measure the low-angle train linearity too, since `v19_mul[k]` scales linearly with the requested flip.
3. Update the numerators in `examples/build_v19_ppl.py` (`RF` table) and regenerate. Do not hand-edit the generated PPLs.
4. RF power/SAR: the prep180 and imaging trains are about 3× and 1.1× the stock pulse peak B1. Check amplifier and coil limits; they are not supplied here.

## Known RF limitations (measured, see `docs/v19/reference_rf.md`)

- **Tip-up:** a water-only spatial SLR pulse, not Gibbons' spectral-spatial pulse. Fat storage is 0.75–0.996 against the published 0.04–0.06 target.
- **Area-renormalised SLR prep180:** maximum basis error 0.339.
- **Hamming re-excitation and imaging pulses:** maximum basis error over the 6 mm interval is 0.535 for re-excitation and 1.149 for imaging. Both have broad transition bands.
- **Guard samples:** the frames have none. The method gates RF off 5 µs after the nominal frame end. The `MR3031_go` latency is unmeasured.
