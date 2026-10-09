import sys,json;sys.path.insert(0,'.')
from pathlib import Path
from collections import defaultdict
from dwfse.ppl.run import map_events
S=Path(sys.argv[1])
OLD=S/'old_9fca.ppl'; NEW=Path('scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl'); PPR=Path('scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppr')
states={"default":({},3),"imaging":({"no_disacq":0,"nav_on":0,"no_views":128},2),"diff_off":({"diff_on":0},2)}
def run(p,ov,sh,sc,stmt=0.0):
    it=map_events(p,PPR,overrides=ov,max_shots=sh,rf_latency_us=3.0,stmt_cost_us=stmt,expr_costs=True,expr_scale=sc)
    w=defaultdict(lambda:[1e18,None])
    for wh,tk,u in it.window_use:
        if tk in (32500,32750,42500,6500,8997,1000,31000,19700,30000,27500):
            sl=tk-u
            if sl<w[tk][0]: w[tk]=[sl,str(wh[-1]) if isinstance(wh,(list,tuple)) else str(wh)]
    ov_=[(f['t_us'],f['msg']) for f in it.flags if f['kind']=='timer_overrun']
    return {k:round(v[0],1) for k,v in w.items()}, ov_[:3], len(ov_)
res={}
for sn,(ov,sh) in states.items():
    for sc in (0.8,0.9,1.0,1.05,1.08,1.09,1.1):
        a=run(OLD,ov,sh,sc); b=run(NEW,ov,sh,sc)
        res[f"{sn}/{sc}"]={"old":a,"new":b}
        print(sn,sc,"OLD",a[0],a[2],a[1][:1],"\n          NEW",b[0],b[2],b[1][:1],flush=True)
