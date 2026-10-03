# Pulseq FSE DWI simulation tools

All tools read the same `.seq` file.

| File | What it is for |
|---|---|
| `view_seq.py` | Look at the sequence: diagram, RF flip/phase table, CPMG moment check, b-value per echo, k-space |
| `mrzero_epg.py` | Generalized EPG (phase distribution graph) simulation: which echo pathways make each echo, B1/B0 sweeps |
| `koma_sim.jl` | Full Bloch simulation in KomaMRI: real RF shapes and slice profile, magnetization snapshots over time |
| `plot_koma.py` | Plots the CSV results that `koma_sim.jl` writes |
| `scale_b1.py` | Makes a copy of the .seq with all RF scaled (B1 error), for KomaMRI |

Python setup: `pip install pypulseq MRzeroCore matplotlib numpy torch`

**Tip:** for simulation, use a reduced .seq (one slice, one b-value and direction, and the
k-space-center phase-encode line, or phase encoding set to zero). The echo-train
physics is the same and every run takes seconds.

---

## 1. View the sequence (PyPulseq)

```
python view_seq.py my_seq.seq            # window = first excitation to second excitation
python view_seq.py my_seq.seq --t0 0 --t1 0.08 --save
```

What to look at:

- **RF table:** check the flip angles, the RF phases (CPMG means the refocusing pulses are
  90 deg from the excitation) and the spacing (the first gap should be half the echo spacing).
- **Gradient moment table:** CPMG needs the same 0th moment in every refocusing
  interval, with the excitation-to-first-refocusing interval at half that. Any interval that
  breaks this is where spurious echoes will come from.
- **b-value table:** b for the main spin-echo pathway at each echo, including the
  imaging and crusher cross terms.

## 2. KomaMRI.jl (Bloch simulation)

**Install (once)**

1. Install Julia with juliaup (https://julialang.org/install).
2. Give KomaMRI its own environment, so no other package versions clash with it. In a
   **fresh** Julia session:
   ```
   julia> cd(raw"C:\path\to\your\pypulseq\folder")
   julia> ]                      # package mode
   pkg> activate .
   pkg> add KomaMRI
   pkg> precompile
   ```
   Press backspace to leave package mode. You do not need to add PlotlyJS separately.
3. Next time, start Julia in that folder with `julia --project=.` (or run `] activate .` first).

**Option A: GUI (quickest look)**

1. In Julia, run `using KomaMRI; KomaUI()`.
2. **Sequence → Load** your `.seq`. Look at the sequence diagram, k-space and the moments views.
3. **Phantom:** start with the built-in brain, or load your own.
4. **Simulate!** View the raw signal, then the reconstructed image.

**Option B: script (for the echo questions)**

1. Edit the settings at the top of `koma_sim.jl`: voxel size, slice thickness, T1/T2/T2',
   and B0 offset.
2. In the Julia REPL, use the full path to the .seq:
   `SEQ_FILE = raw"C:\path\to\my_seq.seq"; include(raw"C:\path\to\koma_sim.jl")`
3. The script writes CSV files next to the .seq. Plot them with
   `python plot_koma.py C:/path/to/my_seq`. You get:
   - the raw signal,
   - echo amplitude vs echo number,
   - |Mxy|, phase and Mz of every spin vs z after each RF pulse. Here you can watch the
     crushers wind a phase helix across the slice and see which part of it each pulse
     refocuses or stores.

   The sequence diagram and k-space are also saved as .html when KomaMRI's plotting loads.
4. **B1 error:** run `python scale_b1.py my_seq.seq 0.8` (repeat for 0.6, 0.7, 0.9 and so on),
   then run the script on each scaled file.
5. **B0:** change `B0_Hz` (global offset) and `T2prime` (spread within the voxel).

**Caveats**

- If precompiling fails on a very new Julia (for example 1.13), install the
  release KomaMRI supports and use that: `juliaup add 1.11`, then `julia +1.11 --project=.`
- If `read_seq` rejects the file version, write the .seq with an older PyPulseq (Pulseq 1.4
  format, `pip install "pypulseq<1.5"`) and try again.
- As far as I know, KomaMRI's Bloch simulation does not use the phantom diffusion fields
  (diffusion there is done through spin motion). Use MRzero for diffusion attenuation, and
  use KomaMRI for RF shape, slice profile and B0/B1 effects.

## 3. MRzero (generalized EPG)

```
python mrzero_epg.py my_seq.seq --voxel-mm 0.2 0.2 1.0
python mrzero_epg.py my_seq.seq --b1 0.8 --b0 30 --T2 0.06 --D 2.0 --save
python mrzero_epg.py my_seq.seq --max-reps 20      # first 20 RF intervals only
```

Set `--voxel-mm` to your real in-plane resolution and slice thickness. The voxel size is what
makes crushed states lose their signal, as they would in the scanner.

Outputs:

- **Pathway decomposition (printed):** for every echo, the coherence pathways that make up
  the k-space-center sample, in Hennig's notation (one label per RF interval: `+`/`-` for
  transverse, `Z` for stored). It also gives each pathway's share and its phase relative to
  the strongest one. Pathways near 180 deg cancel signal. `net/sum` below 1 tells you how
  much cancellation there is.
  - Example, CPMG at 80 % B1, echo 2: `+ - +` (spin echo) 81.5 %, `+ Z -` (stimulated echo) 18.5 %.
- **PDG plot:** every transverse state per RF interval, positioned by k_x, k_y, k_z and tau,
  colored by how much signal it can still produce.
- **Signal vs time:** ADC samples, ideal vs imperfect B1/B0.
- **Sweeps:** echo amplitude vs echo number for:
  - several B1 scales,
  - several B0 offsets,
  - an extra phase added to the excitation pulse (`--phase-sweep`). This mimics the random
    phase that motion during the diffusion gradients adds in vivo. +0 and +180 deg keep the
    CPMG condition. At +90 deg the magnetization is perpendicular to the refocusing axis, and
    the echoes collapse and oscillate once B1 is off. That is the core DW-FSE problem.
- **B0:** pulses are instantaneous here, so with strong crushers a uniform B0 offset barely
  changes the echoes. B0 matters when an echo sits off the ADC center (a timing or moment
  error) or through off-resonant pulse behavior. Use KomaMRI for the second case.

**Limits:** RF pulses are instantaneous rotations (no slice profile), and the phantom is one voxel.
Use KomaMRI to check slice-profile effects.
