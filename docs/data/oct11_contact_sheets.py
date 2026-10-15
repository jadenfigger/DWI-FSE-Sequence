"""Contact sheets of every 10-11 scan (uncorrected recon), one PNG per scan, plus a volume summary CSV."""
import sys, csv
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0, str(Path(__file__).parent))
from oct11_load import load_all, ROOT, direction_label

OUT = ROOT/'docs/figures/physical_scanner_2026-10-11'; OUT.mkdir(parents=True, exist_ok=True)
scans = load_all()
rows = []
for k, s in scans.items():
    E, S = s['E'], s['S']
    fig, axs = plt.subplots(S, E, figsize=(2.2*E, 2.3*S+0.4), squeeze=False)
    ref = np.percentile(s['img'][0], 99.5)
    for e in range(E):
        for sl in range(S):
            im = s['img'][e, sl]; ax = axs[sl, e]
            ax.imshow(im, cmap='gray', vmin=0, vmax=np.percentile(im, 99.5)); ax.axis('off')
            ax.set_title(f"b{s['b'][e]:g} {direction_label(s['vec'][e])}\nsl{sl+1} max/b0 {np.percentile(im,99.5)/ref:.2f}", fontsize=7)
            bg = np.concatenate([im[:12, :12].ravel(), im[:12, -12:].ravel(), im[-12:, :12].ravel(), im[-12:, -12:].ravel()])
            rows.append(dict(scan=k, version=s['version'], vol=e+1, slice=sl+1, b=s['b'][e], dir=direction_label(s['vec'][e]),
                             p99=float(np.percentile(im, 99)), mean=float(im.mean()), bg_mean=float(bg.mean()), bg_std=float(bg.std()),
                             p99_over_bg=float(np.percentile(im, 99)/bg.mean())))
    fig.suptitle(f"{k} ({s['version']}) ESP{s['esp']:g} TE{s['te']:g} TR{s['tr']:g} D{s['big_delta_ms']:g} dwell{s['dwell_us']:g} RX{s['gains']['rx']:g} — each panel own scale", fontsize=8)
    fig.tight_layout(); fig.savefig(OUT/f'contact_{k}.png', dpi=90); plt.close(fig)
with open(ROOT/'docs/data/oct11_volume_overview.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
for r in rows:
    print(r['scan'], r['vol'], r['slice'], r['b'], r['dir'], round(r['p99']), round(r['bg_mean'],1), round(r['p99_over_bg'],1))
