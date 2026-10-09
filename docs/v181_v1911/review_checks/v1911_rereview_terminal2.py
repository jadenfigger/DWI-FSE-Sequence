"""Terminal list-end vs waittimer(40000) exit, receiver-busy overlap, next list start; acqpad sweep."""
from v1911_rereview_common import *
import json
from functools import partial
import dwfse.ppl.run as runmod
from dwfse.ppl.interp import Interp
from dwfse.ppl.ledger import list_starts, list_duration_us
def run_ac(model,acq,imaging=True,shots=2,ov=None):
    orig=runmod.Interp
    runmod.Interp=partial(Interp,acqpad_ticks=acq)
    try: return run('v1911',model,imaging,shots=shots,overrides=ov)
    finally: runmod.Interp=orig
def analyze(it,n=1):
    led=build_ledger(it,n); ts,te=led['t_start'],led['t_end']
    la=led['adc'][-1]; tc=la['t_complete']
    wt=[(w,tk,t) for (w,tk,t) in [(None,e[2],e[1]) for e in it.misc_events if e[0]=='waittimer' and ts<=e[1]<te]]
    # sequence of waittimers after last ADC init
    after=[(tk,t) for (_,tk,t) in wt if t>la['t_init']]
    # first 24000,28000,40000 (-25536->40000) after
    tm={tk:t for tk,t in after if tk in (24000,28000,40000)}
    starts=list_starts(it,led,'v1911_l_end')
    dur=list_duration_us(it,'v1911_l_end')
    r={'adc_complete':round(tc-ts,1),'wt24':round(tm.get(24000,0)-tc,1),'wt28':round(tm.get(28000,0)-tc,1),'wt40':round(tm.get(40000,0)-tc,1),
       'list_start':[(round(t-tc,1),a) for t,a in starts],'list_dur':dur,
       'list_end_minus_wt40':[round(t+dur-tm.get(40000,0),1) for t,a in starts],
       'nextwaits_after_wt40':[(tk,round(t-tc,1)) for tk,t in after if t>tm.get(40000,1e18)][:3]}
    # S starts after wt40 (post-ETL crusher list)
    Ss=[(round(t-tc,1),ad) for t,a,ad in it.grad.starts if a is not None and t>tm.get(40000,1e18) and t<te][:4]
    r['gradstarts_after_wt40']=Ss
    # terminal S lobe overlap with receiver busy (all adcs), with 0 and 60us shift
    G=led['G']['S']
    St=[l for l in lobes(G,la['t_init'],te)]
    tsl=St[0] if St else None
    r['S_first_lobe_after_last_init_rel_complete']=[round(x-tc,1) for x in tsl[:2]] if tsl else None
    mx=0
    for a in led['adc']:
        for sh in (0,60.0,100.0):
            for (x,y,ar,pk) in St[:1]:
                lo=max(x+sh,a['t_init']);hi=min(y+sh,a['t_complete'])
                mx=max(mx,hi-lo)
    r['terminal_S_busy_overlap_max_us']=round(max(mx,0),2)
    r['S_lobes_all_after_last_init']=[(round(a-tc,1),round(b-tc,1),round(ar),round(pk)) for a,b,ar,pk in St]
    r['overruns']=[f['msg'] for f in it.flags if f['kind']=='timer_overrun'][:3]
    r['ignored']=[f['msg'] for f in it.flags if 'ignored' in f['msg']][:3]
    r['issues']={ax:len(led['issues'][ax]) for ax in 'SPR'}
    r['err']=[o[1].strip() for o in it.out if 'V19' in o[1]][-1:]
    return r
out={'models':{},'acq':{}}
for model in COST_MODELS:
    it=run('v1911',model,True,shots=3)
    out['models'][model]=[analyze(it,n) for n in (1,3)]
    print(model,out['models'][model][0])
for acq in (3730,4000,4200,4600,4800,5000,5100,5500,6000,7500):
    for model in ('flat_0us','manual_x0.8'):
        it=run_ac(model,acq)
        err=[o[1].strip() for o in it.out if 'V19' in o[1]]
        nrf=len([e for e in it.rf_events]) if hasattr(it,'rf_events') else None
        try: r=analyze(it,1)
        except Exception as e: r={'exc':repr(e)}
        out['acq'][f'{acq}|{model}']={'err':err[-2:],'adc':len(it.adc),'analysis':r}
        print('acq',acq,model,'adc',len(it.adc),err[-2:], {k:r.get(k) for k in ('wt24','wt28','wt40','list_end_minus_wt40','terminal_S_busy_overlap_max_us','overruns','ignored','issues','S_first_lobe_after_last_init_rel_complete')} if 'exc' not in r else r)
json.dump(out,open('v1911_rereview_terminal2.json','w'),indent=1,default=float)
