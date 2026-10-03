# Prompt: explore and improve the DW-FSE PPL/PPR

You are an MRI pulse-sequence engineer working in this repository. You have the MR Solutions PPL source of a diffusion-weighted fast spin echo sequence and a Python pipeline that turns it into a Pulseq file and Bloch-simulates it. Your job has two parts:

1. Find what is wrong with or weak about the sequence (the PPL program and its PPR protocol).
2. Iteratively improve it.

The first goal is to **suppress spurious echoes (stimulated, FID and other unwanted coherence pathways) as much as possible while keeping SNR high.** The second goal is to find and document **any other errors or issues** in the PPL/PPR.

How you explore, which experiments you run, and in what order is up to you. Let the simulated data guide you.

## Read first

- `README.md`: the pipeline and its commands.
- `REPORT.md`: what has already been validated and found. Do not just repeat it; build on it, and confirm or correct it.
- `docs/ppl_to_pulseq.md`: how each PPL line maps to the Pulseq model, including the assumptions and the PPL issues already flagged.
- `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.6.ppl` and `.ppr`: the sequence and the current protocol.
- `examples/README.md`: small teaching sequences (CPMG vs CP, unequal first interval, diffusion phase error).

## Tools you have

- **`python dw.py run NAME [--set key=value ...] [--b1 ...] [--b0 ...] [--full]`**: generates the sequence from the PPR, views it, Bloch-simulates it and plots it into `runs/NAME/`.
  - Read `seq.gen.txt` (the PPL's own limits and checks), `view.txt` (timing, gradient moments per refocusing interval, b-value per echo, k-space), `summary.txt`, and the PNGs.
- **`python dw.py compare runs/A runs/B ...`**: overlays the results of several runs.
- **`python dw.py epg SEQ --b1 0.8`**: echo-pathway (EPG/PDG) breakdown. This is the most direct way to measure spurious echoes: it shows which coherence pathways contribute to each echo, and with what share and phase. It needs MRzeroCore; install it with `pip install MRzeroCore torch` if it is missing.
- **`python dw.py sim/view`** on any `.seq`. You may also write your own analysis scripts, or build small test sequences with PyPulseq (see `examples/make_examples.py`).
- **The generator `dwfse/generate.py`** re-implements the PPL line by line, citing PPL line numbers. To test a change to the PPL, change the generator in the same way, either behind a new `sim_*` switch or as a new parameter. Keep the original behaviour available, so every comparison is against the as-written sequence.

## How to judge a change

Define your metrics explicitly and use them consistently. Reasonable choices:

- **Spurious-echo level:** the fraction of each echo that does not come from the primary spin-echo pathway (from `epg`). Also look for signal appearing at unexpected times inside the ADC windows (from `sim`).
- **SNR proxy:** primary-echo amplitude, especially at the k-space-centre echo, and the echo-train decay.
- **Robustness:** how both of the above change over a range of B1 (for example 0.7–1.2) and B0 (for example 0–100 Hz). Scanner B1 is never perfect.

Test realistic conditions, not just the convenient ones:

- **b > 0:** for example `--set acq_b=0,1000` with `no_diff_acq` and `no_experiments` matching.
- **A longer echo train** (8 or more echoes).
- **The motion-induced phase error of diffusion imaging.** The simulator has static spins, so emulate this with an excitation phase offset, as `examples/ex6b` does, or add a phase-error option to the simulator.

## Rules

- **Simulate, do not assume.** Every claim in your report must be backed by a run you did (cite the `runs/` folder) or by a PPL line number.
- **Change one thing at a time,** and keep a baseline run to compare against. Record every experiment: what you changed, why, and what happened, including the failures.
- **Respect the scanner.** Keep the PPL's hardware limits and timing rules (minimum TE/ESP/TR, gradient and slew limits, the abort conditions the generator replays). Proposed changes must be implementable in PPL. Say how: which lines or variables change, and roughly what the new code does.
- **Keep the model honest.** If a result depends on a modelling assumption (the RF pulse shape, the 60 µs gradient delay, the refocusing flip calibration, the static-spin limitation), say so, and test the sensitivity where you can.
- If you change the pipeline itself (for example new simulator options), keep the existing commands working and note the change.

## Possible starting points (not a required plan)

- The first refocusing interval differs from the train (TE/2 ≠ ESP/2), and the first-180 crushers are smaller than the train crushers.
- The crusher sizes and polarity pattern across the train; whether alternating or varying crushers suppress pathways better.
- The 180° centring bug in the v1.6 independent-crusher code (`sim_fix_refocus_centering`).
- Refocusing flip angle and RF pulse shape / slice-profile mismatch between the 90° and 180° pulses.
- RF phase schemes for diffusion FSE, where the CPMG condition is broken by motion, for example:
  - quadratic or alternating phase cycling;
  - splitting the signal into two echo families;
  - phase-insensitive or "non-CPMG" schemes from the literature.
- Readout prephaser balance and the post-train crusher.
- Anything else you find in the PPL code: timing arithmetic, integer truncation, unused or wrong branches, PPR values that look inconsistent.

## Output: a plain-English report

Write `docs/ppl_improvement_report.md` for a reader who understands MRI but has not seen your runs. Keep it clear and short. Explain jargon the first time you use it, and prefer figures and small tables over long text. Include:

1. **Summary:** the most important findings and the recommended changes, in a few sentences.
2. **Problems found:** each issue in the PPL/PPR, how you know (run or line number), and how much it matters.
3. **What you tried:** each experiment and its result, including the ones that did not help.
4. **Recommended changes:** ranked by benefit. For each, give:
   - the expected effect on spurious echoes and on SNR, with numbers;
   - the trade-offs (TE, scan time, SAR, gradient load);
   - how to implement it in the PPL (lines and variables).
5. **Confidence and limits:** what depends on modelling assumptions, and what should be checked on the scanner or a phantom.

Commit the report, any new runs' key figures (copy them into `docs/figures/`; `runs/` is not committed) and any generator/simulator changes.
