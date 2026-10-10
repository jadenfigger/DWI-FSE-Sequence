/* Spin explorer engine: Pulseq .seq parser + Bloch simulator of an isochromat ensemble.
 *
 * Conventions match dwfse/simulate.py:
 *   - rotating frame at the RF carrier; units Hz (RF, off-resonance) and Hz/m (gradients)
 *   - an RF field B = (B1x, B1y, Bz) rotates M by -2*pi*|B|*dt about B
 *     (so a 90 deg pulse with phase 0 takes +z to +y, free precession is Mxy*exp(-i*phi))
 *   - RF blocks are time-stepped with exact-area step averages; everything else is exact.
 * Works in the browser (window.SpinEngine) and in node (module.exports).
 */
(function (root) {
  'use strict';
  const TWO_PI = 2 * Math.PI;

  // ------------------------------------------------------------------ parser
  function decompress(shape) {
    const c = shape.data, n = shape.n;
    if (c.length === n) return Float64Array.from(c);
    const w = new Float64Array(n);
    let i = 0, j = 0;
    while (i < c.length && j < n) {
      if (i + 2 < c.length && c[i] === c[i + 1]) {
        const rep = Math.round(c[i + 2]) + 2;
        for (let r = 0; r < rep && j < n; r++) w[j++] = c[i];
        i += 3;
      } else { w[j++] = c[i]; i += 1; }
    }
    for (let k = 1; k < n; k++) w[k] += w[k - 1];
    return w;
  }

  function parseSeq(text) {
    const S = {}, shapes = {}, defs = {}, version = { major: 1, minor: 4, revision: 0 };
    let sec = null, cur = null;
    for (const raw of text.split(/\r?\n/)) {
      const line = raw.replace(/#.*$/, '').trim();
      if (!line) continue;
      if (line[0] === '[') { sec = line.replace(/[\[\]]/g, '').trim().toUpperCase(); continue; }
      if (sec === 'SIGNATURE' || sec === 'EXTENSIONS') continue;
      if (sec === 'VERSION') { const p = line.split(/\s+/); version[p[0]] = +p[1]; continue; }
      if (sec === 'DEFINITIONS') { const m = line.match(/^(\S+)\s*(.*)$/); if (m) defs[m[1]] = m[2].trim(); continue; }
      if (sec === 'SHAPES') {
        let m;
        if ((m = line.match(/^shape_id\s+(\d+)/))) { cur = { n: 0, data: [] }; shapes[+m[1]] = cur; continue; }
        if ((m = line.match(/^num_samples\s+(\d+)/))) { cur.n = +m[1]; continue; }
        if (cur) cur.data.push(parseFloat(line));
        continue;
      }
      if (!sec) continue;
      (S[sec] = S[sec] || []).push(line.split(/\s+/));
    }
    if (!S.BLOCKS) throw new Error('No [BLOCKS] section found: is this a Pulseq .seq file?');
    const num = v => +v;
    const shapeCache = {};
    const shape = id => (shapeCache[id] = shapeCache[id] || (shapes[id] ? decompress(shapes[id]) : null));
    const defNum = (k, d) => (defs[k] !== undefined && !isNaN(parseFloat(defs[k])) ? parseFloat(defs[k]) : d);
    const gradRaster = defNum('GradientRasterTime', 10e-6);
    const rfRaster = defNum('RadiofrequencyRasterTime', 1e-6);
    const blockRaster = defNum('BlockDurationRaster', 10e-6);
    const legacyBlocks = version.major === 1 && version.minor < 4;

    // RF events
    const rfs = {};
    for (const r of S.RF || []) {
      const v = r.map(num), id = v[0];
      let o;
      if (r.length >= 12) o = { amp: v[1], mag: v[2], ph: v[3], time: v[4], center: v[5] * 1e-6, delay: v[6] * 1e-6, freq: v[9], phase: v[10], use: r[11] };
      else if (r.length >= 8) o = { amp: v[1], mag: v[2], ph: v[3], time: v[4], center: null, delay: v[5] * 1e-6, freq: v[6], phase: v[7], use: '' };
      else o = { amp: v[1], mag: v[2], ph: v[3], time: 0, center: null, delay: v[4] * 1e-6, freq: v[5], phase: v[6], use: '' };
      const mag = shape(o.mag), ph = shape(o.ph);
      const n = mag.length;
      const re = new Float64Array(n), im = new Float64Array(n);
      for (let k = 0; k < n; k++) {
        const a = o.amp * mag[k], p = TWO_PI * (ph ? ph[k] : 0);
        re[k] = a * Math.cos(p); im[k] = a * Math.sin(p);
      }
      // cumulative complex area on "edges" (exact-area convention of dwfse/simulate.py)
      let edges, cre, cim;
      if (o.time) {
        const ts = shape(o.time);
        edges = Float64Array.from(ts, x => x * rfRaster);
        cre = new Float64Array(n); cim = new Float64Array(n);
        for (let k = 1; k < n; k++) {
          const d = edges[k] - edges[k - 1];
          cre[k] = cre[k - 1] + d * (re[k] + re[k - 1]) / 2;
          cim[k] = cim[k - 1] + d * (im[k] + im[k - 1]) / 2;
        }
      } else {
        edges = new Float64Array(n + 1); cre = new Float64Array(n + 1); cim = new Float64Array(n + 1);
        for (let k = 0; k <= n; k++) edges[k] = k * rfRaster;
        for (let k = 1; k <= n; k++) { cre[k] = cre[k - 1] + re[k - 1] * rfRaster; cim[k] = cim[k - 1] + im[k - 1] * rfRaster; }
      }
      o.edges = edges; o.cre = cre; o.cim = cim;
      o.dur = edges[edges.length - 1];
      // samples for drawing: (t, |B1|, phase)
      o.drawT = o.time ? edges : Float64Array.from({ length: n }, (_, k) => (k + 0.5) * rfRaster);
      o.drawRe = re; o.drawIm = im;
      if (o.center === null) {
        let best = 0, kb = 0;
        for (let k = 0; k < n; k++) { const a = re[k] * re[k] + im[k] * im[k]; if (a > best) { best = a; kb = k; } }
        o.center = o.drawT[kb];
      }
      const are = cre[cre.length - 1], aim = cim[cim.length - 1];
      o.flipDeg = 360 * Math.hypot(are, aim);           // nominal flip angle (B1 = 1)
      o.axisPhase = Math.atan2(aim, are) + o.phase;       // effective rotation axis phase
      o.bw = estimateBandwidth(o);
      rfs[id] = o;
    }

    // gradient events -> piecewise linear (t relative to block start, amplitude Hz/m)
    const grads = {};
    for (const r of S.GRADIENTS || []) {
      const v = r.map(num), id = v[0];
      let amp, first = null, last = null, sid, tid, delay;
      if (r.length >= 7) { amp = v[1]; first = v[2]; last = v[3]; sid = v[4]; tid = v[5]; delay = v[6]; }
      else if (r.length >= 5) { amp = v[1]; sid = v[2]; tid = v[3]; delay = v[4]; }
      else { amp = v[1]; sid = v[2]; tid = 0; delay = v[3]; }
      delay *= 1e-6;
      const s = shape(sid);
      let t, a;
      if (tid) {
        const ts = shape(tid);
        t = Float64Array.from(ts, x => delay + x * gradRaster);
        a = Float64Array.from(s, x => amp * x);
      } else {
        const n = s.length;
        t = new Float64Array(n + 2); a = new Float64Array(n + 2);
        t[0] = delay; a[0] = amp * (first !== null ? first : s[0]);
        for (let k = 0; k < n; k++) { t[k + 1] = delay + (k + 0.5) * gradRaster; a[k + 1] = amp * s[k]; }
        t[n + 1] = delay + n * gradRaster; a[n + 1] = amp * (last !== null ? last : s[n - 1]);
      }
      grads[id] = chan(t, a);
    }
    for (const r of S.TRAP || []) {
      const v = r.map(num);
      const d = v[5] * 1e-6, ri = v[2] * 1e-6, fl = v[3] * 1e-6, fa = v[4] * 1e-6;
      grads[v[0]] = chan(new Float64Array([d, d + ri, d + ri + fl, d + ri + fl + fa]), new Float64Array([0, v[1], v[1], 0]));
    }
    const adcs = {};
    for (const r of S.ADC || []) {
      const v = r.map(num);
      if (r.length >= 9) adcs[v[0]] = { num: v[1], dwell: v[2] * 1e-9, delay: v[3] * 1e-6, freq: v[6], phase: v[7] };
      else adcs[v[0]] = { num: v[1], dwell: v[2] * 1e-9, delay: v[3] * 1e-6, freq: v[4], phase: v[5] };
    }
    const delays = {};
    for (const r of S.DELAYS || []) delays[+r[0]] = +r[1] * 1e-6;

    // blocks
    const blocks = [];
    let t0 = 0;
    for (const r of S.BLOCKS) {
      const v = r.map(num);
      const b = {
        index: v[0], start: t0,
        rf: v[2] ? rfs[v[2]] : null, rfId: v[2],
        g: [v[3] ? grads[v[3]] : null, v[4] ? grads[v[4]] : null, v[5] ? grads[v[5]] : null],
        gId: [v[3], v[4], v[5]],
        adc: v[6] ? adcs[v[6]] : null,
      };
      let dur;
      if (!legacyBlocks) dur = v[1] * blockRaster;
      else {
        dur = delays[v[1]] || 0;
        if (b.rf) dur = Math.max(dur, b.rf.delay + b.rf.dur);
        for (const g of b.g) if (g) dur = Math.max(dur, g.t[g.t.length - 1]);
        if (b.adc) dur = Math.max(dur, b.adc.delay + b.adc.num * b.adc.dwell);
      }
      b.dur = dur;
      b.active = !!(b.rf || b.adc || b.g[0] || b.g[1] || b.g[2]);
      blocks.push(b);
      t0 += dur;
    }
    // number RF pulses and ADCs in order
    let nrf = 0, nadc = 0;
    for (const b of blocks) {
      if (b.rf) b.rfNo = ++nrf;
      if (b.adc) b.adcNo = ++nadc;
    }
    let lastActive = 0;
    for (const b of blocks) if (b.active) lastActive = b.start + b.dur;
    const thk = defNum('SliceThickness', null);
    return { version, defs, blocks, total: t0, lastActive, sliceThickness: thk, nRF: nrf, nADC: nadc, gradRaster, rfRaster };
  }

  function chan(t, a) {
    const n = t.length, cum = new Float64Array(n);
    let amax = 0;
    for (let k = 1; k < n; k++) cum[k] = cum[k - 1] + (t[k] - t[k - 1]) * (a[k] + a[k - 1]) / 2;
    for (let k = 0; k < n; k++) amax = Math.max(amax, Math.abs(a[k]));
    return { t, a, cum, area: cum[n - 1], amax, t0: t[0], t1: t[n - 1] };
  }

  function seek(t, x) { // largest i with t[i] <= x (0 <= i <= n-2)
    let lo = 0, hi = t.length - 2;
    while (lo < hi) { const m = (lo + hi + 1) >> 1; if (t[m] <= x) lo = m; else hi = m - 1; }
    return lo;
  }
  function integ(ch, tau) { // integral of gradient from block start to tau [cycles/m]
    if (!ch || tau <= ch.t0) return 0;
    if (tau >= ch.t1) return ch.area;
    const i = seek(ch.t, tau), t = ch.t, a = ch.a;
    const d = tau - t[i], span = t[i + 1] - t[i];
    const slope = span > 0 ? (a[i + 1] - a[i]) / span : 0;
    return ch.cum[i] + a[i] * d + 0.5 * slope * d * d;
  }
  function gval(ch, tau) {
    if (!ch || tau < ch.t0 || tau > ch.t1) return 0;
    const i = seek(ch.t, tau), t = ch.t, a = ch.a, span = t[i + 1] - t[i];
    return span > 0 ? a[i] + (a[i + 1] - a[i]) * (tau - t[i]) / span : a[i];
  }

  function cumAt(rf, tt) { // complex cumulative RF area at time tt (relative to RF start)
    const e = rf.edges, n = e.length;
    if (tt <= e[0]) return [0, 0];
    if (tt >= e[n - 1]) return [rf.cre[n - 1], rf.cim[n - 1]];
    const i = seek(e, tt), f = (tt - e[i]) / (e[i + 1] - e[i]);
    return [rf.cre[i] + f * (rf.cre[i + 1] - rf.cre[i]), rf.cim[i] + f * (rf.cim[i + 1] - rf.cim[i])];
  }

  // FWHM of |spectrum| of the pulse [Hz] (used for the ideal-pulse slab and labels)
  function estimateBandwidth(rf) {
    const M = 256, dur = rf.dur;
    if (!(dur > 0)) return 0;
    const re = new Float64Array(M), im = new Float64Array(M), tt = new Float64Array(M);
    let prev = [0, 0];
    for (let k = 0; k < M; k++) {
      const c = cumAt(rf, (k + 1) * dur / M);
      re[k] = c[0] - prev[0]; im[k] = c[1] - prev[1]; prev = c; tt[k] = (k + 0.5) * dur / M;
    }
    const F = 24 / dur, NF = 961;
    const mags = new Float64Array(NF);
    let best = 0, ib = 0;
    for (let j = 0; j < NF; j++) {
      const f = -F + 2 * F * j / (NF - 1);
      let sr = 0, si = 0;
      for (let k = 0; k < M; k++) {
        const p = -TWO_PI * f * tt[k], c = Math.cos(p), s = Math.sin(p);
        sr += re[k] * c - im[k] * s; si += re[k] * s + im[k] * c;
      }
      mags[j] = Math.hypot(sr, si);
      if (mags[j] > best) { best = mags[j]; ib = j; }
    }
    let lo = ib, hi = ib;
    while (lo > 0 && mags[lo] > best / 2) lo--;
    while (hi < NF - 1 && mags[hi] > best / 2) hi++;
    return (hi - lo) * 2 * F / (NF - 1);
  }

  // ------------------------------------------------------------------ ensemble
  function mulberry32(a) {
    return function () {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      let t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  function probit(p) { // Acklam's inverse normal CDF
    const a = [-39.69683028665376, 220.9460984245205, -275.9285104469687, 138.357751867269, -30.66479806614716, 2.506628277459239];
    const b = [-54.47609879822406, 161.5858368580409, -155.6989798598866, 66.80131188771972, -13.28068155288572];
    const c = [-0.007784894002430293, -0.3223964580411365, -2.400758277161838, -2.549732539343734, 4.374664141464968, 2.938163982698783];
    const d = [0.007784695709041462, 0.3224671290700398, 2.445134137142996, 3.754408661907416];
    const pl = 0.02425;
    let q, r;
    if (p < pl) { q = Math.sqrt(-2 * Math.log(p)); return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
    if (p > 1 - pl) { q = Math.sqrt(-2 * Math.log(1 - p)); return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
    q = p - 0.5; r = q * q;
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
  }

  /* opts: nz, nsub, zSpan [m], thk [m or null], voxXY [m], t2p [s, 0 = none], b0 [Hz],
           b1 (global scale), b1Spread (fractional half-range), motion {mode:'none'|'coherent'|'uniform'|'gauss', deg}, seed */
  function makeEnsemble(o) {
    const rnd = mulberry32(o.seed || 7);
    const nz = o.nz, ns = o.nsub, N = nz * ns;
    const x = new Float64Array(N), y = new Float64Array(N), z = new Float64Array(N), df = new Float64Array(N);
    const b1 = new Float64Array(N), mphase = new Float64Array(N), zbin = new Int32Array(N);
    const inSlice = new Uint8Array(N);
    const zc = new Float64Array(nz), dz = o.zSpan / nz;
    const perm = () => { const p = Array.from({ length: ns }, (_, k) => k); for (let k = ns - 1; k > 0; k--) { const j = Math.floor(rnd() * (k + 1)); [p[k], p[j]] = [p[j], p[k]]; } return p; };
    const strat = () => { const p = perm(); return p.map(k => (k + rnd()) / ns); };
    const hw = o.t2p > 0 ? 1 / (TWO_PI * o.t2p) : 0;
    let nin = 0;
    for (let i = 0; i < nz; i++) {
      zc[i] = -o.zSpan / 2 + (i + 0.5) * dz;
      const ux = strat(), uy = strat(), uf = strat(), ub = strat(), um = strat(), uz = strat();
      for (let j = 0; j < ns; j++) {
        const k = i * ns + j;
        zbin[k] = i;
        x[k] = (ux[j] - 0.5) * o.voxXY;
        y[k] = (uy[j] - 0.5) * o.voxXY;
        z[k] = zc[i] + (ns > 1 ? (uz[j] - 0.5) * dz : 0);
        df[k] = o.b0 + (hw ? Math.max(-2000, Math.min(2000, hw * Math.tan(Math.PI * (uf[j] - 0.5)))) : 0);
        b1[k] = o.b1 * (1 + (ns > 1 ? (ub[j] - 0.5) * 2 * (o.b1Spread || 0) : 0));
        const m = o.motion || { mode: 'none' };
        const deg = (m.deg || 0) * Math.PI / 180;
        mphase[k] = m.mode === 'coherent' ? deg : m.mode === 'uniform' ? TWO_PI * um[j] : m.mode === 'gauss' ? deg * probit(um[j]) : 0;
        inSlice[k] = o.thk ? (Math.abs(z[k]) <= o.thk / 2 ? 1 : 0) : 1;
        nin += inSlice[k];
      }
    }
    return { N, nz, nsub: ns, x, y, z, df, b1, mphase, zbin, zc, inSlice, nin: Math.max(1, nin), zSpan: o.zSpan, thk: o.thk, L: o.thk || o.zSpan };
  }

  // ------------------------------------------------------------------ simulator
  /* phys: T1, T2 [s], rfMode 'finite'|'ideal', stepUs (RF step target), motionAfterBlock (index into blocks or -1),
           tEnd [s] window end, nGrid */
  function Simulator(seq, ens, phys) {
    this.seq = seq; this.ens = ens; this.p = phys;
    const tEnd = Math.min(phys.tEnd || seq.lastActive, seq.total);
    this.tEnd = tEnd;
    const tStart = phys.tStart || 0;
    this.blocks = seq.blocks.filter(b => b.start < tEnd - 1e-12 && b.start + b.dur > tStart + 1e-12);
    if (!this.blocks.length) throw new Error('The simulation window contains no blocks.');
    this.tStart = this.blocks[0].start; // simulation starts from equilibrium at this block boundary
    this.E = new Map(); // per-block RF step data
    this.cpEvery = 1;
    const bytes = this.blocks.length * ens.N * 3 * 4;
    if (bytes > 160e6) this.cpEvery = Math.ceil(bytes / 160e6);
    this.checkpoints = [];
    this.cache = null;
  }

  Simulator.prototype.rfSteps = function (b) {
    if (this.E.has(b)) return this.E.get(b);
    const rf = b.rf, p = this.p;
    const n = Math.max(4, Math.min(1500, Math.ceil(rf.dur / ((p.stepUs || 5) * 1e-6))));
    const dt = rf.dur / n;
    const bre = new Float64Array(n), bim = new Float64Array(n), gx = new Float64Array(n), gy = new Float64Array(n), gz = new Float64Array(n);
    let prev = [0, 0];
    for (let k = 0; k < n; k++) {
      const c = cumAt(rf, (k + 1) * dt);
      const r = (c[0] - prev[0]) / dt, i = (c[1] - prev[1]) / dt; prev = c;
      const tc = rf.delay + (k + 0.5) * dt;
      const ph = rf.phase + TWO_PI * rf.freq * (tc - rf.delay);
      const cp = Math.cos(ph), sp = Math.sin(ph);
      bre[k] = r * cp - i * sp; bim[k] = r * sp + i * cp;
      const ta = rf.delay + k * dt, tb = ta + dt;
      gx[k] = (integ(b.g[0], tb) - integ(b.g[0], ta)) / dt;
      gy[k] = (integ(b.g[1], tb) - integ(b.g[1], ta)) / dt;
      gz[k] = (integ(b.g[2], tb) - integ(b.g[2], ta)) / dt;
    }
    // ideal (instantaneous) model
    const tc = rf.center + rf.delay;
    const G = [gval(b.g[0], tc), gval(b.g[1], tc), gval(b.g[2], tc)];
    const fc = rf.phase + TWO_PI * rf.freq * (rf.center);
    const e = { n, dt, t0: rf.delay, t1: rf.delay + rf.dur, bre, bim, gx, gy, gz, tc, G, axis: rf.axisPhase + TWO_PI * rf.freq * rf.center, fc };
    const gmag = Math.hypot(G[0], G[1], G[2]);
    e.selective = gmag * this.ens.zSpan > 0.1 * rf.bw;
    this.E.set(b, e);
    return e;
  };

  // free precession of state over [ta, tb] within block b (in place)
  Simulator.prototype.free = function (st, b, ta, tb) {
    if (tb <= ta) return;
    const ens = this.ens, N = ens.N;
    const kx = integ(b.g[0], tb) - integ(b.g[0], ta), ky = integ(b.g[1], tb) - integ(b.g[1], ta), kz = integ(b.g[2], tb) - integ(b.g[2], ta);
    const d = tb - ta, e2 = Math.exp(-d / this.p.T2), e1 = Math.exp(-d / this.p.T1);
    const { x, y, z, df } = ens, mx = st.mx, my = st.my, mz = st.mz;
    for (let i = 0; i < N; i++) {
      const ph = TWO_PI * (kx * x[i] + ky * y[i] + kz * z[i] + df[i] * d);
      const c = Math.cos(ph), s = Math.sin(ph), a = mx[i], bb = my[i];
      mx[i] = (a * c + bb * s) * e2; my[i] = (bb * c - a * s) * e2; mz[i] = 1 + (mz[i] - 1) * e1;
    }
  };

  // one RF step k (or the first frac of it) in place
  Simulator.prototype.step = function (st, e, k, frac) {
    const ens = this.ens, N = ens.N, dt = e.dt * (frac === undefined ? 1 : frac);
    const Bx = e.bre[k], By = e.bim[k], gx = e.gx[k], gy = e.gy[k], gz = e.gz[k];
    const e2 = Math.exp(-dt / this.p.T2), e1 = Math.exp(-dt / this.p.T1);
    const { x, y, z, df, b1 } = ens, mx = st.mx, my = st.my, mz = st.mz;
    const w = TWO_PI * dt;
    for (let i = 0; i < N; i++) {
      const bx = Bx * b1[i], by = By * b1[i], bz = gx * x[i] + gy * y[i] + gz * z[i] + df[i];
      const bn = Math.sqrt(bx * bx + by * by + bz * bz);
      const a = mx[i], bb = my[i], cz = mz[i];
      if (bn > 0) {
        const th = -w * bn, c = Math.cos(th), s = Math.sin(th);
        const kx = bx / bn, ky = by / bn, kz = bz / bn;
        const kd = (kx * a + ky * bb + kz * cz) * (1 - c);
        mx[i] = (a * c + (ky * cz - kz * bb) * s + kx * kd) * e2;
        my[i] = (bb * c + (kz * a - kx * cz) * s + ky * kd) * e2;
        mz[i] = 1 + (cz * c + (kx * bb - ky * a) * s + kz * kd - 1) * e1;
      } else {
        mx[i] = a * e2; my[i] = bb * e2; mz[i] = 1 + (cz - 1) * e1;
      }
    }
  };

  // ideal instantaneous rotation (rectangular slice profile)
  Simulator.prototype.instant = function (st, b, e) {
    const ens = this.ens, N = ens.N, rf = b.rf;
    const alpha = rf.flipDeg * Math.PI / 180;
    const kx = -Math.cos(e.axis), ky = -Math.sin(e.axis);
    const { x, y, z, df, b1 } = ens, mx = st.mx, my = st.my, mz = st.mz;
    for (let i = 0; i < N; i++) {
      if (e.selective) {
        const nu = e.G[0] * x[i] + e.G[1] * y[i] + e.G[2] * z[i] + df[i];
        if (Math.abs(nu - rf.freq) > rf.bw / 2) continue;
      }
      const th = alpha * b1[i], c = Math.cos(th), s = Math.sin(th);
      const a = mx[i], bb = my[i], cz = mz[i];
      const kd = (kx * a + ky * bb) * (1 - c);
      mx[i] = a * c + (ky * cz) * s + kx * kd;
      my[i] = bb * c + (-kx * cz) * s + ky * kd;
      mz[i] = cz * c + (kx * bb - ky * a) * s;
    }
  };

  Simulator.prototype.applyMotion = function (st) {
    const { mphase, N } = this.ens, mx = st.mx, my = st.my;
    for (let i = 0; i < N; i++) {
      const p = mphase[i];
      if (!p) continue;
      const c = Math.cos(p), s = Math.sin(p), a = mx[i], bb = my[i];
      mx[i] = a * c + bb * s; my[i] = bb * c - a * s;
    }
  };

  /* Advance state from the start of block b to tau (<= b.dur), in place.
     onStep(tauAfterStep) is called after each RF step (for recording). */
  Simulator.prototype.advance = function (st, b, tau, onStep) {
    if (!b.rf) { this.free(st, b, 0, tau); return; }
    const e = this.rfSteps(b);
    if (this.p.rfMode === 'ideal') {
      this.free(st, b, 0, Math.min(tau, e.tc));
      if (tau >= e.tc) { this.instant(st, b, e); this.free(st, b, e.tc, tau); }
      return;
    }
    this.free(st, b, 0, Math.min(tau, e.t0));
    if (tau <= e.t0) return;
    const kmax = Math.min(e.n, Math.floor((tau - e.t0) / e.dt + 1e-9));
    for (let k = 0; k < kmax; k++) { this.step(st, e, k); if (onStep) onStep(e.t0 + (k + 1) * e.dt); }
    if (kmax < e.n) {
      const rem = (tau - e.t0) / e.dt - kmax;
      if (rem > 1e-9) this.step(st, e, kmax, rem);
      return;
    }
    this.free(st, b, e.t1, tau);
  };

  function newState(N) { const mz = new Float64Array(N); mz.fill(1); return { mx: new Float64Array(N), my: new Float64Array(N), mz }; }
  function copyState(s) { return { mx: Float64Array.from(s.mx), my: Float64Array.from(s.my), mz: Float64Array.from(s.mz) }; }

  // sums used for the signal trace: complex signal (all spins / in-slice count), in-slice mean vector
  Simulator.prototype.summary = function (st) {
    const { N, inSlice, nin } = this.ens;
    let sx = 0, sy = 0, ix = 0, iy = 0, iz = 0;
    for (let i = 0; i < N; i++) {
      sx += st.mx[i]; sy += st.my[i];
      if (inSlice[i]) { ix += st.mx[i]; iy += st.my[i]; iz += st.mz[i]; }
    }
    return [sx / nin, sy / nin, ix / nin, iy / nin, iz / nin];
  };
  // same sums for the state reached by free precession from st over [ta, tb] (st unchanged)
  Simulator.prototype.summaryFree = function (st, b, ta, tb) {
    const ens = this.ens, N = ens.N, { x, y, z, df, inSlice, nin } = ens;
    const kx = integ(b.g[0], tb) - integ(b.g[0], ta), ky = integ(b.g[1], tb) - integ(b.g[1], ta), kz = integ(b.g[2], tb) - integ(b.g[2], ta);
    const d = tb - ta, e2 = Math.exp(-d / this.p.T2), e1 = Math.exp(-d / this.p.T1);
    let sx = 0, sy = 0, ix = 0, iy = 0, iz = 0;
    for (let i = 0; i < N; i++) {
      const ph = TWO_PI * (kx * x[i] + ky * y[i] + kz * z[i] + df[i] * d);
      const c = Math.cos(ph), s = Math.sin(ph), a = st.mx[i], bb = st.my[i];
      const X = (a * c + bb * s), Y = (bb * c - a * s);
      sx += X; sy += Y;
      if (inSlice[i]) { ix += X; iy += Y; iz += 1 + (st.mz[i] - 1) * e1; }
    }
    return [sx * e2 / nin, sy * e2 / nin, ix * e2 / nin, iy * e2 / nin, iz / nin];
  };

  /* Full pass: checkpoints + signal trace + echo table. A generator so the UI can yield. */
  Simulator.prototype.run = function* () {
    const ens = this.ens, blocks = this.blocks, nG = this.p.nGrid || 3000;
    // sample times: uniform grid + ADC samples (strided) + ADC centres
    const times = [];
    for (let k = 0; k <= nG; k++) times.push({ t: this.tStart + k * (this.tEnd - this.tStart) / nG, kind: 0 });
    const echoes = [];
    for (const b of blocks) {
      if (!b.adc) continue;
      const a = b.adc, stride = Math.max(1, Math.ceil(a.num / 160));
      const ic = Math.floor(a.num / 2);
      for (let k = 0; k < a.num; k += stride) times.push({ t: b.start + a.delay + (k + 0.5) * a.dwell, kind: 0 });
      const ec = { no: b.adcNo, t: b.start + a.delay + (ic + 0.5) * a.dwell, adc: a, block: b, value: null };
      echoes.push(ec);
      times.push({ t: ec.t, kind: 1, echo: ec });
    }
    times.sort((p, q) => p.t - q.t);
    const tr = { t: new Float64Array(times.length), sx: new Float64Array(times.length), sy: new Float64Array(times.length), ix: new Float64Array(times.length), iy: new Float64Array(times.length), iz: new Float64Array(times.length) };
    let ti = 0, rec = 0;
    const record = (t, v, item) => {
      tr.t[rec] = t; tr.sx[rec] = v[0]; tr.sy[rec] = v[1]; tr.ix[rec] = v[2]; tr.iy[rec] = v[3]; tr.iz[rec] = v[4]; rec++;
      if (item.kind === 1) {
        const a = item.echo.adc, b = item.echo.block;
        const ph = -(a.phase + TWO_PI * a.freq * (t - b.start - a.delay));
        const c = Math.cos(ph), s = Math.sin(ph);
        item.echo.value = [v[0] * c - v[1] * s, v[0] * s + v[1] * c];
        item.echo.raw = [v[0], v[1]];
      }
    };
    const st = newState(ens.N);
    const motionAfter = this.p.motionAfterBlock;
    let lastYield = Date.now();
    for (let bi = 0; bi < blocks.length; bi++) {
      const b = blocks[bi];
      if (bi % this.cpEvery === 0) this.checkpoints[bi / this.cpEvery] = { mx: Float32Array.from(st.mx), my: Float32Array.from(st.my), mz: Float32Array.from(st.mz) };
      const bEnd = Math.min(b.dur, this.tEnd - b.start);
      // samples in [b.start, b.start + bEnd)
      const isLast = bi === blocks.length - 1;
      const inBlock = t => t < b.start + bEnd || (isLast && t <= b.start + bEnd + 1e-12);
      if (!b.rf) {
        while (ti < times.length && inBlock(times[ti].t)) { const it = times[ti++]; record(it.t, this.summaryFree(st, b, 0, it.t - b.start), it); }
        this.free(st, b, 0, bEnd);
      } else {
        // sample before RF via exact free, during RF on step ends, after RF via free from post-RF state
        const e = this.rfSteps(b);
        const tA = this.p.rfMode === 'ideal' ? e.tc : e.t0;
        while (ti < times.length && inBlock(times[ti].t) && times[ti].t - b.start < tA) { const it = times[ti++]; record(it.t, this.summaryFree(st, b, 0, it.t - b.start), it); }
        if (this.p.rfMode === 'ideal') {
          this.free(st, b, 0, e.tc); this.instant(st, b, e);
          while (ti < times.length && inBlock(times[ti].t)) { const it = times[ti++]; record(it.t, this.summaryFree(st, b, e.tc, it.t - b.start), it); }
          this.free(st, b, e.tc, bEnd);
        } else {
          this.free(st, b, 0, e.t0);
          for (let k = 0; k < e.n; k++) {
            this.step(st, e, k);
            const tk = b.start + e.t0 + (k + 1) * e.dt;
            if (ti < times.length && times[ti].t <= tk && inBlock(times[ti].t)) {
              const v = this.summary(st);
              while (ti < times.length && times[ti].t <= tk && inBlock(times[ti].t)) record(times[ti].t, v, times[ti++]);
            }
          }
          while (ti < times.length && inBlock(times[ti].t)) { const it = times[ti++]; record(it.t, this.summaryFree(st, b, e.t1, it.t - b.start), it); }
          this.free(st, b, e.t1, bEnd);
        }
      }
      if (bi === motionAfter) this.applyMotion(st);
      if (Date.now() - lastYield > 30) { lastYield = Date.now(); yield (bi + 1) / blocks.length; }
    }
    for (const k in tr) tr[k] = tr[k].subarray(0, rec);
    this.trace = tr;
    this.echoes = echoes.filter(e => e.value);
    this.finalState = st;
  };
  Simulator.prototype.runSync = function () { const g = this.run(); while (!g.next().done); return this; };

  function blockAt(blocks, t) {
    let lo = 0, hi = blocks.length - 1;
    while (lo < hi) { const m = (lo + hi + 1) >> 1; if (blocks[m].start <= t) lo = m; else hi = m - 1; }
    return lo;
  }

  // State at absolute time t (needs run() first). Uses checkpoints and a small cache for playback.
  Simulator.prototype.stateAt = function (t) {
    t = Math.max(this.tStart, Math.min(t, this.tEnd));
    const blocks = this.blocks;
    const bi = blockAt(blocks, t), b = blocks[bi];
    const tau = Math.min(t - b.start, b.dur);
    // cache inside a finite RF block: continue stepping forward
    if (b.rf && this.p.rfMode !== 'ideal') {
      const e = this.rfSteps(b);
      let base = null, kDone = 0;
      if (this.cache && this.cache.bi === bi && this.cache.tau <= tau + 1e-15) { base = copyState(this.cache.st); kDone = this.cache.k; }
      if (!base) { base = this.blockStart(bi); this.free(base, b, 0, e.t0); kDone = 0; }
      if (tau > e.t0) {
        const kmax = Math.min(e.n, Math.floor((tau - e.t0) / e.dt + 1e-9));
        for (let k = kDone; k < kmax; k++) this.step(base, e, k);
        this.cache = { bi, k: Math.max(kDone, kmax), tau: e.t0 + Math.max(kDone, kmax) * e.dt, st: copyState(base) };
        if (kmax < e.n) { const rem = (tau - e.t0) / e.dt - kmax; if (rem > 1e-9) this.step(base, e, kmax, rem); }
        else this.free(base, b, e.t1, tau);
      } else {
        // before the RF starts: base is at e.t0, go back by recomputing exactly
        const s0 = this.blockStart(bi); this.free(s0, b, 0, tau); return s0;
      }
      return base;
    }
    const st = this.blockStart(bi);
    this.advance(st, b, tau);
    return st;
  };
  Simulator.prototype.blockStart = function (bi) {
    const cpi = Math.floor(bi / this.cpEvery), cp = this.checkpoints[cpi];
    const st = { mx: Float64Array.from(cp.mx), my: Float64Array.from(cp.my), mz: Float64Array.from(cp.mz) };
    for (let j = cpi * this.cpEvery; j < bi; j++) {
      this.advance(st, this.blocks[j], this.blocks[j].dur);
      if (j === this.p.motionAfterBlock) this.applyMotion(st);
    }
    return st;
  };

  const api = { parseSeq, makeEnsemble, Simulator, integ, gval, cumAt, blockAt };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.SpinEngine = api;
})(typeof window !== 'undefined' ? window : globalThis);
