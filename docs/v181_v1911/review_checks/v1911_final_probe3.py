import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from dwfse.ppl.run import map_events
from dwfse.ppl.ledger import build_ledger
from examples.v19_validate_events import COST_MODELS
SC=ROOT/'scanner'
for lab,(ppl,ppr) in {'v7':(ROOT/'docs/v181_v1911/baseline_v7/FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl',ROOT/'docs/v181_v1911/baseline_v7/FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppr'),'v1911':(SC/'FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl',SC/'FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppr')}.items():
    it=map_events(ppl,ppr,max_shots=7,**COST_MODELS['flat_0us'])
    print(lab,[ (e[1]) for e in it.misc_events if e[0]=='shot'])
    for n in range(1,8):
        led=build_ledger(it,n)
        a=led['adc']
        v=[x['vars'] for x in a]
        print(n,len(led['rf']),len(a),[ (x.get('nav_cnt'),x.get('gp_mul'),x.get('diff_acq_cnt'),x.get('disacq_cnt'),x.get('current_view')) for x in v[:2]], led['t_start'], led['t_end'])
