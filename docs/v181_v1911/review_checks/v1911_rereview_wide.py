"""Which waittimer arguments exceed 32767 (int16 sign bit) in v7 (scanner-run lineage) and v1911 (new)."""
from v1911_rereview_common import *
import json
out={}
for seq in ('v7','v1911'):
    for model in COST_MODELS:
        for imaging in (True,False):
            it=run(seq,model,imaging,shots=2)
            big={}
            for (w,tk,u) in it.window_use:
                if tk>32767: big[tk]=big.get(tk,0)+1
            neg=[f['msg'] for f in it.flags if f['kind']=='timer_arg']
            out[f'{seq}|{model}|{imaging}']={'ticks_gt_32767':big,'timer_arg_flags':neg[:3],'n_timer_arg':len(neg),'all_flags':sorted({f['kind'] for f in it.flags})}
    # print summary for first model
for k,v in out.items():
    if 'flat_0|' in k or 'manual_x1.0' in k: print(k,v)
json.dump(out,open('v1911_rereview_wide.json','w'),indent=1)
