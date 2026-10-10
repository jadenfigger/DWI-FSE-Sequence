/* DW-FSE Spin Explorer UI. Needs window.SpinEngine and window.SEQ_FILES ({key: seq text}). */
(function () {
  'use strict';
  const E = window.SpinEngine;
  const $ = id => document.getElementById(id);
  const DEG = 180 / Math.PI;
  const GAMMA_HZ_PER_MT = 42577.48; // Hz/m per mT/m

  // ------------------------------------------------------------------ catalogue
  const CATALOG = [
    {
      group: 'Hard-pulse building blocks (no slice selection)', items: [
        {
          key: 'ex1_fid', title: 'Free induction decay', short: 'FID',
          desc: 'One 90° hard pulse (phase 0°) and a 40 ms acquisition. Every isochromat precesses at its own off-resonance, so the fan opens and the signal decays with T2* (T2′ combined with T2). Nothing ever brings it back.',
          marks: [['rf1.e', 'Just excited', 'All isochromats point along +y′ together: full signal.'],
                  ['ms:6', 'Fanning out', 'Off-resonant isochromats have drifted apart. Their mean (the bold vector) shrinks although each one is still full length.']],
        },
        {
          key: 'ex2_spin_echo', title: 'Spin echo', short: 'SE',
          desc: '90°x, wait 10 ms, 180°y. The 180° mirrors the fan of off-resonant isochromats about y′, so the fast ones are now behind and catch up exactly at TE = 20 ms. There are no crushers, so try B1 = 0.8 and watch the FID that the imperfect 180° adds.',
          marks: [['rf2.b', 'Fan before the 180°', 'The isochromats have spread by their off-resonance × 10 ms.'],
                  ['rf2.e', 'Mirrored', 'The 180° about y′ reflected every vector: the leading isochromats are now behind.'],
                  ['adc1', 'Echo', 'The fan closes: off-resonance is refocused, only T2 loss remains.']],
        },
        {
          key: 'ex3_cpmg_train', title: 'CPMG train (180° along the magnetization)', short: 'CPMG',
          desc: '90°x then four 180°y with crusher pairs, echo spacing 10 ms. The refocusing axis is parallel to the magnetization (CPMG), so a refocusing error is the same rotation every time and the stimulated pathways add in phase. Try B1 = 0.8: echo 2 onwards stays high.',
          marks: [['rf2.b', 'Before the first crusher', 'Transverse magnetization along +y′, still coherent along z.'],
                  ['rf2.s', 'Crusher wound the helix', 'The left crusher lobe has wound the transverse magnetization into a helix along z (see Profile vs z and the F states).'],
                  ['rf2.e', 'Second crusher unwinds', 'The 180° turned the helix around; the identical right lobe unwinds it. Whatever the imperfect 180° left in other states stays wound.'],
                  ['adc2', 'Echo 2', 'Echo 2 with B1 errors: the stimulated echo adds to the primary echo here.']],
        },
        {
          key: 'ex4_cp_train', title: 'CP train (180° along the excitation axis)', short: 'CP',
          desc: 'Same 90°x but the 180° pulses are also along x′ (Carr–Purcell), and there are no crushers. With a perfect 180° it is equivalent to CPMG. With B1 = 0.8 each refocusing error rotates the magnetization out of the transverse plane and the errors accumulate instead of cancelling: the train collapses.',
          marks: [['rf2.e', 'After an imperfect 180°x', 'Set B1 = 0.8: the vectors no longer lie in the transverse plane.'],
                  ['adc3', 'Echo 3', 'With B1 = 0.8 this echo is nearly gone.']],
        },
        {
          key: 'ex5_unequal_first_interval', title: 'Unequal first interval', short: 'Unequal',
          desc: '90°, 20 ms, 180°, 20 ms, echo 1, and a second 180° only 5 ms later. The first 180° also stores some magnetization as Mz. Because the intervals differ, that stimulated echo returns 20 ms after the second 180° (≈ 66 ms), not on echo 2 (≈ 51 ms). Use B1 = 0.8.',
          marks: [['ms:51', 'Echo 2', 'The primary echo of the second 180°.'],
                  ['ms:66', 'Stimulated echo', 'Magnetization that sat in Z states between the two 180° pulses refocuses here, off the echo.']],
        },
        {
          key: 'ex5_unequal_first_interval_b', title: 'Unequal first interval, half-size first crushers', short: 'Unequal ½',
          desc: 'Same timing as the previous file, but the crushers around the first 180° are half as large. The stimulated-echo pathway now ends with net dephasing and is crushed: the 66 ms peak disappears. This is what the small first-180° crushers in the DW-FSE do.',
          marks: [['ms:66', 'Where the stimulated echo was', 'With unequal crusher pairs this pathway keeps half a crusher of dephasing.']],
        },
        {
          key: 'ex6_dw_fse_mini', title: 'Mini DW-FSE', short: 'mini DW-FSE',
          desc: 'Stejskal–Tanner lobes on x around the first 180° (TE1 40 ms), then three 180°y at 10 ms spacing. With static spins and a 0° excitation phase it behaves like CPMG. Turn on a coherent motion phase of 90° together with B1 = 0.8 to see why motion during the lobes breaks the train.',
          motionBlock: 8,
          marks: [['b4.e', 'First diffusion lobe', 'The lobe winds spins across the in-plane voxel (x): switch the 3D view to "Every spin".'],
                  ['b8.e', 'Motion phase', 'The motion phase is added here, after the second lobe.'],
                  ['adc2', 'Train echo', 'With a 90° motion phase and B1 = 0.8 the train is no longer CPMG.']],
        },
      ],
    },
    {
      group: 'DW-FSE with preparations (TE 64 ms, ESP 16 ms, ETL 8, b 1000)', items: [
        {
          key: 'original', title: 'Original v1.6 DW-FSE', short: 'Original',
          desc: '90° excitation, diffusion lobes on read around a first 180° with small crushers, first echo at 64 ms, then seven 180°(−y′) every 16 ms with large constant crushers. The first 180° is part of the train, so the motion phase decides whether the train is CPMG (0°/180°) or CP (90°/270°). The v1.6 file plays each 180° 60 µs off its slice-select plateau, which leaves a twist through the slice at every echo.',
          motionBlock: 9,
          marks: [['rf1.e', 'Excited slice', 'Profile vs z shows the sinc slice profile; the 3D fan is the slice-select twist before the rephaser.'],
                  ['b5.e', 'Diffusion lobe 1', 'The read lobe (b 1000) winds the voxel along x; "Every spin" shows it.'],
                  ['b9.e', 'Motion phase', 'The motion phase is applied here, after the second lobe.'],
                  ['adc1', 'Echo 1 (TE 64 ms)', 'Diffusion-weighted echo. Its phase relative to −y′ is the motion phase.'],
                  ['rf3.b', 'Train crusher', 'The large train crushers wind about 3 turns across the slice before each 180°.'],
                  ['adc8', 'Echo 8', 'Compare with the prepared sequences under B1 = 0.8: use Sweep φ in Echo train.']],
        },
        {
          key: 'centered_original', title: 'Original, 180° re-centred', short: 'Centred',
          desc: 'The original sequence with each refocusing pulse centred on its slice-select plateau. Compare Profile vs z at echo 1 with the original: the through-slice twist from the 60 µs offset is gone.',
          motionBlock: 9,
          marks: [['adc1', 'Echo 1', 'Flat phase through the slice, unlike the original.'], ['adc2', 'Echo 2', '']],
        },
        {
          key: 'alternating', title: 'Alternating-polarity crushers', short: 'Alternating',
          desc: 'Train crushers alternate in sign (+, −, +, …) at constant strength. Spurious pathways are sorted onto different dephasing orders than with constant crushers; check F states between pulses.',
          motionBlock: 9,
          marks: [['rf3.b', 'Crusher +', ''], ['rf4.b', 'Crusher −', ''], ['adc8', 'Echo 8', '']],
        },
        {
          key: 'increasing', title: 'Increasing crushers', short: 'Increasing',
          desc: 'Train crusher strength grows from 1× to 3.4× along the train, so each unwanted pathway ends with its own net dephasing and fewer of them overlap the primary echo.',
          motionBlock: 9,
          marks: [['rf3.b', 'Crusher 1×', ''], ['rf9.b', 'Crusher 3.4×', ''], ['adc8', 'Echo 8', '']],
        },
        {
          key: 'decreasing', title: 'Decreasing crushers', short: 'Decreasing',
          desc: 'The mirror image of the increasing schedule: strongest crushers right after the diffusion echo, weakest at the end.',
          motionBlock: 9,
          marks: [['rf3.b', 'Crusher 3.4×', ''], ['adc8', 'Echo 8', '']],
        },
        {
          key: 'alsop', title: 'Alsop preparation (adaptation)', short: 'Alsop',
          desc: 'After the diffusion spin echo at 48 ms, a Gz lobe winds 2 turns across the slice. A 90° pulse about −y′ (the CPMG axis) then stores the x′ part of every vector in Mz. Whatever the motion phase, the part along y′ stays transverse and is CPMG-compatible; a recall lobe before each ADC unwinds it. The price is half the signal, independent of the phase.',
          motionBlock: 9,
          marks: [['b9.e', 'Motion phase', 'Arbitrary phase added here. Change φ and watch which part of the helix ends up in Mz.'],
                  ['b11.e', 'Helix wound (2 turns)', 'Every phase now exists somewhere along z: Mx and My oscillate through the slice.'],
                  ['rf3.e', 'After the 90°(−y′) tip', 'x′ parts are now stored in Mz (see the cos pattern in Mz); y′ parts stay transverse.'],
                  ['rf4.e', 'First train 180°', 'The transverse part is along ±y′, parallel to the refocusing axis: CPMG.'],
                  ['adc1', 'Echo 1, recalled', 'The recall lobe brings one of the two helix components back to F0: about half the signal.'],
                  ['adc8', 'Echo 8', 'Compare with the original at B1 = 0.8: Sweep φ in Echo train for both.']],
        },
        {
          key: 'ss_mgot', title: 'ss-MGOT preparation (adaptation)', short: 'ss-MGOT',
          desc: 'The diffusion spin echo is at 36 ms in a 3 mm slab. A 2-turn Gz lobe, then a 90° pulse about −x′ stores the y′ parts in Mz; a 6 ms Gy spoiler (8 turns across the voxel) destroys what stayed transverse; a new 90° (phase 0°) re-excites the stored pattern with a known phase. The train is then true CPMG. Half the signal is kept, T1-weighted while stored.',
          motionBlock: 9,
          marks: [['b9.e', 'Motion phase', 'Arbitrary phase added here.'],
                  ['b11.e', 'Helix wound', 'Two turns across the slice.'],
                  ['rf3.e', 'Tip-up 90°(−x′)', 'y′ parts are now in Mz; x′ parts stay transverse.'],
                  ['b15.e', 'Spoiled', 'The Gy spoiler has dispersed the remaining transverse part across the voxel; only the Mz pattern is left. Try "Every spin".'],
                  ['rf4.e', 'Re-excited', 'The stored pattern is tipped back with phase 0°: its phase is now set by the RF, not by motion.'],
                  ['adc1', 'Echo 1', 'About half the magnetization, recalled.']],
        },
      ],
    },
  ];
  const ITEMS = {};
  CATALOG.forEach(g => g.items.forEach(it => { ITEMS[it.key] = it; }));

  // ------------------------------------------------------------------ parameters
  const PARAMS = [
    { group: 'RF and fields', items: [
      { id: 'b1', label: 'B1 scale', type: 'range', min: 0.5, max: 1.3, step: 0.01, fmt: v => v.toFixed(2) + '×', hint: 'Scales every RF pulse. 0.8 = all flip angles 20 % short.' },
      { id: 'b1Spread', label: 'B1 spread within voxel', type: 'range', min: 0, max: 30, step: 1, fmt: v => '±' + v + ' %' },
      { id: 'b0', label: 'B0 offset', type: 'range', min: -400, max: 400, step: 5, fmt: v => v + ' Hz', hint: 'Shifts every isochromat. Moves the slice by Δf / G and adds phase between pulses.' },
      { id: 't2p', label: 'T2′ (field spread)', type: 'range', min: 0, max: 100, step: 1, fmt: v => v ? v + ' ms' : 'off', hint: 'Lorentzian off-resonance spread, HWHM = 1/(2π T2′).' },
      { id: 'rfMode', label: 'RF pulses', type: 'seg', options: [['finite', 'From file'], ['ideal', 'Ideal instant']], hint: '“Ideal” swaps each pulse for an instant rotation at its centre with a rectangular slab of the same bandwidth.' },
    ] },
    { group: 'Motion phase (diffusion)', items: [
      { id: 'motionMode', label: 'Phase added by motion', type: 'select', options: [['none', 'none (static spins)'], ['coherent', 'coherent φ for the whole voxel'], ['gauss', 'per isochromat, Gaussian σ = φ'], ['uniform', 'per isochromat, uniform 0–360°']],
        hint: 'Coherent φ is bulk motion: one phase per voxel that changes from shot to shot. Use “Sweep φ” in Echo train to see all phases at once. Per-isochromat phases disperse inside the voxel: that is diffusion attenuation, and no preparation recovers it.' },
      { id: 'motionDeg', label: 'φ', type: 'range', min: 0, max: 360, step: 5, fmt: v => v + '°' },
      { id: 'motionAfter', label: 'Applied after', type: 'select', options: [] },
    ] },
    { group: 'Relaxation', items: [
      { id: 'T1', label: 'T1', type: 'range', min: 100, max: 3000, step: 50, fmt: v => v + ' ms' },
      { id: 'T2', label: 'T2', type: 'range', min: 10, max: 1000, step: 5, fmt: v => v + ' ms' },
    ] },
    { group: 'Ensemble & window', items: [
      { id: 'nz', label: 'z positions', type: 'range', min: 21, max: 201, step: 4, fmt: v => String(v) },
      { id: 'nsub', label: 'Isochromats per z', type: 'range', min: 1, max: 64, step: 1, fmt: v => String(v) },
      { id: 'zSpan', label: 'z range', type: 'range', min: 0.5, max: 6, step: 0.1, fmt: v => v.toFixed(1) + ' mm' },
      { id: 'thk', label: 'Nominal slice', type: 'range', min: 0, max: 5, step: 0.05, fmt: v => v ? v.toFixed(2) + ' mm' : 'none', hint: 'Sets “in-slice” for the signal normalization and the F/Z states. 0 = non-selective.' },
      { id: 'voxXY', label: 'In-plane voxel', type: 'range', min: 0, max: 1, step: 0.05, fmt: v => v.toFixed(2) + ' mm' },
      { id: 'tStart', label: 'Window start', type: 'number', min: 0, step: 1, unit: 'ms' },
      { id: 'tEnd', label: 'Window end', type: 'number', min: 1, step: 1, unit: 'ms' },
    ] },
  ];
  const DEFAULTS = { b1: 1, b1Spread: 0, b0: 0, t2p: 30, rfMode: 'finite', motionMode: 'none', motionDeg: 90, motionAfter: 'auto',
    T1: 1500, T2: 80, nz: 81, nsub: 24, zSpan: 2, thk: 1, voxXY: 0.2, tStart: 0, tEnd: 200 };

  // ------------------------------------------------------------------ state
  const S = {
    key: null, item: null, seq: null, P: Object.assign({}, DEFAULTS), sim: null, runId: 0,
    t: 0, playing: false, view: [0, 1], cam: { az: -2.2, el: 0.42, zoom: 1 }, tab: 'profile', selZ: null,
    pins: [], dirtyStatic: true, events: [], uploaded: {},
  };

  // ------------------------------------------------------------------ colours
  let C = {};
  function readColors() {
    const cs = getComputedStyle(document.documentElement);
    for (const k of ['bg', 'panel', 'ink', 'muted', 'line', 'soft', 'accent', 'rf', 'gx', 'gy', 'gz', 'adc', 'sig', 'warn']) C[k] = cs.getPropertyValue('--' + k).trim();
    S.dirtyStatic = true;
  }
  function hexRgb(h) { const n = parseInt(h.replace('#', ''), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
  function rgba(h, a) { const [r, g, b] = hexRgb(h); return `rgba(${r},${g},${b},${a})`; }
  const ZSTOPS = [[47, 111, 222], [138, 79, 216], [209, 71, 122], [233, 133, 47]];
  function zColor(f) {
    f = Math.max(0, Math.min(1, f)) * (ZSTOPS.length - 1);
    const i = Math.min(ZSTOPS.length - 2, Math.floor(f)), u = f - i, a = ZSTOPS[i], b = ZSTOPS[i + 1];
    return `rgb(${a[0] + (b[0] - a[0]) * u | 0},${a[1] + (b[1] - a[1]) * u | 0},${a[2] + (b[2] - a[2]) * u | 0})`;
  }
  function divColor(f) { // -1..1 blue - grey - orange
    f = Math.max(-1, Math.min(1, f));
    const g = [140, 150, 165], lo = [58, 123, 213], hi = [224, 122, 47], t = Math.abs(f), e = f < 0 ? lo : hi;
    return `rgb(${g[0] + (e[0] - g[0]) * t | 0},${g[1] + (e[1] - g[1]) * t | 0},${g[2] + (e[2] - g[2]) * t | 0})`;
  }
  const PIN_COLORS = ['rf', 'gz', 'gy', 'adc', 'gx', 'warn'];

  // ------------------------------------------------------------------ helpers
  const fmtMs = t => (t * 1e3).toFixed(3) + ' ms';
  function axisName(phaseRad) {
    let d = ((phaseRad * DEG) % 360 + 360) % 360;
    const near = v => Math.abs(d - v) < 0.5 || Math.abs(d - v - 360) < 0.5;
    if (near(0)) return 'x′'; if (near(90)) return 'y′'; if (near(180)) return '−x′'; if (near(270)) return '−y′';
    return d.toFixed(0) + '°';
  }
  const useName = u => ({ e: 'excitation', r: 'refocusing', p: 'preparation', i: 'inversion', s: 'saturation' }[u] || 'RF');
  function fitCanvas(c) {
    const r = c.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    const w = Math.max(10, Math.round(r.width)), h = Math.max(10, Math.round(r.height));
    if (c.width !== Math.round(w * dpr) || c.height !== Math.round(h * dpr)) { c.width = Math.round(w * dpr); c.height = Math.round(h * dpr); }
    const ctx = c.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx, w, h, dpr };
  }
  function setStatus(txt, busy) { const s = $('status'); s.textContent = txt; s.classList.toggle('busy', !!busy); }

  // ------------------------------------------------------------------ sequence loading
  function seqText(key) { return S.uploaded[key] || (window.SEQ_FILES || {})[key]; }

  function estimateThickness(seq) {
    if (seq.sliceThickness) return seq.sliceThickness;
    for (const b of seq.blocks) {
      if (!b.rf || !b.g[2]) continue;
      const g = E.gval(b.g[2], b.rf.delay + b.rf.center);
      if (Math.abs(g) > 1e3 && b.rf.bw) return b.rf.bw / Math.abs(g);
    }
    return null;
  }

  function findMotionBlock(seq, item, t0, t1) {
    if (item && item.motionBlock) { const b = seq.blocks.find(x => x.index === item.motionBlock); if (b) return seq.blocks.indexOf(b); }
    const cand = [];
    seq.blocks.forEach((b, i) => {
      if (b.rf || b.start >= t1 || b.start < t0) return;
      const a = b.g.map(g => g ? g.area : 0), m = Math.hypot(...a);
      if (m > 0) cand.push({ i, a, m });
    });
    // diffusion lobes: the largest pair of identical gradient blocks
    let best = null;
    for (let p = 0; p < cand.length; p++) for (let q = p + 1; q < cand.length; q++) {
      const A = cand[p], B = cand[q];
      const d = Math.hypot(A.a[0] - B.a[0], A.a[1] - B.a[1], A.a[2] - B.a[2]);
      if (d < 0.01 * A.m && (!best || A.m > best.m * 1.001)) best = { m: A.m, i: B.i };
    }
    if (best) return best.i;
    const rf1 = seq.blocks.findIndex(b => b.rf);
    return rf1;
  }

  function loadSequence(key, opts = {}) {
    const text = seqText(key);
    let seq;
    try { seq = E.parseSeq(text); } catch (err) { setStatus('could not read file'); showNote('This file could not be read: ' + err.message + ' Load a Pulseq 1.3–1.5 .seq file.'); return false; }
    S.key = key; S.item = ITEMS[key] || null; S.seq = seq;
    $('seqSelect').value = key;
    // sequence-specific defaults
    const thk = estimateThickness(seq);
    const P = Object.assign({}, DEFAULTS);
    P.thk = thk ? +(thk * 1e3).toFixed(2) : 0;
    P.zSpan = thk ? +Math.min(6, Math.max(0.5, 2 * thk * 1e3)).toFixed(1) : 2;
    P.t2p = thk ? 30 : 3;
    P.tStart = 0;
    const end = Math.min(seq.lastActive + 0.5e-3, seq.total);
    P.tEnd = Math.ceil(Math.min(end, 0.6) * 1e3);
    if (!opts.resetPhysics) for (const k of ['b1', 'b1Spread', 'b0', 'rfMode', 'motionMode', 'motionDeg', 'T1', 'T2']) P[k] = S.P[k];
    Object.assign(P, opts.params || {});
    S.P = P;
    S.selZ = null;
    buildMotionOptions();
    syncControls();
    renderInfo();
    S.view = [P.tStart * 1e-3, P.tEnd * 1e-3];
    S.t = P.tStart * 1e-3;
    S.sim = null;
    S.dirtyStatic = true;
    if (end > 0.6 && !opts.quiet) showNote(`This file runs ${(seq.total * 1e3).toFixed(0)} ms. The simulation window is set to the first ${P.tEnd} ms; change it under Ensemble & window.`);
    else if (!opts.keepNote) showNote('');
    runSim();
    return true;
  }

  function buildMotionOptions() {
    const sel = $('p-motionAfter'), seq = S.seq;
    const t0 = S.P.tStart * 1e-3, t1 = S.P.tEnd * 1e-3;
    const auto = findMotionBlock(seq, S.item, t0, t1);
    const ab = seq.blocks[auto];
    const opts = [['auto', `auto: end of block ${ab ? ab.index : '—'} (${ab ? ((ab.start + ab.dur) * 1e3).toFixed(1) : '–'} ms)`]];
    seq.blocks.forEach((b, i) => { if (b.rf && b.start < t1 && b.start >= t0) opts.push([String(i), `after RF ${b.rfNo} (${useName(b.rf.use)}), block ${b.index}`]); });
    sel.innerHTML = opts.map(([v, l]) => `<option value="${v}">${l}</option>`).join('');
    if (![...sel.options].some(o => o.value === String(S.P.motionAfter))) S.P.motionAfter = 'auto';
    sel.value = String(S.P.motionAfter);
    S.autoMotion = auto;
  }
  function motionBlockIndex() { return S.P.motionMode === 'none' ? -1 : (S.P.motionAfter === 'auto' ? S.autoMotion : +S.P.motionAfter); }

  // ------------------------------------------------------------------ simulation
  function makeSim(seq, P, item) {
    const thk = P.thk > 0 ? P.thk * 1e-3 : null;
    const ens = E.makeEnsemble({ nz: P.nz, nsub: P.nsub, zSpan: P.zSpan * 1e-3, thk, voxXY: P.voxXY * 1e-3, t2p: P.t2p * 1e-3,
      b0: P.b0, b1: P.b1, b1Spread: P.b1Spread / 100, motion: { mode: P.motionMode, deg: P.motionDeg }, seed: 11 });
    let mb = -1;
    if (P.motionMode !== 'none') mb = P.motionAfter === 'auto' ? findMotionBlock(seq, item, P.tStart * 1e-3, P.tEnd * 1e-3) : +P.motionAfter;
    const blocks0 = seq.blocks;
    const sim = new E.Simulator(seq, ens, { T1: P.T1 * 1e-3, T2: P.T2 * 1e-3, rfMode: P.rfMode, stepUs: 5,
      motionAfterBlock: -1, tStart: P.tStart * 1e-3, tEnd: P.tEnd * 1e-3, nGrid: 3000 });
    // the simulator indexes its own (windowed) block list
    sim.p.motionAfterBlock = mb >= 0 ? sim.blocks.indexOf(blocks0[mb]) : -1;
    return sim;
  }

  async function simulate(seq, P, item, onProgress, isCurrent) {
    const sim = makeSim(seq, P, item);
    const gen = sim.run();
    for (;;) {
      const r = gen.next();
      if (r.done) break;
      if (onProgress) onProgress(r.value);
      await new Promise(res => setTimeout(res, 0));
      if (isCurrent && !isCurrent()) return null;
    }
    return sim;
  }

  // 8 runs with a coherent motion phase 0..315 deg on a lighter ensemble: mean, min and max echo magnitude
  async function sweep(seq, P, item, isCurrent) {
    const vals = [];
    for (let k = 0; k < 8; k++) {
      setStatus(`φ sweep ${k + 1}/8…`, true);
      const Q = Object.assign({}, P, { motionMode: 'coherent', motionDeg: k * 45, nz: 61, nsub: 12 });
      const sim = await simulate(seq, Q, item, null, isCurrent);
      if (!sim) return null;
      vals.push(sim.echoes.map(e => Math.hypot(...e.value)));
    }
    const n = Math.min(...vals.map(v => v.length));
    const col = i => vals.map(v => v[i]);
    return {
      vals: Array.from({ length: n }, (_, i) => col(i).reduce((a, b) => a + b, 0) / vals.length),
      lo: Array.from({ length: n }, (_, i) => Math.min(...col(i))),
      hi: Array.from({ length: n }, (_, i) => Math.max(...col(i))),
    };
  }
  function sweepLabel(item, key, P) {
    return `${item ? item.short : key} · B1 ${P.b1.toFixed(2)} · φ 0–315° band${P.rfMode === 'ideal' ? ' · ideal RF' : ''}`;
  }

  let simTimer = null;
  function scheduleSim() { clearTimeout(simTimer); simTimer = setTimeout(runSim, 220); }
  async function runSim() {
    const id = ++S.runId;
    if (!S.seq) return;
    setStatus('simulating 0 %', true);
    let sim;
    try {
      sim = await simulate(S.seq, S.P, S.item, f => setStatus(`simulating ${Math.round(f * 100)} %`, true), () => id === S.runId);
    } catch (err) { setStatus('simulation failed', false); showNote(err.message); return; }
    if (!sim) return;
    S.sim = sim;
    S.t = Math.max(sim.tStart, Math.min(S.t, sim.tEnd));
    buildEvents();
    S.dirtyStatic = true;
    setStatus(`${sim.ens.N} isochromats · ${sim.blocks.length} blocks`, false);
    if (S.pendingAt) { gotoRef(S.pendingAt); S.pendingAt = null; }
    syncSlider();
    requestRender();
  }

  // ------------------------------------------------------------------ events and bookmarks
  function buildEvents() {
    const ev = [];
    for (const b of S.sim.blocks) {
      if (b.rf) ev.push(b.start + b.rf.delay, b.start + b.rf.delay + b.rf.center, b.start + b.rf.delay + b.rf.dur);
      if (b.adc) ev.push(b.start + b.adc.delay + (Math.floor(b.adc.num / 2) + 0.5) * b.adc.dwell);
      if (!b.rf && (b.g[0] || b.g[1] || b.g[2])) ev.push(b.start, b.start + b.dur);
    }
    ev.push(S.sim.tStart, S.sim.tEnd);
    S.events = [...new Set(ev.map(t => Math.round(t * 1e7) / 1e7))].sort((a, b) => a - b);
    // chips
    const chips = [];
    for (const b of S.sim.blocks) {
      if (b.rf) chips.push(`<button class="chip ev" data-ref="rf${b.rfNo}.e" title="end of RF ${b.rfNo}">RF${b.rfNo} ${b.rf.flipDeg.toFixed(0)}°${axisName(b.rf.axisPhase)}</button>`);
      if (b.adc) chips.push(`<button class="chip ev" data-ref="adc${b.adcNo}" title="centre of ADC ${b.adcNo}">E${b.adcNo}</button>`);
    }
    $('eventChips').innerHTML = '<span class="lbl">Jump to</span>' + chips.join('');
  }

  function refTime(ref) {
    const seq = S.seq; let m;
    if ((m = ref.match(/^ms:([\d.]+)$/))) return +m[1] * 1e-3;
    if ((m = ref.match(/^rf(\d+)\.([bsce])$/))) {
      const b = seq.blocks.find(x => x.rfNo === +m[1]); if (!b) return null;
      return m[2] === 'b' ? b.start : m[2] === 's' ? b.start + b.rf.delay : m[2] === 'c' ? b.start + b.rf.delay + b.rf.center : b.start + b.rf.delay + b.rf.dur;
    }
    if ((m = ref.match(/^adc(\d+)$/))) {
      const b = seq.blocks.find(x => x.adcNo === +m[1]); if (!b) return null;
      return b.start + b.adc.delay + (Math.floor(b.adc.num / 2) + 0.5) * b.adc.dwell;
    }
    if ((m = ref.match(/^b(\d+)\.([se])$/))) {
      const b = seq.blocks.find(x => x.index === +m[1]); if (!b) return null;
      return m[2] === 's' ? b.start : b.start + b.dur - 1e-7; // stay inside the block for the narration
    }
    return null;
  }
  function gotoRef(ref) {
    const t = refTime(ref); if (t === null) return;
    setTime(t, true);
  }

  // ------------------------------------------------------------------ info panel
  function renderInfo() {
    const it = S.item, seq = S.seq, d = seq.defs;
    $('seqTitle').textContent = it ? it.title : (d.Name || S.key);
    $('seqDesc').textContent = it ? it.desc : (d.Description || 'Loaded from file. Use the event chips and the diagram to explore it.');
    const facts = [];
    facts.push(`Pulseq ${seq.version.major}.${seq.version.minor}`);
    facts.push(`${seq.blocks.length} blocks`, `${seq.nRF} RF`, `${seq.nADC} ADC`);
    if (d.TE) facts.push(`TE ${(+d.TE * 1e3).toFixed(0)} ms`);
    if (d.EchoSpacing) facts.push(`ESP ${(+d.EchoSpacing * 1e3).toFixed(0)} ms`);
    if (d.bValuesRequested) facts.push(`b ${d.bValuesRequested}`);
    const thk = estimateThickness(seq);
    facts.push(thk ? `slice ${(thk * 1e3).toFixed(2)} mm` : 'non-selective');
    $('seqFacts').innerHTML = facts.map(f => `<span>${f}</span>`).join('');
    const marks = it ? it.marks : [];
    $('bookmarks').innerHTML = marks.length ? '<span class="lbl">Look here</span>' + marks.map((m, i) => `<button class="chip" data-mark="${i}">${m[1]}</button>`).join('') : '';
  }
  function showNote(html) { const n = $('note'); n.innerHTML = html || ''; n.hidden = !html; }

  // ------------------------------------------------------------------ time handling
  function setTime(t, center) {
    if (!S.sim) { S.t = t; return; }
    S.t = Math.max(S.sim.tStart, Math.min(t, S.sim.tEnd));
    if (center) {
      const [v0, v1] = S.view, w = v1 - v0;
      if (S.t < v0 || S.t > v1) { S.view = [S.t - w / 2, S.t + w / 2]; clampView(); S.dirtyStatic = true; }
    }
    syncSlider();
    requestRender();
  }
  function syncSlider() {
    if (!S.sim) return;
    const sl = $('time');
    sl.max = 4000;
    sl.value = Math.round((S.t - S.sim.tStart) / (S.sim.tEnd - S.sim.tStart) * 4000);
    $('tread').textContent = fmtMs(S.t);
  }
  function stepEvent(dir) {
    if (!S.events.length) return;
    const eps = 2e-7;
    let t = null;
    if (dir > 0) t = S.events.find(x => x > S.t + eps);
    else for (let i = S.events.length - 1; i >= 0; i--) if (S.events[i] < S.t - eps) { t = S.events[i]; break; }
    if (t !== null && t !== undefined) setTime(t, true);
  }

  let lastFrame = 0;
  function playLoop(ts) {
    if (!S.playing) return;
    const dt = lastFrame ? Math.min(0.1, (ts - lastFrame) / 1000) : 0;
    lastFrame = ts;
    if (S.sim) {
      let rate = +$('speed').value * 1e-3; // sequence seconds per real second
      const b = S.sim.blocks[E.blockAt(S.sim.blocks, S.t)];
      if ($('slowRF').checked && b && b.rf) {
        const tau = S.t - b.start;
        if (tau >= b.rf.delay - 1e-4 && tau <= b.rf.delay + b.rf.dur + 1e-4) rate *= 0.08;
      }
      const nt = S.t + rate * dt;
      if (nt >= S.sim.tEnd) { setTime(S.sim.tEnd, true); togglePlay(false); return; }
      setTime(nt, false);
      const [v0, v1] = S.view;
      if (S.t > v1 - (v1 - v0) * 0.05) { const w = v1 - v0; S.view = [S.t - w * 0.1, S.t + w * 0.9]; clampView(); S.dirtyStatic = true; }
    }
    requestAnimationFrame(playLoop);
  }
  function togglePlay(on) {
    S.playing = on === undefined ? !S.playing : on;
    $('play').textContent = S.playing ? '❚❚' : '▶';
    if (S.playing) {
      if (S.sim && S.t >= S.sim.tEnd - 1e-9) setTime(S.sim.tStart, true);
      lastFrame = 0; requestAnimationFrame(playLoop);
    }
  }

  // ------------------------------------------------------------------ rendering
  let renderQueued = false;
  function requestRender() { if (!renderQueued) { renderQueued = true; requestAnimationFrame(() => { renderQueued = false; render(); }); } }
  let curState = null;
  function render() {
    if (S.sim) curState = S.sim.stateAt(S.t);
    drawDiagram();
    drawSphere();
    drawPlot();
    describeNow();
  }

  // ---- diagram
  const ROWS = [
    { key: 'rf', label: 'RF', h: 1.3 }, { key: 'gx', label: 'Gx', h: 1 }, { key: 'gy', label: 'Gy', h: 1 },
    { key: 'gz', label: 'Gz', h: 1 }, { key: 'adc', label: 'ADC', h: 0.42 }, { key: 'sig', label: '|S|', h: 1.25 },
  ];
  const LEFT = 46, AXIS_H = 20;
  let staticLayer = null, rowGeom = [];
  function clampView() {
    if (!S.sim && !S.seq) return;
    const t0 = S.sim ? S.sim.tStart : S.P.tStart * 1e-3, t1 = S.sim ? S.sim.tEnd : S.P.tEnd * 1e-3;
    let [a, b] = S.view; const w = Math.min(b - a, t1 - t0);
    if (w < 20e-6) { const m = (a + b) / 2; a = m - 10e-6; b = m + 10e-6; }
    else { b = a + w; }
    if (a < t0) { b += t0 - a; a = t0; }
    if (b > t1) { a -= b - t1; b = t1; }
    S.view = [Math.max(t0, a), b];
  }
  function drawDiagram() {
    const cv = $('diag'), { ctx, w, h, dpr } = fitCanvas(cv);
    if (!S.seq) return;
    if (S.dirtyStatic || !staticLayer || staticLayer.width !== cv.width || staticLayer.height !== cv.height) {
      staticLayer = staticLayer || document.createElement('canvas');
      staticLayer.width = cv.width; staticLayer.height = cv.height;
      const sc = staticLayer.getContext('2d'); sc.setTransform(dpr, 0, 0, dpr, 0, 0);
      drawDiagramStatic(sc, w, h);
      S.dirtyStatic = false;
    }
    ctx.clearRect(0, 0, w, h);
    ctx.drawImage(staticLayer, 0, 0, w, h);
    // cursor
    const [v0, v1] = S.view, X = t => LEFT + (t - v0) / (v1 - v0) * (w - LEFT - 6);
    if (S.t >= v0 && S.t <= v1) {
      const x = X(S.t);
      ctx.strokeStyle = C.accent; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(x, 2); ctx.lineTo(x, h - AXIS_H); ctx.stroke();
      ctx.fillStyle = C.accent; ctx.beginPath(); ctx.moveTo(x - 5, 0); ctx.lineTo(x + 5, 0); ctx.lineTo(x, 7); ctx.fill();
    }
  }
  function drawDiagramStatic(ctx, w, h) {
    ctx.clearRect(0, 0, w, h);
    const seq = S.seq, [v0, v1] = S.view, plotW = w - LEFT - 6;
    const X = t => LEFT + (t - v0) / (v1 - v0) * plotW;
    const totalH = h - AXIS_H - 4, unit = totalH / ROWS.reduce((s, r) => s + r.h, 0);
    let y = 4; rowGeom = [];
    for (const r of ROWS) { rowGeom.push({ key: r.key, y0: y, y1: y + r.h * unit, mid: y + r.h * unit / 2, label: r.label }); y += r.h * unit; }
    const G = Object.fromEntries(rowGeom.map(g => [g.key, g]));
    const blocks = seq.blocks.filter(b => b.start + b.dur >= v0 && b.start <= v1);
    // scales over the whole window
    const tw0 = S.P.tStart * 1e-3, tw1 = S.P.tEnd * 1e-3;
    let gmax = 1, rfmax = 1;
    for (const b of seq.blocks) {
      if (b.start > tw1 || b.start + b.dur < tw0) continue;
      for (const g of b.g) if (g) gmax = Math.max(gmax, g.amax);
      if (b.rf) for (let k = 0; k < b.rf.drawRe.length; k++) rfmax = Math.max(rfmax, Math.hypot(b.rf.drawRe[k], b.rf.drawIm[k]));
    }
    // row backgrounds and labels
    ctx.font = '600 11px ' + getComputedStyle(document.body).getPropertyValue('--font-label');
    rowGeom.forEach((g, i) => {
      if (i % 2 === 0) { ctx.fillStyle = rgba(C.line, 0.25); ctx.fillRect(LEFT, g.y0, plotW, g.y1 - g.y0); }
      ctx.fillStyle = C[g.key === 'sig' ? 'sig' : g.key] || C.muted;
      ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
      ctx.fillText(g.label, LEFT - 8, g.mid);
      if (g.key !== 'adc') { ctx.strokeStyle = rgba(C.muted, 0.35); ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(LEFT, (g.key === 'sig' ? g.y1 - 3 : g.mid) + 0.5); ctx.lineTo(w - 6, (g.key === 'sig' ? g.y1 - 3 : g.mid) + 0.5); ctx.stroke(); }
    });
    ctx.save(); ctx.beginPath(); ctx.rect(LEFT, 0, plotW, h); ctx.clip();
    // gradients
    ['gx', 'gy', 'gz'].forEach((k, ax) => {
      const g = G[k], amp = (g.y1 - g.y0) / 2 - 3;
      ctx.fillStyle = rgba(C[k], 0.22); ctx.strokeStyle = C[k]; ctx.lineWidth = 1.2;
      for (const b of blocks) {
        const ch = b.g[ax]; if (!ch) continue;
        ctx.beginPath(); ctx.moveTo(X(b.start + ch.t[0]), g.mid);
        for (let i = 0; i < ch.t.length; i++) ctx.lineTo(X(b.start + ch.t[i]), g.mid - ch.a[i] / gmax * amp);
        ctx.lineTo(X(b.start + ch.t[ch.t.length - 1]), g.mid); ctx.closePath(); ctx.fill(); ctx.stroke();
      }
    });
    // RF (signed amplitude along the pulse's own axis)
    {
      const g = G.rf, amp = (g.y1 - g.y0) / 2 - 4;
      let lastLabelX = -1e9;
      for (const b of blocks) {
        if (!b.rf) continue;
        const rf = b.rf, a0 = rf.axisPhase - rf.phase, ca = Math.cos(a0), sa = Math.sin(a0), t0 = b.start + rf.delay;
        ctx.fillStyle = rgba(C.rf, 0.25); ctx.strokeStyle = C.rf; ctx.lineWidth = 1.2;
        ctx.beginPath(); ctx.moveTo(X(t0), g.mid);
        for (let k = 0; k < rf.drawT.length; k++) ctx.lineTo(X(t0 + rf.drawT[k]), g.mid - (rf.drawRe[k] * ca + rf.drawIm[k] * sa) / rfmax * amp);
        ctx.lineTo(X(t0 + rf.dur), g.mid); ctx.closePath(); ctx.fill(); ctx.stroke();
        const xc = X(t0 + rf.center);
        if (xc - lastLabelX > 46) {
          ctx.fillStyle = C.ink; ctx.textAlign = 'center'; ctx.textBaseline = 'top';
          ctx.font = '500 10.5px ' + getComputedStyle(document.body).getPropertyValue('--font-data');
          const flip = rf.flipDeg * S.P.b1;
          ctx.fillText(`${flip.toFixed(0)}°${axisName(rf.axisPhase)}`, xc, g.y0 + 1);
          lastLabelX = xc;
        }
      }
    }
    // ADC
    {
      const g = G.adc;
      for (const b of blocks) {
        if (!b.adc) continue;
        const a = b.adc, x0 = X(b.start + a.delay), x1 = X(b.start + a.delay + a.num * a.dwell);
        ctx.fillStyle = rgba(C.adc, 0.3); ctx.strokeStyle = C.adc; ctx.lineWidth = 1;
        ctx.fillRect(x0, g.y0 + 2, Math.max(1, x1 - x0), g.y1 - g.y0 - 4); ctx.strokeRect(x0, g.y0 + 2, Math.max(1, x1 - x0), g.y1 - g.y0 - 4);
        if (x1 - x0 > 18) { ctx.fillStyle = C.ink; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.font = '500 10px ' + getComputedStyle(document.body).getPropertyValue('--font-data'); ctx.fillText('E' + b.adcNo, (x0 + x1) / 2, g.mid); }
      }
    }
    // motion marker
    const mbi = motionBlockIndex();
    if (mbi >= 0 && S.seq.blocks[mbi]) {
      const tm = S.seq.blocks[mbi].start + S.seq.blocks[mbi].dur, x = X(tm);
      ctx.strokeStyle = C.warn; ctx.setLineDash([4, 3]); ctx.lineWidth = 1.2;
      ctx.beginPath(); ctx.moveTo(x, G.rf.y0); ctx.lineTo(x, G.sig.y1); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = C.warn; ctx.textAlign = 'left'; ctx.textBaseline = 'top'; ctx.font = '600 11px ' + getComputedStyle(document.body).getPropertyValue('--font-label');
      ctx.fillText('motion φ', x + 3, G.gx.y0 + 1);
    }
    // signal
    let sigMax = 0.25;
    if (S.sim && S.sim.trace) {
      const tr = S.sim.trace, g = G.sig, base = g.y1 - 3, hgt = g.y1 - g.y0 - 8;
      for (let i = 0; i < tr.t.length; i++) sigMax = Math.max(sigMax, Math.hypot(tr.sx[i], tr.sy[i]));
      sigMax = Math.min(1.5, sigMax * 1.08);
      ctx.strokeStyle = C.sig; ctx.lineWidth = 1.4; ctx.beginPath();
      let started = false;
      for (let i = 0; i < tr.t.length; i++) {
        if (tr.t[i] < v0 - (v1 - v0) * 0.01 || tr.t[i] > v1 + (v1 - v0) * 0.01) continue;
        const x = X(tr.t[i]), yy = base - Math.hypot(tr.sx[i], tr.sy[i]) / sigMax * hgt;
        if (!started) { ctx.moveTo(x, yy); started = true; } else ctx.lineTo(x, yy);
      }
      ctx.stroke();
      ctx.fillStyle = C.sig;
      ctx.font = '500 10px ' + getComputedStyle(document.body).getPropertyValue('--font-data');
      for (const e of S.sim.echoes) {
        if (e.t < v0 || e.t > v1) continue;
        const m = Math.hypot(...e.value), x = X(e.t), yy = base - m / sigMax * hgt;
        ctx.beginPath(); ctx.arc(x, yy, 3, 0, 7); ctx.fill();
        ctx.textAlign = 'center'; ctx.textBaseline = 'bottom'; ctx.fillText(m.toFixed(3), x, Math.max(g.y0 + 10, yy - 4));
      }
    }
    ctx.restore();
    // signal scale label
    ctx.fillStyle = C.muted; ctx.textAlign = 'right'; ctx.textBaseline = 'top';
    ctx.font = '500 9.5px ' + getComputedStyle(document.body).getPropertyValue('--font-data');
    ctx.fillText(sigMax.toFixed(2), LEFT - 6, G.sig.y0 + 12);
    // time axis
    const axY = h - AXIS_H;
    ctx.strokeStyle = C.line; ctx.beginPath(); ctx.moveTo(LEFT, axY + 0.5); ctx.lineTo(w - 6, axY + 0.5); ctx.stroke();
    const span = (v1 - v0) * 1e3, raw = span / Math.max(2, plotW / 90), p10 = Math.pow(10, Math.floor(Math.log10(raw)));
    const stepMs = [1, 2, 5, 10].map(m => m * p10).find(s => s >= raw) || 10 * p10;
    ctx.fillStyle = C.muted; ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    const dec = stepMs < 0.01 ? 3 : stepMs < 0.1 ? 2 : stepMs < 1 ? 1 : 0;
    for (let tm = Math.ceil(v0 * 1e3 / stepMs) * stepMs; tm <= v1 * 1e3 + 1e-9; tm += stepMs) {
      const x = X(tm * 1e-3);
      ctx.beginPath(); ctx.moveTo(x, axY); ctx.lineTo(x, axY + 4); ctx.stroke();
      ctx.fillText(tm.toFixed(dec), x, axY + 5);
    }
    ctx.textAlign = 'left'; ctx.fillText('ms', 4, axY + 5);
    $('diagScale').textContent = `G full scale ${(gmax / GAMMA_HZ_PER_MT).toFixed(0)} mT/m · RF ${(rfmax / 42.577).toFixed(1)} µT · view ${span.toFixed(span < 10 ? 2 : 1)} ms`;
  }

  // diagram interaction
  function setupDiagram() {
    const cv = $('diag');
    let drag = null;
    const tAt = x => { const r = cv.getBoundingClientRect(), pw = r.width - LEFT - 6; return S.view[0] + (x - r.left - LEFT) / pw * (S.view[1] - S.view[0]); };
    cv.addEventListener('pointerdown', e => { drag = { x: e.clientX, v: S.view.slice(), moved: false }; cv.setPointerCapture(e.pointerId); });
    cv.addEventListener('pointermove', e => {
      if (drag) {
        const dx = e.clientX - drag.x;
        if (Math.abs(dx) > 3) drag.moved = true;
        if (drag.moved) {
          const r = cv.getBoundingClientRect(), dt = dx / (r.width - LEFT - 6) * (drag.v[1] - drag.v[0]);
          S.view = [drag.v[0] - dt, drag.v[1] - dt]; clampView(); S.dirtyStatic = true; requestRender();
        }
      }
      showTip(e);
    });
    cv.addEventListener('pointerup', e => {
      if (drag && !drag.moved) setTime(tAt(e.clientX));
      drag = null;
    });
    cv.addEventListener('pointerleave', () => { $('tip').hidden = true; });
    cv.addEventListener('wheel', e => {
      e.preventDefault();
      const t = tAt(e.clientX), f = Math.exp((e.deltaY || e.deltaX) * 0.0015);
      S.view = [t - (t - S.view[0]) * f, t + (S.view[1] - t) * f]; clampView(); S.dirtyStatic = true; requestRender();
    }, { passive: false });
    cv.addEventListener('dblclick', () => { if (S.sim) { S.view = [S.sim.tStart, S.sim.tEnd]; S.dirtyStatic = true; requestRender(); } });
    function showTip(e) {
      if (!S.seq || drag && drag.moved) { $('tip').hidden = true; return; }
      const r = cv.getBoundingClientRect(), t = tAt(e.clientX);
      if (e.clientX - r.left < LEFT) { $('tip').hidden = true; return; }
      const bi = E.blockAt(S.seq.blocks, t), b = S.seq.blocks[bi];
      const lines = [`t ${fmtMs(t)} · block ${b.index}`];
      blockSummary(b).forEach(s => lines.push(s));
      const tip = $('tip'); tip.textContent = lines.join('\n'); tip.hidden = false;
      const pr = cv.parentElement.getBoundingClientRect();
      let x = e.clientX - pr.left + 14; if (x + tip.offsetWidth > pr.width - 4) x = e.clientX - pr.left - tip.offsetWidth - 14;
      tip.style.left = Math.max(4, x) + 'px'; tip.style.top = Math.max(4, e.clientY - pr.top - 10) + 'px';
    }
  }
  function lobeText(ax, ch) {
    const L = S.P.thk > 0 ? S.P.thk : null, a = ch.area / 1e3; // cycles/mm
    let s = `G${'xyz'[ax]} area ${a.toFixed(2)} turns/mm, peak ${(ch.amax / GAMMA_HZ_PER_MT).toFixed(1)} mT/m`;
    if (ax === 2 && L) s += ` (${(a * L).toFixed(2)} turns across the slice)`;
    if (ax < 2 && S.P.voxXY > 0) s += ` (${(a * S.P.voxXY).toFixed(1)} turns across the voxel)`;
    return s;
  }
  function blockSummary(b) {
    const out = [];
    if (b.rf) out.push(`RF ${b.rfNo} ${useName(b.rf.use)}: ${(b.rf.flipDeg).toFixed(0)}° about ${axisName(b.rf.axisPhase)}, ${(b.rf.dur * 1e3).toFixed(2)} ms, BW ≈ ${b.rf.bw.toFixed(0)} Hz`);
    b.g.forEach((ch, ax) => { if (ch) out.push(lobeText(ax, ch)); });
    if (b.adc) out.push(`ADC ${b.adcNo}: ${b.adc.num} samples × ${(b.adc.dwell * 1e6).toFixed(0)} µs`);
    if (!out.length) out.push('delay (free precession)');
    return out;
  }

  // ---- narration
  function describeNow() {
    if (!S.sim || !curState) { $('nowText').textContent = S.seq ? 'Simulating…' : '—'; $('meters').innerHTML = ''; return; }
    const sim = S.sim, t = S.t, bi = E.blockAt(sim.blocks, t), b = sim.blocks[bi], tau = t - b.start;
    const parts = [];
    if (b.rf && tau >= b.rf.delay && tau <= b.rf.delay + b.rf.dur) {
      const pct = (tau - b.rf.delay) / b.rf.dur * 100;
      parts.push(`<b>RF ${b.rfNo} playing</b> (${useName(b.rf.use)}): ${(b.rf.flipDeg * S.P.b1).toFixed(0)}° about ${axisName(b.rf.axisPhase)}, ${pct.toFixed(0)} % through.`);
    } else if (b.rf) parts.push(tau < b.rf.delay ? `Block ${b.index}: RF ${b.rfNo} starts in ${((b.rf.delay - tau) * 1e3).toFixed(2)} ms.` : `Block ${b.index}: RF ${b.rfNo} finished ${((tau - b.rf.delay - b.rf.dur) * 1e3).toFixed(2)} ms ago.`);
    const active = [];
    b.g.forEach((ch, ax) => { if (ch) { const g = E.gval(ch, tau); if (Math.abs(g) > 1) active.push(`G${'xyz'[ax]} ${(g / GAMMA_HZ_PER_MT).toFixed(1)} mT/m`); } });
    if (active.length) parts.push('Gradient on: ' + active.join(', ') + '.');
    const lobes = b.g.map((ch, ax) => ch ? lobeText(ax, ch) : null).filter(Boolean);
    if (lobes.length && !b.rf) parts.push('This block: ' + lobes.join('; ') + '.');
    else if (lobes.length && b.rf) parts.push('Block gradients: ' + lobes.join('; ') + '.');
    if (b.adc) {
      const a0 = b.adc.delay, a1 = a0 + b.adc.num * b.adc.dwell;
      parts.push(tau >= a0 && tau <= a1 ? `<b>ADC ${b.adcNo} sampling</b>.` : `ADC ${b.adcNo} in this block.`);
    }
    if (!parts.length) parts.push(`Block ${b.index}: free precession, no gradients. Only off-resonance and relaxation act.`);
    const mbi = sim.p.motionAfterBlock;
    if (mbi >= 0 && bi === mbi + 1 && tau < 0.3e-3) parts.push('<b>Motion phase was just added.</b>');
    $('nowText').innerHTML = parts.join(' ');
    // meters
    const st = curState, ens = sim.ens;
    let sx = 0, sy = 0, ix = 0, iy = 0, iz = 0;
    for (let i = 0; i < ens.N; i++) { sx += st.mx[i]; sy += st.my[i]; if (ens.inSlice[i]) { iz += st.mz[i]; } }
    sx /= ens.nin; sy /= ens.nin; iz /= ens.nin;
    const mag = Math.hypot(sx, sy), ph = Math.atan2(sy, sx) * DEG;
    $('meters').innerHTML = `<span>|S| <b>${mag.toFixed(3)}</b></span><span>∠S <b>${ph.toFixed(0)}°</b></span><span>Mz (slice) <b>${iz.toFixed(3)}</b></span>`;
  }

  // ---- 3D sphere
  function camProj(w, h) {
    const { az, el, zoom } = S.cam, ca = Math.cos(az), sa = Math.sin(az), ce = Math.cos(el), se = Math.sin(el);
    const R = Math.min(w, h) * 0.36 * zoom, cx = w / 2, cy = h / 2 + 6;
    return (x, y, z) => {
      const X = x * ca - y * sa, Yd = x * sa + y * ca;
      const Y = z * ce + Yd * se, D = Yd * ce - z * se;
      const p = 1 / (1 + D * 0.12);
      return [cx + X * R * p, cy - Y * R * p, D];
    };
  }
  function selectedVectors() {
    const sim = S.sim, ens = sim.ens, st = curState, mode = $('sphMode').value, inOnly = $('inOnly').checked;
    const out = [];
    const L = ens.zSpan, colorBy = mode === 'z' ? 'z' : $('colorBy').value;
    const thk = ens.thk;
    const zcol = z => { const f = (z + L / 2) / L; const inside = !thk || Math.abs(z) <= thk / 2; return inside ? zColor(f) : rgba(C.muted, 0.55); };
    if (mode === 'z') {
      const n = ens.nz, mx = new Float64Array(n), my = new Float64Array(n), mz = new Float64Array(n);
      for (let i = 0; i < ens.N; i++) { const k = ens.zbin[i]; mx[k] += st.mx[i]; my[k] += st.my[i]; mz[k] += st.mz[i]; }
      for (let k = 0; k < n; k++) {
        const z = ens.zc[k];
        if (inOnly && thk && Math.abs(z) > thk / 2) continue;
        out.push({ v: [mx[k] / ens.nsub, my[k] / ens.nsub, mz[k] / ens.nsub], c: zcol(z), sel: k === S.selZ });
      }
    } else {
      const zsel = S.selZ === null ? Math.floor(ens.nz / 2) : S.selZ;
      let dfMax = 1; for (let i = 0; i < ens.N; i++) dfMax = Math.max(dfMax, Math.abs(ens.df[i] - S.P.b0));
      const stride = mode === 'spins' ? Math.max(1, Math.ceil(ens.N / 2500)) : 1;
      for (let i = 0; i < ens.N; i += stride) {
        if (mode === 'onez' && ens.zbin[i] !== zsel) continue;
        if (mode === 'spins' && inOnly && !ens.inSlice[i]) continue;
        let c;
        if (colorBy === 'z') c = zcol(ens.z[i]);
        else if (colorBy === 'df') c = divColor((ens.df[i] - S.P.b0) / Math.min(dfMax, 3 / (2 * Math.PI * Math.max(1e-3, S.P.t2p * 1e-3))));
        else if (colorBy === 'b1') c = divColor(S.P.b1Spread ? (ens.b1[i] / S.P.b1 - 1) / (S.P.b1Spread / 100) : 0);
        else c = `hsl(${(ens.mphase[i] * DEG % 360 + 360) % 360},62%,52%)`;
        out.push({ v: [st.mx[i], st.my[i], st.mz[i]], c });
      }
    }
    return out;
  }
  function drawSphere() {
    const cv = $('sphere'), { ctx, w, h } = fitCanvas(cv);
    ctx.clearRect(0, 0, w, h);
    const P = camProj(w, h);
    const fontD = getComputedStyle(document.body).getPropertyValue('--font-data');
    // wireframe
    const circle = (f, back) => {
      ctx.beginPath();
      let pen = false;
      for (let k = 0; k <= 96; k++) {
        const a = k / 96 * Math.PI * 2, [x, y, d] = P(...f(a));
        if ((d > 0) !== back) { pen = false; continue; }
        if (!pen) { ctx.moveTo(x, y); pen = true; } else ctx.lineTo(x, y);
      }
      ctx.stroke();
    };
    const rings = [a => [Math.cos(a), Math.sin(a), 0], a => [Math.cos(a), 0, Math.sin(a)], a => [0, Math.cos(a), Math.sin(a)]];
    ctx.lineWidth = 1;
    ctx.strokeStyle = rgba(C.muted, 0.18); rings.forEach(f => circle(f, true));
    ctx.strokeStyle = rgba(C.muted, 0.45); rings.forEach(f => circle(f, false));
    // axes
    const axes = [[[1.18, 0, 0], 'x′', C.gx], [[0, 1.18, 0], 'y′', C.gy], [[0, 0, 1.18], 'z', C.gz]];
    const o = P(0, 0, 0);
    ctx.font = '600 13px ' + fontD; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    for (const [v, name, col] of axes) {
      const n = P(-v[0], -v[1], -v[2]), p = P(...v);
      ctx.strokeStyle = rgba(C.muted, 0.35); ctx.setLineDash([3, 3]); ctx.beginPath(); ctx.moveTo(o[0], o[1]); ctx.lineTo(n[0], n[1]); ctx.stroke(); ctx.setLineDash([]);
      ctx.strokeStyle = col; ctx.lineWidth = 1.4; ctx.beginPath(); ctx.moveTo(o[0], o[1]); ctx.lineTo(p[0], p[1]); ctx.stroke(); ctx.lineWidth = 1;
      const q = P(v[0] * 1.1, v[1] * 1.1, v[2] * 1.1); ctx.fillStyle = col; ctx.fillText(name, q[0], q[1]);
    }
    if (!S.sim || !curState) return;
    const vecs = selectedVectors();
    const thin = vecs.length > 400;
    ctx.lineWidth = thin ? 0.8 : 1.6;
    for (const it of vecs) {
      const p = P(...it.v);
      ctx.strokeStyle = it.c; ctx.globalAlpha = thin ? 0.35 : 0.85;
      ctx.beginPath(); ctx.moveTo(o[0], o[1]); ctx.lineTo(p[0], p[1]); ctx.stroke();
      ctx.globalAlpha = 1; ctx.fillStyle = it.c;
      ctx.beginPath(); ctx.arc(p[0], p[1], thin ? 1.6 : 2.6, 0, 7); ctx.fill();
      if (it.sel) { ctx.strokeStyle = C.ink; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(p[0], p[1], 5, 0, 7); ctx.stroke(); ctx.lineWidth = thin ? 0.8 : 1.6; }
    }
    // trail of the in-slice net vector
    const tr = S.sim.trace;
    if ($('showTrail').checked && tr) {
      const tw = 8e-3;
      ctx.strokeStyle = C.ink; ctx.lineWidth = 1.2;
      let i0 = 0; while (i0 < tr.t.length && tr.t[i0] < S.t - tw) i0++;
      let prev = null;
      for (let i = i0; i < tr.t.length && tr.t[i] <= S.t; i++) {
        const p = P(tr.ix[i], tr.iy[i], tr.iz[i]);
        if (prev) { ctx.globalAlpha = 0.15 + 0.6 * (1 - (S.t - tr.t[i]) / tw); ctx.beginPath(); ctx.moveTo(prev[0], prev[1]); ctx.lineTo(p[0], p[1]); ctx.stroke(); }
        prev = p;
      }
      ctx.globalAlpha = 1;
    }
    // net vector (in-slice mean)
    const ens = S.sim.ens, st = curState;
    let nx = 0, ny = 0, nz = 0;
    for (let i = 0; i < ens.N; i++) if (ens.inSlice[i]) { nx += st.mx[i]; ny += st.my[i]; nz += st.mz[i]; }
    nx /= ens.nin; ny /= ens.nin; nz /= ens.nin;
    if ($('showNet').checked) {
      const p = P(nx, ny, nz), pxy = P(nx, ny, 0);
      ctx.strokeStyle = rgba(C.ink, 0.45); ctx.setLineDash([2, 3]); ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(p[0], p[1]); ctx.lineTo(pxy[0], pxy[1]); ctx.lineTo(o[0], o[1]); ctx.stroke(); ctx.setLineDash([]);
      ctx.strokeStyle = C.ink; ctx.lineWidth = 3.2; ctx.beginPath(); ctx.moveTo(o[0], o[1]); ctx.lineTo(p[0], p[1]); ctx.stroke();
      const ang = Math.atan2(p[1] - o[1], p[0] - o[0]), L = Math.hypot(p[0] - o[0], p[1] - o[1]);
      if (L > 8) { ctx.fillStyle = C.ink; ctx.beginPath(); ctx.moveTo(p[0], p[1]); ctx.lineTo(p[0] - 10 * Math.cos(ang - 0.4), p[1] - 10 * Math.sin(ang - 0.4)); ctx.lineTo(p[0] - 10 * Math.cos(ang + 0.4), p[1] - 10 * Math.sin(ang + 0.4)); ctx.fill(); }
    }
    ctx.font = '500 11.5px ' + fontD; ctx.textAlign = 'left'; ctx.textBaseline = 'top'; ctx.fillStyle = C.muted;
    ctx.fillText(`t ${fmtMs(S.t)}`, 10, 8);
    ctx.fillText(`net M (slice) = (${nx.toFixed(2)}, ${ny.toFixed(2)}, ${nz.toFixed(2)})`, 10, 24);
    const mode = $('sphMode').value;
    $('sphFoot').textContent = mode === 'z'
      ? `${vecs.length} vectors, one per z position, each the coherent mean of ${ens.nsub} isochromats. Colour runs along z (blue = −z edge, orange = +z edge); grey is outside the nominal slice. Bold = mean over the slice.`
      : mode === 'spins' ? `${vecs.length} individual isochromats. Their spread shows dephasing in x, y and off-resonance that the z-averaged view hides.`
      : `Isochromats at z = ${((ens.zc[S.selZ === null ? Math.floor(ens.nz / 2) : S.selZ]) * 1e3).toFixed(3)} mm (click a position in Profile vs z to change it).`;
  }
  function setupSphere() {
    const cv = $('sphere'); let drag = null;
    cv.addEventListener('pointerdown', e => { drag = { x: e.clientX, y: e.clientY, az: S.cam.az, el: S.cam.el }; cv.setPointerCapture(e.pointerId); cv.style.cursor = 'grabbing'; });
    cv.addEventListener('pointermove', e => {
      if (!drag) return;
      S.cam.az = drag.az - (e.clientX - drag.x) * 0.01;
      S.cam.el = Math.max(-1.55, Math.min(1.55, drag.el + (e.clientY - drag.y) * 0.01));
      requestRender();
    });
    cv.addEventListener('pointerup', () => { drag = null; cv.style.cursor = ''; });
    cv.addEventListener('wheel', e => { e.preventDefault(); S.cam.zoom = Math.max(0.5, Math.min(3, S.cam.zoom * Math.exp(-e.deltaY * 0.0012))); requestRender(); }, { passive: false });
    document.querySelectorAll('[data-cam]').forEach(b => b.addEventListener('click', () => {
      const v = b.dataset.cam;
      if (v === 'iso') Object.assign(S.cam, { az: -2.2, el: 0.42 });
      if (v === 'top') Object.assign(S.cam, { az: -Math.PI / 2, el: Math.PI / 2 - 0.001 });
      if (v === 'side') Object.assign(S.cam, { az: -Math.PI / 2, el: 0 });
      requestRender();
    }));
  }

  // ---- plots
  let plotGeom = null;
  function drawPlot() {
    const cv = $('plot'), { ctx, w, h } = fitCanvas(cv);
    ctx.clearRect(0, 0, w, h);
    const tools = $('tabTools');
    if (S.tab === 'echo') { if (!tools.dataset.echo) { tools.innerHTML = '<button class="btn small" id="pinBtn">Pin this run</button><button class="btn small" id="sweepBtn" title="8 runs with a coherent motion phase 0°–315°">Sweep φ</button><button class="btn small" id="clearPins">Clear pins</button>'; tools.dataset.echo = '1'; } }
    else if (tools.dataset.echo) { tools.innerHTML = ''; delete tools.dataset.echo; }
    if (!S.sim || !curState) return;
    if (S.tab === 'profile') drawProfile(ctx, w, h);
    else if (S.tab === 'spec') drawSpectrum(ctx, w, h);
    else drawEchoes(ctx, w, h);
  }
  function frame(ctx, x0, y0, x1, y1) { ctx.strokeStyle = C.line; ctx.lineWidth = 1; ctx.strokeRect(x0 + 0.5, y0 + 0.5, x1 - x0, y1 - y0); }
  function fontD() { return getComputedStyle(document.body).getPropertyValue('--font-data'); }
  function drawProfile(ctx, w, h) {
    const ens = S.sim.ens, st = curState, n = ens.nz;
    const mx = new Float64Array(n), my = new Float64Array(n), mz = new Float64Array(n);
    for (let i = 0; i < ens.N; i++) { const k = ens.zbin[i]; mx[k] += st.mx[i]; my[k] += st.my[i]; mz[k] += st.mz[i]; }
    for (let k = 0; k < n; k++) { mx[k] /= ens.nsub; my[k] /= ens.nsub; mz[k] /= ens.nsub; }
    const x0 = 44, x1 = w - 12, y0 = 26, y1 = h - 30;
    const L = ens.zSpan, X = z => x0 + (z + L / 2) / L * (x1 - x0), Y = v => y0 + (1 - (v + 1.05) / 2.1) * (y1 - y0);
    plotGeom = { x0, x1, L };
    if (ens.thk) { ctx.fillStyle = rgba(C.accent, 0.08); ctx.fillRect(X(-ens.thk / 2), y0, X(ens.thk / 2) - X(-ens.thk / 2), y1 - y0); }
    frame(ctx, x0, y0, x1, y1);
    ctx.font = '500 10.5px ' + fontD(); ctx.fillStyle = C.muted; ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    for (const v of [-1, -0.5, 0, 0.5, 1]) { ctx.fillText(v.toFixed(1), x0 - 6, Y(v)); ctx.strokeStyle = rgba(C.line, v === 0 ? 1 : 0.5); ctx.beginPath(); ctx.moveTo(x0, Y(v) + 0.5); ctx.lineTo(x1, Y(v) + 0.5); ctx.stroke(); }
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    const zt = L * 1e3 > 3 ? 1 : L * 1e3 > 1.2 ? 0.5 : 0.25;
    for (let z = Math.ceil(-L * 1e3 / 2 / zt) * zt; z <= L * 1e3 / 2 + 1e-9; z += zt) ctx.fillText(z.toFixed(2), X(z * 1e-3), y1 + 4);
    ctx.fillText('z (mm)', (x0 + x1) / 2, y1 + 16);
    const line = (arr, col, dash, lw) => { ctx.strokeStyle = col; ctx.lineWidth = lw || 1.6; ctx.setLineDash(dash || []); ctx.beginPath(); for (let k = 0; k < n; k++) { const x = X(ens.zc[k]), y = Y(arr[k]); k ? ctx.lineTo(x, y) : ctx.moveTo(x, y); } ctx.stroke(); ctx.setLineDash([]); };
    const mag = Float64Array.from(mx, (v, k) => Math.hypot(v, my[k]));
    line(mag, rgba(C.ink, 0.5), [4, 3], 1.2);
    line(mz, C.gz); line(my, C.gy); line(mx, C.gx);
    if (S.selZ !== null) { const x = X(ens.zc[S.selZ]); ctx.strokeStyle = C.ink; ctx.setLineDash([2, 2]); ctx.beginPath(); ctx.moveTo(x, y0); ctx.lineTo(x, y1); ctx.stroke(); ctx.setLineDash([]); }
    // legend
    ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.font = '600 11.5px ' + fontD();
    let lx = x0 + 4;
    for (const [lab, col] of [['Mx', C.gx], ['My', C.gy], ['Mz', C.gz], ['|Mxy|', C.muted]]) { ctx.fillStyle = col; ctx.fillRect(lx, 9, 14, 3); ctx.fillText(lab, lx + 18, 11); lx += 30 + ctx.measureText(lab).width; }
    $('plotFoot').textContent = 'Coherent mean of each z position over its isochromats. Shaded band: nominal slice. Click to pick a z for the 3D view.';
  }
  function drawSpectrum(ctx, w, h) {
    const ens = S.sim.ens, st = curState, K = 12, Lc = ens.L;
    const F = [], Z = [];
    for (let n = -K; n <= K; n++) {
      let fr = 0, fi = 0, zr = 0, zi = 0;
      for (let i = 0; i < ens.N; i++) {
        if (!ens.inSlice[i]) continue;
        const p = 2 * Math.PI * n * ens.z[i] / Lc, c = Math.cos(p), s = Math.sin(p);
        fr += st.mx[i] * c - st.my[i] * s; fi += st.mx[i] * s + st.my[i] * c;
        if (n >= 0) { zr += st.mz[i] * c; zi += st.mz[i] * s; }
      }
      F.push(Math.hypot(fr, fi) / ens.nin); if (n >= 0) Z.push(Math.hypot(zr, zi) / ens.nin);
    }
    const x0 = 44, x1 = w - 12, mid = h * 0.52;
    const drawBars = (vals, ns, ya, yb, col, title) => {
      frame(ctx, x0, ya, x1, yb);
      const bw = (x1 - x0) / (2 * K + 1), Y = v => yb - Math.min(1, v) * (yb - ya - 4);
      ctx.font = '500 10px ' + fontD(); ctx.fillStyle = C.muted; ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
      for (const v of [0, 0.5, 1]) { ctx.fillText(v.toFixed(1), x0 - 6, Y(v)); ctx.strokeStyle = rgba(C.line, 0.6); ctx.beginPath(); ctx.moveTo(x0, Y(v) + 0.5); ctx.lineTo(x1, Y(v) + 0.5); ctx.stroke(); }
      vals.forEach((v, j) => {
        const n = ns[j], x = x0 + (n + K) * bw;
        ctx.fillStyle = n === 0 && title.startsWith('F') ? C.accent : col;
        ctx.fillRect(x + bw * 0.15, Y(v), bw * 0.7, yb - Y(v));
      });
      ctx.textAlign = 'center'; ctx.textBaseline = 'top'; ctx.fillStyle = C.muted;
      for (let n = -K; n <= K; n += 2) ctx.fillText(String(n), x0 + (n + K + 0.5) * bw, yb + 3);
      ctx.textAlign = 'left'; ctx.fillStyle = C.ink; ctx.font = '600 11.5px ' + fontD(); ctx.fillText(title, x0 + 6, ya + 5);
    };
    drawBars(F, F.map((_, j) => j - K), 22, mid - 18, C.gx, 'F_n  transverse, wound n turns');
    drawBars(Z, Z.map((_, j) => j), mid + 8, h - 30, C.gz, 'Z_n  longitudinal pattern, n turns');
    ctx.fillStyle = C.muted; ctx.font = '500 10.5px ' + fontD(); ctx.textAlign = 'center'; ctx.fillText(`n = turns across ${ens.thk ? 'the slice' : 'the z range'} (${(Lc * 1e3).toFixed(2)} mm)`, (x0 + x1) / 2, h - 14);
    $('plotFoot').textContent = 'F0 (highlighted) is the only state that gives signal. Dephasing in x or y (readout, spoilers, diffusion lobes) does not show here; it removes amplitude from all bars.';
  }
  function echoLabel() {
    const it = S.item, P = S.P;
    const mot = P.motionMode === 'none' ? 'static' : P.motionMode === 'coherent' ? `φ ${P.motionDeg}°` : P.motionMode === 'uniform' ? 'intravoxel φ 0–360°' : `intravoxel σ ${P.motionDeg}°`;
    return `${it ? it.short : S.key} · B1 ${P.b1.toFixed(2)} · ${mot}${P.rfMode === 'ideal' ? ' · ideal RF' : ''}${P.b0 ? ` · B0 ${P.b0} Hz` : ''}`;
  }
  function drawEchoes(ctx, w, h) {
    const cur = { label: echoLabel() + ' (current)', vals: S.sim.echoes.map(e => Math.hypot(...e.value)), col: C.accent, cur: true };
    const runs = S.pins.map((p, i) => ({ label: p.label, vals: p.vals, lo: p.lo, hi: p.hi, col: C[PIN_COLORS[i % PIN_COLORS.length]] })).concat([cur]);
    const nmax = Math.max(1, ...runs.map(r => r.vals.length));
    if (!cur.vals.length && !S.pins.length) { ctx.fillStyle = C.muted; ctx.font = '13px ' + fontD(); ctx.fillText('No ADC in this window.', 20, 30); return; }
    const vmax = Math.max(0.1, ...runs.flatMap(r => r.hi || r.vals)) * 1.12;
    const legendH = 16 * runs.length + 6;
    const x0 = 48, x1 = w - 14, y0 = 14 + legendH, y1 = h - 34;
    const X = k => x0 + (nmax === 1 ? 0.5 : k / (nmax - 1)) * (x1 - x0 - 20) + 10, Y = v => y1 - v / vmax * (y1 - y0);
    frame(ctx, x0, y0, x1, y1);
    ctx.font = '500 10.5px ' + fontD(); ctx.fillStyle = C.muted; ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    const step = vmax > 0.6 ? 0.2 : vmax > 0.25 ? 0.1 : 0.05;
    for (let v = 0; v <= vmax + 1e-9; v += step) { ctx.fillText(v.toFixed(2), x0 - 6, Y(v)); ctx.strokeStyle = rgba(C.line, 0.6); ctx.beginPath(); ctx.moveTo(x0, Y(v) + 0.5); ctx.lineTo(x1, Y(v) + 0.5); ctx.stroke(); }
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    for (let k = 0; k < nmax; k++) ctx.fillText('E' + (k + 1), X(k), y1 + 4);
    ctx.fillText('echo (ADC centre sample), |S| relative to slice M0', (x0 + x1) / 2, y1 + 18);
    for (const r of runs) {
      if (r.lo) {
        ctx.fillStyle = rgba(r.col, 0.16); ctx.beginPath();
        r.hi.forEach((v, k) => k ? ctx.lineTo(X(k), Y(v)) : ctx.moveTo(X(k), Y(v)));
        for (let k = r.lo.length - 1; k >= 0; k--) ctx.lineTo(X(k), Y(r.lo[k]));
        ctx.closePath(); ctx.fill();
      }
      ctx.strokeStyle = r.col; ctx.fillStyle = r.col; ctx.lineWidth = r.cur ? 2.4 : 1.6;
      ctx.beginPath(); r.vals.forEach((v, k) => k ? ctx.lineTo(X(k), Y(v)) : ctx.moveTo(X(k), Y(v))); ctx.stroke();
      r.vals.forEach((v, k) => { ctx.beginPath(); ctx.arc(X(k), Y(v), r.cur ? 3.5 : 2.6, 0, 7); ctx.fill(); });
    }
    ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.font = '500 11.5px ' + fontD();
    runs.forEach((r, i) => { const y = 12 + i * 16; ctx.fillStyle = r.col; ctx.fillRect(x0, y - 2, 16, 4); ctx.fillStyle = C.ink; ctx.fillText(r.label, x0 + 22, y); });
    // current echo marker
    const bi = E.blockAt(S.sim.blocks, S.t), b = S.sim.blocks[bi];
    if (b && b.adcNo) { const k = b.adcNo - 1; ctx.strokeStyle = C.ink; ctx.setLineDash([2, 3]); ctx.beginPath(); ctx.moveTo(X(k), y0); ctx.lineTo(X(k), y1); ctx.stroke(); ctx.setLineDash([]); }
    $('plotFoot').textContent = cur.vals.length ? 'Current: ' + cur.vals.map(v => v.toFixed(3)).join('  ') : '';
  }
  function setupPlot() {
    $('plot').addEventListener('click', e => {
      if (S.tab !== 'profile' || !S.sim || !plotGeom) return;
      const r = $('plot').getBoundingClientRect(), x = e.clientX - r.left;
      const z = (x - plotGeom.x0) / (plotGeom.x1 - plotGeom.x0) * plotGeom.L - plotGeom.L / 2;
      const ens = S.sim.ens; let best = 0;
      for (let k = 0; k < ens.nz; k++) if (Math.abs(ens.zc[k] - z) < Math.abs(ens.zc[best] - z)) best = k;
      S.selZ = best; requestRender();
    });
    document.querySelectorAll('[data-tab]').forEach(b => b.addEventListener('click', () => {
      S.tab = b.dataset.tab;
      document.querySelectorAll('[data-tab]').forEach(x => x.setAttribute('aria-selected', String(x === b)));
      requestRender();
    }));
    $('tabTools').addEventListener('click', e => {
      if (e.target.id === 'pinBtn' && S.sim) { S.pins.push({ label: echoLabel(), vals: S.sim.echoes.map(x => Math.hypot(...x.value)) }); if (S.pins.length > 6) S.pins.shift(); requestRender(); }
      if (e.target.id === 'clearPins') { S.pins = []; requestRender(); }
      if (e.target.id === 'sweepBtn' && S.seq) {
        const id = ++S.runId;
        sweep(S.seq, S.P, S.item, () => id === S.runId).then(r => { if (!r) return; S.pins.push({ label: sweepLabel(S.item, S.key, S.P), ...r }); if (S.pins.length > 6) S.pins.shift(); S.runId++; setStatus('sweep pinned'); requestRender(); });
      }
    });
  }

  // ------------------------------------------------------------------ controls
  function buildControls() {
    const rail = $('rail');
    rail.innerHTML = PARAMS.map(g => `<fieldset><legend>${g.group}</legend>${g.items.map(ctlHtml).join('')}</fieldset>`).join('')
      + `<fieldset><legend>Reset</legend><button class="btn" id="resetPhys">Reset physics to defaults</button></fieldset>`;
    for (const g of PARAMS) for (const it of g.items) {
      const el = $('p-' + it.id);
      if (it.type === 'seg') {
        el.querySelectorAll('button').forEach(b => b.addEventListener('click', () => { S.P[it.id] = b.dataset.v; syncControls(); onParam(it.id); }));
        continue;
      }
      el.addEventListener(it.type === 'range' ? 'input' : 'change', () => {
        let v = el.value;
        if (it.type === 'range' || it.type === 'number') v = +v;
        if (it.type === 'select' && it.id === 'motionAfter') v = el.value;
        S.P[it.id] = v;
        syncControls();
        onParam(it.id);
      });
    }
    $('resetPhys').addEventListener('click', () => {
      for (const k of ['b1', 'b1Spread', 'b0', 'rfMode', 'motionMode', 'motionDeg', 'motionAfter', 'T1', 'T2']) S.P[k] = DEFAULTS[k];
      S.P.t2p = S.P.thk > 0 ? 30 : 3;
      syncControls(); S.dirtyStatic = true; scheduleSim();
    });
  }
  function ctlHtml(it) {
    const id = 'p-' + it.id;
    if (it.type === 'range') return `<div class="ctl"><label for="${id}">${it.label}</label><output id="${id}-o"></output><input type="range" id="${id}" min="${it.min}" max="${it.max}" step="${it.step}">${it.hint ? `<div class="hint">${it.hint}</div>` : ''}</div>`;
    if (it.type === 'select') return `<div class="ctl"><label for="${id}">${it.label}</label><span></span><select id="${id}">${it.options.map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select>${it.hint ? `<div class="hint">${it.hint}</div>` : ''}</div>`;
    if (it.type === 'number') return `<div class="ctl"><label for="${id}">${it.label} (${it.unit})</label><input type="number" id="${id}" min="${it.min}" step="${it.step}" style="width:96px"></div>`;
    if (it.type === 'seg') return `<div class="ctl"><span>${it.label}</span><span></span><div class="seg full" id="${id}" role="group" aria-label="${it.label}">${it.options.map(([v, l]) => `<button type="button" data-v="${v}">${l}</button>`).join('')}</div>${it.hint ? `<div class="hint">${it.hint}</div>` : ''}</div>`;
    return '';
  }
  function syncControls() {
    for (const g of PARAMS) for (const it of g.items) {
      const el = $('p-' + it.id), v = S.P[it.id];
      if (it.type === 'seg') { el.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.v === v))); continue; }
      if (document.activeElement !== el || it.type !== 'number') el.value = String(v);
      const o = $('p-' + it.id + '-o'); if (o && it.fmt) o.textContent = it.fmt(+v);
    }
    $('p-motionDeg').disabled = S.P.motionMode === 'none' || S.P.motionMode === 'uniform';
    $('p-motionAfter').disabled = S.P.motionMode === 'none';
  }
  function onParam(id) {
    if (id === 'tStart' || id === 'tEnd') {
      if (S.P.tEnd <= S.P.tStart + 1) S.P.tEnd = S.P.tStart + 1;
      S.P.tEnd = Math.min(S.P.tEnd, Math.ceil(S.seq.total * 1e3));
      buildMotionOptions();
      S.view = [S.P.tStart * 1e-3, S.P.tEnd * 1e-3];
      S.t = Math.max(S.t, S.P.tStart * 1e-3);
    }
    if (id === 'b1' || id === 'motionMode' || id === 'motionAfter') S.dirtyStatic = true;
    scheduleSim();
  }

  // ------------------------------------------------------------------ experiments
  const EXPERIMENTS = [
    { title: 'CPMG vs CP when the flip angle is wrong', text: 'B1 = 0.8. CP (pinned) collapses by echo 3; CPMG keeps echo 2 onwards. Watch the 3D view after each 180°.',
      seq: 'ex3_cpmg_train', params: { b1: 0.8, t2p: 3 }, pins: [{ seq: 'ex4_cp_train', params: { b1: 0.8, t2p: 3 } }], at: 'rf3.e', tab: 'echo' },
    { title: 'Crushers decide which echoes survive', text: 'B1 = 0.8. With equal crusher pairs (pinned) a stimulated echo appears at 66 ms; halving the first pair crushes it. Look at the |S| row.',
      seq: 'ex5_unequal_first_interval_b', params: { b1: 0.8, t2p: 3 }, pins: [{ seq: 'ex5_unequal_first_interval', params: { b1: 0.8, t2p: 3 } }], at: 'ms:66', tab: 'spec' },
    { title: 'Off-resonance is refocused, then lost again', text: 'Spin echo with a 50 Hz offset and a wide field spread: watch the fan open, flip and close.',
      seq: 'ex2_spin_echo', params: { b0: 50, t2p: 3 }, at: 'rf2.b', tab: 'profile', sph: 'spins', color: 'df' },
    { title: 'Motion phase turns DW-FSE into CP', text: 'Original sequence, B1 = 0.8. Pinned: no motion phase. Current: a coherent 90° phase after the diffusion lobes. The train oscillates and decays.',
      seq: 'original', params: { b1: 0.8, motionMode: 'coherent', motionDeg: 90 }, pins: [{ seq: 'original', params: { b1: 0.8, motionMode: 'none' } }], at: 'adc3', tab: 'echo' },
    { title: 'Original vs Alsop vs ss-MGOT over all motion phases', text: 'B1 = 0.8. Each band is 8 runs with a coherent motion phase from 0° to 315° (line = mean, band = min–max). The original train swings with φ; the prepared trains hardly move, at about half the height. Takes ~15 s.',
      seq: 'ss_mgot', params: { b1: 0.8, motionMode: 'coherent', motionDeg: 90 }, pins: [{ seq: 'original', sweep: true, params: { b1: 0.8 } }, { seq: 'alsop', sweep: true, params: { b1: 0.8 } }, { seq: 'ss_mgot', sweep: true, params: { b1: 0.8 } }], at: 'b15.e', tab: 'echo' },
    { title: 'How Alsop keeps half: the helix and the tip pulse', text: 'Coherent 60° motion phase. Step from the helix (after block 11) across the 90°(−y′) pulse and watch Mx turn into Mz in Profile vs z.',
      seq: 'alsop', params: { motionMode: 'coherent', motionDeg: 60 }, at: 'b11.e', tab: 'profile' },
    { title: 'Real slice profile vs ideal pulses', text: 'Pinned: ideal instantaneous pulses with rectangular slabs. Current: the file’s sinc pulses. Compare echo heights and the profile at echo 1.',
      seq: 'centered_original', params: { rfMode: 'finite' }, pins: [{ seq: 'centered_original', params: { rfMode: 'ideal' } }], at: 'adc1', tab: 'profile' },
    { title: 'Crusher schedules across motion phases', text: 'B1 = 0.8. φ-sweep bands for constant, alternating and increasing crushers: which schedule keeps the train least dependent on the motion phase? Takes ~15 s.',
      seq: 'increasing', params: { b1: 0.8, motionMode: 'coherent', motionDeg: 90 }, pins: [{ seq: 'original', sweep: true, params: { b1: 0.8 } }, { seq: 'alternating', sweep: true, params: { b1: 0.8 } }, { seq: 'increasing', sweep: true, params: { b1: 0.8 } }], at: 'adc8', tab: 'echo' },
    { title: 'Diffusion attenuation: phase spread inside the voxel', text: 'Gaussian motion phase per isochromat, σ = 60°. Every sequence loses the same fraction (about e^(−σ²/2)); the preparations do not help here. Compare with σ = 0 (pinned).',
      seq: 'alsop', params: { motionMode: 'gauss', motionDeg: 60 }, pins: [{ seq: 'alsop', params: { motionMode: 'none' } }], at: 'adc1', tab: 'echo' },
  ];
  function buildExperiments() {
    $('experiments').innerHTML = EXPERIMENTS.map((x, i) => `<button data-exp="${i}"><b>${x.title}</b><span>${x.text}</span></button>`).join('');
    $('experiments').addEventListener('click', async e => {
      const btn = e.target.closest('[data-exp]'); if (!btn) return;
      const x = EXPERIMENTS[+btn.dataset.exp];
      S.pins = [];
      const myRun = ++S.runId;
      for (const p of x.pins || []) {
        const seq = E.parseSeq(seqText(p.seq));
        const P = paramsFor(seq, p.params);
        setStatus('simulating reference…', true);
        const prev = { P: S.P, item: S.item, key: S.key };
        if (p.sweep) {
          const r = await sweep(seq, P, ITEMS[p.seq], () => myRun === S.runId);
          if (!r) return;
          S.pins.push({ label: sweepLabel(ITEMS[p.seq], p.seq, P), ...r });
          continue;
        }
        const sim = await simulate(seq, P, ITEMS[p.seq], null, () => myRun === S.runId);
        if (!sim) return;
        S.P = P; S.item = ITEMS[p.seq]; S.key = p.seq;
        S.pins.push({ label: echoLabel(), vals: sim.echoes.map(v => Math.hypot(...v.value)) });
        Object.assign(S, prev);
      }
      S.pendingAt = x.at;
      loadSequence(x.seq, { resetPhysics: true, params: x.params, quiet: true, keepNote: true });
      showNote(`<b>${x.title}.</b> ${x.text}`);
      if (x.tab) document.querySelector(`[data-tab="${x.tab}"]`).click();
      $('sphMode').value = x.sph || 'z';
      $('colorBy').value = x.color || 'z';
      window.scrollTo({ top: 0, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
    });
  }
  function paramsFor(seq, over) {
    const thk = estimateThickness(seq), P = Object.assign({}, DEFAULTS);
    P.thk = thk ? +(thk * 1e3).toFixed(2) : 0;
    P.zSpan = thk ? +Math.min(6, Math.max(0.5, 2 * thk * 1e3)).toFixed(1) : 2;
    P.t2p = thk ? 30 : 3;
    P.tEnd = Math.ceil(Math.min(seq.lastActive + 0.5e-3, seq.total, 0.6) * 1e3);
    return Object.assign(P, over || {});
  }

  // ------------------------------------------------------------------ setup
  function buildSelect() {
    const sel = $('seqSelect');
    let html = CATALOG.map(g => `<optgroup label="${g.group}">${g.items.map(it => `<option value="${it.key}">${it.title}</option>`).join('')}</optgroup>`).join('');
    const up = Object.keys(S.uploaded);
    if (up.length) html += `<optgroup label="Loaded files">${up.map(k => `<option value="${k}">${k}</option>`).join('')}</optgroup>`;
    sel.innerHTML = html;
  }
  function setup() {
    readColors();
    buildSelect();
    buildControls();
    buildExperiments();
    setupDiagram(); setupSphere(); setupPlot();
    $('seqSelect').addEventListener('change', e => loadSequence(e.target.value));
    $('fileIn').addEventListener('change', e => {
      const f = e.target.files[0]; if (!f) return;
      const rd = new FileReader();
      rd.onload = () => { S.uploaded[f.name] = String(rd.result); buildSelect(); loadSequence(f.name); };
      rd.readAsText(f);
      e.target.value = '';
    });
    $('time').addEventListener('input', e => { if (S.sim) setTime(S.sim.tStart + (+e.target.value / 4000) * (S.sim.tEnd - S.sim.tStart), true); });
    $('play').addEventListener('click', () => togglePlay());
    $('prevEv').addEventListener('click', () => stepEvent(-1));
    $('nextEv').addEventListener('click', () => stepEvent(1));
    ['sphMode', 'colorBy', 'inOnly', 'showNet', 'showTrail'].forEach(id => $(id).addEventListener('change', requestRender));
    $('bookmarks').addEventListener('click', e => {
      const b = e.target.closest('[data-mark]'); if (!b || !S.item) return;
      const m = S.item.marks[+b.dataset.mark];
      gotoRef(m[0]); showNote(`<b>${m[1]}.</b> ${m[2]}`);
      document.querySelectorAll('#bookmarks .chip').forEach(c => c.classList.toggle('on', c === b));
    });
    $('eventChips').addEventListener('click', e => { const b = e.target.closest('[data-ref]'); if (b) gotoRef(b.dataset.ref); });
    document.addEventListener('keydown', e => {
      if (e.target.closest('input[type="number"], select, input[type="text"]')) return;
      if (e.key === ' ' && !e.target.closest('button')) { e.preventDefault(); togglePlay(); }
      else if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        if (e.target.closest('input[type="range"]') && e.target.id !== 'time') return;
        e.preventDefault(); setTime(S.t + (e.key === 'ArrowRight' ? 1 : -1) * (e.shiftKey ? 1e-3 : 5e-5), true);
      }
      else if (e.key === ']') stepEvent(1);
      else if (e.key === '[') stepEvent(-1);
    });
    const ro = new ResizeObserver(() => { S.dirtyStatic = true; requestRender(); });
    ['diag', 'sphere', 'plot'].forEach(id => ro.observe($(id)));
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { readColors(); requestRender(); });
    new MutationObserver(() => { readColors(); requestRender(); }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { S.dirtyStatic = true; requestRender(); });
    S.pendingAt = 'b11.e';
    loadSequence('alsop', { resetPhysics: true, params: { motionMode: 'coherent', motionDeg: 60 }, quiet: true });
    S.tab = 'profile';
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', setup); else setup();
})();
