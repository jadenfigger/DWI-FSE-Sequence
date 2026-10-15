"""Checks for the 2026-10-12 PPRs (run from the repository root after make_pprs.py).

Per protocol: (1) console rule NO_VIEWS % VIEWS_PER_SEGMENT == 0; (2) every :VAR the PPL declares is
present, in PPL declaration order (the console rejects out-of-order records); (3) diffusion arrays fit
(512 rows v1.83, 64 rows v1.912); (4) the event model maps the protocol, reports no error/minimum
messages and emits ADCs (first two shots; every diffusion row is checked by overriding the row).
Writes validation.json. Source model only: it cannot certify vendor compilation or console acceptance.
"""
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from dwfse.ppl.run import map_events  # noqa: E402

VERS = {"v183": "1.83", "v1912": "1.912"}
BAD = re.compile(r"error|minimum|too short|increase|reduce|not supported|must|invalid|overflow", re.I)


def declared(ppl):
    t = ppl.read_text(encoding="latin-1")
    return [m.split(",")[-1].strip(" ;\r").lower() for m in re.findall(r"^(?:EDITTEXT|SCROLLBAR)[^\n]*", t, re.M)]


def main():
    man = json.loads((OUT/"manifest.json").read_text())
    results, fails = [], []
    for p in man["protocols"]:
        ppl = ROOT/f"scanner/FSE_dwi_CPMG_non_CPMG_twoTE-{VERS[p['version']]}.ppl"
        ppr = OUT/p["ppr"]; text = ppr.read_text(encoding="latin-1")
        nv = int(re.search(r":NO_VIEWS no_views, (\d+)", text)[1]); vps = int(re.search(r":VIEWS_PER_SEGMENT views_per_seg, (\d+)", text)[1])
        vars_ = [v.lower() for v in re.findall(r"^:VAR (\w+),", text, re.M)]
        decl = declared(ppl)
        order_ok = [v for v in vars_ if v in decl] == [d for d in decl if d in vars_] and all(d in vars_ for d in decl)
        n_rows = len(p["rows"]); cap = 64 if p["version"] == "v1912" else 512
        msgs, adcs = [], []
        it = map_events(ppl, ppr, overrides={}, max_shots=2, rf_latency_us=3.0)
        msgs += [m.strip() for _, m in it.out if BAD.search(m)]; adcs.append(len(it.adc))
        # strongest rows: largest b on each direction family
        top = sorted(range(n_rows), key=lambda i: -p["rows"][i][0])[:3]
        for i in top:
            b, d = p["rows"][i]
            ov = {"no_diff_acq": 1, "no_experiments": 1, "acq_b": [b], "acq_x": [d[0]], "acq_y": [d[1]], "acq_z": [d[2]]}
            it = map_events(ppl, ppr, overrides=ov, max_shots=2, rf_latency_us=3.0)
            msgs += [f"row {i}: " + m.strip() for _, m in it.out if BAD.search(m)]; adcs.append(len(it.adc))
        r = dict(test=p["letter"], version=p["version"], no_views=nv, views_per_segment=vps, divisor_ok=nv % vps == 0,
                 var_order_ok=order_ok, rows=n_rows, rows_fit=n_rows <= cap, model_messages=msgs, adc_counts=adcs,
                 pass_=nv % vps == 0 and order_ok and n_rows <= cap and not msgs and min(adcs) > 0)
        results.append(r)
        if not r["pass_"]:
            fails.append(r)
        print(f"{p['letter']:3s} {p['version']:5s} views {nv}/{vps} ok={r['divisor_ok']} order={order_ok} rows={n_rows} adc={adcs} msgs={msgs[:2]} -> {'PASS' if r['pass_'] else 'FAIL'}")
    (OUT/"validation.json").write_text(json.dumps(dict(pass_=not fails, results=results), indent=1)+"\n")
    print("ALL PASS" if not fails else f"{len(fails)} FAIL")


if __name__ == "__main__":
    main()
