"""Independent physics-review helpers (reviewer-side; read-only wrt repo sources).

Uses the repo mapper (dwfse/ppl) ONLY to obtain mapped gradient/RF/ADC events for the actual
final bytes; all b-tensor / area / pathway computations below are re-implemented here.
"""
from pathlib import Path
import hashlib, sys
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from dwfse.ppl.run import map_events          # noqa: E402
from dwfse.ppl.ledger import build_ledger, adc_middle_times   # noqa: E402

SC = ROOT / "scanner"
V7 = ROOT / "docs/v181_v1911/baseline_v7/FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl"
SRC = {
    "v18": (SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl", ROOT / "experiments/FSE-DWI_10-05-2026_v18_test1e/FSE-DWI_10-05-2026_v18_test1.ppr"),
    "v181": (SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl", SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppr"),
    "v7": (V7, V7.with_suffix(".ppr")),
    "v1911": (SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl", SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppr"),
}
EXPECT = {"v181": "545a14ec8c65ed578ea76628796547dd463eb8cd4a2efa680de89058a837de69",
          "v1911": "716478bb357ba1479e6cc8fcc18c1085e44b3c78ecf1bdf32bb561b171838682",
          "v18": "3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2",
          "v7": "6a0d222b6c8689fbdee5f4ae412c4d5df0bea10a7da99a309fabf5dfab04d828"}
IMAGING = {"no_disacq": 0, "nav_on": 0, "no_views": 128}
COST = dict(stmt_cost_us=0.0, expr_costs=True, expr_scale=0.8)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check_hashes():
    for k, (p, _) in SRC.items():
        h = sha(p)
        assert h == EXPECT[k], (k, h)
    return {k: sha(p) for k, (p, _) in SRC.items()}


def mapped(label, overrides=None, shots=2, rf_latency_us=0.0, imaging=True):
    ppl, ppr = SRC[label]
    ov = dict(IMAGING) if imaging else {}
    ov.update(overrides or {})
    it = map_events(ppl, ppr, overrides=ov, max_shots=shots, rf_latency_us=rf_latency_us, **COST)
    if "v19_error_code" in it.vars and it.vars["v19_error_code"].value:
        raise RuntimeError(f"{label}: v19_error_code={it.vars['v19_error_code'].value}")
    return it


def waveform(led, axis):
    """Return (t breakpoints us, value DAC per segment) of the mapped PWC output."""
    W = led["G"][axis]
    return np.asarray(W.t, float), np.asarray(W.v, float)


def area(t, v, a, b):
    """Exact integral (DAC*us) of PWC over [a,b]."""
    if b <= a:
        return 0.0
    lo = np.clip(t[:-1], a, b); hi = np.clip(t[1:], a, b)
    return float(np.sum(v * (hi - lo)))
