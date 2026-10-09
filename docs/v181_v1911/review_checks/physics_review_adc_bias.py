"""Effective b (primary path, +read diffusion) for the seven nominal b of the Oct-07 protocols and the resulting
apparent-ADC bias when requested (nominal) b is used in the fit.  v1.8 vs v1.81, echoes 1 and 8."""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from physics_review_common import *
from physics_review_btensor import analyse
HERE = Path(__file__).resolve().parent
B = (0, 100, 500, 1000, 2000, 3000, 6000)
out = {"nominal_b": B, "runs": {}}
for lab in ("v18", "v181"):
    out["runs"][lab] = {}
    for sgn, name in ((1000, "+X"), (-1000, "-X")):
        rows = [analyse(lab, b, (sgn, 0, 0))["echoes"] for b in B]
        E1 = [r[0]["trace_total"] for r in rows]; E8 = [r[7]["trace_total"] for r in rows]
        out["runs"][lab][name] = {"E1": E1, "E8": E8}
    for name in ("+X", "-X"):
        E1 = np.array(out["runs"][lab][name]["E1"])
        print(lab, name, "E1 b_eff:", np.round(E1, 1), " b_eff/b_nom(b>0):", np.round(E1[1:] / np.array(B[1:]), 3))
        # apparent ADC multiplier using requested-b slope between b0 and each b
        mult = (E1[1:] - E1[0]) / np.array(B[1:])
        print("      apparent-ADC multiplier (b0 -> b):", np.round(mult, 4))
        out["runs"][lab][name]["apparent_ADC_multiplier_b0_to_b"] = mult.tolist()
        # predicted ratio S(b1000)/S(b0) transform
json.dump(out, open(HERE / "physics_review_adc_bias.json", "w"), indent=1)
# conversion of the archived b1000/b0 navigator ratio
m18 = out["runs"]["v18"]["+X"]["apparent_ADC_multiplier_b0_to_b"][2]
m181 = out["runs"]["v181"]["+X"]["apparent_ADC_multiplier_b0_to_b"][2]
for R in (0.1158, 0.1170, 0.1185):
    adc_app = -np.log(R) / 1000; adc_true = adc_app / m18
    pred = np.exp(-adc_true * 1000 * m181)
    print("archived v1.8 b1000/b0 = %.4f -> apparent ADC %.5f -> true-b ADC %.5f mm2/s -> predicted v1.81 ratio %.4f" % (R, adc_app, adc_true, pred))
