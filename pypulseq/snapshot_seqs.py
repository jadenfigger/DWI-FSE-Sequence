"""
snapshot_seqs.py - make copies of a .seq that stop at chosen times, so a simulator
that can only return the final state (KomaMRI "state", bloch_sim.py) gives a
snapshot of the magnetization at that time, e.g. at the centre of every ADC (echo).

    python snapshot_seqs.py my.seq --at adc              # one cut per ADC centre (echo)
    python snapshot_seqs.py my.seq --at adc --adc 1 2    # only ADC windows 1 and 2
    python snapshot_seqs.py my.seq --at rf               # right after each RF pulse ends
    python snapshot_seqs.py my.seq --times 18.5 54.9     # any times [ms]
    python snapshot_seqs.py my.seq --blocks 7 11         # end of these blocks (= koma snap_blocks)

Writes <name>_snap/snap_NN.seq (time order) and <name>_snap/index.csv
(snap #, time [ms], block, what). koma_sim.jl simulates every file in that folder
and plot_koma.py labels the panels from index.csv. Times are rounded to the
gradient raster; a time inside an RF pulse is refused.
"""
import argparse
import csv
import os

import numpy as np
import pypulseq as pp


def grad_points(g):
    if g.type == 'trap':
        t = np.array([0, g.rise_time, g.rise_time + g.flat_time, g.rise_time + g.flat_time + g.fall_time])
        a = np.array([0, g.amplitude, g.amplitude, 0.0])
    else:
        t, a = np.asarray(g.tt, float), np.asarray(g.waveform, float)
    return t + g.delay, a


def cut_grad(g, t_cut, system):
    """Gradient of a block truncated at t_cut (s, from block start), or None if it starts later."""
    t, a = grad_points(g)
    if t[0] >= t_cut:
        return None
    keep = t < t_cut
    tt = np.r_[t[keep], t_cut]
    aa = np.r_[a[keep], np.interp(t_cut, t, a)]
    if tt[0] > 0 and aa[0] != 0:          # waveform continuing from the previous block: start at 0
        tt, aa = np.r_[0.0, tt], np.r_[aa[0], aa]
    r = system.grad_raster_time
    tt = np.round(tt / r) * r
    tt, idx = np.unique(tt, return_index=True)
    return pp.make_extended_trapezoid(channel=g.channel, times=tt, amplitudes=aa[idx], system=system,
                                      skip_check=True)


def block_starts(seq):
    ids = sorted(seq.block_events)
    dur = np.array([seq.block_durations[i] for i in ids])
    return ids, np.r_[0, np.cumsum(dur)[:-1]], dur


def cut_sequence(seq, t_abs, system):
    """New Sequence identical to seq up to absolute time t_abs (s), then stopping."""
    ids, starts, dur = block_starts(seq)
    k = int(np.searchsorted(starts + dur, t_abs - 1e-12))     # block containing t_abs
    out = pp.Sequence(system)
    for i in ids[:k]:
        out.add_block(seq.get_block(i))
    if k >= len(ids):
        return out, ids[-1]
    b = seq.get_block(ids[k])
    t_cut = round((t_abs - starts[k]) / system.grad_raster_time) * system.grad_raster_time
    if t_cut <= 0:
        return out, ids[k] - 1
    ev = []
    if b.rf is not None:
        rf_end = b.rf.delay + b.rf.shape_dur
        if b.rf.delay < t_cut < rf_end - 1e-12:
            raise ValueError(f't = {t_abs*1e3:.3f} ms is inside the RF pulse of block {ids[k]}')
        if t_cut >= rf_end - 1e-12:
            ev.append(b.rf)
    for ax in 'xyz':
        g = getattr(b, 'g' + ax, None)
        if g is not None:
            gc = cut_grad(g, t_cut, system)
            if gc is not None:
                ev.append(gc)
    ev.append(pp.make_delay(t_cut))
    out.add_block(*ev)
    return out, ids[k]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('seq')
    ap.add_argument('--at', choices=['adc', 'rf'], help='ADC centres or RF ends')
    ap.add_argument('--adc', nargs='*', type=int, help='with --at adc: only these ADC windows (1-based)')
    ap.add_argument('--times', nargs='*', type=float, default=[], help='times [ms]')
    ap.add_argument('--blocks', nargs='*', type=int, default=[], help='end of these blocks')
    ap.add_argument('--out', help='output folder (default <name>_snap)')
    a = ap.parse_args()

    seq = pp.Sequence()
    seq.read(a.seq)
    sysd = seq.system
    for key, attr in (('GradientRasterTime', 'grad_raster_time'), ('RadiofrequencyRasterTime', 'rf_raster_time'),
                      ('AdcRasterTime', 'adc_raster_time'), ('BlockDurationRaster', 'block_duration_raster')):
        if key in seq.definitions:
            setattr(sysd, attr, float(np.atleast_1d(seq.definitions[key])[0]))
    system = pp.Opts(grad_raster_time=sysd.grad_raster_time, rf_raster_time=sysd.rf_raster_time,
                     adc_raster_time=sysd.adc_raster_time, block_duration_raster=sysd.block_duration_raster,
                     max_grad=1e12, max_slew=1e15, grad_unit='Hz/m', slew_unit='Hz/m/s')
    ids, starts, dur = block_starts(seq)
    snaps = []                                            # (time s, what)
    n_adc = 0
    for i, s in zip(ids, starts):
        b = seq.get_block(i)
        if b.adc is not None:
            n_adc += 1
            if a.at == 'adc' and (not a.adc or n_adc in a.adc):
                snaps.append((s + b.adc.delay + b.adc.num_samples * b.adc.dwell / 2, f'ADC {n_adc} centre (echo)'))
        if b.rf is not None and a.at == 'rf':
            snaps.append((s + b.rf.delay + b.rf.shape_dur, f'end of RF in block {i}'))
    snaps += [(t * 1e-3, f't = {t:g} ms') for t in a.times]
    snaps += [(starts[ids.index(i)] + dur[ids.index(i)], f'end of block {i}') for i in a.blocks]
    if not snaps:
        raise SystemExit('nothing selected: use --at, --times or --blocks')
    snaps.sort()

    stem = os.path.splitext(a.seq)[0]
    out = a.out or stem + '_snap'
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):                             # stale files would be simulated too
        if f.startswith('snap_') and f.endswith('.seq'):
            os.remove(os.path.join(out, f))
    rows = []
    for n, (t, what) in enumerate(snaps, 1):
        cut, blk = cut_sequence(seq, t, system)
        for k, v in seq.definitions.items():
            if k not in ('TotalDuration',):
                cut.set_definition(k, v)
        cut.set_definition('SnapshotTime_ms', round(t * 1e3, 4))
        fn = os.path.join(out, f'snap_{n:02d}.seq')
        cut.write(fn)
        rows.append([n, round(t * 1e3, 4), blk, what])
        print(f'snap_{n:02d}.seq  t = {t*1e3:10.4f} ms  (block {blk})  {what}')
    with open(os.path.join(out, 'index.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['snap', 'time_ms', 'block', 'what'])
        w.writerows(rows)
    print(f'wrote {len(rows)} files + index.csv to {out}')


if __name__ == '__main__':
    main()
