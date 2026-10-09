"""Independent reviewer echo-centering probe, not scanner/isodelay calibration.

The finite-RF Bloch simulator is used with an intravoxel off-resonance
distribution to localize the first echo's envelope near the retained ADC center.
This explicitly tests only the chosen B1/phase/distribution; its fitted maximum
is not a universal pulse isodelay. A second spatial resolution can be requested.
"""
from pathlib import Path
import argparse
import json
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from dwfse.ppl.run import map_events
from dwfse.ppl.ledger import build_ledger, adc_middle_times
from dwfse.ppl.bloch import EventBloch, Grid, SimConfig, rf_calibration_hz_per_unit
from dwfse.vendor_seq import decode

OUT = Path(__file__).parent
SC = ROOT / 'scanner'
BASE = ROOT / 'docs/v181_v1911/baseline_v7/FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl'
SOURCES = {
    'v18': (SC/'FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl', ROOT/'experiments/FSE-DWI_10-05-2026_v18_test1e/FSE-DWI_10-05-2026_v18_test1.ppr'),
    'v181': (SC/'FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl', SC/'FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppr'),
    'v191_v7': (BASE, BASE.with_suffix('.ppr')),
    'v1911': (SC/'FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl', SC/'FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppr'),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--labels', nargs='+', default=list(SOURCES))
    parser.add_argument('--nz', type=int, default=1000)
    parser.add_argument('--ny', type=int, default=8)
    parser.add_argument('--latency', type=float, default=3)
    parser.add_argument('--b1', type=float, default=1)
    parser.add_argument('--phase', type=float, default=45)
    parser.add_argument('--output', default='finite_rf_peak.json')
    args = parser.parse_args()
    started = time.time()
    result = {'scope': 'Finite RF, no molecular diffusion/read spatial coordinate; first-echo peak of uniform +/-150 Hz intravoxel distribution. Not universal isodelay or console calibration.',
              'configuration': vars(args), 'sequences': {}}
    stock = decode(SC/'utilities/rfstd44.seq').frame('3lobe_sinc_3kHz')
    for label in args.labels:
        ppl, ppr = SOURCES[label]
        it = map_events(ppl, ppr, max_shots=1, rf_latency_us=args.latency,
                        expr_costs=True, expr_scale=.8)
        led = build_ledger(it)
        cal = rf_calibration_hz_per_unit(stock.samples, stock.wait_ticks/10, it.vars['rfcal'].value)
        center = adc_middle_times(it, led)[0][1]
        offsets = np.arange(-500, 501, 10, dtype=float)
        requests = [(str(i), center+offset) for i, offset in enumerate(offsets)]
        z = (np.arange(args.nz)+.5)/args.nz * .005 - .0025
        ny = args.ny if label.startswith('v191') else 1
        y = (np.arange(ny)+.5)/ny*(.035/136)-(.035/136)/2 if ny > 1 else np.zeros(1)
        total = np.zeros(len(offsets), complex)
        for df in np.linspace(-150, 150, 15):
            cfg = SimConfig(b1_scale=args.b1, df_hz=df,
                            grad_latency_us=float(it.vars['rfdelay'].value),
                            extra_phase_deg={0: args.phase})
            sim = EventBloch(led, Grid(z,y), cal, cfg)
            _, adc = sim.run(led['rf'], {}, requests)
            total += np.array([adc[name][0].mean() for name, _ in requests])
        envelope = np.abs(total)/15
        k = int(np.argmax(envelope))
        peak = float(offsets[k])
        if 0 < k < len(offsets)-1:
            correction = .5*(envelope[k-1]-envelope[k+1])/(envelope[k-1]-2*envelope[k]+envelope[k+1])
            peak += float(correction)*10
        result['sequences'][label] = {'inputs': it.inputs,
            'ADC_center_from_excitation_us': center-led['rf'][0]['t_center'],
            'peak_offset_from_retained_center_us': peak,
            'peak_at_probe_edge': k in (0,len(offsets)-1),
            'center_over_peak': float(envelope[len(offsets)//2]/envelope.max()),
            'offsets_us': offsets.tolist(), 'envelope': envelope.tolist()}
        (OUT/args.output).write_text(json.dumps(result,indent=2)+'\n')
        print(label, peak, flush=True)
    result['elapsed_s'] = time.time()-started
    (OUT/args.output).write_text(json.dumps(result,indent=2)+'\n')


if __name__ == '__main__':
    main()
