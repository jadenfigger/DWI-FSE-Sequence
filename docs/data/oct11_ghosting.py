"""Ghost / out-of-object signal per image for the 10-11 v1.82 scans.

Object mask = gaussian-smoothed (sigma 1.5 px at 128, 3 px at 256) image > 20% of its 99th percentile, filled,
dilated by 5% of the matrix. Ghost zone = outside the dilated mask, inside the columns (readout extent) spanned by the
object, i.e. along the phase-encode direction where FSE echo-modulation ghosts land. Noise from k-space corners
(complex sample std), converted to the Rayleigh image mean expected for pure noise. Ghost ratio =
(mean(ghost zone) - noise mean) / mean(object). Reported for the low-b reference (b0/b10) and for b1000.
"""
import sys, csv
from pathlib import Path
import numpy as np
from scipy import ndimage
sys.path.insert(0, str(Path(__file__).parent))
from oct11_load import load, ROOT, direction_label

def kspace_noise_sigma(k):
    n, m = k.shape; c = np.r_[0:n//16, n-n//16:n]; r = np.r_[0:m//16, m-m//16:m]
    z = k[np.ix_(c, r)].ravel()
    return float(np.sqrt(np.mean(abs(z)**2)/2))  # per real/imag channel

def ghost(im, k):
    N, M = im.shape; s = 1.5*N/128
    sm = ndimage.gaussian_filter(im, s)
    obj = ndimage.binary_fill_holes(sm > .2*np.percentile(sm, 99))
    lab, n = ndimage.label(obj); obj = lab == (1+np.argmax(ndimage.sum(obj, lab, range(1, n+1))))
    dil = ndimage.binary_dilation(obj, iterations=int(.05*N))
    cols = np.flatnonzero(obj.any(0)); zone = np.zeros_like(obj); zone[:, cols.min():cols.max()+1] = True; zone &= ~dil
    sig_img = kspace_noise_sigma(k)/np.sqrt(N*M)   # ifft2 normalisation
    noise_mean = sig_img*np.sqrt(np.pi/2)
    return dict(object_mean=float(im[obj].mean()), ghost_mean=float(im[zone].mean()), noise_mean=noise_mean,
                ghost_ratio=float((im[zone].mean()-noise_mean)/im[obj].mean()), zone_px=int(zone.sum()), snr_object=float(im[obj].mean()/sig_img))

rows = []
for L in ['A', 'C', 'AB', 'E', 'G', 'I', 'M', 'K', 'O', 'Q', 'S', 'T', 'TT', 'V']:
    s = load(L)
    for e in range(s['E']):
        for sl in range(s['S']):
            g = ghost(s['img'][e, sl], s['kspace'][e, sl])
            rows.append(dict(scan=L, vol=e+1, slice=sl+1, z_mm=s['offsets_mm'][sl] if s['offsets_mm'] else 0, b=s['b'][e], dir=direction_label(s['vec'][e]),
                             tr=s['tr'], esp=s['esp'], dwell=s['dwell_us'], **g))
with open(ROOT/'docs/data/oct11_ghosting.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
for r in rows:
    if r['b'] <= 10 or r['b'] == 1000:
        print(f"{r['scan']:3s} v{r['vol']:<2d} sl{r['slice']} z{r['z_mm']:+5.1f} b{r['b']:<5g}{r['dir']:3s} TR{r['tr']:g} ghost {100*r['ghost_ratio']:6.2f}%  objSNR {r['snr_object']:7.1f}")
