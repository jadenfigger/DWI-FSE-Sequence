from v1911_final_common import *
from dwfse.ppl.ledger import effective_moment
out={}
for seq in ('v7','v1911'):
    it=run(seq,'flat_0us',True)
    led=build_ledger(it,1)
    rf=led['rf']
    im=[p['t_center'] for p in rf if p['frame']=='v19_imaging180']
    re=[p for p in rf if p['frame']=='v19_reexc90'][0]['t_center']
    adc=[t for _,t in adc_middle_times(it,led)]
    # post crusher start
    lb=lobes(led['G']['S'],im[-1],led['t_end'])
    tend=lb[-1][0]-1.0
    print(seq,'tend rel',tend-re, 'last lobes',[(round(a-re),round(b-re)) for a,b,_,_ in lb])
    H=led['H']
    for ax in 'SPR':
        ks=[effective_moment(led,ax,re,t,im,unit='dac_us') for t in adc]
        ke=effective_moment(led,ax,re,tend,im,unit='dac_us')
        out[(seq,ax)]=(ks,ke)
        print(seq,ax,'k@ADCmid',[round(x) for x in ks],'k@end',round(ke))
for ax in 'SPR':
    a,ae=out[('v7',ax)];b,be=out[('v1911',ax)]
    print(ax,'diff@ADC',[round(y-x) for x,y in zip(a,b)],'diff@end',round(be-ae), 'cyc/mm', (be-ae)/32767*25447e-6)
