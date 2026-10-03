# DW-FSE improvement experiment log

## Design fixed before screening (2026-10-03)

Baseline: original PPR saved separately as `runs/improve_ppr_original`; mechanistic
baseline uses TE 36 ms, ESP 16 ms, ETL 8, 16 imaging lines, b table [0,1000],
two experiments/two diffusion rows, read-axis diffusion, and the shot containing
ky=0 at echo 1. No dummy trains in single-shot comparisons. The original scanner
files and simulation defaults remain available.

Metrics: at each ADC centre sample, identify the *primary* path by uninterrupted
transverse coherence and conjugation at every refocusing pulse (never by largest
amplitude). Report its amplitude P, total complex-sum magnitude S, and unwanted
fraction U=sum(|other paths|)/sum(|all paths|). Also retain complex interference,
ADC peak and displacement from the window centre. U is a pathway-amplitude share,
not a power fraction; reducing U alone is insufficient if P or S collapses.
Centre-of-k-space signal is echo 1 for PE order 1 and the selected shot.

Model qualification: MRzero instantaneous RF cannot reproduce the slice profile.
The existing `epg.pathway_report` uses prepass weights and emitted-signal estimates;
its percentages require independent sample-level verification before optimization.
Use D=0 for like-for-like static-spin comparison; diffusion attenuation must be
reported separately from static-spin diffusion-gradient/phase effects.

Screen one change at a time at B1=.8, B0=0, phase errors 0/90 degrees, b=1000:
centering; equal first crusher; uniform larger crushers; alternating polarity;
varying symmetric per-RF moments; equal TE/ESP; RF flip and shape; explicit phase
tables; post-crusher off; read prephaser. Phase offset applies to excitation only.
Use 4096 spins for screening, retain candidates only after denser Bloch and pathway
checks. Fixed seed and stratified sampling reduce comparative Monte Carlo noise.

Robustness targets: b=0/1000, B1=.7/.8/1/1.2, B0=0/100 Hz, excitation offset
0/45/90 degrees. Confirm spin-count/time-step and RF-model sensitivity for the
leading candidate. Exact settings and raw outputs are saved under `runs/improve_*`.
Record failed or rejected interventions in the final report; do not combine changes
before measuring them individually. Scanner feasibility uses existing timing,
gradient, and slew limits; scanner compilation/SAR certification are outside the
local model.

## Results and controlled follow-ups

The first 16 variants were screened individually at phase 0/90 degrees; subsequent
bounded follow-ups tested linear, irregular and duration-half crusher schemes.
The first varying table reduced unwanted share but lost total signal. A linear
40%-per-echo amplitude increment offered a better signal/purity compromise, so
it and its centred combination were subjected to the same robustness and
sensitivity grid before selection. Combined candidates retain separate individual
comparisons. Exact variant definitions are in `examples/improve_ppl.py`.

Completed: 44 screen conditions, 336 robustness conditions across seven variants,
30 spin-count/RF-step/shape/gradient-lag sensitivity conditions, and two
eight-dummy/post-crusher conditions (412 Bloch conditions total). Sample-level
pathway decomposition and signal closure were checked independently, plus
0.5/1/2-mm PDG spatial support and a D=.001-mm²/s water check. The final candidate
is linear+centred, while the stronger varying+centred table remains a documented
purity trade-off. Neither is scanner validated.

The source-audit memory hypothesis was narrowed before adoption: DWI rejects
PE order 0, and the ETL-256 spill touches an unused word. The accepted proof uses
diffusion OFF/PE order 0/ETL 512/no_views 1024 with TR 30 s and an ordered RAM
replay showing three altered PE entries. The report distinguishes this dormant
source defect from current DWI behavior.

Measurements, failed interventions, limits, and exact reproduction commands are
in `docs/ppl_improvement_report.md`; compact results are committed in `docs/data/`.
