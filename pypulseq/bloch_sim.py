"""
bloch_sim.py - small Bloch simulator for Pulseq .seq files (numpy, no GPU).

Same voxel model as koma_sim.jl: isochromats spread over x, y (in-plane voxel),
z (2x slice thickness) and a Lorentzian off-resonance (T2'). RF blocks are
stepped on the 1 us RF raster; blocks without RF are applied exactly
(gradient-moment phase + relaxation), so a whole TR takes a second or two.

    python bloch_sim.py my.seq                    # prints echo amplitudes
    python bloch_sim.py my.seq --b1 0.9 --b0 20   # B1 scale, global off-resonance [Hz]

From Python:  res = simulate('my.seq', b1=1.0)   -> dict(echo_center, echo_peak, signal, t_adc)
Echo amplitude convention matches koma_sim.jl: |mean Mxy| at sample N//2 of each ADC.
"""
import argparse
import numpy as np
import pypulseq as pp


def make_voxel(n=20000, voxel_xy=0.2e-3, slice_thk=1.0e-3, T2prime=0.03, b0=0.0, seed=1, z_span=2.0,
               stratified=False):
    """stratified=True: evenly spaced quantiles (shuffled per axis) -> much less Monte-Carlo noise."""
    rng = np.random.default_rng(seed)

    def u():
        if not stratified:
            return rng.random(n)
        return rng.permutation((np.arange(n) + 0.5) / n)

    x = (u() - 0.5) * voxel_xy
    y = (u() - 0.5) * voxel_xy
    z = (u() - 0.5) * z_span * slice_thk
    df = np.clip(np.tan(np.pi * (u() - 0.5)) / (2 * np.pi * T2prime), -2000, 2000) + b0 \
        if T2prime else np.full(n, float(b0))
    return dict(x=x, y=y, z=z, df=df)


def _grad_pts(g):
    """piecewise-linear (t, amp) of one gradient event, t relative to block start."""
    if g is None:
        return None
    if g.type == 'trap':
        t = np.array([0, g.rise_time, g.rise_time + g.flat_time, g.rise_time + g.flat_time + g.fall_time])
        a = np.array([0, g.amplitude, g.amplitude, 0.0])
    else:
        t, a = np.asarray(g.tt, float), np.asarray(g.waveform, float)
    return t + g.delay, a


def _cumint(pts, t):
    """integral of the piecewise-linear gradient from block start to times t."""
    if pts is None:
        return np.zeros_like(t)
    tp, ap = pts
    tg = np.concatenate([[0.0], tp]) if tp[0] > 0 else tp
    ag = np.concatenate([[0.0], ap]) if tp[0] > 0 else ap
    seg = np.concatenate([[0.0], np.cumsum(np.diff(tg) * (ag[1:] + ag[:-1]) / 2)])
    out = np.interp(t, tg, seg)
    i = np.clip(np.searchsorted(tg, t, side='right') - 1, 0, len(tg) - 2)
    inside = (t > tg[0]) & (t < tg[-1])
    t0, a0 = tg[i], ag[i]
    slope = (ag[i + 1] - a0) / np.maximum(tg[i + 1] - t0, 1e-30)
    dt = t - t0
    exact = seg[i] + a0 * dt + 0.5 * slope * dt ** 2
    out = np.where(inside, exact, out)
    out = np.where(t >= tg[-1], seg[-1], out)
    return out


def _rotate(mx, my, mz, bx, by, bz, dt):
    """rotate M about B (Hz) by -2*pi*|B|*dt (left-handed, matches free precession exp(-i phi))."""
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


def simulate(seq_path, b1=1.0, b0=0.0, T1=1.5, T2=0.08, T2prime=0.03, n=20000, voxel=None,
             snapshot_blocks=(), max_blocks=None, rf_dt=None, m0=None, start_block=1):
    seq = pp.Sequence()
    seq.read(seq_path)
    vox = voxel or make_voxel(n=n, T2prime=T2prime, b0=b0)
    x, y, z, df = vox['x'], vox['y'], vox['z'], vox['df']
    N = len(x)
    mx, my, mz = (np.zeros(N), np.zeros(N), np.ones(N)) if m0 is None else (m0[0] * np.ones(N), m0[1] * np.ones(N), m0[2] * np.ones(N))
    t_abs = 0.0
    sig, tads, snaps = [], [], {}
    nblk = len(seq.block_events)
    for ib in range(start_block, (max_blocks or nblk) + 1):
        blk = seq.get_block(ib)
        dur = seq.block_durations[ib]
        g = {ax: _grad_pts(getattr(blk, 'g' + ax, None)) for ax in 'xyz'}
        if blk.rf is None:
            if blk.adc is not None:
                a = blk.adc
                ts = a.delay + (np.arange(a.num_samples) + 0.5) * a.dwell
                kx, ky, kz = (_cumint(g[ax], ts) for ax in 'xyz')
                ph = 2 * np.pi * (np.outer(kx, x) + np.outer(ky, y) + np.outer(kz, z) + np.outer(ts, df))
                mxy = (mx + 1j * my)[None, :] * np.exp(-1j * ph) * np.exp(-ts / T2)[:, None]
                sig.append(mxy.mean(axis=1))
                tads.append(t_abs + ts)
            te = np.array([dur])
            kx, ky, kz = (_cumint(g[ax], te)[0] for ax in 'xyz')
            ph = 2 * np.pi * (kx * x + ky * y + kz * z + dur * df)
            mxy = (mx + 1j * my) * np.exp(-1j * ph) * np.exp(-dur / T2)
            mx, my = mxy.real, mxy.imag
            mz = 1 + (mz - 1) * np.exp(-dur / T1)
        else:
            rf = blk.rf
            dt = rf_dt or seq.rf_raster_time
            nt = int(round(dur / dt))
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
        t_abs += dur
        if ib in snapshot_blocks:
            snaps[ib] = (mx.copy(), my.copy(), mz.copy())
    s = np.concatenate(sig) if sig else np.zeros(0)
    nper = [len(q) for q in sig]
    edges = np.cumsum([0] + nper)
    if not nper:
        return dict(snapshots=snaps, voxel=vox, echo_center=np.zeros(0))
    centre = np.array([abs(s[edges[i] + nper[i] // 2]) for i in range(len(nper))])
    peak = np.array([abs(s[edges[i]:edges[i + 1]]).max() for i in range(len(nper))])
    return dict(echo_center=centre, echo_peak=peak, signal=s,
                t_adc=np.concatenate(tads) if tads else s, snapshots=snaps, voxel=vox)


def write_csvs(seq_path, res, vox, prefix='bloch'):
    """Same CSV files koma_sim.jl writes (<name>_<prefix>_signal/echoes.csv)."""
    import os
    stem = os.path.splitext(seq_path)[0]
    s = res['signal']
    np.savetxt(f'{stem}_{prefix}_signal.csv', np.c_[res['t_adc'], s.real, s.imag], delimiter=',')
    e = res['echo_center']
    np.savetxt(f'{stem}_{prefix}_echoes.csv', np.c_[np.arange(1, len(e) + 1), e, res['echo_peak']], delimiter=',')


def snapshot_csv(seq_path, vox, prefix='bloch', **kw):
    """Simulate every <name>_snap/snap_NN.seq (from snapshot_seqs.py) to its end and write
    <name>_<prefix>_snapshots_t.csv: snap #, z, Mxy re, Mxy im, Mz (same layout as koma_sim.jl)."""
    import glob
    import os
    stem = os.path.splitext(seq_path)[0]
    files = sorted(glob.glob(os.path.join(stem + '_snap', 'snap_*.seq')))
    rows = []
    for k, f in enumerate(files, 1):
        q = pp.Sequence()
        q.read(f)
        nb = max(q.block_events)
        r = simulate(f, voxel=vox, snapshot_blocks=(nb,), **kw)
        mx, my, mz = r['snapshots'][nb]
        rows.append(np.c_[np.full(len(mx), k), vox['z'], mx, my, mz])
        print(f'{os.path.basename(f)}: |mean Mxy| = {abs((mx + 1j * my).mean()):.4f}, mean Mz = {mz.mean():.4f}')
    if rows:
        np.savetxt(f'{stem}_{prefix}_snapshots_t.csv', np.vstack(rows), delimiter=',')
    return len(rows)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('seq')
    ap.add_argument('--b1', type=float, default=1.0)
    ap.add_argument('--b0', type=float, default=0.0)
    ap.add_argument('--n', type=int, default=20000)
    ap.add_argument('--csv', action='store_true',
                    help='write <name>_bloch_signal/echoes.csv, and <name>_bloch_snapshots_t.csv if <name>_snap/ '
                         'exists (plot with: python plot_koma.py <name> --sim bloch)')
    a = ap.parse_args()
    vox = make_voxel(n=a.n, b0=a.b0)
    r = simulate(a.seq, b1=a.b1, voxel=vox)
    print('echo |center| =', np.round(r['echo_center'], 4))
    if a.csv:
        write_csvs(a.seq, r, vox)
        snapshot_csv(a.seq, vox, b1=a.b1)
