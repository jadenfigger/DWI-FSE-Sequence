"""Matched ADC-center Bloch and stimulated-pathway snapshots.

Run from the repository root: python examples/compare_echo_snapshots.py
PNG deliverables are kept together; raw sequences and arrays live under runs/.
The spatial pathway reconstruction is restricted to the stationary D=0,
one-box-voxel, instantaneous-RF model and checked against the existing exact
enumerator. It is not a decomposition of the finite-RF Bloch simulation.
"""
import argparse
import csv
import json
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dwfse import epg, generate, pathways, simulate
from examples.improve_ppl import BASE, VARIANTS

UP = [1, 1, 1.4, 1.8, 2.2, 2.6, 3, 3.4]
DOWN = [1, 3.4, 3, 2.6, 2.2, 1.8, 1.4, 1]
CASES = [
    ('01_original', 'Original constant crushers', VARIANTS['base']),
    ('02_linear_increasing', 'Linearly increasing crushers', VARIANTS['linear_crushers']),
    ('03_irregular', 'Irregular crushers', VARIANTS['irregular_crushers']),
    ('04_alternating', 'Alternating crusher polarity', VARIANTS['alternate']),
    ('05_rf_xy', 'RF phases alternate by 90 degrees', VARIANTS['phase_xy']),
    ('06_rf_180', 'RF phases alternate by 180 degrees', VARIANTS['phase_alternate']),
    ('07_rf_quadratic', 'Quadratic RF phase progression', VARIANTS['phase_quadratic']),
    ('08_linear_decreasing', 'Linearly decreasing crushers', dict(sim_train_crusher_scales=DOWN)),
    ('09_linear_centered', 'Increasing crushers and corrected timing', VARIANTS['centered_linear']),
    ('10_alternating_increasing', 'Alternating and increasing crushers',
     dict(sim_train_crusher_scales=[v * (-1 if k % 2 else 1) for k, v in enumerate(UP)])),
]
COLORS = dict(primary='#2166ac', stimulated='#d6604d', other='#888888', total='#111111')


def adc_centers(seq):
    """Use an actual middle ADC sample, not the unsampled geometric midpoint."""
    ids, starts, _ = simulate.block_times(seq)
    result = []
    for bid, start in zip(ids, starts):
        adc = seq.get_block(bid).adc
        if adc is not None:
            result.append(start + adc.delay + (adc.num_samples // 2 + .5) * adc.dwell)
    return np.array(result)


def category(history, primary):
    if history == primary:
        return 'primary'
    # Recovery lineages are distinct from stimulus stored from the excitation.
    if 'Z' in history and 'Z0' not in history:
        return 'stimulated'
    return 'other'


def spatial_pathways(seq, data, metrics, z):
    """Reconstruct transverse primary/stored/other fields across the 1-mm box.

    Average analytically over x/y and the Lorentzian B0 distribution. Integrate
    the z dependence analytically too to check against enumerate_center_pathways.
    All RF branching reuses the existing exact enumerator's coefficients.
    """
    diffusivity = float(data.D.flatten()[0])
    # MRzero floors a requested D=0 to 1e-6 in its internal units. Retain the
    # floor in both transverse and longitudinal evolution for exact closure.
    if seq.normalized_grads or diffusivity > 1.1e-6:
        raise ValueError('spatial reconstruction requires physical gradients and D=0')
    t1, t2, t2p = [float(v.flatten()[0]) for v in (data.T1, data.T2, data.T2dash)]
    b0 = float(data.B0.flatten()[0])
    paths = [pathways._Path('z', 1 + 0j, np.zeros(4), +1, (), True)]
    outputs = []
    xy_cache = {}
    for index, rep in enumerate(seq):
        paths = pathways._branch(paths, pathways._rf_coefficients(rep, data))
        dt = rep.event_time.detach().cpu().numpy().astype(float)
        gm = rep.gradm.detach().cpu().numpy().astype(float)
        trajectory = np.cumsum(np.column_stack((gm, dt)), axis=0)
        events = np.flatnonzero(rep.adc_usage.detach().cpu().numpy() > 0)
        if len(events):
            metric = metrics[len(outputs)]
            event = int(events[len(events) // 2])
            spatial = {key: {} for key in ('primary', 'stimulated', 'other')}
            sums = {key: 0j for key in spatial}
            for path in paths:
                if path.kind != 'p':
                    continue
                k = path.kt + trajectory[event]
                dist = path.kt[None, :3] + trajectory[:, :3]
                previous = np.vstack((path.kt[:3], dist[:-1]))
                b = ((2*np.pi)**2 / 3) * dt * np.sum(previous**2 + previous*dist + dist**2, axis=1)
                diffusion = np.exp(-1e-9 * diffusivity * np.cumsum(b))
                xy_key = tuple(k[:2])
                if xy_key not in xy_cache:
                    kt = torch.tensor([[k[0], k[1], 0]], dtype=torch.float32)
                    xy_cache[xy_key] = float(data.dephasing_func(kt, data.nyquist)[0])
                coeff = (pathways.SQRT2 * path.mag * np.exp(-trajectory[event, 3] / t2)
                         * np.exp(-abs(k[3]) / t2p) * np.exp(-2j * np.pi * k[3] * b0)
                         * np.exp(1j * float(rep.adc_phase[event])) * xy_cache[xy_key]
                         * diffusion[event])
                group = category(path.history, metric.primary_history)
                spatial[group][float(k[2])] = spatial[group].get(float(k[2]), 0j) + coeff
                # float32 matches MRzero's box dephasing convention.
                zweight = float(torch.sinc(torch.tensor(k[2], dtype=torch.float32)
                                          * torch.tensor(.001, dtype=torch.float32)))
                sums[group] += coeff * zweight
            oracle = {key: sum((p.value for p in metric.contributions
                               if category(p.history, metric.primary_history) == key), 0j)
                      for key in spatial}
            errors = [abs(sums[key] - oracle[key]) for key in spatial]
            if max(errors) > 3e-6:
                raise RuntimeError(f'profile integration disagrees with oracle: {errors}')
            profiles = {}
            for group, coefficients in spatial.items():
                curve = np.zeros(len(z), complex)
                entries = list(coefficients.items())
                for offset in range(0, len(entries), 64):
                    batch = entries[offset:offset + 64]
                    kz = np.array([v[0] for v in batch])
                    c = np.array([v[1] for v in batch])
                    curve += c @ np.exp(-2j * np.pi * kz[:, None] * z[None, :])
                profiles[group] = curve
            profiles['total'] = sum(profiles.values())
            outputs.append(dict(profiles=profiles, sums=oracle,
                                max_integrated_error=max(errors)))
        total = float(dt.sum())
        evolved = []
        for path in paths:
            if path.kind == 'p':
                dist = path.kt[None, :3] + trajectory[:, :3]
                previous = np.vstack((path.kt[:3], dist[:-1]))
                b = ((2*np.pi)**2 / 3) * dt * np.sum(previous**2 + previous*dist + dist**2, axis=1)
                attenuation = np.exp(-1e-9 * diffusivity * b.sum())
                evolved.append(pathways._Path('p', path.mag * np.exp(-total / t2) * attenuation,
                                             path.kt + trajectory[-1], path.parity,
                                             path.history, False))
            else:
                attenuation = np.exp(-1e-9 * diffusivity * total * np.linalg.norm(path.kt[:3])**2)
                evolved.append(pathways._Path('z', path.mag * np.exp(-total / t1) * attenuation,
                                             path.kt.copy(), path.parity, path.history,
                                             path.equilibrium))
        evolved.append(pathways._Path('z', complex(1 - np.exp(-total / t1)), np.zeros(4),
                                     +1, ('Z0',) * (index + 1), True))
        paths = evolved
    return outputs


def common_axes(axs):
    for ax in axs.flat:
        ax.grid(alpha=.15)
        ax.tick_params(labelsize=8)
        ax.set_xlim(-1, 1)
        ax.set_xticks([-1, 0, 1])
        ax.axvline(-.5, color='#999999', lw=.6, ls=':')
        ax.axvline(.5, color='#999999', lw=.6, ls=':')


def bloch_png(record, destination):
    r = record['bloch']
    z = r['voxel']['z'] * 1e3
    fig, axs = plt.subplots(3, 8, figsize=(22, 7.4), sharex=True, sharey='row')
    common_axes(axs)
    for j, (t, mx, my, mz) in enumerate(r['snapshots']):
        xy = mx + 1j * my
        order = np.argsort(z)
        # All spins are included, with identical point size and axes for all cases.
        axs[0, j].scatter(z[order], abs(xy[order]), s=.35, alpha=.35,
                          color='#2166ac', rasterized=True)
        keep = abs(xy) > 1e-5
        axs[1, j].scatter(z[keep], np.degrees(np.angle(xy[keep])), s=.35,
                          alpha=.30, color='#2166ac', rasterized=True)
        axs[2, j].scatter(z[order], mz[order], s=.35, alpha=.35,
                          color='#2166ac', rasterized=True)
        axs[0, j].set_title(f'Echo {j+1}   {(t-record["t_exc"])*1e3:.3f} ms\n'
                            f'|mean Mxy| = {abs(xy.mean()):.4f}', fontsize=9)
        axs[0, j].set_ylim(0, 1.1)
        axs[1, j].set_ylim(-185, 185)
        axs[1, j].set_yticks([-180, 0, 180])
        axs[2, j].set_ylim(-1.1, 1.1)
        axs[2, j].set_xlabel('Slice position z (mm)', fontsize=8)
    axs[0, 0].set_ylabel('|Mxy| / M0')
    axs[1, 0].set_ylabel('Phase (degrees)')
    axs[2, 0].set_ylabel('Mz / M0')
    fig.suptitle(record['title'] + f' | RF strength {record["b1"]*100:.0f}%'
                 f' | excitation phase error {record["phase"]:.0f} degrees\n'
                 'Finite-duration sinc RF Bloch model | middle ADC sample of each echo', fontsize=13)
    fig.text(.5, .02, 'All signal routes are mixed here. Mz is current storage, not an isolated stimulated-echo signal. '
             'Dotted lines mark nominal slice edges. Identical axes; no per-image normalization.',
             ha='center', fontsize=10)
    fig.subplots_adjust(top=.81, bottom=.11, left=.06, right=.99, hspace=.28, wspace=.12)
    fig.savefig(destination, dpi=150)
    plt.close(fig)


def pathway_png(record, destination):
    fig, axs = plt.subplots(3, 8, figsize=(22, 7.4), sharex='row', sharey='row')
    for j, (metric, spatial) in enumerate(zip(record['metrics'], record['spatial'])):
        profiles = spatial['profiles']
        z = record['pdg_z'] * 1e3
        for group in ('primary', 'stimulated', 'total'):
            axs[0, j].plot(z, abs(profiles[group]), color=COLORS[group], lw=.8, label=group)
        for group in ('primary', 'stimulated'):
            curve = profiles[group]
            phase = np.degrees(np.angle(curve)).copy()
            phase[abs(curve) < 1e-5] = np.nan
            axs[1, j].plot(z, phase, '.', ms=.9, color=COLORS[group], alpha=.65)
        for row in (0, 1):
            axs[row, j].set_xlim(-.5, .5)
            axs[row, j].set_xticks([-.5, 0, .5])
            axs[row, j].grid(alpha=.15)
        axs[0, j].set_ylim(0, 1.1)
        axs[1, j].set_ylim(-185, 185)
        axs[1, j].set_yticks([-180, 0, 180])
        sums = spatial['sums']
        rotate = np.exp(-1j * np.angle(metric.primary))
        vectors = dict(sums, total=metric.total)
        ax = axs[2, j]
        for key in ('primary', 'stimulated', 'other', 'total'):
            v = vectors[key] * rotate
            ax.annotate('', xy=(v.real, v.imag), xytext=(0, 0),
                        arrowprops=dict(arrowstyle='->', color=COLORS[key], lw=1.3))
        ax.set_xlim(-.8, .8); ax.set_ylim(-.8, .8)
        ax.set_aspect('equal', adjustable='box')
        ax.axhline(0, color='#cccccc', lw=.6); ax.axvline(0, color='#cccccc', lw=.6)
        ax.set_xticks([-.5, 0, .5]); ax.set_yticks([-.5, 0, .5]); ax.tick_params(labelsize=8)
        ax.set_xlabel('Real signal / M0', fontsize=8)
        axs[1, j].set_xlabel('Slice position z (mm)', fontsize=8)
        axs[0, j].set_title(f'Echo {j+1}\nP={abs(metric.primary):.4f}  '
                           f'STE={abs(sums["stimulated"]):.4f}', fontsize=9)
    axs[0, 0].set_ylabel('Magnitude / M0')
    axs[1, 0].set_ylabel('Phase (degrees)')
    axs[2, 0].set_ylabel('Imaginary signal / M0')
    handles = [plt.Line2D([0], [0], color=COLORS[k], lw=2, label=l) for k, l in
               [('primary', 'Primary'), ('stimulated', 'Stimulated routes'),
                ('other', 'Other routes and recovery'), ('total', 'Total')]]
    fig.legend(handles=handles, loc='upper center', bbox_to_anchor=(.5, .885), ncol=4,
               frameon=False, fontsize=10)
    fig.suptitle(record['title'] + f' | RF strength {record["b1"]*100:.0f}%'
                 f' | excitation phase error {record["phase"]:.0f} degrees\n'
                 'Instantaneous RF pathway model | true stimulated-route isolation at each middle ADC sample',
                 fontsize=13)
    fig.text(.5, .015, 'Red: transverse signal that was previously stored longitudinally after excitation. '
             'Top rows average over x/y in a 1-mm box slice.\n'
             'Bottom: voxel-integrated arrows rotated so primary points right; identical absolute axes. '
             'This is a separate model from the finite-RF Bloch plots.', ha='center', fontsize=10)
    fig.subplots_adjust(top=.78, bottom=.12, left=.06, right=.99, hspace=.34, wspace=.14)
    fig.savefig(destination, dpi=150)
    plt.close(fig)


def comparison_png(records, b1, phase, folder):
    selected = [r for r in records if r['b1'] == b1 and r['phase'] == phase]
    fig, axs = plt.subplots(len(selected), 3, figsize=(14, 2.05 * len(selected)), sharex='col')
    for row, record in enumerate(selected):
        t, mx, my, mz = record['bloch']['snapshots'][-1]
        z = record['bloch']['voxel']['z'] * 1e3
        xy = mx + 1j * my
        axs[row, 0].scatter(z, abs(xy), s=.45, alpha=.35, color='#2166ac', rasterized=True)
        keep = abs(xy) > 1e-5
        axs[row, 1].scatter(z[keep], np.degrees(np.angle(xy[keep])), s=.45,
                            alpha=.35, color='#2166ac', rasterized=True)
        for key in ('primary', 'stimulated', 'total'):
            axs[row, 2].plot(record['pdg_z'] * 1e3,
                            abs(record['spatial'][-1]['profiles'][key]),
                            color=COLORS[key], lw=.8)
        axs[row, 0].set_ylabel(record['title'].replace(' and ', '\nand ') + '\n'
                              f'Bloch S8={record["bloch"]["echo_center"][-1]:.4f}', fontsize=8)
        for col in range(3):
            ax = axs[row, col]
            ax.grid(alpha=.15); ax.tick_params(labelsize=8)
            ax.set_xlim((-1, 1) if col < 2 else (-.5, .5))
            ax.set_ylim((-185, 185) if col == 1 else (0, 1.1))
    for col, title in enumerate(['Total local |Mxy|\nFinite RF Bloch', 'Total local phase (degrees)\nFinite RF Bloch',
                                  'Primary (blue), stimulated (red), total (black)\nInstantaneous RF model']):
        axs[0, col].set_title(title, fontsize=11)
        axs[-1, col].set_xlabel('Slice position z (mm)')
    fig.suptitle(f'Echo 8 comparison | RF strength {b1*100:.0f}% | phase error {phase:.0f} degrees\n'
                 'Matched ADC samples and identical axes; spatial supports differ between the two models', fontsize=14)
    fig.subplots_adjust(left=.22, right=.98, bottom=.035, top=.94, hspace=.24, wspace=.18)
    fig.savefig(folder / f'00_compare_echo08_rf{round(b1*100):03d}_phase{phase:03.0f}.png', dpi=150)
    plt.close(fig)


def summary_png(records, b1, phase, folder):
    selected = [r for r in records if r['b1'] == b1 and r['phase'] == phase]
    fig, axs = plt.subplots(1, 3, figsize=(17, 5.8))
    for n, r in enumerate(selected):
        color = plt.cm.tab10(n)
        x = np.arange(1, 9)
        axs[0].plot(x, r['bloch']['echo_center'], '.-', color=color, label=r['title'])
        axs[1].plot(x, [abs(s['sums']['stimulated']) for s in r['spatial']], '.-', color=color)
        axs[2].plot(x, [100*m.other_l1_fraction for m in r['metrics']], '.-', color=color)
    titles = ['Acquired total signal\nFinite-duration RF Bloch',
              'Stimulated routes after coherent summation\nInstantaneous RF pathway model',
              'All non-primary route amplitude share\nInstantaneous RF pathway model']
    for ax, title in zip(axs, titles):
        ax.set_title(title, fontsize=11); ax.set_xlabel('Echo number'); ax.set_xticks(range(1, 9)); ax.grid(alpha=.2)
        ax.set_ylim(bottom=0)
    axs[0].set_ylabel('Amplitude / M0'); axs[1].set_ylabel('Amplitude / M0'); axs[2].set_ylabel('L1 amplitude share (%)')
    # Fixed ranges across RF strengths, including the nearly-zero ideal-RF
    # stimulated signal. Autoscaling there would magnify roundoff misleadingly.
    axs[0].set_ylim(0, .32); axs[1].set_ylim(0, .28); axs[2].set_ylim(0, 100)
    axs[0].legend(fontsize=8, loc='upper right')
    fig.suptitle(f'RF strength {b1*100:.0f}% | phase error {phase:.0f} degrees | nominal b=1000 s/mm2', fontsize=13)
    fig.text(.5, .02, 'Models have different RF/slice assumptions and volume normalization. '
             'Do not equate their absolute amplitudes. Route share is not artifact intensity.', ha='center', fontsize=10)
    fig.tight_layout(rect=(0, .045, 1, .94))
    fig.savefig(folder / f'00_echo_metrics_rf{round(b1*100):03d}_phase{phase:03.0f}.png', dpi=160)
    plt.close(fig)


def schedule_png(records, folder):
    fig, axs = plt.subplots(1, 2, figsize=(15, 6))
    for i, r in enumerate(records[::4]):
        axs[0].plot(range(1, 9), r['crusher_dac'], 'o-', color=plt.cm.tab10(i), label=r['title'])
        axs[1].plot(range(1, 9), r['rf_offsets'], 'o-', color=plt.cm.tab10(i))
    axs[0].set_ylabel('Signed crusher amplitude (DAC units)')
    axs[1].set_ylabel('Additional RF phase offset (degrees)')
    axs[0].set_title('Crusher schedule: each pair uses matching lobes')
    axs[1].set_title('RF phase offsets relative to original sequence')
    for ax in axs:
        ax.set_xlabel('Refocusing pulse number'); ax.set_xticks(range(1, 9)); ax.grid(alpha=.2)
    axs[0].legend(fontsize=8, ncol=2, loc='lower left')
    fig.suptitle('Definitions of the snapshot alternatives', fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, .95))
    fig.savefig(folder / '00_gradient_and_rf_schedules.png', dpi=170)
    plt.close(fig)


def cancellation_png(records, folder):
    chosen = [r for r in records if r['b1'] == .8 and r['key'] in ('01_original', '04_alternating')]
    fig, axs = plt.subplots(2, 2, figsize=(12, 10), sharex=True, sharey=True)
    for r, ax in zip(chosen, axs.flat):
        m = r['metrics'][-1]
        groups = r['spatial'][-1]['sums']
        vectors = dict(primary=m.primary, stimulated=groups['stimulated'], other=groups['other'], total=m.total)
        rot = np.exp(-1j * np.angle(m.primary))
        for key, v in vectors.items():
            v *= rot
            ax.annotate('', xy=(v.real, v.imag), xytext=(0, 0),
                        arrowprops=dict(arrowstyle='->', color=COLORS[key], lw=2.5))
            ax.scatter([v.real], [v.imag], s=38, color=COLORS[key], zorder=6)
            ax.plot([], [], color=COLORS[key], label=f'{key}: {abs(v):.5f}')
        ax.axhline(0, color='#cccccc'); ax.axvline(0, color='#cccccc'); ax.grid(alpha=.15)
        ax.set_title(r['title'] + f' | phase error {r["phase"]:.0f} degrees\n'
                     f'All-other vs primary phase: {m.other_relative_phase_deg:.1f} degrees', fontsize=11)
        ax.set_xlim(-.21, .21); ax.set_ylim(-.21, .21); ax.set_aspect('equal')
        ax.legend(fontsize=9, loc='lower left'); ax.set_xlabel('Real signal / M0'); ax.set_ylabel('Imaginary signal / M0')
    fig.suptitle('Why the simple alternating schedule loses signal at echo 8\n'
                 'RF strength 80% | instantaneous RF model | arrows rotated to primary direction', fontsize=14)
    fig.text(.5, .025, 'The primary amplitude is preserved. In the alternating case, other routes point nearly opposite '
             'to the primary and cancel it.\nThis diagnoses the idealized model; finite-RF Bloch magnitudes show '
             'a similar loss but do not supply a pathway decomposition.', ha='center', fontsize=11)
    fig.tight_layout(rect=(0, .07, 1, .93))
    fig.savefig(folder / '00_alternating_cancellation_explained.png', dpi=170)
    plt.close(fig)


def reading_guide_png(folder, n=10000):
    fig = plt.figure(figsize=(13, 11), facecolor='white')
    fig.text(.065, .94, 'How to compare the echo snapshots', fontsize=23, weight='bold')
    paragraphs = [
        ('Start with the files beginning 00',
         'The compare_echo08 images put all ten alternatives side by side at echo 8. '
         'The echo_metrics images show all eight echoes. The schedules image defines the changes. '
         'The alternating_cancellation image shows why our simple sign-flip schedule lost signal.'),
        ('Each alternative has two image types',
         'bloch_snapshots: total local transverse magnitude, transverse phase and longitudinal '
         'magnetization across the slice. These include all routes together and finite-duration sinc RF pulses. '
         'Each column is one echo, measured at its actual middle ADC sample.'),
        ('The stimulated_pathways images isolate stored routes',
         'Blue is the primary route, red is the coherent sum of routes that were stored longitudinally '
         'after excitation, and black is the total. The top rows show magnitude and phase across a 1-mm box. '
         'Bottom-row arrows show the voxel-integrated signal, rotated so the primary points right. '
         'Gray arrows include other transverse routes and T1 recovery.'),
        ('Read the filenames',
         'rf080 means both excitation and refocusing RF strengths are scaled to 80%; rf100 means 100%. '
         'phase000 and phase090 refer to an excitation phase error before the train. '
         'This is separate from alternatives that change refocusing RF phases between echoes.'),
        ('Use the same axes to compare cases',
         'All images use fixed axes and no per-image amplitude normalization. '
         'Local magnitude can remain high even when phase is spread out and the mean signal is small. '
         'Mz measures what is stored now; it is not itself a stimulated-echo signal.'),
        ('The two models answer different questions',
         'The stimulated-route separation uses instantaneous RF pulses and a 1-mm box voxel. '
         'The Bloch model uses an assumed sinc waveform and includes slice edges over 2 mm. '
         'Do not equate their absolute amplitudes or phase frames. At 100% RF, stimulated routes vanish '
         'in the idealized model, while finite-RF slice-profile effects can persist.'),
        ('Matched experimental conditions',
         'Eight echoes; TE 36 ms; spacing 16 ms; requested b=1000 s/mm2 along the read axis; '
         f'B0=0; T1=1.5 s; T2=80 ms; T2 prime=30 ms. Bloch uses {n:,} stationary spins, seed 1. '
         'Diffusion gradients are played, but these snapshots do not simulate molecular motion. '
         'The decreasing example reverses pulse 2 through 8 amplitudes; pulse 1 is unchanged.'),
    ]
    y = .875
    for title, paragraph in paragraphs:
        fig.text(.065, y, title, fontsize=13, weight='bold')
        y -= .029
        lines = textwrap.wrap(paragraph, width=125)
        fig.text(.065, y, '\n'.join(lines), fontsize=11.5, va='top', linespacing=1.35)
        y -= len(lines) * .021 + .017
    fig.savefig(folder / '00_read_me_first.png', dpi=160)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--n', type=int, default=10000)
    ap.add_argument('--variants', help='comma-separated keys, for a limited rerun')
    ap.add_argument('--reuse', action='store_true', help='reuse saved Bloch arrays')
    args = ap.parse_args()
    folder = ROOT / 'docs/figures/echo_snapshot_comparison'
    raw = ROOT / 'runs/echo_snapshot_comparison'
    folder.mkdir(parents=True, exist_ok=True); raw.mkdir(parents=True, exist_ok=True)
    voxel = simulate.make_voxel(n=args.n, seed=1)
    pdg_z = np.linspace(-.0005, .0005, 2001)
    selected = CASES if not args.variants else [c for c in CASES if c[0] in args.variants.split(',')]
    records = []; table = []
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10})
    for key, title, variant in selected:
        for b1 in (.8, 1.):
            for phase in (0., 90.):
                tag = f'{key}_rf{round(b1*100):03d}_phase{phase:03.0f}'
                case_dir = raw / tag; case_dir.mkdir(exist_ok=True)
                overrides = dict(BASE, **variant)
                overrides.update(sim_reduced_rows=[1], sim_excitation_phase_deg=phase)
                seq, c, d, log = generate.build_sequence(generate.load_params(overrides=overrides), reduced=True)
                ok, errors = seq.check_timing()
                if not ok:
                    raise RuntimeError(errors)
                seqpath = case_dir / 'seq.seq'; seq.write(str(seqpath))
                times = adc_centers(seq)
                if len(times) != 8:
                    raise RuntimeError('comparison must contain exactly 8 echoes')
                t_exc = simulate.first_excitation(seq)
                cache = case_dir / 'bloch.npz'
                if args.reuse and cache.exists():
                    saved = np.load(cache)
                    b = dict(echo_center=saved['echo_center'],
                             voxel=dict(voxel), snapshots=[(t, saved['mx'][i], saved['my'][i], saved['mz'][i])
                                                          for i, t in enumerate(saved['times'])])
                else:
                    b = simulate.simulate(seq, b1=b1, b0=0, voxel=voxel, snap_times=times, rf_dt=1e-5)
                    np.savez_compressed(cache, times=times, mx=[s[1] for s in b['snapshots']],
                                        my=[s[2] for s in b['snapshots']], mz=[s[3] for s in b['snapshots']],
                                        echo_center=b['echo_center'], signal=b['signal'], t_adc=b['t_adc'],
                                        x=voxel['x'], y=voxel['y'], z=voxel['z'], df=voxel['df'])
                snap_errors = [abs(abs(np.mean(s[1] + 1j*s[2])) - value)
                               for s, value in zip(b['snapshots'], b['echo_center'])]
                if max(snap_errors) > 1e-10:
                    raise RuntimeError('snapshot does not agree with actual middle ADC sample')
                mrseq = epg.quiet(epg.mr0.Sequence.import_file, str(seqpath))
                ph = epg.make_phantom(SimpleNamespace(voxel_mm=[.2,.2,1], T1=1.5,T2=.08,
                                                      T2dash=.03,D=0,b0=0,b1=b1))
                metrics = epg.quiet(pathways.enumerate_center_pathways, mrseq, ph)
                spatial = spatial_pathways(mrseq, ph, metrics, pdg_z)
                (case_dir / 'pathways.json').write_text(json.dumps(
                    [pathways.metric_record(m, top=None) for m in metrics], indent=2))
                (case_dir / 'settings.json').write_text(json.dumps(dict(
                    overrides=overrides, b1=b1, b0=0, seed=1, n=args.n, rf_dt=1e-5,
                    T1=1.5,T2=.08,T2prime=.03, nominal_b=1000, diffusion_motion=False,
                    center_rule='actual upper-middle ADC sample N//2',
                    crusher_dac=d.train_crusher_amplitudes_dac,
                    max_bloch_snapshot_error=max(snap_errors)), indent=2))
                r = dict(key=key,title=title,b1=b1,phase=phase,bloch=b,metrics=metrics,
                         spatial=spatial,pdg_z=pdg_z,t_exc=t_exc,
                         crusher_dac=d.train_crusher_amplitudes_dac,
                         rf_offsets=variant.get('sim_refocus_phase_offsets_deg', [0]*8))
                records.append(r)
                bloch_png(r, folder / (tag + '_bloch_snapshots.png'))
                pathway_png(r, folder / (tag + '_stimulated_pathways.png'))
                for m, s, bs in zip(metrics, spatial, b['echo_center']):
                    stim = s['sums']['stimulated']; other = s['sums']['other']
                    table.append(dict(variant=key,b1=b1,phase=phase,echo=m.echo,
                        bloch_total=bs,primary_pdg=abs(m.primary),stimulated_coherent_pdg=abs(stim),
                        remaining_other_coherent_pdg=abs(other),total_pdg=abs(m.total),
                        nonprimary_l1_share=m.other_l1_fraction,other_phase_deg=m.other_relative_phase_deg,
                        stimulated_phase_deg=float(np.degrees(np.angle(stim/m.primary))),
                        max_profile_integration_error=s['max_integrated_error']))
                print(f'{tag}: S8 Bloch={b["echo_center"][-1]:.5f}, '
                      f'P8={abs(metrics[-1].primary):.5f}, '
                      f'STE8={abs(spatial[-1]["sums"]["stimulated"]):.5f}, '
                      f'U8={100*metrics[-1].other_l1_fraction:.1f}%', flush=True)
    for b1 in (.8, 1.):
        for phase in (0., 90.):
            comparison_png(records, b1, phase, folder)
            summary_png(records, b1, phase, folder)
    schedule_png(records, folder)
    reading_guide_png(folder, args.n)
    if any(r['key'] == '04_alternating' for r in records) and any(r['key'] == '01_original' for r in records):
        cancellation_png(records, folder)
    dest = ROOT / 'docs/data/echo_snapshot_comparison.csv'
    with dest.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(table[0])); writer.writeheader(); writer.writerows(table)
    print(f'Finished: {len(records)} conditions, {len(list(folder.glob("*.png")))} PNGs in {folder}', flush=True)


if __name__ == '__main__':
    main()
