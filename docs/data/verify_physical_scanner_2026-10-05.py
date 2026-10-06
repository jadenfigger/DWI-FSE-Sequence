"""Integration verification of Oct 5 derived artifacts, identities and arithmetic."""
from pathlib import Path
import json, csv, hashlib, re, importlib.util
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'docs/data'
main=json.loads((DATA/'physical_scanner_analysis_2026-10-05.json').read_text())
protocol=json.loads((DATA/'oct05_protocol_audit.json').read_text(encoding='utf-8'))
areas=json.loads((DATA/'oct05_crusher_area.json').read_text())
names=set(main['scans'])
for path,expected_hash in main['source_sha256'].items():
    assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected_hash,path
assert len(names)==20
assert names=={r['scan'] for r in protocol['scans']}
for row in protocol['scans']:
    name=row['scan']; sc=main['scans'][name]
    actual=hashlib.sha256((ROOT/row['mrd']).read_bytes()).hexdigest()
    assert row['mrd_sha256']==sc['mrd_sha256']==actual,(name,'identity')
    assert row['data_payload_complete'],name
    assert row['embedded_receiver_gain']==(180 if name=='test0' else 30)
    assert row['embedded_transmit_gain']==-205
    assert row['b_values']==[0,1000,6000]
    assert sc['N']==128 and sc['dims'][0]==3
    bvals=list((ROOT/row['folder']).glob('*.bval'))
    if bvals:
        assert np.array_equal(np.loadtxt(bvals[0]),[0,1000,6000])
        bvec=np.loadtxt(next((ROOT/row['folder']).glob('*.bvec')))
        assert np.array_equal(bvec,[[0,1,1],[0,0,0],[0,0,0]])
    if sc['nifti_errors']: assert sc['nifti_errors']['deramp']<4e-8,name
assert sum(bool(s['nifti_errors']) for s in main['scans'].values())==18
# Replay complex imaging data to verify the new power measurements, independently
# of figure rendering. Check both raw energy and Fourier normalization explicitly.
spec=importlib.util.spec_from_file_location('oct05_replay',DATA/'physical_scanner_analysis_2026-10-05.py')
replay=importlib.util.module_from_spec(spec);spec.loader.exec_module(replay)
loaded=replay.load_scans()
with (DATA/'oct05_kspace_measurements.csv').open() as f: kcsv=list(csv.DictReader(f))
krows=main['kspace']['measurements']
assert len(krows)==len(kcsv)==120
klookup={(r['scan'],r['b'],r['mode']):r for r in krows}
assert len(klookup)==120
assert set(klookup)=={(n,b,m) for n in names for b in (0,1000,6000) for m in ('off','deramp')}
for r,c in zip(krows,kcsv):
    assert r['scan']==c['scan'] and r['mode']==c['mode']
    for key,value in r.items():
        if key not in ('scan','mode'):assert float(c[key])==value,(r['scan'],key,'CSV')
    sc=loaded[r['scan']];v=list(sc['b']).index(r['b'])
    k=replay.sorted_kspace(sc,v,r['mode']);p=abs(k)**2;total=p.sum()
    edge=p[:,np.r_[0:12,116:128]].sum()
    expected=dict(total_power=total,total_l2=np.sqrt(total),readout_edge_power_fraction=edge/total,readout_center_power_fraction=p[:,56:73].sum()/total,central_ky_band_power_fraction=p[56:72].sum()/total,all_ky_edge_sample_l2=np.sqrt(edge))
    for key,value in expected.items():assert np.isclose(r[key],value,rtol=1e-12),(r['scan'],key)
    assert all(0<=r[key]<=1 for key in r if key.endswith('_fraction'))
    assert np.isclose(total/(k.shape[0]*k.shape[1]),np.sum(abs(sc['images'][v][r['mode']])**2),rtol=1e-12)
    if r['mode']=='off':
        raw=sc['raw'][v,sc['nav']*sc['L']:].astype(np.complex128)
        assert np.isclose(total,np.sum(abs(raw)**2),rtol=1e-12)
with (DATA/'oct05_crusher_echo_areas.csv').open() as f: echo=list(csv.DictReader(f))
assert len(echo)==145
totals={r['scan']:r for r in areas['summary']}
assert set(totals)==names-{'testa'}
assert totals['test1']['pair_absolute_area_cumulative_dac_us']==59205600
assert totals['test2']['pair_absolute_area_cumulative_dac_us']==114463200
assert totals['test4b']['pair_absolute_area_cumulative_dac_us']==241625600
assert totals['test6']['pair_absolute_area_cumulative_dac_us']==79202400
for name,t in totals.items():
    rr=[r for r in echo if r['scan']==name]
    assert len(rr)==t['etl']
    signed=absolute=0
    for r in rr:
        p=int(r['pulse']); flat=t['flat_first_us'] if p==1 else t['flat_train_us']
        lobe=int(r['crusher_dac'])*(flat+200)
        assert int(r['lobe_area_dac_us'])==lobe
        assert int(r['pair_commanded_area_dac_us'])==2*lobe
        assert abs(int(r['crusher_dac']))<=32767
        signed+=2*lobe;absolute+=2*abs(lobe)
    assert signed==t['pair_signed_area_cumulative_dac_us']
    assert absolute==t['pair_absolute_area_cumulative_dac_us']
    # Independent check of nominal physical-unit conversion: DACus -> Ts/m.
    nominal=absolute*25447/32767/42.57747892e6*1e-3
    assert np.isclose(nominal,t['nominal_pair_abs_area_T_s_per_m'])
for a,b in [('test1','test1e'),('test1b','test1c'),('test2','test2b'),('test2','test3'),('test2b','test3b'),('test2b','test5'),('test6','test7')]:
    assert totals[a]['pair_absolute_area_cumulative_dac_us']==totals[b]['pair_absolute_area_cumulative_dac_us']
for a,b in [('test1','test1e'),('test1b','test1c'),('test2','test2b'),('test3','test3b')]:
    assert totals[a]['pair_signed_area_cumulative_dac_us']==-totals[b]['pair_signed_area_cumulative_dac_us']
assert sorted(map(abs,map(int,totals['test2b']['crusher_dac_by_pulse'].split(';'))))==sorted(map(abs,map(int,totals['test5']['crusher_dac_by_pulse'].split(';'))))
for pair in protocol['controlled_pairs']:
    if pair['scan_a'] in ('test1e','test1f','test2b','test2c') and pair['scan_b'] in ('test1f','test1g','test2c','test2d'):
        assert set(pair['protocol_differences'])=={'PE_order'}
masks=np.load(DATA/'oct05_roi_masks.npz')
assert all(masks[k].sum()==main['roi']['counts'][k] for k in masks)
assert not np.any(masks['interior']&masks['background'])
report=ROOT/'docs/physical_scanner_experiments_2026-10-05.md'
text=report.read_text(encoding='utf-8')
assert text.index('## Crusher-area audit')<text.index('## Crusher findings')
assert text.index('## Reproduction')<text.index('## Next scanner experiments')
def check_rounded(displayed,actual):
    clean=displayed.strip().replace('−','-').replace('+','')
    decimals=len(clean.split('.')[1]) if '.' in clean else 0
    assert abs(float(clean)-actual)<=.5001*10**(-decimals),(displayed,actual)
metric_rows={(r['scan'],r['b']):r for r in main['measurements'] if r['mode']=='deramp'}
area_section=text.split('## Crusher-area audit')[1].split('## Crusher findings')[0]
for line in area_section.splitlines():
    if not line.startswith('| test'):continue
    cells=[c.strip() for c in line.strip('|').split('|')]
    name=re.match(r'test\d+[a-z]*',cells[0])[0]
    rr=[r for r in echo if r['scan']==name]
    first=abs(int(rr[0]['pair_commanded_area_dac_us']))
    t=totals[name];absolute=t['pair_absolute_area_cumulative_dac_us']
    for displayed,actual in zip(cells[2:],[first/1e6,(absolute-first)/1e6,t['pair_signed_area_cumulative_dac_us']/1e6,absolute/1e6]):check_rounded(displayed,actual)
image_section=text.split('The quantitative anchors below')[1].split('The [full measurement table]')[0]
for line in image_section.splitlines():
    if not line.startswith('| test'):continue
    cells=[c.strip() for c in line.strip('|').split('|')]; name=cells[0]
    zero=metric_rows[name,0];low=metric_rows[name,1000];high=metric_rows[name,6000];nav=main['scans'][name]['navigators']
    actual=[zero['interior_mean'],low['interior_mean'],low['roi_ratio_to_b0'],low['interior_highpass_over_mean']*100,high['rim_mean'],high['background_mean'],nav[2]['edge_excess'][1],nav[1]['ratio'][-1]]
    for displayed,value in zip(cells[1:],actual):check_rounded(displayed,value)
links=re.findall(r'\]\(([^)]+)\)',text)
for link in links:
    if not link.startswith('http'): assert (report.parent/link).exists(),link
ksection=text.split('## K-space comparisons before reconstruction')[1].split('## Reconstruction check')[0]
for line in ksection.splitlines():
    if not line.startswith('| test'):continue
    cells=[c.strip() for c in line.strip('|').split('|')];n=cells[0]
    low=klookup[n,1000,'off'];high=klookup[n,6000,'off']
    for displayed,value in zip(cells[1:],[100*low['readout_edge_power_fraction'],100*high['readout_edge_power_fraction'],high['total_l2']]):check_rounded(displayed,value)
catalog=ROOT/'experiments/scan_catalog_2026-10-05.md';ctext=catalog.read_text(encoding='utf-8')
with (DATA/'oct05_scan_comparison.csv').open() as f: comparison=list(csv.DictReader(f))
assert len(comparison)==20 and {r['scan'] for r in comparison}==names
protocol_lookup={r['scan']:r for r in protocol['scans']}
for c in comparison:
    n=c['scan'];r=protocol_lookup[n];v=r['_embedded_values']
    assert int(c['pe_order'])==r['pe_order']==main['scans'][n]['pe']
    assert int(c['etl'])==main['scans'][n]['L']
    assert int(c['imaging_views'])==main['scans'][n]['N']
    assert int(c['nav_on'])==main['scans'][n]['nav']
    assert float(c['rx_gain'])==r['embedded_receiver_gain']
    assert c['mrd_sha256']==r['mrd_sha256']
    assert np.array_equal(json.loads(c['b_values']),r['b_values'])
    assert json.loads(c['crusher_custom_pct'])==(r['crusher_custom_pct'] or [])[:int(r['crusher_custom_count'] or 0)]
    line=next(line for line in ctext.splitlines() if f'[{n}](' in line)
    cells=[cell.strip() for cell in line.strip('|').split('|')]
    assert int(cells[3].split()[0])==int(c['pe_order'])
    assert cells[4]==f'{c["raw_views"]} / {c["imaging_views"]} / {c["etl"]}'
    assert cells[5]==('On' if int(c['nav_on']) else 'Off')
    check_rounded(cells[6],float(c['rx_gain']))
    for displayed,value in zip(cells[7].split('/'),[r['te_ms'],r['esp_ms'],v['big_delta']/1000]):check_rounded(displayed,value)
    if n!='testa':
        for displayed,value in zip(cells[8].split('/'),[r['first_crusher_baseline_dac'],r['train_crusher_baseline_dac']]):check_rounded(displayed,value)
    for displayed,value in zip(cells[9].split('/'),[r['first_crusher_duration_us'],r['train_crusher_duration_us']]):check_rounded(displayed,value)
    assert f'({int(r["crusher_schedule"])};' in cells[10] if n!='testa' else 'Legacy' in cells[10]
for link in re.findall(r'\]\(([^)]+)\)',ctext):assert (catalog.parent/link).exists(),link
assert ctext.count('**Controlled comparisons and important co-changes**')==1
assert len(re.findall(r'\[test\w*\]\(',ctext))==20
figures=list((ROOT/'docs/figures/physical_scanner_2026-10-05').glob('*.png'))
for fig in figures:
    with Image.open(fig) as im:
        assert im.width>400 and im.height>300
        im.verify()
assert len(list((ROOT/'docs/figures/physical_scanner_2026-10-05').glob('kspace_*.png')))==11
print(f'PASS: 20 MRD identities/payloads, 18 NIfTI reproductions, 120 k-space measurements and Parseval checks, 20 catalog/CSV protocols, 145 crusher echo rows, area units/pairs, report tables, source hashes, gains, ROIs, {len(figures)} readable figures and {len(links)} report links.')
