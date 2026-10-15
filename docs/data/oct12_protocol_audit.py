"""Audit the October 12 MRDs and regenerate the scan catalog.

Run: python docs/data/oct12_protocol_audit.py
Reads acquisition files without changing them. Uses the October 5 MRD/PPR parser
(oct05_protocol_audit.py) and the shared October 12 loader (oct12_load.py, used here
for cross-checks of dimensions, ETL, thickness, offsets and gains).

Session: ex-vivo rat brain in PBS (volume coil), then in-vivo rat brain (surface coil).
FSE keys A..R are ex vivo, iA..iF are in vivo; the lab EPI scans are epi0 (ex vivo) and
epiA (in vivo). Each acquired embedded FSE protocol is compared with
(a) the adjacent PPR in its own folder and (b) the planned PPR in
experiments/2026-10-12_exvivo_invivo_plan/ (the same letter for ex-vivo scans, a fixed
reference for the unplanned MM, Q1 and QQQ, and the closest in-vivo plan letter U/V/W/X for
iA..iF; the matching nav-1 fallback PPR and the PPR whose letter is in the adjacent file name
are also compared). Scanner records (gains, masks, delays) exist only in the MRDs and are
reported separately from protocol fields. The EPI PPL uses different variable names; its
b-values and directions are decoded from b_steps_array and diff_grad_dir.
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

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from oct05_protocol_audit import parse_mrd, parse_ppr, sha256, stable_equal  # noqa: E402
from oct12_load import SCANS, EPI_SCANS, mrd_path, load  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/data'
EXPS = ROOT / 'experiments'
PLAN = EXPS / '2026-10-12_exvivo_invivo_plan'
NAV2_PPRS = EXPS / '2026-10-12_nav2_pprs'
CATALOG = EXPS / 'scan_catalog_2026-10-12.md'
DAY = '10-12-2026'
PRIOR_DAY = '10-11-2026'

# display order: plan order, unplanned scans after their references, then in vivo; EPI after its session
ORDER = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'M', 'MM', 'N', 'O', 'Q', 'Q1', 'QQ', 'QQQ', 'R', 'epi0',
         'iA', 'iB', 'iC', 'iD', 'iE', 'iF', 'epiA']
LABEL = {k: k for k in ORDER}
LABEL['epi0'] = 'EPI-test0'
LABEL['epiA'] = 'EPI-invivoA'
EPI_KEYS = ['epi0', 'epiA']
INVIVO = ['iA', 'iB', 'iC', 'iD', 'iE', 'iF']
# fixed plan reference for ex-vivo scans; unplanned scans use the nearest planned letter
PLAN_REF = {'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D', 'E': 'E', 'F': 'F', 'G': 'G', 'M': 'M', 'MM': 'M', 'N': 'N', 'O': 'O',
            'Q': 'Q', 'Q1': 'Q', 'QQ': 'QQ', 'QQQ': 'QQ', 'R': 'R'}
UNPLANNED = {'MM', 'Q1', 'QQQ'}
UNPLANNED_ROLE = {
    'MM': 'Unplanned: single b10 slice at z = +2.8 mm (v1.83, nav 1); reference M',
    'Q1': 'Unplanned: Q volume list with seven slices (−5.2, −4.0, −2.8, 0, 2.8, 4.0, 5.2 mm), nav 1; reference Q',
    'QQQ': 'Unplanned: QQ geometry (three slices, b10 only, nav 1) repeat; reference QQ',
}
RUNTIME = {'AcquisitionStartTime', 'PerformanceCounterFrequency', 'END'}
ACQ_ARRAYS = ('acq_b', 'acq_x', 'acq_y', 'acq_z')
GEOMETRY_KEYS = {'NO_SLICES', 'FOV_OFFSETS', 'FOV_SLICE_OFF', 'FOV_READ_OFF', 'FOV_PHASE_OFF',
                 'MULTI_ORIENTATION', 'X_ANGLE', 'Y_ANGLE', 'Z_ANGLE', 'slice_offset', 'gs_var'}
DIFFUSION_KEYS = set(ACQ_ARRAYS) | {'no_diff_acq', 'no_experiments'}
METHOD = {'1.82': 'v1.82', '1.83': 'v1.83', '1.911': 'ss-MGOT revised', '1.912': 'ss-MGOT v1.912'}
# pairs: (first, second, factor)
PAIRS = [
    ('A', 'B', 'Frequency check: 20 kHz (ESP 14) vs 40 kHz (ESP 11), v1.83, b10, one slice'),
    ('D', 'E', 'Phase-mode calibration step 1: mode 0 (vendor) vs mode 1 with phcal 0'),
    ('E', 'F', 'Phase-mode calibration: mode 1, phcal 0 vs +530'),
    ('E', 'G', 'Phase-mode calibration: mode 1, phcal 0 vs −530'),
    ('F', 'G', 'Phase-mode calibration: mode 1, phcal +530 vs −530'),
    ('M', 'N', 'Navigator mode: nav 1 (volume only) vs nav 2 (per shot), v1.83'),
    ('M', 'O', 'v1.83 vs v1.912 at nav 1 and matched volume list (O vs M)'),
    ('Q', 'R', 'v1.83 nav 1 vs v1.912 nav 2, three slices, seven volumes (planned as a nav-2 pair)'),
    ('Q', 'QQ', 'Repeat of the Q geometry: seven volumes vs single b10 volume'),
    ('QQ', 'QQQ', 'Repeat of QQ (three slices, b10)'),
    ('QQQ', 'MM', 'Three slices (−2.8, 0, 2.8 mm) vs single slice at +2.8 mm, b10'),
    ('Q', 'Q1', 'Three vs seven slices with the Q volume list'),
    ('iA', 'iB', 'In vivo: v1.83 (seven slices) vs v1.912 (three slices), same ten-volume list'),
    ('iD', 'iE', 'In vivo TR 3000, b10/b6000 +y: TE 44 / Δ 30 / 1-mm slices vs TE 54 / Δ 40 / 2-mm slices'),
    ('iE', 'iF', 'In vivo: ETL 8 vs 16 at TE 54 / Δ 40 / 2-mm slices'),
]
CROSS_PRIOR_KEYS = ['A', 'B', 'C', 'D', 'E', 'M', 'N', 'O', 'Q', 'R']


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
    if 'no_diff_acq' in v:                               # FSE only; the EPI PPL has no acq_* arrays
        n = int(v['no_diff_acq'])
        for k in ACQ_ARRAYS:
            if isinstance(v.get(k), list):
                v[k] = v[k][:n]
    return v


def is_scanner_record(key: str) -> bool:
    return key.startswith('_') or key.endswith(('Delay', 'Mask'))


def compare(ref_values: dict, acq_values: dict) -> dict:
    """Split differences into protocol fields and scanner records (gains, masks, delays);
    fields present on one side only are listed separately."""
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


def fov_triplets(rec):
    """FOV_OFFSETS record [N, x, y, z, ...] -> list of (x, y, z) per slice (mm)."""
    vals = rec[1:]
    return [tuple(vals[i:i + 3]) for i in range(0, len(vals), 3)]


def slice_z(v) -> list:
    return [t[2] for t in fov_triplets(v['FOV_OFFSETS'])]


def thickness_mm(v):
    return v['gs_var'][-1]


def dwell_us(v):
    return v['sample_period'][3]


def bandwidth_khz(v):
    return v['sample_period'][2]


def slice_geometry(v) -> dict:
    """Nominal edge-to-edge gaps between neighbouring slices (negative = overlap) from FOV_OFFSETS z and
    the slice-thickness record. The PPL positions slices from the FOV_SLICE_OFF DAC table."""
    z = slice_z(v)
    t = thickness_mm(v)
    order = sorted(z)
    pitches = [round(b - a, 6) for a, b in zip(order, order[1:])]
    gaps = [round(p - t, 6) for p in pitches]
    dac = v['FOV_SLICE_OFF'][1:]
    per_mm = sorted({round(abs(d / zz) * t, 3) for d, zz in zip(dac, z) if zz})
    return dict(z_mm=z, thickness_mm=t, pitches_mm=pitches, gaps_mm=gaps, overlap=any(g < -1e-9 for g in gaps),
                overlap_pairs=[[order[i], order[i + 1], gaps[i]] for i in range(len(gaps)) if gaps[i] < -1e-9],
                mean_pitch_mm=(sum(pitches) / len(pitches)) if pitches else None,
                slice_off_dac=dac, slice_off_dac_per_mm_times_thickness=per_mm,
                separation_record_mm=v['slice_offset'][-1])


def gap_text(g):
    if not g['gaps_mm']:
        return f'{fmt(g["thickness_mm"])} / —'
    return f'{fmt(g["thickness_mm"])} / ' + ', '.join(minus(x) for x in g['gaps_mm']) + (' (overlap)' if g['overlap'] else '')


def direction_label(b, x, y, z):
    if b == 0:
        return 'b0'
    comps = [(n, c) for n, c in zip('xyz', (x, y, z)) if c]
    if len(comps) == 1:
        n, c = comps[0]
        return ('+' if c > 0 else '−') + n
    return '(' + ', '.join(f'{minus(c / 1000)}{n}' for n, c in comps) + ')'


def directions_text(v):
    """Per-b description of the stored volume directions, e.g. 'b10 +x; b1000 +x, +y, +z'."""
    n = int(v['no_diff_acq'])
    groups, order = {}, []
    for i in range(n):
        b = v['acq_b'][i]
        if b not in groups:
            groups[b] = []
            order.append(b)
        groups[b].append(direction_label(b, v['acq_x'][i], v['acq_y'][i], v['acq_z'][i]))
    return '; '.join(('b0' if b == 0 else f'b{b:g} ' + ', '.join(groups[b])) for b in order)


def epi_decode(v) -> dict:
    """EPI b-values and directions: one b_steps_array entry and one diff_grad_dir (x, y, z) triplet per b-step."""
    n = int(v['no_b_steps'])
    b = v['b_steps_array'][:n]
    trip = [v['diff_grad_dir'][3 * i:3 * i + 3] for i in range(n)]
    synthetic = dict(no_diff_acq=n, acq_b=b, acq_x=[t[0] for t in trip], acq_y=[t[1] for t in trip], acq_z=[t[2] for t in trip])
    return dict(n=n, b=b, triplets=trip, text=directions_text(synthetic), synthetic=synthetic)


def read_btable(folder: Path):
    p = folder / 'btable.txt'
    if not p.exists():
        return None
    return [[float(x) for x in line.split()] for line in p.read_text().splitlines() if line.strip()]


def version_of(ppl: str):
    m = re.search(r'twoTE-(\d+\.\d+)\.ppl', str(ppl))
    return m.group(1) if m else None


def ppl_label(ppl: str):
    v = version_of(ppl)
    if v:
        return v
    return re.sub(r'\.ppl$', '', str(ppl).split('\\')[-1])


def describe_key(key, a, b):
    if key == 'PPL':
        return f'PPL {ppl_label(a)}→{ppl_label(b)}'
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
    if key == 'VIEWS_PER_SEGMENT':
        return f'views per segment {minus(a)}→{minus(b)}'
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
        if 'NO_SLICES' in d:
            geo.append(f'slices {fmt(d["NO_SLICES"][0])}→{fmt(d["NO_SLICES"][1])}')
        if 'FOV_OFFSETS' in d:
            ref, acq = d['FOV_OFFSETS']
            if isinstance(ref, list) and isinstance(acq, list):
                tr, ta = fov_triplets(ref), fov_triplets(acq)
                if {t[:2] for t in tr} != {t[:2] for t in ta}:
                    geo.append(f'in-plane FOV offset (read, phase) {minus(sorted({t[:2] for t in tr}))}→{minus(sorted({t[:2] for t in ta}))} mm')
                if [t[2] for t in tr] != [t[2] for t in ta]:
                    geo.append(f'z offsets {minus([t[2] for t in tr])}→{minus([t[2] for t in ta])} mm')
            else:
                geo.append('FOV_OFFSETS rows differ')
        if 'gs_var' in d:
            geo.append(f'slice thickness {fmt(d["gs_var"][0][-1])}→{fmt(d["gs_var"][1][-1])} mm (`gs_var` {minus(d["gs_var"][0][0])}→{minus(d["gs_var"][1][0])} DAC)')
        if 'slice_offset' in d:
            a, b = d['slice_offset']
            if a[-1] == b[-1]:
                geo.append(f'SLICE_SEPARATION record DAC {fmt(a[0])}→{fmt(b[0])} ({fmt(a[-1])} mm unchanged)')
            else:
                geo.append(f'SLICE_SEPARATION record {fmt(a[-1])}→{fmt(b[-1])} mm ({fmt(a[0])}→{fmt(b[0])} DAC)')
        if not geo:
            geo.append('slice-geometry DAC records differ (z offsets and thickness unchanged)')
        out.append('; '.join(geo))
        handled |= GEOMETRY_KEYS
    for k in sorted(keys - handled):
        out.append(describe_key(k, *d[k]))
    return '; '.join(out)


READOUT_KEYS = {'sample_period', 'SMX', 'gr_var', 'esp'}
SEGMENT_KEYS = {'nav_on', 'no_views', 'VIEWS_PER_SEGMENT', 'SMY', 'gp_init_var'}


def concept_count(c: dict) -> int:
    """Number of independent changes between two protocols: the diffusion list, slice geometry, readout
    (bandwidth/ESP/gradients), navigator/segment records and phcor each count once; one-sided v19_*/v183_* records count once per family."""
    keys = set(c['protocol'])
    n = sum(1 for g in (DIFFUSION_KEYS, GEOMETRY_KEYS, READOUT_KEYS, SEGMENT_KEYS, {'phcor_plus', 'phcor_minus'}) if keys & g)
    n += len(keys - DIFFUSION_KEYS - GEOMETRY_KEYS - READOUT_KEYS - SEGMENT_KEYS - {'phcor_plus', 'phcor_minus'})
    one = set(c['reference_only']) | set(c['acquired_only'])
    n += int(any(k.startswith('v19_') for k in one)) + int(any(k.startswith('v183_') for k in one))
    n += len([k for k in one if not k.startswith(('v19_', 'v183_'))])
    return n


def sided_text(first_only: dict, second_only: dict, names=('first', 'second')) -> str:
    """Fields present on one side only, grouped by prefix."""
    parts = []
    for side, d in ((names[0], first_only), (names[1], second_only)):
        if not d:
            continue
        groups = {}
        for k in d:
            g = 'v19_*' if k.startswith('v19_') else ('v183_*' if k.startswith('v183_') else k)
            groups.setdefault(g, []).append(k)
        for g, ks in groups.items():
            label = {'v19_*': 'ss-MGOT fields (`v19_*`, ' + str(len(ks)) + ' records)',
                     'v183_*': 'v1.83 fields (' + ', '.join(f'`{k}`' for k in ks) + ')'}.get(g, f'`{g}`')
            parts.append(f'{label} only in {side}')
    return '; '.join(parts)


def scan_folder(key: str) -> Path:
    return EXPS / (SCANS.get(key) or EPI_SCANS[key])


def sidecar(folder: Path, pattern: str, skip=('protocol_notes', '_beff', '_bmatrix', 'shot_nav_phases')):
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


def imaging_views(v, dims):
    """Imaging lines per slice: raw views minus the volume-navigator train; for nav_on=2 the raw views also hold one
    per-shot navigator echo after every imaging shot (VIEWS_PER_SEGMENT = ETL + 1)."""
    vps = int(v['VIEWS_PER_SEGMENT'])
    if int(v['nav_on']) == 2:
        etl = vps - 1
        return (dims['views'] // (etl + 1) - 1) * etl, etl
    return dims['views'] - int(v['nav_on']) * vps, vps


def slice_payload_checks(blob: bytes, parsed):
    d = parsed['dims']
    comp = 8                                           # complex float32 (datatype 0x15)
    S = d['slices']
    slice_bytes = d['samples'] * d['views'] * d['views_2'] * comp
    exp_bytes = slice_bytes * S * d['echoes']
    nz = [[any(blob[512 + e * exp_bytes + s * slice_bytes:512 + e * exp_bytes + (s + 1) * slice_bytes])
           for s in range(S)] for e in range(d['experiments'])]
    complete = parsed['payload_end_offset'] + 120 == parsed['embedded_ppr_offset']
    return nz, complete


def experiment_means(path: Path, parsed):
    """Mean complex magnitude per experiment (used only to align raw and vendor-reconstructed EPI experiments)."""
    d = parsed['dims']
    n = d['experiments'] * d['echoes'] * d['slices'] * d['views_2'] * d['views'] * d['samples']
    arr = np.fromfile(path, dtype='<f4', count=2 * n, offset=512).reshape(d['experiments'], -1, 2)
    return [float(np.hypot(a[:, 0], a[:, 1]).mean()) for a in arr]


SEQUENCE_KEYS = ('te', 'tr', 'esp', 'big_delta', 'sm_delta', 'nav_on', 'VIEWS_PER_SEGMENT', 'no_samples')


def sequence_distance(a, b):
    """Number of differing timing/readout/navigator records plus the dwell and the PPL family (1.8x vs 1.9x);
    the volume list and slice geometry are user choices and are not counted."""
    n = sum(1 for k in SEQUENCE_KEYS if a.get(k) != b.get(k))
    n += int(dwell_us(a) != dwell_us(b))
    n += int(version_of(a['PPL'])[:3] != version_of(b['PPL'])[:3])
    return n


def shared_rows(v):
    """Set of (b, x, y, z) volume rows."""
    n = int(v['no_diff_acq'])
    return {(v['acq_b'][i], v['acq_x'][i], v['acq_y'][i], v['acq_z'][i]) for i in range(n)}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    run = read_run_order(PLAN)
    fallback_of = {}
    for letter, row in run.items():
        m = re.match(r'FALLBACK \(nav 1\) for (\w+):', row['purpose'])
        if m:
            fallback_of[m.group(1)] = letter
    plan_vals = {letter: parse_ppr((PLAN / row['PPR']).read_text(encoding='latin1'))[0] for letter, row in run.items()}
    plan_sha = {letter: sha256(PLAN / row['PPR']) for letter, row in run.items()}

    # ---- inventory of 2026-10-12 acquisition folders ----------------------------------------
    mapped = {SCANS[k] for k in SCANS} | set(EPI_SCANS.values())
    inventory = []
    for p in sorted(EXPS.glob(f'*-DWI_{DAY}_*')):
        if p.is_dir():
            files = sorted(f.name for f in p.iterdir() if f.is_file())
            inventory.append(dict(folder=p.name, mapped=p.name in mapped, n_files=len(files), empty=not files))
    empty_folders = [i['folder'] for i in inventory if i['empty']]
    unmapped_nonempty = [i['folder'] for i in inventory if not i['mapped'] and not i['empty']]
    assert not unmapped_nonempty, unmapped_nonempty

    scans = []
    for key in ORDER:
        folder = scan_folder(key)
        mrd = mrd_path(key)
        parsed = parse_mrd(mrd)
        v = parsed['values']
        is_epi = key in EPI_KEYS
        ppr = sidecar(folder, '*.ppr')
        adj_vals = parse_ppr(ppr.read_text(encoding='latin1'))[0]
        d = parsed['dims']
        S = d['slices']
        blob = mrd.read_bytes()
        nz_slices, payload_complete = slice_payload_checks(blob, parsed)
        mtime = datetime.fromtimestamp(mrd.stat().st_mtime, timezone.utc).isoformat(timespec='seconds')
        files = sorted(p.name for p in folder.iterdir() if p.is_file())
        png_count = sum(1 for f in files if f.lower().endswith('.png'))
        present = [f for f in files if not f.lower().endswith('.png')]
        geo = slice_geometry(v)
        ppl = v['PPL']
        row = dict(scan=key, label=LABEL[key], modality='EPI' if is_epi else 'FSE', folder=relative(folder), ppr=relative(ppr),
                   ppr_name=ppr.name, mrd=relative(mrd), mrd_sha256=parsed['sha256'], mrd_bytes=parsed['byte_size'],
                   ppl_path=ppl, ppl_version=ppl_label(ppl),
                   method=METHOD.get(version_of(ppl)) if not is_epi else 'lab EPI diffusion PPL (epidw_509_SH_MAZ04)',
                   counter=v['AcquisitionStartTime'], counter_frequency=v['PerformanceCounterFrequency'],
                   slices=S, slice_z_offsets_mm=geo['z_mm'], thickness_mm=geo['thickness_mm'], slice_gaps_mm=geo['gaps_mm'],
                   slices_overlap=geo['overlap'], separation_record_mm=geo['separation_record_mm'],
                   slice_off_dac_per_mm_times_thickness=geo['slice_off_dac_per_mm_times_thickness'],
                   fov_read_offsets_mm=[t[0] for t in fov_triplets(v['FOV_OFFSETS'])],
                   fov_phase_offsets_mm=[t[1] for t in fov_triplets(v['FOV_OFFSETS'])],
                   fov_read_off_dac=v['FOV_READ_OFF'][1:], fov_phase_off_dac=v['FOV_PHASE_OFF'][1:],
                   fov_mm=v['FOV'], raw_views=d['views'], samples=d['samples'],
                   tr_ms=v['tr'], te_ms=v['te'], big_delta_ms=v['big_delta'] / 1000, sm_delta_ms=v['sm_delta'] / 1000,
                   dwell_us=dwell_us(v), bandwidth_khz=bandwidth_khz(v),
                   rx_gain=v['_ObserveReceiverGain'], tx_gain=v['_ObserveTransmitGain'], decoupler_gain=v['_DecoupleTransmitGain'],
                   rfcal=v.get('rfcal'), alpha=v.get('alpha'), p180_scale=v.get('p180_scale'),
                   nav_on=int(v['nav_on']), raw_experiments=d['experiments'],
                   nonzero_experiment_slots=parsed['nonzero_experiment_slots'], nonzero_experiment_count=sum(parsed['nonzero_experiment_slots']),
                   all_slice_blocks_nonzero=all(all(x) for x in nz_slices), payload_complete=payload_complete,
                   present_files=present, png_count=png_count, mrd_mtime_utc=mtime,
                   _slice_nonzero=nz_slices, _folder_ppr_sha256=sha256(ppr), _embedded_values={k: x for k, x in v.items() if k not in RUNTIME},
                   _adj_values=adj_vals, _parsed=parsed, _geo=geo, _folder=folder, _ppr=ppr, _mrd=mrd)
        if not is_epi:
            sh = load(key, recon=False)                       # shared loader: independent parse for cross-checks
            n = int(v['no_diff_acq'])
            b = v['acq_b'][:n]
            imaging, etl = imaging_views(v, d)
            assert (sh['E'], sh['S'], sh['V'], sh['nsamp'], sh['N'], sh['L'], sh['nav']) == (d['experiments'], S, d['views'], d['samples'], imaging, etl, row['nav_on']), key
            assert sh['thickness_mm'] == geo['thickness_mm'] and [float(x) for x in sh['offsets_mm']] == [float(x) for x in geo['z_mm']], key
            assert (sh['gains']['rx'], sh['gains']['tx']) == (row['rx_gain'], row['tx_gain']), key
            assert sh['mrd_sha256'] == parsed['sha256'], key
            assert sh['phmode'] == v.get('v183_phmode') and sh['phcal'] == v.get('v183_phcal'), key
            assert int(v['b_input_mode']) == 1 and v['PE_order'] == 1 and v['NO_AVERAGES'] == 1 and v['sm_delta'] == 4000, key
            assert [t[:2] for t in fov_triplets(v['FOV_OFFSETS'])] == [(0.0, 0.0)] * S, key
            assert geo['slice_off_dac_per_mm_times_thickness'] in ([], [400.0]), (key, geo['slice_off_dac_per_mm_times_thickness'])
            dirs = [[v['acq_x'][i] / 1000, v['acq_y'][i] / 1000, v['acq_z'][i] / 1000] for i in range(n)]
            row.update(no_experiments=n, imaging_views=imaging, etl=etl, pe_order=v['PE_order'], esp_ms=v['esp'],
                       b_values=b, directions_xyz=dirs, directions=directions_text(v),
                       crush_amp=v['crush_amp'], diff_crush_amp=v['diff_crush_amp'], crusher_schedule=v['crusher_schedule'],
                       crusher_step_pct=v['crusher_step_pct'], gp_init_var=v['gp_init_var'], SMX=v['SMX'], SMY=v['SMY'], gr_var=v['gr_var'],
                       v183_phmode=v.get('v183_phmode'), v183_phcal=v.get('v183_phcal'),
                       phcor_plus=v['phcor_plus'], phcor_minus=v['phcor_minus'],
                       v19={k: v.get(k) for k in ('v19_on', 'v19_cycles', 'v19_comp_flat', 'v19_slab_pml', 'v19_tip_pml', 'v19_spoil_cpmm', 'v19_spoil_dac')},
                       active_flip_degrees=[x / 10 for x in v.get('v19_flip_tenths', [])[:etl]] if 'v19_flip_tenths' in v else None)
            # ---- sidecars -------------------------------------------------------------------
            json_path = sidecar(folder, '*.json')
            bval_path = sidecar(folder, '*.bval')
            bvec_path = sidecar(folder, '*.bvec')
            beff_path = next(folder.glob('*_beff.bval'), None)
            bmat_path = next(folder.glob('*_bmatrix.txt'), None)
            nii_path = sidecar(folder, '*.nii.gz')
            notes_path = folder / 'protocol_notes.json'
            json_check = j = None
            if json_path:
                j = json.loads(json_path.read_text(encoding='utf-8'))
                exp_spacing = geo['mean_pitch_mm'] if S > 1 else geo['separation_record_mm']
                comparisons = {
                    'PEOrder': (j.get('PEOrder'), v['PE_order']),
                    'BValueInputMode': (j.get('BValueInputMode'), v['b_input_mode']),
                    'DiffusionOn': (j.get('DiffusionOn'), v['diff_on']),
                    'SmallDelta_ms': (j.get('SmallDelta_ms'), v['sm_delta'] / 1000),
                    'BigDelta_ms': (j.get('BigDelta_ms'), v['big_delta'] / 1000),
                    'bval_s_per_mm2': (j.get('bval_s_per_mm2'), b),
                    'SliceOffsets_mm': (j.get('SliceOffsets_mm'), geo['z_mm']),
                    'SliceSpacing_mm (mean z pitch; separation record for one slice)': (j.get('SliceSpacing_mm'), exp_spacing),
                    'NavigatorMode': (j.get('NavigatorMode'), int(v['nav_on'])),
                }
                json_check = {k: dict(json=a, mrd=z, match=stable_equal(a, z)) for k, (a, z) in comparisons.items()}
                assert all(x['match'] for x in json_check.values()), (key, json_check)
            diffusion = None
            if bval_path and bvec_path:
                bside = [float(x) for x in bval_path.read_text().split()]
                vec = [[float(x) for x in line.split()] for line in bvec_path.read_text().splitlines() if line.strip()]
                scaled = {k: v[k][:n] for k in ACQ_ARRAYS[1:]}
                expected_vec = [[0.0] * n for _ in range(3)]
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
                diffusion = dict(bval_path=relative(bval_path), bvec_path=relative(bvec_path), bval_values=bside, bvec_values=vec,
                                 bval_match=stable_equal(bside, b), bvec_match=vec_close, bvec_norms_ok=norms_ok)
                assert diffusion['bval_match'] and vec_close and norms_ok, key
            nifti = None
            if nii_path:
                dims, pixdim = nifti_info(nii_path)
                ndim = dims[0]
                sizes = (dims[1:1 + ndim] + [1, 1, 1, 1])[:4]
                expected = [d['samples'], imaging, S, n]
                nifti = dict(path=relative(nii_path), dims=dims, pixdim=pixdim, shape_xyzt=sizes, expected_xyzt=expected,
                             shape_matches_mrd=sizes == expected)
                assert nifti['shape_matches_mrd'], (key, sizes, expected)
            notes = None
            if notes_path.exists():
                pn = json.loads(notes_path.read_text(encoding='utf-8'))
                notes = dict(letter=pn.get('letter'), version=pn.get('version'), n_rows=len(pn.get('rows', [])), nav_on=pn.get('nav_on'),
                             raw_views=pn.get('raw_views'), slice_offsets_mm=pn.get('slice_offsets_mm'), sample=pn.get('sample'),
                             purpose=pn.get('purpose'),
                             matches_embedded=dict(volumes=len(pn.get('rows', [])) == n, nav_on=pn.get('nav_on') == row['nav_on'],
                                                   raw_views=pn.get('raw_views') == d['views'],
                                                   slice_offsets=[float(x) for x in pn.get('slice_offsets_mm', [])] == [float(x) for x in geo['z_mm']]))
                notes['all_match'] = all(notes['matches_embedded'].values())
            bmatrix_source = j.get('BMatrixSource') if j else None
            row.update(json_present=json_path is not None, bval_present=bval_path is not None, bvec_present=bvec_path is not None,
                       diffusion_sidecars_present=bool(bval_path and bvec_path), nifti_present=nii_path is not None,
                       protocol_notes_present=notes_path.exists(), beff_present=beff_path is not None, bmatrix_txt_present=bmat_path is not None,
                       bmatrix_source=bmatrix_source,
                       bmatrix_warning=([w for w in j.get('BMatrixWarnings', []) if 'unavailable' in w][:1] if j else None),
                       effective_b_equals_nominal=(stable_equal(j.get('EffectiveBValue', []), b) if j else None),
                       json_navigator_mode=j.get('NavigatorMode') if j else None, json_slice_spacing_mm=j.get('SliceSpacing_mm') if j else None,
                       nifti_shape_xyzt=nifti['shape_xyzt'] if nifti else None, nifti_pixdim=nifti['pixdim'][1:5] if nifti else None,
                       json=json_check, diffusion=diffusion, nifti=nifti, protocol_notes=notes,
                       beff_bval_values=[float(x) for x in beff_path.read_text().split()] if beff_path else None,
                       _json_path=relative(json_path) if json_path else None, _json_obj=j)
        else:
            dec = epi_decode(v)
            btable = read_btable(folder)
            o_mrd = folder / (mrd.stem + '_o.MRD')
            o_parsed = parse_mrd(o_mrd)
            o_nii = next(folder.glob('*_o.nii.gz'))
            dims, pixdim = nifti_info(o_nii)
            raw_means = experiment_means(mrd, parsed)
            o_means = experiment_means(o_mrd, o_parsed)
            n = dec['n']
            aligned = d['experiments'] == n + 1 and o_parsed['dims']['experiments'] == n and all(
                abs(o_means[i] - raw_means[i + 1]) / raw_means[i + 1] < 0.05 for i in range(n))
            btable_dirs = [r[1:4] for r in btable] if btable else None
            btable_b = [r[0] for r in btable] if btable else None
            decoded_dirs = [[x / 1000 for x in t] for t in dec['triplets']]
            row.update(no_experiments=n, imaging_views=None, etl=None, pe_order=None, esp_ms=None,
                       b_values=dec['b'], directions_xyz=decoded_dirs, directions=dec['text'],
                       b_steps=dec['b'], diff_grad_dir_triplets=dec['triplets'], no_diff_dir=v['no_diff_dir'],
                       btable_rows=btable, btable_b_matches=(btable_b == dec['b']) if btable else None,
                       btable_dirs_all_100=(all(x == [1.0, 0.0, 0.0] for x in btable_dirs) if btable else None),
                       btable_matches_decoded_dirs=(btable_dirs == decoded_dirs) if btable else None,
                       epi_vendor=dict(o_mrd=relative(o_mrd), o_mrd_dims=o_parsed['dims'], o_nifti=relative(o_nii), o_nifti_dims=dims,
                                       o_nifti_pixdim=pixdim[1:5], raw_experiment_mean_magnitude=raw_means,
                                       o_experiment_mean_magnitude=o_means, o_experiments_align_with_raw_1_to_n=aligned),
                       epi_extras={k: v.get(k) for k in ('chess_on', 'sat_on', 'PB_on', 'nav_on', 'no_navs', 'asymm', 'blip_on', 'psd',
                                                        'sm_delta1', 'sm_delta14', 'no_disaqu', 'p180_scale', 'tref', 'tcrush', 'diff_tcrush', 'diff_tramp')},
                       json_present=False, bval_present=False, bvec_present=False, diffusion_sidecars_present=False,
                       nifti_present=False, protocol_notes_present=False, bmatrix_source=None,
                       nifti_shape_xyzt=dims[1:5], nifti_pixdim=pixdim[1:5], json=None, diffusion=None, nifti=None,
                       protocol_notes=None, v183_phmode=None, v183_phcal=None, v19={},
                       adjacent_ppr_te_ms=adj_vals.get('te'),
                       n_sur_files=sum(1 for f in files if f.lower().endswith('.sur')))
            assert aligned, key
        scans.append(row)

    by = {r['scan']: r for r in scans}
    fse = [r for r in scans if r['modality'] == 'FSE']
    ex = [r for r in fse if r['scan'] not in INVIVO]

    # ---- consistency of the new-method records ---------------------------------------------
    v19_scans = [r['scan'] for r in fse if r['ppl_version'] == '1.912']
    assert len({json.dumps(by[k]['v19'], sort_keys=True) for k in v19_scans}) == 1, v19_scans
    assert len({json.dumps([by[k]['_embedded_values'].get('v19_flip_tenths')], sort_keys=True) for k in v19_scans}) == 1
    assert len({(r['crush_amp'], r['diff_crush_amp'], r['crusher_schedule'], r['crusher_step_pct']) for r in fse}) == 1

    # ---- references: planned PPR comparisons --------------------------------------------------
    def plan_compare(letter, values):
        return dict(reference=relative(PLAN / run[letter]['PPR']), letter=letter, **compare(plan_vals[letter], values))

    closest = {}
    for key in INVIVO:
        r = by[key]
        v = r['_embedded_values']
        version = version_of(v['PPL'])
        cands = [L for L in 'UVWX' if version_of(plan_vals[L]['PPL']) == version]
        ranked = []
        for L in cands:
            c = compare(plan_vals[L], v)
            shared = len(shared_rows(active(plan_vals[L])) & shared_rows(active(v)))
            ranked.append((concept_count(c), len(c['protocol']), -shared, abs(int(plan_vals[L]['no_diff_acq']) - int(v['no_diff_acq'])), L))
        ranked.sort()
        closest[key] = dict(letter=ranked[0][4], changes={L: n for n, _, _, _, L in ranked}, fields_differing={L: f for _, f, _, _, L in ranked},
                            shared_rows={L: -s for _, _, s, _, L in ranked})
    for key in ORDER:
        r = by[key]
        v = r['_embedded_values']
        refs = {}
        r['adjacent_diff'] = dict(reference=relative(r['_ppr']), **compare(r['_adj_values'], v))
        if r['modality'] == 'EPI':
            r['plan_letter'] = None
            r['planned_reference'] = None
            r['diffs'] = {'adjacent': r['adjacent_diff']}
            r['role'] = None
            continue
        if key in INVIVO:
            letter = closest[key]['letter']
            r['closest_plan'] = letter
        else:
            letter = PLAN_REF[key]
        r['plan_letter'] = letter
        r['planned_reference'] = relative(PLAN / run[letter]['PPR'])
        refs['adjacent'] = r['adjacent_diff']
        refs['planned'] = plan_compare(letter, v)
        fb = fallback_of.get(letter)
        if fb and fb in plan_vals and fb != letter:
            refs['planned_nav1_fallback'] = plan_compare(fb, v)
        if key in INVIVO:
            m = re.search(r'test([A-Z]+)\.ppr$', r['ppr_name'])
            if m and m.group(1) in plan_vals and m.group(1) not in (letter, fb):
                refs['plan_named_in_adjacent_file'] = plan_compare(m.group(1), v)
        r['diffs'] = refs
        r['folder_ppr_identical_to_plan'] = (r['_folder_ppr_sha256'] == plan_sha[letter])
        if key in UNPLANNED:
            r['role'] = UNPLANNED_ROLE[key]
        elif key in INVIVO:
            pv = r['_embedded_values']
            vols = int(pv['no_diff_acq'])
            r['role'] = (f'Not in plan: in vivo (surface coil), {vols} volumes, {r["slices"]} slice{"s" if r["slices"] > 1 else ""}; '
                         f'closest plan {letter}')
        else:
            r['role'] = run[letter]['purpose']

    # ---- chronology (FSE and EPI share one hardware counter) ---------------------------------
    assert len({r['counter_frequency'] for r in scans}) == 1
    anchor = min(r['counter'] for r in scans)
    chrono = sorted(scans, key=lambda r: r['counter'])
    for rank, r in enumerate(chrono, 1):
        r['counter_order'] = rank
        r['minutes_from_first'] = (r['counter'] - anchor) / r['counter_frequency'] / 60
    for r, nxt in zip(chrono, chrono[1:] + [None]):
        r['minutes_to_next_start'] = None if nxt is None else nxt['minutes_from_first'] - r['minutes_from_first']
    for r in scans:
        pl = r.get('plan_letter')
        r['planned_scan_minutes'] = float(run[pl]['scan_minutes']) if (pl and r['scan'] not in UNPLANNED and r['scan'] not in INVIVO and r['modality'] == 'FSE') else None

    # ---- planned scans not acquired -----------------------------------------------------------
    acquired_letters = {PLAN_REF[k] for k in ORDER if k in PLAN_REF and k not in UNPLANNED}
    not_acquired = [dict(letter=L, version=run[L]['version'], part=run[L]['part'], purpose=run[L]['purpose'],
                         scan_minutes=float(run[L]['scan_minutes']), nav_fallback_for=next((a for a, b in fallback_of.items() if b == L), None))
                    for L in run if L not in acquired_letters]

    # ---- extra PPRs in 2026-10-12_nav2_pprs ---------------------------------------------------
    nav2_extra = []
    for f in sorted(NAV2_PPRS.iterdir()):
        ppr = next(f.glob('*.ppr'))
        sv = parse_ppr(ppr.read_text(encoding='latin1'))[0]
        nav2_extra.append(dict(folder=f.name, ppr=relative(ppr), ppl_version=ppl_label(sv['PPL']), nav_on=int(sv['nav_on']),
                               raw_views=int(sv['no_views']), volumes=int(sv['no_diff_acq']), b_values=sv['acq_b'][:int(sv['no_diff_acq'])],
                               te_ms=sv['te'], tr_ms=sv['tr'], big_delta_ms=sv['big_delta'] / 1000, esp_ms=sv['esp'],
                               matches_an_acquired_embedded_protocol=any(
                                   not compare(sv, by[k]['_embedded_values'])['protocol'] for k in by if by[k]['modality'] == 'FSE')))

    # ---- pairs ---------------------------------------------------------------------------------
    pair_rows = []
    for a, b_, factor in PAIRS:
        ra, rb = by[a], by[b_]
        c = compare(ra['_embedded_values'], rb['_embedded_values'])
        pair_rows.append(dict(scan_a=a, scan_b=b_, factor=factor, protocol_differences=c['protocol'], scanner_records=c['scanner_records'],
                              first_only=c['reference_only'], second_only=c['acquired_only'],
                              summary=summarize(c['protocol']), sided=sided_text(c['reference_only'], c['acquired_only'], (a, b_)),
                              scanner_summary=summarize(c['scanner_records']) if c['scanner_records'] else 'none',
                              minutes_apart=by[b_]['minutes_from_first'] - by[a]['minutes_from_first']))

    # ---- attribute comparison for FSE vs EPI ---------------------------------------------------
    def attrs(r):
        v = r['_embedded_values']
        return {
            'PPL': ppl_label(v['PPL']),
            'volumes': r['no_experiments'], 'b-values': '/'.join(fmt(x) for x in r['b_values']), 'directions': r['directions'],
            'TE (ms)': v['te'], 'TR (ms)': v['tr'], 'Δ (ms)': v['big_delta'] / 1000, 'δ (ms)': v['sm_delta'] / 1000,
            'slices': r['slices'], 'z offsets (mm)': minus(r['slice_z_offsets_mm']), 'thickness (mm)': r['thickness_mm'],
            'FOV (mm)': r['fov_mm'], 'in-plane offset (mm)': '0, 0' if not any(r['fov_read_offsets_mm']) and not any(r['fov_phase_offsets_mm']) else 'nonzero',
            'raw views × samples': f'{r["raw_views"]} × {r["samples"]}', 'dwell (µs)': r['dwell_us'],
            'nav_on': r['nav_on'], 'RX / TX gain': f'{fmt(r["rx_gain"])} / {minus(r["tx_gain"])}',
        }

    epi_pairs = []
    for a, b_, factor in (('iA', 'epiA', 'In vivo: FSE iA vs lab EPI invivoA (same ten b-values and x/y/z directions)'),
                          ('Q', 'epi0', 'Ex vivo: FSE Q vs lab EPI test0')):
        aa, bb = attrs(by[a]), attrs(by[b_])
        diffs = {k: [aa[k], bb[k]] for k in aa if aa[k] != bb[k]}
        same = [k for k in aa if aa[k] == bb[k]]
        epi_pairs.append(dict(scan_a=a, scan_b=b_, factor=factor, attribute_differences=diffs, attributes_equal=same,
                              minutes_apart=by[b_]['minutes_from_first'] - by[a]['minutes_from_first']))

    # ---- cross-day: closest 2026-10-11 scan ----------------------------------------------------
    prior = {}
    for p in sorted(EXPS.glob(f'FSE-DWI_{PRIOR_DAY}_*')):
        m = next(p.glob('*.MRD'), None)
        if m:
            prior[p.name.replace(f'FSE-DWI_{PRIOR_DAY}_', '')] = parse_mrd(m)['values']
    prior_gains = sorted({(x['_ObserveReceiverGain'], x['_ObserveTransmitGain'], x['_DecoupleTransmitGain']) for x in prior.values()})
    cross = {}
    for key in CROSS_PRIOR_KEYS:
        v = by[key]['_embedded_values']
        ranked = []
        for name, pv in prior.items():
            if pv['no_samples'] != v['no_samples']:               # different matrix: not a protocol analogue
                continue
            c = compare(pv, v)
            ranked.append((sequence_distance(pv, v), -len(shared_rows(active(pv)) & shared_rows(active(v))), len(c['protocol']), name))
        ranked.sort()
        n0, _, f0, name = ranked[0]
        c = compare(prior[name], v)
        cross[key] = dict(reference=name, sequence_distance=n0, n_protocol_fields_differ=f0, protocol=c['protocol'],
                          scanner_records=c['scanner_records'], reference_only=c['reference_only'], acquired_only=c['acquired_only'],
                          runner_up=ranked[1][3], runner_up_sequence_distance=ranked[1][0])

    # ---- varying fields ------------------------------------------------------------------------
    all_keys = sorted(set().union(*(r['_embedded_values'] for r in fse)))
    base = fse[0]['_embedded_values']
    varying = {k: {r['scan']: r['_embedded_values'].get(k) for r in fse} for k in all_keys
               if any(not stable_equal(base.get(k), r['_embedded_values'].get(k)) for r in fse[1:])}

    # ---- outputs ---------------------------------------------------------------------------------
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

    scan_columns = ['scan', 'label', 'modality', 'role', 'folder', 'ppr', 'ppr_name', 'ppl_path', 'ppl_version', 'method',
                    'plan_letter', 'planned_reference', 'folder_ppr_identical_to_plan', 'counter_order', 'minutes_from_first',
                    'minutes_to_next_start', 'planned_scan_minutes', 'no_experiments', 'raw_experiments', 'b_values', 'directions_xyz',
                    'directions', 'nav_on', 'raw_views', 'samples', 'imaging_views', 'etl', 'pe_order', 'tr_ms', 'te_ms', 'esp_ms',
                    'big_delta_ms', 'sm_delta_ms', 'dwell_us', 'bandwidth_khz', 'slices', 'slice_z_offsets_mm', 'thickness_mm',
                    'slice_gaps_mm', 'slices_overlap', 'separation_record_mm', 'fov_mm', 'fov_read_offsets_mm', 'fov_phase_offsets_mm',
                    'rx_gain', 'tx_gain', 'decoupler_gain', 'v183_phmode', 'v183_phcal', 'rfcal', 'alpha', 'p180_scale', 'SMX', 'SMY',
                    'gr_var', 'gp_init_var', 'phcor_plus', 'phcor_minus', 'crush_amp', 'diff_crush_amp', 'v19', 'mrd', 'mrd_sha256',
                    'mrd_bytes', 'nonzero_experiment_count', 'all_slice_blocks_nonzero', 'payload_complete', 'json_present', 'bval_present',
                    'bvec_present', 'diffusion_sidecars_present', 'nifti_present', 'nifti_shape_xyzt', 'nifti_pixdim', 'bmatrix_source',
                    'effective_b_equals_nominal', 'protocol_notes_present', 'btable_dirs_all_100', 'btable_matches_decoded_dirs',
                    'png_count', 'mrd_mtime_utc', 'present_files']
    for r in scans:
        r.setdefault('folder_ppr_identical_to_plan', None)
        r.setdefault('role', None)
    csv_write('oct12_protocol_scans.csv', scans, scan_columns)
    csv_write('oct12_protocol_plan_diffs.csv', plan_rows,
              ['scan', 'label', 'comparison', 'reference', 'field', 'kind', 'reference_value', 'acquired_value'])

    json_scans = []
    for r in scans:
        clean = {k: x for k, x in r.items() if not k.startswith('_') and k != 'diffs'}
        clean['diffs'] = r['diffs']
        clean['embedded_protocol'] = active(r['_embedded_values']) if r['modality'] == 'FSE' else r['_embedded_values']
        clean['folder_ppr_sha256'] = r['_folder_ppr_sha256']
        clean['slice_geometry'] = {k: x for k, x in r['_geo'].items()}
        json_scans.append(clean)
    audit = dict(
        title='October 12, 2026 physical scanner protocol audit',
        method={
            'mrd': 'Embedded PPR text is parsed from the MRD (October 5 parser); dimensions and datatype from the binary header. FSE dimensions, ETL, thickness, offsets, gains and phase-mode records are cross-checked against oct12_load.load().',
            'comparison': 'Protocol fields are compared after trimming acquisition arrays to each side\'s no_diff_acq and dropping acq_grad (inactive in b-input mode 1). Runtime-only AcquisitionStartTime, PerformanceCounterFrequency and END are excluded. Scanner records (gains, masks, delays) are reported separately; the planned PPRs carry none, so they appear as reference=null.',
            'references': 'adjacent = PPR in the scan folder; planned = experiments/2026-10-12_exvivo_invivo_plan PPR of the same letter (MM uses M, Q1 uses Q, QQQ uses QQ); in-vivo scans use the closest plan letter U/V/W/X of the same PPL (fewest differing protocol fields, ties by shared (b, direction) rows then by volume count); planned_nav1_fallback = the doubled-letter fallback PPR; plan_named_in_adjacent_file = the plan PPR whose letter appears in the in-vivo folder PPR file name.',
            'epi': 'EPI b-values and directions decoded from b_steps_array and diff_grad_dir (one x, y, z triplet per b-step, thousandths); btable.txt is compared separately. The raw EPI MRD has no_b_steps+1 experiments; the vendor _o.MRD holds no_b_steps experiments that align with raw experiments 1..n by mean magnitude.',
            'slice_geometry': 'Edge-to-edge gap = z pitch of neighbouring FOV_OFFSETS minus slice thickness (gs_var, mm); negative = nominal overlap. The PPL positions slices from the FOV_SLICE_OFF DAC table, not from the SLICE_SEPARATION record; DAC per mm x thickness is 400 for every FSE slice.',
            'counter': 'Hardware performance counter (10 MHz), relative chronology only; not a calendar timestamp. FSE and EPI MRDs share one counter frequency and are placed on one timeline.',
            'source_identity': 'PPL paths are version labels only; the MRD carries no source-content hash.',
        },
        scans=json_scans,
        chronology=[dict(scan=r['scan'], counter_order=r['counter_order'], minutes_from_first=r['minutes_from_first'],
                         minutes_to_next_start=r['minutes_to_next_start'], planned_scan_minutes=r['planned_scan_minutes']) for r in chrono],
        controlled_pairs=pair_rows,
        fse_vs_epi=epi_pairs,
        closest_invivo_plan=closest,
        planned_not_acquired=not_acquired,
        acquired_unplanned=[r['scan'] for r in scans if r['scan'] in UNPLANNED or r['scan'] in INVIVO or r['modality'] == 'EPI'],
        empty_folders=empty_folders,
        folder_inventory=inventory,
        extra_nav2_pprs=nav2_extra,
        varying_embedded_fields=varying,
        cross_prior_day={k: dict(v) for k, v in cross.items()},
        prior_day_gains=[dict(rx=a, tx=b, decoupler=c) for a, b, c in prior_gains],
    )
    (OUT / 'oct12_protocol_audit.json').write_text(json.dumps(audit, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf-8')
    ctx = dict(run=run, by=by, scans=scans, fse=fse, ex=ex, chrono=chrono, pair_rows=pair_rows, epi_pairs=epi_pairs, closest=closest,
               not_acquired=not_acquired, empty_folders=empty_folders, nav2_extra=nav2_extra, cross=cross, prior_gains=prior_gains,
               fallback_of=fallback_of, v19_scans=v19_scans, plan_vals=plan_vals)
    make_catalog(ctx)
    print(f'Audited {len(scans)} MRDs; counter order:', ', '.join(f'{r["label"]} ({r["minutes_from_first"]:.2f})' for r in chrono))
    print('Written:', relative(OUT / 'oct12_protocol_scans.csv'), relative(OUT / 'oct12_protocol_plan_diffs.csv'),
          relative(OUT / 'oct12_protocol_audit.json'), relative(CATALOG))


# ---- catalog ------------------------------------------------------------------------------------

def gain_text(r):
    return f'{fmt(r["rx_gain"])} / {minus(r["tx_gain"])}'


def slices_text(r):
    return f'{r["slices"]} ({", ".join(minus(x) for x in r["slice_z_offsets_mm"])})'


def modal_exceptions(rows, getter, show=fmt):
    """Most common value and the scans that differ from it."""
    vals = {}
    for r in rows:
        vals.setdefault(json.dumps(getter(r)), []).append(r['label'])
    modal = max(vals.items(), key=lambda kv: len(kv[1]))
    exc = [(json.loads(k), labels) for k, labels in vals.items() if k != modal[0]]
    return json.loads(modal[0]), exc


def exc_text(name, rows, getter, unit='', show=fmt):
    modal, exc = modal_exceptions(rows, getter)
    text = f'{name} {show(modal)}{unit}'
    if exc:
        text += ' except ' + '; '.join(f'{", ".join(labels)} ({show(val)}{unit})' for val, labels in exc)
    return text


def spec_changes(r):
    """Console-side changes vs the planned reference (protocol fields only)."""
    if r['modality'] == 'EPI':
        d = r['diffs']['adjacent']['protocol']
        return 'None (PPR = embedded)' if not d else 'embedded protocol differs from adjacent PPR: ' + summarize(d)
    pl = r['diffs']['planned']['protocol']
    return 'None vs planned PPR' if not pl else summarize(pl)


def pair_notes(by, pair_rows, epi_pairs):
    """Interpretation text for each controlled comparison; the factual claims are asserted against the parsed protocols."""
    dt = {(p['scan_a'], p['scan_b']): p['minutes_apart'] for p in pair_rows + epi_pairs}
    g = lambda k: f'RX {fmt(by[k]["rx_gain"])} / TX {minus(by[k]["tx_gain"])}'
    same_gain = lambda a, b: (by[a]['rx_gain'], by[a]['tx_gain']) == (by[b]['rx_gain'], by[b]['tx_gain'])
    assert same_gain('A', 'B') and same_gain('D', 'E') and same_gain('E', 'F') and same_gain('F', 'G') and same_gain('M', 'N')
    assert same_gain('M', 'O') and same_gain('QQ', 'QQQ') and same_gain('QQQ', 'MM') and same_gain('iA', 'iB') and same_gain('iD', 'iE')
    assert same_gain('iE', 'iF') and same_gain('iA', 'epiA') and by['Q']['rx_gain'] == 120 and by['R']['rx_gain'] == 0
    assert by['Q']['tx_gain'] == by['R']['tx_gain'] == by['epi0']['tx_gain'] == -128
    assert abs(by['N']['SMY'] / by['M']['SMY'] - 153 / 136) < 1e-4 and abs(by['R']['SMY'] / by['Q']['SMY'] - 153 / 136) < 1e-4
    assert abs(by['iF']['SMY'] / by['iE']['SMY'] - 144 / 136) < 1e-4
    assert by['epiA']['_embedded_values']['chess_on'] == 1 and by['iA']['_embedded_values']['chess_on'] == 0
    span = by['G']['minutes_from_first'] - by['D']['minutes_from_first']
    between_qr = [r['label'] for r in by.values() if by['Q']['minutes_from_first'] < r['minutes_from_first'] < by['R']['minutes_from_first']]
    between_qe = [r['label'] for r in by.values() if by['Q']['minutes_from_first'] < r['minutes_from_first'] < by['epi0']['minutes_from_first']]
    return {
        ('A', 'B'): f'Bandwidth, ESP and the readout-gradient scale (`SMX`, `gr_var`) change together, so 20 vs 40 kHz cannot be separated from ESP 14 vs 11 ms. TE 44, Δ 30, TR 2000, nav 1, b10 +x, geometry and gains ({g("A")}) are identical. Acquired {dt[("A", "B")]:.1f} min apart.',
        ('D', 'E'): f'Only the phase-mode record differs (0 = vendor / v1.81 scheme, 1 = v1.82 gated scheme, here with phcal 0). Geometry (±1.2 mm, 1-mm slices), b10 +x, timing, nav 1 and gains ({g("D")}) are identical. D, E, F and G were acquired within {span:.1f} min.',
        ('E', 'F'): 'Only `v183_phcal` differs (0 → +530, in the 0.1 µs ticks of the calibration note), in mode 1.',
        ('E', 'G'): 'Only `v183_phcal` differs (0 → −530), in mode 1.',
        ('F', 'G'): 'Symmetric ±530 pair; only `v183_phcal` differs.',
        ('M', 'N'): f'Navigator mode is the intended factor. It comes with the longer segment (`VIEWS_PER_SEGMENT` 8→9, raw views 136→153) and console-rescaled `SMY` and `gp_init_var` (×1.125 = 153/136). PPL, b-list (b10 and b1000 +x; b3000 and b6000 +z), geometry, timing and gains ({g("M")}) are identical. Acquired {dt[("M", "N")]:.1f} min apart.',
        ('M', 'O'): f'Same volume list, nav 1, geometry, timing and gains ({g("M")}); only the PPL and its method-specific records differ (v1.83 phase-mode records vs v1.912 ss-MGOT records). O is the planned v1.912 counterpart of M, acquired {dt[("M", "O")]:.1f} min after it.',
        ('Q', 'R'): f'Not a clean v1.83 vs v1.912 contrast. R is nav 2 (raw views 153, `VIEWS_PER_SEGMENT` 9, `SMY` and `gp_init_var` ×1.125) but Q was acquired nav 1, so PPL and navigator mode change together, and the RX gain also changes from 120 to 0 between the scans ({dt[("Q", "R")]:.1f} min apart; {", ".join(between_qr)} were acquired in between). Volume list, geometry (±2.8 mm), timing and TX gain (−128) are identical. Signal-level and ghosting differences between Q and R therefore confound PPL, navigator mode and RX gain.',
        ('Q', 'QQ'): f'QQ repeats the Q geometry with a single b10 volume. The volume list, `phcor_plus`/`phcor_minus` (23→29) and RX gain (120→0) differ. QQ is the planned nav-1 fallback of Q, which was planned with seven volumes and acquired with one. {dt[("Q", "QQ")]:.1f} min apart.',
        ('QQ', 'QQQ'): f'Repeat of the same three slices with b10 only and RX 0. QQQ returns `phcor` to 23 and its `SLICE_SEPARATION` record reads 1.2 mm, but the z-offset table (−2.8, 0, 2.8 mm; `FOV_SLICE_OFF` ±1120 DAC) is identical, so the slice positions are the same. {dt[("QQ", "QQQ")]:.1f} min apart.',
        ('QQQ', 'MM'): f'Clean geometry-only contrast: same b10 volume, nav 1, timing, RX 0 and `phcor` 23. QQQ acquires three slices (−2.8, 0, +2.8 mm), MM only the +2.8-mm slice. MM was acquired {abs(dt[("QQQ", "MM")]):.1f} min before QQQ.',
        ('Q', 'Q1'): f'Same volume list and nav 1 with seven 1-mm slices (nominal gaps 0.2 mm at the outer pairs, 1.8 mm across the centre) instead of three. The RX gain also differs (120→0), and Q1 was acquired {dt[("Q", "Q1")]:.1f} min after Q. The JSON/NIfTI z spacing (1.733 mm) is the mean of uneven offsets.',
        ('iA', 'iB'): f'Same ten-volume list, TE/TR/ESP/Δ, nav 1, 1-mm slices and gains ({g("iA")}). The PPL changes together with the slice set: iA has seven slices (−5.2 … +5.2 mm, uneven) and iB three (−2.8, 0, +2.8 mm), and iA carries the v1.83 phase-mode records (mode 0, phcal 0) that v1.912 lacks. {dt[("iA", "iB")]:.1f} min apart.',
        ('iD', 'iE'): f'Δ and TE rise together by 10 ms and the slice thickness doubles (`gs_var` and the `FOV_SLICE_OFF` DAC values halve; z offsets unchanged); TR 3000, b10/b6000 +y, nav 1, ETL 8 and gains ({g("iD")}) are the same. Diffusion time, TE and slice thickness co-change, and the 2-mm slices overlap nominally by 0.8 mm at the 1.2-mm spacing. {dt[("iD", "iE")]:.1f} min apart.',
        ('iE', 'iF'): f'Only the echo-train length changes, 8→16 (`VIEWS_PER_SEGMENT` 8→16, raw views 136→144 = 128 + 16 navigator views), with console-rescaled `SMY` and `gp_init_var` (×1.059 = 144/136). TE 54, ESP 11, TR 3000, Δ 40, the overlapping 2-mm slices and gains are identical. {dt[("iE", "iF")]:.1f} min apart.',
        ('iA', 'epiA'): f'Different PPLs and readouts, so the differences are structural. Matched: Δ 30 ms, δ 4 ms, TE 44 ms, FOV 35 mm, no in-plane offset, the b1000/b3000/b6000 shells with x/y/z directions, and the gains ({g("iA")}). Not matched: EPI starts with b0 where FSE has b10; TR 3000 vs 2000 ms; three 2-mm slices at ±2.2 mm vs seven 1-mm slices (only the centre slice coincides); EPI readout (5-µs dwell, 16 views × 1344 samples, vendor image 256 × 128) vs FSE 128 × 128; and the EPI protocol has `chess_on=1` (FSE 0). EPI invivoA was acquired {abs(dt[("iA", "epiA")]):.1f} min before iA.',
        ('Q', 'epi0'): f'Different PPLs. EPI test0 has b0, b1000 +y and b6000 +z; Q has b10 and b1000/b3000 along x, y, z, so only the b1000 +y volume has a counterpart (Q has no b6000). Matched: Δ 30 ms, δ 4 ms, FOV, no in-plane offset, TX gain −128. Not matched: RX gain 120 vs 0; TE 44 vs 42 ms (the EPI embedded TE; its adjacent PPR says 32 ms); TR 2000 vs 3000 ms; EPI 2-mm slices at ±2.2 mm vs Q 1-mm slices at ±2.8 mm; readout. {dt[("Q", "epi0")]:.1f} min apart; {", ".join(between_qe)} were acquired in between.',
    }


def make_catalog(ctx):
    run, by, scans, fse, ex, chrono, pair_rows = ctx['run'], ctx['by'], ctx['scans'], ctx['fse'], ctx['ex'], ctx['chrono'], ctx['pair_rows']
    closest, not_acq = ctx['closest'], ctx['not_acquired']
    n_all, n_fse = len(scans), len(fse)
    n_vol = sum(r['no_experiments'] for r in fse)
    cat = []
    na_letters = [x['letter'] for x in not_acq]
    na_main = [x for x in na_letters if len(set(x)) == 1 and len(x) == 1]
    na_fb = [x for x in na_letters if len(x) == 2]
    adj_clean = [r['label'] for r in scans if not r['diffs']['adjacent']['protocol']]
    adj_diff = [r['label'] for r in scans if r['diffs']['adjacent']['protocol']]
    unplanned_list = ', '.join(r['label'] for r in scans if r['scan'] in UNPLANNED or r['scan'] in INVIVO or r['modality'] == 'EPI')
    renamed = [f'{k} (`{by[k]["ppr_name"].replace("FSE-DWI_10-12-2026_", "").replace(".ppr", "")}`)' for k in INVIVO
               if re.search(r'test[A-Z]+\.ppr$', by[k]['ppr_name'])]
    cat += ['# Scanner experiments — October 12, 2026', '',
            f'All {n_all} acquisitions ({n_fse} FSE and 2 lab EPI) were verified using their MRD-embedded PPR, adjacent PPR, reconstructed NIfTI header where one exists, and JSON and diffusion sidecars where they exist. Each FSE embedded protocol was diffed against the planned PPR it was run from ([2026-10-12 plan](2026-10-12_exvivo_invivo_plan/README.md); [run order](2026-10-12_exvivo_invivo_plan/run_order.csv)); the in-vivo scans were not planned as run and are compared with the closest plan letter. Scans are listed in plan order with the unplanned MM, Q1 and QQQ after their references, then EPI test0, the in-vivo scans iA–iF (folders `invivoA`…`invivoF`) and EPI invivoA; the chronology table gives actual acquisition-counter order. '
            f'**Planned scans {", ".join(na_main)} and the navigator-1 fallbacks {", ".join(na_fb)} were not acquired.** QQ is the only fallback acquired. Unplanned acquisitions: {unplanned_list}. The `v183_testO` folder is empty; the acquired O is in `v1912_testO`. N has an MRD, PPR and protocol_notes.json but no reconstruction. '
            f'Embedded metadata takes precedence where PPRs differ. The folder PPRs of {", ".join(renamed)} carry plan-letter names but their content matches the embedded in-vivo protocol, not those plans; the adjacent PPR matches the embedded protocol for {len(adj_clean)} of {n_all} scans (differences: {", ".join(adj_diff) if adj_diff else "none"}). A version label identifies the recorded scanner PPL path; it does not prove the source or build used on the scanner.',
            '',
            '**Sample provenance:** A–R and EPI test0 are a fixed rat brain in a PBS-filled tube with the volume coil; iA–iF and EPI invivoA are in-vivo rat brain with the surface coil (as stated for the session; fixation history, animal details, anaesthesia, temperature and shim were not supplied). The MRD does not record the centre frequency (`:OBSERVE_FREQUENCY` holds a 0.0 placeholder), and the outcome of the A/B frequency check is not part of this audit.',
            '']
    z7 = [-5.2, -4.0, -2.8, 0.0, 2.8, 4.0, 5.2]
    shared = [
        'All FSE scans use centric phase encoding (`PE_order=1`), one average, 35-mm FOV, 128 samples and 128 imaging lines, b-input mode 1, δ 4 ms, zero in-plane FOV offsets, and the same crusher settings (first-echo / train amplitude '
        f'{minus(fse[0]["diff_crush_amp"])} / {minus(fse[0]["crush_amp"])} DAC, constant schedule). ',
        exc_text('Otherwise TE', fse, lambda r: r['te_ms'], ' ms') + '; ' + exc_text('ESP', fse, lambda r: r['esp_ms'], ' ms') + '; ' +
        exc_text('TR', fse, lambda r: r['tr_ms'], ' ms') + '; ' + exc_text('Δ', fse, lambda r: r['big_delta_ms'], ' ms') + '; ' +
        exc_text('dwell', fse, lambda r: r['dwell_us'], ' µs') + '; ' + exc_text('slice thickness', fse, lambda r: r['thickness_mm'], ' mm') + '; ' +
        exc_text('nav_on', fse, lambda r: r['nav_on']) + '; ' + exc_text('ETL', fse, lambda r: r['etl']) + '. ',
        'ETL means echo train length; navigator views are additional raw lines, not extra imaging lines. For `nav_on=2` the stored `VIEWS_PER_SEGMENT` is 9 (8 echoes plus the per-shot navigator echo) and the 153 raw views are one navigator segment plus 16 shots of 8 imaging lines each followed by one navigator echo. ',
        'Directions are in the scanner logical axes as stored (x = read, y = phase, z = slice). The planned PPRs carry no gain records, so gains come from the MRDs only.',
    ]
    cat += [''.join(shared[:2]) + shared[2] + shared[3], '']
    cat += ['**Protocol identity**', '',
            '| Scan / PPR | Role | PPL path / method | Volumes | b-values (s/mm²) | Directions | nav_on | Raw / imaging views / ETL |',
            '|---|---|---|---:|---|---|---:|---|']
    for r in scans:
        link = r['ppr'].removeprefix('experiments/')
        if r['modality'] == 'EPI':
            role = ('Lab EPI, ex vivo (volume coil): b0, b1000, b6000' if r['scan'] == 'epi0'
                    else 'Lab EPI, in vivo (surface coil): b0 and b1000/3000/6000 along x, y, z')
            cat.append(f'| [{r["label"]}]({link}) | {role} | {r["ppl_version"]} (`{r["ppl_path"]}`) | {r["no_experiments"]} (raw MRD {r["raw_experiments"]}) | '
                       f'{", ".join(f"{b:g}" for b in r["b_values"])} | {r["directions"]} | {r["nav_on"]} | {r["raw_views"]} views × {r["samples"]} samples (EPI) |')
            continue
        cat.append(f'| [{r["label"]}]({link}) | {r["role"]} | {r["ppl_version"]} — {r["method"]} (`{r["ppl_path"]}`) | {r["no_experiments"]} | '
                   f'{", ".join(f"{b:g}" for b in r["b_values"])} | {r["directions"]} | {r["nav_on"]} | {r["raw_views"]} / {r["imaging_views"]} / {r["etl"]} |')
    cat += ['', '**Timing, geometry, gains and plan agreement**', '',
            'Thickness / gap gives the slice thickness and the nominal edge-to-edge gap between neighbouring slices from the z-offset table (negative = overlap). The slice-profile tails are not modelled here. The PPL positions slices from `FOV_SLICE_OFF`, not from the `SLICE_SEPARATION` record, which is shown for scans where the two disagree.', '',
            '| Scan | ESP (ms) | TE (ms) | TR (ms) | Δ / δ (ms) | Dwell (µs) / bandwidth (kHz) | Slices (z offsets, mm) | Thickness (mm) / gaps (mm) | RX / TX gain | Adjacent PPR vs embedded | Console-side change vs planned PPR |',
            '|---|---:|---:|---:|---|---|---|---|---|---|---|']
    for r in scans:
        adj = 'None' if not r['diffs']['adjacent']['protocol'] else summarize(r['diffs']['adjacent']['protocol'])
        if r['modality'] == 'EPI':
            te_note = fmt(r['te_ms'])
            if r['adjacent_diff']['protocol'].get('te'):
                a, b = r['adjacent_diff']['protocol']['te']
                te_note = f'{fmt(b)} (adjacent PPR {fmt(a)})'
            cat.append(f'| {r["label"]} | — | {te_note} | {fmt(r["tr_ms"])} | {fmt(r["big_delta_ms"])} / {fmt(r["sm_delta_ms"])} | {fmt(r["dwell_us"])} / {fmt(r["bandwidth_khz"])} | '
                       f'{slices_text(r)} | {gap_text(r["_geo"])} | {gain_text(r)} | {adj} | no plan PPR (lab EPI) |')
            continue
        cat.append(f'| {r["label"]} | {fmt(r["esp_ms"])} | {fmt(r["te_ms"])} | {fmt(r["tr_ms"])} | '
                   f'{fmt(r["big_delta_ms"])} / {fmt(r["sm_delta_ms"])} | {fmt(r["dwell_us"])} / {fmt(r["bandwidth_khz"])} | '
                   f'{slices_text(r)} | {gap_text(r["_geo"])} | {gain_text(r)} | {adj} | '
                   f'{(spec_changes(r) + (" [reference " + r["plan_letter"] + "]" if r["scan"] in UNPLANNED else "")) if r["scan"] not in INVIVO else "closest plan " + r["plan_letter"] + ": " + str(len(r["diffs"]["planned"]["protocol"])) + " fields differ (list below)"} |')
    # gains prose
    exv = [r for r in scans if r['scan'] not in INVIVO and r['scan'] != 'epiA']
    rx120 = [r['label'] for r in scans if r['rx_gain'] == 120]
    rx0 = [r['label'] for r in scans if r['rx_gain'] == 0]
    rx180 = [r['label'] for r in scans if r['rx_gain'] == 180]
    tx128 = [r['label'] for r in scans if r['tx_gain'] == -128]
    tx197 = [r['label'] for r in scans if r['tx_gain'] == -197]
    assert len(rx120) + len(rx0) + len(rx180) == len(scans) and len(tx128) + len(tx197) == len(scans)
    assert all(r['decoupler_gain'] == -453 for r in scans)
    qq_t = by['Q']['minutes_from_first'], by['QQ']['minutes_from_first']
    cat += ['',
            f'Gains are recorded from the MRDs only. RX gain is 120 for {", ".join(rx120)}; 0 for {", ".join(rx0)}; and 180 for {", ".join(rx180)}. TX gain is −128 for the ex-vivo scans ({len(tx128)} scans) and −197 for the in-vivo scans ({", ".join(tx197)}). Decoupler gain is −453 throughout. The RX gain therefore changes twice: 120 → 0 between Q ({qq_t[0]:.2f} min) and QQ ({qq_t[1]:.2f} min), inside the ex-vivo series, and 0 → 180 (with TX −128 → −197) between EPI test0 and EPI invivoA. No PPR records either change. The plan asks for the RX gain to be fixed for the whole session.', '']
    cat += ['**Chronology and acquisition integrity**', '',
            '| Scan | Counter order | Minutes from first scan | Minutes to next start | Planned min | Experiments / nonzero raw slots | Reconstructed NIfTI shape | Sidecars (JSON / bval / bvec; b-matrix source) |',
            '|---|---:|---:|---:|---:|---|---|---|']
    for r in scans:
        nxt = '—' if r['minutes_to_next_start'] is None else f'{r["minutes_to_next_start"]:.2f}'
        pm = '—' if r['planned_scan_minutes'] is None else f'{r["planned_scan_minutes"]:.1f}'
        if r['modality'] == 'EPI':
            ev = r['epi_vendor']
            shape = ' × '.join(str(x) for x in r['nifti_shape_xyzt'])
            cat.append(f'| {r["label"]} | {r["counter_order"]} | {r["minutes_from_first"]:.2f} | {nxt} | {pm} | raw {r["raw_experiments"]} / {r["nonzero_experiment_count"]}; vendor `_o.MRD` {ev["o_mrd_dims"]["experiments"]} | '
                       f'{shape} (vendor `_o.nii.gz`) | none (no JSON, bval or bvec; vendor `btable.txt` only) |')
            continue
        shape = '—' if not r['nifti'] else ' × '.join(str(x) for x in r['nifti_shape_xyzt'])
        if r['diffusion_sidecars_present']:
            sc = f'JSON / bval / bvec match embedded protocol; `BMatrixSource` {r["bmatrix_source"]}'
        elif r['protocol_notes_present']:
            sc = 'none in folder (protocol_notes.json only)'
        else:
            sc = 'none in folder'
        cat.append(f'| {r["label"]} | {r["counter_order"]} | {r["minutes_from_first"]:.2f} | {nxt} | {pm} | '
                   f'{r["no_experiments"]} / {r["nonzero_experiment_count"]} | {shape} | {sc} |')
    n_nz = sum(r['nonzero_experiment_count'] for r in fse)
    assert all(r['all_slice_blocks_nonzero'] and r['payload_complete'] and r['nonzero_experiment_count'] == r['raw_experiments'] for r in scans)
    gaps = sorted(((r['minutes_to_next_start'], r['label']) for r in chrono if r['minutes_to_next_start'] is not None), reverse=True)[:4]
    cat += ['',
            f'Counter times provide relative acquisition order, not clock times; the FSE and EPI MRDs share one counter frequency (10 MHz). The order is {", ".join(r["label"] for r in chrono)}. '
            f'All {n_vol} FSE volumes contain nonzero raw data ({n_nz} nonzero), including every slice block of the multi-slice scans, and all EPI raw experiments are nonzero; this is a completeness check, not evidence of good signal. Every MRD payload ends where the embedded PPR begins.',
            '',
            'Start-to-start intervals include each acquisition. The longest intervals are ' + ', '.join(f'{g:.2f} min after {lab}' for g, lab in gaps) + '. '
            f'Q is followed by QQ after {by["Q"]["minutes_to_next_start"]:.2f} min (Q planned {by["Q"]["planned_scan_minutes"]:.1f} min); the interval after EPI test0 spans the ex-vivo to in-vivo change in coil gains. No record explains these intervals. '
            f'The planned verification scans H, I, J, K and L (phase mode at ±2.8 and ±5 mm) were not acquired; G is followed directly by M.', '']
    # directions
    cat += ['**Diffusion directions and sign convention**', '']
    ep0, epa = by['epi0'], by['epiA']
    assert ep0['btable_dirs_all_100'] and epa['btable_dirs_all_100'] and ep0['btable_b_matches'] and epa['btable_b_matches']
    n_bt0 = sum(1 for t in ep0['directions_xyz'] if t != [1.0, 0.0, 0.0])
    n_bta = sum(1 for t in epa['directions_xyz'] if t != [1.0, 0.0, 0.0])
    groups = {}
    for r in fse:
        groups.setdefault(r['directions'], []).append(r['label'])
    assert all(r['diffusion'] is None or (r['diffusion']['bval_match'] and r['diffusion']['bvec_match']) for r in fse)
    sidecar_scans = [r['label'] for r in fse if r['diffusion']]
    assert not any(b == 0 for r in fse for b in r['b_values'])
    cat.append(
        'Stored FSE directions by scan: ' + '; '.join(f'**{desc}**: {", ".join(labels)}' for desc, labels in groups.items()) + '. '
        'No FSE scan has a b=0 volume; the b10 volumes embed a nominal direction like the others. '
        f'For the {len(sidecar_scans)} scans with sidecars, the bval equals the embedded b-list and the bvec is the embedded direction normalised to unit length with no axis permutation or sign flip, as on 2026-10-10 and 2026-10-11. The logical axes have not been mapped to NIfTI image axes here.')
    cat.append('')
    cat.append(
        f'**EPI directions.** The EPI PPR uses `b_steps_array` and `diff_grad_dir` (one x, y, z triplet in thousandths per b-step, `no_diff_dir=1`). EPI test0 has {ep0["no_experiments"]} b-steps, b {", ".join(f"{b:g}" for b in ep0["b_values"])}, with triplets {"; ".join("(" + ", ".join(fmt(x) for x in t) + ")" for t in ep0["diff_grad_dir_triplets"])}, i.e. {ep0["directions"]}. '
        f'EPI invivoA has {epa["no_experiments"]} b-steps (b0; b1000, b3000 and b6000 each along +x, +y, +z): {epa["directions"]}. '
        f'**The vendor `btable.txt` in both folders lists every row, including b0, as direction (1, 0, 0)** (the b-values agree), which disagrees with the decoded `diff_grad_dir` in {n_bt0} of {ep0["no_experiments"]} rows for test0 (b1000 and b6000) and {n_bta} of {epa["no_experiments"]} rows for invivoA (the y and z rows). The embedded `diff_grad_dir` is used here; no EPI JSON, bval or bvec exists. '
        f'The raw EPI MRD holds {ep0["raw_experiments"]} (test0) and {epa["raw_experiments"]} (invivoA) experiments, one more than the b-steps; the vendor `_o.MRD` and `_o.nii.gz` hold {ep0["no_experiments"]} and {epa["no_experiments"]} volumes that align with raw experiments 1..n by mean magnitude (raw experiment 0 is not a b-step volume).')
    cat.append('')
    # new-method
    v19 = by[ctx['v19_scans'][0]]['v19']
    flips = by[ctx['v19_scans'][0]]['active_flip_degrees']
    ph = [(r['label'], r['v183_phmode'], r['v183_phcal']) for r in fse if r['v183_phmode'] is not None]
    mode1 = [(l, m, c) for l, m, c in ph if m == 1]
    mode0 = [l for l, m, c in ph if m == 0]
    assert all(c == 0 for l, m, c in ph if m == 0)
    assert all(r['alpha'] == 90 and r['rfcal'] == 594 for r in fse)
    p180 = sorted({r['p180_scale'] for r in fse})
    cat += ['**New-method parameters**', '',
            f'**v1.912 ss-MGOT.** {", ".join(by[k]["label"] for k in ctx["v19_scans"])} record identical new-method fields: `v19_on={fmt(v19["v19_on"])}`, `v19_cycles={fmt(v19["v19_cycles"])}`, a {fmt(v19["v19_comp_flat"])} µs compensation-lobe plateau, prep slab width {fmt(v19["v19_slab_pml"])} per mille, tip-up width {fmt(v19["v19_tip_pml"])} per mille, spoiler moment {fmt(v19["v19_spoil_cpmm"])} cycles/mm and spoiler amplitude {fmt(v19["v19_spoil_dac"])} DAC. The active ETL-8 flip angles are {", ".join(f"{x:g}°" for x in flips)} (variable flip angle). The v1.83 scans do not expose these fields. '
            f'All FSE protocols store `rfcal=594` and `alpha=90`; `p180_scale` is {", ".join(str(int(x)) for x in p180)}. The revised branches bypass the legacy `alpha` and `p180_scale` controls, so achieved flip angles remain unverified. The v1.912 scans (C, O, R, iB, iC) have no off-centre phase parameter.',
            '',
            f'**v1.83 off-centre RF phase (`v183_phmode`, `v183_phcal`).** Mode 0 / phcal 0 in {", ".join(mode0)}. Mode 1: ' +
            '; '.join(f'{l} phcal {minus(f"{c:+g}") if c else "0"}' for l, m, c in mode1) +
            '. Every v1.83 scan after the D–G series is saved with mode 0 and phcal 0, as the plan prescribed for "all later v1.83 files" before the calibration was evaluated; no scan uses a calibrated value. The v1.912 PPLs do not carry these fields.', '']
    # controlled comparisons
    PAIR_NOTES = pair_notes(by, pair_rows, ctx['epi_pairs'])
    cat += ['**Controlled comparisons and co-changes**', '',
            'The "recorded differences" column is generated from the acquired embedded protocols (acquisition arrays trimmed at `no_diff_acq`, first scan → second scan). Gain differences are listed separately as scanner records; fields present in only one PPL are listed under them.', '',
            '| Comparison | Intended factor | Recorded differences (first → second) | Interpretation / co-changes |', '|---|---|---|---|']
    for pr in pair_rows:
        note = PAIR_NOTES.get((pr['scan_a'], pr['scan_b']), '')
        extra = ''
        if pr['sided']:
            extra += f'; {pr["sided"]}'
        if pr['scanner_summary'] != 'none':
            extra += f'; scanner records: {pr["scanner_summary"]}'
        diffs = pr['summary'] if pr['summary'] != 'none' else 'none'
        cat.append(f'| {pr["scan_a"]} / {pr["scan_b"]} | {pr["factor"]} | {diffs}{extra} | {note} |')
    for ep in ctx['epi_pairs']:
        a, b_ = ep['scan_a'], ep['scan_b']
        diffs = '; '.join(f'{k} {fmt(x)}→{fmt(y)}' if not isinstance(x, str) and not isinstance(y, str) else f'{k} ({x}) → ({y})'
                          for k, (x, y) in ep['attribute_differences'].items())
        cat.append(f'| {by[a]["label"]} / {by[b_]["label"]} | {ep["factor"]} | {diffs}; equal: {", ".join(ep["attributes_equal"])} | {PAIR_NOTES.get((a, b_), "")} |')
    cat += ['', '**Metadata details that affect comparisons**', '']
    # plan agreement
    exact = [r['label'] for r in scans if r['modality'] == 'FSE' and r['scan'] not in UNPLANNED and r['scan'] not in INVIVO and not r['diffs']['planned']['protocol']]
    differ = [r['label'] for r in scans if r['modality'] == 'FSE' and r['scan'] not in UNPLANNED and r['scan'] not in INVIVO and r['diffs']['planned']['protocol']]
    ident = [r['label'] for r in scans if r.get('folder_ppr_identical_to_plan')]
    cat.append(
        f'Embedded protocols of {", ".join(exact)} match their planned PPRs exactly (scanner records excluded). {", ".join(differ)} differ from plan: '
        + '; '.join(f'{by[k]["label"]}: {summarize(by[k]["diffs"]["planned"]["protocol"])}' for k in ORDER if by[k]['label'] in differ) + '. '
        f'Folder PPRs byte-identical to the planned PPR: {", ".join(ident) if ident else "none"}.')
    cat.append('')
    q = by['Q']
    assert not q['diffs']['planned_nav1_fallback']['protocol'] and q['diffs']['planned_nav1_fallback']['letter'] == 'QQ'
    cat.append(
        f'**Navigator mode.** The plan stored Q (and R, N) with `nav_on=2` (153 raw views). N and R were acquired as planned in navigator mode 2. Q was acquired with `nav_on=1` and 136 raw views: its embedded protocol equals the planned QQ (nav-1 fallback) PPR with no differing field, though the Q folder PPR is not byte-identical to that file. M and O are nav 1 as planned. '
        f'In N and R the embedded `SMY` and `gp_init_var` are ×1.125 the planned values ({fmt(by["N"]["_adj_values"]["SMY"])}→{fmt(by["N"]["SMY"])}, {minus(by["N"]["_adj_values"]["gp_init_var"])}→{minus(by["N"]["gp_init_var"])}; 1.125 = 153/136), so the embedded N and R protocols also differ from their folder PPRs; the same rescaling is present in iF ({minus(by["iE"]["gp_init_var"])}→{minus(by["iF"]["gp_init_var"])}, ×{by["iF"]["gp_init_var"] / by["iE"]["gp_init_var"]:.3f} = 144/136).')
    cat.append('')
    qq, qqq, mm = by['QQ'], by['QQQ'], by['MM']
    cat.append(
        f'**Console-side changes inside the Q family.** QQ was planned with seven volumes and was acquired with one (b10) and `phcor_plus`/`phcor_minus` {fmt(by["Q"]["phcor_plus"])}→{fmt(qq["phcor_plus"])}; QQQ has the same slices and a single b10 volume but `phcor` {fmt(qqq["phcor_plus"])}, and its `SLICE_SEPARATION` record is {fmt(qqq["separation_record_mm"])} mm ({fmt(qqq["_embedded_values"]["slice_offset"][0])} DAC) while its z-offset table is −2.8, 0, 2.8 mm (`FOV_SLICE_OFF` ±1120 DAC, identical to QQ). The PPL positions slices from `FOV_SLICE_OFF`, so the acquired positions follow the table; the JSON `SliceSpacing_mm` (2.8) also follows the table. MM is a single slice at +2.8 mm. Q1 has seven slices at −5.2, −4.0, −2.8, 0, 2.8, 4.0, 5.2 mm, 1 mm thick.')
    cat.append('')
    overl = [r for r in scans if r['slices_overlap']]
    assert [r['scan'] for r in overl] == ['iE', 'iF'] and all(by[k]['thickness_mm'] == 1 for k in ('Q1', 'iA', 'iD')) and all(by[k]['thickness_mm'] == 2 for k in ('iE', 'iF'))
    assert all(by[k]['slice_z_offsets_mm'] == z7 for k in ('Q1', 'iA', 'iD', 'iE', 'iF'))
    cat.append(
        f'**Slice geometry.** The seven-slice protocols (Q1, iA, iD, iE, iF) use z offsets {", ".join(minus(x) for x in z7)} mm, whose centre spacing is 1.2 mm at the outer pairs (−5.2/−4.0/−2.8 and 2.8/4.0/5.2) and 2.8 mm across the centre; their `SLICE_SEPARATION` record is 1.2 mm and the recon JSON/NIfTI report the mean spacing 1.733 mm because an affine cannot represent the uneven positions. '
        f'Q1, iA and iD have 1-mm slices (nominal gaps 0.2, 0.2, 1.8, 1.8, 0.2, 0.2 mm). **iE and iF have 2-mm slices, so neighbouring slices at 1.2-mm spacing nominally overlap by 0.8 mm (−5.2/−4.0, −4.0/−2.8, 2.8/4.0, 4.0/5.2) and leave a 0.8-mm gap across the centre.** ' +
        (f'Scans with nominal overlap: {", ".join(r["label"] for r in overl)}. ' if overl else '') +
        'D, E, F and G (±1.2 mm, 1-mm slices) have 0.2-mm nominal gaps; EPI slices are 2 mm thick at ±2.2 mm (0.2-mm gap). No scan applies an in-plane FOV offset (all `FOV_READ_OFF` and `FOV_PHASE_OFF` values are zero), including the in-vivo scans.')
    cat.append('')
    # in-vivo mapping
    cat.append('**In-vivo scans vs plan.** The in-vivo scans were edited on the console; the embedded MRD protocol is authoritative. The closest plan letter is the PPR of the same PPL with the fewest independent changes (ties: fewer differing fields, then more shared b/direction rows, then closer volume count). Differences from that plan PPR follow; the nav-1 fallback letter and, where the folder PPR carries a plan-letter name, that named plan are given as field counts (details in the plan-difference CSV).')
    cat.append('')
    for k in INVIVO:
        r = by[k]
        L = closest[k]['letter']
        fb = r['diffs'].get('planned_nav1_fallback')
        nm = r['diffs'].get('plan_named_in_adjacent_file')
        extra = []
        if fb:
            extra.append(f'nav-1 fallback {fb["letter"]}: {len(fb["protocol"])} fields')
        if nm:
            extra.append(f'plan {nm["letter"]} named in the folder PPR file name: {len(nm["protocol"])} fields')
        cat.append(f'- {k} → {L} ({closest[k]["fields_differing"][L]} fields differ{"; " + "; ".join(extra) if extra else ""}): {summarize(r["diffs"]["planned"]["protocol"])}.')
    notes_stale = [(r['label'], r['protocol_notes']) for r in fse if r['protocol_notes'] and not r['protocol_notes']['all_match']]
    cat.append('')
    ibn = by['iB']['protocol_notes']
    assert ibn and ibn['letter'] == 'V' and ibn['nav_on'] == 2 and ibn['raw_views'] == 153 and ibn['n_rows'] == 4
    assert all(by[k]['protocol_notes'] is None for k in INVIVO if k != 'iB')
    stale_txt = '; '.join(f'{lab}: ' + ', '.join(k.replace("_", " ") for k, ok in pn['matches_embedded'].items() if not ok) for lab, pn in notes_stale)
    cat.append(
        'Only iB has a `protocol_notes.json` among the in-vivo folders, and it is the plan V notes (letter V, 4 volumes, `nav_on=2`, 153 raw views, three slices); the embedded iB protocol has 10 volumes, `nav_on=1` and 136 raw views. '
        f'The notes disagree with the embedded protocol in: {stale_txt if stale_txt else "nothing"} (Q\'s notes are the plan Q notes, planned nav 2).')
    cat.append('')
    ex_ = ctx['nav2_extra']
    cat.append(
        f'[`2026-10-12_nav2_pprs`](2026-10-12_nav2_pprs) holds {len(ex_)} extra PPRs ({", ".join(e["folder"].replace("FSE-DWI_10-12-2026_", "") for e in ex_)}): each has {ex_[0]["volumes"]} volumes (b {"/".join(fmt(x) for x in ex_[0]["b_values"])}), TE {fmt(ex_[0]["te_ms"])} ms, Δ {fmt(ex_[0]["big_delta_ms"])} ms and TR {fmt(ex_[0]["tr_ms"])} ms; '
        + ('none of them matches an acquired embedded protocol.' if not any(e['matches_an_acquired_embedded_protocol'] for e in ex_) else 'some match an acquired protocol.'))
    cat.append('')
    cat.append('Scanner gains, gradient/RF/receiver delays and masks (`_pts_mask`, `_pdd_*_mask`, `_use_pdd`, `*Delay`) occur only in the MRD. Delays and masks are identical across scans (no deviation from plan); the gains are discussed above.')
    cat.append('')
    nosc = [r['label'] for r in fse if not r['diffusion_sidecars_present']]
    nonii = [r['label'] for r in fse if not r['nifti_present']]
    n_json = sum(1 for r in fse if r['json_present'])
    srcs = {r['bmatrix_source'] for r in fse if r['json_present']}
    assert srcs == {'nominal-fallback'} and all(r['effective_b_equals_nominal'] for r in fse if r['json_present'])
    nav_json = by['R']['_json_obj']
    cat.append(
        f'Sidecars: {n_json} of {n_fse} FSE scans have JSON, bval and bvec; {", ".join(nosc)} {"has" if len(nosc) == 1 else "have"} none (NIfTI missing for {", ".join(nonii)}). Every one of the {n_json} JSON files reports `BMatrixSource` as `nominal-fallback` with the warning "repo PPL not found" for its PPL version (1.83 or 1.912), `BMatrixCalibrationApplied` false, and `EffectiveBValue` equal to the nominal b-values; the `_beff.bval` files repeat the nominal b-values. No effective-b model was applied by that reconstruction.' + (' Source-model per-volume effective b-matrices for these scans are in [oct12_effective_b.csv](../docs/data/oct12_effective_b.csv) (`python docs/data/oct12_effective_b.py`). ' if (OUT / 'oct12_effective_b.csv').exists() else ' ') + ''
        f'The JSON `NavigatorMode` equals the embedded `nav_on` in every file; R\'s JSON also carries a per-shot navigator list ({len(nav_json["PerShotNavigator"])} entries, one per volume and slice) and the folder holds `shot_nav_phases` .json and .npy files. The JSON does not record slice thickness. The EPI folders have no JSON, bval, bvec or recon NIfTI beyond the vendor `_o.nii.gz` ({" and ".join(" × ".join(str(x) for x in by[k]["nifti_shape_xyzt"]) for k in EPI_KEYS)}, voxel {", ".join(f"{x:.4g}" for x in by["epi0"]["nifti_pixdim"][:3])} mm) and 9 vendor `.SUR` files in the test0 folder.')
    cat.append('')
    e0 = by['epi0']
    cat.append(
        f'The EPI test0 adjacent PPR stores TE {fmt(e0["adjacent_ppr_te_ms"])} ms while the embedded protocol has TE {fmt(e0["te_ms"])} ms (the embedded MRD protocol is used); all other protocol fields match. The EPI invivoA folder PPR is named `EPI-DWI_10-12-2026_test0.ppr` and matches the embedded invivoA protocol (10 b-steps, TE {fmt(by["epiA"]["te_ms"])} ms). Both EPI protocols use PPL `{e0["ppl_path"]}` ({e0["dwell_us"]:g}-µs dwell, {e0["bandwidth_khz"]:g} kHz; {e0["raw_views"]} raw views × {e0["samples"]} samples per slice; vendor image 256 × 128), 3 slices at ±2.2 mm and 2-mm thickness, `chess_on=1`, `sat_on=1` with all `PB_on` flags 0, `nav_on=1`.')
    cat.append('')
    # cross-day
    pg = ctx['prior_gains']
    cat += ['**Cross-day notes (vs October 11)**', '',
            f'On 2026-10-11 the RX gain was {" or ".join(sorted({fmt(a) for a, _, _ in pg}, key=float))}, TX gain {", ".join(sorted({minus(b) for _, b, _ in pg}))} and decoupler gain {", ".join(sorted({minus(c) for _, _, c in pg}))}. On 2026-10-12 TX is −128 ex vivo and −197 in vivo, and RX is 120 or 0 ex vivo and 180 in vivo. The v1.83 PPL is new on 10-12; the 10-11 FSE scans used v1.82 and v1.912 (the [10-11 catalog](scan_catalog_2026-10-11.md) reports essentially noise for its v1.912 and v1.911 scans). Sequence, gain and b-list changes co-vary across days, so brightness comparisons across days confound gain changes. For each ex-vivo scan, the closest 2026-10-11 MRD with the same matrix is listed, ranked by sequence distance (number of differing TE, TR, ESP, Δ, δ, dwell, navigator and segment records plus a PPL-family change; ties by shared b/direction rows; embedded protocol, active fields only):', '']
    for key, c in ctx['cross'].items():
        prot = summarize(c['protocol'])
        sc = summarize(c['scanner_records'])
        sided = sided_text(c['reference_only'], c['acquired_only'], ('10-11', '10-12'))
        cat.append(f'- {by[key]["label"]} vs 2026-10-11 {c["reference"]} (sequence distance {c["sequence_distance"]}; {c["n_protocol_fields_differ"]} fields differ): {prot}'
                   f'{"; " + sided if sided else ""}; scanner records: {sc}.')
    cat += ['',
            'The [complete plan-difference CSV](../docs/data/oct12_protocol_plan_diffs.csv), [scan metadata CSV](../docs/data/oct12_protocol_scans.csv) and [audit JSON](../docs/data/oct12_protocol_audit.json) retain the full differences. Rebuild the catalog and audit with `python docs/data/oct12_protocol_audit.py`.',
            '']
    CATALOG.write_text('\n'.join(cat), encoding='utf-8')


if __name__ == '__main__':
    main()
