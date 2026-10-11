"""Audit all October 10 MRDs and regenerate the scan catalog (standard library only).

Run: python docs/data/oct10_protocol_audit.py
Reads acquisition files without changing them. Uses the October 5 parser and
compares every embedded field/record, retaining inactive arrays separately.
Adapted from oct07_protocol_audit.py with three additions: every embedded
protocol is also diffed against the PPR it was planned from
(experiments/2026-10-09_exvivo_plan/, scan K against A), multi-slice scan K
is handled, and diffusion-direction signs are checked explicitly.
"""
from __future__ import annotations

import csv
import gzip
import itertools
import json
import re
import struct
from datetime import datetime, timezone
from pathlib import Path

from oct05_protocol_audit import parse_mrd, parse_ppr, sha256, stable_equal

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/data'
PLAN_DIR = ROOT / 'experiments/2026-10-09_exvivo_plan'
DAY = '10-10-2026'
# scan letter -> (folder suffix, planned PPR stem, role)
SCANS = {
    'A': ('v181_testA', 'A_v181_7b', 'v1.81, seven b'),
    'B': ('v1911_testB', 'B_v1911_7b', 'ss-MGOT v1.911, seven b'),
    'C': ('v18_testC', 'C_v18_7b_control', 'v1.8 control, seven b'),
    'D': ('v191_testD', 'D_v191_7b_control', 'v1.91 control, seven b'),
    'E': ('v181_testE', 'E_v181_dirs', 'v1.81 directions incl. -x'),
    'G': ('v1911_testG', 'G_v1911_dirs', 'v1.911 directions incl. -x'),
    'H': ('v181_testH', 'H_v181_crush_eq_selector', 'v1.81 train crusher = selector'),
    'I': ('v1911_testI', 'I_v1911_delta30', 'v1.911 delta 30 / TE 44'),
    'J': ('v181_testJ', 'J_v181_bw_console', 'v1.81 40 kHz console change'),
    'K': ('v181_testK', 'A_v181_7b', 'v1.81 three slices (unplanned)'),
}
ORDER = list(SCANS)
PLAN_REFERENCE = {'K': 'A'}          # K has no PPR of its own: compare against A's plan
RUNTIME = {'AcquisitionStartTime', 'PerformanceCounterFrequency', 'END'}
DIFF_ARRAYS = ('acq_b', 'acq_x', 'acq_y', 'acq_z')
METHOD = {'1.8': 'legacy', '1.81': 'revised legacy', '1.91': 'ss-MGOT', '1.911': 'ss-MGOT revised', '1.92': 'Alsop'}
PAIR_ORDER = [('A', 'C'), ('B', 'D'), ('E', 'A'), ('G', 'B'), ('H', 'A'), ('I', 'B'), ('J', 'A'), ('K', 'A'), ('E', 'G'), ('K', 'J')]


def relative(p):
    return p.relative_to(ROOT).as_posix()


def differences(a, b, exclude=()):
    return {k: [a.get(k), b.get(k)] for k in sorted(set(a) | set(b))
            if k not in exclude and not stable_equal(a.get(k), b.get(k))}


def active_protocol(v):
    """Drop reserved tails only for acquisition arrays; retain all other fields."""
    v = {k: x for k, x in v.items() if k not in RUNTIME}
    for k in DIFF_ARRAYS:
        if isinstance(v.get(k), list):
            v[k] = v[k][:int(v['no_diff_acq'])]
    if v.get('b_input_mode') == 1:      # acq_grad is an inactive cache in b-input mode 1
        v.pop('acq_grad', None)
    return v


def csv_write(name, rows):
    with (OUT / name).open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: json.dumps(x, ensure_ascii=False) if isinstance(x, (dict, list)) else x
                          for k, x in row.items()} for row in rows)


def fmt(v):
    if v is None:
        return '—'
    if isinstance(v, str):
        return v
    return f'{v:g}'


def minus(x):
    return fmt(x).replace('-', '−')


def slice_z(values):
    """z offsets (mm) from the FOV_OFFSETS record: [N, x, y, z, x, y, z, ...]."""
    vals = values['FOV_OFFSETS']
    return [float(x) for x in vals[1:][2::3]]


def dwell_us(v):
    return v['sample_period'][3]


def bandwidth_khz(v):
    return v['sample_period'][2]


def direction_label(b, x, y, z):
    if b == 0:
        return 'none (b=0)'
    parts = [('+' if c > 0 else '−') + n for n, c in zip('xyz', (x, y, z)) if c]
    return ' '.join(parts) if len(parts) == 1 else '(' + ', '.join(f'{c/1000:g}{n}' for n, c in zip('xyz', (x, y, z)) if c) + ')'


def directions_text(r):
    """Compact b/direction list, grouped by b-value, from the active embedded arrays."""
    v = r['_embedded_values']
    n = r['no_diff_acq']
    groups, order = {}, []
    for i in range(n):
        b = v['acq_b'][i]
        lab = direction_label(b, v['acq_x'][i], v['acq_y'][i], v['acq_z'][i])
        if b not in groups:
            groups[b] = []
            order.append(b)
        groups[b].append(lab)
    if all(all(l == '+x' for l in groups[b]) for b in order if b):
        return '+x (read) for every b>0'
    return '; '.join(('b0' if b == 0 else f'b{b:g} ' + ', '.join(groups[b])) for b in order)


def short_diff(pa):
    """Human-readable summary of an {key: [a, b]} difference dict (a -> b)."""
    out = []
    handled = set()
    diff_keys = set(pa)
    if diff_keys & (set(DIFF_ARRAYS) | {'no_diff_acq', 'no_experiments'}):
        na, nb = pa.get('no_diff_acq', [None, None])
        bs = pa.get('acq_b')
        txt = 'diffusion list' if bs is None else 'diffusion list (b / directions)'
        if na is not None:
            txt += f' {int(na)}→{int(nb)} volumes'
        out.append(txt)
        handled |= set(DIFF_ARRAYS) | {'no_diff_acq', 'no_experiments'}
    for k, (a, b) in pa.items():
        if k in handled:
            continue
        if k == 'PPL':
            va = re.search(r'twoTE-(\d+\.\d+)', a).group(1)
            vb = re.search(r'twoTE-(\d+\.\d+)', b).group(1)
            out.append(f'PPL {va}→{vb}')
        elif k == 'sample_period':
            out.append(f'dwell {fmt(a[3])}→{fmt(b[3])} µs ({fmt(a[2])}→{fmt(b[2])} kHz)')
        elif k in ('NO_SLICES', 'FOV_OFFSETS', 'FOV_SLICE_OFF', 'FOV_READ_OFF', 'FOV_PHASE_OFF', 'MULTI_ORIENTATION',
                   'X_ANGLE', 'Y_ANGLE', 'Z_ANGLE'):
            if 'slices' not in ' '.join(out):
                za = [float(x) for x in a[1:][2::3]] if k == 'FOV_OFFSETS' else None
                out.append('slices ' + (f"{fmt(pa['NO_SLICES'][0])}→{fmt(pa['NO_SLICES'][1])}" if 'NO_SLICES' in pa else '') +
                           ' (stored per-slice orientation/offset arrays also differ)')
        elif isinstance(a, list) or isinstance(b, list):
            out.append(f'`{k}` array differs')
        else:
            out.append(f'`{k}` {minus(a)}→{minus(b)}')
    return '; '.join(out) if out else 'none'


def main():
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    exps = ROOT / 'experiments'
    scans = []
    for rank, (letter, (suffix, plan_stem, role)) in enumerate(SCANS.items(), 1):
        folders = list(exps.glob(f'FSE-DWI_{DAY}_{suffix}'))
        assert len(folders) == 1, (letter, folders)
        folder = folders[0]
        mrd, ppr = next(folder.glob('*.MRD')), next(folder.glob('*.ppr'))
        parsed = parse_mrd(mrd)
        v, records = parsed['values'], parsed['records']
        sv, sr = parse_ppr(ppr.read_text(encoding='latin1'))
        protocol_diffs = differences(sv, v, RUNTIME)
        shared_diffs = {k: pair for k, pair in protocol_diffs.items() if k in sv and k in v}
        embedded_only = {k: pair[1] for k, pair in protocol_diffs.items() if k not in sv}
        sidecar_only = {k: pair[0] for k, pair in protocol_diffs.items() if k not in v}
        # ---- planned PPR comparison -------------------------------------------------
        plan_path = PLAN_DIR / f'FSE-DWI_10-09-2026_{plan_stem}.ppr'
        pv, pr = parse_ppr(plan_path.read_text(encoding='latin1'))
        plan_all = differences(pv, v, RUNTIME)
        plan_shared = {k: pair for k, pair in plan_all.items() if k in pv and k in v}
        plan_active = differences(active_protocol(pv), active_protocol(v))
        plan_active_shared = {k: pair for k, pair in plan_active.items() if k in pv and k in v}
        plan_embedded_only = {k: pair[1] for k, pair in plan_all.items() if k not in pv}
        plan_only = {k: pair[0] for k, pair in plan_all.items() if k not in v}
        etl = int(v['VIEWS_PER_SEGMENT'])
        n = int(v['no_diff_acq'])
        S = parsed['dims']['slices']
        b = v['acq_b'][:n]
        jp = next(folder.glob('*.json'))
        j = json.loads(jp.read_text(encoding='utf-8'))
        zoff = slice_z(v)
        comparisons = {'PEOrder': (j.get('PEOrder'), v['PE_order']),
                       'BValueInputMode': (j.get('BValueInputMode'), v['b_input_mode']),
                       'DiffusionOn': (j.get('DiffusionOn'), v['diff_on']),
                       'SmallDelta_ms': (j.get('SmallDelta_ms'), v['sm_delta'] / 1000),
                       'BigDelta_ms': (j.get('BigDelta_ms'), v['big_delta'] / 1000),
                       'bval_s_per_mm2': (j.get('bval_s_per_mm2'), b),
                       'SliceSpacing_mm': (j.get('SliceSpacing_mm'), v['slice_offset'][-1]),
                       'SliceOffsets_mm': (j.get('SliceOffsets_mm'), zoff)}
        json_check = {k: {'json': a, 'mrd': z, 'match': stable_equal(a, z)} for k, (a, z) in comparisons.items()}
        bp, vp, np_ = next(folder.glob('*.bval')), next(folder.glob('*.bvec')), next(folder.glob('*.nii.gz'))
        bside = [float(x) for x in bp.read_text().split()]
        vec = [[float(x) for x in line.split()] for line in vp.read_text().splitlines() if line.strip()]
        scaled = {k: v[k][:n] for k in DIFF_ARRAYS[1:]}
        expected_vec = [[0.0 if bv == 0 else scaled[k][i] / 1000 for i, bv in enumerate(b)] for k in ('acq_x', 'acq_y', 'acq_z')]
        norms = [sum(vec[a][i] ** 2 for a in range(3)) ** .5 for i in range(n)]
        with gzip.open(np_, 'rb') as f:
            header = f.read(348)
        endian = '<' if struct.unpack('<i', header[:4])[0] == 348 else '>'
        dims = list(struct.unpack(endian + '8h', header[40:56]))
        pixdim = list(struct.unpack(endian + '8f', header[76:108]))
        present = sorted(p.name for p in folder.iterdir() if p.is_file())
        # per (experiment, slice) nonzero check: slice blocks are contiguous inside each experiment block
        blob = mrd.read_bytes()
        d = parsed['dims']
        comp = 8  # complex float32
        slice_bytes = d['samples'] * d['views'] * d['views_2'] * comp
        exp_bytes = slice_bytes * S * d['echoes']
        slice_nonzero = [[any(blob[512 + e * exp_bytes + s * slice_bytes:512 + e * exp_bytes + (s + 1) * slice_bytes])
                          for s in range(S)] for e in range(d['experiments'])]
        imaging_views = parsed['dims']['views'] - int(v['nav_on']) * etl
        row = dict(scan=letter, folder_name=folder.name, role=role, catalog_order=rank, folder=relative(folder), mrd=relative(mrd),
                   mrd_sha256=parsed['sha256'], mrd_bytes=parsed['byte_size'], sidecar_ppr=relative(ppr),
                   sidecar_ppr_sha256=sha256(ppr), sidecar_ppr_basename_matches_scan=ppr.stem == folder.name,
                   planned_ppr=relative(plan_path), planned_ppr_sha256=sha256(plan_path),
                   embedded_ppl=v['PPL'], embedded_ppl_version=re.search(r'twoTE-(\d+\.\d+)\.ppl', v['PPL']).group(1),
                   mrd_mtime_utc=datetime.fromtimestamp(mrd.stat().st_mtime, timezone.utc).isoformat(timespec='seconds'),
                   acquisition_start_counter=v['AcquisitionStartTime'], performance_counter_frequency=v['PerformanceCounterFrequency'],
                   embedded_receiver_gain=v['_ObserveReceiverGain'], embedded_transmit_gain=v['_ObserveTransmitGain'],
                   embedded_decouple_gain=v['_DecoupleTransmitGain'], dims=parsed['dims'], datatype_hex=parsed['datatype_hex'],
                   views_per_segment=etl, raw_views=parsed['dims']['views'], imaging_views=imaging_views, slices=S,
                   slice_offsets_mm=zoff, no_diff_acq=n, b_values=b, diffusion_directions_scaled=scaled,
                   pe_order=v['PE_order'], te_ms=v['te'], esp_ms=v['esp'], tr_ms=v['tr'],
                   dwell_us=dwell_us(v), bandwidth_khz=bandwidth_khz(v), sample_period_record=v['sample_period'],
                   first_crusher_duration_us=v['diff_tcrush'], train_crusher_duration_us=v['tcrush'],
                   first_crusher_baseline_dac=v['diff_crush_amp'], train_crusher_baseline_dac=v['crush_amp'],
                   crusher_schedule=v['crusher_schedule'], crusher_step_pct=v['crusher_step_pct'],
                   crusher_custom_count=v['crusher_custom_count'], crusher_custom_pct=v['crusher_custom_pct'],
                   sidecar_protocol_values_match=not shared_diffs, sidecar_protocol_value_diffs=shared_diffs,
                   sidecar_embedded_only_runtime_values=embedded_only, sidecar_only_values=sidecar_only,
                   plan_reference=PLAN_REFERENCE.get(letter, letter),
                   plan_differences=plan_shared, plan_active_differences=plan_active_shared,
                   plan_embedded_only_records=plan_embedded_only, plan_only_records=plan_only,
                   plan_matches=not plan_active_shared,
                   json=dict(available=True, path=relative(jp), comparisons=json_check),
                   diffusion_sidecars=dict(bval_path=relative(bp), bvec_path=relative(vp), bval_values=bside, bvec_values=vec,
                                           bvec_vector_norms=norms, bval_match=stable_equal(bside, b),
                                           bvec_match=stable_equal(vec, expected_vec)),
                   nifti=dict(path=relative(np_), dims=dims, pixdim=pixdim, datatype=struct.unpack(endian + 'h', header[70:72])[0],
                              shape_matches_mrd=dims[:6] == [4, 128, 128, S, n, 1] or dims[:5] == [4, 128, 128, S, n]),
                   data_payload_complete=parsed['payload_end_offset'] + 120 == parsed['embedded_ppr_offset'],
                   nonzero_experiment_slots=parsed['nonzero_experiment_slots'], nonzero_experiment_count=sum(parsed['nonzero_experiment_slots']),
                   nonzero_experiment_slice_blocks=slice_nonzero,
                   trailing_bytes_before_ppr=parsed['gap_bytes_before_ppr'], present_files=present,
                   _embedded_values={k: x for k, x in v.items() if k not in RUNTIME}, _embedded_records=records,
                   _sidecar_values=sv, _sidecar_records=sr)
        assert row['data_payload_complete'] and all(row['nonzero_experiment_slots']), letter
        assert all(all(x) for x in slice_nonzero), letter
        assert all(x['match'] for x in json_check.values()), (letter, json_check)
        assert row['diffusion_sidecars']['bval_match'] and row['diffusion_sidecars']['bvec_match'] and row['nifti']['shape_matches_mrd'], letter
        assert all(abs(x - 1) < 1e-5 for x, bv in zip(norms, b) if bv), letter
        assert row['sidecar_protocol_values_match'], letter
        scans.append(row)
    by = {r['scan']: r for r in scans}

    # ---- chronology -------------------------------------------------------------------
    assert len({x['performance_counter_frequency'] for x in scans}) == 1
    anchor = min(x['acquisition_start_counter'] for x in scans)
    chrono = sorted(scans, key=lambda x: x['acquisition_start_counter'])
    for rank, row in enumerate(chrono, 1):
        row['counter_order'] = rank
        row['acquisition_elapsed_minutes_from_first'] = (row['acquisition_start_counter'] - anchor) / row['performance_counter_frequency'] / 60
    for r, nxt in zip(chrono, chrono[1:] + [None]):
        r['minutes_to_next_start'] = None if nxt is None else nxt['acquisition_elapsed_minutes_from_first'] - r['acquisition_elapsed_minutes_from_first']

    # ---- pairs ------------------------------------------------------------------------
    pairs = []
    for a, b in itertools.combinations(scans, 2):
        va, vb = a['_embedded_values'], b['_embedded_values']
        ar, br = a['_embedded_records'], b['_embedded_records']
        pairs.append(dict(scan_a=a['scan'], scan_b=b['scan'], same_mrd_sha256=a['mrd_sha256'] == b['mrd_sha256'],
                          protocol_differences=differences(va, vb), active_protocol_differences=differences(active_protocol(va), active_protocol(vb)),
                          raw_record_difference_keys=[k for k in sorted(set(ar) | set(br)) if k not in RUNTIME and ' '.join(ar.get(k, '').split()) != ' '.join(br.get(k, '').split())]))
    repeats = [(p['scan_a'], p['scan_b']) for p in pairs if not p['active_protocol_differences']]
    all_keys = sorted(set().union(*(r['_embedded_values'] for r in scans)))
    varying = {k: {r['scan']: r['_embedded_values'].get(k) for r in scans} for k in all_keys
               if any(not stable_equal(scans[0]['_embedded_values'].get(k), r['_embedded_values'].get(k)) for r in scans[1:])}

    # ---- cross-day: October 7 -----------------------------------------------------------
    oct7 = json.loads((OUT / 'oct07_protocol_audit.json').read_text(encoding='utf-8'))
    o7 = {s['scan']: s for s in oct7['scans']}
    gain_keys = ('_ObserveReceiverGain', '_ObserveTransmitGain', '_DecoupleTransmitGain')
    cross = {}
    for letter, o7name in [('C', 'test1'), ('A', 'test1'), ('D', 'test2'), ('B', 'test2')]:
        dd = differences(active_protocol(o7[o7name]['_embedded_values']), active_protocol(by[letter]['_embedded_values']))
        cross[f'{letter} vs 10-07 {o7name}'] = dd
    cross_gains = {'oct07': {k: sorted({s['_embedded_values'].get(k) for s in oct7['scans']}) for k in gain_keys},
                   'oct10': {k: sorted({r['_embedded_values'].get(k) for r in scans}) for k in gain_keys}}

    # ---- plan deviations -----------------------------------------------------------------
    planned_pairs = {}
    for a_name, b_name in PAIR_ORDER:
        a, b = by[a_name], by[b_name]
        d = differences(active_protocol(a['_embedded_values']), active_protocol(b['_embedded_values']))
        planned_pairs[f'{a_name} vs {b_name}'] = dict(active_differences=d, summary=short_diff(d))

    source_files = [ROOT / 'scanner' / f'FSE_dwi_CPMG_non_CPMG_twoTE-{v}.ppl' for v in ('1.8', '1.81', '1.91', '1.911')]
    audit = dict(title='October 10, 2026 physical scanner protocol audit', scans=scans, controlled_pairs=pairs,
                 planned_pair_comparisons=planned_pairs,
                 plan_deviations={r['scan']: dict(reference_plan=r['plan_reference'], active_differences=r['plan_active_differences'],
                                                  stored_differences=r['plan_differences'],
                                                  embedded_only_records=r['plan_embedded_only_records']) for r in scans},
                 chronology=[dict(scan=r['scan'], counter_order=r['counter_order'], minutes_from_first=r['acquisition_elapsed_minutes_from_first'],
                                  minutes_to_next_start=r['minutes_to_next_start']) for r in chrono],
                 exact_protocol_repeats=repeats, cross_day_vs_oct07=cross, cross_day_gains=cross_gains,
                 all_varying_embedded_fields=varying,
                 available_current_sources=[dict(path=relative(p), sha256=sha256(p)) for p in source_files],
                 method={'authoritative_metadata': 'MRD-embedded PPR describes the acquisition; adjacent PPR and planned-PPR differences are retained explicitly.',
                         'counter': 'Hardware performance counter, relative chronology only; not a civil timestamp.',
                         'payload': 'Dimensions and datatype from binary MRD header; exact 120-byte interstitial region and nonzero experiment/slice blocks checked.',
                         'plan_comparison': 'Embedded values vs the planned PPR (experiments/2026-10-09_exvivo_plan); scan K is compared against plan A. Runtime-only records (gains, delays, masks) occur only in MRDs and are listed separately. Active comparison trims acquisition arrays at no_diff_acq and omits the mode-1 acq_grad cache.',
                         'active_pair_comparison': 'Acquisition arrays trimmed at no_diff_acq; mode-1 acq_grad inactive cache omitted. Full stored arrays/raw record differences retained separately.',
                         'source_identity': 'Embedded PPL paths name releases but contain no source hashes; repository source hashes identify repository copies, not a proven scanner build.'})
    (OUT / 'oct10_protocol_audit.json').write_text(json.dumps(audit, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    csv_write('oct10_protocol_scans.csv', [{k: x for k, x in r.items() if not k.startswith('_')} for r in scans])
    csv_write('oct10_protocol_pairs.csv', pairs)
    csv_write('oct10_protocol_variations.csv', [dict(field=k, **values) for k, values in varying.items()])
    make_catalog(scans, by, chrono, planned_pairs, cross, cross_gains)
    make_audit_notes(scans, by, chrono, pairs, varying, repeats, cross, cross_gains, source_files)
    print('Audited 10 MRDs; counter order:', ', '.join(f'{r["scan"]} ({r["acquisition_elapsed_minutes_from_first"]:.2f})' for r in chrono))
    print('Exact protocol repeats:', repeats or 'none')
    print('Adjacent-PPR discrepancies:', {r['scan']: r['sidecar_protocol_value_diffs'] for r in scans if not r['sidecar_protocol_values_match']} or 'none')
    print('Plan deviations:')
    for r in scans:
        print(' ', r['scan'], '(vs', r['plan_reference'] + ')', short_diff(r['plan_active_differences']) if r['plan_active_differences'] else 'none')
    print('All binary payload, experiment/slice, NIfTI shape, JSON and diffusion-sidecar checks passed.')


def plan_text(r):
    d = r['plan_active_differences']
    if not d:
        return 'None'
    out = []
    keys = set(d)
    groups = {'diffusion list': set(DIFF_ARRAYS) | {'no_diff_acq', 'no_experiments'},
              'slice geometry': {'NO_SLICES', 'FOV_OFFSETS', 'FOV_SLICE_OFF', 'FOV_READ_OFF', 'FOV_PHASE_OFF', 'MULTI_ORIENTATION', 'X_ANGLE', 'Y_ANGLE', 'Z_ANGLE'}}
    if keys & groups['diffusion list']:
        out.append(f'diffusion list {int(d["no_diff_acq"][0])}→{int(d["no_diff_acq"][1])} volumes (plan→acquired)')
    if keys & groups['slice geometry']:
        out.append('slices 1→3, z offsets 0→−1.2, 0, +1.2 mm (plan→acquired)')
    for k, (a, b) in d.items():
        if k in groups['diffusion list'] or k in groups['slice geometry']:
            continue
        if k == 'sample_period':
            out.append(f'`sample_period` {fmt(a[0])}/{fmt(a[1])} ({fmt(a[3])} µs, {fmt(a[2])} kHz)→{fmt(b[0])}/{fmt(b[1])} ({fmt(b[3])} µs, {fmt(b[2])} kHz)')
        else:
            out.append(f'`{k}` {minus(a)}→{minus(b)}')
    return '; '.join(out)


def make_catalog(scans, by, chrono, planned_pairs, cross, cross_gains):
    k_ = by['K']
    lines = ['# Scanner experiments — October 10, 2026', '',
             'All 10 acquisitions were verified using their MRD-embedded PPR, adjacent PPR, reconstructed NIfTI header, JSON and diffusion sidecars, and each embedded protocol was diffed against the PPR it was planned from ([2026-10-09 ex-vivo plan](2026-10-09_exvivo_plan/README.md)). Scans are named by plan letter, so the main tables are in letter order; the chronology table gives actual acquisition-counter order. **Plan scan F (v1.8 polarity) was not acquired. Scan K was added and is not in the plan.** Embedded metadata takes precedence where PPRs differ (here, adjacent PPRs match the embedded protocol exactly for all ten). A version label identifies the recorded scanner PPL path; it does not prove the source/build used on the scanner.', '',
             '**Sample provenance:** The plan expected a fixed ex-vivo rat brain in PBS, but the reconstructed images appear to be a water phantom (uniform disc, signal at the noise floor by b3000). Sample identity and temperature were not supplied — confirm with user. Until then, treat any tissue interpretation in the plan README as unverified.', '',
             'All scans use centric phase encoding (`PE_order=1`), navigators on, stored TR 2000 ms, nominal diffusion duration δ=4 ms, ETL 8 (136 raw views = 128 imaging + 8 navigator), 128 readout samples, 128 imaging phase-encode lines, FOV 35 mm, 1 mm slice thickness and 1.2 mm slice separation, and read-axis (x) diffusion except where E and G add y, z and −x. Crusher plateaus are 1000 / 1000 µs with 200 µs ramps; first diffusion-echo crusher is −5482 DAC in all scans and every schedule is constant (`crusher_schedule=0`, so the stored 40% step in v1.8/v1.81 is inactive). All record RX gain 30, TX gain −203 and decoupler gain −453. Unless stated, TE is 54 ms, ESP is 14 ms (13 ms for v1.911, 11 ms for J and K), Δ is 40 ms and dwell is 50 µs (20 kHz). For the ss-MGOT scans TE 54 ms is the preparation echo, not the first acquired imaging echo. The plan PPRs carry no gain records, so gains were set on the console and are recorded here from the MRDs only. No temperature or ambient notes accompany the data.', '',
             'Crusher entries are **first diffusion echo / train baseline** in DAC units. ETL means echo train length; navigator views are additional raw lines, not extra imaging lines. Directions are in the scanner logical axes as stored (x = read); b=0 volumes embed a nominal +x vector but carry no diffusion weighting.', '',
             '**Protocol identity**', '',
             '| Scan / PPR | Role | PPL path / method | Volumes | b-values (s/mm²) | Directions | Raw / imaging views / ETL | First / train crusher (DAC) |',
             '|---|---|---|---:|---|---|---|---|']
    roles = {r['scan']: r['role'] for r in scans}
    for r in scans:
        v = r['_embedded_values']; version = r['embedded_ppl_version']
        link = Path(r['sidecar_ppr']).relative_to('experiments').as_posix()
        lines.append(f'| [{r["scan"]}]({link}) | {roles[r["scan"]]} | {version} — {METHOD[version]} (`{v["PPL"]}`) | {r["no_diff_acq"]} | {", ".join(f"{b:g}" for b in r["b_values"])} | {directions_text(r)} | {r["raw_views"]} / {r["imaging_views"]} / {r["views_per_segment"]} | {minus(v["diff_crush_amp"])} / {minus(v["crush_amp"])} |')
    lines += ['', '**Timing, geometry, gains and plan agreement**', '',
              '| Scan | ESP (ms) | TE (ms) | TR (ms) | Δ / δ (ms) | Dwell (µs) / bandwidth (kHz) | Slices (z offsets, mm) | RX / TX gain | Adjacent PPR discrepancy | Console-side change vs planned PPR |',
              '|---|---:|---:|---:|---|---|---|---|---|---|']
    for r in scans:
        v = r['_embedded_values']
        z = ', '.join(minus(x) for x in r['slice_offsets_mm'])
        lines.append(f'| {r["scan"]} | {fmt(v["esp"])} | {fmt(v["te"])} | {fmt(v["tr"])} | {v["big_delta"]/1000:g} / {v["sm_delta"]/1000:g} | {fmt(r["dwell_us"])} / {fmt(r["bandwidth_khz"])} | {r["slices"]} ({z}) | {fmt(r["embedded_receiver_gain"])} / {minus(r["embedded_transmit_gain"])} | {"None" if r["sidecar_protocol_values_match"] else "see audit"} | {plan_text(r)}{" (vs plan A)" if r["scan"]=="K" else ""} |')
    comparison = []
    for r in scans:
        v = r['_embedded_values']; version = r['embedded_ppl_version']
        c = dict(scan=r['scan'], role=r['role'], ppr=r['sidecar_ppr'], mrd=r['mrd'], mrd_sha256=r['mrd_sha256'], ppl_version=version, method=METHOD[version],
                 catalog_order=r['catalog_order'], counter_order=r['counter_order'], elapsed_minutes=r['acquisition_elapsed_minutes_from_first'],
                 raw_views=r['raw_views'], imaging_views=r['imaging_views'], etl=r['views_per_segment'], slices=r['slices'], slice_offsets_mm=r['slice_offsets_mm'],
                 b_values=r['b_values'], directions=directions_text(r), diffusion_directions_scaled=r['diffusion_directions_scaled'],
                 rx_gain=r['embedded_receiver_gain'], tx_gain=r['embedded_transmit_gain'], decouple_gain=r['embedded_decouple_gain'],
                 dwell_us=r['dwell_us'], bandwidth_khz=r['bandwidth_khz'],
                 adjacent_ppr_matches_embedded=r['sidecar_protocol_values_match'], adjacent_ppr_differences=r['sidecar_protocol_value_diffs'],
                 plan_reference=r['plan_reference'], plan_matches_active=r['plan_matches'], plan_differences=r['plan_active_differences'])
        for k in ('tr', 'te', 'esp', 'PE_order', 'nav_on', 'sm_delta', 'big_delta', 'sample_period', 'FOV', 'gs_var', 'slice_offset', 'rfcal', 'alpha', 'p180_scale', 'diff_crush_amp', 'crush_amp', 'diff_tcrush', 'tcrush', 'tramp', 'crusher_schedule', 'crusher_step_pct', 'crusher_custom_count', 'crusher_custom_pct', 'crush_independent_on', 'crusher_max_dac', 'crusher_slew_dac_100us', 'gp_init_var', 'SMX', 'SMY', 'gr_var', 'grad_var', 'no_disacq', 'no_discard', 'b_input_mode', 'v19_on', 'v19_cycles', 'v19_comp_flat', 'v19_slab_pml', 'v19_tip_pml', 'v19_spoil_cpmm', 'v19_spoil_dac'):
            c[k] = v.get(k)
        c['active_refocusing_flip_degrees'] = [x / 10 for x in v.get('v19_flip_tenths', [])[:r['views_per_segment']]]
        comparison.append(c)
    csv_write('oct10_scan_comparison.csv', comparison)

    chron_text = ', '.join(r['scan'] for r in chrono)
    lines += ['', '**Chronology and acquisition integrity**', '',
              '| Scan | Counter order | Minutes from first scan | Minutes to next start | Experiments / nonzero raw slots | Reconstructed NIfTI shape | Diffusion sidecars |',
              '|---|---:|---:|---:|---|---|---|']
    for r in scans:
        nxt = '—' if r['minutes_to_next_start'] is None else f'{r["minutes_to_next_start"]:.2f}'
        lines.append(f'| {r["scan"]} | {r["counter_order"]} | {r["acquisition_elapsed_minutes_from_first"]:.2f} | {nxt} | {r["no_diff_acq"]} / {r["nonzero_experiment_count"]} | 128 × 128 × {r["slices"]} × {r["no_diff_acq"]} | JSON / bval / bvec match embedded protocol |')
    nexp = sum(r['no_diff_acq'] for r in scans)
    nz = sum(r['nonzero_experiment_count'] for r in scans)
    e, g = by['E'], by['G']
    lines += ['', f'Counter times provide relative acquisition order, not clock times; the MRD file modification times all fall within about one second of each other (2026-10-10 20:09 UTC) and reflect copying, not acquisition. The order is {chron_text}, i.e. plan-letter order with no exact protocol repeats (the plan\'s optional end-of-session repeat of A was not run, and no scan has an identical active protocol to another); the planned core order A → C → B → D was not followed, B was run second. F was skipped and K was added last. Start-to-start intervals include the acquisition itself, so the longest gaps (about 4.4–5.2 min) belong to the seven- and eight-volume scans and the shortest (about 2.1–2.6 min) to the three-volume scans H, I and J. All {nexp} experiment slots contain nonzero raw data ({nz} nonzero), K\'s {k_["slices"]} × {k_["no_diff_acq"]} slice blocks are all nonzero, and all expected complex payloads are present; this is a completeness check, not evidence of good signal.', '',
              '**Diffusion directions and sign convention**', '',
              f'E and G both contain a −x volume: volume 3 of 8 (b=1000) embeds `acq_x=-1000, acq_y=0, acq_z=0`, and the bvec file stores `-1.000000 0 0` for it, so the bvec preserves the embedded sign (`bvec = acq/1000`, no axis permutation or sign flip). Volumes in E and G are b0; b1000 +x, −x, +y, +z; b3000 +x, +y, +z, and the embedded arrays, bval, bvec and JSON agree. For b=0 the embedded arrays hold a nominal +x (1000, 0, 0) while the bvec holds a zero vector; this is the same convention as 10-07. The embedded values are thousandths of a unit vector in the scanner\'s logical read/phase/slice axes. Whether these axes map to the NIfTI voxel axes with the same sign has not been validated here, so a "−x" in the bvec is a sequence-side polarity, not a verified image-space direction.', '',
              '**New-method parameters**', '']
    b_ = by['B']['_embedded_values']
    lines += [f'B, D, G and I record `v19_on=1` (D is the v1.91 control for B), two cycles of added dephasing across the imaging slice (`v19_cycles={b_["v19_cycles"]:g}`) and a {b_["v19_comp_flat"]:g} µs compensation-lobe plateau. The stored refocusing flip array is in tenths of a degree; the active ETL8 flips are 142.2°, 94.9°, 69.2°, 63.0°, 60.2°, 60°, 60°, 60° (variable flip angle, VFA), identical to 10-07 v1.91. v1.8/v1.81 do not expose the VFA array. All protocols store `rfcal=594`, `alpha=90` and `p180_scale=185`, but the revised branches bypass the legacy `alpha` and `p180_scale` controls; achieved flip angles remain physically unverified. The v1.911 and v1.91 scans additionally store prep slab width {b_["v19_slab_pml"]:g} per mille, tip-up width {b_["v19_tip_pml"]:g} per mille, spoiler moment {b_["v19_spoil_cpmm"]:g} cycles/mm and spoiler amplitude {b_["v19_spoil_dac"]:g} DAC. In all v1.91 and v1.911 scans `crusher_step_pct=0`.', '',
              '**v1.911 ESP 13 ms.** B, G and I use echo spacing 13 ms rather than the 14 ms of the v1.91 control (D) and of 10-07; this is the planned change made in the PPR (no console edit), and it is the only embedded difference besides the PPL path between B and D. Because the shorter spacing and the merged lobes of v1.911 change together, B versus D cannot separate them. v1.911 requires zero slice offset and angle, and all three v1.911 scans have one slice at offset 0.', '',
              '**Controlled comparisons and co-changes**', '',
              'The "recorded differences" column is generated from the acquired embedded protocols (acquisition arrays trimmed at `no_diff_acq`, first scan → second scan).', '',
              '| Comparison | Intended factor | Recorded differences (first → second) | Interpretation / co-changes |', '|---|---|---|---|']
    notes = {
        'A vs C': ('v1.81 vs v1.8 at identical protocol', 'Only the PPL path differs; every embedded protocol field, gain and array matches. This isolates the v1.81 b-value correction (and any other v1.81 source change) with no parameter co-change. C was acquired ' + f"{by['C']['acquisition_elapsed_minutes_from_first']-by['A']['acquisition_elapsed_minutes_from_first']:.1f}" + ' min after A.'),
        'B vs D': ('ss-MGOT v1.911 vs v1.91', 'PPL path and ESP 13 vs 14 ms. Planned co-change: the ESP reduction and v1.911 source changes cannot be separated. All other fields, gains and arrays match.'),
        'E vs A': ('Direction set (b0; b1000 +x, −x, +y, +z; b3000 +x, +y, +z) vs seven-b series', 'Same PPL, geometry, crusher −8223, gains and timing; only the diffusion list differs (8 vs 7 volumes). Not a b-matched comparison except b0, b1000 +x and b3000 +x.'),
        'G vs B': ('Direction set on v1.911', 'Same as E vs A for v1.911: only the diffusion list differs; ESP 13 in both.'),
        'H vs A': ('Train crusher equal to selector (−2741) vs −8223', 'Only the train crusher baseline differs plus the three-b list (0/1000/3000 vs seven b). First-echo crusher stays −5482.'),
        'I vs B': ('Δ 30 / TE 44 vs Δ 40 / TE 54 on v1.911', 'Δ and TE change together by 10 ms each (planned, accepted by the console; no further TE adjustment was needed), with the three-b list. ESP 13 in both. Diffusion time changes, so tissue ADC is not directly comparable.'),
        'J vs A': ('40 kHz readout bandwidth and shorter ESP vs 20 kHz', 'Console-side changes on J: dwell 50→25 µs, `sample_period` code 500/12→250/17, read gradient `gr_var` −735→−1471, `SMX` 0.0224563→0.0449126, ESP 14→11 ms. TE stays 54 ms and Δ stays 40 ms. The three-b list also differs. Bandwidth, ESP, readout gradient and echo-train length in time all change together.'),
        'K vs A': ('Three slices vs one', 'Same J console-side changes (dwell 25 µs, ESP 11, `gr_var`, `SMX`) plus three slices at z = −1.2, 0, +1.2 mm (NO_SLICES 3, FOV_SLICE_OFF −480/0/480) and a two-b list (0/1000). Not a clean slice test against A; use K vs J.'),
        'E vs G': ('v1.81 vs v1.911 at the eight-volume direction set', 'PPL, ESP 14 vs 13, crusher step 40 vs 0 (inactive under constant schedule) and the v1.911 `v19_*` fields. Diffusion list, crusher −8223, gains and geometry match.'),
        'K vs J': ('Three slices vs one at the same readout', 'Slice geometry and the b list (0/1000 vs 0/1000/3000) only; dwell, ESP, `gr_var`, `SMX` and everything else match. Cleanest multi-slice comparison.'),
    }
    for (a, b) in PAIR_ORDER:
        key = f'{a} vs {b}'
        lines.append(f'| {a} / {b} | {notes[key][0]} | {planned_pairs[key]["summary"]} | {notes[key][1]} |')
    cd = cross
    lines += ['', '**Metadata details that affect comparisons**', '',
              'Adjacent PPRs match the embedded protocol exactly for all ten scans (no stale or hand-edited PPRs). J and K\'s adjacent PPRs already contain the console changes. Scanner gains, gradient/RF/receiver delays and masks (`_pts_mask` 13, `_pdd_*_mask` 8, `_use_pdd` 0, all delays 0) occur only in the MRD. Compared with the plan, the only console-side changes are in J (bandwidth, ESP, readout gradient scale) and the unplanned K. In particular, I\'s TE 44 and Δ 30 ms, the ESP 13 settings of B, G and I, and all b and direction lists are exactly as planned.', '',
              'The v1.8/v1.81 arrays reserve 512 entries and the v1.91/v1.911 arrays 64; only the first `no_diff_acq` entries are active. `acq_grad` is an inactive cache in b-input mode 1 (stale from the 10-07 base protocols), as noted in the plan generator. The standalone PPR filenames match their scan folders. Scan K has three slices, so its reconstructed NIfTI is 128 × 128 × 3 × 2 with the JSON slice offsets −1.2, 0, 1.2 mm and NIfTI slice pixdim 1.2 mm; the other nine scans are single-slice.', '',
              'All b-values are requested values. The v1.8 read-axis cross term makes the effective b differ from nominal for +x versus −x; the plan predicts about 1176 and 842 at nominal b1000. No F scan was acquired, and E and G use the revised v1.81 / v1.911 sources, so this effect is not directly measured today. Matching metadata does not validate the effective b-tensor or gradient calibration.', '',
              '**Cross-day notes (vs October 7)**', '']
    oc = cross_gains
    lines += [f'RX gain is {oc["oct10"]["_ObserveReceiverGain"][0]:g} on both days and decoupler gain is {minus(oc["oct10"]["_DecoupleTransmitGain"][0])} on both, but TX gain is {minus(oc["oct10"]["_ObserveTransmitGain"][0])} today versus {minus(oc["oct07"]["_ObserveTransmitGain"][0])} on 10-07 (and −205 on 10-05). The gain-to-amplitude conversion has not been validated, so brightness comparisons across days confound sequence and gain changes. Embedded protocols otherwise inherit the 10-07 base protocols: ']
    for k, d in cross.items():
        lines.append(f'- {k}: {short_diff(d)}.')
    lines += ['', 'Today\'s sample appears to be a water phantom again, but this is unconfirmed. Geometry, phase-encode calibration (`gp_init_var=-1000`, `SMY=0.0305406`, ETL 8), RF scales and crusher baselines equal those of 10-07 test1/test2 apart from the items above.', '',
              'The [complete comparison CSV](../docs/data/oct10_scan_comparison.csv) includes common important parameters and every new-method control. The [protocol audit](../docs/data/oct10_protocol_audit.md), [all varying embedded fields](../docs/data/oct10_protocol_variations.csv), [scan metadata CSV](../docs/data/oct10_protocol_scans.csv) and [all 45 pair comparisons](../docs/data/oct10_protocol_pairs.csv) retain the full differences. Rebuild the catalog and audit with `python docs/data/oct10_protocol_audit.py`.', '']
    (ROOT / 'experiments/scan_catalog_2026-10-10.md').write_text('\n'.join(lines), encoding='utf-8')


def make_audit_notes(scans, by, chrono, pairs, varying, repeats, cross, cross_gains, source_files):
    lines = ['# October 10 physical scanner protocol audit', '',
             'Reproducible script: [oct10_protocol_audit.py](oct10_protocol_audit.py). Detailed outputs: [JSON](oct10_protocol_audit.json), [scans CSV](oct10_protocol_scans.csv), [pairs CSV](oct10_protocol_pairs.csv), [varying fields CSV](oct10_protocol_variations.csv), [comparison CSV](oct10_scan_comparison.csv). The script uses only Python’s standard library and the October 5 PPR/MRD parser.', '',
             'All 10 MRDs have datatype 0x15 (complex 32-bit floating components), complete dimension-derived payloads and exactly 120 bytes between payload and embedded PPR. All %d experiment slots (and all slice blocks of three-slice scan K) contain nonzero raw data. Every reconstructed NIfTI header is 128 × 128 × slices × acquired experiments. Every JSON PE order, b-input mode, diffusion flag, δ/Δ, b array, slice offset list and slice spacing agrees with embedded acquisition metadata. Every bval and bvec agrees, using a zero vector for b=0; non-zero bvec columns are unit vectors. These checks establish structural completeness and metadata consistency, not image quality or calibrated diffusion accuracy.' % sum(r['no_diff_acq'] for r in scans), '',
             'Acquisition chronology (counter order, minutes from first scan): ' + ', '.join(f'{r["scan"]} ({r["acquisition_elapsed_minutes_from_first"]:.2f})' for r in chrono) + '. All use the same 10 MHz hardware-counter frequency; counter values are not calendar timestamps. Exact active-protocol repeats: ' + (', '.join('/'.join(p) for p in repeats) if repeats else 'none') + '.', '',
             'Receiver gain %s, transmit gain %s and decoupler gain %s in every scan (10-07: %s / %s / %s). Adjacent PPRs omit scanner runtime gains, masks and delays but otherwise match the embedded protocol exactly in all ten scans.' % (
                 fmt(cross_gains['oct10']['_ObserveReceiverGain'][0]), minus(cross_gains['oct10']['_ObserveTransmitGain'][0]), minus(cross_gains['oct10']['_DecoupleTransmitGain'][0]),
                 fmt(cross_gains['oct07']['_ObserveReceiverGain'][0]), minus(cross_gains['oct07']['_ObserveTransmitGain'][0]), minus(cross_gains['oct07']['_DecoupleTransmitGain'][0])), '',
             '## Differences from the planned PPRs (console-side changes)', '',
             'Each embedded protocol is compared with the planned PPR in `experiments/2026-10-09_exvivo_plan/` (scan K against plan A). Differences below are active-protocol differences (plan → acquired); records that exist only in the MRD (gains, delays, masks) are not deviations because the plan PPRs carry none.', '',
             '| Scan | Reference plan | Active differences (plan → acquired) |', '|---|---|---|']
    for r in scans:
        lines.append(f'| {r["scan"]} | {r["plan_reference"]} | {plan_text(r)} |')
    lines += ['', 'MRD-only records common to all scans: ' + ', '.join(f'`{k}`' for k in sorted(by['A']['plan_embedded_only_records'])) + '.', '',
              '## Planned-pair comparisons (acquired vs acquired)', '', '| Pair | Differences (first → second) |', '|---|---|']
    for (a, b) in PAIR_ORDER:
        d = differences(active_protocol(by[a]['_embedded_values']), active_protocol(by[b]['_embedded_values']))
        lines.append(f'| {a} vs {b} | {short_diff(d)} |')
    lines += ['', '## Cross-day (October 7) active-protocol differences', '']
    for k, d in cross.items():
        lines.append(f'- {k}: {short_diff(d)}')
    lines += ['', '## Diffusion arrays and sign convention', '', '| Scan | Volume | b | Embedded x, y, z (thousandths) | bvec column |', '|---|---:|---:|---|---|']
    for r in scans:
        if r['scan'] in ('E', 'G'):
            for i, bv in enumerate(r['b_values']):
                emb = [r['diffusion_directions_scaled'][k][i] for k in ('acq_x', 'acq_y', 'acq_z')]
                bc = [r['diffusion_sidecars']['bvec_values'][a][i] for a in range(3)]
                lines.append(f'| {r["scan"]} | {i+1} | {bv:g} | {", ".join(f"{x:g}" for x in emb)} | {", ".join(f"{x:g}" for x in bc)} |')
    lines += ['', 'The −x volume (volume 3) is present in both E and G, with sign preserved in the bvec (−1). b=0 volumes embed +x but bvec is zero.', '',
              'All 45 scan pairs are compared using every normalized embedded field and every raw PPR record, excluding only counter, frequency and END. The JSON contains full stored arrays. A second pair-difference field trims active acquisition arrays to `no_diff_acq` and removes inactive `acq_grad` caches in b-input mode 1.', '',
              'Stored varying fields: ' + ', '.join(f'`{k}`' for k in varying) + '. Common fields are retained in each scan’s `_embedded_values` and `_embedded_records`.', '',
              'The MRDs embed release paths ending in 1.8, 1.81, 1.91 or 1.911. Repository source copies are present in `scanner/`; their SHA-256 identities are recorded under `available_current_sources` in the JSON. The MRD carries no source-content hash, so matching version/path labels cannot prove which build generated each acquisition.', '']
    (OUT / 'oct10_protocol_audit.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    main()
