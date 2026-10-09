"""Independent final review: v1.911 vs v7, all 8 cost models, two configs."""
from v1911_final_common import *
import json, sys
from collections import Counter
from dwfse.ppl.ledger import effective_moment
H = 25447.0


def cyc_mm(x):
    return x / 32767.0 * H * 1e-6


def rfwin(p, shift=0.0):
    on = np.flatnonzero(np.abs(p['amp']) > 1e-8)
    return (p['t'][on[0]] + shift, p['t'][on[-1]] + p['dt'] + shift) if len(on) else None


def clearance(segs, win):
    best = 1e18
    for a, b in segs:
        if b <= win[0]:
            d = win[0] - b
        elif a >= win[1]:
            d = a - win[1]
        else:
            d = 0.0
        best = min(best, d)
    return best


def bounds(it, led):
    rf = led['rf']
    im = [p for p in rf if p['frame'] == 'v19_imaging180']
    re = [p for p in rf if p['frame'] == 'v19_reexc90'][0]
    adc = [t for _, t in adc_middle_times(it, led)]
    b = [('reexc', re['t_center'])]
    for j, p in enumerate(im):
        b.append((f'RF{j+1}', p['t_center']))
        b.append((f'ADC{j+1}', adc[j]))
    return b, im, re, adc


def shot_info(it, n):
    led = build_ledger(it, n)
    b, im, re, adc = bounds(it, led)
    imc = [p['t_center'] for p in im]
    return led, b, im, re, adc, imc


def busy_overlap(it, led, shift=60.0):
    out = {}
    for ax in 'SPR':
        ch = it.grad.ch[ax]
        tot = 0.0
        sec = 0.0
        for (t0, t1, pr, sc) in ch.segments:
            if t1 <= led['t_start'] or t0 >= led['t_end']:
                continue
            if not (pr or sc):
                continue
            for a in led['adc']:
                for sh in (0.0, shift):
                    lo = max(t0 + sh, a['t_init'])
                    hi = min(t1 + sh, a['t_complete'])
                    if hi > lo:
                        if sh == shift:
                            tot += hi - lo
                            if sc:
                                sec += hi - lo
        out[ax] = {'nonzero_us_shifted': round(tot, 1), 'sec_nonzero_us_shifted': round(sec, 1)}
    # zero-shift too, for S sec only
    ch = it.grad.ch['S']
    z = 0.0
    for (t0, t1, pr, sc) in ch.segments:
        if t1 <= led['t_start'] or t0 >= led['t_end'] or not (pr or sc):
            continue
        for a in led['adc']:
            lo = max(t0, a['t_init'])
            hi = min(t1, a['t_complete'])
            if hi > lo:
                z += hi - lo
    out['S_shift0_nonzero_us'] = round(z, 1)
    return out


def analyze(model, imaging, shots=None, overrides=None):
    its = {s: run(s, model, imaging, shots=shots, overrides=overrides) for s in ('v7', 'v1911')}
    nshots = len([e for e in its['v1911'].misc_events if e[0] == 'shot']) - 1
    res = {'model': model, 'imaging': imaging, 'nshots': nshots}
    res['flags'] = {s: dict(Counter(f['kind'] for f in its[s].flags)) for s in its}
    res['errors_printed'] = {s: [o[1].strip() for o in its[s].out if 'V19' in o[1] and 'error' in o[1].lower()][:3] for s in its}
    res['setlist_ignored'] = {s: sum(1 for f in its[s].flags if 'ignored' in f['msg']) for s in its}
    res['overruns'] = {s: sum(1 for f in its[s].flags if f['kind'] == 'timer_overrun') for s in its}
    res['esp_var'] = {s: int(its[s].vars['esp'].value) for s in its}
    res['shot_us_var'] = {s: int(its[s].vars['v19_shot_us'].value) for s in its}
    res['tr_min_ms'] = {s: int(its[s].vars['tr_min'].value) for s in its}
    per = []
    for n in range(1, nshots + 1):
        rec = {'shot': n}
        L = {s: shot_info(its[s], n) for s in ('v7', 'v1911')}
        led7, b7, im7, re7, adc7, imc7 = L['v7']
        led, b, im, re, adc, imc = L['v1911']
        ad = led['adc']
        rec['gp_mul_all'] = [a['vars'].get('gp_mul') for a in ad]
        rec['diff_acq_cnt'] = ad[0]['vars'].get('diff_acq_cnt')
        rec['disacq'] = ad[0]['vars'].get('disacq_cnt')
        rec['nav_cnt'] = ad[0]['vars'].get('nav_cnt')
        rec['n_rf'] = (len(led7['rf']), len(led['rf']))
        rec['n_adc'] = (len(led7['adc']), len(ad))
        rec['ESP_RF'] = [round(x, 2) for x in np.diff(imc)]
        rec['ESP_RF_v7'] = [round(x, 2) for x in np.diff(imc7)]
        rec['ADC_ESP'] = [round(x, 2) for x in np.diff(adc)]
        rec['ADC_minus_mid'] = [round(adc[j] - (imc[j] + imc[j + 1]) / 2, 2) for j in range(7)]
        rec['ADC8_minus_RF8_halfESP'] = round(adc[7] - (imc[7] + (imc[7] - imc[6]) / 2), 2)
        diffs = {ax: [] for ax in 'SPR'}
        names = []
        for (n0, t0), (n1, t1), (m0, u0), (m1, u1) in zip(b[:-1], b[1:], b7[:-1], b7[1:]):
            names.append(n0 + '->' + n1)
            for ax in 'SPR':
                diffs[ax].append(led['G'][ax].integral(t0, t1) - led7['G'][ax].integral(u0, u1))
        rec['interval_names'] = names
        rec['interval_diff_dac_us'] = {ax: [round(x, 1) for x in diffs[ax]] for ax in 'SPR'}
        lbS = lobes(led['G']['S'], imc[-1], led['t_end'])
        lbS7 = lobes(led7['G']['S'], imc7[-1], led7['t_end'])
        tend = lbS[-1][0] - 1
        tend7 = lbS7[-1][0] - 1
        endk = {}
        for ax in 'SPR':
            k = effective_moment(led, ax, re['t_center'], tend, imc, unit='dac_us')
            k7 = effective_moment(led7, ax, re7['t_center'], tend7, imc7, unit='dac_us')
            ks = [effective_moment(led, ax, re['t_center'], t, imc, unit='dac_us') for t in adc]
            ks7 = [effective_moment(led7, ax, re7['t_center'], t, imc7, unit='dac_us') for t in adc7]
            endk[ax] = {'end': round(k - k7, 1), 'adc': [round(a - c, 1) for a, c in zip(ks, ks7)]}
        rec['moment_diff'] = endk
        rec['last_interval_diff'] = {ax: round(led['G'][ax].integral(b[-1][1], tend) - led7['G'][ax].integral(b7[-1][1], tend7), 1) for ax in 'SPR'}
        ac = ad[-1]
        tc = ac['t_complete']
        S_after = [l for l in lbS if l[1] > ac['t_init']]
        rec['S_lobes_after_last_ADC_init'] = [(round(l[0] - tc, 1), round(l[1] - tc, 1), round(l[2]), round(l[3])) for l in S_after]
        a7 = led7['adc'][-1]
        S7after = [l for l in lbS7 if l[1] > a7['t_init']]
        rec['v7_S_lobes_after_last_ADC_init'] = [(round(l[0] - a7['t_complete'], 1), round(l[1] - a7['t_complete'], 1), round(l[2]), round(l[3])) for l in S7after]
        rec['receiver_overlap_v1911'] = busy_overlap(its['v1911'], led)
        rec['receiver_overlap_v7'] = busy_overlap(its['v7'], led7)
        # gap between each ADC complete and next S / P / R nonzero start (v1911 and v7)
        gaps = {}
        for lab, (it_, led_) in {'v7': (its['v7'], led7), 'v1911': (its['v1911'], led)}.items():
            gaps[lab] = {}
            for ax in 'SPR':
                ch = it_.grad.ch[ax]
                g = []
                for a in led_['adc'][:-1]:
                    nxt = [t0 for (t0, t1, pr, sc) in ch.segments if t0 >= a['t_complete'] - 400 and (pr or sc) and t0 > a['t_init'] + 4000 and t1 > t0]
                    g.append(round(min(nxt) - a['t_complete'], 1) if nxt else None)
                gaps[lab][ax] = g
        rec['gap_complete_to_next_nonzero'] = gaps
        clr = {}
        for ax in 'SPR':
            ch = its['v1911'].grad.ch[ax]
            segs = [(t0, t1) for (t0, t1, pr, sc) in ch.segments if led['t_start'] <= t0 < led['t_end'] and sc != 0 and t1 > t0]
            allseg = [(t0, t1) for (t0, t1, pr, sc) in ch.segments if led['t_start'] <= t0 < led['t_end'] and (pr or sc) and t1 > t0]
            c0 = {0.0: [], 60.0: []}
            c1 = {0.0: [], 60.0: []}
            for p in im:
                w = rfwin(p)
                for sh in (0.0, 60.0):
                    c0[sh].append(clearance([(a + sh, b_ + sh) for a, b_ in segs], w))
                    c1[sh].append(clearance([(a + sh, b_ + sh) for a, b_ in allseg], w))
            clr[ax] = {'sec_clear_shift0': round(min(c0[0.0]), 1), 'sec_clear_shift60': round(min(c0[60.0]), 1),
                       'any_clear_shift0': round(min(c1[0.0]), 1), 'any_clear_shift60': round(min(c1[60.0]), 1)}
        rec['clearance_to_imaging_RF'] = clr
        sel = {}
        for lab, (led_, im_) in {'v7': (led7, im7), 'v1911': (led, im)}.items():
            vals = []
            for p in im_:
                on = np.flatnonzero(np.abs(p['amp']) > 1e-8)
                for sh in (0.0, 60.0):
                    g = led_['G']['S'].sample(p['t'][on] + p['dt'] / 2 - sh)
                    vals.append((sh, float(g.min()), float(g.max())))
            sel[lab] = {str(sh): (min(v[1] for v in vals if v[0] == sh), max(v[2] for v in vals if v[0] == sh)) for sh in (0.0, 60.0)}
        rec['selector'] = sel
        pk = {}
        sl = {}
        for lab, led_ in {'v7': led7, 'v1911': led}.items():
            pk[lab] = {}
            sl[lab] = {}
            for ax in 'SPR':
                G = led_['G'][ax]
                m = (G.t[:-1] >= led_['t_start']) & (G.t[:-1] < led_['t_end'])
                v = G.v[m]
                dt = np.diff(G.t)[m]
                pk[lab][ax] = float(np.max(np.abs(v)))
                dv = np.abs(np.diff(v))
                mid = (dt[:-1] + dt[1:]) / 2
                good = mid > 0
                sl[lab][ax] = float(np.max(dv[good] / mid[good])) if good.any() else 0
        rec['peak_dac'] = pk
        rec['max_slew_dac_per_us'] = sl
        rec['ledger_issues'] = {s: {ax: len(L[s][0]['issues'][ax]) for ax in 'SPR'} for s in L}
        per.append(rec)
    res['shots'] = per
    return res, its


if __name__ == '__main__':
    allres = []
    for imaging in (True, False):
        for model in COST_MODELS:
            r, _ = analyze(model, imaging)
            allres.append(r)
            print(model, imaging, flush=True)
    json.dump(allres, open('v1911_final_results.json', 'w'), indent=1, default=float)
