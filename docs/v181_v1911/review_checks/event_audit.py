"""Independent all-model/two-shot event review of final PPL/PPR bytes."""
from pathlib import Path
import argparse
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from dwfse.ppl.run import map_events
from dwfse.ppl.ledger import build_ledger, adc_middle_times
from examples.v19_validate_events import COST_MODELS

SC = ROOT/'scanner'
OUT = Path(__file__).parent
SOURCES = {label:(SC/f'FSE_dwi_CPMG_non_CPMG_twoTE-{version}.ppl', SC/f'FSE_dwi_CPMG_non_CPMG_twoTE-{version}.ppr')
           for label,version in [('v181','1.81'),('v1911','1.911')]}


def overlapping_nonzero(g, a, b, shift):
    lo = np.maximum(g.t[:-1]+shift,a)
    hi = np.minimum(g.t[1:]+shift,b)
    mask = (hi > lo+1e-8) & (np.abs(g.v)>1e-8)
    return {'duration_us':float(np.sum((hi-lo)[mask])),
            'peak_DAC':float(np.max(np.abs(g.v[mask]))) if mask.any() else 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--labels',nargs='+',default=list(SOURCES))
    parser.add_argument('--imaging',action='store_true')
    args = parser.parse_args()
    report = {'scope':'Independent source-model review; rfdelay shifts logical waveforms. RF pipeline assumed3us; physical orientation and console semantics not qualified.', 'sequences':{}}
    for label in args.labels:
        ppl,ppr = SOURCES[label]
        model_results={}
        for name,model in COST_MODELS.items():
            overrides={'no_disacq':0,'nav_on':0,'no_views':128} if args.imaging else {}
            it=map_events(ppl,ppr,max_shots=2,rf_latency_us=3,overrides=overrides,**model)
            shots=[]
            shift=float(it.vars['rfdelay'].value)
            for number in (1,2):
                led=build_ledger(it,number)
                rf=led['rf']
                ims=[p for p in rf if p['frame']=='v19_imaging180'] if label=='v1911' else rf[2:]
                rc=np.array([p['t_center'] for p in ims])
                refs=ims if label=='v1911' else rf[1:]
                allrc=np.array([p['t_center'] for p in refs])
                ac=np.array([t for _,t in adc_middle_times(it,led)])
                imaging_ac=ac if label=='v1911' else ac[1:]
                receiver=[]
                for a in led['adc']:
                    receiver.append({axis:overlapping_nonzero(led['G'][axis],a['t_init'],a['t_complete'],shift) for axis in 'SP'})
                rf_scope=[]
                for p in rf:
                    on=np.flatnonzero(np.abs(p['amp'])>1e-8)
                    t=p['t'][on] if len(on) else np.zeros(0)
                    g=led['G']['S'].sample(t-shift+p['dt']/2)
                    rf_scope.append({'frame':p['frame'],'RF_start_rel_excitation_us':p['t_go']-rf[0]['t_center'],
                        'selector_min_DAC':float(g.min()) if len(g) else None,
                        'selector_max_DAC':float(g.max()) if len(g) else None,
                        'selector_variable_during_nonzero_RF':bool(len(g) and np.ptp(g)>1e-7)})
                shots.append({'shot':number,'RF_count':len(rf),'ADC_count':len(ac),
                    'RF_ESP_us':np.diff(rc).tolist(),'ADC_ESP_us':np.diff(ac).tolist(),
                    'ADC_minus_imaging_RF_midpoint_us':(imaging_ac[:len(rc)-1]-(rc[:-1]+rc[1:])/2).tolist(),
                    'RF_to_ADC_us':(ac-allrc).tolist(),
                    'ADC_center_from_excitation_us':(ac-rf[0]['t_center']).tolist(),
                    'slice_phase_during_receiver_busy':receiver,'RF_selector':rf_scope,
                    'matrix_issues':led['issues']})
            model_results[name]={'inputs':it.inputs,'flags':it.flags,'shots':shots}
            print(label,name,flush=True)
        report['sequences'][label]=model_results
        target='independent_event_audit_imaging.json' if args.imaging else 'independent_event_audit.json'
        (OUT/target).write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    main()
