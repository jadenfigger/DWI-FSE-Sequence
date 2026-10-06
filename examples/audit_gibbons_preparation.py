"""Locate why the existing adaptation's pre-RF Mx differs from Gibbons Fig. 3.

This traces the existing waveforms; it does not claim a paper reproduction.
"""
import hashlib
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pypulseq as pp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dwfse import simulate
from examples.compare_prepared_fse import build, profiles, pe_moments, SPOIL


def trace(key, b1=1., T1=1.5, T2=.08, suppress_leading_crusher=False):
    seq, info = build(key, 45.)
    ids, starts, durations = simulate.block_times(seq)
    start = dict(zip(ids, starts))
    end = dict(zip(ids, starts + durations))
    tip = info['tip_block']
    first = info['imaging_rf_blocks'][0]
    block = seq.get_block(first)
    # Point C in the paper's schematic is at the entrance to the imaging
    # train. The earlier gallery samples later, after the leading crusher.
    events = [
        ('Before added dephasing', start[tip-2]),
        ('After added dephasing', end[tip-2]),
        ('After compensated tip', info['after_tip_s']),
    ]
    if key == 'ss_mgot':
        events.extend([
            ('After Gy spoiler', info['after_spoiler_s']),
            ('After re-excitation / compensation', end[info['reexcitation_block']]),
        ])
    events.extend([
        ('Before imaging crusher', start[first]),
        ('Before RF waveform (old snapshot)', start[first]+block.rf.delay-4e-6),
    ])
    times = np.array([t for _, t in events])
    area = float(simulate._cumint(simulate.grad_pts(block.gz), block.rf.delay-4e-6))
    if suppress_leading_crusher:
        # Causal diagnostic only: remove just Gz before RF onset, preserving
        # RF, subsequent gradients, preparation and all elapsed times.
        g = block.gz
        g.waveform = g.waveform.copy()
        g.waveform[g.tt < block.rf.delay] = 0.
        if hasattr(g, 'id'): del g.id
        seq.set_block(first, block.rf, g, pp.make_delay(block.block_duration))
    grid = 1025
    z = np.linspace(-.001, .001, grid)
    y = np.array([0., -1/(4*SPOIL), 1/(4*SPOIL)])
    voxel = dict(x=np.zeros(grid*3), y=np.repeat(y, grid), z=np.tile(z, 3), df=np.zeros(grid*3))
    result = simulate.simulate(seq, b1=b1, T1=T1, T2=T2, voxel=voxel,
                               snap_times=times, rf_dt=4e-6, max_blocks=first)
    m = np.array([s[1:] for s in result['snapshots']])
    assert len(m) == len(times)
    avg = profiles(m, grid, 'average', pe_moments(seq, info, times))
    assert np.isfinite(avg).all()
    metrics = []
    for (label, t), state in zip(events, avg):
        mask = abs(z) <= .0005
        metrics.append(dict(landmark=label, time_ms=(t-info['initial_excitation_s'])*1000,
                            max_abs_mx=float(np.max(abs(state[0, mask]))),
                            rms_mx=float(np.sqrt(np.mean(state[0, mask]**2))),
                            rms_my=float(np.sqrt(np.mean(state[1, mask]**2)))))
    return dict(key=key, b1=b1, z=z, events=events, average=avg, local=m[:, :, :grid],
                metrics=metrics, leading_gz_moment_cycles_m=area,
                duration_since_exc_ms=(times-info['initial_excitation_s'])*1000)


def main():
    folder = ROOT/'docs/figures/gibbons_preparation_audit'
    folder.mkdir(parents=True, exist_ok=True)
    traces = []
    for b1 in [1., .8]:
        records = [trace(key, b1) for key in ['alsop', 'ss_mgot']]
        fig, axes = plt.subplots(2, 3, figsize=(13, 7), sharex=True, sharey=True)
        for row, r in enumerate(records):
            for k, ax in enumerate(axes[row]):
                ax.plot(r['z']*1000, r['average'][-2, k], color=['#2166ac','#d6604d','#228833'][k], lw=1)
                ax.axhline(0, color='#888', lw=.5);ax.axvspan(-.5,.5,color='#bbb',alpha=.15)
                ax.set_ylim(-1.05,1.05);ax.grid(alpha=.15)
                if row == 0:ax.set_title(['Mx / M0','My / M0','Mz / M0'][k])
                else:ax.set_xlabel('z (mm)')
            axes[row,0].set_ylabel(r['key']+' adaptation')
        fig.suptitle('Preparation endpoint before leading imaging crusher\n'
                     f'Existing substitute-pulse models; RF {b1*100:.0f}%, initial phase 45 deg; not a Gibbons reproduction', fontsize=13)
        fig.tight_layout(rect=(0,0,1,.9))
        fig.savefig(folder/f'pre_crusher_components_rf{b1*100:03.0f}.png',dpi=150)
        fig.savefig(folder/f'pre_crusher_components_rf{b1*100:03.0f}.svg')
        plt.close(fig)
        fig, axes = plt.subplots(6, 3, figsize=(14, 16), sharex=True, sharey=True)
        for method, r in enumerate(records):
            indices = [len(r['events'])-3, len(r['events'])-2, len(r['events'])-1]
            for j, index in enumerate(indices):
                row = method*3+j
                for component, ax in enumerate(axes[row]):
                    ax.plot(r['z']*1000, r['average'][index, component], lw=1,
                            color=['#2166ac', '#d6604d', '#228833'][component])
                    ax.axhline(0, color='#888', lw=.5)
                    ax.axvspan(-.5, .5, color='#bbb', alpha=.15)
                    ax.set_ylim(-1.05, 1.05); ax.grid(alpha=.15)
                    if row == 0: ax.set_title(['Mx / M0', 'My / M0', 'Mz / M0'][component])
                    if row == 5: ax.set_xlabel('z (mm)')
                axes[row, 0].set_ylabel(r['key']+'\n'+r['events'][index][0].replace(' / ', '\n')+
                                        f'\n{r["duration_since_exc_ms"][index]:.3f} ms', fontsize=9)
        fig.suptitle(f'Where transverse Mx appears in the existing preparation adaptations\n'
                     f'RF {b1*100:.0f}%, initial phase 45 deg; coherent y average; T1 1.5 s, T2 80 ms', fontsize=14)
        fig.tight_layout(rect=(0, 0, 1, .95))
        fig.savefig(folder/f'crusher_trace_rf{b1*100:03.0f}.png', dpi=140)
        plt.close(fig)
        for r in records:
            traces.append({k:v for k,v in r.items() if k in ['key','b1','metrics','leading_gz_moment_cycles_m']})
            print(r['key'], b1, json.dumps(r['metrics'][-3:]), flush=True)
    normal = trace('ss_mgot')
    removed = trace('ss_mgot', suppress_leading_crusher=True)
    # With no RF between the two snapshots, Gz can only phase-rotate Mxy.
    before = normal['average'][-2, 0]+1j*normal['average'][-2, 1]
    dt = (normal['events'][-1][1]-normal['events'][-2][1])
    predicted = before*np.exp(-dt/.08)*np.exp(-2j*np.pi*normal['leading_gz_moment_cycles_m']*normal['z'])
    actual = normal['average'][-1, 0]+1j*normal['average'][-1, 1]
    error = float(np.max(abs(predicted-actual)))
    assert error < 1e-10
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True)
    for ax, r, title in zip(axes, [normal, removed], ['Played leading crusher', 'Leading crusher removed (diagnostic)']):
        for k, color in enumerate(['#2166ac', '#d6604d']):
            ax.plot(r['z']*1000, r['average'][-1, k], color=color, label=['Mx','My'][k])
        ax.set_title(title);ax.set_ylim(-1.05, 1.05);ax.set_xlabel('z (mm)');ax.grid(alpha=.15)
    axes[0].set_ylabel('Component / M0');axes[1].legend()
    fig.suptitle('Same ss-MGOT preparation and pre-RF time; isolate the crusher phase\nNominal RF, initial phase 45 deg; diagnostic is not a replacement sequence')
    fig.tight_layout(rect=(0, 0, 1, .87))
    fig.savefig(folder/'leading_crusher_control.png', dpi=150);plt.close(fig)
    result = dict(traces=traces, phase_rotation_prediction_max_error=error,
                  removed_crusher_metrics=removed['metrics'][-1],
                  source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
                                 for p in ['examples/audit_gibbons_preparation.py','examples/compare_prepared_fse.py','dwfse/simulate.py']},
                  source_pdf_sha256={p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
                                     for p in ['C:/Users/jaden/Downloads/Gibbons_2017.pdf',
                                               'C:/Users/jaden/Downloads/mrm26971-sup-0001-suppinfo01.pdf']})
    (ROOT/'docs/data/gibbons_preparation_audit.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('Crusher rotation check', error, 'control', removed['metrics'][-1], flush=True)


if __name__ == '__main__': main()
