"""Effective-b ADC and kurtosis fits for the 10-11 brain / PBS ROIs.

Inputs: oct11_roi_signals.csv (oct11_roi_analysis.py) and oct11_effective_b.csv (oct11_effective_b.py, echo 1 traces).
ADC uses differences of echo-1 effective traces relative to the scan's b10 (or b0) reference along +x
(the reference volumes are along +x in every scan). Kurtosis: ln S(b)/S(ref) = -db*D + db^2 D^2 K/6 fitted
over the available shells. Writes docs/data/oct11_adc_fits.json.
"""
import csv, json
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sig = list(csv.DictReader(open(ROOT/'docs/data/oct11_roi_signals.csv')))
eb = list(csv.DictReader(open(ROOT/'docs/data/oct11_effective_b.csv')))
LETTER = {'v182_testA': 'A', 'v182_testC': 'C', 'v182_testE': 'E', 'v182_testM': 'M', 'v182_testQ': 'Q', 'v182_testT': 'T',
          'v182_testTT': 'TT', 'v182_testV': 'V', 'v182_testAB': 'AB', 'v182_testK': 'K'}
trace = {}
for r in eb:
    if r['echo'] != '1':
        continue
    L = next((v for k, v in LETTER.items() if r['folder'].endswith(k)), None)
    if L:
        trace[(L, int(r['volume']))] = float(r['trace_s_mm2'])


def S(L, vol, roi, sl=1):
    return next(float(r['signal']) for r in sig if r['scan'] == L and int(r['vol']) == vol and int(r['slice']) == sl and r['roi'] == roi)


def adc(L, ref, vol, roi, sl=1, refscan=None):
    rs = refscan or L
    db = trace[(L, vol)]-trace[(rs, ref)]
    return float(np.log(S(rs, ref, roi, sl)/S(L, vol, roi, sl))/db*1e3), db


def dki(L, ref, vols, roi, sl=1):
    db = np.array([trace[(L, v)]-trace[(L, ref)] for v in vols])*1e-3
    y = np.array([np.log(S(L, ref, roi, sl)/S(L, v, roi, sl)) for v in vols])
    A = np.stack([db, -db**2/6], 1); (D, DK), *_ = np.linalg.lstsq(A, y, rcond=None)
    return dict(D=float(D), K=float(DK/D**2), db=db.tolist(), y=y.tolist())


out = {}
for roi in ('brain', 'pbs'):
    o = {}
    o['C_b1000'] = {lab: adc('C', 1, v, roi)[0] for lab, v in zip(['+x', '-x', '+y', '-y', '+z', '-z'], range(8, 14))}
    o['C_b500'] = {lab: adc('C', 1, v, roi)[0] for lab, v in zip(['+x', '-x', '+y', '-y', '+z', '-z'], range(2, 8))}
    # +/- pair geometric mean with mean trace
    for b, base in (('b500', 2), ('b1000', 8)):
        for k, ax in enumerate('xyz'):
            p, m = base+2*k, base+2*k+1
            g = np.sqrt(S('C', p, roi)*S('C', m, roi)); db = (trace[('C', p)]+trace[('C', m)])/2-trace[('C', 1)]
            o[f'C_{b}_{ax}_geomean'] = float(np.log(S('C', 1, roi)/g)/db*1e3)
        # predicted vs measured +z/-z ratio
    o['A_b10_1000'] = adc('A', 3, 6, roi)[0]; o['A_b0_1000'] = adc('A', 1, 6, roi)[0]
    for L in ('E', 'M', 'Q', 'T', 'TT'):
        o[f'{L}_b10_1000'] = adc(L, 1, 2, roi)[0]
    for sl in (1, 2, 3):
        o[f'V_sl{sl}'] = {f'b{b}{d}': adc('V', 1, v, roi, sl)[0] for v, (b, d) in enumerate([(1000, '+x'), (1000, '+y'), (1000, '+z'), (3000, '+x'), (3000, '+y'), (3000, '+z'), (6000, '+x'), (6000, '+y'), (6000, '+z')], start=2)}
    out[roi] = o
out['brain_dki'] = {f'V_sl{sl}_{d}': dki('V', 1, vols, 'brain', sl) for sl in (1, 2, 3) for d, vols in (('+x', [2, 5, 8]), ('+y', [3, 6, 9]), ('+z', [4, 7, 10]))}
out['brain_dki']['A_+x'] = dki('A', 3, [5, 6, 7], 'brain'); out['brain_dki']['E_+x'] = dki('E', 1, [2, 3], 'brain'); out['brain_dki']['Q_+x'] = dki('Q', 1, [2, 3], 'brain')
# predicted ±z signal ratio in PBS at b500/b1000 for D = mean of x/y geomean
D = np.mean([out['pbs']['C_b1000_x_geomean'], out['pbs']['C_b1000_y_geomean']])*1e-3
out['pbs_z_polarity'] = {b: dict(predicted_plus_over_minus=float(np.exp(-D*(trace[('C', p)]-trace[('C', m)]))), measured=S('C', p, 'pbs')/S('C', m, 'pbs'))
                         for b, p, m in (('b500', 6, 7), ('b1000', 12, 13))}
json.dump(out, open(ROOT/'docs/data/oct11_adc_fits.json', 'w'), indent=1)
print(json.dumps(out, indent=1, default=lambda x: round(x, 3))[:6000])
