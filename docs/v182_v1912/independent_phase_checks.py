"""Integrate delivered frequency commands independently of phase helper."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from examples import validate_v182_v1912 as gate
from dwfse.ppl.run import map_events

DOC = Path(__file__).parent
rows = []
def accrued(it, start, end, ref, mhz):
    # Integrate piecewise delivered frequencies; reset_frequency does not
    # clear accrued phase. MHz receive mode is a coherent separate bank.
    f, bank, t, val = ref, mhz, start, 0.
    for e in sorted((x for x in it.frequency_events if x['kind']=='send'),key=lambda x:x['t_us']):
        x = e['t_us']
        if x <= start:
            f,bank=e['frequency_hz'],e['mhz']
        elif x < end:
            if bank == mhz:
                val += (f-ref)*(x-t)*0.00036
            t,f,bank=x,e['frequency_hz'],e['mhz']
        else:
            break
    if bank == mhz:
        val += (f-ref)*(end-t)*0.00036
    return val

for label in ['v182','v1912']:
    for mm in [-5.,0.,5.]:
        it = map_events(gate.SOURCES[label], DOC/'test_pprs'/f'{label}_slice_0mm.ppr'
                        if label=='v1912' else DOC/'test_pprs'/f'{label}_manual_x0.8_slice_0mm.ppr',
                        overrides={**gate.IMAGING,'no_slices':1,'batch_slices':1,
                                   'fov_slice_off':[int(mm*400)],'slice_mm_10':0},
                        max_shots=1,rf_latency_us=3,**gate.NOMINAL)
        pulses=gate.rf_all(it)
        base=[e for e in it.frequency_events if e['kind']=='send' and e.get('buffer')==6
              and pulses and e['t_us']<=pulses[0]['t_center']]
        anchor=max(base,key=lambda e:e['t_us']) if base else None
        ref=anchor['frequency_hz'] if anchor else pulses[0]['tx_freq_hz']
        origin=anchor['t_us'] if anchor else pulses[0]['t_center']
        effective=[(p['phase_deg']+accrued(it,origin,p['t_center'],ref,p['tx_mhz']))%360 for p in pulses]
        intended=([0,270]+[270]*(len(pulses)-2) if label=='v182' else
                  [0,270,180,0]+[270]*(len(pulses)-4))
        error=[(a-effective[0]-b+180)%360-180 for a,b in zip(effective,intended)]
        rows.append({'label':label,'z_mm':mm,'phase_error_deg':error,
                     'max_error_deg':max(map(abs,error)),
                     'frequency_hz':[p['tx_freq_hz']-ref for p in pulses]})
        print(label,mm,'maximum phase error deg',rows[-1]['max_error_deg'],flush=True)
(DOC/'independent_phase.json').write_text(json.dumps(rows,indent=2))
