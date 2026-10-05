# DW-FSE sequence: PPL → Pulseq → simulation

This repo turns the MR Solutions PPL sequence `FSE_dwi_CPMG_non_CPMG_twoTE-1.6` (diffusion-weighted fast spin echo) into a Pulseq `.seq` file that reproduces the scanner's timing, gradients and RF phases. It then Bloch-simulates that file, to study stimulated/spurious echoes and B1/B0 sensitivity. Everything is Python; no Julia is needed.

**Findings so far:** [REPORT.md](REPORT.md). **How the PPL maps to Pulseq (branch table, timeline, assumptions):** [docs/ppl_to_pulseq.md](docs/ppl_to_pulseq.md).

**ETL-8 improvement investigation:** [docs/ppl_improvement_report.md](docs/ppl_improvement_report.md)
compares original behavior, crusher and RF-phase changes, diffusion-phase errors,
and B1/B0 robustness. The original scanner files and generator defaults remain available.

**Combined-factor follow-up (4 October 2026):** [report and reproducible results](docs/combined_factor_investigation.md).
Tests 41 configurations with held-out validation, independent pathway/tensor audits,
and a spatial phantom whose sampling failure prevents image-quality ranking.

**Scanner v1.7:** [implementation, experimental PPRs, validation and reproduction](docs/scanner_v17.md).
Adds bounded signed crusher schedules, fixes independent-crusher centering and
guards PE0 scratch memory. Select a `twoTE-1.7*.ppr` explicitly; defaults still
use v1.6. `python -m dwfse.btensor file.seq --out runs/tensor` exports the complete
modeled played waveform and per-echo b tensor. Vendor compilation and phantom
qualification remain required.

## Setup

```bash
pip install -r requirements.txt          # pypulseq, numpy, scipy, matplotlib
pip install MRzeroCore torch             # optional, only for `dw.py epg`
```

## The pipeline

```
scanner/*.ppr  ──(--set / --params)──►  gen  ──►  seq.seq  ──►  view  ──►  sim  ──►  plot
   or any .seq file (--seq) ───────────────────────┘                                  │
                                                         compare runs/A runs/B  ◄─────┘
```

`python dw.py run NAME` does gen → view → sim → plot in one go and puts everything in `runs/NAME/`. A typical iteration:

```bash
python dw.py run base                                  # the PPR as it is
python dw.py run te50 --set te=50 --set esp=50         # change PPR parameters
python dw.py run fix  --set sim_fix_refocus_centering=true
python dw.py compare runs/base runs/te50 runs/fix      # overlay echoes and signal -> runs/compare_*.png
python dw.py run b1   --b1 0.7 0.8 0.9 1.0 1.1         # B1 sweep (also --b0 0 25 50)
python dw.py run ex3  --seq examples/ex3_cpmg_train.seq   # any existing .seq
python dw.py run full --full                           # whole protocol (all slices, shots, dummies, b-values)
```

A run takes seconds for the default reduced sequence. `--full` builds and simulates the whole protocol, which is slower (about 15 s for the current PPR). To only write the `.seq`: `python dw.py gen my.seq --full`.

The generator is specific to this PPL: it re-implements `FSE_dwi_CPMG_non_CPMG_twoTE-1.6.ppl` in Python and takes all its parameters from a `.ppr` (`--ppr` for another PPR of the same PPL). A different PPL needs its own generator.

### What is in `runs/NAME/`

| file | what to look at |
|---|---|
| `seq.seq`, `seq.params.json` | the sequence and every parameter used to build it |
| `seq.gen.txt` | the PPL's own report: min TE/ESP/TR, gradient DACs, b-value per row, slice-profile widths |
| `diagram.png` | sequence diagram; **every block numbered** (Pulseq block index) |
| `view.txt` | block table, RF table, TE/ESP, gradient moments per refocusing interval (CPMG check), b-value per echo, k-space per echo |
| `kspace.png` | k-space trajectory and phase-encode order |
| `signal.png`, `echoes.png` | simulated signal in every ADC window; echo amplitudes vs echo number/time (one line per B1/B0) |
| `b1_sweep.png` | echo amplitude vs B1 (when several `--b1` are given) |
| `snapshots.png` | magnetization vs z at every echo centre: \|Mxy\|, phase, Mz |
| `results.npz`, `summary.txt` | raw results and the echo table |

### Single steps

```bash
python dw.py gen out.seq [--set k=v] [--params f.json] [--ppr f.ppr] [--full] [--report]
python dw.py view my.seq [--blocks 19 35 | --t0 0 --t1 60] [--mark 7 13] [--show]
python dw.py sim  my.seq [--b1 ...] [--b0 ...] [--T1 1.5 --T2 0.08 --T2p 0.03] [--n 20000] [--snaps adc]
python dw.py plot runs/NAME [--snaps 1 3]          # re-plot, choose snapshot panels
python dw.py epg  my.seq --b1 0.8                  # which echo pathways make each echo (MRzeroCore)
python dw.py rf   [--out rf]                       # RF pulse models and their slice profiles
```

### Exact pathway metrics

For one excitation followed by at most eight acquired echoes, `dw.py epg` now
prints exact centre-sample RF-history contributions. Larger/full protocols fall
back to **explicitly heuristic** graph weights. `--legacy-pathways` requests that
older presentation. Use `--D 0` for comparison with the static-spin Bloch model;
the EPG `--D` unit remains 10^-3 mm²/s (default 2.0).

To save the exact decomposition with an independent MRzero signal-closure check:

```bash
python -m dwfse.pathways runs/base/seq.seq --b1 0.8 --out runs/base/pathways.json
python -m dwfse.pathways runs/base/seq.seq --b1 0.8 --diffusion-mm2-s 0.001 --out runs/base/pathways_diffusion.json
python dw.py run candidate --params docs/params/improvement_candidate.json --b1 0.7 0.8 1.0 1.2 --b0 0 100
```

The explicit `--diffusion-mm2-s` option uses physical units. Both decomposition
models treat RF as instantaneous; they do not measure finite-pulse slice profiles.
See the improvement report for reproduction commands, trade-offs, and scanner patches.

## Changing the sequence

The generator reads `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.6.ppr`. There are three ways to change it:

1. **Edit the PPR**, exactly as on the scanner. Variable names are the PPR's names.
2. **`--set name=value`** on the command line. Lists are comma-separated: `--set acq_b=0,1000,3000`.
3. **A JSON file** with `--params`; see [`params_example.json`](params_example.json).

The generator emulates PARSETUP, so changing FOV, slice thickness, views or bandwidth updates the gradient values the way the scanner's parameter editor would. It also runs the PPL's own checks and stops with the PPL's message, e.g. "esp too short: increase esp to at least 14 ms".

Most-used parameters:

| parameter | meaning |
|---|---|
| `te`, `esp`, `tr` | first (diffusion) echo time, train echo spacing, TR [ms] |
| `views_per_seg`, `no_views`, `nav_on`, `PE_order` | echo-train length, total views, navigator, phase-encode order (1, 6, 7) |
| `acq_b`, `acq_x/y/z`, `no_diff_acq`, `no_experiments` | diffusion table (b-values, directions); `no_experiments` must be a multiple of `no_diff_acq` |
| `sm_delta`, `big_delta` | δ and Δ [µs] |
| `tcrush`, `crush_amp`, `diff_tcrush`, `diff_crush_amp` | train-180 and first-180 crushers (µs, DAC) |
| `crush_independent_on` | 1 = v1.6 separate crusher lobes, 0 = legacy |
| `rfnum`, `sim_rf_model`, `sim_rf_apodization` | RF frame and its model (`truncated_sinc` / `bw_matched_sinc`) |
| `sim_refocus_flip_deg`, `sim_excitation_flip_deg` | flip angles (default 180 / `alpha`) |
| `hw_grad_delay_us` | physical gradient lag (default 60 µs = PPR `rfdelay`, PPL:4100); 0 = commanded timing |
| `sim_fix_refocus_centering` | false = PPL v1.6 as written (180 off-centre, see REPORT); true = intended |
| `sim_excitation_phase_deg` | excitation-only phase offset to emulate a coherent diffusion phase error; quantized to 0.225° |
| `sim_refocus_phase_offsets_deg` | explicit ETL-sized table relative to existing refocusing phases; receiver phases unchanged |
| `sim_train_crusher_scales` | ETL-sized table multiplying first/train crusher DACs, symmetrically around each RF; independent mode only |
| `sim_reduced_slices/rows/shots/n_dummy` | what the reduced cut keeps (centre slice, first b > 0 row, first imaging shot, 0 dummies) |
| `no_disacq`, `no_slices`, `no_averages` | dummies, slices, averages (used with `--full`) |

The full list, with PPL line references, is in [docs/ppl_to_pulseq.md](docs/ppl_to_pulseq.md).

**Editing a `.seq` directly** also works. Build or modify it with PyPulseq (see `examples/make_examples.py`), then `python dw.py run NAME --seq file.seq`. Block numbers in `diagram.png`/`view.txt` are the Pulseq block indices, which is what `--snaps blocks:7,11` and `view --blocks` refer to.

## Simulation model (`dwfse/simulate.py`)

The model is a voxel of 20,000 isochromats:

- spread over a 0.2 × 0.2 mm in-plane area and twice the slice thickness in z (so the slice-profile edges are included);
- with a Lorentzian off-resonance spread (T2′) plus an optional global B0;
- with T1/T2 relaxation;
- with real RF shapes, so slice profiles come out naturally.

RF blocks are time-stepped; everything else is applied exactly. The echo amplitude is |mean Mxy| at the k-space-centre sample. Snapshots (`--snaps`) can be taken at any time: `adc` = every echo centre (default), `rf` = end of every RF block, `blocks:3,7`, `times:18.5,54.9`. This simulator was checked against KomaMRI (same results within Monte-Carlo noise). Diffusion (spin motion) is not simulated; b-values are computed from the gradients in `view.txt`.

## Repository layout

```
dw.py                 command-line entry point
dwfse/                generate.py (PPR/PPL -> seq), rf_pulses.py, view.py, simulate.py, results.py, epg.py
scanner/              the PPL, the PPR, the .pph include files and the EVO manual
examples/             eight small hard-pulse sequences, FID -> CPMG/CP -> mini DW-FSE (see its README)
docs/                 technical reference and figures
REPORT.md             project report and findings
runs/                 outputs (not in git)
```
