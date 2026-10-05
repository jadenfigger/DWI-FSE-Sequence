"""Bounded, isolated reproduction of selected archived v1.7 comparisons."""
from pathlib import Path
import contextlib, csv, hashlib, importlib.metadata, io, json, sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import MRzeroCore as mr0
from dwfse import generate, simulate, btensor
from dwfse.pathways import with_mrzero_closure

OUT = ROOT/'runs/combined_design'
with (ROOT/'docs/data/scanner_v17_validation.csv').open() as stream:
    archived = list(csv.DictReader(stream))
vox = simulate.make_voxel(n=10000, seed=1)
records = []
for name, version, mode in [('original','1.6',0), ('increasing_alternating','1.7',3)]:
    folder = OUT/name
    folder.mkdir(parents=True, exist_ok=True)
    overrides = dict(views_per_seg=8,no_views=16,te=36,esp=16,
        acq_b=[0,1000]+[0]*510,no_diff_acq=2,no_experiments=2,
        acq_x=[1000,1000]+[0]*510,sim_reduced_shots=[1],sim_reduced_rows=[1],
        crusher_schedule=mode,crusher_step_pct=40,sim_excitation_phase_deg=0)
    seq,c,d,_ = generate.build_sequence(ppr=str(ROOT/'scanner'/f'FSE_dwi_CPMG_non_CPMG_twoTE-{version}.ppr'),overrides=overrides,reduced=True)
    assert seq.check_timing()[0]
    path = folder/'seq.seq'
    seq.write(str(path))
    restored = simulate.read_seq(path)
    assert restored.check_timing()[0]
    (folder/'overrides.json').write_text(json.dumps(overrides,indent=2))
    r = simulate.simulate(restored,b1=.8,b0=0,voxel=vox,rf_dt=1e-5)
    ends = np.cumsum(np.r_[0,r['adc_sizes']])
    signals = [r['signal'][a+(b-a)//2] for a,b in zip(ends[:-1],ends[1:])]
    np.savez_compressed(folder/'bloch.npz',signal=r['signal'],t_adc=r['t_adc'],adc_sizes=r['adc_sizes'])
    bt = btensor.calculate(restored)
    for D in [0.,.001]:
        with contextlib.redirect_stdout(io.StringIO()):
            model = mr0.Sequence.import_file(str(path))
            data = mr0.CustomVoxelPhantom(pos=[[0.,0.,0.]],PD=1.,T1=1.5,T2=.08,
                T2dash=.03,D=D*1e3,B0=0.,B1=.8,voxel_size=[.0002,.0002,.001],voxel_shape='box').build()
            metrics = with_mrzero_closure(model,data,max_state_count=1000000)
        for m,signal in zip(metrics,signals):
            previous = next(x for x in archived if x['variant']==name and float(x['b1'])==.8
                and float(x['b0_Hz'])==0 and float(x['excitation_phase_deg'])==0
                and float(x['D_mm2_s'])==D and int(x['echo'])==m.echo)
            rec = dict(variant=name,D_mm2_s=D,echo=m.echo,closure_relative_error=m.closure_relative_error)
            for key,value in [('pdg_primary',m.primary),('pdg_total',m.total),('pdg_other',m.other)]:
                rec[key+'_real']=float(value.real)
                rec[key+'_imag']=float(value.imag)
                rec[key+'_abs']=float(abs(value))
                old = complex(float(previous[key+'_real']),float(previous[key+'_imag']))
                rec[key+'_complex_error']=float(abs(value-old))
            rec['unwanted_L1_amplitude_share']=m.other_l1_fraction
            rec['L1_share_error']=abs(m.other_l1_fraction-float(previous['unwanted_L1_amplitude_share']))
            if D==0:
                old = complex(float(previous['bloch_static_total_real']),float(previous['bloch_static_total_imag']))
                rec['bloch_complex_error']=float(abs(signal-old))
                rec['bloch_magnitude']=float(abs(signal))
            records.append(rec)
    print(name, 'complete', flush=True)
old_provenance=json.loads((ROOT/'docs/data/improvement_provenance.json').read_text())
source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
    for p in [ROOT/'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.6.ppl',ROOT/'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.6.ppr']}
summary=dict(settings=dict(n=10000,seed=1,rf_dt=1e-5,b1=.8,b0=0,phase=0,D_mm2_s=[0,.001]),
    archived_csv='docs/data/scanner_v17_validation.csv',source_sha256=source_hashes,
    prior_provenance_matches={k:v==old_provenance['source_sha256'][k] for k,v in source_hashes.items()},
    versions={k:importlib.metadata.version(k) for k in ['numpy','pypulseq','MRzeroCore','torch']},
    max_pdg_complex_error=max(r[k] for r in records for k in ['pdg_primary_complex_error','pdg_total_complex_error','pdg_other_complex_error']),
    max_L1_share_error=max(r['L1_share_error'] for r in records),
    max_bloch_complex_error=max(r.get('bloch_complex_error',0) for r in records),
    max_closure_relative_error=max(r['closure_relative_error'] for r in records),records=records)
summary['acceptance']=dict(pdg_complex_tolerance=1e-6,bloch_complex_tolerance=1e-6,L1_share_tolerance=1e-6,closure_relative_tolerance=5e-4)
summary['passed']=all([summary['max_pdg_complex_error']<1e-6,summary['max_bloch_complex_error']<1e-6,
    summary['max_L1_share_error']<1e-6,summary['max_closure_relative_error']<5e-4])
(OUT/'prior_reproduction.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='records'},indent=2))

