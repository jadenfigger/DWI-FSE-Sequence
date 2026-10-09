"""Shot/TR accounting for 716478bb vs v7: train end vs v19_shot_us, TR floor behaviour, all 8 cost models."""
from v1911_rereview_common import *
import json
out={}
for model in COST_MODELS:
    d={}
    for seq in ('v7','v1911'):
        it=run(seq,model,True,shots=2)
        led=build_ledger(it,1); t_shot=led['t_start']
        wt=[e for e in it.misc_events if e[0]=='waittimer' and t_shot<=e[1]<led['t_end']]
        i690=[k for k,e in enumerate(wt) if e[2]==690][0]
        t_train_end=wt[i690-1][1]
        sh=[e[1] for e in it.misc_events if e[0]=='shot']
        d[seq]={'v19_shot_us':int(it.vars['v19_shot_us'].value),'train_end_rel':round(t_train_end-t_shot,1),
                'slack_us':round(int(it.vars['v19_shot_us'].value)-(t_train_end-t_shot),1),
                'tr_min':int(it.vars['tr_min'].value),'period_us':round(sh[1]-sh[0],1),'tr_stored_ms':int(it.vars['tr'].value)}
        trm=int(it.vars['tr_min'].value)
        for trv in (trm-1,trm,trm+1):
            it2=run(seq,model,True,shots=4,overrides={'tr':trv})
            sh2=[e[1] for e in it2.misc_events if e[0]=='shot']
            rej=[o[1].strip() for o in it2.out if 'TR too' in o[1] or 'increase' in o[1].lower()]
            d[seq][f'tr={trv}']={'rejected':rej[:1],'periods_minus_TR_us':[round(b-a-trv*1000,1) for a,b in zip(sh2[:-1],sh2[1:])][:3],
                'overruns':sum(1 for f in it2.flags if f['kind']=='timer_overrun'),'nshots':len(sh2)}
    out[model]=d
    print(model,'shot_us',d['v7']['v19_shot_us'],'->',d['v1911']['v19_shot_us'],'tr_min',d['v7']['tr_min'],'->',d['v1911']['tr_min'],'slack',d['v7']['slack_us'],d['v1911']['slack_us'])
    for k,v in d['v1911'].items():
        if k.startswith('tr='): print('   v1911',k,v)
json.dump(out,open('v1911_rereview_tr.json','w'),indent=1,default=float)
