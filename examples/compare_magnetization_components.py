"""Signed finite-RF Bloch profiles at specified RF/ADC landmarks.

Run: python examples/compare_magnetization_components.py
The original v1.6 source is evaluated with the established ETL8 overrides.
No scanner source or simulator defaults are modified.
"""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dwfse import generate, simulate
from examples.improve_ppl import BASE

UP = [1, 1, 1.4, 1.8, 2.2, 2.6, 3, 3.4]
DOWN = [1, 3.4, 3, 2.6, 2.2, 1.8, 1.4, 1]
CASES = [
    ('original', 'Original', [1]*8, [0]*8, [180]*8),
    ('increasing', 'Increasing', UP, [0]*8, [180]*8),
    ('increasing_alternating', 'Increasing + alternating', [v*(-1)**k for k,v in enumerate(UP)], [0]*8, [180]*8),
    ('decreasing', 'Decreasing', DOWN, [0]*8, [180]*8),
    ('decreasing_alternating', 'Decreasing + alternating', [v*(-1)**k for k,v in enumerate(DOWN)], [0]*8, [180]*8),
    ('rf_xy', 'Original + RF phase 0/90', [1]*8, [0,90]*4, [180]*8),
    ('rf_180', 'Original + RF phase 0/180', [1]*8, [0,180]*4, [180]*8),
    ('rf_quadratic', 'Original + quadratic RF phase', [1]*8, [(65*k*k)%360 for k in range(8)], [180]*8),
    ('increasing_rf_xy', 'Increasing + RF phase 0/90', UP, [0,90]*4, [180]*8),
    ('increasing_rf_taper', 'Increasing + RF angle taper', UP, [0]*8, [180,180,175,170,165,160,155,150]),
]
LABELS = ['Before RF1', 'Before ADC1', 'Middle ADC1', 'Middle ADC2', 'Before ADC8', 'Middle ADC8']
COLORS = ['#2166ac', '#d6604d', '#228833']
COMPONENTS = ['Mx', 'My', 'Mz']


def landmarks(seq):
    ids, starts, durations = simulate.block_times(seq)
    adc, rf = [], []
    for bid, start in zip(ids, starts):
        block = seq.get_block(bid)
        if block.adc is not None:
            a = block.adc
            adc.append(dict(block=int(bid), start_s=float(start+a.delay),
                midpoint_s=float(start+a.delay+a.num_samples*a.dwell/2),
                sample_s=float(start+a.delay+(a.num_samples//2+.5)*a.dwell),
                sample_index=int(a.num_samples//2), dwell_s=float(a.dwell),
                num_samples=int(a.num_samples), phase_rad=float(a.phase_offset),
                frequency_hz=float(a.freq_offset)))
        if block.rf is not None and block.rf.use.startswith('ref'):
            r = block.rf
            rf.append(dict(block=int(bid), start_s=float(start+r.delay),
                           phase_deg=float(np.degrees(r.phase_offset))))
    assert len(adc) == len(rf) == 8
    # The first crusher shares a block with RF. Sample after that crusher,
    # 2 us before RF starts, at an exact step boundary for both 2/1-us runs.
    rf_start = rf[0]['start_s']
    times = [rf_start-2e-6, adc[0]['start_s']-1e-6, adc[0]['sample_s'],
             adc[1]['sample_s'], adc[7]['start_s']-1e-6, adc[7]['sample_s']]
    for j,t in enumerate(times):
        k = int(np.searchsorted(starts, t, side='right')-1)
        block = seq.get_block(ids[k])
        if j==0:
            assert t < rf_start
            for step in [1e-6,2e-6]:
                dt=durations[k]/round(durations[k]/step)
                assert abs((t-starts[k])/dt-round((t-starts[k])/dt))<1e-7
        else:
            assert block.rf is None, 'ADC snapshot must be in an RF-free block'
        assert starts[k] <= t <= starts[k]+durations[k]+1e-12
    return times, adc, rf, simulate.first_excitation(seq)


def sequence(scales, phases, angles, phase):
    overrides = dict(BASE, sim_reduced_rows=[1], sim_excitation_phase_deg=phase,
                     sim_train_crusher_scales=scales, sim_refocus_phase_offsets_deg=phases)
    seq,c,d,_ = generate.build_sequence(generate.load_params(overrides=overrides), reduced=True)
    if angles != [180]*8:
        k = 0
        for bid in sorted(seq.block_events):
            block = seq.get_block(bid)
            if block.rf is not None and block.rf.use.startswith('ref'):
                block.rf.signal *= angles[k]/c.sim_refocus_flip_deg
                if hasattr(block.rf, 'id'):
                    del block.rf.id
                seq.set_block(bid, block)
                k += 1
        assert k == 8
    ok,errors = seq.check_timing()
    assert ok, errors
    return seq, overrides, d.train_crusher_amplitudes_dac, d.refocus_phase_offsets_deg


def values(result, ng, mode):
    arrays = np.array([s[1:] for s in result['snapshots']])
    if mode == 'line':
        return result['voxel']['z'][:ng]*1e3, arrays[:,:,:ng]
    z = result['voxel']['z'][ng:]*1e3
    edges = np.linspace(-1,1,129)
    bins = np.minimum(np.searchsorted(edges,z,side='right')-1,127)
    counts = np.bincount(bins,minlength=128)
    profiles = np.array([[np.bincount(bins,weights=v,minlength=128)/counts
                         for v in snap[:,ng:]] for snap in arrays])
    return (edges[:-1]+edges[1:])/2, profiles


def advance_rf_free_prefix(seq, state, old_t, new_t, voxel):
    """Move an older pre-block checkpoint through the leading crusher exactly."""
    ids,starts,durations=simulate.block_times(seq)
    moment=np.zeros(3)
    for bid,start,duration in zip(ids,starts,durations):
        left=max(old_t,start); right=min(new_t,start+duration)
        if right<=left: continue
        block=seq.get_block(bid)
        if block.rf is not None:
            assert right <= start+block.rf.delay+1e-12
        for i,axis in enumerate('xyz'):
            pts=simulate.grad_pts(getattr(block,'g'+axis,None))
            moment[i]+=float(simulate._cumint(pts,right-start)-simulate._cumint(pts,left-start))
    dt=new_t-old_t
    assert dt>=0
    phi=2*np.pi*(sum(moment[i]*voxel[k] for i,k in enumerate('xyz'))+voxel['df']*dt)
    transverse=(state[0]+1j*state[1])*np.exp(-1j*phi-dt/.08)
    return np.array([transverse.real,transverse.imag,1+(state[2]-1)*np.exp(-dt/1.5)])


def profile_figure(record, ng, mode, destination):
    z, m = values(record['result'],ng,mode)
    fig,axs = plt.subplots(3,6,figsize=(19,8),sharex=True,sharey=True)
    for j in range(6):
        for i in range(3):
            ax = axs[i,j]
            ax.plot(z,m[j,i],color=COLORS[i],lw=.8)
            ax.axhline(0,color='#888888',lw=.5)
            ax.axvspan(-.5,.5,color='#bbbbbb',alpha=.12)
            ax.set_ylim(-1.05,1.05); ax.set_xlim(-1,1); ax.grid(alpha=.12)
            if j == 0: ax.set_ylabel(COMPONENTS[i]+' / M0')
            if i == 0:
                ax.set_title(f'{LABELS[j]}\n{record["relative_ms"][j]:.3f} ms',fontsize=10)
            if i == 2: ax.set_xlabel('Slice position z (mm)')
    subtitle = ('Local isochromats on x=y=0, off-resonance=0 Hz; no spatial averaging'
                if mode == 'line' else 'Voxel conditional means in 128 z bins; transverse phase cancellation is included')
    fig.suptitle(f'{record["title"]} | RF strength {100*record["b1"]:.0f}% | excitation phase offset {record["phase"]:.0f} deg\n'+subtitle,fontsize=14)
    fig.text(.5,.02,'Signed components in the same simulation rotating frame; shaded region: nominal 1-mm slice. '
             'Times relative to excitation center. Before ADC = 1 us before acquisition starts.',ha='center',fontsize=10)
    fig.tight_layout(rect=(0,.05,1,.91))
    fig.savefig(destination,dpi=145)
    if record['key']=='original' and record['b1']==.8 and record['phase']==45 and mode=='line':
        fig.savefig(destination.with_suffix('.svg'))
    plt.close(fig)


def comparison(records,ng,b1,phase,group,destination):
    selection = [r for r in records if r['b1']==b1 and r['phase']==phase
                 and (r['key'] in [c[0] for c in CASES[:5]] if group=='crushers' else r['key'] in ['original']+[c[0] for c in CASES[5:]])]
    fig,axs = plt.subplots(len(selection),3,figsize=(13,2*len(selection)),sharex=True,sharey=True)
    for row,r in enumerate(selection):
        z,m = values(r['result'],ng,'line')
        for i,ax in enumerate(axs[row]):
            ax.plot(z,m[5,i],color=COLORS[i],lw=.65)
            ax.axhline(0,color='#888888',lw=.4); ax.axvspan(-.5,.5,color='#bbbbbb',alpha=.12)
            ax.set_xlim(-1,1); ax.set_ylim(-1.05,1.05); ax.grid(alpha=.12)
            if row==0: ax.set_title(COMPONENTS[i]+' / M0')
            if row==len(selection)-1: ax.set_xlabel('Slice position z (mm)')
        axs[row,0].set_ylabel(r['title'].replace(' + ','\n+ '),fontsize=9)
    fig.suptitle(f'Middle of ADC8 | {group} comparison | RF {b1*100:.0f}% | excitation offset {phase:.0f} deg\n'
                 'Local central line; signed components; common axes and rotating frame',fontsize=13)
    fig.tight_layout(rect=(0,0,1,.94)); fig.savefig(destination,dpi=145)
    if b1==.8 and phase==45:
        fig.savefig(destination.with_suffix('.svg'))
    plt.close(fig)


def gallery(folder):
    options = ''.join(f'<option value="{c[0]}">{c[1]}</option>' for c in CASES)
    html = '''<!doctype html><html><head><meta charset="utf-8"><title>Magnetization components</title>
<style>body{font:16px system-ui;margin:24px;background:#f8fafc;color:#172033}select{font:inherit;padding:8px;margin:6px}img{width:100%;background:white}p{max-width:1100px}a{color:#2166ac}</style></head><body>
<h1>Mx, My and Mz across the slice</h1><p>Signed finite-RF Bloch components, normalized to equilibrium M0. Every panel uses one fixed rotating frame and the same vertical scale. “Before ADC” is 1 microsecond before the acquisition window starts; “Middle ADC” uses the upper-middle acquired sample. An extra pre-RF1 panel supports the requested reference-style comparison.</p>
<p>Original means the v1.6 source with the established eight-echo protocol (TE 36 ms, spacing 16 ms, requested b 1000 s/mm²). These are stationary-spin simulations with modeled sinc RF. Gibbons et al. Figure 3 also uses signed components versus z, with a 45° excitation phase. Their Alsop and ss-MGOT preparation modules differ from this sequence. Before RF1 is 2 microseconds before the waveform starts, after its leading crusher.</p>
<label>Sequence <select id="variant">OPTIONS</select></label><label>RF strength <select id="b1"><option value="080">80%</option><option value="100">100%</option></select></label><label>Excitation phase <select id="phase"><option value="045">45° (Figure 3 condition)</option><option value="000">0°</option><option value="090">90°</option></select></label><label>Profile <select id="mode"><option value="line">Local central line</option><option value="ensemble">Voxel average by z</option></select></label>
<img id="figure" alt="Signed magnetization component snapshots"><p id="link"></p>
<h2>Compare the final ADC</h2><p>Crusher variants:</p><img id="crushers"><p>RF modulation variants (exploratory phase laws and angle taper):</p><img id="rf">
<p>Local central line: x=y=0, B0=0, no off-resonance spread. Voxel means: 0.2×0.2×2 mm support, Lorentzian frequency spread T2′=30 ms. Gray shading marks the nominal 1-mm slice. Mz includes equilibrium, inversion, storage and recovery; it is not a stimulated-echo fraction.</p>
<script>const ids=['variant','b1','phase','mode'];function update(){const [v,b,p,m]=ids.map(x=>document.getElementById(x).value);let f=`${v}_rf${b}_phase${p}_${m}.png`;document.getElementById('figure').src=f;document.getElementById('link').innerHTML=`<a href="${f}">Open full-size figure</a>`;for(const g of ['crushers','rf'])document.getElementById(g).src=`compare_${g}_rf${b}_phase${p}.png`;}ids.forEach(x=>document.getElementById(x).onchange=update);update();</script></body></html>'''
    (folder/'index.html').write_text(html.replace('OPTIONS',options),encoding='utf-8')


def prefill_job(job):
    """Independent simulation worker; writes only its unique raw array file."""
    case,phase,b1,ng,n=job
    key=case[0]
    seq,*_=sequence(*case[2:],phase)
    times,*_=landmarks(seq)
    line=dict(x=np.zeros(ng),y=np.zeros(ng),z=np.linspace(-.001,.001,ng),df=np.zeros(ng))
    ensemble=simulate.make_voxel(n=n,seed=1)
    voxel={k:np.r_[line[k],ensemble[k]] for k in line}
    result=simulate.simulate(seq,b1=b1,voxel=voxel,snap_times=times,rf_dt=2e-6)
    arrays=np.array([s[1:] for s in result['snapshots']])
    tag=f'{key}_rf{b1*100:03.0f}_phase{phase:03.0f}'
    np.savez_compressed(ROOT/'runs/magnetization_components'/f'{tag}.npz',**voxel,times_s=times,
        mx=arrays[:,0],my=arrays[:,1],mz=arrays[:,2],signal=result['signal'],
        t_adc=result['t_adc'],adc_sizes=result['adc_sizes'],line_count=ng)
    return tag


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--grid',type=int,default=8193)
    ap.add_argument('--n',type=int,default=8192)
    ap.add_argument('--phases',default='0,45,90',help='comma-separated excitation phase offsets')
    ap.add_argument('--reuse',action='store_true',help='reuse matching raw arrays; update pre-RF landmark if needed')
    ap.add_argument('--prefill',action='store_true',help='compute raw arrays only in parallel, then use --reuse for figures/checks')
    ap.add_argument('--workers',type=int,default=4)
    ap.add_argument('--reference-pdf',type=Path,default=Path('C:/Users/jaden/Downloads/Gibbons_2017.pdf'))
    args = ap.parse_args()
    excitation_phases=[float(p) for p in args.phases.split(',')]
    folder = ROOT/'docs/figures/magnetization_components'
    raw = ROOT/'runs/magnetization_components'
    folder.mkdir(parents=True,exist_ok=True); raw.mkdir(parents=True,exist_ok=True)
    if args.n<128: raise ValueError('at least 128 voxel spins needed for bins')
    if args.grid<9 or args.grid%2==0: raise ValueError('grid count must be odd and at least 9')
    if args.prefill:
        jobs=[(case,phase,b1,args.grid,args.n) for case in CASES for phase in excitation_phases for b1 in [.8,1.]]
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for tag in pool.map(prefill_job,jobs):
                print(tag,'computed',flush=True)
        return
    ensemble = simulate.make_voxel(n=args.n,seed=1)
    ng = args.grid
    line = dict(x=np.zeros(ng),y=np.zeros(ng),z=np.linspace(-.001,.001,ng),df=np.zeros(ng))
    voxel = {k:np.r_[line[k],ensemble[k]] for k in line}
    records,rows,checks,timing = [],[],[],[]
    for key,title,scales,phases,angles in CASES:
        for phase in excitation_phases:
            seq,overrides,crusher_dac,quantized_phases = sequence(scales,phases,angles,phase)
            times,adcs,rfs,texc = landmarks(seq)
            relative_ms = (np.array(times)-texc)*1000
            stem = f'{key}_phase{phase:03.0f}'
            seqpath = raw/(stem+'.seq'); seq.write(str(seqpath))
            loaded = simulate.read_seq(str(seqpath)); assert loaded.check_timing()[0]
            timing.append(dict(key=key,phase=phase,times_s=times,relative_ms=relative_ms.tolist(),
                labels=LABELS,adc=adcs,rf=rfs,crusher_dac=crusher_dac,
                rf_offsets_deg=quantized_phases,rf_angles_deg=angles,overrides=overrides,
                sequence_sha256=hashlib.sha256(seqpath.read_bytes()).hexdigest()))
            for b1 in (.8,1.):
                tag = f'{key}_rf{b1*100:03.0f}_phase{phase:03.0f}'
                cache=raw/(tag+'.npz')
                if args.reuse and cache.exists():
                    saved=np.load(cache)
                    assert all(np.array_equal(saved[k],voxel[k]) for k in voxel)
                    assert np.allclose(saved['times_s'][1:],times[1:],rtol=0,atol=1e-12)
                    arrays=np.array([saved['mx'],saved['my'],saved['mz']]).transpose(1,0,2)
                    if abs(saved['times_s'][0]-times[0])>1e-12:
                        arrays[0]=advance_rf_free_prefix(seq,arrays[0],saved['times_s'][0],times[0],voxel)
                    result=dict(voxel=voxel,signal=saved['signal'],t_adc=saved['t_adc'],adc_sizes=saved['adc_sizes'],
                                snapshots=[(t,*arrays[i]) for i,t in enumerate(times)])
                else:
                    result = simulate.simulate(seq,b1=b1,voxel=voxel,snap_times=times,rf_dt=2e-6)
                assert len(result['snapshots'])==6
                assert np.max(np.abs(np.array([s[0] for s in result['snapshots']])-times))<1e-12
                arrays = np.array([s[1:] for s in result['snapshots']])
                assert np.isfinite(arrays).all()
                maxnorm = float(np.max(np.sqrt(np.sum(arrays**2,axis=1))))
                assert maxnorm <= 1.000001
                closure = []
                edges = np.cumsum(np.r_[0,result['adc_sizes']])
                for snap,echo in [(2,0),(3,1),(5,7)]:
                    a = adcs[echo]; t = times[snap]
                    demod = np.exp(-1j*(a['phase_rad']+2*np.pi*a['frequency_hz']*(t-a['start_s'])))
                    signal = np.mean(arrays[snap,0]+1j*arrays[snap,1])*demod
                    closure.append(float(abs(signal-result['signal'][edges[echo]+a['sample_index']])))
                assert max(closure)<1e-10
                np.savez_compressed(raw/(tag+'.npz'),**voxel,times_s=times,mx=arrays[:,0],my=arrays[:,1],mz=arrays[:,2],
                    signal=result['signal'],t_adc=result['t_adc'],adc_sizes=result['adc_sizes'],line_count=ng)
                r = dict(key=key,title=title,b1=b1,phase=phase,result=result,relative_ms=relative_ms)
                records.append(r)
                for mode in ['line','ensemble']:
                    profile_figure(r,ng,mode,folder/(tag+'_'+mode+'.png'))
                checks.append(dict(tag=tag,adc_complex_closure_max=max(closure),max_spin_norm=maxnorm))
                for snap,label in enumerate(LABELS):
                    # All scalar statistics here refer only to the ensemble.
                    mx,my,mz = arrays[snap,:,ng:]
                    rows.append(dict(tag=tag,landmark=label,time_after_excitation_ms=float(relative_ms[snap]),
                        mean_mx=float(mx.mean()),mean_my=float(my.mean()),mean_mz=float(mz.mean()),
                        abs_mean_mxy=float(abs(np.mean(mx+1j*my))),mean_abs_mxy=float(np.mean(np.hypot(mx,my)))))
                print(tag, 'passed',flush=True)
    for b1 in (.8,1.):
        for phase in excitation_phases:
            for group in ['crushers','rf']:
                comparison(records,ng,b1,phase,group,folder/f'compare_{group}_rf{b1*100:03.0f}_phase{phase:03.0f}.png')
    # Numerical checks measure signed spatial components, not only averaged signal.
    for key in ['original','increasing_alternating','decreasing_alternating','rf_quadratic','increasing_rf_taper']:
        case = next(c for c in CASES if c[0]==key)
        seq,*_ = sequence(*case[2:],90.)
        times,*_ = landmarks(seq)
        v = {k:line[k][::4] for k in line}
        a = simulate.simulate(seq,b1=.8,voxel=v,snap_times=times,rf_dt=2e-6)
        b = simulate.simulate(seq,b1=.8,voxel=v,snap_times=times,rf_dt=1e-6)
        av,bv = [np.array([s[1:] for s in q['snapshots']]) for q in [a,b]]
        error = float(np.max(np.abs(av-bv)))
        assert error<.003, error
        checks.append(dict(tag=key,rf_step_2us_vs_1us_max_component_error=error))
        # Half-grid linear interpolation error quantifies spatial resolution.
        r = next(r for r in records if r['key']==key and r['phase']==90 and r['b1']==.8)
        z,m = values(r['result'],ng,'line')
        midpoint_error = float(np.max(np.abs(m[:,:,1::2]-(m[:,:,:-2:2]+m[:,:,2::2])/2)))
        assert midpoint_error<.01, midpoint_error
        checks.append(dict(tag=key,half_grid_interpolation_max_component_error=midpoint_error))
        cache_error=float(np.max(np.abs(m[:,:,::4]-av)))
        assert cache_error<1e-10, cache_error
        checks.append(dict(tag=key,cached_vs_independent_full_simulation_max_component_error=cache_error))
    # Future schedule changes cannot alter early snapshots in these cases.
    for b1 in [.8,1.]:
        for phase in excitation_phases:
            selected = [r for r in records if r['b1']==b1 and r['phase']==phase]
            ref = values(selected[0]['result'],ng,'line')[1][:3]
            error = max(float(np.max(np.abs(values(r['result'],ng,'line')[1][:3]-ref))) for r in selected)
            assert error<1e-12
            checks.append(dict(tag=f'early_causality_rf{b1}_phase{phase}',max_component_error=error))
    data = ROOT/'docs/data'; data.mkdir(exist_ok=True)
    with (data/'magnetization_components.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    source_paths=['scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.6.ppl','scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.6.ppr',
                  'dwfse/generate.py','dwfse/simulate.py','examples/compare_magnetization_components.py']
    provenance=dict(protocol='v1.6 ETL8 controlled comparison, original centering',
        paper_reference_status='Gibbons et al., DOI 10.1002/mrm.26971, Figure 3 inspected; not a reproduction of their sequences',
        paper_source_sha256=hashlib.sha256(args.reference_pdf.read_bytes()).hexdigest() if args.reference_pdf.exists() else None,
        grid_count=ng,ensemble_count=args.n,seed=1,rf_step_s=2e-6,T1_s=1.5,T2_s=.08,T2prime_ensemble_s=.03,
        line=dict(x_m=0,y_m=0,df_hz=0,z_range_mm=[-1,1]),normalization='individual equilibrium M0=1',
        frame='common simulation rotating frame, Mxy=Mx+iMy, free precession exp(-i phi); no receiver rotation of plots',
        diffusion='stationary spins; played diffusion gradients, no molecular diffusion attenuation',
        sources={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_paths},
        dependencies={p:importlib.metadata.version(p) for p in ['numpy','matplotlib','pypulseq']},
        timing=timing,checks=checks)
    (data/'magnetization_components_provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    gallery(folder)
    print('Complete:',folder/'index.html',flush=True)


if __name__=='__main__':
    main()
