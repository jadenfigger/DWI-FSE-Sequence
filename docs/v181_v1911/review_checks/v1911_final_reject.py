"""Rejection (before any RF/ADC) and acceptance tests for v1.911 vs v7."""
from v1911_final_common import *
import json
from dwfse.ppl.events import rf_pulses


def outcome(seq, ov, model='manual_x0.8', imaging=False, shots=1):
    ppl, ppr = SEQ[seq]
    ovr = dict(ov)
    it = map_events(ppl, ppr, max_shots=shots, overrides=ovr, rf_latency_us=3, **COST_MODELS[model])
    nrf = len([p for p in rf_pulses(it) if p.get('library')])
    msg = [o[1].strip() for o in it.out if 'V19' in o[1] or 'TR too' in o[1] or 'error' in o[1].lower()]
    grad = sum(len(c.segments) for c in it.grad.ch.values())
    return {'rf': nrf, 'adc': len(it.adc), 'grad_segments': grad, 'msg': msg[-1] if msg else ''}


ORIG19 = {"3D": {"no_views_2": 2}, "multislice": {"no_slices": 2}, "slice offset": {"slice_mm_10": 10},
          "presat": {"sat_on": 1}, "flow comp": {"flow_comp_on": 1}, "DE": {"de_on": 1},
          "gating": {"gating": 1}, "crusher schedule": {"crusher_schedule": 1},
          "crusher too small": {"crush_amp": -2741}, "TE too short": {"te": 52},
          "ESP too short": {"esp": 11}, "flip out of range": {"v19_flip_tenths": [0] * 8},
          "TR too short": {"tr": 150}, "cycles not validated": {"v19_cycles": 4},
          "C1 small coincidence": {"diff_crush_amp": -1500},
          "C1 large coincidence": {"diff_crush_amp": -12000},
          "C outside validated window": {"crush_amp": -7700},
          "C1 opposite polarity": {"diff_crush_amp": 5482},
          "crusher polarity not validated": {"crush_amp": 8223, "diff_crush_amp": 5482}}
NEW = {"ESP12": {"esp": 12}, "ESP11": {"esp": 11}, "ESP10": {"esp": 10},
       "tramp 190 (diff_tramp same)": {"tramp": 190, "diff_tramp": 190},
       "tramp 250": {"tramp": 250, "diff_tramp": 250},
       "tdp 650": {"tdp": 650}, "tdp 750": {"tdp": 750},
       "tcrush 900": {"tcrush": 900}, "tcrush 1100": {"tcrush": 1100},
       "rfdelay 50": {"rfdelay": 50}, "rfdelay 70": {"rfdelay": 70},
       "subj_angle_x": {"subj_angle_x": 5}, "subj_angle_y": {"subj_angle_y": 5}, "subj_angle_z": {"subj_angle_z": 5},
       "r_angle": {"r_angle_var": [5, 0, 0]}, "p_angle": {"p_angle_var": [5, 0, 0]}, "s_angle": {"s_angle_var": [5, 0, 0]},
       "phase_var swap": {"phase_var": 1},
       "r_angle[1] (not checked)": {"r_angle_var": [0, 5, 0]},
       "crush_amp -32000 overflow": {"crush_amp": -32000},
       "crush_amp -20000": {"crush_amp": -20000},
       "crusher_max_dac small": {"crusher_max_dac": 8000},
       "te 108 (ok?)": {"te": 108}, "esp 14": {"esp": 14}, "esp 16": {"esp": 16}, "esp 20": {"esp": 20},
       "sample_period 250": {"sample_period": 250}, "sample_period 1000": {"sample_period": 1000},
       "no_samples 256": {"no_samples": 256}, "no_samples 64": {"no_samples": 64},
       "slice_thick small gs": {"gs_var": -3000}, "slice_thick big gs": {"gs_var": -500},
       "etl4": {"etl": 4}, "etl 16": {"etl": 16}}
if __name__ == '__main__':
    out = {}
    for lab, tests in (('orig19', ORIG19), ('new', NEW)):
        out[lab] = {}
        for name, ov in tests.items():
            out[lab][name] = {s: outcome(s, ov) for s in ('v7', 'v1911')}
            a, b = out[lab][name]['v7'], out[lab][name]['v1911']
            print(f"{lab:6s} {name:34s} v7 rf={a['rf']:2d} adc={a['adc']} '{a['msg'][:34]}' | v1911 rf={b['rf']:2d} adc={b['adc']} '{b['msg'][:44]}'", flush=True)
    json.dump(out, open('v1911_final_reject.json', 'w'), indent=1)
