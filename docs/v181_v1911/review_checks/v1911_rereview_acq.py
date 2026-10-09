"""acqpad (receiver filter length) sweep: P/R trailing end vs terminal CREATE_MATRIX, ready vs S start."""
from v1911_rereview_common import *
import json
from functools import partial
import dwfse.ppl.run as runmod
from dwfse.ppl.interp import Interp
out={}
for acq in (3730,4000,4600,5000,5100):
  for model in COST_MODELS:
    orig=runmod.Interp; runmod.Interp=partial(Interp,acqpad_ticks=acq)
    try:
        its={im:run('v1911',model,im,shots=3 if im else 4) for im in (True,False)}
    finally: runmod.Interp=orig
    for im,it in its.items():
        n=len([e for e in it.misc_events if e[0]=='shot'])-1
        worst_pr=-1e9; worst_rdy=1e9; iss=0; ov=sum(1 for f in it.flags if f['kind']=='timer_overrun'); ign=sum(1 for f in it.flags if 'ignored' in f['msg'])
        for k in range(1,n+1):
            led=build_ledger(it,k); ts,te=led['t_start'],led['t_end']
            la=led['adc'][-1]
            term=[d for d in it.grad.mats[259] if ts<=d[0]<te][-1]
            pr=max([b for ax in 'PR' for a,b,ar,pk in lobes(led['G'][ax],la['t_init'],te) if a<term[0]]+[0])
            worst_pr=max(worst_pr,pr-term[0])
            S=[l for l in lobes(led['G']['S'],la['t_init'],te) if l[0]>=term[0]][0]
            worst_rdy=min(worst_rdy,S[0]-term[1])
            iss+=sum(len(led['issues'][a]) for a in 'SPR')
            ov_busy=max([min(S[1],a['t_complete'])-max(S[0],a['t_init']) for a in led['adc']]+[0])
            assert ov_busy<=0
        out[f'{acq}|{model}|{"img" if im else "def"}']=dict(PR_end_minus_create_worst=round(worst_pr,1),create_ready_to_S_start_min=round(worst_rdy,1),issues=iss,overruns=ov,ignored=ign,tfilter=int(it.vars['tfilter'].value))
  r=[v for k,v in out.items() if k.startswith(str(acq)+'|')]
  print(acq,'tfilter',r[0]['tfilter'],'PR_end-create worst(max)',max(x['PR_end_minus_create_worst'] for x in r),'ready->S min',min(x['create_ready_to_S_start_min'] for x in r),'issues',sum(x['issues'] for x in r),'overruns',sum(x['overruns'] for x in r),'ignored',sum(x['ignored'] for x in r))
json.dump(out,open('v1911_rereview_acq.json','w'),indent=1)
