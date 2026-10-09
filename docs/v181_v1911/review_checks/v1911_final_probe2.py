import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from dwfse.ppl.run import map_events
from dwfse.ppl.ledger import build_ledger
from examples.v19_validate_events import COST_MODELS
SC=ROOT/'scanner'
ov={'no_disacq':0,'nav_on':0,'no_views':128}
it=map_events(SC/'FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl',SC/'FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppr',max_shots=3,overrides=ov,**COST_MODELS['flat_0us'])
led=build_ledger(it,1)
last=led['adc'][-1]; print('last adc',last['t_init'],last['t_complete'])
for ax in 'SPR':
    print(ax)
    ch=it.grad.ch[ax]
    for s in ch.segments:
        if 183000<s[0]<196000 and (s[2] or s[3]): print('  ',[round(x,1) for x in s])
print([ (e) for e in it.grad.mats.get(259,[])[-4:]])
print([ (e) for e in it.grad.mats.get(3,[])[-3:]])
print(it.grad.sel_hist[-6:])
print([ (e[0],round(e[1],1)) for e in it.misc_events if 183000<e[1]<400000][:40])
