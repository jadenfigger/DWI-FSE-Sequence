"""Empirical echo-peak position along the readout in archived v1.8 raw data (b=0 volume, test1/test1e etc.).

Read-only on the MRD. Answers (empirically, without models) how far the echo centre sits from the nominal ADC centre
(sample 64 of 128, 50 us dwell) per echo - i.e. the combined effect of RF latency, gradient lag, selective-RF effective
centre and eddy/ADC-filter delay that a fixed isodelay shift would try to correct.
"""
import sys, json, glob
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scanner" / "recon"))
from get_mrd_3d4 import get_mrd_3d4

HERE = Path(__file__).resolve().parent
out = {}
for mrd in sorted(glob.glob(str(ROOT / "experiments" / "FSE-DWI_10-0[57]-2026_v18_test*" / "*.MRD"))):
    try:
        im, dim, par = get_mrd_3d4(mrd, "seq", "seq")
    except Exception as e:
        print(mrd, "ERR", e); continue
    name = Path(mrd).parent.name
    # dims (no_expts, no_echoes, no_slices, no_views_2, no_views, no_samples)
    print(name, dim, {k: par.get(k) for k in ("no_samples", "sample_period", "dwell") if k in par})
    d = im
    res = []
    for ex in range(dim[0]):
        row = []
        for e in range(dim[1]):
            blk = np.abs(d[ex, e, 0, 0])                    # (views, samples)
            energy = (blk ** 2).sum(1)
            top = np.argsort(-energy)[:max(4, dim[4] // 16)]
            prof = (blk[top] ** 2).sum(0)
            n = len(prof); idx = np.arange(n)
            pk = int(np.argmax(prof))
            # parabolic sub-sample peak and centroid over +-6 samples
            lo, hi = max(pk - 6, 0), min(pk + 7, n)
            cen = float((prof[lo:hi] * idx[lo:hi]).sum() / prof[lo:hi].sum())
            row.append({"peak_sample": pk, "centroid_sample": cen})
        res.append(row)
    out[name] = {"dim": dim, "per_experiment_per_echo": res}
    b0 = res[0]
    print("   exp0 centroid per echo:", [round(x["centroid_sample"], 2) for x in b0], " peak:", [x["peak_sample"] for x in b0])
(HERE / "physics_review_echo_peak_from_mrd.json").write_text(json.dumps(out, indent=1))
