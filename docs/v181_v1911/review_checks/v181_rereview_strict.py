import sys,json;sys.path.insert(0,'.')
from pathlib import Path
from dwfse.ppl.run import map_events
from dwfse.ppl.events import rf_pulses
from examples.v19_validate_events import COST_MODELS
S=Path(sys.argv[1])
OLD=S/'old_9fca.ppl'; NEW=Path('scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl'); PPR=Path('scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppr')
def R(x): return round(x,4)
def sig(it):
    lib=[p for p in it.rf.events if p.get('library')]
    t0=lib[0]['t_go']
    ev=[]
    for p in it.rf.events:
        if p['t_go']>=t0-1e-9: ev.append(('rf',R(p['t_go']-t0),p.get('frame'),p['mul'],p.get('phase_deg'),p.get('tx_freq_hz'),p['level'],p.get('gate')))
    for a in it.adc:
        ev.append(('adc',R(a['t_init']-t0),R(a['sync_t']-t0) if a.get('sync_t') is not None else None,R((a.get('t_complete') or 0)-t0),a['sample_period_ticks'],a['rx_phase_deg'],a['rx_freq_hz'],a['dummy_cycles'],a['discard']))
    for ax,c in it.grad.ch.items():
        for s in c.segments:
            if s[1]>t0: ev.append(('g'+ax,R(max(s[0],t0)-t0),R(s[1]-t0))+tuple(s[2:]))
    for m in it.misc_events:
        if m[1]>=t0: ev.append(('misc',m[0],R(m[1]-t0))+tuple(m[2:]))
    fl=[(f['kind'],R(f['t_us']-t0),f['msg']) for f in it.flags if f['t_us']>=t0 and f['kind'] not in('narrowing',)]
    return sorted(ev,key=str),sorted(fl,key=str),len(lib),[o[1] for o in it.out]
states={"flow_diffoff":({"diff_on":0,"flow_comp_on":1,"te":40},1),"tref1500":({"tref_setup":1500,"te":60},1),"tramp300":({"tramp":300,"diff_tramp":300,"te":60},1),"flow_diffoff_diffTE":({"diff_on":0,"flow_comp_on":1,"te":40,"esp":18},1)}
tot=0;bad=0
for sn,(ov,sh) in states.items():
  for mn,m in COST_MODELS.items():
    try:
        a=sig(map_events(OLD,PPR,overrides=ov,max_shots=sh,rf_latency_us=3.0,**m)); b=sig(map_events(NEW,PPR,overrides=ov,max_shots=sh,rf_latency_us=3.0,**m))
    except Exception as e:
        print(sn,mn,"EXC",repr(e)[:120]); continue
    tot+=1
    same=[a[i]==b[i] for i in range(4)]
    if not all(same):
        bad+=1
        d=[k for k,v in zip(('events','flags','nrf','printf'),same) if not v]
        print(sn,mn,"DIFF",d,"nrf",a[2],b[2],(a[3][-1:],b[3][-1:]) if 'printf' in d else '')
        if 'events' in d:
            sa=set(map(str,a[0])); sb=set(map(str,b[0])); print("   only old",list(sa-sb)[:3],"only new",list(sb-sa)[:3])
        if 'flags' in d: print("   flags old",[f for f in a[1] if f not in b[1]][:3],"new",[f for f in b[1] if f not in a[1]][:3])
    else: print(sn,mn,"identical",a[2],"RF", len(a[0]),"events")
print("cases",tot,"differing",bad)
