"""Follow-up to physics_review_bloch_corner.py: net v1.911/v7 ratio at the worst off-resonance corner for several T2
(T1 1.3 s) and an in-range milder corner.  Repo EventBloch, diagnostic only."""
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from physics_review_bloch_corner import run
HERE = Path(__file__).resolve().parent
res = []
for (b1, df, ph, relax) in ((1.1, -128.0, 90.0, (1.3, 0.060)), (1.1, -128.0, 90.0, (1.3, 0.100)), (1.0, -128.0, 0.0, None), (1.0, 128.0, 0.0, None), (1.0, -128.0, 0.0, (1.3, 0.032))):
    a7, _ = run("v7", b1, df, ph, relax); a9, _ = run("v1911", b1, df, ph, relax)
    r = a9 / a7
    print(b1, df, ph, relax, "ratio", np.round(r, 4), flush=True)
    res.append({"B1": b1, "df": df, "ph": ph, "relax": relax, "v7": a7.tolist(), "v1911": a9.tolist(), "ratio": r.tolist()})
(HERE / "physics_review_bloch_corner2.json").write_text(json.dumps(res, indent=1))
