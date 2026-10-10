# DW-FSE Spin Explorer

Open `spin_explorer.html` in a browser (no server, no install). It shows a Pulseq sequence
diagram above a rotating-frame Bloch sphere. Scrub or play through the sequence and watch an
isochromat ensemble evolve, along with its through-slice profile (Mx/My/Mz vs z),
its dephasing states (F_n/Z_n across the slice) and the echo train.

- **Sequences:** built-in hard-pulse examples (`examples/ex*.seq`), plus the TE 64 / ESP 16 / ETL 8
  DW-FSE controls and Alsop/ss-MGOT adaptations from `examples/compare_prepared_fse.py`
  (excitation phase 0°). Any Pulseq 1.3–1.5 `.seq` file can be loaded.
- **Physics controls:** B1 scale and in-voxel spread, B0 offset, T2′ spread, T1/T2, finite (file)
  or ideal instantaneous RF, and the motion phase. The motion phase is either coherent per voxel
  (with a φ-sweep band in the Echo train tab) or dispersed per isochromat. Ensemble size, z range,
  slice and in-plane voxel can also be set, along with the simulation window.
- **Guided experiments:** CPMG vs CP, crusher pathway selection, off-resonance refocusing,
  motion phase in DW-FSE, Original vs Alsop vs ss-MGOT across φ, real vs ideal slice profile,
  crusher schedules, and intravoxel phase dispersion.

`engine.js` is the parser and simulator. It uses the conventions of `dwfse/simulate.py`, and the
echo amplitudes agree with it to about 0.003 M0 on these files. `app.js` is the UI and
`template.html` the page. Rebuild the bundled page after editing any of them, or after adding
`.seq` files to `sequences/`:

```bash
python tools/spin_explorer/build.py
```
