"""Protocol-specific isolated source experiment; not a scanner deliverable."""
from pathlib import Path
import sys
import json
from copy import deepcopy
from types import SimpleNamespace
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from examples import v19_validate_events as old
from dwfse.ppl.run import map_events, sha256
from dwfse.ppl.ledger import build_ledger,list_starts,list_duration_us,effective_moment,adc_middle_times
from dwfse.ppl.events import gradient_pwc, PWC
from dwfse.ppl.bloch import Grid,rf_calibration_hz_per_unit
from dwfse.vendor_seq import decode

OUT=Path(__file__).parent
BASE=ROOT/'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl'
PPR=BASE.with_suffix('.ppr')

def component(it, matrix_ids, unit=False):
    g=deepcopy(it.grad)
    g.mats={k:[tuple([d[0],d[1], (1 if unit else d[2]) if k in matrix_ids else 0,*d[3:]]) for d in ds] for k,ds in g.mats.items()}
    return gradient_pwc(SimpleNamespace(grad=g),'S')[0]

def stats(it):
    l=build_ledger(it)
    return dict(timer_overruns=[f for f in it.flags if f['kind']=='timer_overrun'],
        ignored_lists=[f for f in it.flags if 'ignored' in f['msg']],matrix_issues=l['issues'],
        RF=[p['t_center'] for p in l['rf']],ADC=[t for _,t in adc_middle_times(it,l)],
        moment_S=[effective_moment(l,'S',l['rf'][0]['t_center'],t,[p['t_center'] for p in l['rf'][1:]]) for _,t in adc_middle_times(it,l)])

def main():
    source=BASE.read_text()
    (OUT/'baseline_snapshot.ppl').write_text(source)
    (OUT/'baseline_snapshot.ppr').write_bytes(PPR.read_bytes())
    baseline=map_events(OUT/'baseline_snapshot.ppl',PPR,max_shots=1,rf_latency_us=3.,**old.NOMINAL)
    led=build_ledger(baseline)
    select=component(baseline,{21,22})
    secunit=component(baseline,{277,278},unit=True)
    starts=list_starts(baseline,led,'slice_180_refocus_diff')+list_starts(baseline,led,'slice_180_refocus')
    selector=baseline.vars['gs_var_rescale'].value
    gz=int(selector/1.2)
    scale=gz/selector
    results={'baseline_sha256':sha256(OUT/'baseline_snapshot.ppl'),'baseline':stats(baseline),'variants':{}}
    runs={'baseline':baseline}
    for lag in (0.,60.):
        amplitudes=[]
        for j in (0,1):
            start=starts[j][0]
            end=start+list_duration_us(baseline,'slice_180_refocus_diff' if j==0 else 'slice_180_refocus')
            center=led['rf'][j+1]['t_center']-lag
            q=[select.integral(start,center),select.integral(center,end)]
            u=[secunit.integral(start,center),secunit.integral(center,end)]
            crusher=baseline.vars['crusher_saved_first' if j==0 else 'crusher_saved_train'].value
            amplitudes.append([round(crusher+v*(1-scale)/a) for v,a in zip(q,u)])
        first,train=amplitudes
        # Known default protocol only. Extra matrices26/27 are absent from
        # this source/includes; primary values are equal during the switch.
        text=source.replace('int gs_var1;', 'int gs_var1;\n int width_post_mat;')
        text=text.replace('CREATE_MATRIX(slice_crush,gs_on*gs_var_rescale,0,0)',f'CREATE_MATRIX(slice_crush,gs_on*({gz}),0,0)')
        text=text.replace('CREATE_MATRIX(first_slice_crush,gs_on*gs_var_rescale,0,0)',f'CREATE_MATRIX(first_slice_crush,gs_on*({gz}),0,0)')
        text=text.replace('CREATE_MATRIX(slice_crush_sec,gs_on*crush_independent_on*crusher_saved_train,0,0)',f'CREATE_MATRIX(slice_crush_sec,gs_on*({train[0]}),0,0)')
        text=text.replace('CREATE_MATRIX(first_slice_crush_sec,gs_on*crusher_saved_first,0,0)',f'CREATE_MATRIX(first_slice_crush_sec,gs_on*({first[0]}),0,0)')
        anchor='CREATE_MATRIX(diff_mat, -diff_slice, -diff_phase, -diff_read)'
        text=text.replace(anchor,f'''CREATE_MATRIX(26,gs_on*({gz}),0,0)
 delay(caldelay,us);
 CREATE_MATRIX(282,gs_on*({train[1]}),0,0)
 delay(caldelay,us);
 CREATE_MATRIX(27,gs_on*({gz}),0,0)
 delay(caldelay,us);
 CREATE_MATRIX(283,gs_on*({first[1]}),0,0)
 delay(caldelay,us);
 {anchor}''')
        anchor='this_tcrush = tcrush_play;'
        text=text.replace(anchor,'width_post_mat=26;\n if ((diff_on==1)&&(total_echo_cnt==0)) width_post_mat=27;\n '+anchor)
        anchor='refocus_wait_ticks = IntToLong(tramp+this_tcrush-rfdelay+crush_post_pad-crush_pre_pad)*10L;'
        text=text.replace(anchor,anchor+'\n MR3040_SelectMatrix(width_post_mat);')
        path=OUT/f'width120_comp_lag{int(lag)}.ppl'
        path.write_text(text)
        it=map_events(path,PPR,max_shots=1,rf_latency_us=3.,**old.NOMINAL)
        runs[path.stem]=it
        result=stats(it)
        result['pre_post_crusher_DAC']={'first':first,'train':train}
        result['selector_DAC']=gz
        result['RF_time_gradient_identity_to_scaled_baseline']=[]
        il=build_ledger(it)
        for p,b in zip(il['rf'][1:],led['rf'][1:]):
            gp=il['G']['S'].sample(p['t']+p['dt']/2)
            gb=led['G']['S'].sample(b['t']+b['dt']/2)
            result['RF_time_gradient_identity_to_scaled_baseline'].append(float(np.max(abs(gp-gb*scale))))
        results['variants'][path.stem]=result
    (OUT/'source_feasibility.json').write_text(json.dumps(results,indent=2,default=float))
    stock=decode(ROOT/'scanner/utilities/rfstd44.seq').frame('3lobe_sinc_3kHz')
    grid=Grid((np.arange(600)+.5)/600*.005-.0025,np.zeros(1))
    full={}
    for name,it in runs.items():
        l=build_ledger(it)
        cal=rf_calibration_hz_per_unit(stock.samples,stock.wait_ticks/10,it.vars['rfcal'].value)
        values=[]
        for lag in (0.,60.):
            for b1 in (.8,1.,1.1):
                for b0 in (-128.,0.,128.):
                    for ph in (0.,45.,90.):
                        s,*_=old.run_bloch(l,it,'v18',cal,phase=ph,b1=b1,df=b0,latency=lag,grid=grid,snapshots=False)
                        values.append(dict(gradient_lag_us=lag,B1=b1,B0_hz=b0,phase_deg=ph,real=np.real(s).tolist(),imag=np.imag(s).tolist(),abs=np.abs(s).tolist()))
        full[name]=values
        (OUT/'fulltrain_bloch.json').write_text(json.dumps(full,indent=2))
        print('Bloch complete: '+name,flush=True)
    for name,values in full.items():
        if name=='baseline':continue
        change=[np.array(v['abs'])-np.array(b['abs']) for v,b in zip(values,full['baseline'])]
        results['variants'][name]['fulltrain_min_per_echo_magnitude_change']=float(np.min(change))
        results['variants'][name]['fulltrain_max_per_echo_magnitude_change']=float(np.max(change))
    (OUT/'source_feasibility.json').write_text(json.dumps(results,indent=2,default=float))
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
