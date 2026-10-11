# Recon checks

Run `python examples/test_v182_v1912_recon.py` from the repository root. It reads
archived scans A, C, B, D and E without changing `experiments/`. Reconstructed
NIfTIs, nominal `.bval/.bvec`, effective `_beff.bval`, full `_bmatrix.txt` and JSON
sidecars are saved here in the scan-letter folders. `results.json` contains the
measured checks and phase estimates; the `cache/` directory holds reusable source
model results. Re-running with the cache is about 0.05–0.08 seconds per scan on
this machine; initial model runs were about 2–4 seconds per scan.

The final-report echo-1 traces at nominal b=0/100/1000/6000 for v1.8, v1.81,
v1.91 and v1.911 are reproduced within **0.0016 s/mm²** (required: 0.5). The
independent direction checks reproduce v1.8/v1.81 −x, +y and +z behaviour. The
model includes every mapped gradient, the instantaneous refocusing sign changes
and the ss-MGOT longitudinal interval. The ss-MGOT branch with the smallest echo
endpoint is selected, matching the existing final physics grid. Logical axes are
x=read, y=phase, z=slice; off-diagonal entries are the tensor entries themselves,
without a factor of two.

Archived A/C/B/D/E complex sorted k-space and reconstructed arrays are
bit-identical to the original mode-1 arithmetic. All original diffusion and
navigator arithmetic for ETL≥2 is preserved; ETL=1 is newly admitted and its
unidentifiable T2 diagnostic returns NaNs. Saved archive
NIfTIs differ only by the expected float32 serialization rounding (absolute max
1.5–4.8×10⁻⁷; relative max <10⁻⁶). Original nominal b files are retained.
Noise-subtracted navigator echoes 2–8 give median low-b effective ADCs:

| Scan | ADC, ×10⁻³ mm²/s |
|---|---:|
| A, v1.81 | 1.8535 |
| C, v1.8 | 1.8550 |
| B, v1.911 | 1.8450 |
| D, v1.91 | 1.8608 |

The largest spread is **0.86%**, inside the documented 3% agreement band. The
echo-1 b0 deficit is deliberately excluded from that fit.

The synthetic check derives navigators from A's measured volume navigator,
injects known random constant and linear readout phase in every imaging shot,
and verifies recovery relative to the selected reference shot. Relative complex
k-space error is **9.36×10⁻⁸** (limit 2×10⁻⁶). Real-format synthetic MRDs labelled
v1.82 and v1.912 exercise automatic mode-2 parsing and full reconstruction. Their
image and k-space errors are recorded in `results.json`. Pure noise navigators
trigger fallback for every shot and leave imaging data bit-identical. The off
switch, constant-only switch, absent flag (mode 0), and unsupported flag error
are checked too. These synthetic tests validate recon, not acquired scanner data.

Mode 2 uses **embedded NO_VIEWS equal to total raw MRD rows**. With ETL 8 and
128 image rows, this is 153: a leading 9-row volume train (8 envelope echoes plus
one appended echo), then 16 imaging shots each containing 8 image echoes and one
appended unencoded echo. The embedded `nav_on=2`, `NO_VIEWS=153` and
`VIEWS_PER_SEGMENT=8` determine the layout exactly. The recon checks that the raw
count agrees, derives 128 image rows, drops appended lines from imaging k-space,
and uses only the first eight leading rows for inherited envelope correction.

`--shot-nav-mode off|constant|constant+linear` controls the extra phase correction;
the default is constant+linear. The fit uses magnitude-weighted unwrapped
projection phase and conjugates it in hybrid x–ky. A strongest-SNR reference shot
retains the unobservable shared phase. Per-shot QA records intercept (radians),
slope (radians/readout voxel), navigator SNR, residual coherence and the applied
or rejected disposition. Default gates are SNR≥3 and coherence≥0.65. Those gates
need confirmation with an acquired mode-2 phantom/in-vivo scan. Edge projection
pixels estimate noise, so an object filling the readout FOV can conservatively
disable correction. No 2D ky phase correction is attempted.

Effective-b output is **source-model-only**. `BMatrixWarnings` states the
instantaneous primary-pathway scope and assumed timing. Missing PPL or model
failure produces nominal matrices and `BMatrixSource="nominal-fallback"` with a
warning; it does not prevent image reconstruction. The cache key contains the
PPL/protocol SHA-256 hashes, model revision and selected echo. v1.91 resolves to
the acquired method-only v7 snapshot under `docs/v181_v1911/baseline_v7/`, since
the current scanner/1.91 source is a different combined version. Calibration is
optional and none is asserted by these runs.

The model rejects timer overruns and ignored gradient-list starts rather than
labelling those waveforms valid. Mode 2 retains its acquired raw count and actual
mirrored phase rewinder, maps the leading volume train(s), and selects the first
imaging shot using the recorded navigator counter. This also preserves the
correct mode-2 waveform when the centre echo is later in the train (v1.82 PE6/7).
The representative imaging-shot index is recorded. The reported echo contains
the k-space centre; its tensor uses the first imaging shot, so phase-encode b
terms are a representative value, not an average over all shots.

An optional `--b-calibration PATH` JSON accepts this schema:

```json
{"versions": {"1.81": {"axis_scale": [1.0, 1.0, 1.0],
"additive_bmatrix": [[0,0,0],[0,0,0],[0,0,0]]}}}
```

`axis_scale` multiplies gradient amplitude in logical read/phase/slice axes, so
the matrix receives both factors (`B′ij=si sj Bij + Aij`). The additive matrix is
in s/mm². Each version is independent; entries must be finite and the resulting
matrix positive semidefinite. Application, exact entries and calibration file
hash are recorded in JSON. The test file contains artificial factors to check
mechanics only; it is not a proposed scanner calibration.

Recon CLI example:

```text
python scanner/recon/bare_bones_recon_fse.py INPUT.MRD --output-dir OUTPUT --no-figures
```
