# v1.83 off-centre RF phase calibration

## What the two console parameters do

- **Off-centre RF phase mode** (`v183_phmode`): 0 = vendor / v1.81 per-echo phase scheme (default). 1 = v1.82 gated scheme, the only mode that uses the calibration value.
- **Off-centre RF phase cal** (`v183_phcal`, -2000 to 2000, 0.1 us ticks): used only in mode 1. It shifts the modelled timing of every off-centre refocusing pulse.
- A timing error tau gives each off-centre pulse a phase error of 360 x f x tau. That error builds up as a steady echo-phase ramp of s deg/echo in the navigator.
- f = z x 2130 Hz/mm for the default 1 mm slice with rfnum 1. At +1.2 mm, f = 2556 Hz and k = 360 x f x 1e-7 = 0.092 deg/echo per tick.
- Mode 1 model: s(P) = s0 + sigma x k x P. The zero of the ramp is P0. The 2026-10-11 data put P0 near +/-530 at +/-1.2 mm.
- Pass per off-centre slice: |ramp| <= 5 deg/echo and |alternation| <= 5 deg.

## Rules for every scan

- Same subject, same PBS, same protocol. Change only the mode or the phcal value.
- Use TR 2000, 40 kHz, ESP 11, three slices per scan (the 2026-10-11 K/S/O scans were TR 1000; their +/-30-50 deg alternation contaminates the fit).
- Save each MRD in its own folder under `experiments/`; replace the placeholder paths below.

## Step 1: mode 0 check (K geometry, +/-1.2 mm, b10)

1. Set `v183_phmode` = 0. Scan the three-slice K geometry (z = -1.2, 0, +1.2 mm).
2. Run:
   `python tools/offcentre_phase_cal.py experiments/<date>_v183_K_m0/<name>.MRD`
3. Check the +/-1.2 mm ramp. Mode 0 should give |s| <= 5 (the 10-10 v1.81 reference gave -1.1 and -0.7).
4. If |s| > 5, mode 0 has its own phase error and needs a different correction. Stop and report it.
5. An alternation of +/-15-17 deg in mode 0 is expected from the 10-10 data. It does not decide the phcal question.

## Step 2: mode 1 at three phcal values (same K geometry)

1. Set `v183_phmode` = 1.
2. Scan three times, changing only `v183_phcal`: 0, then +530, then -530.
3. Keep the three MRDs as `..._m1_p0`, `..._m1_pp530` and `..._m1_pm530`.

## Step 3: solve for the recommended value

1. Run the tool on the three mode-1 MRDs (the mode-0 scan is ignored for the phcal solution):
   `python tools/offcentre_phase_cal.py experiments/<date>_v183_K_m1_p0/<name>.MRD experiments/<date>_v183_K_m1_pp530/<name>.MRD experiments/<date>_v183_K_m1_pm530/<name>.MRD --out experiments/<date>_v183_K_cal.json --plot experiments/<date>_v183_K_cal.png`
2. The tool prints the sign it chose from the residuals, the zero P0 for each slice, and `RECOMMENDED v183_phcal`. Set that value.
3. If only one mode-1 MRD exists, the tool prints two candidates per slice, `P - s/k` and `P + s/k`. Scan once at one of them. The candidate that brings the ramp to |s| <= 5 is correct.
4. Check the spread in the output. A spread of more than about 100 ticks means the slices disagree and the value is not reliable.

## Step 4: verify at the outer slices

1. With the recommended phcal, scan the S geometry (+/-2.4 mm, three slices) and the O geometry (+/-5 mm, three slices).
2. Run:
   `python tools/offcentre_phase_cal.py experiments/<date>_v183_S_cal/<name>.MRD`
   `python tools/offcentre_phase_cal.py experiments/<date>_v183_O_cal/<name>.MRD`
3. Pass = every off-centre slice has |ramp| <= 5 and |alternation| <= 5 deg. An alternation failure with a passing ramp is not a phcal problem; it is the separate TR/alternation issue in the Oct-11 notes.

## Deciding mode 0 or mode 1

- Compare the largest off-centre |ramp| in the two modes at the same geometry. Keep the mode with the smaller value.
- If the ramps tie, keep the mode with the cleaner outer-slice images (PBS stripes, double edges).
- Mode 0 is the default. Switch to mode 1 only if its ramp is clearly smaller at all three geometries.
- Do not judge by alternation alone; both modes showed it on 10-11.

## 2026-10-11 numbers (v1.82 = mode 1, phcal 0; v1.81 = mode 0)

| Scan | Slices | Ramp (deg/echo) | Tau (us) | Note |
|---|---|---|---|---|
| v1.82 K (TR 1000) | -1.2 / +1.2 mm | -48.5 / +50.1 | +53 / +54 | alternation contaminated by TR 1000 |
| v1.82 S (TR 1000) | -2.4 / +2.4 mm | -97.7 / +99.5 | +53 / +54 | |
| v1.82 V (TR 2000, 256 samples) | -2.4 / +2.4 mm | -112.7 / +84.1 | +61 / +46 | cleanest off-centre fit |
| v1.82 O (TR 1000) | -5 / +5 mm | +34.3 / -29.7 | -9 / -8 | does not follow 41 deg/mm |
| v1.81 K (TR 2000, mode 0) | -1.2 / +1.2 mm | -1.1 / -0.7 | +1 / -1 | alternation +/-16 deg |

- Centre slice ramp: under 1 deg/echo in every v1.82 scan.
- Single-scan candidates for K, S and V agree at about +/-530 ticks.
- Ramps are known only modulo 180 deg (a 180-deg ramp looks like an alternation shift), so the sign of the single-scan candidate is provisional until Step 2.
- Tau is known only modulo 1/f (about 94 us at 5 mm). The tool lists the alias.
- The nominal 2130 Hz/mm is approximate. If a scan suggests a different scale, rerun with `--hz-per-mm <value>`.
