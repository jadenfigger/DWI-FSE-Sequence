import json,numpy as np
R=json.load(open('v1911_final_results.json'))
H=25447.0
cm=lambda x:x/32767*H*1e-6
print(len(R),'runs')
worst={'S':0,'P':0,'R':0}; wend=0; wadc=0
for r in R:
    tag=(r['model'],r['imaging'])
    bad=[]
    if r['flags']['v1911'].get('timer_overrun') or r['overruns']['v1911']: bad.append('overrun')
    if r['setlist_ignored']['v1911']: bad.append('ignored')
    if r['errors_printed']['v1911']: bad.append(r['errors_printed']['v1911'])
    fl={k:v for k,v in r['flags']['v1911'].items()}
    fl7={k:v for k,v in r['flags']['v7'].items()}
    print(tag,'nshots',r['nshots'],'esp',r['esp_var'],'shot_us',r['shot_us_var'],'tr_min',r['tr_min_ms'],bad)
    if tag[0]=='flat_0us': print('   flags v1911',fl,'v7',fl7)
    for s in r['shots']:
        for ax in 'SPR':
            worst[ax]=max(worst[ax],max(abs(x) for x in s['interval_diff_dac_us'][ax]))
        wend=max(wend,abs(s['moment_diff']['S']['end']),abs(s['moment_diff']['P']['end']),abs(s['moment_diff']['R']['end']))
        wadc=max(wadc,max(abs(x) for ax in 'SPR' for x in s['moment_diff'][ax]['adc']))
print('worst interval diff DAC.us',worst,{k:cm(v) for k,v in worst.items()})
print('worst end/adc moment diff',wend,wadc,cm(wend),cm(wadc))
