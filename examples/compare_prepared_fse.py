"""Research Alsop/ss-MGOT adaptations and matched DW-FSE controls.

python examples/compare_prepared_fse.py --prefill --workers 4
python examples/compare_prepared_fse.py --reuse
These water-only, ETL8 mechanism models are not the published scanner protocols.
"""
import argparse
import copy
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
import pypulseq as pp

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dwfse import generate,simulate,btensor
from examples.improve_ppl import BASE
from examples.compare_magnetization_components import UP,DOWN

CASES=[('original','Original'),('increasing','Increasing'),('decreasing','Decreasing'),
       ('alternating','Alternating polarity'),('centered_original','Centered original'),
       ('alsop','Alsop adaptation'),('ss_mgot','ss-MGOT adaptation')]
TE_MS=64.
SLICE=.001
DEPHASE=2/SLICE  # Pulseq area in cycles/m
SPOIL=8/.0002
LANDMARKS=['Before imaging RF1','Before ADC1','Middle ADC1','Middle ADC2','Before ADC8','Middle ADC8']
COLORS=['#2166ac','#d6604d','#228833']


def clean(event):
    if event is not None and hasattr(event,'id'): del event.id
    return event


def add_copy(seq,block,duration=None):
    events=[clean(copy.deepcopy(getattr(block,k))) for k in ['rf','gx','gy','gz','adc'] if getattr(block,k) is not None]
    for label in (block.label or {}).values(): events.append(copy.deepcopy(label))
    events.append(pp.make_delay(duration or block.block_duration))
    seq.add_block(*events)


def elapsed(seq): return sum(seq.block_durations.values())


def until(seq,t):
    dt=round((t-elapsed(seq))/1e-6)*1e-6
    if dt < -1e-9: raise ValueError(f'Events overlap by {-dt*1000:.6f} ms at {t*1000:.6f} ms')
    if dt>0: seq.add_block(pp.make_delay(dt))


def grad(seq,axis,area,duration=.0008):
    event=pp.make_trapezoid(axis,area=area,duration=duration,rise_time=.0001,fall_time=.0001,system=seq.system)
    seq.add_block(event)
    return event


def summed_gradient(system,axis,events,duration):
    knots=np.unique(np.r_[0,duration,*[simulate.grad_pts(g)[0] for g in events if g is not None]])
    amplitudes=sum(np.interp(knots,*simulate.grad_pts(g),left=0,right=0) for g in events if g is not None)
    return pp.make_extended_trapezoid(axis,times=knots,amplitudes=amplitudes,system=system)


def rf_center(rf):
    return rf.delay+getattr(rf,'center',rf.t[np.argmax(np.abs(rf.signal))])


def prepare_reference(te,phase,scales=None,centered=False):
    overrides=dict(BASE,te=te,sim_reduced_rows=[1],sim_excitation_phase_deg=phase,
                   sim_fix_refocus_centering=centered,sim_train_crusher_scales=scales or [1]*8)
    seq,c,d,_=generate.build_sequence(generate.load_params(overrides=overrides),reduced=True)
    return seq,c,d,overrides


def tip_events(system,phase,thickness):
    rf,gz,_=pp.make_sinc_pulse(np.pi/2,duration=.0032,time_bw_product=3.55,
        apodization=.46,slice_thickness=thickness,phase_offset=phase,
        delay=system.rf_dead_time,return_gz=True,use='preparation',system=system)
    # This spatial sinc substitutes for the unpublished water-selective
    # spectral-spatial tip-up. Pre/post compensation is explicit.
    half=float(simulate._cumint(simulate.grad_pts(gz),rf_center(rf)))
    duration=np.ceil(pp.calc_duration(rf,gz)/4e-6)*4e-6
    return rf,gz,half,duration


def build(key,phase=45.):
    scales={'original':[1]*8,'centered_original':[1]*8,'increasing':UP,
            'decreasing':DOWN,'alternating':[(-1)**k for k in range(8)]}
    if key in scales:
        seq,c,d,overrides=prepare_reference(TE_MS,phase,scales[key],key=='centered_original')
        ids,starts,_=simulate.block_times(seq)
        ref=[i for i in ids if seq.get_block(i).rf is not None and seq.get_block(i).rf.use=='refocusing']
        exc=simulate.first_excitation(seq)
        info=dict(key=key,title=dict(CASES)[key],initial_excitation_s=exc,imaging_origin_s=exc,
                  imaging_rf_blocks=ref,preparation_echo_ms=None,overrides=overrides,
                  centering='corrected' if key=='centered_original' else 'v1.6 as written')
    else:
        # Alsop's elimination pulse occurs half an ESP before imaging RF1.
        # ss-MGOT instead stores at a shorter diffusion echo, spoils, then
        # re-excites at that same imaging-train origin.
        prep_te=48. if key=='alsop' else 36.
        ref,c,d,overrides=prepare_reference(prep_te,phase,centered=True)
        seq=pp.Sequence(system=copy.deepcopy(ref.system))
        seq.definitions=copy.deepcopy(ref.definitions)
        seq.set_definition('Name',f'{key}_water_only_mechanism_ETL8')
        seq.set_definition('ResearchAdaptation',1)
        seq.set_definition('ImagingRefocusFlip_deg',180)
        seq.set_definition('TotalFirstADC_TE_ms',TE_MS)
        seq.set_definition('PreparationEcho_ms',prep_te)
        seq.set_definition('AdditionalDephase_cycles',2)
        seq.set_definition('TipUpModel','3.2ms spatial Hamming sinc TBW3.55; no spectral selectivity')
        seq.set_definition('PreparationSlab_mm',1 if key=='alsop' else 3)
        seq.set_definition('SpoilerY_cycles',0 if key=='alsop' else 8)
        seq.set_definition('PublishedProtocolReproduction',0)
        ids,starts,durs=simulate.block_times(ref)
        exc=simulate.first_excitation(ref)
        first_adc=next(i for i in ids if ref.get_block(i).adc is not None)
        # Prefix ends at the last played diffusion gradient. Remove the
        # excitation's readout prephaser; add it once at the imaging origin.
        diffusion_blocks=[i for i in ids if i<first_adc and ref.get_block(i).rf is None and ref.get_block(i).gx is not None]
        last_diff=max(diffusion_blocks)
        for bid in ids:
            if bid>last_diff: break
            block=copy.deepcopy(ref.get_block(bid))
            if block.rf is not None and block.rf.use=='excitation': block.gx=None
            if key=='ss_mgot' and block.gz is not None:
                g=block.gz
                if g.type=='trap':
                    g.amplitude/=3; g.area/=3; g.flat_area/=3
                else:
                    g.waveform=g.waveform/3
                    g.first/=3; g.last/=3
                clean(g)
            add_copy(seq,block)
        prefix_end=elapsed(seq)
        # Negative-y tip preserves My in Alsop, matching the refocusing phase.
        # Negative-x tip stores My in
        # ss-MGOT, in the common frame where imaging RF is negative-y.
        tip_phase=3*np.pi/2 if key=='alsop' else np.pi
        tip,gz,half,tip_duration=tip_events(seq.system,tip_phase,SLICE if key=='alsop' else 3*SLICE)
        tip_center=exc+prep_te/1000
        tip_start=tip_center-rf_center(tip)
        until(seq,tip_start-.0016)
        grad(seq,'z',DEPHASE)
        grad(seq,'z',-half)
        assert abs(elapsed(seq)-tip_start)<1e-10
        tip_block=seq.next_free_block_ID
        seq.add_block(tip,gz,pp.make_delay(tip_duration))
        grad(seq,'z',-float(gz.area-half))
        after_tip=elapsed(seq)
        spoiler_block=None
        if key=='ss_mgot':
            spoiler_block=seq.next_free_block_ID
            grad(seq,'y',SPOIL,duration=.006)
            after_spoiler=elapsed(seq)
            # Copy the original excitation's RF/slice-gradient model for
            # imaging re-excitation; its readout prephaser is handled below.
            original_exc=next(ref.get_block(i) for i in ids if ref.get_block(i).rf is not None and ref.get_block(i).rf.use=='excitation')
            block=copy.deepcopy(original_exc)
            block.gx=None
            block.rf.phase_offset=0.  # stored Mz -> +My, independently of initial phase
            clean(block.rf)
            imaging_origin=exc+.048
            until(seq,imaging_origin-rf_center(block.rf))
            reexc_block=seq.next_free_block_ID
            add_copy(seq,block)
        else:
            imaging_origin=tip_center
            after_spoiler=None; reexc_block=None
        # The first original readout's half-moment gives its required initial
        # prephaser. Both original and prepared trains use these same ADCs.
        read_blocks=[ref.get_block(i) for i in ids if ref.get_block(i).adc is not None]
        rb=read_blocks[0]
        read_half=float(simulate._cumint(simulate.grad_pts(rb.gx),rb.adc.delay+rb.adc.num_samples*rb.adc.dwell/2))
        grad(seq,'x',read_half)
        # Later original refocusing blocks are a normal constant crusher pair.
        ref_blocks=[ref.get_block(i) for i in ids if ref.get_block(i).rf is not None and ref.get_block(i).rf.use=='refocusing']
        template=ref_blocks[1]
        imaging_rf=[]
        for echo in range(8):
            center=exc+(TE_MS+16*echo)/1000
            rf_time=center-.008
            until(seq,rf_time-rf_center(template.rf))
            imaging_rf.append(seq.next_free_block_ID)
            add_copy(seq,template)
            block=copy.deepcopy(read_blocks[echo])
            a=block.adc
            adc_mid=a.delay+a.num_samples*a.dwell/2
            until(seq,center-adc_mid)
            # Recall +2 cycles before ADC; restore -2 cycles after ADC.
            # Together with unchanged symmetric RF crushers this is equivalent
            # to the paper's added/subtracted crusher moments after echo 1.
            pre=pp.make_trapezoid('z',area=DEPHASE,duration=.0008,rise_time=.0001,fall_time=.0001,
                                 delay=.0001,system=seq.system)
            post=pp.make_trapezoid('z',area=-DEPHASE,duration=.0008,rise_time=.0001,fall_time=.0001,
                                  delay=block.block_duration-.0009,system=seq.system)
            assert pp.calc_duration(pre)<a.delay
            assert post.delay>a.delay+a.num_samples*a.dwell
            block.gz=summed_gradient(seq.system,'z',[block.gz,pre,post],block.block_duration)
            add_copy(seq,block)
        until(seq,max(c.tr/1000,elapsed(seq)))
        info=dict(key=key,title=dict(CASES)[key],initial_excitation_s=exc,imaging_origin_s=imaging_origin,
            preparation_echo_ms=prep_te,imaging_rf_blocks=imaging_rf,tip_block=tip_block,
            reexcitation_block=reexc_block,spoiler_block=spoiler_block,after_tip_s=after_tip,
            after_spoiler_s=after_spoiler,prefix_end_s=prefix_end,read_prephaser_cycles_m=read_half,
            dephase_cycles=2,slab_scale=1 if key=='alsop' else 3,spoiler_cycles_y=0 if key=='alsop' else 8,
            centering='corrected',overrides=overrides,
            adaptations=['spatial sinc instead of spectral-spatial tip-up','common fixed-180 imaging train',
                         'ETL8; 1mm slice; 16ms ESP; common 64ms total first ADC TE',
                         'slab widening scales all prefix z gradients including preparation crushers'])
    ok,errors=seq.check_timing()
    assert ok,errors
    seq.set_definition('InitialExcitationPhase_deg',phase)
    seq.set_definition('SimulationUseOnly',1)
    seq.set_definition('ImagingRFBlockIDs',info['imaging_rf_blocks'])
    return seq,info


def landmarks(seq,info):
    ids,starts,durs=simulate.block_times(seq)
    adcs=[]
    for bid,start in zip(ids,starts):
        a=seq.get_block(bid).adc
        if a is not None:
            adcs.append(dict(block=bid,start_s=start+a.delay,midpoint_s=start+a.delay+a.num_samples*a.dwell/2,
                sample_s=start+a.delay+(a.num_samples//2+.5)*a.dwell,phase_rad=a.phase_offset,
                frequency_hz=a.freq_offset,sample_index=a.num_samples//2,num_samples=a.num_samples))
    assert len(adcs)==8
    bid=info['imaging_rf_blocks'][0]
    block=seq.get_block(bid)
    rf_start=starts[ids.index(bid)]+block.rf.delay
    pre=rf_start-4e-6
    dt=durs[ids.index(bid)]/round(durs[ids.index(bid)]/4e-6)
    assert abs((pre-starts[ids.index(bid)])/dt-round((pre-starts[ids.index(bid)])/dt))<1e-7
    times=[pre,adcs[0]['start_s']-1e-6,adcs[0]['sample_s'],adcs[1]['sample_s'],
           adcs[7]['start_s']-1e-6,adcs[7]['sample_s']]
    assert np.allclose([(a['midpoint_s']-info['initial_excitation_s'])*1000 for a in adcs],
                       TE_MS+np.arange(8)*16,atol=1e-8)
    return np.array(times),adcs


def voxel(grid,n,phase_points=2):
    z=np.linspace(-.001,.001,grid)
    # Exact mean of harmonic e^(+/-i 2pi SPOIL*y) over an integer-cycle voxel.
    # A separate 256-point quadrature checks this reduction independently,
    # including the phase encoding at each ADC.
    y=np.array([-1,1])/(4*SPOIL) if phase_points==2 else ((np.arange(phase_points)+.5)/phase_points-.5)*.0002
    ensemble=simulate.make_voxel(n=n,seed=1)
    v=dict(x=np.zeros(grid*(1+phase_points)),y=np.r_[np.zeros(grid),np.repeat(y,grid)],
           z=np.tile(z,1+phase_points),df=np.zeros(grid*(1+phase_points)))
    return {k:np.r_[v[k],ensemble[k]] for k in v}


def simulate_job(job):
    key,phase,b1,grid,n=job
    seq,info=build(key,phase)
    times,adcs=landmarks(seq,info)
    v=voxel(grid,n)
    all_times=sorted(set(times.tolist()+[a['sample_s'] for a in adcs]))
    result=simulate.simulate(seq,b1=b1,voxel=v,snap_times=all_times,rf_dt=4e-6)
    snaps={round(s[0],12):np.array(s[1:]) for s in result['snapshots']}
    m=np.array([snaps[round(t,12)] for t in times])
    voxel_echo_states=np.array([snaps[round(a['sample_s'],12)][:,-n:] for a in adcs])
    assert m.shape==(6,3,3*grid+n)
    tag=f'{key}_rf{b1*100:03.0f}_phase{phase:03.0f}'
    np.savez_compressed(ROOT/'runs/prepared_fse_comparison'/f'{tag}.npz',**v,times_s=times,
                        mx=m[:,0],my=m[:,1],mz=m[:,2],signal=result['signal'],
                        t_adc=result['t_adc'],adc_sizes=result['adc_sizes'],grid=grid,n=n,
                        voxel_echo_states=voxel_echo_states)
    return tag


def pe_moments(seq,info,times):
    ids,starts,durations=simulate.block_times(seq)
    moments=[]
    for t in times:
        area=0.
        for bid,start,duration in zip(ids,starts,durations):
            block=seq.get_block(bid)
            if block.gy is not None:
                if block.rf is not None:raise ValueError('harmonic averaging requires no Gy during RF')
                area+=float(simulate._cumint(simulate.grad_pts(block.gy),np.clip(t-start,0,duration)))
        moments.append(area-(SPOIL if info['key']=='ss_mgot' else 0))
    return np.array(moments)


def profiles(arrays,grid,mode,pe=None):
    if mode=='local': return arrays[:,:,:grid]
    # RF is linear, all Gy encoding lies outside RF, and PE lobes rewind
    # before the next RF. States have only DC and +/-SPOIL harmonics in y.
    # Samples at y=0 and +/-1/(4*SPOIL) recover these three coefficients.
    # Remove the current PE phase, integrate each harmonic analytically over
    # the uniform .2-mm voxel, and retain its effect on the ADC mean.
    pe=np.zeros(len(arrays)) if pe is None else np.asarray(pe)
    xy=arrays[:,0]+1j*arrays[:,1]
    minus=xy[:,grid:2*grid]*np.exp(-2j*np.pi*pe[:,None]/(4*SPOIL))
    plus=xy[:,2*grid:3*grid]*np.exp(2j*np.pi*pe[:,None]/(4*SPOIL))
    dc=(minus+plus)/2
    cosine=xy[:,:grid]-dc
    sine=(plus-minus)/2
    width=.0002
    c=(np.sinc((pe-SPOIL)*width)+np.sinc((pe+SPOIL)*width))/2
    s=(np.sinc((pe-SPOIL)*width)-np.sinc((pe+SPOIL)*width))/(2j)
    mean=dc*np.sinc(pe[:,None]*width)+cosine*c[:,None]+sine*s[:,None]
    mz=(arrays[:,2,grid:2*grid]+arrays[:,2,2*grid:3*grid])/2
    return np.array([mean.real,mean.imag,mz]).transpose(1,0,2)


def plot_profiles(record,grid,mode,path):
    fig,axs=plt.subplots(3,6,figsize=(19,8),sharex=True,sharey=True)
    z=record['z'][:grid]*1000
    m=profiles(record['m'],grid,mode,record['pe_moments'])
    for i in range(3):
        for j in range(6):
            ax=axs[i,j];ax.plot(z,m[j,i],lw=.8,color=COLORS[i])
            ax.axhline(0,color='#888888',lw=.5);ax.axvspan(-.5,.5,color='#bbbbbb',alpha=.12)
            ax.set_ylim(-1.05,1.05);ax.set_xlim(-1,1);ax.grid(alpha=.12)
            if j==0: ax.set_ylabel(['Mx / M0','My / M0','Mz / M0'][i])
            if i==2: ax.set_xlabel('Slice position z (mm)')
            if i==0: ax.set_title(f'{LANDMARKS[j]}\n{record["relative_ms"][j]:.3f} ms',fontsize=10)
    note='Local x=y=0, on resonance' if mode=='local' else 'On-resonance x=0 profile, coherently averaged over y (includes Gy spoiling)'
    fig.suptitle(f'{record["title"]} | RF {record["b1"]*100:.0f}% | initial excitation phase {record["phase"]:.0f} deg\n'+note,fontsize=14)
    fig.text(.5,.02,'Matched first ADC midpoint TE 64 ms; ESP 16 ms; ETL8. Signed components in one fixed rotating frame. '
             'Times from initial excitation center.',ha='center',fontsize=10)
    fig.tight_layout(rect=(0,.05,1,.91));fig.savefig(path,dpi=145);plt.close(fig)


def comparison(records,grid,b1,phase,snap,folder):
    selected=[r for r in records if r['b1']==b1 and r['phase']==phase]
    fig,axs=plt.subplots(len(selected),3,figsize=(13,2*len(selected)),sharex=True,sharey=True)
    for row,r in enumerate(selected):
        m=profiles(r['m'],grid,'average',r['pe_moments'])[snap]
        for i,ax in enumerate(axs[row]):
            ax.plot(r['z'][:grid]*1000,m[i],color=COLORS[i],lw=.7)
            ax.axhline(0,color='#888888',lw=.4);ax.axvspan(-.5,.5,color='#bbbbbb',alpha=.12)
            ax.set_xlim(-1,1);ax.set_ylim(-1.05,1.05);ax.grid(alpha=.12)
            if row==0: ax.set_title(['Mx / M0','My / M0','Mz / M0'][i])
            if row==len(selected)-1:ax.set_xlabel('Slice position z (mm)')
        axs[row,0].set_ylabel(r['title'].replace(' ','\n',1),fontsize=9)
    fig.suptitle(f'{LANDMARKS[snap]} | RF {b1*100:.0f}% | initial phase {phase:.0f} deg\n'
                 'Coherent mean over y; same axes and frame; matched first ADC TE 64 ms',fontsize=13)
    fig.tight_layout(rect=(0,0,1,.94))
    path=folder/f'compare_t{snap}_rf{b1*100:03.0f}_phase{phase:03.0f}.png'
    fig.savefig(path,dpi=145)
    if b1==.8 and phase==45 and snap in [0,5]:fig.savefig(path.with_suffix('.svg'))
    plt.close(fig)


def echo_plot(records,folder):
    fig,axs=plt.subplots(2,3,figsize=(16,9),sharex=True,sharey=True)
    for row,b1 in enumerate([.8,1.]):
        for col,phase in enumerate([0.,45.,90.]):
            ax=axs[row,col]
            for k,(key,title) in enumerate(CASES):
                r=next(r for r in records if r['key']==key and r['b1']==b1 and r['phase']==phase)
                ax.plot(range(1,9),r['ensemble_echoes'],'o-',ms=3,label=title,color=plt.cm.tab10(k))
            ax.set_title(f'RF {b1*100:.0f}% | initial phase {phase:.0f} deg')
            ax.set_xticks(range(1,9));ax.grid(alpha=.2);ax.set_ylim(0,.55)
            if col==0:ax.set_ylabel('|Mean Mxy| / M0')
            if row==1:ax.set_xlabel('Acquired echo')
    fig.legend(*axs[0,0].get_legend_handles_labels(),loc='lower center',ncol=4,fontsize=10,frameon=False)
    fig.suptitle('Coherent voxel signal at ADC middle samples | matched total TE / ESP / ETL\n'
                 'Finite RF, stationary spins; same M0 scale; includes all mixed pathways',fontsize=14)
    fig.tight_layout(rect=(0,.09,1,.92));fig.savefig(folder/'echo_signals.png',dpi=155);fig.savefig(folder/'echo_signals.svg');plt.close(fig)


def timeline_plot(configs,folder):
    fig,axs=plt.subplots(3,4,figsize=(17,10),sharex=True,sharey='col')
    for row,key in enumerate(['original','alsop','ss_mgot']):
        info=next(c for c in configs if c['key']==key and c['phase']==45)
        seq=simulate.read_seq(str(ROOT/info['seq_path']))
        exc=info['initial_excitation_s']
        ids,starts,durations=simulate.block_times(seq)
        for bid,start,duration in zip(ids,starts,durations):
            if start-exc>.09:break
            block=seq.get_block(bid)
            if block.rf is not None:
                rf=block.rf;t=(start+rf.delay+rf.t-exc)*1000
                wave=rf.signal*np.exp(1j*rf.phase_offset)
                axs[row,0].plot(t,wave.real,color='#2166ac',lw=.7)
                axs[row,0].plot(t,wave.imag,color='#d6604d',lw=.7)
            for col,axis in enumerate('xyz',1):
                g=getattr(block,'g'+axis)
                if g is not None:
                    t,a=simulate.grad_pts(g)
                    axs[row,col].plot((t+start-exc)*1000,a/seq.system.gamma*1000,color=COLORS[col-1],lw=.9)
            if block.adc is not None:
                a=block.adc
                for ax in axs[row]:ax.axvspan((start+a.delay-exc)*1000,(start+a.delay+a.num_samples*a.dwell-exc)*1000,
                                            color='#f0ad4e',alpha=.15)
        for col,ax in enumerate(axs[row]):
            ax.set_xlim(-2,86);ax.grid(alpha=.15)
            if row==0:ax.set_title(['Complex RF: real blue / imaginary red','Readout Gx','Spoiler / phase Gy','Slice / recall Gz'][col])
            if row==2:ax.set_xlabel('Time from initial excitation (ms)')
            ax.set_ylabel((info['title']+'\n' if col==0 else '')+('RF (Hz)' if col==0 else 'Gradient (mT/m)'),fontsize=9)
    fig.suptitle('Played model waveforms through ADC2 | shaded regions are acquisition windows\n'
                 'Same first ADC TE / ESP; added storage, spoiler and re-excitation are visible',fontsize=14)
    fig.tight_layout(rect=(0,0,1,.94));fig.savefig(folder/'sequence_timing.png',dpi=150);fig.savefig(folder/'sequence_timing.svg');plt.close(fig)


def gallery(folder):
    options=''.join(f'<option value="{key}">{title}</option>' for key,title in CASES)
    landmarks_options=''.join(f'<option value="{i}">{s}</option>' for i,s in enumerate(LANDMARKS))
    html='''<!doctype html><html><head><meta charset="utf-8"><title>Alsop and ss-MGOT comparisons</title><style>
body{font:16px system-ui;margin:24px;background:#f8fafc;color:#172033}select{font:inherit;padding:8px;margin:6px}img{width:100%;background:white}p{max-width:1100px}</style></head><body>
<h1>Prepared FSE compared with crusher variants</h1><p>Two research adaptations implement the Alsop and ss-MGOT preparation mechanisms, with common fixed-180° imaging RF. These water-only models use a spatial sinc tip-up rather than the paper’s spectral-spatial pulse. They do not reproduce its full scanner protocol. All methods have first ADC midpoint TE 64 ms, ESP 16 ms and eight echoes. Original means the v1.6 source with these comparison overrides; centered original separates the RF-centering correction used in the prepared models.</p>
<label>Sequence <select id="method">OPTIONS</select></label><label>RF strength <select id="b1"><option value="080">80%</option><option value="100">100%</option></select></label><label>Initial phase <select id="phase"><option value="045">45°</option><option value="000">0°</option><option value="090">90°</option></select></label><label>Profile <select id="mode"><option value="average">Coherent mean over y</option><option value="local">Local x=y=0</option></select></label>
<img id="detail" alt="Magnetization components at six landmarks"><h2>All methods at one landmark</h2><select id="time">LANDMARKS</select><img id="compare" alt="Sequence comparison"><h2>Acquired voxel signal</h2><img src="echo_signals.png" alt="Echo signals"><h2>Preparation and imaging timing</h2><img src="sequence_timing.png" alt="Played waveforms">
<p>Gy spoiling removes the coherent transverse mean, rather than the local transverse vector. The mean-over-y view includes this effect. Mz includes stored signal, equilibrium, inversion and recovery; it is not a stimulated-echo fraction. No molecular diffusion attenuation or image reconstruction is simulated.</p>
<script>function update(){const v=document.getElementById('method').value,b=document.getElementById('b1').value,p=document.getElementById('phase').value,m=document.getElementById('mode').value,t=document.getElementById('time').value;document.getElementById('detail').src=`${v}_rf${b}_phase${p}_${m}.png`;document.getElementById('compare').src=`compare_t${t}_rf${b}_phase${p}.png`;}['method','b1','phase','mode','time'].forEach(x=>document.getElementById(x).onchange=update);update();</script></body></html>'''
    (folder/'index.html').write_text(html.replace('OPTIONS',options).replace('LANDMARKS',landmarks_options),encoding='utf-8')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--grid',type=int,default=4097);ap.add_argument('--n',type=int,default=8192)
    ap.add_argument('--workers',type=int,default=4);ap.add_argument('--prefill',action='store_true')
    ap.add_argument('--reuse',action='store_true');ap.add_argument('--build-only',action='store_true')
    ap.add_argument('--validate-only',action='store_true',help='reuse figures and recheck data/provenance')
    ap.add_argument('--cases',help='comma-separated subset for raw prefill/build only')
    args=ap.parse_args()
    chosen=CASES if not args.cases else [c for c in CASES if c[0] in args.cases.split(',')]
    if args.cases and not (args.prefill or args.build_only):raise ValueError('case subsets are for prefill/build only')
    raw=ROOT/'runs/prepared_fse_comparison';folder=ROOT/'docs/figures/prepared_fse_comparison'
    data=ROOT/'docs/data';exports=ROOT/'examples/sequences'
    for p in [raw,folder,data,exports]:p.mkdir(parents=True,exist_ok=True)
    configs=[]
    for key,title in CASES:
        for phase in [0.,45.,90.]:
            seq,info=build(key,phase)
            times,adcs=landmarks(seq,info)
            path=raw/f'{key}_phase{phase:03.0f}.seq';seq.write(str(path))
            loaded=simulate.read_seq(str(path));assert loaded.check_timing()[0]
            info.update(phase=phase,snapshot_times_s=times.tolist(),adc=adcs,
                        seq_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),seq_path=str(path.relative_to(ROOT)))
            configs.append(info)
            if key in ['alsop','ss_mgot'] and phase==45:
                export=exports/f'{key}_adapted.seq';seq.write(str(export))
    if args.build_only:
        (raw/'build.json').write_text(json.dumps(configs,indent=2),encoding='utf-8');print('Built all sequences',flush=True);return
    jobs=[(key,phase,b1,args.grid,args.n) for key,_ in chosen for phase in [0.,45.,90.] for b1 in [.8,1.]]
    pending=[j for j in jobs if not args.reuse or not (raw/f'{j[0]}_rf{j[2]*100:03.0f}_phase{j[1]:03.0f}.npz').exists()]
    if args.prefill:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for tag in pool.map(simulate_job,pending):print(tag,'simulated',flush=True)
        return
    for job in pending:print(simulate_job(job),'simulated',flush=True)
    records,rows,checks=[],[],[]
    for key,phase,b1,grid,n in jobs:
        tag=f'{key}_rf{b1*100:03.0f}_phase{phase:03.0f}'
        saved=np.load(raw/(tag+'.npz'))
        assert saved['grid']==args.grid and saved['n']==args.n
        info=next(c for c in configs if c['key']==key and c['phase']==phase)
        seq=simulate.read_seq(str(ROOT/info['seq_path']))
        m=np.array([saved['mx'],saved['my'],saved['mz']]).transpose(1,0,2)
        times=np.array(info['snapshot_times_s'])
        assert np.allclose(saved['times_s'],times,rtol=0,atol=1e-12)
        assert np.isfinite(m).all();assert np.max(np.linalg.norm(m,axis=1))<1.000001
        edges=np.cumsum(np.r_[0,saved['adc_sizes']]);closure=[]
        for snap,e in [(2,0),(3,1),(5,7)]:
            a=info['adc'][e]
            demod=np.exp(-1j*(a['phase_rad']+2*np.pi*a['frequency_hz']*(times[snap]-a['start_s'])))
            closure.append(float(abs(np.mean(m[snap,0]+1j*m[snap,1])*demod-saved['signal'][edges[e]+a['sample_index']])))
        assert max(closure)<1e-10
        r=dict(key=key,title=dict(CASES)[key],b1=b1,phase=phase,z=saved['z'],m=m,
               relative_ms=(times-info['initial_excitation_s'])*1000,ensemble_echoes=[],
               pe_moments=pe_moments(seq,info,times))
        # The final n entries are the original voxel support, not line points.
        # Per-spin evolution is independent: extract and average only the
        # voxel population, rather than the artificial mixed line/voxel set.
        for e,state in enumerate(saved['voxel_echo_states']):
            a=info['adc'][e];t=a['sample_s']
            demod=np.exp(-1j*(a['phase_rad']+2*np.pi*a['frequency_hz']*(t-a['start_s'])))
            expected=np.mean(state[0]+1j*state[1])*demod
            r['ensemble_echoes'].append(float(abs(expected)))
            rows.append(dict(key=key,phase_deg=phase,b1=b1,echo=e+1,time_ms=(t-info['initial_excitation_s'])*1000,
                 magnitude=float(abs(expected)),mean_mx=float(state[0].mean()),mean_my=float(state[1].mean()),
                 mean_mz=float(state[2].mean()),mean_local_transverse=float(np.hypot(state[0],state[1]).mean())))
        for snap,e in [(2,0),(3,1),(5,7)]:
            error=float(np.max(np.abs(m[snap,:,-n:]-saved['voxel_echo_states'][e])))
            assert error<1e-10
        records.append(r)
        if not args.validate_only:
            for mode in ['average','local']:plot_profiles(r,grid,mode,folder/(tag+'_'+mode+'.png'))
        checks.append(dict(tag=tag,complex_adc_closure_max=max(closure)))
        print(tag,'figures checked',flush=True)
    if not args.validate_only:
        for b1 in [.8,1.]:
            for phase in [0.,45.,90.]:
                for snap in range(6):comparison(records,args.grid,b1,phase,snap,folder)
        echo_plot(records,folder);timeline_plot(configs,folder);gallery(folder)
    # Dense, independent y quadrature checks the analytic harmonic integral,
    # including the readout's PE phase, re-excitation and subsequent RF.
    for key in ['alsop','ss_mgot','centered_original']:
        seq,info=build(key,45);times,_=landmarks(seq,info)
        z=np.linspace(-.001,.001,65)
        v=voxel(65,1,phase_points=256)
        result=simulate.simulate(seq,b1=.8,voxel=v,snap_times=times,rf_dt=4e-6)
        m=np.array([s[1:] for s in result['snapshots']])
        mean_dense=m[:,:,65:257*65].reshape(6,3,256,65).mean(axis=2)
        r=next(r for r in records if r['key']==key and r['phase']==45 and r['b1']==.8)
        thin=profiles(r['m'],args.grid,'average',r['pe_moments'])[:,:,::64]
        error=float(np.max(abs(mean_dense-thin)))
        assert error<3e-5,error
        checks.append(dict(tag=key,analytic_y_mean_vs_256_point_max_component_error=error))
        line=dict(x=np.zeros(1025),y=np.zeros(1025),z=np.linspace(-.001,.001,1025),df=np.zeros(1025))
        runs=[simulate.simulate(seq,b1=.8,voxel=line,snap_times=times,rf_dt=step) for step in [4e-6,2e-6]]
        arrays=[np.array([s[1:] for s in result['snapshots']]) for result in runs]
        error=float(np.max(abs(arrays[0]-arrays[1])))
        assert error<.003,error
        checks.append(dict(tag=key,rf_step_4us_vs_2us_max_component_error=error))
        # Independent voxel-only ADC simulation verifies extraction, receiver
        # demodulation and all eight displayed echo magnitudes.
        saved=np.load(raw/f'{key}_rf080_phase045.npz')
        v={k:saved[k][-args.n:] for k in ['x','y','z','df']}
        result=simulate.simulate(seq,b1=.8,voxel=v,rf_dt=4e-6)
        error=float(np.max(abs(result['echo_center']-r['ensemble_echoes'])))
        assert error<1e-10,error
        checks.append(dict(tag=key,independent_voxel_adc_magnitude_max_error=error))
    for key in ['original','increasing','decreasing','alternating','alsop','ss_mgot']:
        r=next(r for r in records if r['key']==key and r['phase']==45 and r['b1']==.8)
        m=profiles(r['m'],args.grid,'local')
        error=float(np.max(abs(m[:,:,1::2]-(m[:,:,:-2:2]+m[:,:,2::2])/2)))
        checks.append(dict(tag=key,half_grid_interpolation_max_component_error=error))
        # The half-grid diagnostic compares 2049 to 4097 samples: it is not
        # the interpolation error of the displayed 4097-point curves. Test
        # the two most oscillatory crusher schedules on a doubled grid.
        if key in ['increasing','decreasing']:
            seq,info=build(key,45);times,_=landmarks(seq,info)
            fine_n=2*args.grid-1
            v=dict(x=np.zeros(fine_n),y=np.zeros(fine_n),z=np.linspace(-.001,.001,fine_n),df=np.zeros(fine_n))
            result=simulate.simulate(seq,b1=.8,voxel=v,snap_times=times,rf_dt=4e-6)
            fine=np.array([s[1:] for s in result['snapshots']])
            error=float(np.max(abs(fine[:,:,1::2]-(m[:,:,:-1]+m[:,:,1:])/2)))
            assert error<.01,error
            checks.append(dict(tag=key,display_grid_interpolation_vs_doubled_grid_max_component_error=error))
    with (data/'prepared_fse_comparison.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    source_paths=['examples/compare_prepared_fse.py','dwfse/generate.py','dwfse/simulate.py',
                  'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.6.ppl','scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.6.ppr']
    provenance=dict(protocol='TE64ms ESP16ms ETL8 fixed180 imaging; water-only stationary mechanism models',
        source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_paths},
        dependencies={p:importlib.metadata.version(p) for p in ['numpy','matplotlib','pypulseq']},
        grid=args.grid,ensemble_n=args.n,rf_dt_s=4e-6,voxel_xy_mm=.2,voxel_z_mm=2,T1_s=1.5,T2_s=.08,T2prime_s=.03,
        line='x=y=df=0; mean-y profiles use analytic harmonic integration including PE, checked against 256 points',
        reference='Gibbons et al. DOI 10.1002/mrm.26971; Alsop DOI 10.1002/mrm.1910380404',
        paper_sha256=hashlib.sha256(Path('C:/Users/jaden/Downloads/Gibbons_2017.pdf').read_bytes()).hexdigest(),
        configurations=configs,checks=checks)
    (data/'prepared_fse_provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    print('Complete',folder/'index.html',flush=True)


if __name__=='__main__':main()
