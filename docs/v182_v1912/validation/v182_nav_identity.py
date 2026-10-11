"""Reproduce the v1.82 navigator-only isolation control and source-event checks.

Run from the repository root: python docs/v182_v1912/validation/v182_nav_identity.py
The control is validation-only. It retains items 2--4 and the approved image
compaction, removing only item 5 (navigator mode 2). It is not a scanner release.
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import examples.build_v182_ppl as builder
from dwfse.ppl.run import map_events
from examples.v19_validate_events import COST_MODELS, event_signature

OUT = Path(__file__).resolve().parent
CONTROL = OUT / "v182_items2to4_control.ppl"
RESULTS = OUT / "v182_nav_identity.json"


def generate_control() -> str:
    """Execute the original builder with its navigator-only transforms omitted."""
    module = ast.parse(inspect.getsource(builder.generate_ppl))
    function = module.body[0]
    navigator_anchors = {
        "nav_on==1", "if (nav_on) {", "\tcrusher_etl = views_per_seg;",
        "\t\tgp_var = (-gp_inc*gp_mul)*nav_cnt;",
        "echo_cnt < views_per_seg+de_on", "echo_cnt < views_per_seg",
        "IntToLong(views_per_seg+echoes_to_discard)",
        "IntToLong(views_per_seg-1+echoes_to_discard)",
    }
    kept = []
    omitted = []
    for statement in function.body:
        if (isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Call)
                and isinstance(statement.value.func, ast.Name)
                and statement.value.func.id == "replace"):
            call = statement.value
            anchor = ast.literal_eval(call.args[0])
            if (anchor in navigator_anchors
                    or anchor.startswith('SCROLLBAR "Navigator?"')
                    or anchor.startswith("v1.81 additive candidate,")
                    or anchor.startswith("\tphase_list = MR3040_InitList();")
                    or anchor.startswith("\tinitiate(sample_period);\n\tstarttimer();")):
                omitted.append(anchor)
                continue
            if anchor == "\tphase_sign =  1;":
                replacement = ast.literal_eval(call.args[1])
                # Keep the approved 3D/DE guards; remove the nav2 raw conversion.
                call.args[1] = ast.Constant(replacement[:replacement.index("\tif ((nav_on<0)")])
        kept.append(statement)
    assert len(omitted) == 12, omitted
    function.body = kept
    ast.fix_missing_locations(module)
    namespace = dict(builder.__dict__)
    exec(compile(module, "<v182_items2to4_control>", "exec"), namespace)
    source = namespace["generate_ppl"]()
    return "/* Validation-only items 2--4 control; not a scanner release. */\n" + source


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run() -> dict:
    frozen_hash = digest(builder.PPL)
    CONTROL.write_bytes(generate_control().replace("\n", "\r\n").encode("latin-1"))
    result = {
        "final_ppl_sha256": frozen_hash,
        "control_ppl_sha256": digest(CONTROL),
        "protocol_sha256": digest(builder.PPR),
        "scope": "Navigator-only identity against items 2--4 control; two actual shots.",
        "timing_signature_resolution_us": 0.001,
        "limits": ["Source mapping, not vendor compilation or scanner validation.",
                   "Matrix write timestamps can change inside padded timers while played events agree."],
        "cases": [],
    }
    for nav in (0, 1):
        for name, model in COST_MODELS.items():
            overrides = {"nav_on": nav, "no_views": 128 + 8 * nav,
                         "no_disacq": 0, "slice_mm_10": 0}
            final = map_events(builder.PPL, builder.PPR, overrides=overrides,
                               max_shots=2, rf_latency_us=3, **model)
            control = map_events(CONTROL, builder.PPR, overrides=overrides,
                                 max_shots=2, rf_latency_us=3, **model)
            actual = event_signature(final)
            expected = event_signature(control)
            matrix_values_equal = True
            matrix_max_write_shift = 0.0
            for index, entries in expected["matrices"].items():
                other = actual["matrices"][index]
                matrix_values_equal &= len(entries) == len(other)
                for left, right in zip(entries, other):
                    matrix_values_equal &= left[1:] == right[1:]
                    if isinstance(left[0], (int, float)):
                        matrix_max_write_shift = max(matrix_max_write_shift,
                                                     abs(right[0] - left[0]))
            checks = {
                "rf_identical": actual["rf"] == expected["rf"],
                "adc_identical": actual["adc"] == expected["adc"],
                "played_SPR_identical": actual["grad"] == expected["grad"],
                "sync_to_first_rf_identical": actual["sync_minus_first_rf_us"] == expected["sync_minus_first_rf_us"],
                "matrix_values_identical": matrix_values_equal,
            }
            case = {"nav_on": nav, "cost_model": name, "overrides": overrides,
                    "checks": checks, "pass": all(checks.values()),
                    "matrix_max_write_shift_us": round(matrix_max_write_shift, 6),
                    "rf_count": len(actual["rf"]), "adc_count": len(actual["adc"])}
            result["cases"].append(case)
            assert case["pass"], case
    assert digest(builder.PPL) == frozen_hash, "Frozen scanner PPL changed"
    result["pass"] = all(case["pass"] for case in result["cases"])
    RESULTS.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    report = run()
    print(json.dumps({"pass": report["pass"], "control_sha256": report["control_ppl_sha256"],
                      "cases": len(report["cases"])}))
