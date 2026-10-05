"""Staged, cached combined-factor DW-FSE study (run from repository root).

Finite-duration RF Bloch totals and exact instantaneous-RF pathway decomposition
are separate models. Pathway groups follow compare_echo_snapshots.category.
All tensors describe the primary instantaneous-RF pathway, not mixed signal.
"""
import argparse
import csv
import hashlib
import importlib.metadata
import os
import json
import sys
import subprocess
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

import matplotlib
matplotlib.use('Agg')
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dwfse import btensor, epg, generate, pathways, simulate
from examples.improve_ppl import BASE
from examples.compare_echo_snapshots import category

OUT = ROOT / 'docs/data'
RUNS = ROOT / 'runs/combined_factor_study'
VERSION = 'combined-v2'
START_TIME=time.perf_counter()
UP = [1, 1, 1.4, 1.8, 2.2, 2.6, 3, 3.4]
DIRECTIONS = {'read': [1000, 0, 0], 'slice': [0, 0, 1000],
              'phase': [0, 1000, 0], 'oblique': [577, 577, 577],
              'held_oblique': [707, 500, 500]}


def configurations():
    c = {}
    def add(name, scales=None, centered=False, **extra):
        c[name] = dict(scanner_version='1.6', sim_fix_refocus_centering=centered,
                       sim_train_crusher_scales=scales or [1]*8, **extra)
    add('original')
    add('centering', centered=True)
    add('increasing', UP)
    add('increasing_centering', UP, True)
    alt = [(-1)**k for k in range(8)]
    ia = [v*s for v,s in zip(UP, alt)]
    add('alternating', alt)
    add('alternating_centering',alt,True)
    add('increasing_alternating', ia)
    add('increasing_alternating_centering', ia, True)
    weak=[1,1,1.2,1.4,1.6,1.8,2,2.2]
    add('weak_increasing_centering',weak,True)
    add('weak_increasing_alternating_centering',[v*s for v,s in zip(weak,alt)],True)
    add('decreasing', [1, 3.4, 3, 2.6, 2.2, 1.8, 1.4, 1])
    add('high_low', [1,3.4,1,3.4,1,3.4,1,3.4])
    add('high_low_alternating', [1,-3.4,1,-3.4,1,-3.4,1,-3.4])
    add('high_low_permutation', [1,1,3.4,1.4,3,1.8,2.6,2.2])
    add('high_low_permutation_alternating', [1,-1,3.4,-1.4,3,-1.8,2.6,-2.2])
    add('high_low_permutation_alternating_centering', [1,-1,3.4,-1.4,3,-1.8,2.6,-2.2],True)
    ramp = [1]+(1+2.4*np.linspace(0,1,7)**1.5).tolist()
    add('ramp_modulated', [1]+[float(v*(1 if k%2==0 else .8)) for k,v in enumerate(ramp[1:])])
    add('quadratic', [1]+(1+2.4*np.linspace(0,1,7)**2).tolist())
    add('geometric', [1]+np.geomspace(1,3.4,7).tolist())
    rng = np.random.default_rng(20261004)
    irregular = [1]+rng.uniform(1,3.4,7).tolist()
    irregular[4] = 3.4
    add('irregular_seeded', irregular)
    add('high_low_energy_matched', [1,3.4,1,3.4,1,3.4,1,3.4], energy_match=True)
    add('irregular_energy_matched', irregular, energy_match=True)
    for stem, scales, centered in [('original',None,False), ('increasing',UP,False), ('increasing_centering',UP,True), ('inc_alt',ia,False),
                                   ('inc_alt_center',ia,True)]:
        for label, offsets in [('rf180',[0,180]*4), ('rf90_exploratory',[0,90]*4)]:
            add(stem+'_'+label, scales, centered, sim_refocus_phase_offsets_deg=offsets)
    for stem, scales, centered in [('original',None,False), ('inc_alt_center',ia,True)]:
        add(stem+'_flip160', scales, centered, sim_refocus_flip_deg=160)
        add(stem+'_flip_train', scales, centered,
            refocus_train_deg=[180,170,160,150,145,150,160,170])
    for stem,scales,centered in [('original',None,False),('increasing',UP,False),('increasing_centering',UP,True)]:
        add(stem+'_taper',scales,centered,refocus_train_deg=[180,180,175,170,165,160,155,150])
    # 500 us crushers are moment-compensated including their 200-us ramps.
    # First RF/crusher are held fixed by retaining diff_tcrush=1000.
    for stem, scales, centered in [('original',None,False),('inc_alt_center',ia,True)]:
        add(stem+'_duration500', scales, centered, tcrush=500,
            crush_amp=round(5482*(1000+200)/(500+200)))
    return c


CONFIGS = configurations()
MATCH_CACHE={}


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:16]


def gradient_energy(seq):
    times,left,right,_,_ = btensor.played_waveform(seq)
    dt=np.diff(times)
    return float(np.sum(dt[:,None]*(left**2+left*right+right**2)/3))


def build(overrides, train=None):
    seq,c,d,log=generate.build_sequence(generate.load_params(overrides=overrides),reduced=True)
    if train:
        k=0
        for bid in list(seq.block_events):
            block=seq.get_block(bid)
            if block.rf is not None and block.rf.use == 'refocusing':
                block.rf.signal *= train[k]/float(c.sim_refocus_flip_deg)
                # A new RF object must not reuse a cached library identifier.
                if hasattr(block.rf,'id'):
                    del block.rf.id
                seq.set_block(bid, block)
                k+=1
        if k != len(train):
            raise ValueError('isolated RF train length differs from generated RF count')
    ok,errors=seq.check_timing()
    if not ok:
        raise RuntimeError(str(errors))
    return seq,c,d


def sequence(name, b, direction, phase, etl=8):
    spec=dict(CONFIGS[name])
    match=spec.pop('energy_match',False)
    train=spec.pop('refocus_train_deg',None)
    overrides=dict(BASE, **spec)
    xyz=DIRECTIONS[direction]
    overrides.update(views_per_seg=etl, no_views=2*etl, sim_reduced_rows=[int(b>0)],
        acq_x=[xyz[0]]*2, acq_y=[xyz[1]]*2, acq_z=[xyz[2]]*2,
        sim_excitation_phase_deg=phase)
    if etl != 8:
        vals=spec['sim_train_crusher_scales']
        tail=np.interp(np.linspace(0,6,etl-1),np.arange(7),np.abs(vals[1:]))
        alternating = any(v<0 for v in vals)
        overrides['sim_train_crusher_scales']=[1]+[float(v*(-1 if alternating and k%2==0 else 1)) for k,v in enumerate(tail)]
        if spec.get('sim_refocus_phase_offsets_deg'):
            overrides['sim_refocus_phase_offsets_deg']=(spec['sim_refocus_phase_offsets_deg']*3)[:etl]
        if train:
            train=[180]+np.interp(np.linspace(0,6,etl-1),np.arange(7),train[1:]).tolist()
    if match:
        matchkey=digest(overrides)
        resolved=RUNS/'energy_matches'/f'{matchkey}.json'
        if matchkey in MATCH_CACHE:
            overrides['sim_train_crusher_scales']=MATCH_CACHE[matchkey]
            match=False
        elif resolved.exists():
            overrides['sim_train_crusher_scales']=json.loads(resolved.read_text())
            MATCH_CACHE[matchkey]=overrides['sim_train_crusher_scales']
            match=False
    if match:
        # Match full played integral G^2 to increasing ramp at the same geometry.
        target=dict(overrides, sim_train_crusher_scales=UP)
        target.pop('energy_match',None)
        target_seq,_,_=build(target)
        desired=gradient_energy(target_seq)
        raw=overrides['sim_train_crusher_scales']
        lo,hi=.1,1.6
        for _ in range(14):
            mult=(lo+hi)/2
            overrides['sim_train_crusher_scales']=[1]+[v*mult for v in raw[1:]]
            candidate,_,_=build(overrides)
            if gradient_energy(candidate)>desired: hi=mult
            else: lo=mult
        MATCH_CACHE[matchkey]=overrides['sim_train_crusher_scales']
        dump(resolved,overrides['sim_train_crusher_scales'])
    settings=dict(version=VERSION, overrides=overrides, refocus_train_deg=train)
    seqid=digest(settings)
    folder=RUNS / 'sequences' / seqid
    if not (folder/'seq.seq').exists():
        seq,c,d=build(overrides,train)
        folder.mkdir(parents=True,exist_ok=True)
        seq.write(str(folder/'seq.seq'))
        dump(folder/'settings.json',settings)
        dump(folder/'params.json',generate.params_dict(c))
        (folder/'generation.txt').write_text(generate.report(c,d)+'\ncheck_timing PASS\n')
        tensors,(times,left,right)=btensor.calculate(seq)
        dt=np.diff(times)
        rfenergy=0
        flips=[]
        for bid in seq.block_events:
            rf=seq.get_block(bid).rf
            if rf is not None:
                rfenergy+=float(np.sum(abs(rf.signal)**2)*seq.rf_raster_time)
                flips.append(float(abs(np.sum(rf.signal)*seq.rf_raster_time)*360))
        samples=[e for e in tensors['echoes'] if e['convention']=='sample']
        centers=np.array([e['time_after_excitation_s'] for e in samples])
        gamma=float(c.hw_gamma_hz_per_t)
        hardware=dict(seqid=seqid, timing_pass=True, TE_ms=float(centers[0]*1000),
            ESP_ms=float(np.median(np.diff(centers))*1000), TR_s=float(seq.duration()[0]),
            peak_gradient_mT_m=float(max(np.max(abs(left)),np.max(abs(right)))/gamma*1000),
            peak_slew_T_m_s=float(np.max(abs(right-left)/dt[:,None])/gamma),
            gradient_squared_Hz2_m2_s=gradient_energy(seq),
            rf_squared_Hz2_s=rfenergy, refocus_nominal_flip_deg=flips[1:],
            crusher_amplitudes_DAC=d.train_crusher_amplitudes_dac,
            gradient_limit_mT_m=float(seq.system.max_grad/gamma*1000),
            slew_limit_T_m_s=float(seq.system.max_slew/gamma),
            RF_energy_is_not_SAR=True)
        dump(folder/'btensor.json',tensors)
        dump(folder/'hardware.json',hardware)
    return simulate.read_seq(str(folder/'seq.seq')),folder,seqid


def table(rows,path):
    if not rows: return
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.'+str(os.getpid())+'.tmp')
    with temporary.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader();w.writerows(rows)
    for attempt in range(20):
        try:temporary.replace(path);break
        except OSError:
            if attempt==19:raise
            time.sleep(.1)


def merge_table(rows,path):
    old=[]
    if path.exists():
        with path.open(newline='',encoding='utf-8') as f: old=list(csv.DictReader(f))
    merged={str(r['case_id'])+'_'+str(r['echo']):r for r in old}
    merged.update({str(r['case_id'])+'_'+str(r['echo']):r for r in rows})
    for row in merged.values():
        row['actual_excitation_phase_deg']=round(float(row['phase'])/.225)*.225
    table(list(merged.values()),path)


def common(stage,name,b,direction,phase,b1,b0,etl,seqid,caseid):
    return dict(stage=stage, variant=name, b=b, direction=direction, phase=phase,
                b1=b1,b0=b0,etl=etl,seqid=seqid,case_id=caseid)


def finite(stage,name,b,direction,phase,b1,b0,etl=8,n=4096,seed=1,dt=1e-5):
    start=time.perf_counter()
    seq,folder,seqid=sequence(name,b,direction,phase,etl)
    settings=dict(stage=stage,name=name,b=b,direction=direction,phase=phase,b1=b1,b0=b0,
                  etl=etl,n=n,seed=seed,rf_dt=dt,seqid=seqid,T1=1.5,T2=.08,T2prime=.03)
    caseid=digest(settings); cache=RUNS/'cases'/caseid
    if (cache/'finite.json').exists():
        rows=json.loads((cache/'finite.json').read_text())
    else:
        r=simulate.simulate(seq,b1=b1,b0=b0,voxel=simulate.make_voxel(n=n,seed=seed),rf_dt=dt)
        edges=np.cumsum(np.r_[0,r['adc_sizes']]); rows=[]
        for echo,(a,z) in enumerate(zip(edges[:-1],edges[1:]),1):
            center=r['signal'][a+(z-a)//2]
            win=r['signal'][a:z]; ts=r['t_adc'][a:z]
            row=common(stage,name,b,direction,phase,b1,b0,etl,seqid,caseid)
            row.update(echo=echo,n=n,seed=seed,rf_dt_s=dt,total_real=float(center.real),
                total_imag=float(center.imag),total_abs=float(abs(center)),
                total_phase_deg=float(np.angle(center,deg=True)),peak=float(abs(win).max()),
                peak_offset_us=float((ts[np.argmax(abs(win))]-ts[(z-a)//2])*1e6),
                elapsed_s=float(time.perf_counter()-start),model='finite_RF_static_Bloch',
                cache=str(cache.relative_to(ROOT)))
            rows.append(row)
        dump(cache/'finite.json',rows); dump(cache/'settings.json',settings)
        np.savez_compressed(cache/'signals.npz',signal=r['signal'],t_adc=r['t_adc'],adc_sizes=r['adc_sizes'])
    merge_table(rows,OUT/f'combined_factor_{stage}_bloch.csv')
    print(f'{stage} {name} b{b} {direction} ph{phase} B1{b1} B0{b0} ETL{etl} | E{etl}={rows[-1]["total_abs"]:.5f} | {time.perf_counter()-start:.1f}s',flush=True)
    return rows


def exact(stage,name,b,direction,phase,b1,b0,D=0,etl=8):
    start=time.perf_counter()
    _,folder,seqid=sequence(name,b,direction,phase,etl)
    settings=dict(stage=stage,name=name,b=b,direction=direction,phase=phase,b1=b1,b0=b0,D=D,etl=etl,seqid=seqid)
    caseid=digest(settings);cache=RUNS/'cases'/caseid
    if (cache/'pathways.json').exists(): rows=json.loads((cache/'pathways.json').read_text())
    else:
        seq=epg.quiet(epg.mr0.Sequence.import_file,str(folder/'seq.seq'))
        args=SimpleNamespace(voxel_mm=[.2,.2,1],T1=1.5,T2=.08,T2dash=.03,D=D,b0=b0,b1=b1)
        ms=epg.quiet(pathways.enumerate_center_pathways,seq,epg.make_phantom(args))
        rows=[]
        for m in ms:
            group={k:[p.value for p in m.contributions if category(p.history,m.primary_history)==k]
                   for k in ['primary','stimulated','other']}
            row=common(stage,name,b,direction,phase,b1,b0,etl,seqid,caseid)
            row.update(echo=m.echo,D_MRzero=D,D_mm2_s=D*.001,l1=m.l1_amplitude,
                unwanted_l1_share=m.other_l1_fraction,cancellation=m.cancellation_ratio,
                elapsed_s=float(time.perf_counter()-start),model='instant_RF_exact_pathways',
                cache=str(cache.relative_to(ROOT)))
            for label,values in list(group.items())+[('total',[m.total])]:
                value=sum(values,0j)
                row.update({label+'_real':float(value.real),label+'_imag':float(value.imag),
                    label+'_abs':float(abs(value)),label+'_phase_deg':float(np.angle(value,deg=True)),
                    label+'_l1':float(sum(abs(v) for v in values))})
            row['stimulated_l1_share']=row['stimulated_l1']/m.l1_amplitude if m.l1_amplitude else 0
            row['stimulated_relative_phase_deg']=float(np.angle(sum(group['stimulated'],0j)*m.primary.conjugate(),deg=True))
            row['group_closure_abs']=float(abs(row['primary_real']+1j*row['primary_imag']+row['stimulated_real']+1j*row['stimulated_imag']+row['other_real']+1j*row['other_imag']-m.total))
            rows.append(row)
        dump(cache/'pathways.json',rows); dump(cache/'settings.json',settings)
    merge_table(rows,OUT/f'combined_factor_{stage}_pathways.csv')
    print(f'PDG {stage} {name} ph{phase} B1{b1} D{D} | E{etl} unwanted={rows[-1]["unwanted_l1_share"]:.4g} | {time.perf_counter()-start:.1f}s',flush=True)
    return rows


def execute(fn,*args,**kwargs):
    try: return fn(*args,**kwargs)
    except Exception as e:
        error=dict(function=fn.__name__,args=args,kwargs=kwargs,error=str(e),traceback=traceback.format_exc())
        path=OUT/'combined_factor_errors.json'
        errors=json.loads(path.read_text()) if path.exists() else []
        errors.append(error);dump(path,errors)
        print('ERROR',args,str(e),flush=True)


def rebuild_tables():
    """Recover compact outputs from immutable, per-case result caches."""
    groups={}
    for model,file in [('bloch','finite.json'),('pathways','pathways.json')]:
        for path in sorted((RUNS/'cases').glob('*/'+file)):
            rows=json.loads(path.read_text())
            if rows:
                for row in rows:
                    row['actual_excitation_phase_deg']=round(float(row['phase'])/.225)*.225
                groups.setdefault((rows[0]['stage'],model),[]).extend(rows)
    for (stage,model),rows in groups.items():
        table(rows,OUT/f'combined_factor_{stage}_{model}.csv')
    errorspath=OUT/'combined_factor_errors.json'
    if errorspath.exists():
        errors=json.loads(errorspath.read_text())
        for error in errors:
            if 'Invalid argument' in error['error'] and 'combined_factor_' in error['error']:
                error.update(status='resolved_infrastructure',resolution='Cached simulation result recovered by rebuilding compact CSV; no scientific generation or simulation failure.')
        dump(errorspath,errors)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('stage',choices=['screen','pathways','robust','heldout','sensitivity','hardware','rebuild'])
    ap.add_argument('--variants',default=None)
    ap.add_argument('--n',type=int,default=4096)
    ap.add_argument('--label',default=None,help='Explicit separate validation-stage label')
    args=ap.parse_args()
    names=args.variants.split(',') if args.variants else list(CONFIGS)
    label=args.label or args.stage
    dump(ROOT/'docs/params/combined_factor_configs.json',dict(version=VERSION,base=BASE,configs=CONFIGS,
        design_notes='Legacy1.6 explicit timing controls; first crusher unchanged; finite-RF and exact pathway models separate; peak3.4 ramps; energy matches full played G squared; 500us amplitude compensates 200us ramp area; physical D is .001*MRzero D.'))
    for name in names:
        if args.stage=='screen':
            for phase in [0,90]:
                for b1 in [.8,1]: execute(finite,'screen',name,1000,'read',phase,b1,0,n=args.n)
        elif args.stage=='pathways':
            for phase in [0,90]:
                for b1 in [.8,1]:
                    for D in [0,1]: execute(exact,'screen',name,1000,'read',phase,b1,0,D=D)
        elif args.stage=='robust':
            # Defined panels, not a massive full cube: reference, phase, B1/B0,
            # b/direction, and mixed challenge panels.
            panel=[(1000,'read',ph,b1,0) for ph in [0,45,90] for b1 in [.7,.8,1,1.2]]
            panel += [(b,d,45,.8,100) for b in [0,1000] for d in ['read','slice','oblique']]
            panel += [(1000,d,90,b1,100) for d in ['read','slice','oblique'] for b1 in [.7,1.2]]
            for b,d,ph,b1,b0 in panel:
                execute(finite,label,name,b,d,ph,b1,b0,n=args.n)
                if d=='read' or (ph==45 and b==1000):
                    execute(exact,label,name,b,d,ph,b1,b0,D=1)
        elif args.stage=='heldout':
            panel=[(1000,d,ph,b1,b0,8) for d in ['phase','held_oblique']
                   for ph,b1,b0 in [(22.5,.9,-75),(67.5,1.1,150)]]
            panel += [(1000,'slice',30,.9,-75,4),(0,'read',60,1.1,-75,6),
                      (1000,'held_oblique',60,.9,150,12)]
            for b,d,ph,b1,b0,etl in panel:
                execute(finite,label,name,b,d,ph,b1,b0,etl=etl,n=args.n,seed=2)
                if etl<=8: execute(exact,label,name,b,d,ph,b1,b0,D=1,etl=etl)
        elif args.stage=='sensitivity':
            for phase in [0,90]:
                execute(finite,'sensitivity_dense',name,1000,'read',phase,.8,0,n=16000,seed=2)
                execute(finite,'sensitivity_dt2us',name,1000,'read',phase,.8,0,n=args.n,dt=2e-6)
        elif args.stage=='hardware':
            for b in [0,1000]:
                for direction in ['read','slice','oblique']:
                    execute(sequence,name,b,direction,0)
    if args.stage=='rebuild':rebuild_tables()
    manifest=[]
    for folder in sorted((RUNS/'sequences').glob('*')):
        if (folder/'hardware.json').exists():
            h=json.loads((folder/'hardware.json').read_text())
            tensors=json.loads((folder/'btensor.json').read_text())
            for e in tensors['echoes']:
                if e['convention']!='sample':continue
                row={k:v for k,v in h.items() if not isinstance(v,list)}
                row.update(echo=e['echo'],time_s=e['time_s'],b_trace_s_mm2=e['trace_s_mm2'])
                for i,a in enumerate('xyz'):
                    for j,z in enumerate('xyz'):row['B'+a+z]=e['B_s_mm2'][i][j]
                    row['q_'+a]=e['q_rad_m'][i]
                manifest.append(row)
    table(manifest,OUT/'combined_factor_hardware_tensors.csv')
    versions={}
    for package in ['numpy','matplotlib','torch','pypulseq','MRzeroCore']:
        try:versions[package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:versions[package]='unavailable'
    sources={}
    baseline_sources={}
    normalized_sources={}
    normalized_baseline_sources={}
    for relative in ['scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.6.ppl',
                     'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.6.ppr',
                     'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.7.ppl',
                     'dwfse/generate.py','dwfse/simulate.py','dwfse/pathways.py',
                     'dwfse/btensor.py','dwfse/epg.py','dwfse/rf_pulses.py',
                     'dwfse/crushers.py','examples/improve_ppl.py',
                     'examples/compare_echo_snapshots.py','examples/combined_factor_study.py']:
        source_bytes=(ROOT/relative).read_bytes()
        sources[relative]=hashlib.sha256(source_bytes).hexdigest()
        normalized_sources[relative]=hashlib.sha256(source_bytes.replace(b'\r\n',b'\n')).hexdigest()
        baseline=subprocess.run(['git','-c','safe.directory='+ROOT.as_posix(),'show','c87b30e:'+relative],cwd=ROOT,capture_output=True)
        if baseline.returncode==0:
            baseline_sources[relative]=hashlib.sha256(baseline.stdout).hexdigest()
            normalized_baseline_sources[relative]=hashlib.sha256(baseline.stdout.replace(b'\r\n',b'\n')).hexdigest()
    count={}
    for file in OUT.glob('combined_factor_*_bloch.csv'):
        with file.open(newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
        count[file.name]=dict(echo_rows=len(rows),cases=len({r['case_id'] for r in rows}))
    for file in OUT.glob('combined_factor_*_pathways.csv'):
        with file.open(newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
        count[file.name]=dict(echo_rows=len(rows),cases=len({r['case_id'] for r in rows}))
    path=OUT/'combined_factor_provenance.json'
    prior=json.loads(path.read_text()) if path.exists() else {}
    stages=prior.get('stage_invocations',[])
    stages.append(dict(stage=args.stage,variants=names,n=args.n,elapsed_wall_s=time.perf_counter()-START_TIME))
    result_paths=list((RUNS/'cases').glob('*/finite.json'))+list((RUNS/'cases').glob('*/pathways.json'))
    computational_s=0.
    for result_path in result_paths:
        results=json.loads(result_path.read_text())
        if results:computational_s+=float(results[-1]['elapsed_s'])
    mtimes=[p.stat().st_mtime for p in result_paths]
    dump(path,dict(version=VERSION,source_sha256=sources,dependencies=versions,
        baseline_commit='c87b30e',baseline_source_sha256=baseline_sources,
        baseline_hash_convention='baseline_source_sha256 hashes committed Git blob bytes; source_sha256 hashes current working-file bytes. LF-normalized comparisons distinguish CRLF-only differences.',
        source_lf_normalized_sha256=normalized_sources,
        baseline_lf_normalized_sha256=normalized_baseline_sources,
        study_start_v17_working_sha256='b415b353a2d52b253eba1c463cffb51d9ca00abf8e553bce7a3d7f314705be68',
        concurrent_change_note='An external v1.7 timer-guard revision appeared during investigation. This runner made no scanner edits; every study sequence explicitly uses unchanged v1.6 PPR/generation controls. Baseline and final-current scanner hashes are separate.',
        stage_invocations=stages,counts=count,configurations=list(CONFIGS),
        sum_cached_case_elapsed_s=computational_s,
        observed_artifact_creation_span_s=max(mtimes)-min(mtimes) if mtimes else 0,
        pruning='none; exact all RF branches ETL<=8; ETL12 finite RF only',
        model_limits='Finite_RF Bloch stationary D=0 over 2mm profile; instant_RF exact pathways one 1mm box with D0/physical .001; models are not a matched decomposition.',
        hardware_limits='PPR full-scale defaults and model gradient delays; no measured scanner PNS, SAR, gradient thermal duty or RF power qualification',
        phase_convention='phase column is requested offset; actual_excitation_phase_deg rounds to .225deg scanner units (30->29.925deg,60->60.075deg)',
        errors_file='combined_factor_errors.json' if (OUT/'combined_factor_errors.json').exists() else None))


if __name__=='__main__':main()
