"""Conservative source checks for additive v1.81/v1.911 candidates.

This does not run PPLC, compile Forth, or measure a target image. It reuses the
historical repository estimates and reports every limitation in the JSON output.
Run with a PPL path; --baseline-source permits grandfathering exact inherited
comments, macro definitions and printed literals against the appropriate source.
Use --method-only for the smaller ss-MGOT image budget.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dwfse.ppl.preprocess import Preprocessor  # noqa: E402
from dwfse.ppl.run import load_program  # noqa: E402

SC = ROOT / "scanner"
V18 = SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl"
SOURCE_PART = re.compile(r'"(?:[^"\\\n]|\\.)*"|/\*.*?\*/|//[^\n]*|\\\\[^\n]*', re.S)


def walk(node):
    if isinstance(node, dict):
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, (tuple, list)):
        if isinstance(node, tuple) and node and isinstance(node[0], str):
            yield node
        for value in node:
            if isinstance(value, (tuple, list, dict)):
                yield from walk(value)


def node_size(node):
    if isinstance(node, tuple):
        if node and node[0] in ("label", "decl", "nop"):
            return 0
        return 1 + sum(node_size(value) for value in node
                       if isinstance(value, (tuple, list)))
    return sum(node_size(value) for value in node) if isinstance(node, list) else 0


def program_metrics(program):
    nodes = list(walk(program))
    types = {name.lower(): node[1] for node in nodes if node[0] == "decl"
             for name, _, _ in node[3]}

    def is_long(expr):
        kind = expr[0]
        if kind == "num":
            return expr[2]
        if kind in ("var", "index"):
            return types.get(expr[1].lower()) == "long"
        if kind == "call":
            return expr[1].lower() in ("inttolong", "unsignedtolong")
        if kind == "un":
            return expr[1] != "!" and is_long(expr[2])
        if kind == "bin":
            return expr[1] not in ("==", "!=", "<", ">", "<=", ">=", "&&", "||") and (
                is_long(expr[2]) or is_long(expr[3]))
        return kind == "assign" and is_long(expr[1])

    long_params = {"delay32": 0, "scale": 0, "loword": 0, "hiword": 0}
    warnings = []
    for node in nodes:
        if node[0] != "call" or node[1].lower() == "printf":
            continue
        for index, arg in enumerate(node[2]):
            if is_long(arg) and long_params.get(node[1].lower()) != index:
                warnings.append({"call": node[1].lower(), "argument": index,
                                 "expression": repr(arg)})
    conditional_sizes = []
    for node in nodes:
        if node[0] == "if":
            conditional_sizes.extend(node_size(body) for body in node[2:4] if body is not None)
        elif node[0] in ("do", "for"):
            conditional_sizes.append(node_size(node[1] if node[0] == "do" else node[2]))
    arrays = sum(2 * dim[1] for node in nodes if node[0] == "decl"
                 for _, dim, _ in node[3] if dim is not None)
    strings = sum(len(node[1]) + 3 for node in nodes if node[0] == "str")
    code_nodes = sum(node_size(body) for _, body in program[1].values())
    return {"predicted_W007_W008": warnings,
            "largest_conditional_body_nodes": max(conditional_sizes, default=0),
            "code_nodes": code_nodes, "array_bytes_model": arrays,
            "string_bytes_model": strings,
            "estimated_image_bytes": round(2.6 * code_nodes + arrays + strings)}


def source_features(source, macro_names):
    parts = list(SOURCE_PART.finditer(source))
    long_literals = Counter(m[0] for m in parts if m[0].startswith('"') and len(m[0][1:-1]) > 48)
    risky_comments = Counter(m[0] for m in parts if m[0].startswith("//") and any(
        re.search(r"\b" + re.escape(name) + r"\s*\(", m[0]) for name in macro_names))
    function_defines = Counter(re.findall(r"(?m)^\s*#define\s+\w+\([^\n]*", source))
    return long_literals, risky_comments, function_defines


def audit(ppl, *, baseline_source=V18, method_only=False):
    ppl, baseline_source = Path(ppl).resolve(), Path(baseline_source).resolve()
    program, pp, _, _ = load_program(ppl)
    reference = program_metrics(load_program(V18)[0])
    metrics = program_metrics(program)
    tokens = Preprocessor([SC / "utilities", SC]).run(ppl)
    labels = {}
    for index, token in enumerate(tokens[:-1]):
        if (token.kind == "id" and tokens[index + 1].value == ":" and index > 0
                and tokens[index - 1].value in (";", "}", "{", ":")):
            labels.setdefault(token.value, index)
    jumps = [(index, tokens[index + 1].value) for index, token in enumerate(tokens[:-1])
             if token.value == "goto"]
    undefined = sorted({name for _, name in jumps if name not in labels})
    forwards = sum(labels.get(name, -1) > index for index, name in jumps)
    macro_names = set()
    for included in set(pp.files) | {baseline_source}:
        text = Path(included).read_text(encoding="latin-1")
        macro_names.update(re.findall(r"(?m)^\s*#define\s+(\w+)\(", text))
    source = ppl.read_text(encoding="latin-1")
    base_text = baseline_source.read_text(encoding="latin-1")
    new_features = [list((actual - inherited).elements()) for actual, inherited in zip(
        source_features(source, macro_names), source_features(base_text, macro_names))]
    reference_warnings = Counter((row["call"], row["argument"], row["expression"])
                                 for row in reference["predicted_W007_W008"])
    warning_counts = Counter((row["call"], row["argument"], row["expression"])
                             for row in metrics["predicted_W007_W008"])
    new_warning_signatures = list((warning_counts - reference_warnings).elements())
    branch_limit = reference["largest_conditional_body_nodes"] * 11 // 10
    # Absolute image prediction lacks fixed target-runtime overhead. The known
    # compiling v18 is the relative reference; reserve 4 KiB for method builds.
    image_limit = reference["estimated_image_bytes"] - (4096 if method_only else 0)
    checks = {"all_jump_targets_defined": not undefined,
              "forward_gotos_below_historical_limit": forwards <= (40 if method_only else 145),
              "warning_signatures_subset_of_v18": not new_warning_signatures,
              "conditional_bodies_within_v18_margin": metrics["largest_conditional_body_nodes"] <= branch_limit,
              "estimated_image_within_relative_budget": metrics["estimated_image_bytes"] <= image_limit,
              "no_added_long_string_literals": not new_features[0],
              "no_added_macro_calls_in_slash_comments": not new_features[1],
              "no_added_function_macro_definitions": not new_features[2]}
    return {"ppl": str(ppl), "ppl_sha256": hashlib.sha256(ppl.read_bytes()).hexdigest(),
            "inherited_source": str(baseline_source),
            "inherited_source_sha256": hashlib.sha256(baseline_source.read_bytes()).hexdigest(),
            "method_only_budget": method_only, "checks": checks, "pass": all(checks.values()),
            "forward_gotos": forwards, "undefined_labels": undefined,
            "unreferenced_labels_informational": sorted(set(labels) - {name for _, name in jumps}),
            "new_warning_signatures": new_warning_signatures,
            "added_long_literals": new_features[0], "added_risky_comments": new_features[1],
            "added_function_macros": new_features[2],
            "conditional_body_limit_nodes": branch_limit,
            "relative_image_limit_bytes": image_limit, **metrics,
            "limits": ["Source model, not vendor cpp/PPLC/Forth validation.",
                       "Warning predictor covers historical W007/W008 only; unreferenced labels are informational.",
                       "48 characters is a conservative source-literal bound, not a measured console limit.",
                       "Image estimate is 2.6 bytes/AST node plus arrays and strings; fixed runtime overhead is unknown.",
                       "Includes use repository files; actual console include versions remain scanner-verify."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ppl", type=Path)
    parser.add_argument("--baseline-source", type=Path, default=V18)
    parser.add_argument("--method-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.ppl, baseline_source=args.baseline_source, method_only=args.method_only)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
