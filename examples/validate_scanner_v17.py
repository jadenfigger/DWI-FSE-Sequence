"""Reproduce v1.7 waveform/tensor and complex-signal validation.

python examples/validate_scanner_v17.py
python -m unittest discover -s tests -v

Requires the optional MRzeroCore/torch dependencies for the water/pathway check.
Raw sequences, parameters and full waveform exports go under runs/scanner_v17;
compact numerical results go into docs/data/scanner_v17_*.{csv,json}.
"""
import argparse
import contextlib
import csv
import hashlib
import importlib.metadata
import io
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dwfse import btensor, generate, simulate
from dwfse.pathways import with_mrzero_closure


def complex_fields(name, value):
    return {name+'_real':float(value.real), name+'_imag':float(value.imag),
            name+'_abs':float(abs(value))}


def main():
    import MRzeroCore as mr0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--n',type=int,default=10000)
    parser.add_argument('--b0',type=float,nargs='+',default=[0,100])
    args = parser.parse_args()
    base = dict(views_per_seg=8,no_views=16,te=36,esp=16,
                acq_b=[0,1000]+[0]*510,no_diff_acq=2,no_experiments=2,
                acq_x=[1000,1000]+[0]*510,sim_reduced_shots=[1],sim_reduced_rows=[1])
    stem = 'FSE_dwi_CPMG_non_CPMG_twoTE-'
    variants = [('original','1.6',0),('centred_constant','1.7',0),
                ('increasing','1.7',1),('increasing_alternating','1.7',3)]
    voxel = simulate.make_voxel(n=args.n,seed=1)
    records, tensor_summary = [], {}
    for name,version,mode in variants:
        for phase in [0,45,90]:
            folder = ROOT/'runs/scanner_v17'/f'{name}_phase{phase}'
            folder.mkdir(parents=True,exist_ok=True)
            overrides = dict(base,crusher_schedule=mode,crusher_step_pct=40,
                             sim_excitation_phase_deg=phase)
            seq,c,d,log = generate.build_sequence(
                ppr=str(ROOT/'scanner'/f'{stem}{version}.ppr'),overrides=overrides,reduced=True)
            ok,errors = seq.check_timing()
            if not ok:
                raise RuntimeError(errors)
            if d.diff_grad[1] <= 0:
                raise RuntimeError('validation must retain nonzero diffusion gradients')
            path = folder/'seq.seq'
            seq.write(str(path))
            restored = simulate.read_seq(path)
            if not restored.check_timing()[0]:
                raise RuntimeError('fine-raster readback timing failed')
            (folder/'params.json').write_text(json.dumps(generate.params_dict(c),indent=2))
            (folder/'setup.txt').write_text(generate.report(c,d)+'\n')
            tensors = btensor.export(restored,folder/'waveform')
            centres = [x for x in tensors['echoes'] if x['convention']=='centre']
            if phase == 0:
                tensor_summary[name] = dict(requested_b=1000,nominal_diffusion_b=d.acq_b_nominal[1],
                    diffusion_dac=d.diff_grad[1],crusher_dac=d.train_crusher_amplitudes_dac,
                    trace_by_echo=[x['trace_s_mm2'] for x in centres],
                    B_echo8_s_mm2=centres[-1]['B_s_mm2'],
                    min_te_us=d.min_te,min_esp_us=d.min_esp_us,tr_min_us=d.tr_min_us,
                    pads_us=[d.crush_pre_pad,d.crush_post_pad],rf_flat_us=d.crush_rf_flat)
            for b1 in [.8,1.0]:
                for b0 in args.b0:
                    bloch = simulate.simulate(restored,b1=b1,b0=b0,voxel=voxel,rf_dt=1e-5)
                    offsets = np.cumsum(np.r_[0,bloch['adc_sizes']])
                    signals = [bloch['signal'][a+(b-a)//2] for a,b in zip(offsets[:-1],offsets[1:])]
                    for diffusion in [0.,.001]:
                        # Preserve simulator conventions; D is explicit mm^2/s.
                        with contextlib.redirect_stdout(io.StringIO()):
                            model = mr0.Sequence.import_file(str(path))
                            data = mr0.CustomVoxelPhantom(pos=[[0.,0.,0.]],PD=1.,T1=1.5,T2=.08,
                                T2dash=.03,D=diffusion*1e3,B0=b0,B1=b1,
                                voxel_size=[.0002,.0002,.001],voxel_shape='box').build()
                            metrics = with_mrzero_closure(model,data,max_state_count=1000000)
                        for metric,signal in zip(metrics,signals):
                            closure = metric.closure_relative_error
                            if closure is None or closure > 5e-4:
                                raise RuntimeError(f'pathway closure failed: {name} {closure}')
                            record = dict(variant=name,b1=b1,b0_Hz=b0,excitation_phase_deg=phase,
                                          D_mm2_s=diffusion,echo=metric.echo,
                                          requested_diffusion_b_s_mm2=1000,
                                          achieved_primary_trace_s_mm2=centres[metric.echo-1]['trace_s_mm2'],
                                          unwanted_L1_amplitude_share=metric.other_l1_fraction,
                                          other_relative_phase_deg=metric.other_relative_phase_deg,
                                          closure_relative_error=closure)
                            record.update(complex_fields('pdg_total',metric.total))
                            record.update(complex_fields('pdg_primary',metric.primary))
                            record.update(complex_fields('pdg_other',metric.other))
                            # Bloch is stationary: don't duplicate it as a water result.
                            record.update(complex_fields('bloch_static_total',signal)
                                          if diffusion==0 else
                                          {k:'' for k in complex_fields('bloch_static_total',0j)})
                            records.append(record)
                    np.savez_compressed(folder/f'bloch_b1{b1}_b0{b0:g}.npz',
                                        signal=bloch['signal'],t_adc=bloch['t_adc'],
                                        adc_sizes=bloch['adc_sizes'])
            print(f'Validated {name}, phase {phase}',flush=True)
    output = ROOT/'docs/data'
    output.mkdir(exist_ok=True)
    with (output/'scanner_v17_validation.csv').open('w',newline='',encoding='utf-8') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    summary = dict(conditions=len(records)//8,echo_records=len(records),
                   max_closure_relative_error=max(x['closure_relative_error'] for x in records),
                   tensors=tensor_summary,echo8={})
    for name,_,_ in variants:
        rows = [x for x in records if x['variant']==name and x['echo']==8 and x['D_mm2_s']==0]
        summary['echo8'][name] = dict(
            static_bloch_median=float(np.median([x['bloch_static_total_abs'] for x in rows])),
            static_bloch_min=float(min(x['bloch_static_total_abs'] for x in rows)),
            rows=rows)
    summary['provenance'] = dict(
        scanner_compiled=False,hardware_qualified=False,
        settings=dict(n=args.n,seed=1,rf_dt_s=1e-5,b1=[.8,1.],b0_Hz=args.b0,
                      phase_deg=[0,45,90],D_mm2_s=[0,.001],T1_s=1.5,T2_s=.08,T2prime_s=.03),
        model_limits=['Bloch has static spins and inferred finite sinc RF',
                      'PDG has instantaneous RF and a box voxel',
                      'MRzero longitudinal diffusion convention lacks transverse (2*pi)^2 factor',
                      'coherent excitation offsets are a phase-error surrogate, not simulated motion',
                      'full b tensor is for primary pathway; acquired signal mixes pathways',
                      'gradient limits default to existing model envelope, not verified scanner ratings'],
        versions={k:importlib.metadata.version(k) for k in ['numpy','pypulseq','MRzeroCore','torch']},
        sha256={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
                for path in [*sorted((ROOT/'scanner').glob(stem+'*.pp*')),
                             ROOT/'dwfse/generate.py',ROOT/'dwfse/crushers.py',
                             ROOT/'dwfse/btensor.py',ROOT/'dwfse/pathways.py',
                             ROOT/'dwfse/simulate.py',Path(__file__).resolve()]})
    (output/'scanner_v17_validation.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:summary[k] for k in ('conditions','echo_records','max_closure_relative_error')},indent=2))


if __name__ == '__main__':
    main()
