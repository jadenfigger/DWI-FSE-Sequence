"""Per-line echo-peak centroid (samples) for the highest-energy lines of archived b=0 data: v1.8 navigator lines (E1-E8)
and v1.91/v1.92 (ss-MGOT/Alsop) data.  Read-only."""
import sys, json
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scanner" / "recon"))
from get_mrd_3d4 import get_mrd_3d4
out = {}
for d in sorted((ROOT / "experiments").glob("FSE-DWI_10-0[57]-2026_v1[89]*")):
    for mrd in d.glob("*.MRD"):
        im, dim, par = get_mrd_3d4(mrd, "seq", "seq")
        a = np.abs(im[0, 0, 0, 0]); en = (a ** 2).sum(1); idx = np.arange(a.shape[1])
        top = np.nonzero(en > 0.3 * en.max())[0]
        c = []
        for v in top:
            pk = int(np.argmax(a[v])); lo, hi = max(pk - 6, 0), min(pk + 7, a.shape[1])
            c.append(float((a[v, lo:hi] ** 2 * idx[lo:hi]).sum() / (a[v, lo:hi] ** 2).sum()))
        first8 = [round(x, 2) for x in c[:8]]
        out[d.name] = {"dim": dim, "n_lines_>30%": int(len(top)), "first8_centroids": first8, "mean": float(np.mean(c)), "std": float(np.std(c)),
                       "PE_order": par.get("PE_order"), "sha_dir": d.name}
        print(d.name, dim, "lines>30%:", len(top), "first8", first8, "mean %.2f sd %.2f" % (np.mean(c), np.std(c)))
json.dump(out, open(Path(__file__).with_name("physics_review_echo_peak_mrd2.json"), "w"), indent=1, default=str)
