"""Audit all October 7 MRDs and regenerate the scan catalog (standard library only).

Run: python docs/data/oct07_protocol_audit.py
Reads acquisition files without changing them. Uses the October 5 parser and
compares every embedded field/record, retaining inactive arrays separately.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import itertools
import json
import re
import struct
from datetime import datetime, timezone
from pathlib import Path

from oct05_protocol_audit import parse_mrd, parse_ppr, sha256, stable_equal

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/data'
ORDER = ['test0', 'test1', 'test1b', 'test2', 'test2b', 'test2c', 'test3', 'test3b', 'test3c', 'test3d']
RUNTIME = {'AcquisitionStartTime', 'PerformanceCounterFrequency', 'END'}
DIFF_ARRAYS = ('acq_b', 'acq_x', 'acq_y', 'acq_z')


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
    # acq_grad is a gradient-amplitude cache, not the selected b input in mode 1.
    if v.get('b_input_mode') == 1:
        v.pop('acq_grad', None)
    return v


def csv_write(name, rows):
    with (OUT / name).open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: json.dumps(x, ensure_ascii=False) if isinstance(x, (dict, list)) else x
                          for k, x in row.items()} for row in rows)


def fmt(v):
    return '—' if v is None else f'{v:g}'


def main():
    scans = []
    for rank, name in enumerate(ORDER, 1):
        folders = list((ROOT / 'experiments').glob(f'FSE-DWI_10-07-*_{name}'))
        assert len(folders) == 1, (name, folders)
        folder = folders[0]
        mrd, ppr = next(folder.glob('*.MRD')), next(folder.glob('*.ppr'))
        parsed = parse_mrd(mrd)
        v, records = parsed['values'], parsed['records']
        sv, sr = parse_ppr(ppr.read_text(encoding='latin1'))
        protocol_diffs = differences(sv, v, RUNTIME)
        # Report scanner-only records separately, never mask shared calibration differences.
        shared_diffs = {k: pair for k, pair in protocol_diffs.items() if k in sv and k in v}
        embedded_only = {k: pair[1] for k, pair in protocol_diffs.items() if k not in sv}
        etl = int(v['VIEWS_PER_SEGMENT'])
        n = int(v['no_diff_acq'])
        b = v['acq_b'][:n]
        jp = next(folder.glob('*.json'))
        j = json.loads(jp.read_text(encoding='utf-8'))
        comparisons = {'PEOrder': (j.get('PEOrder'), v['PE_order']),
                       'BValueInputMode': (j.get('BValueInputMode'), v['b_input_mode']),
                       'DiffusionOn': (j.get('DiffusionOn'), v['diff_on']),
                       'SmallDelta_ms': (j.get('SmallDelta_ms'), v['sm_delta']/1000),
                       'BigDelta_ms': (j.get('BigDelta_ms'), v['big_delta']/1000),
                       'bval_s_per_mm2': (j.get('bval_s_per_mm2'), b),
                       'SliceSpacing_mm': (j.get('SliceSpacing_mm'), v['slice_offset'][-1]),
                       'SliceOffsets_mm': (j.get('SliceOffsets_mm'), [0.0])}
        json_check = {k: {'json': a, 'mrd': z, 'match': stable_equal(a, z)} for k, (a,z) in comparisons.items()}
        bp, vp, np = next(folder.glob('*.bval')), next(folder.glob('*.bvec')), next(folder.glob('*.nii.gz'))
        bside = [float(x) for x in bp.read_text().split()]
        vec = [[float(x) for x in line.split()] for line in vp.read_text().splitlines() if line.strip()]
        expected_vec = [[0.0 if bv == 0 else v[k][i]/1000 for i,bv in enumerate(b)] for k in ('acq_x','acq_y','acq_z')]
        with gzip.open(np, 'rb') as f:
            header = f.read(348)
        endian = '<' if struct.unpack('<i',header[:4])[0] == 348 else '>'
        dims = list(struct.unpack(endian+'8h',header[40:56]))
        pixdim = list(struct.unpack(endian+'8f',header[76:108]))
        present = sorted(p.name for p in folder.iterdir() if p.is_file())
        row = dict(scan=name, catalog_order=rank, folder=relative(folder), mrd=relative(mrd),
                   mrd_sha256=parsed['sha256'], mrd_bytes=parsed['byte_size'], sidecar_ppr=relative(ppr),
                   sidecar_ppr_sha256=sha256(ppr), sidecar_ppr_basename_matches_scan=ppr.stem == folder.name,
                   embedded_ppl=v['PPL'], embedded_ppl_version=re.search(r'twoTE-(\d+\.\d+)\.ppl',v['PPL']).group(1),
                   mrd_mtime_utc=datetime.fromtimestamp(mrd.stat().st_mtime,timezone.utc).isoformat(timespec='seconds'),
                   acquisition_start_counter=v['AcquisitionStartTime'], performance_counter_frequency=v['PerformanceCounterFrequency'],
                   embedded_receiver_gain=v['_ObserveReceiverGain'], embedded_transmit_gain=v['_ObserveTransmitGain'],
                   embedded_decouple_gain=v['_DecoupleTransmitGain'], dims=parsed['dims'], datatype_hex=parsed['datatype_hex'],
                   views_per_segment=etl, raw_views=parsed['dims']['views'], imaging_views=parsed['dims']['views']-int(v['nav_on'])*etl,
                   no_diff_acq=n, b_values=b, diffusion_directions_scaled={k:v[k][:n] for k in DIFF_ARRAYS[1:]},
                   pe_order=v['PE_order'], te_ms=v['te'], esp_ms=v['esp'],
                   first_crusher_duration_us=v['diff_tcrush'], train_crusher_duration_us=v['tcrush'],
                   first_crusher_baseline_dac=v['diff_crush_amp'], train_crusher_baseline_dac=v['crush_amp'],
                   crusher_schedule=v['crusher_schedule'], crusher_step_pct=v['crusher_step_pct'],
                   crusher_custom_count=v['crusher_custom_count'], crusher_custom_pct=v['crusher_custom_pct'],
                   sidecar_protocol_values_match=not shared_diffs, sidecar_protocol_value_diffs=shared_diffs,
                   sidecar_embedded_only_runtime_values=embedded_only,
                   json=dict(available=True,path=relative(jp),comparisons=json_check),
                   diffusion_sidecars=dict(bval_path=relative(bp),bvec_path=relative(vp),bval_values=bside,bvec_values=vec,
                                           bval_match=stable_equal(bside,b),bvec_match=stable_equal(vec,expected_vec)),
                   nifti=dict(path=relative(np),dims=dims,pixdim=pixdim,datatype=struct.unpack(endian+'h',header[70:72])[0],
                              shape_matches_mrd=dims[:5]==[4,128,128,1,n]),
                   data_payload_complete=parsed['payload_end_offset']+120==parsed['embedded_ppr_offset'],
                   nonzero_experiment_slots=parsed['nonzero_experiment_slots'],nonzero_experiment_count=sum(parsed['nonzero_experiment_slots']),
                   trailing_bytes_before_ppr=parsed['gap_bytes_before_ppr'],present_files=present,
                   _embedded_values={k:x for k,x in v.items() if k not in RUNTIME},_embedded_records=records,
                   _sidecar_values=sv,_sidecar_records=sr)
        assert row['data_payload_complete'] and all(row['nonzero_experiment_slots']), name
        assert all(x['match'] for x in json_check.values()), (name,json_check)
        assert row['diffusion_sidecars']['bval_match'] and row['diffusion_sidecars']['bvec_match'] and row['nifti']['shape_matches_mrd'], name
        scans.append(row)
    anchor = min(x['acquisition_start_counter'] for x in scans)
    chrono = sorted(scans,key=lambda x:x['acquisition_start_counter'])
    assert len({x['performance_counter_frequency'] for x in scans})==1
    for rank,row in enumerate(chrono,1):
        row['counter_order']=rank
        row['acquisition_elapsed_minutes_from_test0']=(row['acquisition_start_counter']-anchor)/row['performance_counter_frequency']/60
    pairs=[]
    for a,b in itertools.combinations(scans,2):
        va,vb=a['_embedded_values'],b['_embedded_values']
        ar,br=a['_embedded_records'],b['_embedded_records']
        pairs.append(dict(scan_a=a['scan'],scan_b=b['scan'],same_mrd_sha256=a['mrd_sha256']==b['mrd_sha256'],
                          protocol_differences=differences(va,vb),active_protocol_differences=differences(active_protocol(va),active_protocol(vb)),
                          raw_record_difference_keys=[k for k in sorted(set(ar)|set(br)) if k not in RUNTIME and ' '.join(ar.get(k,'').split())!=' '.join(br.get(k,'').split())]))
    all_keys=sorted(set().union(*(r['_embedded_values'] for r in scans)))
    varying={k:{r['scan']:r['_embedded_values'].get(k) for r in scans} for k in all_keys
             if any(not stable_equal(scans[0]['_embedded_values'].get(k),r['_embedded_values'].get(k)) for r in scans[1:])}
    source_files=[ROOT/'scanner'/f'FSE_dwi_CPMG_non_CPMG_twoTE-{v}.ppl' for v in ('1.91','1.92')]
    audit=dict(title='October 7, 2026 physical scanner protocol audit',scans=scans,controlled_pairs=pairs,
               all_varying_embedded_fields=varying,
               available_current_sources=[dict(path=relative(p),sha256=sha256(p)) for p in source_files],
               method={'authoritative_metadata':'MRD-embedded PPR describes the acquisition; adjacent PPR discrepancies are retained explicitly.',
                       'counter':'Hardware performance counter, relative chronology only; not a civil timestamp.',
                       'payload':'Dimensions and datatype from binary MRD header; exact 120-byte interstitial region and nonzero experiment slots checked.',
                       'active_pair_comparison':'Acquisition arrays trimmed at no_diff_acq; mode-1 acq_grad inactive cache omitted. Full stored arrays/raw record differences retained separately.',
                       'source_identity':'Embedded PPL paths name releases but contain no source hashes; available current source hashes identify repository copies, not a proven scanner build.'})
    (OUT/'oct07_protocol_audit.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    csv_write('oct07_protocol_scans.csv',[{k:x for k,x in r.items() if not k.startswith('_')} for r in scans])
    csv_write('oct07_protocol_pairs.csv',pairs)
    csv_write('oct07_protocol_variations.csv',[dict(field=k,**values) for k,values in varying.items()])
    make_catalog(scans)
    make_audit_notes(scans,chrono,pairs,varying)
    print('Audited 10 MRDs:', ', '.join(r['scan'] for r in chrono))
    print('Shared PPR discrepancies:',{r['scan']:r['sidecar_protocol_value_diffs'] for r in scans if not r['sidecar_protocol_values_match']})
    print('All binary payload, experiment, NIfTI shape, JSON and diffusion-sidecar checks passed.')


def make_catalog(scans):
    lines=['# Scanner experiments — October 7, 2026','',
           'All 10 acquisitions were verified using their MRD-embedded PPR, adjacent PPR, reconstructed NIfTI header, JSON and diffusion sidecars. The main table keeps scan-name order; the second table gives actual acquisition-counter chronology. Embedded metadata takes precedence where adjacent PPRs differ. A version label identifies the recorded scanner PPL path; it does not prove the source/build used on the scanner.','',
           '**Sample provenance:** Water phantom, per user; temperature not supplied. The user identifies b=6000 s/mm² as a condition where primary water signal is not expected.','',
           'All scans use centric phase encoding (`PE_order=1`), navigators on, stored TR 2000 ms, TE 54 ms and echo spacing 14 ms, nominal diffusion duration δ=4 ms and separation Δ=40 ms, with read-axis (x) diffusion. For the new methods, TE 54 ms denotes the preparation echo, not the first acquired imaging echo. Current-source modeling places the first imaging echo at approximately 73.716 ms for v1.91 and 68 ms for v1.92, versus 54 ms for v1.8; these source-modeled times are not scanner timing measurements. They have 128 readout samples at 50 µs, 128 imaging phase-encode lines, FOV 35 mm, one 1 mm imaging slice and 1.2 mm slice separation. All record RX gain 30, TX gain −195 and decoupler gain −453.','',
           'Crusher entries are **first diffusion echo / subsequent train baseline** in DAC units, with 1000 / 1000 µs plateaus and 200 µs ramps throughout. All schedules are constant (`crusher_schedule=0`); the stored 40% step in v1.8 is inactive for this schedule. ETL means echo train length; navigator views are additional raw lines, not extra imaging lines.','',
           '| Order | Scan / PPR | PPL / method | b-values (s/mm²) | Raw / imaging views / ETL | First / train crusher (DAC) | Schedule code / stored step % | Embedded `gp_init_var` / `SMY` | Adjacent PPR discrepancy |',
           '|---|---|---|---|---|---|---|---|---|']
    comparison=[]
    for r in scans:
        v=r['_embedded_values']; version=r['embedded_ppl_version'];method={'1.8':'legacy','1.91':'ss-MGOT','1.92':'Alsop'}[version]
        btext='0, 1000, 6000' if r['no_diff_acq']==3 else '0, 100, 500, 1000, 2000, 3000, 6000'
        link=Path(r['sidecar_ppr']).relative_to('experiments').as_posix()
        mismatch='`gp_init_var`, `SMY`' if not r['sidecar_protocol_values_match'] else 'None'
        lines.append(f'| {r["catalog_order"]} | [{r["scan"]}]({link}) | {version} — {method} | {btext} | {r["raw_views"]} / {r["imaging_views"]} / {r["views_per_segment"]} | {fmt(v["diff_crush_amp"])} / {fmt(v["crush_amp"])} | {fmt(v["crusher_schedule"])} / {fmt(v["crusher_step_pct"])} | {fmt(v["gp_init_var"])} / {fmt(v["SMY"])} | {mismatch} |')
        c=dict(scan=r['scan'],ppr=r['sidecar_ppr'],mrd=r['mrd'],mrd_sha256=r['mrd_sha256'],ppl_version=version,method=method,
               catalog_order=r['catalog_order'],counter_order=r['counter_order'],elapsed_minutes=r['acquisition_elapsed_minutes_from_test0'],
               raw_views=r['raw_views'],imaging_views=r['imaging_views'],etl=r['views_per_segment'],b_values=r['b_values'],
               rx_gain=r['embedded_receiver_gain'],tx_gain=r['embedded_transmit_gain'],decouple_gain=r['embedded_decouple_gain'],
               adjacent_ppr_matches_embedded=r['sidecar_protocol_values_match'],adjacent_ppr_differences=r['sidecar_protocol_value_diffs'])
        for k in ('tr','te','esp','PE_order','nav_on','sm_delta','big_delta','sample_period','FOV','gs_var','slice_offset','rfcal','alpha','p180_scale','diff_crush_amp','crush_amp','diff_tcrush','tcrush','tramp','crusher_schedule','crusher_step_pct','crusher_custom_count','crusher_custom_pct','crush_independent_on','crusher_max_dac','crusher_slew_dac_100us','gp_init_var','SMX','SMY','gr_var','grad_var','no_disacq','no_discard','b_input_mode','v19_on','v19_cycles','v19_comp_flat','v19_slab_pml','v19_tip_pml','v19_spoil_cpmm','v19_spoil_dac'):
            c[k]=v.get(k)
        c['active_refocusing_flip_degrees']=[x/10 for x in v.get('v19_flip_tenths',[])[:r['views_per_segment']]]
        comparison.append(c)
    csv_write('oct07_scan_comparison.csv',comparison)
    lines += ['', '**Chronology and acquisition integrity**','',
              '| Scan | Counter order | Minutes from test0 | Experiments / nonzero raw slots | Reconstructed NIfTI shape | Diffusion sidecars |',
              '|---|---:|---:|---|---|---|']
    for r in scans:
        lines.append(f'| {r["scan"]} | {r["counter_order"]} | {r["acquisition_elapsed_minutes_from_test0"]:.2f} | {r["no_diff_acq"]} / {r["nonzero_experiment_count"]} | 128 × 128 × 1 × {r["no_diff_acq"]} | JSON / bval / bvec match embedded protocol |')
    lines += ['', 'Counter times provide relative acquisition order, not clock times. The order is test0, test1, test2, test3, test2b, test3b, test2c, test3c, test1b, test3d. Test3d repeats the exact embedded protocol of test3c approximately 35.78 minutes later. Test1b is a late v1.8 control, despite its name. All 46 experiment slots contain nonzero raw data, and all expected complex payloads are present; this is a completeness check, not evidence of good signal.','',
              '**New method parameters**','',
              'Both v1.91 (ss-MGOT) and v1.92 (Alsop) record `v19_on=1`, two cycles of added dephasing across the imaging slice (`v19_cycles=2`) and a 1000 µs compensation-lobe plateau (`v19_comp_flat=1000`). Their stored refocusing flip array is in tenths of a degree. The active ETL8 flips are 142.2°, 94.9°, 69.2°, 63.0°, 60.2°, 60°, 60°, 60°; ETL16 adds eight further 60° pulses. VFA means variable flip angle: the refocusing pulses intentionally change angle through the train. v1.8 does not expose that VFA array. All protocols store `rfcal=594`, `alpha=90` and `p180_scale=185`, but the revised method branches bypass the legacy `alpha` and `p180_scale` controls. RF calibration and actual achieved method flip angles remain physically unverified; matching stored scales do not imply identical transmitted pulses.','',
              'v1.91 additionally stores prep slab width 3000 per mille (3 × the imaging-slice width), tip-up width 1667 per mille (1.667 ×), spoiler moment 32 cycles/mm on the phase axis, and spoiler amplitude 16384 DAC. v1.92 omits those preparation-only fields. The intended mechanisms and the revised compiler-compatible source are discussed in the [analysis report](../docs/physical_scanner_experiments_2026-10-07.md) and [compiler-compatibility documentation](../docs/v19/compiler_compatibility).','',
              '**Controlled comparisons and co-changes**','',
              '| Comparison | Intended factor | Other recorded differences / interpretation |',
              '|---|---|---|',
              '| test0 / test1 | Stronger train crushers | Only `crush_amp` changes, −5482 to −8223; first crusher remains −5482. Both are ETL8. Today’s test0 is not a single-echo control. |',
              '| test1 / test2 / test3 | v1.8 / ss-MGOT v1.91 / Alsop v1.92 at ETL8 | Matching imaging geometry, gains, stored timing fields, nominal b entries and crusher baselines. Actual first imaging echo occurs later in the new-method source models. New methods intentionally change RF/dephasing and preparation; inactive array capacities and stored schedule step also differ. |',
              '| test2 / test2b; test3 / test3b | ETL8 / ETL16 | Raw views 136→144, embedded phase calibration −1000 / 0.0305406→−1059 / 0.0323371, and eight more VFA pulses. ETL is not the only metadata change. |',
              '| test2b / test3b | ss-MGOT / Alsop at ETL16, three b entries | Matching stored timing, gains, imaging geometry, b entries and common VFA/dephasing fields; preparation and source-modeled first imaging echo time differ. |',
              '| test2c / test3c; test1b / test2c / test3c | Seven-b ETL16 method comparisons | Matching active diffusion arrays, imaging geometry, gains, stored timing fields and crusher baselines. Preparation, RF path and first imaging echo time differ between methods. Test1b was acquired later. |',
              '| test2b / test2c; test3b / test3c | Three / seven b entries | Nominal protocol otherwise matches within method; elapsed time differs. Compare by b-value rather than experiment number. |',
              '| test3c / test3d | Repeatability | All embedded protocol/scanner records match except acquisition counter. Different raw files; no intervention is documented in their metadata. |','',
              '**Metadata details that affect comparisons**','',
              'For test1b, test2c and test3b, the adjacent PPR stores `gp_init_var=-1000`, `SMY=0.0305406`, while the acquired MRD embeds −1059 and 0.0323371. The catalog and numerical analysis use the embedded values. Other shared normalized PPR fields match; scanner gains and delay/mask tags occur only in the embedded acquisition record. Do not use the standalone PPR to infer these three acquisitions’ phase calibration.','',
              'Test1b and test2b reuse PPR basenames ending in test1 and test2, respectively. Each link points to the actual PPR within the relevant scan folder; filenames are not used as protocol identities. The v1.8 acquisition arrays reserve 512 entries and the v1.9 arrays 64. Only the first `no_diff_acq` entries are active. In particular, trailing nonzero direction entries in v1.8 test1b do not add experiments; the MRD, JSON, bval, bvec and NIfTI all agree on seven entries.','',
              'All b-values are requested values. Additional gradients and coherence pathways can affect actual diffusion weighting; the metadata agreement does not independently validate the effective b-tensor or the physical gradient calibration. The legacy and new methods also differ in the intended RF and gradient events, so an equal requested b-value alone does not establish an equal signal pathway.','',
              'Compared with October 5, the recorded TX gain is −195 rather than −205. No validated gain-to-amplitude conversion is available, so comparisons across days should not treat brightness changes as sequence performance alone.','',
              'The [complete comparison CSV](../docs/data/oct07_scan_comparison.csv) includes common important parameters and every new-method control. The [protocol audit](../docs/data/oct07_protocol_audit.md), [all varying embedded fields](../docs/data/oct07_protocol_variations.csv), and [all 45 pair comparisons](../docs/data/oct07_protocol_pairs.csv) retain the full differences. See the [report and comparison figures](../docs/physical_scanner_experiments_2026-10-07.md) for quality assessment. Rebuild the catalog and audit with `python docs/data/oct07_protocol_audit.py`.','']
    (ROOT/'experiments/scan_catalog_2026-10-07.md').write_text('\n'.join(lines),encoding='utf-8')


def make_audit_notes(scans,chrono,pairs,varying):
    lines=['# October 7 physical scanner protocol audit','',
           'Reproducible script: [oct07_protocol_audit.py](oct07_protocol_audit.py). Detailed outputs: [JSON](oct07_protocol_audit.json), [scans CSV](oct07_protocol_scans.csv), [pairs CSV](oct07_protocol_pairs.csv), [varying fields CSV](oct07_protocol_variations.csv), [comparison CSV](oct07_scan_comparison.csv). The script uses only Python’s standard library and the existing October 5 PPR/MRD parser.','',
           'All 10 MRDs have datatype 0x15 (complex 32-bit floating components), complete dimension-derived payloads and exactly 120 bytes between payload and embedded PPR. All 46 experiment slots contain nonzero raw data. Every reconstructed NIfTI header is 128 × 128 × 1 × the acquired experiment count. Every JSON PE order, b-input mode, diffusion flag, δ/Δ, b array, centered slice offset and slice spacing agrees with embedded acquisition metadata. Every bval and bvec agrees, using a zero vector for b=0. These checks establish structural completeness and metadata consistency, not image quality or calibrated diffusion accuracy.','',
           'Acquisition chronology: '+', '.join(r['scan'] for r in chrono)+'. All use the same 10 MHz hardware-counter frequency; counter values are not calendar timestamps. File modification timestamps are separately recorded in UTC as file metadata.','',
           'All scans record receiver gain 30, transmit gain −195 and decoupler gain −453. Adjacent PPRs omit scanner runtime gains, masks and delays. Shared normalized fields disagree only for test1b, test2c and test3b:','',
           '| Scan | Field | Adjacent PPR | MRD embedded acquisition |','|---|---|---:|---:|']
    for r in scans:
        for k,(a,b) in r['sidecar_protocol_value_diffs'].items():
            lines.append(f'| {r["scan"]} | `{k}` | {fmt(a)} | {fmt(b)} |')
    lines += ['', 'The embedded values are authoritative for cataloging acquired settings. Test1b and test2b also reuse PPR filenames from test1 and test2; folder association and content comparison resolve them.','',
              'All 45 scan pairs are compared using every normalized embedded field and every raw PPR record, excluding only counter, frequency and END. The JSON contains full stored arrays. A second pair-difference field trims active acquisition arrays to `no_diff_acq` and removes inactive `acq_grad` caches in b-input mode 1, separating actual requested acquisition differences from reserved tails. Both representations remain available for inspection.','',
              'Stored varying fields: '+', '.join(f'`{k}`' for k in varying)+'. Common fields are still retained in each scan’s complete `_embedded_values` and `_embedded_records`.','',
              'Test3c/test3d are an exact protocol repeat: no normalized or raw embedded-record difference remains after excluding acquisition counter/frequency/END. Their MRD hashes differ. A late repeat can reveal stability but the absence of an intervention record cannot prove the physical setup was unchanged.','',
              'The MRDs embed release paths ending in 1.8, 1.91 or 1.92. Current v1.91/v1.92 source copies are present in `scanner/`; their SHA-256 identities are recorded under `available_current_sources`. The MRD carries no source-content hash, so matching version/path labels cannot prove which compiler-compatible build generated each acquisition. See the current [compiler-compatibility artifacts](../v19/compiler_compatibility) and sequence-source analysis in the [scan report](../physical_scanner_experiments_2026-10-07.md).','']
    (OUT/'oct07_protocol_audit.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__ == '__main__':
    main()
