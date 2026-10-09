import sys,json,hashlib;sys.path.insert(0,'.')
from pathlib import Path
from dwfse.ppl.run import map_events
from dwfse.ppl.events import rf_pulses
from examples.v19_validate_events import COST_MODELS
OLD=Path(sys.argv[1]);NEW=Path('scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl');PPR=Path('scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppr')
def tl(it):
    rf=[p for p in rf_pulses(it) if p.get('library')]
    t0=rf[0]['t_go']
    R=[(p['t_go']-t0,p['frame'],p['mul'],p['phase_units'],p['tx_freq_hz'],p['duration_us'],p['level']) for p in rf]
    A=[(a['t_init']-t0,a['rx_phase_units'],a['rx_freq_hz'],a['sample_period_ticks'],(a.get('t_complete') or 0)-t0) for a in it.adc]
    G={}
    for ax,c in it.grad.ch.items():
        segs=[]
        for s in c.segments:
            if s[0]<t0-200000: continue  # ignore setup-era zero lists far before first RF? keep all after
            v=tuple(s[2:])
            if segs and segs[-1][2]==v and abs(segs[-1][1]-s[0])<1e-6: segs[-1]=(segs[-1][0],s[1],v)
            else: segs.append((s[0],s[1],v))
        G[ax]=[(a-t0,b-t0,v) for a,b,v in segs if any(v)]
    flags=sorted({f['kind'] for f in it.flags})
    return R,A,G,flags,[f for f in it.flags if f['kind'] not in('narrowing','matrix_active')]
def cmp(x,y):
    if len(x)!=len(y): return {"length":[len(x),len(y)]}
    dt=0;other=0
    for a,b in zip(x,y):
        ta=[v for v in a if isinstance(v,float)] ; 
        dt=max([dt]+[abs(a[i]-b[i]) for i in range(len(a)) if isinstance(a[i],(int,float)) and i in(0,1) and isinstance(a[0],float)] if False else [dt])
        for i,(u,v) in enumerate(zip(a,b)):
            if isinstance(u,float) and isinstance(v,float) and i<2 or (isinstance(u,float) and i==len(a)-1 and len(a)==5): dt=max(dt,abs(u-v))
            elif u!=v: other+=1
    return {"max_time_diff_us":round(dt,6),"non_time_mismatches":other}
states={"default_6shots":({},6),"imaging_2shots":({"no_disacq":0,"nav_on":0,"no_views":128},2),"diff_off_2shots":({"diff_on":0},2)}
out={"old_sha256":hashlib.sha256(OLD.read_bytes()).hexdigest(),"new_sha256":hashlib.sha256(NEW.read_bytes()).hexdigest(),"note":"times relative to first library RF of each run","cases":{}}
for sn,(ov,sh) in states.items():
  for mn,m in COST_MODELS.items():
    a=tl(map_events(OLD,PPR,overrides=ov,max_shots=sh,rf_latency_us=3.0,**m)); b=tl(map_events(NEW,PPR,overrides=ov,max_shots=sh,rf_latency_us=3.0,**m))
    r={"rf":cmp(a[0],b[0]),"adc":cmp(a[1],b[1]),"grad":{ax:cmp(a[2][ax],b[2][ax]) for ax in a[2]},"flag_kinds":[a[3],b[3]],"bad_flags":[len(a[4]),len(b[4])]}
    out["cases"][f"{sn}/{mn}"]=r;print(sn,mn,json.dumps(r),flush=True)
Path(sys.argv[2]).write_text(json.dumps(out,indent=1)+"\n")
