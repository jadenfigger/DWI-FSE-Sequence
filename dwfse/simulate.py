"""
simulate.py - Bloch simulation of any Pulseq .seq file (numpy, CPU).

Voxel model: isochromats spread over x, y (in-plane voxel), z (2x the slice
thickness, so slice-profile edges are included) and a Lorentzian off-resonance
spread (T2'). RF blocks are stepped in time (default 10 us, validated against
1 us); blocks without RF are applied exactly (gradient-moment phase + relaxation),
so long delays cost nothing.

Validated: matches KomaMRI on the minimal DW-FSE protocol within Monte-Carlo
noise, and a snapshot at an ADC centre equals the simulated signal at that time.

Used through the CLI (README.md):  python dw.py sim my.seq --b1 0.8 0.9 1.0
From Python:
    res = run('my.seq', b1=[1.0, 0.9], snaps='adc')    # dict, see run()
    r = simulate('my.seq', b1=0.9)                     # single run, lower level

Echo amplitude convention: |mean Mxy| at sample N//2 of each ADC window
(the k-space-centre sample for an even number of samples).
"""
import numpy as np
import pypulseq as pp


# ------------------------------------------------------------------ voxel
def make_voxel(n=20000, voxel_xy=0.2e-3, slice_thk=1.0e-3, T2prime=0.03, b0=0.0, seed=1, z_span=2.0,
               stratified=True):
    """Isochromats: x, y in a voxel_xy square, z over z_span*slice_thk, Lorentzian off-resonance
    with HWHM 1/(2 pi T2') plus a global b0 [Hz]. stratified=True uses evenly spaced quantiles
    (shuffled per axis): far less Monte-Carlo noise than random sampling."""
    rng = np.random.default_rng(seed)

    def u():
        return rng.permutation((np.arange(n) + 0.5) / n) if stratified else rng.random(n)

    x = (u() - 0.5) * voxel_xy
    y = (u() - 0.5) * voxel_xy
    z = (u() - 0.5) * z_span * slice_thk
    df = np.clip(np.tan(np.pi * (u() - 0.5)) / (2 * np.pi * T2prime), -2000, 2000) + b0 \
        if T2prime else np.full(n, float(b0))
    return dict(x=x, y=y, z=z, df=df)


# ------------------------------------------------------------------ helpers
def grad_pts(g):
    """Piecewise-linear (t, amp) of one gradient event; t relative to block start."""
    if g is None:
        return None
    if g.type == 'trap':
        t = np.array([0, g.rise_time, g.rise_time + g.flat_time, g.rise_time + g.flat_time + g.fall_time])
        a = np.array([0, g.amplitude, g.amplitude, 0.0])
    else:
        t, a = np.asarray(g.tt, float), np.asarray(g.waveform, float)
    return t + g.delay, a


def _cumint(pts, t):
    """Integral of the piecewise-linear gradient from block start to times t (exact)."""
    t = np.asarray(t, float)
    if pts is None:
        return np.zeros_like(t)
    tp, ap = pts
    tg = np.concatenate([[0.0], tp]) if tp[0] > 0 else tp
    ag = np.concatenate([[0.0], ap]) if tp[0] > 0 else ap
    seg = np.concatenate([[0.0], np.cumsum(np.diff(tg) * (ag[1:] + ag[:-1]) / 2)])
    i = np.clip(np.searchsorted(tg, t, side='right') - 1, 0, len(tg) - 2)
    t0, a0 = tg[i], ag[i]
    slope = (ag[i + 1] - a0) / np.maximum(tg[i + 1] - t0, 1e-30)
    exact = seg[i] + a0 * (t - t0) + 0.5 * slope * (t - t0) ** 2
    out = np.where(t <= tg[0], 0.0, exact)
    return np.where(t >= tg[-1], seg[-1], out)


def _rotate(mx, my, mz, bx, by, bz, dt):
    """Rotate M about B [Hz] by -2 pi |B| dt (left-handed; free precession = exp(-i phi))."""
    bn = np.sqrt(bx * bx + by * by + bz * bz)
    th = -2 * np.pi * bn * dt
    with np.errstate(invalid='ignore', divide='ignore'):
        kx, ky, kz = np.where(bn > 0, bx / bn, 0), np.where(bn > 0, by / bn, 0), np.where(bn > 0, bz / bn, 1)
    c, s = np.cos(th), np.sin(th)
    kd = kx * mx + ky * my + kz * mz
    cx, cy, cz = ky * mz - kz * my, kz * mx - kx * mz, kx * my - ky * mx
    return (mx * c + cx * s + kx * kd * (1 - c),
            my * c + cy * s + ky * kd * (1 - c),
            mz * c + cz * s + kz * kd * (1 - c))


def read_seq(seq_or_path):
    if isinstance(seq_or_path, pp.Sequence):
        return seq_or_path
    seq = pp.Sequence()
    seq.read(seq_or_path)
    return seq


def block_times(seq):
    ids = sorted(seq.block_events)
    dur = np.array([seq.block_durations[i] for i in ids])
    return ids, np.r_[0, np.cumsum(dur)[:-1]], dur


def snapshot_times(seq, mode='adc'):
    """[(time s, label)] for: 'adc' (centre of every ADC = echo), 'rf' (end of every RF block),
    'none', 'blocks:3,7,11' (end of those blocks) or 'times:18.5,54.9' (ms)."""
    if not mode or mode == 'none':
        return []
    seq = read_seq(seq)
    ids, starts, dur = block_times(seq)
    out = []
    if mode == 'adc' or mode == 'rf':
        n_adc = 0
        for i, s, d in zip(ids, starts, dur):
            b = seq.get_block(i)
            if mode == 'adc' and b.adc is not None:
                n_adc += 1
                out.append((s + b.adc.delay + b.adc.num_samples * b.adc.dwell / 2, f'echo {n_adc} (ADC centre)'))
            if mode == 'rf' and b.rf is not None:
                out.append((s + d, f'end of RF block {i}'))
    elif mode.startswith('blocks:'):
        for i in (int(v) for v in mode[7:].split(',') if v):
            k = ids.index(i)
            out.append((starts[k] + dur[k], f'end of block {i}'))
    elif mode.startswith('times:'):
        out = [(float(v) * 1e-3, f't = {float(v):g} ms') for v in mode[6:].split(',') if v]
    else:
        raise ValueError(f'unknown snapshot mode {mode!r}')
    return sorted(out)


# ------------------------------------------------------------------ simulation
def simulate(seq, b1=1.0, b0=0.0, T1=1.5, T2=0.08, T2prime=0.03, n=20000, voxel=None,
             snap_times=(), rf_dt=1e-5, max_blocks=None):
    """One Bloch run. Returns dict(t_adc, signal (complex), adc_sizes, echo_center, echo_peak,
    snapshots [(t, mx, my, mz)], voxel). b0 adds to every isochromat's off-resonance [Hz]."""
    seq = read_seq(seq)
    vox = voxel or make_voxel(n=n, T2prime=T2prime)
    x, y, z = vox['x'], vox['y'], vox['z']
    df = vox['df'] + b0
    N = len(x)
    mx, my, mz = np.zeros(N), np.zeros(N), np.ones(N)
    snap_times = sorted(snap_times)
    snaps, si = [], 0
    sig, tads = [], []
    ids, starts, dur_all = block_times(seq)
    if max_blocks:
        ids = ids[:max_blocks]
    for ib, t_abs, dur in zip(ids, starts, dur_all):
        blk = seq.get_block(ib)
        g = {ax: grad_pts(getattr(blk, 'g' + ax, None)) for ax in 'xyz'}

        def free(t_rel):
            """state after free precession from block start to t_rel (no RF in block)."""
            t_rel = np.atleast_1d(np.asarray(t_rel, float))
            kx, ky, kz = (_cumint(g[ax], t_rel) for ax in 'xyz')
            ph = 2 * np.pi * (np.outer(kx, x) + np.outer(ky, y) + np.outer(kz, z) + np.outer(t_rel, df))
            mxy = (mx + 1j * my)[None, :] * np.exp(-1j * ph) * np.exp(-t_rel / T2)[:, None]
            return mxy, 1 + (mz - 1)[None, :] * np.exp(-t_rel / T1)[:, None]

        if blk.rf is None:
            if blk.adc is not None:
                a = blk.adc
                ts = a.delay + (np.arange(a.num_samples) + 0.5) * a.dwell
                mxy, _ = free(ts)
                demod = np.exp(-1j * (a.phase_offset + 2 * np.pi * a.freq_offset * (ts - a.delay)))
                sig.append(mxy.mean(axis=1) * demod)
                tads.append(t_abs + ts)
            while si < len(snap_times) and snap_times[si] <= t_abs + dur + 1e-12:
                mxy, mzs = free(snap_times[si] - t_abs)
                snaps.append((snap_times[si], mxy[0].real.copy(), mxy[0].imag.copy(), mzs[0].copy()))
                si += 1
            mxy, mzs = free(dur)
            mx, my, mz = mxy[0].real, mxy[0].imag, mzs[0]
        else:
            rf = blk.rf
            dt = rf_dt or seq.rf_raster_time
            nt = max(1, int(round(dur / dt)))
            dt = dur / nt
            tc = (np.arange(nt) + 0.5) * dt
            G = {ax: (np.interp(tc, *g[ax], left=0, right=0) if g[ax] is not None else np.zeros(nt)) for ax in 'xyz'}
            trf = rf.t + rf.delay
            inrf = (tc >= trf[0] - dt / 2) & (tc <= trf[-1] + dt / 2)
            B1 = np.where(inrf, np.interp(tc, trf, rf.signal.real) + 1j * np.interp(tc, trf, rf.signal.imag), 0)
            B1 = B1 * b1 * np.exp(1j * (rf.phase_offset + 2 * np.pi * rf.freq_offset * (tc - rf.delay)))
            e2, e1 = np.exp(-dt / T2), np.exp(-dt / T1)
            for k in range(nt):
                bz = G['x'][k] * x + G['y'][k] * y + G['z'][k] * z + df
                if B1[k] != 0:
                    mx, my, mz = _rotate(mx, my, mz, B1[k].real, B1[k].imag, bz, dt)
                else:
                    c, s = np.cos(2 * np.pi * bz * dt), np.sin(2 * np.pi * bz * dt)
                    mx, my = mx * c + my * s, my * c - mx * s
                mx, my, mz = mx * e2, my * e2, 1 + (mz - 1) * e1
                while si < len(snap_times) and snap_times[si] <= t_abs + (k + 1) * dt + 1e-12:
                    snaps.append((snap_times[si], mx.copy(), my.copy(), mz.copy()))
                    si += 1
            if blk.adc is not None:
                raise NotImplementedError(f'block {ib}: ADC during RF is not supported')
    s = np.concatenate(sig) if sig else np.zeros(0, complex)
    sizes = [len(q) for q in sig]
    edges = np.cumsum([0] + sizes)
    centre = np.array([abs(s[edges[i] + sizes[i] // 2]) for i in range(len(sizes))])
    peak = np.array([abs(s[edges[i]:edges[i + 1]]).max() for i in range(len(sizes))])
    return dict(t_adc=np.concatenate(tads) if tads else np.zeros(0), signal=s, adc_sizes=np.array(sizes),
                echo_center=centre, echo_peak=peak, snapshots=snaps, voxel=vox)


def run(seq_path, b1=(1.0,), b0=(0.0,), T1=1.5, T2=0.08, T2prime=0.03, n=20000, snaps='adc',
        rf_dt=1e-5, verbose=True):
    """Simulate every (b1, b0) combination. Snapshots are kept for the FIRST combination only.
    Returns a dict ready for save_npz()/results.py."""
    seq = read_seq(seq_path)
    vox = make_voxel(n=n, T2prime=T2prime)
    st = snapshot_times(seq, snaps)
    runs = []
    for i, bb1 in enumerate(b1):
        for j, bb0 in enumerate(b0):
            r = simulate(seq, b1=bb1, b0=bb0, T1=T1, T2=T2, voxel=vox, rf_dt=rf_dt,
                         snap_times=[t for t, _ in st] if (i == 0 and j == 0) else ())
            runs.append((bb1, bb0, r))
            if verbose:
                print(f'B1 {bb1:.2f}  B0 {bb0:+.0f} Hz : echoes |centre| = {np.round(r["echo_center"], 4)}')
    r0 = runs[0][2]
    out = dict(b1=np.array([q[0] for q in runs]), b0=np.array([q[1] for q in runs]),
               t_adc=r0['t_adc'], adc_sizes=r0['adc_sizes'],
               signal=np.array([q[2]['signal'] for q in runs]),
               echo_center=np.array([q[2]['echo_center'] for q in runs]),
               echo_peak=np.array([q[2]['echo_peak'] for q in runs]),
               z=vox['z'].astype(np.float32),
               snap_t=np.array([t for t, *_ in r0['snapshots']]),
               snap_label=np.array([lab for _, lab in st][:len(r0['snapshots'])]),
               snap_mx=np.array([m[1] for m in r0['snapshots']], np.float32),
               snap_my=np.array([m[2] for m in r0['snapshots']], np.float32),
               snap_mz=np.array([m[3] for m in r0['snapshots']], np.float32),
               tissue=np.array([T1, T2, T2prime, n]))
    adc_c, k0 = [], 0
    for sz in out['adc_sizes']:
        adc_c.append(out['t_adc'][k0:k0 + sz].mean())
        k0 += sz
    out['echo_t'] = np.array(adc_c)
    out['t_exc'] = np.array(first_excitation(seq))
    out['t_exc_all'] = np.array(excitation_times(seq))
    return out


def excitation_times(seq):
    """Centre times [s] of every RF pulse that is not a refocusing pulse."""
    ids, starts, _ = block_times(seq)
    out = []
    for i, s in zip(ids, starts):
        rf = seq.get_block(i).rf
        if rf is not None and not (getattr(rf, 'use', '') or '').startswith('ref'):
            c = getattr(rf, 'center', None)
            out.append(s + rf.delay + (c if c is not None else rf.t[int(np.argmax(np.abs(rf.signal)))]))
    return out


def first_excitation(seq):
    """Centre time [s] of the first RF pulse that is not a refocusing pulse (0 if none)."""
    ids, starts, _ = block_times(seq)
    for i, s in zip(ids, starts):
        rf = seq.get_block(i).rf
        if rf is not None and not (getattr(rf, 'use', '') or '').startswith('ref'):
            c = getattr(rf, 'center', None)
            return s + rf.delay + (c if c is not None else rf.t[int(np.argmax(np.abs(rf.signal)))])
    return 0.0


def save_npz(path, res):
    np.savez_compressed(path, **res)


def load_npz(path):
    d = np.load(path, allow_pickle=False)
    return {k: d[k] for k in d.files}
