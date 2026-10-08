"""Convenience entry points: map an actual PPL + PPR to recorded events."""
from __future__ import annotations

from pathlib import Path
import hashlib

from ..vendor_seq import decode
from .preprocess import Preprocessor
from .parser import Parser
from .ppr import read_ppr
from .interp import Interp, ASSUMPTIONS

ROOT = Path(__file__).resolve().parents[2]
SCANNER = ROOT / "scanner"

RECORD_VARS = ["echo_cnt", "total_echo_cnt", "current_view", "nav_cnt", "disacq_cnt",
               "diff_acq_cnt", "completed_ex", "gp_mul", "phase_correction", "no_acq",
               "current_slice", "v19_stage", "v19_rf_index", "v19_echo", "current_view_2"]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve_library(path_text: str) -> Path:
    name = path_text.replace("\\", "/").split("/")[-1]
    for d in (SCANNER / "utilities", SCANNER / "rf"):
        for p in d.iterdir():
            if p.name.lower() == name.lower():
                return p
    if name.lower() == "v19_research_rf.seq":
        # Historical PPL snapshots used one combined library, since split into
        # per-pulse scanner/rf/v19_*.seq files with identical records.
        return ROOT / "docs/v19/compiler_compatibility/superseded_v19_research_rf.seq"
    raise FileNotFoundError(path_text)


def load_program(ppl_path):
    pp = Preprocessor([SCANNER / "utilities", SCANNER])
    toks = pp.run(Path(ppl_path))
    program = Parser(toks).program()
    libs = {}
    lib_files = {}
    for kind, path, alias in pp.uses:
        p = resolve_library(path)
        libs[alias] = decode(p)
        lib_files[alias] = str(p.relative_to(ROOT)).replace("\\", "/")
    return program, pp, libs, lib_files


def map_events(ppl_path, ppr_path, *, overrides=None, max_shots=2, stmt_cost_us=0.0,
               shot_label="slice_block_loop", rf_latency_us=0.0, grad_latency_us=0.0,
               expr_costs=False, expr_scale=0.8):
    program, pp, libs, lib_files = load_program(ppl_path)
    params, meta = read_ppr(ppr_path)
    params.update({k.lower(): v for k, v in (overrides or {}).items()})
    it = Interp(program, pp.uses, libs, params, stmt_cost_us=stmt_cost_us,
                shot_label=shot_label, max_shots=max_shots, record_vars=RECORD_VARS,
                rf_latency_us=rf_latency_us, grad_latency_us=grad_latency_us,
                expr_costs=expr_costs)
    it.expr_scale = expr_scale
    unused = it.run()
    it.inputs = {
        "ppl": str(Path(ppl_path)), "ppl_sha256": sha256(ppl_path),
        "ppr": str(Path(ppr_path)), "ppr_sha256": sha256(ppr_path),
        "includes": {str(p.relative_to(ROOT)).replace("\\", "/"): sha256(p) for p in pp.files[1:]},
        "libraries": {a: {"file": f, "sha256": sha256(ROOT / f)} for a, f in lib_files.items()},
        "overrides": overrides or {}, "unused_ppr_params": unused, "assumptions": ASSUMPTIONS,
        "stmt_cost_us": stmt_cost_us, "manual_expression_costs": expr_costs,
        "manual_expression_cost_scale": expr_scale,
    }
    return it
