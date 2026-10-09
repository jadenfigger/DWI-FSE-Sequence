from v1911_final_common import *
def bounds(it,led):
    rf=led['rf']
    im=[p for p in rf if p['frame']=='v19_imaging180']
    re=[p for p in rf if p['frame']=='v19_reexc90'][0]
    adc=[t for _,t in adc_middle_times(it,led)]
    b=[('reexc',re['t_center'])]
    for j,p in enumerate(im):
        b.append((f'RF{j+1}',p['t_center'])); b.append((f'ADC{j+1}',adc[j]))
    return b
res={}
for seq in ('v7','v1911'):
    it=run(seq,'flat_0us',True)
    led=build_ledger(it,1)
    b=bounds(it,led)
    # end: end of last nonzero S/P/R before post-train crusher: use ADC8 mid + 3500 us (v7: lobes through ~ +7650?) 
    last=b[-1][1]
    H=led['H']
    rows=[]
    for (n0,t0),(n1,t1) in zip(b[:-1],b[1:]):
        rows.append((n0+'->'+n1,[led['G'][ax].integral(t0,t1) for ax in 'SPR']))
    res[seq]=(rows,led)
    print(seq,'H',H)
for (n,a),(n2,b_) in zip(res['v7'][0],res['v1911'][0]):
    d=[(y-x) for x,y in zip(a,b_)]
    print(n, [round(x/1e3) for x in a],[round(x) for x in d])
