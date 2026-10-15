"""Can the existing per-volume navigator (nav_on=1) repair v1.82 ghosting in reconstruction?

For V, K and S (and A/E/Q high b), reconstruct every image three ways with the inherited recon corrections
(bare_bones_recon_fse.nav_correction): 'off', 'deramp_mag' (smooth per-echo amplitude only) and 'deramp'
(amplitude + per-echo phase from the navigator). Measures the phase-encode ghost ratio (same zone/ROI definition as
oct11_highb_ghosts.py) and brain/PBS ROI signals. If the errors are the same in every shot (a per-echo error), the
navigator correction should remove most of the ghosting; if they vary shot to shot (vibration, motion), it cannot.
Writes docs/data/oct11_nav_correction_test.csv and a figure.
"""
import sys, csv
from pathlib import Path
import numpy as np
from scipy import ndimage
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0, str(Path(__file__).parent))
from oct11_load import load, ROOT, ns, direction_label
from oct11_roi_analysis import sigma_img

FIG = ROOT/'docs/figures/physical_scanner_2026-10-11'
masks = np.load(ROOT/'docs/data/oct11_roi_masks.npz')
MODES = ('off', 'deramp_mag', 'deramp')


def recon(s, e, sl, mode):
    k = s['raw'][e, sl]; L, N, nav = s['L'], s['N'], s['nav']
    amp, ph, _ = ns['nav_envelope'](k, L)
    corr = np.ones(N, complex) if mode == 'off' else ns['nav_correction'](amp, ph, np.arange(N) % L, s['rows'], N, 'deramp', mode == 'deramp', .01, s['pe'])
    kk = np.zeros((N, s['nsamp']), complex); kk[s['rows']] = k[nav*L:]*corr[:, None]
    return abs(np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(kk)))), kk


def zone_of(ref):
    n = ref.shape[0]; sm = ndimage.gaussian_filter(ref, 1.5*n/128)
    obj = ndimage.binary_fill_holes(sm > .2*np.percentile(sm, 99))
    dil = ndimage.binary_dilation(obj, iterations=int(.04*n)); cols = np.flatnonzero(obj.any(0))
    z = np.zeros_like(obj); z[:, cols.min():cols.max()+1] = True
    return z & ~dil


rows = []; keep = {}
for L in ('V', 'K', 'S', 'A', 'E', 'Q', 'TT'):
    s = load(L)
    for sl in range(s['S']):
        ref = s['img'][list(s['b']).index(10) if 10 in s['b'] else 0, sl]; zone = zone_of(ref)
        key = f'V_sl{sl+1}' if L == 'V' else ('TT_sl1' if L == 'TT' else ('E_sl1' if s['dwell_us'] == 25 else 'C_sl1'))
        brain, pbs = masks[key+'_brain'], masks[key+'_pbs']
        for e in range(s['E']):
            out = dict(scan=L, slice=sl+1, z_mm=(s['offsets_mm'] or [0])[sl], vol=e+1, b=float(s['b'][e]), dir=direction_label(s['vec'][e]))
            for mode in MODES:
                im, kk = recon(s, e, sl, mode); sig = sigma_img(kk)
                br = np.sqrt(max(np.mean(im[brain]**2)-2*sig**2, 0)); pb = np.sqrt(max(np.mean(im[pbs]**2)-2*sig**2, 0))
                gh = np.sqrt(max(np.mean(im[zone]**2)-2*sig**2, 0))
                out[f'ghost_over_brain_{mode}'] = gh/br if br else np.nan
                out[f'brain_{mode}'] = br; out[f'pbs_{mode}'] = pb
                if L == 'V' and e in (0, 9) or (L == 'K' and e == 1):
                    keep[(L, e, sl, mode)] = im
            rows.append(out)
with open(ROOT/'docs/data/oct11_nav_correction_test.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
for r in rows:
    print(f"{r['scan']:2s} sl{r['slice']} z{r['z_mm']:+4.1f} b{r['b']:<5g}{r['dir']:3s} ghost/brain off {r['ghost_over_brain_off']:.3f}  amp {r['ghost_over_brain_deramp_mag']:.3f}  amp+phase {r['ghost_over_brain_deramp']:.3f}"
          f"   PBS amp+phase/off {r['pbs_deramp']/max(r['pbs_off'],1e-12):.3f}")

fig, axs = plt.subplots(3, 4, figsize=(15, 11))
for i, (L, e, sl, t) in enumerate([('V', 9, 1, 'V centre b6000 +z'), ('V', 0, 0, 'V slice -2.4 mm b10'), ('K', 1, 2, 'K slice +1.2 mm b10')]):
    for j, mode in enumerate(('off', 'deramp')):
        im = keep[(L, e, sl, mode)]
        axs[i, j].imshow(im, cmap='gray', vmax=np.percentile(im, 99.5)); axs[i, j].axis('off')
        axs[i, j].set_title(f"{t}\n{'no correction' if mode == 'off' else 'navigator amplitude + phase'}", fontsize=9)
    d = keep[(L, e, sl, 'deramp')]-keep[(L, e, sl, 'off')]
    axs[i, 2].imshow(d, cmap='coolwarm', vmin=-np.percentile(abs(d), 99), vmax=np.percentile(abs(d), 99)); axs[i, 2].axis('off'); axs[i, 2].set_title('difference (corrected - off)', fontsize=9)
    axs[i, 3].plot(keep[(L, e, sl, 'off')].mean(1), label='off'); axs[i, 3].plot(keep[(L, e, sl, 'deramp')].mean(1), label='corrected')
    axs[i, 3].set_title('mean along readout vs phase-encode row', fontsize=9); axs[i, 3].legend(fontsize=8)
fig.tight_layout(); fig.savefig(FIG/'nav_correction_test.png', dpi=90); plt.close(fig)
