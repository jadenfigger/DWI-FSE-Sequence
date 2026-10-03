# Simple example sequences

Eight small `.seq` files that build up, one idea at a time, to the DW-FSE echo train. They use hard 200 µs pulses (no slice selection), z-crushers, no imaging gradients, and long ADC windows, so you can watch echoes form. Each file is one shot with a 1 s TR.

From the repository root:

```bash
python dw.py run ex3 --seq examples/ex3_cpmg_train.seq --b1 0.8 1.0   # view + simulate + plots in runs/ex3/
python dw.py run ex4 --seq examples/ex4_cp_train.seq --b1 0.8 1.0
python dw.py compare runs/ex3 runs/ex4                                 # CPMG vs CP side by side
python dw.py epg examples/ex4_cp_train.seq --b1 0.8                    # which echo pathways make each echo
```

In this folder: `python make_examples.py` regenerates the files, and `python simulate_examples.py` simulates all of them at B1 1.0 and 0.8 into `examples_overview.png`.

The amplitudes below come from the project simulator (`dwfse/simulate.py`): T1 1.5 s, T2 80 ms, and T2′ = 3 ms so the echoes are sharp. Values are the peak of each ADC window at B1 = 1.0 / 0.8.

| file | what it is | what to look for | echoes, B1 1.0 → 0.8 |
|---|---|---|---|
| `ex1_fid` | 90x, then 40 ms ADC | FID decays with T2* (T2′ + T2) | — |
| `ex2_spin_echo` | 90x – 10 ms – 180y | echo at 20 ms recovers T2′ loss; height ≈ e^(−TE/T2) | 0.76 → 0.66 |
| `ex3_cpmg_train` | 90x, 4 × crushed 180y, ESP 10 ms | **CPMG**: under B1 error echo 2 ≈ echo 1, because stimulated echoes add in phase | 0.87 0.78 0.68 0.60 → 0.74 0.74 0.60 0.58 |
| `ex4_cp_train` | same, but 180x | **CP** (refocusing phase = excitation phase): under B1 error the train collapses | 0.87 0.74 0.64 0.55 → 0.74 0.44 0.13 0.13 |
| `ex5_unequal_first_interval` | 90 – 20 ms – 180 – 20 ms – echo 1 – 5 ms – 180 | first interval ≠ later one. The stimulated echo leaves echo 2 and appears **20 ms after the 2nd 180** (66 ms), visible at B1 0.8 | echo 2: 0.52 → 0.41; peak at 66 ms ≈ 0.10 at B1 0.8 |
| `ex5_..._b` | same, first crusher pair half size (like PPR 2754 vs 5482) | the stimulated echo at 66 ms is now spoiled, as in your DW-FSE | 66 ms peak gone |
| `ex6_dw_fse_mini` | Stejskal–Tanner lobes on x around 180₁ (TE1 40 ms), then 3 echoes at ESP 10 ms | the real structure: long DW first echo, short train. Static spins: still CPMG-like for echoes 2–4 | 0.59 0.52 0.46 0.41 → 0.51 0.41 0.40 0.33 |
| `ex6b_dw_fse_mini_phase90` | identical, excitation phase 90° | stands in for the random phase that motion adds during the lobes when b > 0. Now the train is CP-like and collapses under B1 error. This is why DW-FSE needs non-CPMG schemes | 0.60 0.52 0.45 0.39 → 0.51 0.41 0.24 0.07 |

Suggested order: ex2 → ex3 vs ex4 (why the refocusing phase matters) → ex5 vs ex5_b (why the first interval and crushers decide which pathways survive) → ex6 vs ex6b (why diffusion-induced phase breaks CPMG). Then go back to `dwfse_minimal.seq`. It is ex6 plus slice selection, imaging gradients, and the PPL timing.
