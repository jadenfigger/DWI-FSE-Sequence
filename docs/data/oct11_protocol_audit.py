"""Audit the October 11 MRDs and regenerate the scan catalog (standard library only).

Run: python docs/data/oct11_protocol_audit.py
Reads acquisition files without changing them. Uses the October 5 MRD/PPR parser
(oct05_protocol_audit.py). Each acquired embedded protocol is compared with
(a) the adjacent PPR in its own folder, (b) the console-compatible planned PPR
(experiments/2026-10-11_exvivo_plan_console_fixed/), and (c) the original planned
PPR (experiments/2026-10-11_exvivo_plan/). Unplanned TT and UU are compared with
their planned references T and U; unplanned v1.911-0 is compared with the
2026-10-10 scan I MRD. Scanner records (gains, masks, delays, observe frequency)
exist only in the MRDs and are reported separately from protocol fields.
"""
from __future__ import annotations

import csv
import gzip
import json
import re
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from oct05_protocol_audit import parse_mrd, parse_ppr, sha256, stable_equal  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/data'
EXPS = ROOT / 'experiments'
PLAN_ORIG = EXPS / '2026-10-11_exvivo_plan'
PLAN_CF = EXPS / '2026-10-11_exvivo_plan_console_fixed'
CATALOG = EXPS / 'scan_catalog_2026-10-11.md'
DAY = '10-11-2026'
PRIOR_DAY = '10-10-2026'

# scan key -> (folder suffix, planned letter used as reference or None)
SCANS = {
    'A': ('v182_testA', 'A'), 'B': ('v1912_testB', 'B'), 'C': ('v182_testC', 'C'),
    'AB': ('v182_testAB', 'AB'), 'E': ('v182_testE', 'E'), 'G': ('v182_testG', 'G'),
    'I': ('v182_testI', 'I'), 'M': ('v182_testM', 'M'), 'N': ('v1912_testN', 'N'),
    'K': ('v182_testK', 'K'), 'O': ('v182_testO', 'O'), 'Q': ('v182_testQ', 'Q'),
    'S': ('v182_testS', 'S'), 'T': ('v182_testT', 'T'), 'TT': ('v182_testTT', 'T'),
    'U': ('v1912_testU', 'U'), 'UU': ('v1912_testUU', 'U'), 'V': ('v182_testV', 'V'),
    '0': ('v1911_test0', None),
}
# display order: plan order with unplanned repeats after their references; v1.911-0 last
ORDER = ['A', 'B', 'C', 'AB', 'E', 'G', 'I', 'M', 'N', 'K', 'O', 'Q', 'S', 'T', 'TT', 'U', 'UU', 'V', '0']
LABEL = {k: k for k in SCANS}
LABEL['0'] = 'v1.911-0'
# 2026-10-10 scans used as the same-letter cross-day comparison
PRIOR = {'A': 'v181_testA', 'B': 'v1911_testB', 'C': 'v18_testC', 'E': 'v181_testE',
         'G': 'v1911_testG', 'I': 'v1911_testI', 'K': 'v181_testK'}
PRIOR_I = 'v1911_testI'          # reference for v1.911-0
RUNTIME = {'AcquisitionStartTime', 'PerformanceCounterFrequency', 'END'}
ACQ_ARRAYS = ('acq_b', 'acq_x', 'acq_y', 'acq_z')
GEOMETRY_KEYS = {'NO_SLICES', 'FOV_OFFSETS', 'FOV_SLICE_OFF', 'FOV_READ_OFF', 'FOV_PHASE_OFF',
                 'MULTI_ORIENTATION', 'X_ANGLE', 'Y_ANGLE', 'Z_ANGLE', 'slice_offset'}
DIFFUSION_KEYS = set(ACQ_ARRAYS) | {'no_diff_acq', 'no_experiments'}
METHOD = {'1.8': 'legacy', '1.81': 'revised legacy', '1.82': 'v1.82 (plan label; no method label in plan generator)',
          '1.91': 'ss-MGOT', '1.911': 'ss-MGOT revised', '1.912': 'ss-MGOT v1.912 (plan label)'}
# pairs: (first, second, factor, interpretation); filled in from the audit output
PAIRS = [
    ('A', 'B', 'v1.82 vs v1.912 at the matched seven-b 20-kHz baseline', None),
    ('A', 'T', 'Drift repeat of A (two volumes, b10/b1000)', None),
    ('B', 'U', 'Drift repeat of B (two volumes, b10/b1000)', None),
    ('M', 'N', 'Planned matched navigator pair (acquired as volume navigators in both)', None),
    ('E', 'M', 'Planned nav2 control against E (acquired nav1 in both)', None),
    ('E', 'G', '40-kHz ESP 11 vs 12 ms with the three-volume vs single-volume lists', None),
    ('G', 'I', '40-kHz vs 20-kHz readout at ESP 12 vs 15 ms', None),
    ('Q', 'E', 'Δ30 / TE44 vs Δ40 / TE54 at 40 kHz', None),
    ('K', 'O', 'Spacing and off-centre phase: ±1.2 mm (three volumes) vs ±5 mm (one volume)', None),
    ('O', 'S', 'Off-centre slice spacing: ±5 mm vs ±2.4 mm', None),
    ('K', 'S', 'Slice spacing: ±1.2 mm vs ±2.4 mm', None),
    ('T', 'TT', 'In-plane FOV offset only (read +3.99875, phase −6.0025 mm)', None),
    ('U', 'UU', 'Single-b10 variant with TR 5000, TE 34, Δ 20 ms and the same in-plane offset', None),
    ('S', 'V', 'Same ±2.4-mm spacing: one-volume 128 matrix vs 256 matrix, 10-volume pilot', None),
]


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def fmt(v):
    if v is None:
        return '—'
    if isinstance(v, str):
        return v
    if isinstance(v, (list, tuple)):
        return ', '.join(fmt(x) for x in v)
    return f'{v:g}'


def minus(v):
    return fmt(v).replace('-', '−')


def active(values: dict) -> dict:
    """Protocol values with runtime-only records removed and acquisition arrays trimmed to no_diff_acq.
    acq_grad is an inactive cache in b-input mode 1 and is ignored entirely."""
    v = {k: x for k, x in values.items() if k not in RUNTIME and k != 'acq_grad'}
    n = int(v['no_diff_acq'])
    for k in ACQ_ARRAYS:
        if isinstance(v.get(k), list):
            v[k] = v[k][:n]
    return v


def is_scanner_record(key: str) -> bool:
    return key.startswith('_') or key.endswith(('Delay', 'Mask'))


def compare(ref_values: dict, acq_values: dict) -> dict:
    """Split differences into protocol fields and scanner records (gains, masks, delays)."""
    ref, acq = active(ref_values), active(acq_values)
    out = dict(protocol={}, scanner_records={}, reference_only={}, acquired_only={})
    for k in sorted(set(ref) | set(acq)):
        if k in ref and k in acq:
            if not stable_equal(ref[k], acq[k]):
                bucket = 'scanner_records' if is_scanner_record(k) else 'protocol'
                out[bucket][k] = [ref[k], acq[k]]
        elif is_scanner_record(k):
            out['scanner_records'][k] = [ref.get(k), acq.get(k)]
        elif k in ref:
            out['reference_only'][k] = ref[k]
        else:
            out['acquired_only'][k] = acq[k]
    return out


def fov_triplets(values):
    """FOV_OFFSETS record [N, x, y, z, ...] -> list of (x, y, z) per slice (mm)."""
    vals = values[1:]
    return [tuple(vals[i:i + 3]) for i in range(0, len(vals), 3)]


def slice_z(v) -> list:
    return [t[2] for t in fov_triplets(v['FOV_OFFSETS'])]


def dwell_us(v):
    return v['sample_period'][3]


def bandwidth_khz(v):
    return v['sample_period'][2]


def direction_label(b, x, y, z):
    if b == 0:
        return 'b0'
    comps = [(n, c) for n, c in zip('xyz', (x, y, z)) if c]
    if len(comps) == 1:
        n, c = comps[0]
        return ('+' if c > 0 else '−') + n
    return '(' + ', '.join(f'{minus(c / 1000)}{n}' for n, c in comps) + ')'


def directions_text(v):
    n = int(v['no_diff_acq'])
    groups, order = {}, []
    for i in range(n):
        b = v['acq_b'][i]
        if b not in groups:
            groups[b] = []
            order.append(b)
        groups[b].append(direction_label(b, v['acq_x'][i], v['acq_y'][i], v['acq_z'][i]))
    if all(all(lbl == '+x' for lbl in groups[b]) for b in order if b):
        return '+x (read) for every b>0'
    return '; '.join(('b0' if b == 0 else f'b{b:g} ' + ', '.join(groups[b])) for b in order)


def describe_key(key, a, b):
    if key == 'PPL':
        va = re.search(r'twoTE-(\d+\.\d+)', str(a)).group(1)
        vb = re.search(r'twoTE-(\d+\.\d+)', str(b)).group(1)
        return f'PPL {va}→{vb}'
    if key == 'sample_period':
        return f'dwell {fmt(a[3])}→{fmt(b[3])} µs ({fmt(a[2])}→{fmt(b[2])} kHz)'
    if key == 'big_delta':
        return f'Δ {fmt(a / 1000)}→{fmt(b / 1000)} ms'
    if key == 'sm_delta':
        return f'δ {fmt(a / 1000)}→{fmt(b / 1000)} ms'
    if key == 'te':
        return f'TE {minus(a)}→{minus(b)} ms'
    if key == 'tr':
        return f'TR {minus(a)}→{minus(b)} ms'
    if key == 'esp':
        return f'ESP {minus(a)}→{minus(b)} ms'
    if key == 'no_views':
        return f'raw views {minus(a)}→{minus(b)}'
    if key == 'nav_on':
        return f'nav_on {minus(a)}→{minus(b)}'
    if key == 'no_samples':
        return f'samples {minus(a)}→{minus(b)}'
    if key in ('_ObserveReceiverGain', '_ObserveTransmitGain', '_DecoupleTransmitGain'):
        return f'`{key}` {minus(a)}→{minus(b)}'
    if isinstance(a, list) or isinstance(b, list):
        return f'`{key}` array differs'
    return f'`{key}` {minus(a)}→{minus(b)}'


def summarize(d: dict) -> str:
    """Human-readable summary of {field: [reference, acquired]} differences."""
    if not d:
        return 'none'
    out, handled = [], set()
    keys = set(d)
    if keys & DIFFUSION_KEYS:
        pieces = []
        if 'acq_b' in d:
            rb, ab = d['acq_b']
            blist = f'b {"/".join(fmt(x) for x in rb)} → {"/".join(fmt(x) for x in ab)}'
            if len(rb) == len(ab):
                pieces.append(f'{len(rb)} volumes, {blist}')
            else:
                pieces.append(f'{len(rb)}→{len(ab)} volumes ({blist})')
        elif 'no_diff_acq' in d:
            pieces.append(f'{fmt(d["no_diff_acq"][0])}→{fmt(d["no_diff_acq"][1])} volumes')
        if keys & {'acq_x', 'acq_y', 'acq_z'}:
            # compare directions only over volumes present on both sides; a change in volume count alone is not a direction change
            dir_keys = [k for k in ('acq_x', 'acq_y', 'acq_z') if k in d]
            m = min(min(len(d[k][0]), len(d[k][1])) for k in dir_keys)
            if any(d[k][0][i] != d[k][1][i] for k in dir_keys for i in range(m)):
                pieces.append('directions differ')
        out.append('diffusion list ' + ('; '.join(pieces) if pieces else 'differs'))
        handled |= DIFFUSION_KEYS
    if keys & GEOMETRY_KEYS:
        geo = []
        if 'FOV_OFFSETS' in d:
            ref, acq = d['FOV_OFFSETS']
            if isinstance(ref, list) and isinstance(acq, list):
                tr, ta = fov_triplets(ref), fov_triplets(acq)
                if [t[:2] for t in tr] != [t[:2] for t in ta]:
                    geo.append(f'in-plane FOV offset (read, phase) {minus(tr[0][0])}, {minus(tr[0][1])}→'
                               f'{minus(ta[0][0])}, {minus(ta[0][1])} mm')
                if [t[2] for t in tr] != [t[2] for t in ta]:
                    geo.append(f'z offsets {minus([t[2] for t in tr])}→{minus([t[2] for t in ta])} mm')
            else:
                geo.append('FOV_OFFSETS rows restored (original plan had count only)')
        if 'NO_SLICES' in d:
            geo.insert(0, f'slices {fmt(d["NO_SLICES"][0])}→{fmt(d["NO_SLICES"][1])}')
        if 'slice_offset' in d:
            geo.append(f'slice separation {fmt(d["slice_offset"][0][-1])}→{fmt(d["slice_offset"][1][-1])} mm')
        if not geo:
            geo.append('slice geometry records differ')
        out.append('; '.join(geo))
        handled |= GEOMETRY_KEYS
    for k in sorted(keys - handled):
        out.append(describe_key(k, *d[k]))
    return '; '.join(out)


def scan_folder(suffix: str) -> Path:
    folders = [p for p in EXPS.glob(f'FSE-DWI_{DAY}_{suffix}') if p.is_dir()]
    assert len(folders) == 1, (suffix, folders)
    return folders[0]


def sidecar(folder: Path, pattern: str, skip=('protocol_notes', '_beff', '_bmatrix')):
    hits = [p for p in sorted(folder.glob(pattern)) if not any(s in p.name for s in skip)]
    assert len(hits) <= 1, (folder.name, pattern, hits)
    return hits[0] if hits else None


def nifti_info(path: Path):
    with gzip.open(path, 'rb') as f:
        header = f.read(348)
    endian = '<' if struct.unpack('<i', header[:4])[0] == 348 else '>'
    dims = list(struct.unpack(endian + '8h', header[40:56]))
    pixdim = list(struct.unpack(endian + '8f', header[76:108]))
    return dims, pixdim


def csv_write(name: str, rows: list, columns=None):
    columns = columns or list(rows[0])
    with (OUT / name).open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(row.get(k), ensure_ascii=False) if isinstance(row.get(k), (dict, list)) else row.get(k)
                             for k in columns})


def read_run_order(folder: Path) -> dict:
    with (folder / 'run_order.csv').open(encoding='utf-8-sig', newline='') as f:
        return {row['test']: row for row in csv.DictReader(f)}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    run_orig = read_run_order(PLAN_ORIG)
    scans = []
    for letter in ORDER:
        suffix, plan_letter = SCANS[letter]
        folder = scan_folder(suffix)
        mrd = next(folder.glob('*.MRD'))
        ppr = sidecar(folder, '*.ppr')
        parsed = parse_mrd(mrd)
        v = parsed['values']
        n = int(v['no_diff_acq'])
        sv, _ = parse_ppr(ppr.read_text(encoding='latin1'))
        etl = int(v['VIEWS_PER_SEGMENT'])
        S = parsed['dims']['slices']
        imaging_views = parsed['dims']['views'] - int(v['nav_on']) * etl
        b = v['acq_b'][:n]
        zoff = slice_z(v)
        fx, fy = [t[0] for t in fov_triplets(v['FOV_OFFSETS'])], [t[1] for t in fov_triplets(v['FOV_OFFSETS'])]
        assert int(v['b_input_mode']) == 1, letter

        # ---- references -------------------------------------------------------------------
        references = {'adjacent': dict(path=ppr, label=relative(ppr))}
        if plan_letter:
            row = run_orig[plan_letter]
            references['planned_console_fixed'] = dict(path=PLAN_CF / row['PPR'], label=relative(PLAN_CF / row['PPR']))
            references['planned_original'] = dict(path=PLAN_ORIG / row['PPR'], label=relative(PLAN_ORIG / row['PPR']))
            for key in ('planned_console_fixed', 'planned_original'):
                assert references[key]['path'].exists(), references[key]['path']
        else:
            prior_folder = EXPS / f'FSE-DWI_{PRIOR_DAY}_{PRIOR_I}'
            prior_mrd = next(prior_folder.glob('*.MRD'))
            references['planned_console_fixed'] = dict(path=prior_mrd, label=relative(prior_mrd) + ' (10-10 scan I MRD; no plan)')
            references['planned_original'] = dict(path=prior_mrd, label=relative(prior_mrd) + ' (10-10 scan I MRD; no plan)')
        diffs = {}
        for name, ref in references.items():
            if ref['path'].suffix.upper() == '.MRD':
                ref_values = parse_mrd(ref['path'])['values']
            else:
                ref_values = parse_ppr(ref['path'].read_text(encoding='latin1'))[0]
            diffs[name] = dict(reference=ref['label'], **compare(ref_values, v))
        # cross-day reference for same-letter scans (10-10); not used for the plan
        cross_day = None
        if letter in PRIOR:
            pf = EXPS / f'FSE-DWI_{PRIOR_DAY}_{PRIOR[letter]}'
            pm = next(pf.glob('*.MRD'))
            cross_day = dict(reference=relative(pm), **compare(parse_mrd(pm)['values'], v))
        if letter == '0':
            pm = next((EXPS / f'FSE-DWI_{PRIOR_DAY}_{PRIOR_I}').glob('*.MRD'))
            cross_day = dict(reference=relative(pm), **compare(parse_mrd(pm)['values'], v))

        # ---- sidecars ---------------------------------------------------------------------
        json_path = sidecar(folder, '*.json')
        bval_path = sidecar(folder, '*.bval')
        bvec_path = sidecar(folder, '*.bvec')
        beff_path = next(folder.glob('*_beff.bval'), None)
        nii_path = sidecar(folder, '*.nii.gz')
        notes_path = folder / 'protocol_notes.json'
        json_check = None
        if json_path:
            j = json.loads(json_path.read_text(encoding='utf-8'))
            comparisons = {
                'PEOrder': (j.get('PEOrder'), v['PE_order']),
                'BValueInputMode': (j.get('BValueInputMode'), v['b_input_mode']),
                'DiffusionOn': (j.get('DiffusionOn'), v['diff_on']),
                'SmallDelta_ms': (j.get('SmallDelta_ms'), v['sm_delta'] / 1000),
                'BigDelta_ms': (j.get('BigDelta_ms'), v['big_delta'] / 1000),
                'bval_s_per_mm2': (j.get('bval_s_per_mm2'), b),
                'SliceSpacing_mm': (j.get('SliceSpacing_mm'), v['slice_offset'][-1]),
                'SliceOffsets_mm': (j.get('SliceOffsets_mm'), zoff),
            }
            json_check = {k: dict(json=a, mrd=z, match=stable_equal(a, z)) for k, (a, z) in comparisons.items()}
            assert all(x['match'] for x in json_check.values()), (letter, json_check)
        diffusion = None
        if bval_path and bvec_path:
            bside = [float(x) for x in bval_path.read_text().split()]
            vec = [[float(x) for x in line.split()] for line in bvec_path.read_text().splitlines() if line.strip()]
            scaled = {k: v[k][:n] for k in ACQ_ARRAYS[1:]}
            # The bvec/bmatrix store the embedded direction normalised to unit length (rounded integers in the MRD).
            expected_vec = []
            for k in ('acq_x', 'acq_y', 'acq_z'):
                expected_vec.append([0.0] * n)
            for i, bv in enumerate(b):
                if bv:
                    vec3 = [scaled[k][i] for k in ('acq_x', 'acq_y', 'acq_z')]
                    mag = sum(x * x for x in vec3) ** .5
                    for a in range(3):
                        expected_vec[a][i] = vec3[a] / mag
            norms = [sum(vec[a][i] ** 2 for a in range(3)) ** .5 for i in range(n)]
            norms_ok = all((abs(norms[i] - 1) < 1e-5) if b[i] else (norms[i] < 1e-9) for i in range(n))
            vec_close = len(vec) == 3 and all(len(vec[a]) == n and all(abs(vec[a][i] - expected_vec[a][i]) <= 1e-5 for i in range(n))
                                              for a in range(3))
            embedded_norm = [sum(scaled[k][i] ** 2 for k in ('acq_x', 'acq_y', 'acq_z')) ** .5 / 1000 for i in range(n)]
            diffusion = dict(bval_path=relative(bval_path), bvec_path=relative(bvec_path), bval_values=bside,
                             bvec_values=vec, bval_match=stable_equal(bside, b), bvec_match=vec_close,
                             bvec_norms_ok=norms_ok, embedded_vector_norms=embedded_norm,
                             bvec_is_normalised_embedded=vec_close)
            assert diffusion['bval_match'] and vec_close and norms_ok, letter
        beff_values = None
        if beff_path:
            beff_values = [float(x) for x in beff_path.read_text().split()]
        json_effective = None
        if json_path:
            json_effective = dict(source=j.get('BMatrixSource'), effective_b_equals_nominal=stable_equal(j.get('EffectiveBValue', []), b),
                                  warning=[w for w in j.get('BMatrixWarnings', []) if 'unavailable' in w][:1])
        nifti = None
        if nii_path:
            dims, pixdim = nifti_info(nii_path)
            ndim = dims[0]
            sizes = (dims[1:1 + ndim] + [1, 1, 1, 1])[:4]
            expected = [parsed['dims']['samples'], imaging_views, S, n]
            nifti = dict(path=relative(nii_path), dims=dims, pixdim=pixdim, shape_xyzt=sizes, expected_xyzt=expected,
                         shape_matches_mrd=sizes == expected)
            assert nifti['shape_matches_mrd'], (letter, sizes, expected)

        # ---- payload and slices ------------------------------------------------------------
        blob = mrd.read_bytes()
        d = parsed['dims']
        comp = 8
        slice_bytes = d['samples'] * d['views'] * d['views_2'] * comp
        exp_bytes = slice_bytes * S * d['echoes']
        slice_nonzero = [[any(blob[512 + e * exp_bytes + s * slice_bytes:512 + e * exp_bytes + (s + 1) * slice_bytes])
                          for s in range(S)] for e in range(d['experiments'])]
        payload_complete = parsed['payload_end_offset'] + 120 == parsed['embedded_ppr_offset']
        assert payload_complete and all(parsed['nonzero_experiment_slots']) and all(all(x) for x in slice_nonzero), letter

        ppl = v['PPL']
        version = re.search(r'twoTE-(\d+\.\d+)\.ppl', ppl).group(1)
        dirs = [[v['acq_x'][i] / 1000, v['acq_y'][i] / 1000, v['acq_z'][i] / 1000] for i in range(n)]
        present = sorted(p.name for p in folder.iterdir() if p.is_file())
        rows = dict(
            scan=letter, label=LABEL[letter], role=run_orig[plan_letter]['purpose'] if plan_letter in run_orig else None,
            folder=relative(folder), ppr=relative(ppr), mrd=relative(mrd), mrd_sha256=parsed['sha256'], mrd_bytes=parsed['byte_size'],
            ppl_path=ppl, ppl_version=version, method=METHOD.get(version),
            counter=v['AcquisitionStartTime'], counter_frequency=v['PerformanceCounterFrequency'],
            no_experiments=n, slices=S, slice_z_offsets_mm=zoff, fov_read_offsets_mm=fx, fov_phase_offsets_mm=fy,
            raw_views=d['views'], samples=d['samples'], imaging_views=imaging_views, etl=etl,
            nav_on=int(v['nav_on']), pe_order=v['PE_order'], tr_ms=v['tr'], te_ms=v['te'], esp_ms=v['esp'],
            big_delta_ms=v['big_delta'] / 1000, sm_delta_ms=v['sm_delta'] / 1000, dwell_us=dwell_us(v), bandwidth_khz=bandwidth_khz(v),
            b_values=b, directions_xyz=dirs, directions=directions_text(v),
            crush_amp=v['crush_amp'], diff_crush_amp=v['diff_crush_amp'], tcrush_us=v['tcrush'], diff_tcrush_us=v['diff_tcrush'],
            rx_gain=v['_ObserveReceiverGain'], tx_gain=v['_ObserveTransmitGain'], decoupler_gain=v['_DecoupleTransmitGain'],
            rfcal=v.get('rfcal'), gp_init_var=v.get('gp_init_var'),
            fov_read_off_dac=v['FOV_READ_OFF'][1], fov_phase_off_dac=v['FOV_PHASE_OFF'][1],
            folder_ppr_identical_to_console_fixed=bool(references['planned_console_fixed']['path'].suffix.lower() == '.ppr' and
                                                       sha256(ppr) == sha256(references['planned_console_fixed']['path'])),
            nifti_present=nii_path is not None, protocol_notes_present=notes_path.exists(),
            json_present=json_path is not None, diffusion_sidecars_present=bool(bval_path and bvec_path),
            nonzero_experiment_slots=parsed['nonzero_experiment_slots'], nonzero_experiment_count=sum(parsed['nonzero_experiment_slots']),
            payload_complete=payload_complete, present_files=present, mrd_mtime_utc=datetime.fromtimestamp(mrd.stat().st_mtime, timezone.utc).isoformat(timespec='seconds'),
            v19={k: v.get(k) for k in ('v19_on', 'v19_cycles', 'v19_comp_flat', 'v19_slab_pml', 'v19_tip_pml', 'v19_spoil_cpmm', 'v19_spoil_dac')},
            active_flip_degrees=[x / 10 for x in v.get('v19_flip_tenths', [])[:etl]] if 'v19_flip_tenths' in v else None,
            rfcal_alpha_p180=[v.get('rfcal'), v.get('alpha'), v.get('p180_scale')],
            crusher_schedule=v['crusher_schedule'], crusher_step_pct=v['crusher_step_pct'],
            planned_reference=references.get('planned_console_fixed', {}).get('label'),
            diffs=diffs, cross_day_oct10=cross_day, json=json_check, json_effective_b=json_effective,
            diffusion=diffusion, beff_bval_values=beff_values, nifti=nifti,
            _embedded_values={k: x for k, x in v.items() if k not in RUNTIME},
            _embedded_records=parsed['records'], _slice_nonzero=slice_nonzero, _folder_ppr_sha256=sha256(ppr),
            _json_path=relative(json_path) if json_path else None,
        )
        scans.append(rows)

    by = {r['scan']: r for r in scans}
    v19_sets = {json.dumps(by[k]['v19'], sort_keys=True) for k in ('B', 'N', 'U', 'UU', '0')}
    assert len(v19_sets) == 1, v19_sets          # v1.912/v1.911 new-method records identical across these scans

    # ---- chronology ---------------------------------------------------------------------
    assert len({r['counter_frequency'] for r in scans}) == 1
    anchor = min(r['counter'] for r in scans)
    chrono = sorted(scans, key=lambda r: r['counter'])
    for rank, r in enumerate(chrono, 1):
        r['counter_order'] = rank
        r['minutes_from_first'] = (r['counter'] - anchor) / r['counter_frequency'] / 60
    for r, nxt in zip(chrono, chrono[1:] + [None]):
        r['minutes_to_next_start'] = None if nxt is None else nxt['minutes_from_first'] - r['minutes_from_first']

    # ---- pairs --------------------------------------------------------------------------
    pair_rows = []
    for a, b_, factor, _ in PAIRS:
        ra, rb = by[a], by[b_]
        d = compare(ra['_embedded_values'], rb['_embedded_values'])
        pair_rows.append(dict(scan_a=a, scan_b=b_, factor=factor, protocol_differences=d['protocol'],
                              scanner_records=d['scanner_records'], summary=summarize(d['protocol']),
                              scanner_summary=summarize(d['scanner_records']) if d['scanner_records'] else 'none'))
    all_keys = sorted(set().union(*(r['_embedded_values'] for r in scans)))
    varying = {k: {r['scan']: r['_embedded_values'].get(k) for r in scans} for k in all_keys
               if any(not stable_equal(scans[0]['_embedded_values'].get(k), r['_embedded_values'].get(k)) for r in scans[1:])}

    # ---- outputs ------------------------------------------------------------------------
    plan_rows = []
    for r in scans:
        for comp_name, res in r['diffs'].items():
            for kind in ('protocol', 'scanner_records', 'reference_only', 'acquired_only'):
                for field, value in res[kind].items():
                    if kind in ('protocol', 'scanner_records'):
                        ref_v, acq_v = value
                    elif kind == 'reference_only':
                        ref_v, acq_v = value, None
                    else:
                        ref_v, acq_v = None, value
                    plan_rows.append(dict(scan=r['scan'], label=r['label'], comparison=comp_name, reference=res['reference'],
                                          field=field, kind=kind, reference_value=ref_v, acquired_value=acq_v))
        if r['cross_day_oct10']:
            res = r['cross_day_oct10']
            for kind in ('protocol', 'scanner_records'):
                for field, (ref_v, acq_v) in res[kind].items():
                    plan_rows.append(dict(scan=r['scan'], label=r['label'], comparison='cross_day_oct10', reference=res['reference'],
                                          field=field, kind=kind, reference_value=ref_v, acquired_value=acq_v))

    scan_columns = ['scan', 'label', 'role', 'folder', 'ppr', 'ppl_path', 'ppl_version', 'method', 'counter_order',
                    'minutes_from_first', 'minutes_to_next_start', 'no_experiments', 'slices', 'slice_z_offsets_mm',
                    'fov_read_offsets_mm', 'fov_phase_offsets_mm', 'raw_views', 'samples', 'imaging_views', 'etl', 'nav_on',
                    'pe_order', 'tr_ms', 'te_ms', 'esp_ms', 'big_delta_ms', 'sm_delta_ms', 'dwell_us', 'bandwidth_khz',
                    'b_values', 'directions_xyz', 'directions', 'crush_amp', 'diff_crush_amp', 'rx_gain', 'tx_gain',
                    'decoupler_gain', 'rfcal', 'gp_init_var', 'fov_read_off_dac', 'fov_phase_off_dac',
                    'folder_ppr_identical_to_console_fixed', 'mrd', 'mrd_sha256', 'nifti_present', 'protocol_notes_present',
                    'json_present', 'diffusion_sidecars_present', 'nonzero_experiment_count', 'mrd_mtime_utc', 'present_files']
    for r in scans:
        r['counter_order'] = r['counter_order']
    csv_write('oct11_protocol_scans.csv', scans, scan_columns)
    csv_write('oct11_protocol_plan_diffs.csv', plan_rows,
              ['scan', 'label', 'comparison', 'reference', 'field', 'kind', 'reference_value', 'acquired_value'])

    json_scans = []
    for r in scans:
        clean = {k: x for k, x in r.items() if not k.startswith('_')}
        clean['_note'] = 'embedded protocol values in _embedded_values'
        clean['embedded_protocol'] = r['_embedded_values']
        clean['folder_ppr_sha256'] = r['_folder_ppr_sha256']
        json_scans.append(clean)
    audit = dict(
        title='October 11, 2026 physical scanner protocol audit',
        method={
            'mrd': 'Embedded PPR text is parsed from the MRD (October 5 parser); dimensions and datatype from the binary header.',
            'comparison': 'Protocol fields are compared after trimming acquisition arrays to each side\'s no_diff_acq and dropping acq_grad (inactive in b-input mode 1). Runtime-only AcquisitionStartTime, PerformanceCounterFrequency and END are excluded. Scanner records (gains, masks, delays) are reported separately.',
            'references': 'adjacent = PPR in the scan folder; planned_console_fixed = experiments/2026-10-11_exvivo_plan_console_fixed; planned_original = experiments/2026-10-11_exvivo_plan; TT and UU use the T and U plans; v1.911-0 uses the 2026-10-10 scan I MRD because it is unplanned.',
            'counter': 'Hardware performance counter (10 MHz), relative chronology only; not a calendar timestamp.',
            'source_identity': 'PPL paths are version labels only; the MRD carries no source-content hash.',
        },
        scans=json_scans,
        chronology=[dict(scan=r['scan'], counter_order=r['counter_order'], minutes_from_first=r['minutes_from_first'],
                         minutes_to_next_start=r['minutes_to_next_start']) for r in chrono],
        controlled_pairs=pair_rows,
        varying_embedded_fields=varying,
        cross_day_oct10={r['scan']: r['cross_day_oct10'] for r in scans if r['cross_day_oct10']},
    )
    (OUT / 'oct11_protocol_audit.json').write_text(json.dumps(audit, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf-8')
    make_catalog(scans, by, chrono, pair_rows)
    print(f'Audited {len(scans)} MRDs; counter order:', ', '.join(f'{r["scan"]} ({r["minutes_from_first"]:.2f})' for r in chrono))
    print('Written:', relative(OUT / 'oct11_protocol_scans.csv'), relative(OUT / 'oct11_protocol_plan_diffs.csv'),
          relative(OUT / 'oct11_protocol_audit.json'), relative(CATALOG))


# ---- catalog ------------------------------------------------------------------------------------

def gain_text(r):
    return f'{fmt(r["rx_gain"])} / {minus(r["tx_gain"])}'


def slices_text(r):
    return f'{r["slices"]} ({", ".join(minus(x) for x in r["slice_z_offsets_mm"])})'


def console_change_text(r):
    if r['scan'] == '0':
        return 'None vs 10-10 scan I protocol (scanner gains differ; see gains)'
    cf = r['diffs']['planned_console_fixed']['protocol']
    orig = r['diffs']['planned_original']['protocol']
    text = summarize(cf) if cf else 'None vs console-compatible PPR'
    extra_keys = {k: v for k, v in orig.items() if k not in cf}
    if extra_keys:
        text += f' (original plan: {summarize(extra_keys)}; workaround in console-compatible copy)'
    if r['scan'] == 'TT':
        text += ' [unplanned; reference T]'
    if r['scan'] == 'UU':
        text += ' [unplanned; reference U]'
    return text


PAIR_NOTES = {
    ('A', 'B'): 'Same b-list and gains (RX 180, TX −129). Only the PPL (1.82 vs 1.912) and ESP (14 vs 13 ms) differ, so the ss-MGOT source change and the ESP change cannot be separated.',
    ('M', 'N'): 'Both were planned as nav2 controls but were acquired as nav1 volume-navigator scans, so this is a v1.82 vs v1.912 single-slice repeat, not a navigator comparison.',
    ('E', 'M'): 'M was planned as the nav2 control for E but was acquired with nav1, so the pair differs only by the volume list (M has no b6000). This is a repeat, not a navigator test.',
    ('E', 'G'): 'Same 40-kHz readout and gains. G is the ESP-12 timing control with a single b10 volume; ESP 11 → 12 ms is the only timing change.',
    ('G', 'I'): 'Bandwidth, ESP and readout gradient change together: 40 kHz at ESP 12 vs 20 kHz at ESP 15, with SMX and gr_var scaled to match. The pair cannot separate bandwidth from ESP.',
    ('Q', 'E'): 'Planned Δ30 / TE44 change: Δ and TE move together by 10 ms, with the same ESP 11, 40-kHz readout and b10/b1000/b6000 list. Diffusion time differs, so ADC is not directly comparable.',
    ('A', 'T'): 'Drift-repeat pair, but RX gain changed from 180 (A) to 0 (T) between the two scans. The gain change confounds any drift measurement; the b10 and b1000 volumes and timing are otherwise matched.',
    ('B', 'U'): 'Drift-repeat pair with the same RX 180 → 0 gain change as A/T; PPL, ESP, Δ and dwell match.',
    ('K', 'O'): 'Different slice geometry and b-list: K has three volumes at ±1.2 mm; O has one volume at ±5 mm. Neither is a clean spacing comparison.',
    ('O', 'S'): 'Clean geometry-only contrast: both have three slices, one b10 volume and the same readout; only the slice separation changes (5 vs 2.4 mm).',
    ('K', 'S'): 'Spacing and b-list differ together: ±1.2 mm with three volumes (K) vs ±2.4 mm with one b10 volume (S). Use O/S for geometry alone.',
    ('T', 'TT'): 'Clean in-plane offset contrast on the same T protocol: read 3.99875 mm and phase −6.0025 mm (FOV_READ_OFF 457, FOV_PHASE_OFF −686 DAC). Unplanned.',
    ('U', 'UU'): 'Not a clean offset contrast: UU also changes TR (5000 ms), TE (34 ms), Δ (20 ms) and the b-list (single b10), in addition to the same in-plane offset.',
    ('S', 'V'): 'Same ±2.4-mm spacing, but V has 256 samples and 256 imaging lines, ten volumes, ESP 14, TE 44, Δ 30, TR 2000, the in-plane offset, and rescaled SMY and gp_init_var for the 256 matrix. Not a controlled comparison; it shows how the final pilot differs from S.',
}


def make_catalog(scans, by, chrono, pair_rows):
    run = read_run_order(PLAN_ORIG)
    cat = []
    n_mrd = len(scans)
    n_vol = sum(r['no_experiments'] for r in scans)
    n_nz = sum(r['nonzero_experiment_count'] for r in scans)
    n_json = sum(1 for r in scans if r['json_present'])
    identical = [r['label'] for r in scans if r['folder_ppr_identical_to_console_fixed']]
    not_identical = [r['label'] for r in scans if not r['folder_ppr_identical_to_console_fixed'] and r['scan'] != '0']
    gap_I, gap_C, gap_V = by['I']['minutes_to_next_start'], by['C']['minutes_to_next_start'], by['V']['minutes_to_next_start']
    v19 = by['B']['v19']
    flips = by['B']['active_flip_degrees']
    chron_order = ', '.join(r['label'] for r in chrono)

    cat += ['# Scanner experiments — October 11, 2026', '',
            f'All {n_mrd} acquisitions were verified using their MRD-embedded PPR, adjacent PPR, reconstructed NIfTI header where one exists, JSON and diffusion sidecars where they exist, and each embedded protocol was diffed against the console-compatible PPR it was run from and against the original plan ([2026-10-11 ex-vivo plan](2026-10-11_exvivo_plan/README.md); [console-compatible copies](2026-10-11_exvivo_plan_console_fixed/README.md)). Scans are named by plan letter and listed in plan order, with the unplanned repeats TT and UU after T and U and the unplanned v1.911-0 last; the chronology table gives actual acquisition-counter order. **Planned scans D, F, H, J, L, P, R, Z, AA and AC were not acquired. AD has a PPR and protocol_notes.json but no MRD. The v182_testUU folder is empty; the acquired UU scan is in v1912_testUU. The guard tests W, X and Y have no acquisition records.** Embedded metadata takes precedence where PPRs differ (here, adjacent PPRs match the embedded protocol exactly for all {n_mrd} scans). A version label identifies the recorded scanner PPL path; it does not prove the source/build used on the scanner. The operator reports that every v1.912 scan and v1.911-0 produced essentially noise; the reconstructions confirm it (navigator echo 1 at 1-12x noise against about 250x for v1.82; see the [10-11 report](../docs/physical_scanner_experiments_2026-10-11.md)).',
            '',
            '**Sample provenance:** The images show the planned sample: a fixed rat brain (coronal sections) held at the bottom of a PBS-filled tube by a three-spoke holder with beads along one spoke. The brain occupies about a quarter of the PBS disk. Fixation history and bore temperature were not supplied. **The centre frequency was about 2.8 kHz off resonance during this session** (bandwidth-dependent readout shift; see the report), and the sample sits about 4 mm from isocentre along the phase-encode axis, so the 128-matrix scans without an in-plane offset wrap the bottom of the tube into the top of the image.',
            '',
            'All scans use centric phase encoding (`PE_order=1`), one average (`NO_AVERAGES=1`), navigator volumes (`nav_on=1`) and ETL 8. Stored TR is 1000 ms except v1.911-0 and V (2000 ms) and UU (5000 ms). Raw views are 136 for the 128-line scans (128 imaging + 8 navigator views) and 264 for V (256 + 8); samples are 128 for the 128-matrix scans and 256 for V. FOV is 35 mm and slices are 1 mm thick. The nominal diffusion duration δ is 4 ms in every scan. Unless stated, TE is 54 ms, ESP is 14 ms and dwell is 50 µs (20 kHz). Crusher plateaus are 1000 / 1000 µs with 200 µs ramps and every schedule is constant (`crusher_schedule=0`, `crusher_step_pct=0`). First diffusion-echo and train crusher values are tabulated below. The planned per-shot navigators (`nav_on=2`) were not acquired; the console-compatible copies were run with `nav_on=1` (see the metadata section). The planned PPRs carry no gain records, so gains are recorded here from the MRDs only.',
            '',
            'Crusher entries are **first diffusion echo / train baseline** in DAC units. ETL means echo train length; navigator views are additional raw lines, not extra imaging lines. Directions are in the scanner logical axes as stored (x = read); b=0 volumes embed a nominal +x vector but carry no diffusion weighting.',
            '',
            '**Protocol identity**',
            '',
            '| Scan / PPR | Role | PPL path / method | Volumes | b-values (s/mm²) | Directions | Raw / imaging views / ETL | First / train crusher (DAC) |',
            '|---|---|---|---:|---|---|---|---|']
    unplanned_role = {
        'TT': 'Unplanned: T with in-plane FOV offset (read +3.99875, phase −6.0025 mm)',
        'UU': 'Unplanned: U with the same in-plane offset, TR 5000, TE 34, Δ 20 ms, single b10',
        '0': 'Unplanned: 10-10 scan I protocol at new gains (RX 180, TX −129)',
    }
    for r in scans:
        link = r['ppr'].removeprefix('experiments/')
        role = unplanned_role.get(r['scan'], r['role'])
        cat.append(f'| [{r["label"]}]({link}) | {role} | {r["ppl_version"]} — {r["method"]} (`{r["ppl_path"]}`) | {r["no_experiments"]} | '
                   f'{", ".join(f"{b:g}" for b in r["b_values"])} | {r["directions"]} | {r["raw_views"]} / {r["imaging_views"]} / {r["etl"]} | '
                   f'{minus(r["diff_crush_amp"])} / {minus(r["crush_amp"])} |')
    cat += ['', '**Timing, geometry, gains and plan agreement**', '',
            '| Scan | ESP (ms) | TE (ms) | TR (ms) | Δ / δ (ms) | Dwell (µs) / bandwidth (kHz) | Slices (z offsets, mm) | RX / TX gain | Adjacent PPR discrepancy | Console-side change vs planned PPR |',
            '|---|---:|---:|---:|---|---|---|---|---|---|']
    for r in scans:
        adj = 'None' if not r['diffs']['adjacent']['protocol'] else 'see audit'
        cat.append(f'| {r["label"]} | {fmt(r["esp_ms"])} | {fmt(r["te_ms"])} | {fmt(r["tr_ms"])} | '
                   f'{fmt(r["big_delta_ms"])} / {fmt(r["sm_delta_ms"])} | {fmt(r["dwell_us"])} / {fmt(r["bandwidth_khz"])} | '
                   f'{slices_text(r)} | {gain_text(r)} | {adj} | {console_change_text(r)} |')
    cat += ['', 'Gains are recorded from the MRDs only. RX gain is 180 for A, B, C and v1.911-0 and 0 for all other scans; TX gain is −129 throughout (−203 on 2026-10-10). Decoupler gain is −453 throughout.', '']
    cat += ['**Chronology and acquisition integrity**', '',
            '| Scan | Counter order | Minutes from first scan | Minutes to next start | Experiments / nonzero raw slots | Reconstructed NIfTI shape | Diffusion sidecars |',
            '|---|---:|---:|---:|---|---|---|']
    for r in scans:
        nxt = '—' if r['minutes_to_next_start'] is None else f'{r["minutes_to_next_start"]:.2f}'
        nifti = '—' if not r['nifti'] else ' × '.join(str(x) for x in r['nifti']['shape_xyzt'])
        sidecar = 'JSON / bval / bvec match embedded protocol' if r['diffusion_sidecars_present'] else (
            'none in folder (protocol_notes.json only)' if r['protocol_notes_present'] else 'none in folder (MRD and PPR only)')
        cat.append(f'| {r["label"]} | {r["counter_order"]} | {r["minutes_from_first"]:.2f} | {nxt} | '
                   f'{r["no_experiments"]} / {r["nonzero_experiment_count"]} | {nifti} | {sidecar} |')
    cat += ['',
            f'Counter times provide relative acquisition order, not clock times. The order is {chron_order}. '
            f'All {n_vol} volumes contain nonzero raw data ({n_nz} nonzero), including every slice block of the three-slice scans K, O, S and V; this is a completeness check, not evidence of good signal.',
            '',
            f'Start-to-start intervals include each acquisition. The RX gain changes once in the session: 180 for A, B, C and v1.911-0 (counters 0.00–12.90 min) and 0 from AB (19.84 min) onward. No PPR records this change, and the gains exist only in the MRDs. The longest intervals are {gap_I:.2f} min between I and M, which no record explains, and {gap_V:.2f} min after V, which matches V\'s planned {float(run["V"]["scan_minutes"]):.2f}-min scan. C\'s {gap_C:.2f}-min interval exceeds its planned {float(run["C"]["scan_minutes"]):.1f}-min scan by {gap_C - float(run["C"]["scan_minutes"]):.1f} min, also unexplained.',
            '']
    cat += ['**Diffusion directions and sign convention**', '',
            'E has b10, b1000 and b6000 volumes, all along +x. M, G, I, K, O, Q, S, T, TT, U, UU and v1.911-0 use +x for every b>0 volume (see the protocol identity table). V adds +y and +z at each of its three shells. AB is one b1000 volume along (577, 577, 577)/1000. Its bvec is normalised to unit length (0.577350 per axis), while the MRD stores the rounded integers (vector norm 0.9993); the bmatrix diagonal (333.3 s/mm²) follows the normalised vector. C has ±x, ±y and ±z at b500 and b1000 with two b10 references; C has no sidecars, so its signs are checked against the MRD arrays only. Every b=0 volume embeds a nominal +x vector (1000, 0, 0) with a zero bvec. The bvec is the embedded direction normalised to unit length with no axis permutation or sign flip, the same convention as 2026-10-10. The logical axes have not been mapped to NIfTI image axes here.',
            '']
    cat += ['**New-method parameters**', '',
            f'B, N, U, UU and v1.911-0 record identical new-method fields: `v19_on={fmt(v19["v19_on"])}`, `v19_cycles={fmt(v19["v19_cycles"])}`, a {fmt(v19["v19_comp_flat"])} µs compensation-lobe plateau, prep slab width {fmt(v19["v19_slab_pml"])} per mille, tip-up width {fmt(v19["v19_tip_pml"])} per mille, spoiler moment {fmt(v19["v19_spoil_cpmm"])} cycles/mm and spoiler amplitude {fmt(v19["v19_spoil_dac"])} DAC. The v1.82 scans do not expose these fields. The active ETL8 flip angles are {", ".join(f"{x:g}°" for x in flips)} (variable flip angle, VFA, on the v1.912 / v1.911 scans). All protocols store `rfcal=594`, `alpha=90` and `p180_scale=185`; the revised branches bypass the legacy `alpha` and `p180_scale` controls, so achieved flip angles remain unverified.',
            '']
    cat += ['**Controlled comparisons and co-changes**', '',
            'The "recorded differences" column is generated from the acquired embedded protocols (acquisition arrays trimmed at `no_diff_acq`, first scan → second scan). Gain differences are listed separately as scanner records.', '',
            '| Comparison | Intended factor | Recorded differences (first → second) | Interpretation / co-changes |', '|---|---|---|---|']
    for pr in pair_rows:
        note = PAIR_NOTES.get((pr['scan_a'], pr['scan_b']), '')
        gains = '' if pr['scanner_summary'] == 'none' else f'; scanner records: {pr["scanner_summary"]}'
        cat.append(f'| {pr["scan_a"]} / {pr["scan_b"]} | {pr["factor"]} | {pr["summary"]}{gains} | {note} |')
    cat += ['', '**Metadata details that affect comparisons**', '',
            f'Adjacent PPRs match the embedded protocol for every scan (scanner records excluded). The folder PPRs of {", ".join(identical)} are byte-identical to the console-compatible copies, and their embedded protocols match those copies. {", ".join(not_identical)} differ from their reference, for the in-plane offsets and the UU reduced protocol described below; v1.911-0 has no console-compatible copy and is compared with the 2026-10-10 scan I MRD.',
            '',
            'The embedded protocols match the console-compatible copies, not the original plan PPRs. The original PPRs for M, N, K, O, Q, S and V use `nav_on=2` (153 raw views, or 297 for V), and K, O, S and V also lack FOV_OFFSETS rows (the original stores only a count). Every one of these seven scans was acquired with `nav_on=1` and the console-compatible raw views. None of them is therefore a per-shot navigator test.',
            '',
            f'**In-plane FOV offsets.** V, TT and UU carry read/phase offsets of 3.99875 / −6.0025 mm, recorded as FOV_READ_OFF {by["V"]["fov_read_off_dac"]:g} and FOV_PHASE_OFF {minus(by["V"]["fov_phase_off_dac"])} DAC on every slice. No planned PPR contains them, and every other scan has zero in-plane offset. For V this is the one console-side geometry change to the final pilot. V\'s gp_init_var is also {minus(by["V"]["gp_init_var"])} against the planned −1941. The records do not explain this one-unit change.',
            '',
            'Scanner gains, gradient/RF/receiver delays and masks (`_pts_mask`, `_pdd_*_mask`, `_use_pdd`, `*Delay`) occur only in the MRD. The gains are discussed above; delays and masks are identical across scans and are not deviations from the plan.',
            '',
            f'Sidecars are missing for C, G, I and Q (no bval, bvec or JSON; NIfTI is also missing for those four). Q also has no protocol_notes.json. B\'s diffusion sidecars use the lowercase `testb` stem. Every one of the {n_json} JSON files reports `BMatrixSource` as `nominal-fallback` with the warning "repo PPL not found" for its PPL version, and `EffectiveBValue` equals the nominal b-values. No effective-b model was applied by that reconstruction, and the `_beff.bval` files repeat the nominal b-values. The model itself resolves the repository PPLs on this machine; per-volume effective b-matrices for all 19 scans are in [oct11_effective_b.csv](../docs/data/oct11_effective_b.csv) (`python docs/data/oct11_effective_b.py`). For v1.82 the b10-to-b1000 trace difference is 986.4 s/mm² along ±x/±y (nominal 990), and the b1000 ±z traces of C are 1038.1 / 963.5.',
            '']
    cat += ['**Cross-day notes (vs October 10)**', '',
            'RX gain is 30 on 2026-10-10 and 180 (A, B, C, v1.911-0) or 0 (all others) on 2026-10-11. TX gain is −203 on 2026-10-10 and −129 on 2026-10-11, and decoupler gain is −453 on both days. Sequence, gain and b-list changes therefore co-vary across days; brightness comparisons across days confound gain changes. The same-letter comparisons below use the 2026-10-10 MRDs (embedded protocol, active fields only).', '']
    for r in scans:
        if r['cross_day_oct10'] and r['scan'] in ('A', 'B', 'C', 'E', 'G', 'I', 'K', '0'):
            prot = summarize(r['cross_day_oct10']['protocol'])
            scan_rec = summarize(r['cross_day_oct10']['scanner_records'])
            prior_name = Path(r['cross_day_oct10']['reference']).parent.name.replace(f'FSE-DWI_{PRIOR_DAY}_', '')
            cat.append(f'- {r["label"]} vs 2026-10-10 {prior_name}: {prot}; scanner records: {scan_rec}.')
    cat += ['',
            'The [complete plan-difference CSV](../docs/data/oct11_protocol_plan_diffs.csv), [scan metadata CSV](../docs/data/oct11_protocol_scans.csv) and [audit JSON](../docs/data/oct11_protocol_audit.json) retain the full differences. Rebuild the catalog and audit with `python docs/data/oct11_protocol_audit.py`.',
            '']
    CATALOG.write_text('\n'.join(cat), encoding='utf-8')


if __name__ == '__main__':
    main()
