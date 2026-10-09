"""Independent exact primary-path tensor/moment review of read relocation."""
from pathlib import Path
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from dwfse.ppl.run import map_events
from dwfse.ppl.ledger import build_ledger, adc_middle_times


def exact_primary(it, led):
    """Independent conjugating-k integration with Cartesian full 3x3 tensors."""
    lag = float(it.vars['rfdelay'].value)
    rf = led['rf']
    events = sorted([(p['t_center'], 'rf') for p in rf[1:]] +
                    [(t, 'adc') for _, t in adc_middle_times(it, led)])
    previous = rf[0]['t_center']
    k = np.zeros(3); tensor = np.zeros((3, 3)); rows = []
    fac = led['H']*1000/32767
    for t, kind in events:
        cuts = {previous, t}
        for axis in 'SPR':
            cuts.update(v+lag for v in led['G'][axis].t if previous < v+lag < t)
        cuts = sorted(cuts)
        for a, b in zip(cuts[:-1], cuts[1:]):
            dt = (b-a)*1e-6
            g = np.array([led['G'][axis].value_at((a+b)/2-lag) for axis in 'SPR'])*fac
            # Simpson's rule is exact for this quadratic outer product.
            end = k+g*dt; middle = (k+end)/2
            tensor += dt/6*(np.outer(k, k)+4*np.outer(middle, middle)+np.outer(end, end))
            k = end
        previous = t
        if kind == 'rf':
            k = -k
        else:
            bt = (2*np.pi)**2*1e-6*tensor
            rows.append({'echo': len(rows)+1, 'k_cycles_m_SPR': k.tolist(),
                         'B_s_mm2_SPR': bt.tolist(), 'trace_s_mm2': float(np.trace(bt))})
    return rows


if __name__ == '__main__':
    sequences = {
        'v18': (ROOT/'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl',
                ROOT/'experiments/FSE-DWI_10-05-2026_v18_test1e/FSE-DWI_10-05-2026_v18_test1.ppr'),
        'v181': (ROOT/'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl',
                 ROOT/'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppr')}
    result = {'scope': 'Exact PWC primary all-transverse conventional spin-echo path. Finite RF, other histories and diffusion during RF excluded.', 'runs': {}}
    for label, (ppl, ppr) in sequences.items():
        result['runs'][label] = {}
        for b in (0, 100, 1000, 6000):
            it = map_events(ppl, ppr, overrides={'acq_b': [b, 1000, 6000]},
                            max_shots=1, expr_costs=True, expr_scale=.8)
            result['runs'][label][b] = {'inputs': it.inputs, 'echoes': exact_primary(it, build_ledger(it))}
    out = Path(__file__).with_suffix('.json')
    out.write_text(json.dumps(result, indent=2)+'\n')
    print([(label, [(b, row['echoes'][0]['trace_s_mm2'], row['echoes'][0]['k_cycles_m_SPR'][2]) for b, row in rows.items()]) for label, rows in result['runs'].items()])
