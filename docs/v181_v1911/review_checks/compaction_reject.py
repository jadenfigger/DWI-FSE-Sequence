import sys,json,hashlib;sys.path.insert(0,'.')
from pathlib import Path
from dwfse.ppl.run import map_events
from dwfse.ppl.events import rf_pulses
from examples.validate_v181_guards import unsafe_cases
from examples.v19_validate_events import NOMINAL
OLD=Path(sys.argv[1]);NEW=Path('scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl');PPR=Path('scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppr')
cases=dict(unsafe_cases())
cases.update({"cest_mtc_on":{"mtc_on":1},"cest_mtc_on_diff_off":{"mtc_on":1,"diff_on":0},"cest_mtc_on_array":{"mtc_on":1,"mtc_array_on":1},
              "validator_default":{"validate":1},"validator_cest":{"validate":1,"mtc_on":1}})
def run(p,ov):
    it=map_events(p,PPR,overrides=ov,max_shots=1,rf_latency_us=3.0,**NOMINAL)
    return {"RF":len([x for x in rf_pulses(it) if x.get('library')]),"ADC":len(it.adc),"messages":[m[1] for m in it.out]}
out={"old_sha256":hashlib.sha256(OLD.read_bytes()).hexdigest(),"new_sha256":hashlib.sha256(NEW.read_bytes()).hexdigest(),"model":"manual_x0.8","cases":{}}
for n,ov in cases.items():
    a,b=run(OLD,ov),run(NEW,ov)
    r={"old":a,"new":b,"same_messages":a["messages"]==b["messages"],"new_rejected_before_RF":b["RF"]==0 and b["ADC"]==0}
    out["cases"][n]=r;print(n,r["same_messages"],r["new_rejected_before_RF"],b["messages"][-1:] ,a["RF"],flush=True)
Path(sys.argv[2]).write_text(json.dumps(out,indent=1)+"\n")
