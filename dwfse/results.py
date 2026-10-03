"""
results.py - plot simulation results (results.npz from simulate.run) and compare runs.

    python dw.py plot runs/NAME                 # signal.png, echoes.png, snapshots.png
    python dw.py plot runs/NAME --snaps 1 2     # choose snapshot panels
    python dw.py compare runs/A runs/B ...      # overlay echoes and signal of several runs

Snapshot panels show every isochromat vs z: |Mxy|, phase(Mxy), Mz. At an echo centre the
refocused part has a flat phase across z; magnetization still wound by crushers or
diffusion lobes does not contribute to that echo. Mz only changes at RF pulses (and
slowly by T1), so it shows what each refocusing pulse stored as longitudinal magnetization.
"""
import os

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from .simulate import load_npz


def _windows(r):
    edges = np.cumsum(np.r_[0, r['adc_sizes']])
    return [slice(edges[i], edges[i + 1]) for i in range(len(r['adc_sizes']))]


def _te(r):
    """Echo times relative to the first excitation (the first TR's excitation for multi-TR runs)."""
    return np.array([t - _last_exc(r, t) for t in r['echo_t']])


def _last_exc(r, t):
    """Centre of the most recent excitation before time t (each echo's own TR)."""
    ex = np.atleast_1d(r.get('t_exc_all', r.get('t_exc', 0.0)))
    ex = ex[ex <= t]
    return float(ex[-1]) if len(ex) else 0.0


def _lab(r, i):
    return f"B1 {r['b1'][i]:.2f}" + (f", B0 {r['b0'][i]:+.0f} Hz" if np.any(r['b0'] != 0) else '')


def plot_run(run_dir, snaps=None, max_snaps=8):
    r = load_npz(os.path.join(run_dir, 'results.npz'))
    figs = {}
    t = r['t_adc'] * 1e3
    # signal
    fig, ax = plt.subplots(figsize=(12, 3.8))
    for i in range(len(r['b1'])):
        for k, w in enumerate(_windows(r)):
            ax.plot(t[w], np.abs(r['signal'][i][w]), color=f'C{i}', lw=1, label=_lab(r, i) if k == 0 else None)
    ax.set_xlabel('time [ms]'); ax.set_ylabel('|signal| / M0'); ax.legend(fontsize=8)
    ax.set_title(f'{run_dir}: signal in every ADC window')
    figs['signal'] = fig
    # echoes
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
    n = np.arange(1, r['echo_center'].shape[1] + 1)
    for i in range(len(r['b1'])):
        ax[0].plot(n, r['echo_center'][i], 'o-', color=f'C{i}', label=_lab(r, i))
        ax[1].plot(_te(r) * 1e3, r['echo_center'][i], 'o-', color=f'C{i}')
    ax[0].set_xlabel('echo #'); ax[1].set_xlabel('echo time after excitation [ms]')
    ax[0].set_ylabel('|signal| at k-centre sample'); ax[0].legend(fontsize=8)
    ax[0].set_title('echo amplitudes')
    if len(r['b1']) > 1 and np.all(r['b0'] == r['b0'][0]):
        fig2, a2 = plt.subplots(figsize=(5.5, 3.8))
        for e in range(min(r['echo_center'].shape[1], 8)):
            a2.plot(r['b1'], r['echo_center'][:, e], 'o-', label=f'echo {e+1}')
        a2.set_xlabel('B1 scale'); a2.set_ylabel('|signal|'); a2.set_title('B1 sensitivity'); a2.legend(fontsize=7)
        fig2.tight_layout()
        figs['b1_sweep'] = fig2
    fig.tight_layout()
    figs['echoes'] = fig
    # snapshots
    ns = len(r['snap_t'])
    if ns:
        ids = [s - 1 for s in snaps if 1 <= s <= ns] if snaps else list(range(min(ns, max_snaps)))
        z = r['z'] * 1e3
        o = np.argsort(z)
        fig, axs = plt.subplots(3, len(ids), figsize=(2.6 * len(ids) + 0.8, 7), sharex=True, sharey='row', squeeze=False)
        for j, s in enumerate(ids):
            mxy = (r['snap_mx'][s] + 1j * r['snap_my'][s])[o]
            axs[0, j].plot(z[o], np.abs(mxy), '.', ms=1)
            axs[1, j].plot(z[o], np.angle(mxy), '.', ms=1)
            axs[2, j].plot(z[o], r['snap_mz'][s][o], '.', ms=1)
            axs[0, j].set_title(f"#{s+1} {r['snap_label'][s]}\n{(r['snap_t'][s] - _last_exc(r, r['snap_t'][s]))*1e3:.2f} ms after exc.  |mean Mxy|={abs(mxy.mean()):.3f}",
                                fontsize=8)
            axs[2, j].set_xlabel('z [mm]')
        axs[0, 0].set_ylabel('|Mxy|'); axs[1, 0].set_ylabel('phase Mxy [rad]'); axs[2, 0].set_ylabel('Mz')
        fig.suptitle(f'{run_dir}: magnetization vs z ({_lab(r, 0)})', fontsize=10)
        fig.tight_layout()
        figs['snapshots'] = fig
    for k, f in figs.items():
        f.savefig(os.path.join(run_dir, f'{k}.png'), dpi=110)
    plt.close('all')
    return figs.keys()


def summary_text(run_dir):
    r = load_npz(os.path.join(run_dir, 'results.npz'))
    lines = [f'{"":14s}' + ''.join(f'  echo{e+1:<3d}' for e in range(r['echo_center'].shape[1]))]
    lines.append(f'{"TE [ms]":14s}' + ''.join(f'{t*1e3:9.2f}' for t in _te(r)))
    for i in range(len(r['b1'])):
        lines.append(f'{_lab(r, i):14s}' + ''.join(f'{v:9.4f}' for v in r['echo_center'][i]))
    return '\n'.join(lines)


def compare(run_dirs, out=None):
    rs = [(d, load_npz(os.path.join(d, 'results.npz'))) for d in run_dirs]
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.2))
    print(f'{"run":30s} B1     echoes |k-centre|')
    for j, (d, r) in enumerate(rs):
        name = os.path.basename(os.path.normpath(d))
        for i in range(len(r['b1'])):
            ls = '-' if i == 0 else '--'
            lab = name + ('' if len(r['b1']) == 1 else f' ({_lab(r, i)})')
            ax[0].plot(np.arange(1, r['echo_center'].shape[1] + 1), r['echo_center'][i], 'o' + ls, color=f'C{j}', label=lab)
            ax[1].plot(_te(r) * 1e3, r['echo_center'][i], 'o' + ls, color=f'C{j}')
            print(f'{name:30s} {r["b1"][i]:.2f}  {np.round(r["echo_center"][i], 4)}')
        t = r['t_adc'] * 1e3
        for k, w in enumerate(_windows(r)):
            ax[2].plot(t[w] - r['echo_t'][0] * 1e3, np.abs(r['signal'][0][w]), color=f'C{j}', lw=1,
                       label=name if k == 0 else None)
    ax[0].set_xlabel('echo #'); ax[0].set_ylabel('|signal| at k-centre sample'); ax[0].legend(fontsize=8)
    ax[1].set_xlabel('echo time after excitation [ms]')
    ax[2].set_xlabel('time after echo 1 [ms]'); ax[2].set_ylabel('|signal| (first B1)'); ax[2].legend(fontsize=8)
    ax[0].set_title('echo amplitudes'); ax[1].set_title('vs time'); ax[2].set_title('signal')
    fig.tight_layout()
    out = out or os.path.join(os.path.dirname(os.path.normpath(run_dirs[0])),
                              'compare_' + '_vs_'.join(os.path.basename(os.path.normpath(d)) for d in run_dirs) + '.png')
    fig.savefig(out, dpi=110)
    if matplotlib.get_backend().lower() != 'agg':
        plt.show()
    plt.close('all')
    return out
