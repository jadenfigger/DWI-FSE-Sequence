"""Per-slice navigator phase model for the 10-11 multi-slice v1.82 scans (and single-slice references).

For each volume/slice the inner-product phase of echo e relative to echo 1 (oct11_navigator_echoes.csv) is unwrapped
and fitted as  phi_e = a + s*(e-1) + h*(-1)^e  over echoes 1..8: s = steady ramp per echo (deg/echo), converted to an
apparent frequency error s/(360*ESP); h = half the odd/even alternation (deg). Writes docs/data/oct11_slice_phase.csv.
"""
import csv
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
rows = [r for r in csv.DictReader(open(ROOT/'docs/data/oct11_navigator_echoes.csv')) if r['session'] == '2026-10-11']
ESP = {'K': 11, 'O': 11, 'S': 11, 'V': 14, 'A': 14, 'T': 14, 'TT': 14, 'E': 11, 'M': 11, 'Q': 11, 'C': 14, 'G': 12, 'I': 15}
out = []
for sc in ESP:
    keys = sorted({(r['volume'], r['slice']) for r in rows if r['scan'] == sc}, key=lambda k: (int(k[0]), int(k[1])))
    for v, sl in keys:
        tr = sorted([r for r in rows if r['scan'] == sc and r['volume'] == v and r['slice'] == sl], key=lambda r: int(r['echo']))
        if float(tr[0]['b']) > 1000 or len(tr) != 8:
            continue
        ph = np.radians([float(r['ip_phase_deg_vs_echo1']) for r in tr]); e = np.arange(8)
        # unwrap after removing a trial alternation: grid-search h, unwrap residual, fit ramp
        best = None
        for h in np.radians(np.arange(-90, 91, 1)):
            u = np.unwrap(ph - h*(-1)**e) ; A = np.stack([np.ones(8), e], 1); p, *_ = np.linalg.lstsq(A, u, rcond=None)
            res = float(np.sqrt(np.mean((u-A@p)**2)))
            if best is None or res < best[0]:
                best = (res, h, p)
        res, h, p = best; s = np.degrees(p[1])
        out.append(dict(scan=sc, volume=int(v), slice=int(sl), slice_offset_mm=float(tr[0]['slice_offset_mm']), b=float(tr[0]['b']), direction=tr[0]['direction'],
                        ramp_deg_per_echo=round(s, 1), apparent_freq_error_hz=round(s/360/(ESP[sc]*1e-3), 1), half_alternation_deg=round(float(np.degrees(h)), 1),
                        fit_rms_deg=round(float(np.degrees(res)), 1)))
with open(ROOT/'docs/data/oct11_slice_phase.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
for o in out:
    print(f"{o['scan']:2s} v{o['volume']} sl{o['slice']} z{o['slice_offset_mm']:+5.1f} b{o['b']:<5g}{o['direction']:3s} ramp {o['ramp_deg_per_echo']:7.1f} deg/echo ({o['apparent_freq_error_hz']:6.1f} Hz)  alt +/-{o['half_alternation_deg']:6.1f}  rms {o['fit_rms_deg']}")
