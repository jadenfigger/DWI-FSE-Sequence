from v1911_final_common import *
for seq in ('v7','v1911'):
    it=run(seq,'flat_0us',True)
    led=build_ledger(it,1)
    print(seq, sha(SEQ[seq][0])[:8], 'ESP',it.vars['esp'].value, 'inputs',len(led['rf']),len(led['adc']))
    rf=led['rf']; c=[p['t_center'] for p in rf]
    adc=led['adc']
    print(' RF centers rel exc',[round(x-c[0],1) for x in c])
    print(' ADC t_init/complete',[(round(a['t_init']-c[0],1),round(a['t_complete']-c[0],1)) for a in adc][-2:])
    tl=adc[-1]['t_init']-3000
    for ax in 'SPR':
        print(' ',ax,[(round(a-c[0],1),round(b-c[0],1),round(ar),round(pk)) for a,b,ar,pk in lobes(led['G'][ax],tl,led['t_end'])])
