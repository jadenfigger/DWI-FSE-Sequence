"""Summarize cached study evidence without re-running or selecting experiments.

python examples/summarize_combined_factors.py
Magnitude statistics are equal-weight condition-grid summaries, not patient SNR.
"""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'docs/data'


def read(path):
    if not path.exists():
        return []
    with path.open(newline='', encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        for key, value in row.items():
            try:
                row[key] = float(value)
            except (ValueError, TypeError):
                pass
    return rows


def write(path, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def condition(row):
    stage = row['stage'].replace('timing_transfer_robust', 'robust').replace(
        'timing_transfer_heldout', 'heldout')
    return (stage,) + tuple(row.get(k, '') for k in (
        'b', 'direction', 'phase', 'b1', 'b0', 'etl', 'echo',
        'D_mm2_s', 'n', 'seed', 'rf_dt_s'))


def main():
    rows = []
    for path in sorted(DATA.glob('combined_factor_*_bloch.csv')):
        rows += read(path)
    for path in sorted(DATA.glob('combined_factor_*_pathways.csv')):
        rows += read(path)
    hardware = {(r['seqid'], r['echo']): r
                for r in read(DATA / 'combined_factor_hardware_tensors.csv')}
    references = {(r['variant'], condition(r)): r for r in rows}
    pairs = []
    for row in rows:
        for name in ['original', 'increasing_centering']:
            base = references.get((name, condition(row)))
            if base is None:
                continue
            result = {k: row.get(k, '') for k in (
                'stage', 'model', 'variant', 'b', 'direction', 'phase',
                'b1', 'b0', 'etl', 'echo', 'D_mm2_s', 'case_id')}
            result['matched_baseline'] = name
            for metric in ['total_abs', 'primary_abs', 'stimulated_abs', 'unwanted_l1_share']:
                if metric not in row:
                    continue
                result[metric] = row[metric]
                result['baseline_' + metric] = base[metric]
                result['delta_' + metric] = row[metric] - base[metric]
                if metric.endswith('_abs'):
                    result['ratio_' + metric] = row[metric] / base[metric] if base[metric] else ''
            result['baseline_total_below_0.001'] = base['total_abs'] < .001
            if 'primary_real' in row:
                primary = row['primary_real'] + 1j*row['primary_imag']
                other = row['total_real'] + 1j*row['total_imag'] - primary
                result['nonprimary_coherent_real'] = float(other.real)
                result['nonprimary_coherent_imag'] = float(other.imag)
                result['nonprimary_coherent_abs'] = float(abs(other))
                result['nonprimary_relative_phase_deg'] = float(np.angle(other*primary.conjugate(), deg=True))
            h = hardware.get((row['seqid'], row['echo']))
            hb = hardware.get((base['seqid'], base['echo']))
            if h and hb:
                result['b_trace_s_mm2'] = h['b_trace_s_mm2']
                result['baseline_b_trace_s_mm2'] = hb['b_trace_s_mm2']
                result['delta_b_trace_s_mm2'] = h['b_trace_s_mm2'] - hb['b_trace_s_mm2']
                for a in 'xyz':
                    for z in 'xyz':
                        key = 'B' + a + z
                        result[key] = h[key]
                        result['delta_' + key] = h[key] - hb[key]
            pairs.append(result)
    write(DATA / 'combined_summary_paired.csv', pairs)

    groups = {}
    for row in rows:
        if row['echo'] != row['etl']:
            continue
        key = (row['stage'], row['model'], row['variant'], row.get('D_mm2_s', ''), row['etl'])
        groups.setdefault(key, []).append(row)
    summaries = []
    for (stage, model, name, diffusion, etl), group in groups.items():
        result = dict(stage=stage, model=model, variant=name, D_mm2_s=diffusion,
                      etl=etl, conditions=len(group))
        for metric in ['total_abs', 'primary_abs', 'stimulated_abs', 'unwanted_l1_share']:
            if metric not in group[0]:
                continue
            values = [r[metric] for r in group]
            for label, fn in [('min', np.min), ('median', np.median), ('max', np.max)]:
                result[metric + '_' + label] = float(fn(values))
        matched = [p for p in pairs if p['variant'] == name and p['stage'] == stage
                   and p['model'] == model and p['D_mm2_s'] == diffusion
                   and p['etl'] == etl and p['echo'] == etl
                   and p['matched_baseline'] == 'original']
        if matched:
            result['median_paired_delta_total_abs'] = float(np.median([p['delta_total_abs'] for p in matched]))
            result['minimum_paired_delta_total_abs'] = float(min(p['delta_total_abs'] for p in matched))
        summaries.append(result)
    write(DATA / 'combined_summary_grid.csv', summaries)

    configs = json.loads((ROOT / 'docs/params/combined_factor_configs.json').read_text())['configs']
    selection = json.loads((DATA / 'combined_factor_selection.json').read_text())
    screened = []
    for name, spec in configs.items():
        p = next((r for r in rows if r['variant'] == name and r['stage'] in ('screen', 'timing_transfer')
                  and r['echo'] == 8 and r['phase'] == 0 and r['b1'] == .8
                  and r.get('D_mm2_s') == 0), None)
        water = next((r for r in rows if r['variant'] == name and r['stage'] in ('screen', 'timing_transfer')
                      and r['echo'] == 8 and r['phase'] == 0 and r['b1'] == .8
                      and r.get('D_mm2_s') == .001), None)
        total = next((r for r in summaries if r['variant'] == name and r['stage'] == 'screen'
                      and r['model'] == 'finite_RF_static_Bloch'), None)
        if not p or not water or not total:
            continue
        h = hardware.get((p['seqid'], 8.))
        original = next((r for r in rows if r['variant'] == 'original' and r['stage'] == 'screen'
                         and r['echo'] == 8 and r['phase'] == 0 and r['b1'] == .8
                         and r.get('D_mm2_s') == 0), None)
        hb = hardware.get((original['seqid'], 8.)) if original else None
        screened.append({
            'Test ID': name, 'Exact changes': json.dumps(spec, sort_keys=True),
            'Conditions': 'ETL8 read b1000; RF0.8/1; phase0/90; B0=0; static and D=.001',
            'Primary signal': f"static {p['primary_abs']:.6g}; water {water['primary_abs']:.6g} (instant RF)",
            'Total signal': f"finite RF median {total['total_abs_median']:.6g}",
            'Stimulated contribution': f"static {p['stimulated_abs']:.6g}; water {water['stimulated_abs']:.6g} (coherent magnitude)",
            'Non-primary share': f"static {p['unwanted_l1_share']:.6g}; water {water['unwanted_l1_share']:.6g} (L1)",
            'Robustness': f"4-point screen range {total['total_abs_min']:.6g} to {total['total_abs_max']:.6g}",
            'Added diffusion weighting': f"E8 trace {h['b_trace_s_mm2']:.6g}; delta {h['b_trace_s_mm2']-hb['b_trace_s_mm2']:.6g} s/mm2" if h and hb else '',
            'Timing/hardware cost': f"TE sample {h['TE_ms']:.6g}ms; ESP {h['ESP_ms']:.6g}ms; TR {h['TR_s']:.6g}s; peak {h['peak_gradient_mT_m']:.6g}mT/m; slew {h['peak_slew_T_m_s']:.6g}T/m/s; G2 {h['gradient_squared_Hz2_m2_s']:.6g}; RF2 {h['rf_squared_Hz2_s']:.6g}" if h else '',
            'Decision': ('supplemental timing-transfer validation' if name == 'high_low_permutation_alternating_centering'
                         else 'broader validation' if name in selection['variants'] else 'screen only; see report for tradeoff'),
        })
    write(DATA / 'combined_summary_screen_tests.csv', screened)

    # Each contrast compares the identical conditions and echo: AB-A-B+baseline.
    experiments = [
        ('centering_x_ramp', 'original', 'centering', 'increasing', 'increasing_centering'),
        ('ramp_x_polarity', 'original', 'increasing', 'alternating', 'increasing_alternating'),
        ('centered_ramp_x_polarity', 'centering', 'increasing_centering',
         'alternating_centering', 'increasing_alternating_centering'),
    ]
    for suffix in ['rf180', 'rf90_exploratory', 'flip160', 'flip_train', 'duration500', 'taper']:
        for stem, bundle in [('inc_alt_center', 'increasing_alternating_centering'),
                             ('inc_center', 'increasing_centering'),
                             ('increasing_centering', 'increasing_centering')]:
            experiments.append((bundle + '_x_' + suffix, 'original', bundle,
                                'original_' + suffix, stem + '_' + suffix))
    interactions = []
    for label, base, a, b, ab in experiments:
        for row in rows:
            if row['variant'] != base:
                continue
            four = [references.get((v, condition(row))) for v in [base, a, b, ab]]
            if any(r is None for r in four):
                continue
            result = {k: row.get(k, '') for k in (
                'stage', 'model', 'b', 'direction', 'phase', 'b1', 'b0', 'etl', 'echo', 'D_mm2_s')}
            result.update(interaction=label, baseline=base, factor_A=a, factor_B=b, combination=ab)
            for metric in ['total_abs', 'primary_abs', 'stimulated_abs', 'unwanted_l1_share', 'total_real', 'total_imag']:
                if metric not in row:
                    continue
                z, x, y, xy = [r[metric] for r in four]
                result[metric + '_interaction'] = xy - x - y + z
                result[metric + '_baseline'] = z
                result[metric + '_A'] = x
                result[metric + '_B'] = y
                result[metric + '_AB'] = xy
            interactions.append(result)
    write(DATA / 'combined_interactions.csv', interactions)

    vertices = ['original', 'centering', 'increasing', 'alternating',
                'increasing_centering', 'alternating_centering',
                'increasing_alternating', 'increasing_alternating_centering']
    three_way = []
    for row in rows:
        if row['variant'] != 'original':
            continue
        cells = [references.get((v, condition(row))) for v in vertices]
        if any(c is None for c in cells):
            continue
        result = {k: row.get(k, '') for k in (
            'stage', 'model', 'phase', 'b1', 'b0', 'etl', 'echo', 'D_mm2_s')}
        for metric in ['total_abs', 'total_real', 'total_imag', 'unwanted_l1_share']:
            if metric in row:
                result[metric + '_three_way_contrast'] = float(np.dot(
                    [-1, 1, 1, 1, -1, -1, -1, 1], [c[metric] for c in cells]))
        three_way.append(result)
    write(DATA / 'combined_interactions_three_way.csv', three_way)

    consistency = []
    trains = {}
    for row in rows:
        trains.setdefault(row['case_id'], []).append(row)
    for case, train in trains.items():
        train.sort(key=lambda r: r['echo'])
        if len(train) < 2:
            continue
        mags = np.array([r['total_abs'] for r in train])
        phase = np.unwrap(np.angle([r['total_real'] + 1j*r['total_imag'] for r in train]))
        consistency.append(dict(case_id=case, stage=train[0]['stage'], variant=train[0]['variant'],
            model=train[0]['model'], D_mm2_s=train[0].get('D_mm2_s', ''),
            echo_magnitude_min=float(mags.min()), echo_magnitude_max=float(mags.max()),
            magnitude_cv=float(mags.std()/mags.mean()) if mags.mean() else 0,
            maximum_adjacent_phase_step_deg=float(np.max(abs(np.diff(phase)))*180/np.pi),
            phase_range_deg=float(np.ptp(phase)*180/np.pi),
            note='includes physical relaxation and prescribed receiver/RF phase; no arbitrary rephasing'))
    write(DATA / 'combined_summary_echo_consistency.csv', consistency)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    labels = []
    candidates = ['original', 'increasing_centering', 'increasing_alternating_centering',
                  'weak_increasing_centering', 'high_low_permutation_alternating_centering']
    display = dict(zip(candidates, ['Original', 'Centered\nramp', 'Centered\nalternating\nramp',
                                   'Centered\nweak ramp', 'Centered\nreordered\nalternation']))
    chosen = [r for r in summaries if r['stage'] in ('robust', 'timing_transfer_robust') and r['model'] == 'finite_RF_static_Bloch'
              and r['etl'] == 8 and r['variant'] in candidates]
    if not chosen:
        chosen = [r for r in summaries if r['stage'] == 'screen' and r['model'] == 'finite_RF_static_Bloch'
                  and r['variant'] in candidates]
    chosen.sort(key=lambda r: candidates.index(r['variant']))
    for i, r in enumerate(chosen):
        labels.append(display[r['variant']])
        axes[0].plot([i, i], [r['total_abs_min'], r['total_abs_max']], color='#6489a7', linewidth=4)
        axes[0].scatter(i, r['total_abs_median'], color='#193c55', zorder=3)
        pdg = [x for x in rows if x['variant'] == r['variant'] and x['stage'] in ('screen', 'timing_transfer')
               and x['model'] == 'instant_RF_exact_pathways' and x['D_mm2_s'] == 0
               and x['echo'] == 8 and x['b1'] == .8 and x['phase'] == 0]
        if pdg:
            axes[1].scatter(i, 100*pdg[0]['unwanted_l1_share'], color='#a4533f')
        seqrow = next((x for x in rows if x['variant'] == r['variant'] and x['b'] == 1000
                       and x['direction'] == 'read' and x['etl'] == 8 and x['echo'] == 8), None)
        if seqrow and (seqrow['seqid'], 8.) in hardware:
            h = hardware[(seqrow['seqid'], 8.)]
            axes[2].scatter(i, h['b_trace_s_mm2'], color='#4b7858')
    for ax in axes:
        ax.set_xticks(range(len(labels)), labels, fontsize=8)
        ax.grid(axis='y', alpha=.2)
    axes[0].set_title('Finite RF stationary signal: final echo')
    axes[0].set_ylabel('Magnitude; dot median, bar grid range')
    axes[1].set_title('Instantaneous RF: non-primary L1 share')
    axes[1].set_ylabel('L1 share (%) at RF scale 0.8, phase 0°, static')
    axes[1].set_ylim(0, 100)
    axes[2].set_title('Full primary diffusion weighting: read b=1000')
    axes[2].set_ylabel('Trace of b tensor (s/mm²)')
    fig.suptitle('Different models and metrics: compare within each panel', fontsize=13)
    fig.tight_layout()
    destination = ROOT / 'docs/figures/combined_factor_results.png'
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=170)
    plt.close(fig)
    print(json.dumps(dict(echo_records=len(rows), paired_records=len(pairs),
                          grid_groups=len(summaries), interaction_records=len(interactions))))


if __name__ == '__main__':
    main()
