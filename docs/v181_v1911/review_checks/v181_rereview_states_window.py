import sys;sys.path.insert(0,'.')
from pathlib import Path
from dwfse.ppl.run import map_events
S=Path(sys.argv[1])
OLD=S/'old_9fca.ppl'; NEW=Path('scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl'); PPR=Path('scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppr')
st={"default":{},"te60":{"te":60},"sat":{"sat_on":1},"chess":{"chess_on":1},"indep":{"crush_independent_on":1,"crusher_schedule":3,"crusher_step_pct":25,"crush_amp":3000,"diff_crush_amp":3000},
"oblique":{"subj_angle_x":300,"subj_angle_y":200,"subj_angle_z":100},"slice_off":{"slice_mm_10":500},"tr800":{"tr":800},"esp18":{"esp":18}}
def slack(p,ov,sc):
    it=map_events(p,PPR,overrides=ov,max_shots=2,rf_latency_us=3.0,stmt_cost_us=0.0,expr_costs=True,expr_scale=sc)
    s=[tk-u for wh,tk,u in it.window_use if tk==32500]
    ovr=[f['msg'] for f in it.flags if f['kind']=='timer_overrun']
    return (round(min(s),1) if s else None), len(ovr), ovr[:1]
for n,ov in st.items():
    for sc in (0.8,1.0):
        a=slack(OLD,ov,sc); b=slack(NEW,ov,sc)
        print(f"{n:9s} x{sc} 32500 slack ticks old {a[0]} new {b[0]}  overruns old {a[1]} new {b[1]} {b[2]}")
