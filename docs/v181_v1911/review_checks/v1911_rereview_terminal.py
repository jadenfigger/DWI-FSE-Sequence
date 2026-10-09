"""Terminal block timing re-review of 716478bb: all 8 cost models, imaging + default PPR, v1911 vs v7."""
from v1911_rereview_common import *
import json, sys
from collections import Counter
assert sha(SEQ['v1911'][0])==EXPECT_SHA['v1911'], sha(SEQ['v1911'][0])
def last_nz(G,t0,t1):
    L=lobes(G,t0,t1)
    return L
out={}
for model in COST_MODELS:
  for imaging in (True,False):
    it=run('v1911',model,imaging)  # 3 shots (imaging) / 8 (default)
    nshots=len([e for e in it.misc_events if e[0]=='shot'])-1
    key=f'{model}|{"img" if imaging else "default"}'
    rec={'nshots':nshots,'flags':dict(Counter(f['kind'] for f in it.flags)),
         'overruns':sum(1 for f in it.flags if f['kind']=='timer_overrun'),
         'setlist_ignored':sum(1 for f in it.flags if 'ignored' in f['msg']),
         'err':[o[1].strip() for o in it.out if 'V19' in o[1] and 'error' in o[1].lower()][:2],
         'shots':[]}
    shots=[e[1] for e in it.misc_events if e[0]=='shot']
    mats259=[d for d in it.grad.mats.get(259,[])]
    for n in range(1,nshots+1):
        led=build_ledger(it,n)
        t_s,t_e=led['t_start'],led['t_end']
        ad=led['adc'];la=ad[-1]
        tc=la['t_complete']; ti=la['t_init']
        # terminal matrix create: last 259 definition in shot
        md=[d for d in mats259 if t_s<=d[0]<t_e]
        term=md[-1]
        # trailing P/R lobes after last ADC init: lobes beginning before terminal create
        res={'shot':n,'t_end_minus_start':round(t_e-t_s,1),'complete_rel':round(tc-t_s,1),'ti_rel':round(ti-t_s,1),
             'term_create_call':round(term[0]-tc,1),'term_ready':round(term[1]-tc,1)}
        # find S lobes after last ADC init
        Sl=lobes(led['G']['S'],ti,t_e)
        res['S_lobes_after_last_ADCinit_rel_complete']=[(round(a-tc,1),round(b-tc,1),round(ar),round(pk)) for a,b,ar,pk in Sl]
        # trailing P/R lobes after last adc init (excluding post-train crusher; they are before the term create)
        for ax in 'PR':
            Lx=lobes(led['G'][ax],ti,t_e)
            res[f'{ax}_lobes_rel_complete']=[(round(a-tc,1),round(b-tc,1),round(ar)) for a,b,ar,pk in Lx]
        # last P/R nonzero end before the terminal create (all lobes whose start < term create)
        pr_end=0
        for ax in 'PR':
            for a,b,ar,pk in lobes(led['G'][ax],ti,t_e):
                if a< term[0]: pr_end=max(pr_end,b)
        res['PR_trailing_end_minus_create']=round(pr_end-term[0],1)
        res['margin_ready_before_S_start']=None
        # matrix issues
        res['issues']={ax:[(round(t-tc,1),m) for t,m in led['issues'][ax]] for ax in 'SPR'}
        # S terminal lobe start = first S lobe starting after term create
        St=[l for l in Sl if l[0]>=term[0]]
        if St:
            a,b,ar,pk=St[0]
            res['term_S_start_rel_complete']=round(a-tc,1); res['term_S_end_rel_complete']=round(b-tc,1)
            res['term_S_area']=round(ar); res['term_S_peak']=round(pk)
            res['term_ready_to_S_start']=round(a-term[1],1)
            res['S_end_to_shot_end']=round(t_e-b,1)
            res['n_S_lobes_after_create']=len(St)
        # receiver busy overlap of terminal S lobe
        # next-event: shot end vs list end - find any nonzero P/R/S after S end up to shot end
        rec['shots'].append(res)
    out[key]=rec
    s0=rec['shots'][-1]
    print(key,'ov',rec['overruns'],'ign',rec['setlist_ignored'],'err',rec['err'],'flags',rec['flags'])
    for s in rec['shots'][:1]+rec['shots'][-1:]:
        print('   shot',s['shot'],{k:s.get(k) for k in ('complete_rel','term_create_call','term_ready','PR_trailing_end_minus_create','term_S_start_rel_complete','term_ready_to_S_start','term_S_end_rel_complete','S_end_to_shot_end','n_S_lobes_after_create','issues')})
json.dump(out,open('v1911_rereview_terminal.json','w'),indent=1,default=float)
