"""Shot/TR accounting, terminal timer margin, tfilter sensitivity, crusher ratios (v1.911 vs v7)."""
from v1911_final_common import *
import json
import dwfse.ppl.run as runmod
from functools import partial
from dwfse.ppl.interp import Interp


def run_ac(seq, model, acq, ov=None, shots=2):
    orig = runmod.Interp
    runmod.Interp = partial(Interp, acqpad_ticks=acq)
    try:
        return run(seq, model, True, shots=shots, overrides=ov)
    finally:
        runmod.Interp = orig


out = {}
for model in COST_MODELS:
    d = {}
    for seq in ('v7', 'v1911'):
        it = run(seq, model, True, shots=2)
        led = build_ledger(it, 1)
        t_shot = led['t_start']
        tr_ms = int(it.vars['tr'].value)
        wt = [e for e in it.misc_events if e[0] == 'waittimer' and t_shot <= e[1] < led['t_end']]
        # first waittimer in after_train segment = waittimer(690); train end = event just before that
        i690 = [k for k, e in enumerate(wt) if e[2] == 690][0]
        t_train_end = wt[i690 - 1][1]
        used = [(w, tk, u) for (w, tk, u) in it.window_use if tk in (18000, 30000)]
        # shot-to-shot period
        sh = [e[1] for e in it.misc_events if e[0] == 'shot']
        d[seq] = {'train_end_minus_shot_start_us': round(t_train_end - t_shot, 1),
                  'v19_shot_us': int(it.vars['v19_shot_us'].value),
                  'slack_us': round(int(it.vars['v19_shot_us'].value) - (t_train_end - t_shot), 1),
                  'period_us': round(sh[1] - sh[0], 1), 'tr_us': tr_ms * 1000,
                  'terminal_timer_use_ticks': [(tk, round(u, 1)) for (w, tk, u) in used][-4:]}
        # min TR run: tr = ceil(floor)
        tr_floor_ms = int(it.vars['tr_min'].value) + 1  # tr_min printed in ms floor
        for trv in (int(it.vars['tr_min'].value), int(it.vars['tr_min'].value) + 1):
            it2 = run(seq, model, True, shots=3, overrides={'tr': trv})
            sh2 = [e[1] for e in it2.misc_events if e[0] == 'shot']
            rej = [o[1].strip() for o in it2.out if 'TR too' in o[1]]
            d[seq][f'tr={trv}'] = {'rejected': rej[:1], 'periods_minus_TR_us': [round(b - a - trv * 1000, 1) for a, b in zip(sh2[:-1], sh2[1:])],
                                   'overruns': sum(1 for f in it2.flags if f['kind'] == 'timer_overrun')}
    out[model] = d
    print(model, json.dumps(d['v1911']['tr=%d' % (int(d['v1911']['tr_us'] / 1000 * 0) or 0)] if False else {k: d['v1911'][k] for k in ('train_end_minus_shot_start_us', 'v19_shot_us', 'slack_us', 'terminal_timer_use_ticks')}), '| v7 slack', d['v7']['slack_us'], flush=True)
    for seq in d:
        print('   ', seq, {k: v for k, v in d[seq].items() if k.startswith('tr=')})
# tfilter sensitivity for terminal 18000 timer
sens = {}
for acq in (3730, 4200, 4600, 5000, 5100, 5500, 6000, 7500):
    it = run_ac('v1911', 'manual_x0.8', acq)
    ov = sum(1 for f in it.flags if f['kind'] == 'timer_overrun')
    msgs = [f['msg'] for f in it.flags if f['kind'] == 'timer_overrun'][:2]
    led = build_ledger(it, 1)
    S_after = [l for l in lobes(led['G']['S'], led['adc'][-1]['t_init'], led['t_end'])]
    sens[acq] = {'overruns': ov, 'msgs': msgs, 'terminal_S_start_minus_complete': round(S_after[0][0] - led['adc'][-1]['t_complete'], 1) if S_after else None,
                 'S_after_n': len(S_after), 'err': [o[1].strip() for o in it.out if 'V19' in o[1]][-1:]}
    print('acqpad', acq, sens[acq])
out['tfilter_sensitivity'] = sens
json.dump(out, open('v1911_final_timing.json', 'w'), indent=1, default=float)
# crusher ratios & area math from variables
it = run('v1911', 'manual_x0.8', True, shots=1)
V = lambda n: it.vars[n].value
C = V('crusher_saved_train'); C1 = V('crusher_saved_first'); D = V('v19_d_dac')
tc, tr_, td = V('tcrush'), V('tramp'), V('tdp')
area = lambda x, flat: x * (flat + tr_) + x * 19200 // 10000
print('C', C, 'C1', C1, 'D', D, '|C|/|D|', abs(area(C, tc) / area(D, td)), '|C1|/|D|', abs(area(C1, tc) / area(D, td)),
      'first/pre/post', V('v1911_first_dac'), V('v1911_pre_dac'), V('v1911_post_dac'), 'slew_limit', V('crusher_slew_dac_100us'), 'max', V('crusher_max_dac'), 'tfilter', V('tfilter'))
