"""ROI masks for the 2026-10-12 analysis. Writes docs/data/oct12_roi_masks.npz and a QC figure.

One whole-brain ROI per sample (plus free PBS ex vivo), centre slice:

Ex vivo (fixed rat brain in PBS, volume coil), defined on v1.83 scan Q (highest-SNR nav1 scan, RX 120):
  ex_pbs    free PBS above the brain: b1000/b10 (mean x,y,z) < 0.30, b10 > 50% of the PBS level, rows < 84,
            opened and eroded 3 px (clear of the holder spokes, the bubble and the tube wall)
  ex_brain  b1000/b10 > 0.45 with b3000 signal present, largest component, filled, then eroded 2 px so
            no pixel touches PBS (partial volume with PBS would raise both b10 signal and ADC); largest
            component kept
In vivo (surface coil on the dorsal head), drawn on EPI A b0 and v1.83 iA b10, which register within 1 px:
  iv_brain  hand-traced cerebrum outline (polygon below) eroded 1 px; excludes the temporalis muscle,
            scalp and the dorsal CSF rim. Depth from the coil runs down the rows (row 53 = dorsal surface).
Noise: readout-side background columns (no phase-encode ghosts): in vivo 2-13 and 115-126; ex vivo
115-126 only (the left columns carry a tube-edge artifact).
"""
import numpy as np
from scipy import ndimage as ndi
from matplotlib.path import Path as MPath
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from oct12_load import load, load_epi, ROOT

FIG = ROOT/'docs/figures/physical_scanner_2026-10-12'
NOISE_COLS_IV = np.r_[2:14, 115:127]   # in vivo: both readout sides are clean background
NOISE_COLS_EX = np.r_[115:127]          # ex vivo: the left columns carry a tube-edge artifact
# (row, col) vertices of the in-vivo cerebrum outline, centre slice
IV_OUTLINE = [(53, 52), (52, 64), (53, 78), (56, 84), (60, 88), (66, 91), (74, 91), (80, 88), (85, 82),
              (88, 74), (88, 58), (85, 50), (80, 44), (74, 41), (66, 41), (60, 44), (56, 48)]


def polygon_mask(vertices, shape=(128, 128)):
    rr, cc = np.mgrid[:shape[0], :shape[1]]
    path = MPath([(c, r) for r, c in vertices])
    return path.contains_points(np.c_[cc.ravel(), rr.ravel()]).reshape(shape)


def exvivo_masks():
    q = load('Q'); I = q['img'][:, 1]
    r1000 = I[1:4].mean(0)/np.maximum(I[0], 1e-9)
    rows = np.arange(128)[:, None]*np.ones((1, 128))
    pbs_level = np.percentile(I[0][(r1000 < 0.3) & (rows < 84)], 75)
    pbs = (r1000 < 0.30) & (I[0] > 0.5*pbs_level) & (rows < 84)
    pbs = ndi.binary_erosion(ndi.binary_opening(pbs, iterations=1), iterations=3)
    sigma = np.sqrt(np.mean(I[0][4:124, NOISE_COLS_EX]**2)/2)
    brain = (r1000 > 0.45) & (I[4:7].mean(0) > 4*sigma)
    lab, n = ndi.label(brain); brain = lab == (np.argmax(ndi.sum(brain, lab, range(1, n+1)))+1)
    brain = ndi.binary_fill_holes(ndi.binary_closing(brain, iterations=2))
    brain = ndi.binary_erosion(brain, iterations=2)
    lab, n = ndi.label(brain); brain = lab == (np.argmax(ndi.sum(brain, lab, range(1, n+1)))+1)
    return dict(ex_pbs=pbs, ex_brain=brain, ex_ref=I[0])


def invivo_masks():
    a = load('iA'); e = load_epi('epiA')
    brain = ndi.binary_erosion(polygon_mask(IV_OUTLINE), iterations=1)
    return dict(iv_brain=brain, iv_ref_fse=a['img'][0, 3], iv_ref_epi=e['img'][0, 1])


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    m = {**exvivo_masks(), **invivo_masks()}
    np.savez_compressed(ROOT/'docs/data/oct12_roi_masks.npz', **m)
    fig, ax = plt.subplots(1, 3, figsize=(15, 5.2))
    def overlay(a, ref, layers, title, ylim, noise_cols):
        a.imshow(ref, cmap='gray', vmax=np.percentile(ref, 99.5), interpolation='nearest')
        for k, c in layers:
            a.contour(m[k].astype(float), [0.5], colors=c, linewidths=1.2)
        for c0 in noise_cols:
            a.add_patch(plt.Rectangle((c0-0.5, 3.5), 12, 120, fill=False, ec='tab:red', lw=1, ls='--'))
        a.set_title(title, fontsize=10); a.set_xlim(-0.5, 127.5); a.set_ylim(*ylim); a.axis('off')
    overlay(ax[0], m['ex_ref'], [('ex_pbs', 'tab:cyan'), ('ex_brain', 'tab:orange')],
            'Ex vivo, Q b10, centre slice\nPBS (cyan), whole brain (orange), noise (red dashed)', (127.5, -0.5), [115])
    overlay(ax[1], m['iv_ref_fse'], [('iv_brain', 'tab:orange')],
            'In vivo, v1.83 iA b10, 0 mm\nwhole brain (orange), noise (red dashed)', (127.5, -0.5), [2, 115])
    overlay(ax[2], m['iv_ref_epi'], [('iv_brain', 'tab:orange')], 'In vivo, EPI b0, 0 mm (same ROI)', (127.5, -0.5), [2, 115])
    plt.tight_layout(); plt.savefig(FIG/'roi_placement.png', dpi=130); plt.close()
    print({k: int(v.sum()) for k, v in m.items() if v.dtype == bool})


if __name__ == '__main__':
    main()
