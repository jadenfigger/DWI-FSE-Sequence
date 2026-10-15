"""Report figures for 10-11 (images, frequency-offset evidence, PBS ratio maps, brain attenuation, multi-slice, ss-MGOT).
Run after oct11_roi_analysis.py. Writes PNGs into docs/figures/physical_scanner_2026-10-11/."""
import sys, json, glob
from pathlib import Path
import numpy as np
from scipy import ndimage
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0, str(Path(__file__).parent))
from oct11_load import load, ROOT, ns
sys.path.insert(0, str(ROOT/'scanner/recon'))
from get_mrd_3d4 import get_mrd_3d4  # noqa: E402

FIG = ROOT/'docs/figures/physical_scanner_2026-10-11'
R = json.loads((ROOT/'docs/data/oct11_roi_results.json').read_text())
S = {L: load(L) for L in ('A', 'B', 'C', 'E', 'TT', 'V', '0', 'UU', 'M', 'T')}


def g(im, ax, t, p=99.5):
    ax.imshow(im, cmap='gray', vmin=0, vmax=np.percentile(im, p)); ax.set_title(t, fontsize=9); ax.axis('off')


# 1. overview
fig, axs = plt.subplots(2, 5, figsize=(17, 7.8))
g(S['A']['img'][2, 0], axs[0, 0], 'A v1.82 b10, 20 kHz, no FOV offset')
g(S['A']['img'][5, 0], axs[0, 1], 'A b1000 +x')
g(S['A']['img'][6, 0], axs[0, 2], 'A b6000 +x')
g(S['TT']['img'][0, 0], axs[0, 3], 'TT b10, FOV re-centred (+4 / -6 mm)')
g(S['TT']['img'][1, 0], axs[0, 4], 'TT b1000 +x')
for j, (e, t) in enumerate([(0, 'b10'), (1, 'b1000 +x'), (4, 'b3000 +x'), (7, 'b6000 +x')]):
    g(S['V']['img'][e, 1], axs[1, j], f'V 256² centre, {t}')
g(S['B']['img'][0, 0], axs[1, 4], 'B v1.912 b0: noise')
fig.suptitle('2026-10-11 fixed rat brain in PBS: representative images (each panel own 99.5th-percentile window)')
fig.tight_layout(); fig.savefig(FIG/'overview.png', dpi=100); plt.close(fig)


# 2. frequency-offset evidence
def img1010(tag, vol=0):
    f = glob.glob(str(ROOT/f'experiments/FSE-DWI_10-10-2026_{tag}/*.MRD'))[0]
    raw, d, p = get_mrd_3d4(f); k = raw[vol, 0, 0, 0, 8:]; N = k.shape[0]
    kk = np.zeros_like(k); kk[ns['pe_rows'](N, 8, 1)] = k
    return abs(np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(kk))))


def prof(im):
    p = im[40:95].mean(0); return p/np.percentile(p, 95)


x = (np.arange(128)-64)*35/128
fig, axs = plt.subplots(1, 3, figsize=(16, 4.2))
axs[0].plot(x, prof(S['C']['img'][0, 0]), label='C 20 kHz (50 us)'); axs[0].plot(x, prof(S['E']['img'][0, 0]), label='E 40 kHz (25 us)')
axs[0].set_title('10-11 brain/PBS: readout profile (rows 40-95, b10)'); axs[0].set_xlabel('readout position (mm)'); axs[0].legend()
a, j = img1010('v181_testA'), img1010('v181_testJ')
axs[1].plot(x, prof(a), label='A 20 kHz'); axs[1].plot(x, prof(j), label='J 40 kHz')
axs[1].set_title('10-10 water phantom: same comparison, no shift'); axs[1].set_xlabel('readout position (mm)'); axs[1].legend()
c1 = S['C']['img'][0, 0]; e1 = S['E']['img'][0, 0]; ov = np.zeros((128, 128, 3))
ov[..., 0] = c1/np.percentile(c1, 99); ov[..., 1] = e1/np.percentile(e1, 99); ov[..., 2] = ov[..., 1]
axs[2].imshow(np.clip(ov, 0, 1)); axs[2].axis('off')
axs[2].set_title('10-11 overlay: red = 20 kHz, cyan = 40 kHz\n9.1 px relative shift = 2.83 kHz centre-frequency error')
fig.tight_layout(); fig.savefig(FIG/'frequency_offset_evidence.png', dpi=100); plt.close(fig)

# 3. PBS ratio maps
pairs = [('A b1000/b10 (0 min)', 'A', 2, 5), ('C +x (5 min)', 'C', 0, 7), ('E (21 min)', 'E', 0, 1),
         ('M (42 min)', 'M', 0, 1), ('T (48 min)', 'T', 0, 1), ('TT, re-centred (53 min)', 'TT', 0, 1)]
fig, axs = plt.subplots(1, 7, figsize=(22, 3.6), gridspec_kw=dict(width_ratios=[1]*6+[.06]))
for ax, (t, L, i, j) in zip(axs, pairs):
    s = S[L]; r = ndimage.gaussian_filter(s['img'][j, 0], 1.5)/np.maximum(ndimage.gaussian_filter(s['img'][i, 0], 1.5), 1e-12)
    m = s['img'][i, 0] > .2*np.percentile(s['img'][i, 0], 99)
    im = ax.imshow(np.where(m, r, np.nan), vmin=.05, vmax=.25, cmap='coolwarm'); ax.set_title(t, fontsize=9); ax.axis('off')
plt.colorbar(im, cax=axs[-1])
fig.suptitle('b1000/b10 maps: free PBS should be uniform (~0.13 for ADC 2.05e-3 mm²/s); brain saturates the scale (red)')
fig.tight_layout(); fig.savefig(FIG/'pbs_ratio_maps.png', dpi=100); plt.close(fig)

# 4. brain attenuation
fig, axs = plt.subplots(1, 2, figsize=(13, 4.6))
for d, c in zip(['+x', '+y', '+z'], ['C0', 'C1', 'C2']):
    for sl, ls in zip(['sl1', 'sl2', 'sl3'], [':', '-', '--']):
        bs = [10, 1000, 3000, 6000]; ys = [1]+[R['V'][sl][f'b{b}{d}']['brain']['ratio'] for b in bs[1:]]
        axs[0].semilogy(bs, ys, ls, color=c, marker='o', label=f'{d} {sl}')
axs[0].set_title('V brain ROI S(b)/S(b10); dotted/solid/dashed = -2.4/0/+2.4 mm', fontsize=10)
axs[0].set_xlabel('nominal b (s/mm²)'); axs[0].legend(fontsize=7, ncol=3)
for L, c in (('A', 'k'), ('E', 'C0'), ('Q', 'C3')):
    if L == 'A':
        bs = [10, 100, 1000, 6000]
        ys = [1, R['A']['brain']['b100'], R['A']['brain']['b1000'], R['A']['brain']['b6000']]
        yp = [1, R['A']['pbs']['b100'], R['A']['pbs']['b1000'], max(R['A']['pbs']['b6000'], 1e-3)]
    else:
        bs = [10, 1000, 6000]
        ys = [1, R[L]['brain']['ratio_1000'], R[L]['brain']['ratio_6000']]
        yp = [1, R[L]['pbs']['ratio_1000'], max(R[L]['pbs']['ratio_6000'], 1e-3)]
    lab = {'A': 'A 20 kHz D40', 'E': 'E 40 kHz D40', 'Q': 'Q 40 kHz D30/TE44'}[L]
    axs[1].semilogy(bs, ys, '-o', color=c, label=lab+' brain'); axs[1].semilogy(bs, yp, '--s', color=c, label=lab+' PBS')
axs[1].set_title('+x attenuation, brain (solid) vs PBS (dashed); PBS b6000 is at the noise floor', fontsize=10)
axs[1].set_xlabel('nominal b (s/mm²)'); axs[1].legend(fontsize=7)
fig.tight_layout(); fig.savefig(FIG/'attenuation_curves.png', dpi=100); plt.close(fig)

# 5. multi-slice retention
fig, ax = plt.subplots(figsize=(7.5, 4))
labs, br, pb = [], [], []
for L, gap in (('K', '±1.2 mm'), ('S', '±2.4 mm'), ('O', '±5 mm')):
    d = R['multislice'][L]; k = [k for k in d if 'z+0' in k][0]
    labs.append(f'{L} centre slice\n(neighbours {gap})'); br.append(d[k]['brain']); pb.append(d[k]['pbs'])
xx = np.arange(3); ax.bar(xx-.18, br, .36, label='brain ROI'); ax.bar(xx+.18, pb, .36, label='PBS ROI')
ax.axhline(1, color='k', lw=.8); ax.axhline(.95, color='k', ls=':', lw=.8)
for i in range(3):
    ax.text(xx[i]-.18, br[i]+.01, f'{br[i]:.2f}', ha='center', fontsize=8); ax.text(xx[i]+.18, pb[i]+.01, f'{pb[i]:.2f}', ha='center', fontsize=8)
ax.set_xticks(xx, labs); ax.set_ylabel('b10 signal / single-slice M'); ax.set_title('Multi-slice centre-slice retention (40 kHz, ESP11, TR1000)'); ax.legend()
fig.tight_layout(); fig.savefig(FIG/'multislice_retention.png', dpi=100); plt.close(fig)

# 6. ss-MGOT
fig, axs = plt.subplots(1, 5, figsize=(18, 3.8))
g(S['A']['img'][0, 0], axs[0], 'A v1.82 b0 (RX180)')
g(S['B']['img'][0, 0], axs[1], 'B v1.912 b0 (RX180)')
g(S['0']['img'][0, 0], axs[2], 'v1.911-0 b0 (10-10 scan I protocol)')
g(S['UU']['img'][0, 0], axs[3], 'UU v1.912 b10, TR5000 TE34')
g(ndimage.gaussian_filter(S['0']['img'][0, 0], 3), axs[4], 'v1.911-0 b0 smoothed (sigma 3 px)', 99.9)
fig.tight_layout(); fig.savefig(FIG/'ssmgot_noise.png', dpi=100); plt.close(fig)
print('figures written')
