"""Oct 10 echo-resolved consistency checks used in the report.

Run: python docs/data/oct10_echo_consistency.py
Writes docs/data/oct10_echo_consistency.json. Reads raw MRDs only.

1. Per-echo navigator b/b0 ratios (noise-subtracted L2), echoes 1..8, all 10-10 scans.
2. Effective-b ADC per sequence from echo 1 alone and from the median of echoes 2..8
   (effective E1 b from docs/v181_v1911/FINAL_REPORT.md section 8; the per-echo b drift of
   ~3 s/mm2/echo is common to b0 and b1000 and cancels in the difference to within 0.5%).
3. b0-versus-b>0 complex fit of each navigator echo (|alpha|, phase, relative residual):
   detects a component present at b0 but removed by diffusion gradients.
4. Per-slice navigator norms and echo phases for the three-slice scan K.
"""
from pathlib import Path
import sys, json
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scanner/recon'))
from get_mrd_3d4 import get_mrd_3d4

TAGS = ['v181_testA', 'v1911_testB', 'v18_testC', 'v191_testD', 'v181_testE', 'v1911_testG',
        'v181_testH', 'v1911_testI', 'v181_testJ', 'v181_testK']
# effective E1 trace b (s/mm2), +x, FINAL_REPORT section 8: (b0, b1000)
B_EFF = {'v18': (12.03, 1175.93), 'v181': (4.00, 1000.71), 'v191': (20.30, 1014.55), 'v1911': (20.44, 1014.68)}


def load(tag):
    mrd = next((ROOT/'experiments').glob(f'FSE-DWI_10-10-2026_{tag}/*.MRD'))
    raw, dims, params = get_mrd_3d4(mrd)
    bval = np.loadtxt(next(mrd.parent.glob('*.bval')))
    return raw[:, 0, :, 0], dims, np.atleast_1d(bval)


def nav_amp(nav):
    """Noise-subtracted L2 norm per navigator line; noise from off-echo readout samples."""
    ns = nav.shape[-1]
    noise = np.median(abs(nav[..., np.r_[16:48, 80:112]])**2, axis=-1)/np.log(2)
    return np.sqrt(np.maximum((abs(nav)**2).sum(-1)-ns*noise, 0))


out = {}
for tag in TAGS:
    data, dims, bval = load(tag)
    E, S = dims[0], dims[2]
    seq = tag.split('_')[0]
    rec = {'b': bval.tolist()}
    sl = S//2
    nav = data[:, sl, :8, :]
    amp = nav_amp(nav)
    rec['per_echo_ratio_to_b0'] = (amp/amp[0]).tolist()
    i1000 = int(np.flatnonzero(bval == 1000)[0])
    r = amp[i1000]/amp[0]
    rec['b1000_over_b0_echo1'] = float(r[0])
    rec['b1000_over_b0_echo2to8_median'] = float(np.median(r[1:]))
    if tag.split('_')[1] in ('testA', 'testB', 'testC', 'testD'):
        db = B_EFF[seq][1]-B_EFF[seq][0]
        rec['adc_eff_echo1'] = float(np.log(1/r[0])/db)
        rec['adc_eff_echo2to8'] = float(np.log(1/np.median(r[1:]))/db)
        rec['adc_nominal_echo2to8'] = float(np.log(1/np.median(r[1:]))/1000)
    fits = []
    for echo in range(3):
        a, b = nav[0, echo], nav[1, echo]
        alpha = np.vdot(b, a)/np.vdot(b, b)
        fits.append(dict(echo=echo+1, abs_alpha=float(abs(alpha)), phase_deg=float(np.degrees(np.angle(alpha))),
                         rel_residual=float(np.linalg.norm(a-alpha*b)/np.linalg.norm(a))))
    rec['b0_vs_next_volume_fit'] = fits
    rec['echo_phase_deg_center_sample'] = {f'vol{v}': np.degrees(np.angle(nav[v, :, 64])).tolist() for v in range(min(E, 2))}
    if S > 1:
        rec['slices'] = []
        ref = np.linalg.norm(data[0, sl, 0])
        for s in range(S):
            n = data[:, s, :8, :]
            rec['slices'].append(dict(slice=s+1, b0_norm_rel_centre=(np.linalg.norm(n[0], axis=1)/ref).tolist(),
                                      b0_echo_phase_deg=np.degrees(np.angle(n[0, :, 64])).tolist(),
                                      b1000_over_b0_echo1=float(np.linalg.norm(n[1, 0])/np.linalg.norm(n[0, 0]))))
    out[tag] = rec

(ROOT/'docs/data/oct10_echo_consistency.json').write_text(json.dumps(out, indent=1))
for tag, rec in out.items():
    line = f"{tag:12s} b1000/b0 E1 {rec['b1000_over_b0_echo1']:.4f}  E2-8 {rec['b1000_over_b0_echo2to8_median']:.4f}"
    if 'adc_eff_echo1' in rec:
        line += f"  ADCeff E1 {rec['adc_eff_echo1']*1e3:.3f}  E2-8 {rec['adc_eff_echo2to8']*1e3:.3f}  ADCnom E2-8 {rec['adc_nominal_echo2to8']*1e3:.3f}"
    f = rec['b0_vs_next_volume_fit'][0]
    line += f"  b0-fit E1 |a| {f['abs_alpha']:.3f} ph {f['phase_deg']:+.1f} res {f['rel_residual']:.3f}"
    print(line)
