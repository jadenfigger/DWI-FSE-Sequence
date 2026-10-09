import sys,json,hashlib;sys.path.insert(0,'.')
from pathlib import Path
from dwfse.ppl.run import map_events
from dwfse.ppl.events import rf_pulses
from examples.v19_validate_events import COST_MODELS
OLD=Path(sys.argv[1]); NEW=Path('scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl'); PPR=Path('scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppr')
def norm(x):
    if isinstance(x,dict): return {str(k):norm(v) for k,v in sorted(x.items(),key=lambda kv:str(kv[0]))}
    if isinstance(x,(list,tuple)): return [norm(v) for v in x]
    if isinstance(x,float): return round(x,6)
    if isinstance(x,(int,str,bool,type(None))): return x
    if hasattr(x,'tolist'): return norm(x.tolist())
    if hasattr(x,'__dict__'): return norm(vars(x))
    return repr(x)
def sig(it):
    g=it.grad
    return {"rf_events":norm(it.rf.events),"rf_level":norm(it.rf.level_hist),"adc":norm(it.adc),"misc":norm(it.misc_events),
            "flags":norm(it.flags),"grad_starts":norm(g.starts),"grad_sel":norm(g.sel_hist),"grad_clock":norm(g.clock_hist),
            "grad_channels":{a:norm(vars(c)) for a,c in g.ch.items()},
            "mats_excl_mtc":norm({k:v for k,v in g.mats.items() if k!=25}),"mtc_mat_present":25 in g.mats,
            "printf":norm(it.out),"shots":it.shots,"t_end":round(it.t,3),
            "rf":len([p for p in rf_pulses(it) if p.get('library')])}
states={"default_6shots":({},6),"imaging_2shots":({"no_disacq":0,"nav_on":0,"no_views":128},2),
        "diff_off":({"diff_on":0},2),"mtc_on":({"mtc_on":1},2),"flow_comp_dwi":({"flow_comp_on":1},1)}
res={"old_sha256":hashlib.sha256(OLD.read_bytes()).hexdigest(),"new_sha256":hashlib.sha256(NEW.read_bytes()).hexdigest(),
     "ppr_sha256":hashlib.sha256(PPR.read_bytes()).hexdigest(),"rf_latency_us":3.0,"cases":{}}
for sn,(ov,shots) in states.items():
  for mn,m in COST_MODELS.items():
    if sn not in("default_6shots","imaging_2shots") and mn not in("flat_0us","manual_x0.8"): continue
    a=sig(map_events(OLD,PPR,overrides=ov,max_shots=shots,rf_latency_us=3.0,**m))
    b=sig(map_events(NEW,PPR,overrides=ov,max_shots=shots,rf_latency_us=3.0,**m))
    diff=[k for k in a if a[k]!=b[k]]
    r={"overrides":ov,"shots_requested":shots,"identical_except_listed":diff,"rf":[a["rf"],b["rf"]],"adc":[len(a["adc"]),len(b["adc"])],
       "t_end":[a["t_end"],b["t_end"]],"mtc_mat_present":[a["mtc_mat_present"],b["mtc_mat_present"]]}
    if "printf" in diff: r["printf_tail"]=[a["printf"][-2:],b["printf"][-2:]]
    res["cases"][f"{sn}/{mn}"]=r; print(sn,mn,r,flush=True)
Path(sys.argv[2]).write_text(json.dumps(res,indent=1)+"\n")
