import sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from dwfse.ppl.run import map_events
from dwfse.ppl.ledger import build_ledger
from examples.v19_validate_events import COST_MODELS
SC=ROOT/'scanner'
V7=ROOT/'docs/v181_v1911/baseline_v7'
t=time.time()
ov={'no_disacq':0,'nav_on':0,'no_views':128}
it=map_events(SC/'FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl',SC/'FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppr',max_shots=3,overrides=ov,**COST_MODELS['flat_0us'])
print(time.time()-t)
print(it.flags[:20])
print(len(it.flags))
print([o for o in it.out][:10])
led=build_ledger(it,1)
print(len(led['rf']),len(led['adc']),led['t_start'],led['t_end'])
print(led['issues'])
print([ (p['frame'],round(p['t_go'],1)) for p in led['rf']])
print([ (round(a['t_init'],1),round(a['t_complete'],1)) for a in led['adc']])
print(it.vars['esp'].value, it.vars['tr'].value if 'tr' in it.vars else None)
print([e for e in it.misc_events][:10])
