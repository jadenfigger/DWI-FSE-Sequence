import sys;sys.path.insert(0,'.')
from pathlib import Path
from dwfse.ppl.run import map_events
S=Path(sys.argv[1])
OLD=S/'old_9fca.ppl'; NEW=Path('scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl'); PPR=Path('scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppr')
def first(p,sc):
    it=map_events(p,PPR,max_shots=1,rf_latency_us=3.0,stmt_cost_us=0.0,expr_costs=True,expr_scale=sc)
    f=[x for x in it.flags if x['kind']=='timer_overrun']
    return f[0]['msg'] if f else None
for name,p in (('old',OLD),('new',NEW)):
    lo,hi=1.0,1.2
    while hi-lo>0.0005:
        m=(lo+hi)/2
        if first(p,m): hi=m
        else: lo=m
    print(name,'first overrun scale ~',round(hi,4),first(p,hi))
