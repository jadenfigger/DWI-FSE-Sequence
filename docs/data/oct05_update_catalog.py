"""Refresh Oct 5 comparison tables from the audited MRD-embedded protocols.

Run oct05_protocol_audit.py first after changing source scans. This script writes
only the derived catalog and a comprehensive comparison CSV, preserving notes.
"""
from pathlib import Path
import csv, json

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'docs/data'
catalog=ROOT/'experiments/scan_catalog_2026-10-05.md'
audit=json.loads((DATA/'oct05_protocol_audit.json').read_text(encoding='utf-8'))
rows=audit['scans']
fmt=lambda x: 'Not exposed' if x is None else f'{x:g}'
pe_labels={1:'centric (egen)',5:'single echo',6:'reverse centric',7:'linear interleaved'}
schedule_labels={0:'Constant',1:'Increasing',3:'Increasing + alternating',4:'Decreasing',5:'Custom'}
lines=[
    '# Scanner experiments — October 5, 2026','',
    'Comparison of all 20 scans, verified against each MRD-embedded PPR and its adjacent PPR. Rows use scan-name order; the second table records acquisition-counter order and elapsed time. These counters provide relative chronology, not civil timestamps. PPL versions identify the recorded file path; the exact v1.8 source/build is unavailable.', '',
    'All scans request b=0, 1000, 6000 s/mm², TR 2000 ms, TE 54 ms, diffusion duration δ=4 ms and read-axis diffusion. They use 128 readout samples at 50 µs, FOV 35 mm, one 1 mm slice and centered zero-angle geometry. Crusher amplitudes and durations below are **first-DWI / subsequent train baseline**, before schedule scaling; durations are plateaus and exclude the 200 µs ramps.', '',
    '| Order | Scan / PPR | PPL | `PE_order` | Raw / imaging views / ETL | Navigator | RX gain | TE / ESP / Δ (ms) | Crusher baseline (DAC) | First / train duration (µs) | Schedule (code; step %) |',
    '|---|---|---|---|---|---|---:|---|---|---|---|',
]
export=[]
for r in rows:
    v=r['_embedded_values']; n=r['scan']; nav=int(v['nav_on'])
    etl=int(v['VIEWS_PER_SEGMENT']); raw=r['dims']['views']; imaging=raw-nav*etl
    pe=int(r['pe_order']); schedule=r['crusher_schedule']
    schedule_text='Legacy; no field' if schedule is None else f'{schedule_labels[int(schedule)]} ({int(schedule)}; {fmt(r["crusher_step_pct"])})'
    link=Path(r['sidecar_ppr']).relative_to('experiments').as_posix()
    baseline='Not exposed' if r['first_crusher_baseline_dac'] is None else f'{fmt(r["first_crusher_baseline_dac"])} / {fmt(r["train_crusher_baseline_dac"])}'
    lines.append(f'| {r["catalog_order"]} | [{n}]({link}) | {r["embedded_ppl_version"]} | {pe} — {pe_labels[pe]} | {raw} / {imaging} / {etl} | {"On" if nav else "Off"} | {fmt(r["embedded_receiver_gain"])} | {fmt(r["te_ms"])} / {fmt(r["esp_ms"])} / {fmt(v["big_delta"]/1000)} | {baseline} | {fmt(r["first_crusher_duration_us"])} / {fmt(r["train_crusher_duration_us"])} | {schedule_text} |')
    custom=(r['crusher_custom_pct'] or [])[:int(r['crusher_custom_count'] or 0)]
    record=dict(scan=n,ppr=r['sidecar_ppr'],mrd=r['mrd'],mrd_sha256=r['mrd_sha256'],ppl_version=r['embedded_ppl_version'],catalog_order=r['catalog_order'],acquisition_counter_order=r['counter_order'],elapsed_minutes=r['acquisition_elapsed_minutes_from_test0'],pe_order=pe,pe_order_name=pe_labels[pe],raw_views=raw,imaging_views=imaging,etl=etl,nav_on=nav,rx_gain=r['embedded_receiver_gain'],tx_gain=r['embedded_transmit_gain'],decouple_gain=r['embedded_decouple_gain'],tr_ms=v['tr'],te_ms=r['te_ms'],esp_ms=r['esp_ms'],small_delta_ms=v['sm_delta']/1000,big_delta_ms=v['big_delta']/1000,b_values=json.dumps(r['b_values']),diffusion_axis='read (x)',first_crusher_baseline_dac=r['first_crusher_baseline_dac'],train_crusher_baseline_dac=r['train_crusher_baseline_dac'],first_crusher_duration_us=r['first_crusher_duration_us'],train_crusher_duration_us=r['train_crusher_duration_us'],crusher_ramp_us=v['tramp'],crusher_schedule=schedule,crusher_step_pct=r['crusher_step_pct'],crusher_custom_count=r['crusher_custom_count'],crusher_custom_pct=json.dumps(custom),crush_independent_on=v.get('crush_independent_on'),crusher_max_dac=v.get('crusher_max_dac'),crusher_slew_dac_100us=v.get('crusher_slew_dac_100us'),slice_separation_mm=v['slice_offset'][-1],gp_init_var=v['gp_init_var'],SMY=v['SMY'],rfcal=v['rfcal'],alpha=v['alpha'],p180_scale=v['p180_scale'],grad_var=json.dumps(v['grad_var']),read_gradient_dac=v['gr_var'],no_disacq=v['no_disacq'],no_discard=v['no_discard'],nifti_available=bool(r['json']['available']))
    export.append(record)
lines += ['', '**Chronology, geometry/calibration differences and derived-file availability**', '',
    '| Scan | Counter order | Minutes from test0 | Slice separation (mm) | `gp_init_var` | `SMY` | NIfTI + diffusion sidecars |',
    '|---|---:|---:|---:|---:|---:|---|']
for r in export:
    lines.append(f'| {r["scan"]} | {r["acquisition_counter_order"]} | {r["elapsed_minutes"]:.2f} | {r["slice_separation_mm"]:g} | {r["gp_init_var"]:g} | {r["SMY"]:g} | {"Present" if r["nifti_available"] else "Absent; raw MRD available"} |')
old=catalog.read_text(encoding='utf-8')
notes=old[old.index('All increasing, increasing-plus-alternating'):].split('**Controlled comparisons and important co-changes**')[0]
notes=notes.replace('1 (egen)', '1 (centric / egen)')
lines += ['', 'All scans record TX gain−205 and decoupler gain−453; RX gain differs for test0 as shown. No validated gain-to-amplitude conversion was supplied, so test0 is not an absolute-brightness control for the ETL8 scans.', '', notes.strip(), '',
    '**Controlled comparisons and important co-changes**', '',
    '| Comparison | Intended factor | Other differences to retain in interpretation |',
    '|---|---|---|',
    '| test1 / test1e; test1b / test1c; test2 / test2b; test3 / test3b | Crusher baseline sign | Matching timing, PE order and absolute per-echo crusher areas within each pair |',
    '| test1e / test1f / test1g; test2b / test2c / test2d | PE1 / PE6 / PE7 | Only PE order differs in embedded records apart from counters, within each group |',
    '| test2 / test3; test2b / test3b; test6 / test7 | Per-echo signs / alternation | Identical per-echo absolute crusher areas within each pair |',
    '| test2b / test5 | Increasing / decreasing | Same first crusher and total absolute area; train magnitudes reversed |',
    '| test1 / test2; test1e / test2b | Constant / increasing | Total absolute area also increases; schedule shape is not isolated |',
    '| test1 / test1b | Longer constant crushers | ESP, first amplitude and durations change together |',
    '| test1c / test1d | Negative amplitude doubled | Absolute area doubles; timing and PE order match |',
    '| test4 / test5 | Stronger decreasing baseline | Train absolute area also changes |',
    '| test4 / test4b | Decreasing amplitude / first duration | Baseline and first duration both change |',
    '| test0 / ETL8 scans | Single echo | PE order, navigator, RX gain and phase calibration also differ |',
    '| testa / v1.8 scans | Legacy sequence | Δ, ESP, crusher implementation and slice separation differ |', '',
    'The [complete comparison CSV](../docs/data/oct05_scan_comparison.csv) includes the table fields plus diffusion settings, custom arrays, RF scales, gradient calibration and crusher limits. The [embedded-protocol audit](../docs/data/oct05_protocol_audit.md) records source identities and pair differences. See the [analysis report with image and k-space comparisons](../docs/physical_scanner_experiments_2026-10-05.md) for observations and the conditional ramp-inclusive crusher-area calculations. Protocol settings alone do not establish scan quality.', '',
    'Rebuild these tables after the protocol audit with `python docs/data/oct05_update_catalog.py`.', '',
]
catalog.write_text('\n'.join(lines),encoding='utf-8')
with (DATA/'oct05_scan_comparison.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(export[0]));w.writeheader();w.writerows(export)
print('Updated catalog and complete comparison CSV for20 scans.')
