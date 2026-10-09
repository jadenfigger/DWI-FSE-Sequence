import sys,json;sys.path.insert(0,'.')
from pathlib import Path
from dwfse.ppl.run import map_events
from dwfse.ppl.events import rf_pulses
from examples.validate_v181_guards import unsafe_cases
from examples.v19_validate_events import COST_MODELS
S=Path(sys.argv[1])
OLD=S/'old_9fca.ppl'; NEW=Path('scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl'); PPR=Path('scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppr')
cases=dict(unsafe_cases())
cases.update({"mtc":{"mtc_on":1},"mtc_diffoff":{"mtc_on":1,"diff_on":0},"mtc_flow":{"mtc_on":1,"flow_comp_on":1},"mtc_te_short":{"mtc_on":1,"te":2},
 "mtc_array":{"mtc_on":1,"mtc_array_on":1},"flow_te_ok":{"flow_comp_on":1,"te":60},"flow_diffoff_ok":{"diff_on":0,"flow_comp_on":1,"te":40,"esp":18},
 "relo_dac_te60":{"te":60,"crusher_max_dac":100},"relo_slew":{"te":60,"crusher_slew_dac_100us":10},"relo_ok_crush_indep":{"crush_independent_on":1,"crusher_max_dac":32767}})
def run(p,ov,val,m):
    o=dict(ov); o['validate']=val
    it=map_events(p,PPR,overrides=o,max_shots=1,rf_latency_us=3.0,**m)
    return len([x for x in rf_pulses(it) if x.get('library')]),len(it.adc),[m_[1].strip() for m_ in it.out][-1:]
rows=[]
for n,ov in cases.items():
  for val in (0,1):
    for mn in ("flat_0us","manual_x1.0"):
      m=COST_MODELS[mn]
      a=run(OLD,ov,val,m); b=run(NEW,ov,val,m)
      rows.append((n,val,mn,a,b))
      flag = "" if a[2]==b[2] else "  <-- msg differs"
      if mn=="manual_x1.0" or flag: print(f"{n:34s} v{val} {mn:12s} old{a} new{b}{flag}")
