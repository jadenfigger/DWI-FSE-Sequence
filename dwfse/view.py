"""
view.py - look at any Pulseq .seq file.

    python dw.py view my.seq                      # first TR: diagram + checks
    python dw.py view my.seq --blocks 19 35       # any block range
    python dw.py view my.seq --t0 0 --t1 60       # time window [ms]
    python dw.py view my.seq --mark 3 7 13        # mark blocks (e.g. snapshot points)

Writes (with --out DIR): diagram.png (every block numbered = Pulseq [BLOCKS] index),
kspace.png and view.txt. view.txt holds:
  * definitions and the PyPulseq timing check
  * block table (start, duration, contents)
  * RF table (centre time, flip, phase, use) and ADC centres
  * timing: TE (excitation -> first echo), echo spacing, RF spacing
  * gradient 0th moment per axis between successive refocusing pulses, and the half
    intervals around each echo (CPMG condition), with differing intervals flagged
  * b-value at every echo for the primary spin-echo pathway (all gradients)
  * k-space position (kx, ky, kz) at every ADC centre (phase-encode order check)
Refocusing pulses are taken from the RF 'use' field (or flip > 120 deg if unset).
"""
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from .simulate import block_times, grad_pts, read_seq

GAMMA = 42.577478e6
DT = 1e-6


def rf_flip_deg(rf, raster):
    """Flip from the RF waveform; works for sample-centred shapes and block pulses (corner points)."""
    t, sgn = np.asarray(rf.t, float), np.asarray(rf.signal)
    if len(t) < 2:
        return 360 * abs(sgn.sum()) * raster
    dts = np.diff(t)
    if np.allclose(dts, dts[0], rtol=1e-3) and abs(t[0] - dts[0] / 2) < 1e-9:
        return 360 * abs(sgn.sum() * dts[0])
    return 360 * abs(np.sum((sgn[1:] + sgn[:-1]) / 2 * dts))


def rf_centre(rf):
    c = getattr(rf, 'center', None)
    if c is None:
        a = np.abs(rf.signal)
        c = rf.t[int(np.argmax(a))]
    return rf.delay + c


def describe(seq, b):
    parts = []
    if b.rf is not None:
        use = (getattr(b.rf, 'use', '') or '')[:3]
        parts.append(f'RF {rf_flip_deg(b.rf, seq.rf_raster_time):.0f}deg ph {np.degrees(b.rf.phase_offset) % 360:.0f}deg {use}')
    gs = [ax for ax in 'xyz' if getattr(b, 'g' + ax, None) is not None]
    if gs:
        parts.append('G' + ''.join(gs))
    if b.adc is not None:
        parts.append(f'ADC {b.adc.num_samples}x{b.adc.dwell*1e6:g}us')
    return ', '.join(parts) if parts else 'delay'


def select_blocks(seq, blocks=None, t0=None, t1=None, max_blocks=150):
    """Block ids to show. Default: first TR = up to the first long (>100 ms) pure delay after the first RF."""
    ids, starts, dur = block_times(seq)
    if blocks:
        return [i for i in ids if blocks[0] <= i <= blocks[1]]
    if t0 is not None or t1 is not None:
        a, b = (t0 or 0) * 1e-3, (t1 if t1 is not None else 1e12) * 1e-3
        return [i for i, s, d in zip(ids, starts, dur) if s + d > a and s < b]
    first_rf = next((i for i in ids if seq.get_block(i).rf is not None), None)
    sel = []
    for i, d in zip(ids, dur):
        if first_rf is not None and i > first_rf and d > 0.1 and describe(seq, seq.get_block(i)) == 'delay':
            break
        sel.append(i)
    return sel[:max_blocks]


def events(seq, sel):
    """RF and ADC events (absolute times) and gradient breakpoints for the selected blocks."""
    ids, starts, dur = block_times(seq)
    rfs, adcs, pts = [], [], {ax: [] for ax in 'xyz'}
    for i in sel:
        k = ids.index(i)
        s = starts[k]
        b = seq.get_block(i)
        if b.rf is not None:
            use = getattr(b.rf, 'use', '') or ''
            flip = rf_flip_deg(b.rf, seq.rf_raster_time)
            ref = use.startswith('ref') or (use not in ('excitation',) and flip > 120)
            rfs.append(dict(block=i, t=s + rf_centre(b.rf), flip=flip, phase=np.degrees(b.rf.phase_offset) % 360,
                            ref=ref, use=use or ('refocusing?' if ref else 'excitation?')))
        if b.adc is not None:
            adcs.append(dict(block=i, t=s + b.adc.delay + b.adc.num_samples * b.adc.dwell / 2))
        for ax in 'xyz':
            p = grad_pts(getattr(b, 'g' + ax, None))
            if p is not None:
                pts[ax].append((p[0] + s, p[1]))
    return rfs, adcs, pts


def sample(pts, t):
    g = np.zeros((3, t.size))
    for j, ax in enumerate('xyz'):
        for tt, aa in pts[ax]:
            m = (t >= tt[0]) & (t <= tt[-1])
            g[j, m] += np.interp(t[m], tt, aa)
    return g


def analysis(seq, sel):
    ids, starts, dur = block_times(seq)
    rfs, adcs, pts = events(seq, sel)
    L = []
    say = L.append
    say('== definitions')
    for k, v in seq.definitions.items():
        say(f'  {k}: {v}')
    ok, err = seq.check_timing()
    say(f'== PyPulseq timing check: {"OK" if ok else f"FAILED ({len(err)})"}')
    for e in err[:5]:
        say(f'   {e}')
    say(f'== blocks {sel[0]}-{sel[-1]} of {len(ids)} (total duration {sum(dur):.4f} s)')
    say(f'{"block":>5} {"start [ms]":>11} {"dur [ms]":>9}  contents')
    for i in sel:
        k = ids.index(i)
        say(f'{i:5d} {starts[k]*1e3:11.3f} {dur[k]*1e3:9.3f}  {describe(seq, seq.get_block(i))}')
    say('== RF pulses')
    for r in rfs:
        say(f'  block {r["block"]:4d}  t {r["t"]*1e3:10.3f} ms  flip {r["flip"]:6.1f}  phase {r["phase"]:6.1f}  {r["use"]}')
    exc = [r for r in rfs if not r['ref']]
    ref = [r for r in rfs if r['ref']]
    ta = np.array([a['t'] for a in adcs])
    if exc and len(ta):
        t_exc = exc[0]['t']
        tr_ = [r['t'] for r in ref if r['t'] > t_exc]
        te = ta[ta > t_exc]
        say('== timing (from RF centres and ADC centres)')
        if len(te):
            say(f'  TE (excitation -> echo 1)  : {(te[0]-t_exc)*1e3:.4f} ms')
        if len(te) > 1:
            d = np.diff(te) * 1e3
            say(f'  echo spacing               : {d.min():.4f} .. {d.max():.4f} ms')
        if len(tr_) > 1:
            d = np.diff(tr_) * 1e3
            say(f'  refocusing spacing         : first {d[0]:.4f} ms, then {d[1:].min() if len(d) > 1 else float("nan"):.4f}'
                f' .. {d[1:].max() if len(d) > 1 else float("nan"):.4f} ms')
        # gradients on a fine grid from the excitation to the last echo
        tl = (te[-1] if len(te) else (tr_[-1] if tr_ else t_exc)) + 1e-3
        t = np.arange(t_exc, tl, DT)
        g = sample(pts, t)
        to_mtms = 1e3 / GAMMA * 1e3                     # Hz/m * s -> mT/m * ms

        def mom(a, b):
            m = (t >= a) & (t < b)
            return g[:, m].sum(axis=1) * DT * to_mtms

        if tr_:
            say('== gradient 0th moment [mT/m*ms] (x, y, z)')
            say('   CPMG condition: equal moment in every refocusing interval; '
                'excitation->1st refocusing and each half interval = half of it')
            say(f'  excitation -> refocus 1      : {np.array2string(mom(t_exc, tr_[0]), precision=3)}')
            ivs = [(a, b) for a, b in zip(tr_[:-1], tr_[1:])]
            ms = [mom(a, b) for a, b in ivs]
            for k, m in enumerate(ms):
                say(f'  refocus {k+1:2d} -> refocus {k+2:2d}     : {np.array2string(m, precision=3)}')
            if ms:
                ref_m = ms[1] if len(ms) > 1 else ms[0]
                bad = [k + 1 for k, m in enumerate(ms) if np.max(np.abs(m - ref_m)) > 0.01 * max(np.abs(ref_m).max(), 1e-6)]
                say(f'  intervals differing from refocus 2->3 by >1 %: {["%d->%d" % (k, k + 1) for k in bad] or "none"}')
            for k, (r, e) in enumerate(zip(tr_, te)):
                if k >= 3:
                    break
                nxt = tr_[k + 1] if k + 1 < len(tr_) else None
                s = f'  refocus {k+1} -> echo {k+1}: {np.array2string(mom(r, e), precision=3)}'
                if nxt:
                    s += f'   echo {k+1} -> refocus {k+2}: {np.array2string(mom(e, nxt), precision=3)}'
                say(s)
        say('== b-value at each echo, primary spin-echo pathway, all gradients [s/mm^2] (bxx, byy, bzz | trace)')
        sgn = np.ones_like(t)
        for r in tr_:
            sgn[t > r] *= -1
        k_rad = 2 * np.pi * np.cumsum(g * sgn, axis=1) * DT
        for j, e in enumerate(te):
            m = t <= e
            bd = (k_rad[:, m] ** 2).sum(axis=1) * DT * 1e-6
            say(f'  echo {j+1:2d} at {(e-t_exc)*1e3:8.3f} ms : {bd[0]:9.2f} {bd[1]:9.2f} {bd[2]:9.2f} | {bd.sum():9.2f}')
        say('== k-space at each ADC centre, spin-echo pathway [1/m] (kx, ky, kz)')
        for j, e in enumerate(te):
            kk = np.array([np.interp(e, t, k_rad[a]) for a in range(3)]) / (2 * np.pi)
            say(f'  echo {j+1:2d} : {kk[0]:9.2f} {kk[1]:9.2f} {kk[2]:9.2f}')
        return '\n'.join(L), dict(t=t, k=k_rad / (2 * np.pi), te=te, t_exc=t_exc)
    return '\n'.join(L), None


def diagram(seq, sel, marks=(), max_delay_ms=5.0, title=''):
    ids, starts, dur = block_times(seq)
    fig, ax = plt.subplots(5, 1, figsize=(15, 9), sharex=True, gridspec_kw=dict(height_ratios=[1.2, 1, 1, 1, 0.4]))
    names = ['RF |B1| [Hz]', 'Gx [mT/m]', 'Gy [mT/m]', 'Gz [mT/m]', 'ADC']
    td = 0.0
    for n, i in enumerate(sel):
        k = ids.index(i)
        b = seq.get_block(i)
        d = dur[k]
        is_delay = describe(seq, b) == 'delay'
        w = min(d, max_delay_ms * 1e-3) if is_delay else d
        x0, x1 = td * 1e3, (td + w) * 1e3
        for a in ax:
            if n % 2:
                a.axvspan(x0, x1, color='0.93', zorder=0)
            a.axvline(x0, color='0.75', lw=0.5, zorder=0)
        ax[0].text((x0 + x1) / 2, 1.02, f'{i}' + ('*' if is_delay and w < d else ''), transform=ax[0].get_xaxis_transform(),
                   ha='center', va='bottom', fontsize=8, rotation=90 if (x1 - x0) < 1.0 else 0)
        if b.rf is not None:
            tt = (b.rf.t + b.rf.delay) * 1e3 + x0
            amp = np.abs(b.rf.signal)
            tt, amp = np.r_[tt[0], tt, tt[-1]], np.r_[0, amp, 0]
            use = getattr(b.rf, 'use', '') or ''
            ax[0].plot(tt, amp, color='C3' if use.startswith('ref') else 'C0')
            ax[0].text(tt.mean(), amp.max(), f'{rf_flip_deg(b.rf, seq.rf_raster_time):.0f}°\nph {np.degrees(b.rf.phase_offset) % 360:.0f}°',
                       ha='center', va='bottom', fontsize=7)
        for j, axn in enumerate('xyz'):
            p = grad_pts(getattr(b, 'g' + axn, None))
            if p is not None:
                ax[j + 1].plot(p[0] * 1e3 + x0, p[1] / GAMMA * 1e3, color='C2', lw=1)
        if b.adc is not None:
            s = b.adc.delay * 1e3 + x0
            ax[4].axvspan(s, s + b.adc.num_samples * b.adc.dwell * 1e3, ymin=0.2, ymax=0.8, color='C1')
        if i in marks:
            for a in ax:
                a.axvline(x1, color='C3', lw=1.5, ls='--')
            ax[4].text(x1, 0.5, f' after {i}', color='C3', fontsize=8, va='center')
        td += w
    ax[0].set_ylim(0, ax[0].get_ylim()[1] * 1.35)
    for a, nm in zip(ax, names):
        a.set_ylabel(nm, fontsize=9)
    ax[4].set_yticks([])
    ax[-1].set_xlabel('display time [ms]  (* = long delay block drawn shortened; real times in view.txt)')
    fig.suptitle(f'{title}  blocks {sel[0]}-{sel[-1]}  (numbers = Pulseq block index)', y=0.995, fontsize=10)
    fig.tight_layout()
    return fig


def kspace_figure(kinfo):
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    t, k = kinfo['t'], kinfo['k']
    ax[0].plot(k[0], k[1], lw=0.6)
    ka = np.array([[np.interp(e, t, k[a]) for a in range(3)] for e in kinfo['te']])
    if len(ka):
        ax[0].plot(ka[:, 0], ka[:, 1], 'o', color='C3', ms=4, label='echo centres')
        span = max(np.ptp(ka[:, 1]), 50.0)
        ax[0].set_ylim(ka[:, 1].min() - span, ka[:, 1].max() + span)
        ax[0].set_xlim(-3 * span, 3 * span)
        ax[0].legend(fontsize=8)
        ax[1].plot(np.arange(1, len(ka) + 1), ka[:, 1], 'o-')
    ax[0].set_xlabel('kx [1/m]'); ax[0].set_ylabel('ky [1/m]'); ax[0].set_title('k-space (spin-echo pathway, zoomed)')
    ax[1].set_xlabel('echo #'); ax[1].set_ylabel('ky at echo centre [1/m]'); ax[1].set_title('phase-encode order')
    fig.tight_layout()
    return fig


def view(seq_path, out=None, blocks=None, t0=None, t1=None, marks=(), show=False):
    seq = read_seq(seq_path)
    sel = select_blocks(seq, blocks, t0, t1)
    if not sel:
        raise SystemExit('no blocks in the selected range')
    text, kinfo = analysis(seq, sel)
    figs = {'diagram': diagram(seq, sel, marks, title=str(seq_path))}
    if kinfo is not None and len(kinfo['te']):
        figs['kspace'] = kspace_figure(kinfo)
    if out:
        import os
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, 'view.txt'), 'w') as f:
            f.write(text + '\n')
        for k, f in figs.items():
            f.savefig(os.path.join(out, f'{k}.png'), dpi=110)
    if show and matplotlib.get_backend().lower() != 'agg':
        plt.show()
    plt.close('all')
    return text
