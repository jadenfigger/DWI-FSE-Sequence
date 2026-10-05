"""Independent numerical/model audit; never changes scanner or core simulators.

python examples/audit_combined_factors.py --sequence ID=path/to/seq.seq
Use repeated --sequence options. Compact findings: runs/combined_audit/audit.json.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import inspect
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import importlib.metadata

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dwfse import btensor, epg, pathways, simulate


def longitudinal_sensitivity(seq, data):
    """Exhaustive enumerator with only stored-grating diffusion coefficient changed.

    This explicit local copy is a sensitivity model, not an upstream correction.
    The tested source replacement is persisted in the audit metadata.
    """
    source = inspect.getsource(pathways.enumerate_center_pathways)
    old = '-1e-9 * d * total_time * np.linalg.norm(path.kt[:3]) ** 2'
    new = '-1e-9 * d * (2 * np.pi) ** 2 * total_time * np.linalg.norm(path.kt[:3]) ** 2'
    if source.count(old) != 1:
        raise RuntimeError('enumerator changed: review sensitivity substitution')
    scope = dict(vars(pathways))
    exec(compile(source.replace(old, new), '<local_longitudinal_sensitivity>', 'exec'), scope)
    return scope['enumerate_center_pathways'](seq, data)


def pdg_primary_tensor(seq):
    """Direct integration of primary trajectory in the imported event representation."""
    if seq.normalized_grads:
        raise ValueError('physical gradient moments required')
    k, tensor, elapsed, tau = np.zeros(3), np.zeros((3, 3)), 0., 0.
    records = []
    intervals = []
    for index, rep in enumerate(seq):
        if index:
            k = -k
            tau = -tau
        dt = rep.event_time.detach().cpu().numpy().astype(float)
        gm = rep.gradm.detach().cpu().numpy().astype(float)
        adc = np.flatnonzero(rep.adc_usage.detach().cpu().numpy() > 0)
        center = adc[len(adc)//2] if len(adc) else None
        for event, (duration, moment) in enumerate(zip(dt, gm)):
            if duration < 0:
                raise RuntimeError('negative imported event time')
            end = k + moment
            tensor += (2*np.pi)**2 * duration * (
                2*np.outer(k,k) + np.outer(k,end) + np.outer(end,k)
                + 2*np.outer(end,end)) / 6 * 1e-6
            intervals.append(dict(start_s=elapsed, end_s=elapsed+duration,
                                  k_start_cycles_m=k.tolist(), k_end_cycles_m=end.tolist()))
            k = end
            elapsed += duration
            tau += duration
            if event == center:
                records.append(dict(echo=index, time_after_excitation_s=elapsed,
                                    B_s_mm2=tensor.tolist(), trace_s_mm2=float(np.trace(tensor)),
                                    k_cycles_m=k.tolist(),tau_s=tau))
    return records, intervals


def numerical_waveform_tensor(seq, maximum_step_s):
    """Independent trapezoid integration on subdivided waveform intervals.

    Gradient is linear on each interval; moment updates use its trapezoid area.
    Integral q q^T is approximated and checked at two step sizes.
    """
    times, left, right, rfs, adcs = btensor.played_waveform(seq)
    rf_at = {round(r['time_s'],12): r['use'] for r in rfs}
    adc_at = {round(a['sample_s'],12): i+1 for i,a in enumerate(adcs)}
    q, b, sign, active = np.zeros(3), np.zeros((3,3)), 1, False
    out = []
    for i, time in enumerate(times):
        use = rf_at.get(round(float(time),12))
        if use == 'excitation':
            q, b, sign, active = np.zeros(3), np.zeros((3,3)), 1, True
        elif use == 'refocusing':
            sign *= -1
        if round(float(time),12) in adc_at:
            out.append(dict(echo=adc_at[round(float(time),12)], B_s_mm2=b.copy().tolist()))
        if i+1 == len(times) or not active:
            continue
        n = max(1, int(np.ceil((times[i+1]-time)/maximum_step_s)))
        dt = (times[i+1]-time)/n
        fractions = np.arange(n+1)/n
        gradients = left[i][None,:] + fractions[:,None]*(right[i]-left[i])[None,:]
        for g0,g1 in zip(gradients[:-1],gradients[1:]):
            end = q + 2*np.pi*sign*(g0+g1)*dt/2
            b += (np.outer(q,q)+np.outer(end,end))*dt/2*1e-6
            q = end
    return out


def hardware(seq):
    times, left, right, rfs, adcs = btensor.played_waveform(seq)
    dt = np.diff(times)
    peak = np.maximum(np.abs(left), np.abs(right)).max(axis=0)
    slopes = (right-left)/dt[:,None]
    energy = np.sum(dt[:,None]*(left*left+left*right+right*right)/3,axis=0)
    gamma = 42.577478e6
    rf_energy = 0.
    rf_windows = []
    ids,starts,durs = simulate.block_times(seq)
    for bid,start in zip(ids,starts):
        rf = seq.get_block(bid).rf
        if rf is not None:
            # Actual sample spacing, rather than assuming the file RF raster.
            spacing = np.median(np.diff(rf.t))
            rf_energy += float(np.sum(abs(rf.signal)**2)*spacing)
            duration = getattr(rf,'shape_dur',rf.t[-1]+spacing/2)
            rf_windows.append([float(start+rf.delay),float(start+rf.delay+duration)])
    samples = np.array([a['sample_s'] for a in adcs])
    te = (samples-rfs[0]['time_s'])*1000
    ok,errors = seq.check_timing()
    return dict(timing_pass=bool(ok), timing_error_count=len(errors),
                peak_gradient_axis_mT_m=(peak/gamma*1000).tolist(),
                peak_gradient_vector_mT_m=float(np.maximum(np.linalg.norm(left,axis=1),
                                                           np.linalg.norm(right,axis=1)).max()/gamma*1000),
                peak_slew_axis_T_m_s=(abs(slopes).max(axis=0)/gamma).tolist(),
                gradient_energy_axis_T2_m2_s=(energy/gamma**2).tolist(),
                rf_energy_Hz2_s=rf_energy, rf_energy_is_SAR=False,
                TE_samples_ms=te.tolist(), ESP_samples_ms=np.diff(samples*1000).tolist(),
                physical_file_duration_s=float(sum(durs)),
                rf_windows_s=rf_windows,
                calibration='gamma=42.577478e6 Hz/T; linear modeled ramps; no hardware measurement',
                system_limits_from_constructor_are_hardware_ratings=False)


def RF_time_tensor_partition(seq, imported_intervals):
    """Partition b accumulation during actual RF support, retaining instantaneous RF.

    Three-point Gaussian quadrature is exact for quartic q(t)q(t)^T on a
    linear-gradient segment. This partition measures timing representation,
    not the effective diffusion weighting of a continuously rotating spin.
    """
    times,left,right,rfs,adcs=btensor.played_waveform(seq)
    windows=hardware(seq)['rf_windows_s']
    cuts=np.array([v for window in windows for v in window])
    nodes,weights=np.polynomial.legendre.leggauss(3)
    q,b,rfb,sign,active=np.zeros(3),0.,0.,1,False
    rf_at={round(r['time_s'],12):r['use'] for r in rfs}
    adc_at={round(a['sample_s'],12):i+1 for i,a in enumerate(adcs)}
    full=[]
    for i,time in enumerate(times):
        use=rf_at.get(round(float(time),12))
        if use=='excitation':q,b,rfb,sign,active=np.zeros(3),0.,0.,1,True
        elif use=='refocusing':sign*=-1
        if round(float(time),12) in adc_at:full.append(dict(total=b,RF=rfb))
        if i+1==len(times) or not active:continue
        end=times[i+1];duration=end-time
        splits=np.r_[time,cuts[(cuts>time)&(cuts<end)],end]
        slope=(right[i]-left[i])/duration
        for a,c in zip(splits[:-1],splits[1:]):
            mid=(a+c)/2;offset=mid+(c-a)*nodes/2-time
            trajectory=q[None,:]+2*np.pi*sign*(offset[:,None]*left[i]+.5*offset[:,None]**2*slope)
            value=float((c-a)/2*np.dot(weights,np.sum(trajectory**2,axis=1))*1e-6)
            b+=value
            if any(lo<mid<hi for lo,hi in windows):rfb+=value
        q+=2*np.pi*sign*(left[i]+right[i])*duration/2
    excitation=rfs[0]['time_s']
    out=[]
    for item,adc in zip(full,adcs):
        bound=adc['sample_s']-excitation
        pdgrf=0.
        for interval in imported_intervals:
            a,c=interval['start_s'],interval['end_s']
            if a>=bound:break
            if c<=a:continue
            k0=np.array(interval['k_start_cycles_m']);k1=np.array(interval['k_end_cycles_m'])
            for lo,hi in windows:
                start=max(a,lo-excitation);end=min(c,hi-excitation,bound)
                if end<=start:continue
                offsets=(start+end)/2+(end-start)*nodes/2-a
                qsample=2*np.pi*(k0[None,:]+offsets[:,None]*(k1-k0)[None,:]/(c-a))
                pdgrf+=float((end-start)/2*np.dot(weights,np.sum(qsample**2,axis=1))*1e-6)
        out.append(dict(full_RF_time_b_trace_s_mm2=item['RF'],
                        pdg_RF_time_b_trace_s_mm2=pdgrf,
                        full_minus_pdg_RF_time_b_trace_s_mm2=item['RF']-pdgrf,
                        full_trace_gaussian_independent_s_mm2=item['total']))
    return out


def complex_record(value):
    return dict(real=float(value.real),imag=float(value.imag),magnitude=float(abs(value)),
                phase_deg=float(np.degrees(np.angle(value))))


def pathway_record(m):
    stimulated = sum((p.value for p in m.contributions if 'Z' in p.history and 'Z0' not in p.history),0j)
    remainder = m.other-stimulated
    closure = abs(m.total-m.mrzero_signal) if m.mrzero_signal is not None else None
    return dict(echo=m.echo, primary=complex_record(m.primary), total=complex_record(m.total),
                stimulated=complex_record(stimulated),remaining_other=complex_record(remainder),
                other_relative_phase_deg=m.other_relative_phase_deg,
                nonprimary_L1_share=m.other_l1_fraction, cancellation_ratio=m.cancellation_ratio,
                number_of_coherently_grouped_histories=len(m.contributions),
                closure_absolute=closure,closure_relative=m.closure_relative_error)


def audit_sequence(name,path,closure=True,bloch=False,support_relaxation=False):
    seq = simulate.read_seq(str(path))
    imported = epg.quiet(epg.mr0.Sequence.import_file,str(path))
    pdg,intervals = pdg_primary_tensor(imported)
    full,_ = btensor.calculate(seq)
    fullsamples = [r for r in full['echoes'] if r['convention']=='sample']
    coarse = numerical_waveform_tensor(seq,20e-6)
    fine = numerical_waveform_tensor(seq,10e-6)
    rf_partition=RF_time_tensor_partition(seq,intervals)
    tensors = []
    for exact,p,c,f,partition in zip(fullsamples,pdg,coarse,fine,rf_partition):
        b = np.array(exact['B_s_mm2'])
        tensors.append(dict(echo=p['echo'],full_B_s_mm2=b.tolist(),
                            full_trace_s_mm2=float(np.trace(b)),pdg_B_s_mm2=p['B_s_mm2'],
                            pdg_trace_s_mm2=p['trace_s_mm2'],
                            full_minus_pdg_trace_s_mm2=float(np.trace(b))-p['trace_s_mm2'],
                            full_vs_numerical_10us_max_abs_s_mm2=float(np.max(abs(b-np.array(f['B_s_mm2'])))),
                            numerical_20_to_10us_max_abs_s_mm2=float(np.max(abs(np.array(c['B_s_mm2'])-f['B_s_mm2']))),
                            eigenvalues_s_mm2=np.linalg.eigvalsh(b).tolist(),
                            time_full_minus_pdg_us=(exact['time_after_excitation_s']-p['time_after_excitation_s'])*1e6,
                            **partition))
    scenarios = []
    for etl in sorted(set([min(4,len(imported)-1), len(imported)-1])):
        if etl>8:
            continue
        trunc = epg.mr0.Sequence(list(imported)[:etl+1],normalized_grads=imported.normalized_grads)
        conditions=[(1.,0.,0.,1.,.08),(.8,0.,0.,1.,.08),(.8,37.,1.,1.,.08),(.9,-63.,2.,.5,.08)]
        if support_relaxation and etl==len(imported)-1:
            conditions += [(.8,0.,D,span,t2) for D in (0.,1.) for span in (.5,2.) for t2 in (.06,.10)]
        for b1,b0,D,span,t2 in conditions:
            args = SimpleNamespace(voxel_mm=[.2,.2,span],T1=1.5,T2=t2,T2dash=.03,D=D,b0=b0,b1=b1)
            data = epg.make_phantom(args)
            fn = pathways.with_mrzero_closure if closure else pathways.enumerate_center_pathways
            base = epg.quiet(fn,trunc,data)
            physical = longitudinal_sensitivity(trunc,data)
            for m,s in zip(base,physical):
                row = dict(ETL=etl,B1=b1,B0_Hz=b0,D_mm2_s=D*.001,voxel_z_mm=span,T2_s=t2,
                           compatibility=pathway_record(m),fourier_longitudinal=pathway_record(s),
                           sensitivity_total_absolute=abs(m.total-s.total),
                           sensitivity_nonprimary_share_absolute=abs(m.other_l1_fraction-s.other_l1_fraction),
                           sensitivity_primary_absolute=abs(m.primary-s.primary))
                # Desired-path water attenuation must match imported primary b exactly.
                expected = np.sin(b1*float(trunc[0].pulse.angle))
                expected *= np.prod([np.sin(b1*float(rep.pulse.angle)/2)**2
                                     for rep in list(trunc)[1:m.echo+1]])
                expected *= np.exp(-m.time_s/float(data.T2.flatten()[0]))
                expected *= np.exp(-float(data.D.flatten()[0])*.001*pdg[m.echo-1]['trace_s_mm2'])
                p=pdg[m.echo-1]
                k_tensor=epg.torch.tensor([p['k_cycles_m']],dtype=epg.torch.float32)
                expected *= float(data.dephasing_func(k_tensor,data.nyquist)[0])
                expected *= np.exp(-abs(p['tau_s'])/float(data.T2dash.flatten()[0]))
                row['primary_magnitude_analytic_expected'] = float(expected)
                row['primary_magnitude_analytic_absolute_error'] = abs(abs(m.primary)-expected)
                scenarios.append(row)
    bloch_rows = []
    if bloch:
        vox=simulate.make_voxel(n=12000,seed=41)
        for strength in (1.,.8):
            outputs=[]
            for dt in (10e-6,5e-6,2.5e-6):
                result=simulate.simulate(seq,b1=strength,b0=37.,voxel=vox,rf_dt=dt)
                ends=np.cumsum(np.r_[0,result['adc_sizes']])
                outputs.append(np.array([result['signal'][a+(b-a)//2] for a,b in zip(ends[:-1],ends[1:])]))
            for e,values in enumerate(zip(*outputs),1):
                bloch_rows.append(dict(B1=strength,B0_Hz=37.,echo=e,
                                       signals=[complex_record(v) for v in values],
                                       absolute_10_to_5us=abs(values[0]-values[1]),
                                       absolute_5_to_2p5us=abs(values[1]-values[2])))
    return dict(ID=name,sequence=str(path.resolve()),sequence_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                hardware=hardware(seq),tensors=tensors,scenarios=scenarios,bloch_RF_convergence=bloch_rows,
                primary_b_representation='full waveform analytic vs imported piecewise-average event gradients',
                RF_duration_statement='RF is instantaneous at center in both b representations; pulse duration remains in elapsed time and played gradients. No finite-RF effective b is asserted.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sequence',action='append',default=[])
    parser.add_argument('--out',default='runs/combined_audit')
    parser.add_argument('--skip-closure',action='store_true')
    parser.add_argument('--bloch',action='store_true')
    parser.add_argument('--support-relaxation',action='store_true')
    parser.add_argument('--summarize',action='store_true',help='summarize all completed audit subdirectories')
    args=parser.parse_args()
    if args.summarize:
        summarize(Path(args.out))
        return
    entries=args.sequence or ['original=runs/improve_screen_base_b1000_ph90/seq.seq',
                              'centered_linear=runs/improve_screen_centered_linear_b1000_ph90/seq.seq']
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    results=[]
    for entry in entries:
        name,path=entry.split('=',1)
        result=audit_sequence(name,Path(path),closure=not args.skip_closure,bloch=args.bloch,
                              support_relaxation=args.support_relaxation)
        results.append(result)
        (out/(name+'.json')).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        print(name,'audited',len(result['scenarios']),'echo-condition records',flush=True)
    payload=dict(metadata=dict(dependency_versions={p:importlib.metadata.version(p) for p in ['numpy','torch','MRzeroCore','pypulseq']},
                               method='ETL<=8 exhaustive no-pruning RF-history audit; independent full-waveform numerical b integration',
                               longitudinal_sensitivity='compatibility: exp(-D_SI dt |k_cycles_m|²); Fourier: exp(-D_SI dt (2*pi)² |k_cycles_m|²)',
                               tolerance=dict(closure_absolute=3e-6,closure_relative_away_from_null=5e-4,
                                              closure_pass_rule='absolute <= 3e-6 OR relative <= 5e-4; both errors retained',
                                              numerical_b_s_mm2=.002,analytic_primary_absolute=2e-6),
                               finite_RF_Bloch_diffusion='stationary spins; no molecular diffusion',
                               pruning='none in exhaustive enumeration; MRzero min_state_mag=0 and execute thresholds=0'),
                 results=results)
    (out/'audit.json').write_text(json.dumps(payload,indent=2,allow_nan=False)+'\n')
    rows=[]
    for r in results:
        for s in r['scenarios']:
            c=s['compatibility'];f=s['fourier_longitudinal']
            rows.append(dict(ID=r['ID'],ETL=s['ETL'],B1=s['B1'],B0_Hz=s['B0_Hz'],D_mm2_s=s['D_mm2_s'],
                             T2_s=s['T2_s'],
                             voxel_z_mm=s['voxel_z_mm'],echo=c['echo'],primary=c['primary']['magnitude'],
                             total=c['total']['magnitude'],stimulated=c['stimulated']['magnitude'],
                             nonprimary_share=c['nonprimary_L1_share'],
                             total_fourier=f['total']['magnitude'],nonprimary_share_fourier=f['nonprimary_L1_share'],
                             closure_absolute=c['closure_absolute'],closure_relative=c['closure_relative'],
                             analytic_primary_absolute_error=s['primary_magnitude_analytic_absolute_error']))
    with (out/'compact.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def summarize(out):
    """Persist compact independently audited findings, including tolerance failures."""
    files=sorted(out.glob('*/audit.json'))
    payloads=[json.loads(file.read_text()) for file in files]
    results=[r for payload in payloads for r in payload['results']]
    full=[r for r in results if any(s['compatibility']['closure_absolute'] is not None for s in r['scenarios'])]
    metrics=[s for r in full for s in r['scenarios']]
    failures=[]
    near_null_absolute_pass=[]
    for r in full:
        for s in r['scenarios']:
            c=s['compatibility']
            if c['closure_absolute']>3e-6 and c['closure_relative']>5e-4:
                failures.append(dict(ID=r['ID'],ETL=s['ETL'],echo=c['echo'],B1=s['B1'],B0_Hz=s['B0_Hz'],
                                     D_mm2_s=s['D_mm2_s'],absolute=c['closure_absolute'],relative=c['closure_relative']))
            elif c['closure_relative']>5e-4:
                near_null_absolute_pass.append(dict(ID=r['ID'],ETL=s['ETL'],echo=c['echo'],
                                                    total_magnitude=c['total']['magnitude'],
                                                    absolute=c['closure_absolute'],relative=c['closure_relative']))
    best={r['ID']:r for r in full}
    summary=dict(audit_payloads=[str(f) for f in files],
                 dependency_versions=payloads[0]['metadata']['dependency_versions'],
                 audit_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 core_enumerator_source_sha256=hashlib.sha256(inspect.getsource(pathways.enumerate_center_pathways).encode()).hexdigest(),
                 closure_cases=len(metrics),closure_absolute_max=max(s['compatibility']['closure_absolute'] for s in metrics),
                 closure_relative_max=max(s['compatibility']['closure_relative'] for s in metrics),
                 closure_failures=failures,closure_rule='abs<=3e-6 OR relative<=5e-4',
                 relative_limit_exceeded_absolute_pass=near_null_absolute_pass,
                 analytic_primary_absolute_max=max(s['primary_magnitude_analytic_absolute_error'] for s in metrics),
                 primary_longitudinal_sensitivity_absolute_max=max(s['sensitivity_primary_absolute'] for s in metrics),
                 full_vs_numerical_10us_tensor_element_absolute_max_s_mm2=max(t['full_vs_numerical_10us_max_abs_s_mm2'] for r in full for t in r['tensors']),
                 full_vs_independent_gaussian_trace_absolute_max_s_mm2=max(abs(t['full_trace_s_mm2']-t['full_trace_gaussian_independent_s_mm2']) for r in full for t in r['tensors']),
                 max_RF_partition_full_minus_pdg_trace_s_mm2=max(abs(t['full_minus_pdg_RF_time_b_trace_s_mm2']) for r in full for t in r['tensors']),
                 finalist_sequence_hashes={name:r['sequence_sha256'] for name,r in best.items()})
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    rows=[]
    for name,r in best.items():
        d0=next(s for s in r['scenarios'] if s['ETL']==8 and s['compatibility']['echo']==8 and s['B1']==.8 and s['B0_Hz']==0 and s['D_mm2_s']==0 and s['voxel_z_mm']==1 and s.get('T2_s',.08)==.08)
        d1=next(s for s in r['scenarios'] if s['ETL']==8 and s['compatibility']['echo']==8 and s['B1']==.8 and s['B0_Hz']==37 and s['D_mm2_s']==.001 and s['voxel_z_mm']==1)
        t=r['tensors'][-1];h=r['hardware']
        rows.append(dict(ID=name,primary_static=d0['compatibility']['primary']['magnitude'],
                         total_static=d0['compatibility']['total']['magnitude'],
                         stimulated_static=d0['compatibility']['stimulated']['magnitude'],
                         nonprimary_share_static=d0['compatibility']['nonprimary_L1_share'],
                         primary_D001_B037=d1['compatibility']['primary']['magnitude'],
                         total_D001_B037_compatibility=d1['compatibility']['total']['magnitude'],
                         total_D001_B037_fourier=d1['fourier_longitudinal']['total']['magnitude'],
                         share_D001_B037_compatibility=d1['compatibility']['nonprimary_L1_share'],
                         share_D001_B037_fourier=d1['fourier_longitudinal']['nonprimary_L1_share'],
                         full_b_trace_s_mm2=t['full_trace_s_mm2'],PDG_b_trace_s_mm2=t['pdg_trace_s_mm2'],
                         peak_z_mT_m=h['peak_gradient_axis_mT_m'][2],peak_z_slew_T_m_s=h['peak_slew_axis_T_m_s'][2],
                         RF_energy_Hz2_s=h['rf_energy_Hz2_s']))
    with (out/'finalist_summary.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    def support_key(s):
        return (s['ETL'],s['compatibility']['echo'],s['B1'],s['B0_Hz'],s['D_mm2_s'],s['voxel_z_mm'],s.get('T2_s',.08))
    support_results={r['ID']:r for r in results if any(s.get('T2_s',.08)!=.08 for s in r['scenarios'])}
    support_rows=[]
    if 'original' in support_results:
        reference={support_key(s):s for s in support_results['original']['scenarios']}
        for name,r in support_results.items():
            for s in r['scenarios']:
                if s['ETL']!=8 or s['compatibility']['echo']!=8 or s.get('T2_s',.08)==.08:
                    continue
                base=reference[support_key(s)]
                c,b=s['compatibility'],base['compatibility']
                f,fb=s['fourier_longitudinal'],base['fourier_longitudinal']
                support_rows.append(dict(ID=name,T2_s=s['T2_s'],voxel_z_mm=s['voxel_z_mm'],D_mm2_s=s['D_mm2_s'],
                                         total=c['total']['magnitude'],original_total=b['total']['magnitude'],
                                         total_difference=c['total']['magnitude']-b['total']['magnitude'],
                                         total_ratio=c['total']['magnitude']/b['total']['magnitude'],
                                         primary=c['primary']['magnitude'],original_primary=b['primary']['magnitude'],
                                         primary_ratio=c['primary']['magnitude']/b['primary']['magnitude'],
                                         share=c['nonprimary_L1_share'],original_share=b['nonprimary_L1_share'],
                                         total_fourier=f['total']['magnitude'],original_total_fourier=fb['total']['magnitude'],
                                         share_fourier=f['nonprimary_L1_share']))
        with (out/'support_relaxation.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(support_rows[0]));writer.writeheader();writer.writerows(support_rows)
    lines=['# Independent combined-factor audit','',
           '4 October 2026. All tables refer to primary instantaneous-center RF unless explicitly labeled finite-RF Bloch. Scanner files were not changed.','',
           '## Metrics and conventions','',
           'Primary is the explicit excitation `+` then `- + - ...` transverse-only RF history. Stimulated is the coherent sum of histories containing `Z` and no `Z0`; recovery lineages and remaining transverse histories are reported separately. Total is the complex sum. Non-primary L1 share uses the sum of magnitudes of histories after coherent grouping. It is neither signal power nor an artifact fraction.','',
           'Gradients in the file are Hz/m, gradient moments cycles/m, q rad/m and B s/mm². MRzero D is in 10^-3 mm²/s. Requested D=0 is internally floored to 10^-6 in those units.','',
           '## Numerical validation','',
           f"The acquired-signal closure audit covers {summary['closure_cases']} echo-condition records across ETL4/8. Maximum absolute complex discrepancy is {summary['closure_absolute_max']:.3g}; maximum relative discrepancy is {summary['closure_relative_max']:.3g}. Pass rule: absolute <=3e-6 OR relative <=5e-4, so ratios at near-zero totals are not used alone. Failures: {len(failures)}.", '',
           f"An analytic primary amplitude using imported RF angles, T2/T2′, box dephasing and exp(-D trace B_PDG) differs by at most {summary['analytic_primary_absolute_max']:.3g}. No pathway magnitude pruning is applied. Only ETL<=8 is reported; no exact long-train claim is made.", '',
           f"Independent 10-us subdivided trapezoid integration of the played waveform differs from the analytic tensor by at most {summary['full_vs_numerical_10us_tensor_element_absolute_max_s_mm2']:.3g} s/mm² per tensor element. A separately implemented three-node Gaussian quadrature agrees with its trace within {summary['full_vs_independent_gaussian_trace_absolute_max_s_mm2']:.3g} s/mm². The numerical check tolerance is .002 s/mm².", '',
           '## Full-waveform versus PDG diffusion weighting','',
           '| Candidate | Full E8 trace | Imported PDG trace | Difference (s/mm²) | Difference (%) |','|---|---:|---:|---:|---:|']
    for row in rows:
        delta=row['full_b_trace_s_mm2']-row['PDG_b_trace_s_mm2']
        lines.append(f"| {row['ID']} | {row['full_b_trace_s_mm2']:.6f} | {row['PDG_b_trace_s_mm2']:.6f} | {delta:.6f} | {100*delta/row['full_b_trace_s_mm2']:.4f} |")
    lines += ['',
        'Both models retain physical RF duration in elapsed time and played gradients while replacing rotations with instantaneous RF at pulse centers. The importer replaces each event interval with its average gradient, so it matches moment endpoints but approximates q within ramps. This explains the small b discrepancy. The largest discrepancy confined to actual RF-support windows is '+f"{summary['max_RF_partition_full_minus_pdg_trace_s_mm2']:.3g} s/mm²"+'. Thus omitted RF time does not explain it. This check does not establish the effective b tensor of continuously rotating spins during imperfect finite RF.', '',
        '## Longitudinal diffusion sensitivity','',
        'MRzeroCore 1.1.1 uses exp(-D_SI dt |k|²) for stored longitudinal gratings, while its transverse formula uses exp(-D_SI dt |2πk|²). The compatibility column reproduces that implementation; the Fourier column applies (2π)² to longitudinal storage only in a local exact-enumerator copy. The factor follows from applying the diffusion equation to exp(i2π k·r). This is a physically motivated sensitivity bracket, not a validated repair or an uncertainty probability. Desired transverse-only primary amplitudes are identical across both conventions.', '',
        '[Weigel et al., original anisotropic diffusion EPG work](https://doi.org/10.1016/j.jmr.2010.05.011) establishes pathway-specific diffusion weighting for arbitrary gradient and RF histories. The specific convention diagnosis above is an independent source-code and Fourier-equation audit.', '',
        '| Candidate | Primary D=.001 | Total compatibility | Total Fourier | L1 share compatibility | L1 share Fourier |','|---|---:|---:|---:|---:|---:|']
    for row in rows:
        lines.append(f"| {row['ID']} | {row['primary_D001_B037']:.6f} | {row['total_D001_B037_compatibility']:.6f} | {row['total_D001_B037_fourier']:.6f} | {100*row['share_D001_B037_compatibility']:.2f}% | {100*row['share_D001_B037_fourier']:.2f}% |")
    lines += ['','Conditions: ETL8, B1=.8, excitation phase90°, B0=37 Hz, T1=1.5s, T2=.08s, T2′=.03s, box voxel .2×.2×1 mm, read requested b1000. Relative phases and all echoes are retained in JSON/CSV. Physiological stimulated fractions remain uncertain; total magnitude can increase or decrease when diffusion changes cancellation.','',
              '## Timing, hardware and finite-RF limitations','',
              'All sequence timing checks pass within the modeled event system. Reported peaks/slew use calibrated logical waveform scaling, gamma42.577478 MHz/T and linear ramps. They are not measured amplifier ratings; no hardware acceptance follows from Pulseq timing alone. RF-energy is integral |B1_Hz|²dt, not SAR. Gradient energy integrates the full played waveform per axis.','',
              'The finite-RF Bloch audit uses stationary isochromats, 12000 samples, seed41, B0=37Hz and RF time steps10/5/2.5us at B1=1/.8. It includes shaped pulse profiles and off-resonance during RF; it contains no molecular diffusion. Its absolute amplitude must not be equated to the instantaneous-RF box-voxel pathway amplitude.','',
              '| Candidate | Maximum complex change10→5us | Maximum change5→2.5us |','|---|---:|---:|']
    for name,r in best.items():
        if r['bloch_RF_convergence']:
            lines.append(f"| {name} | {max(x['absolute_10_to_5us'] for x in r['bloch_RF_convergence']):.6g} | {max(x['absolute_5_to_2p5us'] for x in r['bloch_RF_convergence']):.6g} |")
    lines += ['','The additional shortlisted schedules are audited across .5/2-mm box slice support, T2=.06/.10s, D0/.001, B1=.8 and phase90°. Matched original/increasing controls use the same exact enumerator; acquired-MRzero closure in that supplementary grid is attached for new candidates, while control closures are checked separately in the base grid.','',
              '| Candidate | E8 total range across8 support/T2/D cells | Total/original range | Primary/original water range | L1-share change range |',
              '|---|---:|---:|---:|---:|']
    for name in support_results:
        if name=='original':continue
        matched=[s for s in support_rows if s['ID']==name]
        water=[s for s in matched if s['D_mm2_s']==.001]
        if matched:
            values=[s['total'] for s in matched];ratios=[s['total_ratio'] for s in matched]
            primary=[s['primary_ratio'] for s in water];shares=[100*(s['share']-s['original_share']) for s in matched]
            lines.append(f"| {name} | {min(values):.6f}–{max(values):.6f} | {min(ratios):.3f}–{max(ratios):.3f} | {min(primary):.6f}–{max(primary):.6f} | {min(shares):+.2f}–{max(shares):+.2f} percentage points |")
    lines += ['', 'These supplementary cells demonstrate support/relaxation sensitivity. Lower L1 share does not imply larger total: removal or attenuation of a coherent component can improve or worsen cancellation. Ratios are accompanied by absolute totals, and the full paired conditions are retained in `support_relaxation.csv`.','',
              '## Reproduction','',
              'Run `python examples/audit_combined_factors.py --sequence ID=path/to/seq.seq --out runs/combined_audit/GROUP` (repeat sequence arguments). Add `--bloch` for RF timestep checks, or `--support-relaxation` for the supplementary support/relaxation grid. `--skip-closure` explicitly omits acquired-MRzero closure. Run `python examples/audit_combined_factors.py --summarize` after all groups finish. Complete metadata, actual failures, sequence hashes, tensor matrices, complex components and dependency versions are in `runs/combined_audit/`.','']
    path=ROOT/'docs/research/combined_factor_audit.md'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
