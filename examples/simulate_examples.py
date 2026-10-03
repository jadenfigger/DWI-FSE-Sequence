"""
simulate_examples.py - run every ex*.seq through the project simulator at B1 = 1.0 and 0.8
and plot |signal| over time (examples_overview.png). Default voxel but T2-prime = 3 ms
so echoes are narrow and separate. Prints the peak of each ADC window.

    cd examples && python simulate_examples.py
(for one file use the main pipeline:  python dw.py run ex3 --seq examples/ex3_cpmg_train.seq)
"""
import glob
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dwfse import simulate as bs  # noqa: E402

files = sorted(glob.glob('ex*.seq'))
vox = bs.make_voxel(n=20000, stratified=True, T2prime=0.003)   # short T2' -> sharp echoes
fig, axs = plt.subplots(len(files), 1, figsize=(11, 2.0 * len(files)), squeeze=False)
for ax, f in zip(axs[:, 0], files):
    print(f)
    for b1, c in ((1.0, 'C0'), (0.8, 'C3')):
        r = bs.simulate(f, voxel=vox, b1=b1, rf_dt=1e-6)
        t, s = r['t_adc'] * 1e3, np.abs(r['signal'])
        gaps = np.where(np.diff(t) > 0.2)[0] + 1          # break line between ADC windows
        for seg_t, seg_s in zip(np.split(t, gaps), np.split(s, gaps)):
            ax.plot(seg_t, seg_s, color=c, lw=1.2, label=f'B1 {b1}' if seg_t[0] == t[0] else None)
        peaks = [seg_s.max() for seg_s in np.split(s, gaps)]
        print(f'   B1 {b1}: window peaks', np.round(peaks, 3))
    ax.set_title(f, fontsize=9, loc='left')
    ax.set_ylabel('|signal|')
    ax.legend(fontsize=7, loc='upper right')
axs[-1, 0].set_xlabel('time [ms]')
fig.tight_layout()
fig.savefig('examples_overview.png', dpi=110)
print('wrote examples_overview.png')
