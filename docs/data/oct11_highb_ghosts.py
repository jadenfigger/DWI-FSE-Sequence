"""High-b phase-encode ghosting in V (and A/E/Q b6000): energy outside the object, inside the object's readout columns.

The object (disk) mask comes from the b10 volume of the same slice (dilated 4%), so at high b the ghost zone contains only
noise plus ghosts. ghost_over_brain = (rms excess over noise in ghost zone) / (brain ROI signal). Brain ROI from
oct11_roi_masks.npz (V) or the g40/g20 masks rebuilt by oct11_roi_analysis.
"""
import sys, csv, json
from pathlib import Path
import numpy as np
from scipy import ndimage
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
sys.path.insert(0, str(Path(__file__).parent))
from oct11_load import load, ROOT, direction_label
from oct11_roi_analysis import sigma_img

FIG = ROOT/'docs/figures/physical_scanner_2026-10-11'
masks = np.load(ROOT/'docs/data/oct11_roi_masks.npz')
rows = []
for L in ('V', 'E', 'Q', 'A', 'TT', 'T', 'M', 'C'):
    s = load(L)
    for sl in range(s['S']):
        ref = s['img'][list(s['b']).index(10) if 10 in s['b'] else 0, sl]; n = ref.shape[0]
        sm = ndimage.gaussian_filter(ref, 1.5*n/128); obj = ndimage.binary_fill_holes(sm > .2*np.percentile(sm, 99))
        dil = ndimage.binary_dilation(obj, iterations=int(.04*n)); cols = np.flatnonzero(obj.any(0))
        zone = np.zeros_like(obj); zone[:, cols.min():cols.max()+1] = True; zone &= ~dil
        key = f'V_sl{sl+1}_brain' if L == 'V' else ('TT_sl1_brain' if L == 'TT' else ('E_sl1_brain' if s['dwell_us'] == 25 else 'C_sl1_brain'))
        brain = masks[key]
        for e in range(s['E']):
            im = s['img'][e, sl]; sig = sigma_img(s['kspace'][e, sl])
            ex = np.sqrt(max(np.mean(im[zone]**2)-2*sig**2, 0)); br = np.sqrt(max(np.mean(im[brain]**2)-2*sig**2, 0))
            rows.append(dict(scan=L, slice=sl+1, vol=e+1, b=float(s['b'][e]), dir=direction_label(s['vec'][e]), ghost_rms_over_noise=ex/sig,
                             brain_snr=br/sig, ghost_over_brain=ex/br if br > 0 else np.nan))
with open(ROOT/'docs/data/oct11_highb_ghosts.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
for r in rows:
    if r['b'] >= 1000:
        print(f"{r['scan']:2s} sl{r['slice']} b{r['b']:<5g}{r['dir']:3s} ghost/brain {r['ghost_over_brain']:.3f}  ghost rms/noise {r['ghost_rms_over_noise']:.2f}  brainSNR {r['brain_snr']:.1f}")
# figure: V centre slice high-b, brain-window
V = load('V'); fig, axs = plt.subplots(3, 6, figsize=(18, 9))
for sl in range(3):
    for j, e in enumerate([4, 5, 6, 7, 8, 9]):
        im = V['img'][e, sl]; ax = axs[sl, j]; ax.imshow(im, cmap='gray', vmax=np.percentile(im, 99.7)); ax.axis('off')
        ax.set_title(f"sl{sl+1} z{V['offsets_mm'][sl]:+g} b{V['b'][e]:g} {direction_label(V['vec'][e])}", fontsize=9)
fig.suptitle('V (v1.82, 256x256, TR2000, TE44, Delta30): b3000/b6000 along +x/+y/+z. Vertical bands = phase-encode ghosts (shot-to-shot phase errors)')
fig.tight_layout(); fig.savefig(FIG/'V_highb_ghosts.png', dpi=80); plt.close(fig)
