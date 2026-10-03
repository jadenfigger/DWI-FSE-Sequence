"""
plot_blocks.py - sequence diagram with every Pulseq block numbered.

Block numbers are the ones in the .seq file's [BLOCKS] table (1-based), which are
also the numbers koma_sim.jl uses for its snapshots (state AFTER block b).

    python plot_blocks.py dwfse_minimal.seq                      # first TR, numbered blocks + table
    python plot_blocks.py dwfse_minimal.seq --mark 3 7 13        # mark "snapshot after block b"
    python plot_blocks.py dwfse_minimal.seq --snap-csv dwfse_minimal_koma_snapshots.csv
    python plot_blocks.py dwfse_minimal.seq --blocks 19 35 --save tr2.png
    python plot_blocks.py my.seq --t0 0 --t1 60                  # time window in ms

Rows: RF magnitude (with flip/phase/use of each pulse), Gx, Gy, Gz, ADC windows.
Long pure-delay blocks are drawn compressed (--max-delay-ms) so short blocks stay readable;
the time axis is then "display time", and each block's real start time is in the table.
"""
import argparse

import matplotlib.pyplot as plt
import numpy as np
import pypulseq as pp

GAMMA = 42.577478e6


def grad_pts(g):
    if g is None:
        return None
    if g.type == 'trap':
        t = np.array([0, g.rise_time, g.rise_time + g.flat_time, g.rise_time + g.flat_time + g.fall_time])
        a = np.array([0, g.amplitude, g.amplitude, 0.0])
    else:
        t, a = np.asarray(g.tt, float), np.asarray(g.waveform, float)
    return t + g.delay, a


def describe(seq, i, b):
    parts = []
    if b.rf is not None:
        rf = b.rf
        dt = np.diff(rf.t).mean() if len(rf.t) > 1 else seq.rf_raster_time
        flip = 360 * abs(np.sum(rf.signal) * dt)
        use = getattr(rf, 'use', '') or ''
        parts.append(f'RF {flip:.0f}deg ph {np.degrees(rf.phase_offset) % 360:.0f}deg {use[:3]}')
    gs = [ax for ax in 'xyz' if getattr(b, 'g' + ax, None) is not None]
    if gs:
        parts.append('G' + ''.join(gs))
    if b.adc is not None:
        parts.append(f'ADC {b.adc.num_samples}x{b.adc.dwell*1e6:.0f}us')
    if getattr(b, 'label', None) is not None:
        parts.append('labels')
    return ', '.join(parts) if parts else 'delay'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('seq')
    ap.add_argument('--blocks', nargs=2, type=int, help='first and last block to show')
    ap.add_argument('--t0', type=float, help='window start [ms] (real time)')
    ap.add_argument('--t1', type=float, help='window end [ms] (real time)')
    ap.add_argument('--mark', nargs='*', type=int, default=[], help='blocks to mark as "snapshot after block"')
    ap.add_argument('--snap-csv', help='koma *_snapshots.csv: mark the blocks it contains')
    ap.add_argument('--max-delay-ms', type=float, default=5.0, help='draw longer delay-only blocks this wide')
    ap.add_argument('--save', help='save figure to this file')
    a = ap.parse_args()

    seq = pp.Sequence()
    seq.read(a.seq)
    ids = sorted(seq.block_events)
    dur = np.array([seq.block_durations[i] for i in ids])
    start = np.concatenate([[0], np.cumsum(dur)[:-1]])
    blocks = {i: seq.get_block(i) for i in ids}

    if a.blocks:
        sel = [i for i in ids if a.blocks[0] <= i <= a.blocks[1]]
    elif a.t0 is not None or a.t1 is not None:
        t0 = (a.t0 or 0) * 1e-3
        t1 = (a.t1 if a.t1 is not None else 1e9) * 1e-3
        sel = [i for i, s, d in zip(ids, start, dur) if s + d > t0 and s < t1]
    else:                                   # default: up to the first long delay after the first RF (= one TR)
        first_rf = next(i for i in ids if blocks[i].rf is not None)
        sel = []
        for i, d in zip(ids, dur):
            if i > first_rf and d > 0.1 and describe(seq, i, blocks[i]) == 'delay':
                break
            sel.append(i)
    marks = set(a.mark)
    if a.snap_csv:
        marks |= set(np.unique(np.loadtxt(a.snap_csv, delimiter=',', usecols=0)).astype(int).tolist())

    # ---- table -----------------------------------------------------------------
    print(f'{"block":>5} {"start [ms]":>11} {"dur [ms]":>9}  contents')
    for i in sel:
        k = ids.index(i)
        flag = '   <- snapshot after this block' if i in marks else ''
        print(f'{i:5d} {start[k]*1e3:11.3f} {dur[k]*1e3:9.3f}  {describe(seq, i, blocks[i])}{flag}')

    # ---- figure (display time: long delays compressed) -------------------------
    fig, ax = plt.subplots(5, 1, figsize=(15, 9), sharex=True,
                           gridspec_kw=dict(height_ratios=[1.2, 1, 1, 1, 0.4]))
    names = ['RF |B1| [Hz]', 'Gx [mT/m]', 'Gy [mT/m]', 'Gz [mT/m]', 'ADC']
    td = 0.0
    maxd = a.max_delay_ms * 1e-3
    for n, i in enumerate(sel):
        k = ids.index(i)
        b = blocks[i]
        d = dur[k]
        is_delay = describe(seq, i, b) == 'delay'
        w = min(d, maxd) if is_delay else d
        x0, x1 = td * 1e3, (td + w) * 1e3
        for axk in ax:
            if n % 2:
                axk.axvspan(x0, x1, color='0.93', zorder=0)
            axk.axvline(x0, color='0.75', lw=0.5, zorder=0)
        lab = f'{i}' + ('*' if is_delay and d > maxd else '')
        ax[0].text((x0 + x1) / 2, 1.02, lab, transform=ax[0].get_xaxis_transform(), ha='center', va='bottom',
                   fontsize=8, rotation=90 if (x1 - x0) < 1.0 else 0)
        if not is_delay or d <= maxd:
            if b.rf is not None:
                t = (b.rf.t + b.rf.delay) * 1e3 + x0
                ax[0].plot(t, np.abs(b.rf.signal), color='C3' if (b.rf.use or '').startswith('ref') else 'C0')
                dt = np.diff(b.rf.t).mean()
                flip = 360 * abs(np.sum(b.rf.signal) * dt)
                ax[0].text(t.mean(), np.abs(b.rf.signal).max(), f'{flip:.0f}°\nph {np.degrees(b.rf.phase_offset) % 360:.0f}°',
                           ha='center', va='bottom', fontsize=7)
            for j, axn in enumerate('xyz'):
                p = grad_pts(getattr(b, 'g' + axn, None))
                if p is not None:
                    ax[j + 1].plot(p[0] * 1e3 + x0, p[1] / GAMMA * 1e3, color='C2', lw=1)
            if b.adc is not None:
                s = b.adc.delay * 1e3 + x0
                ax[4].axvspan(s, s + b.adc.num_samples * b.adc.dwell * 1e3, ymin=0.2, ymax=0.8, color='C1')
        if i in marks:
            for axk in ax:
                axk.axvline(x1, color='C3', lw=1.5, ls='--')
            ax[4].text(x1, 0.5, f' after {i}', color='C3', fontsize=8, va='center')
        td += w
    lo, hi = ax[0].get_ylim()
    ax[0].set_ylim(0, hi * 1.35)                     # room for the flip/phase labels
    for axk, nm in zip(ax, names):
        axk.set_ylabel(nm, fontsize=9)
    ax[4].set_yticks([])
    ax[-1].set_xlabel('display time [ms]  (* = delay block drawn shortened; real times in the printed table)')
    fig.suptitle(f'{a.seq}: blocks {sel[0]}-{sel[-1]} (numbers = Pulseq block index; red dashed = snapshot point)',
                 y=0.995, fontsize=10)
    fig.tight_layout()
    if a.save:
        fig.savefig(a.save, dpi=120)
        print('saved', a.save)
    else:
        plt.show()


if __name__ == '__main__':
    main()
